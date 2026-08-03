const fs = require('node:fs');
const { test, expect } = require('@playwright/test');
const { apiJson } = require('./support');

const enabled = /^(1|true|yes)$/i.test(process.env.PLATFORM_LIVE_PROVIDER_ACCEPTANCE || '');

test.describe('controlled live-provider acceptance', () => {
  test('@live-provider submits exactly one already-approved reserved managed job', async ({ request }, testInfo) => {
    test.skip(!enabled, 'Live provider acceptance is disabled.');
    testInfo.annotations.push({ type: 'severity', description: 'P0' });

    const provider = process.env.PLATFORM_LIVE_PROVIDER;
    const planId = process.env.PLATFORM_LIVE_ROUTING_PLAN_ID;
    const payloadFile = process.env.PLATFORM_LIVE_RESERVATION_PAYLOAD_FILE;
    const maxSpend = Number(process.env.PLATFORM_LIVE_MAX_SPEND_USD || '0');
    const confirmation = process.env.PLATFORM_LIVE_CONFIRMATION;

    expect(['fal', 'vidu']).toContain(provider);
    expect(planId).toMatch(/^[0-9a-f-]{36}$/i);
    expect(payloadFile).toBeTruthy();
    expect(fs.existsSync(payloadFile)).toBe(true);
    expect(maxSpend).toBeGreaterThan(0);
    expect(maxSpend).toBeLessThanOrEqual(1);
    expect(confirmation).toBe(`SPEND-${provider.toUpperCase()}-${maxSpend.toFixed(2)}`);

    const plan = await apiJson(request, 'GET', `/routing/plans/${planId}`, { expected: [200] });
    expect(plan.payload.plan?.status || plan.payload.status).toMatch(/approved|ready|submitted/);
    const approvedCeiling = Number(
      plan.payload.plan?.approved_ceiling ||
      plan.payload.approved_ceiling ||
      plan.payload.decision?.approved_ceiling ||
      0
    );
    expect(approvedCeiling).toBeGreaterThan(0);
    expect(approvedCeiling).toBeLessThanOrEqual(maxSpend);

    const payload = JSON.parse(fs.readFileSync(payloadFile, 'utf8'));
    expect(payload.routing_item_id).toMatch(/^[0-9a-f-]{36}$/i);

    const result = await apiJson(request, 'POST', `/routing/plans/${planId}/managed-jobs`, {
      data: payload,
      expected: [200, 201]
    });
    const job = result.payload.job || result.payload.generation_job || result.payload;
    expect(job.id || job.job_id).toBeTruthy();

    await testInfo.attach('live-provider-reservation-result', {
      body: Buffer.from(JSON.stringify(result.payload, null, 2)),
      contentType: 'application/json'
    });
  });
});
