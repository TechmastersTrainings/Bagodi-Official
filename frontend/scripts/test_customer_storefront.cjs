const puppeteer = require("puppeteer-core");
const path = require("path");

const CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const ARTIFACT_DIR = "/Users/sachin/.gemini/antigravity/brain/d7370da4-5291-4c6d-80c9-a1cbef243e3c";

async function runTest() {
  console.log("Launching headless Chrome for Bagodi Storefront browser verification...");
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });

    page.on("console", (msg) => console.log("BROWSER CONSOLE:", msg.text()));
    page.on("requestfailed", (req) => console.log("REQUEST FAILED:", req.url(), req.failure()));
    page.on("response", async (res) => {
      if (res.status() >= 400) {
        try {
          const text = await res.text();
          console.log(`HTTP ${res.status()} ${res.url()}: ${text}`);
        } catch {}
      }
    });

    console.log("Navigating to Bagodi Customer Web on http://localhost:5180...");
    await page.goto("http://localhost:5180", { waitUntil: "networkidle0", timeout: 15000 });

    // 1. Verify Brand and Header Elements
    const brandText = await page.$eval(".brand-logo", (el) => el.textContent.trim());
    console.log(`[PASS] Brand logo verified: "${brandText}"`);

    const noticeText = await page.$eval(".top-notice-bar", (el) => el.textContent.trim());
    console.log(`[PASS] Top notice bar: "${noticeText}"`);

    const locationText = await page.$eval(".location-badge", (el) => el.textContent.trim());
    console.log(`[PASS] Location badge: "${locationText}"`);

    // 2. Verify Search Bar and Category Nav
    const searchPlaceholder = await page.$eval(".search-input", (el) => el.getAttribute("placeholder"));
    console.log(`[PASS] Search bar active with placeholder: "${searchPlaceholder}"`);

    const allItemsPill = await page.$eval(".category-pill.active", (el) => el.textContent.trim());
    console.log(`[PASS] Active category pill: "${allItemsPill}"`);

    // 3. Verify Zero Dummy Data Policy Empty State
    const emptyStateTitle = await page.$eval(".empty-title", (el) => el.textContent.trim());
    console.log(`[PASS] Zero Dummy Data Empty State verified: "${emptyStateTitle}"`);

    // Capture Desktop Storefront Screenshot
    const desktopScreenshotPath = path.join(ARTIFACT_DIR, "storefront_desktop.png");
    await page.screenshot({ path: desktopScreenshotPath, fullPage: false });
    console.log(`[PASS] Desktop screenshot captured: ${desktopScreenshotPath}`);

    // 4. Test Customer Auth Modal Interaction
    console.log("Testing Customer Phone OTP Authentication interaction...");
    await page.click(".btn-header-auth");
    await page.waitForSelector(".modal-dialog", { timeout: 5000 });

    const modalTitle = await page.$eval(".modal-title", (el) => el.textContent.trim());
    console.log(`[PASS] Auth Modal opened with title: "${modalTitle}"`);

    // Enter Phone Number
    await page.type("#phone-input", "9876543210");
    const phoneVal = await page.$eval("#phone-input", (el) => el.value);
    console.log(`[PASS] Phone number entered: "+91 ${phoneVal}"`);

    // Capture Phone Step Screenshot
    const phoneModalPath = path.join(ARTIFACT_DIR, "auth_modal_phone.png");
    await page.screenshot({ path: phoneModalPath });
    console.log(`[PASS] Auth Phone modal screenshot captured: ${phoneModalPath}`);

    // Click "Send Verification Code"
    console.log("Submitting OTP request to live backend (/api/v1/auth/otp/send)...");
    await page.click(".btn-primary-action");

    // Wait for OTP Step
    await page.waitForSelector(".otp-inputs-row", { timeout: 8000 });
    const otpInputCount = await page.$$eval(".otp-digit-field", (els) => els.length);
    console.log(`[PASS] OTP verification step displayed with ${otpInputCount} single-digit inputs!`);

    // Capture OTP Step Screenshot
    const otpModalPath = path.join(ARTIFACT_DIR, "auth_modal_otp.png");
    await page.screenshot({ path: otpModalPath });
    console.log(`[PASS] Auth OTP modal screenshot captured: ${otpModalPath}`);

    // Close Modal
    await page.click(".modal-close-btn");
    await page.waitForFunction(() => !document.querySelector(".modal-backdrop"), { timeout: 3000 });
    console.log("[PASS] Auth modal closed cleanly.");

    // 5. Test Responsive Mobile Viewport (iPhone 375x812)
    console.log("Testing mobile-first responsive viewport (375x812)...");
    await page.setViewport({ width: 375, height: 812, isMobile: true, hasTouch: true });
    await page.waitForTimeout ? await page.waitForTimeout(400) : new Promise((r) => setTimeout(r, 400));

    const mobileScreenshotPath = path.join(ARTIFACT_DIR, "storefront_mobile.png");
    await page.screenshot({ path: mobileScreenshotPath, fullPage: false });
    console.log(`[PASS] Mobile responsive screenshot captured: ${mobileScreenshotPath}`);

    console.log("\n========================================================");
    console.log("ALL LIVE BROWSER INTEGRATION CHECKS PASSED SUCCESSFULLY!");
    console.log("========================================================");
  } finally {
    await browser.close();
  }
}

runTest().catch((err) => {
  console.error("Test failed with error:", err);
  process.exit(1);
});
