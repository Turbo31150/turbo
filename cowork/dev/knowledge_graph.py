#!/usr/bin/env python3
"""knowledge_graph.py

Batch 6.3 – Gestion d'un graphe de connaissances pour JARVIS.

Fonctionnalités :
* Stockage SQLite dans `knowledge.db` avec deux tables :
  - `entities` (id, name, type, description)
  - `relations` (id, source_id, target_id, rel_type)
* Types d'entités : person, service, model, script, database, api
* Types de relation : uses, depends_on, produces, monitors, controls
* CLI :
  --add-entity TYPE NAME [--desc DESC]
  --add-relation SRC REL_TYPE TARGET
  --query NAME            – affiche l'entité et ses relations
  --graph                 – affiche tout le graphe (textuel)
  --stats                 – compte entités / relations par type
* À la création du fichier, le graphe est pré‑rempli avec les
  éléments majeurs du système JARVIS.

Utilise uniquement la bibliothèque standard (`sqlite3`, `argparse`, `textwrap`).
"""

import argparse
import sqlite3
import sys
import textwrap
from collections import Counter
from pathlib import Path

DB_PATH = Path(__file__).with_name("knowledge.db")

# ---------------------------------------------------------------------------
# Initialisation de la base
# ---------------------------------------------------------------------------

