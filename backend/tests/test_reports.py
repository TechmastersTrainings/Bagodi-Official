from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.db.session import engine
from app.modules.payments.providers.mock_provider import MockPaymentGatewayProvider


@pytest.fixture
async def setup_reporting_ecosystem(client: AsyncClient, mint_jwt_token):
    """
    Provisions a complete multi-tenant, multi-store analytical testing environment:
    - Platform Super Admin
    - Tenant A (Bagodi) with 2 physical stores (Store A1 & Store A2)
    - Catalogue with Categories, Products, and Variants
    - Stock inwarded into both stores
    - Delivery vehicles & internal delivery staff
    - Multiple customers with completed, delivered, and cancelled orders
    - Online payments captured, refunds processed, COD collected
    - Damaged stock ledger entries
    - Tenant B (Second Merchant) with separate store and orders for isolation verification
    """
    # Insert real User records to satisfy foreign key constraints across exports, delivery, and audits
    async with engine.begin() as conn:
        res_pa = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919000000001', 'platform.admin@bagodi.internal', 'Platform Super Admin', 'active', true, now(), now()) "
                "RETURNING id;"
            )
        )
        platform_admin_id = res_pa.scalar_one()

        res_ma = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919000000002', 'merchant.a@bagodi.in', 'Merchant A Admin', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        merchant_a_admin_id = res_ma.scalar_one()

        res_mb = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919000000003', 'merchant.b@secondmerchant.in', 'Merchant B Admin', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        merchant_b_admin_id = res_mb.scalar_one()

    platform_admin_token = mint_jwt_token(
        user_id=platform_admin_id,
        is_platform_user=True,
        permissions=["platform.*"],
    )
    platform_headers = {"Authorization": f"Bearer {platform_admin_token}"}

    # 1. Onboard Tenant A (Bagodi)
    resp_a = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Bagodi Retail Store",
            "slug": "bagodi-retail",
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
            "name": "Second Merchant LLP",
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

    # 3. Create Stores for Tenant A (Store A1 and Store A2)
    merchant_a_token = mint_jwt_token(
        user_id=merchant_a_admin_id,
        tenant_id=tenant_a_id,
        permissions=[
            "stores.*",
            "catalog.*",
            "inventory.*",
            "orders.*",
            "payments.*",
            "delivery.*",
            "notifications.*",
            "reports.*",
        ],
    )
    merchant_a_headers = {"Authorization": f"Bearer {merchant_a_token}"}

    resp_s1 = await client.post(
        "/api/v1/stores",
        json={
            "name": "Bagodi Flagship Store",
            "code": "STORE-01",
            "address_line": "Fort Road, Main Market",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        headers=merchant_a_headers,
    )
    store_a1_id = UUID(resp_s1.json()["id"])

    resp_s2 = await client.post(
        "/api/v1/stores",
        json={
            "name": "Bagodi City Branch",
            "code": "STORE-02",
            "address_line": "Gumpa Road",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585402",
        },
        headers=merchant_a_headers,
    )
    store_a2_id = UUID(resp_s2.json()["id"])

    # Store for Tenant B
    merchant_b_token = mint_jwt_token(
        user_id=merchant_b_admin_id,
        tenant_id=tenant_b_id,
        permissions=[
            "stores.*",
            "catalog.*",
            "inventory.*",
            "orders.*",
            "payments.*",
            "delivery.*",
            "notifications.*",
            "reports.*",
        ],
    )
    merchant_b_headers = {"Authorization": f"Bearer {merchant_b_token}"}

    resp_sb = await client.post(
        "/api/v1/stores",
        json={
            "name": "Second Merchant Store",
            "code": "STORE-B1",
            "address_line": "Market Road",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        headers=merchant_b_headers,
    )
    store_b_id = UUID(resp_sb.json()["id"])

    # 4. Insert Users (Customers & Staff)
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

        res_staff = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919888800001', 'rider1@bagodi.in', 'Anand Kumar', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        staff_user_id = res_staff.scalar_one()

    customer_1_token = mint_jwt_token(
        user_id=customer_1_id,
        tenant_id=tenant_a_id,
        roles=["customer"],
        permissions=["customer.*"],
    )
    customer_1_headers = {"Authorization": f"Bearer {customer_1_token}"}

    customer_2_token = mint_jwt_token(
        user_id=customer_2_id,
        tenant_id=tenant_a_id,
        roles=["customer"],
        permissions=["customer.*"],
    )
    customer_2_headers = {"Authorization": f"Bearer {customer_2_token}"}

    delivery_staff_token = mint_jwt_token(
        user_id=staff_user_id,
        tenant_id=tenant_a_id,
        roles=["delivery_staff"],
        permissions=["delivery:staff", "delivery.*"],
    )
    delivery_staff_headers = {"Authorization": f"Bearer {delivery_staff_token}"}

    # 5. Catalogue: Categories & Products
    cat_1 = (
        await client.post(
            "/api/v1/merchant/catalog/categories",
            json={"name": "Bidri Metal Crafts", "slug": "bidri-metal-crafts"},
            headers=merchant_a_headers,
        )
    ).json()

    cat_2 = (
        await client.post(
            "/api/v1/merchant/catalog/categories",
            json={"name": "Sandalwood Carvings", "slug": "sandalwood-carvings"},
            headers=merchant_a_headers,
        )
    ).json()

    # Product 1 in Cat 1: Bidri Inlaid Vase
    prod_1 = (
        await client.post(
            "/api/v1/merchant/catalog/products",
            json={
                "category_id": cat_1["id"],
                "name": "Bidri Inlaid Vase",
                "slug": "bidri-inlaid-vase",
                "status": "active",
                "is_published": True,
                "variants": [
                    {
                        "name": "Small Inlaid Vase",
                        "sku": "BIDRI-VASE-S",
                        "barcode": "8901110001",
                        "mrp": "1500.00",
                        "base_price": "1200.00",
                    },
                    {
                        "name": "Large Inlaid Vase",
                        "sku": "BIDRI-VASE-L",
                        "barcode": "8901110002",
                        "mrp": "2800.00",
                        "base_price": "2400.00",
                    },
                ],
            },
            headers=merchant_a_headers,
        )
    ).json()
    var_vase_s = UUID(prod_1["variants"][0]["id"])
    var_vase_l = UUID(prod_1["variants"][1]["id"])

    # Product 2 in Cat 2: Sandalwood Jewel Box
    prod_2 = (
        await client.post(
            "/api/v1/merchant/catalog/products",
            json={
                "category_id": cat_2["id"],
                "name": "Sandalwood Jewel Box",
                "slug": "sandalwood-jewel-box",
                "status": "active",
                "is_published": True,
                "variants": [
                    {
                        "name": "Standard Jewel Box",
                        "sku": "SANDAL-BOX-STD",
                        "barcode": "8901110003",
                        "mrp": "1000.00",
                        "base_price": "800.00",
                    }
                ],
            },
            headers=merchant_a_headers,
        )
    ).json()
    var_box = UUID(prod_2["variants"][0]["id"])

    # 6. Inward Stock into Stores
    # Inward into Store A1
    await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": str(store_a1_id),
            "receipt_number": "INW-A1-001",
            "items": [
                {"variant_id": str(var_vase_s), "quantity_received": 100, "unit_cost": "750.00"},
                {"variant_id": str(var_vase_l), "quantity_received": 50, "unit_cost": "1500.00"},
            ],
        },
        headers=merchant_a_headers,
    )
    # Inward into Store A2
    await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": str(store_a2_id),
            "receipt_number": "INW-A2-001",
            "items": [
                {"variant_id": str(var_box), "quantity_received": 40, "unit_cost": "500.00"},
            ],
        },
        headers=merchant_a_headers,
    )

    # 7. Delivery Vehicles & Personnel Setup
    veh_resp = await client.post(
        "/api/v1/merchant/delivery/vehicles",
        json={
            "store_id": str(store_a1_id),
            "vehicle_type": "MOTORCYCLE",
            "registration_number": "KA-38-M-2020",
            "max_weight_capacity_kg": "30.00",
            "status": "AVAILABLE",
        },
        headers=merchant_a_headers,
    )
    vehicle_id = UUID(veh_resp.json()["id"])

    rider_resp = await client.post(
        "/api/v1/merchant/delivery/personnel",
        json={
            "store_id": str(store_a1_id),
            "user_id": str(staff_user_id),
            "employee_code": "RIDER-01",
            "full_name": "Anand Kumar",
            "phone_number": "+919888800001",
            "assigned_vehicle_id": str(vehicle_id),
            "verification_status": "VERIFIED",
            "duty_status": "AVAILABLE",
        },
        headers=merchant_a_headers,
    )
    rider_id = UUID(rider_resp.json()["id"])

    # 8. Record Damaged Stock in Store A1
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO inventory_ledger (id, tenant_id, store_id, variant_id, movement_type, "
                "from_account, to_account, quantity, on_hand_delta, reserved_delta, in_transit_delta, "
                "balance_after_on_hand, balance_after_reserved, balance_after_available, notes, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :tid, :sid, :vid, 'DAMAGE', 'ON_HAND', 'DAMAGE_EXPENSE', 2, -2, 0, 0, 98, 0, 98, 'Damaged in transit inspection', now(), now());"
            ),
            {"tid": tenant_a_id, "sid": store_a1_id, "vid": var_vase_s},
        )
        # Update stock balance on hand to reflect damage write-off
        await conn.execute(
            text(
                "UPDATE stock_balances SET on_hand_qty = on_hand_qty - 2, available_qty = available_qty - 2 "
                "WHERE tenant_id = :tid AND store_id = :sid AND variant_id = :vid;"
            ),
            {"tid": tenant_a_id, "sid": store_a1_id, "vid": var_vase_s},
        )

    return {
        "platform_headers": platform_headers,
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "merchant_a_headers": merchant_a_headers,
        "merchant_b_headers": merchant_b_headers,
        "store_a1_id": store_a1_id,
        "store_a2_id": store_a2_id,
        "store_b_id": store_b_id,
        "customer_1_id": customer_1_id,
        "customer_2_id": customer_2_id,
        "customer_1_headers": customer_1_headers,
        "customer_2_headers": customer_2_headers,
        "delivery_staff_headers": delivery_staff_headers,
        "rider_id": rider_id,
        "vehicle_id": vehicle_id,
        "cat_1_id": UUID(cat_1["id"]),
        "cat_2_id": UUID(cat_2["id"]),
        "prod_1_id": UUID(prod_1["id"]),
        "prod_2_id": UUID(prod_2["id"]),
        "var_vase_s": var_vase_s,
        "var_vase_l": var_vase_l,
        "var_box": var_box,
    }


