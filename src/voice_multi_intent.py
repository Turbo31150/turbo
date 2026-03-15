#!/usr/bin/env python3
"""voice_multi_intent.py — Parseur multi-intent pour commandes vocales composees.

Une seule phrase peut declencher plusieurs actions via des separateurs
naturels : "et", "puis", "ou", "apres", "en meme temps".

Exemples :
    "ouvre firefox et spotify"
    "fais un backup puis mets a jour"
    "dans 5 minutes ferme tout"
    "verifie le cluster et les GPU en meme temps"

Usage:
    python src/voice_multi_intent.py --cmd "ouvre firefox et spotify"
    python src/voice_multi_intent.py --cmd "fais un backup puis mets a jour"
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable

# Garantir que le dossier racine jarvis est dans le PYTHONPATH
_jarvis_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _jarvis_root not in sys.path:
    sys.path.insert(0, _jarvis_root)

logger = logging.getLogger("jarvis.multi_intent")

__all__ = [
    "MultiIntentParser",
    "Intent",
    "IntentMode",
    "has_multi_intent",
]


# ---------------------------------------------------------------------------
# Modeles de donnees
# ---------------------------------------------------------------------------

class IntentMode(str, Enum):
    """Mode d'execution entre deux intentions."""
    AND = "and"              # Parallele implicite ("et")
    THEN = "then"            # Sequentiel ("puis")
    OR = "or"                # Premier qui reussit ("ou")
    DELAY_THEN = "delay"     # Avec delai ("apres", "dans X minutes")
    PARALLEL = "parallel"    # Parallele explicite ("en meme temps")


@dataclass
class Intent:
    """Representation d'une intention unique extraite d'une commande composee."""
    text: str                              # Texte brut de la sous-commande
    mode: IntentMode = IntentMode.AND      # Mode de liaison avec l'intent suivant
    delay_seconds: float = 0.0             # Delai avant execution (DELAY_THEN)
    resolved: bool = False                 # True si la reference a ete resolue
    original_ref: str = ""                 # Texte original avant resolution de ref
    result: dict[str, Any] = field(default_factory=dict)  # Resultat apres execution

    def to_dict(self) -> dict[str, Any]:
        """Serialise l'intent en dict."""
        d = asdict(self)
        d["mode"] = self.mode.value
        return d


# ---------------------------------------------------------------------------
# Separateurs et patterns
# ---------------------------------------------------------------------------

# Ordre important : les patterns les plus longs en premier pour eviter
# les matchs partiels ("en meme temps" avant "et")
_SEPARATOR_PATTERNS: list[tuple[str, IntentMode]] = [
    (r"\ben\s+m[eê]me\s+temps\b", IntentMode.PARALLEL),
    (r"\bsimultan[ée]ment\b", IntentMode.PARALLEL),
    (r"\bapr[eè]s\b", IntentMode.DELAY_THEN),
    (r"\bpuis\b", IntentMode.THEN),
    (r"\bensuite\b", IntentMode.THEN),
    (r"\bet\s+apr[eè]s\b", IntentMode.THEN),
    (r"\bou\s+bien\b", IntentMode.OR),
    (r"\bou\s+sinon\b", IntentMode.OR),
    (r"\bou\b", IntentMode.OR),
    (r"\bet\b", IntentMode.AND),
    # Virgule comme separateur uniquement si suivie d'un verbe
    (r",\s*(?=(?:ouvre|lance|ferme|fais|verifie|montre|lis|mets|active|"
     r"desactive|redemarre|arrete|cherche|copie|deplace|supprime|"
     r"joue|pause|stop|resume|augmente|baisse|coupe))", IntentMode.THEN),
]

# Pattern pour detecter un delai dans le texte
_DELAY_PATTERN = re.compile(
    r"(?:dans|apr[eè]s|attends?)\s+"
    r"(\d+(?:[.,]\d+)?)\s*"
    r"(secondes?|sec|s|minutes?|min|m|heures?|h)",
    re.IGNORECASE,
)

