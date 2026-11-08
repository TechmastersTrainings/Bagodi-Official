from uuid import UUID

import pytest
from httpx import AsyncClient


@pytest.fixture
async def setup_tenants_and_users(client: AsyncClient, mint_jwt_token):
    """Helper fixture to onboard and activate Tenant A (Bagodi) and Tenant B (Second Merchant)

    and produce their respective authenticated clients / headers.
    """
    platform_admin_token = mint_jwt_token(
        is_platform_user=True,
        permissions=["platform.*"],
    )
    platform_headers = {"Authorization": f"Bearer {platform_admin_token}"}

    # Onboard Tenant A
    resp_a = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Bagodi Bidar Store",
            "slug": "bagodi-bidar",
            "legal_name": "Bagodi Enterprises",
            "contact_email": "ops@bagodi.in",
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

    # Onboard Tenant B
    resp_b = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Second Merchant Bidar",
            "slug": "second-bidar",
            "legal_name": "Second Merchant LLP",
            "contact_email": "ops@secondmerchant.in",
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

    # Tokens with catalog permissions
    merchant_a_token = mint_jwt_token(
        tenant_id=tenant_a_id,
        permissions=["catalog.*"],
    )
    merchant_b_token = mint_jwt_token(
        tenant_id=tenant_b_id,
        permissions=["catalog.*"],
    )

    return {
        "platform_headers": platform_headers,
        "tenant_a_id": tenant_a_id,
        "tenant_a_headers": {"Authorization": f"Bearer {merchant_a_token}"},
        "tenant_b_id": tenant_b_id,
        "tenant_b_headers": {"Authorization": f"Bearer {merchant_b_token}"},
    }


@pytest.mark.asyncio
async def test_category_hierarchy_and_ownership(client: AsyncClient, setup_tenants_and_users):
    data = setup_tenants_and_users
    platform_headers = data["platform_headers"]
    headers_a = data["tenant_a_headers"]
    headers_b = data["tenant_b_headers"]

    # 1. Platform Admin creates global root category
    resp_global = await client.post(
        "/api/v1/platform/catalog/categories",
        json={
            "name": "Apparel & Textiles",
            "slug": "apparel-textiles",
            "description": "Standard apparel category",
        },
        headers=platform_headers,
    )
    assert resp_global.status_code == 201
    global_cat = resp_global.json()
    assert global_cat["tenant_id"] is None
    global_cat_id = global_cat["id"]

    # 2. Merchant A creates subcategory under global category
    resp_sub_a = await client.post(
        "/api/v1/merchant/catalog/categories",
        json={
            "parent_id": global_cat_id,
            "name": "Bidar Traditional Sarees",
            "slug": "bidar-sarees",
            "description": "Handloom sarees",
        },
        headers=headers_a,
    )
    assert resp_sub_a.status_code == 201
    sub_a = resp_sub_a.json()
    assert sub_a["tenant_id"] == str(data["tenant_a_id"])
    assert sub_a["parent_id"] == global_cat_id

    # 3. Merchant A lists categories -> sees global + Merchant A's category
    resp_list_a = await client.get("/api/v1/merchant/catalog/categories", headers=headers_a)
    assert resp_list_a.status_code == 200
    slugs_a = [c["slug"] for c in resp_list_a.json()]
    assert "apparel-textiles" in slugs_a
    assert "bidar-sarees" in slugs_a

    # 4. Merchant B lists categories -> sees global, but NOT Merchant A's category
    resp_list_b = await client.get("/api/v1/merchant/catalog/categories", headers=headers_b)
    assert resp_list_b.status_code == 200
    slugs_b = [c["slug"] for c in resp_list_b.json()]
    assert "apparel-textiles" in slugs_b
    assert "bidar-sarees" not in slugs_b

    # 5. Merchant B creates category with same slug "bidar-sarees" -> succeeds (tenant-scoped)
    resp_sub_b = await client.post(
        "/api/v1/merchant/catalog/categories",
        json={
            "parent_id": global_cat_id,
            "name": "Second Merchant Sarees",
            "slug": "bidar-sarees",
        },
        headers=headers_b,
    )
    assert resp_sub_b.status_code == 201

    # 6. Merchant A duplicate slug -> 409 Conflict
    resp_dup = await client.post(
        "/api/v1/merchant/catalog/categories",
        json={
            "name": "Another Saree Category",
            "slug": "bidar-sarees",
        },
        headers=headers_a,
    )
    assert resp_dup.status_code == 409
    assert resp_dup.json()["code"] == "CATEGORY_SLUG_EXISTS"

    # 7. Merchant A cannot update global category -> 403 Forbidden
    resp_update_global = await client.patch(
        f"/api/v1/merchant/catalog/categories/{global_cat_id}",
        json={"name": "Tampered Name"},
        headers=headers_a,
    )
    assert resp_update_global.status_code == 403
    assert resp_update_global.json()["code"] == "CANNOT_MODIFY_GLOBAL_CATEGORY"


