#!/usr/bin/env python3
"""driver_checker.py

Vérificateur de pilotes Windows.

CLI :
    --list       : Lister tous les pilotes avec version et date
    --outdated   : Détecter les pilotes anciens (>1 an)
    --problems   : Pilotes en erreur ou désactivés
    --gpu        : Info détaillée GPU (nvidia-smi + driver)
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from typing import List, Dict

# TELEGRAM_TOKEN loaded from _paths (.env)
TELEGRAM_CHAT_ID = TELEGRAM_CHAT

def telegram_send(msg: str):
    import urllib.parse, urllib.request
from _paths import TELEGRAM_TOKEN, TELEGRAM_CHAT
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

def run_cmd(cmd: List[str], timeout: int = 15) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=timeout).strip()
    except Exception:
        return ""

# ---------------------------------------------------------------------------
# List drivers
# ---------------------------------------------------------------------------
def list_drivers():
    out = ps("""
        Get-WmiObject Win32_PnPSignedDriver |
        Where-Object {$_.DeviceName -ne $null} |
        Select-Object DeviceName,DriverVersion,DriverDate,Manufacturer |
        Sort-Object DeviceName |
        ConvertTo-Json -Compress
    """)
    if not out:
        print("[driver_checker] Impossible de lister les pilotes.")
        return
    try:
        drivers = json.loads(out)
        if isinstance(drivers, dict):
            drivers = [drivers]
    except Exception:
        print("[driver_checker] Erreur de parsing.")
        return

    print(f"Pilotes installés ({len(drivers)}) :")
    for d in drivers[:60]:
        name = d.get("DeviceName", "?")
        ver = d.get("DriverVersion", "?")
        mfr = d.get("Manufacturer", "?")
        print(f"  {name}")
        print(f"    Version: {ver} | Fabricant: {mfr}")

# ---------------------------------------------------------------------------
# Outdated drivers
# ---------------------------------------------------------------------------
def check_outdated():
    out = ps("""
        Get-WmiObject Win32_PnPSignedDriver |
        Where-Object {$_.DeviceName -ne $null -and $_.DriverDate -ne $null} |
        Select-Object DeviceName,DriverVersion,DriverDate |
        ConvertTo-Json -Compress
    """)
    if not out:
        print("[driver_checker] Impossible de vérifier les pilotes.")
        return
    try:
        drivers = json.loads(out)
        if isinstance(drivers, dict):
            drivers = [drivers]
    except Exception:
        return

    one_year_ago = datetime.now() - timedelta(days=365)
    outdated = []
    for d in drivers:
        date_str = d.get("DriverDate", "")
        if not date_str:
            continue
        try:
            # WMI format: 20231215000000.000000-000
            dt = datetime.strptime(date_str[:14], "%Y%m%d%H%M%S")
            if dt < one_year_ago:
                outdated.append((d["DeviceName"], d.get("DriverVersion", "?"), dt.strftime("%Y-%m-%d")))
        except Exception:
            continue

    if not outdated:
        print("[driver_checker] Tous les pilotes sont récents (< 1 an).")
        return

    print(f"Pilotes anciens (> 1 an) — {len(outdated)} trouvés :")
    for name, ver, date in outdated:
        print(f"  ⚠️ {name}")
        print(f"    Version: {ver} | Date: {date}")

# ---------------------------------------------------------------------------
# Problem drivers
# ---------------------------------------------------------------------------
def check_problems():
    out = ps("""
        Get-PnpDevice |
        Where-Object {$_.Status -ne 'OK' -and $_.Class -ne $null} |
        Select-Object Status,Class,FriendlyName,InstanceId |
        ConvertTo-Json -Compress
    """)
    if not out:
        print("[driver_checker] Aucun pilote en erreur détecté.")
        return
    try:
        devices = json.loads(out)
        if isinstance(devices, dict):
            devices = [devices]
    except Exception:
        print("[driver_checker] Aucun problème détecté.")
        return

    if not devices:
        print("[driver_checker] Tous les pilotes fonctionnent correctement.")
        return

    print(f"Pilotes en erreur ({len(devices)}) :")
    for d in devices:
        status = d.get("Status", "?")
        name = d.get("FriendlyName", "Inconnu")
        cls = d.get("Class", "?")
        icon = "🔴" if status == "Error" else "🟡"
        print(f"  {icon} [{status}] {name} (classe: {cls})")

# ---------------------------------------------------------------------------
# GPU info
# ---------------------------------------------------------------------------
def gpu_info():
    nv = run_cmd(["nvidia-smi", "--query-gpu=name,driver_version,temperature.gpu,memory.used,memory.total",
                   "--format=csv,noheader,nounits"])
    if nv:
        print("GPU NVIDIA :")
        for line in nv.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                print(f"  🖥️ {parts[0]}")
                print(f"    Driver: {parts[1]} | Temp: {parts[2]}°C | VRAM: {parts[3]}/{parts[4]} MB")
    else:
        print("[driver_checker] nvidia-smi non disponible.")

    # Windows driver info
    drv = ps("Get-WmiObject Win32_VideoController | Select-Object Name,DriverVersion,DriverDate | ConvertTo-Json -Compress")
    if drv:
        try:
            gpus = json.loads(drv)
            if isinstance(gpus, dict):
                gpus = [gpus]
            print("\nPilotes vidéo Windows :")
            for g in gpus:
                print(f"  {g.get('Name', '?')} — Driver v{g.get('DriverVersion', '?')}")
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(description="Vérificateur de pilotes Windows.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="Lister tous les pilotes")
    group.add_argument("--outdated", action="store_true", help="Pilotes anciens (> 1 an)")
    group.add_argument("--problems", action="store_true", help="Pilotes en erreur")
    group.add_argument("--gpu", action="store_true", help="Info GPU détaillée")
    args = parser.parse_args()

    if args.list:
        list_drivers()
    elif args.outdated:
        check_outdated()
    elif args.problems:
        check_problems()
    elif args.gpu:
        gpu_info()

if __name__ == "__main__":
    main()