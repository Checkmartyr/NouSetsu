# 🛠️ Code & Developer API Reference

This document provides a technical API reference for core classes, functions, utilities, and Pydantic models in **NouSetsu**.

---

## 🤖 Agents (`src/nousetsu/agents/`)

### `EntityExtractorAgent` (*Schriftdetektiv*) (`src/nousetsu/agents/extractor.py`)
Extracts named entities, characters, and glossary candidates from source text before translation begins.

```python
class EntityExtractorAgent:
    def __init__(self, model_name: str = "gemini-2.5-pro")
    
    def extract(
        self,
        source_text: str,
        bible: NovelBible
    ) -> Tuple[List[CharacterProfile], List[GlossaryItem], List[str]]:
        """
        Extracts new characters and glossary terms.
        Returns: (new_characters, new_terms, active_terms_in_chapter)
        """
```

---

### `ContextAwareDrafterAgent` (*Wortschmied*) (`src/nousetsu/agents/drafter.py`)
Produces initial novelistic translation drafts with zero-anaphora resolution, character voices, and episodic memory.

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

### `CritiqueAgent` (*Zensor*) (`src/nousetsu/agents/critic.py`)
Performs independent fidelity, style, and glossary compliance audits for both raw drafts and polished iterations.

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
        Audits draft or polished translation against source.
        Returns: (QualityAudit object, critique_notes string)
        """
```

---

### `PolishingAgent` (*Feinschliff*) (`src/nousetsu/agents/polisher.py`)
Refines prose cadence, remedies critique feedback, and eliminates translationese tropes.

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
        Polishes prose to publication standard based on critique notes.
        Returns: Polished Markdown text.
        """
```

---

### `ChroniclerAgent` (*Chronist*) (`src/nousetsu/agents/chronicler.py`)
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
        """Generates episodic synopsis and records character state changes."""

    def assemble_metadata(...) -> ChapterMetadata:
        """Assembles final ChapterMetadata record with stats, checkpoint data, and audit scores."""
```

---

## ⚡ Utilities (`src/nousetsu/utils/`)

### `SlidingWindowRateLimiter` (`src/nousetsu/utils/rate_limiter.py`)
Thread-safe sliding-window rate limiter enforcing dual TPM and RPM quotas across a 60-second window.

```python
class SlidingWindowRateLimiter:
    def __init__(self, max_tpm: int = 16000, max_rpm: int = 60, window_seconds: float = 60.0)

    def acquire(self, tokens: int = 1, stop_event: Optional[threading.Event] = None) -> None:
        """
        Blocks until capacity is available under both TPM and RPM limits.
        Sleeps in 200–250ms chunks to allow instant interruption via stop_event.
        """

    def reset(self) -> None:
        """Clears all logged request and token timestamps."""
```

### `estimate_tokens` (`src/nousetsu/utils/rate_limiter.py`)
Fast, offline token estimator optimized for mixed CJK and Latin text.

```python
def estimate_tokens(text: str) -> int:
    """
    Computes token estimate without external model weights:
    ~1.7 tokens per CJK character + ~1.3 tokens per Latin word.
    """
```

### `detect_language` (`src/nousetsu/utils/language.py`)
Zero-dependency Unicode script and stop-word frequency analyzer.

```python
def detect_language(text: str, default: str = "Japanese") -> str:
    """
    Detects language from raw sample text:
    Recognizes Japanese, Chinese, Korean, Thai, Russian, English, Spanish, French, German.
    """
```

---

## 🛡️ LLM Invocation & Retry (`src/nousetsu/agents/llm.py`)

```python
def get_llm(model_name: str, temperature: float = 0.3) -> BaseChatModel:
    """Factory returning Google Gemini model, or MockNovelLLM if no API key is present."""

def extract_text_from_message(content: Any) -> str:
    """Extracts plain text from LLM response, discarding reasoning blocks."""

def is_rate_limit_error(err: Exception) -> bool:
    """Returns True if exception is HTTP 429, ResourceExhausted, or rate limit exceeded."""

def parse_retry_delay(err: Exception) -> Optional[float]:
    """Parses delay seconds from retry-after headers or 'retry in Xs' error text."""

def invoke_with_retry(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = 4,
    initial_delay: float = 2.0,
    backoff_factor: float = 2.0,
    notify_callback: Optional[Callable[[str], None]] = None,
    rate_limiter: Optional[SlidingWindowRateLimiter] = None,
    estimated_tokens: int = 1000,
    stop_event: Optional[threading.Event] = None,
    **kwargs: Any
) -> Any:
    """
    Executes function with rate limit token acquisition, 25s–65s window rollover
    quota backoff for 429 errors, and exponential backoff for transient errors.
    """
```

