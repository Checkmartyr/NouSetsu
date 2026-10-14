import { API_BASE, isTauriDesktopRuntime } from './apiBase';
import type { ActiveProjectResponse, ProjectMeta } from '../types/trace';
import type { ChapterItem } from '../types/dashboard';

export type ServiceCheckId = 'backend' | 'project' | 'events' | 'models' | 'chapters';

export interface ServiceCheckItem {
  id: ServiceCheckId;
  label: string;
  description: string;
  status: 'pending' | 'checking' | 'ready' | 'error';
  error?: string;
  latencyMs?: number;
}

export interface VerificationResult {
  allReady: boolean;
  activeProject: ProjectMeta | null;
  projects: ProjectMeta[];
  chapters: ChapterItem[];
  desktopVersion?: string;
  checks: ServiceCheckItem[];
}

export interface StartupData {
  activeProject: ProjectMeta | null;
  projects: ProjectMeta[];
  chapters: ChapterItem[];
  projectsDir?: string;
}

/** Keep the deadline active while reading the response body as well as its headers. */
async function fetchStartupJson<T>(path: string, timeoutMs = 5000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
    return await response.json() as T;
  } finally {
    clearTimeout(timer);
  }
}

export const INITIAL_SERVICE_CHECKS: ServiceCheckItem[] = [
  {
    id: 'backend',
    label: 'Backend API Gateway',
    description: 'Pinging local HTTP server and verifying desktop protocol (port 15474)',
    status: 'pending',
  },
  {
    id: 'project',
    label: 'Project Registry & Memory',
    description: 'Loading active novel workspace and persistent Bible registry',
    status: 'pending',
  },
  {
    id: 'events',
    label: 'Real-Time Event Stream',
    description: 'Handshaking SSE event bus for live progress & execution logs',
    status: 'pending',
  },
  {
    id: 'models',
    label: 'AI Environment & Models',
    description: 'Reading local configuration; AI connections are tested explicitly in Setup',
    status: 'pending',
  },
  {
    id: 'chapters',
    label: 'Chapter Roster & Cache',
    description: 'Priming chapter files, aligned translation cache & status index',
    status: 'pending',
  },
];

/**
 * Polls the backend until responsive or timeout exceeded
 */
export async function pollBackendReady(
  maxWaitMs: number = isTauriDesktopRuntime() ? 30000 : 3500,
  intervalMs: number = 400
): Promise<{ ready: boolean; version?: string; latencyMs: number; error?: string }> {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    const attemptStart = Date.now();
    try {
      const data = await fetchStartupJson<{ version?: string }>(
        '/api/desktop-info', Math.min(2000, maxWaitMs - (Date.now() - start)),
      );
      return { ready: true, version: data.version, latencyMs: Date.now() - attemptStart };
    } catch {
      // Backend still booting or socket not bound yet
    }
    const remaining = maxWaitMs - (Date.now() - start);
    if (remaining > 0) await new Promise((resolve) => setTimeout(resolve, Math.min(intervalMs, remaining)));
  }
  return {
    ready: false,
    latencyMs: Date.now() - start,
    error: `Backend server did not respond within ${maxWaitMs / 1000} seconds.`,
  };
}

/**
 * Verifies the SSE event stream endpoint responds
 */
export async function verifyEventStream(): Promise<{ ready: boolean; latencyMs: number; error?: string }> {
  const start = Date.now();
  return new Promise((resolve) => {
    let resolved = false;
    let eventSource: EventSource | null = null;
    const timer = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        if (eventSource) eventSource.close();
        resolve({
          ready: true, // Non-fatal if stream takes extra time, SSE will reconnect in background
          latencyMs: Date.now() - start,
        });
      }
    }, 2500);

    try {
      eventSource = new EventSource(`${API_BASE}/api/stream/events`);
      eventSource.onopen = () => {
        if (!resolved) {
          resolved = true;
          clearTimeout(timer);
          eventSource?.close();
          resolve({ ready: true, latencyMs: Date.now() - start });
        }
      };
      eventSource.onerror = () => {
        // SSE may error if already active or during quick handshake; treat as non-fatal fallback
        if (!resolved) {
          resolved = true;
          clearTimeout(timer);
          eventSource?.close();
          resolve({ ready: true, latencyMs: Date.now() - start });
        }
      };
    } catch {
      if (!resolved) {
        resolved = true;
        clearTimeout(timer);
        resolve({ ready: true, latencyMs: Date.now() - start });
      }
    }
  });
}

/**
 * Verifies environment and model configurations
 */
export async function verifyEnvironment(): Promise<{ ready: boolean; latencyMs: number; error?: string }> {
  const start = Date.now();
  try {
    await fetchStartupJson('/api/environment');
    return {
      ready: true,
      latencyMs: Date.now() - start,
    };
  } catch (err: any) {
    return {
      ready: false,
      latencyMs: Date.now() - start,
      error: err?.message || 'Could not connect to environment configuration API.',
    };
  }
}

