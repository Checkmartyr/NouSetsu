import type { ProjectSettings } from '../types/dashboard';
const readOnly = new Set(['config', 'env', 'machine_env', 'api_key_status', 'env_file_path', 'revision', 'sources', 'effective_config', 'available_presets', 'env_presets', 'model_catalog', 'created_at', 'workspace_folders']);
const numericDefaults: Record<string, number> = {chunk_threshold_lines: 800, chunk_size_lines: 400, target_chunk_lines: 400, chunk_overlap_lines: 3, safety_subdivision_min_lines: 8, safety_subdivision_max_depth: 4, rag_top_k: 2};
const inheritedNumbers = new Set(['max_review_loops', 'quality_threshold', 'max_tpm', 'max_rpm', 'procedural_learning_interval', 'procedural_learning_min_failures']);
export function dirtySettings(draft: ProjectSettings, baseline: ProjectSettings): Partial<ProjectSettings> {
  return Object.fromEntries(Object.entries(draft).filter(([key, value]) => !readOnly.has(key) && !key.startsWith('effective_') && JSON.stringify(value) !== JSON.stringify(baseline[key])).map(([key, value]) => [key, value === '' && key in numericDefaults ? numericDefaults[key] : value === '' && inheritedNumbers.has(key) ? null : value]));
}
export function dirtyValues(draft: Record<string, string>, baseline: Record<string, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(draft).filter(([key, value]) => value !== baseline[key]));
}

export function refreshDraft(draft: ProjectSettings, baseline: ProjectSettings, fresh: ProjectSettings) {
  const dirty = dirtySettings(draft, baseline);
  const hasEdits = Object.keys(dirty).length > 0;
  return {draft: {...fresh, ...dirty}, baseline: hasEdits ? baseline : fresh, conflict: hasEdits && baseline.revision !== fresh.revision};
}
