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

export interface BibleCharacter {
  name: string;
  original_name: string;
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
  arc_number?: number;
  arc_title?: string;
  summary?: string;
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

export interface ProjectFoldersResult {
  default_folder: string;
  folders: string[];
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

