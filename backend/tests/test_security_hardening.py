import time
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine
from app.modules.payments.providers.mock_provider import MockPaymentGatewayProvider


@pytest.fixture
async def setup_security_ecosystem(client: AsyncClient, mint_jwt_token):
    """Provisions Tenant A and Tenant B with independent stores, products, and users."""
    async with engine.begin() as conn:
        res_pa = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919000000055', 'pa@sec.internal', 'Platform Admin', 'active', true, now(), now()) "
                "RETURNING id;"
            )
        )
        pa_id = res_pa.scalar_one()

        res_ma = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919000000066', 'ma@sec.internal', 'Merchant A Admin', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        ma_id = res_ma.scalar_one()

        res_mb = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919000000077', 'mb@sec.internal', 'Merchant B Admin', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        mb_id = res_mb.scalar_one()

        res_ca = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919999900011', 'ca@sec.internal', 'Customer 1', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        c1_id = res_ca.scalar_one()

        res_cb = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919999900022', 'cb@sec.internal', 'Customer 2', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        c2_id = res_cb.scalar_one()

    pa_token = mint_jwt_token(user_id=pa_id, is_platform_user=True, permissions=["platform.*"])
    pa_headers = {"Authorization": f"Bearer {pa_token}"}

    # Onboard Tenant A
    ta_resp = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Sec Tenant A",
            "slug": "sec-tenant-a",
            "legal_name": "Sec Tenant A LLC",
            "contact_email": "a@sec.internal",
            "contact_phone": "+919000000066",
        },
        headers=pa_headers,
    )
    tenant_a_id = UUID(ta_resp.json()["id"])
    await client.patch(
        f"/api/v1/platform/tenants/{tenant_a_id}/status",
        json={"status": "active"},
        headers=pa_headers,
    )

    # Onboard Tenant B
    tb_resp = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Sec Tenant B",
            "slug": "sec-tenant-b",
            "legal_name": "Sec Tenant B LLC",
            "contact_email": "b@sec.internal",
            "contact_phone": "+919000000077",
        },
        headers=pa_headers,
    )
    tenant_b_id = UUID(tb_resp.json()["id"])
    await client.patch(
        f"/api/v1/platform/tenants/{tenant_b_id}/status",
        json={"status": "active"},
        headers=pa_headers,
    )

    ma_token = mint_jwt_token(
        user_id=ma_id,
        tenant_id=tenant_a_id,
        permissions=["stores.*", "catalog.*", "inventory.*", "orders.*", "reports.*"],
    )
    ma_headers = {"Authorization": f"Bearer {ma_token}"}

    mb_token = mint_jwt_token(
        user_id=mb_id,
        tenant_id=tenant_b_id,
        permissions=["stores.*", "catalog.*", "inventory.*", "orders.*", "reports.*"],
    )
    mb_headers = {"Authorization": f"Bearer {mb_token}"}

    c1_token = mint_jwt_token(
        user_id=c1_id,
        tenant_id=tenant_a_id,
        roles=["customer"],
        permissions=["customer.*"],
    )
    c1_headers = {"Authorization": f"Bearer {c1_token}"}

    c2_token = mint_jwt_token(
        user_id=c2_id,
        tenant_id=tenant_a_id,
        roles=["customer"],
        permissions=["customer.*"],
    )
    c2_headers = {"Authorization": f"Bearer {c2_token}"}

    # Store for Tenant A
    sa_resp = await client.post(
        "/api/v1/stores",
        json={
            "name": "Store A",
            "code": "STR-SEC-A",
            "address_line": "Fort Road",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        headers=ma_headers,
    )
    store_a_id = UUID(sa_resp.json()["id"])

    # Store for Tenant B
    sb_resp = await client.post(
        "/api/v1/stores",
        json={
            "name": "Store B",
            "code": "STR-SEC-B",
            "address_line": "Market Road",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        headers=mb_headers,
    )
    store_b_id = UUID(sb_resp.json()["id"])

    # Catalog in Store A
    cat_a = (
        await client.post(
            "/api/v1/merchant/catalog/categories",
            json={"name": "Category A", "slug": "cat-a"},
            headers=ma_headers,
        )
    ).json()

    prod_a = (
        await client.post(
            "/api/v1/merchant/catalog/products",
            json={
                "category_id": cat_a["id"],
                "name": "Product A",
                "slug": "prod-a",
                "status": "active",
                "is_published": True,
                "variants": [
                    {
                        "name": "Variant A",
                        "sku": "SKU-SEC-A",
                        "barcode": "8907770001",
                        "mrp": "1000.00",
                        "base_price": "900.00",
                    }
                ],
            },
            headers=ma_headers,
        )
    ).json()
    var_a_id = UUID(prod_a["variants"][0]["id"])

    # Inward stock
    await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": str(store_a_id),
            "receipt_number": "INW-SEC-A",
            "items": [
                {"variant_id": str(var_a_id), "quantity_received": 10, "unit_cost": "500.00"}
            ],
        },
        headers=ma_headers,
    )

    return {
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "store_a_id": store_a_id,
        "store_b_id": store_b_id,
        "var_a_id": var_a_id,
        "ma_headers": ma_headers,
        "mb_headers": mb_headers,
        "c1_headers": c1_headers,
        "c2_headers": c2_headers,
        "c1_id": c1_id,
        "c2_id": c2_id,
    }