async def _create_and_pay_order(
    client: AsyncClient,
    cust_headers: dict,
    store_id: UUID,
    variant_id: UUID,
    quantity: int = 1,
    payment_method: str = "online",
) -> dict:
    """Helper to add item to cart, checkout, and capture online payment."""
    cart_add_resp = await client.post(
        f"/api/v1/cart/items?store_id={store_id}",
        json={"variant_id": str(variant_id), "quantity": quantity},
        headers=cust_headers,
    )
    assert cart_add_resp.status_code == 201, f"Cart add failed: {cart_add_resp.text}"

    checkout_resp = await client.post(
        "/api/v1/orders/checkout",
        json={
            "store_id": str(store_id),
            "payment_method": payment_method,
            "shipping_address": {
                "full_name": "Ramesh Kumar",
                "phone": "+919999900001",
                "address_line1": "Fort View",
                "city": "Bidar",
                "state": "Karnataka",
                "postal_code": "585401",
            },
            "customer_name": "Ramesh Kumar",
            "customer_email": "cust1@example.com",
            "customer_phone": "+919999900001",
        },
        headers=cust_headers,
    )
    assert checkout_resp.status_code == 201, f"Checkout failed: {checkout_resp.text}"
    order = checkout_resp.json()
    order_id = order["id"]

    if payment_method == "online":
        init_resp = await client.post(
            "/api/v1/payments/initiate",
            json={"order_id": order_id, "payment_method": "online"},
            headers=cust_headers,
        )
        assert init_resp.status_code == 200, f"Pay init failed: {init_resp.text}"
        init_data = init_resp.json()
        txn_id = init_data["transaction_id"]
        gw_order_id = init_data["gateway_order_id"]
        gw_payment_id = f"pay_mock_{order_id[:8]}"

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
        assert verify_resp.status_code == 200, f"Pay verify failed: {verify_resp.text}"

    return order


