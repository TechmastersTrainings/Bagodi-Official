from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.db.session import engine


@pytest.fixture
async def setup_order_ecosystem(client: AsyncClient, mint_jwt_token):
    """Helper fixture that provisions Tenant A (Bagodi) with physical store,

    Tenant B with store, products, variants, and inward stock, plus customer and merchant tokens.
    """
    platform_admin_token = mint_jwt_token(
        is_platform_user=True,
        permissions=["platform.*"],
    )
    platform_headers = {"Authorization": f"Bearer {platform_admin_token}"}

    # 1. Onboard Tenant A (Bagodi)
    resp_a = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Bagodi Bidar Store",
            "slug": "bagodi-bidar",
            "legal_name": "Bagodi Retail Private Limited",
            "contact_email": "ops@bagodi.in",
            "contact_phone": "+919876543210",
        },
        headers=platform_headers,
    )
    tenant_a_id = UUID(resp_a.json()["id"])
    await client.patch(
        f"/api/v1/platform/tenants/{tenant_a_id}/status",
        json={"status": "active"},
        headers=platform_headers,
    )

    # 2. Onboard Tenant B (Second Merchant)
    resp_b = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Second Merchant",
            "slug": "second-merchant",
            "legal_name": "Second Merchant LLP",
            "contact_email": "admin@secondmerchant.in",
            "contact_phone": "+919876543211",
        },
        headers=platform_headers,
    )
    tenant_b_id = UUID(resp_b.json()["id"])
    await client.patch(
        f"/api/v1/platform/tenants/{tenant_b_id}/status",
        json={"status": "active"},
        headers=platform_headers,
    )

    # 3. Create Store for Tenant A (Bagodi Bidar Flagship)
    merchant_a_token = mint_jwt_token(
        tenant_id=tenant_a_id,
        permissions=["stores.*", "catalog.*", "inventory.*", "orders.*"],
    )
    merchant_a_headers = {"Authorization": f"Bearer {merchant_a_token}"}

    resp_store_a = await client.post(
        "/api/v1/stores",
        json={
            "name": "Bagodi Flagship Store Bidar",
            "code": "STORE01",
            "address_line": "Near Old Fort, Main Market",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        headers=merchant_a_headers,
    )
    store_a_id = UUID(resp_store_a.json()["id"])

    # 4. Create Store for Tenant B
    merchant_b_token = mint_jwt_token(
        tenant_id=tenant_b_id,
        permissions=["stores.*", "catalog.*", "inventory.*", "orders.*"],
    )
    merchant_b_headers = {"Authorization": f"Bearer {merchant_b_token}"}

    resp_store_b = await client.post(
        "/api/v1/stores",
        json={
            "name": "Second Merchant Store",
            "code": "STORE01",
            "address_line": "Market Road",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        headers=merchant_b_headers,
    )
    store_b_id = UUID(resp_store_b.json()["id"])

    # 5. Insert Customers into users table so foreign keys resolve cleanly
    async with engine.begin() as conn:
        res_u1 = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919999900001', 'cust1@example.com', 'Ramesh Kumar', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        customer_1_id = res_u1.scalar_one()

        res_u2 = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919999900002', 'cust2@example.com', 'Suresh Patil', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        customer_2_id = res_u2.scalar_one()

    # 6. Customer Tokens
    cust1_token = mint_jwt_token(
        user_id=customer_1_id,
        tenant_id=tenant_a_id,
        roles=["customer"],
        permissions=["customer.*"],
    )
    customer_1_headers = {"Authorization": f"Bearer {cust1_token}"}

    cust2_token = mint_jwt_token(
        user_id=customer_2_id,
        tenant_id=tenant_a_id,
        roles=["customer"],
        permissions=["customer.*"],
    )
    customer_2_headers = {"Authorization": f"Bearer {cust2_token}"}

    # 7. Create Catalogue Category, Product and 2 Variants for Tenant A
    cat_a = (
        await client.post(
            "/api/v1/merchant/catalog/categories",
            json={"name": "Bidri Handicrafts", "slug": "bidri-handicrafts"},
            headers=merchant_a_headers,
        )
    ).json()

    prod_a = (
        await client.post(
            "/api/v1/merchant/catalog/products",
            json={
                "category_id": cat_a["id"],
                "name": "Bidriware Silver Coaster Set",
                "slug": "bidriware-silver-coaster-set",
                "status": "active",
                "is_published": True,
                "variants": [
                    {
                        "sku": "COASTER-SET-4",
                        "barcode": "8908880001",
                        "name": "Set of 4 Coasters",
                        "mrp": "1500.00",
                        "base_price": "1299.00",
                    },
                    {
                        "sku": "COASTER-SET-6",
                        "barcode": "8908880002",
                        "name": "Set of 6 Coasters",
                        "mrp": "2200.00",
                        "base_price": "1899.00",
                    },
                ],
            },
            headers=merchant_a_headers,
        )
    ).json()
    variant_1_id = UUID(prod_a["variants"][0]["id"])
    variant_2_id = UUID(prod_a["variants"][1]["id"])

    # 8. Inward Stock: 20 units for Variant 1, 10 units for Variant 2
    await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": str(store_a_id),
            "receipt_number": "RCP-INIT-COASTERS",
            "items": [
                {"variant_id": str(variant_1_id), "quantity_received": 20, "unit_cost": "900.00"},
                {"variant_id": str(variant_2_id), "quantity_received": 10, "unit_cost": "1300.00"},
            ],
        },
        headers=merchant_a_headers,
    )

    return {
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "store_a_id": store_a_id,
        "store_b_id": store_b_id,
        "customer_1_id": customer_1_id,
        "customer_2_id": customer_2_id,
        "customer_1_headers": customer_1_headers,
        "customer_2_headers": customer_2_headers,
        "merchant_a_headers": merchant_a_headers,
        "merchant_b_headers": merchant_b_headers,
        "variant_1_id": variant_1_id,
        "variant_2_id": variant_2_id,
    }


