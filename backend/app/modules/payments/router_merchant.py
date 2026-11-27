from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, require_permission
from app.db.session import get_db
from app.modules.orders.models import PaymentTransaction
from app.modules.payments.models import CodSettlement, PaymentAuditLog, Refund
from app.modules.payments.schemas import (
    CodCollectionRequest,
    CodReconcileRequest,
    CodSettlementResponse,
    PaymentAuditLogResponse,
    PaymentTransactionResponse,
    ReconciliationSummaryResponse,
    RefundCreateRequest,
    RefundResponse,
)
from app.modules.payments.services import PaymentService

router = APIRouter(prefix="/merchant/payments", tags=["Merchant Payments & Reconciliation"])


@router.get("", response_model=list[PaymentTransactionResponse])
@router.get("/transactions", response_model=list[PaymentTransactionResponse])
async def list_payments(
    principal: Annotated[SecurityPrincipal, Depends(require_permission("orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    order_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PaymentTransactionResponse]:
    stmt = select(PaymentTransaction)
    if principal.tenant_id and not principal.is_platform_user:
        stmt = stmt.where(PaymentTransaction.tenant_id == principal.tenant_id)
    if status_filter:
        stmt = stmt.where(PaymentTransaction.status == status_filter)
    if order_id:
        stmt = stmt.where(PaymentTransaction.order_id == order_id)

    stmt = stmt.order_by(PaymentTransaction.created_at.desc()).limit(limit).offset(offset)
    txns = (await db.execute(stmt)).scalars().all()
    return [PaymentTransactionResponse.model_validate(t) for t in txns]


@router.post(
    "/orders/{order_id}/refund", response_model=RefundResponse, status_code=status.HTTP_201_CREATED
)
async def create_refund(
    order_id: UUID,
    data: RefundCreateRequest,
    principal: Annotated[SecurityPrincipal, Depends(require_permission("orders.update"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RefundResponse:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    refund = await PaymentService.create_refund(
        db,
        tenant_id=principal.tenant_id,
        order_id=order_id,
        data=data,
        actor_id=principal.user_id,
    )
    return RefundResponse.model_validate(refund)


@router.get("/refunds/list", response_model=list[RefundResponse])
async def list_refunds(
    principal: Annotated[SecurityPrincipal, Depends(require_permission("orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    order_id: Annotated[UUID | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RefundResponse]:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    stmt = select(Refund).where(Refund.tenant_id == principal.tenant_id)
    if order_id:
        stmt = stmt.where(Refund.order_id == order_id)
    if status_filter:
        stmt = stmt.where(Refund.status == status_filter)

    stmt = stmt.order_by(Refund.created_at.desc()).limit(limit).offset(offset)
    refunds = (await db.execute(stmt)).scalars().all()
    return [RefundResponse.model_validate(r) for r in refunds]


@router.post(
    "/cod/{order_id}/collect",
    response_model=CodSettlementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_cod_collection(
    order_id: UUID,
    data: CodCollectionRequest,
    principal: Annotated[SecurityPrincipal, Depends(require_permission("orders.update"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CodSettlementResponse:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    settlement = await PaymentService.record_cod_collection(
        db,
        tenant_id=principal.tenant_id,
        order_id=order_id,
        data=data,
        actor_id=principal.user_id,
    )
    return CodSettlementResponse.model_validate(settlement)


@router.post("/cod/{settlement_id}/reconcile", response_model=CodSettlementResponse)
async def reconcile_cod_settlement(
    settlement_id: UUID,
    data: CodReconcileRequest,
    principal: Annotated[SecurityPrincipal, Depends(require_permission("orders.update"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CodSettlementResponse:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    settlement = await PaymentService.reconcile_cod_settlement(
        db,
        tenant_id=principal.tenant_id,
        settlement_id=settlement_id,
        data=data,
        actor_id=principal.user_id,
    )
    return CodSettlementResponse.model_validate(settlement)


@router.get("/cod/settlements", response_model=list[CodSettlementResponse])
async def list_cod_settlements(
    principal: Annotated[SecurityPrincipal, Depends(require_permission("orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    settlement_status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CodSettlementResponse]:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    stmt = select(CodSettlement).where(CodSettlement.tenant_id == principal.tenant_id)
    if settlement_status:
        stmt = stmt.where(CodSettlement.settlement_status == settlement_status)

    stmt = stmt.order_by(CodSettlement.created_at.desc()).limit(limit).offset(offset)
    settlements = (await db.execute(stmt)).scalars().all()
    return [CodSettlementResponse.model_validate(s) for s in settlements]


@router.get("/reconciliation/summary", response_model=ReconciliationSummaryResponse)
async def get_reconciliation_summary(
    principal: Annotated[SecurityPrincipal, Depends(require_permission("orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    from_date: Annotated[datetime | None, Query()] = None,
    to_date: Annotated[datetime | None, Query()] = None,
) -> ReconciliationSummaryResponse:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    return await PaymentService.get_reconciliation_summary(
        db,
        tenant_id=principal.tenant_id,
        from_date=from_date,
        to_date=to_date,
    )


@router.get("/audit-logs", response_model=list[PaymentAuditLogResponse])
async def list_audit_logs(
    principal: Annotated[SecurityPrincipal, Depends(require_permission("orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    order_id: Annotated[UUID | None, Query()] = None,
    payment_id: Annotated[UUID | None, Query()] = None,
    event_type: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PaymentAuditLogResponse]:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    stmt = select(PaymentAuditLog).where(PaymentAuditLog.tenant_id == principal.tenant_id)
    if order_id:
        stmt = stmt.where(PaymentAuditLog.order_id == order_id)
    if payment_id:
        stmt = stmt.where(PaymentAuditLog.payment_id == payment_id)
    if event_type:
        stmt = stmt.where(PaymentAuditLog.event_type == event_type)

    stmt = stmt.order_by(PaymentAuditLog.created_at.desc()).limit(limit).offset(offset)
    logs = (await db.execute(stmt)).scalars().all()
    return [PaymentAuditLogResponse.model_validate(log) for log in logs]


@router.get("/{payment_id}", response_model=PaymentTransactionResponse)
async def get_payment(
    payment_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(require_permission("orders.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentTransactionResponse:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    stmt = select(PaymentTransaction).where(
        PaymentTransaction.id == payment_id,
        PaymentTransaction.tenant_id == principal.tenant_id,
    )
    txn = (await db.execute(stmt)).scalar_one_or_none()
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PAYMENT_NOT_FOUND", "message": "Payment transaction not found."},
        )
    return PaymentTransactionResponse.model_validate(txn)
