import React, { useRef } from 'react';
import { FolderOpen, FileText, Sparkles, Cpu, Clock, Layers, RefreshCw, Radio } from 'lucide-react';
import { LoadedChapter, ProjectMeta } from '../types/trace';

interface NavbarProps {
  chapters: LoadedChapter[];
  selectedChapterId: string | null;
  onSelectChapter: (id: string) => void;
  onOpenDirectory: () => void;
  onLoadFiles: (files: FileList) => void;
  onLoadDemo: () => void;
  isFileSystemSupported: boolean;

  // TUI Project Synchronization Props
  activeProject: ProjectMeta | null;
  projects: ProjectMeta[];
  onSwitchProject: (path: string) => void;
  autoSync: boolean;
  onToggleAutoSync: () => void;
  isSyncing: boolean;
  onManualSync: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  chapters,
  selectedChapterId,
  onSelectChapter,
  onOpenDirectory,
  onLoadFiles,
  onLoadDemo,
  isFileSystemSupported,
  activeProject,
  projects,
  onSwitchProject,
  autoSync,
  onToggleAutoSync,
  isSyncing,
  onManualSync,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const currentChapter = chapters.find((c) => c.id === selectedChapterId);
  const totalTokens = currentChapter?.document.total_token_usage?.total_tokens ?? 0;
  const totalDuration = currentChapter?.document.total_duration_seconds ?? 0;
  const totalInteractions = currentChapter?.document.total_interactions ?? 0;

  // Group chapters by folder
  const groupedChapters = chapters.reduce((acc, ch) => {
    const group = ch.folder || 'Root (Main Traces)';
    if (!acc[group]) acc[group] = [];
    acc[group].push(ch);
    return acc;
  }, {} as Record<string, LoadedChapter[]>);

