import { test, expect } from '@playwright/test';

test.describe('Design Token Consistency & Styling', () => {
  test('Warm Canvas Design System Theme Colors', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('header');

    // Verify Body styles
    const bodyStyles = await page.evaluate(() => {
      const body = document.body;
      const computed = window.getComputedStyle(body);
      return {
        backgroundColor: computed.backgroundColor,
        color: computed.color,
        fontFamily: computed.fontFamily,
      };
    });

    console.log('Computed Body Styles:', bodyStyles);

    // #2b2622 in RGB is rgb(43, 38, 34)
    expect(bodyStyles.backgroundColor).toBe('rgb(43, 38, 34)');
    // #f7f5f0 in RGB is rgb(247, 245, 240)
    expect(bodyStyles.color).toBe('rgb(247, 245, 240)');
    // Font family should reference Inter
    expect(bodyStyles.fontFamily.toLowerCase()).toContain('inter');
  });

  test('Header Surface and Hairline Border Styling', async ({ page }) => {
    await page.goto('/');
    const header = page.locator('header');
    await header.waitFor();

    const headerStyles = await header.evaluate((el) => {
      const computed = window.getComputedStyle(el);
      return {
        backgroundColor: computed.backgroundColor,
        borderBottomColor: computed.borderBottomColor,
        borderBottomWidth: computed.borderBottomWidth,
      };
    });

    console.log('Computed Header Styles:', headerStyles);
    expect(headerStyles.backgroundColor).toBe('rgb(43, 38, 34)');
    // Border hairline #3f3a36 is rgb(63, 58, 54)
    expect(headerStyles.borderBottomColor).toBe('rgb(63, 58, 54)');
    expect(headerStyles.borderBottomWidth).toBe('1px');
  });

  test('Button and Card Variant Consistency', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('header');

    // Check tabs styling
    const tabs = page.locator('header button');
    const firstTab = tabs.first();
    await expect(firstTab).toBeVisible();

    const tabStyles = await firstTab.evaluate((el) => {
      const computed = window.getComputedStyle(el);
      return {
        borderRadius: computed.borderRadius,
        fontSize: computed.fontSize,
      };
    });

    console.log('Tab Button Styles:', tabStyles);
    // Radius should be 3px or 4px according to design tokens
    expect(['3px', '4px']).toContain(tabStyles.borderRadius);
  });

  test('Typography Font-Family Consistency Across Elements', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('header');

    // Switch to Traces tab to inspect DM Mono and code styling
    const tracesTab = page.locator('header').getByRole('button', { name: 'Traces', exact: true });
    if ((await tracesTab.count()) > 0) {
      await tracesTab.click();
      await page.waitForTimeout(300);

      const monoElements = page.locator('.font-mono, select');
      if ((await monoElements.count()) > 0) {
        const fontFamily = await monoElements.first().evaluate((el) => {
          return window.getComputedStyle(el).fontFamily;
        });
        console.log('Monospace Element Font Family:', fontFamily);
        expect(
          fontFamily.toLowerCase().includes('mono') ||
          fontFamily.toLowerCase().includes('consolas') ||
          fontFamily.toLowerCase().includes('menlo')
        ).toBeTruthy();
      }
    }
  });
});
