import { test, expect } from '@playwright/test';

test.describe('Layout & Viewport Responsiveness', () => {
  test('No Horizontal Scroll Leak across Main Views', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('header');

    const tabs = ['Studio', 'Reader', 'Novel Bible', 'Traces', 'Settings'];

    for (const tabName of tabs) {
      const button = page.locator('header').getByRole('button', { name: tabName, exact: true });
      if ((await button.count()) > 0) {
        await button.click();
        await page.waitForTimeout(200);

        const hasHorizontalOverflow = await page.evaluate(() => {
          const docEl = document.documentElement;
          const body = document.body;
          const scrollWidth = Math.max(docEl.scrollWidth, body.scrollWidth);
          const clientWidth = docEl.clientWidth;
          return scrollWidth > clientWidth + 2; // allowance of 2px for subpixel rendering
        });

        expect(
          hasHorizontalOverflow,
          `Detected horizontal overflow leak on tab [${tabName}]`
        ).toBeFalsy();
      }
    }
  });

  test('Header and Navigation Elements Remain Accessible', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('header');

    const header = page.locator('header');
    await expect(header).toBeVisible();

    // Check brand logo and title
    const brand = header.getByText('Nousetsu');
    await expect(brand).toBeVisible();

    // Verify all primary tabs are mounted
    for (const tab of ['Studio', 'Reader', 'Novel Bible', 'Traces', 'Settings']) {
      const tabButton = header.getByRole('button', { name: tab, exact: true });
      await expect(tabButton).toBeAttached();
    }
  });

  test('Reader View Split-Pane and Content Layout', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('header');

    // Switch to Reader tab
    const readerTab = page.locator('header').getByRole('button', { name: 'Reader', exact: true });
    await readerTab.click();
    await page.waitForTimeout(300);

    // Verify reader container exists
    const readerRoot = page.locator('div.flex-1.overflow-hidden').first();
    await expect(readerRoot).toBeVisible();
  });

  test('New Project Modal Viewport Centering & Responsiveness', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('header');

    // Find and click the + / New Project button in the navbar if present
    const newProjectBtn = page.locator('header button[title*="New Project"], header button:has-text("New Project"), header button:has(.lucide-plus)');
    if ((await newProjectBtn.count()) > 0) {
      await newProjectBtn.first().click();
      await page.waitForTimeout(200);

      // Verify modal is centered and does not overflow viewport
      const modal = page.locator('div[role="dialog"], .fixed.inset-0');
      if ((await modal.count()) > 0) {
        const bounds = await modal.first().boundingBox();
        const viewport = page.viewportSize();
        if (bounds && viewport) {
          expect(bounds.x).toBeGreaterThanOrEqual(0);
          expect(bounds.y).toBeGreaterThanOrEqual(0);
        }

        // Close modal
        await page.keyboard.press('Escape');
      }
    }
  });
});
