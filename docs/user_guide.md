# 📖 NouSetsu User Guide

> **The Complete End-User Manual for Agentic Document-Level Novel Translation**  
> Powered by LangGraph, Textual, React 19, Tauri, and Rich.

---

## 📑 Table of Contents

1. [Introduction](#-1-introduction)
2. [Installation & Setup](#-2-installation--setup)
3. [60-Second Quickstart (The Textual TUI Dashboard)](#-3-60-second-quickstart-the-textual-tui-dashboard) — see the [Web Studio & Desktop App Guide](./web_desktop_guide.md) for app workflows.
4. [Headless CLI & Batch Automation](#-4-headless-cli--batch-automation)
5. [Agent Skills System](#-5-agent-skills-system)
6. [Procedural Graph Execution (Zero-Token Overhead)](#-6-procedural-graph-execution-zero-token-overhead)
7. [Managing the Novel Bible & Lore](#-7-managing-the-novel-bible--lore)
8. [Enterprise Safety Guards](#-8-enterprise-safety-guards)
9. [Gemini Interactions API & Granular Token Tracking](#-9-gemini-interactions-api--granular-token-tracking)
10. [Troubleshooting & FAQ](#-10-troubleshooting--faq)

---

## 🌟 1. Introduction

Traditional machine translation tools (e.g. Google Translate, DeepL) process texts sentence-by-sentence or paragraph-by-paragraph. While serviceable for short technical documents, this approach fails disastrously for literary novels:
* **Pronoun Disappearance (*Zero-Anaphora*)**: In East Asian languages (Japanese, Chinese, Korean), subjects and pronouns are frequently omitted in dialogue and narration. Generic MT engines guess blindly or invent random pronouns ("he/she/it"), destroying immersion.
* **Character Voice Drift**: A haughty tsundere villainess sounds identical to an ancient martial arts grandmaster.
* **Term Inconsistency**: A martial arts technique or magical artifact changes spelling every three paragraphs.
* **Memory Loss**: MT engines have zero awareness of events that took place in preceding chapters.

**NouSetsu** solves this with a collaborative 5-stage agent pipeline coordinated by **LangGraph**:
1. **Entity Extractor** (*EntityExtractorAgent*): Discovers new character names, factions, and terms before translation.
2. **Context-Aware Drafter** (*ContextAwareDrafterAgent*): Resolves omitted pronouns (*Zero-Anaphora*) and character voices using the persistent **Novel Bible**.
3. **Critique Agent** (*CritiqueAgent*): Audits the draft against the full raw source text for fidelity (0-10) and prose style (0-10).
4. **Polishing Agent** (*PolishingAgent*): Refines draft prose into literary, publication-grade target language fiction using critique notes and source text reference.
5. **Chronicler Agent** (*ChroniclerAgent*): Summarizes chapter turning points, updates rolling lore memory, and compiles checkpoint metadata into `.novel/metadata.json`.

---

## 🛠️ 2. Installation & Setup

### Prerequisites
* **Python 3.13+** installed on your system for source and CLI installs.
* Optional but recommended: [uv](https://github.com/astral-sh/uv) (ultra-fast Python package installer).

### Windows Desktop Installer
The Windows desktop installer bundles the Python backend, so Python is not required separately. On first launch, NouSetsu copies the packaged `.env.example` to its application-data directory as `.env` if no local environment file exists. Existing settings are preserved on later launches and upgrades. Configure provider keys in **Settings → Environment & API Keys**; keys are stored locally in `.env`, so protect that file and never put live secrets in `.env.example`. See the [Web Studio & Desktop App Guide](./web_desktop_guide.md) for the complete workflow.

### Option A: Install from Local Repository / Pip (Recommended)
You can install NouSetsu directly into your Python environment:

```bash
# Clone the repository
git clone https://github.com/Checkmartyr/NouSetsu.git
cd NouSetsu

# Install with pip
pip install .

# Or install with uv
uv pip install .
```

Once installed, two console commands are available globally in your terminal:
* `nousetsu`: Primary command.
* `novel`: Convenient shorthand alias.

### Option B: Run from Source with `uv`
If you prefer running from source without global installation:
```bash
git clone https://github.com/Checkmartyr/NouSetsu.git
cd NouSetsu
uv sync
```

### Option C: Run with Docker Compose
If you prefer running containerized with zero local Python/Node dependencies:
```bash
git clone https://github.com/Checkmartyr/NouSetsu.git
cd NouSetsu

# Configure environment variables
cp .env.example .env

# Launch Web Studio container
docker compose up -d

# Open http://localhost:5173 in your browser
```

You can also execute headless batch translations or project scans via Docker Compose:
```bash
# Scan novel projects
docker compose run --rm nousetsu scan --all-projects

# Run batch translation
docker compose run --rm nousetsu batch --project-dir Douyara -c 48
```

### Configuring API Keys
NouSetsu supports Gemini/Google, OpenAI, OpenRouter, custom OpenAI-compatible endpoints, and an offline mock model. For the browser Web Studio or desktop app, configure credentials in **Settings → Environment & API Keys**. For CLI use, add the variables for your chosen provider to the local `.env` file:

```dotenv
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key
OPENROUTER_API_KEY=your-openrouter-key
CUSTOM_API_BASE_URL=https://provider.example/v1
CUSTOM_API_KEY=your-custom-provider-key
```

For a custom endpoint, also select **Custom OpenAI-compatible** as the model route and specify its model ID. See the [Web Studio & Desktop App Guide](./web_desktop_guide.md#configure-model-providers-and-api-keys) for the full setup steps. Keep `.env` private; never put live keys in `.env.example` or commit them.

> [!NOTE]
> If no API key is provided, NouSetsu automatically operates with a deterministic offline mock model (`mock-novel-llm`), allowing you to test UI navigation, batch scanning, and checkpoint resumption without consuming API tokens.

---

## 🖥️ 3. 60-Second Quickstart (The Textual TUI Dashboard)

The fastest and most intuitive way to translate novels is via the interactive **Textual Terminal User Interface (TUI)**.

### Launching the TUI
Simply open your terminal and type:
```bash
nousetsu
```
*(Or use the shortcut `novel`).*

If you have an active novel project, it loads immediately. If you are in a new or uninitialized directory, the dashboard opens ready for you to create or pick a project!

```text
┌─ NouSetsu ──────────────────────────────────────────────────────────── [12:00:00] ─┐
│ 📚 Chapters (85% Height)          │ 📖 Dual Reader Pane (80% Viewport)             │
│  ✓ Ch.001 - Awakening             │ ┌────────────────────────┬───────────────────┐ │
│  ⏸ Ch.002 - Magic Beast           │ │ 🇺🇸 English Source      │ 🇹🇭 Thai Polished  │ │
│  · Ch.003 - Forest Encounter      │ │ The boy stepped out.   │ เด็กหนุ่มก้าวเดิน..│ │
│  · Ch.004 - Kingdom Royal Gate    │ └────────────────────────┴───────────────────┘ │
│  · Ch.005 - Ancient Dragon        ├────────────────────────────────────────────────┤
│                                   │ ⚡ Progress: 📖 Ch.002 [████████░░░░░░░░] 50%    │
│                                   │ Stage: [2/5 DRAFTING] | Status: Translating... │
│                                   ├────────────────────────────────────────────────┤
│                                   │ 📊 Inspector: Fidelity: 9.5 | Style: 9.2       │
│                                   │ Tokens: 1,284 in 3.9s | Status: COMPLETED      │
├───────────────────────────────────┴────────────────────────────────────────────────┤
│ [▶ Translate (T)]   [⚡ Batch All (B)]   [⏹ Stop (X)]       [📖 Bible (E)]          │
│ [📁 Projects (P)]   [✨ New (N)]          [⚙ Settings (S)]   [✖ Quit (Q)]           │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### TUI Keyboard Shortcuts

| Key | Action | Description |
|:---:|:---|:---|
| `T` | **Translate Selected** | Triggers the 5-stage agentic translation graph on the highlighted chapter. |
| `B` | **Run All Batch** | Batches through all untranslated or resumed chapters in order. |
| `X` | **Stop Translation** | Safely pauses the active translation, saves a `PAUSED` checkpoint, and halts. |
| `E` | **Novel Bible** | Opens the in-terminal editor to inspect/add characters, relationships, and glossary terms. |
| `M` | **Tokens** | Toggles the dedicated Token & Duration Analytics dashboard. |
| `W` | **Web Traces** | Launches or opens the local Vite + React 19 Web Trace Visualizer in browser. |
| `F` | **Folder** | Opens the Folder Selector modal to switch between translation volumes/folders (e.g. Volume 4 vs Volume 5). |
| `P` | **Projects** | Opens the Project Selector modal to switch between novel projects. |
| `N` | **New Project** | Opens the Project Creator modal to configure novel title, languages, and genre. |
| `S` | **Settings** | Opens the Settings modal to tune TPM/RPM rate limits, review loop caps, and model choices. |
| `R` | **Refresh** | Re-scans the raw chapters directory and refreshes chapter list status. |
| `Q` | **Quit** | Exits the application cleanly. |
| `Esc` | **Close Modal** | Dismisses any open dialog modal and returns to the main reader view. |
| `↑` / `↓` | **Navigate** | Moves selection up and down the chapter list. |
| `Tab` | **Cycle Focus** | Cycles focus between sidebar controls and reader panes. |

### Step-by-Step Workflow in TUI

1. **Create a Project**: Press `N`. Enter your novel's title (e.g. *Villainess Reversal*), source language (e.g. *Japanese*, *Chinese*, *Korean*, or *auto*), target language (e.g. *English*, *Thai*), and genre (*isekai*, *wuxia*, *romance*, *general*).
2. **Add Raw Chapters**: Drop your raw text files (`.txt` or `.md`) into the project's `raw_chapters/` directory.
3. **Translate Single Chapter**: Highlight a chapter in the left sidebar and press `T`. Watch the live progress panel transition across Extraction, Drafting, Critique, Polishing, and Chronicling!
4. **Translate Entire Novel**: Press `B` to translate all chapters sequentially.
5. **Interrupt Safely**: If you need to stop, press `X` or click **Stop Translation**. The current chapter is immediately saved with status `[PAUSED:STAGE]`. When you restart or press `T`, it resumes exactly where it stopped without repeating completed stages!

### 🌐 Web Studio & Trace Visualizer (React 19 + Vite)

For visual inspection, web novel scraping, translation, and interactive publishing, NouSetsu provides an integrated **Web Studio** built with React 19 and Vite. For the complete browser workflow and Windows desktop app instructions, see the [Web Studio & Desktop App Guide](./web_desktop_guide.md).

#### Launching the Web Studio
From your terminal, execute:
```bash
# Launch on the local machine (http://127.0.0.1:5173)
nousetsu web
```
*(You can also press `W` from within the running Textual TUI application to open the Web Studio automatically!)*

#### 1. Studio & Batch Translation Dashboard
Inspect real-time chapter queue progress, switch volume folders, trigger single or batch translations, and monitor live streaming SSE execution logs:

![NouSetsu Web Studio Dashboard View](images/web_studio_dashboard_demo.png)

#### 2. Distraction-Free Novel Reader
Read translated literary prose with custom font sizes, background themes (Dark, Sepia, Light), and an instant side-by-side peek to the raw source text:

![NouSetsu Web Studio Reader View](images/web_studio_reader_demo.png)

#### 3. Interactive Novel Bible & Character Sheets
Manage the project's living lore repository with searchable character cards, romanized naming aliases, speech registers, and canonical terms:

![NouSetsu Web Studio Novel Bible View](images/web_studio_bible_demo.png)

#### 4. Forensic Pipeline Traces & Agent Thought Auditing
Inspect raw model prompts, dynamic system instructions, and real-time completions across each stage and reflection review pass:

![NouSetsu Web Studio Traces View](images/web_studio_traces_demo.png)

#### 5. Side-by-Side Diff Comparison
Track how the Polishing Agent refines prose cadence, fixes dropped chapter headers, and eliminates translationese between draft and polished versions:

![NouSetsu Web Studio Diff Comparison](images/web_studio_diff_demo.png)

#### 6. Granular Token & Latency Analytics
Inspect real-time token utilization (input, output, thought, cached) and elapsed duration broken down by stage and LLM model:

![NouSetsu Web Studio Token Analytics](images/web_studio_tokens_demo.png)

#### 7. Categorical Settings & Model Routing
Configure Gemini, OpenAI, OpenRouter, or a custom OpenAI-compatible provider; set primary and fallback routes for each pipeline agent, tune 32K TPM / 60 RPM rate limits, and customize semantic chunking thresholds:

![NouSetsu Web Studio Settings View](images/web_studio_settings_demo.png)

---

## ⚡ 4. Headless CLI & Batch Automation

For headless Linux servers, Docker containers, or automated scripts, NouSetsu provides a full suite of CLI subcommands.

### CLI Command Summary

```bash
# 1. Automatic TUI Dashboard (Default)
nousetsu

# 2. Check Installed Version
nousetsu --version

# 3. Project Initialization
nousetsu init --title "My Novel" --source-lang "Japanese" --target-lang "English" --genre "isekai"

# 4. Headless Batch Translation
nousetsu batch --input-dir raw_chapters --output-dir translated_chapters --limit 10

# 5. Targeted Single Chapter Translation
nousetsu batch -p project/Villainess -F Villainess_05 --chapter 48

# 6. Web Trace Visualizer (React 19 + Vite)
nousetsu web
nousetsu web --port 5173

# 7. Inspect Forensic Prompt Traces
nousetsu traces -p ./my_novel --chapter 1

# 8. Query and Manage Hybrid RAG Knowledge Store
nousetsu lore "Azure Thunder Blade"
nousetsu migrate-rag -p ./my_novel

# 9. Agent Domain Skills Catalog
nousetsu skills --agent drafter --genre isekai

# 10. Inspect Procedural Execution Graphs (Rich Tree)
nousetsu graph-info
nousetsu graph-info --agent drafter

# 11. Inspect 3-Tier Hierarchical Story Memory (Rich Tree)
nousetsu narrative
nousetsu narrative -p ./my_novel

# 12. Migrate Legacy Summaries to 3-Tier Hierarchy
nousetsu migrate-summaries -p ./my_novel

# 13. Explicit TUI Launch with Custom Paths
nousetsu tui --project-dir ./my_novel

# 14. Offline Self-Evolution for Procedural Graphs (arXiv:2609.09153v1)
nousetsu learn-graph -p ./my_novel -a all

# 15. Realignment of Chapter Numbering Collisions
nousetsu realign-chapters -p ./my_novel -F Villainess_06

# 16. Fast Chapter Queue & Project Scanner
nousetsu scan --all-projects
nousetsu scan -p ./my_novel -F Villainess_05

# 17. Import and Extract Chapters from EPUB or PDF
nousetsu import ./novel.epub -p ./my_novel -F Volume_01
nousetsu import ./novel.pdf -p ./my_novel --start 1 --end 25

# 18. Compile Translated Chapters into Publication-Ready PDF or EPUB3
nousetsu export -p ./my_novel -F Volume_01_th -f pdf --font "Sarabun" --font-size 16
nousetsu export -p ./my_novel -F Volume_01_th -f epub --title "My Translated Novel"
```

### Chapter Queue Scanner (`nousetsu scan`)

```bash
nousetsu scan [OPTIONS]
```

| Flag | Shorthand | Default | Description |
|:---|:---:|:---:|:---|
| `--project-dir` | `-p` | `None` | Folder or name of novel project (resolves in `NOVEL_PROJECTS_DIR` or current directory) |
| `--folder` / `--volume` | `-F` | `None` | Specific volume folder to scan within the project |
| `--all-projects` | `-A` | `False` | Scan across all novel projects in `NOVEL_PROJECTS_DIR` with completion overview |

### Full `nousetsu batch` Flags

| Flag | Shorthand | Default | Description |
|:---|:---:|:---:|:---|
| `--project-dir` | `-p` | Current directory | Root folder of the novel project |
| `--volume` / `--folder` | `-F` | None | Translation volume/folder within project (e.g. `-F Villainess_05`) |
| `--chapter` | `-c` | None | Filter and translate a specific chapter by number or name (e.g. `48`, `"ch 48"`, `"048"`, `"chapter 48"`) |
| `--input-dir` | `-i` | `raw_chapters` | Folder containing raw chapter text files |
| `--output-dir` | `-o` | `translated_chapters` | Folder where translated markdown files are written |
| `--source-lang` | | `auto` | Override source language (`Japanese`, `Chinese`, `Korean`, `English`, etc.) |
| `--target-lang` | | `English` | Override target language (`English`, `Thai`, `Spanish`, etc.) |
| `--genre` | `-g` | `general` | Novel genre (`xianxia`, `wuxia`, `isekai`, `litrpg`, `romance`, `general`) |
| `--model` | `-m` | `gemini-3.1-flash-lite` | Primary LLM model name (or set `NOVEL_MODEL` in `.env`) |
| `--fallback-model` | | `gemini-3.5-flash-lite` | Automatic fallback model used upon HTTP 429 quota exhaustion |
| `--extractor-model` | | `gemini-3.1-flash-lite` | Model for Stage 1: Entity Extractor |
| `--drafter-model` | | `gemini-3.5-flash-lite` | Model for Stage 2: Context-Aware Drafter |
| `--critic-model` | | `gemma-4-26b-a4b-it` | Model for Stage 3: Critique Agent |
| `--polisher-model` | | `gemini-3.5-flash-lite` | Model for Stage 4: Prose Polisher |
| `--chronicler-model` | | `gemma-4-26b-a4b-it` | Model for Stage 5: Lore Chronicler |
| `--limit` | `-l` | None (all) | Maximum number of chapters to process in this run |
| `--force` | `-f` | False | Force re-translation even if chapter is already marked `COMPLETED` |
| `--max-loops` | | `3` | Maximum review reflection loops between Critic and Polisher (1–5) |
| `--quality-threshold` | | `8.5` | Target quality score (fidelity & style) to exit review loop early |
| `--max-tpm` | | `32000` | Sliding-window Tokens Per Minute rate limit quota |
| `--max-rpm` | | `60` | Sliding-window Requests Per Minute rate limit quota |
| `--rag / --no-rag` | | True | Enable or disable Hybrid Search RAG (SQLite FTS5 + Gemini Embedding 2) |
| `--rerank / --no-rerank` | | True | Enable or disable LLM Cross-Encoder reranking of RAG candidates |
| `--interactions / --no-interactions` | | True | Enable or disable Gemini Interactions API (`/v1beta/interactions`) with fallback |
| `--chunking / --no-chunking` | | True | Enable or disable line-based semantic chunking for long chapters |
| `--chunk-threshold-lines` | | `800` | Minimum non-empty lines to trigger chunked translation |
| `--target-chunk-lines` | | `400` | Target line count per chunk |
| `--auto-update-bible` | | True | Automatically merge newly discovered characters and terms into Novel Bible |

> [!TIP]
> Pressing `Ctrl+C` (`SIGINT`) during headless CLI batch translation will gracefully pause the active chapter, flush `.novel/metadata.json`, and exit without data corruption.

### Novel Ingestion & Extraction (`nousetsu import`)

Ingest existing digital light novels and raw chapter compilations in `.epub` or `.pdf` format. NouSetsu automatically extracts chapters, volume metadata, and preserves embedded color illustrations:

```bash
nousetsu import FILE [OPTIONS]
```

| Flag | Shorthand | Default | Description |
|:---|:---:|:---:|:---|
| `file` | | *(Positional)* | Path to source `.epub` or `.pdf` file |
| `--project-dir` | `-p` | `None` | Novel project directory |
| `--folder` / `--volume` | `-F` | `None` | Destination volume subfolder (e.g. `Volume_01` or `raw_chapters`) |
| `--start` | | `None` | First chapter index to extract |
| `--end` | | `None` | Last chapter index to extract |
| `--overwrite` | | `False` | Overwrite existing chapter files in target folder |
| `--no-images` | | `False` | Skip extracting illustration images to `assets/` |

**Example Workflows**:
```bash
# Ingest entire EPUB into Volume 1
nousetsu import ./light_novel_vol1.epub -p ./projects/reincarnated -F Volume_01

# Ingest specific chapter range from PDF without images
nousetsu import ./webnovel_raw.pdf -p ./projects/reincarnated --start 1 --end 20 --no-images
```

---

### Publication eBook & PDF Compilation (`nousetsu export`)

Compile translated markdown chapters into publication-grade **EPUB3** or native in-memory **PDF** files with professional typography:

```bash
nousetsu export [OPTIONS]
```

| Flag | Shorthand | Default | Description |
|:---|:---:|:---:|:---|
| `--format` | `-f` | `epub` | Output format: `epub`, `pdf` (native binary), or `html` |
| `--project-dir` | `-p` | `.` | Root folder of the novel project |
| `--folder` / `--volume` | `-F` | `None` | Translated volume folder to compile (auto-resolves active translated folder) |
| `--output` | `-o` | `None` | Output destination file path (`.epub`, `.pdf`, or `.html`) |
| `--title` | | `None` | Book title override |
| `--author` | | `None` | Author name override |
| `--font` | | `Sarabun` | Font family (`Sarabun`, `Prompt`, `Kanit`, `Noto Serif Thai`, `Chakra Petch`) |
| `--font-size` | | `16` | Body text font size in points/pixels |
| `--line-height` | | `1.8` | Line height spacing ratio |
| `--no-appendix` | | `False` | Do not append Novel Bible characters/glossary appendix |
| `--no-wrap` | | `False` | Disable Thai zero-width space line breaking |

**Key Features**:
* **Native In-Memory PDF Generation**: Uses `pymupdf.DocumentWriter` + `pymupdf.Story` to build genuine binary PDF files with custom page breaks, margins, and centered running bottom page numbers (`- {page} -`).
* **Thai Typography & Word Wrapping**: Automatically inserts zero-width break spaces (`\u200b`) via `pythainlp` into paragraph runs to prevent abrupt syllable clipping across line breaks.
* **Auto-Resolution of Active Translated Folders**: Automatically discovers and defaults to volume translated directories (`<volume>_th` or `translated_chapters`) without manual path configuration.
* **Live Publication Studio**: You can also use the interactive graphical preview in the Web Studio with real-time typography sliders and reader view before downloading.

---

### Web Novel URL Scraper & Project Ingestion

NouSetsu integrates an automated web novel scraper powered by `Novel-Scraper` (`modules/novel_scraper`) for zero-touch ingestion from online fiction portals:

1. Launch Web Studio:
   ```bash
   nousetsu web
   ```
2. In your browser (`http://localhost:5173`), click **`+ New Project`** and select **`Import from Web URL`**.
3. Paste a novel landing page URL (e.g. `https://ncode.syosetu.com/n1234xx/` or Kakuyomu).
4. Click **Inspect (🔍)** to preview the Table of Contents, author name, and chapter count.
5. Select your target chapter range (e.g. `1` to `50`) and click **`⚡ Import Novel`**.
6. The system automatically scrapes chapters, sanitizes HTML, romanizes East Asian titles into clean project folder slugs, and populates `raw_chapters/` ready for immediate translation!

For full technical specifications, architecture details, and supported sites, refer to the [**Novel Scraper Guide**](./novel_scraper.md).

---

## 🥋 5. Agent Skills System

NouSetsu equips agents with **domain-specific translation skills** that automatically inject targeted directives into agent prompts based on the novel's source language and genre:

```bash
# View all registered skills
nousetsu skills

# Filter by agent and genre
nousetsu skills --agent drafter --genre wuxia
```

### Built-in Skills (23 Total)

| Agent | Skill Name | Genre / Language Scope | Description |
|:---|:---|:---:|:---|
| **Extractor** | `entity_disambiguation` | All genres / All languages | Distinguishes family names, given names, and honorific suffixes. |
| **Extractor** | `cultivation_realm_extractor` | Xianxia, Wuxia, LitRPG / CJK | Discovers martial/magic realms, meridians, and cultivation tiers. |
| **Extractor** | `relationship_mapper` | All genres / All languages | Maps master-disciple, senpai-kouhai, and clan hierarchies. |
| **Drafter** | `zero_anaphora_resolution` | Japanese, Chinese, Korean | Reconstructs omitted subjects and pronouns from context. |
| **Drafter** | `name_address_fidelity` | All genres / All languages | Enforces strict dialogue address registers; preserves nicknames without arbitrary full-name substitution. |
| **Drafter** | `character_voice_differentiation` | All genres / All languages | Enforces distinct dialogue registers for each character. |
| **Drafter** | `idiom_localization` | Chinese, Japanese, Korean | Localizes 4-character idioms (Chengyu/Yojijukugo) naturally. |
| **Drafter** | `litrpg_system_framing` | LitRPG, GameLit / All languages | Formats status screens, inventory logs, and system notifications. |
| **Critic** | `omission_detector` | All genres / All languages | Audits for skipped sentences or condensed descriptions. |
| **Critic** | `glossary_enforcer` | All genres / All languages | Enforces exact canonical terms from Novel Bible. |
| **Critic** | `hallucination_guard` | All genres / All languages | Flags fabricated plot events or unnatural additions. |
| **Critic** | `nickname_disparity_auditor` | All genres / All languages | Flags unprovoked name/nickname swaps and register mismatches. |
| **Critic** | `tone_consistency_auditor` | All genres / All languages | Audits narrative register against established tone. |
| **Critic** | `prose_cadence_auditor` | All genres / All languages | Audits sentence rhythm and flags stiff or repetitive translationese. |
| **Polisher** | `chapter_header_preservation` | All genres / All languages | Ensures chapter titles, numbers, and structural headings from the draft are strictly retained at the top of the polished output. |
| **Polisher** | `translationese_filter` | All genres / All languages | Purges clunky passive voice and repetitive translation tropes. |
| **Polisher** | `prose_cadence_enhancer` | All genres / All languages | Crafts dynamic sentence rhythm and sensory prose. |
| **Polisher** | `address_form_preservation` | All genres / All languages | Strictly forbids normalizing intimate pet names and emotional address forms. |
| **Polisher** | `show_dont_tell` | All genres / All languages | Converts flat emotional labels into physical actions. |
| **Polisher** | `dialogue_flow` | All genres / All languages | Ensures spoken dialogue sounds natural and fluid. |
| **Chronicler** | `lore_world_state_tracker` | All genres / All languages | Tracks realm breakthroughs, inventory acquisitions, sect territory changes, and power systems. |
| **Chronicler** | `character_status_tracker` | All genres / All languages | Records physical injuries, psychological trauma, secrets revealed, and relationship milestones. |
| **Chronicler** | `continuity_auditor` | All genres / All languages | Verifies timeline consistency and cross-checks chapter outcomes against previous summaries. |

### Catalog Markdown Skills (`src/nousetsu/skills/catalog/`)

| Agent | Skill Name | Genre / Language Scope | Description |
|:---|:---|:---:|:---|
| **Drafter** | `isekai_fantasy_tropes` | Isekai, Fantasy / All languages | Formats adventurer guild ranks, quest boards, and stat windows. |
| **Drafter** | `wuxia_martial_arts` | Wuxia, Xianxia / All languages | Formats qi flow, stances, and martial arts combat exchanges. |
| **Polisher** | `otome_court_etiquette` | Romance, Otome, Drama / All | Refines aristocratic court banter and villainess poise. |

### Adding Custom Markdown Skills
You can add custom skills simply by dropping a markdown file with YAML frontmatter into `src/nousetsu/skills/catalog/` or your project folder:

```markdown
---
name: grimdark_horror_atmosphere
agent: polisher
title: Grimdark Horror & Sensory Dread
languages: [all]
genres: [horror, grimdark, dark-fantasy]
priority: 110
---

### Grimdark Atmosphere Directives:
- Sharpen visceral sensory cues: metallic tang of blood, oppressive damp chill, guttering candles.
- Emphasize character exhaustion, paranoia, and psychological dread.
```

---

## 🧠 6. Procedural Graph Execution (Zero-Token Overhead)

NouSetsu integrates an innovative **Procedural Graph** engine based on Google DeepMind research (*Procedural Graphs: Self-Evolving Execution Structures for LLM Agents*, Lu et al., arXiv:2609.09153v1).

### 💡 The Core Idea: Knowledge Graph vs. Procedural Graph in Plain English

Most AI systems know **facts**, but get lost on **procedures** (what to do next):

| Graph Type | What Question It Answers | Example Triplet | Real-World Analogy |
|:---|:---|:---|:---|
| **Knowledge Graph (KG)** | *"What is this thing?"* (Facts) | `(Clara, IS_A, Noble)`<br>`(Excalibur, LOCATED_IN, Stone)` | An Encyclopedia |
| **Procedural Graph (PG)** | *"What should I do next?"* (Actions) | `(Scan Candidates, LEADS_TO, Filter Known)` | A Flight Checklist / GPS |

```mermaid
flowchart LR
    subgraph KG ["Knowledge Graph: Facts ('What is')"]
        E1["Clara"] -->|is_a| E2["Villainess"]
        E1 -->|serves| E3["Amber Family"]
    end

    subgraph PG ["Procedural Graph: Workflow ('What to do')"]
        P1["1. Scan Text"] -->|LEADS_TO| P2["2. Check Bible"]
        P2 -->|LEADS_TO| P3["3. Infer Gender"]
        P3 -->|LEADS_TO| P4["4. Prune Junk Terms"]
    end
```

### 🗝️ The 3 Magic Attributes on Every Edge

In a simple diagram, arrows just say "leads to". In a **Procedural Graph**, every transition edge carries three vital pieces of operational advice:

$$\Phi(e) = (\text{Condition}, \text{Guidance}, \text{Pitfalls})$$

1. **Condition**: *When* should this step trigger?  
   *(e.g., "When a candidate character name appears in the scene")*
2. **Guidance**: *How* should the model solve it?  
   *(e.g., "Inspect speech honorifics like -sama or -kun to determine gender and status before guessing")*
3. **Pitfalls (The Secret Weapon)**: *What mistakes* must the model NOT make?  
   *(e.g., "DO NOT extract common conversational verbs, everyday adjectives, or greetings as novel terms!")*

### ⚡ The Research Paper's Flaw vs. NouSetsu's Token-Frugal Architecture

In the original academic paper:
* At **every single step**, the agent asks a separate online "Guidance LLM": *"Look at the graph and tell me what to do."*
* **The Problem**: Token consumption exploded by **+55% to +430%** (consuming up to 367,000 tokens on large tasks)!

**NouSetsu's Lightweight Solution**:
1. **Deterministic Localization (0 Extra LLM Calls, 0ms Latency)**:  
   Fast Python code tracks pipeline state:
   * Extractor running? $\rightarrow$ Select `Scan_Candidates` edge.
   * Drafter translating Chunk 1? $\rightarrow$ Select `Scene_Init` edge.
   * Drafter translating Chunk 2+? $\rightarrow$ Select `Boundary_Continuity` edge.
2. **Compact Serialized Injection (< 80 Tokens)**:  
   Only the active edge's guidance and pitfalls are injected into the agent's prompt.
3. **Net Token Reduction (We Actually Save Tokens!)**:  
   By giving the Extractor a strict anti-bloat pitfall rule (*"Do not extract everyday conversational vocabulary"*), the model stops outputting dozens of useless JSON dictionary entries.
   * Prompt overhead: **+60 tokens**.
   * Output reduction: **-300 to -800 tokens**.
   * **Net Result: Translation uses FEWER tokens than without the graph!**

### 🎬 Concrete Examples in Action

#### Example A: In the Entity Extractor (`EntityExtractorAgent`)
* **Without PG**: The model reads a Japanese sentence, finds common descriptive phrasing, and extracts everyday words ("quickly", "good", "run") into the glossary. The output is bloated with 1,200 tokens of junk.
* **With PG**: The prompt injects:
  > **Step $\rightarrow$ Prune Trivial Terms**: Extract only domain-specific martial ranks, spells, and unique items.  
  > **Pitfalls to Avoid**: Strictly exclude ordinary conversational vocabulary, everyday verbs, and greetings.
* **Result**: The LLM outputs only valid novel lore (`Azure Thunder Blade`, `Clara`), saving 300–800 output tokens.

#### Example B: In the Context-Aware Drafter (`ContextAwareDrafterAgent`) across Chunks
* **Chunk 1**: Localizes at `Scene_Init`. Tells model: *"Anchor character POV, establish narrative past tense, and identify opening speakers."*
* **Chunk 2+**: Localizes at `Boundary_Continuity`. Tells model:
  > **Step $\rightarrow$ Boundary Continuity**: Read Preceding Scene Context to identify active speaker. Resume translating immediately.  
  > **Pitfalls to Avoid**: DO NOT repeat or re-translate preceding text. DO NOT restart the scene or re-introduce known characters.
* **Result**: Eliminates the classic chunk boundary bug where Chunk 2 re-translates lines from Chunk 1 or greets characters as if meeting them for the first time.

### 🔍 Terminal Inspection Tool (`nousetsu graph-info`)

You can inspect all active procedural graphs directly in your terminal using the built-in Rich tree viewer:

```bash
# View all active agent procedural graphs
nousetsu graph-info

# Filter by a specific agent with verbose edge attributes
nousetsu graph-info --agent drafter --verbose
```

Terminal output displays the execution flow, transitions, guidance notes, and pitfall guards in colorful Rich trees:

```text
📦 NouSetsu Procedural Graph Inspection
├── 🎭 Stage 1: Entity Extractor (EntityExtractorAgent)
│   ├── [Scan_Candidates] ──(text_received)──> [Filter_Known]
│   ├── [Filter_Known] ──(unregistered_found)──> [Deduce_Profiles]
│   └── [Deduce_Profiles] ──(entities_resolved)──> [Prune_Trivial_Terms]
│       └── ⚠️ Pitfall: Strictly exclude ordinary conversational vocabulary, everyday verbs, and greetings.
├── ✍️ Stage 2: Context-Aware Drafter (ContextAwareDrafterAgent)
│   ├── [Scene_Init] ──(chunk_1_or_single)──> [Zero_Anaphora_Resolution]
│   ├── [Boundary_Continuity] ──(chunk_gt_1)──> [Zero_Anaphora_Resolution]
│   │   └── ⚠️ Pitfall: DO NOT repeat or re-translate preceding text. DO NOT restart scene.
│   ├── [Zero_Anaphora_Resolution] ──(subjects_resolved)──> [Voice_Modulation]
│   └── [Voice_Modulation] ──(voices_locked)──> [Glossary_Lock]
├── 🔍 Stage 3: Critique Agent (CritiqueAgent)
│   ├── [Audit_Init] ──(draft_received)──> [Omission_Check]
│   ├── [Omission_Check] ──(omissions_verified)──> [Glossary_Audit]
│   ├── [Glossary_Audit] ──(terms_checked)──> [Register_Tone_Check]
│   └── [Register_Tone_Check] ──(register_verified)──> [Scoring_Gating]
├── 🎨 Stage 4: Polishing Agent (PolishingAgent)
│   ├── [Inspect_Critique] ──(notes_ingested)──> [Title_Header_Lock]
│   │   └── ⚠️ Pitfall: NEVER drop or translate away the chapter header or title line!
│   ├── [Title_Header_Lock] ──(header_anchored)──> [Translationese_Filter]
│   ├── [Translationese_Filter] ──(cliches_purged)──> [Cadence_Rhythm_Polish]
│   └── [Cadence_Rhythm_Polish] ──(flow_optimized)──> [Patch_Fidelity_Lock]
└── 📚 Stage 5: Chronicler Agent (ChroniclerAgent)
    ├── [Chapter_Deconstruction] ──(prose_analyzed)──> [State_Shift_Tracking]
    ├── [State_Shift_Tracking] ──(shifts_recorded)──> [Arc_Boundary_Detection]
    ├── [Arc_Boundary_Detection] ──(arc_analyzed)──> [Entity_Reconciliation]
    └── [Entity_Reconciliation] ──(terms_reconciled)──> [Bible_Memory_Commit]
```

### 🧬 Offline Self-Evolution (`nousetsu learn-graph`)

NouSetsu includes an offline self-evolution refiner ([`pg_refiner.py`](file:///D:/Code/novel_translation_Agent/src/nousetsu/graph/pg_refiner.py)) based on Algorithm 1 of the paper:
1. When the Critique Agent (`CritiqueAgent`) audits translation drafts, a `DiagnosticTrace` records any omissions, register shifts, or terminology discrepancies into `.novel/traces/`.
2. Running `nousetsu learn-graph` analyzes historical audit traces across completed chapters, clusters recurring flaws, and synthesizes localized graph edge mutations (e.g. appending new specific pitfalls or sharpening guidance).
3. Changes are committed only if structural validation passes and regression tests succeed.
4. **Inference Token Cost: 0 tokens during active batch translation** (runs offline or post-batch).

```bash
# Run offline self-evolution on all agent graphs
nousetsu learn-graph -p project/Villainess -a all

# Run offline evolution on a specific agent graph with dry-run preview
nousetsu learn-graph -p project/Villainess -a critic --dry-run
```

---

## 📖 7. Managing the Novel Bible & Lore

All persistent memory is stored in human-readable YAML at:
```text
.novel/bible/bible.yaml
```

### Structure of the Novel Bible

```yaml
title: Reincarnated as a Swordmaster
source_language: Japanese
target_language: English
genre: isekai

characters:
  - name: Allen
    original_name: アレン
    gender: male
    role: protagonist
    voice: humble, determined, polite with elders, fierce in combat
    relationships:
      Seraphina: companion

glossary:
  - source: 蒼雷剣
    target: Azure Thunder Blade
    category: item
    notes: Legendary katana forged from storm dragon scales

style_guide:
  reading_level: literary_fiction
  tense: past
  pov: third_person
  honorific_mode: retain   # 'retain' (-san/-sama), 'translate' (Mr./Lord), or 'omit'

whole_story_summary: "Macro premise: Allen departs his home after awakening dragon lineage to uncover ancient artifacts."

summaries:
  - chapter_num: 1
    title: The Departure
    synopsis: Allen leaves his hometown after awakening his dragon lineage.
```

### 3-Tier Hierarchical Narrative Memory (Macro > Meso > Micro)
To prevent narrative drift across long multi-volume series, NouSetsu organizes memory hierarchically:
1. **Macro Context (`whole_story_summary`)**: Global narrative synthesis capturing overarching conflicts, major world state changes, and character goals. Stored directly in `bible.yaml`.
2. **Meso Context (`ArcSummary`)**: Story arc boundaries autonomously detected by the Chronicler Agent (*ChroniclerAgent*). Tracks arc titles, core conflicts, and milestone progress. Saved in `.novel/summaries/arcs/arc_XXXX.json`. When completed, arcs are archived into `bible.yaml`.
3. **Micro Context (`ChapterSummary`)**: Immediate preceding chapter outcomes, cliffhangers, and character state changes partitioned by volume folder (`.novel/summaries/<volume>/chapter_XXXX.json`). Seamlessly backfills context across volume transitions (`Villainess_04` -> `Villainess_05`) with volume badges.

### Inspecting and Migrating Narrative Memory
* **`nousetsu narrative`**: Renders an interactive 3-tier Rich tree in your terminal displaying Whole Story progression, active and completed story arcs with milestones, and chapter summaries.
* **`nousetsu migrate-summaries`**: Seamlessly upgrades legacy flat summary novel projects to the 3-tier hierarchical system.

> [!TIP]
> You can edit the Novel Bible directly in the Textual TUI by pressing `E`. Changes take effect on the next translated chapter!

---

## 🛡️ 8. Enterprise Safety Guards

1. **Sliding-Window Rate Limiter (32K TPM / 60 RPM)**:
   - Tracks token and request quotas across a rolling 60-second window.
   - Automatically pauses before API calls to guarantee your quota is never exceeded.
   - On Google API 429 quota exhaustion, performs an intelligent 25s–65s window rollover wait.
2. **Automatic Fallback Model Guard (429 Failover)**:
   - When any agent stage encounters HTTP 429 or `RESOURCE_EXHAUSTED` errors, `FallbackChatModel` automatically fails over to the designated `fallback_model` (default: `gemini-3.5-flash-lite`).
   - Ensures continuous batch translation even during sudden API tier limits.
3. **Language Regression Guard**:
   - Polisher and Critic verify that outputs match `target_language` using offline Unicode script analysis (`detect_language`).
   - If an LLM attempts to translate back to `source_language`, the regression is immediately rejected and the valid target draft is preserved.
4. **Best-Candidate Regression Guard**:
   - During multi-pass reflection loops, the system tracks the highest-scoring version. If a later loop pass scores lower, the best version is automatically restored.
5. **Single-File Checkpoints (`.novel/metadata.json`)**:
   - All chapter checkpoints, error traces, and quality audits are stored in a single JSON file.
   - Enables fast directory scanning and instant resume.
6. **Line-Based Semantic Chunking (32K TPM Rate-Limit Guard)**:
   - Scans non-empty lines in source chapters. If line count exceeds `chunk_threshold_lines` (default: 800), automatically divides chapters into ~400-line chunks.
   - Snaps to scene break lines (`***`, `---`, `◆◆◆`) and paragraph boundaries while strictly preserving multi-line dialogue quotes (`「...」`, `"..."`).
   - Keeps individual chunk requests under ~3,500 total tokens (under 12% of the 32,000 TPM limit), completely preventing 60-second sliding-window freezes.
   - Passes sliding translation context (last 3 lines of preceding translation) to guarantee zero-anaphora pronoun continuity and character voice.
7. **Active Chapter Glossary Optimization**:
   - Dynamically filters the Novel Bible glossary to terms actually present in the chapter text before sending prompts to Critic and Polisher.
   - Prevents prompt bloat and eliminates false-positive compliance warnings.
8. **AI Safety Block Resilience & Recursive Bisection**:
   - Intense action scenes or romantic intimacy in webnovels can trigger commercial LLM safety filters (e.g. Google AI `prohibited_content` HTTP 400).
   - **Analytical Task Framing**: Formats excerpts with explicit literary task framing across all five pipeline agents, minimizing false-positive safety triggers.
   - **Recursive Binary Bisection (`bisect_text`)**: When a safety block occurs, the system bisects the chunk along paragraph, line, or sentence boundaries. Safe sub-chunks are translated by the primary LLM with full literary prose, while only the isolated minimal sensitive sub-block ($\le 8$ lines or depth 4) triggers a seamless **Google Translate fallback** (`deep-translator`) with subsequent literary polishing.
   - Extractor and Critic similarly bisect blocked chunks so safe text is extracted and audited with full fidelity.

---

## ⚡ 9. Gemini Interactions API & Granular Token Tracking

NouSetsu natively integrates Google's cutting-edge **Gemini Interactions API** (`/v1beta/interactions`) to coordinate stateful multi-turn agent conversations, stream model thoughts, and provide high-fidelity token accounting across all pipeline stages.

### Interactions API Architecture
* **Native SDK Integration**: Interacts directly through `google.genai.Client.interactions.create` with support for `model`, `input`, and structured thought tokens.
* **Resilient HTTP REST Fallback**: Automatically falls back to standard direct REST (`https://generativelanguage.googleapis.com/v1beta/interactions`) if the SDK method is unavailable or in transitional environments.
* **Toggle via Configuration**: Controlled via `--interactions / --no-interactions` in CLI or `use_interactions_api: true/false` in `ProjectConfig`.

### Granular Per-Task & Per-Step Token Metrics
NouSetsu tracks 5 precise token dimensions across every pipeline stage:
* `input_tokens`: Raw prompt and context tokens fed to the agent.
* `output_tokens`: Final generated tokens produced by the agent.
* `thought_tokens`: Internal reasoning / chain-of-thought tokens consumed by reasoning models (e.g. Gemini 2.5 Flash Thinking / Gemini 2.5 Pro).
* `cached_tokens`: Tokens retrieved from prompt cache contexts.
* `total_tokens`: Grand total of all token usage for that step.

### Monitored Pipeline Steps
1. `extracting`: Entity discovery pass.
2. `drafting`: Initial narrative translation pass.
3. `critiquing (loop #1, #2, ...)`: Fidelity and prose evaluation pass.
4. `polishing (loop #1, #2, ...)`: Literary rewriting pass.
5. `chronicling`: Narrative summary extraction and metadata consolidation.

### Viewing Token & Duration Metrics
* **TUI Checkpoint Inspector**: Highlight any chapter in the TUI to view live aggregated metrics including duration:
  ```text
  Tokens: 1,284 in 3.9s (In: 820 Out: 364)
  ```
* **Rich CLI Batch Table**: At the conclusion of `nousetsu batch`, a comprehensive summary table displays token and execution duration breakdowns by task and step:
  ```text
  📊 Token & Duration Breakdown by Pipeline Step
  Chapter / Step       Extraction   Drafting      Critique      Polishing     Chronicle     Thought   Total Tokens   Time (s)
  ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  Ch.1                 200 (0.5s)   340 (1.2s)    324 (0.9s)    310 (1.1s)    110 (0.4s)    100       1,284          4.1
  ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  GRAND TOTAL          -            -             -             -             -             100       1,284          4.1
  ```
* **Persistent Metadata (`.novel/metadata.json`)**: Every chapter's `stats` object stores the complete cumulative metrics alongside the `step_usage` array (recording `duration_seconds` for every pipeline pass) for automated billing, latency monitoring, or profiling analytics.

---

## ❓ 10. Troubleshooting & FAQ

### Q: What should I do if I get a `429 Resource Exhausted` error?
**A**: NouSetsu's sliding-window rate limiter automatically catches 429 errors, pauses execution until the current 60-second window clears, and retries with exponential backoff. If you are on a restricted tier, lower your TPM via CLI:
```bash
nousetsu batch --max-tpm 10000 --max-rpm 30
```

### Q: How do I resume a batch translation that was stopped?
**A**: Simply run `nousetsu batch` again (or open `nousetsu` and press `B`). NouSetsu automatically skips completed chapters and resumes paused or failed chapters from their last completed stage!

### Q: Can I translate from English to Thai, Spanish, or Japanese?
**A**: Yes! NouSetsu supports arbitrary language pairs. Configure `--source-lang` and `--target-lang` during initialization:
```bash
nousetsu init --title "Villainess" --source-lang "English" --target-lang "Thai"
```
The Polisher and Critic dynamically adapt their prompts and enforce target language fidelity.

### Q: How do I force re-translation of a chapter?
**A**: Use the `--force` flag in CLI:
```bash
nousetsu batch --force --limit 1
```
Or in the TUI, select the chapter and press `T`.

---

*NouSetsu is maintained by Checkmartyr. Contributions and issues welcome on [GitHub](https://github.com/Checkmartyr/NouSetsu).*