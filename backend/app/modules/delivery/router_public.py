from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.delivery.schemas import ServiceabilityCheckRequest, ServiceabilityCheckResponse
from app.modules.delivery.services import DeliveryService

router = APIRouter(prefix="/delivery", tags=["Delivery Public & Webhooks"])


@router.post(
    "/serviceability/check",
    response_model=ServiceabilityCheckResponse,
)
async def check_serviceability(
    payload: ServiceabilityCheckRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
):
    target_tenant_id = payload.tenant_id or x_tenant_id
    if not target_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "TENANT_REQUIRED",
                "message": "Tenant identifier is required to check delivery serviceability.",
            },
        )

    return await DeliveryService.check_serviceability(
        db,
        tenant_id=target_tenant_id,
        pincode=payload.pincode,
        order_amount=payload.order_amount,
        total_weight_kg=payload.total_weight_kg,
        store_id=payload.store_id,
    )


@router.post(
    "/webhooks/{provider}",
    status_code=status.HTTP_200_OK,
)
async def handle_courier_webhook(
    provider: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    raw_body = await request.body()
    headers = dict(request.headers)
    return await DeliveryService.process_courier_webhook(
        db,
        provider_name=provider,
        raw_body=raw_body,
        headers=headers,
    )
