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
    from app.modules.catalog.models import ProductVariant
    from app.modules.identity.models import User
    from app.modules.platform.models import Store


class Cart(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "carts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "customer_id", name="uq_carts_tenant_customer"),
    )

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    coupon_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    items: Mapped[list["CartItem"]] = relationship(
        "CartItem", cascade="all, delete-orphan", back_populates="cart"
    )


class CartItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "variant_id", name="uq_cart_items_cart_variant"),
        CheckConstraint("quantity > 0", name="chk_cart_items_quantity_positive"),
    )

    cart_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")
    variant: Mapped["ProductVariant"] = relationship("ProductVariant")


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_number", name="uq_orders_tenant_order_number"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_orders_tenant_idempotency"),
    )

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING_PAYMENT", index=True
    )
    payment_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False, default="online")
    fulfillment_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="unfulfilled"
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    shipping_fee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    coupon_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("coupons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    coupon_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discount_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reservation_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    reservation_released: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    shipping_address: Mapped[dict] = mapped_column(JSONB, nullable=False)
    billing_address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    customer_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    store: Mapped["Store"] = relationship("Store")
    customer: Mapped["User"] = relationship("User")
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", cascade="all, delete-orphan", back_populates="order"
    )
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        "OrderStatusHistory",
        cascade="all, delete-orphan",
        back_populates="order",
        order_by="OrderStatusHistory.created_at.asc()",
    )
    payments: Mapped[list["PaymentTransaction"]] = relationship(
        "PaymentTransaction", cascade="all, delete-orphan", back_populates="order"
    )
    return_requests: Mapped[list["OrderReturnRequest"]] = relationship(
        "OrderReturnRequest", cascade="all, delete-orphan", back_populates="order"
    )


class OrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_items"

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(String(80), nullable=False)
    product_name: Mapped[str] = mapped_column(String(250), nullable=False)
    variant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    original_unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    applied_promotion_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("promotions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    applied_promotion_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    variant: Mapped["ProductVariant"] = relationship("ProductVariant")


class OrderStatusHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_status_history"

    order_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by_user_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    order: Mapped["Order"] = relationship("Order", back_populates="status_history")


class PaymentTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payment_transactions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "transaction_reference", name="uq_payment_transactions_tenant_ref"
        ),
    )

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transaction_reference: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="initiated"
    )  # initiated, captured, failed, refunded, partially_refunded
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    gateway_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="mock")
    gateway_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    gateway_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    gateway_signature: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount_refunded: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    gateway_fee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    gateway_tax: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gateway_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="payments")


class OrderReturnRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_return_requests"

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_item_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="RETURN"
    )  # RETURN, EXCHANGE
    reason: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # SIZE_FIT_ISSUE, DEFECTIVE, WRONG_ITEM, FABRIC_QUALITY, COLOR_MISMATCH, CHANGED_MIND
    detailed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_variant_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requested_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="REQUESTED", index=True
    )  # REQUESTED, APPROVED, REJECTED, PICKUP_SCHEDULED, PICKED_UP, RECEIVED, COMPLETED, CANCELLED
    refund_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pickup_tracking_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    images: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="return_requests")
    order_item: Mapped["OrderItem"] = relationship("OrderItem")
    customer: Mapped["User"] = relationship("User", foreign_keys=[customer_id])
    requested_variant: Mapped["ProductVariant | None"] = relationship(
        "ProductVariant", foreign_keys=[requested_variant_id]
    )
    reviewed_by: Mapped["User | None"] = relationship("User", foreign_keys=[reviewed_by_user_id])

