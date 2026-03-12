#!/usr/bin/env python3
"""ia_meta_optimizer.py — #212 Grid search hyperparameters for optimal model config.
Usage:
    python dev/ia_meta_optimizer.py --optimize
    python dev/ia_meta_optimizer.py --hyperparams
    python dev/ia_meta_optimizer.py --search '{"temperature":[0.1,0.3,0.5],"max_tokens":[512,1024]}'
    python dev/ia_meta_optimizer.py --best
    python dev/ia_meta_optimizer.py --once
"""
import argparse, json, sqlite3, time, math, urllib.request, os
from datetime import datetime
from pathlib import Path
from itertools import product

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "meta_optimizer.db"

# Standard test prompts for evaluation
STANDARD_PROMPTS = [
    {"id": "p1", "prompt": "Write a Python function to check if a number is prime. Return only the function.", "expected_contains": ["def ", "return"]},
    {"id": "p2", "prompt": "Explain what a REST API is in 2 sentences.", "expected_min_len": 50},
    {"id": "p3", "prompt": "Fix this code: def add(a,b) return a+b", "expected_contains": ["def add", ":"]},
    {"id": "p4", "prompt": "List 5 sorting algorithms.", "expected_min_len": 30},
    {"id": "p5", "prompt": "What is 17 * 23?", "expected_contains": ["391"]},
]

