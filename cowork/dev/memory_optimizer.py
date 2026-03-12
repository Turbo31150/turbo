#!/usr/bin/env python3
"""
Memory Optimizer — Analyse et optimisation de la memoire RAM et VRAM.

Fonctionnalites:
  - Analyse detaillee de l'utilisation RAM et VRAM
  - Detection des processus gourmands en memoire
  - Nettoyage automatique (__pycache__, .pyc, fichiers temporaires)
  - Monitoring continu avec stockage des metriques
  - Rapports d'evolution et recommandations

Auteur: JARVIS Turbo
Date: 2026-03-05
"""

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# --- Chemin vers la base de donnees ---
DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "memory_optimizer.db"

# --- Seuils d'alerte memoire (en pourcentage) ---
MEMORY_THRESHOLDS = {
    "ram_warning_pct": 80,     # Alerte si RAM > 80%
    "ram_critical_pct": 92,    # Critique si RAM > 92%
    "vram_warning_pct": 85,    # Alerte si VRAM > 85% (par GPU)
    "vram_critical_pct": 95,   # Critique si VRAM > 95%
    "process_high_mb": 500,    # Processus > 500 MB = "gourmand"
    "process_extreme_mb": 2000, # Processus > 2 GB = "extreme"
}

# --- Patterns de nettoyage ---
CLEANUP_PATTERNS = {
    "__pycache__": {
        "type": "directory",
        "pattern": "__pycache__",
        "description": "Repertoires de cache Python bytecode",
    },
    ".pyc": {
        "type": "file",
        "pattern": "*.pyc",
        "description": "Fichiers Python compiles (.pyc)",
    },
    ".pyo": {
        "type": "file",
        "pattern": "*.pyo",
        "description": "Fichiers Python optimises (.pyo)",
    },
    "temp_files": {
        "type": "file",
        "pattern": "*.tmp",
        "description": "Fichiers temporaires (.tmp)",
    },
    ".pytest_cache": {
        "type": "directory",
        "pattern": ".pytest_cache",
        "description": "Cache de pytest",
    },
    ".mypy_cache": {
        "type": "directory",
        "pattern": ".mypy_cache",
        "description": "Cache de mypy",
    },
    ".ruff_cache": {
        "type": "directory",
        "pattern": ".ruff_cache",
        "description": "Cache de ruff",
    },
}


def _init_db():
    """Initialise la base de donnees SQLite avec les tables necessaires."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Table des snapshots memoire (historique global)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            total_ram_mb REAL,
            used_ram_mb REAL,
            free_ram_mb REAL,
            ram_usage_pct REAL,
            total_vram_mb REAL,
            used_vram_mb REAL,
            free_vram_mb REAL,
            vram_usage_pct REAL,
            gpu_count INTEGER,
            process_count INTEGER
        )
    """)

    # Table des processus gourmands detectes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS high_memory_processes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            snapshot_id INTEGER,
            pid INTEGER,
            name TEXT,
            memory_mb REAL,
            category TEXT,
            FOREIGN KEY (snapshot_id) REFERENCES memory_snapshots(id)
        )
    """)

    # Table des nettoyages effectues
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cleanup_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            target_path TEXT,
            pattern TEXT,
            items_removed INTEGER,
            bytes_freed INTEGER,
            errors INTEGER,
            details TEXT
        )
    """)

    # Table des alertes memoire
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            value REAL,
            threshold REAL,
            message TEXT
        )
    """)

    conn.commit()
    conn.close()


def _run_command(cmd, timeout=15):
    """
    Execute une commande systeme et retourne la sortie.
    Gere les erreurs et timeouts de maniere securisee.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=isinstance(cmd, str),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.stdout.strip(), result.returncode
    except FileNotFoundError:
        return None, -1
    except subprocess.TimeoutExpired:
        return None, -2
    except Exception as e:
        return str(e), -3


