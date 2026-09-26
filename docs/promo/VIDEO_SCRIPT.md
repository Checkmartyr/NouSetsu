# 🎬 NouSetsu Promotional Video Script & Storyboard

> **Official Video Production Guide for Social Media Launch & Community Outreach**  
> Formats: **60-Second Viral Short (9:16)** & **2-Minute Feature Showcase (16:9)**  
> Target Platforms: YouTube, X (Twitter), TikTok, Instagram Reels, Reddit (r/LocalLLaMA, r/LightNovels)

---

## 📌 Video 1: 60-Second Viral Short / Reel (9:16 Vertical)
*Fast-paced, high energy, hook in the first 3 seconds, targeted at light novel readers, AI developers, and webnovel fans.*

* **Pacing**: Fast (~140 words per minute)
* **Audio Track**: Futuristic Lo-Fi Cyber Synthwave (Upbeat, rhythmic bassline)
* **Tone**: Confident, enthusiastic, tech-savvy

### Timeline & Storyboard

| Timestamp | Visual Cues & On-Screen Action | On-Screen Text (OST) | Voiceover Script (Audio) |
| :--- | :--- | :--- | :--- |
| **0:00 - 0:05** | Quick-cut montage of terrible machine translations: pronouns swapping randomly ("He kissed him... wait, she?"), names misspelled 3 times in one page. Red glitch effect. | ⚠️ **AI NOVEL TRANSLATION IS BROKEN.** | "Why is machine translating light novels still so terrible? Pronouns disappear, character voices sound like robots, and names change every single page." |
| **0:05 - 0:12** | Slam cut to cyberpunk anime title splash with glowing particles: **NOUSETSU**. High-tech floating manuscript. | 🌸 **MEET NOUSETSU**<br>Document-Level Multi-Agent Translation | "Stop using single-prompt translators. Meet **NouSetsu**—the open-source, document-level AI translation framework designed specifically for light novels." |
| **0:12 - 0:24** | Dynamic 3D diagram animating 5 interconnected nodes with glowing energy lines: Extractor ➔ Drafter ➔ Critic ➔ Polisher ➔ Chronicler. | 🤖 **5 SPECIALIZED AGENTS**<br>LangGraph Reflection Cycle | "Instead of one messy prompt, NouSetsu orchestrates five specialized agents in a cyclic LangGraph loop. An Extractor finds unknown lore, a Drafter translates with zero-anaphora resolution..." |
| **0:24 - 0:34** | Split-screen showing Critique Agent auditing line-by-line, calculating Fidelity & Style score cards (9.2 / 10). | 🔍 **CRITIC & POLISHER LOOP**<br>Fidelity: 9.4/10 \| Style: 9.2/10 | "...a Critic audits every sentence for fidelity, and a Polisher rewrites it into publication-quality literary English using targeted Diff patches." |
| **0:34 - 0:45** | Screen recording of the **Novel Bible** (`bible.yaml`) and **3-Tier Narrative Memory** (Macro > Meso > Micro) showing character relationship graphs. | 🧠 **PERSISTENT NOVEL BIBLE**<br>3-Tier Memory Never Forgets Lore | "And it never forgets. The Novel Bible tracks character statuses, injuries, and story arcs across hundreds of chapters without narrative drift." |
| **0:45 - 0:54** | Quick showcase of the dual interfaces: Beautiful Textual TUI in terminal and Vite + React 19 Web Studio in browser, running via Docker Compose. | ⚡ **TUI + WEB STUDIO**<br>Docker Compose in 1 Command | "Run it in your terminal with Textual, or launch the React 19 Web Studio with a single Docker Compose command." |
| **0:54 - 1:00** | End card with GitHub logo, repo URL, star animation, and Cristina mascot kaomoji `(=^･ω･^=)`. | ⭐ **STAR ON GITHUB**<br>github.com/Checkmartyr/NouSetsu | "100% open-source on GitHub. Star NouSetsu today and elevate your webnovel translation nya~!" |

---

## 🎥 Video 2: 2-Minute Comprehensive Feature Showcase (16:9 Horizontal)
*In-depth technical and literary demonstration for YouTube, X (Twitter), and Developer conferences.*

* **Pacing**: Steady, authoritative, informative
* **Audio Track**: Cinematic Synth Orchestral (Subtle build-up leading into triumphant electronic melody)

### Scene Breakdown

#### Scene 1: The Problem (0:00 - 0:20)
* **Visual**: Screen capture of a raw Japanese webnovel chapter (syosetu / kakuyomu). Highlight the missing subjects and omitted pronouns (*zero-anaphora*). Transition to generic DeepL/ChatGPT output showing hallucinated pronouns and flat emotionless prose.
* **On-Screen Text**: *The Zero-Anaphora Dilemma: When Context Vanishes.*
* **Voiceover**:
  > "In East Asian webnovels, subjects and pronouns are almost never stated explicitly. When traditional machine translation or single-prompt LLMs translate these chapters, they guess blindly. A haughty villainess ends up speaking like an ancient martial arts master, terms change spelling every chapter, and narrative continuity collapses. Literary translation isn't a sentence-level problem—it's a document-level and multi-chapter narrative challenge."

