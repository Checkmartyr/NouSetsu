import { API_BASE } from './apiBase';
import {
  ChapterItem,
  ChapterContent,
  TranslationStatus,
  BibleData,
  ProjectSettings,
  ProjectFoldersResult,
  UploadChaptersResult,
  ScraperCheckResult,
  ScraperInspectResult,
  ScraperExtractParams,
  ScraperExtractResult,
  ScraperStatusResult,
  EbookInspectResult,
  EbookImportParams,
  EbookImportResult,
  EbookExportOptions,
  EbookPreviewResult,
  MachineEnvironment,
  ModelCatalogResult,
  ModelProvider,
  UpdateCheckResult,
} from '../types/dashboard';

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
  chapter?: string | number;
  chapter_num?: string | number;
  chapter_filter?: string | number;
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
      const { config, ...rest } = data;
      return {
        ...config,
        ...rest,
        env: data.env,
      } as ProjectSettings;
    }
    return data as ProjectSettings;
  } catch (e) {
    return null;
  }
}

export async function fetchModelCatalog(provider: ModelProvider): Promise<ModelCatalogResult> {
  const params = new URLSearchParams({ provider });
  const res = await fetch(`${API_BASE}/api/model-catalog?${params.toString()}`);
  if (!res.ok) {
    throw new Error(`Could not load ${provider} model catalog (HTTP ${res.status}).`);
  }
  return (await res.json()) as ModelCatalogResult;
}

export async function fetchMachineEnvironment(): Promise<MachineEnvironment | null> {
  try {
    const res = await fetch(`${API_BASE}/api/environment`);
    if (!res.ok) return null;
    return (await res.json()) as MachineEnvironment;
  } catch (e) {
    console.error('Failed to fetch machine environment settings:', e);
    return null;
  }
}

export async function saveMachineEnvironment(data: {
  values: Record<string, string>;
  api_keys: Record<string, string>;
  clear_api_keys: string[];
}): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/environment`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return res.ok;
  } catch (e) {
    console.error('Failed to save machine environment settings:', e);
    return false;
  }
}

export async function checkLatestRelease(): Promise<UpdateCheckResult> {
  const res = await fetch(`${API_BASE}/api/updates/latest`);
  const responseText = await res.text();
  let data: unknown;

  try {
    data = JSON.parse(responseText);
  } catch {
    throw new Error(`Update check returned an invalid response (HTTP ${res.status}).`);
  }

  if (!res.ok) {
    const detail =
      typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string'
        ? data.detail
        : `Update check failed (HTTP ${res.status}).`;
    throw new Error(detail);
  }

  return data as UpdateCheckResult;
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
    'stage_start',
    'stage_progress',
    'chapter_finished',
    'chapter_completed',
    'job_finished',
    'batch_completed',
    'batch_stopped',
    'batch_error',
    'log',
    'log_message',
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

export async function fetchProjectFolders(projectPath?: string): Promise<ProjectFoldersResult> {
  try {
    const params = new URLSearchParams();
    if (projectPath) params.set('project_path', projectPath);
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/api/folders${qs}`);
    if (!res.ok) return { default_folder: 'raw_chapters', folders: ['raw_chapters'] };
    return (await res.json()) as ProjectFoldersResult;
  } catch (e) {
    console.error('Failed to fetch project folders:', e);
    return { default_folder: 'raw_chapters', folders: ['raw_chapters'] };
  }
}

export async function uploadChapters(params: {
  files: { name: string; content: string }[];
  projectPath?: string;
  folder?: string;
  overwrite?: boolean;
}): Promise<UploadChaptersResult> {
  const res = await fetch(`${API_BASE}/api/chapters/upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_path: params.projectPath,
      folder: params.folder,
      files: params.files,
      overwrite: params.overwrite ?? false,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Failed to upload chapters');
  }
  return data as UploadChaptersResult;
}

export async function checkScraperAvailability(projectPath?: string): Promise<ScraperCheckResult> {
  try {
    const params = new URLSearchParams();
    if (projectPath) params.set('project_path', projectPath);
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/api/scraper/check${qs}`);
    if (!res.ok) return { available: false, scraper_dir: null, python_exe: null };
    return (await res.json()) as ScraperCheckResult;
  } catch (e) {
    return { available: false, scraper_dir: null, python_exe: null };
  }
}

export async function inspectScraperUrl(url: string, projectPath?: string): Promise<ScraperInspectResult> {
  const res = await fetch(`${API_BASE}/api/scraper/inspect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, project_path: projectPath }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || data.error || 'Failed to inspect novel URL');
  }
  return data as ScraperInspectResult;
}

export async function startScraperExtract(params: ScraperExtractParams): Promise<ScraperExtractResult> {
  const res = await fetch(`${API_BASE}/api/scraper/extract`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      url: params.url,
      project_path: params.projectPath,
      folder: params.folder,
      chapter_indices: params.chapterIndices,
      start_chapter: params.startChapter,
      end_chapter: params.endChapter,
      concurrency: params.concurrency ?? 3,
      include_frontmatter: params.includeFrontmatter ?? false,
      overwrite: params.overwrite ?? false,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Failed to start scraping task');
  }
  return data as ScraperExtractResult;
}

export async function fetchScraperStatus(taskId: string): Promise<ScraperStatusResult> {
  const res = await fetch(`${API_BASE}/api/scraper/status/${taskId}`);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Failed to fetch scraper task status');
  }
  return data as ScraperStatusResult;
}

export async function inspectEbook(file: File): Promise<EbookInspectResult> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/api/ebook/inspect`, {
    method: 'POST',
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || data.error || 'Failed to inspect eBook');
  }
  return data as EbookInspectResult;
}

export async function importEbook(file: File, params: EbookImportParams): Promise<EbookImportResult> {
  const formData = new FormData();
  formData.append('file', file);
  if (params.project_path) formData.append('project_path', params.project_path);
  if (params.folder) formData.append('folder', params.folder);
  if (params.start_chapter !== undefined) formData.append('start_chapter', String(params.start_chapter));
  if (params.end_chapter !== undefined) formData.append('end_chapter', String(params.end_chapter));
  if (params.selected_indices) formData.append('selected_indices', params.selected_indices);
  if (params.overwrite !== undefined) formData.append('overwrite', String(params.overwrite));
  if (params.extract_images !== undefined) formData.append('extract_images', String(params.extract_images));

  const res = await fetch(`${API_BASE}/api/ebook/import`, {
    method: 'POST',
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || data.error || 'Failed to import eBook chapters');
  }
  return data as EbookImportResult;
}

export async function exportEbook(options: EbookExportOptions): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${API_BASE}/api/ebook/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
  });

  if (!res.ok) {
    const errorJson = await res.json().catch(() => ({}));
    throw new Error(errorJson.detail || 'Failed to compile and export eBook');
  }

  // Parse filename from Content-Disposition header if available
  let filename = options.format === 'pdf' ? 'novel.pdf' : (options.format === 'html' ? 'novel.html' : 'novel.epub');
  const disposition = res.headers.get('Content-Disposition');
  if (disposition) {
    const match = disposition.match(/filename="?([^";]+)"?/i);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  const blob = await res.blob();
  return { blob, filename };
}

export async function previewEbook(
  options: EbookExportOptions,
  previewIndex: number = 1
): Promise<EbookPreviewResult> {
  const reqBody = { ...options, preview_chapter_index: previewIndex };
  const res = await fetch(`${API_BASE}/api/ebook/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(reqBody),
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || data.error || 'Failed to preview eBook');
  }
  return data as EbookPreviewResult;
}




