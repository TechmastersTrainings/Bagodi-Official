import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import HTTPException, status

from app.core.config import get_settings

settings = get_settings()


def generate_otp_code() -> str:
    """Generate a cryptographically secure 6-digit numeric OTP."""
    number = secrets.randbelow(1_000_000)
    return f"{number:06d}"


def generate_salt() -> str:
    return secrets.token_hex(16)


def hash_otp(otp_code: str, salt: str) -> str:
    payload = f"{otp_code}:{salt}:{settings.jwt_secret_key}".encode()
    return hashlib.sha256(payload).hexdigest()


def verify_otp_hash(otp_code: str, salt: str, expected_hash: str) -> bool:
    computed = hash_otp(otp_code, salt)
    return hmac.compare_digest(computed, expected_hash)


def generate_raw_refresh_token() -> str:
    """Generate an unguessable high-entropy refresh token string."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_access_token(
    user_id: UUID,
    is_platform_user: bool,
    tenant_id: UUID | None,
    session_id: UUID,
    roles: list[str],
    permissions: list[str],
) -> tuple[str, int]:
    """Create a cryptographically signed short-lived JWT access token."""
    now = datetime.now(UTC)
    expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    exp = now + expires_delta

    claims = {
        "sub": str(user_id),
        "is_platform_user": is_platform_user,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "session_id": str(session_id),
        "roles": roles,
        "permissions": permissions,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    token = jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> dict:
    """Decode and verify a signed JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_EXPIRED", "message": "Access token has expired."},
        ) from None
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Access token is invalid or malformed."},
        ) from None
