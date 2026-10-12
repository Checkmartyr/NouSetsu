import type { Page } from '@playwright/test';

export const projectPaths = ['C:/novels/A novel & 世界', 'C:/novels/Second', 'C:/novels/Third'];
export const projects = projectPaths.map((path, index) => ({
  path, name: `Novel${index + 1}`, title: `Novel ${index + 1}`, genre: 'fantasy',
  source_language: 'Japanese', target_language: 'English', has_traces: true,
  trace_count: 3, latest_trace_mtime: 1,
}));
const chapterPairs = [{ num: 1, folder: null }, { num: 1, folder: 'Volume 01' }, { num: 2, folder: 'Volume 01' }];
export const chapters = chapterPairs.map(({ num, folder }) => ({
  chapter_num: num, folder, title: `${folder || 'Root'} chapter ${num}`,
  file_name: `${num}.txt`, output_file_name: `${num}.md`, status: 'COMPLETED',
  current_stage: 'COMPLETED', raw_exists: true, raw_lines: 2, raw_words: 5,
  translated_exists: true, translated_words: 5, is_completed: true, has_checkpoint: false,
}));
const usage = { input_tokens: 10, output_tokens: 5, thought_tokens: 0, cached_tokens: 0, total_tokens: 15 };
export const traceChapters = chapterPairs.map(({ num, folder }, index) => ({
  id: `chapter-${index}`, chapterNum: num, folder, fileName: `${num}.json`,
  document: {
    chapter_id: `chapter-${index}`, chapter_num: num, folder, total_interactions: 2,
    total_duration_seconds: 2, total_token_usage: usage, stage_breakdown: { drafting: 1, critique: 1 },
    traces: ['drafting', 'critique'].map((stage) => ({
      trace_id: `${index}-${stage}`, timestamp: '2026-10-12T00:00:00Z', chapter_id: `chapter-${index}`,
      chapter_num: num, folder, stage, agent: stage === 'drafting' ? 'drafter' : 'critic', model: 'mock-model',
      iteration: 1, chunk_index: 1, total_chunks: 1, depth: 0, system_prompt: `${stage} system`,
      user_prompt: `${stage} requested input ${index}`, raw_output: `${stage} output ${index}`,
      parsed_output: {}, token_usage: usage, duration_seconds: 1, status: 'success', error_message: null, metadata: {},
    })),
  },
}));

export function path(view: string, params: Record<string, string> = {}) {
  return `/${view}?${new URLSearchParams({ project: projectPaths[0], ...params })}`;
}

