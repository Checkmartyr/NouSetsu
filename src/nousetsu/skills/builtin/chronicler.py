"""Built-in domain skills for ChroniclerAgent (Chronist)."""
from typing import List
from nousetsu.skills.models import AgentSkill

CHRONICLER_SKILLS: List[AgentSkill] = [
    AgentSkill(
        name="lore_world_state_tracker",
        agent="chronicler",
        title="World State, Artifact & Lore Progression Tracker",
        description="Tracks realm breakthroughs, inventory acquisitions, sect territory changes, and power systems.",
        content="""### World State & Lore Tracking Directives:
- Explicitly record any major breakthroughs in cultivation ranks, magic tiers, or level-ups.
- Catalogue newly acquired artifacts, legendary weapons, secret manuals, or spiritual herbs.
- Track political and sect dynamics: territorial shifts, declarations of war, treaty signings, and faction alliances.""",
        languages=["all"],
        genres=["all"],
        priority=100,
        source="builtin"
    ),
    AgentSkill(
        name="character_status_tracker",
        agent="chronicler",
        title="Character Condition, Injury & Revelation Tracker",
        description="Records physical injuries, psychological trauma, secrets revealed, and relationship milestones.",
        content="""### Character Status & Condition Directives:
- Note physical traumas, poisonings, lost limbs, or lingering debuffs that carry over into subsequent chapters.
- Document critical character revelations: true identities uncovered, confessions of love or betrayal, and lineage truths.
- Summarize changes in interpersonal relationships to keep future chapter voice and pronoun resolution accurate.""",
        languages=["all"],
        genres=["all"],
        priority=95,
        source="builtin"
    ),
    AgentSkill(
        name="continuity_auditor",
        agent="chronicler",
        title="Narrative Lore & Timeline Continuity Auditor",
        description="Verifies timeline consistency and cross-checks chapter outcomes against previous summaries.",
        content="""### Narrative Continuity Audit Directives:
- Highlight any timeline anomalies, sudden character presence contradictions, or previously deceased characters reappearing.
- Formulate concise, high-density chapter synopses (2-3 paragraphs) that focus strictly on forward narrative momentum rather than minor fluff.""",
        languages=["all"],
        genres=["all"],
        priority=85,
        source="builtin"
    ),
]
