#!/usr/bin/env python3
"""
Network Optimizer — Optimiseur reseau pour le cluster IA distribue.

Mesure latence, bande passante, MTU et recommandations TCP entre les noeuds.
Utilise subprocess: ping, netsh, pathping.

Stdlib uniquement. Sortie JSON.
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path

# --- Configuration du cluster ---

# Repertoire de base pour la base de donnees
DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "network.db"

# Noeuds du cluster avec leurs IPs
CLUSTER_NODES = {
    "M1": {
        "ip": "127.0.0.1",
        "port": 1234,
        "description": "LM Studio local — qwen3-8b (6 GPU 46GB)",
        "type": "lmstudio"
    },
    "M2": {
        "ip": "192.168.1.26",
        "port": 1234,
        "description": "LM Studio distant — deepseek-coder-v2 (3 GPU 24GB)",
        "type": "lmstudio"
    },
    "M3": {
        "ip": "192.168.1.113",
        "port": 1234,
        "description": "LM Studio distant — deepseek-r1 (1 GPU 8GB)",
        "type": "lmstudio"
    },
    "OL1": {
        "ip": "127.0.0.1",
        "port": 11434,
        "description": "Ollama local — qwen3:1.7b + cloud models",
        "type": "ollama"
    }
}

# Seuils de qualite reseau (en ms)
LATENCY_THRESHOLDS = {
    "excellent": 1.0,    # < 1ms (local)
    "good": 5.0,         # < 5ms (LAN rapide)
    "acceptable": 20.0,  # < 20ms (LAN normal)
    "poor": 50.0,        # < 50ms (LAN degrade)
    "critical": 100.0    # >= 100ms (probleme)
}

# Taille MTU standard et jumbo
MTU_STANDARD = 1500
MTU_JUMBO = 9000

# Nombre de pings par test de latence
PING_COUNT = 10
# Tailles de paquets pour estimation bande passante (octets)
BANDWIDTH_PACKET_SIZES = [64, 512, 1024, 4096, 8192, 32768]


# --- Base de donnees ---

def init_db():
    """Initialise la base SQLite avec les tables de metriques reseau."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()

    # Table des mesures de latence
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS latency_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            source TEXT DEFAULT 'localhost',
            target_node TEXT NOT NULL,
            target_ip TEXT NOT NULL,
            packets_sent INTEGER,
            packets_received INTEGER,
            packet_loss_pct REAL,
            min_ms REAL,
            avg_ms REAL,
            max_ms REAL,
            jitter_ms REAL,
            quality TEXT
        )
    """)

    # Table des estimations de bande passante
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bandwidth_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            target_node TEXT NOT NULL,
            target_ip TEXT NOT NULL,
            packet_size INTEGER,
            latency_ms REAL,
            estimated_throughput_mbps REAL,
            quality TEXT
        )
    """)

    # Table des verifications MTU
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mtu_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            target_node TEXT NOT NULL,
            target_ip TEXT NOT NULL,
            max_mtu INTEGER,
            supports_jumbo INTEGER DEFAULT 0,
            fragmentation_detected INTEGER DEFAULT 0
        )
    """)

    # Table des recommandations TCP
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tcp_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            parameter TEXT NOT NULL,
            current_value TEXT,
            recommended_value TEXT,
            status TEXT,
            description TEXT
        )
    """)

    # Table des rapports complets
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            report_type TEXT NOT NULL,
            content TEXT NOT NULL,
            score INTEGER
        )
    """)

    conn.commit()
    conn.close()


def get_db():
    """Retourne une connexion SQLite configuree."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _now():
    """Retourne le timestamp ISO 8601 UTC courant."""
    return datetime.now(timezone.utc).isoformat()


# --- Utilitaires subprocess ---

