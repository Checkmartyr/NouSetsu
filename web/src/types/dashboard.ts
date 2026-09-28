export type WorkspaceTab = 'studio' | 'reader' | 'bible' | 'traces' | 'settings';

export interface ChapterItem {
  chapter_num: number;
  title: string;
  file_name: string;
  output_file_name?: string;
  folder: string | null;
  status: 'COMPLETED' | 'FAILED' | 'PAUSED' | 'RESUME' | 'PENDING';
  current_stage: string;
  raw_exists: boolean;
  raw_lines: number;
  raw_words: number;
  translated_exists: boolean;
  translated_words: number;
  is_completed: boolean;
  has_checkpoint: boolean;
  quality_audit?: {
    fidelity_score?: number;
    style_score?: number;
    critique_notes?: string[];
  } | null;
}

export interface ChapterContent {
  chapter_num: number;
  folder: string | null;
  source_file: string;
  output_file: string;
  output_file_name?: string;
  source_text: string;
  translated_text: string;
  has_source: boolean;
  has_translated: boolean;
}

export interface TranslationStatus {
  is_running: boolean;
  active_chapter: number | null;
  active_folder: string | null;
  active_stage: string | null;
  completed_count: number;
  total_count: number;
  paused_reason: string | null;
  last_log: string | null;
}

export interface CharacterNameDetail {
  name?: string;
  m_name?: string;
  s_name?: string;
}

export interface CharacterNames {
  source?: CharacterNameDetail;
  target?: CharacterNameDetail;
}

export interface BibleCharacter {
  name: string;
  original_name: string;
  names?: CharacterNames;
  gender?: string;
  role?: string;
  speaking_style?: string;
  voice?: string;
  summary?: string;
  aliases?: string[];
  power_level?: string;
  status?: string;
  relationships?: Record<string, string>;
  pronouns?: {
    source?: string;
    target?: string;
    relational?: Record<string, string>;
  } | string;
}

export interface BibleTerm {
  term?: string;
  translation?: string;
  source?: string;
  target?: string;
  category?: string;
  notes?: string;
}

export interface BibleArc {
  arc_id?: string;
  arc_num?: number;
  arc_number?: number;
  title?: string;
  arc_title?: string;
  synopsis?: string;
  summary?: string;
  core_conflict?: string;
  status?: string;
  start_chapter?: number;
  end_chapter?: number | null;
  folder?: string | null;
  key_milestones?: string[];
}

export interface BibleData {
  title: string;
  source_language: string;
  target_language: string;
  genre: string;
  writing_style?: string;
  whole_story_summary?: string;
  characters: BibleCharacter[];
  glossary: BibleTerm[];
  active_arc?: BibleArc;
  archived_arcs?: BibleArc[];
}

export interface ModelPreset {
  id: string;
  name: string;
  description: string;
  models: {
    model_name?: string;
    fallback_model?: string;
    extractor_model?: string;
    drafter_model?: string;
    critic_model?: string;
    polisher_model?: string;
    chronicler_model?: string;
    [key: string]: string | undefined;
  };
}

export interface MachineEnvironment {
  env_file_path: string;
  values: Record<string, string>;
  api_key_status: Record<string, boolean>;
}

export interface UpdateReleaseAsset {
  name: string;
  download_url: string;
  size?: number;
}

export interface UpdateCheckResult {
  current_version: string;
  latest_version: string;
  update_available: boolean;
  release_name: string;
  release_notes: string;
  release_url: string;
  published_at?: string | null;
  assets: UpdateReleaseAsset[];
}

export interface ProjectSettings {
  // General & Project Metadata
  project_id?: string;
  title?: string;
  genre?: string;
  source_language?: string;
  target_language?: string;
  created_at?: string;

  // Workspace Paths
  raw_dir?: string;
  output_dir?: string;
  translated_dir?: string;

  // Model Routing & Cascades
  model_name?: string;
  fallback_model?: string;
  extractor_model?: string;
  drafter_model?: string;
  critic_model?: string;
  polisher_model?: string;
  chronicler_model?: string;
  use_interactions_api?: boolean;

  // Presets & Catalogs
  effective_model_name?: string;
  effective_fallback_model?: string;
  effective_extractor_model?: string;
  effective_drafter_model?: string;
  effective_critic_model?: string;
  effective_polisher_model?: string;
  effective_chronicler_model?: string;
  env_presets?: Record<string, string>;
  available_presets?: ModelPreset[];
  model_catalog?: string[];

