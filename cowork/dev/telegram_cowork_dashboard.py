#!/usr/bin/env python3
"""telegram_cowork_dashboard.py — Interactive COWORK Dashboard via Telegram.

Full interactive dashboard with inline keyboard buttons, ASCII charts,
live-updating messages, GPU monitoring, and auto-refresh.

Main entry: /dashboard or /d
Navigation via inline buttons — no need to type commands.

Sections:
  [Status]    - Infrastructure overview with visual bars
  [Cluster]   - Node health with response times + GPU temps
  [Dispatch]  - Pattern stats with success bars + latency
  [Quality]   - Quality scores with trend indicators
  [Errors]    - Error breakdown with cause analysis
  [Trends]    - Emerging/declining patterns
  [Cycle]     - Run full improvement cycle
  [Tests]     - Self-test results all levels
  [Improve]   - Auto-improvement recommendations
  [GPU]       - GPU temperatures + VRAM usage

CLI:
    --poll       : start interactive bot (long-running)
    --once       : send main dashboard
    --health     : send cluster health
    --full       : send all sections at once
    --stats      : show sent reports

Stdlib-only (sqlite3, json, argparse, urllib, subprocess).
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
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
ETOILE_DB = Path(r"F:/BUREAU/turbo/etoile.db")
PYTHON = sys.executable

TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT_ID = "2010747443"
API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ── Helpers ──────────────────────────────────────────────────────────────────

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
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def tg_call(method, params):
    """Call Telegram Bot API."""
    data = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{API}/{method}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())
    except Exception:
        # Fallback: strip markdown and retry
        if "parse_mode" in params:
            params2 = dict(params)
            del params2["parse_mode"]
            data2 = json.dumps(params2).encode()
            req2 = urllib.request.Request(
                f"{API}/{method}",
                data=data2,
                headers={"Content-Type": "application/json"},
            )
            try:
                resp2 = urllib.request.urlopen(req2, timeout=15)
                return json.loads(resp2.read())
            except Exception:
                pass
    return {"ok": False}


def send_msg(text, keyboard=None, chat_id=None):
    """Send message with optional inline keyboard."""
    params = {
        "chat_id": chat_id or TELEGRAM_CHAT_ID,
        "text": text[:4096],
        "parse_mode": "HTML",
    }
    if keyboard:
        params["reply_markup"] = {"inline_keyboard": keyboard}
    result = tg_call("sendMessage", params)
    return result.get("result", {}).get("message_id", 0)


def edit_msg(message_id, text, keyboard=None, chat_id=None):
    """Edit an existing message."""
    params = {
        "chat_id": chat_id or TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": text[:4096],
        "parse_mode": "HTML",
    }
    if keyboard:
        params["reply_markup"] = {"inline_keyboard": keyboard}
    return tg_call("editMessageText", params)


def answer_callback(callback_id, text=""):
    """Answer callback query (removes loading spinner)."""
    tg_call("answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": text[:200],
    })


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
        return {"error": r.stderr[:200] if r.stderr else "empty"}
    except subprocess.TimeoutExpired:
        return {"error": "timeout (120s)"}
    except json.JSONDecodeError:
        return {"error": "invalid JSON output"}
    except Exception as e:
        return {"error": str(e)[:150]}


# ── Visual helpers ───────────────────────────────────────────────────────────

def bar(value, max_val=100, width=12):
    """ASCII progress bar."""
    pct = min(value / max(max_val, 1), 1.0)
    filled = int(pct * width)
    empty = width - filled
    return f"[{'#' * filled}{'.' * empty}] {value:.0f}%"


def bar_latency(ms, target=20000, width=10):
    """Latency bar (lower is better)."""
    pct = min(ms / max(target * 2, 1), 1.0)
    filled = int(pct * width)
    return f"[{'!' * filled}{'_' * (width - filled)}] {ms:.0f}ms"


def spark(values, width=8):
    """Mini sparkline from values."""
    if not values:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn or 1
    chars = " _.-~*#@"
    return "".join(chars[min(int((v - mn) / rng * 7), 7)] for v in values[-width:])


def status_icon(ok):
    """Status indicator."""
    return "OK" if ok else "!!"


def trend_arrow(change_pct):
    """Trend arrow from percentage change."""
    if change_pct > 10:
        return "++ "
    elif change_pct > 0:
        return "+  "
    elif change_pct < -10:
        return "-- "
    elif change_pct < 0:
        return "-  "
    return "=  "


# ── Keyboard layouts ─────────────────────────────────────────────────────────

def main_keyboard():
    return [
        [{"text": "Status", "callback_data": "sec:status"},
         {"text": "Cluster", "callback_data": "sec:cluster"},
         {"text": "GPU", "callback_data": "sec:gpu"}],
        [{"text": "Dispatch", "callback_data": "sec:dispatch"},
         {"text": "Nodes", "callback_data": "sec:nodes"},
         {"text": "History", "callback_data": "sec:history"}],
        [{"text": "Quality", "callback_data": "sec:quality"},
         {"text": "Errors", "callback_data": "sec:errors"},
         {"text": "Trends", "callback_data": "sec:trends"}],
        [{"text": "Tests", "callback_data": "sec:tests"},
         {"text": "Cycle", "callback_data": "sec:cycle"},
         {"text": "Improve", "callback_data": "sec:improve"}],
        [{"text": "Scripts", "callback_data": "sec:search"},
         {"text": "Scheduler", "callback_data": "sec:scheduler"},
         {"text": "Refresh", "callback_data": "sec:status"}],
    ]


def back_keyboard():
    return [[{"text": "<< Menu principal", "callback_data": "sec:main"}]]


# ── Dashboard sections ───────────────────────────────────────────────────────

def section_main():
    """Main dashboard overview."""
    edb = _get_etoile()
    if not edb:
        return "etoile.db introuvable", main_keyboard()

    total = edb.execute("SELECT COUNT(*) FROM agent_dispatch_log").fetchone()[0]
    success = edb.execute("SELECT SUM(success) FROM agent_dispatch_log").fetchone()[0] or 0
    rate = success / max(total, 1) * 100
    avg_q = edb.execute("SELECT AVG(quality_score) FROM agent_dispatch_log WHERE success=1").fetchone()[0] or 0
    avg_lat = edb.execute("SELECT AVG(latency_ms) FROM agent_dispatch_log").fetchone()[0] or 0
    scripts = edb.execute("SELECT COUNT(*) FROM cowork_script_mapping WHERE status='active'").fetchone()[0]
    patterns = edb.execute("SELECT COUNT(DISTINCT pattern_id) FROM cowork_script_mapping WHERE status='active'").fetchone()[0]
    edb.close()

    files = len(list(SCRIPT_DIR.glob("*.py")))
    ts = datetime.now().strftime("%H:%M:%S")

    text = f"""<b>JARVIS COWORK Dashboard</b>
{'=' * 32}

