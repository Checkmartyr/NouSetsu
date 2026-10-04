import React, { useState, useEffect, useCallback, useRef } from 'react';
import { LoadedChapter, ProjectMeta, SyncState } from './types/trace';
import { ChapterItem, WorkspaceTab } from './types/dashboard';
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
import { ProjectTokenAnalytics } from './components/ProjectTokenAnalytics';
import { StudioView } from './components/StudioView';
import { ReaderView } from './components/ReaderView';
import { BibleView } from './components/BibleView';
import { SettingsView } from './components/SettingsView';
import { NewProjectModal } from './components/NewProjectModal';
import { StartupLoadingScreen } from './components/StartupLoadingScreen';
import { UploadCloud, AlertCircle, CheckCircle2 } from 'lucide-react';

export const App: React.FC = () => {
  // Startup Readiness State
  const [isAppReady, setIsAppReady] = useState(false);
  const [primedChapters, setPrimedChapters] = useState<ChapterItem[]>([]);

  // Navigation & Workspace State
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceTab>('studio');
  const [readerChapterNum, setReaderChapterNum] = useState<number | null>(null);
  const [readerFolder, setReaderFolder] = useState<string | null>(null);
  const [traceViewMode, setTraceViewMode] = useState<'chapter-traces' | 'project-analytics'>('chapter-traces');

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
  const [mobileTraceView, setMobileTraceView] = useState<'timeline' | 'detail'>('detail');
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Synchronized refs to avoid stale closure during async polling
  const selectedChapterIdRef = useRef<string | null>(selectedChapterId);
  const selectedTraceIdRef = useRef<string | null>(selectedTraceId);
  const selectedStageFilterRef = useRef<string | null>(selectedStageFilter);
  const chaptersRef = useRef<LoadedChapter[]>(chapters);
  const lastLoadedProjectPathRef = useRef<string | null>(null);

  useEffect(() => {
    selectedChapterIdRef.current = selectedChapterId;
  }, [selectedChapterId]);

  useEffect(() => {
    selectedTraceIdRef.current = selectedTraceId;
  }, [selectedTraceId]);

  useEffect(() => {
    selectedStageFilterRef.current = selectedStageFilter;
  }, [selectedStageFilter]);

  useEffect(() => {
    chaptersRef.current = chapters;
  }, [chapters]);

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

  // Group chapters by volume / folder for navigation inside Traces view
  const groupedChapters = React.useMemo(() => {
    return chapters.reduce<Record<string, LoadedChapter[]>>((acc, ch) => {
      const group = ch.folder || 'Root (Main Traces)';
      if (!acc[group]) acc[group] = [];
      acc[group].push(ch);
      return acc;
    }, {});
  }, [chapters]);

  // Helper to show transient sync toasts
  const triggerToast = (msg: string) => {
    setSyncToast(msg);
    setTimeout(() => setSyncToast(null), 4000);
  };

  // Load traces from API for a project with smart state retention
  const loadTracesFromBackend = useCallback(async (projectPath?: string, chapterNumToRefresh?: number) => {
    const targetPath = projectPath || activeProject?.path;
    setIsSyncing(true);
    try {
      const currentChapterId = selectedChapterIdRef.current;
      const currentCh = chaptersRef.current.find((c) => c.id === currentChapterId);
      const activeChapterNum = chapterNumToRefresh !== undefined ? chapterNumToRefresh : currentCh?.chapterNum;

      const res = await fetchProjectTraces(targetPath, undefined, undefined, false, activeChapterNum);
      if (res && res.chapters.length > 0) {
        const prevChapters = chaptersRef.current;
        const prevMap = new Map(prevChapters.map((c) => [c.id, c]));
        const isSameProject = targetPath && lastLoadedProjectPathRef.current === targetPath;
        lastLoadedProjectPathRef.current = targetPath || null;

        const mergedChapters: LoadedChapter[] = !isSameProject
          ? res.chapters
          : res.chapters.map((newCh) => {
              const prevCh = prevMap.get(newCh.id);
              if (!prevCh) return newCh;

              // If this chapter was explicitly refreshed and new payload has traces, prefer the new traces!
              if (
                chapterNumToRefresh !== undefined &&
                newCh.chapterNum === chapterNumToRefresh &&
                newCh.document?.traces &&
                newCh.document.traces.length > 0
              ) {
                return newCh;
              }

              const newTraces = newCh.document?.traces;
              const prevTraces = prevCh.document?.traces;

              // If incoming payload has stripped/empty traces but we already had traces in memory, keep them!
              if ((!newTraces || newTraces.length === 0) && prevTraces && prevTraces.length > 0) {
                return {
                  ...newCh,
                  document: {
                    ...newCh.document,
                    traces: prevTraces,
                  },
                };
              }
              return newCh;
            });

        setChapters(mergedChapters);

        // After state update, check target chapter in merged list
        let targetChapter = mergedChapters.find((c) => c.id === currentChapterId);
        if (!targetChapter) {
          targetChapter = mergedChapters[0];
          if (targetChapter) {
            setSelectedChapterId(targetChapter.id);
          }
        }

        // If target chapter traces are still missing, lazy-load them on-demand
        if (targetChapter && (!targetChapter.document.traces || targetChapter.document.traces.length === 0)) {
          try {
            const lazyRes = await fetchProjectTraces(
              targetPath,
              targetChapter.chapterNum,
              targetChapter.folder || undefined
            );
            if (lazyRes && lazyRes.chapters && lazyRes.chapters.length > 0) {
              const loadedCh = lazyRes.chapters.find((c) => c.id === targetChapter!.id) || lazyRes.chapters[0];
              if (loadedCh && loadedCh.document?.traces && loadedCh.document.traces.length > 0) {
                targetChapter = { ...targetChapter, document: loadedCh.document };
                setChapters((prev) => prev.map((c) => (c.id === targetChapter!.id ? targetChapter! : c)));
              }
            }
          } catch (lazyErr) {
            console.warn('Could not lazy-load traces for target chapter in loadTracesFromBackend:', lazyErr);
          }
        }

        const targetTraces = targetChapter?.document.traces || [];
        const currentTraceId = selectedTraceIdRef.current;
        const currentStageFilter = selectedStageFilterRef.current;

        if (targetTraces.length > 0) {
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
            // Trace still exists and matches stage filter (or no filter) - keep it!
            return;
          } else {
            if (currentStageFilter) {
              const matchingStageTrace = targetTraces.find((t) => t.stage === currentStageFilter);
              if (matchingStageTrace) {
                setSelectedTraceId(matchingStageTrace.trace_id);
                return;
              }
            }
            setSelectedTraceId(targetTraces[0].trace_id);
          }
        } else {
          setSelectedTraceId(null);
        }
      }
    } catch (err: any) {
      console.warn('Could not load traces from backend:', err);
    } finally {
      setIsSyncing(false);
    }
  }, [activeProject?.path]);

  // If chapter changes, preserve active stage filter or select first trace (with on-demand trace fetching)
  const handleSelectChapter = async (id: string) => {
    setSelectedChapterId(id);
    let target = chaptersRef.current.find((c) => c.id === id) || chapters.find((c) => c.id === id);
    if (!target) return;

    if (!target.document.traces || target.document.traces.length === 0) {
      try {
        const res = await fetchProjectTraces(activeProject?.path, target.chapterNum, target.folder || undefined);
        if (res && res.chapters && res.chapters.length > 0) {
          const loadedCh = res.chapters.find((c) => c.id === id) || res.chapters[0];
          if (loadedCh && loadedCh.document?.traces && loadedCh.document.traces.length > 0) {
            target = { ...target, document: loadedCh.document };
            setChapters((prev) => prev.map((c) => (c.id === id ? target! : c)));
          }
        }
      } catch (err) {
        console.warn('Could not lazy-load chapter traces:', err);
      }
    }

    if (target && target.document.traces && target.document.traces.length > 0) {
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
        const finishedCh = typeof data.chapter_num === 'number' ? data.chapter_num : undefined;
        logMsg = `[${ts}] ✓ Finished Ch.${data.chapter_num ?? '?'}`;
        // Automatically reload traces on chapter completion with targeted refresh for finished chapter
        if (activeProject?.path) {
          loadTracesFromBackend(activeProject.path, finishedCh);
        }
      } else if (typeof data === 'object' && data.message) {
        logMsg = `[${ts}] [${event}] ${data.message}`;
      }

      setLogs((prev) => [...prev.slice(-300), logMsg]);
    });

    return () => {
      disconnect();
    };
  }, [activeProject, loadTracesFromBackend]);

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

  // Handle successful startup service verification
  const handleStartupReady = useCallback(
    async (data: {
      activeProject: ProjectMeta | null;
      projects: ProjectMeta[];
      chapters: ChapterItem[];
    }) => {
      if (data.activeProject) {
        setActiveProject(data.activeProject);
        lastSyncRef.current = {
          active_project_path: data.activeProject.path,
          active_project_title: data.activeProject.title,
          traces_count: data.activeProject.trace_count,
          latest_trace_mtime: data.activeProject.latest_trace_mtime,
        };
        await loadTracesFromBackend(data.activeProject.path);
      }
      if (data.projects && data.projects.length > 0) {
        setProjects(data.projects);
      }
      if (data.chapters && data.chapters.length > 0) {
        setPrimedChapters(data.chapters);
      }
      setIsAppReady(true);
    },
    [loadTracesFromBackend]
  );

  // Handle project created via modal
  const handleProjectCreated = async (created: ProjectMeta) => {
    setActiveProject(created);
    await syncWithBackend(true);
    triggerToast(`(=^･ω･^=) Created and switched to: ${created.title}!`);
  };

  // Background sync polling (every 3s, only active after startup verification)
  useEffect(() => {
    if (!autoSync || !isAppReady) return;
    const interval = setInterval(() => {
      syncWithBackend(false);
    }, 3000);
    return () => clearInterval(interval);
  }, [autoSync, isAppReady, syncWithBackend]);

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

  if (!isAppReady) {
    return <StartupLoadingScreen onReady={handleStartupReady} />;
  }

  return (
    <div className="flex flex-col h-screen bg-[#2b2622] text-[#f7f5f0] overflow-hidden font-sans relative">
      {/* Top Navigation */}
      <Navbar
        activeTab={activeWorkspace}
        onSelectTab={setActiveWorkspace}
        onOpenDirectory={handleOpenDirectory}
        onLoadFiles={handleLoadFiles}
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
        <div className="fixed top-16 right-6 z-50 bg-[#383330] text-[#f7f5f0] border border-[#3f3a36] px-3.5 py-2 rounded-[4px] text-xs font-medium shadow-md flex items-center gap-2 animate-fade-in pointer-events-none">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{syncToast}</span>
        </div>
      )}

      {/* Error Banner */}
      {errorMessage && (
        <div className="bg-rose-950/40 border-b border-rose-900/50 px-4 py-2 text-rose-200 text-xs flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-[#aea69c] hover:text-[#f7f5f0] cursor-pointer"
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
            onNavigateToReader={(chapterNum, folder) => {
              setReaderChapterNum(chapterNum);
              setReaderFolder(folder || null);
              setActiveWorkspace('reader');
            }}
            logs={logs}
            initialChapters={primedChapters}
          />
        ) : activeWorkspace === 'reader' ? (
          <ReaderView
            key={activeProject?.path || 'reader'}
            activeProjectPath={activeProject?.path || null}
            initialChapterNum={readerChapterNum}
            initialFolder={readerFolder}
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
            onProjectUpdated={() => syncWithBackend(true)}
          />
        ) : (
          /* TRACES WORKSPACE */
          <div className="flex flex-col h-full overflow-hidden">
            <div className="flex items-center justify-between border-b border-[#3f3a36] bg-[#2b2622] px-3 py-2 sm:px-4 gap-2">
              <div role="group" aria-label="Traces view" className="flex items-center gap-1 rounded-[4px] border border-[#3f3a36] bg-[#24201d] p-0.5 shrink-0">
                <button
                  type="button"
                  aria-pressed={traceViewMode === 'chapter-traces'}
                  onClick={() => setTraceViewMode('chapter-traces')}
                  className={`rounded-[3px] px-3 py-1.5 text-xs transition-colors cursor-pointer ${traceViewMode === 'chapter-traces' ? 'bg-[#383330] text-[#f7f5f0] border border-[#544d47] font-medium' : 'text-[#c9c0ad] hover:bg-[#383330]/50 hover:text-[#f7f5f0]'}`}
                >
                  Chapter Traces
                </button>
                <button
                  type="button"
                  aria-pressed={traceViewMode === 'project-analytics'}
                  onClick={() => setTraceViewMode('project-analytics')}
                  className={`rounded-[3px] px-3 py-1.5 text-xs transition-colors cursor-pointer ${traceViewMode === 'project-analytics' ? 'bg-[#383330] text-[#f7f5f0] border border-[#544d47] font-medium' : 'text-[#c9c0ad] hover:bg-[#383330]/50 hover:text-[#f7f5f0]'}`}
                >
                  Project Analytics
                </button>
              </div>

              {/* Chapter selector inside Chapter Traces view */}
              {traceViewMode === 'chapter-traces' && chapters.length > 0 && (
                <div className="flex items-center gap-2 max-w-[280px] sm:max-w-xs shrink-0">
                  <label htmlFor="trace-chapter-selector" className="text-xs text-[#aea69c] font-medium hidden sm:inline whitespace-nowrap">
                    Chapter:
                  </label>
                  <select
                    id="trace-chapter-selector"
                    value={selectedChapterId || ''}
                    onChange={(e) => handleSelectChapter(e.target.value)}
                    aria-label="Select chapter trace"
                    className="w-full bg-[#383330] border border-[#3f3a36] hover:border-[#544d47] rounded-[3px] px-2.5 py-1 text-xs text-[#f7f5f0] focus:outline-none focus:border-[#dad2c1] truncate cursor-pointer font-mono transition-colors"
                  >
                    {Object.entries(groupedChapters).map(([group, groupList]) => (
                      <optgroup label={`📁 ${group}`} key={group} className="bg-[#2b2622] text-[#c9c0ad] font-semibold">
                        {groupList.map((ch) => (
                          <option key={ch.id} value={ch.id} className="bg-[#383330] text-[#f7f5f0] py-1 font-normal">
                            Ch.{ch.chapterNum} ({ch.document.total_interactions} acts)
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </div>
              )}

              {traceViewMode === 'project-analytics' && activeProject && (
                <span className="hidden sm:block truncate text-xs text-[#aea69c]">{activeProject.title}</span>
              )}
            </div>

            {traceViewMode === 'project-analytics' ? (
              <ProjectTokenAnalytics
                key={activeProject?.path || 'project-token-analytics'}
                projectPath={activeProject?.path || null}
                projectTitle={activeProject?.title || null}
                refreshKey={`${activeProject?.latest_trace_mtime || 0}:${activeProject?.trace_count || 0}`}
              />
            ) : (
              <>
                <StagePipeline
                  traces={traces}
                  selectedStageFilter={selectedStageFilter}
                  onSelectStageFilter={handleSelectStageFilter}
                />

                {/* Mobile View Toggle Bar (Only visible on screens < lg) */}
                <div className="lg:hidden flex items-center justify-between px-3 py-1.5 bg-[#2b2622] border-b border-[#3f3a36]">
                  <span className="text-[11px] font-mono text-[#aea69c]">Trace View:</span>
                  <div className="flex items-center gap-1 bg-[#383330] p-0.5 rounded-[3px] border border-[#3f3a36]">
                    <button
                      type="button"
                      onClick={() => setMobileTraceView('timeline')}
                      className={`px-2 py-0.5 text-xs rounded-[2px] transition-colors cursor-pointer ${
                        mobileTraceView === 'timeline'
                          ? 'bg-[#f7f5f0] text-[#2b2622] font-medium'
                          : 'text-[#c9c0ad] hover:text-[#f7f5f0]'
                      }`}
                    >
                      Timeline ({traces.length})
                    </button>
                    <button
                      type="button"
                      onClick={() => setMobileTraceView('detail')}
                      className={`px-2 py-0.5 text-xs rounded-[2px] transition-colors cursor-pointer ${
                        mobileTraceView === 'detail'
                          ? 'bg-[#f7f5f0] text-[#2b2622] font-medium'
                          : 'text-[#c9c0ad] hover:text-[#f7f5f0]'
                      }`}
                    >
                      Detail
                    </button>
                  </div>
                </div>

                <div className="flex-1 flex overflow-hidden">
                  <div className={`${mobileTraceView === 'timeline' ? 'block' : 'hidden'} lg:block w-full lg:w-80 md:w-96 shrink-0 h-full overflow-hidden`}>
                    <TraceTimeline
                      traces={traces}
                      selectedTraceId={selectedTraceId}
                      onSelectTrace={(id) => {
                        handleSelectChapter(selectedChapterId || '');
                        setSelectedTraceId(id);
                        setMobileTraceView('detail');
                      }}
                      selectedStageFilter={selectedStageFilter}
                    />
                  </div>
                  <div className={`${mobileTraceView === 'detail' ? 'flex' : 'hidden'} lg:flex flex-1 flex-col h-full overflow-hidden min-w-0`}>
                    {currentTrace && currentChapter ? (
                      <TraceDetail
                        trace={currentTrace}
                        chapterDoc={currentChapter.document}
                        activeTab={activeDetailTab}
                        onTabChange={setActiveDetailTab}
                      />
                    ) : (
                      <div className="flex-1 flex flex-col items-center justify-center p-8 text-[#aea69c] text-xs space-y-2">
                        <p>No traces recorded for this chapter yet.</p>
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Drag & Drop Overlay */}
      {isDraggingOver && (
        <div className="fixed inset-0 z-50 bg-[#2b2622]/90 backdrop-blur-sm flex flex-col items-center justify-center pointer-events-none border-2 border-dashed border-[#c9c0ad] m-4 rounded-[6px]">
          <UploadCloud className="w-12 h-12 text-[#f7f5f0] animate-bounce mb-3" />
          <h3 className="text-base font-normal tracking-tight text-[#f7f5f0] mb-1">
            Drop Trace Files Here (=^･ω･^=)
          </h3>
          <p className="text-xs text-[#aea69c]">
            Drop chapter_XXXX.json or chapter_XXXX.jsonl to inspect traces
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
