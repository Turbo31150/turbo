"""JARVIS Performance Monitor — Collecte et persistence des métriques système en temps réel.

Surveille CPU, RAM, GPU, disque, réseau et services JARVIS avec ring buffer
en mémoire (1000 échantillons ≈ 2.7h) et résumés horaires persistés dans JSONL.

Usage:
    from src.performance_monitor import perf_monitor
    perf_monitor.start()
    snap = perf_monitor.get_current()
    history = perf_monitor.get_history(hours=2)
    alerts = perf_monitor.get_alerts()
    perf_monitor.stop()
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import statistics
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.perf_monitor")

# --- Constantes ---
POLL_INTERVAL_S: float = 10.0
RING_BUFFER_SIZE: int = 1000  # ~2.7 heures à 10s d'intervalle
HISTORY_DIR: Path = Path("/home/turbo/jarvis/data")
HISTORY_FILE: Path = HISTORY_DIR / "perf_history.jsonl"

# Seuils d'alerte
ALERT_CPU_PCT: float = 90.0
ALERT_CPU_DURATION_S: float = 60.0
ALERT_RAM_PCT: float = 95.0
ALERT_GPU_TEMP_C: float = 80.0
ALERT_DISK_WRITE_MBS: float = 500.0
ALERT_DISK_WRITE_DURATION_S: float = 30.0


# --- Dataclass pour les alertes ---
@dataclass
class PerfAlert:
    """Alerte de performance détectée."""
    key: str
    message: str
    level: str  # warning, critical
    triggered_at: float
    resolved_at: float | None = None
    value: float = 0.0
    threshold: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# --- Fonctions de collecte bas niveau ---

def _read_proc_stat() -> dict[str, Any]:
    """Lit /proc/stat pour obtenir le load CPU et l'usage par cœur."""
    result: dict[str, Any] = {"load_avg": [0.0, 0.0, 0.0], "per_core": [], "total_pct": 0.0}
    try:
        # Load average depuis /proc/loadavg
        with open("/proc/loadavg", "r") as f:
            parts = f.read().split()
            result["load_avg"] = [float(parts[0]), float(parts[1]), float(parts[2])]
    except (OSError, IndexError, ValueError):
        pass

    try:
        with open("/proc/stat", "r") as f:
            lines = f.readlines()
        for line in lines:
            if line.startswith("cpu") and not line.startswith("cpu "):
                # cpuN user nice system idle iowait irq softirq steal
                parts = line.split()
                core_name = parts[0]
                vals = [int(x) for x in parts[1:8]]
                total = sum(vals)
                idle = vals[3] + vals[4]  # idle + iowait
                result["per_core"].append({
                    "core": core_name,
                    "total_ticks": total,
                    "idle_ticks": idle,
                })
            elif line.startswith("cpu "):
                # CPU global
                parts = line.split()
                vals = [int(x) for x in parts[1:8]]
                total = sum(vals)
                idle = vals[3] + vals[4]
                result["_global_total"] = total
                result["_global_idle"] = idle
    except (OSError, ValueError):
        pass

    # Fréquences CPU
    try:
        with open("/proc/cpuinfo", "r") as f:
            freqs = re.findall(r"cpu MHz\s*:\s*([\d.]+)", f.read())
            if freqs:
                result["frequency_mhz"] = [float(x) for x in freqs]
    except OSError:
        pass

    return result


def _read_proc_meminfo() -> dict[str, Any]:
    """Lit /proc/meminfo pour RAM et swap."""
    mem: dict[str, int] = {}
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(":")
                    mem[key] = int(parts[1]) * 1024  # kB → bytes
    except (OSError, ValueError):
        pass

    total = mem.get("MemTotal", 1)
    available = mem.get("MemAvailable", 0)
    cached = mem.get("Cached", 0)
    swap_total = mem.get("SwapTotal", 0)
    swap_free = mem.get("SwapFree", 0)
    used = total - available

    return {
        "total_bytes": total,
        "used_bytes": used,
        "available_bytes": available,
        "cached_bytes": cached,
        "swap_total_bytes": swap_total,
        "swap_used_bytes": swap_total - swap_free,
        "used_pct": round((used / total) * 100, 1) if total > 0 else 0.0,
    }


