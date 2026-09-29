import { expect, test, type Page } from '@playwright/test';

type LocalUpdaterOutcome = 'available' | 'none' | 'error';

async function openLocalUpdaterSettings(page: Page, outcome: LocalUpdaterOutcome) {
  const releaseChecks: string[] = [];

  await page.addInitScript((updaterOutcome) => {
    Object.defineProperty(window, '__TAURI_INTERNALS__', {
      configurable: true,
      value: {
        invoke: async (command: string) => {
          if (command === 'plugin:updater|check') {
            if (updaterOutcome === 'error') {
              throw new Error('Local updater feed unavailable');
            }
            if (updaterOutcome === 'none') return null;
            return {
              currentVersion: '0.4.8',
              version: '0.4.9',
              date: '2026-09-29T00:00:00Z',
              body: 'Local signed update',
            };
          }
          if (command === 'plugin:app|version') return '0.4.8';
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
  await page.route('http://127.0.0.1:5174/**', (route) => route.abort());

  await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'App Updates' }).click();
  await page.getByRole('button', { name: 'Check for Updates' }).click();

  return releaseChecks;
}

test('local updater reports no update without calling the release API', async ({ page }) => {
  const releaseChecks = await openLocalUpdaterSettings(page, 'none');

  await expect(page.getByText('You are up to date', { exact: true })).toBeVisible();
  expect(releaseChecks).toHaveLength(0);
});

test('local updater errors stay local instead of calling the release API', async ({ page }) => {
  const releaseChecks = await openLocalUpdaterSettings(page, 'error');

  await expect(page.getByRole('alert')).toHaveText('Local updater feed unavailable');
  expect(releaseChecks).toHaveLength(0);
});

test('local update is presented for in-app installation without release API fallback', async ({ page }) => {
  const releaseChecks = await openLocalUpdaterSettings(page, 'available');

  await expect(page.getByText('Installed: 0.4.8')).toBeVisible();
  await expect(page.getByText('Latest: 0.4.9')).toBeVisible();
  await expect(page.getByText('NouSetsu 0.4.9', { exact: true })).toBeVisible();
  await expect(page.getByText('Local signed update', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Install Update', exact: true })).toBeVisible();
  expect(releaseChecks).toHaveLength(0);
});
