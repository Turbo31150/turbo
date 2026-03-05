#!/usr/bin/env python3
"""decision_engine.py

Moteur de decision autonome pour JARVIS.

Evalue des situations systeme contre un ensemble de regles integrees,
choisit la meilleure action, et enregistre chaque decision avec un score
de confiance dans une base SQLite.

Regles integrees :
  - GPU chaud (>80C)   -> alerte + reduction de charge
  - Disque faible (<10GB) -> nettoyage automatique
  - API down           -> redemarrage du service
  - CPU eleve (>90%)   -> kill processus zombies

CLI :
  --decide SITUATION   : evaluer une situation et prendre une decision
  --options            : lister toutes les regles disponibles
  --history            : afficher l'historique des decisions
  --explain ID         : expliquer une decision passee par son ID
  --rules              : afficher les regles du moteur en detail

Sortie JSON exclusivement. Stdlib uniquement.
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Base de donnees dans dev/data/
DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "decisions.db"

# Seuils par defaut
GPU_TEMP_THRESHOLD = 80     # °C
DISK_FREE_THRESHOLD = 10    # GB
CPU_THRESHOLD = 90          # %

# ---------------------------------------------------------------------------
# Regles integrees du moteur de decision
# ---------------------------------------------------------------------------

RULES = [
    {
        "id": "gpu_hot",
        "name": "GPU surchauffe",
        "description": "Temperature GPU superieure a 80°C detectee",
        "keywords": ["gpu", "chaud", "hot", "temperature", "thermal", "surchauffe", "overheat"],
        "condition": "gpu_temperature > 80°C",
        "actions": [
            {"action": "alert_telegram", "description": "Envoyer alerte Telegram", "priority": 1},
            {"action": "reduce_load", "description": "Reduire la charge GPU (migrer taches vers M2/OL1)", "priority": 2},
            {"action": "throttle_models", "description": "Limiter le debit des modeles actifs", "priority": 3},
        ],
        "confidence": 0.95,
        "severity": "critical",
    },
    {
        "id": "disk_low",
        "name": "Espace disque faible",
        "description": "Espace disque libre inferieur a 10 GB",
        "keywords": ["disque", "disk", "espace", "space", "stockage", "storage", "plein", "full"],
        "condition": "disk_free < 10 GB",
        "actions": [
            {"action": "cleanup_temp", "description": "Nettoyer les fichiers temporaires", "priority": 1},
            {"action": "cleanup_logs", "description": "Purger les anciens logs (>7j)", "priority": 2},
            {"action": "cleanup_cache", "description": "Vider les caches LM Studio / Ollama", "priority": 3},
            {"action": "alert_user", "description": "Notifier l'utilisateur", "priority": 4},
        ],
        "confidence": 0.90,
        "severity": "warning",
    },
    {
        "id": "api_down",
        "name": "API inaccessible",
        "description": "Un service API du cluster ne repond plus",
        "keywords": ["api", "down", "offline", "service", "crash", "timeout", "connexion", "connection"],
        "condition": "service_health_check == failed",
        "actions": [
            {"action": "restart_service", "description": "Redemarrer le service concerne", "priority": 1},
            {"action": "failover", "description": "Basculer vers le noeud de secours", "priority": 2},
            {"action": "alert_telegram", "description": "Envoyer alerte Telegram", "priority": 3},
        ],
        "confidence": 0.88,
        "severity": "high",
    },
    {
        "id": "high_cpu",
        "name": "CPU sature",
        "description": "Utilisation CPU superieure a 90%",
        "keywords": ["cpu", "processeur", "charge", "load", "saturation", "zombie", "process", "lent", "slow"],
        "condition": "cpu_usage > 90%",
        "actions": [
            {"action": "kill_zombies", "description": "Terminer les processus zombies", "priority": 1},
            {"action": "reduce_parallelism", "description": "Reduire le parallelisme des agents", "priority": 2},
            {"action": "defer_tasks", "description": "Reporter les taches non-critiques", "priority": 3},
        ],
        "confidence": 0.85,
        "severity": "warning",
    },
    {
        "id": "memory_pressure",
        "name": "Memoire insuffisante",
        "description": "La RAM disponible est inferieure a 2 GB",
        "keywords": ["ram", "memoire", "memory", "swap", "oom", "insuffisante"],
        "condition": "available_ram < 2 GB",
        "actions": [
            {"action": "unload_models", "description": "Decharger les modeles inutilises de la VRAM/RAM", "priority": 1},
            {"action": "gc_collect", "description": "Forcer le garbage collector Python", "priority": 2},
            {"action": "restart_heavy", "description": "Redemarrer les processus les plus gourmands", "priority": 3},
        ],
        "confidence": 0.82,
        "severity": "high",
    },
    {
        "id": "network_latency",
        "name": "Latence reseau elevee",
        "description": "Latence reseau anormalement elevee entre les noeuds",
        "keywords": ["reseau", "network", "latence", "latency", "lent", "ping", "timeout"],
        "condition": "avg_latency > 500ms",
        "actions": [
            {"action": "switch_local", "description": "Prioriser les modeles locaux (M1, OL1)", "priority": 1},
            {"action": "check_routes", "description": "Verifier les routes reseau", "priority": 2},
            {"action": "alert_user", "description": "Notifier l'utilisateur", "priority": 3},
        ],
        "confidence": 0.78,
        "severity": "warning",
    },
    {
        "id": "model_degraded",
        "name": "Qualite modele degradee",
        "description": "Un modele IA retourne des reponses de qualite inferieure",
        "keywords": ["modele", "model", "qualite", "quality", "degrade", "erreur", "error", "hallucination"],
        "condition": "response_quality_score < 0.5",
        "actions": [
            {"action": "switch_model", "description": "Basculer vers un modele alternatif", "priority": 1},
            {"action": "reload_model", "description": "Recharger le modele (poids corrompus ?)", "priority": 2},
            {"action": "log_incident", "description": "Enregistrer l'incident pour analyse", "priority": 3},
        ],
        "confidence": 0.75,
        "severity": "warning",
    },
]

# ---------------------------------------------------------------------------
# Base de donnees SQLite
# ---------------------------------------------------------------------------

def _ensure_db_dir():
    """Cree le repertoire data/ s'il n'existe pas."""
    DB_DIR.mkdir(parents=True, exist_ok=True)


def _get_conn() -> sqlite3.Connection:
    """Retourne une connexion SQLite initialisee."""
    _ensure_db_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection):
    """Cree les tables si elles n'existent pas encore."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT    NOT NULL,
            situation   TEXT    NOT NULL,
            rule_id     TEXT    NOT NULL,
            rule_name   TEXT    NOT NULL,
            action      TEXT    NOT NULL,
            confidence  REAL    NOT NULL,
            severity    TEXT    NOT NULL,
            reasoning   TEXT    NOT NULL,
            outcome     TEXT    DEFAULT 'pending'
        )
    """)
    conn.commit()

# ---------------------------------------------------------------------------
# Moteur d'evaluation
# ---------------------------------------------------------------------------

def _match_rule(situation: str) -> list:
    """Trouve les regles correspondant a la situation decrite.

    Compare les mots-cles de chaque regle avec la situation (insensible
    a la casse).  Retourne la liste des regles triees par nombre de
    correspondances decroissant.
    """
    situation_lower = situation.lower()
    scored = []
    for rule in RULES:
        # Comptage des mots-cles presents dans la situation
        hits = sum(1 for kw in rule["keywords"] if kw in situation_lower)
        if hits > 0:
            scored.append((hits, rule))
    # Tri par nombre de hits (desc) puis par confiance (desc)
    scored.sort(key=lambda x: (x[0], x[1]["confidence"]), reverse=True)
    return [r for _, r in scored]


def _build_reasoning(situation: str, rule: dict) -> str:
    """Construit une explication textuelle de la decision."""
    matched_kw = [kw for kw in rule["keywords"] if kw in situation.lower()]
    return (
        f"Situation analysee : '{situation}'. "
        f"Regle '{rule['name']}' declenchee (mots-cles : {', '.join(matched_kw)}). "
        f"Condition : {rule['condition']}. "
        f"Action recommandee : {rule['actions'][0]['description']} "
        f"(confiance {rule['confidence']:.0%}, severite {rule['severity']})."
    )


def decide(situation: str) -> dict:
    """Evalue une situation, choisit la meilleure action, enregistre."""
    matching = _match_rule(situation)

    if not matching:
        # Aucune regle ne correspond — decision par defaut
        result = {
            "status": "no_match",
            "situation": situation,
            "message": "Aucune regle ne correspond a cette situation.",
            "suggestion": "Decrire la situation avec des termes comme : gpu, disque, api, cpu, ram, reseau, modele.",
            "available_rules": [r["id"] for r in RULES],
        }
        return result

    # Prendre la meilleure regle
    best = matching[0]
    primary_action = best["actions"][0]
    reasoning = _build_reasoning(situation, best)

    # Enregistrer la decision en base
    conn = _get_conn()
    cur = conn.cursor()
    ts = datetime.utcnow().isoformat()
    cur.execute(
        """INSERT INTO decisions (ts, situation, rule_id, rule_name, action, confidence, severity, reasoning)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (ts, situation, best["id"], best["name"],
         primary_action["action"], best["confidence"],
         best["severity"], reasoning),
    )
    decision_id = cur.lastrowid
    conn.commit()
    conn.close()

    # Construire le resultat
    result = {
        "status": "decided",
        "decision_id": decision_id,
        "timestamp": ts,
        "situation": situation,
        "rule": {
            "id": best["id"],
            "name": best["name"],
            "severity": best["severity"],
        },
        "action": {
            "primary": primary_action["action"],
            "description": primary_action["description"],
            "alternatives": [
                {"action": a["action"], "description": a["description"]}
                for a in best["actions"][1:]
            ],
        },
        "confidence": best["confidence"],
        "reasoning": reasoning,
        "other_matches": [
            {"rule_id": r["id"], "rule_name": r["name"], "confidence": r["confidence"]}
            for r in matching[1:]
        ],
    }
    return result

