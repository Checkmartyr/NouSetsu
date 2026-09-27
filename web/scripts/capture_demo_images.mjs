import { chromium } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..', '..');
const imagesDir = path.join(repoRoot, 'docs', 'images');

const BASE_URL = 'http://localhost:5173';

async function capture() {
  console.log('🐾 Launching Chromium to capture Web Studio demo images (=^･ω･^=)...');

  const browser = await chromium.launch({
    channel: 'chrome',
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
  });

  const page = await context.newPage();

  try {
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('header', { timeout: 10000 });
    await page.waitForTimeout(1000);

    // ==========================================
    // 1. Studio Workspace View
    // ==========================================
    console.log('📸 Capturing web_studio_dashboard_demo.png (Studio View)...');
    const studioTab = page.locator('header').getByRole('button', { name: 'Studio', exact: true });
    await studioTab.click();
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: path.join(imagesDir, 'web_studio_dashboard_demo.png'),
      fullPage: false,
    });

    // ==========================================
    // 2. Reader Workspace View
    // ==========================================
    console.log('📸 Capturing web_studio_reader_demo.png (Reader View)...');
    const readerTab = page.locator('header').getByRole('button', { name: 'Reader', exact: true });
    await readerTab.click();
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: path.join(imagesDir, 'web_studio_reader_demo.png'),
      fullPage: false,
    });

    // ==========================================
    // 3. Novel Bible Workspace View
    // ==========================================
    console.log('📸 Capturing web_studio_bible_demo.png (Novel Bible View)...');
    const bibleTab = page.locator('header').getByRole('button', { name: 'Novel Bible', exact: true });
    await bibleTab.click();
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: path.join(imagesDir, 'web_studio_bible_demo.png'),
      fullPage: false,
    });

    // ==========================================
    // 4. Traces Workspace (Traces, Diff, Tokens)
    // ==========================================
    const tracesTab = page.locator('header').getByRole('button', { name: 'Traces', exact: true });
    await tracesTab.click();
    await page.waitForTimeout(500);

    // If Demo button is present, click it to ensure full demo data
    const demoBtn = page.getByRole('button', { name: 'Demo' });
    if ((await demoBtn.count()) > 0 && (await demoBtn.isVisible())) {
      await demoBtn.click();
      await page.waitForTimeout(400);
    }

    // 4a. Traces & Extraction Output View
    console.log('📸 Capturing web_studio_traces_demo.png...');
    const outputTabBtn = page.getByRole('button', { name: 'Output', exact: true });
    if (await outputTabBtn.count() > 0) {
      await outputTabBtn.click();
      await page.waitForTimeout(300);
    }
    await page.screenshot({
      path: path.join(imagesDir, 'web_studio_traces_demo.png'),
      fullPage: false,
    });

    // 4b. Diff Comparison View
    console.log('📸 Capturing web_studio_diff_demo.png...');
    const diffTabBtn = page.getByRole('button', { name: /Diff Comparison/i });
    if (await diffTabBtn.count() > 0 && await diffTabBtn.isVisible()) {
      await diffTabBtn.click();
      await page.waitForTimeout(500);
      await page.screenshot({
        path: path.join(imagesDir, 'web_studio_diff_demo.png'),
        fullPage: false,
      });
    }

    // 4c. Token & Latency Analytics View
    console.log('📸 Capturing web_studio_tokens_demo.png...');
    const tokensTabBtn = page.getByRole('button', { name: /Token & Latency Analytics/i });
    if (await tokensTabBtn.count() > 0 && await tokensTabBtn.isVisible()) {
      await tokensTabBtn.click();
      await page.waitForTimeout(500);
      await page.screenshot({
        path: path.join(imagesDir, 'web_studio_tokens_demo.png'),
        fullPage: false,
      });
    }

    // ==========================================
    // 5. Settings Workspace View
    // ==========================================
    console.log('📸 Capturing web_studio_settings_demo.png (Settings View)...');
    const settingsTab = page.locator('header').getByRole('button', { name: 'Settings', exact: true });
    await settingsTab.click();
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: path.join(imagesDir, 'web_studio_settings_demo.png'),
      fullPage: false,
    });

    console.log('✨ All demo images captured successfully nya~! (=^･ω･^=)');
  } catch (err) {
    console.error('❌ Capture failed:', err);
  } finally {
    await browser.close();
  }
}

capture();
