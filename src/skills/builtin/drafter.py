"""Built-in domain skills for ContextAwareDrafterAgent (Wortschmied)."""
from typing import List
from src.skills.models import AgentSkill

DRAFTER_SKILLS: List[AgentSkill] = [
    AgentSkill(
        name="zero_anaphora_resolution",
        agent="drafter",
        title="Zero-Anaphora Subject & Pronoun Resolution",
        description="Recovers unstated subjects, omitted actors, and dialogue speakers using context and speech registers.",
        content="""### Zero-Anaphora Resolution Directives:
- In East Asian languages (Japanese, Chinese, Korean), grammatical subjects and personal pronouns are routinely omitted in narrative and dialogue.
- Trace the subject across dialogue turns by examining sentence endings, honorifics (e.g., -wa, -ze, -kashira, -ssu, -de gozaru), verb honorific forms (keigo/sonkeigo/kenjougo), and physical positioning in the scene.
- Never default to generic "he" or "they" when the context clearly reveals a specific female character or group.
- If a sentence describes an involuntary physiological reaction or sensory experience, attribute it strictly to the current viewpoint (POV) character.""",
        languages=["Japanese", "Chinese", "Korean"],
        genres=["all"],
        priority=110,
        source="builtin"
    ),
    AgentSkill(
        name="character_voice_differentiation",
        agent="drafter",
        title="Distinct Character Voice Differentiation",
        description="Enforces individualized speech registers, cadence, and personality traits for every speaker.",
        content="""### Character Voice Differentiation Directives:
- Respect registered character voice profiles from the Novel Bible.
- Aristocrats, sect masters, and elders speak with elevated vocabulary, measured clauses, and formal dignity.
- Delinquents, mercenaries, and commoners use brisk colloquialisms, contractions, and energetic rhythms.
- Keep Tsundere, Kuudere, Chuunibyou, and eccentric speech mannerisms distinct without rendering them as nonsensical gibberish in English.""",
        languages=["all"],
        genres=["all"],
        priority=100,
        source="builtin"
    ),
    AgentSkill(
        name="idiom_localization",
        agent="drafter",
        title="Cultural Idiom & Four-Character Metaphor Localization",
        description="Translates four-character idioms (chengyu/yojijukugo) into vivid English prose rather than literal calques.",
        content="""### Idiom & Metaphor Localization Directives:
- Translate cultural idioms, proverbs, and four-character expressions (chengyu / yojijukugo / saja seong-eo) into idiomatic, evocative English prose.
- When an idiom carries deep narrative or martial symbolism, capture both the poetic imagery and the underlying thematic meaning.
- Avoid bizarre literal word-for-word calques (e.g., do not translate "draw a snake and add feet" literally when "overgilding the lily" or "ruining through excess" conveys the intent naturally).""",
        languages=["Chinese", "Japanese", "Korean"],
        genres=["all"],
        priority=90,
        source="builtin"
    ),
    AgentSkill(
        name="litrpg_system_framing",
        agent="drafter",
        title="LitRPG & Game System Interface Formatting",
        description="Standardizes system notifications, status windows, and bracketed game skill alerts.",
        content="""### LitRPG & System Window Directives:
- Render system notifications, quest logs, and game announcements in clean blockquotes or markdown frames:
  > **[System Alert]**
  > Level Up! Strength +5 | Agility +3
- Maintain strict consistency for skill names, status prompts, and attribute abbreviations (HP, MP, STR, DEX, INT).
- Keep bracketed formats `[Skill Name]` consistent across all occurrences.""",
        languages=["all"],
        genres=["litrpg", "gamelit", "isekai", "progression"],
        priority=85,
        source="builtin"
    ),
]
