#!/usr/bin/env python3
"""JARVIS Master Autonome — Cerveau permanent du cluster.

Orchestre des VAGUES de taches en cascade sur le cluster IA.
Chaque vague contient plusieurs sous-taches distribuees aux noeuds.

Planning des vagues:
  - Toutes les 30min : Health + Heartbeat (rapide, 2min)
  - Toutes les 1h    : Maintenance Vague (scan, repair, optimize)
  - Toutes les 2h    : Intelligence Vague (code, learn, benchmark)
  - Toutes les 3h    : Deep Vague (audit, refactor, improve)
  - Toutes les 6h    : Full Pipeline (185 taches cluster)
  - Toutes les 24h   : Report + Cleanup

Auto-reparation: detecte les erreurs dans les logs, les corrige, relance.
Telegram: rapporte les resultats et alertes proactives.

Usage:
    python cowork/dev/jarvis_master_autonome.py              # Lancer le master
    python cowork/dev/jarvis_master_autonome.py --status      # Voir l'etat
    python cowork/dev/jarvis_master_autonome.py --once        # Une seule passe
    python cowork/dev/jarvis_master_autonome.py --dry-run     # Simulation
"""

import json, os, sqlite3, subprocess, sys, time, traceback
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Paths ────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
TURBO = SCRIPT_DIR.parent.parent
DATA_DIR = TURBO / "data"
DB_PATH = DATA_DIR / "master_autonome.db"
PID_FILE = DATA_DIR / "master_autonome.pid"
LOG_FILE = DATA_DIR / "master_autonome.log"

# ── Telegram ─────────────────────────────────────────────────
def _load_env():
    env_path = TURBO / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

_load_env()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", os.environ.get("TELEGRAM_BOT_TOKEN", ""))
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT", "2010747443")

# ── Cluster Nodes ────────────────────────────────────────────
NODES = {
    "M1": {"url": "http://127.0.0.1:1234/api/v1/chat", "model": "qwen3-8b",
            "prefix": "/nothink\n", "timeout": 60, "type": "lmstudio", "max_tokens": 1024},
    "M2": {"url": "http://192.168.1.26:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b",
            "prefix": "", "timeout": 90, "type": "lmstudio", "max_tokens": 2048},
    "M3": {"url": "http://192.168.1.113:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b",
            "prefix": "", "timeout": 90, "type": "lmstudio", "max_tokens": 2048},
    "OL1": {"url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b",
             "timeout": 30, "type": "ollama", "max_tokens": 512},
}

node_health = {n: {"alive": False, "fails": 0, "latency": 0} for n in NODES}

# ── HTTP + Query ─────────────────────────────────────────────
def _http_post(url, body, timeout_s):
    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=timeout_s)
    return json.loads(resp.read().decode("utf-8", "replace"))

def check_node(name):
    node = NODES[name]
    t0 = time.time()
    try:
        if node["type"] == "ollama":
            d = _http_post(node["url"], {"model": node["model"],
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False, "think": False}, 10)
            ok = "message" in d
        else:
            d = _http_post(node["url"], {"model": node["model"],
                "input": node.get("prefix", "") + "ping",
                "temperature": 0.1, "max_output_tokens": 5,
                "stream": False, "store": False}, 15)
            ok = "output" in d
        return ok, (time.time() - t0) * 1000
    except Exception:
        return False, (time.time() - t0) * 1000

def health_check_all():
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(check_node, n): n for n in NODES}
        for f in as_completed(futs):
            name = futs[f]
            alive, lat = f.result()
            node_health[name] = {"alive": alive, "fails": 0 if alive else node_health[name]["fails"] + 1,
                                  "latency": lat}
    online = [n for n, h in node_health.items() if h["alive"]]
    return online

