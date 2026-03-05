#!/usr/bin/env python3
"""telegram_cowork_dashboard.py — COWORK Dashboard via Telegram Bot.

Sends rich status reports, health checks, and improvement cycle results
directly to Telegram. Can run as a one-shot or periodic reporter.

Commands understood via Telegram:
  /cowork_status   - Full COWORK status
  /cowork_health   - Cluster health check
  /cowork_cycle    - Run improvement cycle
  /cowork_quality  - Quality report
  /cowork_errors   - Error analysis
  /cowork_trends   - Trend analysis
  /cowork_test     - Self-test results
  /cowork_dispatch - Dispatch stats

CLI:
    --once        : send full status to Telegram
    --health      : send health check
    --cycle       : run and report improvement cycle
    --poll        : start polling for commands (long-running)
    --stats       : show what was sent

Stdlib-only (sqlite3, json, argparse, urllib).
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
ETOILE_DB = Path(r"F:/BUREAU/turbo/etoile.db")
PYTHON = sys.executable

# Telegram config
TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT_ID = "2010747443"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS telegram_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        report_type TEXT NOT NULL,
        message_id INTEGER,
        content_preview TEXT
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def send_telegram(text, parse_mode="Markdown"):
    """Send a message to Telegram."""
    # Split long messages
    max_len = 4000
    parts = [text[i:i+max_len] for i in range(0, len(text), max_len)]

    message_ids = []
    for part in parts:
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": part,
            "parse_mode": parse_mode,
        }).encode()

        try:
            req = urllib.request.Request(f"{TELEGRAM_API}/sendMessage", data)
            resp = urllib.request.urlopen(req, timeout=10)
            result = json.loads(resp.read())
            if result.get("ok"):
                message_ids.append(result["result"]["message_id"])
        except Exception as e:
            # Retry without parse_mode if markdown fails
            try:
                data2 = urllib.parse.urlencode({
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": part,
                }).encode()
                req2 = urllib.request.Request(f"{TELEGRAM_API}/sendMessage", data2)
                resp2 = urllib.request.urlopen(req2, timeout=10)
                result2 = json.loads(resp2.read())
                if result2.get("ok"):
                    message_ids.append(result2["result"]["message_id"])
            except Exception:
                pass

    return message_ids


def run_script(name, args):
    """Run a COWORK script and return parsed JSON."""
    script_path = SCRIPT_DIR / f"{name}.py"
    if not script_path.exists():
        return {"error": f"{name}.py not found"}

    cmd = [PYTHON, str(script_path)] + (args if isinstance(args, list) else [args])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(SCRIPT_DIR))
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
        return {"error": r.stderr[:200] if r.stderr else "empty output"}
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except json.JSONDecodeError:
        return {"error": "invalid JSON"}
    except Exception as e:
        return {"error": str(e)[:200]}


def format_status():
    """Format full COWORK status report."""
    # Get stats from etoile.db
    if not ETOILE_DB.exists():
        return "etoile.db not found"

    edb = sqlite3.connect(str(ETOILE_DB))
    patterns = edb.execute("SELECT COUNT(DISTINCT pattern_id) FROM cowork_script_mapping WHERE status='active'").fetchone()[0]
    scripts = edb.execute("SELECT COUNT(*) FROM cowork_script_mapping WHERE status='active'").fetchone()[0]
    dispatches = edb.execute("SELECT COUNT(*) FROM agent_dispatch_log").fetchone()[0]
    success_rate = edb.execute("SELECT AVG(CASE WHEN success=1 THEN 100.0 ELSE 0.0 END) FROM agent_dispatch_log").fetchone()[0]
    avg_quality = edb.execute("SELECT AVG(quality_score) FROM agent_dispatch_log WHERE success=1").fetchone()[0]
    edb.close()

    script_files = len(list(SCRIPT_DIR.glob("*.py")))

    msg = f"""*COWORK Dashboard*
{'='*30}

*Infrastructure*
  Scripts: {script_files} fichiers
  Mappes: {scripts} (30 patterns)
  Dispatches: {dispatches}

*Performance*
  Success rate: {success_rate:.1f}%
  Qualite moy: {(avg_quality or 0)*100:.1f}%

