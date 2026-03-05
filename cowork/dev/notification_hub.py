#!/usr/bin/env python3
"""notification_hub.py

Hub centralisé de notifications pour les scripts COWORK.

Fonctionnalités :
* **Mode serveur** (`--server`) : écoute TCP sur le port 9999, accepte des messages JSON
  contenant :
      {"level": "critical|warning|info", "source": "nom_du_script", "message": "texte"}
  Le serveur déduplique les alertes (hash basé sur source+message) et conserve les
  200 dernières pour éviter les répétitions.
* **Priorisation** : les niveaux sont simplement conservés, mais les alertes
  critiques sont marquées comme telles dans les envois.
* **Envoi** : chaque alerte (nouvelle) est transmise :
  - via Telegram (bot token `TELEGRAM_TOKEN_REDACTED`, chat `2010747443`).
  - via un toast Windows en appelant le script existant ``win_notify.py`` (si présent).
* **Mode client** (`--send level source "message"`) : ouvre une connexion TCP au
  hub (localhost :9999) et transmet le JSON.

Le script utilise uniquement la bibliothèque standard : ``socket``, ``json``,
``threading``, ``hashlib``, ``collections`` et ``subprocess``.
"""

import argparse
import collections
import hashlib
import json
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 9999
TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT_ID = "2010747443"
MAX_DEDUP = 200  # keep last N hashes for deduplication

# ---------------------------------------------------------------------------
# Déduplication (LRU)
# ---------------------------------------------------------------------------
recent_hashes = collections.deque(maxlen=MAX_DEDUP)
lock = threading.Lock()

def _hash_alert(alert: dict) -> str:
    # Combine source+message+level
    s = f"{alert.get('source','')}-{alert.get('level','')}-{alert.get('message','')}"
    return hashlib.sha256(s.encode()).hexdigest()

# ---------------------------------------------------------------------------
# Envoi Telegram (reuse from other scripts)
# ---------------------------------------------------------------------------
def telegram_send(text: str):
    try:
        data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode()
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"[notification_hub] Erreur Telegram : {e}", file=sys.stderr)

# ---------------------------------------------------------------------------
# Toast Windows via win_notify.py (if present)
# ---------------------------------------------------------------------------
def windows_toast(message: str):
    script = Path(__file__).with_name("win_notify.py")
    if not script.is_file():
        return
    try:
        subprocess.Popen([sys.executable, str(script), message],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Traitement d'une alerte reçue
# ---------------------------------------------------------------------------
def handle_alert(alert: dict):
    # Basic validation
    level = alert.get("level", "info").lower()
    source = alert.get("source", "unknown")
    message = alert.get("message", "")
    if not message:
        return
    # Deduplication
    h = _hash_alert(alert)
    with lock:
        if h in recent_hashes:
            return  # duplicate, ignore
        recent_hashes.append(h)
    # Build a unified text for both channels
    prefix = {
        "critical": "⚠️ *CRITICAL*",
        "warning": "🔔 *WARNING*",
        "info": "ℹ️ *INFO*",
    }.get(level, "ℹ️ *INFO*")
    full_msg = f"{prefix} [{source}] {message}"
    # Send via Telegram and Windows toast
    telegram_send(full_msg)
    windows_toast(full_msg)

# ---------------------------------------------------------------------------
# Server (thread per connection)
# ---------------------------------------------------------------------------
def client_thread(conn: socket.socket, addr):
    try:
        data = conn.recv(4096)
        if not data:
            return
        try:
            alert = json.loads(data.decode())
            handle_alert(alert)
        except json.JSONDecodeError:
            print(f"[notification_hub] JSON invalide reçu de {addr}")
    finally:
        conn.close()

def run_server():
    print(f"[notification_hub] Démarrage du serveur sur {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        while True:
            try:
                conn, addr = s.accept()
                threading.Thread(target=client_thread, args=(conn, addr), daemon=True).start()
            except KeyboardInterrupt:
                print("[notification_hub] Arrêt du serveur demandé.")
                break
            except Exception as e:
                print(f"[notification_hub] Erreur serveur : {e}")
                continue

# ---------------------------------------------------------------------------
# Client helper – envoie d'une alerte au hub
# ---------------------------------------------------------------------------
def send_alert(level: str, source: str, message: str):
    payload = json.dumps({"level": level.lower(), "source": source, "message": message})
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((HOST, PORT))
            s.sendall(payload.encode())
            # No response expected
        except ConnectionRefusedError:
            print("[notification_hub] Impossible de joindre le serveur (connexion refusée).", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"[notification_hub] Erreur d'envoi : {e}", file=sys.stderr)
            sys.exit(1)

# ---------------------------------------------------------------------------
# CLI handling
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Hub centralisé de notifications.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--server", action="store_true", help="Lancer le serveur de réception d'alertes")
    group.add_argument("--send", nargs=3, metavar=("LEVEL", "SOURCE", "MESSAGE"),
                       help="Envoyer une alerte au hub (client). Exemple : --send warning myscript \"Quelque chose\"")
    args = parser.parse_args()

    if args.server:
        run_server()
    else:
        level, source, message = args.send
        send_alert(level, source, message)

if __name__ == "__main__":
    main()
