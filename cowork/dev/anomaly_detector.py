#!/usr/bin/env python3
"""anomaly_detector.py

Batch 6.1 – Détection d'anomalies système.

Fonctionnalités :
* Collecte des métriques :
  - CPU % (utilisation moyenne sur 1 s)
  - RAM % (utilisation totale)
  - Température GPU °C (nvidia‑smi, première carte trouvée)
  - Espace disque libre sur les volumes C: et F:
* Stockage des mesures dans une base SQLite `anomalies.db`.
* Détection d’anomalies :
  - Seuils statiques : CPU>90 %, RAM>85 %, GPU Temp>80 °C, disque libre <10 GB.
  - Déviation standard (z‑score) : |z|>2 pour chaque métrique (calculé sur l’historique stocké).
* Alertes :
  - Telegram (bot token `8369376863:AAF-7YGDbun8mXWwqYJFj‑eX6P78DeIu9Aw`, chat 2010747443)
  - Toast Windows via le script existant `win_notify.py` (appelé avec le texte).
* CLI :
  --once   : collecte unique + détection.
  --loop   : boucle toutes les 2 min (Ctrl‑C pour arrêter).
  --history : affiche l’historique des mesures (dernier jour).
"""

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# Ensure Unicode output works on Windows consoles (cp1252 cannot encode all chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"
DB_PATH = Path(__file__).with_name("anomalies.db")

THRESHOLDS = {
    "cpu": 90.0,
    "ram": 85.0,
    "gpu_temp": 80.0,
    "disk_c": 10.0,  # free GB
    "disk_f": 10.0,
}

# ---------------------------------------------------------------------------
# Helpers – collecte des métriques
# ---------------------------------------------------------------------------

def get_cpu_percent() -> float:
    """Retourne l'utilisation CPU en pourcentage (moyenne sur 1 s)."""
    try:
        # psutil est souvent présent sur les environnements OpenClaw
        import psutil
        return psutil.cpu_percent(interval=1.0)
    except Exception:
        # Fallback: PowerShell Get-Counter
        try:
            out = subprocess.check_output(
                ["powershell", "-Command", "(Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples[0].CookedValue"],
                text=True,
            )
            return float(out.strip())
        except Exception:
            return 0.0


def get_ram_percent() -> float:
    """Retourne l'utilisation RAM en pourcentage (physique)."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return mem.percent
    except Exception:
        try:
            out = subprocess.check_output(
                ["powershell", "-Command", "(Get-Counter '\\Memory\\% Committed Bytes In Use').CounterSamples[0].CookedValue"],
                text=True,
            )
            return float(out.strip())
        except Exception:
            return 0.0


def get_gpu_temperature() -> float:
    """Retourne la température du premier GPU (°C) via nvidia‑smi.
    Retourne 0.0 si aucune donnée disponible.
    """
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            text=True,
        )
        # La sortie peut contenir plusieurs lignes (plusieurs GPU) – on prend le premier
        line = out.strip().splitlines()[0]
        return float(line.strip())
    except Exception:
        return 0.0


def get_disk_free_gb(drive: str) -> float:
    """Retourne l'espace libre (GB) du volume indiqué (ex. "C:")."""
    try:
        total, used, free = shutil.disk_usage(drive)
        return free / (1024 ** 3)
    except Exception:
        return 0.0

# ---------------------------------------------------------------------------
# SQLite – persistence
# ---------------------------------------------------------------------------

