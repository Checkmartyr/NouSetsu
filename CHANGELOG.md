# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-09-15

### Added
- **Native LangChain Structured Outputs & Typed Pydantic Schemas**:
  - Migrated `Schriftdetektiv` (`EntityExtractorAgent`), `Zensor` (`CritiqueAgent`), and `Chronist` (`ChroniclerAgent`) from brittle regex/JSON parsing to native LangChain structured output backed by strongly typed Pydantic models (`ExtractorResult`, `CritiqueResult`, `ChroniclerResult`).
  - Unified `invoke_structured` orchestration utility managing provider schema constraints (`response_json_schema`), secondary fallback failover on 429 quota exhaustion, and raw trace logging.
- **Configurable Thinking Level & Reasoning Budgets**:
  - Full support for Gemini 2.5/3.x `thinking_level` ("minimal", "low", "medium", "high", "off") and `thinking_budget` across all agents and the 4-tier configuration cascade.
  - Sanitized REST generation config parameters avoiding upstream 400 Bad Request errors.
- **Hybrid Search RAG Knowledge Store & Cross-Encoder Reranking**:
  - SQLite FTS5 BM25 lexical keyword search and Gemini Embedding 2 (`models/gemini-embedding-2`, 3072 dimensions) dense semantic vector search managed via **SQLAlchemy 2.0 ORM** (`.novel/rag/lore.db`).
  - Reciprocal Rank Fusion (RRF, $k=60$) candidate fusion and LLM Cross-Encoder Reranker (`LLMCrossEncoderReranker`).
  - Canonical Translation Memory (TM) retrieval to `Zensor` (CritiqueAgent) on Pass 1.
  - Inbound lore retrieval to `Chronist` (ChroniclerAgent) and `Wortschmied` (DrafterAgent).
  - Outbound auto-indexing of chapter summaries and 20-line scene chunks upon chapter completion.
  - New CLI commands `nousetsu lore` and `nousetsu migrate-rag` (alias `index-rag`).
- **Forensic Prompt Tracking & Web Visualizer**:
  - `PromptTracker` engine capturing full system prompts, user inputs, raw outputs, token telemetry, and latencies across every agent stage, serialized into `.novel/traces/`.
  - Vite + React 19 + TypeScript web trace visualizer (`web/`, `nousetsu web`, `src/nousetsu/cli/web_server.py`) with stage timelines, token estimators, unified diff viewers, and raw JSON inspectors.
  - Real-time active project sync between Textual TUI and Web Visualizer via the `W` hotkey.
  - Model token cost analytics calculation in USD based on official pricing tiers for input, cached, and output tokens.
  - Multi-segment input/cached/output token distribution charts and KV cache telemetry per agent.
- **Robust Diff / Patch Polishing Engine & Token Optimization**:
  - `DiffPatcher` (`src/nousetsu/utils/diff_patcher.py`) and `PATCH_POLISHING_SYSTEM_PROMPT` generating targeted `<<<<<<< SEARCH ... ======= ... >>>>>>>` block replacements or `NO_CHANGES_NEEDED` rather than re-streaming whole chapters.
  - Multi-block patch support in a single LLM turn with dynamic document re-indexing.
  - Preserves intra-paragraph blank lines during window matching, whitespace normalization, and fuzzy sequence matching.
  - Strict fallback to base draft text and multi-layer diff marker leakage rejection.
  - KV Context Caching prefix stabilization (`GEMINI_KV_CACHE_STABLE_PREFIX`) maximizing Gemini prompt cache hits.
- **Chapter Title Preservation Guard**:
  - Added built-in `chapter_header_preservation` domain skill to `PolishingAgent` (priority 115).
  - Added programmatic regex guard (`_ensure_chapter_title_preserved`) across Asian and Western chapter headings.
- **Scene-Level Character & Glossary Filtering**:
  - `filter_characters_for_scene` dynamically filters character profiles to those active in the scene, preserving core protagonist roles while eliminating prompt bloat.
  - `filter_glossary_for_text` with script-aware word boundary detection (CJK ideographs vs Latin `\b` boundaries).
  - Dedicated scene-based entity and glossary filtering for `Schriftdetektiv` (`EntityExtractorAgent`).
- **Flexible Chapter CLI Range & Batch Targeting**:
  - Extended `--chapter` / `-c` to support range (`5-58`, `5..58`, `ch 5 to 58`) and start-from (`5+`) syntax.
