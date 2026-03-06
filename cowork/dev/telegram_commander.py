#!/usr/bin/env python3
"""JARVIS Telegram Commander — Commandes pipeline avec reponses soignees."""
import json, sys, os, subprocess, urllib.request, time
from datetime import datetime

TOKEN = TELEGRAM_TOKEN
CHAT_ID = TELEGRAM_CHAT
DEV_DIR = "C:/Users/franc/.openclaw/workspace/dev"

# ─── FORMATAGE TELEGRAM SOIGNE ─────────────────────────────────────

def send_telegram(msg, parse_mode="Markdown"):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = json.dumps({"chat_id": CHAT_ID, "text": msg[:4000], "parse_mode": parse_mode}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}), timeout=10)
        return True
    except:
        # Fallback sans Markdown
        data = json.dumps({"chat_id": CHAT_ID, "text": msg[:4000]}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}), timeout=10)
            return True
        except:
            return False

def run_script(name, args="--once", timeout=30):
    path = os.path.join(DEV_DIR, f"{name}.py")
    if not os.path.exists(path):
        return {"ok": False, "output": f"Script {name}.py introuvable"}
    try:
        r = subprocess.run(["python", path, args], capture_output=True, text=True, timeout=timeout, cwd=DEV_DIR)
        return {"ok": r.returncode == 0, "output": r.stdout[:1500]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "TIMEOUT"}
    except Exception as e:
        return {"ok": False, "output": str(e)[:200]}

# ─── PIPELINES TELEGRAM ────────────────────────────────────────────

def pipeline_status():
    """Pipeline: Status complet du systeme."""
    lines = ["🖥️ *JARVIS — Status Systeme*", f"📅 {datetime.now().strftime('%d/%m %H:%M')}\n"]

    # Cluster
    r = run_script("auto_monitor")
    if r["ok"]:
        for line in r["output"].splitlines():
            if "M1" in line or "OL1" in line or "M2" in line or "M3" in line:
                status = "🟢" if "OK" in line or "UP" in line else "🔴"
                lines.append(f"{status} {line.strip()}")
    else:
        lines.append("🔴 Cluster: erreur check")

    lines.append("")

    # System
    r = run_script("system_benchmark", "--quick")
    if r["ok"]:
        lines.append(f"⚡ {r['output'].strip()}")

    # GPU
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,temperature.gpu,memory.used,memory.total",
                           "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            for line in r.stdout.strip().splitlines()[:2]:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    lines.append(f"🎮 {parts[0]}: {parts[1]}°C | {parts[2]}/{parts[3]}MB")
    except: pass

    return "\n".join(lines)

def pipeline_trading():
    """Pipeline: Analyse trading."""
    lines = ["📈 *JARVIS — Trading Pipeline*", f"📅 {datetime.now().strftime('%d/%m %H:%M')}\n"]

    r = run_script("auto_trader")
    if r["ok"]:
        for line in r["output"].splitlines():
            if "SIGNAL" in line.upper() or ">" in line:
                lines.append(f"🔔 {line.strip()}")
            elif "SCAN" in line.upper():
                lines.append(f"📊 {line.strip()}")
            elif any(c in line for c in ["BTC", "ETH", "SOL", "SUI", "PEPE", "DOGE", "XRP"]):
                lines.append(f"  {line.strip()}")
    else:
        lines.append("❌ Scan erreur")

    # Risk
    r = run_script("risk_manager")
    if r["ok"] and r["output"].strip():
        lines.append(f"\n💰 *Risk Manager*")
        for line in r["output"].splitlines()[:5]:
            lines.append(f"  {line.strip()}")

    return "\n".join(lines)

def pipeline_health():
    """Pipeline: Health check complet."""
    lines = ["🏥 *JARVIS — Health Check*", f"📅 {datetime.now().strftime('%d/%m %H:%M')}\n"]

    r = run_script("health_checker")
    if r["ok"]:
        for line in r["output"].splitlines():
            if "[OK]" in line or "OK" in line:
                lines.append(f"✅ {line.strip()}")
            elif "[!!]" in line or "DOWN" in line:
                lines.append(f"❌ {line.strip()}")
            elif "Grade" in line:
                lines.append(f"📊 {line.strip()}")
            elif "HEALTH" in line:
                lines.append(f"🏥 {line.strip()}")
            else:
                lines.append(f"  {line.strip()}")
    return "\n".join(lines)

