# Provider-Independent Payment & Refund Architecture Specification

**Platform Owner:** TechMasters Innovations Private Limited  
**Merchant Scope:** Multi-tenant (Bagodi and future merchants)  
**System Module:** `backend/app/modules/payments`  

---

## 1. Architectural Principles

1. **Provider Independence (Strategy Pattern):**
   Payment processing is decoupled from specific third-party providers (Razorpay, Cashfree, PayU, Stripe). Core business logic, order lifecycle, database schemas, and accounting do not depend on external SDKs or vendor-specific data shapes. Providers are implemented via a standard abstract interface: `BasePaymentGatewayProvider`.
2. **State Separation:**
   Order state (`PENDING_PAYMENT`, `CONFIRMED`, `PROCESSING`, `DISPATCHED`, `DELIVERED`, `CANCELLED`, `RETURNED`) is strictly separated from Payment state (`initiated`, `pending`, `authorized`, `captured`, `failed`, `refunded`, `partially_refunded`). An order only transitions to `CONFIRMED` upon cryptographic verification or authoritative webhook confirmation of payment capture.
3. **Idempotency & Replay Protection:**
   Payment initiation, verification callbacks, gateway webhooks, and refund processing require idempotency keys. Repeated webhook deliveries or network retries will never double-capture funds or double-issue refunds.
4. **Backend-Only Financial Authority:**
   All monetary amounts, currencies, and refund balances are calculated and validated exclusively by the backend. Client-submitted payment amounts are strictly ignored.
5. **Double-Entry & Reconciliation Ledger:**
   Every financial event (initiation, capture, failure, refund, COD collection, bank deposit) generates an immutable entry in `payment_audit_logs`.

---

## 2. Entities & Data Models

### A. Payment Transactions (`payment_transactions`)
Tracks every payment attempt and its lifecycle status.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `tenant_id` | UUID | Owning merchant tenant ID (Foreign Key) |
| `order_id` | UUID | Foreign Key to `orders.id` |
| `transaction_reference` | String(100) | Unique internal reference (e.g. `TXN-ORD...-01`) |
| `idempotency_key` | String(100) (nullable) | Prevents duplicate payment initiations |
| `payment_method` | String(30) | `online`, `cod`, `upi`, `card`, `netbanking` |
| `gateway_provider` | String(50) | Gateway provider key (`mock`, `razorpay`, `cashfree`, `cod`) |
| `gateway_order_id` | String(100) (nullable) | External gateway order identifier |
| `gateway_payment_id` | String(100) (nullable) | External gateway payment/transaction ID |
| `gateway_signature` | String(255) (nullable) | Cryptographic signature from gateway |
| `amount` | Numeric(12, 2) | Total payable transaction amount |
| `amount_refunded` | Numeric(12, 2) | Cumulative refunded amount (default `0.00`) |
| `currency` | String(3) | Currency code (default `INR`) |
| `status` | String(30) | `initiated`, `pending`, `authorized`, `captured`, `failed`, `refunded`, `partially_refunded` |
| `gateway_payload` | JSONB (nullable) | Full raw response/webhook payload for audit |
| `error_message` | Text (nullable) | Gateway error description if failed |
| `captured_at` | DateTime (UTC, nullable) | Timestamp of successful capture |
| `created_at`, `updated_at` | DateTime (UTC) | Timestamps |

### B. Refunds (`refunds`)
Tracks full and partial refunds linked to orders and original payment transactions.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `tenant_id` | UUID | Owning merchant tenant ID |
| `order_id` | UUID | Foreign Key to `orders.id` |
| `payment_transaction_id` | UUID | Foreign Key to `payment_transactions.id` |
| `refund_reference` | String(100) | Unique refund reference (e.g. `RFD-ORD...-01`) |
| `gateway_refund_id` | String(100) (nullable) | External gateway refund ID |
| `idempotency_key` | String(100) (nullable) | Idempotent retry protection |
| `amount` | Numeric(12, 2) | Refunded amount ($> 0$, $\le \text{amount} - \text{amount\_refunded}$) |
| `currency` | String(3) | Currency code (`INR`) |
| `status` | String(30) | `initiated`, `pending`, `succeeded`, `failed` |
| `reason` | String(500) | Business reason (`cancellation`, `customer_return`, `overcharge`) |
| `initiated_by_user_id` | UUID (nullable) | Admin or customer user who initiated refund |
| `gateway_payload` | JSONB (nullable) | Raw gateway response |
| `created_at`, `updated_at` | DateTime (UTC) | Timestamps |

