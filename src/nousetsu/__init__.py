"""NouSetsu - Agentic Document-Level Cross-Chapter Novel Translation System."""
import sys
from nousetsu.utils.env import load_env

# Automatically load environment variables from central .env if present
load_env()

__version__ = "0.3.0"

# Register backward-compatibility alias so legacy 'src.*' imports resolve cleanly
sys.modules.setdefault("src", sys.modules[__name__])

