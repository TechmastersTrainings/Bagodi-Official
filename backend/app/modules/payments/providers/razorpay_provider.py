import hashlib
import hmac
import json
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx

from app.core.config import get_settings
from app.modules.payments.providers.base import (
    BasePaymentGatewayProvider,
    PaymentInitiationResult,
    PaymentVerificationResult,
    RefundResult,
    WebhookProcessingResult,
)


class RazorpayPaymentGatewayProvider(BasePaymentGatewayProvider):
    """
    Razorpay Sandbox & Production Payment Gateway Adapter.
    Adheres strictly to the BasePaymentGatewayProvider interface.
    Supports cryptographic HMAC-SHA256 verification and sandbox simulation.
    """

    def __init__(
        self,
        key_id: str | None = None,
        key_secret: str | None = None,
        webhook_secret: str | None = None,
        base_url: str = "https://api.razorpay.com/v1",
        is_sandbox: bool = True,
    ):
        settings = get_settings()
        self.key_id = (
            key_id
            or getattr(settings, "razorpay_key_id", None)
            or "rzp_test_bagodi_sandbox_key_001"
        )
        self.key_secret = (
            key_secret
            or getattr(settings, "razorpay_key_secret", None)
            or "rzp_test_secret_32char_key_bagodi"
        )
        self.webhook_secret = (
            webhook_secret
            or getattr(settings, "razorpay_webhook_secret", None)
            or "rzp_whsec_32char_key_bagodi"
        )
        self.base_url = base_url
        self.is_sandbox = is_sandbox

    @property
    def provider_name(self) -> str:
        return "razorpay"

    def generate_payment_signature(self, order_id: str, payment_id: str) -> str:
        msg = f"{order_id}|{payment_id}".encode()
        return hmac.new(self.key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    def generate_webhook_signature(self, raw_body: bytes) -> str:
        return hmac.new(self.webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

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
        amount_paise = int(amount * 100)
        order_payload = {
            "amount": amount_paise,
            "currency": currency,
            "receipt": order_number,
            "notes": {
                "tenant_id": str(tenant_id),
                "transaction_id": str(transaction_id),
            },
        }

        # Offline sandbox deterministic simulation when test keys are active
        if self.is_sandbox and (self.key_id.startswith("rzp_test_bagodi") or not self.key_id):
            gw_order_id = f"order_rzp_{transaction_id.hex[:14]}"
            return PaymentInitiationResult(
                gateway_order_id=gw_order_id,
                gateway_payment_id=None,
                status="initiated",
                checkout_url=f"https://api.razorpay.com/v1/checkout/{gw_order_id}",
                checkout_payload={
                    "key": self.key_id,
                    "order_id": gw_order_id,
                    "amount": amount_paise,
                    "currency": currency,
                    "name": "Bagodi Retail",
                    "description": f"Order #{order_number}",
                    "prefill": customer_info or {},
                },
            )

        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            resp = await client.post(
                "/orders",
                json=order_payload,
                auth=(self.key_id, self.key_secret),
            )
            data = resp.json()
            if resp.status_code >= 400:
                raise RuntimeError(f"Razorpay order creation failed: {data}")
            gw_order_id = data["id"]
            return PaymentInitiationResult(
                gateway_order_id=gw_order_id,
                gateway_payment_id=None,
                status="initiated",
                checkout_payload=data,
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
        expected_sig = self.generate_payment_signature(gateway_order_id, gateway_payment_id)
        if not hmac.compare_digest(expected_sig, gateway_signature):
            return PaymentVerificationResult(
                is_valid=False,
                gateway_payment_id=gateway_payment_id,
                status="failed",
                error_message="Razorpay payment signature mismatch",
            )

        # Standard Razorpay processing fee: 2% + 18% GST on fee
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
                "status": "captured",
                "order_id": gateway_order_id,
                "id": gateway_payment_id,
            },
        )

    async def verify_webhook_signature(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> bool:
        sig = headers.get("x-razorpay-signature") or headers.get("X-Razorpay-Signature")
        if not sig:
            return False
        expected_sig = self.generate_webhook_signature(raw_body)
        return hmac.compare_digest(expected_sig, sig)

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
                error_message="Invalid Razorpay webhook signature",
            )
        payload = json.loads(raw_body.decode("utf-8"))
        event = payload.get("event", "payment.captured")
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        gw_order_id = payment_entity.get("order_id")
        gw_payment_id = payment_entity.get("id")
        amount = Decimal(str(payment_entity.get("amount", 0))) / Decimal("100.0")
        fee = Decimal(str(payment_entity.get("fee", 0))) / Decimal("100.0")
        tax = Decimal(str(payment_entity.get("tax", 0))) / Decimal("100.0")

        return WebhookProcessingResult(
            is_valid=True,
            event_id=payload.get("account_id", f"evt_rzp_{gw_payment_id}"),
            event_type=event,
            gateway_order_id=gw_order_id,
            gateway_payment_id=gw_payment_id,
            status="captured" if event == "payment.captured" else "failed",
            fee=fee,
            tax=tax,
            amount=amount,
            raw_payload=payload,
        )

    async def process_refund(
        self,
        *,
        tenant_id: UUID,
        transaction_id: UUID,
        gateway_payment_id: str,
        amount: Decimal,
        reason: str | None = None,
    ) -> RefundResult:
        if self.is_sandbox and (self.key_id.startswith("rzp_test_bagodi") or not self.key_id):
            gw_refund_id = f"rfnd_rzp_{transaction_id.hex[:14]}"
            return RefundResult(
                is_valid=True,
                gateway_refund_id=gw_refund_id,
                status="succeeded",
                fee=Decimal("0.00"),
                tax=Decimal("0.00"),
                raw_response={
                    "status": "processed",
                    "id": gw_refund_id,
                    "amount": int(amount * 100),
                },
            )
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            resp = await client.post(
                f"/payments/{gateway_payment_id}/refund",
                json={"amount": int(amount * 100), "notes": {"reason": reason or "Return"}},
                auth=(self.key_id, self.key_secret),
            )
            data = resp.json()
            if resp.status_code >= 400:
                return RefundResult(
                    is_valid=False,
                    gateway_refund_id="",
                    status="failed",
                    error_message=str(data),
                )
            return RefundResult(
                is_valid=True,
                gateway_refund_id=data.get("id", f"rfnd_{gateway_payment_id[:8]}"),
                status="succeeded",
                raw_response=data,
            )
