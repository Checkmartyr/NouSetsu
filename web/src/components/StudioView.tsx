import React, { useState, useEffect, useRef } from 'react';
import {
  Play,
  Square,
  RefreshCw,
  FileText,
  Search,
  Clock,
  Terminal,
  ChevronDown,
  ChevronUp,
  Sparkles,
  BookOpen
} from 'lucide-react';
import { ChapterItem, ChapterContent, TranslationStatus } from '../types/dashboard';
import {
  fetchChapters,
  fetchChapterContent,
  fetchTranslationStatus,
  startTranslation,
  stopTranslation
} from '../services/dashboardApi';

interface StudioViewProps {
  activeProjectPath: string | null;
  activeProjectTitle: string | null;
  onNavigateToReader: (chapterNum: number) => void;
  logs: string[];
}

export const StudioView: React.FC<StudioViewProps> = ({
  activeProjectPath,
  activeProjectTitle,
  onNavigateToReader,
  logs,
}) => {
  const [chapters, setChapters] = useState<ChapterItem[]>([]);
  const [selectedChapterNum, setSelectedChapterNum] = useState<number | null>(null);
  const [chapterContent, setChapterContent] = useState<ChapterContent | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [status, setStatus] = useState<TranslationStatus | null>(null);

  // Filters & Controls
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedFolder, setSelectedFolder] = useState<string>('all');
  const [isLogDrawerOpen, setIsLogDrawerOpen] = useState(false);
  const [isStarting, setIsStarting] = useState(false);

  // Translation Options Modal / Fields
  const [limitCount, setLimitCount] = useState<number | undefined>(undefined);
  const [forceRetranslate, setForceRetranslate] = useState(false);

  const logBottomRef = useRef<HTMLDivElement>(null);

  // Load chapters & translation status
  const refreshData = async () => {
    if (!activeProjectPath) return;
    const [chList, transStat] = await Promise.all([
      fetchChapters(activeProjectPath),
      fetchTranslationStatus(),
    ]);
    setChapters(chList);
    setStatus(transStat);

    if (chList.length > 0 && selectedChapterNum === null) {
      setSelectedChapterNum(chList[0].chapter_num);
    }
  };

  useEffect(() => {
    refreshData();
    const interval = setInterval(async () => {
      const s = await fetchTranslationStatus();
      setStatus(s);
    }, 2000);
    return () => clearInterval(interval);
  }, [activeProjectPath]);

  // Load selected chapter source & translation
  useEffect(() => {
    if (selectedChapterNum === null || !activeProjectPath) return;
    let active = true;
    setLoadingContent(true);
    fetchChapterContent(selectedChapterNum, activeProjectPath).then((content) => {
      if (active) {
        setChapterContent(content);
        setLoadingContent(false);
      }
    });
    return () => {
      active = false;
    };
  }, [selectedChapterNum, activeProjectPath]);

  // Scroll logs to bottom when updated
  useEffect(() => {
    if (isLogDrawerOpen && logBottomRef.current) {
      logBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, isLogDrawerOpen]);

  const handleStart = async (targetChapter?: number) => {
    if (!activeProjectPath) return;
    setIsStarting(true);
    try {
      await startTranslation({
        project_path: activeProjectPath,
        chapter_num: targetChapter,
        limit: limitCount,
        force_retranslate: forceRetranslate,
        folder: selectedFolder !== 'all' ? selectedFolder : undefined,
      });
      await refreshData();
    } catch (e: any) {
      alert(`Could not start translation: ${e.message}`);
    } finally {
      setIsStarting(false);
    }
  };

  const handleStop = async () => {
    try {
      await stopTranslation();
      await refreshData();
    } catch (e: any) {
      alert(`Could not stop translation: ${e.message}`);
    }
  };

  // Filter folders
  const folders = Array.from(new Set(chapters.map((c) => c.folder).filter(Boolean))) as string[];

  const filteredChapters = chapters.filter((c) => {
    const matchesSearch =
      c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.chapter_num.toString().includes(searchQuery);
    const matchesStatus =
      statusFilter === 'all'
        ? true
        : statusFilter === 'completed'
        ? c.is_completed
        : statusFilter === 'paused'
        ? c.status === 'PAUSED' || c.status === 'RESUME'
        : c.status === statusFilter.toUpperCase();
    const matchesFolder =
      selectedFolder === 'all' ? true : c.folder === selectedFolder;
    return matchesSearch && matchesStatus && matchesFolder;
  });

  const stages = [
    { key: 'EXTRACTION', label: '1. Extractor', agent: 'EntityExtractorAgent' },
    { key: 'DRAFTING', label: '2. Drafter', agent: 'ContextAwareDrafterAgent' },
    { key: 'CRITIQUE', label: '3. Critic', agent: 'CritiqueAgent' },
    { key: 'POLISHING', label: '4. Polisher', agent: 'PolishingAgent' },
    { key: 'CHRONICLING', label: '5. Chronicler', agent: 'ChroniclerAgent' },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden bg-slate-950 text-slate-100">
      {/* Top Banner: Translation Controls & Active Pipeline */}
      <div className="bg-slate-900/80 border-b border-slate-800/80 px-6 py-4 flex flex-wrap items-center justify-between gap-4">
        {/* Left: Project Title & Quick Stats */}
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold bg-gradient-to-r from-indigo-400 via-purple-300 to-pink-400 bg-clip-text text-transparent">
              {activeProjectTitle || 'Novel Studio'}
            </span>
            {status?.is_running ? (
              <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 animate-pulse">
                <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                RUNNING (Ch.{status.active_chapter ?? '?'})
              </span>
            ) : (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
                IDLE
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {chapters.length} total chapters &bull;{' '}
            {chapters.filter((c) => c.is_completed).length} translated &bull;{' '}
            {chapters.filter((c) => c.status === 'PAUSED' || c.status === 'RESUME').length} paused
          </p>
        </div>

        {/* Center: Realtime Pipeline Stages */}
        <div className="flex items-center gap-1.5 bg-slate-950/70 px-3 py-2 rounded-xl border border-slate-800 shadow-inner">
          {stages.map((st) => {
            const isActive =
              status?.is_running &&
              status.active_stage?.toUpperCase() === st.key;
            return (
              <div
                key={st.key}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/30 scale-105 ring-1 ring-indigo-400'
                    : 'bg-slate-900 text-slate-400 border border-slate-800/80'
                }`}
              >
                {isActive && <Sparkles className="w-3 h-3 animate-spin text-pink-300" />}
                <span>{st.label}</span>
              </div>
            );
          })}
        </div>

        {/* Right: Action Buttons */}
        <div className="flex items-center gap-2">
          {/* Translation Options: Limit & Force */}
          {!status?.is_running && (
            <div className="hidden sm:flex items-center gap-2 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800 text-xs">
              <label className="text-slate-400">Limit:</label>
              <input
                type="number"
                min={1}
                placeholder="All"
                value={limitCount ?? ''}
                onChange={(e) =>
                  setLimitCount(e.target.value ? parseInt(e.target.value, 10) : undefined)
                }
                className="w-12 bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-slate-200 text-xs focus:outline-none focus:border-indigo-500"
              />
              <label className="flex items-center gap-1 text-slate-400 cursor-pointer ml-1">
                <input
                  type="checkbox"
                  checked={forceRetranslate}
                  onChange={(e) => setForceRetranslate(e.target.checked)}
                  className="rounded accent-indigo-600 cursor-pointer"
                />
                <span>Force</span>
              </label>
            </div>
          )}

          {status?.is_running ? (
            <button
              onClick={handleStop}
              className="flex items-center gap-2 px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-sm font-semibold shadow-lg shadow-rose-600/20 transition-all cursor-pointer"
            >
              <Square className="w-4 h-4 fill-white" />
              Stop Translation
            </button>
          ) : (
            <button
              onClick={() => handleStart()}
              disabled={isStarting}
              className="flex items-center gap-2 px-5 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-lg text-sm font-semibold shadow-lg shadow-indigo-600/20 transition-all cursor-pointer disabled:opacity-50"
            >
              <Play className="w-4 h-4 fill-white" />
              {isStarting ? 'Starting...' : 'Translate Batch'}
            </button>
          )}

          <button
            onClick={refreshData}
            title="Refresh chapter list"
            className="p-2 text-slate-400 hover:text-slate-200 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg cursor-pointer transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Studio Grid: Left Sidebar (Chapters) & Right Viewer (Dual Text) */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Column: Chapter Queue & Filters */}
        <div className="w-96 border-r border-slate-800/80 bg-slate-900/40 flex flex-col shrink-0">
          {/* Filter Bar */}
          <div className="p-3 border-b border-slate-800/80 space-y-2">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
              <input
                type="text"
                placeholder="Search chapter..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="flex items-center gap-2">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
              >
                <option value="all">All Statuses</option>
                <option value="completed">Completed</option>
                <option value="paused">Paused / Resume</option>
                <option value="pending">Pending</option>
                <option value="failed">Failed</option>
              </select>

              {folders.length > 0 && (
                <select
                  value={selectedFolder}
                  onChange={(e) => setSelectedFolder(e.target.value)}
                  className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
                >
                  <option value="all">All Volumes</option>
                  {folders.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>

          {/* Chapter Task List */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-800/50">
            {filteredChapters.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-500">
                No chapters match the filter criteria.
              </div>
            ) : (
              filteredChapters.map((ch) => {
                const isSelected = ch.chapter_num === selectedChapterNum;
                const isRunningThis =
                  status?.is_running && status.active_chapter === ch.chapter_num;

                return (
                  <div
                    key={`${ch.folder || 'root'}_${ch.chapter_num}`}
                    onClick={() => setSelectedChapterNum(ch.chapter_num)}
                    className={`p-3 cursor-pointer transition-all flex items-start justify-between gap-2 select-none ${
                      isSelected
                        ? 'bg-indigo-950/40 border-l-4 border-indigo-500'
                        : 'hover:bg-slate-900/60 border-l-4 border-transparent'
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-slate-200 truncate">
                          Ch.{ch.chapter_num.toString().padStart(3, '0')} - {ch.title}
                        </span>
                        {ch.folder && (
                          <span className="text-[10px] px-1.5 py-0.2 bg-slate-800 text-slate-400 rounded">
                            {ch.folder}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-1.5 text-[11px] text-slate-400">
                        <span>{ch.raw_lines} lines</span>
                        {ch.translated_words > 0 && (
                          <span className="text-emerald-400 font-medium">
                            {ch.translated_words} words
                          </span>
                        )}
                        {ch.quality_audit?.fidelity_score && (
                          <span className="text-amber-400 font-medium">
                            ★ {ch.quality_audit.fidelity_score.toFixed(1)}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex flex-col items-end shrink-0 gap-1">
                      {isRunningThis ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 animate-pulse">
                          TRANSLATING
                        </span>
                      ) : ch.is_completed ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          DONE
                        </span>
                      ) : ch.status === 'PAUSED' || ch.status === 'RESUME' ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          PAUSED
                        </span>
                      ) : ch.status === 'FAILED' ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                          FAILED
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-500">
                          WAIT
                        </span>
                      )}

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStart(ch.chapter_num);
                        }}
                        title="Translate only this chapter"
                        className="opacity-0 group-hover:opacity-100 hover:opacity-100 text-[10px] text-indigo-400 hover:text-indigo-300 transition-opacity"
                      >
                        Run ▶
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Dual Source / Target Comparison Reader */}
        <div className="flex-1 flex flex-col overflow-hidden bg-slate-950">
          {/* Subheader */}
          <div className="px-6 py-2.5 border-b border-slate-800/80 flex items-center justify-between bg-slate-900/30">
            <div className="flex items-center gap-3">
              <FileText className="w-4 h-4 text-indigo-400" />
              <span className="text-sm font-semibold text-slate-200">
                Chapter {selectedChapterNum ?? '—'}:{' '}
                {chapterContent?.source_file ? chapterContent.source_file.split(/[\/\\]/).pop() : ''}
              </span>
            </div>

            <div className="flex items-center gap-3">
              {chapterContent?.has_translated && (
                <button
                  onClick={() => selectedChapterNum && onNavigateToReader(selectedChapterNum)}
                  className="flex items-center gap-1.5 px-3 py-1 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded-lg text-xs font-medium cursor-pointer transition-colors"
                >
                  <BookOpen className="w-3.5 h-3.5" />
                  Read in Reader Mode
                </button>
              )}
            </div>
          </div>

          {/* Dual Column Content Body */}
          {loadingContent ? (
            <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
              Loading chapter content...
            </div>
          ) : (
            <div className="flex-1 grid grid-cols-2 divide-x divide-slate-800/80 overflow-hidden">
              {/* Left: Original Source */}
              <div className="flex flex-col h-full overflow-hidden">
                <div className="px-4 py-2 bg-slate-900/60 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-800">
                  Raw Source Text
                </div>
                <div className="flex-1 p-6 overflow-y-auto font-mono text-sm leading-relaxed text-slate-300 whitespace-pre-wrap selection:bg-indigo-500/30">
                  {chapterContent?.source_text || (
                    <span className="text-slate-600 italic">No source file found.</span>
                  )}
                </div>
              </div>

              {/* Right: Translated Target */}
              <div className="flex flex-col h-full overflow-hidden bg-slate-900/10">
                <div className="px-4 py-2 bg-slate-900/60 text-xs font-semibold text-emerald-400 uppercase tracking-wider border-b border-slate-800 flex items-center justify-between">
                  <span>Literary English Translation</span>
                  {chapterContent?.has_translated && (
                    <span className="text-[11px] text-slate-400 font-normal">
                      Publication Draft
                    </span>
                  )}
                </div>
                <div className="flex-1 p-6 overflow-y-auto text-sm leading-relaxed text-slate-200 whitespace-pre-wrap selection:bg-emerald-500/30">
                  {chapterContent?.translated_text ? (
                    chapterContent.translated_text
                  ) : (
                    <div className="h-full flex flex-col items-center justify-center text-slate-500 text-sm gap-2">
                      <Clock className="w-8 h-8 text-slate-600" />
                      <span>Not translated yet.</span>
                      <button
                        onClick={() => selectedChapterNum && handleStart(selectedChapterNum)}
                        className="mt-2 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium cursor-pointer"
                      >
                        Translate Chapter {selectedChapterNum}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Collapsible Event Log Drawer */}
      <div className="border-t border-slate-800 bg-slate-900/90 backdrop-blur shrink-0 transition-all">
        <button
          onClick={() => setIsLogDrawerOpen(!isLogDrawerOpen)}
          className="w-full px-4 py-2 flex items-center justify-between text-xs font-mono text-slate-400 hover:text-slate-200 cursor-pointer transition-colors"
        >
          <div className="flex items-center gap-2">
            <Terminal className="w-3.5 h-3.5 text-indigo-400" />
            <span className="font-semibold text-slate-300">Live Pipeline Event Stream</span>
            {logs.length > 0 && (
              <span className="px-1.5 py-0.2 bg-slate-800 text-[10px] text-slate-400 rounded">
                {logs.length} events
              </span>
            )}
            {status?.last_log && (
              <span className="text-slate-500 truncate max-w-xl font-normal">
                &bull; {status.last_log}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {isLogDrawerOpen ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronUp className="w-4 h-4" />
            )}
          </div>
        </button>

        {isLogDrawerOpen && (
          <div className="h-44 p-3 bg-black/80 font-mono text-xs text-emerald-400/90 overflow-y-auto space-y-1 border-t border-slate-800/80">
            {logs.length === 0 ? (
              <div className="text-slate-600 italic">No events streamed yet.</div>
            ) : (
              logs.map((lg, i) => (
                <div key={i} className="leading-snug">
                  {lg}
                </div>
              ))
            )}
            <div ref={logBottomRef} />
          </div>
        )}
      </div>
    </div>
  );
};
