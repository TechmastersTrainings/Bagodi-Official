from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.notifications.services import NotificationService

router = APIRouter(prefix="/notifications/webhooks", tags=["Notification Delivery Webhooks (DLR)"])


@router.post("/{provider}", status_code=status.HTTP_200_OK)
async def handle_delivery_webhook(
    provider: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Public delivery receipt (DLR) webhook receiver for SMS, WhatsApp, and Email providers.
    Cryptographically authenticated via provider signatures.
    """
    raw_body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    return await NotificationService.handle_delivery_report(
        db,
        provider_name=provider,
        raw_body=raw_body,
        headers=headers,
    )
