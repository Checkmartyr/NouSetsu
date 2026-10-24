// Fictional, fixed documentation data. Never reads a registry, novel, .env, or API key.
export const projectPath = 'C:/NouSetsu Demo/The Lantern Archive';
const title = 'The Lantern Archive';
const folder = 'Volume 01';
export const sourceText = `# 第一話　雨の向こうの図書館

雨がやむころ、遥は古い図書館の前に立っていた。閉じた扉の向こうで、青い灯がひとつ揺れている。

「ここで待っていて」蓮はそう言った。けれど、彼の声は雨音に溶け、足音だけが石畳に残った。

遥は祖母から預かった鍵を握りしめた。銀色の鍵には、小さな月と、読めない文字が刻まれている。

扉に触れると、遠い鐘の音が聞こえた。夕暮れの町には時計塔などなかったはずなのに。

「本を返しに来たの？」背後から静かな声がした。振り返ると、見知らぬ少女が一冊の本を抱えていた。

「いいえ。祖母の手紙を届けに来たんです」遥は濡れた封筒を見せた。少女はその紋章を見るなり、笑みを消した。

青い灯が明るくなり、図書館の扉が内側へと開いた。そこには、夜空のように深い廊下が続いていた。

遥は息を吸い、最初の一歩を踏み出した。物語はまだ、彼女の名前を知らなかった。`;

export const polishedText = `# Chapter 1 — The Library Beyond the Rain

By the time the rain stopped, Haruka stood outside the old library. Beyond its closed doors, a single blue lantern stirred.

“Wait here,” Ren had said. But his voice dissolved into the rain, leaving only the echo of footsteps on wet stone.

Haruka tightened her grip on the key her grandmother had entrusted to her. A tiny crescent and letters she could not read were engraved in its silver.

When she touched the door, a distant bell rang. There was no clock tower in this town. She was certain of that.

“Have you come to return a book?” A quiet voice spoke behind her. She turned to find an unfamiliar girl cradling a single volume.

“No. I have a letter from my grandmother.” Haruka held out the damp envelope. At the sight of its crest, the girl's smile faded.

The blue lantern brightened. The library doors swung inward, revealing a corridor as deep as the night sky.

Haruka drew a breath and took the first step. The story did not yet know her name.`;
const draftText = polishedText
  .replace('a single blue lantern stirred', 'there was one blue light moving')
  .replace('his voice dissolved into the rain, leaving only the echo of footsteps on wet stone', 'his voice was mixed with the sound of rain, and only the sound of his footsteps remained on the stone pavement')
  .replace('Haruka tightened her grip on the key her grandmother had entrusted to her', 'Haruka strongly held the key that she received from her grandmother')
  .replace('a corridor as deep as the night sky', 'a hallway that was deep like the night sky');
const characters = [
  { name: 'Haruka Mori', original_name: '森遥', gender: 'female', role: 'protagonist', aliases: ['Haruka'], status: 'active',
    voice: 'Thoughtful and observant; measured speech that grows more direct when she is afraid.',
    summary: 'A young archivist following her grandmother’s letter to a library that appears only after rain.',
    relationships: { 'Ren Aoki': 'Childhood friend and trusted guide' }, pronouns: { source: '私', target: 'I' } },
  { name: 'Ren Aoki', original_name: '青木蓮', gender: 'male', role: 'supporting', aliases: ['Ren'], status: 'active',
    voice: 'Brief, practical sentences; understated humour hides his concern for Haruka.',
    summary: 'A lantern keeper who knows more about the archive than he admits.',
    relationships: { 'Haruka Mori': 'Childhood friend; determined to protect her' }, pronouns: { source: '僕', target: 'I' } },
  { name: 'Mio', original_name: '澪', gender: 'female', role: 'supporting', aliases: ['The Librarian'], status: 'active',
    voice: 'Soft, formal speech with an unsettling certainty about events that have not happened.',
    summary: 'The keeper of the Lantern Archive, collecting stories that have lost their endings.', relationships: {} },
];
const bible = { title, genre: 'fantasy', source_language: 'Japanese', target_language: 'English', characters,
  glossary: [{ source: '灯の書庫', target: 'Lantern Archive', category: 'location', notes: 'Canonical name; always capitalise.' },
    { source: '月の鍵', target: 'Crescent Key', category: 'item', notes: 'The silver key entrusted to Haruka.' }],
  whole_story_summary: 'Haruka follows a letter to a hidden library, where unfinished stories can alter the world outside.',
  archived_arcs: [], style_guide: 'Lyrical, precise English. Preserve quiet tension and distinct dialogue registers.' };
