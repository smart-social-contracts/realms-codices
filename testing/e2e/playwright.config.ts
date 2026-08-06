import { defineConfig, devices } from '@playwright/test';

const lifecycleE2e = !!process.env.LIFECYCLE_E2E;

export default defineConfig({
  testDir: './specs',
  timeout: 120_000,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  maxFailures: 0,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { open: 'never' }],
    ...(lifecycleE2e ? [['json', { outputFile: 'test-results/playwright-results.json' }]] : []),
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'https://staging.gos.earth',
    trace: lifecycleE2e ? 'on' : 'on-first-retry',
    screenshot: 'on',
    video: lifecycleE2e ? 'on' : 'retain-on-failure',
    navigationTimeout: 120_000,
    actionTimeout: 20_000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
