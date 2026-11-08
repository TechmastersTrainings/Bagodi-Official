from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerCommunicationPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    customer_id: UUID
    email_opt_in: bool
    sms_opt_in: bool
    whatsapp_opt_in: bool
    preferred_channel: str
    consent_recorded_at: datetime


class CustomerCommunicationPreferenceUpdateRequest(BaseModel):
    email_opt_in: bool | None = None
    sms_opt_in: bool | None = None
    whatsapp_opt_in: bool | None = None
    preferred_channel: str | None = Field(default=None, pattern="^(sms|whatsapp|email)$")


class NotificationMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    outbox_id: UUID | None
    recipient: str
    channel: str
    template_code: str
    template_version: int
    subject: str | None
    body: str
    status: str
    provider: str
    provider_message_id: str | None
    delivery_timestamp: datetime | None
    retry_count: int
    max_retries: int
    next_retry_at: datetime | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class NotificationOutboxResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any]
    status: str
    retry_count: int
    max_retries: int
    next_retry_at: datetime | None
    error_message: str | None
    processed_at: datetime | None
    created_at: datetime


class NotificationTemplateCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=100)
    channel: str = Field(pattern="^(sms|whatsapp|email)$")
    language: str = Field(default="en", max_length=10)
    subject_template: str | None = Field(default=None, max_length=255)
    body_template: str = Field(min_length=5)
    version: int = Field(default=1, ge=1)
    is_active: bool = True


class NotificationTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None
    code: str
    channel: str
    language: str
    version: int
    subject_template: str | None
    body_template: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class OutboxProcessResponse(BaseModel):
    processed_count: int
    dispatched_messages_count: int
    failed_count: int
    dead_letter_count: int


class NotificationDirectSendRequest(BaseModel):
    recipient: str = Field(min_length=3, max_length=255)
    channel: str = Field(pattern="^(sms|whatsapp|email)$")
    template_code: str = Field(min_length=2, max_length=100)
    context: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=100)


class NotificationAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    message_id: UUID | None
    event_type: str
    actor_id: UUID | None
    payload: dict[str, Any]
    created_at: datetime