@pytest.mark.asyncio
async def test_cart_persistence_and_guest_merging(client: AsyncClient, setup_order_ecosystem):
    data = setup_order_ecosystem
    cust_headers = data["customer_1_headers"]
    variant_1_id = str(data["variant_1_id"])
    variant_2_id = str(data["variant_2_id"])
    tenant_a_id = str(data["tenant_a_id"])
    store_a_id = str(data["store_a_id"])

    # 1. Customer adds 2 units of Variant 1 to cart
    add_resp = await client.post(
        "/api/v1/cart/items",
        json={"variant_id": variant_1_id, "quantity": 2},
        headers=cust_headers,
    )
    assert add_resp.status_code == 201
    cart1 = add_resp.json()
    assert cart1["total_items"] == 2
    assert cart1["subtotal"] == "2598.00"  # 2 * 1299.00
    item1_id = cart1["items"][0]["id"]

    # 2. Customer updates quantity from 2 to 3
    up_resp = await client.patch(
        f"/api/v1/cart/items/{item1_id}",
        json={"quantity": 3},
        headers=cust_headers,
    )
    assert up_resp.status_code == 200
    assert up_resp.json()["total_items"] == 3
    assert up_resp.json()["subtotal"] == "3897.00"

    # 3. Guest User adds 1 unit of Variant 2 with X-Session-ID
    guest_session = "guest-session-xyz-12345"
    guest_headers = {"X-Session-ID": guest_session}
    g_add = await client.post(
        f"/api/v1/cart/items?tenant_id={tenant_a_id}&store_id={store_a_id}",
        json={"variant_id": variant_2_id, "quantity": 1},
        headers=guest_headers,
    )
    assert g_add.status_code == 201
    g_cart = g_add.json()
    assert g_cart["total_items"] == 1
    assert g_cart["items"][0]["variant_id"] == variant_2_id

    # 4. Customer logs in and merges guest cart into their cart
    merge_resp = await client.post(
        "/api/v1/cart/merge",
        json={"session_id": guest_session},
        headers=cust_headers,
    )
    assert merge_resp.status_code == 200
    merged_cart = merge_resp.json()
    assert merged_cart["total_items"] == 4  # 3 of Variant 1 + 1 of Variant 2
    assert len(merged_cart["items"]) == 2
    assert merged_cart["subtotal"] == "5796.00"  # (3 * 1299.00) + (1 * 1899.00)


