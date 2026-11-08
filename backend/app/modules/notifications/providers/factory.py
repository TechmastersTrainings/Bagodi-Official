from typing import ClassVar

from app.core.config import get_settings
from app.modules.notifications.providers.base import BaseNotificationProvider
from app.modules.notifications.providers.mock_provider import MockNotificationProvider


class NotificationProviderFactory:
    """Factory resolving notification gateway adapters by provider name."""

    _providers: ClassVar[dict[str, BaseNotificationProvider]] = {}

    @classmethod
    def get_provider(cls, provider_name: str | None = None) -> BaseNotificationProvider:
        settings = get_settings()
        target = (provider_name or settings.notification_default_provider or "mock").strip().lower()

        if "mock" not in cls._providers:
            cls._providers["mock"] = MockNotificationProvider()
        return cls._providers.get(target, cls._providers["mock"])
