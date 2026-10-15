# Uncensored models for literary translation: evidence, deployment, and cost

Research checked **2026-10-16, Asia/Bangkok**. This is a source-based comparison and a future evaluation design. **No candidate models were run, no translations were generated, and no GPU was rented for this report.** Model quality on this novel is therefore unknown.

## Reading guide and conclusion

- [Candidate inventory](#candidate-inventory) gives exact uncensored checkpoints and their parent controls.
- [Deployment feasibility](#deployment-feasibility) separates model context specifications from a usable single-GPU deployment.
- [Published translation evidence](#published-translation-evidence) distinguishes actual translation results from general benchmarks.
- [Twenty translation directions](#twenty-translation-directions) records what evidence exists for every ordered language pair.
- [Project cost comparison](#project-cost-comparison) uses the project's recorded workload, with explicitly hypothetical self-hosted throughput.
- [Future 240-case comparison](#future-240-case-comparison) describes the controlled trial required to choose a model.

**Trial priority:** begin with Qwen3.5 9B and its Huihui derivative for a relatively inexpensive multilingual pair; use Qwen3 14B as a middle-size control, then probe Qwen3.5 27B / Qwen3.8 27B and Qwen3.5 / Qwen3.6 35B-A3B only after a quantized deployment passes the 24GB memory gate. These are priorities for collecting evidence, not quality winners. Keep a specialized translation model such as TranslateGemma as a standard, unmodified control.

The deployment constraint is **one 24GB RTX 4090 with all inference weights and state on that GPU**. CPU weight offload, disk offload, additional GPUs, and hardware with more VRAM cannot be used to establish a pass. CPU orchestration and tokenization are permitted. A model advertised as “uncensored” can still refuse, omit, sanitize, repeat, or mistranslate text; the claim must be evaluated independently of fidelity.

## Evidence rules

| Label | Meaning in this report |
|---|---|
| Published result | A model publisher or research paper reports an actual measurement, with its dataset and metric. |
| Publisher claim | A checkpoint card claims a property; this is not an independent test. |
| Architecture support | The inference engine documents the underlying architecture or quantization method. |
| Estimate | Arithmetic or a planning assumption; not measured candidate performance. |
| Unknown | No suitable direct evidence found in the sources checked. |
| Future trial | A proposed experiment; there are no results yet. |

General reasoning, coding, role-play, or multilingual knowledge scores do not prove literary translation quality. Results from the original model do not establish that an abliterated or quantized derivative retains that result. Different translation metrics and different benchmark subsets must not be combined into a single numerical leaderboard.

### Source freshness and revision handling

The linked model cards were opened during this research. Most links use live `main`; **this report is not an immutable checkpoint manifest**. Attempts to obtain complete Hugging Face API metadata from the local environment failed because its network DNS was unavailable. Some official model pages also returned a browser verification page, so this report leaves their unverified details unknown rather than substituting community claims.

Before a future trial, capture the full SHA for model, tokenizer, chat template and quantization, the runtime/container digest, and the exact license files. Do not treat a displayed file commit as the full current repository revision. This matters for [Huihui Qwen3.8 27B](https://huggingface.co/huihui-ai/Huihui-Qwen3.8-27B-abliterated): its card describes a changed selection of ablated layers and a previous revision `d42ca89`, while claiming MTP and vision were left unchanged. That is a method change, not proof of unchanged translation quality.

## Candidate inventory

Bands use the marketed **language-model** count; multimodal encoders, MTP heads, and rounding can make Hugging Face's tensor count larger. MoE total parameters determine weight residency; active parameters describe only the portion used per token. A 35B-A3B model does not have a 3B weight-memory requirement.

At most two uncensored candidates are listed per band. Original parent checkpoints are controls, not additional uncensored candidates. “Apache 2.0, card” below means the badge/card was read; a direct license link is given where its text was accessible. License uncertainty of a conversion remains a trial gate.

| Band | LM total / active parameters | Exact uncensored checkpoint and original control | Method and license evidence | Initial trial priority |
|---|---|---|---|---|
| 1–4B | ~2B / ~2B dense | [`huihui-ai/Huihui-Qwen3.5-2B-abliterated`](https://huggingface.co/huihui-ai/Huihui-Qwen3.5-2B-abliterated); parent [`Qwen/Qwen3.5-2B`](https://huggingface.co/Qwen/Qwen3.5-2B) | Publisher identifies abliteration; [Apache 2.0 license text](https://huggingface.co/huihui-ai/Huihui-Qwen3.5-2B-abliterated/blob/main/LICENSE). | Lower-size floor; test whether it can preserve complete meaning at all. |
| 1–4B | ~4B / ~4B dense | [`huihui-ai/Huihui-Qwen3.5-4B-abliterated`](https://huggingface.co/huihui-ai/Huihui-Qwen3.5-4B-abliterated); parent [`Qwen/Qwen3.5-4B`](https://huggingface.co/Qwen/Qwen3.5-4B) | Card says **TRL fine-tuning**, using non-thinking data, not merely refusal-direction removal. Apache 2.0, card. Weight names changed and **MTP weights are absent**. | Small translation candidate after loader compatibility is confirmed. |
| 7–9B | ~9B / ~9B dense | [`huihui-ai/Huihui-Qwen3.5-9B-abliterated`](https://huggingface.co/huihui-ai/Huihui-Qwen3.5-9B-abliterated); parent [`Qwen/Qwen3.5-9B`](https://huggingface.co/Qwen/Qwen3.5-9B) | Publisher identifies abliteration; [Apache 2.0 license text](https://huggingface.co/huihui-ai/Huihui-Qwen3.5-9B-abliterated/blob/main/LICENSE). | First multilingual paired trial. |
| 7–9B | ~8B / ~8B dense | [`dphn/Dolphin3.0-Llama3.1-8B`](https://huggingface.co/dphn/Dolphin3.0-Llama3.1-8B); parent [`meta-llama/Llama-3.1-8B`](https://huggingface.co/meta-llama/Llama-3.1-8B) | Publisher describes steerable alignment and fine-tuning; Llama 3.1 community license, not Apache. Card uses ChatML. | Independent-family exploratory control; weaker direct coverage evidence for this five-language task. |
| 12–14B | 14.8B / 14.8B dense | [`huihui-ai/Huihui-Qwen3-14B-abliterated-v2`](https://huggingface.co/huihui-ai/Huihui-Qwen3-14B-abliterated-v2); parent [`Qwen/Qwen3-14B`](https://huggingface.co/Qwen/Qwen3-14B) | Publisher identifies updated abliteration; Apache 2.0, card. Official parent has 14.8B actual parameters. | Middle-size comparison; quantify what is gained over 9B. |
| 24–28B dense | ~27B / ~27B dense | [`huihui-ai/Huihui-Qwen3.5-27B-abliterated`](https://huggingface.co/huihui-ai/Huihui-Qwen3.5-27B-abliterated); parent [`Qwen/Qwen3.5-27B`](https://huggingface.co/Qwen/Qwen3.5-27B) | Publisher identifies abliteration; Apache 2.0, card. | Established-generation large dense control, conditional on 4-bit fit. |
| 24–28B dense | ~27B / ~27B dense | [`huihui-ai/Huihui-Qwen3.8-27B-abliterated`](https://huggingface.co/huihui-ai/Huihui-Qwen3.8-27B-abliterated); parent [`Qwen/Qwen3.8-27B`](https://huggingface.co/Qwen/Qwen3.8-27B) | Publisher identifies partial-layer abliteration; [Apache 2.0 license text](https://huggingface.co/huihui-ai/Huihui-Qwen3.8-27B-abliterated/blob/main/LICENSE). | Newer-generation comparison; no automatic preference over 3.5. |
| 26–35B MoE | ~35B / ~3B MoE | [`huihui-ai/Huihui-Qwen3.5-35B-A3B-abliterated`](https://huggingface.co/huihui-ai/Huihui-Qwen3.5-35B-A3B-abliterated); parent [`Qwen/Qwen3.5-35B-A3B`](https://huggingface.co/Qwen/Qwen3.5-35B-A3B) | Publisher identifies abliteration; [Apache 2.0 license text](https://huggingface.co/huihui-ai/Huihui-Qwen3.5-35B-A3B-abliterated/blob/main/LICENSE). Parent is 35B total / 3B active. | Requested MoE cost/quality baseline, conditional on 4-bit fit. |
| 26–35B MoE | ~35B / ~3B MoE | [`huihui-ai/Huihui-Qwen3.6-35B-A3B-abliterated`](https://huggingface.co/huihui-ai/Huihui-Qwen3.6-35B-A3B-abliterated); parent [`Qwen/Qwen3.6-35B-A3B`](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) | Publisher identifies abliteration; Apache 2.0, card. [vLLM recipe](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html) identifies 35B / 3B active. | Newer MoE comparison using the same feasibility gate. |

Qwen's [3.5 4B official card](https://huggingface.co/Qwen/Qwen3.5-4B) claims 201 languages/dialects at family level. [Qwen3's official card](https://huggingface.co/Qwen/Qwen3-14B) claims 100+ and translation capability. These broad claims are insufficient to rank EN, ZH, KO, JA, or TH. An uncensored card's inheritance from a multilingual parent is an investigation lead, not direct language-quality evidence.

### Required standard reference points

These comparison controls are separate from the uncensored shortlist. An original instruction model and its quantization must not be relabeled as uncensored.

| Reference | Total / active LM parameters | Artifact and license evidence | Runtime / context / 24GB status |
|---|---|---|---|
| Gemini 3.1 and 3.5 Flash-Lite | Undisclosed proprietary parameter counts | API model IDs `gemini-3.1-flash-lite` and `gemini-3.5-flash-lite`; hosted service controls, not downloadable weights. [Official API pricing](https://ai.google.dev/gemini-api/docs/pricing). | Existing recorded JA→TH results only; not vLLM or single-GPU deployments. Other nineteen directions remain unmeasured here. |
| Qwen3.5 35B-A3B GPTQ-Int4 | ~35B total / ~3B active | Exact official checkpoint [`Qwen/Qwen3.5-35B-A3B-GPTQ-Int4`](https://huggingface.co/Qwen/Qwen3.5-35B-A3B-GPTQ-Int4/raw/main/README.md), Apache 2.0 per official card/license link; GPTQ 4-bit, not an uncensored quantization. | Publisher documents vLLM compatibility. Native specification 262,144 total tokens; propose 8,192 initially, never assume full-context 24GB fit. [Config](https://huggingface.co/Qwen/Qwen3.5-35B-A3B-GPTQ-Int4/raw/main/config.json) declares one MTP layer and leaves MTP/attention/shared experts/vision outside quantization, so ideal 17.5GB arithmetic understates its footprint. Full GPU residency and quantized MTP execution remain unmeasured here. |
| Gemma 4 26B A4B IT | Marketed ~26B total / ~4B active | Original [`google/gemma-4-26B-A4B-it`](https://huggingface.co/google/gemma-4-26B-A4B-it), with official [QAT q4_0 GGUF](https://huggingface.co/google/gemma-4-26B-A4B-it-qat-q4_0-gguf). Official GGUF card declares Apache 2.0; inspect exact artifact terms before deployment. | Original architecture and MTP assistant supported by vLLM. No quality-preserving 24GB vLLM configuration is established in this report; see the format-specific quantization warning below. |

### Gemma uncensored reference

[`huihui-ai/Huihui-gemma-4-26B-A4B-it-abliterated`](https://huggingface.co/huihui-ai/Huihui-gemma-4-26B-A4B-it-abliterated) explicitly derives from `google/gemma-4-26B-A4B-it`; the card declares Apache 2.0 and links Google's Gemma 4 license. Parent license text could not be retrieved during this check, so the badge alone does not resolve inherited terms or a conversion's terms. Audit the [parent LICENSE](https://huggingface.co/google/gemma-4-26B-A4B-it/blob/main/LICENSE) before deployment. The derivative says the first five layers were retained and expert weights were not ablated. It remains a comparison reference rather than a third MoE shortlist candidate because **a suitable quality-preserving, fully resident 24GB vLLM deployment has not been established**. Its official MTP assistant is `google/gemma-4-26B-A4B-it-assistant`; architecture support does not validate the altered target and assistant together. [Publisher card](https://huggingface.co/huihui-ai/Huihui-gemma-4-26B-A4B-it-abliterated), [vLLM Gemma 4 recipe](https://docs.vllm.ai/projects/recipes/en/latest/Google/Gemma4.html).


## Deployment feasibility

### Precision, context, and support ledger

“Proposed precision” is a trial configuration, not a downloaded or validated conversion. A row without an exact audited 4-bit repository must not be represented as deployment-ready. Do not use the official original model's GPTQ checkpoint as if it were a quantization of an uncensored descendant.

| Candidate | Proposed precision | Family context versus proposed deployment context | vLLM / MTP status | Single-4090 status |
|---|---|---|---|---|
| Huihui Qwen3.5 2B | BF16 first | Qwen3.5 family advertises 262,144 native; verify this exact config. Trial: 8,192 total, later 16,384. | Architecture supported; exact target/MTP-weight compatibility unverified. MTP off initially. | Plausible from weight arithmetic; unmeasured. |
| Huihui Qwen3.5 4B | BF16 first | Parent advertises 262,144 native / ~1M extended. Trial: 8,192, later 16,384. | Renamed weights require loader probe; **MTP absent in derivative**. | Plausible memory; compatibility unvalidated. |
| Huihui Qwen3.5 9B | BF16 first; separate 4-bit deployment comparison if needed | Verify derivative config; trial 8,192, later 16,384. Family maximum is not a 24GB guarantee. | Qwen3.5 engine support; derivative quantization/MTP unverified. | BF16 weight memory leaves modest cache/runtime headroom; unmeasured. |
| Dolphin 8B | BF16 first | Parent/card 131,072 specification; trial 8,192, later 16,384. | Llama architecture supported, but ChatML template required. No native MTP claim established. | Plausible; unmeasured. |
| Huihui Qwen3 14B v2 | Matching W4A16 conversion for both paired models | Parent: 32,768 native, 131,072 with YaRN; trial 8,192, later 16,384. | Qwen3 supported; no native MTP checkpoint established. Conversion must pass loader probe. | Quantization required for meaningful headroom; unmeasured. |
| Huihui Qwen3.5 27B | W4A16 | Parent family 262,144 native; trial 8,192, then 16,384 only if it fits. | Example publisher conversion below preserves MTP; not a 4090 validation. | Conditional; reject if full workload needs CPU offload. |
| Huihui Qwen3.8 27B | W4A16, conversion not yet selected | Exact parent/config context not verified here; trial 8,192 then 16,384. | Card claims preserved MTP. Engine architecture and conversion still need validation. | Conditional; no measured 4090 result. |
| Huihui Qwen3.5 35B-A3B | W4A16, conversion not yet selected | Parent advertises 262,144 native; trial 8,192, later 16,384 if it fits. | Qwen3.5 support; altered target, quantization and MTP pairing unverified. | Tight 4-bit weight/cache budget; conditional. |
| Huihui Qwen3.6 35B-A3B | W4A16, conversion not yet selected | Exact derivative context unverified; trial 8,192, later 16,384. | Official recipe documents original architecture and MTP; derivative pairing unverified. | Conditional; no measured 4090 result. |
| Gemma4 26B-A4B reference | INT8 recommended by engine; Q4 experimental | Trial only after memory/quality gate; no 24GB context promise. | Original model and assistant supported; altered/quantized pairing unverified. | Not established within constraint; INT8 weights may already exceed budget. |

Context/support sources: [Qwen3 official card](https://huggingface.co/Qwen/Qwen3-14B), [Qwen3.5 4B card](https://huggingface.co/Qwen/Qwen3.5-4B), [Qwen3.5 35B card](https://huggingface.co/Qwen/Qwen3.5-35B-A3B?library=transformers), [Dolphin card](https://huggingface.co/dphn/Dolphin3.0-Llama3.1-8B), [vLLM Qwen recipe](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html), [vLLM quantization compatibility](https://docs.vllm.ai/en/latest/features/quantization/).

BF16 arithmetic is approximately `2 × parameter count` bytes; ideal 4-bit arithmetic is `0.5 × parameter count`. For marketed 2/4/8/9/14.8/27/35B counts this is roughly 4/8/16/18/29.6/54/70GB BF16 or 1/2/4/4.5/7.4/13.5/17.5GB ideal 4-bit, respectively. These are **lower-bound planning calculations**, not actual safetensor sizes or VRAM measurements: scales, unquantized modules, embeddings, multimodal components, MTP heads, allocator reserve, activation buffers and KV/recurrent state add memory. Decimal GB also differs from GiB.

### Quantization and MTP cautions that affect this comparison

The [vLLM Gemma 4 recipe](https://docs.vllm.ai/projects/recipes/en/latest/Google/Gemma4.html) specifically excludes 26B-A4B MoE from its QAT W4A16 list because its small experts incur excessive quality loss. It recommends online INT8 per-channel weight-only quantization. This warning concerns that vLLM W4A16 route, **not every 4-bit format**: Google also publishes an official [QAT q4_0 GGUF checkpoint](https://huggingface.co/google/gemma-4-26B-A4B-it-qat-q4_0-gguf), which uses a different deployment path and requires a matching assistant precision for MTP. Its existence does not validate an uncensored vLLM conversion. Earlier chat estimates based on community Gemma Q4 speed should not be treated as quality-preserving cost measurements. A [Gemma NVFP4 conversion publisher](https://huggingface.co/sakamakismile/Huihui-gemma-4-26B-A4B-it-abliterated-NVFP4) additionally reports repetition collapse in long Japanese generation; this concerns that Blackwell conversion, not every 4090 quantization.

An exact candidate conversion exists at [`j-a-a-a-y/Huihui-Qwen3.5-27B-abliterated-AWQ-W4A16`](https://huggingface.co/j-a-a-a-y/Huihui-Qwen3.5-27B-abliterated-AWQ-W4A16): the publisher describes text-only AWQ, 18.6GB on disk, an included BF16 MTP head, and vLLM usage. Its benchmark uses an **RTX 5090**, and its card reports lower MTP acceptance than its GPTQ alternative. Its license badge is `other`, so its own license and inherited terms must be audited before adoption. This is evidence of a conversion, not of quality or 4090 fit.

The [vLLM Qwen guide](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html) warns that MTP can reduce throughput at high concurrency. The guide's verified deployments use much larger GPU configurations. A generic Hugging Face “serve with vLLM” snippet confirms neither memory fit nor a working quantized MTP implementation.

For a later runtime probe, begin with text-only loading, concurrency 1, MTP off, and 8,192 total tokens. Increase to 16,384 and concurrency 2/4 only after memory measurements. Never silently trim source or glossary to make a model pass. If a common test does not fit, report unsupported for that workload; do not compare a truncated answer against complete answers.

## Published translation evidence

### Original Qwen results: relevant but not uncensored results

The original Qwen3.5 publisher reports WMT24++ scores using **XCOMET-XXL on a harder, rebalanced subset**, averaged across 55 languages. The published values are 4B **66.6**, 9B **72.6**, 27B **77.6**, and 35B-A3B **76.3**. These are direct translation-task results for the original models, not Huihui variants, not per-language rankings, and not measurements of long novel chapters or 4-bit deployment. [4B/9B official table and metric definition](https://huggingface.co/Qwen/Qwen3.5-4B/raw/main/README.md), [27B/35B official table and metric definition](https://huggingface.co/Qwen/Qwen3.5-35B-A3B/raw/main/README.md).

No comparable published twenty-direction literary translation results were established for the exact uncensored shortlist. Newer model names, higher parameter counts, broad multilingual benchmarks and download counts cannot fill those cells. The trial must measure each exact derivative.

### Specialized standard control: TranslateGemma versus Gemma 3

TranslateGemma is a translation-specialized family, **not an uncensored checkpoint claim**. Its paper provides a useful standard-model control with real direction-specific evidence. Table 4 reports the following **MetricX scores, lower is better**. Size columns are always 27B / 12B / 4B. [TranslateGemma technical report, v3, Table 4](https://arxiv.org/pdf/2601.09012v3).

| Direction | TranslateGemma 27B / 12B / 4B | Gemma 3 parent 27B / 12B / 4B |
|---|---:|---:|
| EN → JA | 3.53 / 3.82 / 4.44 | 4.11 / 4.30 / 5.09 |
| EN → KO | 2.81 / 2.97 / 3.93 | 3.43 / 3.79 / 4.72 |
| EN → TH | 2.33 / 2.66 / 3.49 | 2.96 / 3.19 / 4.14 |
| EN → ZH, simplified | 1.86 / 2.07 / 2.66 | 2.47 / 2.61 / 3.27 |

The same report's human MQM results also show why automatic aggregate gains cannot be generalized: EN→KO is 3.1 / 4.6 / 3.8 and EN→ZH is 6.3 / 8.4 / 7.4 for TranslateGemma 27B / TranslateGemma 12B / Gemma 3 27B, respectively. For JA→EN the corresponding values are **13.4 / 15.7 / 11.6**, a regression, with named-entity errors discussed. MQM is lower-is-better. These published samples are not full-chapter continuity tests. [Report, human evaluation](https://arxiv.org/pdf/2601.09012v3).

Do not compare these MetricX values numerically against Qwen's XCOMET values. WMT24++ covers English-to-55-language directions; it is not evidence for all reverse or non-English pairs. [Dataset publisher](https://huggingface.co/datasets/google/wmt24pp).

## Twenty translation directions

EN = English, ZH = Chinese, KO = Korean, JA = Japanese, TH = Thai. The trial uses simplified Chinese as the default ZH target and records source script; traditional Chinese requires a separately declared condition. “Unknown” is an evidence status, not a prediction of bad quality. All rows require native or bilingual review.

`TG-MX` = TranslateGemma/Gemma3 published MetricX comparison above; `TG-MQM` = published human comparison. Qwen's aggregate translation scores remain aggregate-only evidence and are not assigned to individual directions. Sources for these tags are the [TranslateGemma report](https://arxiv.org/pdf/2601.09012v3) and [WMT24++ dataset](https://huggingface.co/datasets/google/wmt24pp).

| # | Direction | Direct direction-specific standard-control evidence found | Exact uncensored comparative quality | Trial focus |
|---:|---|---|---|---|
| 1 | EN → ZH | TG-MX and TG-MQM | Unknown | Natural narration, names, simplified script |
| 2 | EN → KO | TG-MX and TG-MQM | Unknown | Speech levels and relationship register |
| 3 | EN → JA | TG-MX | Unknown | Address forms, subject omission, natural prose |
| 4 | EN → TH | TG-MX; separate MEET-MR evaluation resource | Unknown | Pronouns, particles, names, Thai phrasing |
| 5 | ZH → EN | No directly comparable result established here | Unknown | Names, idioms, omitted subjects |
| 6 | ZH → KO | No directly comparable result established here | Unknown | Names, rank/address terms, speech level |
| 7 | ZH → JA | No directly comparable result established here | Unknown | False friends, names, register |
| 8 | ZH → TH | No directly comparable result established here | Unknown | Terminology, pronouns, idioms |
| 9 | KO → EN | No directly comparable result established here | Unknown | Honorifics, omitted subjects, dialogue voice |
| 10 | KO → ZH | No directly comparable result established here | Unknown | Social roles, names, source omissions |
| 11 | KO → JA | No directly comparable result established here | Unknown | Register transfer and address forms |
| 12 | KO → TH | No directly comparable result established here | Unknown | Speech levels, Thai pronouns and particles |
| 13 | JA → EN | TG-MQM, including regression described above | Unknown | Named entities, zero anaphora, voice |
| 14 | JA → ZH | No directly comparable result established here | Unknown | Names, false friends, narrative subject |
| 15 | JA → KO | No directly comparable result established here | Unknown | Address forms and relationship register |
| 16 | JA → TH | No directly comparable result established here | Unknown | Project-relevant names, pronouns, omissions |
| 17 | TH → EN | No directly comparable result established here | Unknown | Implicit subjects, names, idioms |
| 18 | TH → ZH | No directly comparable result established here | Unknown | Pronouns, particles and culturally specific terms |
| 19 | TH → KO | No directly comparable result established here | Unknown | Register and relationship mapping |
| 20 | TH → JA | No directly comparable result established here | Unknown | Pronouns, particles, names and dialogue voice |

## Project cost comparison

The existing `Isekai Tenshou Shitanode Honmono Nokukkoroga Mita I !` workload supplies a useful scale, not a measured self-hosted workload. Local trace/metadata reconciliation found **127 unique completed chapters**, with duplicate alias entries excluded, and **1,118 traces**: 1,097 successes, 20 safety-blocked attempts and one error. There are 159 raw chapters, so these calculations are not the cost of finishing every raw chapter.

| Recorded token category | Tokens | Interpretation |
|---|---:|---|
| Input | 8,837,363 | Includes cached input below |
| Cached input | 1,309,902 | A subset of input; never add it to input again |
| Visible output | 1,306,320 | Published text and other visible stage outputs |
| Thought/reasoning | 3,690,136 | Generated tokens that also consume time / output billing |
| All generated | 4,996,456 | Visible output + thoughts |
| Input + all generated | 13,833,819 | Does not add cached tokens twice |

Local sources are `.novel/metadata.json`, `.novel/config.yaml`, and the 127 `.novel/traces/raw_chapters/chapter_*.json` files under that project. Metadata contains 254 records representing 127 identical alias pairs; group by source path before counting chapters. Token/cost sums use unique `trace_id` records, including additional calls absent from stage aggregates. Unknown or unrecorded billing cannot be reconstructed.

The recorded standard Gemini mix has a **$12.5793 paid-list-price equivalent**, not a recovered payment invoice. It includes model-specific input/cache prices and generated reasoning charges. Trace allocations are Gemini 3.1 Flash-Lite $4.013256325 and Gemini 3.5 Flash-Lite $8.56604007. Free-tier use or other contract pricing can change the actual payment. Critique accounts for about $7.00836, roughly 56% of this estimate. [Google API pricing](https://ai.google.dev/gemini-api/docs/pricing).

### Reproducible Gemini calculation

Prices below are USD per million tokens at the checked standard API rates. Cached tokens are already part of the input count.

| Recorded model | Input | Visible output | Reasoning | Cached input | Input / generated / cached rate | Cost |
|---|---:|---:|---:|---:|---:|---:|
| Gemini 3.1 Flash-Lite | 4,094,614 | 832,480 | 1,177,131 | 110,283 | $0.25 / $1.50 / $0.025 | $4.0133 |
| Gemini 3.5 Flash-Lite | 4,742,749 | 473,840 | 2,513,005 | 1,199,619 | $0.30 / $2.50 / $0.03 | $8.5660 |
| Total | 8,837,363 | 1,306,320 | 3,690,136 | 1,309,902 | Per-model calculation | **$12.5793** |

For each model, `cost = ((input - cached) * input_rate + cached * cached_rate + (visible_output + reasoning) * output_rate) / 1,000,000`. Apply rates separately before summing. Cache storage, tax, non-trace services, and any unrecorded calls are excluded. This prices the recorded calls; it is not a prediction of what another model would generate. [Official standard pricing](https://ai.google.dev/gemini-api/docs/pricing).

For the same fixed token workload, pricing every stage as Gemini 3.1 Flash-Lite would give **$9.4093**, or every stage as Gemini 3.5 Flash-Lite **$14.7887**. Neither assumes unchanged quality after a real model substitution. Reasoning is **73.86% of all generated tokens**; lowering it is a cost hypothesis that requires quality evaluation.

### Self-hosted sensitivity, not per-model benchmark prices

The following calculations reuse Gemini's token counts only to illustrate scale. Each candidate tokenizer, reasoning policy, number of retries, and output length can differ. Cached input is still included in the conservative prefill total; the table assumes no self-hosted cache savings.

`GPU hours = 1.15 × [input_tokens / input_tokens_per_second + generated_tokens / output_tokens_per_second] / 3600`

The 15% multiplier is an assumed allowance for startup and execution overhead, not observed overhead. When actual billed startup is known, replace that allowance rather than adding it twice. Add any model download time or idle periods beyond the allowance, storage, evaluator costs, and tax separately. Price columns use $0.34/hour as the advertised Community sensitivity and $0.89/hour as the rate visible on the public RTX 4090 pricing listing when checked. They are not verified available offers in the user's account; check the actual deployment quote. Different 24GB GPUs cannot reuse RTX 4090 throughput assumptions. [RunPod RTX 4090](https://www.runpod.io/gpu-models/rtx-4090), [RunPod pricing](https://www.runpod.io/pricing).

| Assumed output / input throughput | Estimated GPU hours | At $0.34/hour | At $0.89/hour |
|---|---:|---:|---:|
| 80 / 800 tokens/s | 23.48 | $7.98 | $20.90 |
| 150 / 1,500 tokens/s | 12.52 | $4.26 | $11.15 |
| 250 / 3,000 tokens/s | 7.33 | $2.49 | $6.52 |

These rows cannot be labeled Gemma, Qwen, or a particular size without a workload measurement. In particular, format-specific Gemma quantization concerns and the tight 35B memory budget can invalidate an optimistic speed assumption. The relevant final comparison is **dollars per accepted chapter at a stated quality level**, not just dollars per million visible tokens.

At the recorded Gemini equivalent, the break-even limit is **14.13 billed GPU hours at $0.89/hour**, or **37.00 hours at $0.34/hour**, before extra charges. Under the table's 1,500 input tokens/s and 15% allowance, generation must exceed approximately **130.27 tokens/s** at $0.89/hour or **45.45 tokens/s** at $0.34/hour. These are workload-specific arithmetic thresholds, not measured performance of any model.

## Future 240-case comparison

This section specifies future work. It does not authorize a rental, model download, paid API call, or translation run by itself. Produce the benchmark set and immutable execution manifest before spending compute.

### Corpus and fair inputs

1. Select **12 original passages per source language = 60 sources**; translate each into the other four languages, producing **240 case-direction records per checkpoint**. Cases are native sources, not machine back-translations of one English seed. Use public-domain, licensed, or user-provided material and retain provenance. Four target records share one source; preserve that dependence in statistics.
2. Each source-language set contains exactly two passages in each of six categories: **narration, dialogue, cultural expressions, pronouns/register, terminology, and sensitive adult fiction**. Sources are 300–600 Unicode characters each. This length rule does not make difficulty or meaning density equal across languages. Tag two of the twelve per source language with matched preceding context to examine continuity without adding main cases.
3. Use identical source, static case-specific context/glossary and output contract across candidates. Budget using every candidate's tokenizer; choose passages that fit all eligible deployments. Never substitute a family maximum for a demonstrated context length. A separate shortlisted **32K total-context full-chapter fitness probe** is later work, outside the 240-case screening set and outside this document-only research.
4. For JA→TH, sample the existing novel's raw passages and relevant frozen Bible/context. Existing Gemini output is a comparator, **not a human reference**. Keep evaluation copies outside live production memory; do not update the Novel Bible or checkpoints during the trial.
5. Store each record's ID, language/script pair, provenance, scene type, source/context/glossary, length, expected entities/numbers, and any human reference separately. A reference is optional; it must never appear in the generation prompt.

### Execution stages and controls

- **Feasibility gate:** audit licenses and exact revisions; verify architecture, loader, chat template, EOS and actual GPU residency. Test short and maximum-profile inputs. Record peak VRAM, driver/CUDA/vLLM versions and failure details. OOM, missing MTP head, incompatible conversion, and offload are explicit outcomes, not discarded observations.
- **Paired model comparison:** compare each uncensored descendant with its declared parent. Dolphin is an exception to an instruction-parent pairing: its card declares the pretrained `meta-llama/Llama-3.1-8B` base, so the comparison measures instruction fine-tuning as well as alignment. Retain that lineage control and use `meta-llama/Llama-3.1-8B-Instruct` as an additional operational comparator; do not call either a pure ablation experiment. [Dolphin original metadata](https://huggingface.co/dphn/Dolphin3.0-Llama3.1-8B/raw/main/README.md). Use the same prompt semantics and deployment context, and identical precision/calibration where feasible. TRL fine-tuning in Huihui 4B makes that pair a fine-tuning comparison, not a pure abliteration experiment. Mismatched quantization makes a pair a deployment comparison rather than a causal estimate of abliteration.
- **Initial quality trial:** concurrency 1, MTP off, no warm prefix cache, and thinking disabled where a supported hard switch exists. Record decoding parameters; use each family's documented non-thinking recommendations and fixed seeds where available. A model without a hard thinking switch must be marked as a different condition rather than silently pooled. Use native EOS and a 2,048-token output cap; hitting the cap is a truncation failure, not an accepted translation. Record prompt-processing and full-generation time separately.
- **Optimization trial:** on quality-acceptable finalists, compare MTP off/on only when heads exist and the exact configuration is supported; then test concurrency 1/2/4, text-only loading and prefix caching. Measure complete workload throughput including prefill. Keep latency and aggregate throughput separate.
- **Pipeline follow-up:** the 240-case first pass tests translation, not every agent role. Only after selection run an isolated copied-project pilot across the five stages, with fixed review limits and no live production writes. That later pilot measures accepted-chapter cost, structured-output failures and correction loops.

### Evaluation and acceptance

Use **two blinded bilingual raters with adjudication** as the decision anchor. Reviewers see source, supplied context and glossary but not model names; randomize output order. Score fidelity/omissions/additions, terminology/names/pronouns, target fluency, register/voice, continuity and formatting. Record specific source/target error spans and minor/major/critical severity. Separately flag refusal, warnings, unwanted sanitization, invented explicitness, truncation, repetition and language mixing. A faithful uncensored translation should preserve what is present without adding content. [MQM human-evaluation methodology](https://github.com/google/wmt-mqm-human-evaluation).

For every direction, report per-stratum case counts, paired preference win/tie/loss, error rates and uncertainty; report size and dense/MoE category separately. Macro-average the twenty directions with equal weight. Bootstrap by independent source case, not by treating four translations of one source as independent samples. Twelve cases per direction are a screening set, insufficient for a universal language ranking; enlarge close comparisons before choosing a deployment.

Automated support can include reference-free COMETKiwi, entity/number/glossary checks and alignment diagnostics. The official COMET project lists all five languages in encoder coverage and offers reference-free evaluation, but that does not prove Thai literary validity. COMETKiwi weights use CC-BY-NC-SA although COMET software is Apache; check intended-use compatibility before selecting an evaluator. [COMET documentation](https://github.com/Unbabel/COMET), [model license table](https://github.com/Unbabel/COMET/blob/master/LICENSE.models.md).

For a separate public reference-based sanity set, [FLORES+](https://huggingface.co/datasets/openlanguagedata/flores_plus) provides aligned references covering the requested languages. Check access and CC-BY-SA conditions before use. Its largely English-origin nonfiction is not a native literary corpus; translated source versions can introduce translationese. Keep its results separate from the 240 native-source literary cases. Run evaluator models after unloading the generator so their memory is not added to the 24GB inference budget.

For EN→TH, [MEET-MR](https://aclanthology.org/2026.eacl-short.41/) supplies human MQM annotations, preferences and references across nine domains and can calibrate an evaluator. It does not establish JA/ZH/KO→TH literary validity. An LLM judge must be blinded and calibrated against bilingual judgments; avoid having a candidate grade itself. BLEU/chrF require references, and back-translation is a diagnostic rather than ground truth. Do not use whitespace-delimited Thai “word” counts; publish character-based lengths and any segmentation policy.

The selection gate is an explicit human-approved quality threshold on the held-out set, zero unresolved critical errors in the pilot, and a demonstrated memory/context pass. Once that gate is met, choose the least expensive measured deployment within each required direction or agent role. Preserve models that are better in different directions rather than forcing one global winner.

### Future result schema

Each run should record `case_id`, direction, model/parent/revision, quantization and calibration revision, runtime digest, prompt/template hash, context and output limits, decoding/thinking/MTP/concurrency settings, input/cache/visible/reasoning token counts, prefill and total wall time, GPU billing time/rate, peak VRAM/residency, output, failure/finish reason, automated diagnostics and blinded reviewer annotations. Report raw and retry-inclusive cost, failure rate, and cost per accepted case/chapter. Unrun or unsupported cells remain explicit rather than receiving estimated scores.

## Decisions supported now

| Band | What to try first | What remains unknown |
|---|---|---|
| 1–4B | 2B for the lower-cost floor; 4B after resolving its renamed weights | Fidelity, refusals and Thai quality; 4B MTP is unavailable in this derivative. |
| 7–9B | Qwen3.5 9B paired with its parent; Dolphin as family-diversity probe | Actual language-specific quality and BF16 context headroom. |
| 12–14B | Qwen3 14B v2 with an audited matching quantization | Benefit over 9B and degradation from quantization. |
| 24–28B dense | Compare Qwen3.5 and Qwen3.8 27B at an identical feasible profile | Exact conversion fit, new-generation benefit, real translation cost. |
| 26–35B MoE | Compare Qwen3.5 and Qwen3.6 35B-A3B if fully resident | Cache/concurrency capacity and actual MTP gain. Gemma26B remains a conditional reference. |

No current source supports a defensible claim that one uncensored checkpoint wins all twenty directions. The report supports an auditable shortlist, exposes deployment blockers and supplies a controlled route to results.
