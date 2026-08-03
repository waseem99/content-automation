const { test, expect } = require('@playwright/test');
const { assertClean, authHeaders, monitorPage, signIn } = require('./support');

test.describe('spend, publishing and security safety contracts', () => {
  test('@smoke unauthenticated protected APIs reject access', async ({ request }) => {
    for (const path of ['/access/me', '/portfolio/brands', '/operations/monitoring', '/renderers/catalogue']) {
      const response = await request.get(path);
      expect([401, 403], `${path} unexpectedly returned ${response.status()}`).toContain(response.status());
    }
  });

  test('@smoke browser never calls provider or publishing origins during no-cost acceptance', async ({ page }, testInfo) => {
    const findings = monitorPage(page);
    await signIn(page, 'admin');
    for (const route of ['/app/dashboard', '/app/campaigns', '/app/content', '/app/reviews', '/app/publishing', '/app/operations']) {
      await page.goto(route);
      await page.waitForTimeout(300);
    }
    await assertClean(findings, testInfo);
  });

  test('campaign workspace explicitly states paid generation and publishing are unavailable', async ({ page }) => {
    await signIn(page, 'admin');
    await page.goto('/app/campaigns');
    await expect(page.locator('#app-view')).toContainText(/Rendering and publishing remain off|Paid generation and public publishing/i);
  });

  test('renderer catalogue may be inspected but setup does not prove real generation', async ({ request }) => {
    const response = await request.get('/renderers/catalogue?provider_key=fal', { headers: authHeaders('admin') });
    expect([200, 404], `Renderer catalogue returned ${response.status()}`).toContain(response.status());
    if (response.status() === 200) {
      const payload = await response.json();
      for (const entry of payload.entries || []) {
        expect(entry.provider_key).toBe('fal');
        expect(entry.data_handling?.credentials_in_git).not.toBe(true);
        expect(entry.data_handling?.credentials_in_postgresql).not.toBe(true);
      }
    }
  });

  test('Reviewer cannot inspect portfolio-wide operations APIs', async ({ request }) => {
    test.skip(!process.env.PLATFORM_REVIEWER_KEY, 'Reviewer key is not available.');
    const response = await request.get('/operations/monitoring', { headers: authHeaders('reviewer') });
    expect([401, 403], `Reviewer operations access returned ${response.status()}`).toContain(response.status());
  });

  test('configured fal pricing reserves the fixed request charge rather than an unsafe duration conversion', async ({ request }, testInfo) => {
    testInfo.annotations.push({ type: 'severity', description: 'P1' });
    testInfo.annotations.push({ type: 'improvement', description: 'Represent fal Wan 2.2 fixed-request billing as per_request_usd and include it in preflight estimation.' });
    const response = await request.get('/renderers/catalogue?provider_key=fal', { headers: authHeaders('admin') });
    test.skip(response.status() === 404, 'fal renderer is not configured yet.');
    expect(response.status()).toBe(200);
    const payload = await response.json();
    const active = (payload.entries || []).find((entry) => entry.status === 'active');
    test.skip(!active, 'No active fal renderer is configured yet.');
    const pricing = active.pricing || {};
    expect(Number(pricing.per_request_usd || 0)).toBeGreaterThan(0);
  });

  test('runtime configuration exposes no operator or provider credentials', async ({ request }) => {
    const payload = await (await request.get('/runtime/config')).json();
    const text = JSON.stringify(payload).toLowerCase();
    expect(text).not.toContain('fal_key');
    expect(text).not.toContain('vidu_api_key');
    expect(text).not.toContain('operator_api_keys_json');
    expect(text).not.toMatch(/bearer\s+[a-z0-9._-]+/i);
  });
});
