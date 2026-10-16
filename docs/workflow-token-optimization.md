# Reducing pipeline tokens with NLP and a specialized critic

**Checked: 2026-10-16, Asia/Bangkok.** Scope: English, Japanese and Chinese **into Thai**, using the current NouSetsu pipeline and a possible single-24GB-GPU specialist. This report implements the approved **analysis-only** work: no application code, settings, training data, model weights, paid API calls or GPU resources were changed.

## Recommendation

First **experiment with lower critic reasoning**, then evaluate compact critique, shared deterministic preflight and exact-input audit reuse. The critic is the largest recorded cost in the inspected novel. A small fine-tuned critic is a subsequent experiment, initially in shadow mode; it must earn the right to replace any semantic review through bilingual evaluation. Local RAG reranking is a task-specific model opportunity for other projects, but saves nothing for this book while RAG is disabled.

NLP can cheaply check format, known terms, explicit entity/number preservation and candidate identity. It cannot establish that a translation preserves unstated subjects, irony, relationships, narrative action or literary voice. Passing these checks must never create a semantic passing score.

### What this report measures

| Status | Meaning |
|---|---|
| Observed | Read directly from project traces, metadata, configuration or current code. |
| Calculated | Arithmetic using observed tokens and stated API prices; not a recovered invoice. |
| Proposed | A future code or workflow change; no saving has yet been demonstrated. |
| Unknown | Requires labeled data, runtime measurement or a controlled trial. |

The analysis uses `Isekai Tenshou Shitanode Honmono Nokukkoroga Mita I !` for quantitative estimates. That project's observed direction does not establish English→Thai or Chinese→Thai results. A local inventory, grouped by case-folded source path and latest metadata timestamp, found the following configured source directions. Configuration labels are not a script audit, and inventory size is not labeled training-set size.

| Configured direction | Completed unique records | Project breakdown |
|---|---:|---|
| JA → TH | 528 | Dagekikei 49; Douyara 288; Isekai 127; ShinjaZero 36; Tech 28 |
| EN → TH | 613 | EWOWMAIBTYPF 302; Villainess 221; YomeMusou 90 |
| ZH → TH | None found in configured local project directories | Does not prove Chinese material is absent elsewhere |

Villainess has 224 unique records including three incomplete; count only the 221 completed in the table. Eight other configured Thai-directed projects had no metadata and were excluded. Latest metadata in these inventoried projects records `review_status=draft`: there are no formal approved labels in that field, although this does not prove nobody has read the prose. No corpus prose was exported for this inventory.

## 1. Where the recorded tokens go

There are **127 unique completed chapters**. Metadata contains 254 entries representing exact duplicate aliases for those chapters; deduplicate aliases before summing or splitting data. The 1,118 prompt traces contain 1,097 successes, 20 safety-blocked attempts and one error. Attempts matter when estimating paid workload, even when only a final chapter is accepted.

| Recorded category | Tokens | Accounting rule |
|---|---:|---|
| Input | 8,837,363 | Includes cached input |
| Cached input | 1,309,902 | Subset of input, not additional tokens |
| Visible output | 1,306,320 | Does not include reasoning in this trace representation |
| Thought/reasoning | 3,690,136 | Generated tokens and output billing must include these |
| All generated | 4,996,456 | Visible + reasoning |
| All input + generated | 13,833,819 | Cached subset is not added twice |

