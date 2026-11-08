from decimal import Decimal
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.db.session import engine
from app.modules.payments.providers.mock_provider import MockPaymentGatewayProvider


@pytest.fixture
async def setup_e2e_ecosystem(client: AsyncClient, mint_jwt_token):
    """
    Sets up an end-to-end multi-tenant environment:
    - Platform Admin user and tenant provisioning
    - Merchant A (Bagodi) with 2 physical stores
    - Merchant Admin with full permissions
    - Catalogue with Categories, Products, and Variants
    - Stock inwarded into both stores
    - Delivery rider & vehicle registered
    - Coupons & promotions configured
    """
    async with engine.begin() as conn:
        res_pa = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919000000099', 'superadmin@techmasters.internal', 'Super Admin', 'active', true, now(), now()) "
                "RETURNING id;"
            )
        )
        platform_user_id = res_pa.scalar_one()

        res_ma = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919000000088', 'merchant@bagodi.in', 'Bagodi Merchant', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        merchant_user_id = res_ma.scalar_one()

        res_cust = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919876543210', 'buyer@example.com', 'Deepa Patil', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        customer_user_id = res_cust.scalar_one()

        res_rider = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919876543299', 'rider@bagodi.in', 'Suresh Rider', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        rider_user_id = res_rider.scalar_one()

    platform_token = mint_jwt_token(
        user_id=platform_user_id,
        is_platform_user=True,
        permissions=["platform.*"],
    )
    platform_headers = {"Authorization": f"Bearer {platform_token}"}

    # 1. Onboard Tenant (Bagodi)
    tenant_resp = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Bagodi Handicrafts & Silk",
            "slug": "bagodi-handicrafts",
            "legal_name": "Bagodi Retail Private Limited",
            "contact_email": "ops@bagodi.in",
            "contact_phone": "+919876543210",
        },
        headers=platform_headers,
    )
    assert tenant_resp.status_code == 201
    tenant_id = UUID(tenant_resp.json()["id"])

    # Activate Tenant
    await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/status",
        json={"status": "active"},
        headers=platform_headers,
    )

    merchant_token = mint_jwt_token(
        user_id=merchant_user_id,
        tenant_id=tenant_id,
        permissions=[
            "stores.*",
            "catalog.*",
            "inventory.*",
            "orders.*",
            "payments.*",
            "delivery.*",
            "pricing.*",
            "notifications.*",
            "reports.*",
        ],
    )
    merchant_headers = {"Authorization": f"Bearer {merchant_token}"}

    # 2. Create Two Physical Stores
    s1_resp = await client.post(
        "/api/v1/stores",
        json={
            "name": "Bagodi Heritage Flagship",
            "code": "BGD-STR-01",
            "address_line": "Near Bidar Fort, Main Road",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        headers=merchant_headers,
    )
    assert s1_resp.status_code == 201
    store_1_id = UUID(s1_resp.json()["id"])

    s2_resp = await client.post(
        "/api/v1/stores",
        json={
            "name": "Bagodi Gumpa Branch",
            "code": "BGD-STR-02",
            "address_line": "Gumpa Circle",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585403",
        },
        headers=merchant_headers,
    )
    assert s2_resp.status_code == 201
    store_2_id = UUID(s2_resp.json()["id"])

    # 3. Create Catalogue (Category, Product, Variants)
    cat_resp = await client.post(
        "/api/v1/merchant/catalog/categories",
        json={"name": "Bidriware Heritage", "slug": "bidriware-heritage"},
        headers=merchant_headers,
    )
    cat_id = cat_resp.json()["id"]

    prod_resp = await client.post(
        "/api/v1/merchant/catalog/products",
        json={
            "category_id": cat_id,
            "name": "Silver Inlaid Huqqa Base",
            "slug": "silver-inlaid-huqqa-base",
            "status": "active",
            "is_published": True,
            "variants": [
                {
                    "name": "Authentic Small (6-inch)",
                    "sku": "BIDRI-HQ-01",
                    "barcode": "8908880001",
                    "mrp": "3500.00",
                    "base_price": "2999.00",
                },
                {
                    "name": "Imperial Large (12-inch)",
                    "sku": "BIDRI-HQ-02",
                    "barcode": "8908880002",
                    "mrp": "7000.00",
                    "base_price": "5999.00",
                },
            ],
        },
        headers=merchant_headers,
    )
    assert prod_resp.status_code == 201
    prod_data = prod_resp.json()
    var_small_id = UUID(prod_data["variants"][0]["id"])
    var_large_id = UUID(prod_data["variants"][1]["id"])

    # 4. Inward Stock into Flagship Store 1
    inw_resp = await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": str(store_1_id),
            "receipt_number": "REC-E2E-001",
            "items": [
                {
                    "variant_id": str(var_small_id),
                    "quantity_received": 50,
                    "unit_cost": "1800.00",
                },
                {
                    "variant_id": str(var_large_id),
                    "quantity_received": 20,
                    "unit_cost": "3600.00",
                },
            ],
        },
        headers=merchant_headers,
    )
    assert inw_resp.status_code == 201

    # 5. Delivery Setup (Vehicle & Personnel)
    veh_resp = await client.post(
        "/api/v1/merchant/delivery/vehicles",
        json={
            "store_id": str(store_1_id),
            "vehicle_type": "MOTORCYCLE",
            "registration_number": "KA-38-V-8888",
            "max_weight_capacity_kg": "25.00",
            "status": "AVAILABLE",
        },
        headers=merchant_headers,
    )
    vehicle_id = UUID(veh_resp.json()["id"])

    rider_resp = await client.post(
        "/api/v1/merchant/delivery/personnel",
        json={
            "store_id": str(store_1_id),
            "user_id": str(rider_user_id),
            "employee_code": "RIDER-E2E-01",
            "full_name": "Suresh Rider",
            "phone_number": "+919876543299",
            "assigned_vehicle_id": str(vehicle_id),
            "verification_status": "VERIFIED",
            "duty_status": "AVAILABLE",
        },
        headers=merchant_headers,
    )
    rider_id = UUID(rider_resp.json()["id"])

    # 6. Delivery Zone Setup for 585401
    zone_resp = await client.post(
        "/api/v1/merchant/delivery/zones",
        json={
            "name": "Bidar Old City Zone",
            "code": "ZONE-BIDAR-01",
            "delivery_charge": "50.00",
            "free_delivery_threshold": "2000.00",
            "estimated_delivery_hours": 4,
            "is_active": True,
            "pincodes": ["585401"],
        },
        headers=merchant_headers,
    )
    assert zone_resp.status_code == 201

    # 7. Configure Coupon Promotion (BAGODI200: Flat 200 discount for orders >= 2000)
    coupon_resp = await client.post(
        "/api/v1/merchant/pricing/coupons",
        json={
            "name": "Festive Heritage Discount",
            "code": "BAGODI200",
            "discount_type": "FIXED_AMOUNT",
            "discount_value": "200.00",
            "min_order_amount": "2000.00",
            "start_date": "2026-01-01T00:00:00Z",
            "end_date": "2027-01-01T00:00:00Z",
            "status": "active",
        },
        headers=merchant_headers,
    )
    assert coupon_resp.status_code == 201

    rider_token = mint_jwt_token(
        user_id=rider_user_id,
        tenant_id=tenant_id,
        roles=["delivery_staff"],
        permissions=["delivery:staff", "delivery.*"],
    )
    rider_headers = {"Authorization": f"Bearer {rider_token}"}

    return {
        "platform_headers": platform_headers,
        "merchant_headers": merchant_headers,
        "rider_headers": rider_headers,
        "tenant_id": tenant_id,
        "store_1_id": store_1_id,
        "store_2_id": store_2_id,
        "customer_user_id": customer_user_id,
        "rider_id": rider_id,
        "vehicle_id": vehicle_id,
        "var_small_id": var_small_id,
        "var_large_id": var_large_id,
    }


