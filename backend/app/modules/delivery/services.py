import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import utc_now
from app.modules.delivery.models import (
    DeliveryAuditLog,
    DeliveryPersonnel,
    DeliveryTrackingEvent,
    DeliveryVehicle,
    DeliveryZone,
    DeliveryZonePincode,
    ProofOfDelivery,
    Shipment,
    ShipmentItem,
)
from app.modules.delivery.providers.base import CourierBookingRequest
from app.modules.delivery.providers.factory import CourierProviderFactory
from app.modules.delivery.schemas import (
    DeliveryPersonnelCreate,
    DeliveryPersonnelUpdate,
    DeliveryVehicleCreate,
    DeliveryVehicleUpdate,
    DeliveryZoneCreate,
    DeliveryZonePincodesAddRequest,
    DeliveryZoneUpdate,
    DutyStatusUpdateRequest,
    FailedDeliveryAttemptRequest,
    ProofOfDeliveryRequest,
    RtoRequest,
    ServiceabilityCheckResponse,
    ShipmentAssignInternalRequest,
    ShipmentBookCourierRequest,
    ShipmentCreateFromOrderRequest,
)
from app.modules.identity.models import User
from app.modules.notifications.services import NotificationService
from app.modules.orders.models import Order
from app.modules.orders.schemas import OrderStatusUpdateRequest
from app.modules.orders.services import OrderService
from app.modules.payments.schemas import CodCollectionRequest
from app.modules.payments.services import PaymentService


