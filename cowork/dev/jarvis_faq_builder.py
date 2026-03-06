#!/usr/bin/env python3
"""jarvis_faq_builder.py — Constructeur FAQ automatique.

Analyse les questions recurrentes, groupe par similarite, genere Q&A.

Usage:
    python dev/jarvis_faq_builder.py --once
    python dev/jarvis_faq_builder.py --build
    python dev/jarvis_faq_builder.py --search QUERY
    python dev/jarvis_faq_builder.py --add
    python dev/jarvis_faq_builder.py --stats
"""
import argparse
from _paths import TURBO_DIR
import json
import os
import sqlite3
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "faq_builder.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS faqs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT, answer TEXT, category TEXT,
        frequency INTEGER DEFAULT 1, ts REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT, results_count INTEGER, ts REAL)""")
    db.commit()
    return db


def build_faq():
    db = init_db()
    existing = db.execute("SELECT COUNT(*) FROM faqs").fetchone()[0]

    # Seed default FAQs if empty
    if existing == 0:
        defaults = [
            ("Comment verifier le cluster?", "python dev/ia_workload_balancer.py --once", "cluster"),
            ("Comment voir les GPU?", "nvidia-smi ou python dev/win_thermal_monitor.py --once", "hardware"),
            ("Comment lancer JARVIS?", "cd F:/BUREAU/turbo && uv run python main.py", "jarvis"),
            ("Comment tester un script?", "python dev/SCRIPT.py --help && python dev/SCRIPT.py --once", "dev"),
            ("Quel modele utiliser pour le code?", "M1 qwen3-8b (champion local) ou M2 deepseek-r1 (reasoning)", "ia"),
            ("Comment voir la sante systeme?", "python dev/jarvis_health_aggregator.py --once", "system"),
            ("Comment backup les DB?", "python dev/jarvis_backup_manager.py --backup", "maintenance"),
            ("Comment voir les commandes vocales?", "Voir docs/COMMANDES_VOCALES.md (2341 commandes)", "voice"),
            ("Comment ajouter un script COWORK?", "Creer dans dev/, pattern COWORK, ajouter a COWORK_QUEUE.md", "dev"),
            ("Quels sont les ports utilises?", "M1:1234, OL1:11434, Proxy:18800, API:9742, Dashboard:8080", "network"),
        ]
        for q, a, cat in defaults:
            db.execute("INSERT INTO faqs (question, answer, category, frequency, ts) VALUES (?,?,?,?,?)",
                       (q, a, cat, 1, time.time()))
        db.commit()

    # Scan dev/data/*.db for common patterns
    data_dir = DEV / "data"
    db_files = list(data_dir.glob("*.db")) if data_dir.exists() else []

    total = db.execute("SELECT COUNT(*) FROM faqs").fetchone()[0]
    cats = {}
    for row in db.execute("SELECT category, COUNT(*) FROM faqs GROUP BY category").fetchall():
        cats[row[0]] = row[1]

    db.close()
    return {
        "ts": datetime.now().isoformat(),
        "total_faqs": total,
        "categories": cats,
        "databases_scanned": len(db_files),
        "status": "ok",
    }


def search_faq(query):
    db = init_db()
    query_lower = query.lower()
    words = query_lower.split()

    rows = db.execute("SELECT id, question, answer, category, frequency FROM faqs").fetchall()
    results = []
    for row in rows:
        q_lower = row[1].lower()
        score = sum(1 for w in words if w in q_lower)
        if score > 0:
            results.append({
                "id": row[0], "question": row[1], "answer": row[2],
                "category": row[3], "frequency": row[4], "relevance": score,
            })

    results.sort(key=lambda x: (-x["relevance"], -x["frequency"]))

    db.execute("INSERT INTO searches (query, results_count, ts) VALUES (?,?,?)",
               (query, len(results), time.time()))
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "query": query,
        "results": results[:10],
        "total_matches": len(results),
    }


def do_stats():
    db = init_db()
    total = db.execute("SELECT COUNT(*) FROM faqs").fetchone()[0]
    searches = db.execute("SELECT COUNT(*) FROM searches").fetchone()[0]
    top = db.execute(
        "SELECT question, frequency FROM faqs ORDER BY frequency DESC LIMIT 5"
    ).fetchall()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "total_faqs": total,
        "total_searches": searches,
        "top_questions": [{"question": r[0], "frequency": r[1]} for r in top],
    }


def main():
    parser = argparse.ArgumentParser(description="FAQ Builder JARVIS")
    parser.add_argument("--once", "--build", action="store_true", help="Build FAQ")
    parser.add_argument("--search", metavar="QUERY", help="Search FAQ")
    parser.add_argument("--add", action="store_true", help="Add FAQ entry")
    parser.add_argument("--stats", action="store_true", help="FAQ stats")
    args = parser.parse_args()

    if args.search:
        result = search_faq(args.search)
    elif args.stats:
        result = do_stats()
    else:
        result = build_faq()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()