DEFAULT_SEARCH_SPACE = {
    "temperature": [0.1, 0.3, 0.5, 0.7],
    "max_tokens": [256, 512, 1024, 2048],
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS search_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        search_space TEXT,
        total_combos INTEGER,
        completed INTEGER DEFAULT 0,
        best_config TEXT,
        best_score REAL,
        status TEXT DEFAULT 'pending',
        started_at TEXT DEFAULT (datetime('now','localtime')),
        finished_at TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS trial_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        config TEXT NOT NULL,
        temperature REAL,
        max_tokens INTEGER,
        prompt_id TEXT,
        latency_ms REAL,
        output_len INTEGER,
        quality_score REAL,
        success INTEGER DEFAULT 1,
        error TEXT,
        ts TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(run_id) REFERENCES search_runs(id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS best_configs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model TEXT NOT NULL,
        temperature REAL,
        max_tokens INTEGER,
        avg_score REAL,
        avg_latency REAL,
        trials INTEGER,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.commit()
    return db


def _call_m1(prompt, temperature=0.2, max_tokens=1024, timeout=30):
    """Call M1 with specific hyperparams."""
    body = {
        "model": "qwen3-8b",
        "input": f"/nothink\n{prompt}",
        "temperature": temperature,
        "max_output_tokens": max_tokens,
        "stream": False,
        "store": False
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:1234/api/v1/chat",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode())
        latency = (time.perf_counter() - start) * 1000

        outputs = raw.get("output", [])
        msg_blocks = [o for o in outputs if o.get("type") == "message"]
        if msg_blocks:
            content = msg_blocks[-1].get("content", [{}])
            if isinstance(content, list):
                text = "".join(c.get("text", "") for c in content)
            else:
                text = str(content)
        else:
            text = str(raw)[:500]

        return text, latency, None
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return "", latency, str(e)


def _score_output(output, prompt_config):
    """Score output quality (0-100)."""
    if not output:
        return 0
    score = 0

    # Length check
    min_len = prompt_config.get("expected_min_len", 20)
    if len(output) >= min_len:
        score += 30
    elif len(output) > 0:
        score += 15

    # Contains check
    expected = prompt_config.get("expected_contains", [])
    if expected:
        matches = sum(1 for e in expected if e.lower() in output.lower())
        score += int((matches / len(expected)) * 50)
    else:
        score += 30  # No specific check, give base score

    # Coherence (simple: not too short, not garbage)
    if len(output) > 10 and not output.startswith("{"):
        score += 20

    return min(100, score)


def run_grid_search(db, search_space=None):
    """Execute grid search over hyperparameters."""
    if search_space is None:
        search_space = DEFAULT_SEARCH_SPACE
    if isinstance(search_space, str):
        search_space = json.loads(search_space)

    temps = search_space.get("temperature", [0.2])
    max_toks = search_space.get("max_tokens", [1024])
    combos = list(product(temps, max_toks))

    cur = db.execute(
        "INSERT INTO search_runs (search_space, total_combos, status) VALUES (?,?,?)",
        (json.dumps(search_space), len(combos), "running")
    )
    run_id = cur.lastrowid
    db.commit()

    best_config = None
    best_avg_score = -1
    combo_results = []

    for temp, max_tok in combos:
        scores = []
        latencies = []

        for p in STANDARD_PROMPTS:
            output, latency, error = _call_m1(p["prompt"], temperature=temp, max_tokens=max_tok)
            success = 1 if not error and output else 0
            quality = _score_output(output, p) if success else 0

            db.execute(
                "INSERT INTO trial_results (run_id, config, temperature, max_tokens, prompt_id, latency_ms, output_len, quality_score, success, error) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run_id, json.dumps({"temp": temp, "max_tokens": max_tok}),
                 temp, max_tok, p["id"], round(latency, 1), len(output), quality, success, error)
            )
            scores.append(quality)
            latencies.append(latency)

        avg_score = sum(scores) / len(scores) if scores else 0
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        entry = {
            "temperature": temp,
            "max_tokens": max_tok,
            "avg_score": round(avg_score, 1),
            "avg_latency_ms": round(avg_latency, 1),
            "trials": len(scores)
        }
        combo_results.append(entry)

        if avg_score > best_avg_score:
            best_avg_score = avg_score
            best_config = entry

    # Save best
    if best_config:
        db.execute(
            "INSERT INTO best_configs (model, temperature, max_tokens, avg_score, avg_latency, trials) VALUES (?,?,?,?,?,?)",
            ("M1/qwen3-8b", best_config["temperature"], best_config["max_tokens"],
             best_config["avg_score"], best_config["avg_latency_ms"], len(STANDARD_PROMPTS))
        )

    db.execute(
        "UPDATE search_runs SET completed=?, best_config=?, best_score=?, status='completed', finished_at=datetime('now','localtime') WHERE id=?",
        (len(combos), json.dumps(best_config) if best_config else None, best_avg_score, run_id)
    )
    db.commit()

    return {
        "run_id": run_id,
        "total_combos": len(combos),
        "results": sorted(combo_results, key=lambda x: x["avg_score"], reverse=True),
        "best": best_config,
        "status": "completed"
    }


def show_hyperparams(db):
    """Show current search space and defaults."""
    return {
        "default_search_space": DEFAULT_SEARCH_SPACE,
        "standard_prompts": len(STANDARD_PROMPTS),
        "target_model": "M1/qwen3-8b (127.0.0.1:1234)",
        "scoring": "quality(0-100) based on expected patterns + length + coherence"
    }


def get_best(db):
    """Get best configurations found."""
    rows = db.execute(
        "SELECT model, temperature, max_tokens, avg_score, avg_latency, trials, ts FROM best_configs ORDER BY avg_score DESC LIMIT 10"
    ).fetchall()
    return {
        "best_configs": [
            {"model": r[0], "temperature": r[1], "max_tokens": r[2],
             "avg_score": r[3], "avg_latency_ms": r[4], "trials": r[5], "ts": r[6]}
            for r in rows
        ]
    }


def do_status(db):
    total_runs = db.execute("SELECT COUNT(*) FROM search_runs").fetchone()[0]
    total_trials = db.execute("SELECT COUNT(*) FROM trial_results").fetchone()[0]
    best = db.execute(
        "SELECT temperature, max_tokens, avg_score FROM best_configs ORDER BY avg_score DESC LIMIT 1"
    ).fetchone()
    return {
        "script": "ia_meta_optimizer.py",
        "id": 212,
        "db": str(DB_PATH),
        "total_search_runs": total_runs,
        "total_trials": total_trials,
        "best_config": {"temp": best[0], "max_tokens": best[1], "score": best[2]} if best else None,
        "search_space": DEFAULT_SEARCH_SPACE,
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="IA Meta Optimizer — grid search hyperparameters")
    parser.add_argument("--optimize", action="store_true", help="Run default grid search")
    parser.add_argument("--hyperparams", action="store_true", help="Show search space")
    parser.add_argument("--search", type=str, metavar="JSON", help="Custom search space")
    parser.add_argument("--best", action="store_true", help="Show best configs found")
    parser.add_argument("--once", action="store_true", help="Quick status")
    args = parser.parse_args()

    db = init_db()

    if args.optimize:
        result = run_grid_search(db)
    elif args.hyperparams:
        result = show_hyperparams(db)
    elif args.search:
        result = run_grid_search(db, args.search)
    elif args.best:
        result = get_best(db)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