*Patterns*: {patterns} COWORK patterns actifs

_Genere le {datetime.now().strftime('%Y-%m-%d %H:%M')}_"""
    return msg


def format_health():
    """Format cluster health report."""
    data = run_script("cluster_health_watchdog", "--once")
    if "error" in data:
        return f"Erreur health check: {data['error']}"

    nodes_text = ""
    for n in data.get("nodes", []):
        icon = "OK" if n["status"] == "healthy" else "WARN" if n["status"] == "slow" else "OFFLINE"
        nodes_text += f"  [{icon}] {n['node']}: {n['response_ms']}ms ({n['models_loaded']} modeles)\n"

    alerts = data.get("alerts", [])
    alerts_text = f"\nAlertes ({len(alerts)}):\n" + "\n".join(f"  - {a['message']}" for a in alerts) if alerts else ""

    return f"""*Cluster Health*
Statut: {data.get('cluster_status', '?').upper()}
Noeuds: {data.get('nodes_online', '?')}

{nodes_text}{alerts_text}

_Check le {datetime.now().strftime('%H:%M:%S')}_"""


def format_cycle():
    """Format improvement cycle results."""
    data = run_script("cowork_full_cycle", "--quick")
    if "error" in data:
        return f"Erreur cycle: {data['error']}"

    results_text = ""
    for r in data.get("results", []):
        status = "OK" if r["status"] == "ok" else "ERR"
        summary = r.get("summary", {})
        detail = " | ".join(f"{k}={v}" for k, v in summary.items()) if summary else ""
        results_text += f"  [{status}] {r['label']}: {detail}\n"

    return f"""*Cycle d'amelioration*
Resultat: {data.get('ok', 0)}/{data.get('total_scripts', 0)} OK
Duree: {data.get('duration_ms', 0)}ms

{results_text}
_Cycle le {datetime.now().strftime('%H:%M:%S')}_"""


def format_quality():
    """Format quality report."""
    data = run_script("dispatch_quality_scorer", "--once")
    if "error" in data:
        return f"Erreur qualite: {data['error']}"

    worst = data.get("worst_combos", [])
    worst_text = "\n".join(f"  - {w['pattern']}/{w['node']}: {w['avg_quality']}" for w in worst[:5])

    return f"""*Qualite Dispatch*
Globale: {data.get('overall_quality', 0)}
Excellent: {data.get('excellent_pct', 0)}%
Critique: {data.get('critical_count', 0)}
En declin: {data.get('declining_count', 0)}

Pires combos:
{worst_text}"""


def format_errors():
    """Format error analysis."""
    data = run_script("dispatch_error_analyzer", "--once")
    if "error" in data:
        return f"Erreur analyse: {data['error']}"

    causes = data.get("inferred_causes", {})
    causes_text = "\n".join(f"  - {k}: {v}" for k, v in causes.items())
    nodes = data.get("node_failure_counts", {})
    nodes_text = "\n".join(f"  - {k}: {v} echecs" for k, v in nodes.items())

    return f"""*Analyse Erreurs*
Total echecs: {data.get('total_failures', 0)}
Null errors: {data.get('null_pct', 0)}%

Causes inferees:
{causes_text}

Par noeud:
{nodes_text}"""


def format_trends():
    """Format trend analysis."""
    data = run_script("dispatch_trend_analyzer", "--once")
    if "error" in data:
        return f"Erreur trends: {data['error']}"

    s = data.get("summary", {})
    emerging = data.get("trends", {}).get("emerging", [])
    em_text = "\n".join(f"  - {t['pattern']}: +{t.get('volume_change_pct', '?')}%" for t in emerging[:5])

    return f"""*Tendances Dispatch*
Emergents: {s.get('emerging', 0)}
En declin: {s.get('declining', 0)}
En amelioration: {s.get('improving', 0)}
En degradation: {s.get('degrading', 0)}

Patterns emergents:
{em_text}"""


def format_test():
    """Format self-test results."""
    data = run_script("cowork_self_test_runner", ["--level", "1"])
    if "error" in data:
        return f"Erreur tests: {data['error']}"

    return f"""*Self-Tests COWORK*
