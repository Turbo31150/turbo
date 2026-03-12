#!/usr/bin/env python3
"""voice_command_fuzzer.py

Fuzz test voice commands for edge cases.

Fonctionnalites :
* Charge les commandes vocales depuis etoile.db (table commands)
* Genere des variations : typos, partiels, inverses, sons similaires
* Teste la reconnaissance par matching flou (distance de Levenshtein)
* Calcule la precision de reconnaissance pour chaque variation
* Enregistre les resultats dans SQLite (cowork_gaps.db)
* Produit un rapport JSON

CLI :
    --once        : lance un cycle de fuzz et affiche le resume JSON
    --count 100   : nombre de tests a generer (defaut: 50)
    --stats       : statistiques des fuzzes precedents

Stdlib-only (sqlite3, json, argparse, random, difflib).
"""

import argparse
import json
import os
import random
import sqlite3
import string
import sys
import time
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
from _paths import ETOILE_DB

# French phonetic similar-sound substitutions
PHONETIC_SUBS = {
    "ai": "e", "ei": "e", "au": "o", "eau": "o",
    "ou": "u", "an": "en", "in": "ain", "on": "om",
    "ph": "f", "qu": "k", "ch": "sh", "gu": "g",
    "c": "s", "ss": "s", "gn": "ni", "tion": "sion",
    "er": "e", "ez": "e", "et": "e", "es": "e",
}

