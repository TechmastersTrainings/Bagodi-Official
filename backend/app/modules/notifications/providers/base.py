from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class NotificationChannel(StrEnum):
    SMS = "sms"
    WHATSAPP = "whatsapp"
    EMAIL = "email"


@dataclass
class NotificationSendResult:
    success: bool
    provider_message_id: str | None = None
    status: str = "sent"  # sent, failed
    error_code: str | None = None
    error_message: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliveryStatusUpdate:
    is_valid: bool
    provider_message_id: str
    status: str  # delivered, failed, bounced, undelivered
    timestamp: datetime
    error_code: str | None = None
    error_message: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


class BaseNotificationProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier (e.g. 'mock', 'twilio', 'gupshup', 'ses')."""

    @abstractmethod
    async def send_sms(
        self,
        *,
        tenant_id: UUID,
        recipient_phone: str,
        message: str,
        template_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationSendResult:
        """Dispatch transactional or promotional SMS."""

    @abstractmethod
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
        """Dispatch verified WhatsApp Business message using pre-approved template."""

    @abstractmethod
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
        """Dispatch transactional or digest Email."""

    @abstractmethod
    async def verify_webhook_signature(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> bool:
        """Verify provider delivery callback (DLR) webhook authenticity."""

    @abstractmethod
    async def parse_delivery_report(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> DeliveryStatusUpdate:
        """Parse inbound delivery callback (DLR) payload into standardized update."""
