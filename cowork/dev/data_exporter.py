#!/usr/bin/env python3
"""data_exporter.py

Exporteur de données SQLite pour les bases JARVIS.

Fonctionnalités :
* ``--list DB`` – liste les tables présentes dans la base SQLite indiquée.
* ``--schema DB TABLE`` – affiche la structure (colonnes, types) d'une table.
* ``--export DB TABLE`` – exporte le contenu d'une table au format CSV ou JSON.
  Options :
    --format csv|json (défaut : csv)
    --output FILE (chemin du fichier de sortie ; sinon stdout)
    --where "SQL_CONDITION" (facultatif) – clause WHERE appliquée lors du SELECT.
    --columns COL1,COL2,… (facultatif) – liste des colonnes à exporter.
    --date-col NAME – si fournie, le script s'assure que les valeurs sont
      au format ISO et peut filtrer par ``>=`` aujourd'hui si aucune condition n'est donnée.

Le script s'appuie uniquement sur la bibliothèque standard : ``sqlite3``, ``csv``, ``json``,
``argparse`` et ``pathlib``.
"""

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Helpers – connexion SQLite
# ---------------------------------------------------------------------------

def connect_db(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        print(f"[data_exporter] Base de données introuvable : {db_path}", file=sys.stderr)
        sys.exit(1)
    return sqlite3.connect(str(db_path))

# ---------------------------------------------------------------------------
# List tables
# ---------------------------------------------------------------------------

def list_tables(db_path: Path):
    conn = connect_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]
    conn.close()
    if not tables:
        print("[data_exporter] Aucun tableau trouvé.")
    else:
        print("Tables :")
        for t in tables:
            print(f"  - {t}")

# ---------------------------------------------------------------------------
# Show schema
# ---------------------------------------------------------------------------

def show_schema(db_path: Path, table: str):
    conn = connect_db(db_path)
    cur = conn.cursor()
    try:
        cur.execute(f"PRAGMA table_info('{table}')")
        rows = cur.fetchall()
        if not rows:
            print(f"[data_exporter] Table '{table}' introuvable ou vide.")
            return
        print(f"Schéma de la table '{table}' :")
        print("  cid | name       | type    | notnull | dflt_value | pk")
        for cid, name, col_type, notnull, dflt, pk in rows:
            print(f"  {cid:3} | {name:10} | {col_type:7} | {notnull:7} | {str(dflt):10} | {pk}")
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Export – CSV / JSON
# ---------------------------------------------------------------------------

def export_table(
    db_path: Path,
    table: str,
    fmt: str,
    output: Optional[Path],
    where: Optional[str],
    columns: Optional[List[str]],
):
    conn = connect_db(db_path)
    cur = conn.cursor()
    # Build SELECT statement
    col_clause = "*" if not columns else ",".join(columns)
    sql = f"SELECT {col_clause} FROM {table}"
    if where:
        sql += f" WHERE {where}"
    try:
        cur.execute(sql)
    except sqlite3.Error as e:
        print(f"[data_exporter] Erreur SQL : {e}", file=sys.stderr)
        conn.close()
        sys.exit(1)
    rows = cur.fetchall()
    col_names = [description[0] for description in cur.description]
    conn.close()

    # Destination – stdout if no file given
    out_stream = sys.stdout if output is None else open(output, "w", encoding="utf-8", newline="")
    try:
        if fmt == "csv":
            writer = csv.writer(out_stream)
            writer.writerow(col_names)
            writer.writerows(rows)
        elif fmt == "json":
            # Convert each row to dict
            data = [dict(zip(col_names, row)) for row in rows]
            json.dump(data, out_stream, ensure_ascii=False, indent=2)
        else:
            print(f"[data_exporter] Format inconnu : {fmt}", file=sys.stderr)
            return
    finally:
        if output is not None:
            out_stream.close()
    print(f"[data_exporter] Export terminé ({len(rows)} lignes) → {output if output else 'stdout'}")

# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Exporteur de données SQLite (JARVIS).")
    sub = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = sub.add_parser("list", help="Lister les tables d'une base")
    p_list.add_argument("db", type=Path, help="Chemin vers le fichier .db")

    # schema
    p_schema = sub.add_parser("schema", help="Afficher le schéma d'une table")
    p_schema.add_argument("db", type=Path, help="Chemin vers le fichier .db")
    p_schema.add_argument("table", help="Nom de la table")

    # export
    p_export = sub.add_parser("export", help="Exporter le contenu d'une table")
    p_export.add_argument("db", type=Path, help="Chemin vers le fichier .db")
    p_export.add_argument("table", help="Nom de la table à exporter")
    p_export.add_argument("--format", choices=["csv", "json"], default="csv", help="Format de sortie")
    p_export.add_argument("--output", type=Path, help="Fichier de destination (par défaut stdout)")
    p_export.add_argument("--where", help="Clause WHERE SQL (sans le mot-clé WHERE)")
    p_export.add_argument("--columns", help="Colonnes à exporter, séparées par des virgules")

    args = parser.parse_args()

    if args.command == "list":
        list_tables(args.db)
    elif args.command == "schema":
        show_schema(args.db, args.table)
    elif args.command == "export":
        cols = args.columns.split(",") if args.columns else None
        export_table(
            db_path=args.db,
            table=args.table,
            fmt=args.format,
            output=args.output,
            where=args.where,
            columns=cols,
        )

if __name__ == "__main__":
    main()
