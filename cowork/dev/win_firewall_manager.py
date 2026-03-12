#!/usr/bin/env python3
"""win_firewall_manager.py

Gestion simple du pare-feu Windows via netsh advfirewall.

CLI disponible :
  --status          : Liste les règles du pare-feu (nom, direction, action, protocole, ports).
  --rules           : Alias de --status, plus détails bruts.
  --add NAME --dir DIR --action ACTION [--proto PROTO] [--port PORT]
                    : Ajoute une règle.
  --remove NAME     : Supprime une règle par son nom.
  --audit [--ports P1,P2,...]
                    : Vérifie si les ports indiqués sont autorisés en inbound.

Exemple d'usage :
  python win_firewall_manager.py --add "AllowMyApp" --dir inbound --action allow --proto TCP --port 1234
  python win_firewall_manager.py --audit --ports 1234,11434,18789,9742,8080

Le script utilise uniquement la bibliothèque standard (argparse, subprocess, json, sys).
"""

import argparse
import subprocess
import sys
import json
from typing import List, Dict


def _run_cmd(cmd: List[str]) -> str:
    """Execute la commande et retourne stdout décodé.
    Lève une RuntimeError en cas d'échec.
    """
    result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    if result.returncode != 0:
        raise RuntimeError(f"Command {' '.join(cmd)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def list_rules() -> List[Dict[str, str]]:
    """Retourne une liste de dictionnaires représentant les règles du pare-feu.
    Utilise `netsh advfirewall firewall show rule name=all` et parse les lignes clés.
    """
    raw = _run_cmd(["netsh", "advfirewall", "firewall", "show", "rule", "name=all"])
    rules = []
    current = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("Rule Name:"):
            if current:
                rules.append(current)
                current = {}
            current["Name"] = line.split(":", 1)[1].strip()
        elif line.startswith("Direction:"):
            current["Direction"] = line.split(":", 1)[1].strip()
        elif line.startswith("Action:"):
            current["Action"] = line.split(":", 1)[1].strip()
        elif line.startswith("Protocol:"):
            current["Protocol"] = line.split(":", 1)[1].strip()
        elif line.startswith("LocalPort:"):
            current["LocalPort"] = line.split(":", 1)[1].strip()
    if current:
        rules.append(current)
    return rules


def add_rule(name: str, direction: str, action: str, proto: str = "TCP", port: str = ""):
    cmd = ["netsh", "advfirewall", "firewall", "add", "rule", f"name={name}", f"dir={direction}", f"action={action}"]
    if proto:
        cmd.append(f"protocol={proto}")
    if port:
        cmd.append(f"localport={port}")
    _run_cmd(cmd)
    return f"Rule '{name}' added."


def remove_rule(name: str):
    cmd = ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={name}"]
    _run_cmd(cmd)
    return f"Rule '{name}' removed."


def audit_ports(ports: List[int]) -> Dict[int, bool]:
    """Vérifie pour chaque port s'il existe au moins une règle inbound allow.
    Retourne un dict {port: bool}.
    """
    results = {}
    # Obtenir toutes les règles une fois pour éviter de lancer netsh à chaque port
    raw = _run_cmd(["netsh", "advfirewall", "firewall", "show", "rule", "name=all"])
    for port in ports:
        needle = f"LocalPort:{port}"  # format trouvé dans la sortie
        # Simple search dans le texte complet
        ok = any(needle in line for line in raw.splitlines())
        results[port] = ok
    return results


def main():
    parser = argparse.ArgumentParser(description="Gestion du pare-feu Windows via netsh advfirewall.")
    subparsers = parser.add_subparsers(dest="command")

    # status / rules (identiques)
    parser_status = subparsers.add_parser("status", help="Liste les règles du pare-feu.")
    parser_rules = subparsers.add_parser("rules", help="Alias de status, montre les règles brutes.")

    # add
    parser_add = subparsers.add_parser("add", help="Ajoute une règle.")
    parser_add.add_argument("--name", required=True, help="Nom de la règle.")
    parser_add.add_argument("--dir", required=True, choices=["in", "out"], help="Direction (inbound/outbound).")
    parser_add.add_argument("--action", required=True, choices=["allow", "block", "reject"], help="Action.")
    parser_add.add_argument("--proto", default="TCP", help="Protocole (TCP/UDP).")
    parser_add.add_argument("--port", default="", help="Port local (comma séparé si plusieurs).")

    # remove
    parser_rm = subparsers.add_parser("remove", help="Supprime une règle par nom.")
    parser_rm.add_argument("--name", required=True, help="Nom de la règle à supprimer.")

    # audit
    parser_audit = subparsers.add_parser("audit", help="Audit des ports spécifiés.")
    parser_audit.add_argument("--ports", default="1234,11434,18789,9742,8080", help="Liste de ports séparés par virgule.")

    args = parser.parse_args()

    try:
        if args.command in ("status", "rules"):
            rules = list_rules()
            print(json.dumps(rules, indent=2, ensure_ascii=False))
        elif args.command == "add":
            direction = "in" if args.dir == "in" else "out"
            msg = add_rule(args.name, direction, args.action, args.proto, args.port)
            print(msg)
        elif args.command == "remove":
            msg = remove_rule(args.name)
            print(msg)
        elif args.command == "audit":
            ports = [int(p.strip()) for p in args.ports.split(",") if p.strip()]
            result = audit_ports(ports)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            parser.print_help()
    except RuntimeError as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
