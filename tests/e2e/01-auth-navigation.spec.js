const { test, expect } = require('@playwright/test');
const { assertClean, monitorPage, navigateApp, signIn, signOut, waitForStudioEntry } = require('./support');

test.describe('authentication and role boundaries', () => {
  test('@smoke invalid access key is rejected without exposing sensitive detail', async ({ page }, testInfo) => {
    const findings = monitorPage(page);
    await page.goto('/app/dashboard');
    const entry = await waitForStudioEntry(page);
    expect(entry.state).toBe('login');

    const accessResponse = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === '/access/me' && response.status() === 401;
    });
    await page.locator('#operator-key').fill('definitely-invalid-e2e-key');
    await page.locator('#login-form button[type="submit"]').click();
    const response = await accessResponse;
    expect(response.status()).toBe(401);

    await expect(page.locator('#login-error')).not.toBeEmpty();
    await expect(page.locator('#studio-shell')).toBeHidden();
    expect(page.url()).not.toContain('definitely-invalid-e2e-key');
    await assertClean(findings, testInfo, {
      allowedClientErrors: [{ status: 401, path: '/access/me' }],
      allowedPageErrors: [/^operator key is invalid$/i]
    });
  });

  test('@smoke Admin can sign in, navigate all operational workspaces and sign out', async ({ page }, testInfo) => {
    const findings = monitorPage(page);
    const key = await signIn(page, 'admin');
    const destinations = [
      ['/app/dashboard', /Dashboard/i],
      ['/app/campaigns', /Campaigns/i],
      ['/app/content', /^Content$/i],
      ['/app/reviews', /Review/i],
      ['/app/team', /Team/i],
      ['/app/settings', /Settings/i],
      ['/app/operations', /Operations/i]
    ];
    for (const [path, title] of destinations) {
      if (new URL(page.url()).pathname !== path) await navigateApp(page, path);
      await expect(page.locator('#studio-shell')).toBeVisible();
      await expect(page.locator('#page-title')).toContainText(title);
      await expect(page.locator('#page-title')).not.toHaveText('Page not found');
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
    await expect(page).toHaveURL(/\/app\/dashboard\/?$/);
    await expect(page.locator('#page-title')).toContainText(/Dashboard/i);
    await expect(nav.getByText('Team & access')).toHaveCount(0);
    await assertClean(findings, testInfo);
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
