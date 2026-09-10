# 🖥️ Interactive Terminal UI (TUI) & Operation Guide

**NouSetsu** includes a full-featured, reactive terminal user interface built with **Textual** and **Rich**. The TUI provides an immersive environment to inspect chapters, monitor multi-agent translation progress, review quality scores, edit the Novel Bible, and manage projects.

---

## 🎨 TUI Layout Overview

```
┌───────────────────────────┬────────────────────────────────────────────────────────┐
│ 📁 Chapters (Sidebar)     │ 📖 Dual Reader Pane                                    │
│                           │                                                        │
│ [DONE] Ch.001 - Awakening │ ┌──────────────────────────┬─────────────────────────┐ │
│ [FAILED] Ch.002 - Magic   │ │ 🇯🇵 Source Chapter       │ 🇬🇧 Translated Chapter   │ │
│ [WAIT] Ch.003 - Forest    │ │                          │                         │ │
│                           │ │ 少年は剣を手に取った。   │ The boy took the sword. │ │
│                           │ └──────────────────────────┴─────────────────────────┘ │
│                           ├────────────────────────────────────────────────────────┤
│ [Translate Selected (T)]  │ ⚡ Live Progress Panel                                  │
│ [Run All Batch (B)]       │ Stage: [3/5 CRITIQUE] [████████████░░░░░░░░] 60%       │
│ [Novel Bible (E)]         │ Status: Auditing fidelity, tone, and glossary...       │
│ [Projects (P)]            ├────────────────────────────────────────────────────────┤
│ [Settings (S)]            │ 📊 Checkpoint Inspector                                │
│                           │ Status: COMPLETED | Fidelity: 9.5/10 | Style: 9.2/10   │
└───────────────────────────┴────────────────────────────────────────────────────────┘
```

---

## 🧭 Main Interface Components

### 1. Chapter Sidebar & Status Badges
Displays all discovered chapters in natural numerical order (`Ch.001`, `Ch.002`, `Ch.010`). Each chapter is prepended with a live reactive badge:

| Badge | Meaning | Action Available |
| :--- | :--- | :--- |
| `[bold green][DONE][/]` | Translation completed and verified against source SHA-256 hash. | Review in Dual Reader. |
| `[bold red][FAILED][/]` | Translation encountered an unrecoverable error or exhausted retries. | Press `T` to retry with exponential backoff. |
| `[bold yellow][RESUME:DRAF][/]` | Chapter has intermediate checkpoint artifacts saved. | Press `T` to resume from the last completed stage. |
| `[dim][WAIT][/]` | Raw chapter discovered, pending processing. | Press `T` to translate or `B` to batch translate. |

---

### 2. Dual Reader Widget (`src/tui/widgets/reader.py`)
Provides side-by-side synchronized comparison between the raw original text and the translated Markdown:
* **Source Pane**: Displays original Japanese/Chinese/Korean text with full Unicode support.
* **Translated Pane**: Renders target English text rendered as rich Markdown with syntax highlighting and formatting.
* Automatically reloads when a chapter selection changes or when background translation completes.

---

### 3. Real-Time Progress Panel (`src/tui/widgets/progress_panel.py`)
Visualizes live agent execution during translation:
* **Stage Badge**: Displays the current executing agent stage (`1/5 EXTRACTION`, `2/5 DRAFTING`, `3/5 CRITIQUE`, `4/5 POLISHING`, `5/5 CHRONICLING`).
* **Animated Progress Bar**: Smooth percentage progression reflecting stage completion.
* **Status Messaging**: Relays active sub-agent actions (e.g. *"Auditing fidelity, tone, and glossary adherence..."* or *"Server busy (500). Retrying in 6.0s (Attempt 2/4)..."*).

---

### 4. Checkpoint Inspector Bar (`src/tui/widgets/checkpoint_inspector.py`)
Located at the bottom of the interface, displaying deep metadata diagnostics for the selected chapter:
* **Status & Checkpoint**: Displays status, last completed stage, and truncated SHA-256 hash.
* **Quality Audit Scores**:
  * **Fidelity**: `0.0 to 10.0` score measuring semantic accuracy.
  * **Style**: `0.0 to 10.0` score measuring natural prose cadence.
  * **Glossary**: Percentage compliance against canonical terms.
* **Warnings & Error Diagnostics**: Lists dropped pronoun warnings, or highlights the exact `failed_stage`, `error_type`, and retry count if the chapter failed.

---

## 🪟 Modals & Configuration Windows

### 1. Novel Bible Modal (`E` key)
* **Characters Tab**: Displays registered character sheets (name, original script, gender, role, vocal tone, aliases).
* **Glossary Tab**: Formatted table of canonical terms, categories, and translation notes.
* **Languages Tab**: Configure or swap source and target languages.
* **Add New Term Tab**: Quick-form to inject new canonical terms directly into the Novel Bible.
* **Dismissal**: Universal `Esc` key, `Q` key, or top-right `✖ Close (Esc)` button. The dialog body uses flex layout (`TabbedContent { height: 1fr; }`) to ensure close buttons are never pushed off screen.

---

### 2. Project Selector Modal (`P` key)
* Lists all known novel translation projects across the machine.
* **Open from Path**: Paste any external folder path on your computer (e.g. `D:\Novels\MyBook` or `~/workspace/novel`) and hit Enter to open or auto-initialize.
* Remembers the `last_active_project` so returning to NouSetsu automatically reopens your active book.

---

### 3. New Project Modal (`N` key)
* Initialize a brand-new translation project.
* Configures project title, filesystem directory, source/target languages, custom raw chapter folder name (e.g. `raw_chapters`), and translated folder name (e.g. `translated_chapters`).

---

### 4. Settings Modal (`S` key)
* Adjust LLM model name (e.g. `gemini-2.5-pro`, `gemini-2.5-flash`).
* Adjust style guide rules (narrative tense, POV, reading level, honorific mode).
* Switch folder directories dynamically.

---

## ⌨️ Complete Keyboard Shortcuts Reference

| Shortcut | Action | Description |
| :---: | :--- | :--- |
| `T` | **Translate Selected** | Run agent translation on currently selected chapter (or retry if failed) |
| `B` | **Run All Batch** | Trigger background batch translation across all pending chapters |
| `E` | **Novel Bible** | Open in-terminal editor to inspect/add characters, glossary, and languages |
| `P` | **Project Selector** | Switch active project or open an external project from folder path |
| `N` | **New Project** | Open wizard to initialize a new novel translation workspace |
| `S` | **Settings** | Adjust LLM model, language pair, style guide, and folder paths |
| `R` | **Refresh** | Re-scan chapters, recompute hashes, and refresh status badges |
| `Q` | **Quit** | Exit the TUI application (or close active modal) |
| `Esc` | **Close Modal** | Universally dismiss any open dialog and return to main reader |
| `↑` / `↓` | **Navigate** | Move selection up and down the chapter list |
| `Tab` | **Cycle Focus** | Shift focus between chapter list, action buttons, and reader panes |
