from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# -----------------------------------------------------------------------------
# Serviceability Schemas
# -----------------------------------------------------------------------------
class ServiceabilityCheckRequest(BaseModel):
    pincode: str = Field(..., min_length=3, max_length=10)
    order_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    total_weight_kg: Decimal = Field(default=Decimal("1.00"), gt=Decimal("0.00"))
    store_id: UUID | None = None
    tenant_id: UUID | None = None


class ServiceabilityCheckResponse(BaseModel):
    serviceable: bool
    pincode: str
    zone_code: str | None = None
    zone_name: str | None = None
    supports_internal_delivery: bool = False
    supports_courier: bool = False
    supports_cod: bool = False
    delivery_fee: Decimal = Decimal("0.00")
    free_delivery_threshold: Decimal | None = None
    estimated_delivery_hours: int = 24
    reason: str | None = None


# -----------------------------------------------------------------------------
# Delivery Zone Schemas
# -----------------------------------------------------------------------------
class DeliveryZoneCreate(BaseModel):
    store_id: UUID | None = None
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=150)
    description: str | None = None
    is_active: bool = True
    supports_internal_delivery: bool = True
    supports_courier: bool = True
    supports_cod: bool = True
    base_delivery_fee: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    free_delivery_threshold: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    estimated_delivery_hours: int = Field(default=24, ge=1)
    metadata_json: dict[str, Any] | None = None


class DeliveryZoneUpdate(BaseModel):
    store_id: UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    is_active: bool | None = None
    supports_internal_delivery: bool | None = None
    supports_courier: bool | None = None
    supports_cod: bool | None = None
    base_delivery_fee: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    free_delivery_threshold: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    estimated_delivery_hours: int | None = Field(default=None, ge=1)
    metadata_json: dict[str, Any] | None = None


class DeliveryZoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    store_id: UUID | None
    code: str
    name: str
    description: str | None
    is_active: bool
    supports_internal_delivery: bool
    supports_courier: bool
    supports_cod: bool
    base_delivery_fee: Decimal
    free_delivery_threshold: Decimal | None
    estimated_delivery_hours: int
    metadata_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class DeliveryZonePincodesAddRequest(BaseModel):
    pincodes: list[str] = Field(..., min_length=1)
    is_serviceable: bool = True
    delivery_charge_override: Decimal | None = Field(default=None, ge=Decimal("0.00"))


class DeliveryZonePincodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    zone_id: UUID
    pincode: str
    is_serviceable: bool
    delivery_charge_override: Decimal | None
    created_at: datetime


# -----------------------------------------------------------------------------
# Delivery Vehicle Schemas
# -----------------------------------------------------------------------------
class DeliveryVehicleCreate(BaseModel):
    store_id: UUID | None = None
    vehicle_type: str = Field(..., min_length=2, max_length=30)
    registration_number: str = Field(..., min_length=2, max_length=50)
    brand_model: str | None = Field(default=None, max_length=100)
    max_weight_capacity_kg: Decimal = Field(default=Decimal("20.00"), gt=Decimal("0.00"))
    max_volume_capacity_m3: Decimal | None = Field(default=None, gt=Decimal("0.00"))
    status: str = "AVAILABLE"
    is_active: bool = True


class DeliveryVehicleUpdate(BaseModel):
    store_id: UUID | None = None
    vehicle_type: str | None = Field(default=None, min_length=2, max_length=30)
    registration_number: str | None = Field(default=None, min_length=2, max_length=50)
    brand_model: str | None = Field(default=None, max_length=100)
    max_weight_capacity_kg: Decimal | None = Field(default=None, gt=Decimal("0.00"))
    max_volume_capacity_m3: Decimal | None = Field(default=None, gt=Decimal("0.00"))
    status: str | None = None
    is_active: bool | None = None


class DeliveryVehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    store_id: UUID | None
    vehicle_type: str
    registration_number: str
    brand_model: str | None
    max_weight_capacity_kg: Decimal
    max_volume_capacity_m3: Decimal | None
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# -----------------------------------------------------------------------------
# Delivery Personnel Schemas
# -----------------------------------------------------------------------------
class DeliveryPersonnelCreate(BaseModel):
    user_id: UUID
    store_id: UUID | None = None
    employee_code: str = Field(..., min_length=2, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=150)
    phone_number: str = Field(..., min_length=5, max_length=50)
    driving_license_number: str | None = Field(default=None, max_length=50)
    assigned_vehicle_id: UUID | None = None
    verification_status: str = "PENDING"
    duty_status: str = "OFFLINE"
    is_active: bool = True


class DeliveryPersonnelUpdate(BaseModel):
    store_id: UUID | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone_number: str | None = Field(default=None, min_length=5, max_length=50)
    driving_license_number: str | None = Field(default=None, max_length=50)
    assigned_vehicle_id: UUID | None = None
    verification_status: str | None = None
    duty_status: str | None = None
    is_active: bool | None = None


