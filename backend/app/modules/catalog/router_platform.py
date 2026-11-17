from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import require_platform_admin
from app.db.session import get_db
from app.modules.catalog.models import Product
from app.modules.catalog.schemas import (
    BrandCreate,
    BrandResponse,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    ProductCreate,
    ProductDetailResponse,
    ProductUpdate,
)
from app.modules.catalog.services import BrandService, CategoryService, ProductService

router = APIRouter(
    prefix="/platform/catalog",
    tags=["Platform Catalogue Governance"],
    dependencies=[Depends(require_platform_admin)],
)


# --- Platform Master Categories ---
@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a global platform-wide category (Platform Admin)",
)
async def create_global_category(
    data: CategoryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CategoryService.create_category(db, data, tenant_id=None)


@router.get(
    "/categories",
    response_model=list[CategoryResponse],
    summary="List all global platform-wide categories (Platform Admin)",
)
async def list_global_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CategoryService.list_categories(db, tenant_id=None, active_only=False)


@router.patch(
    "/categories/{category_id}",
    response_model=CategoryResponse,
    summary="Update a global platform category (Platform Admin)",
)
async def update_global_category(
    category_id: UUID,
    data: CategoryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CategoryService.update_category(db, category_id, data, tenant_id=None)


# --- Platform Master Brands ---
@router.post(
    "/brands",
    response_model=BrandResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a global platform-wide brand (Platform Admin)",
)
async def create_global_brand(
    data: BrandCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await BrandService.create_brand(db, data, tenant_id=None)


@router.get(
    "/brands",
    response_model=list[BrandResponse],
    summary="List all global platform-wide brands (Platform Admin)",
)
async def list_global_brands(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await BrandService.list_brands(db, tenant_id=None, active_only=False)


# --- Platform Master Products ---
@router.get(
    "/products",
    response_model=list[ProductDetailResponse],
    summary="List all products across the platform (Platform Admin)",
)
async def list_platform_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    category_id: UUID | None = None,
    brand_id: UUID | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
):
    stmt = (
        select(Product)
        .options(
            selectinload(Product.variants),
            selectinload(Product.images),
            selectinload(Product.category),
            selectinload(Product.brand),
        )
    )
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if brand_id:
        stmt = stmt.where(Product.brand_id == brand_id)
    if search:
        stmt = stmt.where(Product.name.ilike(f"%{search.strip()}%"))

    stmt = stmt.order_by(Product.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    products = list(result.scalars().all())
    await ProductService._attach_stock_balances(db, products)
    return products


@router.post(
    "/products",
    response_model=ProductDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an apparel product as platform administrator",
)
async def create_platform_product(
    data: ProductCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: UUID | None = None,
):
    effective_tenant_id = tenant_id or UUID("11111111-1111-1111-1111-111111111111")
    return await ProductService.create_product(db, effective_tenant_id, data)


@router.patch(
    "/products/{product_id}",
    response_model=ProductDetailResponse,
    summary="Update an apparel product as platform administrator",
)
async def update_platform_product(
    product_id: UUID,
    data: ProductUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = (
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.variants),
            selectinload(Product.images),
            selectinload(Product.category),
            selectinload(Product.brand),
        )
    )
    product = (await db.execute(stmt)).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if data.name is not None:
        product.name = data.name
    if data.description is not None:
        product.description = data.description
    if data.category_id is not None:
        product.category_id = data.category_id
    if data.brand_id is not None:
        product.brand_id = data.brand_id
    if data.status is not None:
        product.status = data.status
    if data.is_published is not None:
        product.is_published = data.is_published
    await db.commit()
    await db.refresh(product)
    await ProductService._attach_stock_balances(db, [product])
    return product


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an apparel product platform-wide",
)
async def delete_platform_product(
    product_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    prod = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if prod:
        await ProductService.delete_merchant_product(db, prod.tenant_id, product_id)
