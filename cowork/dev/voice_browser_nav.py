#!/usr/bin/env python3
"""voice_browser_nav.py — Navigation web par commandes vocales.

Interprete des commandes vocales naturelles en francais et les traduit
en actions browser_pilot.py + window_manager.py.

Usage:
    python dev/voice_browser_nav.py --cmd "ouvre google"
    python dev/voice_browser_nav.py --cmd "clique sur suivant"
    python dev/voice_browser_nav.py --cmd "ferme la page"
    python dev/voice_browser_nav.py --cmd "deplace sur l'autre ecran"
    python dev/voice_browser_nav.py --cmd "scroll en bas"
    python dev/voice_browser_nav.py --cmd "lis la page"
    python dev/voice_browser_nav.py --cmd "cherche python tutorial"
    python dev/voice_browser_nav.py --cmd "tape bonjour"
    python dev/voice_browser_nav.py --cmd "appuie sur entree"
    python dev/voice_browser_nav.py --commands     # Liste toutes les commandes
    python dev/voice_browser_nav.py --test         # Test toutes les commandes
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEV = Path(__file__).parent
BROWSER_PILOT = DEV / "browser_pilot.py"
WINDOW_MANAGER = DEV / "window_manager.py"
SMART_LAUNCHER = DEV / "smart_launcher.py"

# ---------------------------------------------------------------------------
# Command patterns: regex → (script, args_builder)
# ---------------------------------------------------------------------------
def run_script(script: Path, args: list) -> dict:
    """Execute un script et retourne le resultat JSON."""
    cmd = [sys.executable, str(script)] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                                env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        output = result.stdout.strip()
        if output:
            try:
                return json.loads(output)
            except:
                return {"output": output[:500]}
        if result.stderr:
            return {"error": result.stderr.strip()[:300]}
        return {"status": "ok"}
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": str(e)}

# Commandes vocales → actions
VOICE_COMMANDS = [
    # --- Navigation ---
    {
        "patterns": [
            r"(?:ouvre|va sur|navigue vers|affiche)\s+(?:le site\s+)?(.+)",
            r"(?:cherche|recherche|google)\s+(.+)",
        ],
        "action": "navigate",
        "description": "Ouvrir un site ou chercher sur Google",
        "examples": ["ouvre google", "cherche python tutorial", "va sur youtube"],
    },
    {
        "patterns": [r"(?:page\s+)?(?:precedente|retour|back|arriere)"],
        "action": "back",
        "description": "Page precedente",
        "examples": ["retour", "page precedente"],
    },
    {
        "patterns": [r"(?:page\s+)?(?:suivante|forward|avant|avance)"],
        "action": "forward",
        "description": "Page suivante",
        "examples": ["suivant", "page suivante"],
    },
    {
        "patterns": [r"(?:actualise|rafraichis?|reload|refresh)"],
        "action": "refresh",
        "description": "Rafraichir la page",
        "examples": ["rafraichis", "actualise la page"],
    },
    # --- Scroll ---
    {
        "patterns": [
            r"(?:scroll|descend|descends|defiles?)\s*(?:en\s+)?(?:bas|down)",
            r"(?:descend|descends)\s*(?:la page)?",
        ],
        "action": "scroll_down",
        "description": "Scroller vers le bas",
        "examples": ["scroll en bas", "descends"],
    },
    {
        "patterns": [
            r"(?:scroll|monte|remonte|defiles?)\s*(?:en\s+)?(?:haut|up)",
            r"(?:monte|remonte)\s*(?:la page)?",
        ],
        "action": "scroll_up",
        "description": "Scroller vers le haut",
        "examples": ["scroll en haut", "remonte"],
    },
    {
        "patterns": [r"(?:tout en haut|debut|top)"],
        "action": "scroll_top",
        "description": "Aller tout en haut",
        "examples": ["tout en haut", "debut de page"],
    },
    {
        "patterns": [r"(?:tout en bas|fin|bottom|end)"],
        "action": "scroll_bottom",
        "description": "Aller tout en bas",
        "examples": ["tout en bas", "fin de page"],
    },
    # --- Clic ---
    {
        "patterns": [
            r"(?:clique|appuie|clic)\s+(?:sur\s+)?(?:le bouton\s+)?['\"]?(.+?)['\"]?$",
            r"(?:press|click)\s+(.+)",
        ],
        "action": "click_text",
        "description": "Cliquer sur un element par son texte",
        "examples": ["clique sur suivant", "clique sur accepter"],
    },
    # --- Onglets ---
    {
        "patterns": [
            r"(?:ferme|close)\s+(?:la\s+)?(?:page|onglet|tab)",
            r"(?:ferme|close)\s+(?:ca|cet onglet)",
        ],
        "action": "close_tab",
        "description": "Fermer l'onglet courant",
        "examples": ["ferme la page", "close tab"],
    },
    {
        "patterns": [
            r"(?:nouvel?\s+)?(?:onglet|tab)\s*(.*)$",
            r"(?:ouvre\s+un\s+)?(?:nouvel?\s+)?(?:onglet|tab)",
        ],
        "action": "new_tab",
        "description": "Ouvrir un nouvel onglet",
        "examples": ["nouvel onglet", "ouvre un nouvel onglet"],
    },
    {
        "patterns": [r"(?:liste|montre|affiche)\s+(?:les\s+)?(?:onglets|tabs)"],
        "action": "list_tabs",
        "description": "Lister les onglets",
        "examples": ["montre les onglets"],
    },
    # --- Texte ---
    {
        "patterns": [
            r"(?:tape|ecris|saisis?|entre|type)\s+['\"]?(.+?)['\"]?$",
        ],
        "action": "type_text",
        "description": "Taper du texte",
        "examples": ["tape bonjour", "ecris python"],
    },
    {
        "patterns": [
            r"(?:appuie|touche|press)\s+(?:sur\s+)?(?:la touche\s+)?(entree|enter|tab|echap|escape|espace|space|suppr|delete|backspace)",
        ],
        "action": "press_key",
        "description": "Appuyer sur une touche",
        "examples": ["appuie sur entree", "touche tab"],
    },
    # --- Fenetre ---
    {
        "patterns": [
            r"(?:deplace|bouge|mets?|envoie)\s+(?:la?\s+)?(?:fenetre|page|navigateur)?\s*(?:sur|vers)\s+(?:l'?\s*autre\s+)?(?:ecran|moniteur|screen)",
            r"(?:autre\s+ecran|change\s+ecran|switch\s+screen)",
        ],
        "action": "move_other_screen",
        "description": "Deplacer la fenetre sur l'autre ecran",
        "examples": ["deplace sur l'autre ecran", "mets ca sur l'autre ecran"],
    },
    {
        "patterns": [
            r"(?:plein\s+ecran|fullscreen|maximise|maximize)",
        ],
        "action": "maximize",
        "description": "Plein ecran / maximiser",
        "examples": ["plein ecran", "maximise"],
    },
    {
        "patterns": [
            r"(?:minimise|minimize|reduis?|cache)\s*(?:la?\s+)?(?:fenetre)?",
        ],
        "action": "minimize",
        "description": "Minimiser la fenetre",
        "examples": ["minimise", "cache la fenetre"],
    },
    # --- Lecture ---
    {
        "patterns": [
            r"(?:lis|lecture|lire|read)\s+(?:la\s+)?(?:page|contenu|texte)",
            r"(?:qu'est-ce qu'il y a|que dit|c'est quoi)\s+(?:sur\s+)?(?:la\s+)?(?:page|ecran)",
        ],
        "action": "read_page",
        "description": "Lire le contenu de la page",
        "examples": ["lis la page", "lecture du contenu"],
    },
    {
        "patterns": [r"(?:titre|title)\s*(?:de\s+la\s+page)?"],
        "action": "get_title",
        "description": "Titre de la page",
        "examples": ["titre de la page"],
    },
    # --- Lancement ---
    {
        "patterns": [
            r"(?:lance|ouvre|start|demarre)\s+(?:le\s+)?(?:navigateur|browser|chrome|edge)",
        ],
        "action": "start_browser",
        "description": "Lancer le navigateur",
        "examples": ["ouvre le navigateur", "lance chrome"],
    },
]

KEY_MAP = {
    "entree": "enter", "enter": "enter",
    "tab": "tab", "tabulation": "tab",
    "echap": "escape", "escape": "escape",
    "espace": "space", "space": "space",
    "suppr": "delete", "delete": "delete",
    "backspace": "backspace", "retour arriere": "backspace",
}

# ---------------------------------------------------------------------------
# Command interpreter
# ---------------------------------------------------------------------------
def interpret_command(text: str) -> dict:
    """Interprete une commande vocale et retourne l'action a executer."""
    text = text.lower().strip()
    # Remove common filler words
    text = re.sub(r"^(jarvis|s'il te plait|stp|please|hey|ok|bon)\s*,?\s*", "", text)
    text = re.sub(r"\s+(s'il te plait|stp|please)$", "", text)

    for cmd in VOICE_COMMANDS:
        for pattern in cmd["patterns"]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                param = groups[0].strip() if groups else None
                return {
                    "action": cmd["action"],
                    "param": param,
                    "description": cmd["description"],
                    "matched": pattern,
                }

    return {"action": "unknown", "text": text, "error": "Commande non reconnue"}

