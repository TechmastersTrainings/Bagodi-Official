from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PaymentInitiateRequest(BaseModel):
    order_id: UUID
    payment_method: str = Field(default="online", max_length=30)
    gateway_provider: str | None = Field(default=None, max_length=50)
    return_url: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=100)


class PaymentInitiateResponse(BaseModel):
    transaction_id: UUID
    transaction_reference: str
    order_id: UUID
    order_number: str
    amount: Decimal
    currency: str
    status: str
    gateway_provider: str
    gateway_order_id: str | None
    checkout_url: str | None
    checkout_payload: dict[str, Any]


class PaymentVerifyRequest(BaseModel):
    transaction_id: UUID
    gateway_order_id: str = Field(max_length=100)
    gateway_payment_id: str = Field(max_length=100)
    gateway_signature: str = Field(max_length=255)


class PaymentTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    order_id: UUID
    transaction_reference: str
    payment_method: str
    amount: Decimal
    amount_refunded: Decimal
    currency: str
    status: str
    gateway_provider: str
    gateway_order_id: str | None
    gateway_payment_id: str | None
    gateway_fee: Decimal
    gateway_tax: Decimal
    captured_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RefundCreateRequest(BaseModel):
    payment_transaction_id: UUID | None = None
    amount: Decimal | None = Field(
        default=None, gt=Decimal("0.00"), description="Leave null for full remaining balance"
    )
    reason: str = Field(max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=100)


class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    order_id: UUID
    payment_transaction_id: UUID
    refund_reference: str
    gateway_refund_id: str | None
    idempotency_key: str | None
    amount: Decimal
    currency: str
    status: str
    reason: str
    initiated_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class CodCollectionRequest(BaseModel):
    amount_collected: Decimal = Field(gt=Decimal("0.00"))
    collected_by_name: str = Field(min_length=2, max_length=150)
    collected_at: datetime | None = None
    notes: str | None = None


class CodReconcileRequest(BaseModel):
    bank_deposit_reference: str = Field(min_length=3, max_length=100)
    notes: str | None = None


class CodSettlementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    order_id: UUID
    payment_transaction_id: UUID
    amount_collected: Decimal
    currency: str
    collected_at: datetime
    collected_by_name: str
    settlement_status: str
    settled_at: datetime | None
    bank_deposit_reference: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ReconciliationSummaryResponse(BaseModel):
    total_captured_amount: Decimal
    total_refunded_amount: Decimal
    net_settled_amount: Decimal
    total_gateway_fees: Decimal
    total_gateway_taxes: Decimal
    cod_collected_amount: Decimal
    cod_pending_deposit_amount: Decimal
    cod_reconciled_amount: Decimal
    transactions_count: int
    refunds_count: int


class PaymentAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    order_id: UUID | None
    payment_id: UUID | None
    refund_id: UUID | None
    event_type: str
    actor_id: UUID | None
    payload: dict[str, Any]
    created_at: datetime


class PaymentTransactionItemRecord(BaseModel):
    id: str
    orderId: str
    orderNumber: str
    customerName: str | None = None
    amount: float
    currency: str = "INR"
    paymentMethod: str
    status: str
    gatewayTransactionId: str | None = None
    settlementBatchId: str | None = None
    createdAt: str
    refundedAmount: float = 0.0


class PaginatedPaymentTransactionsResponse(BaseModel):
    items: list[PaymentTransactionItemRecord]
    total: int
    page: int
    pageSize: int
    totalPages: int
