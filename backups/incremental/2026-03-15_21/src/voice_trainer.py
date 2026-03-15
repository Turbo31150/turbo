"""JARVIS Voice Trainer — Entraînement progressif à la reconnaissance vocale.

Collecte les transcriptions réussies et les corrections pour améliorer
la reconnaissance vocale au fil du temps. Analyse les patterns d'erreur,
génère automatiquement des corrections et exporte les données pour
fine-tuning Whisper/Vosk.

Usage:
    from src.voice_trainer import VoiceTrainer
    trainer = VoiceTrainer()
    trainer.record_success("ouvre firefox", "open_app:firefox")
    trainer.record_correction("fire fox", "firefox")
    report = trainer.generate_training_report()
    score = trainer.get_recognition_score()
"""

from __future__ import annotations

import csv
import io
import json
import logging
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

__all__ = [
    "TrainingEntry",
    "CorrectionEntry",
    "ErrorPattern",
    "VoiceTrainer",
]

logger = logging.getLogger("jarvis.voice_trainer")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRAINING_FILE = DATA_DIR / "voice_training_data.jsonl"


# ═══════════════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TrainingEntry:
    """Une entrée de succès dans le journal d'entraînement."""
    timestamp: float
    transcription: str
    resolved_command: str
    entry_type: str = "success"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.timestamp,
            "type": self.entry_type,
            "transcription": self.transcription,
            "resolved_command": self.resolved_command,
        }


@dataclass
class CorrectionEntry:
    """Une paire correction (mauvais → correct) dans le journal."""
    timestamp: float
    wrong: str
    correct: str
    entry_type: str = "correction"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.timestamp,
            "type": self.entry_type,
            "wrong": self.wrong,
            "correct": self.correct,
        }


@dataclass
class ErrorPattern:
    """Un pattern d'erreur détecté dans les transcriptions."""
    wrong_text: str
    correct_text: str
    count: int
    first_seen: float
    last_seen: float
    hours_distribution: dict[int, int] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════
# VOICE TRAINER — Classe principale
# ═══════════════════════════════════════════════════════════════════════════

