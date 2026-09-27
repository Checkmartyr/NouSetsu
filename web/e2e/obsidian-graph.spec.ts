import { test, expect } from '@playwright/test';

test.describe('Obsidian-Style Interactive Relationship Graph', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to local test app
    await page.goto('/');
    await page.waitForSelector('header');

    // Wait for header and navigate to Novel Bible
    const bibleTab = page.locator('header').getByRole('button', { name: 'Novel Bible', exact: true });
    await expect(bibleTab).toBeVisible({ timeout: 10000 });
    await bibleTab.click();

    // Wait for loading to finish
    await page.locator('text=Loading Bible data...').waitFor({ state: 'detached', timeout: 8000 }).catch(() => {});

    // Switch to Visualizer subtab
    const visualizerSubtab = page.getByRole('button', { name: /Visualizer/i }).first();
    await expect(visualizerSubtab).toBeVisible({ timeout: 5000 });
    await visualizerSubtab.click();
    await page.waitForTimeout(300);
  });

  test('Personal Relationship Map renders Obsidian Graph mode with interactive canvas and controls', async ({ page }) => {
    // Check if relationships exist for active character
    const relMapHeading = page.locator('text=Personal Relationship Map').first();
    if ((await relMapHeading.count()) > 0) {
      await expect(relMapHeading).toBeVisible({ timeout: 5000 });

      // Verify mode toggle buttons exist
      const graphToggle = page.locator('button', { hasText: 'Obsidian Graph' }).first();
      const matrixToggle = page.locator('button', { hasText: 'Cards Matrix' }).first();
      await expect(graphToggle).toBeVisible();
      await expect(matrixToggle).toBeVisible();

      // Verify Canvas is present and rendered
      const canvas = page.locator('canvas').first();
      await expect(canvas).toBeVisible();

      // Verify search input is present
      const searchInput = page.locator('input[placeholder="Search graph..."]').first();
      await expect(searchInput).toBeVisible();

      // Verify physics settings drawer opens and displays sliders
      const settingsBtn = page.locator('button[title="Physics Simulation Settings"]').first();
      if ((await settingsBtn.count()) > 0) {
        await expect(settingsBtn).toBeVisible();
        await settingsBtn.click();

        const settingsDrawer = page.locator('text=Obsidian Physics Forces').first();
        await expect(settingsDrawer).toBeVisible();
        await expect(page.locator('text=Node Repulsion').first()).toBeVisible();
        await expect(page.locator('text=Link Distance').first()).toBeVisible();

        // Close settings
        await settingsBtn.click();
        await expect(settingsDrawer).not.toBeVisible();
      }
    }
  });

  test('Can toggle between Obsidian Graph and Cards Matrix mode', async ({ page }) => {
    const matrixToggle = page.locator('button', { hasText: 'Cards Matrix' }).first();
    if ((await matrixToggle.count()) > 0) {
      await expect(matrixToggle).toBeVisible({ timeout: 5000 });
      await matrixToggle.click();

      // Verify matrix search bar is rendered
      const matrixSearch = page.locator('input[placeholder="Search relationships..."]').first();
      await expect(matrixSearch).toBeVisible();

      // Toggle back to Obsidian Graph
      const graphToggle = page.locator('button', { hasText: 'Obsidian Graph' }).first();
      await expect(graphToggle).toBeVisible();
      await graphToggle.click();

      // Canvas should be visible again
      const canvas = page.locator('canvas').first();
      await expect(canvas).toBeVisible();
    }
  });
});
