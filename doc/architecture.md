# 🏛️ System Architecture & Component Design

This document details the software architecture, design patterns, and layer separation of **NouSetsu**. The system is built with clean architecture principles to ensure decoupling between LLM providers, multi-agent orchestration, local persistence, and user interfaces.

---

## 🏗️ Layered Architecture Diagram

```mermaid
graph TD
    subgraph Presentation_Layer ["Presentation Layer (UI / CLI)"]
        TUI["Textual TUI Application<br/>(DualReader, ProgressPanel, Token Analytics M, Volume F, Stop X)"]
        CLI["Rich CLI Commands<br/>(init, batch, tui, narrative, migrate-summaries, graph-info, skills)"]
    end

    subgraph Batch_Orchestration ["Batch & Task Orchestration"]
        Scanner["ChapterScanner<br/>(natsort, SHA256, load_all_metadata)"]
        Runner["BatchRunner<br/>(sequential loop, stop_event, checkpoints, Rich progress)"]
    end

    subgraph Workflow_Layer ["Agentic Workflow Layer (LangGraph & Procedural Graphs)"]
        Workflow["NovelTranslationWorkflow<br/>(StateGraph, Review Reflection Loop, stage callbacks)"]
        State["TranslationState<br/>(source, draft, critique, polish, 3-tier Bible memory, best candidate)"]
        PG["ProceduralGraph & Refiner<br/>(G=(V,R,E,Phi), deterministic localization, Name_Discipline, offline self-evolution)"]
    end

    subgraph Agent_Layer ["Specialized Agent Layer (German Designations)"]
        Extractor["Stage 1: Schriftdetektiv<br/>(EntityExtractorAgent + Scan_Candidates PG)"]
        Drafter["Stage 2: Wortschmied<br/>(ContextAwareDrafterAgent + Chunk-Aware PG)"]
        Critic["Stage 3: Zensor<br/>(CritiqueAgent + Nickname Auditor)"]
        Polisher["Stage 4: Feinschliff<br/>(PolishingAgent + Cadence Engine)"]
        Chronicler["Stage 5: Chronist<br/>(ChroniclerAgent + 3-Tier Hierarchy Generator)"]
        LLM["LLM Client & FallbackChatModel<br/>(Per-Role Model Routing, 429 Automatic Failover)"]
    end

    subgraph Utility_Layer ["Foundational Utilities (src/nousetsu/utils/)"]
        RateLimiter["SlidingWindowRateLimiter<br/>(32K TPM / 60 RPM, rolling window, 429 backoff)"]
        Chunker["LineSemanticChunker<br/>(85-line threshold, 70 target, 3 overlap)"]
        TokenEstimator["estimate_tokens<br/>(offline CJK 1.7 / Latin 1.3 weights)"]
        LangDetector["detect_language<br/>(Unicode script & lexical analysis)"]
        Formatter["format_duration<br/>(human-friendly step duration display)"]
        TokenMetrics["TokenTracker<br/>(prompt, completion, thought, cached tokens)"]
    end

    subgraph Storage_Layer ["Persistence & Storage Layer"]
        Repo["NovelRepository<br/>(bible.yaml, .novel/metadata.json, summaries, arcs)"]
        Registry["ProjectRegistry<br/>(multi-project paths, last active project)"]
        Migrator["SummaryMigrationEngine<br/>(migrate_novel_summaries, 3-tier synthesis)"]
    end

    subgraph Domain_Models ["Domain & Schema Layer (Pydantic)"]
        M_Bible["NovelBible, CharacterProfile, GlossaryItem"]
        M_Meta["ChapterMetadata, CheckpointData, ErrorLogEntry, ArcSummary"]
        M_Config["ProjectConfig, StyleGuideConfig"]
        M_PG["ProceduralNode, ProceduralEdge, DiagnosticTrace"]
    end

    %% Dependencies
    TUI --> Runner
    CLI --> Runner
    Runner --> Scanner
    Runner --> Workflow
    Scanner --> LangDetector
    Runner --> RateLimiter
    Workflow --> State
    Workflow --> PG
    Workflow --> Extractor
    Workflow --> Drafter
    Workflow --> Critic
    Workflow --> Polisher
    Workflow --> Chronicler
    Workflow --> RateLimiter
    Workflow --> TokenMetrics
    PG --> Extractor
    PG --> Drafter
    Critic -.->|"Audit Traces"| PG
    Drafter --> Chunker
    Polisher --> Chunker
    RateLimiter --> TokenEstimator
    Extractor --> LLM
    Drafter --> LLM
    Critic --> LLM
    Polisher --> LLM
    Chronicler --> LLM
    LLM --> RateLimiter
    Runner --> Repo
    Scanner --> Repo
    Migrator --> Repo
    TUI --> Registry
    TUI --> Repo
    Repo --> Domain_Models
    Workflow --> Domain_Models
```

