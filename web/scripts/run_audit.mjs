import { chromium } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const webRoot = path.resolve(__dirname, '..');
const resultsDir = path.join(webRoot, 'audit-results');
const screenshotsDir = path.join(resultsDir, 'screenshots');

// Ensure output directories exist
fs.mkdirSync(screenshotsDir, { recursive: true });

const BASE_URL = 'http://localhost:5173';

const VIEWPORTS = [
  { name: 'desktop-hd', width: 1920, height: 1080, deviceScaleFactor: 1 },
  { name: 'laptop', width: 1440, height: 900, deviceScaleFactor: 1 },
  { name: 'tablet', width: 1024, height: 768, deviceScaleFactor: 2 },
  { name: 'mobile', width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 3 },
];

const TABS = [
  { id: 'studio', label: 'Studio' },
  { id: 'reader', label: 'Reader' },
  { id: 'bible', label: 'Novel Bible' },
  { id: 'traces', label: 'Traces' },
  { id: 'settings', label: 'Settings' },
];

async function runAudit() {
  console.log('🐾 [Nousetsu] Launching Playwright Chromium for UI & Performance Audit (=^･ω･^=)...');

  const browser = await chromium.launch({
    channel: 'chrome',
    headless: true,
  });

  const auditReport = {
    timestamp: new Date().toISOString(),
    baseUrl: BASE_URL,
    performance: {},
    layout: {},
    designConsistency: {},
    screenshots: [],
    consoleErrors: [],
    networkFailures: [],
  };

  try {
    // 1. Performance & Core Web Vitals Audit on Desktop
    console.log('📊 Benchmarking Navigation & Load Performance on Desktop HD...');
    const context = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
    });
    const page = await context.newPage();

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        auditReport.consoleErrors.push({
          location: 'console',
          text: msg.text(),
        });
      }
    });

    page.on('requestfailed', (req) => {
      auditReport.networkFailures.push({
        url: req.url(),
        failure: req.failure()?.errorText || 'Unknown failure',
      });
    });

    const startNav = Date.now();
    const resp = await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('header', { timeout: 10000 });
    await page.waitForTimeout(500);
    const fullLoadTime = Date.now() - startNav;

    const navTiming = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0];
      const paint = performance.getEntriesByType('paint');
      const fcp = paint.find((p) => p.name === 'first-contentful-paint');

      return {
        dnsMs: nav ? Math.round(nav.domainLookupEnd - nav.domainLookupStart) : 0,
        tcpMs: nav ? Math.round(nav.connectEnd - nav.connectStart) : 0,
        ttfbMs: nav ? Math.round(nav.responseStart - nav.requestStart) : 0,
        domInteractiveMs: nav ? Math.round(nav.domInteractive - nav.startTime) : 0,
        domContentLoadedMs: nav ? Math.round(nav.domContentLoadedEventEnd - nav.startTime) : 0,
        loadCompleteMs: nav ? Math.round(nav.loadEventEnd - nav.startTime) : 0,
        fcpMs: fcp ? Math.round(fcp.startTime) : 0,
        domNodeCount: document.getElementsByTagName('*').length,
      };
    });

    auditReport.performance.initialLoad = {
      status: resp?.status(),
      totalNetworkIdleTimeMs: fullLoadTime,
      ...navTiming,
    };

    // Tab Switch Latencies
    console.log('⚡ Measuring Workspace Transition Latencies...');
    const tabLatencies = {};
    for (const tab of TABS) {
      const btn = page.locator('header').getByRole('button', { name: tab.label, exact: true });
      if ((await btn.count()) > 0) {
        const t0 = Date.now();
        await btn.click();
        await page.waitForTimeout(150);
        tabLatencies[tab.id] = Date.now() - t0;
      }
    }
    auditReport.performance.tabSwitchLatencies = tabLatencies;

    // Design Token Validation
    console.log('🎨 Validating Warm Canvas Design Tokens & CSS Properties...');
    const designTokens = await page.evaluate(() => {
      const body = document.body;
      const bodyComputed = window.getComputedStyle(body);
      const header = document.querySelector('header');
      const headerComputed = header ? window.getComputedStyle(header) : null;

      // Sample a card
      const card = document.querySelector('.card-mockup, .bg-\\[\\#383330\\], [class*="bg-[#383330]"]');
      const cardComputed = card ? window.getComputedStyle(card) : null;

      return {
        body: {
          backgroundColor: bodyComputed.backgroundColor,
          color: bodyComputed.color,
          fontFamily: bodyComputed.fontFamily,
        },
        header: headerComputed
          ? {
              backgroundColor: headerComputed.backgroundColor,
              borderBottomColor: headerComputed.borderBottomColor,
              borderBottomWidth: headerComputed.borderBottomWidth,
            }
          : null,
        card: cardComputed
          ? {
              backgroundColor: cardComputed.backgroundColor,
              borderRadius: cardComputed.borderRadius,
            }
          : null,
      };
    });

    auditReport.designConsistency = designTokens;
    await context.close();

    // 2. Multi-Viewport Responsive & Layout Audit
    console.log('📱 Auditing Multi-Viewport Layouts & Overflow Leaks...');
    for (const vp of VIEWPORTS) {
      console.log(`   -> Testing Viewport: ${vp.name} (${vp.width}x${vp.height})`);
      const vpContext = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        isMobile: vp.isMobile || false,
        hasTouch: vp.hasTouch || false,
        deviceScaleFactor: vp.deviceScaleFactor || 1,
      });

      const vpPage = await vpContext.newPage();
      await vpPage.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
      await vpPage.waitForSelector('header');

      const vpResult = {
        viewport: `${vp.width}x${vp.height}`,
        tabs: {},
      };

      for (const tab of TABS) {
        const btn = vpPage.locator('header').getByRole('button', { name: tab.label, exact: true });
        if ((await btn.count()) > 0) {
          await btn.click();
          await vpPage.waitForTimeout(300);

          // Check horizontal overflow
          const overflow = await vpPage.evaluate(() => {
            const docEl = document.documentElement;
            const scrollW = Math.max(docEl.scrollWidth, document.body.scrollWidth);
            const clientW = docEl.clientWidth;
            return {
              scrollWidth: scrollW,
              clientWidth: clientW,
              hasLeak: scrollW > clientW + 2,
            };
          });

          // Take screenshot
          const screenshotName = `${vp.name}_${tab.id}.png`;
          const screenshotPath = path.join(screenshotsDir, screenshotName);
          await vpPage.screenshot({ path: screenshotPath, fullPage: false });

          auditReport.screenshots.push({
            viewport: vp.name,
            tab: tab.id,
            file: screenshotName,
            path: screenshotPath,
          });

          vpResult.tabs[tab.id] = {
            horizontalOverflow: overflow.hasLeak,
            scrollWidth: overflow.scrollWidth,
            clientWidth: overflow.clientWidth,
          };
        }
      }

      auditReport.layout[vp.name] = vpResult;
      await vpContext.close();
    }

    console.log('✨ All Viewports and Tests Processed successfully!');
  } finally {
    await browser.close();
  }

  // Write JSON report
  const jsonPath = path.join(resultsDir, 'audit_summary.json');
  fs.writeFileSync(jsonPath, JSON.stringify(auditReport, null, 2), 'utf8');
  console.log(`📝 JSON Audit summary saved to: ${jsonPath}`);

  return auditReport;
}

runAudit()
  .then((report) => {
    console.log('🐾 [Nousetsu] Playwright UI Audit Completed (=^･ω･^=) nya~!');
    process.exit(0);
  })
  .catch((err) => {
    console.error('❌ Audit encountered an error:', err);
    process.exit(1);
  });
