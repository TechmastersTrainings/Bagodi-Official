from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, get_security_principal
from app.db.session import get_db
from app.modules.orders.models import Order, PaymentTransaction
from app.modules.payments.models import Refund
from app.modules.payments.schemas import (
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentTransactionResponse,
    PaymentVerifyRequest,
    RefundResponse,
)
from app.modules.payments.services import PaymentService

router = APIRouter(prefix="", tags=["Customer Payments"])


@router.post(
    "/payments/initiate", response_model=PaymentInitiateResponse, status_code=status.HTTP_200_OK
)
async def initiate_payment(
    data: PaymentInitiateRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentInitiateResponse:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    return await PaymentService.initiate_payment(
        db,
        tenant_id=principal.tenant_id,
        data=data,
        customer_id=principal.user_id,
    )


@router.post(
    "/payments/verify", response_model=PaymentTransactionResponse, status_code=status.HTTP_200_OK
)
async def verify_payment(
    data: PaymentVerifyRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentTransactionResponse:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    txn = await PaymentService.verify_payment(
        db,
        tenant_id=principal.tenant_id,
        data=data,
        customer_id=principal.user_id,
    )
    return PaymentTransactionResponse.model_validate(txn)


@router.get("/orders/{order_id}/payments", response_model=list[PaymentTransactionResponse])
async def get_order_payments(
    order_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PaymentTransactionResponse]:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    stmt = select(Order).where(Order.id == order_id, Order.tenant_id == principal.tenant_id)
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ORDER_NOT_FOUND", "message": "Order not found."},
        )

    if (
        not principal.is_platform_user
        and not principal.has_permission("orders.read")
        and order.customer_id != principal.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": "You cannot access payments for another customer's order.",
            },
        )

    stmt_txns = (
        select(PaymentTransaction)
        .where(
            PaymentTransaction.tenant_id == principal.tenant_id,
            PaymentTransaction.order_id == order_id,
        )
        .order_by(PaymentTransaction.created_at.desc())
    )
    txns = (await db.execute(stmt_txns)).scalars().all()
    return [PaymentTransactionResponse.model_validate(t) for t in txns]


@router.get("/orders/{order_id}/refunds", response_model=list[RefundResponse])
async def get_order_refunds(
    order_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[RefundResponse]:
    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    stmt = select(Order).where(Order.id == order_id, Order.tenant_id == principal.tenant_id)
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ORDER_NOT_FOUND", "message": "Order not found."},
        )

    if (
        not principal.is_platform_user
        and not principal.has_permission("orders.read")
        and order.customer_id != principal.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": "You cannot access refunds for another customer's order.",
            },
        )

    stmt_refunds = (
        select(Refund)
        .where(
            Refund.tenant_id == principal.tenant_id,
            Refund.order_id == order_id,
        )
        .order_by(Refund.created_at.desc())
    )
    refunds = (await db.execute(stmt_refunds)).scalars().all()
    return [RefundResponse.model_validate(r) for r in refunds]
