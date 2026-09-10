"""Data models for modular agent skills."""
from typing import List, Optional
from pydantic import BaseModel, Field


class AgentSkill(BaseModel):
    """Modular skill applied to enhance a specific agent's domain capabilities."""

    name: str = Field(..., description="Unique skill identifier (e.g. zero_anaphora)")
    agent: str = Field(..., description="Target agent: extractor, drafter, critic, polisher, chronicler, or all")
    title: str = Field(..., description="Human-readable title (e.g. Zero-Anaphora Subject Resolution)")
    description: str = Field(..., description="Short explanation of what the skill accomplishes")
    content: str = Field(..., description="Detailed instructions, directives, and examples injected into the prompt")
    languages: List[str] = Field(
        default_factory=lambda: ["all"],
        description="Applicable source languages ('all', 'Japanese', 'Chinese', 'Korean', etc.)"
    )
    genres: List[str] = Field(
        default_factory=lambda: ["all"],
        description="Applicable genres ('all', 'xianxia', 'isekai', 'litrpg', 'romance', etc.)"
    )
    priority: int = Field(default=100, description="Priority weight (higher priority appears earlier in prompt)")
    enabled: bool = Field(default=True, description="Whether the skill is active")
    source: str = Field(default="builtin", description="Origin: 'builtin' or 'custom_file'")