const stages = ['extraction', 'drafting', 'critique', 'polishing', 'chronicling'];
const agents = ['extractor', 'drafter', 'critic', 'polisher', 'chronicler'];
const tokenCounts = [1200, 3200, 1800, 2200, 1000];
const durations = [0.8, 4.2, 1.6, 2.8, 1.1];
const outputs = [JSON.stringify({ new_characters: characters, new_terms: bible.glossary }, null, 2), draftText,
  JSON.stringify({ fidelity_score: 9.2, style_score: 8.7, critique_notes: ['Preserve the blue lantern motif.', 'Replace literal phrasing with natural cadence; retain every source detail.'] }, null, 2),
  polishedText, JSON.stringify({ summary: bible.whole_story_summary, characters_present: ['Haruka Mori', 'Ren Aoki', 'Mio'], arc_completed: false }, null, 2)];
const traces = stages.map((stage, i) => ({ trace_id: `demo-${stage}`, chapter_id: 'chapter_0001', chapter_num: 1, folder,
  timestamp: `2026-10-01T10:00:0${i}.000Z`, stage, agent: agents[i], model: 'mock-literary-model', iteration: 1,
  chunk_index: 0, total_chunks: 1, depth: 0, duration_seconds: durations[i], status: 'success', error_message: null,
  system_prompt: `You are the ${agents[i]} for this fictional Japanese-to-English literary translation. Preserve character voice, source meaning, chapter titles, and the Novel Bible.`,
  user_prompt: sourceText, raw_output: outputs[i], parsed_output: i === 1 || i === 3 ? { text: outputs[i] } : JSON.parse(outputs[i]),
  token_usage: { input_tokens: tokenCounts[i] * 0.7, output_tokens: tokenCounts[i] * 0.3, thought_tokens: 0, cached_tokens: 0, total_tokens: tokenCounts[i] }, metadata: {} }));
const traceDocument = { chapter_id: 'chapter_0001', chapter_num: 1, folder, created_at: '2026-10-01T10:00:00.000Z',
  total_interactions: 5, total_duration_seconds: 10.5, total_token_usage: { input_tokens: 6580, output_tokens: 2820, thought_tokens: 0, cached_tokens: 0, total_tokens: 9400 },
  stage_breakdown: Object.fromEntries(stages.map(stage => [stage, 1])), traces };
const chapterTitles = ['The Library Beyond the Rain', 'A Letter Without an Address', 'The Keeper of Lost Endings', 'Names Written in Silver', 'A Lantern for the Journey', 'The Door at Midnight', 'Stories Yet Untold', 'The Last Page'];
const chapters = chapterTitles.map((name, i) => ({ chapter_num: i + 1, folder, title: name, file_name: `${String(i + 1).padStart(4, '0')}.md`,
  output_file_name: `${String(i + 1).padStart(4, '0')}.md`, status: i < 6 ? 'COMPLETED' : 'PENDING', current_stage: i < 6 ? 'COMPLETED' : 'NONE',
  raw_exists: true, raw_lines: 120 + i * 8, raw_words: 640 + i * 25, translated_exists: i < 6, translated_words: i < 6 ? 720 + i * 28 : 0,
  is_completed: i < 6, has_checkpoint: false, quality_audit: i < 6 ? { fidelity_score: 9.2, style_score: 9.0 } : null }));
