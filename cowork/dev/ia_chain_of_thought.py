#!/usr/bin/env python3
"""ia_chain_of_thought.py (#186) — Chain-of-Thought problem solver.

Decomposes a problem into reasoning steps, sends each to M1 (qwen3-8b).
Uses LM Studio Responses API: POST http://127.0.0.1:1234/api/v1/chat
Body: model=qwen3-8b, input="/nothink\\nPROMPT"
Extract: output[].type==message -> content[].type==output_text -> .text

Usage:
    python dev/ia_chain_of_thought.py --once
    python dev/ia_chain_of_thought.py --solve "How to optimize GPU memory for 3 concurrent models?"
    python dev/ia_chain_of_thought.py --steps "Design a cache system"
    python dev/ia_chain_of_thought.py --verify "The answer is X"
"""
import argparse
import json
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "chain_of_thought.db"

M1_URL = "http://127.0.0.1:1234/api/v1/chat"
M1_MODEL = "qwen3-8b"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS cot_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        problem TEXT,
        steps_json TEXT,
        final_answer TEXT,
        total_time REAL,
        step_count INTEGER
    )""")
    db.commit()
    return db


def call_m1(prompt, max_tokens=2048):
    """Call M1 (qwen3-8b) via LM Studio Responses API."""
    body = json.dumps({
        "model": M1_MODEL,
        "input": f"/nothink\n{prompt}",
        "temperature": 0.3,
        "max_output_tokens": max_tokens,
        "stream": False,
        "store": False
    })

    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "60", M1_URL,
             "-H", "Content-Type: application/json",
             "-d", body],
            capture_output=True, text=True, timeout=65
        )
        if result.returncode != 0:
            return None, f"curl error: {result.stderr[:200]}"

        data = json.loads(result.stdout)

        # Extract from output[].type==message -> content[].type==output_text -> .text
        for output_item in data.get("output", []):
            if output_item.get("type") == "message":
                for content_item in output_item.get("content", []):
                    if content_item.get("type") == "output_text":
                        return content_item.get("text", "").strip(), None

        # Fallback: try last output item
        outputs = data.get("output", [])
        if outputs:
            last = outputs[-1]
            if isinstance(last, dict):
                for c in last.get("content", []):
                    if "text" in c:
                        return c["text"].strip(), None

        return None, "No output_text found in response"

    except subprocess.TimeoutExpired:
        return None, "M1 timeout (60s)"
    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}"
    except Exception as e:
        return None, f"Error: {e}"


def decompose_problem(problem):
    """Ask M1 to decompose a problem into reasoning steps."""
    prompt = (
        f"Decompose this problem into 3-5 clear reasoning steps. "
        f"Return ONLY a JSON array of step strings, no explanation.\n\n"
        f"Problem: {problem}\n\n"
        f"Output format: [\"Step 1: ...\", \"Step 2: ...\", ...]"
    )
    text, err = call_m1(prompt, 1024)
    if err:
        return None, err

    # Try to parse JSON array from response
    try:
        # Find JSON array in text
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            steps = json.loads(text[start:end])
            if isinstance(steps, list):
                return steps, None
    except json.JSONDecodeError:
        pass

    # Fallback: split by numbered lines
    lines = [l.strip() for l in text.split("\n") if l.strip() and any(c.isalpha() for c in l)]
    if lines:
        return lines[:5], None

    return [f"Analyze: {problem}"], None


def solve_step(step, context=""):
    """Solve a single reasoning step."""
    prompt = f"Solve this reasoning step concisely (2-3 sentences max).\n"
    if context:
        prompt += f"Context from previous steps:\n{context}\n\n"
    prompt += f"Step: {step}"

    text, err = call_m1(prompt, 512)
    return text or f"(no response: {err})", err


def solve_problem(db, problem):
    """Full CoT: decompose -> solve each step -> synthesize."""
    start = time.time()

    # Step 1: Decompose
    steps, err = decompose_problem(problem)
    if err:
        return {"status": "error", "error": f"Decomposition failed: {err}", "agent": "M1/qwen3-8b"}

    # Step 2: Solve each step
    solved_steps = []
    context_so_far = ""
    for i, step in enumerate(steps):
        step_start = time.time()
        answer, step_err = solve_step(step, context_so_far)
        step_time = time.time() - step_start

        solved_steps.append({
            "step_num": i + 1,
            "step": step,
            "reasoning": answer,
            "time": round(step_time, 2),
            "error": step_err
        })
        context_so_far += f"\n{step}: {answer}"

    # Step 3: Synthesize final answer
    synth_prompt = (
        f"Based on this chain of reasoning, give a concise final answer.\n\n"
        f"Problem: {problem}\n\n"
        f"Reasoning chain:\n{context_so_far}\n\n"
        f"Final answer:"
    )
    final_answer, synth_err = call_m1(synth_prompt, 1024)
    total_time = time.time() - start

    # Save to DB
    db.execute(
        "INSERT INTO cot_sessions (ts, problem, steps_json, final_answer, total_time, step_count) VALUES (?,?,?,?,?,?)",
        (time.time(), problem, json.dumps(solved_steps), final_answer or "", total_time, len(steps))
    )
    db.commit()

    return {
        "status": "ok",
        "agent": "M1/qwen3-8b",
        "problem": problem,
        "steps": solved_steps,
        "final_answer": final_answer or f"(synthesis error: {synth_err})",
        "total_time": round(total_time, 2),
        "step_count": len(steps)
    }


def get_steps(db, limit=5):
    """Show recent CoT sessions."""
    rows = db.execute(
        "SELECT ts, problem, step_count, total_time, final_answer FROM cot_sessions ORDER BY ts DESC LIMIT ?",
        (limit,)
    ).fetchall()
    sessions = []
    for r in rows:
        sessions.append({
            "time": datetime.fromtimestamp(r[0]).isoformat(),
            "problem": r[1][:100],
            "steps": r[2],
            "time_seconds": round(r[3], 2),
            "answer_preview": (r[4] or "")[:150]
        })
    return {"status": "ok", "sessions": sessions}


def verify_answer(db, answer):
    """Ask M1 to verify/critique an answer."""
    prompt = (
        f"Critically evaluate this answer. Is it correct, complete, and well-reasoned? "
        f"Give a score 0-10 and explain.\n\nAnswer to evaluate: {answer}"
    )
    text, err = call_m1(prompt, 512)
    if err:
        return {"status": "error", "error": err, "agent": "M1/qwen3-8b"}

    return {
        "status": "ok",
        "agent": "M1/qwen3-8b",
        "original": answer[:200],
        "verification": text
    }


def once(db):
    """Run once: show stats and do a simple demo solve."""
    total = db.execute("SELECT COUNT(*) FROM cot_sessions").fetchone()[0]
    avg_time = db.execute("SELECT COALESCE(AVG(total_time), 0) FROM cot_sessions").fetchone()[0]
    avg_steps = db.execute("SELECT COALESCE(AVG(step_count), 0) FROM cot_sessions").fetchone()[0]

    # Quick demo
    demo = solve_problem(db, "What are the 3 main benefits of using SQLite for local data storage?")

    return {
        "status": "ok", "mode": "once",
        "total_sessions": total + 1,
        "avg_time": round(avg_time, 2),
        "avg_steps": round(avg_steps, 1),
        "demo": demo
    }


def main():
    parser = argparse.ArgumentParser(description="Chain-of-Thought Solver (#186) — M1/qwen3-8b reasoning")
    parser.add_argument("--solve", type=str, help="Solve a problem with chain-of-thought")
    parser.add_argument("--steps", action="store_true", help="Show recent CoT sessions")
    parser.add_argument("--verify", type=str, help="Verify an answer")
    parser.add_argument("--once", action="store_true", help="Run once with demo")
    args = parser.parse_args()

    db = init_db()

    if args.solve:
        result = solve_problem(db, args.solve)
    elif args.steps:
        result = get_steps(db)
    elif args.verify:
        result = verify_answer(db, args.verify)
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, default=str))
    db.close()


if __name__ == "__main__":
    main()
