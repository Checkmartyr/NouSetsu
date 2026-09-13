# 📚 NouSetsu Technical Documentation Hub

Welcome to the **NouSetsu** (濃説 / 脳説) technical documentation. This directory provides in-depth architectural guides, agent workflow specifications, data schemas, and developer references for the autonomous multi-agent novel translation system.

---

## 🧭 Documentation Map

| Guide | Document | Description |
| :--- | :--- | :--- |
| **Five Pipeline Agents** | [**`agents/README.md`**](./agents/README.md) | Dedicated per-agent operational guides with method contracts, RAG roles, cognitive mechanics, and domain skills ([`01_entity_extractor`](./agents/01_entity_extractor.md), [`02_drafter`](./agents/02_drafter.md), [`03_critic`](./agents/03_critic.md), [`04_polisher`](./agents/04_polisher.md), [`05_chronicler`](./agents/05_chronicler.md)). |
| **End-User Guide** | [**`user_guide.md`**](./user_guide.md) | Complete end-user manual covering installation, minimal TUI dashboard, headless batch automation, per-agent model routing, Novel Bible management, 22 custom domain skills, narrative inspection CLI, Hybrid RAG, Trace Visualizer web app, and safety guards. |
| **Workflow & Pipeline** | [**`workflow.md`**](./workflow.md) | LangGraph multi-agent execution, reflection review loop, agent functions, line-based semantic chunking, rate limiting (32K TPM / 60 RPM), Hybrid RAG retrieval/indexing, PromptTracker, Diff/Patch engine, and sequence diagrams. |
| **Agents Deep Dive** | [**`agents_deep_dive.md`**](./agents_deep_dive.md) | Comprehensive cognitive breakdown of all 5 agents (Schriftdetektiv, Wortschmied, Zensor, Feinschliff, Chronist): prompt engineering, 3-tier memory injection, chunking mechanics, nickname discipline, Diff/Patch polishing, PromptTracker, and safety guards. |
| **System Architecture** | [**`architecture.md`**](./architecture.md) | Layered architecture, component responsibilities, utilities (`rate_limiter`, `chunker`, `formatting`), FallbackChatModel failover, procedural graphs, summary migration, Hybrid RAG SQLite FTS5 engine, PromptTracker, Web Visualizer, and thread-safe cancellation. |
| **Novel Bible & Memory** | [**`novel_bible.md`**](./novel_bible.md) | 3-tier hierarchical narrative memory (Macro premise > Meso arcs > Micro rolling chapters), cross-volume memory backfill, script-aware word boundary glossary filtering, per-scene character roster filtering, nickname discipline, automatic language detection, character registers, and style guide. |
| **Storage & Checkpoints** | [**`storage_and_checkpoints.md`**](./storage_and_checkpoints.md) | Single project metadata document (`.novel/metadata.json`), story arc summaries (`.novel/summaries/arcs/`), prompt trace archive (`.novel/traces/`), Hybrid RAG database (`.novel/rag/lore.db`), summary migration engine, step duration tracking, paused checkpoint state machine (`PAUSED`), and SHA-256 integrity. |
| **Terminal UI (TUI) Guide** | [**`tui_guide.md`**](./tui_guide.md) | Minimal Textual interface, bottom 2-row toolbar, active chapter progress label, Dual Reader inspection, Token Analytics dashboard (`M`), Web Traces hotkey (`W`), Volume Switcher modal (`F`), Stop button (`X`), and Bible editor. |
| **Developer API Reference** | [**`api_reference.md`**](./api_reference.md) | Python API reference for agents, FallbackChatModel, LineSemanticChunker, workflow graph, rate limiter, ArcSummary, NovelBible hierarchy methods, summary migration, DiffPatcher, PromptTracker, HybridSearchEngine, and Pydantic models. |

---

## 🎯 Quick Navigation by Role

### 📖 For Novel Translators & Readers
* Learn how the multi-agent pipeline and review loop produce literary English: [**Workflow Deep Dive**](./workflow.md).
* Deep-dive into each agent's cognitive role, zero-anaphora resolution, and translationese elimination: [**Agents Deep Dive**](./agents_deep_dive.md).
* Master the interactive terminal reader, token analytics, stop controls, and Bible editor: [**TUI User Guide**](./tui_guide.md).
* Customize character voices, honorifics, and style guides: [**Novel Bible Guide**](./novel_bible.md).

