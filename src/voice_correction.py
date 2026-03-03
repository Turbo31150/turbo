"""JARVIS Voice Correction — Intelligent correction despite capture errors.

Pipeline: Raw STT → Nettoyage → Corrections locales → Phonetique →
          Fuzzy match → Suggestions → Correction IA → Execution
"""

from __future__ import annotations

import logging
import re
import threading
import unicodedata
from difflib import SequenceMatcher, get_close_matches
from functools import lru_cache
from typing import Any

logger = logging.getLogger("jarvis.voice_correction")

from src.commands import (
    COMMANDS, JarvisCommand, VOICE_CORRECTIONS,
    APP_PATHS, SITE_ALIASES, correct_voice_text,
)
from src.config import prepare_lmstudio_input, build_lmstudio_payload, build_ollama_payload


# ═══════════════════════════════════════════════════════════════════════════
# PHONETIC MAP — Sons francais similaires (Whisper confond souvent)
# ═══════════════════════════════════════════════════════════════════════════

# Groupes de sons qui se confondent en francais
PHONETIC_GROUPS: list[list[str]] = [
    ["ai", "e", "est", "et", "es", "ait", "ais"],
    ["au", "o", "eau", "haut", "oh"],
    ["an", "en", "ant", "ent", "amp", "emps"],
    ["on", "ont", "om"],
    ["in", "ain", "ein", "im"],
    ["ou", "oo", "oux"],
    ["eu", "oeu", "eux"],
    ["oi", "oie", "wa"],
    ["ch", "sh"],
    ["g", "j", "ge"],
    ["k", "c", "qu", "q"],
    ["s", "ss", "c", "ce"],
    ["z", "s"],
    ["f", "ph"],
    ["t", "th"],
    # Vague 2 — Anglicismes mal prononces en francais
    ["tion", "sion", "shion", "chion"],
    ["w", "ou", "oi"],
    ["x", "ks", "cs"],
    ["y", "i", "ee"],
    ["ck", "k", "que"],
    ["er", "eur", "aire"],
    ["ing", "igne", "ine"],
    # Vague 8 — Tech terms et consonnes anglaises
    ["th", "t", "d"],       # thread/tread, the/de
    ["sh", "ch", "sch"],    # shell/chell, schema
    ["dj", "j", "g"],       # Django, JSON
    ["ks", "x", "cks"],     # index, flex
    ["ts", "tz", "z"],      # typescript, hertz
    ["mp", "nb", "mb"],     # embed, number
]

# Mots-outils souvent rajoutes/enleves par le STT
FILLER_WORDS = {
    "euh", "hum", "hmm", "bah", "ben", "bon", "alors",
    "donc", "voila", "ok", "well", "so", "please",
    "s'il te plait", "s'il vous plait", "merci",
    "un peu", "juste", "peut-etre", "genre",
    "tu peux", "est-ce que tu peux", "peux-tu",
    "je veux", "je voudrais", "j'aimerais",
    "est-ce que", "est ce que",
    # Vague 2 — Fillers courants manquants
    "en fait", "du coup", "tu sais", "hey", "dis",
    "enfin", "quoi", "bref", "disons", "attends",
    "en gros", "comment dire", "tu vois", "voyons",
    "allez", "tiens", "dis moi", "dis-moi",
    "hey jarvis", "oh jarvis", "eh jarvis",
}

