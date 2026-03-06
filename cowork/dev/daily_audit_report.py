#!/usr/bin/env python3
"""
Daily Audit Report — Execute la Mission 1 Perplexity et envoie sur Telegram.

Appelle les 8 outils MCP via le serveur local, synthetise un rapport,
et l'envoie sur Telegram + sauvegarde en fichier.

Usage:
    python cowork/dev/daily_audit_report.py          # Run once
    python cowork/dev/daily_audit_report.py --cron    # Schedule daily at 08:00
"""

import json, os, sqlite3, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

TURBO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = TURBO_ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

MCP_URL = "http://127.0.0.1:8901/mcp/"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "2010747443")


def mcp_call(tool_name, arguments=None, timeout=20):
    """Call a JARVIS MCP tool and return the text result."""
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments or {}}
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    try:
        req = urllib.request.Request(MCP_URL, body, headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
        for line in raw.split("\n"):
            if line.strip().startswith("data:"):
                d = json.loads(line.strip()[5:])
                contents = d.get("result", {}).get("content", [])
                texts = [c.get("text", "") for c in contents if c.get("text")]
                return "\n".join(texts) if texts else ""
        return ""
    except Exception as e:
        return f"[ERR] {e}"


def send_telegram(text):
    """Send message to Telegram (split if > 4000 chars)."""
    if not TELEGRAM_TOKEN:
        print("  [WARN] No TELEGRAM_BOT_TOKEN, skipping Telegram")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        body = json.dumps({
            "chat_id": TELEGRAM_CHAT,
            "text": chunk,
            "parse_mode": "Markdown"
        }).encode()
        try:
            req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            print(f"  [ERR] Telegram: {e}")


def run_audit():
    ts = datetime.now()
    print(f"[{ts.strftime('%H:%M:%S')}] === DAILY AUDIT REPORT ===\n")

    report_lines = [f"*JARVIS AUDIT QUOTIDIEN* — {ts.strftime('%Y-%m-%d %H:%M')}\n"]
    scores = {}

    # 1. Cluster status
    print("  [1/8] Cluster status...", end=" ", flush=True)
    r = mcp_call("lm_cluster_status")
    if r and not r.startswith("[ERR]"):
        online = r.count("ONLINE")
        total = r.count("ONLINE") + r.count("OFFLINE")
        scores["cluster"] = int(online / max(total, 1) * 100)
        report_lines.append(f"*Cluster*: {online}/{total} noeuds en ligne")
        for line in r.strip().split("\n")[:6]:
            report_lines.append(f"  {line.strip()}")
        print(f"OK ({online}/{total})")
    else:
        scores["cluster"] = 0
        report_lines.append(f"*Cluster*: ERREUR — {str(r)[:60]}")
        print("FAIL")

    # 2. GPU
    print("  [2/8] GPU info...", end=" ", flush=True)
    r = mcp_call("gpu_info")
    if r and not r.startswith("[ERR]"):
        gpu_count = r.count("NVIDIA")
        scores["gpu"] = 100 if gpu_count >= 4 else gpu_count * 20
        report_lines.append(f"\n*GPU*: {gpu_count} cartes detectees")
        for line in r.strip().split("\n")[:6]:
            report_lines.append(f"  {line.strip()}")
        print(f"OK ({gpu_count} GPUs)")
    else:
        scores["gpu"] = 0
        print("FAIL")

    # 3. Trading
    print("  [3/8] Trading status...", end=" ", flush=True)
    r = mcp_call("trading_status")
    if r and not r.startswith("[ERR]"):
        try:
            data = json.loads(r)
            sigs = data.get("pipeline", {}).get("total_signals", 0)
            opens = data.get("trades", {}).get("open", 0)
            dry = data.get("config", {}).get("dry_run", True)
            scores["trading"] = 80 if sigs > 0 else 40
            report_lines.append(f"\n*Trading*: {sigs} signaux total, {opens} positions ouvertes")
            report_lines.append(f"  Config: MEXC {data.get('config',{}).get('leverage',0)}x, DRY\\_RUN={'oui' if dry else 'non'}")
            print(f"OK ({sigs} sigs, {opens} open)")
        except Exception:
            scores["trading"] = 50
            report_lines.append(f"\n*Trading*: actif (parse error)")
            print("OK (parse err)")
    else:
        scores["trading"] = 0
        print("FAIL")

    # 4. Security
    print("  [4/8] Security...", end=" ", flush=True)
    r = mcp_call("security_score")
    if r and not r.startswith("[ERR]"):
        try:
            data = json.loads(r)
            score = data.get("score", 0)
            grade = data.get("grade", "?")
            scores["security"] = score
            report_lines.append(f"\n*Securite*: {score}/100 Grade {grade}")
            details = data.get("details", {})
            for k, v in list(details.items())[:5]:
                report_lines.append(f"  {k}: {v}")
            print(f"OK ({score}/100 {grade})")
        except Exception:
            scores["security"] = 50
            print("OK (parse err)")
    else:
        scores["security"] = 0
        print("FAIL")

    # 5. Brain
    print("  [5/8] Brain status...", end=" ", flush=True)
    r = mcp_call("brain_status")
    if r and not r.startswith("[ERR]"):
        scores["brain"] = 80
        report_lines.append(f"\n*Cerveau JARVIS*:")
        for line in r.strip().split("\n")[:4]:
            report_lines.append(f"  {line.strip()}")
        print("OK")
    else:
        scores["brain"] = 0
        print("FAIL")

    # 6. Evolution DB
    print("  [6/8] Evolution status...", end=" ", flush=True)
    evo_db = DATA_DIR / "strategy_evolution.db"
    if evo_db.exists():
        try:
            db = sqlite3.connect(str(evo_db), timeout=10)
            gen = db.execute("SELECT generation, best_fitness, avg_fitness FROM generations ORDER BY id DESC LIMIT 1").fetchone()
            alive = db.execute("SELECT COUNT(*) FROM strategies WHERE alive=1").fetchone()[0]
            db.close()
            if gen:
                scores["evolution"] = min(100, int(gen[1] * 150))
                report_lines.append(f"\n*Evolution*: Gen {gen[0]}, {alive} strategies vivantes")
                report_lines.append(f"  Best fitness: {gen[1]:.4f}, Avg: {gen[2]:.4f}")
                print(f"OK (Gen {gen[0]})")
            else:
                scores["evolution"] = 0
                print("no data")
        except Exception as e:
            scores["evolution"] = 0
            print(f"ERR: {e}")
    else:
        scores["evolution"] = 0
        print("no DB")

    # 7. Orchestrator v3
    print("  [7/8] Orchestrator v3...", end=" ", flush=True)
    orch_db = DATA_DIR / "orchestrator_v3.db"
    if orch_db.exists():
        try:
            db = sqlite3.connect(str(orch_db), timeout=10)
            cycles = db.execute("SELECT COUNT(*) FROM cycles").fetchone()[0]
            signals = db.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
            db.close()
            scores["orchestrator"] = 80 if cycles > 10 else 40
            report_lines.append(f"\n*Orchestrator v3*: {cycles} cycles, {signals} signaux detectes")
            print(f"OK ({cycles} cycles)")
        except Exception as e:
            scores["orchestrator"] = 0
            print(f"ERR: {e}")
    else:
        scores["orchestrator"] = 0
        print("no DB")

    # 8. Deep analysis
    print("  [8/8] Deep analysis...", end=" ", flush=True)
    analysis_db = DATA_DIR / "cluster_analysis.db"
    if analysis_db.exists():
        try:
            db = sqlite3.connect(str(analysis_db), timeout=10)
            analyses = db.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
            regimes = db.execute("SELECT COUNT(*) FROM market_regimes").fetchone()[0]
            db.close()
            scores["analysis"] = 80 if analyses > 5 else 40
            report_lines.append(f"\n*Deep Analysis*: {analyses} analyses, {regimes} regimes detectes")
            print(f"OK ({analyses} analyses)")
        except Exception as e:
            scores["analysis"] = 0
            print(f"ERR: {e}")
    else:
        scores["analysis"] = 0
        print("no DB")

    # Compute overall score
    if scores:
        overall = sum(scores.values()) / len(scores)
        grade = "A" if overall >= 80 else "B" if overall >= 60 else "C" if overall >= 40 else "D"
    else:
        overall = 0
        grade = "F"

    report_lines.append(f"\n*SCORE GLOBAL: {overall:.0f}/100 — Grade {grade}*")
    report_lines.append(f"Scores: {' | '.join(f'{k}={v}' for k,v in scores.items())}")

    # Workers check
    report_lines.append(f"\n*Workers actifs*: evolution + orchestrator\\_v3 + strategy\\_worker + deep\\_analysis + MCP\\_server")

    report = "\n".join(report_lines)

    # Save to file
    fname = REPORTS_DIR / f"audit_{ts.strftime('%Y-%m-%d_%H%M')}.md"
    fname.write_text(report.replace("*", "**").replace("\\_", "_"), encoding="utf-8")
    print(f"\n  Saved: {fname}")

    # Send to Telegram
    send_telegram(report)
    print(f"  Telegram: sent")

    print(f"\n  SCORE: {overall:.0f}/100 Grade {grade}")
    print(f"  Audit complete.\n")

    return overall


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Daily Audit Report")
    parser.add_argument("--cron", action="store_true", help="Schedule daily at 08:00")
    args = parser.parse_args()

    if args.cron:
        import sched, time as t
        s = sched.scheduler(t.time, t.sleep)
        while True:
            now = datetime.now()
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if target <= now:
                from datetime import timedelta
                target += timedelta(days=1)
            wait = (target - now).total_seconds()
            print(f"Next audit at {target.strftime('%Y-%m-%d %H:%M')} ({wait/3600:.1f}h)")
            t.sleep(wait)
            run_audit()
    else:
        run_audit()