@pytest.mark.asyncio
async def test_checkout_atomicity_price_integrity_and_stock_reservation(
    client: AsyncClient, setup_order_ecosystem
):
    data = setup_order_ecosystem
    cust_headers = data["customer_1_headers"]
    merchant_headers = data["merchant_a_headers"]
    variant_1_id = str(data["variant_1_id"])
    store_a_id = str(data["store_a_id"])

    # 1. Add 5 units of Variant 1 to cart
    await client.post(
        "/api/v1/cart/items",
        json={"variant_id": variant_1_id, "quantity": 5},
        headers=cust_headers,
    )

    # 2. Check stock before checkout: on_hand = 20, reserved = 0, available = 20
    bal_before = (
        await client.get(
            f"/api/v1/merchant/inventory/balances/{store_a_id}/{variant_1_id}",
            headers=merchant_headers,
        )
    ).json()
    assert bal_before["on_hand_qty"] == 20
    assert bal_before["reserved_qty"] == 0
    assert bal_before["available_qty"] == 20

    # 3. Perform Checkout (Online Payment)
    checkout_payload = {
        "store_id": store_a_id,
        "shipping_address": {
            "full_name": "Ramesh Kumar",
            "address_line1": "Flat 102, Shanti Nilaya",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
            "phone": "+919999900001",
        },
        "customer_name": "Ramesh Kumar",
        "customer_phone": "+919999900001",
        "customer_email": "ramesh@example.com",
        "payment_method": "online",
        "notes": "Please deliver in evening",
        "idempotency_key": "IDEMP-CHECKOUT-001",
    }

    chk_resp = await client.post(
        "/api/v1/orders/checkout", json=checkout_payload, headers=cust_headers
    )
    assert chk_resp.status_code == 201
    order = chk_resp.json()
    order_number = order["order_number"]
    assert order["status"] == "PENDING_PAYMENT"
    assert order["payment_status"] == "pending"
    assert order["total_amount"] == "6495.00"  # 5 * 1299.00
    assert len(order["items"]) == 1
    assert order["items"][0]["sku"] == "COASTER-SET-4"
    assert order["items"][0]["product_name"] == "Bidriware Silver Coaster Set"
    assert order["items"][0]["quantity"] == 5

    # 4. VERIFY: Stock is reserved atomically via InventoryService!
    # on_hand = 20, reserved = 5, available = 15
    bal_after = (
        await client.get(
            f"/api/v1/merchant/inventory/balances/{store_a_id}/{variant_1_id}",
            headers=merchant_headers,
        )
    ).json()
    assert bal_after["on_hand_qty"] == 20
    assert bal_after["reserved_qty"] == 5
    assert bal_after["available_qty"] == 15

    # 5. VERIFY: Customer Cart was cleared upon checkout
    cart_after = (await client.get("/api/v1/cart", headers=cust_headers)).json()
    assert cart_after["total_items"] == 0
    assert len(cart_after["items"]) == 0

    # 6. VERIFY IDEMPOTENCY: Retrying checkout with same idempotency key returns existing order!
    chk_retry = await client.post(
        "/api/v1/orders/checkout", json=checkout_payload, headers=cust_headers
    )
    assert chk_retry.status_code == 201
    assert chk_retry.json()["id"] == order["id"]
    assert chk_retry.json()["order_number"] == order_number


