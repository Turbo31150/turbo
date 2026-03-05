#!/usr/bin/env python3
"""continuous_coder.py — Orchestrateur de developpement continu autonome.

Boucle infinie: analyse → planifie → code → teste → deploie.
Se nourrit du COWORK_QUEUE.md et genere de nouveaux scripts en continu.
Coordonne self_feeding_engine, jarvis_self_evolve, continuous_test_runner.

Usage:
    python dev/continuous_coder.py --once                    # Un cycle
    python dev/continuous_coder.py --loop                    # Boucle continue
    python dev/continuous_coder.py --status                  # Statut du dev
    python dev/continuous_coder.py --queue                   # Queue de dev
    python dev/continuous_coder.py --plan "description"      # Planifier un nouveau script
    python dev/continuous_coder.py --history                 # Historique
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
WORKSPACE = DEV.parent
COWORK = WORKSPACE / "COWORK_QUEUE.md"
DB_PATH = DEV / "data" / "continuous_dev.db"
CLUSTER_URL_M1 = "http://127.0.0.1:1234/api/v1/chat"
CLUSTER_URL_OL1 = "http://127.0.0.1:11434/api/chat"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS dev_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts_created REAL, ts_started REAL, ts_completed REAL,
        name TEXT, description TEXT, filename TEXT,
        status TEXT DEFAULT 'pending',
        priority INTEGER DEFAULT 5,
        source TEXT DEFAULT 'auto',
        code_generated TEXT, test_result TEXT,
        cluster_node TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS dev_cycles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, cycle_type TEXT,
        tasks_processed INTEGER, tasks_succeeded INTEGER,
        tasks_failed INTEGER, duration_s REAL,
        details TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS code_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_scripts INTEGER, total_lines INTEGER,
        total_functions INTEGER, tests_passing INTEGER,
        health_score REAL)""")
    db.commit()
    return db

