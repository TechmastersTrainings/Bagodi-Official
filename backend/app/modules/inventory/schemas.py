from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# --- Supplier Schemas ---
class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    code: str = Field(..., min_length=2, max_length=50, pattern=r"^[A-Z0-9_\-]+$")
    contact_person: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    gstin: str | None = Field(default=None, max_length=20)
    is_active: bool = Field(default=True)


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    contact_person: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    gstin: str | None = Field(default=None, max_length=20)
    is_active: bool | None = Field(default=None)


class SupplierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    code: str
    contact_person: str | None
    email: str | None
    phone: str | None
    address: str | None
    gstin: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --- Stock Balance Schemas ---
class StockBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    store_id: UUID
    variant_id: UUID
    on_hand_qty: int
    reserved_qty: int
    available_qty: int
    in_transit_qty: int
    reorder_threshold: int
    low_stock_alert: bool
    updated_at: datetime


# --- Inventory Ledger Schemas ---
class InventoryLedgerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    store_id: UUID
    variant_id: UUID
    movement_type: str
    from_account: str
    to_account: str
    quantity: int
    on_hand_delta: int
    reserved_delta: int
    in_transit_delta: int
    balance_after_on_hand: int
    balance_after_reserved: int
    balance_after_available: int
    idempotency_key: str | None
    reference_type: str | None
    reference_id: str | None
    notes: str | None
    created_by_user_id: UUID | None
    created_at: datetime


# --- Stock Movement Operation Payloads ---
class StockAdjustmentCreate(BaseModel):
    store_id: UUID
    variant_id: UUID
    reason: Literal["damage", "loss", "reconciliation_gain", "reconciliation_loss"]
    quantity: int = Field(..., gt=0)
    notes: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=100)


class StockReservationCreate(BaseModel):
    store_id: UUID
    variant_id: UUID
    quantity: int = Field(..., gt=0)
    reference_id: str = Field(..., min_length=1, max_length=100, description="Order ID or Checkout ID")
    notes: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=100)


class StockReservationRelease(BaseModel):
    store_id: UUID
    variant_id: UUID
    quantity: int = Field(..., gt=0)
    reference_id: str = Field(..., min_length=1, max_length=100, description="Order ID or Checkout ID")
    notes: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=100)


class StockDispatchCreate(BaseModel):
    store_id: UUID
    variant_id: UUID
    quantity: int = Field(..., gt=0)
    reference_id: str = Field(..., min_length=1, max_length=100, description="Order ID")
    notes: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=100)


class CustomerReturnCreate(BaseModel):
    store_id: UUID
    variant_id: UUID
    quantity: int = Field(..., gt=0)
    reference_id: str = Field(..., min_length=1, max_length=100, description="Return Authorization or Order ID")
    notes: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=100)


# --- Purchase Order Schemas ---
class PurchaseOrderItemCreate(BaseModel):
    variant_id: UUID
    quantity_ordered: int = Field(..., gt=0)
    unit_cost: Decimal = Field(..., ge=0)


class PurchaseOrderCreate(BaseModel):
    store_id: UUID
    supplier_id: UUID | None = None
    po_number: str = Field(..., min_length=2, max_length=50, pattern=r"^[A-Z0-9_\-]+$")
    items: list[PurchaseOrderItemCreate] = Field(..., min_length=1)
    notes: str | None = Field(default=None, max_length=1000)


class PurchaseOrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    variant_id: UUID
    quantity_ordered: int
    quantity_received: int
    unit_cost: Decimal
    total_cost: Decimal


class PurchaseOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    store_id: UUID
    supplier_id: UUID | None
    po_number: str
    status: str
    total_amount: Decimal
    notes: str | None
    items: list[PurchaseOrderItemResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# --- Stock Receipt Schemas ---
class StockReceiptItemCreate(BaseModel):
    variant_id: UUID
    quantity_received: int = Field(..., gt=0)
    unit_cost: Decimal = Field(..., ge=0)


class StockReceiptCreate(BaseModel):
    store_id: UUID
    purchase_order_id: UUID | None = None
    receipt_number: str = Field(..., min_length=2, max_length=50, pattern=r"^[A-Z0-9_\-]+$")
    invoice_number: str | None = Field(default=None, max_length=100)
    items: list[StockReceiptItemCreate] = Field(..., min_length=1)
    notes: str | None = Field(default=None, max_length=1000)
    idempotency_key: str | None = Field(default=None, max_length=100)


class StockReceiptItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    variant_id: UUID
    quantity_received: int
    unit_cost: Decimal


class StockReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    store_id: UUID
    purchase_order_id: UUID | None
    receipt_number: str
    invoice_number: str | None
    notes: str | None
    items: list[StockReceiptItemResponse] = Field(default_factory=list)
    created_at: datetime


# --- Store Transfer Schemas ---
class StoreTransferItemCreate(BaseModel):
    variant_id: UUID
    quantity_shipped: int = Field(..., gt=0)


class StoreTransferCreate(BaseModel):
    source_store_id: UUID
    destination_store_id: UUID
    transfer_number: str = Field(..., min_length=2, max_length=50, pattern=r"^[A-Z0-9_\-]+$")
    items: list[StoreTransferItemCreate] = Field(..., min_length=1)
    notes: str | None = Field(default=None, max_length=1000)
    idempotency_key: str | None = Field(default=None, max_length=100)


class StoreTransferReceive(BaseModel):
    idempotency_key: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=1000)


class StoreTransferItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    variant_id: UUID
    quantity_shipped: int
    quantity_received: int


class StoreTransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    source_store_id: UUID
    destination_store_id: UUID
    transfer_number: str
    status: str
    notes: str | None
    items: list[StoreTransferItemResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

