#!/usr/bin/env python3
"""startup_manager.py — Gestion des programmes au démarrage Windows.

Fonctionnalités :
  --list                Lister les entrées de démarrage (registre + dossier).
  --add PATH            Ajouter un programme au démarrage (registre).
  --remove NAME         Supprimer l'entrée nommée (registre ou fichier).
  --optimize            Analyser et proposer des optimisations (ex. >1 Mo).
  --report              Rapport synthétique au format JSON.

Toutes les sorties sont du JSON (sauf --help).
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Registry handling (only on Windows)
if os.name == "nt":
    import winreg

REG_RUN_PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
STARTUP_FOLDER = os.path.expandvars(r"%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup")

def get_registry_entries():
    entries = []
    if os.name != "nt":
        return entries
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_PATH) as key:
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    entries.append({"name": name, "path": value, "source": "registry"})
                    i += 1
                except OSError:
                    break
    except FileNotFoundError:
        pass
    return entries

def get_startup_folder_entries():
    entries = []
    folder = Path(STARTUP_FOLDER)
    if not folder.is_dir():
        return entries
    for file in folder.iterdir():
        if file.is_file():
            entries.append({"name": file.name, "path": str(file), "source": "folder"})
    return entries

def list_entries():
    data = get_registry_entries() + get_startup_folder_entries()
    print(json.dumps(data, ensure_ascii=False, indent=2))

def add_entry(path_str):
    if os.name != "nt":
        print(json.dumps({"error": "Add only supported on Windows"}, ensure_ascii=False))
        return
    path = Path(path_str).expanduser().resolve()
    if not path.is_file():
        print(json.dumps({"error": f"File not found: {path}"}, ensure_ascii=False))
        return
    name = path.stem
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(path))
        print(json.dumps({"added": {"name": name, "path": str(path), "source": "registry"}}, ensure_ascii=False))
    except PermissionError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))

def remove_entry(name):
    removed = []
    # Registry
    if os.name == "nt":
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_PATH, 0, winreg.KEY_SET_VALUE) as key:
                try:
                    winreg.DeleteValue(key, name)
                    removed.append({"name": name, "source": "registry"})
                except FileNotFoundError:
                    pass
        except PermissionError:
            pass
    # Startup folder
    folder_path = Path(STARTUP_FOLDER) / name
    if folder_path.is_file():
        try:
            folder_path.unlink()
            removed.append({"name": name, "source": "folder"})
        except Exception:
            pass
    if removed:
        print(json.dumps({"removed": removed}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"error": f"Entry '{name}' not found"}, ensure_ascii=False))

def optimize_entries():
    # Simple heuristic: recommend removal of entries >1 MiB (files) or path string >100 chars (registry)
    recommendations = []
    for entry in get_startup_folder_entries():
        try:
            size = os.path.getsize(entry["path"])
            if size > 1_048_576:  # 1 MiB
                recommendations.append({"name": entry["name"], "size_bytes": size, "reason": "large file"})
        except OSError:
            continue
    for entry in get_registry_entries():
        if len(entry["path"]) > 100:
            recommendations.append({"name": entry["name"], "path_length": len(entry["path"]), "reason": "long path"})
    print(json.dumps({"recommendations": recommendations}, ensure_ascii=False, indent=2))

def report():
    regs = get_registry_entries()
    folder = get_startup_folder_entries()
    total = len(regs) + len(folder)
    # approximate size for folder entries
    total_size = 0
    for e in folder:
        try:
            total_size += os.path.getsize(e["path"])
        except OSError:
            pass
    report_data = {
        "total_entries": total,
        "registry_entries": len(regs),
        "folder_entries": len(folder),
        "folder_total_size_bytes": total_size,
    }
    print(json.dumps(report_data, ensure_ascii=False, indent=2))

def main():
    parser = argparse.ArgumentParser(description="Gestion des programmes au démarrage Windows")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="Lister les entrées de démarrage")
    group.add_argument("--add", metavar="PATH", help="Ajouter un programme (registre)")
    group.add_argument("--remove", metavar="NAME", help="Supprimer une entrée par son nom")
    group.add_argument("--optimize", action="store_true", help="Proposer des optimisations")
    group.add_argument("--report", action="store_true", help="Rapport synthétique")
    args = parser.parse_args()

    if args.list:
        list_entries()
    elif args.add:
        add_entry(args.add)
    elif args.remove:
        remove_entry(args.remove)
    elif args.optimize:
        optimize_entries()
    elif args.report:
        report()

if __name__ == "__main__":
    main()