# Mots de reference qui renvoient a la commande precedente
_REFERENCE_WORDS: dict[str, str] = {
    "ça": "",            # "fais ça aussi" → repete la commande precedente
    "ca": "",
    "aussi": "",         # "aussi" → meme action
    "pareil": "",        # "pareil" → meme action
    "la même chose": "",  # "la meme chose" → meme action
    "idem": "",          # "idem" → meme action
    "le même": "",       # "le meme" → meme action
    "la meme chose": "",
    "le meme": "",
}


# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------

def has_multi_intent(text: str) -> bool:
    """Detection rapide : le texte contient-il des separateurs multi-intent ?

    Utilise par voice_router pour decider si on passe par MultiIntentParser.
    """
    normalized = text.lower().strip()
    # Exclure les cas triviaux (commande trop courte)
    if len(normalized) < 8:
        return False
    for pattern, _ in _SEPARATOR_PATTERNS:
        if re.search(pattern, normalized):
            return True
    # Verifier aussi les delais
    if _DELAY_PATTERN.search(normalized):
        return True
    return False


def _extract_delay(text: str) -> tuple[str, float]:
    """Extrait un delai du texte et retourne (texte_nettoye, delai_secondes).

    Exemples :
        "dans 5 minutes ferme tout" -> ("ferme tout", 300.0)
        "apres 30 secondes redemarre" -> ("redemarre", 30.0)
    """
    match = _DELAY_PATTERN.search(text)
    if not match:
        return text, 0.0

    value = float(match.group(1).replace(",", "."))
    unit = match.group(2).lower()

    # Conversion en secondes
    multipliers: dict[str, float] = {
        "s": 1.0, "sec": 1.0, "seconde": 1.0, "secondes": 1.0,
        "m": 60.0, "min": 60.0, "minute": 60.0, "minutes": 60.0,
        "h": 3600.0, "heure": 3600.0, "heures": 3600.0,
    }
    seconds = value * multipliers.get(unit, 1.0)

    # Retirer le pattern de delai du texte
    cleaned = text[:match.start()] + text[match.end():]
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, seconds


def _resolve_references(intents: list[Intent]) -> list[Intent]:
    """Resout les references inter-commandes ("ca", "aussi", "pareil").

    Si une sous-commande contient un mot de reference, on la remplace
    par le texte de la commande precedente.
    """
    for i, intent in enumerate(intents):
        if i == 0:
            continue
        lower = intent.text.lower().strip()
        for ref_word in _REFERENCE_WORDS:
            if ref_word in lower:
                # Remplacer la reference par le texte de l'intent precedent
                prev_text = intents[i - 1].text
                intent.original_ref = intent.text
                intent.text = prev_text
                intent.resolved = True
                break
    return intents


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------

