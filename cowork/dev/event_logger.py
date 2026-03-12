#!/usr/bin/env python3
"""event_logger.py

Centralisateur d'évènements JARVIS.

Fonctionnalités :
* **Mode serveur** (`--server`) : écoute UDP sur le port 9998, accepte des paquets JSON contenant
  ``{"source": "nom", "level": "info|warning|critical", "message": "texte"}``
  Il insère chaque évènement dans une base SQLite ``events.db`` (table ``events`` : id, ts, source, level, message).
* **Mode client** (`--send source level "message"`) : envoie le JSON au serveur local (UDP 9998).
* **--tail** : affiche les 20 derniers évènements (ou ``--tail N`` pour un nombre personnalisé).
* **--stats** : compte les évènements par source et par niveau, affiche un petit tableau.
* **--history** (option alternative) : montre tout l’historique complet (trié par ts).

Le script n’utilise que la bibliothèque standard : ``socket``, ``json``, ``sqlite3``, ``argparse``, ``datetime`` et ``threading``.
"""

import argparse
import json
import sqlite3
import socket
import sys
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 9998
DB_PATH = Path(__file__).with_name("events.db")
MAX_TAIL = 20

# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

def init_db(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            source TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL
        )
        """
    )
    conn.commit()

def insert_event(conn: sqlite3.Connection, source: str, level: str, message: str):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO events (ts, source, level, message) VALUES (?,?,?,?)",
        (datetime.utcnow().isoformat() + "Z", source, level, message),
    )
    conn.commit()

def fetch_tail(conn: sqlite3.Connection, n: int = MAX_TAIL):
    cur = conn.cursor()
    cur.execute("SELECT ts, source, level, message FROM events ORDER BY id DESC LIMIT ?", (n,))
    rows = cur.fetchall()
    # reverse to chronological order
    return rows[::-1]

def fetch_stats(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT source, COUNT(*) FROM events GROUP BY source")
    by_source = dict(cur.fetchall())
    cur.execute("SELECT level, COUNT(*) FROM events GROUP BY level")
    by_level = dict(cur.fetchall())
    return by_source, by_level

def fetch_all(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT ts, source, level, message FROM events ORDER BY id")
    return cur.fetchall()

# ---------------------------------------------------------------------------
# UDP server – runs in a thread
# ---------------------------------------------------------------------------

def server_loop(stop_event: threading.Event):
    print(f"[event_logger] UDP server listening on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((HOST, PORT))
        conn = sqlite3.connect(str(DB_PATH))
        init_db(conn)
        while not stop_event.is_set():
            try:
                s.settimeout(1.0)
                data, addr = s.recvfrom(4096)
                if not data:
                    continue
                try:
                    payload = json.loads(data.decode())
                    source = payload.get('source', 'unknown')
                    level = payload.get('level', 'info')
                    message = payload.get('message', '')
                    insert_event(conn, source, level, message)
                except json.JSONDecodeError:
                    print(f"[event_logger] Received invalid JSON from {addr}")
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[event_logger] Server error: {e}", file=sys.stderr)
        conn.close()
    print("[event_logger] Server stopped.")

# ---------------------------------------------------------------------------
# Client helper – send a single event
# ---------------------------------------------------------------------------
def send_event(source: str, level: str, message: str):
    payload = json.dumps({"source": source, "level": level, "message": message}).encode()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(payload, (HOST, PORT))
    print(f"[event_logger] Event sent: [{level}] {source} – {message}")

# ---------------------------------------------------------------------------
# CLI handling
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Hub centralisé d'évènements JARVIS (UDP, SQLite).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--server", action="store_true", help="Lancer le serveur UDP qui écoute les évènements")
    group.add_argument("--send", nargs=3, metavar=("SOURCE", "LEVEL", "MESSAGE"),
                       help="Envoyer un évènement au serveur (exemple: --send myscript warning \"quelque chose\"")
    group.add_argument("--tail", nargs='?', const=MAX_TAIL, type=int,
                       help="Afficher les derniers N évènements (défaut 20)")
    group.add_argument("--stats", action="store_true", help="Statistiques par source et par niveau")
    group.add_argument("--history", action="store_true", help="Afficher tout l'historique des évènements")
    args = parser.parse_args()

    if args.server:
        stop_event = threading.Event()
        try:
            server_loop(stop_event)
        except KeyboardInterrupt:
            stop_event.set()
    elif args.send:
        src, lvl, msg = args.send
        send_event(src, lvl, msg)
    elif args.tail is not None:
        conn = sqlite3.connect(str(DB_PATH))
        init_db(conn)
        rows = fetch_tail(conn, args.tail)
        conn.close()
        for ts, src, lvl, msg in rows:
            print(f"{ts} | [{lvl}] {src}: {msg}")
    elif args.stats:
        conn = sqlite3.connect(str(DB_PATH))
        init_db(conn)
        by_src, by_lvl = fetch_stats(conn)
        conn.close()
        print("=== Évènements par source ===")
        for src, cnt in sorted(by_src.items(), key=lambda x: -x[1]):
            print(f"{src}: {cnt}")
        print("\n=== Évènements par niveau ===")
        for lvl, cnt in sorted(by_lvl.items(), key=lambda x: -x[1]):
            print(f"{lvl}: {cnt}")
    elif args.history:
        conn = sqlite3.connect(str(DB_PATH))
        init_db(conn)
        rows = fetch_all(conn)
        conn.close()
        for ts, src, lvl, msg in rows:
            print(f"{ts} | [{lvl}] {src}: {msg}")

if __name__ == "__main__":
    main()