# =============================================================================
# 1. Merchant Dashboard KPIs & Time-Series Tests
# =============================================================================
@pytest.mark.asyncio
async def test_merchant_dashboard_kpis_and_time_series(
    client: AsyncClient, setup_reporting_ecosystem
):
    eco = setup_reporting_ecosystem
    merchant_headers = eco["merchant_a_headers"]
    cust1_headers = eco["customer_1_headers"]
    staff_headers = eco["delivery_staff_headers"]
    store_a1_id = eco["store_a1_id"]
    var_vase_s = eco["var_vase_s"]
    rider_id = eco["rider_id"]
    vehicle_id = eco["vehicle_id"]

    # 1. Place, Pay and Deliver Order 1 (2 units of Vase S @ 1200.00 = 2400.00)
    order_1 = await _create_and_pay_order(
        client, cust1_headers, store_a1_id, var_vase_s, quantity=2, payment_method="online"
    )
    order_1_id = order_1["id"]

    # Create shipment, assign, pickup, deliver with OTP
    shp = (
        await client.post(
            "/api/v1/merchant/delivery/shipments",
            json={"order_id": str(order_1_id), "delivery_type": "INTERNAL"},
            headers=merchant_headers,
        )
    ).json()
    shp_id = shp["id"]
    await client.post(
        f"/api/v1/merchant/delivery/shipments/{shp_id}/assign-internal",
        json={"personnel_id": str(rider_id), "vehicle_id": str(vehicle_id)},
        headers=merchant_headers,
    )
    await client.post(f"/api/v1/delivery-staff/shipments/{shp_id}/pickup", headers=staff_headers)
    await client.post(
        f"/api/v1/delivery-staff/shipments/{shp_id}/out-for-delivery", headers=staff_headers
    )

    # Deliver with OTP
    async with engine.connect() as conn:
        otp = (
            await conn.execute(text(f"SELECT delivery_otp FROM shipments WHERE id = '{shp_id}'"))
        ).scalar_one()

    await client.post(
        f"/api/v1/delivery-staff/shipments/{shp_id}/deliver",
        json={
            "recipient_name": "Ramesh Kumar",
            "recipient_phone": "+919999900001",
            "delivery_otp": otp,
        },
        headers=staff_headers,
    )

    # 2. Query Dashboard
    dash_resp = await client.get("/api/v1/merchant/reports/dashboard", headers=merchant_headers)
    assert dash_resp.status_code == 200, f"Dashboard failed: {dash_resp.text}"
    data = dash_resp.json()

    kpis = data["kpis"]
    assert Decimal(kpis["gross_sales"]) == Decimal("2400.00")
    assert Decimal(kpis["net_sales"]) == Decimal("2400.00")
    assert kpis["total_orders"] >= 1
    assert kpis["delivered_orders"] >= 1
    assert Decimal(kpis["aov"]) == Decimal("2400.00")

    # Verify time-series contains data
    assert len(data["time_series"]) >= 1
    today_str = datetime.now(UTC).strftime("%Y-%m-%d")
    matching_points = [p for p in data["time_series"] if p["date"] == today_str]
    assert len(matching_points) == 1
    assert matching_points[0]["orders_count"] >= 1


