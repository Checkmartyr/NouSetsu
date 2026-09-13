import React, { useState, useEffect, useCallback, useRef } from 'react';
import { LoadedChapter, ProjectMeta, SyncState } from './types/trace';
import { DEMO_CHAPTER_TRACE } from './services/mockData';
import { openDirectoryPicker, groupFilesIntoChapters } from './services/traceLoader';
import { fetchActiveProject, fetchSyncState, fetchProjectTraces, switchActiveProject } from './services/apiClient';
import { Navbar } from './components/Navbar';
import { StagePipeline } from './components/StagePipeline';
import { TraceTimeline } from './components/TraceTimeline';
import { TraceDetail } from './components/TraceDetail';
import { UploadCloud, AlertCircle, Sparkles, CheckCircle2 } from 'lucide-react';

export const App: React.FC = () => {
  const [chapters, setChapters] = useState<LoadedChapter[]>([
    {
      id: 'demo_chapter_1',
      fileName: 'chapter_0001.json',
      folder: 'Villainess_05',
      chapterNum: 1,
      document: DEMO_CHAPTER_TRACE,
    },
  ]);

  const [selectedChapterId, setSelectedChapterId] = useState<string | null>('demo_chapter_1');
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(
    DEMO_CHAPTER_TRACE.traces[0]?.trace_id || null
  );
  const [selectedStageFilter, setSelectedStageFilter] = useState<string | null>(null);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // TUI Project Synchronization State
  const [activeProject, setActiveProject] = useState<ProjectMeta | null>(null);
  const [projects, setProjects] = useState<ProjectMeta[]>([]);
  const [autoSync, setAutoSync] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncToast, setSyncToast] = useState<string | null>(null);
  const lastSyncRef = useRef<SyncState | null>(null);

  const isFileSystemSupported = typeof window !== 'undefined' && 'showDirectoryPicker' in window;

  const currentChapter = chapters.find((c) => c.id === selectedChapterId) || chapters[0];
  const traces = currentChapter?.document.traces || [];
  const currentTrace = traces.find((t) => t.trace_id === selectedTraceId) || traces[0];

  // Helper to show transient sync toasts
  const triggerToast = (msg: string) => {
    setSyncToast(msg);
    setTimeout(() => setSyncToast(null), 4000);
  };

  // If chapter changes, select its first trace
  const handleSelectChapter = (id: string) => {
    setSelectedChapterId(id);
    const target = chapters.find((c) => c.id === id);
    if (target && target.document.traces.length > 0) {
      setSelectedTraceId(target.document.traces[0].trace_id);
    }
  };

  // Load traces from API for a project
  const loadTracesFromBackend = useCallback(async (projectPath?: string) => {
    setIsSyncing(true);
    try {
      const res = await fetchProjectTraces(projectPath);
      if (res && res.chapters.length > 0) {
        setChapters(res.chapters);
        setSelectedChapterId(res.chapters[0].id);
        setSelectedTraceId(res.chapters[0].document.traces[0]?.trace_id || null);
      }
    } catch (err: any) {
      console.warn('Could not load traces from backend:', err);
    } finally {
      setIsSyncing(false);
    }
  }, []);

  // Poll sync state
  const syncWithBackend = useCallback(async (force: boolean = false) => {
    try {
      const syncState = await fetchSyncState();
      if (!syncState) return;

      const last = lastSyncRef.current;
      const projectChanged = !last || last.active_project_path !== syncState.active_project_path;
      const tracesUpdated = last && (last.latest_trace_mtime !== syncState.latest_trace_mtime || last.traces_count !== syncState.traces_count);

      if (projectChanged || tracesUpdated || force) {
        lastSyncRef.current = syncState;

        // Re-fetch project metadata
        const activeRes = await fetchActiveProject();
        if (activeRes) {
          setActiveProject(activeRes.active_project);
          setProjects(activeRes.projects);
        }

        if (projectChanged) {
          triggerToast(`(=^･ω･^=) Synced with TUI project: ${syncState.active_project_title || 'Novel'}`);
        } else if (tracesUpdated) {
          triggerToast(`🐾 New traces detected from TUI! Refreshed.`);
        }

        await loadTracesFromBackend(syncState.active_project_path || undefined);
      }
    } catch {
      // Backend not available or interrupted
    }
  }, [loadTracesFromBackend]);

  // Initial mount: connect to backend if available
  useEffect(() => {
    const init = async () => {
      const activeRes = await fetchActiveProject();
      if (activeRes && activeRes.active_project) {
        setActiveProject(activeRes.active_project);
        setProjects(activeRes.projects);
        lastSyncRef.current = {
          active_project_path: activeRes.active_project.path,
          active_project_title: activeRes.active_project.title,
          traces_count: activeRes.active_project.trace_count,
          latest_trace_mtime: activeRes.active_project.latest_trace_mtime,
        };
        await loadTracesFromBackend(activeRes.active_project.path);
        triggerToast(`🟢 Connected to TUI project: ${activeRes.active_project.title}`);
      }
    };
    init();
  }, [loadTracesFromBackend]);

  // Background sync polling (every 2.5s)
  useEffect(() => {
    if (!autoSync) return;
    const interval = setInterval(() => {
      syncWithBackend(false);
    }, 2500);
    return () => clearInterval(interval);
  }, [autoSync, syncWithBackend]);

  // Handle user switching project from Web Navbar
  const handleSwitchProject = async (targetPath: string) => {
    const ok = await switchActiveProject(targetPath);
    if (ok) {
      await syncWithBackend(true);
      triggerToast(`Switched active project in TUI registry!`);
    } else {
      setErrorMessage(`Failed to switch project to ${targetPath}`);
    }
  };

  // Open directory via File System Access API (Manual mode)
  const handleOpenDirectory = async () => {
    setErrorMessage(null);
    try {
      const files = await openDirectoryPicker();
      if (files.length === 0) {
        setErrorMessage('No .json or .jsonl trace files found in selected directory.');
        return;
      }
      const loaded = groupFilesIntoChapters(files);
      if (loaded.length > 0) {
        setChapters(loaded);
        setSelectedChapterId(loaded[0].id);
        setSelectedTraceId(loaded[0].document.traces[0]?.trace_id || null);
        triggerToast(`Loaded ${loaded.length} chapters from local folder!`);
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setErrorMessage(err.message || 'Failed to open directory');
      }
    }
  };

  // Load from file input or drag-drop (Manual mode)
  const handleLoadFiles = async (fileList: FileList) => {
    setErrorMessage(null);
    try {
      const files: { name: string; content: string; relativePath?: string }[] = [];
      for (let i = 0; i < fileList.length; i++) {
        const file = fileList[i];
        if (file.name.endsWith('.json') || file.name.endsWith('.jsonl')) {
          const content = await file.text();
          const relativePath = file.webkitRelativePath || file.name;
          files.push({ name: file.name, content, relativePath });
        }
      }

      if (files.length === 0) {
        setErrorMessage('Please upload valid .json or .jsonl trace files.');
        return;
      }

      const loaded = groupFilesIntoChapters(files);
      if (loaded.length > 0) {
        setChapters(loaded);
        setSelectedChapterId(loaded[0].id);
        setSelectedTraceId(loaded[0].document.traces[0]?.trace_id || null);
        triggerToast(`Loaded ${loaded.length} chapters from uploaded files!`);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to parse uploaded files.');
    }
  };

  // Reset to Demo
  const handleLoadDemo = () => {
    setChapters([
      {
        id: 'demo_chapter_1',
        fileName: 'chapter_0001.json',
        folder: 'Villainess_05',
        chapterNum: 1,
        document: DEMO_CHAPTER_TRACE,
      },
    ]);
    setSelectedChapterId('demo_chapter_1');
    setSelectedTraceId(DEMO_CHAPTER_TRACE.traces[0]?.trace_id || null);
    setSelectedStageFilter(null);
    setErrorMessage(null);
    triggerToast('Loaded demo chapter trace dataset nya~!');
  };

  // Drag-and-drop listener
  useEffect(() => {
    const handleDragOver = (e: DragEvent) => {
      e.preventDefault();
      setIsDraggingOver(true);
    };

    const handleDragLeave = (e: DragEvent) => {
      e.preventDefault();
      if (!e.relatedTarget) {
        setIsDraggingOver(false);
      }
    };

    const handleDrop = (e: DragEvent) => {
      e.preventDefault();
      setIsDraggingOver(false);
      if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
        handleLoadFiles(e.dataTransfer.files);
      }
    };

    window.addEventListener('dragover', handleDragOver);
    window.addEventListener('dragleave', handleDragLeave);
    window.addEventListener('drop', handleDrop);

    return () => {
      window.removeEventListener('dragover', handleDragOver);
      window.removeEventListener('dragleave', handleDragLeave);
      window.removeEventListener('drop', handleDrop);
    };
  }, []);

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-100 overflow-hidden font-sans relative">
      {/* Top Navigation with TUI sync */}
      <Navbar
        chapters={chapters}
        selectedChapterId={selectedChapterId}
        onSelectChapter={handleSelectChapter}
        onOpenDirectory={handleOpenDirectory}
        onLoadFiles={handleLoadFiles}
        onLoadDemo={handleLoadDemo}
        isFileSystemSupported={isFileSystemSupported}
        activeProject={activeProject}
        projects={projects}
        onSwitchProject={handleSwitchProject}
        autoSync={autoSync}
        onToggleAutoSync={() => setAutoSync(!autoSync)}
        isSyncing={isSyncing}
        onManualSync={() => syncWithBackend(true)}
      />

      {/* Sync Toast Notification */}
      {syncToast && (
        <div className="absolute top-20 right-6 z-50 bg-indigo-900/90 text-indigo-100 border border-indigo-500/50 backdrop-blur px-4 py-2 rounded-xl text-xs font-medium shadow-xl flex items-center gap-2 animate-fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{syncToast}</span>
        </div>
      )}

      {/* Error banner */}
      {errorMessage && (
        <div className="bg-red-500/20 border-b border-red-500/30 px-4 py-2 text-red-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-slate-400 hover:text-white"
          >
            ✕
          </button>
        </div>
      )}

      {/* Pipeline Stage Progression Ribbon */}
      <StagePipeline
        traces={traces}
        selectedStageFilter={selectedStageFilter}
        onSelectStageFilter={setSelectedStageFilter}
      />

      {/* Main Workspace (Split View) */}
      <div className="flex-1 flex overflow-hidden">
        {/* Timeline sidebar */}
        <TraceTimeline
          traces={traces}
          selectedTraceId={selectedTraceId}
          onSelectTrace={setSelectedTraceId}
          selectedStageFilter={selectedStageFilter}
        />

        {/* Trace Inspector */}
        {currentTrace && currentChapter ? (
          <TraceDetail trace={currentTrace} chapterDoc={currentChapter.document} />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-slate-500 text-sm space-y-3">
            <p>No traces recorded for this chapter yet.</p>
            <button
              onClick={handleLoadDemo}
              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Load Demo Traces</span>
            </button>
          </div>
        )}
      </div>

      {/* Drag & Drop Overlay */}
      {isDraggingOver && (
        <div className="fixed inset-0 z-50 bg-indigo-950/80 backdrop-blur-sm flex flex-col items-center justify-center pointer-events-none border-4 border-dashed border-indigo-500 m-4 rounded-2xl">
          <UploadCloud className="w-16 h-16 text-indigo-400 animate-bounce mb-4" />
          <h3 className="text-xl font-bold text-white mb-1">
            Drop Trace Files Here (=^･ω･^=)
          </h3>
          <p className="text-sm text-indigo-300">
            Drop chapter_XXXX.json or chapter_XXXX.jsonl to inspect traces!
          </p>
        </div>
      )}
    </div>
  );
};
