#!/usr/bin/env python3
"""JARVIS Report Mailer — Envoi de rapports par email."""
import json, sys, os, subprocess
from datetime import datetime

MAIL_SCRIPT = "C:/Users/franc/.openclaw/workspace/jarvis_mail.py"
REPORT_DIR = "C:/Users/franc/.openclaw/workspace/dev/reports"
RECIPIENT = "franck"  # Alias in jarvis_mail.py

def get_latest_report():
    """Recupere le dernier rapport JSON."""
    if not os.path.exists(REPORT_DIR):
        return None
    reports = sorted([f for f in os.listdir(REPORT_DIR) if f.endswith(".json")])
    if not reports:
        return None
    path = os.path.join(REPORT_DIR, reports[-1])
    with open(path) as f:
        return json.load(f)

def format_report_email(report):
    """Formate le rapport en texte email."""
    lines = [f"JARVIS Daily Report — {datetime.now().strftime('%d/%m/%Y %H:%M')}"]
    lines.append("=" * 50)

    # Cluster
    cluster = report.get("cluster", {})
    online = sum(1 for v in cluster.values() if v.get("status") == "OK")
    lines.append(f"\nCLUSTER ({online}/{len(cluster)} online)")
    for name, data in cluster.items():
        lines.append(f"  {name}: {data.get('status', '?')} ({data.get('models', 0)} modeles)")

    # System
    sys_info = report.get("system", {})
    lines.append(f"\nSYSTEME")
    lines.append(f"  CPU: {sys_info.get('cpu_pct', '?')}%")
    lines.append(f"  RAM: {sys_info.get('ram_free_gb', '?')}GB libre / {sys_info.get('ram_total_gb', '?')}GB")
    disks = sys_info.get("disks", [])
    if not isinstance(disks, list): disks = [disks]
    for d in disks:
        lines.append(f"  Disque {d.get('Name', '?')}: {d.get('FreeGB', '?')}GB libre")

    # Trading
    trading = report.get("trading", [])
    if trading:
        lines.append(f"\nTRADING TOP 5")
        for t in trading[:5]:
            arrow = "+" if t.get("change", 0) > 0 else ""
            lines.append(f"  {t['symbol']}: ${t['price']} ({arrow}{t['change']}%)")

    lines.append(f"\n{'=' * 50}")
    lines.append("Genere automatiquement par JARVIS")
    return "\n".join(lines)

def send_report(recipient=RECIPIENT, subject=None):
    """Envoie le rapport par email via jarvis_mail.py."""
    report = get_latest_report()
    if not report:
        print("No report available. Run auto_reporter.py --once first.")
        return False

    body = format_report_email(report)
    if subject is None:
        subject = f"JARVIS Report {datetime.now().strftime('%d/%m/%Y')}"

    cmd = ["python", MAIL_SCRIPT, "send", "--to", recipient, "--subject", subject, "--body", body]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"Email sent to {recipient}: {subject}")
            return True
        else:
            print(f"Error: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"Failed: {e}")
        return False

def send_weekly_summary(recipient=RECIPIENT):
    """Resume hebdomadaire a partir des rapports disponibles."""
    if not os.path.exists(REPORT_DIR):
        print("No reports directory")
        return False

    reports = sorted([f for f in os.listdir(REPORT_DIR) if f.endswith(".json")])[-7:]
    if not reports:
        print("No reports available")
        return False

    lines = [f"JARVIS Weekly Summary — {datetime.now().strftime('%d/%m/%Y')}"]
    lines.append(f"Reports: {len(reports)} jours\n")

    for rf in reports:
        path = os.path.join(REPORT_DIR, rf)
        try:
            with open(path) as f:
                data = json.load(f)
            cluster = data.get("cluster", {})
            online = sum(1 for v in cluster.values() if v.get("status") == "OK")
            sys_info = data.get("system", {})
            lines.append(f"{rf[:15]}: {online} nodes | CPU {sys_info.get('cpu_pct', '?')}% | RAM {sys_info.get('ram_free_gb', '?')}GB free")
        except: pass

    body = "\n".join(lines)
    subject = f"JARVIS Weekly Summary {datetime.now().strftime('%d/%m/%Y')}"

    cmd = ["python", MAIL_SCRIPT, "send", "--to", recipient, "--subject", subject, "--body", body]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"Weekly summary sent to {recipient}")
            return True
        else:
            print(f"Error: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"Failed: {e}")
        return False

if __name__ == "__main__":
    if "--once" in sys.argv:
        send_report()
    elif "--weekly" in sys.argv:
        send_weekly_summary()
    elif "--test" in sys.argv:
        # Send a test email
        cmd = ["python", MAIL_SCRIPT, "send", "--to", RECIPIENT,
               "--subject", "JARVIS Test Email",
               "--body", f"Test email from JARVIS Report Mailer at {datetime.now().isoformat()}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        print("Test email:", "OK" if result.returncode == 0 else result.stderr[:200])
    elif "--preview" in sys.argv:
        report = get_latest_report()
        if report:
            print(format_report_email(report))
        else:
            print("No report available")
    else:
        print("Usage: report_mailer.py --once | --weekly | --test | --preview")
