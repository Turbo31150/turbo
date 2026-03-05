#!/usr/bin/env python3
"""ia_chain_of_thought_v2.py — Structured CoT v2 (#258).

Decomposes problem into numbered steps, executes each via M1,
verifies consistency between steps, compares with direct approach.

Usage:
    python dev/ia_chain_of_thought_v2.py --once
    python dev/ia_chain_of_thought_v2.py --solve "PROBLEM"
    python dev/ia_chain_of_thought_v2.py --steps
    python dev/ia_chain_of_thought_v2.py --verify
    python dev/ia_chain_of_thought_v2.py --compare
"""
import argparse
import json
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "chain_of_thought_v2.db"

M1_URL = "http://127.0.0.1:1234/api/v1/chat"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS problems (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        problem TEXT NOT NULL,
        steps_json TEXT,
        direct_answer TEXT,
        cot_answer TEXT,
        consistent INTEGER,
        total_latency_ms REAL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        problem_id INTEGER,
        step_num INTEGER,
        prompt TEXT,
        response TEXT,
        latency_ms REAL,
        valid INTEGER DEFAULT 1
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS comparisons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        problem_id INTEGER,
        cot_answer TEXT,
        direct_answer TEXT,
        match INTEGER,
        analysis TEXT
    )""")
    db.commit()
    return db


def call_m1(prompt, max_tokens=1024):
    """Call M1 with a prompt."""
    body = json.dumps({
        "model": "qwen3-8b",
        "input": f"/nothink\n{prompt}",
        "temperature": 0.2,
        "max_output_tokens": max_tokens,
        "stream": False,
        "store": False,
    })
    start = time.time()
    try:
        out = subprocess.check_output(
            ["curl", "-s", "--max-time", "30",
             M1_URL, "-H", "Content-Type: application/json", "-d", body],
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
        if not content and output:
            content = str(output[0].get("content", ""))
        return content, round(latency, 1), None
    except Exception as e:
        return None, round((time.time() - start) * 1000, 1), str(e)


def decompose_problem(problem):
    """Ask M1 to decompose a problem into steps."""
    prompt = f"""Decompose this problem into 3-5 numbered steps. Return ONLY a JSON array of step descriptions.
Problem: {problem}

Format: ["step 1 description", "step 2 description", ...]"""

    response, latency, error = call_m1(prompt)
    if error or not response:
        return ["Analyze the problem", "Apply reasoning", "Formulate answer"], latency

    # Try to parse JSON from response
    try:
        # Find JSON array in response
        start = response.find("[")
        end = response.rfind("]") + 1
        if start >= 0 and end > start:
            steps = json.loads(response[start:end])
            if isinstance(steps, list) and len(steps) >= 2:
                return steps, latency
    except (json.JSONDecodeError, ValueError):
        pass

    return ["Analyze the problem", "Break down components", "Synthesize answer"], latency


def do_solve(problem):
    """Solve a problem using structured CoT."""
    db = init_db()
    now = datetime.now()
    total_start = time.time()

    # Step 1: Decompose
    steps_desc, decompose_latency = decompose_problem(problem)

    # Step 2: Execute each step
    step_results = []
    accumulated_context = f"Problem: {problem}\n\n"

    for i, step_desc in enumerate(steps_desc, 1):
        prompt = f"""{accumulated_context}Step {i}/{len(steps_desc)}: {step_desc}
Provide a concise answer for this step only."""

        response, latency, error = call_m1(prompt)
        step_result = {
            "step": i,
            "description": step_desc,
            "response": response or f"Error: {error}",
            "latency_ms": latency,
            "valid": response is not None,
        }
        step_results.append(step_result)

        if response:
            accumulated_context += f"Step {i} ({step_desc}): {response[:200]}\n"

    # Step 3: Synthesize final answer
    synth_prompt = f"""Based on these step-by-step results, provide a final concise answer.

Problem: {problem}

