#!/usr/bin/env python3
"""node_balancer.py — Équilibre la charge du cluster IA.

CLI:
  --balance   : Analyse les métriques et déclenche des actions de rééquilibrage.
  --status    : Affiche l'état actuel des nœuds (temp, VRAM, CPU).
  --migrate   : Force la migration d'une tâche d'un nœud surchargé vers un autre.
  --report    : Génère un rapport JSON des actions récentes enregistrées.
  --help      : Affiche l'aide.

Le script utilise uniquement la stdlib et stocke les logs dans
`dev/data/balancer.db`.
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from typing import Dict, List, Tuple

# Configuration des nœuds du cluster
NODES = {
    "M1": {"gpus": 6, "vram_gb": 46},
    "M2": {"gpus": 3, "vram_gb": 24},
    "M3": {"gpus": 1, "vram_gb": 8},
    "OL1": {"cloud": True},
}

# Seuils de déclenchement
THRESHOLDS = {
    "temp_c": 75,   # >75°C → décharger
    "vram_pct": 90, # >90% d'utilisation → migrer
    "cpu_pct": 95,  # >95% → distribuer
}

DB_PATH = os.path.join("dev", "data", "balancer.db")

def _ensure_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT
        )
        """
    )
    conn.commit()
    return conn

def log_action(action: str, details: Dict = None) -> None:
    conn = _ensure_db()
    cur = conn.cursor()
    ts = datetime.utcnow().isoformat() + "Z"
    cur.execute(
        "INSERT INTO actions (ts, action, details) VALUES (?,?,?)",
        (ts, action, json.dumps(details) if details else None),
    )
    conn.commit()
    conn.close()

def get_recent_actions(limit: int = 20) -> List[Dict]:
    conn = _ensure_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT ts, action, details FROM actions ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"timestamp": r[0], "action": r[1], "details": json.loads(r[2]) if r[2] else None}
        for r in rows
    ]

# ---------------------------------------------------------------------------
# Métriques factices – dans un vrai environnement on récupérerait les stats
# via nvidia‑smi, wmi ou des appels REST aux agents de monitoring.
# ---------------------------------------------------------------------------

def mock_metrics() -> Dict[str, Dict[str, float]]:
    """Retourne des métriques factices pour chaque nœud.
    Les valeurs changent légèrement à chaque appel pour simuler une charge.
    """
    import random
    metrics = {}
    for node in NODES:
        # valeurs aléatoires autour de niveaux raisonnables
        temp = random.uniform(50, 85) if not NODES[node].get("cloud") else None
        vram = random.uniform(30, 95) if not NODES[node].get("cloud") else None
        cpu = random.uniform(20, 98)
        metrics[node] = {
            "temp_c": round(temp, 1) if temp is not None else None,
            "vram_pct": round(vram, 1) if vram is not None else None,
            "cpu_pct": round(cpu, 1),
        }
    return metrics

def display_status(metrics: Dict[str, Dict[str, float]]) -> None:
    print("État des nœuds du cluster IA :")
    for node, data in metrics.items():
        parts = []
        if data["temp_c"] is not None:
            parts.append(f"Temp: {data['temp_c']}°C")
        if data["vram_pct"] is not None:
            parts.append(f"VRAM: {data['vram_pct']}%")
        parts.append(f"CPU: {data['cpu_pct']}%")
        print(f"  {node:4}: " + ", ".join(parts))

def find_overloaded(metrics: Dict[str, Dict[str, float]]) -> List[Tuple[str, List[str]]]:
    """Renvoie la liste des nœuds avec leurs problèmes détectés.
    Exemple: [("M2", ["temp", "vram"]), ...]
    """
    overloaded = []
    for node, data in metrics.items():
        problems = []
        if data["temp_c"] is not None and data["temp_c"] > THRESHOLDS["temp_c"]:
            problems.append("temp")
        if data["vram_pct"] is not None and data["vram_pct"] > THRESHOLDS["vram_pct"]:
            problems.append("vram")
        if data["cpu_pct"] > THRESHOLDS["cpu_pct"]:
            problems.append("cpu")
        if problems:
            overloaded.append((node, problems))
    return overloaded

def select_target(overloaded_node: str, metrics: Dict[str, Dict[str, float]]) -> str:
    """Choisit le nœud le moins chargé parmi ceux qui ne sont pas surchargés.
    On privilégie les nœuds avec le plus de VRAM disponible.
    """
    candidates = []
    for node, data in metrics.items():
        if node == overloaded_node:
            continue
        # Exclure les nœuds déjà en surcharge
        if any([
            data["temp_c"] and data["temp_c"] > THRESHOLDS["temp_c"],
            data["vram_pct"] and data["vram_pct"] > THRESHOLDS["vram_pct"],
            data["cpu_pct"] > THRESHOLDS["cpu_pct"],
        ]):
            continue
        # Score basé sur la VRAM libre (ou CPU si cloud)
        score = 0
        if data["vram_pct"] is not None:
            score = 100 - data["vram_pct"]
        else:
            # cloud node – on considère qu'il a capacité illimitée
            score = 100
        candidates.append((score, node))
    if not candidates:
        return None
    # Le plus grand score = le plus de ressources disponibles
    candidates.sort(reverse=True)
    return candidates[0][1]

def perform_migration(src: str, dst: str) -> None:
    # Dans un vrai système on invoquerait le dispatcher ou un script de migration.
    # Ici on ne fait qu'enregistrer l'action.
    log_action(
        "migrate",
        {"from": src, "to": dst, "time": datetime.utcnow().isoformat() + "Z"},
    )
    print(f"Migration simulée de {src} → {dst}")

def balance() -> None:
    metrics = mock_metrics()
    overloaded = find_overloaded(metrics)
    if not overloaded:
        print("Pas de surcharge détectée. Le cluster est équilibré.")
        log_action("balance", {"status": "balanced"})
        return
    for node, issues in overloaded:
        target = select_target(node, metrics)
        if target:
            print(f"Nœud {node} surchargé ({', '.join(issues)}). Migration vers {target}.")
            perform_migration(node, target)
        else:
            print(f"Nœud {node} surchargé ({', '.join(issues)}). Aucun nœud cible disponible.")
            log_action("balance_failed", {"node": node, "issues": issues})
    log_action("balance", {"overloaded": overloaded})

def migrate(src: str, dst: str) -> None:
    if src not in NODES or dst not in NODES:
        print("Erreur : nœud source ou destination inconnu.")
        return
    perform_migration(src, dst)

def report() -> None:
    actions = get_recent_actions()
    print(json.dumps({"recent_actions": actions}, ensure_ascii=False, indent=2))

def main() -> None:
    parser = argparse.ArgumentParser(description="Équilibrage du cluster IA")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--balance", action="store_true", help="Analyse et rééquilibre le cluster")
    group.add_argument("--status", action="store_true", help="Affiche l’état des nœuds")
    group.add_argument("--migrate", nargs=2, metavar=("SRC", "DST"), help="Force la migration d’un nœud vers un autre")
    group.add_argument("--report", action="store_true", help="Rapport JSON des actions récentes")
    args = parser.parse_args()

    if args.balance:
        balance()
    elif args.status:
        display_status(mock_metrics())
    elif args.migrate:
        src, dst = args.migrate
        migrate(src, dst)
    elif args.report:
        report()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
