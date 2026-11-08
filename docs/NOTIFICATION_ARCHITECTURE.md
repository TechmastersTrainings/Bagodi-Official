# Customer Communication, Notifications & Alerts Engine Specification

**Platform Owner:** TechMasters Innovations Private Limited  
**Merchant Scope:** Multi-tenant (Bagodi and future merchant tenants)  
**System Module:** `backend/app/modules/notifications`  

---

## 1. Architectural Principles

1. **Transactional Outbox Pattern:**
   Notification events are persisted atomically within the exact same database transaction that creates, updates, or transitions business aggregates (e.g. order creation, payment capture, refund issuance). This guarantees **at-least-once delivery** and zero lost notifications even in the event of worker crashes or network interruptions.
2. **Provider Independence (Strategy Pattern):**
   Notification delivery is decoupled from specific downstream telecom or email gateways (e.g. Twilio, Gupshup, Meta Cloud WhatsApp API, AWS SES, SendGrid). A unified interface, `BaseNotificationProvider`, standardizes send requests, template mappings, and delivery status updates.
3. **Strict Idempotency & Replay Protection:**
   Both the outbox layer and notification message layer enforce unique idempotency keys per tenant. Duplicate events or replayed webhooks will never trigger duplicate SMS, WhatsApp, or Email sends.
4. **Resilient Delivery Lifecycle & Dead-Letter Queue:**
   Notifications follow a deterministic lifecycle:
   $$\text{PENDING} \longrightarrow \text{QUEUED} \longrightarrow \text{PROCESSING} \longrightarrow \text{SENT} \longrightarrow \text{DELIVERED}$$
   Failed deliveries undergo bounded exponential backoff retries ($2^{\text{retry\_count}} \times 30\text{s}$). If maximum retries are exhausted, messages transition to `DEAD_LETTER` with permanent failure diagnostics.
5. **Customer Consent & Preference Governance:**
   Customers maintain fine-grained communication preferences for Email, SMS, and WhatsApp. While critical transactional security notices (OTP, account access, refund verification) cannot be suppressed, channel routing honors customer preferences (e.g. preferring WhatsApp over SMS).
6. **Data Privacy & Log Redaction:**
   Sensitive credentials, passwords, raw OTPs, and cardholder data are strictly prevented from appearing in rendered notification bodies or audit logs.

---

## 2. Entities & Data Models

### A. Notification Outbox (`notification_outbox`)
Captures business events atomically with originating database transactions.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `tenant_id` | UUID | Owning merchant tenant ID (Foreign Key) |
| `event_type` | String(100) | Business event (e.g. `order.confirmed`, `order.dispatched`, `payment.captured`, `refund.succeeded`) |
| `aggregate_type` | String(50) | Domain aggregate (`order`, `payment`, `refund`, `customer`) |
| `aggregate_id` | String(100) | ID of originating aggregate (e.g. `order_id`) |
| `payload` | JSONB | Context variables for template rendering and recipient routing |
| `status` | String(30) | `pending`, `processed`, `failed` |
| `idempotency_key` | String(100) | Unique deduplication key per tenant |
| `retry_count` | Integer | Delivery attempts (default 0) |
| `max_retries` | Integer | Threshold before marking failed (default 3) |
| `next_retry_at` | DateTime (UTC, nullable) | Timestamp for next processing attempt |
| `error_message` | Text (nullable) | Error diagnostics if processing fails |
| `processed_at` | DateTime (UTC, nullable) | Timestamp of successful outbox dispatch |
| `created_at`, `updated_at` | DateTime (UTC) | Audit timestamps |

### B. Notification Messages (`notification_messages`)
Records individual messages dispatched across communication channels.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `tenant_id` | UUID | Owning merchant tenant ID |
| `outbox_id` | UUID (nullable) | Link to originating outbox event |
| `recipient` | String(255) | E.164 phone number or email address |
| `channel` | String(30) | `sms`, `whatsapp`, `email` |
| `template_code` | String(100) | Notification template code |
| `template_version` | Integer | Version of template rendered |
| `subject` | String(255) (nullable) | Email subject line |
| `body` | Text | Rendered message text |
| `status` | String(30) | `queued`, `processing`, `sent`, `delivered`, `failed`, `dead_letter` |
| `provider` | String(50) | Gateway provider (`mock`, `twilio`, `gupshup`, `ses`) |
| `provider_message_id` | String(150) (nullable) | External provider transaction reference |
| `delivery_timestamp` | DateTime (UTC, nullable) | Confirmed delivery timestamp from provider DLR |
| `retry_count` | Integer | Retries attempted |
| `max_retries` | Integer | Maximum retry limit (default 3) |
| `next_retry_at` | DateTime (UTC, nullable) | Scheduled timestamp for next retry |
| `error_code` | String(50) (nullable) | Telecom/provider error code |
| `error_message` | Text (nullable) | Failure description |
| `idempotency_key` | String(100) | Deduplication key |
| `metadata_payload` | JSONB (nullable) | Channel-specific metadata |
| `created_at`, `updated_at` | DateTime (UTC) | Timestamps |

