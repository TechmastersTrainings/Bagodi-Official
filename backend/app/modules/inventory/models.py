from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.modules.catalog.models import ProductVariant
    from app.modules.platform.models import Store


class Supplier(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_suppliers_tenant_code"),
    )

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class StockBalance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stock_balances"
    __table_args__ = (
        UniqueConstraint("tenant_id", "store_id", "variant_id", name="uq_stock_balances_tenant_store_variant"),
        CheckConstraint("on_hand_qty >= 0", name="chk_stock_balances_on_hand_non_negative"),
        CheckConstraint("reserved_qty >= 0", name="chk_stock_balances_reserved_non_negative"),
        CheckConstraint("available_qty >= 0", name="chk_stock_balances_available_non_negative"),
        CheckConstraint("in_transit_qty >= 0", name="chk_stock_balances_in_transit_non_negative"),
        CheckConstraint("reserved_qty <= on_hand_qty", name="chk_stock_balances_reserved_le_on_hand"),
    )

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    store_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    variant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    on_hand_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    in_transit_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reorder_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    low_stock_alert: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    store: Mapped["Store"] = relationship("Store")
    variant: Mapped["ProductVariant"] = relationship("ProductVariant")


class InventoryLedger(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable audit-grade double-entry stock ledger.

    Never edit or delete records. Balancing rule: from_account and to_account define debit/credit
    flow of units.
    """

    __tablename__ = "inventory_ledger"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_inventory_ledger_tenant_idempotency"),
        CheckConstraint("quantity > 0", name="chk_inventory_ledger_quantity_positive"),
    )

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    store_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    variant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    movement_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    from_account: Mapped[str] = mapped_column(String(50), nullable=False)
    to_account: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    on_hand_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    in_transit_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    balance_after_on_hand: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after_reserved: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after_available: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    store: Mapped["Store"] = relationship("Store")
    variant: Mapped["ProductVariant"] = relationship("ProductVariant")


class PurchaseOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "po_number", name="uq_purchase_orders_tenant_po_number"),
    )

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    store_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    supplier_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    po_number: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    store: Mapped["Store"] = relationship("Store")
    supplier: Mapped["Supplier | None"] = relationship("Supplier")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        "PurchaseOrderItem", cascade="all, delete-orphan", back_populates="purchase_order"
    )
    receipts: Mapped[list["StockReceipt"]] = relationship(
        "StockReceipt", back_populates="purchase_order"
    )


class PurchaseOrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "purchase_order_items"

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    purchase_order_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    purchase_order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder", back_populates="items")
    variant: Mapped["ProductVariant"] = relationship("ProductVariant")


class StockReceipt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stock_receipts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "receipt_number", name="uq_stock_receipts_tenant_receipt_number"),
    )

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    store_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    purchase_order_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    receipt_number: Mapped[str] = mapped_column(String(50), nullable=False)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_by_user_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    store: Mapped["Store"] = relationship("Store")
    purchase_order: Mapped["PurchaseOrder | None"] = relationship("PurchaseOrder", back_populates="receipts")
    items: Mapped[list["StockReceiptItem"]] = relationship(
        "StockReceiptItem", cascade="all, delete-orphan", back_populates="stock_receipt"
    )


class StockReceiptItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stock_receipt_items"

    stock_receipt_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stock_receipts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    stock_receipt: Mapped["StockReceipt"] = relationship("StockReceipt", back_populates="items")
    variant: Mapped["ProductVariant"] = relationship("ProductVariant")


class StoreTransfer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "store_transfers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "transfer_number", name="uq_store_transfers_tenant_transfer_number"),
    )

    tenant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_store_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    destination_store_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    transfer_number: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")  # draft, in_transit, received, cancelled
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched_by_user_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    received_by_user_id: Mapped[PG_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    source_store: Mapped["Store"] = relationship("Store", foreign_keys=[source_store_id])
    destination_store: Mapped["Store"] = relationship("Store", foreign_keys=[destination_store_id])
    items: Mapped[list["StoreTransferItem"]] = relationship(
        "StoreTransferItem", cascade="all, delete-orphan", back_populates="transfer"
    )


class StoreTransferItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "store_transfer_items"

    transfer_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("store_transfers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variant_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity_shipped: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    transfer: Mapped["StoreTransfer"] = relationship("StoreTransfer", back_populates="items")
    variant: Mapped["ProductVariant"] = relationship("ProductVariant")