# Expansions de commandes implicites
IMPLICIT_COMMANDS: dict[str, str] = {
    "google": "cherche sur google",
    "youtube": "ouvre youtube",
    "gmail": "ouvre gmail",
    "chrome": "ouvre chrome",
    "comet": "ouvre comet",
    "terminal": "ouvre le terminal",
    "vscode": "ouvre vscode",
    "documents": "ouvre mes documents",
    "telechargements": "ouvre les telechargements",
    "bureau": "ouvre le bureau",
    "volume": "monte le volume",
    "mute": "coupe le son",
    "silence": "coupe le son",
    "screenshot": "capture ecran",
    "capture": "capture ecran",
    "scanner": "scanne le marche",
    "breakout": "detecte les breakouts",
    "pipeline": "lance le pipeline",
    "cluster": "statut du cluster",
    "aide": "aide",
    "stop": "stop",
    "status": "statut du cluster",
    # Nouvelles commandes implicites
    "bluetooth": "active le bluetooth",
    "parametres": "ouvre les parametres",
    "reglages": "ouvre les reglages",
    "emojis": "ouvre les emojis",
    "widgets": "ouvre les widgets",
    "notifications": "ouvre les notifications",
    "explorateur": "ouvre l'explorateur de fichiers",
    "wifi": "scan wifi",
    "positions": "mes positions",
    "signaux": "signaux en attente",
    "services": "liste les services",
    "save": "sauvegarde",
    "find": "recherche dans la page",
    "redo": "refais",
    "trading": "statut trading",
    # Vague 2 - Commandes implicites
    "micro": "coupe le micro",
    "camera": "parametres camera",
    "zoom": "zoom avant",
    "print": "imprime",
    "refresh": "actualise",
    "rename": "renomme",
    "delete": "supprime",
    "lock": "verrouille",
    "reunion": "mode reunion",
    "visio": "mode reunion",
    "focus": "mode focus",
    "presentation": "mode presentation",
    "musique": "mets de la musique",
    "diagnostic": "diagnostic complet",
    "monitoring": "monitoring complet",
    "optimisation": "optimise le pc",
    "stream": "mode stream",
    "gaming": "mode gaming",
    "dev": "mode dev",
    # Vague 3 - Accessibilite / Multimedia / Reseau
    "loupe": "active la loupe",
    "narrateur": "active le narrateur",
    "dictee": "lance la dictee",
    "contraste": "contraste eleve",
    "accessibilite": "parametres accessibilite",
    "incognito": "mode incognito",
    "historique": "historique chrome",
    "performance": "mode performance",
    "economie": "mode economie",
    "dns": "vide le cache dns",
    "vpn": "parametres vpn",
    "snap": "snap layout",
    "record": "enregistre l'ecran",
    "ipconfig": "montre l'ip",
    "proxy": "parametres proxy",
    "gamebare": "game bar",
    # Vague 4 - Multi-ecran / Focus / Disques / Taskbar
    "alarme": "ouvre les alarmes",
    "minuteur": "ouvre les alarmes",
    "timer": "ouvre les alarmes",
    "chronometre": "ouvre les alarmes",
    "disques": "info disques",
    "batterie": "parametres batterie",
    "heure": "parametres heure",
    "langue": "parametres langue",
    "souris": "parametres souris",
    "clavier": "parametres clavier",
    "comptes": "parametres comptes",
    "timeline": "historique activite",
    # Vague 5 - Securite / DevTools / Maintenance
    "antivirus": "ouvre la securite",
    "defender": "ouvre la securite",
    "firewall": "parametres pare-feu",
    "defrag": "defragmente",
    "hotspot": "active le hotspot",
    "miracast": "partage l'ecran",
    "pilotes": "gestionnaire de peripheriques",
    "drivers": "gestionnaire de peripheriques",
    "peripheriques": "gestionnaire de peripheriques",
    "partitions": "gestionnaire de disques",
    "autostart": "applications demarrage",
    "confidentialite": "parametres confidentialite",
    "desinstaller": "programmes installes",
    # Vague 6 - Personnalisation / Audio
    "imprimante": "parametres imprimantes",
    "wallpaper": "fond d'ecran",
    "polices": "polices",
    "themes": "themes windows",
    "sombre": "active le mode sombre",
    "clair": "active le mode clair",
    "regedit": "ouvre le registre",
    "hdr": "parametres hdr",
    "multitache": "parametres multitache",
    # Vague 7 - Reseau / Systeme avance
    "uptime": "depuis quand le pc tourne",
    "temperature": "temperature cpu",
    "netstat": "connexions actives",
    "sandbox": "ouvre la sandbox",
    "restauration": "restauration systeme",
    "backup": "sauvegarde windows",
    "ethernet": "parametres ethernet",
    "specs": "a propos du pc",
    "mac": "adresse mac",
    "sfc": "verifie les fichiers systeme",
    # Vague 8 - Docker / Git / Dev
    "docker": "liste les conteneurs",
    "conteneurs": "liste les conteneurs",
    "git": "git status",
    "pip": "pip list",
    "jupyter": "ouvre jupyter",
    "notebook": "ouvre jupyter",
    "n8n": "ouvre n8n",
    "workflows": "ouvre n8n",
    "profils wifi": "profils wifi",
    # Vague 9 - Apps / Clipboard / Systeme
    "paint": "ouvre paint",
    "obs": "ouvre obs",
    "vlc": "ouvre vlc",
    "clipboard": "lis le presse-papier",
    "path": "montre le path",
    "archives": "ouvre 7zip",
    "stream": "ouvre obs",
    "dessin": "ouvre paint",
    # Vague 10 - Onglets / Session / Ecrans
    "onglet": "nouvel onglet",
    "tab": "nouvel onglet",
    "hibernation": "hiberne",
    "heure": "quelle heure est-il",
    "date": "quelle date",
    "majuscules": "en majuscules",
    "minuscules": "en minuscules",
    "ecrans": "etends l'ecran",
    "dupliquer": "duplique l'ecran",
    # Vague 11 - Hardware / RAM / CPU
    "ram": "utilisation ram",
    "cpu": "utilisation cpu",
    "processeur": "info cpu",
    "batterie": "niveau de batterie",
    "bios": "info bios",
    "motherboard": "info carte mere",
    "gpu": "info gpu detaille",
    "ssd": "sante des disques",
    "meteo": "dis moi la meteo",
    "logs": "voir les logs",
    # Vague 12 - Chrome / Fenetres / Accessibilite
    "favoris": "ouvre les favoris",
    "bookmarks": "ouvre les favoris",
    "fullscreen": "plein ecran",
    "zoom": "zoom avant",
    "daltonien": "filtre de couleur",
    "captions": "sous-titres",
    # Vague 13 - Reseau avance / DNS / Ports
    "ports": "ports ouverts",
    "arp": "table arp",
    "nslookup": "nslookup",
    "routage": "table de routage",
    "ssl": "certificat ssl",
    "dns": "vide le cache dns",
    "ip publique": "mon ip publique",
    "partages": "partages reseau",
    # Vague 14 - Fichiers avances
    "doublons": "fichiers en double",
    "zip": "compresse",
    "hash": "hash de",
    "grep": "cherche dans les fichiers",
    "recents": "derniers fichiers modifies",
    "gros fichiers": "plus gros fichiers",
    # Vague 15 - IA / Cluster / Modeles
    "ollama": "statut ollama",
    "qwen": "info modele qwen",
    "whisper": "statut whisper",
    "embedding": "lance embedding",
    "finetune": "statut finetuning",
    "finetuning": "statut finetuning",
    "tokenizer": "info tokenizer",
    "inference": "lance inference",
    "modeles": "liste les modeles",
    "models": "liste les modeles",
    "vram": "utilisation vram",
    "cuda": "info cuda",
    "tenseurs": "info tenseurs",
    "weights": "info poids modele",
    "checkpoint": "dernier checkpoint",
    "epochs": "statut entrainement",
    "lora": "info lora",
    # Vague 16 - JARVIS / Dominos / Audit
    "domino": "liste les dominos",
    "dominos": "liste les dominos",
    "audit": "audit systeme",
    "heal": "heal cluster",
    "healing": "heal cluster",
    "dashboard": "ouvre le dashboard",
    "jarvis": "statut jarvis",
    "mcp": "statut mcp",
    "tools": "liste les outils",
    "outils": "liste les outils",
    "skills": "liste les skills",
    "commandes": "aide commandes",
    "corrections": "statistiques corrections vocales",
    "voix": "statut vocal",
    "tts": "test tts",
    "stt": "statut stt",
    "wakeword": "statut wakeword",
    # Vague 17 - Dev avance / CI / Tests
    "pytest": "lance les tests",
    "tests": "lance les tests",
    "lint": "lance le linter",
    "linter": "lance le linter",
    "mypy": "lance mypy",
    "uv": "uv sync",
    "npm": "npm install",
    "node": "version node",
    "python": "version python",
    "typescript": "compile typescript",
    "build": "lance le build",
    "ci": "statut ci",
    "coverage": "rapport couverture",
    "profiling": "lance le profiling",
    "benchmark": "lance benchmark cluster",
    "stress": "stress test cluster",
    # ── COMMAND ALIASES — shortened forms for common commands ──────────────
    "vol+": "monte le volume",
    "vol-": "baisse le volume",
    "vol up": "monte le volume",
    "vol down": "baisse le volume",
    "ss": "capture ecran",
    "sc": "capture ecran",
    "maj": "mets a jour",
    "update": "mets a jour",
    "restart": "redemarre",
    "reboot": "redemarre",
    "kill": "ferme l'application",
    "close": "ferme",
    "open": "ouvre",
    "run": "lance",
    "start": "lance",
    "exec": "lance",
    "ls": "liste les fichiers",
    "dir": "liste les fichiers",
    "pwd": "chemin actuel",
    "cls": "efface l'ecran",
    "clear": "efface l'ecran",
    "top": "utilisation cpu",
    "htop": "utilisation cpu",
    "df": "info disques",
    "free": "utilisation ram",
    "ps": "liste les processus",
    "up": "monte le volume",
    "down": "baisse le volume",
    # Vague 18 — Cluster / Maintenance rapide
    "sante": "health check",
    "check": "health check",
    "bilan": "bilan session",
    "rapport": "rapport du jour",
    "diagnostique": "diagnostic complet",
    "diagnostiquer": "diagnostic complet",
    "maintenance": "maintenance bases",
    "vacuum": "vacuum les bases",
    "compacte": "vacuum les bases",
    "nettoyer": "nettoie les logs",
    "restore": "restaure le backup",
    "restaure": "restaure le backup",
    "backuper": "backup les bases",
    "sauvegarde": "backup les bases",
    "sync": "synchronise le cluster",
    "synchronise": "synchronise le cluster",
    # Vague 19 — Trading quick actions
    "marche": "scan trading",
    "scanner le marche": "scan trading",
    "balance": "balance trading",
    "pnl": "pnl du jour",
    "drawdown": "analyse drawdown",
    "close all": "ferme les positions",
    "close tout": "ferme les positions",
    "risk": "analyse risque",
    "tp sl": "configure tp sl",
    "take profit": "configure tp sl",
    "stoploss": "configure tp sl",
    "signaux trading": "signaux en attente",
    "best pair": "meilleure paire",
    "backtest": "lance backtest",
    # Vague 20 — Domino quick launch
    "briefing": "lance briefing matin",
    "briefing matin": "lance briefing matin",
    "mode nuit": "mode nuit",
    "bonne nuit": "mode nuit",
    "mode weekend": "mode weekend",
    "fin de journee": "mode nuit",
    "mode pause": "mode pause",
    "pause": "mode pause",
    "mode coding": "mode coding",
    "mode dev": "mode coding",
    "mode focus": "mode focus",
    "concentration": "mode focus",
    "pomodoro": "lance pomodoro",
    "securite": "scan securite",
    "hotfix": "deploie hotfix",
    "rollback": "rollback derniere version",
    "deploy": "deploie en production",
    "deployer": "deploie en production",
    "consensus": "consensus cluster",
    # Vague 21 — Automation / Session shortcuts
    "commit": "auto commit",
    "push": "git push",
    "commite": "auto commit",
    "pousse": "pousse le code",
    "snapshot": "sauvegarde la session",
    "session": "statut session",
    "env": "verifie l'environnement",
    "rapport": "rapport systeme complet",
    "report": "rapport systeme complet",
    "etat": "etat global",
    "global": "etat global",
    "complet": "rapport systeme complet",
    # Vague 22 — Integration / Modeles shortcuts
    "ollama models": "liste les modeles ollama",
    "lm models": "liste les modeles lm studio",
    "lmstudio models": "liste les modeles lm studio",
    "n8n": "statut n8n",
    "workflows": "statut n8n",
    "csv": "exporte la base en csv",
    "export": "exporte les metriques",
    "comptage": "combien de lignes en base",
    "rows": "combien de lignes en base",
    "lignes": "combien de lignes en base",
    "logs": "analyse les logs",
    "erreurs": "analyse les logs",
    # Vague 23 — Actions rapides vocales
    "rebalance": "reequilibre le cluster",
    "equilibre": "reequilibre le cluster",
    "watch": "surveille les temperatures",
    "surveille": "surveille les temperatures",
    "quick test": "test rapide",
    "syntax": "test rapide",
    "init": "initialise un projet python",
    "nouveau": "initialise un projet python",
    "auto push": "pousse le code",
    "auto save": "sauvegarde la session",
}