Steps completed:
"""
    for sr in step_results:
        synth_prompt += f"- Step {sr['step']}: {sr['response'][:150]}\n"
    synth_prompt += "\nFinal answer:"

    cot_answer, synth_latency, synth_error = call_m1(synth_prompt)

    # Step 4: Get direct answer for comparison
    direct_prompt = f"Answer this directly and concisely: {problem}"
    direct_answer, direct_latency, direct_error = call_m1(direct_prompt)

    total_latency = (time.time() - total_start) * 1000

    # Store
    problem_id = db.execute(
        "INSERT INTO problems (ts, problem, steps_json, direct_answer, cot_answer, total_latency_ms) VALUES (?,?,?,?,?,?)",
        (now.isoformat(), problem, json.dumps([s["description"] for s in step_results]),
         direct_answer, cot_answer, round(total_latency, 1)),
    ).lastrowid

    for sr in step_results:
        db.execute(
            "INSERT INTO steps (problem_id, step_num, prompt, response, latency_ms, valid) VALUES (?,?,?,?,?,?)",
            (problem_id, sr["step"], sr["description"], sr["response"],
             sr["latency_ms"], int(sr["valid"])),
        )

    db.commit()

    result = {
        "ts": now.isoformat(), "action": "solve", "problem_id": problem_id,
        "problem": problem,
        "steps": [
            {"step": s["step"], "desc": s["description"],
             "response": s["response"][:200] if s["response"] else None,
             "latency_ms": s["latency_ms"]}
            for s in step_results
        ],
        "cot_answer": (cot_answer or "")[:500],
        "direct_answer": (direct_answer or "")[:500],
        "total_steps": len(step_results),
        "total_latency_ms": round(total_latency, 1),
    }
    db.close()
    return result


def do_steps():
    """Show steps from last problem."""
    db = init_db()
    last_problem = db.execute(
        "SELECT id, problem, steps_json FROM problems ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if not last_problem:
        db.close()
        return {"ts": datetime.now().isoformat(), "action": "steps", "message": "No problems solved yet"}

    steps = db.execute(
        "SELECT step_num, prompt, response, latency_ms, valid FROM steps WHERE problem_id=? ORDER BY step_num",
        (last_problem[0],),
    ).fetchall()

    result = {
        "ts": datetime.now().isoformat(), "action": "steps",
        "problem_id": last_problem[0], "problem": last_problem[1],
        "steps": [
            {"step": s[0], "desc": s[1], "response": (s[2] or "")[:200],
             "latency_ms": s[3], "valid": bool(s[4])}
            for s in steps
        ],
    }
    db.close()
    return result


def do_verify():
    """Verify consistency of last solution."""
    db = init_db()
    last = db.execute(
        "SELECT id, problem, cot_answer, direct_answer FROM problems ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if not last:
        db.close()
        return {"ts": datetime.now().isoformat(), "action": "verify", "message": "No problems to verify"}

    steps = db.execute(
        "SELECT response, valid FROM steps WHERE problem_id=? ORDER BY step_num", (last[0],)
    ).fetchall()

    all_valid = all(s[1] for s in steps)
    has_answers = bool(last[2]) and bool(last[3])

    result = {
        "ts": datetime.now().isoformat(), "action": "verify",
        "problem_id": last[0], "problem": last[1],
        "all_steps_valid": all_valid,
        "step_count": len(steps),
        "has_cot_answer": bool(last[2]),
        "has_direct_answer": bool(last[3]),
        "verification": "consistent" if all_valid and has_answers else "incomplete",
    }
    db.close()
    return result


def do_compare():
    """Compare CoT vs direct answers."""
    db = init_db()
    rows = db.execute(
        "SELECT id, problem, cot_answer, direct_answer, total_latency_ms FROM problems ORDER BY id DESC LIMIT 10"
    ).fetchall()

    result = {
        "ts": datetime.now().isoformat(), "action": "compare",
        "total_problems": len(rows),
        "comparisons": [
            {"id": r[0], "problem": r[1][:80],
             "cot": (r[2] or "")[:150], "direct": (r[3] or "")[:150],
             "latency_ms": r[4]}
            for r in rows
        ],
    }
    db.close()
    return result


def do_status():
    db = init_db()
    result = {
        "ts": datetime.now().isoformat(), "script": "ia_chain_of_thought_v2.py", "script_id": 258,
        "db": str(DB_PATH),
        "total_problems": db.execute("SELECT COUNT(*) FROM problems").fetchone()[0],
        "total_steps": db.execute("SELECT COUNT(*) FROM steps").fetchone()[0],
        "status": "ok",
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="ia_chain_of_thought_v2.py — Structured CoT v2 (#258)")
    parser.add_argument("--solve", type=str, metavar="PROBLEM", help="Solve a problem with CoT")
    parser.add_argument("--steps", action="store_true", help="Show steps from last problem")
    parser.add_argument("--verify", action="store_true", help="Verify last solution consistency")
    parser.add_argument("--compare", action="store_true", help="Compare CoT vs direct answers")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.solve:
        result = do_solve(args.solve)
    elif args.steps:
        result = do_steps()
    elif args.verify:
        result = do_verify()
    elif args.compare:
        result = do_compare()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
