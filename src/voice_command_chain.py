"""JARVIS Voice Command Chain — Enchaînement intelligent de commandes vocales.

Permet de chaîner des commandes où le résultat de l'une alimente la suivante,
avec variables de contexte persistantes entre les étapes.

Exemples :
    "cherche les gros fichiers et supprime les plus vieux"
    "liste les services et redémarre ceux qui sont failed"
    "vérifie le cluster et envoie le rapport par telegram"

Usage:
    from src.voice_command_chain import command_chain
    chain = command_chain.create_chain(["cherche les gros fichiers", "supprime les plus vieux"])
    result = await command_chain.execute_chain(chain)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shlex
import sqlite3
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine

__all__ = [
    "Chain",
    "ChainStep",
    "ChainResult",
    "CommandChain",
    "command_chain",
]

logger = logging.getLogger("jarvis.voice_chain")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "jarvis.db"

# ── Verbes d'action qui déclenchent un chaînage automatique ──────────────

ACTION_VERBS: list[str] = [
    "supprime", "supprimer", "efface", "effacer",
    "redémarre", "redémarrer", "restart", "relance", "relancer",
    "envoie", "envoyer", "envoi",
    "copie", "copier", "déplace", "déplacer", "move",
    "arrête", "arrêter", "stoppe", "stopper", "stop",
    "démarre", "démarrer", "lance", "lancer", "start",
    "installe", "installer",
    "analyse", "analyser",
    "sauvegarde", "sauvegarder", "backup",
    "compresse", "compresser", "archive", "archiver",
    "affiche", "afficher", "montre", "montrer",
    "trie", "trier", "filtre", "filtrer",
    "compte", "compter",
    "nettoie", "nettoyer", "clean",
    "télécharge", "télécharger", "download",
    "upload", "envoie", "pousse", "push",
    "kill", "tue", "tuer",
]

# ── Patterns pour extraire des infos du résultat précédent ───────────────

_RE_FILE_PATH = re.compile(r"(/[\w./_-]+(?:\.\w+)?)")
_RE_NUMBER = re.compile(r"(\d+(?:[.,]\d+)?)")
_RE_SERVICE_NAME = re.compile(r"(\S+\.service)")
_RE_PID = re.compile(r"\b(\d{2,7})\b")


class StepStatus(str, Enum):
    """Statut d'une étape de la chaîne."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ChainStep:
    """Une étape dans la chaîne de commandes."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    raw_command: str = ""
    resolved_command: str = ""
    action_type: str = "bash"  # bash | python | chain | internal
    status: StepStatus = StepStatus.PENDING
    output: str = ""
    error: str = ""
    duration_ms: float = 0.0
    timestamp: float = 0.0


@dataclass
class Chain:
    """Chaîne de commandes à exécuter séquentiellement."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    steps: list[ChainStep] = field(default_factory=list)
    original_input: str = ""
    created_at: float = field(default_factory=time.time)
    status: StepStatus = StepStatus.PENDING


@dataclass
class ChainResult:
    """Résultat complet d'une exécution de chaîne."""
    chain_id: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    final_output: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    total_ms: float = 0.0
    ok: bool = True
    step_count: int = 0
    success_count: int = 0
    fail_count: int = 0


# ── Mappings de commandes vocales vers commandes système ─────────────────

