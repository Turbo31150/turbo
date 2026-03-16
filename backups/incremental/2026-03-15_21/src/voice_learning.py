"""voice_learning.py — Apprentissage automatique depuis voice_analytics.

Analyse les commandes vocales echouees, suggere des corrections et
des alias, genere un rapport de qualite STT.

Usage:
    from src.voice_learning import analyze_failures, auto_suggest_corrections, get_voice_report
    report = get_voice_report()
    suggestions = auto_suggest_corrections()
    applied = apply_suggestions(suggestions, auto=True)
"""
from __future__ import annotations

import difflib
import json
import logging
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.voice_learning")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "jarvis.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def analyze_failures(hours: int = 24) -> dict[str, Any]:
    """Analyse les commandes echouees sur les N dernieres heures.

    Returns:
        Dict avec top_failures (textes qui echouent le plus),
        failure_rate, total_commands, patterns detectes.
    """
    conn = _get_conn()
    cutoff = time.time() - (hours * 3600)

    try:
        # Toutes les commandes recentes
        all_rows = conn.execute(
            "SELECT text, success, confidence, method, latency_ms FROM voice_analytics WHERE timestamp > ? ORDER BY timestamp DESC",
            (cutoff,)
        ).fetchall()

        if not all_rows:
            return {"total": 0, "message": "Aucune donnee voice_analytics"}

        total = len(all_rows)
        successes = sum(1 for r in all_rows if r["success"])
        failures = total - successes

        # Top commandes echouees (groupees par texte)
        fail_texts = [r["text"] for r in all_rows if not r["success"]]
        fail_counter = Counter(fail_texts)
        top_failures = fail_counter.most_common(20)

        # Commandes les plus utilisees (succes)
        success_texts = [r["method"] for r in all_rows if r["success"]]
        top_methods = Counter(success_texts).most_common(10)

        # Latence moyenne
        latencies = [r["latency_ms"] for r in all_rows if r["latency_ms"]]
        avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0

        # Confiance moyenne
        confidences = [r["confidence"] for r in all_rows if r["confidence"] and r["success"]]
        avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0

        conn.close()

        return {
            "hours": hours,
            "total": total,
            "successes": successes,
            "failures": failures,
            "success_rate": round(successes / total * 100, 1) if total > 0 else 0,
            "top_failures": top_failures,
            "top_methods": top_methods,
            "avg_latency_ms": avg_latency,
            "avg_confidence": avg_confidence,
        }
    except sqlite3.Error as e:
        conn.close()
        return {"error": str(e)}


def auto_suggest_corrections(min_occurrences: int = 2) -> list[dict[str, str]]:
    """Genere des suggestions de corrections basees sur les echecs.

    Cherche les textes echoues qui sont proches de commandes existantes
    (distance de Levenshtein / ratio de similarite).

    Args:
        min_occurrences: Nombre minimum d'echecs pour considerer une correction.

    Returns:
        Liste de {"wrong": str, "correct": str, "score": float, "count": int}
    """
    conn = _get_conn()

    try:
        # Commandes echouees
        fail_rows = conn.execute(
            "SELECT text, COUNT(*) as cnt FROM voice_analytics WHERE success = 0 GROUP BY text HAVING cnt >= ? ORDER BY cnt DESC LIMIT 50",
            (min_occurrences,)
        ).fetchall()

        if not fail_rows:
            conn.close()
            return []

        # Charger toutes les commandes vocales connues (depuis les imports Python)
        known_commands = set()
        try:
            from src.linux_desktop_control import VOICE_COMMANDS
            known_commands.update(VOICE_COMMANDS.keys())
        except Exception:
            pass
        try:
            from src.voice_window_manager import VOICE_COMMANDS as WM_COMMANDS
            known_commands.update(WM_COMMANDS.keys())
        except Exception:
            pass
        try:
            from src.voice_mouse_control import VOICE_COMMANDS as MOUSE_COMMANDS
            known_commands.update(MOUSE_COMMANDS.keys())
        except Exception:
            pass
        try:
            from src.voice_dictation import VOICE_COMMANDS as DICT_COMMANDS
            known_commands.update(DICT_COMMANDS.keys())
        except Exception:
            pass

        if not known_commands:
            conn.close()
            return []

        # Corrections deja existantes
        existing = set()
        try:
            rows = conn.execute("SELECT wrong FROM voice_corrections").fetchall()
            existing = {r["wrong"] for r in rows}
        except sqlite3.Error:
            pass

        suggestions = []
        for row in fail_rows:
            wrong_text = row["text"]
            count = row["cnt"]

            # Skip si deja une correction
            if wrong_text in existing:
                continue

            # Chercher la commande la plus proche
            matches = difflib.get_close_matches(wrong_text, known_commands, n=1, cutoff=0.6)
            if matches:
                score = difflib.SequenceMatcher(None, wrong_text, matches[0]).ratio()
                suggestions.append({
                    "wrong": wrong_text,
                    "correct": matches[0],
                    "score": round(score, 3),
                    "count": count,
                })

        conn.close()
        return sorted(suggestions, key=lambda x: (-x["count"], -x["score"]))

    except sqlite3.Error as e:
        conn.close()
        logger.error("auto_suggest_corrections error: %s", e)
        return []


