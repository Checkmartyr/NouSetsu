"""Unified structured character roster formatter for LLM agent prompts.

Converts CharacterProfile models into clean, hierarchical markdown cards
tailored for each pipeline agent (Drafter, Critic, Chronicler, Extractor, Polisher).
"""
from typing import List, Optional
from nousetsu.models.bible import CharacterProfile


def format_character_roster(
    characters: List[CharacterProfile],
    context_characters: Optional[List[CharacterProfile]] = None,
    agent_role: str = "drafter",
    empty_fallback: str = "No explicit character cards registered.",
) -> str:
    """Formats a list of CharacterProfile objects into an indented, multi-level

    hierarchical markdown block for agent system prompts.

    Args:
        characters: The list of active/scene characters to format.
        context_characters: Other characters in the scene for resolving
            relational address pairings (defaults to `characters` if None).
        agent_role: Target agent role ('drafter', 'critic', 'chronicler', 'extractor', 'polisher').
        empty_fallback: Fallback string if characters list is empty.

    Returns:
        Structured markdown character roster string.
    """
    if not characters:
        return empty_fallback

    ref_characters = context_characters if context_characters is not None else characters
    cards: List[str] = []

    for c in characters:
        lines: List[str] = []

        # 1. Header Line: Name, Source Name, Gender, Role
        gender_str = c.gender if c.gender and c.gender.strip() else "unspecified"
        role_str = c.role if c.role and c.role.strip() else "supporting"
        orig_name = c.original_name.strip() if c.original_name else "Unknown"

        if agent_role == "extractor":
            # Compact identity line for entity extraction
            lines.append(f"- **{c.name}** ({orig_name} | {role_str})")
        else:
            lines.append(f"- **{c.name}** ({orig_name} | {gender_str} | {role_str})")

        # Name Breakdown (Given, Middle, Surname)
        if c.names and (not c.names.source.is_empty() or not c.names.target.is_empty()):
            src_n = c.names.source
            tgt_n = c.names.target
            breakdown_parts = []
            if src_n.name or tgt_n.name:
                breakdown_parts.append(f"Given: {src_n.name or '—'} -> {tgt_n.name or '—'}")
            if src_n.m_name or tgt_n.m_name:
                breakdown_parts.append(f"Middle: {src_n.m_name or '—'} -> {tgt_n.m_name or '—'}")
            if src_n.s_name or tgt_n.s_name:
                breakdown_parts.append(f"Surname: {src_n.s_name or '—'} -> {tgt_n.s_name or '—'}")
            if breakdown_parts:
                lines.append(f"  * Name Breakdown: {' | '.join(breakdown_parts)}")

        # 2. Voice & Tone
        voice_str = (c.voice or "").strip()
        if voice_str and voice_str.lower() not in ["none", "neutral", "unspecified"]:
            label = "Voice & Tone" if agent_role != "extractor" else "Voice"
            lines.append(f"  * {label}: {voice_str}")

        # 3. Base Pronouns (Zero-Anaphora Subject Resolution)
        has_pronouns = c.pronouns and (c.pronouns.source or c.pronouns.target)
        if has_pronouns:
            src_p = (c.pronouns.source or "N/A").strip()
            tgt_p = (c.pronouns.target or "N/A").strip()
            if agent_role == "critic":
                lines.append(f"  * Expected Pronouns: [Source: {src_p}] -> [Target: {tgt_p}]")
            elif agent_role == "extractor":
                lines.append(f"  * Pronouns: [Source: {src_p}] -> [Target: {tgt_p}]")
            else:
                lines.append(f"  * Pronouns (Zero-Anaphora): [Source: {src_p}] -> [Target: {tgt_p}]")

        # 4. Relational Address Forms (Dialogue Calling Rules)
        if agent_role != "extractor" and c.pronouns and getattr(c.pronouns, "relational", None):
            rel_map = c.pronouns.relational
            rel_items: List[str] = []

            # Resolve matches against other characters in scene context
            matched_targets = set()
            for other_c in ref_characters:
                if other_c.name != c.name and other_c.original_name != c.original_name:
                    p_rel = rel_map.get(other_c.name) or rel_map.get(other_c.original_name)
                    if p_rel:
                        matched_targets.add(other_c.name)
                        rel_items.append(f"    - with {other_c.name}: {p_rel}")

            # If no context characters matched but relational entries exist, include all entries
            if not rel_items:
                for target_name, p_rel in rel_map.items():
                    rel_items.append(f"    - with {target_name}: {p_rel}")

            if rel_items:
                heading = "Relational Address Rules:" if agent_role == "critic" else "Relational Address:"
                lines.append(f"  * {heading}")
                lines.extend(rel_items)

        # 5. Social Bonds & Relationships
        if agent_role in ("drafter", "critic", "chronicler", "polisher") and c.relationships:
            bonds: List[str] = []
            for other_name, bond in c.relationships.items():
                bonds.append(f"{other_name} ({bond})")
            if bonds:
                lines.append(f"  * Relationships: {', '.join(bonds)}")

        # 6. Aliases & Titles
        if c.aliases:
            clean_aliases = [a.strip() for a in c.aliases if a and a.strip()]
            if clean_aliases:
                lines.append(f"  * Aliases: {', '.join(clean_aliases)}")

        cards.append("\n".join(lines))

    return "\n\n".join(cards)
