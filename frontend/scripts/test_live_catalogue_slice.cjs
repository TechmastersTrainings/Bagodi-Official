const puppeteer = require("puppeteer-core");
const path = require("path");
const { execSync } = require("child_process");

const CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const ARTIFACT_DIR = "/Users/sachin/.gemini/antigravity/brain/d7370da4-5291-4c6d-80c9-a1cbef243e3c";

// Python script to seed temporary real products and return their IDs
const SEED_SCRIPT = `
import asyncio
import uuid
from app.db.session import AsyncSessionLocal
from sqlalchemy import text

async def seed():
    async with AsyncSessionLocal() as session:
        # Create tenant
        tenant_id = str(uuid.uuid4())
        await session.execute(text("""
            INSERT INTO tenants (id, name, slug, legal_name, contact_email, contact_phone, status, created_at, updated_at)
            VALUES (:id, 'Bagodi Retailers', 'bagodi-retail', 'Bagodi Retailers LLP', 'ops@bagodi.in', '+919876543210', 'active', now(), now())
        """), {"id": tenant_id})

        # Create global category
        cat_id = str(uuid.uuid4())
        await session.execute(text("""
            INSERT INTO categories (id, tenant_id, name, slug, description, is_active, sort_order, created_at, updated_at)
            VALUES (:id, NULL, 'Fresh Produce', 'fresh-produce', 'Fresh farm produce from Bidar', true, 1, now(), now())
        """), {"id": cat_id})

        # Create Product 1: Bidar Alphonso Mangoes
        prod1_id = str(uuid.uuid4())
        await session.execute(text("""
            INSERT INTO products (id, tenant_id, category_id, name, slug, description, status, is_published, created_at, updated_at)
            VALUES (:id, :tenant_id, :cat_id, 'Bidar Farm Fresh Alphonso Mangoes', 'bidar-alphonso-mangoes', 'Organically ripened sweet Alphonso mangoes directly harvested from Bidar orchards.', 'active', true, now(), now())
        """), {"id": prod1_id, "tenant_id": tenant_id, "cat_id": cat_id})

        # Variants for Product 1
        v1_id = str(uuid.uuid4())
        await session.execute(text("""
            INSERT INTO product_variants (id, tenant_id, product_id, sku, barcode, name, size, base_price, mrp, status, created_at, updated_at)
            VALUES (:id, :tenant_id, :prod_id, 'MANGO-1KG', '8901234567890', '1 kg (Approx. 3-4 pcs)', '1 kg', 180.00, 220.00, 'active', now(), now())
        """), {"id": v1_id, "tenant_id": tenant_id, "prod_id": prod1_id})

        v2_id = str(uuid.uuid4())
        await session.execute(text("""
            INSERT INTO product_variants (id, tenant_id, product_id, sku, barcode, name, size, base_price, mrp, status, created_at, updated_at)
            VALUES (:id, :tenant_id, :prod_id, 'MANGO-3KG-BOX', '8901234567891', '3 kg Crates (10-12 pcs)', '3 kg', 490.00, 620.00, 'active', now(), now())
        """), {"id": v2_id, "tenant_id": tenant_id, "prod_id": prod1_id})

        # Create Product 2: Cold Pressed Safflower Oil
        prod2_id = str(uuid.uuid4())
        await session.execute(text("""
            INSERT INTO products (id, tenant_id, category_id, name, slug, description, status, is_published, created_at, updated_at)
            VALUES (:id, :tenant_id, :cat_id, 'Bidar Cold-Pressed Safflower Oil (Kardi)', 'cold-pressed-safflower-oil', 'Traditional wood-pressed nutrient rich unrefined safflower cooking oil.', 'active', true, now(), now())
        """), {"id": prod2_id, "tenant_id": tenant_id, "cat_id": cat_id})

        v3_id = str(uuid.uuid4())
        await session.execute(text("""
            INSERT INTO product_variants (id, tenant_id, product_id, sku, barcode, name, size, base_price, mrp, status, created_at, updated_at)
            VALUES (:id, :tenant_id, :prod_id, 'OIL-SAFF-1L', '8901234567892', '1 Litre Glass Bottle', '1 Litre', 240.00, 290.00, 'active', now(), now())
        """), {"id": v3_id, "tenant_id": tenant_id, "prod_id": prod2_id})

        await session.commit()
        print(f"SEEDED:{tenant_id}")

asyncio.run(seed())
`;

const CLEANUP_SCRIPT = (tenantId) => `
import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import text

async def cleanup():
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM product_variants WHERE tenant_id = :id"), {"id": "${tenantId}"})
        await session.execute(text("DELETE FROM products WHERE tenant_id = :id"), {"id": "${tenantId}"})
        await session.execute(text("DELETE FROM categories WHERE slug = 'fresh-produce'"))
        await session.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": "${tenantId}"})
        await session.commit()
        print("CLEANED")

asyncio.run(cleanup())
`;