### 🛠️ For AI Developers & Contributors
* Master the prompt engineering, chunking flow, and safety guards of all 5 agents: [**Agents Deep Dive**](./agents_deep_dive.md).
* Understand the decoupled modular architecture, rate limiting, and LangGraph wiring: [**System Architecture**](./architecture.md).
* Explore the checkpointing schema, 3-tier arc storage, prompt traces, and error logging: [**Storage & Checkpoints**](./storage_and_checkpoints.md).
* Review classes, methods, rate limiters, migration engine, and agent contracts: [**API Reference**](./api_reference.md).

---

## 🏛️ Core Principles of NouSetsu

1. **Document-Level Coherence & 3-Tier Memory**: Traditional machine translation operates sentence-by-sentence. NouSetsu processes full chapters while maintaining a 3-tier narrative memory (Macro whole-story premise > Meso story arcs > Micro rolling chapters) across volume boundaries to eliminate context amnesia.
2. **Zero-Anaphora Subject Resolution & Nickname Discipline**: East Asian languages (Japanese, Chinese, Korean) frequently omit sentence subjects and pronouns. NouSetsu's drafter infers subjects from scene context and character cards while strictly enforcing formal vs diminutive address rules.
3. **Multi-Agent Quality Gating & Reflection**: Translation is an automated assembly line: extraction $\to$ drafting $\to$ critique $\to$ prose polishing $\to$ reflection review cycle (fidelity & style $\ge 8.5/10$) $\to$ chronicling.
4. **Proactive Quota & Rate Limit Protection**: Proactive 32,000 TPM and 60 RPM sliding window throttling prevents API 429 quota exhaustion, coupled with automatic fallback model failover and smart 25s–65s window rollover backoff.
5. **Thread-Safe Graceful Resumption**: Batch runs can be safely interrupted at any second, cleanly saving intermediate stage checkpoints with zero lost progress.
6. **Resilient Local Persistence**: Everything is saved locally in transparent YAML/JSON files with single project metadata keeping output folders completely clean.
7. **Procedural Graph Steering & Self-Evolution (arXiv:2609.09153v1)**: Procedural execution knowledge is encoded outside model weights as attributed directed graphs with `(condition, guidance, pitfalls)`. Deterministic code-level localization prevents runtime token bloat (<100 prompt tokens), while offline feedback loops self-evolve edge rules from critique audit traces.
8. **AI Safety Dual Resilience & Recursive Bisection**: Proactively intercepts commercial LLM safety blocks (`prohibited_content` HTTP 400) on intense action or romantic scenes, recursively bisecting chunks down to minimal sensitive snippets ($\le 8$ lines) so safe text retains full LLM literary prose while sensitive snippets seamlessly fall back to Google Translate and literary polishing.
9. **Hybrid Search RAG Knowledge Store & Cross-Encoder Reranking**: Zero-daemon local SQLite knowledge store (`.novel/rag/lore.db`) combining FTS5 BM25 lexical search with Gemini Embedding 2 (3072-dim) vector search via Reciprocal Rank Fusion (RRF, $k=60$) and optional LLM Cross-Encoder reranking.
10. **Forensic Prompt Tracking & Trace Visualizer**: End-to-end prompt and response tracing (`PromptTracker`, `.novel/traces/`) coupled with a React 19 + Vite web visualizer (`nousetsu web`, TUI `W` keybinding).
11. **Diff / Patch Polishing & Title Preservation Guard**: Optional token-efficient unified diff polishing engine (`DiffPatcher`) paired with programmatic chapter title protection preventing heading loss or hallucination.
12. **Script-Aware Word Boundary & Scene Character Filtering**: CJK vs non-CJK regex word-boundary detection prevents substring collisions, while Drafter/Critic dynamically filter active characters to those appearing in each ~70-line scene chunk.
13. **KV Context Caching Prefix Stabilization**: High-entropy dynamic variables are consolidated at prompt tails, maintaining stable system prompt prefixes for Gemini KV context caching.
