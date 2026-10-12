import { expect, test, type Locator, type Page } from '@playwright/test';
import { chapterItem, mockBackend, path, projectPaths, sortingChapters } from './helpers/mockBackend';
import { sortDisplayChapters, sortStoryChapters } from '../src/utils/chapterOrdering';

const roster = (size: number) => Array.from({ length: size }, (_, i) => chapterItem(size - i));
const toc = (page: Page) => page.getByRole('navigation', { name: 'Table of contents' });
const rows = (page: Page) => toc(page).locator('[data-chapter-num]');
const selector = (page: Page) => page.getByRole('combobox', { name: 'Select chapter to read' });
const sort = (page: Page) => page.getByRole('combobox', { name: 'Sort Reader chapters' });
async function identities(locator: Locator) {
  return locator.evaluateAll((elements) => elements.map((el) => `${el.getAttribute('data-chapter-folder')}::${el.getAttribute('data-chapter-num')}`));
}
async function openContents(page: Page) {
  await page.getByRole('button', { name: 'Contents', exact: true }).click();
  await expect(toc(page)).toBeVisible();
}
async function closeContents(page: Page) {
  await toc(page).getByRole('button', { name: 'Close contents' }).click();
  await expect(toc(page)).not.toBeVisible();
}

for (const size of [0, 1, 50, 51, 101]) {
  test(`ToC renders at most 50 rows for ${size} chapters and page browsing preserves reading`, async ({ page }, testInfo) => {
    const backend = await mockBackend(page, { chapters: roster(size) });
    await page.goto(path('reader', { chapter: '1' }));
    if (size > 0) {
      await expect(page.locator('article')).toContainText('Root chapter 1');
      await expect(page.getByRole('button', { name: 'Bookmarked chapter', exact: true })).toBeVisible();
    }
    await openContents(page);
    await expect(rows(page)).toHaveCount(Math.min(size, 50));
    if (size === 51) await page.screenshot({ path: testInfo.outputPath('reader-contents.png'), animations: 'disabled' });
    const pagination = toc(page).locator('[aria-label="Pagination Navigation"]');
    if (size === 0) {
      await expect(toc(page)).toContainText('No chapters found');
      await expect(pagination).toHaveCount(0);
    } else {
      await expect(pagination).toContainText(`Showing 1–${Math.min(size, 50)} of ${size} chapters`);
      await expect(toc(page).getByRole('combobox')).toHaveCount(1);
      const originalUrl = page.url();
      const originalBookmark = await page.evaluate(() => Object.entries(localStorage).filter(([key]) => key.startsWith('nousetsu_reader_bookmark_')));
      if (size > 50) {
        await pagination.getByRole('button', { name: 'Next page', exact: true }).click();
        await expect(rows(page)).toHaveCount(Math.min(size - 50, 50));
        await expect(pagination).toContainText(`Showing 51–${Math.min(size, 100)} of ${size} chapters`);
        if (size > 100) await pagination.getByRole('button', { name: 'Last page', exact: true }).click();
        await expect(pagination.getByRole('button', { name: 'Last page', exact: true })).toBeDisabled();
        await expect(rows(page)).toHaveCount(size % 50 || 50);
        expect(page.url()).toBe(originalUrl);
        expect(await page.evaluate(() => Object.entries(localStorage).filter(([key]) => key.startsWith('nousetsu_reader_bookmark_')))).toEqual(originalBookmark);
        await closeContents(page);
        await expect(page.locator('article')).toContainText('Root chapter 1');
        await openContents(page);
        await expect(rows(page).first()).toHaveAttribute('data-chapter-num', '1');
      } else {
        await expect(pagination.getByRole('button', { name: 'Next page', exact: true })).toBeDisabled();
      }
    }
    expect(backend.unexpected).toEqual([]);
  });
}

