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


async def purge_user_completely(db: AsyncSession, user_id: UUID) -> bool:
    from sqlalchemy import select, delete, update
    from app.core.storage import storage
    from app.modules.identity.models import User, UserRole, UserSession, CustomerAddress
    from app.modules.orders.models import Order, OrderItem, Cart, CartItem, OrderReturnRequest, PaymentTransaction
    from app.modules.pricing.models import CouponRedemption
    from app.modules.delivery.models import Shipment, ShipmentItem, DeliveryTrackingEvent, ProofOfDelivery, DeliveryPersonnel
    from app.modules.platform.models import PlatformAuditLog

    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        return False

    # Never delete protected master administrative accounts
    protected_emails = {
        "bagodistore@techmastersinnovations.in",
        "merchant@bagodi.in",
        "admin@techmasters.in",
        "techmastersinnovations@gmail.com",
        "sachin@techmastersinnovations.in",
    }
    protected_phones = {"+919880768222"}
    if user.email in protected_emails or user.phone_e164 in protected_phones:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "CANNOT_DELETE_MASTER_ACCOUNT", "message": "Master administrative accounts cannot be deleted."}
        )

    # 1. Nullify references in platform audit logs so foreign key constraints are not violated
    await db.execute(update(PlatformAuditLog).where(PlatformAuditLog.actor_id == user_id).values(actor_id=None))

    # 2. Clean up returns and associated images in Cloudflare R2
    try:
        ret_stmt = select(OrderReturnRequest).where(OrderReturnRequest.customer_id == user_id)
        returns = (await db.execute(ret_stmt)).scalars().all()
        for ret in returns:
            if ret.images and isinstance(ret.images, list):
                for img_url in ret.images:
                    if img_url:
                        storage.delete_by_url(img_url)
        await db.execute(delete(OrderReturnRequest).where(OrderReturnRequest.customer_id == user_id))
    except Exception:
        pass

    # 3. Clean up coupon redemptions
    try:
        await db.execute(delete(CouponRedemption).where(CouponRedemption.customer_id == user_id))
    except Exception:
        pass

    # 4. Clean up carts and cart items
    try:
        cart_ids = (await db.execute(select(Cart.id).where(Cart.customer_id == user_id))).scalars().all()
        if cart_ids:
            await db.execute(delete(CartItem).where(CartItem.cart_id.in_(cart_ids)))
            await db.execute(delete(Cart).where(Cart.id.in_(cart_ids)))
    except Exception:
        pass

    # 5. Clean up customer orders (and shipments, proof of delivery in Cloudflare R2)
    try:
        order_ids = (await db.execute(select(Order.id).where(Order.customer_id == user_id))).scalars().all()
        if order_ids:
            shipment_ids = (await db.execute(select(Shipment.id).where(Shipment.order_id.in_(order_ids)))).scalars().all()
            if shipment_ids:
                pod_stmt = select(ProofOfDelivery).where(ProofOfDelivery.shipment_id.in_(shipment_ids))
                pods = (await db.execute(pod_stmt)).scalars().all()
                for pod in pods:
                    if pod.photo_url:
                        storage.delete_by_url(pod.photo_url)
                    if pod.signature_url:
                        storage.delete_by_url(pod.signature_url)

                await db.execute(delete(ProofOfDelivery).where(ProofOfDelivery.shipment_id.in_(shipment_ids)))
                await db.execute(delete(DeliveryTrackingEvent).where(DeliveryTrackingEvent.shipment_id.in_(shipment_ids)))
                await db.execute(delete(ShipmentItem).where(ShipmentItem.shipment_id.in_(shipment_ids)))
                await db.execute(delete(Shipment).where(Shipment.id.in_(shipment_ids)))

            await db.execute(delete(PaymentTransaction).where(PaymentTransaction.order_id.in_(order_ids)))
            await db.execute(delete(OrderItem).where(OrderItem.order_id.in_(order_ids)))
            await db.execute(delete(Order).where(Order.id.in_(order_ids)))
    except Exception:
        pass

    # 6. Customer addresses
    try:
        await db.execute(delete(CustomerAddress).where(CustomerAddress.customer_id == user_id))
    except Exception:
        pass

    # 7. Delivery personnel linking
    try:
        await db.execute(delete(DeliveryPersonnel).where(DeliveryPersonnel.user_id == user_id))
    except Exception:
        pass

    # 8. User roles and sessions
    await db.execute(delete(UserRole).where(UserRole.user_id == user_id))
    await db.execute(delete(UserSession).where(UserSession.user_id == user_id))

    # 9. Clean up any custom user avatar/document files in Cloudflare R2 under users/{user_id}
    storage.delete_file(f"users/{user_id}.jpg")
    storage.delete_file(f"users/{user_id}.png")
    storage.delete_file(f"users/{user_id}.webp")
    storage.delete_file(f"customers/{user_id}.jpg")
    storage.delete_file(f"customers/{user_id}.png")
    storage.delete_file(f"customers/{user_id}.webp")

    # 10. Record immutable audit log WITHOUT setting actor_id to the deleted user
    try:
        from app.modules.platform.services import PlatformAuditService
        await PlatformAuditService.log(
            db,
            action="USER_DELETED",
            target_type="USER",
            target_id=str(user.id),
            actor_id=None,
            actor_email="system@bagodi.in",
            details={
                "user_id": str(user.id),
                "email": user.email,
                "phone": user.phone_e164,
                "display_name": user.display_name,
                "status": "permanently_deleted_all_traces",
            },
        )
    except Exception as e:
        pass

    # 11. Delete the user row permanently
    await db.delete(user)
    await db.commit()
    return True


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a platform user account from catalogue, database, and R2",
)
async def delete_platform_user(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    success = await purge_user_completely(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "User not found."},
        )


