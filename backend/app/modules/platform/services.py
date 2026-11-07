from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.models import Store, Tenant
from app.modules.platform.schemas import StoreCreate, TenantCreate


class TenantService:
    @staticmethod
    async def create_tenant(db: AsyncSession, data: TenantCreate) -> Tenant:
        stmt = select(Tenant).where(Tenant.slug == data.slug)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "TENANT_SLUG_EXISTS", "message": f"Tenant slug '{data.slug}' already exists."},
            )

        tenant = Tenant(
            name=data.name,
            slug=data.slug,
            status="pending",
            legal_name=data.legal_name,
            contact_email=data.contact_email,
            contact_phone=data.contact_phone,
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        return tenant

    @staticmethod
    async def list_tenants(db: AsyncSession, skip: int = 0, limit: int = 50) -> list[Tenant]:
        stmt = select(Tenant).order_by(Tenant.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_tenant_by_id(db: AsyncSession, tenant_id: UUID) -> Tenant:
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        tenant = (await db.execute(stmt)).scalar_one_or_none()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "TENANT_NOT_FOUND", "message": "Tenant not found."},
            )
        return tenant

    @staticmethod
    async def update_tenant_status(db: AsyncSession, tenant_id: UUID, new_status: str) -> Tenant:
        tenant = await TenantService.get_tenant_by_id(db, tenant_id)
        tenant.status = new_status
        await db.commit()
        await db.refresh(tenant)
        return tenant


class StoreService:
    @staticmethod
    async def create_store(db: AsyncSession, tenant_id: UUID, data: StoreCreate) -> Store:
        stmt = select(Store).where(Store.tenant_id == tenant_id, Store.code == data.code)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "STORE_CODE_EXISTS",
                    "message": f"Store code '{data.code}' already exists for this merchant.",
                },
            )

        store = Store(
            tenant_id=tenant_id,
            name=data.name,
            code=data.code,
            status="active",
            address_line=data.address_line,
            city=data.city,
            state=data.state,
            postal_code=data.postal_code,
            phone=data.phone,
        )
        db.add(store)
        await db.commit()
        await db.refresh(store)
        return store

    @staticmethod
    async def list_stores(db: AsyncSession, tenant_id: UUID) -> list[Store]:
        stmt = select(Store).where(Store.tenant_id == tenant_id).order_by(Store.name.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_store_by_id(db: AsyncSession, tenant_id: UUID, store_id: UUID) -> Store:
        stmt = select(Store).where(Store.tenant_id == tenant_id, Store.id == store_id)
        store = (await db.execute(stmt)).scalar_one_or_none()
        if not store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "STORE_NOT_FOUND", "message": "Store not found for this merchant."},
            )
        return store

    @staticmethod
    async def update_store_status(
        db: AsyncSession, tenant_id: UUID, store_id: UUID, new_status: str
    ) -> Store:
        store = await StoreService.get_store_by_id(db, tenant_id, store_id)
        store.status = new_status
        await db.commit()
        await db.refresh(store)
        return store
