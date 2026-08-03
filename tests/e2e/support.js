const { expect } = require('@playwright/test');

function envKey(role) {
  const name = {
    'super-admin': 'PLATFORM_SUPER_ADMIN_KEY',
    admin: 'PLATFORM_ADMIN_KEY',
    reviewer: 'PLATFORM_REVIEWER_KEY'
  }[role];
  const value = process.env[name] || '';
  if (!value) throw new Error(`${name} is required for the ${role} acceptance flow.`);
  return value;
}

async function signIn(page, role = 'admin') {
  const key = envKey(role);
  await page.goto('/app/dashboard');
  const dialog = page.locator('#login-dialog');
  if (await dialog.isVisible().catch(() => false)) {
    await page.locator('#operator-key').fill(key);
    await page.locator('#login-form button[type="submit"]').click();
  }
  await expect(page.locator('#studio-shell')).toBeVisible();
  await expect(page.locator('#page-title')).toBeVisible();
  return key;
}

async function signOut(page) {
  await page.locator('#sign-out').click();
  await expect(page.locator('#login-dialog')).toBeVisible();
}

function monitorPage(page) {
  const findings = { consoleErrors: [], pageErrors: [], serverErrors: [], externalRequests: [] };
  page.on('console', (message) => {
    if (message.type() === 'error') findings.consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => findings.pageErrors.push(error.message));
  page.on('response', (response) => {
    if (response.status() >= 500) findings.serverErrors.push(`${response.status()} ${response.url()}`);
  });
  page.on('request', (request) => {
    const url = request.url();
    if (/queue\.fal\.run|api\.vidu\.com|youtube\.googleapis\.com\/upload/i.test(url)) {
      findings.externalRequests.push(`${request.method()} ${url}`);
    }
  });
  return findings;
}

async function assertClean(findings, testInfo, options = {}) {
  await testInfo.attach('browser-findings', {
    body: Buffer.from(JSON.stringify(findings, null, 2)),
    contentType: 'application/json'
  });
  if (!options.allowServerErrors) expect(findings.serverErrors, 'Unexpected server errors').toEqual([]);
  if (!options.allowConsoleErrors) expect(findings.consoleErrors, 'Unexpected browser console errors').toEqual([]);
  expect(findings.pageErrors, 'Unhandled browser errors').toEqual([]);
  expect(findings.externalRequests, 'Browser initiated a paid-provider or publishing request').toEqual([]);
}

function authHeaders(role = 'admin') {
  return { 'X-Operator-Key': envKey(role), 'Content-Type': 'application/json' };
}

async function apiJson(request, method, path, { role = 'admin', data, expected = [200, 201] } = {}) {
  const response = await request.fetch(path, {
    method,
    headers: authHeaders(role),
    data
  });
  const payload = await response.json().catch(() => ({}));
  expect(expected, `${method} ${path} returned ${response.status()}: ${JSON.stringify(payload)}`).toContain(response.status());
  return { response, payload };
}

async function firstBrand(request, role = 'admin') {
  const { payload } = await apiJson(request, 'GET', '/portfolio/brands', { role, expected: [200] });
  const brand = payload.brands?.[0];
  expect(brand, 'At least one brand is required for automated campaign acceptance').toBeTruthy();
  return brand;
}

function runId() {
  return process.env.PLATFORM_E2E_RUN_ID || `e2e-${Date.now()}`;
}

async function createQaCampaign(request) {
  const brand = await firstBrand(request, 'admin');
  const id = runId().toLowerCase().replace(/[^a-z0-9._-]+/g, '-').slice(0, 70);
  const campaignKey = `${id}-${Date.now()}`.slice(0, 115);
  const { payload: created } = await apiJson(request, 'POST', '/p119/campaigns', {
    data: {
      campaign_key: campaignKey,
      brand_id: brand.id,
      name: `E2E Platform Acceptance ${id}`,
      description: 'Automated no-cost platform acceptance campaign.',
      metadata: { automated_e2e: true, run_id: id, manual_sheet_required: false }
    }
  });
  const campaign = created.campaign;
  const version = created.versions?.[0];
  expect(campaign?.id).toBeTruthy();
  expect(version?.id).toBeTruthy();

  const date = new Date().toISOString().slice(0, 10);
  await apiJson(request, 'POST', `/p119/campaign-versions/${version.id}/items`, {
    data: {
      items: [
        {
          item_key: 'item-00001',
          title: `E2E supported factual item ${id}`,
          topic: 'Explain a stable, non-sensitive topic using only well-supported factual claims.',
          objective: 'Exercise automatic pre-generation without final rendering or publishing.',
          audience: 'Internal QA reviewers',
          format_name: 'master_video',
          primary_platform: 'facebook',
          target_platforms: ['facebook'],
          target_duration_seconds: 30,
          short_cut_count: 0,
          language: 'en-US',
          scheduled_for: date,
          priority: 10,
          metadata: { automated_e2e: true, run_id: id }
        }
      ]
    }
  });
  await apiJson(request, 'POST', `/p119/campaign-versions/${version.id}/validate`);
  await apiJson(request, 'POST', `/p119/campaign-versions/${version.id}/activate`);
  await apiJson(request, 'POST', `/p120/campaigns/${campaign.id}/autopilot/start`);
  return { brand, campaign, version, campaignKey };
}

module.exports = {
  assertClean,
  authHeaders,
  createQaCampaign,
  envKey,
  firstBrand,
  monitorPage,
  runId,
  signIn,
  signOut,
  apiJson
};
