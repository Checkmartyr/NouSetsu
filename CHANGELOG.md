# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
