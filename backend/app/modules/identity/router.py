from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    SecurityPrincipal,
    get_optional_security_principal,
    get_security_principal,
)
from app.db.session import get_db
from app.modules.identity.models import User
from app.modules.identity.schemas import (
    CustomerRegisterRequest,
    LoginRequest,
    LogoutRequest,
    MerchantRegisterRequest,
    MerchantRegisterResponse,
    MessageResponse,
    OTPSendRequest,
    OTPSendResponse,
    OTPVerifyRequest,
    TokenRefreshRequest,
    TokenResponse,
    UserProfileResponse,
)
from app.modules.identity.services import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


class CustomerProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    display_name: str | None = Field(default=None, alias="displayName")
    full_name: str | None = Field(default=None, alias="fullName")
    email: str | None = None


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate with Email / Phone and Password (Real User Platform)",
)
@router.post(
    "/customer/login-password",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Customer password login alias",
)
async def login(
    data: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    return await AuthService.login_with_password(
        db, data, ip_address=ip_address, user_agent=user_agent
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register external customer user account with password",
)
@router.post(
    "/customer/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register customer alias",
)
async def register_customer(
    data: CustomerRegisterRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    return await AuthService.register_customer(
        db, data, ip_address=ip_address, user_agent=user_agent
    )


@router.post(
    "/merchant/register",
    response_model=MerchantRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register real merchant boutique/store for platform approval",
)
async def register_merchant(
    data: MerchantRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AuthService.register_merchant(db, data)


@router.post(
    "/otp/send",
    response_model=OTPSendResponse,
    status_code=status.HTTP_200_OK,
    summary="Request a secure 6-digit OTP code to mobile number or email",
)
@router.post(
    "/customer/send-otp",
    response_model=OTPSendResponse,
    status_code=status.HTTP_200_OK,
    summary="Send customer OTP alias",
)
async def send_otp(
    data: OTPSendRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ip_address = request.client.host if request.client else None
    return await AuthService.request_otp(
        db,
        phone_e164=data.phone_e164,
        email=data.email,
        ip_address=ip_address,
    )


@router.post(
    "/otp/verify",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify mobile OTP and obtain JWT access and refresh tokens",
)
@router.post(
    "/customer/verify-otp",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify customer OTP alias",
)
async def verify_otp(
    data: OTPVerifyRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    return await AuthService.verify_otp(db, data, ip_address=ip_address, user_agent=user_agent)


@router.post(
    "/token/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Exchange refresh token for new access and rotated refresh token",
)
@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh tokens alias",
)
async def refresh_tokens(
    data: TokenRefreshRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    return await AuthService.refresh_tokens(
        db, data.refresh_token, ip_address=ip_address, user_agent=user_agent
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke active session and logout",
)
async def logout(
    data: LogoutRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[SecurityPrincipal | None, Depends(get_optional_security_principal)] = None,
):
    if principal:
        await AuthService.logout(db, principal, raw_refresh_token=data.refresh_token)
    return MessageResponse(message="Successfully logged out and session revoked.")


@router.get(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated user profile, active tenant, roles and permissions",
)
async def get_me(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AuthService.get_user_profile(db, principal)


@router.patch(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update customer profile details (name, email)",
)
async def update_customer_profile(
    data: CustomerProfileUpdateRequest,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTHENTICATION_REQUIRED", "message": "Customer login is required."},
        )
    stmt = select(User).where(User.id == principal.user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "Customer account not found."},
        )

    new_name = data.full_name or data.display_name
    if new_name is not None and new_name.strip():
        user.display_name = new_name.strip()
    if data.email is not None:
        user.email = data.email.strip().lower() if data.email.strip() else None

    await db.commit()
    await db.refresh(user)
    return await AuthService.get_user_profile(db, principal)