# =============================================================================
# 2. Sales & Revenue Reports (Daily, Weekly, Monthly)
# =============================================================================
@pytest.mark.asyncio
async def test_sales_revenue_reporting_granularities(
    client: AsyncClient, setup_reporting_ecosystem
):
    eco = setup_reporting_ecosystem
    merchant_headers = eco["merchant_a_headers"]
    cust1_headers = eco["customer_1_headers"]
    store_a1_id = eco["store_a1_id"]
    var_vase_s = eco["var_vase_s"]

    # Place and pay order
    await _create_and_pay_order(
        client, cust1_headers, store_a1_id, var_vase_s, quantity=1, payment_method="online"
    )

    # 1. Daily Report
    daily_resp = await client.get(
        "/api/v1/merchant/reports/sales?granularity=daily", headers=merchant_headers
    )
    assert daily_resp.status_code == 200
    daily_data = daily_resp.json()
    assert daily_data["granularity"] == "daily"
    assert len(daily_data["records"]) >= 1
    assert Decimal(daily_data["records"][0]["net_sales"]) > Decimal("0.00")

    # 2. Weekly Report
    weekly_resp = await client.get(
        "/api/v1/merchant/reports/sales?granularity=weekly", headers=merchant_headers
    )
    assert weekly_resp.status_code == 200
    assert weekly_resp.json()["granularity"] == "weekly"

    # 3. Monthly Report
    monthly_resp = await client.get(
        "/api/v1/merchant/reports/sales?granularity=monthly", headers=merchant_headers
    )
    assert monthly_resp.status_code == 200
    assert monthly_resp.json()["granularity"] == "monthly"


