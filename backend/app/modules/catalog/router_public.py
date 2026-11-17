from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.catalog.models import Brand, Category
from app.modules.catalog.schemas import (
    BrandResponse,
    CategoryResponse,
    ProductDetailResponse,
)
from app.modules.catalog.services import BrandService, CategoryService, ProductService

router = APIRouter(prefix="/catalog", tags=["Customer Catalogue"])
storefront_router = APIRouter(tags=["Storefront Public"])


@router.get(
    "/categories",
    response_model=list[CategoryResponse],
    summary="List active categories for customer browsing",
)
@storefront_router.get(
    "/categories",
    response_model=list[CategoryResponse],
    summary="List active categories for customer storefront",
)
async def list_public_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[UUID | None, Query(description="Optional merchant filter")] = None,
):
    return await CategoryService.list_categories(db, tenant_id=tenant_id, active_only=True)


@router.get(
    "/brands",
    response_model=list[BrandResponse],
    summary="List active brands for customer browsing",
)
@storefront_router.get(
    "/brands",
    response_model=list[BrandResponse],
    summary="List active brands for customer storefront",
)
async def list_public_brands(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[UUID | None, Query(description="Optional merchant filter")] = None,
):
    return await BrandService.list_brands(db, tenant_id=tenant_id, active_only=True)


@router.get(
    "/products",
    response_model=list[ProductDetailResponse],
    summary="Browse and search live published products",
)
@storefront_router.get(
    "/products",
    response_model=list[ProductDetailResponse],
    summary="Browse and search live published storefront products",
)
async def list_public_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[
        UUID | None, Query(description="Filter products by merchant organization")
    ] = None,
    category: Annotated[str | None, Query(description="Filter by category slug or ID")] = None,
    category_id: Annotated[str | None, Query(description="Filter by category ID")] = None,
    categoryId: Annotated[str | None, Query(description="Filter by category ID (frontend alias)")] = None,
    brand: Annotated[str | None, Query(description="Filter by brand slug or ID")] = None,
    brand_id: Annotated[str | None, Query(description="Filter by brand ID")] = None,
    brandId: Annotated[str | None, Query(description="Filter by brand ID (frontend alias)")] = None,
    search: Annotated[str | None, Query(description="Search products by title or keyword")] = None,
    page: Annotated[int | None, Query(ge=1, description="1-based page number")] = None,
    pageSize: Annotated[int | None, Query(ge=1, le=100, description="Items per page")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    sortBy: Annotated[str | None, Query(description="Sorting option")] = None,
    sizes: Annotated[str | None, Query(description="Size filters")] = None,
    minPrice: Annotated[float | None, Query(description="Minimum price")] = None,
    maxPrice: Annotated[float | None, Query(description="Maximum price")] = None,
    inStockOnly: Annotated[bool | None, Query(description="Only in stock items")] = None,
):
    # Resolve category filter (support UUID or slug e.g. 'sarees', 'mens-wear')
    resolved_category_id: UUID | None = None
    raw_cat = category or category_id or categoryId
    if raw_cat and raw_cat.strip() and raw_cat.strip().upper() != "ALL":
        try:
            resolved_category_id = UUID(raw_cat.strip())
        except (ValueError, TypeError):
            cat_stmt = select(Category).where(Category.slug == raw_cat.strip().lower())
            found_cat = (await db.execute(cat_stmt)).scalar_one_or_none()
            if found_cat:
                resolved_category_id = found_cat.id

    # Resolve brand filter (support UUID or slug e.g. 'raymond', 'bagodi-atelier')
    resolved_brand_id: UUID | None = None
    raw_brand = brand or brand_id or brandId
    if raw_brand and raw_brand.strip() and raw_brand.strip().upper() != "ALL":
        try:
            resolved_brand_id = UUID(raw_brand.strip())
        except (ValueError, TypeError):
            brand_stmt = select(Brand).where(Brand.slug == raw_brand.strip().lower())
            found_brand = (await db.execute(brand_stmt)).scalar_one_or_none()
            if found_brand:
                resolved_brand_id = found_brand.id

    # Calculate effective pagination
    effective_limit = pageSize or limit
    effective_skip = skip
    if page and page > 1 and skip == 0:
        effective_skip = (page - 1) * effective_limit

    return await ProductService.list_public_products(
        db,
        tenant_id=tenant_id,
        category_id=resolved_category_id,
        brand_id=resolved_brand_id,
        search=search,
        skip=effective_skip,
        limit=effective_limit,
    )


@router.get(
    "/products/{slug}",
    response_model=ProductDetailResponse,
    summary="Get live published product details by slug",
)
@storefront_router.get(
    "/products/{slug}",
    response_model=ProductDetailResponse,
    summary="Get live published storefront product details by slug or ID",
)
async def get_public_product(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[UUID | None, Query(description="Optional merchant context")] = None,
):
    return await ProductService.get_public_product_by_slug(db, slug=slug, tenant_id=tenant_id)
