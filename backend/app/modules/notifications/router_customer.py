from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, get_security_principal
from app.db.session import get_db
from app.modules.identity.models import User
from app.modules.notifications.models import NotificationMessage
from app.modules.notifications.schemas import (
    CustomerCommunicationPreferenceResponse,
    CustomerCommunicationPreferenceUpdateRequest,
    NotificationMessageResponse,
)
from app.modules.notifications.services import NotificationService

router = APIRouter(prefix="/customer/notifications", tags=["Customer Notification Preferences"])


@router.get("/preferences", response_model=CustomerCommunicationPreferenceResponse)
async def get_preferences(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerCommunicationPreferenceResponse:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    pref = await NotificationService.get_or_create_customer_preferences(
        db, tenant_id=principal.tenant_id, customer_id=principal.user_id
    )
    return CustomerCommunicationPreferenceResponse.model_validate(pref)


@router.put("/preferences", response_model=CustomerCommunicationPreferenceResponse)
async def update_preferences(
    data: CustomerCommunicationPreferenceUpdateRequest,
    request: Request,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerCommunicationPreferenceResponse:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    client_ip = request.client.host if request.client else None
    pref = await NotificationService.update_customer_preferences(
        db,
        tenant_id=principal.tenant_id,
        customer_id=principal.user_id,
        data=data,
        client_ip=client_ip,
    )
    return CustomerCommunicationPreferenceResponse.model_validate(pref)


@router.get("/messages", response_model=list[NotificationMessageResponse])
async def list_customer_messages(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[NotificationMessageResponse]:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    # Fetch customer phone and email to isolate message history to this customer
    stmt_user = select(User).where(User.id == principal.user_id)
    user = (await db.execute(stmt_user)).scalar_one_or_none()
    if not user:
        return []

    recipients = [r for r in [user.phone_e164, user.email] if r]
    if not recipients:
        return []

    stmt_msgs = (
        select(NotificationMessage)
        .where(
            NotificationMessage.tenant_id == principal.tenant_id,
            NotificationMessage.recipient.in_(recipients),
        )
        .order_by(NotificationMessage.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    messages = (await db.execute(stmt_msgs)).scalars().all()
    return [NotificationMessageResponse.model_validate(m) for m in messages]
