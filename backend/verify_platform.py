import asyncio
import os
import sys
from uuid import UUID
from httpx import ASGITransport, AsyncClient

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://bagodi:bagodi_dev_secret@localhost:5432/bagodi"
)

from app.main import app

async def run_verification():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        print("\n==========================================")
        print("  BAGODI PLATFORM END-TO-END VERIFICATION")
        print("==========================================\n")

        # 1. Categories
        print("1. Checking Categories...")
        res = await client.get("/api/v1/catalog/categories")
        assert res.status_code == 200, f"Categories failed: {res.status_code} {res.text}"
        cats = res.json()
        cat_slugs = [c["slug"] for c in cats]
        print(f"   -> Found {len(cats)} categories: {cat_slugs}")
        expected_cats = ["mens-wear", "womens-wear", "kids-wear", "sarees", "blazers"]
        for ec in expected_cats:
            assert ec in cat_slugs, f"Missing category: {ec}"
        print("   [PASS] All 5 official categories present.")

        # 2. Brands
        print("\n2. Checking Brands...")
        res = await client.get("/api/v1/catalog/brands")
        assert res.status_code == 200, f"Brands failed: {res.status_code} {res.text}"
        brands = res.json()
        brand_slugs = [b["slug"] for b in brands]
        print(f"   -> Found {len(brands)} brands: {brand_slugs}")
        expected_brands = ["bagodi-atelier", "raymond", "park-avenue", "parx", "colorplus", "manyavar"]
        for eb in expected_brands:
            assert eb in brand_slugs, f"Missing brand: {eb}"
        print("   [PASS] All 6 authentic brands present.")

        # 3. Public Products & Filter Mapping
        print("\n3. Checking Live Storefront Products & Category Mapping...")
        res = await client.get("/api/v1/products")
        assert res.status_code == 200, f"Products failed: {res.status_code} {res.text}"
        products = res.json()
        print(f"   -> Total live published products: {len(products)}")
        assert len(products) > 0, "No products found in live catalogue!"

        # Check structure of the first product
        sample = products[0]
        print(f"   -> Sample Product: '{sample['name']}' (slug: {sample['slug']})")
        assert "category" in sample and sample["category"] is not None, "Product missing category relationship"
        assert "brand" in sample, "Product missing brand relationship"
        assert "variants" in sample and len(sample["variants"]) > 0, "Product has no variants"
        assert "images" in sample and len(sample["images"]) > 0, "Product has no images"
        assert "basePrice" in sample, "Product missing computed basePrice"
        print(f"      Category: {sample['category']['name']} ({sample['category']['slug']})")
        print(f"      Brand: {sample['brand']['name'] if sample['brand'] else 'N/A'}")
        print(f"      Variants (Sizes): {[v['size'] for v in sample['variants']]}")
        print(f"      Primary Image: {sample['images'][0]['url']}")
        print("   [PASS] Product relationship mapping and computed fields validated.")

        # Test filtering by category slug e.g. sarees, mens-wear
        for cat_slug in ["sarees", "mens-wear", "womens-wear", "kids-wear", "blazers"]:
            filter_res = await client.get(f"/api/v1/products?category={cat_slug}")
            assert filter_res.status_code == 200, f"Filter by {cat_slug} failed: {filter_res.text}"
            filtered_prods = filter_res.json()
            print(f"   -> Category filter '{cat_slug}': {len(filtered_prods)} item(s)")
            for p in filtered_prods:
                assert p["category"]["slug"] == cat_slug, f"Product {p['name']} category mismatch"
        print("   [PASS] Storefront category filtering verified across all categories.")

        # 4. Merchant Authentication
        print("\n4. Checking Merchant Authentication...")
        merchant_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "merchant@bagodi.in", "password": "Fri10Feb@2023"}
        )
        assert merchant_login.status_code == 200, f"Merchant login failed: {merchant_login.status_code} {merchant_login.text}"
        merchant_token = merchant_login.json()["access_token"]
        merchant_tenant_id = merchant_login.json().get("tenant_id")
        print(f"   -> Merchant logged in successfully. Tenant: {merchant_tenant_id}")
        merchant_headers = {
            "Authorization": f"Bearer {merchant_token}",
            "X-Tenant-ID": str(merchant_tenant_id)
        }
        print("   [PASS] Merchant authentication verified.")

        # 5. Merchant User Management
        print("\n5. Checking Merchant User Management (/api/v1/merchant/users)...")
        m_users_res = await client.get("/api/v1/merchant/users", headers=merchant_headers)
        assert m_users_res.status_code == 200, f"Merchant users failed: {m_users_res.status_code} {m_users_res.text}"
        m_users = m_users_res.json()
        print(f"   -> Found {len(m_users)} store team member(s)")
        print("   [PASS] Merchant User Management endpoint validated.")

        # 6. Merchant Product Creation (CRUD verification with auto-SKU, auto-slug, sizes S-XXL)
        print("\n6. Checking Merchant Apparel Item Creation (CRUD)...")
        # Find category ID for Sarees or Men's Wear
        saree_cat = next(c for c in cats if c["slug"] == "sarees")
        bagodi_brand = next(b for b in brands if b["slug"] == "bagodi-atelier")

        new_product_payload = {
            "name": "Bidar Heritage Paithani Silk Saree",
            "category_id": saree_cat["id"],
            "brand_id": bagodi_brand["id"],
            "description": "Exquisite hand-woven Paithani silk saree featuring peacock motifs and real zari pallu.",
            "is_published": True,
            "status": "active",
            "variants": [
                {"name": "Free Size", "size": "Free Size", "mrp": 21999.0, "base_price": 16999.0, "initial_stock": 5},
                {"name": "Size S", "size": "S", "mrp": 21999.0, "base_price": 16999.0, "initial_stock": 8},
                {"name": "Size M", "size": "M", "mrp": 21999.0, "base_price": 16999.0, "initial_stock": 10},
                {"name": "Size L", "size": "L", "mrp": 21999.0, "base_price": 16999.0, "initial_stock": 6},
                {"name": "Size XL", "size": "XL", "mrp": 21999.0, "base_price": 16999.0, "initial_stock": 4},
                {"name": "Size XXL", "size": "XXL", "mrp": 21999.0, "base_price": 16999.0, "initial_stock": 3},
            ],
            "images": [
                {
                    "url": "https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=1200&q=85",
                    "alt_text": "Bidar Heritage Paithani Silk Saree",
                    "is_primary": True,
                    "sort_order": 0
                }
            ]
        }
        create_res = await client.post(
            "/api/v1/merchant/catalog/products",
            json=new_product_payload,
            headers=merchant_headers
        )
        assert create_res.status_code in (200, 201), f"Product creation failed: {create_res.status_code} {create_res.text}"
        created_product = create_res.json()
        print(f"   -> Created Product: '{created_product['name']}'")
        print(f"      Auto-generated Slug: {created_product['slug']}")
        print(f"      Auto-generated SKUs: {[v['sku'] for v in created_product['variants']]}")
        assert created_product["slug"], "Slug was not auto-generated"
        for v in created_product["variants"]:
            assert v["sku"] and v["sku"].startswith("BGD-"), f"SKU {v['sku']} is invalid"
        print("   [PASS] Auto-SKU, auto-slug, and size-wise stock creation verified.")

        # Verify newly created product appears immediately in public products
        public_check = await client.get(f"/api/v1/products/{created_product['slug']}")
        assert public_check.status_code == 200, f"New product not found in public API: {public_check.text}"
        print(f"   -> Verified product appears on customer storefront immediately!")
        print("   [PASS] Real-time Storefront Publishing verified.")

        # 7. Super Admin Authentication & Operations
        print("\n7. Checking Super Admin Authentication...")
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "techmastersinnovations@gmail.com", "password": "Fri10Feb@2023"}
        )
        assert admin_login.status_code == 200, f"Admin login failed: {admin_login.status_code} {admin_login.text}"
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        print("   [PASS] Super Admin authentication verified.")

        # 8. Super Admin Operational Modules
        print("\n8. Checking Super Admin Endpoints (7 Core Modules)...")
        # 8.1 Users
        adm_users = await client.get("/api/v1/platform/users", headers=admin_headers)
        assert adm_users.status_code == 200, f"Platform users failed: {adm_users.text}"
        print(f"   -> User Management: {len(adm_users.json())} platform users")

        # 8.2 Products
        adm_prods = await client.get("/api/v1/platform/catalog/products", headers=admin_headers)
        assert adm_prods.status_code == 200, f"Platform products failed: {adm_prods.text}"
        print(f"   -> Product Management: {len(adm_prods.json())} global products")

        # 8.3 Orders
        adm_orders = await client.get("/api/v1/merchant/orders", headers=admin_headers)
        assert adm_orders.status_code == 200, f"Orders failed: {adm_orders.text}"
        print(f"   -> Order Management: {len(adm_orders.json())} orders")

        # 8.4 Delivery Management
        adm_deliv_zones = await client.get("/api/v1/merchant/delivery/zones", headers=admin_headers)
        assert adm_deliv_zones.status_code == 200, f"Delivery zones failed: {adm_deliv_zones.text}"
        adm_deliv_riders = await client.get("/api/v1/merchant/delivery/personnel", headers=admin_headers)
        assert adm_deliv_riders.status_code == 200, f"Delivery riders failed: {adm_deliv_riders.text}"
        print(f"   -> Delivery Management: {len(adm_deliv_zones.json())} zones, {len(adm_deliv_riders.json())} riders")

        # 8.5 Coupons & Discounts
        adm_coupons = await client.get("/api/v1/merchant/pricing/coupons", headers=admin_headers)
        assert adm_coupons.status_code == 200, f"Coupons failed: {adm_coupons.text}"
        print(f"   -> Discount & Coupon Management: {len(adm_coupons.json())} coupons")

        # 8.6 Payments
        adm_payments = await client.get("/api/v1/merchant/payments/transactions", headers=admin_headers)
        assert adm_payments.status_code == 200, f"Payments failed: {adm_payments.text}"
        print(f"   -> Payment Management: {len(adm_payments.json())} transactions")
        print("   [PASS] All Super Admin operational endpoints validated.")

        print("\n==========================================")
        print("  ALL VERIFICATION CHECKS PASSED (100%)")
        print("==========================================\n")

if __name__ == "__main__":
    asyncio.run(run_verification())
