import uuid
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.db.session import engine


@pytest.fixture
async def setup_retail_environment(client: AsyncClient, mint_jwt_token):
    platform_admin_token = mint_jwt_token(
        is_platform_user=True,
        permissions=["platform.*"],
    )
    platform_headers = {"Authorization": f"Bearer {platform_admin_token}"}

    # 1. Onboard Tenant A (Bagodi)
    resp_a = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Bagodi Bidar Fashion Store",
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

    # 2. Store for Tenant A
    merchant_a_token = mint_jwt_token(
        tenant_id=tenant_a_id,
        permissions=["stores.*", "catalog.*", "inventory.*", "orders.*"],
    )
    merchant_a_headers = {"Authorization": f"Bearer {merchant_a_token}"}

    resp_store = await client.post(
        "/api/v1/stores",
        json={
            "name": "Bagodi Bidar Flagship",
            "code": "BGD-BDR-01",
            "address_line": "Near Bidar Fort, Main Bazaar Road",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
            "phone": "+919876543210",
        },
        headers=merchant_a_headers,
    )
    store_id = UUID(resp_store.json()["id"])

    # 3. Category & Apparel Product with Variants (Sizes M, L)
    cat_resp = await client.post(
        "/api/v1/merchant/catalog/categories",
        json={"name": "Ethnic Wear", "slug": "ethnic-wear"},
        headers=merchant_a_headers,
    )
    cat_id = cat_resp.json()["id"]

    prod_resp = await client.post(
        "/api/v1/merchant/catalog/products",
        json={
            "category_id": cat_id,
            "name": "Bidar Handcrafted Silk Kurta",
            "slug": "bidar-silk-kurta",
            "description": "Authentic Bidar pure silk festive kurta",
            "is_published": True,
            "status": "active",
            "variants": [
                {
                    "sku": "BGD-KURTA-M",
                    "name": "Size M / Royal Indigo",
                    "size": "M",
                    "color": "Royal Indigo",
                    "base_price": "2499.00",
                    "mrp": "2999.00",
                    "status": "active",
                },
                {
                    "sku": "BGD-KURTA-L",
                    "name": "Size L / Royal Indigo",
                    "size": "L",
                    "color": "Royal Indigo",
                    "base_price": "2499.00",
                    "mrp": "2999.00",
                    "status": "active",
                },
            ],
        },
        headers=merchant_a_headers,
    )
    prod_data = prod_resp.json()
    variant_m_id = UUID(prod_data["variants"][0]["id"])
    variant_l_id = UUID(prod_data["variants"][1]["id"])

    # 4. Stock supplier & PO receipt for inventory
    supp_resp = await client.post(
        "/api/v1/merchant/inventory/suppliers",
        json={
            "name": "Bidar Weavers Association",
            "code": "SUP-WEAVERS-01",
            "contact_person": "Kashinath Rao",
            "phone": "+919876543222",
        },
        headers=merchant_a_headers,
    )
    supp_id = supp_resp.json()["id"]

    po_resp = await client.post(
        "/api/v1/merchant/inventory/purchase-orders",
        json={
            "store_id": str(store_id),
            "supplier_id": supp_id,
            "po_number": "PO-TEST-001",
            "items": [
                {"variant_id": str(variant_m_id), "quantity_ordered": 20, "unit_cost": "1200.00"},
                {"variant_id": str(variant_l_id), "quantity_ordered": 20, "unit_cost": "1200.00"},
            ],
        },
        headers=merchant_a_headers,
    )
    po_id = po_resp.json()["id"]

    await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": str(store_id),
            "purchase_order_id": po_id,
            "receipt_number": "RCP-TEST-001",
            "invoice_number": "INV-TEST-001",
            "items": [
                {"variant_id": str(variant_m_id), "quantity_received": 20, "unit_cost": "1200.00"},
                {"variant_id": str(variant_l_id), "quantity_received": 20, "unit_cost": "1200.00"},
            ],
        },
        headers=merchant_a_headers,
    )

    # 5. Customer setup
    async with engine.begin() as conn:
        res = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919876543210', 'priyanka@bagodi.in', 'Priyanka Patil', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        customer_id = res.scalar_one()

    customer_token = mint_jwt_token(
        user_id=customer_id,
        tenant_id=tenant_a_id,
        roles=["customer"],
    )
    customer_headers = {
        "Authorization": f"Bearer {customer_token}",
        "X-Tenant-ID": str(tenant_a_id),
    }

    return {
        "tenant_id": tenant_a_id,
        "store_id": store_id,
        "merchant_headers": merchant_a_headers,
        "customer_id": customer_id,
        "customer_headers": customer_headers,
        "variant_m_id": variant_m_id,
        "variant_l_id": variant_l_id,
    }