@pytest.mark.asyncio
async def test_concurrent_checkout_and_overselling_prevention(
    client: AsyncClient, setup_order_ecosystem
):
    data = setup_order_ecosystem
    cust1_headers = data["customer_1_headers"]
    cust2_headers = data["customer_2_headers"]
    variant_2_id = str(data["variant_2_id"])  # Available = 10 units
    store_a_id = str(data["store_a_id"])

    # Customer 1 adds 7 units to cart
    await client.post(
        "/api/v1/cart/items",
        json={"variant_id": variant_2_id, "quantity": 7},
        headers=cust1_headers,
    )

    # Customer 2 adds 5 units to cart
    await client.post(
        "/api/v1/cart/items",
        json={"variant_id": variant_2_id, "quantity": 5},
        headers=cust2_headers,
    )

    # Customer 1 checks out 7 units -> succeeds! (Remaining available = 3)
    c1_resp = await client.post(
        "/api/v1/orders/checkout",
        json={
            "store_id": store_a_id,
            "shipping_address": {
                "full_name": "Ramesh",
                "address_line1": "Bidar",
                "city": "Bidar",
                "state": "KA",
                "postal_code": "585401",
                "phone": "+919999900001",
            },
            "customer_name": "Ramesh",
            "customer_phone": "+919999900001",
            "payment_method": "cod",
        },
        headers=cust1_headers,
    )
    assert c1_resp.status_code == 201
    assert c1_resp.json()["status"] == "CONFIRMED"

    # Customer 2 attempts to checkout 5 units when only 3 are available -> MUST FAIL WITH 409 CONFLICT!
    c2_resp = await client.post(
        "/api/v1/orders/checkout",
        json={
            "store_id": store_a_id,
            "shipping_address": {
                "full_name": "Suresh",
                "address_line1": "Bidar",
                "city": "Bidar",
                "state": "KA",
                "postal_code": "585401",
                "phone": "+919999900002",
            },
            "customer_name": "Suresh",
            "customer_phone": "+919999900002",
            "payment_method": "cod",
        },
        headers=cust2_headers,
    )
    assert c2_resp.status_code == 409
    assert c2_resp.json()["code"] == "INSUFFICIENT_AVAILABLE_STOCK"


@pytest.mark.asyncio
async def test_order_lifecycle_state_machine_and_fulfillment(
    client: AsyncClient, setup_order_ecosystem
):
    data = setup_order_ecosystem
    cust_headers = data["customer_1_headers"]
    merchant_headers = data["merchant_a_headers"]
    variant_1_id = str(data["variant_1_id"])
    store_a_id = str(data["store_a_id"])

    # 1. Checkout 2 units
    await client.post(
        "/api/v1/cart/items", json={"variant_id": variant_1_id, "quantity": 2}, headers=cust_headers
    )
    order = (
        await client.post(
            "/api/v1/orders/checkout",
            json={
                "store_id": store_a_id,
                "shipping_address": {
                    "full_name": "Ramesh",
                    "address_line1": "Bidar",
                    "city": "Bidar",
                    "state": "KA",
                    "postal_code": "585401",
                    "phone": "+919999900001",
                },
                "customer_name": "Ramesh",
                "customer_phone": "+919999900001",
                "payment_method": "online",
            },
            headers=cust_headers,
        )
    ).json()
    order_id = order["id"]
    order_number = order["order_number"]
    assert order["status"] == "PENDING_PAYMENT"

    # 2. Payment Gateway Callback: Success
    pay_resp = await client.post(
        f"/api/v1/orders/{order_id}/payments/callback",
        json={
            "transaction_reference": f"TXN-{order_number}-01",
            "gateway_status": "success",
            "gateway_payload": {"bank_ref": "HDFC12345678"},
        },
        headers=cust_headers,
    )
    assert pay_resp.status_code == 200
    assert pay_resp.json()["payment_status"] == "captured"
    assert pay_resp.json()["status"] == "CONFIRMED"

    # 3. Invalid Transition: Cannot jump directly from CONFIRMED to DELIVERED
    bad_trans = await client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        json={"status": "DELIVERED"},
        headers=merchant_headers,
    )
    assert bad_trans.status_code == 409
    assert bad_trans.json()["code"] == "INVALID_STATUS_TRANSITION"

    # 4. Valid Transition: CONFIRMED -> PROCESSING
    p_resp = await client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        json={"status": "PROCESSING", "notes": "Items picked and packed"},
        headers=merchant_headers,
    )
    assert p_resp.status_code == 200
    assert p_resp.json()["status"] == "PROCESSING"

    # 5. Transition to DISPATCHED -> Triggers InventoryService.dispatch_stock!
    d_resp = await client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        json={"status": "DISPATCHED", "notes": "Handed to BlueDart AWB# 98765432"},
        headers=merchant_headers,
    )
    assert d_resp.status_code == 200
    assert d_resp.json()["status"] == "DISPATCHED"
    assert d_resp.json()["fulfillment_status"] == "fulfilled"

    # Verify inventory was written off from on-hand:
    bal_disp = (
        await client.get(
            f"/api/v1/merchant/inventory/balances/{store_a_id}/{variant_1_id}",
            headers=merchant_headers,
        )
    ).json()
    assert bal_disp["reserved_qty"] == 0
    assert bal_disp["on_hand_qty"] == 18  # 20 - 2

    # 6. Transition to DELIVERED
    del_resp = await client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        json={"status": "DELIVERED", "notes": "Delivered and signed by customer"},
        headers=merchant_headers,
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "DELIVERED"

    # 7. Customer Return & Restocking
    ret_resp = await client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        json={"status": "RETURNED", "notes": "Customer exchange, verified intact"},
        headers=merchant_headers,
    )
    assert ret_resp.status_code == 200
    assert ret_resp.json()["status"] == "RETURNED"

    # Verify stock was restored back into on_hand:
    bal_ret = (
        await client.get(
            f"/api/v1/merchant/inventory/balances/{store_a_id}/{variant_1_id}",
            headers=merchant_headers,
        )
    ).json()
    assert bal_ret["on_hand_qty"] == 20
    assert bal_ret["available_qty"] == 20


