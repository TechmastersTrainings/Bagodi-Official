import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text

from app.db.session import engine


@pytest_asyncio.fixture
async def setup_pricing_ecosystem(client: AsyncClient, mint_jwt_token):
    """Sets up an isolated dual-tenant environment with stores, categories, products,

    variants, and initial stock balances for testing pricing and promotions.
    """
    # 1. Create Platform Admin
    platform_token = mint_jwt_token(
        is_platform_user=True,
        permissions=["platform.*", "tenants.*"],
    )
    platform_headers = {"Authorization": f"Bearer {platform_token}"}

    # 2. Create Tenant A (Bagodi)
    resp_tenant_a = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Bagodi Handicrafts",
            "slug": "bagodi-pricing",
            "business_type": "handicrafts",
            "email": "pricing@bagodi.in",
            "phone": "+919888800001",
        },
        headers=platform_headers,
    )
    tenant_a_id = UUID(resp_tenant_a.json()["id"])
    await client.patch(
        f"/api/v1/platform/tenants/{tenant_a_id}/status",
        json={"status": "active"},
        headers=platform_headers,
    )

    # 3. Create Tenant B (Second Merchant for Isolation Testing)
    resp_tenant_b = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Second Merchant",
            "slug": "second-pricing",
            "business_type": "textiles",
            "email": "pricing@second.in",
            "phone": "+919888800002",
        },
        headers=platform_headers,
    )
    tenant_b_id = UUID(resp_tenant_b.json()["id"])
    await client.patch(
        f"/api/v1/platform/tenants/{tenant_b_id}/status",
        json={"status": "active"},
        headers=platform_headers,
    )

    # 4. Merchant A & B Staff Tokens
    merchant_a_token = mint_jwt_token(
        tenant_id=tenant_a_id,
        permissions=["stores.*", "catalog.*", "inventory.*", "orders.*", "pricing.*"],
    )
    merchant_a_headers = {"Authorization": f"Bearer {merchant_a_token}"}

    merchant_b_token = mint_jwt_token(
        tenant_id=tenant_b_id,
        permissions=["stores.*", "catalog.*", "inventory.*", "orders.*", "pricing.*"],
    )
    merchant_b_headers = {"Authorization": f"Bearer {merchant_b_token}"}

    # 5. Create Stores
    resp_store_a = await client.post(
        "/api/v1/stores",
        json={
            "name": "Bagodi Main Store",
            "code": "BGD-STORE-01",
            "address_line": "Bidar Fort Gate",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        headers=merchant_a_headers,
    )
    store_a_id = UUID(resp_store_a.json()["id"])

    resp_store_b = await client.post(
        "/api/v1/stores",
        json={
            "name": "Second Store",
            "code": "SEC-STORE-01",
            "address_line": "Market Road",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        headers=merchant_b_headers,
    )
    store_b_id = UUID(resp_store_b.json()["id"])

    # 6. Insert Verified Customers into users table
    async with engine.begin() as conn:
        res_u1 = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919999911111', 'pricing_c1@example.com', 'Anil Deshmukh', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        customer_1_id = res_u1.scalar_one()

        res_u2 = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919999922222', 'pricing_c2@example.com', 'Pooja Hegde', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        customer_2_id = res_u2.scalar_one()

        res_u3 = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919999933333', 'pricing_c3@example.com', 'Rohan Gupta', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        customer_3_id = res_u3.scalar_one()

    # 7. Customer Auth Headers
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

    cust3_token = mint_jwt_token(
        user_id=customer_3_id,
        tenant_id=tenant_a_id,
        roles=["customer"],
        permissions=["customer.*"],
    )
    customer_3_headers = {"Authorization": f"Bearer {cust3_token}"}

    # 8. Catalogue for Tenant A: Category, Brand, Product, 2 Variants
    cat_resp = await client.post(
        "/api/v1/merchant/catalog/categories",
        json={"name": "Bidriware Craft", "slug": "bidriware-craft"},
        headers=merchant_a_headers,
    )
    category_id = UUID(cat_resp.json()["id"])

    prod_resp = await client.post(
        "/api/v1/merchant/catalog/products",
        json={
            "name": "Bidri Silver Inlay Vase",
            "slug": "bidri-silver-vase",
            "category_id": str(category_id),
            "is_published": True,
            "status": "active",
        },
        headers=merchant_a_headers,
    )
    product_id = UUID(prod_resp.json()["id"])

    # Variant 1: Base Price ₹2,000.00
    v1_resp = await client.post(
        f"/api/v1/merchant/catalog/products/{product_id}/variants",
        json={
            "name": "Small Vase 6 inch",
            "sku": "VASE-S-6INCH",
            "mrp": "2500.00",
            "base_price": "2000.00",
            "status": "active",
        },
        headers=merchant_a_headers,
    )
    variant_1_id = UUID(v1_resp.json()["id"])

    # Variant 2: Base Price ₹4,000.00
    v2_resp = await client.post(
        f"/api/v1/merchant/catalog/products/{product_id}/variants",
        json={
            "name": "Large Vase 12 inch",
            "sku": "VASE-L-12INCH",
            "mrp": "5000.00",
            "base_price": "4000.00",
            "status": "active",
        },
        headers=merchant_a_headers,
    )
    variant_2_id = UUID(v2_resp.json()["id"])

    # Stock balances: 50 units each in Store A
    async with engine.begin() as conn:
        for vid in [variant_1_id, variant_2_id]:
            await conn.execute(
                text(
                    "INSERT INTO stock_balances (id, tenant_id, store_id, variant_id, on_hand_qty, reserved_qty, in_transit_qty, available_qty, reorder_threshold, low_stock_alert, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), :tid, :sid, :vid, 50, 0, 0, 50, 5, false, now(), now());"
                ),
                {"tid": tenant_a_id, "sid": store_a_id, "vid": vid},
            )

    return {
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "store_a_id": store_a_id,
        "store_b_id": store_b_id,
        "category_id": category_id,
        "product_id": product_id,
        "variant_1_id": variant_1_id,
        "variant_2_id": variant_2_id,
        "customer_1_id": customer_1_id,
        "customer_2_id": customer_2_id,
        "customer_3_id": customer_3_id,
        "customer_1_headers": customer_1_headers,
        "customer_2_headers": customer_2_headers,
        "customer_3_headers": customer_3_headers,
        "merchant_a_headers": merchant_a_headers,
        "merchant_b_headers": merchant_b_headers,
    }


@pytest.mark.asyncio
async def test_promotion_crud_and_audit_logging(client: AsyncClient, setup_pricing_ecosystem):
    data = setup_pricing_ecosystem
    merchant_headers = data["merchant_a_headers"]
    variant_1_id = str(data["variant_1_id"])

    now = datetime.now(UTC)
    start_time = now - timedelta(days=1)
    end_time = now + timedelta(days=30)

    # 1. Create Promotion
    create_payload = {
        "name": "Diwali 10% Off Small Vase",
        "description": "Festive 10 percent discount",
        "promotion_type": "PERCENTAGE",
        "scope": "VARIANT",
        "target_id": variant_1_id,
        "discount_value": "10.00",
        "max_discount_amount": "250.00",
        "min_order_amount": "0.00",
        "start_date": start_time.isoformat(),
        "end_date": end_time.isoformat(),
        "status": "active",
        "priority": 5,
        "is_stackable": False,
    }
    create_resp = await client.post("/api/v1/merchant/pricing/promotions", json=create_payload, headers=merchant_headers)
    assert create_resp.status_code == 201
    promo = create_resp.json()
    promo_id = promo["id"]
    assert promo["name"] == "Diwali 10% Off Small Vase"
    assert promo["discount_value"] == "10.00"

    # 2. Get Promotion by ID
    get_resp = await client.get(f"/api/v1/merchant/pricing/promotions/{promo_id}", headers=merchant_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == promo_id

    # 3. Update Promotion
    patch_resp = await client.patch(
        f"/api/v1/merchant/pricing/promotions/{promo_id}",
        json={"name": "Updated Festive 15%", "discount_value": "15.00", "priority": 10},
        headers=merchant_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Updated Festive 15%"
    assert patch_resp.json()["discount_value"] == "15.00"

    # 4. Check Audit Logs: Should contain CREATE and UPDATE entries
    audit_resp = await client.get("/api/v1/merchant/pricing/audit-logs?entity_type=promotion", headers=merchant_headers)
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) >= 2
    actions = [l["action"] for l in logs]
    assert "CREATE" in actions
    assert "UPDATE" in actions

    # 5. Archive (Delete) Promotion
    del_resp = await client.delete(f"/api/v1/merchant/pricing/promotions/{promo_id}", headers=merchant_headers)
    assert del_resp.status_code == 204

    # Verify status changed to archived
    check_del = await client.get(f"/api/v1/merchant/pricing/promotions/{promo_id}", headers=merchant_headers)
    assert check_del.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_item_promotion_precedence_hierarchy(client: AsyncClient, setup_pricing_ecosystem):
    """Verifies Specificity Precedence: VARIANT (Rank 3) > PRODUCT (Rank 2) > CATEGORY (Rank 1).

    Variant 1 has Variant promo (₹300 off).
    Parent Product has Product promo (15% off = ₹300 for V1, ₹600 for V2).
    Parent Category has Category promo (10% off).

    Outcome:
    - Variant 1 receives Variant promo (₹300 flat off), overriding Product promo.
    - Variant 2 receives Product promo (15% off = ₹600 off), overriding Category promo.
    """
    data = setup_pricing_ecosystem
    merchant_headers = data["merchant_a_headers"]
    cust_headers = data["customer_1_headers"]
    variant_1_id = str(data["variant_1_id"])
    variant_2_id = str(data["variant_2_id"])
    product_id = str(data["product_id"])
    category_id = str(data["category_id"])

    now = datetime.now(UTC)
    start_time = now - timedelta(days=1)
    end_time = now + timedelta(days=30)

    # Category Promo: 10% Off
    await client.post(
        "/api/v1/merchant/pricing/promotions",
        json={
            "name": "Category 10% Off",
            "promotion_type": "PERCENTAGE",
            "scope": "CATEGORY",
            "target_id": category_id,
            "discount_value": "10.00",
            "start_date": start_time.isoformat(),
            "end_date": end_time.isoformat(),
            "priority": 1,
        },
        headers=merchant_headers,
    )

    # Product Promo: 15% Off
    await client.post(
        "/api/v1/merchant/pricing/promotions",
        json={
            "name": "Product 15% Off",
            "promotion_type": "PERCENTAGE",
            "scope": "PRODUCT",
            "target_id": product_id,
            "discount_value": "15.00",
            "start_date": start_time.isoformat(),
            "end_date": end_time.isoformat(),
            "priority": 2,
        },
        headers=merchant_headers,
    )

    # Variant 1 Specific Promo: Fixed ₹300.00 Off
    await client.post(
        "/api/v1/merchant/pricing/promotions",
        json={
            "name": "Variant 1 Fixed ₹300 Off",
            "promotion_type": "FIXED_AMOUNT",
            "scope": "VARIANT",
            "target_id": variant_1_id,
            "discount_value": "300.00",
            "start_date": start_time.isoformat(),
            "end_date": end_time.isoformat(),
            "priority": 3,
        },
        headers=merchant_headers,
    )

    # Customer adds 1 unit of V1 (base ₹2000) and 1 unit of V2 (base ₹4000) to cart
    await client.post("/api/v1/cart/items", json={"variant_id": variant_1_id, "quantity": 1}, headers=cust_headers)
    await client.post("/api/v1/cart/items", json={"variant_id": variant_2_id, "quantity": 1}, headers=cust_headers)

    # Get authoritative price quote
    quote_resp = await client.get("/api/v1/pricing/quote", headers=cust_headers)
    assert quote_resp.status_code == 200
    quote = quote_resp.json()

    assert quote["subtotal"] == "6000.00"  # 2000 + 4000

    item1 = next(i for i in quote["items"] if i["variant_id"] == variant_1_id)
    assert item1["original_unit_price"] == "2000.00"
    assert item1["unit_price"] == "1700.00"  # 2000 - 300 (Variant promo wins!)
    assert item1["discount_amount"] == "300.00"
    assert item1["applied_promotion"]["title"] == "Variant 1 Fixed ₹300 Off"

    item2 = next(i for i in quote["items"] if i["variant_id"] == variant_2_id)
    assert item2["original_unit_price"] == "4000.00"
    assert item2["unit_price"] == "3400.00"  # 4000 - 15% (600) (Product promo wins over Category promo!)
    assert item2["discount_amount"] == "600.00"
    assert item2["applied_promotion"]["title"] == "Product 15% Off"

    assert quote["total_discount"] == "900.00"  # 300 + 600
    assert quote["total_amount"] == "5100.00"  # 6000 - 900


@pytest.mark.asyncio
async def test_coupon_validation_expiry_and_minimum_order(client: AsyncClient, setup_pricing_ecosystem):
    data = setup_pricing_ecosystem
    merchant_headers = data["merchant_a_headers"]
    cust_headers = data["customer_1_headers"]
    variant_1_id = str(data["variant_1_id"])

    now = datetime.now(UTC)

    # 1. Inactive Coupon
    await client.post(
        "/api/v1/merchant/pricing/coupons",
        json={
            "code": "INACTIVE10",
            "name": "Inactive Voucher",
            "discount_type": "PERCENTAGE",
            "discount_value": "10.00",
            "start_date": (now - timedelta(days=5)).isoformat(),
            "end_date": (now + timedelta(days=5)).isoformat(),
            "status": "inactive",
        },
        headers=merchant_headers,
    )

    # 2. Expired Coupon
    await client.post(
        "/api/v1/merchant/pricing/coupons",
        json={
            "code": "EXPIRED20",
            "name": "Old Voucher",
            "discount_type": "PERCENTAGE",
            "discount_value": "20.00",
            "start_date": (now - timedelta(days=10)).isoformat(),
            "end_date": (now - timedelta(days=1)).isoformat(),
            "status": "active",
        },
        headers=merchant_headers,
    )

    # 3. High Minimum Order Coupon (min ₹5,000)
    await client.post(
        "/api/v1/merchant/pricing/coupons",
        json={
            "code": "BIGORDER500",
            "name": "Big Spender ₹500 Off",
            "discount_type": "FIXED_AMOUNT",
            "discount_value": "500.00",
            "min_order_amount": "5000.00",
            "start_date": (now - timedelta(days=1)).isoformat(),
            "end_date": (now + timedelta(days=10)).isoformat(),
            "status": "active",
        },
        headers=merchant_headers,
    )

    # 4. Valid Active Coupon (Flat ₹200 off)
    await client.post(
        "/api/v1/merchant/pricing/coupons",
        json={
            "code": "SAVE200",
            "name": "Save ₹200 Flat",
            "discount_type": "FIXED_AMOUNT",
            "discount_value": "200.00",
            "min_order_amount": "1000.00",
            "start_date": (now - timedelta(days=1)).isoformat(),
            "end_date": (now + timedelta(days=10)).isoformat(),
            "status": "active",
        },
        headers=merchant_headers,
    )

    # Add 1 unit of V1 (₹2,000) to cart
    await client.post("/api/v1/cart/items", json={"variant_id": variant_1_id, "quantity": 1}, headers=cust_headers)

    # Try applying INACTIVE10 -> 400 COUPON_INACTIVE
    resp_inact = await client.post("/api/v1/cart/coupon", json={"code": "INACTIVE10"}, headers=cust_headers)
    assert resp_inact.status_code == 400
    assert resp_inact.json()["code"] == "COUPON_INACTIVE"

    # Try applying EXPIRED20 -> 400 COUPON_EXPIRED
    resp_exp = await client.post("/api/v1/cart/coupon", json={"code": "EXPIRED20"}, headers=cust_headers)
    assert resp_exp.status_code == 400
    assert resp_exp.json()["code"] == "COUPON_EXPIRED"

    # Try applying BIGORDER500 on ₹2000 cart -> 400 COUPON_MIN_ORDER_NOT_MET
    resp_min = await client.post("/api/v1/cart/coupon", json={"code": "BIGORDER500"}, headers=cust_headers)
    assert resp_min.status_code == 400
    assert resp_min.json()["code"] == "COUPON_MIN_ORDER_NOT_MET"

    # Apply SAVE200 -> 200 OK
    resp_valid = await client.post("/api/v1/cart/coupon", json={"code": "SAVE200"}, headers=cust_headers)
    assert resp_valid.status_code == 200
    cart_data = resp_valid.json()
    assert cart_data["coupon_code"] == "SAVE200"
    assert cart_data["discount_amount"] == "200.00"
    assert cart_data["total_amount"] == "1800.00"  # 2000 - 200

    # Delete coupon from cart
    del_c_resp = await client.delete("/api/v1/cart/coupon", headers=cust_headers)
    assert del_c_resp.status_code == 200
    assert del_c_resp.json()["coupon_code"] is None
    assert del_c_resp.json()["total_amount"] == "2000.00"


@pytest.mark.asyncio
async def test_coupon_usage_limits_and_per_customer_limits(client: AsyncClient, setup_pricing_ecosystem):
    """Verifies that coupons strictly enforce:

    1. usage_limit_per_customer (max redemptions per user)
    2. total_usage_limit (max global redemptions across all users)
    """
    data = setup_pricing_ecosystem
    merchant_headers = data["merchant_a_headers"]
    cust1_headers = data["customer_1_headers"]
    cust2_headers = data["customer_2_headers"]
    cust3_headers = data["customer_3_headers"]
    store_a_id = str(data["store_a_id"])
    variant_1_id = str(data["variant_1_id"])

    now = datetime.now(UTC)

    # Create coupon with total_usage_limit = 2, usage_limit_per_customer = 1
    await client.post(
        "/api/v1/merchant/pricing/coupons",
        json={
            "code": "FIRST2USERS",
            "name": "First 2 Users Voucher",
            "discount_type": "FIXED_AMOUNT",
            "discount_value": "100.00",
            "min_order_amount": "500.00",
            "start_date": (now - timedelta(days=1)).isoformat(),
            "end_date": (now + timedelta(days=10)).isoformat(),
            "status": "active",
            "total_usage_limit": 2,
            "usage_limit_per_customer": 1,
        },
        headers=merchant_headers,
    )

    checkout_payload = {
        "store_id": store_a_id,
        "shipping_address": {
            "full_name": "Customer",
            "address_line1": "Bidar",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
            "phone": "+919999911111",
        },
        "customer_name": "Customer",
        "customer_phone": "+919999911111",
        "payment_method": "cod",
        "coupon_code": "FIRST2USERS",
    }

    # 1. Customer 1 checks out with FIRST2USERS -> SUCCESS (1st redemption)
    await client.post("/api/v1/cart/items", json={"variant_id": variant_1_id, "quantity": 1}, headers=cust1_headers)
    ord1_resp = await client.post("/api/v1/orders/checkout", json=checkout_payload, headers=cust1_headers)
    assert ord1_resp.status_code == 201
    ord1 = ord1_resp.json()
    assert ord1["discount_amount"] == "100.00"
    assert ord1["total_amount"] == "1900.00"  # 2000 - 100

    # 2. Customer 1 tries to checkout again with FIRST2USERS -> FAILS (per-customer limit exceeded)
    await client.post("/api/v1/cart/items", json={"variant_id": variant_1_id, "quantity": 1}, headers=cust1_headers)
    ord1_repeat = await client.post("/api/v1/orders/checkout", json=checkout_payload, headers=cust1_headers)
    assert ord1_repeat.status_code == 400
    assert ord1_repeat.json()["code"] == "CUSTOMER_COUPON_LIMIT_EXCEEDED"

    # 3. Customer 2 checks out with FIRST2USERS -> SUCCESS (2nd redemption, reaches total limit)
    await client.post("/api/v1/cart/items", json={"variant_id": variant_1_id, "quantity": 1}, headers=cust2_headers)
    ord2_resp = await client.post("/api/v1/orders/checkout", json=checkout_payload, headers=cust2_headers)
    assert ord2_resp.status_code == 201
    assert ord2_resp.json()["total_amount"] == "1900.00"

    # 4. Customer 3 tries to checkout with FIRST2USERS -> FAILS (total_usage_limit reached)
    await client.post("/api/v1/cart/items", json={"variant_id": variant_1_id, "quantity": 1}, headers=cust3_headers)
    ord3_resp = await client.post("/api/v1/orders/checkout", json=checkout_payload, headers=cust3_headers)
    assert ord3_resp.status_code == 400
    assert ord3_resp.json()["code"] == "COUPON_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_order_cancellation_reverts_coupon_redemption(client: AsyncClient, setup_pricing_ecosystem):
    """Verifies that when an order is cancelled, the coupon redemption is atomically reverted

    and the customer can redeem it again.
    """
    data = setup_pricing_ecosystem
    merchant_headers = data["merchant_a_headers"]
    cust_headers = data["customer_1_headers"]
    store_a_id = str(data["store_a_id"])
    variant_1_id = str(data["variant_1_id"])

    now = datetime.now(UTC)

    # Create single-use coupon
    c_resp = await client.post(
        "/api/v1/merchant/pricing/coupons",
        json={
            "code": "ONEUSEONLY",
            "name": "One Use Only",
            "discount_type": "FIXED_AMOUNT",
            "discount_value": "150.00",
            "min_order_amount": "1000.00",
            "start_date": (now - timedelta(days=1)).isoformat(),
            "end_date": (now + timedelta(days=10)).isoformat(),
            "status": "active",
            "total_usage_limit": 1,
            "usage_limit_per_customer": 1,
        },
        headers=merchant_headers,
    )
    coupon_id = c_resp.json()["id"]

    # Customer checks out
    await client.post("/api/v1/cart/items", json={"variant_id": variant_1_id, "quantity": 1}, headers=cust_headers)
    ord_resp = await client.post(
        "/api/v1/orders/checkout",
        json={
            "store_id": store_a_id,
            "shipping_address": {
                "full_name": "Customer",
                "address_line1": "Bidar",
                "city": "Bidar",
                "state": "Karnataka",
                "postal_code": "585401",
                "phone": "+919999911111",
            },
            "customer_name": "Customer",
            "customer_phone": "+919999911111",
            "payment_method": "cod",
            "coupon_code": "ONEUSEONLY",
        },
        headers=cust_headers,
    )
    assert ord_resp.status_code == 201
    order_data = ord_resp.json()
    order_number = order_data["order_number"]

    # Verify coupon total_redeemed_count is 1
    c_check = (await client.get(f"/api/v1/merchant/pricing/coupons/{coupon_id}", headers=merchant_headers)).json()
    assert c_check["total_redeemed_count"] == 1

    # Customer cancels order
    cancel_resp = await client.post(
        f"/api/v1/orders/{order_number}/cancel",
        json={"reason": "Customer cancellation test"},
        headers=cust_headers,
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    # Verify coupon total_redeemed_count is reverted to 0
    c_check2 = (await client.get(f"/api/v1/merchant/pricing/coupons/{coupon_id}", headers=merchant_headers)).json()
    assert c_check2["total_redeemed_count"] == 0

    # Customer can successfully redeem ONEUSEONLY again!
    await client.post("/api/v1/cart/items", json={"variant_id": variant_1_id, "quantity": 1}, headers=cust_headers)
    re_ord_resp = await client.post(
        "/api/v1/orders/checkout",
        json={
            "store_id": store_a_id,
            "shipping_address": {
                "full_name": "Customer",
                "address_line1": "Bidar",
                "city": "Bidar",
                "state": "Karnataka",
                "postal_code": "585401",
                "phone": "+919999911111",
            },
            "customer_name": "Customer",
            "customer_phone": "+919999911111",
            "payment_method": "cod",
            "coupon_code": "ONEUSEONLY",
        },
        headers=cust_headers,
    )
    assert re_ord_resp.status_code == 201
    assert re_ord_resp.json()["discount_amount"] == "150.00"


@pytest.mark.asyncio
async def test_concurrent_coupon_redemption_race_condition(client: AsyncClient, setup_pricing_ecosystem):
    """Verifies PostgreSQL row-level locking (with_for_update) prevents concurrent over-redemption

    when two parallel checkout tasks attempt to claim the final single available coupon slot.
    """
    data = setup_pricing_ecosystem
    merchant_headers = data["merchant_a_headers"]
    cust1_headers = data["customer_1_headers"]
    cust2_headers = data["customer_2_headers"]
    store_a_id = str(data["store_a_id"])
    variant_1_id = str(data["variant_1_id"])

    now = datetime.now(UTC)

    # Coupon with total_usage_limit = 1
    await client.post(
        "/api/v1/merchant/pricing/coupons",
        json={
            "code": "CONCURRENT1",
            "name": "Single Slot Flash Coupon",
            "discount_type": "FIXED_AMOUNT",
            "discount_value": "250.00",
            "min_order_amount": "500.00",
            "start_date": (now - timedelta(days=1)).isoformat(),
            "end_date": (now + timedelta(days=10)).isoformat(),
            "status": "active",
            "total_usage_limit": 1,
            "usage_limit_per_customer": 1,
        },
        headers=merchant_headers,
    )

    # Customer 1 and Customer 2 both add items to cart
    await client.post("/api/v1/cart/items", json={"variant_id": variant_1_id, "quantity": 1}, headers=cust1_headers)
    await client.post("/api/v1/cart/items", json={"variant_id": variant_1_id, "quantity": 1}, headers=cust2_headers)

    payload_1 = {
        "store_id": store_a_id,
        "shipping_address": {
            "full_name": "User 1",
            "address_line1": "Bidar",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
            "phone": "+919999911111",
        },
        "customer_name": "User 1",
        "customer_phone": "+919999911111",
        "payment_method": "cod",
        "coupon_code": "CONCURRENT1",
    }
    payload_2 = {
        "store_id": store_a_id,
        "shipping_address": {
            "full_name": "User 2",
            "address_line1": "Bidar",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
            "phone": "+919999922222",
        },
        "customer_name": "User 2",
        "customer_phone": "+919999922222",
        "payment_method": "cod",
        "coupon_code": "CONCURRENT1",
    }

    # Execute concurrent checkout requests
    results = await asyncio.gather(
        client.post("/api/v1/orders/checkout", json=payload_1, headers=cust1_headers),
        client.post("/api/v1/orders/checkout", json=payload_2, headers=cust2_headers),
        return_exceptions=True,
    )

    status_codes = [r.status_code for r in results if not isinstance(r, Exception)]
    # Exactly one checkout MUST succeed (201) and the other MUST be rejected (400 or 409)
    assert 201 in status_codes
    assert any(code in [400, 409] for code in status_codes)


@pytest.mark.asyncio
async def test_cross_tenant_pricing_and_coupon_isolation(client: AsyncClient, setup_pricing_ecosystem):
    """Verifies that promotions and coupons belonging to Tenant A cannot be viewed, modified,

    or redeemed by Tenant B staff or customers.
    """
    data = setup_pricing_ecosystem
    merchant_a_headers = data["merchant_a_headers"]
    merchant_b_headers = data["merchant_b_headers"]
    variant_1_id = str(data["variant_1_id"])

    now = datetime.now(UTC)

    # 1. Tenant A creates Coupon & Promotion
    c_resp = await client.post(
        "/api/v1/merchant/pricing/coupons",
        json={
            "code": "TENANTAONLY",
            "name": "Tenant A Secret Voucher",
            "discount_type": "PERCENTAGE",
            "discount_value": "10.00",
            "start_date": (now - timedelta(days=1)).isoformat(),
            "end_date": (now + timedelta(days=10)).isoformat(),
            "status": "active",
        },
        headers=merchant_a_headers,
    )
    coupon_a_id = c_resp.json()["id"]

    p_resp = await client.post(
        "/api/v1/merchant/pricing/promotions",
        json={
            "name": "Tenant A Promo",
            "promotion_type": "FIXED_AMOUNT",
            "scope": "VARIANT",
            "target_id": variant_1_id,
            "discount_value": "100.00",
            "start_date": (now - timedelta(days=1)).isoformat(),
            "end_date": (now + timedelta(days=10)).isoformat(),
            "status": "active",
        },
        headers=merchant_a_headers,
    )
    promo_a_id = p_resp.json()["id"]

    # 2. Merchant B staff attempts to access Tenant A's coupon -> 404
    resp_cross_coupon = await client.get(f"/api/v1/merchant/pricing/coupons/{coupon_a_id}", headers=merchant_b_headers)
    assert resp_cross_coupon.status_code == 404

    # 3. Merchant B staff attempts to access Tenant A's promotion -> 404
    resp_cross_promo = await client.get(f"/api/v1/merchant/pricing/promotions/{promo_a_id}", headers=merchant_b_headers)
    assert resp_cross_promo.status_code == 404

    # 4. Merchant B staff attempts to modify Tenant A's coupon -> 404
    resp_cross_patch = await client.patch(
        f"/api/v1/merchant/pricing/coupons/{coupon_a_id}",
        json={"discount_value": "50.00"},
        headers=merchant_b_headers,
    )
    assert resp_cross_patch.status_code == 404

    # 5. Customer browsing Tenant B store context cannot redeem TENANTAONLY coupon
    store_b_id = str(data["store_b_id"])
    tenant_b_id = str(data["tenant_b_id"])

    # Create dummy variant for Tenant B so they can add to cart
    cat_b = (await client.post("/api/v1/merchant/catalog/categories", json={"name": "Textiles", "slug": "textiles-b"}, headers=merchant_b_headers)).json()
    prod_b = (await client.post("/api/v1/merchant/catalog/products", json={"name": "Silk Saree", "slug": "silk-saree-b", "category_id": cat_b["id"], "is_published": True, "status": "active"}, headers=merchant_b_headers)).json()
    var_b = (await client.post(f"/api/v1/merchant/catalog/products/{prod_b['id']}/variants", json={"name": "Red Saree", "sku": "SAREE-RED-01", "mrp": "3000.00", "base_price": "2500.00", "status": "active"}, headers=merchant_b_headers)).json()
    var_b_id = var_b["id"]

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO stock_balances (id, tenant_id, store_id, variant_id, on_hand_qty, reserved_qty, in_transit_qty, available_qty, reorder_threshold, low_stock_alert, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :tid, :sid, :vid, 10, 0, 0, 10, 5, false, now(), now());"
            ),
            {"tid": tenant_b_id, "sid": store_b_id, "vid": var_b_id},
        )

    # Guest user on Tenant B tries to apply TENANTAONLY -> 404 COUPON_NOT_FOUND
    guest_headers = {"X-Session-ID": "guest-tenant-b-session"}
    await client.post(f"/api/v1/cart/items?tenant_id={tenant_b_id}&store_id={store_b_id}", json={"variant_id": var_b_id, "quantity": 1}, headers=guest_headers)
    apply_resp = await client.post(f"/api/v1/cart/coupon?tenant_id={tenant_b_id}&store_id={store_b_id}", json={"code": "TENANTAONLY"}, headers=guest_headers)
    assert apply_resp.status_code == 404
    assert apply_resp.json()["code"] == "COUPON_NOT_FOUND"
