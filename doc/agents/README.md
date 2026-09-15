# 🏛️ NouSetsu Agent Catalog & Technical Reference Hub

Welcome to the **NouSetsu Agent Catalog**. This directory provides individual, standalone technical references for each of the five specialized AI agents operating in the translation pipeline.

---

## 📑 The Five Specialized Pipeline Agents

Each agent in the pipeline is given an official German designation reflecting its precise literary role:

| Stage | Dedicated Specification | German Codename | Agent Class | Production Model | Primary Mission | RAG Role |
|:---:|:---|:---|:---|:---|:---|:---:|
| **1** | [**`01_entity_extractor.md`**](./01_entity_extractor.md) | **Schriftdetektiv** | [`EntityExtractorAgent`](file:///D:/Code/novel_translation_Agent/src/nousetsu/agents/extractor.py) | `gemini-3.1-flash-lite` | Pre-translation discovery of characters, factions, and cultivation realms. | Feeds Bible Terms |
| **2** | [**`02_drafter.md`**](./02_drafter.md) | **Wortschmied** | [`ContextAwareDrafterAgent`](file:///D:/Code/novel_translation_Agent/src/nousetsu/agents/drafter.py) | `gemini-3.5-flash-lite` | Context-aware initial draft, zero-anaphora pronoun resolution, character voice registers. | Inbound ($k=2$) |
| **3** | [**`03_critic.md`**](./03_critic.md) | **Zensor** | [`CritiqueAgent`](file:///D:/Code/novel_translation_Agent/src/nousetsu/agents/critic.py) | `gemma-4-26b-a4b-it` | Line-by-line fidelity & style auditor, omission detection, nickname disparity auditing. | Inbound TM ($k=2$) |
| **4** | [**`04_polisher.md`**](./04_polisher.md) | **Feinschliff** | [`PolishingAgent`](file:///D:/Code/novel_translation_Agent/src/nousetsu/agents/polisher.py) | `gemini-3.5-flash-lite` | Publication-grade prose polishing, translationese purging, prose cadence and emotional depth. | Indirect via Notes |
| **5** | [**`05_chronicler.md`**](./05_chronicler.md) | **Chronist** | [`ChroniclerAgent`](file:///D:/Code/novel_translation_Agent/src/nousetsu/agents/chronicler.py) | `gemma-4-26b-a4b-it` | 3-tier narrative memory (Micro, Meso, Macro), story arc tracking, telemetry compilation. | Bi-directional (Read $k=3$ / Write) |

---

## 🔄 Pipeline Workflow & Architecture Links

- **End-to-End Workflow**: Consult [`doc/workflow.md`](../workflow.md) for the LangGraph multi-agent execution graph, cyclic reflection review loops, and sequence diagrams.
- **System Architecture**: Consult [`doc/architecture.md`](../architecture.md) for the layered architecture, rate limiting, chunking, and fallback mechanisms.
- **Combined Agents Deep Dive**: Consult [`doc/agents_deep_dive.md`](../agents_deep_dive.md) for a single-file consolidated overview.
- **Operational Handbook**: Consult [`AGENTS.md`](file:///D:/Code/novel_translation_Agent/AGENTS.md) for coding standards, model cascades, and testing conventions.