# =============================================================================
# 3. Product & Category Performance Analytics
# =============================================================================
@pytest.mark.asyncio
async def test_product_and_category_performance_analytics(
    client: AsyncClient, setup_reporting_ecosystem
):
    eco = setup_reporting_ecosystem
    merchant_headers = eco["merchant_a_headers"]
    cust1_headers = eco["customer_1_headers"]
    store_a1_id = eco["store_a1_id"]
    var_vase_s = eco["var_vase_s"]

    # Place order
    await _create_and_pay_order(
        client, cust1_headers, store_a1_id, var_vase_s, quantity=3, payment_method="online"
    )

    # 1. Product Performance
    prod_resp = await client.get("/api/v1/merchant/reports/products", headers=merchant_headers)
    assert prod_resp.status_code == 200
    pdata = prod_resp.json()
    assert pdata["total_units_sold"] >= 3
    vase_record = next((r for r in pdata["records"] if "Vase" in r["product_name"]), None)
    assert vase_record is not None
    assert vase_record["units_sold"] >= 3
    assert vase_record["current_stock_on_hand"] >= 0

    # 2. Category Performance
    cat_resp = await client.get("/api/v1/merchant/reports/categories", headers=merchant_headers)
    assert cat_resp.status_code == 200
    cdata = cat_resp.json()
    assert len(cdata["records"]) >= 1
    crafts_cat = next((r for r in cdata["records"] if "Bidri" in r["category_name"]), None)
    assert crafts_cat is not None
    assert crafts_cat["units_sold"] >= 3
    assert Decimal(crafts_cat["revenue_share_percentage"]) > Decimal("0.00")


# =============================================================================
# 4. Inventory Valuation, Damaged Stock & Movement Reports
# =============================================================================
@pytest.mark.asyncio
async def test_inventory_stock_valuation_and_movement_reports(
    client: AsyncClient, setup_reporting_ecosystem
):
    eco = setup_reporting_ecosystem
    merchant_headers = eco["merchant_a_headers"]

    inv_resp = await client.get("/api/v1/merchant/reports/inventory", headers=merchant_headers)
    assert inv_resp.status_code == 200
    inv = inv_resp.json()

    # Total units & valuations
    assert inv["total_on_hand_units"] > 0
    assert Decimal(inv["total_valuation_at_cost"]) > Decimal("0.00")
    assert Decimal(inv["total_valuation_at_retail"]) > Decimal("0.00")

    # Verify damaged records include the 2 damaged units from fixture
    assert len(inv["damaged_records"]) >= 1
    dmg = inv["damaged_records"][0]
    assert dmg["movement_type"] == "DAMAGE"
    assert dmg["quantity"] == 2
    assert Decimal(dmg["total_cost_impact"]) > Decimal("0.00")

    # Verify ledger movements summary includes DAMAGE movement
    dmg_mov = next((m for m in inv["ledger_movements"] if m["movement_type"] == "DAMAGE"), None)
    assert dmg_mov is not None
    assert dmg_mov["units_moved"] == 2


