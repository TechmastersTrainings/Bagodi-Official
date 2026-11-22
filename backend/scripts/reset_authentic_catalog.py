import asyncio
import os
import sys
from decimal import Decimal
from uuid import UUID, uuid4

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import delete, select, text
from app.db.session import AsyncSessionLocal
from app.modules.catalog.models import Category, Product, ProductImage, ProductVariant
from app.modules.inventory.models import InventoryLedger, StockBalance
from app.modules.orders.models import Order, OrderItem, PaymentTransaction
from app.modules.platform.models import Store, Tenant
from app.modules.identity.models import User

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
STORE_ID = UUID("22222222-2222-2222-2222-222222222222")

AUTHENTIC_PRODUCTS = [
    {
        "name": "Bagodi Royal Banarasi Katan Silk Saree",
        "slug": "bagodi-royal-banarasi-katan-silk-saree",
        "category_slug": "silks-sarees",
        "description": "Authentic handloom Banarasi Katan silk saree woven with antique gold zari kadwa motifs and regal meenakari floral pallu. Handcrafted in the heritage tradition of royal Deccan ateliers.",
        "images": [
            ("https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=1200&q=85", "Royal Banarasi Silk Saree Drape", True),
            ("https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?auto=format&fit=crop&w=1200&q=85", "Intricate Zari Kadwa Pallu Close-up", False),
        ],
        "variants": [
            {"size": "S", "stock": 8, "base_price": "18499.00", "mrp": "24999.00", "sku": "BGD-BSK-S"},
            {"size": "M", "stock": 12, "base_price": "18499.00", "mrp": "24999.00", "sku": "BGD-BSK-M"},
            {"size": "L", "stock": 15, "base_price": "18499.00", "mrp": "24999.00", "sku": "BGD-BSK-L"},
            {"size": "XL", "stock": 10, "base_price": "18499.00", "mrp": "24999.00", "sku": "BGD-BSK-XL"},
            {"size": "XXL", "stock": 6, "base_price": "18499.00", "mrp": "24999.00", "sku": "BGD-BSK-XXL"},
        ],
    },
    {
        "name": "Bidar Heritage Zari Embroidered Silk Sherwani",
        "slug": "bidar-heritage-zari-embroidered-silk-sherwani",
        "category_slug": "festive-wedding",
        "description": "Regal raw silk ivory sherwani embellished with antique Bidri-inspired floral dabka, French knot zardozi, and hand-stitched metallic borders. Finished with bespoke mother-of-pearl buttons.",
        "images": [
            ("https://images.unsplash.com/photo-1597983073493-88cd35cf93b0?auto=format&fit=crop&w=1200&q=85", "Heritage Zari Sherwani Front View", True),
            ("https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?auto=format&fit=crop&w=1200&q=85", "Bidri Craftsmanship Embroidery", False),
        ],
        "variants": [
            {"size": "S", "stock": 4, "base_price": "32500.00", "mrp": "42000.00", "sku": "BGD-SHR-S"},
            {"size": "M", "stock": 8, "base_price": "32500.00", "mrp": "42000.00", "sku": "BGD-SHR-M"},
            {"size": "L", "stock": 10, "base_price": "32500.00", "mrp": "42000.00", "sku": "BGD-SHR-L"},
            {"size": "XL", "stock": 6, "base_price": "32500.00", "mrp": "42000.00", "sku": "BGD-SHR-XL"},
            {"size": "XXL", "stock": 3, "base_price": "32500.00", "mrp": "42000.00", "sku": "BGD-SHR-XXL"},
        ],
    },
    {
        "name": "Bidar Chanderi Zari Silk Kurta & Dupatta Set",
        "slug": "bidar-chanderi-zari-silk-kurta-set",
        "category_slug": "designer-kurtas",
        "description": "Lustrous sheer Chanderi silk kurta with delicate golden coin bootas, paired with hand-dyed organza scalloped dupatta and tailored silk trousers. Designed for festive celebrations.",
        "images": [
            ("https://images.unsplash.com/photo-1609357605129-26f69add5d6e?auto=format&fit=crop&w=1200&q=85", "Chanderi Silk Kurta Ensemble", True),
            ("https://images.unsplash.com/photo-1610030469668-93510cb28052?auto=format&fit=crop&w=1200&q=85", "Organza Dupatta and Neckline Detail", False),
        ],
        "variants": [
            {"size": "S", "stock": 10, "base_price": "12999.00", "mrp": "16500.00", "sku": "BGD-KRT-S"},
            {"size": "M", "stock": 14, "base_price": "12999.00", "mrp": "16500.00", "sku": "BGD-KRT-M"},
            {"size": "L", "stock": 12, "base_price": "12999.00", "mrp": "16500.00", "sku": "BGD-KRT-L"},
            {"size": "XL", "stock": 8, "base_price": "12999.00", "mrp": "16500.00", "sku": "BGD-KRT-XL"},
            {"size": "XXL", "stock": 4, "base_price": "12999.00", "mrp": "16500.00", "sku": "BGD-KRT-XXL"},
        ],
    },
    {
        "name": "Kanjeevaram Crimson Bridal Silk Saree",
        "slug": "kanjeevaram-crimson-bridal-silk-saree",
        "category_slug": "silks-sarees",
        "description": "Heirloom pure mulberry silk saree woven with three-ply silk yarn and 24-karat pure silver dipped gold zari temple borders. Provenance: Flagship Bidar Atelier.",
        "images": [
            ("https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?auto=format&fit=crop&w=1200&q=85", "Crimson Bridal Kanjeevaram Silk", True),
            ("https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=1200&q=85", "Temple Zari Border Detail", False),
        ],
        "variants": [
            {"size": "S", "stock": 5, "base_price": "28900.00", "mrp": "36000.00", "sku": "BGD-KNJ-S"},
            {"size": "M", "stock": 8, "base_price": "28900.00", "mrp": "36000.00", "sku": "BGD-KNJ-M"},
            {"size": "L", "stock": 10, "base_price": "28900.00", "mrp": "36000.00", "sku": "BGD-KNJ-L"},
            {"size": "XL", "stock": 6, "base_price": "28900.00", "mrp": "36000.00", "sku": "BGD-KNJ-XL"},
            {"size": "XXL", "stock": 2, "base_price": "28900.00", "mrp": "36000.00", "sku": "BGD-KNJ-XXL"},
        ],
    },
    {
        "name": "Bespoke Tailored Egyptian Giza Cotton Kurta",
        "slug": "bespoke-tailored-egyptian-giza-cotton-kurta",
        "category_slug": "mens-tailoring",
        "description": "Tailored from 120s two-ply certified Egyptian Giza long-staple cotton with mother-of-pearl buttons and hand-rolled French seams. Unmatched breathability and drape for Bidar summers.",
        "images": [
            ("https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?auto=format&fit=crop&w=1200&q=85", "Egyptian Giza Cotton Kurta", True),
            ("https://images.unsplash.com/photo-1620012253295-c15c429f66bf?auto=format&fit=crop&w=1200&q=85", "Collar and Cuff Tailoring", False),
        ],
        "variants": [
            {"size": "S", "stock": 15, "base_price": "5499.00", "mrp": "7200.00", "sku": "BGD-GIZ-S"},
            {"size": "M", "stock": 20, "base_price": "5499.00", "mrp": "7200.00", "sku": "BGD-GIZ-M"},
            {"size": "L", "stock": 25, "base_price": "5499.00", "mrp": "7200.00", "sku": "BGD-GIZ-L"},
            {"size": "XL", "stock": 18, "base_price": "5499.00", "mrp": "7200.00", "sku": "BGD-GIZ-XL"},
            {"size": "XXL", "stock": 10, "base_price": "5499.00", "mrp": "7200.00", "sku": "BGD-GIZ-XXL"},
        ],
    },
    {
        "name": "Pure European Linen Bandhgala Nehru Jacket",
        "slug": "pure-european-linen-bandhgala-nehru-jacket",
        "category_slug": "linen-classics",
        "description": "Structured handcrafted waistcoat tailored from 100% natural Normandy flax linen with horn buttons, dual vents, and breathable Bemberg silk lining.",
        "images": [
            ("https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=1200&q=85", "Linen Bandhgala Jacket", True),
            ("https://images.unsplash.com/photo-1594938298603-c8148c4dae35?auto=format&fit=crop&w=1200&q=85", "Flax Linen Texture and Pocket Detail", False),
        ],
        "variants": [
            {"size": "S", "stock": 6, "base_price": "8999.00", "mrp": "11500.00", "sku": "BGD-LNN-S"},
            {"size": "M", "stock": 10, "base_price": "8999.00", "mrp": "11500.00", "sku": "BGD-LNN-M"},
            {"size": "L", "stock": 12, "base_price": "8999.00", "mrp": "11500.00", "sku": "BGD-LNN-L"},
            {"size": "XL", "stock": 8, "base_price": "8999.00", "mrp": "11500.00", "sku": "BGD-LNN-XL"},
            {"size": "XXL", "stock": 4, "base_price": "8999.00", "mrp": "11500.00", "sku": "BGD-LNN-XXL"},
        ],
    },
]


