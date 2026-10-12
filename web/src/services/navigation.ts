import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import type { SetStateAction } from 'react';
import type { WorkspaceTab } from '../types/dashboard';

export interface WorkspaceRoute {
  workspace: WorkspaceTab;
  project?: string;
  chapter?: number;
  folder?: string;
  trace?: string;
  mode?: 'chapter-traces' | 'project-analytics';
  stage?: string;
  detail?: 'prompts' | 'output' | 'diff' | 'analytics' | 'raw';
  section?: string;
}

const workspaces = ['studio', 'reader', 'traces', 'bible', 'settings'];
const bibleSections = ['characters', 'visualizer', 'glossary', 'memory', 'raw'];
const settingsSections = ['global', 'updates', 'logs', 'all', 'general', 'models', 'review', 'chunking', 'memory', 'rag', 'safety', 'ratelimit', 'paths'];
const stages = ['extraction', 'drafting', 'critique', 'polishing', 'chronicling'];
const details = ['prompts', 'output', 'diff', 'analytics', 'raw'];
const memory = new Map<string, string>();
const listeners = new Set<() => void>();
let revision = 0;
function notifyNavigation(): void {
  revision++;
  listeners.forEach((notify) => notify());
}
window.addEventListener('popstate', notifyNavigation);
export const getNavigationRevision = () => revision;

function readSession(key: string): string | null {
  try { return sessionStorage.getItem(key) ?? memory.get(key) ?? null; }
  catch { return memory.get(key) ?? null; }
}

function writeSession(key: string, value: string): void {
  memory.set(key, value);
  try { sessionStorage.setItem(key, value); } catch { /* Memory still retains this visit. */ }
}

export function parseRoute(url: string): WorkspaceRoute {
  const parsed = new URL(url, window.location.href);
  const workspace = parsed.pathname.replace(/^\/|\/$/g, '');
  const route: WorkspaceRoute = { workspace: workspaces.includes(workspace) ? workspace as WorkspaceTab : 'studio' };
  const params = parsed.searchParams;
  const project = params.get('project');
  if (project?.trim()) route.project = project;
  if (['studio', 'reader', 'traces'].includes(route.workspace)) {
    const chapter = params.get('chapter');
    if (chapter && /^\d+$/.test(chapter) && Number.isSafeInteger(Number(chapter)) && Number(chapter) > 0) {
      route.chapter = Number(chapter);
      const folder = params.get('folder');
      if (folder) route.folder = folder;
    }
  }
  if (route.workspace === 'traces') {
    if (params.get('trace')) route.trace = params.get('trace')!;
    if (['project-analytics', 'chapter-traces'].includes(params.get('mode') || '')) route.mode = params.get('mode') as WorkspaceRoute['mode'];
    if (stages.includes(params.get('stage') || '')) route.stage = params.get('stage')!;
    if (details.includes(params.get('detail') || '')) route.detail = params.get('detail') as WorkspaceRoute['detail'];
  }
  const sections = route.workspace === 'bible' ? bibleSections : route.workspace === 'settings' ? settingsSections : [];
  if (sections.includes(params.get('section') || '')) route.section = params.get('section')!;
  return route;
}

export function routeUrl(route: WorkspaceRoute): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(route)) {
    if (key !== 'workspace' && value !== undefined && value !== '' && value !== null) params.set(key, String(value));
  }
  // Round-trip once to discard parameters that do not apply to this workspace.
  const clean = parseRoute(`/${route.workspace}?${params}`);
  const result = new URLSearchParams();
  for (const [key, value] of Object.entries(clean)) if (key !== 'workspace') result.set(key, String(value));
  return `/${clean.workspace}${result.size ? `?${result}` : ''}`;
}

function snapshotKey(project: string | undefined, workspace: WorkspaceTab): string {
  return `nousetsu_navigation:v1:${project || ''}:${workspace}`;
}

export function getRoute(): WorkspaceRoute { return parseRoute(window.location.href); }

export function navigateRoute(route: WorkspaceRoute, replace = false): void {
  const url = routeUrl(route);
  writeSession(snapshotKey(route.project, route.workspace), url);
  if (window.location.pathname + window.location.search === url) return;
  window.history[replace ? 'replaceState' : 'pushState'](null, '', url);
  notifyNavigation();
}

export function patchRoute(update: Partial<WorkspaceRoute>, replace = false): void {
  navigateRoute({ ...getRoute(), ...update }, replace);
}

export function navigateWorkspace(workspace: WorkspaceTab, project?: string, replace = false): void {
  const saved = readSession(snapshotKey(project, workspace));
  navigateRoute({ ...(saved ? parseRoute(saved) : {}), workspace, project }, replace);
}

function subscribe(notify: () => void): () => void {
  listeners.add(notify);
  return () => { listeners.delete(notify); };
}

export function useWorkspaceRoute(): WorkspaceRoute {
  const url = useSyncExternalStore(subscribe, () => window.location.pathname + window.location.search);
  const route = useMemo(() => {
    const parsed = parseRoute(url);
    const saved = readSession(snapshotKey(parsed.project, parsed.workspace));
    // A bare workspace URL resumes its last selection; an explicit selection wins.
    return Object.keys(parsed).every((key) => key === 'workspace' || key === 'project') && saved
      ? { ...parseRoute(saved), ...parsed } : parsed;
  }, [url]);
  useEffect(() => { navigateRoute(route, true); }, [route]);
  return route;
}

// Persist only explicitly selected display state; callers must never pass form data.
export function useSessionState<T>(project: string | null, workspace: WorkspaceTab, name: string, initial: T) {
  const key = `${snapshotKey(project || undefined, workspace)}:${name}`;
  const restore = () => {
    try {
      const raw = readSession(key);
      const saved: unknown = raw ? JSON.parse(raw) : initial;
      if (typeof saved === typeof initial && (initial === null || typeof initial !== 'object'
        || (saved !== null && Array.isArray(saved) === Array.isArray(initial)))) return saved as T;
    } catch { /* Corrupt snapshots use the default. */ }
    return initial;
  };
  const [record, setRecord] = useState(() => ({ key, value: restore() }));
  let value = record.value;
  if (record.key !== key) {
    value = restore();
    setRecord({ key, value });
  }
  const setValue = useCallback((update: SetStateAction<T>) => {
    setRecord((current) => ({ key, value: typeof update === 'function'
      ? (update as (previous: T) => T)(current.value) : update }));
  }, [key]);
  useEffect(() => { writeSession(key, JSON.stringify(value)); }, [key, value]);
  return [value, setValue] as const;
}
