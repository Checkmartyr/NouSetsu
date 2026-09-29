import { expect, test, type Page } from '@playwright/test';

type UpdaterOutcome = 'none' | 'error';

async function assertProductionReleaseFallback(page: Page, outcome: UpdaterOutcome) {
  const releaseChecks: string[] = [];

  await page.addInitScript((updaterOutcome) => {
    Object.defineProperty(window, '__TAURI_INTERNALS__', {
      configurable: true,
      value: {
        invoke: async (command: string) => {
          if (command === 'plugin:updater|check' && updaterOutcome === 'error') {
            throw new Error('Signed updater feed unavailable');
          }
          return null;
        },
      },
    });
  }, outcome);
  page.on('request', (request) => {
    if (request.url() === 'http://127.0.0.1:5174/api/updates/latest') {
      releaseChecks.push(request.url());
    }
  });
  await page.route('http://127.0.0.1:5174/**', async (route) => {
    if (route.request().url() === 'http://127.0.0.1:5174/api/updates/latest') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: { 'access-control-allow-origin': '*' },
        body: JSON.stringify({
          current_version: '0.4.8',
          latest_version: '0.4.9',
          update_available: true,
          release_name: 'NouSetsu 0.4.9',
          release_notes: 'Production release notes',
          release_url: 'https://github.com/Checkmartyr/NouSetsu/releases/latest',
          assets: [],
        }),
      });
      return;
    }
    await route.abort();
  });

  await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'App Updates' }).click();
  await page.getByRole('button', { name: 'Check for Updates' }).click();

  await expect(page.getByText('NouSetsu 0.4.9', { exact: true })).toBeVisible();
  await expect(page.getByText('Production release notes', { exact: true })).toBeVisible();
  expect(releaseChecks).toHaveLength(1);
}

test('production updater falls back to the release API when the signed feed has no update', async ({ page }) => {
  await assertProductionReleaseFallback(page, 'none');
});

test('production updater falls back to the release API when the signed feed errors', async ({ page }) => {
  await assertProductionReleaseFallback(page, 'error');
});
