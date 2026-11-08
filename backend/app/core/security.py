from dataclasses import dataclass, field
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tokens import decode_access_token
from app.db.session import get_db
from app.modules.identity.models import UserSession

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class SecurityPrincipal:
    user_id: UUID
    is_platform_user: bool = False
    tenant_id: UUID | None = None
    session_id: UUID | None = None
    roles: tuple[str, ...] = field(default_factory=tuple)
    permissions: frozenset[str] = field(default_factory=frozenset)

    def has_permission(self, permission: str) -> bool:
        if "*" in self.permissions or permission in self.permissions:
            return True
        # Check domain wildcard, e.g. "stores.*" matches "stores.read" or "stores:read"
        sep = "." if "." in permission else (":" if ":" in permission else None)
        if sep:
            domain = permission.split(sep)[0]
            if f"{domain}.*" in self.permissions or f"{domain}:*" in self.permissions:
                return True
        return False


async def get_security_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SecurityPrincipal:
    """Extract and cryptographically verify the authenticated principal from the JWT Bearer token.

    Never trusts client-supplied identity or tenant headers.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTHENTICATION_REQUIRED", "message": "Authentication is required."},
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    try:
        user_uuid = UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_PRINCIPAL", "message": "Invalid token subject."},
        ) from None

    tenant_uuid: UUID | None = None
    if payload.get("tenant_id"):
        try:
            tenant_uuid = UUID(payload["tenant_id"])
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_TENANT_ID", "message": "Invalid tenant ID in token."},
            ) from None

    session_uuid: UUID | None = None
    if payload.get("session_id"):
        try:
            session_uuid = UUID(payload["session_id"])
            # Verify session revocation status
            stmt = select(UserSession).where(UserSession.id == session_uuid)
            session = (await db.execute(stmt)).scalar_one_or_none()
            if session and session.is_revoked:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "code": "SESSION_REVOKED",
                        "message": "Session has been revoked. Please log in again.",
                    },
                )
        except ValueError:
            pass

    is_platform = bool(payload.get("is_platform_user", False))
    roles = tuple(payload.get("roles", []))
    permissions = frozenset(payload.get("permissions", []))

    return SecurityPrincipal(
        user_id=user_uuid,
        is_platform_user=is_platform,
        tenant_id=tenant_uuid,
        session_id=session_uuid,
        roles=roles,
        permissions=permissions,
    )


async def get_optional_security_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SecurityPrincipal | None:
    """Extract and cryptographically verify the principal if a token is provided; otherwise returns None."""
    if not credentials or not credentials.credentials:
        return None
    return await get_security_principal(credentials, db)


def require_permission(permission: str):
    """Factory dependency enforcing that the calling principal holds the specified permission."""

    def dependency(
        principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    ) -> SecurityPrincipal:
        if not principal.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PERMISSION_DENIED",
                    "message": f"Permission '{permission}' is required.",
                },
            )
        return principal

    return dependency


def require_platform_admin(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
) -> SecurityPrincipal:
    """Enforce that caller is a platform user and holds platform administrator privileges."""
    if not principal.is_platform_user or not (
        principal.has_permission("platform.*") or principal.has_permission("platform.admin")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PLATFORM_ADMIN_REQUIRED",
                "message": "Platform administrator privileges are required.",
            },
        )
    return principal
