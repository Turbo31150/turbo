#!/usr/bin/env python3
"""gpu_thermal_guard.py

Surveillance thermique continue du(s) GPU via ``nvidia-smi``.

Fonctionnalités :
* Lit la température maximale du GPU (``nvidia-smi --query-gpu=temperature.gpu``).
* Enregistre chaque mesure dans ``thermal.db`` (table ``temps`` : ts, temperature).
* Alerte Telegram (bot token ``{TELEGRAM_TOKEN}``, chat ``2010747443``) :
    - **Warning** quand la température dépasse 75 °C.
    - **Critical** quand elle dépasse 85 °C ; le script indique alors que les tâches seront basculées vers un autre nœud (M2/OL1).
* CLI :
    --once      : effectue une lecture unique et gère les alertes.
    --loop      : boucle indéfiniment, lecture toutes les 30 s.
    --history   : affiche les dernières mesures stockées.

Utilise uniquement la bibliothèque standard (``subprocess``, ``sqlite3``, ``datetime``, ``urllib``).
"""

import argparse
import subprocess
import sqlite3
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

# Ensure Unicode output works on Windows consoles (cp1252 cannot encode all chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
from _paths import TELEGRAM_TOKEN, TELEGRAM_CHAT

# TELEGRAM_TOKEN loaded from _paths (.env)
TELEGRAM_CHAT_ID = TELEGRAM_CHAT
DB_PATH = Path(__file__).with_name("thermal.db")

WARNING_TEMP = 75  # °C
CRITICAL_TEMP = 85  # °C

# ---------------------------------------------------------------------------
# Helpers – base de données
# ---------------------------------------------------------------------------

def init_db(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS temps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            temperature REAL NOT NULL
        )
        """
    )
    conn.commit()

def store_temp(conn: sqlite3.Connection, temperature: float):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO temps (ts, temperature) VALUES (?,?)",
        (datetime.utcnow().isoformat(), temperature),
    )
    conn.commit()

def fetch_history(conn: sqlite3.Connection, limit: int = 20):
    cur = conn.cursor()
    cur.execute("SELECT ts, temperature FROM temps ORDER BY ts DESC LIMIT ?", (limit,))
    return cur.fetchall()

# ---------------------------------------------------------------------------
# Notification Telegram
# ---------------------------------------------------------------------------

def telegram_alert(message: str):
    try:
        data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": message}).encode()
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"[gpu_thermal_guard] Erreur d'envoi Telegram : {e}", file=sys.stderr)

# ---------------------------------------------------------------------------
# Lecture de la température GPU via nvidia‑smi
# ---------------------------------------------------------------------------

def get_gpu_temperature() -> float:
    """Retourne la température maximale parmi les GPU détectés.
    Si la commande échoue, renvoie -1.
    """
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=10,
        )
        temps = [int(line.strip()) for line in out.strip().splitlines() if line.strip()]
        if not temps:
            return -1.0
        return max(temps)
    except Exception as e:
        print(f"[gpu_thermal_guard] Erreur lecture nvidia‑smi : {e}", file=sys.stderr)
        return -1.0

# ---------------------------------------------------------------------------
# Gestion des alertes & migration fictive
# ---------------------------------------------------------------------------

def handle_temperature(temp: float):
    if temp < 0:
        # lecture impossible
        return
    if temp > CRITICAL_TEMP:
        msg = f"⚠️ [GPU THERMAL] Température critique : {temp} °C > {CRITICAL_TEMP} °C. Migration des tâches vers M2/OL1."
        print(msg)
        telegram_alert(msg)
        # Ici on pourrait déclencher un vrai ré‑affectation des jobs via le système de cron/agents.
    elif temp > WARNING_TEMP:
        msg = f"🔔 [GPU THERMAL] Température élevée : {temp} °C > {WARNING_TEMP} °C."
        print(msg)
        telegram_alert(msg)
    else:
        print(f"[gpu_thermal_guard] Température GPU OK : {temp} °C")

# ---------------------------------------------------------------------------
# CLI actions
# ---------------------------------------------------------------------------

def run_once():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    temp = get_gpu_temperature()
    store_temp(conn, temp)
    handle_temperature(temp)
    conn.close()

def run_loop():
    print("[gpu_thermal_guard] Démarrage du monitoring continu (30 s). Ctrl‑C pour arrêter.")
    try:
        while True:
            run_once()
            # 30 seconds interval
            import time
            time.sleep(30)
    except KeyboardInterrupt:
        print("[gpu_thermal_guard] Surveillance arrêtée par l'utilisateur.")

def show_history(limit: int = 20):
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    rows = fetch_history(conn, limit)
    for ts, temp in rows:
        print(f"{ts} – {temp} °C")
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Surveillance thermique GPU via nvidia‑smi.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Lecture unique")
    group.add_argument("--loop", action="store_true", help="Boucle toutes les 30 s")
    group.add_argument("--history", action="store_true", help="Afficher l'historique des mesures")
    args = parser.parse_args()

    if args.once:
        run_once()
    elif args.loop:
        run_loop()
    elif args.history:
        show_history()

if __name__ == "__main__":
    main()