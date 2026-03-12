#!/usr/bin/env python3
"""alert_manager.py

Gestion d'alertes système configurables via un fichier JSON.

Fonctionnalités principales :
- Chargement des règles depuis `config.json` (exemple de seuils : cpu>90, disk<10GB, gpu>80).
- Vérification des indicateurs système (CPU, espace disque disponible, utilisation GPU).
- Enregistrement des alertes dans une base SQLite locale (`alerts.db`).
- Envoi de notifications Telegram (BOT_TOKEN et CHAT_ID attendus dans les variables d'environnement).
- Interface en ligne de commande avec les options :
    --rules            : afficher les règles actuelles
    --add RULE_JSON    : ajouter ou mettre à jour une règle (ex. '{"cpu":90,"disk":10,"gpu":80}')
    --trigger          : déclencher la vérification et les alertes
    --history [N]     : afficher les N dernières alertes (défaut 10)
    -h/--help          : afficher l'aide

Aucune dépendance externe – uniquement la bibliothèque standard.
"""

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
import urllib.parse
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("config.json")
DB_PATH = Path(__file__).with_name("alerts.db")

# ---------------------------------------------------------------------------
# Gestion du fichier de configuration JSON
# ---------------------------------------------------------------------------

def load_config():
    """Charge les règles depuis le fichier JSON.
    Retourne un dict avec les seuils. Si le fichier n'existe pas, crée une configuration vide.
    """
    if not CONFIG_PATH.is_file():
        # configuration par défaut vide
        default = {"cpu": 90, "disk": 10, "gpu": 80}
        save_config(default)
        return default
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            print("[alert_manager] Erreur de décodage du fichier de configuration.")
            sys.exit(1)


def save_config(config):
    """Enregistre le dict de configuration au format JSON indénté."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

# ---------------------------------------------------------------------------
# Accès SQLite
# ---------------------------------------------------------------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL NOT NULL,
            threshold REAL NOT NULL,
            condition TEXT NOT NULL,
            message TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def log_alert(metric, value, threshold, condition, message):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO alerts (ts, metric, value, threshold, condition, message) VALUES (?,?,?,?,?,?)",
        (datetime.utcnow().isoformat(), metric, value, threshold, condition, message),
    )
    conn.commit()
    conn.close()


def fetch_history(limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT ts, metric, value, threshold, condition, message FROM alerts ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

# ---------------------------------------------------------------------------
# Métriques système (STD LIB)
# ---------------------------------------------------------------------------

def get_cpu_usage():
    """Renvoie l'utilisation CPU en pourcentage (0‑100).
    Utilise `wmic` sur Windows, sinon `os.getloadavg` comme fallback.
    """
    try:
        # Windows – wmic retourne un entier
        result = subprocess.check_output([
            "wmic",
            "cpu",
            "get",
            "loadpercentage",
            "/format:list",
        ], shell=True, text=True)
        for line in result.splitlines():
            if line.strip().startswith("LoadPercentage"):
                _, val = line.split('=')
                return float(val.strip())
    except Exception:
        pass
    # Fallback Unix‑like
    try:
        load1, _, _ = os.getloadavg()
        # Approximation : charge 1 minute / nombre de CPU * 100
        cpu_count = os.cpu_count() or 1
        return (load1 / cpu_count) * 100.0
    except Exception:
        return 0.0


def get_disk_free_gb():
    """Espace disque libre (GB) sur la partition système."""
    usage = shutil.disk_usage(Path.cwd())
    free_gb = usage.free / (1024 ** 3)
    return free_gb


def get_gpu_usage():
    """Utilisation GPU en pourcentage (0‑100).
    Recherche `nvidia-smi` si disponible, sinon retourne 0.
    """
    try:
        output = subprocess.check_output(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"], text=True)
        # Peut retourner plusieurs lignes si plusieurs GPU – on prend le max
        values = [float(v.strip()) for v in output.strip().split('\n') if v.strip()]
        return max(values) if values else 0.0
    except Exception:
        return 0.0

# ---------------------------------------------------------------------------
# Notification Telegram (STD LIB via urllib)
# ---------------------------------------------------------------------------

def send_telegram(message: str):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        print("[alert_manager] Variables d'environnement TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquantes.")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": message, "parse_mode": "HTML"}).encode()
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()  # on ignore la réponse
    except Exception as e:
        print(f"[alert_manager] Échec d'envoi Telegram: {e}")

# ---------------------------------------------------------------------------
# Vérification des règles et déclenchement des alertes
# ---------------------------------------------------------------------------

def check_and_alert():
    cfg = load_config()
    alerts = []
    # CPU > seuil
    cpu = get_cpu_usage()
    if "cpu" in cfg and cpu > cfg["cpu"]:
        msg = f"⚠️ CPU à {cpu:.1f}% (seuil {cfg['cpu']}%)"
        alerts.append(("cpu", cpu, cfg["cpu"], ">", msg))
    # Disk < seuil (GB)
    disk = get_disk_free_gb()
    if "disk" in cfg and disk < cfg["disk"]:
        msg = f"⚠️ Espace disque disponible {disk:.1f} GB (seuil {cfg['disk']} GB)"
        alerts.append(("disk", disk, cfg["disk"], "<", msg))
    # GPU > seuil
    gpu = get_gpu_usage()
    if "gpu" in cfg and gpu > cfg["gpu"]:
        msg = f"⚠️ GPU à {gpu:.1f}% (seuil {cfg['gpu']}%)"
        alerts.append(("gpu", gpu, cfg["gpu"], ">", msg))
    # Enregistrement et notif
    for metric, value, thresh, cond, message in alerts:
        log_alert(metric, value, thresh, cond, message)
        send_telegram(message)
    if not alerts:
        print("[alert_manager] Aucun dépassement de seuil détecté.")

# ---------------------------------------------------------------------------
# Interface ligne de commande
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Gestionnaire d'alertes système.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--rules", action="store_true", help="Afficher les règles actuelles.")
    group.add_argument("--add", metavar="RULE_JSON", help='Ajouter ou mettre a jour des regles (JSON). Exemple: \'{"cpu":90,"disk":10,"gpu":80}\'.')
    group.add_argument("--trigger", action="store_true", help="Vérifier les indicateurs et déclencher les alertes.")
    group.add_argument("--history", nargs="?", const=10, type=int, help="Afficher les N dernières alertes (défaut 10).")

    args = parser.parse_args()

    init_db()

    if args.rules:
        cfg = load_config()
        print(json.dumps(cfg, indent=4, ensure_ascii=False))
    elif args.add:
        try:
            new_rules = json.loads(args.add)
            if not isinstance(new_rules, dict):
                raise ValueError
            cfg = load_config()
            cfg.update(new_rules)
            save_config(cfg)
            print("[alert_manager] Règles mises à jour :")
            print(json.dumps(cfg, indent=4, ensure_ascii=False))
        except Exception:
            print("[alert_manager] JSON de règles invalide.")
            sys.exit(1)
    elif args.trigger:
        check_and_alert()
    elif args.history is not None:
        rows = fetch_history(args.history)
        for ts, metric, value, thresh, cond, message in rows:
            print(f"{ts} | {metric.upper():4} | {value:.2f} (seuil {thresh}{cond}) -> {message}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
