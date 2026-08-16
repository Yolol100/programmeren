const { test, expect } = require('@playwright/test');

const baseURL = process.env.BASE_URL || 'http://127.0.0.1:8881';
const screenshot = process.env.PLAYWRIGHT_SCREENSHOT || 'browser-home.png';

async function assertHealthy(page, path) {
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(String(error)));
  const response = await page.goto(`${baseURL}${path}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  expect(response, `No main response for ${path}`).not.toBeNull();
  expect(response.status(), `${path} returned ${response.status()}`).toBeLessThan(500);
  await page.waitForTimeout(250);
  expect(pageErrors, `Uncaught browser errors on ${path}: ${pageErrors.join(' | ')}`).toEqual([]);
}

test('WordPress and WooCommerce public surfaces render without 5xx or page exceptions', async ({ page }) => {
  await assertHealthy(page, '/');
  await page.screenshot({ path: screenshot, fullPage: true });
  await assertHealthy(page, '/wp-json/');
  await assertHealthy(page, '/shop/');
  await assertHealthy(page, '/cart/');
  await assertHealthy(page, '/checkout/');
  await assertHealthy(page, '/wp-login.php');
});
