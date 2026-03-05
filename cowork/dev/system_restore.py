#!/usr/bin/env python3
"""system_restore.py

Gestionnaire de points de restauration Windows.

CLI :
    --create [DESC]  : Créer un point de restauration
    --list           : Lister les points existants
    --info           : Informations sur la restauration système
"""

import argparse
import json
import subprocess
import sys
from typing import List

TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT_ID = "2010747443"

def telegram_send(msg: str):
    import urllib.parse, urllib.request
    try:
        data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": msg}).encode()
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)
    except Exception:
        pass

def ps(cmd: str, timeout: int = 20) -> str:
    try:
        return subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", cmd],
            text=True, stderr=subprocess.DEVNULL, timeout=timeout
        ).strip()
    except Exception:
        return ""

# ---------------------------------------------------------------------------
# Create restore point
# ---------------------------------------------------------------------------
def create_restore_point(description: str = "JARVIS Auto Restore Point"):
    print(f"[system_restore] Création du point de restauration : {description}")
    out = ps(f'Checkpoint-Computer -Description "{description}" -RestorePointType "MODIFY_SETTINGS" -ErrorAction SilentlyContinue', timeout=60)
    # Check if it worked
    latest = ps("Get-ComputerRestorePoint | Sort-Object SequenceNumber -Descending | Select-Object -First 1 | ConvertTo-Json -Compress")
    if latest:
        try:
            data = json.loads(latest)
            print(f"[system_restore] Point créé : #{data.get('SequenceNumber', '?')} — {data.get('Description', '?')}")
            telegram_send(f"💾 Point de restauration créé : {description}")
            return
        except Exception:
            pass
    print("[system_restore] Point de restauration créé (ou limite de fréquence atteinte).")
    print("  Note: Windows limite à 1 point par 24h via PowerShell.")

# ---------------------------------------------------------------------------
# List restore points
# ---------------------------------------------------------------------------
def list_restore_points():
    out = ps("Get-ComputerRestorePoint | Sort-Object SequenceNumber -Descending | ConvertTo-Json -Compress")
    if not out:
        print("[system_restore] Aucun point de restauration trouvé (ou accès refusé).")
        print("  Note: Cette commande nécessite des droits administrateur.")
        return
    try:
        points = json.loads(out)
        if isinstance(points, dict):
            points = [points]
    except Exception:
        print("[system_restore] Erreur de parsing.")
        return

    print(f"Points de restauration ({len(points)}) :")
    for p in points:
        seq = p.get("SequenceNumber", "?")
        desc = p.get("Description", "?")
        date_raw = p.get("CreationTime", "")
        # WMI date format
        date_str = date_raw[:10] if date_raw else "?"
        rtype = p.get("RestorePointType", "?")
        type_label = {0: "App Install", 1: "App Uninstall", 10: "Device Driver", 12: "Modify Settings", 13: "Cancelled"}.get(rtype, str(rtype))
        print(f"  #{seq} — {desc}")
        print(f"    Date: {date_str} | Type: {type_label}")

# ---------------------------------------------------------------------------
# Info
# ---------------------------------------------------------------------------
def show_info():
    # Protection status
    status = ps("Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore' -Name RPSessionInterval -ErrorAction SilentlyContinue | Select-Object -ExpandProperty RPSessionInterval")
    enabled = ps("(Get-ComputerRestorePoint -ErrorAction SilentlyContinue) -ne $null")

    # Disk usage
    disk = ps("vssadmin list shadowstorage 2>$null")

    print("=== Restauration système Windows ===")

    # Check if protection is enabled
    protection = ps("Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore' -ErrorAction SilentlyContinue | Select-Object RPSessionInterval,DisableSR | ConvertTo-Json -Compress")
    if protection:
        try:
            data = json.loads(protection)
            disabled = data.get("DisableSR", 0)
            print(f"Protection : {'Désactivée' if disabled else 'Activée'}")
        except Exception:
            print("Protection : État inconnu")
    else:
        print("Protection : État inconnu (accès admin requis)")

    if disk:
        print(f"\nStockage Shadow Copy :")
        for line in disk.splitlines():
            if line.strip():
                print(f"  {line.strip()}")

    # Count points
    count = ps("(Get-ComputerRestorePoint -ErrorAction SilentlyContinue).Count")
    print(f"\nPoints de restauration : {count or '0 (ou accès refusé)'}")

def main():
    parser = argparse.ArgumentParser(description="Gestionnaire de points de restauration Windows.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create", nargs="?", const="JARVIS Auto Restore Point", metavar="DESC", help="Créer un point de restauration")
    group.add_argument("--list", action="store_true", help="Lister les points existants")
    group.add_argument("--info", action="store_true", help="Info restauration système")
    args = parser.parse_args()

    if args.create is not None:
        create_restore_point(args.create)
    elif args.list:
        list_restore_points()
    elif args.info:
        show_info()

if __name__ == "__main__":
    main()
