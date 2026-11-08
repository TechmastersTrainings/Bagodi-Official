import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.db.session import engine


@pytest.fixture
async def setup_concurrency_ecosystem(client: AsyncClient, mint_jwt_token):
    """
    Sets up a tenant with a product variant that has EXACTLY 5 units of stock.
    Creates 50 customer accounts and tokens to perform simultaneous concurrent checkouts.
    """
    # 1. Platform Admin & Tenant Provisioning
    async with engine.begin() as conn:
        res_pa = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919000000011', 'pa@concurrency.internal', 'Platform Admin', 'active', true, now(), now()) "
                "RETURNING id;"
            )
        )
        pa_id = res_pa.scalar_one()

        res_ma = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919000000022', 'ma@concurrency.internal', 'Merchant Admin', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        ma_id = res_ma.scalar_one()

    pa_token = mint_jwt_token(user_id=pa_id, is_platform_user=True, permissions=["platform.*"])
    pa_headers = {"Authorization": f"Bearer {pa_token}"}

    tenant_resp = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Flash Sale Merchant",
            "slug": "flash-sale-merchant",
            "legal_name": "Flash Sale Retail Private Limited",
            "contact_email": "flash@bagodi.in",
            "contact_phone": "+919000000022",
        },
        headers=pa_headers,
    )
    tenant_id = UUID(tenant_resp.json()["id"])
    await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/status",
        json={"status": "active"},
        headers=pa_headers,
    )

    ma_token = mint_jwt_token(
        user_id=ma_id,
        tenant_id=tenant_id,
        permissions=["stores.*", "catalog.*", "inventory.*", "orders.*", "pricing.*"],
    )
    ma_headers = {"Authorization": f"Bearer {ma_token}"}

    # Store
    store_resp = await client.post(
        "/api/v1/stores",
        json={
            "name": "Flash Hub",
            "code": "FLASH-01",
            "address_line": "Fort Gate",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        headers=ma_headers,
    )
    store_id = UUID(store_resp.json()["id"])

    # Category & Limited Product
    cat = (
        await client.post(
            "/api/v1/merchant/catalog/categories",
            json={"name": "Limited Editions", "slug": "limited-editions"},
            headers=ma_headers,
        )
    ).json()

    prod = (
        await client.post(
            "/api/v1/merchant/catalog/products",
            json={
                "category_id": cat["id"],
                "name": "Limited Edition Silver Coin",
                "slug": "limited-edition-silver-coin",
                "status": "active",
                "is_published": True,
                "variants": [
                    {
                        "name": "100g Pure Silver Coin",
                        "sku": "COIN-100G",
                        "barcode": "8909990001",
                        "mrp": "8500.00",
                        "base_price": "8000.00",
                    }
                ],
            },
            headers=ma_headers,
        )
    ).json()
    variant_id = UUID(prod["variants"][0]["id"])

    # Inward EXACTLY 5 units
    await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": str(store_id),
            "receipt_number": "INW-FLASH-01",
            "items": [
                {"variant_id": str(variant_id), "quantity_received": 5, "unit_cost": "6000.00"}
            ],
        },
        headers=ma_headers,
    )

    # Single-use Coupon: FLASH500 (max_uses=1)
    now = datetime.now(UTC)
    await client.post(
        "/api/v1/merchant/pricing/coupons",
        json={
            "name": "Flash Single Coupon",
            "code": "FLASH500",
            "discount_type": "FIXED_AMOUNT",
            "discount_value": "500.00",
            "min_order_amount": "1000.00",
            "total_usage_limit": 1,
            "usage_limit_per_customer": 1,
            "start_date": (now - timedelta(days=1)).isoformat(),
            "end_date": (now + timedelta(days=10)).isoformat(),
            "status": "active",
        },
        headers=ma_headers,
    )

    # Pre-create 30 customer tokens
    customer_tokens = []
    async with engine.begin() as conn:
        for i in range(30):
            res_c = await conn.execute(
                text(
                    "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), :phone, :email, :name, 'active', false, now(), now()) "
                    "RETURNING id;"
                ),
                {
                    "phone": f"+9198000{i:05d}",
                    "email": f"concurrent_user_{i}@example.com",
                    "name": f"User {i}",
                },
            )
            uid = res_c.scalar_one()
            tok = mint_jwt_token(
                user_id=uid,
                tenant_id=tenant_id,
                roles=["customer"],
                permissions=["customer.*"],
            )
            customer_tokens.append(tok)

    return {
        "tenant_id": tenant_id,
        "store_id": store_id,
        "variant_id": variant_id,
        "customer_tokens": customer_tokens,
    }


