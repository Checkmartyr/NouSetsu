import { test, expect, type Page, type Locator, type APIRequestContext } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

// These tests exercise the real API. No page.route(), fetch replacement, or
// simulated Tauri globals are used. Findings are recorded separately from
// harness assertions so a reproduced product defect is not a passing contract.
const evidence = path.resolve('../audit-results/settings');
const roles = [
  ['extractor', 'Entity Extractor'], ['drafter', 'Context-Aware Drafter'],
  ['critic', 'Critique Agent'], ['polisher', 'Polishing Agent'],
  ['chronicler', 'Chronicler Agent'], ['scraper', 'Novel Scraper'],
] as const;
type Result = { mode: string; scenario: string; status: 'pass' | 'fail' | 'blocked'; fields: string[]; details: unknown };
const rows: Result[] = [];
let fixture: any;
const backend = (mode: string) => `http://127.0.0.1:${mode === 'web-dev' ? 5186 : 5188}`;
const url = (section: string, project = fixture.projects.A) => `/settings?${new URLSearchParams({ project, section })}`;
const hash = (value: string) => crypto.createHash('sha256').update(value).digest('hex');
function record(scenario: string, fields: string[], status: Result['status'], details: unknown) {
  rows.push({ mode: test.info().project.name, scenario, fields, status, details });
}
function field(scope: Page | Locator, label: string | RegExp): Locator {
  return scope.locator('label').filter({ hasText: label }).first().locator('xpath=..').locator('input, select').first();
}
async function snapshot(request: APIRequestContext) {
  return (await request.get(`${backend(test.info().project.name)}/api/audit/fixture`)).json();
}
async function settings(request: APIRequestContext, project = fixture.projects.A) {
  return (await request.get(`${backend(test.info().project.name)}/api/settings?${new URLSearchParams({ project_path: project })}`)).json();
}
async function open(page: Page, section: string, project = fixture.projects.A) {
  await page.goto(url(section, project));
  if (section === 'global') {
    await expect(page.getByRole('button', { name: 'Save Global Settings', exact: true })).toBeVisible();
    return;
  }
  await expect(page.getByRole('button', { name: 'Save Settings', exact: true })).toBeVisible();
  await expect(page.locator('form')).toBeVisible();
}
async function saveProject(page: Page) {
  const response = page.waitForResponse(r => r.url().includes('/api/settings') && r.request().method() === 'PUT');
  const refreshed = page.waitForResponse(r => r.url().includes('/api/settings') && r.request().method() === 'GET');
  await page.getByRole('button', { name: 'Save Settings', exact: true }).click();
  const result = await response;
  expect(result.status()).toBe(200);
  await refreshed;
  await expect(page.locator('form')).toBeVisible();
}
async function saveGlobal(page: Page) {
  const response = page.waitForResponse(r => r.url().endsWith('/api/environment') && r.request().method() === 'PUT');
  const refreshed = page.waitForResponse(r => r.url().endsWith('/api/environment') && r.request().method() === 'GET');
  await page.getByRole('button', { name: 'Save Global Settings', exact: true }).click();
  expect((await response).status()).toBe(200);
  await refreshed;
  await expect(page.getByText('Local environment settings saved.', { exact: true })).toBeVisible();
}
async function generation(card: Locator, temperature: string, budget: string) {
  await card.getByLabel('Gemini Interactions API', { exact: true }).selectOption('false');
  await card.getByLabel('Temperature', { exact: true }).fill(temperature);
  await card.getByRole('combobox', { name: 'Thinking level', exact: true }).selectOption('low');
  await card.getByLabel('Thinking budget', { exact: true }).fill(budget);
}

test.beforeAll(async ({}, info) => {
  fs.mkdirSync(evidence, { recursive: true });
  const filename = path.join(evidence, 'browser-results.json');
  const previous: Result[] = fs.existsSync(filename) ? JSON.parse(fs.readFileSync(filename, 'utf8')) : [];
  // A fresh worker/run must not inherit passes from an older run of this mode.
  fs.writeFileSync(filename, JSON.stringify(previous.filter(row => row.mode !== info.project.name), null, 2));
});

