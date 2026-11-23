from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.passwords import hash_password
from app.core.security import SecurityPrincipal, get_security_principal
from app.core.tenant import TenantContext, get_current_tenant
from app.db.session import get_db
from app.modules.identity.models import Role, User, UserRole
from app.modules.identity.schemas import MerchantStaffCreate, MerchantStaffResponse

router = APIRouter(prefix="/merchant/users", tags=["Merchant Staff & Boutique Team"])


@router.get(
    "",
    response_model=list[MerchantStaffResponse],
    summary="List all store staff and boutique team members for the merchant",
)
async def list_merchant_staff(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = (
        select(User, Role.code)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.tenant_id == tenant.tenant_id)
        .order_by(User.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    results = []
    seen = set()
    for user, role_code in rows:
        if user.id in seen:
            continue
        seen.add(user.id)
        results.append(
            MerchantStaffResponse(
                id=user.id,
                display_name=user.display_name,
                email=user.email,
                phone_e164=user.phone_e164,
                status=user.status,
                role=role_code,
                tenant_id=tenant.tenant_id,
                created_at=user.created_at,
            )
        )
    return results


@router.post(
    "",
    response_model=MerchantStaffResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new boutique staff or store associate",
)
async def create_merchant_staff(
    data: MerchantStaffCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    clean_email = data.email.strip().lower()
    # Check if user already exists
    existing = (
        await db.execute(select(User).where(User.email == clean_email))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EMAIL_EXISTS",
                "message": f"User with email '{clean_email}' already exists.",
            },
        )

    # Resolve role
    role_obj = (
        await db.execute(select(Role).where(Role.code == data.role))
    ).scalar_one_or_none()
    if not role_obj:
        role_obj = (
            await db.execute(select(Role).where(Role.code == "STORE_MANAGER"))
        ).scalar_one_or_none()

    new_user = User(
        email=clean_email,
        phone_e164=data.phone_e164.strip(),
        display_name=data.display_name.strip(),
        password_hash=hash_password(data.password),
        status="active",
        is_platform_user=False,
    )
    db.add(new_user)
    await db.flush()

    if role_obj:
        db.add(
            UserRole(
                user_id=new_user.id,
                role_id=role_obj.id,
                tenant_id=tenant.tenant_id,
            )
        )

    await db.commit()
    await db.refresh(new_user)

    return MerchantStaffResponse(
        id=new_user.id,
        display_name=new_user.display_name,
        email=new_user.email,
        phone_e164=new_user.phone_e164,
        status=new_user.status,
        role=role_obj.code if role_obj else "STORE_MANAGER",
        tenant_id=tenant.tenant_id,
        created_at=new_user.created_at,
    )


@router.patch(
    "/{user_id}/status",
    response_model=MerchantStaffResponse,
    summary="Toggle boutique staff active/inactive status",
)
async def toggle_merchant_staff_status(
    user_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Verify user belongs to tenant
    ur_stmt = select(UserRole).where(
        UserRole.user_id == user_id, UserRole.tenant_id == tenant.tenant_id
    )
    user_role = (await db.execute(ur_stmt)).scalar_one_or_none()
    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "Staff member not found."},
        )

    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "Staff member not found."},
        )

    user.status = "inactive" if user.status == "active" else "active"
    await db.commit()
    await db.refresh(user)

    try:
        from app.modules.platform.services import PlatformAuditService
        audit_action = "STAFF_SUSPENDED" if user.status == "inactive" else "STAFF_ACTIVATED"
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
                "status": user.status,
            },
        )
    except Exception:
        pass

    role_code = "STORE_MANAGER"
    role_obj = (
        await db.execute(select(Role).where(Role.id == user_role.role_id))
    ).scalar_one_or_none()
    if role_obj:
        role_code = role_obj.code

    return MerchantStaffResponse(
        id=user.id,
        display_name=user.display_name,
        email=user.email,
        phone_e164=user.phone_e164,
        status=user.status,
        role=role_code,
        tenant_id=tenant.tenant_id,
        created_at=user.created_at,
    )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a staff member from the merchant boutique",
)
async def delete_merchant_staff(
    user_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ur_stmt = select(UserRole).where(
        UserRole.user_id == user_id, UserRole.tenant_id == tenant.tenant_id
    )
    user_role = (await db.execute(ur_stmt)).scalar_one_or_none()
    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "Staff member not found."},
        )

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user:
        try:
            from app.modules.platform.services import PlatformAuditService
            await PlatformAuditService.log(
                db,
                action="STAFF_DELETED",
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

    from app.modules.identity.models import UserSession
    await db.execute(delete(UserRole).where(UserRole.user_id == user_id))
    await db.execute(delete(UserSession).where(UserSession.user_id == user_id))
    if user:
        await db.delete(user)
    await db.commit()

