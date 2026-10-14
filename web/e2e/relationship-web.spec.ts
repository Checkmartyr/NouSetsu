import { test, expect, type Page } from '@playwright/test';
import { mockBackend, path } from './helpers/mockBackend';
import type { BibleCharacter } from '../src/types/dashboard';

const characters: BibleCharacter[] = [
  { name: 'Aria', original_name: 'アリア', role: 'protagonist', aliases: ['Ari'], relationships: { 'B先生': 'teacher', Phantom: 'unknown guide', Shared: 'acquaintance' } },
  { name: 'Benedict', original_name: 'B先生', role: 'mentor', aliases: ['Ben'], relationships: { Ari: 'student', Claudia: 'ally' } },
  { name: 'Claudia', original_name: 'クラウディア', role: 'antagonist', aliases: ['Shared'], relationships: { アリア: 'rival' } },
  { name: '孤独な旅人 — นักเดินทางผู้โดดเดี่ยว', original_name: '旅人', role: 'supporting', aliases: ['Shared'] },
];

async function openVisualizer(page: Page, roster = characters) {
  await mockBackend(page);
  await page.route('**/api/bible?**', route => route.fulfill({ json: {
    title: 'Relationship Test', genre: 'fantasy', source_language: 'Japanese', target_language: 'English',
    characters: roster, glossary: [], archived_arcs: [],
  } }));
  // Observe actual Canvas coordinates without adding production test hooks.
  await page.addInitScript(() => {
    const clear = CanvasRenderingContext2D.prototype.clearRect;
    const text = CanvasRenderingContext2D.prototype.fillText;
    CanvasRenderingContext2D.prototype.clearRect = function (...args) {
      this.canvas.dataset.labels = '[]';
      return clear.apply(this, args);
    };
    CanvasRenderingContext2D.prototype.fillText = function (label, x, y, maxWidth?) {
      const point = this.getTransform().transformPoint({ x, y });
      const labels = JSON.parse(this.canvas.dataset.labels || '[]');
      labels.push({ text: label, x: point.x / devicePixelRatio, y: point.y / devicePixelRatio, width: this.measureText(label).width * this.getTransform().a / devicePixelRatio });
      this.canvas.dataset.labels = JSON.stringify(labels);
      if (maxWidth === undefined) text.call(this, label, x, y);
      else text.call(this, label, x, y, maxWidth);
    };
  });
  await page.goto(path('bible'));
  await page.getByRole('button', { name: /Visualizer/i }).click();
  await expect(page.getByText('Personal Relationship Map', { exact: false }).first()).toBeVisible();
}

async function openNetwork(page: Page, roster = characters) {
  await openVisualizer(page, roster);
  await page.getByRole('button', { name: 'Relationship Web', exact: true }).click();
  const graph = page.getByRole('region', { name: 'Global relationship graph' });
  await expect(graph.locator('canvas')).toBeVisible();
  await graph.locator('canvas').scrollIntoViewIfNeeded();
  return graph;
}

test('Global map preserves one-way, reciprocal, unresolved and disconnected characters', async ({ page }) => {
  const graph = await openNetwork(page);
  await expect(graph.getByRole('status')).toHaveText('6 characters · 5 connections');
  const details = graph.getByLabel('Relationship details');
  await expect(details).toContainText('Select or hover');
  await graph.getByText('Choose a character', { exact: false }).click();
  await graph.getByRole('button', { name: 'Aria', exact: true }).click();
  for (const relation of ['teacher', 'student', 'rival']) await expect(details).toContainText(relation);
  await graph.getByRole('button', { name: 'Clear selection' }).click();
  await expect(details).toContainText('Select or hover');
  // Re-selecting the current roster character after clearing must restore focus.
  await page.getByRole('button', { name: /Aria.*Protagonist/ }).click();
  await expect(details).toContainText('teacher');
  await graph.getByRole('button', { name: 'Shared', exact: true }).click();
  await expect(details).toContainText('Unregistered character');
  await expect(details.getByRole('button', { name: /Open dossier/ })).toHaveCount(0);
  await graph.getByRole('button', { name: characters[3].name, exact: true }).click();
  await expect(details).toContainText('No connections in this view.');
  await details.getByRole('button', { name: /Open dossier/ }).click();
  await expect(page.getByRole('region', { name: 'Global relationship graph' })).toHaveCount(0);
  await expect(page.getByText(characters[3].name, { exact: true }).first()).toBeVisible();
});

