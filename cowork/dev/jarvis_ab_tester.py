#!/usr/bin/env python3
"""jarvis_ab_tester.py (#200) — A/B tester for AI models.

Sends same prompt to 2 different models, compares response length/quality.
Uses M1 (qwen3-8b) vs OL1 (qwen3:1.7b) by default.

Usage:
    python dev/jarvis_ab_tester.py --once
    python dev/jarvis_ab_tester.py --test "Explain Python decorators"
    python dev/jarvis_ab_tester.py --compare
    python dev/jarvis_ab_tester.py --winner
"""
import argparse
import json
import re
import sqlite3
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "ab_tester.db"

# Model configurations
MODELS = {
    "M1_qwen3-8b": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "type": "lmstudio",
        "model": "qwen3-8b",
        "label": "M1/qwen3-8b"
    },
    "OL1_qwen3-1.7b": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "qwen3:1.7b",
        "label": "OL1/qwen3:1.7b"
    }
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        prompt TEXT,
        model_a TEXT,
        model_b TEXT,
        response_a TEXT,
        response_b TEXT,
        latency_a_ms REAL,
        latency_b_ms REAL,
        length_a INTEGER,
        length_b INTEGER,
        score_a REAL,
        score_b REAL,
        winner TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS ab_stats (
        model TEXT PRIMARY KEY,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0,
        ties INTEGER DEFAULT 0,
        avg_latency_ms REAL DEFAULT 0,
        avg_score REAL DEFAULT 0,
        total_tests INTEGER DEFAULT 0
    )""")
    db.commit()
    return db


def call_lmstudio(url, model, prompt, max_tokens=1024):
    """Call LM Studio Responses API."""
    body = json.dumps({
        "model": model,
        "input": f"/nothink\n{prompt}",
        "temperature": 0.3,
        "max_output_tokens": max_tokens,
        "stream": False,
        "store": False
    })
    start = time.time()
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "60", url,
             "-H", "Content-Type: application/json",
             "-d", body],
            capture_output=True, text=True, timeout=65
        )
        latency = (time.time() - start) * 1000
        if result.returncode != 0:
            return None, latency, "curl error"

        data = json.loads(result.stdout)
        for item in reversed(data.get("output", [])):
            if item.get("type") == "message":
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        return c.get("text", "").strip(), latency, None
        return None, latency, "no output_text"
    except Exception as e:
        return None, (time.time() - start) * 1000, str(e)


def call_ollama(url, model, prompt, max_tokens=1024):
    """Call Ollama API."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    })
    start = time.time()
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "60", url,
             "-d", body],
            capture_output=True, text=True, timeout=65
        )
        latency = (time.time() - start) * 1000
        if result.returncode != 0:
            return None, latency, "curl error"

        data = json.loads(result.stdout)
        text = data.get("message", {}).get("content", "")
        # Remove thinking tags if present
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        return text, latency, None
    except Exception as e:
        return None, (time.time() - start) * 1000, str(e)


def call_model(config, prompt):
    """Call a model based on its config."""
    if config["type"] == "lmstudio":
        return call_lmstudio(config["url"], config["model"], prompt)
    elif config["type"] == "ollama":
        return call_ollama(config["url"], config["model"], prompt)
    return None, 0, "unknown type"


def score_response(text, prompt):
    """Score a response 0-100 based on heuristics."""
    if not text:
        return 0

    score = 30  # base

    words = text.split()
    wc = len(words)

    # Length (reasonable length is good)
    if wc >= 20:
        score += 5
    if wc >= 50:
        score += 10
    if wc >= 100:
        score += 5
    if wc > 500:
        score -= 5  # too verbose

    # Structure
    if any(m in text for m in ["1.", "2.", "- ", "* ", "##"]):
        score += 10

    # Examples
    if any(kw in text.lower() for kw in ["example", "for instance", "e.g.", "such as"]):
        score += 10

    # Relevance (check if prompt keywords appear in response)
    prompt_words = set(re.findall(r'\w+', prompt.lower()))
    response_words = set(re.findall(r'\w+', text.lower()))
    common = prompt_words & response_words
    relevance = len(common) / max(len(prompt_words), 1)
    score += int(relevance * 15)

    # Reasoning
    if any(kw in text.lower() for kw in ["because", "therefore", "since", "due to"]):
        score += 5

    # Code blocks
    if "```" in text:
        score += 5

    return max(0, min(score, 100))


