#!/usr/bin/env python3
"""
GPU Optimizer — Gestion avancee des GPU NVIDIA via nvidia-smi.

Fonctionnalites:
  - Lecture des temperatures, horloges, puissance, VRAM
  - Application de profils d'optimisation (Gaming, IA-Training, Inference, Eco)
  - Benchmarks et comparaisons historiques
  - Monitoring thermique avec seuils d'alerte
  - Stockage SQLite pour historique et tendances

Auteur: JARVIS Turbo
Date: 2026-03-05
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

# --- Chemin vers la base de donnees ---
DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "gpu_optimizer.db"

# --- Profils d'optimisation GPU ---
# Chaque profil definit une puissance cible (% du TDP max), un niveau de ventilation
# et une description. Les watts exacts sont calcules dynamiquement selon le GPU.
PROFILES = {
    "gaming": {
        "name": "Gaming",
        "description": "Performance maximale — puissance et ventilation au max",
        "power_percent": 100,        # 100% du TDP max
        "fan_target": "aggressive",  # Ventilation agressive pour refroidir
        "priority": "performance",
    },
    "ia-training": {
        "name": "IA-Training",
        "description": "Charge soutenue — puissance elevee, ventilation moderee",
        "power_percent": 90,         # 90% du TDP pour limiter la chaleur en continu
        "fan_target": "sustained",   # Ventilation soutenue mais pas maximale
        "priority": "throughput",
    },
    "inference": {
        "name": "Inference",
        "description": "Equilibre — puissance moderee, ventilation auto",
        "power_percent": 75,         # 75% du TDP, suffisant pour l'inference
        "fan_target": "balanced",    # Laisser le pilote gerer
        "priority": "efficiency",
    },
    "eco": {
        "name": "Eco",
        "description": "Economie d'energie — puissance minimale, silence",
        "power_percent": 50,         # 50% du TDP, consommation reduite
        "fan_target": "quiet",       # Ventilation minimale, silence prioritaire
        "priority": "power_saving",
    },
}

# --- Seuils thermiques (en degres Celsius) ---
THERMAL_THRESHOLDS = {
    "optimal": 55,      # En dessous: tout va bien
    "normal": 70,       # 55-70: charge normale
    "warning": 80,      # 70-80: attention, surveiller
    "critical": 90,     # 80-90: critique, reduire la charge
    "emergency": 95,    # 90+: urgence, risque de throttling/shutdown
}


def _init_db():
    """Initialise la base de donnees SQLite avec les tables necessaires."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Table des snapshots GPU (historique des lectures)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gpu_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            gpu_index INTEGER NOT NULL,
            gpu_name TEXT,
            temperature_c REAL,
            power_draw_w REAL,
            power_limit_w REAL,
            memory_used_mb REAL,
            memory_total_mb REAL,
            utilization_pct REAL,
            clock_mhz REAL
        )
    """)

    # Table des profils appliques (journal des changements)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            gpu_index INTEGER NOT NULL,
            profile_name TEXT NOT NULL,
            power_limit_set_w REAL,
            previous_power_limit_w REAL,
            success INTEGER NOT NULL DEFAULT 1,
            error_message TEXT
        )
    """)

    # Table des benchmarks (resultats de tests)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS benchmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            gpu_index INTEGER NOT NULL,
            gpu_name TEXT,
            duration_s REAL,
            avg_temperature_c REAL,
            max_temperature_c REAL,
            avg_power_w REAL,
            avg_utilization_pct REAL,
            avg_clock_mhz REAL,
            memory_peak_mb REAL,
            samples_count INTEGER,
            profile_active TEXT
        )
    """)

    # Table des alertes thermiques
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS thermal_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            gpu_index INTEGER NOT NULL,
            temperature_c REAL NOT NULL,
            severity TEXT NOT NULL,
            message TEXT
        )
    """)

    conn.commit()
    conn.close()


