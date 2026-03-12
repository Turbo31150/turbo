#!/usr/bin/env python3
"""system_benchmark.py

Benchmark complet du poste Windows.

Fonctionnalités :
* **CPU** – calcule les nombres premiers jusqu'à une limite (par défaut 20 000) et
  mesure le temps d'exécution.  Le score (0-100) est basé sur un temps de référence
  (ex. 2 s pour la limite donnée) ; plus rapide = score plus élevé.
* **RAM** – alloue un gros tableau (par défaut 200 MiB), le remplit, puis le libère,
  en mesurant le temps.  Le score repose sur un temps de référence similaire.
* **Disque** – crée un fichier temporaire de taille configurable (par défaut
  100 MiB), mesure le débit d'écriture puis de lecture via ``shutil``/
  ``open``.  Le score est proportionnel au débit (Mo/s) comparé à un seuil de
  référence (ex. 200 Mo/s).
* **Réseau** – télécharge un petit fichier (~1 MiB) depuis ``https://speed.hetzner.de/1MB.bin``
  (ou toute URL fiable) avec ``urllib.request`` et mesure le débit
  (Mo/s).  Le score est calculé à partir d'un débit de référence (ex. 50 Mo/s).
* Les scores (0-100) ainsi que les temps/debits bruts sont stockés dans une
  base SQLite ``benchmark.db`` (table ``runs``).
* CLI :
  - ``--run`` : exécute le benchmark complet et ajoute une ligne dans la DB.
  - ``--history`` : affiche les précédents résultats (triés par date).
  - ``--compare`` : montre les meilleures (max) scores par catégorie et le
    score moyen global.

Le script utilise uniquement la bibliothèque standard : ``time``, ``sqlite3``,
``urllib.request``, ``os`` et ``shutil``.
"""

import argparse
import os
import shutil
import sqlite3
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration des références de performance (benchmark values)
# ---------------------------------------------------------------------------
CPU_PRIME_LIMIT = 20000          # recherche de nombres premiers jusqu'à ce nombre
CPU_REF_TIME = 2.0               # secondes attendues pour la référence (score 100)

RAM_ALLOC_MB = 200               # taille à allouer en mégaoctets
RAM_REF_TIME = 0.5               # secondes attendues pour la référence

DISK_FILE_MB = 100              # taille du fichier de test disque (MiB)
DISK_REF_SPEED = 200.0           # Mo/s référence pour score 100

NETWORK_TEST_URL = "https://speed.hetzner.de/1MB.bin"  # petit fichier fiable
NETWORK_REF_SPEED = 50.0          # Mo/s référence pour score 100

DB_PATH = Path(__file__).with_name("benchmark.db")

# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

