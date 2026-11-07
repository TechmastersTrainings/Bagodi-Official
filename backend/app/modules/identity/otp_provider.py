import logging
from abc import ABC, abstractmethod
from typing import ClassVar

from app.core.config import get_settings

logger = logging.getLogger("bagodi.otp")
settings = get_settings()


class BaseOTPProvider(ABC):
    @abstractmethod
    async def send_otp(self, phone_e164: str, otp_code: str, expires_in_seconds: int) -> bool:
        """Deliver OTP code to the recipient's mobile number."""


class ConsoleOTPProvider(BaseOTPProvider):
    async def send_otp(self, phone_e164: str, otp_code: str, expires_in_seconds: int) -> bool:
        logger.info(
            "OTP delivery requested for %s: code dispatched (valid for %ds)",
            phone_e164,
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


_test_provider = InMemoryTestOTPProvider()
_console_provider = ConsoleOTPProvider()


def get_otp_provider() -> BaseOTPProvider:
    if settings.otp_provider == "in_memory" or settings.app_env == "test":
        return _test_provider
    return _console_provider
