#!/usr/bin/env python3
"""voice_gap_filler.py — Detecte les commandes vocales echouees et genere des suggestions.

Analyse voice_corrections dans jarvis.db (confidence < 0.5),
genere des commandes candidates via le cluster IA, et les valide.

Usage:
    python dev/voice_gap_filler.py --once
    python dev/voice_gap_filler.py --analyze
    python dev/voice_gap_filler.py --generate
    python dev/voice_gap_filler.py --test
"""
import argparse
import json
import os
import sqlite3
import time
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
JARVIS_DB = Path("F:/BUREAU/turbo/data/jarvis.db")
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")
DB_PATH = DEV / "data" / "voice_gaps.db"
M1_URL = "http://127.0.0.1:1234/api/v1/chat"
OL1_URL = "http://127.0.0.1:11434/api/chat"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS gaps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, raw_text TEXT, count INTEGER,
        suggestion TEXT, status TEXT DEFAULT 'pending')""")
    db.execute("""CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, gaps_found INTEGER, suggestions_generated INTEGER, report TEXT)""")
    db.commit()
    return db


def analyze_gaps():
    """Find failed voice commands (low confidence)."""
    if not JARVIS_DB.exists():
        return []

    try:
        conn = sqlite3.connect(str(JARVIS_DB))
        conn.row_factory = sqlite3.Row

        # Get corrections with low confidence (failed matches)
        rows = conn.execute("""
            SELECT original_text, corrected_text, confidence, COUNT(*) as cnt
            FROM voice_corrections
            WHERE confidence < 0.5 AND original_text IS NOT NULL
            GROUP BY original_text
            HAVING cnt >= 2
            ORDER BY cnt DESC LIMIT 30
        """).fetchall()

        gaps = []
        for row in rows:
            gaps.append({
                "raw_text": row["original_text"],
                "corrected": row["corrected_text"],
                "confidence": row["confidence"],
                "count": row["cnt"],
            })

        conn.close()
        return gaps
    except Exception as e:
        print(f"[WARN] analyze_gaps: {e}")
        return []


def get_existing_commands():
    """Get list of existing voice command triggers."""
    if not ETOILE_DB.exists():
        return set()

    try:
        conn = sqlite3.connect(str(ETOILE_DB))
        rows = conn.execute("""
            SELECT trigger_text FROM voice_commands
            UNION
            SELECT text FROM voice_corrections WHERE confidence >= 0.8
        """).fetchall()
        conn.close()
        return {r[0].lower().strip() for r in rows if r[0]}
    except Exception:
        return set()


def query_cluster(prompt, timeout=30):
    """Query M1 for command generation."""
    try:
        data = json.dumps({
            "model": "qwen3-8b",
            "input": f"/nothink\n{prompt}",
            "temperature": 0.3,
            "max_output_tokens": 1024,
            "stream": False,
            "store": False,
        }).encode()
        req = urllib.request.Request(
            M1_URL, data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read().decode())
            for item in reversed(result.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return c.get("text", "")
            return ""
    except Exception:
        pass

    # Fallback OL1
    try:
        data = json.dumps({
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            OL1_URL, data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read().decode())
            return result.get("message", {}).get("content", "")
    except Exception:
        return ""


def generate_suggestions(gaps):
    """Generate command suggestions for gaps using cluster IA."""
    existing = get_existing_commands()
    suggestions = []

    for gap in gaps[:10]:
        raw = gap["raw_text"]
        if raw.lower().strip() in existing:
            continue

        prompt = f"""L'utilisateur dit souvent "{raw}" a JARVIS mais la commande n'est pas reconnue (confidence: {gap['confidence']}).
Genere une commande vocale JARVIS pour cette intention.
Reponds UNIQUEMENT en JSON:
{{"id": "nom_commande", "triggers": ["trigger1", "trigger2", "trigger3"], "category": "categorie", "description": "ce que ca fait", "action_type": "python|hotkey|pipeline", "action": "fonction_ou_commande"}}"""

        response = query_cluster(prompt)
        if response:
            try:
                # Extract JSON from response
                start = response.find("{")
                end = response.rfind("}") + 1
                if start >= 0 and end > start:
                    suggestion = json.loads(response[start:end])
                    suggestion["source_gap"] = raw
                    suggestion["gap_count"] = gap["count"]
                    suggestions.append(suggestion)
            except (json.JSONDecodeError, ValueError):
                pass

    return suggestions


def validate_suggestion(suggestion):
    """Basic validation of generated command."""
    required = ["id", "triggers", "action_type"]
    if not all(k in suggestion for k in required):
        return False
    if not isinstance(suggestion.get("triggers"), list) or len(suggestion["triggers"]) == 0:
        return False
    if suggestion.get("action_type") not in ("python", "hotkey", "pipeline", "domino"):
        return False
    # Reject dangerous patterns
    dangerous = ["rm -rf", "format", "shutdown", "del /f", "rmdir"]
    action = str(suggestion.get("action", "")).lower()
    if any(d in action for d in dangerous):
        return False
    return True


def do_once():
    """Full analysis + generation cycle."""
    db = init_db()

    gaps = analyze_gaps()
    suggestions = generate_suggestions(gaps) if gaps else []
    valid = [s for s in suggestions if validate_suggestion(s)]

    # Store gaps
    for gap in gaps:
        existing = db.execute(
            "SELECT COUNT(*) FROM gaps WHERE raw_text=?", (gap["raw_text"],)
        ).fetchone()[0]
        if existing == 0:
            db.execute(
                "INSERT INTO gaps (ts, raw_text, count, status) VALUES (?,?,?,?)",
                (time.time(), gap["raw_text"], gap["count"], "pending")
            )

    # Store suggestions
    for s in valid:
        db.execute(
            "UPDATE gaps SET suggestion=?, status='suggested' WHERE raw_text=?",
            (json.dumps(s, ensure_ascii=False), s.get("source_gap", ""))
        )

    report = {
        "ts": datetime.now().isoformat(),
        "gaps_found": len(gaps),
        "suggestions_generated": len(valid),
        "top_gaps": [{"text": g["raw_text"], "count": g["count"]} for g in gaps[:5]],
        "suggestions": valid[:5],
    }

    db.execute(
        "INSERT INTO runs (ts, gaps_found, suggestions_generated, report) VALUES (?,?,?,?)",
        (time.time(), len(gaps), len(valid), json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def get_test_results():
    """Get validation results of suggestions."""
    db = init_db()
    rows = db.execute(
        "SELECT raw_text, suggestion, status FROM gaps WHERE suggestion IS NOT NULL ORDER BY ts DESC LIMIT 20"
    ).fetchall()
    db.close()
    results = []
    for r in rows:
        try:
            s = json.loads(r[1]) if r[1] else {}
        except Exception:
            s = {}
        results.append({"gap": r[0], "suggestion": s, "status": r[2]})
    return results


def main():
    parser = argparse.ArgumentParser(description="Voice Gap Filler — Detect & suggest missing voice commands")
    parser.add_argument("--once", action="store_true", help="Full analyze + generate cycle")
    parser.add_argument("--analyze", action="store_true", help="Analyze gaps only")
    parser.add_argument("--generate", action="store_true", help="Generate suggestions for known gaps")
    parser.add_argument("--test", action="store_true", help="Show suggestion validation results")
    args = parser.parse_args()

    if args.analyze:
        gaps = analyze_gaps()
        print(json.dumps({"gaps": gaps, "total": len(gaps)}, ensure_ascii=False, indent=2))
    elif args.test:
        results = get_test_results()
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        result = do_once()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
