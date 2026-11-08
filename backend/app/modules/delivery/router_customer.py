from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, get_security_principal
from app.db.session import get_db
from app.modules.delivery.schemas import ShipmentResponse, ShipmentTrackingHistoryResponse
from app.modules.delivery.services import DeliveryService

router = APIRouter(prefix="/customer/delivery", tags=["Customer Delivery Tracking"])


@router.get(
    "/shipments/{shipment_id}/track",
    response_model=ShipmentTrackingHistoryResponse,
)
async def track_customer_shipment(
    shipment_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    shipment = await DeliveryService.get_shipment_tracking_for_customer(
        db,
        tenant_id=principal.tenant_id,
        customer_id=principal.user_id,
        shipment_id=shipment_id,
    )
    return ShipmentTrackingHistoryResponse(
        shipment_id=shipment.id,
        shipment_number=shipment.shipment_number,
        order_id=shipment.order_id,
        status=shipment.status,
        delivery_type=shipment.delivery_type,
        courier_provider=shipment.courier_provider,
        courier_awb=shipment.courier_awb,
        courier_label_url=shipment.courier_label_url,
        delivered_at=shipment.delivered_at,
        tracking_events=shipment.tracking_events,
    )


@router.get(
    "/orders/{order_id}/shipment",
    response_model=ShipmentResponse,
)
async def get_customer_order_shipment(
    order_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    shipment = await DeliveryService.get_shipment_by_order_id_for_customer(
        db,
        tenant_id=principal.tenant_id,
        customer_id=principal.user_id,
        order_id=order_id,
    )
    return ShipmentResponse.model_validate(shipment)
