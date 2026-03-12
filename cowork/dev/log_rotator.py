#!/usr/bin/env python3
"""log_rotator.py

Batch 7.2 – Rotation et compression des logs.

Fonctionnalités :
* Parcourt plusieurs répertoires de logs :
  - ``~/.openclaw/agents/main/logs/``
  - ``/home/turbo/jarvis-m1-ops/data/``
  - ``~/.openclaw/workspace/dev/`` (le dossier courant du script).
* Compresse les fichiers ``*.log`` et ``*.json`` dont la taille > 10 MiB en ``.gz`` (gzip).
* Supprime les archives ``*.gz`` plus vieilles que 30 jours.
* Produit un rapport de l’espace libéré lors de l’opération.
* CLI :
  --once   : réalise la rotation (compression + nettoyage) et affiche le résumé.
  --stats  : montre la taille actuelle de tous les logs (bruts + gz).
  --clean  : ne supprime que les archives anciennes (> 30 j) et indique l’espace libéré.

Le script utilise uniquement la bibliothèque standard : ``os``, ``pathlib``, ``gzip``, ``shutil``, ``datetime``.
"""

import argparse
from _paths import TURBO_DIR, DATA_DIR
import gzip
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# ------------------------------------------------------------
# Configuration des répertoires à scanner
# ------------------------------------------------------------
HOME = Path.home()
LOG_DIRS = [
    HOME / ".openclaw" / "agents" / "main" / "logs",
    DATA_DIR,
    HOME / ".openclaw" / "workspace" / "dev",
]

COMPRESS_THRESHOLD = 10 * 1024 * 1024  # 10 MiB
MAX_AGE_DAYS = 30

# ------------------------------------------------------------
# Helpers – taille lisible
# ------------------------------------------------------------

def human_bytes(num: int) -> str:
    for unit in ["B", "KB", "MiB", "GiB", "TiB"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}PiB"

# ------------------------------------------------------------
# Récupération des fichiers de logs (raw) dépassant le seuil
# ------------------------------------------------------------

def find_large_logs() -> list[Path]:
    large = []
    for base in LOG_DIRS:
        if not base.is_dir():
            continue
        for ext in ("*.log", "*.json"):
            for p in base.rglob(ext):
                try:
                    if p.is_file() and p.stat().st_size > COMPRESS_THRESHOLD:
                        large.append(p)
                except Exception:
                    continue
    return large

# ------------------------------------------------------------
# Compression d'un fichier en .gz
# ------------------------------------------------------------

def compress_file(src: Path) -> tuple[int, int]:
    """Compresses *src* to *src*.gz, deletes the original.
    Returns (original_size, compressed_size).
    """
    dst = src.with_suffix(src.suffix + ".gz")
    try:
        with open(src, "rb") as f_in, gzip.open(dst, "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)
        orig = src.stat().st_size
        comp = dst.stat().st_size
        src.unlink()  # remove original
        return orig, comp
    except Exception as e:
        print(f"[log_rotator] Erreur compression {src}: {e}")
        return 0, 0

# ------------------------------------------------------------
# Nettoyage des archives .gz trop vieilles
# ------------------------------------------------------------

def clean_old_archives() -> int:
    """Supprime les *.gz plus vieux que *MAX_AGE_DAYS*.
    Retourne l'espace libéré (en octets).
    """
    now = datetime.now()
    cutoff = now - timedelta(days=MAX_AGE_DAYS)
    freed = 0
    for base in LOG_DIRS:
        if not base.is_dir():
            continue
        for gz in base.rglob("*.gz"):
            try:
                mtime = datetime.fromtimestamp(gz.stat().st_mtime)
                if mtime < cutoff:
                    size = gz.stat().st_size
                    gz.unlink()
                    freed += size
            except Exception:
                continue
    return freed

# ------------------------------------------------------------
# Statistiques – taille actuelle des logs (raw + gz)
# ------------------------------------------------------------

def compute_stats() -> tuple[int, int, int]:
    raw_total = 0
    gz_total = 0
    for base in LOG_DIRS:
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            try:
                if p.is_file():
                    if p.suffix == ".gz":
                        gz_total += p.stat().st_size
                    else:
                        raw_total += p.stat().st_size
            except Exception:
                continue
    return raw_total, gz_total, raw_total + gz_total

# ------------------------------------------------------------
# CLI actions
# ------------------------------------------------------------

def rotate_once():
    # Compression
    large_files = find_large_logs()
    total_orig = 0
    total_comp = 0
    for f in large_files:
        o, c = compress_file(f)
        total_orig += o
        total_comp += c
    # Cleanup old archives
    freed_cleanup = clean_old_archives()
    # Compute summary
    freed_by_compression = total_orig - total_comp if total_orig >= total_comp else 0
    total_freed = freed_by_compression + freed_cleanup
    print("[log_rotator] Rotation complete:")
    print(f"  Files compressed: {len(large_files)}")
    print(f"  Original size compressed: {human_bytes(total_orig)}")
    print(f"  Size after compression: {human_bytes(total_comp)}")
    print(f"  Space freed by compression: {human_bytes(freed_by_compression)}")
    print(f"  Archives deleted (> {MAX_AGE_DAYS} days): {human_bytes(freed_cleanup)} freed")
    print(f"  TOTAL space freed: {human_bytes(total_freed)}")

def show_stats():
    raw, gz, total = compute_stats()
    print("[log_rotator] Statistiques des logs :")
    print(f"  Taille brute (non compressée) : {human_bytes(raw)}")
    print(f"  Taille des archives .gz : {human_bytes(gz)}")
    print(f"  Taille combinée : {human_bytes(total)}")

def clean_only():
    freed = clean_old_archives()
    print(f"[log_rotator] Nettoyage – archives supprimées : {human_bytes(freed)} libérées")

def main():
    parser = argparse.ArgumentParser(description="Rotation et compression des logs.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Effectuer rotation + nettoyage")
    group.add_argument("--stats", action="store_true", help="Afficher taille actuelle des logs")
    group.add_argument("--clean", action="store_true", help="Supprimer uniquement les archives anciennes (>30j)")
    args = parser.parse_args()

    if args.once:
        rotate_once()
    elif args.stats:
        show_stats()
    elif args.clean:
        clean_only()

if __name__ == "__main__":
    main()