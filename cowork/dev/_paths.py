"""Shared path constants for COWORK scripts.

Derives TURBO_DIR from the file location instead of hardcoding F:/BUREAU/turbo.
All cowork scripts should use: from _paths import TURBO_DIR, ETOILE_DB, JARVIS_DB
"""
from pathlib import Path

# cowork/dev/_paths.py -> cowork/dev/ -> cowork/ -> turbo/
TURBO_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = TURBO_DIR / "data"
ETOILE_DB = DATA_DIR / "etoile.db"
JARVIS_DB = DATA_DIR / "jarvis.db"
SNIPER_DB = DATA_DIR / "sniper.db"
