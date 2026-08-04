const { test, expect } = require('@playwright/test');
const { assertClean, monitorPage } = require('./support');

test.describe('runtime and deployment acceptance', () => {
  test('@smoke local runtime, database, schema and migration readiness', async ({ request }) => {
    const response = await request.get('/runtime/ready');
    expect(response.ok()).toBeTruthy();
    const payload = await response.json();
    expect(payload.ok).toBe(true);
    expect(payload.checks).toMatchObject({
      runtime_configured: true,
      database_configured: true,
      database_reachable: true,
      schema_ready: true,
      migrations_ready: true
    });
    expect(payload.release?.migration_head).toMatch(/^0108_p131_staged_acceptance_closeout\.sql$/);
  });

  test('@smoke release evidence identifies the deployed commit', async ({ request }) => {
    const expectedGitSha = process.env.PLATFORM_EXPECTED_GIT_SHA;
    expect(expectedGitSha).toMatch(/^[0-9a-f]{40}$/);
    const payload = await (await request.get('/runtime/ready')).json();
    expect(payload.release?.git_sha).toBe(expectedGitSha);
    expect(payload.release?.configuration_digest).toMatch(/^[0-9a-f]{64}$/);
    expect(payload.release?.configuration_digest).not.toBe('0'.repeat(64));
  });

  test('@smoke Creator Studio shell and static assets load without browser errors', async ({ page }, testInfo) => {
    const findings = monitorPage(page);
    await page.goto('/app/dashboard');
    await expect(page).toHaveTitle(/Content Engine Studio/);
    await expect(page.locator('#login-dialog')).toBeVisible();
    await expect(page.locator('#operator-key')).toBeVisible();
    await assertClean(findings, testInfo);
  });

  test('@smoke remote ngrok readiness matches the local runtime', async ({ playwright }) => {
    const remoteURL = process.env.PLATFORM_REMOTE_URL;
    test.skip(!remoteURL, 'PLATFORM_REMOTE_URL is not configured.');
    const context = await playwright.request.newContext({
      baseURL: remoteURL,
      extraHTTPHeaders: { 'ngrok-skip-browser-warning': 'true' }
    });
    try {
      const response = await context.get('/runtime/ready');
      expect(response.ok()).toBeTruthy();
      const payload = await response.json();
      expect(payload.ok).toBe(true);
      expect(payload.release?.git_sha).toBe(process.env.PLATFORM_EXPECTED_GIT_SHA);
    } finally {
      await context.dispose();
    }
  });
});
