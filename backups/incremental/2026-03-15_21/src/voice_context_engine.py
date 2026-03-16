"""voice_context_engine.py — Moteur de contexte vocal adaptatif pour JARVIS.

Enrichit les commandes vocales avec du contexte systeme, temporel,
applicatif et historique pour proposer des suggestions intelligentes
et adapter le comportement du routeur vocal.

Usage:
    from src.voice_context_engine import voice_context_engine
    ctx = voice_context_engine.get_context()
    suggestions = voice_context_engine.get_suggestions(max=5)
    enriched = voice_context_engine.enrich_command("ouvre firefox")
"""
from __future__ import annotations

import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.voice_context_engine")

# Repertoire racine du projet
_BASE_DIR = Path(__file__).resolve().parent.parent

# Seuils d'alerte systeme
_GPU_TEMP_THRESHOLD: int = 75        # degres Celsius
_RAM_USAGE_THRESHOLD: float = 85.0   # pourcentage
_DISK_USAGE_THRESHOLD: float = 90.0  # pourcentage

# Intervalle minimum entre deux suggestions proactives (secondes)
_SUGGESTION_COOLDOWN: float = 120.0

# Poids pour la combinaison des scores de suggestion
_WEIGHT_SYSTEM: float = 0.35
_WEIGHT_TEMPORAL: float = 0.25
_WEIGHT_APP: float = 0.20
_WEIGHT_HISTORY: float = 0.20


