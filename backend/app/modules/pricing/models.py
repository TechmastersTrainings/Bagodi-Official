from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
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
    from app.modules.orders.models import Order
    from app.modules.platform.models import Tenant


class Promotion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "promotions"
    __table_args__ = (
        CheckConstraint("discount_value > 0", name="chk_promotions_discount_value_positive"),
        CheckConstraint(
            "promotion_type IN ('PERCENTAGE', 'FIXED_AMOUNT')",
            name="chk_promotions_type_valid",
        ),
        CheckConstraint(
            "scope IN ('VARIANT', 'PRODUCT', 'CATEGORY', 'CART')",
            name="chk_promotions_scope_valid",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'archived')",
            name="chk_promotions_status_valid",
        ),
    )

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    promotion_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # PERCENTAGE | FIXED_AMOUNT
    scope: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # VARIANT | PRODUCT | CATEGORY | CART
    target_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    discount_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    max_discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    min_order_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_stackable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    tenant: Mapped["Tenant"] = relationship("Tenant")


class Coupon(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "coupons"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_coupons_tenant_code"),
        CheckConstraint("discount_value > 0", name="chk_coupons_discount_value_positive"),
        CheckConstraint(
            "discount_type IN ('PERCENTAGE', 'FIXED_AMOUNT')",
            name="chk_coupons_discount_type_valid",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'expired')",
            name="chk_coupons_status_valid",
        ),
        CheckConstraint(
            "usage_limit_per_customer > 0",
            name="chk_coupons_usage_limit_per_customer_positive",
        ),
    )

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    discount_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # PERCENTAGE | FIXED_AMOUNT
    discount_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    max_discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    min_order_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    total_usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_limit_per_customer: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_redeemed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_stackable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    redemptions: Mapped[list["CouponRedemption"]] = relationship(
        "CouponRedemption", back_populates="coupon"
    )


class CouponRedemption(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "coupon_redemptions"
    __table_args__ = (
        UniqueConstraint("coupon_id", "order_id", name="uq_coupon_redemptions_coupon_order"),
    )

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    coupon_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("coupons.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    discount_applied: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="consumed", index=True
    )  # consumed | reverted

    coupon: Mapped["Coupon"] = relationship("Coupon", back_populates="redemptions")
    customer: Mapped["User"] = relationship("User")
    order: Mapped["Order"] = relationship("Order")


class PricingAuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "pricing_audit_logs"

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )  # promotion | coupon
    entity_id: Mapped[PG_UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # CREATE | UPDATE | STATUS_CHANGE | DELETE
    changed_by_user_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    changes: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