# =============================================================================
# 5. Order Analytics & Lead Time Calculations
# =============================================================================
@pytest.mark.asyncio
async def test_order_lifecycle_cancellations_and_fulfillment_lead_time(
    client: AsyncClient, setup_reporting_ecosystem
):
    eco = setup_reporting_ecosystem
    merchant_headers = eco["merchant_a_headers"]
    cust2_headers = eco["customer_2_headers"]
    store_a1_id = eco["store_a1_id"]
    var_vase_s = eco["var_vase_s"]

    # 1. Place and Cancel Order
    cancelled_order = await _create_and_pay_order(
        client, cust2_headers, store_a1_id, var_vase_s, quantity=1, payment_method="online"
    )
    cancel_resp = await client.patch(
        f"/api/v1/merchant/orders/{cancelled_order['id']}/status",
        json={"status": "CANCELLED", "notes": "Customer requested order cancellation"},
        headers=merchant_headers,
    )
    assert cancel_resp.status_code == 200

    # 2. Query Order Analytics
    orders_resp = await client.get("/api/v1/merchant/reports/orders", headers=merchant_headers)
    assert orders_resp.status_code == 200
    odata = orders_resp.json()
    assert odata["total_orders"] >= 1
    assert odata["cancellation_count"] >= 1
    assert Decimal(odata["cancellation_rate"]) > Decimal("0.00")

    # Verify status breakdown contains CANCELLED
    cancel_status = next((s for s in odata["status_breakdown"] if s["status"] == "CANCELLED"), None)
    assert cancel_status is not None
    assert cancel_status["count"] >= 1


# =============================================================================
# 6. Payment, Refund & COD Reconciliation Reports
# =============================================================================
@pytest.mark.asyncio
async def test_payment_cod_settlement_and_refund_reconciliation(
    client: AsyncClient, setup_reporting_ecosystem
):
    eco = setup_reporting_ecosystem
    merchant_headers = eco["merchant_a_headers"]
    cust1_headers = eco["customer_1_headers"]
    staff_headers = eco["delivery_staff_headers"]
    store_a1_id = eco["store_a1_id"]
    var_vase_s = eco["var_vase_s"]
    rider_id = eco["rider_id"]

    # 1. Place COD order, deliver it and collect COD
    cod_order = await _create_and_pay_order(
        client, cust1_headers, store_a1_id, var_vase_s, quantity=1, payment_method="cod"
    )
    cod_shp = (
        await client.post(
            "/api/v1/merchant/delivery/shipments",
            json={"order_id": str(cod_order["id"]), "delivery_type": "INTERNAL"},
            headers=merchant_headers,
        )
    ).json()
    shp_id = cod_shp["id"]
    await client.post(
        f"/api/v1/merchant/delivery/shipments/{shp_id}/assign-internal",
        json={"personnel_id": str(rider_id)},
        headers=merchant_headers,
    )
    await client.post(f"/api/v1/delivery-staff/shipments/{shp_id}/pickup", headers=staff_headers)
    await client.post(
        f"/api/v1/delivery-staff/shipments/{shp_id}/out-for-delivery", headers=staff_headers
    )

    async with engine.connect() as conn:
        otp = (
            await conn.execute(text(f"SELECT delivery_otp FROM shipments WHERE id = '{shp_id}'"))
        ).scalar_one()

    await client.post(
        f"/api/v1/delivery-staff/shipments/{shp_id}/deliver",
        json={
            "recipient_name": "Ramesh Kumar",
            "recipient_phone": "+919999900001",
            "delivery_otp": otp,
        },
        headers=staff_headers,
    )

    # 2. Query Payment Reports
    pay_resp = await client.get("/api/v1/merchant/reports/payments", headers=merchant_headers)
    assert pay_resp.status_code == 200
    pdata = pay_resp.json()

    assert Decimal(pdata["net_realized_revenue"]) >= Decimal("0.00")
    cod_sum = pdata["cod_settlement"]
    assert cod_sum["total_cod_orders"] >= 1
    assert Decimal(cod_sum["total_cod_collected"]) > Decimal("0.00")
    assert Decimal(cod_sum["pending_deposit_amount"]) > Decimal("0.00")


