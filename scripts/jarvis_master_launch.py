#!/usr/bin/env python3
"""JARVIS Master Launch - Unified startup, verification, and cluster distribution.

Usage:
    python scripts/jarvis_master_launch.py [--verify] [--bench] [--fix] [--full]

    --verify  Run verification checks (files, SQL, GitHub, logs, Telegram)
    --bench   Run speed/quality benchmark on available nodes
    --fix     Auto-fix detected issues
    --full    All of the above
"""
import asyncio, httpx, subprocess, json, time, sys, os, sqlite3, re
from pathlib import Path
from datetime import datetime

# === CONFIGURATION ===
TURBO_ROOT = Path("F:/BUREAU/turbo")
OPENCLAW_ROOT = Path("C:/Users/franc/.openclaw")
DATA_DIR = TURBO_ROOT / "data"

NODES = {
    "M1": {"url": "http://127.0.0.1:1234", "type": "lmstudio", "model": "qwen3-8b", "weight": 1.8},
    "M2": {"url": "http://192.168.1.26:1234", "type": "lmstudio", "model": "deepseek-r1-0528-qwen3-8b", "weight": 1.5},
    "M3": {"url": "http://192.168.1.113:1234", "type": "lmstudio", "model": "deepseek-r1-0528-qwen3-8b", "weight": 1.2},
    "OL1": {"url": "http://127.0.0.1:11434", "type": "ollama", "weight": 1.3},
    "GEMINI": {"url": "http://127.0.0.1:18791", "type": "gemini", "weight": 1.2},
    "CLAUDE": {"url": "http://127.0.0.1:18793", "type": "claude-bridge", "weight": 1.2},
}

SERVICES = {
    "OpenClaw Gateway": {"port": 18789, "health": "http://127.0.0.1:18789"},
    "Gemini Proxy": {"port": 18791, "health": "http://127.0.0.1:18791"},
    "Claude Bridge": {"port": 18793, "health": "http://127.0.0.1:18793/v1/models"},
    "n8n": {"port": 5678, "health": "http://127.0.0.1:5678"},
    "Python WS": {"port": 9742, "health": "http://127.0.0.1:9742/api/health"},
    "Dashboard": {"port": 8080, "health": "http://127.0.0.1:8080"},
    "Chat Proxy": {"port": 18790, "health": "http://127.0.0.1:18790/health"},
}

DBS = {
    "etoile": DATA_DIR / "etoile.db",
    "jarvis": DATA_DIR / "jarvis.db",
    "sniper": DATA_DIR / "sniper.db",
    "finetuning": DATA_DIR / "finetuning.db",
}


def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# === 1. CLUSTER HEALTH CHECK ===
async def check_cluster():
    section("CLUSTER HEALTH CHECK")
    results = {}
    async with httpx.AsyncClient() as client:
        for name, cfg in NODES.items():
            try:
                if cfg["type"] == "lmstudio":
                    r = await client.get(f"{cfg['url']}/api/v1/models", timeout=3)
                    d = r.json()
                    loaded = [m for m in d.get("data", d.get("models", [])) if m.get("loaded_instances")]
                    results[name] = {"status": "UP", "models": len(loaded), "loaded": [l.get("id", "?") for l in loaded]}
                elif cfg["type"] == "ollama":
                    r = await client.get(f"{cfg['url']}/api/tags", timeout=3)
                    d = r.json()
                    models = d.get("models", [])
                    results[name] = {"status": "UP", "models": len(models)}
                elif cfg["type"] in ("gemini", "claude-bridge"):
                    r = await client.get(f"{cfg['url']}/v1/models", timeout=3)
                    results[name] = {"status": "UP" if r.status_code < 500 else "ERROR"}
            except Exception as e:
                results[name] = {"status": "DOWN", "error": str(e)[:60]}

        for name, r in results.items():
            icon = "OK" if r["status"] == "UP" else "!!"
            extra = f"models={r.get('models', '?')}" if r["status"] == "UP" else r.get("error", "")[:40]
            print(f"  [{icon}] {name:<10s} {r['status']:<6s} {extra}")

    return results


# === 2. SERVICES CHECK ===
async def check_services():
    section("SERVICES CHECK")
    results = {}
    async with httpx.AsyncClient() as client:
        for name, cfg in SERVICES.items():
            try:
                r = await client.get(cfg["health"], timeout=3)
                results[name] = {"status": "UP", "code": r.status_code}
                print(f"  [OK] {name:<20s} port {cfg['port']} — HTTP {r.status_code}")
            except Exception:
                results[name] = {"status": "DOWN"}
                print(f"  [!!] {name:<20s} port {cfg['port']} — OFFLINE")
    return results


