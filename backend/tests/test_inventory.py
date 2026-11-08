from uuid import UUID

import pytest
from httpx import AsyncClient


@pytest.fixture
async def setup_inventory_context(client: AsyncClient, mint_jwt_token):
    """Helper fixture to set up Tenant A (Bagodi) with 2 stores (Flagship & Branch),

    Tenant B (Second Merchant) with 1 store, along with categories, products, and variants.
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
            "name": "Bagodi Enterprises Bidar",
            "slug": "bagodi-bidar",
            "legal_name": "Bagodi Retail Private Limited",
            "contact_email": "operations@bagodi.in",
            "contact_phone": "+919876543210",
        },
        headers=platform_headers,
    )
    assert resp_a.status_code == 201
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
    assert resp_b.status_code == 201
    tenant_b_id = UUID(resp_b.json()["id"])
    await client.patch(
        f"/api/v1/platform/tenants/{tenant_b_id}/status",
        json={"status": "active"},
        headers=platform_headers,
    )

    # 3. Mint JWT tokens with full permissions
    merchant_a_token = mint_jwt_token(
        tenant_id=tenant_a_id,
        permissions=["stores.*", "catalog.*", "inventory.*"],
    )
    headers_a = {"Authorization": f"Bearer {merchant_a_token}"}

    merchant_b_token = mint_jwt_token(
        tenant_id=tenant_b_id,
        permissions=["stores.*", "catalog.*", "inventory.*"],
    )
    headers_b = {"Authorization": f"Bearer {merchant_b_token}"}

    # 4. Create Stores for Tenant A: Store 1 (Flagship Bidar) and Store 2 (Branch)
    resp_s1 = await client.post(
        "/api/v1/stores",
        json={
            "name": "Bagodi Flagship Store Bidar",
            "code": "STORE01",
            "address_line": "Main Bazaar, Old City",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        headers=headers_a,
    )
    assert resp_s1.status_code == 201
    store_a1_id = UUID(resp_s1.json()["id"])

    resp_s2 = await client.post(
        "/api/v1/stores",
        json={
            "name": "Bagodi Warehouse Bidar",
            "code": "WH01",
            "address_line": "Industrial Area, Naubad",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585402",
        },
        headers=headers_a,
    )
    assert resp_s2.status_code == 201
    store_a2_id = UUID(resp_s2.json()["id"])

    # 5. Create Store for Tenant B
    resp_sb = await client.post(
        "/api/v1/stores",
        json={
            "name": "Second Merchant Main Store",
            "code": "STORE01",
            "address_line": "Station Road",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        headers=headers_b,
    )
    assert resp_sb.status_code == 201
    store_b1_id = UUID(resp_sb.json()["id"])

    # 6. Create Category and Product with Variants for Tenant A
    cat_a = (await client.post(
        "/api/v1/merchant/catalog/categories",
        json={"name": "Bidriware", "slug": "bidriware"},
        headers=headers_a,
    )).json()

    prod_a = (await client.post(
        "/api/v1/merchant/catalog/products",
        json={
            "category_id": cat_a["id"],
            "name": "Handcrafted Bidri Vase",
            "slug": "handcrafted-bidri-vase",
            "status": "active",
            "is_published": True,
            "variants": [
                {
                    "sku": "VASE-6INCH",
                    "barcode": "890111122201",
                    "name": "6 Inch Vase",
                    "mrp": "2500.00",
                    "base_price": "2100.00",
                },
                {
                    "sku": "VASE-8INCH",
                    "barcode": "890111122202",
                    "name": "8 Inch Vase",
                    "mrp": "3500.00",
                    "base_price": "2900.00",
                },
            ],
        },
        headers=headers_a,
    )).json()
    variant_a1_id = UUID(prod_a["variants"][0]["id"])
    variant_a2_id = UUID(prod_a["variants"][1]["id"])

    # 7. Create Category and Product for Tenant B
    cat_b = (await client.post(
        "/api/v1/merchant/catalog/categories",
        json={"name": "Textiles", "slug": "textiles"},
        headers=headers_b,
    )).json()
    prod_b = (await client.post(
        "/api/v1/merchant/catalog/products",
        json={
            "category_id": cat_b["id"],
            "name": "Cotton Kurta",
            "slug": "cotton-kurta",
            "status": "active",
            "is_published": True,
            "variants": [
                {
                    "sku": "KURTA-M",
                    "barcode": "890222233301",
                    "name": "Medium Size",
                    "mrp": "1200.00",
                    "base_price": "999.00",
                }
            ],
        },
        headers=headers_b,
    )).json()
    variant_b1_id = UUID(prod_b["variants"][0]["id"])

    return {
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "headers_a": headers_a,
        "headers_b": headers_b,
        "store_a1_id": store_a1_id,
        "store_a2_id": store_a2_id,
        "store_b1_id": store_b1_id,
        "variant_a1_id": variant_a1_id,
        "variant_a2_id": variant_a2_id,
        "variant_b1_id": variant_b1_id,
    }


@pytest.mark.asyncio
async def test_purchase_order_and_inward_receipt_workflow(client: AsyncClient, setup_inventory_context):
    data = setup_inventory_context
    headers_a = data["headers_a"]
    store_a1_id = str(data["store_a1_id"])
    variant_a1_id = str(data["variant_a1_id"])

    # 1. Register a Supplier
    supplier_resp = await client.post(
        "/api/v1/merchant/inventory/suppliers",
        json={
            "name": "Bidar Master Artisans Guild",
            "code": "SUP-ARTISAN-01",
            "contact_person": "Kashinath Rao",
            "phone": "+918482001122",
            "email": "guild@bidarart.org",
        },
        headers=headers_a,
    )
    assert supplier_resp.status_code == 201
    supplier_id = supplier_resp.json()["id"]

    # 2. Check initial stock balance -> 0 on-hand, 0 available
    bal_initial = await client.get(
        f"/api/v1/merchant/inventory/balances/{store_a1_id}/{variant_a1_id}",
        headers=headers_a,
    )
    assert bal_initial.status_code == 200
    assert bal_initial.json()["on_hand_qty"] == 0
    assert bal_initial.json()["available_qty"] == 0

    # 3. Create Purchase Order for 50 units @ Rs 1500.00 each
    po_resp = await client.post(
        "/api/v1/merchant/inventory/purchase-orders",
        json={
            "store_id": store_a1_id,
            "supplier_id": supplier_id,
            "po_number": "PO-2026-001",
            "items": [
                {
                    "variant_id": variant_a1_id,
                    "quantity_ordered": 50,
                    "unit_cost": "1500.00",
                }
            ],
            "notes": "Initial procurement order",
        },
        headers=headers_a,
    )
    assert po_resp.status_code == 201
    po = po_resp.json()
    assert po["status"] == "ordered"
    assert po["total_amount"] == "75000.00"
    po_id = po["id"]

    # 4. VERIFY: PO creation does NOT alter inventory balances!
    bal_after_po = (await client.get(
        f"/api/v1/merchant/inventory/balances/{store_a1_id}/{variant_a1_id}",
        headers=headers_a,
    )).json()
    assert bal_after_po["on_hand_qty"] == 0
    assert bal_after_po["available_qty"] == 0

    # 5. Receive Partial Inward Stock (30 of 50 units)
    rcp1_resp = await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": store_a1_id,
            "purchase_order_id": po_id,
            "receipt_number": "RCP-2026-001",
            "invoice_number": "INV-ARTISAN-8891",
            "items": [
                {
                    "variant_id": variant_a1_id,
                    "quantity_received": 30,
                    "unit_cost": "1500.00",
                }
            ],
        },
        headers=headers_a,
    )
    assert rcp1_resp.status_code == 201

    # 6. Verify PO status updated to partially_received
    po_updated = (await client.get(f"/api/v1/merchant/inventory/purchase-orders/{po_id}", headers=headers_a)).json()
    assert po_updated["status"] == "partially_received"
    assert po_updated["items"][0]["quantity_received"] == 30

    # 7. Verify Stock Balance: On-Hand = 30, Available = 30
    bal_after_rcp1 = (await client.get(
        f"/api/v1/merchant/inventory/balances/{store_a1_id}/{variant_a1_id}",
        headers=headers_a,
    )).json()
    assert bal_after_rcp1["on_hand_qty"] == 30
    assert bal_after_rcp1["available_qty"] == 30
    assert bal_after_rcp1["reserved_qty"] == 0

    # 8. Receive remaining 20 units
    rcp2_resp = await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": store_a1_id,
            "purchase_order_id": po_id,
            "receipt_number": "RCP-2026-002",
            "invoice_number": "INV-ARTISAN-8899",
            "items": [
                {
                    "variant_id": variant_a1_id,
                    "quantity_received": 20,
                    "unit_cost": "1500.00",
                }
            ],
        },
        headers=headers_a,
    )
    assert rcp2_resp.status_code == 201

    # 9. Verify PO status updated to received
    po_final = (await client.get(f"/api/v1/merchant/inventory/purchase-orders/{po_id}", headers=headers_a)).json()
    assert po_final["status"] == "received"
    assert po_final["items"][0]["quantity_received"] == 50

    # 10. Verify Stock Balance: On-Hand = 50, Available = 50
    bal_final = (await client.get(
        f"/api/v1/merchant/inventory/balances/{store_a1_id}/{variant_a1_id}",
        headers=headers_a,
    )).json()
    assert bal_final["on_hand_qty"] == 50
    assert bal_final["available_qty"] == 50

    # 11. Verify Double-Entry Ledger entries
    ledger_entries = (await client.get(
        f"/api/v1/merchant/inventory/ledger?store_id={store_a1_id}&variant_id={variant_a1_id}",
        headers=headers_a,
    )).json()
    assert len(ledger_entries) == 2
    for entry in ledger_entries:
        assert entry["movement_type"] == "PURCHASE_RECEIPT"
        assert entry["from_account"] == "SUPPLIER_INWARD"
        assert entry["to_account"] == "STORE_ON_HAND"
        assert entry["on_hand_delta"] > 0
        assert entry["reserved_delta"] == 0


@pytest.mark.asyncio
async def test_reservation_release_dispatch_lifecycle(client: AsyncClient, setup_inventory_context):
    data = setup_inventory_context
    headers_a = data["headers_a"]
    store_a1_id = str(data["store_a1_id"])
    variant_a1_id = str(data["variant_a1_id"])

    # Inward stock of 10 units
    await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": store_a1_id,
            "receipt_number": "RCP-INWARD-10",
            "items": [{"variant_id": variant_a1_id, "quantity_received": 10, "unit_cost": "1000.00"}],
        },
        headers=headers_a,
    )

    # 1. Customer order reservation: Reserve 4 units
    res_resp = await client.post(
        "/api/v1/merchant/inventory/reservations",
        json={
            "store_id": store_a1_id,
            "variant_id": variant_a1_id,
            "quantity": 4,
            "reference_id": "ORDER-1001",
            "notes": "Hold for online customer checkout",
        },
        headers=headers_a,
    )
    assert res_resp.status_code == 201
    entry_res = res_resp.json()
    assert entry_res["movement_type"] == "SALES_RESERVATION"
    assert entry_res["from_account"] == "STORE_ON_HAND"
    assert entry_res["to_account"] == "STORE_RESERVED"
    assert entry_res["balance_after_on_hand"] == 10
    assert entry_res["balance_after_reserved"] == 4
    assert entry_res["balance_after_available"] == 6

    # Verify balance
    bal1 = (await client.get(f"/api/v1/merchant/inventory/balances/{store_a1_id}/{variant_a1_id}", headers=headers_a)).json()
    assert bal1["on_hand_qty"] == 10
    assert bal1["reserved_qty"] == 4
    assert bal1["available_qty"] == 6

    # 2. Release partial reservation (e.g. user reduced cart from 4 to 3 -> release 1)
    rel_resp = await client.post(
        "/api/v1/merchant/inventory/reservations/release",
        json={
            "store_id": store_a1_id,
            "variant_id": variant_a1_id,
            "quantity": 1,
            "reference_id": "ORDER-1001",
            "notes": "User decreased cart quantity",
        },
        headers=headers_a,
    )
    assert rel_resp.status_code == 200
    entry_rel = rel_resp.json()
    assert entry_rel["movement_type"] == "SALES_RELEASE"
    assert entry_rel["balance_after_reserved"] == 3
    assert entry_rel["balance_after_available"] == 7

    # 3. Dispatch the remaining 3 units (order paid, packed, dispatched)
    disp_resp = await client.post(
        "/api/v1/merchant/inventory/dispatch",
        json={
            "store_id": store_a1_id,
            "variant_id": variant_a1_id,
            "quantity": 3,
            "reference_id": "ORDER-1001",
            "notes": "Shipped to customer via courier",
        },
        headers=headers_a,
    )
    assert disp_resp.status_code == 200
    entry_disp = disp_resp.json()
    assert entry_disp["movement_type"] == "SALES_DISPATCH"
    assert entry_disp["from_account"] == "STORE_RESERVED"
    assert entry_disp["to_account"] == "SALES_CUSTOMER"
    assert entry_disp["balance_after_on_hand"] == 7
    assert entry_disp["balance_after_reserved"] == 0
    assert entry_disp["balance_after_available"] == 7

    # Final balance check
    bal_final = (await client.get(f"/api/v1/merchant/inventory/balances/{store_a1_id}/{variant_a1_id}", headers=headers_a)).json()
    assert bal_final["on_hand_qty"] == 7
    assert bal_final["reserved_qty"] == 0
    assert bal_final["available_qty"] == 7


@pytest.mark.asyncio
async def test_overselling_and_negative_stock_prevention(client: AsyncClient, setup_inventory_context):
    data = setup_inventory_context
    headers_a = data["headers_a"]
    store_a1_id = str(data["store_a1_id"])
    variant_a1_id = str(data["variant_a1_id"])

    # Inward 5 units
    await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": store_a1_id,
            "receipt_number": "RCP-OVERSOLD-TEST",
            "items": [{"variant_id": variant_a1_id, "quantity_received": 5, "unit_cost": "500.00"}],
        },
        headers=headers_a,
    )

    # Attempt to reserve 6 units -> must fail with 409 Conflict (INSUFFICIENT_AVAILABLE_STOCK)
    fail_res = await client.post(
        "/api/v1/merchant/inventory/reservations",
        json={
            "store_id": store_a1_id,
            "variant_id": variant_a1_id,
            "quantity": 6,
            "reference_id": "GREEDY-ORDER",
        },
        headers=headers_a,
    )
    assert fail_res.status_code == 409
    assert fail_res.json()["code"] == "INSUFFICIENT_AVAILABLE_STOCK"

    # Attempt to adjust damage for 10 units -> must fail with 409 Conflict (INSUFFICIENT_STOCK)
    fail_adj = await client.post(
        "/api/v1/merchant/inventory/adjustments",
        json={
            "store_id": store_a1_id,
            "variant_id": variant_a1_id,
            "reason": "damage",
            "quantity": 10,
        },
        headers=headers_a,
    )
    assert fail_adj.status_code == 409
    assert fail_adj.json()["code"] == "INSUFFICIENT_STOCK"

    # Attempt to release reservation when reserved=0 -> must fail with 409 Conflict (INVALID_RESERVATION)
    fail_rel = await client.post(
        "/api/v1/merchant/inventory/reservations/release",
        json={
            "store_id": store_a1_id,
            "variant_id": variant_a1_id,
            "quantity": 2,
            "reference_id": "PHANTOM-ORDER",
        },
        headers=headers_a,
    )
    assert fail_rel.status_code == 409
    assert fail_rel.json()["code"] == "INVALID_RESERVATION"


@pytest.mark.asyncio
async def test_idempotency_protection_against_duplicate_events(client: AsyncClient, setup_inventory_context):
    data = setup_inventory_context
    headers_a = data["headers_a"]
    store_a1_id = str(data["store_a1_id"])
    variant_a1_id = str(data["variant_a1_id"])

    # Inward 10 units
    await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": store_a1_id,
            "receipt_number": "RCP-IDEMP-01",
            "items": [{"variant_id": variant_a1_id, "quantity_received": 10, "unit_cost": "500.00"}],
        },
        headers=headers_a,
    )

    # First attempt: Reserve 3 units with unique idempotency_key
    key = "CHECKOUT-UUID-9999"
    resp1 = await client.post(
        "/api/v1/merchant/inventory/reservations",
        json={
            "store_id": store_a1_id,
            "variant_id": variant_a1_id,
            "quantity": 3,
            "reference_id": "ORDER-9999",
            "idempotency_key": key,
        },
        headers=headers_a,
    )
    assert resp1.status_code == 201
    entry1 = resp1.json()
    assert entry1["balance_after_available"] == 7

    # Second attempt: Network retry with the SAME idempotency_key
    resp2 = await client.post(
        "/api/v1/merchant/inventory/reservations",
        json={
            "store_id": store_a1_id,
            "variant_id": variant_a1_id,
            "quantity": 3,
            "reference_id": "ORDER-9999",
            "idempotency_key": key,
        },
        headers=headers_a,
    )
    assert resp2.status_code == 201
    entry2 = resp2.json()
    assert entry2["id"] == entry1["id"]

    # Verify balance is STILL 7 (did not double decrement to 4!)
    bal = (await client.get(f"/api/v1/merchant/inventory/balances/{store_a1_id}/{variant_a1_id}", headers=headers_a)).json()
    assert bal["reserved_qty"] == 3
    assert bal["available_qty"] == 7


@pytest.mark.asyncio
async def test_store_transfers_with_in_transit_reconciliation(client: AsyncClient, setup_inventory_context):
    data = setup_inventory_context
    headers_a = data["headers_a"]
    store_a1_id = str(data["store_a1_id"])  # Flagship Store
    store_a2_id = str(data["store_a2_id"])  # Warehouse
    variant_a1_id = str(data["variant_a1_id"])

    # 1. Inward 20 units into Store A1 (Flagship)
    await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": store_a1_id,
            "receipt_number": "RCP-TRANSFER-INIT",
            "items": [{"variant_id": variant_a1_id, "quantity_received": 20, "unit_cost": "1000.00"}],
        },
        headers=headers_a,
    )

    # 2. Transfer 8 units from Store A1 to Store A2 (Warehouse)
    trf_resp = await client.post(
        "/api/v1/merchant/inventory/transfers",
        json={
            "source_store_id": store_a1_id,
            "destination_store_id": store_a2_id,
            "transfer_number": "TRF-2026-001",
            "items": [{"variant_id": variant_a1_id, "quantity_shipped": 8}],
            "notes": "Restocking secondary warehouse",
        },
        headers=headers_a,
    )
    assert trf_resp.status_code == 201
    transfer = trf_resp.json()
    assert transfer["status"] == "in_transit"
    transfer_id = transfer["id"]

    # 3. VERIFY IN-TRANSIT STATE:
    # Source Store A1: on_hand = 12, in_transit = 8, available = 12
    bal_src = (await client.get(f"/api/v1/merchant/inventory/balances/{store_a1_id}/{variant_a1_id}", headers=headers_a)).json()
    assert bal_src["on_hand_qty"] == 12
    assert bal_src["in_transit_qty"] == 8
    assert bal_src["available_qty"] == 12

    # Destination Store A2: on_hand = 0, available = 0 (goods still on the truck!)
    bal_dest_before = (await client.get(f"/api/v1/merchant/inventory/balances/{store_a2_id}/{variant_a1_id}", headers=headers_a)).json()
    assert bal_dest_before["on_hand_qty"] == 0
    assert bal_dest_before["available_qty"] == 0

    # 4. Destination Store receives the transfer
    recv_resp = await client.post(
        f"/api/v1/merchant/inventory/transfers/{transfer_id}/receive",
        json={"notes": "Received safely in good condition"},
        headers=headers_a,
    )
    assert recv_resp.status_code == 200
    assert recv_resp.json()["status"] == "completed"

    # 5. VERIFY POST-TRANSFER BALANCES:
    # Source Store A1: in_transit relieved -> in_transit = 0, on_hand = 12
    bal_src_final = (await client.get(f"/api/v1/merchant/inventory/balances/{store_a1_id}/{variant_a1_id}", headers=headers_a)).json()
    assert bal_src_final["on_hand_qty"] == 12
    assert bal_src_final["in_transit_qty"] == 0
    assert bal_src_final["available_qty"] == 12

    # Destination Store A2: on_hand = 8, available = 8
    bal_dest_final = (await client.get(f"/api/v1/merchant/inventory/balances/{store_a2_id}/{variant_a1_id}", headers=headers_a)).json()
    assert bal_dest_final["on_hand_qty"] == 8
    assert bal_dest_final["available_qty"] == 8


@pytest.mark.asyncio
async def test_adjustments_damage_loss_and_reconciliation(client: AsyncClient, setup_inventory_context):
    data = setup_inventory_context
    headers_a = data["headers_a"]
    store_a1_id = str(data["store_a1_id"])
    variant_a1_id = str(data["variant_a1_id"])

    # Inward 25 units
    await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": store_a1_id,
            "receipt_number": "RCP-ADJUST-INIT",
            "items": [{"variant_id": variant_a1_id, "quantity_received": 25, "unit_cost": "800.00"}],
        },
        headers=headers_a,
    )

    # 1. Damage adjustment: 2 units damaged in flood/mishandling
    dmg_resp = await client.post(
        "/api/v1/merchant/inventory/adjustments",
        json={
            "store_id": store_a1_id,
            "variant_id": variant_a1_id,
            "reason": "damage",
            "quantity": 2,
            "notes": "Broken during shelf reorganization",
        },
        headers=headers_a,
    )
    assert dmg_resp.status_code == 200
    assert dmg_resp.json()["movement_type"] == "ADJUSTMENT_DAMAGE"
    assert dmg_resp.json()["balance_after_on_hand"] == 23

    # 2. Loss adjustment: 1 unit missing/unaccounted
    loss_resp = await client.post(
        "/api/v1/merchant/inventory/adjustments",
        json={
            "store_id": store_a1_id,
            "variant_id": variant_a1_id,
            "reason": "loss",
            "quantity": 1,
            "notes": "Unaccounted discrepancy",
        },
        headers=headers_a,
    )
    assert loss_resp.status_code == 200
    assert loss_resp.json()["movement_type"] == "ADJUSTMENT_LOSS"
    assert loss_resp.json()["balance_after_on_hand"] == 22

    # 3. Reconciliation Gain: Cycle audit found 3 extra units
    gain_resp = await client.post(
        "/api/v1/merchant/inventory/adjustments",
        json={
            "store_id": store_a1_id,
            "variant_id": variant_a1_id,
            "reason": "reconciliation_gain",
            "quantity": 3,
            "notes": "Audit cycle count surplus",
        },
        headers=headers_a,
    )
    assert gain_resp.status_code == 200
    assert gain_resp.json()["movement_type"] == "RECONCILIATION_GAIN"
    assert gain_resp.json()["balance_after_on_hand"] == 25

    # 4. Customer Return: 1 unit returned by customer
    ret_resp = await client.post(
        "/api/v1/merchant/inventory/returns",
        json={
            "store_id": store_a1_id,
            "variant_id": variant_a1_id,
            "quantity": 1,
            "reference_id": "RETURN-RMA-554",
            "notes": "Returned unused in original box",
        },
        headers=headers_a,
    )
    assert ret_resp.status_code == 200
    assert ret_resp.json()["movement_type"] == "CUSTOMER_RETURN"
    assert ret_resp.json()["balance_after_on_hand"] == 26


@pytest.mark.asyncio
async def test_cross_tenant_and_cross_store_isolation(client: AsyncClient, setup_inventory_context):
    data = setup_inventory_context
    headers_a = data["headers_a"]
    headers_b = data["headers_b"]
    store_a1_id = str(data["store_a1_id"])
    store_b1_id = str(data["store_b1_id"])
    variant_a1_id = str(data["variant_a1_id"])

    # Merchant A receives stock
    await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": store_a1_id,
            "receipt_number": "RCP-TENANT-A",
            "items": [{"variant_id": variant_a1_id, "quantity_received": 15, "unit_cost": "750.00"}],
        },
        headers=headers_a,
    )

    # 1. Merchant B attempts to read Merchant A's stock balance -> 404 Not Found
    resp_b_bal = await client.get(
        f"/api/v1/merchant/inventory/balances/{store_a1_id}/{variant_a1_id}",
        headers=headers_b,
    )
    assert resp_b_bal.status_code == 404

    # 2. Merchant B attempts to reserve Merchant A's stock -> 404 Not Found
    resp_b_res = await client.post(
        "/api/v1/merchant/inventory/reservations",
        json={
            "store_id": store_a1_id,
            "variant_id": variant_a1_id,
            "quantity": 5,
            "reference_id": "HACK-ORDER",
        },
        headers=headers_b,
    )
    assert resp_b_res.status_code == 404

    # 3. Merchant A attempts to transfer stock to Merchant B's store -> 404 Not Found
    resp_cross_trf = await client.post(
        "/api/v1/merchant/inventory/transfers",
        json={
            "source_store_id": store_a1_id,
            "destination_store_id": store_b1_id,
            "transfer_number": "TRF-ILLICIT",
            "items": [{"variant_id": variant_a1_id, "quantity_shipped": 5}],
        },
        headers=headers_a,
    )
    assert resp_cross_trf.status_code == 404

