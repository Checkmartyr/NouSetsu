import { expect, test } from '@playwright/test';
import { mockBackend, path, projectPaths, traceChapters } from './helpers/mockBackend';

test('reader deep links select the exact root/volume pair and refresh without repeating service verification', async ({ page }) => {
  const backend = await mockBackend(page);
  await page.goto(path('reader', { chapter: '1' }));
  const selector = page.getByRole('combobox', { name: 'Select chapter to read' });
  await expect(selector).toHaveValue('::1');
  await expect(page.locator('article')).toContainText('Root chapter 1');
  expect(backend.environment).toBe(1);
  await selector.selectOption('Volume 01::1');
  await expect(page).toHaveURL(/folder=Volume\+01/);
  await expect(page.locator('article')).toContainText('Volume 01 chapter 1');
  await page.reload();
  await expect(selector).toHaveValue('Volume 01::1');
  await expect(page.locator('article')).toContainText('Volume 01 chapter 1');
  expect(backend.environment).toBe(1);
  expect(backend.desktop).toBe(2);
  await page.goBack();
  await expect(selector).toHaveValue('::1');
  await expect(page.locator('article')).toContainText('Root chapter 1');
  await page.goForward();
  await expect(selector).toHaveValue('Volume 01::1');
  expect(new URL(page.url()).searchParams.get('project')).toBe(projectPaths[0]);
  expect(backend.unexpected).toEqual([]);
});

test('reader next/previous updates the URL and rejects a delayed older response', async ({ page }) => {
  const backend = await mockBackend(page, { delayContent: true });
  await page.goto(path('reader', { chapter: '1', folder: 'Volume 01' }));
  const selector = page.getByRole('combobox', { name: 'Select chapter to read' });
  await expect(selector).toHaveValue('Volume 01::1');
  await page.getByRole('button', { name: 'Next Chapter', exact: true }).click();
  await expect(page).toHaveURL(/chapter=2/);
  await expect(page.locator('article')).toContainText('Volume 01 chapter 2');
  await expect.poll(() => backend.delayedContentCompleted).toBe(true);
  await expect(page.locator('article')).toContainText('Volume 01 chapter 2');
  await page.getByRole('button', { name: 'Previous Chapter', exact: true }).click();
  await expect(page).toHaveURL(/chapter=1/);
  await expect(selector).toHaveValue('Volume 01::1');
});

test('workspace history preserves reader selections and Bible section filters', async ({ page }) => {
  await mockBackend(page);
  await page.goto(path('reader', { chapter: '2', folder: 'Volume 01' }));
  await expect(page.locator('article')).toContainText('Volume 01 chapter 2');
  await page.locator('header').getByRole('button', { name: 'Novel Bible', exact: true }).click();
  await expect(page).toHaveURL(/\/bible\?/);
  await page.getByRole('button', { name: /Glossary/i }).click();
  await expect(page).toHaveURL(/section=glossary/);
  await page.getByPlaceholder('Search terms or translations...').fill('sword');
  await page.locator('header').getByRole('button', { name: 'Reader', exact: true }).click();
  await expect(page.getByRole('combobox', { name: 'Select chapter to read' })).toHaveValue('Volume 01::2');
  await page.goBack();
  await expect(page).toHaveURL(/\/bible\?.*section=glossary/);
  await expect(page.getByPlaceholder('Search terms or translations...')).toHaveValue('sword');
  await page.reload();
  await expect(page.getByPlaceholder('Search terms or translations...')).toHaveValue('sword');
});

