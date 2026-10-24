// Run from any directory: node web/scripts/capture_demo_images.mjs
// Owns a temporary Vite server; API responses use fictional fixtures only.
import { chromium, expect } from '@playwright/test';
import { createServer } from 'vite';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { installDemo, projectPath, sourceText, polishedText } from './documentation_demo.mjs';

const repoRoot = fileURLToPath(new URL('../../', import.meta.url));
const imagesDir = path.join(repoRoot, 'docs/images');
const server = await createServer({ root: path.join(repoRoot, 'web'), server: { host: '127.0.0.1', port: 0, open: false } });
let browser;
try {
  await server.listen();
  const origin = `http://127.0.0.1:${server.httpServer.address().port}`;
  browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1,
    locale: 'en-US', timezoneId: 'UTC', colorScheme: 'dark', serviceWorkers: 'block',
  });
  const failures = await installDemo(context, origin);
  const page = await context.newPage();
  page.on('pageerror', error => failures.push(error.message));
  await mkdir(imagesDir, { recursive: true });

  async function capture(name, workspace, params, verify) {
    const query = new URLSearchParams({ project: projectPath, chapter: '1', folder: 'Volume 01', ...params });
    await page.goto(`${origin}/${workspace}?${query}`, { waitUntil: 'domcontentloaded' });
    const logo = page.locator('header img[alt="Nousetsu"]');
    await expect(logo).toBeVisible();
    await expect(logo).toHaveJSProperty('naturalWidth', 1024);
    await expect(page.locator('header').getByRole('button', {
      name: { dashboard: 'Studio', reader: 'Reader', bible: 'Novel Bible', settings: 'Settings' }[name] || 'Traces', exact: true,
    })).toBeVisible();
    await verify();
    await page.evaluate(() => document.fonts.ready);
    await expect(page.getByRole('alert')).toHaveCount(0);
    expect(failures, 'No unknown API calls, writes, or rendering errors').toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: path.join(imagesDir, `web_studio_${name}_demo.png`), animations: 'disabled' });
    console.log(`Captured ${name} (1920 x 1080)`);
  }

  await capture('dashboard', 'studio', {}, async () => {
    await expect(page.getByText(sourceText.split('\n\n')[1], { exact: false }).first()).toBeVisible();
    await expect(page.getByText(polishedText.split('\n\n')[1], { exact: false }).first()).toBeVisible();
  });
  await capture('reader', 'reader', {}, async () => {
    await expect(page.getByText(polishedText.split('\n\n')[1], { exact: false }).first()).toBeVisible();
  });
  await capture('bible', 'bible', { section: 'characters' }, async () => {
    await expect(page.getByText('Haruka Mori', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Ren Aoki', { exact: true }).first()).toBeVisible();
  });
  await capture('traces', 'traces', { trace: 'demo-extraction', stage: 'extraction', detail: 'output' }, async () => {
    await expect(page.getByRole('button', { name: 'Output', exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Extracted Characters (3)', exact: true })).toBeVisible();
    await expect(page.locator('main').getByText('Haruka Mori', { exact: true })).toBeVisible();
  });
  await capture('diff', 'traces', { trace: 'demo-polishing', stage: 'polishing', detail: 'diff' }, async () => {
    await expect(page.getByTitle('Side-by-Side Diff', { exact: true })).toBeVisible();
    await page.getByTitle('Side-by-Side Diff', { exact: true }).click();
    await expect(page.getByText(/\+\d+ words/)).toBeVisible();
    await expect(page.getByText(/-\d+ words/)).toBeVisible();
  });
  await capture('tokens', 'traces', { mode: 'project-analytics' }, async () => {
    await expect(page.getByRole('heading', { name: 'Project Token Analysis', exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'By processing stage', exact: true })).toBeVisible();
    await expect(page.getByText('56,400', { exact: true }).first()).toBeVisible();
  });
  await capture('settings', 'settings', { section: 'general' }, async () => {
    await expect(page.getByRole('button', { name: 'Save Settings', exact: true })).toBeVisible();
    await expect(page.locator('input[value="The Lantern Archive"]').first()).toBeVisible();
  });
  console.log('Seven images verified; no real backend or external services used.');
} finally {
  await browser?.close();
  await server.close();
}