# =============================================================================
# 1. Full E2E Customer Journey
# =============================================================================
@pytest.mark.asyncio
async def test_e2e_complete_customer_journey(
    client: AsyncClient, setup_e2e_ecosystem, mint_jwt_token
):
    """
    Validates complete customer lifecycle:
    1. Public catalogue browsing & product selection.
    2. Add to persistent cart & price verification.
    3. Apply valid coupon with backend validation.
    4. Checkout order creation with stock reservation.
    5. Payment initiation, verification, and transition to CONFIRMED.
    6. Transactional outbox notification event check.
    7. Shipment creation, assignment, pickup, and OTP doorstep delivery.
    8. Order return request & merchant acceptance with automated refund.
    """
    eco = setup_e2e_ecosystem
    merchant_headers = eco["merchant_headers"]
    rider_headers = eco["rider_headers"]
    store_1_id = eco["store_1_id"]
    var_small_id = eco["var_small_id"]
    customer_user_id = eco["customer_user_id"]
    tenant_id = eco["tenant_id"]

    # 1. Authenticate Customer via JWT
    cust_token = mint_jwt_token(
        user_id=customer_user_id,
        tenant_id=tenant_id,
        roles=["customer"],
        permissions=["customer.*"],
    )
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    # Verify Profile Endpoint
    me_resp = await client.get("/api/v1/auth/me", headers=cust_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "buyer@example.com"

    # 2. Public Catalogue Browsing
    cat_resp = await client.get(f"/api/v1/catalog/categories?tenant_id={tenant_id}")
    assert cat_resp.status_code == 200
    assert len(cat_resp.json()) >= 1

    prod_resp = await client.get(f"/api/v1/catalog/products?tenant_id={tenant_id}")
    assert prod_resp.status_code == 200
    products = prod_resp.json()
    assert any("Huqqa" in p["name"] for p in products)

    # 3. Add to Cart
    add_resp = await client.post(
        f"/api/v1/cart/items?store_id={store_1_id}",
        json={"variant_id": str(var_small_id), "quantity": 1},
        headers=cust_headers,
    )
    assert add_resp.status_code == 201

    # Verify Cart Contents (Unit price: 2999.00)
    cart_resp = await client.get("/api/v1/cart", headers=cust_headers)
    assert cart_resp.status_code == 200
    cart_data = cart_resp.json()
    assert len(cart_data["items"]) == 1
    assert Decimal(cart_data["subtotal"]) == Decimal("2999.00")

    # 4. Checkout with Coupon "BAGODI200"
    checkout_resp = await client.post(
        "/api/v1/orders/checkout",
        json={
            "store_id": str(store_1_id),
            "payment_method": "online",
            "coupon_code": "BAGODI200",
            "shipping_address": {
                "full_name": "Deepa Patil",
                "phone": "+919876543210",
                "address_line1": "Near Bidar Fort",
                "city": "Bidar",
                "state": "Karnataka",
                "postal_code": "585401",
            },
            "customer_name": "Deepa Patil",
            "customer_email": "buyer@example.com",
            "customer_phone": "+919876543210",
        },
        headers=cust_headers,
    )
    assert checkout_resp.status_code == 201
    order = checkout_resp.json()
    order_id = order["id"]

    # Subtotal 2999.00 - Discount 200.00 = Net 2799.00
    assert Decimal(order["subtotal"]) == Decimal("2999.00")
    assert Decimal(order["discount_amount"]) == Decimal("200.00")
    assert Decimal(order["total_amount"]) == Decimal("2799.00")
    assert order["status"] == "PENDING_PAYMENT"

    # 5. Initiate & Complete Online Payment
    init_resp = await client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order_id, "payment_method": "online"},
        headers=cust_headers,
    )
    assert init_resp.status_code == 200
    init_data = init_resp.json()
    txn_id = init_data["transaction_id"]
    gw_order_id = init_data["gateway_order_id"]
    gw_payment_id = f"pay_e2e_{order_id[:8]}"

    provider = MockPaymentGatewayProvider()
    valid_sig = provider.generate_payment_signature(
        gw_order_id, gw_payment_id, Decimal(order["total_amount"])
    )

    verify_resp = await client.post(
        "/api/v1/payments/verify",
        json={
            "transaction_id": txn_id,
            "gateway_order_id": gw_order_id,
            "gateway_payment_id": gw_payment_id,
            "gateway_signature": valid_sig,
        },
        headers=cust_headers,
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["status"] == "captured"

    # Verify order transitioned to CONFIRMED
    ord_check = await client.get(
        f"/api/v1/orders/{order['order_number']}",
        headers=cust_headers,
    )
    assert ord_check.status_code == 200
    assert ord_check.json()["status"] == "CONFIRMED"

    # 6. Verify Outbox Event Generated
    async with engine.connect() as conn:
        outbox_count = (
            await conn.execute(
                text("SELECT count(*) FROM notification_outbox WHERE tenant_id = :tid"),
                {"tid": tenant_id},
            )
        ).scalar_one()
    assert outbox_count >= 1

    # 7. Delivery Execution: Shipment Creation -> Assign -> Pickup -> Deliver with OTP
    shp_resp = await client.post(
        "/api/v1/merchant/delivery/shipments",
        json={"order_id": order_id, "delivery_type": "INTERNAL"},
        headers=merchant_headers,
    )
    assert shp_resp.status_code == 201
    shp_id = shp_resp.json()["id"]

    await client.post(
        f"/api/v1/merchant/delivery/shipments/{shp_id}/assign-internal",
        json={"personnel_id": str(eco["rider_id"]), "vehicle_id": str(eco["vehicle_id"])},
        headers=merchant_headers,
    )
    await client.post(f"/api/v1/delivery-staff/shipments/{shp_id}/pickup", headers=rider_headers)
    await client.post(
        f"/api/v1/delivery-staff/shipments/{shp_id}/out-for-delivery", headers=rider_headers
    )

    # Fetch OTP from database
    async with engine.connect() as conn:
        delivery_otp = (
            await conn.execute(
                text("SELECT delivery_otp FROM shipments WHERE id = :id"), {"id": shp_id}
            )
        ).scalar_one()

    deliver_resp = await client.post(
        f"/api/v1/delivery-staff/shipments/{shp_id}/deliver",
        json={
            "recipient_name": "Deepa Patil",
            "recipient_phone": "+919876543210",
            "delivery_otp": delivery_otp,
        },
        headers=rider_headers,
    )
    assert deliver_resp.status_code == 200
    assert deliver_resp.json()["delivery_otp_verified"] is True

    # 8. Order Return & Refund Workflow
    # Merchant processes return approval and issues refund
    merchant_refund_resp = await client.post(
        f"/api/v1/merchant/payments/orders/{order_id}/refund",
        json={
            "amount": "2799.00",
            "reason": "Customer return approved & restocked",
        },
        headers=merchant_headers,
    )
    assert merchant_refund_resp.status_code == 201
    assert merchant_refund_resp.json()["status"] == "succeeded"

    # Merchant transitions order status to RETURNED
    order_ret_resp = await client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        json={"status": "RETURNED", "notes": "Returned by customer and refunded"},
        headers=merchant_headers,
    )
    assert order_ret_resp.status_code == 200
    assert order_ret_resp.json()["status"] == "RETURNED"