test('Search and categories retain endpoints and handle empty results', async ({ page }) => {
  const graph = await openNetwork(page);
  const search = graph.getByRole('textbox', { name: 'Search graph' });
  for (const [query, count] of [['rival', '2 characters · 1 connections'], ['Ben', '3 characters · 2 connections'], ['アリア', '5 characters · 4 connections']]) {
    await search.fill(query);
    await expect(graph.getByRole('status')).toHaveText(count);
  }
  await search.fill('');
  await graph.getByRole('button', { name: 'Mentor & Order', exact: true }).click();
  await expect(graph.getByRole('status')).toHaveText('3 characters · 2 connections');
  await graph.getByRole('button', { name: 'All', exact: true }).click();
  await search.fill('no-such-character');
  await expect(graph.getByRole('status')).toHaveText('0 characters · 0 connections');
  await expect(graph.getByText('No matching characters or relationships.')).toBeVisible();
  await search.fill('');
  await expect(graph.getByRole('status')).toHaveText('6 characters · 5 connections');
});

test('Zoom, fit, pointer selection, hover and dragging preserve network navigation', async ({ page }) => {
  const graph = await openNetwork(page);
  const canvas = graph.locator('canvas'), zoom = graph.getByLabel('Graph zoom');
  const initialZoom = await zoom.textContent();
  await graph.getByRole('button', { name: 'Zoom in', exact: true }).click();
  await expect(zoom).not.toHaveText(initialZoom!);
  const manualZoom = await zoom.textContent();
  await graph.getByText('Choose a character', { exact: false }).click();
  await graph.getByRole('button', { name: 'Benedict', exact: true }).click();
  await expect(zoom).toHaveText(manualZoom!);
  await graph.getByRole('button', { name: 'Clear selection' }).click();
  await graph.getByRole('button', { name: 'Fit graph' }).click();
  await expect(zoom).toHaveText(initialZoom!);
  await canvas.scrollIntoViewIfNeeded();
  await expect.poll(() => canvas.evaluate(el => JSON.parse(el.dataset.labels || '[]').length)).toBeGreaterThan(0);
  const point = await canvas.evaluate(el => {
    const labels: { text: string; x: number; y: number }[] = JSON.parse(el.dataset.labels || '[]');
    const p = labels.find(l => l.text === 'A')!;
    const rect = el.getBoundingClientRect();
    return { x: p.x + rect.left, y: p.y + rect.top };
  });
  await page.mouse.move(point.x, point.y);
  await expect(graph.getByLabel('Relationship details')).toContainText('teacher');
  await page.mouse.click(point.x, point.y);
  await page.mouse.move(0, 0);
  await expect(graph.getByLabel('Relationship details')).toContainText('Aria');
  await graph.getByRole('button', { name: 'Clear selection' }).click();
  await canvas.scrollIntoViewIfNeeded();
  await page.mouse.move(point.x, point.y);
  await page.mouse.down();
  await page.mouse.move(point.x + 30, point.y + 30, { steps: 8 });
  await page.mouse.up();
  await page.mouse.move(0, 0);
  await expect(graph.getByLabel('Relationship details')).toContainText('Select or hover');
  await expect(graph).toBeVisible();
  await canvas.hover();
  const beforeWheel = await zoom.textContent();
  await page.mouse.wheel(0, -100);
  await expect(zoom).not.toHaveText(beforeWheel!);
});