def init_db(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            cpu_time REAL,
            cpu_score INTEGER,
            ram_time REAL,
            ram_score INTEGER,
            disk_write_speed REAL,
            disk_read_speed REAL,
            disk_score INTEGER,
            net_speed REAL,
            net_score INTEGER,
            overall_score INTEGER
        )
        """
    )
    conn.commit()

def insert_run(conn: sqlite3.Connection, data: dict):
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO runs (ts, cpu_time, cpu_score, ram_time, ram_score, "
        "disk_write_speed, disk_read_speed, disk_score, net_speed, net_score, overall_score) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            data["ts"], data["cpu_time"], data["cpu_score"], data["ram_time"], data["ram_score"],
            data["disk_write_speed"], data["disk_read_speed"], data["disk_score"],
            data["net_speed"], data["net_score"], data["overall_score"],
        ),
    )
    conn.commit()

def fetch_all(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT * FROM runs ORDER BY ts DESC")
    return cur.fetchall()

# ---------------------------------------------------------------------------
# Benchmark primitives
# ---------------------------------------------------------------------------

def benchmark_cpu() -> tuple[float, int]:
    """Calculate primes up to CPU_PRIME_LIMIT and return execution time + score."""
    start = time.time()
    primes = []
    for n in range(2, CPU_PRIME_LIMIT + 1):
        is_prime = True
        for p in primes:
            if p * p > n:
                break
            if n % p == 0:
                is_prime = False
                break
        if is_prime:
            primes.append(n)
    elapsed = time.time() - start
    # Simple linear scoring: faster than ref => 100, slower proportionally down to 0
    score = max(0, int(100 * (CPU_REF_TIME / elapsed)))
    return elapsed, score

def benchmark_ram() -> tuple[float, int]:
    """Allocate a large list, fill it, then release – measure time and score."""
    size = RAM_ALLOC_MB * 1024 * 1024 // 8  # number of 64-bit ints approx
    start = time.time()
    data = [0] * size
    for i in range(size):
        data[i] = i
    del data
    elapsed = time.time() - start
    score = max(0, int(100 * (RAM_REF_TIME / elapsed)))
    return elapsed, score

def benchmark_disk() -> tuple[float, float, float, int]:
    """Write and read a temporary file; return write speed, read speed and score."""
    tmp = Path.cwd() / "_disk_test.tmp"
    total_bytes = DISK_FILE_MB * 1024 * 1024
    # Write test
    start_write = time.time()
    with open(tmp, "wb") as f:
        f.write(os.urandom(total_bytes))
    write_time = time.time() - start_write
    write_speed = (total_bytes / (1024 * 1024)) / write_time  # MB/s
    # Read test
    start_read = time.time()
    with open(tmp, "rb") as f:
        _ = f.read()
    read_time = time.time() - start_read
    read_speed = (total_bytes / (1024 * 1024)) / read_time
    # Clean up
    try:
        tmp.unlink()
    except Exception:
        pass
    # Scoring – average of write/read vs reference
    avg_speed = (write_speed + read_speed) / 2.0
    score = max(0, int(100 * (avg_speed / DISK_REF_SPEED)))
    return write_speed, read_speed, avg_speed, score

def benchmark_network() -> tuple[float, int]:
    """Download a small file and compute download speed (MiB/s)."""
    start = time.time()
    try:
        with urllib.request.urlopen(NETWORK_TEST_URL, timeout=30) as resp:
            data = resp.read()
    except Exception as e:
        print(f"[system_benchmark] Erreur téléchargement : {e}")
        return 0.0, 0
    elapsed = time.time() - start
    size_mb = len(data) / (1024 * 1024)
    speed = size_mb / elapsed if elapsed > 0 else 0.0
    score = max(0, int(100 * (speed / NETWORK_REF_SPEED)))
    return speed, score

# ---------------------------------------------------------------------------
# Overall orchestration
# ---------------------------------------------------------------------------

def run_benchmark():
    ts = datetime.utcnow().isoformat() + "Z"
    print("[system_benchmark] Démarrage du benchmark…")
    cpu_t, cpu_s = benchmark_cpu()
    print(f"CPU : {cpu_t:.2f}s -> score {cpu_s}")
    ram_t, ram_s = benchmark_ram()
    print(f"RAM : {ram_t:.2f}s -> score {ram_s}")
    dw, dr, avg, disk_s = benchmark_disk()
    print(f"DISK : write {dw:.1f} MiB/s, read {dr:.1f} MiB/s -> score {disk_s}")
    net_speed, net_s = benchmark_network()
    print(f"NETWORK : {net_speed:.2f} MiB/s -> score {net_s}")
    # Overall simple average of the five scores
    overall = int((cpu_s + ram_s + disk_s + net_s) / 4)
    print(f"Overall score : {overall}")
    data = {
        "ts": ts,
        "cpu_time": cpu_t,
        "cpu_score": cpu_s,
        "ram_time": ram_t,
        "ram_score": ram_s,
        "disk_write_speed": dw,
        "disk_read_speed": dr,
        "disk_score": disk_s,
        "net_speed": net_speed,
        "net_score": net_s,
        "overall_score": overall,
    }
    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)
    insert_run(conn, data)
    conn.close()
    print("[system_benchmark] Benchmark enregistré.")

def show_history():
    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)
    rows = fetch_all(conn)
    conn.close()
    if not rows:
        print("[system_benchmark] Aucun résultat enregistré.")
        return
    for row in rows:
        (rid, ts, cpu_t, cpu_s, ram_t, ram_s, dw, dr, disk_s, net_sp, net_s, overall) = row
        print(f"{ts} – CPU {cpu_s} (t={cpu_t:.2f}s), RAM {ram_s} (t={ram_t:.2f}s), "
              f"DISK {disk_s} (W={dw:.1f} MiB/s R={dr:.1f} MiB/s), NET {net_s} (t={net_sp:.2f} MiB/s), "
              f"OVERALL {overall}")

def compare_best():
    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)
    rows = fetch_all(conn)
    conn.close()
    if not rows:
        print("[system_benchmark] Aucun résultat à comparer.")
        return
    # Compute max per category
    max_cpu = max(r[3] for r in rows)  # cpu_score index 3
    max_ram = max(r[5] for r in rows)  # ram_score index 5
    max_disk = max(r[9] for r in rows)  # disk_score index 9
    max_net = max(r[11] for r in rows)  # net_score index 11
    avg_overall = sum(r[12] for r in rows) / len(rows)
    print("Meilleurs scores par catégorie :")
    print(f"  CPU   : {max_cpu}")
    print(f"  RAM   : {max_ram}")
    print(f"  DISK  : {max_disk}")
    print(f"  NET   : {max_net}")
    print(f"Score moyen global : {avg_overall:.1f}")

# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Benchmark système complet.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run", action="store_true", help="Exécuter le benchmark complet")
    group.add_argument("--history", action="store_true", help="Afficher l'historique des benchmarks")
    group.add_argument("--compare", action="store_true", help="Comparer les meilleurs scores")
    args = parser.parse_args()

    if args.run:
        run_benchmark()
    elif args.history:
        show_history()
    elif args.compare:
        compare_best()

if __name__ == "__main__":
    main()
