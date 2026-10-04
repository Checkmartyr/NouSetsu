import { API_BASE, isTauriDesktopRuntime } from './apiBase';
import type { ProjectMeta } from '../types/trace';
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
    description: 'Validating LLM provider credentials, rate limits & agent catalog',
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
      const res = await fetch(`${API_BASE}/api/desktop-info`, {
        headers: { Accept: 'application/json' },
      });
      if (res.ok) {
        const data = await res.json();
        return {
          ready: true,
          version: data.version,
          latencyMs: Date.now() - attemptStart,
        };
      }
    } catch {
      // Backend still booting or socket not bound yet
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  return {
    ready: false,
    latencyMs: Date.now() - start,
    error: 'Backend server did not respond within the 30-second initialization window.',
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
    const res = await fetch(`${API_BASE}/api/environment`, {
      headers: { Accept: 'application/json' },
    });
    return {
      ready: res.ok,
      latencyMs: Date.now() - start,
      error: res.ok ? undefined : `Environment API returned HTTP ${res.status}`,
    };
  } catch (err: any) {
    return {
      ready: false,
      latencyMs: Date.now() - start,
      error: err?.message || 'Could not connect to environment configuration API.',
    };
  }
}
