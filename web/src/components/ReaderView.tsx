import React, { useState, useEffect } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  BookOpen,
  Eye,
  Sun,
  Moon,
  Coffee,
  ArrowLeft
} from 'lucide-react';
import { ChapterItem, ChapterContent } from '../types/dashboard';
import { fetchChapters, fetchChapterContent } from '../services/dashboardApi';

interface ReaderViewProps {
  activeProjectPath: string | null;
  initialChapterNum?: number | null;
  onBackToStudio: () => void;
}

type ReaderTheme = 'dark' | 'sepia' | 'light';
type FontSize = 'sm' | 'base' | 'lg' | 'xl';

export const ReaderView: React.FC<ReaderViewProps> = ({
  activeProjectPath,
  initialChapterNum,
  onBackToStudio,
}) => {
  const [chapters, setChapters] = useState<ChapterItem[]>([]);
  const [currentChapterNum, setCurrentChapterNum] = useState<number>(initialChapterNum || 1);
  const [content, setContent] = useState<ChapterContent | null>(null);
  const [loading, setLoading] = useState(false);

  // Customization
  const [theme, setTheme] = useState<ReaderTheme>('dark');
  const [fontSize, setFontSize] = useState<FontSize>('lg');
  const [showOriginalPeek, setShowOriginalPeek] = useState(false);

  useEffect(() => {
    if (!activeProjectPath) return;
    fetchChapters(activeProjectPath).then((list) => {
      setChapters(list);
      if (list.length > 0) {
        if (!initialChapterNum || !list.some((c) => c.chapter_num === currentChapterNum)) {
          // Default to first completed / translated chapter or first chapter
          const firstCompleted = list.find((c) => c.is_completed || c.translated_exists);
          setCurrentChapterNum(firstCompleted ? firstCompleted.chapter_num : list[0].chapter_num);
        }
      }
    });
  }, [activeProjectPath, initialChapterNum]);

  useEffect(() => {
    if (!activeProjectPath || !currentChapterNum) return;
    setLoading(true);
    const curChap = chapters.find((c) => c.chapter_num === currentChapterNum);
    fetchChapterContent(currentChapterNum, activeProjectPath, curChap?.folder || undefined).then((res) => {
      setContent(res);
      setLoading(false);
    });
  }, [currentChapterNum, activeProjectPath, chapters]);

  const currentIndex = chapters.findIndex((c) => c.chapter_num === currentChapterNum);
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex >= 0 && currentIndex < chapters.length - 1;

  const handlePrev = () => {
    if (hasPrev) setCurrentChapterNum(chapters[currentIndex - 1].chapter_num);
  };

  const handleNext = () => {
    if (hasNext) setCurrentChapterNum(chapters[currentIndex + 1].chapter_num);
  };

  // Theme styling configurations
  const themeClasses: Record<ReaderTheme, { bg: string; text: string; subtext: string; border: string; header: string }> = {
    dark: {
      bg: 'bg-slate-950',
      text: 'text-slate-100',
      subtext: 'text-slate-400',
      border: 'border-slate-800',
      header: 'bg-slate-900/80 border-slate-800',
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
      <div className={`px-6 py-3 border-b flex items-center justify-between gap-4 backdrop-blur shrink-0 ${curTheme.header}`}>
        <div className="flex items-center gap-3">
          <button
            onClick={onBackToStudio}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border cursor-pointer transition-colors ${curTheme.border} ${curTheme.subtext} hover:${curTheme.text}`}
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Studio
          </button>

          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-indigo-400" />
            <select
              value={currentChapterNum}
              onChange={(e) => setCurrentChapterNum(Number(e.target.value))}
              aria-label="Select chapter to read"
              className={`text-sm font-semibold rounded-lg px-2.5 py-1 border cursor-pointer focus:outline-none ${curTheme.bg} ${curTheme.border} ${curTheme.text}`}
            >
              {chapters.map((c) => (
                <option key={c.chapter_num} value={c.chapter_num}>
                  Chapter {c.chapter_num.toString().padStart(3, '0')} - {c.title} {c.is_completed ? '✓' : ''}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Center: Chapter Nav */}
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrev}
            disabled={!hasPrev}
            aria-label="Previous Chapter"
            className={`p-1.5 rounded-lg border cursor-pointer disabled:opacity-30 transition-opacity ${curTheme.border}`}
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className={`text-xs font-medium ${curTheme.subtext}`}>
            {currentIndex >= 0 ? `${currentIndex + 1} of ${chapters.length}` : ''}
          </span>
          <button
            onClick={handleNext}
            disabled={!hasNext}
            aria-label="Next Chapter"
            className={`p-1.5 rounded-lg border cursor-pointer disabled:opacity-30 transition-opacity ${curTheme.border}`}
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Right: Typography & Theme Controls */}
        <div className="flex items-center gap-3">
          {/* Theme Switcher */}
          <div className={`flex items-center rounded-lg border p-0.5 ${curTheme.border}`}>
            <button
              onClick={() => setTheme('dark')}
              title="Dark Theme"
              className={`p-1.5 rounded cursor-pointer ${theme === 'dark' ? 'bg-slate-800 text-indigo-400' : 'text-slate-400'}`}
            >
              <Moon className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setTheme('sepia')}
              title="Sepia Theme"
              className={`p-1.5 rounded cursor-pointer ${theme === 'sepia' ? 'bg-[#dfd3bc] text-[#433422]' : 'text-slate-400'}`}
            >
              <Coffee className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setTheme('light')}
              title="Light Theme"
              className={`p-1.5 rounded cursor-pointer ${theme === 'light' ? 'bg-neutral-200 text-neutral-900' : 'text-slate-400'}`}
            >
              <Sun className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Font Size */}
          <div className={`flex items-center rounded-lg border p-0.5 text-xs font-bold ${curTheme.border}`}>
            {(['sm', 'base', 'lg', 'xl'] as FontSize[]).map((sz) => (
              <button
                key={sz}
                onClick={() => setFontSize(sz)}
                className={`px-2 py-0.5 rounded uppercase cursor-pointer ${
                  fontSize === sz
                    ? theme === 'dark'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-neutral-300 text-black'
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
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium cursor-pointer transition-colors ${
              showOriginalPeek
                ? 'bg-indigo-600/20 text-indigo-400 border-indigo-500/40'
                : `${curTheme.border} ${curTheme.subtext}`
            }`}
          >
            <Eye className="w-3.5 h-3.5" />
            <span>Raw</span>
          </button>
        </div>
      </div>

      {/* Reader Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Main Focus Reading Column */}
        <div className="flex-1 overflow-y-auto px-6 py-10 flex justify-center">
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
                <div className="text-lg font-medium opacity-60">
                  Chapter {currentChapterNum} has not been translated yet.
                </div>
                <button
                  onClick={onBackToStudio}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium"
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
    </div>
  );
};
