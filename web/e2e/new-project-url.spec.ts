import { expect, test, type Page } from '@playwright/test';

const novelUrl = 'https://ncode.syosetu.com/n1234aa/';
const project = {
  path: 'C:/mock-projects/Hoshi no Monogatari', name: 'Hoshi no Monogatari',
  title: 'Hoshi no Monogatari', genre: 'general', source_language: 'Japanese',
  target_language: 'Thai', has_traces: false, trace_count: 0, latest_trace_mtime: 0,
};

function inspection(url = novelUrl, romanizedTitle = '  Hoshi no Monogatari  ') {
  return {
    success: true, url, novel_title: '星の物語', romanized_title: romanizedTitle,
    author: 'Mock Author', total_chapters: 3,
    chapters: [1, 2, 3].map((index) => ({ index, title: `Chapter ${index}`, url: `${url}${index}/` })),
  };
}

// Exercise the real modal in React StrictMode without booting or changing any host project.
async function openModal(page: Page) {
  page.on('pageerror', (error) => console.error('Modal harness error:', error.message));
  await page.route('**/api/**', (route) => route.fulfill({ status: 404, json: { detail: 'Unexpected mock request' } }));
  await page.route('**/api/scraper/check', (route) => route.fulfill({ json: { available: true } }));
  await page.route('**/api/scraper/inspect', (route) => route.fulfill({ json: inspection() }));
  await page.route('**/__new-project-test', (route) => route.fulfill({
    contentType: 'text/html',
    body: `<!doctype html><html><body><div id="root"></div><script type="module">
      import RefreshRuntime from '/@react-refresh';
      RefreshRuntime.injectIntoGlobalHook(window);
      window.$RefreshReg$ = () => {};
      window.$RefreshSig$ = () => (type) => type;
      window.__vite_plugin_react_preamble_installed__ = true;
    </script><script type="module">
      import React from '/node_modules/.vite/deps/react.js';
      import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
      import { NewProjectModal } from '/src/components/NewProjectModal.tsx';
      import '/src/index.css';
      function Harness() {
        const [isOpen, setOpen] = React.useState(true);
        return React.createElement(React.Fragment, null,
          React.createElement('button', { onClick: () => setOpen(true) }, 'Open project modal'),
          React.createElement(NewProjectModal, {
            isOpen, onClose: () => setOpen(false), onProjectCreated: () => {},
          }));
      }
      ReactDOM.createRoot(document.getElementById('root')).render(
        React.createElement(React.StrictMode, null, React.createElement(Harness)));
    </script></body></html>`,
  }));
  await page.goto('/__new-project-test');
  await page.getByRole('checkbox', { name: /Import chapters from a novel URL/ }).check();
  await page.getByPlaceholder('https://ncode.syosetu.com/... or Kakuyomu URL').fill(novelUrl);
}

test('URL inspection fills a trimmed romanized title and sanitized project name, retaining original preview', async ({ page }) => {
  await openModal(page);
  await page.route('**/api/scraper/inspect', (route) => route.fulfill({ json: inspection(novelUrl, '  Hoshi: Monogatari  ') }));
  await page.getByRole('button', { name: 'Inspect', exact: true }).click();
  await expect(page.getByLabel('Novel Title')).toHaveValue('Hoshi: Monogatari');
  await expect(page.getByLabel('Project Name')).toHaveValue('Hoshi_ Monogatari');
  await expect(page.getByText('星の物語', { exact: true })).toBeVisible();
});

test('blank romanization falls back to the original title', async ({ page }) => {
  await openModal(page);
  await page.route('**/api/scraper/inspect', (route) => route.fulfill({ json: inspection(novelUrl, '   ') }));
  await page.getByRole('button', { name: 'Inspect', exact: true }).click();
  await expect(page.getByLabel('Novel Title')).toHaveValue('星の物語');
  await expect(page.getByLabel('Project Name')).toHaveValue('星の物語');
});

