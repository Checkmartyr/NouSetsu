# 📖 NouSetsu User Guide

> **The Complete End-User Manual for Agentic Document-Level Novel Translation**  
> Powered by LangGraph, Textual, and Rich.

---

## 📑 Table of Contents

1. [Introduction](#-1-introduction)
2. [Installation & Setup](#-2-installation--setup)
3. [60-Second Quickstart (The Textual TUI Dashboard)](#-3-60-second-quickstart-the-textual-tui-dashboard)
4. [Headless CLI & Batch Automation](#-4-headless-cli--batch-automation)
5. [Agent Skills System](#-5-agent-skills-system)
6. [Managing the Novel Bible & Lore](#-6-managing-the-novel-bible--lore)
7. [Enterprise Safety Guards](#-7-enterprise-safety-guards)
8. [Gemini Interactions API & Granular Token Tracking](#-8-gemini-interactions-api--granular-token-tracking)
9. [Troubleshooting & FAQ](#-9-troubleshooting--faq)

---

## 🌟 1. Introduction

Traditional machine translation tools (e.g. Google Translate, DeepL) process texts sentence-by-sentence or paragraph-by-paragraph. While serviceable for short technical documents, this approach fails disastrously for literary novels:
* **Pronoun Disappearance (*Zero-Anaphora*)**: In East Asian languages (Japanese, Chinese, Korean), subjects and pronouns are frequently omitted in dialogue and narration. Generic MT engines guess blindly or invent random pronouns ("he/she/it"), destroying immersion.
* **Character Voice Drift**: A haughty tsundere villainess sounds identical to an ancient martial arts grandmaster.
* **Term Inconsistency**: A martial arts technique or magical artifact changes spelling every three paragraphs.
* **Memory Loss**: MT engines have zero awareness of events that took place in preceding chapters.

**NouSetsu** solves this with a collaborative 5-stage agent pipeline coordinated by **LangGraph**:
1. **Schriftdetektiv** (*EntityExtractorAgent*): Discovers new character names, factions, and terms before translation.
2. **Wortschmied** (*ContextAwareDrafterAgent*): Resolves omitted pronouns (*Zero-Anaphora*) and character voices using the persistent **Novel Bible**.
3. **Zensor** (*CritiqueAgent*): Audits the draft against the full raw source text for fidelity (0-10) and prose style (0-10).
4. **Feinschliff** (*PolishingAgent*): Refines draft prose into literary, publication-grade target language fiction using critique notes and source text reference.
5. **Chronist** (*ChroniclerAgent*): Summarizes chapter turning points, updates rolling lore memory, and compiles checkpoint metadata into `.novel/metadata.json`.

---

## 🛠️ 2. Installation & Setup

### Prerequisites
* **Python 3.13+** installed on your system.
* Optional but recommended: [uv](https://github.com/astral-sh/uv) (ultra-fast Python package installer).

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

### Configuring API Keys
NouSetsu supports Google Gemini (default), OpenAI, Anthropic, or an offline mock model:

```bash
# Windows PowerShell
$env:GEMINI_API_KEY = "AIzaSy..."

# Linux / macOS Bash
export GEMINI_API_KEY="AIzaSy..."
```

> [!NOTE]
> If no API key is provided, NouSetsu automatically operates with a deterministic offline mock model (`mock-novel-llm`), allowing you to test UI navigation, batch scanning, and checkpoint resumption without consuming API tokens!

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
┌─ Novel Translation Agent ───────────────────────────────────────────── [12:00:00] ─┐
│ 📚 Chapters                       │  Progress: [====================] 100%         │
│  [DONE] Ch.001 - Chapter 1.txt    │  Stage: CHRONICLING                            │
│  [WAIT] Ch.002 - Chapter 2.txt    │                                                │
│  [WAIT] Ch.003 - Chapter 3.txt    ├───────────────────────┬────────────────────────┤
│                                   │ Original Source       │ Polished Translation   │
│ [▶ Translate Selected (T)]        │                       │                        │
│ [⚡ Run All Batch (B)]            │ 第一章：旅立ちの合図   │ Chapter 1: The Signal  │
│ [⏹ Stop Translation (X)]          │ 少年は歩き出した。     │ The boy stepped out.   │
│ [📖 Novel Bible (E)]               │                       │                        │
│ [📁 Projects (P)]                 ├───────────────────────┴────────────────────────┤
│ [✨ New Project (N)]               │ 🔍 Checkpoint Inspector: Fidelity: 9.5 | 9.2   │
│ [⚙ Settings (S)]                  │ Warnings: None | Status: COMPLETED             │
└───────────────────────────────────┴────────────────────────────────────────────────┘
```

### TUI Keyboard Shortcuts

| Key | Action | Description |
|:---:|:---|:---|
| `T` | **Translate Selected** | Triggers the 5-stage agentic translation graph on the highlighted chapter. |
| `B` | **Run All Batch** | Concurrently batches through all untranslated or resumed chapters in order. |
| `X` | **Stop Translation** | Safely pauses the active translation, saves a `PAUSED` checkpoint, and halts. |
| `P` | **Projects** | Opens the Project Selector modal to switch between novel projects. |
| `N` | **New Project** | Opens the Project Creator modal to configure novel title, languages, and genre. |
| `E` | **Novel Bible** | Opens the in-terminal editor to inspect/add characters, relationships, and glossary terms. |
| `S` | **Settings** | Opens the Settings modal to tune TPM/RPM rate limits and review loop caps. |
| `Q` | **Quit** | Exits the application cleanly. |

### Step-by-Step Workflow in TUI

1. **Create a Project**: Press `N`. Enter your novel's title (e.g. *Villainess Reversal*), source language (e.g. *Japanese*, *Chinese*, *Korean*, or *auto*), target language (e.g. *English*, *Thai*), and genre (*isekai*, *wuxia*, *romance*, *general*).
2. **Add Raw Chapters**: Drop your raw text files (`.txt` or `.md`) into the project's `raw_chapters/` directory.
3. **Translate Single Chapter**: Highlight a chapter in the left sidebar and press `T`. Watch the live progress panel transition across Extraction, Drafting, Critique, Polishing, and Chronicling!
4. **Translate Entire Novel**: Press `B` to translate all chapters sequentially.
5. **Interrupt Safely**: If you need to stop, press `X` or click **Stop Translation**. The current chapter is immediately saved with status `[PAUSED:STAGE]`. When you restart or press `T`, it resumes exactly where it stopped without repeating completed stages!

---

## ⚡ 4. Headless CLI & Batch Automation

For headless Linux servers, Docker containers, or automated scripts, NouSetsu provides a full suite of CLI subcommands.

### CLI Command Summary

```bash
# 1. Automatic TUI Dashboard (Default)
nousetsu

# 2. Project Initialization
nousetsu init --title "My Novel" --source-lang "Japanese" --target-lang "English" --genre "isekai"

# 3. Headless Batch Translation
nousetsu batch --input-dir raw_chapters --output-dir translated_chapters --limit 10

# 4. Agent Domain Skills Catalog
nousetsu skills --agent drafter --genre isekai

# 5. Explicit TUI Launch with Custom Paths
nousetsu tui --project-dir ./my_novel
```

### Full `nousetsu batch` Flags

| Flag | Shorthand | Default | Description |
|:---|:---:|:---:|:---|
| `--project-dir` | `-p` | Current directory | Root folder of the novel project |
| `--input-dir` | `-i` | `raw_chapters` | Folder containing raw chapter text files |
| `--output-dir` | `-o` | `translated_chapters` | Folder where translated markdown files are written |
| `--source-lang` | | `auto` | Override source language (`Japanese`, `Chinese`, `Korean`, etc.) |
| `--target-lang` | | `English` | Override target language (`English`, `Thai`, `Spanish`, etc.) |
| `--genre` | `-g` | `general` | Novel genre (`xianxia`, `wuxia`, `isekai`, `litrpg`, `romance`, `general`) |
| `--model` | `-m` | `gemini-2.5-pro` | LLM model name (or set `DEFAULT_MODEL` in `.env`) |
| `--limit` | `-l` | None (all) | Maximum number of chapters to process in this run |
| `--force` | `-f` | False | Force re-translation even if chapter is already marked `COMPLETED` |
| `--max-loops` | | `3` | Maximum review reflection loops between Critic and Polisher (1–5) |
| `--quality-threshold` | | `8.5` | Target quality score (fidelity & style) to exit review loop early |
| `--max-tpm` | | `16000` | Sliding-window Tokens Per Minute rate limit quota |
| `--max-rpm` | | `60` | Sliding-window Requests Per Minute rate limit quota |
| `--interactions / --no-interactions` | | True | Enable or disable Gemini Interactions API (`/v1beta/interactions`) with fallback |
| `--auto-update-bible` | | True | Automatically merge newly discovered characters and terms into Novel Bible |

> [!TIP]
> Pressing `Ctrl+C` (`SIGINT`) during headless CLI batch translation will gracefully pause the active chapter, flush `.novel/metadata.json`, and exit without data corruption.

---

## 🥋 5. Agent Skills System

NouSetsu equips agents with **domain-specific translation skills** that automatically inject targeted directives into agent prompts based on the novel's source language and genre:

```bash
# View all registered skills
nousetsu skills

# Filter by agent and genre
nousetsu skills --agent drafter --genre wuxia
```

### Built-in Skills (17 Total)

| Agent | Skill Name | Genre / Language Scope | Description |
|:---|:---|:---:|:---|
| **Extractor** | `entity_disambiguation` | All genres / All languages | Distinguishes family names, given names, and honorific suffixes. |
| **Extractor** | `cultivation_hierarchies` | Xianxia, Wuxia, LitRPG / CJK | Discovers martial/magic realms and meridians. |
| **Extractor** | `relationship_mapping` | All genres / All languages | Maps master-disciple, senpai-kouhai, and clan hierarchies. |
| **Drafter** | `zero_anaphora_resolution` | Japanese, Chinese, Korean | Reconstructs omitted subjects and pronouns from context. |
| **Drafter** | `character_voice_differentiation` | All genres / All languages | Enforces distinct dialogue registers for each character. |
| **Drafter** | `idiom_localization` | Chinese, Japanese, Korean | Localizes 4-character idioms (Chengyu/Yojijukugo) naturally. |
| **Drafter** | `isekai_fantasy_tropes` | Isekai, Fantasy / All languages | Formats adventurer guild ranks, quest boards, and stat windows. |
| **Drafter** | `wuxia_martial_arts` | Wuxia, Xianxia / All languages | Formats qi flow, stances, and martial arts combat exchanges. |
| **Drafter** | `litrpg_system_interface` | LitRPG, GameLit / All languages | Formats status screens, inventory logs, and system notifications. |
| **Critic** | `omission_detector` | All genres / All languages | Audits for skipped sentences or condensed descriptions. |
| **Critic** | `glossary_auditor` | All genres / All languages | Enforces exact canonical terms from Novel Bible. |
| **Critic** | `hallucination_guard` | All genres / All languages | Flags fabricated plot events or unnatural additions. |
| **Critic** | `tone_consistency_auditor` | All genres / All languages | Audits narrative register against established tone. |
| **Polisher** | `translationese_filter` | All genres / All languages | Purges clunky passive voice and repetitive translation tropes. |
| **Polisher** | `prose_cadence_enhancer` | All genres / All languages | Crafts dynamic sentence rhythm and sensory prose. |
| **Polisher** | `show_dont_tell` | All genres / All languages | Converts flat emotional labels into physical actions. |
| **Polisher** | `dialogue_flow` | All genres / All languages | Ensures spoken dialogue sounds natural and fluid. |
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

## 📖 6. Managing the Novel Bible & Lore

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

summaries:
  - chapter_num: 1
    title: The Departure
    synopsis: Allen leaves his hometown after awakening his dragon lineage.
```

> [!TIP]
> You can edit the Novel Bible directly in the Textual TUI by pressing `E`. Changes take effect on the next translated chapter!

---

## 🛡️ 7. Enterprise Safety Guards

1. **Sliding-Window Rate Limiter (16K TPM / 60 RPM)**:
   - Tracks token and request quotas across a rolling 60-second window.
   - Automatically pauses before API calls to guarantee your quota is never exceeded.
   - On Google API 429 quota exhaustion, performs an intelligent 25s–65s window rollover wait.
2. **Language Regression Guard**:
   - Polisher and Critic verify that outputs match `target_language` using offline Unicode script analysis (`detect_language`).
   - If an LLM attempts to translate back to `source_language`, the regression is immediately rejected and the valid target draft is preserved.
3. **Best-Candidate Regression Guard**:
   - During multi-pass reflection loops, the system tracks the highest-scoring version. If a later loop pass scores lower, the best version is automatically restored.
4. **Single-File Checkpoints (`.novel/metadata.json`)**:
   - All chapter checkpoints, error traces, and quality audits are stored in a single JSON file.
   - Enables fast directory scanning and instant resume.

---

## ⚡ 8. Gemini Interactions API & Granular Token Tracking

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

### Viewing Token Metrics
* **TUI Checkpoint Inspector**: Highlight any chapter in the TUI to view live aggregated metrics:
  ```text
  Tokens: 1,284 (In: 820 | Out: 364 | Thought: 100)
  ```
* **Rich CLI Batch Table**: At the conclusion of `nousetsu batch`, a comprehensive summary table displays token breakdowns by task and step:
  ```text
  📊 Token Usage by Task & Pipeline Step
  Chapter / Step       Input    Output   Thought  Cached   Total
  ─────────────────────────────────────────────────────────────
  Ch.1                 820      364      100      0        1,284
    ├── 1. extracting  150      50       0        0          200
    ├── 2. drafting    220      120      0        0          340
    ├── 3. critiquing  200      74       50       0          324
    ├── 4. polishing   180      80       50       0          310
    └── 5. chronicling  70      40       0        0          110
  ─────────────────────────────────────────────────────────────
  Grand Total          820      364      100      0        1,284
  ```
* **Persistent Metadata (`.novel/metadata.json`)**: Every chapter's `stats` object stores the complete cumulative metrics alongside the `step_usage` array for automated billing or usage analytics.

---

## ❓ 9. Troubleshooting & FAQ

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
