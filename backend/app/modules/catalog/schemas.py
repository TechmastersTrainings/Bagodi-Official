from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    parent_id: UUID | None = Field(default=None)
    description: str | None = Field(default=None, max_length=500)
    sort_order: int = Field(default=0)
    is_active: bool = Field(default=True)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    parent_id: UUID | None = Field(default=None)
    description: str | None = Field(default=None, max_length=500)
    sort_order: int | None = Field(default=None)
    is_active: bool | None = Field(default=None)


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None
    parent_id: UUID | None
    name: str
    slug: str
    description: str | None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BrandCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = Field(default=True)


class BrandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = Field(default=None)


class BrandResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None
    name: str
    slug: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductVariantCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    sku: str | None = Field(default=None, max_length=80, pattern=r"^[a-zA-Z0-9_\-]+$")
    barcode: str | None = Field(default=None, max_length=100)
    name: str = Field(default="Standard", min_length=1, max_length=200)
    size: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=50, alias="colorName")
    attributes: dict | None = Field(default=None)
    mrp: Decimal | None = Field(default=None, ge=0)
    base_price: Decimal | None = Field(default=None, ge=0, alias="sellingPrice")
    initial_stock: int = Field(default=0, ge=0, alias="initialStock")
    status: Literal["active", "inactive"] = Field(default="active")


class ProductVariantUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    barcode: str | None = Field(default=None, max_length=100)
    size: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=50, alias="colorName")
    attributes: dict | None = Field(default=None)
    mrp: Decimal | None = Field(default=None, ge=0)
    base_price: Decimal | None = Field(default=None, ge=0, alias="sellingPrice")
    status: Literal["active", "inactive"] | None = Field(default=None)


class ProductVariantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    product_id: UUID
    sku: str
    barcode: str | None
    name: str
    size: str | None
    color: str | None
    attributes: dict | None
    mrp: Decimal
    base_price: Decimal
    status: str
    available_qty: int = 0
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def sellingPrice(self) -> float:
        return float(self.base_price)

    @computed_field
    @property
    def basePrice(self) -> float:
        return float(self.base_price)

    @computed_field
    @property
    def mrpAmount(self) -> float:
        return float(self.mrp)

    @computed_field
    @property
    def availableStock(self) -> int:
        return self.available_qty

    @computed_field
    @property
    def colorName(self) -> str:
        return self.color or "Standard"

    @computed_field
    @property
    def isActive(self) -> bool:
        return self.status == "active"


class ProductImageCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    url: str = Field(...)
    alt_text: str | None = Field(default=None, max_length=255, alias="altText")
    variant_id: UUID | None = Field(default=None, alias="variantId")
    sort_order: int = Field(default=0, alias="displayOrder")
    is_primary: bool = Field(default=False, alias="isPrimary")


class ProductImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    variant_id: UUID | None
    url: str
    alt_text: str | None
    sort_order: int
    is_primary: bool
    created_at: datetime

    @computed_field
    @property
    def isPrimary(self) -> bool:
        return self.is_primary

    @computed_field
    @property
    def displayOrder(self) -> int:
        return self.sort_order

    @computed_field
    @property
    def altText(self) -> str | None:
        return self.alt_text


class ProductCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    category_id: UUID = Field(..., alias="categoryId")
    brand_id: UUID | None = Field(default=None, alias="brandId")
    name: str = Field(..., min_length=2, max_length=250)
    slug: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    base_price: Decimal | None = Field(default=None, alias="basePrice")
    status: Literal["draft", "active", "archived"] = Field(default="draft")
    is_published: bool = Field(default=True, alias="isPublished")
    variants: list[ProductVariantCreate] = Field(default_factory=list)
    sizes: list[str] | None = Field(default=None)
    size: str | None = Field(default=None)
    images: list[ProductImageCreate] = Field(default_factory=list)

    @field_validator("brand_id", mode="before")
    @classmethod
    def clean_brand_id(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v


class ProductUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    category_id: UUID | None = Field(default=None, alias="categoryId")
    brand_id: UUID | None = Field(default=None, alias="brandId")
    name: str | None = Field(default=None, min_length=2, max_length=250)
    description: str | None = Field(default=None, max_length=2000)
    base_price: Decimal | None = Field(default=None, alias="basePrice")
    status: Literal["draft", "active", "archived"] | None = Field(default=None)
    is_published: bool | None = Field(default=None, alias="isPublished")
    sizes: list[str] | None = Field(default=None)
    size: str | None = Field(default=None)
    images: list[ProductImageCreate] | None = Field(default=None)

    @field_validator("brand_id", mode="before")
    @classmethod
    def clean_brand_id(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v


class ProductDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    category_id: UUID
    brand_id: UUID | None
    category: CategoryResponse | None = None
    brand: BrandResponse | None = None
    name: str
    slug: str
    description: str | None
    status: str
    is_published: bool
    variants: list[ProductVariantResponse] = Field(default_factory=list)
    images: list[ProductImageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def basePrice(self) -> float:
        if self.variants:
            return float(self.variants[0].base_price)
        return 0.0

    @computed_field
    @property
    def isActive(self) -> bool:
        return self.status == "active" and self.is_published

    @computed_field
    @property
    def isArchived(self) -> bool:
        return self.status == "archived"

    @computed_field
    @property
    def currency(self) -> str:
        return "INR"

    @computed_field
    @property
    def categoryId(self) -> UUID:
        return self.category_id

    @computed_field
    @property
    def brandId(self) -> UUID | None:
        return self.brand_id

    @computed_field
    @property
    def isFeatured(self) -> bool:
        return True

    @computed_field
    @property
    def returnEligible(self) -> bool:
        return True

    @computed_field
    @property
    def exchangeEligible(self) -> bool:
        return True

    @computed_field
    @property
    def returnWindowDays(self) -> int:
        return 7


class BarcodeLookupResponse(BaseModel):
    variant: ProductVariantResponse
    product: ProductDetailResponse
