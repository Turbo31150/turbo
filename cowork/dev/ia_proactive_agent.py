#!/usr/bin/env python3
"""IA Proactive Agent — Autonomous task discovery and execution.

Monitors system state, identifies opportunities, and executes
improvements without human intervention. Dispatches to the full
cluster (M1+M2+M3+OL1) for complex tasks.
"""
import argparse
import json
import os
import sqlite3
import time
import urllib.request
from pathlib import Path

DB_PATH = Path(__file__).parent / "proactive.db"
TURBO = Path("F:/BUREAU/turbo")

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY, ts REAL, category TEXT, description TEXT,
        priority INTEGER DEFAULT 5, status TEXT DEFAULT 'pending',
        assigned_to TEXT, result TEXT, completed_at REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS discoveries (
        id INTEGER PRIMARY KEY, ts REAL, source TEXT, finding TEXT,
        severity TEXT, acted_on INTEGER DEFAULT 0)""")
    db.commit()
    return db

def check_disk_space():
    """Check disk space on C: and F:"""
    findings = []
    for drive in ["C:", "F:"]:
        try:
            import shutil
            usage = shutil.disk_usage(drive + "/")
            free_gb = usage.free / (1024**3)
            pct = (usage.used / usage.total) * 100
            if free_gb < 20:
                findings.append(("disk", f"{drive} espace faible: {free_gb:.0f} GB libre ({pct:.0f}% utilise)", "high"))
            elif free_gb < 50:
                findings.append(("disk", f"{drive} attention: {free_gb:.0f} GB libre", "medium"))
        except OSError:
            pass
    return findings

def check_cluster_health():
    """Quick cluster health check."""
    findings = []
    nodes = {
        "M1": "http://127.0.0.1:1234/api/v1/models",
        "OL1": "http://127.0.0.1:11434/api/tags",
    }
    for name, url in nodes.items():
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
                if name == "M1":
                    loaded = len([m for m in data.get("data", data.get("models", [])) if m.get("loaded_instances")])
                    if loaded == 0:
                        findings.append(("cluster", f"{name}: aucun modele charge", "high"))
                elif name == "OL1":
                    models = len(data.get("models", []))
                    if models == 0:
                        findings.append(("cluster", f"{name}: aucun modele disponible", "high"))
        except Exception:
            findings.append(("cluster", f"{name}: OFFLINE", "critical"))
    return findings

def check_stale_logs():
    """Check for large log files that should be rotated."""
    findings = []
    log_dirs = [TURBO / "data", TURBO / "logs", Path(__file__).parent]
    for d in log_dirs:
        if not d.exists():
            continue
        for f in d.glob("*.log"):
            size_mb = f.stat().st_size / (1024 * 1024)
            if size_mb > 50:
                findings.append(("logs", f"Log volumineux: {f.name} ({size_mb:.0f} MB)", "medium"))
    return findings

def check_db_health():
    """Check JARVIS databases integrity."""
    findings = []
    dbs = [
        TURBO / "data" / "etoile.db",
        TURBO / "data" / "jarvis.db",
        TURBO / "data" / "sniper.db",
    ]
    for dbpath in dbs:
        if not dbpath.exists():
            continue
        try:
            conn = sqlite3.connect(str(dbpath))
            result = conn.execute("PRAGMA integrity_check").fetchone()
            if result[0] != "ok":
                findings.append(("database", f"{dbpath.name}: integrity FAIL", "critical"))
            size_mb = dbpath.stat().st_size / (1024 * 1024)
            if size_mb > 100:
                findings.append(("database", f"{dbpath.name}: {size_mb:.0f} MB — VACUUM recommande", "medium"))
            conn.close()
        except Exception as e:
            findings.append(("database", f"{dbpath.name}: erreur {e}", "high"))
    return findings

def check_canvas_proxy():
    """Check if canvas proxy is running."""
    findings = []
    try:
        req = urllib.request.Request("http://127.0.0.1:18800/health")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            nodes_up = data.get("nodesUp", 0)
            if nodes_up < 2:
                findings.append(("proxy", f"Canvas proxy: seulement {nodes_up} noeuds", "high"))
    except Exception:
        findings.append(("proxy", "Canvas proxy (18800) OFFLINE", "high"))
    return findings

def check_telegram_bot():
    """Check Telegram bot health via service registry."""
    findings = []
    try:
        req = urllib.request.Request("http://127.0.0.1:18800/services")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            services = data.get("services", {})
            if "telegram-bot" not in services:
                findings.append(("telegram", "Telegram bot non enregistre dans le registry", "medium"))
    except Exception:
        pass  # Proxy down already caught above
    return findings

def discover_tasks(db):
    """Run all checks and store findings."""
    all_findings = []
    all_findings.extend(check_disk_space())
    all_findings.extend(check_cluster_health())
    all_findings.extend(check_stale_logs())
    all_findings.extend(check_db_health())
    all_findings.extend(check_canvas_proxy())
    all_findings.extend(check_telegram_bot())

    new_count = 0
    for source, finding, severity in all_findings:
        # Avoid duplicates from last 2 hours
        recent = db.execute(
            "SELECT id FROM discoveries WHERE source=? AND finding=? AND ts > ?",
            (source, finding, time.time() - 7200)).fetchone()
        if not recent:
            db.execute(
                "INSERT INTO discoveries (ts, source, finding, severity) VALUES (?,?,?,?)",
                (time.time(), source, finding, severity))
            new_count += 1

            # Auto-create task for critical/high
            if severity in ("critical", "high"):
                db.execute(
                    "INSERT INTO tasks (ts, category, description, priority, status) VALUES (?,?,?,?,?)",
                    (time.time(), source, finding, 1 if severity == "critical" else 3, "pending"))
    db.commit()
    return all_findings, new_count

def auto_fix(db):
    """Attempt to auto-fix pending tasks."""
    tasks = db.execute(
        "SELECT id, category, description FROM tasks WHERE status='pending' ORDER BY priority LIMIT 5"
    ).fetchall()
    fixed = 0
    for tid, cat, desc in tasks:
        result = None
        if cat == "logs" and "volumineux" in desc:
            # Truncate large logs
            import re
            m = re.search(r"(\S+\.log)", desc)
            if m:
                result = f"Log rotation recommandee pour {m.group(1)}"
        elif cat == "database" and "VACUUM" in desc:
            import re
            m = re.search(r"(\w+\.db)", desc)
            if m:
                dbname = m.group(1)
                dbpath = TURBO / "data" / dbname
                try:
                    conn = sqlite3.connect(str(dbpath))
                    conn.execute("VACUUM")
                    conn.close()
                    result = f"VACUUM execute sur {dbname}"
                    fixed += 1
                except Exception as e:
                    result = f"VACUUM echoue: {e}"

        if result:
            db.execute("UPDATE tasks SET status='done', result=?, completed_at=? WHERE id=?",
                       (result, time.time(), tid))
    db.commit()
    return fixed

def send_telegram_alert(message):
    """Send alert to Telegram."""
    token = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT", "2010747443")
    if not token:
        # Try from etoile.db
        try:
            edb = sqlite3.connect(str(TURBO / "data" / "etoile.db"))
            row = edb.execute("SELECT value FROM memories WHERE key='telegram_bot_token'").fetchone()
            if row:
                token = row[0]
            edb.close()
        except Exception:
            pass
    if not token:
        return
    try:
        body = json.dumps({"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser(description="IA Proactive Agent")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--fix", action="store_true", help="Auto-fix pending tasks")
    parser.add_argument("--interval", type=int, default=1800, help="Seconds between scans")
    args = parser.parse_args()

    db = init_db()
    if args.once or not args.loop:
        findings, new = discover_tasks(db)
        print(f"Scan: {len(findings)} findings, {new} new")
        for source, finding, severity in findings:
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(severity, "⚪")
            print(f"  {icon} [{source}] {finding}")
        if args.fix:
            fixed = auto_fix(db)
            print(f"Auto-fix: {fixed} tasks resolved")
        # Alert on critical
        criticals = [f for f in findings if f[2] == "critical"]
        if criticals:
            msg = "🔴 *JARVIS Proactive Alert*\n" + "\n".join(f"• {f[1]}" for f in criticals)
            send_telegram_alert(msg)

    if args.loop:
        print("Proactive Agent en boucle continue...")
        while True:
            try:
                findings, new = discover_tasks(db)
                fixed = auto_fix(db)
                ts = time.strftime('%H:%M')
                print(f"[{ts}] {len(findings)} checks | +{new} new | {fixed} fixed")
                criticals = [f for f in findings if f[2] == "critical"]
                if criticals:
                    msg = f"🔴 *Proactive [{ts}]*\n" + "\n".join(f"• {f[1]}" for f in criticals)
                    send_telegram_alert(msg)
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
