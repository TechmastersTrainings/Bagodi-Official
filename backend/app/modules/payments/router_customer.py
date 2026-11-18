import math
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, get_security_principal
from app.db.session import get_db
from app.modules.orders.models import Order, PaymentTransaction
from app.modules.payments.models import Refund
from app.modules.payments.schemas import (
    PaginatedPaymentTransactionsResponse,
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentTransactionItemRecord,
    PaymentTransactionResponse,
    PaymentVerifyRequest,
    RefundCreateRequest,
    RefundResponse,
)
from app.modules.payments.services import PaymentService
from app.modules.platform.models import Tenant

router = APIRouter(prefix="", tags=["Customer Payments"])


@router.post(
    "/payments/initiate", response_model=PaymentInitiateResponse, status_code=status.HTTP_200_OK
)
async def initiate_payment(
    data: PaymentInitiateRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
) -> PaymentInitiateResponse:
    target_tenant_id = principal.tenant_id or x_tenant_id
    if not target_tenant_id:
        order_tenant = (
            await db.execute(select(Order.tenant_id).where(Order.id == data.order_id))
        ).scalar_one_or_none()
        if order_tenant:
            target_tenant_id = order_tenant

    if not target_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    return await PaymentService.initiate_payment(
        db,
        tenant_id=target_tenant_id,
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
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
) -> PaymentTransactionResponse:
    target_tenant_id = principal.tenant_id or x_tenant_id
    if not target_tenant_id:
        txn_tenant = (
            await db.execute(
                select(PaymentTransaction.tenant_id).where(
                    PaymentTransaction.id == data.transaction_id
                )
            )
        ).scalar_one_or_none()
        if txn_tenant:
            target_tenant_id = txn_tenant

    if not target_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "Tenant context is required."},
        )

    txn = await PaymentService.verify_payment(
        db,
        tenant_id=target_tenant_id,
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


@router.get(
    "/payments/transactions",
    response_model=PaginatedPaymentTransactionsResponse,
    summary="List payment transactions for merchant financial ledger",
)
async def list_payment_transactions(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    pageSize: Annotated[int, Query(ge=1, le=100)] = 15,
    status: Annotated[str | None, Query()] = None,
    paymentMethod: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
):
    target_tenant_id = principal.tenant_id or x_tenant_id
    if not target_tenant_id:
        active_t = (await db.execute(select(Tenant).where(Tenant.status == "active").limit(1))).scalar_one_or_none()
        if active_t:
            target_tenant_id = active_t.id
        else:
            any_t = (await db.execute(select(Tenant).limit(1))).scalar_one_or_none()
            if any_t:
                target_tenant_id = any_t.id

    conditions = []
    if target_tenant_id:
        conditions.append(PaymentTransaction.tenant_id == target_tenant_id)

    if status and status != "ALL":
        conditions.append(PaymentTransaction.status.ilike(status))
    if paymentMethod and paymentMethod != "ALL":
        conditions.append(PaymentTransaction.payment_method.ilike(paymentMethod))

    count_stmt = select(func.count(PaymentTransaction.id)).where(*conditions)
    total_count = (await db.execute(count_stmt)).scalar() or 0

    eff_offset = (page - 1) * pageSize
    stmt = (
        select(PaymentTransaction, Order)
        .join(Order, PaymentTransaction.order_id == Order.id, isouter=True)
        .where(*conditions)
        .order_by(PaymentTransaction.created_at.desc())
        .offset(eff_offset)
        .limit(pageSize)
    )
    results = (await db.execute(stmt)).all()

    items = []
    for txn, ord_rec in results:
        items.append(
            PaymentTransactionItemRecord(
                id=str(txn.id),
                orderId=str(txn.order_id),
                orderNumber=ord_rec.order_number if ord_rec else str(txn.order_id)[:8],
                customerName=ord_rec.customer_name if ord_rec else None,
                amount=float(txn.amount),
                currency=txn.currency,
                paymentMethod=txn.payment_method.upper(),
                status=txn.status.upper(),
                gatewayTransactionId=txn.gateway_payment_id or txn.transaction_reference,
                settlementBatchId=None,
                createdAt=txn.created_at.isoformat() if txn.created_at else "",
                refundedAmount=float(txn.amount_refunded or 0.0),
            )
        )

    total_pages = math.ceil(total_count / pageSize) if pageSize > 0 else 1

    return PaginatedPaymentTransactionsResponse(
        items=items,
        total=total_count,
        page=page,
        pageSize=pageSize,
        totalPages=total_pages,
    )


@router.post(
    "/payments/refunds",
    response_model=RefundResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Process payment transaction refund",
)
async def process_payment_refund(
    data: RefundCreateRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
):
    target_tenant_id = principal.tenant_id or x_tenant_id
    if not target_tenant_id:
        active_t = (await db.execute(select(Tenant).where(Tenant.status == "active").limit(1))).scalar_one_or_none()
        target_tenant_id = active_t.id if active_t else None

    if not target_tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")

    return await PaymentService.create_refund(
        db=db,
        tenant_id=target_tenant_id,
        user_id=principal.user_id or target_tenant_id,
        data=data,
    )
