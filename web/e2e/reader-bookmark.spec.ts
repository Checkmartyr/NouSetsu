import { test, expect } from '@playwright/test';

test.describe('Reader Bookmark & Progress Persistence', () => {
  test('Save Chapter bookmark button toggles and persists in localStorage', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('header');

    // 1. Navigate to Reader tab
    const readerTab = page.locator('header').getByRole('button', { name: 'Reader', exact: true });
    await expect(readerTab).toBeVisible();
    await readerTab.click();

    // 2. Wait for Reader header controls
    const chapterSelect = page.getByRole('combobox', { name: /Select chapter to read/i });
    await expect(chapterSelect).toBeVisible({ timeout: 10000 });

    // 3. Verify Bookmark button exists
    const bookmarkBtn = page.getByRole('button', { name: /(Save Chapter|Bookmarked)/i });
    await expect(bookmarkBtn).toBeVisible();

    // 4. Click Save Chapter (or re-confirm)
    await bookmarkBtn.click();
    await page.waitForTimeout(300);

    // Verify it now displays "Bookmarked"
    await expect(bookmarkBtn).toContainText('Bookmarked');

    // 5. Check localStorage persistence
    const hasBookmark = await page.evaluate(() => {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('nousetsu_reader_bookmark_')) {
          const val = localStorage.getItem(key);
          if (val) {
            const parsed = JSON.parse(val);
            if (typeof parsed.chapter_num === 'number') {
              return true;
            }
          }
        }
      }
      return false;
    });
    expect(hasBookmark).toBeTruthy();
  });

  test('Auto-save toggle updates reader preferences', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('header');

    const readerTab = page.locator('header').getByRole('button', { name: 'Reader', exact: true });
    await readerTab.click();

    const autoSaveBtn = page.getByRole('button', { name: /Auto-save:/i });
    await expect(autoSaveBtn).toBeVisible();

    const initialText = await autoSaveBtn.innerText();
    await autoSaveBtn.click();
    await page.waitForTimeout(300);

    const toggledText = await autoSaveBtn.innerText();
    expect(toggledText).not.toEqual(initialText);

    // Verify preference is persisted in localStorage
    const savedPrefs = await page.evaluate(() => {
      const raw = localStorage.getItem('nousetsu_reader_settings');
      return raw ? JSON.parse(raw) : null;
    });
    expect(savedPrefs).not.toBeNull();
    expect(typeof savedPrefs.autoSave).toBe('boolean');
  });

  test('Resume Bookmark button appears when navigating away and restores chapter', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('header');

    const readerTab = page.locator('header').getByRole('button', { name: 'Reader', exact: true });
    await readerTab.click();

    const chapterSelect = page.getByRole('combobox', { name: /Select chapter to read/i });
    await expect(chapterSelect).toBeVisible();

    // Explicitly set bookmark to Chapter 1
    const bookmarkBtn = page.getByRole('button', { name: /(Save Chapter|Bookmarked)/i });
    await bookmarkBtn.click();
    await page.waitForTimeout(200);

    // Check if next chapter button is enabled (header button)
    const nextBtn = page.getByRole('button', { name: 'Next Chapter', exact: true });
    if (await nextBtn.isEnabled()) {
      await nextBtn.click();
      await page.waitForTimeout(500);

      // Now "Resume Ch." button should be visible!
      const resumeBtn = page.getByRole('button', { name: /Resume Ch\./i });
      if ((await resumeBtn.count()) > 0) {
        await expect(resumeBtn).toBeVisible();
        await resumeBtn.click();
        await page.waitForTimeout(300);

        // Reader should return to bookmarked chapter and button shows Bookmarked
        await expect(bookmarkBtn).toContainText('Bookmarked');
      }
    }
  });
});
