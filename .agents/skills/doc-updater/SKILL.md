---
name: doc-updater
description: >-
  Systematically audits, synchronizes, and exhaustively verifies project documentation (README.md, AGENTS.md, docs/ guides, API references, CLI manuals, architecture diagrams, CHANGELOG.md) against the codebase. Re-checks every related file, code symbol, CLI command/flag, environment variable, and snippet. Triggers on "update document to latest version of code", "sync docs", "refresh documentation", "update README", "re check every relate files and code on docs", or "align docs with code".
---

# Documentation Updater Skill (`doc-updater`)

This skill provides an automated, rigorous, multi-phase procedure to inspect codebase modifications, re-check every cited file, class, function, method, CLI flag, configuration option, and code snippet in project documentation, and synchronize all documents to reflect the true state of the software.

---

## 1. Activation Triggers

Activate this skill when:
- The user requests:
  - *"update document to latest version of code"*
  - *"re check every relate files and code on docs"*
  - *"sync docs"* or *"refresh documentation"*
  - *"align docs with code"* or *"audit doc links"*
  - *"update README and AGENTS.md"*
- Major features, new pipeline agents, procedural graphs, or new CLI subcommands/options have been added or modified.
- A feature branch is ready for merge/PR into `main`.
- A release or version tag is being prepared.

---

## 2. Exhaustive Pre-Flight Code-to-Doc Audit

Before modifying any documentation files, run the deep code-to-doc drift auditor:

```powershell
.\.venv\Scripts\python.exe .agents/skills/doc-updater/scripts/check_doc_drift.py
```

### Deep Verification Capabilities
This script automatically performs a 7-point integrity check:
1. **Branch Diff & Change Manifest**: Identifies all files modified, added, or deleted since diverging from `main`, mapping them to affected documentation targets.
2. **File & Line Anchor Verification**: Audits all `file:///` URLs and relative links across `README.md`, `AGENTS.md`, and all `docs/**/*.md`. Ensures target files exist on disk and validates that line anchors (`#L{start}-L{end}`) are within file line boundaries.
3. **AST Symbol Verification**: Uses Python's Abstract Syntax Tree (`ast.parse`) to verify that classes, functions, and methods cited in markdown links (e.g. `[ClassName](file:///path/to/file.py)`) actually exist in the target file.
4. **CLI Commands & Option Flags Parity**: Introspects `src/nousetsu/cli/app.py` for all subcommands, aliases, flags (`--chapter`, `-c`, `--filter-extractor`, `--reconcile-terms`, etc.), defaults, and help text. Detects undocumented flags in code or hallucinated flags in docs.
5. **Environment Configuration Parity**: Compares `NOVEL_*` variables in docs against `.env.example` and `src/nousetsu/config/`.
6. **Agent Skills & Catalog Inventory**: Cross-checks skill counts and skill names in `AGENTS.md` and `docs/agents_deep_dive.md` against `src/nousetsu/skills/catalog/*.md`.
7. **Mermaid Diagrams & Python Snippet Syntax**: Ensures all Mermaid node labels with special characters (parentheses, brackets, colons) are properly double-quoted (`id["..."]`), and validates Python code blocks via `ast.parse`.
8. **Test Suite Metrics**: Queries `pytest --collect-only` to ensure test counts (e.g. `416 tests across 59 modules`) match reality.

### Optional Auditor Flags
- `--fix`: Automatically synchronizes stale test count references and fixes legacy `doc/` $\to$ `docs/` link typos.
- `--strict`: Fails with exit code 1 if any broken link, nonexistent symbol, or stale test count is detected (ideal for CI/verification).
- `--json`: Emits a structured JSON audit report for automated tooling.

---

## 3. Step-by-Step 7-Phase Synchronization Workflow

Follow this procedure systematically:

### Phase 1: Branch Diff Analysis & Change Categorization
1. Identify the merge base and inspect the full branch diff:
   ```powershell
   git merge-base main HEAD
   git diff main...HEAD --stat
   git diff main...HEAD --name-status
   git log main..HEAD --oneline
   ```