@pytest.mark.asyncio
async def test_brand_global_and_merchant_isolation(client: AsyncClient, setup_tenants_and_users):
    data = setup_tenants_and_users
    platform_headers = data["platform_headers"]
    headers_a = data["tenant_a_headers"]
    headers_b = data["tenant_b_headers"]

    # 1. Platform Admin creates global brand
    resp_global = await client.post(
        "/api/v1/platform/catalog/brands",
        json={"name": "Raymond", "slug": "raymond"},
        headers=platform_headers,
    )
    assert resp_global.status_code == 201
    assert resp_global.json()["tenant_id"] is None

    # 2. Merchant A creates private brand
    resp_brand_a = await client.post(
        "/api/v1/merchant/catalog/brands",
        json={"name": "Bagodi In-House", "slug": "bagodi-in-house"},
        headers=headers_a,
    )
    assert resp_brand_a.status_code == 201

    # 3. Merchant A listing contains both
    list_a = (await client.get("/api/v1/merchant/catalog/brands", headers=headers_a)).json()
    slugs_a = [b["slug"] for b in list_a]
    assert "raymond" in slugs_a
    assert "bagodi-in-house" in slugs_a

    # 4. Merchant B listing contains global only, not Merchant A's brand
    list_b = (await client.get("/api/v1/merchant/catalog/brands", headers=headers_b)).json()
    slugs_b = [b["slug"] for b in list_b]
    assert "raymond" in slugs_b
    assert "bagodi-in-house" not in slugs_b


@pytest.mark.asyncio
async def test_merchant_product_variant_and_image_management(
    client: AsyncClient, setup_tenants_and_users
):
    data = setup_tenants_and_users
    headers_a = data["tenant_a_headers"]

    # 1. Create category and brand for product association
    cat_resp = await client.post(
        "/api/v1/merchant/catalog/categories",
        json={"name": "Handicrafts", "slug": "handicrafts"},
        headers=headers_a,
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]

    brand_resp = await client.post(
        "/api/v1/merchant/catalog/brands",
        json={"name": "Bidri Craftwork", "slug": "bidri-craftwork"},
        headers=headers_a,
    )
    assert brand_resp.status_code == 201
    brand_id = brand_resp.json()["id"]

    # 2. Create Product with initial variants and image
    product_payload = {
        "category_id": cat_id,
        "brand_id": brand_id,
        "name": "Bidriware Silver Inlay Floral Vase",
        "slug": "bidriware-silver-inlay-floral-vase",
        "description": "Authentic Bidriware crafted using zinc and copper alloy with pure silver inlay.",
        "status": "draft",
        "is_published": False,
        "variants": [
            {
                "sku": "BD-VASE-06INCH",
                "barcode": "890123456001",
                "name": "6 Inch Vase",
                "attributes": {"height": "6 inches", "finish": "matte black"},
                "mrp": "2499.00",
                "base_price": "1999.00",
                "status": "active",
            },
            {
                "sku": "BD-VASE-08INCH",
                "barcode": "890123456002",
                "name": "8 Inch Vase",
                "attributes": {"height": "8 inches", "finish": "matte black"},
                "mrp": "3499.00",
                "base_price": "2999.00",
                "status": "active",
            },
        ],
        "images": [
            {
                "url": "https://cdn.bagodi.in/products/bidri-vase-1.jpg",
                "alt_text": "Bidriware Silver Inlay Vase Front View",
                "is_primary": True,
                "sort_order": 0,
            }
        ],
    }

    resp = await client.post(
        "/api/v1/merchant/catalog/products", json=product_payload, headers=headers_a
    )
    assert resp.status_code == 201
    prod = resp.json()
    prod_id = prod["id"]
    assert prod["name"] == "Bidriware Silver Inlay Floral Vase"
    assert prod["status"] == "draft"
    assert prod["is_published"] is False
    assert len(prod["variants"]) == 2
    assert len(prod["images"]) == 1

    # Verify variants contain NO stock balance columns (Phase 4 inventory ledger boundary)
    for variant in prod["variants"]:
        assert "stock" not in variant
        assert "quantity" not in variant
        assert "available_stock" not in variant

    # 3. Add a third variant to existing product
    resp_var3 = await client.post(
        f"/api/v1/merchant/catalog/products/{prod_id}/variants",
        json={
            "sku": "BD-VASE-10INCH",
            "barcode": "890123456003",
            "name": "10 Inch Vase",
            "attributes": {"height": "10 inches"},
            "mrp": "4999.00",
            "base_price": "4299.00",
            "status": "active",
        },
        headers=headers_a,
    )
    assert resp_var3.status_code == 201
    var3_id = resp_var3.json()["id"]

    # 4. Update the variant
    resp_up_var = await client.patch(
        f"/api/v1/merchant/catalog/variants/{var3_id}",
        json={"base_price": "3999.00", "name": "10 Inch Masterpiece Vase"},
        headers=headers_a,
    )
    assert resp_up_var.status_code == 200
    assert resp_up_var.json()["base_price"] == "3999.00"
    assert resp_up_var.json()["name"] == "10 Inch Masterpiece Vase"

    # 5. Add an additional image
    resp_img2 = await client.post(
        f"/api/v1/merchant/catalog/products/{prod_id}/images",
        json={
            "url": "https://cdn.bagodi.in/products/bidri-vase-detail.jpg",
            "alt_text": "Bidriware Silver Inlay Close-up Detail",
            "is_primary": False,
            "sort_order": 1,
        },
        headers=headers_a,
    )
    assert resp_img2.status_code == 201

    # 6. Publish the product
    resp_publish = await client.patch(
        f"/api/v1/merchant/catalog/products/{prod_id}",
        json={"status": "active", "is_published": True},
        headers=headers_a,
    )
    assert resp_publish.status_code == 200
    updated_prod = resp_publish.json()
    assert updated_prod["status"] == "active"
    assert updated_prod["is_published"] is True
    assert len(updated_prod["variants"]) == 3
    assert len(updated_prod["images"]) == 2