def _run_cmd(cmd, timeout=30):
    """
    Execute une commande systeme et retourne stdout/stderr.
    Gere les erreurs et timeouts proprement.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=True,
            encoding="utf-8",
            errors="replace"
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": f"Timeout apres {timeout}s"}
    except Exception as e:
        return {"returncode": -1, "stdout": "", "stderr": str(e)}


def _classify_latency(avg_ms):
    """Classifie la qualite de la latence selon les seuils."""
    if avg_ms is None:
        return "unknown"
    for quality, threshold in LATENCY_THRESHOLDS.items():
        if avg_ms < threshold:
            return quality
    return "critical"


# --- Mesure de latence (ping) ---

def measure_latency(node_name, count=PING_COUNT):
    """
    Mesure la latence vers un noeud avec ping Windows.
    Retourne les statistiques detaillees.
    """
    node = CLUSTER_NODES[node_name]
    ip = node["ip"]

    result = {
        "node": node_name,
        "ip": ip,
        "description": node["description"],
        "timestamp": _now(),
        "packets_sent": count,
        "packets_received": 0,
        "packet_loss_pct": 100.0,
        "min_ms": None,
        "avg_ms": None,
        "max_ms": None,
        "jitter_ms": None,
        "quality": "unknown",
        "error": None
    }

    # Commande ping Windows: -n count, -w timeout_ms
    cmd = f"ping -n {count} -w 2000 {ip}"
    output = _run_cmd(cmd, timeout=count * 3 + 10)

    if output["returncode"] != 0 and not output["stdout"]:
        result["error"] = output["stderr"] or "Ping echoue"
        result["quality"] = "offline"
        _save_latency(result)
        return result

    stdout = output["stdout"]

    # Parser les statistiques de ping Windows (format francais et anglais)
    # Paquets: envoyes = 10, recus = 10, perdus = 0
    # Packets: Sent = 10, Received = 10, Lost = 0
    pkt_match = re.search(
        r'(?:envoy|sent)\s*=\s*(\d+).*?(?:re[cç]us?|received)\s*=\s*(\d+).*?(?:perdus?|lost)\s*=\s*(\d+)',
        stdout, re.IGNORECASE
    )
    if pkt_match:
        result["packets_sent"] = int(pkt_match.group(1))
        result["packets_received"] = int(pkt_match.group(2))
        lost = int(pkt_match.group(3))
        total = result["packets_sent"]
        result["packet_loss_pct"] = round((lost / total * 100) if total > 0 else 100, 1)

    # Parser les temps: Minimum = 0ms, Maximum = 1ms, Moyenne = 0ms
    # Minimum = 0ms, Maximum = 1ms, Average = 0ms
    time_match = re.search(
        r'(?:minimum|min)\s*=\s*(\d+)\s*ms.*?(?:maximum|max)\s*=\s*(\d+)\s*ms.*?(?:moyenne|average|avg)\s*=\s*(\d+)\s*ms',
        stdout, re.IGNORECASE
    )
    if time_match:
        result["min_ms"] = float(time_match.group(1))
        result["max_ms"] = float(time_match.group(2))
        result["avg_ms"] = float(time_match.group(3))
        # Jitter estime comme (max - min) / 2
        result["jitter_ms"] = round((result["max_ms"] - result["min_ms"]) / 2, 2)

    # Fallback: parser les lignes individuelles de reponse pour calculer la moyenne
    if result["avg_ms"] is None:
        times = re.findall(r'(?:temps|time)[=<]\s*(\d+)\s*ms', stdout, re.IGNORECASE)
        if times:
            values = [float(t) for t in times]
            result["min_ms"] = min(values)
            result["max_ms"] = max(values)
            result["avg_ms"] = round(sum(values) / len(values), 2)
            result["jitter_ms"] = round((max(values) - min(values)) / 2, 2)
            result["packets_received"] = len(values)
            result["packet_loss_pct"] = round(
                (1 - len(values) / count) * 100, 1
            )

    # Classifier la qualite
    result["quality"] = _classify_latency(result["avg_ms"])

    # Sauvegarder en base
    _save_latency(result)
    return result


def _save_latency(data):
    """Enregistre une mesure de latence en base."""
    conn = get_db()
    conn.execute("""
        INSERT INTO latency_tests
        (timestamp, target_node, target_ip, packets_sent, packets_received,
         packet_loss_pct, min_ms, avg_ms, max_ms, jitter_ms, quality)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (data["timestamp"], data["node"], data["ip"],
          data["packets_sent"], data["packets_received"],
          data["packet_loss_pct"], data["min_ms"], data["avg_ms"],
          data["max_ms"], data["jitter_ms"], data["quality"]))
    conn.commit()
    conn.close()


