from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass
class PaymentInitiationResult:
    gateway_order_id: str
    gateway_payment_id: str | None = None
    status: str = "initiated"  # initiated, pending
    checkout_url: str | None = None
    checkout_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class PaymentVerificationResult:
    is_valid: bool
    gateway_payment_id: str
    gateway_signature: str | None = None
    status: str = "captured"  # captured, failed
    fee: Decimal = Decimal("0.00")
    tax: Decimal = Decimal("0.00")
    error_message: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookProcessingResult:
    is_valid: bool
    event_id: str
    event_type: str  # payment.captured, payment.failed, refund.processed
    gateway_order_id: str | None = None
    gateway_payment_id: str | None = None
    status: str = "captured"  # captured, failed, refunded
    fee: Decimal = Decimal("0.00")
    tax: Decimal = Decimal("0.00")
    amount: Decimal = Decimal("0.00")
    error_message: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class RefundResult:
    is_valid: bool
    gateway_refund_id: str
    status: str = "succeeded"  # succeeded, pending, failed
    fee: Decimal = Decimal("0.00")
    tax: Decimal = Decimal("0.00")
    error_message: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


class BasePaymentGatewayProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier string (e.g. 'mock', 'razorpay', 'cod')."""

    @abstractmethod
    async def initiate_payment(
        self,
        *,
        tenant_id: UUID,
        transaction_id: UUID,
        order_number: str,
        amount: Decimal,
        currency: str = "INR",
        customer_info: dict[str, Any] | None = None,
        return_url: str | None = None,
    ) -> PaymentInitiationResult:
        """Create or initiate payment session with the gateway."""

    @abstractmethod
    async def verify_payment(
        self,
        *,
        tenant_id: UUID,
        gateway_order_id: str,
        gateway_payment_id: str,
        gateway_signature: str,
        amount: Decimal,
        currency: str = "INR",
    ) -> PaymentVerificationResult:
        """Verify payment cryptographic authenticity and capture status."""

    @abstractmethod
    async def verify_webhook_signature(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> bool:
        """Verify gateway webhook cryptographic signature and timestamp freshness."""

    @abstractmethod
    async def process_webhook(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> WebhookProcessingResult:
        """Parse, authenticate and unpack webhook payload."""

    @abstractmethod
    async def process_refund(
        self,
        *,
        tenant_id: UUID,
        payment_transaction_id: UUID,
        gateway_payment_id: str | None,
        refund_reference: str,
        amount: Decimal,
        currency: str = "INR",
        reason: str,
    ) -> RefundResult:
        """Process refund with external gateway."""