@pytest.mark.asyncio
async def test_sku_and_barcode_uniqueness_enforcement(client: AsyncClient, setup_tenants_and_users):
    data = setup_tenants_and_users
    headers_a = data["tenant_a_headers"]
    headers_b = data["tenant_b_headers"]

    # Create category for products
    cat_a = (
        await client.post(
            "/api/v1/merchant/catalog/categories",
            json={"name": "Clothing A", "slug": "clothing-a"},
            headers=headers_a,
        )
    ).json()
    cat_b = (
        await client.post(
            "/api/v1/merchant/catalog/categories",
            json={"name": "Clothing B", "slug": "clothing-b"},
            headers=headers_b,
        )
    ).json()

    # Merchant A creates Product 1
    p1_payload = {
        "category_id": cat_a["id"],
        "name": "Bidar Silk Scarf",
        "slug": "bidar-silk-scarf",
        "variants": [
            {
                "sku": "SILK-SCARF-RED",
                "barcode": "8909990001",
                "name": "Red Scarf",
                "mrp": "999.00",
                "base_price": "799.00",
                "status": "active",
            }
        ],
    }
    resp1 = await client.post(
        "/api/v1/merchant/catalog/products", json=p1_payload, headers=headers_a
    )
    assert resp1.status_code == 201
    p1_id = resp1.json()["id"]

    # Merchant A attempts to add variant with duplicate SKU
    resp_dup_sku = await client.post(
        f"/api/v1/merchant/catalog/products/{p1_id}/variants",
        json={
            "sku": "SILK-SCARF-RED",
            "barcode": "8909990002",
            "name": "Another Red Scarf",
            "mrp": "999.00",
            "base_price": "799.00",
            "status": "active",
        },
        headers=headers_a,
    )
    assert resp_dup_sku.status_code == 409
    assert resp_dup_sku.json()["code"] == "VARIANT_SKU_EXISTS"

    # Merchant A attempts to add variant with duplicate Barcode
    resp_dup_barcode = await client.post(
        f"/api/v1/merchant/catalog/products/{p1_id}/variants",
        json={
            "sku": "SILK-SCARF-BLUE",
            "barcode": "8909990001",
            "name": "Blue Scarf",
            "mrp": "999.00",
            "base_price": "799.00",
            "status": "active",
        },
        headers=headers_a,
    )
    assert resp_dup_barcode.status_code == 409
    assert resp_dup_barcode.json()["code"] == "VARIANT_BARCODE_EXISTS"

    # Merchant B creates product with SAME SKU and BARCODE -> succeeds because scoped per tenant!
    p_b_payload = {
        "category_id": cat_b["id"],
        "name": "Merchant B Scarf",
        "slug": "merchant-b-scarf",
        "variants": [
            {
                "sku": "SILK-SCARF-RED",
                "barcode": "8909990001",
                "name": "Red Scarf B",
                "mrp": "1099.00",
                "base_price": "899.00",
                "status": "active",
            }
        ],
    }
    resp_b = await client.post(
        "/api/v1/merchant/catalog/products", json=p_b_payload, headers=headers_b
    )
    assert resp_b.status_code == 201


