"""Built-in domain skills for EntityExtractorAgent (Schriftdetektiv)."""
from typing import List
from nousetsu.skills.models import AgentSkill

EXTRACTOR_SKILLS: List[AgentSkill] = [
    AgentSkill(
        name="entity_disambiguation",
        agent="extractor",
        title="Entity & Honorific Disambiguation",
        description="Distinguishes familial titles, honorifics, and clan prefixes from canonical character names.",
        content="""### Entity Disambiguation Directives:
- Separate name affixes, familial titles, and honorific suffixes (-san, -kun, -senpai, -sama, -ge, -jie, -shixiong, -orabeoni) from the root proper name.
- Do not mistake situational epithets (e.g., "the silver-haired youth", "the sect master") for canonical character names unless used consistently as primary monikers.
- Detect clan, faction, or sect surnames versus individual given names, preserving accurate alias mappings.""",
        languages=["all"],
        genres=["all"],
        priority=100,
        source="builtin"
    ),
    AgentSkill(
        name="cultivation_realm_extractor",
        agent="extractor",
        title="Cultivation & Magic Realm Hierarchy Extraction",
        description="Extracts Daoist cultivation realms, martial arts stages, and magical tier hierarchies.",
        content="""### Cultivation & Magical Hierarchy Directives:
- Systematically identify realm progression terms (e.g., Qi Refining, Foundation Establishment, Golden Core, Nascent Soul, Martial Saint, Archmage Tier).
- Capture specialized body structures, internal energy channels (Dantian, Meridians, Spiritual Roots, Mana Cores), and alchemy pill grades.
- Group related martial arts techniques, sword intents, or elemental spell categories with contextual category notes.""",
        languages=["Chinese", "Japanese", "Korean"],
        genres=["xianxia", "wuxia", "cultivation", "fantasy", "litrpg"],
        priority=90,
        source="builtin"
    ),
    AgentSkill(
        name="relationship_mapper",
        agent="extractor",
        title="Social Hierarchy & Relationship Mapping",
        description="Infers interpersonal bonds, seniority, master-disciple links, and faction alignments.",
        content="""### Relationship Mapping Directives:
- Infer explicit and implicit interpersonal relationships (e.g., sworn sibling, disciple, rival, superior officer).
- Record hierarchical dynamics (politeness registers, subordination, affection) in each character's voice field to inform the drafting agent.""",
        languages=["all"],
        genres=["all"],
        priority=80,
        source="builtin"
    ),
]