# === 3. GPU STATUS ===
def check_gpu():
    section("GPU STATUS")
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,temperature.gpu,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        gpus = []
        for line in r.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                gpu = {"idx": parts[0], "name": parts[1], "temp": int(parts[2]), "mem_used": int(parts[3]),
                       "mem_total": int(parts[4]), "util": int(parts[5])}
                gpus.append(gpu)
                icon = "!!" if gpu["temp"] >= 80 else "OK"
                print(f"  [{icon}] GPU{gpu['idx']} {gpu['name'][:30]:30s} {gpu['temp']}C  {gpu['mem_used']}/{gpu['mem_total']}MB  util={gpu['util']}%")
        return gpus
    except Exception as e:
        print(f"  [!!] nvidia-smi failed: {e}")
        return []


# === 4. DATABASE VERIFICATION ===
def verify_databases():
    section("DATABASE VERIFICATION")
    results = {}
    for name, path in DBS.items():
        if not path.exists():
            print(f"  [!!] {name}: FILE NOT FOUND ({path})")
            results[name] = {"status": "MISSING"}
            continue
        try:
            conn = sqlite3.connect(str(path))
            c = conn.cursor()
            # Integrity check
            integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
            # Table count
            tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            # Row counts
            total_rows = 0
            table_info = {}
            for (t,) in tables:
                try:
                    count = c.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
                    total_rows += count
                    table_info[t] = count
                except:
                    pass
            conn.close()
            icon = "OK" if integrity == "ok" else "!!"
            print(f"  [{icon}] {name:12s} {len(tables):>3d} tables  {total_rows:>6d} rows  integrity={integrity}")
            results[name] = {"status": "OK", "tables": len(tables), "rows": total_rows, "integrity": integrity}
        except Exception as e:
            print(f"  [!!] {name}: {e}")
            results[name] = {"status": "ERROR", "error": str(e)[:60]}
    return results


# === 5. GIT STATUS ===
def check_git():
    section("GIT STATUS")
    try:
        os.chdir(str(TURBO_ROOT))
        # Current branch
        branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, timeout=5).stdout.strip()
        # Status
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, timeout=5).stdout.strip()
        changed = len(status.split("\n")) if status else 0
        # Last 3 commits
        log = subprocess.run(["git", "log", "--oneline", "-3"], capture_output=True, text=True, timeout=5).stdout.strip()
        # Remote
        remote = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True, timeout=5).stdout.strip().split("\n")[0] if True else ""

        print(f"  Branch: {branch}")
        print(f"  Changed files: {changed}")
        print(f"  Remote: {remote}")
        print(f"  Recent commits:")
        for line in log.split("\n")[:3]:
            print(f"    {line}")
        return {"branch": branch, "changed": changed, "log": log}
    except Exception as e:
        print(f"  [!!] Git error: {e}")
        return {"error": str(e)}


# === 6. OPENCLAW LOGS ANALYSIS ===
def analyze_openclaw_logs():
    section("OPENCLAW LOGS ANALYSIS")
    log_dir = Path("C:/Users/franc/AppData/Local/Temp/openclaw")
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"openclaw-{today}.log"

    if not log_file.exists():
        print(f"  [!!] Log file not found: {log_file}")
        return {}

    size_mb = log_file.stat().st_size / (1024 * 1024)
    print(f"  Log file: {log_file} ({size_mb:.1f} MB)")

    # Read last 500 lines for analysis
    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    total_lines = len(lines)
    print(f"  Total lines: {total_lines}")

    # Parse errors from last 500 lines
    recent = lines[-500:] if len(lines) > 500 else lines
    errors = {"context_exceeded": 0, "gateway_timeout": 0, "rate_limit": 0, "enoent": 0, "other_errors": 0}

    for line in recent:
        if "Context size has been exceeded" in line:
            errors["context_exceeded"] += 1
        elif "gateway timeout" in line.lower():
            errors["gateway_timeout"] += 1
        elif "rate limit" in line.lower():
            errors["rate_limit"] += 1
        elif "ENOENT" in line:
            errors["enoent"] += 1
        elif "error" in line.lower() and "FailoverError" not in line:
            errors["other_errors"] += 1

    print(f"  Errors (last 500 lines):")
    for k, v in errors.items():
        icon = "!!" if v > 0 else "OK"
        print(f"    [{icon}] {k}: {v}")

    return {"total_lines": total_lines, "size_mb": round(size_mb, 1), "errors": errors}


