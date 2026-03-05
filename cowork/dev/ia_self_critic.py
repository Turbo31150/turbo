#!/usr/bin/env python3
"""ia_self_critic.py (#187) — Auto-critique IA des reponses avant envoi.

Evalue et ameliore les reponses via M1 (qwen3-8b). Score completeness,
precision, clarity 0-100. Regenere si score <70, max 3 iterations.

Usage:
    python dev/ia_self_critic.py --once
    python dev/ia_self_critic.py --evaluate "The answer is 42 because..."
    python dev/ia_self_critic.py --improve "Short incomplete answer"
    python dev/ia_self_critic.py --score "Some response text"
    python dev/ia_self_critic.py --history
"""
import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "self_critic.db"

M1_URL = "http://127.0.0.1:1234/api/v1/chat"
M1_MODEL = "qwen3-8b"
MAX_ITERATIONS = 3
MIN_SCORE = 70


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        response_hash TEXT,
        response_preview TEXT,
        completeness INTEGER,
        precision INTEGER,
        clarity INTEGER,
        overall INTEGER,
        critique TEXT,
        improvements_json TEXT,
        iteration INTEGER DEFAULT 1,
        source TEXT DEFAULT 'local',
        word_count INTEGER,
        sentence_count INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS iterations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        eval_id INTEGER,
        iteration INTEGER,
        score_before INTEGER,
        score_after INTEGER,
        improved_text TEXT,
        FOREIGN KEY (eval_id) REFERENCES evaluations(id)
    )""")
    db.commit()
    return db


def query_m1(prompt, max_tokens=2048):
    """Query M1 via curl. Returns text or None on failure."""
    payload = json.dumps({
        "model": M1_MODEL,
        "input": f"/nothink\n{prompt}",
        "temperature": 0.2,
        "max_output_tokens": max_tokens,
        "stream": False,
        "store": False
    })
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "60", M1_URL,
             "-H", "Content-Type: application/json",
             "-d", payload],
            capture_output=True, text=True, timeout=65
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        # Extract last message block from output[]
        for item in reversed(data.get("output", [])):
            if item.get("type") == "message":
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        return c.get("text", "")
        # Fallback: direct content
        if data.get("output") and isinstance(data["output"], list):
            for item in data["output"]:
                if isinstance(item, dict) and "content" in item:
                    content = item["content"]
                    if isinstance(content, str):
                        return content
                    if isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict) and c.get("text"):
                                return c["text"]
        return None
    except Exception:
        return None


def analyze_text_local(text):
    """Local heuristic analysis of text structure."""
    words = text.split()
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    has_structure = any(m in text for m in ["1.", "2.", "- ", "* ", "##"])
    has_examples = any(kw in text.lower() for kw in [
        "example", "for instance", "e.g.", "such as", "par exemple"
    ])
    has_reasoning = any(kw in text.lower() for kw in [
        "because", "therefore", "since", "due to", "car", "donc", "parce"
    ])
    return {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "paragraph_count": len(paragraphs),
        "has_structure": has_structure,
        "has_examples": has_examples,
        "has_reasoning": has_reasoning,
        "avg_sentence_length": round(len(words) / max(len(sentences), 1), 1),
    }


def score_local(text):
    """Local scoring fallback (0-100 scale)."""
    a = analyze_text_local(text)
    comp = 30
    if a["word_count"] >= 20: comp += 10
    if a["word_count"] >= 50: comp += 10
    if a["word_count"] >= 100: comp += 10
    if a["has_structure"]: comp += 15
    if a["has_examples"]: comp += 15
    if a["has_reasoning"]: comp += 10
    comp = min(comp, 100)

    prec = 50
    hedges = ["maybe", "perhaps", "i think", "not sure", "might be", "possibly"]
    prec -= sum(5 for h in hedges if h in text.lower())
    if bool(re.search(r'\d+', text)): prec += 15
    if a["has_reasoning"]: prec += 15
    prec = max(0, min(prec, 100))

    clar = 40
    if 8 <= a["avg_sentence_length"] <= 25: clar += 20
    if a["has_structure"]: clar += 15
    if a["paragraph_count"] >= 2: clar += 10
    if a["word_count"] >= 30: clar += 10
    clar = max(0, min(clar, 100))

    overall = round(comp * 0.35 + prec * 0.35 + clar * 0.30)
    return {
        "completeness": comp, "precision": prec, "clarity": clar,
        "overall": overall, "source": "local"
    }


def score_via_m1(text):
    """Score via M1 critique. Returns dict with scores or None."""
    prompt = (
        "You are a response quality critic. Evaluate this response on 3 axes, "
        "each scored 0-100:\n"
        "- completeness: how thorough and complete\n"
        "- precision: how accurate and specific\n"
        "- clarity: how clear and well-structured\n\n"
        f"Response to evaluate:\n\"\"\"\n{text[:2000]}\n\"\"\"\n\n"
        "Reply ONLY with valid JSON: "
        "{\"completeness\": N, \"precision\": N, \"clarity\": N, \"critique\": \"...\", "
        "\"improvements\": [\"...\", \"...\"]}"
    )
    raw = query_m1(prompt, max_tokens=1024)
    if not raw:
        return None
    # Try to parse JSON from response
    try:
        # Find JSON in response
        match = re.search(r'\{[^{}]*"completeness"[^{}]*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            comp = max(0, min(int(data.get("completeness", 50)), 100))
            prec = max(0, min(int(data.get("precision", 50)), 100))
            clar = max(0, min(int(data.get("clarity", 50)), 100))
            overall = round(comp * 0.35 + prec * 0.35 + clar * 0.30)
            return {
                "completeness": comp, "precision": prec, "clarity": clar,
                "overall": overall, "source": "M1/qwen3-8b",
                "critique": data.get("critique", ""),
                "improvements": data.get("improvements", [])
            }
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return None


def evaluate_response(db, response):
    """Full evaluation: try M1, fallback local."""
    analysis = analyze_text_local(response)
    resp_hash = hashlib.sha256(response.encode()).hexdigest()[:16]

    # Try M1 first
    scores = score_via_m1(response)
    if not scores:
        scores = score_local(response)
        scores["critique"] = "Local heuristic evaluation (M1 unavailable)"
        scores["improvements"] = []
        if scores["overall"] < 70:
            scores["improvements"].append("Add more detail and examples")
        if not analysis["has_structure"]:
            scores["improvements"].append("Use structured formatting (lists, headers)")
        if not analysis["has_reasoning"]:
            scores["improvements"].append("Explain reasoning behind statements")

    db.execute(
        """INSERT INTO evaluations
           (ts, response_hash, response_preview, completeness, precision, clarity,
            overall, critique, improvements_json, source, word_count, sentence_count)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (time.time(), resp_hash, response[:200],
         scores["completeness"], scores["precision"], scores["clarity"],
         scores["overall"], scores.get("critique", ""),
         json.dumps(scores.get("improvements", []), ensure_ascii=False),
         scores["source"], analysis["word_count"], analysis["sentence_count"])
    )
    db.commit()

    grade = "A" if scores["overall"] >= 90 else "B" if scores["overall"] >= 80 else \
            "C" if scores["overall"] >= 65 else "D" if scores["overall"] >= 50 else "F"

    return {
        "status": "ok",
        "scores": {
            "completeness": scores["completeness"],
            "precision": scores["precision"],
            "clarity": scores["clarity"],
            "overall": scores["overall"]
        },
        "grade": grade,
        "critique": scores.get("critique", ""),
        "improvements": scores.get("improvements", []),
        "source": scores["source"],
        "analysis": analysis,
        "response_preview": response[:150]
    }


