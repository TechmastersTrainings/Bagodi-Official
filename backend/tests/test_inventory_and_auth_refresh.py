import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_refresh_camel_case(client: AsyncClient, mint_jwt_token):
    # 1. Test POST /api/v1/auth/refresh with camelCase payload as sent by frontend client.ts
    refresh_token = mint_jwt_token(
        is_platform_user=False,
        permissions=["inventory.*", "catalog.*"],
    )
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": refresh_token},
    )
    # Should not return 422 Unprocessable Content
    assert resp.status_code != 422, f"Failed with 422: {resp.text}"

    # 2. Test POST /api/v1/auth/logout with camelCase payload
    logout_resp = await client.post(
        "/api/v1/auth/logout",
        json={"refreshToken": refresh_token},
    )
    assert logout_resp.status_code == 200, f"Logout failed: {logout_resp.text}"


@pytest.mark.asyncio
async def test_direct_inventory_endpoints(client: AsyncClient, mint_jwt_token):
    admin_token = mint_jwt_token(
        is_platform_user=True,
        permissions=["platform.*", "inventory.*", "catalog.*"],
    )
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Add inventory item with pushToCatalogue=False (staged)
    payload_staged = {
        "productName": "Bidar Heritage Raw Silk Staged Kurta",
        "categoryName": "Men's Wear",
        "price": 3499.00,
        "mrp": 4999.00,
        "onHandQuantity": 12,
        "size": "L (42)",
        "colorName": "Royal Gold",
        "pushToCatalogue": False,
    }
    create_resp = await client.post("/api/v1/inventory", json=payload_staged, headers=headers)
    assert create_resp.status_code == 201, f"Failed creating inventory: {create_resp.text}"
    staged_data = create_resp.json()
    assert staged_data["success"] is True
    assert staged_data["isPublished"] is False
    staged_variant_id = staged_data["variantId"]
    staged_product_id = staged_data["productId"]

    # 2. List inventory items
    list_resp = await client.get("/api/v1/inventory", headers=headers)
    assert list_resp.status_code == 200, f"List inventory failed: {list_resp.text}"
    inventory_data = list_resp.json()
    assert "items" in inventory_data
    assert any(i["variantId"] == staged_variant_id for i in inventory_data["items"])

    # 3. Test Stock Valuation
    val_resp = await client.get("/api/v1/inventory/valuation", headers=headers)
    assert val_resp.status_code == 200, f"Valuation failed: {val_resp.text}"
    val_data = val_resp.json()
    assert "totalRetailValuation" in val_data
    assert "totalUnitsOnHand" in val_data
    assert val_data["totalUnitsOnHand"] >= 12

    # 4. Test Barcode Lookup
    barcode = staged_data["barcode"]
    lookup_resp = await client.get(f"/api/v1/inventory/barcode/{barcode}", headers=headers)
    assert lookup_resp.status_code == 200
    lookup_data = lookup_resp.json()
    assert lookup_data["found"] is True
    assert lookup_data["productName"] == "Bidar Heritage Raw Silk Staged Kurta"

    # 5. Push staged item to catalogue
    push_resp = await client.post(
        "/api/v1/inventory/push-to-catalogue",
        json={"inventoryId": staged_variant_id},
        headers=headers,
    )
    assert push_resp.status_code == 200, f"Push to catalogue failed: {push_resp.text}"

    # 6. Verify product is now live on /api/v1/products
    prod_resp = await client.get("/api/v1/products")
    assert prod_resp.status_code == 200
    live_prods = prod_resp.json()
    assert any(p["id"] == staged_product_id for p in live_prods)

    # 7. Test Stock Movements
    mov_resp = await client.get("/api/v1/inventory/movements", headers=headers)
    assert mov_resp.status_code == 200
    mov_data = mov_resp.json()
    assert "items" in mov_data

    # 8. Test Stock Reconciliation
    recon_resp = await client.get("/api/v1/inventory/reconciliation", headers=headers)
    assert recon_resp.status_code == 200
    recon_data = recon_resp.json()
    assert "items" in recon_data

    # 9. Test Reconcile Commit
    reconcile_post = await client.post(
        "/api/v1/inventory/reconcile",
        json={"variantId": staged_variant_id, "countedQuantity": 15},
        headers=headers,
    )
    assert reconcile_post.status_code == 200

    # 10. Test Stock Adjust
    adjust_resp = await client.post(
        "/api/v1/inventory/adjust",
        json={
            "variantId": staged_variant_id,
            "operationType": "STOCK_ADJUSTMENT",
            "quantityChange": 2,
            "reason": "Found on upper shelf",
        },
        headers=headers,
    )
    assert adjust_resp.status_code == 200
    assert adjust_resp.json()["success"] is True
