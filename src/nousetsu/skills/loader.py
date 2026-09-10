"""Custom Markdown and YAML skill file loader."""
from pathlib import Path
import re
from typing import List, Optional
import yaml
from nousetsu.skills.models import AgentSkill


def parse_markdown_skill(file_path: Path) -> Optional[AgentSkill]:
    """Parse a Markdown file with YAML frontmatter into an AgentSkill."""
    try:
        raw = file_path.read_text(encoding="utf-8")
        # Match YAML frontmatter between --- fences
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n([\s\S]*)$", raw, re.DOTALL)
        if not match:
            return None
        frontmatter_text, body_text = match.group(1), match.group(2)
        meta = yaml.safe_load(frontmatter_text)
        if not isinstance(meta, dict) or "name" not in meta or "agent" not in meta:
            return None

        return AgentSkill(
            name=str(meta.get("name")),
            agent=str(meta.get("agent")).lower(),
            title=str(meta.get("title", meta.get("name"))),
            description=str(meta.get("description", "")),
            content=body_text.strip(),
            languages=meta.get("languages", ["all"]),
            genres=meta.get("genres", ["all"]),
            priority=int(meta.get("priority", 80)),
            enabled=bool(meta.get("enabled", True)),
            source=f"file:{file_path.name}"
        )
    except Exception:
        return None


def parse_yaml_skill(file_path: Path) -> Optional[AgentSkill]:
    """Parse a pure YAML file into an AgentSkill."""
    try:
        raw = file_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        if not isinstance(data, dict) or "name" not in data or "agent" not in data:
            return None
        return AgentSkill(
            name=str(data.get("name")),
            agent=str(data.get("agent")).lower(),
            title=str(data.get("title", data.get("name"))),
            description=str(data.get("description", "")),
            content=str(data.get("content", "")).strip(),
            languages=data.get("languages", ["all"]),
            genres=data.get("genres", ["all"]),
            priority=int(data.get("priority", 80)),
            enabled=bool(data.get("enabled", True)),
            source=f"file:{file_path.name}"
        )
    except Exception:
        return None


def load_skills_from_directory(directory: Path) -> List[AgentSkill]:
    """Scan a directory for .md and .yaml files and parse them into AgentSkills."""
    skills: List[AgentSkill] = []
    if not directory.exists() or not directory.is_dir():
        return skills

    # Recursively check markdown and yaml files
    for file_path in directory.glob("**/*"):
        if file_path.is_file():
            if file_path.suffix.lower() == ".md":
                skill = parse_markdown_skill(file_path)
                if skill:
                    skills.append(skill)
            elif file_path.suffix.lower() in [".yaml", ".yml"]:
                skill = parse_yaml_skill(file_path)
                if skill:
                    skills.append(skill)

    return skills
