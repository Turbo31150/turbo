#!/usr/bin/env python3
"""wifi_manager.py

Gestionnaire Wi‑Fi pour Windows (via ``netsh wlan``).

Fonctionnalités :
* ``--status`` : affiche le réseau actuellement connecté (SSID, état, force du signal).
* ``--scan`` : liste les réseaux sans fil détectés – SSID, type, signal, sécurité.
* ``--disconnect`` : déconnecte le client Wi‑Fi du réseau actif.
* ``--connect SSID`` : se connecte au réseau indiqué (le profil doit déjà exister ; sinon le script
de tente de le créer avec une requête de type ``netsh wlan connect name="SSID"``).

Le script utilise uniquement la bibliothèque standard : ``subprocess`` pour exécuter les commandes
``netsh wlan show interfaces``, ``netsh wlan show networks mode=bssid`` etc.
"""

import argparse
import json
import subprocess
import sys
from typing import List, Dict, Optional

# ---------------------------------------------------------------------------
# Helpers – exécution de netsh et parsing simplifié
# ---------------------------------------------------------------------------

def run_netsh(args: List[str]) -> str:
    """Execute ``netsh`` avec les arguments fournis et retourne la sortie décodée.
    En cas d’erreur, renvoie une chaîne vide et affiche le problème sur stderr.
    """
    try:
        result = subprocess.check_output(["netsh"] + args, text=True, timeout=15)
        return result.strip()
    except subprocess.CalledProcessError as e:
        print(f"[wifi_manager] netsh error: {e}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"[wifi_manager] Unexpected error: {e}", file=sys.stderr)
        return ""

# ---------------------------------------------------------------------------
# Parsing helpers – we keep it simple, extracting lines we need.
# ---------------------------------------------------------------------------

def parse_interface_info(output: str) -> Dict[str, str]:
    info = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, val = [part.strip() for part in line.split(":", 1)]
        info[key] = val
    return info

def parse_networks(output: str) -> List[Dict[str, str]]:
    networks = []
    current: Dict[str, str] = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        if line.lstrip().startswith("SSID "):
            # New network block – store previous if any
            if current:
                networks.append(current)
                current = {}
            # Example: "SSID 1 : MyNetwork"
            parts = line.split(":", 1)
            if len(parts) == 2:
                current["SSID"] = parts[1].strip()
        elif ":" in line:
            k, v = [p.strip() for p in line.split(":", 1)]
            current[k] = v
    if current:
        networks.append(current)
    return networks

# ---------------------------------------------------------------------------
# CLI actions
# ---------------------------------------------------------------------------

def show_status():
    out = run_netsh(["wlan", "show", "interfaces"])
    if not out:
        print("[wifi_manager] Aucun résultat – l'interface Wi‑Fi est peut‑être désactivée.")
        return
    info = parse_interface_info(out)
    ssid = info.get("SSID", "(non connecté)")
    state = info.get("State", "unknown")
    signal = info.get("Signal", "N/A")
    print(f"État : {state}")
    print(f"SSID  : {ssid}")
    print(f"Signal: {signal}")

def scan_networks():
    out = run_netsh(["wlan", "show", "networks", "mode=bssid"])
    if not out:
        print("[wifi_manager] Aucun réseau détecté.")
        return
    nets = parse_networks(out)
    if not nets:
        print("[wifi_manager] Aucun réseau trouvé dans le parsing.")
        return
    print("Réseaux disponibles :")
    for net in nets:
        ssid = net.get("SSID", "?")
        signal = net.get("Signal", "N/A")
        auth = net.get("Authentication", "N/A")
        cipher = net.get("Cipher", "N/A")
        print(f"- {ssid} | Signal: {signal} | Auth: {auth} | Cipher: {cipher}")

def disconnect():
    out = run_netsh(["wlan", "disconnect"])
    if out:
        print("[wifi_manager] Déconnexion demandée.")
    else:
        print("[wifi_manager] Aucun résultat – peut‑être déjà déconnecté.")

def connect(ssid: str):
    # Attempt to connect using the profile name equal to SSID
    out = run_netsh(["wlan", "connect", f"name={ssid}"])
    if out:
        print(f"[wifi_manager] Tentative de connexion à '{ssid}'…")
        print(out)
    else:
        print(f"[wifi_manager] Impossible de se connecter à '{ssid}'.")

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Gestionnaire Wi‑Fi Windows via netsh.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true", help="Afficher le réseau actuellement connecté")
    group.add_argument("--scan", action="store_true", help="Lister les réseaux disponibles")
    group.add_argument("--disconnect", action="store_true", help="Déconnecter le client Wi‑Fi actuel")
    group.add_argument("--connect", metavar="SSID", help="Connecter au réseau indiqué (profil existant)")
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.scan:
        scan_networks()
    elif args.disconnect:
        disconnect()
    elif args.connect:
        connect(args.connect)

if __name__ == "__main__":
    main()
