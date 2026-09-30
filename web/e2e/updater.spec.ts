import { expect, test, type Page } from '@playwright/test';

type LocalUpdaterOutcome = 'available' | 'none' | 'error';

async function openLocalUpdaterSettings(page: Page, outcome: LocalUpdaterOutcome) {
  const releaseChecks: string[] = [];

  await page.addInitScript((updaterOutcome) => {
    const updaterCalls: string[] = [];
    Object.defineProperty(window, '__updaterCalls', { value: updaterCalls });
    Object.defineProperty(window, '__failBackendStop', { value: false, writable: true });
    Object.defineProperty(window, '__TAURI_INTERNALS__', {
      configurable: true,
      value: {
        transformCallback: () => 'test-callback',
        invoke: async (command: string, args?: {
          onEvent?: {
            onmessage?: (event: { event: string; data: { contentLength?: number; chunkLength?: number } }) => void;
          };
        }) => {
          if (command === 'plugin:updater|check') {
            if (updaterOutcome === 'error') {
              throw new Error('Local updater feed unavailable');
            }
            if (updaterOutcome === 'none') return null;
            return {
              rid: 1,
              currentVersion: '0.4.8',
              version: '0.4.9',
              date: '2026-09-29T00:00:00Z',
              body: 'Local signed update',
            };
          }
          if (command === 'plugin:updater|download') {
            updaterCalls.push('download:start');
            args?.onEvent?.onmessage?.({ event: 'Started', data: { contentLength: 100 } });
            args?.onEvent?.onmessage?.({ event: 'Progress', data: { chunkLength: 100 } });
            args?.onEvent?.onmessage?.({ event: 'Finished', data: {} });
            updaterCalls.push('download:finished');
            return 2;
          }
          if (command === 'stop_backend_before_update') {
            updaterCalls.push('stop-backend');
            if ((window as typeof window & { __failBackendStop: boolean }).__failBackendStop) {
              throw new Error('A NouSetsu backend is still running');
            }
            return null;
          }
          if (command === 'plugin:updater|install') {
            updaterCalls.push('install');
            return null;
          }
          if (command === 'plugin:updater|download_and_install') {
            updaterCalls.push('download-and-install');
            return null;
          }
          if (command === 'plugin:app|version') return '0.4.8';
          return null;
        },
      },
    });
  }, outcome);
  page.on('request', (request) => {
    if (request.url() === 'http://127.0.0.1:15474/api/updates/latest') {
      releaseChecks.push(request.url());
    }
  });
  await page.route('http://127.0.0.1:15474/**', (route) => route.abort());

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

test('local update stops the backend after download and before installer launch', async ({ page }) => {
  await openLocalUpdaterSettings(page, 'available');
  await page.getByRole('button', { name: 'Install Update', exact: true }).click();

  const updaterCalls = await page.evaluate(() =>
    (window as typeof window & { __updaterCalls: string[] }).__updaterCalls,
  );
  expect(updaterCalls).toEqual(['download:start', 'download:finished', 'stop-backend', 'install']);
});

test('local update does not launch installer if the backend cannot stop', async ({ page }) => {
  await openLocalUpdaterSettings(page, 'available');
  await page.evaluate(() => {
    (window as typeof window & { __failBackendStop: boolean }).__failBackendStop = true;
  });
  await page.getByRole('button', { name: 'Install Update', exact: true }).click();

  await expect(page.getByRole('alert')).toHaveText('A NouSetsu backend is still running');
  const updaterCalls = await page.evaluate(() =>
    (window as typeof window & { __updaterCalls: string[] }).__updaterCalls,
  );
  expect(updaterCalls).toEqual(['download:start', 'download:finished', 'stop-backend']);
});
