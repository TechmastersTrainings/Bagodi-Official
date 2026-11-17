from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.base import utc_now
from app.modules.identity.models import Permission, Role, RolePermission, User, UserRole
from app.modules.notifications.models import NotificationOutbox
from app.modules.notifications.services import NotificationService
from app.modules.platform.models import (
    MerchantInvoice,
    MerchantSubscription,
    MerchantSubscriptionPlan,
    PlatformAuditLog,
    Store,
    Tenant,
    TenantKYCDocument,
    TenantStatusLog,
)
from app.modules.platform.schemas import (
    MerchantInvoiceCreate,
    PlatformStaffCreate,
    PlatformStaffUpdate,
    StoreCreate,
    StoreUpdate,
    SubscriptionPlanCreate,
    TenantCreate,
    TenantKYCDocumentCreate,
    TenantKYCDocumentReview,
    TenantUpdate,
)

settings = get_settings()


# -----------------------------------------------------------------------------
# Helper: Verify user exists before setting foreign key
# -----------------------------------------------------------------------------
async def get_valid_user_id(db: AsyncSession, user_id: UUID | None) -> UUID | None:
    if not user_id:
        return None
    stmt = select(User.id).where(User.id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()


# -----------------------------------------------------------------------------
# 1. Platform Audit Logger Service
# -----------------------------------------------------------------------------
class PlatformAuditService:
    @staticmethod
    async def log(
        db: AsyncSession,
        action: str,
        target_type: str,
        target_id: str | None = None,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> PlatformAuditLog:
        valid_actor_id = await get_valid_user_id(db, actor_id)

        entry = PlatformAuditLog(
            actor_id=valid_actor_id,
            actor_email=actor_email,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def list_logs(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        action: str | None = None,
        target_type: str | None = None,
    ) -> list[PlatformAuditLog]:
        stmt = select(PlatformAuditLog).order_by(desc(PlatformAuditLog.created_at))
        if action:
            stmt = stmt.where(PlatformAuditLog.action == action)
        if target_type:
            stmt = stmt.where(PlatformAuditLog.target_type == target_type)
        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())


# -----------------------------------------------------------------------------
# 2. Tenant & Store Service
# -----------------------------------------------------------------------------
class TenantService:
    @staticmethod
    async def create_tenant(
        db: AsyncSession,
        data: TenantCreate,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Tenant:
        stmt = select(Tenant).where(Tenant.slug == data.slug)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "TENANT_SLUG_EXISTS",
                    "message": f"Tenant slug '{data.slug}' already exists.",
                },
            )

        tenant = Tenant(
            name=data.name,
            slug=data.slug,
            status="pending",
            legal_name=data.legal_name,
            contact_email=data.contact_email,
            contact_phone=data.contact_phone,
            business_type=data.business_type,
            pan_number=data.pan_number,
            gstin=data.gstin,
            registered_address=data.registered_address,
        )
        db.add(tenant)
        await db.flush()

        # Create initial status log
        valid_actor_id = await get_valid_user_id(db, actor_id)
        status_log = TenantStatusLog(
            tenant_id=tenant.id,
            previous_status="NONE",
            new_status="pending",
            reason="Initial merchant onboarding submission",
            actor_id=valid_actor_id,
        )
        db.add(status_log)

        # Audit log
        await PlatformAuditService.log(
            db,
            action="TENANT_ONBOARDED",
            target_type="TENANT",
            target_id=str(tenant.id),
            actor_id=actor_id,
            actor_email=actor_email,
            details={
                "name": tenant.name,
                "slug": tenant.slug,
                "legal_name": tenant.legal_name,
                "business_type": tenant.business_type,
                "gstin": tenant.gstin,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Assign initial subscription plan if specified
        if data.initial_plan_code:
            plan_stmt = select(MerchantSubscriptionPlan).where(
                MerchantSubscriptionPlan.code == data.initial_plan_code
            )
            plan = (await db.execute(plan_stmt)).scalar_one_or_none()
            if plan:
                now = utc_now()
                end_date = now + timedelta(days=365 if plan.billing_cycle == "ANNUAL" else 30)
                sub = MerchantSubscription(
                    tenant_id=tenant.id,
                    plan_id=plan.id,
                    status="ACTIVE",
                    current_period_start=now,
                    current_period_end=end_date,
                    auto_renew=True,
                )
                db.add(sub)

        # Update associated merchant users and stores status
        from app.modules.identity.models import User, UserRole
        from app.modules.platform.models import Store
        user_roles_stmt = select(UserRole.user_id).where(UserRole.tenant_id == tenant_id)
        user_ids = (await db.execute(user_roles_stmt)).scalars().all()
        if user_ids:
            users_stmt = select(User).where(User.id.in_(user_ids))
            users = (await db.execute(users_stmt)).scalars().all()
            for u in users:
                if new_status == "active":
                    u.status = "active"
                elif new_status in ("suspended", "rejected"):
                    u.status = "suspended"

        store_stmt = select(Store).where(Store.tenant_id == tenant_id)
        stores = (await db.execute(store_stmt)).scalars().all()
        for s in stores:
            if new_status == "active":
                s.status = "active"
            elif new_status in ("suspended", "rejected"):
                s.status = "inactive"

        await db.commit()
        await db.refresh(tenant)
        return tenant

    @staticmethod
    async def list_tenants(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        status_filter: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        stmt = (
            select(
                Tenant,
                func.count(Store.id).label("store_count"),
            )
            .outerjoin(Store, Store.tenant_id == Tenant.id)
            .group_by(Tenant.id)
            .order_by(desc(Tenant.created_at))
        )

        if status_filter:
            stmt = stmt.where(Tenant.status == status_filter)
        if search:
            s = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Tenant.name.ilike(s),
                    Tenant.slug.ilike(s),
                    Tenant.legal_name.ilike(s),
                    Tenant.gstin.ilike(s),
                )
            )

        stmt = stmt.offset(skip).limit(limit)
        results = (await db.execute(stmt)).all()

        enriched = []
        for tenant, store_count in results:
            # Check KYC documents status
            kyc_stmt = select(TenantKYCDocument.status).where(TenantKYCDocument.tenant_id == tenant.id)
            kyc_statuses = (await db.execute(kyc_stmt)).scalars().all()
            if not kyc_statuses:
                kyc_summary = "NOT_SUBMITTED"
            elif any(s == "REJECTED" for s in kyc_statuses):
                kyc_summary = "REJECTED"
            elif all(s == "VERIFIED" for s in kyc_statuses) and len(kyc_statuses) >= 2:
                kyc_summary = "VERIFIED"
            else:
                kyc_summary = "PENDING_REVIEW"

            # Check active subscription
            sub_stmt = (
                select(MerchantSubscriptionPlan.name)
                .join(MerchantSubscription, MerchantSubscription.plan_id == MerchantSubscriptionPlan.id)
                .where(MerchantSubscription.tenant_id == tenant.id, MerchantSubscription.status == "ACTIVE")
                .limit(1)
            )
            plan_name = (await db.execute(sub_stmt)).scalar_one_or_none()

            enriched.append(
                {
                    "id": tenant.id,
                    "name": tenant.name,
                    "slug": tenant.slug,
                    "status": tenant.status,
                    "legal_name": tenant.legal_name,
                    "contact_email": tenant.contact_email,
                    "contact_phone": tenant.contact_phone,
                    "business_type": tenant.business_type,
                    "pan_number": tenant.pan_number,
                    "gstin": tenant.gstin,
                    "registered_address": tenant.registered_address,
                    "owner_name": tenant.owner_name,
                    "bank_account_number": tenant.bank_account_number,
                    "bank_ifsc": tenant.bank_ifsc,
                    "bank_name": tenant.bank_name,
                    "category_specialization": tenant.category_specialization,
                    "created_at": tenant.created_at,
                    "updated_at": tenant.updated_at,
                    "store_count": store_count,
                    "kyc_status": kyc_summary,
                    "current_plan_name": plan_name or "Standard Retail",
                }
            )

        return enriched

    @staticmethod
    async def get_tenant_by_id(db: AsyncSession, tenant_id: UUID) -> dict:
        stmt = (
            select(
                Tenant,
                func.count(Store.id).label("store_count"),
            )
            .outerjoin(Store, Store.tenant_id == Tenant.id)
            .where(Tenant.id == tenant_id)
            .group_by(Tenant.id)
        )
        res = (await db.execute(stmt)).first()
        if not res:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "TENANT_NOT_FOUND", "message": "Tenant not found."},
            )
        tenant, store_count = res

        # KYC summary
        kyc_stmt = select(TenantKYCDocument.status).where(TenantKYCDocument.tenant_id == tenant.id)
        kyc_statuses = (await db.execute(kyc_stmt)).scalars().all()
        if not kyc_statuses:
            kyc_summary = "NOT_SUBMITTED"
        elif any(s == "REJECTED" for s in kyc_statuses):
            kyc_summary = "REJECTED"
        elif all(s == "VERIFIED" for s in kyc_statuses) and len(kyc_statuses) >= 2:
            kyc_summary = "VERIFIED"
        else:
            kyc_summary = "PENDING_REVIEW"

        # Plan
        sub_stmt = (
            select(MerchantSubscriptionPlan.name)
            .join(MerchantSubscription, MerchantSubscription.plan_id == MerchantSubscriptionPlan.id)
            .where(MerchantSubscription.tenant_id == tenant.id, MerchantSubscription.status == "ACTIVE")
            .limit(1)
        )
        plan_name = (await db.execute(sub_stmt)).scalar_one_or_none()

        return {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "status": tenant.status,
            "legal_name": tenant.legal_name,
            "contact_email": tenant.contact_email,
            "contact_phone": tenant.contact_phone,
            "business_type": tenant.business_type,
            "pan_number": tenant.pan_number,
            "gstin": tenant.gstin,
            "registered_address": tenant.registered_address,
            "owner_name": tenant.owner_name,
            "bank_account_number": tenant.bank_account_number,
            "bank_ifsc": tenant.bank_ifsc,
            "bank_name": tenant.bank_name,
            "category_specialization": tenant.category_specialization,
            "created_at": tenant.created_at,
            "updated_at": tenant.updated_at,
            "store_count": store_count,
            "kyc_status": kyc_summary,
            "current_plan_name": plan_name or "Standard Retail",
        }

    @staticmethod
    async def update_tenant_status(
        db: AsyncSession,
        tenant_id: UUID,
        new_status: str,
        reason: str | None = None,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Tenant:
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        tenant = (await db.execute(stmt)).scalar_one_or_none()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "TENANT_NOT_FOUND", "message": "Tenant not found."},
            )

        previous_status = tenant.status
        tenant.status = new_status

        # Create status change log
        valid_actor_id = await get_valid_user_id(db, actor_id)
        status_log = TenantStatusLog(
            tenant_id=tenant.id,
            previous_status=previous_status,
            new_status=new_status,
            reason=reason or f"Administrative status change to {new_status}",
            actor_id=valid_actor_id,
        )
        db.add(status_log)

        # Audit log
        action_name = "TENANT_ACTIVATED" if new_status == "active" else (
            "TENANT_SUSPENDED" if new_status == "suspended" else "TENANT_STATUS_CHANGED"
        )
        await PlatformAuditService.log(
            db,
            action=action_name,
            target_type="TENANT",
            target_id=str(tenant.id),
            actor_id=actor_id,
            actor_email=actor_email,
            details={
                "previous_status": previous_status,
                "new_status": new_status,
                "reason": reason,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Update associated merchant users and stores status
        from app.modules.identity.models import User, UserRole
        from app.modules.platform.models import Store
        user_roles_stmt = select(UserRole.user_id).where(UserRole.tenant_id == tenant_id)
        user_ids = (await db.execute(user_roles_stmt)).scalars().all()
        if user_ids:
            users_stmt = select(User).where(User.id.in_(user_ids))
            users = (await db.execute(users_stmt)).scalars().all()
            for u in users:
                if new_status == "active":
                    u.status = "active"
                elif new_status in ("suspended", "rejected"):
                    u.status = "suspended"

        store_stmt = select(Store).where(Store.tenant_id == tenant_id)
        stores = (await db.execute(store_stmt)).scalars().all()
        for s in stores:
            if new_status == "active":
                s.status = "active"
            elif new_status in ("suspended", "rejected"):
                s.status = "inactive"

        await db.commit()
        await db.refresh(tenant)
        return tenant

    @staticmethod
    async def list_lifecycle_logs(db: AsyncSession, tenant_id: UUID) -> list[TenantStatusLog]:
        stmt = (
            select(TenantStatusLog)
            .where(TenantStatusLog.tenant_id == tenant_id)
            .order_by(desc(TenantStatusLog.created_at))
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


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
                detail={"code": "STORE_NOT_FOUND", "message": "Store not found."},
            )
        return store

    @staticmethod
    async def update_store(
        db: AsyncSession, tenant_id: UUID, store_id: UUID, data: StoreUpdate
    ) -> Store:
        store = await StoreService.get_store_by_id(db, tenant_id, store_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(store, field, value)
        await db.commit()
        await db.refresh(store)
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


# -----------------------------------------------------------------------------
# 3. KYC Document Management Service
# -----------------------------------------------------------------------------
class KYCService:
    @staticmethod
    async def add_document(
        db: AsyncSession,
        tenant_id: UUID,
        data: TenantKYCDocumentCreate,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
        ip_address: str | None = None,
    ) -> TenantKYCDocument:
        doc = TenantKYCDocument(
            tenant_id=tenant_id,
            document_type=data.document_type,
            document_number=data.document_number,
            document_url=data.document_url,
            file_name=data.file_name,
            file_size_bytes=data.file_size_bytes,
            status="PENDING",
        )
        db.add(doc)
        await db.flush()

        await PlatformAuditService.log(
            db,
            action="KYC_DOCUMENT_UPLOADED",
            target_type="KYC",
            target_id=str(doc.id),
            actor_id=actor_id,
            actor_email=actor_email,
            details={
                "tenant_id": str(tenant_id),
                "document_type": data.document_type,
                "document_number": data.document_number,
                "file_name": data.file_name,
            },
            ip_address=ip_address,
        )

        await db.commit()
        await db.refresh(doc)
        return doc

    @staticmethod
    async def list_documents(db: AsyncSession, tenant_id: UUID) -> list[TenantKYCDocument]:
        stmt = (
            select(TenantKYCDocument)
            .where(TenantKYCDocument.tenant_id == tenant_id)
            .order_by(desc(TenantKYCDocument.created_at))
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def review_document(
        db: AsyncSession,
        tenant_id: UUID,
        doc_id: UUID,
        review_data: TenantKYCDocumentReview,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
        ip_address: str | None = None,
    ) -> TenantKYCDocument:
        stmt = select(TenantKYCDocument).where(
            TenantKYCDocument.id == doc_id,
            TenantKYCDocument.tenant_id == tenant_id,
        )
        doc = (await db.execute(stmt)).scalar_one_or_none()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "KYC_DOC_NOT_FOUND", "message": "KYC document not found."},
            )

        doc.status = review_data.status
        doc.rejection_reason = review_data.rejection_reason if review_data.status == "REJECTED" else None
        doc.verified_at = utc_now()
        doc.verified_by = await get_valid_user_id(db, actor_id)

        await PlatformAuditService.log(
            db,
            action=f"KYC_DOCUMENT_{review_data.status}",
            target_type="KYC",
            target_id=str(doc.id),
            actor_id=actor_id,
            actor_email=actor_email,
            details={
                "tenant_id": str(tenant_id),
                "document_type": doc.document_type,
                "status": review_data.status,
                "rejection_reason": doc.rejection_reason,
            },
            ip_address=ip_address,
        )

        await db.commit()
        await db.refresh(doc)
        return doc


# -----------------------------------------------------------------------------
# 4. Merchant Subscription & Billing Service
# -----------------------------------------------------------------------------
class BillingService:
    @staticmethod
    async def seed_default_plans_if_empty(db: AsyncSession):
        stmt = select(func.count(MerchantSubscriptionPlan.id))
        count = (await db.execute(stmt)).scalar() or 0
        if count == 0:
            default_plans = [
                MerchantSubscriptionPlan(
                    code="STARTER",
                    name="Bagodi Boutique Starter",
                    description="Ideal for single boutique physical store operations and emerging apparel retail",
                    billing_cycle="MONTHLY",
                    price=Decimal("2999.00"),
                    currency="INR",
                    max_stores=1,
                    max_staff_users=5,
                    commission_rate_percent=Decimal("2.50"),
                    features=["1 Physical Store", "5 Staff Accounts", "Barcoding & POS", "Standard Reports"],
                    is_active=True,
                ),
                MerchantSubscriptionPlan(
                    code="GROWTH_RETAIL",
                    name="Fashion Growth Tier",
                    description="Multi-store apparel inventory, doorstep delivery logistics, and double-entry ledger",
                    billing_cycle="MONTHLY",
                    price=Decimal("7999.00"),
                    currency="INR",
                    max_stores=5,
                    max_staff_users=25,
                    commission_rate_percent=Decimal("1.75"),
                    features=["Up to 5 Stores", "25 Staff Accounts", "Dedicated Rider Management", "Advanced Analytics", "Automated DLR & SMS"],
                    is_active=True,
                ),
                MerchantSubscriptionPlan(
                    code="ENTERPRISE_FLAGSHIP",
                    name="Omnichannel Enterprise",
                    description="Unlimited store branches, custom courier integrations, SLA monitoring, and API access",
                    billing_cycle="MONTHLY",
                    price=Decimal("19999.00"),
                    currency="INR",
                    max_stores=20,
                    max_staff_users=100,
                    commission_rate_percent=Decimal("1.00"),
                    features=["Unlimited Stores", "Dedicated Account Manager", "Priority Courier Integration", "Automated Reconciliation", "24/7 SLA Support"],
                    is_active=True,
                ),
            ]
            db.add_all(default_plans)
            await db.commit()

    @staticmethod
    async def list_plans(db: AsyncSession) -> list[MerchantSubscriptionPlan]:
        await BillingService.seed_default_plans_if_empty(db)
        stmt = select(MerchantSubscriptionPlan).where(MerchantSubscriptionPlan.is_active == True).order_by(MerchantSubscriptionPlan.price.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_plan(
        db: AsyncSession,
        data: SubscriptionPlanCreate,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
    ) -> MerchantSubscriptionPlan:
        plan = MerchantSubscriptionPlan(
            code=data.code.upper(),
            name=data.name,
            description=data.description,
            billing_cycle=data.billing_cycle,
            price=data.price,
            currency=data.currency,
            max_stores=data.max_stores,
            max_staff_users=data.max_staff_users,
            commission_rate_percent=data.commission_rate_percent,
            features=data.features,
            is_active=True,
        )
        db.add(plan)
        await db.flush()

        await PlatformAuditService.log(
            db,
            action="SUBSCRIPTION_PLAN_CREATED",
            target_type="SUBSCRIPTION_PLAN",
            target_id=str(plan.id),
            actor_id=actor_id,
            actor_email=actor_email,
            details={"code": plan.code, "name": plan.name, "price": str(plan.price)},
        )

        await db.commit()
        await db.refresh(plan)
        return plan

    @staticmethod
    async def list_subscriptions(db: AsyncSession, tenant_id: UUID | None = None) -> list[MerchantSubscription]:
        stmt = (
            select(MerchantSubscription)
            .options(selectinload(MerchantSubscription.plan))
            .order_by(desc(MerchantSubscription.created_at))
        )
        if tenant_id:
            stmt = stmt.where(MerchantSubscription.tenant_id == tenant_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def assign_subscription(
        db: AsyncSession,
        tenant_id: UUID,
        plan_id: UUID,
        auto_renew: bool = True,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
    ) -> MerchantSubscription:
        # Check plan
        plan_stmt = select(MerchantSubscriptionPlan).where(MerchantSubscriptionPlan.id == plan_id)
        plan = (await db.execute(plan_stmt)).scalar_one_or_none()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PLAN_NOT_FOUND", "message": "Subscription plan not found."},
            )

        now = utc_now()
        end_date = now + timedelta(days=365 if plan.billing_cycle == "ANNUAL" else 30)

        # Cancel previous active subscriptions for this tenant
        prev_stmt = select(MerchantSubscription).where(
            MerchantSubscription.tenant_id == tenant_id,
            MerchantSubscription.status == "ACTIVE",
        )
        prev_subs = (await db.execute(prev_stmt)).scalars().all()
        for ps in prev_subs:
            ps.status = "CANCELLED"

        sub = MerchantSubscription(
            tenant_id=tenant_id,
            plan_id=plan.id,
            status="ACTIVE",
            current_period_start=now,
            current_period_end=end_date,
            auto_renew=auto_renew,
        )
        db.add(sub)
        await db.flush()

        await PlatformAuditService.log(
            db,
            action="SUBSCRIPTION_ASSIGNED",
            target_type="SUBSCRIPTION",
            target_id=str(sub.id),
            actor_id=actor_id,
            actor_email=actor_email,
            details={
                "tenant_id": str(tenant_id),
                "plan_code": plan.code,
                "plan_name": plan.name,
                "price": str(plan.price),
            },
        )

        await db.commit()
        stmt = (
            select(MerchantSubscription)
            .options(selectinload(MerchantSubscription.plan))
            .where(MerchantSubscription.id == sub.id)
        )
        return (await db.execute(stmt)).scalar_one()

    @staticmethod
    async def list_invoices(
        db: AsyncSession, tenant_id: UUID | None = None, status_filter: str | None = None
    ) -> list[MerchantInvoice]:
        stmt = select(MerchantInvoice).order_by(desc(MerchantInvoice.created_at))
        if tenant_id:
            stmt = stmt.where(MerchantInvoice.tenant_id == tenant_id)
        if status_filter:
            stmt = stmt.where(MerchantInvoice.status == status_filter)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_invoice(
        db: AsyncSession,
        data: MerchantInvoiceCreate,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
    ) -> MerchantInvoice:
        inv_count_stmt = select(func.count(MerchantInvoice.id))
        count = (await db.execute(inv_count_stmt)).scalar() or 0
        inv_number = f"TM-INV-{datetime.now(UTC).year}-{count + 1001:05d}"

        invoice = MerchantInvoice(
            tenant_id=data.tenant_id,
            subscription_id=data.subscription_id,
            invoice_number=inv_number,
            billing_period_start=data.billing_period_start,
            billing_period_end=data.billing_period_end,
            amount=data.amount,
            tax_amount=data.tax_amount,
            total_amount=data.total_amount,
            currency=data.currency,
            status="PENDING",
            due_date=data.due_date,
            line_items=data.line_items or [{"description": "Platform SaaS subscription & merchant services", "amount": str(data.amount)}],
        )
        db.add(invoice)
        await db.flush()

        await PlatformAuditService.log(
            db,
            action="MERCHANT_INVOICE_GENERATED",
            target_type="INVOICE",
            target_id=str(invoice.id),
            actor_id=actor_id,
            actor_email=actor_email,
            details={
                "tenant_id": str(data.tenant_id),
                "invoice_number": inv_number,
                "total_amount": str(data.total_amount),
            },
        )

        await db.commit()
        await db.refresh(invoice)
        return invoice

    @staticmethod
    async def pay_invoice(
        db: AsyncSession,
        invoice_id: UUID,
        payment_reference: str,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
    ) -> MerchantInvoice:
        stmt = select(MerchantInvoice).where(MerchantInvoice.id == invoice_id)
        invoice = (await db.execute(stmt)).scalar_one_or_none()
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "INVOICE_NOT_FOUND", "message": "Invoice not found."},
            )

        invoice.status = "PAID"
        invoice.paid_at = utc_now()
        invoice.payment_reference = payment_reference

        await PlatformAuditService.log(
            db,
            action="MERCHANT_INVOICE_PAID",
            target_type="INVOICE",
            target_id=str(invoice.id),
            actor_id=actor_id,
            actor_email=actor_email,
            details={
                "invoice_number": invoice.invoice_number,
                "payment_reference": payment_reference,
                "total_amount": str(invoice.total_amount),
            },
        )

        await db.commit()
        await db.refresh(invoice)
        return invoice


# -----------------------------------------------------------------------------
# 5. Super Admin Staff Delegation & RBAC Service
# -----------------------------------------------------------------------------
class PlatformStaffService:
    @staticmethod
    async def list_staff(db: AsyncSession) -> list[dict]:
        stmt = (
            select(User)
            .where(User.is_platform_user == True)
            .order_by(desc(User.created_at))
        )
        users = (await db.execute(stmt)).scalars().all()

        staff_list = []
        for u in users:
            role_stmt = (
                select(Role.code)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == u.id, UserRole.tenant_id.is_(None))
            )
            roles = (await db.execute(role_stmt)).scalars().all()
            staff_list.append(
                {
                    "id": u.id,
                    "phone_e164": u.phone_e164,
                    "email": u.email,
                    "display_name": u.display_name or (u.email.split("@")[0] if u.email else "Platform Admin"),
                    "status": u.status,
                    "is_platform_user": u.is_platform_user,
                    "roles": list(roles) if roles else ["SUPER_ADMIN"],
                    "created_at": u.created_at,
                }
            )
        return staff_list

    @staticmethod
    async def create_staff(
        db: AsyncSession,
        data: PlatformStaffCreate,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
    ) -> dict:
        stmt = select(User).where(User.phone_e164 == data.phone_e164)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            user = existing
            user.is_platform_user = True
            user.display_name = data.display_name
            if data.email:
                user.email = data.email
        else:
            user = User(
                phone_e164=data.phone_e164,
                email=data.email,
                display_name=data.display_name,
                status="active",
                is_platform_user=True,
            )
            db.add(user)
            await db.flush()

        # Ensure Role exists
        role_stmt = select(Role).where(Role.code == data.role_code, Role.tenant_id.is_(None))
        role = (await db.execute(role_stmt)).scalar_one_or_none()
        if not role:
            role = Role(
                code=data.role_code,
                name=data.role_code.replace("_", " ").title(),
                scope="platform",
                tenant_id=None,
            )
            db.add(role)
            await db.flush()

            # Ensure Permission platform.* exists
            p_stmt = select(Permission).where(Permission.code == "platform.*")
            perm = (await db.execute(p_stmt)).scalar_one_or_none()
            if not perm:
                perm = Permission(code="platform.*", description="Full platform administrator access")
                db.add(perm)
                await db.flush()

            rp = RolePermission(role_id=role.id, permission_id=perm.id)
            db.add(rp)
            await db.flush()

        # Assign UserRole
        ur_stmt = select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_id == role.id,
            UserRole.tenant_id.is_(None),
        )
        ur = (await db.execute(ur_stmt)).scalar_one_or_none()
        if not ur:
            db.add(UserRole(user_id=user.id, role_id=role.id, tenant_id=None))

        await PlatformAuditService.log(
            db,
            action="PLATFORM_STAFF_DELEGATED",
            target_type="USER",
            target_id=str(user.id),
            actor_id=actor_id,
            actor_email=actor_email,
            details={
                "phone_e164": user.phone_e164,
                "display_name": user.display_name,
                "role_code": data.role_code,
            },
        )

        await db.commit()
        await db.refresh(user)

        return {
            "id": user.id,
            "phone_e164": user.phone_e164,
            "email": user.email,
            "display_name": user.display_name,
            "status": user.status,
            "is_platform_user": True,
            "roles": [data.role_code],
            "created_at": user.created_at,
        }

    @staticmethod
    async def update_staff_status(
        db: AsyncSession,
        user_id: UUID,
        data: PlatformStaffUpdate,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
    ) -> dict:
        stmt = select(User).where(User.id == user_id, User.is_platform_user == True)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "STAFF_NOT_FOUND", "message": "Platform staff member not found."},
            )

        if data.status:
            user.status = data.status
        if data.display_name:
            user.display_name = data.display_name

        if data.role_code:
            # Change role
            role_stmt = select(Role).where(Role.code == data.role_code, Role.tenant_id.is_(None))
            role = (await db.execute(role_stmt)).scalar_one_or_none()
            if not role:
                role = Role(
                    code=data.role_code,
                    name=data.role_code.replace("_", " ").title(),
                    scope="platform",
                    tenant_id=None,
                )
                db.add(role)
                await db.flush()

            # Replace user_roles
            del_ur = select(UserRole).where(UserRole.user_id == user.id, UserRole.tenant_id.is_(None))
            existing_urs = (await db.execute(del_ur)).scalars().all()
            for eur in existing_urs:
                await db.delete(eur)

            db.add(UserRole(user_id=user.id, role_id=role.id, tenant_id=None))

        await PlatformAuditService.log(
            db,
            action="PLATFORM_STAFF_UPDATED",
            target_type="USER",
            target_id=str(user.id),
            actor_id=actor_id,
            actor_email=actor_email,
            details={"status": user.status, "role_code": data.role_code},
        )

        await db.commit()
        await db.refresh(user)

        role_stmt = (
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id, UserRole.tenant_id.is_(None))
        )
        roles = (await db.execute(role_stmt)).scalars().all()

        return {
            "id": user.id,
            "phone_e164": user.phone_e164,
            "email": user.email,
            "display_name": user.display_name,
            "status": user.status,
            "is_platform_user": True,
            "roles": list(roles) if roles else ["SUPER_ADMIN"],
            "created_at": user.created_at,
        }