---

## 🧩 Architectural Layers & Responsibilities

### 1. Presentation Layer (`src/nousetsu/tui/`, `src/nousetsu/cli/`)
* **Textual TUI (`src/nousetsu/tui/app.py`)**: An asynchronous terminal application powered by `textual`. Renders side-by-side original and translated chapter views, reactive status badges (`[DONE]`, `[FAILED]`, `[RESUME]`, `[PAUSED]`, `[WAIT]`), a live 5-stage progress visualizer with chapter name display, dedicated **Stop Translation (`X`)** controls, volume folder switcher modal (`F`), Token Analysis modal (`M`), and tabs for editing the Novel Bible, inspecting 3-tier summaries, and switching projects.
* **Rich CLI (`src/nousetsu/cli/app.py`)**: Command-line entry points for headless execution:
  * `nousetsu batch`: Batch chapter translation with limit, genre, and volume routing.
  * `nousetsu narrative`: Inspects 3-tier macro, meso, and micro narrative memory tree.
  * `nousetsu migrate-summaries`: Upgrades legacy flat summaries into 3-tier arc hierarchies.
  * `nousetsu graph-info`: Visualizes procedural execution graphs and name discipline directives.
  * `nousetsu skills`: Inspects, filters, and validates the 20-skill catalog.

### 2. Batch & Scanning Layer (`src/nousetsu/batch/`)
* **`ChapterScanner`**: Discovers raw chapter files (`.txt`, `.md`), applies natural numerical sorting (`1, 2, 10`), computes SHA-256 checksums to detect file changes, triggers auto source language detection, supports multi-folder novel structures, and performs a single I/O read of `.novel/metadata.json` for instantaneous project discovery.
* **`BatchRunner`**: Sequentially translates chapters, passes updated Novel Bible state forward, manages resumption checkpoints, manages thread-safe `stop()` and `reset_stop()` signals, and coordinates rate limits.

### 3. Agentic Workflow & Procedural Graph Layer (`src/nousetsu/graph/`)
* **`NovelTranslationWorkflow`**: Compiles a LangGraph `StateGraph` featuring an automated **Reflection Review Loop** between `Feinschliff` and `Zensor`:
  * Evaluates fidelity and style quality thresholds (`>= 8.5/10`).
  * Employs an automated **Best-Candidate Regression Guard** to retain the highest-scoring candidate if subsequent passes degrade.
  * Emits fine-grained progress notifications (`stage_callback`) to update the TUI and CLI in real time.
  * Wraps all agent invocations with `invoke_with_retry` and rate-limit acquisitions.
* **Procedural Graph Engine (`src/nousetsu/graph/procedural.py`)**: Attributed directed graph $G = (V, R, E, \Phi)$ formalizing procedural execution knowledge (Lu et al., arXiv:2609.09153v1). Provides deterministic code-level localization without online guidance LLM token bloat. Features `Name_Discipline` for enforcing formal-vs-diminutive address rules.
* **Offline Refiner (`src/nousetsu/graph/pg_refiner.py`)**: Analyzes chapter critique audit traces offline to propose mutations (add/update/delete edge pitfalls and guidance), gated by structural verification and rejection memory with zero live inference token cost.

### 4. Specialized Agent Layer (`src/nousetsu/agents/`)
Each agent possesses a single cognitive responsibility:
* **Stage 1: `EntityExtractorAgent` (*Schriftdetektiv*)**: Discovers unknown character names, spells, items, and titles before drafting. Steered by `Scan_Candidates` procedural graph directives with anti-bloat term pruning.
* **Stage 2: `ContextAwareDrafterAgent` (*Wortschmied*)**: First-pass translation with zero-anaphora subject inference, character voice registers, nickname discipline, and 3-tier hierarchical narrative injection (Macro whole-story + Meso arc + Micro rolling chapters with volume badges). Localizes procedural state to `Scene_Init` for chunk 1 and `Boundary_Continuity` for subsequent chunks. Integrates `LineSemanticChunker` for long chapters.
* **Stage 3: `CritiqueAgent` (*Zensor*)**: Line-by-line fidelity and stylistic auditing, generating scores and remediation notes. Audits nickname disparity and skipped lines.
* **Stage 4: `PolishingAgent` (*Feinschliff*)**: High-cadence prose refinement, address form preservation, and translationese elimination across semantic chunks.
* **Stage 5: `ChroniclerAgent` (*Chronist*)**: Generates episodic chapter summaries, evaluates arc progression and milestone climaxes, updates macro `whole_story_summary`, and archives completed story arcs into `.novel/summaries/arcs/`.
* **Per-Role Model Routing & `FallbackChatModel` (`src/nousetsu/agents/llm.py`)**: Resolves specialized models per stage (`extractor_model`, `drafter_model`, `critic_model`, `polisher_model`, `chronicler_model`), stripping thought tokens and automatically failing over to `fallback_model` when encountering HTTP 429 quota exhaustion.

