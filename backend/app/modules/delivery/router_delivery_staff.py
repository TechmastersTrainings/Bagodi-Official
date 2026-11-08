from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import SecurityPrincipal, get_security_principal
from app.db.session import get_db
from app.modules.delivery.models import DeliveryPersonnel, Shipment
from app.modules.delivery.schemas import (
    DeliveryPersonnelResponse,
    DutyStatusUpdateRequest,
    FailedDeliveryAttemptRequest,
    ProofOfDeliveryRequest,
    ProofOfDeliveryResponse,
    ShipmentResponse,
)
from app.modules.delivery.services import DeliveryService

router = APIRouter(prefix="/delivery-staff", tags=["Delivery Staff Operations"])


async def _resolve_staff_personnel(
    db: AsyncSession, principal: SecurityPrincipal
) -> DeliveryPersonnel:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TENANT_REQUIRED",
                "message": "Tenant context is required for delivery operations.",
            },
        )
    stmt = (
        select(DeliveryPersonnel)
        .where(
            DeliveryPersonnel.tenant_id == principal.tenant_id,
            DeliveryPersonnel.user_id == principal.user_id,
        )
        .options(selectinload(DeliveryPersonnel.vehicle))
    )
    personnel = (await db.execute(stmt)).scalar_one_or_none()
    if not personnel or not personnel.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "NOT_DELIVERY_STAFF",
                "message": "Active delivery staff profile not found for this account.",
            },
        )
    return personnel


@router.get(
    "/me/profile",
    response_model=DeliveryPersonnelResponse,
)
async def get_my_profile(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    personnel = await _resolve_staff_personnel(db, principal)
    return DeliveryPersonnelResponse.model_validate(personnel)


@router.put(
    "/me/duty-status",
    response_model=DeliveryPersonnelResponse,
)
async def update_my_duty_status(
    payload: DutyStatusUpdateRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    personnel = await DeliveryService.update_duty_status(
        db, tenant_id=principal.tenant_id, user_id=principal.user_id, data=payload
    )
    return DeliveryPersonnelResponse.model_validate(personnel)


@router.get(
    "/me/assigned-shipments",
    response_model=list[ShipmentResponse],
)
async def list_my_assigned_shipments(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
):
    personnel = await _resolve_staff_personnel(db, principal)
    stmt = (
        select(Shipment)
        .where(
            Shipment.tenant_id == principal.tenant_id,
            Shipment.assigned_personnel_id == personnel.id,
        )
        .options(
            selectinload(Shipment.items),
            selectinload(Shipment.tracking_events),
        )
    )
    if status_filter:
        stmt = stmt.where(Shipment.status == status_filter.upper())
    stmt = stmt.order_by(Shipment.created_at.desc())
    shipments = (await db.execute(stmt)).scalars().all()
    return [ShipmentResponse.model_validate(s) for s in shipments]


@router.post(
    "/shipments/{shipment_id}/pickup",
    response_model=ShipmentResponse,
)
async def pickup_shipment(
    shipment_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    personnel = await _resolve_staff_personnel(db, principal)
    shipment = await DeliveryService.get_shipment_by_id(
        db, tenant_id=principal.tenant_id, shipment_id=shipment_id
    )
    if shipment.assigned_personnel_id != personnel.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "SHIPMENT_NOT_ASSIGNED",
                "message": "This shipment is not assigned to you.",
            },
        )
    updated = await DeliveryService.pickup_shipment(
        db, tenant_id=principal.tenant_id, shipment_id=shipment_id, actor_id=principal.user_id
    )
    return ShipmentResponse.model_validate(updated)


@router.post(
    "/shipments/{shipment_id}/out-for-delivery",
    response_model=ShipmentResponse,
)
async def mark_out_for_delivery(
    shipment_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    personnel = await _resolve_staff_personnel(db, principal)
    shipment = await DeliveryService.get_shipment_by_id(
        db, tenant_id=principal.tenant_id, shipment_id=shipment_id
    )
    if shipment.assigned_personnel_id != personnel.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "SHIPMENT_NOT_ASSIGNED",
                "message": "This shipment is not assigned to you.",
            },
        )
    updated = await DeliveryService.mark_out_for_delivery(
        db, tenant_id=principal.tenant_id, shipment_id=shipment_id, actor_id=principal.user_id
    )
    return ShipmentResponse.model_validate(updated)


@router.post(
    "/shipments/{shipment_id}/deliver",
    response_model=ProofOfDeliveryResponse,
)
async def complete_delivery(
    shipment_id: UUID,
    payload: ProofOfDeliveryRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    personnel = await _resolve_staff_personnel(db, principal)
    shipment = await DeliveryService.get_shipment_by_id(
        db, tenant_id=principal.tenant_id, shipment_id=shipment_id
    )
    if shipment.assigned_personnel_id != personnel.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "SHIPMENT_NOT_ASSIGNED",
                "message": "This shipment is not assigned to you.",
            },
        )
    pod = await DeliveryService.complete_delivery(
        db,
        tenant_id=principal.tenant_id,
        shipment_id=shipment_id,
        data=payload,
        actor_id=principal.user_id,
    )
    return ProofOfDeliveryResponse.model_validate(pod)


@router.post(
    "/shipments/{shipment_id}/fail-attempt",
    response_model=ShipmentResponse,
)
async def record_failed_attempt(
    shipment_id: UUID,
    payload: FailedDeliveryAttemptRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    personnel = await _resolve_staff_personnel(db, principal)
    shipment = await DeliveryService.get_shipment_by_id(
        db, tenant_id=principal.tenant_id, shipment_id=shipment_id
    )
    if shipment.assigned_personnel_id != personnel.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "SHIPMENT_NOT_ASSIGNED",
                "message": "This shipment is not assigned to you.",
            },
        )
    updated = await DeliveryService.record_failed_attempt(
        db,
        tenant_id=principal.tenant_id,
        shipment_id=shipment_id,
        data=payload,
        actor_id=principal.user_id,
    )
    return ShipmentResponse.model_validate(updated)