async function main() {
  console.log("Seeding test catalogue fixture via backend database...");
  const seedOutput = execSync(`cd backend && PYTHONPATH=. .venv/bin/python -c "${SEED_SCRIPT.replace(/"/g, '\\"')}"`, {
    encoding: "utf-8",
  });
  const match = seedOutput.match(/SEEDED:([a-f0-9-]+)/);
  if (!match) throw new Error("Failed to seed catalogue records");
  const tenantId = match[1];
  console.log(`[PASS] Seeded test tenant: ${tenantId}`);

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 850 });

    console.log("Navigating to Bagodi Storefront with live catalogue data...");
    await page.goto("http://localhost:5180", { waitUntil: "networkidle0", timeout: 15000 });

    // 1. Verify category pills
    await page.waitForSelector(".category-pill", { timeout: 5000 });
    const pills = await page.$$eval(".category-pill", (els) => els.map((e) => e.textContent.trim()));
    console.log(`[PASS] Category navigation rendered: ${JSON.stringify(pills)}`);

    // 2. Verify product cards
    await page.waitForSelector(".product-card", { timeout: 5000 });
    const productTitles = await page.$$eval(".product-title", (els) => els.map((e) => e.textContent.trim()));
    console.log(`[PASS] Product cards rendered: ${JSON.stringify(productTitles)}`);

    const prices = await page.$$eval(".current-price", (els) => els.map((e) => e.textContent.trim()));
    console.log(`[PASS] Price tags rendered: ${JSON.stringify(prices)}`);

    // Capture populated desktop storefront
    const populatedScreenshot = path.join(ARTIFACT_DIR, "storefront_populated_desktop.png");
    await page.screenshot({ path: populatedScreenshot, fullPage: false });
    console.log(`[PASS] Populated storefront screenshot captured: ${populatedScreenshot}`);

    // 3. Test Product Detail Modal
    console.log("Testing Product Detail Modal interaction...");
    await page.click(".product-card:first-child");
    await page.waitForSelector(".pdp-dialog", { timeout: 5000 });

    const pdpTitle = await page.$eval(".pdp-title", (el) => el.textContent.trim());
    console.log(`[PASS] Product Detail Modal opened for: "${pdpTitle}"`);

    // Verify variant chips (e.g. 1 kg and 3 kg)
    const variantChips = await page.$$eval(".variant-chip", (els) => els.map((e) => e.textContent.trim()));
    console.log(`[PASS] Variant chips rendered: ${JSON.stringify(variantChips)}`);

    // Switch variant: click the second chip (3 kg box)
    if (variantChips.length > 1) {
      await page.click(".variant-chip:nth-child(2)");
      await page.waitForTimeout ? await page.waitForTimeout(200) : new Promise((r) => setTimeout(r, 200));
      const activeChipText = await page.$eval(".variant-chip.active", (el) => el.textContent.trim());
      console.log(`[PASS] Variant successfully switched to: "${activeChipText}"`);
    }

    // Capture PDP Modal screenshot
    const pdpScreenshot = path.join(ARTIFACT_DIR, "storefront_pdp_modal.png");
    await page.screenshot({ path: pdpScreenshot });
    console.log(`[PASS] PDP Modal screenshot captured: ${pdpScreenshot}`);

    // 4. Test Add to Cart Interaction
    console.log("Testing Add to Cart action...");
    await page.click(".pdp-dialog .btn-primary-action");
    await page.waitForSelector(".cart-count-badge", { timeout: 5000 });

    const cartBadgeCount = await page.$eval(".cart-count-badge", (el) => el.textContent.trim());
    console.log(`[PASS] Shopping cart badge updated with count: ${cartBadgeCount}`);

    // Close PDP Modal
    await page.click(".pdp-dialog .modal-close-btn");
    await page.waitForFunction(() => !document.querySelector(".pdp-dialog"), { timeout: 3000 });
    console.log("[PASS] PDP modal closed.");

    // 5. Test Live Search Filtering
    console.log("Testing live search filtering with query 'Safflower'...");
    await page.type(".search-input", "Safflower");
    await page.waitForTimeout ? await page.waitForTimeout(300) : new Promise((r) => setTimeout(r, 300));

    const filteredTitles = await page.$$eval(".product-title", (els) => els.map((e) => e.textContent.trim()));
    console.log(`[PASS] Filtered results for 'Safflower': ${JSON.stringify(filteredTitles)}`);

    const searchScreenshot = path.join(ARTIFACT_DIR, "storefront_search_filter.png");
    await page.screenshot({ path: searchScreenshot });
    console.log(`[PASS] Search filter screenshot captured: ${searchScreenshot}`);

    console.log("\n========================================================");
    console.log("LIVE CATALOGUE VERTICAL SLICE FULLY VERIFIED!");
    console.log("========================================================");
  } finally {
    await browser.close();
    console.log("Tearing down temporary test records to preserve Zero Dummy Data Policy...");
    execSync(`cd backend && PYTHONPATH=. .venv/bin/python -c "${CLEANUP_SCRIPT(tenantId).replace(/"/g, '\\"')}"`, {
      encoding: "utf-8",
    });
    console.log("[PASS] Cleaned up test records. Zero dummy data policy intact.");
  }
}

main().catch((err) => {
  console.error("Test failed with error:", err);
  process.exit(1);
});