class MultiIntentParser:
    """Parseur multi-intent pour commandes vocales composees.

    Parse une phrase contenant des separateurs ("et", "puis", "ou", etc.)
    en une liste d'intentions executables, puis les execute via le voice_router.
    """

    def __init__(self, router_fn: Callable[[str], dict[str, Any]] | None = None):
        """Initialise le parseur.

        Args:
            router_fn: Fonction de routage pour chaque sous-commande.
                       Par defaut, utilise voice_router.route_voice_command.
        """
        self._router_fn = router_fn
        self._last_command: str = ""  # Derniere commande executee (pour references)

    @property
    def router_fn(self) -> Callable[[str], dict[str, Any]]:
        """Retourne la fonction de routage, avec import lazy si necessaire."""
        if self._router_fn is None:
            from src.voice_router import route_voice_command
            self._router_fn = route_voice_command
        return self._router_fn

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse(self, text: str) -> list[Intent]:
        """Parse une commande composee en liste d'intentions.

        Decoupe le texte par les separateurs naturels, detecte les delais,
        et resout les references inter-commandes.

        Args:
            text: Commande vocale brute (ex: "ouvre firefox et spotify")

        Returns:
            Liste d'Intent avec mode, texte, et delai eventuels.
        """
        normalized = text.strip()
        if not normalized:
            return []

        # Detecter un delai global en debut de phrase
        global_cleaned, global_delay = _extract_delay(normalized)
        if global_delay > 0:
            # La phrase entiere est retardee
            # Parser le reste normalement
            sub_intents = self._split_by_separators(global_cleaned)
            if sub_intents:
                sub_intents[0].delay_seconds = global_delay
                sub_intents[0].mode = IntentMode.DELAY_THEN
            return _resolve_references(sub_intents)

        # Decoupage par separateurs
        intents = self._split_by_separators(normalized)

        # Resolution des references ("ca", "aussi", "pareil")
        intents = _resolve_references(intents)

        return intents

    def _split_by_separators(self, text: str) -> list[Intent]:
        """Decoupe le texte en segments selon les separateurs detectes.

        Algorithme : on scanne le texte de gauche a droite, on trouve le
        premier separateur, on decoupe, et on recurse sur le reste.
        Les modificateurs de phrase ("en meme temps", "simultanement") en fin
        de texte changent le mode de tous les intents.
        """
        lower_text = text.lower()

        # Phase 1 : detecter les modificateurs de phrase en fin de texte
        # "en meme temps" / "simultanement" a la fin → tout est PARALLEL
        phrase_mode: IntentMode | None = None
        cleaned_text = text
        for pattern, mode in _SEPARATOR_PATTERNS[:2]:  # PARALLEL patterns only
            match = re.search(pattern + r"\s*$", lower_text)
            if match:
                phrase_mode = mode
                cleaned_text = text[:match.start()].strip()
                lower_text = cleaned_text.lower()
                break

        # Phase 2 : trouver le premier separateur (le plus a gauche)
        best_match: tuple[int, int, IntentMode] | None = None
        best_start = len(cleaned_text)

        for pattern, mode in _SEPARATOR_PATTERNS:
            match = re.search(pattern, lower_text)
            if match and match.start() < best_start:
                # Verifier qu'il y a du contenu avant ET apres le separateur
                before = cleaned_text[:match.start()].strip()
                after = cleaned_text[match.end():].strip()
                if before and after:
                    best_match = (match.start(), match.end(), mode)
                    best_start = match.start()

        if best_match is None:
            # Pas de separateur : une seule intention
            final = cleaned_text.strip()
            if not final:
                return []
            # Verifier s'il y a un delai dans ce segment
            final, delay = _extract_delay(final)
            if not final:
                return []
            intent = Intent(text=final, delay_seconds=delay)
            if delay > 0:
                intent.mode = IntentMode.DELAY_THEN
            elif phrase_mode:
                intent.mode = phrase_mode
            return [intent]

        start, end, mode = best_match
        before = cleaned_text[:start].strip()
        after = cleaned_text[end:].strip()

        # Si un modificateur de phrase a ete detecte, forcer le mode
        effective_mode = phrase_mode if phrase_mode else mode

        # Extraire le delai pour la partie avant
        before_cleaned, before_delay = _extract_delay(before)

        # Creer l'intent pour la partie avant
        intent_before = Intent(
            text=before_cleaned,
            mode=effective_mode,  # Le mode s'applique a la liaison VERS le suivant
            delay_seconds=before_delay,
        )
        if before_delay > 0 and effective_mode not in (IntentMode.DELAY_THEN,):
            intent_before.mode = IntentMode.DELAY_THEN

        # Parser recursivement la partie apres
        intents_after = self._split_by_separators(after)

        # Appliquer le modificateur de phrase a tous les intents
        if phrase_mode:
            for intent in intents_after:
                intent.mode = phrase_mode

        result = [intent_before] + intents_after
        return result

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, intents: list[Intent]) -> list[dict[str, Any]]:
        """Execute une liste d'intentions selon leurs modes.

        - AND / PARALLEL : execution en parallele via threads
        - THEN : execution sequentielle, stop si erreur
        - OR : premier qui reussit
        - DELAY_THEN : planifie via threading.Timer

        Args:
            intents: Liste d'Intent parsees

        Returns:
            Liste de resultats (un dict par intent)
        """
        if not intents:
            return []

        results: list[dict[str, Any]] = []

        # Grouper les intents par mode pour optimiser l'execution
        groups = self._group_intents(intents)

        for group_mode, group_intents in groups:
            if group_mode in (IntentMode.AND, IntentMode.PARALLEL):
                group_results = self._execute_parallel(group_intents)
                results.extend(group_results)
            elif group_mode == IntentMode.THEN:
                group_results = self._execute_sequential(group_intents)
                results.extend(group_results)
            elif group_mode == IntentMode.OR:
                group_results = self._execute_or(group_intents)
                results.extend(group_results)
            elif group_mode == IntentMode.DELAY_THEN:
                group_results = self._execute_delayed(group_intents)
                results.extend(group_results)

        return results

    def _group_intents(
        self, intents: list[Intent]
    ) -> list[tuple[IntentMode, list[Intent]]]:
        """Regroupe les intents consecutifs partageant le meme mode.

        Ex: [A(and), B(and), C(then), D(then)] -> [(and, [A,B]), (then, [C,D])]
        Le dernier intent d'un groupe herite du mode du groupe.
        """
        if not intents:
            return []

        groups: list[tuple[IntentMode, list[Intent]]] = []
        current_mode = intents[0].mode
        current_group: list[Intent] = [intents[0]]

        for intent in intents[1:]:
            # Le mode du groupe est defini par le separateur AVANT l'intent
            # (c'est-a-dire le mode du precedent)
            prev_mode = current_group[-1].mode
            if prev_mode == intent.mode or (
                prev_mode in (IntentMode.AND, IntentMode.PARALLEL)
                and intent.mode in (IntentMode.AND, IntentMode.PARALLEL)
            ):
                current_group.append(intent)
            else:
                groups.append((current_mode, current_group))
                current_mode = intent.mode
                current_group = [intent]

        groups.append((current_mode, current_group))
        return groups

    def _execute_single(self, intent: Intent) -> dict[str, Any]:
        """Execute une seule intention via le routeur."""
        start = time.time()
        try:
            result = self.router_fn(intent.text)
            result["intent_text"] = intent.text
            result["intent_mode"] = intent.mode.value
            if intent.resolved:
                result["resolved_from"] = intent.original_ref
            intent.result = result
            self._last_command = intent.text
            return result
        except Exception as e:
            error_result = {
                "success": False,
                "method": "multi_intent_error",
                "result": f"Erreur: {e}",
                "confidence": 0.0,
                "module": "voice_multi_intent",
                "intent_text": intent.text,
                "intent_mode": intent.mode.value,
                "latency_ms": round((time.time() - start) * 1000, 1),
            }
            intent.result = error_result
            return error_result

    def _execute_parallel(self, intents: list[Intent]) -> list[dict[str, Any]]:
        """Execute les intentions en parallele via threading."""
        results: list[dict[str, Any]] = [{}] * len(intents)
        threads: list[threading.Thread] = []

        def _run(idx: int, intent: Intent) -> None:
            results[idx] = self._execute_single(intent)

        for i, intent in enumerate(intents):
            t = threading.Thread(target=_run, args=(i, intent), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30.0)

        return results

    def _execute_sequential(self, intents: list[Intent]) -> list[dict[str, Any]]:
        """Execute les intentions une par une, stop si erreur."""
        results: list[dict[str, Any]] = []
        for intent in intents:
            result = self._execute_single(intent)
            results.append(result)
            if not result.get("success", False):
                # Stop sur erreur en mode sequentiel
                logger.warning(
                    "Arret sequentiel: echec sur '%s'", intent.text
                )
                break
        return results

    def _execute_or(self, intents: list[Intent]) -> list[dict[str, Any]]:
        """Execute les intentions une par une, retourne la premiere qui reussit."""
        for intent in intents:
            result = self._execute_single(intent)
            if result.get("success", False):
                return [result]
        # Aucune n'a reussi, retourner le dernier resultat
        if intents:
            return [self._execute_single(intents[-1])]
        return []

    def _execute_delayed(self, intents: list[Intent]) -> list[dict[str, Any]]:
        """Execute les intentions avec delai via threading.Timer.

        Pour les commandes interactives, on attend la fin du timer.
        """
        results: list[dict[str, Any]] = []
        for intent in intents:
            delay = intent.delay_seconds
            if delay > 0:
                # Planifier l'execution
                result_container: list[dict[str, Any]] = []
                event = threading.Event()

                def _delayed_run(i: Intent = intent) -> None:
                    r = self._execute_single(i)
                    r["delayed_by_seconds"] = delay
                    result_container.append(r)
                    event.set()

                timer = threading.Timer(delay, _delayed_run)
                timer.daemon = True
                timer.start()

                # Attendre la fin (max 10 minutes)
                max_wait = min(delay + 10.0, 600.0)
                event.wait(timeout=max_wait)

                if result_container:
                    results.extend(result_container)
                else:
                    results.append({
                        "success": True,
                        "method": "delayed_scheduled",
                        "result": f"Planifie dans {delay}s: {intent.text}",
                        "confidence": 1.0,
                        "module": "voice_multi_intent",
                        "intent_text": intent.text,
                        "delay_seconds": delay,
                    })
            else:
                results.append(self._execute_single(intent))
        return results

    # ------------------------------------------------------------------
    # Interface unifiee
    # ------------------------------------------------------------------

    def process(self, text: str) -> dict[str, Any]:
        """Parse et execute une commande composee en une seule etape.

        Point d'entree principal pour le voice_router.

        Args:
            text: Commande vocale brute

        Returns:
            Dict avec les resultats de toutes les sous-commandes.
        """
        start = time.time()

        intents = self.parse(text)
        if not intents:
            return {
                "success": False,
                "method": "multi_intent",
                "result": "Aucune intention detectee",
                "confidence": 0.0,
                "module": "voice_multi_intent",
                "intent_count": 0,
                "latency_ms": round((time.time() - start) * 1000, 1),
            }

        # Si une seule intention sans delai, pas besoin du multi-intent
        if len(intents) == 1 and intents[0].delay_seconds == 0:
            result = self._execute_single(intents[0])
            result["latency_ms"] = round((time.time() - start) * 1000, 1)
            return result

        results = self.execute(intents)

        # Calculer le succes global
        successes = sum(1 for r in results if r.get("success", False))
        total = len(results)

        # Resume textuel
        summary_parts: list[str] = []
        for r in results:
            status = "OK" if r.get("success") else "ECHEC"
            cmd = r.get("intent_text", "?")[:50]
            summary_parts.append(f"[{status}] {cmd}")
        summary = " | ".join(summary_parts)

        latency = round((time.time() - start) * 1000, 1)

        return {
            "success": successes > 0,
            "method": "multi_intent",
            "result": f"{successes}/{total} intentions reussies: {summary}",
            "confidence": round(successes / total, 2) if total > 0 else 0.0,
            "module": "voice_multi_intent",
            "intent_count": total,
            "intents": [i.to_dict() for i in intents],
            "results": results,
            "latency_ms": latency,
        }


