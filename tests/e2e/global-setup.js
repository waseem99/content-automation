const fs = require('node:fs');
const path = require('node:path');
const { request } = require('@playwright/test');

module.exports = async function globalSetup(config) {
  const runDir = process.env.PLATFORM_E2E_RUN_DIR || path.join('.runtime', 'e2e', 'latest');
  fs.mkdirSync(runDir, { recursive: true });

  const baseURL = process.env.PLATFORM_BASE_URL || config.projects[0]?.use?.baseURL || 'http://127.0.0.1:8000';
  const context = await request.newContext({ baseURL, ignoreHTTPSErrors: false });
  let readiness;
  try {
    const response = await context.get('/runtime/ready', { timeout: 15_000 });
    readiness = await response.json().catch(() => ({}));
    if (!response.ok() || readiness.ok !== true) {
      throw new Error(`Platform readiness failed (${response.status()}): ${JSON.stringify(readiness)}`);
    }
  } finally {
    await context.dispose();
  }

  const metadata = {
    kind: 'platform_e2e_run',
    run_id: process.env.PLATFORM_E2E_RUN_ID || path.basename(runDir),
    generated_at: new Date().toISOString(),
    base_url: baseURL,
    remote_url: process.env.PLATFORM_REMOTE_URL || null,
    mutating: /^(1|true|yes)$/i.test(process.env.PLATFORM_E2E_MUTATING || ''),
    cross_browser: /^(1|true|yes)$/i.test(process.env.PLATFORM_CROSS_BROWSER || ''),
    provider_execution_expected_disabled: true,
    public_publishing_expected_disabled: true,
    readiness
  };
  fs.writeFileSync(path.join(runDir, 'run-metadata.json'), JSON.stringify(metadata, null, 2));
};
