import { test, expect } from '@playwright/test';
import { dirtySettings, dirtyValues, refreshDraft } from '../src/services/settingsDraft';

test('dirty patches exclude derived fields and preserve false, zero, and reset values', () => {
  const baseline = { title: 'Old', revision: 'r1', max_tpm: 100, enable_rag: true, chunk_overlap_lines: 3 };
  expect(dirtySettings({...baseline, title: 'New', revision: 'r2', effective_model_name: 'mock', enable_rag: false, chunk_overlap_lines: 0, max_tpm: null}, baseline)).toEqual({title: 'New', enable_rag: false, chunk_overlap_lines: 0, max_tpm: null});
});
test('blank chunk fields use display defaults while inherited fields reset', () => {
  expect(dirtySettings({chunk_threshold_lines: '', chunk_size_lines: '', max_tpm: '', max_rpm: ''}, {chunk_threshold_lines: 900, chunk_size_lines: 450, max_tpm: 100, max_rpm: 10})).toEqual({chunk_threshold_lines: 800, chunk_size_lines: 400, max_tpm: null, max_rpm: null});
});
test('generation resets replace the map without sending unchanged metadata', () => {
  const baseline = {generation_settings: {drafter: {temperature: 1}}, title: 'Existing', config: {title: 'Existing'}};
  expect(dirtySettings({...baseline, generation_settings: {}}, baseline)).toEqual({generation_settings: {}});
});
test('global saves only changed values including explicit clearing', () => {
  expect(dirtyValues({NOVEL_MODEL: '', NOVEL_MAX_RPM: '0', SOURCE_LANG: 'Japanese'}, {NOVEL_MODEL: 'mock', NOVEL_MAX_RPM: '60', SOURCE_LANG: 'Japanese'})).toEqual({NOVEL_MODEL: '', NOVEL_MAX_RPM: '0'});
});

test('refresh updates effective defaults without rebasing a stale dirty revision', () => {
  const baseline = {title: 'Original', revision: 'old', effective_model_name: 'mock-old'};
  const refreshed = refreshDraft({...baseline, title: 'Draft'}, baseline, {title: 'External edit', revision: 'new', effective_model_name: 'mock-new'});
  expect(refreshed.draft.title).toBe('Draft');
  expect(refreshed.draft.effective_model_name).toBe('mock-new');
  expect(refreshed.baseline.revision).toBe('old');
  expect(refreshed.conflict).toBe(true);
});
