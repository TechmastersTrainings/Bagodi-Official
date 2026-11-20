import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class OTPSendRequest(BaseModel):
    phone_e164: str | None = Field(
        default=None, description="Mobile number in E.164 format"
    )
    phoneOrEmail: str | None = Field(default=None, description="Mobile number or email")
    email: str | None = Field(
        default=None, description="Email address for OTP dispatch"
    )
    purpose: str = Field(default="login", max_length=50)
    channel: str | None = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def resolve_otp_destination(cls, data: Any) -> Any:
        if isinstance(data, (str, bytes)):
            try:
                import json
                data = json.loads(data)
            except Exception:
                pass
        if isinstance(data, dict):
            dest = data.get("phoneOrEmail") or data.get("phone_e164") or data.get("email")
            if dest:
                dest_str = str(dest).strip()
                if "@" in dest_str:
                    data["email"] = dest_str.lower()
                else:
                    clean = re.sub(r"\D", "", dest_str)
                    if len(clean) == 10:
                        clean = f"+91{clean}"
                    elif not clean.startswith("+"):
                        clean = f"+{clean}"
                    data["phone_e164"] = clean
        return data


class OTPSendResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str = "sent"
    cooldown_seconds: int = Field(default=60, alias="cooldownSeconds")
    expires_in_seconds: int = Field(default=300, alias="expiresInSeconds")
    message: str
    dev_otp: str | None = Field(default=None, alias="devOtp")
    reference_id: str | None = Field(default=None, alias="referenceId")
    masked_destination: str | None = Field(default=None, alias="maskedDestination")


class OTPVerifyRequest(BaseModel):
    phone_e164: str | None = Field(default=None)
    phoneOrEmail: str | None = Field(default=None)
    email: str | None = Field(default=None)
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    referenceId: str | None = Field(default=None)
    tenant_id: UUID | None = Field(
        default=None, description="Optional tenant context for staff/merchant login"
    )

    @model_validator(mode="before")
    @classmethod
    def resolve_verify_destination(cls, data: Any) -> Any:
        if isinstance(data, (str, bytes)):
            try:
                import json
                data = json.loads(data)
            except Exception:
                pass
        if isinstance(data, dict):
            dest = data.get("phoneOrEmail") or data.get("phone_e164") or data.get("email")
            if dest:
                dest_str = str(dest).strip()
                if "@" in dest_str:
                    data["email"] = dest_str.lower()
                else:
                    clean = re.sub(r"\D", "", dest_str)
                    if len(clean) == 10:
                        clean = f"+91{clean}"
                    elif not clean.startswith("+"):
                        clean = f"+{clean}"
                    data["phone_e164"] = clean
        return data


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

    @computed_field
    @property
    def role(self) -> str:
        if "SUPER_ADMIN" in self.roles:
            return "SUPER_ADMIN"
        if "MERCHANT_OWNER" in self.roles or "MERCHANT_ADMIN" in self.roles:
            return "MERCHANT_ADMIN"
        if self.roles:
            return self.roles[0]
        return "CUSTOMER"

    @computed_field
    @property
    def fullName(self) -> str:
        return self.display_name or self.email or ""

    @computed_field
    @property
    def isActive(self) -> bool:
        return self.status == "active"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfileResponse

    @computed_field
    @property
    def tokens(self) -> dict[str, Any]:
        return {
            "accessToken": self.access_token,
            "refreshToken": self.refresh_token,
            "tokenType": "Bearer",
            "expiresIn": self.expires_in,
        }


class TokenRefreshRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    refresh_token: str = Field(..., min_length=10, alias="refreshToken")


class LogoutRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    refresh_token: str | None = Field(default=None, alias="refreshToken")


class MessageResponse(BaseModel):
    message: str


class CustomerAddressCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    full_name: str = Field(..., min_length=2, max_length=150, alias="fullName")
    phone: str = Field(..., min_length=10, max_length=20, alias="phoneNumber")
    address_line1: str = Field(..., min_length=3, max_length=255, alias="addressLine1")
    address_line2: str | None = Field(default=None, max_length=255, alias="addressLine2")
    landmark: str | None = Field(default=None, max_length=150)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    postal_code: str = Field(..., min_length=5, max_length=10, alias="postalCode")
    address_type: str = Field(default="home", pattern=r"^(home|work|other)$", alias="addressType")
    is_default: bool = Field(default=False, alias="isDefault")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, (str, bytes)):
            try:
                import json
                data = json.loads(data)
            except Exception:
                pass
        if isinstance(data, dict):
            if "fullName" in data and "full_name" not in data:
                data["full_name"] = data["fullName"]
            elif "recipient_name" in data and "full_name" not in data:
                data["full_name"] = data["recipient_name"]
            if "phoneNumber" in data and "phone" not in data:
                data["phone"] = data["phoneNumber"]
            elif "phone_number" in data and "phone" not in data:
                data["phone"] = data["phone_number"]
            if "addressLine1" in data and "address_line1" not in data:
                data["address_line1"] = data["addressLine1"]
            if "addressLine2" in data and "address_line2" not in data:
                data["address_line2"] = data["addressLine2"]
            if "postalCode" in data and "postal_code" not in data:
                data["postal_code"] = data["postalCode"]
            elif "pincode" in data and "postal_code" not in data:
                data["postal_code"] = data["pincode"]
            if "addressType" in data and "address_type" not in data:
                data["address_type"] = str(data["addressType"]).lower()
            if "isDefault" in data and "is_default" not in data:
                data["is_default"] = bool(data["isDefault"])
        return data


class CustomerAddressUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    full_name: str | None = Field(default=None, min_length=2, max_length=150, alias="fullName")
    phone: str | None = Field(default=None, min_length=10, max_length=20, alias="phoneNumber")
    address_line1: str | None = Field(default=None, min_length=3, max_length=255, alias="addressLine1")
    address_line2: str | None = Field(default=None, max_length=255, alias="addressLine2")
    landmark: str | None = Field(default=None, max_length=150)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    state: str | None = Field(default=None, min_length=2, max_length=100)
    postal_code: str | None = Field(default=None, min_length=5, max_length=10, alias="postalCode")
    address_type: str | None = Field(default=None, pattern=r"^(home|work|other)$", alias="addressType")
    is_default: bool | None = Field(default=None, alias="isDefault")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, (str, bytes)):
            try:
                import json
                data = json.loads(data)
            except Exception:
                pass
        if isinstance(data, dict):
            if "fullName" in data and "full_name" not in data:
                data["full_name"] = data["fullName"]
            if "phoneNumber" in data and "phone" not in data:
                data["phone"] = data["phoneNumber"]
            elif "phone_number" in data and "phone" not in data:
                data["phone"] = data["phone_number"]
            if "addressLine1" in data and "address_line1" not in data:
                data["address_line1"] = data["addressLine1"]
            if "addressLine2" in data and "address_line2" not in data:
                data["address_line2"] = data["addressLine2"]
            if "postalCode" in data and "postal_code" not in data:
                data["postal_code"] = data["postalCode"]
            elif "pincode" in data and "postal_code" not in data:
                data["postal_code"] = data["pincode"]
            if "addressType" in data and "address_type" not in data:
                data["address_type"] = str(data["addressType"]).lower()
            if "isDefault" in data and "is_default" not in data:
                data["is_default"] = bool(data["isDefault"])
        return data


class CustomerAddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    tenant_id: UUID
    customer_id: UUID
    full_name: str
    phone: str
    address_line1: str
    address_line2: str | None
    landmark: str | None
    city: str
    state: str
    postal_code: str
    address_type: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    @computed_field
    def fullName(self) -> str:
        return self.full_name

    @computed_field
    def phoneNumber(self) -> str:
        return self.phone

    @computed_field
    def addressLine1(self) -> str:
        return self.address_line1

    @computed_field
    def addressLine2(self) -> str | None:
        return self.address_line2

    @computed_field
    def postalCode(self) -> str:
        return self.postal_code

    @computed_field
    def pincode(self) -> str:
        return self.postal_code

    @computed_field
    def addressType(self) -> str:
        return self.address_type

    @computed_field
    def isDefault(self) -> bool:
        return self.is_default


