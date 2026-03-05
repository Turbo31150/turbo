#!/usr/bin/env python3
"""power_manager.py — Gestion des plans d'alimentation Windows pour le cluster IA.

Fonctionnalités principales :
  --status            Affiche le plan actif et ses paramètres clés.
  --plan              Liste tous les plans disponibles.
  --set-plan NAME     Définit le plan d'alimentation actif (par nom ou GUID).
  --battery           Affiche l'état de la batterie (si présent).
  --sleep-settings    Affiche les paramètres de mise en veille/sommeil.

Utilise uniquement la bibliothèque standard.
"""

import argparse
import json
import subprocess
import sys
import re
from typing import List, Dict, Any

def run_cmd(cmd: List[str]) -> str:
    """Execute une commande et retourne stdout décodé en UTF-8.
    Lance une exception si le code de retour n'est pas zéro.
    """
    result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    if result.returncode != 0:
        raise RuntimeError(f"Command {' '.join(cmd)} failed: {result.stderr.strip()}")
    return result.stdout.strip()

def list_plans() -> List[Dict[str, str]]:
    """Retourne la liste des plans d'alimentation.
    Chaque entrée contient GUID, Index, Name, Description.
    """
    out = run_cmd(["powercfg", "/list"])
    plans = []
    for line in out.splitlines():
        # Exemple de ligne : "Power Scheme GUID: 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c  (Balanced) *"
        m = re.search(r"Power Scheme GUID:\s*([0-9a-fA-F-]+)\s*\(([^)]+)\)(?:\s*\*)?", line)
        if m:
            guid, name = m.groups()
            active = "*" in line
            plans.append({"guid": guid, "name": name, "active": active})
    return plans

def get_active_plan() -> Dict[str, str]:
    for p in list_plans():
        if p.get("active"):
            return p
    # fallback: query via powercfg /getactivescheme
    out = run_cmd(["powercfg", "/getactivescheme"])
    m = re.search(r"Power Scheme GUID:\s*([0-9a-fA-F-]+)\s*\(([^)]+)\)", out)
    if m:
        guid, name = m.groups()
        return {"guid": guid, "name": name, "active": True}
    raise RuntimeError("Unable to determine active power plan")

def set_active_plan(identifier: str) -> Dict[str, str]:
    """Change le plan actif. identifier peut être un GUID ou le nom (case‑insensitive)."""
    plans = list_plans()
    guid = None
    for p in plans:
        if p["guid"].lower() == identifier.lower() or p["name"].lower() == identifier.lower():
            guid = p["guid"]
            break
    if not guid:
        raise ValueError(f"Plan '{identifier}' not found.")
    run_cmd(["powercfg", "/setactive", guid])
    return get_active_plan()

def get_battery_info() -> Dict[str, Any]:
    # Utilise powercfg /batteryreport n’est pas disponible sans privilèges admin.
    # On utilise wmic pour récupérer le statut.
    try:
        out = run_cmd(["wmic", "PATH", "Win32_Battery", "Get", "EstimatedChargeRemaining,Status"])
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        if len(lines) >= 2:
            # Première ligne = en-têtes
            values = lines[1].split()
            charge = int(values[0]) if values[0].isdigit() else None
            status = int(values[1]) if len(values) > 1 and values[1].isdigit() else None
            return {"charge_percent": charge, "status": status}
    except Exception:
        pass
    return {"error": "Battery information not available on this system"}

def get_sleep_settings() -> Dict[str, Any]:
    out = run_cmd(["powercfg", "/query"])
    # Recherche des réglages de mise en veille (ac et dc)
    sleep_settings = {}
    for line in out.splitlines():
        if "SUB_SLEEP" in line:
            # Exemple : "Subgroup GUID: ... (Sleep)"
            continue
        m = re.search(r"Power Setting GUID: ([0-9a-fA-F-]+)\s+\(([^)]+)\)\s+\[([^]]+)\]", line)
        if m:
            guid, name, ac_dc = m.groups()
            if name.lower().startswith("sleep after"):
                sleep_settings[ac_dc] = name
    return {"raw": out[:500]}

def main():
    parser = argparse.ArgumentParser(description="Gestionnaire de plans d'alimentation Windows pour le cluster IA")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true", help="Affiche le plan actif et ses paramètres")
    group.add_argument("--plan", action="store_true", help="Liste tous les plans disponibles")
    group.add_argument("--set-plan", metavar="NAME_OR_GUID", help="Définit le plan actif")
    group.add_argument("--battery", action="store_true", help="Affiche l'état de la batterie")
    group.add_argument("--sleep-settings", action="store_true", help="Affiche les paramètres de mise en veille")
    args = parser.parse_args()

    try:
        if args.status:
            active = get_active_plan()
            print(json.dumps({"active_plan": active}, ensure_ascii=False, indent=2))
        elif args.plan:
            plans = list_plans()
            print(json.dumps({"plans": plans}, ensure_ascii=False, indent=2))
        elif args.set_plan:
            new = set_active_plan(args.set_plan)
            print(json.dumps({"new_active_plan": new}, ensure_ascii=False, indent=2))
        elif args.battery:
            info = get_battery_info()
            print(json.dumps(info, ensure_ascii=False, indent=2))
        elif args.sleep_settings:
            settings = get_sleep_settings()
            print(json.dumps(settings, ensure_ascii=False, indent=2))
        else:
            parser.print_help()
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
