from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


# --- Cart Schemas ---
class CartItemAdd(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    variant_id: UUID | None = Field(default=None, alias="variantId")
    quantity: int = Field(default=1, gt=0)

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data):
        if isinstance(data, dict):
            if "variantId" in data and ("variant_id" not in data or not data["variant_id"]):
                data["variant_id"] = data["variantId"]
        return data


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., gt=0)


class CartVariantSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    sku: str
    size: str = "Standard"
    color_name: str | None = Field(default=None, alias="colorName")
    mrp: Decimal | None = None
    selling_price: Decimal | None = Field(default=None, alias="sellingPrice")
    available_stock: int = Field(default=0, alias="availableStock")


class CartPricing(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    subtotal: Decimal
    discount_total: Decimal = Field(default=Decimal("0.00"), alias="discountTotal")
    delivery_charge: Decimal = Field(default=Decimal("0.00"), alias="deliveryCharge")
    tax_total: Decimal = Field(default=Decimal("0.00"), alias="taxTotal")
    final_total: Decimal = Field(..., alias="finalTotal")


class CartItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    variant_id: UUID = Field(..., alias="variantId")
    sku: str
    product_name: str = Field(..., alias="productName")
    variant_name: str = Field(..., alias="variantName")
    image_url: str | None = Field(default=None, alias="imageUrl")
    quantity: int
    unit_price: Decimal = Field(..., alias="unitPrice")
    total_price: Decimal = Field(..., alias="totalPrice")
    is_in_stock: bool = True
    available_qty: int = Field(default=0, alias="availableStock")
    variant: CartVariantSummary | None = None


class CartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    tenant_id: UUID
    customer_id: UUID | None
    session_id: str | None
    coupon_code: str | None = None
    items: list[CartItemResponse]
    total_items: int = Field(..., alias="itemCount")
    subtotal: Decimal
    discount_amount: Decimal = Decimal("0.00")
    total_amount: Decimal = Decimal("0.00")
    pricing: CartPricing | None = None
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
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    full_name: str = Field(..., min_length=2, max_length=150, alias="fullName")
    address_line1: str = Field(..., min_length=3, max_length=255, alias="addressLine1")
    address_line2: str | None = Field(default=None, max_length=255, alias="addressLine2")
    landmark: str | None = Field(default=None, max_length=150)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    postal_code: str = Field(..., min_length=4, max_length=20, alias="postalCode")
    phone: str = Field(..., min_length=10, max_length=20, alias="phoneNumber")

    @model_validator(mode="before")
    @classmethod
    def normalize_shipping_address(cls, data):
        if isinstance(data, (str, bytes)):
            try:
                import json
                data = json.loads(data)
            except Exception:
                pass
        if isinstance(data, dict):
            if "recipient_name" in data and "full_name" not in data:
                data["full_name"] = data["recipient_name"]
            elif "fullName" in data and "full_name" not in data:
                data["full_name"] = data["fullName"]
            if "phoneNumber" in data and "phone" not in data:
                data["phone"] = data["phoneNumber"]
            elif "phone_number" in data and "phone" not in data:
                data["phone"] = data["phone_number"]
            if "addressLine1" in data and "address_line1" not in data:
                data["address_line1"] = data["addressLine1"]
            if "addressLine2" in data and "address_line2" not in data:
                data["address_line2"] = data["addressLine2"]
            if "postalCode" in data and "postal_code" not in data:
                data["postal_code"] = data["postalCode"]
            elif "pincode" in data and "postal_code" not in data:
                data["postal_code"] = data["pincode"]
        return data


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    store_id: UUID | None = Field(default=None, description="Fulfilling store location (defaults to active store)")
    shipping_address: ShippingAddressSchema
    billing_address: ShippingAddressSchema | None = None
    customer_name: str | None = Field(default=None, max_length=200)
    customer_email: str | None = Field(default=None, max_length=150)
    customer_phone: str | None = Field(default=None, max_length=50)
    payment_method: Literal["online", "cod", "upi", "card", "netbanking"] = "online"
    notes: str | None = Field(default=None, max_length=1000)
    coupon_code: str | None = Field(
        default=None, max_length=50, description="Optional promotional coupon code"
    )
    idempotency_key: str | None = Field(default=None, max_length=100)

    @model_validator(mode="before")
    @classmethod
    def populate_customer_details(cls, data):
        if isinstance(data, dict):
            s_addr = data.get("shipping_address")
            if hasattr(s_addr, "full_name"):
                if not data.get("customer_name"):
                    data["customer_name"] = getattr(s_addr, "full_name", None) or "Valued Customer"
                if not data.get("customer_phone"):
                    data["customer_phone"] = getattr(s_addr, "phone", None) or "+919876543210"
            elif isinstance(s_addr, dict):
                if not data.get("customer_name"):
                    data["customer_name"] = s_addr.get("full_name") or s_addr.get("recipient_name") or s_addr.get("fullName") or "Valued Customer"
                if not data.get("customer_phone"):
                    data["customer_phone"] = s_addr.get("phone") or s_addr.get("phoneNumber") or "+919876543210"
        return data


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
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

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
    shipping_address: dict | None = None
    billing_address: dict | None = None
    customer_name: str
    customer_email: str | None = None
    customer_phone: str
    notes: str | None = None
    items: list[OrderItemResponse]
    status_history: list[OrderStatusHistoryResponse]
    payments: list[PaymentTransactionResponse]
    created_at: datetime
    updated_at: datetime

    @computed_field
    def shippingAddress(self) -> dict | None:
        return self.shipping_address

    @computed_field
    def billingAddress(self) -> dict | None:
        return self.billing_address

    @computed_field
    def fulfillmentStatus(self) -> str:
        return self.fulfillment_status

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
    status: str = Field(..., description="Target fulfillment status")
    notes: str | None = Field(default=None, max_length=500)
    courierPartner: str | None = None
    courier_partner: str | None = None
    trackingNumber: str | None = None
    tracking_number: str | None = None
    cancellationReason: str | None = None
    cancellation_reason: str | None = None
    pickupSlot: str | None = None
    weightKg: float | None = None

    class Config:
        extra = "allow"


class OrderNotificationRequest(BaseModel):
    channel: str = Field(default="WHATSAPP", description="Notification channel: WHATSAPP, SMS, or EMAIL")
    custom_note: str | None = Field(default=None, max_length=1000)
    customNote: str | None = Field(default=None, max_length=1000)

    class Config:
        extra = "allow"


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