# ---------------------------------------------------------------------------
# Commandes CLI
# ---------------------------------------------------------------------------

def cmd_decide(situation: str):
    """Evalue une situation et retourne la decision en JSON."""
    result = decide(situation)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_options():
    """Liste toutes les regles disponibles."""
    options = []
    for rule in RULES:
        options.append({
            "id": rule["id"],
            "name": rule["name"],
            "description": rule["description"],
            "severity": rule["severity"],
            "confidence": rule["confidence"],
            "keywords": rule["keywords"],
            "nb_actions": len(rule["actions"]),
        })
    result = {
        "status": "ok",
        "total_rules": len(RULES),
        "rules": options,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_history():
    """Affiche l'historique des decisions prises."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, ts, situation, rule_id, rule_name, action, confidence, severity, outcome
        FROM decisions
        ORDER BY id DESC
        LIMIT 50
    """)
    rows = cur.fetchall()
    conn.close()

    decisions = []
    for row in rows:
        decisions.append({
            "id": row["id"],
            "timestamp": row["ts"],
            "situation": row["situation"],
            "rule_id": row["rule_id"],
            "rule_name": row["rule_name"],
            "action": row["action"],
            "confidence": row["confidence"],
            "severity": row["severity"],
            "outcome": row["outcome"],
        })

    result = {
        "status": "ok",
        "total": len(decisions),
        "decisions": decisions,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_explain(decision_id: int):
    """Explique une decision passee en detail."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        result = {
            "status": "error",
            "message": f"Aucune decision trouvee avec l'ID {decision_id}.",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # Retrouver la regle correspondante pour les details complets
    rule_detail = None
    for rule in RULES:
        if rule["id"] == row["rule_id"]:
            rule_detail = rule
            break

    result = {
        "status": "ok",
        "decision": {
            "id": row["id"],
            "timestamp": row["ts"],
            "situation": row["situation"],
            "outcome": row["outcome"],
        },
        "rule_applied": {
            "id": row["rule_id"],
            "name": row["rule_name"],
            "condition": rule_detail["condition"] if rule_detail else "inconnue",
            "severity": row["severity"],
        },
        "action_taken": {
            "action": row["action"],
            "description": rule_detail["actions"][0]["description"] if rule_detail else "inconnue",
            "alternatives": [
                {"action": a["action"], "description": a["description"]}
                for a in (rule_detail["actions"][1:] if rule_detail else [])
            ],
        },
        "confidence": row["confidence"],
        "reasoning": row["reasoning"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_rules():
    """Affiche les regles en detail avec toutes les actions possibles."""
    rules_detail = []
    for rule in RULES:
        rules_detail.append({
            "id": rule["id"],
            "name": rule["name"],
            "description": rule["description"],
            "condition": rule["condition"],
            "severity": rule["severity"],
            "confidence": rule["confidence"],
            "keywords": rule["keywords"],
            "actions": rule["actions"],
        })
    result = {
        "status": "ok",
        "engine": "JARVIS Decision Engine v1.0",
        "total_rules": len(RULES),
        "severity_levels": ["critical", "high", "warning"],
        "rules": rules_detail,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Moteur de decision autonome JARVIS — evalue des situations et choisit la meilleure action.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Exemples :
  python decision_engine.py --decide "Le GPU est tres chaud, temperature elevee"
  python decision_engine.py --decide "API M2 down, timeout connexion"
  python decision_engine.py --decide "Disque C presque plein, espace insuffisant"
  python decision_engine.py --options
  python decision_engine.py --history
  python decision_engine.py --explain 1
  python decision_engine.py --rules
""",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--decide", type=str, metavar="SITUATION",
                       help="Evaluer une situation et prendre une decision")
    group.add_argument("--options", action="store_true",
                       help="Lister les regles disponibles")
    group.add_argument("--history", action="store_true",
                       help="Afficher l'historique des decisions")
    group.add_argument("--explain", type=int, metavar="ID",
                       help="Expliquer une decision passee par son ID")
    group.add_argument("--rules", action="store_true",
                       help="Afficher les regles du moteur en detail")

    args = parser.parse_args()

    if args.decide:
        cmd_decide(args.decide)
    elif args.options:
        cmd_options()
    elif args.history:
        cmd_history()
    elif args.explain is not None:
        cmd_explain(args.explain)
    elif args.rules:
        cmd_rules()


if __name__ == "__main__":
    main()
