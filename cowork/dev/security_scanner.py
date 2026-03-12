#!/usr/bin/env python3
"""security_scanner.py

Batch 7.1 – Scanner de sécurité Windows.

Fonctionnalités :
* Vérifie :
  - Les ports TCP en écoute (via PowerShell Get‑NetTCPConnection).
  - Les services Windows en cours d’exécution (PowerShell Get‑Service).
  - La présence de fichiers sensibles (.env, credentials, .git‑config) dans le répertoire utilisateur.
  - L’état du pare‑feu Windows (Get‑NetFirewallProfile).
  - L’état de Windows Defender (Get‑MpComputerStatus).
* Stocke chaque résultat dans une base SQLite ``security.db`` avec les champs :
  ``id``, ``ts`` (timestamp UTC), ``category`` (ports, services, files, firewall, defender), ``result`` (texte brut).
* Envoie une alerte Telegram (bot token ``{TELEGRAM_TOKEN}``, chat ``2010747443``) si un risque est détecté :
  - Port d’accès à distance ouvert (3389), SMB (445) ou tout port > 1024 ouvert.
  - Services dangereux actifs (RemoteRegistry, Telnet, RDP, SMB).
  - Fichiers sensibles trouvés.
  - Pare‑feu désactivé ou Defender désactivé.
* CLI :
  --once      : exécute le scan complet et alerte si besoin.
  --ports     : n’affiche que les ports ouverts.
  --services  : n’affiche que les services actifs.
  --history   : montre les derniers scans (par catégorie).

Utilise uniquement la bibliothèque standard (subprocess, sqlite3, json, urllib, pathlib, datetime).
"""

import argparse
import json
import sqlite3
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from _paths import TELEGRAM_TOKEN, TELEGRAM_CHAT

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
# TELEGRAM_TOKEN loaded from _paths (.env)
TELEGRAM_CHAT_ID = TELEGRAM_CHAT
DB_PATH = Path(__file__).with_name("security.db")
USER_HOME = Path.home()

# ------------------------------------------------------------
# Helpers – stockage SQLite
# ------------------------------------------------------------

def init_db(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            category TEXT NOT NULL,
            result TEXT NOT NULL
        )
        """
    )
    conn.commit()

def store_scan(conn: sqlite3.Connection, category: str, result: str):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO scans (ts, category, result) VALUES (?,?,?)",
        (datetime.utcnow().isoformat(), category, result),
    )
    conn.commit()

def fetch_recent(conn: sqlite3.Connection, limit: int = 20):
    cur = conn.cursor()
    cur.execute("SELECT ts, category, result FROM scans ORDER BY ts DESC LIMIT ?", (limit,))
    return cur.fetchall()

# ------------------------------------------------------------
# Notification Telegram
# ------------------------------------------------------------

def telegram_alert(message: str):
    try:
        data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": message}).encode()
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"[security_scanner] Erreur d'envoi Telegram : {e}", file=sys.stderr)

# ------------------------------------------------------------
# Scans individuels
# ------------------------------------------------------------

def run_ps(command: str) -> str:
    """Execute une commande PowerShell et retourne la sortie texte (utf‑8)."""
    try:
        completed = subprocess.run([
            "powershell", "-NoProfile", "-Command", command
        ], capture_output=True, text=True, timeout=30)
        return completed.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def scan_ports() -> str:
    cmd = "Get-NetTCPConnection -State Listen | Select-Object -Property LocalPort, OwningProcess | Format-Table -AutoSize"
    return run_ps(cmd)

def scan_services() -> str:
    cmd = "Get-Service | Where-Object {$_.Status -eq 'Running'} | Select-Object -Property Name, Status | Format-Table -AutoSize"
    return run_ps(cmd)

def scan_sensitive_files() -> str:
    patterns = ["*.env", "*credentials*", "*.pem", "*.key", "*.crt", "*.config", "*.json"]
    matches = []
    for pattern in patterns:
        for p in USER_HOME.rglob(pattern):
            matches.append(str(p))
    if not matches:
        return "Aucun fichier sensible trouvé."
    return "Fichiers sensibles :\n" + "\n".join(matches)

def scan_firewall() -> str:
    cmd = "Get-NetFirewallProfile | Select-Object -Property Name, Enabled | Format-Table -AutoSize"
    return run_ps(cmd)

def scan_defender() -> str:
    cmd = "Get-MpComputerStatus | Select-Object -Property AntivirusEnabled, RealTimeProtectionEnabled, AntivirusSignatureLastUpdated | Format-List"
    return run_ps(cmd)

# ------------------------------------------------------------
# Analyse des risques
# ------------------------------------------------------------

def detect_risks(port_output: str, service_output: str, file_output: str, firewall_output: str, defender_output: str) -> list:
    alerts = []
    # Ports à risque – on regarde les numéros dans le texte
    risky_ports = {"3389", "445"}
    for line in port_output.splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        # Le premier champ devrait être le port
        if parts[0].isdigit():
            port = parts[0]
            if port in risky_ports or int(port) > 1024:
                alerts.append(f"Port à risque ouvert : {port}")
    # Services à risque
    risky_services = {"RemoteRegistry", "Telnet", "RemoteDesktop", "SMB", "RDP"}
    for line in service_output.splitlines():
        for svc in risky_services:
            if svc.lower() in line.lower():
                alerts.append(f"Service potentiellement dangereux actif : {svc}")
    # Fichiers sensibles
    if "Fichiers sensibles" in file_output:
        alerts.append("Fichiers sensibles détectés dans le répertoire utilisateur")
    # Pare‑feu désactivé ?
    if "Enabled : False" in firewall_output or "Enabled : 0" in firewall_output:
        alerts.append("Pare‑feu Windows désactivé.")
    # Defender désactivé ?
    if "AntivirusEnabled : False" in defender_output or "RealTimeProtectionEnabled : False" in defender_output:
        alerts.append("Windows Defender désactivé ou protection en temps réel désactivée.")
    return alerts

# ------------------------------------------------------------
# CLI actions
# ------------------------------------------------------------

def run_once():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    # Execute scans
    ports = scan_ports()
    services = scan_services()
    files = scan_sensitive_files()
    firewall = scan_firewall()
    defender = scan_defender()
    # Store results
    store_scan(conn, "ports", ports)
    store_scan(conn, "services", services)
    store_scan(conn, "files", files)
    store_scan(conn, "firewall", firewall)
    store_scan(conn, "defender", defender)
    # Analyse des risques
    alerts = detect_risks(ports, services, files, firewall, defender)
    if alerts:
        msg = "[SECURITY ALERT] " + ", ".join(alerts)
        print(msg)
        telegram_alert(msg)
    else:
        print("[security_scanner] Aucun risque détecté.")
    conn.close()

def show_ports():
    print(scan_ports())

def show_services():
    print(scan_services())

def show_history(limit: int = 20):
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    rows = fetch_recent(conn, limit)
    for ts, cat, res in rows:
        print(f"--- {ts} | {cat} ---")
        print(res)
        print("\n")
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Scanner de sécurité Windows.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Exécuter le scan complet et alerter si risque")
    group.add_argument("--ports", action="store_true", help="Afficher uniquement les ports ouverts")
    group.add_argument("--services", action="store_true", help="Afficher les services actifs")
    group.add_argument("--history", action="store_true", help="Afficher l'historique des scans")
    args = parser.parse_args()

    if args.once:
        run_once()
    elif args.ports:
        show_ports()
    elif args.services:
        show_services()
    elif args.history:
        show_history()

if __name__ == "__main__":
    main()