def pipeline_services():
    """Pipeline: Services Windows."""
    lines = ["⚙️ *JARVIS — Services*", f"📅 {datetime.now().strftime('%d/%m %H:%M')}\n"]

    r = run_script("service_watcher")
    if r["ok"]:
        for line in r["output"].splitlines():
            if "[OK]" in line:
                lines.append(f"✅ {line.strip()}")
            elif "DOWN" in line or "CRITICAL" in line:
                lines.append(f"❌ {line.strip()}")
            elif "SERVICE" in line:
                lines.append(f"⚙️ {line.strip()}")
            else:
                lines.append(f"  {line.strip()}")
    return "\n".join(lines)

def pipeline_benchmark():
    """Pipeline: Benchmark systeme."""
    lines = ["🏎️ *JARVIS — Benchmark*", f"📅 {datetime.now().strftime('%d/%m %H:%M')}\n"]

    r = run_script("system_benchmark", "--once", timeout=60)
    if r["ok"]:
        for line in r["output"].splitlines():
            if "TOTAL" in line:
                lines.append(f"🏆 *{line.strip()}*")
            elif ":" in line and ("pts" in line or "ms" in line):
                lines.append(f"  📊 {line.strip()}")
            elif "BENCHMARK" in line:
                lines.append(f"🏎️ {line.strip()}")
            else:
                lines.append(f"  {line.strip()}")
    return "\n".join(lines)

def pipeline_emails():
    """Pipeline: Lecture emails via jarvis_mail.py."""
    import imaplib, email as email_mod
    from email.header import decode_header as dh

    def decode_str(s):
        if not s: return ''
        parts = dh(s)
        r = []
        for p, enc in parts:
            r.append(p.decode(enc or 'utf-8', errors='replace') if isinstance(p, bytes) else str(p))
        return ' '.join(r)

    # Load config
    config_path = os.path.join(DEV_DIR, "email_config.json")
    accounts = []
    if os.path.exists(config_path):
        with open(config_path) as f:
            cfg = json.load(f)
            accounts = [a for a in cfg.get("accounts", []) if a.get("password", "").startswith("APP_") == False and len(a.get("password", "")) == 16]

    # Fallback to hardcoded miningexpert31
    if not accounts:
        accounts = [{"email": "miningexpert31@gmail.com", "password": "ipicqcsimiitoxwj", "imap_host": "imap.gmail.com"}]

    lines = ["📬 *JARVIS — Emails*", f"📅 {datetime.now().strftime('%d/%m %H:%M')}\n"]

    for acct in accounts:
        try:
            mail = imaplib.IMAP4_SSL(acct.get("imap_host", "imap.gmail.com"))
            mail.login(acct["email"], acct["password"])
            mail.select("INBOX")
            _, data = mail.search(None, "ALL")
            ids = data[0].split()
            last_5 = ids[-5:][::-1]

            lines.append(f"📧 *{acct['email'].split('@')[0]}*")
            emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
            for i, eid in enumerate(last_5):
                _, msg_data = mail.fetch(eid, "(RFC822)")
                msg = email_mod.message_from_bytes(msg_data[0][1])
                subj = decode_str(msg.get("Subject", "(sans sujet)"))
                frm = decode_str(msg.get("From", "?"))
                sender = frm.split("<")[0].strip().strip('"') if "<" in frm else frm
                lines.append(f"  {emojis[i]} *{subj[:50]}*")
                lines.append(f"     De: {sender[:35]}")

            mail.logout()
            lines.append("")
        except Exception as e:
            lines.append(f"  ❌ {acct['email']}: {str(e)[:60]}")

    return "\n".join(lines)

def pipeline_workspace():
    """Pipeline: Etat du workspace COWORK."""
    lines = ["🗂️ *JARVIS — Workspace COWORK*", f"📅 {datetime.now().strftime('%d/%m %H:%M')}\n"]

    scripts = sorted([f for f in os.listdir(DEV_DIR) if f.endswith(".py")])
    lines.append(f"📦 *{len(scripts)} scripts* dans dev/\n")

    # Group by prefix
    groups = {}
    for s in scripts:
        prefix = s.split("_")[0] if "_" in s else s.replace(".py", "")
        groups.setdefault(prefix, []).append(s.replace(".py", ""))

    for prefix in sorted(groups.keys()):
        items = groups[prefix]
        lines.append(f"  *{prefix}* ({len(items)}): {', '.join(items[:5])}")

    # Crons
    try:
        r = subprocess.run(["openclaw", "cron", "list"], capture_output=True, text=True, timeout=10)
        cron_count = r.stdout.count("every ") + r.stdout.count("cron ")
        lines.append(f"\n⏰ *{cron_count} cron jobs* actifs")
    except:
        lines.append(f"\n⏰ Cron: non disponible")

    return "\n".join(lines)

