import { expect, test, type Page } from '@playwright/test';

// Mount only startup so background workspace polling cannot mask duplicate checks.
async function mountStartup(page: Page, options: { brokenRegistry?: boolean; blockedStorage?: boolean; withProject?: boolean } = {}) {
  page.on('pageerror', (error) => console.error('Startup harness error:', error.message));
  const calls: Record<string, number> = {};
  const state = { brokenRegistry: options.brokenRegistry ?? false, title: 'Test novel' };
  await page.addInitScript(({ blockedStorage }) => {
    Object.defineProperty(window, '__startupStreamChecks', { value: 0, writable: true });
    window.EventSource = class {
      onopen: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor() {
        const browser = window as typeof window & { __startupStreamChecks: number };
        browser.__startupStreamChecks += 1;
        setTimeout(() => this.onopen?.(), 0);
      }
      close() { /* Startup owns the probe and closes it after handshake. */ }
    } as unknown as typeof EventSource;
    if (blockedStorage) {
      Storage.prototype.getItem = () => { throw new Error('Storage unavailable'); };
      Storage.prototype.setItem = () => { throw new Error('Storage unavailable'); };
    }
  }, { blockedStorage: options.blockedStorage ?? false });
  await page.route('**/api/**', async (route) => {
    const endpoint = new URL(route.request().url()).pathname;
    calls[endpoint] = (calls[endpoint] || 0) + 1;
    if (endpoint === '/api/active-project') {
      const project = options.withProject ? {
        path: 'C:/Test novels/Novel', name: 'Novel', title: state.title, genre: 'fantasy',
        source_language: 'Japanese', target_language: 'English', has_traces: false,
        trace_count: 0, latest_trace_mtime: 0,
      } : null;
      await route.fulfill(state.brokenRegistry
        ? { status: 503, json: { error: 'Registry unavailable' } }
        : { json: { active_project: project, projects: project ? [project] : [], projects_dir: 'C:/Test novels' } });
    } else if (endpoint === '/api/chapters') {
      await route.fulfill({ json: [{ chapter_num: 1, folder: null, title: state.title }] });
    } else {
      await route.fulfill({ json: { version: 'test' } });
    }
  });
  await page.route('**/startup-test', (route) => route.fulfill({
    contentType: 'text/html',
    body: `<!doctype html><html><body><div id="root"></div>
      <script type="module">
        import RefreshRuntime from '/@react-refresh';
        RefreshRuntime.injectIntoGlobalHook(window);
        window.$RefreshReg$ = () => {};
        window.$RefreshSig$ = () => (type) => type;
        window.__vite_plugin_react_preamble_installed__ = true;
      </script>
      <script type="module">
        import React from '/node_modules/.vite/deps/react.js';
        import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
        import { StartupLoadingScreen } from '/src/components/StartupLoadingScreen.tsx';
        const root = ReactDOM.createRoot(document.getElementById('root'));
        function Parent() {
          const [tick, update] = React.useState(0);
          React.useEffect(() => {
            const timer = setInterval(() => update((n) => n + 1), 30);
            return () => clearInterval(timer);
          }, []);
          return React.createElement(StartupLoadingScreen, {
            onReady: (data) => {
              window.__startupData = data;
              root.render(React.createElement('main', {}, data.activeProject?.title || 'Empty workspace'));
            },
          });
        }
        root.render(React.createElement(React.StrictMode, {}, React.createElement(Parent)));
      </script></body></html>`,
  }));
  await page.goto('/startup-test');
  return { calls, state };
}

test('startup verifies once across StrictMode and callback changes, then refresh hydrates quietly', async ({ page }) => {
  const { calls, state } = await mountStartup(page, { withProject: true });
  await expect(page.getByText('Test novel', { exact: true })).toBeVisible();
  expect(calls['/api/desktop-info']).toBe(1);
  expect(calls['/api/active-project']).toBe(1);
  expect(calls['/api/environment']).toBe(1);
  expect(calls['/api/chapters']).toBe(1);
  expect(await page.evaluate(() => (window as typeof window & { __startupStreamChecks: number }).__startupStreamChecks)).toBe(1);
  expect(await page.evaluate(() => (window as typeof window & { __startupData: { projectsDir: string } }).__startupData.projectsDir)).toBe('C:/Test novels');

  state.title = 'Refreshed novel';
  await page.reload();
  await expect(page.getByText('Refreshed novel', { exact: true })).toBeVisible();
  await expect(page.getByText('Verifying service readiness...')).toHaveCount(0);
  expect(calls['/api/desktop-info']).toBe(2);
  expect(calls['/api/active-project']).toBe(2);
  expect(calls['/api/environment']).toBe(1);
  expect(calls['/api/chapters']).toBe(2);
  expect(await page.evaluate(() => (window as typeof window & { __startupData: { chapters: { title: string }[] } }).__startupData.chapters[0].title)).toBe('Refreshed novel');
  expect(await page.evaluate(() => (window as typeof window & { __startupStreamChecks: number }).__startupStreamChecks)).toBe(0);
});

test('registry failures offer recovery and retry resets the failed operation', async ({ page }) => {
  const { calls, state } = await mountStartup(page, { brokenRegistry: true });
  await expect(page.getByText('Service Initialization Stalled', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => Object.keys(sessionStorage).some((key) => key.startsWith('nousetsu_startup:')))).toBe(false);
  state.brokenRegistry = false;
  await page.getByRole('button', { name: 'Retry Verification' }).click();
  await expect(page.getByText('Empty workspace', { exact: true })).toBeVisible();
  expect(calls['/api/desktop-info']).toBe(2);
  expect(calls['/api/active-project']).toBe(2);
  expect(calls['/api/environment']).toBe(1);
});

test('bypassing a registry failure does not save successful verification', async ({ page }) => {
  const { calls, state } = await mountStartup(page, { brokenRegistry: true });
  await page.getByRole('button', { name: 'Skip & Continue' }).click();
  await expect(page.getByText('Empty workspace', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => Object.keys(sessionStorage).some((key) => key.startsWith('nousetsu_startup:')))).toBe(false);
  state.brokenRegistry = false;
  await page.reload();
  await expect(page.getByText('Empty workspace', { exact: true })).toBeVisible();
  expect(calls['/api/environment']).toBe(1);
});

test('restricted session storage still completes startup', async ({ page }) => {
  const { calls } = await mountStartup(page, { blockedStorage: true });
  await expect(page.getByText('Empty workspace', { exact: true })).toBeVisible();
  expect(calls['/api/desktop-info']).toBe(1);
  expect(calls['/api/active-project']).toBe(1);
});

test('a stalled backend request is bounded and offers Retry and Skip', async ({ page }) => {
  await mountStartup(page);
  await expect(page.getByText('Empty workspace', { exact: true })).toBeVisible();
  await page.route('**/api/desktop-info', () => { /* Deliberately leave the request pending. */ });
  await page.reload();
  await expect(page.getByText('Service Initialization Stalled', { exact: true })).toBeVisible({ timeout: 7000 });
  await expect(page.getByRole('button', { name: 'Retry Verification' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Skip & Continue' })).toBeVisible();
});
