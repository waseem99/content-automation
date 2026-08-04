const { test, expect } = require('@playwright/test');
const { apiJson, assertClean, createQaCampaign, monitorPage, signIn } = require('./support');

const mutating = /^(1|true|yes)$/i.test(process.env.PLATFORM_E2E_MUTATING || '');

async function waitForCampaignStatus(request, campaignId, expectedStatus) {
  const deadline = Date.now() + 15_000;
  let latest;
  do {
    latest = await apiJson(request, 'GET', `/p119/campaigns/${campaignId}`, { expected: [200] });
    if (latest.payload.campaign?.status === expectedStatus) return latest;
    await new Promise((resolve) => setTimeout(resolve, 250));
  } while (Date.now() < deadline);
  expect(latest?.payload?.campaign?.status, `Campaign ${campaignId} did not reach ${expectedStatus}`).toBe(expectedStatus);
  return latest;
}

async function clickCampaignStatusAction(page, selector, endpoint, expectedStatus) {
  const button = page.locator(selector);
  await expect(button).toBeVisible();
  const responsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === 'POST' && url.pathname === endpoint;
  });
  await button.click();
  const response = await responsePromise;
  const payload = await response.json().catch(() => ({}));
  expect(response.status(), `POST ${endpoint} returned ${response.status()}: ${JSON.stringify(payload)}`).toBe(200);
  expect(payload.campaign?.status).toBe(expectedStatus);
  return payload;
}

test.describe.serial('database-native campaign lifecycle', () => {
  let fixture;

  test('creates, validates, activates and starts one no-cost QA campaign', async ({ request }) => {
    test.skip(!mutating, 'Set PLATFORM_E2E_MUTATING=true for the full no-cost lifecycle.');
    fixture = await createQaCampaign(request);
    const { payload } = await apiJson(request, 'GET', `/p119/campaigns/${fixture.campaign.id}`, { expected: [200] });
    expect(payload.campaign.id).toBe(fixture.campaign.id);
    expect(payload.campaign.campaign_key).toBe(fixture.campaignKey);
    expect(payload.campaign.status).toMatch(/active|running|validated/);
  });

  test('campaign is visible and operable through Creator Studio', async ({ page }, testInfo) => {
    test.skip(!mutating || !fixture, 'Mutating campaign fixture was not created.');
    const findings = monitorPage(page);
    await signIn(page, 'admin');
    await page.goto(`/app/campaigns/${fixture.campaign.id}`);
    await expect(page.locator('#page-title')).toContainText('E2E Platform Acceptance');
    await expect(page.locator('#app-view')).toContainText('Campaign items');
    await expect(page.locator('#app-view')).toContainText('Boundary enforced');
    await expect(page.locator('#app-view')).toContainText(/Paid generation and public publishing cannot start/i);
    await assertClean(findings, testInfo);
  });

  test('pause and resume preserve the campaign and do not create a new version', async ({ page, request }, testInfo) => {
    test.skip(!mutating || !fixture, 'Mutating campaign fixture was not created.');
    const findings = monitorPage(page);
    await signIn(page, 'admin');
    await page.goto(`/app/campaigns/${fixture.campaign.id}`);
    await expect(page.locator('#page-title')).toContainText('E2E Platform Acceptance');

    const before = await apiJson(request, 'GET', `/p119/campaigns/${fixture.campaign.id}`, { expected: [200] });
    const versionIds = (before.payload.versions || []).map((item) => item.id);

    await clickCampaignStatusAction(
      page,
      '#campaign-pause',
      `/p120/campaigns/${fixture.campaign.id}/pause`,
      'paused'
    );
    await expect(page.locator('#campaign-resume')).toBeVisible();
    const paused = await waitForCampaignStatus(request, fixture.campaign.id, 'paused');
    expect((paused.payload.versions || []).map((item) => item.id)).toEqual(versionIds);

    await clickCampaignStatusAction(
      page,
      '#campaign-resume',
      `/p120/campaigns/${fixture.campaign.id}/resume`,
      'active'
    );
    await expect(page.locator('#campaign-pause')).toBeVisible();
    const resumed = await waitForCampaignStatus(request, fixture.campaign.id, 'active');
    expect((resumed.payload.versions || []).map((item) => item.id)).toEqual(versionIds);
    await assertClean(findings, testInfo);
  });

  test('autopilot dashboard, item grid and grouped exceptions endpoints reconcile', async ({ request }) => {
    test.skip(!mutating || !fixture, 'Mutating campaign fixture was not created.');
    const dashboard = await apiJson(request, 'GET', `/p120/campaigns/${fixture.campaign.id}/dashboard`, { expected: [200] });
    const items = await apiJson(request, 'GET', `/p120/campaigns/${fixture.campaign.id}/items?limit=200`, { expected: [200] });
    const exceptions = await apiJson(request, 'GET', `/p120/campaigns/${fixture.campaign.id}/exception-groups`, { expected: [200] });
    expect(Number(dashboard.payload.metrics?.total || 0)).toBeGreaterThanOrEqual(1);
    expect(items.payload.items?.length).toBeGreaterThanOrEqual(1);
    expect(Array.isArray(exceptions.payload.groups)).toBe(true);
  });
});