_VOCAL_TO_CMD: dict[str, str] = {
    # Recherche de fichiers
    "cherche les gros fichiers": "find / -xdev -type f -size +100M -exec ls -lhS {} + 2>/dev/null | head -20",
    "cherche les fichiers récents": "find /home -type f -mtime -1 -exec ls -lt {} + 2>/dev/null | head -20",
    "cherche les fichiers vides": "find /home -type f -empty 2>/dev/null | head -20",
    "cherche les doublons": "find /home -type f -exec md5sum {} + 2>/dev/null | sort | uniq -d -w32 | head -20",
    # Services
    "liste les services": "systemctl list-units --type=service --no-pager",
    "liste les services failed": "systemctl list-units --type=service --state=failed --no-pager",
    "liste les services actifs": "systemctl list-units --type=service --state=active --no-pager",
    # Processus
    "liste les processus": "ps aux --sort=-%mem | head -20",
    "liste les processus gourmands": "ps aux --sort=-%cpu | head -10",
    # Réseau
    "vérifie le réseau": "ip -br addr && echo '---' && ss -tulnp | head -20",
    "teste la connexion": "ping -c 3 8.8.8.8 && curl -sI https://google.com | head -5",
    # Cluster
    "vérifie le cluster": "curl -s http://127.0.0.1:1234/v1/models 2>/dev/null | python3 -m json.tool || echo 'Cluster indisponible'",
    "statut du cluster": "curl -s http://127.0.0.1:1234/v1/models 2>/dev/null || echo 'Offline'",
    # Système
    "vérifie l'espace disque": "df -h | grep -v tmpfs",
    "vérifie la mémoire": "free -h",
    "vérifie la température": "nvidia-smi --query-gpu=temperature.gpu,name,utilization.gpu --format=csv,noheader 2>/dev/null || sensors 2>/dev/null || echo 'Pas de capteur'",
    "vérifie les logs": "journalctl --since '1 hour ago' --priority=err --no-pager | tail -30",
    "vérifie les mises à jour": "apt list --upgradable 2>/dev/null | head -20",
}

# ── Mappings d'actions sur résultat précédent ────────────────────────────

_ACTION_TEMPLATES: dict[str, str] = {
    # Suppression
    "supprime les plus vieux": "echo '$LAST_RESULT' | tail -5 | awk '{print $NF}' | xargs -r rm -v",
    "supprime les plus gros": "echo '$LAST_RESULT' | head -5 | awk '{print $NF}' | xargs -r rm -v",
    "supprime tout": "echo '$LAST_RESULT' | awk '{print $NF}' | xargs -r rm -v",
    # Services
    "redémarre ceux qui sont failed": "echo '$LAST_RESULT' | grep failed | awk '{print $1}' | xargs -r -I{} systemctl restart {}",
    "redémarre tout": "echo '$LAST_RESULT' | grep '\\.service' | awk '{print $1}' | xargs -r -I{} systemctl restart {}",
    "arrête ceux qui sont failed": "echo '$LAST_RESULT' | grep failed | awk '{print $1}' | xargs -r -I{} systemctl stop {}",
    # Processus
    "kill les plus gourmands": "echo '$LAST_RESULT' | awk 'NR>1{print $2}' | head -5 | xargs -r kill -9",
    "tue les zombies": "ps aux | awk '$8==\"Z\"{print $2}' | xargs -r kill -9",
    # Envoi / rapport
    "envoie le rapport": "echo '$LAST_RESULT' | tee /tmp/jarvis_report_$(date +%s).txt",
    "envoie le rapport par telegram": "echo '$LAST_RESULT' > /tmp/jarvis_report.txt && echo 'Rapport sauvé: /tmp/jarvis_report.txt'",
    "envoie par email": "echo '$LAST_RESULT' > /tmp/jarvis_report.txt && echo 'Rapport prêt pour envoi'",
    # Sauvegarde
    "sauvegarde le résultat": "echo '$LAST_RESULT' > /tmp/jarvis_chain_$(date +%s).txt && echo 'Sauvegardé'",
    "archive le résultat": "echo '$LAST_RESULT' | gzip > /tmp/jarvis_chain_$(date +%s).gz && echo 'Archivé'",
    # Tri / filtre
    "trie par taille": "echo '$LAST_RESULT' | sort -k5 -h",
    "trie par date": "echo '$LAST_RESULT' | sort -k6,7",
    "filtre les erreurs": "echo '$LAST_RESULT' | grep -i 'error\\|fail\\|critical'",
    "compte les résultats": "echo '$LAST_RESULT' | wc -l",
    # Affichage
    "affiche les 10 premiers": "echo '$LAST_RESULT' | head -10",
    "affiche les 10 derniers": "echo '$LAST_RESULT' | tail -10",
}


