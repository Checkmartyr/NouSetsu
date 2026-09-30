import { test, expect } from '@playwright/test';

const projectPath = 'C:/projects/TestNovel';

function summary(totalTokens: number, chapterNum: number, folder: string) {
  const promptTokens = totalTokens === 285 ? 178 : totalTokens === 275 ? 170 : totalTokens === 55 ? 30 : totalTokens === 10 ? 8 : 0;
  const completionTokens = totalTokens === 285 ? 92 : totalTokens === 275 ? 90 : totalTokens === 55 ? 20 : totalTokens === 10 ? 2 : 0;
  const thoughtTokens = totalTokens === 285 || totalTokens === 275 ? 15 : totalTokens === 55 ? 5 : 0;
  const cachedTokens = totalTokens === 285 || totalTokens === 275 ? 30 : 0;
  const durationSeconds = totalTokens === 285 ? 6.5 : totalTokens === 275 ? 6 : totalTokens === 55 ? 3 : totalTokens === 10 ? 0.5 : 0;
  return {
    total_chapters: totalTokens === 285 ? 3 : totalTokens === 275 ? 2 : totalTokens === 0 ? 0 : 1,
    analyzed_chapters: totalTokens === 285 ? 3 : totalTokens === 275 ? 2 : totalTokens === 0 ? 0 : 1,
    total_tokens: totalTokens,
    prompt_tokens: promptTokens,
    completion_tokens: completionTokens,
    thought_tokens: thoughtTokens,
    cached_tokens: cachedTokens,
    total_duration_seconds: durationSeconds,
    selected_folder: totalTokens === 275 ? 'ALL' : folder,
    available_folders: ['default', 'Volume_01'],
    stage_metrics: [{
      stage: 'drafting', calls: 2, total_tokens: totalTokens,
      input_tokens: promptTokens, output_tokens: completionTokens,
      thought_tokens: thoughtTokens, cached_tokens: cachedTokens,
      duration_seconds: durationSeconds,
    }],
    model_metrics: [{
      model: 'mock-model', calls: 2, total_tokens: totalTokens,
      input_tokens: promptTokens, output_tokens: completionTokens,
      thought_tokens: thoughtTokens, cached_tokens: cachedTokens,
      duration_seconds: durationSeconds,
    }],
    folder_metrics: [{
      folder, chapter_count: 1, analyzed_chapters: 1, total_tokens: totalTokens,
      input_tokens: promptTokens, output_tokens: completionTokens,
      thought_tokens: thoughtTokens, cached_tokens: cachedTokens,
      duration_seconds: durationSeconds,
    }],
    chapter_rankings: [{
      chapter_id: 'ch_002', chapter_num: chapterNum, source_file: '0002.txt',
      folder, total_tokens: totalTokens, prompt_tokens: promptTokens,
      completion_tokens: completionTokens, thought_tokens: thoughtTokens,
      cached_tokens: cachedTokens, duration_seconds: durationSeconds, status: 'pending',
    }],
  };
}

test('Project Analytics shows project totals and filters a volume folder', async ({ page }) => {
  await page.route('**/api/active-project', (route) => route.fulfill({
    json: {
      active_project: {
        path: projectPath, name: 'TestNovel', title: 'Test Novel', genre: 'fantasy',
        source_language: 'Japanese', target_language: 'English', has_traces: true,
        trace_count: 2, latest_trace_mtime: 1,
      },
      projects: [],
    },
  }));
  await page.route('**/api/sync-state', (route) => route.fulfill({
    json: {
      active_project_path: projectPath, active_project_title: 'Test Novel',
      traces_count: 2, latest_trace_mtime: 1,
    },
  }));
  await page.route('**/api/traces**', (route) => route.fulfill({
    json: { project_path: projectPath, project_title: 'Test Novel', genre: 'fantasy', chapters: [] },
  }));

  const requestedFolders: string[] = [];
  await page.route('**/api/token-analytics**', async (route) => {
    const url = new URL(route.request().url());
    const folder = url.searchParams.get('folder');
    requestedFolders.push(folder || 'ALL');
    const isFiltered = folder === 'Volume_01';
    await route.fulfill({
      json: {
        project_path: projectPath,
        project_title: 'Test Novel',
        selected_folder: isFiltered ? folder : 'ALL',
        available_folders: ['default', 'Volume_01'],
        recorded: summary(isFiltered ? 55 : 285, isFiltered ? 2 : 1, isFiltered ? 'Volume_01' : 'default'),
        history: summary(isFiltered ? 55 : 275, 2, isFiltered ? 'Volume_01' : 'default'),
        metadata_snapshot: summary(isFiltered ? 0 : 10, isFiltered ? 0 : 3, isFiltered ? 'default' : 'Volume_02'),
        coverage: {
          known_chapters: 3, history_chapters: 2, trace_snapshot_chapters: 0,
          snapshot_only_chapters: 1, history_complete: false,
        },
      },
    });
  });

  await page.goto('/');
  await page.getByRole('button', { name: 'Traces', exact: true }).click();
  await page.getByRole('button', { name: 'Project Analytics', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Project Token Analysis' })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Select chapter trace' })).toHaveCount(0);
  await expect(page.getByText('285', { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/history is incomplete/i)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Metadata snapshots with recorded usage' })).toBeVisible();
  await expect(page.getByText(/Metadata-only snapshot: 10 tokens across 1 chapter with recorded step usage/)).toBeVisible();
  await expect(page.getByRole('columnheader', { name: 'Thought' }).first()).toBeVisible();
  await expect(page.getByRole('columnheader', { name: 'Cached' }).first()).toBeVisible();

  await page.getByRole('combobox', { name: 'Filter by volume folder' }).selectOption('Volume_01');
  await expect(page.getByText('55', { exact: true }).first()).toBeVisible();
  expect(requestedFolders).toContain('Volume_01');
});
