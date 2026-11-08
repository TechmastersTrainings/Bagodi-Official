from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_permission
from app.core.tenant import TenantContext, get_current_tenant
from app.db.session import get_db
from app.modules.catalog.schemas import (
    BrandCreate,
    BrandResponse,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    ProductCreate,
    ProductDetailResponse,
    ProductImageCreate,
    ProductImageResponse,
    ProductUpdate,
    ProductVariantCreate,
    ProductVariantResponse,
    ProductVariantUpdate,
)
from app.modules.catalog.services import BrandService, CategoryService, ProductService

router = APIRouter(prefix="/merchant/catalog", tags=["Merchant Catalogue"])


# --- Categories ---
@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a merchant-specific category",
    dependencies=[Depends(require_permission("catalog.categories.create"))],
)
async def create_category(
    data: CategoryCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CategoryService.create_category(db, data, tenant_id=tenant.tenant_id)


@router.get(
    "/categories",
    response_model=list[CategoryResponse],
    summary="List all categories accessible to merchant (global + merchant-owned)",
    dependencies=[Depends(require_permission("catalog.categories.read"))],
)
async def list_categories(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CategoryService.list_categories(db, tenant_id=tenant.tenant_id, active_only=False)


@router.patch(
    "/categories/{category_id}",
    response_model=CategoryResponse,
    summary="Update a merchant-specific category",
    dependencies=[Depends(require_permission("catalog.categories.update"))],
)
async def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CategoryService.update_category(db, category_id, data, tenant_id=tenant.tenant_id)


# --- Brands ---
@router.post(
    "/brands",
    response_model=BrandResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a merchant-specific brand",
    dependencies=[Depends(require_permission("catalog.brands.create"))],
)
async def create_brand(
    data: BrandCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await BrandService.create_brand(db, data, tenant_id=tenant.tenant_id)


@router.get(
    "/brands",
    response_model=list[BrandResponse],
    summary="List all brands accessible to merchant (global + merchant-owned)",
    dependencies=[Depends(require_permission("catalog.brands.read"))],
)
async def list_brands(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await BrandService.list_brands(db, tenant_id=tenant.tenant_id, active_only=False)


# --- Products ---
@router.post(
    "/products",
    response_model=ProductDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product with optional variants and images",
    dependencies=[Depends(require_permission("catalog.products.create"))],
)
async def create_product(
    data: ProductCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProductService.create_product(db, tenant.tenant_id, data)


@router.get(
    "/products",
    response_model=list[ProductDetailResponse],
    summary="List all merchant products (draft, active, archived)",
    dependencies=[Depends(require_permission("catalog.products.read"))],
)
async def list_products(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
    category_id: Annotated[UUID | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await ProductService.list_merchant_products(
        db,
        tenant_id=tenant.tenant_id,
        category_id=category_id,
        status_filter=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/products/{product_id}",
    response_model=ProductDetailResponse,
    summary="Get merchant product details by ID",
    dependencies=[Depends(require_permission("catalog.products.read"))],
)
async def get_product(
    product_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProductService.get_merchant_product(db, tenant.tenant_id, product_id)


@router.patch(
    "/products/{product_id}",
    response_model=ProductDetailResponse,
    summary="Update product metadata and publication status",
    dependencies=[Depends(require_permission("catalog.products.update"))],
)
async def update_product(
    product_id: UUID,
    data: ProductUpdate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProductService.update_merchant_product(db, tenant.tenant_id, product_id, data)


# --- Variants ---
@router.post(
    "/products/{product_id}/variants",
    response_model=ProductVariantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a sellable variant to an existing product",
    dependencies=[Depends(require_permission("catalog.variants.create"))],
)
async def add_variant(
    product_id: UUID,
    data: ProductVariantCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProductService.add_variant(db, tenant.tenant_id, product_id, data)


@router.patch(
    "/variants/{variant_id}",
    response_model=ProductVariantResponse,
    summary="Update a variant's attributes, price, barcode, or status",
    dependencies=[Depends(require_permission("catalog.variants.update"))],
)
async def update_variant(
    variant_id: UUID,
    data: ProductVariantUpdate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProductService.update_variant(db, tenant.tenant_id, variant_id, data)


# --- Images ---
@router.post(
    "/products/{product_id}/images",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Attach an image to a product",
    dependencies=[Depends(require_permission("catalog.products.update"))],
)
async def add_image(
    product_id: UUID,
    data: ProductImageCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProductService.add_image(db, tenant.tenant_id, product_id, data)
