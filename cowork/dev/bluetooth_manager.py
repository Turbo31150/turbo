#!/usr/bin/env python3
"""bluetooth_manager.py

Gestionnaire Bluetooth Windows via PowerShell.

CLI :
    --scan        : Scanner les appareils Bluetooth visibles
    --list        : Lister les appareils appairés
    --status      : État de l'adaptateur Bluetooth
    --connect MAC : Connecter un appareil (via DeviceId)
"""

import argparse
import subprocess
import sys
from typing import List, Dict

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"

def telegram_send(msg: str):
    import urllib.parse, urllib.request
    try:
        data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": msg}).encode()
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)
    except Exception:
        pass

def ps(cmd: str, timeout: int = 15) -> str:
    try:
        return subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", cmd],
            text=True, stderr=subprocess.DEVNULL, timeout=timeout
        ).strip()
    except Exception:
        return ""

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
def show_status():
    out = ps("Get-PnpDevice -Class Bluetooth | Select-Object Status,FriendlyName | Format-Table -AutoSize")
    if not out:
        print("[bluetooth_manager] Aucun adaptateur Bluetooth détecté.")
        return
    # Check adapter
    adapter = ps("Get-PnpDevice -Class Bluetooth | Where-Object {$_.FriendlyName -like '*Bluetooth*' -and $_.Class -eq 'Bluetooth'} | Select-Object -First 1 Status,FriendlyName | Format-List")
    radio = ps("Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | Where-Object {$_.InstanceId -like 'USB*' -or $_.FriendlyName -match 'Radio|Adapter'} | Select-Object -First 1 Status")
    enabled = "OK" in (radio or adapter) or "OK" in out.split('\n')[0] if out else False
    print(f"Adaptateur Bluetooth : {'Actif' if enabled else 'État inconnu'}")
    print(f"\nAppareils Bluetooth :")
    print(out)

# ---------------------------------------------------------------------------
# List paired
# ---------------------------------------------------------------------------
def list_paired():
    out = ps("""
        Get-PnpDevice -Class Bluetooth |
        Where-Object {$_.FriendlyName -notmatch 'Microsoft|Radio|Enumerator|Bluetooth Device'} |
        Select-Object Status,FriendlyName,InstanceId |
        Format-Table -AutoSize
    """)
    if not out or "FriendlyName" not in out:
        print("[bluetooth_manager] Aucun appareil appairé trouvé.")
        return
    print("Appareils Bluetooth appairés :")
    print(out)

# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------
def scan_devices():
    print("[bluetooth_manager] Scan Bluetooth en cours (via PnP)...")
    out = ps("""
        Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue |
        Select-Object Status,FriendlyName,InstanceId |
        Format-Table -AutoSize
    """, timeout=20)
    if not out:
        out = ps("""
            Get-PnpDevice | Where-Object {$_.Class -like '*Bluetooth*'} |
            Select-Object Status,Class,FriendlyName |
            Format-Table -AutoSize
        """, timeout=20)
    if out:
        print("Appareils Bluetooth détectés :")
        print(out)
    else:
        print("[bluetooth_manager] Aucun appareil détecté. Vérifiez que le Bluetooth est activé.")

# ---------------------------------------------------------------------------
# Connect
# ---------------------------------------------------------------------------
def connect_device(device_id: str):
    # Enable device via PnP
    out = ps(f"Enable-PnpDevice -InstanceId '{device_id}' -Confirm:$false -ErrorAction SilentlyContinue")
    print(f"[bluetooth_manager] Tentative de connexion à {device_id}")
    # Verify
    status = ps(f"Get-PnpDevice -InstanceId '{device_id}' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Status")
    if status == "OK":
        print(f"[bluetooth_manager] Appareil connecté (Status: OK)")
    else:
        print(f"[bluetooth_manager] Status après connexion : {status or 'inconnu'}")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Gestionnaire Bluetooth Windows.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scan", action="store_true", help="Scanner les appareils visibles")
    group.add_argument("--list", action="store_true", help="Lister les appareils appairés")
    group.add_argument("--status", action="store_true", help="État de l'adaptateur")
    group.add_argument("--connect", metavar="DEVICE_ID", help="Connecter un appareil")
    args = parser.parse_args()

    if args.scan:
        scan_devices()
    elif args.list:
        list_paired()
    elif args.status:
        show_status()
    elif args.connect:
        connect_device(args.connect)

if __name__ == "__main__":
    main()
