"""Built-in domain skills for PolishingAgent (Feinschliff)."""
from typing import List
from nousetsu.skills.models import AgentSkill

POLISHER_SKILLS: List[AgentSkill] = [
    AgentSkill(
        name="chapter_header_preservation",
        agent="polisher",
        title="Chapter Header & Title Preservation",
        description="Ensures chapter titles, numbers, and structural headings from the draft are strictly retained at the top of the polished output.",
        content="""### Chapter Header & Title Preservation Directives:
- If the draft translation begins with a chapter heading or title (e.g., "บทที่ X - ...", "Chapter X: ...", "第X章 ...", or "# Title"), you MUST preserve and include this chapter title at the very beginning of the polished output.
- Refine the chapter title if needed for publication-grade eloquence, but NEVER delete or omit the chapter number and title.
- Do NOT begin the polished text directly with narrative body prose if a chapter header exists in the draft.""",
        languages=["all"],
        genres=["all"],
        priority=115,
        source="builtin"
    ),
    AgentSkill(
        name="translationese_filter",
        agent="polisher",
        title="Anti-Translationese & Stiff Phrasing Filter",
        description="Eliminates repetitive machine-translation cliches, awkward passives, and unnatural syntax.",
        content="""### Anti-Translationese Directives:
- Purge repetitive translationese crutches:
  * "could not help but..." -> use direct physical actions or internal emotional impulses.
  * "as expected of..." -> integrate natural admiration or contextual acknowledgment.
  * "it was none other than..." -> state identity directly with dramatic impact.
  * "after all, he had..." -> eliminate explanatory fluff that dampens tension.
- Convert clunky passive constructions ("his cheek was struck by her hand") into vibrant active voice ("she slapped his cheek").
- Remove repetitive filler pronouns ("he... he... his...") by combining clauses with varied participial phrases.""",
        languages=["all"],
        genres=["all"],
        priority=110,
        source="builtin"
    ),
    AgentSkill(
        name="prose_cadence_enhancer",
        agent="polisher",
        title="Literary Cadence & Rhythmic Sentence Variation",
        description="Crafts dynamic sentence variety, lyrical pacing, and immersive sensory descriptions.",
        content="""### Prose Cadence & Rhythm Directives:
- Vary sentence structures and lengths dynamically: use short, punchy sentences during high-stakes combat or shock, and sweeping, layered periods during atmospheric exposition.
- Sharpen sensory details: replace bland visual adjectives with tactile, auditory, and olfactory textures.
- Ensure natural rhythmic cadence when read aloud—avoid repetitive subject-verb-object monotony.""",
        languages=["all"],
        genres=["all"],
        priority=100,
        source="builtin"
    ),
    AgentSkill(
        name="address_form_preservation",
        agent="polisher",
        title="Address Form & Nickname Preservation",
        description="Preserves exact dialogue address choices (formal names vs. nicknames) during stylistic polishing.",
        content="""### Address Form & Nickname Preservation Directives:
- Retain the exact address forms (formal name, surname, title, diminutive, pet name, or nickname) established in the draft and Novel Bible.
- NEVER rewrite a formal name into a nickname or vice-versa to make English dialogue "flow more naturally" or "sound friendlier."
- Dialogue polish must respect the character's chosen level of intimacy and formality without alteration.""",
        languages=["all"],
        genres=["all"],
        priority=95,
        source="builtin"
    ),
    AgentSkill(
        name="show_dont_tell",
        agent="polisher",
        title="Show-Don't-Tell Emotional Depth Enhancer",
        description="Transforms flat emotional assertions into physical character behaviors and atmospheric cues.",
        content="""### Show-Don't-Tell Directives:
- Instead of telling readers a character was angry, describe tightened knuckles, a sudden drop in vocal cadence, or a twitch in their jaw.
- Anchor emotional turns in the environment: shadow play, flickering flames, chilling wind, or sudden heavy silence.
- Preserve the authentic intent and intensity of the original scene without fabricating unrelated plot points.""",
        languages=["all"],
        genres=["all"],
        priority=90,
        source="builtin"
    ),
    AgentSkill(
        name="dialogue_flow",
        agent="polisher",
        title="Snappy Dialogue & Conversational Flow",
        description="Refines spoken dialogue for natural English conversational rhythm and expressive speech.",
        content="""### Conversational Dialogue Flow Directives:
- Make spoken dialogue flow naturally without feeling like translated subtitles.
- Use contractions (don't, can't, won't) naturally in colloquial conversation, reserving uncontracted speech for formal declarations or solemn vows.
- Use varied dialogue tags and action beats instead of repetitive "said... said... said".""",
        languages=["all"],
        genres=["all"],
        priority=85,
        source="builtin"
    ),
]