# ---------------------------------------------------------------------------
# Instance globale (singleton)
# ---------------------------------------------------------------------------

multi_intent_parser = MultiIntentParser()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(
        description="JARVIS Multi-Intent Voice Parser"
    )
    arg_parser.add_argument("--cmd", help="Commande vocale composee a parser/executer")
    arg_parser.add_argument(
        "--parse-only", action="store_true",
        help="Parser seulement, sans executer"
    )
    arg_parser.add_argument(
        "--interactive", action="store_true",
        help="Mode interactif"
    )
    args = arg_parser.parse_args()

    mi = MultiIntentParser()

    if args.cmd:
        if args.parse_only:
            intents = mi.parse(args.cmd)
            print(f"Intents ({len(intents)}):")
            for i, intent in enumerate(intents):
                print(f"  {i+1}. [{intent.mode.value:8s}] "
                      f"delay={intent.delay_seconds}s : \"{intent.text}\"")
                if intent.resolved:
                    print(f"     (resolu depuis: \"{intent.original_ref}\")")
        else:
            result = mi.process(args.cmd)
            print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.interactive:
        print("JARVIS Multi-Intent Parser — Mode interactif")
        print("Tapez vos commandes composees (Ctrl+C pour quitter)\n")
        while True:
            try:
                cmd = input("multi> ").strip()
                if not cmd:
                    continue
                if cmd in ("quit", "exit", "q"):
                    break

                intents = mi.parse(cmd)
                print(f"\n  Intents detectes: {len(intents)}")
                for i, intent in enumerate(intents):
                    print(f"    {i+1}. [{intent.mode.value:8s}] "
                          f"delay={intent.delay_seconds}s : \"{intent.text}\"")
                print()
            except (KeyboardInterrupt, EOFError):
                print("\nAu revoir!")
                break
    else:
        arg_parser.print_help()