def init_db(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS measures (
            ts TEXT PRIMARY KEY,
            cpu REAL,
            ram REAL,
            gpu_temp REAL,
            disk_c REAL,
            disk_f REAL
        )
        """
    )
    conn.commit()

def insert_measure(conn: sqlite3.Connection, ts: str, cpu: float, ram: float, gpu_temp: float, disk_c: float, disk_f: float):
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO measures (ts, cpu, ram, gpu_temp, disk_c, disk_f) VALUES (?,?,?,?,?,?)",
        (ts, cpu, ram, gpu_temp, disk_c, disk_f),
    )
    conn.commit()

def fetch_all(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT * FROM measures ORDER BY ts")
    return cur.fetchall()

# ---------------------------------------------------------------------------
# Analyse – détection d’anomalies
# ---------------------------------------------------------------------------

def compute_stats(rows):
    """Calcule moyenne et écart‑type pour chaque colonne numérique.
    Retourne dict {col: (mean, std)}.
    """
    import statistics
    cols = ["cpu", "ram", "gpu_temp", "disk_c", "disk_f"]
    stats = {}
    for idx, col in enumerate(cols, start=1):  # skip ts column
        values = [row[idx] for row in rows if row[idx] is not None]
        if len(values) < 2:
            stats[col] = (0.0, 0.0)
        else:
            mean = statistics.mean(values)
            std = statistics.stdev(values)
            stats[col] = (mean, std)
    return stats

def detect_anomaly(current, stats):
    """Renvoie une liste de messages d’anomalie détectés.
    `current` est dict contenant les mesures actuelles.
    `stats` provient de `compute_stats`.
    """
    alerts = []
    # Seuils statiques
    for key, limit in THRESHOLDS.items():
        value = current[key]
        if key.startswith("disk"):
            if value < limit:
                alerts.append(f"{key.upper()} free < {limit} GB (actuel {value:.1f} GB)")
        else:
            if value > limit:
                alerts.append(f"{key.upper()} > {limit}% (actuel {value:.1f}%)")
    # Z‑score
    for key, (mean, std) in stats.items():
        if std == 0:
            continue
        z = (current[key] - mean) / std
        if abs(z) > 2:
            alerts.append(f"{key.upper()} z‑score {z:.2f} (>2) – valeur {current[key]:.1f}")
    return alerts

# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def send_telegram(text: str):
    try:
        data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode()
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"[anomaly_detector] Erreur Telegram : {e}", file=sys.stderr)

def send_toast(message: str):
    # Supposons que win_notify.py accepte le texte en argument.
    script = Path(__file__).with_name("win_notify.py")
    if not script.is_file():
        return
    try:
        subprocess.Popen([sys.executable, str(script), message], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def collect_and_store(conn: sqlite3.Connection):
    ts = datetime.utcnow().isoformat()
    cpu = get_cpu_percent()
    ram = get_ram_percent()
    gpu_temp = get_gpu_temperature()
    disk_c = get_disk_free_gb("C:\\")
    disk_f = get_disk_free_gb("F:\\")
    insert_measure(conn, ts, cpu, ram, gpu_temp, disk_c, disk_f)
    return {
        "cpu": cpu,
        "ram": ram,
        "gpu_temp": gpu_temp,
        "disk_c": disk_c,
        "disk_f": disk_f,
        "ts": ts,
    }

def run_once():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    current = collect_and_store(conn)
    rows = fetch_all(conn)
    stats = compute_stats(rows)
    alerts = detect_anomaly(current, stats)
    if alerts:
        msg = "[ANOMALIE] " + ", ".join(alerts)
        print(msg)
        send_telegram(msg)
        send_toast(msg)
    else:
        print("[anomaly_detector] Aucun problème détecté.")
    conn.close()

def run_loop():
    print("[anomaly_detector] Démarrage en mode boucle (toutes les 2 min). Ctrl‑C pour arrêter.")
    try:
        while True:
            run_once()
            time.sleep(120)
    except KeyboardInterrupt:
        print("[anomaly_detector] Boucle interrompue par l'utilisateur.")

def show_history():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    rows = fetch_all(conn)
    # Affiche les 20 dernières entrées
    for row in rows[-20:]:
        ts, cpu, ram, gpu, dc, df = row
        print(f"{ts} | CPU {cpu:.1f}% | RAM {ram:.1f}% | GPU {gpu:.1f}°C | C:{dc:.1f}GB | F:{df:.1f}GB")
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Détection d'anomalies système.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Collecte unique + détection")
    group.add_argument("--loop", action="store_true", help="Boucle toutes les 2 min")
    group.add_argument("--history", action="store_true", help="Afficher l'historique (dernier jour)")
    args = parser.parse_args()

    if args.once:
        run_once()
    elif args.loop:
        run_loop()
    elif args.history:
        show_history()

if __name__ == "__main__":
    main()
