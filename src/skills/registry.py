"""Skill registry and smart activation coordinator."""
from pathlib import Path
from typing import Dict, List, Optional
from src.skills.builtin import ALL_BUILTIN_SKILLS
from src.skills.loader import load_skills_from_directory
from src.skills.models import AgentSkill


def _normalize_lang(lang: Optional[str]) -> str:
    """Normalize language identifiers to standard lowercase names."""
    if not lang:
        return "all"
    l = lang.strip().lower()
    if l in ["ja", "jp", "japanese", "nihongo"]:
        return "japanese"
    if l in ["zh", "cn", "chinese", "mandarin"]:
        return "chinese"
    if l in ["ko", "kr", "korean", "hangul"]:
        return "korean"
    if l in ["en", "english"]:
        return "english"
    if l in ["auto", "autodetect", "detect"]:
        return "all"
    return l


def _normalize_genre(genre: Optional[str]) -> str:
    """Normalize genre identifier."""
    if not genre:
        return "general"
    return genre.strip().lower()


class SkillRegistry:
    """Manages built-in and file-based skills with smart filtering."""

    _instance: Optional["SkillRegistry"] = None

    def __init__(self, load_catalog: bool = True):
        self._skills: Dict[str, AgentSkill] = {}
        # Register built-in skills
        for skill in ALL_BUILTIN_SKILLS:
            self.register_skill(skill)

        # Load default catalog files if enabled
        if load_catalog:
            default_catalog = Path(__file__).parent / "catalog"
            if default_catalog.exists():
                self.load_directory(default_catalog)

    @classmethod
    def get_instance(cls) -> "SkillRegistry":
        """Singleton accessor."""
        if cls._instance is None:
            cls._instance = SkillRegistry()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (primarily for testing isolation)."""
        cls._instance = None

    def register_skill(self, skill: AgentSkill) -> None:
        """Register or override a skill by unique name."""
        self._skills[skill.name] = skill

    def load_directory(self, directory: Path) -> int:
        """Load skills from a directory of markdown/yaml files."""
        loaded = load_skills_from_directory(directory)
        for skill in loaded:
            self.register_skill(skill)
        return len(loaded)

    def list_skills(self) -> List[AgentSkill]:
        """Return all registered skills."""
        return list(self._skills.values())

    def get_active_skills(
        self,
        agent: str,
        source_lang: Optional[str] = None,
        genre: Optional[str] = None
    ) -> List[AgentSkill]:
        """
        Smart filter: returns skills matching target agent, source language, and genre,
        ordered by priority (descending).
        """
        agent_norm = agent.lower().strip()

        matched: List[AgentSkill] = []
        for skill in self._skills.values():
            if not skill.enabled:
                continue

            # 1. Agent match
            if skill.agent not in (agent_norm, "all") and agent_norm != "all":
                continue

            # 2. Language match (if filtered)
            if source_lang is not None:
                lang_norm = _normalize_lang(source_lang)
                skill_langs = [_normalize_lang(l) for l in skill.languages]
                lang_match = ("all" in skill_langs) or (lang_norm in skill_langs) or (lang_norm == "all")
                if not lang_match:
                    continue

            # 3. Genre match (if filtered)
            if genre is not None:
                genre_norm = _normalize_genre(genre)
                skill_genres = [_normalize_genre(g) for g in skill.genres]
                genre_match = ("all" in skill_genres) or (genre_norm in skill_genres) or (genre_norm == "all")
                if not genre_match:
                    continue

            matched.append(skill)

        # Sort by priority descending, then title ascending
        matched.sort(key=lambda s: (-s.priority, s.title))
        return matched

    def build_prompt_section(
        self,
        agent: str,
        source_lang: Optional[str] = None,
        genre: Optional[str] = None
    ) -> str:
        """Generate formatted prompt text to inject into an agent's system prompt."""
        active = self.get_active_skills(agent=agent, source_lang=source_lang, genre=genre)
        if not active:
            return ""

        sections = [
            "## ACTIVE SPECIALIZED AGENT SKILLS:",
            "Apply the following domain directives to this chapter:"
        ]
        for skill in active:
            sections.append(f"\n[{skill.title}]\n{skill.content}")

        return "\n".join(sections)