test('Personal map keeps graph, settings and cards matrix working', async ({ page }) => {
  await openVisualizer(page);
  const graph = page.getByRole('region', { name: 'Personal relationship graph' });
  await expect(graph.getByRole('status')).toHaveText('4 characters · 3 connections');
  await graph.getByRole('button', { name: 'Layout settings' }).click();
  await expect(graph.getByText('Obsidian Physics Forces')).toBeVisible();
  await graph.getByRole('slider', { name: 'Link Distance' }).fill('200');
  await page.getByRole('button', { name: 'Cards Matrix' }).click();
  await expect(page.getByPlaceholder('Search relationships...')).toBeVisible();
  await page.getByRole('button', { name: 'Obsidian Graph' }).click();
  await expect(graph.locator('canvas')).toBeVisible();
});

test('Self relationships and an isolated cast remain drawable', async ({ page }) => {
  const graph = await openNetwork(page, [
    { name: 'Self', original_name: '自己', relationships: { 自己: 'inner voice' } },
    { name: 'Isolate', original_name: '孤独' },
  ]);
  await expect(graph.getByRole('status')).toHaveText('2 characters · 1 connections');
  await graph.getByText('Choose a character', { exact: false }).click();
  await graph.getByRole('button', { name: 'Self', exact: true }).click();
  await expect(graph.getByLabel('Relationship details')).toContainText('Self → Self: inner voice');
  await graph.getByRole('button', { name: 'Family & Bond', exact: true }).click();
  await expect(graph.getByRole('status')).toHaveText('0 characters · 0 connections');
  await graph.getByRole('button', { name: 'All', exact: true }).click();
  await expect(graph.getByRole('status')).toHaveText('2 characters · 1 connections');
});

for (const size of ['small', 'dense'] as const) {
  test(`${size} network fits and resizes without horizontal overflow`, async ({ page }, testInfo) => {
    const roster = size === 'small' ? characters : Array.from({ length: 30 }, (_, i): BibleCharacter => ({
      name: `Character ${i} — 人物`, original_name: `人物${i}`, role: i === 0 ? 'protagonist' : 'supporting',
      relationships: { [`人物${(i + 1) % 30}`]: i % 2 ? 'friend' : 'rival', [`人物${(i + 7) % 30}`]: 'ally' },
    }));
    const graph = await openNetwork(page, roster);
    await expect(graph.getByRole('status')).toHaveText(size === 'small' ? '6 characters · 5 connections' : '30 characters · 60 connections');
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(2);
    await graph.screenshot({ path: testInfo.outputPath(`${size}-graph.png`) });
    const canvas = graph.locator('canvas'), oldWidth = await canvas.evaluate(el => el.width);
    await canvas.screenshot({ path: testInfo.outputPath(`${size}-canvas.png`) });
    const labels = await canvas.evaluate(el => {
      const labels: { text: string; x: number; y: number; width: number }[] = JSON.parse(el.dataset.labels || '[]');
      return labels.filter(l => l.text.length > 1);
    });
    expect(labels).toHaveLength(size === 'small' ? 6 : 30);
    for (let i = 0; i < labels.length; i++) {
      for (let j = i + 1; j < labels.length; j++) {
        const a = labels[i], b = labels[j];
        expect(Math.abs(a.x - b.x) >= (a.width + b.width) / 2 || Math.abs(a.y - b.y) >= 18, `${JSON.stringify(a)} overlaps ${JSON.stringify(b)}`).toBeTruthy();
      }
    }
    const viewport = page.viewportSize()!;
    await page.setViewportSize({ width: viewport.width === 390 ? 600 : 800, height: viewport.height });
    await expect.poll(() => canvas.evaluate(el => el.width)).not.toBe(oldWidth);
    await graph.getByText('Choose a character', { exact: false }).click();
    await graph.getByRole('button', { name: roster[0].name, exact: true }).focus();
    await page.keyboard.press('Enter');
    await expect(graph.getByLabel('Relationship details')).toContainText(roster[0].name);
  });
}
