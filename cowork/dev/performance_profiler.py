#!/usr/bin/env python3
"""performance_profiler.py

Profilage de performance pour les scripts du répertoire ``dev/``.

Fonctionnalités :
* **--profile script.py** – exécute le script avec ``python`` et mesure :
    - temps d'exécution (seconds, à la milliseconde)
    - mémoire maximale utilisée (MiB) – via ``psutil`` si disponible, sinon 0
    - taille du flux stdout et stderr (bytes) – permet d’estimer l’I/O.
* **--all** – profile tous les fichiers ``*.py`` présents dans le même répertoire.
* **--report** – affiche les 10 scripts les plus lents (triés par temps d’exécution),
  avec les métriques mesurées.
* Les résultats sont persistés dans SQLite ``profiler.db`` (table ``runs``).

Le script utilise uniquement la bibliothèque standard : ``subprocess``, ``time``,
``sqlite3``, ``argparse`` et, si disponible, ``psutil`` pour la mesure de la
mémoire.
"""

import argparse
import os
import subprocess
import sys
import sqlite3
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional psutil for memory profiling
# ---------------------------------------------------------------------------
try:
    import psutil  # type: ignore
except Exception:
    psutil = None

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent  # dev/ folder
DB_PATH = BASE_DIR / "profiler.db"

# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

def init_db(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            script TEXT NOT NULL,
            ts TEXT NOT NULL,
            exec_time REAL NOT NULL,
            max_mem_mb REAL NOT NULL,
            stdout_bytes INTEGER NOT NULL,
            stderr_bytes INTEGER NOT NULL
        )
        """
    )
    conn.commit()

def insert_run(conn: sqlite3.Connection, script: str, exec_time: float, max_mem_mb: float, out_len: int, err_len: int):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO runs (script, ts, exec_time, max_mem_mb, stdout_bytes, stderr_bytes) VALUES (?,?,?,?,?,?)",
        (script, datetime.utcnow().isoformat() + "Z", exec_time, max_mem_mb, out_len, err_len),
    )
    conn.commit()

def fetch_all(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT script, exec_time, max_mem_mb, stdout_bytes, stderr_bytes FROM runs ORDER BY exec_time DESC")
    return cur.fetchall()

# ---------------------------------------------------------------------------
# Profilage d'un script
# ---------------------------------------------------------------------------

def profile_script(script_path: Path):
    if not script_path.is_file():
        print(f"[performance_profiler] Script introuvable : {script_path}", file=sys.stderr)
        return None
    # Start subprocess
    start = time.time()
    proc = subprocess.Popen([sys.executable, str(script_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # If psutil is available, monitor memory usage
    max_mem = 0.0
    if psutil:
        p = psutil.Process(proc.pid)
        while proc.poll() is None:
            try:
                mem = p.memory_info().rss / (1024 * 1024)  # MiB
                if mem > max_mem:
                    max_mem = mem
            except Exception:
                pass
            time.sleep(0.05)
    # Wait for completion and capture output
    out, err = proc.communicate()
    end = time.time()
    exec_time = end - start
    # If we didn't monitor memory, try a final check after process ended
    if psutil and max_mem == 0.0:
        try:
            p = psutil.Process(proc.pid)
            max_mem = p.memory_info().rss / (1024 * 1024)
        except Exception:
            max_mem = 0.0
    return {
        "exec_time": exec_time,
        "max_mem_mb": max_mem,
        "stdout_bytes": len(out),
        "stderr_bytes": len(err),
    }

# ---------------------------------------------------------------------------
# CLI handling
# ---------------------------------------------------------------------------

def cmd_profile(script_name: str):
    script_path = BASE_DIR / script_name
    result = profile_script(script_path)
    if not result:
        return
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    insert_run(conn, script_name, result["exec_time"], result["max_mem_mb"], result["stdout_bytes"], result["stderr_bytes"])
    conn.close()
    print(f"[performance_profiler] Profiling de {script_name} terminé :")
    print(f"  Temps d'exécution : {result['exec_time']:.3f}s")
    print(f"  Mémoire max : {result['max_mem_mb']:.1f} MiB")
    print(f"  stdout : {result['stdout_bytes']} bytes, stderr : {result['stderr_bytes']} bytes")

def cmd_all():
    py_files = [p.name for p in BASE_DIR.iterdir() if p.suffix == ".py" and p.name != Path(__file__).name]
    for script in py_files:
        print(f"[performance_profiler] Profilage de {script} …")
        cmd_profile(script)

def cmd_report():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    rows = fetch_all(conn)
    conn.close()
    if not rows:
        print("[performance_profiler] Aucun résultat de profilage disponible.")
        return
    print("=== Top 10 scripts les plus lents ===")
    for i, (script, t, mem, outb, errb) in enumerate(rows[:10], 1):
        print(f"{i}. {script} – {t:.3f}s, Mémoire : {mem:.1f} MiB, stdout : {outb} B, stderr : {errb} B")

def main():
    parser = argparse.ArgumentParser(description="Profiler de performance pour les scripts JARVIS (dev/).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--profile", metavar="SCRIPT", help="Profiler le script indiqué (exemple: --profile auto_healer.py)")
    group.add_argument("--all", action="store_true", help="Profiler tous les scripts .py du répertoire dev/")
    group.add_argument("--report", action="store_true", help="Afficher le top 10 des scripts les plus lents")
    args = parser.parse_args()

    if args.profile:
        cmd_profile(args.profile)
    elif args.all:
        cmd_all()
    elif args.report:
        cmd_report()

if __name__ == "__main__":
    main()
