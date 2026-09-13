# ✨ Stage 4: Feinschliff (`PolishingAgent`)

- **Source File**: [`src/nousetsu/agents/polisher.py`](file:///D:/Code/novel_translation_Agent/src/nousetsu/agents/polisher.py)
- **Class**: `PolishingAgent`
- **German Codename**: **Feinschliff** (*The Stylist*)
- **Production Model**: `gemini-3.5-flash-lite` (Default via `.env` / cascade)
- **Fallback Model**: `gemini-3.5-flash-lite` (Via `FallbackChatModel` on HTTP 429)

---

## 1. Architectural Mission

`Feinschliff` is the stylistic master of the NouSetsu pipeline. Its mission is to transform rough drafted prose into publication-grade, immersive literary target-language fiction by incorporating the specific editorial feedback provided by `Zensor` (CritiqueAgent).

Unlike crude automated paraphrasers, `Feinschliff`:
1. Systematically purges mechanical **translationese cliches** and passive sentence structures.
2. Ingests raw source text as a **read-only nuance reference** to resolve ambiguous draft phrasing without hallucinating new plot beats.
3. Enhances **prose cadence, rhythm, and sensory depth** (alternating terse action beats with lyrical atmospheric exposition).
4. Strictly preserves canonical terminology and character address hierarchies established in the Novel Bible.

```mermaid
graph TD
    DRAFT["Drafted Candidate Prose"] --> POLISH["Feinschliff<br>(PolishingAgent)"]
    NOTES["critique_notes<br>(from Stage 3: Zensor)"] --> POLISH
    GLOSS[("Active Glossary<br>(Novel Bible)")] --> POLISH
    SRC["Raw Source Text<br>(Read-Only Reference)"] --> POLISH
    POLISH --> OUTPUT["polished_text<br>(Publication-Grade Prose)"]
    OUTPUT --> REAUDIT{"Review Pass <= Max Loops?"}
    REAUDIT -->|"Yes (Pass 2+)"| ZENSOR["Stage 3: Zensor (Re-Audit)"]
    REAUDIT -->|"No (Max Loops Exceeded)"| FINISH["Stage 5: Chronist"]
```

---

## 2. Public & Internal Method Contracts

### `__init__`
```python
def __init__(
    self,
    model_name: str = "gemini-3.5-flash-lite",
    fallback_model: Optional[str] = None,
    temperature: Optional[float] = None
)
```

### `polish()`
Primary entry point invoked by `NovelTranslationWorkflow`:
```python
def polish(
    self,
    draft_text: str,
    critique_notes: str,
    active_glossary: List[GlossaryItem],
    bible: NovelBible,
    genre: Optional[str] = None,
    source_text: Optional[str] = None,
    draft_chunks: Optional[List[Any]] = None,
    notify_callback: Optional[Any] = None,
    rate_limiter: Optional[Any] = None,
    stop_event: Optional[Any] = None,
    **kwargs: Any
) -> str
```
- **Returns**: High-polish literary English prose text.
- **Delegation**: If `draft_chunks` has more than 1 chunk, delegates automatically to `polish_chunked()`.

### `polish_chunked()`
Chunk-by-chunk polishing with running context for long chapters:
```python
def polish_chunked(
    self,
    draft_chunks: List[Any],
    critique_notes: str,
    active_glossary: List[GlossaryItem],
    bible: NovelBible,
    genre: Optional[str] = None,
    source_text: Optional[str] = None,
    notify_callback: Optional[Any] = None,
    rate_limiter: Optional[Any] = None,
    stop_event: Optional[Any] = None,
    **kwargs: Any
) -> str
```

---

## 3. Core Cognitive Mechanics

### A. Translationese Purging
`Feinschliff` eliminates stiff machine-translation crutches:
- *"could not help but..."* $\to$ Converted into direct physical actions or internal emotional impulses.
- *"as expected of..."* $\to$ Integrated as natural character admiration or contextual acknowledgment.
- *"it was none other than..."* $\to$ Stated directly with dramatic punch.
- Clunky passive verbs (*"his face was slapped by her"*) $\to$ Active, visceral verbs (*"she slapped his face"*).

### B. Read-Only Nuance Disambiguation
To prevent "telephone game" distortions across multiple polishing passes, `Feinschliff` receives the original source text marked explicitly as `(Reference Only)`:
- Allows the polisher to verify the emotional weight or exact metaphor of an ambiguous sentence in the draft.
- In chunked mode, source text is sliced per chunk (`raw_src_lines[src_start:src_end]`), preventing context overload.

### C. Cadence & Sensory Expansion (Show, Don't Tell)
The agent restructures repetitive subject-verb-object cadences:
- **Action & Tension**: Employs short, punchy sentence fragments to accelerate heart rate during combat or revelations.
- **Exposition & Atmosphere**: Weaves sweeping, layered descriptive periods with tactile, auditory, and olfactory textures.
- **Dialogue Pacing**: Tightens verbal sparring to sound like natural spoken dialogue while strictly retaining honorific titles and relationship distance.

### D. Target Language Regression Guard
If the model produces prose that accidentally reverts to the source language (or an unlocalized bilingual mix):
- `detect_language(text)` detects the regression.
- The polisher automatically discards the corrupt generation and retains `draft_text`, guaranteeing that the chapter remains 100% in the target language.

### E. AI Safety Block Stripping Retry
If Google AI safety filters trip on a sensitive scene during polishing:
- First retry: Automatically strips the raw source text reference and retries polishing using only the already-drafted target text.
- Fallback: If still blocked, logs a warning and safely returns the unmodified `draft_text`, allowing the pipeline to proceed without data loss.

---

## 4. Domain Skills Active for Polisher

Registered via [`src/nousetsu/skills/builtin/polisher.py`](file:///D:/Code/novel_translation_Agent/src/nousetsu/skills/builtin/polisher.py):

| Skill Name | Title | Priority | Mission |
|:---|:---|:---:|:---|
| `translationese_filter` | Anti-Translationese & Stiff Phrasing Filter | 110 | Eliminates repetitive machine-translation cliches, awkward passives, and unnatural syntax. |
| `prose_cadence_enhancer` | Literary Cadence & Rhythmic Sentence Variation | 100 | Crafts dynamic sentence variety, lyrical pacing, and immersive sensory descriptions. |
| `address_form_preservation` | Address Form & Nickname Preservation | 95 | Preserves exact dialogue address choices (formal names vs. nicknames) during stylistic polishing. |
| `show_dont_tell` | Show-Don't-Tell Emotional Depth Enhancer | 90 | Transforms flat emotional assertions into physical character behaviors and atmospheric cues. |
| `dialogue_flow` | Natural Spoken Dialogue Cadence | 85 | Enhances natural conversational cadence and verbal sparring without diluting regional dialects. |

---

## 5. RAG System Interaction

- **Indirect Ingestion**: `Feinschliff` does not directly query the vector database; instead, it consumes the actionable critique notes from `Zensor`, which already incorporate canonical Translation Memory (TM) constraints from RAG.
- **Cyclic Feedback**: Polished outputs are immediately re-evaluated by `Zensor` in subsequent reflection loops, ensuring stylistic embellishments never sacrifice factual fidelity.

---

## 6. Testing & Hermetic Mocking

`PolishingAgent` is tested deterministically with `MockNovelLLM`:
```python
agent = PolishingAgent(model_name="mock-model")
polished = agent.polish(
    draft_text="She could not help but smile.",
    critique_notes="Remove translationese cliches.",
    active_glossary=[],
    bible=bible
)
assert len(polished) > 0
```
- Fully tested across `tests/test_review_loop.py` and `tests/test_translation_fallback.py`.
