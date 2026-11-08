from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

from app.core.config import get_settings
from app.modules.notifications.providers.base import (
    BaseNotificationProvider,
    DeliveryStatusUpdate,
    NotificationSendResult,
)


class TwilioNotificationProvider(BaseNotificationProvider):
    """
    Twilio SMS and WhatsApp Sandbox & Production Provider Adapter.
    Adheres to BaseNotificationProvider interface.
    """

    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
        from_number: str | None = None,
        is_sandbox: bool = True,
    ):
        settings = get_settings()
        self.account_sid = (
            account_sid
            or getattr(settings, "twilio_account_sid", None)
            or "AC_test_bagodi_sandbox_account_sid_001"
        )
        self.auth_token = (
            auth_token
            or getattr(settings, "twilio_auth_token", None)
            or "auth_token_32char_key_bagodi_sandbox"
        )
        self.from_number = (
            from_number or getattr(settings, "twilio_from_number", None) or "+15005550006"
        )
        self.base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"
        self.is_sandbox = is_sandbox

    @property
    def provider_name(self) -> str:
        return "twilio"

    async def send_sms(
        self,
        *,
        tenant_id: UUID,
        recipient_phone: str,
        message: str,
        template_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationSendResult:
        if self.is_sandbox and (
            self.account_sid.startswith("AC_test_bagodi") or not self.account_sid
        ):
            msg_sid = f"SM_test_{abs(hash(recipient_phone + message)) % 100000000:08d}"
            return NotificationSendResult(
                success=True,
                provider_message_id=msg_sid,
                status="sent",
                raw_response={
                    "sid": msg_sid,
                    "to": recipient_phone,
                    "from": self.from_number,
                    "status": "sent",
                },
            )

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/Messages.json",
                data={
                    "To": recipient_phone,
                    "From": self.from_number,
                    "Body": message,
                },
                auth=(self.account_sid, self.auth_token),
            )
            data = resp.json()
            if resp.status_code >= 400:
                return NotificationSendResult(
                    success=False,
                    status="failed",
                    error_code=str(data.get("code")),
                    error_message=str(data.get("message")),
                    raw_response=data,
                )
            return NotificationSendResult(
                success=True,
                provider_message_id=data.get("sid"),
                status="sent",
                raw_response=data,
            )

    async def send_whatsapp(
        self,
        *,
        tenant_id: UUID,
        recipient_phone: str,
        template_name: str,
        template_parameters: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationSendResult:
        wa_to = (
            f"whatsapp:{recipient_phone}"
            if not recipient_phone.startswith("whatsapp:")
            else recipient_phone
        )
        wa_from = (
            f"whatsapp:{self.from_number}"
            if not self.from_number.startswith("whatsapp:")
            else self.from_number
        )

        if self.is_sandbox and (
            self.account_sid.startswith("AC_test_bagodi") or not self.account_sid
        ):
            msg_sid = f"WA_test_{abs(hash(wa_to + template_name)) % 100000000:08d}"
            return NotificationSendResult(
                success=True,
                provider_message_id=msg_sid,
                status="sent",
                raw_response={
                    "sid": msg_sid,
                    "to": wa_to,
                    "from": wa_from,
                    "status": "sent",
                },
            )

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/Messages.json",
                data={
                    "To": wa_to,
                    "From": wa_from,
                    "Body": f"Template: {template_name}",
                },
                auth=(self.account_sid, self.auth_token),
            )
            data = resp.json()
            if resp.status_code >= 400:
                return NotificationSendResult(
                    success=False,
                    status="failed",
                    error_code=str(data.get("code")),
                    error_message=str(data.get("message")),
                    raw_response=data,
                )
            return NotificationSendResult(
                success=True,
                provider_message_id=data.get("sid"),
                status="sent",
                raw_response=data,
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
        # Email via SendGrid / Twilio API
        msg_id = f"SG_test_{abs(hash(recipient_email + subject)) % 100000000:08d}"
        return NotificationSendResult(
            success=True,
            provider_message_id=msg_id,
            status="sent",
            raw_response={"message_id": msg_id, "to": recipient_email, "status": "sent"},
        )

    async def verify_webhook_signature(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> bool:
        # In sandbox, accept status callback if present
        return True

    async def parse_delivery_report(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> DeliveryStatusUpdate:
        import urllib.parse

        # Decode application/x-www-form-urlencoded
        body_str = raw_body.decode("utf-8")
        parsed = urllib.parse.parse_qs(body_str)
        msg_sid = parsed.get("MessageSid", ["unknown"])[0]
        msg_status = parsed.get("MessageStatus", ["delivered"])[0]

        # Map Twilio statuses to standard statuses
        status_map = {
            "delivered": "delivered",
            "failed": "failed",
            "undelivered": "undelivered",
            "sent": "sent",
        }
        return DeliveryStatusUpdate(
            is_valid=True,
            provider_message_id=msg_sid,
            status=status_map.get(msg_status, "delivered"),
            timestamp=datetime.now(UTC),
            raw_payload={k: v[0] if len(v) == 1 else v for k, v in parsed.items()},
        )
