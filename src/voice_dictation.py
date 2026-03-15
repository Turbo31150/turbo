"""JARVIS — Module de dictee vocale et edition de texte par la voix.

Controle complet de la saisie et edition de texte sans clavier physique.
Utilise xdotool pour la simulation clavier sur Linux (GNOME + X11).
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import time
from typing import Any

__all__ = [
    "VoiceDictation",
    "VOICE_COMMANDS",
    "PARAM_PATTERNS",
]

logger = logging.getLogger("jarvis.voice_dictation")

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

# Caracteres speciaux par nom francais
SPECIAL_CHARS: dict[str, str] = {
    "arobase": "@",
    "at": "@",
    "point": ".",
    "virgule": ",",
    "tiret": "-",
    "underscore": "_",
    "slash": "/",
    "antislash": "\\",
    "backslash": "\\",
    "egal": "=",
    "plus": "+",
    "etoile": "*",
    "asterisque": "*",
    "diese": "#",
    "hashtag": "#",
    "dollar": "$",
    "euro": "€",
    "pourcent": "%",
    "et commercial": "&",
    "esperluette": "&",
    "exclamation": "!",
    "interrogation": "?",
    "point virgule": ";",
    "deux points": ":",
    "apostrophe": "'",
    "guillemet": '"',
    "parenthese ouvrante": "(",
    "parenthese fermante": ")",
    "crochet ouvrant": "[",
    "crochet fermant": "]",
    "accolade ouvrante": "{",
    "accolade fermante": "}",
    "inferieur": "<",
    "superieur": ">",
    "pipe": "|",
    "tilde": "~",
    "accent grave": "`",
    "chapeau": "^",
}

# Alphabet phonetique (francais + NATO)
PHONETIC_ALPHABET: dict[str, str] = {
    # NATO
    "alpha": "a", "bravo": "b", "charlie": "c", "delta": "d",
    "echo": "e", "foxtrot": "f", "golf": "g", "hotel": "h",
    "india": "i", "juliet": "j", "kilo": "k", "lima": "l",
    "mike": "m", "november": "n", "oscar": "o", "papa": "p",
    "quebec": "q", "romeo": "r", "sierra": "s", "tango": "t",
    "uniform": "u", "victor": "v", "whiskey": "w", "x-ray": "x",
    "yankee": "y", "zoulou": "z",
    # Francais classique (Anatole, Berthe, etc.)
    "anatole": "a", "berthe": "b", "celestin": "c", "desire": "d",
    "eugene": "e", "francois": "f", "gaston": "g", "henri": "h",
    "irma": "i", "joseph": "j", "kleber": "k", "louis": "l",
    "marcel": "m", "nicolas": "n", "emile": "e",
    "pierre": "p", "raoul": "r", "suzanne": "s",
    "therese": "t", "ursule": "u", "william": "w",
    "xavier": "x", "yvonne": "y",
}

# ══════════════════════════════════════════════════════════════════════════════
# COMMANDES VOCALES
# ══════════════════════════════════════════════════════════════════════════════

VOICE_COMMANDS: dict[str, dict[str, Any]] = {
    # --- Saisie de texte ---
    "dicte": {
        "method": "dict_type_text",
        "params": ["text"],
        "aliases": ["tape", "ecris", "saisis"],
        "description": "Dicter du texte dans l'application active",
    },
    "dicte lentement": {
        "method": "dict_type_slow",
        "params": ["text"],
        "aliases": ["tape lentement"],
        "description": "Dicter du texte lentement (applications lentes)",
    },
    "epelle": {
        "method": "dict_spell",
        "params": ["letters"],
        "aliases": ["epeler"],
        "description": "Epeler lettre par lettre",
    },
    "nombre": {
        "method": "dict_number",
        "params": ["number"],
        "aliases": ["chiffre", "numero"],
        "description": "Taper un nombre",
    },
    "nouvelle ligne": {
        "method": "dict_newline",
        "params": [],
        "aliases": ["retour a la ligne", "retour", "entree"],
        "description": "Appuyer sur Entree",
    },
    "tabulation": {
        "method": "dict_tab",
        "params": [],
        "aliases": ["tab"],
        "description": "Appuyer sur Tabulation",
    },
    "espace": {
        "method": "dict_space",
        "params": [],
        "aliases": [],
        "description": "Inserer un espace",
    },
    # --- Caracteres speciaux ---
    "arobase": {
        "method": "dict_special_char",
        "params": [],
        "params_fixed": {"name": "arobase"},
        "aliases": ["at"],
        "description": "Taper @",
    },
    "point": {
        "method": "dict_special_char",
        "params": [],
        "params_fixed": {"name": "point"},
        "aliases": [],
        "description": "Taper .",
    },
    "virgule": {
        "method": "dict_special_char",
        "params": [],
        "params_fixed": {"name": "virgule"},
        "aliases": [],
        "description": "Taper ,",
    },
    "tiret": {
        "method": "dict_special_char",
        "params": [],
        "params_fixed": {"name": "tiret"},
        "aliases": [],
        "description": "Taper -",
    },
    "underscore": {
        "method": "dict_special_char",
        "params": [],
        "params_fixed": {"name": "underscore"},
        "aliases": [],
        "description": "Taper _",
    },
    "slash": {
        "method": "dict_special_char",
        "params": [],
        "params_fixed": {"name": "slash"},
        "aliases": [],
        "description": "Taper /",
    },
    "diese": {
        "method": "dict_special_char",
        "params": [],
        "params_fixed": {"name": "diese"},
        "aliases": ["hashtag"],
        "description": "Taper #",
    },
    # --- Navigation ---
    "debut du document": {
        "method": "dict_goto_start",
        "params": [],
        "aliases": ["aller au debut"],
        "description": "Aller au debut du document",
    },
    "fin du document": {
        "method": "dict_goto_end",
        "params": [],
        "aliases": ["aller a la fin"],
        "description": "Aller a la fin du document",
    },
    "debut de ligne": {
        "method": "dict_goto_line_start",
        "params": [],
        "aliases": ["debut de la ligne"],
        "description": "Aller au debut de la ligne",
    },
    "fin de ligne": {
        "method": "dict_goto_line_end",
        "params": [],
        "aliases": ["fin de la ligne"],
        "description": "Aller a la fin de la ligne",
    },
    "mot precedent": {
        "method": "dict_word_left",
        "params": [],
        "aliases": ["mot a gauche"],
        "description": "Aller au mot precedent",
    },
    "mot suivant": {
        "method": "dict_word_right",
        "params": [],
        "aliases": ["mot a droite"],
        "description": "Aller au mot suivant",
    },
    "page precedente": {
        "method": "dict_page_up",
        "params": [],
        "aliases": ["page haut"],
        "description": "Page precedente",
    },
    "page suivante": {
        "method": "dict_page_down",
        "params": [],
        "aliases": ["page bas"],
        "description": "Page suivante",
    },
    # --- Selection ---
    "selectionne tout": {
        "method": "dict_select_all",
        "params": [],
        "aliases": ["tout selectionner", "select all"],
        "description": "Selectionner tout le texte",
    },
    "selectionne le mot": {
        "method": "dict_select_word",
        "params": [],
        "aliases": ["selection mot"],
        "description": "Selectionner le mot a gauche",
    },
    "selectionne mot suivant": {
        "method": "dict_select_word_right",
        "params": [],
        "aliases": ["selection mot droite"],
        "description": "Selectionner le mot a droite",
    },
    "selectionne la ligne": {
        "method": "dict_select_line",
        "params": [],
        "aliases": ["selection ligne"],
        "description": "Selectionner la ligne courante",
    },
    "selectionne jusqu au debut": {
        "method": "dict_select_to_start",
        "params": [],
        "aliases": ["selection debut"],
        "description": "Selectionner jusqu'au debut du document",
    },
    "selectionne jusqu a la fin": {
        "method": "dict_select_to_end",
        "params": [],
        "aliases": ["selection fin"],
        "description": "Selectionner jusqu'a la fin du document",
    },
    # --- Edition ---
    "supprime le mot": {
        "method": "dict_delete_word",
        "params": [],
        "aliases": ["efface le mot", "supprimer mot"],
        "description": "Supprimer le mot precedent",
    },
    "supprime la ligne": {
        "method": "dict_delete_line",
        "params": [],
        "aliases": ["efface la ligne", "supprimer ligne"],
        "description": "Supprimer la ligne courante",
    },
    "couper": {
        "method": "dict_cut",
        "params": [],
        "aliases": ["coupe"],
        "description": "Couper la selection",
    },
    "copier": {
        "method": "dict_copy",
        "params": [],
        "aliases": ["copie"],
        "description": "Copier la selection",
    },
    "coller": {
        "method": "dict_paste",
        "params": [],
        "aliases": ["cole"],
        "description": "Coller le contenu du presse-papier",
    },
    "annuler": {
        "method": "dict_undo",
        "params": [],
        "aliases": ["defaire"],
        "description": "Annuler la derniere action",
    },
    "refaire": {
        "method": "dict_redo",
        "params": [],
        "aliases": ["retablir"],
        "description": "Refaire la derniere action annulee",
    },
    "cherche": {
        "method": "dict_find",
        "params": ["text"],
        "aliases": ["recherche", "trouve", "trouver"],
        "description": "Rechercher du texte dans le document",
    },
    "remplace": {
        "method": "dict_replace",
        "params": ["old", "new"],
        "aliases": ["remplacer"],
        "description": "Remplacer du texte dans le document",
    },
    # --- Formatage ---
    "gras": {
        "method": "dict_bold",
        "params": [],
        "aliases": ["met en gras"],
        "description": "Basculer le gras",
    },
    "italique": {
        "method": "dict_italic",
        "params": [],
        "aliases": ["met en italique"],
        "description": "Basculer l'italique",
    },
    "souligne": {
        "method": "dict_underline",
        "params": [],
        "aliases": ["souligner"],
        "description": "Basculer le soulignement",
    },
    # --- Dictee speciale ---
    "email": {
        "method": "dict_email",
        "params": ["address"],
        "aliases": ["adresse mail", "adresse email"],
        "description": "Taper une adresse email",
    },
    "url": {
        "method": "dict_url",
        "params": ["url"],
        "aliases": ["adresse web", "lien"],
        "description": "Taper une URL",
    },
    "majuscule": {
        "method": "dict_capitalize",
        "params": [],
        "aliases": ["capitalise"],
        "description": "Mettre en majuscule le dernier mot",
    },
    "tout en majuscule": {
        "method": "dict_uppercase",
        "params": [],
        "aliases": ["tout majuscule", "caps"],
        "description": "Convertir la selection en majuscules",
    },
    "tout en minuscule": {
        "method": "dict_lowercase",
        "params": [],
        "aliases": ["tout minuscule"],
        "description": "Convertir la selection en minuscules",
    },
    # --- Insertion de dates/templates ---
    "insere la date": {
        "method": "dict_insert_date",
        "params": [],
        "aliases": ["date du jour", "tape la date", "quelle date aujourd'hui"],
        "description": "Inserer la date du jour",
    },
    "insere l'heure": {
        "method": "dict_insert_time",
        "params": [],
        "aliases": ["heure actuelle", "tape l'heure"],
        "description": "Inserer l'heure actuelle",
    },
    "insere date et heure": {
        "method": "dict_insert_datetime",
        "params": [],
        "aliases": ["horodatage", "timestamp"],
        "description": "Inserer date et heure",
    },
    "signature": {
        "method": "dict_insert_signature",
        "params": [],
        "aliases": ["insere la signature", "signe"],
        "description": "Inserer la signature standard",
    },
    "template email": {
        "method": "dict_insert_email_template",
        "params": [],
        "aliases": ["modele email", "nouveau mail"],
        "description": "Inserer un template d'email",
    },
    # --- Navigation par paragraphe ---
    "paragraphe precedent": {
        "method": "dict_paragraph_up",
        "params": [],
        "aliases": ["paragraphe haut", "monte paragraphe"],
        "description": "Aller au paragraphe precedent",
    },
    "paragraphe suivant": {
        "method": "dict_paragraph_down",
        "params": [],
        "aliases": ["paragraphe bas", "descends paragraphe"],
        "description": "Aller au paragraphe suivant",
    },
    "selectionne paragraphe": {
        "method": "dict_select_paragraph",
        "params": [],
        "aliases": ["selectionne le paragraphe"],
        "description": "Selectionner le paragraphe courant",
    },
    # --- Manipulation de lignes ---
    "supprime la ligne": {
        "method": "dict_delete_line",
        "params": [],
        "aliases": ["efface la ligne", "supprime ligne"],
        "description": "Supprimer la ligne courante",
    },
    "duplique la ligne": {
        "method": "dict_duplicate_line",
        "params": [],
        "aliases": ["copie la ligne", "duplique ligne"],
        "description": "Dupliquer la ligne courante",
    },
    "indente": {
        "method": "dict_indent",
        "params": [],
        "aliases": ["ajoute indentation", "tab"],
        "description": "Indenter",
    },
    "desindente": {
        "method": "dict_unindent",
        "params": [],
        "aliases": ["retire indentation", "shift tab"],
        "description": "Desindenter",
    },
    # --- Recherche ---
    "rechercher": {
        "method": "dict_find_text",
        "params": [],
        "aliases": ["trouve texte", "chercher dans le texte", "ctrl f"],
        "description": "Ouvrir la recherche",
    },
    "rechercher remplacer": {
        "method": "dict_find_replace",
        "params": [],
        "aliases": ["chercher remplacer", "ctrl h"],
        "description": "Ouvrir rechercher et remplacer",
    },
    # --- Navigation avancee ---
    "debut de ligne": {
        "method": "dict_goto_line_start",
        "params": [],
        "aliases": ["debut ligne", "home"],
        "description": "Debut de la ligne",
    },
    "fin de ligne": {
        "method": "dict_goto_line_end",
        "params": [],
        "aliases": ["fin ligne", "end"],
        "description": "Fin de la ligne",
    },
    "debut du document": {
        "method": "dict_goto_doc_start",
        "params": [],
        "aliases": ["tout en haut du document", "debut fichier"],
        "description": "Debut du document",
    },
    "fin du document": {
        "method": "dict_goto_doc_end",
        "params": [],
        "aliases": ["tout en bas du document", "fin fichier"],
        "description": "Fin du document",
    },
    "selectionne la ligne": {
        "method": "dict_select_line",
        "params": [],
        "aliases": ["selectionne ligne"],
        "description": "Selectionner la ligne courante",
    },
    "selectionne le mot": {
        "method": "dict_select_word",
        "params": [],
        "aliases": ["selectionne mot"],
        "description": "Selectionner le mot sous le curseur",
    },
}

# Ajouter les commandes pour chaque lettre de l'alphabet phonetique
for _name, _letter in PHONETIC_ALPHABET.items():
    if _name not in VOICE_COMMANDS:
        VOICE_COMMANDS[_name] = {
            "method": "dict_letter",
            "params": [],
            "params_fixed": {"name": _name},
            "aliases": [],
            "description": f"Taper la lettre '{_letter}'",
        }

# ══════════════════════════════════════════════════════════════════════════════
# PATTERNS DE PARAMETRES (pour extraction depuis commandes vocales)
# ══════════════════════════════════════════════════════════════════════════════

PARAM_PATTERNS: dict[str, str] = {
    "dicte": r"(?:dicte|tape|ecris|saisis)\s+(.+)",
    "dicte_lent": r"(?:dicte|tape)\s+lentement\s+(.+)",
    "epelle": r"(?:epelle|epeler)\s+(.+)",
    "nombre": r"(?:nombre|chiffre|numero)\s+(\d+)",
    "cherche": r"(?:cherche|recherche|trouve|trouver)\s+(.+)",
    "remplace": r"(?:remplace|remplacer)\s+(.+?)\s+par\s+(.+)",
    "email": r"(?:email|adresse mail|adresse email)\s+(.+)",
    "url": r"(?:url|adresse web|lien)\s+(.+)",
    "lettre": r"(?:lettre)\s+(\w+)",
    "caractere": r"(?:caractere|caractere special)\s+(.+)",
}


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

class VoiceDictation:
    """Module de dictee et edition de texte par commandes vocales.

    Utilise xdotool pour simuler les frappes clavier sur Linux (X11).
    Toutes les methodes sont prefixees par ``dict_``.
    """

    # Delai par defaut entre les touches pour dict_type_slow (ms)
    SLOW_DELAY_MS: int = 50
    # Delai entre les combinaisons de touches (secondes)
    KEY_COMBO_DELAY: float = 0.05

    def __init__(self, *, xdotool_path: str | None = None) -> None:
        """Initialiser le module de dictee vocale.

        Args:
            xdotool_path: Chemin vers xdotool (auto-detecte si None).
        """
        self._xdotool = xdotool_path or shutil.which("xdotool")
        if not self._xdotool:
            raise RuntimeError(
                "xdotool introuvable. Installer avec: sudo apt install xdotool"
            )
        logger.info("VoiceDictation initialise avec xdotool=%s", self._xdotool)

    # ══════════════════════════════════════════════════════════════════════
    # UTILITAIRES INTERNES
    # ══════════════════════════════════════════════════════════════════════

    def _xdo(self, *args: str) -> str:
        """Executer une commande xdotool.

        Returns:
            La sortie stdout de la commande.

        Raises:
            RuntimeError: Si la commande echoue.
        """
        cmd = [self._xdotool, *args]
        logger.debug("xdotool: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                err = result.stderr.strip()
                logger.error("xdotool erreur: %s", err)
                raise RuntimeError(f"xdotool erreur: {err}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise RuntimeError("xdotool timeout (10s)")

    def _key(self, *keys: str) -> None:
        """Envoyer une combinaison de touches."""
        self._xdo("key", "--clearmodifiers", "+".join(keys))

    def _type_str(self, text: str, *, delay_ms: int = 0) -> None:
        """Taper une chaine de caracteres.

        Args:
            text: Le texte a taper.
            delay_ms: Delai entre les caracteres en millisecondes.
        """
        args = ["type", "--clearmodifiers"]
        if delay_ms > 0:
            args.extend(["--delay", str(delay_ms)])
        args.append(text)
        self._xdo(*args)

    def _get_clipboard(self) -> str:
        """Lire le contenu du presse-papier via xclip."""
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    def _set_clipboard(self, text: str) -> None:
        """Ecrire dans le presse-papier via xclip."""
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text,
                text=True,
                timeout=5,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("xclip introuvable, presse-papier non modifie")

    # ══════════════════════════════════════════════════════════════════════
    # SAISIE DE TEXTE
    # ══════════════════════════════════════════════════════════════════════

    def dict_type_text(self, text: str) -> str:
        """Taper du texte dans l'application active.

        Args:
            text: Le texte a saisir.

        Returns:
            Message de confirmation.
        """
        if not text:
            return "Aucun texte a saisir"
        self._type_str(text)
        preview = text[:50] + ("..." if len(text) > 50 else "")
        logger.info("Texte saisi: %s", preview)
        return f"Texte saisi : \"{preview}\""

    def dict_type_slow(self, text: str) -> str:
        """Taper du texte avec un delai entre chaque caractere.

        Utile pour les applications lentes qui perdent des caracteres.

        Args:
            text: Le texte a saisir lentement.

        Returns:
            Message de confirmation.
        """
        if not text:
            return "Aucun texte a saisir"
        self._type_str(text, delay_ms=self.SLOW_DELAY_MS)
        preview = text[:50] + ("..." if len(text) > 50 else "")
        logger.info("Texte saisi lentement: %s", preview)
        return f"Texte saisi lentement : \"{preview}\""

    def dict_spell(self, letters: str) -> str:
        """Epeler des lettres une par une.

        Accepte des lettres separees par des espaces: "a b c" -> "abc".

        Args:
            letters: Lettres separees par des espaces.

        Returns:
            Message de confirmation.
        """
        chars = letters.replace(" ", "")
        if not chars:
            return "Aucune lettre a epeler"
        for ch in chars:
            self._type_str(ch)
            time.sleep(0.05)
        logger.info("Epele: %s", chars)
        return f"Epele : \"{chars}\""

    def dict_number(self, number: str) -> str:
        """Taper un nombre.

        Args:
            number: Le nombre a saisir (chaine pour preserver les zeros).

        Returns:
            Message de confirmation.
        """
        clean = str(number).strip()
        if not clean:
            return "Aucun nombre a saisir"
        self._type_str(clean)
        logger.info("Nombre saisi: %s", clean)
        return f"Nombre saisi : {clean}"

    def dict_special_char(self, name: str) -> str:
        """Taper un caractere special par son nom francais.

        Args:
            name: Nom du caractere (arobase, point, virgule, tiret, etc.).

        Returns:
            Message de confirmation ou erreur.
        """
        name_lower = name.lower().strip()
        char = SPECIAL_CHARS.get(name_lower)
        if char is None:
            available = ", ".join(sorted(SPECIAL_CHARS.keys()))
            return f"Caractere inconnu : \"{name}\". Disponibles : {available}"
        self._type_str(char)
        logger.info("Caractere special: %s -> %s", name, char)
        return f"Caractere saisi : {char} ({name})"

    def dict_newline(self) -> str:
        """Appuyer sur la touche Entree (nouvelle ligne)."""
        self._key("Return")
        logger.info("Nouvelle ligne")
        return "Nouvelle ligne"

    def dict_tab(self) -> str:
        """Appuyer sur la touche Tabulation."""
        self._key("Tab")
        logger.info("Tabulation")
        return "Tabulation"

    def dict_space(self) -> str:
        """Inserer un espace."""
        self._key("space")
        logger.info("Espace insere")
        return "Espace insere"

    # ══════════════════════════════════════════════════════════════════════
    # NAVIGATION DANS LE TEXTE
    # ══════════════════════════════════════════════════════════════════════

    def dict_goto_start(self) -> str:
        """Aller au debut du document (Ctrl+Home)."""
        self._key("ctrl+Home")
        logger.info("Navigation: debut du document")
        return "Debut du document"

    def dict_goto_end(self) -> str:
        """Aller a la fin du document (Ctrl+End)."""
        self._key("ctrl+End")
        logger.info("Navigation: fin du document")
        return "Fin du document"

    def dict_goto_line_start(self) -> str:
        """Aller au debut de la ligne courante (Home)."""
        self._key("Home")
        logger.info("Navigation: debut de ligne")
        return "Debut de ligne"

    def dict_goto_line_end(self) -> str:
        """Aller a la fin de la ligne courante (End)."""
        self._key("End")
        logger.info("Navigation: fin de ligne")
        return "Fin de ligne"

    def dict_word_left(self) -> str:
        """Aller au mot precedent (Ctrl+Gauche)."""
        self._key("ctrl+Left")
        logger.info("Navigation: mot precedent")
        return "Mot precedent"

    def dict_word_right(self) -> str:
        """Aller au mot suivant (Ctrl+Droite)."""
        self._key("ctrl+Right")
        logger.info("Navigation: mot suivant")
        return "Mot suivant"

    def dict_page_up(self) -> str:
        """Page precedente (Page Up)."""
        self._key("Prior")
        logger.info("Navigation: page precedente")
        return "Page precedente"

    def dict_page_down(self) -> str:
        """Page suivante (Page Down)."""
        self._key("Next")
        logger.info("Navigation: page suivante")
        return "Page suivante"

    # ══════════════════════════════════════════════════════════════════════
    # SELECTION DE TEXTE
    # ══════════════════════════════════════════════════════════════════════

    def dict_select_all(self) -> str:
        """Selectionner tout le texte (Ctrl+A)."""
        self._key("ctrl+a")
        logger.info("Selection: tout")
        return "Tout selectionne"

    def dict_select_word(self) -> str:
        """Selectionner le mot a gauche (Ctrl+Shift+Gauche)."""
        self._key("ctrl+shift+Left")
        logger.info("Selection: mot a gauche")
        return "Mot selectionne (gauche)"

    def dict_select_word_right(self) -> str:
        """Selectionner le mot a droite (Ctrl+Shift+Droite)."""
        self._key("ctrl+shift+Right")
        logger.info("Selection: mot a droite")
        return "Mot selectionne (droite)"

    def dict_select_line(self) -> str:
        """Selectionner la ligne courante (Home puis Shift+End)."""
        self._key("Home")
        time.sleep(self.KEY_COMBO_DELAY)
        self._key("shift+End")
        logger.info("Selection: ligne courante")
        return "Ligne selectionnee"

    def dict_select_to_start(self) -> str:
        """Selectionner du curseur jusqu'au debut du document (Ctrl+Shift+Home)."""
        self._key("ctrl+shift+Home")
        logger.info("Selection: jusqu'au debut")
        return "Selection jusqu'au debut"

    def dict_select_to_end(self) -> str:
        """Selectionner du curseur jusqu'a la fin du document (Ctrl+Shift+End)."""
        self._key("ctrl+shift+End")
        logger.info("Selection: jusqu'a la fin")
        return "Selection jusqu'a la fin"

    # ══════════════════════════════════════════════════════════════════════
    # EDITION DE TEXTE
    # ══════════════════════════════════════════════════════════════════════

    def dict_delete_word(self) -> str:
        """Supprimer le mot precedent (Ctrl+Backspace)."""
        self._key("ctrl+BackSpace")
        logger.info("Edition: mot supprime")
        return "Mot supprime"

    def dict_delete_line(self) -> str:
        """Supprimer la ligne courante (selection + suppression)."""
        self._key("Home")
        time.sleep(self.KEY_COMBO_DELAY)
        self._key("shift+End")
        time.sleep(self.KEY_COMBO_DELAY)
        self._key("BackSpace")
        logger.info("Edition: ligne supprimee")
        return "Ligne supprimee"

    def dict_cut(self) -> str:
        """Couper la selection (Ctrl+X)."""
        self._key("ctrl+x")
        logger.info("Edition: couper")
        return "Selection coupee"

    def dict_copy(self) -> str:
        """Copier la selection (Ctrl+C)."""
        self._key("ctrl+c")
        logger.info("Edition: copier")
        return "Selection copiee"

    def dict_paste(self) -> str:
        """Coller le contenu du presse-papier (Ctrl+V)."""
        self._key("ctrl+v")
        logger.info("Edition: coller")
        return "Contenu colle"

    def dict_undo(self) -> str:
        """Annuler la derniere action (Ctrl+Z)."""
        self._key("ctrl+z")
        logger.info("Edition: annuler")
        return "Action annulee"

    def dict_redo(self) -> str:
        """Refaire la derniere action annulee (Ctrl+Shift+Z)."""
        self._key("ctrl+shift+z")
        logger.info("Edition: refaire")
        return "Action refaite"

    def dict_find(self, text: str) -> str:
        """Ouvrir la recherche et taper le texte a chercher.

        Args:
            text: Le texte a rechercher.

        Returns:
            Message de confirmation.
        """
        if not text:
            return "Aucun texte a rechercher"
        self._key("ctrl+f")
        time.sleep(0.15)
        self._type_str(text)
        logger.info("Recherche: %s", text)
        return f"Recherche de : \"{text}\""

    def dict_replace(self, old: str, new: str) -> str:
        """Ouvrir le dialogue de remplacement et remplir les champs.

        Args:
            old: Le texte a remplacer.
            new: Le texte de remplacement.

        Returns:
            Message de confirmation.
        """
        if not old:
            return "Aucun texte a remplacer"
        self._key("ctrl+h")
        time.sleep(0.2)
        self._type_str(old)
        time.sleep(0.1)
        self._key("Tab")
        time.sleep(0.05)
        self._type_str(new)
        logger.info("Remplacement: '%s' -> '%s'", old, new)
        return f"Remplacement : \"{old}\" par \"{new}\""

    def dict_bold(self) -> str:
        """Basculer le gras (Ctrl+B)."""
        self._key("ctrl+b")
        logger.info("Formatage: gras")
        return "Gras bascule"

    def dict_italic(self) -> str:
        """Basculer l'italique (Ctrl+I)."""
        self._key("ctrl+i")
        logger.info("Formatage: italique")
        return "Italique bascule"

    def dict_underline(self) -> str:
        """Basculer le soulignement (Ctrl+U)."""
        self._key("ctrl+u")
        logger.info("Formatage: souligne")
        return "Soulignement bascule"

    # ══════════════════════════════════════════════════════════════════════
    # DICTEE SPECIALE
    # ══════════════════════════════════════════════════════════════════════

    def dict_email(self, address: str) -> str:
        """Taper une adresse email.

        Args:
            address: L'adresse email a saisir.

        Returns:
            Message de confirmation.
        """
        if not address:
            return "Aucune adresse email fournie"
        # Nettoyer les espaces eventuels de la reconnaissance vocale
        clean = address.strip().replace(" ", "")
        self._type_str(clean)
        logger.info("Email saisi: %s", clean)
        return f"Email saisi : {clean}"

    def dict_url(self, url: str) -> str:
        """Taper une URL.

        Args:
            url: L'URL a saisir.

        Returns:
            Message de confirmation.
        """
        if not url:
            return "Aucune URL fournie"
        clean = url.strip().replace(" ", "")
        self._type_str(clean)
        logger.info("URL saisie: %s", clean)
        return f"URL saisie : {clean}"

    def dict_capitalize(self) -> str:
        """Mettre en majuscule le dernier mot tape.

        Selectionne le mot precedent, le copie, le met en majuscule
        et le recolle.
        """
        # Selectionner le mot precedent
        self._key("ctrl+shift+Left")
        time.sleep(0.05)
        # Couper
        self._key("ctrl+x")
        time.sleep(0.1)
        # Lire le presse-papier, transformer, recoller
        text = self._get_clipboard()
        if text:
            capitalized = text.capitalize()
            self._set_clipboard(capitalized)
            time.sleep(0.05)
            self._key("ctrl+v")
            logger.info("Capitalise: '%s' -> '%s'", text.strip(), capitalized.strip())
            return f"Capitalise : \"{capitalized.strip()}\""
        return "Impossible de capitaliser (presse-papier vide)"

    def dict_uppercase(self) -> str:
        """Convertir la selection en majuscules.

        Coupe la selection, la transforme en majuscules et la recolle.
        """
        self._key("ctrl+x")
        time.sleep(0.1)
        text = self._get_clipboard()
        if text:
            upper = text.upper()
            self._set_clipboard(upper)
            time.sleep(0.05)
            self._key("ctrl+v")
            logger.info("Majuscules: '%s'", upper.strip())
            return f"Converti en majuscules : \"{upper.strip()}\""
        return "Aucune selection a convertir"

    def dict_lowercase(self) -> str:
        """Convertir la selection en minuscules.

        Coupe la selection, la transforme en minuscules et la recolle.
        """
        self._key("ctrl+x")
        time.sleep(0.1)
        text = self._get_clipboard()
        if text:
            lower = text.lower()
            self._set_clipboard(lower)
            time.sleep(0.05)
            self._key("ctrl+v")
            logger.info("Minuscules: '%s'", lower.strip())
            return f"Converti en minuscules : \"{lower.strip()}\""
        return "Aucune selection a convertir"

    # ══════════════════════════════════════════════════════════════════════
    # ALPHABET PHONETIQUE
    # ══════════════════════════════════════════════════════════════════════

    def dict_letter(self, name: str) -> str:
        """Taper une lettre a partir de son nom phonetique.

        Supporte l'alphabet NATO et les noms francais classiques.
        Exemples: alpha/anatole -> a, bravo/berthe -> b, etc.

        Args:
            name: Le nom phonetique de la lettre.

        Returns:
            Message de confirmation ou erreur.
        """
        name_lower = name.lower().strip()
        letter = PHONETIC_ALPHABET.get(name_lower)
        if letter is None:
            available = ", ".join(sorted(PHONETIC_ALPHABET.keys()))
            return f"Lettre inconnue : \"{name}\". Disponibles : {available}"
        self._type_str(letter)
        logger.info("Lettre: %s -> %s", name, letter)
        return f"Lettre saisie : {letter} ({name})"

    # ══════════════════════════════════════════════════════════════════════
    # INSERTION DE DATES, HEURES, TEMPLATES
    # ══════════════════════════════════════════════════════════════════════

    def dict_insert_date(self) -> str:
        """Inserer la date du jour (format francais)."""
        import datetime
        date_str = datetime.date.today().strftime("%d/%m/%Y")
        self._type_str(date_str)
        return f"Date inseree: {date_str}"

    def dict_insert_time(self) -> str:
        """Inserer l'heure actuelle."""
        import datetime
        time_str = datetime.datetime.now().strftime("%H:%M")
        self._type_str(time_str)
        return f"Heure inseree: {time_str}"

    def dict_insert_datetime(self) -> str:
        """Inserer date et heure."""
        import datetime
        dt_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        self._type_str(dt_str)
        return f"Date et heure inserees: {dt_str}"

    def dict_insert_signature(self) -> str:
        """Inserer une signature standard."""
        sig = "Cordialement,\nTurbo"
        self._type_str(sig)
        return "Signature inseree"

    def dict_insert_email_template(self) -> str:
        """Inserer un template d'email."""
        template = "Bonjour,\n\n\n\nCordialement,\nTurbo"
        self._type_str(template)
        # Positionner le curseur au milieu (2 lignes haut)
        self._key("Up", "Up", "Up")
        return "Template email insere"

    def dict_paragraph_up(self) -> str:
        """Aller au paragraphe precedent."""
        self._key("ctrl+Up")
        return "Paragraphe precedent"

    def dict_paragraph_down(self) -> str:
        """Aller au paragraphe suivant."""
        self._key("ctrl+Down")
        return "Paragraphe suivant"

    def dict_select_paragraph(self) -> str:
        """Selectionner le paragraphe courant."""
        self._key("Home")
        time.sleep(0.02)
        self._key("shift+ctrl+Down")
        return "Paragraphe selectionne"

    def dict_delete_line(self) -> str:
        """Supprimer la ligne courante."""
        self._key("Home")
        time.sleep(0.02)
        self._key("shift+Down")
        time.sleep(0.02)
        self._key("Delete")
        return "Ligne supprimee"

    def dict_duplicate_line(self) -> str:
        """Dupliquer la ligne courante."""
        # Selectionner toute la ligne
        self._key("Home")
        time.sleep(0.02)
        self._key("shift+End")
        time.sleep(0.02)
        self._key("ctrl+c")
        time.sleep(0.05)
        self._key("End")
        time.sleep(0.02)
        self._key("Return")
        time.sleep(0.02)
        self._key("ctrl+v")
        return "Ligne dupliquee"

    def dict_indent(self) -> str:
        """Indenter (Tab)."""
        self._key("Tab")
        return "Indentation ajoutee"

    def dict_unindent(self) -> str:
        """Desindenter (Shift+Tab)."""
        self._key("shift+Tab")
        return "Indentation retiree"

    def dict_find_text(self) -> str:
        """Ouvrir rechercher (Ctrl+F)."""
        self._key("ctrl+f")
        return "Recherche ouverte"

    def dict_find_replace(self) -> str:
        """Ouvrir rechercher et remplacer (Ctrl+H)."""
        self._key("ctrl+h")
        return "Rechercher et remplacer ouvert"

    def dict_goto_line_start(self) -> str:
        """Aller au debut de la ligne."""
        self._key("Home")
        return "Debut de ligne"

    def dict_goto_line_end(self) -> str:
        """Aller a la fin de la ligne."""
        self._key("End")
        return "Fin de ligne"

    def dict_goto_doc_start(self) -> str:
        """Aller au debut du document."""
        self._key("ctrl+Home")
        return "Debut du document"

    def dict_goto_doc_end(self) -> str:
        """Aller a la fin du document."""
        self._key("ctrl+End")
        return "Fin du document"

    def dict_select_line(self) -> str:
        """Selectionner la ligne courante."""
        self._key("Home")
        time.sleep(0.02)
        self._key("shift+End")
        return "Ligne selectionnee"

    def dict_select_word(self) -> str:
        """Selectionner le mot sous le curseur."""
        self._key("ctrl+shift+Left")
        return "Mot selectionne"

    # ══════════════════════════════════════════════════════════════════════
    # DISPATCH COMMANDE VOCALE
    # ══════════════════════════════════════════════════════════════════════

    def dispatch(self, command: str, **kwargs: Any) -> str:
        """Dispatcher une commande vocale vers la methode appropriee.

        Cherche dans VOICE_COMMANDS (commandes et aliases) et appelle
        la methode correspondante.

        Args:
            command: La commande vocale (ex: "dicte", "copier", "alpha").
            **kwargs: Parametres supplementaires pour la methode.

        Returns:
            Resultat de la methode ou message d'erreur.
        """
        cmd_lower = command.lower().strip()

        # Chercher dans les commandes et aliases
        for cmd_name, cmd_info in VOICE_COMMANDS.items():
            if cmd_lower == cmd_name or cmd_lower in cmd_info.get("aliases", []):
                method_name = cmd_info["method"]
                method = getattr(self, method_name, None)
                if method is None:
                    return f"Methode introuvable : {method_name}"

                # Fusionner les parametres fixes avec ceux fournis
                merged = {**cmd_info.get("params_fixed", {}), **kwargs}

                # Construire les args selon la signature
                params = cmd_info.get("params", [])
                call_args = []
                call_kwargs = {}
                for p in params:
                    if p in merged:
                        call_args.append(merged[p])
                    elif p in kwargs:
                        call_args.append(kwargs[p])

                # Ajouter les params_fixed non dans params
                for k, v in merged.items():
                    if k not in params:
                        call_kwargs[k] = v

                try:
                    return method(*call_args, **call_kwargs)
                except TypeError as e:
                    return f"Erreur d'appel pour {method_name}: {e}"

        return f"Commande vocale inconnue : \"{command}\""

    def parse_and_execute(self, utterance: str) -> str:
        """Analyser une phrase vocale et executer la commande correspondante.

        Utilise PARAM_PATTERNS pour extraire les parametres de la phrase.

        Args:
            utterance: La phrase vocale complete.

        Returns:
            Resultat de l'execution ou message d'erreur.
        """
        text = utterance.lower().strip()

        # Tenter le remplacement en premier (contient "par")
        m = re.match(PARAM_PATTERNS["remplace"], text)
        if m:
            return self.dict_replace(m.group(1).strip(), m.group(2).strip())

        # Dictee lente
        m = re.match(PARAM_PATTERNS["dicte_lent"], text)
        if m:
            return self.dict_type_slow(m.group(1))

        # Dictee standard
        m = re.match(PARAM_PATTERNS["dicte"], text)
        if m:
            return self.dict_type_text(m.group(1))

        # Epellation
        m = re.match(PARAM_PATTERNS["epelle"], text)
        if m:
            return self.dict_spell(m.group(1))

        # Nombre
        m = re.match(PARAM_PATTERNS["nombre"], text)
        if m:
            return self.dict_number(m.group(1))

        # Recherche
        m = re.match(PARAM_PATTERNS["cherche"], text)
        if m:
            return self.dict_find(m.group(1))

        # Email
        m = re.match(PARAM_PATTERNS["email"], text)
        if m:
            return self.dict_email(m.group(1))

        # URL
        m = re.match(PARAM_PATTERNS["url"], text)
        if m:
            return self.dict_url(m.group(1))

        # Commandes sans parametres — essayer le dispatch direct
        return self.dispatch(text)

    # ══════════════════════════════════════════════════════════════════════
    # INTROSPECTION
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def list_commands() -> list[dict[str, Any]]:
        """Lister toutes les commandes vocales disponibles.

        Returns:
            Liste de dictionnaires avec les infos de chaque commande.
        """
        result = []
        for cmd_name, cmd_info in VOICE_COMMANDS.items():
            result.append({
                "commande": cmd_name,
                "methode": cmd_info["method"],
                "parametres": cmd_info.get("params", []),
                "aliases": cmd_info.get("aliases", []),
                "description": cmd_info.get("description", ""),
            })
        return result

    @staticmethod
    def list_methods() -> list[str]:
        """Lister toutes les methodes dict_ disponibles.

        Returns:
            Liste triee des noms de methodes.
        """
        methods = []
        for name in dir(VoiceDictation):
            if name.startswith("dict_") and callable(getattr(VoiceDictation, name)):
                methods.append(name)
        return sorted(methods)

    @staticmethod
    def list_special_chars() -> dict[str, str]:
        """Lister tous les caracteres speciaux disponibles.

        Returns:
            Dictionnaire nom -> caractere.
        """
        return dict(sorted(SPECIAL_CHARS.items()))

    @staticmethod
    def list_phonetic_alphabet() -> dict[str, str]:
        """Lister l'alphabet phonetique complet.

        Returns:
            Dictionnaire nom -> lettre.
        """
        return dict(sorted(PHONETIC_ALPHABET.items()))


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Point d'entree CLI pour le module de dictee vocale."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="JARVIS — Module de dictee vocale et edition de texte",
    )
    parser.add_argument(
        "--cmd",
        type=str,
        help="Executer une commande vocale (ex: --cmd 'dicte bonjour le monde')",
    )
    parser.add_argument(
        "--dispatch",
        nargs="+",
        metavar=("COMMANDE", "PARAM"),
        help="Dispatcher une commande avec parametres (ex: --dispatch dicte text='bonjour')",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lister toutes les commandes vocales disponibles",
    )
    parser.add_argument(
        "--list-methods",
        action="store_true",
        help="Lister toutes les methodes dict_ disponibles",
    )
    parser.add_argument(
        "--list-chars",
        action="store_true",
        help="Lister les caracteres speciaux disponibles",
    )
    parser.add_argument(
        "--list-alphabet",
        action="store_true",
        help="Lister l'alphabet phonetique",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Activer les logs detailles",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    # --- Lister les commandes ---
    if args.list:
        commands = VoiceDictation.list_commands()
        print(f"{'Commande':<30} {'Methode':<25} {'Description'}")
        print("=" * 90)
        for cmd in commands:
            aliases = ", ".join(cmd["aliases"]) if cmd["aliases"] else ""
            params = ", ".join(cmd["parametres"]) if cmd["parametres"] else ""
            desc = cmd["description"]
            if aliases:
                desc += f" (alias: {aliases})"
            if params:
                desc += f" [params: {params}]"
            print(f"{cmd['commande']:<30} {cmd['methode']:<25} {desc}")
        print(f"\nTotal : {len(commands)} commandes vocales")
        return

    # --- Lister les methodes ---
    if args.list_methods:
        methods = VoiceDictation.list_methods()
        print("Methodes dict_ disponibles :")
        print("=" * 40)
        for m in methods:
            doc = getattr(VoiceDictation, m).__doc__
            first_line = (doc or "").strip().split("\n")[0]
            print(f"  {m:<30} {first_line}")
        print(f"\nTotal : {len(methods)} methodes")
        return

    # --- Lister les caracteres speciaux ---
    if args.list_chars:
        chars = VoiceDictation.list_special_chars()
        print("Caracteres speciaux disponibles :")
        print("=" * 40)
        for name, char in chars.items():
            print(f"  {name:<25} -> {char}")
        print(f"\nTotal : {len(chars)} caracteres")
        return

    # --- Lister l'alphabet ---
    if args.list_alphabet:
        alpha = VoiceDictation.list_phonetic_alphabet()
        print("Alphabet phonetique :")
        print("=" * 40)
        for name, letter in alpha.items():
            print(f"  {name:<20} -> {letter}")
        print(f"\nTotal : {len(alpha)} entrees")
        return

    # --- Executer une commande ---
    if args.cmd:
        try:
            vd = VoiceDictation()
            result = vd.parse_and_execute(args.cmd)
            print(result)
        except RuntimeError as e:
            print(f"Erreur : {e}")
            raise SystemExit(1)
        return

    # --- Dispatcher ---
    if args.dispatch:
        cmd_name = args.dispatch[0]
        kwargs = {}
        for param in args.dispatch[1:]:
            if "=" in param:
                k, v = param.split("=", 1)
                kwargs[k] = v
        try:
            vd = VoiceDictation()
            result = vd.dispatch(cmd_name, **kwargs)
            print(result)
        except RuntimeError as e:
            print(f"Erreur : {e}")
            raise SystemExit(1)
        return

    parser.print_help()


def execute_dictation_command(text: str) -> dict:
    """Interface unifiee pour le voice_router."""
    try:
        vd = VoiceDictation()
        result = vd.parse_and_execute(text)
        if result and "inconnue" not in result.lower() and "erreur" not in result.lower():
            return {"success": True, "method": "dictation", "result": result, "confidence": 0.8}
    except Exception:
        pass
    return {"success": False, "method": "unknown", "result": f"Non reconnu: {text}", "confidence": 0.0}


if __name__ == "__main__":
    main()
