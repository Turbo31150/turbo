#!/usr/bin/env python3
"""voice_router.py — Routeur unifie pour le pilotage vocal complet de Linux.

Dispatche chaque commande vocale vers le module le plus adapte:
1. linux_desktop_control — apps, fichiers, systeme, volume, reseau, services
2. voice_mouse_control — deplacement curseur, clics, scroll, drag, grille
3. voice_dictation — dictee, epellation, navigation texte, edition
4. voice_window_manager — fenetres, workspaces, menus, dialogues
5. voice_screen_reader — lecture ecran, OCR, notifications, description IA

Usage:
    python src/voice_router.py --cmd "ouvre firefox"
    python src/voice_router.py --cmd "curseur au centre"
    python src/voice_router.py --cmd "dicte bonjour tout le monde"
    python src/voice_router.py --stats
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time

# Garantir que le dossier racine jarvis est dans le PYTHONPATH
_jarvis_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _jarvis_root not in sys.path:
    sys.path.insert(0, _jarvis_root)


def _import_module(module_name: str):
    """Importe un module par son nom dotte."""
    return importlib.import_module(module_name)


def _try_module(module_name: str, execute_fn_name: str, text: str) -> dict | None:
    """Tente d'executer une commande via un module specifique."""
    try:
        mod = _import_module(module_name)
        execute_fn = getattr(mod, execute_fn_name)
        result = execute_fn(text)
        # Format dict (linux_desktop_control, voice_dictation, voice_window_manager)
        if isinstance(result, dict):
            if result.get("success"):
                # Filtrer les faux positifs (resultat qui contient un message d'erreur)
                res_text = str(result.get("result", "")).lower()
                if any(x in res_text for x in ["non reconnue", "non reconnu", "commande inconnue",
                                                "erreur navigateur", "erreur:", "chrome cdp"]):
                    return None
                result["module"] = module_name
                return result
            return None
        # Format string (voice_mouse_control, voice_screen_reader)
        if isinstance(result, str) and result:
            if any(x in result.lower() for x in ["erreur", "inconnue", "non reconnu", "non reconnue"]):
                return None
            return {"success": True, "method": module_name.split(".")[-1],
                    "result": result, "confidence": 0.8, "module": module_name}
        # None = pas reconnu
    except Exception:
        pass
    return None


# Ordre de priorite des modules — du plus specifique au plus general
MODULES = [
    # Module desktop en premier (couvre le plus de commandes: 305)
    ("src.linux_desktop_control", "execute_voice_command"),
    # Window manager (fenetres, menus, workspaces: 114 commandes)
    ("src.voice_window_manager", "execute_window_command"),
    # Souris (mouvements, clics, grille: 30+ commandes)
    ("src.voice_mouse_control", "execute_mouse_command"),
    # Dictee (frappe texte, edition, alphabet: 94 commandes)
    ("src.voice_dictation", "execute_dictation_command"),
    # Lecteur d'ecran (lecture, OCR, notifications: 12 commandes)
    ("src.voice_screen_reader", "execute_screen_command"),
]