test('every display sort preserves exact chapter identity and natural story navigation', async ({ page }) => {
  const frozenRoster = sortingChapters.map((chapter) => ({ ...chapter }));
  const snapshot = JSON.stringify(frozenRoster);
  frozenRoster.forEach(Object.freeze);
  Object.freeze(frozenRoster);
  sortDisplayChapters(frozenRoster, 'title-desc');
  sortStoryChapters(frozenRoster);
  expect(JSON.stringify(frozenRoster)).toBe(snapshot);
  const backend = await mockBackend(page, { chapters: sortingChapters });
  await page.goto(path('reader', { chapter: '2' }));
  const expectations = {
    'number-asc': ['::1', 'Volume 2::1', 'Volume 10::1', '::2', 'Volume 2::2', 'Volume 2::10'],
    'number-desc': ['Volume 2::10', '::2', 'Volume 2::2', '::1', 'Volume 2::1', 'Volume 10::1'],
    'title-asc': ['Volume 2::1', '::1', 'Volume 2::2', 'Volume 2::10', '::2', 'Volume 10::1'],
    'title-desc': ['Volume 10::1', '::2', 'Volume 2::10', '::1', 'Volume 2::2', 'Volume 2::1'],
  };
  for (const [value, expected] of Object.entries(expectations)) {
    await openContents(page);
    await sort(page).selectOption(value);
    await expect.poll(() => identities(rows(page))).toEqual(expected);
    await expect(toc(page).locator('[data-chapter-num="2"][data-chapter-folder=""]')).toHaveAttribute('aria-current', 'page');
    await expect(toc(page)).toContainText('Alpha 1.txt');
    await closeContents(page);
    await expect(selector(page)).toHaveValue('::2');
    await selector(page).selectOption('::2');
    await expect(page.locator('article')).toContainText('Root chapter 2');
    await expect.poll(() => selector(page).locator('option').evaluateAll((options) => options.map((option) => (option as HTMLOptionElement).value))).toEqual(expected);
    await page.getByRole('button', { name: 'Next Chapter', exact: true }).click();
    await expect(selector(page)).toHaveValue('Volume 2::1');
    await expect(page.locator('article')).toContainText('Volume 2 chapter 1');
    await page.getByRole('button', { name: 'Previous Chapter', exact: true }).click();
    await expect(selector(page)).toHaveValue('::2');
  }
  await selector(page).selectOption('Volume 2::10');
  await page.getByRole('button', { name: 'Next Chapter', exact: true }).click();
  await expect(selector(page)).toHaveValue('Volume 10::1');
  await expect(page.locator('article')).toContainText('Volume 10 chapter 1');
  expect(backend.unexpected).toEqual([]);
});

test('deep links, history, bookmarks and sorts reveal the current ToC page', async ({ page }) => {
  const backend = await mockBackend(page, { chapters: roster(101) });
  await page.addInitScript(() => localStorage.setItem('nousetsu_reader_settings', JSON.stringify({ theme: 'dark', fontSize: 'lg', autoSave: false })));
  await page.goto(path('reader', { chapter: '75' }));
  await expect(page.locator('article')).toContainText('Root chapter 75');
  await openContents(page);
  await expect(toc(page).locator('[data-chapter-num="75"]')).toHaveAttribute('aria-current', 'page');
  await expect(toc(page)).toContainText('Showing 51–100 of 101 chapters');
  await sort(page).selectOption('number-desc');
  await expect(toc(page)).toContainText('Showing 1–50 of 101 chapters');
  await closeContents(page);
  await page.getByRole('button', { name: 'Save current reading chapter', exact: true }).click();
  await selector(page).selectOption('::1');
  await page.goBack();
  await expect(selector(page)).toHaveValue('::75');
  await openContents(page);
  await expect(toc(page).locator('[data-chapter-num="75"]')).toHaveAttribute('aria-current', 'page');
  await closeContents(page);
  await page.goForward();
  await expect(selector(page)).toHaveValue('::1');
  await page.getByRole('button', { name: /Resume Ch\.75/ }).click();
  await expect(selector(page)).toHaveValue('::75');
  await page.goto(path('reader'));
  await expect(selector(page)).toHaveValue('::75');
  await openContents(page);
  await expect(toc(page).locator('[data-chapter-num="75"]')).toHaveAttribute('aria-current', 'page');
  await sort(page).selectOption('number-asc');
  await closeContents(page);
  await selector(page).selectOption('::50');
  await openContents(page);
  await expect(toc(page)).toContainText('Showing 1–50 of 101 chapters');
  await closeContents(page);
  await page.getByRole('button', { name: 'Next Chapter', exact: true }).click();
  await expect(selector(page)).toHaveValue('::51');
  await openContents(page);
  await expect(toc(page)).toContainText('Showing 51–100 of 101 chapters');
  await expect(toc(page).locator('[data-chapter-num="51"]')).toHaveAttribute('aria-current', 'page');
  await closeContents(page);
  await page.getByRole('button', { name: 'Previous Chapter', exact: true }).click();
  await expect(selector(page)).toHaveValue('::50');
  await openContents(page);
  await expect(toc(page)).toContainText('Showing 1–50 of 101 chapters');
  expect(backend.unexpected).toEqual([]);
});

