"""JARVIS Browser Voice Commands — Playwright-powered navigation by voice.

These commands are loaded by the voice pipeline and route to browser_navigator.
They complement existing navigation commands in commands.py (which use hotkeys/OS).

Usage:
    from src.commands_browser import BROWSER_COMMANDS, execute_browser_command
"""

from __future__ import annotations

import logging
import time
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

    # ── Memory & Intelligence ─────────────────────────────────────────────
    BrowserVoiceCommand(
        "browser_bookmark",
        "Ajouter cette page aux favoris",
        ["ajoute aux favoris", "bookmark cette page", "sauvegarde cette page",
         "enregistre cette page", "mets en favori", "garde cette page"],
    ),
    BrowserVoiceCommand(
        "browser_bookmarks_list",
        "Lister les favoris",
        ["liste mes favoris", "quels sont mes favoris", "mes bookmarks",
         "montre les favoris", "mes pages sauvegardees"],
    ),
    BrowserVoiceCommand(
        "browser_history",
        "Historique de navigation recent",
        ["historique de navigation", "pages recentes", "dernieres pages visitees",
         "qu'est-ce que j'ai visite", "historique web"],
    ),
    BrowserVoiceCommand(
        "browser_search_history",
        "Chercher dans l'historique",
        ["cherche dans l'historique {query}", "retrouve la page {query}",
         "trouve la page sur {query}", "ou j'ai vu {query}"],
        ["query"],
    ),
    BrowserVoiceCommand(
        "browser_goto_remembered",
        "Retourner a une page memorisee",
        ["retourne sur {name}", "reouvre {name}", "va sur la page {name}",
         "ouvre la page de {name}", "reviens sur {name}"],
        ["name"],
    ),
    BrowserVoiceCommand(
        "browser_landmarks",
        "Lister les reperes de la page",
        ["quels sont les reperes", "reperes de la page", "structure de la page",
         "analyse la page", "qu'est-ce qu'il y a sur la page", "lis les titres",
         "montre les elements"],
    ),
    BrowserVoiceCommand(
        "browser_scroll_to",
        "Aller a un repere de la page",
        ["va au {text}", "descends jusqu'a {text}", "trouve {text} sur la page",
         "scroll vers {text}", "montre moi {text}"],
        ["text"],
    ),
    BrowserVoiceCommand(
        "browser_summarize",
        "Resumer la page avec l'IA",
        ["resume cette page", "c'est quoi cette page", "de quoi parle cette page",
         "resume le contenu", "explique cette page"],
    ),
    BrowserVoiceCommand(
        "browser_add_note",
        "Ajouter une note a la page",
        ["note sur cette page {note}", "ajoute la note {note}",
         "prends note {note}", "rappelle que {note}"],
        ["note"],
    ),
    BrowserVoiceCommand(
        "browser_save_session",
        "Sauvegarder les onglets comme session",
        ["sauvegarde les onglets", "sauvegarde la session {name}",
         "enregistre les onglets sous {name}", "garde ces onglets"],
        ["name"],
    ),
    BrowserVoiceCommand(
        "browser_restore_session",
        "Restaurer une session d'onglets",
        ["restaure la session {name}", "ouvre la session {name}",
         "charge la session {name}", "recharge les onglets {name}"],
        ["name"],
    ),
    BrowserVoiceCommand(
        "browser_most_visited",
        "Pages les plus visitees",
        ["pages les plus visitees", "mes sites preferes", "top pages",
         "quels sites je visite le plus"],
    ),

    # ── New: Find, Links, Structure, Persistent ────────────────────────────
    BrowserVoiceCommand(
        "browser_find",
        "Chercher du texte dans la page (Ctrl+F vocal)",
        ["cherche {text} sur la page", "trouve {text} dans la page",
         "ou est {text}", "ctrl f {text}", "find {text}"],
        ["text"],
    ),
    BrowserVoiceCommand(
        "browser_clear_find",
        "Effacer le surlignage de recherche",
        ["efface le surlignage", "enleve le jaune", "clear highlights"],
    ),
    BrowserVoiceCommand(
        "browser_read_links",
        "Lister les liens visibles de la page",
        ["lis les liens", "quels liens", "montre les liens",
         "liste les liens", "les liens de la page"],
    ),
    BrowserVoiceCommand(
        "browser_click_number",
        "Cliquer sur le lien numero N",
        ["clique lien {number}", "ouvre lien {number}", "lien numero {number}",
         "va au lien {number}"],
        ["number"],
    ),
    BrowserVoiceCommand(
        "browser_scroll_top",
        "Remonter tout en haut de la page",
        ["remonte tout en haut", "haut de la page", "debut de la page",
         "scroll tout en haut"],
    ),
    BrowserVoiceCommand(
        "browser_scroll_bottom",
        "Descendre tout en bas de la page",
        ["descends tout en bas", "bas de la page", "fin de la page",
         "scroll tout en bas"],
    ),
    BrowserVoiceCommand(
        "browser_structure",
        "Vue d'ensemble de la page (titres, liens, boutons)",
        ["structure de la page", "c'est quoi cette page en gros",
         "donne moi un apercu", "overview de la page", "analyse rapide"],
    ),
    BrowserVoiceCommand(
        "browser_selection",
        "Lire le texte selectionne",
        ["lis la selection", "qu'est-ce qui est selectionne",
         "lis le texte selectionne", "read selection"],
    ),
    BrowserVoiceCommand(
        "browser_launch_persistent",
        "Ouvrir le navigateur avec sauvegarde de session (cookies gardes)",
        ["ouvre le navigateur persistent", "lance le navigateur avec login",
         "navigateur qui garde les cookies", "ouvre avec mon profil"],
    ),
    BrowserVoiceCommand(
        "browser_type_text",
        "Taper du texte dans le champ actif",
        ["tape {text}", "ecris {text}", "type {text}", "saisis {text}"],
        ["text"],
    ),
    BrowserVoiceCommand(
        "browser_press_key",
        "Appuyer sur une touche",
        ["appuie sur entree", "touche {key}", "appuie sur {key}",
         "press {key}", "echap", "tab", "entree"],
        ["key"],
    ),
    BrowserVoiceCommand(
        "browser_switch_tab",
        "Basculer sur l'onglet numero N",
        ["onglet {index}", "va sur l'onglet {index}", "switch tab {index}",
         "passe a l'onglet {index}"],
        ["index"],
    ),
]


