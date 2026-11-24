from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, get_security_principal, require_permission
from app.core.tenant import TenantContext, get_current_tenant
from app.db.session import get_db
from app.modules.orders.schemas import (
    OrderCancelRequest,
    OrderNotificationRequest,
    OrderResponse,
    OrderStatusUpdateRequest,
)
from app.modules.orders.services import OrderService

router = APIRouter(prefix="/merchant/orders", tags=["Merchant Order Operations"])


@router.get(
    "",
    response_model=list[OrderResponse],
    summary="List merchant orders with store, status, and pagination filters",
    dependencies=[Depends(require_permission("orders.read"))],
)
async def list_merchant_orders(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
    store_id: Annotated[UUID | None, Query(description="Filter by store")] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await OrderService.list_merchant_orders(
        db=db,
        tenant_id=tenant.tenant_id,
        store_id=store_id,
        status_filter=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get full order details with line items and status audit history",
    dependencies=[Depends(require_permission("orders.read"))],
)
async def get_merchant_order(
    order_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await OrderService.get_order_by_id(db, tenant_id=tenant.tenant_id, order_id=order_id)


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Transition order status through server-side state machine (triggers dispatch/returns)",
    dependencies=[Depends(require_permission("orders.update"))],
)
async def update_order_status(
    order_id: UUID,
    data: OrderStatusUpdateRequest,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await OrderService.update_order_status(
        db=db,
        tenant_id=tenant.tenant_id,
        order_id=order_id,
        data=data,
        user_id=principal.user_id,
    )


@router.post(
    "/{order_id}/notify",
    summary="Dispatch customer notification event for order",
    dependencies=[Depends(require_permission("orders.update"))],
)
async def notify_merchant_order(
    order_id: UUID,
    data: OrderNotificationRequest,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    order = await OrderService.get_order_by_id(db, tenant_id=tenant.tenant_id, order_id=order_id)
    channel = (data.channel or "WHATSAPP").upper()
    custom_message = data.custom_note or data.customNote or "Your order update from Bagodi Shopping Mall"

    from app.modules.inventory.services import _resolve_user_id
    valid_user_id = await _resolve_user_id(db, principal.user_id)

    from app.modules.notifications.services import NotificationService
    await NotificationService.enqueue_outbox_event(
        db,
        tenant_id=tenant.tenant_id,
        event_type="order.customer_notification",
        aggregate_type="order",
        aggregate_id=str(order.id),
        payload={
            "order_id": str(order.id),
            "order_number": order.order_number,
            "channel": channel,
            "customer_name": order.customer_name,
            "customer_phone": order.customer_phone,
            "customer_email": order.customer_email,
            "message": custom_message,
            "status": order.status,
        },
        idempotency_key=f"outbox-notify-{order.order_number}-{channel}-{int(datetime.now(UTC).timestamp())}",
    )

    try:
        from app.modules.platform.services import PlatformService
        await PlatformService.log_action(
            db,
            actor_id=valid_user_id,
            action="ORDER_CUSTOMER_NOTIFIED",
            target_type="ORDER",
            target_id=str(order.id),
            details={
                "order_number": order.order_number,
                "channel": channel,
                "recipient": order.customer_phone if channel in ("WHATSAPP", "SMS") else order.customer_email,
                "message": custom_message,
            },
        )
    except Exception:
        pass
    await db.commit()

    return {
        "status": "success",
        "message": f"Notification dispatched to {order.customer_name} via {channel}",
        "orderId": str(order.id),
        "orderNumber": order.order_number,
        "channel": channel,
    }


@router.post(
    "/{order_id}/cancel",
    response_model=OrderResponse,
    summary="Merchant administrator cancellation of order (releases reserved stock)",
    dependencies=[Depends(require_permission("orders.cancel"))],
)
async def cancel_merchant_order(
    order_id: UUID,
    data: OrderCancelRequest,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    order = await OrderService.get_order_by_id(db, tenant_id=tenant.tenant_id, order_id=order_id)
    return await OrderService.cancel_order(
        db=db,
        tenant_id=tenant.tenant_id,
        order_number=order.order_number,
        reason=data.reason,
        user_id=principal.user_id,
    )


@router.post(
    "/process-expiry",
    summary="Trigger background processor for expired payment reservations (idempotent, releases stock)",
    dependencies=[Depends(require_permission("orders.update"))],
)
async def process_reservation_expiry(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    released_count = await OrderService.expire_stale_reservations(db, tenant_id=tenant.tenant_id)
    return {"status": "ok", "released_count": released_count}
