import logging
from abc import ABC, abstractmethod
from typing import ClassVar
from uuid import UUID

from app.core.config import get_settings

logger = logging.getLogger("bagodi.otp")


class BaseOTPProvider(ABC):
    @abstractmethod
    async def send_otp(self, phone_e164: str, otp_code: str, expires_in_seconds: int) -> bool:
        """Deliver OTP code to the recipient's mobile number."""


class ConsoleOTPProvider(BaseOTPProvider):
    async def send_otp(self, phone_e164: str, otp_code: str, expires_in_seconds: int) -> bool:
        logger.info(
            "OTP delivery requested for %s: code=%s (valid for %ds)",
            phone_e164,
            otp_code,
            expires_in_seconds,
        )
        return True


class InMemoryTestOTPProvider(BaseOTPProvider):
    _dispatched_otps: ClassVar[dict[str, str]] = {}

    async def send_otp(self, phone_e164: str, otp_code: str, expires_in_seconds: int) -> bool:
        self._dispatched_otps[phone_e164] = otp_code
        logger.debug("InMemory OTP captured for %s", phone_e164)
        return True

    @classmethod
    def get_last_otp(cls, phone_e164: str) -> str | None:
        return cls._dispatched_otps.get(phone_e164)

    @classmethod
    def clear(cls) -> None:
        cls._dispatched_otps.clear()


class TwilioOTPProvider(BaseOTPProvider):
    """Production SMS OTP delivery via Twilio Messaging REST API."""

    async def send_otp(self, phone_e164: str, otp_code: str, expires_in_seconds: int) -> bool:
        from app.modules.notifications.providers.twilio_provider import TwilioNotificationProvider

        cfg = get_settings()
        is_prod = cfg.app_env.lower() == "production" and not cfg.allow_mock_providers_in_production
        if is_prod and (not cfg.twilio_account_sid or not cfg.twilio_auth_token or not cfg.twilio_from_number):
            raise RuntimeError("Twilio SMS OTP credentials must be configured in production.")

        provider = TwilioNotificationProvider(
            account_sid=cfg.twilio_account_sid or None,
            auth_token=cfg.twilio_auth_token or None,
            from_number=cfg.twilio_from_number or None,
            is_sandbox=not is_prod,
        )
        mins = max(1, expires_in_seconds // 60)
        res = await provider.send_sms(
            tenant_id=UUID(int=0),
            recipient_phone=phone_e164,
            message=f"Your Bagodi verification code is {otp_code}. Valid for {mins} minutes. Do not share it.",
        )
        if not res.success:
            raise RuntimeError(f"Twilio OTP SMS failed: {res.error_code} {res.error_message}")
        return True


_test_provider = InMemoryTestOTPProvider()
_console_provider = ConsoleOTPProvider()
_twilio_provider = TwilioOTPProvider()


def get_otp_provider() -> BaseOTPProvider:
    cfg = get_settings()
    target = (cfg.otp_provider or "console").strip().lower()
    if target == "in_memory" or cfg.app_env == "test":
        return _test_provider
    if target in ("twilio", "sms"):
        return _twilio_provider
    return _console_provider