### C. Notification Templates (`notification_templates`)
Versioned multi-lingual message templates.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `tenant_id` | UUID (nullable) | Null for platform default, specific UUID for merchant overrides |
| `code` | String(100) | Template code (`order_confirmed`, `payment_captured`, etc.) |
| `channel` | String(30) | `sms`, `whatsapp`, `email` |
| `language` | String(10) | ISO language code (`en`, `kn`, `hi`) |
| `version` | Integer | Monotonically increasing version number |
| `subject_template` | String(255) (nullable) | Jinja/format string for email subjects |
| `body_template` | Text | Formatted template body with `{{ variable }}` interpolation |
| `is_active` | Boolean | Activation status |
| `created_at`, `updated_at` | DateTime (UTC) | Timestamps |

### D. Customer Communication Preferences (`customer_communication_preferences`)
Governs customer opt-ins and preferred communication channels.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `tenant_id` | UUID | Merchant tenant ID |
| `customer_id` | UUID | Foreign Key to `users.id` |
| `email_opt_in` | Boolean | Email opt-in flag (default True) |
| `sms_opt_in` | Boolean | SMS opt-in flag (default True) |
| `whatsapp_opt_in` | Boolean | WhatsApp opt-in flag (default True) |
| `preferred_channel` | String(30) | Customer's primary channel (`whatsapp`, `sms`, `email`) |
| `consent_recorded_at` | DateTime (UTC) | Timestamp of consent update |
| `consent_ip_address` | String(45) (nullable) | Audit IP address of user |
| `created_at`, `updated_at` | DateTime (UTC) | Timestamps |

### E. Notification Audit Logs (`notification_audit_logs`)
Immutable ledger of all dispatch attempts, DLR callbacks, and preference adjustments.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `tenant_id` | UUID | Merchant tenant ID |
| `message_id` | UUID (nullable) | Foreign Key to `notification_messages.id` |
| `event_type` | String(50) | `QUEUED`, `SENT`, `DELIVERED`, `FAILED`, `DEAD_LETTER`, `PREFERENCE_UPDATED` |
| `actor_id` | UUID (nullable) | User or worker ID |
| `payload` | JSONB | Snapshot of event details |
| `created_at` | DateTime (UTC) | Audit timestamp |

---

## 3. Provider Abstraction (Strategy Pattern)

```python
class BaseNotificationProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    async def send_sms(
        self,
        *,
        tenant_id: UUID,
        recipient_phone: str,
        message: str,
        template_id: str | None = None,
        metadata: dict | None = None,
    ) -> NotificationSendResult:
        pass

    @abstractmethod
    async def send_whatsapp(
        self,
        *,
        tenant_id: UUID,
        recipient_phone: str,
        template_name: str,
        parameters: dict[str, str],
        fallback_text: str,
        metadata: dict | None = None,
    ) -> NotificationSendResult:
        pass

    @abstractmethod
    async def send_email(
        self,
        *,
        tenant_id: UUID,
        recipient_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
        metadata: dict | None = None,
    ) -> NotificationSendResult:
        pass

    @abstractmethod
    async def verify_webhook_signature(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> bool:
        pass

    @abstractmethod
    async def parse_delivery_report(
        self,
        *,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> DeliveryStatusUpdate:
        pass
```

---

## 4. Message Delivery Lifecycle State Machine

```
[OUTBOX: PENDING]
       │
       ▼ (Outbox Processor)
[MESSAGE: QUEUED] ─────────────> [PROCESSING]
                                      │
                   ┌──────────────────┴──────────────────┐
                   ▼                                     ▼
             [MESSAGE: SENT]                     [MESSAGE: FAILED]
                   │                                     │
         (Provider DLR Callback)               (Exponential Backoff)
                   │                                     │
                   ▼                           ┌─────────┴─────────┐
          [MESSAGE: DELIVERED]                 ▼                   ▼
                                         [QUEUED: RETRY]     [DEAD_LETTER]
                                          (Retry < Max)      (Retry >= Max)
```

---

## 5. Transactional Event Outbox Mapping

| Triggering Business Event | Originating Module | Channels Dispatched | Template Code |
|---|---|---|---|
| User requests login OTP | `app.modules.identity` | SMS, WhatsApp | `auth_otp` |
| Order placed & confirmed | `app.modules.orders` | WhatsApp, SMS, Email | `order_confirmed` |
| Payment captured | `app.modules.payments` | WhatsApp, SMS, Email | `payment_captured` |
| Payment failed | `app.modules.payments` | SMS, WhatsApp | `payment_failed` |
| Order dispatched | `app.modules.orders` | WhatsApp, SMS | `order_dispatched` |
| Order delivered | `app.modules.orders` | WhatsApp, SMS, Email | `order_delivered` |
| Order cancelled | `app.modules.orders` | WhatsApp, SMS, Email | `order_cancelled` |
| Refund succeeded | `app.modules.payments` | WhatsApp, SMS, Email | `refund_succeeded` |
| COD collected | `app.modules.payments` | SMS, WhatsApp | `cod_collected` |