class CommandChain:
    """Moteur de chaînage de commandes vocales avec contexte partagé."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DB_PATH
        self._context: dict[str, Any] = {
            "LAST_RESULT": "",
            "LAST_FILE": "",
            "LAST_COUNT": 0,
            "LAST_ERROR": "",
            "LAST_FILES": [],
            "LAST_SERVICES": [],
            "LAST_PIDS": [],
        }
        self._history: list[ChainResult] = []
        self._max_history = 100
        # Handlers personnalisés par type d'action
        self._custom_handlers: dict[str, Callable[..., Coroutine[Any, Any, str]]] = {}

    # ── API publique ─────────────────────────────────────────────────────

    def create_chain(self, steps: list[str], original_input: str = "") -> Chain:
        """Crée une chaîne à partir d'une liste de commandes textuelles.

        Args:
            steps: Liste de commandes en langage naturel.
            original_input: Phrase d'origine complète (optionnel).

        Returns:
            Chain prête à être exécutée.
        """
        chain = Chain(original_input=original_input or " et ".join(steps))
        for raw in steps:
            step = ChainStep(raw_command=raw.strip())
            chain.steps.append(step)
        logger.info("Chaîne créée : %s avec %d étapes", chain.id, len(chain.steps))
        return chain

    async def execute_chain(self, chain: Chain) -> ChainResult:
        """Exécute une chaîne étape par étape, en propageant le contexte.

        Args:
            chain: Chaîne à exécuter.

        Returns:
            ChainResult avec le résultat de chaque étape.
        """
        t0 = time.time()
        chain.status = StepStatus.RUNNING
        result = ChainResult(chain_id=chain.id, step_count=len(chain.steps))

        for i, step in enumerate(chain.steps):
            step.status = StepStatus.RUNNING
            step.timestamp = time.time()

            try:
                # Résoudre la commande avec le contexte
                resolved = self._resolve_command(step.raw_command, is_followup=(i > 0))
                step.resolved_command = resolved
                step.action_type = self._detect_action_type(resolved)

                # Exécuter
                st = time.time()
                output = await self._execute_step(step)
                step.duration_ms = (time.time() - st) * 1000
                step.output = output
                step.status = StepStatus.SUCCESS

                # Mettre à jour le contexte
                self._update_context(output)
                result.success_count += 1

            except Exception as exc:
                step.error = str(exc)
                step.status = StepStatus.FAILED
                step.duration_ms = (time.time() - step.timestamp) * 1000
                self._context["LAST_ERROR"] = str(exc)
                result.fail_count += 1
                logger.error("Étape %d échouée : %s", i, exc)

            result.steps.append({
                "id": step.id,
                "raw": step.raw_command,
                "resolved": step.resolved_command,
                "type": step.action_type,
                "status": step.status.value,
                "output": step.output[:2000],
                "error": step.error,
                "duration_ms": round(step.duration_ms, 1),
            })

        result.total_ms = (time.time() - t0) * 1000
        result.ok = result.fail_count == 0
        result.final_output = chain.steps[-1].output if chain.steps else ""
        result.context = dict(self._context)
        chain.status = StepStatus.SUCCESS if result.ok else StepStatus.FAILED

        # Historique
        self._history.append(result)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        logger.info(
            "Chaîne %s terminée : %d/%d OK en %.0fms",
            chain.id, result.success_count, result.step_count, result.total_ms,
        )
        return result

    def get_context(self) -> dict[str, Any]:
        """Retourne les variables de contexte actuelles.

        Returns:
            Dictionnaire des variables ($LAST_RESULT, $LAST_FILE, etc.).
        """
        return dict(self._context)

    def clear_context(self) -> None:
        """Réinitialise toutes les variables de contexte."""
        self._context = {
            "LAST_RESULT": "",
            "LAST_FILE": "",
            "LAST_COUNT": 0,
            "LAST_ERROR": "",
            "LAST_FILES": [],
            "LAST_SERVICES": [],
            "LAST_PIDS": [],
        }
        logger.info("Contexte réinitialisé")

    def parse_vocal_chain(self, text: str) -> Chain | None:
        """Détecte et parse un enchaînement dans une phrase vocale.

        Cherche le pattern "commande1 et verbe_action commande2" et crée
        une chaîne automatiquement.

        Args:
            text: Phrase vocale brute.

        Returns:
            Chain si un enchaînement est détecté, None sinon.
        """
        text_lower = text.lower().strip()

        # Chercher "et" suivi d'un verbe d'action
        for verb in ACTION_VERBS:
            pattern = re.compile(
                rf"^(.+?)\s+et\s+({re.escape(verb)}\s+.+)$",
                re.IGNORECASE,
            )
            match = pattern.match(text_lower)
            if match:
                step1 = match.group(1).strip()
                step2 = match.group(2).strip()
                logger.info("Chaîne vocale détectée : [%s] → [%s]", step1, step2)
                return self.create_chain([step1, step2], original_input=text)

        # Chercher "puis" comme connecteur alternatif
        if " puis " in text_lower:
            parts = text_lower.split(" puis ", 1)
            if len(parts) == 2 and any(v in parts[1] for v in ACTION_VERBS):
                return self.create_chain(
                    [parts[0].strip(), parts[1].strip()],
                    original_input=text,
                )

        # Chercher des virgules avec verbe d'action après
        if ", " in text_lower:
            parts = text_lower.split(", ", 1)
            if len(parts) == 2 and any(parts[1].startswith(v) for v in ACTION_VERBS):
                return self.create_chain(
                    [parts[0].strip(), parts[1].strip()],
                    original_input=text,
                )

        return None

    def register_handler(
        self,
        action_type: str,
        handler: Callable[..., Coroutine[Any, Any, str]],
    ) -> None:
        """Enregistre un handler personnalisé pour un type d'action.

        Args:
            action_type: Type d'action (ex: "telegram", "email").
            handler: Fonction async qui reçoit (command, context) et retourne le résultat.
        """
        self._custom_handlers[action_type] = handler
        logger.info("Handler enregistré pour type : %s", action_type)

    def get_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Retourne l'historique des chaînes exécutées.

        Args:
            limit: Nombre max de résultats.

        Returns:
            Liste des derniers résultats.
        """
        return [
            {
                "chain_id": r.chain_id,
                "ok": r.ok,
                "steps": r.step_count,
                "success": r.success_count,
                "total_ms": round(r.total_ms, 1),
            }
            for r in self._history[-limit:]
        ]

    # ── Résolution de commande ───────────────────────────────────────────

    def _resolve_command(self, raw: str, is_followup: bool = False) -> str:
        """Résout une commande vocale en commande système.

        Cherche d'abord dans les mappings vocaux, puis dans les templates
        d'action, puis essaie une résolution directe.
        """
        raw_lower = raw.lower().strip()

        # Si c'est une commande de suivi, chercher dans les templates d'action
        if is_followup:
            for template_key, template_cmd in _ACTION_TEMPLATES.items():
                if template_key in raw_lower or self._fuzzy_match(raw_lower, template_key):
                    # Substituer les variables de contexte
                    return self._substitute_context(template_cmd)

        # Chercher dans les commandes vocales connues
        for vocal_key, cmd in _VOCAL_TO_CMD.items():
            if vocal_key in raw_lower or raw_lower in vocal_key:
                return cmd

        # Chercher une correspondance partielle
        best_match = ""
        best_score = 0.0
        for vocal_key, cmd in _VOCAL_TO_CMD.items():
            score = self._similarity(raw_lower, vocal_key)
            if score > best_score and score > 0.5:
                best_score = score
                best_match = cmd
        if best_match:
            return best_match

        # Même logique pour les templates d'action
        if is_followup:
            for template_key, template_cmd in _ACTION_TEMPLATES.items():
                score = self._similarity(raw_lower, template_key)
                if score > best_score and score > 0.4:
                    best_score = score
                    best_match = self._substitute_context(template_cmd)
            if best_match:
                return best_match

        # Commande brute — si ça ressemble à du bash, garder tel quel
        if raw.startswith("/") or raw.startswith("sudo ") or "|" in raw:
            return raw

        # Dernier recours : echo
        return f"echo 'Commande non reconnue: {raw}'"

    def _substitute_context(self, template: str) -> str:
        """Remplace les variables $LAST_* dans un template."""
        result = template
        result = result.replace("$LAST_RESULT", str(self._context.get("LAST_RESULT", "")))
        result = result.replace("$LAST_FILE", str(self._context.get("LAST_FILE", "")))
        result = result.replace("$LAST_COUNT", str(self._context.get("LAST_COUNT", 0)))
        result = result.replace("$LAST_ERROR", str(self._context.get("LAST_ERROR", "")))
        return result

    def _detect_action_type(self, command: str) -> str:
        """Détecte le type d'action d'une commande résolue."""
        if command.startswith("python") or command.startswith("uv run"):
            return "python"
        if any(kw in command for kw in ["curl", "wget", "http"]):
            return "http"
        return "bash"

    # ── Exécution ────────────────────────────────────────────────────────

    async def _execute_step(self, step: ChainStep) -> str:
        """Exécute une étape et retourne sa sortie."""
        cmd = step.resolved_command

        # Handler personnalisé
        if step.action_type in self._custom_handlers:
            handler = self._custom_handlers[step.action_type]
            return await handler(cmd, self._context)

        # Exécution bash par défaut
        return await self._run_bash(cmd)

    async def _run_bash(self, command: str, timeout: float = 30.0) -> str:
        """Exécute une commande bash de manière asynchrone.

        Args:
            command: Commande à exécuter.
            timeout: Timeout en secondes.

        Returns:
            Sortie stdout (ou stderr si vide).
        """
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
            output = stdout.decode("utf-8", errors="replace").strip()
            if not output and stderr:
                err_text = stderr.decode("utf-8", errors="replace").strip()
                if proc.returncode != 0:
                    raise RuntimeError(f"Code {proc.returncode}: {err_text}")
                output = err_text
            return output

        except asyncio.TimeoutError:
            proc.kill()  # type: ignore[union-attr]
            raise RuntimeError(f"Timeout ({timeout}s) : {command[:80]}")

    # ── Mise à jour du contexte ──────────────────────────────────────────

    def _update_context(self, output: str) -> None:
        """Met à jour les variables de contexte à partir de la sortie."""
        self._context["LAST_RESULT"] = output

        # Extraire les chemins de fichiers
        files = _RE_FILE_PATH.findall(output)
        if files:
            self._context["LAST_FILE"] = files[-1]
            self._context["LAST_FILES"] = files[:20]

        # Extraire les nombres
        numbers = _RE_NUMBER.findall(output)
        if numbers:
            try:
                self._context["LAST_COUNT"] = int(numbers[-1].replace(",", ""))
            except ValueError:
                self._context["LAST_COUNT"] = float(numbers[-1].replace(",", "."))

        # Extraire les noms de services
        services = _RE_SERVICE_NAME.findall(output)
        if services:
            self._context["LAST_SERVICES"] = services[:20]

        # Extraire les PIDs
        pids = _RE_PID.findall(output)
        if pids:
            self._context["LAST_PIDS"] = pids[:20]

    # ── Utilitaires de matching ──────────────────────────────────────────

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Score de similarité simple entre deux chaînes (Jaccard sur mots)."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    @staticmethod
    def _fuzzy_match(text: str, pattern: str) -> bool:
        """Vérifie si le texte contient tous les mots clés du pattern."""
        pattern_words = pattern.lower().split()
        text_lower = text.lower()
        return all(w in text_lower for w in pattern_words)


