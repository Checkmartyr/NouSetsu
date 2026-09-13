export type PipelineStage = 'extraction' | 'drafting' | 'critique' | 'polishing' | 'chronicling';
export type TraceStatus = 'success' | 'error' | 'safety_blocked';

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  thought_tokens: number;
  cached_tokens: number;
  total_tokens: number;
}

export interface AgentPromptTrace {
  trace_id: string;
  timestamp: string;
  chapter_id: string;
  chapter_num: number;
  folder: string | null;
  stage: PipelineStage;
  agent: string;
  model: string;
  iteration: number;
  chunk_index: number;
  total_chunks: number;
  depth: number;
  system_prompt: string;
  user_prompt: string;
  raw_output: string | null;
  parsed_output: Record<string, any> | null;
  token_usage: TokenUsage;
  duration_seconds: number;
  status: TraceStatus;
  error_message: string | null;
  metadata: Record<string, any>;
}

export interface ChapterTraceDocument {
  chapter_id: string;
  chapter_num: number;
  folder: string | null;
  created_at?: string;
  total_interactions: number;
  total_duration_seconds: number;
  total_token_usage?: TokenUsage;
  stage_breakdown?: Record<string, number>;
  traces: AgentPromptTrace[];
}

export interface LoadedChapter {
  id: string; // e.g. "Villainess_05/chapter_0001" or "chapter_0001"
  fileName: string;
  folder: string | null;
  chapterNum: number;
  document: ChapterTraceDocument;
}

export interface ProjectMeta {
  path: string;
  name: string;
  title: string;
  genre: string;
  source_language: string;
  target_language: string;
  has_traces: boolean;
  trace_count: number;
  latest_trace_mtime: number;
  is_active?: boolean;
}

export interface ActiveProjectResponse {
  active_project: ProjectMeta | null;
  projects: ProjectMeta[];
}

export interface SyncState {
  active_project_path: string | null;
  active_project_title: string | null;
  traces_count: number;
  latest_trace_mtime: number;
}

export interface ProjectTracesResponse {
  project_path: string;
  project_title: string;
  genre: string;
  chapters: LoadedChapter[];
}

