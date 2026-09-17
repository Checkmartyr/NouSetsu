# Documentation Inventory & Code-to-Doc Mapping Matrix

This matrix maps codebase components, modules, and subsystems to their corresponding documentation files. Whenever code in a component is created or modified, use this matrix to identify every documentation file that must be checked and synchronized.

---

## 1. Primary Documentation Matrix

| Code Component / Module | Source Path | Primary Documentation | Secondary Documentation | Key Sections to Audit |
|:---|:---|:---|:---|:---|
| **CLI App & Subcommands** | `src/nousetsu/cli/app.py` | `README.md`<br>`AGENTS.md` (Sec 8) | `doc/user_guide.md`<br>`doc/api_reference.md` | Command syntax, flags, default options, help strings, example usages |
| **LangGraph Workflow & Pipeline** | `src/nousetsu/graph/workflow.py`<br>`src/nousetsu/graph/state.py` | `AGENTS.md` (Sec 2, 4)<br>`doc/workflow.md` | `README.md`<br>`doc/architecture.md` | Mermaid sequence/state diagrams, pipeline stages, loop thresholds, state keys |
| **Procedural Graphs** | `src/nousetsu/graph/procedural.py`<br>`src/nousetsu/graph/pg_refiner.py` | `AGENTS.md` (Sec 7.17)<br>`doc/workflow.md` | `README.md`<br>`doc/agents/` | Procedural graph nodes, hops, offline self-evolution (`learn-graph`), arXiv citation |
| **Pipeline Agents (1–5)** | `src/nousetsu/agents/*.py` | `AGENTS.md` (Sec 3)<br>`doc/agents_deep_dive.md` | `doc/agents/01_*.md`<br>through `05_*.md` | Production models, fallback models, agent roles, prompt structures, structured schemas |
| **Skills System** | `src/nousetsu/skills/` | `AGENTS.md` (Sec 5) | `README.md`<br>`doc/agents_deep_dive.md` | Built-in skill count (currently 23), catalog YAML schema, smart activation rules |
| **Storage & Memory Hierarchy** | `src/nousetsu/storage/`<br>`src/nousetsu/batch/` | `AGENTS.md` (Sec 6)<br>`doc/storage_and_checkpoints.md` | `doc/novel_bible.md` | 3-tier memory (Macro > Meso > Micro), checkpoints, multi-volume directories |
| **Hybrid RAG Knowledge Store** | `src/nousetsu/rag/` | `AGENTS.md` (Sec 7.9)<br>`doc/hybrid_rag.md` | `doc/architecture.md` | SQLite FTS5, BM25, Gemini Embedding 2, RRF ($k=60$), Cross-Encoder reranker |
| **TUI Interface** | `src/nousetsu/tui/` | `README.md`<br>`doc/tui_guide.md` | `AGENTS.md` (Sec 7.14) | Keyboard shortcuts, panels (dual reader, checkpoint inspector, token analytics) |
| **Web Visualizer** | `web/`<br>`src/nousetsu/web_server.py` | `README.md`<br>`AGENTS.md` (Sec 7.12) | `doc/user_guide.md` | Vite + React 19 visualizer, trace explorer, API endpoints |
| **Rate Limiter & Quota** | `src/nousetsu/utils/rate_limiter.py` | `AGENTS.md` (Sec 7.1) | `doc/architecture.md` | Sliding window TPM/RPM values, rollover sleep intervals |
| **Environment & Config** | `.env.example`<br>`src/nousetsu/config/` | `AGENTS.md` (Sec 6)<br>`README.md` | `doc/user_guide.md` | Environment variables cascade, project config YAML options |
| **Test Suite & CI** | `tests/`<br>`.github/workflows/` | `README.md`<br>`AGENTS.md` (Sec 7.7, 8) | `CHANGELOG.md` | Test count, test execution command (`uv run pytest`), CI status |

---

## 2. Doc Update Triggers

Always trigger a documentation synchronization when:
1. **New CLI Subcommand or Option**: A new `@cli.command()` or `@click.option()` is added or changed in `src/nousetsu/cli/app.py`.
2. **Agent Architecture Shift**: An agent prompt, model default, structured output schema, or pipeline stage is modified.
3. **New Pipeline Engine or Feature**: A new subsystem (e.g. Procedural Graphs, Diff/Patch Polishing, Reconciliation) is integrated.
4. **Configuration Change**: A new environment variable is introduced in `.env.example` or `config.py`.
5. **Test Count / Module Growth**: New test modules or significant additions alter the verified test suite count.
6. **Release / Tag Preparation**: Before merging or releasing a new version, update `CHANGELOG.md` and bump versions if applicable.
