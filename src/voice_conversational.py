"""voice_conversational.py — Moteur vocal conversationnel avec cluster IA.

Quand aucun module vocal ne reconnait une commande, ce moteur :
1. Envoie la requete au cluster IA (M1 ou OL1) pour comprendre l'intention
2. Genere un plan d'execution (liste de commandes bash)
3. Execute le plan avec validation de securite
4. Sauvegarde le dialogue + plan dans skills.json via save_learned_pipeline()

Usage:
    engine = ConversationalVoiceEngine()
    result = engine.process_unknown_command("liste les fichiers python du projet")
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any

# Garantir que le dossier racine jarvis est dans le PYTHONPATH
_jarvis_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _jarvis_root not in sys.path:
    sys.path.insert(0, _jarvis_root)

logger = logging.getLogger("jarvis.voice_conversational")

# ============================================================================
# Configuration des endpoints IA
# ============================================================================

# M1 — LM Studio (prioritaire, plus puissant)
M1_ENDPOINT = "http://127.0.0.1:1234/api/v1/chat/completions"
M1_TIMEOUT = 15

# OL1 — Ollama (fallback rapide)
OL1_ENDPOINT = "http://127.0.0.1:11434/api/chat"
OL1_TIMEOUT = 15
OL1_MODEL = "qwen3:1.7b"

# Limites d'execution
CMD_TIMEOUT = 10       # Timeout par commande individuelle (secondes)
TOTAL_TIMEOUT = 30     # Timeout global pour toutes les commandes (secondes)
MAX_COMMANDS = 10       # Nombre max de commandes dans un plan

# Prompt systeme pour l'IA — demande un JSON strict
SYSTEM_PROMPT = (
    "Tu es JARVIS. Convertis cette demande en commandes Linux bash. "
    "Retourne UNIQUEMENT un JSON: "
    '{"commands": ["cmd1", "cmd2"], "description": "ce que ça fait"}'
)

# ============================================================================
# Liste noire de commandes dangereuses
# ============================================================================

DANGEROUS_PATTERNS: list[str] = [
    # Destruction de systeme de fichiers
    "rm -rf /",
    "rm -rf /*",
    "rm -rf ~",
    "rm -rf ~/",
    "rm -rf .",
    # Formatage / ecrasement disque
    "mkfs",
    "dd if=/dev/zero of=/dev/sd",
    "dd if=/dev/zero of=/dev/nvme",
    "dd if=/dev/random of=/dev/sd",
    "dd if=/dev/urandom of=/dev/sd",
    # Fork bomb
    ":(){ :|:& };:",
    # Ecriture directe sur les devices
    "> /dev/sd",
    "of=/dev/sd",
    "of=/dev/nvme",
    # Suppression de fichiers critiques
    "rm /etc/passwd",
    "rm /etc/shadow",
    "rm -rf /boot",
    "rm -rf /usr",
    "rm -rf /var",
    "rm -rf /etc",
    "rm -rf /sys",
    "rm -rf /proc",
    # Commandes reseau dangereuses
    "iptables -F",
    "iptables --flush",
    # Modification du bootloader
    "grub-install",
    "update-grub",
    # Shutdown / reboot (sauf si explicite)
    "shutdown",
    "reboot",
    "init 0",
    "init 6",
    "poweroff",
    "halt",
    # Chmod/chown recursif sur racine
    "chmod -R 777 /",
    "chown -R",
    # Telechargement et execution aveugle
    "curl | sh",
    "curl | bash",
    "wget | sh",
    "wget | bash",
    # Kernel panic
    "echo c > /proc/sysrq-trigger",
    # Swap off complet
    "swapoff -a",
]


def _is_command_safe(cmd: str) -> bool:
    """Verifie qu'une commande ne correspond a aucun pattern dangereux."""
    cmd_lower = cmd.lower().strip()
    for pattern in DANGEROUS_PATTERNS:
        if pattern.lower() in cmd_lower:
            return False
    # Verification supplementaire: pas de sudo avec des commandes destructives
    if cmd_lower.startswith("sudo") and any(
        danger in cmd_lower for danger in ["rm -rf", "mkfs", "dd if=/dev", "format"]
    ):
        return False
    return True


