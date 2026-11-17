import asyncio
import os
import sys
from decimal import Decimal
from uuid import UUID, uuid4

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import delete, select, text
from app.db.session import AsyncSessionLocal
from app.modules.catalog.models import Brand, Category, Product, ProductImage, ProductVariant
from app.modules.inventory.models import InventoryLedger, StockBalance
from app.modules.platform.models import Store, Tenant
from app.modules.identity.models import User

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
STORE_ID = UUID("22222222-2222-2222-2222-222222222222")

AUTHENTIC_CATALOG = [
    {
        "name": "Bagodi Royal Banarasi Katan Silk Saree",
        "slug": "bagodi-royal-banarasi-katan-silk-saree",
        "category_slug": "sarees",
        "brand_slug": "bagodi-atelier",
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
        "name": "Bagodi Kanjeevaram Crimson Bridal Silk Saree",
        "slug": "bagodi-kanjeevaram-crimson-bridal-silk-saree",
        "category_slug": "sarees",
        "brand_slug": "bagodi-atelier",
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
            {"size": "XXL", "stock": 3, "base_price": "28900.00", "mrp": "36000.00", "sku": "BGD-KNJ-XXL"},
        ],
    },
    {
        "name": "Raymond Executive Bespoke Navy Blazer",
        "slug": "raymond-executive-bespoke-navy-blazer",
        "category_slug": "blazers",
        "brand_slug": "raymond",
        "description": "Crafted from Raymond Super 120s pure Australian merino wool. Hand-canvassed construction with horn buttons, peak lapels, and double side vents for unmatched executive authority.",
        "images": [
            ("https://images.unsplash.com/photo-1594938298603-c8148c4dae35?auto=format&fit=crop&w=1200&q=85", "Raymond Executive Wool Blazer", True),
            ("https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=1200&q=85", "Peak Lapel and Fabric Weave", False),
        ],
        "variants": [
            {"size": "S", "stock": 7, "base_price": "14999.00", "mrp": "19999.00", "sku": "RYM-BLZ-S"},
            {"size": "M", "stock": 12, "base_price": "14999.00", "mrp": "19999.00", "sku": "RYM-BLZ-M"},
            {"size": "L", "stock": 14, "base_price": "14999.00", "mrp": "19999.00", "sku": "RYM-BLZ-L"},
            {"size": "XL", "stock": 8, "base_price": "14999.00", "mrp": "19999.00", "sku": "RYM-BLZ-XL"},
            {"size": "XXL", "stock": 4, "base_price": "14999.00", "mrp": "19999.00", "sku": "RYM-BLZ-XXL"},
        ],
    },
    {
        "name": "Park Avenue Royal Textured Formal Blazer",
        "slug": "park-avenue-royal-textured-formal-blazer",
        "category_slug": "blazers",
        "brand_slug": "park-avenue",
        "description": "Tailored fit slim blazer from Park Avenue in an aristocratic textured weave. Designed with stretch-comfort fabric, notch lapels, and patterned inner lining.",
        "images": [
            ("https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=1200&q=85", "Park Avenue Formal Blazer", True),
            ("https://images.unsplash.com/photo-1594938298603-c8148c4dae35?auto=format&fit=crop&w=1200&q=85", "Inner Lining and Lapel Detail", False),
        ],
        "variants": [
            {"size": "S", "stock": 6, "base_price": "11999.00", "mrp": "15999.00", "sku": "PA-BLZ-S"},
            {"size": "M", "stock": 10, "base_price": "11999.00", "mrp": "15999.00", "sku": "PA-BLZ-M"},
            {"size": "L", "stock": 12, "base_price": "11999.00", "mrp": "15999.00", "sku": "PA-BLZ-L"},
            {"size": "XL", "stock": 7, "base_price": "11999.00", "mrp": "15999.00", "sku": "PA-BLZ-XL"},
            {"size": "XXL", "stock": 3, "base_price": "11999.00", "mrp": "15999.00", "sku": "PA-BLZ-XXL"},
        ],
    },
    {
        "name": "Manyavar Royal Ivory Silk Sherwani Set",
        "slug": "manyavar-royal-ivory-silk-sherwani-set",
        "category_slug": "mens-wear",
        "brand_slug": "manyavar",
        "description": "Exquisite art silk ivory sherwani ensemble embellished with intricate zari embroidery and hand-set stone work. Comes complete with tailored churidar.",
        "images": [
            ("https://images.unsplash.com/photo-1597983073493-88cd35cf93b0?auto=format&fit=crop&w=1200&q=85", "Manyavar Ivory Silk Sherwani", True),
            ("https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?auto=format&fit=crop&w=1200&q=85", "Zari Collar and Cuffs Detail", False),
        ],
        "variants": [
            {"size": "S", "stock": 4, "base_price": "24999.00", "mrp": "32000.00", "sku": "MNY-SHR-S"},
            {"size": "M", "stock": 8, "base_price": "24999.00", "mrp": "32000.00", "sku": "MNY-SHR-M"},
            {"size": "L", "stock": 10, "base_price": "24999.00", "mrp": "32000.00", "sku": "MNY-SHR-L"},
            {"size": "XL", "stock": 6, "base_price": "24999.00", "mrp": "32000.00", "sku": "MNY-SHR-XL"},
            {"size": "XXL", "stock": 2, "base_price": "24999.00", "mrp": "32000.00", "sku": "MNY-SHR-XXL"},
        ],
    },
    {
        "name": "ColorPlus Premium Supima Cotton Casual Shirt",
        "slug": "colorplus-premium-supima-cotton-casual-shirt",
        "category_slug": "mens-wear",
        "brand_slug": "colorplus",
        "description": "Tailored from 100% long-staple American Supima cotton with garment enzyme wash for luxurious peach-finish softness. Ideal for smart-casual wear.",
        "images": [
            ("https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?auto=format&fit=crop&w=1200&q=85", "ColorPlus Supima Cotton Shirt", True),
            ("https://images.unsplash.com/photo-1620012253295-c15c429f66bf?auto=format&fit=crop&w=1200&q=85", "Fabric Weave and Collar Detail", False),
        ],
        "variants": [
            {"size": "S", "stock": 15, "base_price": "3499.00", "mrp": "4499.00", "sku": "CLP-SHT-S"},
            {"size": "M", "stock": 20, "base_price": "3499.00", "mrp": "4499.00", "sku": "CLP-SHT-M"},
            {"size": "L", "stock": 25, "base_price": "3499.00", "mrp": "4499.00", "sku": "CLP-SHT-L"},
            {"size": "XL", "stock": 18, "base_price": "3499.00", "mrp": "4499.00", "sku": "CLP-SHT-XL"},
            {"size": "XXL", "stock": 8, "base_price": "3499.00", "mrp": "4499.00", "sku": "CLP-SHT-XXL"},
        ],
    },
    {
        "name": "Parx Urban Printed Slim Cotton Shirt",
        "slug": "parx-urban-printed-slim-cotton-shirt",
        "category_slug": "mens-wear",
        "brand_slug": "parx",
        "description": "Energetic micro-geometric print shirt crafted from compact breathable cotton. Features a semi-cutaway collar, curved hem, and modern slim silhouette.",
        "images": [
            ("https://images.unsplash.com/photo-1596755094514-f87e34085b2c?auto=format&fit=crop&w=1200&q=85", "Parx Printed Casual Shirt", True),
        ],
        "variants": [
            {"size": "S", "stock": 10, "base_price": "2499.00", "mrp": "3299.00", "sku": "PRX-SHT-S"},
            {"size": "M", "stock": 15, "base_price": "2499.00", "mrp": "3299.00", "sku": "PRX-SHT-M"},
            {"size": "L", "stock": 18, "base_price": "2499.00", "mrp": "3299.00", "sku": "PRX-SHT-L"},
            {"size": "XL", "stock": 12, "base_price": "2499.00", "mrp": "3299.00", "sku": "PRX-SHT-XL"},
            {"size": "XXL", "stock": 6, "base_price": "2499.00", "mrp": "3299.00", "sku": "PRX-SHT-XXL"},
        ],
    },
    {
        "name": "Bagodi Designer Chanderi Silk Anarkali Set",
        "slug": "bagodi-designer-chanderi-silk-anarkali-set",
        "category_slug": "womens-wear",
        "brand_slug": "bagodi-atelier",
        "description": "Lustrous pure Chanderi silk floor-length Anarkali suit with golden gota-patti embroidery, accompanied by a hand-painted floral organza dupatta and churidar.",
        "images": [
            ("https://images.unsplash.com/photo-1609357605129-26f69add5d6e?auto=format&fit=crop&w=1200&q=85", "Chanderi Silk Anarkali Set", True),
            ("https://images.unsplash.com/photo-1610030469668-93510cb28052?auto=format&fit=crop&w=1200&q=85", "Gota Patti Yoke Embroidery Detail", False),
        ],
        "variants": [
            {"size": "S", "stock": 8, "base_price": "16499.00", "mrp": "21000.00", "sku": "BGD-ANK-S"},
            {"size": "M", "stock": 12, "base_price": "16499.00", "mrp": "21000.00", "sku": "BGD-ANK-M"},
            {"size": "L", "stock": 14, "base_price": "16499.00", "mrp": "21000.00", "sku": "BGD-ANK-L"},
            {"size": "XL", "stock": 9, "base_price": "16499.00", "mrp": "21000.00", "sku": "BGD-ANK-XL"},
            {"size": "XXL", "stock": 4, "base_price": "16499.00", "mrp": "21000.00", "sku": "BGD-ANK-XXL"},
        ],
    },
    {
        "name": "Manyavar Kids Royal Brocade Sherwani Set",
        "slug": "manyavar-kids-royal-brocade-sherwani-set",
        "category_slug": "kids-wear",
        "brand_slug": "manyavar",
        "description": "Celebration sherwani for boys featuring golden Benarasi brocade jacquard weave, mandarin collar with velvet piping, and soft cotton lining for all-day comfort.",
        "images": [
            ("https://images.unsplash.com/photo-1597983073493-88cd35cf93b0?auto=format&fit=crop&w=1200&q=85", "Kids Royal Brocade Sherwani", True),
        ],
        "variants": [
            {"size": "S", "stock": 10, "base_price": "5999.00", "mrp": "7999.00", "sku": "MNY-KID-S"},
            {"size": "M", "stock": 15, "base_price": "5999.00", "mrp": "7999.00", "sku": "MNY-KID-M"},
            {"size": "L", "stock": 12, "base_price": "5999.00", "mrp": "7999.00", "sku": "MNY-KID-L"},
            {"size": "XL", "stock": 8, "base_price": "5999.00", "mrp": "7999.00", "sku": "MNY-KID-XL"},
            {"size": "XXL", "stock": 5, "base_price": "5999.00", "mrp": "7999.00", "sku": "MNY-KID-XXL"},
        ],
    },
    {
        "name": "Bagodi Junior Festive Silk Lehenga Choli",
        "slug": "bagodi-junior-festive-silk-lehenga-choli",
        "category_slug": "kids-wear",
        "brand_slug": "bagodi-atelier",
        "description": "Traditional Deccan heritage silk lehenga choli for young girls with woven gold borders, lightweight net dupatta, and adjustable drawstring waist.",
        "images": [
            ("https://images.unsplash.com/photo-1610030469668-93510cb28052?auto=format&fit=crop&w=1200&q=85", "Junior Festive Silk Lehenga", True),
        ],
        "variants": [
            {"size": "S", "stock": 8, "base_price": "6499.00", "mrp": "8499.00", "sku": "BGD-LHG-S"},
            {"size": "M", "stock": 12, "base_price": "6499.00", "mrp": "8499.00", "sku": "BGD-LHG-M"},
            {"size": "L", "stock": 10, "base_price": "6499.00", "mrp": "8499.00", "sku": "BGD-LHG-L"},
            {"size": "XL", "stock": 6, "base_price": "6499.00", "mrp": "8499.00", "sku": "BGD-LHG-XL"},
            {"size": "XXL", "stock": 4, "base_price": "6499.00", "mrp": "8499.00", "sku": "BGD-LHG-XXL"},
        ],
    },
]


