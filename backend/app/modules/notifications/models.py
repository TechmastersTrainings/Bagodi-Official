from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.modules.identity.models import User
    from app.modules.platform.models import Tenant


class NotificationOutbox(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Transactional Outbox for domain events.
    Enqueued atomically with the originating business mutations (orders, payments, refunds).
    """

    __tablename__ = "notification_outbox"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_notification_outbox_tenant_idemp"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant")


class NotificationMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Individual communications dispatched across SMS, WhatsApp, or Email.
    Tracks provider references, delivery states, and error handling.
    """

    __tablename__ = "notification_messages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_notification_messages_tenant_idemp"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    outbox_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("notification_outbox.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recipient: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # sms, whatsapp, email
    template_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="mock", index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    delivery_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    metadata_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    outbox: Mapped["NotificationOutbox"] = relationship("NotificationOutbox")


class NotificationTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Configurable, versioned notification templates per channel and language.
    Supports platform defaults (tenant_id IS NULL) and merchant overrides.
    """

    __tablename__ = "notification_templates"

    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # sms, whatsapp, email
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en", index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    subject_template: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    tenant: Mapped["Tenant | None"] = relationship("Tenant")


class CustomerCommunicationPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Customer consent and communication channel preferences per merchant tenant.
    """

    __tablename__ = "customer_communication_preferences"
    __table_args__ = (
        UniqueConstraint("tenant_id", "customer_id", name="uq_customer_comm_pref_tenant_customer"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sms_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    preferred_channel: Mapped[str] = mapped_column(String(30), nullable=False, default="whatsapp")
    consent_recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consent_ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    customer: Mapped["User"] = relationship("User")


class NotificationAuditLog(UUIDPrimaryKeyMixin, Base):
    """
    Immutable audit ledger capturing notification events, DLRs, and preference updates.
    """

    __tablename__ = "notification_audit_logs"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    message_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("notification_messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    message: Mapped["NotificationMessage | None"] = relationship("NotificationMessage")
    actor: Mapped["User | None"] = relationship("User")
