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

export interface ProjectSettings {
  title?: string;
  genre?: string;
  source_language?: string;
  target_language?: string;
  raw_dir?: string;
  translated_dir?: string;
  model_name?: string;
  fallback_model?: string;
  max_review_loops?: number;
  quality_threshold?: number;
  chunk_threshold_lines?: number;
  chunk_size_lines?: number;
  chunk_overlap_lines?: number;
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

