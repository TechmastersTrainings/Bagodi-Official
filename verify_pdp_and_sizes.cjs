const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: "new",
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  const consoleLogs = [];
  page.on('console', msg => consoleLogs.push(`[${msg.type()}] ${msg.text()}`));
  page.on('pageerror', err => consoleLogs.push(`[PAGE ERROR] ${err.message}`));

  const wait = (ms) => new Promise(r => setTimeout(r, ms));

  console.log("1. Visiting Storefront PDP...");
  await page.goto('https://bagodi-store.vercel.app/product/classic-lenin-shirt-example', {
    waitUntil: 'networkidle2',
    timeout: 30000
  });

  await wait(3000);

  // Take screenshot of PDP showing the two buttons
  const pdpScreenshot = '/Users/sachin/.gemini/antigravity/brain/d7370da4-5291-4c6d-80c9-a1cbef243e3c/live_storefront_two_buttons.png';
  await page.screenshot({ path: pdpScreenshot, fullPage: false });
  console.log("Saved PDP screenshot to", pdpScreenshot);

  // Check buttons
  const buttons = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(Boolean);
  });
  console.log("Visible buttons on PDP:", buttons);

  // Test clicking "Add to Bag"
  console.log("Clicking Add to Bag button...");
  const addToBagBtn = await page.evaluateHandle(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    return btns.find(b => b.innerText.includes('Add to Bag') || b.innerText.includes('Add to Boutique Bag'));
  });

  if (addToBagBtn) {
    await addToBagBtn.click();
    await wait(3000);
  }

  // Take screenshot after adding to bag
  const addedScreenshot = '/Users/sachin/.gemini/antigravity/brain/d7370da4-5291-4c6d-80c9-a1cbef243e3c/live_storefront_added_to_bag.png';
  await page.screenshot({ path: addedScreenshot, fullPage: false });
  console.log("Saved Added to Bag screenshot to", addedScreenshot);

  // 2. Visit Merchant Portal and open New Garment modal
  console.log("2. Visiting Merchant Portal...");
  await page.goto('https://bagodi-merchant.vercel.app/login', {
    waitUntil: 'networkidle2',
    timeout: 30000
  });

  await page.evaluate(() => {
    localStorage.setItem('bagodi_auth_at', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy');
    localStorage.setItem('bagodi_user_role', 'merchant_admin');
    localStorage.setItem('bagodi_auth_user', JSON.stringify({
      id: "11111111-1111-1111-1111-111111111111",
      email: "merchant@bagodi.in",
      role: "merchant_admin",
      fullName: "Bagodi Flagship Store Admin",
      tenantId: "11111111-1111-1111-1111-111111111111",
      storeId: "22222222-2222-2222-2222-222222222222"
    }));
  });

  await page.goto('https://bagodi-merchant.vercel.app/products', {
    waitUntil: 'networkidle2',
    timeout: 30000
  });

  await wait(3000);

  // Click "+ New Garment" button
  console.log("Clicking + New Garment button...");
  const clicked = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const btn = btns.find(b => b.innerText.includes('New Garment'));
    if (btn) {
      btn.click();
      return true;
    }
    return false;
  });
  console.log("Found and clicked + New Garment:", clicked);
  await wait(2000);

  const modalScreenshot = '/Users/sachin/.gemini/antigravity/brain/d7370da4-5291-4c6d-80c9-a1cbef243e3c/live_merchant_size_matrix_modal.png';
  await page.screenshot({ path: modalScreenshot, fullPage: false });
  console.log("Saved Size Matrix Modal screenshot to", modalScreenshot);

  console.log("Console logs during test:", consoleLogs.filter(l => l.includes('400') || l.includes('error') || l.includes('cart')));

  await browser.close();
})();