def _get_ram_info():
    """
    Recupere les informations RAM via wmic (Windows).
    Retourne un dict avec total, utilise, libre et pourcentage.
    """
    # Memoire physique totale
    total_out, rc1 = _run_command(
        ["wmic", "ComputerSystem", "get", "TotalPhysicalMemory", "/value"]
    )
    # Memoire libre
    free_out, rc2 = _run_command(
        ["wmic", "OS", "get", "FreePhysicalMemory", "/value"]
    )

    total_mb = None
    free_mb = None

    if total_out and rc1 == 0:
        for line in total_out.split("\n"):
            if "TotalPhysicalMemory=" in line:
                try:
                    # wmic retourne en octets
                    total_bytes = int(line.split("=")[1].strip())
                    total_mb = round(total_bytes / (1024 * 1024), 1)
                except (ValueError, IndexError):
                    pass

    if free_out and rc2 == 0:
        for line in free_out.split("\n"):
            if "FreePhysicalMemory=" in line:
                try:
                    # wmic retourne en Ko pour FreePhysicalMemory
                    free_kb = int(line.split("=")[1].strip())
                    free_mb = round(free_kb / 1024, 1)
                except (ValueError, IndexError):
                    pass

    if total_mb and free_mb:
        used_mb = round(total_mb - free_mb, 1)
        usage_pct = round((used_mb / total_mb) * 100, 1)
    else:
        used_mb = None
        usage_pct = None

    return {
        "total_mb": total_mb,
        "used_mb": used_mb,
        "free_mb": free_mb,
        "usage_pct": usage_pct,
    }


def _get_vram_info():
    """
    Recupere les informations VRAM de tous les GPU via nvidia-smi.
    Retourne une liste de dicts par GPU.
    """
    query = "index,name,memory.used,memory.total,memory.free,utilization.memory"
    out, rc = _run_command([
        "nvidia-smi",
        f"--query-gpu={query}",
        "--format=csv,noheader,nounits",
    ])

    if out is None or rc != 0:
        return []

    gpus = []
    for line in out.split("\n"):
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            parts.extend([""] * (6 - len(parts)))

        try:
            used = float(parts[2]) if parts[2] not in ("[N/A]", "") else None
            total = float(parts[3]) if parts[3] not in ("[N/A]", "") else None
            free = float(parts[4]) if parts[4] not in ("[N/A]", "") else None
            util = float(parts[5]) if parts[5] not in ("[N/A]", "") else None
        except ValueError:
            used = total = free = util = None

        usage_pct = round((used / total) * 100, 1) if used and total else None

        gpus.append({
            "index": int(parts[0]) if parts[0].isdigit() else 0,
            "name": parts[1],
            "used_mb": used,
            "total_mb": total,
            "free_mb": free,
            "utilization_pct": util,
            "usage_pct": usage_pct,
        })

    return gpus


def _get_vram_processes():
    """
    Recupere la liste des processus utilisant la VRAM via nvidia-smi.
    """
    out, rc = _run_command([
        "nvidia-smi",
        "--query-compute-apps=pid,name,used_memory",
        "--format=csv,noheader,nounits",
    ])

    if out is None or rc != 0:
        return []

    processes = []
    for line in out.split("\n"):
        if not line.strip() or "no running" in line.lower():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3:
            try:
                processes.append({
                    "pid": int(parts[0]),
                    "name": parts[1],
                    "vram_mb": float(parts[2]) if parts[2] not in ("[N/A]", "") else None,
                })
            except (ValueError, IndexError):
                pass

    return processes


