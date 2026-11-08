from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, get_security_principal
from app.db.session import get_db
from app.modules.orders.schemas import (
    CheckoutRequest,
    OrderCancelRequest,
    OrderResponse,
    PaymentCallbackRequest,
)
from app.modules.orders.services import OrderService

router = APIRouter(prefix="/orders", tags=["Customer Orders"])


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
    tenant_id: Annotated[UUID | None, Query(description="Merchant organization ID")] = None,
):
    resolved_tenant = principal.tenant_id or tenant_id
    if not resolved_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Merchant context is required for checkout."},
        )
    return await OrderService.checkout(
        db=db,
        tenant_id=resolved_tenant,
        customer_id=customer_id,
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
    tenant_id: Annotated[UUID | None, Query(description="Merchant context")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    resolved_tenant = principal.tenant_id or tenant_id
    if not resolved_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Merchant context is required."},
        )
    return await OrderService.list_customer_orders(
        db=db, tenant_id=resolved_tenant, customer_id=customer_id, skip=skip, limit=limit
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
    tenant_id: Annotated[UUID | None, Query(description="Merchant context")] = None,
):
    resolved_tenant = principal.tenant_id or tenant_id
    if not resolved_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Merchant context is required."},
        )
    return await OrderService.get_order_by_number(
        db=db,
        tenant_id=resolved_tenant,
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
    tenant_id: Annotated[UUID | None, Query(description="Merchant context")] = None,
):
    resolved_tenant = principal.tenant_id or tenant_id
    if not resolved_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Merchant context is required."},
        )
    return await OrderService.cancel_order(
        db=db,
        tenant_id=resolved_tenant,
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
    tenant_id: Annotated[UUID | None, Query(description="Merchant context")] = None,
):
    resolved_tenant = principal.tenant_id or tenant_id
    if not resolved_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Merchant context is required."},
        )
    return await OrderService.process_payment_callback(
        db=db, tenant_id=resolved_tenant, order_id=order_id, data=data
    )

