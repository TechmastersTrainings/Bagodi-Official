from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.modules.catalog.models import ProductVariant
    from app.modules.identity.models import User
    from app.modules.orders.models import Order, OrderItem
    from app.modules.platform.models import Store, Tenant


class DeliveryZone(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "delivery_zones"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_delivery_zones_tenant_code"),)

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supports_internal_delivery: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supports_courier: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supports_cod: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    base_delivery_fee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    free_delivery_threshold: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    estimated_delivery_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    store: Mapped["Store | None"] = relationship("Store")
    pincodes: Mapped[list["DeliveryZonePincode"]] = relationship(
        "DeliveryZonePincode", cascade="all, delete-orphan", back_populates="zone"
    )


class DeliveryZonePincode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "delivery_zone_pincodes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "pincode", name="uq_delivery_zone_pincodes_tenant_pin"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    zone_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("delivery_zones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pincode: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    is_serviceable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    delivery_charge_override: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    zone: Mapped["DeliveryZone"] = relationship("DeliveryZone", back_populates="pincodes")


class DeliveryVehicle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "delivery_vehicles"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "registration_number", name="uq_delivery_vehicles_tenant_reg"
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    vehicle_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # BICYCLE, MOTORCYCLE, SCOOTER, VAN, TRUCK
    registration_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    brand_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    max_weight_capacity_kg: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), default=Decimal("20.00"), nullable=False
    )
    max_volume_capacity_m3: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="AVAILABLE", nullable=False
    )  # AVAILABLE, IN_USE, MAINTENANCE, INACTIVE
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    store: Mapped["Store | None"] = relationship("Store")


class DeliveryPersonnel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "delivery_personnel"
    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_code", name="uq_delivery_personnel_tenant_code"),
        UniqueConstraint("tenant_id", "user_id", name="uq_delivery_personnel_tenant_user"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)
    driving_license_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(30), default="PENDING", nullable=False
    )  # PENDING, VERIFIED, REJECTED
    duty_status: Mapped[str] = mapped_column(
        String(30), default="OFFLINE", nullable=False
    )  # AVAILABLE, ON_DELIVERY, OFFLINE
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    assigned_vehicle_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("delivery_vehicles.id", ondelete="SET NULL"),
        nullable=True,
    )
    current_latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    current_longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    store: Mapped["Store | None"] = relationship("Store")
    user: Mapped["User"] = relationship("User")
    vehicle: Mapped["DeliveryVehicle | None"] = relationship("DeliveryVehicle")


class Shipment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shipments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "shipment_number", name="uq_shipments_tenant_number"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    shipment_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    delivery_type: Mapped[str] = mapped_column(
        String(20), default="INTERNAL", nullable=False
    )  # INTERNAL, COURIER
    status: Mapped[str] = mapped_column(
        String(30), default="PENDING_ASSIGNMENT", nullable=False, index=True
    )  # PENDING_ASSIGNMENT, ASSIGNED, PICKED_UP, IN_TRANSIT, OUT_FOR_DELIVERY, DELIVERED, FAILED_ATTEMPT, RETURNED_TO_STORE, CANCELLED
    assigned_personnel_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("delivery_personnel.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_vehicle_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("delivery_vehicles.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    courier_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    courier_awb: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    courier_label_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_weight_kg: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), default=Decimal("1.00"), nullable=False
    )
    parcel_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_cod: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cod_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    delivery_otp: Mapped[str | None] = mapped_column(String(128), nullable=True)
    delivery_otp_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivery_otp_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_delivery_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_reason: Mapped[str | None] = mapped_column(String(150), nullable=True)
    next_attempt_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recipient_name: Mapped[str] = mapped_column(String(150), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    shipping_address: Mapped[dict] = mapped_column(JSONB, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    store: Mapped["Store"] = relationship("Store")
    order: Mapped["Order"] = relationship("Order")
    assigned_personnel: Mapped["DeliveryPersonnel | None"] = relationship("DeliveryPersonnel")
    assigned_vehicle: Mapped["DeliveryVehicle | None"] = relationship("DeliveryVehicle")
    items: Mapped[list["ShipmentItem"]] = relationship(
        "ShipmentItem", cascade="all, delete-orphan", back_populates="shipment"
    )
    tracking_events: Mapped[list["DeliveryTrackingEvent"]] = relationship(
        "DeliveryTrackingEvent",
        cascade="all, delete-orphan",
        back_populates="shipment",
        order_by="DeliveryTrackingEvent.event_timestamp.asc()",
    )
    proof_of_delivery: Mapped["ProofOfDelivery | None"] = relationship(
        "ProofOfDelivery", back_populates="shipment", uselist=False, cascade="all, delete-orphan"
    )


class ShipmentItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shipment_items"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    shipment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(String(80), nullable=False)
    product_name: Mapped[str] = mapped_column(String(250), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="items")
    order_item: Mapped["OrderItem"] = relationship("OrderItem")
    variant: Mapped["ProductVariant"] = relationship("ProductVariant")


class DeliveryTrackingEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "delivery_tracking_events"
    __table_args__ = (
        UniqueConstraint("shipment_id", "idempotency_key", name="uq_tracking_shipment_idempotency"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    shipment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # INTERNAL_STAFF, MERCHANT_ADMIN, COURIER_WEBHOOK, SYSTEM
    actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    tenant: Mapped["Tenant"] = relationship("Tenant")
    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="tracking_events")


class ProofOfDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "proof_of_deliveries"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    shipment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    recipient_name: Mapped[str] = mapped_column(String(150), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    relationship_to_customer: Mapped[str] = mapped_column(
        String(30), default="SELF", nullable=False
    )
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivery_otp_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    signature_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="proof_of_delivery")


class DeliveryAuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "delivery_audit_logs"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    shipment_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    tenant: Mapped["Tenant"] = relationship("Tenant")
    shipment: Mapped["Shipment | None"] = relationship("Shipment")
