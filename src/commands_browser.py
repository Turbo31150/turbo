"""JARVIS Browser Voice Commands — Playwright-powered navigation by voice.

These commands are loaded by the voice pipeline and route to browser_navigator.
They complement existing navigation commands in commands.py (which use hotkeys/OS).

Usage:
    from src.commands_browser import BROWSER_COMMANDS, execute_browser_command
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.commands_browser")


@dataclass
class BrowserVoiceCommand:
    """A browser voice command routed to BrowserNavigator."""
    name: str
    description: str
    triggers: list[str]
    params: list[str] = field(default_factory=list)


BROWSER_COMMANDS: list[BrowserVoiceCommand] = [
    # ── Navigation ────────────────────────────────────────────────────────
    BrowserVoiceCommand(
        "browser_open",
        "Ouvrir le navigateur Playwright",
        ["ouvre le navigateur playwright", "lance playwright", "ouvre playwright"],
    ),
    BrowserVoiceCommand(
        "browser_navigate",
        "Naviguer vers un site",
        ["va sur {site}", "navigue vers {site}", "ouvre {site}"],
        ["site"],
    ),
    BrowserVoiceCommand(
        "browser_back",
        "Page precedente",
        ["page precedente", "retour", "reviens en arriere", "go back"],
    ),
    BrowserVoiceCommand(
        "browser_forward",
        "Page suivante",
        ["page suivante", "avance", "suivant", "go forward"],
    ),
    BrowserVoiceCommand(
        "browser_reload",
        "Recharger la page",
        ["recharge la page", "refresh", "actualise", "recharge"],
    ),

    # ── Tabs ──────────────────────────────────────────────────────────────
    BrowserVoiceCommand(
        "browser_close_tab",
        "Fermer l'onglet actif",
        ["ferme la page", "ferme l'onglet", "close tab"],
    ),
    BrowserVoiceCommand(
        "browser_new_tab",
        "Nouvel onglet",
        ["nouvel onglet playwright", "nouveau tab playwright", "ouvre un onglet playwright"],
    ),
    BrowserVoiceCommand(
        "browser_list_tabs",
        "Lister les onglets ouverts",
        ["liste les onglets", "quels onglets", "tabs ouverts"],
    ),

    # ── Interaction ───────────────────────────────────────────────────────
    BrowserVoiceCommand(
        "browser_click",
        "Cliquer sur un element par texte",
        ["clique sur {text}", "appuie sur {text}", "click {text}"],
        ["text"],
    ),
    BrowserVoiceCommand(
        "browser_scroll_down",
        "Scroller vers le bas",
        ["descends", "scroll", "defile", "scroll down"],
    ),
    BrowserVoiceCommand(
        "browser_scroll_up",
        "Scroller vers le haut",
        ["remonte", "scroll vers le haut", "scroll up"],
    ),
    BrowserVoiceCommand(
        "browser_search",
        "Recherche Google via Playwright",
        ["cherche {query} sur playwright", "recherche playwright {query}"],
        ["query"],
    ),
    BrowserVoiceCommand(
        "browser_fill",
        "Remplir un champ de formulaire",
        ["ecris {text} dans {field}", "tape {text} dans {field}"],
        ["text", "field"],
    ),
    BrowserVoiceCommand(
        "browser_read",
        "Lire le contenu de la page",
        ["lis la page", "qu'est-ce qui est ecrit", "lis le contenu"],
    ),
    BrowserVoiceCommand(
        "browser_screenshot",
        "Capture d'ecran de la page",
        ["capture la page", "screenshot du navigateur", "screen playwright"],
    ),

    # ── Window management ─────────────────────────────────────────────────
    BrowserVoiceCommand(
        "browser_move_screen",
        "Deplacer le navigateur sur l'autre ecran",
        ["deplace le nav sur l'autre ecran", "mets le navigateur sur l'autre ecran",
         "bouge le nav", "passe le nav sur le deuxieme ecran"],
    ),
    BrowserVoiceCommand(
        "browser_fullscreen",
        "Plein ecran",
        ["plein ecran playwright", "maximise le nav playwright", "fullscreen"],
    ),
]


async def execute_browser_command(name: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    """Execute a browser command by name."""
    from src.browser_navigator import browser_nav

    params = params or {}

    handlers: dict[str, Any] = {
        "browser_open": lambda: browser_nav.launch(),
        "browser_navigate": lambda: browser_nav.navigate(params.get("site", "")),
        "browser_back": lambda: browser_nav.go_back(),
        "browser_forward": lambda: browser_nav.go_forward(),
        "browser_reload": lambda: browser_nav.reload(),
        "browser_close_tab": lambda: browser_nav.close_tab(),
        "browser_new_tab": lambda: browser_nav.new_tab(params.get("url")),
        "browser_list_tabs": lambda: browser_nav.list_tabs(),
        "browser_click": lambda: browser_nav.click_text(params.get("text", "")),
        "browser_scroll_down": lambda: browser_nav.scroll("down"),
        "browser_scroll_up": lambda: browser_nav.scroll("up"),
        "browser_search": lambda: browser_nav.search(params.get("query", "")),
        "browser_fill": lambda: browser_nav.fill_field(params.get("field", ""), params.get("text", "")),
        "browser_read": lambda: browser_nav.read_page(),
        "browser_screenshot": lambda: browser_nav.screenshot_page(),
        "browser_move_screen": lambda: browser_nav.move_to_screen(),
        "browser_fullscreen": lambda: browser_nav.fullscreen(),
    }

    handler = handlers.get(name)
    if not handler:
        return {"error": f"Unknown browser command: {name}"}

    try:
        result = await handler()
        return {"status": "ok", "command": name, "result": result}
    except Exception as e:
        logger.warning("Browser command %s failed: %s", name, e)
        return {"status": "error", "command": name, "error": str(e)}
