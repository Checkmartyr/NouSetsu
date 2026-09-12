# 📚 NouSetsu Technical Documentation Hub

Welcome to the **NouSetsu** (濃説 / 脳説) technical documentation. This directory provides in-depth architectural guides, agent workflow specifications, data schemas, and developer references for the autonomous multi-agent novel translation system.

---

## 🧭 Documentation Map

| Guide | Document | Description |
| :--- | :--- | :--- |
| **End-User Guide** | [**`user_guide.md`**](./user_guide.md) | Complete end-user manual covering installation, minimal TUI dashboard, headless batch automation, per-agent model routing, Novel Bible management, custom skills, and safety guards. |
| **Workflow & Pipeline** | [**`workflow.md`**](./workflow.md) | LangGraph multi-agent execution, reflection review loop, agent functions, line-based semantic chunking, rate limiting (32K TPM / 60 RPM), and sequence diagrams. |
| **Agents Deep Dive** | [**`agents_deep_dive.md`**](./agents_deep_dive.md) | Comprehensive cognitive breakdown of all 5 agents (Schriftdetektiv, Wortschmied, Zensor, Feinschliff, Chronist): prompt engineering, context assembly, chunking mechanics, and safety guards. |
| **System Architecture** | [**`architecture.md`**](./architecture.md) | Layered architecture, component responsibilities, utilities (`rate_limiter`, `chunker`, `formatting`), FallbackChatModel failover, and thread-safe cancellation. |
| **Novel Bible & Memory** | [**`novel_bible.md`**](./novel_bible.md) | Persistent world memory, zero-anaphora resolution, automatic language detection, character registers, and style guide. |
| **Storage & Checkpoints** | [**`storage_and_checkpoints.md`**](./storage_and_checkpoints.md) | Single project metadata document (`.novel/metadata.json`), step duration tracking, paused checkpoint state machine (`PAUSED`), and SHA-256 integrity. |
| **Terminal UI (TUI) Guide** | [**`tui_guide.md`**](./tui_guide.md) | Minimal Textual interface, bottom 2-row toolbar, real-time active chapter progress label, Dual Reader inspection, Stop button (`X`), Settings modal (model routing & rate limits), and Bible editor. |
| **Developer API Reference** | [**`api_reference.md`**](./api_reference.md) | Python API reference for agents, FallbackChatModel, LineSemanticChunker, workflow graph, rate limiter, language detector, batch runner, and Pydantic models. |

---

## 🎯 Quick Navigation by Role

### 📖 For Novel Translators & Readers
* Learn how the multi-agent pipeline and review loop produce literary English: [**Workflow Deep Dive**](./workflow.md).
* Deep-dive into each agent's cognitive role, zero-anaphora resolution, and translationese elimination: [**Agents Deep Dive**](./agents_deep_dive.md).
* Master the interactive terminal reader, stop controls, and Bible editor: [**TUI User Guide**](./tui_guide.md).
* Customize character voices, honorifics, and style guides: [**Novel Bible Guide**](./novel_bible.md).

### 🛠️ For AI Developers & Contributors
* Master the prompt engineering, chunking flow, and safety guards of all 5 agents: [**Agents Deep Dive**](./agents_deep_dive.md).
* Understand the decoupled modular architecture, rate limiting, and LangGraph wiring: [**System Architecture**](./architecture.md).
* Explore the checkpointing schema, pause states, and error logging: [**Storage & Checkpoints**](./storage_and_checkpoints.md).
* Review classes, methods, rate limiters, and agent contracts: [**API Reference**](./api_reference.md).

---

## 🏛️ Core Principles of NouSetsu

1. **Document-Level Coherence**: Traditional machine translation operates sentence-by-sentence. NouSetsu processes full chapters while querying preceding chapter summaries to eliminate context amnesia.
2. **Zero-Anaphora Subject Resolution**: East Asian languages (Japanese, Chinese, Korean) frequently omit sentence subjects and pronouns. NouSetsu's drafter infers subjects from scene context and active character cards.
3. **Multi-Agent Quality Gating & Reflection**: Translation is an automated assembly line: extraction $\to$ drafting $\to$ critique $\to$ prose polishing $\to$ reflection review cycle (fidelity & style $\ge 8.5/10$) $\to$ chronicling.
4. **Proactive Quota & Rate Limit Protection**: Proactive 32,000 TPM and 60 RPM sliding window throttling prevents API 429 quota exhaustion, coupled with automatic fallback model failover and smart 25s–65s window rollover backoff.
5. **Thread-Safe Graceful Resumption**: Batch runs can be safely interrupted at any second, cleanly saving intermediate stage checkpoints with zero lost progress.
6. **Resilient Local Persistence**: Everything is saved locally in transparent YAML/JSON files with single project metadata keeping output folders completely clean.
7. **Procedural Graph Steering & Self-Evolution (arXiv:2609.09153v1)**: Procedural execution knowledge is encoded outside model weights as attributed directed graphs with `(condition, guidance, pitfalls)`. Deterministic code-level localization prevents runtime token bloat (<100 prompt tokens), while offline feedback loops self-evolve edge rules from critique audit traces.
