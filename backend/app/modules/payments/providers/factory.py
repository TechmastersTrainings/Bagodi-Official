from typing import ClassVar

from app.core.config import get_settings
from app.modules.payments.providers.base import BasePaymentGatewayProvider
from app.modules.payments.providers.cod_provider import CodPaymentProvider
from app.modules.payments.providers.mock_provider import MockPaymentGatewayProvider
from app.modules.payments.providers.razorpay_provider import RazorpayPaymentGatewayProvider


class PaymentGatewayFactory:
    """Factory to retrieve payment gateway providers according to provider identifier."""

    _providers: ClassVar[dict[str, BasePaymentGatewayProvider]] = {}

    @classmethod
    def get_provider(cls, provider_name: str | None = None) -> BasePaymentGatewayProvider:
        settings = get_settings()
        target = (provider_name or settings.payment_gateway_provider or "mock").strip().lower()

        if target in ("cod", "cash_on_delivery"):
            if "cod" not in cls._providers:
                cls._providers["cod"] = CodPaymentProvider()
            return cls._providers["cod"]

        if target == "razorpay":
            if "razorpay" not in cls._providers:
                cls._providers["razorpay"] = RazorpayPaymentGatewayProvider()
            return cls._providers["razorpay"]

        # Default / mock / simulated gateway
        if "mock" not in cls._providers:
            cls._providers["mock"] = MockPaymentGatewayProvider()
        return cls._providers["mock"]
