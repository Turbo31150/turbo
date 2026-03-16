"""JARVIS Command Database — SQL-backed registry + preserved utility functions.

Migration 2026-03-05:
  - 889 JarvisCommand data → jarvis.db (voice_commands table, 853 unique)
  - VOICE_CORRECTIONS data → already in jarvis.db (voice_corrections table, 2628 rows)
  - 16 utility functions PRESERVED from original
  - APP_PATHS + SITE_ALIASES dicts PRESERVED
  - Reduced from 410 KB (8417 lines) → ~25 KB
"""

from __future__ import annotations

import json
import re
import sqlite3 as _sqlite3
import time as _time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from src.config import PATHS


__all__ = [
    "JarvisCommand",
    "correct_voice_text",
    "dry_run_command",
    "expand_macro",
    "format_commands_help",
    "get_command_analytics",
    "get_commands_by_category",
    "get_macros",
    "get_unused_commands",
    "match_command",
    "record_command_execution",
    "register_macro",
    "similarity",
]

_TURBO_DIR = str(PATHS.get("turbo", "/home/turbo/jarvis"))
_TURBO_DIR_FWD = str(PATHS.get("turbo", "/home/turbo/jarvis"))
_USER_HOME = str(Path.home())

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "jarvis.db"


# ═══════════════════════════════════════════════════════════════════════════
# COMMAND DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class JarvisCommand:
    """A pre-registered JARVIS voice command."""
    name: str                          # Identifiant unique
    category: str                      # Categorie (navigation, fichiers, trading, systeme, app)
    description: str                   # Description en francais
    triggers: list[str]                # Phrases vocales qui declenchent cette commande
    action_type: str                   # Type: powershell, app_open, browser, script, pipeline
    action: str                        # Commande/template a executer
    params: list[str] = field(default_factory=list)  # Parametres a remplir (phrases a trou)
    confirm: bool = False              # Demander confirmation avant execution


# ═══════════════════════════════════════════════════════════════════════════
# SQL-BACKED COMMAND LOADER
# ═══════════════════════════════════════════════════════════════════════════

def _load_commands_from_db() -> list[JarvisCommand]:
    """Load voice commands from jarvis.db voice_commands table."""
    commands = []
    try:
        conn = _sqlite3.connect(str(_DB_PATH))
        conn.row_factory = _sqlite3.Row
        rows = conn.execute("""
            SELECT name, category, description, triggers, action_type, action, params, confirm
            FROM voice_commands
            WHERE enabled = 1
            ORDER BY category, name
        """).fetchall()

        for r in rows:
            triggers = json.loads(r["triggers"])
            params_raw = json.loads(r["params"] or "[]")
            params = params_raw if isinstance(params_raw, list) else list(params_raw.keys()) if isinstance(params_raw, dict) else []
            commands.append(JarvisCommand(
                name=r["name"],
                category=r["category"],
                description=r["description"] or "",
                triggers=triggers,
                action_type=r["action_type"],
                action=r["action"],
                params=params,
                confirm=bool(r["confirm"]),
            ))
        conn.close()
    except Exception as e:
        import logging
        logging.getLogger("jarvis.commands").error(f"Failed to load commands from DB: {e}")
    return commands


COMMANDS: list[JarvisCommand] = _load_commands_from_db()


# ═══════════════════════════════════════════════════════════════════════════
# PATH FIXUP + EXTENSIONS
# ═══════════════════════════════════════════════════════════════════════════

def _fixup_paths(commands: list) -> None:
    """Replace hardcoded paths with config-driven values in command actions."""
    for _cmd in commands:
        if "F:/BUREAU/turbo" in _cmd.action:
            _cmd.action = _cmd.action.replace("F:/BUREAU/turbo", _TURBO_DIR)
        if "/home/turbo/jarvis-m1-ops" in _cmd.action:
            _cmd.action = _cmd.action.replace("/home/turbo/jarvis-m1-ops", _TURBO_DIR_FWD)
        if "C:\\Users\\franc" in _cmd.action:
            _cmd.action = _cmd.action.replace("C:\\Users\\franc", _USER_HOME)
        if "C:/Users/franc" in _cmd.action:
            _cmd.action = _cmd.action.replace("C:/Users/franc", _USER_HOME.replace("/", "/"))

