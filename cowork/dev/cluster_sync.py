#!/usr/bin/env python3
"""cluster_sync.py — Synchronisation du cluster.

Ce script gère la synchronisation des configurations et scripts entre les trois nœuds du cluster :
- M1 (local)
- M2 (192.168.1.26)
- M3 (192.168.1.113)

Il utilise uniquement la bibliothèque standard et les outils système (scp/ssh) disponibles sur la machine.

CLI :
  --sync    : réalise un push puis un pull complet.
  --diff    : affiche les différences de fichiers (checksum).
  --push    : envoie les fichiers locaux vers les nœuds distants.
  --pull    : récupère les fichiers distants vers le local.
  --status  : résume l'état de synchronisation.

Le script synchronise les répertoires "dev/" ainsi que le fichier "IDENTITY.md".
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Configuration des nœuds
NODES = {
    "M2": "192.168.1.26",
    "M3": "192.168.1.113",
}
# Chemin distant (on suppose le même chemin workspace sur chaque nœud)
REMOTE_ROOT = "~/workspace"
LOCAL_ROOT = Path.cwd()

def run_cmd(command: List[str]) -> Tuple[int, str, str]:
    """Execute une commande et retourne (code_retour, stdout, stderr)."""
    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()

def ssh_cmd(host: str, remote_cmd: str) -> Tuple[int, str, str]:
    return run_cmd(["ssh", host, remote_cmd])

def scp_copy(src: str, host: str, dst: str, direction: str = "push") -> Tuple[int, str, str]:
    """Copie de fichiers avec scp.
    direction = "push"  -> scp src to host:dst
    direction = "pull"  -> scp host:src dst
    """
    if direction == "push":
        return run_cmd(["scp", "-r", src, f"{host}:{dst}"])
    else:
        return run_cmd(["scp", "-r", f"{host}:{src}", dst])

def gather_checksums(path: Path) -> Dict[str, str]:
    """Retourne un dict {relative_path: md5} pour tous les fichiers sous path."""
    import hashlib
    checksums = {}
    for file in path.rglob("*"):
        if file.is_file():
            rel = str(file.relative_to(path))
            h = hashlib.md5()
            with file.open('rb') as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            checksums[rel] = h.hexdigest()
    return checksums

def remote_checksums(host: str) -> Dict[str, str]:
    """Demande au remote de calculer les checksums via ssh.
    Retourne un dict {relative_path: md5}.
    """
    remote_cmd = (
        f"python - <<'PY'\n"
        f"import os, hashlib, json;\n"
        f"root='{REMOTE_ROOT}';\n"
        f"checksums={{}};\n"
        f"for dirpath,_,filenames in os.walk(root):\n"
        f"  for f in filenames:\n"
        f"    p=os.path.join(dirpath,f);\n"
        f"    rel=os.path.relpath(p,root);\n"
        f"    h=hashlib.md5();\n"
        f"    with open(p,'rb') as fh:\n"
        f"      while True:\n"
        f"        chunk=fh.read(8192);\n"
        f"        if not chunk: break;\n"
        f"        h.update(chunk);\n"
        f"    checksums[rel]=h.hexdigest();\n"
        f"print(json.dumps(checksums))\n"
        f"PY"
    )
    rc, out, err = ssh_cmd(host, remote_cmd)
    if rc != 0:
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {}

def diff_node(host: str) -> Dict[str, List[str]]:
    local = {}
    # local checksums for dev/ and IDENTITY.md
    local_paths = [LOCAL_ROOT / "dev", LOCAL_ROOT / "IDENTITY.md"]
    for p in local_paths:
        if p.is_dir():
            local.update(gather_checksums(p))
        elif p.is_file():
            rel = str(p.relative_to(LOCAL_ROOT))
            h = hashlib.md5()
            with p.open('rb') as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            local[rel] = h.hexdigest()
    remote = remote_checksums(host)
    diff = {"only_local": [], "only_remote": [], "changed": []}
    for k, v in local.items():
        if k not in remote:
            diff["only_local"].append(k)
        elif remote[k] != v:
            diff["changed"].append(k)
    for k in remote:
        if k not in local:
            diff["only_remote"].append(k)
    return diff

def perform_sync(action: str):
    results = {}
    for name, host in NODES.items():
        if action == "push":
            src = str(LOCAL_ROOT)
            dst = REMOTE_ROOT
            rc, out, err = scp_copy(src, host, dst, "push")
        elif action == "pull":
            src = REMOTE_ROOT
            dst = str(LOCAL_ROOT)
            rc, out, err = scp_copy(src, host, dst, "pull")
        elif action == "status":
            diff = diff_node(host)
            results[name] = diff
            continue
        else:
            rc, out, err = 1, "", f"Unsupported action {action}"
        results[name] = {"rc": rc, "out": out, "err": err}
    print(json.dumps(results, ensure_ascii=False, indent=2))

def main():
    parser = argparse.ArgumentParser(description="Synchronisation du cluster (M1,M2,M3)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sync", action="store_true", help="Push puis pull complet")
    group.add_argument("--diff", action="store_true", help="Afficher les différences de checksum")
    group.add_argument("--push", action="store_true", help="Envoyer les fichiers locaux vers les nœuds")
    group.add_argument("--pull", action="store_true", help="Récupérer les fichiers des nœuds vers le local")
    group.add_argument("--status", action="store_true", help="Résumé de l'état de synchronisation")
    args = parser.parse_args()

    if args.sync:
        perform_sync("push")
        perform_sync("pull")
    elif args.push:
        perform_sync("push")
    elif args.pull:
        perform_sync("pull")
    elif args.diff:
        all_diff = {}
        for name, host in NODES.items():
            all_diff[name] = diff_node(host)
        print(json.dumps(all_diff, ensure_ascii=False, indent=2))
    elif args.status:
        perform_sync("status")

if __name__ == "__main__":
    main()