#### Scene 2: The Multi-Agent LangGraph Solution (0:20 - 0:50)
* **Visual**: Smooth animation of the system architecture from `README.md`. Showcase the five agents activating sequentially:
  1. **Stage 1 (Extractor)**: Scanning raw text, extracting cultivation realms and unknown names.
  2. **Stage 2 (Drafter)**: Ingesting rolling context and active glossary to draft chapter prose.
  3. **Stage 3 & 4 (Critic & Polisher Reflection Loop)**: Bi-directional inspection loop scoring fidelity and style, with the Best-Candidate Regression Guard retaining the peak draft.
  4. **Stage 5 (Chronicler)**: Updating story arc summaries and indexing into SQLite RAG.
* **Voiceover**:
  > "NouSetsu solves this through a cyclic multi-agent architecture powered by LangGraph. Before a single word is translated, the Entity Extractor discovers new characters and terminology. The Context-Aware Drafter resolves omitted pronouns using persistent character voice profiles. Then, our Critique Agent inspects the draft against raw source text, passing actionable revision notes to the Polishing Agent. If prose quality is below target, they reflect and refine in an automated review loop—backed by a Best-Candidate Guard that prevents quality regression."

#### Scene 3: 3-Tier Narrative Memory & Hybrid RAG (0:50 - 1:20)
* **Visual**: Zoom in on `.novel/bible/` and `.novel/rag/lore.db`. Show the Rich CLI tree rendering the 3-tier memory hierarchy: Macro (Whole Story), Meso (Active Story Arcs), Micro (Immediate Chapter Summaries). Show a quick Hybrid RAG search retrieving episodic lore with BM25 + Gemini Embedding 2.
* **On-Screen Text**: *Macro > Meso > Micro: Zero Narrative Drift Across 500+ Chapters.*
* **Voiceover**:
  > "How does NouSetsu translate multi-hundred chapter epics without forgetting past events? Through 3-Tier Hierarchical Narrative Memory. Macro context preserves overarching novel milestones, Meso context tracks active story arc conflicts, and Micro context scopes immediate preceding chapter cliffhangers. Combined with a zero-daemon local Hybrid SQLite RAG store with cross-encoder reranking, agents pull exact historical lore right when it matters."

#### Scene 4: Developer & Reader Experience (1:20 - 1:45)
* **Visual**: Screen recording demonstrating:
  1. Terminal TUI: Scrolling through chapters, dual source/target reader, token KPI dashboard (`M` hotkey).
  2. Web Studio: Drag-and-drop chapter upload, interactive character relationship dossiers, draft-to-polish diff viewer.
  3. One-line terminal launch: `docker compose up -d`.
* **Voiceover**:
  > "NouSetsu is built for effortless workflow. Monitor token usage, stage durations, and chapter queues inside a lightning-fast Textual terminal dashboard. Prefer a graphical interface? Launch the Vite and React 19 Web Studio in your browser, inspect character dossiers, and drag-and-drop entire volume folders. Deploy instantly with Docker Compose—zero dependencies required."

#### Scene 5: Outro & Call to Action (1:45 - 2:00)
* **Visual**: Clean splash screen with promotional banner, GitHub URL, MIT License badge, and community links.
* **On-Screen Text**: *NouSetsu: The Document-Level AI Translation Framework.*
* **Voiceover**:
  > "NouSetsu is fully open-source, extensible with custom markdown domain skills, and ready for your favorite light novels. Check out the link in the description, try the demo, and star the repository on GitHub. Happy translating nya~!"

---

## 🎵 Audio & SFX Recommendations
* **Theme Music**: Synthwave / Cyberpunk Lofi (e.g. *Kavinsky-style retro synth* or *ChilledCow anime lofi beats*).
* **Sound Effects**:
  - `0:03`: Glitch sound on bad translation cut.
  - `0:15`: Digital laser whoosh on agent node activation.
  - `0:30`: Stamp / chime SFX on 9.5/10 quality score pass.
  - `0:50`: Soft keyboard mechanical typing on TUI showcase.
  - `1:55`: Crisp chime on GitHub star button click.

---

## 🎨 Asset Checklist for Video Creator
- [x] Official Promotional Banner (`docs/promo/promo_banner.jpg`)
- [x] Interactive Presentation Reel Player (`docs/promo/presentation.html`)
- [x] Automated Terminal Animation Script (`docs/promo/demo_terminal_video.py`)
- [x] Full Storyboard & Voiceover Script (`docs/promo/VIDEO_SCRIPT.md`)
- [x] Social Media Launch Kit (`docs/promo/SOCIAL_MEDIA_KIT.md`)