def _run_cmd(cmd: list[str], timeout: float = 3.0) -> str:
    """Execute une commande shell avec timeout. Retourne stdout ou chaine vide."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except Exception:
        return ""


class VoiceContextEngine:
    """Moteur de contexte vocal adaptatif.

    Combine quatre sources de contexte :
    1. Systeme — CPU, RAM, GPU, disque, services
    2. Temporel — heure, jour, routines
    3. Applicatif — fenetre active, apps ouvertes
    4. Historique — prediction engine, profil vocal
    """

    def __init__(self) -> None:
        # Cache du dernier contexte pour eviter les appels systeme trop frequents
        self._context_cache: dict[str, Any] = {}
        self._cache_ttl: float = 10.0  # secondes
        self._cache_timestamp: float = 0.0

        # Timestamp de la derniere suggestion proactive
        self._last_suggestion_time: float = 0.0

        # Compteur de suggestions par session
        self._suggestion_count: int = 0

        logger.info("VoiceContextEngine initialise")

    # ── Contexte systeme ──────────────────────────────────────────────────

    def _get_system_context(self) -> dict[str, Any]:
        """Collecte les metriques systeme (GPU, RAM, disque, services)."""
        ctx: dict[str, Any] = {
            "gpu_temps": [],
            "gpu_alert": False,
            "ram_percent": 0.0,
            "ram_alert": False,
            "disk_percent": 0.0,
            "disk_alert": False,
            "services_down": [],
            "alerts": [],
        }

        # Temperatures GPU via nvidia-smi
        gpu_output = _run_cmd([
            "nvidia-smi",
            "--query-gpu=temperature.gpu",
            "--format=csv,noheader,nounits",
        ])
        if gpu_output:
            temps: list[int] = []
            for line in gpu_output.splitlines():
                line = line.strip()
                if line.isdigit():
                    temps.append(int(line))
            ctx["gpu_temps"] = temps
            if temps and max(temps) > _GPU_TEMP_THRESHOLD:
                ctx["gpu_alert"] = True
                ctx["alerts"].append({
                    "type": "gpu_temp",
                    "message": f"GPU surchauffe : {max(temps)}°C (seuil: {_GPU_TEMP_THRESHOLD}°C)",
                    "severity": "warning",
                    "suggestion": "optimise les gpu",
                })

        # Utilisation RAM via /proc/meminfo (plus rapide que psutil)
        try:
            meminfo_path = Path("/proc/meminfo")
            if meminfo_path.exists():
                meminfo = meminfo_path.read_text()
                mem_total = 0
                mem_available = 0
                for line in meminfo.splitlines():
                    if line.startswith("MemTotal:"):
                        mem_total = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        mem_available = int(line.split()[1])
                if mem_total > 0:
                    ram_percent = ((mem_total - mem_available) / mem_total) * 100.0
                    ctx["ram_percent"] = round(ram_percent, 1)
                    if ram_percent > _RAM_USAGE_THRESHOLD:
                        ctx["ram_alert"] = True
                        ctx["alerts"].append({
                            "type": "ram_usage",
                            "message": f"RAM elevee : {ram_percent:.1f}% (seuil: {_RAM_USAGE_THRESHOLD}%)",
                            "severity": "warning",
                            "suggestion": "libere de la memoire",
                        })
        except Exception:
            pass

        # Utilisation disque (partition racine)
        disk_output = _run_cmd(["df", "--output=pcent", "/"])
        if disk_output:
            lines = disk_output.splitlines()
            if len(lines) >= 2:
                pct_str = lines[1].strip().rstrip("%")
                try:
                    disk_pct = float(pct_str)
                    ctx["disk_percent"] = disk_pct
                    if disk_pct > _DISK_USAGE_THRESHOLD:
                        ctx["disk_alert"] = True
                        ctx["alerts"].append({
                            "type": "disk_usage",
                            "message": f"Disque presque plein : {disk_pct:.0f}% (seuil: {_DISK_USAGE_THRESHOLD}%)",
                            "severity": "critical",
                            "suggestion": "nettoyage profond",
                        })
                except ValueError:
                    pass

        # Services critiques (systemd)
        critical_services = ["ollama", "n8n", "docker"]
        for svc in critical_services:
            status_output = _run_cmd(["systemctl", "is-active", svc], timeout=2.0)
            if status_output and status_output != "active":
                ctx["services_down"].append(svc)

        if ctx["services_down"]:
            ctx["alerts"].append({
                "type": "service_down",
                "message": f"Services inactifs : {', '.join(ctx['services_down'])}",
                "severity": "warning",
                "suggestion": "redemarre les services",
            })

        return ctx

    # ── Contexte temporel ─────────────────────────────────────────────────

    def _get_temporal_context(self) -> dict[str, Any]:
        """Determine le contexte temporel (periode, jour, suggestions)."""
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()  # 0=lundi, 6=dimanche

        # Determiner la periode de la journee
        if 6 <= hour < 9:
            period = "matin"
            period_suggestions = [
                {"command": "bonjour jarvis", "reason": "Routine du matin", "priority": 0.9},
                {"command": "rapport systeme", "reason": "Etat du systeme au reveil", "priority": 0.8},
                {"command": "meteo", "reason": "Meteo du jour", "priority": 0.6},
                {"command": "agenda du jour", "reason": "Planning de la journee", "priority": 0.5},
            ]
        elif 9 <= hour < 12:
            period = "matinee"
            period_suggestions = [
                {"command": "mode dev", "reason": "Debut de session de travail", "priority": 0.7},
                {"command": "verifie le cluster", "reason": "Sante du cluster", "priority": 0.5},
            ]
        elif 12 <= hour < 13:
            period = "midi"
            period_suggestions = [
                {"command": "pause", "reason": "Heure du dejeuner", "priority": 0.7},
                {"command": "lance musique", "reason": "Musique pendant la pause", "priority": 0.5},
            ]
        elif 13 <= hour < 18:
            period = "apres-midi"
            period_suggestions = [
                {"command": "trading status", "reason": "Suivi des marches", "priority": 0.5},
                {"command": "gpu status", "reason": "Monitoring GPU", "priority": 0.4},
            ]
        elif 18 <= hour < 22:
            period = "soir"
            period_suggestions = [
                {"command": "backup systeme", "reason": "Backup quotidien", "priority": 0.8},
                {"command": "rapport journee", "reason": "Resume de la journee", "priority": 0.7},
                {"command": "rapport trading", "reason": "Bilan trading du jour", "priority": 0.5},
            ]
        else:
            period = "nuit"
            period_suggestions = [
                {"command": "bonne nuit", "reason": "Fin de journee", "priority": 0.9},
                {"command": "mode veille", "reason": "Economie d'energie", "priority": 0.7},
            ]

        # Weekend : ajouter des suggestions loisirs
        is_weekend = weekday >= 5
        if is_weekend and period not in ("nuit",):
            period_suggestions.append({
                "command": "mode weekend",
                "reason": "C'est le weekend !",
                "priority": 0.6,
            })

        day_names = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

        return {
            "hour": hour,
            "minute": now.minute,
            "weekday": weekday,
            "day_name": day_names[weekday],
            "period": period,
            "is_weekend": is_weekend,
            "suggestions": period_suggestions,
        }

    # ── Contexte applicatif ───────────────────────────────────────────────

    def _get_app_context(self) -> dict[str, Any]:
        """Detecte les applications ouvertes via wmctrl -l et la fenetre active."""
        ctx: dict[str, Any] = {
            "active_window": "",
            "open_apps": [],
            "dominant_category": "general",
            "suggestions": [],
        }

        # Fenetre active via xdotool
        active_window = _run_cmd(["xdotool", "getactivewindow", "getwindowname"])
        ctx["active_window"] = active_window

        # Liste des fenetres ouvertes via wmctrl
        wmctrl_output = _run_cmd(["wmctrl", "-l"])
        open_windows: list[str] = []
        if wmctrl_output:
            for line in wmctrl_output.splitlines():
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    open_windows.append(parts[3].lower())

        ctx["open_apps"] = open_windows

        # Detecter la categorie dominante
        dev_apps = {"code", "vscode", "cursor", "sublime", "vim", "nvim", "pycharm", "intellij"}
        browser_apps = {"firefox", "chrome", "chromium", "brave", "opera", "vivaldi"}
        terminal_apps = {"terminal", "konsole", "alacritty", "kitty", "wezterm", "tmux", "wt"}
        media_apps = {"spotify", "vlc", "mpv", "rhythmbox", "audacity"}
        trading_apps = {"tradingview", "metatrader", "binance"}

        # Analyser la fenetre active en priorite, puis les fenetres ouvertes
        all_window_text = " ".join(open_windows) + " " + active_window.lower()

        # Compteur de categories detectees
        category_scores: dict[str, float] = {
            "dev": 0.0,
            "navigation": 0.0,
            "terminal": 0.0,
            "media": 0.0,
            "trading": 0.0,
        }

        for app in dev_apps:
            if app in all_window_text:
                category_scores["dev"] += 1.0
            if app in active_window.lower():
                category_scores["dev"] += 2.0  # Bonus fenetre active

        for app in browser_apps:
            if app in all_window_text:
                category_scores["navigation"] += 1.0
            if app in active_window.lower():
                category_scores["navigation"] += 2.0

        for app in terminal_apps:
            if app in all_window_text:
                category_scores["terminal"] += 1.0
            if app in active_window.lower():
                category_scores["terminal"] += 2.0

        for app in media_apps:
            if app in all_window_text:
                category_scores["media"] += 1.0
            if app in active_window.lower():
                category_scores["media"] += 2.0

        for app in trading_apps:
            if app in all_window_text:
                category_scores["trading"] += 1.0
            if app in active_window.lower():
                category_scores["trading"] += 2.0

        # Determiner la categorie dominante
        max_score = max(category_scores.values()) if category_scores else 0.0
        if max_score > 0:
            dominant = max(category_scores, key=category_scores.get)  # type: ignore[arg-type]
            ctx["dominant_category"] = dominant
        else:
            ctx["dominant_category"] = "general"

        # Suggestions basees sur le contexte applicatif
        category_suggestions: dict[str, list[dict[str, Any]]] = {
            "dev": [
                {"command": "git status", "reason": "VSCode/Cursor ouvert — workflow git", "priority": 0.7},
                {"command": "lance les tests", "reason": "Environnement dev actif", "priority": 0.5},
                {"command": "ouvre terminal", "reason": "Acces rapide au terminal", "priority": 0.4},
            ],
            "navigation": [
                {"command": "nouvel onglet", "reason": "Navigateur actif", "priority": 0.5},
                {"command": "recherche", "reason": "Navigation web en cours", "priority": 0.4},
                {"command": "ferme l'onglet", "reason": "Gestion des onglets", "priority": 0.3},
            ],
            "terminal": [
                {"command": "diagnostic systeme", "reason": "Terminal actif — commandes systeme", "priority": 0.6},
                {"command": "verifie le cluster", "reason": "Monitoring depuis le terminal", "priority": 0.5},
                {"command": "gpu status", "reason": "Etat des GPUs", "priority": 0.4},
            ],
            "media": [
                {"command": "volume haut", "reason": "Application media active", "priority": 0.5},
                {"command": "pause musique", "reason": "Controle du lecteur", "priority": 0.4},
                {"command": "chanson suivante", "reason": "Playlist en cours", "priority": 0.3},
            ],
            "trading": [
                {"command": "trading scan", "reason": "Plateforme trading ouverte", "priority": 0.7},
                {"command": "trading status", "reason": "Suivi des positions", "priority": 0.6},
                {"command": "rapport trading", "reason": "Analyse du portefeuille", "priority": 0.5},
            ],
        }

        dominant = ctx["dominant_category"]
        if dominant in category_suggestions:
            ctx["suggestions"] = category_suggestions[dominant]

        return ctx

    # ── Contexte historique ───────────────────────────────────────────────

    def _get_history_context(self) -> dict[str, Any]:
        """Recupere les suggestions du moteur de prediction et du profil actif."""
        ctx: dict[str, Any] = {
            "predictions": [],
            "active_profile": "normal",
            "profile_skills": [],
            "suggestions": [],
        }

        # Moteur de prediction vocale
        try:
            from src.voice_prediction_engine import voice_prediction_engine
            now = datetime.now()
            last_cmd = voice_prediction_engine._last_command

            if last_cmd:
                predictions = voice_prediction_engine.predict_next(last_cmd, time=now, top_k=5)
                ctx["predictions"] = predictions

                # Convertir les predictions en suggestions
                for pred in predictions:
                    ctx["suggestions"].append({
                        "command": pred["command"],
                        "reason": f"Suite probable apres '{last_cmd}'",
                        "priority": pred["confidence"],
                    })
            else:
                # Pas de derniere commande : suggestions de routine
                routines = voice_prediction_engine.get_routine_suggestions(
                    hour=now.hour,
                    weekday=now.weekday(),
                    top_k=3,
                )
                for r in routines:
                    ctx["suggestions"].append({
                        "command": r["command"],
                        "reason": r.get("reason", "Routine temporelle"),
                        "priority": r["confidence"],
                    })
        except Exception as exc:
            logger.debug("Prediction engine indisponible: %s", exc)

        # Profil vocal actif
        try:
            from src.voice_profiles import profile_manager
            ctx["active_profile"] = profile_manager.get_current_profile()
            ctx["profile_skills"] = profile_manager.get_priority_skills()
        except Exception as exc:
            logger.debug("Profile manager indisponible: %s", exc)

        return ctx

    # ── API publique ──────────────────────────────────────────────────────

    def get_context(self) -> dict[str, Any]:
        """Snapshot complet du contexte actuel.

        Retourne un dictionnaire avec les quatre axes de contexte :
        systeme, temporel, applicatif et historique.

        Returns:
            Dict avec les cles: system, temporal, app, history, timestamp.
        """
        now = time.time()

        # Utiliser le cache si encore valide
        if self._context_cache and (now - self._cache_timestamp) < self._cache_ttl:
            return self._context_cache

        context: dict[str, Any] = {
            "timestamp": now,
            "system": self._get_system_context(),
            "temporal": self._get_temporal_context(),
            "app": self._get_app_context(),
            "history": self._get_history_context(),
        }

        # Mettre en cache
        self._context_cache = context
        self._cache_timestamp = now

        return context

    def get_suggestions(self, max: int = 5) -> list[dict[str, Any]]:
        """Retourne les suggestions contextuelles triees par pertinence.

        Combine les suggestions de toutes les sources de contexte,
        ponderees par leur poids respectif et deduplicees.

        Args:
            max: Nombre maximum de suggestions a retourner.

        Returns:
            Liste de dicts tries par score decroissant :
            [{"command": str, "reason": str, "score": float, "source": str}, ...]
        """
        context = self.get_context()
        scored: dict[str, dict[str, Any]] = {}  # command -> meilleur entry

        # Alertes systeme (priorite haute)
        for alert in context["system"].get("alerts", []):
            cmd = alert.get("suggestion", "")
            if cmd:
                score = _WEIGHT_SYSTEM * (1.0 if alert["severity"] == "critical" else 0.8)
                if cmd not in scored or scored[cmd]["score"] < score:
                    scored[cmd] = {
                        "command": cmd,
                        "reason": alert["message"],
                        "score": round(score, 4),
                        "source": "system",
                    }

        # Suggestions temporelles
        for sug in context["temporal"].get("suggestions", []):
            cmd = sug["command"]
            score = _WEIGHT_TEMPORAL * sug.get("priority", 0.5)
            if cmd not in scored or scored[cmd]["score"] < score:
                scored[cmd] = {
                    "command": cmd,
                    "reason": sug["reason"],
                    "score": round(score, 4),
                    "source": "temporal",
                }

        # Suggestions applicatives
        for sug in context["app"].get("suggestions", []):
            cmd = sug["command"]
            score = _WEIGHT_APP * sug.get("priority", 0.5)
            if cmd not in scored or scored[cmd]["score"] < score:
                scored[cmd] = {
                    "command": cmd,
                    "reason": sug["reason"],
                    "score": round(score, 4),
                    "source": "app",
                }

        # Suggestions historiques / prediction
        for sug in context["history"].get("suggestions", []):
            cmd = sug["command"]
            score = _WEIGHT_HISTORY * sug.get("priority", 0.5)
            if cmd not in scored or scored[cmd]["score"] < score:
                scored[cmd] = {
                    "command": cmd,
                    "reason": sug["reason"],
                    "score": round(score, 4),
                    "source": "history",
                }

        # Trier par score decroissant et limiter
        results = sorted(scored.values(), key=lambda x: x["score"], reverse=True)

        # Mettre a jour le compteur
        self._suggestion_count += 1

        return results[:max]

    def enrich_command(self, text: str) -> str:
        """Enrichit une commande vocale avec du contexte.

        Ajoute des parametres implicites en fonction du contexte actuel.
        Par exemple : "backup" le soir → "backup systeme complet".

        Args:
            text: Commande vocale brute.

        Returns:
            Commande enrichie ou texte original si pas d'enrichissement pertinent.
        """
        if not text:
            return text

        normalized = text.lower().strip()
        context = self.get_context()

        # Enrichissement temporel
        period = context["temporal"].get("period", "")

        # "rapport" sans precision → adapter selon l'heure
        if normalized in ("rapport", "resume"):
            if period == "matin":
                return "rapport systeme"
            elif period == "soir":
                return "rapport journee"
            else:
                return "rapport systeme"

        # "backup" sans precision → backup complet le soir
        if normalized == "backup":
            if period == "soir":
                return "backup systeme complet"
            return "backup systeme"

        # "mode" sans precision → suggerer selon le contexte applicatif
        if normalized == "mode":
            dominant = context["app"].get("dominant_category", "general")
            mode_map = {
                "dev": "mode dev",
                "trading": "mode trading",
                "media": "mode weekend",
            }
            return mode_map.get(dominant, "mode normal")

        # "optimise" sans precision → cible selon les alertes
        if normalized in ("optimise", "optimize"):
            alerts = context["system"].get("alerts", [])
            for alert in alerts:
                if alert["type"] == "gpu_temp":
                    return "optimise les gpu"
                if alert["type"] == "ram_usage":
                    return "libere de la memoire"
                if alert["type"] == "disk_usage":
                    return "nettoyage profond"
            return "optimise le systeme"

        # "verifie" / "check" sans precision → selon le contexte
        if normalized in ("verifie", "check"):
            dominant = context["app"].get("dominant_category", "general")
            if dominant == "dev":
                return "git status"
            elif dominant == "trading":
                return "trading status"
            else:
                return "verifie le cluster"

        # "ouvre" sans precision → selon le contexte applicatif et temporel
        if normalized == "ouvre":
            dominant = context["app"].get("dominant_category", "general")
            if dominant == "dev":
                return "ouvre terminal"
            elif dominant == "navigation":
                return "ouvre firefox"
            else:
                return "ouvre terminal"

        # Enrichissement par profil actif : ajouter le contexte des skills prioritaires
        profile = context["history"].get("active_profile", "normal")
        if profile == "trading" and "scan" in normalized:
            if "complet" not in normalized:
                return normalized + " complet"

        return text

    def should_suggest(self) -> bool:
        """Determine s'il faut faire une suggestion proactive.

        Retourne True si :
        - Le cooldown est respecte (pas de spam)
        - Il y a des alertes systeme OU
        - On est dans une periode de routine OU
        - Le contexte applicatif a change significativement

        Returns:
            True si une suggestion proactive est pertinente.
        """
        now = time.time()

        # Respecter le cooldown
        if (now - self._last_suggestion_time) < _SUGGESTION_COOLDOWN:
            return False

        context = self.get_context()

        # Alertes systeme critiques → toujours suggerer
        system_alerts = context["system"].get("alerts", [])
        if any(a.get("severity") == "critical" for a in system_alerts):
            self._last_suggestion_time = now
            return True

        # Alertes systeme warning → suggerer
        if system_alerts:
            self._last_suggestion_time = now
            return True

        # Periodes de routine (matin, midi, soir, nuit) → suggerer
        period = context["temporal"].get("period", "")
        hour = context["temporal"].get("hour", 12)
        minute = context["temporal"].get("minute", 0)

        # Suggerer au debut de chaque periode (premiere demi-heure)
        routine_windows = {
            "matin": (6, 0),
            "midi": (12, 0),
            "soir": (18, 0),
            "nuit": (22, 0),
        }

        if period in routine_windows:
            start_hour, start_min = routine_windows[period]
            # Dans la premiere demi-heure de la periode
            if hour == start_hour and minute < 30:
                self._last_suggestion_time = now
                return True

        return False

    # ── Integration avec le routeur ───────────────────────────────────────

    def get_fallback_suggestions(self, text: str, max: int = 3) -> list[dict[str, Any]]:
        """Suggestions de fallback quand le routeur ne trouve pas de commande exacte.

        Appele par voice_router.py avant le fallback IA pour proposer
        des alternatives contextuelles pertinentes.

        Args:
            text: Commande vocale non reconnue.
            max: Nombre maximum de suggestions.

        Returns:
            Liste de suggestions contextuelles avec score de pertinence.
        """
        suggestions = self.get_suggestions(max=max + 2)

        # Filtrer : garder les suggestions les plus pertinentes par rapport au texte
        text_lower = text.lower()
        text_words = set(text_lower.split())

        # Bonus pour les suggestions qui partagent des mots avec la commande
        for sug in suggestions:
            cmd_words = set(sug["command"].lower().split())
            overlap = text_words & cmd_words
            if overlap:
                sug["score"] = round(sug["score"] + 0.15 * len(overlap), 4)
                sug["reason"] = f"Suggestion proche de '{text}' — {sug['reason']}"

        # Re-trier et limiter
        suggestions.sort(key=lambda x: x["score"], reverse=True)
        return suggestions[:max]


# ── Singleton global ──────────────────────────────────────────────────────
voice_context_engine = VoiceContextEngine()
