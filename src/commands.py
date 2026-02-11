"""JARVIS Command Database — Pre-registered voice commands, pipelines, fuzzy matching."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════
# COMMAND DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class JarvisCommand:
    """A pre-registered JARVIS voice command."""
    name: str                          # Identifiant unique
    category: str                      # Categorie (navigation, fichiers, trading, systeme, app)
    description: str                   # Description en francais
    triggers: list[str]                # Phrases vocales qui declenchent cette commande
    action_type: str                   # Type: powershell, app_open, browser, script, pipeline
    action: str                        # Commande/template a executer
    params: list[str] = field(default_factory=list)  # Parametres a remplir (phrases a trou)
    confirm: bool = False              # Demander confirmation avant execution


# ═══════════════════════════════════════════════════════════════════════════
# PRE-REGISTERED COMMANDS DATABASE
# ═══════════════════════════════════════════════════════════════════════════

COMMANDS: list[JarvisCommand] = [
    # ══════════════════════════════════════════════════════════════════════
    # NAVIGATION WEB (11 commandes)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_chrome", "navigation", "Ouvrir Google Chrome", [
        "ouvre chrome", "ouvrir chrome", "lance chrome", "ouvre le navigateur",
        "ouvrir le navigateur", "lance le navigateur", "ouvre google chrome",
        "demarre chrome", "ouvre internet", "ouvrir internet",
    ], "app_open", "chrome"),
    JarvisCommand("ouvrir_comet", "navigation", "Ouvrir Comet Browser", [
        "ouvre comet", "ouvrir comet", "lance comet", "ouvre le navigateur comet",
    ], "app_open", "comet"),
    JarvisCommand("aller_sur_site", "navigation", "Naviguer vers un site web", [
        "va sur {site}", "ouvre {site}", "navigue vers {site}",
        "aller sur {site}", "ouvrir {site}", "charge {site}",
        "affiche {site}", "montre {site}",
    ], "browser", "navigate:{site}", ["site"]),
    JarvisCommand("chercher_google", "navigation", "Rechercher sur Google", [
        "cherche {requete}", "recherche {requete}", "google {requete}",
        "cherche sur google {requete}", "recherche sur google {requete}",
        "trouve {requete}", "chercher {requete}",
    ], "browser", "search:{requete}", ["requete"]),
    JarvisCommand("chercher_youtube", "navigation", "Rechercher sur YouTube", [
        "cherche sur youtube {requete}", "youtube {requete}",
        "recherche sur youtube {requete}", "mets {requete} sur youtube",
    ], "browser", "navigate:https://www.youtube.com/results?search_query={requete}", ["requete"]),
    JarvisCommand("ouvrir_gmail", "navigation", "Ouvrir Gmail", [
        "ouvre gmail", "ouvrir gmail", "ouvre mes mails", "ouvre mes emails",
        "va sur gmail", "ouvre ma boite mail", "ouvre la messagerie",
        "check mes mails", "verifie mes mails",
    ], "browser", "navigate:https://mail.google.com"),
    JarvisCommand("ouvrir_youtube", "navigation", "Ouvrir YouTube", [
        "ouvre youtube", "va sur youtube", "lance youtube",
        "ouvrir youtube", "mets youtube",
    ], "browser", "navigate:https://youtube.com"),
    JarvisCommand("ouvrir_github", "navigation", "Ouvrir GitHub", [
        "ouvre github", "va sur github", "ouvrir github",
    ], "browser", "navigate:https://github.com"),
    JarvisCommand("ouvrir_tradingview", "navigation", "Ouvrir TradingView", [
        "ouvre tradingview", "va sur tradingview", "lance tradingview",
        "ouvre trading view", "ouvre les charts",
    ], "browser", "navigate:https://www.tradingview.com"),
    JarvisCommand("ouvrir_mexc", "navigation", "Ouvrir MEXC", [
        "ouvre mexc", "va sur mexc", "lance mexc", "ouvre l'exchange",
    ], "browser", "navigate:https://www.mexc.com"),
    JarvisCommand("nouvel_onglet", "navigation", "Ouvrir un nouvel onglet", [
        "nouvel onglet", "nouveau tab", "ouvre un nouvel onglet",
        "ouvre un nouveau tab",
    ], "hotkey", "ctrl+t"),

    # ══════════════════════════════════════════════════════════════════════
    # FICHIERS & DOCUMENTS (7 commandes)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_documents", "fichiers", "Ouvrir le dossier Documents", [
        "ouvre mes documents", "ouvrir mes documents", "ouvre documents",
        "affiche mes documents", "va dans mes documents", "ouvre le dossier documents",
    ], "powershell", "Start-Process explorer.exe -ArgumentList ([Environment]::GetFolderPath('MyDocuments'))"),
    JarvisCommand("ouvrir_bureau", "fichiers", "Ouvrir le dossier Bureau", [
        "ouvre le bureau", "ouvrir le bureau", "affiche le bureau",
        "ouvre mes fichiers bureau", "va sur le bureau",
    ], "powershell", "Start-Process explorer.exe -ArgumentList 'F:\\BUREAU'"),
    JarvisCommand("ouvrir_dossier", "fichiers", "Ouvrir un dossier specifique", [
        "ouvre le dossier {dossier}", "ouvrir le dossier {dossier}",
        "va dans {dossier}", "explore {dossier}",
    ], "powershell", "Start-Process explorer.exe -ArgumentList '{dossier}'", ["dossier"]),
    JarvisCommand("ouvrir_telechargements", "fichiers", "Ouvrir Telechargements", [
        "ouvre les telechargements", "ouvre mes telechargements",
        "ouvrir telechargements", "va dans telechargements",
    ], "powershell", "Start-Process explorer.exe -ArgumentList ([Environment]::GetFolderPath('UserProfile') + '\\Downloads')"),
    JarvisCommand("ouvrir_images", "fichiers", "Ouvrir le dossier Images", [
        "ouvre mes images", "ouvre mes photos", "ouvre le dossier images",
        "va dans mes images", "affiche mes photos",
    ], "powershell", "Start-Process explorer.exe -ArgumentList ([Environment]::GetFolderPath('MyPictures'))"),
    JarvisCommand("ouvrir_musique", "fichiers", "Ouvrir le dossier Musique", [
        "ouvre ma musique", "ouvre le dossier musique",
        "va dans ma musique",
    ], "powershell", "Start-Process explorer.exe -ArgumentList ([Environment]::GetFolderPath('MyMusic'))"),
    JarvisCommand("ouvrir_projets", "fichiers", "Ouvrir le dossier projets", [
        "ouvre mes projets", "va dans les projets", "ouvre le dossier turbo",
        "ouvre les projets", "ouvre turbo",
    ], "powershell", "Start-Process explorer.exe -ArgumentList 'F:\\BUREAU\\turbo'"),

    # ══════════════════════════════════════════════════════════════════════
    # APPLICATIONS (10 commandes)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_vscode", "app", "Ouvrir Visual Studio Code", [
        "ouvre vscode", "ouvrir vscode", "lance vscode", "ouvre visual studio code",
        "ouvre vs code", "lance vs code", "ouvre l'editeur", "ouvre l'editeur de code",
    ], "app_open", "code"),
    JarvisCommand("ouvrir_terminal", "app", "Ouvrir un terminal", [
        "ouvre le terminal", "ouvrir le terminal", "lance powershell",
        "ouvre powershell", "lance le terminal", "ouvre la console",
        "ouvre un terminal", "lance un terminal",
    ], "app_open", "wt"),
    JarvisCommand("ouvrir_lmstudio", "app", "Ouvrir LM Studio", [
        "ouvre lm studio", "lance lm studio", "demarre lm studio",
        "ouvrir lm studio", "ouvre l m studio",
    ], "app_open", "lmstudio"),
    JarvisCommand("ouvrir_discord", "app", "Ouvrir Discord", [
        "ouvre discord", "lance discord", "va sur discord",
    ], "app_open", "discord"),
    JarvisCommand("ouvrir_spotify", "app", "Ouvrir Spotify", [
        "ouvre spotify", "lance spotify", "mets spotify",
        "lance la musique", "ouvre la musique",
    ], "app_open", "spotify"),
    JarvisCommand("ouvrir_task_manager", "app", "Ouvrir le gestionnaire de taches", [
        "ouvre le gestionnaire de taches", "task manager",
        "gestionnaire de taches", "ouvre les taches",
        "ouvre le gestionnaire", "lance le gestionnaire de taches",
    ], "app_open", "taskmgr"),
    JarvisCommand("ouvrir_notepad", "app", "Ouvrir Notepad", [
        "ouvre notepad", "ouvre bloc notes", "ouvre le bloc notes",
        "lance notepad", "nouveau fichier texte",
    ], "app_open", "notepad"),
    JarvisCommand("ouvrir_calculatrice", "app", "Ouvrir la calculatrice", [
        "ouvre la calculatrice", "lance la calculatrice", "calculatrice",
        "ouvre calc",
    ], "app_open", "calc"),
    JarvisCommand("fermer_app", "app", "Fermer une application", [
        "ferme {app}", "fermer {app}", "quitte {app}",
        "kill {app}", "arrete {app}",
    ], "jarvis_tool", "close_app:{app}", ["app"]),
    JarvisCommand("ouvrir_app", "app", "Ouvrir une application par nom", [
        "ouvre {app}", "ouvrir {app}", "lance {app}", "demarre {app}",
    ], "app_open", "{app}", ["app"]),

    # ══════════════════════════════════════════════════════════════════════
    # CONTROLE MEDIA (7 commandes)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("media_play_pause", "media", "Play/Pause media", [
        "play", "pause", "mets pause", "reprends", "lecture",
        "mets en pause", "stop la musique", "reprends la musique",
    ], "hotkey", "media_play_pause"),
    JarvisCommand("media_next", "media", "Piste suivante", [
        "suivant", "piste suivante", "chanson suivante",
        "musique suivante", "next", "morceau suivant",
        "prochain morceau", "prochaine chanson", "prochaine musique",
    ], "hotkey", "media_next"),
    JarvisCommand("media_previous", "media", "Piste precedente", [
        "precedent", "piste precedente", "chanson precedente",
        "musique precedente", "previous", "morceau precedent",
        "morceau d'avant", "chanson d'avant", "musique d'avant",
    ], "hotkey", "media_previous"),
    JarvisCommand("volume_haut", "media", "Augmenter le volume", [
        "monte le volume", "augmente le volume", "volume plus fort",
        "plus fort", "monte le son", "augmente le son", "volume haut",
    ], "hotkey", "volume_up"),
    JarvisCommand("volume_bas", "media", "Baisser le volume", [
        "baisse le volume", "diminue le volume", "volume moins fort",
        "moins fort", "baisse le son", "diminue le son", "volume bas",
    ], "hotkey", "volume_down"),
    JarvisCommand("muet", "media", "Couper/activer le son", [
        "coupe le son", "mute", "silence", "muet",
        "active le son", "reactive le son", "unmute",
    ], "hotkey", "volume_mute"),
    JarvisCommand("volume_precis", "media", "Mettre le volume a un niveau precis", [
        "mets le volume a {niveau}", "volume a {niveau}",
        "regle le volume a {niveau}", "volume {niveau} pourcent",
    ], "powershell", "powershell -NoProfile -Command \"$vol = {niveau} / 100; (New-Object -ComObject WScript.Shell).SendKeys([char]173); Start-Sleep -Milliseconds 200\"", ["niveau"]),

    # ══════════════════════════════════════════════════════════════════════
    # FENETRES WINDOWS (9 commandes)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("minimiser_tout", "fenetre", "Minimiser toutes les fenetres", [
        "minimise tout", "montre le bureau", "affiche le bureau",
        "cache tout", "bureau", "show desktop",
    ], "hotkey", "win+d"),
    JarvisCommand("alt_tab", "fenetre", "Basculer entre les fenetres", [
        "change de fenetre", "fenetre suivante", "bascule",
        "alt tab", "switch", "passe a l'autre fenetre",
    ], "hotkey", "alt+tab"),
    JarvisCommand("fermer_fenetre", "fenetre", "Fermer la fenetre active", [
        "ferme la fenetre", "ferme ca", "ferme cette fenetre",
        "close", "ferme",
    ], "hotkey", "alt+F4"),
    JarvisCommand("maximiser_fenetre", "fenetre", "Maximiser la fenetre active", [
        "maximise", "plein ecran", "maximiser la fenetre",
        "agrandis la fenetre", "fenetre maximale",
    ], "hotkey", "win+up"),
    JarvisCommand("minimiser_fenetre", "fenetre", "Minimiser la fenetre active", [
        "minimise", "reduis la fenetre", "minimiser",
        "cache la fenetre", "range la fenetre",
    ], "hotkey", "win+down"),
    JarvisCommand("fenetre_gauche", "fenetre", "Fenetre a gauche", [
        "fenetre a gauche", "mets a gauche", "snap gauche",
        "colle a gauche", "moitie gauche",
    ], "hotkey", "win+left"),
    JarvisCommand("fenetre_droite", "fenetre", "Fenetre a droite", [
        "fenetre a droite", "mets a droite", "snap droite",
        "colle a droite", "moitie droite",
    ], "hotkey", "win+right"),
    JarvisCommand("focus_fenetre", "fenetre", "Mettre le focus sur une fenetre", [
        "focus sur {titre}", "va sur la fenetre {titre}",
        "montre {titre}", "affiche la fenetre {titre}",
    ], "jarvis_tool", "focus_window:{titre}", ["titre"]),
    JarvisCommand("liste_fenetres", "fenetre", "Lister les fenetres ouvertes", [
        "quelles fenetres sont ouvertes", "liste les fenetres",
        "montre les fenetres", "fenetres ouvertes",
    ], "jarvis_tool", "list_windows"),

    # ══════════════════════════════════════════════════════════════════════
    # PRESSE-PAPIER & SAISIE (6 commandes)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("copier", "clipboard", "Copier la selection", [
        "copie", "copier", "copy", "copie ca", "copie la selection",
    ], "hotkey", "ctrl+c"),
    JarvisCommand("coller", "clipboard", "Coller le contenu", [
        "colle", "coller", "paste", "colle ca", "colle le contenu",
    ], "hotkey", "ctrl+v"),
    JarvisCommand("couper", "clipboard", "Couper la selection", [
        "coupe", "couper", "cut", "coupe ca",
    ], "hotkey", "ctrl+x"),
    JarvisCommand("tout_selectionner", "clipboard", "Selectionner tout", [
        "selectionne tout", "tout selectionner", "select all",
        "prends tout", "selectionner tout le texte",
    ], "hotkey", "ctrl+a"),
    JarvisCommand("annuler", "clipboard", "Annuler la derniere action", [
        "annule", "annuler", "undo", "ctrl z", "defais",
    ], "hotkey", "ctrl+z"),
    JarvisCommand("ecrire_texte", "clipboard", "Ecrire du texte au clavier", [
        "ecris {texte}", "tape {texte}", "saisis {texte}",
        "ecrit {texte}", "entre {texte}",
    ], "jarvis_tool", "type_text:{texte}", ["texte"]),

    # ══════════════════════════════════════════════════════════════════════
    # SYSTEME WINDOWS (14 commandes)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("verrouiller", "systeme", "Verrouiller le PC", [
        "verrouille le pc", "verrouille l'ecran", "lock",
        "verrouiller", "bloque le pc",
    ], "powershell", "rundll32.exe user32.dll,LockWorkStation", confirm=True),
    JarvisCommand("eteindre", "systeme", "Eteindre le PC", [
        "eteins le pc", "eteindre le pc", "arrete le pc",
        "shutdown", "eteindre l'ordinateur",
    ], "powershell", "Stop-Computer -Force", confirm=True),
    JarvisCommand("redemarrer", "systeme", "Redemarrer le PC", [
        "redemarre le pc", "redemarrer le pc", "reboot",
        "redemarre l'ordinateur", "restart",
    ], "powershell", "Restart-Computer -Force", confirm=True),
    JarvisCommand("veille", "systeme", "Mettre en veille", [
        "mets en veille", "veille", "sleep", "dors",
        "mets le pc en veille", "mise en veille",
    ], "powershell", "rundll32.exe powrprof.dll,SetSuspendState 0,1,0", confirm=True),
    JarvisCommand("capture_ecran", "systeme", "Capture d'ecran", [
        "capture ecran", "screenshot", "prends une capture",
        "fais une capture", "capture d'ecran", "copie l'ecran",
    ], "hotkey", "win+shift+s"),
    JarvisCommand("info_systeme", "systeme", "Infos systeme", [
        "info systeme", "infos systeme", "statut systeme",
        "etat du systeme", "donne moi les infos systeme",
    ], "jarvis_tool", "system_info"),
    JarvisCommand("info_gpu", "systeme", "Infos GPU", [
        "info gpu", "infos gpu", "statut gpu", "etat des gpu",
        "quelles gpu", "combien de gpu", "gpu info",
    ], "jarvis_tool", "gpu_info"),
    JarvisCommand("info_reseau", "systeme", "Infos reseau", [
        "info reseau", "infos reseau", "statut reseau",
        "etat du reseau", "quelle est mon ip", "mon ip",
    ], "jarvis_tool", "network_info"),
    JarvisCommand("processus", "systeme", "Lister les processus", [
        "liste les processus", "montre les processus",
        "quels processus tournent", "affiche les processus",
    ], "jarvis_tool", "list_processes"),
    JarvisCommand("kill_process", "systeme", "Tuer un processus", [
        "tue le processus {nom}", "kill {nom}", "ferme le processus {nom}",
        "arrete le processus {nom}",
    ], "jarvis_tool", "kill_process:{nom}", ["nom"], confirm=True),
    JarvisCommand("wifi_scan", "systeme", "Scanner les reseaux Wi-Fi", [
        "scan wifi", "wifi scan", "reseaux wifi", "quels reseaux wifi",
        "liste les wifi", "wifi disponible", "cherche wifi",
        "scanne wifi", "scanne les wifi",
    ], "jarvis_tool", "wifi_networks"),
    JarvisCommand("ping_host", "systeme", "Ping un hote", [
        "ping {host}", "teste la connexion a {host}",
        "verifie {host}", "ping vers {host}",
    ], "jarvis_tool", "ping:{host}", ["host"]),
    JarvisCommand("vider_corbeille", "systeme", "Vider la corbeille", [
        "vide la corbeille", "nettoie la corbeille", "vider la corbeille",
        "supprime la corbeille",
    ], "powershell", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue; 'Corbeille videe'", confirm=True),
    JarvisCommand("mode_nuit", "systeme", "Activer/desactiver le mode nuit", [
        "mode nuit", "lumiere bleue", "filtre bleu",
        "active le mode nuit", "desactive le mode nuit", "night mode",
    ], "hotkey", "win+a"),

    # ══════════════════════════════════════════════════════════════════════
    # TRADING & IA (10 commandes)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("scanner_marche", "trading", "Scanner le marche MEXC", [
        "scanne le marche", "scanner le marche", "lance le scanner",
        "analyse le marche", "scan mexc", "lance mexc scanner",
    ], "script", "mexc_scanner"),
    JarvisCommand("detecter_breakout", "trading", "Detecter les breakouts", [
        "detecte les breakouts", "cherche les breakouts",
        "breakout detector", "lance breakout", "lance le detecteur",
    ], "script", "breakout_detector"),
    JarvisCommand("pipeline_trading", "trading", "Lancer le pipeline intensif", [
        "lance le pipeline", "pipeline intensif", "demarre le pipeline",
        "lance le trading", "pipeline trading",
    ], "script", "pipeline_intensif_v2", confirm=True),
    JarvisCommand("sniper_breakout", "trading", "Lancer le sniper breakout", [
        "lance le sniper", "sniper breakout", "demarre le sniper",
        "active le sniper",
    ], "script", "sniper_breakout", confirm=True),
    JarvisCommand("river_scalp", "trading", "Lancer le River Scalp 1min", [
        "lance river scalp", "river scalp", "scalp 1 minute",
        "lance le scalping", "demarre le scalp",
    ], "script", "river_scalp_1min", confirm=True),
    JarvisCommand("hyper_scan", "trading", "Lancer l'hyper scan V2", [
        "lance hyper scan", "hyper scan", "scan intensif",
        "lance le scan intensif",
    ], "script", "hyper_scan_v2"),
    JarvisCommand("statut_cluster", "trading", "Statut du cluster IA", [
        "statut du cluster", "etat du cluster", "statut cluster",
        "status cluster", "verifie le cluster", "comment va le cluster",
    ], "jarvis_tool", "lm_cluster_status"),
    JarvisCommand("modeles_charges", "trading", "Modeles charges sur le cluster", [
        "quels modeles sont charges", "liste les modeles",
        "modeles charges", "modeles actifs", "quels modeles",
    ], "jarvis_tool", "lm_models"),
    JarvisCommand("consensus_ia", "trading", "Consensus multi-IA", [
        "consensus sur {question}", "demande un consensus sur {question}",
        "lance un consensus {question}", "consensus {question}",
    ], "jarvis_tool", "consensus:{question}", ["question"]),
    JarvisCommand("query_ia", "trading", "Interroger une IA locale", [
        "demande a {node} {prompt}", "interroge {node} sur {prompt}",
        "pose a {node} la question {prompt}",
    ], "jarvis_tool", "lm_query:{node}:{prompt}", ["node", "prompt"]),

    # ══════════════════════════════════════════════════════════════════════
    # CONTROLE JARVIS (6 commandes)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("jarvis_aide", "jarvis", "Afficher l'aide JARVIS", [
        "aide", "help", "quelles commandes", "que sais tu faire",
        "liste les commandes", "montre les commandes",
        "qu'est ce que tu peux faire", "tes capacites",
    ], "list_commands", "all"),
    JarvisCommand("jarvis_stop", "jarvis", "Arreter JARVIS", [
        "stop", "arrete", "quitte", "exit", "jarvis stop",
        "arrete jarvis", "ferme jarvis", "au revoir",
    ], "exit", "stop"),
    JarvisCommand("jarvis_repete", "jarvis", "Repeter la derniere reponse", [
        "repete", "redis", "repete ca", "dis le encore",
        "qu'est ce que tu as dit", "repete s'il te plait",
    ], "jarvis_repeat", "last"),
    JarvisCommand("jarvis_scripts", "jarvis", "Lister les scripts disponibles", [
        "quels scripts sont disponibles", "liste les scripts",
        "montre les scripts", "scripts disponibles",
    ], "jarvis_tool", "list_scripts"),
    JarvisCommand("jarvis_projets", "jarvis", "Lister les projets indexes", [
        "quels projets existent", "liste les projets",
        "montre les projets", "projets indexes",
    ], "jarvis_tool", "list_project_paths"),
    JarvisCommand("jarvis_notification", "jarvis", "Envoyer une notification", [
        "notifie {message}", "notification {message}",
        "envoie une notification {message}", "alerte {message}",
    ], "jarvis_tool", "notify:JARVIS:{message}", ["message"]),
    JarvisCommand("jarvis_skills", "jarvis", "Lister les skills/pipelines appris", [
        "quels skills existent", "liste les skills", "montre les skills",
        "skills disponibles", "mes pipelines", "liste les pipelines",
    ], "list_commands", "skills"),
    JarvisCommand("jarvis_suggestions", "jarvis", "Suggestions d'actions", [
        "que me suggeres tu", "suggestions", "quoi faire",
        "propose quelque chose", "next actions",
    ], "list_commands", "suggestions"),
]


# ═══════════════════════════════════════════════════════════════════════════
# KNOWN APP PATHS (Windows)
# ═══════════════════════════════════════════════════════════════════════════

APP_PATHS: dict[str, str] = {
    # Navigateurs
    "chrome": "chrome",
    "google chrome": "chrome",
    "comet": "comet-browser",
    "firefox": "firefox",
    "edge": "msedge",
    "brave": "brave",
    "opera": "opera",
    # Editeurs / Dev
    "code": "code",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "cursor": "cursor",
    "notepad": "notepad",
    "bloc notes": "notepad",
    "notepad++": "notepad++",
    "sublime": "subl",
    # Terminal
    "terminal": "wt",
    "powershell": "powershell",
    "cmd": "cmd",
    "git bash": "git-bash",
    # Systeme
    "explorateur": "explorer",
    "explorer": "explorer",
    "calculatrice": "calc",
    "calc": "calc",
    "paint": "mspaint",
    "snipping tool": "SnippingTool",
    "gestionnaire de taches": "taskmgr",
    "task manager": "taskmgr",
    "panneau de configuration": "control",
    "parametres": "ms-settings:",
    "reglages": "ms-settings:",
    "settings": "ms-settings:",
    # Office
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    # IA & Dev
    "lmstudio": "lmstudio",
    "lm studio": "lmstudio",
    "docker": "docker",
    "postman": "postman",
    # Communication
    "discord": "discord",
    "telegram": "telegram",
    "whatsapp": "whatsapp",
    "slack": "slack",
    "teams": "teams",
    "zoom": "zoom",
    # Media
    "spotify": "spotify",
    "vlc": "vlc",
    "obs": "obs64",
    "obs studio": "obs64",
    "audacity": "audacity",
    # Utilitaires
    "7zip": "7zFM",
    "winrar": "winrar",
    "steam": "steam",
    "epic games": "EpicGamesLauncher",
}


# ═══════════════════════════════════════════════════════════════════════════
# SITE ALIASES
# ═══════════════════════════════════════════════════════════════════════════

SITE_ALIASES: dict[str, str] = {
    # Search / Mail
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "google drive": "https://drive.google.com",
    "google docs": "https://docs.google.com",
    "google maps": "https://maps.google.com",
    "google translate": "https://translate.google.com",
    "google agenda": "https://calendar.google.com",
    # Social / Media
    "youtube": "https://www.youtube.com",
    "twitter": "https://twitter.com",
    "x": "https://twitter.com",
    "reddit": "https://www.reddit.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "tiktok": "https://www.tiktok.com",
    "twitch": "https://www.twitch.tv",
    "netflix": "https://www.netflix.com",
    # Dev
    "github": "https://github.com",
    "github turbo": "https://github.com/Turbo31150/turbo",
    "gitlab": "https://gitlab.com",
    "stackoverflow": "https://stackoverflow.com",
    "npm": "https://www.npmjs.com",
    "pypi": "https://pypi.org",
    "huggingface": "https://huggingface.co",
    "kaggle": "https://www.kaggle.com",
    # IA
    "chatgpt": "https://chat.openai.com",
    "claude": "https://claude.ai",
    "gemini": "https://gemini.google.com",
    "perplexity": "https://www.perplexity.ai",
    "mistral": "https://chat.mistral.ai",
    # Trading / Finance
    "mexc": "https://www.mexc.com",
    "tradingview": "https://www.tradingview.com",
    "coinglass": "https://www.coinglass.com",
    "coinmarketcap": "https://coinmarketcap.com",
    "binance": "https://www.binance.com",
    "coingecko": "https://www.coingecko.com",
    "dexscreener": "https://dexscreener.com",
    # Local / Self-hosted
    "n8n": "http://localhost:5678",
    "lm studio": "http://localhost:1234",
    "dashboard": "http://localhost:3000",
    # Utilitaires
    "amazon": "https://www.amazon.fr",
    "leboncoin": "https://www.leboncoin.fr",
    "wikipedia": "https://fr.wikipedia.org",
    "deepl": "https://www.deepl.com/translator",
}


# ═══════════════════════════════════════════════════════════════════════════
# FUZZY MATCHING & VOICE CORRECTION
# ═══════════════════════════════════════════════════════════════════════════

# Corrections courantes de reconnaissance vocale (erreurs frequentes)
VOICE_CORRECTIONS: dict[str, str] = {
    # Mots souvent mal reconnus
    "ouvres": "ouvre",
    "ouvert": "ouvre",
    "ouverts": "ouvre",
    "lances": "lance",
    "lancee": "lance",
    "cherches": "cherche",
    "recherches": "recherche",
    "va-sur": "va sur",
    "vasur": "va sur",
    "vas sur": "va sur",
    "demarre": "demarre",
    "demarres": "demarre",
    "navigue": "navigue",
    "navigues": "navigue",
    # Apps mal reconnues
    "crome": "chrome",
    "krome": "chrome",
    "crohm": "chrome",
    "crom": "chrome",
    "grome": "chrome",
    "chronme": "chrome",
    "comete": "comet",
    "comette": "comet",
    "kommet": "comet",
    "komete": "comet",
    "komett": "comet",
    "vscod": "vscode",
    "vis code": "vscode",
    "visualstudiocode": "vscode",
    "el m studio": "lm studio",
    "aile m studio": "lm studio",
    "elle m studio": "lm studio",
    "elle emme studio": "lm studio",
    # Sites mal reconnus
    "gougueule": "google",
    "gougle": "google",
    "gogol": "google",
    "gogle": "google",
    "gemail": "gmail",
    "jimail": "gmail",
    "jmail": "gmail",
    "g mail": "gmail",
    "you tube": "youtube",
    "youtub": "youtube",
    "git hub": "github",
    "guithub": "github",
    "git-hub": "github",
    "tredingview": "tradingview",
    "traiding view": "tradingview",
    "trading vue": "tradingview",
    # Trading mal reconnu
    "breakaout": "breakout",
    "brequaout": "breakout",
    "brecaoutte": "breakout",
    "snipeur": "sniper",
    "snaiper": "sniper",
    "skanne": "scanne",
    "skane": "scan",
    "pipelaïne": "pipeline",
    "pailpelaïne": "pipeline",
    "consencus": "consensus",
    "consansus": "consensus",
    # Systeme mal reconnu
    "verouille": "verrouille",
    "verrouie": "verrouille",
    "eteint": "eteins",
    "etteint": "eteins",
    "redemarrre": "redemarre",
    "captur": "capture",
    # Mots francais courants mal transcrits
    "processuce": "processus",
    "procaissus": "processus",
    "sisteme": "systeme",
    "sisthem": "systeme",
    "cleussteur": "cluster",
    "clustere": "cluster",
    "téléchargement": "telechargements",
    "telechargement": "telechargements",
}


def correct_voice_text(text: str) -> str:
    """Apply known voice corrections to transcribed text."""
    text = text.lower().strip()

    # Apply word-level corrections
    words = text.split()
    corrected = []
    for word in words:
        corrected.append(VOICE_CORRECTIONS.get(word, word))
    text = " ".join(corrected)

    # Apply phrase-level corrections
    for wrong, right in VOICE_CORRECTIONS.items():
        if wrong in text:
            text = text.replace(wrong, right)

    return text


def similarity(a: str, b: str) -> float:
    """Calculate string similarity ratio (0.0 to 1.0)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def match_command(voice_text: str, threshold: float = 0.55) -> tuple[JarvisCommand | None, dict[str, str], float]:
    """Match voice input to a pre-registered command.

    Returns: (command, extracted_params, confidence_score)
    """
    # Step 1: Correct common voice errors
    corrected = correct_voice_text(voice_text)

    best_match: JarvisCommand | None = None
    best_score: float = 0.0
    best_params: dict[str, str] = {}

    for cmd in COMMANDS:
        for trigger in cmd.triggers:
            # Check if trigger has parameters (phrases a trou)
            if "{" in trigger:
                # Extract parameter pattern
                param_names = re.findall(r"\{(\w+)\}", trigger)
                # Build regex from trigger template
                pattern = trigger
                for pname in param_names:
                    pattern = pattern.replace(f"{{{pname}}}", r"(.+)")
                pattern = "^" + pattern + "$"

                match = re.match(pattern, corrected, re.IGNORECASE)
                if match:
                    score = 0.95
                    params = {param_names[i]: match.group(i + 1).strip() for i in range(len(param_names))}
                    if score > best_score:
                        best_score = score
                        best_match = cmd
                        best_params = params
                else:
                    # Try fuzzy match on the fixed parts
                    fixed_part = re.sub(r"\{(\w+)\}", "", trigger).strip()
                    if fixed_part and fixed_part in corrected:
                        remaining = corrected.replace(fixed_part, "").strip()
                        if remaining:
                            score = 0.80
                            params = {param_names[0]: remaining} if param_names else {}
                            if score > best_score:
                                best_score = score
                                best_match = cmd
                                best_params = params
            else:
                # Exact match
                if corrected == trigger.lower():
                    score = 1.0
                elif trigger.lower() in corrected:
                    score = 0.90
                else:
                    score = similarity(corrected, trigger)

                if score > best_score:
                    best_score = score
                    best_match = cmd
                    best_params = {}

    if best_score < threshold:
        return None, {}, best_score

    return best_match, best_params, best_score


def get_commands_by_category(category: str | None = None) -> list[JarvisCommand]:
    """List commands, optionally filtered by category."""
    if category:
        return [c for c in COMMANDS if c.category == category]
    return COMMANDS


def format_commands_help() -> str:
    """Format all commands as help text for voice output."""
    categories = {}
    for cmd in COMMANDS:
        categories.setdefault(cmd.category, []).append(cmd)

    lines = ["Commandes JARVIS disponibles:"]
    cat_names = {
        "navigation": "Navigation Web",
        "fichiers": "Fichiers & Documents",
        "app": "Applications",
        "systeme": "Systeme Windows",
        "trading": "Trading",
        "jarvis": "Controle JARVIS",
    }
    for cat, cmds in categories.items():
        lines.append(f"\n  {cat_names.get(cat, cat)}:")
        for cmd in cmds:
            trigger_example = cmd.triggers[0]
            lines.append(f"    - {trigger_example} → {cmd.description}")
    return "\n".join(lines)
