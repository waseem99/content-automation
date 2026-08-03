const path = require('node:path');
const { defineConfig, devices } = require('@playwright/test');

const baseURL = process.env.PLATFORM_BASE_URL || 'http://127.0.0.1:8000';
const runDir = process.env.PLATFORM_E2E_RUN_DIR || path.join('.runtime', 'e2e', 'latest');
const crossBrowser = /^(1|true|yes)$/i.test(process.env.PLATFORM_CROSS_BROWSER || '');
const headed = /^(1|true|yes)$/i.test(process.env.PLATFORM_HEADED || '');

const projects = [
  {
    name: 'chromium',
    use: {
      ...devices['Desktop Chrome'],
      viewport: { width: 1440, height: 900 }
    }
  }
];

if (crossBrowser) {
  projects.push(
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } }
  );
}

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  outputDir: path.join(runDir, 'artifacts'),
  globalSetup: require.resolve('./tests/e2e/global-setup'),
  reporter: [
    [require.resolve('./tests/e2e/platform-reporter'), { outputDir: runDir }],
    ['html', { outputFolder: path.join(runDir, 'playwright-report'), open: 'never' }],
    ['json', { outputFile: path.join(runDir, 'results.json') }],
    ['junit', { outputFile: path.join(runDir, 'junit.xml'), stripANSIControlSequences: true }],
    [process.env.CI ? 'dot' : 'list']
  ],
  use: {
    baseURL,
    headless: !headed,
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
    ignoreHTTPSErrors: false,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  projects
});