  return (
    <header className="bg-slate-900/90 backdrop-blur border-b border-slate-800 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 gap-4">

          {/* Logo & Mascot */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/20 text-xl">
              🐾
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg text-slate-100 tracking-tight">Nousetsu</span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  Visualizer
                </span>
              </div>
              <p className="text-xs text-slate-400 font-medium">Multi-Agent Prompt & Output Traces</p>
            </div>
          </div>

          {/* Center Column: Project Selector + Chapter Selector */}
          <div className="flex items-center gap-3 flex-1 max-w-2xl">

            {/* TUI Project Selector Dropdown (when connected to API) */}
            {activeProject && projects.length > 0 ? (
              <div className="flex items-center gap-1.5 shrink-0 max-w-[210px]">
                <div className="relative w-full">
                  <select
                    value={activeProject.path}
                    onChange={(e) => onSwitchProject(e.target.value)}
                    title={`Active TUI Project: ${activeProject.title}\nPath: ${activeProject.path}`}
                    aria-label="Select active project"
                    className="w-full bg-slate-950 border border-indigo-500/50 hover:border-indigo-400 rounded-lg px-2.5 py-1.5 text-xs text-indigo-200 font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500 truncate cursor-pointer transition-colors"
                  >
                    {projects.map((p) => (
                      <option key={p.path} value={p.path} className="bg-slate-900 text-slate-100 py-1 font-normal">
                        📚 {p.title || p.name} {p.is_active ? '★ (Active)' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            ) : null}

            {/* Chapter Selector */}
            {chapters.length > 0 ? (
              <div className="flex-1 min-w-0">
                <label htmlFor="chapter-select" className="sr-only">Select Chapter</label>
                <select
                  id="chapter-select"
                  value={selectedChapterId || ''}
                  onChange={(e) => onSelectChapter(e.target.value)}
                  aria-label="Select chapter trace"
                  className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-1.5 text-xs text-slate-200 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-colors cursor-pointer"
                >
                  {Object.entries(groupedChapters).map(([group, groupList]) => (
                    <optgroup label={`📁 ${group}`} key={group} className="bg-slate-900 text-slate-300 font-semibold">
                      {groupList.map((ch) => (
                        <option key={ch.id} value={ch.id} className="bg-slate-950 text-slate-100 py-1">
                          Chapter {ch.chapterNum} — ({ch.document.total_interactions} interactions, {(ch.document.total_token_usage?.total_tokens || 0).toLocaleString()} tokens)
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
            ) : (
              <div className="text-xs text-slate-400 italic">No traces loaded yet</div>
            )}

            {/* Quick stats pills */}
            {currentChapter && (
              <div className="hidden xl:flex items-center gap-1.5 text-xs shrink-0">
                <span className="flex items-center gap-1 px-2 py-1 rounded-md bg-slate-800 text-slate-300 border border-slate-700 text-[11px]">
                  <Layers className="w-3 h-3 text-indigo-400" />
                  <span>{totalInteractions}</span>
                </span>
                <span className="flex items-center gap-1 px-2 py-1 rounded-md bg-slate-800 text-slate-300 border border-slate-700 text-[11px]">
                  <Cpu className="w-3 h-3 text-amber-400" />
                  <span>{totalTokens.toLocaleString()} tok</span>
                </span>
                <span className="flex items-center gap-1 px-2 py-1 rounded-md bg-slate-800 text-slate-300 border border-slate-700 text-[11px]">
                  <Clock className="w-3 h-3 text-emerald-400" />
                  <span>{totalDuration.toFixed(1)}s</span>
                </span>
              </div>
            )}
          </div>

          {/* Action & Sync Buttons */}
          <div className="flex items-center gap-2 shrink-0">
            {/* TUI Sync Status Indicator & Manual Sync */}
            {activeProject ? (
              <div className="flex items-center gap-1 bg-slate-950 border border-emerald-500/40 rounded-lg px-2 py-1 shadow-sm">
                <button
                  type="button"
                  onClick={onManualSync}
                  className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium hover:text-emerald-300 transition-colors"
                  title="Click to manually refresh traces from TUI active project"
                >
                  <span className="relative flex h-2 w-2">
                    {autoSync && (
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    )}
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                  <span className="hidden sm:inline">TUI Sync</span>
                  <RefreshCw className={`w-3 h-3 ${isSyncing ? 'animate-spin text-emerald-300' : 'text-emerald-500'}`} />
                </button>

                <button
                  type="button"
                  onClick={onToggleAutoSync}
                  className={`ml-1 px-1.5 py-0.5 rounded text-[10px] font-bold transition-colors ${
                    autoSync
                      ? 'bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30'
                      : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                  title={autoSync ? 'Auto-sync active (every 2.5s). Click to pause.' : 'Auto-sync paused. Click to resume.'}
                >
                  {autoSync ? 'LIVE' : 'PAUSED'}
                </button>
              </div>
            ) : (
              <span className="flex items-center gap-1 text-[11px] text-slate-400 bg-slate-800/70 border border-slate-700 px-2 py-1 rounded-lg">
                <Radio className="w-3 h-3 text-slate-500" />
                <span className="hidden sm:inline">Standalone</span>
              </span>
            )}

            {/* Native Directory Picker */}
            {isFileSystemSupported && (
              <button
                type="button"
                onClick={onOpenDirectory}
                className="flex items-center gap-1.5 px-2.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-md shadow-indigo-600/20 transition-colors"
                title="Open local .novel/traces folder manually"
              >
                <FolderOpen className="w-3.5 h-3.5" />
                <span className="hidden md:inline">Open Folder</span>
              </button>
            )}

            {/* Fallback File/Folder input */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".json,.jsonl"
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  onLoadFiles(e.target.files);
                }
              }}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium border border-slate-700 transition-colors"
              title="Select .json or .jsonl files"
            >
              <FileText className="w-3.5 h-3.5 text-slate-400" />
              <span className="hidden lg:inline">Files</span>
            </button>

            {/* Demo Button */}
            <button
              type="button"
              onClick={onLoadDemo}
              className="flex items-center gap-1.5 px-2.5 py-1.5 bg-pink-500/10 hover:bg-pink-500/20 text-pink-400 border border-pink-500/30 rounded-lg text-xs font-medium transition-colors"
              title="Load demo traces"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Demo</span>
            </button>
          </div>

        </div>
      </div>
    </header>
  );
};
