#!/usr/bin/env python3
"""ia_fact_checker.py — Automatic fact checking (#259).

Sends statement to multiple models (M1+OL1), compares responses,
confidence scoring based on agreement.

Usage:
    python dev/ia_fact_checker.py --once
    python dev/ia_fact_checker.py --check "STATEMENT"
    python dev/ia_fact_checker.py --sources
    python dev/ia_fact_checker.py --confidence
    python dev/ia_fact_checker.py --history
"""
import argparse
import json
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "fact_checker.db"

M1_URL = "http://127.0.0.1:1234/api/v1/chat"
OL1_URL = "http://127.0.0.1:11434/api/chat"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        statement TEXT NOT NULL,
        m1_verdict TEXT,
        ol1_verdict TEXT,
        agreement REAL,
        confidence REAL,
        final_verdict TEXT,
        total_latency_ms REAL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        check_id INTEGER,
        model TEXT NOT NULL,
        response TEXT,
        verdict TEXT,
        latency_ms REAL,
        error TEXT
    )""")
    db.commit()
    return db


def call_m1(prompt):
    """Call M1."""
    body = json.dumps({
        "model": "qwen3-8b",
        "input": f"/nothink\n{prompt}",
        "temperature": 0.1,
        "max_output_tokens": 512,
        "stream": False,
        "store": False,
    })
    start = time.time()
    try:
        out = subprocess.check_output(
            ["curl", "-s", "--max-time", "30", M1_URL,
             "-H", "Content-Type: application/json", "-d", body],
            stderr=subprocess.DEVNULL, text=True, timeout=35,
        )
        latency = (time.time() - start) * 1000
        data = json.loads(out)
        output = data.get("output", [])
        content = ""
        for item in reversed(output):
            if item.get("type") == "message":
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        content = c.get("text", "")
                        break
                if content:
                    break
        return content, round(latency, 1), None
    except Exception as e:
        return None, round((time.time() - start) * 1000, 1), str(e)


def call_ol1(prompt):
    """Call OL1 (Ollama)."""
    body = json.dumps({
        "model": "qwen3:1.7b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    })
    start = time.time()
    try:
        out = subprocess.check_output(
            ["curl", "-s", "--max-time", "30", f"{OL1_URL}",
             "-d", body],
            stderr=subprocess.DEVNULL, text=True, timeout=35,
        )
        latency = (time.time() - start) * 1000
        data = json.loads(out)
        content = data.get("message", {}).get("content", "")
        return content, round(latency, 1), None
    except Exception as e:
        return None, round((time.time() - start) * 1000, 1), str(e)


def extract_verdict(response):
    """Extract TRUE/FALSE/UNCERTAIN from response."""
    if not response:
        return "unknown"
    resp_lower = response.lower()
    # Count indicators
    true_indicators = sum(1 for k in ["true", "correct", "accurate", "yes", "factual", "verified"] if k in resp_lower)
    false_indicators = sum(1 for k in ["false", "incorrect", "inaccurate", "no", "wrong", "misleading"] if k in resp_lower)
    uncertain_indicators = sum(1 for k in ["uncertain", "unclear", "depends", "partially", "debatable", "mixed"] if k in resp_lower)

    if true_indicators > false_indicators and true_indicators > uncertain_indicators:
        return "TRUE"
    if false_indicators > true_indicators and false_indicators > uncertain_indicators:
        return "FALSE"
    if uncertain_indicators > 0:
        return "UNCERTAIN"
    return "UNCERTAIN"


def calculate_agreement(verdict1, verdict2):
    """Calculate agreement between two verdicts."""
    if verdict1 == verdict2:
        return 1.0
    if {verdict1, verdict2} == {"TRUE", "FALSE"}:
        return 0.0
    return 0.5  # One uncertain


def do_check(statement):
    """Check a statement against multiple models."""
    db = init_db()
    now = datetime.now()
    total_start = time.time()

    fact_prompt = f"""Evaluate whether the following statement is TRUE, FALSE, or UNCERTAIN.
Explain briefly why, then state your verdict clearly.

Statement: "{statement}"

