#!/usr/bin/env python3
"""ia_curriculum_planner.py — #210 Adaptive curriculum planning for IA skill progression.
Usage:
    python dev/ia_curriculum_planner.py --plan
    python dev/ia_curriculum_planner.py --next
    python dev/ia_curriculum_planner.py --progress
    python dev/ia_curriculum_planner.py --adjust
    python dev/ia_curriculum_planner.py --once
"""
import argparse, json, sqlite3, time, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "curriculum_planner.db"

# Skill domains and their curriculum
SKILL_DOMAINS = {
    "code": {
        "levels": [
            {"level": 1, "name": "basics", "topics": ["syntax", "variables", "functions", "loops"], "threshold": 70},
            {"level": 2, "name": "intermediate", "topics": ["classes", "error_handling", "file_io", "testing"], "threshold": 75},
            {"level": 3, "name": "advanced", "topics": ["async", "decorators", "metaclasses", "optimization"], "threshold": 80},
            {"level": 4, "name": "expert", "topics": ["architecture", "design_patterns", "concurrency", "profiling"], "threshold": 85},
            {"level": 5, "name": "master", "topics": ["compiler_theory", "os_internals", "distributed_systems", "ml_from_scratch"], "threshold": 90},
        ]
    },
    "trading": {
        "levels": [
            {"level": 1, "name": "basics", "topics": ["market_structure", "order_types", "candlesticks"], "threshold": 65},
            {"level": 2, "name": "technical", "topics": ["indicators", "patterns", "volume_analysis"], "threshold": 70},
            {"level": 3, "name": "strategy", "topics": ["backtesting", "risk_management", "position_sizing"], "threshold": 75},
            {"level": 4, "name": "algorithmic", "topics": ["signal_generation", "execution", "portfolio_optimization"], "threshold": 80},
            {"level": 5, "name": "quantitative", "topics": ["statistical_arbitrage", "ml_signals", "hft_basics"], "threshold": 85},
        ]
    },
    "nlp": {
        "levels": [
            {"level": 1, "name": "basics", "topics": ["tokenization", "embeddings", "similarity"], "threshold": 65},
            {"level": 2, "name": "intermediate", "topics": ["classification", "ner", "sentiment"], "threshold": 70},
            {"level": 3, "name": "advanced", "topics": ["transformers", "fine_tuning", "rag"], "threshold": 80},
            {"level": 4, "name": "expert", "topics": ["prompt_engineering", "agents", "evaluation"], "threshold": 85},
        ]
    },
    "reasoning": {
        "levels": [
            {"level": 1, "name": "basics", "topics": ["logic", "deduction", "pattern_recognition"], "threshold": 70},
            {"level": 2, "name": "intermediate", "topics": ["chain_of_thought", "decomposition", "analogies"], "threshold": 75},
            {"level": 3, "name": "advanced", "topics": ["multi_step", "constraint_satisfaction", "planning"], "threshold": 80},
            {"level": 4, "name": "expert", "topics": ["meta_reasoning", "uncertainty", "causal_inference"], "threshold": 85},
        ]
    }
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS skill_levels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        current_level INTEGER DEFAULT 1,
        current_score REAL DEFAULT 0,
        topics_completed TEXT DEFAULT '[]',
        total_exercises INTEGER DEFAULT 0,
        last_evaluated TEXT,
        UNIQUE(domain)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS curriculum_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        level INTEGER,
        topic TEXT,
        status TEXT DEFAULT 'pending',
        score REAL,
        attempts INTEGER DEFAULT 0,
        completed_at TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT,
        level INTEGER,
        topic TEXT,
        score REAL,
        passed INTEGER,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    # Seed skill levels if empty
    count = db.execute("SELECT COUNT(*) FROM skill_levels").fetchone()[0]
    if count == 0:
        for domain in SKILL_DOMAINS:
            db.execute(
                "INSERT INTO skill_levels (domain, current_level, current_score) VALUES (?,?,?)",
                (domain, 1, 0)
            )
    db.commit()
    return db


def create_plan(db):
    """Generate/update curriculum plan based on current levels."""
    plan = {}
    for domain, config in SKILL_DOMAINS.items():
        row = db.execute("SELECT current_level, current_score FROM skill_levels WHERE domain=?", (domain,)).fetchone()
        current_level = row[0] if row else 1
        current_score = row[1] if row else 0

        levels_data = config["levels"]
        current_config = None
        next_topics = []

        for lv in levels_data:
            if lv["level"] == current_level:
                current_config = lv
                completed = db.execute(
                    "SELECT topic FROM curriculum_items WHERE domain=? AND level=? AND status='completed'",
                    (domain, current_level)
                ).fetchall()
                completed_topics = {c[0] for c in completed}

                for topic in lv["topics"]:
                    if topic not in completed_topics:
                        existing = db.execute(
                            "SELECT id FROM curriculum_items WHERE domain=? AND level=? AND topic=?",
                            (domain, current_level, topic)
                        ).fetchone()
                        if not existing:
                            db.execute(
                                "INSERT INTO curriculum_items (domain, level, topic) VALUES (?,?,?)",
                                (domain, current_level, topic)
                            )
                        next_topics.append(topic)
                break

        plan[domain] = {
            "current_level": current_level,
            "level_name": current_config["name"] if current_config else "unknown",
            "current_score": current_score,
            "pending_topics": next_topics,
            "threshold": current_config["threshold"] if current_config else 70,
            "total_levels": len(levels_data)
        }

    db.commit()
    return {"plan": plan, "domains": len(plan)}


def get_next(db):
    """Get next recommended learning item."""
    recommendations = []
    for domain in SKILL_DOMAINS:
        item = db.execute(
            "SELECT id, domain, level, topic, attempts FROM curriculum_items WHERE domain=? AND status='pending' ORDER BY level, id LIMIT 1",
            (domain,)
        ).fetchone()
        if item:
            recommendations.append({
                "id": item[0], "domain": item[1], "level": item[2],
                "topic": item[3], "attempts": item[4]
            })

    # Sort by least attempted first
    recommendations.sort(key=lambda x: x["attempts"])
    return {"next_items": recommendations, "count": len(recommendations)}


def show_progress(db):
    """Show progress across all domains."""
    progress = {}
    for domain, config in SKILL_DOMAINS.items():
        row = db.execute(
            "SELECT current_level, current_score FROM skill_levels WHERE domain=?",
            (domain,)
        ).fetchone()
        current_level = row[0] if row else 1
        score = row[1] if row else 0

        total_topics = sum(len(lv["topics"]) for lv in config["levels"])
        completed = db.execute(
            "SELECT COUNT(*) FROM curriculum_items WHERE domain=? AND status='completed'",
            (domain,)
        ).fetchone()[0]
        pending = db.execute(
            "SELECT COUNT(*) FROM curriculum_items WHERE domain=? AND status='pending'",
            (domain,)
        ).fetchone()[0]

        pct = round(completed / total_topics * 100, 1) if total_topics else 0
        progress[domain] = {
            "level": current_level,
            "max_level": len(config["levels"]),
            "score": score,
            "completed_topics": completed,
            "pending_topics": pending,
            "total_topics": total_topics,
            "progress_pct": pct
        }

    overall = sum(p["progress_pct"] for p in progress.values()) / len(progress) if progress else 0
    return {"progress": progress, "overall_pct": round(overall, 1)}


def adjust_curriculum(db):
    """Adaptive adjustment: promote level if threshold met, demote if struggling."""
    adjustments = []
    for domain, config in SKILL_DOMAINS.items():
        row = db.execute(
            "SELECT current_level, current_score FROM skill_levels WHERE domain=?",
            (domain,)
        ).fetchone()
        if not row:
            continue
        current_level, score = row

        # Check completion of current level
        current_config = None
        for lv in config["levels"]:
            if lv["level"] == current_level:
                current_config = lv
                break

        if not current_config:
            continue

        total_topics = len(current_config["topics"])
        completed = db.execute(
            "SELECT COUNT(*) FROM curriculum_items WHERE domain=? AND level=? AND status='completed'",
            (domain, current_level)
        ).fetchone()[0]

        # Promote if all topics completed and score above threshold
        if completed >= total_topics and score >= current_config["threshold"]:
            next_level = current_level + 1
            if next_level <= len(config["levels"]):
                db.execute(
                    "UPDATE skill_levels SET current_level=?, current_score=0, last_evaluated=datetime('now','localtime') WHERE domain=?",
                    (next_level, domain)
                )
                adjustments.append({
                    "domain": domain, "action": "promoted",
                    "from": current_level, "to": next_level
                })

        # Check for struggling (many failed attempts)
        failed = db.execute(
            "SELECT COUNT(*) FROM curriculum_items WHERE domain=? AND level=? AND attempts>=3 AND status='pending'",
            (domain, current_level)
        ).fetchone()[0]
        if failed > total_topics // 2 and current_level > 1:
            adjustments.append({
                "domain": domain, "action": "struggling",
                "level": current_level, "failed_topics": failed,
                "recommendation": "Review previous level or simplify exercises"
            })

    db.commit()
    return {"adjustments": adjustments, "count": len(adjustments)}


def do_status(db):
    total_items = db.execute("SELECT COUNT(*) FROM curriculum_items").fetchone()[0]
    completed = db.execute("SELECT COUNT(*) FROM curriculum_items WHERE status='completed'").fetchone()[0]
    domains = db.execute("SELECT domain, current_level, current_score FROM skill_levels").fetchall()
    return {
        "script": "ia_curriculum_planner.py",
        "id": 210,
        "db": str(DB_PATH),
        "total_items": total_items,
        "completed": completed,
        "domains": {d[0]: {"level": d[1], "score": d[2]} for d in domains},
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="IA Curriculum Planner — adaptive learning progression")
    parser.add_argument("--plan", action="store_true", help="Create/update curriculum plan")
    parser.add_argument("--next", action="store_true", help="Get next learning items")
    parser.add_argument("--progress", action="store_true", help="Show progress")
    parser.add_argument("--adjust", action="store_true", help="Adaptive adjustment")
    parser.add_argument("--once", action="store_true", help="Quick status")
    args = parser.parse_args()

    db = init_db()

    if args.plan:
        result = create_plan(db)
    elif args.next:
        result = get_next(db)
    elif args.progress:
        result = show_progress(db)
    elif args.adjust:
        result = adjust_curriculum(db)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
