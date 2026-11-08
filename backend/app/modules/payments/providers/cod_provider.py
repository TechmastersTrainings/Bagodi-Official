from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.modules.payments.providers.base import (
    BasePaymentGatewayProvider,
    PaymentInitiationResult,
    PaymentVerificationResult,
    RefundResult,
    WebhookProcessingResult,
)


class CodPaymentProvider(BasePaymentGatewayProvider):
    """
    Provider for Cash-On-Delivery transactions.
    Handles offline cash collections, courier reconciliations, and manual cash refunds.
    """

    @property
    def provider_name(self) -> str:
        return "cod"

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
        gateway_order_id = f"cod_{order_number}"
        return PaymentInitiationResult(
            gateway_order_id=gateway_order_id,
            gateway_payment_id=None,
            status="pending",
            checkout_payload={
                "payment_mode": "cash_on_delivery",
                "instructions": "Cash to be collected upon doorstep delivery",
                "amount": str(amount),
                "currency": currency,
            },
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
        return PaymentVerificationResult(
            is_valid=True,
            gateway_payment_id=gateway_payment_id,
            gateway_signature=gateway_signature,
            status="captured",
            fee=Decimal("0.00"),
            tax=Decimal("0.00"),
            raw_response={"mode": "cod_delivery_handover", "status": "captured"},
        )

    async def verify_webhook_signature(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> bool:
        # COD does not receive inbound webhooks
        return False

    async def process_webhook(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> WebhookProcessingResult:
        return WebhookProcessingResult(
            is_valid=False,
            event_id="none",
            event_type="none",
            status="failed",
            error_message="Webhooks not supported for COD provider",
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
        gateway_refund_id = f"rfnd_cod_{uuid4().hex[:12]}"
        return RefundResult(
            is_valid=True,
            gateway_refund_id=gateway_refund_id,
            status="succeeded",
            fee=Decimal("0.00"),
            tax=Decimal("0.00"),
            raw_response={
                "gateway": "cod",
                "refund_reference": refund_reference,
                "gateway_refund_id": gateway_refund_id,
                "amount": str(amount),
                "currency": currency,
                "reason": reason,
                "status": "succeeded",
            },
        )
