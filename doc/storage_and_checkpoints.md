# 💾 Storage & Checkpoint Architecture

This document describes the filesystem layout, single project metadata architecture, checkpointing mechanism, and error diagnostic logs implemented in **NouSetsu**.

---

## 📂 Project Filesystem Layout

Each novel project managed by NouSetsu contains the following structure:

```
<project_root>/
├── .novel/                         # Hidden project configuration & storage
│   ├── config.yaml                 # Folder paths, languages, model settings
│   ├── metadata.json               # Consolidated single metadata document
│   ├── bible/
│   │   └── bible.yaml              # Novel Bible (characters, glossary, style guide)
│   └── summaries/
│       ├── chapter_0001.json       # Episodic chapter synopses
│       └── chapter_0002.json
├── raw_chapters/                   # Input folder (user-configurable name)
│   ├── 001 - Awakening.txt
│   └── 002 - Magic Beast.txt
└── translated_chapters/            # Output folder (clean .md translations only)
    ├── 001 - Awakening.md
    └── 002 - Magic Beast.md
```

---

## 📦 Single Project Metadata Architecture (`.novel/metadata.json`)

### Why Consolidate into a Single File?
In early versions, every translated chapter output an accompanying `.meta.json` file in the output directory (e.g. `001.md` and `001.meta.json`). For a 122-chapter novel, this cluttered the output folder with 244 files. Furthermore, discovering chapter statuses required opening and parsing 122 individual JSON files on disk.

In NouSetsu, all chapter metadata is stored in a single, high-performance project document located at `.novel/metadata.json`.

```mermaid
flowchart TD
    subgraph Output_Directory ["translated_chapters/ (Clean)"]
        MD1["001_Chapter 1.md"]
        MD2["002_Chapter 2.md"]
        MDN["... (No .meta.json clutter)"]
    end

    subgraph Project_Storage [".novel/"]
        Config["config.yaml"]
        Bible["bible/bible.yaml"]
        Doc[".novel/metadata.json (ProjectMetadataDocument)"]
    end

    Doc --> Ch1["chapters['001_Chapter 1']: ChapterMetadata"]
    Doc --> Ch2["chapters['002_Chapter 2']: ChapterMetadata"]
    
    Scanner["ChapterScanner.scan_directory()"] -->|Single File Read| Doc
```

### Performance Benefits
* **Clean Output Folders**: Output folders contain only publication-ready `.md` translations.
* **Instant Batch Scanning**: The `ChapterScanner` reads `.novel/metadata.json` once, reducing I/O operations from $O(N)$ file reads to $O(1)$.
* **Atomic Updates**: Updates to individual chapters are written safely with zero cross-chapter lock contention.

### Document Structure Example (`.novel/metadata.json`)
```json
{
  "schema_version": "1.0",
  "project_id": "villainess_001",
  "last_updated": "2026-09-11T12:00:00Z",
  "chapters": {
    "001 - Awakening": {
      "chapter_id": "001 - Awakening",
      "chapter_num": 1,
      "source_file": "raw_chapters/001 - Awakening.txt",
      "source_sha256": "3a7b9c...",
      "output_file": "translated_chapters/001 - Awakening.md",
      "stats": {
        "duration_seconds": 4.1,
        "input_tokens": 820,
        "output_tokens": 364,
        "thought_tokens": 100,
        "cached_tokens": 0,
        "total_tokens": 1284,
        "step_usage": [
          {"stage": "extracting", "step_name": "Entity Extraction", "iteration": 1, "duration_seconds": 0.52, "model": "gemini-3.1-flash-lite", "usage": {"input_tokens": 200, "output_tokens": 50, "thought_tokens": 0, "cached_tokens": 0, "total_tokens": 250}},
          {"stage": "drafting", "step_name": "Context-Aware Drafting", "iteration": 1, "duration_seconds": 1.25, "model": "gemini-3.5-flash-lite", "usage": {"input_tokens": 220, "output_tokens": 120, "thought_tokens": 0, "cached_tokens": 0, "total_tokens": 340}},
          {"stage": "critiquing", "step_name": "Critique Audit (Pass 1)", "iteration": 1, "duration_seconds": 0.88, "model": "gemma-4-26b-a4b-it", "usage": {"input_tokens": 150, "output_tokens": 74, "thought_tokens": 50, "cached_tokens": 0, "total_tokens": 274}},
          {"stage": "polishing", "step_name": "Prose Polishing (Pass 1)", "iteration": 1, "duration_seconds": 1.10, "model": "gemini-3.5-flash-lite", "usage": {"input_tokens": 180, "output_tokens": 80, "thought_tokens": 50, "cached_tokens": 0, "total_tokens": 310}},
          {"stage": "chronicling", "step_name": "Lore Chronicling", "iteration": 1, "duration_seconds": 0.35, "model": "gemma-4-26b-a4b-it", "usage": {"input_tokens": 70, "output_tokens": 40, "thought_tokens": 0, "cached_tokens": 0, "total_tokens": 110}}
        ]
      },
      "checkpoint": {
        "status": "COMPLETED",
        "last_completed_stage": "CHRONICLING",
        "retry_count": 0
      }
    }
  }
}
```

