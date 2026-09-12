# 🏛️ System Architecture & Component Design

This document details the software architecture, design patterns, and layer separation of **NouSetsu**. The system is built with clean architecture principles to ensure decoupling between LLM providers, multi-agent orchestration, local persistence, and user interfaces.

---

## 🏗️ Layered Architecture Diagram

```mermaid
graph TD
    subgraph Presentation_Layer ["Presentation Layer (UI / CLI)"]
        TUI["Textual TUI Application<br/>(DualReader, ProgressPanel, Modals, Stop Button X)"]
        CLI["Rich CLI Commands<br/>(init, batch, tui, SIGINT Stop)"]
    end

    subgraph Batch_Orchestration ["Batch & Task Orchestration"]
        Scanner["ChapterScanner<br/>(natsort, SHA256, load_all_metadata)"]
        Runner["BatchRunner<br/>(sequential loop, stop_event, checkpoints, Rich progress)"]
    end

    subgraph Workflow_Layer ["Agentic Workflow Layer (LangGraph)"]
        Workflow["NovelTranslationWorkflow<br/>(StateGraph, Review Reflection Loop, stage callbacks)"]
        State["TranslationState<br/>(source, draft, critique, polish, Bible memory, best candidate)"]
    end

    subgraph Agent_Layer ["Specialized Agent Layer (German Designations)"]
        Extractor["Stage 1: Schriftdetektiv<br/>(EntityExtractorAgent)"]
        Drafter["Stage 2: Wortschmied<br/>(ContextAwareDrafterAgent)"]
        Critic["Stage 3: Zensor<br/>(CritiqueAgent)"]
        Polisher["Stage 4: Feinschliff<br/>(PolishingAgent)"]
        Chronicler["Stage 5: Chronist<br/>(ChroniclerAgent)"]
        LLM["LLM Client & FallbackChatModel<br/>(Per-Role Model Routing, 429 Automatic Failover)"]
    end

    subgraph Utility_Layer ["Foundational Utilities (src/nousetsu/utils/)"]
        RateLimiter["SlidingWindowRateLimiter<br/>(32K TPM / 60 RPM, rolling window, 429 backoff)"]
        Chunker["LineSemanticChunker<br/>(85-line threshold, 70 target, 3 overlap)"]
        TokenEstimator["estimate_tokens<br/>(offline CJK 1.7 / Latin 1.3 weights)"]
        LangDetector["detect_language<br/>(Unicode script & lexical analysis)"]
        Formatter["format_duration<br/>(human-friendly step duration display)"]
    end

    subgraph Storage_Layer ["Persistence & Storage Layer"]
        Repo["NovelRepository<br/>(bible.yaml, .novel/metadata.json, summaries)"]
        Registry["ProjectRegistry<br/>(multi-project paths, last active project)"]
    end

    subgraph Domain_Models ["Domain & Schema Layer (Pydantic)"]
        M_Bible["NovelBible, CharacterProfile, GlossaryItem"]
        M_Meta["ChapterMetadata, CheckpointData, ErrorLogEntry"]
        M_Config["ProjectConfig, StyleGuideConfig"]
    end

    %% Dependencies
    TUI --> Runner
    CLI --> Runner
    Runner --> Scanner
    Runner --> Workflow
    Scanner --> LangDetector
    Runner --> RateLimiter
    Workflow --> State
    Workflow --> Extractor
    Workflow --> Drafter
    Workflow --> Critic
    Workflow --> Polisher
    Workflow --> Chronicler
    Workflow --> RateLimiter
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
    TUI --> Registry
    TUI --> Repo
    Repo --> Domain_Models
    Workflow --> Domain_Models
```

---

## 🧩 Architectural Layers & Responsibilities

### 1. Presentation Layer (`src/nousetsu/tui/`, `src/nousetsu/cli/`)
* **Textual TUI (`src/nousetsu/tui/app.py`)**: An asynchronous terminal application powered by `textual`. Renders side-by-side original and translated chapter views, reactive status badges (`[DONE]`, `[FAILED]`, `[RESUME]`, `[PAUSED]`, `[WAIT]`), a live 5-stage progress visualizer, dedicated **Stop Translation (`X`)** controls, and modals for editing the Novel Bible, adjusting rate limits & review loops, and switching projects.
* **Rich CLI (`src/nousetsu/cli/app.py`)**: Command-line entry points for headless servers, scripts, and terminal batch translation with native `SIGINT` (Ctrl+C) signal interception.

