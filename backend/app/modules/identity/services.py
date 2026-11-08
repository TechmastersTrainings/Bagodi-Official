from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import SecurityPrincipal
from app.core.tokens import (
    create_access_token,
    generate_otp_code,
    generate_raw_refresh_token,
    generate_salt,
    hash_otp,
    hash_refresh_token,
    verify_otp_hash,
)
from app.modules.identity.models import (
    OTPRequest,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
    UserSession,
)
from app.modules.identity.otp_provider import get_otp_provider
from app.modules.identity.schemas import (
    OTPSendResponse,
    OTPVerifyRequest,
    TokenResponse,
    UserProfileResponse,
)

settings = get_settings()


class AuthService:
    @staticmethod
    async def get_user_roles_and_permissions(
        db: AsyncSession, user_id: UUID, tenant_id: UUID | None
    ) -> tuple[list[str], list[str]]:
        """Fetch active role codes and distinct permission codes for a user."""
        # Query UserRoles for this user matching tenant_id (or platform roles if tenant_id is None)
        query = (
            select(Role.code, Permission.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(UserRole.user_id == user_id)
        )
        if tenant_id:
            query = query.where(UserRole.tenant_id == tenant_id)
        else:
            query = query.where(UserRole.tenant_id.is_(None))

        results = (await db.execute(query)).all()
        roles = sorted({r[0] for r in results})
        permissions = sorted({r[1] for r in results})
        return roles, permissions

    @staticmethod
    async def request_otp(
        db: AsyncSession, phone_e164: str, ip_address: str | None = None
    ) -> OTPSendResponse:
        now = datetime.now(UTC)

        # 1. Check rate limits: maximum requests per hour
        one_hour_ago = now - timedelta(hours=1)
        count_stmt = select(func.count(OTPRequest.id)).where(
            OTPRequest.phone_e164 == phone_e164,
            OTPRequest.created_at >= one_hour_ago,
        )
        hourly_count = (await db.execute(count_stmt)).scalar() or 0
        if hourly_count >= settings.otp_max_hourly_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Hourly OTP request limit exceeded. Please wait before trying again.",
                },
            )

        # 2. Check resend cooldown limit
        latest_stmt = (
            select(OTPRequest)
            .where(OTPRequest.phone_e164 == phone_e164)
            .order_by(OTPRequest.created_at.desc())
            .limit(1)
        )
        latest_req = (await db.execute(latest_stmt)).scalar_one_or_none()
        if latest_req:
            elapsed = (now - latest_req.created_at).total_seconds()
            if elapsed < settings.otp_resend_cooldown_seconds:
                remaining = int(settings.otp_resend_cooldown_seconds - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code": "COOLDOWN_ACTIVE",
                        "message": f"Please wait {remaining} seconds before requesting a new OTP.",
                    },
                )

        # 3. Generate secure code, salt, and hash
        otp_code = generate_otp_code()
        salt = generate_salt()
        otp_hash = hash_otp(otp_code, salt)
        expires_at = now + timedelta(seconds=settings.otp_expire_seconds)

        otp_record = OTPRequest(
            phone_e164=phone_e164,
            otp_hash=otp_hash,
            salt=salt,
            purpose="login",
            attempts=0,
            max_attempts=settings.otp_max_attempts,
            expires_at=expires_at,
            ip_address=ip_address,
        )
        db.add(otp_record)
        await db.commit()

        # 4. Dispatch via provider-independent OTP service
        provider = get_otp_provider()
        await provider.send_otp(phone_e164, otp_code, settings.otp_expire_seconds)

        return OTPSendResponse(
            status="sent",
            cooldown_seconds=settings.otp_resend_cooldown_seconds,
            expires_in_seconds=settings.otp_expire_seconds,
            message="OTP dispatched successfully.",
        )

    @staticmethod
    async def verify_otp(
        db: AsyncSession,
        data: OTPVerifyRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        now = datetime.now(UTC)

        # 1. Fetch latest unconsumed OTP request
        stmt = (
            select(OTPRequest)
            .where(
                OTPRequest.phone_e164 == data.phone_e164,
                OTPRequest.consumed_at.is_(None),
            )
            .order_by(OTPRequest.created_at.desc())
            .limit(1)
        )
        otp_record = (await db.execute(stmt)).scalar_one_or_none()

        if not otp_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "OTP_NOT_FOUND",
                    "message": "No active OTP request found for this number.",
                },
            )

        # 2. Check expiration
        if now > otp_record.expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "OTP_EXPIRED",
                    "message": "OTP has expired. Please request a new code.",
                },
            )

        # 3. Check attempt limit
        if otp_record.attempts >= otp_record.max_attempts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "OTP_MAX_ATTEMPTS_EXCEEDED",
                    "message": "Maximum verification attempts exceeded. Please request a new OTP.",
                },
            )

        # 4. Validate OTP hash
        is_valid = verify_otp_hash(data.otp, otp_record.salt, otp_record.otp_hash)
        if not is_valid:
            otp_record.attempts += 1
            await db.commit()
            remaining = otp_record.max_attempts - otp_record.attempts
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "OTP_INVALID",
                    "message": f"Invalid verification code. {remaining} attempt(s) remaining.",
                },
            )

        # 5. Mark OTP as consumed
        otp_record.consumed_at = now

        # 6. Retrieve or create user
        user_stmt = select(User).where(User.phone_e164 == data.phone_e164)
        user = (await db.execute(user_stmt)).scalar_one_or_none()

        if not user:
            user = User(
                phone_e164=data.phone_e164,
                status="active",
                is_platform_user=False,
            )
            db.add(user)
            await db.flush()

        if user.status == "suspended":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "USER_SUSPENDED", "message": "Your user account is suspended."},
            )

        # 7. Fetch user roles and permissions
        roles, permissions = await AuthService.get_user_roles_and_permissions(
            db, user.id, data.tenant_id
        )

        # If user is platform user, load platform permissions
        if user.is_platform_user and not data.tenant_id:
            plat_roles, plat_perms = await AuthService.get_user_roles_and_permissions(
                db, user.id, None
            )
            roles = sorted(set(roles + plat_roles))
            permissions = sorted(set(permissions + plat_perms))

        # 8. Create user session and refresh token
        raw_refresh_token = generate_raw_refresh_token()
        refresh_hash = hash_refresh_token(raw_refresh_token)
        session_expires_at = now + timedelta(days=settings.jwt_refresh_token_expire_days)

        session = UserSession(
            user_id=user.id,
            tenant_id=data.tenant_id,
            token_hash=refresh_hash,
            expires_at=session_expires_at,
            is_revoked=False,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        db.add(session)
        await db.flush()

        # 9. Mint JWT access token
        access_token, expires_in = create_access_token(
            user_id=user.id,
            is_platform_user=user.is_platform_user,
            tenant_id=data.tenant_id,
            session_id=session.id,
            roles=roles,
            permissions=permissions,
        )

        await db.commit()

        user_profile = UserProfileResponse(
            id=user.id,
            phone_e164=user.phone_e164,
            email=user.email,
            display_name=user.display_name,
            status=user.status,
            is_platform_user=user.is_platform_user,
            tenant_id=data.tenant_id,
            roles=roles,
            permissions=permissions,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            token_type="bearer",
            expires_in=expires_in,
            user=user_profile,
        )

    @staticmethod
    async def refresh_tokens(
        db: AsyncSession,
        raw_refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        now = datetime.now(UTC)
        token_hash = hash_refresh_token(raw_refresh_token)

        stmt = select(UserSession).where(UserSession.token_hash == token_hash)
        session = (await db.execute(stmt)).scalar_one_or_none()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_REFRESH_TOKEN", "message": "Refresh token is invalid."},
            )

        # Replay Attack Detection: If token is already revoked, check if it was rotated
        if session.is_revoked:
            if session.replaced_by_session_id:
                # Potential token compromise: revoke the replacement session tree!
                replacement_stmt = select(UserSession).where(
                    UserSession.id == session.replaced_by_session_id
                )
                replacement = (await db.execute(replacement_stmt)).scalar_one_or_none()
                if replacement:
                    replacement.is_revoked = True
                    replacement.revoked_at = now
                    await db.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "TOKEN_REPLAY_DETECTED",
                    "message": "Refresh token was already used or revoked. Session has been terminated.",
                },
            )

        if now > session.expires_at:
            session.is_revoked = True
            session.revoked_at = now
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "TOKEN_EXPIRED", "message": "Refresh token has expired."},
            )

        # Retrieve user
        user_stmt = select(User).where(User.id == session.user_id)
        user = (await db.execute(user_stmt)).scalar_one_or_none()
        if not user or user.status == "suspended":
            session.is_revoked = True
            session.revoked_at = now
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "USER_SUSPENDED", "message": "User account is suspended."},
            )

        roles, permissions = await AuthService.get_user_roles_and_permissions(
            db, user.id, session.tenant_id
        )

        # Rotate refresh token: revoke old session, generate new session
        session.is_revoked = True
        session.revoked_at = now

        new_raw_refresh = generate_raw_refresh_token()
        new_refresh_hash = hash_refresh_token(new_raw_refresh)
        new_session_expires = now + timedelta(days=settings.jwt_refresh_token_expire_days)

        new_session = UserSession(
            user_id=user.id,
            tenant_id=session.tenant_id,
            token_hash=new_refresh_hash,
            expires_at=new_session_expires,
            is_revoked=False,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        db.add(new_session)
        await db.flush()

        session.replaced_by_session_id = new_session.id

        access_token, expires_in = create_access_token(
            user_id=user.id,
            is_platform_user=user.is_platform_user,
            tenant_id=session.tenant_id,
            session_id=new_session.id,
            roles=roles,
            permissions=permissions,
        )

        await db.commit()

        user_profile = UserProfileResponse(
            id=user.id,
            phone_e164=user.phone_e164,
            email=user.email,
            display_name=user.display_name,
            status=user.status,
            is_platform_user=user.is_platform_user,
            tenant_id=session.tenant_id,
            roles=roles,
            permissions=permissions,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_raw_refresh,
            token_type="bearer",
            expires_in=expires_in,
            user=user_profile,
        )

    @staticmethod
    async def logout(
        db: AsyncSession, principal: SecurityPrincipal, raw_refresh_token: str | None = None
    ) -> None:
        now = datetime.now(UTC)
        if raw_refresh_token:
            token_hash = hash_refresh_token(raw_refresh_token)
            stmt = select(UserSession).where(UserSession.token_hash == token_hash)
            session = (await db.execute(stmt)).scalar_one_or_none()
            if session:
                session.is_revoked = True
                session.revoked_at = now

        if principal.session_id:
            stmt = select(UserSession).where(UserSession.id == principal.session_id)
            current_session = (await db.execute(stmt)).scalar_one_or_none()
            if current_session:
                current_session.is_revoked = True
                current_session.revoked_at = now

        await db.commit()

    @staticmethod
    async def get_user_profile(
        db: AsyncSession, principal: SecurityPrincipal
    ) -> UserProfileResponse:
        user_stmt = select(User).where(User.id == principal.user_id)
        user = (await db.execute(user_stmt)).scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "USER_NOT_FOUND", "message": "User not found."},
            )

        return UserProfileResponse(
            id=user.id,
            phone_e164=user.phone_e164,
            email=user.email,
            display_name=user.display_name,
            status=user.status,
            is_platform_user=user.is_platform_user,
            tenant_id=principal.tenant_id,
            roles=list(principal.roles),
            permissions=list(principal.permissions),
        )