### C. COD Settlements (`cod_settlements`)
Tracks physical cash collection at doorstep and bank reconciliation for Cash-on-Delivery orders.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `tenant_id` | UUID | Owning merchant tenant ID |
| `order_id` | UUID | Foreign Key to `orders.id` (Unique) |
| `payment_transaction_id` | UUID | Foreign Key to `payment_transactions.id` |
| `amount_collected` | Numeric(12, 2) | Exact cash collected at delivery |
| `collected_at` | DateTime (UTC) | Timestamp when cash was handed over |
| `collected_by_name` | String(150) | Delivery executive or store staff name |
| `settlement_status` | String(30) | `pending_deposit`, `deposited_to_bank`, `reconciled`, `discrepancy` |
| `settled_at` | DateTime (UTC, nullable) | Timestamp of bank deposit / reconciliation |
| `bank_deposit_reference` | String(100) (nullable) | Bank challan / NEFT / UPI deposit reference |
| `notes` | Text (nullable) | Notes or discrepancy details |
| `created_at`, `updated_at` | DateTime (UTC) | Timestamps |

### D. Payment Audit Logs (`payment_audit_logs`)
Immutable ledger capturing all lifecycle transitions, webhook events, and financial mutations.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `tenant_id` | UUID | Owning merchant tenant ID |
| `payment_id` | UUID (nullable) | Associated payment transaction ID |
| `refund_id` | UUID (nullable) | Associated refund ID |
| `event_type` | String(50) | `PAYMENT_INITIATED`, `PAYMENT_CAPTURED`, `PAYMENT_FAILED`, `REFUND_INITIATED`, `REFUND_SUCCEEDED`, `COD_COLLECTED`, `COD_RECONCILED`, `WEBHOOK_RECEIVED` |
| `actor_id` | UUID (nullable) | User ID who triggered the action |
| `payload` | JSONB | Complete snapshot of event payload |
| `created_at` | DateTime (UTC) | Event timestamp |

---

## 3. Provider-Independent Gateway Interface

```python
class BasePaymentGatewayProvider(ABC):
    @abstractmethod
    async def initiate_payment(
        self,
        tenant_id: UUID,
        order_number: str,
        amount: Decimal,
        currency: str,
        customer_info: dict,
        return_url: str | None = None,
    ) -> PaymentInitiationResult:
        """Generates payment order / session with external gateway."""
        pass

    @abstractmethod
    async def verify_payment(
        self,
        tenant_id: UUID,
        payment_transaction: PaymentTransaction,
        payload: dict,
        signature: str | None = None,
    ) -> PaymentVerificationResult:
        """Verifies payment signature and returns verified capture status."""
        pass

    @abstractmethod
    async def process_webhook(
        self,
        tenant_id: UUID,
        event_payload: dict,
        signature: str | None = None,
    ) -> WebhookProcessingResult:
        """Parses and verifies gateway webhook event payload."""
        pass

    @abstractmethod
    async def process_refund(
        self,
        tenant_id: UUID,
        payment_transaction: PaymentTransaction,
        refund_amount: Decimal,
        reason: str,
        refund_reference: str,
    ) -> RefundResult:
        """Submits refund request to payment gateway."""
        pass
```

---

## 4. Payment Lifecycle State Machine

```
[INITIATED] ───────────────> [PENDING / AUTHORIZED]
     │                               │
     ├──> [FAILED]                   ├──> [CAPTURED] ───> [PARTIALLY_REFUNDED]
     │                               │                          │
     └──> [CANCELLED]                └──> [FAILED]              └──> [REFUNDED]
```

### Transition Invariants:
1. `CAPTURED` is reached only when the gateway verification succeeds or an authenticated webhook payload confirms capture.
2. An order in `PENDING_PAYMENT` transitions to `CONFIRMED` upon payment capture.
3. If an order with `CAPTURED` payment is cancelled or returned, a `Refund` is created and `PaymentTransaction.amount_refunded` is incremented.
4. When `amount_refunded == amount`, payment status becomes `REFUNDED`. If `amount_refunded < amount`, it becomes `PARTIALLY_REFUNDED`.

---

## 5. Cash-on-Delivery (COD) Reconciliation Workflow

1. **Checkout:** Customer selects `payment_method = "cod"`. Order is created directly with `status = "CONFIRMED"` and `payment_status = "pending"`.
2. **Dispatch & Delivery:** Order moves to `PROCESSING` $\rightarrow$ `DISPATCHED` $\rightarrow$ `DELIVERED`.
3. **Cash Collection:** Upon delivery, the delivery executive collects the exact amount. The merchant logs cash collection via `POST /api/v1/merchant/payments/cod/{order_id}/collect`:
   - Creates a `CodSettlement` with `settlement_status = "pending_deposit"`.
   - Transitions `PaymentTransaction.status = "captured"` and `Order.payment_status = "captured"`.
4. **Bank Deposit & Reconciliation:** When the delivery executive or logistics partner deposits the collected cash into the merchant bank account, staff records `bank_deposit_reference` via `POST /api/v1/merchant/payments/cod/{settlement_id}/reconcile`:
   - Updates `settlement_status = "reconciled"`.
   - Records reconciliation timestamp in audit logs.
