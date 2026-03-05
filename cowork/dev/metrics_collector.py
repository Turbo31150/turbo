#!/usr/bin/env python3
"""metrics_collector.py
Collecte périodiquement les métriques système (CPU, RAM, GPU, disque, réseau) et les stocke dans une base SQLite.
Retention : 7 jours.
CLI options:
  --collect          : effectue une collecte et l'enregistre.
  --export [FILE]    : exporte les données en CSV ou JSON (déduit du suffixe .csv/.json) ; si aucun fichier indiqué, écrit sur stdout.
  --history DAYS     : limite les exportations aux dernières DAYS jours (par défaut toutes).
  --format FORMAT    : force le format d'export (csv ou json).
  --help             : montre ce message d'aide.

Utilise uniquement la bibliothèque standard (subprocess, sqlite3, json, csv, argparse, datetime, os, sys).
"""

import argparse
import csv
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "metrics.db")
RETENTION_DAYS = 7


def _run_cmd(cmd: list[str]) -> str:
    """Execute une commande et retourne stdout décodé (utf‑8)."""
    result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    return result.stdout.strip()


def _get_cpu_percent() -> float:
    # Windows: wmic cpu get loadpercentage
    try:
        out = _run_cmd(["wmic", "cpu", "get", "loadpercentage"])
        # la première ligne est le titre, la deuxième la valeur
        lines = [l for l in out.splitlines() if l.strip()]
        if len(lines) >= 2:
            return float(lines[1].strip())
    except Exception:
        pass
    return 0.0


def _get_ram() -> tuple[int, int]:
    # Retourne (used_mb, total_mb)
    try:
        out = _run_cmd(["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/Value"])
        # format: FreePhysicalMemory=xxxx\nTotalVisibleMemorySize=yyyyy
        data = {}
        for part in out.splitlines():
            if "=" in part:
                k, v = part.split("=", 1)
                data[k.strip()] = int(v.strip())
        total_kb = data.get("TotalVisibleMemorySize", 0)
        free_kb = data.get("FreePhysicalMemory", 0)
        used_mb = (total_kb - free_kb) // 1024
        total_mb = total_kb // 1024
        return used_mb, total_mb
    except Exception:
        return 0, 0


def _get_gpu_util() -> tuple[int, int]:
    # Retourne (util_percent, used_mem_mb) – utilise nvidia‑smi si présent
    try:
        out = _run_cmd(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"])
        if out:
            util_str, mem_str = out.split(",")
            return int(util_str.strip()), int(mem_str.strip())
    except Exception:
        pass
    return 0, 0


def _get_disk() -> tuple[float, float]:
    # Retourne (used_gb, total_gb) pour le disque système (C:)
    try:
        out = _run_cmd(["wmic", "logicaldisk", "where", "DeviceID='C:'", "get", "Size,FreeSpace", "/Value"])
        data = {}
        for part in out.splitlines():
            if "=" in part:
                k, v = part.split("=", 1)
                data[k.strip()] = int(v.strip())
        total = data.get("Size", 0)
        free = data.get("FreeSpace", 0)
        used_gb = (total - free) / (1024 ** 3)
        total_gb = total / (1024 ** 3)
        return used_gb, total_gb
    except Exception:
        return 0.0, 0.0


def _get_network() -> tuple[int, int]:
    # Bytes sent / received depuis le dernier reset du compteur (cumulatif depuis le démarrage).
    try:
        out = _run_cmd(["netstat", "-e"])
        lines = out.splitlines()
        for i, line in enumerate(lines):
            if "Bytes" in line:
                # Les deux lignes suivantes contiennent les valeurs
                sent_line = lines[i + 1]
                recv_line = lines[i + 2]
                sent = int(sent_line.split()[1])
                recv = int(recv_line.split()[1])
                return sent, recv
    except Exception:
        pass
    return 0, 0


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics (
            ts TEXT PRIMARY KEY,
            cpu REAL,
            ram_used_mb INTEGER,
            ram_total_mb INTEGER,
            gpu_util REAL,
            gpu_mem_mb INTEGER,
            disk_used_gb REAL,
            disk_total_gb REAL,
            net_sent_bytes INTEGER,
            net_recv_bytes INTEGER
        )
        """
    )
    conn.commit()


def collect_and_store() -> None:
    ts = datetime.utcnow().isoformat()
    cpu = _get_cpu_percent()
    ram_used, ram_total = _get_ram()
    gpu_util, gpu_mem = _get_gpu_util()
    disk_used, disk_total = _get_disk()
    net_sent, net_recv = _get_network()

    conn = sqlite3.connect(DB_PATH)
    _init_db(conn)
    conn.execute(
        "INSERT OR REPLACE INTO metrics (ts, cpu, ram_used_mb, ram_total_mb, gpu_util, gpu_mem_mb, disk_used_gb, disk_total_gb, net_sent_bytes, net_recv_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (ts, cpu, ram_used, ram_total, gpu_util, gpu_mem, disk_used, disk_total, net_sent, net_recv),
    )
    # purge old rows
    cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    conn.execute("DELETE FROM metrics WHERE ts < ?", (cutoff.isoformat(),))
    conn.commit()
    conn.close()
    print(f"Collected metrics at {ts}")


def export_data(filepath: str | None, fmt: str, days: int | None) -> None:
    conn = sqlite3.connect(DB_PATH)
    _init_db(conn)
    query = "SELECT * FROM metrics"
    params = []
    if days is not None:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query += " WHERE ts >= ?"
        params.append(cutoff.isoformat())
    rows = conn.execute(query, params).fetchall()
    colnames = [desc[0] for desc in conn.execute(query, params).description]
    conn.close()

    if fmt == "json":
        data = [dict(zip(colnames, r)) for r in rows]
        out_str = json.dumps(data, indent=2, default=str)
    else:  # csv
        import io
        out_io = io.StringIO()
        writer = csv.writer(out_io)
        writer.writerow(colnames)
        writer.writerows(rows)
        out_str = out_io.getvalue()

    if filepath:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(out_str)
        print(f"Exported {len(rows)} rows to {filepath}")
    else:
        print(out_str)


def main():
    parser = argparse.ArgumentParser(description="Collecte métriques système et exportation.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--collect", action="store_true", help="Effectuer une collecte et la persister.")
    group.add_argument("--export", nargs="?", const="-", metavar="FILE", help="Exporter les données (CSV par défaut, .json force JSON). Utiliser '-' pour stdout.")
    parser.add_argument("--history", type=int, metavar="DAYS", help="Limiter l'export aux D jours précédents.")
    parser.add_argument("--format", choices=["csv", "json"], help="Forcer le format d'export.")
    args = parser.parse_args()

    if args.collect:
        collect_and_store()
    elif args.export is not None:
        fmt = "json" if (args.export and args.export.lower().endswith('.json')) else "csv"
        if args.format:
            fmt = args.format
        export_data(None if args.export == "-" else args.export, fmt, args.history)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