_fixup_paths(COMMANDS)


def _load_extensions() -> None:
    """Charge les commandes des fichiers par categorie."""
    try:
        from src.commands_pipelines import PIPELINE_COMMANDS
        COMMANDS.extend(PIPELINE_COMMANDS)
    except ImportError:
        pass
    try:
        from src.commands_navigation import NAVIGATION_COMMANDS
        COMMANDS.extend(NAVIGATION_COMMANDS)
    except ImportError:
        pass
    try:
        from src.commands_maintenance import MAINTENANCE_COMMANDS
        COMMANDS.extend(MAINTENANCE_COMMANDS)
    except ImportError:
        pass
    try:
        from src.commands_dev import DEV_COMMANDS
        COMMANDS.extend(DEV_COMMANDS)
    except ImportError:
        pass

_load_extensions()
_fixup_paths(COMMANDS)  # also patch extension commands


# ═══════════════════════════════════════════════════════════════════════════
# KNOWN APP PATHS (Windows)
# ═══════════════════════════════════════════════════════════════════════════

APP_PATHS: dict[str, str] = {
    "chrome": "chrome", "google chrome": "chrome",
    "comet": str(Path.home() / "AppData" / "Local" / "Perplexity" / "Comet" / "Application" / "comet.exe"),
    "firefox": "firefox", "edge": "msedge", "brave": "brave", "opera": "opera",
    "code": "code", "vscode": "code", "vs code": "code", "visual studio code": "code",
    "cursor": "cursor", "notepad": "notepad", "bloc notes": "notepad", "notepad++": "notepad++",
    "sublime": "subl", "terminal": "wt", "powershell": "powershell", "cmd": "cmd",
    "git bash": "git-bash", "explorateur": "explorer", "explorer": "explorer",
    "calculatrice": "calc", "calc": "calc", "paint": "mspaint",
    "snipping tool": "SnippingTool", "gestionnaire de taches": "taskmgr",
    "task manager": "taskmgr", "panneau de configuration": "control",
    "parametres": "ms-settings:", "reglages": "ms-settings:", "settings": "ms-settings:",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "lmstudio": "lmstudio", "lm studio": "lmstudio", "docker": "docker", "postman": "postman",
    "discord": "discord", "telegram": "telegram", "whatsapp": "whatsapp",
    "slack": "slack", "teams": "teams", "zoom": "zoom",
    "spotify": "spotify", "vlc": "vlc", "obs": "obs64", "obs studio": "obs64",
    "audacity": "audacity", "7zip": "7zFM", "winrar": "winrar",
    "steam": "steam", "epic games": "EpicGamesLauncher",
}


# ═══════════════════════════════════════════════════════════════════════════
# SITE ALIASES
# ═══════════════════════════════════════════════════════════════════════════

SITE_ALIASES: dict[str, str] = {
    "google": "https://www.google.com", "gmail": "https://mail.google.com",
    "google drive": "https://drive.google.com", "google docs": "https://docs.google.com",
    "google maps": "https://maps.google.com", "google translate": "https://translate.google.com",
    "google agenda": "https://calendar.google.com",
    "youtube": "https://www.youtube.com", "twitter": "https://twitter.com", "x": "https://twitter.com",
    "reddit": "https://www.reddit.com", "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com", "linkedin": "https://www.linkedin.com",
    "tiktok": "https://www.tiktok.com", "twitch": "https://www.twitch.tv", "netflix": "https://www.netflix.com",
    "github": "https://github.com", "github turbo": "https://github.com/Turbo31150/turbo",
    "gitlab": "https://gitlab.com", "stackoverflow": "https://stackoverflow.com",
    "npm": "https://www.npmjs.com", "pypi": "https://pypi.org",
    "huggingface": "https://huggingface.co", "kaggle": "https://www.kaggle.com",
    "chatgpt": "https://chat.openai.com", "claude": "https://claude.ai",
    "gemini": "https://gemini.google.com", "perplexity": "https://www.perplexity.ai",
    "mistral": "https://chat.mistral.ai",
    "mexc": "https://www.mexc.com", "tradingview": "https://www.tradingview.com",
    "coinglass": "https://www.coinglass.com", "coinmarketcap": "https://coinmarketcap.com",
    "binance": "https://www.binance.com", "coingecko": "https://www.coingecko.com",
    "dexscreener": "https://dexscreener.com",
    "n8n": "http://127.0.0.1:5678", "lm studio": "http://127.0.0.1:1234",
    "dashboard": "http://127.0.0.1:3000",
    "amazon": "https://www.amazon.fr", "leboncoin": "https://www.leboncoin.fr",
    "wikipedia": "https://fr.wikipedia.org", "deepl": "https://www.deepl.com/translator",
}