def _read_gpu_nvidia() -> list[dict[str, Any]]:
    """Appelle nvidia-smi pour récupérer les métriques GPU."""
    gpus: list[dict[str, Any]] = []
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,temperature.gpu,utilization.gpu,"
                "memory.used,memory.total,fan.speed,power.draw",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return gpus
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 8:
                continue
            gpus.append({
                "index": int(parts[0]),
                "name": parts[1],
                "temp_c": _safe_float(parts[2]),
                "utilization_pct": _safe_float(parts[3]),
                "vram_used_mb": _safe_float(parts[4]),
                "vram_total_mb": _safe_float(parts[5]),
                "fan_speed_pct": _safe_float(parts[6]),
                "power_draw_w": _safe_float(parts[7]),
            })
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return gpus


def _read_disk_io() -> dict[str, Any]:
    """Lit /proc/diskstats pour les IOPS et le throughput."""
    result: dict[str, Any] = {"read_ios": 0, "write_ios": 0, "read_bytes": 0, "write_bytes": 0}
    try:
        with open("/proc/diskstats", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 14:
                    continue
                dev = parts[2]
                # Filtrer les partitions, garder les disques principaux
                if dev.startswith("loop") or dev.startswith("dm-"):
                    continue
                # Seuls les disques sans numéro final (sda, nvme0n1)
                if re.match(r"^(sd[a-z]+|nvme\d+n\d+)$", dev):
                    result["read_ios"] += int(parts[3])
                    result["write_ios"] += int(parts[7])
                    # Secteurs lus/écrits × 512 octets
                    result["read_bytes"] += int(parts[5]) * 512
                    result["write_bytes"] += int(parts[9]) * 512
    except (OSError, ValueError, IndexError):
        pass
    return result


def _read_network() -> dict[str, Any]:
    """Lit /proc/net/dev pour rx/tx et compte les connexions réseau."""
    net: dict[str, Any] = {"rx_bytes": 0, "tx_bytes": 0, "connections": 0}
    try:
        with open("/proc/net/dev", "r") as f:
            for line in f:
                if ":" not in line:
                    continue
                iface, data = line.split(":", 1)
                iface = iface.strip()
                if iface == "lo":
                    continue
                parts = data.split()
                if len(parts) >= 9:
                    net["rx_bytes"] += int(parts[0])
                    net["tx_bytes"] += int(parts[8])
    except (OSError, ValueError):
        pass

    # Nombre de connexions TCP établies
    try:
        with open("/proc/net/tcp", "r") as f:
            # Ligne d'entête + connexions ; état 01 = ESTABLISHED
            lines = f.readlines()[1:]
            net["connections"] = sum(1 for l in lines if len(l.split()) > 3 and l.split()[3] == "01")
    except (OSError, IndexError):
        pass
    return net


def _read_jarvis_meta() -> dict[str, Any]:
    """Métriques internes JARVIS : services, skills brain, cycles improve."""
    meta: dict[str, Any] = {"services_count": 0, "brain_skills": 0, "improve_cycles": 0}
    # Nombre de services JARVIS actifs
    try:
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "--plain"],
            capture_output=True, text=True, timeout=5,
        )
        meta["services_count"] = sum(
            1 for l in result.stdout.splitlines() if "jarvis" in l.lower()
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Skills du brain
    try:
        skills_path = Path("/home/turbo/jarvis/data/skills.json")
        if skills_path.exists():
            data = json.loads(skills_path.read_text())
            if isinstance(data, list):
                meta["brain_skills"] = len(data)
            elif isinstance(data, dict):
                meta["brain_skills"] = len(data.get("skills", data))
    except (json.JSONDecodeError, OSError):
        pass

    # Cycles improve
    try:
        cycles_path = Path("/home/turbo/jarvis/data/improve_cycles.jsonl")
        if cycles_path.exists():
            with open(cycles_path, "r") as f:
                meta["improve_cycles"] = sum(1 for _ in f)
    except OSError:
        pass

    return meta


def _safe_float(val: str) -> float:
    """Convertit une valeur en float, retourne 0.0 si impossible."""
    try:
        return float(val.strip())
    except (ValueError, AttributeError):
        return 0.0


def _percentile(data: list[float], pct: float) -> float:
    """Calcule le percentile p d'une liste triée."""
    if not data:
        return 0.0
    sorted_d = sorted(data)
    k = (len(sorted_d) - 1) * (pct / 100.0)
    f = int(k)
    c = f + 1
    if c >= len(sorted_d):
        return sorted_d[-1]
    return sorted_d[f] + (k - f) * (sorted_d[c] - sorted_d[f])


# --- Classe principale ---

class PerformanceMonitor:
    """Moniteur de performance temps réel avec historique et alertes."""

    def __init__(self) -> None:
        self._buffer: deque[dict[str, Any]] = deque(maxlen=RING_BUFFER_SIZE)
        self._lock: threading.Lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running: bool = False

        # État pour le calcul des deltas (CPU, disque, réseau)
        self._prev_cpu: dict[str, Any] | None = None
        self._prev_disk: dict[str, Any] | None = None
        self._prev_net: dict[str, Any] | None = None
        self._prev_ts: float = 0.0

        # Alertes actives
        self._alerts: dict[str, PerfAlert] = {}
        self._alert_history: list[dict[str, Any]] = []

        # Suivi temporel pour alertes à durée
        self._cpu_high_since: float = 0.0
        self._disk_high_since: float = 0.0

        # Résumé horaire
        self._current_hour_samples: list[dict[str, Any]] = []
        self._current_hour_start: float = 0.0

        # Créer le répertoire data si nécessaire
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    # --- Collecte principale ---

    def _collect_sample(self) -> dict[str, Any]:
        """Collecte un échantillon complet de toutes les métriques."""
        now = time.time()
        dt = now - self._prev_ts if self._prev_ts > 0 else POLL_INTERVAL_S

        sample: dict[str, Any] = {"ts": now}

        # --- CPU ---
        cpu_raw = _read_proc_stat()
        cpu_data: dict[str, Any] = {
            "load_avg": cpu_raw["load_avg"],
            "frequency_mhz": cpu_raw.get("frequency_mhz", []),
        }
        # Calcul du pourcentage CPU via delta
        if self._prev_cpu is not None:
            prev_total = self._prev_cpu.get("_global_total", 0)
            prev_idle = self._prev_cpu.get("_global_idle", 0)
            cur_total = cpu_raw.get("_global_total", 0)
            cur_idle = cpu_raw.get("_global_idle", 0)
            d_total = cur_total - prev_total
            d_idle = cur_idle - prev_idle
            if d_total > 0:
                cpu_data["total_pct"] = round((1.0 - d_idle / d_total) * 100, 1)
            else:
                cpu_data["total_pct"] = 0.0

            # Par cœur
            per_core_pct: list[dict[str, Any]] = []
            prev_cores = {c["core"]: c for c in self._prev_cpu.get("per_core", [])}
            for core in cpu_raw.get("per_core", []):
                prev_c = prev_cores.get(core["core"])
                if prev_c:
                    dt_t = core["total_ticks"] - prev_c["total_ticks"]
                    dt_i = core["idle_ticks"] - prev_c["idle_ticks"]
                    pct = round((1.0 - dt_i / dt_t) * 100, 1) if dt_t > 0 else 0.0
                    per_core_pct.append({"core": core["core"], "pct": pct})
            cpu_data["per_core_pct"] = per_core_pct
        else:
            cpu_data["total_pct"] = 0.0
            cpu_data["per_core_pct"] = []

        self._prev_cpu = cpu_raw
        sample["cpu"] = cpu_data

        # --- RAM ---
        sample["ram"] = _read_proc_meminfo()

        # --- GPU ---
        sample["gpu"] = _read_gpu_nvidia()

        # --- Disque (delta IOPS / throughput) ---
        disk_raw = _read_disk_io()
        disk_data: dict[str, Any] = {}
        if self._prev_disk is not None and dt > 0:
            disk_data["read_iops"] = round(
                (disk_raw["read_ios"] - self._prev_disk["read_ios"]) / dt, 1
            )
            disk_data["write_iops"] = round(
                (disk_raw["write_ios"] - self._prev_disk["write_ios"]) / dt, 1
            )
            disk_data["read_throughput_mbs"] = round(
                (disk_raw["read_bytes"] - self._prev_disk["read_bytes"]) / dt / 1_048_576, 2
            )
            disk_data["write_throughput_mbs"] = round(
                (disk_raw["write_bytes"] - self._prev_disk["write_bytes"]) / dt / 1_048_576, 2
            )
        else:
            disk_data = {"read_iops": 0, "write_iops": 0,
                         "read_throughput_mbs": 0.0, "write_throughput_mbs": 0.0}
        self._prev_disk = disk_raw
        sample["disk"] = disk_data

        # --- Réseau (delta rx/tx) ---
        net_raw = _read_network()
        net_data: dict[str, Any] = {"connections": net_raw["connections"]}
        if self._prev_net is not None and dt > 0:
            net_data["rx_bytes_sec"] = round(
                (net_raw["rx_bytes"] - self._prev_net["rx_bytes"]) / dt, 0
            )
            net_data["tx_bytes_sec"] = round(
                (net_raw["tx_bytes"] - self._prev_net["tx_bytes"]) / dt, 0
            )
        else:
            net_data["rx_bytes_sec"] = 0
            net_data["tx_bytes_sec"] = 0
        self._prev_net = net_raw
        sample["network"] = net_data

        # --- JARVIS meta ---
        sample["jarvis"] = _read_jarvis_meta()

        self._prev_ts = now
        return sample

    # --- Alertes ---

    def _check_alerts(self, sample: dict[str, Any]) -> None:
        """Vérifie les seuils et gère les alertes actives."""
        now = sample["ts"]

        # CPU > 90% pendant 60s
        cpu_pct = sample.get("cpu", {}).get("total_pct", 0.0)
        if cpu_pct > ALERT_CPU_PCT:
            if self._cpu_high_since == 0.0:
                self._cpu_high_since = now
            elif (now - self._cpu_high_since) >= ALERT_CPU_DURATION_S:
                self._fire_alert(
                    key="cpu_high",
                    message=f"CPU à {cpu_pct}% depuis {int(now - self._cpu_high_since)}s",
                    level="critical",
                    value=cpu_pct,
                    threshold=ALERT_CPU_PCT,
                )
        else:
            self._cpu_high_since = 0.0
            self._resolve_alert("cpu_high")

        # RAM > 95%
        ram_pct = sample.get("ram", {}).get("used_pct", 0.0)
        if ram_pct > ALERT_RAM_PCT:
            self._fire_alert(
                key="ram_high",
                message=f"RAM à {ram_pct}% (seuil {ALERT_RAM_PCT}%)",
                level="critical",
                value=ram_pct,
                threshold=ALERT_RAM_PCT,
            )
        else:
            self._resolve_alert("ram_high")

        # GPU temp > 80°C (par GPU)
        for gpu in sample.get("gpu", []):
            gpu_key = f"gpu_{gpu['index']}_hot"
            if gpu["temp_c"] > ALERT_GPU_TEMP_C:
                self._fire_alert(
                    key=gpu_key,
                    message=f"GPU {gpu['index']} ({gpu['name']}) à {gpu['temp_c']}°C",
                    level="warning",
                    value=gpu["temp_c"],
                    threshold=ALERT_GPU_TEMP_C,
                    metadata={"gpu_index": gpu["index"]},
                )
            else:
                self._resolve_alert(gpu_key)

        # Disk write > 500 MB/s pendant 30s
        write_mbs = sample.get("disk", {}).get("write_throughput_mbs", 0.0)
        if write_mbs > ALERT_DISK_WRITE_MBS:
            if self._disk_high_since == 0.0:
                self._disk_high_since = now
            elif (now - self._disk_high_since) >= ALERT_DISK_WRITE_DURATION_S:
                self._fire_alert(
                    key="disk_write_high",
                    message=f"Écriture disque à {write_mbs} MB/s depuis {int(now - self._disk_high_since)}s",
                    level="warning",
                    value=write_mbs,
                    threshold=ALERT_DISK_WRITE_MBS,
                )
        else:
            self._disk_high_since = 0.0
            self._resolve_alert("disk_write_high")

    def _fire_alert(
        self,
        key: str,
        message: str,
        level: str,
        value: float = 0.0,
        threshold: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Déclenche ou met à jour une alerte."""
        if key in self._alerts:
            # Mise à jour silencieuse
            self._alerts[key].value = value
            self._alerts[key].message = message
            return
        alert = PerfAlert(
            key=key,
            message=message,
            level=level,
            triggered_at=time.time(),
            value=value,
            threshold=threshold,
            metadata=metadata or {},
        )
        self._alerts[key] = alert
        logger.warning("Alerte déclenchée : [%s] %s", key, message)

    def _resolve_alert(self, key: str) -> None:
        """Résout une alerte si elle existe."""
        if key in self._alerts:
            alert = self._alerts.pop(key)
            alert.resolved_at = time.time()
            self._alert_history.append(asdict(alert))
            # Garder un historique limité
            if len(self._alert_history) > 500:
                self._alert_history = self._alert_history[-250:]
            logger.info("Alerte résolue : [%s]", key)

    # --- Résumé horaire ---

    def _update_hourly_summary(self, sample: dict[str, Any]) -> None:
        """Accumule les échantillons et persiste le résumé toutes les heures."""
        now = sample["ts"]
        current_hour = int(now // 3600) * 3600

        if self._current_hour_start == 0.0:
            self._current_hour_start = current_hour

        if current_hour > self._current_hour_start and self._current_hour_samples:
            # Nouvelle heure → persister le résumé de l'heure précédente
            summary = self._compute_summary(self._current_hour_samples)
            summary["hour_start"] = self._current_hour_start
            summary["hour_end"] = self._current_hour_start + 3600
            summary["sample_count"] = len(self._current_hour_samples)
            self._persist_summary(summary)
            self._current_hour_samples = []
            self._current_hour_start = current_hour

        self._current_hour_samples.append(sample)

    def _compute_summary(self, samples: list[dict[str, Any]]) -> dict[str, Any]:
        """Calcule min/max/avg/p95 pour les métriques numériques clés."""
        summary: dict[str, Any] = {}

        # Helper pour agréger une série de valeurs
        def agg(values: list[float]) -> dict[str, float]:
            if not values:
                return {"min": 0.0, "max": 0.0, "avg": 0.0, "p95": 0.0}
            return {
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "avg": round(statistics.mean(values), 2),
                "p95": round(_percentile(values, 95), 2),
            }

        # CPU
        summary["cpu_pct"] = agg([s.get("cpu", {}).get("total_pct", 0.0) for s in samples])
        summary["load_1m"] = agg([s.get("cpu", {}).get("load_avg", [0])[0] for s in samples])

        # RAM
        summary["ram_pct"] = agg([s.get("ram", {}).get("used_pct", 0.0) for s in samples])
        summary["ram_used_gb"] = agg([
            s.get("ram", {}).get("used_bytes", 0) / 1_073_741_824 for s in samples
        ])

        # GPU (agrégation sur tous les GPUs)
        gpu_temps: list[float] = []
        gpu_utils: list[float] = []
        gpu_vram: list[float] = []
        gpu_power: list[float] = []
        for s in samples:
            for g in s.get("gpu", []):
                gpu_temps.append(g.get("temp_c", 0.0))
                gpu_utils.append(g.get("utilization_pct", 0.0))
                gpu_vram.append(g.get("vram_used_mb", 0.0))
                gpu_power.append(g.get("power_draw_w", 0.0))
        summary["gpu_temp_c"] = agg(gpu_temps)
        summary["gpu_util_pct"] = agg(gpu_utils)
        summary["gpu_vram_mb"] = agg(gpu_vram)
        summary["gpu_power_w"] = agg(gpu_power)

        # Disque
        summary["disk_read_mbs"] = agg([
            s.get("disk", {}).get("read_throughput_mbs", 0.0) for s in samples
        ])
        summary["disk_write_mbs"] = agg([
            s.get("disk", {}).get("write_throughput_mbs", 0.0) for s in samples
        ])

        # Réseau
        summary["net_rx_mbs"] = agg([
            s.get("network", {}).get("rx_bytes_sec", 0) / 1_048_576 for s in samples
        ])
        summary["net_tx_mbs"] = agg([
            s.get("network", {}).get("tx_bytes_sec", 0) / 1_048_576 for s in samples
        ])
        summary["net_connections"] = agg([
            float(s.get("network", {}).get("connections", 0)) for s in samples
        ])

        return summary

    def _persist_summary(self, summary: dict[str, Any]) -> None:
        """Écrit un résumé horaire dans le fichier JSONL."""
        try:
            with open(HISTORY_FILE, "a") as f:
                f.write(json.dumps(summary, ensure_ascii=False) + "\n")
            logger.info(
                "Résumé horaire persisté : %s → %s (%d échantillons)",
                time.strftime("%H:%M", time.localtime(summary["hour_start"])),
                time.strftime("%H:%M", time.localtime(summary["hour_end"])),
                summary["sample_count"],
            )
        except OSError as exc:
            logger.error("Impossible d'écrire le résumé horaire : %s", exc)

    # --- Boucle principale ---

    def _poll_loop(self) -> None:
        """Boucle de collecte exécutée dans un thread daemon."""
        logger.info("Boucle de collecte démarrée (intervalle=%ss)", POLL_INTERVAL_S)
        while self._running:
            try:
                sample = self._collect_sample()
                with self._lock:
                    self._buffer.append(sample)
                self._check_alerts(sample)
                self._update_hourly_summary(sample)
            except Exception:
                logger.exception("Erreur dans la boucle de collecte")
            # Sommeil fractionné pour un arrêt réactif
            deadline = time.time() + POLL_INTERVAL_S
            while self._running and time.time() < deadline:
                time.sleep(0.5)

    # --- API publique ---

    def start(self) -> None:
        """Démarre le thread de collecte daemon."""
        if self._running:
            logger.warning("Le moniteur de performance est déjà actif")
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="jarvis-perf-monitor",
            daemon=True,
        )
        self._thread.start()
        logger.info("Performance monitor démarré")

    def stop(self) -> None:
        """Arrête le thread de collecte proprement."""
        if not self._running:
            return
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=15.0)
            self._thread = None
        # Persister le résumé partiel de l'heure en cours
        if self._current_hour_samples:
            summary = self._compute_summary(self._current_hour_samples)
            summary["hour_start"] = self._current_hour_start
            summary["hour_end"] = time.time()
            summary["sample_count"] = len(self._current_hour_samples)
            summary["partial"] = True
            self._persist_summary(summary)
            self._current_hour_samples = []
        logger.info("Performance monitor arrêté")

    def get_current(self) -> dict[str, Any]:
        """Retourne le snapshot le plus récent."""
        with self._lock:
            if self._buffer:
                return dict(self._buffer[-1])
        # Si pas encore de données, collecter un échantillon immédiat
        return self._collect_sample()

    def get_history(self, hours: int = 1) -> list[dict[str, Any]]:
        """Retourne l'historique des N dernières heures depuis le ring buffer.

        Pour les données au-delà du buffer mémoire, lire le fichier JSONL.
        """
        cutoff = time.time() - (hours * 3600)
        result: list[dict[str, Any]] = []

        # D'abord les résumés horaires persistés si demandé
        if hours > 3:  # Au-delà de la capacité du ring buffer
            try:
                if HISTORY_FILE.exists():
                    with open(HISTORY_FILE, "r") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                entry = json.loads(line)
                                if entry.get("hour_start", 0) >= cutoff:
                                    result.append(entry)
                            except json.JSONDecodeError:
                                continue
            except OSError:
                pass

        # Puis le ring buffer mémoire
        with self._lock:
            for sample in self._buffer:
                if sample.get("ts", 0) >= cutoff:
                    result.append(dict(sample))

        return result

    def get_summary(self, hours: int = 1) -> dict[str, Any]:
        """Retourne un résumé min/max/avg/p95 des N dernières heures."""
        cutoff = time.time() - (hours * 3600)
        samples: list[dict[str, Any]] = []
        with self._lock:
            for sample in self._buffer:
                if sample.get("ts", 0) >= cutoff:
                    samples.append(dict(sample))

        if not samples:
            return {"error": "Pas de données disponibles", "hours": hours}

        summary = self._compute_summary(samples)
        summary["hours"] = hours
        summary["sample_count"] = len(samples)
        summary["from_ts"] = samples[0]["ts"]
        summary["to_ts"] = samples[-1]["ts"]
        return summary

    def get_alerts(self) -> list[dict[str, Any]]:
        """Retourne les alertes actuellement actives."""
        return [asdict(a) for a in self._alerts.values()]

    def get_alert_history(self) -> list[dict[str, Any]]:
        """Retourne l'historique des alertes résolues."""
        return list(self._alert_history)


# --- Singleton module ---
perf_monitor = PerformanceMonitor()


# --- Point d'entrée pour systemd ---
if __name__ == "__main__":
    import signal
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("/home/turbo/jarvis/data/logs/perf_monitor.log"),
        ],
    )

    logger.info("=== JARVIS Performance Monitor ===")

    def _shutdown(signum: int, frame: Any) -> None:
        """Arrêt propre sur signal."""
        logger.info("Signal %s reçu, arrêt en cours...", signum)
        perf_monitor.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    perf_monitor.start()

    # Garder le processus principal vivant
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        perf_monitor.stop()