### 5. Foundational Utility Layer (`src/nousetsu/utils/`)
* **`SlidingWindowRateLimiter` (`src/nousetsu/utils/rate_limiter.py`)**: Tracks requests and tokens across a rolling 60-second window, enforcing 32,000 TPM and 60 RPM limits with interruptible sleeps.
* **`LineSemanticChunker` (`src/nousetsu/utils/chunker.py`)**: Partitions chapters over 85 lines into ~70-line semantic chunks with 3-line boundary overlap, maintaining scene breaks and quote continuity.
* **`format_duration` (`src/nousetsu/utils/formatting.py`)**: Human-friendly duration display formatting (`3.9s`, `2m 15s`, `1h 4m`).
* **`estimate_tokens` (`src/nousetsu/utils/rate_limiter.py`)**: Offline token estimation assigning ~1.7 tokens per CJK character and ~1.3 tokens per Latin word.
* **`detect_language` (`src/nousetsu/utils/language.py`)**: Zero-dependency Unicode script and stop-word frequency analyzer recognizing Japanese, Chinese, Korean, Thai, Russian, and Latin languages.
* **`TokenTracker` (`src/nousetsu/utils/token_metrics.py`)**: Tracks prompt, completion, thought, and cached tokens across every pipeline step.

### 6. Persistence & Storage Layer (`src/nousetsu/storage/`)
* **`NovelRepository`**: Manages all file system persistence for a project:
  * `.novel/config.yaml`: Language pair, raw/output folders, rate limits, review loop caps, and per-agent model preferences.
  * `.novel/bible/bible.yaml`: Characters, glossary, and style guide.
  * `.novel/metadata.json`: Consolidated single metadata document storing all chapter checkpoints, quality audit scores, step durations, token breakdowns, and paused stage artifacts.
  * `.novel/summaries/<volume>/`: Historical episodic chapter summaries partitioned by volume folder.
  * `.novel/summaries/arcs/`: Archived Meso-tier story arc summaries (`arc_XXXX.json`).
* **`ProjectRegistry`**: Stores user-registered project directories across arbitrary filesystem locations and persists the `last_active_project` for instant reopening.
* **`SummaryMigrationEngine` (`src/nousetsu/storage/migration.py`)**: Automatically detects and migrates legacy flat summaries into the 3-tier hierarchy (`whole_story_summary` -> `ArcSummary` -> partitioned volume summaries).

### 7. Domain Model Layer (`src/nousetsu/models/`)
* Strongly typed Pydantic V2 models defining contracts across the entire system (`TranslationState`, `NovelBible`, `ChapterMetadata`, `ArcSummary`, `ProjectConfig`).

---

## 🔒 Error Handling, Quota Management & Cancellation

NouSetsu is engineered for enterprise reliability over massive web novel series:

```mermaid
flowchart TD
    Call["Execute Agent Stage"] --> Limiter["SlidingWindowRateLimiter.acquire()<br/>(Wait if projected TPM > 32k or RPM > 60)"]
    Limiter --> CheckStop{"Stop Event Set?<br/>(X Key or Ctrl+C)"}
    CheckStop -- Yes --> RaiseStop["Raise BatchStoppedException<br/>(Save status: PAUSED, preserve artifacts)"]
    CheckStop -- No --> TryCall{"Try Primary Model Invocation"}
    
    TryCall -- Success --> Return["Return Stage Result"]
    TryCall -- HTTP 429 Quota --> Fallback{"FallbackChatModel configured?"}
    Fallback -- Yes --> TryFallback["Invoke Fallback Model (e.g. gemini-3.5-flash-lite)"]
    TryFallback -- Success --> Return
    TryFallback -- HTTP 429 / Failed --> QuotaWait["Window Rollover Backoff<br/>(Wait 25s–65s for 60s quota reset)"]
    Fallback -- No --> QuotaWait
    QuotaWait --> TryCall
    
    TryCall -- Transient Error (500, 503) --> Backoff["Exponential Backoff + Jitter<br/>(Attempt 1–6)"]
    Backoff --> TryCall
    
    TryCall -- Fatal / Exhausted --> SaveFailed["Save Checkpoint (status: FAILED)<br/>Capture traceback in metadata"]
```

* **Zero Data Loss**: Checkpoints preserve intermediate progress at the chapter level.
* **Atomic Writes**: YAML and JSON files are written safely to prevent corruption during interruptions.
