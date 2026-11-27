import time
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import SecurityPrincipal, get_security_principal
from app.db.base import utc_now
from app.db.session import get_db
from app.modules.delivery.models import DeliveryPersonnel, Shipment
from app.modules.delivery.qr_utils import generate_qr_svg, generate_upi_uri
from app.modules.delivery.schemas import (
    DeliveryPersonnelResponse,
    DoorstepCashCollectionRequest,
    DoorstepCashCollectionResponse,
    DoorstepPaymentSummaryResponse,
    DutyStatusUpdateRequest,
    FailedDeliveryAttemptRequest,
    ProofOfDeliveryRequest,
    ProofOfDeliveryResponse,
    ShipmentResponse,
    UpiPaymentVerificationRequest,
    UpiPaymentVerificationResponse,
    UpiQrGenerationResponse,
)
from app.modules.delivery.services import DeliveryService
from app.modules.orders.models import Order, PaymentTransaction
from app.modules.payments.schemas import CodCollectionRequest
from app.modules.payments.services import PaymentService

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
@router.get(
    "/my-deliveries",
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


# -----------------------------------------------------------------------------
# Doorstep Payment Collection & Dynamic UPI QR Endpoints
# -----------------------------------------------------------------------------
class AgentLocationUpdate(BaseModel):
    latitude: Decimal = Field(..., ge=-90, le=90)
    longitude: Decimal = Field(..., ge=-180, le=180)


@router.put(
    "/me/location",
    response_model=DeliveryPersonnelResponse,
)
async def update_my_location(
    payload: AgentLocationUpdate,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    personnel = await _resolve_staff_personnel(db, principal)
    personnel.current_latitude = payload.latitude
    personnel.current_longitude = payload.longitude
    personnel.last_active_at = utc_now()
    await db.commit()
    await db.refresh(personnel)
    return DeliveryPersonnelResponse.model_validate(personnel)


@router.get(
    "/shipments/{shipment_id}/payment-status",
    response_model=DoorstepPaymentSummaryResponse,
)
async def get_doorstep_payment_status(
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
            detail={"code": "SHIPMENT_NOT_ASSIGNED", "message": "This shipment is not assigned to you."},
        )

    # Fetch order
    stmt = select(Order).where(Order.id == shipment.order_id, Order.tenant_id == principal.tenant_id)
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated order not found.")

    is_paid = order.payment_status in ("captured", "paid")
    amount_payable = Decimal("0.00") if is_paid else (shipment.cod_amount or order.total_amount)

    # TechMasters commission calculation (2% on product subtotal)
    commission_2pct = Decimal(str(round(float(order.subtotal) * 0.02, 2)))
    merchant_payable = max(Decimal("0.00"), amount_payable - commission_2pct)

    return DoorstepPaymentSummaryResponse(
        shipment_id=shipment.id,
        order_id=order.id,
        order_number=order.order_number,
        recipient_name=shipment.recipient_name,
        recipient_phone=shipment.recipient_phone,
        delivery_status=shipment.status,
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        amount_payable=amount_payable,
        is_cod=shipment.is_cod or order.payment_method == "cod",
        is_paid=is_paid,
        techmasters_commission_amount=commission_2pct,
        merchant_payable_amount=merchant_payable,
    )


@router.post(
    "/shipments/{shipment_id}/generate-upi-qr",
    response_model=UpiQrGenerationResponse,
)
async def generate_doorstep_upi_qr(
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
            detail={"code": "SHIPMENT_NOT_ASSIGNED", "message": "This shipment is not assigned to you."},
        )

    stmt = select(Order).where(Order.id == shipment.order_id, Order.tenant_id == principal.tenant_id)
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated order not found.")

    amount_payable = shipment.cod_amount or order.total_amount
    payee_vpa = "bagodi.payments@okaxis"
    payee_name = "Bagodi Luxury Retail"
    txn_ref = f"TXN-UPI-{shipment.shipment_number}-{int(time.time())}"

    # Generate NPCI UPI URI
    upi_uri = generate_upi_uri(
        payee_vpa=payee_vpa,
        payee_name=payee_name,
        amount=amount_payable,
        transaction_ref=txn_ref,
        order_number=order.order_number,
    )
    qr_svg = generate_qr_svg(upi_uri)

    # 2% TechMasters commission calculation
    commission_2pct = Decimal(str(round(float(order.subtotal) * 0.02, 2)))
    merchant_payable = max(Decimal("0.00"), amount_payable - commission_2pct)

    # Find or create PaymentTransaction
    stmt_tx = select(PaymentTransaction).where(
        PaymentTransaction.order_id == order.id,
        PaymentTransaction.payment_method == "upi_delivery",
        PaymentTransaction.status == "pending",
    )
    tx = (await db.execute(stmt_tx)).scalar_one_or_none()
    if not tx:
        tx = PaymentTransaction(
            id=uuid4(),
            tenant_id=principal.tenant_id,
            order_id=order.id,
            transaction_reference=txn_ref,
            payment_method="upi_delivery",
            amount=amount_payable,
            currency="INR",
            status="pending",
            gateway_provider="upi_dynamic",
            gateway_payload={
                "payee_vpa": payee_vpa,
                "payee_name": payee_name,
                "upi_uri": upi_uri,
                "techmasters_commission_2pct": str(commission_2pct),
                "merchant_payable": str(merchant_payable),
            },
        )
        db.add(tx)
    else:
        tx.transaction_reference = txn_ref
        tx.amount = amount_payable
        tx.gateway_payload = {
            "payee_vpa": payee_vpa,
            "payee_name": payee_name,
            "upi_uri": upi_uri,
            "techmasters_commission_2pct": str(commission_2pct),
            "merchant_payable": str(merchant_payable),
        }
    await db.commit()

    return UpiQrGenerationResponse(
        shipment_id=shipment.id,
        order_id=order.id,
        order_number=order.order_number,
        amount_payable=amount_payable,
        payee_vpa=payee_vpa,
        payee_name=payee_name,
        transaction_reference=txn_ref,
        upi_intent_uri=upi_uri,
        qr_code_svg=qr_svg,
        payment_status=order.payment_status,
        techmasters_commission_amount=commission_2pct,
        merchant_payable_amount=merchant_payable,
    )


@router.post(
    "/shipments/{shipment_id}/verify-upi-payment",
    response_model=UpiPaymentVerificationResponse,
)
async def verify_doorstep_upi_payment(
    shipment_id: UUID,
    payload: UpiPaymentVerificationRequest,
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
            detail={"code": "SHIPMENT_NOT_ASSIGNED", "message": "This shipment is not assigned to you."},
        )

    stmt = (
        select(Order)
        .where(Order.id == shipment.order_id, Order.tenant_id == principal.tenant_id)
        .options(selectinload(Order.payments))
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated order not found.")

    # Find pending UPI transaction
    tx = next(
        (t for t in order.payments if t.payment_method == "upi_delivery"),
        None,
    )
    if not tx:
        amount_payable = shipment.cod_amount or order.total_amount
        txn_ref = payload.transaction_reference or f"TXN-UPI-{shipment.shipment_number}-{int(time.time())}"
        tx = PaymentTransaction(
            id=uuid4(),
            tenant_id=principal.tenant_id,
            order_id=order.id,
            transaction_reference=txn_ref,
            payment_method="upi_delivery",
            amount=amount_payable,
            currency="INR",
            status="pending",
            gateway_provider="upi_dynamic",
        )
        order.payments.append(tx)
        db.add(tx)
        await db.flush()

    now = utc_now()
    tx.status = "captured"
    tx.captured_at = now
    order.payment_status = "captured"

    commission_2pct = Decimal(str(round(float(order.subtotal) * 0.02, 2)))
    merchant_payable = max(Decimal("0.00"), tx.amount - commission_2pct)

    tx.gateway_payload = {
        **(tx.gateway_payload or {}),
        "verified_by_rider_id": str(personnel.id),
        "verified_by_rider_name": personnel.full_name,
        "verification_source": "NPCI_FAST_CONFIRMATION",
        "techmasters_commission_2pct": str(commission_2pct),
        "merchant_payable": str(merchant_payable),
        "notes": payload.notes,
    }

    # Add tracking event
    from app.modules.delivery.models import DeliveryTrackingEvent
    tracking = DeliveryTrackingEvent(
        id=uuid4(),
        tenant_id=principal.tenant_id,
        shipment_id=shipment.id,
        status="PAYMENT_CAPTURED",
        description=f"Doorstep UPI payment of ₹{tx.amount:.2f} verified by delivery partner {personnel.full_name}.",
        actor_type="INTERNAL_STAFF",
        actor_id=principal.user_id,
        event_timestamp=now,
        idempotency_key=f"upi_paid_{tx.id}_{int(now.timestamp())}",
    )
    db.add(tracking)

    await db.commit()
    await db.refresh(tx)

    return UpiPaymentVerificationResponse(
        verified=True,
        status="captured",
        transaction_reference=tx.transaction_reference,
        amount=tx.amount,
        captured_at=now,
        payment_method="upi_delivery",
        techmasters_commission_amount=commission_2pct,
        merchant_payable_amount=merchant_payable,
    )


@router.post(
    "/shipments/{shipment_id}/collect-cash",
    response_model=DoorstepCashCollectionResponse,
)
async def collect_doorstep_cash(
    shipment_id: UUID,
    payload: DoorstepCashCollectionRequest,
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
            detail={"code": "SHIPMENT_NOT_ASSIGNED", "message": "This shipment is not assigned to you."},
        )

    stmt = select(Order).where(Order.id == shipment.order_id, Order.tenant_id == principal.tenant_id)
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated order not found.")

    settlement = await PaymentService.record_cod_collection(
        db=db,
        tenant_id=principal.tenant_id,
        order_id=shipment.order_id,
        data=CodCollectionRequest(
            amount_collected=payload.amount_collected,
            collected_by_name=personnel.full_name,
            notes=payload.notes or f"Cash collected at doorstep by rider {personnel.full_name} ({personnel.employee_code})",
        ),
        actor_id=principal.user_id,
    )

    commission_2pct = Decimal(str(round(float(order.subtotal) * 0.02, 2)))
    merchant_payable = max(Decimal("0.00"), payload.amount_collected - commission_2pct)

    return DoorstepCashCollectionResponse(
        collected=True,
        amount=settlement.amount_collected,
        recorded_at=settlement.collected_at,
        settlement_id=settlement.id,
        payment_status="captured",
        techmasters_commission_amount=commission_2pct,
        merchant_payable_amount=merchant_payable,
    )
