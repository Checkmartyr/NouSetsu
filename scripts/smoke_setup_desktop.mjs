// Run a hidden Tauri/WebView2 setup flow against an isolated source fixture.
// Build the debug executable with devUrl=http://127.0.0.1:15474 and visible=false.
import { chromium, expect } from '../web/node_modules/playwright/test.mjs';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import net from 'node:net';
import { spawn, execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
for (const port of [15474, 5197]) {
  const server = net.createServer();
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(port, '127.0.0.1', resolve); });
  await new Promise(resolve => server.close(resolve));
}
const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'nousetsu-desktop-setup-'));
fs.cpSync(path.join(root, 'src'), path.join(fixture, 'src'), { recursive: true });
fs.cpSync(path.join(root, 'web/dist'), path.join(fixture, 'web/dist'), { recursive: true });
const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith('NOVEL_') && !key.startsWith('NOUSETSU_') && !['GEMINI_API_KEY','GOOGLE_API_KEY','OPENAI_API_KEY','OPENROUTER_API_KEY','CUSTOM_API_KEY','DEFAULT_MODEL','SOURCE_LANG','TARGET_LANG'].includes(key)));
Object.assign(env, {
  NOUSETSU_PROJECT_DIR: fixture, NOUSETSU_PYTHON: path.join(root, '.venv/Scripts/python.exe'),
  NOVEL_REGISTRY_DIR: path.join(fixture, 'registry'),
  WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: '--remote-debugging-port=5197',
  WEBVIEW2_USER_DATA_FOLDER: path.join(fixture, 'webview'),
});
const child = spawn(path.resolve(process.argv[2] || path.join(root, 'src-tauri/target/debug/nousetsu-desktop.exe')), [], { cwd: fixture, env, windowsHide: true, stdio: 'ignore' });
let browser;
try {
  for (let attempt = 0; attempt < 100; attempt++) {
    try { browser = await chromium.connectOverCDP('http://127.0.0.1:5197'); break; }
    catch { if (child.exitCode !== null) throw new Error('Native app exited before WebView2 became ready'); await new Promise(resolve => setTimeout(resolve, 300)); }
  }
  if (!browser) throw new Error('Native WebView2 did not become ready');
  let page;
  for (let attempt = 0; attempt < 100; attempt++) {
    page = browser.contexts().flatMap(context => context.pages()).find(page => page.url().includes(':15474'));
    if (page) break;
    await new Promise(resolve => setTimeout(resolve, 300));
  }
  if (!page) throw new Error('Owned native app page was not found');
  page.setDefaultTimeout(30000);
  expect(await page.evaluate(() => '__TAURI_INTERNALS__' in window)).toBe(true);
  const context = await (await fetch('http://127.0.0.1:15474/api/desktop-info')).json();
  expect(path.resolve(context.env_file_path)).toBe(path.join(fixture, '.env'));
  await expect(page).toHaveURL(/\/setup/);
  await page.getByRole('combobox', { name: 'Language / ภาษา' }).selectOption('th');
  await page.getByRole('button', { name: 'ถัดไป', exact: true }).click();
  await page.getByRole('button', { name: 'ตั้งค่า AI ภายหลัง' }).click();
  await expect(page.getByRole('combobox', { name: 'แปลเป็นภาษา' })).toHaveValue('Thai');
  await page.getByRole('button', { name: 'ถัดไป', exact: true }).click();
  await page.getByRole('textbox', { name: 'โฟลเดอร์นิยาย' }).fill(path.join(fixture, 'novels'));
  await page.getByRole('button', { name: 'ถัดไป', exact: true }).click();
  await page.getByRole('button', { name: 'บันทึกการตั้งค่า' }).click();
  await expect(page.getByRole('heading', { name: 'พร้อมเริ่มใช้งานแล้ว' })).toBeVisible();
  expect(JSON.parse(fs.readFileSync(path.join(fixture, 'setup.json'), 'utf8')).locale).toBe('th');
  await page.getByRole('button', { name: 'สำรวจ Studio' }).click();
  await expect(page).toHaveURL(/\/studio/);
  await page.goto('http://127.0.0.1:15474/setup');
  await expect(page.getByRole('heading', { name: 'ตั้งค่า NouSetsu ให้พร้อมใช้งาน' })).toBeVisible();
  const screenshot = path.join(root, 'audit-results/setup/native-thai.png');
  fs.mkdirSync(path.dirname(screenshot), { recursive: true });
  await page.screenshot({ path: screenshot, fullPage: true });
  console.log('Actual Tauri WebView2: Thai setup, persistence, Studio and reopening passed');
} finally {
  if (child.pid && child.exitCode === null) {
    try { execFileSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }); } catch { /* Owned process already exited. */ }
  }
  if (browser) await browser.close().catch(() => {});
  // Retain the isolated fixture for diagnosis; never remove host application data.
}
