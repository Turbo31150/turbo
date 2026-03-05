#!/usr/bin/env python3
"""ia_experiment_runner.py — #203 Run experiments across models with stats.
Usage:
    python dev/ia_experiment_runner.py --run '{"name":"temp_test","hypothesis":"Lower temp = more consistent","prompt":"Write hello world in Python","models":["M1","OL1"],"repeats":3}'
    python dev/ia_experiment_runner.py --results
    python dev/ia_experiment_runner.py --compare 1
    python dev/ia_experiment_runner.py --report
    python dev/ia_experiment_runner.py --once
"""
import argparse, json, sqlite3, time, subprocess, os, math, urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "experiment_runner.db"

MODEL_ENDPOINTS = {
    "M1": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "body_template": {
            "model": "qwen3-8b",
            "temperature": 0.2,
            "max_output_tokens": 1024,
            "stream": False,
            "store": False
        },
        "input_key": "input",
        "input_prefix": "/nothink\n",
        "extract": "lmstudio"
    },
    "OL1": {
        "url": "http://127.0.0.1:11434/api/chat",
        "body_template": {
            "model": "qwen3:1.7b",
            "stream": False
        },
        "input_key": "messages",
        "extract": "ollama"
    }
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        hypothesis TEXT,
        prompt TEXT,
        models TEXT,
        repeats INTEGER DEFAULT 3,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT (datetime('now','localtime')),
        finished_at TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        experiment_id INTEGER,
        model TEXT,
        run_num INTEGER,
        latency_ms REAL,
        output_len INTEGER,
        output_text TEXT,
        success INTEGER DEFAULT 1,
        error TEXT,
        ts TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(experiment_id) REFERENCES experiments(id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        experiment_id INTEGER,
        model TEXT,
        mean_latency REAL,
        std_latency REAL,
        mean_output_len REAL,
        success_rate REAL,
        runs INTEGER,
        FOREIGN KEY(experiment_id) REFERENCES experiments(id)
    )""")
    db.commit()
    return db


def _call_model(model_name, prompt, timeout=60):
    """Call a model endpoint and return (output, latency_ms, error)."""
    cfg = MODEL_ENDPOINTS.get(model_name)
    if not cfg:
        return "", 0, f"Unknown model: {model_name}"

    body = dict(cfg["body_template"])
    if cfg["input_key"] == "messages":
        body["messages"] = [{"role": "user", "content": prompt}]
    else:
        body[cfg["input_key"]] = cfg.get("input_prefix", "") + prompt

    data = json.dumps(body).encode()
    req = urllib.request.Request(
        cfg["url"],
        data=data,
        headers={"Content-Type": "application/json"}
    )

    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode())
        latency = (time.perf_counter() - start) * 1000

        if cfg["extract"] == "ollama":
            output = raw.get("message", {}).get("content", "")
        else:
            outputs = raw.get("output", [])
            msg_blocks = [o for o in outputs if o.get("type") == "message"]
            if msg_blocks:
                output = msg_blocks[-1].get("content", [{}])
                if isinstance(output, list):
                    output = "".join(c.get("text", "") for c in output)
            elif outputs:
                output = str(outputs[-1])
            else:
                output = json.dumps(raw)[:500]

        return output, latency, None
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return "", latency, str(e)


def _mean(vals):
    return sum(vals) / len(vals) if vals else 0


def _std(vals):
    if len(vals) < 2:
        return 0
    m = _mean(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))


def run_experiment(db, spec):
    """Execute an experiment."""
    if isinstance(spec, str):
        spec = json.loads(spec)

    name = spec.get("name", "unnamed")
    hypothesis = spec.get("hypothesis", "")
    prompt = spec.get("prompt", "Hello")
    models = spec.get("models", ["M1"])
    repeats = spec.get("repeats", 3)

    cur = db.execute(
        "INSERT INTO experiments (name, hypothesis, prompt, models, repeats, status) VALUES (?,?,?,?,?,?)",
        (name, hypothesis, prompt, json.dumps(models), repeats, "running")
    )
    exp_id = cur.lastrowid
    db.commit()

    all_results = {}
    for model in models:
        all_results[model] = []
        for run in range(1, repeats + 1):
            output, latency, error = _call_model(model, prompt)
            success = 1 if not error else 0
            db.execute(
                "INSERT INTO results (experiment_id, model, run_num, latency_ms, output_len, output_text, success, error) VALUES (?,?,?,?,?,?,?,?)",
                (exp_id, model, run, round(latency, 2), len(output), output[:5000], success, error)
            )
            all_results[model].append({
                "run": run, "latency_ms": round(latency, 2),
                "output_len": len(output), "success": bool(success)
            })

        lats = [r["latency_ms"] for r in all_results[model] if r["success"]]
        olens = [r["output_len"] for r in all_results[model] if r["success"]]
        succ = sum(1 for r in all_results[model] if r["success"])
        db.execute(
            "INSERT INTO stats (experiment_id, model, mean_latency, std_latency, mean_output_len, success_rate, runs) VALUES (?,?,?,?,?,?,?)",
            (exp_id, model, round(_mean(lats), 2), round(_std(lats), 2),
             round(_mean(olens), 1), round(succ / repeats * 100, 1), repeats)
        )

    db.execute(
        "UPDATE experiments SET status='completed', finished_at=datetime('now','localtime') WHERE id=?",
        (exp_id,)
    )
    db.commit()

    return {
        "experiment_id": exp_id,
        "name": name,
        "hypothesis": hypothesis,
        "models": models,
        "repeats": repeats,
        "results": all_results,
        "status": "completed"
    }


def get_results(db, limit=10):
    """Show recent experiment results."""
    exps = db.execute(
        "SELECT id, name, hypothesis, status, created_at FROM experiments ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    result = []
    for eid, ename, ehyp, estatus, ecreated in exps:
        stats = db.execute(
            "SELECT model, mean_latency, std_latency, mean_output_len, success_rate, runs FROM stats WHERE experiment_id=?",
            (eid,)
        ).fetchall()
        result.append({
            "id": eid, "name": ename, "hypothesis": ehyp, "status": estatus,
            "created": ecreated,
            "stats": [{"model": s[0], "mean_latency": s[1], "std_latency": s[2],
                        "mean_output_len": s[3], "success_rate": s[4], "runs": s[5]} for s in stats]
        })
    return {"experiments": result, "total": len(result)}


def compare_experiment(db, exp_id):
    """Compare models for a specific experiment."""
    exp = db.execute("SELECT name, hypothesis, prompt FROM experiments WHERE id=?", (exp_id,)).fetchone()
    if not exp:
        return {"error": f"Experiment {exp_id} not found"}

    stats = db.execute(
        "SELECT model, mean_latency, std_latency, mean_output_len, success_rate FROM stats WHERE experiment_id=? ORDER BY mean_latency",
        (exp_id,)
    ).fetchall()

    comparison = []
    best_latency = None
    for s in stats:
        entry = {
            "model": s[0], "mean_latency_ms": s[1], "std_latency_ms": s[2],
            "mean_output_len": s[3], "success_rate": s[4]
        }
        if best_latency is None:
            best_latency = s[1]
            entry["fastest"] = True
        comparison.append(entry)

    return {
        "experiment_id": exp_id,
        "name": exp[0],
        "hypothesis": exp[1],
        "comparison": comparison,
        "verdict": f"Fastest: {comparison[0]['model']}" if comparison else "No data"
    }


def do_status(db):
    total = db.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    total_runs = db.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    recent = db.execute(
        "SELECT id, name, status FROM experiments ORDER BY id DESC LIMIT 3"
    ).fetchall()
    return {
        "script": "ia_experiment_runner.py",
        "id": 203,
        "db": str(DB_PATH),
        "total_experiments": total,
        "total_runs": total_runs,
        "recent": [{"id": r[0], "name": r[1], "status": r[2]} for r in recent],
        "available_models": list(MODEL_ENDPOINTS.keys()),
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="IA Experiment Runner — A/B test models")
    parser.add_argument("--run", type=str, metavar="SPEC_JSON", help="Run experiment from JSON spec")
    parser.add_argument("--results", action="store_true", help="Show recent results")
    parser.add_argument("--compare", type=int, metavar="EXP_ID", help="Compare models for experiment")
    parser.add_argument("--report", action="store_true", help="Full report")
    parser.add_argument("--once", action="store_true", help="Show status and exit")
    args = parser.parse_args()

    db = init_db()

    if args.run:
        result = run_experiment(db, args.run)
    elif args.results:
        result = get_results(db)
    elif args.compare:
        result = compare_experiment(db, args.compare)
    elif args.report:
        result = get_results(db, limit=50)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
