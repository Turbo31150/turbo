#!/usr/bin/env python3
"""proactive_agent.py — Agent proactif qui anticipe les besoins sans demande.

Triggers automatiques bases sur l'heure, l'etat systeme, et les patterns.

Usage:
    python dev/proactive_agent.py --start
    python dev/proactive_agent.py --stop
    python dev/proactive_agent.py --rules
    python dev/proactive_agent.py --history
    python dev/proactive_agent.py --check
    python dev/proactive_agent.py --add "name" --trigger "condition" --action "command"
"""
import argparse
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "proactive.db"
DEV = Path(__file__).parent

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, trigger_type TEXT, trigger_value TEXT,
        action TEXT, cooldown_s INTEGER, enabled INTEGER DEFAULT 1,
        last_fired REAL DEFAULT 0, fire_count INTEGER DEFAULT 0)""")
    db.execute("""CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, rule_name TEXT, trigger_matched TEXT,
        action TEXT, success INTEGER, output TEXT)""")
    db.commit()

    # Regles par defaut
    defaults = [
        ("rapport_matinal", "time", "08:00", "python dev/pipeline_orchestrator.py --run morning_check", 82800),
        ("gpu_chaud", "gpu_temp", "80", "python dev/gpu_optimizer.py --thermal 2>/dev/null || nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader", 600),
        ("disk_plein", "disk_free_gb", "10", "python dev/desktop_organizer.py --scan", 3600),
        ("gateway_down", "port_down", "18789", "python dev/openclaw_watchdog.py --restart", 300),
        ("rapport_soir", "time", "22:00", "python dev/pipeline_orchestrator.py --run full_diagnostic", 82800),
        ("trading_matin", "time", "09:30", "python dev/domino_executor.py --run trading_pipeline", 82800),
        ("dev_review", "time", "14:00", "python dev/self_feeding_engine.py --review", 82800),
        ("cleanup_hebdo", "weekday_time", "0-02:00", "python dev/desktop_organizer.py --organize", 604800),
    ]
    for name, ttype, tval, action, cooldown in defaults:
        db.execute(
            "INSERT OR IGNORE INTO rules (name, trigger_type, trigger_value, action, cooldown_s) VALUES (?,?,?,?,?)",
            (name, ttype, tval, action, cooldown)
        )
    db.commit()
    return db

# ---------------------------------------------------------------------------
# Trigger evaluation
# ---------------------------------------------------------------------------
def check_trigger(trigger_type: str, trigger_value: str) -> dict:
    """Evalue si un trigger est actif."""
    now = datetime.now()

    if trigger_type == "time":
        target_h, target_m = map(int, trigger_value.split(":"))
        # Match dans les 2 minutes
        if now.hour == target_h and abs(now.minute - target_m) <= 2:
            return {"matched": True, "reason": f"Heure {trigger_value}"}
        return {"matched": False}

    elif trigger_type == "weekday_time":
        parts = trigger_value.split("-")
        target_day = int(parts[0])
        target_h, target_m = map(int, parts[1].split(":"))
        if now.weekday() == target_day and now.hour == target_h and abs(now.minute - target_m) <= 2:
            return {"matched": True, "reason": f"Jour {target_day} heure {parts[1]}"}
        return {"matched": False}

    elif trigger_type == "gpu_temp":
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5
            )
            temps = [int(t.strip()) for t in result.stdout.strip().split("\n") if t.strip().isdigit()]
            max_temp = max(temps) if temps else 0
            threshold = int(trigger_value)
            if max_temp > threshold:
                return {"matched": True, "reason": f"GPU {max_temp}C > {threshold}C"}
        except Exception:
            pass
        return {"matched": False}

    elif trigger_type == "disk_free_gb":
        try:
            usage = shutil.disk_usage("C:/")
            free_gb = usage.free // (1024**3)
            threshold = int(trigger_value)
            if free_gb < threshold:
                return {"matched": True, "reason": f"C: {free_gb}GB libre < {threshold}GB"}
        except Exception:
            pass
        return {"matched": False}

    elif trigger_type == "port_down":
        port = int(trigger_value)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            if result != 0:
                return {"matched": True, "reason": f"Port {port} inaccessible"}
        except Exception:
            return {"matched": True, "reason": f"Port {port} erreur connexion"}
        return {"matched": False}

    return {"matched": False}

# ---------------------------------------------------------------------------
# Execute action
# ---------------------------------------------------------------------------
def execute_action(db, rule_name: str, action: str, reason: str) -> dict:
    start = time.time()
    try:
        result = subprocess.run(
            action, shell=True, capture_output=True, text=True,
            timeout=120, cwd=str(DEV.parent),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}
        )
        success = result.returncode == 0
        output = (result.stdout.strip() or result.stderr.strip())[:500]
    except subprocess.TimeoutExpired:
        success = False
        output = "timeout"
    except Exception as e:
        success = False
        output = str(e)[:200]

    db.execute(
        "INSERT INTO actions (ts, rule_name, trigger_matched, action, success, output) VALUES (?,?,?,?,?,?)",
        (time.time(), rule_name, reason, action, int(success), output)
    )
    db.execute(
        "UPDATE rules SET last_fired = ?, fire_count = fire_count + 1 WHERE name = ?",
        (time.time(), rule_name)
    )
    db.commit()

    return {
        "rule": rule_name,
        "action": action[:100],
        "success": success,
        "reason": reason,
        "duration_s": round(time.time() - start, 1),
        "output_preview": output[:200],
    }

# ---------------------------------------------------------------------------
# Check all rules
# ---------------------------------------------------------------------------
def check_all(db) -> dict:
    rules = db.execute(
        "SELECT name, trigger_type, trigger_value, action, cooldown_s, last_fired, enabled FROM rules"
    ).fetchall()

    fired = []
    skipped = []
    now = time.time()

    for name, ttype, tval, action, cooldown, last_fired, enabled in rules:
        if not enabled:
            skipped.append({"name": name, "reason": "disabled"})
            continue

        if now - last_fired < cooldown:
            remaining = int(cooldown - (now - last_fired))
            skipped.append({"name": name, "reason": f"cooldown ({remaining}s restant)"})
            continue

        trigger = check_trigger(ttype, tval)
        if trigger["matched"]:
            result = execute_action(db, name, action, trigger["reason"])
            fired.append(result)
        else:
            skipped.append({"name": name, "reason": "trigger non actif"})

    return {
        "timestamp": datetime.now().isoformat(),
        "fired": fired,
        "skipped": skipped,
        "total_rules": len(rules),
        "actions_fired": len(fired),
    }

# ---------------------------------------------------------------------------
# Watch loop
# ---------------------------------------------------------------------------
def watch_loop(db, interval: int = 60):
    print(f"[proactive] Agent demarre (interval={interval}s)")
    while True:
        try:
            result = check_all(db)
            if result["actions_fired"] > 0:
                for a in result["fired"]:
                    status = "OK" if a["success"] else "FAIL"
                    print(f"[proactive] {a['rule']} → {status} ({a['reason']})")
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[proactive] Arrete.")
            break
        except Exception as e:
            print(f"[proactive] Erreur: {e}")
            time.sleep(interval)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="JARVIS Proactive Agent — Anticipe les besoins")
    parser.add_argument("--start", action="store_true", help="Demarrer la boucle proactive")
    parser.add_argument("--check", action="store_true", help="Verifier une fois toutes les regles")
    parser.add_argument("--rules", action="store_true", help="Lister les regles")
    parser.add_argument("--history", nargs="?", const=20, type=int, help="Historique actions (N dernieres)")
    parser.add_argument("--add", type=str, help="Ajouter une regle (nom)")
    parser.add_argument("--trigger", type=str, help="Condition trigger (type:value)")
    parser.add_argument("--action", type=str, help="Commande a executer")
    parser.add_argument("--cooldown", type=int, default=3600, help="Cooldown en secondes (defaut: 3600)")
    parser.add_argument("--interval", type=int, default=60, help="Intervalle loop en secondes (defaut: 60)")
    parser.add_argument("--enable", type=str, help="Activer une regle")
    parser.add_argument("--disable", type=str, help="Desactiver une regle")
    args = parser.parse_args()

    db = init_db()

    if args.check:
        result = check_all(db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.rules:
        rules = db.execute(
            "SELECT name, trigger_type, trigger_value, action, cooldown_s, last_fired, fire_count, enabled FROM rules ORDER BY name"
        ).fetchall()
        output = []
        for name, ttype, tval, action, cd, lf, fc, en in rules:
            output.append({
                "name": name,
                "trigger": f"{ttype}:{tval}",
                "action": action[:80],
                "cooldown_s": cd,
                "enabled": bool(en),
                "fire_count": fc,
                "last_fired": datetime.fromtimestamp(lf).strftime("%H:%M") if lf > 0 else "never",
            })
        print(json.dumps(output, indent=2, ensure_ascii=False))
    elif args.history is not None:
        rows = db.execute(
            "SELECT ts, rule_name, trigger_matched, success, output FROM actions ORDER BY ts DESC LIMIT ?",
            (args.history,)
        ).fetchall()
        print(json.dumps([
            {"when": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M"),
             "rule": r, "trigger": t, "success": bool(s), "output": o[:100]}
            for ts, r, t, s, o in rows
        ], indent=2, ensure_ascii=False))
    elif args.add and args.trigger and args.action:
        parts = args.trigger.split(":", 1)
        if len(parts) != 2:
            print(json.dumps({"error": "Format trigger: type:value (ex: time:08:00, gpu_temp:80, port_down:18789)"}))
            sys.exit(1)
        db.execute(
            "INSERT OR REPLACE INTO rules (name, trigger_type, trigger_value, action, cooldown_s) VALUES (?,?,?,?,?)",
            (args.add, parts[0], parts[1], args.action, args.cooldown)
        )
        db.commit()
        print(json.dumps({"added": args.add, "trigger": args.trigger, "action": args.action}))
    elif args.enable:
        db.execute("UPDATE rules SET enabled = 1 WHERE name = ?", (args.enable,))
        db.commit()
        print(json.dumps({"enabled": args.enable}))
    elif args.disable:
        db.execute("UPDATE rules SET enabled = 0 WHERE name = ?", (args.disable,))
        db.commit()
        print(json.dumps({"disabled": args.disable}))
    elif args.start:
        watch_loop(db, args.interval)
    else:
        parser.print_help()

    db.close()

if __name__ == "__main__":
    main()