@pytest.mark.asyncio
async def test_cross_tenant_product_isolation(client: AsyncClient, setup_tenants_and_users):
    data = setup_tenants_and_users
    headers_a = data["tenant_a_headers"]
    headers_b = data["tenant_b_headers"]

    cat_a = (
        await client.post(
            "/api/v1/merchant/catalog/categories",
            json={"name": "Jewelry", "slug": "jewelry"},
            headers=headers_a,
        )
    ).json()

    # Merchant A creates Product A
    resp_a = await client.post(
        "/api/v1/merchant/catalog/products",
        json={
            "category_id": cat_a["id"],
            "name": "Merchant A Exclusive Jewelry Box",
            "slug": "merchant-a-jewelry-box",
            "variants": [
                {
                    "sku": "JWL-BOX-01",
                    "name": "Standard Box",
                    "mrp": "1500.00",
                    "base_price": "1200.00",
                    "status": "active",
                }
            ],
        },
        headers=headers_a,
    )
    assert resp_a.status_code == 201
    prod_a = resp_a.json()
    prod_a_id = prod_a["id"]
    variant_a_id = prod_a["variants"][0]["id"]

    # Merchant B attempts to fetch Merchant A's product -> 404 Not Found
    resp_get = await client.get(f"/api/v1/merchant/catalog/products/{prod_a_id}", headers=headers_b)
    assert resp_get.status_code == 404

    # Merchant B attempts to modify Merchant A's product -> 404 Not Found
    resp_patch = await client.patch(
        f"/api/v1/merchant/catalog/products/{prod_a_id}",
        json={"name": "Hacked Title"},
        headers=headers_b,
    )
    assert resp_patch.status_code == 404

    # Merchant B attempts to add a variant to Merchant A's product -> 404 Not Found
    resp_add_var = await client.post(
        f"/api/v1/merchant/catalog/products/{prod_a_id}/variants",
        json={
            "sku": "JWL-BOX-02",
            "name": "Illicit Variant",
            "mrp": "1500.00",
            "base_price": "1200.00",
            "status": "active",
        },
        headers=headers_b,
    )
    assert resp_add_var.status_code == 404

    # Merchant B attempts to update Merchant A's variant -> 404 Not Found
    resp_patch_var = await client.patch(
        f"/api/v1/merchant/catalog/variants/{variant_a_id}",
        json={"base_price": "1.00"},
        headers=headers_b,
    )
    assert resp_patch_var.status_code == 404

    # Merchant B attempts to add image to Merchant A's product -> 404 Not Found
    resp_add_img = await client.post(
        f"/api/v1/merchant/catalog/products/{prod_a_id}/images",
        json={"url": "https://cdn.hack.com/bad.jpg"},
        headers=headers_b,
    )
    assert resp_add_img.status_code == 404

    # Merchant B's product listing does NOT show Merchant A's product
    list_resp_b = await client.get("/api/v1/merchant/catalog/products", headers=headers_b)
    assert list_resp_b.status_code == 200
    assert len(list_resp_b.json()) == 0


