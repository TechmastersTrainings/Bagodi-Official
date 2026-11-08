from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, get_security_principal
from app.db.session import get_db
from app.modules.platform.models import Tenant


@dataclass(frozen=True)
class TenantContext:
    tenant_id: UUID
    name: str
    slug: str
    status: str


async def get_current_tenant(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TenantContext:
    """Resolve and enforce the merchant tenant context from the server-authenticated principal.

    Never trusts client-supplied tenant identifiers in URL query params or request bodies.
    """
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TENANT_CONTEXT_REQUIRED",
                "message": "Tenant context is required for this merchant operation.",
            },
        )

    stmt = select(Tenant).where(Tenant.id == principal.tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TENANT_NOT_FOUND", "message": "Tenant not found."},
        )

    if tenant.status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "TENANT_SUSPENDED", "message": "Merchant organization is suspended."},
        )

    if tenant.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TENANT_NOT_ACTIVE",
                "message": f"Merchant organization is {tenant.status} and cannot process operations.",
            },
        )

    return TenantContext(
        tenant_id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        status=tenant.status,
    )


def scoped_query(stmt: Select, model, tenant: TenantContext) -> Select:
    """Ensure every tenant-owned model query is strictly scoped to the authenticated tenant."""
    return stmt.where(model.tenant_id == tenant.tenant_id)
