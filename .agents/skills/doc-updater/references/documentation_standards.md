# Documentation Standards & Formatting Guidelines

This guide establishes the stylistic, structural, and semantic rules for all documentation files (`AGENTS.md`, `README.md`, `CHANGELOG.md`, and `doc/**/*.md`) in this repository.

---

## 1. Clickable File & Symbol Links

All references to repository files, source modules, classes, and CLI commands must be formatted as clickable GitHub-style markdown links:

- **Files**: `[` `filename.ext` `](` `file:///absolute/path/to/file` `)` or `[` `filename.ext` `](` `./relative/path/to/file.ext` `)`.
  - On Windows, always use forward slashes (`/`), e.g.:
    `[` `app.py` `](` `file:///D:/Code/novel_translation_Agent/src/nousetsu/cli/app.py` `)`
- **Classes & Functions**: Use backticks with links:
  - `[` `ContextAwareDrafterAgent` `](` `file:///D:/Code/novel_translation_Agent/src/nousetsu/agents/drafter.py` `)`
  - Direct line link: `[` `LineSemanticChunker` `](` `file:///D:/Code/novel_translation_Agent/src/nousetsu/utils/chunker.py#L45-L80` `)`

---

## 2. GitHub-Flavored Markdown Alerts

Use standard GitHub alert callouts to highlight operational constraints, warnings, and architectural notes. Never stack consecutive alerts without intervening text:

```markdown
> [!NOTE]
> Informational context, non-breaking architectural notes, or background explanations.

> [!TIP]
> Operational shortcuts, performance optimization tips, or recommended commands.

> [!IMPORTANT]
> Critical setup requirements, model prerequisites, or configuration necessities.

> [!WARNING]
> Deprecation warnings, behavioral breaking changes, or rate limit caveats.

> [!CAUTION]
> High-risk operations (e.g. database resetting, stage deletion, or quota exhaustion).
```

---

## 3. Mermaid Diagram Standards

All architecture workflows, agent reflection loops, and state machines must use valid Mermaid syntax that renders cleanly in GitHub, VS Code, and IDE previewers:

- **Supported Types**:
  - `graph TD` / `graph LR` (Flowcharts and component interactions)
  - `stateDiagram-v2` (Agent lifecycle and reflection review loops)
  - `sequenceDiagram` (Multi-agent messaging and batch orchestrations)
  - `classDiagram` (Data models, schemas, and Pydantic relationships)
- **Label Quoting Rule**:
  - Any node label containing parentheses, brackets, or punctuation **MUST** be enclosed in double quotes:
    ```mermaid
    A["SlidingWindowRateLimiter (32,000 TPM / 60 RPM)"] --> B["FallbackChatModel (gemini-3.5-flash-lite)"]
    ```
  - Never use raw `<br>` or unescaped HTML tags inside bracketed labels if double quotes are omitted.

---

## 4. Keep a Changelog Guidelines (`CHANGELOG.md`)

When updating `CHANGELOG.md`, follow the standard [Keep a Changelog](https://keepachangelog.com/) convention:

```markdown
## [Unreleased] (or [X.Y.Z] - YYYY-MM-DD)

### Added
- New user-facing features, CLI commands, or pipeline agents.

### Changed
- Refactored components, updated model defaults, or prompt optimizations.

### Fixed
- Bug fixes, schema validations, or error recovery enhancements.

### Deprecated
- Features scheduled for removal in subsequent releases.

### Removed
- Removed deprecated flags, obsolete models, or unused modules.

### Security
- Vulnerability patches, API key sanitization, or safety block resilience.
```

---

## 5. Rich & Textual CLI Readability

Because project users view markdown outputs via Rich and Textual TUI readers:
- Keep table widths reasonable and columns clearly headered.
- Ensure terminal code blocks specify the exact shell syntax (`powershell`, `bash`).
- Avoid unsupported Unicode glyphs that may trigger Windows `cp1252` encoding exceptions on legacy shells; use clean ASCII/Unicode compatible markers.