// No request can reach a running backend or mutate a real project.
export async function mockBackend(page: Page, options: { delayContent?: boolean; delaySwitch?: boolean; failSwitch?: boolean; lazyTraces?: boolean } = {}) {
  const state = { active: 0, environment: 0, desktop: 0, switches: [] as string[], concurrentSwitches: 0, maxConcurrentSwitches: 0, unexpected: [] as string[], delayedContentCompleted: false,
    holdNextRegistry: false, registryHeld: false, registryReleased: false, releaseRegistry: null as (() => void) | null };
  await page.route('**/api/**', async (route) => {
    const fulfill = (response: Parameters<typeof route.fulfill>[0]) => route.fulfill({
      ...response,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        ...response.headers,
      },
    });
    const request = route.request();
    if (request.method() === 'OPTIONS') return fulfill({ status: 204 });
    const url = new URL(request.url());
    const endpoint = url.pathname;
    if (endpoint === '/api/desktop-info') { state.desktop++; return fulfill({ json: { version: 'test' } }); }
    if (endpoint === '/api/environment') { state.environment++; return fulfill({ json: { values: {}, api_key_status: {}, configured_keys: {}, resolved_models: {}, env_file_path: 'test.env' } }); }
    if (endpoint === '/api/stream/events') return fulfill({ contentType: 'text/event-stream', body: ': connected\n\n' });
    if (endpoint === '/api/active-project') {
      if (request.method() === 'POST') {
        const target = request.postDataJSON().project_path;
        state.switches.push(target);
        state.concurrentSwitches++;
        state.maxConcurrentSwitches = Math.max(state.maxConcurrentSwitches, state.concurrentSwitches);
        if (options.delaySwitch) await new Promise((resolve) => setTimeout(resolve, 400));
        state.concurrentSwitches--;
        if (options.failSwitch) return fulfill({ status: 500, json: { detail: 'Switch failed' } });
        state.active = projectPaths.indexOf(target);
      }
      const registry = { success: true, active_project: projects[state.active], projects, projects_dir: 'C:/novels' };
      if (request.method() === 'GET' && state.holdNextRegistry) {
        state.holdNextRegistry = false;
        state.registryHeld = true;
        await new Promise<void>((resolve) => { state.releaseRegistry = resolve; });
        state.registryReleased = true;
      }
      return fulfill({ json: registry });
    }
    if (endpoint === '/api/sync-state') return fulfill({ json: { active_project_path: projectPaths[state.active], active_project_title: projects[state.active].title, traces_count: 3, latest_trace_mtime: 1 } });
    if (endpoint === '/api/chapters') return fulfill({ json: chapters });
    const contentMatch = endpoint.match(/^\/api\/chapters\/(\d+)\/content$/);
    if (contentMatch) {
      const chapter = Number(contentMatch[1]);
      const folder = url.searchParams.get('folder') || null;
      const target = url.searchParams.get('project_path') || projectPaths[state.active];
      if (options.delayContent && chapter === 1 && folder === 'Volume 01') {
        await new Promise((resolve) => setTimeout(resolve, 700));
        state.delayedContentCompleted = true;
      }
      return fulfill({ json: { chapter_num: chapter, folder, source_file: `${chapter}.txt`, output_file: `${chapter}.md`, source_text: 'Original chapter', translated_text: `Reading ${target} ${folder || 'Root'} chapter ${chapter}`, has_source: true, has_translated: true } });
    }
    if (endpoint === '/api/traces') {
      const num = url.searchParams.get('chapter');
      const folder = url.searchParams.get('folder') || null;
      if (options.lazyTraces && num) await new Promise((resolve) => setTimeout(resolve, 300));
      const list = num ? traceChapters.filter((ch) => ch.chapterNum === Number(num) && ch.folder === folder) : traceChapters.map((ch, index) =>
        options.lazyTraces && index > 0 ? { ...ch, document: { ...ch.document, traces: [] } } : ch);
      return fulfill({ json: { project_path: projectPaths[state.active], project_title: projects[state.active].title, genre: 'fantasy', chapters: list } });
    }
    if (endpoint === '/api/translate/status') return fulfill({ json: { is_running: false, active_chapter: null, active_folder: null, active_stage: null, completed_count: 3, total_count: 3, paused_reason: null, last_log: null } });
    if (endpoint === '/api/bible') return fulfill({ json: { title: 'Novel 1', genre: 'fantasy', source_language: 'Japanese', target_language: 'English', characters: [], glossary: [], archived_arcs: [] } });
    if (endpoint === '/api/bible/raw') return fulfill({ json: { raw_yaml: 'title: Novel 1' } });
    if (endpoint === '/api/settings') return fulfill({ json: { title: 'Novel 1', source_language: 'Japanese', target_language: 'English', genre: 'fantasy' } });
    if (endpoint === '/api/folders') return fulfill({ json: { folders: ['Volume 01'], output_folders: [], default_output_dir: 'translated_chapters' } });
    if (endpoint === '/api/model-catalog') return fulfill({ json: { provider: url.searchParams.get('provider'), models: [], configured: false } });
    if (endpoint === '/api/logs/frontend') return fulfill({ json: { success: true } });
    if (endpoint === '/api/token-analytics') {
      const summary = { total_chapters: 3, analyzed_chapters: 3, total_tokens: 45, prompt_tokens: 30, completion_tokens: 15, thought_tokens: 0, cached_tokens: 0, total_duration_seconds: 3, selected_folder: 'ALL', available_folders: ['default', 'Volume 01'], stage_metrics: [], model_metrics: [], folder_metrics: [], chapter_rankings: [] };
      return fulfill({ json: { project_path: projectPaths[state.active], project_title: projects[state.active].title, selected_folder: 'ALL', available_folders: summary.available_folders, recorded: summary, history: summary, metadata_snapshot: summary, coverage: { known_chapters: 3, history_chapters: 3, trace_snapshot_chapters: 0, snapshot_only_chapters: 0, history_complete: true } } });
    }
    state.unexpected.push(`${request.method()} ${endpoint}`);
    return fulfill({ status: 404, json: { detail: 'Unmocked API endpoint' } });
  });
  return state;
}
