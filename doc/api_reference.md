# 🛠️ Code & Developer API Reference

This document provides a technical API reference for core classes, functions, and Pydantic models in **NouSetsu**.

---

## 🤖 Agents (`src/agents/`)

### `EntityExtractorAgent` (`src/agents/extractor.py`)
Extracts named entities, characters, and glossary candidates from source text.

```python
class EntityExtractorAgent:
    def __init__(self, model_name: str = "gemini-2.5-pro")
    
    def extract(
        self,
        source_text: str,
        bible: NovelBible
    ) -> Tuple[List[CharacterProfile], List[GlossaryItem], List[GlossaryItem]]:
        """
        Extracts new characters and glossary terms.
        Returns: (new_characters, new_terms, active_terms_in_chapter)
        """
```

---

### `ContextAwareDrafterAgent` (`src/agents/drafter.py`)
Produces initial novelistic translation drafts with zero-anaphora resolution and character voices.

```python
class ContextAwareDrafterAgent:
    def __init__(self, model_name: str = "gemini-2.5-pro")
    
    def draft(
        self,
        source_text: str,
        bible: NovelBible,
        active_characters: List[CharacterProfile],
        active_glossary: List[GlossaryItem],
        rolling_summaries: List[ChapterSummary]
    ) -> str:
        """
        Translates raw text with voice registers and rolling summaries.
        Returns: Raw draft string.
        """
```

---

### `CritiqueAgent` (`src/agents/critic.py`)
Performs independent fidelity, style, and glossary compliance audits.

```python
class CritiqueAgent:
    def __init__(self, model_name: str = "gemini-2.5-pro")
    
    def evaluate(
        self,
        source_text: str,
        draft_text: str,
        bible: NovelBible,
        active_characters: List[CharacterProfile],
        active_glossary: List[GlossaryItem]
    ) -> Tuple[QualityAudit, str]:
        """
        Audits draft against source.
        Returns: (QualityAudit object, critique_notes string)
        """
```

---

### `PolishingAgent` (`src/agents/polisher.py`)
Refines prose cadence and eliminates translationese.

```python
class PolishingAgent:
    def __init__(self, model_name: str = "gemini-2.5-pro")
    
    def polish(
        self,
        draft_text: str,
        critique_notes: str,
        active_glossary: List[GlossaryItem],
        bible: NovelBible
    ) -> str:
        """
        Polishes prose to publication standard.
        Returns: Polished Markdown text.
        """
```

---

### `ChroniclerAgent` (`src/agents/chronicler.py`)
Updates narrative lore, generates chapter synopses, and compiles metadata.

```python
class ChroniclerAgent:
    def __init__(self, model_name: str = "gemini-2.5-pro")
    
    def chronicle(
        self,
        chapter_num: int,
        chapter_title: str,
        translated_text: str
    ) -> ChapterSummary:
        """Generates episodic synopsis and records state changes."""

    def assemble_metadata(...) -> ChapterMetadata:
        """Assembles final ChapterMetadata record with stats and audit scores."""
```

---

### `LLM Utilities` (`src/agents/llm.py`)

```python
def get_llm(model_name: str, temperature: float = 0.3) -> BaseChatModel:
    """Factory returning Google Gemini model, or MockNovelLLM if no API key is present."""

def extract_text_from_message(content: Any) -> str:
    """Extracts plain text from LLM response, discarding reasoning blocks."""

def is_transient_error(err: Exception) -> bool:
    """Returns True if exception is 500, 503, 429 rate limit, or socket timeout."""

def invoke_with_retry(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = 4,
    initial_delay: float = 2.0,
    backoff_factor: float = 2.0,
    notify_callback: Optional[Callable[[str], None]] = None,
    **kwargs: Any
) -> Any:
    """Executes a function with exponential backoff and jitter on transient errors."""
```

---

## 🔄 Graph & Workflow (`src/graph/`)

### `NovelTranslationWorkflow` (`src/graph/workflow.py`)
Compiles and coordinates the multi-agent LangGraph execution.

```python
class NovelTranslationWorkflow:
    def __init__(self, model_name: str = "gemini-2.5-pro")
    
    def run(
        self,
        initial_state: TranslationState,
        stage_callback: Optional[Callable[[PipelineStage, str, float], None]] = None
    ) -> TranslationState:
        """Runs the LangGraph workflow to completion with stage callbacks."""
```

