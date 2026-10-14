import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: 'settings-audit.spec.ts',
  workers: 1,
  fullyParallel: false,
  timeout: 120_000,
  outputDir: '../audit-results/settings-repair/browser-artifacts',
  reporter: [['list'], ['json', { outputFile: '../audit-results/settings-repair/browser-playwright.json' }]],
  use: { channel: 'chrome', viewport: { width: 1440, height: 900 }, actionTimeout: 15_000, screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  webServer: [
    { command: 'uv run --no-sync python scripts/audit/settings_fixture_server.py --port 5186 --mode dev', cwd: '..', url: 'http://127.0.0.1:5186/api/audit/fixture', timeout: 120_000, reuseExistingServer: false },
    { command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5187 --strictPort', url: 'http://127.0.0.1:5187', env: { VITE_API_PORT: '5186' }, reuseExistingServer: false },
    { command: 'uv run --no-sync python scripts/audit/settings_fixture_server.py --port 5188 --mode built', cwd: '..', url: 'http://127.0.0.1:5188/api/audit/fixture', timeout: 120_000, reuseExistingServer: false },
  ],
  projects: [
    { name: 'web-dev', use: { baseURL: 'http://127.0.0.1:5187' } },
    { name: 'web-built', use: { baseURL: 'http://127.0.0.1:5188' } },
  ],
});