def _get_top_processes(top_n=20):
    """
    Recupere les processus les plus gourmands en RAM via tasklist.
    Trie par memoire decroissante, retourne les top N.
    """
    # Utiliser tasklist avec format CSV pour un parsing fiable
    out, rc = _run_command(["tasklist", "/FO", "CSV", "/NH"])

    if out is None or rc != 0:
        return []

    processes = []
    for line in out.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Format CSV: "nom.exe","PID","Session","Num","Mem Usage"
        # Les guillemets et les separateurs Ko rendent le parsing delicat
        try:
            parts = line.split('","')
            if len(parts) >= 5:
                name = parts[0].strip('"')
                pid = int(parts[1].strip('"'))
                # La memoire est au format "123 456 Ko" ou "123,456 K"
                mem_str = parts[4].strip('"').strip()
                # Nettoyer: retirer Ko/K, espaces, points, virgules de milliers
                mem_str = mem_str.replace("\xa0", "").replace(" ", "")
                mem_str = mem_str.replace("Ko", "").replace("K", "")
                mem_str = mem_str.replace(",", "").replace(".", "").strip()
                if mem_str.isdigit():
                    mem_kb = int(mem_str)
                    mem_mb = round(mem_kb / 1024, 1)
                    processes.append({
                        "pid": pid,
                        "name": name,
                        "memory_mb": mem_mb,
                    })
        except (ValueError, IndexError):
            continue

    # Trier par memoire decroissante et prendre les top N
    processes.sort(key=lambda p: p["memory_mb"], reverse=True)
    return processes[:top_n]


def _categorize_process(name, memory_mb):
    """
    Categorise un processus selon son nom et sa consommation memoire.
    """
    name_lower = name.lower()

    # Categories basees sur le nom du processus
    if any(kw in name_lower for kw in ["python", "uv", "pip"]):
        category = "python"
    elif any(kw in name_lower for kw in ["node", "electron", "npm"]):
        category = "javascript"
    elif any(kw in name_lower for kw in ["lm studio", "lmstudio", "ollama"]):
        category = "ia_inference"
    elif any(kw in name_lower for kw in ["chrome", "firefox", "edge", "brave"]):
        category = "browser"
    elif any(kw in name_lower for kw in ["code", "cursor", "vscode"]):
        category = "editor"
    elif any(kw in name_lower for kw in ["nvidia", "cuda", "nv"]):
        category = "gpu_driver"
    elif any(kw in name_lower for kw in ["svchost", "system", "csrss", "dwm"]):
        category = "system"
    elif any(kw in name_lower for kw in ["discord", "telegram", "slack"]):
        category = "communication"
    else:
        category = "other"

    # Niveau de consommation
    if memory_mb >= MEMORY_THRESHOLDS["process_extreme_mb"]:
        level = "extreme"
    elif memory_mb >= MEMORY_THRESHOLDS["process_high_mb"]:
        level = "high"
    else:
        level = "normal"

    return category, level