def route_voice_command(text: str) -> dict:
    """Route une commande vocale vers le module le plus adapte.

    Applique les corrections vocales SQL, essaie chaque module par
    ordre de priorite, log dans voice_analytics + action_history.

    Returns:
        {"success": bool, "method": str, "result": str,
         "confidence": float, "module": str, "latency_ms": float}
    """
    start = time.time()
    normalized = text.lower().strip()
    if not normalized:
        return {"success": False, "method": "none", "result": "Commande vide",
                "confidence": 0.0, "module": "none", "latency_ms": 0}

    # Voice aliases: raccourcis vocaux ultra-courts (priorite maximale)
    try:
        from src.voice_aliases import execute_alias
        alias_result = execute_alias(normalized)
        if alias_result:
            alias_result["latency_ms"] = round((time.time() - start) * 1000, 1)
            _log_voice_analytics(normalized, alias_result)
            _log_action_history(normalized, alias_result)
            return alias_result
    except Exception:
        pass  # Fallback vers le routage normal si les aliases echouent

    # Appliquer les corrections vocales du cache SQL
    original = normalized
    try:
        from src.db_boot_validator import apply_voice_correction
        normalized = apply_voice_correction(normalized)
        if normalized != original:
            text = normalized  # Utiliser le texte corrige pour le dispatch
    except Exception:
        pass

    # Detection multi-intent : si la phrase contient des separateurs
    # ("et", "puis", "apres", "ou", "en meme temps"), router vers
    # le parseur multi-intent AVANT les modules individuels
    try:
        from src.voice_multi_intent import has_multi_intent, multi_intent_parser
        if has_multi_intent(normalized):
            mi_result = multi_intent_parser.process(text)
            if mi_result.get("intent_count", 0) > 1 or mi_result.get("method") == "delayed_scheduled":
                mi_result["latency_ms"] = round((time.time() - start) * 1000, 1)
                _log_voice_analytics(original, mi_result)
                _log_action_history(original, mi_result)
                return mi_result
    except Exception:
        pass  # Fallback vers le routage classique si multi-intent echoue

    # Enrichissement contextuel (commandes ambigues → commandes precises)
    try:
        from src.voice_context_engine import voice_context_engine
        enriched = voice_context_engine.enrich_command(normalized)
        if enriched != normalized:
            text = enriched
            normalized = enriched.lower().strip()
    except Exception:
        pass

    # Heuristique rapide: deviner le module le plus probable
    priority_modules = _guess_priority(normalized)

    # Essayer les modules prioritaires d'abord
    for mod_name, fn_name in priority_modules:
        result = _try_module(mod_name, fn_name, text)
        if result and result.get("confidence", 0) >= 0.5:
            result["latency_ms"] = round((time.time() - start) * 1000, 1)
            if normalized != original:
                result["corrected_from"] = original
            _log_voice_analytics(original, result)
            _log_action_history(original, result)
            return result

    # Fallback: essayer tous les modules
    for mod_name, fn_name in MODULES:
        if (mod_name, fn_name) in priority_modules:
            continue  # Deja essaye
        result = _try_module(mod_name, fn_name, text)
        if result and result.get("confidence", 0) >= 0.5:
            result["latency_ms"] = round((time.time() - start) * 1000, 1)
            if normalized != original:
                result["corrected_from"] = original
            _log_voice_analytics(original, result)
            _log_action_history(original, result)
            return result

    # Context engine: suggestions contextuelles avant le fallback IA
    context_result = _fallback_context_engine(text, original)
    if context_result and context_result.get("success"):
        context_result["latency_ms"] = round((time.time() - start) * 1000, 1)
        if normalized != original:
            context_result["corrected_from"] = original
        _log_voice_analytics(original, context_result)
        _log_action_history(original, context_result)
        return context_result

    # Voice FAQ: reponses instantanees aux questions frequentes
    faq_result = _fallback_faq(normalized)
    if faq_result and faq_result.get("success"):
        faq_result["latency_ms"] = round((time.time() - start) * 1000, 1)
        if normalized != original:
            faq_result["corrected_from"] = original
        _log_voice_analytics(original, faq_result)
        _log_action_history(original, faq_result)
        return faq_result

    # Fallback IA: quand aucun module ne reconnait la commande,
    # envoyer a l'IA locale pour interpretation ou reponse conversationnelle
    ai_result = _fallback_ia(text, original)
    if ai_result and ai_result.get("success"):
        ai_result["latency_ms"] = round((time.time() - start) * 1000, 1)
        _log_voice_analytics(original, ai_result)
        _log_action_history(original, ai_result)
        return ai_result

    # Dernier fallback: moteur conversationnel IA (genere et execute un plan bash)
    conv_result = _fallback_conversational(text)
    if conv_result and conv_result.get("success"):
        conv_result["latency_ms"] = round((time.time() - start) * 1000, 1)
        if normalized != original:
            conv_result["corrected_from"] = original
        _log_voice_analytics(original, conv_result)
        _log_action_history(original, conv_result)
        return conv_result

    latency = round((time.time() - start) * 1000, 1)
    fail_result = {"success": False, "method": "unknown",
                   "result": f"Commande non reconnue: {text}",
                   "confidence": 0.0, "module": "none", "latency_ms": latency}
    _log_voice_analytics(original, fail_result)
    _log_action_history(original, fail_result)
    return fail_result


def _fallback_faq(text: str) -> dict | None:
    """Fallback FAQ: reponses instantanees aux questions frequentes."""
    try:
        from src.voice_faq import find_faq_answer
        return find_faq_answer(text)
    except Exception:
        return None


def _fallback_ia(text: str, original: str) -> dict | None:
    """Fallback IA: envoie a qwen3-8b pour interpreter ou repondre."""
    import urllib.request  # Import lazy — uniquement si le fallback IA est atteint

    # Construire le prompt avec les categories de commandes disponibles
    prompt = (
        f"/nothink Tu es JARVIS, assistant vocal Linux. "
        f"L'utilisateur dit: \"{text}\"\n"
        f"Reponds en une phrase courte (max 50 mots). "
        f"Si c'est une question, reponds. "
        f"Si c'est une commande que tu ne peux pas executer, dis-le."
    )

    # Ollama d'abord (qwen3:1.7b ultra-rapide), puis LM Studio en fallback
    endpoints = [
        ("http://127.0.0.1:11434/api/generate", {
            "model": "qwen3:1.7b", "prompt": prompt,
            "stream": False, "think": False,
            "options": {"num_predict": 150},
        }, lambda d: d.get("response", "")),
        ("http://127.0.0.1:1234/v1/chat/completions", {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 150, "temperature": 0.5,
        }, lambda d: d.get("choices", [{}])[0].get("message", {}).get("content", "")),
    ]

    for url, payload, extract_fn in endpoints:
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                answer = extract_fn(data)
                if answer and len(answer.strip()) > 3:
                    return {
                        "success": True,
                        "method": "ia_fallback",
                        "result": answer.strip()[:300],
                        "confidence": 0.4,
                        "module": "ia_conversationnel",
                    }
        except Exception:
            continue

    return None