test('Studio route selection takes precedence over restored filters and Reader panel state persists', async ({ page }) => {
  await mockBackend(page);
  await page.goto(path('studio', { chapter: '1' }));
  await expect(page.getByText(`Reading ${projectPaths[0]} Root chapter 1`, { exact: true })).toBeVisible();
  await page.getByPlaceholder('Search chapter...').fill('Root');
  await page.goto(path('studio', { chapter: '2', folder: 'Volume 01' }));
  await expect(page.getByPlaceholder('Search chapter...')).toHaveValue('Root');
  await expect(page.getByText(`Reading ${projectPaths[0]} Volume 01 chapter 2`, { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Reader Mode', exact: true }).click();
  await expect(page.getByRole('combobox', { name: 'Select chapter to read' })).toHaveValue('Volume 01::2');
  await page.getByRole('button', { name: 'Raw', exact: true }).click();
  await expect(page.getByText('Original chapter', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText('Original chapter', { exact: true })).toBeVisible();
  await page.locator('header').getByRole('button', { name: 'Studio', exact: true }).click();
  await expect(page.getByPlaceholder('Search chapter...')).toHaveValue('Root');
  await expect(page.getByText(`Reading ${projectPaths[0]} Volume 01 chapter 2`, { exact: true })).toBeVisible();
});

test('trace deep links restore chapter, trace, stage and detail, then preserve analytics mode', async ({ page }) => {
  await mockBackend(page);
  await page.goto(path('traces', { chapter: '1', folder: 'Volume 01', trace: '1-critique', stage: 'critique', detail: 'prompts' }));
  await expect(page.getByRole('combobox', { name: 'Select chapter trace' })).toHaveValue('chapter-1');
  await expect(page.locator('main').getByText('critique requested input 1', { exact: false }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Output', exact: true }).click();
  await expect(page).toHaveURL(/detail=output/);
  await expect(page.locator('main').getByText('critique output 1', { exact: false }).first()).toBeVisible();
  await page.reload();
  await expect(page.locator('main').getByText('critique output 1', { exact: false }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Project Analytics', exact: true }).click();
  await expect(page).toHaveURL(/mode=project-analytics/);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Project Token Analysis' })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('combobox', { name: 'Select chapter trace' })).toHaveValue('chapter-1');
});

test('unknown route/project/chapter selections safely canonicalize to valid data', async ({ page }) => {
  await mockBackend(page);
  await page.goto('/unknown?project=unregistered&chapter=bad&folder=missing');
  await expect(page).toHaveURL(/\/studio\?/);
  await expect(page.locator('header')).toBeVisible();
  expect(new URL(page.url()).searchParams.get('project')).toBe(projectPaths[0]);
  await page.goto(path('reader', { chapter: '999', folder: 'missing' }));
  await expect(page.getByRole('combobox', { name: 'Select chapter to read' })).toHaveValue('::1');
  await expect(page.locator('article')).toContainText('Root chapter 1');
  expect(new URL(page.url()).searchParams.get('chapter')).toBe('1');
  expect(new URL(page.url()).searchParams.has('folder')).toBe(false);
});

test('trace IDs are validated only after lazy chapter loading completes', async ({ page }) => {
  await mockBackend(page, { lazyTraces: true });
  await page.goto(path('traces', { chapter: '1', folder: 'Volume 01', trace: '1-critique', stage: 'critique', detail: 'output' }));
  await expect(page.getByRole('combobox', { name: 'Select chapter trace' })).toHaveValue('chapter-1');
  await expect(page.locator('main').getByText('critique output 1', { exact: false }).first()).toBeVisible();
  expect(new URL(page.url()).searchParams.get('trace')).toBe('1-critique');
  await page.goto(path('traces', { chapter: '1', trace: 'nonexistent', detail: 'output' }));
  await expect(page.getByRole('combobox', { name: 'Select chapter trace' })).toHaveValue('chapter-0');
  await expect(page.locator('main').getByText('drafting output 0', { exact: false }).first()).toBeVisible();
  expect(new URL(page.url()).searchParams.get('trace')).toBe('0-drafting');
});

test('settings deep link and section navigation survive refresh and Back', async ({ page }) => {
  await mockBackend(page);
  await page.goto(path('settings', { section: 'chunking' }));
  await expect(page.getByPlaceholder('800')).toBeVisible();
  await page.getByRole('button', { name: /Novel Information/i }).click();
  await expect(page).toHaveURL(/section=general/);
  await expect(page.getByPlaceholder('Ascendance of a Bookworm')).toBeVisible();
  await page.reload();
  await expect(page.getByPlaceholder('Ascendance of a Bookworm')).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/section=chunking/);
  await expect(page.getByPlaceholder('800')).toBeVisible();
});

test('unfinished settings form values are excluded from navigation snapshots', async ({ page }) => {
  await mockBackend(page);
  await page.goto(path('settings', { section: 'general' }));
  const title = page.getByPlaceholder('Ascendance of a Bookworm');
  await expect(title).toHaveValue('Novel 1');
  await title.fill('Unfinished Novel');
  expect(await page.evaluate(() => Object.values(sessionStorage).join(' '))).not.toContain('Unfinished Novel');
  await page.reload();
  await expect(title).toHaveValue('Novel 1');
  await expect(page).toHaveURL(/section=general/);
});

test('external TUI project changes replace the current route without adding history', async ({ page }) => {
  const backend = await mockBackend(page);
  await page.goto(path('reader', { chapter: '1' }));
  await expect(page.locator('article')).toContainText(projectPaths[0]);
  const historyLength = await page.evaluate(() => history.length);
  backend.active = 1;
  await expect.poll(() => new URL(page.url()).searchParams.get('project'), { timeout: 10000 }).toBe(projectPaths[1]);
  await expect(page.locator('article')).toContainText(projectPaths[1]);
  expect(await page.evaluate(() => history.length)).toBe(historyLength);
  expect(backend.switches).toEqual([]);
});

test('delayed sync registry data cannot overwrite navigation after returning from another project', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === 'mobile', 'Project selector and manual sync are hidden by the mobile layout.');
  const backend = await mockBackend(page);
  await page.goto(path('reader', { chapter: '1' }));
  await expect(page.locator('article')).toContainText(projectPaths[0]);
  // A TUI sync captures B, then stays in flight while web navigation goes A -> B -> A.
  backend.active = 1;
  backend.holdNextRegistry = true;
  await page.getByTitle('Click to refresh from project').click();
  await expect.poll(() => backend.registryHeld).toBe(true);
  backend.active = 0;
  const selector = page.getByRole('combobox', { name: 'Select active project' });
  await selector.selectOption(projectPaths[1]);
  await expect(page.locator('article')).toContainText(projectPaths[1]);
  await selector.selectOption(projectPaths[0]);
  await expect(page.locator('article')).toContainText(projectPaths[0]);
  backend.releaseRegistry?.();
  await expect.poll(() => backend.registryReleased).toBe(true);
  // Allow the completed fetch and React render to settle before checking stale-data rejection.
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(selector).toHaveValue(projectPaths[0]);
  await expect(page.locator('article')).toContainText(projectPaths[0]);
  expect(new URL(page.url()).searchParams.get('project')).toBe(projectPaths[0]);
  expect(backend.switches).toEqual([projectPaths[1], projectPaths[0]]);
});

test('project deep links switch the backend and rapid project selections are serialized', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === 'mobile', 'Project selector is hidden by the mobile layout.');
  const backend = await mockBackend(page, { delaySwitch: true });
  await page.goto(path('reader', { project: projectPaths[1], chapter: '1' }));
  const selector = page.getByRole('combobox', { name: 'Select active project' });
  await expect(selector).toHaveValue(projectPaths[1]);
  await expect.poll(() => backend.active).toBe(1);
  await expect(page.locator('article')).toContainText(projectPaths[1]);
  await selector.selectOption(projectPaths[0]);
  await expect.poll(() => backend.switches.length).toBe(2);
  await selector.selectOption(projectPaths[2]);
  await expect.poll(() => backend.active).toBe(2);
  await expect(selector).toHaveValue(projectPaths[2]);
  await expect(page.locator('article')).toContainText(projectPaths[2]);
  expect(new URL(page.url()).searchParams.get('project')).toBe(projectPaths[2]);
  expect(backend.maxConcurrentSwitches).toBe(1);
  expect(backend.switches).toEqual([projectPaths[1], projectPaths[0], projectPaths[2]]);
});

test('failed project switch retains the last valid project and displays a recovery error', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === 'mobile', 'Project selector is hidden by the mobile layout.');
  await mockBackend(page, { failSwitch: true });
  await page.goto(path('reader', { chapter: '1' }));
  const selector = page.getByRole('combobox', { name: 'Select active project' });
  await expect(page.locator('article')).toContainText(projectPaths[0]);
  await selector.selectOption(projectPaths[1]);
  await expect(page.getByText(/Failed to switch project/)).toBeVisible();
  await expect(selector).toHaveValue(projectPaths[0]);
  expect(new URL(page.url()).searchParams.get('project')).toBe(projectPaths[0]);
  await expect(page.locator('article')).toContainText(projectPaths[0]);
});

test('a bare reader URL resumes the active project navigation before bookmarks or defaults', async ({ page }) => {
  await mockBackend(page);
  await page.addInitScript(() => {
    localStorage.setItem('nousetsu_reader_settings', JSON.stringify({ theme: 'dark', fontSize: 'lg', autoSave: false }));
  });
  await page.goto(path('reader', { chapter: '2', folder: 'Volume 01' }));
  await expect(page.locator('article')).toContainText('Volume 01 chapter 2');
  expect(await page.evaluate(() => Object.keys(localStorage).some((key) => key.startsWith('nousetsu_reader_bookmark_')))).toBe(false);
  // Omit the project as well as chapter so bootstrap must restore the active-project snapshot.
  await page.goto('/reader');
  await expect(page.getByRole('combobox', { name: 'Select chapter to read' })).toHaveValue('Volume 01::2');
  await expect(page.locator('article')).toContainText('Volume 01 chapter 2');
  const url = new URL(page.url());
  expect(url.searchParams.get('project')).toBe(projectPaths[0]);
  expect(url.searchParams.get('chapter')).toBe('2');
  expect(url.searchParams.get('folder')).toBe('Volume 01');
});

test('local trace uploads remain selected while an active backend has a different trace roster', async ({ page }) => {
  const backend = await mockBackend(page);
  await page.goto(path('traces', { chapter: '1', detail: 'output' }));
  await expect(page.locator('main').getByText('drafting output 0', { exact: false }).first()).toBeVisible();
  const document = {
    ...traceChapters[0].document,
    chapter_id: 'local-chapter-9', chapter_num: 9, folder: null,
    traces: traceChapters[0].document.traces.map((trace) => ({
      ...trace, chapter_id: 'local-chapter-9', chapter_num: 9, folder: null,
      trace_id: `local-${trace.stage}-9`, raw_output: `Uploaded local ${trace.stage} chapter 9`,
    })),
  };
  await page.locator('header input[type="file"]').setInputFiles({
    name: 'chapter_0009.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(document)),
  });
  await expect(page.locator('main').getByText('Uploaded local drafting chapter 9', { exact: false }).first()).toBeVisible();
  // Returning to Traces must continue to inspect the uploaded file, rather than the backend roster.
  await page.locator('header').getByRole('button', { name: 'Reader', exact: true }).click();
  await expect(page.locator('article')).toBeVisible();
  await page.locator('header').getByRole('button', { name: 'Traces', exact: true }).click();
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(page.getByRole('combobox', { name: 'Select chapter trace' })).toHaveValue('root_ch9');
  await expect(page.locator('main').getByText('Uploaded local drafting chapter 9', { exact: false }).first()).toBeVisible();
  expect(new URL(page.url()).searchParams.get('chapter')).toBe('9');
  expect(backend.unexpected).toEqual([]);
});
