# 📱 NouSetsu Social Media Launch Kit

> **Ready-to-Post Copy, Hooks, Hashtags, and Community Threads**

---

## 🐦 1. X (Twitter) Launch Thread (High Engagement)

### Tweet 1 (Hook with Video/Banner)
> 🚨 AI light novel translation is notoriously broken:  
> • Pronouns vanish into thin air  
> • Names change spelling every 3 paragraphs  
> • Haughty villainesses sound like ancient kung-fu masters  
> 
> We fixed it.  
> 
> Meet **NouSetsu** 🐾: The open-source, document-level multi-agent novel translation system.  
> 
> 🧵👇 [Attach 60-Sec Short Video or promo_banner.jpg]  
> #MachineTranslation #LightNovel #LangGraph #AI #OpenSource #WebNovel

### Tweet 2 (The Multi-Agent Architecture)
> Single-prompt LLM translations collapse on 3,000-word chapters.  
> 
> NouSetsu orchestrates 5 specialized agents in a cyclic @LangChainAI LangGraph loop:  
> 1️⃣ Extractor: Discovers characters & cultivation realms before translation  
> 2️⃣ Drafter: Resolves zero-anaphora & character voice registers  
> 3️⃣ Critic: Line-by-line fidelity & style auditor (0-10)  
> 4️⃣ Polisher: Targeted diff-patch prose styling  
> 5️⃣ Chronicler: Updates rolling story memory

### Tweet 3 (3-Tier Memory & Hybrid RAG)
> Ever tried translating chapter 150 of an epic novel? Most AIs forget what happened in chapter 10.  
> 
> NouSetsu features **3-Tier Narrative Memory**:  
> 🌐 Macro: Overarching world milestones  
> 📖 Meso: Active story arc conflict tracking  
> 📄 Micro: Immediate preceding chapter summaries  
> 
> Backed by local SQLite Hybrid RAG (FTS5 + Gemini Embedding 2) with Cross-Encoder reranking. Zero narrative drift!

### Tweet 4 (Developer Experience & Docker)
> Run it your way:  
> 🖥️ Blazing fast terminal dashboard with Textual & Rich  
> 🌐 Modern Web Studio in React 19 + Vite with character dossiers & live diff viewer  
> 🐳 One-command launch with Docker Compose: `docker compose up -d`  
> 
> No API key? It includes a deterministic offline mock model for instant testing!

### Tweet 5 (Call to Action)
> 100% Open Source under MIT License.  
> 
> Give your favorite light novels and webnovels the translation quality they deserve:  
> ⭐ Star the repo: https://github.com/Checkmartyr/NouSetsu  
> 
> Feedback and PRs welcome nya~! (=^･ω･^=) ★

---

## 🔴 2. Reddit Post (r/LocalLLaMA & r/noveltranslations)

**Title**:  
`[P] NouSetsu: An Open-Source Document-Level Multi-Agent Translation Framework for Light Novels & Webnovels (LangGraph + 3-Tier Memory + Textual/Web Studio)`

**Post Body**:
```markdown
Hey everyone!

If you've ever tried machine-translating raw Japanese, Chinese, or Korean webnovels using standard single-prompt LLMs or Google Translate, you know the frustration:
- **Zero-Anaphora**: East Asian languages drop subjects/pronouns constantly. Traditional MT guesses blindly ("he/she/it" swap every sentence).
- **Voice Homogenization**: Every character ends up sounding like generic ChatGPT assistant prose.
- **Narrative Amnesia**: By chapter 50, the model has forgotten key plot events, character injuries, and established terminology.

Over the past few months, we've built **NouSetsu** (`novel_translation_Agent`) to solve document-level and cross-chapter literary translation from the ground up.

### 🌟 Key Highlights:
1. **5-Agent LangGraph Reflection Review Loop**:
   - **Entity Extractor**: Discovers unknown names and power realms *before* translation.
   - **Context-Aware Drafter**: Resolves omitted pronouns and voice registers using persistent Character Profiles.
   - **Critique Agent**: Scores fidelity and style (0-10) against raw source text, hunting for omissions and glossary violations.
   - **Polishing Agent**: Uses a Diff/Patch engine to refine literary prose without re-generating full chapters.
   - **Chronicler Agent**: Summarizes turning points and reconciles provisional terms into the Novel Bible.
   - **Best-Candidate Guard**: Automatically retains the highest-scoring candidate if subsequent review passes score lower.

2. **3-Tier Hierarchical Narrative Memory**:
   - Macro Context: Overarching story synthesis.
   - Meso Context: Story arc boundary detection and conflict milestones.
   - Micro Context: Preceding chapter rolling context with cross-volume inheritance.

3. **Hybrid RAG Knowledge Store**:
   - SQLite FTS5 lexical BM25 + Gemini Embedding 2 (3072 dims) semantic search.
   - Cross-Encoder reranking via Reciprocal Rank Fusion (RRF, $k=60$).

4. **Modern UI & Deployment**:
   - Terminal lovers: Rich + Textual interactive TUI with real-time token KPI analytics.
   - Browser lovers: React 19 + Vite Web Studio with interactive character dossiers and draft diff viewer.
   - 1-command Docker Compose deployment (`docker compose up -d`).

Repo is 100% open-source (MIT):
🔗 https://github.com/Checkmartyr/NouSetsu

Would love to hear your thoughts, feedback, and feature requests!
```

---

## 📺 3. YouTube Video Metadata

* **Title**: `Translating Light Novels with 5 AI Agents! (LangGraph + Hybrid RAG) | NouSetsu Showcase`
* **Alternative Title**: `How I Built an Autonomous Multi-Agent Novel Translation Framework (NouSetsu)`
* **Description**:
```text
Tired of terrible machine translation destroying your favorite Japanese, Chinese, and Korean light novels? 

In this video, we showcase NouSetsu—an open-source, document-level multi-agent novel translation system powered by LangGraph, 3-Tier Narrative Memory, and Gemini.

🔗 GitHub Repository: https://github.com/Checkmartyr/NouSetsu
📖 Full Documentation: https://github.com/Checkmartyr/NouSetsu/tree/main/docs

⏱️ Timestamps:
0:00 - The Problem with AI Novel Translation
0:20 - Introducing NouSetsu & The 5-Agent Pipeline
0:50 - The LangGraph Reflection Review Loop
1:20 - 3-Tier Narrative Memory & Hybrid RAG Lore Store
1:45 - Interactive Terminal TUI & React 19 Web Studio Demo
2:15 - 1-Click Docker Compose Deployment & Getting Started

#AI #LangGraph #MachineTranslation #LightNovel #WebNovel #Python #React #OpenSource
```
