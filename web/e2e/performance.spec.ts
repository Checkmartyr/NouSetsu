import { test, expect } from '@playwright/test';

test.describe('Performance Benchmarks', () => {
  test('Initial Page Load and Navigation Timings', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    const startTime = Date.now();
    const response = await page.goto('/');
    expect(response?.status()).toBe(200);

    // Wait for the app container to mount
    await page.waitForSelector('header');
    const loadTimeMs = Date.now() - startTime;

    // Collect Navigation Timing API metrics
    const timing = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      return {
        dns: nav ? Math.round(nav.domainLookupEnd - nav.domainLookupStart) : 0,
        tcp: nav ? Math.round(nav.connectEnd - nav.connectStart) : 0,
        ttfb: nav ? Math.round(nav.responseStart - nav.requestStart) : 0,
        domInteractive: nav ? Math.round(nav.domInteractive - nav.startTime) : 0,
        domContentLoaded: nav ? Math.round(nav.domContentLoadedEventEnd - nav.startTime) : 0,
        loadComplete: nav ? Math.round(nav.loadEventEnd - nav.startTime) : 0,
      };
    });

    console.log('Navigation Performance Metrics:', timing, `Total Load Time: ${loadTimeMs}ms`);

    // Verify reasonable thresholds for local dev server
    expect(timing.ttfb).toBeLessThan(1500);
    expect(timing.domContentLoaded).toBeLessThan(3000);

    // Verify 0 uncaught errors on initial load
    const fatalErrors = consoleErrors.filter(
      (err) => !err.includes('favicon') && !err.includes('status of 404')
    );
    expect(fatalErrors).toEqual([]);
  });

  test('Workspace Tab Switching Latency & Rendering', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('header');

    const tabs = ['Studio', 'Reader', 'Novel Bible', 'Traces', 'Settings'];
    const transitionTimes: Record<string, number> = {};

    for (const tabName of tabs) {
      const button = page.locator('header').getByRole('button', { name: tabName, exact: true });
      if ((await button.count()) > 0) {
        const t0 = Date.now();
        await button.click();
        await page.waitForTimeout(100); // Allow render tick
        transitionTimes[tabName] = Date.now() - t0;
      }
    }

    console.log('Tab Transition Latencies (ms):', transitionTimes);
    for (const [, duration] of Object.entries(transitionTimes)) {
      expect(duration).toBeLessThan(1000);
    }
  });

  test('DOM Node Count & Memory Footprint', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('header');

    // Count DOM nodes across tabs
    const nodeCount = await page.evaluate(() => document.getElementsByTagName('*').length);
    console.log(`DOM Node Count on Initial View: ${nodeCount}`);
    expect(nodeCount).toBeLessThan(5000); // Prevents bloated initial DOM trees
  });
});
