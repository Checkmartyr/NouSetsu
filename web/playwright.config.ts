import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testIgnore: '**/updater.production.spec.ts',
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['list']
  ],
  use: {
    baseURL: 'http://localhost:5176',
    channel: 'chrome',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'npm run dev -- --port 5176 --strictPort',
    url: 'http://localhost:5176',
    reuseExistingServer: false,
    env: { VITE_LOCAL_UPDATER_TEST: 'true' },
  },
  projects: [
    {
      name: 'desktop-hd',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1920, height: 1080 }
      },
    },
    {
      name: 'laptop',
      use: {
        viewport: { width: 1440, height: 900 }
      },
    },
    {
      name: 'tablet',
      use: {
        viewport: { width: 1024, height: 768 }
      },
    },
    {
      name: 'mobile',
      use: {
        viewport: { width: 390, height: 844 }
      },
    },
  ],
});