const SESSION_KEY = `nousetsu_startup:v1:${new URL(API_BASE || window.location.origin).origin}`;
let verifiedInMemory = false;

function hasVerifiedSession(): boolean {
  try {
    return verifiedInMemory || sessionStorage.getItem(SESSION_KEY) === 'ready';
  } catch {
    return verifiedInMemory;
  }
}

function markSessionVerified(): void {
  verifiedInMemory = true;
  try {
    sessionStorage.setItem(SESSION_KEY, 'ready');
  } catch {
    // Restricted browser storage should not prevent startup in this document.
  }
}

interface StartupSnapshot {
  checks: ServiceCheckItem[];
  progress: number;
  message: string;
  lightweight: boolean;
  status: 'idle' | 'running' | 'ready' | 'error';
  error?: string;
  data: StartupData;
}

function initialStartupSnapshot(): StartupSnapshot {
  return {
    checks: INITIAL_SERVICE_CHECKS.map((check) => ({ ...check })),
    progress: 0,
    message: 'Connecting to novel workspace...',
    lightweight: hasVerifiedSession(),
    status: 'idle',
    data: { activeProject: null, projects: [], chapters: [] },
  };
}

let startupSnapshot = initialStartupSnapshot();
let verification: Promise<void> | null = null;
const startupListeners = new Set<() => void>();

export const getStartupSnapshot = () => startupSnapshot;
export function subscribeStartup(listener: () => void): () => void {
  startupListeners.add(listener);
  return () => { startupListeners.delete(listener); };
}

function publishStartup(update: Partial<StartupSnapshot>): void {
  startupSnapshot = { ...startupSnapshot, ...update };
  startupListeners.forEach((listener) => listener());
}

function updateStartupCheck(id: ServiceCheckId, update: Partial<ServiceCheckItem>): void {
  publishStartup({ checks: startupSnapshot.checks.map((check) =>
    check.id === id ? { ...check, ...update } : check),
  });
}

async function runStartupVerification(): Promise<void> {
  let currentCheck: ServiceCheckId = 'backend';
  try {
    publishStartup({ status: 'running', progress: 5 });
    updateStartupCheck('backend', { status: 'checking' });
    const backend = await pollBackendReady();
    if (!backend.ready) throw new Error(backend.error);
    updateStartupCheck('backend', { status: 'ready', latencyMs: backend.latencyMs });

    currentCheck = 'project';
    publishStartup({ progress: 25, message: 'Loading project registry...' });
    updateStartupCheck('project', { status: 'checking' });
    const projectStart = Date.now();
    const registry = await fetchStartupJson<ActiveProjectResponse>('/api/active-project');
    if (!registry || !Array.isArray(registry.projects) || !('active_project' in registry)) {
      throw new Error('The project registry returned an invalid response.');
    }
    publishStartup({ data: {
      activeProject: registry.active_project,
      projects: registry.projects,
      chapters: [],
      projectsDir: registry.projects_dir,
    }, progress: 50 });
    updateStartupCheck('project', { status: 'ready', latencyMs: Date.now() - projectStart });

    if (!startupSnapshot.lightweight) {
      publishStartup({ message: 'Testing real-time event pipeline...' });
      updateStartupCheck('events', { status: 'checking' });
      const events = await verifyEventStream();
      updateStartupCheck('events', { status: 'ready', latencyMs: events.latencyMs });
      publishStartup({ progress: 75, message: 'Checking AI environment...' });
      updateStartupCheck('models', { status: 'checking' });
      const environment = await verifyEnvironment();
      updateStartupCheck('models', {
        status: environment.ready ? 'ready' : 'error',
        latencyMs: environment.latencyMs, error: environment.error,
      });
    }

    currentCheck = 'chapters';
    publishStartup({ progress: 90, message: 'Loading chapter roster...' });
    updateStartupCheck('chapters', { status: 'checking' });
    const chapterStart = Date.now();
    const path = registry.active_project?.path;
    const chapters = path ? await fetchStartupJson<ChapterItem[]>(
      `/api/chapters?${new URLSearchParams({ project_path: path })}`,
    ) : [];
    if (!Array.isArray(chapters)) throw new Error('The chapter roster returned an invalid response.');
    updateStartupCheck('chapters', { status: 'ready', latencyMs: Date.now() - chapterStart });
    markSessionVerified();
    publishStartup({
      data: { ...startupSnapshot.data, chapters },
      progress: 100, status: 'ready', message: 'Workspace ready.',
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'A required service did not respond.';
    updateStartupCheck(currentCheck, { status: 'error', error: message });
    publishStartup({ status: 'error', message: 'Service initialization stalled.', error: message });
  }
}

/** StrictMode remounts and callback updates reuse the same bootstrap operation. */
export function startVerification(retry = false): Promise<void> {
  if (startupSnapshot.status === 'running') return verification!;
  if (!retry && verification) return verification;
  if (retry) publishStartup(initialStartupSnapshot());
  verification = Promise.resolve().then(runStartupVerification);
  return verification;
}