def cmd_analyze(args):
    """
    Analyse complete de la memoire: RAM, VRAM, processus gourmands.
    """
    _init_db()

    # Collecter les informations RAM
    ram_info = _get_ram_info()

    # Collecter les informations VRAM
    vram_gpus = _get_vram_info()
    vram_processes = _get_vram_processes()

    # Totaux VRAM (somme de tous les GPU)
    total_vram = sum(g["total_mb"] for g in vram_gpus if g["total_mb"]) if vram_gpus else None
    used_vram = sum(g["used_mb"] for g in vram_gpus if g["used_mb"]) if vram_gpus else None
    free_vram = sum(g["free_mb"] for g in vram_gpus if g["free_mb"]) if vram_gpus else None
    vram_pct = round((used_vram / total_vram) * 100, 1) if used_vram and total_vram else None

    # Processus RAM les plus gourmands
    top_processes = _get_top_processes(top_n=args.top)

    # Categoriser les processus
    categorized = {}
    high_memory_list = []
    for proc in top_processes:
        cat, level = _categorize_process(proc["name"], proc["memory_mb"])
        proc["category"] = cat
        proc["level"] = level

        if cat not in categorized:
            categorized[cat] = {"count": 0, "total_mb": 0}
        categorized[cat]["count"] += 1
        categorized[cat]["total_mb"] = round(
            categorized[cat]["total_mb"] + proc["memory_mb"], 1
        )

        if level in ("high", "extreme"):
            high_memory_list.append(proc)

    # Sauvegarder le snapshot
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    ts = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO memory_snapshots
            (timestamp, total_ram_mb, used_ram_mb, free_ram_mb, ram_usage_pct,
             total_vram_mb, used_vram_mb, free_vram_mb, vram_usage_pct,
             gpu_count, process_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ts, ram_info["total_mb"], ram_info["used_mb"], ram_info["free_mb"],
        ram_info["usage_pct"], total_vram, used_vram, free_vram, vram_pct,
        len(vram_gpus), len(top_processes),
    ))
    snapshot_id = cursor.lastrowid

    # Sauvegarder les processus gourmands
    for proc in high_memory_list:
        cursor.execute("""
            INSERT INTO high_memory_processes
                (timestamp, snapshot_id, pid, name, memory_mb, category)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ts, snapshot_id, proc["pid"], proc["name"],
              proc["memory_mb"], proc["category"]))

    # Generer des alertes si necessaire
    alerts = []
    if ram_info["usage_pct"]:
        if ram_info["usage_pct"] >= MEMORY_THRESHOLDS["ram_critical_pct"]:
            alert = {
                "type": "ram",
                "severity": "critical",
                "value": ram_info["usage_pct"],
                "threshold": MEMORY_THRESHOLDS["ram_critical_pct"],
                "message": (
                    f"RAM critique: {ram_info['usage_pct']}% "
                    f"({ram_info['used_mb']} / {ram_info['total_mb']} MB)"
                ),
            }
            alerts.append(alert)
            cursor.execute("""
                INSERT INTO memory_alerts (timestamp, alert_type, severity, value, threshold, message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ts, alert["type"], alert["severity"], alert["value"],
                  alert["threshold"], alert["message"]))
        elif ram_info["usage_pct"] >= MEMORY_THRESHOLDS["ram_warning_pct"]:
            alert = {
                "type": "ram",
                "severity": "warning",
                "value": ram_info["usage_pct"],
                "threshold": MEMORY_THRESHOLDS["ram_warning_pct"],
                "message": (
                    f"RAM elevee: {ram_info['usage_pct']}% "
                    f"({ram_info['used_mb']} / {ram_info['total_mb']} MB)"
                ),
            }
            alerts.append(alert)
            cursor.execute("""
                INSERT INTO memory_alerts (timestamp, alert_type, severity, value, threshold, message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ts, alert["type"], alert["severity"], alert["value"],
                  alert["threshold"], alert["message"]))

    # Alertes VRAM par GPU
    for gpu in vram_gpus:
        if gpu["usage_pct"] is not None:
            if gpu["usage_pct"] >= MEMORY_THRESHOLDS["vram_critical_pct"]:
                alert = {
                    "type": "vram",
                    "severity": "critical",
                    "gpu_index": gpu["index"],
                    "value": gpu["usage_pct"],
                    "threshold": MEMORY_THRESHOLDS["vram_critical_pct"],
                    "message": (
                        f"VRAM GPU {gpu['index']} critique: {gpu['usage_pct']}% "
                        f"({gpu['used_mb']} / {gpu['total_mb']} MB)"
                    ),
                }
                alerts.append(alert)
                cursor.execute("""
                    INSERT INTO memory_alerts (timestamp, alert_type, severity, value, threshold, message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ts, alert["type"], alert["severity"], alert["value"],
                      alert["threshold"], alert["message"]))
            elif gpu["usage_pct"] >= MEMORY_THRESHOLDS["vram_warning_pct"]:
                alert = {
                    "type": "vram",
                    "severity": "warning",
                    "gpu_index": gpu["index"],
                    "value": gpu["usage_pct"],
                    "threshold": MEMORY_THRESHOLDS["vram_warning_pct"],
                    "message": (
                        f"VRAM GPU {gpu['index']} elevee: {gpu['usage_pct']}% "
                        f"({gpu['used_mb']} / {gpu['total_mb']} MB)"
                    ),
                }
                alerts.append(alert)
                cursor.execute("""
                    INSERT INTO memory_alerts (timestamp, alert_type, severity, value, threshold, message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ts, alert["type"], alert["severity"], alert["value"],
                      alert["threshold"], alert["message"]))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "timestamp": ts,
        "ram": ram_info,
        "vram": {
            "gpu_count": len(vram_gpus),
            "total_mb": total_vram,
            "used_mb": used_vram,
            "free_mb": free_vram,
            "usage_pct": vram_pct,
            "per_gpu": vram_gpus,
            "processes": vram_processes,
        },
        "top_processes": top_processes,
        "high_memory_processes": high_memory_list,
        "categories": categorized,
        "alerts": alerts,
        "thresholds": MEMORY_THRESHOLDS,
        "snapshot_id": snapshot_id,
    }


def cmd_clean(args):
    """
    Nettoyage des fichiers temporaires: __pycache__, .pyc, .tmp, caches divers.
    Parcourt recursivement le repertoire cible.
    """
    target_dir = Path(args.path).resolve()
    dry_run = args.dry_run

    if not target_dir.exists():
        return {
            "success": False,
            "error": f"Repertoire introuvable: {target_dir}",
        }

    _init_db()
    ts = datetime.now().isoformat()

    results = {
        "success": True,
        "timestamp": ts,
        "target_path": str(target_dir),
        "dry_run": dry_run,
        "cleaned": {},
        "total_items_removed": 0,
        "total_bytes_freed": 0,
        "errors": [],
    }

    for pattern_key, pattern_info in CLEANUP_PATTERNS.items():
        items_found = []
        items_removed = 0
        bytes_freed = 0
        errors = 0

        if pattern_info["type"] == "directory":
            # Chercher les repertoires correspondants
            for dirpath, dirnames, _ in os.walk(str(target_dir)):
                for dirname in dirnames:
                    if dirname == pattern_info["pattern"]:
                        full_path = Path(dirpath) / dirname
                        try:
                            # Calculer la taille avant suppression
                            dir_size = sum(
                                f.stat().st_size
                                for f in full_path.rglob("*")
                                if f.is_file()
                            )
                            file_count = sum(1 for _ in full_path.rglob("*") if _.is_file())
                            items_found.append({
                                "path": str(full_path),
                                "size_bytes": dir_size,
                                "file_count": file_count,
                            })

                            if not dry_run:
                                shutil.rmtree(str(full_path), ignore_errors=True)
                                items_removed += 1
                                bytes_freed += dir_size
                            else:
                                items_removed += 1
                                bytes_freed += dir_size
                        except (PermissionError, OSError) as e:
                            errors += 1
                            results["errors"].append({
                                "path": str(full_path),
                                "error": str(e),
                            })

        elif pattern_info["type"] == "file":
            # Chercher les fichiers correspondants
            for filepath in target_dir.rglob(pattern_info["pattern"]):
                if filepath.is_file():
                    try:
                        file_size = filepath.stat().st_size
                        items_found.append({
                            "path": str(filepath),
                            "size_bytes": file_size,
                        })

                        if not dry_run:
                            filepath.unlink()
                            items_removed += 1
                            bytes_freed += file_size
                        else:
                            items_removed += 1
                            bytes_freed += file_size
                    except (PermissionError, OSError) as e:
                        errors += 1
                        results["errors"].append({
                            "path": str(filepath),
                            "error": str(e),
                        })

        results["cleaned"][pattern_key] = {
            "description": pattern_info["description"],
            "items_found": len(items_found),
            "items_removed": items_removed,
            "bytes_freed": bytes_freed,
            "bytes_freed_human": _human_size(bytes_freed),
            "errors": errors,
        }
        results["total_items_removed"] += items_removed
        results["total_bytes_freed"] += bytes_freed

    results["total_bytes_freed_human"] = _human_size(results["total_bytes_freed"])

    # Enregistrer le nettoyage dans l'historique
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cleanup_history
            (timestamp, target_path, pattern, items_removed, bytes_freed, errors, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        ts, str(target_dir), "all_patterns",
        results["total_items_removed"], results["total_bytes_freed"],
        len(results["errors"]),
        json.dumps(results["cleaned"], ensure_ascii=False),
    ))
    conn.commit()
    conn.close()

    return results


def _human_size(size_bytes):
    """Convertit une taille en octets en format lisible (Ko, Mo, Go)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 1)} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{round(size_bytes / (1024 * 1024), 1)} MB"
    else:
        return f"{round(size_bytes / (1024 * 1024 * 1024), 2)} GB"