# ═══════════════════════════════════════════════════════════════════════════
# TEXT CLEANING
# ═══════════════════════════════════════════════════════════════════════════

def normalize_text(text: str) -> str:
    """Normalize text: lowercase, remove accents, clean punctuation."""
    text = text.lower().strip()
    # Remove common punctuation
    text = re.sub(r"[.,!?;:\"'()\[\]{}<>]", "", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@lru_cache(maxsize=512)
def remove_accents(text: str) -> str:
    """Remove accents from text for fuzzy comparison."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ═══════════════════════════════════════════════════════════════════════════
# PARAMETER EXTRACTION — Extract named params from voice input
# ═══════════════════════════════════════════════════════════════════════════

# Known parameter patterns for voice extraction
_PARAM_PATTERNS: list[tuple[str, str, str]] = [
    # pattern, param_name, transform
    (r"\b(etoile|jarvis|sniper|finetuning)(?:\.db)?\b", "db", "{0}.db"),
    (r"\b(\d+)\s*(?:minutes?|min)\b", "minutes", "{0}"),
    (r"\b(\d+)\s*(?:secondes?|sec|s)\b", "seconds", "{0}"),
    (r"\b(BTC|ETH|SOL|SUI|PEPE|DOGE|XRP|ADA|AVAX|LINK)\b", "coin", "{0}"),
    (r"\bmodele?\s+(\S+)\b", "modele", "{0}"),
    (r"\bnoeud\s+(M[123]|OL1|GEMINI|CLAUDE)\b", "node", "{0}"),
    (r"\b(M[123]|OL1|GEMINI|CLAUDE)\b", "node", "{0}"),
    (r"\bcategorie?\s+(\w+)\b", "category", "{0}"),
    (r"\b(\d{1,3})\s*(?:pour\s*cent|pourcent|%)\b", "percentage", "{0}"),
    (r"\b(haute?|basse?|normal|critique|urgent)\b", "priority", "{0}"),
]


def extract_params(text: str) -> dict[str, str]:
    """Extract named parameters from voice input text."""
    params: dict[str, str] = {}
    text_lower = text.lower()
    for pattern, name, template in _PARAM_PATTERNS:
        m = re.search(pattern, text_lower, re.IGNORECASE)
        if m:
            params[name] = template.format(m.group(1))
    return params


def remove_fillers(text: str) -> str:
    """Remove filler words and politeness from voice input."""
    words = text.split()
    cleaned = []
    skip_next = False
    for i, word in enumerate(words):
        if skip_next:
            skip_next = False
            continue
        # Check single word fillers
        if word in FILLER_WORDS:
            continue
        # Check two-word fillers
        if i < len(words) - 1:
            pair = f"{word} {words[i+1]}"
            if pair in FILLER_WORDS:
                skip_next = True
                continue
        cleaned.append(word)
    return " ".join(cleaned)


def extract_action_intent(text: str) -> str:
    """Extract the core action intent from verbose voice input.

    "est-ce que tu peux ouvrir chrome s'il te plait" → "ouvrir chrome"
    "j'aimerais que tu cherches bitcoin sur google" → "cherche bitcoin sur google"
    """
    text = remove_fillers(text)

    # Remove leading "que tu" / "de"
    text = re.sub(r"^que tu\s+", "", text)
    text = re.sub(r"^de\s+", "", text)

    # Normalize verb forms → imperative
    replacements = [
        (r"\bouvrir\b", "ouvre"),
        (r"\blancer\b", "lance"),
        (r"\bchercher\b", "cherche"),
        (r"\brechercher\b", "recherche"),
        (r"\bnaviguer\b", "navigue"),
        (r"\bfermer\b", "ferme"),
        (r"\bmettre\b", "mets"),
        (r"\baugmenter\b", "augmente"),
        (r"\bbaisser\b", "baisse"),
        (r"\bcouper\b", "coupe"),
        (r"\bverrouiller\b", "verrouille"),
        (r"\beteindre\b", "eteins"),
        (r"\bredemarrer\b", "redemarre"),
        (r"\bscanner\b", "scanne"),
        (r"\bdetecter\b", "detecte"),
        (r"\bafficher\b", "affiche"),
        (r"\bmonter\b", "monte"),
        # Vague 2 — Verbes manquants
        (r"\bactiver\b", "active"),
        (r"\bdesactiver\b", "desactive"),
        (r"\banalyser\b", "analyse"),
        (r"\btester\b", "teste"),
        (r"\bdeployer\b", "deploie"),
        (r"\boptimiser\b", "optimise"),
        (r"\bconfigurer\b", "configure"),
        (r"\bverifier\b", "verifie"),
        (r"\barreter\b", "arrete"),
        (r"\bdemarrer\b", "demarre"),
        (r"\bcreer\b", "cree"),
        (r"\bsupprimer\b", "supprime"),
        (r"\btelecharger\b", "telecharge"),
        (r"\binstaller\b", "installe"),
        (r"\bdesinstaller\b", "desinstalle"),
        (r"\bsauvegarder\b", "sauvegarde"),
        (r"\brestaurer\b", "restaure"),
        (r"\bnettoyer\b", "nettoie"),
        (r"\bdiagnostiquer\b", "diagnostique"),
        (r"\bcompiler\b", "compile"),
        # Vague 3 — Verbes cluster/devops/trading
        (r"\bexporter\b", "exporte"),
        (r"\bmigrer\b", "migre"),
        (r"\bbenchmarker\b", "benchmark"),
        (r"\bswapper\b", "swap"),
        (r"\bbroadcaster\b", "broadcast"),
        (r"\bsynchroniser\b", "synchronise"),
        (r"\bsyncer\b", "sync"),
        (r"\brollbacker\b", "rollback"),
        (r"\blogger\b", "log"),
        (r"\barchiver\b", "archive"),
        (r"\brebalancer\b", "rebalance"),
        (r"\bthrottler\b", "throttle"),
        (r"\bmonitor(?:er)?\b", "monitor"),
        (r"\bauditer\b", "audite"),
        (r"\bprofiler\b", "profile"),
        (r"\bbackuper\b", "backup"),
        # Vague 4 — Verbes automation/integration
        (r"\bcommiter\b", "commite"),
        (r"\bpusher\b", "push"),
        (r"\bpouvoir\b", ""),
        (r"\breequilibrer\b", "reequilibre"),
        (r"\bsurveiller\b", "surveille"),
        (r"\binitialiser\b", "initialise"),
        (r"\bexecuter\b", "execute"),
        (r"\bimporter\b", "importe"),
        (r"\brafraichir\b", "rafraichis"),
        (r"\brelancer\b", "relance"),
        (r"\brechercher\b", "recherche"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)

    return text.strip()


# ═══════════════════════════════════════════════════════════════════════════
# PHONETIC SIMILARITY
# ═══════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1024)
def phonetic_normalize(word: str) -> str:
    """Reduce a French word to its phonetic skeleton.

    Handles accented characters (é/è/ê/ç/œ) before stripping,
    preserving French phonetic distinctions.
    """
    word = word.lower()

    # Pre-accent phonetic mappings (before remove_accents strips them)
    accent_map = [
        ("œu", "eu"), ("œ", "eu"),  # cœur → ceur
        ("ç", "s"),                   # français → fransais
        ("ë", "e"), ("ï", "i"),      # naïf → naif
    ]
    for old, new in accent_map:
        word = word.replace(old, new)

    word = remove_accents(word)

    # Apply phonetic reductions
    reductions = [
        (r"eau", "o"), (r"au", "o"), (r"ai", "e"), (r"ei", "e"),
        (r"ou", "u"), (r"ph", "f"), (r"th", "t"), (r"ch", "sh"),
        (r"qu", "k"), (r"gu", "g"), (r"gn", "n"),
        (r"tion", "sion"), (r"ce", "se"), (r"ci", "si"),
        (r"ge", "je"), (r"gi", "ji"),
        # French-specific reductions
        (r"eur$", "er"), (r"eux$", "eu"),  # chercheur → chercher
        (r"ment$", "man"),                  # rapidement → rapidman
        (r"ain", "en"), (r"ein", "en"),    # main → men
        (r"an", "en"),                      # France → frense
        (r"oi", "wa"),                      # voix → vwa
        (r"in", "en"),                      # fin → fen
        # Double consonants → single
        (r"(.)\1+", r"\1"),
        # Silent endings
        (r"[esxzt]$", ""),
    ]
    for pattern, replacement in reductions:
        word = re.sub(pattern, replacement, word)

    return word


def phonetic_similarity(a: str, b: str) -> float:
    """Compare two strings phonetically."""
    pa = phonetic_normalize(a)
    pb = phonetic_normalize(b)
    return SequenceMatcher(None, pa, pb).ratio()


def _trigrams(s: str) -> set[str]:
    """Extract character trigrams from a string for fuzzy matching."""
    s = f"  {s} "  # pad for edge trigrams
    return {s[i:i+3] for i in range(len(s) - 2)}


def trigram_similarity(a: str, b: str) -> float:
    """Jaccard similarity of character trigrams — robust to typos and word order."""
    ta, tb = _trigrams(a.lower()), _trigrams(b.lower())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# ═══════════════════════════════════════════════════════════════════════════
# SUGGESTION ENGINE
# ═══════════════════════════════════════════════════════════════════════════

_command_usage_cache: dict[str, int] = {}
_command_usage_loaded = False

# Pre-computed trigger data for fast suggestion scoring (built lazily)
_trigger_cache: list[tuple[JarvisCommand, str, str, set[str]]] = []
_trigger_cache_built = False


def _build_trigger_cache() -> None:
    """Pre-compute normalized triggers for all commands (called once)."""
    global _trigger_cache_built
    if _trigger_cache_built:
        return
    _trigger_cache_built = True
    for cmd in COMMANDS:
        for trigger in cmd.triggers:
            clean = normalize_text(trigger.replace("{", "").replace("}", ""))
            no_acc = remove_accents(clean)
            words = set(clean.split())
            _trigger_cache.append((cmd, no_acc, clean, words))
    logger.info("Trigger cache built: %d entries from %d commands", len(_trigger_cache), len(COMMANDS))


def _load_command_usage() -> None:
    """Load command usage counts from DB for popularity boost (lazy, once)."""
    global _command_usage_loaded
    if _command_usage_loaded:
        return
    _command_usage_loaded = True
    try:
        import sqlite3
        import os
        db_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "jarvis.db"))
        if not os.path.exists(db_path):
            return
        with sqlite3.connect(db_path, timeout=5) as conn:
            rows = conn.execute(
                "SELECT command_name, COUNT(*) as cnt FROM command_history "
                "GROUP BY command_name ORDER BY cnt DESC LIMIT 200"
            ).fetchall()
            for name, cnt in rows:
                _command_usage_cache[name] = cnt
    except (sqlite3.Error, OSError) as exc:
        logger.debug("Failed to load command usage: %s", exc)


def get_suggestions(text: str, max_results: int = 3) -> list[tuple[JarvisCommand, float]]:
    """Get command suggestions ranked by combined similarity score.

    5 factors: text sim (30%) + phonetic (20%) + trigram (15%) + keyword (20%) + popularity (15%).
    Uses pre-computed trigger cache for performance (~2000 commands).
    """
    _load_command_usage()
    _build_trigger_cache()
    max_usage = max(_command_usage_cache.values()) if _command_usage_cache else 1

    text_normalized = normalize_text(text)
    text_no_accents = remove_accents(text_normalized)
    text_words = set(text_normalized.split())

    # Track best score per command (avoid duplicates)
    cmd_scores: dict[str, tuple[JarvisCommand, float]] = {}

    for cmd, trigger_no_acc, trigger_clean, trigger_words in _trigger_cache:
        # 1. Direct text similarity (30%)
        text_sim = SequenceMatcher(None, text_no_accents, trigger_no_acc).ratio()

        # 2. Phonetic similarity (20%)
        phon_sim = phonetic_similarity(text_normalized, trigger_clean)

        # 3. Trigram similarity (15%)
        tri_sim = trigram_similarity(text_no_accents, trigger_no_acc)

        # 4. Keyword overlap (20%)
        if trigger_words:
            common = text_words & trigger_words
            keyword_sim = len(common) / len(trigger_words)
        else:
            keyword_sim = 0.0

        # 5. Popularity boost (15%)
        usage = _command_usage_cache.get(cmd.name, 0)
        pop_score = min(1.0, usage / max_usage) if max_usage > 0 else 0.0

        score = (text_sim * 0.30) + (phon_sim * 0.20) + (tri_sim * 0.15) + (keyword_sim * 0.20) + (pop_score * 0.15)

        if score > 0.30:
            existing = cmd_scores.get(cmd.name)
            if existing is None or score > existing[1]:
                cmd_scores[cmd.name] = (cmd, score)

    scored = sorted(cmd_scores.values(), key=lambda x: x[1], reverse=True)
    return scored[:max_results]


def format_suggestions(suggestions: list[tuple[JarvisCommand, float]]) -> str:
    """Format suggestions for voice output."""
    if not suggestions:
        return "Je n'ai pas compris. Dis 'aide' pour la liste des commandes."

    lines = ["Tu voulais dire:"]
    for i, (cmd, score) in enumerate(suggestions, 1):
        trigger = cmd.triggers[0]
        lines.append(f"  {i}. {trigger} ({cmd.description})")
    lines.append("Repete la commande ou dis le numero.")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# DB-BACKED CORRECTIONS LOADER — Enrich VOICE_CORRECTIONS from database
# ═══════════════════════════════════════════════════════════════════════════

_db_corrections_loaded = False


def load_db_corrections() -> int:
    """Load voice corrections from etoile.db and jarvis.db into VOICE_CORRECTIONS.

    Returns number of new corrections added (not already in dict).
    """
    global _db_corrections_loaded
    if _db_corrections_loaded:
        return 0
    _db_corrections_loaded = True
    added = 0
    try:
        import sqlite3
        import os
        base = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
        for db_name in ("jarvis.db", "etoile.db"):
            db_path = os.path.join(base, "data", db_name)
            if not os.path.exists(db_path):
                continue
            with sqlite3.connect(db_path, timeout=5) as conn:
                # Check if table exists
                tables = [r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='voice_corrections'"
                ).fetchall()]
                if not tables:
                    continue
                rows = conn.execute(
                    "SELECT wrong, corrected FROM voice_corrections WHERE wrong IS NOT NULL AND corrected IS NOT NULL"
                ).fetchall()
                for wrong, corrected in rows:
                    key = wrong.lower().strip()
                    if key and key not in VOICE_CORRECTIONS:
                        VOICE_CORRECTIONS[key] = corrected.lower().strip()
                        added += 1
        if added:
            logger.info("Loaded %d DB voice corrections into dict (total: %d)", added, len(VOICE_CORRECTIONS))
    except (ImportError, OSError) as exc:
        logger.debug("Failed to load DB corrections: %s", exc)
    return added


# ═══════════════════════════════════════════════════════════════════════════
# HIT COUNT TRACKING
# ═══════════════════════════════════════════════════════════════════════════

_db_lock = threading.Lock()


def _increment_voice_correction_hits(original: str, corrected: str) -> None:
    """Increment hit_count for words that were corrected by the dictionary."""
    orig_words = original.lower().split()
    corr_words = corrected.lower().split()
    changed = [w for w, c in zip(orig_words, corr_words) if w != c]
    if not changed:
        return
    try:
        import sqlite3
        import os
        base = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
        with _db_lock:
            for db_name in ("jarvis.db", "etoile.db"):
                db_path = os.path.join(base, "data", db_name)
                if not os.path.exists(db_path):
                    continue
                with sqlite3.connect(db_path, timeout=10) as conn:
                    for wrong_word in changed:
                        conn.execute(
                            "UPDATE voice_corrections SET hit_count = hit_count + 1 WHERE wrong = ?",
                            (wrong_word,),
                        )
    except sqlite3.Error as exc:
        logger.debug("voice_correction hit_count update failed: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════
# FULL CORRECTION PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

async def full_correction_pipeline(
    raw_text: str,
    use_ia: bool = True,
    ia_url: str = "",
    ia_model: str = "",
) -> dict[str, Any]:
    """Complete voice correction pipeline.

    Returns dict with:
    - raw: original text
    - cleaned: after local cleaning
    - corrected: after all corrections
    - intent: extracted action intent
    - command: matched JarvisCommand or None
    - params: extracted parameters
    - confidence: match confidence (0-1)
    - suggestions: alternative commands if low confidence
    - method: how the match was found
    - domino: matched DominoPipeline (if method is "domino")
    """
    # Load DB corrections on first call (lazy, once)
    load_db_corrections()

    # Resolve defaults from config at runtime
    if not ia_url or not ia_model:
        try:
            from src.config import config as _cfg
            ol = _cfg.get_ollama_node("OL1")
            if ol and not ia_url:
                ia_url = ol.url
            if ol and not ia_model:
                ia_model = ol.default_model
        except ImportError:
            pass
    if not ia_url:
        ia_url = "http://127.0.0.1:11434"
    if not ia_model:
        ia_model = "qwen3:1.7b"

    result: dict[str, Any] = {
        "raw": raw_text,
        "cleaned": "",
        "corrected": "",
        "intent": "",
        "command": None,
        "params": {},
        "confidence": 0.0,
        "suggestions": [],
        "method": "none",
    }

    # Step 1: Basic normalization
    cleaned = normalize_text(raw_text)
    result["cleaned"] = cleaned

    # Step 1.5: Extract parameters from voice input (before further processing)
    voice_params = extract_params(cleaned)
    if voice_params:
        result["params"].update(voice_params)

    # Step 2: Check implicit commands (single-word AND multi-word)
    single = cleaned.strip()
    if single in IMPLICIT_COMMANDS:
        cleaned = IMPLICIT_COMMANDS[single]
        result["method"] = "implicit"
    else:
        # Check multi-word implicit commands (longest match first)
        # Also match as prefix: "scanner le marche BTC" matches "scanner le marche"
        for key in sorted(IMPLICIT_COMMANDS, key=len, reverse=True):
            if " " in key and (single == key or single.startswith(key + " ")):
                extra = single[len(key):].strip() if single != key else ""
                cleaned = IMPLICIT_COMMANDS[key]
                if extra:
                    cleaned = f"{cleaned} {extra}"  # Carry extra words
                result["method"] = "implicit"
                break

    # Step 3: Apply local voice corrections dictionary
    corrected = correct_voice_text(cleaned)
    result["corrected"] = corrected

    # Step 3.1: Track which corrections were applied for hit_count
    if corrected != cleaned:
        _increment_voice_correction_hits(cleaned, corrected)

    # Step 3.5: EARLY EXIT — If local match is high confidence, skip IA entirely
    from src.commands import match_command
    early_intent = extract_action_intent(corrected)
    early_cmd, early_params, early_score = match_command(early_intent)
    if early_cmd and early_score >= 0.85:
        result["command"] = early_cmd
        result["params"] = early_params
        result["confidence"] = early_score
        result["intent"] = early_intent
        result["method"] = "local_fast"
        return result

    # Also check implicit commands with high confidence
    if single in IMPLICIT_COMMANDS and result["method"] == "implicit":
        impl_intent = extract_action_intent(IMPLICIT_COMMANDS[single])
        impl_cmd, impl_params, impl_score = match_command(impl_intent)
        if impl_cmd:
            result["command"] = impl_cmd
            result["params"] = impl_params
            result["confidence"] = max(impl_score, 0.95)
            result["intent"] = impl_intent
            result["method"] = "implicit_fast"
            return result

    # Step 4: IA correction EARLY — let LM Studio fix transcription errors FIRST
    ia_corrected = None
    if use_ia:
        try:
            ia_corrected = await _ia_correct(corrected, ia_url, ia_model)
            if ia_corrected and ia_corrected.lower().strip() != corrected.lower().strip():
                result["corrected"] = ia_corrected
                corrected = ia_corrected
        except (OSError, ValueError, TimeoutError, KeyError, ImportError) as exc:
            logger.debug("IA correction failed for %r: %s", corrected, exc)

    # Step 5: Extract action intent (remove fillers, normalize verbs)
    intent = extract_action_intent(corrected)
    result["intent"] = intent

    # Step 6: Try exact/fuzzy match with commands
    from src.commands import match_command
    cmd, params, score = match_command(intent)

    if cmd and score >= 0.70:
        result["command"] = cmd
        result["params"] = params
        result["confidence"] = score
        result["method"] = "ia_direct" if ia_corrected else "direct"
        return result

    # Step 7: Try phonetic matching
    best_phon_cmd = None
    best_phon_score = 0.0
    for c in COMMANDS:
        for trigger in c.triggers:
            clean_trigger = normalize_text(trigger.replace("{", "").replace("}", ""))
            ps = phonetic_similarity(intent, clean_trigger)
            if ps > best_phon_score:
                best_phon_score = ps
                best_phon_cmd = c

    if best_phon_cmd and best_phon_score >= 0.70:
        result["command"] = best_phon_cmd
        result["params"] = {}
        result["confidence"] = best_phon_score
        result["method"] = "phonetic"
        return result

    # Step 8: If IA corrected but still no match, try matching the IA intent directly
    if ia_corrected:
        ia_intent = extract_action_intent(ia_corrected)
        if ia_intent != intent:
            cmd3, params3, score3 = match_command(ia_intent)
            if cmd3 and score3 >= 0.55:
                result["command"] = cmd3
                result["params"] = params3
                result["confidence"] = score3
                result["method"] = "ia_rematch"
                return result

    # Step 9: Get suggestions
    suggestions = get_suggestions(intent)
    result["suggestions"] = suggestions

    if suggestions and suggestions[0][1] >= 0.55:
        top_cmd, top_score = suggestions[0]
        result["command"] = top_cmd
        result["confidence"] = top_score
        result["method"] = "suggestion"
        return result

    # Step 10: Try domino pipeline matching (cascades vocales)
    try:
        from src.domino_pipelines import find_domino
        # Try intent first, then full corrected text as fallback
        domino = find_domino(intent)
        if not domino and corrected != intent:
            domino = find_domino(corrected)
        if domino:
            result["domino"] = domino
            result["confidence"] = 0.80
            result["method"] = "domino"
            return result
    except ImportError:
        pass

    # No match — will be sent to Claude as freeform
    result["confidence"] = max(score, best_phon_score)
    result["method"] = "freeform"
    return result


_vc_http = None
_vc_http_lock = __import__("asyncio").Lock()


async def _get_vc_http():
    """Lazy shared httpx client for voice correction (avoids import at module level)."""
    global _vc_http
    async with _vc_http_lock:
        if _vc_http is not None and not _vc_http.is_closed:
            return _vc_http
        import httpx
        _vc_http = httpx.AsyncClient(timeout=5, limits=httpx.Limits(max_keepalive_connections=5))
        return _vc_http


async def _ia_correct(text: str, url: str, model: str) -> str:
    """Use Ollama qwen3:1.7b (fast, 1.36 GB) to correct voice transcription.

    Primary: Ollama qwen3:1.7b (lightweight, always loaded, <1s)
    Fallback: LM Studio M1/qwen3-8b (fast, accurate)
    """
    from src.config import config
    prompt = (
        "Tu es le correcteur ORTHOGRAPHIQUE de JARVIS.\n"
        "REGLE ABSOLUE: corrige UNIQUEMENT les fautes d'orthographe et de grammaire.\n"
        "NE CHANGE JAMAIS le sens, NE RAJOUTE JAMAIS de mots, NE MODIFIE PAS l'intention.\n"
        "Exemples:\n"
        "- 'ouvre moa les chart mexc' → 'ouvre moi les charts mexc'\n"
        "- 'ferm tout les fenaitre' → 'ferme toutes les fenetres'\n"
        "- 'statu du clusteur' → 'statut du cluster'\n"
        "- 'repete' → 'repete'\n"
        "- 'ouvre youtube' → 'ouvre youtube'\n"
        "- 'mets youtube' → 'mets youtube'\n"
        "- 'kel heurre il ait' → 'quelle heure il est'\n"
        "Reponds UNIQUEMENT avec le texte corrige, RIEN d'autre. Pas de /no_think.\n\n"
        f"Texte: {text}"
    )
    messages = [{"role": "user", "content": prompt}]
    # Primary: Ollama qwen3:1.7b (fast, lightweight, always available)
    ol = config.get_ollama_node("OL1")
    import httpx
    if ol:
        try:
            c = await _get_vc_http()
            r = await c.post(
                f"{ol.url}/api/chat",
                json=build_ollama_payload(
                    model, messages, temperature=0.1, num_predict=200,
                ),
            )
            r.raise_for_status()
            return r.json()["message"]["content"].strip()
        except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
            logger.debug("OL1 correction fallback failed: %s", exc)
    # Fallback: LM Studio M1 (qwen3-8b — fast and accurate)
    node = config.get_node("M1")
    if node:
        try:
            c = await _get_vc_http()
            r = await c.post(
                f"{node.url}/api/v1/chat",
                json=build_lmstudio_payload(
                    node.default_model,
                    prepare_lmstudio_input(text, node.name, node.default_model),
                    temperature=0.1, max_output_tokens=200,
                    system_prompt=messages[0]["content"] if messages and messages[0]["role"] == "system" else "",
                ),
                headers=node.auth_headers,
            )
            r.raise_for_status()
            from src.tools import extract_lms_output
            return extract_lms_output(r.json()).strip()
        except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
            logger.debug("M1 correction fallback failed: %s", exc)
    return text


# ═══════════════════════════════════════════════════════════════════════════
# VOICE SESSION STATE — Track conversation context
# ═══════════════════════════════════════════════════════════════════════════

class VoiceSession:
    """Track voice session state for multi-turn correction (thread-safe)."""

    # Anaphoric references that refer to the last command
    _REPEAT_PHRASES = {
        "refais", "relance", "encore", "pareil", "la meme chose",
        "meme chose", "repete", "fais le encore", "lance ca",
        "fais ca", "recommence", "de nouveau",
    }

    def __init__(self):
        self._lock = threading.Lock()
        self.last_suggestions: list[tuple[JarvisCommand, float]] = []
        self.last_raw: str = ""
        self.last_command: JarvisCommand | None = None
        self.last_params: dict = {}
        self.correction_count: int = 0
        self.history: list[str] = []

    def is_selecting_suggestion(self, text: str) -> JarvisCommand | None:
        """Check if user is selecting from previous suggestions by number."""
        text = text.strip()
        if text in ("1", "un", "premier", "premiere", "la premiere", "le premier"):
            idx = 0
        elif text in ("2", "deux", "deuxieme", "la deuxieme", "le deuxieme"):
            idx = 1
        elif text in ("3", "trois", "troisieme", "la troisieme", "le troisieme"):
            idx = 2
        else:
            return None

        if idx < len(self.last_suggestions):
            return self.last_suggestions[idx][0]
        return None

    def is_repeat_request(self, text: str) -> JarvisCommand | None:
        """Check if user wants to repeat the last command."""
        if text.strip().lower() in self._REPEAT_PHRASES and self.last_command:
            return self.last_command
        return None

    def is_confirmation(self, text: str) -> bool:
        """Check if user is confirming."""
        confirms = {"oui", "yes", "ok", "confirme", "valide", "go", "lance", "d'accord", "daccord", "ouais", "yep", "correct", "exactement", "c'est ca"}
        return text.strip().lower() in confirms

    def is_denial(self, text: str) -> bool:
        """Check if user is denying/canceling."""
        denials = {"non", "no", "annule", "annuler", "pas ca", "non merci", "nan", "nope", "stop", "arrete"}
        return text.strip().lower() in denials

    def record_execution(self, cmd: JarvisCommand, params: dict | None = None):
        """Record a successfully executed command for context carry."""
        with self._lock:
            self.last_command = cmd
            self.last_params = params or {}

    def add_to_history(self, text: str):
        """Add corrected text to history for context (thread-safe)."""
        with self._lock:
            self.history.append(text)
            if len(self.history) > 10:
                self.history.pop(0)


# ═══════════════════════════════════════════════════════════════════════════
# DOMINO EXECUTION — Wire domino result into live execution
# ═══════════════════════════════════════════════════════════════════════════

def execute_domino_result(pipeline_result: dict) -> dict | None:
    """Execute a domino pipeline found by full_correction_pipeline().

    Call this after full_correction_pipeline() when result["method"] == "domino".
    Returns DominoExecutor.run() result dict or None if no domino found.
    """
    domino = pipeline_result.get("domino")
    if domino is None:
        return None

    try:
        from src.domino_executor import DominoExecutor
        executor = DominoExecutor()
        result = executor.run(domino)
        logger.info(
            "Domino %s executed: %d/%d PASS in %.0fms",
            result["domino_id"], result["passed"], result["total_steps"], result["total_ms"],
        )
        return result
    except (ImportError, OSError, ValueError, RuntimeError) as e:
        logger.error("Domino execution failed: %s", e)
        return {"error": str(e)}
