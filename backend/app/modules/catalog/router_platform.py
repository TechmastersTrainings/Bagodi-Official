from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_platform_admin
from app.db.session import get_db
from app.modules.catalog.schemas import (
    BrandCreate,
    BrandResponse,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
)
from app.modules.catalog.services import BrandService, CategoryService

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
