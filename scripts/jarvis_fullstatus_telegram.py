#!/usr/bin/env python3
"""JARVIS Full Status — Complete dashboard for Telegram.
Combines: boot diagnostic + GPU details + cluster + DBs + automation + disk.

Usage: python /home/turbo/jarvis-m1-ops/scripts/jarvis_fullstatus_telegram.py
"""
import json, subprocess, time, sqlite3, os, sys
from pathlib import Path

TIMEOUT = 5
DATA = Path("/home/turbo/jarvis-m1-ops/data")
WS_URL = "http://127.0.0.1:9742"

def run(cmd, timeout=TIMEOUT):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                           encoding='utf-8', errors='replace')
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None

def ws_get(path, timeout=5):
    try:
        import urllib.request
        with urllib.request.urlopen(f"{WS_URL}{path}", timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


# ── SECTION 1: CLUSTER ─────────────────────────────────────────────
def sect_cluster():
    lines = ["CLUSTER"]
    nodes = [
        ("M1", "http://127.0.0.1:1234/api/v1/models"),
        ("OL1", "http://127.0.0.1:11434/api/tags"),
        ("M2", "http://192.168.1.26:1234/api/v1/models"),
        ("M3", "http://192.168.1.113:1234/api/v1/models"),
    ]
    for name, url in nodes:
        r = run(f'curl -s --max-time 3 {url}')
        if not r:
            lines.append(f"  {name}: OFFLINE")
            continue
        try:
            d = json.loads(r)
            if "/api/tags" in url:
                lines.append(f"  {name}: OK ({len(d.get('models',[]))} models)")
            else:
                models = d.get("data", d.get("models", []))
                loaded = [m for m in models if m.get("state") == "loaded" or m.get("loaded_instances")]
                lines.append(f"  {name}: OK ({len(loaded) if loaded else len(models)} loaded, {len(models)} available)")
        except:
            lines.append(f"  {name}: OK (parse error)")
    return "\n".join(lines)


# ── SECTION 2: GPU ──────────────────────────────────────────────────
def sect_gpu():
    r = run("nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader")
    if not r: return "GPU\n  nvidia-smi unavailable"
    lines = ["GPU"]
    total_used, total_total = 0, 0
    for line in r.strip().split("\n"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 5:
            name = parts[0].replace("NVIDIA GeForce ", "")
            temp = parts[1].replace(" ", "")
            used = parts[2].replace(" MiB", "").replace(" ", "")
            total = parts[3].replace(" MiB", "").replace(" ", "")
            util = parts[4].replace(" ", "")
            total_used += int(used)
            total_total += int(total)
            warn = " !" if int(temp.replace("C","").replace("°","")) >= 75 else ""
            lines.append(f"  {name}: {temp}C | {used}/{total}MB | {util}{warn}")
    lines.append(f"  TOTAL VRAM: {total_used}/{total_total}MB ({total_used*100//max(total_total,1)}%)")
    return "\n".join(lines)


# ── SECTION 3: SERVICES ────────────────────────────────────────────
def sect_services():
    r = run('netstat -ano | findstr "LISTENING"')
    ports = {1234: "M1 LMStudio", 8080: "Dashboard", 9742: "WS FastAPI", 11434: "Ollama", 18800: "Proxy"}
    lines = ["SERVICES"]
    for p, name in sorted(ports.items()):
        up = r and (f":{p} " in r or f":{p}\t" in r) if r else False
        lines.append(f"  :{p} {name} — {'UP' if up else 'DOWN'}")
    # Telegram bot check
    tg = run('tasklist /FI "IMAGENAME eq node.exe" /FO CSV')
    tg_up = tg and "telegram-bot" in (run('wmic process where "name=\'node.exe\'" get commandline') or "")
    lines.append(f"  Telegram Bot — {'UP' if tg_up else 'DOWN'}")
    return "\n".join(lines)


# ── SECTION 4: DATABASES ───────────────────────────────────────────
def sect_databases():
    lines = ["DATABASES"]
    dbs = [("etoile", DATA / "etoile.db"), ("jarvis", DATA / "jarvis.db"), ("sniper", DATA / "sniper.db")]
    total_rows, total_tables = 0, 0
    for name, path in dbs:
        if not path.exists():
            lines.append(f"  {name}: MISSING")
            continue
        try:
            conn = sqlite3.connect(str(path))
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
            rows = 0
            for t in tables:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM [{t}]")
                    rows += cur.fetchone()[0]
                except: pass
            conn.close()
            kb = os.path.getsize(str(path)) // 1024
            total_rows += rows
            total_tables += len(tables)
            lines.append(f"  {name}: {len(tables)}t, {rows}r, {kb}KB")
        except Exception as e:
            lines.append(f"  {name}: ERROR {e}")
    lines.append(f"  TOTAL: {total_tables} tables, {total_rows} rows")
    return "\n".join(lines)


# ── SECTION 5: AUTOMATION ──────────────────────────────────────────
def sect_automation():
    lines = ["AUTOMATION"]
    # Autonomous loop
    auto = ws_get("/api/autonomous/status")
    if auto and isinstance(auto, dict):
        running = auto.get("running", False)
        tasks = auto.get("tasks", {})
        active = sum(1 for t in tasks.values() if t.get("enabled"))
        total_runs = sum(t.get("run_count", 0) for t in tasks.values())
        health = next((t.get("last_result", {}).get("health_score") for t in tasks.values() if "health_score" in t.get("last_result", {})), None)
        lines.append(f"  Autonomous: {'RUNNING' if running else 'STOPPED'} | {active} tasks | {total_runs} runs" + (f" | health={health}" if health else ""))
    else:
        lines.append("  Autonomous: unavailable")
    # Self-improve
    si = ws_get("/api/self-improve/status")
    if si and isinstance(si, dict):
        cycles = si.get("cycles", si.get("total_cycles", "?"))
        actions = si.get("total_actions", "?")
        last = si.get("last_report", {})
        last_acts = last.get("actions_taken", 0)
        lines.append(f"  Self-Improve: {cycles} cycles, {actions} actions (last: {last_acts} acts)")
    # Scheduler
    sched = ws_get("/api/scheduler/jobs")
    if sched and isinstance(sched, dict):
        jobs = sched.get("jobs", sched.get("data", []))
        if isinstance(jobs, list):
            active = sum(1 for j in jobs if j.get("enabled"))
            lines.append(f"  Scheduler: {active}/{len(jobs)} jobs active")
    elif sched and isinstance(sched, list):
        active = sum(1 for j in sched if j.get("enabled"))
        lines.append(f"  Scheduler: {active}/{len(sched)} jobs active")
    # Queue
    queue = ws_get("/api/queue/status")
    if queue and isinstance(queue, dict):
        pending = queue.get("pending", queue.get("count", 0))
        lines.append(f"  Queue: {pending} pending")
    # SQL stats
    sql = ws_get("/api/sql/stats")
    if sql and isinstance(sql, dict):
        total = sql.get("_total", {})
        lines.append(f"  SQL: {total.get('databases','?')} DBs, {total.get('tables','?')} tables, {total.get('rows','?')} rows")
    return "\n".join(lines)


# ── SECTION 6: DISK ────────────────────────────────────────────────
def sect_disk():
    lines = ["DISKS"]
    r = run('powershell -Command "Get-PSDrive -PSProvider FileSystem | ForEach-Object { $t=[math]::Round(($_.Used+$_.Free)/1GB); if($t -gt 0){ Write-Host ($_.Name + /\":/\" + [math]::Round($_.Free/1GB) + /\"//\" + $t) } }"')
    if not r:
        return "DISKS\n  unavailable"
    for line in r.strip().split("\n"):
        parts = line.strip().split(":")
        if len(parts) == 2:
            name = parts[0].strip()
            vals = parts[1].strip().split("/")
            if len(vals) == 2:
                try:
                    free_gb = int(vals[0])
                    total_gb = int(vals[1])
                    pct = free_gb * 100 // max(total_gb, 1)
                    warn = " !" if pct < 10 else ""
                    lines.append(f"  {name}: {free_gb}/{total_gb}GB free ({pct}%){warn}")
                except ValueError:
                    pass
    return "\n".join(lines)


# ── GRADE ───────────────────────────────────────────────────────────
def compute_grade(cluster_text, gpu_text, services_text):
    score = 100
    issues = []
    if "M1: OFFLINE" in cluster_text:
        score -= 25; issues.append("CRITICAL: M1 OFFLINE")
    if "OL1: OFFLINE" in cluster_text:
        score -= 15; issues.append("CRITICAL: OL1 OFFLINE")
    if "M2: OFFLINE" in cluster_text:
        score -= 5; issues.append("WARNING: M2 OFFLINE")
    if "M3: OFFLINE" in cluster_text:
        score -= 5; issues.append("WARNING: M3 OFFLINE")
    for line in gpu_text.split("\n"):
        if "!" in line and "C" in line:
            score -= 5; issues.append(f"THERMAL: {line.strip()}")
    if "WS FastAPI — DOWN" in services_text:
        score -= 10; issues.append("DOWN: WS FastAPI")
    if "Proxy — DOWN" in services_text:
        score -= 10; issues.append("DOWN: Proxy")
    if "Telegram Bot — DOWN" in services_text:
        score -= 5; issues.append("DOWN: Telegram Bot")
    if score >= 95: grade = "A+"
    elif score >= 85: grade = "A"
    elif score >= 70: grade = "B"
    elif score >= 50: grade = "C"
    else: grade = "D"
    return grade, score, issues


if __name__ == "__main__":
    t0 = time.time()
    c = sect_cluster()
    g = sect_gpu()
    s = sect_services()
    d = sect_databases()
    a = sect_automation()
    dk = sect_disk()
    grade, score, issues = compute_grade(c, g, s)
    elapsed = round(time.time() - t0, 1)

    header = f"JARVIS FULL STATUS — Grade {grade} ({score}/100) — {elapsed}s"
    sep = "=" * len(header)
    print(sep)
    print(header)
    print(sep)
    print()
    for section in [c, g, s, d, a, dk]:
        print(section)
        print()
    if issues:
        print("ISSUES")
        for i in issues:
            print(f"  - {i}")
    print(sep)