# ============================================================================
# Classe principale
# ============================================================================


@dataclass
class CommandResult:
    """Resultat d'execution d'une commande individuelle."""
    command: str
    returncode: int
    stdout: str
    stderr: str
    duration_ms: float
    success: bool


class ConversationalVoiceEngine:
    """Moteur vocal conversationnel — interprete les commandes inconnues via le cluster IA."""

    def __init__(self) -> None:
        # Compteurs de statistiques
        self._stats: dict[str, int] = {
            "total_requests": 0,
            "m1_calls": 0,
            "ol1_calls": 0,
            "m1_successes": 0,
            "ol1_successes": 0,
            "plans_executed": 0,
            "plans_failed": 0,
            "commands_executed": 0,
            "commands_failed": 0,
            "commands_blocked": 0,
            "skills_saved": 0,
            "parse_errors": 0,
        }

    # ----------------------------------------------------------------
    # Point d'entree principal
    # ----------------------------------------------------------------

    def process_unknown_command(self, text: str) -> dict[str, Any]:
        """Traite une commande vocale inconnue via le cluster IA.

        1. Envoie au cluster IA (M1 puis OL1) pour obtenir un plan bash
        2. Valide les commandes (blacklist)
        3. Execute chaque commande
        4. Sauvegarde le pipeline appris si succes

        Returns:
            {"success": bool, "method": str, "result": str,
             "confidence": float, "module": str, "commands": list,
             "description": str, "execution_results": list}
        """
        self._stats["total_requests"] += 1
        start = time.time()

        if not text or not text.strip():
            return self._fail_result("Commande vide", start)

        # Etape 1: Obtenir le plan d'execution depuis le cluster IA
        plan = self._get_ai_plan(text)
        if not plan:
            return self._fail_result(
                "Impossible d'obtenir un plan d'execution depuis le cluster IA", start
            )

        commands: list[str] = plan.get("commands", [])
        description: str = plan.get("description", "Plan genere par IA")

        if not commands:
            return self._fail_result("Le plan IA ne contient aucune commande", start)

        # Limiter le nombre de commandes
        if len(commands) > MAX_COMMANDS:
            commands = commands[:MAX_COMMANDS]
            logger.warning(
                "Plan tronque a %d commandes (max: %d)", MAX_COMMANDS, MAX_COMMANDS
            )

        # Etape 2: Valider toutes les commandes (blacklist)
        blocked: list[str] = []
        safe_commands: list[str] = []
        for cmd in commands:
            if _is_command_safe(cmd):
                safe_commands.append(cmd)
            else:
                blocked.append(cmd)
                self._stats["commands_blocked"] += 1
                logger.warning("Commande bloquee (dangereuse): %s", cmd)

        if not safe_commands:
            return self._fail_result(
                f"Toutes les commandes ont ete bloquees (dangereuses): {blocked}",
                start,
            )

        # Etape 3: Executer chaque commande
        execution_results = self._execute_plan(safe_commands)

        # Verifier le succes global
        all_success = all(r.success for r in execution_results)
        any_success = any(r.success for r in execution_results)

        if any_success:
            self._stats["plans_executed"] += 1
        else:
            self._stats["plans_failed"] += 1

        # Etape 4: Sauvegarder le pipeline appris si succes
        if any_success:
            self._save_learned_pipeline(text, safe_commands, description)

        # Construire le resultat
        output_lines: list[str] = []
        for r in execution_results:
            status = "OK" if r.success else "ERREUR"
            output = r.stdout.strip() if r.success else r.stderr.strip()
            # Tronquer les sorties longues
            if len(output) > 200:
                output = output[:200] + "..."
            output_lines.append(f"[{status}] {r.command}: {output}")

        # Log dans voice_analytics
        self._log_analytics(text, all_success, time.time() - start)

        latency_ms = round((time.time() - start) * 1000, 1)
        result_text = "\n".join(output_lines) if output_lines else description

        return {
            "success": any_success,
            "method": "conversational_ai",
            "result": result_text[:500],
            "confidence": 0.6 if all_success else 0.4,
            "module": "voice_conversational",
            "commands": safe_commands,
            "description": description,
            "blocked_commands": blocked,
            "execution_results": [
                {
                    "command": r.command,
                    "success": r.success,
                    "output": (r.stdout if r.success else r.stderr)[:200],
                    "duration_ms": r.duration_ms,
                }
                for r in execution_results
            ],
            "latency_ms": latency_ms,
        }

    # ----------------------------------------------------------------
    # Communication avec le cluster IA
    # ----------------------------------------------------------------

    def _get_ai_plan(self, text: str) -> dict[str, Any] | None:
        """Obtient un plan d'execution depuis le cluster IA (M1 puis OL1).

        Essaie M1 (LM Studio) en priorite, puis OL1 (Ollama) en fallback.
        """
        # Tentative M1 — LM Studio
        plan = self._query_m1(text)
        if plan:
            return plan

        # Fallback OL1 — Ollama
        plan = self._query_ol1(text)
        if plan:
            return plan

        return None

    def _query_m1(self, text: str) -> dict[str, Any] | None:
        """Interroge M1 (LM Studio) pour obtenir un plan d'execution."""
        self._stats["m1_calls"] += 1
        payload = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "max_tokens": 500,
            "temperature": 0.3,
        }

        try:
            req = urllib.request.Request(
                M1_ENDPOINT,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=M1_TIMEOUT) as resp:
                data = json.loads(resp.read())
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                plan = self._parse_ai_response(content)
                if plan:
                    self._stats["m1_successes"] += 1
                    logger.info("Plan obtenu via M1: %s", plan.get("description", ""))
                return plan
        except Exception as exc:
            logger.debug("M1 indisponible: %s", exc)
            return None

    def _query_ol1(self, text: str) -> dict[str, Any] | None:
        """Interroge OL1 (Ollama) pour obtenir un plan d'execution."""
        self._stats["ol1_calls"] += 1
        payload = {
            "model": OL1_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "stream": False,
        }

        try:
            req = urllib.request.Request(
                OL1_ENDPOINT,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=OL1_TIMEOUT) as resp:
                data = json.loads(resp.read())
                content = data.get("message", {}).get("content", "")
                plan = self._parse_ai_response(content)
                if plan:
                    self._stats["ol1_successes"] += 1
                    logger.info("Plan obtenu via OL1: %s", plan.get("description", ""))
                return plan
        except Exception as exc:
            logger.debug("OL1 indisponible: %s", exc)
            return None

    def _parse_ai_response(self, content: str) -> dict[str, Any] | None:
        """Parse la reponse IA et en extrait le JSON {commands, description}.

        Gere les cas ou l'IA entoure le JSON de markdown ou de texte superflu.
        """
        if not content:
            return None

        # Nettoyer les blocs markdown ```json ... ```
        content = content.strip()
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        else:
            # Chercher le premier objet JSON dans la reponse
            brace_match = re.search(r"\{.*\}", content, re.DOTALL)
            if brace_match:
                content = brace_match.group(0)

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            self._stats["parse_errors"] += 1
            logger.warning("Impossible de parser la reponse IA: %s", content[:200])
            return None

        # Valider la structure attendue
        if not isinstance(data, dict):
            self._stats["parse_errors"] += 1
            return None

        commands = data.get("commands", [])
        if not isinstance(commands, list) or not commands:
            self._stats["parse_errors"] += 1
            return None

        # S'assurer que toutes les commandes sont des strings
        commands = [str(c) for c in commands if c]
        if not commands:
            return None

        return {
            "commands": commands,
            "description": str(data.get("description", "Plan IA")),
        }

    # ----------------------------------------------------------------
    # Execution du plan
    # ----------------------------------------------------------------

    def _execute_plan(self, commands: list[str]) -> list[CommandResult]:
        """Execute une liste de commandes bash avec timeout individuel et global."""
        results: list[CommandResult] = []
        plan_start = time.time()

        for cmd in commands:
            # Verifier le timeout global
            elapsed = time.time() - plan_start
            if elapsed >= TOTAL_TIMEOUT:
                logger.warning(
                    "Timeout global atteint (%.1fs >= %ds), arret du plan",
                    elapsed,
                    TOTAL_TIMEOUT,
                )
                # Ajouter les commandes restantes comme echouees
                remaining_idx = commands.index(cmd)
                for remaining_cmd in commands[remaining_idx:]:
                    results.append(
                        CommandResult(
                            command=remaining_cmd,
                            returncode=-1,
                            stdout="",
                            stderr="Timeout global atteint",
                            duration_ms=0,
                            success=False,
                        )
                    )
                break

            # Executer la commande individuelle
            result = self._execute_single_command(cmd)
            results.append(result)

            if result.success:
                self._stats["commands_executed"] += 1
            else:
                self._stats["commands_failed"] += 1

        return results

    def _execute_single_command(self, cmd: str) -> CommandResult:
        """Execute une seule commande bash avec timeout."""
        cmd_start = time.time()
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=CMD_TIMEOUT,
                cwd=os.path.expanduser("~"),
            )
            duration_ms = round((time.time() - cmd_start) * 1000, 1)
            success = proc.returncode == 0

            if success:
                logger.info("Commande OK: %s (%.1fms)", cmd, duration_ms)
            else:
                logger.warning(
                    "Commande echouee (code %d): %s — %s",
                    proc.returncode,
                    cmd,
                    proc.stderr[:100],
                )

            return CommandResult(
                command=cmd,
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_ms=duration_ms,
                success=success,
            )
        except subprocess.TimeoutExpired:
            duration_ms = round((time.time() - cmd_start) * 1000, 1)
            logger.warning("Timeout commande (%ds): %s", CMD_TIMEOUT, cmd)
            return CommandResult(
                command=cmd,
                returncode=-1,
                stdout="",
                stderr=f"Timeout apres {CMD_TIMEOUT}s",
                duration_ms=duration_ms,
                success=False,
            )
        except Exception as exc:
            duration_ms = round((time.time() - cmd_start) * 1000, 1)
            logger.error("Erreur execution: %s — %s", cmd, exc)
            return CommandResult(
                command=cmd,
                returncode=-1,
                stdout="",
                stderr=str(exc),
                duration_ms=duration_ms,
                success=False,
            )

    # ----------------------------------------------------------------
    # Sauvegarde du pipeline appris
    # ----------------------------------------------------------------

    def _save_learned_pipeline(
        self, trigger_text: str, commands: list[str], description: str
    ) -> None:
        """Sauvegarde le pipeline appris dans skills.json via le module skills."""
        try:
            from src.skills import Skill, SkillStep, add_skill

            # Creer les etapes du pipeline
            steps: list[SkillStep] = []
            for cmd in commands:
                steps.append(
                    SkillStep(
                        tool="bash_run",
                        args={"command": cmd},
                        description=cmd,
                        wait_for_result=True,
                    )
                )

            # Creer le skill avec le trigger vocal
            skill_name = f"auto_{trigger_text[:40].replace(' ', '_').lower()}"
            # Nettoyer le nom (garder uniquement alphanum et underscore)
            skill_name = re.sub(r"[^a-z0-9_]", "", skill_name)

            skill = Skill(
                name=skill_name,
                description=f"[Auto-appris] {description}",
                triggers=[trigger_text.lower().strip()],
                steps=steps,
                category="conversational_auto",
                created_at=time.time(),
                usage_count=1,
                last_used=time.time(),
                success_rate=1.0,
                confirm=False,
            )

            add_skill(skill)
            self._stats["skills_saved"] += 1
            logger.info(
                "Pipeline sauvegarde: '%s' (%d commandes)", skill_name, len(commands)
            )
        except Exception as exc:
            logger.error("Erreur sauvegarde pipeline: %s", exc)

    # ----------------------------------------------------------------
    # Logging analytics
    # ----------------------------------------------------------------

    def _log_analytics(self, text: str, success: bool, duration: float) -> None:
        """Log dans la table voice_analytics pour le suivi."""
        try:
            from src.database import get_connection

            conn = get_connection()
            conn.execute(
                """INSERT INTO voice_analytics
                (timestamp, stage, text, confidence, method, latency_ms, success)
                VALUES (?, 'conversational', ?, ?, 'conversational_ai', ?, ?)""",
                (
                    time.time(),
                    text[:200],
                    0.6 if success else 0.2,
                    round(duration * 1000, 1),
                    1 if success else 0,
                ),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # Ne jamais bloquer le pipeline vocal

    # ----------------------------------------------------------------
    # Statistiques
    # ----------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Retourne les statistiques du moteur conversationnel.

        Returns:
            dict avec compteurs: total_requests, m1/ol1 calls/successes,
            plans executed/failed, commands executed/failed/blocked, etc.
        """
        stats = dict(self._stats)
        # Calculer des metriques derivees
        total = stats["total_requests"]
        if total > 0:
            stats["success_rate"] = round(
                stats["plans_executed"] / total * 100, 1
            )
            stats["m1_hit_rate"] = round(
                stats["m1_successes"] / max(stats["m1_calls"], 1) * 100, 1
            )
            stats["ol1_hit_rate"] = round(
                stats["ol1_successes"] / max(stats["ol1_calls"], 1) * 100, 1
            )
        else:
            stats["success_rate"] = 0.0
            stats["m1_hit_rate"] = 0.0
            stats["ol1_hit_rate"] = 0.0
        return stats

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    def _fail_result(
        self, reason: str, start_time: float
    ) -> dict[str, Any]:
        """Construit un resultat d'echec standardise."""
        latency_ms = round((time.time() - start_time) * 1000, 1)
        return {
            "success": False,
            "method": "conversational_ai",
            "result": reason,
            "confidence": 0.0,
            "module": "voice_conversational",
            "commands": [],
            "description": "",
            "blocked_commands": [],
            "execution_results": [],
            "latency_ms": latency_ms,
        }


# ============================================================================
# Instance globale (singleton pour le routeur)
# ============================================================================

_engine: ConversationalVoiceEngine | None = None


def get_engine() -> ConversationalVoiceEngine:
    """Retourne l'instance singleton du moteur conversationnel."""
    global _engine
    if _engine is None:
        _engine = ConversationalVoiceEngine()
    return _engine


def process_unknown_command(text: str) -> dict[str, Any]:
    """Point d'entree pour le routeur vocal — traite une commande inconnue."""
    return get_engine().process_unknown_command(text)


def get_conversational_stats() -> dict[str, Any]:
    """Retourne les stats du moteur conversationnel (pour le routeur)."""
    return get_engine().get_stats()


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="JARVIS Conversational Voice Engine"
    )
    parser.add_argument("--cmd", help="Commande vocale a interpreter")
    parser.add_argument(
        "--stats", action="store_true", help="Afficher les statistiques"
    )
    args = parser.parse_args()

    if args.stats:
        stats = get_conversational_stats()
        print(json.dumps(stats, indent=2))
    elif args.cmd:
        result = process_unknown_command(args.cmd)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
