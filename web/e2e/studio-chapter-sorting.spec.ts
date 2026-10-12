import { expect, test, type Page } from '@playwright/test';
import { chapterItem, mockBackend, path, projectPaths, sortingChapters } from './helpers/mockBackend';

const list = (page: Page) => page.getByRole('region', { name: 'Studio chapters' });
const rows = (page: Page) => list(page).locator('[data-chapter-num]');
const sort = (page: Page) => page.getByRole('combobox', { name: 'Sort Studio chapters' });
const volumeFilter = (page: Page) => page.locator('select').filter({ has: page.locator('option[value="all"]', { hasText: 'All Volumes' }) });
const statusFilter = (page: Page) => page.locator('select').filter({ has: page.locator('option[value="all"]', { hasText: 'All Statuses' }) });
async function identities(page: Page) {
  return rows(page).evaluateAll((elements) => elements.map((el) => `${el.getAttribute('data-chapter-folder')}::${el.getAttribute('data-chapter-num')}`));
}

test('Studio sorts inside naturally ordered volume groups and flat filtered lists without changing selection', async ({ page }, testInfo) => {
  const backend = await mockBackend(page, { chapters: sortingChapters.map((chapter) =>
    chapter.folder === 'Volume 2' && chapter.chapter_num === 1
      ? { ...chapter, status: 'PENDING', is_completed: false } : chapter) });
  await page.addInitScript((project) => sessionStorage.setItem(`nousetsu_navigation:v1:${project}:studio:chapterSort`, JSON.stringify('unsupported')), projectPaths[0]);
  await page.goto(path('studio', { chapter: '2', folder: 'Volume 2' }));
  await expect(sort(page)).toBeVisible();
  await expect(sort(page)).toHaveValue('number-asc');
  await page.getByRole('button', { name: 'Expand All', exact: true }).click();
  const expectations = {
    'number-asc': ['::1', '::2', 'Volume 2::1', 'Volume 2::2', 'Volume 2::10', 'Volume 10::1'],
    'number-desc': ['::2', '::1', 'Volume 2::10', 'Volume 2::2', 'Volume 2::1', 'Volume 10::1'],
    'title-asc': ['::1', '::2', 'Volume 2::1', 'Volume 2::2', 'Volume 2::10', 'Volume 10::1'],
    'title-desc': ['::2', '::1', 'Volume 2::10', 'Volume 2::2', 'Volume 2::1', 'Volume 10::1'],
  };
  for (const [value, expected] of Object.entries(expectations)) {
    await sort(page).selectOption(value);
    await expect.poll(() => identities(page)).toEqual(expected);
    await expect(list(page).locator('[aria-current="page"]')).toHaveAttribute('data-chapter-folder', 'Volume 2');
    await expect(list(page).locator('[aria-current="page"]')).toHaveAttribute('data-chapter-num', '2');
    await expect(page.getByText(`Reading ${projectPaths[0]} Volume 2 chapter 2`, { exact: true })).toBeVisible();
  }
  await page.screenshot({ path: testInfo.outputPath('studio-sorting.png'), animations: 'disabled' });
  await list(page).locator('[data-chapter-num="1"][data-chapter-folder=""]').click();
  await expect(page.getByText(`Reading ${projectPaths[0]} Root chapter 1`, { exact: true })).toBeVisible();
  await list(page).locator('[data-chapter-num="1"][data-chapter-folder="Volume 10"]').click();
  await expect(page.getByText(`Reading ${projectPaths[0]} Volume 10 chapter 1`, { exact: true })).toBeVisible();
  await volumeFilter(page).selectOption('Volume 2');
  for (const [value, expected] of Object.entries(expectations)) {
    await sort(page).selectOption(value);
    await expect.poll(() => identities(page)).toEqual(expected.filter((key) => key.startsWith('Volume 2::')));
  }
  await page.getByPlaceholder('Search chapter...').fill('Alpha');
  await expect(rows(page)).toHaveCount(3);
  await statusFilter(page).selectOption('completed');
  await expect(rows(page)).toHaveCount(2);
  await expect(sort(page)).toHaveValue('title-desc');
  await list(page).locator('[data-chapter-num="10"]').click();
  await expect(page.getByText(`Reading ${projectPaths[0]} Volume 2 chapter 10`, { exact: true })).toBeVisible();
  await page.getByPlaceholder('Search chapter...').fill('');
  await statusFilter(page).selectOption('all');
  await volumeFilter(page).selectOption('all');
  await page.getByRole('button', { name: 'Expand All', exact: true }).click();
  await page.getByTitle('Translate all pending chapters in Volume 2', { exact: true }).click();
  await expect.poll(() => backend.translationPayloads.length).toBe(1);
  expect(backend.translationPayloads[0]).toEqual({ project_path: projectPaths[0], folder: 'Volume 2', force_retranslate: false });
  await expect(sort(page)).toHaveValue('title-desc');
  expect(backend.unexpected).toEqual([]);
});

