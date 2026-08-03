const { test, expect } = require('@playwright/test');
const { apiJson } = require('./support');

test.describe('existing portfolio evidence audit', () => {
  test('overview, brands, queue, reviews, operations, releases and deliveries are readable', async ({ request }, testInfo) => {
    const endpoints = [
      '/studio-v2/overview',
      '/portfolio/brands',
      '/portfolio/queue',
      '/review/inbox?limit=100',
      '/operations/monitoring',
      '/local-production/status',
      '/releases?limit=100',
      '/deliveries?limit=100',
      '/renderers/catalogue',
      '/routing/policies'
    ];
    const evidence = {};
    for (const endpoint of endpoints) {
      const result = await apiJson(request, 'GET', endpoint, { expected: [200, 404, 409, 422] });
      expect(result.response.status(), `${endpoint} returned a server error`).toBeLessThan(500);
      evidence[endpoint] = { status: result.response.status(), payload: result.payload };
    }
    await testInfo.attach('portfolio-api-evidence', {
      body: Buffer.from(JSON.stringify(evidence, null, 2)),
      contentType: 'application/json'
    });
  });

  test('recent canonical content reconciles across state, jobs, review and release APIs', async ({ request }, testInfo) => {
    const overview = await apiJson(request, 'GET', '/studio-v2/overview', { expected: [200] });
    const recent = overview.payload.recent || [];
    test.skip(!recent.length, 'No existing content is available for evidence reconciliation.');

    const evidence = [];
    for (const row of recent.slice(0, 10)) {
      const id = row.item?.id || row.id;
      if (!id) continue;
      const state = await apiJson(request, 'GET', `/studio-v2/content/${id}/state`, { expected: [200] });
      const jobs = await apiJson(request, 'GET', `/generation/jobs?content_id=${id}&limit=100`, { expected: [200] });
      const review = await apiJson(request, 'GET', `/review/content/${id}`, { expected: [200, 404, 409] });
      const releases = await apiJson(request, 'GET', `/releases?content_id=${id}&limit=100`, { expected: [200] });

      expect(state.payload.item?.id || state.payload.item?.content_id).toBe(id);
      expect(Array.isArray(jobs.payload.jobs)).toBe(true);
      expect(review.response.status()).toBeLessThan(500);
      expect(Array.isArray(releases.payload.releases || releases.payload.items || [])).toBe(true);
      evidence.push({
        content_id: id,
        title: state.payload.item?.title,
        status: state.payload.status,
        jobs: jobs.payload.jobs?.map((job) => ({ id: job.id, type: job.job_type, status: job.status })),
        review_status: review.response.status(),
        release_count: (releases.payload.releases || releases.payload.items || []).length,
        blockers: state.payload.blockers || []
      });
    }
    expect(evidence.length).toBeGreaterThan(0);
    await testInfo.attach('canonical-content-reconciliation', {
      body: Buffer.from(JSON.stringify(evidence, null, 2)),
      contentType: 'application/json'
    });
  });

  test('generation jobs have valid identities, states and bounded cost evidence', async ({ request }, testInfo) => {
    const result = await apiJson(request, 'GET', '/generation/jobs?limit=100', { expected: [200] });
    const jobs = result.payload.jobs || [];
    const allowed = new Set(['queued', 'running', 'succeeded', 'failed', 'cancelled', 'retry_wait']);
    for (const job of jobs) {
      expect(job.id).toMatch(/^[0-9a-f-]{36}$/i);
      expect(job.job_type).toBeTruthy();
      expect(allowed.has(job.status), `Unexpected job status ${job.status}`).toBe(true);
      expect(Number(job.estimated_cost_usd || 0)).toBeGreaterThanOrEqual(0);
      expect(Number(job.reserved_cost_usd || 0)).toBeGreaterThanOrEqual(0);
      expect(Number(job.observed_cost_usd || 0)).toBeGreaterThanOrEqual(0);
    }
    await testInfo.attach('generation-job-audit', {
      body: Buffer.from(JSON.stringify(jobs, null, 2)),
      contentType: 'application/json'
    });
  });

  test('release and delivery records preserve immutable identifiers and never imply automatic publication', async ({ request }, testInfo) => {
    const releases = await apiJson(request, 'GET', '/releases?limit=100', { expected: [200] });
    const deliveries = await apiJson(request, 'GET', '/deliveries?limit=100', { expected: [200] });
    const releaseRows = releases.payload.releases || releases.payload.items || [];
    const deliveryRows = deliveries.payload.deliveries || deliveries.payload.items || [];

    for (const release of releaseRows) {
      expect(release.id).toMatch(/^[0-9a-f-]{36}$/i);
      if (release.package_sha256) expect(release.package_sha256).toMatch(/^[0-9a-f]{64}$/i);
    }
    for (const delivery of deliveryRows) {
      expect(delivery.id).toMatch(/^[0-9a-f-]{36}$/i);
      expect(String(delivery.triggered_by || delivery.created_by || '')).not.toMatch(/automatic.publication/i);
    }
    await testInfo.attach('release-delivery-audit', {
      body: Buffer.from(JSON.stringify({ releases: releaseRows, deliveries: deliveryRows }, null, 2)),
      contentType: 'application/json'
    });
  });
});