const project = { path: projectPath, name: title, title, genre: 'fantasy', source_language: 'Japanese', target_language: 'English', has_traces: true, trace_count: 1, latest_trace_mtime: 1 };
const settings = { title, source_language: 'Japanese', target_language: 'English', genre: 'fantasy', raw_dir: 'raw_chapters', output_dir: 'translated_chapters', max_loops: 2, quality_threshold: 8.5 };
const totals = { total_tokens: 56400, input_tokens: 39480, output_tokens: 16920, thought_tokens: 0, cached_tokens: 0, duration_seconds: 63 };
const summary = { total_chapters: 8, analyzed_chapters: 6, total_tokens: totals.total_tokens, prompt_tokens: totals.input_tokens,
  completion_tokens: totals.output_tokens, thought_tokens: 0, cached_tokens: 0, total_duration_seconds: 63, selected_folder: 'ALL', available_folders: [folder],
  stage_metrics: stages.map((stage, i) => ({ stage, calls: 6, total_tokens: tokenCounts[i] * 6, input_tokens: tokenCounts[i] * 4.2, output_tokens: tokenCounts[i] * 1.8, thought_tokens: 0, cached_tokens: 0, duration_seconds: durations[i] * 6 })),
  model_metrics: [{ model: 'mock-literary-model', calls: 30, ...totals }], folder_metrics: [{ folder, chapter_count: 8, analyzed_chapters: 6, ...totals }],
  chapter_rankings: chapters.slice(0, 6).map(ch => ({ chapter_id: `chapter_${ch.chapter_num}`, chapter_num: ch.chapter_num, source_file: ch.file_name, folder,
    total_tokens: 9400, prompt_tokens: 6580, completion_tokens: 2820, thought_tokens: 0, cached_tokens: 0, duration_seconds: 10.5, status: 'COMPLETED' })) };

export async function installDemo(context, origin) {
  const failures = [];
  await context.route('**/*', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/api/')) {
      // Keep screenshots independent of remote fonts and never contact another service.
      return url.origin === origin ? route.continue() : route.abort();
    }
    const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': 'GET, OPTIONS' };
    if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
    if (request.method() === 'POST' && url.pathname === '/api/logs/frontend') return route.fulfill({ headers, json: { success: true } });
    if (request.method() !== 'GET') {
      failures.push(`Unexpected write: ${request.method()} ${url.pathname}`);
      return route.fulfill({ status: 405, headers, json: { detail: 'Documentation capture is read-only.' } });
    }
    if (url.pathname === '/api/stream/events') return route.fulfill({ headers, contentType: 'text/event-stream', body: ': documentation demo\n\n' });
    const responses = {
      '/api/desktop-info': { version: 'demo' }, '/api/setup': { completed: true, existing: true, locale: 'en' },
      '/api/active-project': { active_project: project, projects: [project], projects_dir: 'C:/NouSetsu Demo' },
      '/api/sync-state': { active_project_path: projectPath, active_project_title: title, traces_count: 1, latest_trace_mtime: 1 },
      '/api/chapters': chapters,
      '/api/folders': { folders: [folder], default_folder: folder, output_folders: ['translated_chapters'], default_output_dir: 'translated_chapters' },
      '/api/translate/status': { is_running: false, active_chapter: null, active_folder: null, active_stage: null, completed_count: 6, total_count: 8, paused_reason: null, last_log: null },
      '/api/traces': { project_path: projectPath, project_title: title, genre: 'fantasy', chapters: [{ id: 'chapter_0001', chapterNum: 1, folder, fileName: '0001.json', document: traceDocument }] },
      '/api/bible': bible, '/api/bible/raw': { raw_yaml: `title: ${title}\ngenre: fantasy\n` }, '/api/settings': settings,
      '/api/environment': { values: {}, api_key_status: {}, configured_keys: {}, resolved_models: {}, env_file_path: 'demo.env' },
      '/api/model-catalog': { provider: 'gemini', models: [], configured: false },
      '/api/scraper/check': { available: true }, '/api/scraper/jobs': { jobs: [] },
      '/api/token-analytics': { project_path: projectPath, project_title: title, selected_folder: 'ALL', available_folders: [folder], recorded: summary, history: summary,
        metadata_snapshot: { ...summary, total_chapters: 6 }, coverage: { known_chapters: 8, history_chapters: 6, trace_snapshot_chapters: 0, snapshot_only_chapters: 0, history_complete: true } },
    };
    if (/^\/api\/chapters\/\d+\/content$/.test(url.pathname)) {
      return route.fulfill({ headers, json: { chapter_num: 1, folder, source_file: '0001.md', output_file: '0001.md', source_text: sourceText, translated_text: polishedText, has_source: true, has_translated: true } });
    }
    if (Object.hasOwn(responses, url.pathname)) return route.fulfill({ headers, json: responses[url.pathname] });
    failures.push(`Missing fixture: ${url.pathname}`);
    return route.fulfill({ status: 404, headers, json: { detail: 'No documentation fixture for this endpoint.' } });
  });
  return failures;
}