test('Reader sort survives reload and tab return, remains project-scoped, and rejects unsupported snapshots', async ({ page }) => {
  const backend = await mockBackend(page, { chapters: sortingChapters });
  await page.addInitScript((project) => {
    if (!sessionStorage.getItem('reader-sort-test-seeded')) {
      sessionStorage.setItem(`nousetsu_navigation:v1:${project}:reader:chapterSort`, JSON.stringify('unsupported'));
      sessionStorage.setItem('reader-sort-test-seeded', 'true');
    }
  }, projectPaths[0]);
  await page.goto(path('reader', { chapter: '1' }));
  await openContents(page);
  await expect(sort(page)).toHaveValue('number-asc');
  await sort(page).selectOption('title-desc');
  await closeContents(page);
  await page.locator('header').getByRole('button', { name: 'Studio', exact: true }).click();
  await expect(page.getByRole('combobox', { name: 'Sort Studio chapters' })).toHaveValue('number-asc');
  await page.locator('header').getByRole('button', { name: 'Reader', exact: true }).click();
  await openContents(page);
  await expect(sort(page)).toHaveValue('title-desc');
  await closeContents(page);
  await page.reload();
  await openContents(page);
  await expect(sort(page)).toHaveValue('title-desc');
  await closeContents(page);
  await page.goto(`/reader?${new URLSearchParams({ project: projectPaths[1], chapter: '1' })}`);
  await openContents(page);
  await expect(sort(page)).toHaveValue('number-asc');
  await closeContents(page);
  await page.goto(path('reader', { chapter: '1' }));
  await openContents(page);
  await expect(sort(page)).toHaveValue('title-desc');
  expect(backend.unexpected).toEqual([]);
});

test('untranslated Unicode chapters remain reachable and a shortened roster has a valid page', async ({ page }) => {
  const untranslated = { ...chapterItem(51, null, '世界'), translated_exists: false, is_completed: false, status: 'PENDING' as const };
  const backend = await mockBackend(page, { chapters: [...roster(50), untranslated] });
  await page.goto(path('reader', { chapter: '1' }));
  await openContents(page);
  await toc(page).getByRole('button', { name: 'Next page', exact: true }).click();
  await expect(rows(page)).toHaveCount(1);
  await expect(rows(page)).toContainText('Not translated');
  await rows(page).click();
  // Selection dismisses only the mobile panel.
  await expect(selector(page)).toHaveValue('::51');
  await expect(page.getByText('Chapter 51 has not been translated yet.', { exact: true })).toBeVisible();
  backend.setChapters(roster(1));
  await page.reload();
  await expect(selector(page)).toHaveValue('::1');
  await openContents(page);
  await expect(rows(page)).toHaveCount(1);
  await expect(toc(page)).toContainText('Showing 1–1 of 1 chapters');
  expect(backend.unexpected).toEqual([]);
});

test('mobile Contents contains keyboard focus and Raw preserves a readable article', async ({ page }, testInfo) => {
  test.skip((page.viewportSize()?.width || 0) >= 768, 'Mobile modal contract');
  const backend = await mockBackend(page, { chapters: roster(51) });
  await page.goto(path('reader', { chapter: '1' }));
  await expect(page.locator('article')).toContainText('Root chapter 1');
  await openContents(page);
  const dialog = page.getByRole('dialog', { name: 'Table of contents' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Close contents' })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  expect(await dialog.evaluate((el) => el.contains(document.activeElement))).toBe(true);
  await page.keyboard.press('Tab');
  await expect(dialog.getByRole('button', { name: 'Close contents' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(page.getByRole('button', { name: 'Contents', exact: true })).toBeFocused();
  await page.getByRole('button', { name: 'Raw', exact: true }).click();
  await expect(page.getByText('Original chapter', { exact: true })).toBeVisible();
  for (const theme of ['Sepia Theme', 'Light Theme', 'Dark Warm Canvas Theme']) {
    await page.getByRole('button', { name: theme, exact: true }).click();
    await expect(page.locator('article')).toBeVisible();
    const box = await page.locator('article').boundingBox();
    expect(box?.width).toBeGreaterThan(250);
    expect(box?.height).toBeGreaterThan(20);
  }
  await page.screenshot({ path: testInfo.outputPath('reader-mobile-raw.png'), animations: 'disabled' });
  expect(backend.unexpected).toEqual([]);
});