The recorded Gemini mix has a **$12.579296395 standard paid-list-price equivalent**, or **$0.09905 per completed chapter** including recorded attempts. Actual payment can differ with free-tier usage or account pricing. The calculation follows model-specific cached-input rates and bills reasoning with output. Taxes, unrecorded calls and any explicit cache-storage charges are excluded; the estimate is not an invoice. [Google pricing](https://ai.google.dev/gemini-api/docs/pricing).

| Recorded model | Calls | Input tokens | Visible output | Reasoning | Cached input subset | USD per million input / output / cached | Calculated USD |
|---|---:|---:|---:|---:|---:|---|---:|
| `gemini-3.1-flash-lite` | 560 | 4,094,614 | 832,480 | 1,177,131 | 110,283 | $0.25 / $1.50 / $0.025 | $4.013256325 |
| `gemini-3.5-flash-lite` | 558 | 4,742,749 | 473,840 | 2,513,005 | 1,199,619 | $0.30 / $2.50 / $0.03 | $8.566040070 |

For each model, `USD = ((input − cached) × input_rate + cached × cache_rate + (visible + reasoning) × output_rate) / 1,000,000`. Sum those model costs within each stage:

| Stage | Calls | Input | Visible output | Reasoning | Cached subset | Input + generated | Calculated USD |
|---|---:|---:|---:|---:|---:|---:|---:|
| Extraction | 127 | 561,397 | 60,581 | 276,456 | 0 | 898,434 | $0.645904750 |
| Drafting | 129 | 850,084 | 342,818 | 270,743 | 6,118 | 1,463,645 | $1.131485950 |
| Critique | 433 | 3,901,383 | 253,881 | 2,213,233 | 1,199,619 | 6,368,497 | $7.008362720 |
| Polishing | 302 | 2,667,392 | 427,597 | 626,263 | 104,165 | 3,721,252 | $2.224200875 |
| Chronicling | 127 | 857,107 | 221,443 | 303,441 | 0 | 1,381,991 | $1.569342100 |
| **Total** | **1,118** | **8,837,363** | **1,306,320** | **3,690,136** | **1,309,902** | **13,833,819** | **$12.579296395** |

Reproduction inputs are this project's `.novel/metadata.json`, `.novel/traces/raw_chapters/chapter_*.json` and `.novel/config.yaml`. Deduplicate metadata by normalized source path and traces by trace ID; sum each attempt once, including recorded failed attempts with usage. Use the trace's actual model rather than today's role defaults. Current telemetry definitions are in [token_metrics.py](../src/nousetsu/analysis/token_metrics.py) and [tracker.py](../src/nousetsu/analysis/tracker.py).

| Critic measurement | Observed or calculated value |
|---|---:|
| Input | 3,901,383 tokens |
| Visible output | 253,881 tokens |
| Reasoning | 2,213,233 tokens |
| Total input + generated | 6,368,497 tokens |
| Standard API cost equivalent | $7.00836272 |
| Critic reasoning cost component | $5.5294135 |

Thus critique accounts for about **56% of recorded cost**, while critic reasoning alone accounts for about **44% of the entire estimate**. Lowering thinking can be worth more than shortening visible critique, but the quality effect is unknown and must be measured. A shorter prompt does not automatically produce a proportional reasoning reduction.

### What duplicate requests actually support

Ten additional successful critique requests repeated the recorded `(chapter_num, model, system_prompt, user_prompt)` values: their observed consumption totals **138,826 tokens / $0.13325859**, roughly 1% of this recorded workload's cost. The stored request match does not prove that every effective generation setting was identical. This is a retrospective reuse opportunity, not a guarantee that a future audit cache will accept every one after applying the complete validity key. No raw polisher output in this sample contained `NO_CHANGES_NEEDED`; do not attribute the observed duplicates to that sentinel.

Four polishing requests also duplicate payloads. They are generative/stochastic revision attempts: identical input can intentionally produce another candidate. **Do not count them as safely removable audits or automatically reuse their prose.** Textually similar chapters, normalized whitespace matches or overlapping scene chunks are also insufficient grounds for semantic audit reuse.

RAG is disabled for the inspected book, so replacing the reranker contributes **zero current-book savings**. Elsewhere, the real reranker invokes a separate generative LLM without recording that usage in the five-stage PromptTracker totals; do not present this report's five-stage totals as every possible ancillary model expense. See [reranker.py, lines 94–128](../src/nousetsu/rag/reranker.py#L94).

## 2. Existing optimizations and remaining waste

| Process | What the code already does | Remaining opportunity |
|---|---|---|
| Extraction | Filters known roster/glossary by scene, no empty fallback, unlimited matching characters; deduplicates registered names | Derive known-term occurrences locally; evaluate an optional candidate-span detector later |
| Drafting | Receives contextual memory and filtered scene material; supports long-text subdivision | Preserve semantic context; do not remove omitted-subject evidence just to reduce size |
| Critique | Native structured output, scene filtering, chunking, glossary/language guards | Compact issue output, reuse identical completed audits, move structural checks before expensive calls |
| Polishing | Patch mode after first pass; title, corruption, truncation and language guards | Pass only relevant issue records to each chunk; avoid repeating full chapter notes |
| Chronicling | Compact provisional entity cards, filtered characters and capped chapter input | Keep narrative memory semantic; further truncation is unsafe |
| RAG reranking | Existing injectable cross-encoder-shaped interface with LLM implementation | Optional non-generative multilingual cross-encoder for RAG-enabled books |

Verified anchors: [extractor.py:102](../src/nousetsu/agents/extractor.py#L102), [extractor.py:266](../src/nousetsu/agents/extractor.py#L266), [critic.py:157](../src/nousetsu/agents/critic.py#L157), [workflow.py:830](../src/nousetsu/graph/workflow.py#L830), [chronicler.py:108](../src/nousetsu/agents/chronicler.py#L108), [reranker.py:15](../src/nousetsu/rag/reranker.py#L15).

The critique template explicitly demands verbose notes, including extra stylistic suggestions for strong drafts: [templates.py:120](../src/nousetsu/prompts/templates.py#L120). The resulting string is embedded into the polisher system prompt at [polisher.py:210](../src/nousetsu/agents/polisher.py#L210) and passed to every polishing chunk at [polisher.py:625](../src/nousetsu/agents/polisher.py#L625). This creates both visible output and downstream input costs.

The critic reads full source and candidate text on every pass: [critic.py:216](../src/nousetsu/agents/critic.py#L216). The prompt asks a later pass to verify previous directives, but the workflow call does not supply previous notes as such: [templates.py:104](../src/nousetsu/prompts/templates.py#L104), [workflow.py:626](../src/nousetsu/graph/workflow.py#L626). A bounded issue history is more useful than repeatedly generating a long fresh essay.

## 3. Recommended future changes, in priority order

| Rank | Recommendation | Measured opportunity / scenario | Effort | Translation risk |
|---|---|---|---|---|
| 1 | Experiment with lower critic reasoning | $5.52941 current reasoning component; halving it would save $2.76471 (21.98% overall) if behavior stayed unchanged | Low setting effort; bilingual evaluation required | High if critical errors become harder to detect |
| 2 | Compact actionable critique | $0.63322 current visible critic output; halving only that output saves $0.31661 (2.52% overall), plus unknown downstream effects | Medium | Medium: losing evidence or global issues |
| 3 | Shared NLP preflight | Existing checks are available; avoided calls not yet measured | Medium | Low for advisory checks; high if treated as semantic approval |
| 4 | Exact-input audit reuse | Ten repeated serialized requests, $0.13326 potential reuse before full-key validation | Medium | Low with a complete key; high with stale context |
| 5 | Conditional reranking / alignment / specialist | Reranking saves $0 here; other net savings unknown | Medium to high | Retrieval and semantic false-negative risks require calibration |

### A. Experiment with lower critic reasoning

The inspected project requests **high thinking for all five roles**, overrides `quality_threshold` to **9.5**, and has RAG disabled. Per-role controls already exist in [config.py:45](../src/nousetsu/models/config.py#L45), resolve through [config.py:88](../src/nousetsu/models/config.py#L88), and reach the critic at [critic.py:58](../src/nousetsu/agents/critic.py#L58). A future trial can change only the critic setting while freezing prompts, source, context, other roles and threshold. No setting is changed by this report.

Compare the current high setting against a supported lower level, verifying actual returned reasoning usage rather than assuming the requested level halves tokens. Review critical-error recall, notes and final prose with blinded bilingual raters. Measure the entire reflection cycle: a cheaper audit that triggers extra polishing or misses an omission is not necessarily cheaper per accepted chapter. The 50% arithmetic scenario would reduce this estimate to **$9.814589645**, not a demonstrated outcome. Test reasoning changes separately from prompt changes before combining them.

### B. Compact critic feedback

Keep complete semantic inspection and existing quality scores. Replace mandatory verbosity with an internal issue list containing category, severity, exact supporting quote/span, concise explanation and suggested action. Permit an empty list when no actionable issue exists. Render that list into the existing `critique_notes` string for compatibility; there is no need to redesign every public interface first. Current fields are in [schemas.py:24](../src/nousetsu/models/schemas.py#L24).

Use a bounded summary plus only relevant unresolved issues for each polishing chunk. Include global identity/register/continuity issues in every affected chunk. If an issue cannot be mapped confidently, retain it rather than silently dropping it. Do not hard-cap the number of critical problems or shorten the source inspection merely to hit a token target.

Run a paired replay to measure critique output, subsequent polishing input, reasoning, accepted edits and total chapter cost. No evidence currently supports a blanket “50% fewer tokens with unchanged quality” claim.

### C. Shared deterministic preflight

Extract the current script-aware glossary and language checks into a reusable report, then add empty-output, unparsed-patch and severe-truncation checks before calling the semantic critic. Cover single-text, chunked and sensitive-subdivision paths; avoid branch-dependent validation. Retain post-polish guards. The existing checks currently occur after critic invocation: [critic.py:651](../src/nousetsu/agents/critic.py#L651), [workflow.py:856](../src/nousetsu/graph/workflow.py#L856).

Only an unambiguous structural failure may bypass the LLM audit and enter the existing repair flow with explicit failure notes. Positive checks never certify fidelity. Number/name differences, mixed script and missing glossary strings are risk signals, not always errors: aliases, inflection, quotation, alternative address forms and polysemy need interpretation. Preserve the existing detector's high-confidence language-regression behavior rather than failing every embedded source-language name.

Reuse [glossary_filter.py:12](../src/nousetsu/utils/glossary_filter.py#L12). Keep core characters even when not named, as required by [character_filter.py:24](../src/nousetsu/utils/character_filter.py#L24) for omitted-subject resolution. Do not skip extraction solely because a regex/NER pass finds no unknown names.

| NLP technique | Future use and implementation seam | Limitation |
|---|---|---|
| Dictionary/alias matching | Share the existing glossary matcher across extraction and preflight; cache known-term occurrences by source hash + glossary revision | A term's occurrence does not resolve its sense or correct translation |
| Thai segmentation | Reuse installed PyThaiNLP with a project-specific name/term dictionary for target-side boundary checks | Segmentation alone does not reduce the LLM tokenizer's token count |
| Number and script inventory | Compare digits, amounts and expected scripts; retain original offsets and normalize only in the matcher | Written numbers, unit conversions and foreign names need interpretation |
| Structural checks | Flag empty output, unparsed patch delimiters and severe corruption before semantic review | A fluent, structurally clean translation may still reverse a negation or omit an event |
| Multilingual sentence alignment | Flag low-coverage source spans for bilingual inspection; allow one-to-many matches | Similarity is not a fidelity score; a missed negation may remain highly similar |

[PyThaiNLP tokenization documentation](https://pythainlp.org/docs/5.1/api/tokenize.html) supports dictionary-based segmentation. Keep this preprocessing local and reversible; do not rewrite original literary text into bag-of-words or stemmed input. Add these helpers behind agent/workflow internals, using current dependencies before adding a separate NER service. Learned NER is an optional later proposal whose EN/JA/ZH name recall needs labels.

### D. Reuse only identical successful audit requests

Add a chapter-local cache keyed by the complete request identity: source and candidate text, language/genre, relevant Bible/glossary/roster, skills/procedural guidance, RAG payload, rendered prompt/schema version, model/provider and generation settings. A changed source, context, configuration or model invalidates the key. Different first-pass versus later-pass RAG payloads must not collide. [workflow.py:598](../src/nousetsu/graph/workflow.py#L598).

Cache only a finished, valid semantic audit. Never cache provider errors, content-filter bypass scores, malformed output or an in-flight request. Existing `NO_CHANGES_NEEDED` returns identical text and can create a reusable candidate, but text identity alone is insufficient: [polisher.py:274](../src/nousetsu/agents/polisher.py#L274).

Initially keep the cache in memory for one chapter invocation; no persisted reuse is implied on resume. Add a local reuse event with zero new API tokens and the original audit reference. Preserve review counters, repair attempts and best-candidate selection. A later versioned checkpoint extension would need save/restore work in [metadata.py:36](../src/nousetsu/models/metadata.py#L36) and [runner.py:409](../src/nousetsu/batch/runner.py#L409).

### E. Specialized local critic, after labeling and shadow evaluation

Use **the original `Qwen/Qwen3.5-4B`, BF16 LoRA**, as the first training candidate for bounded bilingual error-span detection and compact JSON. This is a task choice to test, not evidence of superior Thai criticism. Parent licensing is Apache 2.0 and its non-thinking API mode is documented. An “uncensored” derivative is not needed to establish this capability, nor does an uncensored label prove fidelity. [Original model card](https://huggingface.co/Qwen/Qwen3.5-4B).

Begin with compact source/Thai candidate pairs plus frozen local glossary/context. Have the specialist identify actionable errors and uncertainty; keep the existing semantic critic as the authority during shadow mode. Malformed spans, missing evidence, out-of-domain language, long-context cases, contradictory findings or uncertain alignment require the existing full critic. Self-reported model confidence is not a calibrated probability or an automatic bypass permission.

This shadow experiment initially **adds** local compute and may add evaluation cost. Only a separately validated routing policy can yield API savings. Do not let a specialist invent high scores to terminate the review loop. A later extractor adapter is a separate problem with separate span/identity labels; avoid combining it with the first critic experiment.

### F. Task-specific reranker when RAG is used

The existing `BaseCrossEncoderReranker.rerank` accepts query/documents/top-k and returns SearchResults. A local option such as [`BAAI/bge-reranker-v2-m3`](https://huggingface.co/BAAI/bge-reranker-v2-m3) is a multilingual, non-generative reranking candidate, not a literary fidelity evaluator. Evaluate canonical-memory retrieval recall for EN/JA/ZH→TH before adopting it.

Implement behind the current factory/injection seam, retaining IDs, scores/ranks, metadata, stable ordering and current RRF fallback. Check cancellation between local batches; record local latency separately. Schedule stage loading so combined models do not silently require more than the single GPU budget. [reranker.py:171](../src/nousetsu/rag/reranker.py#L171), [workflow.py:177](../src/nousetsu/graph/workflow.py#L177).

## 4. Training feasibility and data requirements

### One 24GB GPU is a candidate budget, not a measured fit

Unsloth estimates Qwen3.5 BF16 LoRA at about **10GB for 4B** and **22GB for 9B**, and warns against 4-bit QLoRA for both dense and MoE Qwen3.5 due to quantization differences. These are vendor setup estimates, not verified memory use for this project's bilingual sequence lengths. Choose BF16 LoRA 4B first; do not promise 9B long-context training fits 24GB. Pin model/training revisions and measure peak VRAM before a run. [Unsloth fine-tuning guide](https://unsloth.ai/docs/models/qwen3.5/fine-tune).

Start feasibility testing at **2K**, then **4K total training tokens**, microbatch 1 with accumulation/checkpointing. Source + Thai candidate + instructions + glossary + labels must all fit; truncate none silently. Observed critic call input has a median of **9,325 provider tokens**; Qwen tokenization will differ, but the proposed training windows do not cover typical current requests. Train on aligned scene windows with original offsets and necessary context. A model trained on windows has not demonstrated full-chapter review. Use an independent long-chapter/context probe and full-critic fallback; the advertised family context maximum does not establish training or serving fit.

### Traces are weak labels until reviewed

All 127 inspected chapters have `review_status=draft`. Existing LLM scores, self-critique and polished outputs are **weak teacher labels**, not human gold. The dataset must include human-confirmed source/target errors and clean negatives, with explicit distinction between objective fidelity errors and optional prose preferences. A tiny one-novel corpus cannot establish English/Japanese/Chinese generalization into Thai.

Critic trace `parsed_output` stores scores, `passed`, `warnings_count` and only a **200-character `critique_notes_preview`**, not complete error annotations. Recover a target only from strictly parsed full `raw_output` or human-corrected text. Never train on that preview as full feedback or treat a warning count as the warning list. StageArtifacts holds final notes, not every review pass. Existing full targets are verbose; human-check compact issue conversions rather than teaching their verbosity. [critic.py:394](../src/nousetsu/agents/critic.py#L394).

Before any export or training, inventory eligible material, provenance/rights, source-target pairing, duplicated requests, retries and language directions. Keep source/target text separate from hidden provider reasoning; train only the intended visible compact response. Do not export API keys, user files or entire trace dumps as an unreviewed dataset. Sensitive literary examples should teach faithful preservation without adding content.

Deduplicate exact chapter aliases and retries before splitting. Group train/validation/test by novel; keep near-duplicate scenes, neighboring context windows and revisions in the same split, with an overlap embargo around held-out chapter boundaries. Freeze the held-out novel/language set before tuning. Where the inventory lacks an independent Chinese→Thai novel, mark that coverage gap and obtain reviewed data rather than manufacture a Chinese quality claim.

Keep issue spans tied to original offsets and exact quoted evidence. Review weak labels before treating warnings as errors; include examples where no edit is needed. Separate scores from error localization: a model trained to repeat teacher scores can appear calibrated without finding omissions. Record rater disagreements and adjudications, and never use held-out reviewer feedback as new training data during the same evaluation.

TRL supports completion-only and assistant-only loss. Assistant masks depend on the actual chat template's generation delimiters. Inspect token-level masks on rendered Qwen3.5 examples: prompt, source, glossary and reasoning should have no target loss; the intended assistant JSON and EOS should. Verify truncation, packing boundaries and EOS explicitly rather than assuming a configuration flag worked. [TRL SFT documentation](https://huggingface.co/docs/trl/sft_trainer).

### Provider controls need their own integration work

Per-role temperature/thinking controls already exist in [config.py:45](../src/nousetsu/models/config.py#L45). The custom OpenAI-compatible constructor currently forwards model/key/temperature/base URL only: [llm.py:487](../src/nousetsu/agents/llm.py#L487). Setting a Gemini `thinking_budget=0` does **not** guarantee non-thinking vLLM inference. Qwen3.5 documents a request-level `chat_template_kwargs.enable_thinking=False`; validate request forwarding or a pinned server default before measuring it. [Qwen non-thinking instructions](https://huggingface.co/Qwen/Qwen3.5-4B#instruct-or-non-thinking-mode).

Future adapter serving must validate the exact Qwen architecture, target modules, tokenizer/template and vLLM revision together; generic LoRA serving support does not establish this adapter's fit or MTP compatibility. Keep training dependencies in a separate pinned environment: the application currently requires Python 3.13+ and does not declare a training stack. [vLLM LoRA documentation](https://docs.vllm.ai/en/latest/features/lora/), [pyproject.toml](../pyproject.toml).

## 5. Cost sensitivity and break-even

There is no measured percentage saving for compact feedback, local NLP, fine-tuning or lower thinking in this project. Use the observed duplicate-audit opportunity as a small measured reference, and estimate other changes only after shadow/replay measurements.

| Scenario | Optimistic avoided API cost for this 127-chapter workload | What it does not include |
|---|---:|---|
| Observed exact duplicate successful critic requests | $0.13325859 | Full future key validity and changed requests |
| Remove 25% of critic reasoning billing | $1.38235 | Quality effects; other critic input/output persists |
| Remove 50% of critic reasoning billing | $2.76471 | Not an observed or quality-neutral saving |
| Replace 25% of all critic API work | $1.75209 | Specialist serving, fallback and labeling |
| Replace 50% of all critic API work | $3.50418 | Not a validated routing result |
| Replace all critic API work | $7.00836 | An upper-bound arithmetic scenario, not a safe proposal |

Do not add these rows: reasoning reductions, replaced requests and duplicate reuse overlap. At this workload scale, expensive labeling/training can exceed many books' API savings. Token reduction and dollar reduction also differ because reasoning/output and cached input have different rates.

### Three different kinds of optimization

| Change | Logical tokens | Billing / compute effect |
|---|---|---|
| Shorter critique or removed redundant request | Fewer new tokens or calls | Reduces corresponding usage if retries do not offset it |
| Gemini cached input | Same logical input, with a cached subset | Discounted input; explicit cache storage may add charges |
| vLLM prefix caching | Same logical input and output | Reuses prefill computation; does not speed decoding by itself |
| Smaller model or quantization | Not inherently fewer tokens; tokenizer can differ | May lower memory/compute cost; quality and throughput must be measured |
| MTP/speculative decoding | Same intended translation length | May accelerate generation, with extra overhead/memory; not an assumed saving |

See [Gemini caching](https://ai.google.dev/gemini-api/docs/caching) and [vLLM prefix caching](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/). Google's Interactions API supports implicit caching; explicit cache objects require a supported generateContent route, so adding them is not merely a prompt setting. Stable instructions are useful cache prefixes; changing scene glossaries/rosters changes the effective prefix. Avoid compressing source prose, required context or schema instructions as a default optimization.

Use `net saving = avoided API charge − local serving charge − extra fallback/evaluation charge`. Include curating labels, training, model storage/startup, idle billing, operational time and human review when assessing total ownership cost. Then calculate `break-even comparable workloads = one-time curation/training cost ÷ net saving per workload`, only if net saving is positive. For example, an assumed $20 one-time experiment and $2 net saving need ten comparable workloads; these inputs are illustrative, not a quote.

Equivalently, `break-even chapters = upfront cost / (baseline cost per accepted chapter − candidate cost per accepted chapter)`. An assumed $20 upfront and $0.02 net saving per chapter require 1,000 chapters; $50 at the same saving requires 2,500. These are sensitivity examples, not measured training expenses or savings.

For a future self-hosted estimate, collect the actual rental rate `r` in USD/hour and billed duration including load, prefill, decoding, retries and idle time. `Local cost = r × billed hours + storage/other charges`; divide by accepted passages/chapters, not merely generated tokens. If projecting before measurement, state prefill throughput `p`, aggregate generated throughput `d`, and assume `active seconds ≈ input/p + (visible + reasoning)/d`; label overlap, cache reuse and utilization assumptions explicitly. No rental rate or throughput has been measured here, so this report makes no dollar-per-million self-hosting quote. MTP and concurrency 1 versus 4 are later serving ablations after quality screening.

Track **cost per accepted chapter**, not only tokens per request. Count all attempts, fallback, reasoning, local compute, failed/truncated output and extra review loops. Preserve cached tokens as a subset of input. A model that uses fewer visible tokens but causes more repairs may be more expensive overall.

## 6. Future evaluation and rollout gates

### Thirty-six source cases, three directions

Use **12 original passages per source language** (EN, JA, ZH), all translated into Thai: **36 cases**. Per source language choose two passages in each of six categories: narration, dialogue, cultural expressions, pronouns/register, terminology and sensitive adult fiction. Use 300–600 Unicode characters; this does not equalize difficulty across languages. Freeze glossary/context and tag two of the twelve with continuity context. The existing JA→TH novel can supply eligible cases, while EN and ZH need independent coverage.

Replay the **current high-thinking baseline versus lower critic thinking alone** first. Test compact prompts, preflight and reuse separately before a combined variant, keeping all other role settings and thresholds fixed. Compare the original small model and later adapter in a separate shadow experiment with thinking off where genuinely supported, MTP off and matching templates/context. Use concurrency 1, a cold prefix cache, native EOS and an explicit output cap initially. Cap hits, malformed JSON, unsupported context and invalid spans are failures; do not silently clip source to make a model pass. Record exact revisions, prompts, input/visible/reasoning/cached tokens, elapsed time, peak memory and all fallback decisions. Compare optimized warm-cache/concurrency/MTP serving only after quality screening.

Use two blinded bilingual raters and adjudication. Score fidelity/omissions/additions, **negation and scope**, names/pronouns/terminology, Thai fluency, voice/register, continuity and required formatting. Evaluate issue precision/recall and critical-error misses for a detector, separately from quality of the final polished prose. Include clean negatives to measure over-editing, and separately labeled controlled corruptions involving a removed sentence, reversed negation, swapped name/number or pronoun. Do not replace natural errors with only synthetic cases. Neither a candidate nor its own uncalibrated confidence can approve itself. [MQM human-evaluation framework](https://github.com/google/wmt-mqm-human-evaluation).

Macro-average the three directions and show each separately. Twelve cases per direction are screening, not a reliable non-inferiority demonstration. Before deployment, pre-register an acceptable quality margin and critical-error policy, then expand independent held-out cases until uncertainty can support that margin. If the trial is underpowered or a direction lacks labeled evidence, remain in shadow/full-critic fallback; do not interpret “no significant difference” as equivalence.

Chinese→Thai needs independently sourced novels/passages, reviewed Thai translations, natural error annotations and clean negatives, with coverage of omitted subjects, negation, names and genre terms. Keep Chinese training novels separate from evaluation novels. Automated format checks and reference-based metrics may supplement human review; generated Gemini outputs are not human reference translations.

### Acceptance checks for eventual implementation

| Compatibility scenario | Required future behavior |
|---|---|
| Bible, glossary, roster, source, prompt, RAG or model setting changes | Invalidate audit reuse and perform the current complete review |
| Clear structural preflight failure | Enter repair with explicit failure notes; never fabricate a semantic pass |
| Advisory number/name/script warning only | Preserve semantic review; record evidence for interpretation |
| Cancellation before/during/after NLP, cache lookup or local inference | Honor the stop event; save only valid completed artifacts, never an in-flight audit |
| Resume from a legacy checkpoint without a fingerprint | Follow current checkpoint semantics; claim no new cross-run cache validity |
| Optional future persisted reuse | Version the fingerprint/artifacts and invalidate unknown/mismatched versions; preserve paused and failed saves |
| All optional optimizations disabled | Preserve existing signatures, graph routing, trace accounting and best-candidate selection |

- Disabled optimizations reproduce current behavior; no live project settings change by default.
- Compact issues retain all critical defects and relevant cross-chunk/global context.
- Only exact complete request identity reuses a completed audit; any input/schema/model/context change invalidates it.
- Cache hits and local NLP record zero new API tokens and separate local/reuse events; no double-counted original usage.
- Preflight clear failures reach the existing repair path; no positive NLP report creates a semantic pass.
- Local model failure, uncertain alignment, invalid spans and unsupported contexts fall back visibly.
- Cancellation works before/after local operations, checkpoints remain resumable, and best-candidate guards remain intact.
- Final accepted-chapter quality meets the declared margin and measured net cost improves after all retries and serving costs.

The workflow's stop check is at [workflow.py:295](../src/nousetsu/graph/workflow.py#L295), review routing at [workflow.py:256](../src/nousetsu/graph/workflow.py#L256), and best-candidate selection at [workflow.py:644](../src/nousetsu/graph/workflow.py#L644). Preserve these semantics. Persistent cache/schema migrations, production route changes and new public configuration interfaces are future implementation work, not changes made by this report.

### Avoid unsafe shortcuts

Current bilingual chunk pairing is proportional by line position, not a validated semantic aligner: [critic.py:85](../src/nousetsu/agents/critic.py#L85). Therefore changed-lines-only critique is later work requiring alignment confidence and full-review fallback. A small edit can change who acted or spoke elsewhere in a scene.

Chronicler already reads only the first 12,000 characters: [chronicler.py:172](../src/nousetsu/agents/chronicler.py#L172). The inspected final chapters are all below this limit (maximum 9,654 characters), so clipping loss is not demonstrated in this workload. Shortening it further can lose endings and state changes in longer future chapters. Summarization/arc synthesis remains semantic, and its correctness matters to subsequent chapters. Do not use an NLP pass to delete unseen narrative state or prune character context without evidence.

## Next decision

The first experiment is **lower critic reasoning**, measured against the current pipeline. The next implementation candidates are compact critic feedback, shared deterministic preflight and exact chapter-local audit reuse. A BF16-LoRA 4B critic should follow only after reviewed multilingual data and a funded, bounded experiment exist. Keep local reranking as an optional RAG-enabled-project improvement, and candidate entity extraction/aligned delta review as separate evaluated extensions.
