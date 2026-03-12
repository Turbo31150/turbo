#!/usr/bin/env python3
"""ia_peer_reviewer.py — AI-powered code peer review with dual model consensus.
COWORK #226 — Batch 103: IA Collaborative

Usage:
    python dev/ia_peer_reviewer.py --review path/to/file.py
    python dev/ia_peer_reviewer.py --criteria
    python dev/ia_peer_reviewer.py --improve path/to/file.py
    python dev/ia_peer_reviewer.py --report
    python dev/ia_peer_reviewer.py --once
"""
import argparse, json, sqlite3, time, subprocess, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "peer_reviewer.db"

REVIEW_CRITERIA = {
    "readability": {"weight": 0.20, "description": "Code clarity, naming, structure"},
    "correctness": {"weight": 0.25, "description": "Logic errors, edge cases, bugs"},
    "performance": {"weight": 0.15, "description": "Efficiency, complexity, bottlenecks"},
    "security": {"weight": 0.15, "description": "Input validation, injection, secrets"},
    "maintainability": {"weight": 0.15, "description": "Modularity, DRY, documentation"},
    "style": {"weight": 0.10, "description": "PEP8, formatting, consistency"},
}

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_hash TEXT,
        lines_count INTEGER,
        m1_review TEXT,
        ol1_review TEXT,
        merged_comments TEXT,
        quality_score REAL,
        criteria_scores TEXT,
        duration_ms INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS improvements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        review_id INTEGER,
        ts TEXT NOT NULL,
        file_path TEXT NOT NULL,
        suggestions TEXT,
        improved_code TEXT,
        model TEXT,
        FOREIGN KEY (review_id) REFERENCES reviews(id)
    )""")
    db.commit()
    return db

def read_file(filepath):
    """Read file content."""
    try:
        p = Path(filepath)
        if not p.exists():
            return None, f"File not found: {filepath}"
        content = p.read_text(encoding="utf-8", errors="replace")
        return content, None
    except Exception as e:
        return None, str(e)

def file_hash(content):
    import hashlib
    return hashlib.md5(content.encode()).hexdigest()[:16]

def query_m1(prompt):
    """Query M1."""
    payload = json.dumps({
        "model": "qwen3-8b",
        "input": f"/nothink/n{prompt}",
        "temperature": 0.2,
        "max_output_tokens": 1024,
        "stream": False,
        "store": False
    })
    try:
        cmd = f'curl -s --max-time 60 http://127.0.0.1:1234/api/v1/chat -H "Content-Type: application/json" -d {json.dumps(payload)}'
        start = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=65, shell=True)
        elapsed = int((time.time() - start) * 1000)
        if r.stdout.strip():
            data = json.loads(r.stdout)
            for item in reversed(data.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return c.get("text", "").strip(), elapsed
        return None, elapsed
    except Exception:
        return None, 0

def query_ol1(prompt):
    """Query OL1."""
    payload = json.dumps({
        "model": "qwen3:1.7b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    })
    try:
        cmd = f'curl -s --max-time 60 http://127.0.0.1:11434/api/chat -d {json.dumps(payload)}'
        start = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=65, shell=True)
        elapsed = int((time.time() - start) * 1000)
        if r.stdout.strip():
            data = json.loads(r.stdout)
            content = data.get("message", {}).get("content", "")
            import re
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            return content.strip(), elapsed
        return None, elapsed
    except Exception:
        return None, 0

def merge_reviews(m1_review, ol1_review):
    """Merge unique comments from both reviews."""
    comments = []
    if m1_review:
        comments.append({"source": "M1", "review": m1_review[:800]})
    if ol1_review:
        comments.append({"source": "OL1", "review": ol1_review[:800]})
    return comments

def do_review(filepath):
    db = init_db()
    content, err = read_file(filepath)
    if err:
        db.close()
        return {"error": err}

    lines = content.count("\n") + 1
    fhash = file_hash(content)
    code_preview = content[:2000]

    review_prompt = f"Review ce code Python. Pour chaque critere donne un score /10 et des commentaires:\n- Readability\n- Correctness\n- Performance\n- Security\n- Maintainability\n- Style\n\nCode:\n```\n{code_preview}\n```\n\nFormat: CRITERE: X/10 - commentaire"

    start_total = time.time()

    # Query both models
    m1_review, m1_ms = query_m1(review_prompt)
    ol1_review, ol1_ms = query_ol1(review_prompt)

    total_ms = int((time.time() - start_total) * 1000)
    merged = merge_reviews(m1_review, ol1_review)

    # Simple quality score (average of available reviews length as proxy)
    quality_score = 0.0
    review_count = 0
    if m1_review:
        quality_score += min(10, len(m1_review) / 100)
        review_count += 1
    if ol1_review:
        quality_score += min(10, len(ol1_review) / 100)
        review_count += 1
    if review_count:
        quality_score = round(quality_score / review_count, 1)

    db.execute("""INSERT INTO reviews (ts, file_path, file_hash, lines_count, m1_review, ol1_review,
                  merged_comments, quality_score, duration_ms) VALUES (?,?,?,?,?,?,?,?,?)""",
               (datetime.now().isoformat(), str(filepath), fhash, lines,
                m1_review[:2000] if m1_review else None,
                ol1_review[:2000] if ol1_review else None,
                json.dumps(merged), quality_score, total_ms))
    db.commit()

    result = {
        "action": "review",
        "file": str(filepath),
        "lines": lines,
        "m1_review": m1_review[:1000] if m1_review else "M1 unavailable",
        "m1_duration_ms": m1_ms,
        "ol1_review": ol1_review[:1000] if ol1_review else "OL1 unavailable",
        "ol1_duration_ms": ol1_ms,
        "quality_score": quality_score,
        "total_duration_ms": total_ms,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_criteria():
    return {
        "action": "criteria",
        "criteria": REVIEW_CRITERIA,
        "total_weight": sum(c["weight"] for c in REVIEW_CRITERIA.values()),
        "ts": datetime.now().isoformat()
    }

def do_improve(filepath):
    db = init_db()
    content, err = read_file(filepath)
    if err:
        db.close()
        return {"error": err}

    code_preview = content[:2000]
    prompt = f"Ameliore ce code Python. Liste les ameliorations et fournis le code ameliore.\n\nCode:\n```\n{code_preview}\n```\n\nReponds avec: AMELIORATIONS: (liste) puis CODE: (code ameliore)"

    improved, elapsed = query_m1(prompt)

    review = db.execute("SELECT id FROM reviews WHERE file_path=? ORDER BY id DESC LIMIT 1", (str(filepath),)).fetchone()
    review_id = review[0] if review else None

    db.execute("INSERT INTO improvements (review_id, ts, file_path, suggestions, improved_code, model) VALUES (?,?,?,?,?,?)",
               (review_id, datetime.now().isoformat(), str(filepath), improved[:2000] if improved else None, None, "M1"))
    db.commit()

    result = {
        "action": "improve",
        "file": str(filepath),
        "suggestions": improved[:1500] if improved else "M1 unavailable",
        "duration_ms": elapsed,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_report():
    db = init_db()
    total = db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    avg_score = db.execute("SELECT AVG(quality_score) FROM reviews").fetchone()[0] or 0
    recent = db.execute("SELECT ts, file_path, quality_score, duration_ms FROM reviews ORDER BY id DESC LIMIT 10").fetchall()
    improvements = db.execute("SELECT COUNT(*) FROM improvements").fetchone()[0]

    result = {
        "action": "report",
        "total_reviews": total,
        "avg_quality_score": round(avg_score, 1),
        "total_improvements": improvements,
        "recent_reviews": [{"ts": r[0], "file": r[1], "score": r[2], "duration_ms": r[3]} for r in recent],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    total = db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    avg = db.execute("SELECT AVG(quality_score) FROM reviews").fetchone()[0] or 0
    result = {
        "status": "ok",
        "total_reviews": total,
        "avg_quality_score": round(avg, 1),
        "criteria": list(REVIEW_CRITERIA.keys()),
        "models": ["M1 (qwen3-8b)", "OL1 (qwen3:1.7b)"],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="IA Peer Reviewer — COWORK #226")
    parser.add_argument("--review", type=str, metavar="FILE", help="Review a code file")
    parser.add_argument("--criteria", action="store_true", help="Show review criteria")
    parser.add_argument("--improve", type=str, metavar="FILE", help="Suggest improvements")
    parser.add_argument("--report", action="store_true", help="Show review report")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.review:
        print(json.dumps(do_review(args.review), ensure_ascii=False, indent=2))
    elif args.criteria:
        print(json.dumps(do_criteria(), ensure_ascii=False, indent=2))
    elif args.improve:
        print(json.dumps(do_improve(args.improve), ensure_ascii=False, indent=2))
    elif args.report:
        print(json.dumps(do_report(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