@pytest.mark.asyncio
async def test_customer_address_lifecycle(client: AsyncClient, setup_retail_environment):
    env = setup_retail_environment
    headers = env["customer_headers"]

    # 1. Initially, no saved addresses
    get_resp = await client.get("/api/v1/customer/addresses", headers=headers)
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == 0

    # 2. Add first address (should auto-default to True)
    addr1_payload = {
        "full_name": "Priyanka Patil",
        "phone": "+919876543210",
        "address_line1": "Flat 402, Bidar Residency",
        "address_line2": "Udgir Road",
        "landmark": "Near Guru Nanak Gate",
        "city": "Bidar",
        "state": "Karnataka",
        "postal_code": "585401",
        "address_type": "home",
        "is_default": False,  # First address should automatically be made default
    }
    create_resp1 = await client.post(
        "/api/v1/customer/addresses", json=addr1_payload, headers=headers
    )
    assert create_resp1.status_code == 201
    addr1 = create_resp1.json()
    assert addr1["full_name"] == "Priyanka Patil"
    assert addr1["is_default"] is True  # Auto-promoted
    addr1_id = addr1["id"]

    # 3. Add second address marked as default
    addr2_payload = {
        "full_name": "Priyanka Patil (Office)",
        "phone": "+919876543210",
        "address_line1": "TechMasters Complex, Suite 10",
        "city": "Bidar",
        "state": "Karnataka",
        "postal_code": "585402",
        "address_type": "work",
        "is_default": True,
    }
    create_resp2 = await client.post(
        "/api/v1/customer/addresses", json=addr2_payload, headers=headers
    )
    assert create_resp2.status_code == 201
    addr2 = create_resp2.json()
    assert addr2["is_default"] is True
    addr2_id = addr2["id"]

    # 4. List addresses - addr1 should no longer be default
    list_resp = await client.get("/api/v1/customer/addresses", headers=headers)
    assert list_resp.status_code == 200
    addresses = list_resp.json()
    assert len(addresses) == 2
    # Sorted by is_default DESC
    assert addresses[0]["id"] == addr2_id
    assert addresses[0]["is_default"] is True
    assert addresses[1]["id"] == addr1_id
    assert addresses[1]["is_default"] is False

    # 5. Switch default back to addr1
    def_resp = await client.post(
        f"/api/v1/customer/addresses/{addr1_id}/default", headers=headers
    )
    assert def_resp.status_code == 200
    assert def_resp.json()["is_default"] is True

    # 6. Update addr1 details
    upd_resp = await client.put(
        f"/api/v1/customer/addresses/{addr1_id}",
        json={"landmark": "Opposite Gurudwara Nanak Jhira Sahib"},
        headers=headers,
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["landmark"] == "Opposite Gurudwara Nanak Jhira Sahib"

    # 7. Delete default addr1 -> remaining addr2 should be promoted to default
    del_resp = await client.delete(f"/api/v1/customer/addresses/{addr1_id}", headers=headers)
    assert del_resp.status_code == 200

    list_after_del = await client.get("/api/v1/customer/addresses", headers=headers)
    assert len(list_after_del.json()) == 1
    assert list_after_del.json()[0]["id"] == addr2_id
    assert list_after_del.json()[0]["is_default"] is True


@pytest.mark.asyncio
async def test_order_return_and_exchange_lifecycle(
    client: AsyncClient, setup_retail_environment
):
    env = setup_retail_environment
    headers = env["customer_headers"]
    merchant_headers = env["merchant_headers"]
    variant_m_id = env["variant_m_id"]
    variant_l_id = env["variant_l_id"]
    store_id = env["store_id"]

    # 1. Add apparel item to cart
    add_item_resp = await client.post(
        "/api/v1/cart/items",
        json={"variant_id": str(variant_m_id), "quantity": 1},
        headers=headers,
    )
    assert add_item_resp.status_code in (200, 201)

    # 2. Checkout order
    checkout_payload = {
        "store_id": str(store_id),
        "shipping_address": {
            "full_name": "Sunil Kumar",
            "address_line1": "Fort View Enclave, Bidar",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
            "phone": "+919876543210",
        },
        "customer_name": "Sunil Kumar",
        "customer_phone": "+919876543210",
        "payment_method": "cod",
    }
    checkout_resp = await client.post(
        "/api/v1/orders/checkout", json=checkout_payload, headers=headers
    )
    assert checkout_resp.status_code == 201
    order = checkout_resp.json()
    order_number = order["order_number"]
    order_id = order["id"]
    order_item_id = order["items"][0]["id"]

    # 3. Try to return before delivery -> Should fail (order is PENDING_PAYMENT / CONFIRMED)
    return_payload = {
        "order_item_id": order_item_id,
        "request_type": "EXCHANGE",
        "reason": "SIZE_FIT_ISSUE",
        "detailed_reason": "Size M is slightly tight across the chest, request exchange for Size L",
        "requested_variant_id": str(variant_l_id),
        "requested_size": "L",
    }
    premature_resp = await client.post(
        f"/api/v1/orders/{order_number}/returns", json=return_payload, headers=headers
    )
    assert premature_resp.status_code == 400
    assert premature_resp.json()["code"] == "INVALID_ORDER_STATE"

    # 4. Merchant advances order through fulfillment: CONFIRMED -> PROCESSING -> DISPATCHED -> DELIVERED
    p_resp = await client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        json={"status": "PROCESSING", "notes": "Packing in Bidar store"},
        headers=merchant_headers,
    )
    assert p_resp.status_code == 200

    d_resp = await client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        json={"status": "DISPATCHED", "notes": "Dispatched with local rider"},
        headers=merchant_headers,
    )
    assert d_resp.status_code == 200

    del_resp = await client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        json={"status": "DELIVERED", "notes": "Delivered and cash collected"},
        headers=merchant_headers,
    )
    assert del_resp.status_code == 200

    # 5. Now customer submits exchange request
    exchange_resp = await client.post(
        f"/api/v1/orders/{order_number}/returns", json=return_payload, headers=headers
    )
    if exchange_resp.status_code != 201:
        print("EXCHANGE_RESP ERROR:", exchange_resp.status_code, exchange_resp.text)
    assert exchange_resp.status_code == 201
    return_req = exchange_resp.json()
    assert return_req["request_type"] == "EXCHANGE"
    assert return_req["reason"] == "SIZE_FIT_ISSUE"
    assert return_req["requested_size"] == "L"
    assert return_req["status"] == "REQUESTED"
    return_id = return_req["id"]

    # 6. Customer cannot submit a duplicate return request for the same item
    dup_resp = await client.post(
        f"/api/v1/orders/{order_number}/returns", json=return_payload, headers=headers
    )
    assert dup_resp.status_code == 409
    assert dup_resp.json()["code"] == "RETURN_ALREADY_EXISTS"

    # 7. Customer views order return list
    cust_returns = await client.get(
        f"/api/v1/orders/{order_number}/returns", headers=headers
    )
    assert cust_returns.status_code == 200
    assert len(cust_returns.json()) == 1

    # 8. Merchant reviews and approves return request
    merchant_review_resp = await client.post(
        f"/api/v1/merchant/orders/returns/{return_id}/review",
        json={
            "status": "APPROVED",
            "admin_notes": "Exchange approved. Size L reserved for customer.",
            "pickup_tracking_id": "BGD-RETURN-PKP-001",
        },
        headers=merchant_headers,
    )
    assert merchant_review_resp.status_code == 200
    reviewed = merchant_review_resp.json()
    assert reviewed["status"] == "APPROVED"
    assert reviewed["pickup_tracking_id"] == "BGD-RETURN-PKP-001"
