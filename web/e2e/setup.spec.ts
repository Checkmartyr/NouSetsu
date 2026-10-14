import { expect, test, type Page } from '@playwright/test';
import { mockBackend } from './helpers/mockBackend';

async function setupBackend(page: Page) {
  await mockBackend(page);
  let revision = 'initial';
  let completed = false;
  let conflict = false;
  const submissions: any[] = [];
  await page.route('**/api/setup**', async route => {
    const endpoint = new URL(route.request().url()).pathname;
    if (endpoint === '/api/setup') return route.fulfill({ json: {
      completed, existing: false, locale: 'en', readiness: 'not_connected',
      provider: 'gemini', model: '', providers: { gemini: false, openai: false, openrouter: false, custom: false },
      semantic_retrieval: false, installation: 'python',
      values: { SOURCE_LANG: 'auto', TARGET_LANG: 'English', NOVEL_PROJECTS_DIR: 'C:/Users/Reader/Documents/NouSetsu' },
      environment: { values: {}, api_key_status: {}, revision },
      fields: ['SOURCE_LANG', 'TARGET_LANG', 'NOVEL_PROJECTS_DIR', 'CUSTOM_API_BASE_URL', 'NOVEL_MAX_REVIEW_LOOPS', 'NOVEL_QUALITY_THRESHOLD'], revision,
    } });
    const body = route.request().postDataJSON();
    if (endpoint.endsWith('/check')) {
      if (body.kind === 'catalog') return route.fulfill({ json: { success: true, models: ['vendor/model'] } });
      if (body.kind === 'folder') return route.fulfill({ json: { path: 'C:/Books/นิยาย' } });
      return route.fulfill({ json: { success: true, readiness: 'tested' } });
    }
    if (endpoint.endsWith('/complete')) {
      submissions.push(body);
      if (conflict) { conflict = false; revision = 'updated'; return route.fulfill({ status: 412, json: { detail: 'Settings changed' } }); }
      expect(route.request().headers()['if-match']).toBe(`"${revision}"`);
      completed = true;
      return route.fulfill({ json: { success: true, settings_saved: true, revision: 'saved' } });
    }
    await route.fulfill({ status: 404, json: {} });
  });
  return { submissions, conflict: () => { conflict = true; } };
}

test('fresh installation offers Thai exploration, folder selection and Studio', async ({ page }) => {
  const backend = await setupBackend(page);
  await page.goto('/studio');
  await expect(page).toHaveURL(/\/setup/);
  await page.getByRole('combobox', { name: 'Language / ภาษา' }).selectOption('th');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('ตั้งค่า NouSetsu ให้พร้อมใช้งาน');
  await page.getByRole('button', { name: 'ถัดไป', exact: true }).click();
  await page.getByRole('button', { name: 'ตั้งค่า AI ภายหลัง' }).click();
  await expect(page.getByRole('combobox', { name: 'แปลเป็นภาษา' })).toHaveValue('Thai');
  await page.getByRole('button', { name: 'ถัดไป', exact: true }).click();
  await page.getByRole('button', { name: 'เลือกโฟลเดอร์', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'โฟลเดอร์นิยาย' })).toHaveValue('C:/Books/นิยาย');
  await page.getByRole('button', { name: 'ถัดไป', exact: true }).click();
  await page.getByRole('button', { name: 'บันทึกการตั้งค่า' }).click();
  await expect(page.getByRole('heading', { name: 'พร้อมเริ่มใช้งานแล้ว' })).toBeVisible();
  expect(backend.submissions[0].skip_ai).toBe(true);
  expect(backend.submissions[0].locale).toBe('th');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole('button', { name: 'สำรวจ Studio' }).click();
  await expect(page).toHaveURL(/\/studio/);
});

test('OpenRouter connects explicitly and keys never enter browser storage', async ({ page }) => {
  const backend = await setupBackend(page);
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: 'OpenRouter', exact: true }).click();
  const key = page.getByRole('textbox', { name: 'Connection key', exact: true });
  await key.fill('private-unsaved-key');
  await expect(key).toHaveAttribute('type', 'password');
  await page.getByRole('button', { name: 'Show', exact: true }).click();
  await expect(key).toHaveAttribute('type', 'text');
  await page.getByRole('button', { name: 'Load available models' }).click();
  await page.getByRole('combobox', { name: 'AI model', exact: true }).fill('vendor/model');
  await page.getByRole('button', { name: 'Test connection' }).click();
  await expect(page.getByRole('status')).toContainText('Connection tested successfully');
  const storage = await page.evaluate(() => JSON.stringify({ ...sessionStorage, ...localStorage }));
  expect(storage).not.toContain('private-unsaved-key');
  for (let step = 0; step < 3; step++) await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: 'Finish setup', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'You’re ready to begin' })).toBeVisible();
  expect(backend.submissions[0].provider).toBe('openrouter');
  expect(backend.submissions[0].route_all).toBe(true);
  expect(backend.submissions[0].api_keys.OPENROUTER_API_KEY).toBe('private-unsaved-key');
  expect(await page.evaluate(() => sessionStorage.getItem('nousetsu_setup_draft'))).toBeNull();
});

test('refresh restores nonsecret drafts and conflict keeps edits for explicit reload', async ({ page }) => {
  const backend = await setupBackend(page);
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('textbox', { name: 'Connection key', exact: true }).fill('key-discarded-on-refresh');
  await page.getByRole('combobox', { name: 'AI model', exact: true }).fill('gemini-manual');
  await page.reload();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Connection key', exact: true })).toHaveValue('');
  await page.getByRole('button', { name: 'Set up AI later' }).click();
  await page.getByRole('combobox', { name: 'Translate into' }).fill('French');
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  backend.conflict();
  await page.getByRole('button', { name: 'Finish setup', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Settings changed elsewhere');
  await page.getByRole('button', { name: 'Reload saved settings; keep my draft' }).click();
  await page.getByRole('button', { name: 'Finish setup', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'You’re ready to begin' })).toBeVisible();
  expect(backend.submissions[1].values.TARGET_LANG).toBe('French');
});

test('keyboard navigation retains focus and exposes Advanced settings', async ({ page }) => {
  await setupBackend(page);
  await page.goto('/setup');
  await page.getByRole('button', { name: 'Continue', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { level: 1 })).toBeFocused();
  await page.getByRole('button', { name: 'Set up AI later' }).click();
  await page.getByText('Advanced installation settings', { exact: true }).click();
  await expect(page.getByText('Blank values inherit defaults. Each novel can have its own settings.')).toBeVisible();
  await page.getByText('Quality Defaults', { exact: true }).click();
  await page.getByRole('textbox', { name: 'Maximum review passes' }).fill('2');
  await expect(page.getByRole('checkbox', { name: 'Use recommended quality settings' })).not.toBeChecked();
});
