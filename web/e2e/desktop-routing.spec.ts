import { expect, test } from '@playwright/test';
import { mockBackend, path } from './helpers/mockBackend';

test('desktop runtime preserves chapter paths through reload and history', async ({ page }) => {
  const backend = await mockBackend(page);
  await page.addInitScript(() => {
    Object.defineProperty(window, '__TAURI_INTERNALS__', {
      value: { invoke: async (command: string) => command === 'plugin:app|version' ? 'test' : null },
    });
  });
  await page.goto(path('reader', { chapter: '1', folder: 'Volume 01' }));
  const reader = page.getByRole('combobox', { name: 'Select chapter to read' });
  await expect(reader).toHaveValue('Volume 01::1');
  await expect(page.locator('article')).toContainText('Volume 01 chapter 1');
  await page.getByRole('button', { name: 'Next Chapter', exact: true }).click();
  await expect(page).toHaveURL(/chapter=2/);
  await page.reload();
  await expect(reader).toHaveValue('Volume 01::2');
  await expect(page.locator('article')).toContainText('Volume 01 chapter 2');
  await page.goBack();
  await expect(reader).toHaveValue('Volume 01::1');
  expect(backend.environment).toBe(1);
  expect(backend.desktop).toBe(2);
  expect(backend.unexpected).toEqual([]);
});
