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
    # Vague 9 — Termes IA / Cluster / Noms de modeles
    ["kw", "qu", "q"],      # qwen/kwen
    ["ai", "aille", "eye"],  # gemini-ai, eye
    ["st", "sst", "str"],   # stream, mistral
    ["oss", "os", "hausse"], # gpt-oss
    ["dev", "dif", "div"],   # devstral, diff
    ["ll", "l", "el"],       # ollama, llm
    ["ck", "k", "g"],        # docker, kubernetes
    # Vague 10 — Programming terms phonetics
    ["py", "pi", "pie"],     # python, pytest
    ["js", "jss", "jis"],    # javascript, nodejs
    ["sql", "quel", "kuel"], # sql, mysql
    ["api", "aille pi aille", "epi"],
    ["http", "atch", "htp"],
    ["ssh", "esse ash", "esh"],
    ["git", "gite", "jit"],  # git/github
    ["npm", "ene pe em", "npeam"],
    # Vague 11 — Frameworks / Libs phonetiques
    ["react", "riate", "rias"],
    ["vue", "viou", "viu"],
    ["angular", "angulair", "angulaire"],
    ["django", "jangau", "djang"],
    ["flask", "flaske", "flasque"],
    ["next", "nexte", "neste"],
    ["express", "expresse", "expres"],
    # Vague 12 — Cloud services phonetiques
    ["aws", "awe", "a double v"],
    ["azure", "azoure", "ajure"],
    ["gcp", "jecipi", "g c p"],
    ["docker", "dockeur", "dokeur"],
    ["kube", "coube", "cube"],
    ["helm", "elme", "healme"],
    # Vague 13 — ML / Data Science phonetiques
    ["tensor", "tenseur", "tenzor"],
    ["epoch", "epoque", "epok"],
    ["batch", "batche", "bache"],
    ["model", "modele", "modul"],
    ["train", "traine", "trene"],
    ["loss", "losse", "los"],
    ["weight", "ouaite", "weite"],
    # Vague 14 — Kubernetes / Containers phonetiques
    ["kubectl", "cube control", "kube ctl", "cubectl"],
    ["docker", "dokeur", "doker"],
    ["kubernetes", "cube air nette", "kubernete"],
    ["helm", "elme", "helme"],
    ["ingress", "inne gresse", "ingrais"],
    ["prometheus", "pro me te us", "promethee"],
    ["grafana", "graffana", "grafanna"],
    # Vague 15 — Cloud / IaaS / Git avance phonetiques
    ["terraform", "terre a forme", "teraforme"],
    ["vercel", "ver celle", "vercelle"],
    ["netlify", "nette li faille", "netlifi"],
    ["rebase", "ri baise", "rebaze"],
    ["squash", "scouache", "skouash"],
    ["copilot", "co pilote", "copilotte"],
    ["neovim", "neo vim", "neovime"],
    # Vague 16 — Testing / Data / Architecture phonetiques
    ["pytest", "pie test", "piteste"],
    ["cypress", "si presse", "cypresse"],
    ["selenium", "sele nium", "selenioum"],
    ["kafka", "cafqua", "kafqua"],
    ["redis", "re disse", "redisse"],
    ["mongodb", "mongo de be", "mongodi bi"],
    ["hadoop", "a doupe", "hadoupe"],
    # Vague 17 — Mobile / DevOps / IA / Crypto phonetiques
    ["flutter", "flotteur", "fleuteur"],
    ["kotlin", "co telline", "coteline"],
    ["ollama", "oh lama", "olama"],
    ["ethereum", "e terre yom", "eteriome"],
    ["solidity", "soliditi", "solidite"],
    ["embedding", "aimbe dine", "imbeding"],
    ["quantization", "quantizacion", "couantizacion"],
    # Vague 18 — UX / Networking / Text processing phonetiques
    ["figma", "feegma", "figmah"],
    ["nginx", "enne gin x", "enginx"],
    ["traefik", "tre fi que", "trafik"],
    ["cloudflare", "claoude flaire", "cloudflair"],
    ["wireguard", "ouaire guard", "wiregard"],
    ["regex", "redjex", "redjexe"],
    ["storybook", "stori bouk", "storybuk"],
    # Vague 19 — TypeScript/Python/React/Linux phonetiques
    ["typescript", "type scripte", "taipscript"],
    ["pydantic", "pie dantic", "pidantique"],
    ["fastapi", "fast a pi", "fastapie"],
    ["uvicorn", "you vi corne", "ouvicorne"],
    ["zustand", "zu stand", "zoustand"],
    ["svelte", "sse velte", "zvelte"],
    ["tailwind", "teil ouinde", "telouind"],
    ["tmux", "te mux", "timuks"],
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
    # Vague 3 — Fillers avances
    "a vrai dire", "franchement", "evidemment",
    "clairement", "en quelque sorte", "tu sais quoi",
    "la en fait", "a ce moment la", "une seconde",
    "une minute", "comment on dit", "cher jarvis",
    "mon cher jarvis", "petit jarvis", "grand jarvis",
    "super jarvis", "yo jarvis", "salut jarvis",
    # Vague 4 — Fillers code/dev context
    "en theorie", "normalement", "techniquement",
    "a priori", "idealement", "potentiellement",
    "grosso modo", "si possible", "dans l'idee",
    "rapidement", "vite fait", "en vitesse",
    "quand tu peux", "des que possible",
    "si tu veux bien", "je te demande de",
    # Vague 5 — Fillers anglais tech
    "basically", "actually", "literally", "like",
    "you know", "i mean", "right", "okay so",
    "let me", "can you", "just", "maybe",
    "i think", "i guess", "sort of", "kind of",
    # Vague 6 — Fillers hesitation / reformulation
    "je veux dire", "c'est-a-dire", "autrement dit",
    "par contre", "cependant", "neanmoins",
    "si tu veux", "disons que", "en principe",
    "sauf erreur", "a mon avis", "il me semble",
    "concretement", "pratiquement", "effectivement",
    "accessoirement", "subsidiairement", "nota bene",
    # Vague 7 — Fillers techniques / dev context
    "for example", "for instance", "in general",
    "as a matter of fact", "to be honest", "honestly",
    "par exemple", "en general", "pour etre honnete",
    "sincerement", "a proprement parler", "stricto sensu",
    "grossierement", "en resume", "pour faire simple",
    "en deux mots", "pour resumer", "long story short",
    # Vague 8 — Reactions / interjections vocales
    "genial", "super", "parfait", "excellent", "nickel",
    "impeccable", "top", "cool", "awesome", "great",
    "nice", "perfect", "wonderful", "amazing",
    "oh mon dieu", "oh la la", "waouh", "wow",
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
    # Vague 24 — Info / Contexte rapide
    "heure": "quelle heure est-il",
    "date": "quelle date",
    "meteo": "dis moi la meteo",
    "uptime": "depuis quand le pc tourne",
    "todo": "liste la todo",
    "taches": "liste la todo",
    "rappel": "rappelle moi de",
    "positions": "mes positions",
    "pnl": "pnl du jour",
    "alertes": "configure les alertes",
    "profit": "pnl du jour",
    "gains": "pnl du jour",
    "pertes": "pnl du jour",
    # Vague 25 — Modes rapides
    "stream": "mode stream",
    "game": "mode gaming",
    "gaming": "mode gaming",
    "meeting": "mode reunion",
    "reunion": "mode reunion",
    "visio": "mode reunion",
    "presentation": "mode presentation",
    "diapo": "mode presentation",
    # Vague 26 — Hardware / Debug rapide
    "nvidia": "info gpu",
    "vram": "utilisation vram",
    "thermal": "surveille les temperatures",
    "temp": "temperature gpu",
    "memoire": "utilisation ram",
    "processeur": "utilisation cpu",
    "disque": "espace disque",
    "network": "diagnostic reseau",
    "reseau": "diagnostic reseau",
    "internet": "test de bande passante",
    # Vague 27 — Commandes combinees / express
    "check all": "rapport systeme complet",
    "test all": "test rapide",
    "scan all": "scan securite complet",
    "fix all": "heal cluster",
    "clean all": "nettoie les fichiers temporaires",
    "backup all": "backup complet",
    "close all": "ferme les positions",
    "update all": "maintenance hebdo",
    "status all": "rapport systeme complet",
    "show all": "rapport systeme complet",
    # Vague 28 — Git shortcuts
    "pull": "git pull",
    "stash": "git stash",
    "branch": "git branch",
    "branches": "liste les branches",
    "merge": "git merge",
    "rebase": "git rebase",
    "log git": "git log",
    "blame": "git blame",
    "diff": "git diff",
    "cherry": "git cherry-pick",
    "tag": "git tag",
    "remote": "git remote",
    "fetch": "git fetch",
    "clone": "git clone",
    "reset": "git reset",
    # Vague 29 — DB shortcuts
    "tables": "liste les tables",
    "schema": "schema de la base",
    "count": "combien de lignes en base",
    "select": "requete sql",
    "insert": "insertion en base",
    "migrate": "migration de base",
    "seed": "seed la base",
    "dump": "dump de la base",
    "restore db": "restaure la base",
    "indices": "liste les indices",
    "foreign keys": "cles etrangeres",
    # Vague 30 — Network shortcuts
    "ping": "ping le reseau",
    "traceroute": "traceroute",
    "curl": "requete curl",
    "wget": "telecharge avec wget",
    "ifconfig": "configuration reseau",
    "bandwidth": "test de bande passante",
    "latency": "test de latence",
    "speedtest": "test de bande passante",
    "whois": "whois",
    "dig": "dig dns",
    # Vague 31 — Windows shortcuts
    "parametres windows": "ouvre les parametres",
    "panneau config": "panneau de configuration",
    "panneau de config": "panneau de configuration",
    "task manager": "gestionnaire de taches",
    "taskmgr": "gestionnaire de taches",
    "gestionnaire": "gestionnaire de taches",
    "msconfig": "configuration systeme",
    "event viewer": "observateur d'evenements",
    "device manager": "gestionnaire de peripheriques",
    "disk management": "gestion des disques",
    "windows update": "mets a jour windows",
    "winupdate": "mets a jour windows",
    "defender": "securite windows",
    "powershell": "ouvre powershell",
    "cmd": "ouvre le terminal",
    "command prompt": "ouvre le terminal",
    # Vague 32 — JARVIS raccourcis
    "jarvis aide": "aide commandes",
    "jarvis help": "aide commandes",
    "jarvis stop": "arrete tout",
    "jarvis pause": "mode pause",
    "jarvis reset": "redemarre jarvis",
    "jarvis restart": "redemarre jarvis",
    "jarvis version": "version jarvis",
    "jarvis stats": "statistiques jarvis",
    "jarvis config": "configuration jarvis",
    "jarvis debug": "mode debug jarvis",
    "jarvis verbose": "mode verbose",
    "jarvis quiet": "mode silencieux",
    "jarvis mute": "coupe la voix jarvis",
    "jarvis unmute": "reactive la voix jarvis",
    # Vague 33 — Combos rapides productivite
    "save and push": "auto commit et push",
    "commit and push": "auto commit et push",
    "lint and test": "lint puis tests",
    "build and deploy": "build puis deploie",
    "pull and build": "pull puis build",
    "test and commit": "teste puis commite",
    "clean and build": "nettoie puis build",
    "check and fix": "diagnostique puis repare",
    "scan and report": "scan puis rapport",
    "backup and clean": "backup puis nettoie",
    # Vague 34 — Cloud / Infrastructure
    "aws": "statut aws",
    "azure": "statut azure",
    "cloud": "statut cloud",
    "kubernetes": "statut kubernetes",
    "k8s": "statut kubernetes",
    "terraform": "statut terraform",
    "ansible": "statut ansible",
    "compose": "docker compose",
    "container": "liste les conteneurs",
    "image": "liste les images docker",
    "registry": "registre docker",
    "helm": "statut helm",
    "ingress": "statut ingress",
    # Vague 35 — Monitoring avance
    "metriques": "affiche les metriques",
    "metrics": "affiche les metriques",
    "graphe": "ouvre grafana",
    "grafana": "ouvre grafana",
    "prometheus": "statut prometheus",
    "alertes systeme": "alertes systeme",
    "sla": "statut sla",
    "uptime systeme": "uptime du systeme",
    "health": "health check",
    "liveness": "liveness check",
    "readiness": "readiness check",
    "heartbeat": "heartbeat check",
    # Vague 36 — Audio / Video
    "volume max": "monte le volume au max",
    "volume min": "baisse le volume au minimum",
    "mute all": "coupe tout le son",
    "unmute": "reactive le son",
    "micro on": "active le micro",
    "micro off": "coupe le micro",
    "camera on": "active la camera",
    "camera off": "coupe la camera",
    "record": "enregistre l'ecran",
    "screencast": "enregistre l'ecran",
    "capture video": "enregistre l'ecran",
    "bass boost": "augmente les basses",
    "equalizer": "ouvre l'egaliseur",
    # Vague 37 — Securite
    "scan virus": "lance un scan antivirus",
    "antivirus scan": "lance un scan antivirus",
    "scan malware": "lance un scan malware",
    "check firewall": "verifie le pare-feu",
    "firewall": "verifie le pare-feu",
    "permissions": "verifie les permissions",
    "credentials": "verifie les credentials",
    "secrets": "verifie les secrets",
    "certs": "verifie les certificats",
    "certificates": "verifie les certificats",
    "encrypt": "chiffre",
    "decrypt": "dechiffre",
    # Vague 38 — Donnees / Export
    "csv": "exporte en csv",
    "json": "exporte en json",
    "xml": "exporte en xml",
    "yaml": "exporte en yaml",
    "pdf": "exporte en pdf",
    "excel": "exporte en excel",
    "import data": "importe les donnees",
    "export data": "exporte les donnees",
    "sync data": "synchronise les donnees",
    "migrate data": "migre les donnees",
    # Vague 39 — JARVIS dominos rapides
    "matin": "lance briefing matin",
    "soir": "bilan du soir",
    "nuit": "mode nuit",
    "urgence": "sauvegarde urgence",
    "review": "revue de code",
    "deploy": "deploie en staging",
    "warmup": "chauffe le cluster",
    "weekly": "maintenance hebdo",
    "startup": "sequence de demarrage",
    "shutdown": "sequence arret",
    # Vague 40 — Trading raccourcis
    "btc": "scan btc",
    "eth": "scan eth",
    "sol": "scan sol",
    "long": "position long",
    "short": "position short",
    "scalp": "mode scalping",
    "swing": "mode swing",
    "spot": "mode spot",
    "futures": "mode futures",
    "leverage": "levier trading",
    "margin": "marge disponible",
    "liquidation": "check liquidation",
    # Vague 41 — Daily routines
    "cafe": "pause cafe",
    "dejeuner": "pause dejeuner",
    "fin": "fin de journee",
    "focus": "mode focus",
    "break": "pause cafe",
    "meeting": "mode reunion",
    "call": "mode reunion",
    "code": "mode coding",
    "coding": "mode coding",
    "debug": "mode debug",
    "relax": "mode pause",
    "chill": "mode pause",
    # Vague 42 — Tests / QA raccourcis
    "unittest": "lance les tests unitaires",
    "unit tests": "lance les tests unitaires",
    "integration": "lance les tests integration",
    "e2e": "lance les tests e2e",
    "smoke": "smoke test",
    "regression": "test de regression",
    "coverage report": "rapport couverture",
    "mock": "configure les mocks",
    # Vague 43 — Architecture raccourcis
    "microservice": "statut microservices",
    "api gateway": "statut api gateway",
    "queue": "statut message queue",
    "cache status": "statut du cache",
    "cdn status": "statut cdn",
    "ssl check": "verifie les certificats",
    "rate limit": "configure rate limit",
    "circuit breaker": "statut circuit breaker",
    # Vague 44 — Raccourcis clavier
    "copier": "copie",
    "coller": "colle",
    "couper": "coupe",
    "annuler": "annule",
    "retablir": "retablis",
    "sauvegarder": "sauvegarde",
    "selectionner": "selectionne tout",
    "rechercher": "recherche",
    "remplacer": "remplace",
    "imprimer": "imprime",
    # Vague 45 — Documentation raccourcis
    "readme": "ouvre le readme",
    "docs": "ouvre la documentation",
    "wiki": "ouvre le wiki",
    "changelog": "montre le changelog",
    "swagger": "ouvre swagger",
    "postman": "ouvre postman",
    "api doc": "documentation api",
    # Vague 46 — CI/CD raccourcis
    "pipeline": "lance le pipeline",
    "ci": "statut ci",
    "cd": "statut cd",
    "actions": "statut github actions",
    "deploy prod": "deploie en production",
    "deploy staging": "deploie en staging",
    "rollback": "rollback derniere version",
    "feature flag": "toggle feature flag",
    "staging": "statut staging",
    # Vague 47 — Collaboration
    "standup": "lance le standup",
    "daily": "lance le daily",
    "retro": "lance la retro",
    "sprint": "statut du sprint",
    "backlog": "montre le backlog",
    "kanban": "ouvre le kanban",
    "pr": "liste les pull requests",
    "review": "lance la code review",
    "pairing": "mode pair programming",
    # Vague 48 — API / HTTP raccourcis
    "get": "envoie une requete get",
    "post": "envoie une requete post",
    "put": "envoie une requete put",
    "delete": "envoie une requete delete",
    "endpoint": "teste l'endpoint",
    "webhook": "teste le webhook",
    "api": "teste l'api",
    "cors": "configure cors",
    "swagger": "ouvre swagger",
    # Vague 49 — Database raccourcis
    "vacuum": "vacuum base de donnees",
    "migrate": "lance la migration",
    "seed": "lance le seeder",
    "schema": "montre le schema",
    "backup db": "backup la base",
    "restore db": "restore la base",
    "reindex": "reindex la base",
    "dump": "dump la base",
    "import db": "importe les donnees",
    # Vague 50 — Kubernetes raccourcis
    "pods": "liste les pods",
    "deployments": "liste les deployments",
    "services k8s": "liste les services kubernetes",
    "logs pod": "affiche les logs du pod",
    "scale": "scale le deployment",
    "rollout": "statut du rollout",
    "helm list": "liste les charts helm",
    "namespace": "change de namespace",
    "kubectl": "lance kubectl",
    # Vague 51 — Monitoring raccourcis
    "metrics": "affiche les metriques",
    "dashboard": "ouvre le dashboard",
    "grafana": "ouvre grafana",
    "prometheus": "ouvre prometheus",
    "alerts": "montre les alertes",
    "logs": "affiche les logs",
    "traces": "affiche les traces",
    "health": "healthcheck systeme",
    # Vague 52 — Auth / Securite raccourcis
    "login": "connecte toi",
    "logout": "deconnecte toi",
    "token": "genere un token",
    "refresh token": "rafraichis le token",
    "permissions": "montre les permissions",
    "roles": "liste les roles",
    "audit log": "affiche l'audit log",
    "encrypt": "chiffre le fichier",
    "decrypt": "dechiffre le fichier",
    # Vague 53 — Cloud / Deploy raccourcis
    "deploy": "deploie en production",
    "serverless": "deploie en serverless",
    "lambda": "lance la lambda",
    "s3": "ouvre s3",
    "ec2": "statut ec2",
    "terraform": "lance terraform",
    "infra": "statut infrastructure",
    "cdn": "purge le cdn",
    "ssl": "verifie le ssl",
    # Vague 54 — Git avance raccourcis
    "cherry pick": "cherry-pick le commit",
    "rebase": "lance le rebase",
    "squash": "squash les commits",
    "stash": "stash les changements",
    "bisect": "lance git bisect",
    "reflog": "montre le reflog",
    "tag": "cree un tag",
    "release": "cree une release",
    "hotfix": "branche hotfix",
    # Vague 55 — IDE / Editeur raccourcis
    "format": "formate le code",
    "lint": "lance le linter",
    "debug": "lance le debugger",
    "breakpoint": "ajoute un breakpoint",
    "extensions": "liste les extensions",
    "snippet": "cree un snippet",
    "refactor": "refactorise le code",
    "rename": "renomme la variable",
    # Vague 56 — Testing raccourcis
    "test": "lance les tests",
    "tests": "lance les tests",
    "pytest": "lance pytest",
    "coverage": "lance la couverture",
    "mock": "cree un mock",
    "fixture": "cree une fixture",
    "e2e": "lance les tests e2e",
    "smoke": "lance le smoke test",
    "benchmark": "lance le benchmark",
    # Vague 57 — Architecture raccourcis
    "singleton": "cree un singleton",
    "factory": "cree une factory",
    "middleware": "ajoute un middleware",
    "injection": "injection de dependances",
    "microservice": "cree un microservice",
    "migration db": "lance la migration db",
    "schema db": "montre le schema db",
    # Vague 58 — Data / Analytics raccourcis
    "etl": "lance le pipeline etl",
    "kafka": "statut kafka",
    "redis": "statut redis",
    "mongo": "statut mongodb",
    "postgres": "statut postgresql",
    "spark": "lance spark",
    "pipeline data": "lance le data pipeline",
    "streaming": "lance le streaming",
    # Vague 59 — Mobile / Cross-platform raccourcis
    "react native": "lance react native",
    "flutter": "lance flutter",
    "expo": "lance expo",
    "build apk": "build l'apk",
    "build ios": "build pour ios",
    "emulateur": "lance l'emulateur",
    "simulator": "lance le simulateur",
    "hot reload": "hot reload",
    # Vague 60 — DevOps / SRE raccourcis
    "incident": "declare un incident",
    "postmortem": "ecris le postmortem",
    "runbook": "ouvre le runbook",
    "canary": "deploie en canary",
    "blue green": "deploie en blue-green",
    "circuit breaker": "active le circuit breaker",
    "chaos": "lance le chaos test",
    "sla": "montre le sla",
    # Vague 61 — IA / LLM raccourcis
    "prompt": "edite le prompt",
    "rag": "lance le rag",
    "fine tune": "lance le fine-tuning",
    "embedding": "genere les embeddings",
    "inference": "lance l'inference",
    "quantize": "quantize le modele",
    "ollama run": "lance ollama",
    "lm studio": "ouvre lm studio",
    # Vague 62 — UX / Design raccourcis
    "figma": "ouvre figma",
    "wireframe": "cree un wireframe",
    "prototype": "lance le prototype",
    "storybook": "ouvre storybook",
    "design system": "ouvre le design system",
    "composant": "cree un composant",
    "responsive": "verifie le responsive",
    "a11y": "check accessibilite",
    # Vague 63 — Networking raccourcis
    "dns": "check dns",
    "ping": "ping le serveur",
    "traceroute": "lance traceroute",
    "nslookup": "nslookup",
    "dig": "dig domain",
    "whois": "whois domain",
    "vpn": "connecte le vpn",
    "firewall": "statut firewall",
    "nginx": "statut nginx",
    # Vague 64 — Text processing raccourcis
    "regex": "teste la regex",
    "grep": "grep dans les fichiers",
    "sed": "lance sed",
    "awk": "lance awk",
    "jq": "parse avec jq",
    "parser": "lance le parser",
    "ast": "affiche l'ast",
    # Vague 65 — TypeScript / JS raccourcis
    "typescript": "lance typescript",
    "tsc": "compile typescript",
    "jsx": "cree un composant jsx",
    "tsx": "cree un composant tsx",
    "hook": "cree un hook react",
    "reducer": "cree un reducer",
    "store": "configure le store",
    "ssr": "active le server side rendering",
    # Vague 66 — Python raccourcis
    "fastapi": "lance fastapi",
    "uvicorn": "lance uvicorn",
    "celery": "lance celery",
    "virtualenv": "cree un virtualenv",
    "venv": "cree un venv",
    "poetry": "lance poetry",
    "pydantic": "cree un modele pydantic",
    "asyncio": "lance asyncio",
    # Vague 67 — Linux / Shell raccourcis
    "crontab": "edite le crontab",
    "systemctl": "statut systemctl",
    "journalctl": "affiche journalctl",
    "chmod": "change les permissions",
    "tmux": "lance tmux",
    "screen": "lance screen",
    "daemon": "lance le daemon",
    "nohup": "lance en nohup",
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
    # Vague 2 — Extended patterns
    (r"\b(etoile|jarvis|sniper|finetuning|trading)\.?(?:db)?\b", "db", "{0}.db"),
    (r"\bpaire?\s+(BTC|ETH|SOL|SUI|PEPE|DOGE|XRP|ADA|AVAX|LINK)(?:USDT)?\b", "pair", "{0}USDT"),
    (r"\btimeframe?\s+(\d+[mhd]|1h|4h|1d|15m|5m|1m)\b", "timeframe", "{0}"),
    (r"\b(rapide|lent|moyen|profond|complet|simple|detaille)\b", "depth", "{0}"),
    (r"\bdossier\s+(.+?)(?:\s+|$)", "folder", "{0}"),
    (r"\bfichier\s+(.+?)(?:\s+|$)", "file", "{0}"),
    # Vague 3 — Extended patterns (port, url, branch, service)
    (r"\bport\s+(\d{2,5})\b", "port", "{0}"),
    (r"\bbranche?\s+(\S+)\b", "branch", "{0}"),
    (r"\bservice\s+(\S+)\b", "service", "{0}"),
    (r"\benv(?:ironnement)?\s+(dev|prod|staging|test|local)\b", "env", "{0}"),
    (r"\b(\d+)\s*(?:heures?|h)\b", "hours", "{0}"),
    (r"\b(\d+)\s*(?:jours?|j)\b", "days", "{0}"),
    # Vague 4 — Extended patterns (version, count, level, format, protocol)
    (r"\bversion\s+(\d+(?:\.\d+)*)\b", "version", "{0}"),
    (r"\b(\d+)\s*(?:fois|x)\b", "count", "{0}"),
    (r"\bniveau\s+(debug|info|warning|error|critical)\b", "level", "{0}"),
    (r"\bformat\s+(json|csv|xml|yaml|toml|txt|md|html)\b", "format", "{0}"),
    (r"\bprotocole?\s+(http|https|tcp|udp|ws|wss|grpc|mqtt)\b", "protocol", "{0}"),
    (r"\b(\d+)\s*(?:threads?|workers?|processus)\b", "workers", "{0}"),
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
        # Vague 5 — Verbes dev/data/reseau
        (r"\bcloner\b", "clone"),
        (r"\bmerger\b", "merge"),
        (r"\bbrancher\b", "branche"),
        (r"\bdumper\b", "dump"),
        (r"\bseeder\b", "seed"),
        (r"\bindexer\b", "indexe"),
        (r"\bpinger\b", "ping"),
        (r"\bfetcher\b", "fetch"),
        (r"\bpuller\b", "pull"),
        (r"\bstreamer\b", "stream"),
        (r"\bdebugger\b", "debug"),
        (r"\bformater\b", "formate"),
        (r"\bscaler\b", "scale"),
        (r"\bcontaineriser\b", "containerise"),
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

