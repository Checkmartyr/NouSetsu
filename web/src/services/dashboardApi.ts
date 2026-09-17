import {
  ChapterItem,
  ChapterContent,
  TranslationStatus,
  BibleData,
  ProjectSettings
} from '../types/dashboard';

const API_BASE = '';

export async function fetchChapters(projectPath?: string, folder?: string): Promise<ChapterItem[]> {
  try {
    const params = new URLSearchParams();
    if (projectPath) params.set('project_path', projectPath);
    if (folder) params.set('folder', folder);
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/api/chapters${qs}`);
    if (!res.ok) return [];
    return (await res.json()) as ChapterItem[];
  } catch (e) {
    console.error('Failed to fetch chapters:', e);
    return [];
  }
}

export async function fetchChapterContent(
  chapterNum: number,
  projectPath?: string,
  folder?: string
): Promise<ChapterContent | null> {
  try {
    const params = new URLSearchParams();
    if (projectPath) params.set('project_path', projectPath);
    if (folder) params.set('folder', folder);
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/api/chapters/${chapterNum}/content${qs}`);
    if (!res.ok) return null;
    return (await res.json()) as ChapterContent;
  } catch (e) {
    console.error(`Failed to fetch chapter ${chapterNum} content:`, e);
    return null;
  }
}

export async function fetchTranslationStatus(): Promise<TranslationStatus | null> {
  try {
    const res = await fetch(`${API_BASE}/api/translate/status`);
    if (!res.ok) return null;
    return (await res.json()) as TranslationStatus;
  } catch (e) {
    return null;
  }
}

export async function startTranslation(params: {
  project_path?: string;
  folder?: string;
  chapter_num?: number;
  limit?: number;
  force_retranslate?: boolean;
  model?: string;
  fallback_model?: string;
  max_loops?: number;
  quality_threshold?: number;
}): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/api/translate/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Failed to start translation');
  }
  return data;
}

export async function stopTranslation(): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/api/translate/stop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  return await res.json();
}

export async function fetchBible(projectPath?: string): Promise<BibleData | null> {
  try {
    const params = new URLSearchParams();
    if (projectPath) params.set('project_path', projectPath);
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/api/bible${qs}`);
    if (!res.ok) return null;
    return (await res.json()) as BibleData;
  } catch (e) {
    console.error('Failed to fetch bible:', e);
    return null;
  }
}

export async function updateBible(data: BibleData, projectPath?: string): Promise<boolean> {
  try {
    const params = new URLSearchParams();
    if (projectPath) params.set('project_path', projectPath);
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/api/bible${qs}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return res.ok;
  } catch (e) {
    console.error('Failed to update bible:', e);
    return false;
  }
}

export async function fetchRawBible(projectPath?: string): Promise<{ raw_yaml: string; raw?: string } | null> {
  try {
    const params = new URLSearchParams();
    if (projectPath) params.set('project_path', projectPath);
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/api/bible/raw${qs}`);
    if (!res.ok) return null;
    const data = await res.json();
    return {
      raw_yaml: data.raw_yaml || data.raw || '',
      raw: data.raw || data.raw_yaml || '',
    };
  } catch (e) {
    return null;
  }
}

export async function updateRawBible(rawYaml: string, projectPath?: string): Promise<boolean> {
  try {
    const params = new URLSearchParams();
    if (projectPath) params.set('project_path', projectPath);
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/api/bible/raw${qs}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ raw_yaml: rawYaml, raw: rawYaml }),
    });
    return res.ok;
  } catch (e) {
    console.error('Failed to update raw bible:', e);
    return false;
  }
}

export async function fetchSettings(projectPath?: string): Promise<ProjectSettings | null> {
  try {
    const params = new URLSearchParams();
    if (projectPath) params.set('project_path', projectPath);
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/api/settings${qs}`);
    if (!res.ok) return null;
    const data = await res.json();
    if (data && data.config && typeof data.config === 'object') {
      return {
        ...data.config,
        ...data,
      } as ProjectSettings;
    }
    return data as ProjectSettings;
  } catch (e) {
    return null;
  }
}

export async function updateSettings(
  data: Partial<ProjectSettings>,
  projectPath?: string
): Promise<boolean> {
  try {
    const params = new URLSearchParams();
    if (projectPath) params.set('project_path', projectPath);
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/api/settings${qs}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return res.ok;
  } catch (e) {
    console.error('Failed to update settings:', e);
    return false;
  }
}

/**
 * Connect to backend Server-Sent Events stream
 */
export function connectSSE(onEvent: (eventName: string, data: any) => void): () => void {
  const eventSource = new EventSource(`${API_BASE}/api/stream/events`);

  const eventTypes = [
    'job_started',
    'chapter_started',
    'stage_progress',
    'chapter_finished',
    'job_finished',
    'log',
    'heartbeat',
  ];

  eventTypes.forEach((evtName) => {
    eventSource.addEventListener(evtName, (e: MessageEvent) => {
      try {
        const parsed = JSON.parse(e.data);
        onEvent(evtName, parsed);
      } catch {
        onEvent(evtName, e.data);
      }
    });
  });

  eventSource.onerror = (err) => {
    console.warn('SSE connection warning or error:', err);
  };

  return () => {
    eventSource.close();
  };
}