Verdict (TRUE/FALSE/UNCERTAIN):"""

    # Call M1
    m1_resp, m1_lat, m1_err = call_m1(fact_prompt)
    m1_verdict = extract_verdict(m1_resp) if m1_resp else "error"

    # Call OL1
    ol1_resp, ol1_lat, ol1_err = call_ol1(fact_prompt)
    ol1_verdict = extract_verdict(ol1_resp) if ol1_resp else "error"

    # Calculate agreement and confidence
    valid_verdicts = [v for v in [m1_verdict, ol1_verdict] if v not in ("error", "unknown")]
    if len(valid_verdicts) == 2:
        agreement = calculate_agreement(valid_verdicts[0], valid_verdicts[1])
        confidence = agreement * 0.8 + 0.2  # Base confidence 0.2
    elif len(valid_verdicts) == 1:
        agreement = 0.5
        confidence = 0.4
    else:
        agreement = 0.0
        confidence = 0.1

    # Final verdict
    if agreement == 1.0:
        final_verdict = valid_verdicts[0]
    elif len(valid_verdicts) >= 1:
        final_verdict = valid_verdicts[0]  # Trust M1 more (higher weight)
    else:
        final_verdict = "UNCERTAIN"

    total_latency = (time.time() - total_start) * 1000

    check_id = db.execute(
        "INSERT INTO checks (ts, statement, m1_verdict, ol1_verdict, agreement, confidence, final_verdict, total_latency_ms) VALUES (?,?,?,?,?,?,?,?)",
        (now.isoformat(), statement, m1_verdict, ol1_verdict,
         round(agreement, 3), round(confidence, 3), final_verdict, round(total_latency, 1)),
    ).lastrowid

    db.execute(
        "INSERT INTO responses (check_id, model, response, verdict, latency_ms, error) VALUES (?,?,?,?,?,?)",
        (check_id, "M1/qwen3-8b", (m1_resp or "")[:1000], m1_verdict, m1_lat, m1_err),
    )
    db.execute(
        "INSERT INTO responses (check_id, model, response, verdict, latency_ms, error) VALUES (?,?,?,?,?,?)",
        (check_id, "OL1/qwen3:1.7b", (ol1_resp or "")[:1000], ol1_verdict, ol1_lat, ol1_err),
    )
    db.commit()

    result = {
        "ts": now.isoformat(), "action": "check", "check_id": check_id,
        "statement": statement,
        "verdicts": {
            "M1": {"verdict": m1_verdict, "response": (m1_resp or "")[:200], "latency_ms": m1_lat},
            "OL1": {"verdict": ol1_verdict, "response": (ol1_resp or "")[:200], "latency_ms": ol1_lat},
        },
        "agreement": round(agreement, 3),
        "confidence": round(confidence, 3),
        "final_verdict": final_verdict,
        "total_latency_ms": round(total_latency, 1),
    }
    db.close()
    return result


def do_sources():
    """Show model responses for last check."""
    db = init_db()
    last = db.execute("SELECT id, statement FROM checks ORDER BY id DESC LIMIT 1").fetchone()
    if not last:
        db.close()
        return {"ts": datetime.now().isoformat(), "action": "sources", "message": "No checks yet"}

    responses = db.execute(
        "SELECT model, response, verdict, latency_ms FROM responses WHERE check_id=?",
        (last[0],),
    ).fetchall()

    result = {
        "ts": datetime.now().isoformat(), "action": "sources",
        "check_id": last[0], "statement": last[1],
        "sources": [
            {"model": r[0], "response": (r[1] or "")[:300], "verdict": r[2], "latency_ms": r[3]}
            for r in responses
        ],
    }
    db.close()
    return result


def do_confidence():
    """Show confidence statistics."""
    db = init_db()
    avg_conf = db.execute("SELECT AVG(confidence) FROM checks").fetchone()[0]
    avg_agree = db.execute("SELECT AVG(agreement) FROM checks").fetchone()[0]
    by_verdict = db.execute(
        "SELECT final_verdict, COUNT(*) FROM checks GROUP BY final_verdict"
    ).fetchall()

    result = {
        "ts": datetime.now().isoformat(), "action": "confidence",
        "total_checks": db.execute("SELECT COUNT(*) FROM checks").fetchone()[0],
        "avg_confidence": round(avg_conf or 0, 3),
        "avg_agreement": round(avg_agree or 0, 3),
        "by_verdict": {r[0]: r[1] for r in by_verdict},
    }
    db.close()
    return result


def do_history():
    """Show check history."""
    db = init_db()
    rows = db.execute(
        "SELECT id, ts, statement, final_verdict, confidence, agreement FROM checks ORDER BY id DESC LIMIT 20"
    ).fetchall()

    result = {
        "ts": datetime.now().isoformat(), "action": "history",
        "total": len(rows),
        "checks": [
            {"id": r[0], "ts": r[1], "statement": r[2][:100],
             "verdict": r[3], "confidence": r[4], "agreement": r[5]}
            for r in rows
        ],
    }
    db.close()
    return result


def do_status():
    db = init_db()
    result = {
        "ts": datetime.now().isoformat(), "script": "ia_fact_checker.py", "script_id": 259,
        "db": str(DB_PATH),
        "total_checks": db.execute("SELECT COUNT(*) FROM checks").fetchone()[0],
        "total_responses": db.execute("SELECT COUNT(*) FROM responses").fetchone()[0],
        "status": "ok",
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="ia_fact_checker.py — Fact checking (#259)")
    parser.add_argument("--check", type=str, metavar="STATEMENT", help="Check a statement")
    parser.add_argument("--sources", action="store_true", help="Show sources for last check")
    parser.add_argument("--confidence", action="store_true", help="Show confidence stats")
    parser.add_argument("--history", action="store_true", help="Show check history")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.check:
        result = do_check(args.check)
    elif args.sources:
        result = do_sources()
    elif args.confidence:
        result = do_confidence()
    elif args.history:
        result = do_history()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
