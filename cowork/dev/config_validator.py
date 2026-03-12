#!/usr/bin/env python3
"""config_validator.py

Validateur de configuration JARVIS.
Vérifie les fichiers de config, bases de données, services et connectivité.

CLI :
    --once     : Validation complète unique
    --fix      : Tenter de corriger les problèmes détectés
    --report   : Rapport détaillé avec scores
"""

import argparse
from _paths import TURBO_DIR, ETOILE_DB, JARVIS_DB, TELEGRAM_TOKEN, TELEGRAM_CHAT
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any

# TELEGRAM_TOKEN loaded from _paths (.env)
TELEGRAM_CHAT_ID = TELEGRAM_CHAT

def telegram_send(msg: str):
    import urllib.parse, urllib.request
    try:
        data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": msg}).encode()
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)
    except Exception:
        pass

def run_cmd(cmd: list, timeout: int = 10) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=timeout).strip()
    except Exception:
        return ""

# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def check_databases() -> Dict[str, Any]:
    """Vérifie les bases SQLite JARVIS."""
    dbs = {
        "etoile.db": Path(str(ETOILE_DB)),
        "jarvis.db": Path(str(JARVIS_DB)),
        "trading_latest.db": TURBO_DIR / "projects/carV1_data/database/trading_latest.db",
    }
    issues = []
    ok = 0
    for name, path in dbs.items():
        if not path.is_file():
            issues.append(f"DB manquante: {name} ({path})")
            continue
        try:
            conn = sqlite3.connect(str(path))
            conn.execute("SELECT 1")
            # Check integrity
            result = conn.execute("PRAGMA integrity_check").fetchone()
            if result[0] != "ok":
                issues.append(f"DB corrompue: {name}")
            else:
                ok += 1
            conn.close()
        except Exception as e:
            issues.append(f"DB erreur {name}: {e}")

    score = int(100 * ok / len(dbs)) if dbs else 0
    return {"name": "databases", "score": score, "issues": issues, "details": f"{ok}/{len(dbs)} OK"}

def check_scripts() -> Dict[str, Any]:
    """Vérifie que tous les scripts du workspace sont valides."""
    dev_dir = Path(__file__).parent
    scripts = list(dev_dir.glob("*.py"))
    issues = []
    ok = 0
    for s in scripts:
        try:
            source = s.read_text(encoding="utf-8")
            compile(source, str(s), "exec")
            ok += 1
        except SyntaxError as e:
            issues.append(f"Syntax error: {s.name} L{e.lineno}")

    score = int(100 * ok / len(scripts)) if scripts else 0
    return {"name": "scripts", "score": score, "issues": issues, "details": f"{ok}/{len(scripts)} valides"}

def check_services() -> Dict[str, Any]:
    """Vérifie les services IA."""
    services = {
        "M1 (LMStudio)": ("curl", "-s", "--max-time", "3", "http://127.0.0.1:1234/api/v1/models"),
        "OL1 (Ollama)": ("curl", "-s", "--max-time", "3", "http://127.0.0.1:11434/api/tags"),
    }
    issues = []
    ok = 0
    for name, cmd in services.items():
        out = run_cmd(list(cmd))
        if out and ("data" in out or "models" in out):
            ok += 1
        else:
            issues.append(f"Service offline: {name}")

    score = int(100 * ok / len(services)) if services else 0
    return {"name": "services", "score": score, "issues": issues, "details": f"{ok}/{len(services)} online"}

def check_disk() -> Dict[str, Any]:
    """Vérifie l'espace disque."""
    import shutil
    issues = []
    drives = ["/\"]
    if os.path.isdir("F:/"):
        drives.append("F:/")

    ok = 0
    for d in drives:
        usage = shutil.disk_usage(d)
        free_gb = usage.free / (1024**3)
        free_pct = usage.free / usage.total * 100
        if free_pct < 10:
            issues.append(f"Espace critique {d}: {free_gb:.1f} GB ({free_pct:.1f}%)")
        elif free_pct < 20:
            issues.append(f"Espace faible {d}: {free_gb:.1f} GB ({free_pct:.1f}%)")
        else:
            ok += 1

    score = int(100 * ok / len(drives)) if drives else 0
    return {"name": "disk", "score": score, "issues": issues, "details": f"{ok}/{len(drives)} OK"}

def check_network() -> Dict[str, Any]:
    """Vérifie la connectivité réseau."""
    issues = []
    out = run_cmd(["ping", "-n", "2", "-w", "2000", "google.com"])
    if "TTL=" in out:
        score = 100
        details = "Internet OK"
    else:
        score = 0
        issues.append("Pas de connexion internet")
        details = "Internet KO"

    return {"name": "network", "score": score, "issues": issues, "details": details}

def check_telegram() -> Dict[str, Any]:
    """Vérifie la connectivité Telegram."""
    import urllib.request
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"
        resp = urllib.request.urlopen(url, timeout=5)
        data = json.loads(resp.read())
        if data.get("ok"):
            return {"name": "telegram", "score": 100, "issues": [], "details": f"Bot @{data['result']['username']}"}
    except Exception:
        pass
    return {"name": "telegram", "score": 0, "issues": ["Telegram bot inaccessible"], "details": "KO"}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def validate_all() -> List[Dict]:
    checks = [
        check_databases(),
        check_scripts(),
        check_services(),
        check_disk(),
        check_network(),
        check_telegram(),
    ]
    return checks

def display_results(checks: List[Dict]):
    total = sum(c["score"] for c in checks)
    avg = total / len(checks) if checks else 0

    if avg >= 90:
        grade = "A"
    elif avg >= 80:
        grade = "B"
    elif avg >= 70:
        grade = "C"
    elif avg >= 60:
        grade = "D"
    else:
        grade = "F"

    print(f"=== Config Validator JARVIS ===")
    print(f"Score global : {avg:.0f}/100 (Grade {grade})\n")

    for c in checks:
        icon = "✅" if c["score"] >= 80 else "⚠️" if c["score"] >= 50 else "❌"
        print(f"  {icon} {c['name']:12} : {c['score']:3}/100 — {c['details']}")
        for issue in c["issues"]:
            print(f"      ⚠️ {issue}")

    return avg, grade

def main():
    parser = argparse.ArgumentParser(description="Validateur de configuration JARVIS.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Validation complète")
    group.add_argument("--fix", action="store_true", help="Valider et corriger")
    group.add_argument("--report", action="store_true", help="Rapport détaillé")
    args = parser.parse_args()

    checks = validate_all()
    avg, grade = display_results(checks)

    if args.report or args.once:
        all_issues = sum(len(c["issues"]) for c in checks)
        telegram_send(f"🔧 Config Validator — Score {avg:.0f}/100 (Grade {grade}) | {all_issues} issue(s)")

    if args.fix:
        print("\n--- Auto-fix ---")
        for c in checks:
            if c["name"] == "services" and c["score"] < 100:
                print("  Tentative de restart Ollama...")
                run_cmd(["taskkill", "/F", "/IM", "ollama.exe"], timeout=5)
                run_cmd(["cmd", "/c", "start", "", "ollama", "serve"], timeout=5)
                print("  Ollama restart tenté.")

if __name__ == "__main__":
    main()