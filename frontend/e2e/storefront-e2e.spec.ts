import { expect, test } from "@playwright/test";

const API_URL = "http://127.0.0.1:8000/api/v1";
const MERCHANT_URL = "http://127.0.0.1:3001";

const MERCHANT_EMAIL = "merchant@bagodi.in";
const MERCHANT_PASSWORD = process.env.INITIAL_ADMIN_PASSWORD || "Fri10Feb@2023";

interface SeededE2EProduct {
  id: string;
  name: string;
  slug: string;
  merchantToken: string;
}

async function provisionE2EProduct(): Promise<SeededE2EProduct> {
  const loginRes = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: MERCHANT_EMAIL, password: MERCHANT_PASSWORD }),
  });
  if (!loginRes.ok) {
    throw new Error(`Merchant API login failed (${loginRes.status}): ${await loginRes.text()}`);
  }
  const loginData = await loginRes.json();
  const merchantToken: string = loginData.tokens?.accessToken || loginData.access_token;

  const [catsRes, brandsRes] = await Promise.all([
    fetch(`${API_URL}/categories`),
    fetch(`${API_URL}/brands`),
  ]);
  const categories = await catsRes.json();
  const brands = await brandsRes.json();
  const categoryId = categories[0]?.id;
  const brandId = brands[0]?.id;
  if (!categoryId) {
    throw new Error("Expected at least one seeded category from /api/v1/categories");
  }

  const uniqueSuffix = Date.now().toString().slice(-6);
  const name = `E2E Heritage Bandhgala ${uniqueSuffix}`;
  const slug = `e2e-heritage-bandhgala-${uniqueSuffix}`;
  const createRes = await fetch(`${API_URL}/merchant/catalog/products`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${merchantToken}`,
    },
    body: JSON.stringify({
      name,
      slug,
      description: "Playwright automated verification heritage bandhgala suiting piece.",
      categoryId,
      brandId,
      basePrice: 4480,
      status: "active",
      isPublished: true,
      variants: [
        {
          sku: `E2E-SKU-${uniqueSuffix}`,
          size: "M",
          colorName: "Royal Emerald",
          mrp: 5999,
          sellingPrice: 4480,
          initialStock: 10,
        },
      ],
      images: [
        {
          url: "https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=1200&q=85",
          altText: name,
          displayOrder: 0,
          isPrimary: true,
        },
      ],
    }),
  });
  if (!createRes.ok) {
    throw new Error(`E2E product creation failed (${createRes.status}): ${await createRes.text()}`);
  }
  const created = await createRes.json();
  return {
    id: created.id,
    name: created.name,
    slug: created.slug || slug,
    merchantToken,
  };
}

test.describe("Bagodi E-Commerce Production E2E Journey", () => {
  let e2eProduct: SeededE2EProduct;
  let placedOrderNumber = "";

  test.beforeAll(async () => {
    e2eProduct = await provisionE2EProduct();
  });

  test.afterAll(async () => {
    if (!e2eProduct?.id || !e2eProduct?.merchantToken) return;
    await fetch(`${API_URL}/merchant/catalog/products/${e2eProduct.id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${e2eProduct.merchantToken}`,
      },
      body: JSON.stringify({ status: "archived", isPublished: false }),
    }).catch(() => {});
  });

  test("Desktop 1440x900: Storefront -> OTP Login -> Wishlist -> Bag -> COD Checkout -> Orders Cancel -> Merchant Order Visibility", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("pageerror", (err) => consoleErrors.push(err.message));

    await page.setViewportSize({ width: 1440, height: 900 });

    // 1. Storefront home & compact legal footer check
    await page.goto("/");
    await expect(page.getByText(/BAGODI/i).first()).toBeVisible();
    await expect(page.getByText(/TechMasters Innovations Private Limited/i).first()).toBeVisible();

    // 2. Contact directory page
    await page.goto("/contact");
    await expect(page.getByRole("heading", { name: /Contact Us & Store Directory/i })).toBeVisible();
    await expect(page.getByText(/Customer Helpline: \+91 99720 00805/)).toBeVisible();

    // 3. Customer OTP Login with console devOtp
    const uniqueMobile = `98765${String(Date.now()).slice(-5)}`;
    await page.goto("/login");
    await page.getByPlaceholder(/Enter 10-digit mobile or email address/i).fill(uniqueMobile);
    await page.getByRole("button", { name: /Send Verification Code/i }).click();

    const otpStrong = page.locator("strong").filter({ hasText: /^\d{6}$/ }).first();
    await expect(otpStrong).toBeVisible();
    const otpCode = ((await otpStrong.textContent()) || "123456").trim();
    for (let i = 0; i < 6; i++) {
      await page.getByLabel(`Digit ${i + 1}`).fill(otpCode[i] || "1");
    }
    await page.getByRole("button", { name: /Verify & Access Account/i }).click();
    await expect(page).not.toHaveURL(/\/login$/);

    // 4. Product detail -> Wishlist persist -> Move to Bag
    await page.goto(`/product/${e2eProduct.slug}`);
    await expect(page.getByText(e2eProduct.name).first()).toBeVisible();
    await page.getByRole("button", { name: "Save to Wishlist" }).click();
    await expect(page.getByRole("link", { name: /Wishlist/i })).toContainText("1");

    await page.goto("/account/wishlist");
    await expect(page.getByText(e2eProduct.name).first()).toBeVisible();
    await page.getByRole("button", { name: /Move to Bag/i }).click();
    await expect(page.getByText(/Your Wishlist is Empty/i)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("link", { name: /Shopping Bag/i })).toContainText("1");

    // 5. Cart -> Checkout -> Save Address -> Place COD Order
    await page.goto("/cart");
    await expect(page.getByText(e2eProduct.name).first()).toBeVisible();
    await page.getByText(/Proceed to Checkout/i).click();
    await expect(page).toHaveURL(/\/checkout/);
    await expect(page.getByRole("heading", { name: /Checkout & Order Review/i })).toBeVisible();

    const fullNameInput = page.getByPlaceholder(/Sachin Anil/i);
    if (await fullNameInput.isVisible()) {
      await fullNameInput.fill("E2E Royal Customer");
      await page.getByPlaceholder(/10-digit mobile/i).fill(uniqueMobile);
      await page.getByPlaceholder(/House \/ Flat \/ Street Name/i).fill("42 Royal Fort Avenue");
      await page.getByPlaceholder("Bidar").fill("Bidar");
      await page.getByPlaceholder("Karnataka").fill("Karnataka");
      await page.getByPlaceholder("585401").fill("585401");
      await page.getByRole("button", { name: /Save & Deliver Here/i }).click();
      await expect(page.locator("main").getByText(/42 Royal Fort Avenue/i)).toBeVisible();
    }

    await page.getByText("Cash on Delivery (COD)").click();
    await page.getByRole("button", { name: /Confirm & Place Order/i }).click();
    await expect(page).toHaveURL(/\/order-success\//, { timeout: 20_000 });

    // 6. My Orders -> Verify GST Invoice + Self-Service Cancel
    await page.goto("/account/orders");
    const firstOrderHeader = page.getByText(/Order #/i).first();
    await expect(firstOrderHeader).toBeVisible();
    const orderText = (await firstOrderHeader.textContent()) || "";
    placedOrderNumber = orderText.replace(/Order #/i, "").trim();
    expect(placedOrderNumber.length).toBeGreaterThan(4);

    await expect(page.getByRole("button", { name: /GST Invoice/i }).first()).toBeVisible();
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: /Cancel Order/i }).first().click();
    await expect(page.getByText(/CANCELLED/i).first()).toBeVisible();

    // 7. Merchant Operations Portal sees the live placed order
    await page.goto(`${MERCHANT_URL}/login`);
    await page.getByPlaceholder("staff@bagodi.in").fill(MERCHANT_EMAIL);
    await page.getByPlaceholder("Enter your store password").fill(MERCHANT_PASSWORD);
    await page.getByRole("button", { name: /Sign In to Command Center/i }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    await page.goto(`${MERCHANT_URL}/orders`);
    await expect(page.getByText(placedOrderNumber).first()).toBeVisible({ timeout: 15_000 });

    expect(consoleErrors).toEqual([]);
  });

  test("Mobile 390x844: Storefront responsive viewport has zero horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    await expect(page.getByText(/TechMasters Innovations Private Limited/i)).toBeVisible();

    const overflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth - document.documentElement.clientWidth;
    });
    expect(overflow).toBeLessThanOrEqual(2);
  });

  test("Security Boundaries: Unauthenticated API and Merchant Portal access denied", async ({ page }) => {
    const apiRes = await fetch(`${API_URL}/wishlist`);
    expect(apiRes.status).toBe(401);

    await page.goto(`${MERCHANT_URL}/orders`);
    await expect(page).toHaveURL(/\/login/);
  });
});