# === 7. OPENCLAW SESSIONS CHECK ===
def check_sessions():
    section("OPENCLAW SESSIONS")
    sessions_dir = OPENCLAW_ROOT / "agents" / "main" / "sessions"
    if not sessions_dir.exists():
        print(f"  [!!] Sessions dir not found")
        return {}

    sessions = list(sessions_dir.glob("*.jsonl"))
    total_size = sum(s.stat().st_size for s in sessions)
    print(f"  Active sessions: {len(sessions)}")
    print(f"  Total size: {total_size / (1024*1024):.1f} MB")

    # Latest session
    if sessions:
        latest = max(sessions, key=lambda s: s.stat().st_mtime)
        print(f"  Latest: {latest.name} ({latest.stat().st_size/1024:.0f} KB)")

    return {"count": len(sessions), "total_mb": round(total_size / (1024 * 1024), 1)}


# === 8. CRON STATUS ===
def check_crons():
    section("OPENCLAW CRONS")
    cron_dir = OPENCLAW_ROOT / "cron"
    if not cron_dir.exists():
        print(f"  [!!] Cron dir not found")
        return {}

    cron_files = list(cron_dir.iterdir())
    print(f"  Cron entries: {len(cron_files)}")

    # Check schedule.json
    schedule = OPENCLAW_ROOT / "workspace" / "dev" / "schedule.json"
    if schedule.exists():
        with open(schedule) as f:
            sched = json.load(f)
        tasks = sched if isinstance(sched, list) else sched.get("tasks", [])
        print(f"  Scheduled tasks: {len(tasks)}")
        for t in tasks:
            if isinstance(t, dict):
                status = "ON" if t.get("enabled", True) else "OFF"
                name = t.get("name", t.get("id", "?"))
                interval = t.get("interval_minutes", t.get("interval", 0))
                print(f"    [{status}] {name:<20s} every {interval} min")
    return {"entries": len(cron_files)}


# === 9. TELEGRAM MESSAGES ===
def check_telegram():
    section("TELEGRAM MESSAGES")
    try:
        # Check latest delivery queue
        dq_dir = OPENCLAW_ROOT / "delivery-queue"
        if dq_dir.exists():
            items = list(dq_dir.iterdir())
            print(f"  Delivery queue items: {len(items)}")

        # Check telegram dir
        tg_dir = OPENCLAW_ROOT / "telegram"
        if tg_dir.exists():
            tg_files = list(tg_dir.iterdir())
            print(f"  Telegram data files: {len(tg_files)}")
            for f in tg_files[:5]:
                print(f"    {f.name} ({f.stat().st_size/1024:.0f} KB)")

    except Exception as e:
        print(f"  [!!] Telegram check error: {e}")


# === 10. FILE CONFORMITY ===
def check_file_conformity():
    section("FILE CONFORMITY CHECK")
    checks = {
        "openclaw.json": OPENCLAW_ROOT / "openclaw.json",
        "gateway.cmd": OPENCLAW_ROOT / "gateway.cmd",
        "watchdog.bat": OPENCLAW_ROOT / "watchdog.bat",
        "schedule.json": OPENCLAW_ROOT / "workspace" / "dev" / "schedule.json",
        "telegram-bot.js": TURBO_ROOT / "canvas" / "telegram-bot.js",
        "agents.py": TURBO_ROOT / "src" / "agents.py",
        "tools.py": TURBO_ROOT / "src" / "tools.py",
        "mcp_server.py": TURBO_ROOT / "src" / "mcp_server.py",
        "etoile.db": DATA_DIR / "etoile.db",
        "jarvis.db": DATA_DIR / "jarvis.db",
    }
    issues = []
    for name, path in checks.items():
        if path.exists():
            size = path.stat().st_size
            icon = "OK" if size > 0 else "!!"
            if size == 0:
                issues.append(f"{name} is empty")
            print(f"  [{icon}] {name:25s} {size:>10,d} bytes")
        else:
            print(f"  [!!] {name:25s} MISSING")
            issues.append(f"{name} missing")

    if issues:
        print(f"\n  ISSUES: {len(issues)}")
        for i in issues:
            print(f"    - {i}")
    return {"issues": issues}


