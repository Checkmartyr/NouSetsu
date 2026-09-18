import React, { useState, useEffect, useCallback, useRef } from 'react';
import { LoadedChapter, ProjectMeta, SyncState } from './types/trace';
import { WorkspaceTab } from './types/dashboard';
import { DEMO_CHAPTER_TRACE } from './services/mockData';
import { openDirectoryPicker, groupFilesIntoChapters } from './services/traceLoader';
import {
  fetchActiveProject,
  fetchSyncState,
  fetchProjectTraces,
  switchActiveProject,
} from './services/apiClient';
import { connectSSE } from './services/dashboardApi';
import { Navbar } from './components/Navbar';
import { StagePipeline } from './components/StagePipeline';
import { TraceTimeline } from './components/TraceTimeline';
import { TraceDetail, DetailTab } from './components/TraceDetail';
import { StudioView } from './components/StudioView';
import { ReaderView } from './components/ReaderView';
import { BibleView } from './components/BibleView';
import { SettingsView } from './components/SettingsView';
import { NewProjectModal } from './components/NewProjectModal';
import { UploadCloud, AlertCircle, Sparkles, CheckCircle2 } from 'lucide-react';

export const App: React.FC = () => {
  // Navigation & Workspace State
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceTab>('studio');
  const [readerChapterNum, setReaderChapterNum] = useState<number | null>(null);

  // Real-time Event Logs from SSE
  const [logs, setLogs] = useState<string[]>([]);

  // Trace State
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
  const [activeDetailTab, setActiveDetailTab] = useState<DetailTab>('output');
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Synchronized refs to avoid stale closure during async polling
  const selectedChapterIdRef = useRef<string | null>(selectedChapterId);
  const selectedTraceIdRef = useRef<string | null>(selectedTraceId);
  const selectedStageFilterRef = useRef<string | null>(selectedStageFilter);

  useEffect(() => {
    selectedChapterIdRef.current = selectedChapterId;
  }, [selectedChapterId]);

  useEffect(() => {
    selectedTraceIdRef.current = selectedTraceId;
  }, [selectedTraceId]);

  useEffect(() => {
    selectedStageFilterRef.current = selectedStageFilter;
  }, [selectedStageFilter]);

  // TUI Project Synchronization State
  const [activeProject, setActiveProject] = useState<ProjectMeta | null>(null);
  const [projects, setProjects] = useState<ProjectMeta[]>([]);
  const [projectsDirName, setProjectsDirName] = useState<string>('project');
  const [isNewProjectModalOpen, setIsNewProjectModalOpen] = useState(false);
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

  // Connect to SSE stream
  useEffect(() => {
    const disconnect = connectSSE((event, data) => {
      const ts = new Date().toLocaleTimeString();
      let logMsg = `[${ts}] ${event}`;

      if (event === 'log' && typeof data === 'object' && data.message) {
        logMsg = `[${ts}] ${data.message}`;
      } else if (event === 'stage_progress' && typeof data === 'object') {
        logMsg = `[${ts}] Ch.${data.chapter_num ?? '?'}: [${data.stage}] ${data.message || ''}`;
      } else if (event === 'chapter_finished' && typeof data === 'object') {
        logMsg = `[${ts}] ✓ Finished Ch.${data.chapter_num ?? '?'}`;
        // Automatically reload traces on chapter completion
        if (activeProject?.path) {
          loadTracesFromBackend(activeProject.path);
        }
      } else if (typeof data === 'object' && data.message) {
        logMsg = `[${ts}] [${event}] ${data.message}`;
      }

      setLogs((prev) => [...prev.slice(-300), logMsg]);
    });

    return () => {
      disconnect();
    };
  }, [activeProject]);

  // If chapter changes, preserve active stage filter or select first trace
  const handleSelectChapter = (id: string) => {
    setSelectedChapterId(id);
    const target = chapters.find((c) => c.id === id);
    if (target && target.document.traces.length > 0) {
      if (selectedStageFilter) {
        const matchingStageTrace = target.document.traces.find((t) => t.stage === selectedStageFilter);
        if (matchingStageTrace) {
          setSelectedTraceId(matchingStageTrace.trace_id);
          return;
        }
      }
      setSelectedTraceId(target.document.traces[0].trace_id);
    } else {
      setSelectedTraceId(null);
    }
  };

  // When user clicks a stage in the pipeline progression ribbon
  const handleSelectStageFilter = (stage: string | null) => {
    setSelectedStageFilter(stage);
    if (stage) {
      const stageTraces = traces.filter((t) => t.stage === stage);
      if (stageTraces.length > 0) {
        const currentInStage = stageTraces.some((t) => t.trace_id === selectedTraceId);
        if (!currentInStage) {
          setSelectedTraceId(stageTraces[0].trace_id);
        }
      }
    }
  };

  // Load traces from API for a project with smart state retention
  const loadTracesFromBackend = useCallback(async (projectPath?: string) => {
    setIsSyncing(true);
    try {
      const res = await fetchProjectTraces(projectPath);
      if (res && res.chapters.length > 0) {
        setChapters(res.chapters);

        const currentChapterId = selectedChapterIdRef.current;
        const currentTraceId = selectedTraceIdRef.current;
        const currentStageFilter = selectedStageFilterRef.current;

        let targetChapter = res.chapters.find((c) => c.id === currentChapterId);
        if (!targetChapter) {
          targetChapter = res.chapters[0];
          setSelectedChapterId(targetChapter.id);
        }

        const targetTraces = targetChapter.document.traces || [];
        const traceStillExists = targetTraces.some((t) => t.trace_id === currentTraceId);
        const currentTraceObj = targetTraces.find((t) => t.trace_id === currentTraceId);

        if (traceStillExists) {
          if (currentStageFilter && currentTraceObj && currentTraceObj.stage !== currentStageFilter) {
            const matchingStageTrace = targetTraces.find((t) => t.stage === currentStageFilter);
            if (matchingStageTrace) {
              setSelectedTraceId(matchingStageTrace.trace_id);
              return;
            }
          }
        } else {
          if (currentStageFilter) {
            const matchingStageTrace = targetTraces.find((t) => t.stage === currentStageFilter);
            if (matchingStageTrace) {
              setSelectedTraceId(matchingStageTrace.trace_id);
              return;
            }
          }
          setSelectedTraceId(targetTraces[0]?.trace_id || null);
        }
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

        const activeRes = await fetchActiveProject();
        if (activeRes) {
          setActiveProject(activeRes.active_project);
          setProjects(activeRes.projects);
          if (activeRes.projects_dir) {
            const dirParts = activeRes.projects_dir.split(/[/\\]/);
            setProjectsDirName(dirParts[dirParts.length - 1] || 'project');
          }
        }

        if (projectChanged) {
          triggerToast(`(=^･ω･^=) Connected to project: ${syncState.active_project_title || 'Novel'}`);
        }

        await loadTracesFromBackend(syncState.active_project_path || undefined);
      }
    } catch {
      // Backend unavailable or offline
    }
  }, [loadTracesFromBackend]);

  // Initial mount
  useEffect(() => {
    const init = async () => {
      const activeRes = await fetchActiveProject();
      if (activeRes && activeRes.active_project) {
        setActiveProject(activeRes.active_project);
        setProjects(activeRes.projects);
        if (activeRes.projects_dir) {
          const dirParts = activeRes.projects_dir.split(/[/\\]/);
          setProjectsDirName(dirParts[dirParts.length - 1] || 'project');
        }
        lastSyncRef.current = {
          active_project_path: activeRes.active_project.path,
          active_project_title: activeRes.active_project.title,
          traces_count: activeRes.active_project.trace_count,
          latest_trace_mtime: activeRes.active_project.latest_trace_mtime,
        };
        await loadTracesFromBackend(activeRes.active_project.path);
      }
    };
    init();
  }, [loadTracesFromBackend]);

  // Handle project created via modal
  const handleProjectCreated = async (created: ProjectMeta) => {
    setActiveProject(created);
    await syncWithBackend(true);
    triggerToast(`(=^･ω･^=) Created and switched to: ${created.title}!`);
  };

  // Background sync polling (every 3s)
  useEffect(() => {
    if (!autoSync) return;
    const interval = setInterval(() => {
      syncWithBackend(false);
    }, 3000);
    return () => clearInterval(interval);
  }, [autoSync, syncWithBackend]);

  // Switch project
  const handleSwitchProject = async (targetPath: string) => {
    const matched = projects.find(
      (p) => p.path.replace(/\\/g, '/').toLowerCase() === targetPath.replace(/\\/g, '/').toLowerCase()
    );
    if (matched) {
      setActiveProject(matched);
    }
    const ok = await switchActiveProject(targetPath);
    if (ok) {
      await syncWithBackend(true);
      triggerToast(`Switched active project!`);
    } else {
      setErrorMessage(`Failed to switch project to ${targetPath}`);
    }
  };

  // Open directory via File System Access API
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

  // Load from file input
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

  // Drag-and-drop listener for Traces view
  useEffect(() => {
    const handleDragOver = (e: DragEvent) => {
      e.preventDefault();
      if (activeWorkspace === 'traces') setIsDraggingOver(true);
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
      if (activeWorkspace === 'traces' && e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
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
  }, [activeWorkspace]);

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-100 overflow-hidden font-sans relative">
      {/* Top Navigation */}
      <Navbar
        activeTab={activeWorkspace}
        onSelectTab={setActiveWorkspace}
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
        onOpenNewProjectModal={() => setIsNewProjectModalOpen(true)}
        autoSync={autoSync}
        onToggleAutoSync={() => setAutoSync(!autoSync)}
        isSyncing={isSyncing}
        onManualSync={() => syncWithBackend(true)}
      />

      {/* Sync Toast */}
      {syncToast && (
        <div className="fixed top-20 right-6 z-50 bg-indigo-900/90 text-indigo-100 border border-indigo-500/50 backdrop-blur px-4 py-2 rounded-xl text-xs font-medium shadow-xl flex items-center gap-2 animate-fade-in pointer-events-none">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{syncToast}</span>
        </div>
      )}

      {/* Error Banner */}
      {errorMessage && (
        <div className="bg-red-500/20 border-b border-red-500/30 px-4 py-2 text-red-300 text-xs flex items-center justify-between shrink-0">
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

      {/* Workspace Body */}
      <div className="flex-1 overflow-hidden">
        {activeWorkspace === 'studio' ? (
          <StudioView
            key={activeProject?.path || 'studio'}
            activeProjectPath={activeProject?.path || null}
            activeProjectTitle={activeProject?.title || null}
            onNavigateToReader={(chapterNum) => {
              setReaderChapterNum(chapterNum);
              setActiveWorkspace('reader');
            }}
            logs={logs}
          />
        ) : activeWorkspace === 'reader' ? (
          <ReaderView
            key={activeProject?.path || 'reader'}
            activeProjectPath={activeProject?.path || null}
            initialChapterNum={readerChapterNum}
            onBackToStudio={() => setActiveWorkspace('studio')}
          />
        ) : activeWorkspace === 'bible' ? (
          <BibleView
            key={activeProject?.path || 'bible'}
            activeProjectPath={activeProject?.path || null}
            activeProjectTitle={activeProject?.title || null}
          />
        ) : activeWorkspace === 'settings' ? (
          <SettingsView
            key={activeProject?.path || 'settings'}
            activeProjectPath={activeProject?.path || null}
            activeProjectTitle={activeProject?.title || null}
          />
        ) : (
          /* TRACES WORKSPACE */
          <div className="flex flex-col h-full overflow-hidden">
            <StagePipeline
              traces={traces}
              selectedStageFilter={selectedStageFilter}
              onSelectStageFilter={handleSelectStageFilter}
            />
            <div className="flex-1 flex overflow-hidden">
              <TraceTimeline
                traces={traces}
                selectedTraceId={selectedTraceId}
                onSelectTrace={setSelectedTraceId}
                selectedStageFilter={selectedStageFilter}
              />
              {currentTrace && currentChapter ? (
                <TraceDetail
                  trace={currentTrace}
                  chapterDoc={currentChapter.document}
                  activeTab={activeDetailTab}
                  onTabChange={setActiveDetailTab}
                />
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center p-8 text-slate-500 text-sm space-y-3">
                  <p>No traces recorded for this chapter yet.</p>
                  <button
                    onClick={handleLoadDemo}
                    className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Load Demo Traces</span>
                  </button>
                </div>
              )}
            </div>
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

      {/* New Project Modal */}
      <NewProjectModal
        isOpen={isNewProjectModalOpen}
        onClose={() => setIsNewProjectModalOpen(false)}
        onProjectCreated={handleProjectCreated}
        projectsDirName={projectsDirName}
      />
    </div>
  );
};
