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
import { ProjectMeta } from '../types/trace';
import { WorkspaceTab } from '../types/dashboard';

interface NavbarProps {
  activeTab: WorkspaceTab;
  onSelectTab: (tab: WorkspaceTab) => void;
  onOpenDirectory: () => void;
  onLoadFiles: (files: FileList) => void;
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
  onOpenDirectory,
  onLoadFiles,
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

  const navTabs: { id: WorkspaceTab; label: string; icon: React.ReactNode }[] = [
    { id: 'studio', label: 'Studio', icon: <Play className="w-3 h-3 fill-current" /> },
    { id: 'reader', label: 'Reader', icon: <BookOpen className="w-3.5 h-3.5" /> },
    { id: 'bible', label: 'Novel Bible', icon: <BookMarked className="w-3.5 h-3.5" /> },
    { id: 'traces', label: 'Traces', icon: <Layers className="w-3.5 h-3.5" /> },
    { id: 'settings', label: 'Settings', icon: <SettingsIcon className="w-3.5 h-3.5" /> },
  ];

  return (
    <header className="bg-[#2b2622] border-b border-[#3f3a36] sticky top-0 z-50">
      <div className="w-full px-2 sm:px-6">
        <div className="flex items-center justify-between h-14 gap-2 sm:gap-4 overflow-hidden">

          {/* Left: Logo & Wordmark */}
          <div className="flex items-center gap-2 shrink-0">
            <div className="w-7 h-7 rounded-[4px] bg-[#383330] border border-[#3f3a36] flex items-center justify-center select-none shadow-xs overflow-hidden">
              <img src="/favicon.png" alt="Nousetsu" className="w-full h-full object-cover" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-medium text-sm text-[#f7f5f0] tracking-[-0.3px]">Nousetsu</span>
                <span className="hidden sm:inline text-[10px] font-mono px-1.5 py-0.2 rounded-[2px] bg-[#383330] text-[#c9c0ad] border border-[#3f3a36]">
                  agent
                </span>
              </div>
            </div>
          </div>

          {/* Center: Workspace Tab Switcher */}
          <nav className="flex items-center gap-1 bg-[#2b2622] p-0.5 rounded-[4px] border border-[#3f3a36] overflow-x-auto max-w-full shrink min-w-0" style={{ scrollbarWidth: 'none' }}>
            {navTabs.map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  aria-label={tab.label}
                  onClick={() => onSelectTab(tab.id)}
                  className={`flex items-center gap-1 sm:gap-1.5 px-2 sm:px-2.5 py-1 text-xs transition-colors cursor-pointer rounded-[3px] shrink-0 whitespace-nowrap ${
                    isActive
                      ? 'bg-[#383330] text-[#f7f5f0] border border-[#544d47] font-medium'
                      : 'text-[#c9c0ad] hover:text-[#f7f5f0] hover:bg-[#383330]/50 font-normal'
                  }`}
                >
                  {tab.icon}
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Right Column: Project & Trace Controls */}
          <div className="hidden md:flex items-center gap-2 shrink-0">

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
                  className="w-full bg-[#383330] border border-[#3f3a36] hover:border-[#544d47] rounded-[3px] px-2 py-1 text-xs text-[#f7f5f0] font-medium focus:outline-none focus:border-[#dad2c1] truncate cursor-pointer transition-colors"
                >
                  {projects.map((p) => (
                    <option key={p.path} value={p.path} className="bg-[#383330] text-[#f7f5f0] py-1 font-normal">
                      📖 {p.title || p.name}
                    </option>
                  ))}
                </select>

                {onOpenNewProjectModal && (
                  <button
                    type="button"
                    onClick={onOpenNewProjectModal}
                    title="Initialize new novel project inside project/"
                    className="flex items-center gap-1 px-2 py-1 rounded-[3px] bg-[#383330] hover:bg-[#453f3a] text-[#f7f5f0] border border-[#3f3a36] text-xs font-medium cursor-pointer transition-colors shrink-0"
                  >
                    <Plus className="w-3 h-3" />
                    <span>New</span>
                  </button>
                )}
              </div>
            ) : null}

            {/* TUI Sync Status Indicator */}
            {activeProject ? (
              <div className="flex items-center gap-1 bg-[#383330] border border-[#3f3a36] rounded-[3px] px-2 py-1">
                <button
                  type="button"
                  onClick={onManualSync}
                  className="flex items-center gap-1.5 text-xs text-[#c9c0ad] hover:text-[#f7f5f0] transition-colors cursor-pointer"
                  title="Click to refresh from project"
                >
                  <span className="relative flex h-2 w-2">
                    {autoSync && (
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60"></span>
                    )}
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                  <RefreshCw className={`w-3 h-3 ${isSyncing ? 'animate-spin text-[#f7f5f0]' : 'text-[#aea69c]'}`} />
                </button>
                <button
                  type="button"
                  onClick={onToggleAutoSync}
                  className={`ml-1 px-1.5 py-0.5 rounded-[2px] text-[10px] font-mono font-medium transition-colors cursor-pointer ${
                    autoSync
                      ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-800/40'
                      : 'bg-[#2b2622] text-[#aea69c] border border-[#3f3a36]'
                  }`}
                  title={autoSync ? 'Auto-sync active. Click to pause.' : 'Auto-sync paused. Click to resume.'}
                >
                  {autoSync ? 'LIVE' : 'PAUSED'}
                </button>
              </div>
            ) : null}

            {/* Traces-only fallback files / folder */}
            {activeTab === 'traces' && (
              <div className="flex items-center gap-1">
                {isFileSystemSupported && (
                  <button
                    type="button"
                    onClick={onOpenDirectory}
                    className="p-1.5 bg-[#383330] hover:bg-[#453f3a] text-[#c9c0ad] hover:text-[#f7f5f0] border border-[#3f3a36] rounded-[3px] text-xs cursor-pointer transition-colors"
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
                  className="p-1.5 bg-[#383330] hover:bg-[#453f3a] text-[#c9c0ad] hover:text-[#f7f5f0] border border-[#3f3a36] rounded-[3px] text-xs cursor-pointer transition-colors"
                  title="Upload trace files"
                >
                  <FileText className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

          </div>

        </div>
      </div>
    </header>
  );
};