  // Reflection Review & Polishing
  max_review_loops?: number;
  quality_threshold?: number;
  enable_patch_polishing?: boolean;

  // Semantic Chunking
  enable_chunking?: boolean;
  chunk_threshold_lines?: number | '';
  chunk_size_lines?: number | '';
  target_chunk_lines?: number | '';
  chunk_overlap_lines?: number | '';

  // Memory, Bible & Multi-Folder
  auto_update_bible?: boolean;
  cross_folder_summaries?: boolean;
  filter_scene_characters?: boolean;
  filter_extractor_entities?: boolean | null;
  enable_post_polish_reconciliation?: boolean;

  // Episodic Lore & Hybrid RAG (Tier 4)
  enable_rag?: boolean;
  rag_top_k?: number;
  rag_embedding_model?: string;
  enable_rag_reranker?: boolean;
  rag_reranker_model?: string;

  // AI Safety & Subdivision
  safety_recursive_subdivision?: boolean;
  safety_subdivision_min_lines?: number | '';
  safety_subdivision_max_depth?: number | '';

  // Rate Limiting & Quotas
  max_tpm?: number | '';
  max_rpm?: number | '';

  [key: string]: any;
}

export interface TranslatedFolderItem {
  folder: string;
  name: string;
  chapter_count: number;
  is_default?: boolean;
}

export interface ProjectFoldersResult {
  default_folder: string;
  folders: string[];
  default_translated_folder?: string;
  translated_folders?: TranslatedFolderItem[];
}

export interface UploadChaptersResult {
  success: boolean;
  folder: string;
  uploaded: string[];
  skipped: string[];
  total_uploaded: number;
  total_skipped: number;
  message: string;
}

export interface ScraperCheckResult {
  available: boolean;
  scraper_dir: string | null;
  python_exe: string | null;
}

export interface ScraperChapterPreview {
  index: number;
  title: string;
  url: string;
}

export interface ScraperInspectResult {
  success: boolean;
  url: string;
  page_type?: string;
  novel_title: string;
  romanized_title?: string | null;
  author?: string | null;
  description?: string | null;
  total_chapters: number;
  chapters: ScraperChapterPreview[];
  error?: string | null;
}

export interface ScraperExtractParams {
  url: string;
  projectPath?: string;
  folder?: string;
  chapterIndices?: number[];
  startChapter?: number;
  endChapter?: number;
  concurrency?: number;
  includeFrontmatter?: boolean;
  overwrite?: boolean;
}

export interface ScraperExtractResult {
  success: boolean;
  task_id: string;
  message: string;
  folder: string;
}

export interface ScraperStatusResult {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress_percent: number;
  current_chapter: number;
  total_chapters: number;
  current_title?: string | null;
  message: string;
  completed_files: string[];
  output_dir?: string | null;
  error?: string | null;
}

export interface EbookInspectChapterItem {
  index: number;
  title: string;
  word_count: number;
  has_images: boolean;
}

export interface EbookInspectResult {
  title: string;
  author?: string | null;
  format: 'epub' | 'pdf';
  total_chapters: number;
  chapters: EbookInspectChapterItem[];
  has_cover: boolean;
  cover_base64?: string | null;
}

export interface EbookImportParams {
  project_path?: string;
  folder?: string;
  start_chapter?: number;
  end_chapter?: number;
  selected_indices?: string;
  overwrite?: boolean;
  extract_images?: boolean;
}

export interface EbookImportResult {
  success: boolean;
  imported_count: number;
  folder: string;
  files: string[];
  message: string;
}

export interface EbookExportOptions {
  project_path?: string;
  format?: 'epub' | 'pdf' | 'html';
  folder?: string;
  title?: string;
  author?: string;
  include_bible_appendix?: boolean;
  include_images?: boolean;
  apply_thai_word_wrap?: boolean;
  soft_wrap_thai?: boolean;
  font_family?: string;
  font_size?: number;
  line_height?: number;
  page_size?: 'A5' | 'A4' | 'B6';
  custom_css?: string;
  preview_chapter_index?: number;
}

export interface EbookPreviewChapterItem {
  index: number;
  title: string;
  word_count: number;
  has_images: boolean;
  source_file?: string | null;
}

export interface EbookPreviewResult {
  title: string;
  author?: string | null;
  language: string;
  total_chapters: number;
  total_words: number;
  has_cover: boolean;
  cover_base64?: string | null;
  toc: EbookPreviewChapterItem[];
  sample_chapter_index: number;
  sample_chapter_title: string;
  sample_chapter_html: string;
  sample_chapter_text: string;
}




