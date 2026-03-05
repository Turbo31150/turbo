#!/usr/bin/env python3
"""continuous_learner.py — Apprentissage continu a partir des interactions.

Collecte les Q&A reussies, cree des datasets, evalue la progression.

Usage:
    python dev/continuous_learner.py --train
    python dev/continuous_learner.py --evaluate
    python dev/continuous_learner.py --export
    python dev/continuous_learner.py --status
    python dev/continuous_learner.py --ingest "question" "reponse" --score 85
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "learning.db"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, question TEXT, answer TEXT,
        score REAL, category TEXT, source TEXT,
        tokens_q INTEGER, tokens_a INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_samples INTEGER, avg_score REAL,
        categories TEXT, quality_trend TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS exports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, format TEXT, path TEXT, samples INTEGER)""")
    db.commit()
    return db

# ---------------------------------------------------------------------------
# Categorisation automatique
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS = {
    "code": ["python", "function", "def ", "class ", "import", "code", "script", "bug", "fix"],
    "system": ["cpu", "ram", "gpu", "disk", "process", "service", "windows", "driver"],
    "trading": ["trading", "btc", "eth", "crypto", "signal", "mexc", "price", "market"],
    "cluster": ["m1", "m2", "m3", "ol1", "ollama", "lm studio", "model", "cluster", "node"],
    "email": ["mail", "email", "inbox", "gmail", "message"],
    "web": ["browser", "chrome", "comet", "navigate", "url", "web", "search"],
    "voice": ["vocal", "tts", "parle", "dis", "voix", "whisper"],
}

def categorize(text: str) -> str:
    text_lower = text.lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if kw in text_lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"

# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------
def ingest_sample(db, question: str, answer: str, score: float = 75.0, source: str = "manual"):
    category = categorize(question + " " + answer)
    tokens_q = len(question.split())
    tokens_a = len(answer.split())
    db.execute(
        "INSERT INTO samples (ts, question, answer, score, category, source, tokens_q, tokens_a) VALUES (?,?,?,?,?,?,?,?)",
        (time.time(), question, answer, score, category, source, tokens_q, tokens_a)
    )
    db.commit()
    return {
        "ingested": True,
        "category": category,
        "score": score,
        "tokens": {"question": tokens_q, "answer": tokens_a},
    }

# ---------------------------------------------------------------------------
# Training analysis
# ---------------------------------------------------------------------------
def train_analysis(db) -> dict:
    total = db.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
    if total == 0:
        return {"status": "no_data", "message": "Aucun echantillon. Utilisez --ingest pour ajouter."}

    avg_score = db.execute("SELECT AVG(score) FROM samples").fetchone()[0] or 0
    by_category = db.execute(
        "SELECT category, COUNT(*), AVG(score) FROM samples GROUP BY category ORDER BY 2 DESC"
    ).fetchall()

    # Qualite par periode
    one_week_ago = time.time() - 7 * 86400
    recent_avg = db.execute(
        "SELECT AVG(score) FROM samples WHERE ts > ?", (one_week_ago,)
    ).fetchone()[0] or 0
    older_avg = db.execute(
        "SELECT AVG(score) FROM samples WHERE ts <= ?", (one_week_ago,)
    ).fetchone()[0] or 0

    trend = "improving" if recent_avg > older_avg + 2 else "stable" if abs(recent_avg - older_avg) <= 2 else "declining"

    # Top samples
    top = db.execute(
        "SELECT question, score, category FROM samples ORDER BY score DESC LIMIT 5"
    ).fetchall()

    # Worst samples (need improvement)
    worst = db.execute(
        "SELECT question, score, category FROM samples WHERE score < 60 ORDER BY score ASC LIMIT 5"
    ).fetchall()

    result = {
        "total_samples": total,
        "avg_score": round(avg_score, 1),
        "recent_avg": round(recent_avg, 1),
        "trend": trend,
        "categories": [{"name": c, "count": n, "avg_score": round(s, 1)} for c, n, s in by_category],
        "top_samples": [{"question": q[:80], "score": s, "category": c} for q, s, c in top],
        "needs_improvement": [{"question": q[:80], "score": s, "category": c} for q, s, c in worst],
    }

    # Store evaluation
    db.execute(
        "INSERT INTO evaluations (ts, total_samples, avg_score, categories, quality_trend) VALUES (?,?,?,?,?)",
        (time.time(), total, avg_score, json.dumps([c for c, _, _ in by_category]), trend)
    )
    db.commit()

    return result

