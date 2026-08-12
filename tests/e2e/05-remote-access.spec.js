const { test, expect } = require('@playwright/test');
const { waitForStudioEntry } = require('./support');

test.describe('remote access boundary', () => {
  test('@smoke remote Creator Studio requires authentication and exposes only the intended web application', async ({ browser }) => {
    const remoteURL = process.env.PLATFORM_REMOTE_URL;
    test.skip(!remoteURL, 'PLATFORM_REMOTE_URL is not configured.');
    const context = await browser.newContext({ extraHTTPHeaders: { 'ngrok-skip-browser-warning': 'true' } });
    const page = await context.newPage();
    try {
      await page.goto(`${remoteURL}/app/dashboard`);
      const entry = await waitForStudioEntry(page, { timeout: 30000 });
      expect(entry, `Remote Creator Studio must stop at login for an unauthenticated fresh context: ${JSON.stringify(entry)}`).toEqual({ state: 'login' });
      await expect(page.locator('#login-dialog')).toBeVisible();
      await expect(page.locator('#operator-key')).toBeVisible();
      await expect(page.locator('#studio-shell')).toBeHidden();
      expect(page.url()).toMatch(/^https:\/\//);
    } finally {
      await context.close();
    }
  });
});
