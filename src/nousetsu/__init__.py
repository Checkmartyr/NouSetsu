"""NouSetsu - Agentic Document-Level Cross-Chapter Novel Translation System."""
import sys
from dotenv import load_dotenv

# Automatically load environment variables from .env if present
load_dotenv()

__version__ = "0.2.0"

# Register backward-compatibility alias so legacy 'src.*' imports resolve cleanly
sys.modules.setdefault("src", sys.modules[__name__])

