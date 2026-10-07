/**
 * readerStorage.ts
 * Type-safe browser localStorage utility for persisting reading bookmarks,
 * scroll progress, and reader display preferences scoped per novel project.
 */

export interface ReadingBookmark {
  chapter_num: number;
  folder: string | null;
  title?: string;
  timestamp: number;
  scroll_ratio?: number;
}

export type ReaderTheme = 'dark' | 'sepia' | 'light';
export type FontSize = 'sm' | 'base' | 'lg' | 'xl';

export interface ReaderPreferences {
  theme: ReaderTheme;
  fontSize: FontSize;
  autoSave: boolean;
}

const DEFAULT_PREFERENCES: ReaderPreferences = {
  theme: 'dark',
  fontSize: 'lg',
  autoSave: true,
};

const SETTINGS_KEY = 'nousetsu_reader_settings';

/**
 * Normalizes project path to create a deterministic storage key.
 */
function getBookmarkKey(projectPath: string | null): string {
  if (!projectPath || !projectPath.trim()) {
    return 'nousetsu_reader_bookmark_global';
  }
  const cleanPath = projectPath.trim().replace(/\\/g, '/').toLowerCase();
  return `nousetsu_reader_bookmark_${encodeURIComponent(cleanPath)}`;
}

/**
 * Retrieves the saved reading bookmark for the given novel project.
 */
export function getReadingBookmark(projectPath: string | null): ReadingBookmark | null {
  if (typeof window === 'undefined' || !window.localStorage) {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(getBookmarkKey(projectPath));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ReadingBookmark;
    if (typeof parsed?.chapter_num === 'number') {
      return parsed;
    }
  } catch (err) {
    console.warn('[readerStorage] Failed to read bookmark from localStorage:', err);
  }
  return null;
}

/**
 * Saves a reading bookmark for the given novel project.
 */
export function saveReadingBookmark(
  projectPath: string | null,
  bookmark: Omit<ReadingBookmark, 'timestamp'> & { timestamp?: number }
): void {
  if (typeof window === 'undefined' || !window.localStorage) {
    return;
  }
  try {
    const payload: ReadingBookmark = {
      ...bookmark,
      timestamp: bookmark.timestamp || Date.now(),
    };
    window.localStorage.setItem(getBookmarkKey(projectPath), JSON.stringify(payload));
  } catch (err) {
    console.warn('[readerStorage] Failed to save bookmark to localStorage:', err);
  }
}

/**
 * Clears the reading bookmark for the given novel project.
 */
export function clearReadingBookmark(projectPath: string | null): void {
  if (typeof window === 'undefined' || !window.localStorage) {
    return;
  }
  try {
    window.localStorage.removeItem(getBookmarkKey(projectPath));
  } catch (err) {
    console.warn('[readerStorage] Failed to clear bookmark from localStorage:', err);
  }
}

/**
 * Retrieves global reader display preferences (theme, font size, autoSave).
 */
export function getReaderPreferences(): ReaderPreferences {
  if (typeof window === 'undefined' || !window.localStorage) {
    return { ...DEFAULT_PREFERENCES };
  }
  try {
    const raw = window.localStorage.getItem(SETTINGS_KEY);
    if (!raw) return { ...DEFAULT_PREFERENCES };
    const parsed = JSON.parse(raw);
    return {
      theme: ['dark', 'sepia', 'light'].includes(parsed.theme) ? parsed.theme : DEFAULT_PREFERENCES.theme,
      fontSize: ['sm', 'base', 'lg', 'xl'].includes(parsed.fontSize) ? parsed.fontSize : DEFAULT_PREFERENCES.fontSize,
      autoSave: typeof parsed.autoSave === 'boolean' ? parsed.autoSave : DEFAULT_PREFERENCES.autoSave,
    };
  } catch (err) {
    console.warn('[readerStorage] Failed to read reader preferences:', err);
    return { ...DEFAULT_PREFERENCES };
  }
}

/**
 * Updates global reader display preferences.
 */
export function saveReaderPreferences(prefs: Partial<ReaderPreferences>): void {
  if (typeof window === 'undefined' || !window.localStorage) {
    return;
  }
  try {
    const current = getReaderPreferences();
    const updated = { ...current, ...prefs };
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(updated));
  } catch (err) {
    console.warn('[readerStorage] Failed to save reader preferences:', err);
  }
}