def _run_nvidia_smi(args_list):
    """
    Execute nvidia-smi avec les arguments donnes.
    Retourne la sortie brute (stdout) ou leve une exception en cas d'erreur.
    """
    cmd = ["nvidia-smi"] + args_list
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"nvidia-smi a echoue (code {result.returncode}): {result.stderr.strip()}"
            )
        return result.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError(
            "nvidia-smi introuvable. Verifiez que les pilotes NVIDIA sont installes "
            "et que nvidia-smi est dans le PATH."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("nvidia-smi timeout apres 15 secondes.")


def _parse_value(raw, value_type="float"):
    """
    Parse une valeur brute de nvidia-smi.
    Gere les unites (W, MiB, MHz, %) et les valeurs manquantes.
    """
    if not raw or raw.strip() in ("[N/A]", "N/A", "[Not Supported]", ""):
        return None
    # Nettoyer les unites courantes
    cleaned = raw.strip()
    for suffix in (" W", " MiB", " MHz", " %", " C"):
        cleaned = cleaned.replace(suffix, "")
    cleaned = cleaned.strip()
    try:
        if value_type == "float":
            return float(cleaned)
        elif value_type == "int":
            return int(float(cleaned))
        return cleaned
    except (ValueError, TypeError):
        return None


def query_gpus():
    """
    Interroge tous les GPU disponibles et retourne leurs informations.
    Utilise une seule commande nvidia-smi avec format CSV.
    """
    # Requete des metriques principales
    query_fields = (
        "name,index,temperature.gpu,power.draw,power.limit,"
        "memory.used,memory.total,utilization.gpu,"
        "clocks.current.graphics,fan.speed,pstate,"
        "power.max_limit,power.min_limit,power.default_limit"
    )
    raw = _run_nvidia_smi([
        f"--query-gpu={query_fields}",
        "--format=csv,noheader,nounits"
    ])

    gpus = []
    for line in raw.split("\n"):
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 14:
            # Completer avec des valeurs nulles si certaines colonnes manquent
            parts.extend([""] * (14 - len(parts)))

        gpu = {
            "name": parts[0].strip(),
            "index": _parse_value(parts[1], "int") or 0,
            "temperature_c": _parse_value(parts[2]),
            "power_draw_w": _parse_value(parts[3]),
            "power_limit_w": _parse_value(parts[4]),
            "memory_used_mb": _parse_value(parts[5]),
            "memory_total_mb": _parse_value(parts[6]),
            "utilization_pct": _parse_value(parts[7]),
            "clock_mhz": _parse_value(parts[8]),
            "fan_speed_pct": _parse_value(parts[9]),
            "pstate": parts[10].strip() if parts[10].strip() not in ("[N/A]", "") else None,
            "power_max_limit_w": _parse_value(parts[11]),
            "power_min_limit_w": _parse_value(parts[12]),
            "power_default_limit_w": _parse_value(parts[13]),
        }

        # Calculs derives
        if gpu["memory_total_mb"] and gpu["memory_used_mb"]:
            gpu["memory_free_mb"] = round(gpu["memory_total_mb"] - gpu["memory_used_mb"], 1)
            gpu["memory_usage_pct"] = round(
                (gpu["memory_used_mb"] / gpu["memory_total_mb"]) * 100, 1
            )
        else:
            gpu["memory_free_mb"] = None
            gpu["memory_usage_pct"] = None

        # Classification thermique
        temp = gpu["temperature_c"]
        if temp is not None:
            if temp < THERMAL_THRESHOLDS["optimal"]:
                gpu["thermal_status"] = "optimal"
            elif temp < THERMAL_THRESHOLDS["normal"]:
                gpu["thermal_status"] = "normal"
            elif temp < THERMAL_THRESHOLDS["warning"]:
                gpu["thermal_status"] = "warning"
            elif temp < THERMAL_THRESHOLDS["critical"]:
                gpu["thermal_status"] = "critical"
            else:
                gpu["thermal_status"] = "emergency"
        else:
            gpu["thermal_status"] = "unknown"

        gpus.append(gpu)

    return gpus


def _save_snapshot(gpus):
    """Enregistre un snapshot de l'etat des GPU dans la base de donnees."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    ts = datetime.now().isoformat()
    for gpu in gpus:
        cursor.execute("""
            INSERT INTO gpu_snapshots
                (timestamp, gpu_index, gpu_name, temperature_c, power_draw_w,
                 power_limit_w, memory_used_mb, memory_total_mb,
                 utilization_pct, clock_mhz)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ts, gpu["index"], gpu["name"], gpu["temperature_c"],
            gpu["power_draw_w"], gpu["power_limit_w"],
            gpu["memory_used_mb"], gpu["memory_total_mb"],
            gpu["utilization_pct"], gpu["clock_mhz"],
        ))
    conn.commit()
    conn.close()


