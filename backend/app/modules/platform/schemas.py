from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# -----------------------------------------------------------------------------
# 1. Tenants
# -----------------------------------------------------------------------------
class TenantCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    legal_name: str | None = Field(default=None, max_length=250)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=20)
    business_type: str | None = Field(default="PRIVATE_LIMITED", max_length=50)
    pan_number: str | None = Field(default=None, max_length=20)
    gstin: str | None = Field(default=None, max_length=25)
    registered_address: str | None = Field(default=None, max_length=500)
    initial_plan_code: str | None = Field(default=None, max_length=50)


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    legal_name: str | None = Field(default=None, max_length=250)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=20)
    business_type: str | None = Field(default=None, max_length=50)
    pan_number: str | None = Field(default=None, max_length=20)
    gstin: str | None = Field(default=None, max_length=25)
    registered_address: str | None = Field(default=None, max_length=500)


class TenantStatusUpdate(BaseModel):
    status: Literal["pending", "active", "suspended"]
    reason: str | None = Field(default=None, max_length=500, description="Mandatory reason for suspension or reactivation")


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    status: str
    legal_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    business_type: str | None = None
    pan_number: str | None = None
    gstin: str | None = None
    registered_address: str | None = None
    owner_name: str | None = None
    bank_account_number: str | None = None
    bank_ifsc: str | None = None
    bank_name: str | None = None
    category_specialization: str | None = None
    created_at: datetime
    updated_at: datetime
    store_count: int = 0
    kyc_status: str = "PENDING"
    current_plan_name: str | None = None


# -----------------------------------------------------------------------------
# 2. Stores
# -----------------------------------------------------------------------------
class StoreCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    code: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-zA-Z0-9_\-]+$")
    address_line: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=20)


class StoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    address_line: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=20)


class StoreStatusUpdate(BaseModel):
    status: Literal["active", "inactive"]


class StoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    code: str
    status: str
    address_line: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    phone: str | None
    created_at: datetime
    updated_at: datetime


# -----------------------------------------------------------------------------
# 3. KYC Documents
# -----------------------------------------------------------------------------
class TenantKYCDocumentCreate(BaseModel):
    document_type: Literal[
        "GST_CERTIFICATE",
        "PAN_CARD",
        "TRADE_LICENSE",
        "BANK_STATEMENT",
        "IDENTITY_PROOF",
    ]
    document_number: str = Field(..., min_length=3, max_length=100)
    document_url: str = Field(..., min_length=5, max_length=500)
    file_name: str = Field(..., min_length=1, max_length=255)
    file_size_bytes: int = Field(default=0, ge=0)


class TenantKYCDocumentReview(BaseModel):
    status: Literal["VERIFIED", "REJECTED"]
    rejection_reason: str | None = Field(default=None, max_length=500)


class TenantKYCDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    document_type: str
    document_number: str
    document_url: str
    file_name: str
    file_size_bytes: int
    status: str
    rejection_reason: str | None = None
    verified_at: datetime | None = None
    verified_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


# -----------------------------------------------------------------------------
# 4. Tenant Lifecycle History
# -----------------------------------------------------------------------------
class TenantStatusLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    previous_status: str
    new_status: str
    reason: str | None = None
    actor_id: UUID | None = None
    created_at: datetime


# -----------------------------------------------------------------------------
# 5. Subscription Plans & Merchant Billing
# -----------------------------------------------------------------------------
class SubscriptionPlanCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    billing_cycle: Literal["MONTHLY", "ANNUAL"] = "MONTHLY"
    price: Decimal = Field(default=Decimal("0.00"), ge=0)
    currency: str = Field(default="INR", max_length=10)
    max_stores: int = Field(default=1, ge=1)
    max_staff_users: int = Field(default=5, ge=1)
    commission_rate_percent: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
    features: list[str] = Field(default_factory=list)


class SubscriptionPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    billing_cycle: str
    price: Decimal
    currency: str
    max_stores: int
    max_staff_users: int
    commission_rate_percent: Decimal
    features: list
    is_active: bool
    created_at: datetime


class SubscriptionAssignRequest(BaseModel):
    plan_id: UUID
    auto_renew: bool = True


class MerchantSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    plan_id: UUID
    status: str
    current_period_start: datetime
    current_period_end: datetime
    auto_renew: bool
    created_at: datetime
    plan: SubscriptionPlanResponse | None = None


class MerchantInvoiceCreate(BaseModel):
    tenant_id: UUID
    subscription_id: UUID | None = None
    billing_period_start: date
    billing_period_end: date
    amount: Decimal = Field(..., ge=0)
    tax_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    total_amount: Decimal = Field(..., ge=0)
    currency: str = "INR"
    due_date: date
    line_items: list[dict] = Field(default_factory=list)


class MerchantInvoicePayRequest(BaseModel):
    payment_reference: str = Field(..., min_length=3, max_length=150)


class MerchantInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    subscription_id: UUID | None
    invoice_number: str
    billing_period_start: date
    billing_period_end: date
    amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    currency: str
    status: str
    due_date: date
    paid_at: datetime | None
    payment_reference: str | None
    line_items: list
    created_at: datetime


# -----------------------------------------------------------------------------
# 6. Global Platform Administrative Audit Logs
# -----------------------------------------------------------------------------
class PlatformAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_id: UUID | None
    actor_email: str | None
    action: str
    target_type: str
    target_id: str | None
    details: dict
    ip_address: str | None
    created_at: datetime


# -----------------------------------------------------------------------------
# 7. Super Admin Staff Delegation & RBAC
# -----------------------------------------------------------------------------
class PlatformStaffCreate(BaseModel):
    phone_e164: str = Field(..., min_length=10, max_length=20)
    email: str | None = Field(default=None, max_length=320)
    display_name: str = Field(..., min_length=2, max_length=200)
    role_code: Literal[
        "SUPER_ADMIN",
        "COMPLIANCE_OFFICER",
        "FINANCE_CONTROLLER",
        "SUPPORT_OPERATOR",
    ] = "SUPER_ADMIN"


class PlatformStaffUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=200)
    status: Literal["active", "suspended"] | None = None
    role_code: Literal[
        "SUPER_ADMIN",
        "COMPLIANCE_OFFICER",
        "FINANCE_CONTROLLER",
        "SUPPORT_OPERATOR",
    ] | None = None


class PlatformStaffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone_e164: str | None
    email: str | None
    display_name: str | None
    status: str
    is_platform_user: bool
    roles: list[str] = Field(default_factory=list)
    created_at: datetime


class PlatformUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone_e164: str | None
    email: str | None
    display_name: str | None
    status: str
    is_platform_user: bool
    tenant_id: UUID | None = None
    tenant_name: str | None = None
    roles: list[str] = Field(default_factory=list)
    created_at: datetime


# -----------------------------------------------------------------------------
# 8. System Diagnostics & Outbox Monitoring
# -----------------------------------------------------------------------------
class OutboxItemResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    tenant_name: str | None = None
    event_type: str
    aggregate_type: str
    aggregate_id: str
    status: str
    retry_count: int
    created_at: datetime
    updated_at: datetime


class SystemHealthResponse(BaseModel):
    app_name: str
    app_env: str
    status: str
    database: str
    pool_size: int
    active_tenants: int
    pending_outbox_events: int
    failed_outbox_events: int
    system_timestamp: datetime
