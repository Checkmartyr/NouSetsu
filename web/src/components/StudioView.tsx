import React, { useState, useEffect, useRef, useMemo } from 'react';
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
  ChevronRight,
  Folder,
  FolderOpen,
  Sparkles,
  BookOpen,
  Upload
} from 'lucide-react';
import { ChapterItem, ChapterContent, TranslationStatus } from '../types/dashboard';
import {
  fetchChapters,
  fetchChapterContent,
  fetchTranslationStatus,
  startTranslation,
  stopTranslation
} from '../services/dashboardApi';
import { UploadModal } from './UploadModal';

interface StudioViewProps {
  activeProjectPath: string | null;
  activeProjectTitle: string | null;
  onNavigateToReader: (chapterNum: number, folder?: string | null) => void;
  logs: string[];
}

export const StudioView: React.FC<StudioViewProps> = ({
  activeProjectPath,
  activeProjectTitle,
  onNavigateToReader,
  logs,
}) => {
  const [chapters, setChapters] = useState<ChapterItem[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<{ num: number; folder?: string | null } | null>(null);
  const [chapterContent, setChapterContent] = useState<ChapterContent | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [status, setStatus] = useState<TranslationStatus | null>(null);

  // Filters & Controls
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedFolder, setSelectedFolder] = useState<string>('all');
  const [isLogDrawerOpen, setIsLogDrawerOpen] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

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

    if (chList.length > 0) {
      setSelectedChapter((prev) => {
        if (!prev || !chList.some((c) => c.chapter_num === prev.num && (c.folder || null) === (prev.folder || null))) {
          return { num: chList[0].chapter_num, folder: chList[0].folder };
        }
        return prev;
      });
    } else {
      setSelectedChapter(null);
      setChapterContent(null);
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
    if (!selectedChapter || !activeProjectPath) {
      setChapterContent(null);
      return;
    }
    let active = true;
    setLoadingContent(true);
    fetchChapterContent(selectedChapter.num, activeProjectPath, selectedChapter.folder || undefined).then((content) => {
      if (active) {
        setChapterContent(content);
        setLoadingContent(false);
      }
    });
    return () => {
      active = false;
    };
  }, [selectedChapter, activeProjectPath]);

  // Scroll logs to bottom when updated
  useEffect(() => {
    if (isLogDrawerOpen && logBottomRef.current) {
      logBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, isLogDrawerOpen]);

  const handleStart = async (targetChapter?: number, targetFolder?: string) => {
    if (!activeProjectPath) return;
    setIsStarting(true);
    try {
      const folderToUse =
        targetFolder !== undefined
          ? targetFolder
          : selectedFolder !== 'all'
          ? selectedFolder
          : undefined;

      await startTranslation({
        project_path: activeProjectPath,
        chapter_num: targetChapter,
        limit: limitCount,
        force_retranslate: forceRetranslate,
        folder: folderToUse,
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
  const hasMultipleFolders = folders.length > 1 || (folders.length === 1 && chapters.some((c) => !c.folder));

  const filteredChapters = chapters.filter((c) => {
    const term = searchQuery.toLowerCase().trim();
    const mdName =
      c.output_file_name ||
      (c.file_name ? c.file_name.replace(/\.[^/.]+$/, '.md') : `${c.chapter_num}.md`);

    const matchesSearch =
      !term ||
      c.title.toLowerCase().includes(term) ||
      c.chapter_num.toString().includes(term) ||
      c.file_name.toLowerCase().includes(term) ||
      mdName.toLowerCase().includes(term) ||
      Boolean(c.folder && c.folder.toLowerCase().includes(term));

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

  interface FolderGroup {
    key: string;
    folder: string | null;
    label: string;
    chapters: ChapterItem[];
    completedCount: number;
    pausedCount: number;
    hasRunning: boolean;
  }

  const folderGroups = useMemo<FolderGroup[]>(() => {
    const map = new Map<string, { folder: string | null; label: string; chapters: ChapterItem[] }>();

    for (const ch of filteredChapters) {
      const fKey = ch.folder || '__root__';
      if (!map.has(fKey)) {
        map.set(fKey, {
          folder: ch.folder || null,
          label: ch.folder || 'Root / Default',
          chapters: [],
        });
      }
      map.get(fKey)!.chapters.push(ch);
    }

    const sortedKeys = Array.from(map.keys()).sort((a, b) => {
      if (a === '__root__') return -1;
      if (b === '__root__') return 1;
      return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
    });

    return sortedKeys.map((key) => {
      const item = map.get(key)!;
      const completedCount = item.chapters.filter((c) => c.is_completed).length;
      const pausedCount = item.chapters.filter((c) => c.status === 'PAUSED' || c.status === 'RESUME').length;
      const hasRunning = Boolean(
        status?.is_running &&
        item.chapters.some(
          (c) => c.chapter_num === status.active_chapter && (c.folder || null) === (status.active_folder || null)
        )
      );

      return {
        key,
        folder: item.folder,
        label: item.label,
        chapters: item.chapters,
        completedCount,
        pausedCount,
        hasRunning,
      };
    });
  }, [filteredChapters, status]);

  // Collapsible dropdown state for folder sections (empty = all expanded by default)
  const [collapsedFolders, setCollapsedFolders] = useState<Record<string, boolean>>({});

  const isFolderOpen = (key: string) => !collapsedFolders[key];

  const toggleFolder = (key: string) => {
    setCollapsedFolders((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const expandAllFolders = () => {
    setCollapsedFolders({});
  };

  const collapseAllFolders = () => {
    const allCollapsed: Record<string, boolean> = {};
    for (const g of folderGroups) {
      allCollapsed[g.key] = true;
    }
    setCollapsedFolders(allCollapsed);
  };

  // Auto-expand folder when selected chapter is inside it
  useEffect(() => {
    if (selectedChapter) {
      const fKey = selectedChapter.folder || '__root__';
      if (collapsedFolders[fKey]) {
        setCollapsedFolders((prev) => ({
          ...prev,
          [fKey]: false,
        }));
      }
    }
  }, [selectedChapter]);

  // Auto-expand all folders when actively searching
  useEffect(() => {
    if (searchQuery.trim()) {
      setCollapsedFolders({});
    }
  }, [searchQuery]);

  // Auto-expand active folder when running
  useEffect(() => {
    if (status?.is_running && status.active_folder) {
      const activeKey = status.active_folder || '__root__';
      if (collapsedFolders[activeKey]) {
        setCollapsedFolders((prev) => ({
          ...prev,
          [activeKey]: false,
        }));
      }
    }
  }, [status?.is_running, status?.active_folder]);

  useEffect(() => {
    if (filteredChapters.length > 0) {
      if (
        selectedChapter === null ||
        !filteredChapters.some(
          (c) => c.chapter_num === selectedChapter.num && (c.folder || null) === (selectedChapter.folder || null)
        )
      ) {
        setSelectedChapter({ num: filteredChapters[0].chapter_num, folder: filteredChapters[0].folder });
      }
    }
  }, [selectedFolder, filteredChapters]);

  const renderChapterRow = (ch: ChapterItem, inFolder: boolean) => {
    const isSelected =
      selectedChapter?.num === ch.chapter_num &&
      (selectedChapter?.folder || null) === (ch.folder || null);
    const isRunningThis =
      status?.is_running &&
      status.active_chapter === ch.chapter_num &&
      (status.active_folder || null) === (ch.folder || null);

    const mdFileName =
      ch.output_file_name ||
      (ch.file_name ? ch.file_name.replace(/\.[^/.]+$/, '.md') : `${ch.chapter_num}.md`);

    return (
      <div
        key={`${ch.folder || 'root'}_${ch.chapter_num}`}
        onClick={() => setSelectedChapter({ num: ch.chapter_num, folder: ch.folder })}
        className={`p-3 cursor-pointer transition-all flex items-start justify-between gap-2 select-none group/item ${
          inFolder ? 'pl-5 pr-3 bg-slate-950/20' : 'px-3'
        } ${
          isSelected
            ? 'bg-indigo-950/50 border-l-4 border-indigo-500 shadow-sm'
            : 'hover:bg-slate-900/60 border-l-4 border-transparent'
        }`}
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 min-w-0">
            {inFolder && (
              <span className="text-slate-500 text-xs font-mono select-none shrink-0">&gt;</span>
            )}
            <span
              className={`text-xs font-mono font-medium truncate ${
                isSelected ? 'text-indigo-200 font-semibold' : 'text-slate-200'
              }`}
              title={mdFileName}
            >
              {mdFileName}
            </span>
            {!inFolder && ch.folder && (
              <span className="text-[10px] px-1.5 py-0.2 bg-slate-800 text-slate-400 rounded shrink-0">
                {ch.folder}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1.5 text-[11px] text-slate-400">
            <span className="text-slate-500">Ch.{ch.chapter_num}</span>
            <span>&bull;</span>
            <span>{ch.raw_lines} lines</span>
            {ch.translated_words > 0 && (
              <>
                <span>&bull;</span>
                <span className="text-emerald-400 font-medium">
                  {ch.translated_words.toLocaleString()} words
                </span>
              </>
            )}
            {ch.quality_audit?.fidelity_score && (
              <>
                <span>&bull;</span>
                <span className="text-amber-400 font-medium">
                  ★ {ch.quality_audit.fidelity_score.toFixed(1)}
                </span>
              </>
            )}
          </div>
        </div>

        <div className="flex flex-col items-end shrink-0 gap-1">
          {isRunningThis ? (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 animate-pulse">
              RUNNING
            </span>
          ) : ch.is_completed ? (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              DONE
            </span>
          ) : ch.status === 'PAUSED' || ch.status === 'RESUME' ? (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
              PAUSED
            </span>
          ) : ch.status === 'FAILED' ? (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
              FAILED
            </span>
          ) : (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-500">
              WAIT
            </span>
          )}

          {!status?.is_running && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleStart(ch.chapter_num, ch.folder || undefined);
              }}
              title="Translate only this chapter"
              className="opacity-0 group-hover/item:opacity-100 hover:opacity-100 text-[10px] text-indigo-400 hover:text-indigo-300 transition-opacity"
            >
              Run ▶
            </button>
          )}
        </div>
      </div>
    );
  };

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
            onClick={() => setIsUploadModalOpen(true)}
            title="Upload chapter files"
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-sm font-semibold shadow-sm transition-all cursor-pointer"
          >
            <Upload className="w-4 h-4 text-indigo-400" />
            <span className="hidden sm:inline">Upload</span>
          </button>

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

          {/* Folder Hierarchy Toolbar (When multiple subfolders exist and viewing All) */}
          {hasMultipleFolders && selectedFolder === 'all' && (
            <div className="px-3 py-1.5 bg-slate-950/60 border-b border-slate-800/60 flex items-center justify-between text-xs text-slate-400 select-none">
              <div className="flex items-center gap-1.5">
                <Folder className="w-3.5 h-3.5 text-amber-400" />
                <span className="font-semibold text-slate-300">{folderGroups.length} Volumes</span>
                <span className="text-[11px] text-slate-500">({filteredChapters.length} ch)</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={expandAllFolders}
                  className="text-[10px] text-indigo-400 hover:text-indigo-300 transition-colors cursor-pointer"
                  title="Expand all folder dropdowns"
                >
                  Expand All
                </button>
                <span className="text-slate-600">&bull;</span>
                <button
                  type="button"
                  onClick={collapseAllFolders}
                  className="text-[10px] text-slate-400 hover:text-slate-300 transition-colors cursor-pointer"
                  title="Collapse all folder dropdowns"
                >
                  Collapse All
                </button>
              </div>
            </div>
          )}

          {/* Chapter Task List */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-800/50">
            {filteredChapters.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500 flex flex-col items-center justify-center gap-3">
                <FileText className="w-8 h-8 text-slate-600" />
                <p>
                  {chapters.length === 0
                    ? 'No chapters found in this project yet.'
                    : 'No chapters match the filter criteria.'}
                </p>
                <button
                  type="button"
                  onClick={() => setIsUploadModalOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded-lg text-xs font-semibold cursor-pointer transition-colors"
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>Upload Chapters</span>
                </button>
              </div>
            ) : hasMultipleFolders && selectedFolder === 'all' ? (
              <div className="divide-y divide-slate-800/60">
                {folderGroups.map((group) => {
                  const isOpen = isFolderOpen(group.key);
                  return (
                    <div key={group.key} className="bg-slate-900/10">
                      {/* Folder Dropdown Header */}
                      <div
                        onClick={() => toggleFolder(group.key)}
                        className="w-full px-3 py-2 bg-slate-950/80 hover:bg-slate-900 border-y border-slate-800/80 flex items-center justify-between cursor-pointer select-none transition-colors sticky top-0 z-10 backdrop-blur group"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          {isOpen ? (
                            <ChevronDown className="w-3.5 h-3.5 text-indigo-400 shrink-0 transition-transform" />
                          ) : (
                            <ChevronRight className="w-3.5 h-3.5 text-slate-500 shrink-0 transition-transform" />
                          )}
                          {isOpen ? (
                            <FolderOpen className="w-4 h-4 text-amber-400 shrink-0" />
                          ) : (
                            <Folder className="w-4 h-4 text-amber-500/80 shrink-0" />
                          )}
                          <span
                            className="font-semibold text-xs text-slate-200 truncate"
                            title={group.label}
                          >
                            {group.label}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800/90 text-slate-400 border border-slate-700/50">
                            {group.chapters.length}
                          </span>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <span className="text-[10px] font-mono text-slate-400">
                            <span
                              className={
                                group.completedCount === group.chapters.length &&
                                group.chapters.length > 0
                                  ? 'text-emerald-400 font-semibold'
                                  : 'text-slate-300'
                              }
                            >
                              {group.completedCount}
                            </span>
                            /{group.chapters.length}
                          </span>

                          {group.hasRunning && (
                            <span className="flex items-center gap-1 text-[10px] px-1.5 py-0.2 bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 rounded animate-pulse">
                              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                              Active
                            </span>
                          )}

                          {!status?.is_running && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleStart(undefined, group.folder || undefined);
                              }}
                              title={`Translate all pending chapters in ${group.label}`}
                              className="opacity-0 group-hover:opacity-100 px-1.5 py-0.5 text-[10px] bg-indigo-600/30 hover:bg-indigo-600/60 text-indigo-200 border border-indigo-500/40 rounded transition-opacity flex items-center gap-1 cursor-pointer"
                            >
                              <Play className="w-2.5 h-2.5 fill-indigo-200" />
                              <span>Run</span>
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Dropdown Items (Chapters) */}
                      {isOpen && (
                        <div className="divide-y divide-slate-800/40">
                          {group.chapters.map((ch) => renderChapterRow(ch, true))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="divide-y divide-slate-800/50">
                {filteredChapters.map((ch) => renderChapterRow(ch, false))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Dual Source / Target Comparison Reader */}
        <div className="flex-1 flex flex-col overflow-hidden bg-slate-950">
          {/* Subheader */}
          <div className="px-6 py-2.5 border-b border-slate-800/80 flex items-center justify-between bg-slate-900/30">
            <div className="flex items-center gap-3 min-w-0">
              <FileText className="w-4 h-4 text-indigo-400 shrink-0" />
              <div className="flex items-center gap-1.5 text-sm font-semibold text-slate-200 truncate">
                {selectedChapter?.folder && (
                  <span className="text-amber-400 font-mono text-xs flex items-center gap-1 shrink-0">
                    <Folder className="w-3.5 h-3.5" />
                    {selectedChapter.folder} &gt;
                  </span>
                )}
                <span className="truncate">
                  Chapter {selectedChapter?.num ?? '—'}:{' '}
                  <span className="font-mono text-xs text-slate-300">
                    {chapterContent?.output_file_name ||
                      (chapterContent?.output_file
                        ? chapterContent.output_file.split(/[\/\\]/).pop()
                        : chapterContent?.source_file
                        ? chapterContent.source_file.split(/[\/\\]/).pop()
                        : '')}
                  </span>
                </span>
              </div>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              {(chapterContent?.has_translated || Boolean(chapterContent?.translated_text?.trim())) && (
                <button
                  onClick={() =>
                    selectedChapter &&
                    onNavigateToReader(selectedChapter.num, selectedChapter.folder)
                  }
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
                  {(chapterContent?.has_translated || Boolean(chapterContent?.translated_text?.trim())) && (
                    <span className="text-[11px] text-slate-400 font-normal">
                      Publication Draft
                    </span>
                  )}
                </div>
                <div className="flex-1 p-6 overflow-y-auto text-sm leading-relaxed text-slate-200 whitespace-pre-wrap selection:bg-emerald-500/30">
                  {chapterContent?.translated_text?.trim() ? (
                    chapterContent.translated_text
                  ) : (
                    <div className="h-full flex flex-col items-center justify-center text-slate-500 text-sm gap-2">
                      <Clock className="w-8 h-8 text-slate-600" />
                      <span>Not translated yet.</span>
                      <button
                        onClick={() => selectedChapter && handleStart(selectedChapter.num)}
                        className="mt-2 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium cursor-pointer"
                      >
                        Translate Chapter {selectedChapter?.num ?? ''}
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

      {/* Upload Chapters Modal */}
      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        activeProjectPath={activeProjectPath}
        activeProjectTitle={activeProjectTitle}
        onUploadSuccess={({ folder }) => {
          refreshData();
          if (folder && folder !== 'raw_chapters' && folder !== 'default') {
            setSelectedFolder(folder);
          }
        }}
      />
    </div>
  );
};