@pytest.mark.asyncio
async def test_order_cancellation_releases_reserved_stock(
    client: AsyncClient, setup_order_ecosystem
):
    data = setup_order_ecosystem
    cust_headers = data["customer_1_headers"]
    merchant_headers = data["merchant_a_headers"]
    variant_1_id = str(data["variant_1_id"])
    store_a_id = str(data["store_a_id"])

    # 1. Checkout 4 units
    await client.post(
        "/api/v1/cart/items", json={"variant_id": variant_1_id, "quantity": 4}, headers=cust_headers
    )
    order = (
        await client.post(
            "/api/v1/orders/checkout",
            json={
                "store_id": store_a_id,
                "shipping_address": {
                    "full_name": "Ramesh",
                    "address_line1": "Bidar",
                    "city": "Bidar",
                    "state": "KA",
                    "postal_code": "585401",
                    "phone": "+919999900001",
                },
                "customer_name": "Ramesh",
                "customer_phone": "+919999900001",
                "payment_method": "cod",
            },
            headers=cust_headers,
        )
    ).json()
    order_number = order["order_number"]

    # Stock is reserved: reserved = 4, available = 16
    bal_res = (
        await client.get(
            f"/api/v1/merchant/inventory/balances/{store_a_id}/{variant_1_id}",
            headers=merchant_headers,
        )
    ).json()
    assert bal_res["reserved_qty"] == 4
    assert bal_res["available_qty"] == 16

    # 2. Customer cancels order
    cancel_resp = await client.post(
        f"/api/v1/orders/{order_number}/cancel",
        json={"reason": "Ordered wrong color by mistake"},
        headers=cust_headers,
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    # 3. VERIFY: Reserved stock was released back to available pool!
    bal_rel = (
        await client.get(
            f"/api/v1/merchant/inventory/balances/{store_a_id}/{variant_1_id}",
            headers=merchant_headers,
        )
    ).json()
    assert bal_rel["reserved_qty"] == 0
    assert bal_rel["available_qty"] == 20


@pytest.mark.asyncio
async def test_reservation_expiry_background_processor(client: AsyncClient, setup_order_ecosystem):
    data = setup_order_ecosystem
    cust_headers = data["customer_1_headers"]
    merchant_headers = data["merchant_a_headers"]
    variant_1_id = str(data["variant_1_id"])
    store_a_id = str(data["store_a_id"])

    # 1. Checkout 3 units online (status=PENDING_PAYMENT, expires in 15 min)
    await client.post(
        "/api/v1/cart/items", json={"variant_id": variant_1_id, "quantity": 3}, headers=cust_headers
    )
    order = (
        await client.post(
            "/api/v1/orders/checkout",
            json={
                "store_id": store_a_id,
                "shipping_address": {
                    "full_name": "Ramesh",
                    "address_line1": "Bidar",
                    "city": "Bidar",
                    "state": "KA",
                    "postal_code": "585401",
                    "phone": "+919999900001",
                },
                "customer_name": "Ramesh",
                "customer_phone": "+919999900001",
                "payment_method": "online",
            },
            headers=cust_headers,
        )
    ).json()
    order_id = order["id"]

    # Stock is reserved: reserved = 3, available = 17
    bal1 = (
        await client.get(
            f"/api/v1/merchant/inventory/balances/{store_a_id}/{variant_1_id}",
            headers=merchant_headers,
        )
    ).json()
    assert bal1["reserved_qty"] == 3
    assert bal1["available_qty"] == 17

    # 2. Artificially expire the reservation in PostgreSQL (simulate passage of time)
    past_time = datetime.now(UTC) - timedelta(minutes=5)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE orders SET reservation_expires_at = :past WHERE id = :oid"),
            {"past": past_time, "oid": order_id},
        )

    # 3. Trigger expiry processor
    exp_resp = await client.post("/api/v1/merchant/orders/process-expiry", headers=merchant_headers)
    assert exp_resp.status_code == 200
    assert exp_resp.json()["released_count"] == 1

    # 4. Verify order is CANCELLED and stock is restored
    order_check = (
        await client.get(f"/api/v1/merchant/orders/{order_id}", headers=merchant_headers)
    ).json()
    assert order_check["status"] == "CANCELLED"
    assert order_check["reservation_released"] is True

    bal_restored = (
        await client.get(
            f"/api/v1/merchant/inventory/balances/{store_a_id}/{variant_1_id}",
            headers=merchant_headers,
        )
    ).json()
    assert bal_restored["reserved_qty"] == 0
    assert bal_restored["available_qty"] == 20

    # 5. IDEMPOTENT: Running expiry processor again releases 0 orders!
    exp_retry = await client.post(
        "/api/v1/merchant/orders/process-expiry", headers=merchant_headers
    )
    assert exp_retry.status_code == 200
    assert exp_retry.json()["released_count"] == 0