# =============================================================================
# Security Hardening Tests
# =============================================================================
@pytest.mark.asyncio
async def test_idor_cross_customer_and_cross_tenant_isolation(
    client: AsyncClient, setup_security_ecosystem
):
    """
    OWASP API1: Broken Object Level Authorization (BOLA / IDOR)
    - Customer 1 places an order in Tenant A.
    - Customer 2 attempts to fetch Customer 1's order details -> Must receive 404 / 403.
    - Merchant B attempts to fetch Customer 1's order -> Must receive 404 / 403.
    - Merchant B attempts to inward stock into Store A -> Must receive 404 / 403.
    """
    eco = setup_security_ecosystem
    store_a_id = eco["store_a_id"]
    var_a_id = eco["var_a_id"]
    c1_headers = eco["c1_headers"]
    c2_headers = eco["c2_headers"]
    mb_headers = eco["mb_headers"]

    # Customer 1 adds item and checkouts
    await client.post(
        f"/api/v1/cart/items?store_id={store_a_id}",
        json={"variant_id": str(var_a_id), "quantity": 1},
        headers=c1_headers,
    )
    chk_resp = await client.post(
        "/api/v1/orders/checkout",
        json={
            "store_id": str(store_a_id),
            "payment_method": "online",
            "shipping_address": {
                "full_name": "Cust 1",
                "phone": "+919999900011",
                "address_line1": "Fort Road",
                "city": "Bidar",
                "state": "Karnataka",
                "postal_code": "585401",
            },
            "customer_name": "Cust 1",
            "customer_email": "ca@sec.internal",
            "customer_phone": "+919999900011",
        },
        headers=c1_headers,
    )
    assert chk_resp.status_code == 201
    order_id = chk_resp.json()["id"]

    # IDOR Test 1: Customer 2 attempts to view Customer 1's order
    idor_c2 = await client.get(f"/api/v1/orders/{order_id}", headers=c2_headers)
    assert idor_c2.status_code in (403, 404), (
        f"IDOR Vulnerability: Customer 2 accessed Customer 1's order! {idor_c2.text}"
    )

    # IDOR Test 2: Merchant B attempts to view Merchant A's order
    idor_mb = await client.get(f"/api/v1/merchant/orders/{order_id}", headers=mb_headers)
    assert idor_mb.status_code in (403, 404), (
        f"Cross-tenant IDOR: Merchant B accessed Merchant A's order! {idor_mb.text}"
    )

    # IDOR Test 3: Merchant B attempts to inward stock into Merchant A's store
    idor_inw = await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": str(store_a_id),
            "receipt_number": "MALICIOUS-INW-01",
            "items": [{"variant_id": str(var_a_id), "quantity_received": 100, "unit_cost": "1.00"}],
        },
        headers=mb_headers,
    )
    assert idor_inw.status_code in (400, 403, 404), (
        f"Cross-tenant Inwarding accepted! {idor_inw.text}"
    )