test.beforeEach(async ({ request }) => {
  rows.length = 0;
  const response = await request.post(`${backend(test.info().project.name)}/api/audit/reset`);
  expect(response.status()).toBe(200);
  fixture = await response.json();
  expect(fixture.env_file).toContain('nousetsu-settings-');
});
test.afterEach(async ({}, info) => {
  if (info.status !== info.expectedStatus) {
    for (const row of rows) row.status = 'blocked';
    record(info.title, [...new Set(rows.flatMap(row => row.fields))], 'blocked', { reason: 'Harness assertion failed; inspect Playwright report/trace.' });
  }
  fs.mkdirSync(evidence, { recursive: true });
  const filename = path.join(evidence, 'browser-results.json');
  const previous: Result[] = fs.existsSync(filename) ? JSON.parse(fs.readFileSync(filename, 'utf8')) : [];
  // Each project runs in its own worker; discard prior rows for completed scenarios.
  const replacements = new Set(rows.map(row => `${row.mode}:${row.scenario}`));
  replacements.add(`${info.project.name}:${info.title}`);
  fs.writeFileSync(filename, JSON.stringify([...previous.filter(row => !replacements.has(`${row.mode}:${row.scenario}`)), ...rows], null, 2));
});

test('all editable project controls save through real API, disk, and reload', async ({ page, request }) => {
  await open(page, 'all');
  const form = page.locator('form');
  const values: Record<string, [string, string | RegExp]> = {
    title: ['Audited Novel 日本語', /^Novel Title$/], genre: ['fantasy', /^Genre$/],
    source_language: ['Japanese', /^Source Language$/], target_language: ['English', /^Target Language$/],
    project_id: ['audit-project-a', /^Project Identifier$/],
    chunk_threshold_lines: ['900', /^Chunk Threshold/], target_chunk_lines: ['450', /^Chunk Size/],
    chunk_overlap_lines: ['5', /^Chunk Overlap/], rag_top_k: ['4', /^Lore Retrieval Top-K/],
    rag_embedding_model: ['mock-embedding', /^Dense Embedding Model$/],
    rag_reranker_model: ['mock-reranker', /^Cross-Encoder Reranker Model$/],
    safety_subdivision_min_lines: ['10', /^Subdivision Min Lines/], safety_subdivision_max_depth: ['5', /^Subdivision Max/],
    max_tpm: ['50000', /^Max Tokens Per Minute/], max_rpm: ['80', /^Max Requests Per Minute/],
    raw_dir: ['raw chapters 日本語', /^Raw Chapters Directory$/], output_dir: ['translated chapters 日本語', /^Translated Chapters Directory$/],
    max_review_loops: ['4', /^Max Review Loops/], quality_threshold: ['9', /^Quality Score Threshold/],
  };
  for (const [, [value, label]] of Object.entries(values)) await field(form, label).fill(value);
  const models: Record<string, string> = { model_name: 'mock-project-primary', fallback_model: 'mock-project-fallback' };
  await form.getByLabel('Primary model route model ID', { exact: true }).fill(models.model_name);
  await form.getByLabel('Shared fallback route model ID', { exact: true }).fill(models.fallback_model);
  for (const [index, [role, title]] of roles.entries()) {
    models[`${role}_model`] = `mock-project-${role}`;
    const model = form.getByLabel(`${title} model model ID`, { exact: true });
    await model.fill(models[`${role}_model`]);
    const card = model.locator('xpath=ancestor::div[contains(@class,"space-y-3")][1]');
    await generation(card, (0.3 + index * 0.1).toFixed(1), String(100 + index));
  }
  const toggles: Record<string, string> = {
    enable_patch_polishing: 'Enable Diff/Patch Polishing Engine', enable_chunking: 'Chunking Enabled',
    auto_update_bible: 'Auto-Update Novel Bible', cross_folder_summaries: 'Cross-Folder Multi-Volume Memory',
    filter_scene_characters: 'Scene Character Filtering', filter_extractor_entities: 'Extractor Known Entity Filtering',
    enable_post_polish_reconciliation: 'Post-Polish Term Reconciliation', enable_rag: 'Hybrid RAG Enabled',
    enable_rag_reranker: 'Enable Cross-Encoder Reranker', safety_recursive_subdivision: 'Subdivision Enabled',
  };
  for (const [, label] of Object.entries(toggles)) {
    const toggle = form.getByText(label, { exact: true }).locator('xpath=ancestor::*[.//button[@role="switch"]][1]').getByRole('switch');
    if (await toggle.getAttribute('aria-checked') === 'true') await toggle.click();
  }
  await saveProject(page);
  const disk = await snapshot(request);
  for (const [key, [value]] of Object.entries(values)) expect(String(disk.config.A[key]), key).toBe(value);
  for (const [key, value] of Object.entries(models)) expect(disk.config.A[key], key).toBe(value);
  for (const key of Object.keys(toggles)) expect(disk.config.A[key], key).toBe(false);
  for (const [index, [role]] of roles.entries()) expect(disk.config.A.generation_settings[role]).toEqual({ temperature: Number((0.3 + index * 0.1).toFixed(1)), thinking_budget: 100 + index, thinking_level: 'low', use_interactions_api: false });
  expect(disk.bible.A.title).toBe(disk.config.A.title);
  expect(disk.config.B.title).toBe('Audit B');
  await page.reload();
  await expect(field(page.locator('form'), /^Novel Title$/)).toHaveValue(values.title[0]);
  for (const [, [value, label]] of Object.entries(values)) await expect(field(page.locator('form'), label)).toHaveValue(value);
  for (const [, label] of Object.entries(toggles)) await expect(page.locator('form').getByText(label, { exact: true }).locator('xpath=ancestor::*[.//button[@role="switch"]][1]').getByRole('switch')).toHaveAttribute('aria-checked', 'false');
  for (const [index, [role, title]] of roles.entries()) {
    const model = page.locator('form').getByLabel(`${title} model model ID`, { exact: true });
    await expect(model).toHaveValue(models[`${role}_model`]);
    const card = model.locator('xpath=ancestor::div[contains(@class,"space-y-3")][1]');
    await expect(card.getByLabel('Temperature', { exact: true })).toHaveValue((0.3 + index * 0.1).toFixed(1));
    await expect(card.getByRole('combobox', { name: 'Thinking level', exact: true })).toHaveValue('low');
    await expect(card.getByLabel('Thinking budget', { exact: true })).toHaveValue(String(100 + index));
    await expect(card.getByLabel('Gemini Interactions API', { exact: true })).toHaveValue('false');
  }
  const read = await settings(request);
  for (const key of Object.keys(models)) expect(read[key], key).toBe(models[key]);
  const tested = [...Object.keys(values), ...Object.keys(models), ...Object.keys(toggles), ...roles.flatMap(([role]) => ['temperature', 'thinking_level', 'thinking_budget', 'use_interactions_api'].map(key => `generation_settings.${role}.${key}`))];
  record('project UI/save/disk/reload', tested, 'pass', { isolated_B_unchanged: true, bible_metadata_synced: true, runtime_execution: 'Covered separately by backend audit; browser validates persistence and resolved API values.' });
  await page.screenshot({ path: path.join(evidence, `${test.info().project.name}-project.png`), fullPage: true });
});