def measure_all_latency():
    """Mesure la latence vers tous les noeuds en parallele."""
    results = {}
    threads = []
    lock = threading.Lock()

    def _measure(name):
        r = measure_latency(name)
        with lock:
            results[name] = r

    for node_name in CLUSTER_NODES:
        t = threading.Thread(target=_measure, args=(node_name,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=60)

    return results


# --- Estimation de bande passante ---

def estimate_bandwidth(node_name):
    """
    Estime la bande passante vers un noeud en envoyant des pings de taille variable.
    Methode: mesure du delta de latence entre petits et gros paquets.
    """
    node = CLUSTER_NODES[node_name]
    ip = node["ip"]

    result = {
        "node": node_name,
        "ip": ip,
        "timestamp": _now(),
        "measurements": [],
        "estimated_bandwidth_mbps": None,
        "quality": "unknown",
        "error": None
    }

    latencies = []
    for size in BANDWIDTH_PACKET_SIZES:
        # ping -n 3 -l SIZE -w 2000 IP
        # -l definit la taille du buffer d'envoi (max ~65500 pour ping Windows)
        effective_size = min(size, 65000)
        cmd = f"ping -n 3 -l {effective_size} -w 2000 {ip}"
        output = _run_cmd(cmd, timeout=15)

        avg_ms = None
        if output["stdout"]:
            # Parser le temps moyen
            time_match = re.search(
                r'(?:moyenne|average|avg)\s*=\s*(\d+)\s*ms',
                output["stdout"], re.IGNORECASE
            )
            if time_match:
                avg_ms = float(time_match.group(1))
            else:
                # Fallback: parser les temps individuels
                times = re.findall(r'(?:temps|time)[=<]\s*(\d+)\s*ms', output["stdout"], re.IGNORECASE)
                if times:
                    avg_ms = sum(float(t) for t in times) / len(times)

        measurement = {
            "packet_size_bytes": effective_size,
            "avg_latency_ms": round(avg_ms, 2) if avg_ms is not None else None
        }
        result["measurements"].append(measurement)

        if avg_ms is not None:
            latencies.append((effective_size, avg_ms))

        # Sauvegarder chaque mesure
        if avg_ms is not None:
            conn = get_db()
            conn.execute("""
                INSERT INTO bandwidth_tests
                (timestamp, target_node, target_ip, packet_size, latency_ms,
                 estimated_throughput_mbps, quality)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (result["timestamp"], node_name, ip, effective_size, avg_ms, None, "measured"))
            conn.commit()
            conn.close()

    # Estimer la bande passante a partir de la pente latence/taille
    if len(latencies) >= 2:
        # Regression lineaire simple: latence = a * taille + b
        # Bande passante ≈ 1 / a (en octets/ms → convertir en Mbps)
        sizes = [l[0] for l in latencies]
        times_ms = [l[1] for l in latencies]

        # Si les latences sont toutes identiques (loopback), indiquer max
        if max(times_ms) == min(times_ms):
            result["estimated_bandwidth_mbps"] = 10000.0  # Loopback = quasi-infini
            result["quality"] = "loopback"
        else:
            n = len(latencies)
            sum_x = sum(sizes)
            sum_y = sum(times_ms)
            sum_xy = sum(s * t for s, t in latencies)
            sum_x2 = sum(s * s for s in sizes)

            denom = n * sum_x2 - sum_x * sum_x
            if denom != 0:
                slope = (n * sum_xy - sum_x * sum_y) / denom
                if slope > 0:
                    # slope en ms/octet → bande passante en octets/ms → Mbps
                    bytes_per_ms = 1.0 / slope
                    mbps = bytes_per_ms * 8 / 1000  # octets/ms → bits/s → Mbps
                    result["estimated_bandwidth_mbps"] = round(mbps, 2)
                else:
                    # Pente negative = fluctuations, prendre estimation haute
                    result["estimated_bandwidth_mbps"] = 1000.0
                    result["quality"] = "estimated"
            else:
                result["estimated_bandwidth_mbps"] = None

    # Classifier la qualite de la bande passante
    if result["estimated_bandwidth_mbps"] is not None:
        bw = result["estimated_bandwidth_mbps"]
        if bw >= 1000:
            result["quality"] = "excellent" if result["quality"] == "unknown" else result["quality"]
        elif bw >= 100:
            result["quality"] = "good"
        elif bw >= 10:
            result["quality"] = "acceptable"
        else:
            result["quality"] = "poor"

    return result


# --- Verification MTU ---

def check_mtu(node_name):
    """
    Determine le MTU maximum vers un noeud par recherche dichotomique.
    Utilise ping -f (don't fragment) avec des tailles decroissantes.
    """
    node = CLUSTER_NODES[node_name]
    ip = node["ip"]

    result = {
        "node": node_name,
        "ip": ip,
        "timestamp": _now(),
        "max_mtu": MTU_STANDARD,  # Valeur par defaut
        "supports_jumbo": False,
        "fragmentation_detected": False,
        "details": [],
        "error": None
    }

    # Noeuds locaux: MTU loopback = 65535 typiquement
    if ip == "127.0.0.1":
        result["max_mtu"] = 65535
        result["supports_jumbo"] = True
        result["details"].append("Loopback: MTU maximum (65535)")
        _save_mtu(result)
        return result

    # Recherche dichotomique du MTU max
    # ping -f -n 1 -l SIZE IP : -f = ne pas fragmenter
    low = 576   # MTU minimum IP
    high = 9000  # Jumbo frame max
    best = low

    # D'abord tester le MTU standard 1472 (1500 - 28 header IP+ICMP)
    test_sizes = [1472, 4000, 8972]  # Standard, intermediaire, jumbo
    for size in test_sizes:
        cmd = f"ping -f -n 1 -l {size} -w 2000 {ip}"
        output = _run_cmd(cmd, timeout=10)
        stdout = output["stdout"]

        # Detecter fragmentation ou echec
        fragmented = "fragment" in stdout.lower() or "frag" in stdout.lower()
        success = output["returncode"] == 0 and not fragmented

        # Verifier si le paquet a ete perdu
        lost_match = re.search(r'(?:perdus?|lost)\s*=\s*(\d+)', stdout, re.IGNORECASE)
        if lost_match and int(lost_match.group(1)) > 0:
            success = False

        result["details"].append({
            "size": size,
            "success": success,
            "fragmented": fragmented
        })

        if fragmented:
            result["fragmentation_detected"] = True

    # Recherche dichotomique precise
    low = 576
    high = 8972
    while low <= high:
        mid = (low + high) // 2
        cmd = f"ping -f -n 1 -l {mid} -w 2000 {ip}"
        output = _run_cmd(cmd, timeout=5)
        stdout = output["stdout"]

        fragmented = "fragment" in stdout.lower() or "frag" in stdout.lower()
        lost_match = re.search(r'(?:perdus?|lost)\s*=\s*(\d+)', stdout, re.IGNORECASE)
        lost = int(lost_match.group(1)) if lost_match else 0
        success = output["returncode"] == 0 and not fragmented and lost == 0

        if success:
            best = mid
            low = mid + 1
        else:
            high = mid - 1

    # MTU = taille payload + 28 (20 IP header + 8 ICMP header)
    result["max_mtu"] = best + 28
    result["supports_jumbo"] = result["max_mtu"] > MTU_STANDARD

    _save_mtu(result)
    return result


def _save_mtu(data):
    """Enregistre un test MTU en base."""
    conn = get_db()
    conn.execute("""
        INSERT INTO mtu_tests
        (timestamp, target_node, target_ip, max_mtu, supports_jumbo, fragmentation_detected)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (data["timestamp"], data["node"], data["ip"],
          data["max_mtu"], 1 if data["supports_jumbo"] else 0,
          1 if data["fragmentation_detected"] else 0))
    conn.commit()
    conn.close()


# --- Configuration TCP et recommandations ---

def analyze_tcp_config():
    """
    Analyse la configuration TCP Windows et genere des recommandations.
    Utilise netsh interface tcp show global.
    """
    result = {
        "timestamp": _now(),
        "current_settings": {},
        "recommendations": [],
        "score": 100,  # Score de sante TCP (0-100)
        "error": None
    }

    # Recuperer la config TCP globale
    cmd = "netsh interface tcp show global"
    output = _run_cmd(cmd, timeout=10)

    if output["returncode"] != 0:
        result["error"] = f"netsh echoue: {output['stderr']}"
        result["score"] = 0
        return result

    tcp_output = output["stdout"]

    # Parser les parametres TCP importants
    # Format typique: "Parametre : valeur" ou "Parameter : value"
    settings = {}
    for line in tcp_output.split("\n"):
        line = line.strip()
        if ":" in line or "=" in line:
            sep = ":" if ":" in line else "="
            parts = line.split(sep, 1)
            if len(parts) == 2:
                key = parts[0].strip().lower()
                value = parts[1].strip()
                settings[key] = value

    result["current_settings"] = settings

    # Recommandations basees sur les parametres critiques
    recommendations = []

    # 1. Autotuning du buffer de reception
    autotuning_key = None
    for k in settings:
        if "auto" in k and "tuning" in k and "receive" in k.replace("réception", "receive"):
            autotuning_key = k
            break
        if "auto" in k and "tuning" in k:
            autotuning_key = k
            break

    if autotuning_key:
        val = settings[autotuning_key].lower()
        rec = {
            "parameter": "Receive Window Auto-Tuning",
            "current": val,
            "recommended": "normal",
            "status": "ok" if "normal" in val else "warning",
            "description": "L'auto-tuning de la fenetre de reception optimise dynamiquement le buffer TCP"
        }
        if "disabled" in val:
            rec["status"] = "critical"
            result["score"] -= 20
        elif "normal" not in val and "experimental" not in val:
            result["score"] -= 10
        recommendations.append(rec)

    # 2. ECN (Explicit Congestion Notification)
    ecn_key = None
    for k in settings:
        if "ecn" in k or "congestion" in k:
            ecn_key = k
            break

    if ecn_key:
        val = settings[ecn_key].lower()
        rec = {
            "parameter": "ECN Capability",
            "current": val,
            "recommended": "enabled (pour cluster LAN)",
            "status": "ok" if "enabled" in val or "activé" in val else "info",
            "description": "ECN reduit les pertes sur un LAN charge (utile pour cluster IA)"
        }
        recommendations.append(rec)

    # 3. Chimney Offload / RSS
    for k in settings:
        if "rss" in k:
            val = settings[k].lower()
            rec = {
                "parameter": "Receive-Side Scaling (RSS)",
                "current": val,
                "recommended": "enabled",
                "status": "ok" if "enabled" in val or "activé" in val else "warning",
                "description": "RSS distribue le traitement reseau sur plusieurs CPUs"
            }
            if "disabled" in val:
                result["score"] -= 15
            recommendations.append(rec)
            break

    # 4. Timestamps TCP
    for k in settings:
        if "timestamp" in k or "horodatage" in k:
            val = settings[k].lower()
            rec = {
                "parameter": "TCP Timestamps",
                "current": val,
                "recommended": "enabled",
                "status": "ok" if "enabled" in val or "activé" in val else "info",
                "description": "Les timestamps TCP ameliorent le calcul RTT et la detection de pertes"
            }
            recommendations.append(rec)
            break

    # 5. DCA (Direct Cache Access)
    for k in settings:
        if "dca" in k or "direct cache" in k:
            val = settings[k].lower()
            rec = {
                "parameter": "Direct Cache Access (DCA)",
                "current": val,
                "recommended": "enabled",
                "status": "ok" if "enabled" in val or "activé" in val else "info",
                "description": "DCA place les donnees reseau directement dans le cache CPU L2"
            }
            recommendations.append(rec)
            break

    # Recommandations generales pour cluster IA
    recommendations.append({
        "parameter": "TCP Buffer Size (recommandation)",
        "current": "systeme",
        "recommended": "4 MB minimum pour transferts IA",
        "status": "info",
        "description": "Les gros modeles IA (120B+) necessitent des buffers TCP larges pour le streaming"
    })

    recommendations.append({
        "parameter": "Nagle Algorithm",
        "current": "enabled (defaut)",
        "recommended": "disabled (TCP_NODELAY) pour faible latence cluster",
        "status": "info",
        "description": "Desactiver Nagle reduit la latence pour les petites requetes API du cluster"
    })

    result["recommendations"] = recommendations

    # Sauvegarder les recommandations
    conn = get_db()
    for rec in recommendations:
        conn.execute("""
            INSERT INTO tcp_config
            (timestamp, parameter, current_value, recommended_value, status, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (result["timestamp"], rec["parameter"], rec["current"],
              rec["recommended"], rec["status"], rec["description"]))
    conn.commit()
    conn.close()

    return result


# --- Rapport complet ---

def generate_report():
    """
    Genere un rapport complet d'optimisation reseau.
    Combine: latence, bande passante, MTU, TCP.
    """
    report = {
        "timestamp": _now(),
        "type": "full_optimization_report",
        "cluster_nodes": {},
        "tcp_analysis": None,
        "overall_score": 0,
        "recommendations_summary": [],
        "errors": []
    }

    # 1. Latence vers tous les noeuds
    print('{"status": "measuring_latency"}', file=sys.stderr)
    latency_results = measure_all_latency()

    # 2. Bande passante (seulement noeuds distants)
    print('{"status": "estimating_bandwidth"}', file=sys.stderr)
    bandwidth_results = {}
    for name, node in CLUSTER_NODES.items():
        if node["ip"] != "127.0.0.1":
            try:
                bandwidth_results[name] = estimate_bandwidth(name)
            except Exception as e:
                report["errors"].append(f"Bandwidth {name}: {e}")

    # 3. MTU
    print('{"status": "checking_mtu"}', file=sys.stderr)
    mtu_results = {}
    for name in CLUSTER_NODES:
        try:
            mtu_results[name] = check_mtu(name)
        except Exception as e:
            report["errors"].append(f"MTU {name}: {e}")

    # 4. TCP
    print('{"status": "analyzing_tcp"}', file=sys.stderr)
    tcp_result = analyze_tcp_config()
    report["tcp_analysis"] = tcp_result

    # Assembler les resultats par noeud
    scores = []
    for name in CLUSTER_NODES:
        node_report = {
            "description": CLUSTER_NODES[name]["description"],
            "ip": CLUSTER_NODES[name]["ip"],
            "latency": latency_results.get(name),
            "bandwidth": bandwidth_results.get(name),
            "mtu": mtu_results.get(name),
            "node_score": 100
        }

        # Calculer le score du noeud
        lat = latency_results.get(name, {})
        if lat.get("quality") == "offline":
            node_report["node_score"] = 0
        elif lat.get("avg_ms") is not None:
            avg = lat["avg_ms"]
            if avg < 1:
                node_report["node_score"] = 100
            elif avg < 5:
                node_report["node_score"] = 90
            elif avg < 20:
                node_report["node_score"] = 75
            elif avg < 50:
                node_report["node_score"] = 50
            else:
                node_report["node_score"] = 25

        # Penalite pour perte de paquets
        loss = lat.get("packet_loss_pct", 0)
        if loss and loss > 0:
            node_report["node_score"] -= int(loss)

        scores.append(node_report["node_score"])
        report["cluster_nodes"][name] = node_report

    # Score global = moyenne des scores noeuds + score TCP
    tcp_score = tcp_result.get("score", 50) if tcp_result else 50
    all_scores = scores + [tcp_score]
    report["overall_score"] = round(sum(all_scores) / len(all_scores)) if all_scores else 0

    # Resume des recommandations
    if tcp_result and tcp_result.get("recommendations"):
        for rec in tcp_result["recommendations"]:
            if rec["status"] in ("warning", "critical"):
                report["recommendations_summary"].append(
                    f"[{rec['status'].upper()}] {rec['parameter']}: {rec['description']}"
                )

    # Recommandations basees sur la latence
    for name, lat in latency_results.items():
        if lat.get("quality") in ("poor", "critical"):
            report["recommendations_summary"].append(
                f"[WARNING] Latence {name} ({lat.get('avg_ms', '?')}ms): verifier le cablage/switch"
            )
        if lat.get("packet_loss_pct", 0) > 1:
            report["recommendations_summary"].append(
                f"[CRITICAL] Perte de paquets {name}: {lat['packet_loss_pct']}% — probleme reseau"
            )

    # Sauvegarder le rapport
    conn = get_db()
    conn.execute(
        "INSERT INTO reports (timestamp, report_type, content, score) VALUES (?, ?, ?, ?)",
        (report["timestamp"], "full", json.dumps(report, ensure_ascii=False), report["overall_score"])
    )
    conn.commit()
    conn.close()

    return report


# --- Commandes CLI ---

def cmd_optimize(args):
    """Lance une optimisation complete: analyse + recommandations."""
    result = {
        "timestamp": _now(),
        "action": "optimize",
        "tcp_analysis": None,
        "latency_quick_check": {},
        "recommendations": [],
        "applied": []
    }

    # Analyse TCP
    tcp = analyze_tcp_config()
    result["tcp_analysis"] = tcp

    # Verification rapide de latence (3 pings seulement)
    for name in CLUSTER_NODES:
        lat = measure_latency(name, count=3)
        result["latency_quick_check"][name] = {
            "avg_ms": lat.get("avg_ms"),
            "quality": lat.get("quality"),
            "loss_pct": lat.get("packet_loss_pct")
        }

    # Generer les recommandations
    if tcp.get("recommendations"):
        for rec in tcp["recommendations"]:
            result["recommendations"].append(rec)

    # Recommandations specifiques cluster IA
    result["recommendations"].append({
        "parameter": "Cluster IA — Pooling HTTP",
        "current": "connexions individuelles",
        "recommended": "HTTP Keep-Alive + Connection Pooling",
        "status": "info",
        "description": "Reutiliser les connexions TCP entre les requetes au cluster reduit la latence de 50-100ms"
    })

    result["recommendations"].append({
        "parameter": "Cluster IA — DNS resolution",
        "current": "IP directes (127.0.0.1, 192.168.x.x)",
        "recommended": "OK — eviter localhost (IPv6 +10s sur Windows)",
        "status": "ok",
        "description": "Les IPs directes evitent la resolution DNS et le probleme IPv6 de Windows"
    })

    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_test(args):
    """Lance tous les tests reseau (latence + MTU + bande passante)."""
    result = {
        "timestamp": _now(),
        "action": "full_test",
        "latency": {},
        "mtu": {},
        "bandwidth": {}
    }

    # Tests de latence
    for name in CLUSTER_NODES:
        result["latency"][name] = measure_latency(name)

    # Tests MTU
    for name in CLUSTER_NODES:
        result["mtu"][name] = check_mtu(name)

    # Tests bande passante (noeuds distants uniquement)
    for name, node in CLUSTER_NODES.items():
        if node["ip"] != "127.0.0.1":
            result["bandwidth"][name] = estimate_bandwidth(name)
        else:
            result["bandwidth"][name] = {
                "node": name,
                "ip": node["ip"],
                "estimated_bandwidth_mbps": 10000.0,
                "quality": "loopback",
                "note": "Noeud local — pas de test bande passante necessaire"
            }

    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_latency(args):
    """Mesure la latence vers tous les noeuds."""
    results = {
        "timestamp": _now(),
        "action": "latency_test",
        "ping_count": PING_COUNT,
        "nodes": {}
    }

    all_results = measure_all_latency()
    results["nodes"] = all_results

    # Resume
    results["summary"] = {
        "online": sum(1 for r in all_results.values() if r.get("quality") != "offline"),
        "offline": sum(1 for r in all_results.values() if r.get("quality") == "offline"),
        "avg_latency_ms": None,
        "best_node": None,
        "worst_node": None
    }

    latencies = {n: r["avg_ms"] for n, r in all_results.items() if r.get("avg_ms") is not None}
    if latencies:
        results["summary"]["avg_latency_ms"] = round(sum(latencies.values()) / len(latencies), 2)
        results["summary"]["best_node"] = min(latencies, key=latencies.get)
        results["summary"]["worst_node"] = max(latencies, key=latencies.get)

    print(json.dumps(results, indent=2, ensure_ascii=False))


def cmd_bandwidth(args):
    """Estime la bande passante vers les noeuds distants."""
    results = {
        "timestamp": _now(),
        "action": "bandwidth_estimation",
        "nodes": {}
    }

    for name, node in CLUSTER_NODES.items():
        if node["ip"] != "127.0.0.1":
            results["nodes"][name] = estimate_bandwidth(name)
        else:
            results["nodes"][name] = {
                "node": name,
                "ip": node["ip"],
                "estimated_bandwidth_mbps": 10000.0,
                "quality": "loopback",
                "note": "Interface loopback — bande passante quasi-infinie"
            }

    print(json.dumps(results, indent=2, ensure_ascii=False))


def cmd_report(args):
    """Genere un rapport complet d'optimisation reseau."""
    report = generate_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))


# --- Point d'entree ---

def main():
    """Point d'entree principal avec parsing des arguments CLI."""
    parser = argparse.ArgumentParser(
        description="Network Optimizer — Optimiseur reseau pour cluster IA distribue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python network_optimizer.py --optimize       # Analyse + recommandations
  python network_optimizer.py --test           # Tests complets (latence + MTU + bande passante)
  python network_optimizer.py --latency        # Mesure latence vers tous les noeuds
  python network_optimizer.py --bandwidth      # Estimation bande passante
  python network_optimizer.py --report         # Rapport complet

Noeuds du cluster:
  M1   127.0.0.1:1234     LM Studio local (qwen3-8b)
  OL1  127.0.0.1:11434    Ollama local (qwen3:1.7b + cloud)
  M2   192.168.1.26:1234  LM Studio distant (deepseek-r1)
  M3   192.168.1.113:1234 LM Studio distant (deepseek-r1)
        """
    )

    # Arguments mutuellement exclusifs
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--optimize", action="store_true",
                       help="Analyser et recommander des optimisations reseau")
    group.add_argument("--test", action="store_true",
                       help="Lancer tous les tests reseau (latence, MTU, bande passante)")
    group.add_argument("--latency", action="store_true",
                       help="Mesurer la latence (ping) vers tous les noeuds")
    group.add_argument("--bandwidth", action="store_true",
                       help="Estimer la bande passante vers les noeuds distants")
    group.add_argument("--report", action="store_true",
                       help="Generer un rapport complet d'optimisation")

    args = parser.parse_args()

    # Initialiser la base de donnees
    init_db()

    # Router vers la commande appropriee
    if args.optimize:
        cmd_optimize(args)
    elif args.test:
        cmd_test(args)
    elif args.latency:
        cmd_latency(args)
    elif args.bandwidth:
        cmd_bandwidth(args)
    elif args.report:
        cmd_report(args)


if __name__ == "__main__":
    main()