---

## 🔄 Graph & Workflow (`src/nousetsu/graph/`)

### `NovelTranslationWorkflow` (`src/nousetsu/graph/workflow.py`)
Coordinates the multi-agent LangGraph execution and reflection review cycle.

```python
class NovelTranslationWorkflow:
    def __init__(
        self,
        model_name: str = "gemini-2.5-pro",
        rate_limiter: Optional[SlidingWindowRateLimiter] = None,
        max_review_loops: int = 3,
        quality_threshold: float = 8.5
    )
    
    def run(
        self,
        initial_state: TranslationState,
        stage_callback: Optional[Callable[[PipelineStage, str, float], None]] = None,
        stop_event: Optional[threading.Event] = None
    ) -> TranslationState:
        """
        Runs LangGraph workflow through extraction, drafting, and conditional
        reflection loop (critique <-> polish) until quality >= 8.5 or loop cap reached.
        """
```

---

## 📦 Batch & Scanning (`src/nousetsu/batch/`)

### `BatchRunner` (`src/nousetsu/batch/runner.py`)
Sequential batch orchestration with Rich progress, rate limits, and thread-safe cancellation.

```python
class BatchRunner:
    def __init__(
        self,
        repository: NovelRepository,
        model_name: str = "gemini-2.5-pro",
        auto_update_bible: Optional[bool] = None,
        max_tpm: Optional[int] = None,
        max_rpm: Optional[int] = None,
        max_review_loops: Optional[int] = None,
        quality_threshold: Optional[float] = None,
        console: Optional[Console] = None
    )

    def stop(self) -> None:
        """Signals runner to gracefully halt and preserve paused checkpoint."""

    def reset_stop(self) -> None:
        """Clears stop event for a new batch run."""

    @property
    def is_stopped(self) -> bool:
        """Returns True if stop signal was sent."""

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

## 💾 Storage & Repositories (`src/nousetsu/storage/`)

### `NovelRepository` (`src/nousetsu/storage/repository.py`)
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

---

## 📋 Data Schemas (`src/nousetsu/models/`)

### Key Pydantic Models

* **`TranslationState` (`src/nousetsu/models/state.py`)**: The LangGraph state schema.
  * Fields: `chapter_id`, `chapter_num`, `source_text`, `draft_text`, `critique_notes`, `quality_audit`, `polished_text`, `review_iteration`, `max_review_loops`, `quality_threshold`, `best_polished_text`, `best_audit`, `metadata`.
* **`ProjectConfig` (`src/nousetsu/models/config.py`)**: Project configuration settings.
  * Fields: `project_id`, `title`, `source_language`, `target_language`, `raw_dir`, `output_dir`, `model_name`, `auto_update_bible`, `max_tpm`, `max_rpm`, `max_review_loops`, `quality_threshold`.
* **`NovelBible` (`src/nousetsu/models/bible.py`)**: Root memory document holding `characters`, `glossary`, `summaries`, and `style_guide`.
* **`ChapterMetadata` (`src/nousetsu/models/metadata.py`)**: Chapter metadata record with paired `CheckpointData`, `QualityAudit`, and `TranslationStats`.
* **`CheckpointData` (`src/nousetsu/models/metadata.py`)**: Stage tracking with `status` (`PENDING`, `IN_PROGRESS`, `PAUSED`, `COMPLETED`, `FAILED`), `stage_artifacts`, and `error_logs`.
* **`StageArtifacts` (`src/nousetsu/models/metadata.py`)**: Intermediate outputs (`extracted_characters`, `extracted_terms`, `draft_text`, `critique_notes`, `polished_text`).