def cmd_monitor(args):
    """
    Monitoring continu de la memoire: collecte des echantillons
    a intervalle regulier pendant une duree donnee.
    """
    duration = args.duration
    interval = args.interval

    _init_db()

    samples = []
    start_time = time.time()
    sample_count = 0

    while (time.time() - start_time) < duration:
        # Collecter RAM
        ram_info = _get_ram_info()

        # Collecter VRAM
        vram_gpus = _get_vram_info()
        total_vram = sum(g["total_mb"] for g in vram_gpus if g["total_mb"]) if vram_gpus else None
        used_vram = sum(g["used_mb"] for g in vram_gpus if g["used_mb"]) if vram_gpus else None

        sample = {
            "elapsed_s": round(time.time() - start_time, 2),
            "timestamp": datetime.now().isoformat(),
            "ram_usage_pct": ram_info.get("usage_pct"),
            "ram_used_mb": ram_info.get("used_mb"),
            "ram_free_mb": ram_info.get("free_mb"),
            "vram_used_mb": used_vram,
            "vram_total_mb": total_vram,
            "gpu_count": len(vram_gpus),
        }
        samples.append(sample)
        sample_count += 1

        # Sauvegarder le snapshot
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        free_vram = sum(g["free_mb"] for g in vram_gpus if g["free_mb"]) if vram_gpus else None
        vram_pct = round((used_vram / total_vram) * 100, 1) if used_vram and total_vram else None
        cursor.execute("""
            INSERT INTO memory_snapshots
                (timestamp, total_ram_mb, used_ram_mb, free_ram_mb, ram_usage_pct,
                 total_vram_mb, used_vram_mb, free_vram_mb, vram_usage_pct,
                 gpu_count, process_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sample["timestamp"], ram_info.get("total_mb"), ram_info.get("used_mb"),
            ram_info.get("free_mb"), ram_info.get("usage_pct"),
            total_vram, used_vram, free_vram, vram_pct,
            len(vram_gpus), 0,
        ))
        conn.commit()
        conn.close()

        time.sleep(interval)

    elapsed = round(time.time() - start_time, 2)

    # Calculer les statistiques du monitoring
    def _safe_avg(key):
        vals = [s[key] for s in samples if s.get(key) is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    def _safe_max(key):
        vals = [s[key] for s in samples if s.get(key) is not None]
        return round(max(vals), 2) if vals else None

    def _safe_min(key):
        vals = [s[key] for s in samples if s.get(key) is not None]
        return round(min(vals), 2) if vals else None

    stats = {
        "ram_usage_pct": {
            "avg": _safe_avg("ram_usage_pct"),
            "max": _safe_max("ram_usage_pct"),
            "min": _safe_min("ram_usage_pct"),
        },
        "ram_used_mb": {
            "avg": _safe_avg("ram_used_mb"),
            "max": _safe_max("ram_used_mb"),
            "min": _safe_min("ram_used_mb"),
        },
        "vram_used_mb": {
            "avg": _safe_avg("vram_used_mb"),
            "max": _safe_max("vram_used_mb"),
            "min": _safe_min("vram_used_mb"),
        },
    }

    # Calculer la tendance (pente de la RAM au fil du temps)
    ram_values = [s["ram_usage_pct"] for s in samples if s.get("ram_usage_pct") is not None]
    if len(ram_values) >= 2:
        # Pente simple: difference entre premiere et derniere valeur
        trend = round(ram_values[-1] - ram_values[0], 2)
        trend_label = "stable" if abs(trend) < 1 else ("croissante" if trend > 0 else "decroissante")
    else:
        trend = 0
        trend_label = "insuffisant"

    return {
        "success": True,
        "action": "monitor",
        "duration_s": elapsed,
        "interval_s": interval,
        "samples_count": sample_count,
        "statistics": stats,
        "trend": {
            "ram_delta_pct": trend,
            "direction": trend_label,
            "note": (
                "Tendance croissante = fuite memoire potentielle"
                if trend > 2 else "Memoire stable"
            ),
        },
        "first_sample": samples[0] if samples else None,
        "last_sample": samples[-1] if samples else None,
    }


def cmd_report(args):
    """
    Genere un rapport complet a partir des donnees historiques stockees en base.
    Inclut les tendances, alertes et recommandations.
    """
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Statistiques globales des snapshots (dernieres 24h)
    cursor.execute("""
        SELECT
            COUNT(*) as readings,
            AVG(ram_usage_pct) as avg_ram,
            MAX(ram_usage_pct) as max_ram,
            MIN(ram_usage_pct) as min_ram,
            AVG(vram_usage_pct) as avg_vram,
            MAX(vram_usage_pct) as max_vram,
            MIN(vram_usage_pct) as min_vram
        FROM memory_snapshots
        WHERE timestamp > datetime('now', '-1 day')
    """)
    row = cursor.fetchone()
    stats_24h = {
        "readings": row[0],
        "ram_avg_pct": round(row[1], 1) if row[1] else None,
        "ram_max_pct": round(row[2], 1) if row[2] else None,
        "ram_min_pct": round(row[3], 1) if row[3] else None,
        "vram_avg_pct": round(row[4], 1) if row[4] else None,
        "vram_max_pct": round(row[5], 1) if row[5] else None,
        "vram_min_pct": round(row[6], 1) if row[6] else None,
    }

    # Top processus les plus frequemment gourmands (dernieres 24h)
    cursor.execute("""
        SELECT name, category,
               COUNT(*) as occurrences,
               AVG(memory_mb) as avg_mb,
               MAX(memory_mb) as max_mb
        FROM high_memory_processes
        WHERE timestamp > datetime('now', '-1 day')
        GROUP BY name
        ORDER BY occurrences DESC, avg_mb DESC
        LIMIT 10
    """)
    frequent_hogs = []
    for r in cursor.fetchall():
        frequent_hogs.append({
            "name": r[0],
            "category": r[1],
            "occurrences": r[2],
            "avg_memory_mb": round(r[3], 1) if r[3] else None,
            "max_memory_mb": round(r[4], 1) if r[4] else None,
        })

    # Historique des nettoyages
    cursor.execute("""
        SELECT timestamp, target_path, items_removed, bytes_freed
        FROM cleanup_history
        ORDER BY id DESC
        LIMIT 10
    """)
    cleanup_history = []
    for r in cursor.fetchall():
        cleanup_history.append({
            "timestamp": r[0],
            "target_path": r[1],
            "items_removed": r[2],
            "bytes_freed": r[3],
            "bytes_freed_human": _human_size(r[3]) if r[3] else "0 B",
        })

    # Alertes recentes (dernieres 24h)
    cursor.execute("""
        SELECT timestamp, alert_type, severity, value, threshold, message
        FROM memory_alerts
        WHERE timestamp > datetime('now', '-1 day')
        ORDER BY id DESC
        LIMIT 20
    """)
    recent_alerts = []
    for r in cursor.fetchall():
        recent_alerts.append({
            "timestamp": r[0],
            "type": r[1],
            "severity": r[2],
            "value": r[3],
            "threshold": r[4],
            "message": r[5],
        })

    # Compteurs de la base
    cursor.execute("SELECT COUNT(*) FROM memory_snapshots")
    total_snapshots = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM high_memory_processes")
    total_hog_records = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM cleanup_history")
    total_cleanups = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM memory_alerts")
    total_alerts = cursor.fetchone()[0]

    conn.close()

    # Generer les recommandations basees sur les donnees
    recommendations = []

    if stats_24h["ram_max_pct"] and stats_24h["ram_max_pct"] > 90:
        recommendations.append({
            "priority": "high",
            "area": "ram",
            "message": (
                f"RAM a atteint {stats_24h['ram_max_pct']}% sur les 24 dernieres heures. "
                f"Envisagez de fermer les processus non essentiels ou d'augmenter la RAM."
            ),
        })

    if stats_24h["vram_max_pct"] and stats_24h["vram_max_pct"] > 90:
        recommendations.append({
            "priority": "high",
            "area": "vram",
            "message": (
                f"VRAM a atteint {stats_24h['vram_max_pct']}% sur les 24 dernieres heures. "
                f"Reduisez la taille des modeles IA charges ou utilisez le swap GPU."
            ),
        })

    if frequent_hogs:
        top_hog = frequent_hogs[0]
        recommendations.append({
            "priority": "medium",
            "area": "process",
            "message": (
                f"'{top_hog['name']}' est le processus le plus frequemment gourmand "
                f"({top_hog['occurrences']} occurrences, moy {top_hog['avg_memory_mb']} MB). "
                f"Verifiez s'il y a une fuite memoire."
            ),
        })

    if not cleanup_history:
        recommendations.append({
            "priority": "low",
            "area": "cleanup",
            "message": (
                "Aucun nettoyage enregistre. Lancez --clean pour liberer de l'espace "
                "en supprimant __pycache__, .pyc et fichiers temporaires."
            ),
        })

    if not recommendations:
        recommendations.append({
            "priority": "info",
            "area": "general",
            "message": "Systeme en bon etat. Aucune action requise.",
        })

    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "report": {
            "stats_24h": stats_24h,
            "frequent_high_memory_processes": frequent_hogs,
            "recent_alerts": recent_alerts,
            "cleanup_history": cleanup_history,
            "recommendations": recommendations,
        },
        "database": {
            "path": str(DB_PATH),
            "total_snapshots": total_snapshots,
            "total_hog_records": total_hog_records,
            "total_cleanups": total_cleanups,
            "total_alerts": total_alerts,
        },
    }


def main():
    """Point d'entree principal — parsing des arguments et dispatch."""
    parser = argparse.ArgumentParser(
        description="Memory Optimizer — Analyse et optimisation RAM/VRAM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  %(prog)s --analyze                        Analyse complete RAM + VRAM + processus
  %(prog)s --analyze --top 30               Top 30 processus (defaut: 20)
  %(prog)s --clean --path F:/BUREAU/turbo   Nettoyer les caches Python
  %(prog)s --clean --path . --dry-run       Simuler le nettoyage (sans supprimer)
  %(prog)s --monitor --duration 60          Monitoring 60 secondes
  %(prog)s --monitor --interval 5           Echantillonnage toutes les 5 secondes
  %(prog)s --report                         Rapport avec historique et recommandations
        """,
    )

    # Actions principales (mutuellement exclusives)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--analyze", action="store_true",
        help="Analyser l'utilisation memoire (RAM + VRAM + processus)",
    )
    group.add_argument(
        "--clean", action="store_true",
        help="Nettoyer les fichiers temporaires (__pycache__, .pyc, .tmp)",
    )
    group.add_argument(
        "--monitor", action="store_true",
        help="Monitoring continu de la memoire avec collecte de metriques",
    )
    group.add_argument(
        "--report", action="store_true",
        help="Generer un rapport avec historique et recommandations",
    )

    # Options supplementaires
    parser.add_argument(
        "--top", type=int, default=20,
        help="Nombre de processus a afficher (defaut: 20, avec --analyze)",
    )
    parser.add_argument(
        "--path", type=str, default=".",
        help="Repertoire cible pour le nettoyage (defaut: repertoire courant, avec --clean)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simuler le nettoyage sans supprimer (avec --clean)",
    )
    parser.add_argument(
        "--duration", type=int, default=30,
        help="Duree du monitoring en secondes (defaut: 30, avec --monitor)",
    )
    parser.add_argument(
        "--interval", type=float, default=2.0,
        help="Intervalle d'echantillonnage en secondes (defaut: 2.0, avec --monitor)",
    )

    args = parser.parse_args()

    # Initialiser la base de donnees
    _init_db()

    # Dispatcher vers la commande appropriee
    if args.analyze:
        result = cmd_analyze(args)
    elif args.clean:
        result = cmd_clean(args)
    elif args.monitor:
        result = cmd_monitor(args)
    elif args.report:
        result = cmd_report(args)
    else:
        result = {"success": False, "error": "Action non reconnue"}

    # Sortie JSON formatee
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    sys.exit(0 if result.get("success", False) else 1)


if __name__ == "__main__":
    main()