class LoginRequest(BaseModel):
    email: str | None = Field(default=None, description="Email address or username")
    emailOrPhone: str | None = Field(default=None, description="Email address or mobile phone")
    password: str = Field(..., min_length=4, description="User password")

    @model_validator(mode="before")
    @classmethod
    def resolve_login_identifier(cls, data: Any) -> Any:
        if isinstance(data, (str, bytes)):
            try:
                import json
                data = json.loads(data)
            except Exception:
                pass
        if isinstance(data, dict):
            identifier = data.get("email") or data.get("emailOrPhone") or data.get("identifier") or data.get("username")
            if identifier:
                data["email"] = str(identifier).strip()
        return data


class CustomerRegisterRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=150)
    fullName: str | None = Field(default=None)
    email: str = Field(..., min_length=5, max_length=320)
    phone_e164: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None)
    password: str = Field(..., min_length=6, max_length=100)
    confirmPassword: str | None = None
    acceptTerms: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_customer_fields(cls, data: Any) -> Any:
        if isinstance(data, (str, bytes)):
            try:
                import json
                data = json.loads(data)
            except Exception:
                pass
        if isinstance(data, dict):
            if "fullName" in data and not data.get("display_name"):
                data["display_name"] = str(data["fullName"]).strip()
            p = data.get("phone") or data.get("phone_e164")
            if p:
                p_str = str(p).strip()
                clean = re.sub(r"\D", "", p_str)
                if len(clean) == 10:
                    clean = f"+91{clean}"
                elif not clean.startswith("+"):
                    clean = f"+{clean}"
                data["phone_e164"] = clean
        return data


class MerchantRegisterRequest(BaseModel):
    business_legal_name: str = Field(..., min_length=3, max_length=250)
    brand_name: str = Field(..., min_length=2, max_length=150)
    owner_name: str = Field(..., min_length=2, max_length=150)
    email: str = Field(..., min_length=5, max_length=320)
    phone_e164: str = Field(..., min_length=10, max_length=20)
    password: str = Field(..., min_length=6, max_length=100)
    business_type: str = Field(default="Private Limited", max_length=50)
    category_specialization: str = Field(default="Apparel & Couture", max_length=150)
    address_line: str = Field(..., min_length=3, max_length=300)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    postal_code: str = Field(..., min_length=6, max_length=20)
    gstin: str | None = Field(default=None, max_length=25)
    pan_number: str | None = Field(default=None, max_length=20)
    bank_account_number: str | None = Field(default=None, max_length=50)
    bank_ifsc: str | None = Field(default=None, max_length=20)
    bank_name: str | None = Field(default=None, max_length=100)

    @model_validator(mode="before")
    @classmethod
    def resolve_merchant_fields(cls, data: Any) -> Any:
        if isinstance(data, (str, bytes)):
            try:
                import json
                data = json.loads(data)
            except Exception:
                pass
        return data


class MerchantRegisterResponse(BaseModel):
    tenant_id: UUID
    user_id: UUID
    status: str
    message: str


class MerchantApprovalResponse(BaseModel):
    tenant_id: UUID
    status: str
    message: str


class MerchantStaffCreate(BaseModel):
    display_name: str = Field(..., min_length=2, max_length=150)
    email: str = Field(..., min_length=5, max_length=320)
    phone_e164: str = Field(..., min_length=10, max_length=20)
    password: str = Field(..., min_length=6, max_length=100)
    role: str = Field(default="STORE_MANAGER", max_length=50)


class MerchantStaffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str | None
    email: str | None
    phone_e164: str | None
    status: str
    role: str
    tenant_id: UUID | None
    created_at: datetime


