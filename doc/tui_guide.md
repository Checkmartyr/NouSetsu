# 🖥️ Interactive Terminal UI (TUI) & Operation Guide

**NouSetsu** includes a full-featured, reactive terminal user interface built with **Textual** and **Rich**. The TUI provides an immersive environment to inspect chapters, monitor multi-agent translation progress, review quality scores, edit the Novel Bible, and manage projects.

---

## 🎨 TUI Layout Overview

```
┌─ NouSetsu ──────────────────────────────────────────────────────────── [12:00:00] ─┐
│ 📚 Chapters (85%+ Height)         │ 📖 Dual Reader Pane (80% Viewport)             │
│                                   │ ┌────────────────────────┬───────────────────┐ │
│  ✓ Ch.001 - Awakening             │ │ 🇺🇸 English Source      │ 🇹🇭 Thai Polished  │ │
│  ● Ch.002 - Magic Beast           │ │ The boy stepped out.   │ เด็กหนุ่มก้าวเดิน..│ │
│  · Ch.003 - Forest Encounter      │ └────────────────────────┴───────────────────┘ │
│  · Ch.004 - Royal Castle Gate     ├────────────────────────────────────────────────┤
│  · Ch.005 - Ancient Dragon        │ ⚡ Progress: 📖 Ch.002 [████████░░░░░░░░] 50%    │
│  · Ch.006 - Secret Library        │ Stage: [2/5 DRAFTING] | Status: Translating... │
│  · Ch.007 - The Alchemist         ├────────────────────────────────────────────────┤
│  · Ch.008 - Shadow Guild          │ 📊 Inspector: Fidelity: 9.5 | Style: 9.2       │
│                                   │ Tokens: 1,284 in 3.9s | Status: COMPLETED      │
├───────────────────────────────────┴────────────────────────────────────────────────┤
│ [▶ Translate (T)]   [⚡ Batch All (B)]   [⏹ Stop (X)]       [📖 Bible (E)]          │
│ [📁 Projects (P)]   [✨ New (N)]          [⚙ Settings (S)]   [✖ Quit (Q)]           │
└────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🧭 Main Interface Components

### 1. Minimal Chapter Sidebar & Status Badges
Displays all discovered chapters in natural numerical order (`Ch.001`, `Ch.002`, `Ch.010`) utilizing over 85% vertical height for maximum reading visibility. Each chapter is prepended with a minimal unicode status glyph:

| Glyph | Status | Meaning | Action Available |
| :---: | :--- | :--- | :--- |
| `✓` | `COMPLETED` | Translation completed and verified against source SHA-256 hash. | Review in Dual Reader. |
| `●` | `IN_PROGRESS` | Chapter actively undergoing pipeline execution. | Watch live progress / Press `X` to pause. |
| `⏸` | `PAUSED` | Translation paused mid-chapter by user; stage artifacts preserved. | Press `T` or `B` to resume instantly. |
| `✕` | `FAILED` | Translation encountered an unrecoverable error or exhausted retries. | Press `T` to retry with exponential backoff. |
| `·` | `WAIT` / `PENDING` | Raw chapter discovered, pending processing. | Press `T` to translate or `B` to batch translate. |

---

### 2. Dual Reader Widget (`src/nousetsu/tui/widgets/reader.py`)
Provides side-by-side synchronized comparison between the raw original text and the translated Markdown:
* **Source Pane**: Displays original Japanese/Chinese/Korean text with full Unicode support.
* **Translated Pane**: Renders target English text rendered as rich Markdown with syntax highlighting and formatting.
* Automatically reloads when a chapter selection changes or when background translation completes.

---

### 3. Real-Time Progress Panel (`src/nousetsu/tui/widgets/progress_panel.py`)
Visualizes live agent execution during translation in a compact 4-line strip:
* **Active Chapter Label**: The progress bar header dynamically binds to the active chapter currently translating (e.g. `📖 Ch.002 - Magic Beast.txt [████████░░░░░░░░] 50%`).
* **Stage Badge**: Displays the current executing agent stage (`1/5 EXTRACTION`, `2/5 DRAFTING`, `3/5 CRITIQUE`, `4/5 POLISHING`, `5/5 CHRONICLING`).
* **Animated Progress Bar**: Smooth percentage progression reflecting stage completion.
* **Status Messaging**: Relays active sub-agent actions (e.g. *"Auditing fidelity, tone, and glossary adherence..."* or *"Server busy (500). Retrying in 6.0s (Attempt 2/4)..."*).

---

### 4. Checkpoint Inspector Bar (`src/nousetsu/tui/widgets/checkpoint_inspector.py`)
Located below the reader pane in a compact 5-line container, displaying deep metadata diagnostics for the selected chapter:
* **Status & Checkpoint**: Displays status, last completed stage, and truncated SHA-256 hash.
* **Quality Audit Scores**:
  * **Fidelity**: `0.0 to 10.0` score measuring semantic accuracy.
  * **Style**: `0.0 to 10.0` score measuring natural prose cadence.
  * **Glossary**: Percentage compliance against canonical terms.
* **Granular Token & Duration Metrics**: Formats cumulative token usage and elapsed duration using human-friendly formatting (`3.9s`, `2m 15s`, `1h 4m`):
  ```text
  Tokens: 1,284 in 3.9s (In: 820 Out: 364)
  ```
* **Warnings & Error Diagnostics**: Lists dropped pronoun warnings, or highlights the exact `failed_stage`, `error_type`, and retry count if the chapter failed.

---

## 🪟 Modals & Configuration Windows

### 1. Novel Bible Modal (`E` key)
* **Characters Tab**: Displays registered character sheets (name, original script, gender, role, vocal tone, aliases).
* **Glossary Tab**: Formatted table of canonical terms, categories, and translation notes.
* **Languages Tab**: Configure or swap source and target languages, or trigger auto-detection from raw chapters.
* **Summaries Tab**: Comprehensive 3-tier narrative memory inspector displaying:
  * **Whole Story Progression Banner**: High-level synopsis of the novel's journey.
  * **Active Story Arc Card**: Active arc title, core conflict, and key milestones achieved.
  * **Concluded Arcs Accordion**: Collapsible history of completed volumes/story arcs.
  * **Chapter Summaries Tree**: Grouped by volume folder with key events and character state changes.
* **Add New Term Tab**: Quick-form to inject new canonical terms directly into the Novel Bible.
* **Dismissal**: Universal `Esc` key, `Q` key, or top-right `✖ Close (Esc)` button. The dialog body uses flex layout (`TabbedContent { height: 1fr; }`) to ensure close buttons are never pushed off screen.

---

### 2. Token Analysis Dashboard (`M` key)
* **Interactive Analytics**: Press `M` or click `[📊 Tokens (M)]` in the action toolbar to inspect real-time resource consumption.
* **KPI Metric Cards**: Displays global totals for Prompt Tokens, Completion Tokens, Thought Tokens (Gemini reasoning), Cached Tokens, and Total Execution Duration.
* **Pipeline Stage DataTable**: Per-stage breakdown of tokens and duration across Extraction, Drafting, Critique passes, Polishing passes, and Chronicling.
* **Model Consumption DataTable**: Tracks cost and token distribution by LLM model (`gemini-3.1-flash-lite`, `gemini-3.5-flash-lite`, `gemma-4-26b-a4b-it`).
* **Chapter Ranking DataTable**: Ranks chapters by total tokens and duration to pinpoint unusually dense chapters.

---

### 3. Folder / Volume Selector Modal (`F` key)
* When working with multi-volume novels (e.g. `Villainess_04`, `Villainess_05`), allows switching the active working volume with a single click, auto-resolving input and output folders.

---

### 4. Project Selector Modal (`P` key)
* Lists all known novel translation projects across the machine.
* **Open from Path**: Paste any external folder path on your computer (e.g. `D:\Novels\MyBook` or `~/workspace/novel`) and hit Enter to open or auto-initialize.
* Remembers the `last_active_project` so returning to NouSetsu automatically reopens your active book.

---

### 5. New Project Modal (`N` key)
* Initialize a brand-new translation project.
* Configures project title, filesystem directory, source/target languages, custom raw chapter folder name (e.g. `raw_chapters`), and translated folder name (e.g. `translated_chapters`).

---

### 6. Settings Modal (`S` key)
* **Model Configuration & Routing**:
  * **Primary Model (`model_name`)**: Base model for unconfigured stages (default: `gemini-3.1-flash-lite`).
  * **Fallback Model (`fallback_model`)**: Failover model used automatically on HTTP 429 quota exhaustion (default: `gemini-3.5-flash-lite`).
  * **Per-Stage Agent Routing**: Assign specialized LLMs per role (e.g. `drafter_model="gemini-3.5-flash-lite"`, `critic_model="gemma-4-26b-a4b-it"`, `polisher_model="gemini-3.5-flash-lite"`, `chronicler_model="gemma-4-26b-a4b-it"`).
* **Language Pairs**: Modify source and target languages (default: English $\to$ Thai for Villainess projects).
* **Style Guide**: Configure narrative tense (past/present), POV (third/first person), reading level, and honorific mode.
* **⚡ API Rate Limits & Throttling Guard**:
  * `Max Tokens Per Minute (TPM)`: Default 32,000 TPM.
  * `Max Requests Per Minute (RPM)`: Default 60 RPM.
* **Line-Based Semantic Chunking**:
  * `Chunk Threshold Lines`: Minimum non-empty lines to trigger chunking (default: 85).
  * `Target Chunk Lines`: Target line count per semantic chunk (default: 70).
* **🔄 Review Loop & Quality Control**:
  * `Max Review Loops`: Allow 1 to 5 iterative passes (default: 3).
  * `Quality Threshold`: Score required to skip further review passes (default: 8.5/10).
* **Directory Paths**: Dynamically change raw chapters and translated chapters folders.

---

## 🛑 Thread-Safe Stop & Interruption Controls

* **Toolbar Stop Button**: Clicking `[⏹ Stop (X)]` (`#btn_stop`) in the bottom action bar or pressing `X` sends an immediate halt signal.
* **UI Mutual Exclusion**: When translation starts, `btn_stop` is automatically enabled while `btn_translate` and `btn_batch` are disabled, preventing race conditions or double triggers.
* **Interruptible Cooldown**: Rate limit sleep intervals are sliced into 200–250ms chunks, ensuring the application responds instantaneously to stop requests.
* **Checkpoint Protection**: Pausing a chapter preserves all completed stages into `.novel/metadata.json` with status `StageStatus.PAUSED`, allowing seamless one-click resumption.