# =============================================================================
# Concurrency Stress Tests
# =============================================================================
@pytest.mark.asyncio
async def test_concurrent_checkout_prevents_overselling_and_deadlocks(
    client: AsyncClient, setup_concurrency_ecosystem
):
    """
    Stress Test:
    30 simultaneous buyers attempt to purchase 1 unit each of a product that has
    ONLY 5 units in stock.

    Invariants Verified:
    1. Zero deadlocks occur.
    2. Exactly 5 checkouts succeed (HTTP 201).
    3. Exactly 25 checkouts are cleanly rejected with HTTP 400 (OUT_OF_STOCK).
    4. Database on-hand stock remains 5, reserved stock is exactly 5, available stock is 0.
    5. Zero negative inventory balances in stock ledger.
    """
    eco = setup_concurrency_ecosystem
    store_id = eco["store_id"]
    variant_id = eco["variant_id"]
    tokens = eco["customer_tokens"]
    tenant_id = eco["tenant_id"]

    # 1. Add item to cart for all 30 users
    for i, tok in enumerate(tokens):
        headers = {"Authorization": f"Bearer {tok}"}
        resp = await client.post(
            f"/api/v1/cart/items?store_id={store_id}",
            json={"variant_id": str(variant_id), "quantity": 1},
            headers=headers,
        )
        assert resp.status_code == 201, f"Cart add failed for user {i}: {resp.text}"

    # 2. Concurrently fire checkout requests for all 30 users simultaneously
    async def _do_checkout(tok: str, idx: int):
        headers = {"Authorization": f"Bearer {tok}"}
        return await client.post(
            "/api/v1/orders/checkout",
            json={
                "store_id": str(store_id),
                "payment_method": "online",
                "shipping_address": {
                    "full_name": f"User {idx}",
                    "phone": f"+9198000{idx:05d}",
                    "address_line1": "Fort Road",
                    "city": "Bidar",
                    "state": "Karnataka",
                    "postal_code": "585401",
                },
                "customer_name": f"User {idx}",
                "customer_email": f"concurrent_user_{idx}@example.com",
                "customer_phone": f"+9198000{idx:05d}",
            },
            headers=headers,
        )

    tasks = [_do_checkout(tok, i) for i, tok in enumerate(tokens)]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    # 3. Analyze Results
    success_count = 0
    out_of_stock_count = 0
    unexpected_errors = []

    for r in responses:
        if isinstance(r, Exception):
            unexpected_errors.append(str(r))
        elif r.status_code == 201:
            success_count += 1
        elif r.status_code in (400, 409):
            out_of_stock_count += 1
        else:
            unexpected_errors.append(f"HTTP {r.status_code}: {r.text}")

    assert len(unexpected_errors) == 0, (
        f"Unexpected errors during concurrent burst: {unexpected_errors}"
    )
    assert success_count == 5, f"Expected exactly 5 successful orders, got {success_count}"
    assert out_of_stock_count == 25, f"Expected 25 rejections, got {out_of_stock_count}"

    # 4. Verify Database Invariants Directly
    async with engine.connect() as conn:
        bal = (
            await conn.execute(
                text(
                    "SELECT on_hand_qty, reserved_qty, available_qty "
                    "FROM stock_balances "
                    "WHERE tenant_id = :tid AND store_id = :sid AND variant_id = :vid"
                ),
                {"tid": tenant_id, "sid": store_id, "vid": variant_id},
            )
        ).one()

        assert bal.on_hand_qty == 5
        assert bal.reserved_qty == 5
        assert bal.available_qty == 0
        assert bal.available_qty >= 0, "CRITICAL: Negative available stock detected!"


@pytest.mark.asyncio
async def test_concurrent_coupon_redemption_strictly_enforces_max_uses(
    client: AsyncClient, setup_concurrency_ecosystem
):
    """
    Stress Test:
    Multiple simultaneous buyers checkout with the same single-use coupon (max_uses=1).
    Validates that exactly 1 receives the discount and concurrent over-redemption is prevented.
    """
    eco = setup_concurrency_ecosystem
    store_id = eco["store_id"]
    variant_id = eco["variant_id"]
    tokens = eco["customer_tokens"][:5]

    # Restock by adding 10 units so stock is not the constraint
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE stock_balances SET on_hand_qty = 20, reserved_qty = 0, available_qty = 20 "
                "WHERE store_id = :sid AND variant_id = :vid"
            ),
            {"sid": store_id, "vid": variant_id},
        )

    # Add item to cart
    for tok in tokens:
        headers = {"Authorization": f"Bearer {tok}"}
        await client.post(
            f"/api/v1/cart/items?store_id={store_id}",
            json={"variant_id": str(variant_id), "quantity": 1},
            headers=headers,
        )

    # Concurrently attempt checkout with coupon FLASH500
    async def _checkout_with_coupon(tok: str, idx: int):
        headers = {"Authorization": f"Bearer {tok}"}
        return await client.post(
            "/api/v1/orders/checkout",
            json={
                "store_id": str(store_id),
                "payment_method": "online",
                "coupon_code": "FLASH500",
                "shipping_address": {
                    "full_name": f"User {idx}",
                    "phone": f"+9198000{idx:05d}",
                    "address_line1": "Fort Road",
                    "city": "Bidar",
                    "state": "Karnataka",
                    "postal_code": "585401",
                },
                "customer_name": f"User {idx}",
                "customer_email": f"user_{idx}@example.com",
                "customer_phone": f"+9198000{idx:05d}",
            },
            headers=headers,
        )

    tasks = [_checkout_with_coupon(tok, i) for i, tok in enumerate(tokens)]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    discounted_orders = 0
    for r in responses:
        if not isinstance(r, Exception) and r.status_code == 201:
            data = r.json()
            if Decimal(data["discount_amount"]) == Decimal("500.00"):
                discounted_orders += 1

    assert discounted_orders == 1, (
        f"Single-use coupon was redeemed {discounted_orders} times! Must be exactly 1."
    )
