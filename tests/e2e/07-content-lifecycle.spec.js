const { test, expect } = require('@playwright/test');
const { apiJson, assertClean, monitorPage, runId, signIn } = require('./support');

const mutating = /^(1|true|yes)$/i.test(process.env.PLATFORM_E2E_MUTATING || '');

test.describe.serial('Creator Studio content lifecycle', () => {
  let contentId;

  test('creates content through the real guided browser wizard and queues local script generation', async ({ page }, testInfo) => {
    test.skip(!mutating, 'Set PLATFORM_E2E_MUTATING=true for the full no-cost lifecycle.');
    test.setTimeout(180_000);
    const findings = monitorPage(page);
    await signIn(page, 'admin');
    await page.goto('/app/content/new');
    await expect(page.locator('#page-title')).toContainText('Create content');

    await page.locator('#wizard-next').click();
    await expect(page.locator('input[name="wizard-start"][value="manual_topic"]')).toBeChecked();
    await page.locator('#wizard-next').click();

    const id = runId();
    await page.locator('#brief-form input[name="title"]').fill(`E2E Creator Studio ${id}`);
    await page.locator('#brief-form textarea[name="topic"]').fill('Explain why a carefully controlled automated acceptance process reduces production risk. Avoid time-sensitive claims.');
    await page.locator('#brief-form input[name="objective"]').fill('Validate the complete browser-to-database content creation flow.');
    await page.locator('#brief-form input[name="audience"]').fill('Internal QA reviewers');
    await page.locator('#brief-form select[name="platform"]').selectOption('facebook');
    await page.locator('#brief-form select[name="format_name"]').selectOption('vertical_short');
    await page.locator('#brief-form select[name="duration_seconds"]').selectOption('30');
    await page.locator('#brief-form textarea[name="notes"]').fill(`Automated QA run ${id}. No paid provider and no publication.`);
    await page.locator('#wizard-next').click();
    await expect(page.locator('#app-view')).toContainText('Confirm and generate');
    await expect(page.locator('#app-view')).toContainText('Nothing is automatically approved or published');

    const createResponse = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return response.request().method() === 'POST' && url.pathname === '/p110/content';
    });
    await page.locator('#wizard-create').click();
    const response = await createResponse;
    const payload = await response.json().catch(() => ({}));
    expect(response.status(), `POST /p110/content failed: ${JSON.stringify(payload)}`).toBe(200);
    expect(payload.content_id, `POST /p110/content did not return content_id: ${JSON.stringify(payload)}`).toMatch(/^[0-9a-f-]{36}$/i);

    await expect(page).toHaveURL(new RegExp(`/app/content/${payload.content_id}/script$`, 'i'), { timeout: 60_000 });
    contentId = payload.content_id;
    await expect(page.locator('#page-title')).toContainText(`E2E Creator Studio ${id}`);
    await expect(page.locator('#app-view')).toContainText(/Generating|Script|queued|draft/i);
    await assertClean(findings, testInfo);
  });

  test('created content has canonical state, jobs and review workspace evidence', async ({ request }) => {
    test.skip(!mutating || !contentId, 'Content fixture was not created.');
    const state = await apiJson(request, 'GET', `/studio-v2/content/${contentId}/state`, { expected: [200] });
    expect(state.payload.item?.id || state.payload.item?.content_id).toBe(contentId);
    expect(Array.isArray(state.payload.jobs)).toBe(true);
    expect((state.payload.jobs || []).some((job) => job.job_type === 'script')).toBe(true);

    const jobs = await apiJson(request, 'GET', `/generation/jobs?content_id=${contentId}&limit=100`, { expected: [200] });
    expect(Array.isArray(jobs.payload.items)).toBe(true);
    expect((jobs.payload.items || []).some((job) => job.job_type === 'script')).toBe(true);

    const review = await apiJson(request, 'GET', `/review/content/${contentId}`, { expected: [200, 404, 409, 422] });
    expect(review.response.status()).not.toBe(500);
  });

  test('script job reaches a retained terminal or reviewable state without duplicate successful jobs', async ({ request }) => {
    test.skip(!mutating || !contentId, 'Content fixture was not created.');
    test.setTimeout(420_000);
    const deadline = Date.now() + 360_000;
    let jobs = [];
    do {
      const result = await apiJson(request, 'GET', `/generation/jobs?content_id=${contentId}&job_type=script&limit=100`, { expected: [200] });
      jobs = result.payload.items || [];
      if (jobs.some((job) => ['succeeded', 'failed', 'cancelled', 'dead_letter'].includes(job.status))) break;
      await new Promise((resolve) => setTimeout(resolve, 5000));
    } while (Date.now() < deadline);

    expect(jobs.length).toBeGreaterThanOrEqual(1);
    const successful = jobs.filter((job) => job.status === 'succeeded');
    expect(successful.length).toBeLessThanOrEqual(1);
    expect(jobs.some((job) => ['succeeded', 'failed', 'cancelled', 'dead_letter'].includes(job.status))).toBe(true);

    const script = await apiJson(request, 'GET', `/scripts/content/${contentId}`, { expected: [200, 404, 409, 422] });
    if (successful.length) {
      expect(script.response.status()).toBe(200);
      expect(script.payload.document?.id).toBeTruthy();
    }
  });

  test('browser refresh during the content workflow preserves the canonical item and session', async ({ page }) => {
    test.skip(!mutating || !contentId, 'Content fixture was not created.');
    await signIn(page, 'admin');
    await page.goto(`/app/content/${contentId}/script`);
    const title = await page.locator('#page-title').innerText();
    await page.reload();
    await expect(page.locator('#studio-shell')).toBeVisible();
    await expect(page.locator('#page-title')).toHaveText(title);
    await expect(page).toHaveURL(new RegExp(`/app/content/${contentId}/script$`, 'i'));
  });
});
