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
    
    IN_PROGRESS --> FAILED: Unrecoverable Error
    EXTRACTION --> FAILED: Unrecoverable Error
    DRAFTING --> FAILED: Unrecoverable Error
    CRITIQUE --> FAILED: Unrecoverable Error
    POLISHING --> FAILED: Unrecoverable Error
    CHRONICLING --> FAILED: Unrecoverable Error
    
    FAILED --> IN_PROGRESS: Resume / Retry Selected
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
```

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
* **Sidebar Badge**: `[bold red][FAILED][/]`
* **Inspector Status**: `Status: FAILED (InternalServerError)`
* **Failed Stage**: `Failed at: CRITIQUE`
* **Error Message Snippet**: `❌ 500 INTERNAL: Internal error encountered...`
* **Log Count & Retries**: `(Retries: 3, Logs: 1)`

Users can press `T` to retry failed chapters immediately from the exact failure stage.