# Recent match cache: maps cleaned text → (command_name, confidence) for instant re-matching
_recent_match_cache: dict[str, tuple[str, float]] = {}
_RECENT_CACHE_MAX = 150

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

    # Step 0.5: Check recent match cache for instant re-matching
    _cache_key = normalize_text(raw_text)
    if _cache_key in _recent_match_cache:
        cached_name, cached_conf = _recent_match_cache[_cache_key]
        from src.commands import match_command
        for cmd in COMMANDS:
            if cmd.name == cached_name:
                result["command"] = cmd
                result["confidence"] = cached_conf
                result["corrected"] = _cache_key
                result["intent"] = _cache_key
                result["method"] = "cache_hit"
                return result

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
        _cache_match_result(raw_text, result)
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
            _cache_match_result(raw_text, result)
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
        _cache_match_result(raw_text, result)
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
        _cache_match_result(raw_text, result)
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
                _cache_match_result(raw_text, result)
                return result

    # Step 9: Get suggestions
    suggestions = get_suggestions(intent)
    result["suggestions"] = suggestions

    if suggestions and suggestions[0][1] >= 0.55:
        top_cmd, top_score = suggestions[0]
        result["command"] = top_cmd
        result["confidence"] = top_score
        result["method"] = "suggestion"
        _cache_match_result(raw_text, result)
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


def _cache_match_result(raw_text: str, result: dict) -> None:
    """Cache a successful match for instant replay on identical input."""
    cmd = result.get("command")
    if cmd is None or result.get("confidence", 0) < 0.70:
        return
    key = normalize_text(raw_text)
    if len(_recent_match_cache) >= _RECENT_CACHE_MAX:
        # Evict oldest entry (FIFO)
        oldest = next(iter(_recent_match_cache))
        del _recent_match_cache[oldest]
    _recent_match_cache[key] = (cmd.name, result["confidence"])


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
        "fais ca", "recommence", "de nouveau", "idem", "same",
        "a nouveau", "encore une fois", "une autre fois", "re",
        "refais la meme chose", "recommence ca", "relance ca",
        "fait pareil", "fait le pareil", "meme commande",
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

    def get_session_stats(self) -> dict:
        """Return session statistics."""
        with self._lock:
            return {
                "correction_count": self.correction_count,
                "history_length": len(self.history),
                "last_command": self.last_command.name if self.last_command else None,
                "last_raw": self.last_raw,
                "suggestions_pending": len(self.last_suggestions),
                "cache_size": len(_recent_match_cache),
            }


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
