from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, require_permission
from app.db.session import get_db
from app.modules.notifications.models import (
    NotificationAuditLog,
    NotificationMessage,
    NotificationOutbox,
    NotificationTemplate,
)
from app.modules.notifications.schemas import (
    NotificationAuditLogResponse,
    NotificationDirectSendRequest,
    NotificationMessageResponse,
    NotificationOutboxResponse,
    NotificationTemplateCreateRequest,
    NotificationTemplateResponse,
    OutboxProcessResponse,
)
from app.modules.notifications.services import NotificationService

router = APIRouter(prefix="/merchant/notifications", tags=["Merchant Communication & Outbox Operations"])


@router.get("/outbox", response_model=list[NotificationOutboxResponse])
async def list_outbox_items(
    principal: Annotated[SecurityPrincipal, Depends(require_permission("notifications.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[NotificationOutboxResponse]:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    stmt = select(NotificationOutbox).where(NotificationOutbox.tenant_id == principal.tenant_id)
    if status_filter:
        stmt = stmt.where(NotificationOutbox.status == status_filter)

    stmt = stmt.order_by(NotificationOutbox.created_at.desc()).limit(limit).offset(offset)
    items = (await db.execute(stmt)).scalars().all()
    return [NotificationOutboxResponse.model_validate(i) for i in items]


@router.post("/outbox/process", response_model=OutboxProcessResponse)
async def process_outbox_queue(
    principal: Annotated[SecurityPrincipal, Depends(require_permission("notifications.update"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    batch_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> OutboxProcessResponse:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    return await NotificationService.process_outbox_batch(db, batch_size=batch_size)


@router.get("/templates", response_model=list[NotificationTemplateResponse])
async def list_templates(
    principal: Annotated[SecurityPrincipal, Depends(require_permission("notifications.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    channel: Annotated[str | None, Query()] = None,
) -> list[NotificationTemplateResponse]:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    stmt = select(NotificationTemplate).where(
        (NotificationTemplate.tenant_id == principal.tenant_id)
        | (NotificationTemplate.tenant_id.is_(None))
    )
    if channel:
        stmt = stmt.where(NotificationTemplate.channel == channel)

    stmt = stmt.order_by(NotificationTemplate.code.asc(), NotificationTemplate.version.desc())
    templates = (await db.execute(stmt)).scalars().all()
    return [NotificationTemplateResponse.model_validate(t) for t in templates]


@router.post("/templates", response_model=NotificationTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_or_override_template(
    data: NotificationTemplateCreateRequest,
    principal: Annotated[SecurityPrincipal, Depends(require_permission("notifications.update"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationTemplateResponse:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    template = NotificationTemplate(
        tenant_id=principal.tenant_id,
        code=data.code,
        channel=data.channel,
        language=data.language,
        version=data.version,
        subject_template=data.subject_template,
        body_template=data.body_template,
        is_active=data.is_active,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return NotificationTemplateResponse.model_validate(template)


@router.post("/send-direct", response_model=NotificationMessageResponse, status_code=status.HTTP_200_OK)
async def send_direct_notification(
    data: NotificationDirectSendRequest,
    principal: Annotated[SecurityPrincipal, Depends(require_permission("notifications.update"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationMessageResponse:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    msg = await NotificationService.dispatch_single_message(
        db,
        tenant_id=principal.tenant_id,
        recipient=data.recipient,
        channel=data.channel,
        template_code=data.template_code,
        context=data.context,
        idempotency_key=data.idempotency_key,
    )
    return NotificationMessageResponse.model_validate(msg)


@router.get("/audit-logs", response_model=list[NotificationAuditLogResponse])
async def list_audit_logs(
    principal: Annotated[SecurityPrincipal, Depends(require_permission("notifications.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    message_id: Annotated[UUID | None, Query()] = None,
    event_type: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[NotificationAuditLogResponse]:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    stmt = select(NotificationAuditLog).where(NotificationAuditLog.tenant_id == principal.tenant_id)
    if message_id:
        stmt = stmt.where(NotificationAuditLog.message_id == message_id)
    if event_type:
        stmt = stmt.where(NotificationAuditLog.event_type == event_type)

    stmt = stmt.order_by(NotificationAuditLog.created_at.desc()).limit(limit).offset(offset)
    logs = (await db.execute(stmt)).scalars().all()
    return [NotificationAuditLogResponse.model_validate(l) for l in logs]


@router.get("/messages", response_model=list[NotificationMessageResponse])
async def list_messages(
    principal: Annotated[SecurityPrincipal, Depends(require_permission("notifications.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    channel: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[NotificationMessageResponse]:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    stmt = select(NotificationMessage).where(NotificationMessage.tenant_id == principal.tenant_id)
    if channel:
        stmt = stmt.where(NotificationMessage.channel == channel)
    if status_filter:
        stmt = stmt.where(NotificationMessage.status == status_filter)

    stmt = stmt.order_by(NotificationMessage.created_at.desc()).limit(limit).offset(offset)
    messages = (await db.execute(stmt)).scalars().all()
    return [NotificationMessageResponse.model_validate(m) for m in messages]


@router.get("/messages/{message_id}", response_model=NotificationMessageResponse)
async def get_message(
    message_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(require_permission("notifications.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationMessageResponse:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    stmt = select(NotificationMessage).where(
        NotificationMessage.id == message_id,
        NotificationMessage.tenant_id == principal.tenant_id,
    )
    msg = (await db.execute(stmt)).scalar_one_or_none()
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "MESSAGE_NOT_FOUND", "message": "Notification message not found."},
        )
    return NotificationMessageResponse.model_validate(msg)


@router.post("/messages/{message_id}/retry", response_model=NotificationMessageResponse)
async def retry_message(
    message_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(require_permission("notifications.update"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationMessageResponse:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    msg = await NotificationService.retry_notification_message(
        db,
        tenant_id=principal.tenant_id,
        message_id=message_id,
        actor_id=principal.user_id,
    )
    return NotificationMessageResponse.model_validate(msg)
