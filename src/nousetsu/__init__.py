"""NouSetsu - Agentic Document-Level Cross-Chapter Novel Translation System."""
import sys

__version__ = "0.1.0"

# Register backward-compatibility alias so legacy 'src.*' imports resolve cleanly
sys.modules.setdefault("src", sys.modules[__name__])
