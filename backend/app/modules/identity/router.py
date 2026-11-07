from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, get_security_principal
from app.db.session import get_db
from app.modules.identity.schemas import (
    LogoutRequest,
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


@router.post(
    "/otp/send",
    response_model=OTPSendResponse,
    status_code=status.HTTP_200_OK,
    summary="Request a secure 6-digit OTP code to mobile number",
)
async def send_otp(
    data: OTPSendRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ip_address = request.client.host if request.client else None
    return await AuthService.request_otp(db, data.phone_e164, ip_address=ip_address)


@router.post(
    "/otp/verify",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify mobile OTP and obtain JWT access and refresh tokens",
)
async def verify_otp(
    data: OTPVerifyRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    return await AuthService.verify_otp(
        db, data, ip_address=ip_address, user_agent=user_agent
    )


@router.post(
    "/token/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Exchange refresh token for new access and rotated refresh token",
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
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
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
