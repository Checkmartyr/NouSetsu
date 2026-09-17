---
name: doc-updater
description: >-
  Systematically audits, synchronizes, and updates project documentation (README.md, AGENTS.md, docs/ guides, API references, CLI manuals, architecture diagrams, CHANGELOG.md) to match the latest codebase changes, git diffs, APIs, and CLI commands. Triggers when the user asks to "update document to latest version of code", "sync docs", "refresh documentation", "update README", or "align docs with code".
---

# Documentation Updater Skill (`doc-updater`)

This skill provides an automated, rigorous, multi-phase procedure to inspect recent codebase commits, diffs, CLI subcommands, model configurations, and architecture diagrams, and synchronize all project documentation so that it accurately reflects the latest version of the code.

---

## 1. Activation Triggers

Activate this skill when:
- The user requests: *"update document to latest version of code"*, *"sync docs"*, *"update documentation"*, *"align docs with code"*, or *"refresh README and AGENTS.md"*.
- Major features, new pipeline agents, procedural graphs, or new CLI subcommands/options have been merged into the codebase.
- A release or version tag is being prepared.

---

## 2. Pre-Flight Drift Audit

Before modifying any documentation files, run the included drift detection helper:

```powershell
.\.venv\Scripts\python.exe .agents/skills/doc-updater/scripts/check_doc_drift.py
```

This script automatically scans:
1. **Registered CLI Subcommands & Options**: Detects any CLI commands in `src/nousetsu/cli/app.py` missing from documentation.
2. **Current Test Count**: Runs the pytest test collector to get exact test and module counts (e.g. `347 tests across 52 modules`).
3. **Recent Commits**: Highlights recent changes from `git log` that may introduce undocumented features.
4. **Local Link Validity**: Identifies broken `file://` and relative markdown links across all documentation files.

---

## 3. Step-by-Step Synchronization Workflow

Follow this 5-phase procedure systematically:

### Phase 1: Codebase Drift & Git Diff Analysis
1. Inspect recent git commits and diffs since the last documented commit:
   ```powershell
   git log -n 10 --oneline
   git diff --stat HEAD~5 HEAD
   ```
2. Identify:
   - New CLI subcommands, arguments, or flags in `src/nousetsu/cli/app.py`.
   - Pipeline changes in `src/nousetsu/graph/workflow.py` or agent classes in `src/nousetsu/agents/`.
   - New subsystems, engines, or algorithms (e.g. Procedural Graphs, Diff/Patch Polishing, RAG Cross-Encoder).
   - New environment variables in `.env.example` or configuration models.

### Phase 2: Documentation Target Mapping
Consult [references/doc_inventory_matrix.md](./references/doc_inventory_matrix.md) to determine which documentation files correspond to the modified code:

- **Root Docs**:
  - `README.md`: User quickstart, CLI command overview, feature matrix, installation, test counts.
  - `AGENTS.md`: Operational handbook, layered architecture, Mermaid diagrams, agent roles, memory tiers, model cascade.
  - `CHANGELOG.md`: Structured release log under `[Unreleased]` (Keep a Changelog format).
- **Subsystem Deep Dives (`doc/`)**:
  - `doc/architecture.md`: System components, rate limiter, safety bisection, fallback chain.
  - `doc/workflow.md`: LangGraph reflection review cycle, procedural graphs, loop thresholds.
  - `doc/agents_deep_dive.md` and `doc/agents/01_*.md` through `05_*.md`: Agent prompts, schemas, RAG roles.
  - `doc/api_reference.md`: Core Python classes, methods, and types.
  - `doc/user_guide.md` & `doc/tui_guide.md`: CLI commands, options, and TUI keybindings.
  - `doc/hybrid_rag.md`: SQLite FTS5, vector search, cross-encoder reranking.

### Phase 3: Core Architecture & Diagram Synchronization
1. **Mermaid Diagrams**: Update state and sequence diagrams to reflect new pipeline nodes, edges, and transitions:
   - Ensure all node labels with brackets or parentheses are double-quoted (`["..."]`).
   - Adhere to supported Mermaid diagram types (`graph TD`, `graph LR`, `stateDiagram-v2`, `sequenceDiagram`).
2. **Five Pipeline Agents Table**:
   - Verify agent roles, classes, production models, fallback models, and source file links match code.
3. **Engine Highlights**:
   - Add concise architectural descriptions for newly introduced algorithms or subsystems.

### Phase 4: CLI & Configuration Reference Synchronization
1. **CLI Commands & Flags**:
   - Ensure every subcommand (e.g. `init`, `batch`, `tui`, `web`, `graph-info`, `learn-graph`, `narrative`, `migrate-rag`, `lore`, `traces`, `realign-chapters`) is documented with its aliases and options.
   - Verify default option values match the default arguments in `src/nousetsu/cli/app.py`.
2. **Environment Cascade**:
   - Verify `.env.example` lists all active variables, and `AGENTS.md` / `README.md` describe the 4-tier precedence cascade accurately.
3. **Test Counts**:
   - Update test suite metrics (e.g. "347 tests across 52 modules") across `README.md` and `AGENTS.md`.

### Phase 5: Changelog & Release Notes
1. Add an entry under `[Unreleased]` in `CHANGELOG.md`:
   - `### Added`: New CLI commands, agent skills, procedural graphs, offline evolution.
   - `### Changed`: Model default updates, prompt enhancements, test speedups.
   - `### Fixed`: Bug fixes, schema validations, encoding guards.
2. Adhere to [references/documentation_standards.md](./references/documentation_standards.md) for formatting rules, alert callouts, and clickable `file://` links.

---

## 4. Verification & Validation

After updating documentation files:
1. Re-run the drift audit script to verify all discrepancies are resolved:
   ```powershell
   .\.venv\Scripts\python.exe .agents/skills/doc-updater/scripts/check_doc_drift.py
   ```
2. Verify git diff to ensure documentation updates are clean, precise, and preserve existing author comments:
   ```powershell
   git diff --stat
   ```
3. Run the test suite to ensure no code or test regressions occurred:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest -q
   ```