def query_node(name, prompt, timeout_override=None):
    node = NODES[name]
    timeout = timeout_override or node["timeout"]
    t0 = time.time()
    try:
        if node["type"] == "ollama":
            d = _http_post(node["url"], {"model": node["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "think": False}, timeout)
            text = d.get("message", {}).get("content", "").strip()
        else:
            d = _http_post(node["url"], {"model": node["model"],
                "input": node.get("prefix", "") + prompt,
                "temperature": 0.2, "max_output_tokens": node.get("max_tokens", 1024),
                "stream": False, "store": False}, timeout)
            text = ""
            for item in reversed(d.get("output", [])):
                if item.get("type") == "message":
                    c = item.get("content", "")
                    text = c.strip() if isinstance(c, str) else str(c)
                    break
        elapsed = time.time() - t0
        if text:
            return text, elapsed, None
        return None, elapsed, "empty response"
    except Exception as e:
        return None, time.time() - t0, str(e)[:120]

def get_alive_nodes():
    alive = [n for n, h in node_health.items() if h["alive"] and h["fails"] < 3]
    return alive if alive else ["M1"]

# ── Telegram ─────────────────────────────────────────────────
def telegram_send(msg):
    if not TELEGRAM_TOKEN:
        return
    try:
        import urllib.request
        body = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg[:4000], "parse_mode": "Markdown"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

# ── Database ─────────────────────────────────────────────────
def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH), timeout=30)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("""CREATE TABLE IF NOT EXISTS master_waves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        wave_type TEXT, timestamp TEXT, tasks_total INTEGER,
        tasks_ok INTEGER, tasks_failed INTEGER, duration_s REAL,
        nodes_used TEXT, errors TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS master_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        wave_id INTEGER, task_name TEXT, node TEXT,
        status TEXT, duration_s REAL, result TEXT, error TEXT,
        timestamp TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS master_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        wave_type TEXT UNIQUE, interval_min INTEGER,
        last_run TEXT, next_run TEXT, run_count INTEGER DEFAULT 0,
        enabled INTEGER DEFAULT 1
    )""")
    db.commit()
    # Init schedule if empty
    if db.execute("SELECT COUNT(*) FROM master_schedule").fetchone()[0] == 0:
        for wave, interval in WAVE_SCHEDULE.items():
            db.execute("INSERT INTO master_schedule (wave_type, interval_min, last_run, next_run) VALUES (?,?,?,?)",
                       (wave, interval, "", datetime.now().strftime("%Y-%m-%dT%H:%M:%S")))
        db.commit()
    return db

# ── Wave Definitions ─────────────────────────────────────────

WAVE_SCHEDULE = {
    "health":       30,    # 30 min
    "maintenance":  60,    # 1 heure
    "intelligence": 120,   # 2 heures
    "deep":         180,   # 3 heures
    "pipeline":     360,   # 6 heures
    "report":       1440,  # 24 heures
}

def wave_health(db, online):
    """Vague rapide: health check + repair basique."""
    tasks = []

    # Task 1: GPU status
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=index,name,temperature.gpu,memory.used,memory.total,utilization.gpu",
                            "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
        gpu_info = r.stdout.strip()
        tasks.append(("gpu_check", "local", "ok", 0, gpu_info, None))
    except Exception as e:
        tasks.append(("gpu_check", "local", "error", 0, None, str(e)[:100]))

    # Task 2: Disk space
    import shutil
    c = shutil.disk_usage("/\")
    f = shutil.disk_usage("F:/")
    disk = f"C: {c.free // 1e9:.0f}GB free | F: {f.free // 1e9:.0f}GB free"
    tasks.append(("disk_check", "local", "ok", 0, disk, None))

    # Task 3: Process check
    try:
        r = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=10)
        node_count = r.stdout.count("node.exe")
        python_count = r.stdout.count("python")
        tasks.append(("process_check", "local", "ok", 0,
                      f"node.exe: {node_count} | python: {python_count}", None))
    except Exception as e:
        tasks.append(("process_check", "local", "error", 0, None, str(e)[:100]))

    # Task 4: Proxy check
    try:
        import urllib.request
        d = json.loads(urllib.request.urlopen("http://127.0.0.1:18800/health", timeout=3).read())
        proxy_ok = d.get("ok", False) if isinstance(d, dict) else bool(d)
        tasks.append(("proxy_check", "local", "ok" if proxy_ok else "warn", 0,
                      f"Proxy 18800: {'OK' if proxy_ok else 'DEGRADED'}", None))
    except Exception:
        tasks.append(("proxy_check", "local", "error", 0, None, "Proxy 18800 OFFLINE"))
        # Auto-repair: try restart proxy
        try:
            subprocess.Popen(["node", str(TURBO / "canvas" / "direct-proxy.js")],
                            cwd=str(TURBO), creationflags=0x00000008)  # DETACHED_PROCESS
            tasks.append(("proxy_restart", "local", "ok", 0, "Proxy relance", None))
        except Exception as e:
            tasks.append(("proxy_restart", "local", "error", 0, None, str(e)[:100]))

    return tasks

def wave_maintenance(db, online):
    """Vague maintenance: scan errors, repair, optimize."""
    tasks = []
    scripts = [
        ("cluster_heartbeat", "cluster_heartbeat.py", ["--once"]),
        ("dispatch_quality", "dispatch_quality_tracker.py", ["--once"]),
        ("health_summary", "cowork_health_summary.py", ["--once"]),
        ("metrics_collect", "metrics_aggregator.py", ["--once"]),
    ]
    for name, script, args in scripts:
        script_path = SCRIPT_DIR / script
        if not script_path.exists():
            tasks.append((name, "local", "skip", 0, None, f"{script} not found"))
            continue
        try:
            t0 = time.time()
            r = subprocess.run(
                [sys.executable, str(script_path)] + args,
                capture_output=True, text=True, timeout=120, cwd=str(SCRIPT_DIR),
                env={**os.environ, "PYTHONPATH": str(TURBO), "PYTHONUTF8": "1"}
            )
            elapsed = time.time() - t0
            status = "ok" if r.returncode == 0 else "error"
            tasks.append((name, "local", status, elapsed,
                         (r.stdout or "")[:500], (r.stderr or "")[:200] if r.returncode != 0 else None))
        except subprocess.TimeoutExpired:
            tasks.append((name, "local", "timeout", 120, None, "timeout 120s"))
        except Exception as e:
            tasks.append((name, "local", "error", 0, None, str(e)[:100]))

    return tasks

def wave_intelligence(db, online):
    """Vague intelligence: code generation, learning, benchmark."""
    tasks = []

    # Sub-batch 1: Dispatch learning
    scripts = [
        ("dispatch_learning", "dispatch_learner.py", ["--learn"]),
        ("routing_update", "smart_routing_engine.py", ["--once"]),
        ("failure_predict", "failure_predictor.py", ["--once"]),
    ]
    for name, script, args in scripts:
        script_path = SCRIPT_DIR / script
        if not script_path.exists():
            tasks.append((name, "local", "skip", 0, None, f"{script} not found"))
            continue
        try:
            t0 = time.time()
            r = subprocess.run(
                [sys.executable, str(script_path)] + args,
                capture_output=True, text=True, timeout=180, cwd=str(SCRIPT_DIR),
                env={**os.environ, "PYTHONPATH": str(TURBO), "PYTHONUTF8": "1"}
            )
            elapsed = time.time() - t0
            status = "ok" if r.returncode == 0 else "error"
            tasks.append((name, "local", status, elapsed,
                         (r.stdout or "")[:500], (r.stderr or "")[:200] if r.returncode != 0 else None))
        except subprocess.TimeoutExpired:
            tasks.append((name, "local", "timeout", 180, None, "timeout 180s"))
        except Exception as e:
            tasks.append((name, "local", "error", 0, None, str(e)[:100]))

    # Sub-batch 2: Cluster tasks (code gen, analysis)
    if online:
        prompts = [
            ("code_quality", "Analyse le code Python dans ce projet et propose 3 ameliorations concretes de performance. Sois specifique avec des exemples de code."),
            ("error_patterns", "Quels sont les patterns d'erreur les plus courants dans un bot Telegram Node.js? Liste 5 avec solutions."),
            ("cluster_optimize", "Comment optimiser un cluster de 4 noeuds IA (M1 46GB, M2 24GB, M3 8GB, OL1 local) pour minimiser la latence? 5 strategies concretes."),
        ]
        node = online[0]  # Best node
        for task_name, prompt in prompts:
            text, elapsed, err = query_node(node, prompt)
            tasks.append((task_name, node, "ok" if text else "error", elapsed,
                         (text or "")[:500], err))

    return tasks

def wave_deep(db, online):
    """Vague deep: audit, refactor, self-improvement."""
    tasks = []

    scripts = [
        ("error_analysis", "dispatch_error_analyzer.py", ["--once"]),
        ("auto_heal", "cluster_auto_healer.py", ["--once"]),
        ("quality_benchmark", "dispatch_quality_tracker.py", ["--benchmark"]),
    ]
    for name, script, args in scripts:
        script_path = SCRIPT_DIR / script
        if not script_path.exists():
            tasks.append((name, "local", "skip", 0, None, f"{script} not found"))
            continue
        try:
            t0 = time.time()
            r = subprocess.run(
                [sys.executable, str(script_path)] + args,
                capture_output=True, text=True, timeout=300, cwd=str(SCRIPT_DIR),
                env={**os.environ, "PYTHONPATH": str(TURBO), "PYTHONUTF8": "1"}
            )
            elapsed = time.time() - t0
            status = "ok" if r.returncode == 0 else "error"
            tasks.append((name, "local", status, elapsed,
                         (r.stdout or "")[:500], (r.stderr or "")[:200] if r.returncode != 0 else None))
        except subprocess.TimeoutExpired:
            tasks.append((name, "local", "timeout", 300, None, "timeout 300s"))
        except Exception as e:
            tasks.append((name, "local", "error", 0, None, str(e)[:100]))

    # Deep cluster tasks
    if online and len(online) >= 2:
        node = online[0]
        text, elapsed, err = query_node(node,
            "Fais un audit complet de securite d'un cluster IA local: "
            "4 machines LAN, API sans auth, tokens en clair dans .env, SQLite non chiffre. "
            "Top 10 corrections urgentes avec niveau de risque et effort.", timeout_override=120)
        tasks.append(("security_audit", node, "ok" if text else "error", elapsed,
                     (text or "")[:500], err))

    return tasks

def wave_pipeline(db, online):
    """Vague pipeline: lance le cluster pipeline complet (185 taches)."""
    tasks = []
    pipeline_script = SCRIPT_DIR / "autonomous_cluster_pipeline.py"
    if not pipeline_script.exists():
        tasks.append(("pipeline", "local", "skip", 0, None, "pipeline script not found"))
        return tasks
    try:
        t0 = time.time()
        r = subprocess.run(
            [sys.executable, str(pipeline_script), "--cycles", "5", "--batch", "4", "--pause", "2"],
            capture_output=True, text=True, timeout=600, cwd=str(SCRIPT_DIR),
            env={**os.environ, "PYTHONPATH": str(TURBO), "PYTHONUTF8": "1"}
        )
        elapsed = time.time() - t0
        status = "ok" if r.returncode == 0 else "error"
        tasks.append(("pipeline_5cycles", "cluster", status, elapsed,
                     (r.stdout or "")[-500:], (r.stderr or "")[:200] if r.returncode != 0 else None))
    except subprocess.TimeoutExpired:
        tasks.append(("pipeline_5cycles", "cluster", "timeout", 600, None, "timeout 600s"))
    except Exception as e:
        tasks.append(("pipeline_5cycles", "cluster", "error", 0, None, str(e)[:100]))
    return tasks

def wave_report(db, online):
    """Vague report: rapport quotidien + cleanup."""
    tasks = []

    # Daily report
    report_script = SCRIPT_DIR / "daily_cowork_report.py"
    if report_script.exists():
        try:
            t0 = time.time()
            r = subprocess.run(
                [sys.executable, str(report_script), "--once"],
                capture_output=True, text=True, timeout=120, cwd=str(SCRIPT_DIR),
                env={**os.environ, "PYTHONPATH": str(TURBO), "PYTHONUTF8": "1"}
            )
            elapsed = time.time() - t0
            tasks.append(("daily_report", "local", "ok" if r.returncode == 0 else "error",
                         elapsed, (r.stdout or "")[:500], None))
        except Exception as e:
            tasks.append(("daily_report", "local", "error", 0, None, str(e)[:100]))

    # Log compression
    compress_script = SCRIPT_DIR / "log_compressor.py"
    if compress_script.exists():
        try:
            t0 = time.time()
            r = subprocess.run(
                [sys.executable, str(compress_script), "--once"],
                capture_output=True, text=True, timeout=60, cwd=str(SCRIPT_DIR),
                env={**os.environ, "PYTHONPATH": str(TURBO), "PYTHONUTF8": "1"}
            )
            elapsed = time.time() - t0
            tasks.append(("log_compress", "local", "ok" if r.returncode == 0 else "error",
                         elapsed, (r.stdout or "")[:300], None))
        except Exception as e:
            tasks.append(("log_compress", "local", "error", 0, None, str(e)[:100]))

    # Self-test
    test_script = SCRIPT_DIR / "cowork_self_test_runner.py"
    if test_script.exists():
        try:
            t0 = time.time()
            r = subprocess.run(
                [sys.executable, str(test_script), "--once"],
                capture_output=True, text=True, timeout=300, cwd=str(SCRIPT_DIR),
                env={**os.environ, "PYTHONPATH": str(TURBO), "PYTHONUTF8": "1"}
            )
            elapsed = time.time() - t0
            tasks.append(("self_test", "local", "ok" if r.returncode == 0 else "error",
                         elapsed, (r.stdout or "")[-300:], None))
        except Exception as e:
            tasks.append(("self_test", "local", "error", 0, None, str(e)[:100]))

    # Generate summary
    wave_count = db.execute("SELECT COUNT(*) FROM master_waves").fetchone()[0]
    task_count = db.execute("SELECT COUNT(*) FROM master_tasks").fetchone()[0]
    ok_count = db.execute("SELECT COUNT(*) FROM master_tasks WHERE status='ok'").fetchone()[0]
    err_count = db.execute("SELECT COUNT(*) FROM master_tasks WHERE status='error'").fetchone()[0]
    tasks.append(("summary", "local", "ok", 0,
                 f"Waves: {wave_count} | Tasks: {task_count} ({ok_count} ok, {err_count} err)", None))

    return tasks

WAVE_HANDLERS = {
    "health": wave_health,
    "maintenance": wave_maintenance,
    "intelligence": wave_intelligence,
    "deep": wave_deep,
    "pipeline": wave_pipeline,
    "report": wave_report,
}

# ── Wave Execution ───────────────────────────────────────────

def execute_wave(db, wave_type, online, dry_run=False):
    """Execute a wave and record results."""
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    t0 = time.time()

    logmsg(f"[WAVE] {wave_type.upper()} starting ({len(online)} nodes online)")

    if dry_run:
        logmsg(f"  [DRY-RUN] Would execute {wave_type} wave")
        return

    handler = WAVE_HANDLERS.get(wave_type)
    if not handler:
        logmsg(f"  [ERROR] Unknown wave type: {wave_type}")
        return

    tasks = handler(db, online)
    duration = time.time() - t0

    # Save wave record
    ok = sum(1 for t in tasks if t[2] == "ok")
    failed = sum(1 for t in tasks if t[2] in ("error", "timeout"))
    errors = "; ".join(t[5] for t in tasks if t[5])[:500]
    nodes_used = list(set(t[1] for t in tasks))

    cur = db.execute(
        "INSERT INTO master_waves (wave_type, timestamp, tasks_total, tasks_ok, tasks_failed, duration_s, nodes_used, errors) VALUES (?,?,?,?,?,?,?,?)",
        (wave_type, ts, len(tasks), ok, failed, round(duration, 2), json.dumps(nodes_used), errors or None))
    wave_id = cur.lastrowid

    # Save task records
    for name, node, status, dur, result, error in tasks:
        db.execute(
            "INSERT INTO master_tasks (wave_id, task_name, node, status, duration_s, result, error, timestamp) VALUES (?,?,?,?,?,?,?,?)",
            (wave_id, name, node, status, round(dur, 2), (result or "")[:2000], error, ts))

    # Update schedule
    next_run = (datetime.now() + timedelta(minutes=WAVE_SCHEDULE[wave_type])).strftime("%Y-%m-%dT%H:%M:%S")
    db.execute(
        "UPDATE master_schedule SET last_run=?, next_run=?, run_count=run_count+1 WHERE wave_type=?",
        (ts, next_run, wave_type))
    db.commit()

    # Log summary
    logmsg(f"  [{wave_type}] {ok}/{len(tasks)} OK | {failed} failed | {duration:.0f}s | nodes: {','.join(nodes_used)}")

    # Telegram notification for important waves
    if wave_type in ("maintenance", "intelligence", "deep", "report"):
        telegram_send(
            f"*JARVIS Master — {wave_type.upper()}*\n"
            f"Tasks: {ok}/{len(tasks)} OK | {failed} failed\n"
            f"Duree: {duration:.0f}s | Nodes: {','.join(nodes_used)}\n"
            f"{'Errors: ' + errors[:200] if errors else 'Aucune erreur'}"
        )

    # Telegram alert if too many failures
    if failed > len(tasks) // 2:
        telegram_send(
            f"*ALERTE MASTER* — {wave_type} a echoue ({failed}/{len(tasks)} tasks failed)\n"
            f"Errors: {errors[:300]}"
        )

    return {"wave_type": wave_type, "ok": ok, "failed": failed, "duration": duration}

# ── Logging ──────────────────────────────────────────────────

def logmsg(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(str(LOG_FILE), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ── Status ───────────────────────────────────────────────────

def show_status():
    if not DB_PATH.exists():
        print("Master autonome: jamais lance")
        return
    db = sqlite3.connect(str(DB_PATH))
    waves = db.execute("SELECT COUNT(*) FROM master_waves").fetchone()[0]
    tasks = db.execute("SELECT COUNT(*) FROM master_tasks").fetchone()[0]
    ok = db.execute("SELECT COUNT(*) FROM master_tasks WHERE status='ok'").fetchone()[0]

    print(f"\n{'='*50}")
    print(f"  JARVIS MASTER AUTONOME — STATUS")
    print(f"{'='*50}")
    print(f"  Waves executees: {waves}")
    print(f"  Tasks totales: {tasks} ({ok} ok, {tasks - ok} failed)")

    # Schedule
    print(f"\n  PLANNING:")
    for row in db.execute("SELECT wave_type, interval_min, last_run, next_run, run_count FROM master_schedule ORDER BY interval_min").fetchall():
        status = "READY" if not row[2] else f"last {row[2]}"
        print(f"    {row[0]:15s} | every {row[1]:4d}min | runs: {row[4]:3d} | {status}")

    # Last 5 waves
    print(f"\n  DERNIERES VAGUES:")
    for row in db.execute("SELECT wave_type, timestamp, tasks_ok, tasks_total-tasks_ok, duration_s FROM master_waves ORDER BY id DESC LIMIT 5").fetchall():
        print(f"    {row[1]} | {row[0]:15s} | {row[2]} ok, {row[3]} failed | {row[4]:.0f}s")

    # PID
    if PID_FILE.exists():
        print(f"\n  PID: {PID_FILE.read_text().strip()}")

    db.close()

# ── Main Loop ────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    # Kill previous instance
    if PID_FILE.exists():
        old_pid = PID_FILE.read_text().strip()
        try:
            subprocess.run(["taskkill", "/PID", old_pid, "/F"],
                          capture_output=True, timeout=5)
        except Exception:
            pass

    PID_FILE.write_text(str(os.getpid()))

    logmsg("=" * 50)
    logmsg("  JARVIS MASTER AUTONOME")
    logmsg(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logmsg(f"  Mode: {'once' if args.once else 'continuous'} | Dry: {args.dry_run}")
    logmsg("=" * 50)

    # Phase 1: Health check
    online = health_check_all()
    logmsg(f"[CLUSTER] {len(online)}/{len(NODES)} online: {', '.join(online)}")

    if not online:
        logmsg("[FATAL] No nodes online!")
        telegram_send("*ALERTE MASTER* — Aucun noeud en ligne! Cluster DOWN.")
        sys.exit(1)

    # Phase 2: Init DB
    db = init_db()

    # Phase 3: Single pass or continuous loop
    if args.once:
        for wave_type in ["health", "maintenance", "intelligence"]:
            execute_wave(db, wave_type, online, args.dry_run)
        db.close()
        PID_FILE.unlink(missing_ok=True)
        return

    # Continuous mode
    telegram_send(
        f"*JARVIS Master Autonome DEMARRE*\n"
        f"Nodes: {', '.join(online)}\n"
        f"Vagues: health(30m) maintenance(1h) intelligence(2h) deep(3h) pipeline(6h) report(24h)"
    )

    check_interval = 60  # Check schedule every 60 seconds
    health_counter = 0

    while True:
        try:
            # Re-check health every 10 iterations (10 min)
            health_counter += 1
            if health_counter % 10 == 0:
                online = health_check_all()
                logmsg(f"[HEALTH] {len(online)}/{len(NODES)} online: {', '.join(online)}")

            # Check which waves are due
            now = datetime.now()
            rows = db.execute(
                "SELECT wave_type, next_run FROM master_schedule WHERE enabled=1"
            ).fetchall()

            for wave_type, next_run_str in rows:
                if not next_run_str:
                    continue
                try:
                    next_run = datetime.strptime(next_run_str, "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    continue
                if now >= next_run:
                    execute_wave(db, wave_type, online, args.dry_run)

            time.sleep(check_interval)

        except KeyboardInterrupt:
            logmsg("[STOP] Interrupted")
            break
        except Exception as e:
            logmsg(f"[ERROR] {e}")
            traceback.print_exc()
            time.sleep(30)

    telegram_send("*JARVIS Master Autonome ARRETE*")
    db.close()
    PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logmsg(f"[CRASH] {e}")
        traceback.print_exc()
        telegram_send(f"*CRASH MASTER*: {str(e)[:200]}")
        raise