# -----------------------------------------------------------------------------
# 6. System Diagnostics & Outbox Monitoring Service
# -----------------------------------------------------------------------------
class PlatformSystemService:
    @staticmethod
    async def get_system_health(db: AsyncSession) -> dict:
        # Check active tenants
        t_stmt = select(func.count(Tenant.id)).where(Tenant.status == "active")
        active_tenants = (await db.execute(t_stmt)).scalar() or 0

        # Outbox pending & failed
        pending_stmt = select(func.count(NotificationOutbox.id)).where(NotificationOutbox.status == "pending")
        pending_outbox = (await db.execute(pending_stmt)).scalar() or 0

        failed_stmt = select(func.count(NotificationOutbox.id)).where(NotificationOutbox.status == "failed")
        failed_outbox = (await db.execute(failed_stmt)).scalar() or 0

        return {
            "app_name": settings.app_name,
            "app_env": settings.app_env,
            "status": "HEALTHY",
            "database": "CONNECTED",
            "pool_size": 20,
            "active_tenants": active_tenants,
            "pending_outbox_events": pending_outbox,
            "failed_outbox_events": failed_outbox,
            "system_timestamp": utc_now(),
        }

    @staticmethod
    async def list_outbox_events(
        db: AsyncSession, limit: int = 50, status_filter: str | None = None
    ) -> list[dict]:
        stmt = (
            select(NotificationOutbox, Tenant.name.label("tenant_name"))
            .outerjoin(Tenant, Tenant.id == NotificationOutbox.tenant_id)
            .order_by(desc(NotificationOutbox.created_at))
        )
        if status_filter:
            stmt = stmt.where(NotificationOutbox.status == status_filter)
        stmt = stmt.limit(limit)
        results = (await db.execute(stmt)).all()

        return [
            {
                "id": ob.id,
                "tenant_id": ob.tenant_id,
                "tenant_name": t_name or "Global System",
                "event_type": ob.event_type,
                "aggregate_type": ob.aggregate_type,
                "aggregate_id": ob.aggregate_id,
                "status": ob.status,
                "retry_count": ob.retry_count,
                "created_at": ob.created_at,
                "updated_at": ob.updated_at,
            }
            for ob, t_name in results
        ]

    @staticmethod
    async def process_outbox_events(
        db: AsyncSession,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
    ) -> dict:
        batch_res = await NotificationService.process_outbox_batch(db, batch_size=50)
        processed = batch_res.processed_count if hasattr(batch_res, "processed_count") else 0

        await PlatformAuditService.log(
            db,
            action="OUTBOX_WORKER_MANUAL_TRIGGER",
            target_type="SYSTEM",
            target_id="notification_outbox",
            actor_id=actor_id,
            actor_email=actor_email,
            details={"processed_count": processed},
        )

        return {"processed": processed, "timestamp": utc_now()}
