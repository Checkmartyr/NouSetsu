---
name: doc-updater
description: >-
  Systematically audits, synchronizes, and updates project documentation (README.md, AGENTS.md, docs/ guides, API references, CLI manuals, architecture diagrams, CHANGELOG.md) to match the latest codebase changes by comparing the current branch against main. Triggers when the user asks to "update document to latest version of code", "sync docs", "refresh documentation", "update README", or "align docs with code".
---

# Documentation Updater Skill (`doc-updater`)

This skill provides an automated, rigorous, multi-phase procedure to compare the current feature branch against `main`, identify all code changes (new files, modified modules, deleted components), and synchronize all project documentation so that it accurately reflects the latest version of the code.

---

## 1. Activation Triggers

Activate this skill when:
- The user requests: *"update document to latest version of code"*, *"sync docs"*, *"update documentation"*, *"align docs with code"*, or *"refresh README and AGENTS.md"*.
- Major features, new pipeline agents, procedural graphs, or new CLI subcommands/options have been added on the current branch.
- A feature branch is ready for merge/PR into `main`.
- A release or version tag is being prepared.

---

## 2. Pre-Flight Branch Diff Audit

Before modifying any documentation files, run the branch-aware drift detection helper:

```powershell
.\.venv\Scripts\python.exe .agents/skills/doc-updater/scripts/check_doc_drift.py
```

This script automatically:
1. **Detects the current branch** and the merge base against `main`.
2. **Generates a full branch diff summary** (`git diff main...HEAD --stat`) showing all files added, modified, or deleted since diverging from `main`.
3. **Categorizes changed files** by subsystem (agents, cli, prompts, storage, web, tests, etc.) and maps them to affected documentation targets.
4. **Scans CLI subcommands & options** registered in the codebase vs. documented in README/AGENTS/docs.
5. **Counts total tests** via pytest collector for accurate test count references.
6. **Validates internal file:// links** across all documentation files.
7. **Produces an actionable change manifest** listing exactly which documentation files need updating and why.

---

## 3. Step-by-Step Synchronization Workflow

Follow this 5-phase procedure systematically:

### Phase 1: Branch Diff Analysis & Change Categorization
1. Identify the merge base and generate the full diff:
   ```powershell
   git merge-base main HEAD
   git diff main...HEAD --stat
   git diff main...HEAD --name-status
   git log main..HEAD --oneline
   ```
2. Review the **Change Manifest** from the drift script output, which categorizes changes into:
   - **Pipeline / Agents**: Modified agent classes, new skills, prompt changes.
   - **CLI / Configuration**: New subcommands, options, environment variables.
   - **Storage / Models**: Schema changes, new Pydantic models, migration utilities.
   - **Web / TUI**: Dashboard redesigns, new components, API endpoint changes.
   - **Utils / Engines**: New algorithms, rate limiter changes, diff patcher updates.
   - **Tests**: New test files, test count growth.
3. For each changed source file, **read the actual diff** to understand the semantic change:
   ```powershell
   git diff main...HEAD -- path/to/changed/file.py
   ```

### Phase 2: Documentation Target Mapping
Consult [references/doc_inventory_matrix.md](./references/doc_inventory_matrix.md) and the **Change Manifest** to determine which documentation files must be updated:

- **Root Docs**:
  - `README.md`: User quickstart, CLI command overview, feature matrix, installation, test counts.
  - `AGENTS.md`: Operational handbook, layered architecture, Mermaid diagrams, agent roles, memory tiers, model cascade, performance features.
  - `CHANGELOG.md`: Structured release log under `[Unreleased]` (Keep a Changelog format).
- **Subsystem Deep Dives (`doc/`)**:
  - `doc/architecture.md`: System components, rate limiter, safety bisection, fallback chain.
  - `doc/workflow.md`: LangGraph reflection review cycle, procedural graphs, loop thresholds.
  - `doc/agents_deep_dive.md` and `doc/agents/01_*.md` through `05_*.md`: Agent prompts, schemas, RAG roles.
  - `doc/api_reference.md`: Core Python classes, methods, and types.
  - `doc/user_guide.md` & `doc/tui_guide.md`: CLI commands, options, and TUI keybindings.
  - `doc/hybrid_rag.md`: SQLite FTS5, vector search, cross-encoder reranking.

### Phase 3: Core Architecture & Diagram Synchronization
1. **Read each changed source file** to understand the actual implementation:
   - For new modules: Read the full file to understand its purpose and API.
   - For modified modules: Read the diff to understand what changed.
2. **Mermaid Diagrams**: Update state and sequence diagrams to reflect new pipeline nodes, edges, and transitions:
   - Ensure all node labels with brackets or parentheses are double-quoted (`["..."]`).
   - Adhere to supported Mermaid diagram types (`graph TD`, `graph LR`, `stateDiagram-v2`, `sequenceDiagram`).
3. **Five Pipeline Agents Table**:
   - Verify agent roles, classes, production models, fallback models, and source file links match code.
4. **Engine Highlights**:
   - For each new algorithm, engine, or subsystem added on the branch, add a concise numbered entry under Section 7 of `AGENTS.md`.

### Phase 4: CLI & Configuration Reference Synchronization
1. **CLI Commands & Flags**:
   - Ensure every subcommand (e.g. `init`, `batch`, `tui`, `web`, `graph-info`, `learn-graph`, `narrative`, `migrate-rag`, `lore`, `traces`, `realign-chapters`) is documented with its aliases and options.
   - Verify default option values match the default arguments in `src/nousetsu/cli/app.py`.
2. **Environment Cascade**:
   - Verify `.env.example` lists all active variables, and `AGENTS.md` / `README.md` describe the 4-tier precedence cascade accurately.
3. **Test Counts**:
   - Update test suite metrics (e.g. "398 tests across 54 modules") across `README.md` and `AGENTS.md` using the exact values from the drift script.

### Phase 5: Changelog & Release Notes
1. Add an entry under `[Unreleased]` in `CHANGELOG.md`:
   - `### Added`: New CLI commands, agent skills, engines, subsystems added on this branch.
   - `### Changed`: Model default updates, prompt enhancements, test speedups.
   - `### Fixed`: Bug fixes, schema validations, encoding guards.
2. Use the **branch commit log** (`git log main..HEAD --oneline`) as the source of truth for changelog entries.
3. Adhere to [references/documentation_standards.md](./references/documentation_standards.md) for formatting rules, alert callouts, and clickable `file://` links.

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
