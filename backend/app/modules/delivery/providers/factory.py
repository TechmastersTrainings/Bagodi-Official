from typing import ClassVar

from app.modules.delivery.providers.base import BaseCourierProvider
from app.modules.delivery.providers.mock_courier import MockCourierProvider
from app.modules.delivery.providers.shiprocket_provider import ShiprocketCourierProvider


class CourierProviderFactory:
    _providers: ClassVar[dict[str, BaseCourierProvider]] = {}

    @classmethod
    def get_provider(cls, name: str | None = None) -> BaseCourierProvider:
        target = (name or "mock").lower()

        if target == "shiprocket":
            if "shiprocket" not in cls._providers:
                cls._providers["shiprocket"] = ShiprocketCourierProvider()
            return cls._providers["shiprocket"]

        if "mock" not in cls._providers:
            cls._providers["mock"] = MockCourierProvider()
        return cls._providers.get(target, cls._providers["mock"])

    @classmethod
    def register_provider(cls, name: str, provider: BaseCourierProvider) -> None:
        cls._providers[name.lower()] = provider
