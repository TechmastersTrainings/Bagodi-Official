from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_platform_admin
from app.db.session import get_db
from app.modules.platform.schemas import (
    TenantCreate,
    TenantResponse,
    TenantStatusUpdate,
)
from app.modules.platform.services import TenantService

router = APIRouter(
    prefix="/platform/tenants",
    tags=["Platform Governance"],
    dependencies=[Depends(require_platform_admin)],
)


@router.post(
    "",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard a new merchant organization (Platform Admin)",
)
async def create_tenant(
    data: TenantCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await TenantService.create_tenant(db, data)


@router.get(
    "",
    response_model=list[TenantResponse],
    summary="List all merchant organizations (Platform Admin)",
)
async def list_tenants(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return await TenantService.list_tenants(db, skip=skip, limit=limit)


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Get merchant organization details (Platform Admin)",
)
async def get_tenant(
    tenant_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await TenantService.get_tenant_by_id(db, tenant_id)


@router.patch(
    "/{tenant_id}/status",
    response_model=TenantResponse,
    summary="Update merchant organization status (Platform Admin)",
)
async def update_tenant_status(
    tenant_id: UUID,
    data: TenantStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await TenantService.update_tenant_status(db, tenant_id, data.status)

