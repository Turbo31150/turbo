"""JARVIS Voice Prediction Engine — Prédiction de commandes vocales par chaînes de Markov.

Analyse l'historique des commandes (jarvis.db + action_history.json) pour
prédire la prochaine commande probable via :
- Chaînes de Markov (transitions commande A → commande B)
- Patterns temporels (heure / jour de la semaine)
- Patterns séquentiels (enchaînements fréquents)

Usage:
    from src.voice_prediction_engine import VoicePredictionEngine
    engine = VoicePredictionEngine()
    predictions = engine.predict_next("git status")
    routines = engine.get_routine_suggestions(hour=9, weekday=0)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.voice_prediction_engine")

# Chemins par défaut
_BASE_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = _BASE_DIR / "data"
_MODEL_PATH = _DATA_DIR / "prediction_model.json"
_HISTORY_JSON_PATH = _DATA_DIR / "action_history.json"
_JARVIS_DB_PATH = _BASE_DIR / "jarvis.db"

# Nombre max de suggestions retournées
_DEFAULT_TOP_K = 5

# Poids pour la combinaison des scores
_WEIGHT_MARKOV = 0.50
_WEIGHT_TEMPORAL = 0.30
_WEIGHT_SEQUENTIAL = 0.20

# Lissage de Laplace pour éviter les probabilités nulles
_LAPLACE_ALPHA = 0.01

# ── Transitions prédéfinies (amorçage du modèle) ──────────────────────────
# Format : (commande_source, commande_destination, probabilité)
_DEFAULT_TRANSITIONS: list[tuple[str, str, float]] = [
    # Workflow Git
    ("ouvre terminal", "git status", 0.30),
    ("git status", "git commit", 0.40),
    ("git commit", "git push", 0.50),
    ("git push", "git status", 0.20),
    ("git pull", "git status", 0.35),
    ("git status", "git diff", 0.25),
    ("git diff", "git commit", 0.35),
    ("git status", "git pull", 0.15),
    ("git commit", "git log", 0.15),
    ("git log", "git push", 0.25),
    # Navigation / Applications
    ("ouvre firefox", "ouvre spotify", 0.20),
    ("ouvre firefox", "ouvre terminal", 0.15),
    ("ouvre spotify", "volume haut", 0.25),
    ("ouvre terminal", "ouvre firefox", 0.10),
    ("ouvre vscode", "ouvre terminal", 0.30),
    ("ouvre vscode", "git status", 0.25),
    ("ouvre terminal", "lance python", 0.20),
    # Monitoring cluster / GPU
    ("vérifie le cluster", "gpu status", 0.30),
    ("gpu status", "température gpu", 0.25),
    ("température gpu", "vérifie le cluster", 0.15),
    ("vérifie le cluster", "état du réseau", 0.20),
    ("gpu status", "vérifie le cluster", 0.20),
    ("état du réseau", "vérifie le cluster", 0.15),
    # Routines matin
    ("bonjour jarvis", "rapport système", 0.35),
    ("rapport système", "vérifie le cluster", 0.30),
    ("rapport système", "check mails", 0.20),
    ("check mails", "agenda du jour", 0.30),
    ("agenda du jour", "météo", 0.25),
    # Routines soir
    ("bonne nuit", "éteins les lumières", 0.40),
    ("bonne nuit", "mode veille", 0.30),
    ("éteins les lumières", "mode veille", 0.35),
    # Trading
    ("trading status", "trading scan", 0.30),
    ("trading scan", "trading execute", 0.20),
    ("trading scan", "trading status", 0.25),
    ("trading status", "rapport trading", 0.20),
    # Mode travail
    ("mode dev", "ouvre vscode", 0.40),
    ("mode dev", "ouvre terminal", 0.30),
    ("mode weekend", "ouvre spotify", 0.30),
    ("mode weekend", "ouvre firefox", 0.25),
    # Commandes vocales courantes
    ("volume haut", "volume bas", 0.15),
    ("volume bas", "volume haut", 0.15),
    ("lance musique", "volume haut", 0.25),
    ("lance musique", "pause musique", 0.20),
    ("pause musique", "lance musique", 0.30),
    # Système
    ("diagnostic système", "rapport système", 0.30),
    ("rapport système", "diagnostic système", 0.15),
    ("redémarre service", "vérifie le cluster", 0.35),
    ("santé cluster", "gpu status", 0.25),
    ("santé cluster", "rapport système", 0.20),
]

# Patterns temporels prédéfinis : (heure_début, heure_fin, commandes typiques)
_DEFAULT_TEMPORAL_PATTERNS: list[tuple[int, int, list[tuple[str, float]]]] = [
    # Matin tôt (6h-9h)
    (6, 9, [
        ("bonjour jarvis", 0.40),
        ("rapport système", 0.35),
        ("check mails", 0.30),
        ("météo", 0.25),
        ("agenda du jour", 0.20),
    ]),
    # Matinée (9h-12h)
    (9, 12, [
        ("mode dev", 0.30),
        ("ouvre vscode", 0.25),
        ("git status", 0.20),
        ("trading scan", 0.20),
        ("vérifie le cluster", 0.15),
    ]),
    # Après-midi (12h-18h)
    (12, 18, [
        ("trading status", 0.25),
        ("git status", 0.20),
        ("gpu status", 0.15),
        ("diagnostic système", 0.15),
        ("ouvre terminal", 0.10),
    ]),
    # Soirée (18h-22h)
    (18, 22, [
        ("mode weekend", 0.20),
        ("lance musique", 0.25),
        ("ouvre spotify", 0.20),
        ("rapport trading", 0.15),
        ("ouvre firefox", 0.15),
    ]),
    # Nuit (22h-6h)
    (22, 6, [
        ("bonne nuit", 0.40),
        ("éteins les lumières", 0.30),
        ("mode veille", 0.25),
        ("rapport système", 0.10),
        ("trading status", 0.10),
    ]),
]

# Patterns par jour de la semaine : (jour, commandes typiques)
# 0=lundi, 6=dimanche
_DEFAULT_WEEKDAY_PATTERNS: dict[int, list[tuple[str, float]]] = {
    0: [("mode dev", 0.35), ("rapport système", 0.30)],        # Lundi
    1: [("mode dev", 0.30), ("trading scan", 0.25)],           # Mardi
    2: [("mode dev", 0.30), ("vérifie le cluster", 0.20)],     # Mercredi
    3: [("trading scan", 0.25), ("mode dev", 0.25)],           # Jeudi
    4: [("mode weekend", 0.30), ("rapport trading", 0.25)],    # Vendredi
    5: [("lance musique", 0.30), ("ouvre firefox", 0.25)],     # Samedi
    6: [("lance musique", 0.25), ("rapport système", 0.20)],   # Dimanche
}


class VoicePredictionEngine:
    """Moteur de prédiction vocale basé sur chaînes de Markov et patterns temporels.

    Combine trois sources de signal :
    1. Chaînes de Markov — probabilité de transition entre commandes
    2. Patterns temporels — commandes typiques par heure et jour
    3. Patterns séquentiels — enchaînements fréquents (n-grams)
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        history_json_path: str | Path | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        self._model_path = Path(model_path) if model_path else _MODEL_PATH
        self._history_json_path = Path(history_json_path) if history_json_path else _HISTORY_JSON_PATH
        self._db_path = Path(db_path) if db_path else _JARVIS_DB_PATH

        # Matrice de transition Markov : {cmd_source: {cmd_dest: count}}
        self._transitions: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

        # Compteurs temporels : {hour: Counter(cmd → count)}
        self._hourly_patterns: dict[int, Counter[str]] = defaultdict(Counter)

        # Compteurs par jour : {weekday: Counter(cmd → count)}
        self._weekday_patterns: dict[int, Counter[str]] = defaultdict(Counter)

        # Séquences récentes (pour patterns séquentiels)
        self._recent_commands: list[tuple[str, float]] = []  # (cmd, timestamp)
        self._max_recent = 100

        # Statistiques
        self._total_transitions: int = 0
        self._total_commands: int = 0
        self._last_command: str | None = None
        self._created_at: float = time.time()

        # Charger le modèle existant ou initialiser
        self._load_model()

    # ── Chargement / Sauvegarde ────────────────────────────────────────────

    def _load_model(self) -> None:
        """Charge le modèle depuis le fichier JSON, ou initialise avec les défauts."""
        loaded = False

        if self._model_path.exists():
            try:
                data = json.loads(self._model_path.read_text(encoding="utf-8"))
                self._deserialize(data)
                loaded = True
                logger.info("Modèle chargé depuis %s (%d transitions)", self._model_path, self._total_transitions)
            except Exception as exc:
                logger.warning("Échec du chargement du modèle: %s", exc)

        if not loaded:
            self._seed_defaults()
            logger.info("Modèle initialisé avec %d transitions par défaut", self._total_transitions)

        # Importer l'historique existant pour enrichir le modèle
        self._import_history()

    def _seed_defaults(self) -> None:
        """Pré-remplit le modèle avec les transitions de bon sens."""
        for from_cmd, to_cmd, prob in _DEFAULT_TRANSITIONS:
            # Convertir la probabilité en pseudo-count (10 = base solide)
            count = prob * 10.0
            self._transitions[from_cmd][to_cmd] += count
            self._total_transitions += 1

        for start_h, end_h, commands in _DEFAULT_TEMPORAL_PATTERNS:
            hours = list(range(start_h, end_h)) if start_h < end_h else list(range(start_h, 24)) + list(range(0, end_h))
            for hour in hours:
                for cmd, weight in commands:
                    self._hourly_patterns[hour][cmd] += weight * 5.0

        for weekday, commands in _DEFAULT_WEEKDAY_PATTERNS.items():
            for cmd, weight in commands:
                self._weekday_patterns[weekday][cmd] += weight * 5.0

    def _save_model(self) -> None:
        """Persiste le modèle dans le fichier JSON."""
        try:
            self._model_path.parent.mkdir(parents=True, exist_ok=True)
            data = self._serialize()
            self._model_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.debug("Modèle sauvegardé dans %s", self._model_path)
        except Exception as exc:
            logger.warning("Échec de la sauvegarde du modèle: %s", exc)

    def _serialize(self) -> dict[str, Any]:
        """Sérialise l'état complet du moteur."""
        return {
            "version": 1,
            "created_at": self._created_at,
            "updated_at": time.time(),
            "total_transitions": self._total_transitions,
            "total_commands": self._total_commands,
            "last_command": self._last_command,
            "transitions": {
                src: dict(dests)
                for src, dests in self._transitions.items()
            },
            "hourly_patterns": {
                str(h): dict(counter)
                for h, counter in self._hourly_patterns.items()
            },
            "weekday_patterns": {
                str(wd): dict(counter)
                for wd, counter in self._weekday_patterns.items()
            },
            "recent_commands": self._recent_commands[-50:],  # Garder les 50 dernières
        }

    def _deserialize(self, data: dict[str, Any]) -> None:
        """Restaure l'état depuis les données sérialisées."""
        self._created_at = data.get("created_at", time.time())
        self._total_transitions = data.get("total_transitions", 0)
        self._total_commands = data.get("total_commands", 0)
        self._last_command = data.get("last_command")

        for src, dests in data.get("transitions", {}).items():
            for dest, count in dests.items():
                self._transitions[src][dest] = float(count)

        for h_str, counts in data.get("hourly_patterns", {}).items():
            hour = int(h_str)
            for cmd, count in counts.items():
                self._hourly_patterns[hour][cmd] = float(count)

        for wd_str, counts in data.get("weekday_patterns", {}).items():
            weekday = int(wd_str)
            for cmd, count in counts.items():
                self._weekday_patterns[weekday][cmd] = float(count)

        self._recent_commands = [
            (cmd, ts) for cmd, ts in data.get("recent_commands", [])
        ]

    # ── Import de l'historique ─────────────────────────────────────────────

    def _import_history(self) -> None:
        """Importe l'historique depuis jarvis.db et action_history.json."""
        commands_imported = 0
        commands_imported += self._import_from_json()
        commands_imported += self._import_from_db()

        if commands_imported > 0:
            logger.info("Historique importé: %d commandes", commands_imported)
            self._save_model()

    def _import_from_json(self) -> int:
        """Importe les commandes depuis data/action_history.json."""
        if not self._history_json_path.exists():
            return 0

        try:
            raw = json.loads(self._history_json_path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                return 0

            # Trier par timestamp pour reconstruire les séquences
            entries = sorted(raw, key=lambda e: e.get("timestamp", 0))
            prev_action: str | None = None
            count = 0

            for entry in entries:
                action = entry.get("action", "")
                ts = entry.get("timestamp", 0)
                if not action:
                    continue

                # Enregistrer le pattern temporel
                dt = datetime.fromtimestamp(ts) if ts else None
                if dt:
                    self._hourly_patterns[dt.hour][action] += 1.0
                    self._weekday_patterns[dt.weekday()][action] += 1.0

                # Enregistrer la transition Markov
                if prev_action and prev_action != action:
                    self._transitions[prev_action][action] += 1.0
                    self._total_transitions += 1

                prev_action = action
                count += 1

            self._total_commands += count
            return count

        except Exception as exc:
            logger.debug("Import JSON échoué: %s", exc)
            return 0

    def _import_from_db(self) -> int:
        """Importe les commandes depuis la table action_history de jarvis.db."""
        if not self._db_path.exists():
            return 0

        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row

            # Vérifier si la table existe
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='action_history'"
            ).fetchone()

            if not tables:
                conn.close()
                return 0

            # Récupérer les colonnes disponibles
            cursor = conn.execute("PRAGMA table_info(action_history)")
            columns = {row["name"] for row in cursor.fetchall()}

            # Construire la requête selon les colonnes disponibles
            action_col = "action" if "action" in columns else "command"
            ts_col = "timestamp" if "timestamp" in columns else "created_at"
            has_action = action_col in columns
            has_ts = ts_col in columns

            if not has_action:
                conn.close()
                return 0

            query = f"SELECT {action_col} as action"
            if has_ts:
                query += f", {ts_col} as ts"
            query += f" FROM action_history ORDER BY {ts_col}" if has_ts else " FROM action_history"

            rows = conn.execute(query).fetchall()
            conn.close()

            prev_action: str | None = None
            count = 0

            for row in rows:
                action = row["action"]
                if not action:
                    continue

                # Pattern temporel si timestamp disponible
                if has_ts:
                    ts_val = row["ts"]
                    if isinstance(ts_val, (int, float)) and ts_val > 0:
                        dt = datetime.fromtimestamp(ts_val)
                        self._hourly_patterns[dt.hour][action] += 1.0
                        self._weekday_patterns[dt.weekday()][action] += 1.0

                # Transition Markov
                if prev_action and prev_action != action:
                    self._transitions[prev_action][action] += 1.0
                    self._total_transitions += 1

                prev_action = action
                count += 1

            self._total_commands += count
            return count

        except Exception as exc:
            logger.debug("Import DB échoué: %s", exc)
            return 0

    # ── Enregistrement en temps réel ───────────────────────────────────────

    def record_transition(self, from_cmd: str, to_cmd: str) -> None:
        """Enregistre une transition entre deux commandes et met à jour le modèle.

        Args:
            from_cmd: Commande source.
            to_cmd: Commande destination.
        """
        from_cmd = from_cmd.strip().lower()
        to_cmd = to_cmd.strip().lower()

        if not from_cmd or not to_cmd:
            return

        self._transitions[from_cmd][to_cmd] += 1.0
        self._total_transitions += 1
        self._total_commands += 1
        self._last_command = to_cmd

        # Mise à jour du pattern temporel
        now = datetime.now()
        self._hourly_patterns[now.hour][to_cmd] += 1.0
        self._weekday_patterns[now.weekday()][to_cmd] += 1.0

        # Ajouter aux commandes récentes
        self._recent_commands.append((to_cmd, time.time()))
        if len(self._recent_commands) > self._max_recent:
            self._recent_commands = self._recent_commands[-self._max_recent:]

        # Persister
        self._save_model()

    def record_command(self, command: str) -> None:
        """Enregistre une commande unique et la relie à la précédente si disponible.

        Args:
            command: Commande exécutée.
        """
        command = command.strip().lower()
        if not command:
            return

        if self._last_command:
            self.record_transition(self._last_command, command)
        else:
            # Première commande de la session, enregistrer pattern temporel seulement
            now = datetime.now()
            self._hourly_patterns[now.hour][command] += 1.0
            self._weekday_patterns[now.weekday()][command] += 1.0
            self._last_command = command
            self._total_commands += 1

            self._recent_commands.append((command, time.time()))
            if len(self._recent_commands) > self._max_recent:
                self._recent_commands = self._recent_commands[-self._max_recent:]

            self._save_model()

    # ── Prédiction ─────────────────────────────────────────────────────────

    def predict_next(
        self,
        current_command: str,
        time: datetime | None = None,
        top_k: int = _DEFAULT_TOP_K,
    ) -> list[dict[str, Any]]:
        """Prédit les commandes les plus probables après current_command.

        Combine les scores Markov, temporels et séquentiels avec pondération.

        Args:
            current_command: La commande courante / dernière exécutée.
            time: Le moment actuel (datetime.now() si None).
            top_k: Nombre max de suggestions à retourner.

        Returns:
            Liste de dicts triés par score décroissant :
            [{"command": str, "confidence": float, "sources": dict}, ...]
        """
        current_command = current_command.strip().lower()
        now = time or datetime.now()

        # 1. Score Markov
        markov_scores = self._score_markov(current_command)

        # 2. Score temporel
        temporal_scores = self._score_temporal(now.hour, now.weekday())

        # 3. Score séquentiel (n-grams récents)
        sequential_scores = self._score_sequential(current_command)

        # Fusionner tous les candidats
        all_commands: set[str] = set()
        all_commands.update(markov_scores.keys())
        all_commands.update(temporal_scores.keys())
        all_commands.update(sequential_scores.keys())

        # Exclure la commande courante des suggestions
        all_commands.discard(current_command)

        if not all_commands:
            return []

        # Calcul du score combiné
        results: list[dict[str, Any]] = []
        for cmd in all_commands:
            m_score = markov_scores.get(cmd, 0.0)
            t_score = temporal_scores.get(cmd, 0.0)
            s_score = sequential_scores.get(cmd, 0.0)

            combined = (
                _WEIGHT_MARKOV * m_score
                + _WEIGHT_TEMPORAL * t_score
                + _WEIGHT_SEQUENTIAL * s_score
            )

            if combined < 0.01:
                continue

            results.append({
                "command": cmd,
                "confidence": round(min(combined, 1.0), 4),
                "sources": {
                    "markov": round(m_score, 4),
                    "temporal": round(t_score, 4),
                    "sequential": round(s_score, 4),
                },
            })

        # Trier par confiance décroissante
        results.sort(key=lambda r: r["confidence"], reverse=True)
        return results[:top_k]

    def _score_markov(self, current_command: str) -> dict[str, float]:
        """Calcule les probabilités de transition depuis current_command.

        Utilise le lissage de Laplace pour éviter les probabilités nulles.
        """
        scores: dict[str, float] = {}

        if current_command not in self._transitions:
            return scores

        dest_counts = self._transitions[current_command]
        if not dest_counts:
            return scores

        # Total des transitions depuis cette commande + lissage
        total = sum(dest_counts.values())
        vocab_size = len(dest_counts)

        for dest, count in dest_counts.items():
            # Probabilité lissée (Laplace)
            prob = (count + _LAPLACE_ALPHA) / (total + _LAPLACE_ALPHA * vocab_size)
            scores[dest] = prob

        # Normaliser au max pour que le meilleur score soit ~1.0
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                scores = {cmd: s / max_score for cmd, s in scores.items()}

        return scores

    def _score_temporal(self, hour: int, weekday: int) -> dict[str, float]:
        """Calcule les scores de commandes typiques pour l'heure et le jour donnés."""
        scores: dict[str, float] = defaultdict(float)

        # Score horaire (poids 0.6)
        hourly = self._hourly_patterns.get(hour, Counter())
        if hourly:
            total_h = sum(hourly.values())
            for cmd, count in hourly.items():
                scores[cmd] += 0.6 * (count / total_h)

        # Score heures adjacentes (poids 0.15 chacune, lissage)
        for adj_hour in [(hour - 1) % 24, (hour + 1) % 24]:
            adj = self._hourly_patterns.get(adj_hour, Counter())
            if adj:
                total_a = sum(adj.values())
                for cmd, count in adj.items():
                    scores[cmd] += 0.15 * (count / total_a)

        # Score jour de la semaine (poids 0.10)
        daily = self._weekday_patterns.get(weekday, Counter())
        if daily:
            total_d = sum(daily.values())
            for cmd, count in daily.items():
                scores[cmd] += 0.10 * (count / total_d)

        # Normaliser
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                scores = {cmd: s / max_score for cmd, s in scores.items()}

        return dict(scores)

    def _score_sequential(self, current_command: str) -> dict[str, float]:
        """Analyse les commandes récentes pour détecter des patterns séquentiels.

        Regarde les N dernières commandes et identifie ce qui suit
        typiquement la commande courante dans les séquences observées.
        """
        scores: dict[str, float] = defaultdict(float)

        if len(self._recent_commands) < 2:
            return dict(scores)

        # Chercher les occurrences de current_command dans l'historique récent
        # et compter ce qui suit
        for i in range(len(self._recent_commands) - 1):
            cmd, _ = self._recent_commands[i]
            if cmd == current_command:
                next_cmd, _ = self._recent_commands[i + 1]
                if next_cmd != current_command:
                    scores[next_cmd] += 1.0

        # Normaliser
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                scores = {cmd: s / max_score for cmd, s in scores.items()}

        return dict(scores)

    # ── Suggestions de routine ─────────────────────────────────────────────

    def get_routine_suggestions(
        self,
        hour: int,
        weekday: int,
        top_k: int = _DEFAULT_TOP_K,
    ) -> list[dict[str, Any]]:
        """Retourne les suggestions basées uniquement sur l'heure et le jour.

        Utile pour les suggestions proactives (ex: après wake word, sans commande précédente).

        Args:
            hour: Heure du jour (0-23).
            weekday: Jour de la semaine (0=lundi, 6=dimanche).
            top_k: Nombre max de suggestions.

        Returns:
            Liste de dicts : [{"command": str, "confidence": float, "reason": str}, ...]
        """
        temporal_scores = self._score_temporal(hour, weekday)

        if not temporal_scores:
            return []

        day_names = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        day_name = day_names[weekday] if 0 <= weekday <= 6 else "inconnu"

        results: list[dict[str, Any]] = []
        for cmd, score in sorted(temporal_scores.items(), key=lambda x: -x[1]):
            if score < 0.05:
                continue
            results.append({
                "command": cmd,
                "confidence": round(min(score, 1.0), 4),
                "reason": f"Routine typique à {hour}h le {day_name}",
            })

        return results[:top_k]

    # ── Statistiques ───────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Retourne les statistiques complètes du moteur de prédiction.

        Returns:
            Dict avec métriques sur les transitions, patterns et historique.
        """
        # Nombre de commandes uniques dans le modèle
        all_commands: set[str] = set()
        for src in self._transitions:
            all_commands.add(src)
            all_commands.update(self._transitions[src].keys())

        # Top transitions
        top_transitions: list[dict[str, Any]] = []
        for src, dests in self._transitions.items():
            for dest, count in sorted(dests.items(), key=lambda x: -x[1])[:3]:
                top_transitions.append({
                    "from": src,
                    "to": dest,
                    "count": round(count, 1),
                })
        top_transitions.sort(key=lambda t: -t["count"])

        return {
            "engine": "VoicePredictionEngine",
            "version": 1,
            "total_transitions": self._total_transitions,
            "total_commands": self._total_commands,
            "unique_commands": len(all_commands),
            "transition_sources": len(self._transitions),
            "hourly_patterns_hours": len(self._hourly_patterns),
            "weekday_patterns_days": len(self._weekday_patterns),
            "recent_commands_count": len(self._recent_commands),
            "last_command": self._last_command,
            "model_path": str(self._model_path),
            "model_exists": self._model_path.exists(),
            "weights": {
                "markov": _WEIGHT_MARKOV,
                "temporal": _WEIGHT_TEMPORAL,
                "sequential": _WEIGHT_SEQUENTIAL,
            },
            "top_transitions": top_transitions[:15],
            "created_at": self._created_at,
        }

    # ── Utilitaires ────────────────────────────────────────────────────────

    def get_transition_matrix(self, command: str) -> dict[str, float]:
        """Retourne la matrice de transition brute pour une commande donnée.

        Args:
            command: Commande source.

        Returns:
            Dict {commande_destination: probabilité normalisée}.
        """
        command = command.strip().lower()
        if command not in self._transitions:
            return {}

        dest_counts = self._transitions[command]
        total = sum(dest_counts.values())
        if total == 0:
            return {}

        return {
            dest: round(count / total, 4)
            for dest, count in sorted(dest_counts.items(), key=lambda x: -x[1])
        }

    def reset_session(self) -> None:
        """Réinitialise la dernière commande (début de nouvelle session vocale)."""
        self._last_command = None

    def force_save(self) -> None:
        """Force la sauvegarde du modèle sur disque."""
        self._save_model()


# ── Singleton global ───────────────────────────────────────────────────────
voice_prediction_engine = VoicePredictionEngine()