async def reset_catalog():
    async with AsyncSessionLocal() as db:
        print("🧹 Cleaning up synthetic/dummy products and test artifacts from database...")

        # 1. Clean up cart items and test orders/shipments that reference old variants
        await db.execute(text("DELETE FROM cart_items"))
        await db.execute(text("DELETE FROM shipment_items"))
        await db.execute(text("DELETE FROM order_return_requests"))
        await db.execute(text("DELETE FROM order_status_history"))
        await db.execute(text("DELETE FROM order_items"))
        await db.execute(text("DELETE FROM payment_transactions"))
        await db.execute(text("DELETE FROM orders"))
        await db.execute(text("DELETE FROM inventory_ledger"))
        await db.execute(text("DELETE FROM stock_balances"))
        await db.execute(text("DELETE FROM product_images"))
        await db.execute(text("DELETE FROM product_variants"))
        await db.execute(text("DELETE FROM products"))

        # Clean up test user accounts (keep only authentic platform and store users)
        await db.execute(
            text(
                "DELETE FROM users WHERE is_platform_user IS NOT TRUE AND email NOT LIKE '%bagodi.in'"
            )
        )
        await db.flush()
        print("  ✓ Removed test records, cart items, order items, and temporary test users")

        # 2. Verify categories
        categories = {}
        for cat_data in [
            ("Handloom Silks & Sarees", "silks-sarees", "Pure Banarasi, Kanjeevaram & Tussar silk sarees with antique zari borders", 1),
            ("Designer Kurtas & Sets", "designer-kurtas", "Handcrafted Anarkali sets, straight kurtis, dupattas & festive wear", 2),
            ("Men's Tailoring & Shirts", "mens-tailoring", "Bespoke Egyptian Giza cotton shirts, linen trousers & formal tailoring", 3),
            ("Festive & Wedding Edit", "festive-wedding", "Royal sherwanis, bandhgalas, bridal silks & ceremonial attire", 4),
            ("Indo-Western & Pret", "indo-western", "Contemporary fusion dresses, coord sets, wrap tops & modern silhouettes", 5),
            ("Pure Linen Classics", "linen-classics", "Breathable European certified pure linen Nehru jackets, kurtas & trousers", 6),
        ]:
            name, slug, desc, order = cat_data
            stmt = select(Category).where(Category.slug == slug)
            cat = (await db.execute(stmt)).scalar_one_or_none()
            if not cat:
                cat = Category(
                    tenant_id=TENANT_ID,
                    name=name,
                    slug=slug,
                    description=desc,
                    sort_order=order,
                    is_active=True,
                )
                db.add(cat)
                await db.flush()
            categories[slug] = cat

        # 3. Insert Authentic Luxury Products
        print("✨ Seeding authentic Bagodi Haute Couture catalogue with high-res photography...")
        for pdata in AUTHENTIC_PRODUCTS:
            category = categories.get(pdata["category_slug"])
            product = Product(
                tenant_id=TENANT_ID,
                category_id=category.id if category else None,
                name=pdata["name"],
                slug=pdata["slug"],
                description=pdata["description"],
                status="active",
                is_published=True,
            )
            db.add(product)
            await db.flush()

            # Add high-resolution images
            for sort_idx, (img_url, alt, is_pri) in enumerate(pdata["images"], 1):
                img = ProductImage(
                    tenant_id=TENANT_ID,
                    product_id=product.id,
                    url=img_url,
                    alt_text=alt,
                    is_primary=is_pri,
                    sort_order=sort_idx,
                )
                db.add(img)

            # Add size variants with individual inventory and automatic SKUs
            for vdata in pdata["variants"]:
                variant = ProductVariant(
                    tenant_id=TENANT_ID,
                    product_id=product.id,
                    sku=vdata["sku"],
                    name=f"{product.name} — Size {vdata['size']}",
                    size=vdata["size"],
                    color="Heritage Gold / Raw Silk",
                    base_price=Decimal(vdata["base_price"]),
                    mrp=Decimal(vdata["mrp"]),
                    status="active",
                )
                db.add(variant)
                await db.flush()

                # Add Stock Balance
                stock = StockBalance(
                    tenant_id=TENANT_ID,
                    store_id=STORE_ID,
                    variant_id=variant.id,
                    on_hand_qty=vdata["stock"],
                    reserved_qty=0,
                    available_qty=vdata["stock"],
                    in_transit_qty=0,
                    reorder_threshold=2,
                    low_stock_alert=False,
                )
                db.add(stock)

                # Add Ledger Entry
                ledger = InventoryLedger(
                    tenant_id=TENANT_ID,
                    store_id=STORE_ID,
                    variant_id=variant.id,
                    movement_type="INWARD_PURCHASE",
                    from_account="SUPPLIER",
                    to_account="ON_HAND",
                    quantity=vdata["stock"],
                    on_hand_delta=vdata["stock"],
                    reserved_delta=0,
                    in_transit_delta=0,
                    balance_after_on_hand=vdata["stock"],
                    balance_after_reserved=0,
                    balance_after_available=vdata["stock"],
                    reference_type="CATALOG_INIT",
                    notes="Authentic boutique inventory opening balance",
                    idempotency_key=str(uuid4()),
                )
                db.add(ledger)

            print(f"  ✓ Seeded: {pdata['name']} (5 sizes S-XXL, {len(pdata['images'])} images)")

        await db.commit()
        print("\n🎉 Authentic Bagodi Catalogue Reset Complete!")
        print("  • 0 dummy or mock products remaining.")
        print("  • 6 high-end luxury couture items with high-res fashion photography and size-wise inventory active.")


if __name__ == "__main__":
    asyncio.run(reset_catalog())
