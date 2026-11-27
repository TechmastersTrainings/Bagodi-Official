from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, get_security_principal
from app.db.session import get_db
from app.modules.delivery.schemas import (
    CustomerTrackingDetailResponse,
    DeliveryTrackingEventResponse,
)
from app.modules.delivery.services import DeliveryService

router = APIRouter(prefix="/customer/delivery", tags=["Customer Delivery Tracking"])


def _format_customer_tracking_detail(shipment) -> CustomerTrackingDetailResponse:
    rider_name = shipment.assigned_personnel.full_name if shipment.assigned_personnel else None
    rider_phone = shipment.assigned_personnel.phone_number if shipment.assigned_personnel else None
    vehicle_type = shipment.assigned_vehicle.vehicle_type if shipment.assigned_vehicle else None
    vehicle_reg = shipment.assigned_vehicle.registration_number if shipment.assigned_vehicle else None
    store_name = shipment.store.name if shipment.store else "Bagodi Flagship Store"
    store_address = (
        f"{shipment.store.address_line}, {shipment.store.city}"
        if shipment.store and shipment.store.address_line
        else "Bidar Mall, Fort Road, Bidar - 585401"
    )

    amount_payable = shipment.cod_amount
    payment_status = "paid"
    order_number = f"ORD-{str(shipment.order_id)[:8].upper()}"
    if shipment.order:
        amount_payable = shipment.cod_amount or shipment.order.total_amount
        payment_status = shipment.order.payment_status
        order_number = shipment.order.order_number

    return CustomerTrackingDetailResponse(
        shipment_id=shipment.id,
        shipment_number=shipment.shipment_number,
        order_id=shipment.order_id,
        order_number=order_number,
        status=shipment.status,
        delivery_type=shipment.delivery_type,
        is_cod=shipment.is_cod,
        amount_payable=amount_payable,
        payment_status=payment_status,
        delivery_otp=shipment.delivery_otp,
        rider_name=rider_name,
        rider_phone=rider_phone,
        vehicle_type=vehicle_type,
        vehicle_registration=vehicle_reg,
        estimated_delivery_time="Within 45 - 60 mins" if shipment.status == "OUT_FOR_DELIVERY" else "Today",
        store_name=store_name,
        store_address=store_address,
        shipping_address=shipment.shipping_address,
        delivered_at=shipment.delivered_at,
        tracking_events=[
            DeliveryTrackingEventResponse.model_validate(e) for e in (shipment.tracking_events or [])
        ],
    )


@router.get(
    "/shipments/{shipment_id}/track",
    response_model=CustomerTrackingDetailResponse,
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
    return _format_customer_tracking_detail(shipment)


@router.get(
    "/orders/{order_id}/shipment",
    response_model=CustomerTrackingDetailResponse,
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
    return _format_customer_tracking_detail(shipment)