### 2. Batch & Scanning Layer (`src/nousetsu/batch/`)
* **`ChapterScanner`**: Discovers raw chapter files (`.txt`, `.md`), applies natural numerical sorting (`1, 2, 10`), computes SHA-256 checksums to detect file changes, triggers auto source language detection, and performs a single I/O read of `.novel/metadata.json` for instantaneous project discovery.
* **`BatchRunner`**: Sequentially translates chapters, passes updated Novel Bible state forward, manages resumption checkpoints, manages thread-safe `stop()` and `reset_stop()` signals, and coordinates rate limits.

### 3. Agentic Workflow Layer (`src/nousetsu/graph/`)
* **`NovelTranslationWorkflow`**: Compiles a LangGraph `StateGraph` featuring an automated **Reflection Review Loop** between `Feinschliff` and `Zensor`:
  * Evaluates fidelity and style quality thresholds (`>= 8.5/10`).
  * Employs an automated **Best-Candidate Regression Guard** to retain the highest-scoring candidate if subsequent passes degrade.
  * Emits fine-grained progress notifications (`stage_callback`) to update the TUI and CLI in real time.
  * Wraps all agent invocations with `invoke_with_retry` and rate-limit acquisitions.

### 4. Specialized Agent Layer (`src/nousetsu/agents/`)
Each agent possesses a single cognitive responsibility:
* **Stage 1: `EntityExtractorAgent` (*Schriftdetektiv*)**: Discovers unknown character names, spells, items, and titles before drafting.
* **Stage 2: `ContextAwareDrafterAgent` (*Wortschmied*)**: First-pass translation with zero-anaphora subject inference, character voice registers, and rolling episodic summaries. Integrates `LineSemanticChunker` for long chapters.
* **Stage 3: `CritiqueAgent` (*Zensor*)**: Line-by-line fidelity and stylistic auditing, generating scores and remediation notes.
* **Stage 4: `PolishingAgent` (*Feinschliff*)**: High-cadence prose refinement and translationese elimination across semantic chunks.
* **Stage 5: `ChroniclerAgent` (*Chronist*)**: Episodic synopses, world lore updates, and metadata compilation.
* **Per-Role Model Routing & `FallbackChatModel` (`src/nousetsu/agents/llm.py`)**: Resolves specialized models per stage (`extractor_model`, `drafter_model`, `critic_model`, `polisher_model`, `chronicler_model`), stripping thought tokens and automatically failing over to `fallback_model` when encountering HTTP 429 quota exhaustion.

### 5. Foundational Utility Layer (`src/nousetsu/utils/`)
* **`SlidingWindowRateLimiter` (`src/nousetsu/utils/rate_limiter.py`)**: Tracks requests and tokens across a rolling 60-second window, enforcing 32,000 TPM and 60 RPM limits with interruptible sleeps.
* **`LineSemanticChunker` (`src/nousetsu/utils/chunker.py`)**: Partitions chapters over 85 lines into ~70-line semantic chunks with 3-line boundary overlap, maintaining scene breaks and quote continuity.
* **`format_duration` (`src/nousetsu/utils/formatting.py`)**: Human-friendly duration display formatting (`3.9s`, `2m 15s`, `1h 4m`).
* **`estimate_tokens` (`src/nousetsu/utils/rate_limiter.py`)**: Offline token estimation assigning ~1.7 tokens per CJK character and ~1.3 tokens per Latin word.
* **`detect_language` (`src/nousetsu/utils/language.py`)**: Zero-dependency Unicode script and stop-word frequency analyzer recognizing Japanese, Chinese, Korean, Thai, Russian, and Latin languages.

### 6. Persistence & Storage Layer (`src/nousetsu/storage/`)
* **`NovelRepository`**: Manages all file system persistence for a project:
  * `.novel/config.yaml`: Language pair, raw/output folders, rate limits, review loop caps, and per-agent model preferences.
  * `.novel/bible/bible.yaml`: Characters, glossary, and style guide.
  * `.novel/metadata.json`: Consolidated single metadata document storing all chapter checkpoints, quality audit scores, step durations, and paused stage artifacts.
  * `.novel/summaries/`: Historical episodic chapter summaries.
* **`ProjectRegistry`**: Stores user-registered project directories across arbitrary filesystem locations and persists the `last_active_project` for instant reopening.

### 7. Domain Model Layer (`src/nousetsu/models/`)
* Strongly typed Pydantic V2 models defining contracts across the entire system (`TranslationState`, `NovelBible`, `ChapterMetadata`, `ProjectConfig`).

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
