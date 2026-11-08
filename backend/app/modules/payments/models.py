from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.orders.models import PaymentTransaction  # Re-export for payments module

if TYPE_CHECKING:
    from app.modules.identity.models import User
    from app.modules.orders.models import Order
    from app.modules.platform.models import Tenant


class Refund(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refunds"
    __table_args__ = (
        UniqueConstraint("tenant_id", "refund_reference", name="uq_refunds_tenant_reference"),
    )

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payment_transaction_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("payment_transactions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    refund_reference: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    gateway_refund_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="initiated", index=True
    )  # initiated, pending, succeeded, failed
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    initiated_by_user_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    gateway_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    order: Mapped["Order"] = relationship("Order")
    payment_transaction: Mapped["PaymentTransaction"] = relationship("PaymentTransaction")
    initiated_by: Mapped["User"] = relationship("User")


class CodSettlement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cod_settlements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_id", name="uq_cod_settlements_tenant_order"),
    )

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payment_transaction_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("payment_transactions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount_collected: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collected_by_name: Mapped[str] = mapped_column(String(150), nullable=False)
    settlement_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending_deposit", index=True
    )  # pending_deposit, deposited_to_bank, reconciled, discrepancy
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bank_deposit_reference: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    order: Mapped["Order"] = relationship("Order")
    payment_transaction: Mapped["PaymentTransaction"] = relationship("PaymentTransaction")


class PaymentAuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "payment_audit_logs"

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payment_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("payment_transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    refund_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("refunds.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class ProcessedWebhookEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "processed_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "event_id",
            name="uq_processed_webhook_events_tenant_provider_event",
        ),
    )

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
