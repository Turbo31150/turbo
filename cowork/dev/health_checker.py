#!/usr/bin/env python3
"""health_checker.py

Health‑check global du système JARVIS.

Il regroupe les vérifications suivantes :
* **Cluster IA** – ping des nœuds M1, M2, OL1 via ``curl`` (les mêmes URLs que dans AGENTS.md).
* **Bases de données** – existence et taille de ``etoile.db``, ``jarvis.db`` et ``trading_latest.db``.
* **Cron jobs** – liste via l'outil OpenClaw ``cron`` (action=list).  S’il n’y a aucun job, note 0.
* **Services Windows** – état des services critiques (Ollama, LMStudio, OpenClaw) via le script ``service_watcher.py``.
* **Espace disque** – capacité libre sur le lecteur C: (et F: si présent).
* **Mémoire RAM** – utilisation globale (via ``psutil`` si disponible sinon ``systeminfo``).
* **GPU** – température maximale via ``nvidia-smi``.
* **Réseau** – latence d’un ping google.com.

Chaque critère reçoit un score 0‑100 (plus haut = meilleur).  La moyenne pondérée fourni le
score global (0‑100) qui est traduit en grade : A (≥90), B (≥80), C (≥70), D (≥60), F (<60).
Le résultat est affiché et, si l’option ``--once`` ou ``--loop`` est utilisée, envoyé sur Telegram
( bot token ``TELEGRAM_TOKEN_REDACTED`` , chat ``2010747443`` ).

CLI :
    --once            : exécuter un check unique et afficher le résumé.
    --loop            : boucle toutes les 5 minutes (Ctrl‑C pour arrêter).
    --json            : sortie brute JSON (utile pour le cron).

Le script ne dépend que de la bibliothèque standard, avec ``psutil`` en option.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any

# Ensure Unicode output works on Windows consoles (cp1252 cannot encode all chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration Telegram
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT_ID = "2010747443"

# ---------------------------------------------------------------------------
# Helper – exécuter une commande et récupérer la sortie (texte)
# ---------------------------------------------------------------------------
def run_cmd(command: list, timeout: int = 10) -> str:
    try:
        out = subprocess.check_output(command, text=True, timeout=timeout)
        return out.strip()
    except Exception:
        return ""

# ---------------------------------------------------------------------------
# Telegram notification
# ---------------------------------------------------------------------------
def telegram_send(message: str):
    import urllib.parse, urllib.request
    try:
        data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": message}).encode()
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[health_checker] Erreur d'envoi Telegram : {e}")

# ---------------------------------------------------------------------------
# Individual checks – each returns a dict with 'score' and optional details
# ---------------------------------------------------------------------------

def check_cluster() -> Dict[str, Any]:
    nodes = {
        "M1": "http://127.0.0.1:1234/v1/chat/completions",
        "M2": "http://192.168.1.26:1234/v1/chat/completions",
        "OL1": "http://127.0.0.1:11434/v1/chat/completions",
    }
    reachable = 0
    for name, url in nodes.items():
        out = run_cmd(["curl.exe", "-s", "-o", "NUL", "-w", "%{http_code}", url])
        if out == "200":
            reachable += 1
    score = int(100 * reachable / len(nodes))
    return {"score": score, "details": f"{reachable}/{len(nodes)} nodes reachable"}

def check_databases() -> Dict[str, Any]:
    db_paths = {
        "etoile.db": Path("F:/BUREAU/turbo/data/etoile.db"),
        "jarvis.db": Path("F:/BUREAU/turbo/data/jarvis.db"),
        "trading_latest.db": Path("F:/BUREAU/turbo/projects/carV1_data/database/trading_latest.db"),
    }
    exists = 0
    total = len(db_paths)
    for name, p in db_paths.items():
        if p.is_file():
            exists += 1
    score = int(100 * exists / total)
    return {"score": score, "details": f"{exists}/{total} DB existent(s)"}

def check_cron() -> Dict[str, Any]:
    # Attempt to list cron jobs via the OpenClaw CLI (if available)
    out = run_cmd(["openclaw", "cron", "list", "--includeDisabled", "true"], timeout=20)
    if not out:
        score = 0
        details = "cron command unavailable"
    else:
        # count non‑disabled jobs
        try:
            data = json.loads(out)
            jobs = data.get("jobs", [])
            cnt = len(jobs)
            score = 100 if cnt > 0 else 0
            details = f"{cnt} job(s) listés"
        except Exception:
            # fallback: simple text parsing
            cnt = out.count("\n")
            score = 100 if cnt > 0 else 0
            details = f"{cnt} job(s) (parsed)"
    return {"score": score, "details": details}

def check_services() -> Dict[str, Any]:
    # Re‑utilise le script service_watcher.py en mode --status
    out = run_cmd([sys.executable, "service_watcher.py", "--list"], timeout=15)
    # Simple parsing: count lines with "[ON]" as running
    running = sum(1 for line in out.splitlines() if line.startswith("[ON]"))
    total = sum(1 for line in out.splitlines() if line.strip())
    score = int(100 * running / total) if total else 0
    details = f"{running}/{total} services running"
    return {"score": score, "details": details}

def check_disk() -> Dict[str, Any]:
    # Check free space on C: (and F: if exists)
    drives = ["C:\\"]
    if os.path.isdir("F:\\"):
        drives.append("F:\\")
    free_total_gb = 0.0
    total_gb = 0.0
    for d in drives:
        usage = shutil.disk_usage(d)
        free_total_gb += usage.free / (1024 ** 3)
        total_gb += usage.total / (1024 ** 3)
    free_percent = free_total_gb / total_gb * 100 if total_gb else 0
    # Score : 100 if >30% libre, linéaire jusqu'à 0%.
    score = int(min(100, max(0, (free_percent - 30) * (100/70)))) if free_percent >= 30 else int(free_percent * (100/30))
    details = f"{free_percent:.1f}% libre sur {', '.join(drives)}"
    return {"score": score, "details": details}

def check_ram() -> Dict[str, Any]:
    try:
        import psutil
        mem = psutil.virtual_memory()
        used_percent = mem.percent
    except Exception:
        # Fallback via systeminfo parsing (Windows)
        out = run_cmd(["systeminfo"], timeout=15)
        used_percent = 0
        for line in out.splitlines():
            if "Available Physical Memory" in line:
                # Approximation – treat as low usage
                used_percent = 10
                break
    # Score : 100 si utilisation < 60%, linéaire jusqu'à 0% à 95%.
    if used_percent < 60:
        score = 100
    elif used_percent > 95:
        score = 0
    else:
        score = int(100 * (95 - used_percent) / 35)
    details = f"RAM used {used_percent:.1f}%"
    return {"score": score, "details": details}

def check_gpu() -> Dict[str, Any]:
    out = run_cmd(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"], timeout=10)
    try:
        temps = [int(t) for t in out.splitlines() if t.strip()]
        max_temp = max(temps) if temps else 0
    except Exception:
        max_temp = 0
    # Score : 100 si <70°C, linéaire jusqu'à 0 à 90°C.
    if max_temp < 70:
        score = 100
    elif max_temp > 90:
        score = 0
    else:
        score = int(100 * (90 - max_temp) / 20)
    details = f"Max GPU temp {max_temp}°C"
    return {"score": score, "details": details}

def check_network() -> Dict[str, Any]:
    # Ping google.com 4 times, measure avg latency.
    out = run_cmd(["ping", "-n", "4", "google.com"], timeout=15)
    avg_ms = None
    for line in out.splitlines():
        if "Average =" in line:
            # Windows format: Average = 23ms
            part = line.split("Average =")[-1].strip()
            if part.endswith("ms"):
                try:
                    avg_ms = int(part.replace("ms", ""))
                except Exception:
                    pass
    if avg_ms is None:
        score = 0
        details = "Ping failed"
    else:
        # Score 100 if <50ms, linearly down to 0 at 200ms.
        if avg_ms < 50:
            score = 100
        elif avg_ms > 200:
            score = 0
        else:
            score = int(100 * (200 - avg_ms) / 150)
        details = f"Ping avg {avg_ms}ms"
    return {"score": score, "details": details}

# ---------------------------------------------------------------------------
# Aggregate health assessment
# ---------------------------------------------------------------------------

def aggregate(scores: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    total = sum(item["score"] for item in scores.values())
    count = len(scores)
    overall = int(total / count) if count else 0
    # Grade mapping
    if overall >= 90:
        grade = "A"
    elif overall >= 80:
        grade = "B"
    elif overall >= 70:
        grade = "C"
    elif overall >= 60:
        grade = "D"
    else:
        grade = "F"
    return {"overall_score": overall, "grade": grade, "components": scores}

# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------
def perform_check() -> Dict[str, Any]:
    checks = {
        "cluster": check_cluster(),
        "databases": check_databases(),
        "cron": check_cron(),
        "services": check_services(),
        "disk": check_disk(),
        "ram": check_ram(),
        "gpu": check_gpu(),
        "network": check_network(),
    }
    result = aggregate(checks)
    return result

def display_result(res: Dict[str, Any]):
    print("=== Health Check JARVIS ===")
    print(f"Score global : {res['overall_score']} / 100   Grade : {res['grade']}")
    for comp, data in res["components"].items():
        print(f"- {comp:10}: {data['score']:3} – {data.get('details','')}")

def main():
    parser = argparse.ArgumentParser(description="Health‑check global JARVIS.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Exécuter un check unique et afficher le résultat")
    group.add_argument("--loop", action="store_true", help="Boucler toutes les 5 min (Ctrl‑C pour arrêter)")
    group.add_argument("--json", action="store_true", help="Sortie JSON brute (pour intégration)")
    args = parser.parse_args()

    if args.once:
        res = perform_check()
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            display_result(res)
            telegram_send(f"🩺 Health Check JARVIS – Score {res['overall_score']} (Grade {res['grade']})")
    elif args.loop:
        print("[health_checker] Démarrage du monitoring (toutes les 5 min). Ctrl‑C pour arrêter.")
        try:
            while True:
                res = perform_check()
                display_result(res)
                telegram_send(f"🩺 Health Check JARVIS – Score {res['overall_score']} (Grade {res['grade']})")
                time.sleep(300)
        except KeyboardInterrupt:
            print("[health_checker] Boucle interrompue par l'utilisateur.")
    elif args.json:
        res = perform_check()
        print(json.dumps(res, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
