from uuid import UUID

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_rbac_permissions_and_role_boundaries(client: AsyncClient, mint_jwt_token):
    platform_admin_token = mint_jwt_token(
        is_platform_user=True,
        permissions=["platform.*"],
    )
    platform_admin_headers = {"Authorization": f"Bearer {platform_admin_token}"}

    # 1. Onboard an active merchant for RBAC testing
    tenant_payload = {
        "name": "RBAC Test Merchant",
        "slug": "rbac-test-merchant",
        "legal_name": "RBAC Merchant Pvt Ltd",
    }
    resp_tenant = await client.post(
        "/api/v1/platform/tenants", json=tenant_payload, headers=platform_admin_headers
    )
    assert resp_tenant.status_code == 201
    tenant_id = resp_tenant.json()["id"]

    await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/status",
        json={"status": "active"},
        headers=platform_admin_headers,
    )

    # 2. Unauthenticated request must fail
    resp_unauth = await client.get("/api/v1/stores")
    assert resp_unauth.status_code == 401
    assert resp_unauth.json()["code"] == "AUTHENTICATION_REQUIRED"

    # 3. User with NO permissions attempts to create store
    no_perm_token = mint_jwt_token(
        tenant_id=UUID(tenant_id),
        permissions=["unrelated.permission"],
    )
    no_perm_headers = {"Authorization": f"Bearer {no_perm_token}"}
    store_payload = {
        "name": "Unauthorized Store",
        "code": "UNAUTH01",
    }
    resp_forbidden = await client.post(
        "/api/v1/stores", json=store_payload, headers=no_perm_headers
    )
    assert resp_forbidden.status_code == 403
    assert resp_forbidden.json()["code"] == "PERMISSION_DENIED"

    # 4. Ordinary merchant user attempts to access platform governance endpoint
    resp_platform_forbidden = await client.get("/api/v1/platform/tenants", headers=no_perm_headers)
    assert resp_platform_forbidden.status_code == 403
    assert resp_platform_forbidden.json()["code"] == "PLATFORM_ADMIN_REQUIRED"

    # 5. User with specific "stores.create" permission creates store successfully
    create_perm_token = mint_jwt_token(
        tenant_id=UUID(tenant_id),
        permissions=["stores.create"],
    )
    create_perm_headers = {"Authorization": f"Bearer {create_perm_token}"}
    store_payload = {
        "name": "Authorized Branch",
        "code": "BRANCH01",
        "city": "Bidar",
    }
    resp_created = await client.post(
        "/api/v1/stores", json=store_payload, headers=create_perm_headers
    )
    assert resp_created.status_code == 201
    assert resp_created.json()["name"] == "Authorized Branch"

    # 6. Duplicate store code within the SAME tenant must fail with 409 Conflict
    resp_dup_code = await client.post(
        "/api/v1/stores", json=store_payload, headers=create_perm_headers
    )
    assert resp_dup_code.status_code == 409
    assert resp_dup_code.json()["code"] == "STORE_CODE_EXISTS"

    # 7. Duplicate slug for tenant must fail with 409 Conflict
    resp_dup_tenant = await client.post(
        "/api/v1/platform/tenants", json=tenant_payload, headers=platform_admin_headers
    )
    assert resp_dup_tenant.status_code == 409
    assert resp_dup_tenant.json()["code"] == "TENANT_SLUG_EXISTS"
