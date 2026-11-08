import hashlib
import hmac
import json
import time
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.core.config import get_settings
from app.modules.payments.providers.base import (
    BasePaymentGatewayProvider,
    PaymentInitiationResult,
    PaymentVerificationResult,
    RefundResult,
    WebhookProcessingResult,
)


class MockPaymentGatewayProvider(BasePaymentGatewayProvider):
    """
    Cryptographically secure mock gateway provider for testing and development.
    Uses HMAC-SHA256 signatures, timestamp validation, and configurable secrets.
    """

    def __init__(
        self,
        secret_key: str | None = None,
        webhook_secret: str | None = None,
        timestamp_tolerance_seconds: int | None = None,
    ):
        settings = get_settings()
        self.secret_key = secret_key or settings.payment_mock_secret
        self.webhook_secret = webhook_secret or settings.payment_webhook_secret
        self.timestamp_tolerance_seconds = (
            timestamp_tolerance_seconds
            if timestamp_tolerance_seconds is not None
            else settings.payment_webhook_timestamp_tolerance_seconds
        )

    @property
    def provider_name(self) -> str:
        return "mock"

    def generate_payment_signature(
        self, gateway_order_id: str, gateway_payment_id: str, amount: Decimal
    ) -> str:
        """Utility method to compute expected HMAC-SHA256 signature for client verification."""
        msg = f"{gateway_order_id}|{gateway_payment_id}|{amount!s}"
        return hmac.new(
            self.secret_key.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def generate_webhook_header(self, raw_body: bytes, timestamp: int | None = None) -> str:
        """Utility method to generate valid X-Webhook-Signature header for testing."""
        ts = timestamp if timestamp is not None else int(time.time())
        msg = f"{ts}.{raw_body.decode('utf-8')}"
        sig = hmac.new(
            self.webhook_secret.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"t={ts},v1={sig}"

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
        gateway_order_id = f"order_mock_{uuid4().hex[:14]}"
        checkout_payload = {
            "key": "mock_publishable_key",
            "gateway_order_id": gateway_order_id,
            "order_number": order_number,
            "amount": str(amount),
            "currency": currency,
            "customer": customer_info or {},
            "callback_url": return_url,
            "simulation": {
                "hint": "Sign with gateway_order_id|gateway_payment_id|amount",
            },
        }
        return PaymentInitiationResult(
            gateway_order_id=gateway_order_id,
            gateway_payment_id=None,
            status="initiated",
            checkout_url=f"https://checkout.bagodi.test/pay/{gateway_order_id}",
            checkout_payload=checkout_payload,
        )

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
        expected_sig = self.generate_payment_signature(gateway_order_id, gateway_payment_id, amount)
        if not hmac.compare_digest(expected_sig, gateway_signature):
            return PaymentVerificationResult(
                is_valid=False,
                gateway_payment_id=gateway_payment_id,
                gateway_signature=gateway_signature,
                status="failed",
                error_message="Invalid payment cryptographic signature",
            )

        fee = (amount * Decimal("0.02")).quantize(Decimal("0.01"))
        tax = (fee * Decimal("0.18")).quantize(Decimal("0.01"))

        return PaymentVerificationResult(
            is_valid=True,
            gateway_payment_id=gateway_payment_id,
            gateway_signature=gateway_signature,
            status="captured",
            fee=fee,
            tax=tax,
            raw_response={
                "gateway": "mock",
                "verified": True,
                "gateway_order_id": gateway_order_id,
                "gateway_payment_id": gateway_payment_id,
            },
        )

    async def verify_webhook_signature(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> bool:
        sig_header = (
            headers.get("x-webhook-signature")
            or headers.get("X-Webhook-Signature")
            or headers.get("x-signature")
            or headers.get("X-Signature")
        )
        if not sig_header:
            return False

        # Support format: t=123456789,v1=abcdef...
        ts_part = None
        sig_part = None

        if "t=" in sig_header and "v1=" in sig_header:
            parts = sig_header.split(",")
            for p in parts:
                p = p.strip()
                if p.startswith("t="):
                    ts_part = p[2:]
                elif p.startswith("v1="):
                    sig_part = p[3:]
        else:
            # Fallback simple signature without timestamp
            sig_part = sig_header

        if ts_part is not None:
            try:
                timestamp = int(ts_part)
                current_time = int(time.time())
                if abs(current_time - timestamp) > self.timestamp_tolerance_seconds:
                    return False
                msg = f"{timestamp}.{raw_body.decode('utf-8')}"
            except (ValueError, UnicodeDecodeError):
                return False
        else:
            msg = raw_body.decode("utf-8")

        expected_sig = hmac.new(
            self.webhook_secret.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected_sig, sig_part)

    async def process_webhook(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> WebhookProcessingResult:
        is_valid = await self.verify_webhook_signature(raw_body=raw_body, headers=headers)
        if not is_valid:
            return WebhookProcessingResult(
                is_valid=False,
                event_id="unknown",
                event_type="unknown",
                status="failed",
                error_message="Invalid webhook signature or expired timestamp",
            )

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return WebhookProcessingResult(
                is_valid=False,
                event_id="unknown",
                event_type="unknown",
                status="failed",
                error_message=f"Malformed webhook JSON: {e!s}",
            )

        event_id = payload.get("event_id") or payload.get("id") or f"evt_{uuid4().hex[:12]}"
        event_type = payload.get("event") or payload.get("event_type", "payment.captured")
        data = payload.get("payload", {}).get("payment", {}) or payload.get("data", {}) or payload

        gateway_order_id = data.get("gateway_order_id") or data.get("order_id")
        gateway_payment_id = data.get("gateway_payment_id") or data.get("payment_id")
        status = data.get("status", "captured")

        amount_val = data.get("amount", "0.00")
        try:
            amount = Decimal(str(amount_val))
        except (ValueError, TypeError):
            amount = Decimal("0.00")

        fee = (amount * Decimal("0.02")).quantize(Decimal("0.01"))
        tax = (fee * Decimal("0.18")).quantize(Decimal("0.01"))

        return WebhookProcessingResult(
            is_valid=True,
            event_id=str(event_id),
            event_type=str(event_type),
            gateway_order_id=gateway_order_id,
            gateway_payment_id=gateway_payment_id,
            status=status,
            fee=fee,
            tax=tax,
            amount=amount,
            raw_payload=payload,
        )

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
        gateway_refund_id = f"rfnd_mock_{uuid4().hex[:14]}"
        return RefundResult(
            is_valid=True,
            gateway_refund_id=gateway_refund_id,
            status="succeeded",
            fee=Decimal("0.00"),
            tax=Decimal("0.00"),
            raw_response={
                "gateway": "mock",
                "refund_reference": refund_reference,
                "gateway_refund_id": gateway_refund_id,
                "amount": str(amount),
                "currency": currency,
                "reason": reason,
                "status": "succeeded",
            },
        )