def init_db(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL,
            description TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            rel_type TEXT NOT NULL,
            FOREIGN KEY(source_id) REFERENCES entities(id),
            FOREIGN KEY(target_id) REFERENCES entities(id)
        )
        """
    )
    conn.commit()

# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------

def add_entity(conn: sqlite3.Connection, name: str, typ: str, desc: str = ""):
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO entities (name, type, description) VALUES (?,?,?)",
            (name, typ, desc),
        )
        conn.commit()
        print(f"[knowledge] Entité ajoutée:  {name} ({typ})")
    except sqlite3.IntegrityError:
        print(f"[knowledge] Entité déjà existante : {name}")

def get_entity_id(conn: sqlite3.Connection, name: str):
    cur = conn.cursor()
    cur.execute("SELECT id FROM entities WHERE name = ?", (name,))
    row = cur.fetchone()
    return row[0] if row else None

def add_relation(conn: sqlite3.Connection, src: str, rel_type: str, tgt: str):
    src_id = get_entity_id(conn, src)
    tgt_id = get_entity_id(conn, tgt)
    if src_id is None:
        print(f"[knowledge] Source inconnue : {src}")
        return
    if tgt_id is None:
        print(f"[knowledge] Cible inconnue : {tgt}")
        return
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO relations (source_id, target_id, rel_type) VALUES (?,?,?)",
        (src_id, tgt_id, rel_type),
    )
    conn.commit()
    print(f"[knowledge] Relation ajoutée:  {src} -[{rel_type}]-> {tgt}")

def query_entity(conn: sqlite3.Connection, name: str):
    cur = conn.cursor()
    cur.execute("SELECT id, type, description FROM entities WHERE name = ?", (name,))
    row = cur.fetchone()
    if not row:
        print(f"[knowledge] Entité non trouvée : {name}")
        return
    eid, typ, desc = row
    print(f"Entité : {name}\n  Type : {typ}\n  Description : {desc or '(aucune)'}")
    # Relations sortantes
    cur.execute(
        "SELECT e2.name, r.rel_type FROM relations r JOIN entities e2 ON r.target_id = e2.id WHERE r.source_id = ?",
        (eid,)
    )
    out = cur.fetchall()
    if out:
        print("  Relations sortantes :")
        for tgt, rtype in out:
            print(f"    - [{rtype}] → {tgt}")
    # Relations entrantes
    cur.execute(
        "SELECT e1.name, r.rel_type FROM relations r JOIN entities e1 ON r.source_id = e1.id WHERE r.target_id = ?",
        (eid,)
    )
    inc = cur.fetchall()
    if inc:
        print("  Relations entrantes :")
        for src, rtype in inc:
            print(f"    - {src} -[{rtype}]-> (cible) {name}")

def display_graph(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT name, type FROM entities ORDER BY type, name")
    entities = cur.fetchall()
    print("=== Entités ===")
    for name, typ in entities:
        print(f"- {name} [{typ}]")
    print("\n=== Relations ===")
    cur.execute(
        """
        SELECT e1.name, r.rel_type, e2.name
        FROM relations r
        JOIN entities e1 ON r.source_id = e1.id
        JOIN entities e2 ON r.target_id = e2.id
        ORDER BY e1.name
        """
    )
    for src, rtype, tgt in cur.fetchall():
        print(f"{src} -[{rtype}]-> {tgt}")

def stats(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT type, COUNT(*) FROM entities GROUP BY type")
    ent_counts = cur.fetchall()
    cur.execute("SELECT rel_type, COUNT(*) FROM relations GROUP BY rel_type")
    rel_counts = cur.fetchall()
    print("=== Statistiques ===")
    print("Entités par type :")
    for typ, cnt in ent_counts:
        print(f"  {typ}: {cnt}")
    print("Relations par type :")
    for rtype, cnt in rel_counts:
        print(f"  {rtype}: {cnt}")

# ---------------------------------------------------------------------------
# Pré‑remplissage du graphe
# ---------------------------------------------------------------------------

def seed_graph(conn: sqlite3.Connection):
    # Entités majeures (type, name, description)
    entities = [
        ("person", "Franc", "Utilisateur principal"),
        ("service", "Telegram", "Bot Telegram de JARVIS"),
        ("service", "MEXC", "Plateforme de trading Futures"),
        ("model", "M1", "qwen3‑30b (réservé embedding)"),
        ("model", "M2", "deepseek‑coder (default)"),
        ("model", "OL1", "qwen3‑8b (rapide)"),
        ("service", "OpenClaw", "Orchestrateur principal"),
        ("script", "auto_healer.py", "Rotation automatique des modèles"),
        ("script", "anomaly_detector.py", "Détection d'anomalies système"),
        ("database", "etoile.db", "DB de la carte HEXA_CORE"),
        ("database", "jarvis.db", "DB interne JARVIS"),
    ]
    for typ, name, desc in entities:
        add_entity(conn, name, typ, desc)
    # Relations (src, type, tgt)
    rels = [
        ("OpenClaw", "controls", "M1"),
        ("OpenClaw", "controls", "M2"),
        ("OpenClaw", "controls", "OL1"),
        ("M2", "uses", "deepseek‑coder"),
        ("OL1", "uses", "qwen3‑8b"),
        ("auto_healer.py", "depends_on", "OpenClaw"),
        ("anomaly_detector.py", "depends_on", "OpenClaw"),
        ("Telegram", "monitors", "OpenClaw"),
        ("MEXC", "produces", "trading signals"),
        ("Franc", "uses", "Telegram"),
    ]
    for src, rtype, tgt in rels:
        add_relation(conn, src, rtype, tgt)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Graphe de connaissances JARVIS.")
    sub = parser.add_mutually_exclusive_group(required=True)
    sub.add_argument("--add-entity", nargs=2, metavar=('TYPE', 'NAME'), help="Ajouter une entité")
    sub.add_argument("--add-relation", nargs=3, metavar=('SRC', 'REL', 'TGT'), help="Ajouter une relation")
    sub.add_argument("--query", metavar='NAME', help="Interroger une entité")
    sub.add_argument("--graph", action='store_true', help="Afficher tout le graphe")
    sub.add_argument("--stats", action='store_true', help="Afficher des statistiques")
    parser.add_argument("--desc", help="Description (utilisée avec --add-entity)")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    # Seed only if database is empty (no entities)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM entities")
    if cur.fetchone()[0] == 0:
        seed_graph(conn)

    if args.add_entity:
        typ, name = args.add_entity
        add_entity(conn, name, typ, args.desc or "")
    elif args.add_relation:
        src, rel_type, tgt = args.add_relation
        add_relation(conn, src, rel_type, tgt)
    elif args.query:
        query_entity(conn, args.query)
    elif args.graph:
        display_graph(conn)
    elif args.stats:
        stats(conn)
    conn.close()

if __name__ == "__main__":
    main()
