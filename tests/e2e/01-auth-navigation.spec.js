const { test, expect } = require('@playwright/test');
const { assertClean, monitorPage, signIn, signOut } = require('./support');

test.describe('authentication and role boundaries', () => {
  test('@smoke invalid access key is rejected without exposing sensitive detail', async ({ page }, testInfo) => {
    const findings = monitorPage(page);
    await page.goto('/app/dashboard');
    await page.locator('#operator-key').fill('definitely-invalid-e2e-key');
    await page.locator('#login-form button[type="submit"]').click();
    await expect(page.locator('#login-error')).not.toBeEmpty();
    await expect(page.locator('#studio-shell')).toBeHidden();
    expect(page.url()).not.toContain('definitely-invalid-e2e-key');
    await assertClean(findings, testInfo);
  });

  test('@smoke Admin can sign in, navigate all operational workspaces and sign out', async ({ page }, testInfo) => {
    const findings = monitorPage(page);
    const key = await signIn(page, 'admin');
    const destinations = [
      ['/app/dashboard', 'Dashboard'],
      ['/app/campaigns', 'Campaigns'],
      ['/app/content', 'Content'],
      ['/app/reviews', 'Reviews'],
      ['/app/team', 'Team'],
      ['/app/settings', 'Settings'],
      ['/app/operations', 'Operations']
    ];
    for (const [path, title] of destinations) {
      await page.goto(path);
      await expect(page.locator('#studio-shell')).toBeVisible();
      await expect(page.locator('#page-title')).toContainText(title, { ignoreCase: true });
      await expect(page.locator('#app-view')).not.toContainText('Unable to load this screen');
    }
    expect(page.url()).not.toContain(key);
    expect(await page.evaluate(() => localStorage.getItem('content-automation.operator-key'))).toBeNull();
    expect(await page.evaluate(() => sessionStorage.getItem('content-automation.operator-key'))).toBe(key);
    await signOut(page);
    expect(await page.evaluate(() => sessionStorage.getItem('content-automation.operator-key'))).toBeNull();
    await assertClean(findings, testInfo);
  });

  test('@smoke Reviewer navigation excludes system administration', async ({ page }, testInfo) => {
    test.skip(!process.env.PLATFORM_REVIEWER_KEY, 'Reviewer key is not available.');
    const findings = monitorPage(page);
    await signIn(page, 'reviewer');
    const nav = page.locator('#primary-nav');
    await expect(nav.getByText('Team & access')).toHaveCount(0);
    await expect(nav.getByText('Settings')).toHaveCount(0);
    await expect(nav.getByText('Operations')).toHaveCount(0);
    await page.goto('/app/team');
    await expect(page.locator('#app-view')).toContainText(/Unable|access|not allowed|forbidden/i);
    await assertClean(findings, testInfo, { allowServerErrors: false });
  });

  test('operator key is not rendered into page text, URL, cookies or local storage', async ({ page }) => {
    const key = await signIn(page, 'admin');
    expect(await page.locator('body').innerText()).not.toContain(key);
    expect(page.url()).not.toContain(key);
    expect(await page.context().cookies()).not.toEqual(expect.arrayContaining([expect.objectContaining({ value: key })]));
    expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain(key);
  });

  test('Super Admin key resolves to the Super Admin identity', async ({ page }) => {
    test.skip(!process.env.PLATFORM_SUPER_ADMIN_KEY, 'Super Admin key is not available.');
    await signIn(page, 'super-admin');
    await expect(page.locator('#session-card')).toContainText(/Super Admin|local-super-admin/i);
  });
});