# === QUICK BENCHMARK ===
async def quick_benchmark():
    section("QUICK BENCHMARK (available nodes)")
    prompt = "Write a Python function that reverses a string. Return only the function."
    results = []

    async with httpx.AsyncClient() as client:
        # M1
        try:
            t0 = time.perf_counter()
            r = await client.post("http://127.0.0.1:1234/api/v1/chat",
                json={"model": "qwen3-8b", "input": "/nothink\n" + prompt, "temperature": 0.2,
                      "max_output_tokens": 512, "stream": False, "store": False},
                headers={"Content-Type": "application/json"}, timeout=15)
            d = r.json()
            msgs = [o for o in d.get("output", []) if o.get("type") == "message"]
            content = msgs[-1].get("content", "") if msgs else ""
            if isinstance(content, list):
                content = content[0].get("text", "") if content else ""
            elapsed = time.perf_counter() - t0
            toks = len(str(content).split())
            results.append(("M1/qwen3-8b", elapsed, toks, bool("def" in str(content).lower())))
            print(f"  M1/qwen3-8b:  {elapsed:.1f}s  {toks} tokens  Q={'OK' if 'def' in str(content).lower() else 'FAIL'}")
        except Exception as e:
            print(f"  M1: FAIL ({e})")

        # OL1/1.7b
        try:
            t0 = time.perf_counter()
            r = await client.post("http://127.0.0.1:11434/api/chat",
                json={"model": "qwen3:1.7b", "messages": [{"role": "user", "content": prompt}],
                      "stream": False}, timeout=20)
            d = r.json()
            content = d.get("message", {}).get("content", "")
            elapsed = time.perf_counter() - t0
            toks = d.get("eval_count", len(content.split()))
            tps = toks / elapsed if elapsed > 0 else 0
            results.append(("OL1/qwen3-1.7b", elapsed, toks, bool("def" in content.lower())))
            print(f"  OL1/qwen3-1.7b: {elapsed:.1f}s  {toks} tokens  {tps:.0f} tok/s  Q={'OK' if 'def' in content.lower() else 'FAIL'}")
        except Exception as e:
            print(f"  OL1: FAIL ({e})")

        # M2
        try:
            t0 = time.perf_counter()
            r = await client.post("http://192.168.1.26:1234/api/v1/chat",
                json={"model": "deepseek-r1-0528-qwen3-8b", "input": prompt, "temperature": 0.3,
                      "max_output_tokens": 2048, "stream": False, "store": False},
                headers={"Content-Type": "application/json"}, timeout=60)
            d = r.json()
            msgs = [o for o in d.get("output", []) if o.get("type") == "message"]
            content = msgs[-1].get("content", "") if msgs else ""
            if isinstance(content, list):
                content = content[0].get("text", "") if content else ""
            elapsed = time.perf_counter() - t0
            toks = len(str(content).split())
            results.append(("M2/deepseek-r1", elapsed, toks, bool("def" in str(content).lower())))
            print(f"  M2/deepseek-r1: {elapsed:.1f}s  {toks} tokens  Q={'OK' if 'def' in str(content).lower() else 'FAIL'}")
        except Exception as e:
            print(f"  M2: FAIL ({e})")

    return results


# === MAIN ===
async def main():
    args = set(sys.argv[1:])
    do_all = "--full" in args
    do_verify = do_all or "--verify" in args
    do_bench = do_all or "--bench" in args

    print(f"\n{'#'*70}")
    print(f"  JARVIS MASTER LAUNCH — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*70}")

    # Always: cluster + GPU
    cluster = await check_cluster()
    gpus = check_gpu()
    services = await check_services()

    if do_verify:
        db_results = verify_databases()
        git = check_git()
        logs = analyze_openclaw_logs()
        sessions = check_sessions()
        crons = check_crons()
        telegram = check_telegram()
        conformity = check_file_conformity()

    if do_bench:
        bench = await quick_benchmark()

    # Summary
    section("SUMMARY")
    up_nodes = sum(1 for v in cluster.values() if v.get("status") == "UP")
    up_services = sum(1 for v in services.values() if v.get("status") == "UP")
    hot_gpus = sum(1 for g in gpus if g.get("temp", 0) >= 75)

    print(f"  Cluster:  {up_nodes}/{len(NODES)} nodes UP")
    print(f"  Services: {up_services}/{len(SERVICES)} services UP")
    print(f"  GPUs:     {len(gpus)} total, {hot_gpus} hot (>75C)")
    if do_verify:
        print(f"  DBs:      {sum(1 for v in db_results.values() if v.get('status') == 'OK')}/{len(DBS)} OK")

    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "cluster": cluster,
        "services": {k: v for k, v in services.items()},
        "gpus": gpus,
    }
    report_path = DATA_DIR / "launch_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n  Report saved: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