# ═══════════════════════════════════════════════════════════════════════════
# VOICE CORRECTIONS (loaded from SQL)
# ═══════════════════════════════════════════════════════════════════════════

def _load_voice_corrections() -> dict[str, str]:
    """Load voice corrections from jarvis.db voice_corrections table."""
    corrections: dict[str, str] = {}
    try:
        conn = _sqlite3.connect(str(_DB_PATH))
        rows = conn.execute("SELECT wrong, correct FROM voice_corrections").fetchall()
        for wrong, correct in rows:
            corrections[wrong] = correct
        conn.close()
    except Exception:
        pass
    return corrections

VOICE_CORRECTIONS: dict[str, str] = _load_voice_corrections()


# ═══════════════════════════════════════════════════════════════════════════
# FUZZY MATCHING & VOICE CORRECTION (preserved original logic)
# ═══════════════════════════════════════════════════════════════════════════

_PHRASE_CORRECTIONS: list[tuple[str, str]] = []


def _build_phrase_corrections() -> None:
    """Build sorted phrase corrections list from VOICE_CORRECTIONS dict."""
    global _PHRASE_CORRECTIONS
    _PHRASE_CORRECTIONS = sorted(
        [(k, v) for k, v in VOICE_CORRECTIONS.items() if " " in k],
        key=lambda x: len(x[0]),
        reverse=True,
    )


def correct_voice_text(text: str) -> str:
    """Apply known voice corrections to transcribed text."""
    if not text:
        return text
    text = text.lower().strip()

    words = text.split()
    corrected = []
    for word in words:
        corrected.append(VOICE_CORRECTIONS.get(word, word))
    text = " ".join(corrected)

    if not _PHRASE_CORRECTIONS:
        _build_phrase_corrections()
    for wrong, right in _PHRASE_CORRECTIONS:
        if wrong in text:
            text = text.replace(wrong, right)

    return text


def similarity(a: str, b: str) -> float:
    """Calculate string similarity ratio (0.0 to 1.0).
    Uses max(SequenceMatcher, bag-of-words) to handle word-order inversions from STT.
    """
    a_low, b_low = a.lower(), b.lower()
    seq_score = SequenceMatcher(None, a_low, b_low).ratio()

    words_a = set(a_low.split())
    words_b = set(b_low.split())
    if words_a and words_b:
        intersection = words_a & words_b
        union = words_a | words_b
        jaccard = len(intersection) / len(union)
        coverage = len(intersection) / len(words_b)
        bow_score = (jaccard + coverage) / 2.0
    else:
        bow_score = 0.0

    return max(seq_score, bow_score)


# ── Trigger Index (built once, O(1) exact + O(k) substring lookups) ───────
_trigger_exact: dict[str, tuple[JarvisCommand, str]] = {}
_trigger_param: list[tuple[re.Pattern, list[str], str, JarvisCommand]] = []
_trigger_index_built = False


def _build_trigger_index():
    """Build hash indexes for fast command matching. Called once on first use."""
    global _trigger_index_built
    if _trigger_index_built:
        return
    _trigger_exact.clear()
    _trigger_param.clear()
    for cmd in COMMANDS:
        for trigger in cmd.triggers:
            if "{" in trigger:
                param_names = re.findall(r"\{(\w+)\}", trigger)
                pattern = trigger
                for pname in param_names:
                    pattern = pattern.replace(f"{{{pname}}}", r"(.+)")
                compiled = re.compile("^" + pattern + "$", re.IGNORECASE)
                fixed_part = re.sub(r"\{(\w+)\}", "", trigger).strip().lower()
                _trigger_param.append((compiled, param_names, fixed_part, cmd))
            else:
                key = trigger.lower()
                if key not in _trigger_exact:
                    _trigger_exact[key] = (cmd, trigger)
    _trigger_index_built = True