# =============================================================================
# 7. Delivery & Rider Performance Analytics
# =============================================================================
@pytest.mark.asyncio
async def test_delivery_and_rider_courier_performance_analytics(
    client: AsyncClient, setup_reporting_ecosystem
):
    eco = setup_reporting_ecosystem
    merchant_headers = eco["merchant_a_headers"]
    cust1_headers = eco["customer_1_headers"]
    staff_headers = eco["delivery_staff_headers"]
    store_a1_id = eco["store_a1_id"]
    var_vase_s = eco["var_vase_s"]
    rider_id = eco["rider_id"]
    vehicle_id = eco["vehicle_id"]

    # Place order, create shipment, assign and deliver
    order = await _create_and_pay_order(
        client, cust1_headers, store_a1_id, var_vase_s, quantity=1, payment_method="online"
    )
    shp = (
        await client.post(
            "/api/v1/merchant/delivery/shipments",
            json={"order_id": str(order["id"]), "delivery_type": "INTERNAL"},
            headers=merchant_headers,
        )
    ).json()
    shp_id = shp["id"]
    await client.post(
        f"/api/v1/merchant/delivery/shipments/{shp_id}/assign-internal",
        json={"personnel_id": str(rider_id), "vehicle_id": str(vehicle_id)},
        headers=merchant_headers,
    )
    await client.post(f"/api/v1/delivery-staff/shipments/{shp_id}/pickup", headers=staff_headers)
    await client.post(
        f"/api/v1/delivery-staff/shipments/{shp_id}/out-for-delivery", headers=staff_headers
    )

    async with engine.connect() as conn:
        otp = (
            await conn.execute(text(f"SELECT delivery_otp FROM shipments WHERE id = '{shp_id}'"))
        ).scalar_one()

    await client.post(
        f"/api/v1/delivery-staff/shipments/{shp_id}/deliver",
        json={
            "recipient_name": "Ramesh Kumar",
            "recipient_phone": "+919999900001",
            "delivery_otp": otp,
        },
        headers=staff_headers,
    )

    deliv_resp = await client.get("/api/v1/merchant/reports/delivery", headers=merchant_headers)
    assert deliv_resp.status_code == 200
    ddata = deliv_resp.json()

    assert ddata["total_shipments"] >= 1
    assert len(ddata["rider_performance"]) >= 1

    rider = ddata["rider_performance"][0]
    assert rider["employee_code"] == "RIDER-01"
    assert rider["rider_name"] == "Anand Kumar"
    assert rider["total_assigned"] >= 1


# =============================================================================
# 8. Customer Analytics & LTV
# =============================================================================
@pytest.mark.asyncio
async def test_customer_analytics_frequency_and_lifetime_value(
    client: AsyncClient, setup_reporting_ecosystem
):
    eco = setup_reporting_ecosystem
    merchant_headers = eco["merchant_a_headers"]
    cust1_headers = eco["customer_1_headers"]
    store_a1_id = eco["store_a1_id"]
    var_vase_s = eco["var_vase_s"]

    # Place and pay order for Customer 1
    await _create_and_pay_order(
        client, cust1_headers, store_a1_id, var_vase_s, quantity=1, payment_method="online"
    )

    cust_resp = await client.get("/api/v1/merchant/reports/customers", headers=merchant_headers)
    assert cust_resp.status_code == 200
    cdata = cust_resp.json()

    assert cdata["total_unique_customers"] >= 1
    assert len(cdata["top_customers"]) >= 1

    top = cdata["top_customers"][0]
    assert top["customer_name"] == "Ramesh Kumar"
    assert top["total_orders"] >= 1
    assert Decimal(top["total_spend"]) > Decimal("0.00")
    assert Decimal(top["average_order_value"]) > Decimal("0.00")


# =============================================================================
# 9. Multi-Store Branch-Level Comparison
# =============================================================================
@pytest.mark.asyncio
async def test_multi_store_branch_level_comparison(client: AsyncClient, setup_reporting_ecosystem):
    eco = setup_reporting_ecosystem
    merchant_headers = eco["merchant_a_headers"]
    cust1_headers = eco["customer_1_headers"]
    store_a2_id = eco["store_a2_id"]
    var_box = eco["var_box"]

    # Place order in Store A2 (Branch)
    await _create_and_pay_order(
        client, cust1_headers, store_a2_id, var_box, quantity=2, payment_method="online"
    )

    stores_resp = await client.get("/api/v1/merchant/reports/stores", headers=merchant_headers)
    assert stores_resp.status_code == 200
    sdata = stores_resp.json()

    assert len(sdata["stores"]) == 2
    store_codes = {s["store_code"] for s in sdata["stores"]}
    assert "STORE-01" in store_codes
    assert "STORE-02" in store_codes

    # Store 2 has stock valuation and orders
    s2 = next(s for s in sdata["stores"] if s["store_code"] == "STORE-02")
    assert s2["total_orders"] >= 1
    assert Decimal(s2["net_sales"]) == Decimal("1600.00")
    assert s2["stock_units_on_hand"] > 0