class VoiceTrainer:
    """Entraîneur vocal — collecte, analyse et optimise la reconnaissance."""

    def __init__(self, data_file: Path | None = None) -> None:
        self._data_file: Path = data_file or TRAINING_FILE
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        # Cache mémoire des entrées chargées
        self._entries: list[dict[str, Any]] = []
        self._loaded = False
        logger.info("VoiceTrainer initialisé — fichier: %s", self._data_file)

    # ───────────────────────────────────────────────────────────────────
    # Persistance JSONL
    # ───────────────────────────────────────────────────────────────────

    def _append_entry(self, entry: dict[str, Any]) -> None:
        """Ajoute une entrée au fichier JSONL (append atomique)."""
        try:
            with open(self._data_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            # Invalider le cache pour forcer un rechargement
            self._loaded = False
        except OSError as exc:
            logger.error("Impossible d'écrire dans %s: %s", self._data_file, exc)

    def _load_entries(self, force: bool = False) -> list[dict[str, Any]]:
        """Charge toutes les entrées depuis le fichier JSONL (avec cache)."""
        if self._loaded and not force:
            return self._entries

        self._entries = []
        if not self._data_file.exists():
            self._loaded = True
            return self._entries

        try:
            with open(self._data_file, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self._entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.warning("Ligne %d invalide dans %s", line_num, self._data_file)
        except OSError as exc:
            logger.error("Impossible de lire %s: %s", self._data_file, exc)

        self._loaded = True
        return self._entries

    def _filter_by_days(self, entries: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
        """Filtre les entrées sur les N derniers jours."""
        cutoff = time.time() - (days * 86400)
        return [e for e in entries if e.get("ts", 0) >= cutoff]

    # ───────────────────────────────────────────────────────────────────
    # Collecte de données
    # ───────────────────────────────────────────────────────────────────

    def record_success(self, transcription: str, resolved_command: str) -> None:
        """Enregistre une commande vocale réussie (transcription → commande)."""
        entry = TrainingEntry(
            timestamp=time.time(),
            transcription=transcription.strip().lower(),
            resolved_command=resolved_command.strip(),
        )
        self._append_entry(entry.to_dict())
        logger.debug("Succès enregistré: '%s' → '%s'", transcription, resolved_command)

    def record_correction(self, wrong: str, correct: str) -> None:
        """Enregistre une correction (mauvaise transcription → texte correct)."""
        if wrong.strip().lower() == correct.strip().lower():
            return  # Pas de correction réelle
        entry = CorrectionEntry(
            timestamp=time.time(),
            wrong=wrong.strip().lower(),
            correct=correct.strip().lower(),
        )
        self._append_entry(entry.to_dict())
        logger.debug("Correction enregistrée: '%s' → '%s'", wrong, correct)

    # ───────────────────────────────────────────────────────────────────
    # Analyse des patterns d'erreur
    # ───────────────────────────────────────────────────────────────────

    def analyze_errors(self, days: int = 7) -> dict[str, Any]:
        """Analyse complète des erreurs de transcription sur N jours.

        Returns:
            Dict contenant:
            - top_misrecognized_words: mots les plus souvent mal transcrits
            - confusion_pairs: paires de confusion fréquentes
            - error_hours: heures avec le plus d'erreurs
            - reformulated_commands: commandes nécessitant le plus de reformulations
            - total_corrections: nombre total de corrections
            - total_successes: nombre total de succès
        """
        all_entries = self._load_entries()
        recent = self._filter_by_days(all_entries, days)

        corrections = [e for e in recent if e.get("type") == "correction"]
        successes = [e for e in recent if e.get("type") == "success"]

        # --- Top mots mal transcrits ---
        wrong_words: Counter[str] = Counter()
        for c in corrections:
            for word in c.get("wrong", "").split():
                wrong_words[word] += 1
        top_misrecognized = wrong_words.most_common(20)

        # --- Paires de confusion (mot → mot) ---
        confusion_pairs: Counter[tuple[str, str]] = Counter()
        for c in corrections:
            wrong_tokens = c.get("wrong", "").split()
            correct_tokens = c.get("correct", "").split()
            # Aligner les mots par position
            for w, r in zip(wrong_tokens, correct_tokens):
                if w != r:
                    pair = (w, r)
                    confusion_pairs[pair] += 1
        top_confusion = confusion_pairs.most_common(20)

        # --- Heures avec le plus d'erreurs (bruit ambiant ?) ---
        error_hours: Counter[int] = Counter()
        for c in corrections:
            ts = c.get("ts", 0)
            hour = datetime.fromtimestamp(ts).hour
            error_hours[hour] += 1
        # Trier par fréquence décroissante
        worst_hours = error_hours.most_common(24)

        # --- Commandes avec le plus de reformulations ---
        # Grouper les succès par commande résolue et compter les transcriptions uniques
        cmd_transcriptions: dict[str, set[str]] = defaultdict(set)
        for s in successes:
            cmd = s.get("resolved_command", "")
            text = s.get("transcription", "")
            if cmd and text:
                cmd_transcriptions[cmd].add(text)
        # Commandes avec plusieurs variantes = reformulations
        reformulated = [
            {"command": cmd, "variants": len(variants), "texts": sorted(variants)}
            for cmd, variants in cmd_transcriptions.items()
            if len(variants) >= 2
        ]
        reformulated.sort(key=lambda x: x["variants"], reverse=True)

        return {
            "days": days,
            "total_corrections": len(corrections),
            "total_successes": len(successes),
            "top_misrecognized_words": [
                {"word": w, "count": c} for w, c in top_misrecognized
            ],
            "confusion_pairs": [
                {"wrong": p[0], "correct": p[1], "count": c}
                for p, c in top_confusion
            ],
            "error_hours": [
                {"hour": h, "count": c} for h, c in worst_hours
            ],
            "reformulated_commands": reformulated[:20],
        }

    # ───────────────────────────────────────────────────────────────────
    # Génération automatique de corrections
    # ───────────────────────────────────────────────────────────────────

    def auto_generate_corrections(self, min_count: int = 3) -> list[dict[str, str]]:
        """Génère des auto-corrections quand un même mot est corrigé min_count+ fois.

        Détecte aussi les commandes reformulées min_count+ fois pour créer des alias.

        Returns:
            Liste de dicts avec type='correction' ou type='alias' et les paires.
        """
        all_entries = self._load_entries()
        corrections = [e for e in all_entries if e.get("type") == "correction"]
        successes = [e for e in all_entries if e.get("type") == "success"]
        results: list[dict[str, str]] = []

        # --- Auto-corrections de mots ---
        # Compter les paires (wrong_phrase → correct_phrase)
        phrase_pairs: Counter[tuple[str, str]] = Counter()
        for c in corrections:
            wrong = c.get("wrong", "").strip()
            correct = c.get("correct", "").strip()
            if wrong and correct:
                phrase_pairs[(wrong, correct)] += 1

        for (wrong, correct), count in phrase_pairs.items():
            if count >= min_count:
                results.append({
                    "type": "correction",
                    "wrong": wrong,
                    "correct": correct,
                    "count": str(count),
                    "action": "add_to_voice_corrections",
                })
                logger.info(
                    "Auto-correction détectée (%dx): '%s' → '%s'",
                    count, wrong, correct,
                )

        # --- Auto-corrections mot à mot ---
        word_pairs: Counter[tuple[str, str]] = Counter()
        for c in corrections:
            wrong_tokens = c.get("wrong", "").split()
            correct_tokens = c.get("correct", "").split()
            for w, r in zip(wrong_tokens, correct_tokens):
                if w != r:
                    word_pairs[(w, r)] += 1

        for (wrong, correct), count in word_pairs.items():
            if count >= min_count:
                # Vérifier qu'on n'a pas déjà ajouté au niveau phrase
                already = any(
                    r["wrong"] == wrong and r["correct"] == correct
                    for r in results
                )
                if not already:
                    results.append({
                        "type": "word_correction",
                        "wrong": wrong,
                        "correct": correct,
                        "count": str(count),
                        "action": "add_to_voice_corrections",
                    })

        # --- Auto-alias (commandes reformulées N+ fois) ---
        cmd_transcriptions: dict[str, list[str]] = defaultdict(list)
        for s in successes:
            cmd = s.get("resolved_command", "")
            text = s.get("transcription", "")
            if cmd and text:
                cmd_transcriptions[cmd].append(text)

        for cmd, texts in cmd_transcriptions.items():
            unique_texts = set(texts)
            if len(unique_texts) >= min_count:
                # La variante la plus fréquente est le "canonical"
                text_counter = Counter(texts)
                canonical = text_counter.most_common(1)[0][0]
                aliases = sorted(unique_texts - {canonical})
                for alias in aliases:
                    results.append({
                        "type": "alias",
                        "alias": alias,
                        "canonical": canonical,
                        "command": cmd,
                        "action": "create_voice_alias",
                    })
                    logger.info(
                        "Auto-alias détecté: '%s' → '%s' (cmd: %s)",
                        alias, canonical, cmd,
                    )

        return results

    # ───────────────────────────────────────────────────────────────────
    # Rapport d'entraînement
    # ───────────────────────────────────────────────────────────────────

    def generate_training_report(self) -> dict[str, Any]:
        """Génère un rapport complet d'entraînement vocal.

        Returns:
            Dict avec métriques, suggestions d'amélioration, score global.
        """
        all_entries = self._load_entries()
        successes = [e for e in all_entries if e.get("type") == "success"]
        corrections = [e for e in all_entries if e.get("type") == "correction"]

        total = len(successes) + len(corrections)
        score = self.get_recognition_score()

        # Analyse des 7 derniers jours
        errors_7d = self.analyze_errors(days=7)
        # Auto-corrections possibles
        auto_corrections = self.auto_generate_corrections(min_count=3)

        # --- Suggestions d'amélioration ---
        suggestions: list[dict[str, str]] = []

        # Suggérer des triggers pour les commandes reformulées
        for cmd_info in errors_7d.get("reformulated_commands", [])[:5]:
            suggestions.append({
                "type": "add_triggers",
                "command": cmd_info["command"],
                "reason": f"{cmd_info['variants']} formulations différentes détectées",
                "suggested_triggers": ", ".join(cmd_info.get("texts", [])[:5]),
            })

        # Suggérer des corrections pour les paires de confusion fréquentes
        for pair in errors_7d.get("confusion_pairs", [])[:5]:
            if pair["count"] >= 2:
                suggestions.append({
                    "type": "add_correction",
                    "wrong": pair["wrong"],
                    "correct": pair["correct"],
                    "reason": f"Confondu {pair['count']} fois en 7 jours",
                })

        # Alerter sur les heures problématiques
        for hour_info in errors_7d.get("error_hours", [])[:3]:
            if hour_info["count"] >= 5:
                suggestions.append({
                    "type": "noise_alert",
                    "hour": str(hour_info["hour"]),
                    "reason": f"{hour_info['count']} erreurs à {hour_info['hour']}h — bruit ambiant ?",
                })

        # Résumé temporel
        now = time.time()
        first_ts = min((e.get("ts", now) for e in all_entries), default=now)
        days_active = max(1, int((now - first_ts) / 86400))

        return {
            "generated_at": datetime.now().isoformat(),
            "total_entries": total,
            "total_successes": len(successes),
            "total_corrections": len(corrections),
            "recognition_score": score,
            "days_active": days_active,
            "avg_entries_per_day": round(total / days_active, 1),
            "errors_7d": errors_7d,
            "auto_corrections_available": len(auto_corrections),
            "auto_corrections": auto_corrections[:20],
            "suggestions": suggestions,
        }

    def get_recognition_score(self) -> float:
        """Calcule le score de reconnaissance global (succès / total).

        Returns:
            Score entre 0.0 et 1.0 (1.0 = parfait). 0.0 si aucune donnée.
        """
        all_entries = self._load_entries()
        successes = sum(1 for e in all_entries if e.get("type") == "success")
        corrections = sum(1 for e in all_entries if e.get("type") == "correction")
        total = successes + corrections
        if total == 0:
            return 0.0
        return round(successes / total, 4)

    # ───────────────────────────────────────────────────────────────────
    # Export pour fine-tuning
    # ───────────────────────────────────────────────────────────────────

    def export_for_whisper(self) -> str:
        """Exporte les données au format TSV pour fine-tuning Whisper.

        Format: audio_path<TAB>transcription
        Comme on n'a pas les fichiers audio, on utilise un placeholder
        et la transcription corrigée comme ground truth.

        Returns:
            Contenu TSV sous forme de chaîne.
        """
        all_entries = self._load_entries()
        output = io.StringIO()
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        writer.writerow(["audio_path", "transcription", "original", "type"])

        idx = 0
        for entry in all_entries:
            entry_type = entry.get("type", "")
            if entry_type == "success":
                # La transcription qui a marché = bonne donnée d'entraînement
                writer.writerow([
                    f"audio_{idx:06d}.wav",
                    entry.get("transcription", ""),
                    entry.get("transcription", ""),
                    "success",
                ])
                idx += 1
            elif entry_type == "correction":
                # Le texte correct = ground truth pour la mauvaise transcription
                writer.writerow([
                    f"audio_{idx:06d}.wav",
                    entry.get("correct", ""),
                    entry.get("wrong", ""),
                    "correction",
                ])
                idx += 1

        result = output.getvalue()
        # Sauvegarder aussi en fichier
        export_path = DATA_DIR / "export" / "whisper_training.tsv"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            export_path.write_text(result, encoding="utf-8")
            logger.info("Export Whisper: %d entrées → %s", idx, export_path)
        except OSError as exc:
            logger.error("Impossible d'écrire l'export Whisper: %s", exc)

        return result

    def export_for_vosk(self) -> str:
        """Exporte les données au format compatible Vosk (JSONL avec phrases).

        Format Vosk language model adaptation:
        Chaque ligne est un JSON {"text": "phrase corrigée"}
        pour enrichir le modèle de langue Vosk.

        Returns:
            Contenu JSONL sous forme de chaîne.
        """
        all_entries = self._load_entries()
        lines: list[str] = []
        seen: set[str] = set()

        for entry in all_entries:
            entry_type = entry.get("type", "")
            text = ""
            if entry_type == "success":
                text = entry.get("transcription", "").strip()
            elif entry_type == "correction":
                text = entry.get("correct", "").strip()

            if text and text not in seen:
                seen.add(text)
                lines.append(json.dumps({"text": text}, ensure_ascii=False))

        result = "\n".join(lines) + "\n" if lines else ""

        # Sauvegarder aussi en fichier
        export_path = DATA_DIR / "export" / "vosk_sentences.jsonl"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            export_path.write_text(result, encoding="utf-8")
            logger.info("Export Vosk: %d phrases uniques → %s", len(lines), export_path)
        except OSError as exc:
            logger.error("Impossible d'écrire l'export Vosk: %s", exc)

        return result

    # ───────────────────────────────────────────────────────────────────
    # Utilitaires
    # ───────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Statistiques rapides sans analyse complète."""
        all_entries = self._load_entries()
        successes = sum(1 for e in all_entries if e.get("type") == "success")
        corrections = sum(1 for e in all_entries if e.get("type") == "correction")
        return {
            "total_entries": len(all_entries),
            "successes": successes,
            "corrections": corrections,
            "score": self.get_recognition_score(),
            "data_file": str(self._data_file),
            "file_exists": self._data_file.exists(),
        }

    def clear_data(self) -> None:
        """Supprime toutes les données d'entraînement (reset complet)."""
        if self._data_file.exists():
            self._data_file.unlink()
            logger.warning("Données d'entraînement supprimées: %s", self._data_file)
        self._entries = []
        self._loaded = True


# ═══════════════════════════════════════════════════════════════════════════
# INSTANCE GLOBALE — Singleton pour usage dans le pipeline vocal
# ═══════════════════════════════════════════════════════════════════════════

_trainer: VoiceTrainer | None = None


def get_trainer() -> VoiceTrainer:
    """Retourne l'instance globale du VoiceTrainer (lazy init)."""
    global _trainer
    if _trainer is None:
        _trainer = VoiceTrainer()
    return _trainer
