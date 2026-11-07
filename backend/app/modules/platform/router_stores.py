from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_permission
from app.core.tenant import TenantContext, get_current_tenant
from app.db.session import get_db
from app.modules.platform.schemas import (
    StoreCreate,
    StoreResponse,
    StoreStatusUpdate,
)
from app.modules.platform.services import StoreService

router = APIRouter(
    prefix="/stores",
    tags=["Store Operations"],
)


@router.post(
    "",
    response_model=StoreResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new physical store under active merchant",
    dependencies=[Depends(require_permission("stores.create"))],
)
async def create_store(
    data: StoreCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await StoreService.create_store(db, tenant.tenant_id, data)


@router.get(
    "",
    response_model=list[StoreResponse],
    summary="List all stores for active merchant",
    dependencies=[Depends(require_permission("stores.read"))],
)
async def list_stores(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await StoreService.list_stores(db, tenant.tenant_id)


@router.get(
    "/{store_id}",
    response_model=StoreResponse,
    summary="Get store details for active merchant",
    dependencies=[Depends(require_permission("stores.read"))],
)
async def get_store(
    store_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await StoreService.get_store_by_id(db, tenant.tenant_id, store_id)


@router.patch(
    "/{store_id}/status",
    response_model=StoreResponse,
    summary="Update store status for active merchant",
    dependencies=[Depends(require_permission("stores.update"))],
)
async def update_store_status(
    store_id: UUID,
    data: StoreStatusUpdate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await StoreService.update_store_status(db, tenant.tenant_id, store_id, data.status)
