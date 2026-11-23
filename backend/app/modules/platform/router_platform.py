from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, get_security_principal, require_platform_admin
from app.db.session import get_db
from app.modules.platform.schemas import (
    MerchantInvoiceCreate,
    MerchantInvoicePayRequest,
    MerchantInvoiceResponse,
    MerchantSubscriptionResponse,
    OutboxItemResponse,
    PlatformAuditLogResponse,
    PlatformStaffCreate,
    PlatformStaffResponse,
    PlatformStaffUpdate,
    PlatformUserResponse,
    SubscriptionAssignRequest,
    SubscriptionPlanCreate,
    SubscriptionPlanResponse,
    SystemHealthResponse,
    TenantCreate,
    TenantKYCDocumentCreate,
    TenantKYCDocumentResponse,
    TenantKYCDocumentReview,
    TenantResponse,
    TenantStatusLogResponse,
    TenantStatusUpdate,
)
from app.modules.platform.services import (
    BillingService,
    KYCService,
    PlatformAuditService,
    PlatformStaffService,
    PlatformSystemService,
    TenantService,
)

router = APIRouter(
    prefix="/platform",
    tags=["Platform Governance & Super Admin"],
    dependencies=[Depends(require_platform_admin)],
)


# -----------------------------------------------------------------------------
# 1. Tenant Management & Onboarding
# -----------------------------------------------------------------------------
@router.post(
    "/tenants",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard a new merchant organization (Platform Admin)",
)
async def create_tenant(
    data: TenantCreate,
    request: Request,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    tenant = await TenantService.create_tenant(
        db,
        data,
        actor_id=principal.user_id,
        actor_email=str(principal.user_id),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return await TenantService.get_tenant_by_id(db, tenant.id)


@router.get(
    "/tenants",
    response_model=list[TenantResponse],
    summary="List all merchant organizations with enriched status and metrics",
)
async def list_tenants(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[str | None, Query(description="Filter by status: pending, active, suspended")] = None,
    search: Annotated[str | None, Query(description="Search by name, slug, legal name, or GSTIN")] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return await TenantService.list_tenants(
        db, skip=skip, limit=limit, status_filter=status, search=search
    )


@router.get(
    "/tenants/{tenant_id}",
    response_model=TenantResponse,
    summary="Get merchant organization details (Platform Admin)",
)
async def get_tenant(
    tenant_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await TenantService.get_tenant_by_id(db, tenant_id)


@router.patch(
    "/tenants/{tenant_id}/status",
    response_model=TenantResponse,
    summary="Update merchant organization status (activate, suspend, pend)",
)
async def update_tenant_status(
    tenant_id: UUID,
    data: TenantStatusUpdate,
    request: Request,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    await TenantService.update_tenant_status(
        db,
        tenant_id=tenant_id,
        new_status=data.status,
        reason=data.reason,
        actor_id=principal.user_id,
        actor_email=str(principal.user_id),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return await TenantService.get_tenant_by_id(db, tenant_id)


@router.get(
    "/tenants/{tenant_id}/lifecycle-logs",
    response_model=list[TenantStatusLogResponse],
    summary="Get merchant lifecycle status history and audit trail",
)
async def get_tenant_lifecycle_logs(
    tenant_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await TenantService.list_lifecycle_logs(db, tenant_id)


# -----------------------------------------------------------------------------
# 2. KYC Document Management
# -----------------------------------------------------------------------------
@router.get(
    "/tenants/{tenant_id}/kyc-documents",
    response_model=list[TenantKYCDocumentResponse],
    summary="List submitted KYC documents for a merchant",
)
async def list_kyc_documents(
    tenant_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await KYCService.list_documents(db, tenant_id)


@router.post(
    "/tenants/{tenant_id}/kyc-documents",
    response_model=TenantKYCDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit or upload a KYC verification document on behalf of a merchant",
)
async def upload_kyc_document(
    tenant_id: UUID,
    data: TenantKYCDocumentCreate,
    request: Request,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ip_address = request.client.host if request.client else None
    return await KYCService.add_document(
        db,
        tenant_id=tenant_id,
        data=data,
        actor_id=principal.user_id,
        actor_email=str(principal.user_id),
        ip_address=ip_address,
    )


@router.post(
    "/tenants/{tenant_id}/kyc-documents/{doc_id}/review",
    response_model=TenantKYCDocumentResponse,
    summary="Verify or reject a merchant KYC compliance document",
)
async def review_kyc_document(
    tenant_id: UUID,
    doc_id: UUID,
    data: TenantKYCDocumentReview,
    request: Request,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ip_address = request.client.host if request.client else None
    return await KYCService.review_document(
        db,
        tenant_id=tenant_id,
        doc_id=doc_id,
        review_data=data,
        actor_id=principal.user_id,
        actor_email=str(principal.user_id),
        ip_address=ip_address,
    )


# -----------------------------------------------------------------------------
# 3. Merchant Subscription Plans & Billing
# -----------------------------------------------------------------------------
@router.get(
    "/billing/plans",
    response_model=list[SubscriptionPlanResponse],
    summary="List active platform subscription tiers and plans",
)
async def list_subscription_plans(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await BillingService.list_plans(db)


@router.post(
    "/billing/plans",
    response_model=SubscriptionPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new merchant subscription pricing plan",
)
async def create_subscription_plan(
    data: SubscriptionPlanCreate,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await BillingService.create_plan(
        db, data, actor_id=principal.user_id, actor_email=str(principal.user_id)
    )


@router.get(
    "/billing/subscriptions",
    response_model=list[MerchantSubscriptionResponse],
    summary="List active merchant subscriptions across the platform",
)
async def list_subscriptions(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[UUID | None, Query()] = None,
):
    return await BillingService.list_subscriptions(db, tenant_id=tenant_id)


@router.post(
    "/billing/subscriptions/assign",
    response_model=MerchantSubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign or upgrade a merchant's active subscription tier",
)
async def assign_subscription(
    data: SubscriptionAssignRequest,
    tenant_id: Annotated[UUID, Query(description="Target tenant ID")],
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await BillingService.assign_subscription(
        db,
        tenant_id=tenant_id,
        plan_id=data.plan_id,
        auto_renew=data.auto_renew,
        actor_id=principal.user_id,
        actor_email=str(principal.user_id),
    )


@router.get(
    "/billing/invoices",
    response_model=list[MerchantInvoiceResponse],
    summary="List merchant SaaS subscription billing invoices",
)
async def list_merchant_invoices(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[UUID | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
):
    return await BillingService.list_invoices(db, tenant_id=tenant_id, status_filter=status)


@router.post(
    "/billing/invoices",
    response_model=MerchantInvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a subscription billing invoice for a merchant organization",
)
async def create_merchant_invoice(
    data: MerchantInvoiceCreate,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await BillingService.create_invoice(
        db, data, actor_id=principal.user_id, actor_email=str(principal.user_id)
    )


@router.patch(
    "/billing/invoices/{invoice_id}/pay",
    response_model=MerchantInvoiceResponse,
    summary="Record settlement / payment of a merchant subscription invoice",
)
async def pay_merchant_invoice(
    invoice_id: UUID,
    data: MerchantInvoicePayRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await BillingService.pay_invoice(
        db,
        invoice_id=invoice_id,
        payment_reference=data.payment_reference,
        actor_id=principal.user_id,
        actor_email=str(principal.user_id),
    )


# -----------------------------------------------------------------------------
# 4. Super Admin Staff & RBAC Delegation
# -----------------------------------------------------------------------------
@router.get(
    "/staff",
    response_model=list[PlatformStaffResponse],
    summary="List Super Admin and Platform Governance staff members",
)
async def list_platform_staff(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PlatformStaffService.list_staff(db)


@router.post(
    "/staff",
    response_model=PlatformStaffResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Delegate and create a new Super Admin staff account",
)
async def create_platform_staff(
    data: PlatformStaffCreate,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PlatformStaffService.create_staff(
        db, data, actor_id=principal.user_id, actor_email=str(principal.user_id)
    )


@router.patch(
    "/staff/{user_id}/status",
    response_model=PlatformStaffResponse,
    summary="Update platform staff status or assigned platform role",
)
async def update_platform_staff_status(
    user_id: UUID,
    data: PlatformStaffUpdate,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PlatformStaffService.update_staff_status(
        db,
        user_id=user_id,
        data=data,
        actor_id=principal.user_id,
        actor_email=str(principal.user_id),
    )


# -----------------------------------------------------------------------------
# 5. Global Administrative Audit Logs
# -----------------------------------------------------------------------------
@router.get(
    "/audit-logs",
    response_model=list[PlatformAuditLogResponse],
    summary="Query global administrative audit log and security events",
)
async def list_platform_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    action: Annotated[str | None, Query(description="Filter by action code")] = None,
    target_type: Annotated[str | None, Query(description="Filter by target type")] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return await PlatformAuditService.list_logs(
        db, skip=skip, limit=limit, action=action, target_type=target_type
    )


# -----------------------------------------------------------------------------
# 6. System Diagnostics & Outbox Monitoring
# -----------------------------------------------------------------------------
@router.get(
    "/system/health",
    response_model=SystemHealthResponse,
    summary="Detailed platform system diagnostics, connection pools & worker metrics",
)
async def get_system_diagnostics(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PlatformSystemService.get_system_health(db)


@router.get(
    "/system/outbox",
    response_model=list[OutboxItemResponse],
    summary="Monitor transactional notification outbox events across all tenants",
)
async def list_system_outbox(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[str | None, Query(description="Filter by status: pending, processed, failed")] = None,
    limit: int = Query(50, ge=1, le=100),
):
    return await PlatformSystemService.list_outbox_events(db, limit=limit, status_filter=status)


@router.post(
    "/system/outbox/process",
    summary="Manually trigger background worker for transactional outbox dispatch",
)
async def process_system_outbox(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PlatformSystemService.process_outbox_events(
        db, actor_id=principal.user_id, actor_email=str(principal.user_id)
    )


# -----------------------------------------------------------------------------
# 7. Platform User Management (Customers, Merchants, Staff, Admins)
# -----------------------------------------------------------------------------
@router.get(
    "/users",
    response_model=list[PlatformUserResponse],
    summary="List all platform users across customer, merchant, and admin roles",
)
async def list_platform_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    role_filter: Annotated[str | None, Query(description="Filter by role: CUSTOMER, MERCHANT, ADMIN")] = None,
    search: Annotated[str | None, Query(description="Search email, phone, name")] = None,
):
    from sqlalchemy import select, or_
    from app.modules.identity.models import User, UserRole, Role
    from app.modules.platform.models import Tenant

    stmt = select(User).order_by(User.created_at.desc())
    if search:
        s = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                User.email.ilike(s),
                User.phone_e164.ilike(s),
                User.display_name.ilike(s),
            )
        )

    users = (await db.execute(stmt)).scalars().all()
    result = []
    for u in users:
        ur_stmt = (
            select(Role.code, UserRole.tenant_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id == u.id)
        )
        user_roles_data = (await db.execute(ur_stmt)).all()
        roles = [r[0] for r in user_roles_data]
        tenant_id = None
        for r in user_roles_data:
            if r[1]:
                tenant_id = r[1]
                break

        tenant_name = None
        if tenant_id:
            t = (await db.execute(select(Tenant.name).where(Tenant.id == tenant_id))).scalar_one_or_none()
            if t:
                tenant_name = t

        # Filter by role category if requested
        if role_filter:
            rf = role_filter.upper()
            if rf == "CUSTOMER" and "CUSTOMER" not in roles:
                continue
            if rf == "MERCHANT" and not any(r in ("MERCHANT_OWNER", "STORE_MANAGER", "STAFF") for r in roles):
                continue
            if rf == "ADMIN" and not (u.is_platform_user or any(r == "SUPER_ADMIN" for r in roles)):
                continue

        result.append(
            PlatformUserResponse(
                id=u.id,
                phone_e164=u.phone_e164,
                email=u.email,
                display_name=u.display_name,
                status=u.status,
                is_platform_user=u.is_platform_user,
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                roles=roles,
                created_at=u.created_at,
            )
        )
    return result


@router.patch(
    "/users/{user_id}/status",
    response_model=PlatformUserResponse,
    summary="Update platform user status (active, suspended)",
)
async def update_platform_user_status(
    user_id: UUID,
    data: PlatformStaffUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from sqlalchemy import select
    from app.modules.identity.models import User, UserRole, Role
    from app.modules.platform.models import Tenant

    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "User not found."},
        )

    if data.status:
        user.status = data.status
        try:
            from app.modules.platform.services import PlatformAuditService
            audit_action = "USER_SUSPENDED" if data.status == "suspended" else "USER_ACTIVATED"
            await PlatformAuditService.log(
                db,
                action=audit_action,
                target_type="USER",
                target_id=str(user.id),
                actor_id=user.id,
                actor_email=user.email,
                details={
                    "user_id": str(user.id),
                    "email": user.email,
                    "phone": user.phone_e164,
                    "display_name": user.display_name,
                    "new_status": user.status,
                },
            )
        except Exception:
            pass

    if data.display_name:
        user.display_name = data.display_name
    await db.commit()
    await db.refresh(user)

    ur_stmt = (
        select(Role.code, UserRole.tenant_id)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == user.id)
    )
    user_roles_data = (await db.execute(ur_stmt)).all()
    roles = [r[0] for r in user_roles_data]
    tenant_id = None
    for r in user_roles_data:
        if r[1]:
            tenant_id = r[1]
            break

    tenant_name = None
    if tenant_id:
        t = (await db.execute(select(Tenant.name).where(Tenant.id == tenant_id))).scalar_one_or_none()
        if t:
            tenant_name = t

    return PlatformUserResponse(
        id=user.id,
        phone_e164=user.phone_e164,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        is_platform_user=user.is_platform_user,
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        roles=roles,
        created_at=user.created_at,
    )


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a platform user account",
)
async def delete_platform_user(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from sqlalchemy import select, delete
    from app.modules.identity.models import User, UserRole, UserSession
    from app.modules.platform.services import PlatformAuditService

    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        return

    # Record immutable audit event
    try:
        await PlatformAuditService.log(
            db,
            action="USER_DELETED",
            target_type="USER",
            target_id=str(user.id),
            actor_id=user.id,
            actor_email=user.email,
            details={
                "user_id": str(user.id),
                "email": user.email,
                "phone": user.phone_e164,
                "display_name": user.display_name,
                "status": "permanently_deleted",
            },
        )
    except Exception:
        pass

    # Delete foreign key references
    await db.execute(delete(UserRole).where(UserRole.user_id == user_id))
    await db.execute(delete(UserSession).where(UserSession.user_id == user_id))

    try:
        from app.modules.identity.models import CustomerAddress
        await db.execute(delete(CustomerAddress).where(CustomerAddress.customer_id == user_id))
    except Exception:
        pass

    try:
        from app.modules.orders.models import CartItem, Cart
        cart_ids = (await db.execute(select(Cart.id).where(Cart.customer_id == user_id))).scalars().all()
        if cart_ids:
            await db.execute(delete(CartItem).where(CartItem.cart_id.in_(cart_ids)))
            await db.execute(delete(Cart).where(Cart.id.in_(cart_ids)))
    except Exception:
        pass

    await db.delete(user)
    await db.commit()


@router.post(
    "/merchants/{tenant_id}/approve",
    response_model=TenantResponse,
    summary="Approve pending merchant application and activate store & user",
)
async def approve_merchant(
    tenant_id: UUID,
    request: Request,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    await TenantService.update_tenant_status(
        db,
        tenant_id=tenant_id,
        new_status="active",
        reason="Approved by Platform Administrator",
        actor_id=principal.user_id,
        actor_email=str(principal.user_id),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return await TenantService.get_tenant_by_id(db, tenant_id)
