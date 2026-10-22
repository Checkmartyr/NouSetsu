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
import { getNavigationRevision, getRoute, navigateRoute, navigateWorkspace, openSetup, consumeSetupReturn, patchRoute, useSessionState, useWorkspaceRoute, WorkspaceRoute } from './services/navigation';
import type { StartupData } from './services/serviceChecker';
import { SetupView } from './components/SetupView';
import { OpenProjectDialog } from './components/OpenProjectDialog';
import { SetupSnapshot, setupRequest } from './services/setupApi';

const sameProject = (a?: string | null, b?: string | null) =>
  (a || '').replace(/\\/g, '/').toLowerCase() === (b || '').replace(/\\/g, '/').toLowerCase();

export const App: React.FC = () => {
  const route = useWorkspaceRoute();
  const activeWorkspace = route.workspace;
  const [isAppReady, setIsAppReady] = useState(false);
  const [setupSnapshot, setSetupSnapshot] = useState<SetupSnapshot | null>(null);
  const [setupDismissed, setSetupDismissed] = useState(false);
  const [openProjectDialog, setOpenProjectDialog] = useState(false);
  const setupReturn = useRef<WorkspaceRoute | null>(null);
  useEffect(() => {
    const connect = (event: Event) => {
      const selected = (event as CustomEvent<{ chapter?: string | number; folder?: string }>).detail;
      const chapter = Number(selected?.chapter);
      setupReturn.current = { ...getRoute(), ...(Number.isSafeInteger(chapter) && chapter > 0 ? { chapter, folder: selected?.folder } : {}) };
      openSetup(setupReturn.current);
    };
    window.addEventListener('nousetsu:connect-ai', connect);
    return () => window.removeEventListener('nousetsu:connect-ai', connect);
  }, []);
  const [primedChapters, setPrimedChapters] = useState<ChapterItem[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [chapters, setChapters] = useState<LoadedChapter[]>([{
    id: 'demo_chapter_1', fileName: 'chapter_0001.json', folder: 'Villainess_05',
    chapterNum: 1, document: DEMO_CHAPTER_TRACE,
  }]);
  const [activeProject, setActiveProject] = useState<ProjectMeta | null>(null);
  const [projects, setProjects] = useState<ProjectMeta[]>([]);
  const [projectsDirName, setProjectsDirName] = useState('project');
  const [isNewProjectModalOpen, setIsNewProjectModalOpen] = useState(false);
  const [autoSync, setAutoSync] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isSwitching, setIsSwitching] = useState(false);
  const [syncToast, setSyncToast] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [mobileTraceView, setMobileTraceView] = useSessionState<'timeline' | 'detail'>(activeProject?.path || null, 'traces', 'mobileView', 'detail');
  const projectRef = useRef<ProjectMeta | null>(null);
  const backendProjectRef = useRef<ProjectMeta | null>(null);
  const projectsRef = useRef<ProjectMeta[]>([]);
  const switchingRef = useRef(false);
  const traceGeneration = useRef(0);
  const localTracesRef = useRef(false);
  const lastSyncRef = useRef<SyncState | null>(null);
  const chaptersRef = useRef(chapters);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  chaptersRef.current = chapters;
  projectsRef.current = projects;

  const traceViewMode = route.mode || 'chapter-traces';
  const selectedStageFilter = route.stage || null;
  const activeDetailTab: DetailTab = route.detail || 'output';
  const setTraceViewMode = (mode: WorkspaceRoute['mode']) => patchRoute({ mode });
  const setActiveDetailTab = (detail: DetailTab) => patchRoute({ detail });
  const setSelectedTraceId = (trace: string | null) => patchRoute({ trace: trace || undefined });
  const currentChapter = chapters.find((ch) => ch.chapterNum === route.chapter && (ch.folder || null) === (route.folder || null)) || chapters[0];
  const selectedChapterId = currentChapter?.id || null;
  const traces = currentChapter?.document.traces || [];
  const currentTrace = traces.find((trace) => trace.trace_id === route.trace) || traces.find((trace) => !route.stage || trace.stage === route.stage) || traces[0];
  const selectedTraceId = currentTrace?.trace_id || null;
  const isFileSystemSupported = 'showDirectoryPicker' in window;
  const groupedChapters = React.useMemo(() => chapters.reduce<Record<string, LoadedChapter[]>>((acc, ch) => {
    (acc[ch.folder || 'Root (Main Traces)'] ||= []).push(ch);
    return acc;
  }, {}), [chapters]);

  const triggerToast = useCallback((message: string) => {
    clearTimeout(toastTimer.current);
    setSyncToast(message);
    toastTimer.current = setTimeout(() => setSyncToast(null), 4000);
  }, []);
  useEffect(() => () => clearTimeout(toastTimer.current), []);

  const applyProject = useCallback((project: ProjectMeta | null, roster: ChapterItem[] = []) => {
    if (!sameProject(projectRef.current?.path, project?.path)) {
      traceGeneration.current++;
      localTracesRef.current = false;
      setChapters([]);
      chaptersRef.current = [];
      setLogs([]);
    }
    projectRef.current = project;
    setActiveProject(project);
    setPrimedChapters(roster);
    lastSyncRef.current = project ? {
      active_project_path: project.path, active_project_title: project.title,
      traces_count: project.trace_count, latest_trace_mtime: project.latest_trace_mtime,
    } : null;
  }, []);

  const loadTracesFromBackend = useCallback(async (projectPath?: string, chapterNumToRefresh?: number) => {
    const targetPath = projectPath || projectRef.current?.path;
    if (!targetPath || switchingRef.current || localTracesRef.current) return;
    const generation = ++traceGeneration.current;
    const requested = getRoute();
    if (requested.project && !sameProject(requested.project, targetPath)) return;
    const valid = () => {
      const latest = getRoute();
      return generation === traceGeneration.current && sameProject(projectRef.current?.path, targetPath)
        && sameProject(latest.project, requested.project) && latest.chapter === requested.chapter
        && (latest.folder || null) === (requested.folder || null) && !switchingRef.current;
    };
    setIsSyncing(true);
    try {
      const res = await fetchProjectTraces(targetPath, undefined, undefined, false, chapterNumToRefresh ?? requested.chapter);
      if (!res || !valid()) return;
      const previous = new Map(chaptersRef.current.map((chapter) => [chapter.id, chapter]));
      const loaded = res.chapters.map((chapter) => {
        const cached = previous.get(chapter.id);
        return !chapter.document.traces.length && cached?.document.traces.length
          ? { ...chapter, document: cached.document } : chapter;
      });
      let target = loaded.find((chapter) => chapter.chapterNum === requested.chapter && (chapter.folder || null) === (requested.folder || null)) || loaded[0];
      let traceDetailsKnown = !target || Boolean(target.document.traces.length);
      if (target && !target.document.traces.length) {
        const lazy = await fetchProjectTraces(targetPath, target.chapterNum, target.folder || undefined);
        if (!valid()) return;
        const full = lazy?.chapters.find((chapter) => chapter.chapterNum === target!.chapterNum && (chapter.folder || null) === (target!.folder || null));
        if (full) {
          traceDetailsKnown = true;
          target = { ...target, document: full.document };
          const index = loaded.findIndex((chapter) => chapter.id === target!.id);
          loaded[index] = target;
        }
      }
      if (!valid()) return;
      setChapters(loaded);
      chaptersRef.current = loaded;
      const latest = getRoute();
      if (latest.workspace === 'traces') {
        const available = target?.document.traces || [];
        const selected = available.find((trace) => trace.trace_id === latest.trace && (!latest.stage || trace.stage === latest.stage))
          || available.find((trace) => !latest.stage || trace.stage === latest.stage) || available[0];
        if (target && traceDetailsKnown) patchRoute({
          chapter: target.chapterNum, folder: target.folder || undefined, trace: selected?.trace_id,
        }, true);
        else if (!target) patchRoute({ chapter: undefined, folder: undefined, trace: undefined }, true);
      }
    } finally {
      if (generation === traceGeneration.current) setIsSyncing(false);
    }
  }, []);

  const handleSelectChapter = (id: string) => {
    const target = chaptersRef.current.find((chapter) => chapter.id === id);
    if (target) patchRoute({ chapter: target.chapterNum, folder: target.folder || undefined, trace: undefined });
  };
  const handleSelectStageFilter = (stage: string | null) => {
    const target = traces.find((trace) => trace.trace_id === selectedTraceId && (!stage || trace.stage === stage))
      || traces.find((trace) => !stage || trace.stage === stage);
    patchRoute({ stage: stage || undefined, trace: target?.trace_id });
  };

  // Serialize POSTs: an old response must never leave the registry on an old destination.
  const reconcileProject = useCallback(async () => {
    if (switchingRef.current) return;
    switchingRef.current = true;
    setIsSwitching(true);
    traceGeneration.current++;
    try {
      while (true) {
        const desired = getRoute().project;
        if (!desired) { navigateWorkspace(getRoute().workspace, backendProjectRef.current?.path, true); break; }
        const matched = projectsRef.current.find((project) => sameProject(project.path, desired));
        if (!matched) {
          setErrorMessage('Requested project is not registered.');
          navigateWorkspace(getRoute().workspace, backendProjectRef.current?.path, true);
          break;
        }
        if (sameProject(backendProjectRef.current?.path, matched.path)) break;
        if (!await switchActiveProject(matched.path)) {
          if (!sameProject(getRoute().project, matched.path)) continue;
          setErrorMessage(`Failed to switch project to ${matched.title}`);
          navigateWorkspace(getRoute().workspace, backendProjectRef.current?.path, true);
          break;
        }
        backendProjectRef.current = matched;
        // The newest history destination is read after every response.
      }
      applyProject(backendProjectRef.current);
      if (backendProjectRef.current && getRoute().project !== backendProjectRef.current.path) patchRoute({ project: backendProjectRef.current.path }, true);
    } finally {
      switchingRef.current = false;
      setIsSwitching(false);
      setIsSyncing(false);
    }
    await loadTracesFromBackend(backendProjectRef.current?.path);
  }, [applyProject, loadTracesFromBackend]);

  useEffect(() => {
    if (!isAppReady) return;
    if (!sameProject(route.project, backendProjectRef.current?.path)) void reconcileProject();
    else if (!route.project && backendProjectRef.current) patchRoute({ project: backendProjectRef.current.path }, true);
  }, [isAppReady, route.project, reconcileProject]);

  useEffect(() => {
    if (isAppReady && !isSwitching && activeWorkspace === 'traces') void loadTracesFromBackend();
  }, [isAppReady, isSwitching, activeWorkspace, route.project, route.chapter, route.folder, loadTracesFromBackend]);

  // Route changes use refs rather than reopening the main event stream.
  useEffect(() => {
    if (!isAppReady) return;
    return connectSSE((event, data) => {
      const ts = new Date().toLocaleTimeString();
      let message = `[${ts}] ${event}`;
      if (event === 'stage_progress' && typeof data === 'object') {
        message = `[${ts}] Ch.${data.chapter_num ?? '?'}: [${data.stage}] ${data.message || ''}`;
      } else if (event === 'chapter_finished' && typeof data === 'object') {
        message = `[${ts}] ✓ Finished Ch.${data.chapter_num ?? '?'}`;
      } else if (typeof data === 'object' && data?.message) {
        message = `[${ts}] [${event}] ${data.message}`;
      }
      setLogs((prev) => [...prev.slice(-300), message]);
      if (event === 'chapter_finished') void loadTracesFromBackend(projectRef.current?.path, data?.chapter_num);
    });
  }, [isAppReady, loadTracesFromBackend]);

  const syncWithBackend = useCallback(async (force = false) => {
    if (switchingRef.current || !sameProject(getRoute().project, backendProjectRef.current?.path)) return;
    const startedAt = getNavigationRevision();
    const valid = () => !switchingRef.current && getNavigationRevision() === startedAt;
    try {
      const sync = await fetchSyncState();
      if (!sync || !valid()) return;
      const last = lastSyncRef.current;
      const changed = !sameProject(last?.active_project_path, sync.active_project_path);
      const updated = !last || last.latest_trace_mtime !== sync.latest_trace_mtime || last.traces_count !== sync.traces_count;
      if (!changed && !updated && !force) return;
      const registry = await fetchActiveProject();
      if (!registry || !valid()) return;
      setProjects(registry.projects);
      projectsRef.current = registry.projects;
      backendProjectRef.current = registry.active_project;
      if (registry.projects_dir) setProjectsDirName(registry.projects_dir.split(/[/\\]/).pop() || 'project');
      if (changed) {
        applyProject(registry.active_project);
        navigateWorkspace(getRoute().workspace, registry.active_project?.path, true);
        triggerToast(`Connected to project: ${registry.active_project?.title || 'Novel'}`);
      } else {
        projectRef.current = registry.active_project;
        setActiveProject(registry.active_project);
      }
      lastSyncRef.current = sync;
      await loadTracesFromBackend(registry.active_project?.path);
    } catch { /* Polling retries while offline. */ }
  }, [applyProject, loadTracesFromBackend, triggerToast]);

  const handleStartupReady = useCallback(async (data: StartupData) => {
    projectsRef.current = [...data.projects];
    if (data.activeProject && !projectsRef.current.some((project) => sameProject(project.path, data.activeProject?.path))) projectsRef.current.push(data.activeProject);
    setProjects(projectsRef.current);
    backendProjectRef.current = data.activeProject;
    applyProject(data.activeProject, data.chapters);
    if (data.projectsDir) setProjectsDirName(data.projectsDir.split(/[/\\]/).pop() || 'project');
    const incoming = getRoute();
    if (!incoming.project) {
      if (Object.keys(incoming).length === 1) navigateWorkspace(incoming.workspace, data.activeProject?.path, true);
      else patchRoute({ project: data.activeProject?.path }, true);
    }
    try {
      const setup = await setupRequest<SetupSnapshot>('');
      if (typeof setup.completed === 'boolean' && typeof setup.existing === 'boolean') {
        setSetupSnapshot(setup);
        if (!setup.completed && !setup.existing && getRoute().workspace !== 'setup') {
          setupReturn.current = getRoute();
          openSetup(setupReturn.current, true);
        }
      }
    } catch { /* Older backends and offline settings retain the existing workspace. */ }
    setIsAppReady(true);
  }, [applyProject]);

  const handleProjectCreated = async (created: ProjectMeta) => {
    backendProjectRef.current = created;
    const registered = [...projectsRef.current.filter((project) => !sameProject(project.path, created.path)), created];
    projectsRef.current = registered;
    setProjects(registered);
    applyProject(created);
    navigateWorkspace('studio', created.path, true);
    await syncWithBackend(true);
    triggerToast(`Created and switched to: ${created.title}!`);
  };

  useEffect(() => {
    if (!autoSync || !isAppReady) return;
    const interval = setInterval(() => { void syncWithBackend(); }, 3000);
    return () => clearInterval(interval);
  }, [autoSync, isAppReady, syncWithBackend]);

  const handleSwitchProject = (targetPath: string) => navigateWorkspace(getRoute().workspace, targetPath);

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
        localTracesRef.current = true;
        traceGeneration.current++;
        setIsSyncing(false);
        setChapters(loaded);
        chaptersRef.current = loaded;
        navigateRoute({ workspace: 'traces', project: activeProject?.path, chapter: loaded[0].chapterNum, folder: loaded[0].folder || undefined, trace: loaded[0].document.traces[0]?.trace_id });
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
        localTracesRef.current = true;
        traceGeneration.current++;
        setIsSyncing(false);
        setChapters(loaded);
        chaptersRef.current = loaded;
        navigateRoute({ workspace: 'traces', project: activeProject?.path, chapter: loaded[0].chapterNum, folder: loaded[0].folder || undefined, trace: loaded[0].document.traces[0]?.trace_id });
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

  if (activeWorkspace === 'setup') return <SetupView initial={setupSnapshot} onExit={(action) => {
    void setupRequest<SetupSnapshot>('').then(setSetupSnapshot).catch(() => {});
    setSetupDismissed(true);
    const restored = consumeSetupReturn();
    if (setupReturn.current || restored) navigateRoute(setupReturn.current || restored!);
    else navigateWorkspace('studio', activeProject?.path);
    setupReturn.current = null;
    if (action === 'create') setIsNewProjectModalOpen(true);
    if (action === 'open') setOpenProjectDialog(true);
  }} />;

  const handleSelectWorkspaceTab = (tab: WorkspaceTab) => navigateWorkspace(tab, activeProject?.path);

  return (
    <div className="flex flex-col h-screen bg-[#2b2622] text-[#f7f5f0] overflow-hidden font-sans relative">
      {/* Top Navigation */}
      <Navbar
        activeTab={activeWorkspace}
        onSelectTab={handleSelectWorkspaceTab}
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
        onManualSync={() => { localTracesRef.current = false; void syncWithBackend(true); }}
      />

      {/* Sync Toast */}
      {setupSnapshot?.existing && !setupSnapshot.completed && !setupDismissed && <div className="px-4 py-3 flex flex-wrap gap-3 items-center border-b border-[#544d47]">
        <span>{setupSnapshot.locale === 'th' ? 'ตรวจสอบการตั้งค่าด้วยขั้นตอนแนะนำ' : 'Review your installation with guided setup.'}</span>
        <button className="underline" onClick={() => { setupReturn.current = getRoute(); openSetup(); }}>{setupSnapshot.locale === 'th' ? 'เปิดการตั้งค่า' : 'Open setup'}</button>
        <button onClick={() => setSetupDismissed(true)}>{setupSnapshot.locale === 'th' ? 'ภายหลัง' : 'Later'}</button>
      </div>}
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
        {isSwitching || (route.project && !sameProject(route.project, activeProject?.path)) ? (
          <div className="p-6 text-xs text-[#aea69c]">Loading project...</div>
        ) : activeWorkspace === 'studio' ? (
          <StudioView
            key={activeProject?.path || 'studio'}
            activeProjectPath={activeProject?.path || null}
            activeProjectTitle={activeProject?.title || null}
            chapterNum={route.chapter}
            chapterFolder={route.folder}
            onChapterChange={(chapter, folder, replace) => patchRoute({ chapter, folder: folder || undefined }, replace)}
            onNavigateToReader={(chapter, folder) => navigateRoute({ workspace: 'reader', project: activeProject?.path, chapter, folder: folder || undefined })}
            logs={logs}
            initialChapters={primedChapters}
          />
        ) : activeWorkspace === 'reader' ? (
          <ReaderView
            key={activeProject?.path || 'reader'}
            activeProjectPath={activeProject?.path || null}
            initialChapterNum={route.chapter}
            initialFolder={route.folder}
            onChapterChange={(chapter, folder, replace) => patchRoute({ chapter, folder: folder || undefined }, replace)}
            onBackToStudio={() => navigateWorkspace('studio', activeProject?.path)}
          />
        ) : activeWorkspace === 'bible' ? (
          <BibleView
            section={route.section}
            onSectionChange={(section) => patchRoute({ section })}
            key={activeProject?.path || 'bible'}
            activeProjectPath={activeProject?.path || null}
            activeProjectTitle={activeProject?.title || null}
          />
        ) : activeWorkspace === 'settings' ? (
          <SettingsView
            section={route.section}
            onSectionChange={(section) => patchRoute({ section })}
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
      {openProjectDialog && <OpenProjectDialog locale={setupSnapshot?.locale || 'en'} onClose={() => setOpenProjectDialog(false)} onOpened={project => {
        backendProjectRef.current = project;
        projectsRef.current = [...projectsRef.current.filter(item => !sameProject(item.path, project.path)), project];
        setProjects(projectsRef.current); applyProject(project);
        navigateWorkspace('studio', project.path, true);
        void syncWithBackend(true);
      }} />}
      <NewProjectModal
        isOpen={isNewProjectModalOpen}
        onClose={() => setIsNewProjectModalOpen(false)}
        onProjectCreated={handleProjectCreated}
        projectsDirName={projectsDirName}
      />
    </div>
  );
};
