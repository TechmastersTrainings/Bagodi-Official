from uuid import UUID

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cross_tenant_isolation_and_suspension(client: AsyncClient, mint_jwt_token):
    platform_admin_token = mint_jwt_token(
        is_platform_user=True,
        permissions=["platform.*"],
    )
    platform_admin_headers = {"Authorization": f"Bearer {platform_admin_token}"}

    # 1. Onboard Tenant A and Tenant B
    tenant_a_payload = {
        "name": "Bagodi Retail Bidar",
        "slug": "bagodi-bidar",
        "legal_name": "Bagodi Enterprises",
        "contact_email": "operations@bagodi.in",
        "contact_phone": "+919876543210",
    }
    resp_a = await client.post("/api/v1/platform/tenants", json=tenant_a_payload, headers=platform_admin_headers)
    assert resp_a.status_code == 201
    tenant_a = resp_a.json()
    tenant_a_id = tenant_a["id"]

    tenant_b_payload = {
        "name": "Second Merchant",
        "slug": "second-merchant",
        "legal_name": "Second Merchant LLP",
        "contact_email": "admin@secondmerchant.in",
        "contact_phone": "+919876543211",
    }
    resp_b = await client.post("/api/v1/platform/tenants", json=tenant_b_payload, headers=platform_admin_headers)
    assert resp_b.status_code == 201
    tenant_b = resp_b.json()
    tenant_b_id = tenant_b["id"]

    # 2. Activate both tenants
    activate_status = {"status": "active"}
    resp_act_a = await client.patch(
        f"/api/v1/platform/tenants/{tenant_a_id}/status",
        json=activate_status,
        headers=platform_admin_headers,
    )
    assert resp_act_a.status_code == 200
    assert resp_act_a.json()["status"] == "active"

    resp_act_b = await client.patch(
        f"/api/v1/platform/tenants/{tenant_b_id}/status",
        json=activate_status,
        headers=platform_admin_headers,
    )
    assert resp_act_b.status_code == 200
    assert resp_act_b.json()["status"] == "active"

    # 3. Create Store under Tenant A using Tenant A's JWT token
    user_a_token = mint_jwt_token(
        tenant_id=UUID(tenant_a_id),
        permissions=["stores.*"],
    )
    user_a_headers = {"Authorization": f"Bearer {user_a_token}"}

    store_a_payload = {
        "name": "Bagodi Flagship Store Bidar",
        "code": "STORE01",
        "address_line": "Near Main Market, Old City",
        "city": "Bidar",
        "state": "Karnataka",
        "postal_code": "585401",
        "phone": "+918482123456",
    }
    resp_store_a = await client.post("/api/v1/stores", json=store_a_payload, headers=user_a_headers)
    assert resp_store_a.status_code == 201
    store_a = resp_store_a.json()
    store_a_id = store_a["id"]
    assert store_a["tenant_id"] == tenant_a_id
    assert store_a["code"] == "STORE01"

    # 4. Create Store under Tenant B with the SAME store code "STORE01" using Tenant B's JWT token
    user_b_token = mint_jwt_token(
        tenant_id=UUID(tenant_b_id),
        permissions=["stores.*"],
    )
    user_b_headers = {"Authorization": f"Bearer {user_b_token}"}

    store_b_payload = {
        "name": "Second Merchant Main Store",
        "code": "STORE01",
        "address_line": "Station Road",
        "city": "Bidar",
        "state": "Karnataka",
        "postal_code": "585401",
        "phone": "+918482654321",
    }
    resp_store_b = await client.post("/api/v1/stores", json=store_b_payload, headers=user_b_headers)
    assert resp_store_b.status_code == 201
    store_b = resp_store_b.json()
    store_b_id = store_b["id"]
    assert store_b["tenant_id"] == tenant_b_id

    # 5. Cross-tenant read isolation: Tenant A lists stores
    resp_list_a = await client.get("/api/v1/stores", headers=user_a_headers)
    assert resp_list_a.status_code == 200
    stores_for_a = resp_list_a.json()
    assert len(stores_for_a) == 1
    assert stores_for_a[0]["id"] == store_a_id
    assert stores_for_a[0]["name"] == "Bagodi Flagship Store Bidar"

    # 6. Cross-tenant detail access: Tenant A tries to access Tenant B's store ID directly
    resp_cross_access = await client.get(f"/api/v1/stores/{store_b_id}", headers=user_a_headers)
    assert resp_cross_access.status_code == 404
    assert resp_cross_access.json()["code"] == "STORE_NOT_FOUND"

    # 7. Suspend Tenant B
    resp_suspend_b = await client.patch(
        f"/api/v1/platform/tenants/{tenant_b_id}/status",
        json={"status": "suspended"},
        headers=platform_admin_headers,
    )
    assert resp_suspend_b.status_code == 200
    assert resp_suspend_b.json()["status"] == "suspended"

    # 8. Suspended tenant cannot perform operations
    resp_suspended_access = await client.get("/api/v1/stores", headers=user_b_headers)
    assert resp_suspended_access.status_code == 403
    assert resp_suspended_access.json()["code"] == "TENANT_SUSPENDED"