@pytest.mark.asyncio
async def test_privilege_escalation_and_function_level_authorization(
    client: AsyncClient, setup_security_ecosystem
):
    """
    OWASP API5: Broken Function Level Authorization
    - Customer user attempts to invoke Merchant and Platform administration APIs.
    - Merchant Admin attempts to invoke TechMasters Platform Admin APIs.
    Must strictly return 403 Forbidden.
    """
    eco = setup_security_ecosystem
    c1_headers = eco["c1_headers"]
    ma_headers = eco["ma_headers"]

    # 1. Customer tries to access merchant dashboard
    r1 = await client.get("/api/v1/merchant/reports/dashboard", headers=c1_headers)
    assert r1.status_code == 403, "Customer accessed merchant reports!"

    # 2. Customer tries to access platform overview
    r2 = await client.get("/api/v1/platform/reports/overview", headers=c1_headers)
    assert r2.status_code == 403, "Customer accessed platform overview!"

    # 3. Customer tries to create a physical store
    r3 = await client.post(
        "/api/v1/stores",
        json={
            "name": "Hacked Store",
            "code": "HACK-01",
            "address_line": "X",
            "city": "Bidar",
            "state": "KA",
            "postal_code": "585401",
        },
        headers=c1_headers,
    )
    assert r3.status_code == 403, "Customer created a physical store!"

    # 4. Merchant Admin tries to view platform-wide tenant overview
    r4 = await client.get("/api/v1/platform/reports/overview", headers=ma_headers)
    assert r4.status_code == 403, "Merchant admin accessed platform super admin analytics!"

    # 5. Merchant Admin tries to onboard another tenant
    r5 = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Rogue Tenant",
            "slug": "rogue",
            "legal_name": "Rogue LLC",
            "contact_email": "r@r.in",
            "contact_phone": "+919000000000",
        },
        headers=ma_headers,
    )
    assert r5.status_code == 403, "Merchant admin onboarded a platform tenant!"


@pytest.mark.asyncio
async def test_jwt_tampering_forgery_and_token_abuse(client: AsyncClient):
    """
    OWASP API2: Broken Authentication
    - Missing token -> 401
    - Malformed token -> 401
    - Forged token signed with a bogus secret key -> 401
    - Expired token -> 401
    """
    # 1. Missing Token
    r1 = await client.get("/api/v1/auth/me")
    assert r1.status_code == 401

    # 2. Malformed Token
    r2 = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer this_is_not_a_valid_jwt"}
    )
    assert r2.status_code == 401

    # 3. Forged Token (signed with an attacker's key)
    attacker_payload = {
        "sub": str(uuid4()),
        "user_id": str(uuid4()),
        "is_platform_user": True,
        "permissions": ["*"],
        "exp": int(time.time()) + 3600,
    }
    forged_token = jwt.encode(
        attacker_payload, "ATTACKER_BOGUS_SECRET_KEY_123456", algorithm="HS256"
    )
    r3 = await client.get(
        "/api/v1/platform/reports/overview", headers={"Authorization": f"Bearer {forged_token}"}
    )
    assert r3.status_code == 401, "Forged JWT was accepted by security principal!"

    # 4. Expired Token
    settings = get_settings()
    expired_payload = {
        "sub": str(uuid4()),
        "user_id": str(uuid4()),
        "exp": int(time.time()) - 3600,  # Expired 1 hour ago
    }
    expired_token = jwt.encode(expired_payload, settings.jwt_secret_key, algorithm="HS256")
    r4 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert r4.status_code == 401, "Expired token was accepted!"


@pytest.mark.asyncio
async def test_webhook_cryptographic_verification_and_replay_protection(client: AsyncClient):
    """
    Validates webhook security:
    - Forged webhook signature is rejected (401/400).
    - Webhook with stale timestamp (> 300 seconds) is rejected.
    """
    provider = MockPaymentGatewayProvider()
    valid_payload = b'{"event": "payment.captured", "amount": 1000}'

    # 1. Tampered / Missing signature
    r1 = await client.post(
        "/api/v1/payments/webhooks/mock",
        content=valid_payload,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": "tampered_signature_hex",
        },
    )
    assert r1.status_code in (400, 401)

    # 2. Stale timestamp (1 hour ago)
    stale_timestamp = int(time.time()) - 3600
    sig_header = provider.generate_webhook_header(valid_payload, timestamp=stale_timestamp)
    r2 = await client.post(
        "/api/v1/payments/webhooks/mock",
        content=valid_payload,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": sig_header,
        },
    )
    assert r2.status_code in (400, 401)