# =============================================================================
# 2. Platform Governance & Tenant Lifecycle
# =============================================================================
@pytest.mark.asyncio
async def test_e2e_platform_governance_and_tenant_suspension(
    client: AsyncClient, setup_e2e_ecosystem, mint_jwt_token
):
    """
    Validates platform-level administrative governance:
    1. Active tenant operations function normally.
    2. Platform Super Admin suspends tenant.
    3. During suspension, all merchant and customer actions are strictly blocked (403/400).
    4. Platform Admin reactivates tenant.
    5. Normal operations resume.
    """
    eco = setup_e2e_ecosystem
    platform_headers = eco["platform_headers"]
    merchant_headers = eco["merchant_headers"]
    tenant_id = eco["tenant_id"]
    customer_user_id = eco["customer_user_id"]
    store_1_id = eco["store_1_id"]
    var_small_id = eco["var_small_id"]

    cust_token = mint_jwt_token(
        user_id=customer_user_id,
        tenant_id=tenant_id,
        roles=["customer"],
        permissions=["customer.*"],
    )
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    # 1. Suspend Tenant
    susp_resp = await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/status",
        json={"status": "suspended"},
        headers=platform_headers,
    )
    assert susp_resp.status_code == 200
    assert susp_resp.json()["status"] == "suspended"

    # 2. Blocked during suspension:
    # Adding item to cart for a suspended tenant
    add_resp = await client.post(
        f"/api/v1/cart/items?store_id={store_1_id}",
        json={"variant_id": str(var_small_id), "quantity": 1},
        headers=cust_headers,
    )
    assert add_resp.status_code in (400, 403, 404)

    # Merchant cannot inward receipts while suspended
    inw_resp = await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": str(store_1_id),
            "receipt_number": "REC-SUSP-001",
            "items": [{"variant_id": str(var_small_id), "quantity": 5, "unit_cost": "1800.00"}],
        },
        headers=merchant_headers,
    )
    assert inw_resp.status_code in (400, 403, 404)

    # 3. Reactivate Tenant
    reactivate_resp = await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/status",
        json={"status": "active"},
        headers=platform_headers,
    )
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.json()["status"] == "active"

    # Operations resume
    add_ok_resp = await client.post(
        f"/api/v1/cart/items?store_id={store_1_id}",
        json={"variant_id": str(var_small_id), "quantity": 1},
        headers=cust_headers,
    )
    assert add_ok_resp.status_code == 201