def match_command(voice_text: str, threshold: float = 0.55) -> tuple[JarvisCommand | None, dict[str, str], float]:
    """Match voice input to a pre-registered command.
    Uses hash index for O(1) exact matches, then parameterized regex,
    then falls back to fuzzy similarity only when needed.
    Returns: (command, extracted_params, confidence_score)
    """
    # --- Learned actions: priorite absolue avant le matching classique ---
    try:
        from src.learned_actions import LearnedActionsEngine
        _la = LearnedActionsEngine()
        la_match = _la.match(voice_text)
        if la_match:
            return JarvisCommand(
                name=la_match["canonical_name"],
                category=la_match.get("category", "system"),
                description=f"Learned action: {la_match['canonical_name']}",
                triggers=la_match.get("triggers", [voice_text]),
                action_type="learned_action",
                action=la_match["canonical_name"],
            ), {}, 1.0
    except Exception:
        pass  # Fallback au matching normal si learned_actions echoue

    _build_trigger_index()

    corrected = correct_voice_text(voice_text)

    # O(1) exact match
    exact = _trigger_exact.get(corrected)
    if exact:
        return exact[0], {}, 1.0

    # O(k) parameterized regex
    best_match: JarvisCommand | None = None
    best_score: float = 0.0
    best_params: dict[str, str] = {}

    for compiled, param_names, fixed_part, cmd in _trigger_param:
        m = compiled.match(corrected)
        if m:
            score = 0.95
            params = {param_names[i]: m.group(i + 1).strip() for i in range(len(param_names))}
            if score > best_score:
                best_score = score
                best_match = cmd
                best_params = params
        elif fixed_part and fixed_part in corrected:
            remaining = corrected.replace(fixed_part, "").strip()
            if remaining:
                score = 0.80
                params = {param_names[0]: remaining} if param_names else {}
                if score > best_score:
                    best_score = score
                    best_match = cmd
                    best_params = params

    if best_score >= 0.90:
        return best_match, best_params, best_score

    # Substring check — require trigger to be significant portion of input
    for key, (cmd, trigger) in _trigger_exact.items():
        if key in corrected and len(key) >= max(4, len(corrected) * 0.4):
            score = 0.90
            if score > best_score:
                best_score = score
                best_match = cmd
                best_params = {}

    if best_score >= 0.85:
        return best_match, best_params, best_score

    # Fuzzy similarity fallback
    for key, (cmd, trigger) in _trigger_exact.items():
        score = similarity(corrected, trigger)
        if score > best_score:
            best_score = score
            best_match = cmd
            best_params = {}

    if best_score < threshold:
        return None, {}, best_score

    return best_match, best_params, best_score


def get_commands_by_category(category: str | None = None) -> list[JarvisCommand]:
    """List commands, optionally filtered by category."""
    if category:
        return [c for c in COMMANDS if c.category == category]
    return COMMANDS