2. Review the **Change Manifest** output from `check_doc_drift.py`. Categorize changes into:
   - **Pipeline / Agents**: Modified agent classes, prompt changes, structured schemas.
   - **CLI / Commands**: New subcommands, new flags, changed defaults.
   - **Storage / Models**: Pydantic schema changes, Novel Bible memory tiers, migration scripts.
   - **Web / TUI**: New UI panels, shortcuts, API endpoints.
   - **Utils / Engines**: Rate limiters, diff patchers, chunkers, safety bisection.
   - **Tests**: New test modules, test count additions.

### Phase 2: Documentation Target Mapping
Consult [references/doc_inventory_matrix.md](./references/doc_inventory_matrix.md) and map every changed code file to its primary and secondary documentation targets in `README.md`, `AGENTS.md`, and `docs/`.

### Phase 3: Deep Code-to-Doc Reference Re-Check
For every file and code entity cited in documentation:
1. **Source File Existence**: Verify that the file exists in the repository. Never point to legacy or renamed folders (e.g. use `docs/` instead of `doc/`).
2. **Code Symbol Verification**: Verify that the class, function, or method name matches the code definition. If a class was refactored (e.g. `apply_diff_patch` function instead of `DiffPatcher` class), update the doc link and text accordingly.
3. **Line Number Anchors**: If referencing line ranges (`#L10-L25`), verify that the line range is accurate and within the file's line count.
4. **CLI Option Flags**: Check every documented command invocation (`nousetsu <cmd> [options]`). Ensure every flag exists in `src/nousetsu/cli/app.py`.
5. **Configuration Settings**: Verify all `NOVEL_*` environment variables in docs match `.env.example`.

### Phase 4: Core Architecture & Diagram Synchronization
1. **Mermaid Diagrams**: Update state and sequence diagrams to reflect new pipeline nodes, edges, and transitions:
   - Ensure all node labels with brackets, parentheses, colons, or line breaks are double-quoted (`id["..."]`).
   - Adhere to supported Mermaid diagram types (`graph TD`, `graph LR`, `stateDiagram-v2`, `sequenceDiagram`, `classDiagram`).
2. **Five Pipeline Agents Table**:
   - Verify agent roles, classes, production models, fallback models, and source file links match code.
3. **Engine Highlights**:
   - For each new algorithm, engine, or subsystem added on the branch, add a concise numbered entry under Section 7 of `AGENTS.md` and the Key Innovations section in `README.md`.

### Phase 5: CLI & Configuration Reference Synchronization
1. **CLI Commands & Flags**:
   - Ensure every subcommand (e.g. `init`, `batch`, `tui`, `web`, `scan`, `skills`, `graph-info`, `learn-graph`, `narrative`, `lore`, `migrate-rag`, `traces`, `realign-chapters`) is documented with all its aliases and options.
   - Verify default option values match the default arguments in `src/nousetsu/cli/app.py`.
2. **Environment Cascade**:
   - Verify `.env.example` lists all active variables, and `AGENTS.md` / `README.md` describe the 4-tier precedence cascade accurately.
3. **Test Counts**:
   - Update test suite metrics (e.g. "416 tests across 59 modules") across `README.md` and `AGENTS.md` using the exact values from `check_doc_drift.py`.

### Phase 6: Changelog & Release Notes
1. Add an entry under `[Unreleased]` in `CHANGELOG.md`:
   - `### Added`: New CLI commands, agent skills, engines, subsystems.
   - `### Changed`: Model default updates, prompt enhancements, test speedups.
   - `### Fixed`: Bug fixes, schema validations, encoding guards.
2. Use the **branch commit log** (`git log main..HEAD --oneline`) as the source of truth for changelog entries.
3. Adhere to [references/documentation_standards.md](./references/documentation_standards.md) for formatting rules, alert callouts, and clickable `file://` links.

### Phase 7: Strict Final Verification
After updating documentation files:
1. Re-run the drift audit script with `--strict` to ensure zero broken links, symbols, or stale metrics remain:
   ```powershell
   .\.venv\Scripts\python.exe .agents/skills/doc-updater/scripts/check_doc_drift.py --strict
   ```
2. Verify git diff to ensure documentation updates are clean, precise, and preserve existing comments:
   ```powershell
   git diff --stat
   ```
3. Run the test suite to ensure no code or test regressions occurred:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest -q
   ```
