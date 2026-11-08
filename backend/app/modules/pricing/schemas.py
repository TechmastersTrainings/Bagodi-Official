from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

PromotionType = Literal["PERCENTAGE", "FIXED_AMOUNT"]
PromotionScope = Literal["VARIANT", "PRODUCT", "CATEGORY", "CART"]
PromotionStatus = Literal["active", "inactive", "archived"]

CouponDiscountType = Literal["PERCENTAGE", "FIXED_AMOUNT"]
CouponStatus = Literal["active", "inactive", "expired"]


# --- Promotion Schemas ---


class PromotionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, description="Campaign title")
    description: str | None = Field(default=None, description="Promotion details and T&Cs")
    promotion_type: PromotionType = Field(..., description="PERCENTAGE or FIXED_AMOUNT")
    scope: PromotionScope = Field(..., description="VARIANT, PRODUCT, CATEGORY, or CART")
    target_id: UUID | None = Field(default=None, description="Target entity ID; NULL for CART scope")
    discount_value: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2, description="Discount rate or amount")
    max_discount_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2, description="Cap on percentage discounts")
    min_order_amount: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2, description="Minimum qualifying spend")
    start_date: datetime = Field(..., description="Effective start timestamp")
    end_date: datetime | None = Field(default=None, description="Effective end timestamp (NULL for open-ended)")
    status: PromotionStatus = Field(default="active", description="active, inactive, or archived")
    priority: int = Field(default=0, description="Precedence priority; higher number takes precedence")
    is_stackable: bool = Field(default=False, description="Whether this promotion combines with other promotions/coupons")

    @field_validator("target_id")
    @classmethod
    def validate_target_id(cls, v: UUID | None, info) -> UUID | None:
        scope = info.data.get("scope")
        if scope and scope != "CART" and v is None:
            raise ValueError(f"target_id is required when scope is '{scope}'.")
        return v


class PromotionCreate(PromotionBase):
    pass


class PromotionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    discount_value: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    max_discount_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    min_order_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: PromotionStatus | None = None
    priority: int | None = None
    is_stackable: bool | None = None


class PromotionResponse(PromotionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime


# --- Coupon Schemas ---


class CouponBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=50, description="Alphanumeric coupon code")
    name: str = Field(..., min_length=1, max_length=150, description="Campaign title")
    description: str | None = Field(default=None, description="Terms and conditions")
    discount_type: CouponDiscountType = Field(..., description="PERCENTAGE or FIXED_AMOUNT")
    discount_value: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2, description="Discount rate or amount")
    max_discount_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2, description="Max monetary cap for percentage discount")
    min_order_amount: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2, description="Minimum order subtotal")
    start_date: datetime = Field(..., description="Effective start date")
    end_date: datetime = Field(..., description="Effective expiry date")
    status: CouponStatus = Field(default="active", description="active, inactive, or expired")
    total_usage_limit: int | None = Field(default=None, gt=0, description="Overall max redemptions (NULL for unlimited)")
    usage_limit_per_customer: int = Field(default=1, gt=0, description="Max redemptions per customer")
    is_stackable: bool = Field(default=False, description="Whether coupon stacks with other promotions")

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper()


class CouponCreate(CouponBase):
    pass


class CouponUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    discount_value: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    max_discount_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    min_order_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: CouponStatus | None = None
    total_usage_limit: int | None = Field(default=None, gt=0)
    usage_limit_per_customer: int | None = Field(default=None, gt=0)
    is_stackable: bool | None = None


class CouponResponse(CouponBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    total_redeemed_count: int
    created_at: datetime
    updated_at: datetime


# --- Calculation, Quote, and Breakdown Schemas ---


class AppliedPromotionDetail(BaseModel):
    promotion_id: UUID
    title: str
    scope: str
    discount_amount: Decimal


class AppliedCouponDetail(BaseModel):
    coupon_id: UUID
    code: str
    name: str
    discount_amount: Decimal


class DiscountBreakdown(BaseModel):
    item_discounts_total: Decimal = Decimal("0.00")
    cart_discount_total: Decimal = Decimal("0.00")
    coupon_discount_total: Decimal = Decimal("0.00")
    promotions_applied: list[AppliedPromotionDetail] = Field(default_factory=list)
    coupon_applied: AppliedCouponDetail | None = None


class PriceQuoteItem(BaseModel):
    variant_id: UUID
    sku: str
    product_name: str
    variant_name: str
    quantity: int
    original_unit_price: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    line_total: Decimal
    applied_promotion: AppliedPromotionDetail | None = None


class PriceQuoteResponse(BaseModel):
    subtotal: Decimal
    item_discount: Decimal
    cart_discount: Decimal
    coupon_discount: Decimal
    total_discount: Decimal
    shipping_fee: Decimal
    total_amount: Decimal
    items: list[PriceQuoteItem]
    discount_breakdown: DiscountBreakdown
    coupon_code: str | None = None


class CartCouponApplyRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="Coupon code to apply to cart")

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper()


# --- Pricing Audit Log Schema ---


class PricingAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    changed_by_user_id: UUID | None
    changes: dict
    created_at: datetime
