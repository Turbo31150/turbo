"""Shared path constants and config for COWORK scripts.

Derives TURBO_DIR from the file location instead of hardcoding /home/turbo/jarvis-m1-ops.
All cowork scripts should use: from _paths import TURBO_DIR, ETOILE_DB, JARVIS_DB
Telegram config loaded from .env (never hardcode tokens).
"""
import os
from pathlib import Path

# cowork/dev/_paths.py -> cowork/dev/ -> cowork/ -> turbo/
TURBO_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = TURBO_DIR / "data"
ETOILE_DB = DATA_DIR / "etoile.db"
JARVIS_DB = DATA_DIR / "jarvis.db"
SNIPER_DB = DATA_DIR / "sniper.db"

# Load .env if not already in environment
_env_file = TURBO_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#"):
            continue
        _eq = _line.find("=")
        if _eq > 0:
            _key = _line[:_eq].strip()
            _val = _line[_eq + 1:].strip()
            if _key not in os.environ:
                os.environ[_key] = _val

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT", "")