async def _format_bookmarks() -> dict[str, Any]:
    from src.browser_memory import browser_memory
    bookmarks = browser_memory.get_bookmarks(limit=10)
    if not bookmarks:
        return {"message": "Aucun favori enregistre.", "bookmarks": []}
    lines = [f"{b['title'] or b['domain']} — {b['url']}" for b in bookmarks]
    return {"message": "\n".join(lines), "bookmarks": bookmarks, "count": len(bookmarks)}


async def _format_history() -> dict[str, Any]:
    from src.browser_memory import browser_memory
    pages = browser_memory.recent_pages(limit=10)
    if not pages:
        return {"message": "Aucune page dans l'historique.", "pages": []}
    lines = [f"{p['title'] or p['domain']} ({p['visit_count']}x)" for p in pages]
    return {"message": "\n".join(lines), "pages": pages, "count": len(pages)}


async def _format_most_visited() -> dict[str, Any]:
    from src.browser_memory import browser_memory
    pages = browser_memory.most_visited(limit=10)
    if not pages:
        return {"message": "Aucune page visitee.", "pages": []}
    lines = [f"{p['title'] or p['domain']} — {p['visit_count']} visites" for p in pages]
    return {"message": "\n".join(lines), "pages": pages}


async def _add_note_to_current(note: str) -> dict[str, Any]:
    from src.browser_navigator import browser_nav
    from src.browser_memory import browser_memory
    if not browser_nav._page or browser_nav._page.is_closed():
        return {"error": "Aucune page ouverte"}
    url = browser_nav._page.url
    ok = browser_memory.add_note(url, note)
    return {"noted": ok, "url": url, "note": note}


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
        # Memory & Intelligence
        "browser_bookmark": lambda: browser_nav.bookmark_current(
            tags=params.get("tags", "").split(",") if params.get("tags") else None,
            notes=params.get("notes", "")),
        "browser_bookmarks_list": lambda: _format_bookmarks(),
        "browser_history": lambda: _format_history(),
        "browser_search_history": lambda: browser_nav.search_history(params.get("query", "")),
        "browser_goto_remembered": lambda: browser_nav.goto_remembered(params.get("name", "")),
        "browser_landmarks": lambda: browser_nav.get_page_landmarks_voice(),
        "browser_scroll_to": lambda: browser_nav.scroll_to_landmark(params.get("text", "")),
        "browser_summarize": lambda: browser_nav.summarize_page(),
        "browser_add_note": lambda: _add_note_to_current(params.get("note", "")),
        "browser_save_session": lambda: browser_nav.save_tab_session(
            params.get("name", f"session_{int(time.time())}")),
        "browser_restore_session": lambda: browser_nav.restore_tab_session(params.get("name", "")),
        "browser_most_visited": lambda: _format_most_visited(),
        # New commands
        "browser_find": lambda: browser_nav.find_on_page(params.get("text", "")),
        "browser_clear_find": lambda: browser_nav.clear_highlights(),
        "browser_read_links": lambda: browser_nav.read_links_voice(),
        "browser_click_number": lambda: browser_nav.click_link_number(int(params.get("number", "1"))),
        "browser_scroll_top": lambda: browser_nav.scroll_to_top(),
        "browser_scroll_bottom": lambda: browser_nav.scroll_to_bottom(),
        "browser_structure": lambda: browser_nav.get_page_structure_voice(),
        "browser_selection": lambda: browser_nav.read_selection(),
        "browser_launch_persistent": lambda: browser_nav.launch_persistent(params.get("url")),
        "browser_type_text": lambda: browser_nav.type_text(params.get("text", "")),
        "browser_press_key": lambda: browser_nav.press_key(
            {"entree": "Enter", "echap": "Escape", "tab": "Tab",
             "espace": "Space", "supprimer": "Delete"}.get(
                params.get("key", "Enter").lower(), params.get("key", "Enter"))),
        "browser_switch_tab": lambda: browser_nav.switch_tab(int(params.get("index", "0"))),
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
