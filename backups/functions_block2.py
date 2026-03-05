

# Pre-computed phrase-level corrections (multi-word keys sorted by length desc for longest match)
_PHRASE_CORRECTIONS: list[tuple[str, str]] = []


def _build_phrase_corrections() -> None:
    """Build sorted phrase corrections list from VOICE_CORRECTIONS dict."""
    global _PHRASE_CORRECTIONS
    _PHRASE_CORRECTIONS = sorted(
        [(k, v) for k, v in VOICE_CORRECTIONS.items() if " " in k],
        key=lambda x: len(x[0]),
        reverse=True,  # Longest phrases first to avoid partial matches
    )


def correct_voice_text(text: str) -> str:
    """Apply known voice corrections to transcribed text."""
    if not text:
        return text
    text = text.lower().strip()

    # Apply word-level corrections (O(n) on word count, O(1) per lookup)
    words = text.split()
    corrected = []
    for word in words:
        corrected.append(VOICE_CORRECTIONS.get(word, word))
    text = " ".join(corrected)

    # Apply phrase-level corrections (longest match first, pre-sorted)
    if not _PHRASE_CORRECTIONS:
        _build_phrase_corrections()
    for wrong, right in _PHRASE_CORRECTIONS:
        if wrong in text:
            text = text.replace(wrong, right)

    return text


def similarity(a: str, b: str) -> float:
    """Calculate string similarity ratio (0.0 to 1.0).

    Uses max(SequenceMatcher, bag-of-words) to handle
    word-order inversions from STT.
    """
    a_low, b_low = a.lower(), b.lower()
    seq_score = SequenceMatcher(None, a_low, b_low).ratio()

    # Bag-of-words: order-insensitive matching
    words_a = set(a_low.split())
    words_b = set(b_low.split())
    if words_a and words_b:
        intersection = words_a & words_b
        union = words_a | words_b
        jaccard = len(intersection) / len(union)
        # Coverage: fraction of trigger words present in input
        coverage = len(intersection) / len(words_b)
        bow_score = (jaccard + coverage) / 2.0
    else:
        bow_score = 0.0

    # Max of both — word inversions get rescued by bow_score
    return max(seq_score, bow_score)


# ── Trigger Index (built once, O(1) exact + O(k) substring lookups) ───────
_trigger_exact: dict[str, tuple[JarvisCommand, str]] = {}   # lowered trigger → (cmd, trigger)
_trigger_param: list[tuple[re.Pattern, list[str], str, JarvisCommand]] = []  # compiled (pattern, param_names, fixed_part, cmd)
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
                # Keep first registration (higher priority commands listed first)
                if key not in _trigger_exact:
                    _trigger_exact[key] = (cmd, trigger)
    _trigger_index_built = True


def match_command(voice_text: str, threshold: float = 0.55) -> tuple[JarvisCommand | None, dict[str, str], float]:
    """Match voice input to a pre-registered command.

    Uses hash index for O(1) exact matches, then parameterized regex,
    then falls back to fuzzy similarity only when needed.

    Returns: (command, extracted_params, confidence_score)
    """
    _build_trigger_index()

    # Step 1: Correct common voice errors
    corrected = correct_voice_text(voice_text)

    # Step 2: O(1) exact match via hash
    exact = _trigger_exact.get(corrected)
    if exact:
        return exact[0], {}, 1.0

    # Step 3: O(k) parameterized regex matches (k = param triggers only, ~180)
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

    # Step 4: Substring check on non-param triggers (still O(n) but skips fuzzy)
    for key, (cmd, trigger) in _trigger_exact.items():
        if key in corrected:
            score = 0.90
            if score > best_score:
                best_score = score
                best_match = cmd
                best_params = {}

    if best_score >= 0.85:
        return best_match, best_params, best_score

    # Step 5: Fuzzy similarity (only reached for uncertain inputs, ~15% of calls)
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
        "navigation": "Navigation Web",
        "fichiers": "Fichiers & Documents",
        "app": "Applications",
        "media": "Controle Media",
        "fenetre": "Fenetres Windows",
        "clipboard": "Presse-papier & Saisie",
        "systeme": "Systeme Windows",
        "trading": "Trading & IA",
        "jarvis": "Controle JARVIS",
        "pipeline": "Pipelines Multi-Etapes",
        "launcher": "Launchers JARVIS",
        "dev": "Developpement & Outils",
        "saisie": "Saisie & Texte",
        "accessibilite": "Accessibilite",
    }
    for cat, cmds in categories.items():
        lines.append(f"\n  {cat_names.get(cat, cat)}:")
        for cmd in cmds:
            trigger_example = cmd.triggers[0]
            lines.append(f"    - {trigger_example} → {cmd.description}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# COMMAND ANALYTICS v2 — Per-command usage tracking + composition
# ═══════════════════════════════════════════════════════════════════════════

import sqlite3 as _sqlite3
import time as _time
from pathlib import Path as _Path2

_ANALYTICS_DB = _Path2(__file__).resolve().parent.parent / "data" / "jarvis.db"


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
        pass  # Best-effort, don't break command execution


def get_command_analytics(top_n: int = 20) -> list[dict]:
    """Get command usage analytics: most used, success rates, avg duration."""
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
# COMMAND COMPOSITION — Chain multiple commands as macros
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
# DRY-RUN MODE — Preview command effects without execution
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