test('all global controls and five secrets persist, preserve, replace, and clear', async ({ page, request }) => {
  await open(page, 'global');
  const expected: Record<string, string> = {};
  const simple = [
    ['Language Defaults', 'SOURCE_LANG', 'Japanese'], ['Language Defaults', 'TARGET_LANG', 'English'],
    ['Quality Defaults', 'NOVEL_MAX_REVIEW_LOOPS', '4'], ['Quality Defaults', 'NOVEL_QUALITY_THRESHOLD', '9'],
    ['Memory & Entity Defaults', 'NOVEL_FILTER_EXTRACTOR_ENTITIES', 'false'], ['Memory & Entity Defaults', 'NOVEL_POST_POLISH_RECONCILIATION', 'false'],
    ['RAG Model Defaults', 'NOVEL_RAG_EMBEDDING_MODEL', 'mock-global-embedding'], ['RAG Model Defaults', 'NOVEL_RAG_RERANKER_MODEL', 'mock-global-reranker'],
    ['Rate Limit Defaults', 'NOVEL_MAX_TPM', '45000'], ['Rate Limit Defaults', 'NOVEL_MAX_RPM', '70'],
    ['Workspace Defaults', 'NOVEL_PROJECTS_DIR', fixture.projects.A.replace(/Audit A$/, '')],
    ['Workspace Defaults', 'NOVEL_SCRAPER_PATH', `${fixture.root}/scraper 日本語`], ['Workspace Defaults', 'NOVEL_SCRAPER_PYTHON', `${fixture.root}/python.exe`],
  ];
  for (const [group, key, value] of simple) { await page.getByRole('textbox', { name: `${group} ${key}`, exact: true }).fill(value); expected[key] = value; }
  for (const [key, label] of [['DEFAULT_MODEL', 'Default model'], ['NOVEL_MODEL', 'Primary model'], ['NOVEL_FALLBACK_MODEL', 'Shared fallback model']]) {
    expected[key] = `mock-global-${key.toLowerCase()}`;
    await page.getByLabel(`${label} model ID`, { exact: true }).fill(expected[key]);
  }
  const shared = page.getByRole('heading', { name: 'Shared generation defaults', exact: true }).locator('xpath=..');
  await generation(shared, '0.4', '101');
  Object.assign(expected, { NOVEL_TEMPERATURE: '0.4', NOVEL_THINKING_LEVEL: 'low', NOVEL_THINKING_BUDGET: '101', NOVEL_USE_INTERACTIONS: 'false' });
  for (const [index, [role, title]] of roles.entries()) {
    const card = page.getByRole('heading', { name: title, exact: true }).locator('xpath=ancestor::section[1]');
    const prefix = `NOVEL_${role.toUpperCase()}`;
    expected[`${prefix}_MODEL`] = `mock-global-${role}`;
    await card.getByLabel('Model route model ID', { exact: true }).fill(expected[`${prefix}_MODEL`]);
    await generation(card, '0.5', String(200 + index));
    Object.assign(expected, { [`${prefix}_TEMPERATURE`]: '0.5', [`${prefix}_THINKING_LEVEL`]: 'low', [`${prefix}_THINKING_BUDGET`]: String(200 + index), [`${prefix}_USE_INTERACTIONS`]: 'false' });
  }
  expected.CUSTOM_API_BASE_URL = `${backend(test.info().project.name)}/api/audit/provider/v1`;
  await page.getByLabel('Custom OpenAI-compatible base URL', { exact: true }).fill(expected.CUSTOM_API_BASE_URL);
  const secrets = ['GEMINI_API_KEY', 'GOOGLE_API_KEY', 'OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'CUSTOM_API_KEY'];
  for (const key of secrets) await page.locator(`#api-key-${key}`).fill(`synthetic-audit-${key}`);
  await saveGlobal(page);
  const disk = await snapshot(request);
  for (const [key, value] of Object.entries(expected)) expect(disk.env_values[key], key).toBe(value);
  for (const key of secrets) expect(disk.secret_hashes[key], key).toBe(hash(`synthetic-audit-${key}`));
  const response = await request.get(`${backend(test.info().project.name)}/api/environment`);
  const responseText = await response.text();
  expect(responseText).not.toContain('synthetic-audit-');
  await page.reload();
  await expect(page.locator('#api-key-GEMINI_API_KEY')).toHaveValue('');
  for (const [group, key, value] of simple) await expect(page.getByRole('textbox', { name: `${group} ${key}`, exact: true })).toHaveValue(value);
  for (const [key, label] of [['DEFAULT_MODEL', 'Default model'], ['NOVEL_MODEL', 'Primary model'], ['NOVEL_FALLBACK_MODEL', 'Shared fallback model']]) await expect(page.getByLabel(`${label} model ID`, { exact: true })).toHaveValue(expected[key]);
  for (const [index, [role, title]] of roles.entries()) {
    const card = page.getByRole('heading', { name: title, exact: true }).locator('xpath=ancestor::section[1]');
    await expect(card.getByLabel('Model route model ID', { exact: true })).toHaveValue(expected[`NOVEL_${role.toUpperCase()}_MODEL`]);
    await expect(card.getByLabel('Temperature', { exact: true })).toHaveValue('0.5');
    await expect(card.getByRole('combobox', { name: 'Thinking level', exact: true })).toHaveValue('low');
    await expect(card.getByLabel('Thinking budget', { exact: true })).toHaveValue(String(200 + index));
    await expect(card.getByLabel('Gemini Interactions API', { exact: true })).toHaveValue('false');
  }
  await saveGlobal(page);
  for (const key of secrets) expect((await snapshot(request)).secret_hashes[key]).toBe(disk.secret_hashes[key]);
  for (const key of secrets) await page.locator(`#api-key-${key}`).fill(`replacement-audit-${key}`);
  await saveGlobal(page);
  for (const key of secrets) {
    expect((await snapshot(request)).secret_hashes[key]).toBe(hash(`replacement-audit-${key}`));
    await page.locator(`#api-key-${key}`).locator('xpath=..').getByRole('button', { name: 'Clear saved key', exact: true }).click();
  }
  await saveGlobal(page);
  for (const key of secrets) expect((await snapshot(request)).secret_hashes[key]).toBe(hash(''));
  record('global UI/save/disk/reload and secret lifecycle', [...Object.keys(expected), ...secrets], 'pass', { allowlisted_keys_edited: Object.keys(expected).length, secrets_returned: false });
  await page.screenshot({ path: path.join(evidence, `${test.info().project.name}-global.png`), fullPage: true });
});

test('presets, reset, provider catalog, stale effective values, navigation and project isolation', async ({ page, request }) => {
  await open(page, 'models');
  const initial = await settings(request);
  const preset = initial.available_presets[0];
  const presetControl = page.locator('select').filter({ has: page.locator('option', { hasText: 'Apply Model Preset' }) });
  await presetControl.selectOption(preset.id);
  await expect(page.getByLabel('Primary model route model ID', { exact: true })).toHaveValue(preset.models.model_name);
  await saveProject(page);
  const presetDisk = await snapshot(request);
  const presetMismatches = Object.entries(preset.models).filter(([key, value]) => presetDisk.config.A[key] !== value).map(([key, expected]) => ({ key, expected, observed: presetDisk.config.A[key] }));
  record('model preset coverage', Object.keys(preset.models), presetMismatches.length ? 'fail' : 'pass', { preset: preset.id, mismatches: presetMismatches, recommendation: 'Apply scraper_model as well as pipeline model fields when using a preset.' });
  await page.getByTitle('Clear all project overrides to inherit 100% from .env', { exact: true }).click();
  await saveProject(page);
  for (const key of ['model_name', 'fallback_model', ...roles.map(([role]) => `${role}_model`)]) expect((await snapshot(request)).config.A[key]).toBeNull();
  expect((await snapshot(request)).config.A.generation_settings).toEqual({});
  await page.getByRole('button', { name: 'Load .env', exact: true }).click();
  await expect(page.getByLabel('Primary model route model ID', { exact: true })).toHaveValue('mock-audit-shared');
  await saveProject(page);
  expect((await snapshot(request)).config.A.model_name).toBe('mock-audit-shared');
  await page.getByTitle('Clear all project overrides to inherit 100% from .env', { exact: true }).click();
  await saveProject(page);
  const before = await settings(request);
  await page.getByRole('button', { name: /Environment & API Keys/ }).click();
  await page.getByLabel('Primary model model ID', { exact: true }).fill('mock-updated-global');
  await page.getByLabel('Custom OpenAI-compatible base URL', { exact: true }).fill(`${backend(test.info().project.name)}/api/audit/provider/v1`);
  await page.locator('#api-key-CUSTOM_API_KEY').fill('synthetic-catalog-only');
  await saveGlobal(page);
  await page.getByRole('button', { name: /Model Routing/ }).click();
  const primary = page.getByLabel('Primary model route model ID', { exact: true });
  const displayed = await primary.getAttribute('placeholder');
  const fresh = await settings(request);
  record('effective project model refresh after global save', ['NOVEL_MODEL', 'effective_model_name'], displayed === fresh.effective_model_name ? 'pass' : 'fail', { before: before.effective_model_name, displayed, fresh: fresh.effective_model_name, recommendation: 'Refresh project resolved settings after a successful global save.' });
  await primary.locator('xpath=..').getByRole('combobox').first().selectOption('custom');
  await primary.fill('audit-local-model');
  await primary.locator('xpath=ancestor::div[contains(@class,"space-y-2")][1]').getByRole('button', { name: 'Load custom catalog', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Refresh custom catalog (1)', exact: true })).toBeVisible();
  await saveProject(page);
  expect((await snapshot(request)).config.A.model_name).toBe('custom:audit-local-model');
  await open(page, 'general', fixture.projects.B);
  await expect(page.getByPlaceholder('Ascendance of a Bookworm')).toHaveValue('Audit B');
  await page.getByPlaceholder('Ascendance of a Bookworm').fill('Unsaved B');
  expect(await page.evaluate(() => Object.values(sessionStorage).join(' '))).not.toContain('Unsaved B');
  await page.reload();
  await expect(page.getByPlaceholder('Ascendance of a Bookworm')).toHaveValue('Audit B');
  await page.getByRole('button', { name: /Semantic Chunking/ }).click();
  await expect(page).toHaveURL(/section=chunking/);
  await page.reload();
  await expect(page.getByPlaceholder('800')).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/section=general/);
  record('presets/reset/load-env/custom catalog/navigation/A-B isolation', ['model_name', 'fallback_model', ...roles.map(([r]) => `${r}_model`), 'generation_settings', 'CUSTOM_API_BASE_URL', 'CUSTOM_API_KEY', 'title'], 'pass', { provider_catalog: 'Real localhost /models transport', unsaved_form_excluded_from_session: true });
});

test('numeric boundaries, blank fallback, accessibility, diagnostics and failed update check', async ({ page, request }) => {
  await open(page, 'chunking');
  // Keyboard save retains focus and reaches handleSave's fallback before blur.
  await page.getByPlaceholder('800').fill('');
  await page.keyboard.press('Control+s');
  await expect(page.getByText('Settings saved to config.yaml successfully!', { exact: true })).toBeVisible();
  const blank = await snapshot(request);
  record('blank threshold keyboard save', ['chunk_threshold_lines'], blank.config.A.chunk_threshold_lines === 800 ? 'pass' : 'fail', { observed: blank.config.A.chunk_threshold_lines, expected: 800, trigger: 'Clear threshold; Ctrl+S without blurring' });
  await open(page, 'chunking');
  await page.getByPlaceholder('400').fill('');
  await page.keyboard.press('Control+s');
  await expect(page.getByText('Settings saved to config.yaml successfully!', { exact: true })).toBeVisible();
  const size = await snapshot(request);
  record('blank size keyboard save', ['target_chunk_lines'], size.config.A.target_chunk_lines === 400 ? 'pass' : 'fail', { observed: size.config.A.target_chunk_lines, expected: 400 });
  await open(page, 'models');
  const extractor = page.getByLabel('Entity Extractor model model ID', { exact: true });
  const card = extractor.locator('xpath=ancestor::div[contains(@class,"space-y-3")][1]');
  await extractor.fill('mock-boundary');
  await card.getByLabel('Temperature', { exact: true }).fill('3');
  page.once('dialog', dialog => dialog.accept());
  const response = page.waitForResponse(r => r.url().includes('/api/settings') && r.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Save Settings', exact: true }).click();
  expect((await response).status()).toBe(400);
  expect((await snapshot(request)).config.A.extractor_model).toBeNull();
  record('invalid generation temperature rejected without persistence', ['generation_settings.extractor.temperature'], 'pass', { status: 400 });
  await open(page, 'all');
  const unnamed = await page.locator('form').getByRole('switch').evaluateAll(elements => elements.filter(e => !e.getAttribute('aria-label') && !e.getAttribute('aria-labelledby')).length);
  const unassociated = await page.locator('form label').evaluateAll(elements => elements.filter(e => !(e as HTMLLabelElement).control).length);
  const descriptors = await page.locator('form').getByRole('switch').evaluateAll(elements => elements.filter(e => !e.getAttribute('aria-label') && !e.getAttribute('aria-labelledby')).map(e => e.parentElement?.textContent?.trim().replace(/\s+/g, ' ').slice(0, 180)));
  record('settings accessible names', [], unnamed || unassociated ? 'fail' : 'pass', { unnamed_switches: unnamed, unassociated_labels: unassociated, unnamed_control_descriptors: descriptors, recommendation: 'Associate every visible label with its control and name switches.' });
  await page.setViewportSize({ width: 390, height: 844 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
  record('mobile settings page overflow', [], overflow ? 'fail' : 'pass', { width: 390, horizontal_overflow: overflow });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole('button', { name: /Logs & Diagnostics/ }).click();
  await expect(page.getByText('Local Logs & Diagnostics', { exact: true })).toBeVisible();
  await expect(page.getByText(fixture.root, { exact: false }).last()).toBeVisible();
  await page.getByRole('button', { name: /App Updates/ }).click();
  await page.getByRole('button', { name: 'Check for Updates', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Could not check GitHub releases');
  record('diagnostics isolation and update error handling', ['logs', 'updates'], 'pass', { logs_directory: 'isolated fixture logs', update_network: 'Blocked by fixture; real backend returns 502 and UI displays error', update_installation: 'excluded' });
});

test('two real browser forms reveal stale full-form save overwrite', async ({ page, context, request }) => {
  await open(page, 'general');
  const second = await context.newPage();
  await open(second, 'general');
  await page.getByPlaceholder('Ascendance of a Bookworm').fill('Saved from form A');
  await saveProject(page);
  await field(second.locator('form'), /^Genre$/).fill('romance');
  await saveProject(second);
  const disk = await snapshot(request);
  record('stale full-form save overwrite', ['title', 'genre'], disk.config.A.title === 'Saved from form A' ? 'pass' : 'fail', { first_save_title: 'Saved from form A', final_title: disk.config.A.title, final_genre: disk.config.A.genre, recommendation: 'Send changed fields or reject stale writes with a revision token.' });
  await second.close();
});

test('global malformed values and no-project settings remain observable', async ({ page, request }) => {
  await open(page, 'global');
  const shared = page.getByRole('heading', { name: 'Shared generation defaults', exact: true }).locator('xpath=..');
  await shared.getByLabel('Temperature', { exact: true }).fill('3');
  await page.getByRole('textbox', { name: 'Quality Defaults NOVEL_MAX_REVIEW_LOOPS', exact: true }).fill('not-a-number');
  await page.getByRole('textbox', { name: 'Rate Limit Defaults NOVEL_MAX_TPM', exact: true }).fill('-1');
  await saveGlobal(page);
  const disk = await snapshot(request);
  record('global semantic input validation', ['NOVEL_TEMPERATURE', 'NOVEL_MAX_REVIEW_LOOPS', 'NOVEL_MAX_TPM'], 'fail', { saved: { NOVEL_TEMPERATURE: disk.env_values.NOVEL_TEMPERATURE, NOVEL_MAX_REVIEW_LOOPS: disk.env_values.NOVEL_MAX_REVIEW_LOOPS, NOVEL_MAX_TPM: disk.env_values.NOVEL_MAX_TPM }, recommendation: 'Validate typed environment controls before persistence with the same ranges as project settings.' });
  await request.post(`${backend(test.info().project.name)}/api/audit/reset`);
  await request.post(`${backend(test.info().project.name)}/api/audit/no-project`);
  await page.goto('/settings?section=global');
  const skip = page.getByRole('button', { name: 'Skip & Continue', exact: true });
  await page.getByRole('button', { name: 'Save Global Settings', exact: true }).or(skip).first().waitFor();
  const startupStalled = await skip.isVisible();
  record('no-project startup permits global settings', ['NOVEL_PROJECTS_DIR'], startupStalled ? 'fail' : 'pass', { stalled: startupStalled, reason: startupStalled ? 'Startup requests chapters for uninitialized fallback cwd and receives HTTP 400.' : null, recommendation: 'Permit global settings on an empty registry without chapter readiness checks.' });
  if (startupStalled) await skip.click();
  await expect(page.getByRole('button', { name: 'Save Global Settings', exact: true })).toBeVisible();
  await page.getByRole('textbox', { name: 'Language Defaults TARGET_LANG', exact: true }).fill('Thai');
  await saveGlobal(page);
  expect((await snapshot(request)).env_values.TARGET_LANG).toBe('Thai');
  await page.getByRole('button', { name: /Novel Information/ }).click();
  await expect(page.getByText('No project selected or config.yaml not found.', { exact: true })).toBeVisible();
  record('no-project global save and project empty state', ['SOURCE_LANG', 'TARGET_LANG', 'title'], 'pass', { global_accessible: true, invalid_project_form: 'empty state shown' });
});

test('inherited entity toggle and legacy Interactions survive apparent clear-all', async ({ page, request }) => {
  const base = backend(test.info().project.name);
  expect((await request.put(`${base}/api/environment`, { data: { values: { NOVEL_FILTER_EXTRACTOR_ENTITIES: 'false', NOVEL_USE_INTERACTIONS: 'true' } } })).status()).toBe(200);
  await open(page, 'memory');
  const toggle = page.getByText('Extractor Known Entity Filtering', { exact: true }).locator('xpath=ancestor::*[.//button[@role="switch"]][1]').getByRole('switch');
  const disk = await snapshot(request);
  const displayed = await toggle.getAttribute('aria-checked');
  expect(disk.config.A.filter_extractor_entities).toBeNull();
  expect(disk.resolved.A.filter_extractor_entities).toBe(false);
  record('inherited entity filtering toggle display', ['filter_extractor_entities', 'NOVEL_FILTER_EXTRACTOR_ENTITIES'], displayed === String(disk.resolved.A.filter_extractor_entities) ? 'pass' : 'fail', { raw_project: null, effective: disk.resolved.A.filter_extractor_entities, displayed_checked: displayed, recommendation: 'Display the effective resolved Boolean and offer a separate inheritance state.' });
  expect((await request.put(`${base}/api/settings?${new URLSearchParams({ project_path: fixture.projects.A })}`, { data: { use_interactions_api: false } })).status()).toBe(200);
  await open(page, 'models');
  await page.getByTitle('Clear all project overrides to inherit 100% from .env', { exact: true }).click();
  await saveProject(page);
  const cleared = await snapshot(request);
  const legacy = cleared.config.A.use_interactions_api;
  record('clear all preserves legacy Interactions override', ['use_interactions_api', 'generation_settings'], legacy === null ? 'pass' : 'fail', { legacy_override_after_clear: legacy, shared_env: 'true', effective_roles: Object.fromEntries(roles.map(([role]) => [role, cleared.resolved.A.generation[role].use_interactions_api])), recommendation: 'Clear the legacy project-wide override together with role generation overrides.' });
});
