from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, get_security_principal
from app.db.session import get_db
from app.modules.orders.schemas import (
    CheckoutRequest,
    DirectCheckoutRequest,
    OrderCancelRequest,
    OrderResponse,
    PaymentCallbackRequest,
)
from app.modules.orders.services import OrderService
from app.modules.platform.models import Tenant

router = APIRouter(prefix="/orders", tags=["Customer Orders"])
customer_orders_router = APIRouter(prefix="/customer", tags=["Customer Orders Storefront"])


def get_authenticated_customer_id(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
) -> UUID:
    if not principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTHENTICATION_REQUIRED", "message": "Customer login is required."},
        )
    return principal.user_id


@router.post(
    "",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer order from cart (Storefront checkout)",
)
async def create_storefront_order(
    payload: dict,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    customer_id: Annotated[UUID, Depends(get_authenticated_customer_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    tenant_id: Annotated[UUID | None, Query(description="Merchant context")] = None,
):
    target_tenant_id = await resolve_order_tenant_id(db, principal, x_tenant_id, tenant_id)
    shipping_addr_id = payload.get("shippingAddressId")
    shipping_data = None
    if shipping_addr_id:
        from app.modules.identity.models import CustomerAddress
        try:
            addr_stmt = select(CustomerAddress).where(
                CustomerAddress.id == UUID(shipping_addr_id),
                CustomerAddress.customer_id == customer_id,
            )
            found_addr = (await db.execute(addr_stmt)).scalar_one_or_none()
            if found_addr:
                shipping_data = {
                    "recipient_name": found_addr.full_name,
                    "phone": found_addr.phone,
                    "address_line1": found_addr.address_line1,
                    "address_line2": found_addr.address_line2,
                    "city": found_addr.city,
                    "state": found_addr.state,
                    "postal_code": found_addr.postal_code,
                    "country": "India",
                }
        except Exception:
            pass

    if not shipping_data:
        new_addr = payload.get("newShippingAddress") or {}
        shipping_data = {
            "recipient_name": new_addr.get("fullName") or principal.display_name or "Valued Customer",
            "phone": new_addr.get("phoneNumber") or principal.phone_e164 or "+919876543210",
            "address_line1": new_addr.get("addressLine1") or "Bidar Main Road",
            "address_line2": new_addr.get("addressLine2"),
            "city": new_addr.get("city") or "Bidar",
            "state": new_addr.get("state") or "Karnataka",
            "postal_code": new_addr.get("postalCode") or "585401",
            "country": "India",
        }

    p_method = "online" if str(payload.get("paymentMethod", "")).upper() == "RAZORPAY" else "cod"

    checkout_req = CheckoutRequest(
        shipping_address=shipping_data,
        customer_name=shipping_data["recipient_name"],
        customer_email=principal.email,
        customer_phone=shipping_data["phone"],
        payment_method=p_method,
        notes=payload.get("customerNotes"),
        coupon_code=payload.get("couponCode"),
    )

    order = await OrderService.checkout(
        db=db,
        tenant_id=target_tenant_id,
        customer_id=customer_id,
        data=checkout_req,
    )

    razorpay_data = None
    if p_method == "online":
        razorpay_data = {
            "keyId": "rzp_test_bagodi_dev",
            "orderId": f"order_{order.order_number}",
            "amount": int(float(order.total_amount) * 100),
            "currency": "INR",
        }

    return {
        "order": OrderResponse.model_validate(order),
        "razorpay": razorpay_data,
    }


@customer_orders_router.get(
    "/orders",
    response_model=list[OrderResponse],
    summary="List current customer orders for storefront",
)
async def list_customer_storefront_orders(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    customer_id: Annotated[UUID, Depends(get_authenticated_customer_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    tenant_id: Annotated[UUID | None, Query(description="Merchant context")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    target_tenant_id = await resolve_order_tenant_id(db, principal, x_tenant_id, tenant_id)
    return await OrderService.list_customer_orders(
        db=db, tenant_id=target_tenant_id, customer_id=customer_id, skip=skip, limit=limit
    )



async def resolve_order_tenant_id(
    db: AsyncSession,
    principal: SecurityPrincipal,
    header_tenant_id: UUID | None,
    query_tenant_id: UUID | None,
) -> UUID:
    resolved = principal.tenant_id or header_tenant_id or query_tenant_id
    if resolved:
        tenant = (
            await db.execute(select(Tenant).where(Tenant.id == resolved, Tenant.status == "active"))
        ).scalar_one_or_none()
        if tenant:
            return tenant.id

    anchor = (
        await db.execute(select(Tenant).where(Tenant.status == "active").limit(1))
    ).scalar_one_or_none()
    if anchor:
        return anchor.id

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "TENANT_REQUIRED", "message": "Merchant context is required for orders."},
    )


@router.post(
    "/checkout",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Checkout cart and create order with atomic inventory reservation",
)
async def checkout_order(
    data: CheckoutRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    customer_id: Annotated[UUID, Depends(get_authenticated_customer_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    tenant_id: Annotated[UUID | None, Query(description="Merchant organization ID")] = None,
):
    target_tenant_id = await resolve_order_tenant_id(db, principal, x_tenant_id, tenant_id)
    return await OrderService.checkout(
        db=db,
        tenant_id=target_tenant_id,
        customer_id=customer_id,
        data=data,
    )


@router.post(
    "/direct-checkout",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Direct instant purchase deducting size stock atomically via double-entry ledger",
)
async def direct_checkout_order(
    data: DirectCheckoutRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    tenant_id: Annotated[UUID | None, Query(description="Merchant organization ID")] = None,
):
    target_tenant_id = await resolve_order_tenant_id(db, principal, x_tenant_id, tenant_id)
    return await OrderService.direct_checkout(
        db=db,
        tenant_id=target_tenant_id,
        customer_id=principal.user_id,
        data=data,
    )


@router.get(
    "/my-orders",
    response_model=list[OrderResponse],
    summary="List current customer's order history",
)
async def list_my_orders(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    customer_id: Annotated[UUID, Depends(get_authenticated_customer_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    tenant_id: Annotated[UUID | None, Query(description="Merchant context")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    target_tenant_id = await resolve_order_tenant_id(db, principal, x_tenant_id, tenant_id)
    return await OrderService.list_customer_orders(
        db=db, tenant_id=target_tenant_id, customer_id=customer_id, skip=skip, limit=limit
    )


@router.get(
    "/{order_number}",
    response_model=OrderResponse,
    summary="Get customer order details by order number",
)
async def get_my_order(
    order_number: str,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    customer_id: Annotated[UUID, Depends(get_authenticated_customer_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    tenant_id: Annotated[UUID | None, Query(description="Merchant context")] = None,
):
    target_tenant_id = await resolve_order_tenant_id(db, principal, x_tenant_id, tenant_id)
    return await OrderService.get_order_by_number(
        db=db,
        tenant_id=target_tenant_id,
        order_number=order_number,
        customer_id=customer_id,
    )


@router.post(
    "/{order_number}/cancel",
    response_model=OrderResponse,
    summary="Customer request to cancel order before dispatch (releases reserved inventory)",
)
async def cancel_my_order(
    order_number: str,
    data: OrderCancelRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    customer_id: Annotated[UUID, Depends(get_authenticated_customer_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    tenant_id: Annotated[UUID | None, Query(description="Merchant context")] = None,
):
    target_tenant_id = await resolve_order_tenant_id(db, principal, x_tenant_id, tenant_id)
    return await OrderService.cancel_order(
        db=db,
        tenant_id=target_tenant_id,
        order_number=order_number,
        reason=data.reason,
        customer_id=customer_id,
    )


@router.post(
    "/{order_id}/payments/callback",
    response_model=OrderResponse,
    summary="Process payment gateway status callback (provider-independent)",
)
async def payment_callback(
    order_id: UUID,
    data: PaymentCallbackRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    tenant_id: Annotated[UUID | None, Query(description="Merchant context")] = None,
):
    target_tenant_id = await resolve_order_tenant_id(db, principal, x_tenant_id, tenant_id)
    return await OrderService.process_payment_callback(
        db=db, tenant_id=target_tenant_id, order_id=order_id, data=data
    )