---

## 🔄 Automatic Legacy Migration

To ensure 100% backward compatibility, `NovelRepository.load_metadata()` includes automatic transparent migration:

1. When loading metadata for an output file, `NovelRepository` first inspects `.novel/metadata.json`.
2. If the chapter is not found, it checks for a legacy `<output_file.stem>.meta.json` file in the output folder.
3. If found, it automatically ingests the legacy metadata into `.novel/metadata.json`, writes the project document, and returns the metadata.
4. Legacy files can then be safely deleted without losing any checkpoint history or audit scores.

---

## 📑 Checkpoint Schema & State Machine

Each chapter tracks its progression through a `CheckpointData` object:

```mermaid
stateDiagram-v2
    [*] --> PENDING: Initial Scan
    PENDING --> IN_PROGRESS: Batch Runner Starts
    IN_PROGRESS --> EXTRACTION: Stage 1 Completed
    EXTRACTION --> DRAFTING: Stage 2 Completed
    DRAFTING --> CRITIQUE: Stage 3 Completed
    CRITIQUE --> POLISHING: Stage 4 Completed
    POLISHING --> CHRONICLING: Stage 5 Completed
    CHRONICLING --> COMPLETED: Final Output Written
    
    IN_PROGRESS --> PAUSED: User Stop Signal (X key / Ctrl+C)
    EXTRACTION --> PAUSED: Stop Signal
    DRAFTING --> PAUSED: Stop Signal
    CRITIQUE --> PAUSED: Stop Signal
    POLISHING --> PAUSED: Stop Signal
    PAUSED --> IN_PROGRESS: Resume Selected (T / B)

    IN_PROGRESS --> FAILED: Unrecoverable Error
    EXTRACTION --> FAILED: Unrecoverable Error
    DRAFTING --> FAILED: Unrecoverable Error
    CRITIQUE --> FAILED: Unrecoverable Error
    POLISHING --> FAILED: Unrecoverable Error
    CHRONICLING --> FAILED: Unrecoverable Error
    
    FAILED --> IN_PROGRESS: Retry Selected (T / B)
```

### `CheckpointData` Pydantic Model
```python
class CheckpointData(BaseModel):
    status: StageStatus = Field(default=StageStatus.PENDING)
    last_completed_stage: PipelineStage = Field(default=PipelineStage.NONE)
    failed_stage: Optional[PipelineStage] = None
    last_error_type: Optional[str] = None
    last_error: Optional[str] = None
    last_error_traceback: Optional[str] = None
    retry_count: int = Field(default=0)
    stage_artifacts: StageArtifacts = Field(default_factory=StageArtifacts)
    error_logs: List[ErrorLogEntry] = Field(default_factory=list)

    def is_resumable(self) -> bool:
        """Returns True if chapter was paused or failed and has intermediate artifacts."""
        return self.status in [StageStatus.PAUSED, StageStatus.FAILED] and bool(
            self.stage_artifacts.draft_text or self.stage_artifacts.extracted_characters
        )
```

### `StageArtifacts` Model
Preserves intermediate outputs so cancelled or paused runs never lose completed work:
* `extracted_characters`: List of character profiles identified in Stage 1.
* `extracted_terms`: Glossary items identified in Stage 1.
* `draft_text`: Complete raw draft generated in Stage 2.
* `critique_notes`: Audit feedback generated in Stage 3.
* `polished_text`: Best literary prose candidate generated in Stage 4.

---

## 🚨 Error Diagnostics & Stack Trace Logging

When translation encounters an unrecoverable failure (or exhausts its exponential backoff retries), NouSetsu captures complete forensic diagnostics.

### `ErrorLogEntry` Schema
```python
class ErrorLogEntry(BaseModel):
    timestamp: str          # ISO 8601 UTC timestamp
    stage: PipelineStage    # Stage where failure occurred (e.g. PipelineStage.CRITIQUE)
    error_type: str         # Exception class name (e.g. 'InternalServerError')
    message: str            # Detailed error message string
    traceback: Optional[str]# Full Python traceback via traceback.format_exc()
    retry_attempt: int      # Number of retries attempted
    model: Optional[str]    # Model name in use (e.g. 'gemini-2.5-pro')
    details: Dict[str, Any] # Upstream API diagnostic payload
```

### Inspected in TUI Checkpoint Inspector
When a chapter fails, the TUI immediately renders:
* **Sidebar Badge**: Minimal red glyph `✕` (`[bold red]✕[/]`)
* **Inspector Status**: `Status: FAILED (InternalServerError)`
* **Failed Stage**: `Failed at: CRITIQUE`
* **Error Message Snippet**: `❌ 500 INTERNAL: Internal error encountered...`
* **Log Count & Retries**: `(Retries: 3, Logs: 1)`

Users can press `T` to retry failed chapters immediately from the exact failure stage.
