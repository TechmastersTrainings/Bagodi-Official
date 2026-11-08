from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, require_permission
from app.core.tenant import TenantContext, get_current_tenant
from app.db.session import get_db
from app.modules.pricing.models import PricingAuditLog
from app.modules.pricing.schemas import (
    CouponCreate,
    CouponResponse,
    CouponUpdate,
    PricingAuditLogResponse,
    PromotionCreate,
    PromotionResponse,
    PromotionUpdate,
)
from app.modules.pricing.services import CouponService, PromotionService

router = APIRouter(prefix="/merchant/pricing", tags=["Merchant Pricing & Promotions"])


# --- Promotions Endpoints ---


@router.post(
    "/promotions",
    response_model=PromotionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new promotional discount rule",
)
async def create_promotion(
    data: PromotionCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(require_permission("pricing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PromotionService.create_promotion(
        db, tenant_id=tenant.tenant_id, data=data, user_id=principal.user_id
    )


@router.get(
    "/promotions",
    response_model=list[PromotionResponse],
    summary="List merchant promotional discount rules",
)
async def list_promotions(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    _: Annotated[SecurityPrincipal, Depends(require_permission("pricing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[
        str | None, Query(description="Filter by status: active, inactive, archived")
    ] = None,
    scope: Annotated[
        str | None, Query(description="Filter by scope: VARIANT, PRODUCT, CATEGORY, CART")
    ] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await PromotionService.list_promotions(
        db, tenant_id=tenant.tenant_id, status=status, scope=scope, skip=skip, limit=limit
    )


@router.get(
    "/promotions/{promotion_id}",
    response_model=PromotionResponse,
    summary="Get promotion rule details",
)
async def get_promotion(
    promotion_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    _: Annotated[SecurityPrincipal, Depends(require_permission("pricing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PromotionService.get_promotion(
        db, tenant_id=tenant.tenant_id, promotion_id=promotion_id
    )


@router.patch(
    "/promotions/{promotion_id}",
    response_model=PromotionResponse,
    summary="Update promotion rule",
)
async def update_promotion(
    promotion_id: UUID,
    data: PromotionUpdate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(require_permission("pricing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PromotionService.update_promotion(
        db,
        tenant_id=tenant.tenant_id,
        promotion_id=promotion_id,
        data=data,
        user_id=principal.user_id,
    )


@router.delete(
    "/promotions/{promotion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive promotional discount rule",
)
async def delete_promotion(
    promotion_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(require_permission("pricing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await PromotionService.delete_promotion(
        db, tenant_id=tenant.tenant_id, promotion_id=promotion_id, user_id=principal.user_id
    )


# --- Coupons Endpoints ---


@router.post(
    "/coupons",
    response_model=CouponResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new merchant coupon code",
)
async def create_coupon(
    data: CouponCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(require_permission("pricing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CouponService.create_coupon(
        db, tenant_id=tenant.tenant_id, data=data, user_id=principal.user_id
    )


@router.get(
    "/coupons",
    response_model=list[CouponResponse],
    summary="List merchant coupon campaigns",
)
async def list_coupons(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    _: Annotated[SecurityPrincipal, Depends(require_permission("pricing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[str | None, Query(description="Filter by status")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await CouponService.list_coupons(
        db, tenant_id=tenant.tenant_id, status=status, skip=skip, limit=limit
    )


@router.get(
    "/coupons/{coupon_id}",
    response_model=CouponResponse,
    summary="Get coupon campaign details",
)
async def get_coupon(
    coupon_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    _: Annotated[SecurityPrincipal, Depends(require_permission("pricing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CouponService.get_coupon(db, tenant_id=tenant.tenant_id, coupon_id=coupon_id)


@router.patch(
    "/coupons/{coupon_id}",
    response_model=CouponResponse,
    summary="Update coupon campaign",
)
async def update_coupon(
    coupon_id: UUID,
    data: CouponUpdate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(require_permission("pricing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CouponService.update_coupon(
        db, tenant_id=tenant.tenant_id, coupon_id=coupon_id, data=data, user_id=principal.user_id
    )


@router.delete(
    "/coupons/{coupon_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Expire coupon campaign",
)
async def delete_coupon(
    coupon_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(require_permission("pricing.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await CouponService.delete_coupon(
        db, tenant_id=tenant.tenant_id, coupon_id=coupon_id, user_id=principal.user_id
    )


# --- Pricing Audit Logs ---


@router.get(
    "/audit-logs",
    response_model=list[PricingAuditLogResponse],
    summary="View pricing, promotion, and coupon audit history",
)
async def list_pricing_audit_logs(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    _: Annotated[SecurityPrincipal, Depends(require_permission("pricing.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    entity_type: Annotated[str | None, Query(description="Filter by promotion or coupon")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    stmt = select(PricingAuditLog).where(PricingAuditLog.tenant_id == tenant.tenant_id)
    if entity_type:
        stmt = stmt.where(PricingAuditLog.entity_type == entity_type)
    stmt = stmt.order_by(PricingAuditLog.created_at.desc()).offset(skip).limit(limit)
    return list((await db.execute(stmt)).scalars().all())
