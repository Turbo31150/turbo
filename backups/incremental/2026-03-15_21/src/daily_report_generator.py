"""JARVIS Daily Report Generator — Rapport quotidien complet en HTML, texte et JSON.

Génère un rapport exhaustif sur 24h couvrant : système, services, cluster,
commandes vocales, brain, sécurité, performance, notifications, git et recommandations.

Usage:
    from src.daily_report_generator import DailyReportGenerator
    gen = DailyReportGenerator()
    report = gen.generate()                  # dict complet
    html = gen.generate_html()               # fichier HTML sauvegardé
    summary = gen.get_summary()              # texte <4000 chars pour Telegram
    recs = gen.get_recommendations()         # liste de recommandations
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

__all__ = ["DailyReportGenerator"]

logger = logging.getLogger("jarvis.daily_report_generator")

# --- Chemins ---
_BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = _BASE_DIR / "data"
REPORTS_DIR = DATA_DIR / "reports"
HEALING_LOG = DATA_DIR / "healing_history.jsonl"
PERF_HISTORY = DATA_DIR / "perf_history.jsonl"
BRAIN_STATE = DATA_DIR / "brain_state.json"
SKILLS_FILE = DATA_DIR / "skills.json"
IMPROVE_CYCLES = DATA_DIR / "improve_cycles.jsonl"
NOTIFICATIONS_LOG = DATA_DIR / "notifications.jsonl"
INTENT_STATS = DATA_DIR / "intent_stats.json"

# Noeuds du cluster
CLUSTER_NODES: dict[str, str] = {
    "M1": "127.0.0.1:1234",
    "M2": "192.168.1.26:1234",
    "M3": "192.168.1.113:1234",
    "OL1": "127.0.0.1:11434",
}

# Services JARVIS surveillés
JARVIS_SERVICES: list[str] = [
    "jarvis-mcp.service",
    "jarvis-auditor.service",
    "jarvis-health-watcher.service",
    "jarvis-lms-guard.service",
    "jarvis-perf-monitor.service",
    "jarvis-proxy.service",
    "jarvis-watchdog.service",
    "jarvis-ws.service",
]


class DailyReportGenerator:
    """Générateur de rapports quotidiens JARVIS.

    Collecte les données système, cluster, services, etc. sur 24h
    et produit des rapports en HTML, texte résumé et JSON.
    """

    def __init__(self) -> None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Any] = {}

    # ──────────────────────────────────────────────
    # Méthodes publiques
    # ──────────────────────────────────────────────

    def generate(self, date: str | None = None) -> dict[str, Any]:
        """Génère le rapport complet sous forme de dict JSON-sérialisable.

        Args:
            date: Date cible au format YYYY-MM-DD. None = aujourd'hui.

        Returns:
            Dictionnaire contenant toutes les sections du rapport.
        """
        target = self._resolve_date(date)
        logger.info("Génération rapport pour %s", target)

        report: dict[str, Any] = {
            "date": target,
            "generated_at": datetime.now().isoformat(),
            "sections": {},
        }

        # Collecte de chaque section avec gestion d'erreur individuelle
        collectors: list[tuple[str, Any]] = [
            ("system", self._collect_system),
            ("services", self._collect_services),
            ("cluster", self._collect_cluster),
            ("voice_commands", self._collect_voice_commands),
            ("brain", self._collect_brain),
            ("security", self._collect_security),
            ("performance", self._collect_performance),
            ("notifications", self._collect_notifications),
            ("git", self._collect_git),
        ]

        for section_name, collector in collectors:
            try:
                report["sections"][section_name] = collector(target)
            except Exception as exc:
                logger.warning("Erreur collecte %s : %s", section_name, exc)
                report["sections"][section_name] = {"error": str(exc)}

        # Recommandations basées sur les données collectées
        report["recommendations"] = self.get_recommendations(report)

        # Sauvegarde JSON
        json_path = REPORTS_DIR / f"{target}.json"
        json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("Rapport JSON sauvegardé : %s", json_path)

        # Mise en cache pour éviter double collecte
        self._cache[target] = report
        return report

    def generate_html(self, date: str | None = None) -> str:
        """Génère le rapport HTML interactif style JARVIS.

        Args:
            date: Date cible au format YYYY-MM-DD. None = aujourd'hui.

        Returns:
            Chemin absolu du fichier HTML généré.
        """
        target = self._resolve_date(date)

        # Utiliser le cache si disponible
        report = self._cache.get(target)
        if not report:
            report = self.generate(target)

        html = self._render_html(report)
        html_path = REPORTS_DIR / f"{target}.html"
        html_path.write_text(html, encoding="utf-8")
        logger.info("Rapport HTML sauvegardé : %s", html_path)
        return str(html_path)

    def get_summary(self, date: str | None = None) -> str:
        """Génère un résumé texte court (<4000 chars) pour Telegram.

        Args:
            date: Date cible au format YYYY-MM-DD. None = aujourd'hui.

        Returns:
            Texte résumé formaté pour Telegram.
        """
        target = self._resolve_date(date)
        report = self._cache.get(target)
        if not report:
            report = self.generate(target)

        return self._render_summary(report)

    def get_recommendations(self, report: dict[str, Any] | None = None) -> list[str]:
        """Génère des recommandations basées sur les données du rapport.

        Args:
            report: Rapport pré-généré. None = génère le rapport courant.

        Returns:
            Liste de recommandations textuelles.
        """
        if report is None:
            report = self.generate()

        recs: list[str] = []
        sections = report.get("sections", {})

        # Recommandations système
        sys_data = sections.get("system", {})
        if not sys_data.get("error"):
            cpu_avg = sys_data.get("cpu_avg_percent", 0)
            ram_pct = sys_data.get("ram_percent", 0)
            disk_pct = sys_data.get("disk_percent_used", 0)

            if cpu_avg > 80:
                recs.append(f"CPU moyen élevé ({cpu_avg}%) — vérifier les processus gourmands")
            if ram_pct > 90:
                recs.append(f"RAM critique ({ram_pct}%) — envisager libérer de la mémoire")
            if disk_pct > 85:
                recs.append(f"Espace disque faible ({disk_pct}% utilisé) — nettoyage recommandé")

            gpu_max_temp = sys_data.get("gpu_max_temp_c", 0)
            if gpu_max_temp > 75:
                recs.append(f"GPU température max {gpu_max_temp}°C — surveiller la ventilation")

        # Recommandations services
        svc_data = sections.get("services", {})
        if not svc_data.get("error"):
            failed = svc_data.get("failed", [])
            healed = svc_data.get("healed_count", 0)
            if failed:
                recs.append(f"{len(failed)} service(s) en échec : {', '.join(failed)}")
            if healed > 3:
                recs.append(f"Auto-healer a redémarré {healed} services — investiguer la cause racine")

        # Recommandations cluster
        cluster_data = sections.get("cluster", {})
        if not cluster_data.get("error"):
            offline = [n for n, s in cluster_data.get("nodes", {}).items() if not s.get("online")]
            if offline:
                recs.append(f"Noeud(s) cluster hors ligne : {', '.join(offline)}")

        # Recommandations vocales
        voice_data = sections.get("voice_commands", {})
        if not voice_data.get("error"):
            success_rate = voice_data.get("success_rate", 100)
            if success_rate < 90:
                recs.append(f"Taux de succès vocal faible ({success_rate}%) — calibrer le micro ou revoir les patterns")

        # Recommandations sécurité
        sec_data = sections.get("security", {})
        if not sec_data.get("error"):
            failed_logins = sec_data.get("failed_login_attempts", 0)
            if failed_logins > 10:
                recs.append(f"{failed_logins} tentatives de connexion échouées — vérifier fail2ban")

        # Recommandations performance
        perf_data = sections.get("performance", {})
        if not perf_data.get("error"):
            samples = perf_data.get("samples_count", 0)
            if samples == 0:
                recs.append("Aucune donnée de performance — vérifier que perf_monitor est actif")

        # Recommandations notifications
        notif_data = sections.get("notifications", {})
        if not notif_data.get("error"):
            criticals = notif_data.get("critical_count", 0)
            if criticals > 5:
                recs.append(f"{criticals} notifications critiques — revue urgente nécessaire")

        if not recs:
            recs.append("Tous les systèmes sont nominaux — aucune action requise")

        return recs

    # ──────────────────────────────────────────────
    # Collecteurs de données
    # ──────────────────────────────────────────────

    def _collect_system(self, date: str) -> dict[str, Any]:
        """Résumé système : uptime, CPU moyen, RAM, GPU, disque."""
        data: dict[str, Any] = {}

        # Uptime
        try:
            uptime_raw = Path("/proc/uptime").read_text().strip()
            uptime_seconds = float(uptime_raw.split()[0])
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            data["uptime"] = f"{days}j {hours}h"
            data["uptime_seconds"] = uptime_seconds
        except Exception:
            data["uptime"] = "inconnu"

        # CPU moyen (via /proc/loadavg pour la charge)
        try:
            loadavg = Path("/proc/loadavg").read_text().strip().split()
            data["load_avg_1m"] = float(loadavg[0])
            data["load_avg_5m"] = float(loadavg[1])
            data["load_avg_15m"] = float(loadavg[2])
        except Exception:
            pass

        # CPU % via psutil si disponible, sinon via /proc/stat
        try:
            import psutil
            data["cpu_avg_percent"] = psutil.cpu_percent(interval=1)
            data["cpu_count"] = psutil.cpu_count()
        except ImportError:
            try:
                result = subprocess.run(
                    ["top", "-bn1"], capture_output=True, text=True, timeout=5
                )
                match = re.search(r"(\d+[\.,]\d+)\s*id", result.stdout)
                if match:
                    idle = float(match.group(1).replace(",", "."))
                    data["cpu_avg_percent"] = round(100.0 - idle, 1)
            except Exception:
                pass

        # RAM
        try:
            import psutil
            mem = psutil.virtual_memory()
            data["ram_used_gb"] = round(mem.used / (1024 ** 3), 1)
            data["ram_total_gb"] = round(mem.total / (1024 ** 3), 1)
            data["ram_percent"] = mem.percent
        except ImportError:
            try:
                meminfo = Path("/proc/meminfo").read_text()
                total = int(re.search(r"MemTotal:\s+(\d+)", meminfo).group(1))
                avail = int(re.search(r"MemAvailable:\s+(\d+)", meminfo).group(1))
                data["ram_total_gb"] = round(total / (1024 ** 2), 1)
                data["ram_used_gb"] = round((total - avail) / (1024 ** 2), 1)
                data["ram_percent"] = round((total - avail) / total * 100, 1)
            except Exception:
                pass

        # GPU
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10,
            )
            gpus: list[dict[str, Any]] = []
            for line in result.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    gpus.append({
                        "name": parts[0],
                        "temp_c": int(parts[1]),
                        "utilization_percent": int(parts[2]),
                        "vram_used_mb": int(parts[3]),
                        "vram_total_mb": int(parts[4]),
                    })
            data["gpus"] = gpus
            data["gpu_count"] = len(gpus)
            if gpus:
                data["gpu_max_temp_c"] = max(g["temp_c"] for g in gpus)
                data["gpu_avg_util"] = round(
                    sum(g["utilization_percent"] for g in gpus) / len(gpus), 1
                )
                data["vram_total_mb"] = sum(g["vram_total_mb"] for g in gpus)
                data["vram_used_mb"] = sum(g["vram_used_mb"] for g in gpus)
        except FileNotFoundError:
            data["gpus"] = []
            data["gpu_count"] = 0
        except Exception as exc:
            data["gpu_error"] = str(exc)

        # Disque
        try:
            disk = shutil.disk_usage("/")
            data["disk_total_gb"] = round(disk.total / (1024 ** 3), 1)
            data["disk_used_gb"] = round(disk.used / (1024 ** 3), 1)
            data["disk_free_gb"] = round(disk.free / (1024 ** 3), 1)
            data["disk_percent_used"] = round(disk.used / disk.total * 100, 1)
        except Exception:
            pass

        # Disque /home si séparé
        try:
            disk_home = shutil.disk_usage("/home")
            if disk_home.total != disk.total:
                data["disk_home_total_gb"] = round(disk_home.total / (1024 ** 3), 1)
                data["disk_home_free_gb"] = round(disk_home.free / (1024 ** 3), 1)
        except Exception:
            pass

        return data

    def _collect_services(self, date: str) -> dict[str, Any]:
        """Services JARVIS : actifs, échoués, redémarrés par auto-healer."""
        data: dict[str, Any] = {
            "active": [],
            "failed": [],
            "inactive": [],
            "healed_count": 0,
            "healed_services": [],
        }

        # État des services systemd
        for service in JARVIS_SERVICES:
            try:
                result = subprocess.run(
                    ["systemctl", "--user", "is-active", service],
                    capture_output=True, text=True, timeout=5,
                )
                status = result.stdout.strip()
                svc_name = service.replace(".service", "")
                if status == "active":
                    data["active"].append(svc_name)
                elif status == "failed":
                    data["failed"].append(svc_name)
                else:
                    data["inactive"].append(svc_name)
            except Exception:
                data["inactive"].append(service.replace(".service", ""))

        data["active_count"] = len(data["active"])
        data["failed_count"] = len(data["failed"])

        # Historique de healing sur la journée
        try:
            if HEALING_LOG.exists():
                target_date = date  # YYYY-MM-DD
                healed: list[str] = []
                for line in HEALING_LOG.read_text(encoding="utf-8").splitlines():
                    try:
                        entry = json.loads(line)
                        ts = entry.get("ts", entry.get("timestamp", ""))
                        if isinstance(ts, (int, float)):
                            entry_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                        else:
                            entry_date = str(ts)[:10]
                        if entry_date == target_date and entry.get("action") == "restart":
                            svc = entry.get("service", entry.get("target", "inconnu"))
                            healed.append(svc)
                    except (json.JSONDecodeError, ValueError):
                        continue

                data["healed_count"] = len(healed)
                data["healed_services"] = list(set(healed))
        except Exception as exc:
            data["healing_error"] = str(exc)

        return data

    def _collect_cluster(self, date: str) -> dict[str, Any]:
        """Cluster : disponibilité M1/M2/M3/OL1 et modèles chargés."""
        import urllib.request
        import urllib.error

        data: dict[str, Any] = {"nodes": {}, "models_loaded": []}

        for node_name, addr in CLUSTER_NODES.items():
            node_info: dict[str, Any] = {"address": addr, "online": False, "models": []}

            # Vérifier disponibilité
            try:
                if "11434" in addr:
                    # Ollama API
                    url = f"http://{addr}/api/tags"
                else:
                    # LM Studio API
                    url = f"http://{addr}/v1/models"

                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    node_info["online"] = True

                    if "models" in body:
                        # Ollama ou LM Studio
                        models = body["models"]
                        if isinstance(models, list):
                            for m in models:
                                name = m.get("id", m.get("name", m.get("model", "?")))
                                node_info["models"].append(name)
                    elif "data" in body:
                        # Format OpenAI-compatible
                        for m in body["data"]:
                            node_info["models"].append(m.get("id", "?"))

                    data["models_loaded"].extend(node_info["models"])

            except (urllib.error.URLError, OSError, json.JSONDecodeError):
                node_info["online"] = False
            except Exception as exc:
                node_info["online"] = False
                node_info["error"] = str(exc)

            data["nodes"][node_name] = node_info

        data["online_count"] = sum(1 for n in data["nodes"].values() if n["online"])
        data["total_nodes"] = len(CLUSTER_NODES)
        data["total_models"] = len(set(data["models_loaded"]))

        return data

    def _collect_voice_commands(self, date: str) -> dict[str, Any]:
        """Commandes vocales : total, taux succès, top 10, échecs."""
        data: dict[str, Any] = {
            "total_executed": 0,
            "success_count": 0,
            "failure_count": 0,
            "success_rate": 100.0,
            "top_commands": [],
            "failures": [],
        }

        # Charger les stats d'intent depuis le fichier
        try:
            if INTENT_STATS.exists():
                stats = json.loads(INTENT_STATS.read_text(encoding="utf-8"))
                data["total_executed"] = stats.get("total", 0)
                data["success_count"] = stats.get("success", stats.get("total", 0))
                data["failure_count"] = stats.get("failures", 0)

                total = data["total_executed"]
                if total > 0:
                    data["success_rate"] = round(data["success_count"] / total * 100, 1)

                # Top commandes
                commands = stats.get("commands", stats.get("intents", {}))
                if isinstance(commands, dict):
                    sorted_cmds = sorted(commands.items(), key=lambda x: x[1], reverse=True)
                    data["top_commands"] = [
                        {"command": cmd, "count": count}
                        for cmd, count in sorted_cmds[:10]
                    ]

                # Échecs récents
                data["failures"] = stats.get("recent_failures", [])[:10]
        except Exception as exc:
            data["error"] = str(exc)

        # Compléter depuis la DB si disponible
        try:
            db_path = DATA_DIR / "jarvis.db"
            if db_path.exists():
                conn = sqlite3.connect(str(db_path), timeout=5)
                conn.row_factory = sqlite3.Row

                # Compter les commandes du jour
                try:
                    rows = conn.execute(
                        "SELECT COUNT(*) as cnt FROM command_log WHERE date(timestamp) = ?",
                        (date,),
                    ).fetchone()
                    if rows and rows["cnt"] > 0:
                        data["total_executed_db"] = rows["cnt"]
                except sqlite3.OperationalError:
                    pass  # Table peut ne pas exister

                conn.close()
        except Exception:
            pass

        return data

    def _collect_brain(self, date: str) -> dict[str, Any]:
        """Brain : skills créés, patterns détectés, cycles improve."""
        data: dict[str, Any] = {
            "total_skills": 0,
            "patterns_detected": 0,
            "improve_cycles": 0,
            "recent_skills": [],
        }

        # Skills existants
        try:
            if SKILLS_FILE.exists():
                skills = json.loads(SKILLS_FILE.read_text(encoding="utf-8"))
                if isinstance(skills, list):
                    data["total_skills"] = len(skills)
                elif isinstance(skills, dict):
                    data["total_skills"] = len(skills.get("skills", skills))
        except Exception:
            pass

        # Brain state (patterns)
        try:
            if BRAIN_STATE.exists():
                state = json.loads(BRAIN_STATE.read_text(encoding="utf-8"))
                patterns = state.get("patterns", state.get("detected_patterns", []))
                if isinstance(patterns, list):
                    data["patterns_detected"] = len(patterns)
                elif isinstance(patterns, int):
                    data["patterns_detected"] = patterns

                data["brain_confidence"] = state.get("confidence", None)
                data["last_analysis"] = state.get("last_analysis", None)
        except Exception:
            pass

        # Cycles d'amélioration
        try:
            if IMPROVE_CYCLES.exists():
                total = 0
                today_count = 0
                for line in IMPROVE_CYCLES.read_text(encoding="utf-8").splitlines():
                    try:
                        entry = json.loads(line)
                        total += 1
                        ts = entry.get("ts", entry.get("timestamp", ""))
                        if isinstance(ts, (int, float)):
                            entry_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                        else:
                            entry_date = str(ts)[:10]
                        if entry_date == date:
                            today_count += 1
                    except (json.JSONDecodeError, ValueError):
                        continue
                data["improve_cycles"] = total
                data["improve_cycles_today"] = today_count
        except Exception:
            pass

        return data

    def _collect_security(self, date: str) -> dict[str, Any]:
        """Sécurité : alertes, tentatives connexion, ports ouverts."""
        data: dict[str, Any] = {
            "failed_login_attempts": 0,
            "open_ports": [],
            "firewall_status": "inconnu",
            "alerts": [],
        }

        # Tentatives de connexion échouées (journalctl)
        try:
            result = subprocess.run(
                ["journalctl", "--since", f"{date} 00:00:00", "--until", f"{date} 23:59:59",
                 "-u", "sshd", "--no-pager", "-q"],
                capture_output=True, text=True, timeout=10,
            )
            failed_count = result.stdout.lower().count("failed password")
            failed_count += result.stdout.lower().count("authentication failure")
            data["failed_login_attempts"] = failed_count
        except Exception:
            pass

        # Ports ouverts (ss)
        try:
            result = subprocess.run(
                ["ss", "-tlnp"],
                capture_output=True, text=True, timeout=5,
            )
            ports: list[str] = []
            for line in result.stdout.splitlines()[1:]:  # Sauter l'en-tête
                match = re.search(r":(\d+)\s", line)
                if match:
                    port = match.group(1)
                    if port not in ports:
                        ports.append(port)
            data["open_ports"] = sorted(ports, key=lambda p: int(p))
            data["open_ports_count"] = len(ports)
        except Exception:
            pass

        # Statut firewall (ufw)
        try:
            result = subprocess.run(
                ["sudo", "-n", "ufw", "status"],
                capture_output=True, text=True, timeout=5,
            )
            if "active" in result.stdout.lower():
                data["firewall_status"] = "actif"
            elif "inactive" in result.stdout.lower():
                data["firewall_status"] = "inactif"
        except Exception:
            # Essayer iptables en fallback
            try:
                result = subprocess.run(
                    ["sudo", "-n", "iptables", "-L", "-n", "--line-numbers"],
                    capture_output=True, text=True, timeout=5,
                )
                rules_count = len(result.stdout.strip().splitlines())
                data["firewall_status"] = f"iptables ({rules_count} règles)"
            except Exception:
                pass

        # Fail2ban (si disponible)
        try:
            result = subprocess.run(
                ["sudo", "-n", "fail2ban-client", "status"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                data["fail2ban_active"] = True
                jails = re.findall(r"Jail list:\s+(.+)", result.stdout)
                if jails:
                    data["fail2ban_jails"] = [j.strip() for j in jails[0].split(",")]
        except Exception:
            data["fail2ban_active"] = False

        return data

    def _collect_performance(self, date: str) -> dict[str, Any]:
        """Performance : métriques min/max/avg sur 24h depuis perf_history."""
        data: dict[str, Any] = {
            "samples_count": 0,
            "cpu": {},
            "ram": {},
            "gpu_temp": {},
        }

        try:
            if not PERF_HISTORY.exists():
                return data

            cpu_vals: list[float] = []
            ram_vals: list[float] = []
            gpu_temp_vals: list[float] = []

            for line in PERF_HISTORY.read_text(encoding="utf-8").splitlines():
                try:
                    entry = json.loads(line)
                    ts = entry.get("ts", entry.get("timestamp", 0))
                    if isinstance(ts, (int, float)):
                        entry_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                    elif isinstance(ts, str):
                        entry_date = ts[:10]
                    else:
                        continue

                    if entry_date != date:
                        continue

                    if "cpu_percent" in entry:
                        cpu_vals.append(float(entry["cpu_percent"]))
                    if "ram_percent" in entry:
                        ram_vals.append(float(entry["ram_percent"]))
                    gpu_temp = entry.get("gpu_temp", entry.get("gpu_temp_c"))
                    if gpu_temp is not None:
                        gpu_temp_vals.append(float(gpu_temp))

                except (json.JSONDecodeError, ValueError, TypeError):
                    continue

            data["samples_count"] = max(len(cpu_vals), len(ram_vals))

            if cpu_vals:
                data["cpu"] = {
                    "min": round(min(cpu_vals), 1),
                    "max": round(max(cpu_vals), 1),
                    "avg": round(sum(cpu_vals) / len(cpu_vals), 1),
                }
            if ram_vals:
                data["ram"] = {
                    "min": round(min(ram_vals), 1),
                    "max": round(max(ram_vals), 1),
                    "avg": round(sum(ram_vals) / len(ram_vals), 1),
                }
            if gpu_temp_vals:
                data["gpu_temp"] = {
                    "min": round(min(gpu_temp_vals), 1),
                    "max": round(max(gpu_temp_vals), 1),
                    "avg": round(sum(gpu_temp_vals) / len(gpu_temp_vals), 1),
                }

        except Exception as exc:
            data["error"] = str(exc)

        return data

    def _collect_notifications(self, date: str) -> dict[str, Any]:
        """Notifications envoyées : warnings, criticals."""
        data: dict[str, Any] = {
            "total_count": 0,
            "warning_count": 0,
            "critical_count": 0,
            "info_count": 0,
            "recent": [],
        }

        try:
            if not NOTIFICATIONS_LOG.exists():
                return data

            for line in NOTIFICATIONS_LOG.read_text(encoding="utf-8").splitlines():
                try:
                    entry = json.loads(line)
                    ts = entry.get("ts", entry.get("timestamp", 0))
                    if isinstance(ts, (int, float)):
                        entry_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                    elif isinstance(ts, str):
                        entry_date = ts[:10]
                    else:
                        continue

                    if entry_date != date:
                        continue

                    data["total_count"] += 1
                    level = entry.get("level", "info").lower()
                    if level == "critical":
                        data["critical_count"] += 1
                    elif level == "warning":
                        data["warning_count"] += 1
                    else:
                        data["info_count"] += 1

                    # Garder les 20 dernières
                    if len(data["recent"]) < 20:
                        data["recent"].append({
                            "level": level,
                            "message": entry.get("message", entry.get("msg", ""))[:100],
                            "timestamp": ts,
                        })

                except (json.JSONDecodeError, ValueError):
                    continue

        except Exception as exc:
            data["error"] = str(exc)

        return data

    def _collect_git(self, date: str) -> dict[str, Any]:
        """Git : commits et fichiers modifiés pour la journée."""
        data: dict[str, Any] = {
            "commits_count": 0,
            "files_changed": 0,
            "commits": [],
        }

        try:
            # Commits du jour
            result = subprocess.run(
                ["git", "-C", str(_BASE_DIR), "log",
                 f"--since={date} 00:00:00", f"--until={date} 23:59:59",
                 "--oneline", "--no-merges"],
                capture_output=True, text=True, timeout=10,
            )
            commits = [c.strip() for c in result.stdout.strip().splitlines() if c.strip()]
            data["commits_count"] = len(commits)
            data["commits"] = commits[:20]  # Max 20

            # Fichiers modifiés
            if commits:
                result = subprocess.run(
                    ["git", "-C", str(_BASE_DIR), "diff",
                     "--stat", f"--since={date} 00:00:00", f"--until={date} 23:59:59",
                     "HEAD"],
                    capture_output=True, text=True, timeout=10,
                )
                # Compter les fichiers via git log --stat
                result2 = subprocess.run(
                    ["git", "-C", str(_BASE_DIR), "log",
                     f"--since={date} 00:00:00", f"--until={date} 23:59:59",
                     "--stat", "--oneline", "--no-merges"],
                    capture_output=True, text=True, timeout=10,
                )
                files_set: set[str] = set()
                for line in result2.stdout.splitlines():
                    line = line.strip()
                    if "|" in line and ("insertion" in line or "deletion" in line or "Bin" in line):
                        fname = line.split("|")[0].strip()
                        files_set.add(fname)
                data["files_changed"] = len(files_set)

        except Exception as exc:
            data["error"] = str(exc)

        return data

    # ──────────────────────────────────────────────
    # Rendu
    # ──────────────────────────────────────────────

    def _render_html(self, report: dict[str, Any]) -> str:
        """Génère le HTML interactif style JARVIS."""
        date = report["date"]
        sections = report.get("sections", {})
        recs = report.get("recommendations", [])

        # Construction des sections HTML
        sys_html = self._html_system(sections.get("system", {}))
        svc_html = self._html_services(sections.get("services", {}))
        cluster_html = self._html_cluster(sections.get("cluster", {}))
        voice_html = self._html_voice(sections.get("voice_commands", {}))
        brain_html = self._html_brain(sections.get("brain", {}))
        sec_html = self._html_security(sections.get("security", {}))
        perf_html = self._html_performance(sections.get("performance", {}))
        notif_html = self._html_notifications(sections.get("notifications", {}))
        git_html = self._html_git(sections.get("git", {}))
        recs_html = self._html_recommendations(recs)

        return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JARVIS — Rapport {date}</title>
    <style>
        :root {{
            --bg: #0a0e17;
            --card-bg: #111827;
            --border: #1e3a5f;
            --accent: #00d4ff;
            --accent2: #7c3aed;
            --text: #e2e8f0;
            --text-dim: #94a3b8;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --info: #3b82f6;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Segoe UI', 'Inter', system-ui, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            padding: 30px 0;
            border-bottom: 2px solid var(--border);
            margin-bottom: 30px;
        }}
        .header h1 {{
            font-size: 2em;
            color: var(--accent);
            text-shadow: 0 0 20px rgba(0, 212, 255, 0.3);
            letter-spacing: 3px;
        }}
        .header .date {{
            color: var(--text-dim);
            font-size: 1.1em;
            margin-top: 8px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(0, 212, 255, 0.1);
        }}
        .card h2 {{
            color: var(--accent);
            font-size: 1.1em;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .card.full-width {{
            grid-column: 1 / -1;
        }}
        .metric {{
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px solid rgba(30, 58, 95, 0.3);
        }}
        .metric:last-child {{ border-bottom: none; }}
        .metric .label {{ color: var(--text-dim); }}
        .metric .value {{ font-weight: 600; }}
        .badge {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }}
        .badge.success {{ background: rgba(16, 185, 129, 0.2); color: var(--success); }}
        .badge.warning {{ background: rgba(245, 158, 11, 0.2); color: var(--warning); }}
        .badge.danger {{ background: rgba(239, 68, 68, 0.2); color: var(--danger); }}
        .badge.info {{ background: rgba(59, 130, 246, 0.2); color: var(--info); }}
        .badge.offline {{ background: rgba(239, 68, 68, 0.2); color: var(--danger); }}
        .badge.online {{ background: rgba(16, 185, 129, 0.2); color: var(--success); }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th, td {{
            text-align: left;
            padding: 8px 10px;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            color: var(--accent);
            font-size: 0.9em;
            text-transform: uppercase;
        }}
        .rec-list {{
            list-style: none;
        }}
        .rec-list li {{
            padding: 10px 15px;
            margin: 6px 0;
            background: rgba(124, 58, 237, 0.1);
            border-left: 3px solid var(--accent2);
            border-radius: 0 8px 8px 0;
        }}
        .node-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
        }}
        .node-card {{
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px;
            text-align: center;
        }}
        .node-card .name {{ font-weight: 700; font-size: 1.1em; }}
        .bar-container {{
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            height: 8px;
            margin-top: 6px;
            overflow: hidden;
        }}
        .bar {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }}
        .bar.ok {{ background: var(--success); }}
        .bar.warn {{ background: var(--warning); }}
        .bar.crit {{ background: var(--danger); }}
        .footer {{
            text-align: center;
            padding: 30px 0 10px;
            color: var(--text-dim);
            font-size: 0.85em;
            border-top: 1px solid var(--border);
            margin-top: 30px;
        }}
        @media (max-width: 600px) {{
            .grid {{ grid-template-columns: 1fr; }}
            body {{ padding: 10px; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>JARVIS DAILY REPORT</h1>
        <div class="date">{date} &mdash; {report.get('generated_at', '')[:19]}</div>
    </div>
    <div class="grid">
        {sys_html}
        {svc_html}
        {cluster_html}
        {voice_html}
        {brain_html}
        {sec_html}
        {perf_html}
        {notif_html}
        {git_html}
        {recs_html}
    </div>
    <div class="footer">
        JARVIS Turbo &mdash; Rapport auto-g&eacute;n&eacute;r&eacute; le {report.get('generated_at', '')[:19]}
    </div>
</body>
</html>"""

    def _html_system(self, data: dict[str, Any]) -> str:
        """Section HTML : résumé système."""
        if data.get("error"):
            return self._html_error_card("Systeme", data["error"])

        gpu_info = ""
        if data.get("gpus"):
            gpu_lines = []
            for g in data["gpus"]:
                gpu_lines.append(
                    f'<div class="metric"><span class="label">{g["name"]}</span>'
                    f'<span class="value">{g["temp_c"]}°C | {g["utilization_percent"]}% | '
                    f'{g["vram_used_mb"]}/{g["vram_total_mb"]}MB</span></div>'
                )
            gpu_info = "".join(gpu_lines)

        ram_pct = data.get("ram_percent", 0)
        ram_class = "ok" if ram_pct < 80 else ("warn" if ram_pct < 95 else "crit")
        disk_pct = data.get("disk_percent_used", 0)
        disk_class = "ok" if disk_pct < 80 else ("warn" if disk_pct < 90 else "crit")

        return f"""<div class="card">
            <h2>Systeme</h2>
            <div class="metric"><span class="label">Uptime</span><span class="value">{data.get('uptime', '?')}</span></div>
            <div class="metric"><span class="label">CPU</span><span class="value">{data.get('cpu_avg_percent', '?')}%</span></div>
            <div class="metric"><span class="label">Load avg</span><span class="value">{data.get('load_avg_1m', '?')} / {data.get('load_avg_5m', '?')} / {data.get('load_avg_15m', '?')}</span></div>
            <div class="metric">
                <span class="label">RAM</span>
                <span class="value">{data.get('ram_used_gb', '?')}/{data.get('ram_total_gb', '?')} GB ({ram_pct}%)</span>
            </div>
            <div class="bar-container"><div class="bar {ram_class}" style="width:{ram_pct}%"></div></div>
            <div class="metric">
                <span class="label">Disque</span>
                <span class="value">{data.get('disk_used_gb', '?')}/{data.get('disk_total_gb', '?')} GB ({disk_pct}%)</span>
            </div>
            <div class="bar-container"><div class="bar {disk_class}" style="width:{disk_pct}%"></div></div>
            <div class="metric"><span class="label">GPUs</span><span class="value">{data.get('gpu_count', 0)} detecte(s)</span></div>
            {gpu_info}
        </div>"""

    def _html_services(self, data: dict[str, Any]) -> str:
        """Section HTML : services JARVIS."""
        if data.get("error"):
            return self._html_error_card("Services JARVIS", data["error"])

        active = data.get("active_count", 0)
        failed = data.get("failed_count", 0)
        healed = data.get("healed_count", 0)

        status_badge = "success" if failed == 0 else "danger"
        status_text = "OK" if failed == 0 else f"{failed} en echec"

        failed_html = ""
        if data.get("failed"):
            failed_html = '<div style="margin-top:10px;color:var(--danger)">En echec : ' + \
                          ", ".join(data["failed"]) + "</div>"

        healed_html = ""
        if data.get("healed_services"):
            healed_html = '<div style="margin-top:8px;color:var(--warning)">Repares : ' + \
                           ", ".join(data["healed_services"]) + "</div>"

        return f"""<div class="card">
            <h2>Services JARVIS</h2>
            <div class="metric"><span class="label">Statut</span><span class="badge {status_badge}">{status_text}</span></div>
            <div class="metric"><span class="label">Actifs</span><span class="value">{active}</span></div>
            <div class="metric"><span class="label">En echec</span><span class="value">{failed}</span></div>
            <div class="metric"><span class="label">Repares (auto-healer)</span><span class="value">{healed}</span></div>
            {failed_html}
            {healed_html}
        </div>"""

    def _html_cluster(self, data: dict[str, Any]) -> str:
        """Section HTML : cluster."""
        if data.get("error"):
            return self._html_error_card("Cluster", data["error"])

        nodes_html = ""
        for name, info in data.get("nodes", {}).items():
            status = "online" if info.get("online") else "offline"
            label = "EN LIGNE" if info.get("online") else "HORS LIGNE"
            models = ", ".join(info.get("models", [])) or "aucun"
            nodes_html += f"""<div class="node-card">
                <div class="name">{name}</div>
                <div><span class="badge {status}">{label}</span></div>
                <div style="font-size:0.8em;color:var(--text-dim);margin-top:6px">{models}</div>
            </div>"""

        return f"""<div class="card">
            <h2>Cluster</h2>
            <div class="metric"><span class="label">Noeuds en ligne</span><span class="value">{data.get('online_count', 0)}/{data.get('total_nodes', 0)}</span></div>
            <div class="metric"><span class="label">Modeles charges</span><span class="value">{data.get('total_models', 0)}</span></div>
            <div class="node-grid" style="margin-top:12px">
                {nodes_html}
            </div>
        </div>"""

    def _html_voice(self, data: dict[str, Any]) -> str:
        """Section HTML : commandes vocales."""
        if data.get("error"):
            return self._html_error_card("Commandes Vocales", data["error"])

        rate = data.get("success_rate", 100)
        rate_badge = "success" if rate >= 95 else ("warning" if rate >= 80 else "danger")

        top_html = ""
        if data.get("top_commands"):
            rows = ""
            for cmd in data["top_commands"]:
                rows += f'<tr><td>{cmd["command"]}</td><td>{cmd["count"]}</td></tr>'
            top_html = f"""<table>
                <tr><th>Commande</th><th>Count</th></tr>
                {rows}
            </table>"""

        return f"""<div class="card">
            <h2>Commandes Vocales</h2>
            <div class="metric"><span class="label">Total executees</span><span class="value">{data.get('total_executed', 0)}</span></div>
            <div class="metric"><span class="label">Taux de succes</span><span class="badge {rate_badge}">{rate}%</span></div>
            <div class="metric"><span class="label">Echecs</span><span class="value">{data.get('failure_count', 0)}</span></div>
            {top_html}
        </div>"""

    def _html_brain(self, data: dict[str, Any]) -> str:
        """Section HTML : brain."""
        if data.get("error"):
            return self._html_error_card("Brain", data["error"])

        return f"""<div class="card">
            <h2>Brain</h2>
            <div class="metric"><span class="label">Skills totaux</span><span class="value">{data.get('total_skills', 0)}</span></div>
            <div class="metric"><span class="label">Patterns detectes</span><span class="value">{data.get('patterns_detected', 0)}</span></div>
            <div class="metric"><span class="label">Cycles improve (total)</span><span class="value">{data.get('improve_cycles', 0)}</span></div>
            <div class="metric"><span class="label">Cycles improve (aujourd'hui)</span><span class="value">{data.get('improve_cycles_today', 0)}</span></div>
        </div>"""

    def _html_security(self, data: dict[str, Any]) -> str:
        """Section HTML : sécurité."""
        if data.get("error"):
            return self._html_error_card("Securite", data["error"])

        logins = data.get("failed_login_attempts", 0)
        login_badge = "success" if logins == 0 else ("warning" if logins < 10 else "danger")

        fw_status = data.get("firewall_status", "inconnu")
        fw_badge = "success" if fw_status == "actif" else "warning"

        ports = ", ".join(data.get("open_ports", [])[:15]) or "aucun"

        return f"""<div class="card">
            <h2>Securite</h2>
            <div class="metric"><span class="label">Tentatives connexion echouees</span><span class="badge {login_badge}">{logins}</span></div>
            <div class="metric"><span class="label">Firewall</span><span class="badge {fw_badge}">{fw_status}</span></div>
            <div class="metric"><span class="label">Fail2ban</span><span class="value">{'actif' if data.get('fail2ban_active') else 'inactif'}</span></div>
            <div class="metric"><span class="label">Ports ouverts ({data.get('open_ports_count', 0)})</span><span class="value" style="font-size:0.85em">{ports}</span></div>
        </div>"""

    def _html_performance(self, data: dict[str, Any]) -> str:
        """Section HTML : performance 24h."""
        if data.get("error"):
            return self._html_error_card("Performance 24h", data["error"])

        def fmt_minmaxavg(d: dict) -> str:
            if not d:
                return "N/A"
            return f"min {d.get('min', '?')} | avg {d.get('avg', '?')} | max {d.get('max', '?')}"

        return f"""<div class="card">
            <h2>Performance 24h</h2>
            <div class="metric"><span class="label">Echantillons</span><span class="value">{data.get('samples_count', 0)}</span></div>
            <div class="metric"><span class="label">CPU %</span><span class="value">{fmt_minmaxavg(data.get('cpu', {}))}</span></div>
            <div class="metric"><span class="label">RAM %</span><span class="value">{fmt_minmaxavg(data.get('ram', {}))}</span></div>
            <div class="metric"><span class="label">GPU Temp °C</span><span class="value">{fmt_minmaxavg(data.get('gpu_temp', {}))}</span></div>
        </div>"""

    def _html_notifications(self, data: dict[str, Any]) -> str:
        """Section HTML : notifications."""
        if data.get("error"):
            return self._html_error_card("Notifications", data["error"])

        crit = data.get("critical_count", 0)
        warn = data.get("warning_count", 0)

        return f"""<div class="card">
            <h2>Notifications</h2>
            <div class="metric"><span class="label">Total</span><span class="value">{data.get('total_count', 0)}</span></div>
            <div class="metric"><span class="label">Critiques</span><span class="badge {'danger' if crit > 0 else 'success'}">{crit}</span></div>
            <div class="metric"><span class="label">Warnings</span><span class="badge {'warning' if warn > 0 else 'success'}">{warn}</span></div>
            <div class="metric"><span class="label">Info</span><span class="value">{data.get('info_count', 0)}</span></div>
        </div>"""

    def _html_git(self, data: dict[str, Any]) -> str:
        """Section HTML : activité git."""
        if data.get("error"):
            return self._html_error_card("Git", data["error"])

        commits_html = ""
        if data.get("commits"):
            rows = "".join(f"<tr><td>{c}</td></tr>" for c in data["commits"][:10])
            commits_html = f'<table><tr><th>Commits recents</th></tr>{rows}</table>'

        return f"""<div class="card">
            <h2>Git</h2>
            <div class="metric"><span class="label">Commits</span><span class="value">{data.get('commits_count', 0)}</span></div>
            <div class="metric"><span class="label">Fichiers modifies</span><span class="value">{data.get('files_changed', 0)}</span></div>
            {commits_html}
        </div>"""

    def _html_recommendations(self, recs: list[str]) -> str:
        """Section HTML : recommandations."""
        items = "".join(f"<li>{r}</li>" for r in recs)
        return f"""<div class="card full-width">
            <h2>Recommandations</h2>
            <ul class="rec-list">{items}</ul>
        </div>"""

    def _html_error_card(self, title: str, error: str) -> str:
        """Carte d'erreur générique."""
        return f"""<div class="card">
            <h2>{title}</h2>
            <div style="color:var(--danger)">Erreur : {error}</div>
        </div>"""

    # ──────────────────────────────────────────────
    # Rendu texte (Telegram)
    # ──────────────────────────────────────────────

    def _render_summary(self, report: dict[str, Any]) -> str:
        """Génère un résumé texte <4000 chars pour Telegram."""
        sections = report.get("sections", {})
        recs = report.get("recommendations", [])
        lines: list[str] = []

        lines.append(f"JARVIS RAPPORT — {report['date']}")
        lines.append("=" * 30)

        # Système
        sys_data = sections.get("system", {})
        if not sys_data.get("error"):
            lines.append("")
            lines.append(f"SYSTEME: up {sys_data.get('uptime', '?')} | CPU {sys_data.get('cpu_avg_percent', '?')}% | RAM {sys_data.get('ram_percent', '?')}%")
            if sys_data.get("gpu_count", 0) > 0:
                lines.append(f"  GPU: {sys_data.get('gpu_count')}x | max {sys_data.get('gpu_max_temp_c', '?')}C | VRAM {sys_data.get('vram_used_mb', 0)}/{sys_data.get('vram_total_mb', 0)}MB")
            lines.append(f"  Disque: {sys_data.get('disk_free_gb', '?')}GB libre ({sys_data.get('disk_percent_used', '?')}%)")

        # Services
        svc_data = sections.get("services", {})
        if not svc_data.get("error"):
            failed = svc_data.get("failed_count", 0)
            active = svc_data.get("active_count", 0)
            healed = svc_data.get("healed_count", 0)
            status = "OK" if failed == 0 else f"{failed} KO"
            lines.append(f"\nSERVICES: {active} actifs | {status} | {healed} repares")

        # Cluster
        cluster_data = sections.get("cluster", {})
        if not cluster_data.get("error"):
            online = cluster_data.get("online_count", 0)
            total = cluster_data.get("total_nodes", 0)
            models = cluster_data.get("total_models", 0)
            lines.append(f"\nCLUSTER: {online}/{total} en ligne | {models} modeles")
            for name, info in cluster_data.get("nodes", {}).items():
                status = "ON" if info.get("online") else "OFF"
                lines.append(f"  {name}: {status}")

        # Vocales
        voice_data = sections.get("voice_commands", {})
        if not voice_data.get("error") and voice_data.get("total_executed", 0) > 0:
            lines.append(f"\nVOCAL: {voice_data.get('total_executed', 0)} cmds | {voice_data.get('success_rate', 100)}% succes")

        # Brain
        brain_data = sections.get("brain", {})
        if not brain_data.get("error"):
            lines.append(f"\nBRAIN: {brain_data.get('total_skills', 0)} skills | {brain_data.get('patterns_detected', 0)} patterns | {brain_data.get('improve_cycles_today', 0)} cycles")

        # Sécurité
        sec_data = sections.get("security", {})
        if not sec_data.get("error"):
            logins = sec_data.get("failed_login_attempts", 0)
            fw = sec_data.get("firewall_status", "?")
            lines.append(f"\nSECU: {logins} tentatives echouees | FW: {fw}")

        # Performance
        perf_data = sections.get("performance", {})
        if not perf_data.get("error") and perf_data.get("samples_count", 0) > 0:
            cpu_info = perf_data.get("cpu", {})
            if cpu_info:
                lines.append(f"\nPERF 24h: CPU {cpu_info.get('avg', '?')}% avg (max {cpu_info.get('max', '?')}%)")

        # Notifications
        notif_data = sections.get("notifications", {})
        if not notif_data.get("error"):
            crit = notif_data.get("critical_count", 0)
            warn = notif_data.get("warning_count", 0)
            total = notif_data.get("total_count", 0)
            if total > 0:
                lines.append(f"\nNOTIFS: {total} total | {crit} critiques | {warn} warnings")

        # Git
        git_data = sections.get("git", {})
        if not git_data.get("error") and git_data.get("commits_count", 0) > 0:
            lines.append(f"\nGIT: {git_data.get('commits_count', 0)} commits | {git_data.get('files_changed', 0)} fichiers")

        # Recommandations
        if recs:
            lines.append(f"\nRECOMMANDATIONS:")
            for r in recs[:5]:  # Max 5 pour Telegram
                lines.append(f"  - {r}")

        summary = "\n".join(lines)

        # Tronquer si >4000 chars
        if len(summary) > 3950:
            summary = summary[:3900] + "\n\n... (tronque)"

        return summary

    # ──────────────────────────────────────────────
    # Utilitaires
    # ──────────────────────────────────────────────

    @staticmethod
    def _resolve_date(date: str | None) -> str:
        """Résout la date cible (YYYY-MM-DD). None → aujourd'hui."""
        if date:
            # Valider le format
            datetime.strptime(date, "%Y-%m-%d")
            return date
        return datetime.now().strftime("%Y-%m-%d")