def _fallback_context_engine(text: str, original: str) -> dict | None:
    """Fallback contextuel: consulte le context engine pour des suggestions."""
    try:
        from src.voice_context_engine import voice_context_engine

        # Tenter d'enrichir la commande et re-router
        enriched = voice_context_engine.enrich_command(text)
        if enriched != text:
            # Re-essayer avec la commande enrichie
            for mod_name, fn_name in MODULES:
                result = _try_module(mod_name, fn_name, enriched)
                if result and result.get("confidence", 0) >= 0.5:
                    result["enriched_from"] = text
                    result["enriched_to"] = enriched
                    return result

        # Sinon, proposer les suggestions contextuelles
        suggestions = voice_context_engine.get_fallback_suggestions(text, max=3)
        if suggestions:
            suggestion_text = "; ".join(
                f"{s['command']} ({s['reason']})" for s in suggestions
            )
            return {
                "success": True,
                "method": "context_suggestions",
                "result": f"Suggestions : {suggestion_text}",
                "confidence": 0.45,
                "module": "voice_context_engine",
                "suggestions": suggestions,
            }
    except Exception:
        pass
    return None


def _fallback_conversational(text: str) -> dict | None:
    """Dernier fallback: moteur conversationnel IA qui genere et execute un plan bash."""
    try:
        from src.voice_conversational import process_unknown_command
        result = process_unknown_command(text)
        if result and result.get("success"):
            return result
    except Exception:
        pass
    return None


def _log_voice_analytics(text: str, result: dict):
    """Log chaque commande vocale dans voice_analytics pour ameliorer le routeur."""
    try:
        from src.database import get_connection
        conn = get_connection()
        conn.execute("""INSERT INTO voice_analytics
            (timestamp, stage, text, confidence, method, latency_ms, success)
            VALUES (?, 'route', ?, ?, ?, ?, ?)""",
            (time.time(), text[:200], result.get("confidence", 0),
             result.get("method", "unknown"), result.get("latency_ms", 0),
             1 if result.get("success") else 0))
        conn.commit()
        conn.close()
    except Exception:
        pass  # Ne jamais bloquer le pipeline vocal


def _log_action_history(text: str, result: dict):
    """Log chaque commande vocale dans action_history pour le brain learning.

    Sauvegarde: commande texte, module/methode, succes/echec, duree.
    """
    try:
        from src.skills import log_action
        module = result.get("module", "unknown")
        method = result.get("method", "unknown")
        success = bool(result.get("success"))
        latency = result.get("latency_ms", 0)
        # Format: "voice:module:method" pour identifier la source
        action = f"voice:{module.split('.')[-1]}:{method}"
        result_text = f"cmd='{text[:100]}' latency={latency}ms"
        log_action(action, result_text, success)
    except Exception:
        pass  # Ne jamais bloquer le pipeline vocal


