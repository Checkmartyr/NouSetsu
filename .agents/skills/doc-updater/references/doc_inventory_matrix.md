# Documentation Inventory & Code-to-Doc Mapping Matrix

This matrix maps codebase components, modules, and subsystems to their corresponding documentation files. Whenever code in a component is created, modified, or refactored, use this matrix to identify every documentation file that must be checked and synchronized.

---

## 1. Primary Documentation Matrix

| Code Component / Module | Source Path | Primary Documentation | Secondary Documentation | Key Sections & Code References to Audit |
|:---|:---|:---|:---|:---|
| **CLI App & Subcommands** | `src/nousetsu/cli/app.py` | `README.md`<br>`AGENTS.md` (Sec 8) | `docs/user_guide.md`<br>`docs/api_reference.md` | Subcommands, aliases, flags (`--chapter`, `-c`, `--filter-extractor`, `--reconcile-terms`, etc.), default values, help strings |
| **LangGraph Workflow & Pipeline** | `src/nousetsu/graph/workflow.py`<br>`src/nousetsu/graph/state.py` | `AGENTS.md` (Sec 2, 4)<br>`docs/workflow.md` | `README.md`<br>`docs/architecture.md` | Mermaid sequence/state diagrams, pipeline stages, loop thresholds, state keys, best-candidate regression guard |
| **Procedural Graphs** | `src/nousetsu/graph/procedural.py`<br>`src/nousetsu/graph/pg_refiner.py` | `AGENTS.md` (Sec 7.17)<br>`docs/workflow.md` | `README.md`<br>`docs/agents/` | Procedural graph nodes, hops, offline self-evolution (`learn-graph`), arXiv citation (arXiv:2609.09153v1) |
| **Pipeline Agents (1–5)** | `src/nousetsu/agents/*.py` | `AGENTS.md` (Sec 3)<br>`docs/agents_deep_dive.md` | `docs/agents/01_*.md`<br>through `05_*.md` | Production models, fallback models, agent roles, prompt structures, structured schemas (`ExtractorResult`, `CritiqueResult`, `ChroniclerResult`) |
| **Character & Glossary Filters** | `src/nousetsu/utils/character_filter.py`<br>`src/nousetsu/utils/glossary_filter.py` | `AGENTS.md` (Sec 7.13)<br>`docs/agents/01_entity_extractor.md` | `docs/agents/02_drafter.md`<br>`docs/architecture.md` | Compound name sub-component matching (`サフィナ・カルシャナ` $\to$ `サフィナ`), alias matching, word boundary heuristics, CJK script awareness |
| **Skills System** | `src/nousetsu/skills/` | `AGENTS.md` (Sec 5) | `README.md`<br>`docs/agents_deep_dive.md` | Built-in skill count (verify against `catalog/*.md`), YAML schema, smart activation engine |
| **Storage & Memory Hierarchy** | `src/nousetsu/storage/`<br>`src/nousetsu/batch/` | `AGENTS.md` (Sec 6)<br>`docs/storage_and_checkpoints.md` | `docs/novel_bible.md` | 3-tier memory (Macro > Meso > Micro), checkpoints, multi-volume directories, post-polish reconciliation |
| **Hybrid RAG Knowledge Store** | `src/nousetsu/rag/` | `AGENTS.md` (Sec 7.9)<br>`docs/hybrid_rag.md` | `docs/architecture.md` | SQLite FTS5, BM25, Gemini Embedding 2, RRF ($k=60$), Cross-Encoder reranker (`LLMCrossEncoderReranker`) |
| **Diff / Patch Polishing** | `src/nousetsu/utils/diff_patcher.py` | `AGENTS.md` (Sec 7.11)<br>`docs/architecture.md` | `README.md`<br>`docs/agents/04_polisher.md` | `apply_diff_patch`, `is_patch_format`, `PATCH_POLISHING_SYSTEM_PROMPT`, token savings |
| **TUI Interface** | `src/nousetsu/tui/` | `README.md`<br>`docs/tui_guide.md` | `AGENTS.md` (Sec 7.14) | Keyboard shortcuts, panels (dual reader, checkpoint inspector, token analytics, hotkeys `W`, `M`, `X`) |
| **Web Visualizer** | `web/`<br>`src/nousetsu/cli/web_server.py` | `README.md`<br>`AGENTS.md` (Sec 7.12) | `docs/user_guide.md` | Vite + React 19 visualizer, trace explorer, API endpoints (`/api/trace`, `/api/run-batch`), diff viewer |
| **Rate Limiter & Safety Bisection** | `src/nousetsu/utils/rate_limiter.py`<br>`src/nousetsu/agents/safety.py` | `AGENTS.md` (Sec 7.1, 7.8)<br>`docs/architecture.md` | `README.md` | Sliding window TPM/RPM values, recursive binary bisection (`bisect_text`), Google Translate fallback |
| **Environment & Config** | `.env.example`<br>`src/nousetsu/config/` | `AGENTS.md` (Sec 6)<br>`README.md` | `docs/user_guide.md` | Environment variables cascade (`NOVEL_*`), project config YAML options |
| **Test Suite & CI** | `tests/`<br>`.github/workflows/` | `README.md`<br>`AGENTS.md` (Sec 7.7, 8) | `CHANGELOG.md` | Exact test count and module count (e.g. `416 tests across 59 modules`), test commands |

---

## 2. Code-to-Doc Audit Checklist

Whenever inspecting documentation files, verify every code citation against the codebase:
1. **File Paths**: Ensure every cited path (`docs/...`, `src/...`, `.novel/...`) actually exists on disk.
2. **Symbols & Callables**: Verify that classes (e.g. `EntityExtractorAgent`), functions (e.g. `filter_characters_for_scene`, `apply_diff_patch`), and data models (e.g. `CharacterProfile`, `NovelBible`) exist in the referenced modules.
3. **Line Anchors**: Verify that `#L{start}-L{end}` line links are within the target file's total line count.
4. **CLI Flags**: Verify that documented flags (e.g. `--chapter`, `-c`, `--force`, `--limit`, `--filter-extractor`, `--reconcile-terms`) match the argument definitions in `src/nousetsu/cli/app.py`.
5. **Configuration Variables**: Verify that all `NOVEL_*` variables in docs are present in `.env.example`.
6. **Code Snippets**: Ensure Python code blocks in markdown are valid Python and reflect current function signatures.
7. **Mermaid Labels**: Ensure all node labels with special characters (brackets, parentheses, colons) are enclosed in double quotes (`id["..."]`).
