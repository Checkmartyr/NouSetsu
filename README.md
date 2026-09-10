# 📖 Novel Translation Agent

> **Agentic Document-Level Cross-Chapter Novel Translation System**  
> Powered by **LangGraph**, **LangChain**, **Textual**, and **Rich**.

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![Package Manager: uv](https://img.shields.io/badge/managed%20by-uv-purple.svg)](https://github.com/astral-sh/uv)
[![Framework: LangGraph](https://img.shields.io/badge/agent-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![UI: Textual](https://img.shields.io/badge/ui-Textual%20%26%20Rich-green.svg)](https://textual.textualize.io/)

---

## 🌟 Key Highlights

* **Cross-Chapter Narrative Memory**: Maintains a persistent **Novel Bible** tracking character sheets, voice registers, canonical glossary terms, and rolling summaries of preceding chapters to eliminate character voice drift.
* **Zero-Anaphora Resolution**: Context-augmented drafting specifically designed for East Asian languages (Japanese, Chinese, Korean) where subjects, agents, and pronouns are omitted.
* **Multi-Stage Agentic Refinement**:
  1. `EntityExtractorAgent`: Discovers unfamiliar names, terms, and ranks before drafting.
  2. `ContextAwareDrafterAgent`: Translates with active character registers and rolling plot context.
  3. `CritiqueAgent`: Inspects fidelity, dropped sentences, and glossary compliance.
  4. `PolishingAgent`: Eliminates machine-translation tropes to produce publication-grade novel prose.
  5. `ChroniclerAgent`: Updates world memory and generates chapter synopses.
* **Stage-Level Metadata Checkpoints (`.meta.json`)**: Every chapter produces a paired metadata file containing quality audit scores, SHA-256 source hash, and intermediate stage artifacts for granular pipeline resumption without re-spending tokens.
* **Folder-to-Folder Batch Automation**: Automatically discovers and naturally sorts chapters (`001.txt`, `ch2.txt`, `ch10.txt`), sequentially translates them while passing state, and skips unaltered completed chapters.
* **Interactive Terminal UI (TUI)**: Full dual-pane terminal reader built with `textual` and `rich`, featuring synchronized source/target inspection, live checkpoint badges, and an in-terminal Novel Bible editor.
* **In-TUI Project Management & Custom Folders**: Seamlessly initialize new novel projects, switch active projects with one click, and configure custom raw and translated output directory names per project.
* **Real-Time Live Translation Visualizer**: Displays granular 5-stage progress badges (`1/5 EXTRACTION`, `2/5 DRAFTING`, `3/5 CRITIQUE`, `4/5 POLISHING`, `5/5 CHRONICLING`), an animated progress bar, and live status messaging during single-chapter or batch execution.

---

## 🏛️ Architecture & Workflow

```mermaid
flowchart TD
    subgraph Input & Discovery
        Raw[raw_chapters/*.txt] --> Scanner[ChapterScanner (natsort + SHA256)]
        Bible[(.novel/bible/bible.yaml)] --> MemorySync[Cross-Chapter Memory Sync]
    end

    subgraph Agentic Translation Graph (LangGraph)
        Scanner --> Extractor[Stage 1: EntityExtractorAgent]
        Extractor --> Drafter[Stage 2: ContextAwareDrafterAgent]
        Drafter --> Critic[Stage 3: CritiqueAgent]
        Critic --> Polisher[Stage 4: PolishingAgent]
        Polisher --> Chronicler[Stage 5: ChroniclerAgent]
    end

    subgraph Output & Verification
        Chronicler --> OutText[translated_chapters/*.md]
        Chronicler --> Meta[.meta.json with Checkpoint & Quality Audit]
        Chronicler --> BibleUpdate[Update Novel Bible Lore & Summaries]
    end

    subgraph UI & Controls
        Meta --> TUI[Textual TUI / Rich CLI]
        TUI --> User[Master Review / Interactive Batch]
    end
```

---

## 🚀 Quick Start

### 1. Prerequisites
* Python `>= 3.13`
* [uv](https://github.com/astral-sh/uv) fast package manager installed:
  ```powershell
  # On Windows PowerShell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

### 2. Installation & Sync
Clone the repository and install all dependencies:
```bash
uv sync
```

### 3. Configure API Key
Set your Gemini API key (or OpenAI / Anthropic key):
```powershell
# Windows PowerShell
$env:GEMINI_API_KEY = "your-google-gemini-api-key"

# Linux / macOS
export GEMINI_API_KEY="your-google-gemini-api-key"
```
*(Note: If no API key is set, the system automatically runs with a deterministic mock model for testing and offline development).*

---

## 💻 Usage & CLI Reference

### 1. Initialize a Project
Create project directories and generate the default **Novel Bible**:
```bash
uv run python main.py init --title "Reincarnated as a Swordmaster" --source-lang "Japanese" --target-lang "English"
```

### 2. Run Automated Folder-to-Folder Batch
Place raw chapter files (`.txt` or `.md`) inside `raw_chapters/` and run:
```bash
uv run python main.py batch --input-dir raw_chapters --output-dir translated_chapters
```

**CLI Flags**:
* `--input-dir`, `-i`: Folder containing raw source chapters (default: `raw_chapters`).
* `--output-dir`, `-o`: Folder for translated output and metadata (default: `translated_chapters`).
* `--source-lang`: Source language (e.g., `Japanese`, `Chinese`, `Korean`).
* `--target-lang`: Target language (e.g., `English`, `Spanish`, `French`).
* `--model`, `-m`: LLM model name (default: `gemini-2.5-pro`).
* `--limit`, `-l`: Maximum number of chapters to process.
* `--force`, `-f`: Force re-translation even if chapter is already marked completed.

### 3. Launch the Textual TUI Dashboard
Launch the interactive dual-pane reader and terminal workspace:
```bash
uv run python main.py tui --input-dir raw_chapters --output-dir translated_chapters
```
*(Or simply run `uv run python main.py` when project files exist).*

#### TUI Keyboard Shortcuts
| Key | Action | Description |
|:---:|:---|:---|
| `T` | **Translate Selected** | Run agentic translation on currently selected chapter |
| `B` | **Run All Batch** | Trigger background batch translation across all chapters |
| `P` | **Projects** | Open Project Selector modal to switch active project |
| `N` | **New Project** | Open Initialize Project modal with title, languages & folder names |
| `E` | **Novel Bible** | Open in-terminal editor to inspect/add characters & terms |
| `S` | **Settings** | Configure LLM model, languages, style guide, and paths |
| `R` | **Refresh** | Re-scan chapters and reload status badges |
| `Q` | **Quit** | Exit the TUI application |

---

## 📑 Translation Metadata & Checkpoints (`.meta.json`)

Each chapter produces an accompanying `<chapter>.meta.json` file providing complete auditability and stage resumption:

```json
{
  "chapter_id": "chapter_0001",
  "chapter_num": 1,
  "source_file": "raw_chapters/001 - Awakening.txt",
  "source_sha256": "eedc16a0eb6762e6e6dd859709f82586f15905907363ed5506fcfdc068a85d30",
  "output_file": "translated_chapters/001 - Awakening.md",
  "timestamp": "2026-09-10T16:37:09Z",
  "model": "gemini-2.5-pro",
  "checkpoint": {
    "status": "completed",
    "last_completed_stage": "chronicling",
    "retry_count": 0,
    "last_error": null,
    "stage_artifacts": {
      "extracted_terms": [],
      "extracted_characters": [],
      "draft_text": "...",
      "critique_notes": "Good flow, prose is faithful.",
      "polished_text": "..."
    }
  },
  "stats": {
    "source_char_count": 166,
    "target_word_count": 22,
    "prompt_tokens": 215,
    "completion_tokens": 30,
    "duration_seconds": 0.01
  },
  "quality_audit": {
    "fidelity_score": 9.5,
    "style_score": 9.2,
    "glossary_compliance_pct": 100.0,
    "warnings": [],
    "passed": true
  },
  "review_status": "draft"
}
```

---

## 🧪 Verification & Walkthrough Summary

The system has been verified through unit, integration, and end-to-end tests:

### 1. Test Suite Execution
```bash
uv run pytest
```
Output:
```
============================= test session starts =============================
tests/test_checkpoint.py .                                               [ 12%]
tests/test_models.py ...                                                 [ 50%]
tests/test_runner.py .                                                   [ 62%]
tests/test_scanner.py ..                                                 [ 87%]
tests/test_tui.py .                                                      [100%]
============================== 8 passed in 2.18s ==============================
```

### 2. End-to-End Batch Validation
Sample raw chapters (`001 - Awakening.txt`, `002 - Magic Beast.txt`) processed through `main.py batch`:
* Translation Markdown created (`.md`) alongside structured audit files (`.meta.json`).
* Memory committed to `.novel/bible/bible.yaml` with updated narrative summaries.
* Subsequent runs demonstrated instant skip-logic when source files were unchanged:
  ```
  Skipped (Done): Ch.2 (002 - Magic Beast.txt) ------------------- 100% 0:00:00
  ```
* Textual TUI headless pilot tests confirmed widget mounting, reactive status badges, and dual-pane synchronization.

---

## 📂 Project Structure

```
novel_translation_Agent/
├── .novel/                         # Project metadata and persistent memory
│   ├── config.yaml                 # Project configuration (languages, raw/out folders)
│   ├── bible/
│   │   └── bible.yaml              # Characters, glossary, and style guide
│   └── summaries/
│       ├── chapter_0001.json       # Per-chapter rolling plot summaries
│       └── chapter_0002.json
├── raw_chapters/                   # Input folder for source chapters
│   ├── 001 - Awakening.txt
│   └── 002 - Magic Beast.txt
├── translated_chapters/            # Output folder with text and metadata
│   ├── 001 - Awakening.md
│   ├── 001 - Awakening.meta.json
│   ├── 002 - Magic Beast.md
│   └── 002 - Magic Beast.meta.json
├── src/
│   ├── agents/                     # LLM agent stages (extractor, drafter, critic, etc.)
│   ├── batch/                      # Folder scanner, natural sorter, batch runner
│   ├── graph/                      # LangGraph state graph workflow
│   ├── models/                     # Pydantic schemas (bible, metadata, state, config)
│   ├── prompts/                    # Translation and critique prompt templates
│   ├── storage/                    # File repository, registry, and persistence handlers
│   ├── tui/                        # Textual TUI app and inspection widgets
│   │   ├── widgets/                # Reader, Inspector, ProgressPanel, Modals
│   │   └── app.py                  # Main Textual App
│   └── cli/                        # CLI command dispatch
├── tests/                          # Automated pytest suite
├── main.py                         # Root entry point
├── pyproject.toml                  # Dependencies and project configuration
└── README.md                       # Documentation
```

---

## 📄 License
MIT License. Built for fiction lovers and novel translation communities.
