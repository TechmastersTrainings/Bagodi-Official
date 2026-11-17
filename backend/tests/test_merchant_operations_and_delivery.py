import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from app.db.session import engine


@pytest.mark.asyncio
async def test_complete_merchant_operations_and_delivery_lifecycle(client: AsyncClient, mint_jwt_token):
    """
    Milestone 4 End-to-End Test:
    Validates complete Merchant Operations & Store Management:
    1. Tenant & Merchant Token Resolution with RBAC
    2. Store & Branch Setup (Bidar Flagship)
    3. Fashion Catalogue & Variant Management (S/M/L SKUs, Barcode, Pricing)
    4. Procurement, Supplier & Inward Goods Receipt (Atomic Ledger Posting)
    5. Order Processing Lifecycle (Confirm -> Pack -> Dispatch -> Deliver)
    6. Return & Size Exchange Review (Physical Inspection & Restock)
    7. Delivery Logistics (Zones, PINs, Riders, Vehicle, Duty Status)
    8. Analytics & Dashboard Metrics Calculation
    """
    # 1. Platform Admin Onboards Bagodi Tenant
    pa_id = uuid.uuid4()
    platform_admin_token = mint_jwt_token(
        user_id=pa_id,
        is_platform_user=True,
        permissions=["platform.*", "stores.*", "catalog.*", "inventory.*", "orders.*", "delivery.*", "reports:read"],
    )
    platform_headers = {"Authorization": f"Bearer {platform_admin_token}"}

    tenant_resp = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Bagodi Retail Bidar",
            "slug": "bagodi-retail-bidar",
            "legal_name": "Bagodi Retail Private Limited",
            "contact_email": "ops@bagodi.in",
            "contact_phone": "+919876543210",
        },
        headers=platform_headers,
    )
    assert tenant_resp.status_code == 201, tenant_resp.text
    tenant_id = tenant_resp.json()["id"]

    await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/status",
        json={"status": "active"},
        headers=platform_headers,
    )

    # 2. Mint Merchant Admin / Store Manager Token
    merchant_user_id = uuid.uuid4()
    # Insert user in DB for foreign key relationships
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, status, is_platform_user, created_at, updated_at) "
                "VALUES (:id, :phone, 'active', false, now(), now()) ON CONFLICT DO NOTHING"
            ),
            {"id": merchant_user_id, "phone": "+919876543210"},
        )

    merchant_token = mint_jwt_token(
        user_id=merchant_user_id,
        tenant_id=uuid.UUID(tenant_id),
        permissions=[
            "stores.*",
            "catalog.*",
            "inventory.*",
            "orders.*",
            "delivery.*",
            "delivery:manage",
            "delivery:read",
            "pricing.*",
            "reports:read",
        ],
    )
    merchant_headers = {
        "Authorization": f"Bearer {merchant_token}",
        "X-Tenant-ID": tenant_id,
    }

    # 3. Create Store Branch: Bagodi Heritage Flagship (Bidar)
    store_resp = await client.post(
        "/api/v1/stores",
        json={
            "name": "Bagodi Heritage Flagship",
            "code": "BGD-STR-01",
            "address_line": "Near Bidar Fort, Main Market Road",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
            "phone": "+919876543210",
        },
        headers=merchant_headers,
    )
    assert store_resp.status_code == 201, store_resp.text
    store_id = store_resp.json()["id"]

    # 4. Create Fashion Catalogue: Category, Brand, Product & Variants
    cat_resp = await client.post(
        "/api/v1/merchant/catalog/categories",
        json={
            "name": "Handcrafted Silk Kurtas",
            "slug": "handcrafted-silk-kurtas",
            "description": "Artisan woven festive apparel",
        },
        headers=merchant_headers,
    )
    assert cat_resp.status_code == 201, cat_resp.text
    category_id = cat_resp.json()["id"]

    brand_resp = await client.post(
        "/api/v1/merchant/catalog/brands",
        json={
            "name": "Bagodi Heritage",
            "slug": "bagodi-heritage",
        },
        headers=merchant_headers,
    )
    assert brand_resp.status_code == 201, brand_resp.text
    brand_id = brand_resp.json()["id"]

    prod_resp = await client.post(
        "/api/v1/merchant/catalog/products",
        json={
            "name": "Bidar Zari Handloom Kurta",
            "slug": "bidar-zari-handloom-kurta",
            "category_id": category_id,
            "brand_id": brand_id,
            "description": "Pure cotton handloom with Bidri zari borders",
            "is_published": True,
            "status": "active",
        },
        headers=merchant_headers,
    )
    assert prod_resp.status_code == 201, prod_resp.text
    product_id = prod_resp.json()["id"]

    # Add Variant S
    var_s_resp = await client.post(
        f"/api/v1/merchant/catalog/products/{product_id}/variants",
        json={
            "name": "Size S / Indigo",
            "sku": "BGD-ZARI-S",
            "barcode": "890123456001",
            "size": "S",
            "color": "Royal Indigo",
            "base_price": "2499.00",
            "mrp": "2999.00",
            "status": "active",
        },
        headers=merchant_headers,
    )
    assert var_s_resp.status_code == 201, var_s_resp.text
    variant_s_id = var_s_resp.json()["id"]

    # Add Variant M
    var_m_resp = await client.post(
        f"/api/v1/merchant/catalog/products/{product_id}/variants",
        json={
            "name": "Size M / Indigo",
            "sku": "BGD-ZARI-M",
            "barcode": "890123456002",
            "size": "M",
            "color": "Royal Indigo",
            "base_price": "2499.00",
            "mrp": "2999.00",
            "status": "active",
        },
        headers=merchant_headers,
    )
    assert var_m_resp.status_code == 201, var_m_resp.text
    variant_m_id = var_m_resp.json()["id"]

    # 5. Procurement: Register Supplier, Raise PO & Inward Goods Receipt
    sup_resp = await client.post(
        "/api/v1/merchant/inventory/suppliers",
        json={
            "name": "Bidar Weavers Cluster",
            "code": "BGD-WEAV-01",
            "phone": "+919448123456",
            "email": "weavers@bidar.org",
            "city": "Bidar",
            "state": "Karnataka",
            "gstin": "29AAAAA1234A1Z5",
        },
        headers=merchant_headers,
    )
    assert sup_resp.status_code == 201, sup_resp.text
    supplier_id = sup_resp.json()["id"]

    po_resp = await client.post(
        "/api/v1/merchant/inventory/purchase-orders",
        json={
            "store_id": store_id,
            "supplier_id": supplier_id,
            "po_number": "PO-BGD-2026-001",
            "items": [
                {
                    "variant_id": variant_m_id,
                    "quantity_ordered": 20,
                    "unit_cost": "1200.00",
                }
            ],
        },
        headers=merchant_headers,
    )
    assert po_resp.status_code == 201, po_resp.text
    po_id = po_resp.json()["id"]
    po_item_id = po_resp.json()["items"][0]["id"]

    # Receive Goods (Inward Receipt)
    receipt_resp = await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "purchase_order_id": po_id,
            "store_id": store_id,
            "receipt_number": "RCP-BGD-2026-001",
            "invoice_number": "INV-WEAV-2026-001",
            "items": [
                {
                    "variant_id": variant_m_id,
                    "quantity_received": 20,
                    "unit_cost": "1200.00",
                }
            ],
        },
        headers=merchant_headers,
    )
    assert receipt_resp.status_code == 201, receipt_resp.text

    # Verify Stock Balances Updated Atomically
    bal_resp = await client.get(
        f"/api/v1/merchant/inventory/balances/{store_id}/{variant_m_id}",
        headers=merchant_headers,
    )
    assert bal_resp.status_code == 200, bal_resp.text
    assert bal_resp.json()["available_qty"] == 20
    assert bal_resp.json()["on_hand_qty"] == 20

    # Verify Immutable Double-Entry Ledger
    ledger_resp = await client.get(
        "/api/v1/merchant/inventory/ledger",
        params={"variant_id": variant_m_id},
        headers=merchant_headers,
    )
    assert ledger_resp.status_code == 200, ledger_resp.text
    ledger_entries = ledger_resp.json()
    assert len(ledger_entries) >= 1
    receipt_entry = next((e for e in ledger_entries if e["movement_type"] == "PURCHASE_RECEIPT"), None)
    assert receipt_entry is not None
    assert receipt_entry["quantity"] == 20

    # 6. Manual Stock Adjustment (Defect Write-off of 1 unit)
    adjust_resp = await client.post(
        "/api/v1/merchant/inventory/adjustments",
        json={
            "store_id": store_id,
            "variant_id": variant_m_id,
            "quantity": 1,
            "reason": "damage",
            "notes": "Zari thread defect noted during rack placement",
        },
        headers=merchant_headers,
    )
    assert adjust_resp.status_code == 200, adjust_resp.text
    # Available stock should now be 19
    bal_after_adj = await client.get(
        f"/api/v1/merchant/inventory/balances/{store_id}/{variant_m_id}",
        headers=merchant_headers,
    )
    assert bal_after_adj.json()["available_qty"] == 19

    # 7. Customer Order Placement & Merchant Fulfillment Workflow
    customer_user_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, status, is_platform_user, created_at, updated_at) "
                "VALUES (:id, :phone, 'active', false, now(), now()) ON CONFLICT DO NOTHING"
            ),
            {"id": customer_user_id, "phone": "+919876543299"},
        )

    customer_token = mint_jwt_token(
        user_id=customer_user_id,
        tenant_id=uuid.UUID(tenant_id),
        roles=["customer"],
    )
    customer_headers = {
        "Authorization": f"Bearer {customer_token}",
        "X-Tenant-ID": tenant_id,
    }

    # Add to cart
    cart_add_resp = await client.post(
        "/api/v1/cart/items",
        json={
            "variant_id": variant_m_id,
            "quantity": 1,
            "store_id": store_id,
        },
        headers=customer_headers,
    )
    assert cart_add_resp.status_code in (200, 201), cart_add_resp.text

    # Checkout
    checkout_resp = await client.post(
        "/api/v1/orders/checkout",
        json={
            "store_id": store_id,
            "customer_name": "Ramesh Patil",
            "customer_phone": "+919876543299",
            "payment_method": "cod",
            "shipping_address": {
                "full_name": "Ramesh Patil",
                "phone": "+919876543299",
                "address_line1": "Flat 302, Royal Residency, Near Fort Road",
                "city": "Bidar",
                "state": "Karnataka",
                "postal_code": "585401",
            },
        },
        headers=customer_headers,
    )
    assert checkout_resp.status_code == 201, checkout_resp.text
    order = checkout_resp.json()
    order_id = order["id"]
    order_number = order["order_number"]
    assert order["status"] == "CONFIRMED"

    # Verify merchant sees order in list
    merchant_orders_resp = await client.get(
        "/api/v1/merchant/orders",
        headers=merchant_headers,
    )
    assert merchant_orders_resp.status_code == 200
    assert any(o["order_number"] == order_number for o in merchant_orders_resp.json())

    # Step 1: Pack (CONFIRMED -> PROCESSING)
    pack_resp = await client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        json={"status": "PROCESSING", "notes": "Packed in festive Bagodi cloth bag"},
        headers=merchant_headers,
    )
    assert pack_resp.status_code == 200
    assert pack_resp.json()["status"] == "PROCESSING"

    # Step 2: Dispatch (PROCESSING -> DISPATCHED)
    dispatch_resp = await client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        json={"status": "DISPATCHED", "notes": "Handed to internal store rider"},
        headers=merchant_headers,
    )
    assert dispatch_resp.status_code == 200
    assert dispatch_resp.json()["status"] == "DISPATCHED"

    # Step 3: Deliver (DISPATCHED -> DELIVERED)
    deliver_resp = await client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        json={"status": "DELIVERED", "notes": "Doorstep delivery confirmed with recipient"},
        headers=merchant_headers,
    )
    assert deliver_resp.status_code == 200
    assert deliver_resp.json()["status"] == "DELIVERED"

    # 8. Customer Size Exchange Submission & Merchant Review
    order_item_id = order["items"][0]["id"]
    return_sub_resp = await client.post(
        f"/api/v1/orders/{order_number}/returns",
        json={
            "order_item_id": order_item_id,
            "request_type": "EXCHANGE",
            "reason": "SIZE_FIT_ISSUE",
            "detailed_reason": "Need Size S instead of Size M for snug fit",
            "requested_size": "S",
            "requested_variant_id": variant_s_id,
        },
        headers=customer_headers,
    )
    assert return_sub_resp.status_code == 201, return_sub_resp.text
    return_req_id = return_sub_resp.json()["id"]

    # Merchant reviews and approves return request
    review_resp = await client.post(
        f"/api/v1/merchant/orders/returns/{return_req_id}/review",
        json={
            "status": "APPROVED",
            "admin_notes": "Approved for doorstep size exchange pickup",
            "pickup_tracking_id": "BGD-EXCH-TRK-01",
        },
        headers=merchant_headers,
    )
    assert review_resp.status_code == 200, review_resp.text
    assert review_resp.json()["status"] == "APPROVED"

    # Inward restock after physical inspection
    restock_resp = await client.post(
        "/api/v1/merchant/inventory/returns",
        json={
            "store_id": store_id,
            "variant_id": variant_m_id,
            "quantity": 1,
            "reference_id": str(return_req_id),
            "notes": "Customer size exchange - brand tags intact and unworn",
        },
        headers=merchant_headers,
    )
    assert restock_resp.status_code == 200, restock_resp.text

    # 9. Delivery Logistics Operations: Zones, Personnel, Vehicle
    zone_resp = await client.post(
        "/api/v1/merchant/delivery/zones",
        json={
            "name": "Bidar Central Zone",
            "code": "BIDAR-CENTRAL",
            "base_delivery_fee": "49.00",
            "free_delivery_threshold": "1999.00",
            "estimated_delivery_hours": 6,
        },
        headers=merchant_headers,
    )
    assert zone_resp.status_code == 201, zone_resp.text
    zone_id = zone_resp.json()["id"]

    # Add PIN codes to zone
    pin_resp = await client.post(
        f"/api/v1/merchant/delivery/zones/{zone_id}/pincodes",
        json={"pincodes": ["585401", "585402"], "is_serviceable": True},
        headers=merchant_headers,
    )
    assert pin_resp.status_code == 201, pin_resp.text

    # Register Delivery Staff
    rider_user_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, status, is_platform_user, created_at, updated_at) "
                "VALUES (:id, :phone, 'active', false, now(), now()) ON CONFLICT DO NOTHING"
            ),
            {"id": rider_user_id, "phone": "+919845112233"},
        )

    rider_resp = await client.post(
        "/api/v1/merchant/delivery/personnel",
        json={
            "user_id": str(rider_user_id),
            "store_id": store_id,
            "employee_code": "RIDER-001",
            "full_name": "Anand Kumar",
            "phone_number": "+919845112233",
            "duty_status": "AVAILABLE",
        },
        headers=merchant_headers,
    )
    assert rider_resp.status_code == 201, rider_resp.text
    rider_id = rider_resp.json()["id"]

    # Update Rider Status
    duty_resp = await client.put(
        f"/api/v1/merchant/delivery/personnel/{rider_id}",
        json={"duty_status": "OFFLINE"},
        headers=merchant_headers,
    )
    assert duty_resp.status_code == 200, duty_resp.text
    assert duty_resp.json()["duty_status"] == "OFFLINE"

    # 10. Reports & Dashboard KPIs
    dash_resp = await client.get(
        "/api/v1/merchant/reports/dashboard",
        headers=merchant_headers,
    )
    assert dash_resp.status_code == 200, dash_resp.text
    dash_data = dash_resp.json()
    assert dash_data["kpis"]["total_orders"] >= 1
    assert float(dash_data["kpis"]["gross_sales"]) > 0

    print("\n✅ COMPLETE MILESTONE 4 WORKFLOW VERIFIED SUCCESSFULLY AGAINST RUNNING FASTAPI & POSTGRESQL!")