# ---------------------------------------------------------------------------
# Cluster communication
# ---------------------------------------------------------------------------
def ask_m1(prompt: str, max_tokens: int = 4096) -> str:
    """Interroge M1 qwen3-8b pour generation de code."""
    import urllib.request
    try:
        data = json.dumps({
            "model": "qwen3-8b",
            "input": f"/nothink\n{prompt}",
            "temperature": 0.2,
            "max_output_tokens": max_tokens,
            "stream": False,
            "store": False,
        }).encode()
        req = urllib.request.Request(CLUSTER_URL_M1, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            for block in reversed(result.get("output", [])):
                if block.get("type") == "message":
                    for c in block.get("content", []):
                        if c.get("type") == "output_text":
                            return c.get("text", "")
            return str(result.get("output", ""))
    except Exception as e:
        return f"ERROR: {e}"

def ask_ol1_fast(prompt: str) -> str:
    """Interroge OL1 qwen3:1.7b pour questions rapides."""
    import urllib.request
    try:
        data = json.dumps({
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }).encode()
        req = urllib.request.Request(CLUSTER_URL_OL1, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return result.get("message", {}).get("content", "")
    except Exception as e:
        return f"ERROR: {e}"

# ---------------------------------------------------------------------------
# COWORK Queue parser
# ---------------------------------------------------------------------------
def parse_cowork_queue() -> list:
    """Parse COWORK_QUEUE.md pour extraire les taches."""
    if not COWORK.exists():
        return []
    content = COWORK.read_text(encoding="utf-8", errors="ignore")
    tasks = []
    current_batch = ""
    current_task = None

    for line in content.split("\n"):
        batch_match = re.match(r"^## (BATCH \d+)", line)
        if batch_match:
            current_batch = batch_match.group(1)
            continue
        task_match = re.match(r"^### \d+\.\s+(\w+\.py)", line)
        if task_match:
            if current_task:
                tasks.append(current_task)
            current_task = {
                "name": task_match.group(1),
                "batch": current_batch,
                "description": "",
                "cli": "",
                "features": [],
            }
            continue
        if current_task:
            if line.startswith("- **CLI**:"):
                current_task["cli"] = line.split(":", 1)[1].strip().strip("`")
            elif line.startswith("- **Fonction**:"):
                current_task["description"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **Features**:"):
                current_task["features"] = [f.strip() for f in line.split(":", 1)[1].split(",")]

    if current_task:
        tasks.append(current_task)

    return tasks

def get_existing_scripts() -> set:
    """Retourne les noms des scripts existants."""
    return {f.name for f in DEV.glob("*.py") if not f.name.startswith("__")}

def get_pending_tasks() -> list:
    """Retourne les taches COWORK non encore implementees."""
    queue = parse_cowork_queue()
    existing = get_existing_scripts()
    return [t for t in queue if t["name"] not in existing]

# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------
def generate_script(task: dict) -> dict:
    """Genere un script Python via le cluster."""
    prompt = f"""Genere un script Python complet et fonctionnel pour JARVIS.

Nom: {task['name']}
Description: {task.get('description', 'Script utilitaire JARVIS')}
CLI: {task.get('cli', '--once / --help')}
Features: {', '.join(task.get('features', []))}

REGLES STRICTES:
1. Utiliser UNIQUEMENT la stdlib Python (pas de pip install)
2. argparse avec --help obligatoire
3. Sortie JSON (json.dumps)
4. Fonctionnel sur Windows
5. Docstring module complete
6. 100-300 lignes max
7. Gestion erreurs propre

Genere UNIQUEMENT le code Python, rien d'autre."""

    code = ask_m1(prompt, max_tokens=4096)

    # Extract code from markdown if needed
    code_match = re.search(r"```python\n(.*?)```", code, re.DOTALL)
    if code_match:
        code = code_match.group(1)

    # Basic validation
    is_valid = (
        "import " in code
        and "def " in code
        and "argparse" in code
        and "if __name__" in code
    )

    return {
        "name": task["name"],
        "code": code,
        "valid": is_valid,
        "lines": len(code.split("\n")),
    }

def test_script(filepath: Path) -> dict:
    """Teste un script avec --help."""
    try:
        result = subprocess.run(
            [sys.executable, str(filepath), "--help"],
            capture_output=True, text=True, timeout=10,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}
        )
        return {
            "file": filepath.name,
            "help_ok": result.returncode == 0,
            "output": result.stdout[:500] if result.stdout else "",
            "error": result.stderr[:300] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"file": filepath.name, "help_ok": False, "error": "timeout"}
    except Exception as e:
        return {"file": filepath.name, "help_ok": False, "error": str(e)}

# ---------------------------------------------------------------------------
# Dev cycle
# ---------------------------------------------------------------------------
def run_cycle(db, max_tasks: int = 3) -> dict:
    """Execute un cycle de developpement."""
    start = time.time()
    pending = get_pending_tasks()
    processed = 0
    succeeded = 0
    failed = 0
    details = []

    for task in pending[:max_tasks]:
        processed += 1
        # Generate
        gen = generate_script(task)

        if gen["valid"]:
            # Write to file
            filepath = DEV / task["name"]
            filepath.write_text(gen["code"], encoding="utf-8")

            # Test
            test = test_script(filepath)
            if test["help_ok"]:
                succeeded += 1
                status = "deployed"
            else:
                failed += 1
                status = "test_failed"
                # Remove broken file
                filepath.unlink(missing_ok=True)
        else:
            failed += 1
            status = "invalid_code"
            test = {"error": "Code validation failed"}

        db.execute(
            "INSERT INTO dev_tasks (ts_created, ts_started, ts_completed, name, description, filename, status, source, code_generated, test_result, cluster_node) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (time.time(), time.time(), time.time(), task["name"],
             task.get("description", ""), task["name"], status, "cowork",
             gen.get("code", "")[:2000], json.dumps(test), "M1")
        )
        details.append({
            "name": task["name"],
            "status": status,
            "lines": gen.get("lines", 0),
        })

    duration = time.time() - start

    # Record cycle
    db.execute(
        "INSERT INTO dev_cycles (ts, cycle_type, tasks_processed, tasks_succeeded, tasks_failed, duration_s, details) VALUES (?,?,?,?,?,?,?)",
        (time.time(), "generate", processed, succeeded, failed, round(duration, 1), json.dumps(details))
    )

    # Record metrics
    existing = get_existing_scripts()
    total_lines = 0
    total_funcs = 0
    for f in DEV.glob("*.py"):
        if f.name.startswith("__"):
            continue
        try:
            code = f.read_text(encoding="utf-8", errors="ignore")
            total_lines += len(code.split("\n"))
            total_funcs += code.count("\ndef ") + code.count("\nasync def ")
        except:
            pass

    db.execute(
        "INSERT INTO code_metrics (ts, total_scripts, total_lines, total_functions, tests_passing, health_score) VALUES (?,?,?,?,?,?)",
        (time.time(), len(existing), total_lines, total_funcs, succeeded, round(succeeded / max(processed, 1) * 100, 1))
    )
    db.commit()

    return {
        "cycle": "complete",
        "pending_in_queue": len(pending),
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "duration_s": round(duration, 1),
        "details": details,
        "total_scripts": len(existing),
        "total_lines": total_lines,
    }

def get_status(db) -> dict:
    """Statut du developpement."""
    existing = get_existing_scripts()
    pending = get_pending_tasks()
    cycles = db.execute("SELECT COUNT(*), SUM(tasks_succeeded), SUM(tasks_failed) FROM dev_cycles").fetchone()
    last_cycle = db.execute("SELECT ts, tasks_processed, tasks_succeeded FROM dev_cycles ORDER BY ts DESC LIMIT 1").fetchone()
    last_metrics = db.execute("SELECT total_scripts, total_lines, total_functions, health_score FROM code_metrics ORDER BY ts DESC LIMIT 1").fetchone()

    return {
        "scripts_existing": len(existing),
        "scripts_pending": len(pending),
        "pending_names": [t["name"] for t in pending[:10]],
        "total_cycles": cycles[0] or 0,
        "total_generated": cycles[1] or 0,
        "total_failed": cycles[2] or 0,
        "last_cycle": {
            "when": datetime.fromtimestamp(last_cycle[0]).isoformat() if last_cycle else None,
            "processed": last_cycle[1] if last_cycle else 0,
            "succeeded": last_cycle[2] if last_cycle else 0,
        } if last_cycle else None,
        "metrics": {
            "scripts": last_metrics[0] if last_metrics else len(existing),
            "lines": last_metrics[1] if last_metrics else 0,
            "functions": last_metrics[2] if last_metrics else 0,
            "health": last_metrics[3] if last_metrics else 0,
        } if last_metrics else None,
    }

def get_history(db) -> dict:
    """Historique de developpement."""
    tasks = db.execute(
        "SELECT name, status, ts_completed, cluster_node FROM dev_tasks ORDER BY ts_completed DESC LIMIT 20"
    ).fetchall()
    cycles = db.execute(
        "SELECT ts, cycle_type, tasks_processed, tasks_succeeded, duration_s FROM dev_cycles ORDER BY ts DESC LIMIT 10"
    ).fetchall()

    return {
        "recent_tasks": [{"name": n, "status": s, "when": datetime.fromtimestamp(t).isoformat() if t else None, "node": nd}
                          for n, s, t, nd in tasks],
        "recent_cycles": [{"when": datetime.fromtimestamp(t).isoformat(), "type": ct, "processed": p, "succeeded": s, "duration": d}
                           for t, ct, p, s, d in cycles],
    }

def plan_new(db, description: str) -> dict:
    """Planifie un nouveau script."""
    # Ask OL1 for a quick name and spec
    prompt = f"""Propose un nom de fichier Python et une spec courte pour:
{description}

Reponds en JSON: {{"filename": "nom.py", "cli": "--once / --help", "features": ["feat1", "feat2"]}}"""

    spec = ask_ol1_fast(prompt)
    try:
        spec_data = json.loads(spec)
    except:
        spec_data = {"filename": description.replace(" ", "_").lower()[:30] + ".py",
                     "cli": "--once / --help", "features": [description]}

    db.execute(
        "INSERT INTO dev_tasks (ts_created, name, description, filename, status, source) VALUES (?,?,?,?,?,?)",
        (time.time(), spec_data.get("filename", "new.py"), description,
         spec_data.get("filename", "new.py"), "planned", "manual")
    )
    db.commit()

    return {"planned": True, "spec": spec_data, "description": description}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="JARVIS Continuous Coder — Developpement autonome non-stop")
    parser.add_argument("--once", action="store_true", help="Un cycle de dev")
    parser.add_argument("--loop", action="store_true", help="Boucle continue (Ctrl+C pour arreter)")
    parser.add_argument("--status", action="store_true", help="Statut du dev")
    parser.add_argument("--queue", action="store_true", help="Queue COWORK")
    parser.add_argument("--plan", type=str, help="Planifier un nouveau script")
    parser.add_argument("--history", action="store_true", help="Historique")
    parser.add_argument("--max", type=int, default=3, help="Max taches par cycle")
    parser.add_argument("--interval", type=int, default=3600, help="Intervalle boucle (sec)")
    args = parser.parse_args()

    db = init_db()

    if args.status:
        print(json.dumps(get_status(db), indent=2, ensure_ascii=False))
    elif args.queue:
        pending = get_pending_tasks()
        print(json.dumps({
            "pending": len(pending),
            "tasks": [{"name": t["name"], "batch": t["batch"], "desc": t.get("description", "")[:80]}
                      for t in pending]
        }, indent=2, ensure_ascii=False))
    elif args.plan:
        result = plan_new(db, args.plan)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.history:
        print(json.dumps(get_history(db), indent=2, ensure_ascii=False))
    elif args.once:
        result = run_cycle(db, args.max)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.loop:
        print(f"Boucle continue demarree (intervalle: {args.interval}s, max: {args.max}/cycle)")
        try:
            while True:
                result = run_cycle(db, args.max)
                print(json.dumps(result, indent=2, ensure_ascii=False))
                if result["pending_in_queue"] == 0:
                    print("Queue vide. Attente...")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nArrete.")
    else:
        # Default: status
        print(json.dumps(get_status(db), indent=2, ensure_ascii=False))

    db.close()

if __name__ == "__main__":
    main()