Level 1 (syntax): {data.get('passed', 0)}/{data.get('total_tests', 0)}
Success: {data.get('success_rate_pct', 0)}%
Echecs: {data.get('failure_count', 0)}
Duree: {data.get('duration_ms', 0)}ms"""


def format_dispatch_stats():
    """Format dispatch statistics."""
    if not ETOILE_DB.exists():
        return "etoile.db not found"

    edb = sqlite3.connect(str(ETOILE_DB))
    edb.row_factory = sqlite3.Row

    rows = edb.execute("""
        SELECT classified_type, COUNT(*) as total,
               AVG(CASE WHEN success=1 THEN 100.0 ELSE 0.0 END) as success_pct,
               AVG(latency_ms) as avg_lat
        FROM agent_dispatch_log
        GROUP BY classified_type
        ORDER BY total DESC
        LIMIT 12
    """).fetchall()
    edb.close()

    stats_text = ""
    for r in rows:
        stats_text += f"  {r['classified_type']:15s} n={r['total']:4d} ok={r['success_pct']:.0f}% lat={int(r['avg_lat'] or 0)}ms\n"

    return f"""*Dispatch Stats*
{'='*30}
{stats_text}"""


COMMAND_MAP = {
    "/cowork_status": ("status", format_status),
    "/cowork_health": ("health", format_health),
    "/cowork_cycle": ("cycle", format_cycle),
    "/cowork_quality": ("quality", format_quality),
    "/cowork_errors": ("errors", format_errors),
    "/cowork_trends": ("trends", format_trends),
    "/cowork_test": ("test", format_test),
    "/cowork_dispatch": ("dispatch", format_dispatch_stats),
}


def action_once():
    """Send full status report."""
    msg = format_status()
    ids = send_telegram(msg)
    conn = get_db()
    conn.execute("INSERT INTO telegram_reports (timestamp, report_type, message_id, content_preview) VALUES (?, ?, ?, ?)",
                 (datetime.now().isoformat(), "status", ids[0] if ids else 0, msg[:100]))
    conn.commit()
    conn.close()
    return {"sent": True, "message_ids": ids, "preview": msg[:200]}


def action_health():
    """Send health report."""
    msg = format_health()
    ids = send_telegram(msg)
    return {"sent": True, "message_ids": ids, "preview": msg[:200]}


def action_cycle():
    """Run cycle and send report."""
    msg = format_cycle()
    ids = send_telegram(msg)
    return {"sent": True, "message_ids": ids, "preview": msg[:200]}


def action_poll():
    """Poll Telegram for commands."""
    offset = 0
    print("Polling Telegram for COWORK commands...")
    while True:
        try:
            url = f"{TELEGRAM_API}/getUpdates?offset={offset}&timeout=30"
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=35)
            data = json.loads(resp.read())

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")

                if str(chat_id) != TELEGRAM_CHAT_ID:
                    continue

                for cmd, (name, formatter) in COMMAND_MAP.items():
                    if text.startswith(cmd):
                        print(f"Command: {cmd}")
                        response = formatter()
                        send_telegram(response)
                        break

        except Exception as e:
            print(f"Poll error: {e}")
            time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description="COWORK Telegram Dashboard")
    parser.add_argument("--once", action="store_true", help="Send status report")
    parser.add_argument("--health", action="store_true", help="Send health check")
    parser.add_argument("--cycle", action="store_true", help="Run and report cycle")
    parser.add_argument("--poll", action="store_true", help="Start polling")
    parser.add_argument("--stats", action="store_true", help="Show sent reports")
    args = parser.parse_args()

    if not any([args.once, args.health, args.cycle, args.poll, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.poll:
        action_poll()
    elif args.health:
        result = action_health()
    elif args.cycle:
        result = action_cycle()
    elif args.stats:
        conn = get_db()
        rows = conn.execute("SELECT * FROM telegram_reports ORDER BY timestamp DESC LIMIT 10").fetchall()
        conn.close()
        result = {"reports": [dict(r) for r in rows]}
    else:
        result = action_once()

    if not args.poll:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