---

## ⌨️ Complete Keyboard Shortcuts Reference

| Shortcut | Action | Description |
| :---: | :--- | :--- |
| `T` | **Translate Selected** | Run agent translation on currently selected chapter (or resume if paused/failed) |
| `B` | **Run All Batch** | Trigger background batch translation across all pending chapters |
| `X` | **Stop Translation** | Gracefully halt active translation and save pause checkpoint |
| `E` | **Novel Bible** | Open in-terminal editor to inspect/add characters, glossary, and 3-tier summaries |
| `M` | **Token Analytics** | Open real-time Token & Latency Analytics dashboard with DataTables |
| `F` | **Volume Selector** | Switch active translation folder/volume in multi-folder projects |
| `P` | **Project Selector** | Switch active project or open an external project from folder path |
| `N` | **New Project** | Open wizard to initialize a new novel translation workspace |
| `S` | **Settings** | Adjust model, language pair, rate limits, review loops, and style guide |
| `R` | **Refresh** | Re-scan chapters, recompute hashes, and refresh status badges |
| `Q` | **Quit** | Exit the TUI application (or close active modal) |
| `Esc` | **Close Modal** | Universally dismiss any open dialog and return to main reader |
| `↑` / `↓` | **Navigate** | Move selection up and down the chapter list |
| `Tab` | **Cycle Focus** | Shift focus between chapter list, action buttons, and reader panes |