def execute_action(action: dict) -> dict:
    """Execute une action interpretee."""
    act = action["action"]
    param = action.get("param")
    result = {"action": act}

    if act == "navigate":
        # Determine if it's a URL or search query
        if param:
            if "." in param and " " not in param:
                url = param if param.startswith("http") else f"https://{param}"
            else:
                url = f"https://www.google.com/search?q={param.replace(' ', '+')}"
            r = run_script(BROWSER_PILOT, ["--navigate", url])
            result.update(r)
            result["url"] = url
        else:
            result["error"] = "Pas d'URL specifiee"

    elif act == "back":
        result.update(run_script(BROWSER_PILOT, ["--back"]))

    elif act == "forward":
        result.update(run_script(BROWSER_PILOT, ["--forward"]))

    elif act == "refresh":
        result.update(run_script(BROWSER_PILOT, ["--eval", "location.reload(); 'refreshed'"]))

    elif act == "scroll_down":
        result.update(run_script(BROWSER_PILOT, ["--scroll", "down"]))

    elif act == "scroll_up":
        result.update(run_script(BROWSER_PILOT, ["--scroll", "up"]))

    elif act == "scroll_top":
        result.update(run_script(BROWSER_PILOT, ["--scroll", "top"]))

    elif act == "scroll_bottom":
        result.update(run_script(BROWSER_PILOT, ["--scroll", "bottom"]))

    elif act == "click_text":
        if param:
            result.update(run_script(BROWSER_PILOT, ["--click-text", param]))
        else:
            result["error"] = "Pas de cible specifiee"

    elif act == "close_tab":
        result.update(run_script(BROWSER_PILOT, ["--close-tab"]))

    elif act == "new_tab":
        url = param if param else "about:blank"
        if param and not param.startswith("http"):
            url = f"https://{param}" if "." in param else "about:blank"
        result.update(run_script(BROWSER_PILOT, ["--new-tab", url]))

    elif act == "list_tabs":
        result.update({"tabs": run_script(BROWSER_PILOT, ["--tabs"])})

    elif act == "type_text":
        if param:
            result.update(run_script(BROWSER_PILOT, ["--type", param]))
        else:
            result["error"] = "Pas de texte a taper"

    elif act == "press_key":
        if param:
            key = KEY_MAP.get(param.lower(), param.lower())
            result.update(run_script(BROWSER_PILOT, ["--press", key]))
        else:
            result["error"] = "Pas de touche specifiee"

    elif act == "move_other_screen":
        # Find browser window and move it
        r = run_script(WINDOW_MANAGER, ["--other-screen", "Chrome"])
        if "error" in r:
            r = run_script(WINDOW_MANAGER, ["--other-screen", "Edge"])
        if "error" in r:
            r = run_script(WINDOW_MANAGER, ["--other-screen", "Comet"])
        result.update(r)

    elif act == "maximize":
        r = run_script(WINDOW_MANAGER, ["--maximize", "Chrome"])
        if "error" in r:
            r = run_script(WINDOW_MANAGER, ["--maximize", "Edge"])
        result.update(r)

    elif act == "minimize":
        r = run_script(WINDOW_MANAGER, ["--minimize", "Chrome"])
        if "error" in r:
            r = run_script(WINDOW_MANAGER, ["--minimize", "Edge"])
        result.update(r)

    elif act == "read_page":
        result.update(run_script(BROWSER_PILOT, ["--text"]))

    elif act == "get_title":
        result.update(run_script(BROWSER_PILOT, ["--title"]))

    elif act == "start_browser":
        result.update(run_script(BROWSER_PILOT, ["--start"]))

    elif act == "unknown":
        result["error"] = f"Commande non reconnue: {action.get('text', '')}"

    return result

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="JARVIS Voice Browser Navigator — Navigation web vocale")
    parser.add_argument("--cmd", type=str, help="Commande vocale a executer")
    parser.add_argument("--interpret", type=str, help="Interpreter sans executer")
    parser.add_argument("--commands", action="store_true", help="Lister toutes les commandes")
    parser.add_argument("--test", action="store_true", help="Tester l'interpretation de commandes")
    args = parser.parse_args()

    if args.commands:
        cmds = []
        for cmd in VOICE_COMMANDS:
            cmds.append({
                "action": cmd["action"],
                "description": cmd["description"],
                "examples": cmd["examples"],
            })
        print(json.dumps(cmds, indent=2, ensure_ascii=False))
        return

    if args.test:
        test_phrases = [
            "ouvre google", "cherche python tutorial", "page suivante",
            "retour", "scroll en bas", "monte", "tout en haut",
            "clique sur suivant", "ferme la page", "nouvel onglet",
            "tape bonjour", "appuie sur entree", "deplace sur l'autre ecran",
            "plein ecran", "lis la page", "lance le navigateur",
            "jarvis, ouvre youtube s'il te plait",
        ]
        results = []
        ok = 0
        for phrase in test_phrases:
            r = interpret_command(phrase)
            success = r["action"] != "unknown"
            if success:
                ok += 1
            results.append({"phrase": phrase, "action": r["action"], "param": r.get("param"), "ok": success})
        print(json.dumps({"total": len(test_phrases), "ok": ok,
                          "rate": f"{ok/len(test_phrases)*100:.0f}%",
                          "results": results}, indent=2, ensure_ascii=False))
        return

    if args.interpret:
        result = interpret_command(args.interpret)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.cmd:
        # Interpret + execute
        interpretation = interpret_command(args.cmd)
        if interpretation["action"] == "unknown":
            print(json.dumps(interpretation, indent=2, ensure_ascii=False))
            sys.exit(1)
        result = execute_action(interpretation)
        result["interpreted_as"] = interpretation["description"]
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    parser.print_help()

if __name__ == "__main__":
    main()