def _guess_priority(text: str) -> list[tuple[str, str]]:
    """Devine le module le plus probable pour accelerer le dispatch."""
    # Mots-cles par module
    mouse_words = {"curseur", "clic", "souris", "scroll", "grille", "glisse",
                   "pixel", "double clic", "clic droit", "maintiens", "relache"}
    dictation_words = {"dicte", "epelle", "lettre", "alpha", "bravo", "mot suivant",
                       "mot precedent", "selectionne", "gras", "italique", "souligne",
                       "arobase", "underscore", "majuscule", "minuscule", "nouvelle ligne"}
    window_words = {"fenetre", "workspace", "menu", "dialogue", "cote a cote",
                    "toujours devant", "snap", "quart", "fleche", "champ suivant",
                    "plein ecran", "restaure", "mosaique", "empile", "echange les",
                    "permute", "swap", "minimise tout", "opacite", "transparent",
                    "grille", "layout"}
    screen_words = {"lis le titre", "quelle application", "decris l'ecran",
                    "notifications", "info fenetre", "zoom ecran", "ocr",
                    "qu'est-ce que je vois", "lis la selection", "contraste",
                    "texte plus gros", "texte plus petit", "couleur pixel",
                    "pipette", "resume ecran"}
    # Mots-cles qui pointent directement vers desktop_control (JARVIS interne, reseau, GPU, trading, spotify)
    desktop_priority_words = {"cluster", "service", "vram", "gpu", "temperature",
                              "ping", "wifi", "port", "processus", "top cpu",
                              "top ram", "vitesse", "speed", "batterie", "swap",
                              "charge", "firewall", "dns", "ecran", "capteur",
                              "sensor", "ip publique", "trading", "scan", "position",
                              "signal", "portefeuille", "spotify", "chanson", "shuffle",
                              "repetition", "workflow", "n8n", "resume systeme",
                              "diagnostic", "kernel", "hostname", "crontab"}

    priority = []

    if any(w in text for w in mouse_words):
        priority.append(("src.voice_mouse_control", "execute_mouse_command"))
    if any(w in text for w in dictation_words):
        priority.append(("src.voice_dictation", "execute_dictation_command"))
    if any(w in text for w in window_words):
        priority.append(("src.voice_window_manager", "execute_window_command"))
    if any(w in text for w in screen_words):
        priority.append(("src.voice_screen_reader", "execute_screen_command"))
    if any(w in text for w in desktop_priority_words):
        priority.append(("src.linux_desktop_control", "execute_voice_command"))

    # Desktop control en dernier resort (tres large)
    if not priority:
        priority.append(("src.linux_desktop_control", "execute_voice_command"))

    return priority


def get_all_commands() -> dict[str, list[str]]:
    """Retourne toutes les commandes disponibles par module."""
    all_cmds = {}
    module_names = {
        "src.linux_desktop_control": "Desktop",
        "src.voice_mouse_control": "Souris",
        "src.voice_dictation": "Dictee",
        "src.voice_window_manager": "Fenetres",
        "src.voice_screen_reader": "Ecran",
    }
    for mod_name, _ in MODULES:
        try:
            mod = _import_module(mod_name)
            cmds = getattr(mod, "VOICE_COMMANDS", {})
            label = module_names.get(mod_name, mod_name)
            # Compter les triggers (pas les commandes internes)
            triggers = []
            for key, val in cmds.items():
                if isinstance(val, dict) and "patterns" in val:
                    # Format screen_reader: dict avec patterns list
                    triggers.extend(val["patterns"])
                else:
                    triggers.append(key)
            all_cmds[label] = sorted(triggers)
        except Exception as e:
            all_cmds[module_names.get(mod_name, mod_name)] = [f"ERREUR: {e}"]
    return all_cmds


def print_stats():
    """Affiche les statistiques de tous les modules."""
    total = 0
    all_cmds = get_all_commands()
    print("=" * 60)
    print("JARVIS VOICE ROUTER — Statistiques")
    print("=" * 60)
    for label, cmds in all_cmds.items():
        count = len(cmds)
        total += count
        print(f"  {label:20s} : {count:4d} commandes")
    print("-" * 60)
    print(f"  {'TOTAL':20s} : {total:4d} commandes vocales")
    print("=" * 60)


# ===========================================================================
# CLI
# ===========================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JARVIS Voice Router")
    parser.add_argument("--cmd", help="Commande vocale a executer")
    parser.add_argument("--stats", action="store_true", help="Statistiques des modules")
    parser.add_argument("--list", action="store_true", help="Lister toutes les commandes")
    parser.add_argument("--interactive", action="store_true", help="Mode interactif")
    args = parser.parse_args()

    if args.stats:
        print_stats()

    elif args.list:
        all_cmds = get_all_commands()
        for label, cmds in all_cmds.items():
            print(f"\n{'=' * 40}")
            print(f" {label} ({len(cmds)} commandes)")
            print(f"{'=' * 40}")
            for c in cmds:
                print(f"  {c}")
        total = sum(len(c) for c in all_cmds.values())
        print(f"\nTotal: {total} commandes vocales")

    elif args.cmd:
        result = route_voice_command(args.cmd)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.interactive:
        print("JARVIS Voice Router — Mode interactif")
        print("Tapez vos commandes (Ctrl+C pour quitter)\n")
        while True:
            try:
                cmd = input("jarvis> ").strip()
                if not cmd:
                    continue
                if cmd in ("quit", "exit", "q"):
                    break
                result = route_voice_command(cmd)
                status = "OK" if result["success"] else "??"
                print(f"  [{status}] {result['module'].split('.')[-1]:25s} → "
                      f"{result['method']:30s} | {result['result'][:80]}")
                print(f"  (confiance: {result['confidence']:.1f}, latence: {result['latency_ms']}ms)\n")
            except (KeyboardInterrupt, EOFError):
                print("\nAu revoir!")
                break

    else:
        parser.print_help()