test('sort preserves routed selection hidden by restored filters while user filters still repair selection', async ({ page }) => {
  const backend = await mockBackend(page, { chapters: sortingChapters });
  await page.goto(path('studio', { chapter: '1' }));
  await page.getByPlaceholder('Search chapter...').fill('Beta');
  await expect(page.getByText(`Reading ${projectPaths[0]} Root chapter 2`, { exact: true })).toBeVisible();
  await page.goto(path('studio', { chapter: '1', folder: 'Volume 10' }));
  await expect(page.getByPlaceholder('Search chapter...')).toHaveValue('Beta');
  await expect(page.getByText(`Reading ${projectPaths[0]} Volume 10 chapter 1`, { exact: true })).toBeVisible();
  await sort(page).selectOption('title-desc');
  await expect(page.getByText(`Reading ${projectPaths[0]} Volume 10 chapter 1`, { exact: true })).toBeVisible();
  await expect(rows(page)).toHaveCount(1);
  await page.reload();
  await expect(sort(page)).toHaveValue('title-desc');
  await expect(page.getByText(`Reading ${projectPaths[0]} Volume 10 chapter 1`, { exact: true })).toBeVisible();
  await page.getByPlaceholder('Search chapter...').fill('Alpha');
  await expect(page).not.toHaveURL(/folder=Volume\+10/);
  await expect(rows(page)).toHaveCount(4);
  await page.goto(`/studio?${new URLSearchParams({ project: projectPaths[1], chapter: '1' })}`);
  await expect(sort(page)).toHaveValue('number-asc');
  await expect(page.getByPlaceholder('Search chapter...')).toHaveValue('');
  await page.goto(path('studio', { chapter: '1', folder: 'Volume 10' }));
  await expect(sort(page)).toHaveValue('title-desc');
  expect(backend.unexpected).toEqual([]);
});

test('refresh and local upload retain sort and translation payloads keep chapter and folder semantics', async ({ page }) => {
  const initial = [chapterItem(2, 'Volume 2', 'Beta'), chapterItem(1, 'Volume 2', 'Gamma')];
  const added = chapterItem(10, 'Volume 2', 'Alpha');
  const backend = await mockBackend(page, { chapters: initial, uploadChapters: [...initial, added] });
  await page.goto(path('studio', { chapter: '2', folder: 'Volume 2' }));
  await sort(page).selectOption('title-asc');
  backend.setChapters([{ ...initial[0], title: 'Zulu' }, initial[1]]);
  await page.getByTitle('Refresh chapter list', { exact: true }).click();
  await expect.poll(() => identities(page)).toEqual(['Volume 2::1', 'Volume 2::2']);
  await expect(sort(page)).toHaveValue('title-asc');
  await expect(list(page).locator('[aria-current="page"]')).toHaveAttribute('data-chapter-num', '2');
  await list(page).locator('[data-chapter-num="2"]').getByTitle('Translate only this chapter', { exact: true }).click();
  await expect.poll(() => backend.translationPayloads.length).toBe(1);
  expect(backend.translationPayloads[0]).toMatchObject({ project_path: projectPaths[0], chapter: 2, folder: 'Volume 2' });
  expect(Object.keys(backend.translationPayloads[0]).sort()).toEqual(['chapter', 'folder', 'force_retranslate', 'project_path']);
  await page.getByTitle('Upload chapter files', { exact: true }).click();
  await page.locator('input[type="file"]').first().setInputFiles({ name: '0010.txt', mimeType: 'text/plain', buffer: Buffer.from('New chapter') });
  await page.getByRole('button', { name: /Upload 1/ }).click();
  await expect.poll(() => backend.uploadPayloads.length).toBe(1);
  await expect.poll(() => identities(page)).toEqual(['Volume 2::10', 'Volume 2::2', 'Volume 2::1']);
  await expect(sort(page)).toHaveValue('title-asc');
  expect(backend.uploadPayloads[0]).toMatchObject({ project_path: projectPaths[0], folder: 'Volume 2', files: [{ name: '0010.txt', content: 'New chapter' }] });
  expect(backend.unexpected).toEqual([]);
});