# ---------------------------------------------------------------------------
# Evaluate
# ---------------------------------------------------------------------------
def evaluate(db) -> dict:
    evals = db.execute(
        "SELECT ts, total_samples, avg_score, quality_trend FROM evaluations ORDER BY ts DESC LIMIT 10"
    ).fetchall()

    if not evals:
        return {"status": "no_evaluations", "message": "Lancez --train d'abord."}

    return {
        "evaluations": [
            {"when": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M"),
             "samples": n, "avg_score": round(s, 1), "trend": t}
            for ts, n, s, t in evals
        ],
        "latest_score": round(evals[0][2], 1),
        "latest_trend": evals[0][3],
    }

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def export_dataset(db, fmt: str = "jsonl") -> dict:
    samples = db.execute(
        "SELECT question, answer, score, category FROM samples WHERE score >= 60 ORDER BY score DESC"
    ).fetchall()

    if not samples:
        return {"error": "Pas d'echantillons de qualite suffisante (score >= 60)"}

    export_dir = DB_PATH.parent / "exports"
    export_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    if fmt == "jsonl":
        path = export_dir / f"training_{timestamp}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for q, a, s, c in samples:
                line = json.dumps({"instruction": q, "output": a, "score": s, "category": c}, ensure_ascii=False)
                f.write(line + "\n")
    elif fmt == "json":
        path = export_dir / f"training_{timestamp}.json"
        data = [{"instruction": q, "output": a, "score": s, "category": c} for q, a, s, c in samples]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    else:
        return {"error": f"Format inconnu: {fmt}"}

    db.execute(
        "INSERT INTO exports (ts, format, path, samples) VALUES (?,?,?,?)",
        (time.time(), fmt, str(path), len(samples))
    )
    db.commit()

    return {
        "exported": True,
        "format": fmt,
        "path": str(path),
        "samples": len(samples),
        "avg_score": round(sum(s for _, _, s, _ in samples) / len(samples), 1),
    }

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
def get_status(db) -> dict:
    total = db.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
    avg = db.execute("SELECT AVG(score) FROM samples").fetchone()[0] or 0
    exports = db.execute("SELECT COUNT(*) FROM exports").fetchone()[0]
    cats = db.execute("SELECT category, COUNT(*) FROM samples GROUP BY category ORDER BY 2 DESC").fetchall()
    sources = db.execute("SELECT source, COUNT(*) FROM samples GROUP BY source ORDER BY 2 DESC").fetchall()

    return {
        "total_samples": total,
        "avg_score": round(avg, 1),
        "total_exports": exports,
        "categories": {c: n for c, n in cats},
        "sources": {s: n for s, n in sources},
        "db_path": str(DB_PATH),
        "db_size_kb": round(DB_PATH.stat().st_size / 1024, 1) if DB_PATH.exists() else 0,
    }

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="JARVIS Continuous Learner — Apprentissage continu")
    parser.add_argument("--train", action="store_true", help="Analyser les echantillons et evaluer la progression")
    parser.add_argument("--evaluate", action="store_true", help="Historique des evaluations")
    parser.add_argument("--export", nargs="?", const="jsonl", help="Exporter dataset (jsonl ou json)")
    parser.add_argument("--status", action="store_true", help="Statut de l'apprentissage")
    parser.add_argument("--ingest", nargs=2, metavar=("QUESTION", "REPONSE"), help="Ajouter un echantillon")
    parser.add_argument("--score", type=float, default=75.0, help="Score de l'echantillon (0-100, defaut: 75)")
    parser.add_argument("--source", type=str, default="manual", help="Source (manual, telegram, cron)")
    args = parser.parse_args()

    db = init_db()

    if args.ingest:
        result = ingest_sample(db, args.ingest[0], args.ingest[1], args.score, args.source)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.train:
        result = train_analysis(db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.evaluate:
        result = evaluate(db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.export is not None:
        result = export_dataset(db, args.export)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.status:
        result = get_status(db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        parser.print_help()

    db.close()

if __name__ == "__main__":
    main()
