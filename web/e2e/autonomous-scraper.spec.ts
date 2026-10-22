import { expect, test, type Page } from '@playwright/test';

const projectPath = 'C:/mock-projects/Novel';
const terminal = {
  task_id: 'fixture-job', status: 'partial', stage: 'partial', progress_percent: 100,
  current_chapter: 2, total_chapters: 2, saved: 1, skipped: 0, failed: 1, blocked: 0,
  message: 'Saved 1, failed 1. Status: partial.', completed_files: ['0001 - Chapter 1.md'],
};

async function openUpload(page: Page, jobs: unknown[] = []) {
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const payload = path === '/api/folders' ? { folders: ['raw_chapters'], default_folder: 'raw_chapters' }
      : path === '/api/scraper/check' ? { available: true }
      : path === '/api/scraper/jobs' ? { jobs } : undefined;
    await route.fulfill(payload ? { json: payload } : { status: 404, json: { detail: 'Unexpected mock request' } });
  });
  await page.route('**/__scraper-test', (route) => route.fulfill({
    contentType: 'text/html', body: `<!doctype html><html><body><div id="root"></div>
    <script type="module">
      import RefreshRuntime from '/@react-refresh';
      RefreshRuntime.injectIntoGlobalHook(window);
      window.$RefreshReg$ = () => {}; window.$RefreshSig$ = () => type => type;
      window.__vite_plugin_react_preamble_installed__ = true;
    </script><script type="module">
      import React from '/node_modules/.vite/deps/react.js';
      import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
      import { UploadModal } from '/src/components/UploadModal.tsx';
      import '/src/index.css';
      ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(React.StrictMode, null,
        React.createElement(UploadModal, { isOpen: true, activeProjectPath: '${projectPath}',
          onClose: () => {}, onUploadSuccess: () => {} })));
    </script></body></html>`,
  }));
  await page.goto('/__scraper-test');
  await page.getByRole('button', { name: /URL/ }).click();
}

test('a URL can extract without inspection and a partial result stays reviewable', async ({ page }) => {
  await openUpload(page);
  let extraction: Record<string, unknown> | undefined;
  let polls = 0;
  await page.route('**/api/scraper/extract', async (route) => {
    extraction = route.request().postDataJSON();
    await route.fulfill({ json: { success: true, task_id: terminal.task_id } });
  });
  await page.route('**/api/scraper/status/**', async (route) => {
    polls++;
    await route.fulfill({ json: terminal });
  });
  await page.getByPlaceholder(/https:\/\//).fill('https://fixture.test/novel');
  await page.getByRole('button', { name: 'Scrape & Import' }).click();
  await expect(page.getByText(terminal.message, { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Resume extraction' })).toBeVisible();
  expect(extraction).toMatchObject({ url: 'https://fixture.test/novel', project_path: projectPath, overwrite: false });
  expect(extraction?.inspection_id).toBeUndefined();
  const stoppedAt = polls;
  await page.waitForTimeout(1300);
  expect(polls).toBe(stoppedAt);
});

test('range progress uses the selected chapter count and stays within the bar', async ({ page }) => {
  await openUpload(page);
  const chapters = Array.from({ length: 110 }, (_, index) => ({
    index: index + 1, title: `Chapter ${index + 1}`, url: `https://fixture.test/novel/${index + 1}`,
  }));
  await page.route('**/api/scraper/inspect', (route) => route.fulfill({ json: {
    success: true, url: 'https://fixture.test/novel', novel_title: 'Fixture Novel', total_chapters: 110,
    chapters, is_complete: true,
  } }));

  let extraction: Record<string, unknown> | undefined;
  let extractionCount = 0;
  let finish = false;
  let holdNextStatus = false;
  let releaseHeldStatus: (() => void) | undefined;
  await page.route('**/api/scraper/extract', async (route) => {
    extraction = route.request().postDataJSON();
    extractionCount++;
    await route.fulfill({ json: { success: true, task_id: `${terminal.task_id}-${extractionCount}` } });
  });
  await page.route('**/api/scraper/status/**', async (route) => {
    if (holdNextStatus) {
      holdNextStatus = false;
      await new Promise<void>((resolve) => { releaseHeldStatus = resolve; });
    }
    await route.fulfill({ json: finish ? terminal : {
      ...terminal, status: 'running', stage: 'downloading', progress_percent: 10,
      current_chapter: 1, total_chapters: 10, message: 'Downloading selected chapters',
    } });
  });

  await page.getByPlaceholder(/https:\/\//).fill('https://fixture.test/novel');
  await page.getByRole('button', { name: 'Inspect TOC' }).click();
  await expect(page.getByText('110 Chapters')).toBeVisible();
  await page.getByLabel('Range', { exact: true }).check();
  const rangeInputs = page.locator('input[type="number"]');
  await rangeInputs.nth(0).fill('101');
  await rangeInputs.nth(1).fill('110');
  await page.getByRole('button', { name: 'Scrape & Import' }).click();

  await expect(page.getByText('downloading: 10%', { exact: true })).toBeVisible();
  await expect(page.locator('div[style="width: 10%;"]')).toBeVisible();
  expect(extraction).toMatchObject({ start_chapter: 101, end_chapter: 110 });

  finish = true;
  await expect(page.getByText(terminal.message, { exact: true }).first()).toBeVisible();

  finish = false;
  holdNextStatus = true;
  await page.getByRole('button', { name: 'Scrape & Import' }).click();
  await expect.poll(() => releaseHeldStatus !== undefined).toBe(true);
  await expect(page.getByText('partial: 100%', { exact: true })).toHaveCount(0);
  releaseHeldStatus?.();
  await expect(page.getByText('downloading: 10%', { exact: true })).toBeVisible();
});

test('a persisted paused job resumes and an active job can be cancelled', async ({ page }) => {
  await openUpload(page, [{ ...terminal, status: 'paused' }]);
  let action = '';
  let cancelled = false;
  await page.route('**/api/scraper/resume/**', async (route) => {
    action = 'resume';
    await route.fulfill({ json: { success: true } });
  });
  await page.route('**/api/scraper/cancel/**', async (route) => {
    cancelled = true;
    await route.fulfill({ json: { success: true } });
  });
  await page.route('**/api/scraper/status/**', async (route) => {
    await route.fulfill({ json: { ...terminal, status: cancelled ? 'cancelled' : 'running', stage: 'downloading' } });
  });
  await page.getByRole('button', { name: 'Resume extraction' }).click();
  await expect(page.getByRole('button', { name: 'Stop extraction' })).toBeVisible();
  expect(action).toBe('resume');
  await page.getByRole('button', { name: 'Stop extraction' }).click();
  await expect(page.getByRole('button', { name: 'Resume extraction' })).toBeVisible();
  expect(cancelled).toBe(true);
});
