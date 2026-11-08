from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.payments.services import PaymentService

router = APIRouter(prefix="/payments/webhooks", tags=["Payment Webhooks"])


@router.post("/{provider}", status_code=status.HTTP_200_OK)
async def handle_payment_webhook(
    provider: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Public webhook receiver for third-party payment gateways.
    Authenticated via HMAC-SHA256 signatures, timestamp drift checks, and replay deduplication.
    """
    raw_body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    return await PaymentService.process_webhook(
        db,
        provider_name=provider,
        raw_body=raw_body,
        headers=headers,
    )
