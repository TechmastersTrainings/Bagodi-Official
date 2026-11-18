import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_products_post_and_put_direct(client: AsyncClient, mint_jwt_token):
    # Mint token with merchant catalog permissions
    admin_token = mint_jwt_token(
        is_platform_user=True,
        permissions=["platform.*", "catalog.*"],
    )
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. First ensure a category exists
    cat_resp = await client.post(
        "/api/v1/platform/catalog/categories",
        json={
            "name": "Men Kurta & Silk",
            "slug": "men-kurta-silk",
            "description": "Traditional royal menswear",
        },
        headers=headers,
    )
    assert cat_resp.status_code == 201, f"Failed to create category: {cat_resp.text}"
    cat_id = cat_resp.json()["id"]

    # 2. Test POST /api/v1/products with camelCase payload as sent by frontend
    payload = {
        "name": "Bidar Heritage Linen Kurta",
        "slug": "bidar-heritage-linen-kurta-test",
        "description": "Handcrafted premium linen kurta made in Bidar workshop.",
        "categoryId": cat_id,
        "basePrice": 2499.00,
        "isPublished": True,
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1596755094514-f87e34085b2c",
                "altText": "Linen Kurta Front",
                "displayOrder": 1,
                "isPrimary": True,
            }
        ],
    }

    resp = await client.post("/api/v1/products", json=payload, headers=headers)
    assert resp.status_code == 201, f"Expected 201 Created but got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["name"] == "Bidar Heritage Linen Kurta"
    assert "id" in data
    product_id = data["id"]

    # 3. Test GET /api/v1/products
    get_resp = await client.get("/api/v1/products")
    assert get_resp.status_code == 200
    products_list = get_resp.json()
    assert isinstance(products_list, list)
    assert any(p["id"] == product_id for p in products_list)

    # 4. Test PUT /api/v1/products/{product_id}
    update_payload = {
        "name": "Bidar Heritage Linen Kurta - Updated",
        "basePrice": 2799.00,
    }
    put_resp = await client.put(f"/api/v1/products/{product_id}", json=update_payload, headers=headers)
    assert put_resp.status_code == 200
    updated_data = put_resp.json()
    assert updated_data["name"] == "Bidar Heritage Linen Kurta - Updated"

    # 5. Test DELETE /api/v1/products/{product_id}
    del_resp = await client.delete(f"/api/v1/products/{product_id}", headers=headers)
    assert del_resp.status_code == 204