# ── Insertion des commandes chain dans la base ───────────────────────────

CHAIN_VOICE_COMMANDS: list[dict[str, Any]] = [
    {
        "name": "chain_gros_fichiers_supprime",
        "category": "chain",
        "description": "Cherche les gros fichiers et supprime les plus vieux",
        "triggers": '["cherche les gros fichiers et supprime les plus vieux", "trouve les gros fichiers et supprime"]',
        "action_type": "chain",
        "action": "cherche les gros fichiers|supprime les plus vieux",
    },
    {
        "name": "chain_services_restart_failed",
        "category": "chain",
        "description": "Liste les services et redémarre ceux qui sont failed",
        "triggers": '["liste les services et redémarre ceux qui sont failed", "relance les services failed"]',
        "action_type": "chain",
        "action": "liste les services failed|redémarre ceux qui sont failed",
    },
    {
        "name": "chain_cluster_rapport",
        "category": "chain",
        "description": "Vérifie le cluster et envoie le rapport",
        "triggers": '["vérifie le cluster et envoie le rapport", "check cluster et rapport"]',
        "action_type": "chain",
        "action": "vérifie le cluster|envoie le rapport",
    },
    {
        "name": "chain_disque_nettoie",
        "category": "chain",
        "description": "Vérifie l'espace disque et nettoie si besoin",
        "triggers": '["vérifie le disque et nettoie", "espace disque et nettoyage"]',
        "action_type": "chain",
        "action": "vérifie l'espace disque|nettoie le système",
    },
    {
        "name": "chain_processus_kill",
        "category": "chain",
        "description": "Liste les processus gourmands et kill les plus gros",
        "triggers": '["liste les processus gourmands et kill", "trouve les processus et tue les"]',
        "action_type": "chain",
        "action": "liste les processus gourmands|kill les plus gourmands",
    },
    {
        "name": "chain_logs_filtre_erreurs",
        "category": "chain",
        "description": "Vérifie les logs et filtre les erreurs",
        "triggers": '["vérifie les logs et filtre les erreurs", "logs et erreurs"]',
        "action_type": "chain",
        "action": "vérifie les logs|filtre les erreurs",
    },
    {
        "name": "chain_fichiers_recents_archive",
        "category": "chain",
        "description": "Cherche les fichiers récents et archive le résultat",
        "triggers": '["cherche les fichiers récents et archive", "fichiers récents puis archive"]',
        "action_type": "chain",
        "action": "cherche les fichiers récents|archive le résultat",
    },
    {
        "name": "chain_memoire_rapport",
        "category": "chain",
        "description": "Vérifie la mémoire et envoie le rapport",
        "triggers": '["vérifie la mémoire et envoie le rapport", "check mémoire et rapport"]',
        "action_type": "chain",
        "action": "vérifie la mémoire|envoie le rapport",
    },
    {
        "name": "chain_services_actifs_compte",
        "category": "chain",
        "description": "Liste les services actifs et compte les résultats",
        "triggers": '["liste les services actifs et compte", "combien de services actifs"]',
        "action_type": "chain",
        "action": "liste les services actifs|compte les résultats",
    },
    {
        "name": "chain_temperature_rapport",
        "category": "chain",
        "description": "Vérifie la température et sauvegarde le résultat",
        "triggers": '["vérifie la température et sauvegarde", "température et sauvegarde"]',
        "action_type": "chain",
        "action": "vérifie la température|sauvegarde le résultat",
    },
    {
        "name": "chain_mises_a_jour_compte",
        "category": "chain",
        "description": "Vérifie les mises à jour et compte les résultats",
        "triggers": '["vérifie les mises à jour et compte", "combien de mises à jour"]',
        "action_type": "chain",
        "action": "vérifie les mises à jour|compte les résultats",
    },
    {
        "name": "chain_reseau_rapport_telegram",
        "category": "chain",
        "description": "Vérifie le réseau et envoie le rapport par telegram",
        "triggers": '["vérifie le réseau et envoie par telegram", "check réseau et telegram"]',
        "action_type": "chain",
        "action": "vérifie le réseau|envoie le rapport par telegram",
    },
    {
        "name": "chain_fichiers_vides_supprime",
        "category": "chain",
        "description": "Cherche les fichiers vides et supprime tout",
        "triggers": '["cherche les fichiers vides et supprime", "supprime les fichiers vides"]',
        "action_type": "chain",
        "action": "cherche les fichiers vides|supprime tout",
    },
    {
        "name": "chain_processus_trie_taille",
        "category": "chain",
        "description": "Liste les processus et trie par taille",
        "triggers": '["liste les processus et trie par taille", "processus triés par mémoire"]',
        "action_type": "chain",
        "action": "liste les processus|trie par taille",
    },
    {
        "name": "chain_cluster_sauvegarde",
        "category": "chain",
        "description": "Vérifie le cluster et sauvegarde le résultat",
        "triggers": '["vérifie le cluster et sauvegarde", "check cluster et backup"]',
        "action_type": "chain",
        "action": "vérifie le cluster|sauvegarde le résultat",
    },
    {
        "name": "chain_connexion_rapport",
        "category": "chain",
        "description": "Teste la connexion et envoie le rapport",
        "triggers": '["teste la connexion et envoie le rapport", "test connexion et rapport"]',
        "action_type": "chain",
        "action": "teste la connexion|envoie le rapport",
    },
    {
        "name": "chain_services_failed_arrete",
        "category": "chain",
        "description": "Liste les services failed et arrête-les",
        "triggers": '["liste les services failed et arrête", "stop les services failed"]',
        "action_type": "chain",
        "action": "liste les services failed|arrête ceux qui sont failed",
    },
    {
        "name": "chain_gros_fichiers_trie",
        "category": "chain",
        "description": "Cherche les gros fichiers et trie par date",
        "triggers": '["cherche les gros fichiers et trie par date", "gros fichiers triés par date"]',
        "action_type": "chain",
        "action": "cherche les gros fichiers|trie par date",
    },
    {
        "name": "chain_logs_sauvegarde",
        "category": "chain",
        "description": "Vérifie les logs et sauvegarde le résultat",
        "triggers": '["vérifie les logs et sauvegarde", "logs et sauvegarde"]',
        "action_type": "chain",
        "action": "vérifie les logs|sauvegarde le résultat",
    },
    {
        "name": "chain_disque_rapport_email",
        "category": "chain",
        "description": "Vérifie l'espace disque et envoie par email",
        "triggers": '["vérifie le disque et envoie par email", "espace disque par email"]',
        "action_type": "chain",
        "action": "vérifie l'espace disque|envoie par email",
    },
]