<b>Infrastructure</b>
  Scripts:     {files} fichiers
  Mappes:      {scripts} actifs
  Patterns:    {patterns}
  Dispatches:  {total}

<b>Performance</b>
  Success  {bar(rate)}
  Qualite  {bar(avg_q * 100)}
  Latence  {bar_latency(avg_lat)}

<code>{ts}</code> | Choisir une section :"""

    return text, main_keyboard()


def section_cluster():
    """Cluster health with node details."""
    data = run_script("cluster_health_watchdog", "--once")
    if "error" in data:
        return f"Erreur: {data['error']}", back_keyboard()

    lines = [f"<b>Cluster Health</b>  [{data.get('cluster_status', '?').upper()}]",
             f"Noeuds: {data.get('nodes_online', '?')}", ""]

    for n in data.get("nodes", []):
        ok = n["status"] == "healthy"
        icon = status_icon(ok)
        ms = n["response_ms"]
        models = n["models_loaded"]
        latbar = f"[{'#' * min(ms // 5, 10)}{'.' * max(10 - ms // 5, 0)}]" if ms < 100 else "[!!!!!!!!!!]"
        lines.append(f"  <b>{n['node']:3s}</b> [{icon}] {latbar} {ms:>4d}ms  {models} mod.")

    alerts = data.get("alerts", [])
    if alerts:
        lines.append(f"\nAlertes ({len(alerts)}):")
        for a in alerts[:5]:
            lines.append(f"  !! {a['message']}")

    lines.append(f"\n<code>{datetime.now().strftime('%H:%M:%S')}</code>")
    return "\n".join(lines), back_keyboard()


def section_gpu():
    """GPU temperatures and VRAM."""
    lines = ["<b>GPU Monitor</b>", ""]

    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,temperature.gpu,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            for line in r.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 6:
                    idx, name, temp, mem_used, mem_total, util = parts[:6]
                    temp_i = int(temp)
                    mem_pct = int(mem_used) / max(int(mem_total), 1) * 100
                    util_i = int(util)

                    # Temperature bar with threshold colors
                    if temp_i >= 85:
                        temp_warn = " CRIT!"
                    elif temp_i >= 75:
                        temp_warn = " chaud"
                    else:
                        temp_warn = ""

                    # Short GPU name
                    short = name.replace("NVIDIA GeForce ", "").replace("NVIDIA ", "")

                    lines.append(f"  <b>GPU{idx}</b> {short}")
                    lines.append(f"    Temp  {bar(temp_i, 100, 10)}{temp_warn}")
                    lines.append(f"    VRAM  {bar(mem_pct, 100, 10)} {mem_used}/{mem_total}MB")
                    lines.append(f"    Load  {bar(util_i, 100, 10)}")
                    lines.append("")
        else:
            lines.append("  nvidia-smi erreur")
    except FileNotFoundError:
        lines.append("  nvidia-smi non trouve")
    except Exception as e:
        lines.append(f"  Erreur: {str(e)[:80]}")

    lines.append(f"<code>{datetime.now().strftime('%H:%M:%S')}</code>")
    return "\n".join(lines), back_keyboard()


def section_dispatch():
    """Dispatch statistics with visual bars."""
    edb = _get_etoile()
    if not edb:
        return "etoile.db introuvable", back_keyboard()

    rows = edb.execute("""
        SELECT classified_type,
               COUNT(*) as total,
               AVG(CASE WHEN success=1 THEN 100.0 ELSE 0.0 END) as rate,
               AVG(latency_ms) as avg_lat,
               AVG(quality_score) as avg_q
        FROM agent_dispatch_log
        GROUP BY classified_type
        ORDER BY total DESC
        LIMIT 15
    """).fetchall()
    edb.close()

    lines = ["<b>Dispatch par Pattern</b>", "",
             "<code>Pattern       N    OK%   Lat(ms)  Q</code>",
             "<code>" + "-" * 42 + "</code>"]

    for r in rows:
        pat = (r["classified_type"] or "?")[:12]
        total = r["total"]
        rate = r["rate"] or 0
        lat = r["avg_lat"] or 0
        q = r["avg_q"] or 0

        rate_bar = "#" * int(rate / 10) + "." * (10 - int(rate / 10))
        lines.append(f"<code>{pat:12s} {total:4d} [{rate_bar}] {lat:5.0f} {q:.1f}</code>")

    lines.append(f"\n<code>{datetime.now().strftime('%H:%M:%S')}</code>")
    return "\n".join(lines), back_keyboard()


def section_quality():
    """Quality analysis with scores."""
    data = run_script("dispatch_quality_scorer", "--once")
    if "error" in data:
        return f"Erreur: {data['error']}", back_keyboard()

    lines = [
        "<b>Qualite Dispatch</b>", "",
        f"  Globale:   {bar((data.get('overall_quality', 0)) * 100)}",
        f"  Excellent: {data.get('excellent_pct', 0)}%",
        f"  Critique:  {data.get('critical_count', 0)}",
        f"  En declin: {data.get('declining_count', 0)}", "",
    ]

    best = data.get("best_combos", [])
    if best:
        lines.append("<b>Meilleurs combos</b>")
        for b in best[:5]:
            lines.append(f"  {b['pattern']:12s} / {b['node']:3s} q={b['avg_quality']:.3f}")

    worst = data.get("worst_combos", [])
    if worst:
        lines.append("\n<b>Pires combos</b>")
        for w in worst[:5]:
            lines.append(f"  {w['pattern']:12s} / {w['node']:3s} q={w['avg_quality']:.3f} [{w['trend']}]")

    # Quality by response length
    by_len = data.get("quality_by_length", [])
    if by_len:
        lines.append("\n<b>Qualite par longueur reponse</b>")
        for bl in by_len:
            q = bl.get("avg_q", 0) or 0
            lines.append(f"  {bl.get('length_bucket', '?'):18s} q={q:.3f} (n={bl.get('cnt', 0)})")

    return "\n".join(lines), back_keyboard()


def section_errors():
    """Error analysis."""
    data = run_script("dispatch_error_analyzer", "--once")
    if "error" in data:
        return f"Erreur: {data['error']}", back_keyboard()

    lines = [
        "<b>Analyse Erreurs</b>", "",
        f"  Total echecs: {data.get('total_failures', 0)}",
        f"  Null errors:  {data.get('null_pct', 0):.1f}%", "",
    ]

    causes = data.get("inferred_causes", {})
    if causes:
        lines.append("<b>Causes inferees</b>")
        total_c = sum(causes.values())
        for cause, count in sorted(causes.items(), key=lambda x: -x[1]):
            pct = count / max(total_c, 1) * 100
            b = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
            lines.append(f"  [{b}] {cause}: {count}")

    nodes = data.get("node_failure_counts", {})
    if nodes:
        lines.append("\n<b>Echecs par noeud</b>")
        total_n = sum(nodes.values())
        for node, count in sorted(nodes.items(), key=lambda x: -x[1]):
            pct = count / max(total_n, 1) * 100
            b = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
            lines.append(f"  [{b}] {node}: {count}")

    recs = data.get("recommendations", [])
    if recs:
        lines.append(f"\n<b>Recommandations ({len(recs)})</b>")
        for r in recs[:4]:
            lines.append(f"  [{r.get('priority', '?').upper():4s}] {r.get('fix', '')[:60]}")

    return "\n".join(lines), back_keyboard()


def section_trends():
    """Trend analysis."""
    data = run_script("dispatch_trend_analyzer", "--once")
    if "error" in data:
        return f"Erreur: {data['error']}", back_keyboard()

    s = data.get("summary", {})
    lines = [
        "<b>Tendances Dispatch</b>", "",
        f"  Emergents:     {s.get('emerging', 0)}",
        f"  En declin:     {s.get('declining', 0)}",
        f"  Amelioration:  {s.get('improving', 0)}",
        f"  Degradation:   {s.get('degrading', 0)}", "",
    ]

    for category, label in [
        ("emerging", "Patterns emergents"),
        ("improving", "En amelioration"),
        ("degrading", "En degradation"),
    ]:
        items = data.get("trends", {}).get(category, [])
        if items:
            lines.append(f"<b>{label}</b>")
            for t in items[:5]:
                arrow = trend_arrow(t.get("volume_change_pct", 0))
                vol = t.get("volume_change_pct", "?")
                sr = t.get("recent_success_pct", "?")
                lines.append(f"  {arrow}{t['pattern']:12s} vol:{vol:+.0f}% ok:{sr}%")
            lines.append("")

    return "\n".join(lines), back_keyboard()


def section_tests():
    """Self-test results."""
    lines = ["<b>Self-Tests COWORK</b>", ""]

    for level in [1, 2, 3]:
        data = run_script("cowork_self_test_runner", ["--level", str(level)])
        if "error" not in data:
            p = data.get("passed", 0)
            t = data.get("total_tests", 0)
            rate = data.get("success_rate_pct", 0)
            dur = data.get("duration_ms", 0)
            names = {1: "Syntax", 2: "Imports", 3: "--help"}
            icon = "OK" if rate == 100 else "!!"
            lines.append(f"  L{level} {names.get(level, '?'):7s} [{icon}] {p}/{t} ({rate}%) {dur}ms")

    fails = 0
    data3 = run_script("cowork_self_test_runner", ["--level", "3", "--failed"])
    if "error" not in data3:
        for f in data3.get("failures", []):
            fails += 1
            if fails <= 5:
                err = f.get("tests", [{}])[0].get("error", "?")[:50]
                lines.append(f"    !! {f['script']}: {err}")

    lines.append(f"\n<code>{datetime.now().strftime('%H:%M:%S')}</code>")
    return "\n".join(lines), back_keyboard()


def section_cycle():
    """Run improvement cycle."""
    data = run_script("cowork_full_cycle", "--quick")
    if "error" in data:
        return f"Erreur: {data['error']}", back_keyboard()

    lines = [
        "<b>Cycle d'amelioration</b>", "",
        f"  Resultat: {data.get('ok', 0)}/{data.get('total_scripts', 0)} OK",
        f"  Duree:    {data.get('duration_ms', 0)}ms", "",
    ]

    for r in data.get("results", []):
        icon = status_icon(r["status"] == "ok")
        summary = r.get("summary", {})
        detail = " | ".join(f"{k}={v}" for k, v in summary.items()) if summary else ""
        dur = r.get("duration_ms", 0)
        lines.append(f"  [{icon}] {r['label']:15s} {dur:5d}ms")
        if detail:
            lines.append(f"       {detail[:55]}")

    # Full cycle button
    kb = [
        [{"text": "Cycle COMPLET (10 analyses)", "callback_data": "run:full_cycle"}],
        [{"text": "<< Menu principal", "callback_data": "sec:main"}],
    ]
    return "\n".join(lines), kb


def section_improve():
    """Auto-improvement recommendations."""
    data = run_script("cowork_auto_improver", "--dry-run")
    if "error" in data:
        return f"Erreur: {data['error']}", back_keyboard()

    lines = [
        "<b>Auto-Amelioration</b>", "",
        f"  Total:        {data.get('total_improvements', 0)}",
        f"  Haute prio:   {data.get('by_priority', {}).get('high', 0)}",
        f"  Moyenne prio: {data.get('by_priority', {}).get('medium', 0)}",
        f"  Basse prio:   {data.get('by_priority', {}).get('low', 0)}", "",
        f"<b>Par type</b>",
    ]

    for t, count in data.get("by_type", {}).items():
        lines.append(f"  {t:20s} {count}")

    hp = data.get("high_priority", [])
    if hp:
        lines.append(f"\n<b>Haute priorite ({len(hp)})</b>")
        for h in hp[:6]:
            lines.append(f"  [{h['type'][:8]:8s}] {h['target'][:15]:15s}")
            lines.append(f"    {h['details'][:55]}")

    kb = [
        [{"text": "APPLIQUER ameliorations", "callback_data": "run:apply_improve"}],
        [{"text": "<< Menu principal", "callback_data": "sec:main"}],
    ]
    return "\n".join(lines), kb


def section_nodes():
    """Per-node performance breakdown."""
    edb = _get_etoile()
    if not edb:
        return "etoile.db introuvable", back_keyboard()

    rows = edb.execute("""
        SELECT node,
               COUNT(*) as total,
               AVG(CASE WHEN success=1 THEN 100.0 ELSE 0.0 END) as rate,
               AVG(latency_ms) as avg_lat,
               AVG(quality_score) as avg_q,
               MIN(latency_ms) as min_lat,
               MAX(latency_ms) as max_lat,
               SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as fails
        FROM agent_dispatch_log
        GROUP BY node
        ORDER BY total DESC
    """).fetchall()
    edb.close()

    lines = ["<b>Performance par Noeud</b>", ""]
    for r in rows:
        node = r["node"] or "?"
        total = r["total"]
        rate = r["rate"] or 0
        lat = r["avg_lat"] or 0
        q = r["avg_q"] or 0
        fails = r["fails"] or 0

        lines.append(f"<b>{node}</b>  ({total} dispatches)")
        lines.append(f"  Success  {bar(rate)}")
        lines.append(f"  Qualite  {bar(q * 100)}")
        lines.append(f"  Latence  {bar_latency(lat)}")
        lines.append(f"  Echecs   {fails}  |  Min/Max: {r['min_lat'] or 0:.0f}/{r['max_lat'] or 0:.0f}ms")
        lines.append("")

    lines.append(f"<code>{datetime.now().strftime('%H:%M:%S')}</code>")
    return "\n".join(lines), back_keyboard()


def section_history():
    """Recent dispatch history (last 20)."""
    edb = _get_etoile()
    if not edb:
        return "etoile.db introuvable", back_keyboard()

    rows = edb.execute("""
        SELECT id, timestamp, classified_type, node, success, latency_ms, quality_score
        FROM agent_dispatch_log
        ORDER BY id DESC LIMIT 20
    """).fetchall()
    edb.close()

    lines = ["<b>Derniers 20 Dispatches</b>", "",
             "<code>ID   Type         Node OK  Lat(ms) Q</code>",
             "<code>" + "-" * 44 + "</code>"]

    for r in rows:
        ok = "ok" if r["success"] else "!!"
        pat = (r["classified_type"] or "?")[:12]
        node = (r["node"] or "?")[:3]
        lat = r["latency_ms"] or 0
        q = r["quality_score"] or 0
        lines.append(f"<code>{r['id']:4d} {pat:12s} {node:3s} {ok:2s} {lat:7.0f} {q:.2f}</code>")

    lines.append(f"\n<code>{datetime.now().strftime('%H:%M:%S')}</code>")
    return "\n".join(lines), back_keyboard()


def section_search():
    """Script search — show top scripts by category."""
    scripts = sorted(SCRIPT_DIR.glob("*.py"))
    total = len(scripts)

    # Categorize
    categories = {}
    for s in scripts:
        name = s.stem
        if name.startswith("dispatch_"):
            cat = "dispatch"
        elif name.startswith("cowork_"):
            cat = "cowork"
        elif name.startswith("cluster_"):
            cat = "cluster"
        elif name.startswith("telegram_"):
            cat = "telegram"
        elif name.startswith("gpu_") or name.startswith("cuda_"):
            cat = "gpu"
        elif name.startswith("pattern_"):
            cat = "pattern"
        elif name.startswith("trading_") or name.startswith("mexc_"):
            cat = "trading"
        elif name.startswith("auto_") or name.startswith("smart_"):
            cat = "auto"
        else:
            cat = "other"
        categories.setdefault(cat, []).append(name)

    lines = [f"<b>Scripts COWORK ({total})</b>", ""]

    # Sort categories by size
    for cat, items in sorted(categories.items(), key=lambda x: -len(x[1])):
        lines.append(f"  <b>{cat}</b> ({len(items)})")
        for name in items[:5]:
            lines.append(f"    {name}")
        if len(items) > 5:
            lines.append(f"    ... +{len(items) - 5}")
        lines.append("")

    # Size stats
    total_kb = sum(s.stat().st_size for s in scripts) // 1024
    lines.append(f"Total: {total} scripts, {total_kb} KB")
    lines.append(f"<code>{datetime.now().strftime('%H:%M:%S')}</code>")
    return "\n".join(lines), back_keyboard()


def section_scheduler():
    """Show scheduler status if available."""
    data = run_script("cowork_scheduler", "--status")
    if "error" in data:
        return f"Scheduler: {data['error']}", back_keyboard()

    tasks = data.get("tasks", [])
    lines = ["<b>Scheduler COWORK</b>", "",
             f"  Taches: {len(tasks)}", ""]

    for t in tasks:
        enabled = "ON" if t.get("enabled") else "off"
        name = t.get("task_name", "?")[:15]
        interval = t.get("interval_minutes", 0)
        runs = t.get("run_count", 0)
        status = t.get("last_status", "?")[:8]
        minutes_until = t.get("minutes_until_next", 0)

        lines.append(f"  [{enabled:3s}] <b>{name:15s}</b> {interval:>4d}m")
        lines.append(f"         runs={runs:3d}  next={minutes_until:.0f}m  last={status}")

    kb = [
        [{"text": "Executer taches dues", "callback_data": "run:run_scheduler"}],
        [{"text": "<< Menu principal", "callback_data": "sec:main"}],
    ]
    return "\n".join(lines), kb


def run_scheduler():
    """Run due scheduler tasks."""
    data = run_script("cowork_scheduler", "--once")
    if "error" in data:
        return f"Erreur: {data['error']}", back_keyboard()

    lines = [
        "<b>Scheduler Execute</b>", "",
        f"  Executees: {data.get('tasks_run', 0)}",
        f"  Ignorees:  {data.get('tasks_skipped', 0)}",
    ]
    for t in data.get("results", []):
        icon = status_icon(t.get("status") == "ok")
        lines.append(f"  [{icon}] {t.get('task_name', '?'):15s} {t.get('duration_ms', 0)}ms")

    return "\n".join(lines), back_keyboard()


def run_full_cycle():
    """Run the full 10-analysis cycle."""
    data = run_script("cowork_full_cycle", "--once")
    if "error" in data:
        return f"Erreur: {data['error']}", back_keyboard()

    lines = [
        "<b>Cycle COMPLET</b>", "",
        f"  {data.get('ok', 0)}/{data.get('total_scripts', 0)} OK en {data.get('duration_ms', 0)}ms", "",
    ]
    for r in data.get("results", []):
        icon = status_icon(r["status"] == "ok")
        summary = r.get("summary", {})
        detail = " | ".join(f"{k}={v}" for k, v in list(summary.items())[:3]) if summary else ""
        lines.append(f"  [{icon}] {r['label']:15s} {detail[:45]}")

    return "\n".join(lines), back_keyboard()


def apply_improvements():
    """Apply auto-improvements."""
    data = run_script("cowork_auto_improver", "--once")
    if "error" in data:
        return f"Erreur: {data['error']}", back_keyboard()

    lines = [
        "<b>Ameliorations appliquees</b>", "",
        f"  Appliquees: {data.get('applied', 0)}",
        f"  Ignorees:   {data.get('skipped', 0)}",
        f"  Total:      {data.get('total', 0)}", "",
    ]
    return "\n".join(lines), back_keyboard()


# ── Database helper ──────────────────────────────────────────────────────────

def _get_etoile():
    """Get etoile.db connection."""
    if not ETOILE_DB.exists():
        return None
    conn = sqlite3.connect(str(ETOILE_DB))
    conn.row_factory = sqlite3.Row
    return conn


# ── Section router ───────────────────────────────────────────────────────────

SECTIONS = {
    "main": section_main,
    "status": section_main,
    "cluster": section_cluster,
    "gpu": section_gpu,
    "dispatch": section_dispatch,
    "nodes": section_nodes,
    "history": section_history,
    "quality": section_quality,
    "errors": section_errors,
    "trends": section_trends,
    "tests": section_tests,
    "cycle": section_cycle,
    "improve": section_improve,
    "search": section_search,
    "scheduler": section_scheduler,
}

ACTIONS = {
    "full_cycle": run_full_cycle,
    "apply_improve": apply_improvements,
    "run_scheduler": run_scheduler,
}


# ── Polling loop ─────────────────────────────────────────────────────────────

def poll():
    """Main polling loop — handles commands and callback queries."""
    offset = 0
    print(f"[{datetime.now().strftime('%H:%M:%S')}] COWORK Dashboard bot started")
    print(f"  Chat ID: {TELEGRAM_CHAT_ID}")
    print(f"  Sections: {len(SECTIONS)}")
    print(f"  Listening...")

    while True:
        try:
            result = tg_call("getUpdates", {"offset": offset, "timeout": 30})

            for update in result.get("result", []):
                offset = update["update_id"] + 1

                # Handle callback queries (button presses)
                cb = update.get("callback_query")
                if cb:
                    cb_data = cb.get("data", "")
                    cb_id = cb["id"]
                    msg_id = cb.get("message", {}).get("message_id")
                    chat_id = cb.get("message", {}).get("chat", {}).get("id")

                    if str(chat_id) != TELEGRAM_CHAT_ID:
                        continue

                    if cb_data.startswith("sec:"):
                        section = cb_data[4:]
                        handler = SECTIONS.get(section)
                        if handler:
                            answer_callback(cb_id, f"Loading {section}...")
                            text, kb = handler()
                            if msg_id:
                                edit_msg(msg_id, text, kb, chat_id)
                            else:
                                send_msg(text, kb, chat_id)
                            _log_report(section)
                            print(f"  [{datetime.now().strftime('%H:%M:%S')}] Section: {section}")

                    elif cb_data.startswith("run:"):
                        action = cb_data[4:]
                        handler = ACTIONS.get(action)
                        if handler:
                            answer_callback(cb_id, f"Running {action}...")
                            text, kb = handler()
                            if msg_id:
                                edit_msg(msg_id, text, kb, chat_id)
                            else:
                                send_msg(text, kb, chat_id)
                            print(f"  [{datetime.now().strftime('%H:%M:%S')}] Action: {action}")

                    continue

                # Handle text commands
                msg = update.get("message", {})
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")

                if str(chat_id) != TELEGRAM_CHAT_ID:
                    continue

                if text in ("/dashboard", "/d", "/start", "/cowork"):
                    text_out, kb = section_main()
                    send_msg(text_out, kb, chat_id)
                    _log_report("dashboard_open")
                    print(f"  [{datetime.now().strftime('%H:%M:%S')}] Dashboard opened")

                elif text.startswith("/search "):
                    query = text[8:].strip().lower()
                    results = [s.stem for s in SCRIPT_DIR.glob("*.py") if query in s.stem.lower()]
                    if results:
                        out = f"<b>Recherche: '{query}'</b>\n\n"
                        out += "\n".join(f"  {r}" for r in results[:20])
                        out += f"\n\n{len(results)} resultats"
                    else:
                        out = f"Aucun script pour '{query}'"
                    send_msg(out, back_keyboard(), chat_id)

                elif text.startswith("/cowork_"):
                    cmd = text.split("@")[0].replace("/cowork_", "")
                    handler = SECTIONS.get(cmd)
                    if handler:
                        text_out, kb = handler()
                        send_msg(text_out, kb, chat_id)
                        _log_report(cmd)

        except Exception as e:
            print(f"  [{datetime.now().strftime('%H:%M:%S')}] Error: {e}")
            time.sleep(5)


def _log_report(report_type):
    """Log report to DB."""
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO telegram_reports (timestamp, report_type) VALUES (?, ?)",
            (datetime.now().isoformat(), report_type)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="COWORK Interactive Telegram Dashboard")
    parser.add_argument("--poll", action="store_true", help="Start interactive bot")
    parser.add_argument("--once", action="store_true", help="Send main dashboard")
    parser.add_argument("--health", action="store_true", help="Send cluster health")
    parser.add_argument("--full", action="store_true", help="Send all sections")
    parser.add_argument("--stats", action="store_true", help="Show sent reports")
    args = parser.parse_args()

    if not any([args.poll, args.once, args.health, args.full, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.poll:
        poll()
    elif args.stats:
        conn = get_db()
        rows = conn.execute("""
            SELECT report_type, COUNT(*) as cnt, MAX(timestamp) as last
            FROM telegram_reports GROUP BY report_type ORDER BY cnt DESC
        """).fetchall()
        conn.close()
        print(json.dumps({"reports": [dict(r) for r in rows]}, indent=2))
    elif args.full:
        for name, handler in SECTIONS.items():
            if name in ("main", "status"):
                continue
            text, kb = handler()
            send_msg(text, kb)
            time.sleep(1)
        print(json.dumps({"sent": len(SECTIONS) - 1}))
    elif args.health:
        text, kb = section_cluster()
        mid = send_msg(text, kb)
        print(json.dumps({"sent": True, "message_id": mid}))
    else:
        text, kb = section_main()
        mid = send_msg(text, kb)
        print(json.dumps({"sent": True, "message_id": mid}))


if __name__ == "__main__":
    main()