class DeliveryService:
    # -------------------------------------------------------------------------
    # Audit Logging
    # -------------------------------------------------------------------------
    @staticmethod
    async def log_audit_event(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        action: str,
        shipment_id: UUID | None = None,
        actor_id: UUID | None = None,
        from_status: str | None = None,
        to_status: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> DeliveryAuditLog:
        audit = DeliveryAuditLog(
            id=uuid4(),
            tenant_id=tenant_id,
            shipment_id=shipment_id,
            actor_id=actor_id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            payload=payload or {},
            created_at=utc_now(),
        )
        db.add(audit)
        await db.flush()
        return audit

    # -------------------------------------------------------------------------
    # Delivery Zones & Serviceability
    # -------------------------------------------------------------------------
    @staticmethod
    async def create_delivery_zone(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        data: DeliveryZoneCreate,
        actor_id: UUID | None = None,
    ) -> DeliveryZone:
        # Check unique code within tenant
        stmt = select(DeliveryZone).where(
            DeliveryZone.tenant_id == tenant_id,
            func.lower(DeliveryZone.code) == data.code.strip().lower(),
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "DUPLICATE_ZONE_CODE",
                    "message": f"Zone code '{data.code}' already exists.",
                },
            )

        zone = DeliveryZone(
            id=uuid4(),
            tenant_id=tenant_id,
            store_id=data.store_id,
            code=data.code.strip().upper(),
            name=data.name.strip(),
            description=data.description,
            is_active=data.is_active,
            supports_internal_delivery=data.supports_internal_delivery,
            supports_courier=data.supports_courier,
            supports_cod=data.supports_cod,
            base_delivery_fee=data.base_delivery_fee,
            free_delivery_threshold=data.free_delivery_threshold,
            estimated_delivery_hours=data.estimated_delivery_hours,
            metadata_json=data.metadata_json,
        )
        db.add(zone)
        await db.flush()
        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            action="CREATE_ZONE",
            actor_id=actor_id,
            payload={"code": zone.code},
        )
        await db.commit()
        await db.refresh(zone)
        return zone

    @staticmethod
    async def update_delivery_zone(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        zone_id: UUID,
        data: DeliveryZoneUpdate,
        actor_id: UUID | None = None,
    ) -> DeliveryZone:
        stmt = select(DeliveryZone).where(
            DeliveryZone.tenant_id == tenant_id, DeliveryZone.id == zone_id
        )
        zone = (await db.execute(stmt)).scalar_one_or_none()
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ZONE_NOT_FOUND", "message": "Delivery zone not found."},
            )

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(zone, key, value)

        await db.flush()
        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            action="UPDATE_ZONE",
            actor_id=actor_id,
            payload={"zone_id": str(zone_id)},
        )
        await db.commit()
        await db.refresh(zone)
        return zone

    @staticmethod
    async def list_delivery_zones(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        store_id: UUID | None = None,
    ) -> list[DeliveryZone]:
        stmt = (
            select(DeliveryZone)
            .where(DeliveryZone.tenant_id == tenant_id)
            .options(selectinload(DeliveryZone.pincodes))
        )
        if store_id:
            stmt = stmt.where(
                (DeliveryZone.store_id == store_id) | (DeliveryZone.store_id.is_(None))
            )
        stmt = stmt.order_by(DeliveryZone.created_at.desc())
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def add_pincodes_to_zone(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        zone_id: UUID,
        data: DeliveryZonePincodesAddRequest,
        actor_id: UUID | None = None,
    ) -> list[DeliveryZonePincode]:
        stmt = select(DeliveryZone).where(
            DeliveryZone.tenant_id == tenant_id, DeliveryZone.id == zone_id
        )
        zone = (await db.execute(stmt)).scalar_one_or_none()
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ZONE_NOT_FOUND", "message": "Delivery zone not found."},
            )

        added: list[DeliveryZonePincode] = []
        for raw_pin in data.pincodes:
            pin = raw_pin.strip()
            if not pin:
                continue
            # Check if pincode already mapped in tenant
            stmt_pin = select(DeliveryZonePincode).where(
                DeliveryZonePincode.tenant_id == tenant_id,
                DeliveryZonePincode.pincode == pin,
            )
            existing = (await db.execute(stmt_pin)).scalar_one_or_none()
            if existing:
                existing.zone_id = zone_id
                existing.is_serviceable = data.is_serviceable
                existing.delivery_charge_override = data.delivery_charge_override
                added.append(existing)
            else:
                new_pin = DeliveryZonePincode(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    zone_id=zone_id,
                    pincode=pin,
                    is_serviceable=data.is_serviceable,
                    delivery_charge_override=data.delivery_charge_override,
                )
                db.add(new_pin)
                added.append(new_pin)

        await db.flush()
        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            action="ADD_PINCODES_TO_ZONE",
            actor_id=actor_id,
            payload={"zone_id": str(zone_id), "pincodes": data.pincodes},
        )
        await db.commit()
        return added

    @staticmethod
    async def check_serviceability(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        pincode: str,
        order_amount: Decimal = Decimal("0.00"),
        total_weight_kg: Decimal = Decimal("1.00"),
        store_id: UUID | None = None,
    ) -> ServiceabilityCheckResponse:
        clean_pin = pincode.strip()
        stmt = (
            select(DeliveryZonePincode)
            .join(DeliveryZone, DeliveryZonePincode.zone_id == DeliveryZone.id)
            .where(
                DeliveryZonePincode.tenant_id == tenant_id,
                DeliveryZonePincode.pincode == clean_pin,
            )
            .options(selectinload(DeliveryZonePincode.zone))
        )
        if store_id:
            stmt = stmt.where(
                (DeliveryZone.store_id == store_id) | (DeliveryZone.store_id.is_(None))
            )

        pin_record = (await db.execute(stmt)).scalar_one_or_none()
        if not pin_record or not pin_record.is_serviceable:
            return ServiceabilityCheckResponse(
                serviceable=False,
                pincode=clean_pin,
                reason="PIN code is not serviceable for this merchant.",
            )

        zone = pin_record.zone
        if not zone.is_active:
            return ServiceabilityCheckResponse(
                serviceable=False,
                pincode=clean_pin,
                reason="Delivery zone is currently inactive.",
            )

        # Delivery fee calculation
        delivery_fee = zone.base_delivery_fee
        if pin_record.delivery_charge_override is not None:
            delivery_fee = pin_record.delivery_charge_override

        if (
            zone.free_delivery_threshold is not None
            and order_amount >= zone.free_delivery_threshold
        ):
            delivery_fee = Decimal("0.00")

        return ServiceabilityCheckResponse(
            serviceable=True,
            pincode=clean_pin,
            zone_code=zone.code,
            zone_name=zone.name,
            supports_internal_delivery=zone.supports_internal_delivery,
            supports_courier=zone.supports_courier,
            supports_cod=zone.supports_cod,
            delivery_fee=delivery_fee,
            free_delivery_threshold=zone.free_delivery_threshold,
            estimated_delivery_hours=zone.estimated_delivery_hours,
        )

    # -------------------------------------------------------------------------
    # Delivery Vehicles
    # -------------------------------------------------------------------------
    @staticmethod
    async def create_vehicle(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        data: DeliveryVehicleCreate,
        actor_id: UUID | None = None,
    ) -> DeliveryVehicle:
        reg = data.registration_number.strip().upper()
        stmt = select(DeliveryVehicle).where(
            DeliveryVehicle.tenant_id == tenant_id,
            DeliveryVehicle.registration_number == reg,
        )
        if (await db.execute(stmt)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "DUPLICATE_REGISTRATION",
                    "message": f"Vehicle with registration '{reg}' already exists.",
                },
            )

        vehicle = DeliveryVehicle(
            id=uuid4(),
            tenant_id=tenant_id,
            store_id=data.store_id,
            vehicle_type=data.vehicle_type.strip().upper(),
            registration_number=reg,
            brand_model=data.brand_model,
            max_weight_capacity_kg=data.max_weight_capacity_kg,
            max_volume_capacity_m3=data.max_volume_capacity_m3,
            status=data.status.upper(),
            is_active=data.is_active,
        )
        db.add(vehicle)
        await db.flush()
        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            action="CREATE_VEHICLE",
            actor_id=actor_id,
            payload={"reg": reg},
        )
        await db.commit()
        await db.refresh(vehicle)
        return vehicle

    @staticmethod
    async def update_vehicle(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        vehicle_id: UUID,
        data: DeliveryVehicleUpdate,
        actor_id: UUID | None = None,
    ) -> DeliveryVehicle:
        stmt = select(DeliveryVehicle).where(
            DeliveryVehicle.tenant_id == tenant_id, DeliveryVehicle.id == vehicle_id
        )
        vehicle = (await db.execute(stmt)).scalar_one_or_none()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "VEHICLE_NOT_FOUND", "message": "Delivery vehicle not found."},
            )

        update_data = data.model_dump(exclude_unset=True)
        for key, val in update_data.items():
            if (
                key == "registration_number"
                and val
                or key == "vehicle_type"
                and val
                or key == "status"
                and val
            ):
                val = val.strip().upper()
            setattr(vehicle, key, val)

        await db.flush()
        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            action="UPDATE_VEHICLE",
            actor_id=actor_id,
            payload={"vehicle_id": str(vehicle_id)},
        )
        await db.commit()
        await db.refresh(vehicle)
        return vehicle

    @staticmethod
    async def list_vehicles(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        store_id: UUID | None = None,
    ) -> list[DeliveryVehicle]:
        stmt = select(DeliveryVehicle).where(DeliveryVehicle.tenant_id == tenant_id)
        if store_id:
            stmt = stmt.where(
                (DeliveryVehicle.store_id == store_id) | (DeliveryVehicle.store_id.is_(None))
            )
        stmt = stmt.order_by(DeliveryVehicle.created_at.desc())
        return list((await db.execute(stmt)).scalars().all())

    # -------------------------------------------------------------------------
    # Delivery Personnel
    # -------------------------------------------------------------------------
    @staticmethod
    async def create_personnel(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        data: DeliveryPersonnelCreate,
        actor_id: UUID | None = None,
    ) -> DeliveryPersonnel:
        emp_code = data.employee_code.strip().upper()
        # Verify employee code unique
        stmt = select(DeliveryPersonnel).where(
            DeliveryPersonnel.tenant_id == tenant_id,
            DeliveryPersonnel.employee_code == emp_code,
        )
        if (await db.execute(stmt)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "DUPLICATE_EMPLOYEE_CODE",
                    "message": f"Personnel code '{emp_code}' already exists.",
                },
            )

        # Verify user exists and unique per tenant
        stmt_user = select(DeliveryPersonnel).where(
            DeliveryPersonnel.tenant_id == tenant_id,
            DeliveryPersonnel.user_id == data.user_id,
        )
        if (await db.execute(stmt_user)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "USER_ALREADY_ASSIGNED",
                    "message": "User is already registered as delivery personnel.",
                },
            )

        user_exists = (
            await db.execute(select(User).where(User.id == data.user_id))
        ).scalar_one_or_none()
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "USER_NOT_FOUND",
                    "message": "Linked identity user does not exist.",
                },
            )

        personnel = DeliveryPersonnel(
            id=uuid4(),
            tenant_id=tenant_id,
            store_id=data.store_id,
            user_id=data.user_id,
            employee_code=emp_code,
            full_name=data.full_name.strip(),
            phone_number=data.phone_number.strip(),
            driving_license_number=data.driving_license_number,
            assigned_vehicle_id=data.assigned_vehicle_id,
            verification_status=data.verification_status.upper(),
            duty_status=data.duty_status.upper(),
            is_active=data.is_active,
        )
        db.add(personnel)
        await db.flush()
        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            action="CREATE_PERSONNEL",
            actor_id=actor_id,
            payload={"emp_code": emp_code},
        )
        await db.commit()
        await db.refresh(personnel)
        return personnel

    @staticmethod
    async def update_personnel(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        personnel_id: UUID,
        data: DeliveryPersonnelUpdate,
        actor_id: UUID | None = None,
    ) -> DeliveryPersonnel:
        stmt = select(DeliveryPersonnel).where(
            DeliveryPersonnel.tenant_id == tenant_id, DeliveryPersonnel.id == personnel_id
        )
        personnel = (await db.execute(stmt)).scalar_one_or_none()
        if not personnel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PERSONNEL_NOT_FOUND", "message": "Delivery personnel not found."},
            )

        update_data = data.model_dump(exclude_unset=True)
        for key, val in update_data.items():
            if key in ("verification_status", "duty_status") and val:
                val = val.strip().upper()
            setattr(personnel, key, val)

        await db.flush()
        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            action="UPDATE_PERSONNEL",
            actor_id=actor_id,
            payload={"personnel_id": str(personnel_id)},
        )
        await db.commit()
        await db.refresh(personnel)
        return personnel

    @staticmethod
    async def update_duty_status(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        user_id: UUID,
        data: DutyStatusUpdateRequest,
    ) -> DeliveryPersonnel:
        stmt = select(DeliveryPersonnel).where(
            DeliveryPersonnel.tenant_id == tenant_id,
            DeliveryPersonnel.user_id == user_id,
        )
        personnel = (await db.execute(stmt)).scalar_one_or_none()
        if not personnel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PERSONNEL_NOT_FOUND",
                    "message": "Delivery profile not found for this user.",
                },
            )

        personnel.duty_status = data.duty_status.upper()
        if data.current_latitude is not None:
            personnel.current_latitude = data.current_latitude
        if data.current_longitude is not None:
            personnel.current_longitude = data.current_longitude
        personnel.last_active_at = utc_now()

        await db.flush()
        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            action="UPDATE_DUTY_STATUS",
            actor_id=user_id,
            payload={"duty_status": personnel.duty_status},
        )
        await db.commit()
        await db.refresh(personnel)
        return personnel

    @staticmethod
    async def list_personnel(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        store_id: UUID | None = None,
    ) -> list[DeliveryPersonnel]:
        stmt = select(DeliveryPersonnel).where(DeliveryPersonnel.tenant_id == tenant_id)
        if store_id:
            stmt = stmt.where(
                (DeliveryPersonnel.store_id == store_id) | (DeliveryPersonnel.store_id.is_(None))
            )
        stmt = stmt.order_by(DeliveryPersonnel.created_at.desc())
        return list((await db.execute(stmt)).scalars().all())

    # -------------------------------------------------------------------------
    # Shipment Creation & Operations
    # -------------------------------------------------------------------------
    @staticmethod
    async def create_shipment_from_order(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        data: ShipmentCreateFromOrderRequest,
        actor_id: UUID | None = None,
    ) -> Shipment:
        stmt_order = (
            select(Order)
            .where(Order.tenant_id == tenant_id, Order.id == data.order_id)
            .options(selectinload(Order.items))
        )
        order = (await db.execute(stmt_order)).scalar_one_or_none()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ORDER_NOT_FOUND", "message": "Order not found."},
            )

        if order.status not in ("CONFIRMED", "PROCESSING"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_ORDER_STATUS",
                    "message": f"Order status '{order.status}' is not eligible for shipment creation.",
                },
            )

        # Check if shipment already created for this order
        stmt_existing = select(Shipment).where(
            Shipment.tenant_id == tenant_id,
            Shipment.order_id == data.order_id,
            Shipment.status != "CANCELLED",
        )
        if (await db.execute(stmt_existing)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "SHIPMENT_ALREADY_EXISTS",
                    "message": "An active shipment already exists for this order.",
                },
            )

        shipment_num = f"SHP-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"
        is_cod = order.payment_method == "cod" and order.payment_status != "captured"
        cod_amount = order.total_amount if is_cod else Decimal("0.00")

        shipment = Shipment(
            id=uuid4(),
            tenant_id=tenant_id,
            store_id=order.store_id,
            order_id=order.id,
            shipment_number=shipment_num,
            delivery_type=data.delivery_type.upper(),
            status="PENDING_ASSIGNMENT",
            total_weight_kg=data.total_weight_kg,
            parcel_count=data.parcel_count,
            is_cod=is_cod,
            cod_amount=cod_amount,
            recipient_name=order.customer_name,
            recipient_phone=order.customer_phone,
            shipping_address=order.shipping_address,
            notes=data.notes,
        )
        db.add(shipment)
        await db.flush()

        # Add shipment items mirroring order items
        for item in order.items:
            shipment_item = ShipmentItem(
                id=uuid4(),
                tenant_id=tenant_id,
                shipment_id=shipment.id,
                order_item_id=item.id,
                variant_id=item.variant_id,
                sku=item.sku,
                product_name=item.product_name,
                quantity=item.quantity,
            )
            db.add(shipment_item)

        # Add initial tracking event
        now = utc_now()
        tracking_event = DeliveryTrackingEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            status="PENDING_ASSIGNMENT",
            description=f"Shipment {shipment_num} created and awaiting assignment.",
            actor_type="MERCHANT_ADMIN" if actor_id else "SYSTEM",
            actor_id=actor_id,
            event_timestamp=now,
            idempotency_key=f"created_{shipment.id}",
        )
        db.add(tracking_event)
        await db.flush()

        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            action="CREATE_SHIPMENT",
            actor_id=actor_id,
            to_status="PENDING_ASSIGNMENT",
            payload={"shipment_number": shipment_num, "order_id": str(order.id)},
        )

        # Enqueue transactional outbox event
        await NotificationService.enqueue_outbox_event(
            db,
            tenant_id=tenant_id,
            event_type="shipment.created",
            aggregate_type="shipment",
            aggregate_id=str(shipment.id),
            payload={
                "shipment_number": shipment_num,
                "order_number": order.order_number,
                "recipient_name": shipment.recipient_name,
                "recipient_phone": shipment.recipient_phone,
            },
            idempotency_key=f"outbox_shipment_created_{shipment.id}",
        )
        await db.commit()

        return await DeliveryService.get_shipment_by_id(
            db, tenant_id=tenant_id, shipment_id=shipment.id
        )

    @staticmethod
    async def get_shipment_by_id(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        shipment_id: UUID,
    ) -> Shipment:
        stmt = (
            select(Shipment)
            .where(Shipment.tenant_id == tenant_id, Shipment.id == shipment_id)
            .options(
                selectinload(Shipment.items),
                selectinload(Shipment.tracking_events),
                selectinload(Shipment.proof_of_delivery),
            )
        )
        shipment = (await db.execute(stmt)).scalar_one_or_none()
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "SHIPMENT_NOT_FOUND", "message": "Shipment not found."},
            )
        return shipment

    @staticmethod
    async def list_shipments(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        store_id: UUID | None = None,
        status_filter: str | None = None,
        personnel_id: UUID | None = None,
    ) -> list[Shipment]:
        stmt = (
            select(Shipment)
            .where(Shipment.tenant_id == tenant_id)
            .options(
                selectinload(Shipment.items),
                selectinload(Shipment.tracking_events),
            )
        )
        if store_id:
            stmt = stmt.where(Shipment.store_id == store_id)
        if status_filter:
            stmt = stmt.where(Shipment.status == status_filter.upper())
        if personnel_id:
            stmt = stmt.where(Shipment.assigned_personnel_id == personnel_id)

        stmt = stmt.order_by(Shipment.created_at.desc())
        return list((await db.execute(stmt)).scalars().all())

    # -------------------------------------------------------------------------
    # Internal Staff & Courier Assignment
    # -------------------------------------------------------------------------
    @staticmethod
    async def assign_internal_delivery(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        shipment_id: UUID,
        data: ShipmentAssignInternalRequest,
        actor_id: UUID | None = None,
    ) -> Shipment:
        shipment = await DeliveryService.get_shipment_by_id(
            db, tenant_id=tenant_id, shipment_id=shipment_id
        )
        if shipment.status not in ("PENDING_ASSIGNMENT", "ASSIGNED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_SHIPMENT_STATUS",
                    "message": f"Cannot assign internal delivery for shipment in status '{shipment.status}'.",
                },
            )

        # Validate personnel
        stmt_p = select(DeliveryPersonnel).where(
            DeliveryPersonnel.tenant_id == tenant_id,
            DeliveryPersonnel.id == data.personnel_id,
        )
        personnel = (await db.execute(stmt_p)).scalar_one_or_none()
        if not personnel or not personnel.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PERSONNEL_NOT_FOUND",
                    "message": "Active delivery personnel not found.",
                },
            )

        if personnel.verification_status != "VERIFIED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "PERSONNEL_NOT_VERIFIED",
                    "message": "Delivery personnel is not verified.",
                },
            )

        if personnel.duty_status == "OFFLINE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "PERSONNEL_OFFLINE",
                    "message": "Delivery personnel is currently offline.",
                },
            )

        # Vehicle capacity validation
        vehicle_id = data.vehicle_id or personnel.assigned_vehicle_id
        if vehicle_id:
            stmt_v = select(DeliveryVehicle).where(
                DeliveryVehicle.tenant_id == tenant_id,
                DeliveryVehicle.id == vehicle_id,
            )
            vehicle = (await db.execute(stmt_v)).scalar_one_or_none()
            if (
                not vehicle
                or not vehicle.is_active
                or vehicle.status in ("MAINTENANCE", "INACTIVE")
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "VEHICLE_NOT_AVAILABLE",
                        "message": "Selected vehicle is not available.",
                    },
                )
            if shipment.total_weight_kg > vehicle.max_weight_capacity_kg:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "VEHICLE_CAPACITY_EXCEEDED",
                        "message": (
                            f"Shipment weight ({shipment.total_weight_kg} kg) exceeds vehicle max capacity "
                            f"({vehicle.max_weight_capacity_kg} kg)."
                        ),
                    },
                )
            shipment.assigned_vehicle_id = vehicle.id
            vehicle.status = "IN_USE"

        from_status = shipment.status
        shipment.assigned_personnel_id = personnel.id
        shipment.assigned_at = utc_now()
        shipment.delivery_type = "INTERNAL"
        shipment.status = "ASSIGNED"
        personnel.duty_status = "ON_DELIVERY"

        now = utc_now()
        tracking = DeliveryTrackingEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            status="ASSIGNED",
            description=f"Assigned to delivery executive {personnel.full_name} ({personnel.employee_code}).",
            actor_type="MERCHANT_ADMIN" if actor_id else "SYSTEM",
            actor_id=actor_id,
            event_timestamp=now,
            idempotency_key=f"assigned_{shipment.id}_{now.timestamp()}",
        )
        db.add(tracking)
        await db.flush()

        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            action="ASSIGN_INTERNAL_DELIVERY",
            from_status=from_status,
            to_status="ASSIGNED",
            actor_id=actor_id,
            payload={"personnel_id": str(personnel.id), "personnel_name": personnel.full_name},
        )

        await NotificationService.enqueue_outbox_event(
            db,
            tenant_id=tenant_id,
            event_type="shipment.assigned",
            aggregate_type="shipment",
            aggregate_id=str(shipment.id),
            payload={
                "shipment_number": shipment.shipment_number,
                "delivery_executive": personnel.full_name,
                "executive_phone": personnel.phone_number,
            },
            idempotency_key=f"outbox_shipment_assigned_{shipment.id}",
        )
        await db.commit()

        return await DeliveryService.get_shipment_by_id(
            db, tenant_id=tenant_id, shipment_id=shipment.id
        )

    @staticmethod
    async def book_courier_shipment(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        shipment_id: UUID,
        data: ShipmentBookCourierRequest,
        actor_id: UUID | None = None,
    ) -> Shipment:
        shipment = await DeliveryService.get_shipment_by_id(
            db, tenant_id=tenant_id, shipment_id=shipment_id
        )
        if shipment.status not in ("PENDING_ASSIGNMENT", "ASSIGNED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_SHIPMENT_STATUS",
                    "message": f"Cannot book courier for shipment in status '{shipment.status}'.",
                },
            )

        provider = CourierProviderFactory.get_provider(data.courier_provider)
        booking_req = CourierBookingRequest(
            shipment_id=shipment.id,
            shipment_number=shipment.shipment_number,
            tenant_id=tenant_id,
            store_id=shipment.store_id,
            recipient_name=shipment.recipient_name,
            recipient_phone=shipment.recipient_phone,
            shipping_address=shipment.shipping_address,
            total_weight_kg=shipment.total_weight_kg,
            parcel_count=shipment.parcel_count,
            is_cod=shipment.is_cod,
            cod_amount=shipment.cod_amount,
        )

        booking_res = await provider.book_shipment(booking_req)
        if not booking_res.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "COURIER_BOOKING_FAILED",
                    "message": booking_res.error_message or "Third-party courier booking failed.",
                },
            )

        from_status = shipment.status
        shipment.delivery_type = "COURIER"
        shipment.courier_provider = data.courier_provider
        shipment.courier_awb = booking_res.tracking_number
        shipment.courier_label_url = booking_res.label_url
        shipment.assigned_at = utc_now()
        shipment.status = "ASSIGNED"

        now = utc_now()
        tracking = DeliveryTrackingEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            status="ASSIGNED",
            description=f"Consignment booked with carrier {booking_res.courier_partner}. AWB: {booking_res.tracking_number}",
            actor_type="MERCHANT_ADMIN" if actor_id else "SYSTEM",
            actor_id=actor_id,
            event_timestamp=now,
            idempotency_key=f"courier_booked_{shipment.id}",
        )
        db.add(tracking)
        await db.flush()

        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            action="BOOK_COURIER",
            from_status=from_status,
            to_status="ASSIGNED",
            actor_id=actor_id,
            payload={"provider": data.courier_provider, "awb": booking_res.tracking_number},
        )

        await NotificationService.enqueue_outbox_event(
            db,
            tenant_id=tenant_id,
            event_type="shipment.assigned",
            aggregate_type="shipment",
            aggregate_id=str(shipment.id),
            payload={
                "shipment_number": shipment.shipment_number,
                "courier_partner": booking_res.courier_partner,
                "awb": booking_res.tracking_number,
            },
            idempotency_key=f"outbox_shipment_courier_{shipment.id}",
        )
        await db.commit()

        return await DeliveryService.get_shipment_by_id(
            db, tenant_id=tenant_id, shipment_id=shipment.id
        )

    # -------------------------------------------------------------------------
    # Pickup, Transit & Out for Delivery
    # -------------------------------------------------------------------------
    @staticmethod
    async def pickup_shipment(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        shipment_id: UUID,
        actor_id: UUID | None = None,
    ) -> Shipment:
        shipment = await DeliveryService.get_shipment_by_id(
            db, tenant_id=tenant_id, shipment_id=shipment_id
        )
        if shipment.status != "ASSIGNED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_SHIPMENT_STATUS",
                    "message": f"Cannot pickup shipment from status '{shipment.status}'.",
                },
            )

        from_status = shipment.status
        now = utc_now()
        shipment.status = "PICKED_UP"
        shipment.dispatched_at = now

        # Synchronize Order & Phase 4 Inventory Ledger
        order = await OrderService.get_order_by_id(
            db, tenant_id=tenant_id, order_id=shipment.order_id
        )
        if order.status == "CONFIRMED":
            # Progress CONFIRMED -> PROCESSING -> DISPATCHED
            await OrderService.update_order_status(
                db=db,
                tenant_id=tenant_id,
                order_id=order.id,
                data=OrderStatusUpdateRequest(
                    status="PROCESSING", notes="Fulfillment processing initiated"
                ),
                user_id=actor_id,
            )
        if order.status in ("CONFIRMED", "PROCESSING"):
            await OrderService.update_order_status(
                db=db,
                tenant_id=tenant_id,
                order_id=order.id,
                data=OrderStatusUpdateRequest(
                    status="DISPATCHED", notes="Order dispatched from store via delivery fleet"
                ),
                user_id=actor_id,
            )

        tracking = DeliveryTrackingEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            status="PICKED_UP",
            description="Shipment picked up from merchant store and dispatched.",
            actor_type="INTERNAL_STAFF" if actor_id else "SYSTEM",
            actor_id=actor_id,
            event_timestamp=now,
            idempotency_key=f"picked_up_{shipment.id}",
        )
        db.add(tracking)
        await db.flush()

        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            action="PICKUP_SHIPMENT",
            from_status=from_status,
            to_status="PICKED_UP",
            actor_id=actor_id,
        )
        await db.commit()
        return await DeliveryService.get_shipment_by_id(
            db, tenant_id=tenant_id, shipment_id=shipment.id
        )

    @staticmethod
    async def mark_out_for_delivery(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        shipment_id: UUID,
        actor_id: UUID | None = None,
    ) -> Shipment:
        shipment = await DeliveryService.get_shipment_by_id(
            db, tenant_id=tenant_id, shipment_id=shipment_id
        )
        if shipment.status not in ("PICKED_UP", "IN_TRANSIT", "FAILED_ATTEMPT"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_SHIPMENT_STATUS",
                    "message": f"Cannot transition to OUT_FOR_DELIVERY from status '{shipment.status}'.",
                },
            )

        from_status = shipment.status
        now = utc_now()
        # Generate secure 6-digit delivery OTP
        delivery_otp = str(secrets.randbelow(900000) + 100000)
        shipment.delivery_otp = delivery_otp
        shipment.delivery_otp_expires_at = now + timedelta(hours=24)
        shipment.delivery_otp_attempts = 0
        shipment.status = "OUT_FOR_DELIVERY"

        tracking = DeliveryTrackingEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            status="OUT_FOR_DELIVERY",
            description="Package is out for delivery with our delivery executive.",
            actor_type="INTERNAL_STAFF" if actor_id else "SYSTEM",
            actor_id=actor_id,
            event_timestamp=now,
            idempotency_key=f"out_for_delivery_{shipment.id}_{now.timestamp()}",
        )
        db.add(tracking)
        await db.flush()

        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            action="MARK_OUT_FOR_DELIVERY",
            from_status=from_status,
            to_status="OUT_FOR_DELIVERY",
            actor_id=actor_id,
        )

        # Enqueue customer notification outbox with OTP
        await NotificationService.enqueue_outbox_event(
            db,
            tenant_id=tenant_id,
            event_type="shipment.out_for_delivery",
            aggregate_type="shipment",
            aggregate_id=str(shipment.id),
            payload={
                "shipment_number": shipment.shipment_number,
                "delivery_otp": delivery_otp,
                "recipient_name": shipment.recipient_name,
                "recipient_phone": shipment.recipient_phone,
            },
            idempotency_key=f"outbox_shipment_ofd_{shipment.id}_{now.timestamp()}",
        )
        await db.commit()

        return await DeliveryService.get_shipment_by_id(
            db, tenant_id=tenant_id, shipment_id=shipment.id
        )

    # -------------------------------------------------------------------------
    # Delivery Completion & Proof of Delivery (POD)
    # -------------------------------------------------------------------------
    @staticmethod
    async def complete_delivery(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        shipment_id: UUID,
        data: ProofOfDeliveryRequest,
        actor_id: UUID | None = None,
    ) -> ProofOfDelivery:
        shipment = await DeliveryService.get_shipment_by_id(
            db, tenant_id=tenant_id, shipment_id=shipment_id
        )
        if shipment.status != "OUT_FOR_DELIVERY":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_SHIPMENT_STATUS",
                    "message": f"Cannot complete delivery for shipment in status '{shipment.status}'. Must be OUT_FOR_DELIVERY.",
                },
            )

        # OTP Validation
        if shipment.delivery_otp:
            if shipment.delivery_otp_attempts >= 5:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "OTP_ATTEMPTS_EXCEEDED",
                        "message": "Too many invalid OTP attempts. Verification locked.",
                    },
                )
            if not data.delivery_otp or data.delivery_otp.strip() != shipment.delivery_otp:
                shipment.delivery_otp_attempts += 1
                await db.flush()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "INVALID_DELIVERY_OTP",
                        "message": "Invalid delivery verification OTP provided.",
                    },
                )

        now = utc_now()
        # Create Proof of Delivery
        pod = ProofOfDelivery(
            id=uuid4(),
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            recipient_name=data.recipient_name.strip(),
            recipient_phone=data.recipient_phone.strip(),
            relationship_to_customer=data.relationship_to_customer.strip().upper(),
            delivered_at=now,
            delivery_otp_verified=bool(shipment.delivery_otp),
            signature_url=data.signature_url,
            photo_url=data.photo_url,
            notes=data.notes,
            verified_by_actor_id=actor_id,
        )
        db.add(pod)

        # Cash on Delivery Collection Integration
        if shipment.is_cod:
            collector_name = "Delivery Staff"
            if shipment.assigned_personnel:
                collector_name = shipment.assigned_personnel.full_name
            await PaymentService.record_cod_collection(
                db=db,
                tenant_id=tenant_id,
                order_id=shipment.order_id,
                data=CodCollectionRequest(
                    amount_collected=shipment.cod_amount,
                    collected_by_name=collector_name,
                    notes=f"COD collected upon successful delivery of shipment {shipment.shipment_number}",
                ),
                actor_id=actor_id,
            )

        # Update Order Status to DELIVERED
        await OrderService.update_order_status(
            db=db,
            tenant_id=tenant_id,
            order_id=shipment.order_id,
            data=OrderStatusUpdateRequest(
                status="DELIVERED",
                notes=f"Order marked DELIVERED upon doorstep handover (Shipment {shipment.shipment_number})",
            ),
            user_id=actor_id,
        )

        from_status = shipment.status
        shipment.status = "DELIVERED"
        shipment.delivered_at = now

        # Free delivery personnel and vehicle if no other pending shipments
        if shipment.assigned_personnel:
            # Check if personnel has any other active out_for_delivery shipments
            stmt_other = select(func.count(Shipment.id)).where(
                Shipment.tenant_id == tenant_id,
                Shipment.assigned_personnel_id == shipment.assigned_personnel_id,
                Shipment.status == "OUT_FOR_DELIVERY",
                Shipment.id != shipment.id,
            )
            other_active = (await db.execute(stmt_other)).scalar_one()
            if other_active == 0:
                shipment.assigned_personnel.duty_status = "AVAILABLE"

        if shipment.assigned_vehicle:
            shipment.assigned_vehicle.status = "AVAILABLE"

        tracking = DeliveryTrackingEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            status="DELIVERED",
            description=f"Package delivered to {pod.recipient_name} ({pod.relationship_to_customer}).",
            actor_type="INTERNAL_STAFF" if actor_id else "SYSTEM",
            actor_id=actor_id,
            event_timestamp=now,
            idempotency_key=f"delivered_{shipment.id}",
        )
        db.add(tracking)
        await db.flush()

        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            action="COMPLETE_DELIVERY",
            from_status=from_status,
            to_status="DELIVERED",
            actor_id=actor_id,
            payload={"recipient": pod.recipient_name, "relationship": pod.relationship_to_customer},
        )

        await NotificationService.enqueue_outbox_event(
            db,
            tenant_id=tenant_id,
            event_type="shipment.delivered",
            aggregate_type="shipment",
            aggregate_id=str(shipment.id),
            payload={
                "shipment_number": shipment.shipment_number,
                "recipient_name": pod.recipient_name,
                "delivered_at": now.isoformat(),
            },
            idempotency_key=f"outbox_shipment_deliv_{shipment.id}",
        )
        await db.commit()
        await db.refresh(pod)

        return pod

    # -------------------------------------------------------------------------
    # Failed Delivery & Return to Origin (RTO)
    # -------------------------------------------------------------------------
    @staticmethod
    async def record_failed_attempt(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        shipment_id: UUID,
        data: FailedDeliveryAttemptRequest,
        actor_id: UUID | None = None,
    ) -> Shipment:
        shipment = await DeliveryService.get_shipment_by_id(
            db, tenant_id=tenant_id, shipment_id=shipment_id
        )
        if shipment.status not in ("OUT_FOR_DELIVERY", "IN_TRANSIT"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_SHIPMENT_STATUS",
                    "message": f"Cannot record failed attempt from status '{shipment.status}'.",
                },
            )

        now = utc_now()
        shipment.attempt_count += 1
        shipment.last_attempt_at = now
        shipment.last_attempt_reason = data.reason
        shipment.next_attempt_date = data.next_attempt_date

        from_status = shipment.status
        is_terminal_failure = (
            shipment.attempt_count >= shipment.max_delivery_attempts
            or data.reason.strip().upper() == "CUSTOMER_REJECTED"
        )

        if is_terminal_failure:
            return await DeliveryService.process_rto(
                db,
                tenant_id=tenant_id,
                shipment_id=shipment_id,
                data=RtoRequest(
                    reason=f"Exceeded max delivery attempts ({shipment.attempt_count}) - {data.reason}",
                    notes=data.notes,
                ),
                actor_id=actor_id,
            )

        shipment.status = "FAILED_ATTEMPT"
        tracking = DeliveryTrackingEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            status="FAILED_ATTEMPT",
            description=f"Delivery attempt #{shipment.attempt_count} failed: {data.reason}",
            actor_type="INTERNAL_STAFF" if actor_id else "SYSTEM",
            actor_id=actor_id,
            event_timestamp=now,
            idempotency_key=f"failed_attempt_{shipment.id}_{shipment.attempt_count}",
        )
        db.add(tracking)
        await db.flush()

        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            action="FAILED_DELIVERY_ATTEMPT",
            from_status=from_status,
            to_status="FAILED_ATTEMPT",
            actor_id=actor_id,
            payload={"attempt": shipment.attempt_count, "reason": data.reason},
        )

        await NotificationService.enqueue_outbox_event(
            db,
            tenant_id=tenant_id,
            event_type="shipment.failed_attempt",
            aggregate_type="shipment",
            aggregate_id=str(shipment.id),
            payload={
                "shipment_number": shipment.shipment_number,
                "attempt_count": shipment.attempt_count,
                "reason": data.reason,
                "next_attempt_date": data.next_attempt_date.isoformat()
                if data.next_attempt_date
                else None,
            },
            idempotency_key=f"outbox_shipment_fail_{shipment.id}_{shipment.attempt_count}",
        )
        await db.commit()

        return await DeliveryService.get_shipment_by_id(
            db, tenant_id=tenant_id, shipment_id=shipment.id
        )

    @staticmethod
    async def process_rto(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        shipment_id: UUID,
        data: RtoRequest,
        actor_id: UUID | None = None,
    ) -> Shipment:
        shipment = await DeliveryService.get_shipment_by_id(
            db, tenant_id=tenant_id, shipment_id=shipment_id
        )
        if shipment.status in ("DELIVERED", "RETURNED_TO_STORE", "CANCELLED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_SHIPMENT_STATUS",
                    "message": f"Shipment is already in terminal status '{shipment.status}'.",
                },
            )

        from_status = shipment.status
        now = utc_now()
        shipment.status = "RETURNED_TO_STORE"

        # Inventory Reconciliation with Phase 4 Inventory Ledger
        order = await OrderService.get_order_by_id(
            db, tenant_id=tenant_id, order_id=shipment.order_id
        )
        if order.status == "DISPATCHED":
            # Items were physically dispatched from store stock; restock them via Order status update to RETURNED
            await OrderService.update_order_status(
                db=db,
                tenant_id=tenant_id,
                order_id=order.id,
                data=OrderStatusUpdateRequest(
                    status="RETURNED",
                    notes=f"RTO Restocked into store inventory: {data.reason}",
                ),
                user_id=actor_id,
            )

        # Free delivery staff and vehicle
        if shipment.assigned_personnel:
            shipment.assigned_personnel.duty_status = "AVAILABLE"
        if shipment.assigned_vehicle:
            shipment.assigned_vehicle.status = "AVAILABLE"

        tracking = DeliveryTrackingEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            status="RETURNED_TO_STORE",
            description=f"Shipment returned to merchant store (RTO). Reason: {data.reason}",
            actor_type="INTERNAL_STAFF" if actor_id else "SYSTEM",
            actor_id=actor_id,
            event_timestamp=now,
            idempotency_key=f"rto_{shipment.id}_{now.timestamp()}",
        )
        db.add(tracking)
        await db.flush()

        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            action="PROCESS_RTO",
            from_status=from_status,
            to_status="RETURNED_TO_STORE",
            actor_id=actor_id,
            payload={"reason": data.reason},
        )

        await NotificationService.enqueue_outbox_event(
            db,
            tenant_id=tenant_id,
            event_type="shipment.rto",
            aggregate_type="shipment",
            aggregate_id=str(shipment.id),
            payload={"shipment_number": shipment.shipment_number, "reason": data.reason},
            idempotency_key=f"outbox_shipment_rto_{shipment.id}",
        )
        await db.commit()

        return await DeliveryService.get_shipment_by_id(
            db, tenant_id=tenant_id, shipment_id=shipment.id
        )

    @staticmethod
    async def cancel_shipment(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        shipment_id: UUID,
        reason: str | None = None,
        actor_id: UUID | None = None,
    ) -> Shipment:
        shipment = await DeliveryService.get_shipment_by_id(
            db, tenant_id=tenant_id, shipment_id=shipment_id
        )
        if shipment.status not in ("PENDING_ASSIGNMENT", "ASSIGNED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_SHIPMENT_STATUS",
                    "message": f"Cannot cancel shipment in status '{shipment.status}'.",
                },
            )

        if shipment.delivery_type == "COURIER" and shipment.courier_awb:
            provider = CourierProviderFactory.get_provider(shipment.courier_provider)
            await provider.cancel_shipment(shipment.courier_awb)

        from_status = shipment.status
        now = utc_now()
        shipment.status = "CANCELLED"

        if shipment.assigned_personnel:
            shipment.assigned_personnel.duty_status = "AVAILABLE"
        if shipment.assigned_vehicle:
            shipment.assigned_vehicle.status = "AVAILABLE"

        tracking = DeliveryTrackingEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            status="CANCELLED",
            description=f"Shipment cancelled. {reason or ''}".strip(),
            actor_type="MERCHANT_ADMIN" if actor_id else "SYSTEM",
            actor_id=actor_id,
            event_timestamp=now,
            idempotency_key=f"cancelled_{shipment.id}",
        )
        db.add(tracking)
        await db.flush()

        await DeliveryService.log_audit_event(
            db,
            tenant_id=tenant_id,
            shipment_id=shipment.id,
            action="CANCEL_SHIPMENT",
            from_status=from_status,
            to_status="CANCELLED",
            actor_id=actor_id,
            payload={"reason": reason},
        )
        await db.commit()

        return await DeliveryService.get_shipment_by_id(
            db, tenant_id=tenant_id, shipment_id=shipment.id
        )

    # -------------------------------------------------------------------------
    # Courier Webhook Ingestion & Tracking Sync
    # -------------------------------------------------------------------------
    @staticmethod
    async def process_courier_webhook(
        db: AsyncSession,
        *,
        provider_name: str,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        provider = CourierProviderFactory.get_provider(provider_name)
        if not provider.verify_webhook_signature(raw_body, headers):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_WEBHOOK_SIGNATURE",
                    "message": "Courier webhook signature verification failed.",
                },
            )

        payload = provider.parse_webhook_payload(raw_body, headers)
        if not payload.tracking_number:
            return {"status": "ignored", "reason": "MISSING_AWB"}

        # Find shipment by AWB
        stmt = select(Shipment).where(Shipment.courier_awb == payload.tracking_number)
        shipment = (await db.execute(stmt)).scalar_one_or_none()
        if not shipment:
            return {"status": "ignored", "reason": "UNKNOWN_AWB"}

        # Idempotency check on event_id
        if payload.event_id:
            stmt_evt = select(DeliveryTrackingEvent).where(
                DeliveryTrackingEvent.shipment_id == shipment.id,
                DeliveryTrackingEvent.idempotency_key == payload.event_id,
            )
            if (await db.execute(stmt_evt)).scalar_one_or_none():
                return {"status": "idempotent_duplicate", "event_id": payload.event_id}

        # Terminal state protection
        TERMINAL_STATES = ("DELIVERED", "RETURNED_TO_STORE", "CANCELLED")
        from_status = shipment.status
        target_status = payload.status

        # Add tracking checkpoint event
        event = DeliveryTrackingEvent(
            id=uuid4(),
            tenant_id=shipment.tenant_id,
            shipment_id=shipment.id,
            status=target_status,
            location=payload.location,
            description=payload.description,
            actor_type="COURIER_WEBHOOK",
            actor_id=None,
            event_timestamp=payload.event_timestamp,
            idempotency_key=payload.event_id,
            metadata_json=payload.raw_payload,
        )
        db.add(event)

        # Update shipment status if not already terminal and not an out-of-order regression
        if from_status not in TERMINAL_STATES and target_status in (
            "PICKED_UP",
            "IN_TRANSIT",
            "OUT_FOR_DELIVERY",
            "DELIVERED",
            "FAILED_ATTEMPT",
            "RETURNED_TO_STORE",
        ):
            # Advance status
            shipment.status = target_status
            if target_status == "DELIVERED":
                shipment.delivered_at = payload.event_timestamp
                # Also create POD record if delivered
                pod = ProofOfDelivery(
                    id=uuid4(),
                    tenant_id=shipment.tenant_id,
                    shipment_id=shipment.id,
                    recipient_name=shipment.recipient_name,
                    recipient_phone=shipment.recipient_phone,
                    relationship_to_customer="SELF",
                    delivered_at=payload.event_timestamp,
                    delivery_otp_verified=False,
                    notes="Delivered via carrier webhook confirmation",
                )
                db.add(pod)
                # Update order to DELIVERED
                await OrderService.update_order_status(
                    db=db,
                    tenant_id=shipment.tenant_id,
                    order_id=shipment.order_id,
                    data=OrderStatusUpdateRequest(
                        status="DELIVERED",
                        notes=f"Carrier confirmed delivery (AWB: {shipment.courier_awb})",
                    ),
                )
            elif target_status == "RETURNED_TO_STORE":
                await OrderService.update_order_status(
                    db=db,
                    tenant_id=shipment.tenant_id,
                    order_id=shipment.order_id,
                    data=OrderStatusUpdateRequest(
                        status="RETURNED",
                        notes=f"Carrier confirmed RTO (AWB: {shipment.courier_awb})",
                    ),
                )

        await db.flush()
        await DeliveryService.log_audit_event(
            db,
            tenant_id=shipment.tenant_id,
            shipment_id=shipment.id,
            action="COURIER_WEBHOOK_UPDATE",
            from_status=from_status,
            to_status=shipment.status,
            payload={"event_id": payload.event_id, "status": target_status},
        )
        await db.commit()

        return {
            "status": "processed",
            "shipment_id": str(shipment.id),
            "new_status": shipment.status,
        }

    # -------------------------------------------------------------------------
    # Customer Tracking & Operational Dashboard
    # -------------------------------------------------------------------------
    @staticmethod
    async def get_shipment_tracking_for_customer(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        customer_id: UUID,
        shipment_id: UUID,
    ) -> Shipment:
        stmt = (
            select(Shipment)
            .join(Order, Shipment.order_id == Order.id)
            .where(
                Shipment.tenant_id == tenant_id,
                Shipment.id == shipment_id,
                Order.customer_id == customer_id,
            )
            .options(
                selectinload(Shipment.tracking_events),
                selectinload(Shipment.items),
                selectinload(Shipment.assigned_personnel),
                selectinload(Shipment.assigned_vehicle),
                selectinload(Shipment.store),
                selectinload(Shipment.order),
            )
        )
        shipment = (await db.execute(stmt)).scalar_one_or_none()
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "SHIPMENT_NOT_FOUND",
                    "message": "Shipment not found or access denied.",
                },
            )
        return shipment

    @staticmethod
    async def get_shipment_by_order_id_for_customer(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        customer_id: UUID,
        order_id: UUID,
    ) -> Shipment:
        stmt = (
            select(Shipment)
            .join(Order, Shipment.order_id == Order.id)
            .where(
                Shipment.tenant_id == tenant_id,
                Shipment.order_id == order_id,
                Order.customer_id == customer_id,
            )
            .options(
                selectinload(Shipment.tracking_events),
                selectinload(Shipment.items),
                selectinload(Shipment.assigned_personnel),
                selectinload(Shipment.assigned_vehicle),
                selectinload(Shipment.store),
                selectinload(Shipment.order),
            )
        )
        shipment = (await db.execute(stmt)).scalar_one_or_none()
        if not shipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "SHIPMENT_NOT_FOUND",
                    "message": "Shipment not found for this order.",
                },
            )
        return shipment

    @staticmethod
    async def get_merchant_dashboard_metrics(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        store_id: UUID | None = None,
    ) -> dict[str, int]:
        stmt = select(Shipment.status, func.count(Shipment.id)).where(
            Shipment.tenant_id == tenant_id
        )
        if store_id:
            stmt = stmt.where(Shipment.store_id == store_id)
        stmt = stmt.group_by(Shipment.status)
        rows = (await db.execute(stmt)).all()
        counts = {r[0]: r[1] for r in rows}

        # Personnel counts
        stmt_riders = select(DeliveryPersonnel.duty_status, func.count(DeliveryPersonnel.id)).where(
            DeliveryPersonnel.tenant_id == tenant_id,
            DeliveryPersonnel.is_active.is_(True),
        )
        if store_id:
            stmt_riders = stmt_riders.where(
                (DeliveryPersonnel.store_id == store_id) | (DeliveryPersonnel.store_id.is_(None))
            )
        stmt_riders = stmt_riders.group_by(DeliveryPersonnel.duty_status)
        rider_rows = (await db.execute(stmt_riders)).all()
        rider_counts = {r[0]: r[1] for r in rider_rows}

        total_shipments = sum(counts.values())
        return {
            "total_shipments": total_shipments,
            "pending_assignment_count": counts.get("PENDING_ASSIGNMENT", 0),
            "assigned_count": counts.get("ASSIGNED", 0),
            "picked_up_count": counts.get("PICKED_UP", 0),
            "in_transit_count": counts.get("IN_TRANSIT", 0),
            "out_for_delivery_count": counts.get("OUT_FOR_DELIVERY", 0),
            "delivered_count": counts.get("DELIVERED", 0),
            "failed_attempt_count": counts.get("FAILED_ATTEMPT", 0),
            "returned_to_store_count": counts.get("RETURNED_TO_STORE", 0),
            "cancelled_count": counts.get("CANCELLED", 0),
            "active_riders_count": rider_counts.get("ON_DELIVERY", 0)
            + rider_counts.get("AVAILABLE", 0),
            "available_riders_count": rider_counts.get("AVAILABLE", 0),
        }
