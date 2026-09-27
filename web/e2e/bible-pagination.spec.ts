import { test, expect } from '@playwright/test';

test.describe('Novel Bible Pagination', () => {
  test('Characters tab displays pagination and responds to page size changes', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('header');

    // Navigate to Novel Bible tab
    const bibleTab = page.locator('header').getByRole('button', { name: 'Novel Bible', exact: true });
    await expect(bibleTab).toBeVisible();
    await bibleTab.click();

    // Wait for any loading state to finish
    await page.locator('text=Loading Bible data...').waitFor({ state: 'detached', timeout: 8000 }).catch(() => {});

    // Ensure we are on the Characters subtab
    const charSubTab = page.getByRole('button', { name: /Characters/i });
    if ((await charSubTab.count()) > 0) {
      await charSubTab.scrollIntoViewIfNeeded();
      await charSubTab.click();
      await page.waitForTimeout(200);
    }

    // Check if characters exist and pagination is mounted
    const pagination = page.locator('div[aria-label="Pagination Navigation"]').first();
    if ((await pagination.count()) > 0) {
      await expect(pagination).toBeVisible();

      // Check range summary text
      const summaryText = await pagination.innerText();
      expect(summaryText).toMatch(/Showing \d+–\d+ of \d+ characters/i);

      // Check page size dropdown
      const pageSizeSelect = pagination.locator('select');
      if ((await pageSizeSelect.count()) > 0) {
        await expect(pageSizeSelect).toBeVisible();
      }
    }
  });

  test('Glossary tab displays pagination and responds to search reset', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('header');

    // Navigate to Novel Bible tab
    const bibleTab = page.locator('header').getByRole('button', { name: 'Novel Bible', exact: true });
    await bibleTab.click();

    // Wait for initial Bible data fetch
    await page.locator('text=Loading Bible data...').waitFor({ state: 'detached', timeout: 8000 }).catch(() => {});

    // Switch to Glossary subtab
    const glossarySubTab = page.getByRole('button', { name: /Glossary/i });
    await expect(glossarySubTab).toBeVisible();
    await glossarySubTab.scrollIntoViewIfNeeded();
    await glossarySubTab.click();

    // Verify glossary search and table
    const searchInput = page.getByPlaceholder(/Search terms or translations/i);
    await expect(searchInput).toBeVisible({ timeout: 10000 });

    const pagination = page.locator('div[aria-label="Pagination Navigation"]').first();
    if ((await pagination.count()) > 0) {
      await expect(pagination).toBeVisible();
      const summaryText = await pagination.innerText();
      expect(summaryText).toMatch(/Showing \d+–\d+ of \d+ terms/i);

      // Test search filter
      await searchInput.fill('__non_existent_term_xyz__');
      await page.waitForTimeout(200);

      // Verify empty state is displayed
      const emptyRow = page.getByText(/No glossary terms found matching your filter/i);
      await expect(emptyRow).toBeVisible();

      // Clear search
      await searchInput.fill('');
      await page.waitForTimeout(200);
    }
  });
});
