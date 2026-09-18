import React, { useRef } from 'react';
import {
  FolderOpen,
  FileText,
  RefreshCw,
  Layers,
  BookOpen,
  BookMarked,
  Settings as SettingsIcon,
  Play,
  Plus
} from 'lucide-react';
import { LoadedChapter, ProjectMeta } from '../types/trace';
import { WorkspaceTab } from '../types/dashboard';

interface NavbarProps {
  activeTab: WorkspaceTab;
  onSelectTab: (tab: WorkspaceTab) => void;

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
  onOpenNewProjectModal?: () => void;
  autoSync: boolean;
  onToggleAutoSync: () => void;
  isSyncing: boolean;
  onManualSync: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onSelectTab,
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
  onOpenNewProjectModal,
  autoSync,
  onToggleAutoSync,
  isSyncing,
  onManualSync,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Group chapters by folder
  const groupedChapters = chapters.reduce((acc, ch) => {
    const group = ch.folder || 'Root (Main Traces)';
    if (!acc[group]) acc[group] = [];
    acc[group].push(ch);
    return acc;
  }, {} as Record<string, LoadedChapter[]>);

  const navTabs: { id: WorkspaceTab; label: string; icon: React.ReactNode }[] = [
    { id: 'studio', label: 'Studio', icon: <Play className="w-3.5 h-3.5 fill-current" /> },
    { id: 'reader', label: 'Reader', icon: <BookOpen className="w-3.5 h-3.5" /> },
    { id: 'bible', label: 'Novel Bible', icon: <BookMarked className="w-3.5 h-3.5" /> },
    { id: 'traces', label: 'Traces', icon: <Layers className="w-3.5 h-3.5" /> },
    { id: 'settings', label: 'Settings', icon: <SettingsIcon className="w-3.5 h-3.5" /> },
  ];

  return (
    <header className="bg-slate-900/90 backdrop-blur border-b border-slate-800 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 gap-4">

          {/* Left: Logo & Mascot */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/20 text-xl select-none">
              🐾
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg text-slate-100 tracking-tight">Nousetsu</span>
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  Agent Web UI
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-medium">Literary Translation Studio</p>
            </div>
          </div>

          {/* Center: Workspace Tab Switcher */}
          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800 shadow-inner">
            {navTabs.map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => onSelectTab(tab.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-all ${
                    isActive
                      ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md shadow-indigo-600/20'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/50'
                  }`}
                >
                  {tab.icon}
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* Right Column: Project & Trace Controls */}
          <div className="flex items-center gap-2 shrink-0">

            {/* Trace Chapter Selector (Only shown on traces tab) */}
            {activeTab === 'traces' && chapters.length > 0 && (
              <div className="hidden lg:block w-48">
                <select
                  value={selectedChapterId || ''}
                  onChange={(e) => onSelectChapter(e.target.value)}
                  aria-label="Select chapter trace"
                  className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-2 py-1 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 truncate cursor-pointer"
                >
                  {Object.entries(groupedChapters).map(([group, groupList]) => (
                    <optgroup label={`📁 ${group}`} key={group} className="bg-slate-900 text-slate-300 font-semibold">
                      {groupList.map((ch) => (
                        <option key={ch.id} value={ch.id} className="bg-slate-950 text-slate-100 py-1">
                          Ch.{ch.chapterNum} ({ch.document.total_interactions} acts)
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
            )}

            {/* TUI Project Selector Dropdown & New Project Button */}
            {activeProject && projects.length > 0 ? (
              <div className="flex items-center gap-1.5 max-w-[240px]">
                <select
                  value={
                    projects.find(
                      (p) => p.path.replace(/\\/g, '/').toLowerCase() === activeProject.path.replace(/\\/g, '/').toLowerCase()
                    )?.path || activeProject.path
                  }
                  onChange={(e) => onSwitchProject(e.target.value)}
                  title={`Active Project: ${activeProject.title}\nPath: ${activeProject.path}`}
                  aria-label="Select active project"
                  className="w-full bg-slate-950 border border-indigo-500/40 hover:border-indigo-400 rounded-lg px-2 py-1 text-xs text-indigo-200 font-semibold focus:outline-none focus:ring-1 focus:ring-indigo-500 truncate cursor-pointer transition-colors"
                >
                  {projects.map((p) => (
                    <option key={p.path} value={p.path} className="bg-slate-900 text-slate-100 py-1 font-normal">
                      📚 {p.title || p.name}
                    </option>
                  ))}
                </select>

                {onOpenNewProjectModal && (
                  <button
                    type="button"
                    onClick={onOpenNewProjectModal}
                    title="Initialize new novel project inside project/"
                    className="flex items-center gap-1 px-2 py-1 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 border border-indigo-500/30 text-xs font-semibold cursor-pointer transition-colors shrink-0"
                  >
                    <Plus className="w-3 h-3" />
                    <span>New</span>
                  </button>
                )}
              </div>
            ) : null}

            {/* TUI Sync Status Indicator */}
            {activeProject ? (
              <div className="flex items-center gap-1 bg-slate-950 border border-emerald-500/40 rounded-lg px-2 py-1 shadow-sm">
                <button
                  type="button"
                  onClick={onManualSync}
                  className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium hover:text-emerald-300 transition-colors cursor-pointer"
                  title="Click to refresh from project"
                >
                  <span className="relative flex h-2 w-2">
                    {autoSync && (
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    )}
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                  <RefreshCw className={`w-3 h-3 ${isSyncing ? 'animate-spin text-emerald-300' : 'text-emerald-500'}`} />
                </button>
                <button
                  type="button"
                  onClick={onToggleAutoSync}
                  className={`ml-1 px-1.5 py-0.5 rounded text-[10px] font-bold transition-colors cursor-pointer ${
                    autoSync
                      ? 'bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30'
                      : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                  title={autoSync ? 'Auto-sync active. Click to pause.' : 'Auto-sync paused. Click to resume.'}
                >
                  {autoSync ? 'LIVE' : 'PAUSED'}
                </button>
              </div>
            ) : null}

            {/* Traces-only fallback files / folder */}
            {activeTab === 'traces' && (
              <>
                {isFileSystemSupported && (
                  <button
                    type="button"
                    onClick={onOpenDirectory}
                    className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs cursor-pointer"
                    title="Open local traces folder"
                  >
                    <FolderOpen className="w-3.5 h-3.5" />
                  </button>
                )}
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
                  className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs cursor-pointer"
                  title="Upload trace files"
                >
                  <FileText className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={onLoadDemo}
                  className="px-2 py-1 bg-pink-500/10 hover:bg-pink-500/20 text-pink-400 border border-pink-500/30 rounded-lg text-xs font-medium cursor-pointer"
                  title="Load demo traces"
                >
                  Demo
                </button>
              </>
            )}

          </div>

        </div>
      </div>
    </header>
  );
};