@pytest.mark.asyncio
async def test_public_customer_catalogue_visibility(client: AsyncClient, setup_tenants_and_users):
    data = setup_tenants_and_users
    headers_a = data["tenant_a_headers"]
    tenant_a_id = data["tenant_a_id"]

    cat_a = (
        await client.post(
            "/api/v1/merchant/catalog/categories",
            json={"name": "Sweets & Confectionery", "slug": "sweets"},
            headers=headers_a,
        )
    ).json()

    # 1. Product 1: Live & Published
    resp_p1 = await client.post(
        "/api/v1/merchant/catalog/products",
        json={
            "category_id": cat_a["id"],
            "name": "Bidar Special Cashew Sweets",
            "slug": "bidar-special-cashew-sweets",
            "status": "active",
            "is_published": True,
            "variants": [
                {
                    "sku": "SWEET-CSH-500G",
                    "name": "500g Box",
                    "mrp": "600.00",
                    "base_price": "550.00",
                    "status": "active",
                }
            ],
        },
        headers=headers_a,
    )
    assert resp_p1.status_code == 201

    # 2. Product 2: Draft (not ready for customers)
    resp_p2 = await client.post(
        "/api/v1/merchant/catalog/products",
        json={
            "category_id": cat_a["id"],
            "name": "Draft Coconut Ladoo",
            "slug": "draft-coconut-ladoo",
            "status": "draft",
            "is_published": True,  # is_published=True but status='draft' -> must NOT appear
            "variants": [
                {
                    "sku": "SWEET-LAD-500G",
                    "name": "500g Box",
                    "mrp": "300.00",
                    "base_price": "250.00",
                    "status": "active",
                }
            ],
        },
        headers=headers_a,
    )
    assert resp_p2.status_code == 201

    # 3. Product 3: Active but is_published=False (hidden from customer)
    resp_p3 = await client.post(
        "/api/v1/merchant/catalog/products",
        json={
            "category_id": cat_a["id"],
            "name": "Secret Hidden Product",
            "slug": "secret-hidden-product",
            "status": "active",
            "is_published": False,
            "variants": [
                {
                    "sku": "SECRET-SKU",
                    "name": "Secret Variant",
                    "mrp": "100.00",
                    "base_price": "90.00",
                    "status": "active",
                }
            ],
        },
        headers=headers_a,
    )
    assert resp_p3.status_code == 201

    # 4. Public endpoint GET /api/v1/catalog/products (no auth required)
    public_list = await client.get(f"/api/v1/catalog/products?tenant_id={tenant_a_id}")
    assert public_list.status_code == 200
    products = public_list.json()

    # Only Product 1 is exposed
    assert len(products) == 1
    assert products[0]["slug"] == "bidar-special-cashew-sweets"

    # 5. Public slug lookup
    # Product 1 slug -> 200 OK
    resp_slug_ok = await client.get("/api/v1/catalog/products/bidar-special-cashew-sweets")
    assert resp_slug_ok.status_code == 200
    assert resp_slug_ok.json()["name"] == "Bidar Special Cashew Sweets"

    # Product 2 slug (draft) -> 404 Not Found
    resp_slug_draft = await client.get("/api/v1/catalog/products/draft-coconut-ladoo")
    assert resp_slug_draft.status_code == 404

    # Product 3 slug (hidden) -> 404 Not Found
    resp_slug_hidden = await client.get("/api/v1/catalog/products/secret-hidden-product")
    assert resp_slug_hidden.status_code == 404

    # 6. Keyword search on public endpoint
    search_match = await client.get("/api/v1/catalog/products?search=Cashew")
    assert search_match.status_code == 200
    assert len(search_match.json()) == 1

    search_no_match = await client.get("/api/v1/catalog/products?search=NonExistentKeyword")
    assert search_no_match.status_code == 200
    assert len(search_no_match.json()) == 0


@pytest.mark.asyncio
async def test_barcode_lookup_scanner(client: AsyncClient, setup_tenants_and_users):
    data = setup_tenants_and_users
    headers_a = data["tenant_a_headers"]
    headers_b = data["tenant_b_headers"]

    barcode = "8905556667778"

    cat_a = (
        await client.post(
            "/api/v1/merchant/catalog/categories",
            json={"name": "Organic Grocery", "slug": "organic-grocery"},
            headers=headers_a,
        )
    ).json()

    # Merchant A creates a product with barcode
    resp_create = await client.post(
        "/api/v1/merchant/catalog/products",
        json={
            "category_id": cat_a["id"],
            "name": "Bidar Organic Honey 500g",
            "slug": "bidar-organic-honey-500g",
            "variants": [
                {
                    "sku": "HONEY-500G",
                    "barcode": barcode,
                    "name": "500g Jar",
                    "mrp": "450.00",
                    "base_price": "399.00",
                    "status": "active",
                }
            ],
        },
        headers=headers_a,
    )
    assert resp_create.status_code == 201

    # 1. Merchant A scans the barcode -> 200 OK with variant and parent product
    scan_a = await client.get(f"/api/v1/barcodes/{barcode}", headers=headers_a)
    assert scan_a.status_code == 200
    body = scan_a.json()
    assert body["variant"]["barcode"] == barcode
    assert body["variant"]["sku"] == "HONEY-500G"
    assert body["product"]["name"] == "Bidar Organic Honey 500g"

    # 2. Merchant B scans Merchant A's barcode -> 404 Not Found (tenant-isolated)
    scan_b = await client.get(f"/api/v1/barcodes/{barcode}", headers=headers_b)
    assert scan_b.status_code == 404
    assert scan_b.json()["code"] == "BARCODE_NOT_FOUND"

    # 3. Non-existent barcode scan -> 404 Not Found
    scan_unknown = await client.get("/api/v1/barcodes/9999999999999", headers=headers_a)
    assert scan_unknown.status_code == 404
    assert scan_unknown.json()["code"] == "BARCODE_NOT_FOUND"
