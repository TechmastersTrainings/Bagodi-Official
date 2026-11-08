from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.catalog.schemas import (
    BrandResponse,
    CategoryResponse,
    ProductDetailResponse,
)
from app.modules.catalog.services import BrandService, CategoryService, ProductService

router = APIRouter(prefix="/catalog", tags=["Customer Catalogue"])


@router.get(
    "/categories",
    response_model=list[CategoryResponse],
    summary="List active categories for customer browsing",
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
async def list_public_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[
        UUID | None, Query(description="Filter products by merchant organization")
    ] = None,
    category_id: Annotated[
        UUID | None, Query(description="Filter products by category")
    ] = None,
    search: Annotated[
        str | None, Query(description="Search products by title or keyword")
    ] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await ProductService.list_public_products(
        db,
        tenant_id=tenant_id,
        category_id=category_id,
        search=search,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/products/{slug}",
    response_model=ProductDetailResponse,
    summary="Get live published product details by slug",
)
async def get_public_product(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[
        UUID | None, Query(description="Optional merchant context")
    ] = None,
):
    return await ProductService.get_public_product_by_slug(db, slug=slug, tenant_id=tenant_id)
