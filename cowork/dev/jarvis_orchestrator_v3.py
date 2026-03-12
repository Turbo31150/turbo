#!/usr/bin/env python3
"""jarvis_orchestrator_v3.py — #216 Ultimate orchestrator v3: unified system dashboard.
Usage:
    python dev/jarvis_orchestrator_v3.py --start
    python dev/jarvis_orchestrator_v3.py --status
    python dev/jarvis_orchestrator_v3.py --config
    python dev/jarvis_orchestrator_v3.py --benchmark
    python dev/jarvis_orchestrator_v3.py --once
"""
import argparse, json, sqlite3, time, subprocess, os, urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DATA_DIR = DEV / "data"
DB_PATH = DATA_DIR / "orchestrator_v3.db"

# Cluster node definitions
CLUSTER_NODES = {
    "M1": {"url": "http://127.0.0.1:1234/api/v1/models", "type": "lmstudio", "desc": "6 GPU 46GB qwen3-8b"},
    "M2": {"url": "http://192.168.1.26:1234/api/v1/models", "type": "lmstudio", "desc": "3 GPU 24GB deepseek-coder"},
    "M3": {"url": "http://192.168.1.113:1234/api/v1/models", "type": "lmstudio", "desc": "1 GPU 8GB deepseek-r1"},
    "OL1": {"url": "http://127.0.0.1:11434/api/tags", "type": "ollama", "desc": "Ollama local+cloud 12 models"},
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS health_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        node TEXT NOT NULL,
        status TEXT DEFAULT 'unknown',
        latency_ms REAL,
        models_loaded INTEGER,
        details TEXT,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS subsystem_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subsystem TEXT NOT NULL,
        status TEXT DEFAULT 'unknown',
        details TEXT,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS benchmarks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        node TEXT,
        test_type TEXT,
        latency_ms REAL,
        tokens_per_sec REAL,
        success INTEGER DEFAULT 1,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS recovery_hints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        node TEXT,
        issue TEXT,
        hint TEXT,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.commit()
    return db


def _check_node(name, config, timeout=5):
    """Check a single cluster node."""
    url = config["url"]
    start = time.perf_counter()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        latency = (time.perf_counter() - start) * 1000

        if config["type"] == "lmstudio":
            models = data.get("data", data.get("models", []))
            loaded = [m for m in models if m.get("loaded_instances")]
            return {
                "status": "online",
                "latency_ms": round(latency, 1),
                "models_loaded": len(loaded),
                "models": [m.get("id", "") for m in loaded],
                "total_models": len(models)
            }
        elif config["type"] == "ollama":
            models = data.get("models", [])
            return {
                "status": "online",
                "latency_ms": round(latency, 1),
                "models_loaded": len(models),
                "models": [m.get("name", "") for m in models[:5]],
                "total_models": len(models)
            }
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return {
            "status": "offline",
            "latency_ms": round(latency, 1),
            "error": str(e)[:200],
            "models_loaded": 0
        }


def _check_databases():
    """Check all databases in data/ directory."""
    dbs = []
    total_size = 0
    total_rows = 0
    for db_file in sorted(DATA_DIR.glob("*.db")):
        if db_file.name == "orchestrator_v3.db":
            continue
        try:
            size = db_file.stat().st_size
            total_size += size
            conn = sqlite3.connect(str(db_file))
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            rows = 0
            for (tname,) in tables:
                try:
                    rows += conn.execute(f"SELECT COUNT(*) FROM [{tname}]").fetchone()[0]
                except Exception:
                    pass
            total_rows += rows
            conn.close()
            dbs.append({"name": db_file.name, "size_kb": round(size/1024, 1), "rows": rows, "tables": len(tables)})
        except Exception as e:
            dbs.append({"name": db_file.name, "error": str(e)})
    return {
        "count": len(dbs),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "total_rows": total_rows,
        "databases": sorted(dbs, key=lambda x: x.get("rows", 0), reverse=True)[:10]
    }


def _check_scripts():
    """Check dev/*.py scripts."""
    scripts = list(DEV.glob("*.py"))
    total_size = sum(s.stat().st_size for s in scripts)
    return {
        "count": len(scripts),
        "total_size_kb": round(total_size / 1024, 1),
        "newest": sorted(scripts, key=lambda s: s.stat().st_mtime, reverse=True)[0].name if scripts else None
    }


def _check_crons():
    """Check for running Python processes (crons/services)."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        if result.returncode == 0:
            lines = [l for l in result.stdout.strip().split("\n") if l.strip() and "python" in l.lower()]
            return {"running_python_processes": len(lines)}
    except Exception:
        pass
    return {"running_python_processes": 0}


def start_check(db):
    """Full system check — all subsystems."""
    results = {"ts": datetime.now().isoformat(), "subsystems": {}}

    # 1. Cluster nodes
    nodes = {}
    for name, config in CLUSTER_NODES.items():
        check = _check_node(name, config)
        nodes[name] = check
        db.execute(
            "INSERT INTO health_checks (node, status, latency_ms, models_loaded, details) VALUES (?,?,?,?,?)",
            (name, check["status"], check.get("latency_ms"), check.get("models_loaded", 0), json.dumps(check))
        )
    results["subsystems"]["cluster"] = {
        "nodes": nodes,
        "online": sum(1 for n in nodes.values() if n["status"] == "online"),
        "total": len(nodes)
    }

    # 2. Databases
    db_check = _check_databases()
    results["subsystems"]["databases"] = db_check
    db.execute(
        "INSERT INTO subsystem_status (subsystem, status, details) VALUES (?,?,?)",
        ("databases", "ok", json.dumps({"count": db_check["count"], "rows": db_check["total_rows"]}))
    )

    # 3. Scripts
    script_check = _check_scripts()
    results["subsystems"]["scripts"] = script_check
    db.execute(
        "INSERT INTO subsystem_status (subsystem, status, details) VALUES (?,?,?)",
        ("scripts", "ok", json.dumps(script_check))
    )

    # 4. Crons/processes
    cron_check = _check_crons()
    results["subsystems"]["processes"] = cron_check

    # 5. Generate recovery hints for offline nodes
    for name, check in nodes.items():
        if check["status"] == "offline":
            hints = _generate_hints(name)
            for hint in hints:
                db.execute(
                    "INSERT INTO recovery_hints (node, issue, hint) VALUES (?,?,?)",
                    (name, "offline", hint)
                )
            results["subsystems"]["cluster"]["nodes"][name]["recovery_hints"] = hints

    # Overall health score
    online = results["subsystems"]["cluster"]["online"]
    total_nodes = results["subsystems"]["cluster"]["total"]
    score = int((online / total_nodes) * 60 + (40 if db_check["count"] > 0 else 0))
    results["health_score"] = min(100, score)
    results["grade"] = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"

    db.commit()
    return results


def _generate_hints(node):
    """Generate auto-recovery hints for a node."""
    hints = {
        "M1": [
            "Check if LM Studio is running on this machine (127.0.0.1:1234)",
            "Restart LM Studio or load qwen3-8b model",
            "Verify no port conflict on 1234"
        ],
        "M2": [
            "Check network connectivity to 192.168.1.26",
            "Verify LM Studio is running on M2 machine",
            "ping 192.168.1.26 to verify network"
        ],
        "M3": [
            "Check network connectivity to 192.168.1.113",
            "Verify LM Studio is running on M3 machine",
            "GPU may be overheated — check temperatures"
        ],
        "OL1": [
            "Restart Ollama: 'ollama serve' or Windows service",
            "Check if port 11434 is free: netstat -an | findstr 11434",
            "Verify OLLAMA_NUM_PARALLEL=3 env var"
        ],
    }
    return hints.get(node, ["Check service status and restart if needed"])


def get_system_status(db):
    """Quick status from last check."""
    latest_checks = {}
    for node in CLUSTER_NODES:
        row = db.execute(
            "SELECT status, latency_ms, models_loaded, ts FROM health_checks WHERE node=? ORDER BY id DESC LIMIT 1",
            (node,)
        ).fetchone()
        if row:
            latest_checks[node] = {"status": row[0], "latency_ms": row[1], "models": row[2], "ts": row[3]}
        else:
            latest_checks[node] = {"status": "never_checked"}

    return {"nodes": latest_checks, "last_full_check": db.execute(
        "SELECT ts FROM subsystem_status ORDER BY id DESC LIMIT 1"
    ).fetchone()}


def get_config(db):
    """Show orchestrator configuration."""
    return {
        "cluster_nodes": {k: {"url": v["url"], "type": v["type"], "desc": v["desc"]}
                          for k, v in CLUSTER_NODES.items()},
        "data_dir": str(DATA_DIR),
        "scripts_dir": str(DEV),
        "script_count": len(list(DEV.glob("*.py"))),
        "db_count": len(list(DATA_DIR.glob("*.db")))
    }


def run_benchmark(db):
    """Quick benchmark of cluster nodes."""
    results = {}
    prompt = "Write a Python hello world program."

    for node, config in CLUSTER_NODES.items():
        start = time.perf_counter()
        try:
            if config["type"] == "lmstudio":
                body = json.dumps({
                    "model": "qwen3-8b" if node == "M1" else "auto",
                    "input": f"/nothink\n{prompt}",
                    "temperature": 0.2,
                    "max_output_tokens": 256,
                    "stream": False,
                    "store": False
                }).encode()
                url = config["url"].replace("/models", "/chat")
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            elif config["type"] == "ollama":
                body = json.dumps({
                    "model": "qwen3:1.7b",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False
                }).encode()
                url = "http://127.0.0.1:11434/api/chat"
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            else:
                continue

            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            latency = (time.perf_counter() - start) * 1000

            # Estimate tokens/sec
            if config["type"] == "ollama":
                output = data.get("message", {}).get("content", "")
                eval_count = data.get("eval_count", len(output) // 4)
                eval_duration = data.get("eval_duration", latency * 1e6)
                tps = eval_count / (eval_duration / 1e9) if eval_duration else 0
            else:
                outputs = data.get("output", [])
                output = ""
                for o in outputs:
                    if o.get("type") == "message":
                        content = o.get("content", [])
                        if isinstance(content, list):
                            output = "".join(c.get("text", "") for c in content)
                tps = len(output) / (latency / 1000) * 0.25 if latency > 0 else 0  # rough estimate

            results[node] = {
                "status": "ok",
                "latency_ms": round(latency, 1),
                "tokens_per_sec": round(tps, 1),
                "output_len": len(output)
            }
            db.execute(
                "INSERT INTO benchmarks (node, test_type, latency_ms, tokens_per_sec, success) VALUES (?,?,?,?,?)",
                (node, "quick", round(latency, 1), round(tps, 1), 1)
            )

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            results[node] = {"status": "failed", "latency_ms": round(latency, 1), "error": str(e)[:200]}
            db.execute(
                "INSERT INTO benchmarks (node, test_type, latency_ms, success) VALUES (?,?,?,?)",
                (node, "quick", round(latency, 1), 0)
            )

    db.commit()

    # Rank by speed
    ranked = sorted(
        [(k, v) for k, v in results.items() if v["status"] == "ok"],
        key=lambda x: x[1].get("latency_ms", 99999)
    )

    return {
        "benchmark": results,
        "ranking": [{"rank": i+1, "node": r[0], "latency_ms": r[1]["latency_ms"],
                      "tps": r[1].get("tokens_per_sec", 0)} for i, r in enumerate(ranked)],
        "fastest": ranked[0][0] if ranked else "none"
    }


def do_status(db):
    total_checks = db.execute("SELECT COUNT(*) FROM health_checks").fetchone()[0]
    total_benchmarks = db.execute("SELECT COUNT(*) FROM benchmarks").fetchone()[0]
    return {
        "script": "jarvis_orchestrator_v3.py",
        "id": 216,
        "db": str(DB_PATH),
        "cluster_nodes": list(CLUSTER_NODES.keys()),
        "total_health_checks": total_checks,
        "total_benchmarks": total_benchmarks,
        "scripts": len(list(DEV.glob("*.py"))),
        "databases": len(list(DATA_DIR.glob("*.db"))),
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Orchestrator v3 — unified system dashboard")
    parser.add_argument("--start", action="store_true", help="Full system check")
    parser.add_argument("--status", action="store_true", help="Quick status")
    parser.add_argument("--config", action="store_true", help="Show configuration")
    parser.add_argument("--benchmark", action="store_true", help="Quick cluster benchmark")
    parser.add_argument("--once", action="store_true", help="Status overview")
    args = parser.parse_args()

    db = init_db()

    if args.start:
        result = start_check(db)
    elif args.status:
        result = get_system_status(db)
    elif args.config:
        result = get_config(db)
    elif args.benchmark:
        result = run_benchmark(db)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