def format_commands_help() -> str:
    """Format all commands as help text for voice output."""
    categories = {}
    for cmd in COMMANDS:
        categories.setdefault(cmd.category, []).append(cmd)

    lines = ["Commandes JARVIS disponibles:"]
    cat_names = {
        "navigation": "Navigation Web", "fichiers": "Fichiers & Documents",
        "app": "Applications", "media": "Controle Media",
        "fenetre": "Fenetres Windows", "clipboard": "Presse-papier & Saisie",
        "systeme": "Systeme Windows", "trading": "Trading & IA",
        "jarvis": "Controle JARVIS", "pipeline": "Pipelines Multi-Etapes",
        "launcher": "Launchers JARVIS", "dev": "Developpement & Outils",
        "saisie": "Saisie & Texte", "accessibilite": "Accessibilite",
    }
    for cat, cmds in categories.items():
        lines.append(f"\n  {cat_names.get(cat, cat)}:")
        for cmd in cmds:
            trigger_example = cmd.triggers[0]
            lines.append(f"    - {trigger_example} -> {cmd.description}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# COMMAND ANALYTICS v2
# ═══════════════════════════════════════════════════════════════════════════

_ANALYTICS_DB = Path(__file__).resolve().parent.parent / "data" / "jarvis.db"


def record_command_execution(command_name: str, duration_ms: float = 0,
                              success: bool = True, source: str = "voice",
                              params: dict | None = None):
    """Record a command execution for analytics."""
    try:
        conn = _sqlite3.connect(str(_ANALYTICS_DB))
        conn.execute(
            "INSERT INTO command_analytics (command_name, duration_ms, success, source, params, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (command_name, duration_ms, 1 if success else 0, source,
             json.dumps(params or {}), _time.time()),
        )
        conn.commit()
        conn.close()
    except _sqlite3.Error:
        pass


def get_command_analytics(top_n: int = 20) -> list[dict]:
    """Get command usage analytics."""
    try:
        conn = _sqlite3.connect(str(_ANALYTICS_DB))
        conn.row_factory = _sqlite3.Row
        rows = conn.execute("""
            SELECT command_name,
                   COUNT(*) as total_uses,
                   SUM(success) as successes,
                   ROUND(AVG(duration_ms), 1) as avg_duration_ms,
                   ROUND(CAST(SUM(success) AS REAL) / COUNT(*), 3) as success_rate,
                   MAX(timestamp) as last_used
            FROM command_analytics
            GROUP BY command_name
            ORDER BY total_uses DESC
            LIMIT ?
        """, (top_n,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except _sqlite3.Error:
        return []


def get_unused_commands(days: int = 30) -> list[str]:
    """Get commands never executed or not used in N days."""
    cutoff = _time.time() - (days * 86400)
    used = set()
    try:
        conn = _sqlite3.connect(str(_ANALYTICS_DB))
        rows = conn.execute(
            "SELECT DISTINCT command_name FROM command_analytics WHERE timestamp > ?",
            (cutoff,),
        ).fetchall()
        conn.close()
        used = {r[0] for r in rows}
    except _sqlite3.Error:
        pass
    all_names = {c.name for c in COMMANDS}
    return sorted(all_names - used)


# ═══════════════════════════════════════════════════════════════════════════
# COMMAND COMPOSITION — Macros
# ═══════════════════════════════════════════════════════════════════════════

_MACROS: dict[str, list[str]] = {}


def register_macro(name: str, command_names: list[str], description: str = ""):
    """Register a macro: a chain of commands executed in sequence."""
    for cmd_name in command_names:
        if not any(c.name == cmd_name for c in COMMANDS):
            raise ValueError(f"Unknown command in macro: {cmd_name}")
    _MACROS[name] = command_names


def get_macros() -> dict[str, list[str]]:
    """Get all registered macros."""
    return dict(_MACROS)


def expand_macro(name: str) -> list[JarvisCommand]:
    """Expand a macro into its constituent commands."""
    cmd_names = _MACROS.get(name, [])
    cmd_map = {c.name: c for c in COMMANDS}
    return [cmd_map[n] for n in cmd_names if n in cmd_map]


# ═══════════════════════════════════════════════════════════════════════════
# DRY-RUN MODE
# ═══════════════════════════════════════════════════════════════════════════

def dry_run_command(voice_text: str) -> dict:
    """Preview what a voice command would do without executing it."""
    cmd, params, score = match_command(voice_text)
    if not cmd:
        return {"matched": False, "score": score, "input": voice_text}

    action_preview = cmd.action
    for key, val in params.items():
        action_preview = action_preview.replace(f"{{{key}}}", val)

    return {
        "matched": True,
        "command": cmd.name,
        "category": cmd.category,
        "description": cmd.description,
        "action_type": cmd.action_type,
        "action_preview": action_preview,
        "params": params,
        "confidence": score,
        "confirm_required": cmd.confirm,
        "input": voice_text,
    }