@pytest.mark.asyncio
async def test_cross_customer_and_cross_tenant_order_isolation(
    client: AsyncClient, setup_order_ecosystem
):
    data = setup_order_ecosystem
    cust1_headers = data["customer_1_headers"]
    cust2_headers = data["customer_2_headers"]
    merchant_b_headers = data["merchant_b_headers"]
    variant_1_id = str(data["variant_1_id"])
    store_a_id = str(data["store_a_id"])

    # Customer 1 places order
    await client.post(
        "/api/v1/cart/items",
        json={"variant_id": variant_1_id, "quantity": 1},
        headers=cust1_headers,
    )
    order1 = (
        await client.post(
            "/api/v1/orders/checkout",
            json={
                "store_id": store_a_id,
                "shipping_address": {
                    "full_name": "Ramesh",
                    "address_line1": "Bidar",
                    "city": "Bidar",
                    "state": "KA",
                    "postal_code": "585401",
                    "phone": "+919999900001",
                },
                "customer_name": "Ramesh",
                "customer_phone": "+919999900001",
                "payment_method": "cod",
            },
            headers=cust1_headers,
        )
    ).json()
    order1_id = order1["id"]
    order1_number = order1["order_number"]

    # 1. Customer 2 attempts to fetch Customer 1's order -> 404 Not Found
    c2_get = await client.get(f"/api/v1/orders/{order1_number}", headers=cust2_headers)
    assert c2_get.status_code == 404

    # 2. Customer 2 attempts to cancel Customer 1's order -> 404 Not Found
    c2_cancel = await client.post(
        f"/api/v1/orders/{order1_number}/cancel",
        json={"reason": "Hacking attempt"},
        headers=cust2_headers,
    )
    assert c2_cancel.status_code == 404

    # 3. Merchant B attempts to fetch Merchant A's order -> 404 Not Found
    mb_get = await client.get(f"/api/v1/merchant/orders/{order1_id}", headers=merchant_b_headers)
    assert mb_get.status_code == 404

    # 4. Merchant B attempts to transition Merchant A's order status -> 404 Not Found
    mb_patch = await client.patch(
        f"/api/v1/merchant/orders/{order1_id}/status",
        json={"status": "PROCESSING"},
        headers=merchant_b_headers,
    )
    assert mb_patch.status_code == 404