def insert_chain_commands(db_path: Path | None = None) -> int:
    """Insère les 20 commandes vocales chain dans jarvis.db.

    Returns:
        Nombre de commandes insérées.
    """
    db = db_path or DB_PATH
    inserted = 0
    now = time.time()

    with sqlite3.connect(str(db)) as conn:
        for cmd in CHAIN_VOICE_COMMANDS:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO voice_commands
                       (name, category, description, triggers, action_type, action,
                        params, confirm, enabled, created_at, usage_count, success_count, fail_count)
                       VALUES (?, ?, ?, ?, ?, ?, '[]', 0, 1, ?, 0, 0, 0)""",
                    (
                        cmd["name"],
                        cmd["category"],
                        cmd["description"],
                        cmd["triggers"],
                        cmd["action_type"],
                        cmd["action"],
                        now,
                    ),
                )
                if conn.total_changes:
                    inserted += 1
            except sqlite3.IntegrityError:
                logger.debug("Commande déjà existante : %s", cmd["name"])
        conn.commit()

    logger.info("%d commandes chain insérées dans %s", inserted, db)
    return inserted


# ── Instance singleton ───────────────────────────────────────────────────

command_chain = CommandChain()


# ── Auto-insertion des commandes au chargement ───────────────────────────

def _auto_setup() -> None:
    """Insère les commandes chain dans la DB si elle existe."""
    if DB_PATH.exists():
        try:
            insert_chain_commands()
        except Exception as exc:
            logger.warning("Impossible d'insérer les commandes chain : %s", exc)


_auto_setup()
