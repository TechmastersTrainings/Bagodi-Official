from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field


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
    sku: str | None = Field(default=None, max_length=80, pattern=r"^[a-zA-Z0-9_\-]+$")
    barcode: str | None = Field(default=None, max_length=100)
    name: str = Field(..., min_length=2, max_length=200)
    size: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=50)
    attributes: dict | None = Field(default=None)
    mrp: Decimal = Field(..., ge=0)
    base_price: Decimal = Field(..., ge=0)
    initial_stock: int = Field(default=0, ge=0, description="Initial stock units for this size")
    status: Literal["active", "inactive"] = Field(default="active")


class ProductVariantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    barcode: str | None = Field(default=None, max_length=100)
    size: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=50)
    attributes: dict | None = Field(default=None)
    mrp: Decimal | None = Field(default=None, ge=0)
    base_price: Decimal | None = Field(default=None, ge=0)
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
    def sellingPrice(self) -> Decimal:
        return self.base_price

    @computed_field
    @property
    def availableStock(self) -> int:
        return self.available_qty

    @computed_field
    @property
    def colorName(self) -> str:
        return self.color or "Standard"


class ProductImageCreate(BaseModel):
    url: str = Field(..., max_length=1000)
    alt_text: str | None = Field(default=None, max_length=255)
    variant_id: UUID | None = Field(default=None)
    sort_order: int = Field(default=0)
    is_primary: bool = Field(default=False)


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


class ProductCreate(BaseModel):
    category_id: UUID
    brand_id: UUID | None = Field(default=None)
    name: str = Field(..., min_length=2, max_length=250)
    slug: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    status: Literal["draft", "active", "archived"] = Field(default="draft")
    is_published: bool = Field(default=False)
    variants: list[ProductVariantCreate] = Field(default_factory=list)
    images: list[ProductImageCreate] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    category_id: UUID | None = Field(default=None)
    brand_id: UUID | None = Field(default=None)
    name: str | None = Field(default=None, min_length=2, max_length=250)
    description: str | None = Field(default=None, max_length=2000)
    status: Literal["draft", "active", "archived"] | None = Field(default=None)
    is_published: bool | None = Field(default=None)


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
    def basePrice(self) -> Decimal:
        if self.variants:
            return self.variants[0].base_price
        return Decimal(0)

    @computed_field
    @property
    def isActive(self) -> bool:
        return self.status == "active"


class BarcodeLookupResponse(BaseModel):
    variant: ProductVariantResponse
    product: ProductDetailResponse
