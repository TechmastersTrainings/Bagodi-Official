import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    SecurityPrincipal,
    get_security_principal,
    get_optional_security_principal,
)
from app.db.session import get_db
from app.modules.orders.models import Order
from app.modules.orders.schemas import (
    CheckoutRequest,
    DirectCheckoutRequest,
    OrderCancelRequest,
    OrderResponse,
    OrderStatusUpdateRequest,
    PaginatedOrderResponse,
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
    x_session_id: Annotated[str | None, Header(alias="X-Session-ID")] = None,
    tenant_id: Annotated[UUID | None, Query(description="Merchant context")] = None,
):
    target_tenant_id = await resolve_order_tenant_id(db, principal, x_tenant_id, tenant_id)

    # Resolve customer user details for notification and receipts
    from app.modules.identity.models import User
    user_stmt = select(User).where(User.id == customer_id)
    user_record = (await db.execute(user_stmt)).scalar_one_or_none()
    customer_email = user_record.email if user_record else None
    customer_phone = user_record.phone_e164 if user_record else None
    customer_name = user_record.display_name if user_record else None

    shipping_addr_id = payload.get("shippingAddressId")
    shipping_data = None
    if shipping_addr_id:
        from app.modules.identity.models import CustomerAddress
        try:
            addr_stmt = select(CustomerAddress).where(
                CustomerAddress.id == UUID(str(shipping_addr_id)),
                CustomerAddress.customer_id == customer_id,
            )
            found_addr = (await db.execute(addr_stmt)).scalar_one_or_none()
            if found_addr:
                shipping_data = {
                    "full_name": found_addr.full_name,
                    "recipient_name": found_addr.full_name,
                    "phone": found_addr.phone,
                    "address_line1": found_addr.address_line1,
                    "address_line2": found_addr.address_line2,
                    "landmark": found_addr.landmark,
                    "city": found_addr.city,
                    "state": found_addr.state,
                    "postal_code": found_addr.postal_code,
                    "country": "India",
                }
        except Exception:
            pass

    if not shipping_data:
        new_addr = payload.get("newShippingAddress") or {}
        recipient = (
            new_addr.get("fullName")
            or new_addr.get("full_name")
            or customer_name
            or "Valued Customer"
        )
        phone = (
            new_addr.get("phoneNumber")
            or new_addr.get("phone")
            or customer_phone
            or "+919876543210"
        )
        addr1 = (
            new_addr.get("addressLine1")
            or new_addr.get("address_line1")
            or "Bidar Main Road"
        )
        shipping_data = {
            "full_name": recipient,
            "recipient_name": recipient,
            "phone": phone,
            "address_line1": addr1,
            "address_line2": new_addr.get("addressLine2") or new_addr.get("address_line2"),
            "landmark": new_addr.get("landmark"),
            "city": new_addr.get("city") or "Bidar",
            "state": new_addr.get("state") or "Karnataka",
            "postal_code": new_addr.get("postalCode") or new_addr.get("postal_code") or "585401",
            "country": "India",
        }

        # Auto-persist newly provided address for customer profile
        if new_addr and (new_addr.get("fullName") or new_addr.get("full_name")):
            try:
                from app.modules.identity.models import CustomerAddress
                saved_addr = CustomerAddress(
                    tenant_id=target_tenant_id,
                    customer_id=customer_id,
                    full_name=recipient,
                    phone=phone,
                    address_line1=addr1,
                    address_line2=shipping_data["address_line2"],
                    landmark=shipping_data["landmark"],
                    city=shipping_data["city"],
                    state=shipping_data["state"],
                    postal_code=shipping_data["postal_code"],
                    is_default=True,
                )
                db.add(saved_addr)
                await db.commit()
            except Exception:
                pass

    p_method = "online" if str(payload.get("paymentMethod", "")).upper() in ["ONLINE", "UPI", "RAZORPAY", "CARD"] else "cod"

    try:
        checkout_req = CheckoutRequest(
            shipping_address=shipping_data,
            customer_name=shipping_data["full_name"],
            customer_email=customer_email or "customer@bagodi.in",
            customer_phone=shipping_data["phone"] or customer_phone or "+919876543210",
            payment_method=p_method,
            notes=payload.get("customerNotes"),
            coupon_code=payload.get("couponCode"),
        )
    except Exception as val_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_CHECKOUT_DATA", "message": f"Invalid checkout details: {str(val_err)}"},
        )

    try:
        # Pre-merge guest session items if any remain
        if x_session_id:
            try:
                from app.modules.orders.services import CartService
                await CartService.get_or_create_cart(
                    db, tenant_id=target_tenant_id, customer_id=customer_id, session_id=x_session_id
                )
            except Exception:
                pass

        order = await OrderService.checkout(
            db=db,
            tenant_id=target_tenant_id,
            customer_id=customer_id,
            data=checkout_req,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "CHECKOUT_FAILED", "message": f"Order placement failed: {str(exc)}"},
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
    principal: SecurityPrincipal | None,
    header_tenant_id: UUID | None,
    query_tenant_id: UUID | None,
) -> UUID:
    resolved = (principal.tenant_id if principal else None) or header_tenant_id or query_tenant_id
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
    "",
    response_model=PaginatedOrderResponse,
    summary="List orders with pagination, store, and status filters",
)
async def list_orders(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    tenant_id: Annotated[UUID | None, Query(description="Merchant context")] = None,
    store_id: Annotated[UUID | None, Query(description="Filter by store")] = None,
    status: Annotated[str | None, Query(description="Filter by order status")] = None,
    paymentStatus: Annotated[str | None, Query(description="Filter by payment status")] = None,
    search: Annotated[str | None, Query(description="Search order number or customer")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    pageSize: Annotated[int, Query(ge=1, le=100)] = 20,
    skip: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
):
    target_tenant_id = await resolve_order_tenant_id(db, principal, x_tenant_id, tenant_id)

    eff_limit = limit or pageSize
    eff_offset = skip if skip is not None else (page - 1) * eff_limit

    conditions = [Order.tenant_id == target_tenant_id]

    caller_roles = set(principal.roles or [])
    merchant_roles = {"SUPER_ADMIN", "MERCHANT_ADMIN", "STORE_MANAGER", "STAFF", "OPERATOR", "DELIVERY_STAFF"}
    if not (caller_roles & merchant_roles):
        if not principal.user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "AUTHENTICATION_REQUIRED", "message": "Authentication is required."},
            )
        conditions.append(Order.customer_id == principal.user_id)

    if store_id:
        conditions.append(Order.store_id == store_id)
    if status and status != "ALL":
        conditions.append(Order.status == status)
    if paymentStatus and paymentStatus != "ALL":
        conditions.append(Order.payment_status == paymentStatus.lower())
    if search:
        search_pattern = f"%{search}%"
        conditions.append(
            or_(
                Order.order_number.ilike(search_pattern),
                Order.customer_name.ilike(search_pattern),
                Order.customer_phone.ilike(search_pattern),
            )
        )

    count_stmt = select(func.count(Order.id)).where(*conditions)
    total_count = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Order)
        .where(*conditions)
        .options(
            selectinload(Order.items),
            selectinload(Order.status_history),
            selectinload(Order.payments),
        )
        .order_by(Order.created_at.desc())
        .offset(eff_offset)
        .limit(eff_limit)
    )
    items = list((await db.execute(stmt)).scalars().all())
    total_pages = math.ceil(total_count / eff_limit) if eff_limit > 0 else 1

    return PaginatedOrderResponse(
        items=items,
        total=total_count,
        page=page,
        pageSize=eff_limit,
        totalPages=total_pages,
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
    summary="Get customer or merchant order details by order number/id",
)
async def get_my_order(
    order_number: str,
    principal: Annotated[SecurityPrincipal | None, Depends(get_optional_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    tenant_id: Annotated[UUID | None, Query(description="Merchant context")] = None,
):
    target_tenant_id = await resolve_order_tenant_id(db, principal, x_tenant_id, tenant_id)
    caller_roles = set(principal.roles or []) if principal else set()
    merchant_roles = {"SUPER_ADMIN", "MERCHANT_ADMIN", "STORE_MANAGER", "STAFF", "OPERATOR", "DELIVERY_STAFF"}
    
    # If customer, scope strictly to customer_id; if merchant/admin or checking direct order confirmation, allow lookup
    scoped_customer_id = None
    if principal and not (caller_roles & merchant_roles):
        scoped_customer_id = principal.user_id

    return await OrderService.get_order_by_number(
        db=db,
        tenant_id=target_tenant_id,
        order_number=order_number,
        customer_id=scoped_customer_id,
    )


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Update order status (Merchant operation)",
)
async def update_order_status_universal(
    order_id: UUID,
    data: OrderStatusUpdateRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    tenant_id: Annotated[UUID | None, Query(description="Merchant context")] = None,
):
    target_tenant_id = await resolve_order_tenant_id(db, principal, x_tenant_id, tenant_id)
    return await OrderService.update_order_status(
        db=db,
        tenant_id=target_tenant_id,
        order_id=order_id,
        data=data,
        user_id=principal.user_id,
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
