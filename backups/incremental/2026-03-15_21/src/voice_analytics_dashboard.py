"""voice_analytics_dashboard.py — Dashboard analytique vocal JARVIS.

Analyse les données de voice_analytics et voice_commands depuis jarvis.db,
génère des rapports JSON et un dashboard HTML interactif avec Chart.js.

Usage:
    python src/voice_analytics_dashboard.py          # Génère le HTML
    python src/voice_analytics_dashboard.py --json   # Affiche le rapport JSON
"""
from __future__ import annotations

import html
import json
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# Chemin racine JARVIS
JARVIS_HOME = Path(__file__).resolve().parent.parent
DB_PATH = JARVIS_HOME / "data" / "jarvis.db"
HTML_OUTPUT = JARVIS_HOME / "docs" / "voice_analytics.html"

# Modules vocaux connus
VOICE_MODULES = ["desktop", "window", "mouse", "dictation", "screen_reader"]

# Étapes du pipeline vocal
PIPELINE_STAGES = ["vad", "stt", "routing", "execution", "tts"]


def _connect_db() -> sqlite3.Connection:
    """Connexion à la base JARVIS avec row_factory."""
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _ts_hours_ago(hours: int) -> float:
    """Retourne le timestamp Unix d'il y a N heures."""
    return time.time() - (hours * 3600)


def _ts_days_ago(days: int) -> float:
    """Retourne le timestamp Unix d'il y a N jours."""
    return time.time() - (days * 86400)


def _esc(text: str) -> str:
    """Échappe le HTML pour éviter les injections XSS."""
    return html.escape(str(text), quote=True)