def run_ab_test(db, prompt, model_a_key=None, model_b_key=None):
    """Run A/B test: send same prompt to 2 models in parallel."""
    model_keys = list(MODELS.keys())
    if model_a_key is None:
        model_a_key = model_keys[0]
    if model_b_key is None:
        model_b_key = model_keys[1] if len(model_keys) > 1 else model_keys[0]

    config_a = MODELS[model_a_key]
    config_b = MODELS[model_b_key]

    # Run in parallel
    results = {}

    def call_a():
        text, lat, err = call_model(config_a, prompt)
        results["a"] = (text, lat, err)

    def call_b():
        text, lat, err = call_model(config_b, prompt)
        results["b"] = (text, lat, err)

    t1 = threading.Thread(target=call_a)
    t2 = threading.Thread(target=call_b)
    t1.start()
    t2.start()
    t1.join(timeout=70)
    t2.join(timeout=70)

    text_a, lat_a, err_a = results.get("a", (None, 0, "thread_timeout"))
    text_b, lat_b, err_b = results.get("b", (None, 0, "thread_timeout"))

    # Score
    score_a = score_response(text_a, prompt) if text_a else 0
    score_b = score_response(text_b, prompt) if text_b else 0

    # Determine winner
    if score_a > score_b:
        winner = config_a["label"]
    elif score_b > score_a:
        winner = config_b["label"]
    else:
        # Tie-break by latency
        if lat_a < lat_b:
            winner = config_a["label"]
        elif lat_b < lat_a:
            winner = config_b["label"]
        else:
            winner = "tie"

    # Save to DB
    db.execute(
        """INSERT INTO tests (ts, prompt, model_a, model_b, response_a, response_b,
           latency_a_ms, latency_b_ms, length_a, length_b, score_a, score_b, winner)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (time.time(), prompt[:500], config_a["label"], config_b["label"],
         (text_a or "")[:2000], (text_b or "")[:2000],
         round(lat_a, 1), round(lat_b, 1),
         len(text_a) if text_a else 0, len(text_b) if text_b else 0,
         score_a, score_b, winner)
    )

    # Update stats
    for model_label, is_winner, score, latency in [
        (config_a["label"], winner == config_a["label"], score_a, lat_a),
        (config_b["label"], winner == config_b["label"], score_b, lat_b),
    ]:
        is_tie = winner == "tie"
        db.execute("""INSERT INTO ab_stats (model, wins, losses, ties, avg_latency_ms, avg_score, total_tests)
                      VALUES (?,?,?,?,?,?,1)
                      ON CONFLICT(model) DO UPDATE SET
                      wins = wins + ?,
                      losses = losses + ?,
                      ties = ties + ?,
                      avg_latency_ms = ((avg_latency_ms * total_tests) + ?) / (total_tests + 1),
                      avg_score = ((avg_score * total_tests) + ?) / (total_tests + 1),
                      total_tests = total_tests + 1""",
                   (model_label,
                    1 if is_winner and not is_tie else 0,
                    1 if not is_winner and not is_tie else 0,
                    1 if is_tie else 0,
                    latency, score,
                    1 if is_winner and not is_tie else 0,
                    1 if not is_winner and not is_tie else 0,
                    1 if is_tie else 0,
                    latency, score))

    db.commit()

    return {
        "status": "ok",
        "prompt": prompt[:200],
        "model_a": {
            "name": config_a["label"],
            "score": score_a,
            "latency_ms": round(lat_a, 1),
            "length": len(text_a) if text_a else 0,
            "error": err_a,
            "preview": (text_a or "")[:200]
        },
        "model_b": {
            "name": config_b["label"],
            "score": score_b,
            "latency_ms": round(lat_b, 1),
            "length": len(text_b) if text_b else 0,
            "error": err_b,
            "preview": (text_b or "")[:200]
        },
        "winner": winner,
        "score_diff": abs(score_a - score_b),
        "latency_diff_ms": round(abs(lat_a - lat_b), 1)
    }


def compare_history(db, limit=10):
    """Show recent A/B test results."""
    rows = db.execute(
        "SELECT ts, prompt, model_a, model_b, score_a, score_b, latency_a_ms, latency_b_ms, winner "
        "FROM tests ORDER BY ts DESC LIMIT ?",
        (limit,)
    ).fetchall()

    history = []
    for r in rows:
        history.append({
            "time": datetime.fromtimestamp(r[0]).isoformat(),
            "prompt": r[1][:80],
            "model_a": r[2], "model_b": r[3],
            "score_a": r[4], "score_b": r[5],
            "latency_a": round(r[6], 0), "latency_b": round(r[7], 0),
            "winner": r[8]
        })

    return {"status": "ok", "count": len(history), "tests": history}


def get_winner_stats(db):
    """Get overall winner stats."""
    rows = db.execute(
        "SELECT model, wins, losses, ties, avg_latency_ms, avg_score, total_tests FROM ab_stats ORDER BY wins DESC"
    ).fetchall()

    stats = []
    for r in rows:
        total = r[1] + r[2] + r[3]
        win_rate = round(r[1] / max(total, 1) * 100, 1)
        stats.append({
            "model": r[0],
            "wins": r[1], "losses": r[2], "ties": r[3],
            "win_rate_pct": win_rate,
            "avg_latency_ms": round(r[4], 1),
            "avg_score": round(r[5], 1),
            "total_tests": r[6]
        })

    total_tests = db.execute("SELECT COUNT(*) FROM tests").fetchone()[0]
    overall_winner = stats[0]["model"] if stats else "none"

    return {
        "status": "ok",
        "total_tests": total_tests,
        "overall_winner": overall_winner,
        "models": stats
    }


def once(db):
    """Run once: quick A/B test + stats."""
    test_result = run_ab_test(db, "What are the benefits of using SQLite for local data storage?")
    stats = get_winner_stats(db)

    return {
        "status": "ok", "mode": "once",
        "test": test_result,
        "stats": stats
    }


def main():
    parser = argparse.ArgumentParser(description="A/B Tester (#200) — Compare AI model responses")
    parser.add_argument("--test", type=str, help="Run A/B test with a prompt")
    parser.add_argument("--compare", action="store_true", help="Show recent test history")
    parser.add_argument("--winner", action="store_true", help="Show winner statistics")
    parser.add_argument("--once", action="store_true", help="Run once with demo")
    args = parser.parse_args()

    db = init_db()

    if args.test:
        result = run_ab_test(db, args.test)
    elif args.compare:
        result = compare_history(db)
    elif args.winner:
        result = get_winner_stats(db)
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, default=str))
    db.close()


if __name__ == "__main__":
    main()
