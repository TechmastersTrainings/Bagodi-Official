from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OTPSendRequest(BaseModel):
    phone_e164: str = Field(
        ..., pattern=r"^\+[1-9]\d{1,14}$", description="Mobile number in E.164 format"
    )
    purpose: str = Field(default="login", max_length=50)


class OTPSendResponse(BaseModel):
    status: str = "sent"
    cooldown_seconds: int
    expires_in_seconds: int
    message: str


class OTPVerifyRequest(BaseModel):
    phone_e164: str = Field(..., pattern=r"^\+[1-9]\d{1,14}$")
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    tenant_id: UUID | None = Field(
        default=None, description="Optional tenant context for staff/merchant login"
    )


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone_e164: str | None
    email: str | None
    display_name: str | None
    status: str
    is_platform_user: bool
    tenant_id: UUID | None
    roles: list[str]
    permissions: list[str]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfileResponse


class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None)


class MessageResponse(BaseModel):
    message: str
