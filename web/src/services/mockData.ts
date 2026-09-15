import { ChapterTraceDocument } from '../types/trace';

export const DEMO_CHAPTER_TRACE: ChapterTraceDocument = {
  chapter_id: "chapter_0001",
  chapter_num: 1,
  folder: "Villainess_05",
  created_at: new Date().toISOString(),
  total_interactions: 5,
  total_duration_seconds: 18.42,
  total_token_usage: {
    input_tokens: 12450,
    output_tokens: 3820,
    thought_tokens: 1200,
    cached_tokens: 4500,
    total_tokens: 17470,
  },
  stage_breakdown: {
    extraction: 1,
    drafting: 1,
    critique: 1,
    polishing: 1,
    chronicling: 1,
  },
  traces: [
    {
      trace_id: "tr_demo_extract_01",
      timestamp: "2026-09-13T10:00:01.000Z",
      chapter_id: "chapter_0001",
      chapter_num: 1,
      folder: "Villainess_05",
      stage: "extraction",
      agent: "extractor",
      model: "gemini-2.5-pro",
      iteration: 1,
      chunk_index: 1,
      total_chunks: 1,
      depth: 0,
      system_prompt: `You are a master literary analyst and translator specializing in creative fiction translation (Japanese to English).
Your task is to analyze the source chapter text against the existing Novel Bible and extract:
1. Characters appearing in the chapter (name, original name, gender/pronouns, role, speaking style/voice).
2. Domain-specific terminology (martial arts ranks, magic spells, locations, factions, special items).

Identify which entities are NEW and propose canonical English translations.

## ACTIVE SPECIALIZED AGENT SKILLS:
[Entity & Honorific Disambiguation]
- Separate name affixes, familial titles, and honorific suffixes (-san, -sama, -dono).
- Detect clan, faction, or sect surnames versus individual given names.`,
      user_prompt: `Extract fictional characters, factions, and world terminology from this novel excerpt:

第1話：悪役令嬢、破滅フラグを回避するために魔術学院へ潜入す
「私、クラウディア・フォン・アウグストは誓います。二度とあの無様なギロチン台の露とは消えぬことを！」
豪華絢爛な薔薇の庭園で、深紅の瞳を宿した少女が紅茶のカップをソーサーに叩きつけた。
侍女のシルヴィアが息を呑む。「お、お嬢様……？ 何をおっしゃっているのですか？」`,
      raw_output: "```json\n" + JSON.stringify({
        new_characters: [
          {
            name: "Claudia von August",
            original_name: "クラウディア・フォン・アウグスト",
            aliases: ["Claudia", "The Villainess"],
            gender: "female",
            role: "protagonist",
            voice: "Regal, commanding, aristocratically proud with sharp dramatic edge",
            relationships: { "Sylvia": "loyal maid" }
          },
          {
            name: "Sylvia",
            original_name: "シルヴィア",
            aliases: [],
            gender: "female",
            role: "supporting",
            voice: "Timid, respectful, nervous servant register",
            relationships: { "Claudia von August": "mistress" }
          }
        ],
        new_terms: [
          {
            source: "破滅フラグ",
            target: "ruin flag",
            category: "term",
            notes: "Classic otome isekai trope refering to fateful doom sequences"
          },
          {
            source: "魔術学院",
            target: "Magic Academy",
            category: "location",
            notes: "Prestige royal magical institution where the main story takes place"
          }
        ],
        active_terms_in_chapter: ["破滅フラグ", "魔術学院"]
      }, null, 2) + "\n```",
      parsed_output: {
        new_characters: 2,
        new_terms: 2,
        active_terms: 2
      },
      token_usage: {
        input_tokens: 1840,
        output_tokens: 420,
        thought_tokens: 280,
        cached_tokens: 0,
        total_tokens: 2540
      },
      duration_seconds: 3.12,
      status: "success",
      error_message: null,
      metadata: {
        extractor_version: "2.1",
        confidence_score: 0.98
      }
    },
    {
      trace_id: "tr_demo_draft_02",
      timestamp: "2026-09-13T10:00:05.000Z",
      chapter_id: "chapter_0001",
      chapter_num: 1,
      folder: "Villainess_05",
      stage: "drafting",
      agent: "drafter",
      model: "gemini-2.5-pro",
      iteration: 1,
      chunk_index: 1,
      total_chunks: 1,
      depth: 0,
      system_prompt: `You are a master creative fiction translator. Your mission is to produce a natural, vivid, stylistically rich English translation of Japanese web novels.

## CHARACTERS IN THIS SCENE:
- Claudia von August (クラウディア): Proud, dramatic, royal cadence
- Sylvia (シルヴィア): Respectful, hesitant maid

## GLOSSARY ENFORCEMENT:
- 破滅フラグ -> ruin flag
- 魔術学院 -> Magic Academy

## PROCEDURAL GUIDELINES:
- Translate fluidly into natural literary English while honoring original tone and pacing.
- Render dialogue with character distinct voices.`,
      user_prompt: `Translate Chapter 1 into vivid literary English:

第1話：悪役令嬢、破滅フラグを回避するために魔術学院へ潜入す
「私、クラウディア・フォン・アウグストは誓います。二度とあの無様なギロチン台の露とは消えぬことを！」
豪華絢爛な薔薇の庭園で、深紅の瞳を宿した少女が紅茶のカップをソーサーに叩きつけた。
侍女のシルヴィアが息を呑む。「お、お嬢様……？ 何をおっしゃっているのですか？」`,
      raw_output: `Chapter 1: The Villainess Infiltrates the Magic Academy to Evade Her Ruin Flag

"I, Claudia von August, hereby swear! Never again shall I perish like pathetic dew beneath that wretched guillotine!"

In a magnificent rose garden, a girl with crimson eyes slammed her teacup against the saucer with a sharp clatter.

Her maid Sylvia gasped, hand flying to her chest. "M-My Lady...? Whatever are you saying?"`,
      parsed_output: {
        word_count: 65,
        paragraphs: 4
      },
      token_usage: {
        input_tokens: 3120,
        output_tokens: 180,
        thought_tokens: 410,
        cached_tokens: 1500,
        total_tokens: 3710
      },
      duration_seconds: 4.25,
      status: "success",
      error_message: null,
      metadata: {
        chunk_split: false
      }
    },
    {
      trace_id: "tr_demo_critique_03",
      timestamp: "2026-09-13T10:00:10.000Z",
      chapter_id: "chapter_0001",
      chapter_num: 1,
      folder: "Villainess_05",
      stage: "critique",
      agent: "critique",
      model: "gemini-2.5-pro",
      iteration: 1,
      chunk_index: 1,
      total_chunks: 1,
      depth: 0,
      system_prompt: `You are an elite literary editor, translation auditor, and prose stylist.
Audit the draft translation for fidelity, natural English rhythm, dialogue voice authenticity, and flow.

Respond strictly in valid JSON:
{
  "fidelity_score": 1-10,
  "flow_score": 1-10,
  "critique_notes": [
    {
      "severity": "minor" | "moderate" | "critical",
      "target": "text excerpt",
      "issue": "detailed issue description",
      "suggestion": "concrete improved phrasing"
    }
  ]
}`,
      user_prompt: `Review this draft against the source text:
[DRAFT]:
"I, Claudia von August, hereby swear! Never again shall I perish like pathetic dew beneath that wretched guillotine!"
In a magnificent rose garden, a girl with crimson eyes slammed her teacup against the saucer with a sharp clatter.
Her maid Sylvia gasped, hand flying to her chest. "M-My Lady...? Whatever are you saying?"`,
      raw_output: JSON.stringify({
        fidelity_score: 9,
        flow_score: 8,
        critique_notes: [
          {
            severity: "minor",
            target: "Never again shall I perish like pathetic dew beneath that wretched guillotine!",
            issue: "The literal translation 'perish like pathetic dew' feels slightly unidiomatic and dampens the explosive theatrical conviction of Claudia's declaration.",
            suggestion: "Consider: 'Never again will I vanish like morning dew upon that shameful guillotine!' or 'Never again shall I meet such a disgraceful end upon the guillotine!'"
          },
          {
            severity: "minor",
            target: "In a magnificent rose garden",
            issue: "Opening with a static prepositional phrase slows the momentum following Claudia's oath.",
            suggestion: "Rearrange to center the sensory resonance: 'Within the opulent rose garden, the crimson-eyed noblewoman slammed her fine porcelain cup into its saucer.'"
          }
        ]
      }, null, 2),
      parsed_output: {
        fidelity_score: 9,
        flow_score: 8,
        issues_count: 2
      },
      token_usage: {
        input_tokens: 2800,
        output_tokens: 390,
        thought_tokens: 210,
        cached_tokens: 1500,
        total_tokens: 3400
      },
      duration_seconds: 3.55,
      status: "success",
      error_message: null,
      metadata: {
        pass: 1,
        requires_polish: true
      }
    },
    {
      trace_id: "tr_demo_polish_04",
      timestamp: "2026-09-13T10:00:14.000Z",
      chapter_id: "chapter_0001",
      chapter_num: 1,
      folder: "Villainess_05",
      stage: "polishing",
      agent: "polisher",
      model: "gemini-2.5-pro",
      iteration: 1,
      chunk_index: 1,
      total_chunks: 1,
      depth: 0,
      system_prompt: `You are a master fiction prose polisher. Refine the draft translation using the editorial critique notes while preserving faithful character voice, emotional weight, and narrative cadence.`,
      user_prompt: `Apply the critique feedback and polish the text:
[CRITIQUE]:
- Elevate "perish like pathetic dew" to capture noble defiance.
- Tighten the garden description for visceral cadence.

[ORIGINAL DRAFT]:
Chapter 1: The Villainess Infiltrates the Magic Academy to Evade Her Ruin Flag

"I, Claudia von August, hereby swear! Never again shall I perish like pathetic dew beneath that wretched guillotine!"

In a magnificent rose garden, a girl with crimson eyes slammed her teacup against the saucer with a sharp clatter.

Her maid Sylvia gasped, hand flying to her chest. "M-My Lady...? Whatever are you saying?"`,
      raw_output: `Chapter 1: The Villainess Infiltrates the Magic Academy to Evade Her Ruin Flag

"I, Claudia von August, swear it on my very soul! Never again shall my life vanish like fleeting dew beneath that wretched guillotine!"

In an opulent garden of blooming roses, the crimson-eyed noblewoman slammed her porcelain teacup down against its saucer with a sharp clatter.

Her maid Sylvia gasped, clutching her chest in sheer disbelief. "M-My Lady...? Whatever in the heavens are you saying?"`,
      parsed_output: {
        word_count: 73,
        paragraphs: 4
      },
      token_usage: {
        input_tokens: 3240,
        output_tokens: 210,
        thought_tokens: 190,
        cached_tokens: 1500,
        total_tokens: 3640
      },
      duration_seconds: 4.80,
      status: "success",
      error_message: null,
      metadata: {
        diff_available: true
      }
    },
    {
      trace_id: "tr_demo_chronicle_05",
      timestamp: "2026-09-13T10:00:19.000Z",
      chapter_id: "chapter_0001",
      chapter_num: 1,
      folder: "Villainess_05",
      stage: "chronicling",
      agent: "chronicler",
      model: "gemini-2.5-pro",
      iteration: 1,
      chunk_index: 1,
      total_chunks: 1,
      depth: 0,
      system_prompt: `You are the master World Chronicler. Synthesize chapter events into concise continuity notes, character relationship updates, and plot flags for future chapters.`,
      user_prompt: `Summarize key events and plot flags from Chapter 1:
- Claudia von August awakens with memories of her past execution.
- Vows to evade her ruin flags by enrolling in the Magic Academy.
- Sylvia witnesses her abrupt shift in personality.`,
      raw_output: JSON.stringify({
        chapter_summary: "Claudia awakens to memories of a grim past execution and swears to evade her destiny by entering the Magic Academy.",
        character_status_updates: {
          "Claudia von August": "Regained past-life/future foresight; resolved to break villainess fate",
          "Sylvia": "Bewildered by Claudia's abrupt change in demeanor"
        },
        new_foreshadowing_flags: [
          "Guillotine execution event in original timeline",
          "Infiltration of the Magic Academy"
        ]
      }, null, 2),
      parsed_output: {
        flags_registered: 2,
        characters_updated: 2
      },
      token_usage: {
        input_tokens: 1450,
        output_tokens: 210,
        thought_tokens: 110,
        cached_tokens: 0,
        total_tokens: 1770
      },
      duration_seconds: 2.70,
      status: "success",
      error_message: null,
      metadata: {
        bible_updated: true
      }
    }
  ]
};