# Keyboard proximity map for typo generation (AZERTY)
AZERTY_NEIGHBORS = {
    "a": "zqs", "z": "aeqs", "e": "zrds", "r": "etfd",
    "t": "rygf", "y": "tuhg", "u": "yijh", "i": "uokj",
    "o": "iplk", "p": "olm", "q": "azsw", "s": "qzdwe",
    "d": "sfxec", "f": "dgcvr", "g": "fhvbt", "h": "gjbny",
    "j": "hknu", "k": "jlmi", "l": "kmo", "m": "lpk",
    "w": "xsq", "x": "wcd", "c": "xvdf", "v": "cbfg",
    "b": "vngh", "n": "bhj",
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fuzz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            original_command TEXT NOT NULL,
            fuzzed_input TEXT NOT NULL,
            fuzz_type TEXT NOT NULL,
            match_score REAL NOT NULL,
            matched_to TEXT,
            is_correct INTEGER NOT NULL,
            edit_distance INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fuzz_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            total_tests INTEGER NOT NULL,
            accuracy_pct REAL NOT NULL,
            avg_match_score REAL NOT NULL,
            worst_type TEXT,
            duration_ms INTEGER NOT NULL
        )
    """)
    conn.commit()


def get_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn

# ---------------------------------------------------------------------------
# Load Voice Commands from etoile.db
# ---------------------------------------------------------------------------
def load_commands() -> list[str]:
    """Load voice commands from etoile.db."""
    commands = []
    if not ETOILE_DB.exists():
        # Fallback: generate sample commands
        return [
            "ouvre le navigateur", "lance la musique", "quel temps fait-il",
            "affiche le tableau de bord", "verifie le cluster",
            "envoie un message", "lis mes emails", "ferme la fenetre",
            "active le mode sombre", "recherche sur le web",
            "montre les alertes", "demarre le trading",
            "arrete le service", "sauvegarde les donnees",
            "mets a jour le systeme", "check la sante",
        ]

    try:
        econn = sqlite3.connect(str(ETOILE_DB))
        # Try multiple possible table/column names
        for table_query in [
            "SELECT command FROM commands",
            "SELECT trigger_text FROM voice_commands",
            "SELECT text FROM commands",
            "SELECT phrase FROM voice_triggers",
            "SELECT trigger FROM corrections",
        ]:
            try:
                rows = econn.execute(table_query).fetchall()
                if rows:
                    commands = [r[0] for r in rows if r[0] and len(r[0]) > 2]
                    break
            except sqlite3.OperationalError:
                continue
        econn.close()
    except Exception:
        pass

    if not commands:
        # Fallback
        commands = [
            "ouvre le navigateur", "lance la musique", "verifie le cluster",
            "montre les statistiques", "demarre le trading",
        ]

    return commands

# ---------------------------------------------------------------------------
# Fuzz Generators
# ---------------------------------------------------------------------------
def levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]


def fuzz_typo(text: str) -> str:
    """Introduce a random typo (keyboard neighbor substitution)."""
    chars = list(text.lower())
    if not chars:
        return text
    # Pick a random alphabetic character to modify
    alpha_indices = [i for i, c in enumerate(chars) if c in AZERTY_NEIGHBORS]
    if not alpha_indices:
        return text
    idx = random.choice(alpha_indices)
    neighbors = AZERTY_NEIGHBORS.get(chars[idx], "")
    if neighbors:
        chars[idx] = random.choice(neighbors)
    return "".join(chars)


def fuzz_partial(text: str) -> str:
    """Return a partial command (first 40-80% of words)."""
    words = text.split()
    if len(words) <= 1:
        return text
    cut = max(1, int(len(words) * random.uniform(0.4, 0.8)))
    return " ".join(words[:cut])


def fuzz_reversed_words(text: str) -> str:
    """Reverse word order."""
    words = text.split()
    random.shuffle(words)
    return " ".join(words)


def fuzz_phonetic(text: str) -> str:
    """Apply a random phonetic substitution."""
    result = text.lower()
    # Apply 1-2 random substitutions
    subs = list(PHONETIC_SUBS.items())
    random.shuffle(subs)
    applied = 0
    for old, new in subs:
        if old in result and applied < 2:
            result = result.replace(old, new, 1)
            applied += 1
    return result


def fuzz_missing_char(text: str) -> str:
    """Remove a random character."""
    if len(text) <= 2:
        return text
    idx = random.randint(0, len(text) - 1)
    return text[:idx] + text[idx + 1:]


def fuzz_extra_char(text: str) -> str:
    """Insert a random character."""
    idx = random.randint(0, len(text))
    char = random.choice(string.ascii_lowercase)
    return text[:idx] + char + text[idx:]


def fuzz_swap_chars(text: str) -> str:
    """Swap two adjacent characters."""
    if len(text) <= 2:
        return text
    idx = random.randint(0, len(text) - 2)
    chars = list(text)
    chars[idx], chars[idx + 1] = chars[idx + 1], chars[idx]
    return "".join(chars)


FUZZ_TYPES = {
    "typo": fuzz_typo,
    "partial": fuzz_partial,
    "reversed": fuzz_reversed_words,
    "phonetic": fuzz_phonetic,
    "missing_char": fuzz_missing_char,
    "extra_char": fuzz_extra_char,
    "swap_chars": fuzz_swap_chars,
}

# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------
def find_best_match(fuzzed: str, commands: list[str]) -> tuple:
    """Find the best matching command for a fuzzed input."""
    best_score = 0.0
    best_match = ""
    for cmd in commands:
        score = SequenceMatcher(None, fuzzed.lower(), cmd.lower()).ratio()
        if score > best_score:
            best_score = score
            best_match = cmd
    return best_match, round(best_score, 4)

# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
def action_once(count: int = 50) -> dict:
    """Run a fuzz cycle."""
    start_ms = int(time.time() * 1000)
    commands = load_commands()
    conn = get_db()

    results = {
        "timestamp": datetime.now().isoformat(),
        "action": "fuzz",
        "commands_loaded": len(commands),
        "tests_count": count,
        "correct": 0,
        "incorrect": 0,
        "by_type": {},
        "worst_cases": [],
    }

    type_stats = {t: {"total": 0, "correct": 0, "scores": []} for t in FUZZ_TYPES}
    all_cases = []

    for _ in range(count):
        original = random.choice(commands)
        fuzz_name = random.choice(list(FUZZ_TYPES.keys()))
        fuzz_fn = FUZZ_TYPES[fuzz_name]
        fuzzed = fuzz_fn(original)

        best_match, score = find_best_match(fuzzed, commands)
        is_correct = best_match.lower() == original.lower() and score >= 0.5
        edit_dist = levenshtein_distance(fuzzed, original)

        case = {
            "original": original,
            "fuzzed": fuzzed,
            "fuzz_type": fuzz_name,
            "match_score": score,
            "matched_to": best_match,
            "is_correct": is_correct,
            "edit_distance": edit_dist,
        }
        all_cases.append(case)

        if is_correct:
            results["correct"] += 1
        else:
            results["incorrect"] += 1

        type_stats[fuzz_name]["total"] += 1
        if is_correct:
            type_stats[fuzz_name]["correct"] += 1
        type_stats[fuzz_name]["scores"].append(score)

        # Persist
        conn.execute("""
            INSERT INTO fuzz_results
            (timestamp, original_command, fuzzed_input, fuzz_type,
             match_score, matched_to, is_correct, edit_distance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(), original, fuzzed, fuzz_name,
            score, best_match, int(is_correct), edit_dist,
        ))

    # Compute per-type stats
    worst_type = None
    worst_accuracy = 101.0
    for ftype, stats in type_stats.items():
        total = stats["total"]
        if total == 0:
            continue
        accuracy = stats["correct"] / total * 100
        avg_score = sum(stats["scores"]) / len(stats["scores"])
        results["by_type"][ftype] = {
            "total": total,
            "correct": stats["correct"],
            "accuracy_pct": round(accuracy, 1),
            "avg_match_score": round(avg_score, 4),
        }
        if accuracy < worst_accuracy:
            worst_accuracy = accuracy
            worst_type = ftype

    # Find worst individual cases
    all_cases.sort(key=lambda c: c["match_score"])
    results["worst_cases"] = all_cases[:5]

    duration_ms = int(time.time() * 1000) - start_ms
    accuracy = results["correct"] / max(count, 1) * 100
    avg_score = sum(c["match_score"] for c in all_cases) / max(len(all_cases), 1)

    results["accuracy_pct"] = round(accuracy, 1)
    results["avg_match_score"] = round(avg_score, 4)
    results["duration_ms"] = duration_ms
    results["worst_fuzz_type"] = worst_type

    # Persist run summary
    conn.execute("""
        INSERT INTO fuzz_runs
        (timestamp, total_tests, accuracy_pct, avg_match_score, worst_type, duration_ms)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        results["timestamp"], count, accuracy, avg_score, worst_type, duration_ms,
    ))

    conn.commit()
    conn.close()

    return results


def action_stats() -> dict:
    """Show fuzz testing statistics from DB."""
    conn = get_db()

    # Overall stats
    total = conn.execute("SELECT COUNT(*) as cnt FROM fuzz_results").fetchone()["cnt"]
    correct = conn.execute(
        "SELECT COUNT(*) as cnt FROM fuzz_results WHERE is_correct = 1"
    ).fetchone()["cnt"]

    # Per fuzz type
    types = conn.execute("""
        SELECT fuzz_type,
               COUNT(*) as total,
               SUM(is_correct) as correct,
               AVG(match_score) as avg_score,
               AVG(edit_distance) as avg_edit
        FROM fuzz_results
        GROUP BY fuzz_type
    """).fetchall()

    # Recent runs
    runs = conn.execute("""
        SELECT * FROM fuzz_runs ORDER BY timestamp DESC LIMIT 10
    """).fetchall()

    # Most problematic commands
    problem_cmds = conn.execute("""
        SELECT original_command,
               COUNT(*) as total,
               SUM(CASE WHEN is_correct=0 THEN 1 ELSE 0 END) as failures,
               AVG(match_score) as avg_score
        FROM fuzz_results
        GROUP BY original_command
        HAVING failures > 0
        ORDER BY failures DESC
        LIMIT 10
    """).fetchall()

    conn.close()

    return {
        "timestamp": datetime.now().isoformat(),
        "action": "stats",
        "overall": {
            "total_tests": total,
            "correct": correct,
            "accuracy_pct": round(correct / max(total, 1) * 100, 1),
        },
        "by_fuzz_type": [dict(t) for t in types],
        "problematic_commands": [dict(c) for c in problem_cmds],
        "recent_runs": [dict(r) for r in runs],
    }

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Fuzz test voice commands for edge cases and recognition accuracy."
    )
    parser.add_argument("--once", action="store_true",
                        help="Run a fuzz cycle and output JSON summary")
    parser.add_argument("--count", type=int, default=50,
                        help="Number of fuzz tests to generate (default: 50)")
    parser.add_argument("--stats", action="store_true",
                        help="Show fuzz testing statistics from database")
    args = parser.parse_args()

    if not any([args.once, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.stats:
        result = action_stats()
    elif args.once:
        result = action_once(count=args.count)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