def improve_response(db, response):
    """Evaluate and iteratively improve if score <70, max 3 iterations."""
    current_text = response
    iterations = []

    for i in range(1, MAX_ITERATIONS + 1):
        eval_result = evaluate_response(db, current_text)
        score_before = eval_result["scores"]["overall"]
        iterations.append({
            "iteration": i,
            "score": score_before,
            "grade": eval_result["grade"],
            "source": eval_result["source"]
        })

        if score_before >= MIN_SCORE:
            break

        if i < MAX_ITERATIONS:
            # Ask M1 to improve
            prompt = (
                f"Improve this response. Current quality score: {score_before}/100.\n"
                f"Issues: {', '.join(eval_result['improvements'])}\n\n"
                f"Original response:\n\"\"\"\n{current_text[:1500]}\n\"\"\"\n\n"
                "Write an improved version that addresses all issues. "
                "Reply with ONLY the improved text, no meta-commentary."
            )
            improved = query_m1(prompt, max_tokens=2048)
            if improved and len(improved.strip()) > 20:
                eval_id = db.execute("SELECT MAX(id) FROM evaluations").fetchone()[0]
                db.execute(
                    "INSERT INTO iterations (ts, eval_id, iteration, score_before, score_after, improved_text) "
                    "VALUES (?,?,?,?,?,?)",
                    (time.time(), eval_id, i, score_before, 0, improved[:2000])
                )
                db.commit()
                current_text = improved.strip()
            else:
                break

    return {
        "status": "ok",
        "iterations": iterations,
        "total_iterations": len(iterations),
        "final_score": iterations[-1]["score"] if iterations else 0,
        "improved": len(iterations) > 1,
        "final_text_preview": current_text[:300],
        "met_threshold": iterations[-1]["score"] >= MIN_SCORE if iterations else False
    }


