#!/usr/bin/env python3
"""ia_transfer_learner.py — #211 Analyze and transfer skills between domains.
Usage:
    python dev/ia_transfer_learner.py --analyze
    python dev/ia_transfer_learner.py --transfer code trading
    python dev/ia_transfer_learner.py --evaluate
    python dev/ia_transfer_learner.py --once
"""
import argparse, json, sqlite3, time, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "transfer_learner.db"

# Cross-domain skill mapping: which skills in domain A help domain B
TRANSFER_MAP = {
    ("code", "trading"): {
        "transferable": ["data_analysis", "backtesting", "optimization", "testing", "automation"],
        "boost_pct": 25,
        "description": "Code skills enhance algorithmic trading implementation"
    },
    ("code", "nlp"): {
        "transferable": ["data_processing", "embeddings", "api_integration", "evaluation"],
        "boost_pct": 30,
        "description": "Code skills directly applicable to NLP pipeline building"
    },
    ("code", "reasoning"): {
        "transferable": ["algorithm_design", "debugging", "decomposition", "logic"],
        "boost_pct": 20,
        "description": "Systematic coding approach improves reasoning structure"
    },
    ("trading", "code"): {
        "transferable": ["quantitative_thinking", "risk_assessment", "data_driven"],
        "boost_pct": 10,
        "description": "Trading mindset brings quantitative rigor to code"
    },
    ("trading", "reasoning"): {
        "transferable": ["probability", "decision_under_uncertainty", "pattern_recognition"],
        "boost_pct": 15,
        "description": "Market analysis sharpens probabilistic reasoning"
    },
    ("nlp", "code"): {
        "transferable": ["text_processing", "regex", "parsing", "api_design"],
        "boost_pct": 15,
        "description": "NLP experience enriches text-heavy code tasks"
    },
    ("nlp", "reasoning"): {
        "transferable": ["context_understanding", "semantic_analysis", "ambiguity_resolution"],
        "boost_pct": 20,
        "description": "Language understanding improves reasoning clarity"
    },
    ("reasoning", "code"): {
        "transferable": ["problem_decomposition", "logical_proofs", "constraint_solving"],
        "boost_pct": 25,
        "description": "Strong reasoning enables better algorithm design"
    },
    ("reasoning", "trading"): {
        "transferable": ["causal_analysis", "hypothesis_testing", "decision_theory"],
        "boost_pct": 15,
        "description": "Reasoning skills improve trade decision quality"
    },
    ("reasoning", "nlp"): {
        "transferable": ["logical_structure", "inference", "evaluation_methodology"],
        "boost_pct": 10,
        "description": "Reasoning helps evaluate NLP model outputs"
    },
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS domain_skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        skill TEXT NOT NULL,
        proficiency REAL DEFAULT 0,
        source TEXT DEFAULT 'direct',
        last_updated TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(domain, skill)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_domain TEXT NOT NULL,
        to_domain TEXT NOT NULL,
        skills_transferred TEXT,
        boost_applied REAL,
        enriched_prompt TEXT,
        accuracy_before REAL,
        accuracy_after REAL,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transfer_id INTEGER,
        metric TEXT,
        score REAL,
        notes TEXT,
        ts TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(transfer_id) REFERENCES transfers(id)
    )""")
    db.commit()
    return db


def analyze_domains(db):
    """Analyze all domains and their transferable skills."""
    # Try to pull data from curriculum_planner.db
    curriculum_db = DEV / "data" / "curriculum_planner.db"
    domain_data = {}

    if curriculum_db.exists():
        try:
            conn = sqlite3.connect(str(curriculum_db))
            rows = conn.execute(
                "SELECT domain, current_level, current_score FROM skill_levels"
            ).fetchall()
            for domain, level, score in rows:
                domain_data[domain] = {"level": level, "score": score}

                # Get completed topics
                topics = conn.execute(
                    "SELECT topic, level FROM curriculum_items WHERE domain=? AND status='completed'",
                    (domain,)
                ).fetchall()
                domain_data[domain]["completed_topics"] = [t[0] for t in topics]
            conn.close()
        except Exception:
            pass

    # If no curriculum data, use defaults
    if not domain_data:
        for d in ["code", "trading", "nlp", "reasoning"]:
            domain_data[d] = {"level": 1, "score": 50, "completed_topics": []}

    # Analyze transferability
    transfers = []
    for (from_d, to_d), mapping in TRANSFER_MAP.items():
        if from_d in domain_data:
            from_score = domain_data[from_d].get("score", 0)
            effective_boost = mapping["boost_pct"] * (from_score / 100)
            transfers.append({
                "from": from_d,
                "to": to_d,
                "transferable_skills": mapping["transferable"],
                "potential_boost_pct": round(effective_boost, 1),
                "description": mapping["description"],
                "from_level": domain_data[from_d].get("level", 1)
            })

    transfers.sort(key=lambda x: x["potential_boost_pct"], reverse=True)

    return {
        "domains": domain_data,
        "transfer_opportunities": transfers[:10],
        "best_transfer": transfers[0] if transfers else None
    }


def do_transfer(db, from_domain, to_domain):
    """Execute a skill transfer between domains."""
    key = (from_domain, to_domain)
    mapping = TRANSFER_MAP.get(key)
    if not mapping:
        return {"error": f"No transfer mapping from {from_domain} to {to_domain}"}

    # Record transferred skills
    for skill in mapping["transferable"]:
        db.execute("""INSERT OR REPLACE INTO domain_skills
            (domain, skill, proficiency, source, last_updated)
            VALUES (?,?,?,?,datetime('now','localtime'))""",
            (to_domain, skill, mapping["boost_pct"], f"transfer:{from_domain}")
        )

    # Create enriched prompt template
    skills_str = ", ".join(mapping["transferable"])
    enriched_prompt = (
        f"Leveraging skills from {from_domain} ({skills_str}), "
        f"apply these to {to_domain} tasks. "
        f"{mapping['description']}. "
        f"Expected performance boost: ~{mapping['boost_pct']}%."
    )

    cur = db.execute(
        "INSERT INTO transfers (from_domain, to_domain, skills_transferred, boost_applied, enriched_prompt) VALUES (?,?,?,?,?)",
        (from_domain, to_domain, json.dumps(mapping["transferable"]), mapping["boost_pct"], enriched_prompt)
    )
    db.commit()

    return {
        "transfer_id": cur.lastrowid,
        "from": from_domain,
        "to": to_domain,
        "skills_transferred": mapping["transferable"],
        "boost_pct": mapping["boost_pct"],
        "enriched_prompt": enriched_prompt,
        "status": "applied"
    }


def evaluate_transfers(db):
    """Evaluate effectiveness of past transfers."""
    transfers = db.execute(
        "SELECT id, from_domain, to_domain, skills_transferred, boost_applied, accuracy_before, accuracy_after, ts FROM transfers ORDER BY id DESC LIMIT 10"
    ).fetchall()

    results = []
    for t in transfers:
        skills = json.loads(t[3]) if t[3] else []
        # Check if target domain skills improved
        skill_scores = []
        for skill in skills:
            row = db.execute(
                "SELECT proficiency FROM domain_skills WHERE domain=? AND skill=?",
                (t[2], skill)
            ).fetchone()
            if row:
                skill_scores.append(row[0])

        avg_proficiency = round(sum(skill_scores) / len(skill_scores), 1) if skill_scores else 0
        results.append({
            "id": t[0],
            "from": t[1],
            "to": t[2],
            "skills": skills,
            "boost_applied": t[4],
            "avg_proficiency": avg_proficiency,
            "effective": avg_proficiency > 0,
            "ts": t[7]
        })

    return {"evaluations": results, "total_transfers": len(results)}


def do_status(db):
    total_skills = db.execute("SELECT COUNT(*) FROM domain_skills").fetchone()[0]
    total_transfers = db.execute("SELECT COUNT(*) FROM transfers").fetchone()[0]
    domains = db.execute("SELECT DISTINCT domain FROM domain_skills").fetchall()
    return {
        "script": "ia_transfer_learner.py",
        "id": 211,
        "db": str(DB_PATH),
        "total_skills_tracked": total_skills,
        "total_transfers": total_transfers,
        "domains": [d[0] for d in domains],
        "available_transfers": len(TRANSFER_MAP),
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="IA Transfer Learner — cross-domain skill transfer")
    parser.add_argument("--analyze", action="store_true", help="Analyze domains and opportunities")
    parser.add_argument("--transfer", nargs=2, metavar=("FROM", "TO"), help="Transfer skills between domains")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate past transfers")
    parser.add_argument("--once", action="store_true", help="Quick status")
    args = parser.parse_args()

    db = init_db()

    if args.analyze:
        result = analyze_domains(db)
    elif args.transfer:
        result = do_transfer(db, args.transfer[0], args.transfer[1])
    elif args.evaluate:
        result = evaluate_transfers(db)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