async def seed_clean_catalog():
    async with AsyncSessionLocal() as db:
        print("Cleaning previous product catalog and resetting to clean authentic items...")

        # 1. Purge previous products and related tables
        await db.execute(delete(InventoryLedger))
        await db.execute(delete(StockBalance))
        await db.execute(delete(ProductImage))
        await db.execute(delete(ProductVariant))
        await db.execute(delete(Product))
        await db.flush()

        # 2. Deactivate any non-standard categories so only the 5 required remain
        standard_slugs = ["mens-wear", "womens-wear", "kids-wear", "sarees", "blazers"]
        all_cats = (await db.execute(select(Category))).scalars().all()
        for cat in all_cats:
            if cat.slug not in standard_slugs:
                cat.is_active = False

        # Load standard categories and brands
        cats_by_slug = {
            c.slug: c.id
            for c in (await db.execute(select(Category).where(Category.slug.in_(standard_slugs)))).scalars().all()
        }
        brands_by_slug = {
            b.slug: b.id
            for b in (await db.execute(select(Brand))).scalars().all()
        }

        # 3. Seed authentic products
        for item in AUTHENTIC_CATALOG:
            cat_id = cats_by_slug.get(item["category_slug"])
            brand_id = brands_by_slug.get(item["brand_slug"])
            if not cat_id:
                print(f"Skipping {item['name']} - category {item['category_slug']} not found")
                continue

            product = Product(
                id=uuid4(),
                tenant_id=TENANT_ID,
                category_id=cat_id,
                brand_id=brand_id,
                name=item["name"],
                slug=item["slug"],
                description=item["description"],
                status="active",
                is_published=True,
            )
            db.add(product)
            await db.flush()

            # Add images
            for sort_idx, (img_url, alt, is_prim) in enumerate(item["images"]):
                img = ProductImage(
                    id=uuid4(),
                    tenant_id=TENANT_ID,
                    product_id=product.id,
                    url=img_url,
                    alt_text=alt,
                    sort_order=sort_idx,
                    is_primary=is_prim,
                )
                db.add(img)

            # Add variants with stock
            for v_data in item["variants"]:
                variant = ProductVariant(
                    id=uuid4(),
                    tenant_id=TENANT_ID,
                    product_id=product.id,
                    sku=v_data["sku"],
                    barcode=f"890{uuid4().int % 1000000000:09d}",
                    name=f"{product.name} - Size {v_data['size']}",
                    size=v_data["size"],
                    base_price=Decimal(v_data["base_price"]),
                    mrp=Decimal(v_data["mrp"]),
                    status="active",
                )
                db.add(variant)
                await db.flush()

                # Add stock balance
                balance = StockBalance(
                    id=uuid4(),
                    tenant_id=TENANT_ID,
                    store_id=STORE_ID,
                    variant_id=variant.id,
                    on_hand_qty=v_data["stock"],
                    available_qty=v_data["stock"],
                    reserved_qty=0,
                    in_transit_qty=0,
                )
                db.add(balance)

                # Add ledger entry
                ledger = InventoryLedger(
                    id=uuid4(),
                    tenant_id=TENANT_ID,
                    store_id=STORE_ID,
                    variant_id=variant.id,
                    movement_type="OPENING_STOCK",
                    from_account="EXTERNAL_SUPPLIER",
                    to_account="ON_HAND",
                    quantity=v_data["stock"],
                    on_hand_delta=v_data["stock"],
                    balance_after_on_hand=v_data["stock"],
                    balance_after_reserved=0,
                    balance_after_available=v_data["stock"],
                    reference_type="OPENING_STOCK",
                    reference_id=str(product.id),
                    notes="Authentic opening stock for Bagodi Flagship",
                )
                db.add(ledger)

            print(f"✓ Seeded: {product.name} ({item['category_slug']}) - 5 Sizes S/M/L/XL/XXL")

        await db.commit()
        print("✓ All authentic catalog items successfully seeded in PostgreSQL!")


if __name__ == "__main__":
    asyncio.run(seed_clean_catalog())
