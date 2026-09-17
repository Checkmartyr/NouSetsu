import { ActiveProjectResponse, SyncState, ProjectTracesResponse, CreateProjectRequest, ProjectMeta } from '../types/trace';

const API_BASE = '';

/**
 * Check if the backend trace server is reachable and get the active project
 */
export async function fetchActiveProject(): Promise<ActiveProjectResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/api/active-project`, {
      headers: { 'Accept': 'application/json' },
    });
    if (!res.ok) return null;
    return (await res.json()) as ActiveProjectResponse;
  } catch {
    return null;
  }
}

/**
 * Lightweight sync status check for background polling
 */
export async function fetchSyncState(): Promise<SyncState | null> {
  try {
    const res = await fetch(`${API_BASE}/api/sync-state`, {
      headers: { 'Accept': 'application/json' },
    });
    if (!res.ok) return null;
    return (await res.json()) as SyncState;
  } catch {
    return null;
  }
}

/**
 * Fetch all loaded chapter traces for a given project path (or active project)
 */
export async function fetchProjectTraces(projectPath?: string): Promise<ProjectTracesResponse | null> {
  try {
    const query = projectPath ? `?project_path=${encodeURIComponent(projectPath)}` : '';
    const res = await fetch(`${API_BASE}/api/traces${query}`, {
      headers: { 'Accept': 'application/json' },
    });
    if (!res.ok) return null;
    return (await res.json()) as ProjectTracesResponse;
  } catch {
    return null;
  }
}

/**
 * Switch active project in ProjectRegistry
 */
export async function switchActiveProject(projectPath: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/active-project`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ project_path: projectPath }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Initialize a new novel translation project inside NOVEL_PROJECTS_DIR
 */
export async function createProject(
  data: CreateProjectRequest
): Promise<{ success: boolean; active_project: ProjectMeta }> {
  const res = await fetch(`${API_BASE}/api/projects/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to create project');
  }
  return await res.json();
}

