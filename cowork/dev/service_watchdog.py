#!/usr/bin/env python3
"""service_watchdog.py — Surveille les services Windows critiques et les redémarre.

Usage examples:
  python dev/service_watchdog.py --once
  python dev/service_watchdog.py --loop
  python dev/service_watchdog.py --status
  python dev/service_watchdog.py --restart Ollama
"""
import argparse
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime

# Configuration
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "watchdog.db")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Services to monitor
# For Windows services we use the service name as seen by Get-Service.
WINDOWS_SERVICES = [
    "LMStudio",   # assumed service name – may need adjustment
    "Ollama",
    "OpenClawGateway",
    "n8n",
]
# FastAPI service is identified by listening TCP port 9742
FASTAPI_PORT = 9742

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS watchdog (
            service TEXT PRIMARY KEY,
            status TEXT,
            last_up TEXT,
            restart_count INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()

def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        subprocess.run([
            "curl.exe", "-s", "-X", "POST", url,
            "-d", f"chat_id={TELEGRAM_CHAT_ID}&text={message}&parse_mode=HTML"
        ], check=False)
    except Exception:
        pass

def get_windows_service_status(name: str) -> str:
    try:
        result = subprocess.run([
            "powershell", "-Command",
            f"(Get-Service -Name '{name}').Status"
        ], capture_output=True, text=True, timeout=10)
        status = result.stdout.strip()
        return status if status else "Unknown"
    except Exception:
        return "Error"

def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except Exception:
            return False

def check_service(name: str):
    if name in WINDOWS_SERVICES:
        status = get_windows_service_status(name)
    elif name == "FastAPI":
        status = "Running" if is_port_open(FASTAPI_PORT) else "Stopped"
    else:
        status = "Unknown"
    return status

def update_db(service: str, status: str, restarted: bool = False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("SELECT status FROM watchdog WHERE service = ?", (service,))
    row = c.fetchone()
    if row:
        restart_count = 0
        if restarted:
            c.execute(
                "UPDATE watchdog SET status = ?, last_up = ?, restart_count = restart_count + 1 WHERE service = ?",
                (status, now, service),
            )
        else:
            c.execute(
                "UPDATE watchdog SET status = ?, last_up = ? WHERE service = ?",
                (status, now, service),
            )
    else:
        restart_count = 1 if restarted else 0
        c.execute(
            "INSERT INTO watchdog (service, status, last_up, restart_count) VALUES (?,?,?,?)",
            (service, status, now, restart_count),
        )
    conn.commit()
    conn.close()

def restart_service(name: str) -> bool:
    try:
        subprocess.run([
            "powershell", "-Command",
            f"Restart-Service -Name '{name}' -Force"
        ], check=True, timeout=30)
        send_telegram(f"✅ Service <b>{name}</b> redémarré avec succès.")
        return True
    except Exception as e:
        send_telegram(f"❌ Échec du redémarrage du service <b>{name}</b>: {e}")
        return False

def monitor_once():
    results = []
    services_to_check = WINDOWS_SERVICES + ["FastAPI"]
    for svc in services_to_check:
        status = check_service(svc)
        restarted = False
        if status not in ("Running", "Started", "Running"):
            # attempt restart for Windows services only
            if svc in WINDOWS_SERVICES:
                success = restart_service(svc)
                restarted = success
                status = "Running" if success else "Stopped"
        update_db(svc, status, restarted)
        results.append({"service": svc, "status": status, "restarted": restarted})
    print(json.dumps(results, ensure_ascii=False, indent=2))

def show_status():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT service, status, last_up, restart_count FROM watchdog")
    rows = c.fetchall()
    conn.close()
    data = [
        {"service": r[0], "status": r[1], "last_up": r[2], "restart_count": r[3]}
        for r in rows
    ]
    print(json.dumps(data, ensure_ascii=False, indent=2))

def main():
    parser = argparse.ArgumentParser(description="Surveille et redémarre les services critiques.")
    parser.add_argument("--once", action="store_true", help="Exécuter une vérification unique")
    parser.add_argument("--loop", action="store_true", help="Boucle de surveillance continuelle (intervalle 60s)")
    parser.add_argument("--status", action="store_true", help="Afficher l'état actuel depuis la base SQLite")
    parser.add_argument("--restart", metavar="SERVICE", help="Redémarrer immédiatement le service indiqué")
    args = parser.parse_args()

    init_db()

    if args.restart:
        name = args.restart
        if name not in WINDOWS_SERVICES and name != "FastAPI":
            print(f"Service inconnu: {name}", file=sys.stderr)
            sys.exit(1)
        if name == "FastAPI":
            # FastAPI n'est pas un service Windows, on tente de tuer le processus qui écoute le port
            # Utilisation de powershell pour récupérer le PID
            try:
                pid_res = subprocess.run([
                    "powershell", "-Command",
                    f"(Get-NetTCPConnection -LocalPort {FASTAPI_PORT} -State Listen).OwningProcess"
                ], capture_output=True, text=True, timeout=5)
                pid = pid_res.stdout.strip()
                if pid:
                    subprocess.run(["powershell", "-Command", f"Stop-Process -Id {pid} -Force"], check=True)
                    time.sleep(2)
                    # relance éventuelle via le script fastapi si connu – ici on suppose que le service est déjà configuré pour redémarrer automatiquement.
                    print(f"FastAPI process {pid} arrêté.")
                else:
                    print("FastAPI n'est pas en écoute.")
            except Exception as e:
                print(f"Erreur lors du redémarrage de FastAPI: {e}")
        else:
            success = restart_service(name)
            print(f"Redémarrage {'réussi' if success else 'échoué'}: {name}")
        return

    if args.status:
        show_status()
        return

    if args.once:
        monitor_once()
        return

    if args.loop:
        try:
            while True:
                monitor_once()
                time.sleep(60)
        except KeyboardInterrupt:
            pass
        return

    # Aucun argument = afficher l'aide
    parser.print_help()

if __name__ == "__main__":
    main()