# =============================================================================
# 10. Platform Super Admin Macro Analytics
# =============================================================================
@pytest.mark.asyncio
async def test_platform_super_admin_cross_tenant_overview(
    client: AsyncClient, setup_reporting_ecosystem
):
    eco = setup_reporting_ecosystem
    platform_headers = eco["platform_headers"]
    merchant_headers = eco["merchant_a_headers"]
    cust1_headers = eco["customer_1_headers"]
    store_a1_id = eco["store_a1_id"]
    var_vase_s = eco["var_vase_s"]

    # Place and pay order in Tenant A so platform GMV is recorded
    await _create_and_pay_order(
        client, cust1_headers, store_a1_id, var_vase_s, quantity=1, payment_method="online"
    )

    # 1. Platform Admin can fetch platform overview
    ov_resp = await client.get("/api/v1/platform/reports/overview", headers=platform_headers)
    assert ov_resp.status_code == 200
    odata = ov_resp.json()

    assert odata["total_active_tenants"] >= 2
    assert odata["total_physical_stores"] >= 3
    assert Decimal(odata["platform_gmv"]) > Decimal("0.00")
    assert len(odata["tenants"]) >= 2

    # 2. Security Boundary: Merchant Admin cannot access Platform Overview
    forbidden_resp = await client.get("/api/v1/platform/reports/overview", headers=merchant_headers)
    assert forbidden_resp.status_code == 403


# =============================================================================
# 11. CSV Export Format, Headers & Audit Logging
# =============================================================================
@pytest.mark.asyncio
async def test_csv_export_format_content_and_audit_logging(
    client: AsyncClient, setup_reporting_ecosystem
):
    eco = setup_reporting_ecosystem
    merchant_headers = eco["merchant_a_headers"]
    cust1_headers = eco["customer_1_headers"]
    store_a1_id = eco["store_a1_id"]
    var_vase_s = eco["var_vase_s"]

    # Place and pay order so sales report has interval data
    await _create_and_pay_order(
        client, cust1_headers, store_a1_id, var_vase_s, quantity=1, payment_method="online"
    )

    # 1. Export Sales as CSV
    csv_resp = await client.get(
        "/api/v1/merchant/reports/sales?format=csv", headers=merchant_headers
    )
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in csv_resp.headers["content-disposition"]

    # Check for UTF-8 BOM prefix (\ufeff)
    content = csv_resp.content.decode("utf-8")
    assert content.startswith("\ufeff")
    assert "interval_date,orders_count,gross_sales" in content

    # 2. Export Inventory as CSV
    csv_inv = await client.get(
        "/api/v1/merchant/reports/inventory?format=csv", headers=merchant_headers
    )
    assert csv_inv.status_code == 200
    inv_content = csv_inv.content.decode("utf-8")
    assert "variant_id,sku,product_name" in inv_content

    # 3. Check Audit Log History
    hist_resp = await client.get(
        "/api/v1/merchant/reports/exports/history", headers=merchant_headers
    )
    assert hist_resp.status_code == 200
    history = hist_resp.json()
    assert len(history) >= 2
    types = [h["report_type"] for h in history]
    assert "SALES" in types
    assert "INVENTORY" in types


# =============================================================================
# 12. Cross-Tenant Reporting Isolation & RBAC Boundaries
# =============================================================================
@pytest.mark.asyncio
async def test_cross_tenant_reporting_isolation_and_rbac_boundaries(
    client: AsyncClient, setup_reporting_ecosystem
):
    eco = setup_reporting_ecosystem
    merchant_b_headers = eco["merchant_b_headers"]
    cust1_headers = eco["customer_1_headers"]

    # 1. Merchant B queries dashboard -> Must see 0 sales (Tenant A data is completely isolated)
    dash_b = await client.get("/api/v1/merchant/reports/dashboard", headers=merchant_b_headers)
    assert dash_b.status_code == 200
    b_kpis = dash_b.json()["kpis"]
    assert Decimal(b_kpis["gross_sales"]) == Decimal("0.00")
    assert Decimal(b_kpis["net_sales"]) == Decimal("0.00")
    assert b_kpis["total_orders"] == 0

    # 2. Customer user attempting to access merchant reports is blocked
    cust_forbidden = await client.get("/api/v1/merchant/reports/dashboard", headers=cust1_headers)
    assert cust_forbidden.status_code == 403
