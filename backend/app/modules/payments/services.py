from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.identity.models import User
from app.modules.orders.models import Order, OrderStatusHistory, PaymentTransaction
from app.modules.payments.models import (
    CodSettlement,
    PaymentAuditLog,
    ProcessedWebhookEvent,
    Refund,
)
from app.modules.payments.providers import PaymentGatewayFactory
from app.modules.payments.schemas import (
    CodCollectionRequest,
    CodReconcileRequest,
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentVerifyRequest,
    ReconciliationSummaryResponse,
    RefundCreateRequest,
)


async def _resolve_user_id(db: AsyncSession, user_id: UUID | None) -> UUID | None:
    if not user_id:
        return None
    stmt = select(User.id).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


class PaymentService:
    @staticmethod
    async def log_audit_event(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        order_id: UUID | None = None,
        payment_id: UUID | None = None,
        refund_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> PaymentAuditLog:
        valid_actor_id = await _resolve_user_id(db, actor_id)
        audit_entry = PaymentAuditLog(
            tenant_id=tenant_id,
            order_id=order_id,
            payment_id=payment_id,
            refund_id=refund_id,
            event_type=event_type,
            actor_id=valid_actor_id,
            payload=payload,
            created_at=datetime.now(UTC),
        )
        db.add(audit_entry)
        return audit_entry

    @staticmethod
    async def initiate_payment(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        data: PaymentInitiateRequest,
        actor_id: UUID | None = None,
        customer_id: UUID | None = None,
    ) -> PaymentInitiateResponse:
        # 1. Fetch order
        stmt = (
            select(Order)
            .where(Order.id == data.order_id, Order.tenant_id == tenant_id)
            .options(selectinload(Order.payments))
        )
        order = (await db.execute(stmt)).scalar_one_or_none()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ORDER_NOT_FOUND", "message": "Order not found."},
            )

        # Customer ownership validation
        if customer_id and order.customer_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "You cannot initiate payment for another customer's order."},
            )

        if order.payment_status == "captured":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "ORDER_ALREADY_PAID", "message": "Order is already paid and captured."},
            )

        if order.status in ("CANCELLED", "RETURNED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_ORDER_STATUS", "message": f"Cannot initiate payment for {order.status} order."},
            )

        # 2. Idempotency Check
        if data.idempotency_key:
            stmt_idemp = select(PaymentTransaction).where(
                PaymentTransaction.tenant_id == tenant_id,
                PaymentTransaction.idempotency_key == data.idempotency_key,
            )
            existing_txn = (await db.execute(stmt_idemp)).scalar_one_or_none()
            if existing_txn:
                return PaymentInitiateResponse(
                    transaction_id=existing_txn.id,
                    transaction_reference=existing_txn.transaction_reference,
                    order_id=order.id,
                    order_number=order.order_number,
                    amount=existing_txn.amount,
                    currency=existing_txn.currency,
                    status=existing_txn.status,
                    gateway_provider=existing_txn.gateway_provider,
                    gateway_order_id=existing_txn.gateway_order_id,
                    checkout_url=f"https://checkout.bagodi.test/pay/{existing_txn.gateway_order_id}"
                    if existing_txn.gateway_order_id
                    else None,
                    checkout_payload=existing_txn.gateway_payload or {},
                )

        # 3. Resolve Provider
        provider = PaymentGatewayFactory.get_provider(data.gateway_provider or data.payment_method)

        # 4. Find or Create Payment Transaction
        pending_txn = next(
            (t for t in order.payments if t.status in ("initiated", "pending") and t.payment_method == data.payment_method),
            None,
        )

        if not pending_txn:
            txn_ref = f"TXN-{order.order_number}-{uuid4().hex[:4].upper()}"
            pending_txn = PaymentTransaction(
                tenant_id=tenant_id,
                order_id=order.id,
                transaction_reference=txn_ref,
                payment_method=data.payment_method,
                amount=order.total_amount,
                currency=order.currency,
                status="initiated",
                gateway_provider=provider.provider_name,
                idempotency_key=data.idempotency_key,
            )
            order.payments.append(pending_txn)
            db.add(pending_txn)
            await db.flush()

        # 5. Call Provider Initiation
        init_result = await provider.initiate_payment(
            tenant_id=tenant_id,
            transaction_id=pending_txn.id,
            order_number=order.order_number,
            amount=order.total_amount,
            currency=order.currency,
            customer_info={
                "name": order.customer_name,
                "email": order.customer_email,
                "phone": order.customer_phone,
            },
            return_url=data.return_url,
        )

        pending_txn.gateway_order_id = init_result.gateway_order_id
        pending_txn.gateway_payload = init_result.checkout_payload
        pending_txn.status = init_result.status
        if data.idempotency_key:
            pending_txn.idempotency_key = data.idempotency_key

        # 6. Audit Log
        await PaymentService.log_audit_event(
            db,
            tenant_id=tenant_id,
            order_id=order.id,
            payment_id=pending_txn.id,
            actor_id=actor_id or customer_id,
            event_type="PAYMENT_INITIATED",
            payload={
                "gateway_order_id": init_result.gateway_order_id,
                "amount": str(order.total_amount),
                "provider": provider.provider_name,
            },
        )

        await db.commit()
        await db.refresh(pending_txn)

        return PaymentInitiateResponse(
            transaction_id=pending_txn.id,
            transaction_reference=pending_txn.transaction_reference,
            order_id=order.id,
            order_number=order.order_number,
            amount=pending_txn.amount,
            currency=pending_txn.currency,
            status=pending_txn.status,
            gateway_provider=pending_txn.gateway_provider,
            gateway_order_id=pending_txn.gateway_order_id,
            checkout_url=init_result.checkout_url,
            checkout_payload=init_result.checkout_payload,
        )

    @staticmethod
    async def verify_payment(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        data: PaymentVerifyRequest,
        actor_id: UUID | None = None,
        customer_id: UUID | None = None,
    ) -> PaymentTransaction:
        # 1. Fetch transaction
        stmt = (
            select(PaymentTransaction)
            .where(PaymentTransaction.id == data.transaction_id, PaymentTransaction.tenant_id == tenant_id)
            .options(selectinload(PaymentTransaction.order).selectinload(Order.status_history))
        )
        txn = (await db.execute(stmt)).scalar_one_or_none()
        if not txn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "TRANSACTION_NOT_FOUND", "message": "Payment transaction not found."},
            )

        order = txn.order
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ORDER_NOT_FOUND", "message": "Associated order not found."},
            )

        if customer_id and order.customer_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "You cannot verify payment for another customer's order."},
            )

        # Idempotent response if already captured
        if txn.status == "captured":
            return txn

        if txn.status not in ("initiated", "pending"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_TRANSACTION_STATUS", "message": f"Transaction in status '{txn.status}' cannot be verified."},
            )

        # 2. Cryptographic signature verification via provider
        provider = PaymentGatewayFactory.get_provider(txn.gateway_provider)
        verification = await provider.verify_payment(
            tenant_id=tenant_id,
            gateway_order_id=data.gateway_order_id,
            gateway_payment_id=data.gateway_payment_id,
            gateway_signature=data.gateway_signature,
            amount=txn.amount,
            currency=txn.currency,
        )

        valid_actor_id = await _resolve_user_id(db, actor_id or customer_id)

        if not verification.is_valid:
            txn.status = "failed"
            txn.error_message = verification.error_message
            await PaymentService.log_audit_event(
                db,
                tenant_id=tenant_id,
                order_id=order.id,
                payment_id=txn.id,
                actor_id=valid_actor_id,
                event_type="PAYMENT_FAILED",
                payload={"error": verification.error_message, "gateway_payment_id": data.gateway_payment_id},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "PAYMENT_VERIFICATION_FAILED", "message": verification.error_message or "Signature mismatch"},
            )

        # 3. Successful Capture Mutation
        txn.status = "captured"
        txn.captured_at = datetime.now(UTC)
        txn.gateway_order_id = data.gateway_order_id
        txn.gateway_payment_id = data.gateway_payment_id
        txn.gateway_signature = data.gateway_signature
        txn.gateway_fee = verification.fee
        txn.gateway_tax = verification.tax
        txn.gateway_payload = verification.raw_response

        order.payment_status = "captured"
        if order.status == "PENDING_PAYMENT":
            order.status = "CONFIRMED"
            order.status_history.append(
                OrderStatusHistory(
                    from_status="PENDING_PAYMENT",
                    to_status="CONFIRMED",
                    notes=f"Payment captured ({data.gateway_payment_id})",
                    changed_by_user_id=valid_actor_id,
                )
            )

        await PaymentService.log_audit_event(
            db,
            tenant_id=tenant_id,
            order_id=order.id,
            payment_id=txn.id,
            actor_id=valid_actor_id,
            event_type="PAYMENT_CAPTURED",
            payload={
                "gateway_order_id": data.gateway_order_id,
                "gateway_payment_id": data.gateway_payment_id,
                "fee": str(verification.fee),
                "tax": str(verification.tax),
            },
        )

        await db.commit()
        await db.refresh(txn)
        return txn

    @staticmethod
    async def process_webhook(
        db: AsyncSession,
        *,
        provider_name: str,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        provider = PaymentGatewayFactory.get_provider(provider_name)
        webhook_result = await provider.process_webhook(raw_body=raw_body, headers=headers)

        if not webhook_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_WEBHOOK", "message": webhook_result.error_message or "Webhook verification failed"},
            )

        # Locate transaction by gateway_order_id or gateway_payment_id
        stmt = (
            select(PaymentTransaction)
            .where(
                (PaymentTransaction.gateway_order_id == webhook_result.gateway_order_id)
                | (PaymentTransaction.gateway_payment_id == webhook_result.gateway_payment_id)
            )
            .options(selectinload(PaymentTransaction.order).selectinload(Order.status_history))
        )
        txn = (await db.execute(stmt)).scalars().first()
        if not txn:
            # Acknowledge unmapped webhook gracefully to avoid gateway retries
            return {"status": "unmapped_order_ignored", "event_id": webhook_result.event_id}

        tenant_id = txn.tenant_id

        # Replay Protection check
        stmt_dedup = select(ProcessedWebhookEvent).where(
            ProcessedWebhookEvent.tenant_id == tenant_id,
            ProcessedWebhookEvent.provider == provider.provider_name,
            ProcessedWebhookEvent.event_id == webhook_result.event_id,
        )
        existing_event = (await db.execute(stmt_dedup)).scalar_one_or_none()
        if existing_event:
            return {"status": "already_processed", "event_id": webhook_result.event_id}

        # Apply state changes based on webhook status
        if webhook_result.status == "captured" and txn.status != "captured":
            txn.status = "captured"
            txn.captured_at = datetime.now(UTC)
            if webhook_result.gateway_payment_id:
                txn.gateway_payment_id = webhook_result.gateway_payment_id
            txn.gateway_fee = webhook_result.fee
            txn.gateway_tax = webhook_result.tax

            order = txn.order
            if order:
                order.payment_status = "captured"
                if order.status == "PENDING_PAYMENT":
                    order.status = "CONFIRMED"
                    order.status_history.append(
                        OrderStatusHistory(
                            from_status="PENDING_PAYMENT",
                            to_status="CONFIRMED",
                            notes=f"Payment captured via webhook ({webhook_result.event_id})",
                            changed_by_user_id=None,
                        )
                    )

            await PaymentService.log_audit_event(
                db,
                tenant_id=tenant_id,
                order_id=order.id if order else None,
                payment_id=txn.id,
                event_type="PAYMENT_CAPTURED",
                payload={"source": "webhook", "event_id": webhook_result.event_id},
            )
        elif webhook_result.status == "failed" and txn.status != "captured":
            txn.status = "failed"
            txn.error_message = webhook_result.error_message or "Payment failed via gateway webhook"
            await PaymentService.log_audit_event(
                db,
                tenant_id=tenant_id,
                order_id=txn.order_id,
                payment_id=txn.id,
                event_type="PAYMENT_FAILED",
                payload={"source": "webhook", "event_id": webhook_result.event_id},
            )

        # Record processed event
        processed_record = ProcessedWebhookEvent(
            tenant_id=tenant_id,
            provider=provider.provider_name,
            event_id=webhook_result.event_id,
            event_type=webhook_result.event_type,
            processed_at=datetime.now(UTC),
            payload=webhook_result.raw_payload,
        )
        db.add(processed_record)

        await db.commit()
        return {"status": "processed", "event_id": webhook_result.event_id}

    @staticmethod
    async def create_refund(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        order_id: UUID,
        data: RefundCreateRequest,
        actor_id: UUID | None = None,
    ) -> Refund:
        # 1. Fetch order
        stmt = (
            select(Order)
            .where(Order.id == order_id, Order.tenant_id == tenant_id)
            .options(selectinload(Order.payments))
        )
        order = (await db.execute(stmt)).scalar_one_or_none()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ORDER_NOT_FOUND", "message": "Order not found."},
            )

        # 2. Idempotency Check
        if data.idempotency_key:
            stmt_idemp = select(Refund).where(
                Refund.tenant_id == tenant_id,
                Refund.idempotency_key == data.idempotency_key,
            )
            existing_refund = (await db.execute(stmt_idemp)).scalar_one_or_none()
            if existing_refund:
                return existing_refund

        # 3. Locate target captured payment transaction
        if data.payment_transaction_id:
            txn = next((t for t in order.payments if t.id == data.payment_transaction_id), None)
            if not txn:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "TRANSACTION_NOT_FOUND", "message": "Specified transaction not found on this order."},
                )
        else:
            txn = next((t for t in order.payments if t.status in ("captured", "partially_refunded", "refunded")), None)
            if not txn:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "NO_CAPTURED_PAYMENT", "message": "No captured payment transaction available for refund."},
                )

        if txn.status not in ("captured", "partially_refunded", "refunded"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_TRANSACTION_STATUS", "message": f"Cannot refund transaction in status '{txn.status}'."},
            )

        # 4. Validate Refundable Amount
        max_refundable = txn.amount - txn.amount_refunded
        if max_refundable <= Decimal("0.00") or txn.status == "refunded":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "ALREADY_FULLY_REFUNDED", "message": "Transaction is already fully refunded."},
            )

        target_amount = data.amount if data.amount is not None else max_refundable
        if target_amount <= Decimal("0.00"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REFUND_AMOUNT", "message": "Refund amount must be greater than zero."},
            )

        if target_amount > max_refundable:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "REFUND_EXCEEDS_BALANCE",
                    "message": f"Requested refund {target_amount} exceeds maximum refundable balance {max_refundable}.",
                },
            )

        # 5. Process refund via provider
        provider = PaymentGatewayFactory.get_provider(txn.gateway_provider)
        refund_ref = f"RFD-{order.order_number}-{uuid4().hex[:6].upper()}"

        refund_result = await provider.process_refund(
            tenant_id=tenant_id,
            payment_transaction_id=txn.id,
            gateway_payment_id=txn.gateway_payment_id,
            refund_reference=refund_ref,
            amount=target_amount,
            currency=txn.currency,
            reason=data.reason,
        )

        if not refund_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "REFUND_FAILED", "message": refund_result.error_message or "Refund processing failed."},
            )

        valid_actor_id = await _resolve_user_id(db, actor_id)

        # 6. Record Refund entity
        refund = Refund(
            tenant_id=tenant_id,
            order_id=order.id,
            payment_transaction_id=txn.id,
            refund_reference=refund_ref,
            gateway_refund_id=refund_result.gateway_refund_id,
            idempotency_key=data.idempotency_key,
            amount=target_amount,
            currency=txn.currency,
            status=refund_result.status,
            reason=data.reason,
            initiated_by_user_id=valid_actor_id,
            gateway_payload=refund_result.raw_response,
        )
        db.add(refund)

        # 7. Update transaction and order states
        txn.amount_refunded += target_amount
        if txn.amount_refunded >= txn.amount:
            txn.status = "refunded"
            order.payment_status = "refunded"
        else:
            txn.status = "partially_refunded"
            order.payment_status = "partially_refunded"

        await PaymentService.log_audit_event(
            db,
            tenant_id=tenant_id,
            order_id=order.id,
            payment_id=txn.id,
            refund_id=refund.id,
            actor_id=valid_actor_id,
            event_type="REFUND_SUCCEEDED",
            payload={
                "refund_reference": refund_ref,
                "amount": str(target_amount),
                "gateway_refund_id": refund_result.gateway_refund_id,
            },
        )

        await db.commit()
        await db.refresh(refund)
        return refund

    @staticmethod
    async def record_cod_collection(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        order_id: UUID,
        data: CodCollectionRequest,
        actor_id: UUID | None = None,
    ) -> CodSettlement:
        # 1. Fetch order
        stmt = (
            select(Order)
            .where(Order.id == order_id, Order.tenant_id == tenant_id)
            .options(selectinload(Order.payments))
        )
        order = (await db.execute(stmt)).scalar_one_or_none()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ORDER_NOT_FOUND", "message": "Order not found."},
            )

        if order.payment_method != "cod":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "NOT_COD_ORDER", "message": "Order payment method is not Cash-On-Delivery."},
            )

        # Check existing settlement
        stmt_settle = select(CodSettlement).where(
            CodSettlement.tenant_id == tenant_id,
            CodSettlement.order_id == order_id,
        )
        existing_settlement = (await db.execute(stmt_settle)).scalar_one_or_none()
        if existing_settlement:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "COD_ALREADY_COLLECTED", "message": "COD settlement already recorded for this order."},
            )

        # 2. Find or create COD payment transaction
        txn = next((t for t in order.payments if t.payment_method == "cod"), None)
        if not txn:
            txn = PaymentTransaction(
                tenant_id=tenant_id,
                order_id=order.id,
                transaction_reference=f"TXN-{order.order_number}-COD",
                payment_method="cod",
                amount=order.total_amount,
                currency=order.currency,
                status="pending",
                gateway_provider="cod",
            )
            order.payments.append(txn)
            db.add(txn)
            await db.flush()

        collected_timestamp = data.collected_at or datetime.now(UTC)

        settlement = CodSettlement(
            tenant_id=tenant_id,
            order_id=order.id,
            payment_transaction_id=txn.id,
            amount_collected=data.amount_collected,
            currency=order.currency,
            collected_at=collected_timestamp,
            collected_by_name=data.collected_by_name,
            settlement_status="pending_deposit",
            notes=data.notes,
        )
        db.add(settlement)

        txn.status = "captured"
        txn.captured_at = collected_timestamp
        order.payment_status = "captured"

        valid_actor_id = await _resolve_user_id(db, actor_id)

        await PaymentService.log_audit_event(
            db,
            tenant_id=tenant_id,
            order_id=order.id,
            payment_id=txn.id,
            actor_id=valid_actor_id,
            event_type="COD_COLLECTED",
            payload={
                "amount_collected": str(data.amount_collected),
                "collected_by": data.collected_by_name,
            },
        )

        await db.commit()
        await db.refresh(settlement)
        return settlement

    @staticmethod
    async def reconcile_cod_settlement(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        settlement_id: UUID,
        data: CodReconcileRequest,
        actor_id: UUID | None = None,
    ) -> CodSettlement:
        stmt = select(CodSettlement).where(
            CodSettlement.id == settlement_id,
            CodSettlement.tenant_id == tenant_id,
        )
        settlement = (await db.execute(stmt)).scalar_one_or_none()
        if not settlement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "SETTLEMENT_NOT_FOUND", "message": "COD settlement record not found."},
            )

        if settlement.settlement_status == "reconciled":
            return settlement

        settlement.settlement_status = "reconciled"
        settlement.bank_deposit_reference = data.bank_deposit_reference
        settlement.settled_at = datetime.now(UTC)
        if data.notes:
            settlement.notes = f"{settlement.notes or ''}\n{data.notes}".strip()

        valid_actor_id = await _resolve_user_id(db, actor_id)

        await PaymentService.log_audit_event(
            db,
            tenant_id=tenant_id,
            order_id=settlement.order_id,
            payment_id=settlement.payment_transaction_id,
            actor_id=valid_actor_id,
            event_type="COD_RECONCILED",
            payload={
                "settlement_id": str(settlement.id),
                "bank_deposit_reference": data.bank_deposit_reference,
            },
        )

        await db.commit()
        await db.refresh(settlement)
        return settlement

    @staticmethod
    async def get_reconciliation_summary(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> ReconciliationSummaryResponse:
        # Aggregations across payments
        txn_stmt = select(
            func.coalesce(func.sum(PaymentTransaction.amount), Decimal("0.00")),
            func.coalesce(func.sum(PaymentTransaction.amount_refunded), Decimal("0.00")),
            func.coalesce(func.sum(PaymentTransaction.gateway_fee), Decimal("0.00")),
            func.coalesce(func.sum(PaymentTransaction.gateway_tax), Decimal("0.00")),
            func.count(PaymentTransaction.id),
        ).where(
            PaymentTransaction.tenant_id == tenant_id,
            PaymentTransaction.status.in_(["captured", "partially_refunded", "refunded"]),
        )
        if from_date:
            txn_stmt = txn_stmt.where(PaymentTransaction.captured_at >= from_date)
        if to_date:
            txn_stmt = txn_stmt.where(PaymentTransaction.captured_at <= to_date)

        txn_res = (await db.execute(txn_stmt)).one()
        captured_total = Decimal(str(txn_res[0]))
        refunded_total = Decimal(str(txn_res[1]))
        fees_total = Decimal(str(txn_res[2]))
        taxes_total = Decimal(str(txn_res[3]))
        txn_count = int(txn_res[4])

        # Refunds count
        rfd_stmt = select(func.count(Refund.id)).where(
            Refund.tenant_id == tenant_id,
            Refund.status == "succeeded",
        )
        if from_date:
            rfd_stmt = rfd_stmt.where(Refund.created_at >= from_date)
        if to_date:
            rfd_stmt = rfd_stmt.where(Refund.created_at <= to_date)
        rfd_count = int((await db.execute(rfd_stmt)).scalar() or 0)

        # COD aggregations
        cod_stmt = select(
            func.coalesce(func.sum(CodSettlement.amount_collected), Decimal("0.00")),
            func.coalesce(
                func.sum(
                    case(
                        (CodSettlement.settlement_status == "pending_deposit", CodSettlement.amount_collected),
                        else_=Decimal("0.00"),
                    )
                ),
                Decimal("0.00"),
            ),
            func.coalesce(
                func.sum(
                    case(
                        (CodSettlement.settlement_status == "reconciled", CodSettlement.amount_collected),
                        else_=Decimal("0.00"),
                    )
                ),
                Decimal("0.00"),
            ),
        ).where(CodSettlement.tenant_id == tenant_id)
        if from_date:
            cod_stmt = cod_stmt.where(CodSettlement.collected_at >= from_date)
        if to_date:
            cod_stmt = cod_stmt.where(CodSettlement.collected_at <= to_date)

        cod_res = (await db.execute(cod_stmt)).one()
        cod_collected = Decimal(str(cod_res[0]))
        cod_pending = Decimal(str(cod_res[1]))
        cod_reconciled = Decimal(str(cod_res[2]))

        net_settled = captured_total - refunded_total - fees_total - taxes_total

        return ReconciliationSummaryResponse(
            total_captured_amount=captured_total,
            total_refunded_amount=refunded_total,
            net_settled_amount=net_settled,
            total_gateway_fees=fees_total,
            total_gateway_taxes=taxes_total,
            cod_collected_amount=cod_collected,
            cod_pending_deposit_amount=cod_pending,
            cod_reconciled_amount=cod_reconciled,
            transactions_count=txn_count,
            refunds_count=rfd_count,
        )

    @staticmethod
    async def trigger_order_refund_if_captured(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        order: Order,
        reason: str,
        actor_id: UUID | None = None,
    ) -> Refund | None:
        """Triggered automatically upon order cancellation or return if funds were captured."""
        if order.payment_status not in ("captured", "partially_refunded"):
            return None

        # Find captured transaction
        stmt = select(PaymentTransaction).where(
            PaymentTransaction.tenant_id == tenant_id,
            PaymentTransaction.order_id == order.id,
            PaymentTransaction.status.in_(["captured", "partially_refunded"]),
        )
        txn = (await db.execute(stmt)).scalars().first()
        if not txn:
            return None

        refundable_balance = txn.amount - txn.amount_refunded
        if refundable_balance <= Decimal("0.00"):
            return None

        return await PaymentService.create_refund(
            db,
            tenant_id=tenant_id,
            order_id=order.id,
            data=RefundCreateRequest(
                payment_transaction_id=txn.id,
                amount=refundable_balance,
                reason=reason,
            ),
            actor_id=actor_id,
        )
