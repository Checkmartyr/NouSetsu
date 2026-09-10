"""Built-in domain skills for translation pipeline agents."""
from src.skills.builtin.extractor import EXTRACTOR_SKILLS
from src.skills.builtin.drafter import DRAFTER_SKILLS
from src.skills.builtin.critic import CRITIC_SKILLS
from src.skills.builtin.polisher import POLISHER_SKILLS
from src.skills.builtin.chronicler import CHRONICLER_SKILLS

ALL_BUILTIN_SKILLS = (
    EXTRACTOR_SKILLS
    + DRAFTER_SKILLS
    + CRITIC_SKILLS
    + POLISHER_SKILLS
    + CHRONICLER_SKILLS
)

__all__ = [
    "EXTRACTOR_SKILLS",
    "DRAFTER_SKILLS",
    "CRITIC_SKILLS",
    "POLISHER_SKILLS",
    "CHRONICLER_SKILLS",
    "ALL_BUILTIN_SKILLS",
]
