"""Built-in domain skills for CritiqueAgent (Zensor)."""
from typing import List
from nousetsu.skills.models import AgentSkill

CRITIC_SKILLS: List[AgentSkill] = [
    AgentSkill(
        name="omission_detector",
        agent="critic",
        title="Omission & Truncation Auditor",
        description="Rigorous line-by-line verification ensuring no sentences, descriptive beats, or dialogues are skipped.",
        content="""### Omission & Truncation Audit Directives:
- Check that every paragraph and line of dialogue in the source text corresponds to content in the translation.
- Flag any condensed summaries, skipped subordinate clauses, or missing sensory descriptors.
- Ensure character inner monologues and sound effects (onomatopoeia) were translated or localized rather than ignored.""",
        languages=["all"],
        genres=["all"],
        priority=110,
        source="builtin"
    ),
    AgentSkill(
        name="glossary_enforcer",
        agent="critic",
        title="Strict Glossary & Canonical Terminology Auditor",
        description="Validates 100% adherence to active glossary terms, spellings, and title capitalizations.",
        content="""### Glossary & Terminology Enforcement Directives:
- Cross-reference every entity and keyword in the Active Glossary against the translated text.
- Penalize fidelity scores if canonical names or registered terms appear in inconsistent, partial, or unlocalized forms.
- Verify capitalization consistency for titles, martial technique names, and divine artifacts.""",
        languages=["all"],
        genres=["all"],
        priority=100,
        source="builtin"
    ),
    AgentSkill(
        name="hallucination_guard",
        agent="critic",
        title="Hallucination & Fabrication Guard",
        description="Detects fabricated events, invented dialogue, or swapped speaker actions.",
        content="""### Hallucination Guard Directives:
- Verify that no actions, abilities, or story elements were invented that do not exist in the source excerpt.
- Ensure actions attributed to Character A are not incorrectly ascribed to Character B.
- Flag any sudden unprompted shifts in narrative point-of-view (POV) or temporal tense.""",
        languages=["all"],
        genres=["all"],
        priority=95,
        source="builtin"
    ),
    AgentSkill(
        name="tone_consistency_auditor",
        agent="critic",
        title="Tone & Register Consistency Auditor",
        description="Audits character dialogue registers against their registered Novel Bible personalities.",
        content="""### Tone Consistency Audit Directives:
- Verify that a cold, stoic character does not speak with an overly bubbly, casual demeanor.
- Verify that archaic sect elders do not slip into 21st-century internet slang unless explicitly a comedic trait.
- Provide actionable critique notes pointing out exact sentences requiring tone adjustments.""",
        languages=["all"],
        genres=["all"],
        priority=85,
        source="builtin"
    ),
]
