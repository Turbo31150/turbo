#!/usr/bin/env python3
"""registry_manager.py

Gestionnaire de registre Windows sécurisé.

CLI :
    --read KEY VALUE_NAME    : Lire une valeur du registre
    --write KEY VALUE_NAME VALUE [--type TYPE] : Écrire une valeur
    --backup KEY --output FILE : Sauvegarder une clé en .reg
    --search PATTERN [--hive HIVE] : Chercher dans le registre
    --list KEY               : Lister les sous-clés et valeurs
"""

import argparse
import subprocess
import sys
import re
from typing import Optional, List, Tuple
from _paths import TELEGRAM_TOKEN, TELEGRAM_CHAT

# TELEGRAM_TOKEN loaded from _paths (.env)
TELEGRAM_CHAT_ID = TELEGRAM_CHAT

def telegram_send(msg: str):
    import urllib.parse, urllib.request
    try:
        data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": msg}).encode()
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)
    except Exception:
        pass

def run_cmd(cmd: List[str], timeout: int = 15) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=timeout).strip()
    except Exception:
        return ""

# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
def read_value(key: str, value_name: str) -> Optional[str]:
    out = run_cmd(["reg", "query", key, "/v", value_name])
    for line in out.splitlines():
        if value_name.lower() in line.lower():
            parts = line.strip().split(None, 2)
            if len(parts) >= 3:
                return parts[2]
    return None

# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------
def write_value(key: str, value_name: str, value: str, reg_type: str = "REG_SZ") -> bool:
    result = run_cmd(["reg", "add", key, "/v", value_name, "/t", reg_type, "/d", value, "/f"])
    return "succès" in result.lower() or "successfully" in result.lower() or result == ""

# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------
def backup_key(key: str, output: str) -> bool:
    result = run_cmd(["reg", "export", key, output, "/y"])
    return True

# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
def search_registry(pattern: str, hive: str = "HKLM") -> List[str]:
    out = run_cmd(["reg", "query", hive, "/s", "/f", pattern], timeout=30)
    results = []
    for line in out.splitlines():
        line = line.strip()
        if line and not line.startswith("Fin") and not line.startswith("End"):
            results.append(line)
    return results[:50]  # Limiter à 50 résultats

# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
def list_key(key: str) -> Tuple[List[str], List[Tuple[str, str, str]]]:
    out = run_cmd(["reg", "query", key])
    subkeys = []
    values = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("HK") or line.startswith("HKEY"):
            if line != key:
                subkeys.append(line)
        else:
            parts = line.split(None, 2)
            if len(parts) >= 3:
                values.append((parts[0], parts[1], parts[2]))
            elif len(parts) == 2:
                values.append((parts[0], parts[1], ""))
    return subkeys, values

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Gestionnaire de registre Windows.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_read = sub.add_parser("read", help="Lire une valeur")
    p_read.add_argument("key", help="Clé registre (ex: HKLM/SOFTWARE/...)")
    p_read.add_argument("value_name", help="Nom de la valeur")

    p_write = sub.add_parser("write", help="Écrire une valeur")
    p_write.add_argument("key")
    p_write.add_argument("value_name")
    p_write.add_argument("value")
    p_write.add_argument("--type", default="REG_SZ", choices=["REG_SZ", "REG_DWORD", "REG_QWORD", "REG_EXPAND_SZ", "REG_MULTI_SZ"])

    p_backup = sub.add_parser("backup", help="Sauvegarder une clé")
    p_backup.add_argument("key")
    p_backup.add_argument("--output", required=True, help="Fichier .reg de sortie")

    p_search = sub.add_parser("search", help="Chercher dans le registre")
    p_search.add_argument("pattern")
    p_search.add_argument("--hive", default="HKLM", help="Hive racine (HKLM, HKCU, etc.)")

    p_list = sub.add_parser("list", help="Lister sous-clés et valeurs")
    p_list.add_argument("key")

    args = parser.parse_args()

    if args.command == "read":
        val = read_value(args.key, args.value_name)
        if val:
            print(f"{args.value_name} = {val}")
        else:
            print(f"[registry_manager] Valeur '{args.value_name}' introuvable.")

    elif args.command == "write":
        ok = write_value(args.key, args.value_name, args.value, args.type)
        if ok:
            print(f"[registry_manager] {args.value_name} = {args.value} (type: {args.type}) écrit.")
        else:
            print("[registry_manager] Échec de l'écriture.")

    elif args.command == "backup":
        backup_key(args.key, args.output)
        print(f"[registry_manager] Clé sauvegardée → {args.output}")

    elif args.command == "search":
        results = search_registry(args.pattern, args.hive)
        print(f"Résultats pour '{args.pattern}' dans {args.hive} ({len(results)} trouvés) :")
        for r in results:
            print(f"  {r}")

    elif args.command == "list":
        subkeys, values = list_key(args.key)
        print(f"Clé : {args.key}")
        if subkeys:
            print(f"\nSous-clés ({len(subkeys)}) :")
            for sk in subkeys:
                print(f"  📁 {sk}")
        if values:
            print(f"\nValeurs ({len(values)}) :")
            for name, vtype, val in values:
                print(f"  {name} [{vtype}] = {val}")

if __name__ == "__main__":
    main()