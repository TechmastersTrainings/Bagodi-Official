const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: "new",
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(`[${msg.type()}] ${msg.text()}`);
    }
  });
  page.on('pageerror', err => consoleErrors.push(`[PAGE ERROR] ${err.message}`));

  const wait = (ms) => new Promise(r => setTimeout(r, ms));

  console.log("1. Visiting Storefront PDP...");
  await page.goto('https://bagodi-store.vercel.app/product/classic-lenin-shirt-example', {
    waitUntil: 'networkidle2',
    timeout: 30000
  });

  await wait(2000);

  // Click "Add to Bag"
  console.log("2. Clicking Add to Bag...");
  const clickedAdd = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const btn = btns.find(b => b.innerText.includes('Add to Bag'));
    if (btn) {
      btn.click();
      return true;
    }
    return false;
  });
  console.log("Clicked Add to Bag:", clickedAdd);
  await wait(3000);

  // 3. Navigate to Cart Page
  console.log("3. Visiting Shopping Bag (/cart)...");
  await page.goto('https://bagodi-store.vercel.app/cart', {
    waitUntil: 'networkidle2',
    timeout: 30000
  });
  await wait(3000);

  const cartScreenshot = '/Users/sachin/.gemini/antigravity/brain/d7370da4-5291-4c6d-80c9-a1cbef243e3c/live_storefront_cart_page.png';
  await page.screenshot({ path: cartScreenshot, fullPage: false });
  console.log("Saved Cart Page screenshot to", cartScreenshot);

  // 4. Setup customer auth in localStorage to test Checkout Page
  console.log("4. Setting customer authentication for Checkout Page...");
  await page.evaluate(() => {
    localStorage.setItem('bagodi_auth_at', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy_customer');
    localStorage.setItem('bagodi_user_role', 'customer');
    localStorage.setItem('bagodi_auth_user', JSON.stringify({
      id: "99999999-9999-9999-9999-999999999999",
      email: "customer@bagodi.in",
      role: "customer",
      fullName: "Ananya Sharma",
      phone: "+919876543210"
    }));
  });

  // 5. Navigate to Checkout Page
  console.log("5. Visiting Checkout Page (/checkout)...");
  await page.goto('https://bagodi-store.vercel.app/checkout', {
    waitUntil: 'networkidle2',
    timeout: 30000
  });
  await wait(3000);

  const checkoutScreenshot = '/Users/sachin/.gemini/antigravity/brain/d7370da4-5291-4c6d-80c9-a1cbef243e3c/live_storefront_checkout_page.png';
  await page.screenshot({ path: checkoutScreenshot, fullPage: false });
  console.log("Saved Checkout Page screenshot to", checkoutScreenshot);

  console.log("Console errors detected during entire run:", consoleErrors);

  await browser.close();
})();