def apply_suggestions(suggestions: list[dict], auto: bool = False, min_score: float = 0.75) -> int:
    """Applique les suggestions de corrections dans la base.

    Args:
        suggestions: Liste de {"wrong", "correct", "score", "count"}
        auto: Si True, applique automatiquement les corrections avec score >= min_score
        min_score: Score minimum pour appliquer automatiquement

    Returns:
        Nombre de corrections appliquees.
    """
    if not suggestions:
        return 0

    conn = _get_conn()
    applied = 0

    for s in suggestions:
        if auto and s["score"] < min_score:
            continue
        if not auto:
            continue  # En mode non-auto, ne rien faire (afficher seulement)

        try:
            conn.execute(
                "INSERT OR IGNORE INTO voice_corrections (wrong, correct, category) VALUES (?, ?, 'auto_learned')",
                (s["wrong"], s["correct"])
            )
            applied += 1
            logger.info("Correction auto: '%s' → '%s' (score=%.2f, count=%d)",
                       s["wrong"], s["correct"], s["score"], s["count"])
        except sqlite3.Error:
            pass

    conn.commit()
    conn.close()

    if applied:
        # Invalider le cache vocal pour forcer le rechargement
        try:
            from src.db_boot_validator import _preload_voice_cache
            _preload_voice_cache()
        except Exception:
            pass

    return applied


def get_voice_report(hours: int = 24) -> str:
    """Genere un rapport texte de qualite vocale pour affichage ou TTS."""
    analysis = analyze_failures(hours)

    if "error" in analysis:
        return f"Erreur analyse: {analysis['error']}"
    if analysis.get("total", 0) == 0:
        return "Aucune commande vocale enregistree"

    lines = [
        f"Rapport vocal ({analysis['hours']}h):",
        f"  {analysis['total']} commandes, {analysis['success_rate']}% reussite",
        f"  Latence moyenne: {analysis['avg_latency_ms']}ms",
        f"  Confiance moyenne: {analysis['avg_confidence']}",
    ]

    if analysis.get("top_failures"):
        lines.append(f"  Top echecs:")
        for text, count in analysis["top_failures"][:5]:
            lines.append(f"    '{text}' ({count}x)")

    if analysis.get("top_methods"):
        lines.append(f"  Top commandes:")
        for method, count in analysis["top_methods"][:5]:
            lines.append(f"    {method} ({count}x)")

    return "\n".join(lines)


def learn_and_improve(auto_apply: bool = True, min_score: float = 0.75) -> dict[str, Any]:
    """Pipeline complet: analyse + suggestion + application.

    Appele periodiquement par le scheduler JARVIS pour ameliorer
    le systeme vocal au fil du temps.
    """
    analysis = analyze_failures(hours=24)
    suggestions = auto_suggest_corrections(min_occurrences=2)
    applied = 0

    if auto_apply and suggestions:
        applied = apply_suggestions(suggestions, auto=True, min_score=min_score)

    return {
        "analysis": analysis,
        "suggestions_count": len(suggestions),
        "applied": applied,
        "suggestions": suggestions[:10],  # Top 10
    }
