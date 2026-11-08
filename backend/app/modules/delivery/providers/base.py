from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CourierBookingRequest(BaseModel):
    shipment_id: UUID
    shipment_number: str
    tenant_id: UUID
    store_id: UUID
    recipient_name: str
    recipient_phone: str
    shipping_address: dict[str, Any]
    total_weight_kg: Decimal = Field(default=Decimal("1.00"), ge=Decimal("0.01"))
    parcel_count: int = Field(default=1, ge=1)
    is_cod: bool = False
    cod_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))


class CourierBookingResult(BaseModel):
    success: bool
    tracking_number: str
    courier_partner: str
    label_url: str | None = None
    estimated_delivery_days: int = 3
    raw_response: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None


class CourierTrackingCheckpoint(BaseModel):
    status: str
    location: str | None = None
    description: str
    timestamp: datetime
    checkpoint_id: str | None = None


class CourierTrackingResult(BaseModel):
    tracking_number: str
    courier_partner: str
    current_status: str
    checkpoints: list[CourierTrackingCheckpoint] = Field(default_factory=list)
    delivered_at: datetime | None = None
    estimated_delivery_date: datetime | None = None
    raw_response: dict[str, Any] = Field(default_factory=dict)


class CourierCancelResult(BaseModel):
    success: bool
    tracking_number: str
    message: str | None = None
    raw_response: dict[str, Any] = Field(default_factory=dict)


class CourierLabelResult(BaseModel):
    tracking_number: str
    label_url: str
    file_format: str = "pdf"


class CourierWebhookPayload(BaseModel):
    tracking_number: str
    status: str  # normalized status
    event_timestamp: datetime
    location: str | None = None
    description: str
    event_id: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class BaseCourierProvider(ABC):
    @abstractmethod
    async def book_shipment(self, request: CourierBookingRequest) -> CourierBookingResult:
        """Create a commercial booking and obtain AWB and shipping label."""

    @abstractmethod
    async def track_shipment(self, tracking_number: str) -> CourierTrackingResult:
        """Fetch latest tracking checkpoints from carrier."""

    @abstractmethod
    async def cancel_shipment(self, tracking_number: str) -> CourierCancelResult:
        """Cancel an existing carrier consignment."""

    @abstractmethod
    async def generate_label(self, tracking_number: str) -> CourierLabelResult:
        """Obtain printable shipping label URL or PDF."""

    @abstractmethod
    def verify_webhook_signature(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        """Cryptographically verify authenticity of carrier webhook payload."""

    @abstractmethod
    def parse_webhook_payload(
        self, raw_body: bytes, headers: dict[str, str]
    ) -> CourierWebhookPayload:
        """Normalize carrier-specific webhook payload into platform schema."""