test('manual title and project edits made while inspection is pending are preserved', async ({ page }) => {
  await openModal(page);
  let release!: () => void;
  const pending = new Promise<void>((resolve) => { release = resolve; });
  await page.route('**/api/scraper/inspect', async (route) => {
    await pending;
    await route.fulfill({ json: inspection() });
  });
  const request = page.waitForRequest('**/api/scraper/inspect');
  await page.getByRole('button', { name: 'Inspect', exact: true }).click();
  await request;
  await page.getByLabel('Novel Title').fill('My Literary Title');
  await page.getByLabel('Project Name').fill('My_Project');
  release();
  await expect(page.getByText('3 chapters found', { exact: false })).toBeVisible();
  await expect(page.getByLabel('Novel Title')).toHaveValue('My Literary Title');
  await expect(page.getByLabel('Project Name')).toHaveValue('My_Project');
});

for (const invalidate of ['url', 'close'] as const) {
  test(`a delayed inspection is ignored after ${invalidate === 'url' ? 'changing the URL' : 'closing and reopening the modal'}`, async ({ page }) => {
    await openModal(page);
    let release!: () => void;
    const pending = new Promise<void>((resolve) => { release = resolve; });
    await page.route('**/api/scraper/inspect', async (route) => {
      await pending;
      await route.fulfill({ json: inspection() });
    });
    const request = page.waitForRequest('**/api/scraper/inspect');
    await page.getByRole('button', { name: 'Inspect', exact: true }).click();
    await request;
    if (invalidate === 'url') {
      await page.getByPlaceholder('https://ncode.syosetu.com/... or Kakuyomu URL').fill('https://kakuyomu.jp/works/new-novel');
    } else {
      await page.getByRole('button', { name: 'Cancel', exact: true }).click();
      await page.getByRole('button', { name: 'Open project modal', exact: true }).click();
    }
    const response = page.waitForResponse('**/api/scraper/inspect');
    release();
    await (await response).finished();
    // A round trip through the browser also lets React consume the response.
    await page.getByLabel('Novel Title').focus();
    await expect(page.getByLabel('Novel Title')).toHaveValue('');
    await expect(page.getByLabel('Project Name')).toHaveValue('');
    await expect(page.getByText('星の物語', { exact: true })).toHaveCount(0);
  });
}

test('chapter range is submitted and a failed import retries against the same created project', async ({ page }) => {
  await openModal(page);
  const creations: Record<string, unknown>[] = [];
  const extractions: Record<string, unknown>[] = [];
  await page.route('**/api/projects/create', async (route) => {
    creations.push(route.request().postDataJSON());
    await route.fulfill({ json: { success: true, active_project: project } });
  });
  await page.route('**/api/scraper/extract', async (route) => {
    extractions.push(route.request().postDataJSON());
    await route.fulfill({ json: { task_id: `mock-${extractions.length}` } });
  });
  await page.route('**/api/scraper/status/**', (route) => route.fulfill({ json: {
    status: extractions.length === 1 ? 'failed' : 'completed', progress_percent: 100,
    error: extractions.length === 1 ? 'Mock import failure' : null,
  } }));
  await page.getByRole('button', { name: 'Inspect', exact: true }).click();
  await page.getByRole('radio', { name: 'Chapter range', exact: true }).check();
  await page.getByRole('spinbutton').first().fill('2');
  await page.getByRole('spinbutton').last().fill('3');
  await page.getByRole('button', { name: 'Create & Import Chapters', exact: true }).click();
  await expect(page.getByText('Project created, but chapter import failed: Mock import failure', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Retry Chapter Import', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Initialize New Novel Project' })).toHaveCount(0);
  expect(creations).toHaveLength(1);
  expect(creations[0]).toMatchObject({ title: 'Hoshi no Monogatari', folder_name: 'Hoshi no Monogatari' });
  expect(extractions).toHaveLength(2);
  for (const extraction of extractions) {
    expect(extraction).toMatchObject({ url: novelUrl, project_path: project.path, folder: 'raw_chapters', start_chapter: 2, end_chapter: 3 });
  }
});
