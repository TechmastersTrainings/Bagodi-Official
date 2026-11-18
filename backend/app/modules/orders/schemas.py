from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field


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
    coupon_code: str | None = None
    items: list[CartItemResponse]
    total_items: int
    subtotal: Decimal
    discount_amount: Decimal = Decimal("0.00")
    total_amount: Decimal = Decimal("0.00")
    updated_at: datetime


class CartMergeRequest(BaseModel):
    session_id: str = Field(
        ...,
        min_length=5,
        max_length=100,
        description="Guest session ID to merge into customer cart",
    )


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
    store_id: UUID | None = Field(default=None, description="Fulfilling store location (defaults to active store)")
    shipping_address: ShippingAddressSchema
    billing_address: ShippingAddressSchema | None = None
    customer_name: str = Field(..., min_length=2, max_length=200)
    customer_email: str | None = Field(default=None, max_length=150)
    customer_phone: str = Field(..., min_length=10, max_length=50)
    payment_method: Literal["online", "cod", "upi", "card", "netbanking"] = "online"
    notes: str | None = Field(default=None, max_length=1000)
    coupon_code: str | None = Field(
        default=None, max_length=50, description="Optional promotional coupon code"
    )
    idempotency_key: str | None = Field(default=None, max_length=100)


class DirectOrderItem(BaseModel):
    variant_id: UUID
    quantity: int = Field(default=1, gt=0)


class DirectCheckoutRequest(BaseModel):
    items: list[DirectOrderItem] = Field(..., min_length=1)
    store_id: UUID | None = Field(default=None, description="Fulfilling store location")
    shipping_address: ShippingAddressSchema | None = None
    customer_name: str | None = Field(default=None, max_length=200)
    customer_email: str | None = Field(default=None, max_length=150)
    customer_phone: str | None = Field(default=None, max_length=50)
    payment_method: Literal["online", "cod", "upi", "card", "netbanking"] = "cod"
    notes: str | None = Field(default=None, max_length=1000)
    coupon_code: str | None = Field(default=None, max_length=50)
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
    original_unit_price: Decimal = Decimal("0.00")
    unit_price: Decimal
    discount_amount: Decimal = Decimal("0.00")
    total_price: Decimal
    applied_promotion_id: UUID | None = None
    applied_promotion_title: str | None = None

    @computed_field
    def productName(self) -> str:
        return self.product_name

    @computed_field
    def variantName(self) -> str:
        return self.variant_name

    @computed_field
    def unitPrice(self) -> float:
        return float(self.unit_price)

    @computed_field
    def totalPrice(self) -> float:
        return float(self.total_price)


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
    coupon_id: UUID | None = None
    coupon_code: str | None = None
    discount_breakdown: dict | None = None
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

    @computed_field
    def orderNumber(self) -> str:
        return self.order_number

    @computed_field
    def grandTotal(self) -> float:
        return float(self.total_amount)

    @computed_field
    def discountTotal(self) -> float:
        return float(self.discount_amount)

    @computed_field
    def deliveryCharge(self) -> float:
        return float(self.shipping_fee)

    @computed_field
    def paymentStatus(self) -> str:
        return self.payment_status

    @computed_field
    def paymentMethod(self) -> str:
        return self.payment_method

    @computed_field
    def customerName(self) -> str:
        return self.customer_name

    @computed_field
    def customerPhone(self) -> str:
        return self.customer_phone

    @computed_field
    def customerEmail(self) -> str | None:
        return self.customer_email

    @computed_field
    def createdAt(self) -> str:
        return self.created_at.isoformat() if self.created_at else ""

    @computed_field
    def updatedAt(self) -> str:
        return self.updated_at.isoformat() if self.updated_at else ""


class PaginatedOrderResponse(BaseModel):
    items: list[OrderResponse]
    total: int
    page: int
    pageSize: int
    totalPages: int


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


# --- Return & Exchange Schemas ---
class OrderReturnRequestCreate(BaseModel):
    order_item_id: UUID
    request_type: Literal["RETURN", "EXCHANGE"] = "RETURN"
    reason: str = Field(..., min_length=2, max_length=100)
    detailed_reason: str | None = Field(default=None, max_length=1000)
    requested_variant_id: UUID | None = None
    requested_size: str | None = Field(default=None, max_length=50)
    images: list[str] | None = None


class OrderReturnRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    order_id: UUID
    order_item_id: UUID
    customer_id: UUID
    request_type: str
    reason: str
    detailed_reason: str | None
    requested_variant_id: UUID | None
    requested_size: str | None
    status: str
    refund_amount: Decimal | None
    admin_notes: str | None
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    pickup_tracking_id: str | None
    images: list[str] | None
    created_at: datetime
    updated_at: datetime


class OrderReturnReviewRequest(BaseModel):
    status: Literal[
        "APPROVED",
        "REJECTED",
        "PICKUP_SCHEDULED",
        "PICKED_UP",
        "RECEIVED",
        "COMPLETED",
        "CANCELLED",
    ]
    admin_notes: str | None = Field(default=None, max_length=1000)
    refund_amount: Decimal | None = None
    pickup_tracking_id: str | None = None