@router.post(
    "/users/purge-dummy-data",
    summary="Purge all synthetic test accounts from database and Cloudflare R2",
)
async def purge_all_dummy_users_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from sqlalchemy import select, or_
    from app.modules.identity.models import User

    cleanup_emails = [
        "bagodistore@techmatersinnovations.in",
        "vip.shopper@bagodi.in",
        "vip.client@bagodi.in",
        "client.bidar@bagodi.in",
        "vip_customer_2026@bagodi.in",
        "user_9705376383@bagodi.in",
        "sachin_tester_2026@bagodi.in",
        "testcustomer123@bagodi.in",
        "ananya.patil@example.com",
        "customer@bagodi.in",
        "dummy@bagodi.in",
        "test@bagodi.in",
    ]
    cleanup_phones = [
        "+917894561230",
        "+919208950128",
        "+919988776655",
        "+919900112233",
        "+919705376383",
        "+919605376373",
        "+919505376355",
        "+919845099887",
        "+919876566725",
        "+919876566688",
        "+919876543203",
        "+919876543202",
        "+919876543201",
        "+919876543233",
        "+919876543222",
        "+919876500999",
        "+919876543210",
        "+919876500003",
    ]
    cleanup_stmt = select(User.id).where(
        or_(
            User.email.in_(cleanup_emails),
            User.phone_e164.in_(cleanup_phones),
            User.display_name.in_([
                "Customer 1230", "Customer 0128", "Vip.Shopper", "Vip.Client",
                "Client.Bidar", "Customer 6655", "Customer 2233", "Vip_Customer_2026",
                "Boutique Client", "Customer 6373", "Customer 6355", "Sachin Tester",
                "Customer 6725", "Customer 6688", "Customer 3203", "Customer 3202",
                "Customer 3201", "Customer 3233", "Customer 3222", "Test Customer",
                "Ananya Sharma", "Customer Account",
            ]),
        )
    )
    user_ids = (await db.execute(cleanup_stmt)).scalars().all()
    purged_count = 0
    for uid in user_ids:
        try:
            res = await purge_user_completely(db, uid)
            if res:
                purged_count += 1
        except Exception:
            pass

    return {
        "status": "success",
        "purged_count": purged_count,
        "message": f"Purged {purged_count} test users completely from database, catalogue, and Cloudflare R2.",
    }


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
