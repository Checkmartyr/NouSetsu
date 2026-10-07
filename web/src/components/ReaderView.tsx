import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  BookOpen,
  Eye,
  Sun,
  Moon,
  Coffee,
  ArrowLeft,
  Bookmark,
  BookMarked,
  Check,
  RotateCcw
} from 'lucide-react';
import { ChapterItem, ChapterContent } from '../types/dashboard';
import { fetchChapters, fetchChapterContent } from '../services/dashboardApi';
import {
  getReadingBookmark,
  saveReadingBookmark,
  getReaderPreferences,
  saveReaderPreferences,
  ReadingBookmark,
  ReaderTheme,
  FontSize,
} from '../utils/readerStorage';

interface ReaderViewProps {
  activeProjectPath: string | null;
  initialChapterNum?: number | null;
  initialFolder?: string | null;
  onBackToStudio: () => void;
}

export const ReaderView: React.FC<ReaderViewProps> = ({
  activeProjectPath,
  initialChapterNum,
  initialFolder,
  onBackToStudio,
}) => {
  const [chapters, setChapters] = useState<ChapterItem[]>([]);
  const [currentChapterNum, setCurrentChapterNum] = useState<number>(initialChapterNum || 1);
  const [currentFolder, setCurrentFolder] = useState<string | null>(initialFolder || null);
  const [content, setContent] = useState<ChapterContent | null>(null);
  const [loading, setLoading] = useState(false);

  // Persistent Reader Customization & Bookmark State
  const initialPrefs = getReaderPreferences();
  const [theme, setTheme] = useState<ReaderTheme>(initialPrefs.theme);
  const [fontSize, setFontSize] = useState<FontSize>(initialPrefs.fontSize);
  const [autoSave, setAutoSave] = useState<boolean>(initialPrefs.autoSave);
  const [showOriginalPeek, setShowOriginalPeek] = useState(false);
  const [savedBookmark, setSavedBookmark] = useState<ReadingBookmark | null>(() =>
    getReadingBookmark(activeProjectPath)
  );
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const readingBodyRef = useRef<HTMLDivElement>(null);
  const toastTimeoutRef = useRef<number | null>(null);

  const triggerToast = useCallback((msg: string) => {
    if (toastTimeoutRef.current) {
      window.clearTimeout(toastTimeoutRef.current);
    }
    setToastMessage(msg);
    toastTimeoutRef.current = window.setTimeout(() => {
      setToastMessage(null);
    }, 2500);
  }, []);

  // Sync savedBookmark whenever activeProjectPath changes
  useEffect(() => {
    if (!activeProjectPath) return;
    const bm = getReadingBookmark(activeProjectPath);
    setSavedBookmark(bm);

    fetchChapters(activeProjectPath).then((list) => {
      setChapters(list);
      if (list.length > 0) {
        if (
          !initialChapterNum ||
          !list.some(
            (c) =>
              c.chapter_num === currentChapterNum &&
              (initialFolder ? c.folder === initialFolder : true)
          )
        ) {
          // If a saved bookmark exists for this project, prioritize it!
          const bookmarkTarget = bm
            ? list.find(
                (c) =>
                  c.chapter_num === bm.chapter_num &&
                  (bm.folder ? c.folder === bm.folder : true)
              )
            : null;
          const matching = initialFolder
            ? list.find((c) => c.folder === initialFolder && (c.is_completed || c.translated_exists))
            : null;
          const firstCompleted = matching || list.find((c) => c.is_completed || c.translated_exists);
          const target =
            bookmarkTarget ||
            firstCompleted ||
            (initialFolder ? list.find((c) => c.folder === initialFolder) : null) ||
            list[0];
          setCurrentChapterNum(target.chapter_num);
          setCurrentFolder(target.folder || null);
        }
      }
    });
  }, [activeProjectPath, initialChapterNum, initialFolder]);

  // Fetch chapter content
  useEffect(() => {
    if (!activeProjectPath || !currentChapterNum) return;
    setLoading(true);
    const curChap =
      chapters.find(
        (c) =>
          c.chapter_num === currentChapterNum &&
          (currentFolder ? c.folder === currentFolder : true)
      ) || chapters.find((c) => c.chapter_num === currentChapterNum);

    fetchChapterContent(currentChapterNum, activeProjectPath, curChap?.folder || undefined).then(
      (res) => {
        setContent(res);
        setLoading(false);
      }
    );
  }, [currentChapterNum, currentFolder, activeProjectPath, chapters]);

  // Auto-save reading chapter when reading content is loaded
  useEffect(() => {
    if (!activeProjectPath || !currentChapterNum || !autoSave || loading) return;
    const curChap =
      chapters.find(
        (c) =>
          c.chapter_num === currentChapterNum &&
          (currentFolder ? c.folder === currentFolder : true)
      ) || chapters.find((c) => c.chapter_num === currentChapterNum);

    const newBm: ReadingBookmark = {
      chapter_num: currentChapterNum,
      folder: currentFolder,
      title: curChap?.title,
      timestamp: Date.now(),
    };
    saveReadingBookmark(activeProjectPath, newBm);
    setSavedBookmark(newBm);
  }, [activeProjectPath, currentChapterNum, currentFolder, autoSave, loading, chapters]);

  const currentIndex = chapters.findIndex(
    (c) =>
      c.chapter_num === currentChapterNum &&
      (currentFolder ? c.folder === currentFolder : true)
  );
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex >= 0 && currentIndex < chapters.length - 1;

  const handlePrev = () => {
    if (hasPrev) {
      const prevCh = chapters[currentIndex - 1];
      setCurrentChapterNum(prevCh.chapter_num);
      setCurrentFolder(prevCh.folder || null);
    }
  };

  const handleNext = () => {
    if (hasNext) {
      const nextCh = chapters[currentIndex + 1];
      setCurrentChapterNum(nextCh.chapter_num);
      setCurrentFolder(nextCh.folder || null);
    }
  };

  const isCurrentBookmarked = Boolean(
    savedBookmark &&
      savedBookmark.chapter_num === currentChapterNum &&
      (savedBookmark.folder || null) === (currentFolder || null)
  );

  const handleToggleBookmark = () => {
    if (!activeProjectPath) return;
    const curChap =
      chapters.find(
        (c) =>
          c.chapter_num === currentChapterNum &&
          (currentFolder ? c.folder === currentFolder : true)
      ) || chapters.find((c) => c.chapter_num === currentChapterNum);

    const newBm: ReadingBookmark = {
      chapter_num: currentChapterNum,
      folder: currentFolder,
      title: curChap?.title,
      timestamp: Date.now(),
    };
    saveReadingBookmark(activeProjectPath, newBm);
    setSavedBookmark(newBm);
    triggerToast(`Saved Chapter ${currentChapterNum} as reading bookmark! (=^･ω･^=)★`);
  };

  const handleResumeBookmark = () => {
    if (!savedBookmark) return;
    setCurrentChapterNum(savedBookmark.chapter_num);
    setCurrentFolder(savedBookmark.folder || null);
    triggerToast(`Resumed Chapter ${savedBookmark.chapter_num}`);
  };

  const handleToggleAutoSave = () => {
    const nextVal = !autoSave;
    setAutoSave(nextVal);
    saveReaderPreferences({ autoSave: nextVal });
    triggerToast(nextVal ? 'Auto-save reading chapter: ON' : 'Auto-save reading chapter: OFF');
  };

  const handleSetTheme = (newTheme: ReaderTheme) => {
    setTheme(newTheme);
    saveReaderPreferences({ theme: newTheme });
  };

  const handleSetFontSize = (newSize: FontSize) => {
    setFontSize(newSize);
    saveReaderPreferences({ fontSize: newSize });
  };

  // Restore scroll position when opening a bookmarked chapter
  useEffect(() => {
    if (!loading && readingBodyRef.current && savedBookmark?.scroll_ratio && isCurrentBookmarked) {
      const el = readingBodyRef.current;
      const maxScroll = el.scrollHeight - el.clientHeight;
      if (maxScroll > 0) {
        el.scrollTop = Math.round(maxScroll * savedBookmark.scroll_ratio);
      }
    }
  }, [loading, isCurrentBookmarked]);

  const handleScroll = useCallback(() => {
    if (!readingBodyRef.current || !activeProjectPath || !isCurrentBookmarked) return;
    const el = readingBodyRef.current;
    const maxScroll = el.scrollHeight - el.clientHeight;
    if (maxScroll <= 0) return;
    const ratio = Math.min(1, Math.max(0, el.scrollTop / maxScroll));
    saveReadingBookmark(activeProjectPath, {
      chapter_num: currentChapterNum,
      folder: currentFolder,
      scroll_ratio: Number(ratio.toFixed(3)),
    });
  }, [activeProjectPath, currentChapterNum, currentFolder, isCurrentBookmarked]);

  // Theme styling configurations
  const themeClasses: Record<ReaderTheme, { bg: string; text: string; subtext: string; border: string; header: string }> = {
    dark: {
      bg: 'bg-[#2b2622]',
      text: 'text-[#dad2c1]',
      subtext: 'text-[#aea69c]',
      border: 'border-[#3f3a36]',
      header: 'bg-[#2b2622] border-b border-[#3f3a36]',
    },
    sepia: {
      bg: 'bg-[#f4ecd8]',
      text: 'text-[#433422]',
      subtext: 'text-[#7d6b53]',
      border: 'border-[#dfd3bc]',
      header: 'bg-[#ebe1c7] border-[#dfd3bc]',
    },
    light: {
      bg: 'bg-[#fafafa]',
      text: 'text-neutral-900',
      subtext: 'text-neutral-500',
      border: 'border-neutral-200',
      header: 'bg-white border-neutral-200',
    },
  };

  const fontClasses: Record<FontSize, string> = {
    sm: 'text-sm leading-relaxed',
    base: 'text-base leading-relaxed',
    lg: 'text-lg leading-loose',
    xl: 'text-xl leading-loose',
  };

  const curTheme = themeClasses[theme];

  return (
    <div className={`flex flex-col h-full overflow-hidden transition-colors ${curTheme.bg} ${curTheme.text}`}>
      {/* Top Header Controls */}
      <div className={`px-3 sm:px-6 py-2 sm:py-2.5 border-b flex items-center justify-between gap-2 sm:gap-4 shrink-0 overflow-x-auto ${curTheme.header}`} style={{ scrollbarWidth: 'none' }}>
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <button
            onClick={onBackToStudio}
            className={`btn-secondary text-xs px-2.5 py-1 flex items-center gap-1.5`}
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Studio</span>
          </button>

          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-[#aea69c]" />
            <select
              value={`${currentFolder || ''}::${currentChapterNum}`}
              onChange={(e) => {
                const val = e.target.value;
                const [f, numStr] = val.split('::');
                setCurrentFolder(f || null);
                setCurrentChapterNum(Number(numStr));
              }}
              aria-label="Select chapter to read"
              className={`text-xs font-medium rounded-[3px] px-2.5 py-1 border cursor-pointer focus:outline-none ${curTheme.bg} ${curTheme.border} ${curTheme.text}`}
            >
              {chapters.map((c) => {
                const isBookmarked =
                  savedBookmark &&
                  savedBookmark.chapter_num === c.chapter_num &&
                  (savedBookmark.folder || null) === (c.folder || null);
                return (
                  <option key={`${c.folder || ''}::${c.chapter_num}`} value={`${c.folder || ''}::${c.chapter_num}`}>
                    {c.folder ? `${c.folder} > ` : ''}
                    {c.output_file_name || (c.file_name ? c.file_name.replace(/\.[^/.]+$/, '.md') : `${c.title}.md`)}
                    {c.is_completed ? ' ✓' : ''}
                    {isBookmarked ? ' 🔖 (Saved)' : ''}
                  </option>
                );
              })}
            </select>
          </div>

          {/* Bookmark / Save Reading Chapter Button */}
          <button
            type="button"
            onClick={handleToggleBookmark}
            aria-label={isCurrentBookmarked ? 'Bookmarked chapter' : 'Save current reading chapter'}
            title={
              isCurrentBookmarked
                ? 'Current chapter is saved as your reading bookmark (=^･ω･^=)'
                : 'Save this chapter as your reading bookmark'
            }
            className={`text-xs px-2.5 py-1 rounded-[3px] border flex items-center gap-1.5 cursor-pointer transition-colors ${
              isCurrentBookmarked
                ? 'bg-amber-950/40 text-amber-300 border-amber-600/60 font-medium'
                : `${curTheme.border} ${curTheme.text} hover:bg-neutral-500/10`
            }`}
          >
            {isCurrentBookmarked ? (
              <BookMarked className="w-3.5 h-3.5 text-amber-400 fill-amber-400/30" />
            ) : (
              <Bookmark className="w-3.5 h-3.5 text-[#aea69c]" />
            )}
            <span>{isCurrentBookmarked ? 'Bookmarked' : 'Save Chapter'}</span>
            {isCurrentBookmarked && <Check className="w-3 h-3 text-emerald-400" />}
          </button>

          {/* Quick Resume Button if viewing a different chapter */}
          {savedBookmark && !isCurrentBookmarked && (
            <button
              type="button"
              onClick={handleResumeBookmark}
              title={`Resume reading from bookmarked Chapter ${savedBookmark.chapter_num}`}
              className="text-xs px-2 py-1 rounded-[3px] border border-amber-800/50 bg-amber-950/30 text-amber-300 flex items-center gap-1 cursor-pointer hover:bg-amber-900/40 transition-colors"
            >
              <RotateCcw className="w-3 h-3 text-amber-400" />
              <span>Resume Ch.{savedBookmark.chapter_num}</span>
            </button>
          )}
        </div>

        {/* Center: Chapter Nav */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handlePrev}
            disabled={!hasPrev}
            aria-label="Previous Chapter"
            className={`p-1 rounded-[3px] border cursor-pointer disabled:opacity-30 transition-opacity ${curTheme.border}`}
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>
          <span className={`text-xs font-mono ${curTheme.subtext}`}>
            {currentIndex >= 0 ? `${currentIndex + 1} / ${chapters.length}` : ''}
          </span>
          <button
            onClick={handleNext}
            disabled={!hasNext}
            aria-label="Next Chapter"
            className={`p-1 rounded-[3px] border cursor-pointer disabled:opacity-30 transition-opacity ${curTheme.border}`}
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Right: Typography & Theme Controls */}
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          {/* Auto-Save Toggle */}
          <button
            type="button"
            onClick={handleToggleAutoSave}
            title={autoSave ? 'Auto-save reading position is ON (click to disable)' : 'Auto-save reading position is OFF (click to enable)'}
            className={`px-2 py-1 rounded-[3px] border text-[11px] font-mono cursor-pointer transition-colors ${
              autoSave
                ? 'border-emerald-800/40 bg-emerald-950/20 text-emerald-400'
                : `${curTheme.border} ${curTheme.subtext}`
            }`}
          >
            Auto-save: {autoSave ? 'ON' : 'OFF'}
          </button>

          {/* Theme Switcher */}
          <div className={`flex items-center rounded-[3px] border p-0.5 ${curTheme.border}`}>
            <button
              onClick={() => handleSetTheme('dark')}
              title="Dark Warm Canvas Theme"
              className={`p-1 rounded-[2px] cursor-pointer ${theme === 'dark' ? 'bg-[#383330] text-[#f7f5f0]' : curTheme.subtext}`}
            >
              <Moon className="w-3 h-3" />
            </button>
            <button
              onClick={() => handleSetTheme('sepia')}
              title="Sepia Theme"
              className={`p-1 rounded-[2px] cursor-pointer ${theme === 'sepia' ? 'bg-[#dfd3bc] text-[#433422]' : curTheme.subtext}`}
            >
              <Coffee className="w-3 h-3" />
            </button>
            <button
              onClick={() => handleSetTheme('light')}
              title="Light Theme"
              className={`p-1 rounded-[2px] cursor-pointer ${theme === 'light' ? 'bg-neutral-200 text-neutral-900' : curTheme.subtext}`}
            >
              <Sun className="w-3 h-3" />
            </button>
          </div>

          {/* Font Size */}
          <div className={`flex items-center rounded-[3px] border p-0.5 text-xs font-mono ${curTheme.border}`}>
            {(['sm', 'base', 'lg', 'xl'] as FontSize[]).map((sz) => (
              <button
                key={sz}
                onClick={() => handleSetFontSize(sz)}
                className={`px-1.5 py-0.5 rounded-[2px] uppercase cursor-pointer text-[10px] ${
                  fontSize === sz
                    ? theme === 'dark'
                      ? 'bg-[#383330] text-[#f7f5f0] font-semibold'
                      : 'bg-neutral-300 text-black font-semibold'
                    : curTheme.subtext
                }`}
              >
                {sz}
              </button>
            ))}
          </div>

          {/* Peek Original Source Toggle */}
          <button
            onClick={() => setShowOriginalPeek(!showOriginalPeek)}
            title="Toggle original source text split drawer"
            className={`flex items-center gap-1.5 px-2 py-1 rounded-[3px] border text-xs font-medium cursor-pointer transition-colors ${
              showOriginalPeek
                ? 'bg-[#383330] text-[#f7f5f0] border-[#544d47]'
                : `${curTheme.border} ${curTheme.subtext}`
            }`}
          >
            <Eye className="w-3 h-3" />
            <span>Raw</span>
          </button>
        </div>
      </div>

      {/* Reader Body */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Main Focus Reading Column */}
        <div ref={readingBodyRef} onScroll={handleScroll} className="flex-1 overflow-y-auto px-6 py-10 flex justify-center">
          <div className="max-w-3xl w-full">
            {loading ? (
              <div className="text-center py-20 opacity-50">Loading translation...</div>
            ) : (content?.has_translated || Boolean(content?.translated_text?.trim())) ? (
              <article className="prose max-w-none">
                <div className={`font-serif whitespace-pre-wrap ${fontClasses[fontSize]}`}>
                  {content?.translated_text}
                </div>
              </article>
            ) : (
              <div className="text-center py-20 space-y-4">
                <div className="text-base font-normal text-[#aea69c]">
                  Chapter {currentChapterNum} has not been translated yet.
                </div>
                <button
                  onClick={onBackToStudio}
                  className="btn-primary text-xs"
                >
                  Return to Studio to Translate
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Optional Collapsible Original Source Peek Drawer */}
        {showOriginalPeek && (
          <div className={`w-96 border-l p-6 overflow-y-auto shrink-0 ${curTheme.border} bg-black/20`}>
            <div className={`text-xs font-semibold uppercase tracking-wider mb-4 ${curTheme.subtext}`}>
              Original Source Text (Ch.{currentChapterNum})
            </div>
            <div className="font-mono text-xs leading-relaxed whitespace-pre-wrap opacity-80 select-text">
              {content?.source_text || 'No source text available.'}
            </div>
          </div>
        )}
      </div>

      {/* Reader Footer Navigation */}
      <div className={`px-6 py-3 border-t flex items-center justify-between text-xs ${curTheme.header} ${curTheme.subtext}`}>
        <div>
          {content?.translated_text ? (
            <span>{content.translated_text.split(/\s+/).length} words</span>
          ) : null}
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={handlePrev}
            disabled={!hasPrev}
            className="hover:underline cursor-pointer disabled:opacity-30"
          >
            &larr; Previous Chapter
          </button>
          <span>&bull;</span>
          <button
            onClick={handleNext}
            disabled={!hasNext}
            className="hover:underline cursor-pointer disabled:opacity-30"
          >
            Next Chapter &rarr;
          </button>
        </div>
      </div>

      {/* Floating Bookmark / Action Toast */}
      {toastMessage && (
        <div className="fixed bottom-14 right-6 z-50 bg-[#383330] border border-amber-600/70 text-[#f7f5f0] text-xs px-3.5 py-2 rounded-[4px] shadow-2xl flex items-center gap-2 pointer-events-none transition-all duration-200">
          <BookMarked className="w-4 h-4 text-amber-400 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
};