def score_only(response):
    """Quick score without DB storage."""
    scores = score_via_m1(response)
    if not scores:
        scores = score_local(response)
    grade = "A" if scores["overall"] >= 90 else "B" if scores["overall"] >= 80 else \
            "C" if scores["overall"] >= 65 else "D" if scores["overall"] >= 50 else "F"
    return {
        "status": "ok",
        "completeness": scores["completeness"],
        "precision": scores["precision"],
        "clarity": scores["clarity"],
        "overall": scores["overall"],
        "grade": grade,
        "source": scores["source"]
    }


def get_history(db, limit=20):
    """Get recent evaluations."""
    rows = db.execute(
        """SELECT ts, response_preview, completeness, precision, clarity, overall, source
           FROM evaluations ORDER BY ts DESC LIMIT ?""", (limit,)
    ).fetchall()
    return {
        "status": "ok",
        "total": db.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0],
        "avg_overall": round(db.execute(
            "SELECT COALESCE(AVG(overall), 0) FROM evaluations"
        ).fetchone()[0], 1),
        "history": [
            {
                "ts": datetime.fromtimestamp(r[0]).strftime("%Y-%m-%d %H:%M:%S"),
                "preview": r[1][:80], "completeness": r[2], "precision": r[3],
                "clarity": r[4], "overall": r[5], "source": r[6]
            }
            for r in rows
        ]
    }


def once(db):
    """Run once with demo evaluation."""
    demo_text = (
        "SQLite is a lightweight database engine. It stores data in a single file. "
        "It's good for local applications because it requires no server setup. "
        "For example, JARVIS uses SQLite for all its local data storage across "
        "19 tables with over 17,000 rows. This makes it ideal for embedded systems "
        "and desktop applications where simplicity and zero-configuration are key advantages."
    )
    demo_result = evaluate_response(db, demo_text)
    total = db.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]
    avg = round(db.execute("SELECT COALESCE(AVG(overall), 0) FROM evaluations").fetchone()[0], 1)

    return {
        "status": "ok",
        "mode": "once",
        "script": "ia_self_critic.py (#187)",
        "total_evaluations": total,
        "avg_quality": avg,
        "min_score_threshold": MIN_SCORE,
        "max_iterations": MAX_ITERATIONS,
        "demo": demo_result
    }


def main():
    parser = argparse.ArgumentParser(
        description="ia_self_critic.py (#187) — Auto-critique IA des reponses"
    )
    parser.add_argument("--evaluate", type=str, metavar="RESPONSE",
                        help="Evaluate a response text")
    parser.add_argument("--improve", type=str, metavar="RESPONSE",
                        help="Evaluate and iteratively improve (max 3 iterations)")
    parser.add_argument("--score", type=str, metavar="RESPONSE",
                        help="Quick score only (no DB storage)")
    parser.add_argument("--history", action="store_true",
                        help="Show evaluation history")
    parser.add_argument("--once", action="store_true",
                        help="Run once with demo evaluation")
    args = parser.parse_args()

    db = init_db()

    if args.evaluate:
        result = evaluate_response(db, args.evaluate)
    elif args.improve:
        result = improve_response(db, args.improve)
    elif args.score:
        result = score_only(args.score)
    elif args.history:
        result = get_history(db)
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        db.close()
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