---

## 💾 Storage & Repositories (`src/storage/`)

### `NovelRepository` (`src/storage/repository.py`)
Manages on-disk state, Bible YAML, and single project metadata JSON.

```python
class NovelRepository:
    def __init__(self, root_dir: Path | str = Path("."))
    
    # Novel Bible
    def load_bible(self) -> NovelBible: ...
    def save_bible(self, bible: NovelBible) -> None: ...
    def update_bible_memory(
        self,
        new_characters: List[CharacterProfile],
        new_terms: List[GlossaryItem],
        summary: Optional[ChapterSummary]
    ) -> NovelBible: ...
    def set_languages(self, source_lang: Optional[str], target_lang: Optional[str]) -> NovelBible: ...
    
    # Project Metadata (.novel/metadata.json)
    def project_metadata_file_path(self) -> Path: ...
    def load_project_metadata_doc(self) -> ProjectMetadataDocument: ...
    def save_project_metadata_doc(self, doc: ProjectMetadataDocument) -> None: ...
    def load_all_metadata(self) -> Dict[str, ChapterMetadata]: ...
    def load_metadata(self, output_file: Path) -> Optional[ChapterMetadata]: ...
    def save_metadata(self, metadata: ChapterMetadata, output_file: Path) -> Path: ...
    
    # Checksums
    @staticmethod
    def compute_sha256(file_path: Path) -> str: ...
```

### `ProjectRegistry` (`src/storage/repository.py`)
Manages multi-project paths and last-active project persistence.

```python
class ProjectRegistry:
    def register_project(self, project_path: Path | str) -> None: ...
    def list_projects(self) -> List[dict]: ...
    def get_last_active_project(self) -> Optional[Path]: ...
    def set_last_active_project(self, path: Path | str) -> None: ...
```

---

## 📦 Batch & Scanning (`src/batch/`)

### `ChapterScanner` (`src/batch/scanner.py`)
Scans directories, sorts naturally, and inspects checkpoints.

```python
class ChapterScanner:
    def __init__(self, repository: NovelRepository)
    def extract_chapter_num(self, path: Path, default_idx: int) -> int: ...
    def scan_directory(self, input_dir: Path, output_dir: Path) -> List[ChapterTask]: ...
```

### `BatchRunner` (`src/batch/runner.py`)
Sequential batch orchestration with Rich progress.

```python
class BatchRunner:
    def __init__(self, repository: NovelRepository, model_name: str = "gemini-2.5-pro", console: Optional[Console] = None)
    def run_batch(
        self,
        input_dir: Path,
        output_dir: Path,
        limit: Optional[int] = None,
        force_retranslate: bool = False,
        tasks: Optional[List[ChapterTask]] = None,
        progress_callback: Optional[Callable[[str, int, int, str], None]] = None,
        stage_callback: Optional[Callable[[str, PipelineStage, str, float], None]] = None
    ) -> List[ChapterMetadata]: ...
```

---

## 📋 Data Schemas (`src/models/`)

### Key Pydantic Models

* **`TranslationState` (`src/models/state.py`)**: The LangGraph shared state object passed across nodes.
* **`NovelBible` (`src/models/bible.py`)**: Root memory document holding `characters`, `glossary`, `summaries`, and `style_guide`.
* **`CharacterProfile` (`src/models/bible.py`)**: Individual character sheet (`name`, `original_name`, `role`, `gender`, `voice`, `aliases`).
* **`GlossaryItem` (`src/models/bible.py`)**: Canonical term mapping (`source`, `target`, `category`, `notes`).
* **`ChapterMetadata` (`src/models/metadata.py`)**: Chapter metadata record with paired `CheckpointData`, `QualityAudit`, and `TranslationStats`.
* **`CheckpointData` (`src/models/metadata.py`)**: Stage tracking (`status`, `last_completed_stage`, `failed_stage`, `last_error_type`, `last_error_traceback`, `error_logs`).
* **`ErrorLogEntry` (`src/models/metadata.py`)**: Granular error log (`timestamp`, `stage`, `error_type`, `message`, `traceback`, `retry_attempt`, `model`).
* **`ProjectMetadataDocument` (`src/models/metadata.py`)**: Single file document representing `.novel/metadata.json`.
