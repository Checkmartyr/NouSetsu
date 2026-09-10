# 📚 NouSetsu Technical Documentation Hub

Welcome to the **NouSetsu** (濃説 / 脳説) technical documentation. This directory provides in-depth architectural guides, agent workflow specifications, data schemas, and developer references for the autonomous multi-agent novel translation system.

---

## 🧭 Documentation Map

| Guide | Document | Description |
| :--- | :--- | :--- |
| **Workflow & Pipeline** | [**`workflow.md`**](./workflow.md) | Stage-by-stage LangGraph execution, state transitions, retry loop, and Mermaid sequence diagrams. |
| **System Architecture** | [**`architecture.md`**](./architecture.md) | High-level system architecture, component layer separation, and data flow pipelines. |
| **Novel Bible & Memory** | [**`novel_bible.md`**](./novel_bible.md) | Persistent world-building memory, zero-anaphora subject resolution, character voice registers, and style guide. |
| **Storage & Checkpoints** | [**`storage_and_checkpoints.md`**](./storage_and_checkpoints.md) | Single project metadata document (`.novel/metadata.json`), error diagnostics, SHA256 integrity, and mid-stage resumption. |
| **Terminal UI (TUI) Guide** | [**`tui_guide.md`**](./tui_guide.md) | Interactive Textual interface, Dual Reader inspection, Novel Bible editor, project manager, and keyboard shortcuts. |
| **Developer API Reference** | [**`api_reference.md`**](./api_reference.md) | Complete Python API reference for agents, workflow graph, storage repository, and Pydantic data models. |

---

## 🎯 Quick Navigation by Role

### 📖 For Novel Translators & Readers
* Learn how the multi-agent pipeline translates foreign novels with zero-anaphora resolution: [**Workflow Deep Dive**](./workflow.md).
* Master the interactive terminal reader and Bible editor: [**TUI User Guide**](./tui_guide.md).
* Customize character voices, honorifics, and style guides: [**Novel Bible Guide**](./novel_bible.md).

### 🛠️ For AI Developers & Contributors
* Understand the decoupled modular architecture and LangGraph wiring: [**System Architecture**](./architecture.md).
* Explore the checkpointing schema and error logging: [**Storage & Checkpoints**](./storage_and_checkpoints.md).
* Review classes, methods, and agent contracts: [**API Reference**](./api_reference.md).

---

## 🏛️ Core Principles of NouSetsu

1. **Document-Level Coherence**: Traditional machine translation operates sentence-by-sentence. NouSetsu processes full chapters while querying preceding chapter summaries to eliminate context amnesia.
2. **Zero-Anaphora Subject Resolution**: East Asian languages (Japanese, Chinese, Korean) frequently omit sentence subjects and pronouns. NouSetsu's drafter infers subjects from scene context and active character cards.
3. **Multi-Agent Quality Gating**: Translation is not a single prompt. It is an automated assembly line: extraction $\to$ drafting $\to$ critique $\to$ prose polishing $\to$ narrative chronicling.
4. **Resilient Local Persistence**: Everything is saved locally in transparent YAML/JSON files. Zero cloud vendor lock-in, with single project metadata keeping output folders clean.