class DutyStatusUpdateRequest(BaseModel):
    duty_status: str = Field(..., pattern="^(AVAILABLE|ON_DELIVERY|OFFLINE)$")
    current_latitude: Decimal | None = None
    current_longitude: Decimal | None = None


class DeliveryPersonnelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    store_id: UUID | None
    user_id: UUID
    employee_code: str
    full_name: str
    phone_number: str
    driving_license_number: str | None
    verification_status: str
    duty_status: str
    is_active: bool
    assigned_vehicle_id: UUID | None
    current_latitude: Decimal | None
    current_longitude: Decimal | None
    last_active_at: datetime | None
    created_at: datetime
    updated_at: datetime


# -----------------------------------------------------------------------------
# Shipment & Tracking Schemas
# -----------------------------------------------------------------------------
class ShipmentCreateFromOrderRequest(BaseModel):
    order_id: UUID
    delivery_type: str = Field(default="INTERNAL", pattern="^(INTERNAL|COURIER)$")
    total_weight_kg: Decimal = Field(default=Decimal("1.00"), gt=Decimal("0.00"))
    parcel_count: int = Field(default=1, ge=1)
    notes: str | None = None


class ShipmentAssignInternalRequest(BaseModel):
    personnel_id: UUID
    vehicle_id: UUID | None = None
    notes: str | None = None


class ShipmentBookCourierRequest(BaseModel):
    courier_provider: str = "mock"
    notes: str | None = None


class ShipmentItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    shipment_id: UUID
    order_item_id: UUID
    variant_id: UUID
    sku: str
    product_name: str
    quantity: int
    created_at: datetime


class ShipmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    store_id: UUID
    order_id: UUID
    shipment_number: str
    delivery_type: str
    status: str
    assigned_personnel_id: UUID | None
    assigned_vehicle_id: UUID | None
    assigned_at: datetime | None
    courier_provider: str | None
    courier_awb: str | None
    courier_label_url: str | None
    total_weight_kg: Decimal
    parcel_count: int
    is_cod: bool
    cod_amount: Decimal
    max_delivery_attempts: int
    attempt_count: int
    last_attempt_at: datetime | None
    last_attempt_reason: str | None
    next_attempt_date: datetime | None
    dispatched_at: datetime | None
    delivered_at: datetime | None
    recipient_name: str
    recipient_phone: str
    shipping_address: dict[str, Any]
    notes: str | None
    created_at: datetime
    updated_at: datetime
    items: list[ShipmentItemResponse] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Proof of Delivery & Completion Schemas
# -----------------------------------------------------------------------------
class ProofOfDeliveryRequest(BaseModel):
    recipient_name: str = Field(..., min_length=2, max_length=150)
    recipient_phone: str = Field(..., min_length=5, max_length=50)
    relationship_to_customer: str = Field(default="SELF", max_length=30)
    delivery_otp: str | None = Field(default=None, max_length=10)
    signature_url: str | None = None
    photo_url: str | None = None
    notes: str | None = None
    collected_cod_amount: Decimal | None = Field(default=None, ge=Decimal("0.00"))


class ProofOfDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    shipment_id: UUID
    recipient_name: str
    recipient_phone: str
    relationship_to_customer: str
    delivered_at: datetime
    delivery_otp_verified: bool
    signature_url: str | None
    photo_url: str | None
    notes: str | None
    verified_by_actor_id: UUID | None
    created_at: datetime


class FailedDeliveryAttemptRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=150)
    next_attempt_date: datetime | None = None
    notes: str | None = None


class RtoRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=150)
    notes: str | None = None


# -----------------------------------------------------------------------------
# Tracking Event Schemas
# -----------------------------------------------------------------------------
class DeliveryTrackingEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    shipment_id: UUID
    status: str
    location: str | None
    description: str
    actor_type: str
    actor_id: UUID | None
    event_timestamp: datetime
    idempotency_key: str | None
    metadata_json: dict[str, Any] | None
    created_at: datetime


class ShipmentTrackingHistoryResponse(BaseModel):
    shipment_id: UUID
    shipment_number: str
    order_id: UUID
    status: str
    delivery_type: str
    courier_provider: str | None
    courier_awb: str | None
    courier_label_url: str | None
    delivered_at: datetime | None
    tracking_events: list[DeliveryTrackingEventResponse] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Dashboard & Audit Schemas
# -----------------------------------------------------------------------------
class DeliveryDashboardMetricsResponse(BaseModel):
    total_shipments: int = 0
    pending_assignment_count: int = 0
    assigned_count: int = 0
    picked_up_count: int = 0
    in_transit_count: int = 0
    out_for_delivery_count: int = 0
    delivered_count: int = 0
    failed_attempt_count: int = 0
    returned_to_store_count: int = 0
    cancelled_count: int = 0
    active_riders_count: int = 0
    available_riders_count: int = 0


class DeliveryAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    shipment_id: UUID | None
    actor_id: UUID | None
    action: str
    from_status: str | None
    to_status: str | None
    payload: dict[str, Any]
    created_at: datetime

