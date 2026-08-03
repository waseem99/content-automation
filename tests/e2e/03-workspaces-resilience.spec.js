const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const { assertClean, monitorPage, signIn } = require('./support');

test.describe('workspaces, resilience and accessibility', () => {
  test('@smoke dashboard, campaigns, content, reviews and operations render meaningful states', async ({ page }, testInfo) => {
    const findings = monitorPage(page);
    await signIn(page, 'admin');
    const routes = ['/app/dashboard', '/app/campaigns', '/app/content', '/app/reviews', '/app/operations'];
    for (const route of routes) {
      await page.goto(route);
      await expect(page.locator('#app-view')).toBeVisible();
      await expect(page.locator('#app-view')).not.toBeEmpty();
      await expect(page.locator('#app-view')).not.toContainText(/undefined|null object|\[object Object\]/i);
      await expect(page.locator('#app-view')).not.toContainText('Unable to load this screen');
    }
    await assertClean(findings, testInfo);
  });

  test('session and current route survive a browser refresh', async ({ page }) => {
    await signIn(page, 'admin');
    await page.goto('/app/campaigns');
    await expect(page.locator('#page-title')).toContainText('Campaigns');
    await page.reload();
    await expect(page.locator('#studio-shell')).toBeVisible();
    await expect(page.locator('#page-title')).toContainText('Campaigns');
  });

  test('known API failure produces an actionable error and retry recovers', async ({ page }) => {
    await signIn(page, 'admin');
    let failedOnce = false;
    await page.route('**/studio-v2/overview', async (route) => {
      if (!failedOnce) {
        failedOnce = true;
        await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'e2e temporary outage' }) });
      } else {
        await route.continue();
      }
    });
    await page.goto('/app/dashboard');
    await expect(page.locator('#app-view')).toContainText('Unable to load this screen');
    await expect(page.locator('#retry-screen')).toBeVisible();
    await page.locator('#retry-screen').click();
    await expect(page.locator('#page-title')).toContainText('Dashboard');
    await expect(page.locator('#app-view')).not.toContainText('Unable to load this screen');
  });

  test('dashboard has no serious or critical automated accessibility violations', async ({ page }, testInfo) => {
    testInfo.annotations.push({ type: 'severity', description: 'P2' });
    await signIn(page, 'admin');
    await page.goto('/app/dashboard');
    const results = await new AxeBuilder({ page }).include('#studio-shell').analyze();
    const blocking = results.violations.filter((item) => ['serious', 'critical'].includes(item.impact));
    await testInfo.attach('axe-results', {
      body: Buffer.from(JSON.stringify(results.violations, null, 2)),
      contentType: 'application/json'
    });
    expect(blocking, blocking.map((item) => `${item.id}: ${item.help}`).join('\n')).toEqual([]);
  });

  for (const viewport of [
    { width: 1366, height: 768, label: 'laptop' },
    { width: 1920, height: 1080, label: 'desktop' }
  ]) {
    test(`Creator Studio remains usable at ${viewport.label} resolution`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await signIn(page, 'admin');
      await page.goto('/app/dashboard');
      await expect(page.locator('#primary-nav')).toBeVisible();
      await expect(page.locator('#app-view')).toBeVisible();
      const body = await page.locator('body').evaluate((node) => ({ scrollWidth: node.scrollWidth, clientWidth: node.clientWidth }));
      expect(body.scrollWidth).toBeLessThanOrEqual(body.clientWidth + 4);
    });
  }
});
