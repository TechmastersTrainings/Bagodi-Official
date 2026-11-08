import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

from app.core.config import get_settings
from app.modules.notifications.providers.base import (
    BaseNotificationProvider,
    DeliveryStatusUpdate,
    NotificationSendResult,
)


class MockNotificationProvider(BaseNotificationProvider):
    """
    Cryptographically verifiable mock notification provider for testing and development.
    Handles SMS, WhatsApp, and Email with in-memory delivery inspection and DLR callbacks.
    """

    _sent_messages: ClassVar[list[dict[str, Any]]] = []

    def __init__(
        self,
        webhook_secret: str | None = None,
        timestamp_tolerance_seconds: int = 300,
    ):
        settings = get_settings()
        self.webhook_secret = webhook_secret or settings.notification_webhook_secret
        self.timestamp_tolerance_seconds = timestamp_tolerance_seconds

    @property
    def provider_name(self) -> str:
        return "mock"

    @classmethod
    def get_sent_messages(cls) -> list[dict[str, Any]]:
        return list(cls._sent_messages)

    @classmethod
    def clear(cls) -> None:
        cls._sent_messages.clear()

    def generate_dlr_header(self, raw_body: bytes, timestamp: int | None = None) -> str:
        """Utility method to produce valid HMAC-SHA256 signature header for DLR webhooks."""
        ts = timestamp if timestamp is not None else int(time.time())
        msg = f"{ts}.{raw_body.decode('utf-8')}"
        sig = hmac.new(
            self.webhook_secret.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"t={ts},v1={sig}"

    async def send_sms(
        self,
        *,
        tenant_id: UUID,
        recipient_phone: str,
        message: str,
        template_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationSendResult:
        if metadata and metadata.get("simulate_failure"):
            return NotificationSendResult(
                success=False,
                status="failed",
                error_code="SMS_GATEWAY_TIMEOUT",
                error_message="Downstream SMS carrier unreachable",
            )

        provider_msg_id = f"sms_mock_{uuid4().hex[:12]}"
        record = {
            "channel": "sms",
            "provider_message_id": provider_msg_id,
            "tenant_id": tenant_id,
            "recipient": recipient_phone,
            "message": message,
            "template_id": template_id,
            "metadata": metadata or {},
            "sent_at": datetime.now(UTC),
        }
        self._sent_messages.append(record)

        return NotificationSendResult(
            success=True,
            provider_message_id=provider_msg_id,
            status="sent",
            raw_response={"provider": "mock", "carrier": "local_mock_network", "chars": len(message)},
        )

    async def send_whatsapp(
        self,
        *,
        tenant_id: UUID,
        recipient_phone: str,
        template_name: str,
        parameters: dict[str, str],
        fallback_text: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationSendResult:
        if metadata and metadata.get("simulate_failure"):
            return NotificationSendResult(
                success=False,
                status="failed",
                error_code="WA_NUMBER_NOT_REGISTERED",
                error_message="Recipient phone number is not on WhatsApp",
            )

        provider_msg_id = f"wa_mock_{uuid4().hex[:12]}"
        record = {
            "channel": "whatsapp",
            "provider_message_id": provider_msg_id,
            "tenant_id": tenant_id,
            "recipient": recipient_phone,
            "template_name": template_name,
            "parameters": parameters,
            "fallback_text": fallback_text,
            "metadata": metadata or {},
            "sent_at": datetime.now(UTC),
        }
        self._sent_messages.append(record)

        return NotificationSendResult(
            success=True,
            provider_message_id=provider_msg_id,
            status="sent",
            raw_response={"provider": "mock", "waba_id": "mock_waba_101", "template": template_name},
        )

    async def send_email(
        self,
        *,
        tenant_id: UUID,
        recipient_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationSendResult:
        if metadata and metadata.get("simulate_failure"):
            return NotificationSendResult(
                success=False,
                status="failed",
                error_code="SMTP_RELAY_DROPPED",
                error_message="Recipient domain rejected connection",
            )

        provider_msg_id = f"email_mock_{uuid4().hex[:12]}"
        record = {
            "channel": "email",
            "provider_message_id": provider_msg_id,
            "tenant_id": tenant_id,
            "recipient": recipient_email,
            "subject": subject,
            "body_html": body_html,
            "body_text": body_text,
            "metadata": metadata or {},
            "sent_at": datetime.now(UTC),
        }
        self._sent_messages.append(record)

        return NotificationSendResult(
            success=True,
            provider_message_id=provider_msg_id,
            status="sent",
            raw_response={"provider": "mock", "mx": "mail.bagodi.test", "accepted": [recipient_email]},
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
        )
        if not sig_header:
            return False

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
            try:
                msg = raw_body.decode("utf-8")
            except UnicodeDecodeError:
                return False

        expected_sig = hmac.new(
            self.webhook_secret.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected_sig, sig_part)

    async def parse_delivery_report(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> DeliveryStatusUpdate:
        is_valid = await self.verify_webhook_signature(raw_body=raw_body, headers=headers)
        if not is_valid:
            return DeliveryStatusUpdate(
                is_valid=False,
                provider_message_id="unknown",
                status="failed",
                timestamp=datetime.now(UTC),
                error_message="Invalid webhook signature or expired timestamp",
            )

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return DeliveryStatusUpdate(
                is_valid=False,
                provider_message_id="unknown",
                status="failed",
                timestamp=datetime.now(UTC),
                error_message=f"Malformed DLR JSON: {e!s}",
            )

        msg_id = payload.get("provider_message_id") or payload.get("message_id") or payload.get("id")
        dlr_status = payload.get("status", "delivered").lower()
        error_code = payload.get("error_code")
        error_msg = payload.get("error_message")

        return DeliveryStatusUpdate(
            is_valid=True,
            provider_message_id=str(msg_id) if msg_id else "unknown",
            status=dlr_status,
            timestamp=datetime.now(UTC),
            error_code=str(error_code) if error_code else None,
            error_message=str(error_msg) if error_msg else None,
            raw_payload=payload,
        )
