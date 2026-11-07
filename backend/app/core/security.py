from dataclasses import dataclass, field
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status


@dataclass(frozen=True)
class SecurityPrincipal:
    user_id: UUID
    is_platform_user: bool = False
    tenant_id: UUID | None = None
    roles: tuple[str, ...] = field(default_factory=tuple)
    permissions: frozenset[str] = field(default_factory=frozenset)

    def has_permission(self, permission: str) -> bool:
        if "*" in self.permissions or permission in self.permissions:
            return True
        # Check domain wildcard, e.g. "stores.*" matches "stores.read"
        if "." in permission:
            domain = permission.split(".")[0]
            if f"{domain}.*" in self.permissions:
                return True
        return False


def get_security_principal(
    x_user_id: Annotated[str | None, Header(alias="X-User-ID")] = None,
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
    x_platform_user: Annotated[str | None, Header(alias="X-Platform-User")] = None,
    x_roles: Annotated[str | None, Header(alias="X-Roles")] = None,
    x_permissions: Annotated[str | None, Header(alias="X-Permissions")] = None,
) -> SecurityPrincipal:
    """Extract authenticated principal context.

    In Phase 1, extracts authenticated context from server-verified headers.
    Phase 2 will integrate the cryptographic JWT verification provider.
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTHENTICATION_REQUIRED", "message": "Authentication is required."},
        )

    try:
        user_uuid = UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_PRINCIPAL", "message": "Invalid user identity."},
        ) from None

    tenant_uuid: UUID | None = None
    if x_tenant_id:
        try:
            tenant_uuid = UUID(x_tenant_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_TENANT_ID", "message": "Invalid tenant identifier format."},
            ) from None

    is_platform = (x_platform_user or "").strip().lower() in {"true", "1", "yes"}

    roles = tuple(r.strip() for r in (x_roles or "").split(",") if r.strip())
    permissions = frozenset(p.strip() for p in (x_permissions or "").split(",") if p.strip())

    return SecurityPrincipal(
        user_id=user_uuid,
        is_platform_user=is_platform,
        tenant_id=tenant_uuid,
        roles=roles,
        permissions=permissions,
    )


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