def cmd_status(args):
    """
    Affiche le statut actuel de tous les GPU.
    Enregistre un snapshot dans la base de donnees.
    """
    try:
        gpus = query_gpus()
    except RuntimeError as e:
        return {"success": False, "error": str(e)}

    _init_db()
    _save_snapshot(gpus)

    # Recuperer les dernieres alertes thermiques (24h)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM thermal_alerts
        WHERE timestamp > datetime('now', '-1 day')
    """)
    recent_alerts = cursor.fetchone()[0]

    # Nombre total de snapshots enregistres
    cursor.execute("SELECT COUNT(*) FROM gpu_snapshots")
    total_snapshots = cursor.fetchone()[0]
    conn.close()

    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "gpu_count": len(gpus),
        "gpus": gpus,
        "thermal_thresholds": THERMAL_THRESHOLDS,
        "recent_alerts_24h": recent_alerts,
        "total_snapshots": total_snapshots,
        "db_path": str(DB_PATH),
    }


def cmd_profile(args):
    """
    Affiche les profils disponibles ou applique un profil a un GPU specifique.
    """
    profile_name = args.name.lower() if args.name else None
    gpu_index = args.gpu

    # Si aucun profil specifie, lister les profils disponibles
    if not profile_name:
        return {
            "success": True,
            "action": "list_profiles",
            "profiles": PROFILES,
            "usage": "Utilisez --profile --name <profil> [--gpu <index>] pour appliquer",
        }

    # Verifier que le profil existe
    if profile_name not in PROFILES:
        return {
            "success": False,
            "error": f"Profil '{profile_name}' inconnu",
            "available": list(PROFILES.keys()),
        }

    profile = PROFILES[profile_name]

    # Lire l'etat actuel du GPU cible
    try:
        gpus = query_gpus()
    except RuntimeError as e:
        return {"success": False, "error": str(e)}

    # Selectionner le GPU cible
    target_gpu = None
    for gpu in gpus:
        if gpu["index"] == gpu_index:
            target_gpu = gpu
            break

    if target_gpu is None:
        return {
            "success": False,
            "error": f"GPU index {gpu_index} introuvable",
            "available_gpus": [{"index": g["index"], "name": g["name"]} for g in gpus],
        }

    # Calculer la nouvelle limite de puissance
    max_power = target_gpu.get("power_max_limit_w")
    min_power = target_gpu.get("power_min_limit_w")
    current_power = target_gpu.get("power_limit_w")

    if max_power is None:
        return {
            "success": False,
            "error": "Impossible de determiner la puissance max du GPU",
        }

    # Appliquer le pourcentage du profil
    target_power = round(max_power * (profile["power_percent"] / 100), 1)

    # Respecter les bornes min/max du GPU
    if min_power and target_power < min_power:
        target_power = min_power
    if target_power > max_power:
        target_power = max_power

    # Appliquer la limite de puissance via nvidia-smi
    _init_db()
    success = True
    error_msg = None

    try:
        _run_nvidia_smi(["-i", str(gpu_index), "-pl", str(target_power)])
    except RuntimeError as e:
        success = False
        error_msg = str(e)

    # Enregistrer dans l'historique
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO profile_history
            (timestamp, gpu_index, profile_name, power_limit_set_w,
             previous_power_limit_w, success, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(), gpu_index, profile_name,
        target_power, current_power, 1 if success else 0, error_msg,
    ))
    conn.commit()
    conn.close()

    result = {
        "success": success,
        "action": "apply_profile",
        "profile": profile,
        "gpu_index": gpu_index,
        "gpu_name": target_gpu["name"],
        "power_limit": {
            "previous_w": current_power,
            "target_w": target_power,
            "max_w": max_power,
            "min_w": min_power,
        },
    }
    if error_msg:
        result["error"] = error_msg
        result["hint"] = (
            "L'application de la limite de puissance necessite des privileges "
            "administrateur. Relancez le script en tant qu'administrateur."
        )

    return result


def cmd_benchmark(args):
    """
    Lance un benchmark GPU: echantillonne les metriques pendant une duree donnee.
    Compare avec les benchmarks precedents si disponibles.
    """
    duration = args.duration
    interval = args.interval
    gpu_index = args.gpu

    # Verifier la disponibilite du GPU
    try:
        gpus = query_gpus()
    except RuntimeError as e:
        return {"success": False, "error": str(e)}

    target_gpu = None
    for gpu in gpus:
        if gpu["index"] == gpu_index:
            target_gpu = gpu
            break

    if target_gpu is None:
        return {
            "success": False,
            "error": f"GPU index {gpu_index} introuvable",
        }

    # Collecter des echantillons pendant la duree specifiee
    samples = []
    start_time = time.time()
    sample_count = 0

    while (time.time() - start_time) < duration:
        try:
            current_gpus = query_gpus()
            for g in current_gpus:
                if g["index"] == gpu_index:
                    samples.append({
                        "elapsed_s": round(time.time() - start_time, 2),
                        "temperature_c": g["temperature_c"],
                        "power_draw_w": g["power_draw_w"],
                        "utilization_pct": g["utilization_pct"],
                        "clock_mhz": g["clock_mhz"],
                        "memory_used_mb": g["memory_used_mb"],
                    })
                    sample_count += 1
                    break
        except RuntimeError:
            pass  # Ignorer les erreurs transitoires pendant le benchmark
        time.sleep(interval)

    elapsed = round(time.time() - start_time, 2)

    if not samples:
        return {
            "success": False,
            "error": "Aucun echantillon collecte pendant le benchmark",
        }

    # Calculer les statistiques
    def _safe_avg(key):
        """Moyenne securisee (ignore les valeurs None)."""
        vals = [s[key] for s in samples if s[key] is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    def _safe_max(key):
        """Maximum securise (ignore les valeurs None)."""
        vals = [s[key] for s in samples if s[key] is not None]
        return max(vals) if vals else None

    def _safe_min(key):
        """Minimum securise (ignore les valeurs None)."""
        vals = [s[key] for s in samples if s[key] is not None]
        return min(vals) if vals else None

    stats = {
        "temperature": {
            "avg_c": _safe_avg("temperature_c"),
            "max_c": _safe_max("temperature_c"),
            "min_c": _safe_min("temperature_c"),
        },
        "power": {
            "avg_w": _safe_avg("power_draw_w"),
            "max_w": _safe_max("power_draw_w"),
            "min_w": _safe_min("power_draw_w"),
        },
        "utilization": {
            "avg_pct": _safe_avg("utilization_pct"),
            "max_pct": _safe_max("utilization_pct"),
        },
        "clock": {
            "avg_mhz": _safe_avg("clock_mhz"),
            "max_mhz": _safe_max("clock_mhz"),
        },
        "memory": {
            "peak_mb": _safe_max("memory_used_mb"),
        },
    }

    # Sauvegarder le benchmark dans la base
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO benchmarks
            (timestamp, gpu_index, gpu_name, duration_s,
             avg_temperature_c, max_temperature_c, avg_power_w,
             avg_utilization_pct, avg_clock_mhz, memory_peak_mb,
             samples_count, profile_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(), gpu_index, target_gpu["name"],
        elapsed, stats["temperature"]["avg_c"], stats["temperature"]["max_c"],
        stats["power"]["avg_w"], stats["utilization"]["avg_pct"],
        stats["clock"]["avg_mhz"], stats["memory"]["peak_mb"],
        sample_count, None,
    ))
    benchmark_id = cursor.lastrowid

    # Recuperer les benchmarks precedents pour comparaison
    cursor.execute("""
        SELECT id, timestamp, duration_s, avg_temperature_c,
               avg_power_w, avg_utilization_pct, avg_clock_mhz, samples_count
        FROM benchmarks
        WHERE gpu_index = ? AND id != ?
        ORDER BY id DESC LIMIT 5
    """, (gpu_index, benchmark_id))

    previous_benchmarks = []
    for row in cursor.fetchall():
        previous_benchmarks.append({
            "id": row[0],
            "timestamp": row[1],
            "duration_s": row[2],
            "avg_temperature_c": row[3],
            "avg_power_w": row[4],
            "avg_utilization_pct": row[5],
            "avg_clock_mhz": row[6],
            "samples_count": row[7],
        })

    conn.commit()
    conn.close()

    return {
        "success": True,
        "action": "benchmark",
        "benchmark_id": benchmark_id,
        "gpu_index": gpu_index,
        "gpu_name": target_gpu["name"],
        "duration_s": elapsed,
        "samples_count": sample_count,
        "interval_s": interval,
        "statistics": stats,
        "previous_benchmarks": previous_benchmarks,
        "comparison_note": (
            "Comparez avg_temperature et avg_clock avec les benchmarks precedents "
            "pour detecter une degradation thermique."
        ) if previous_benchmarks else "Premier benchmark enregistre pour ce GPU.",
    }


def cmd_thermal(args):
    """
    Monitoring thermique: verifie les temperatures, genere des alertes,
    et affiche l'historique thermique.
    """
    try:
        gpus = query_gpus()
    except RuntimeError as e:
        return {"success": False, "error": str(e)}

    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Enregistrer un snapshot
    _save_snapshot(gpus)

    # Verifier les seuils et generer des alertes
    alerts = []
    for gpu in gpus:
        temp = gpu.get("temperature_c")
        if temp is None:
            continue

        # Determiner la severite
        severity = None
        message = None

        if temp >= THERMAL_THRESHOLDS["emergency"]:
            severity = "emergency"
            message = (
                f"GPU {gpu['index']} ({gpu['name']}): {temp}C — URGENCE! "
                f"Risque de throttling/shutdown. Reduisez la charge immediatement."
            )
        elif temp >= THERMAL_THRESHOLDS["critical"]:
            severity = "critical"
            message = (
                f"GPU {gpu['index']} ({gpu['name']}): {temp}C — CRITIQUE. "
                f"Temperature trop elevee, envisagez un profil Eco."
            )
        elif temp >= THERMAL_THRESHOLDS["warning"]:
            severity = "warning"
            message = (
                f"GPU {gpu['index']} ({gpu['name']}): {temp}C — ATTENTION. "
                f"Temperature elevee, surveillez la charge."
            )

        if severity:
            cursor.execute("""
                INSERT INTO thermal_alerts
                    (timestamp, gpu_index, temperature_c, severity, message)
                VALUES (?, ?, ?, ?, ?)
            """, (datetime.now().isoformat(), gpu["index"], temp, severity, message))
            alerts.append({
                "gpu_index": gpu["index"],
                "temperature_c": temp,
                "severity": severity,
                "message": message,
            })

    # Recuperer l'historique thermique recent (derniere heure)
    cursor.execute("""
        SELECT gpu_index, timestamp, temperature_c
        FROM gpu_snapshots
        WHERE timestamp > datetime('now', '-1 hour')
        ORDER BY timestamp DESC
        LIMIT 60
    """)
    recent_history = []
    for row in cursor.fetchall():
        recent_history.append({
            "gpu_index": row[0],
            "timestamp": row[1],
            "temperature_c": row[2],
        })

    # Statistiques thermiques (dernieres 24h)
    cursor.execute("""
        SELECT gpu_index,
               MIN(temperature_c) as min_temp,
               AVG(temperature_c) as avg_temp,
               MAX(temperature_c) as max_temp,
               COUNT(*) as readings
        FROM gpu_snapshots
        WHERE timestamp > datetime('now', '-1 day')
              AND temperature_c IS NOT NULL
        GROUP BY gpu_index
    """)
    thermal_stats_24h = {}
    for row in cursor.fetchall():
        thermal_stats_24h[row[0]] = {
            "min_c": round(row[1], 1) if row[1] else None,
            "avg_c": round(row[2], 1) if row[2] else None,
            "max_c": round(row[3], 1) if row[3] else None,
            "readings": row[4],
        }

    # Nombre d'alertes par severite (dernieres 24h)
    cursor.execute("""
        SELECT severity, COUNT(*)
        FROM thermal_alerts
        WHERE timestamp > datetime('now', '-1 day')
        GROUP BY severity
    """)
    alert_counts = dict(cursor.fetchall())

    conn.commit()
    conn.close()

    # Resume thermique par GPU
    thermal_summary = []
    for gpu in gpus:
        summary = {
            "gpu_index": gpu["index"],
            "gpu_name": gpu["name"],
            "current_temp_c": gpu["temperature_c"],
            "thermal_status": gpu["thermal_status"],
            "fan_speed_pct": gpu.get("fan_speed_pct"),
            "power_draw_w": gpu["power_draw_w"],
            "power_limit_w": gpu["power_limit_w"],
        }
        if gpu["index"] in thermal_stats_24h:
            summary["stats_24h"] = thermal_stats_24h[gpu["index"]]
        thermal_summary.append(summary)

    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "thresholds": THERMAL_THRESHOLDS,
        "gpu_thermal_summary": thermal_summary,
        "active_alerts": alerts,
        "alert_counts_24h": alert_counts,
        "recent_readings_1h": len(recent_history),
    }


def cmd_optimize(args):
    """
    Optimisation automatique: analyse l'etat actuel et suggere/applique
    le profil optimal en fonction de la charge et de la temperature.
    """
    try:
        gpus = query_gpus()
    except RuntimeError as e:
        return {"success": False, "error": str(e)}

    gpu_index = args.gpu
    auto_apply = args.apply

    # Trouver le GPU cible
    target_gpu = None
    for gpu in gpus:
        if gpu["index"] == gpu_index:
            target_gpu = gpu
            break

    if target_gpu is None:
        return {
            "success": False,
            "error": f"GPU index {gpu_index} introuvable",
        }

    # Analyser l'etat actuel pour recommander un profil
    temp = target_gpu.get("temperature_c", 0) or 0
    utilization = target_gpu.get("utilization_pct", 0) or 0
    memory_pct = target_gpu.get("memory_usage_pct", 0) or 0

    # Logique de decision du profil optimal
    recommended_profile = None
    reasoning = []

    if temp >= THERMAL_THRESHOLDS["critical"]:
        recommended_profile = "eco"
        reasoning.append(
            f"Temperature critique ({temp}C >= {THERMAL_THRESHOLDS['critical']}C) "
            f"— profil Eco recommande pour reduire la chaleur."
        )
    elif temp >= THERMAL_THRESHOLDS["warning"]:
        recommended_profile = "inference"
        reasoning.append(
            f"Temperature elevee ({temp}C >= {THERMAL_THRESHOLDS['warning']}C) "
            f"— profil Inference pour equilibrer performances et thermique."
        )
    elif utilization > 90 and memory_pct > 80:
        recommended_profile = "ia-training"
        reasoning.append(
            f"Charge elevee soutenue (GPU {utilization}%, VRAM {memory_pct}%) "
            f"— profil IA-Training pour charge continue."
        )
    elif utilization > 70:
        recommended_profile = "gaming"
        reasoning.append(
            f"Charge importante (GPU {utilization}%) avec temperature correcte ({temp}C) "
            f"— profil Gaming pour performance maximale."
        )
    elif utilization < 20 and temp < THERMAL_THRESHOLDS["optimal"]:
        recommended_profile = "eco"
        reasoning.append(
            f"Charge faible (GPU {utilization}%, {temp}C) "
            f"— profil Eco pour economiser l'energie."
        )
    else:
        recommended_profile = "inference"
        reasoning.append(
            f"Charge moderee (GPU {utilization}%, {temp}C) "
            f"— profil Inference pour un bon equilibre."
        )

    result = {
        "success": True,
        "action": "optimize",
        "gpu_index": gpu_index,
        "gpu_name": target_gpu["name"],
        "current_state": {
            "temperature_c": temp,
            "utilization_pct": utilization,
            "memory_usage_pct": memory_pct,
            "power_draw_w": target_gpu["power_draw_w"],
            "power_limit_w": target_gpu["power_limit_w"],
            "thermal_status": target_gpu["thermal_status"],
        },
        "recommendation": {
            "profile": recommended_profile,
            "profile_details": PROFILES[recommended_profile],
            "reasoning": reasoning,
        },
        "auto_applied": False,
    }

    # Appliquer automatiquement si demande
    if auto_apply:
        # Simuler l'application du profil via cmd_profile
        apply_args = argparse.Namespace(name=recommended_profile, gpu=gpu_index)
        apply_result = cmd_profile(apply_args)
        result["auto_applied"] = True
        result["apply_result"] = apply_result

    return result


def main():
    """Point d'entree principal — parsing des arguments et dispatch."""
    parser = argparse.ArgumentParser(
        description="GPU Optimizer — Gestion avancee des GPU NVIDIA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  %(prog)s --status                          Statut de tous les GPU
  %(prog)s --profile                         Lister les profils disponibles
  %(prog)s --profile --name gaming --gpu 0   Appliquer le profil Gaming au GPU 0
  %(prog)s --benchmark --duration 30         Benchmark de 30 secondes
  %(prog)s --thermal                         Monitoring thermique
  %(prog)s --optimize --gpu 0                Recommandation automatique
  %(prog)s --optimize --gpu 0 --apply        Appliquer la recommandation
        """,
    )

    # Actions principales (mutuellement exclusives)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--status", action="store_true",
        help="Afficher le statut actuel de tous les GPU",
    )
    group.add_argument(
        "--profile", action="store_true",
        help="Gerer les profils d'optimisation (lister ou appliquer)",
    )
    group.add_argument(
        "--benchmark", action="store_true",
        help="Lancer un benchmark GPU avec collecte de metriques",
    )
    group.add_argument(
        "--thermal", action="store_true",
        help="Monitoring thermique avec alertes et historique",
    )
    group.add_argument(
        "--optimize", action="store_true",
        help="Analyser et recommander le profil optimal",
    )

    # Options supplementaires
    parser.add_argument(
        "--gpu", type=int, default=0,
        help="Index du GPU cible (defaut: 0)",
    )
    parser.add_argument(
        "--name", type=str, default=None,
        help="Nom du profil a appliquer (gaming, ia-training, inference, eco)",
    )
    parser.add_argument(
        "--duration", type=int, default=10,
        help="Duree du benchmark en secondes (defaut: 10)",
    )
    parser.add_argument(
        "--interval", type=float, default=1.0,
        help="Intervalle d'echantillonnage du benchmark en secondes (defaut: 1.0)",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Appliquer automatiquement la recommandation (avec --optimize)",
    )

    args = parser.parse_args()

    # Initialiser la base de donnees
    _init_db()

    # Dispatcher vers la commande appropriee
    if args.status:
        result = cmd_status(args)
    elif args.profile:
        result = cmd_profile(args)
    elif args.benchmark:
        result = cmd_benchmark(args)
    elif args.thermal:
        result = cmd_thermal(args)
    elif args.optimize:
        result = cmd_optimize(args)
    else:
        result = {"success": False, "error": "Action non reconnue"}

    # Sortie JSON formatee
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    sys.exit(0 if result.get("success", False) else 1)


if __name__ == "__main__":
    main()
