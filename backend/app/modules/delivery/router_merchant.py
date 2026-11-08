from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, get_security_principal, require_permission
from app.db.session import get_db
from app.modules.delivery.models import DeliveryAuditLog
from app.modules.delivery.schemas import (
    DeliveryAuditLogResponse,
    DeliveryDashboardMetricsResponse,
    DeliveryPersonnelCreate,
    DeliveryPersonnelResponse,
    DeliveryPersonnelUpdate,
    DeliveryVehicleCreate,
    DeliveryVehicleResponse,
    DeliveryVehicleUpdate,
    DeliveryZoneCreate,
    DeliveryZonePincodeResponse,
    DeliveryZonePincodesAddRequest,
    DeliveryZoneResponse,
    DeliveryZoneUpdate,
    RtoRequest,
    ShipmentAssignInternalRequest,
    ShipmentBookCourierRequest,
    ShipmentCreateFromOrderRequest,
    ShipmentResponse,
    ShipmentTrackingHistoryResponse,
)
from app.modules.delivery.services import DeliveryService

router = APIRouter(prefix="/merchant/delivery", tags=["Merchant Delivery & Logistics"])


# -----------------------------------------------------------------------------
# Delivery Zones
# -----------------------------------------------------------------------------
@router.post(
    "/zones",
    response_model=DeliveryZoneResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("delivery:manage"))],
)
async def create_delivery_zone(
    payload: DeliveryZoneCreate,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    zone = await DeliveryService.create_delivery_zone(
        db, tenant_id=principal.tenant_id, data=payload, actor_id=principal.user_id
    )
    return DeliveryZoneResponse.model_validate(zone)


@router.get(
    "/zones",
    response_model=list[DeliveryZoneResponse],
    dependencies=[Depends(require_permission("delivery:read"))],
)
async def list_delivery_zones(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    store_id: Annotated[UUID | None, Query()] = None,
):
    zones = await DeliveryService.list_delivery_zones(
        db, tenant_id=principal.tenant_id, store_id=store_id
    )
    return [DeliveryZoneResponse.model_validate(z) for z in zones]


@router.put(
    "/zones/{zone_id}",
    response_model=DeliveryZoneResponse,
    dependencies=[Depends(require_permission("delivery:manage"))],
)
async def update_delivery_zone(
    zone_id: UUID,
    payload: DeliveryZoneUpdate,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    zone = await DeliveryService.update_delivery_zone(
        db, tenant_id=principal.tenant_id, zone_id=zone_id, data=payload, actor_id=principal.user_id
    )
    return DeliveryZoneResponse.model_validate(zone)


@router.post(
    "/zones/{zone_id}/pincodes",
    response_model=list[DeliveryZonePincodeResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("delivery:manage"))],
)
async def add_pincodes_to_zone(
    zone_id: UUID,
    payload: DeliveryZonePincodesAddRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    pincodes = await DeliveryService.add_pincodes_to_zone(
        db, tenant_id=principal.tenant_id, zone_id=zone_id, data=payload, actor_id=principal.user_id
    )
    return [DeliveryZonePincodeResponse.model_validate(p) for p in pincodes]


# -----------------------------------------------------------------------------
# Delivery Vehicles
# -----------------------------------------------------------------------------
@router.post(
    "/vehicles",
    response_model=DeliveryVehicleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("delivery:manage"))],
)
async def create_vehicle(
    payload: DeliveryVehicleCreate,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    vehicle = await DeliveryService.create_vehicle(
        db, tenant_id=principal.tenant_id, data=payload, actor_id=principal.user_id
    )
    return DeliveryVehicleResponse.model_validate(vehicle)


@router.get(
    "/vehicles",
    response_model=list[DeliveryVehicleResponse],
    dependencies=[Depends(require_permission("delivery:read"))],
)
async def list_vehicles(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    store_id: Annotated[UUID | None, Query()] = None,
):
    vehicles = await DeliveryService.list_vehicles(
        db, tenant_id=principal.tenant_id, store_id=store_id
    )
    return [DeliveryVehicleResponse.model_validate(v) for v in vehicles]


@router.put(
    "/vehicles/{vehicle_id}",
    response_model=DeliveryVehicleResponse,
    dependencies=[Depends(require_permission("delivery:manage"))],
)
async def update_vehicle(
    vehicle_id: UUID,
    payload: DeliveryVehicleUpdate,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    vehicle = await DeliveryService.update_vehicle(
        db,
        tenant_id=principal.tenant_id,
        vehicle_id=vehicle_id,
        data=payload,
        actor_id=principal.user_id,
    )
    return DeliveryVehicleResponse.model_validate(vehicle)


# -----------------------------------------------------------------------------
# Delivery Personnel
# -----------------------------------------------------------------------------
@router.post(
    "/personnel",
    response_model=DeliveryPersonnelResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("delivery:manage"))],
)
async def create_personnel(
    payload: DeliveryPersonnelCreate,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    personnel = await DeliveryService.create_personnel(
        db, tenant_id=principal.tenant_id, data=payload, actor_id=principal.user_id
    )
    return DeliveryPersonnelResponse.model_validate(personnel)


@router.get(
    "/personnel",
    response_model=list[DeliveryPersonnelResponse],
    dependencies=[Depends(require_permission("delivery:read"))],
)
async def list_personnel(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    store_id: Annotated[UUID | None, Query()] = None,
):
    personnel = await DeliveryService.list_personnel(
        db, tenant_id=principal.tenant_id, store_id=store_id
    )
    return [DeliveryPersonnelResponse.model_validate(p) for p in personnel]


@router.put(
    "/personnel/{personnel_id}",
    response_model=DeliveryPersonnelResponse,
    dependencies=[Depends(require_permission("delivery:manage"))],
)
async def update_personnel(
    personnel_id: UUID,
    payload: DeliveryPersonnelUpdate,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    personnel = await DeliveryService.update_personnel(
        db,
        tenant_id=principal.tenant_id,
        personnel_id=personnel_id,
        data=payload,
        actor_id=principal.user_id,
    )
    return DeliveryPersonnelResponse.model_validate(personnel)


# -----------------------------------------------------------------------------
# Operational Dashboard & Audit Logs
# Note: Static path routes must precede parameterized /{shipment_id} routes!
# -----------------------------------------------------------------------------
@router.get(
    "/dashboard",
    response_model=DeliveryDashboardMetricsResponse,
    dependencies=[Depends(require_permission("delivery:read"))],
)
async def get_dashboard(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    store_id: Annotated[UUID | None, Query()] = None,
):
    metrics = await DeliveryService.get_merchant_dashboard_metrics(
        db, tenant_id=principal.tenant_id, store_id=store_id
    )
    return DeliveryDashboardMetricsResponse(**metrics)


@router.get(
    "/audit-logs",
    response_model=list[DeliveryAuditLogResponse],
    dependencies=[Depends(require_permission("delivery:read"))],
)
async def list_audit_logs(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    stmt = (
        select(DeliveryAuditLog)
        .where(DeliveryAuditLog.tenant_id == principal.tenant_id)
        .order_by(DeliveryAuditLog.created_at.desc())
        .limit(limit)
    )
    logs = (await db.execute(stmt)).scalars().all()
    return [DeliveryAuditLogResponse.model_validate(log) for log in logs]


# -----------------------------------------------------------------------------
# Shipments Management
# -----------------------------------------------------------------------------
@router.post(
    "/shipments",
    response_model=ShipmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("delivery:manage"))],
)
async def create_shipment(
    payload: ShipmentCreateFromOrderRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    shipment = await DeliveryService.create_shipment_from_order(
        db, tenant_id=principal.tenant_id, data=payload, actor_id=principal.user_id
    )
    return ShipmentResponse.model_validate(shipment)


@router.get(
    "/shipments",
    response_model=list[ShipmentResponse],
    dependencies=[Depends(require_permission("delivery:read"))],
)
async def list_shipments(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    store_id: Annotated[UUID | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    personnel_id: Annotated[UUID | None, Query()] = None,
):
    shipments = await DeliveryService.list_shipments(
        db,
        tenant_id=principal.tenant_id,
        store_id=store_id,
        status_filter=status_filter,
        personnel_id=personnel_id,
    )
    return [ShipmentResponse.model_validate(s) for s in shipments]


@router.get(
    "/shipments/{shipment_id}",
    response_model=ShipmentResponse,
    dependencies=[Depends(require_permission("delivery:read"))],
)
async def get_shipment(
    shipment_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    shipment = await DeliveryService.get_shipment_by_id(
        db, tenant_id=principal.tenant_id, shipment_id=shipment_id
    )
    return ShipmentResponse.model_validate(shipment)


@router.post(
    "/shipments/{shipment_id}/assign-internal",
    response_model=ShipmentResponse,
    dependencies=[Depends(require_permission("delivery:manage"))],
)
async def assign_internal_delivery(
    shipment_id: UUID,
    payload: ShipmentAssignInternalRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    shipment = await DeliveryService.assign_internal_delivery(
        db,
        tenant_id=principal.tenant_id,
        shipment_id=shipment_id,
        data=payload,
        actor_id=principal.user_id,
    )
    return ShipmentResponse.model_validate(shipment)


@router.post(
    "/shipments/{shipment_id}/book-courier",
    response_model=ShipmentResponse,
    dependencies=[Depends(require_permission("delivery:manage"))],
)
async def book_courier(
    shipment_id: UUID,
    payload: ShipmentBookCourierRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    shipment = await DeliveryService.book_courier_shipment(
        db,
        tenant_id=principal.tenant_id,
        shipment_id=shipment_id,
        data=payload,
        actor_id=principal.user_id,
    )
    return ShipmentResponse.model_validate(shipment)


@router.post(
    "/shipments/{shipment_id}/cancel",
    response_model=ShipmentResponse,
    dependencies=[Depends(require_permission("delivery:manage"))],
)
async def cancel_shipment(
    shipment_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    reason: Annotated[str | None, Query()] = None,
):
    shipment = await DeliveryService.cancel_shipment(
        db,
        tenant_id=principal.tenant_id,
        shipment_id=shipment_id,
        reason=reason,
        actor_id=principal.user_id,
    )
    return ShipmentResponse.model_validate(shipment)


@router.post(
    "/shipments/{shipment_id}/rto",
    response_model=ShipmentResponse,
    dependencies=[Depends(require_permission("delivery:manage"))],
)
async def process_rto(
    shipment_id: UUID,
    payload: RtoRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    shipment = await DeliveryService.process_rto(
        db,
        tenant_id=principal.tenant_id,
        shipment_id=shipment_id,
        data=payload,
        actor_id=principal.user_id,
    )
    return ShipmentResponse.model_validate(shipment)


@router.get(
    "/shipments/{shipment_id}/tracking-history",
    response_model=ShipmentTrackingHistoryResponse,
    dependencies=[Depends(require_permission("delivery:read"))],
)
async def get_tracking_history(
    shipment_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    shipment = await DeliveryService.get_shipment_by_id(
        db, tenant_id=principal.tenant_id, shipment_id=shipment_id
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
