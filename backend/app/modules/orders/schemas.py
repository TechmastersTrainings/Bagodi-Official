from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# --- Cart Schemas ---
class CartItemAdd(BaseModel):
    variant_id: UUID
    quantity: int = Field(default=1, gt=0)


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., gt=0)


class CartItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    variant_id: UUID
    sku: str
    product_name: str
    variant_name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    is_in_stock: bool
    available_qty: int


class CartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    customer_id: UUID | None
    session_id: str | None
    items: list[CartItemResponse]
    total_items: int
    subtotal: Decimal
    updated_at: datetime


class CartMergeRequest(BaseModel):
    session_id: str = Field(..., min_length=5, max_length=100, description="Guest session ID to merge into customer cart")


# --- Address & Checkout Schemas ---
class ShippingAddressSchema(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    address_line1: str = Field(..., min_length=3, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    postal_code: str = Field(..., min_length=4, max_length=20)
    phone: str = Field(..., min_length=10, max_length=20)


class CheckoutRequest(BaseModel):
    store_id: UUID = Field(..., description="Fulfilling store location")
    shipping_address: ShippingAddressSchema
    billing_address: ShippingAddressSchema | None = None
    customer_name: str = Field(..., min_length=2, max_length=200)
    customer_email: str | None = Field(default=None, max_length=150)
    customer_phone: str = Field(..., min_length=10, max_length=50)
    payment_method: Literal["online", "cod"] = "online"
    notes: str | None = Field(default=None, max_length=1000)
    idempotency_key: str | None = Field(default=None, max_length=100)


# --- Order Response Schemas ---
class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    variant_id: UUID
    sku: str
    product_name: str
    variant_name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal


class OrderStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    from_status: str | None
    to_status: str
    notes: str | None
    changed_by_user_id: UUID | None
    created_at: datetime


class PaymentTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transaction_reference: str
    payment_method: str
    amount: Decimal
    currency: str
    status: str
    gateway_provider: str
    error_message: str | None
    created_at: datetime


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    store_id: UUID
    customer_id: UUID
    order_number: str
    status: str
    payment_status: str
    payment_method: str
    fulfillment_status: str
    currency: str
    subtotal: Decimal
    discount_amount: Decimal
    shipping_fee: Decimal
    total_amount: Decimal
    reservation_expires_at: datetime | None
    reservation_released: bool
    shipping_address: dict
    billing_address: dict | None
    customer_name: str
    customer_email: str | None
    customer_phone: str
    notes: str | None
    items: list[OrderItemResponse]
    status_history: list[OrderStatusHistoryResponse]
    payments: list[PaymentTransactionResponse]
    created_at: datetime
    updated_at: datetime


# --- Order State Machine Operations ---
class OrderStatusUpdateRequest(BaseModel):
    status: Literal["CONFIRMED", "PROCESSING", "DISPATCHED", "DELIVERED", "CANCELLED", "RETURNED"]
    notes: str | None = Field(default=None, max_length=500)


class OrderCancelRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class PaymentCallbackRequest(BaseModel):
    transaction_reference: str = Field(..., min_length=2, max_length=100)
    gateway_status: Literal["success", "failure"]
    gateway_payload: dict | None = None
    error_message: str | None = None
