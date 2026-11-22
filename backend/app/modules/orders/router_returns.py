from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import SecurityPrincipal, get_security_principal
from app.db.session import get_db
from app.modules.catalog.models import ProductVariant
from app.modules.identity.models import User
from app.modules.orders.models import Order, OrderItem, OrderReturnRequest
from app.modules.orders.schemas import (
    OrderReturnRequestCreate,
    OrderReturnRequestResponse,
    OrderReturnReviewRequest,
)

router = APIRouter(tags=["Order Returns & Exchanges"])


def get_authenticated_customer_id(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
) -> UUID:
    if not principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTHENTICATION_REQUIRED", "message": "Customer login is required."},
        )
    return principal.user_id


def require_merchant_permission(permission: str):
    def dependency(
        principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    ) -> SecurityPrincipal:
        if principal.is_platform_user:
            return principal
        if not principal.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "TENANT_REQUIRED", "message": "Merchant context is required."},
            )
        if not principal.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "PERMISSION_DENIED", "message": f"Requires '{permission}' permission."},
            )
        return principal

    return dependency


@router.post(
    "/orders/{order_number}/returns",
    response_model=OrderReturnRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an apparel return or size exchange request for an ordered item",
)
async def submit_return_request(
    order_number: str,
    data: OrderReturnRequestCreate,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    customer_id: Annotated[UUID, Depends(get_authenticated_customer_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
):
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .where(
            Order.order_number == order_number,
            Order.customer_id == customer_id,
        )
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ORDER_NOT_FOUND", "message": f"Order {order_number} not found."},
        )

    # Eligible statuses to request a return or exchange
    if order.status not in ("DELIVERED", "COMPLETED", "CONFIRMED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_ORDER_STATE",
                "message": f"Cannot return or exchange items for an order in '{order.status}' status.",
            },
        )

    # Validate item belongs to order
    item = next((i for i in order.items if i.id == data.order_item_id), None)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ITEM_NOT_FOUND", "message": "Order item not found in this order."},
        )

    # Check if an active return/exchange request already exists for this item
    existing_stmt = select(OrderReturnRequest).where(
        OrderReturnRequest.order_item_id == data.order_item_id,
        OrderReturnRequest.status.not_in(["REJECTED", "CANCELLED"]),
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "RETURN_ALREADY_EXISTS",
                "message": f"A {existing.request_type.lower()} request is already {existing.status.lower()} for this item.",
            },
        )

    # If exchange, validate requested variant if provided
    if data.request_type == "EXCHANGE" and data.requested_variant_id:
        v_stmt = select(ProductVariant).where(ProductVariant.id == data.requested_variant_id)
        target_variant = (await db.execute(v_stmt)).scalar_one_or_none()
        if not target_variant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "VARIANT_NOT_FOUND", "message": "Requested exchange variant not found."},
            )

    return_req = OrderReturnRequest(
        tenant_id=order.tenant_id,
        order_id=order.id,
        order_item_id=item.id,
        customer_id=customer_id,
        request_type=data.request_type,
        reason=data.reason,
        detailed_reason=data.detailed_reason,
        requested_variant_id=data.requested_variant_id,
        requested_size=data.requested_size,
        status="REQUESTED",
        refund_amount=item.total_price if data.request_type == "RETURN" else None,
        images=data.images,
    )
    db.add(return_req)
    await db.commit()
    await db.refresh(return_req)
    return return_req


@router.get(
    "/orders/{order_number}/returns",
    response_model=list[OrderReturnRequestResponse],
    summary="List customer return and exchange requests for an order",
)
async def list_order_returns(
    order_number: str,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    customer_id: Annotated[UUID, Depends(get_authenticated_customer_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = (
        select(OrderReturnRequest)
        .join(Order, OrderReturnRequest.order_id == Order.id)
        .where(
            Order.order_number == order_number,
            Order.customer_id == customer_id,
        )
        .order_by(desc(OrderReturnRequest.created_at))
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get(
    "/customer/returns",
    response_model=list[OrderReturnRequestResponse],
    summary="List all return and exchange requests for the authenticated customer",
)
async def list_customer_returns(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    customer_id: Annotated[UUID, Depends(get_authenticated_customer_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = (
        select(OrderReturnRequest)
        .where(OrderReturnRequest.customer_id == customer_id)
        .order_by(desc(OrderReturnRequest.created_at))
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get(
    "/merchant/orders/returns",
    response_model=list[OrderReturnRequestResponse],
    summary="Merchant: List all return and exchange requests across store orders",
)
async def merchant_list_returns(
    principal: Annotated[SecurityPrincipal, Depends(require_merchant_permission("orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    request_type: Annotated[str | None, Query(alias="type")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    query = select(OrderReturnRequest)
    if not principal.is_platform_user and principal.tenant_id:
        query = query.where(OrderReturnRequest.tenant_id == principal.tenant_id)

    if status_filter:
        query = query.where(OrderReturnRequest.status == status_filter)
    if request_type:
        query = query.where(OrderReturnRequest.request_type == request_type)

    query = query.order_by(desc(OrderReturnRequest.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post(
    "/merchant/orders/returns/{return_id}/review",
    response_model=OrderReturnRequestResponse,
    summary="Merchant: Review, approve, reject or update status of return/exchange request",
)
async def merchant_review_return(
    return_id: UUID,
    data: OrderReturnReviewRequest,
    principal: Annotated[SecurityPrincipal, Depends(require_merchant_permission("orders.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = select(OrderReturnRequest).where(OrderReturnRequest.id == return_id)
    if not principal.is_platform_user and principal.tenant_id:
        stmt = stmt.where(OrderReturnRequest.tenant_id == principal.tenant_id)

    return_req = (await db.execute(stmt)).scalar_one_or_none()
    if not return_req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RETURN_NOT_FOUND", "message": "Return request not found."},
        )

    return_req.status = data.status
    if principal.user_id:
        user_exists = (
            await db.execute(select(User.id).where(User.id == principal.user_id))
        ).scalar_one_or_none()
        return_req.reviewed_by_user_id = user_exists
    else:
        return_req.reviewed_by_user_id = None
    return_req.reviewed_at = datetime.now(UTC)

    if data.admin_notes is not None:
        return_req.admin_notes = data.admin_notes
    if data.refund_amount is not None:
        return_req.refund_amount = data.refund_amount
    if data.pickup_tracking_id is not None:
        return_req.pickup_tracking_id = data.pickup_tracking_id

    await db.commit()
    await db.refresh(return_req)
    return return_req
