import { defineConfig, devices } from '@playwright/test';

// Run after npm run build: exercise the shipped assets rather than Vite source modules.
export default defineConfig({
  testDir: './e2e',
  testMatch: ['**/routing.spec.ts', '**/desktop-routing.spec.ts'],
  workers: 1,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5178', channel: 'chrome' },
  webServer: {
    command: 'node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 5178 --strictPort',
    url: 'http://127.0.0.1:5178',
    reuseExistingServer: false,
  },
  projects: [{ name: 'desktop-hd', use: { ...devices['Desktop Chrome'] } }],
});