class VoiceAnalyticsDashboard:
    """Analyse et dashboard des données vocales JARVIS."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self._ensure_tables()

    def _ensure_tables(self):
        """Vérifie que les tables nécessaires existent, les crée sinon."""
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=5)
            cursor = conn.cursor()
            # Table voice_analytics (devrait déjà exister)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voice_analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL DEFAULT (unixepoch()),
                    stage TEXT NOT NULL,
                    text TEXT DEFAULT '',
                    confidence REAL DEFAULT 0,
                    method TEXT DEFAULT '',
                    latency_ms REAL DEFAULT 0,
                    success INTEGER DEFAULT 1
                )
            """)
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _get_conn(self) -> sqlite3.Connection:
        """Retourne une connexion DB."""
        conn = sqlite3.connect(str(self.db_path), timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    # ─── Rapport principal ────────────────────────────────────────

    def generate_report(self, hours: int = 24) -> dict:
        """Génère un rapport JSON complet des analytics vocales.

        Args:
            hours: Fenêtre d'analyse en heures (défaut: 24h)

        Returns:
            Dictionnaire avec toutes les métriques
        """
        since = _ts_hours_ago(hours)
        conn = self._get_conn()

        report = {
            "generated_at": datetime.now().isoformat(),
            "period_hours": hours,
            "kpis": self._compute_kpis(conn, since),
            "commands_per_hour": self._commands_per_hour(conn, since),
            "success_by_module": self._success_by_module(conn, since),
            "top_commands": self._top_commands(conn, limit=10),
            "top_failures": self._top_failures(conn, limit=10),
            "latency_by_stage": self._latency_by_stage(conn, since),
            "stt_distribution": self._stt_distribution(conn, since),
            "recent_errors": self._recent_errors(conn, limit=20),
        }

        conn.close()
        return report

    def _compute_kpis(self, conn: sqlite3.Connection, since: float) -> dict:
        """Calcule les KPIs principaux."""
        cursor = conn.cursor()

        # Total commandes dans la période
        cursor.execute(
            "SELECT COUNT(*) FROM voice_analytics WHERE timestamp >= ?", (since,)
        )
        total = cursor.fetchone()[0]

        # Commandes réussies
        cursor.execute(
            "SELECT COUNT(*) FROM voice_analytics WHERE timestamp >= ? AND success = 1",
            (since,),
        )
        success = cursor.fetchone()[0]

        # Taux de succès
        success_rate = round((success / total * 100) if total > 0 else 0, 1)

        # Latence moyenne globale
        cursor.execute(
            "SELECT AVG(latency_ms) FROM voice_analytics WHERE timestamp >= ? AND latency_ms > 0",
            (since,),
        )
        avg_latency = cursor.fetchone()[0] or 0

        # Total historique (toutes les commandes)
        cursor.execute("SELECT COUNT(*) FROM voice_analytics")
        total_all = cursor.fetchone()[0]

        # Commandes vocales enregistrées
        try:
            cursor.execute("SELECT COUNT(*) FROM voice_commands WHERE enabled = 1")
            active_commands = cursor.fetchone()[0]
        except Exception:
            active_commands = 0

        return {
            "total_commands": total,
            "total_all_time": total_all,
            "success_count": success,
            "failure_count": total - success,
            "success_rate": success_rate,
            "avg_latency_ms": round(avg_latency, 1),
            "active_voice_commands": active_commands,
        }

    def _commands_per_hour(self, conn: sqlite3.Connection, since: float) -> list:
        """Commandes groupées par heure."""
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                CAST(strftime('%H', timestamp, 'unixepoch', 'localtime') AS INTEGER) as hour,
                COUNT(*) as count,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count
            FROM voice_analytics
            WHERE timestamp >= ?
            GROUP BY hour
            ORDER BY hour
            """,
            (since,),
        )
        # Remplir les heures manquantes avec 0
        result_map = {}
        for row in cursor.fetchall():
            result_map[row[0]] = {"hour": row[0], "count": row[1], "success": row[2]}

        result = []
        for h in range(24):
            if h in result_map:
                result.append(result_map[h])
            else:
                result.append({"hour": h, "count": 0, "success": 0})
        return result

    def _success_by_module(self, conn: sqlite3.Connection, since: float) -> dict:
        """Taux de succès par module vocal (basé sur la catégorie de voice_commands)."""
        cursor = conn.cursor()

        # Mapper les méthodes/stages aux modules
        modules = {}
        for module in VOICE_MODULES:
            modules[module] = {"total": 0, "success": 0, "rate": 0}

        # Chercher dans voice_commands par catégorie
        try:
            cursor.execute(
                """
                SELECT category, SUM(usage_count) as total,
                       SUM(success_count) as successes, SUM(fail_count) as failures
                FROM voice_commands
                GROUP BY category
                """
            )
            for row in cursor.fetchall():
                cat = row[0] or "unknown"
                total = (row[1] or 0)
                successes = (row[2] or 0)
                # Mapper les catégories aux modules
                module = self._category_to_module(cat)
                if module in modules:
                    modules[module]["total"] += total
                    modules[module]["success"] += successes
        except Exception:
            pass

        # Ajouter les données de voice_analytics par méthode
        try:
            cursor.execute(
                """
                SELECT method, COUNT(*) as total,
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes
                FROM voice_analytics
                WHERE timestamp >= ? AND method != ''
                GROUP BY method
                """,
                (since,),
            )
            for row in cursor.fetchall():
                method = row[0] or "unknown"
                module = self._method_to_module(method)
                if module in modules:
                    modules[module]["total"] += row[1]
                    modules[module]["success"] += row[2]
        except Exception:
            pass

        # Calculer les taux
        for mod in modules:
            t = modules[mod]["total"]
            s = modules[mod]["success"]
            modules[mod]["rate"] = round((s / t * 100) if t > 0 else 0, 1)

        return modules

    def _category_to_module(self, category: str) -> str:
        """Mappe une catégorie de commande à un module vocal."""
        cat = category.lower()
        if any(k in cat for k in ["window", "switch", "workspace"]):
            return "window"
        if any(k in cat for k in ["mouse", "click", "scroll"]):
            return "mouse"
        if any(k in cat for k in ["dictation", "type", "text"]):
            return "dictation"
        if any(k in cat for k in ["screen_reader", "accessibility", "read"]):
            return "screen_reader"
        return "desktop"

    def _method_to_module(self, method: str) -> str:
        """Mappe une méthode analytics à un module vocal."""
        m = method.lower()
        if "window" in m:
            return "window"
        if "mouse" in m:
            return "mouse"
        if "dict" in m:
            return "dictation"
        if "screen" in m or "read" in m:
            return "screen_reader"
        return "desktop"

    def _top_commands(self, conn: sqlite3.Connection, limit: int = 10) -> list:
        """Top N commandes les plus utilisées."""
        cursor = conn.cursor()
        results = []

        # Depuis voice_commands
        try:
            cursor.execute(
                """
                SELECT name, category, usage_count, success_count, fail_count
                FROM voice_commands
                WHERE usage_count > 0
                ORDER BY usage_count DESC
                LIMIT ?
                """,
                (limit,),
            )
            for row in cursor.fetchall():
                results.append({
                    "name": row[0],
                    "category": row[1],
                    "usage_count": row[2],
                    "success_count": row[3],
                    "fail_count": row[4],
                })
        except Exception:
            pass

        # Fallback depuis voice_analytics si pas assez de données
        if len(results) < limit:
            try:
                cursor.execute(
                    """
                    SELECT text, COUNT(*) as cnt,
                           SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as ok
                    FROM voice_analytics
                    WHERE text != ''
                    GROUP BY text
                    ORDER BY cnt DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                for row in cursor.fetchall():
                    results.append({
                        "name": row[0],
                        "category": "analytics",
                        "usage_count": row[1],
                        "success_count": row[2],
                        "fail_count": row[1] - row[2],
                    })
            except Exception:
                pass

        return results[:limit]

    def _top_failures(self, conn: sqlite3.Connection, limit: int = 10) -> list:
        """Top N commandes qui échouent le plus."""
        cursor = conn.cursor()
        results = []

        # Depuis voice_commands
        try:
            cursor.execute(
                """
                SELECT name, category, fail_count, usage_count, success_count
                FROM voice_commands
                WHERE fail_count > 0
                ORDER BY fail_count DESC
                LIMIT ?
                """,
                (limit,),
            )
            for row in cursor.fetchall():
                usage = row[3] or 1
                results.append({
                    "name": row[0],
                    "category": row[1],
                    "fail_count": row[2],
                    "usage_count": row[3],
                    "fail_rate": round(row[2] / usage * 100, 1),
                })
        except Exception:
            pass

        # Fallback analytics
        if len(results) < limit:
            try:
                cursor.execute(
                    """
                    SELECT text, COUNT(*) as total,
                           SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as fails
                    FROM voice_analytics
                    WHERE text != '' AND success = 0
                    GROUP BY text
                    ORDER BY fails DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                for row in cursor.fetchall():
                    results.append({
                        "name": row[0],
                        "category": "analytics",
                        "fail_count": row[2],
                        "usage_count": row[1],
                        "fail_rate": round(row[2] / max(row[1], 1) * 100, 1),
                    })
            except Exception:
                pass

        return results[:limit]

    def _latency_by_stage(self, conn: sqlite3.Connection, since: float) -> dict:
        """Latence moyenne par étape du pipeline."""
        cursor = conn.cursor()
        stages = {}

        cursor.execute(
            """
            SELECT stage, AVG(latency_ms) as avg_ms,
                   MIN(latency_ms) as min_ms, MAX(latency_ms) as max_ms,
                   COUNT(*) as count
            FROM voice_analytics
            WHERE timestamp >= ? AND latency_ms > 0
            GROUP BY stage
            """,
            (since,),
        )
        for row in cursor.fetchall():
            stages[row[0]] = {
                "avg_ms": round(row[1], 1),
                "min_ms": round(row[2], 1),
                "max_ms": round(row[3], 1),
                "count": row[4],
            }

        # Ajouter les étapes manquantes avec des zéros
        for stage in PIPELINE_STAGES:
            if stage not in stages:
                stages[stage] = {"avg_ms": 0, "min_ms": 0, "max_ms": 0, "count": 0}

        return stages

    def _stt_distribution(self, conn: sqlite3.Connection, since: float) -> dict:
        """Distribution des méthodes STT utilisées."""
        cursor = conn.cursor()
        dist = {"whisper_local": 0, "whisper_cloud": 0, "other": 0}

        cursor.execute(
            """
            SELECT method, COUNT(*) as cnt
            FROM voice_analytics
            WHERE timestamp >= ? AND method != ''
            GROUP BY method
            """,
            (since,),
        )
        for row in cursor.fetchall():
            method = (row[0] or "").lower()
            if "local" in method or "whisper" in method and "cloud" not in method:
                dist["whisper_local"] += row[1]
            elif "cloud" in method or "api" in method:
                dist["whisper_cloud"] += row[1]
            else:
                dist["other"] += row[1]

        # Si aucune données STT, compter les analytics avec stage stt
        if sum(dist.values()) == 0:
            cursor.execute(
                """
                SELECT COUNT(*) FROM voice_analytics
                WHERE timestamp >= ? AND stage = 'stt'
                """,
                (since,),
            )
            cnt = cursor.fetchone()[0]
            dist["whisper_local"] = cnt  # Défaut: local

        return dist

    def _recent_errors(self, conn: sqlite3.Connection, limit: int = 20) -> list:
        """Dernières erreurs enregistrées."""
        cursor = conn.cursor()
        errors = []

        cursor.execute(
            """
            SELECT timestamp, stage, text, method, latency_ms
            FROM voice_analytics
            WHERE success = 0
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        for row in cursor.fetchall():
            ts = row[0]
            try:
                dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                dt = str(ts)
            errors.append({
                "timestamp": dt,
                "stage": row[1],
                "text": row[2],
                "method": row[3],
                "latency_ms": row[4],
            })
        return errors

    # ─── Tendances ────────────────────────────────────────────────

    def get_trends(self, days: int = 7) -> dict:
        """Analyse les tendances sur N jours.

        Args:
            days: Nombre de jours à analyser

        Returns:
            Dictionnaire avec tendances quotidiennes et comparaisons
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        since = _ts_days_ago(days)

        # Commandes par jour
        cursor.execute(
            """
            SELECT date(timestamp, 'unixepoch', 'localtime') as day,
                   COUNT(*) as total,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                   AVG(latency_ms) as avg_lat
            FROM voice_analytics
            WHERE timestamp >= ?
            GROUP BY day
            ORDER BY day
            """,
            (since,),
        )

        daily = []
        for row in cursor.fetchall():
            total = row[1]
            successes = row[2]
            daily.append({
                "date": row[0],
                "total": total,
                "successes": successes,
                "failures": total - successes,
                "success_rate": round(successes / max(total, 1) * 100, 1),
                "avg_latency_ms": round(row[3] or 0, 1),
            })

        # Comparaison semaine actuelle vs précédente
        mid = _ts_days_ago(days // 2)
        cursor.execute(
            "SELECT COUNT(*), AVG(latency_ms) FROM voice_analytics WHERE timestamp >= ? AND timestamp < ?",
            (since, mid),
        )
        r1 = cursor.fetchone()
        cursor.execute(
            "SELECT COUNT(*), AVG(latency_ms) FROM voice_analytics WHERE timestamp >= ?",
            (mid,),
        )
        r2 = cursor.fetchone()

        first_half = {"count": r1[0], "avg_latency": round(r1[1] or 0, 1)}
        second_half = {"count": r2[0], "avg_latency": round(r2[1] or 0, 1)}

        # Calcul de la tendance
        if first_half["count"] > 0:
            volume_trend = round(
                (second_half["count"] - first_half["count"]) / first_half["count"] * 100, 1
            )
        else:
            volume_trend = 0

        conn.close()
        return {
            "period_days": days,
            "daily": daily,
            "first_half": first_half,
            "second_half": second_half,
            "volume_trend_pct": volume_trend,
        }

    # ─── Analyse des échecs ───────────────────────────────────────

    def get_failure_analysis(self) -> list:
        """Analyse approfondie des échecs avec suggestions de correction.

        Returns:
            Liste de dicts avec pattern d'échec, fréquence et suggestion
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        analyses = []

        # 1. Échecs par stage
        cursor.execute(
            """
            SELECT stage, COUNT(*) as cnt,
                   GROUP_CONCAT(DISTINCT text) as examples
            FROM voice_analytics
            WHERE success = 0
            GROUP BY stage
            ORDER BY cnt DESC
            """
        )
        for row in cursor.fetchall():
            stage = row[0]
            count = row[1]
            examples = (row[2] or "")[:200]
            suggestion = self._suggest_fix(stage, count, examples)
            analyses.append({
                "pattern": f"Failures in stage: {stage}",
                "count": count,
                "examples": examples.split(",")[:5] if examples else [],
                "suggestion": suggestion,
            })

        # 2. Commandes à fort taux d'échec
        try:
            cursor.execute(
                """
                SELECT name, category, fail_count, usage_count
                FROM voice_commands
                WHERE fail_count > 0 AND usage_count > 2
                ORDER BY CAST(fail_count AS REAL) / usage_count DESC
                LIMIT 10
                """
            )
            for row in cursor.fetchall():
                rate = round(row[2] / max(row[3], 1) * 100, 1)
                analyses.append({
                    "pattern": f"High failure rate: {row[0]} ({row[1]})",
                    "count": row[2],
                    "examples": [f"{rate}% fail rate over {row[3]} uses"],
                    "suggestion": f"Review command '{row[0]}' triggers and action. "
                                  f"Consider adding aliases or simplifying the trigger phrase.",
                })
        except Exception:
            pass

        # 3. Patterns temporels d'échecs
        cursor.execute(
            """
            SELECT CAST(strftime('%H', timestamp, 'unixepoch', 'localtime') AS INTEGER) as hour,
                   COUNT(*) as fails
            FROM voice_analytics
            WHERE success = 0
            GROUP BY hour
            ORDER BY fails DESC
            LIMIT 3
            """
        )
        peak_hours = cursor.fetchall()
        if peak_hours:
            hours_str = ", ".join(f"{r[0]}h ({r[1]} fails)" for r in peak_hours)
            analyses.append({
                "pattern": "Peak failure hours",
                "count": sum(r[1] for r in peak_hours),
                "examples": [hours_str],
                "suggestion": "Check for ambient noise or system load during these hours. "
                              "Consider adjusting VAD sensitivity or STT model.",
            })

        conn.close()
        return analyses

    def _suggest_fix(self, stage: str, count: int, examples: str) -> str:
        """Génère une suggestion de correction basée sur le stage et les patterns."""
        suggestions = {
            "vad": "Adjust VAD sensitivity threshold. Check microphone levels and ambient noise.",
            "stt": "Consider switching STT model or adjusting beam size. "
                   "Check audio quality and sample rate.",
            "routing": "Review command routing rules. Some commands may need "
                       "updated triggers or new category mappings.",
            "execution": "Check system permissions and service availability. "
                         "Verify that target applications are running.",
            "tts": "Check TTS engine status and audio output device. "
                   "Verify espeak/piper installation.",
            "context": "Context resolution failed. Ensure context providers "
                       "are returning valid data.",
            "route": "Command routing issues. Check that command patterns "
                     "match the intent classifier rules.",
        }
        base = suggestions.get(stage, "Investigate logs for this stage to identify root cause.")
        if count > 50:
            base += " HIGH PRIORITY: Frequent failures detected."
        return base

    # ─── Génération HTML ──────────────────────────────────────────

    def generate_html(self, hours: int = 24) -> str:
        """Génère le dashboard HTML complet et l'écrit dans docs/.

        Args:
            hours: Fenêtre d'analyse en heures

        Returns:
            Chemin du fichier HTML généré
        """
        report = self.generate_report(hours)
        trends = self.get_trends(days=7)
        failures = self.get_failure_analysis()

        html_content = self._build_html(report, trends, failures)

        # Créer le dossier docs/ si nécessaire
        HTML_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        HTML_OUTPUT.write_text(html_content, encoding="utf-8")
        return str(HTML_OUTPUT)

    def _build_html(self, report: dict, trends: dict, failures: list) -> str:
        """Construit le HTML du dashboard.

        Toutes les données sont échappées pour éviter les injections XSS.
        Les graphiques utilisent Chart.js avec des données JSON sérialisées.
        Le rendu dynamique utilise textContent (pas innerHTML) pour la sécurité.
        """
        kpis = report["kpis"]
        # Sérialiser les données pour Chart.js (données internes de confiance)
        commands_per_hour = json.dumps(report["commands_per_hour"])
        modules_data = json.dumps(report["success_by_module"])
        top_commands = json.dumps(report["top_commands"])
        top_failures = json.dumps(report["top_failures"])
        latency_data = json.dumps(report["latency_by_stage"])
        stt_dist = json.dumps(report["stt_distribution"])
        recent_errors = json.dumps(report["recent_errors"])
        trends_json = json.dumps(trends)
        failures_json = json.dumps(failures)
        gen_time = _esc(report["generated_at"])

        # Classes CSS pour les KPIs (calculées côté serveur)
        rate_class = "green" if kpis["success_rate"] >= 90 else "orange" if kpis["success_rate"] >= 70 else "red"
        lat_class = "green" if kpis["avg_latency_ms"] < 500 else "orange" if kpis["avg_latency_ms"] < 1000 else "red"

        return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60">
    <title>JARVIS Voice Analytics Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: #0a0e17;
            color: #c8d6e5;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            padding: 20px;
            min-height: 100vh;
        }}
        .header {{
            text-align: center;
            padding: 20px 0;
            border-bottom: 1px solid #00e5ff33;
            margin-bottom: 24px;
        }}
        .header h1 {{
            color: #00e5ff;
            font-size: 28px;
            letter-spacing: 2px;
            text-shadow: 0 0 20px #00e5ff44;
        }}
        .header .subtitle {{
            color: #5f7d95;
            font-size: 13px;
            margin-top: 6px;
        }}
        .kpis {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .kpi {{
            background: linear-gradient(135deg, #111827, #1a2332);
            border: 1px solid #00e5ff22;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            transition: border-color 0.3s;
        }}
        .kpi:hover {{ border-color: #00e5ff66; }}
        .kpi .value {{
            font-size: 32px;
            font-weight: 700;
            color: #00e5ff;
            text-shadow: 0 0 10px #00e5ff44;
        }}
        .kpi .label {{
            font-size: 12px;
            color: #5f7d95;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 6px;
        }}
        .kpi .value.green {{ color: #00ff88; text-shadow: 0 0 10px #00ff8844; }}
        .kpi .value.orange {{ color: #ffaa00; text-shadow: 0 0 10px #ffaa0044; }}
        .kpi .value.red {{ color: #ff4444; text-shadow: 0 0 10px #ff444444; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }}
        .card {{
            background: #111827;
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 20px;
        }}
        .card h2 {{
            color: #00e5ff;
            font-size: 16px;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid #1e293b;
        }}
        .card canvas {{ max-height: 280px; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th, td {{
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid #1e293b;
        }}
        th {{
            color: #00e5ff;
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        tr:hover td {{ background: #1a2332; }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 600;
        }}
        .badge-success {{ background: #00ff8822; color: #00ff88; }}
        .badge-danger {{ background: #ff444422; color: #ff4444; }}
        .badge-warn {{ background: #ffaa0022; color: #ffaa00; }}
        .error-timeline {{
            max-height: 300px;
            overflow-y: auto;
            font-size: 12px;
        }}
        .error-item {{
            padding: 8px 12px;
            border-left: 3px solid #ff4444;
            margin-bottom: 8px;
            background: #1a0a0a;
            border-radius: 0 6px 6px 0;
        }}
        .error-ts {{ color: #5f7d95; font-size: 11px; }}
        .error-stage {{ color: #ffaa00; font-weight: 600; }}
        .error-text {{ color: #c8d6e5; }}
        .error-lat {{ color: #5f7d95; }}
        .suggestion {{
            padding: 12px;
            background: #0a1628;
            border-left: 3px solid #00e5ff;
            border-radius: 0 8px 8px 0;
            margin-bottom: 10px;
            font-size: 13px;
        }}
        .suggestion .pattern {{ color: #ffaa00; font-weight: 600; }}
        .suggestion .fix {{ color: #aabbcc; margin-top: 4px; }}
        .footer {{
            text-align: center;
            color: #334155;
            font-size: 11px;
            padding: 20px 0;
            border-top: 1px solid #1e293b;
        }}
        ::-webkit-scrollbar {{ width: 6px; }}
        ::-webkit-scrollbar-track {{ background: #0a0e17; }}
        ::-webkit-scrollbar-thumb {{ background: #1e293b; border-radius: 3px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #00e5ff44; }}
    </style>
</head>
<body>

<div class="header">
    <h1>JARVIS VOICE ANALYTICS</h1>
    <div class="subtitle">Generated: {gen_time} | Period: {_esc(str(report['period_hours']))}h | Auto-refresh: 60s</div>
</div>

<!-- KPIs -->
<div class="kpis">
    <div class="kpi">
        <div class="value">{_esc(str(kpis['total_commands']))}</div>
        <div class="label">Commands (period)</div>
    </div>
    <div class="kpi">
        <div class="value">{_esc(str(kpis['total_all_time']))}</div>
        <div class="label">Total All Time</div>
    </div>
    <div class="kpi">
        <div class="value {rate_class}">{_esc(str(kpis['success_rate']))}%</div>
        <div class="label">Success Rate</div>
    </div>
    <div class="kpi">
        <div class="value {lat_class}">{_esc(str(kpis['avg_latency_ms']))}ms</div>
        <div class="label">Avg Latency</div>
    </div>
    <div class="kpi">
        <div class="value red">{_esc(str(kpis['failure_count']))}</div>
        <div class="label">Failures</div>
    </div>
    <div class="kpi">
        <div class="value">{_esc(str(kpis['active_voice_commands']))}</div>
        <div class="label">Active Commands</div>
    </div>
</div>

<!-- Graphiques -->
<div class="grid">
    <div class="card">
        <h2>Commands per Hour</h2>
        <canvas id="chartHourly"></canvas>
    </div>
    <div class="card">
        <h2>Module Distribution</h2>
        <canvas id="chartModules"></canvas>
    </div>
    <div class="card">
        <h2>Latency by Pipeline Stage</h2>
        <canvas id="chartLatency"></canvas>
    </div>
    <div class="card">
        <h2>STT Method Distribution</h2>
        <canvas id="chartSTT"></canvas>
    </div>
</div>

<!-- Tableaux et timeline -->
<div class="grid">
    <div class="card">
        <h2>Top 10 Commands</h2>
        <div style="overflow-x: auto;">
            <table id="tableTop">
                <thead>
                    <tr><th>Command</th><th>Category</th><th>Uses</th><th>Success</th><th>Fails</th></tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>
    </div>
    <div class="card">
        <h2>Top 10 Failing Commands</h2>
        <div style="overflow-x: auto;">
            <table id="tableFails">
                <thead>
                    <tr><th>Command</th><th>Category</th><th>Fails</th><th>Fail Rate</th></tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>
    </div>
    <div class="card">
        <h2>Recent Errors Timeline</h2>
        <div class="error-timeline" id="errorTimeline"></div>
    </div>
    <div class="card">
        <h2>Failure Analysis &amp; Suggestions</h2>
        <div id="failureAnalysis"></div>
    </div>
</div>

<!-- Tendances -->
<div class="grid">
    <div class="card" style="grid-column: 1 / -1;">
        <h2>7-Day Trend</h2>
        <canvas id="chartTrend"></canvas>
    </div>
</div>

<div class="footer">
    JARVIS Voice Analytics Dashboard &mdash; Powered by JARVIS OS
</div>

<script>
    // Données injectées (sources internes de confiance uniquement)
    const hourlyData = {commands_per_hour};
    const modulesData = {modules_data};
    const topCommands = {top_commands};
    const topFailures = {top_failures};
    const latencyData = {latency_data};
    const sttDist = {stt_dist};
    const recentErrors = {recent_errors};
    const trends = {trends_json};
    const failureAnalysis = {failures_json};

    // Couleurs JARVIS
    const CYAN = '#00e5ff';
    const GREEN = '#00ff88';
    const ORANGE = '#ffaa00';
    const RED = '#ff4444';
    const PURPLE = '#a855f7';
    const BLUE = '#3b82f6';

    Chart.defaults.color = '#5f7d95';
    Chart.defaults.borderColor = '#1e293b';

    // 1. Commandes par heure (barres empilées)
    new Chart(document.getElementById('chartHourly'), {{
        type: 'bar',
        data: {{
            labels: hourlyData.map(d => d.hour + 'h'),
            datasets: [
                {{
                    label: 'Success',
                    data: hourlyData.map(d => d.success),
                    backgroundColor: GREEN + '88',
                    borderColor: GREEN,
                    borderWidth: 1,
                }},
                {{
                    label: 'Failures',
                    data: hourlyData.map(d => d.count - d.success),
                    backgroundColor: RED + '88',
                    borderColor: RED,
                    borderWidth: 1,
                }}
            ]
        }},
        options: {{
            responsive: true,
            plugins: {{ legend: {{ position: 'top' }} }},
            scales: {{
                x: {{ stacked: true }},
                y: {{ stacked: true, beginAtZero: true }}
            }}
        }}
    }});

    // 2. Répartition par module (camembert)
    const moduleNames = Object.keys(modulesData);
    const moduleTotals = moduleNames.map(k => modulesData[k].total);
    new Chart(document.getElementById('chartModules'), {{
        type: 'doughnut',
        data: {{
            labels: moduleNames.map(n => n.charAt(0).toUpperCase() + n.slice(1)),
            datasets: [{{
                data: moduleTotals,
                backgroundColor: [CYAN + 'cc', GREEN + 'cc', ORANGE + 'cc', PURPLE + 'cc', BLUE + 'cc'],
                borderColor: '#0a0e17',
                borderWidth: 2,
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{ position: 'right' }},
                tooltip: {{
                    callbacks: {{
                        afterLabel: function(ctx) {{
                            const mod = moduleNames[ctx.dataIndex];
                            return 'Success: ' + modulesData[mod].rate + '%';
                        }}
                    }}
                }}
            }}
        }}
    }});

    // 3. Latence par étape (barres horizontales)
    const stageNames = Object.keys(latencyData);
    new Chart(document.getElementById('chartLatency'), {{
        type: 'bar',
        data: {{
            labels: stageNames.map(s => s.toUpperCase()),
            datasets: [
                {{
                    label: 'Avg (ms)',
                    data: stageNames.map(s => latencyData[s].avg_ms),
                    backgroundColor: CYAN + '88',
                    borderColor: CYAN,
                    borderWidth: 1,
                }},
                {{
                    label: 'Max (ms)',
                    data: stageNames.map(s => latencyData[s].max_ms),
                    backgroundColor: ORANGE + '44',
                    borderColor: ORANGE,
                    borderWidth: 1,
                }}
            ]
        }},
        options: {{
            indexAxis: 'y',
            responsive: true,
            plugins: {{ legend: {{ position: 'top' }} }},
            scales: {{ x: {{ beginAtZero: true }} }}
        }}
    }});

    // 4. Distribution STT (camembert)
    new Chart(document.getElementById('chartSTT'), {{
        type: 'pie',
        data: {{
            labels: ['Whisper Local', 'Whisper Cloud', 'Other'],
            datasets: [{{
                data: [sttDist.whisper_local, sttDist.whisper_cloud, sttDist.other],
                backgroundColor: [CYAN + 'cc', PURPLE + 'cc', ORANGE + 'cc'],
                borderColor: '#0a0e17',
                borderWidth: 2,
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{ legend: {{ position: 'right' }} }}
        }}
    }});

    // 5. Tendances 7 jours
    if (trends.daily && trends.daily.length > 0) {{
        new Chart(document.getElementById('chartTrend'), {{
            type: 'line',
            data: {{
                labels: trends.daily.map(d => d.date),
                datasets: [
                    {{
                        label: 'Total Commands',
                        data: trends.daily.map(d => d.total),
                        borderColor: CYAN,
                        backgroundColor: CYAN + '22',
                        fill: true,
                        tension: 0.3,
                    }},
                    {{
                        label: 'Successes',
                        data: trends.daily.map(d => d.successes),
                        borderColor: GREEN,
                        backgroundColor: GREEN + '11',
                        fill: true,
                        tension: 0.3,
                    }},
                    {{
                        label: 'Failures',
                        data: trends.daily.map(d => d.failures),
                        borderColor: RED,
                        backgroundColor: RED + '11',
                        fill: true,
                        tension: 0.3,
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ position: 'top' }} }},
                scales: {{ y: {{ beginAtZero: true }} }}
            }}
        }});
    }}

    // Remplir un tableau de manière sécurisée (textContent uniquement)
    function fillTable(tableId, data, columns) {{
        var tbody = document.querySelector('#' + tableId + ' tbody');
        while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
        data.forEach(function(row) {{
            var tr = document.createElement('tr');
            columns.forEach(function(col) {{
                var td = document.createElement('td');
                var val = row[col.key];
                if (col.badge) {{
                    var span = document.createElement('span');
                    span.className = 'badge ' + col.badge(val);
                    span.textContent = val !== undefined ? val : '-';
                    td.appendChild(span);
                }} else {{
                    td.textContent = val !== undefined ? val : '-';
                }}
                tr.appendChild(td);
            }});
            tbody.appendChild(tr);
        }});
    }}

    fillTable('tableTop', topCommands, [
        {{ key: 'name' }},
        {{ key: 'category' }},
        {{ key: 'usage_count' }},
        {{ key: 'success_count', badge: function(v) {{ return v > 0 ? 'badge-success' : ''; }} }},
        {{ key: 'fail_count', badge: function(v) {{ return v > 0 ? 'badge-danger' : 'badge-success'; }} }}
    ]);

    fillTable('tableFails', topFailures, [
        {{ key: 'name' }},
        {{ key: 'category' }},
        {{ key: 'fail_count', badge: function() {{ return 'badge-danger'; }} }},
        {{ key: 'fail_rate', badge: function(v) {{ return v > 50 ? 'badge-danger' : 'badge-warn'; }} }}
    ]);

    // Timeline erreurs (construction DOM sécurisée avec textContent)
    (function() {{
        var timeline = document.getElementById('errorTimeline');
        if (recentErrors.length === 0) {{
            var p = document.createElement('p');
            p.style.cssText = 'color:#5f7d95;text-align:center;padding:20px;';
            p.textContent = 'No recent errors';
            timeline.appendChild(p);
        }} else {{
            recentErrors.forEach(function(err) {{
                var div = document.createElement('div');
                div.className = 'error-item';

                var tsSpan = document.createElement('span');
                tsSpan.className = 'error-ts';
                tsSpan.textContent = err.timestamp;
                div.appendChild(tsSpan);

                div.appendChild(document.createTextNode(' '));

                var stageSpan = document.createElement('span');
                stageSpan.className = 'error-stage';
                stageSpan.textContent = '[' + err.stage + ']';
                div.appendChild(stageSpan);

                div.appendChild(document.createTextNode(' '));

                var textSpan = document.createElement('span');
                textSpan.className = 'error-text';
                textSpan.textContent = err.text || 'N/A';
                div.appendChild(textSpan);

                if (err.latency_ms) {{
                    var latSpan = document.createElement('span');
                    latSpan.className = 'error-lat';
                    latSpan.textContent = ' (' + err.latency_ms + 'ms)';
                    div.appendChild(latSpan);
                }}

                timeline.appendChild(div);
            }});
        }}
    }})();

    // Analyse des échecs (construction DOM sécurisée avec textContent)
    (function() {{
        var analysisDiv = document.getElementById('failureAnalysis');
        if (failureAnalysis.length === 0) {{
            var p = document.createElement('p');
            p.style.cssText = 'color:#5f7d95;text-align:center;padding:20px;';
            p.textContent = 'No failure patterns detected';
            analysisDiv.appendChild(p);
        }} else {{
            failureAnalysis.forEach(function(item) {{
                var div = document.createElement('div');
                div.className = 'suggestion';

                var patDiv = document.createElement('div');
                patDiv.className = 'pattern';
                patDiv.textContent = item.pattern + ' (' + item.count + ' occurrences)';
                div.appendChild(patDiv);

                var fixDiv = document.createElement('div');
                fixDiv.className = 'fix';
                fixDiv.textContent = item.suggestion;
                div.appendChild(fixDiv);

                analysisDiv.appendChild(div);
            }});
        }}
    }})();
</script>
</body>
</html>"""


# ─── API endpoint pour jarvis_desktop_dashboard.py ────────────────

def get_voice_analytics_json(hours: int = 24) -> dict:
    """Fonction appelée par le endpoint GET /api/voice_analytics.

    Retourne les métriques vocales au format JSON.
    """
    dashboard = VoiceAnalyticsDashboard()
    report = dashboard.generate_report(hours)
    report["trends"] = dashboard.get_trends(days=7)
    report["failure_analysis"] = dashboard.get_failure_analysis()
    return report


# ─── Main ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    dashboard = VoiceAnalyticsDashboard()

    if "--json" in sys.argv:
        # Mode JSON
        report = dashboard.generate_report()
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        # Génération HTML
        output = dashboard.generate_html()
        print(f"[JARVIS] Voice Analytics Dashboard generated: {output}")

        # Afficher un résumé
        report = dashboard.generate_report()
        kpis = report["kpis"]
        print(f"  Total commands (24h): {kpis['total_commands']}")
        print(f"  Success rate: {kpis['success_rate']}%")
        print(f"  Avg latency: {kpis['avg_latency_ms']}ms")
        print(f"  All-time total: {kpis['total_all_time']}")
        print(f"  Active voice commands: {kpis['active_voice_commands']}")

        # Tendances
        trends = dashboard.get_trends()
        print(f"  Volume trend (7d): {trends['volume_trend_pct']:+.1f}%")

        # Analyses d'échecs
        failures = dashboard.get_failure_analysis()
        if failures:
            print(f"  Failure patterns found: {len(failures)}")
            for f in failures[:3]:
                print(f"    - {f['pattern']}: {f['count']} occurrences")