def pipeline_full_report():
    """Pipeline: Rapport complet."""
    lines = ["📋 *JARVIS — Rapport Complet*", f"📅 {datetime.now().strftime('%d/%m %H:%M')}", "═" * 30 + "\n"]

    # Status
    r = run_script("auto_monitor")
    if r["ok"]:
        cluster_lines = [l for l in r["output"].splitlines() if any(x in l for x in ["M1", "M2", "M3", "OL1"])]
        up = sum(1 for l in cluster_lines if "OK" in l or "UP" in l)
        lines.append(f"🖥️ *Cluster*: {up}/{len(cluster_lines)} noeuds UP")

    # Trading
    r = run_script("auto_trader")
    if r["ok"]:
        signals = [l for l in r["output"].splitlines() if "SIGNAL" in l.upper()]
        lines.append(f"📈 *Trading*: {len(signals)} signaux detectes")

    # Scripts
    scripts = [f for f in os.listdir(DEV_DIR) if f.endswith(".py")]
    lines.append(f"📦 *Workspace*: {len(scripts)} scripts")

    # Disks
    import shutil
from _paths import TELEGRAM_TOKEN, TELEGRAM_CHAT
    for drive, name in [("C:/", "C:"), ("F:/", "F:")]:
        try:
            total, used, free = shutil.disk_usage(drive)
            lines.append(f"💾 *{name}* {round(free/1024**3)}GB libres / {round(total/1024**3)}GB")
        except: pass

    lines.append(f"\n_Rapport genere a {datetime.now().strftime('%H:%M:%S')}_")
    return "\n".join(lines)

# ─── COMMANDES DISPONIBLES ──────────────────────────────────────────

COMMANDS = {
    "status": {"fn": pipeline_status, "desc": "Status systeme complet"},
    "trading": {"fn": pipeline_trading, "desc": "Analyse trading MEXC"},
    "health": {"fn": pipeline_health, "desc": "Health check complet"},
    "services": {"fn": pipeline_services, "desc": "Services Windows"},
    "benchmark": {"fn": pipeline_benchmark, "desc": "Benchmark CPU/RAM/GPU"},
    "emails": {"fn": pipeline_emails, "desc": "Lire les derniers emails"},
    "workspace": {"fn": pipeline_workspace, "desc": "Etat workspace COWORK"},
    "report": {"fn": pipeline_full_report, "desc": "Rapport complet"},
}

def show_help():
    lines = ["🤖 *JARVIS Telegram Commander*\n", "📋 *Commandes disponibles :*\n"]
    for cmd, info in COMMANDS.items():
        lines.append(f"  `/j {cmd}` — {info['desc']}")
    lines.append(f"\n💡 Utilisation : `python telegram_commander.py --cmd COMMANDE`")
    return "\n".join(lines)

if __name__ == "__main__":
    if "--cmd" in sys.argv:
        idx = sys.argv.index("--cmd")
        cmd = sys.argv[idx + 1].lower() if len(sys.argv) > idx + 1 else "help"

        if cmd == "help":
            msg = show_help()
        elif cmd in COMMANDS:
            print(f"[PIPELINE] Running: {cmd}...")
            msg = COMMANDS[cmd]["fn"]()
        elif cmd == "all":
            for name in ["status", "trading", "health"]:
                msg = COMMANDS[name]["fn"]()
                if msg:
                    send_telegram(msg)
                    time.sleep(1)
            msg = None
        else:
            msg = f"❌ Commande inconnue: `{cmd}`\n\nTapez `/j help` pour la liste."

        if msg:
            send_telegram(msg)
            print(f"Sent to Telegram: {cmd}")

    elif "--list" in sys.argv:
        print("[TELEGRAM COMMANDS]")
        for cmd, info in COMMANDS.items():
            print(f"  {cmd}: {info['desc']}")

    elif "--all" in sys.argv:
        print("[SENDING ALL PIPELINES]")
        for name in COMMANDS:
            print(f"  Running {name}...", end=" ", flush=True)
            msg = COMMANDS[name]["fn"]()
            if msg:
                send_telegram(msg)
                print("OK")
                time.sleep(1)
            else:
                print("(direct)")

    elif "--once" in sys.argv:
        msg = pipeline_status()
        send_telegram(msg)
        print("Status sent to Telegram")

    else:
        print("Usage: telegram_commander.py --cmd COMMAND | --list | --all | --once")
        print("\nCommands: " + ", ".join(COMMANDS.keys()))