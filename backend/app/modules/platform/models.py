from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.modules.identity.models import User


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    legal_name: Mapped[str | None] = mapped_column(String(250), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    business_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pan_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(25), nullable=True)
    registered_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    bank_account_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bank_ifsc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_specialization: Mapped[str | None] = mapped_column(String(150), nullable=True)

    stores: Mapped[list["Store"]] = relationship("Store", back_populates="tenant", cascade="all, delete-orphan")
    kyc_documents: Mapped[list["TenantKYCDocument"]] = relationship("TenantKYCDocument", back_populates="tenant", cascade="all, delete-orphan")
    status_logs: Mapped[list["TenantStatusLog"]] = relationship("TenantStatusLog", back_populates="tenant", cascade="all, delete-orphan")
    subscriptions: Mapped[list["MerchantSubscription"]] = relationship("MerchantSubscription", back_populates="tenant", cascade="all, delete-orphan")
    invoices: Mapped[list["MerchantInvoice"]] = relationship("MerchantInvoice", back_populates="tenant", cascade="all, delete-orphan")


class Store(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stores"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_stores_tenant_code"),)

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    address_line: Mapped[str | None] = mapped_column(String(300), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="stores")


class TenantKYCDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenant_kyc_documents"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)  # GST_CERTIFICATE, PAN_CARD, TRADE_LICENSE, BANK_STATEMENT, IDENTITY_PROOF
    document_number: Mapped[str] = mapped_column(String(100), nullable=False)
    document_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True)  # PENDING, VERIFIED, REJECTED
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="kyc_documents")


class TenantStatusLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "tenant_status_logs"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_status: Mapped[str] = mapped_column(String(30), nullable=False)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actor_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="status_logs")


class MerchantSubscriptionPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "merchant_subscription_plans"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_cycle: Mapped[str] = mapped_column(String(30), nullable=False, default="MONTHLY")  # MONTHLY, ANNUAL
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    max_stores: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_staff_users: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    commission_rate_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    features: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MerchantSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "merchant_subscriptions"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("merchant_subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")  # ACTIVE, TRIAL, PAST_DUE, CANCELLED
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="subscriptions")
    plan: Mapped["MerchantSubscriptionPlan"] = relationship("MerchantSubscriptionPlan")


class MerchantInvoice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "merchant_invoices"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("merchant_subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    billing_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    billing_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True)  # PAID, PENDING, OVERDUE, VOID
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(150), nullable=True)
    line_items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="invoices")
    subscription: Mapped["MerchantSubscription | None"] = relationship("MerchantSubscription")


class PlatformAuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "platform_audit_logs"

    actor_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