- **High-Performance Textual TUI**:
  - Dual reader widget memoization, cached SHA-256 scanning, throttled 60 FPS progress updates, and lazy token analytics rendering.
- **Test Suite Expansion**:
  - Expanded test coverage to 325 passing tests across 50 modules.

## [0.2.0] - 2026-09-13

### Added
- **3-Tier Hierarchical Narrative Memory**: Macro (`whole_story_summary`), Meso (`ArcSummary` with autonomous boundary/milestone detection in `.novel/summaries/arcs/`), and Micro (volume-partitioned `ChapterSummary`).
- **Cross-Folder & Multi-Volume Narrative Memory**: Auto-detects volume sequences (`Villainess_04`, `Villainess_05`), partitions summaries, and seamlessly backfills preceding volume summaries with volume badges.
- **Narrative CLI & Migration Tools**: Added `nousetsu narrative` for interactive Rich tree inspection and `nousetsu migrate-summaries` for upgrading legacy flat summaries.
- **AI Safety Block Resilience**:
  - `bisect_text` recursive binary bisection engine isolating sensitive scenes down to <= 8-line snippets.
  - `translate_via_google` fallback leveraging `deep-translator` when encountering Google AI `prohibited_content` blocks.
  - Universal task framing across all five pipeline agents (Extractor, Drafter, Critic, Polisher, Chronicler).
  - Graceful Polisher decoupling and multi-stage fallback.
- **Flexible Chapter CLI Targeting**: `--chapter` / `-c` supporting natural chapter arguments (`48`, `048`, `ch 48`, `chapter 48`, `第48話`).
- **Procedural Execution Graphs (arXiv:2609.09153v1)**: Attributed procedural graphs $G = (V, R, E, \Phi)$ steering extraction term pruning (-300 to -800 tokens) and drafter state switching (`Name_Discipline`), inspectable via `nousetsu graph-info`.
- **Domain Skills Catalog**: 20 built-in domain skills across all five agents and support for custom YAML frontmatter Markdown skill files in `src/nousetsu/skills/catalog/`.
- **Token Analytics Dashboard**: Real-time KPI cards and interactive DataTables accessible via `M` shortcut in the TUI, tracking prompt, completion, thought, and cached tokens.
- **Minimalist Reactive TUI**: 2-row bottom toolbar layout, active chapter progress strip (`📖 {chapter} [████░░░░] 50%`), and 80%+ viewport height.

### Changed
- Standardized prompt framing across Extractor, Drafter, Critic, Polisher, and Chronicler to emphasize literary fiction translation and prevent safety false positives.
- Decoupled Polisher prompt to pass chunked source slices instead of raw full text.
- Checkpoints now record bounded error diagnostics and stage status without losing partial progress on cancellation or failure.

### Fixed
- Resolved Google AI `prohibited_content` safety blocks through recursive bisection and Google Translate fallback.
- Fixed unchunked source text payload leaks to the Polishing agent.
- Prevented infinite reflection review loop spinning when critique audit is bypassed due to safety blocks.
- Fixed FallbackChatModel constructor wiring and mock model propagation across pipeline agents.

## [0.1.0] - 2026-09-10

### Added
- Initial release of **NouSetsu** novel translation system.
- Five-agent LangGraph reflection pipeline:
  - **Schriftdetektiv** (`EntityExtractorAgent`)
  - **Wortschmied** (`ContextAwareDrafterAgent`)
  - **Zensor** (`CritiqueAgent`)
  - **Feinschliff** (`PolishingAgent`)
  - **Chronist** (`ChroniclerAgent`)
- Persistent Novel Bible (`bible.yaml`) with character profiles, terminology glossary, and style guide.
- Single consolidated project metadata document (`.novel/metadata.json`).
- Textual TUI dashboard with dual-pane reading viewer and live pipeline progress visualization.
- Proactive sliding-window rate limiter (32,000 TPM / 60 RPM).
- Line-based semantic chunker (85-line threshold) with 3-line sliding context.
- Automatic CJK source language detection (Japanese, Chinese, Korean).
- Console scripts `nousetsu` and `novel`.

[0.3.0]: https://github.com/Checkmartyr/NouSetsu/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Checkmartyr/NouSetsu/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Checkmartyr/NouSetsu/releases/tag/v0.1.0
