#!/usr/bin/env python3
"""auto_healer.py

Batch 4.1: Agent d'auto‑réparation du cluster.
Vérifie les nœuds M1, M2, OL1 ; si un nœud est hors‑ligne, le relance.

* M1  : http://127.0.0.1:1234
* M2  : http://192.168.1.26:1234
* OL1 : http://127.0.0.1:11434 (ollama)

Redémarrage :
- OL1 : `ollama serve`
- LM Studio (local) : `lms.exe`

Alertes Telegram via bot token 8369376863:AAF-7YGDbun8mXWwqYJFj‑eX6P78DeIu9Aw, chat_id 2010747443.

Usage :
    auto_healer.py --once      # vérifie et répare une fois
    auto_healer.py --loop      # boucle toutes les 5 min
"""

import argparse
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request

# Ensure Unicode output works on Windows consoles (cp1252 cannot encode all chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"

NODES = {
    "M1": {"host": "127.0.0.1", "port": 1234, "restart_cmd": None},
    "M2": {"host": "192.168.1.26", "port": 1234, "restart_cmd": None},
    "OL1": {"host": "127.0.0.1", "port": 11434, "restart_cmd": ["ollama", "serve"]},
    "LMStudio": {"host": "127.0.0.1", "port": 1234, "restart_cmd": ["lms.exe"]},
}

def send_telegram(msg: str) -> None:
    """Envoie un message texte via l'API Bot Telegram."""
    try:
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
        }).encode()
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()  # on ignore le contenu
    except Exception as e:
        print(f"[auto_healer] Erreur d'envoi Telegram: {e}", file=sys.stderr)

def is_node_up(host: str, port: int, timeout: float = 2.0) -> bool:
    """Teste la connectivité TCP du nœud."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

def restart_node(name: str, cmd: list) -> bool:
    """Lance la commande de redémarrage du nœud.
    Retourne True si le processus démarre sans lever d'exception.
    """
    if not cmd:
        return False
    try:
        # Utilise subprocess.Popen afin que le processus reste en arrière‑plan.
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
        return True
    except Exception as e:
        print(f"[auto_healer] Erreur lors du redémarrage de {name}: {e}", file=sys.stderr)
        return False

def check_and_heal() -> None:
    for name, cfg in NODES.items():
        up = is_node_up(cfg["host"], cfg["port"])
        if up:
            print(f"[auto_healer] {name} OK ({cfg['host']}:{cfg['port']})")
            continue
        # Node down
        print(f"[auto_healer] {name} DOWN – tentative de redémarrage...")
        restarted = False
        if cfg.get("restart_cmd"):
            restarted = restart_node(name, cfg["restart_cmd"]) 
        if restarted:
            msg = f"🔧 {name} était hors ligne, redémarrage lancé avec succès."
        else:
            msg = f"⚠️ {name} était hors ligne, impossible de le redémarrer automatiquement."
        send_telegram(msg)
        # Petit délai avant de re‑vérifier le node
        time.sleep(3)
        # Re‑vérifie une fois
        if is_node_up(cfg["host"], cfg["port"]):
            send_telegram(f"✅ {name} est maintenant en ligne.")
        else:
            send_telegram(f"❌ {name} reste indisponible après redémarrage.")

def main():
    parser = argparse.ArgumentParser(description="Auto‑healer du cluster IA.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Vérifier et réparer une fois.")
    group.add_argument("--loop", action="store_true", help="Boucler toutes les 5 min.")
    args = parser.parse_args()

    if args.once:
        check_and_heal()
    else:
        print("[auto_healer] Démarrage en boucle (5 min). Ctrl‑C pour arrêter.")
        try:
            while True:
                check_and_heal()
                time.sleep(300)  # 5 minutes
        except KeyboardInterrupt:
            print("[auto_healer] Arrêt du mode boucle.")

if __name__ == "__main__":
    main()
