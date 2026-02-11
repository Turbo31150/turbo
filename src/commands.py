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
    JarvisCommand("fermer_onglet", "navigation", "Fermer l'onglet actif", [
        "ferme l'onglet", "ferme cet onglet", "ferme le tab",
        "close tab", "fermer l'onglet",
    ], "hotkey", "ctrl+w"),

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
    JarvisCommand("ouvrir_explorateur", "fichiers", "Ouvrir l'explorateur de fichiers", [
        "ouvre l'explorateur", "ouvre l'explorateur de fichiers",
        "explorateur de fichiers", "ouvre explorer",
    ], "hotkey", "win+e"),
    JarvisCommand("lister_dossier", "fichiers", "Lister le contenu d'un dossier", [
        "que contient {dossier}", "liste le dossier {dossier}",
        "contenu du dossier {dossier}", "affiche le dossier {dossier}",
    ], "jarvis_tool", "list_folder:{dossier}", ["dossier"]),
    JarvisCommand("creer_dossier", "fichiers", "Creer un nouveau dossier", [
        "cree un dossier {nom}", "nouveau dossier {nom}",
        "cree le dossier {nom}", "creer dossier {nom}",
    ], "jarvis_tool", "create_folder:{nom}", ["nom"]),
    JarvisCommand("chercher_fichier", "fichiers", "Chercher un fichier", [
        "cherche le fichier {nom}", "trouve le fichier {nom}",
        "ou est le fichier {nom}", "recherche fichier {nom}",
    ], "jarvis_tool", "search_files:{nom}", ["nom"]),

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
        "ouvre diskord", "lance diskord",
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
    JarvisCommand("sauvegarder", "clipboard", "Sauvegarder le fichier actif", [
        "sauvegarde", "enregistre", "save", "sauvegarder",
        "enregistrer", "ctrl s",
    ], "hotkey", "ctrl+s"),
    JarvisCommand("refaire", "clipboard", "Refaire la derniere action annulee", [
        "refais", "redo", "refaire", "ctrl y",
        "retablis", "retablir",
    ], "hotkey", "ctrl+y"),
    JarvisCommand("recherche_page", "clipboard", "Rechercher dans la page", [
        "recherche dans la page", "cherche dans la page", "find",
        "ctrl f", "recherche texte",
    ], "hotkey", "ctrl+f"),
    JarvisCommand("lire_presse_papier", "clipboard", "Lire le contenu du presse-papier", [
        "lis le presse-papier", "qu'est-ce qui est copie",
        "contenu du presse-papier", "montre le presse-papier",
    ], "jarvis_tool", "clipboard_get"),
    JarvisCommand("historique_clipboard", "clipboard", "Historique du presse-papier", [
        "historique du presse-papier", "clipboard history",
        "historique presse-papier", "historique copie",
    ], "hotkey", "win+v"),

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

    # ── Raccourcis Windows supplementaires ──
    JarvisCommand("ouvrir_run", "systeme", "Ouvrir la boite Executer", [
        "ouvre executer", "boite de dialogue executer", "run",
        "ouvre run", "ouvrir executer",
    ], "hotkey", "win+r"),
    JarvisCommand("recherche_windows", "systeme", "Recherche Windows", [
        "recherche windows", "cherche sur le pc", "recherche sur le pc",
        "recherche dans windows", "search windows",
    ], "hotkey", "win+s"),
    JarvisCommand("centre_notifications", "systeme", "Ouvrir le centre de notifications", [
        "ouvre les notifications", "notifications", "centre de notifications",
        "ouvre le centre de notifications",
    ], "hotkey", "win+n"),
    JarvisCommand("ouvrir_widgets", "systeme", "Ouvrir les widgets", [
        "ouvre les widgets", "widgets", "affiche les widgets",
        "ouvre le panneau widgets",
    ], "hotkey", "win+w"),
    JarvisCommand("ouvrir_emojis", "systeme", "Ouvrir le panneau emojis", [
        "ouvre les emojis", "emojis", "panneau emojis",
        "selecteur emojis",
    ], "hotkey", "win+;"),
    JarvisCommand("projeter_ecran", "systeme", "Projeter l'ecran", [
        "projette l'ecran", "duplique l'ecran", "mode ecran",
        "projeter", "projection ecran",
    ], "hotkey", "win+p"),

    # ── Bureaux virtuels Windows 11 ──
    JarvisCommand("vue_taches", "systeme", "Vue des taches / bureaux virtuels", [
        "vue des taches", "bureaux virtuels", "task view",
        "ouvre la vue des taches", "ouvre les bureaux virtuels",
    ], "hotkey", "win+tab"),
    JarvisCommand("bureau_suivant", "systeme", "Passer au bureau virtuel suivant", [
        "bureau suivant", "prochain bureau", "next desktop",
        "bureau virtuel suivant",
    ], "hotkey", "ctrl+win+right"),
    JarvisCommand("bureau_precedent", "systeme", "Passer au bureau virtuel precedent", [
        "bureau precedent", "bureau virtuel precedent",
        "previous desktop", "bureau d'avant",
    ], "hotkey", "ctrl+win+left"),

    # ── Parametres Windows (ms-settings:) ──
    JarvisCommand("ouvrir_parametres", "systeme", "Ouvrir les parametres Windows", [
        "ouvre les parametres", "parametres", "reglages",
        "ouvre les reglages", "ouvrir parametres", "settings",
    ], "ms_settings", "ms-settings:"),
    JarvisCommand("param_wifi", "systeme", "Parametres Wi-Fi", [
        "parametres wifi", "reglages wifi", "ouvre les parametres wifi",
        "config wifi",
    ], "ms_settings", "ms-settings:network-wifi"),
    JarvisCommand("param_bluetooth", "systeme", "Parametres Bluetooth", [
        "parametres bluetooth", "reglages bluetooth",
        "ouvre les parametres bluetooth", "config bluetooth",
    ], "ms_settings", "ms-settings:bluetooth"),
    JarvisCommand("param_affichage", "systeme", "Parametres d'affichage", [
        "parametres affichage", "reglages ecran", "parametres ecran",
        "config affichage",
    ], "ms_settings", "ms-settings:display"),
    JarvisCommand("param_son", "systeme", "Parametres son", [
        "parametres son", "reglages audio", "parametres audio",
        "config son",
    ], "ms_settings", "ms-settings:sound"),
    JarvisCommand("param_stockage", "systeme", "Espace disque et stockage", [
        "espace disque", "stockage", "parametres stockage",
        "reglages stockage", "combien d'espace",
    ], "ms_settings", "ms-settings:storagesense"),
    JarvisCommand("param_mises_a_jour", "systeme", "Mises a jour Windows", [
        "mises a jour", "windows update", "mise a jour",
        "verifie les mises a jour", "updates",
    ], "ms_settings", "ms-settings:windowsupdate"),
    JarvisCommand("param_alimentation", "systeme", "Parametres d'alimentation", [
        "parametres alimentation", "economie energie",
        "reglages alimentation", "gestion energie",
    ], "ms_settings", "ms-settings:powersleep"),

    # ── Bluetooth on/off ──
    JarvisCommand("bluetooth_on", "systeme", "Activer le Bluetooth", [
        "active le bluetooth", "allume bluetooth", "bluetooth on",
        "active bluetooth", "allume le bluetooth",
    ], "powershell", "Add-Type -AssemblyName System.Runtime.WindowsRuntime; $radio = [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]::GetRadiosAsync().GetAwaiter().GetResult() | Where-Object { $_.Kind -eq 'Bluetooth' }; if($radio) { $radio[0].SetStateAsync('On').GetAwaiter().GetResult() | Out-Null; 'Bluetooth active' } else { 'Aucun adaptateur Bluetooth' }"),
    JarvisCommand("bluetooth_off", "systeme", "Desactiver le Bluetooth", [
        "desactive le bluetooth", "coupe bluetooth", "bluetooth off",
        "desactive bluetooth", "coupe le bluetooth",
    ], "powershell", "Add-Type -AssemblyName System.Runtime.WindowsRuntime; $radio = [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]::GetRadiosAsync().GetAwaiter().GetResult() | Where-Object { $_.Kind -eq 'Bluetooth' }; if($radio) { $radio[0].SetStateAsync('Off').GetAwaiter().GetResult() | Out-Null; 'Bluetooth desactive' } else { 'Aucun adaptateur Bluetooth' }"),

    # ── Luminosite ──
    JarvisCommand("luminosite_haut", "systeme", "Augmenter la luminosite", [
        "augmente la luminosite", "plus lumineux", "luminosite plus",
        "monte la luminosite",
    ], "powershell", "$b = (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness; $n = [Math]::Min(100, $b + 10); (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, $n); \"Luminosite: $n%\""),
    JarvisCommand("luminosite_bas", "systeme", "Baisser la luminosite", [
        "baisse la luminosite", "moins lumineux", "luminosite moins",
        "diminue la luminosite",
    ], "powershell", "$b = (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness; $n = [Math]::Max(0, $b - 10); (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, $n); \"Luminosite: $n%\""),

    # ── Services Windows via MCP ──
    JarvisCommand("lister_services", "systeme", "Lister les services Windows", [
        "liste les services", "services windows", "quels services",
        "montre les services",
    ], "jarvis_tool", "list_services"),
    JarvisCommand("demarrer_service", "systeme", "Demarrer un service Windows", [
        "demarre le service {nom}", "start service {nom}",
        "lance le service {nom}",
    ], "jarvis_tool", "start_service:{nom}", ["nom"]),
    JarvisCommand("arreter_service", "systeme", "Arreter un service Windows", [
        "arrete le service {nom}", "stop service {nom}",
        "stoppe le service {nom}",
    ], "jarvis_tool", "stop_service:{nom}", ["nom"], confirm=True),

    # ── Infos systeme supplementaires ──
    JarvisCommand("resolution_ecran", "systeme", "Resolution de l'ecran", [
        "resolution ecran", "quelle resolution", "resolution de l'ecran",
        "taille ecran",
    ], "jarvis_tool", "screen_resolution"),
    JarvisCommand("taches_planifiees", "systeme", "Taches planifiees Windows", [
        "taches planifiees", "taches automatiques", "scheduled tasks",
        "taches programmees",
    ], "jarvis_tool", "scheduled_tasks"),

    # ── Mode avion / micro / camera ──
    JarvisCommand("mode_avion_on", "systeme", "Activer le mode avion", [
        "active le mode avion", "mode avion", "mode avion on",
        "coupe le reseau", "active mode avion",
    ], "ms_settings", "ms-settings:network-airplanemode"),
    JarvisCommand("micro_mute", "systeme", "Couper le microphone", [
        "coupe le micro", "mute le micro", "micro off",
        "desactive le micro", "silence micro",
    ], "powershell", "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class A{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte k,byte s,int f,int e);}'; [A]::keybd_event(0xAD,0,0,0); [A]::keybd_event(0xAD,0,2,0)"),
    JarvisCommand("micro_unmute", "systeme", "Reactiver le microphone", [
        "reactive le micro", "unmute micro", "micro on",
        "active le micro", "rallume le micro",
    ], "powershell", "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class A{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte k,byte s,int f,int e);}'; [A]::keybd_event(0xAD,0,0,0); [A]::keybd_event(0xAD,0,2,0)"),
    JarvisCommand("param_camera", "systeme", "Parametres camera", [
        "parametres camera", "reglages camera", "config camera",
        "ouvre les parametres camera",
    ], "ms_settings", "ms-settings:privacy-webcam"),

    # ── Bureaux virtuels avances ──
    JarvisCommand("nouveau_bureau", "systeme", "Creer un nouveau bureau virtuel", [
        "nouveau bureau", "cree un bureau", "ajoute un bureau",
        "nouveau bureau virtuel", "new desktop",
    ], "hotkey", "ctrl+win+d"),
    JarvisCommand("fermer_bureau", "systeme", "Fermer le bureau virtuel actif", [
        "ferme le bureau", "ferme ce bureau", "supprime le bureau",
        "ferme le bureau virtuel", "close desktop",
    ], "hotkey", "ctrl+win+F4"),

    # ── Navigation/Edition supplementaire ──
    JarvisCommand("zoom_avant", "systeme", "Zoomer", [
        "zoom avant", "zoom plus", "agrandis", "zoome",
        "plus gros",
    ], "hotkey", "ctrl++"),
    JarvisCommand("zoom_arriere", "systeme", "Dezoomer", [
        "zoom arriere", "zoom moins", "retrecis", "dezoome",
        "plus petit",
    ], "hotkey", "ctrl+-"),
    JarvisCommand("zoom_reset", "systeme", "Reinitialiser le zoom", [
        "zoom normal", "zoom reset", "taille normale",
        "reinitialise le zoom",
    ], "hotkey", "ctrl+0"),
    JarvisCommand("imprimer", "systeme", "Imprimer", [
        "imprime", "imprimer", "print", "lance l'impression",
        "ctrl p",
    ], "hotkey", "ctrl+p"),
    JarvisCommand("renommer", "systeme", "Renommer le fichier selectionne", [
        "renomme", "renommer", "rename",
        "renomme le fichier", "change le nom",
    ], "hotkey", "F2"),
    JarvisCommand("supprimer", "systeme", "Supprimer le fichier selectionne", [
        "supprime", "supprimer", "delete",
        "envoie a la corbeille", "mets a la corbeille",
    ], "hotkey", "delete"),
    JarvisCommand("proprietes", "systeme", "Proprietes du fichier selectionne", [
        "proprietes", "proprietes du fichier", "infos fichier",
        "details du fichier",
    ], "hotkey", "alt+enter"),
    JarvisCommand("actualiser", "systeme", "Actualiser la page ou le dossier", [
        "actualise", "rafraichis", "refresh", "recharge",
        "actualiser", "F5",
    ], "hotkey", "F5"),

    # ── Verrouillage rapide ──
    JarvisCommand("verrouiller_rapide", "systeme", "Verrouiller le PC rapidement", [
        "verrouille", "lock", "verrouille vite",
        "bloque l'ecran",
    ], "hotkey", "win+l"),

    # ── Accessibilite Windows ──
    JarvisCommand("loupe", "systeme", "Activer la loupe / zoom accessibilite", [
        "active la loupe", "loupe", "magnifier",
        "zoom accessibilite", "agrandis l'ecran",
    ], "hotkey", "win++"),
    JarvisCommand("loupe_off", "systeme", "Desactiver la loupe", [
        "desactive la loupe", "ferme la loupe", "loupe off",
        "arrete la loupe",
    ], "hotkey", "win+escape"),
    JarvisCommand("narrateur", "systeme", "Activer/desactiver le narrateur", [
        "active le narrateur", "narrateur", "narrator",
        "desactive le narrateur", "lecteur ecran",
    ], "hotkey", "ctrl+win+enter"),
    JarvisCommand("clavier_visuel", "systeme", "Ouvrir le clavier visuel", [
        "clavier visuel", "ouvre le clavier", "clavier ecran",
        "on screen keyboard", "clavier tactile",
    ], "powershell", "Start-Process osk"),
    JarvisCommand("dictee", "systeme", "Activer la dictee vocale Windows", [
        "dictee", "dictee vocale", "lance la dictee",
        "mode dictee", "dicte", "ecrire avec la voix",
    ], "hotkey", "win+h"),
    JarvisCommand("contraste_eleve", "systeme", "Activer le mode contraste eleve", [
        "contraste eleve", "high contrast", "mode contraste",
        "active le contraste",
    ], "hotkey", "alt+shift+print"),
    JarvisCommand("param_accessibilite", "systeme", "Parametres d'accessibilite", [
        "parametres accessibilite", "reglages accessibilite",
        "accessibilite", "options accessibilite",
    ], "ms_settings", "ms-settings:easeofaccess"),

    # ── Multimedia / Enregistrement ──
    JarvisCommand("enregistrer_ecran", "systeme", "Enregistrer l'ecran (Xbox Game Bar)", [
        "enregistre l'ecran", "lance l'enregistrement", "record",
        "capture video", "enregistrement ecran", "screen record",
    ], "hotkey", "win+alt+r"),
    JarvisCommand("game_bar", "systeme", "Ouvrir la Xbox Game Bar", [
        "ouvre la game bar", "game bar", "xbox game bar",
        "barre de jeu",
    ], "hotkey", "win+g"),
    JarvisCommand("snap_layout", "systeme", "Ouvrir les dispositions Snap", [
        "snap layout", "disposition fenetre", "snap",
        "dispositions", "arrange les fenetres",
    ], "hotkey", "win+z"),

    # ── Gestion alimentation ──
    JarvisCommand("plan_performance", "systeme", "Activer le mode performances", [
        "mode performance", "performances maximales", "haute performance",
        "plan performance", "max power",
    ], "powershell", "powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c; 'Mode haute performance active'"),
    JarvisCommand("plan_equilibre", "systeme", "Activer le mode equilibre", [
        "mode equilibre", "plan equilibre", "balanced",
        "mode normal", "puissance normale",
    ], "powershell", "powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e; 'Mode equilibre active'"),
    JarvisCommand("plan_economie", "systeme", "Activer le mode economie d'energie", [
        "mode economie", "economie d'energie", "power saver",
        "economise la batterie", "mode batterie",
    ], "powershell", "powercfg /setactive a1841308-3541-4fab-bc81-f71556f20b4a; 'Mode economie active'"),

    # ── Reseau avance ──
    JarvisCommand("ipconfig", "systeme", "Afficher la configuration IP", [
        "montre l'ip", "quelle est mon adresse ip", "ipconfig",
        "adresse ip", "config ip",
    ], "jarvis_tool", "get_ip"),
    JarvisCommand("vider_dns", "systeme", "Vider le cache DNS", [
        "vide le cache dns", "flush dns", "nettoie le dns",
        "vider dns", "purge dns",
    ], "powershell", "ipconfig /flushdns"),
    JarvisCommand("param_vpn", "systeme", "Parametres VPN", [
        "parametres vpn", "reglages vpn", "config vpn",
        "ouvre le vpn", "vpn",
    ], "ms_settings", "ms-settings:network-vpn"),
    JarvisCommand("param_proxy", "systeme", "Parametres proxy", [
        "parametres proxy", "reglages proxy", "config proxy",
        "ouvre le proxy",
    ], "ms_settings", "ms-settings:network-proxy"),

    # ── Fichiers rapides ──
    JarvisCommand("ouvrir_recents", "fichiers", "Ouvrir les fichiers recents", [
        "fichiers recents", "ouvre les recents", "derniers fichiers",
        "fichiers ouverts recemment",
    ], "powershell", "Start-Process explorer.exe -ArgumentList 'shell:Recent'"),
    JarvisCommand("ouvrir_temp", "fichiers", "Ouvrir le dossier temporaire", [
        "ouvre le dossier temp", "fichiers temporaires", "dossier temp",
        "ouvre temp",
    ], "powershell", "Start-Process explorer.exe -ArgumentList $env:TEMP"),
    JarvisCommand("ouvrir_appdata", "fichiers", "Ouvrir le dossier AppData", [
        "ouvre appdata", "dossier appdata", "ouvre app data",
        "appdata",
    ], "powershell", "Start-Process explorer.exe -ArgumentList $env:APPDATA"),

    # ── Navigation Chrome avancee ──
    JarvisCommand("mode_incognito", "navigation", "Ouvrir Chrome en mode incognito", [
        "mode incognito", "navigation privee", "ouvre en prive",
        "incognito", "mode prive",
    ], "powershell", "Start-Process chrome '-incognito'"),
    JarvisCommand("historique_chrome", "navigation", "Ouvrir l'historique Chrome", [
        "historique chrome", "ouvre l'historique", "historique navigateur",
        "historique de navigation",
    ], "hotkey", "ctrl+h"),
    JarvisCommand("favoris_chrome", "navigation", "Ouvrir les favoris Chrome", [
        "ouvre les favoris", "favoris", "bookmarks",
        "mes favoris", "signets",
    ], "hotkey", "ctrl+d"),
    JarvisCommand("telecharger_chrome", "navigation", "Ouvrir les telechargements Chrome", [
        "telechargements chrome", "ouvre les downloads",
        "mes telechargements navigateur",
    ], "hotkey", "ctrl+j"),

    # ── Vague 4: Multi-ecran / Focus Assist / Taskbar / Night Light / Disques ──
    JarvisCommand("etendre_ecran", "systeme", "Etendre l'affichage sur un second ecran", [
        "etends l'ecran", "double ecran", "ecran etendu",
        "affiche sur deux ecrans", "mode etendu",
    ], "powershell", "DisplaySwitch.exe /extend"),
    JarvisCommand("dupliquer_ecran", "systeme", "Dupliquer l'affichage", [
        "duplique l'ecran", "meme image", "ecran duplique",
        "miroir", "copie l'ecran",
    ], "powershell", "DisplaySwitch.exe /clone"),
    JarvisCommand("ecran_principal_seul", "systeme", "Afficher uniquement sur l'ecran principal", [
        "ecran principal seulement", "un seul ecran", "desactive le second ecran",
        "ecran principal uniquement",
    ], "powershell", "DisplaySwitch.exe /internal"),
    JarvisCommand("ecran_secondaire_seul", "systeme", "Afficher uniquement sur le second ecran", [
        "ecran secondaire seulement", "second ecran uniquement",
        "affiche sur l'autre ecran", "ecran externe",
    ], "powershell", "DisplaySwitch.exe /external"),
    JarvisCommand("focus_assist_on", "systeme", "Activer l'aide a la concentration (ne pas deranger)", [
        "ne pas deranger", "focus assist", "mode silencieux",
        "active ne pas deranger", "desactive les notifications",
    ], "powershell", "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings' -Name 'NOC_GLOBAL_SETTING_ALLOW_NOTIFICATION_SOUND' -Value 0; 'Focus Assist active'"),
    JarvisCommand("focus_assist_off", "systeme", "Desactiver l'aide a la concentration", [
        "desactive ne pas deranger", "reactive les notifications",
        "focus assist off", "notifications normales",
    ], "powershell", "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings' -Name 'NOC_GLOBAL_SETTING_ALLOW_NOTIFICATION_SOUND' -Value 1; 'Focus Assist desactive'"),
    JarvisCommand("taskbar_hide", "systeme", "Masquer la barre des taches", [
        "cache la barre des taches", "masque la taskbar",
        "barre des taches invisible", "hide taskbar",
    ], "powershell", "$p = 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\StuckRects3'; $v = (Get-ItemProperty -Path $p).Settings; $v[8] = 3; Set-ItemProperty -Path $p -Name Settings -Value $v; Stop-Process -Name explorer -Force; 'Taskbar masquee'"),
    JarvisCommand("taskbar_show", "systeme", "Afficher la barre des taches", [
        "montre la barre des taches", "affiche la taskbar",
        "barre des taches visible", "show taskbar",
    ], "powershell", "$p = 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\StuckRects3'; $v = (Get-ItemProperty -Path $p).Settings; $v[8] = 2; Set-ItemProperty -Path $p -Name Settings -Value $v; Stop-Process -Name explorer -Force; 'Taskbar affichee'"),
    JarvisCommand("night_light_on", "systeme", "Activer l'eclairage nocturne", [
        "active la lumiere nocturne", "night light on", "eclairage nocturne",
        "lumiere chaude", "filtre lumiere bleue on",
    ], "powershell", "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\CloudStore\\Store\\DefaultAccount\\Current\\default$windows.data.bluelightreduction.settings\\windows.data.bluelightreduction.settings' -Name 'Data' -Value ([byte[]](2,0,0,0,0x38,0,0,0,2,1,0xCA,0x14,0x0E,0x15,0,0,0,0x2A,6,0xFE,0xD2,0xB3,0xA5,0x04,0,0,0x43,0x42,1,0)); 'Night Light active'"),
    JarvisCommand("night_light_off", "systeme", "Desactiver l'eclairage nocturne", [
        "desactive la lumiere nocturne", "night light off",
        "lumiere normale", "filtre lumiere bleue off",
    ], "powershell", "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\CloudStore\\Store\\DefaultAccount\\Current\\default$windows.data.bluelightreduction.settings\\windows.data.bluelightreduction.settings' -Name 'Data' -Value ([byte[]](2,0,0,0,0x38,0,0,0,0,1,0xCA,0x14,0x0E,0x15,0,0,0,0x2A,6,0xFE,0xD2,0xB3,0xA5,0x04,0,0,0x43,0x42,1,0)); 'Night Light desactive'"),
    JarvisCommand("info_disques", "systeme", "Afficher l'espace disque", [
        "espace disque", "info disques", "combien de place",
        "espace libre", "taille des disques",
    ], "powershell", "Get-CimInstance Win32_LogicalDisk | Select DeviceID, @{N='Total(GB)';E={[math]::Round($_.Size/1GB,1)}}, @{N='Free(GB)';E={[math]::Round($_.FreeSpace/1GB,1)}}, @{N='Used%';E={[math]::Round(($_.Size-$_.FreeSpace)/$_.Size*100,1)}} | Out-String"),
    JarvisCommand("vider_temp", "systeme", "Vider les fichiers temporaires", [
        "vide les fichiers temporaires", "nettoie les temp",
        "supprime les temp", "clean temp",
    ], "powershell", "$before = (Get-ChildItem $env:TEMP -Recurse -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB; Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; $after = (Get-ChildItem $env:TEMP -Recurse -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB; \"Temp nettoye: $([math]::Round($before - $after, 1)) MB liberes\"", confirm=True),
    JarvisCommand("ouvrir_alarmes", "systeme", "Ouvrir l'application Horloge/Alarmes", [
        "ouvre les alarmes", "alarme", "minuteur", "timer",
        "chronometre", "ouvre l'horloge",
    ], "app_open", "ms-clock:"),
    JarvisCommand("historique_activite", "systeme", "Ouvrir l'historique d'activite Windows", [
        "historique activite", "timeline", "activites recentes",
        "que faisais-je", "historique windows",
    ], "ms_settings", "ms-settings:privacy-activityhistory"),
    JarvisCommand("param_clavier", "systeme", "Parametres clavier", [
        "parametres clavier", "reglages clavier", "config clavier",
        "langue du clavier", "disposition clavier",
    ], "ms_settings", "ms-settings:keyboard"),
    JarvisCommand("param_souris", "systeme", "Parametres souris", [
        "parametres souris", "reglages souris", "config souris",
        "vitesse souris", "sensibilite souris",
    ], "ms_settings", "ms-settings:mousetouchpad"),
    JarvisCommand("param_batterie", "systeme", "Parametres batterie", [
        "parametres batterie", "etat batterie", "batterie",
        "niveau batterie", "autonomie",
    ], "ms_settings", "ms-settings:batterysaver"),
    JarvisCommand("param_comptes", "systeme", "Parametres des comptes utilisateur", [
        "parametres comptes", "comptes utilisateur", "mon compte",
        "gestion comptes",
    ], "ms_settings", "ms-settings:accounts"),
    JarvisCommand("param_heure", "systeme", "Parametres date et heure", [
        "parametres heure", "reglages heure", "date et heure",
        "quelle heure est-il", "fuseau horaire",
    ], "ms_settings", "ms-settings:dateandtime"),
    JarvisCommand("param_langue", "systeme", "Parametres de langue", [
        "parametres langue", "changer la langue", "langue windows",
        "langue du systeme",
    ], "ms_settings", "ms-settings:regionlanguage"),

    # ── Vague 5: Securite / DevTools / Partage / Maintenance avancee ──
    JarvisCommand("windows_security", "systeme", "Ouvrir Windows Security", [
        "ouvre la securite", "securite windows", "windows security",
        "antivirus", "protection virus", "defender",
    ], "app_open", "windowsdefender:"),
    JarvisCommand("pare_feu", "systeme", "Parametres du pare-feu", [
        "parametres pare-feu", "firewall", "ouvre le pare-feu",
        "reglages pare-feu", "pare feu",
    ], "ms_settings", "ms-settings:windowsdefender"),
    JarvisCommand("partage_proximite", "systeme", "Parametres de partage a proximite", [
        "partage a proximite", "nearby sharing", "partage rapide",
        "envoyer a un appareil", "partage bluetooth",
    ], "ms_settings", "ms-settings:crossdevice"),
    JarvisCommand("hotspot", "systeme", "Activer le point d'acces mobile", [
        "point d'acces", "hotspot", "partage de connexion",
        "active le hotspot", "partage wifi",
    ], "ms_settings", "ms-settings:network-mobilehotspot"),
    JarvisCommand("defrag_disque", "systeme", "Optimiser les disques (defragmentation)", [
        "defragmente", "optimise les disques", "defragmentation",
        "defrag", "optimise le disque",
    ], "powershell", "Start-Process dfrgui"),
    JarvisCommand("gestion_disques", "systeme", "Ouvrir le gestionnaire de disques", [
        "gestionnaire de disques", "gestion des disques", "disk manager",
        "ouvre les disques", "partitions",
    ], "powershell", "Start-Process diskmgmt.msc"),
    JarvisCommand("variables_env", "systeme", "Ouvrir les variables d'environnement", [
        "variables d'environnement", "variables env", "env variables",
        "ouvre les variables", "path windows",
    ], "powershell", "Start-Process rundll32.exe -ArgumentList 'sysdm.cpl,EditEnvironmentVariables'"),
    JarvisCommand("evenements_windows", "systeme", "Ouvrir l'observateur d'evenements", [
        "observateur d'evenements", "event viewer", "journaux windows",
        "logs windows", "evenements systeme",
    ], "powershell", "Start-Process eventvwr.msc"),
    JarvisCommand("moniteur_ressources", "systeme", "Ouvrir le moniteur de ressources", [
        "moniteur de ressources", "resource monitor", "ressources systeme",
        "moniteur performances", "perfmon",
    ], "powershell", "Start-Process resmon"),
    JarvisCommand("info_systeme_detaille", "systeme", "Ouvrir les informations systeme detaillees", [
        "informations systeme detaillees", "msinfo", "infos systeme avancees",
        "specs du pc", "configuration detaillee",
    ], "powershell", "Start-Process msinfo32"),
    JarvisCommand("nettoyage_disque", "systeme", "Ouvrir le nettoyage de disque Windows", [
        "nettoyage de disque", "disk cleanup", "nettoie le disque",
        "clean disk", "libere de l'espace",
    ], "powershell", "Start-Process cleanmgr"),
    JarvisCommand("gestionnaire_peripheriques", "systeme", "Ouvrir le gestionnaire de peripheriques", [
        "gestionnaire de peripheriques", "device manager",
        "mes peripheriques", "drivers", "pilotes",
    ], "powershell", "Start-Process devmgmt.msc"),
    JarvisCommand("connexions_reseau", "systeme", "Ouvrir les connexions reseau", [
        "connexions reseau", "adaptateurs reseau", "network connections",
        "cartes reseau", "interfaces reseau",
    ], "powershell", "Start-Process ncpa.cpl"),
    JarvisCommand("programmes_installees", "systeme", "Ouvrir programmes et fonctionnalites", [
        "programmes installes", "applications installees",
        "liste des programmes", "desinstaller un programme",
    ], "ms_settings", "ms-settings:appsfeatures"),
    JarvisCommand("demarrage_apps", "systeme", "Gerer les applications au demarrage", [
        "applications demarrage", "programmes au demarrage",
        "gere le demarrage", "startup apps", "autostart",
    ], "ms_settings", "ms-settings:startupapps"),
    JarvisCommand("param_confidentialite", "systeme", "Parametres de confidentialite", [
        "parametres confidentialite", "privacy", "confidentialite",
        "vie privee", "reglages confidentialite",
    ], "ms_settings", "ms-settings:privacy"),
    JarvisCommand("param_reseau_avance", "systeme", "Parametres reseau avances", [
        "parametres reseau avances", "reseau avance", "advanced network",
        "config reseau avancee",
    ], "ms_settings", "ms-settings:network-advancedsettings"),
    JarvisCommand("partager_ecran", "systeme", "Partager l'ecran via Miracast", [
        "partage l'ecran", "miracast", "cast", "diffuse l'ecran",
        "envoie l'ecran", "screen cast",
    ], "hotkey", "win+k"),

    # ── Vague 6: Personnalisation / Audio / Imprimantes / Outils avances ──
    JarvisCommand("param_imprimantes", "systeme", "Parametres imprimantes et scanners", [
        "parametres imprimantes", "imprimante", "ouvre les imprimantes",
        "scanners", "gere les imprimantes",
    ], "ms_settings", "ms-settings:printers"),
    JarvisCommand("param_fond_ecran", "systeme", "Personnaliser le fond d'ecran", [
        "fond d'ecran", "change le fond", "wallpaper",
        "arriere plan", "personnalise le bureau",
    ], "ms_settings", "ms-settings:personalization-background"),
    JarvisCommand("param_couleurs", "systeme", "Personnaliser les couleurs Windows", [
        "couleurs windows", "couleur d'accent", "theme couleur",
        "mode sombre", "mode clair", "dark mode", "light mode",
    ], "ms_settings", "ms-settings:personalization-colors"),
    JarvisCommand("param_ecran_veille", "systeme", "Parametres ecran de verrouillage", [
        "ecran de veille", "ecran de verrouillage", "lock screen",
        "personnalise l'ecran de veille",
    ], "ms_settings", "ms-settings:lockscreen"),
    JarvisCommand("param_polices", "systeme", "Gerer les polices installees", [
        "polices", "fonts", "gere les polices",
        "polices installees", "typographies",
    ], "ms_settings", "ms-settings:fonts"),
    JarvisCommand("param_themes", "systeme", "Gerer les themes Windows", [
        "themes windows", "change le theme", "personnalise le theme",
        "themes", "apparence windows",
    ], "ms_settings", "ms-settings:themes"),
    JarvisCommand("mode_sombre", "systeme", "Activer le mode sombre Windows", [
        "active le mode sombre", "dark mode on", "theme sombre",
        "passe en sombre", "mode fonce",
    ], "powershell", "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name 'AppsUseLightTheme' -Value 0; Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name 'SystemUsesLightTheme' -Value 0; 'Mode sombre active'"),
    JarvisCommand("mode_clair", "systeme", "Activer le mode clair Windows", [
        "active le mode clair", "light mode on", "theme clair",
        "passe en clair", "mode lumineux",
    ], "powershell", "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name 'AppsUseLightTheme' -Value 1; Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name 'SystemUsesLightTheme' -Value 1; 'Mode clair active'"),
    JarvisCommand("param_son_avance", "systeme", "Parametres audio avances", [
        "parametres audio avances", "son avance", "mixer audio",
        "gere les sorties audio", "peripheriques audio",
    ], "ms_settings", "ms-settings:sound-advancedoptions" if False else "ms-settings:sound"),
    JarvisCommand("param_hdr", "systeme", "Parametres HDR", [
        "parametres hdr", "active le hdr", "hdr",
        "mode hdr", "high dynamic range",
    ], "ms_settings", "ms-settings:display-advancedgraphics"),
    JarvisCommand("ouvrir_regedit", "systeme", "Ouvrir l'editeur de registre", [
        "ouvre le registre", "regedit", "editeur de registre",
        "registre windows",
    ], "powershell", "Start-Process regedit", confirm=True),
    JarvisCommand("ouvrir_mmc", "systeme", "Ouvrir la console de gestion (MMC)", [
        "console de gestion", "mmc", "ouvre mmc",
        "gestion de l'ordinateur",
    ], "powershell", "Start-Process compmgmt.msc"),
    JarvisCommand("ouvrir_politique_groupe", "systeme", "Ouvrir l'editeur de strategie de groupe", [
        "politique de groupe", "group policy", "gpedit",
        "strategie de groupe", "ouvre gpedit",
    ], "powershell", "Start-Process gpedit.msc"),
    JarvisCommand("taux_rafraichissement", "systeme", "Parametres taux de rafraichissement ecran", [
        "taux de rafraichissement", "hertz ecran", "frequence ecran",
        "combien de hertz", "refresh rate",
    ], "ms_settings", "ms-settings:display-advancedgraphics"),
    JarvisCommand("param_notifications_avance", "systeme", "Parametres notifications avances", [
        "parametres notifications avances", "gere les notifications",
        "quelles apps notifient", "notifications par app",
    ], "ms_settings", "ms-settings:notifications"),
    JarvisCommand("param_multitache", "systeme", "Parametres multitache Windows", [
        "parametres multitache", "multitasking", "reglages multitache",
        "snap assist", "bureaux virtuels reglages",
    ], "ms_settings", "ms-settings:multitasking"),

    # ── Vague 7: Energie / Stockage / Apps defaut / Sauvegarde / Restauration ──
    JarvisCommand("apps_par_defaut", "systeme", "Gerer les applications par defaut", [
        "applications par defaut", "apps par defaut", "ouvre avec",
        "navigateur par defaut", "lecteur par defaut",
    ], "ms_settings", "ms-settings:defaultapps"),
    JarvisCommand("param_stockage_avance", "systeme", "Gestion du stockage et assistant", [
        "assistant stockage", "nettoyage automatique", "stockage intelligent",
        "storage sense", "gestion stockage avancee",
    ], "ms_settings", "ms-settings:storagepolicies"),
    JarvisCommand("sauvegarder_windows", "systeme", "Parametres de sauvegarde Windows", [
        "sauvegarde windows", "backup windows", "parametres backup",
        "sauvegarde systeme", "backup systeme",
    ], "ms_settings", "ms-settings:backup"),
    JarvisCommand("restauration_systeme", "systeme", "Ouvrir la restauration du systeme", [
        "restauration systeme", "point de restauration", "system restore",
        "restaure le systeme", "reviens en arriere",
    ], "powershell", "Start-Process rstrui"),
    JarvisCommand("a_propos_pc", "systeme", "Informations sur le PC (A propos)", [
        "a propos du pc", "about pc", "nom du pc",
        "version windows", "specs du pc", "quel windows",
    ], "ms_settings", "ms-settings:about"),
    JarvisCommand("param_ethernet", "systeme", "Parametres Ethernet", [
        "parametres ethernet", "cable reseau", "connexion filaire",
        "config ethernet", "reseau filaire",
    ], "ms_settings", "ms-settings:network-ethernet"),
    JarvisCommand("param_data_usage", "systeme", "Utilisation des donnees reseau", [
        "utilisation donnees", "data usage", "consommation reseau",
        "combien de donnees", "bande passante utilisee",
    ], "ms_settings", "ms-settings:datausage"),
    JarvisCommand("tracert", "systeme", "Tracer la route vers un hote", [
        "trace la route vers {host}", "traceroute {host}", "tracert {host}",
        "chemin vers {host}",
    ], "powershell", "tracert {host} | Out-String", ["host"]),
    JarvisCommand("netstat", "systeme", "Afficher les connexions reseau actives", [
        "connexions actives", "netstat", "ports ouverts",
        "quels ports sont utilises", "connexions reseau actives",
    ], "powershell", "netstat -an | Select-Object -First 30 | Out-String"),
    JarvisCommand("uptime", "systeme", "Temps de fonctionnement du PC", [
        "uptime", "depuis quand le pc tourne", "temps de fonctionnement",
        "depuis combien de temps", "depuis quand",
    ], "powershell", "$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; $up = (Get-Date) - $boot; \"Uptime: $($up.Days)j $($up.Hours)h $($up.Minutes)m (boot: $boot)\""),
    JarvisCommand("temperature_cpu", "systeme", "Temperature du processeur", [
        "temperature cpu", "temperature processeur", "cpu temperature",
        "chauffe le cpu", "le pc chauffe",
    ], "powershell", "Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace root/WMI -ErrorAction SilentlyContinue | ForEach-Object { $t = ($_.CurrentTemperature - 2732) / 10; \"CPU: $([math]::Round($t,1)) C\" }"),
    JarvisCommand("liste_utilisateurs", "systeme", "Lister les utilisateurs du PC", [
        "liste les utilisateurs", "quels utilisateurs", "comptes locaux",
        "qui utilise le pc", "users",
    ], "powershell", "Get-LocalUser | Select Name, Enabled, LastLogon | Out-String"),
    JarvisCommand("adresse_mac", "systeme", "Afficher les adresses MAC", [
        "adresse mac", "mac address", "adresses mac",
        "quelle est mon adresse mac",
    ], "powershell", "Get-NetAdapter | Select Name, MacAddress, Status | Out-String"),
    JarvisCommand("vitesse_reseau", "systeme", "Tester la vitesse de la carte reseau", [
        "vitesse reseau", "speed test", "debit reseau",
        "quelle vitesse", "bande passante",
    ], "powershell", "Get-NetAdapter | Where Status -eq 'Up' | Select Name, LinkSpeed | Out-String"),
    JarvisCommand("param_optionnel", "systeme", "Gerer les fonctionnalites optionnelles Windows", [
        "fonctionnalites optionnelles", "optional features", "features windows",
        "activer des fonctionnalites", "composants windows",
    ], "ms_settings", "ms-settings:optionalfeatures"),
    JarvisCommand("ouvrir_sandbox", "systeme", "Ouvrir Windows Sandbox", [
        "ouvre la sandbox", "sandbox", "windows sandbox",
        "bac a sable", "lance la sandbox",
    ], "powershell", "Start-Process WindowsSandbox"),
    JarvisCommand("verifier_fichiers", "systeme", "Verifier l'integrite des fichiers systeme", [
        "verifie les fichiers systeme", "sfc scan", "scan integrite",
        "repare les fichiers", "sfc scannow",
    ], "powershell", "Start-Process powershell -ArgumentList '/c sfc /scannow' -Verb RunAs", confirm=True),

    # ── Vague 8: Docker / Git / Python / n8n / Wi-Fi avance / IA locale ──
    JarvisCommand("docker_ps", "dev", "Lister les conteneurs Docker", [
        "liste les conteneurs", "docker ps", "conteneurs docker",
        "quels conteneurs", "docker actifs",
    ], "powershell", "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | Out-String"),
    JarvisCommand("docker_images", "dev", "Lister les images Docker", [
        "images docker", "docker images", "quelles images",
        "liste les images docker",
    ], "powershell", "docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' | Out-String"),
    JarvisCommand("docker_stop_all", "dev", "Arreter tous les conteneurs Docker", [
        "arrete tous les conteneurs", "docker stop all", "stoppe docker",
        "ferme tous les conteneurs",
    ], "powershell", "docker stop $(docker ps -q) 2>$null; 'Tous les conteneurs arretes'", confirm=True),
    JarvisCommand("git_status", "dev", "Git status du projet courant", [
        "git status", "statut git", "etat du repo",
        "quels changements git", "modifs en cours",
    ], "powershell", "cd F:\\BUREAU\\turbo; git status"),
    JarvisCommand("git_log", "dev", "Git log recent", [
        "git log", "historique git", "derniers commits",
        "quels commits", "log git",
    ], "powershell", "cd F:\\BUREAU\\turbo; git log --oneline -10"),
    JarvisCommand("git_pull", "dev", "Git pull origin main", [
        "git pull", "tire les changements", "pull git",
        "mets a jour le repo", "recupere les commits",
    ], "powershell", "cd F:\\BUREAU\\turbo; git pull origin main"),
    JarvisCommand("git_push", "dev", "Git push origin main", [
        "git push", "pousse les commits", "push git",
        "envoie sur github", "pousse sur le repo",
    ], "powershell", "cd F:\\BUREAU\\turbo; git push origin main", confirm=True),
    JarvisCommand("pip_list", "dev", "Lister les packages Python installes", [
        "pip list", "packages python", "quels packages",
        "librairies python", "modules python",
    ], "powershell", "& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run --directory F:\\BUREAU\\turbo pip list | Out-String"),
    JarvisCommand("python_version", "dev", "Version Python et uv", [
        "version python", "quelle version python", "python version",
        "quelle version uv",
    ], "powershell", "& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run --directory F:\\BUREAU\\turbo python --version; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' --version"),
    JarvisCommand("wifi_connecter", "systeme", "Se connecter a un reseau Wi-Fi", [
        "connecte moi au wifi {ssid}", "connecte au wifi {ssid}",
        "rejoins le wifi {ssid}", "wifi connect {ssid}",
    ], "powershell", "netsh wlan connect name='{ssid}'", ["ssid"]),
    JarvisCommand("wifi_deconnecter", "systeme", "Se deconnecter du Wi-Fi", [
        "deconnecte le wifi", "deconnecte du wifi", "wifi off",
        "coupe le wifi", "deconnecte moi du wifi",
    ], "powershell", "netsh wlan disconnect"),
    JarvisCommand("wifi_profils", "systeme", "Lister les profils Wi-Fi sauvegardes", [
        "profils wifi", "wifi sauvegardes", "reseaux memorises",
        "wifi connus", "wifi enregistres",
    ], "powershell", "netsh wlan show profiles | Out-String"),
    JarvisCommand("ouvrir_n8n", "dev", "Ouvrir n8n dans le navigateur", [
        "ouvre n8n", "lance n8n", "n8n",
        "ouvre les workflows", "automatisation n8n",
    ], "browser", "navigate:http://localhost:5678"),
    JarvisCommand("lm_studio_restart", "dev", "Relancer LM Studio", [
        "relance lm studio", "redemarre lm studio", "restart lm studio",
        "reboot lm studio",
    ], "powershell", "Stop-Process -Name 'LM Studio' -Force -ErrorAction SilentlyContinue; Start-Sleep 2; Start-Process lmstudio; 'LM Studio relance'"),
    JarvisCommand("ouvrir_jupyter", "dev", "Ouvrir Jupyter dans le navigateur", [
        "ouvre jupyter", "lance jupyter", "jupyter notebook",
        "jupyter lab", "ouvre le notebook",
    ], "browser", "navigate:http://localhost:8888"),

    # ── Vague 9: Clipboard avance / Raccourcis app / Recherche / Automation ──
    JarvisCommand("clipboard_vider", "systeme", "Vider le presse-papier", [
        "vide le presse-papier", "efface le clipboard", "nettoie le presse-papier",
        "clear clipboard",
    ], "powershell", "Set-Clipboard -Value $null; 'Presse-papier vide'"),
    JarvisCommand("clipboard_compter", "systeme", "Compter les caracteres du presse-papier", [
        "combien de caracteres dans le presse-papier", "taille du presse-papier",
        "longueur du clipboard",
    ], "powershell", "$c = Get-Clipboard; \"Clipboard: $($c.Length) caracteres\""),
    JarvisCommand("ouvrir_paint", "app", "Ouvrir Paint", [
        "ouvre paint", "lance paint", "ouvrir paint", "dessiner",
    ], "app_open", "mspaint"),
    JarvisCommand("ouvrir_wordpad", "app", "Ouvrir WordPad", [
        "ouvre wordpad", "lance wordpad", "ouvrir wordpad",
    ], "app_open", "wordpad"),
    JarvisCommand("ouvrir_snipping", "app", "Ouvrir l'Outil Capture", [
        "ouvre l'outil capture", "lance l'outil capture", "outil de capture",
        "snipping tool", "capture avancee",
    ], "app_open", "snippingtool"),
    JarvisCommand("ouvrir_magnifier", "app", "Ouvrir la loupe Windows", [
        "ouvre la loupe windows", "loupe windows", "loupe ecran",
    ], "hotkey", "win+plus"),
    JarvisCommand("fermer_loupe", "app", "Fermer la loupe Windows", [
        "ferme la loupe", "desactive la loupe", "arrete la loupe",
    ], "hotkey", "win+escape"),
    JarvisCommand("recherche_everywhere", "systeme", "Rechercher partout sur le PC", [
        "recherche partout {terme}", "cherche partout {terme}",
        "trouve {terme} sur le pc", "recherche globale {terme}",
    ], "powershell", "Get-ChildItem -Path C:\\ -Recurse -Filter '*{terme}*' -ErrorAction SilentlyContinue | Select -First 20 FullName | Out-String", ["terme"]),
    JarvisCommand("historique_commandes", "jarvis", "Voir l'historique des commandes JARVIS", [
        "historique des commandes", "quelles commandes j'ai utilise",
        "dernieres commandes", "historique jarvis",
    ], "powershell", "if (Test-Path 'F:\\BUREAU\\turbo\\data\\action_history.json') { Get-Content 'F:\\BUREAU\\turbo\\data\\action_history.json' | ConvertFrom-Json | Select -Last 10 | Out-String } else { 'Aucun historique' }"),
    JarvisCommand("tache_planifier", "systeme", "Creer une tache planifiee", [
        "planifie une tache {nom}", "cree une tache planifiee {nom}",
        "programme {nom}", "schedule {nom}",
    ], "powershell", "Write-Output 'Pour creer une tache planifiee, precisez: nom, heure, commande'", ["nom"]),
    JarvisCommand("variables_utilisateur", "systeme", "Afficher les variables d'environnement utilisateur", [
        "variables utilisateur", "mes variables", "env utilisateur",
        "variables d'environnement utilisateur",
    ], "powershell", "[Environment]::GetEnvironmentVariables('User') | Out-String"),
    JarvisCommand("chemin_path", "systeme", "Afficher le PATH systeme", [
        "montre le path", "affiche le path", "variable path",
        "quel est le path", "path systeme",
    ], "powershell", "$env:PATH -split ';' | ForEach-Object { $_ } | Out-String"),
    JarvisCommand("ouvrir_obs", "app", "Ouvrir OBS Studio", [
        "ouvre obs", "lance obs", "obs studio", "ouvrir obs",
        "lance le stream",
    ], "app_open", "obs64"),
    JarvisCommand("ouvrir_vlc", "app", "Ouvrir VLC Media Player", [
        "ouvre vlc", "lance vlc", "ouvrir vlc",
        "lecteur multimedia",
    ], "app_open", "vlc"),
    JarvisCommand("ouvrir_7zip", "app", "Ouvrir 7-Zip", [
        "ouvre 7zip", "lance 7zip", "ouvrir 7zip",
        "ouvre 7-zip", "gestionnaire d'archives",
    ], "app_open", "7zFM"),

    # ── Vague 10: Onglets Chrome / Session / Ecrans / Saisie avancee ──
    JarvisCommand("nouvel_onglet", "navigation", "Ouvrir un nouvel onglet Chrome", [
        "nouvel onglet", "ouvre un onglet", "nouveau tab",
        "new tab", "onglet vierge",
    ], "hotkey", "ctrl+t"),
    JarvisCommand("onglet_precedent", "navigation", "Onglet precedent Chrome", [
        "onglet precedent", "tab precedent", "onglet d'avant",
        "onglet a gauche",
    ], "hotkey", "ctrl+shift+tab"),
    JarvisCommand("onglet_suivant", "navigation", "Onglet suivant Chrome", [
        "onglet suivant", "tab suivant", "prochain onglet",
        "onglet a droite",
    ], "hotkey", "ctrl+tab"),
    JarvisCommand("rouvrir_onglet", "navigation", "Rouvrir le dernier onglet ferme", [
        "rouvre l'onglet", "rouvrir onglet", "restaure l'onglet",
        "onglet ferme", "ctrl shift t",
    ], "hotkey", "ctrl+shift+t"),
    JarvisCommand("deconnexion_windows", "systeme", "Deconnexion de la session Windows", [
        "deconnecte moi", "deconnexion", "log out", "logout",
        "ferme la session",
    ], "powershell", "shutdown /l", confirm=True),
    JarvisCommand("hibernation", "systeme", "Mettre en hibernation", [
        "hiberne", "hibernation", "mise en hibernation",
        "hibernate", "veille prolongee",
    ], "powershell", "shutdown /h", confirm=True),
    JarvisCommand("planifier_arret", "systeme", "Planifier un arret dans X minutes", [
        "eteins dans {minutes} minutes", "arret dans {minutes} minutes",
        "programme l'arret dans {minutes}", "shutdown dans {minutes}",
    ], "powershell", "shutdown /s /t ([int]'{minutes}' * 60); \"Arret programme dans {minutes} min\"", ["minutes"]),
    JarvisCommand("annuler_arret", "systeme", "Annuler un arret programme", [
        "annule l'arret", "annuler shutdown", "cancel shutdown",
        "arrete le compte a rebours", "annule l'extinction",
    ], "powershell", "shutdown /a; 'Arret programme annule'"),
    JarvisCommand("heure_actuelle", "systeme", "Donner l'heure actuelle", [
        "quelle heure est-il", "quelle heure", "l'heure",
        "donne moi l'heure", "heure actuelle",
    ], "powershell", "Get-Date -Format 'dddd dd MMMM yyyy HH:mm:ss'"),
    JarvisCommand("date_actuelle", "systeme", "Donner la date actuelle", [
        "quelle date", "quel jour on est", "on est quel jour",
        "la date", "date actuelle", "aujourd'hui",
    ], "powershell", "Get-Date -Format 'dddd dd MMMM yyyy'"),
    JarvisCommand("ecran_externe_etendre", "systeme", "Etendre sur ecran externe", [
        "etends l'ecran", "ecran etendu", "mode etendu",
        "extend display", "deux ecrans",
    ], "powershell", "displayswitch.exe /extend"),
    JarvisCommand("ecran_duplique", "systeme", "Dupliquer l'ecran", [
        "duplique l'ecran", "ecran duplique", "mode duplique",
        "clone l'ecran", "meme image deux ecrans",
    ], "powershell", "displayswitch.exe /clone"),
    JarvisCommand("ecran_interne_seul", "systeme", "Ecran interne uniquement", [
        "ecran principal seulement", "ecran interne seul",
        "desactive l'ecran externe", "un seul ecran",
    ], "powershell", "displayswitch.exe /internal"),
    JarvisCommand("ecran_externe_seul", "systeme", "Ecran externe uniquement", [
        "ecran externe seulement", "ecran externe seul",
        "desactive l'ecran principal", "second ecran seul",
    ], "powershell", "displayswitch.exe /external"),
    JarvisCommand("texte_majuscule", "saisie", "Convertir le presse-papier en majuscules", [
        "en majuscules", "tout en majuscules", "texte en majuscules",
        "uppercase", "caps",
    ], "powershell", "$t = Get-Clipboard; Set-Clipboard ($t.ToUpper()); 'Texte converti en majuscules'"),
    JarvisCommand("texte_minuscule", "saisie", "Convertir le presse-papier en minuscules", [
        "en minuscules", "tout en minuscules", "texte en minuscules",
        "lowercase",
    ], "powershell", "$t = Get-Clipboard; Set-Clipboard ($t.ToLower()); 'Texte converti en minuscules'"),

    # ── Vague 11: Hardware / Memoire / CPU / Batterie / Temperatures ──
    JarvisCommand("ram_usage", "systeme", "Utilisation de la RAM", [
        "utilisation ram", "combien de ram", "memoire utilisee",
        "ram disponible", "etat de la ram",
    ], "powershell", "$os = Get-CimInstance Win32_OperatingSystem; $total = [math]::Round($os.TotalVisibleMemorySize/1MB,1); $free = [math]::Round($os.FreePhysicalMemory/1MB,1); $used = $total - $free; \"RAM: $used/$total GB utilise ($free GB libre)\""),
    JarvisCommand("cpu_usage", "systeme", "Utilisation du processeur", [
        "utilisation cpu", "charge du processeur", "combien de cpu",
        "cpu utilise", "etat du processeur",
    ], "powershell", "$cpu = (Get-CimInstance Win32_Processor).LoadPercentage; \"CPU: $cpu% utilise\""),
    JarvisCommand("cpu_info", "systeme", "Informations sur le processeur", [
        "quel processeur", "info cpu", "nom du processeur",
        "details cpu", "specs processeur",
    ], "powershell", "Get-CimInstance Win32_Processor | Select Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed | Out-String"),
    JarvisCommand("ram_info", "systeme", "Informations detaillees sur la RAM", [
        "info ram", "details ram", "combien de barrettes",
        "specs ram", "type de ram",
    ], "powershell", "Get-CimInstance Win32_PhysicalMemory | Select Manufacturer, Capacity, Speed, MemoryType | Out-String"),
    JarvisCommand("batterie_niveau", "systeme", "Niveau de batterie", [
        "niveau de batterie", "combien de batterie", "batterie restante",
        "pourcentage batterie", "etat batterie",
    ], "powershell", "$b = Get-CimInstance Win32_Battery; if ($b) { \"Batterie: $($b.EstimatedChargeRemaining)% - $($b.BatteryStatus)\" } else { 'Pas de batterie detectee (PC fixe)' }"),
    JarvisCommand("disque_sante", "systeme", "Sante des disques (SMART)", [
        "sante des disques", "etat des disques", "smart disque",
        "sante ssd", "sante hdd",
    ], "powershell", "Get-PhysicalDisk | Select FriendlyName, MediaType, HealthStatus, Size | Out-String"),
    JarvisCommand("carte_mere", "systeme", "Informations carte mere", [
        "info carte mere", "quelle carte mere", "modele carte mere",
        "motherboard", "specs carte mere",
    ], "powershell", "Get-CimInstance Win32_BaseBoard | Select Manufacturer, Product, SerialNumber | Out-String"),
    JarvisCommand("bios_info", "systeme", "Informations BIOS", [
        "info bios", "version bios", "quel bios",
        "details bios", "bios version",
    ], "powershell", "Get-CimInstance Win32_BIOS | Select Manufacturer, SMBIOSBIOSVersion, ReleaseDate | Out-String"),
    JarvisCommand("top_ram", "systeme", "Top 10 processus par RAM", [
        "quoi consomme la ram", "top ram", "processus gourmands ram",
        "qui mange la ram", "plus gros en memoire",
    ], "powershell", "Get-Process | Sort WorkingSet64 -Descending | Select -First 10 Name, @{N='RAM(MB)';E={[math]::Round($_.WorkingSet64/1MB,0)}} | Out-String"),
    JarvisCommand("top_cpu", "systeme", "Top 10 processus par CPU", [
        "quoi consomme le cpu", "top cpu", "processus gourmands cpu",
        "qui mange le cpu", "plus gros en cpu",
    ], "powershell", "Get-Process | Sort CPU -Descending | Select -First 10 Name, @{N='CPU(s)';E={[math]::Round($_.CPU,1)}} | Out-String"),
    JarvisCommand("carte_graphique", "systeme", "Informations carte graphique", [
        "quelle carte graphique", "info gpu detaille", "specs gpu",
        "details carte graphique", "nom de la carte graphique",
    ], "powershell", "Get-CimInstance Win32_VideoController | Select Name, DriverVersion, AdapterRAM, VideoProcessor | Out-String"),
    JarvisCommand("espace_dossier", "fichiers", "Taille d'un dossier", [
        "taille du dossier {dossier}", "combien pese {dossier}",
        "espace utilise par {dossier}", "poids du dossier {dossier}",
    ], "powershell", "$s = (Get-ChildItem '{dossier}' -Recurse -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1GB; \"Taille: $([math]::Round($s,2)) GB\"", ["dossier"]),
    JarvisCommand("nombre_fichiers", "fichiers", "Compter les fichiers dans un dossier", [
        "combien de fichiers dans {dossier}", "nombre de fichiers {dossier}",
        "compte les fichiers dans {dossier}",
    ], "powershell", "$n = (Get-ChildItem '{dossier}' -Recurse -File -ErrorAction SilentlyContinue).Count; \"$n fichiers dans {dossier}\"", ["dossier"]),
    JarvisCommand("windows_version", "systeme", "Version exacte de Windows", [
        "version de windows", "quelle version windows",
        "build windows", "windows version", "quel windows",
    ], "powershell", "[System.Environment]::OSVersion.VersionString + ' - Build ' + (Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion').DisplayVersion"),

    # ── Vague 12: Chrome avance / Fenetres / Accessibilite etendue ──
    JarvisCommand("chrome_favoris", "navigation", "Ouvrir les favoris Chrome", [
        "ouvre les favoris", "mes favoris", "bookmarks",
        "affiche les favoris", "gestionnaire de favoris",
    ], "hotkey", "ctrl+shift+o"),
    JarvisCommand("chrome_telechargements", "navigation", "Ouvrir les telechargements Chrome", [
        "telechargements chrome", "mes telechargements chrome",
        "fichiers telecharges", "downloads chrome",
    ], "hotkey", "ctrl+j"),
    JarvisCommand("chrome_plein_ecran", "navigation", "Chrome en plein ecran (F11)", [
        "plein ecran", "chrome plein ecran", "fullscreen",
        "mode plein ecran", "f11",
    ], "hotkey", "f11"),
    JarvisCommand("chrome_zoom_plus", "navigation", "Zoom avant Chrome", [
        "zoom avant chrome", "agrandir la page", "plus grand",
        "zoom plus", "ctrl plus",
    ], "hotkey", "ctrl+plus"),
    JarvisCommand("chrome_zoom_moins", "navigation", "Zoom arriere Chrome", [
        "zoom arriere chrome", "reduire la page", "plus petit",
        "zoom moins", "ctrl moins",
    ], "hotkey", "ctrl+minus"),
    JarvisCommand("chrome_zoom_reset", "navigation", "Reinitialiser le zoom Chrome", [
        "zoom normal", "zoom 100", "reinitialise le zoom",
        "taille normale", "ctrl zero",
    ], "hotkey", "ctrl+0"),
    JarvisCommand("fenetre_haut_gauche", "fenetre", "Fenetre en haut a gauche", [
        "fenetre en haut a gauche", "snap haut gauche",
        "coin haut gauche", "top left",
    ], "powershell", "Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class K { [DllImport(\"user32.dll\")] public static extern void keybd_event(byte vk, byte scan, int flags, int extra); }'; [K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0x25,0,0,0); [K]::keybd_event(0x25,0,2,0); [K]::keybd_event(0x5B,0,2,0); Start-Sleep -Milliseconds 300; [K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0x26,0,0,0); [K]::keybd_event(0x26,0,2,0); [K]::keybd_event(0x5B,0,2,0)"),
    JarvisCommand("fenetre_haut_droite", "fenetre", "Fenetre en haut a droite", [
        "fenetre en haut a droite", "snap haut droite",
        "coin haut droite", "top right",
    ], "powershell", "Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class K { [DllImport(\"user32.dll\")] public static extern void keybd_event(byte vk, byte scan, int flags, int extra); }'; [K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0x27,0,0,0); [K]::keybd_event(0x27,0,2,0); [K]::keybd_event(0x5B,0,2,0); Start-Sleep -Milliseconds 300; [K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0x26,0,0,0); [K]::keybd_event(0x26,0,2,0); [K]::keybd_event(0x5B,0,2,0)"),
    JarvisCommand("fenetre_bas_gauche", "fenetre", "Fenetre en bas a gauche", [
        "fenetre en bas a gauche", "snap bas gauche",
        "coin bas gauche", "bottom left",
    ], "powershell", "Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class K { [DllImport(\"user32.dll\")] public static extern void keybd_event(byte vk, byte scan, int flags, int extra); }'; [K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0x25,0,0,0); [K]::keybd_event(0x25,0,2,0); [K]::keybd_event(0x5B,0,2,0); Start-Sleep -Milliseconds 300; [K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0x28,0,0,0); [K]::keybd_event(0x28,0,2,0); [K]::keybd_event(0x5B,0,2,0)"),
    JarvisCommand("fenetre_bas_droite", "fenetre", "Fenetre en bas a droite", [
        "fenetre en bas a droite", "snap bas droite",
        "coin bas droite", "bottom right",
    ], "powershell", "Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class K { [DllImport(\"user32.dll\")] public static extern void keybd_event(byte vk, byte scan, int flags, int extra); }'; [K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0x27,0,0,0); [K]::keybd_event(0x27,0,2,0); [K]::keybd_event(0x5B,0,2,0); Start-Sleep -Milliseconds 300; [K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0x28,0,0,0); [K]::keybd_event(0x28,0,2,0); [K]::keybd_event(0x5B,0,2,0)"),
    JarvisCommand("taille_texte_grand", "accessibilite", "Agrandir la taille du texte systeme", [
        "texte plus grand", "agrandis le texte", "taille texte grande",
        "texte plus gros", "augmente la taille du texte",
    ], "ms_settings", "ms-settings:easeofaccess-display"),
    JarvisCommand("clavier_virtuel", "accessibilite", "Ouvrir le clavier virtuel", [
        "clavier virtuel", "ouvre le clavier virtuel", "clavier a l'ecran",
        "on screen keyboard", "clavier tactile",
    ], "powershell", "Start-Process osk"),
    JarvisCommand("filtre_couleur", "accessibilite", "Activer/desactiver le filtre de couleur", [
        "filtre de couleur", "active le filtre couleur", "mode daltonien",
        "filtre daltonien", "accessibilite couleur",
    ], "ms_settings", "ms-settings:easeofaccess-colorfilter"),
    JarvisCommand("sous_titres", "accessibilite", "Parametres des sous-titres", [
        "sous-titres", "parametres sous-titres", "active les sous-titres",
        "closed captions", "legende",
    ], "ms_settings", "ms-settings:easeofaccess-closedcaptioning"),

    # ── Vague 13: Reseau avance / DNS / VPN / Partage / Ports ──
    JarvisCommand("dns_changer_google", "systeme", "Changer DNS vers Google (8.8.8.8)", [
        "mets le dns google", "change le dns en google", "dns google",
        "dns 8.8.8.8", "passe sur google dns",
    ], "powershell", "Set-DnsClientServerAddress -InterfaceAlias 'Wi-Fi' -ServerAddresses ('8.8.8.8','8.8.4.4'); 'DNS Google configure'", confirm=True),
    JarvisCommand("dns_changer_cloudflare", "systeme", "Changer DNS vers Cloudflare (1.1.1.1)", [
        "mets le dns cloudflare", "change le dns en cloudflare", "dns cloudflare",
        "dns 1.1.1.1", "passe sur cloudflare",
    ], "powershell", "Set-DnsClientServerAddress -InterfaceAlias 'Wi-Fi' -ServerAddresses ('1.1.1.1','1.0.0.1'); 'DNS Cloudflare configure'", confirm=True),
    JarvisCommand("dns_reset", "systeme", "Remettre le DNS en automatique", [
        "dns automatique", "reset le dns", "dns par defaut",
        "dns auto", "remets le dns normal",
    ], "powershell", "Set-DnsClientServerAddress -InterfaceAlias 'Wi-Fi' -ResetServerAddresses; 'DNS remis en automatique'", confirm=True),
    JarvisCommand("ports_ouverts", "systeme", "Lister les ports ouverts", [
        "ports ouverts", "quels ports sont ouverts", "liste les ports",
        "ports en ecoute", "listening ports",
    ], "powershell", "Get-NetTCPConnection -State Listen | Select LocalPort, OwningProcess, @{N='Process';E={(Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).Name}} | Sort LocalPort | Out-String"),
    JarvisCommand("ip_publique", "systeme", "Obtenir l'IP publique", [
        "mon ip publique", "quelle est mon ip publique", "ip externe",
        "ip internet", "public ip",
    ], "powershell", "(Invoke-WebRequest -Uri 'https://api.ipify.org' -UseBasicParsing).Content"),
    JarvisCommand("partage_reseau", "systeme", "Lister les partages reseau", [
        "partages reseau", "dossiers partages", "quels dossiers sont partages",
        "network shares", "smb shares",
    ], "powershell", "Get-SmbShare | Select Name, Path, Description | Out-String"),
    JarvisCommand("connexions_actives", "systeme", "Connexions reseau actives", [
        "connexions actives", "qui est connecte", "connexions etablies",
        "established connections", "connexions tcp",
    ], "powershell", "Get-NetTCPConnection -State Established | Select RemoteAddress, RemotePort, OwningProcess, @{N='Process';E={(Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).Name}} | Sort RemoteAddress | Out-String"),
    JarvisCommand("vitesse_reseau", "systeme", "Vitesse de la carte reseau", [
        "vitesse reseau", "debit carte reseau", "link speed",
        "vitesse de connexion", "bande passante",
    ], "powershell", "Get-NetAdapter | Where Status -eq Up | Select Name, LinkSpeed, MacAddress | Out-String"),
    JarvisCommand("arp_table", "systeme", "Afficher la table ARP", [
        "table arp", "arp", "appareils sur le reseau",
        "qui est sur le reseau", "appareils connectes",
    ], "powershell", "Get-NetNeighbor | Where State -ne Unreachable | Select IPAddress, LinkLayerAddress, State | Out-String"),
    JarvisCommand("test_port", "systeme", "Tester si un port est ouvert sur une machine", [
        "teste le port {port} sur {host}", "port {port} ouvert sur {host}",
        "check port {port} {host}", "scan port {port} {host}",
    ], "powershell", "Test-NetConnection -ComputerName '{host}' -Port {port} | Select ComputerName, TcpTestSucceeded, RemotePort | Out-String", ["host", "port"]),
    JarvisCommand("route_table", "systeme", "Afficher la table de routage", [
        "table de routage", "routes reseau", "route table",
        "routing table", "affiche les routes",
    ], "powershell", "Get-NetRoute | Where DestinationPrefix -ne '::' | Select DestinationPrefix, NextHop, InterfaceAlias | Out-String"),
    JarvisCommand("nslookup", "systeme", "Resolution DNS d'un domaine", [
        "nslookup {domaine}", "resous {domaine}", "dns de {domaine}",
        "ip de {domaine}", "resolve {domaine}",
    ], "powershell", "Resolve-DnsName '{domaine}' | Select Name, Type, IPAddress | Out-String", ["domaine"]),
    JarvisCommand("certificat_ssl", "systeme", "Verifier le certificat SSL d'un site", [
        "certificat ssl de {site}", "check ssl {site}",
        "verifie le ssl de {site}", "https {site}",
    ], "powershell", "$r = [Net.HttpWebRequest]::Create('https://{site}'); $r.GetResponse() | Out-Null; $c = $r.ServicePoint.Certificate; \"Emetteur: $($c.Issuer)`nExpire: $($c.GetExpirationDateString())\"", ["site"]),

    # ── Vague 14: Fichiers avances / Compression / Hash / Recherche contenu ──
    JarvisCommand("compresser_dossier", "fichiers", "Compresser un dossier en ZIP", [
        "compresse {dossier}", "zip {dossier}", "archive {dossier}",
        "cree un zip de {dossier}", "compresse le dossier {dossier}",
    ], "powershell", "Compress-Archive -Path '{dossier}' -DestinationPath '{dossier}.zip' -Force; 'Archive creee: {dossier}.zip'", ["dossier"]),
    JarvisCommand("decompresser_zip", "fichiers", "Decompresser un fichier ZIP", [
        "decompresse {fichier}", "unzip {fichier}", "extrais {fichier}",
        "dezippe {fichier}", "ouvre l'archive {fichier}",
    ], "powershell", "Expand-Archive -Path '{fichier}' -DestinationPath (Split-Path '{fichier}') -Force; 'Extrait dans: ' + (Split-Path '{fichier}')", ["fichier"]),
    JarvisCommand("hash_fichier", "fichiers", "Calculer le hash SHA256 d'un fichier", [
        "hash de {fichier}", "sha256 de {fichier}", "checksum de {fichier}",
        "verifie l'integrite de {fichier}", "hash {fichier}",
    ], "powershell", "(Get-FileHash '{fichier}' -Algorithm SHA256).Hash", ["fichier"]),
    JarvisCommand("chercher_contenu", "fichiers", "Chercher du texte dans les fichiers", [
        "cherche {texte} dans les fichiers", "grep {texte}",
        "trouve {texte} dans les fichiers", "recherche {texte} dans le code",
    ], "powershell", "Get-ChildItem -Recurse -File -ErrorAction SilentlyContinue | Select-String -Pattern '{texte}' -List | Select Path, LineNumber | Select -First 20 | Out-String", ["texte"]),
    JarvisCommand("derniers_fichiers", "fichiers", "Derniers fichiers modifies", [
        "derniers fichiers modifies", "fichiers recents", "quoi de nouveau",
        "derniers changements", "fichiers changes recemment",
    ], "powershell", "Get-ChildItem -Recurse -File -ErrorAction SilentlyContinue | Sort LastWriteTime -Descending | Select -First 15 Name, LastWriteTime, @{N='Size(KB)';E={[math]::Round($_.Length/1KB,1)}} | Out-String"),
    JarvisCommand("doublons_fichiers", "fichiers", "Trouver les fichiers en double", [
        "fichiers en double", "doublons", "trouve les doublons",
        "fichiers dupliques", "duplicates",
    ], "powershell", "Get-ChildItem -Recurse -File -ErrorAction SilentlyContinue | Group-Object Length | Where Count -gt 1 | ForEach-Object { $_.Group | Select Name, Length, DirectoryName } | Select -First 20 | Out-String"),
    JarvisCommand("gros_fichiers", "fichiers", "Trouver les plus gros fichiers", [
        "plus gros fichiers", "fichiers les plus lourds", "gros fichiers",
        "quoi prend de la place", "fichiers volumineux",
    ], "powershell", "Get-ChildItem -Recurse -File -ErrorAction SilentlyContinue | Sort Length -Descending | Select -First 20 Name, @{N='Size(MB)';E={[math]::Round($_.Length/1MB,1)}}, DirectoryName | Out-String"),
    JarvisCommand("fichiers_type", "fichiers", "Lister les fichiers d'un type", [
        "fichiers {ext}", "tous les {ext}", "liste les {ext}",
        "trouve les fichiers {ext}", "combien de {ext}",
    ], "powershell", "$f = Get-ChildItem -Recurse -Filter '*.{ext}' -File -ErrorAction SilentlyContinue; \"$($f.Count) fichiers .{ext} trouves\"; $f | Select -First 15 Name, @{N='Size(KB)';E={[math]::Round($_.Length/1KB,1)}} | Out-String", ["ext"]),
    JarvisCommand("renommer_masse", "fichiers", "Renommer des fichiers en masse", [
        "renomme les fichiers {ancien} en {nouveau}",
        "remplace {ancien} par {nouveau} dans les noms",
    ], "powershell", "Get-ChildItem -File | Where Name -match '{ancien}' | Rename-Item -NewName { $_.Name -replace '{ancien}','{nouveau}' } -WhatIf | Out-String", ["ancien", "nouveau"]),
    JarvisCommand("dossiers_vides", "fichiers", "Trouver les dossiers vides", [
        "dossiers vides", "repertoires vides", "trouve les dossiers vides",
        "empty folders",
    ], "powershell", "Get-ChildItem -Directory -Recurse -ErrorAction SilentlyContinue | Where { (Get-ChildItem $_.FullName -Force -ErrorAction SilentlyContinue).Count -eq 0 } | Select FullName | Out-String"),
    JarvisCommand("proprietes_fichier", "fichiers", "Proprietes detaillees d'un fichier", [
        "proprietes de {fichier}", "details de {fichier}", "info sur {fichier}",
        "quand a ete cree {fichier}", "taille de {fichier}",
    ], "powershell", "$f = Get-Item '{fichier}'; \"Nom: $($f.Name)`nTaille: $([math]::Round($f.Length/1KB,1)) KB`nCree: $($f.CreationTime)`nModifie: $($f.LastWriteTime)`nType: $($f.Extension)\"", ["fichier"]),
    JarvisCommand("copier_fichier", "fichiers", "Copier un fichier vers un dossier", [
        "copie {source} dans {destination}", "copie {source} vers {destination}",
        "duplique {source} dans {destination}",
    ], "powershell", "Copy-Item '{source}' '{destination}' -Force; 'Copie effectuee'", ["source", "destination"]),
    JarvisCommand("deplacer_fichier", "fichiers", "Deplacer un fichier", [
        "deplace {source} dans {destination}", "deplace {source} vers {destination}",
        "bouge {source} dans {destination}",
    ], "powershell", "Move-Item '{source}' '{destination}' -Force; 'Deplacement effectue'", ["source", "destination"]),

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
    JarvisCommand("signaux_trading", "trading", "Signaux de trading en attente", [
        "signaux en attente", "quels signaux", "signaux trading",
        "liste les signaux", "signaux",
    ], "jarvis_tool", "trading_pending_signals"),
    JarvisCommand("positions_trading", "trading", "Positions de trading ouvertes", [
        "mes positions", "positions ouvertes", "quelles positions",
        "positions trading", "positions",
    ], "jarvis_tool", "trading_positions"),
    JarvisCommand("statut_trading", "trading", "Statut global du trading", [
        "statut trading", "etat du trading", "status trading",
        "comment va le trading", "trading status",
    ], "jarvis_tool", "trading_status"),
    JarvisCommand("executer_signal", "trading", "Executer un signal de trading", [
        "execute le signal {id}", "lance le signal {id}",
        "trade le signal {id}", "execute signal {id}",
    ], "jarvis_tool", "trading_execute_signal:{id}", ["id"], confirm=True),

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
    # Brain / Apprentissage
    JarvisCommand("jarvis_brain_status", "jarvis", "Etat du cerveau JARVIS", [
        "etat du cerveau", "brain status", "cerveau jarvis",
        "comment va ton cerveau", "apprentissage status",
    ], "jarvis_tool", "brain_status"),
    JarvisCommand("jarvis_brain_learn", "jarvis", "Apprendre de nouveaux patterns", [
        "apprends", "brain learn", "auto apprends",
        "apprends de mes actions", "detecte des patterns",
    ], "jarvis_tool", "brain_learn"),
    JarvisCommand("jarvis_brain_suggest", "jarvis", "Demander une suggestion de skill a l'IA", [
        "suggere un skill", "brain suggest", "invente un skill",
        "cree un nouveau skill", "propose un pipeline",
    ], "jarvis_tool", "brain_suggest"),
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
    "diskord": "discord",
    "discorde": "discord",
    "disscord": "discord",
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
    # Parametres / Settings
    "paramaitre": "parametres",
    "parametre": "parametres",
    "paramaître": "parametres",
    "reglage": "reglages",
    "raglage": "reglages",
    # Bluetooth
    "bleutous": "bluetooth",
    "bleutouss": "bluetooth",
    "bluethooth": "bluetooth",
    "bloutousse": "bluetooth",
    "blue tooth": "bluetooth",
    # Emojis / Widgets
    "emogi": "emojis",
    "emojie": "emojis",
    "widjet": "widgets",
    "vidjette": "widgets",
    # Luminosite
    "lumineausite": "luminosite",
    "luminausite": "luminosite",
    # Notifications
    "notificassion": "notifications",
    "notificasion": "notifications",
    # Services
    "servicee": "service",
    "servisse": "service",
    # Stockage / Resolution
    "stoquage": "stockage",
    "resolussion": "resolution",
    "rezolution": "resolution",
    # Explorateur
    "explorrateur": "explorateur",
    "eksplorateur": "explorateur",
    # Presse-papier
    "presse papier": "presse-papier",
    "pressepapier": "presse-papier",
    # Bureau virtuel
    "burot": "bureau",
    "buro": "bureau",
    # Vague 3 — Accessibilite
    "louppe": "loupe",
    "narateur": "narrateur",
    "narrateure": "narrateur",
    "clavie": "clavier",
    "dictee vocale": "dictee vocale",
    "contrast": "contraste",
    "accessibilitee": "accessibilite",
    "accessiblite": "accessibilite",
    # Vague 3 — Game Bar / Snap
    "gambar": "game bar",
    "game barre": "game bar",
    "snappe": "snap",
    "snape": "snap",
    # Vague 3 — Performance / Energie
    "performanse": "performance",
    "performence": "performance",
    "equilibree": "equilibre",
    "economee": "economie",
    "economi": "economie",
    # Vague 3 — Reseau avance
    "ip config": "ipconfig",
    "denes": "dns",
    "proxie": "proxy",
    "procksy": "proxy",
    "incognitau": "incognito",
    "incognitto": "incognito",
    # Vague 3 — Chrome
    "historike": "historique",
    "favouris": "favoris",
    "favori": "favoris",
    "boucmarque": "bookmarks",
    # Vague 4 — Multi-ecran / Focus / Taskbar
    "etends": "etends",
    "dupliqe": "duplique",
    "taskbarre": "taskbar",
    "barre de tache": "barre des taches",
    "barre de taches": "barre des taches",
    "nuit light": "night light",
    "naïte laïte": "night light",
    "focusse": "focus",
    "minuteure": "minuteur",
    "chrono": "chronometre",
    "allarm": "alarme",
    "alarrme": "alarme",
    "batterie": "batterie",
    "battri": "batterie",
    "fuso": "fuseau",
    "horaire": "horaire",
    # Vague 5 — Securite / DevTools
    "antivirus": "antivirus",
    "defandeur": "defender",
    "defender": "defender",
    "pare feu": "pare-feu",
    "parefeu": "pare-feu",
    "firewal": "firewall",
    "firevol": "firewall",
    "defragmantation": "defragmentation",
    "defragmantassion": "defragmentation",
    "hotspot": "hotspot",
    "otspoute": "hotspot",
    "hotespote": "hotspot",
    "miracaste": "miracast",
    "mirakast": "miracast",
    "peripherike": "peripheriques",
    "periferiue": "peripheriques",
    "pilotte": "pilotes",
    "driverr": "drivers",
    "confidancialite": "confidentialite",
    "confidentalite": "confidentialite",
    # Vague 6 — Personnalisation
    "walpepper": "wallpaper",
    "walpaper": "wallpaper",
    "fon d'ecran": "fond d'ecran",
    "fond decran": "fond d'ecran",
    "polisse": "polices",
    "fonte": "fonts",
    "imprimentes": "imprimantes",
    "imprimante": "imprimante",
    "regedte": "regedit",
    "rejedi": "regedit",
    "multitasking": "multitache",
    "hdaire": "hdr",
    "dark mods": "dark mode",
    "light mods": "light mode",
    "theme somb": "theme sombre",
    # Vague 7 — Reseau / Systeme avance
    "traceroute": "tracert",
    "traceroutte": "tracert",
    "netstate": "netstat",
    "netestat": "netstat",
    "sandboxe": "sandbox",
    "sandeboks": "sandbox",
    "restaurassion": "restauration",
    "restoracion": "restauration",
    "upttaime": "uptime",
    "temperatur": "temperature",
    "temperatture": "temperature",
    "euthernet": "ethernet",
    "eternet": "ethernet",
    "macadresse": "mac address",
    # Mode avion / Micro / Camera
    "mod avion": "mode avion",
    "mode avillion": "mode avion",
    "mikro": "micro",
    "micro phone": "microphone",
    "kamera": "camera",
    "camerra": "camera",
    # Zoom
    "zoome": "zoom",
    "zooome": "zoom",
    # Imprimer
    "impprime": "imprime",
    "imprimme": "imprime",
    # Actualiser
    "rafraichi": "rafraichis",
    "refraichi": "rafraichis",
    "refrech": "refresh",
    # Reunion
    "reunion": "reunion",
    "reunnion": "reunion",
    "visio": "visio",
    "visioconference": "visioconference",
    # Vague 8 — Docker / Git / Dev / n8n / Jupyter
    "dockerr": "docker",
    "dokeur": "docker",
    "doker": "docker",
    "dok air": "docker",
    "conteneurr": "conteneur",
    "conteneure": "conteneur",
    "contener": "conteneur",
    "imaje docker": "images docker",
    "gite": "git",
    "guitte": "git",
    "guit": "git",
    "git states": "git status",
    "git statu": "git status",
    "git poul": "git pull",
    "git pouche": "git push",
    "pippe": "pip",
    "pippe liste": "pip list",
    "jupiter": "jupyter",
    "jupiterre": "jupyter",
    "jupitter": "jupyter",
    "notebok": "notebook",
    "notebouk": "notebook",
    "n huit n": "n8n",
    "n8 n": "n8n",
    "ennuit n": "n8n",
    "lm studio": "lm studio",
    "lm studiot": "lm studio",
    "wiffi": "wifi",
    "why fi": "wifi",
    "profilz": "profils",
    "profille": "profils",
    # Vague 9 — Apps / Clipboard / Systeme
    "peinte": "paint",
    "painte": "paint",
    "wordpade": "wordpad",
    "worpade": "wordpad",
    "snippinge": "snipping",
    "snipingtool": "snipping tool",
    "obss": "obs",
    "o b s": "obs",
    "vlcc": "vlc",
    "7 zip": "7zip",
    "septzip": "7zip",
    "sept zip": "7zip",
    "clipboarde": "clipboard",
    "clipbord": "clipboard",
    "presse papie": "presse-papier",
    "louppe": "loupe",
    "historike": "historique",
    "plannifie": "planifie",
    "planiffie": "planifie",
    "variablle": "variable",
    "pathe": "path",
    # Vague 10 — Onglets / Session / Ecrans / Texte
    "onglay": "onglet",
    "onglet": "onglet",
    "tabbe": "tab",
    "tabe": "tab",
    "hibernassion": "hibernation",
    "ibernation": "hibernation",
    "deconnexcion": "deconnexion",
    "deconexion": "deconnexion",
    "majuscul": "majuscules",
    "minuscul": "minuscules",
    "uppercas": "uppercase",
    "lowercas": "lowercase",
    "shutdowne": "shutdown",
    "sheutdaoune": "shutdown",
    "ecran externe": "ecran externe",
    "displai": "display",
    # Vague 11 — Hardware / RAM / CPU / Batterie
    "rame": "ram",
    "ramm": "ram",
    "processeure": "processeur",
    "processeurr": "processeur",
    "batterie": "batterie",
    "battri": "batterie",
    "batteri": "batterie",
    "carte maire": "carte mere",
    "carte merre": "carte mere",
    "bioss": "bios",
    "bayoss": "bios",
    "carte grafique": "carte graphique",
    "carte graphik": "carte graphique",
    "gpuu": "gpu",
    "essesdee": "ssd",
    "hardisque": "hdd",
    "smartte": "smart",
    # Vague 12 — Chrome / Fenetres / Accessibilite
    "favoris": "favoris",
    "favori": "favoris",
    "bookmarcks": "bookmarks",
    "boukmarcks": "bookmarks",
    "foulscrine": "fullscreen",
    "plein ecrant": "plein ecran",
    "zoome": "zoom",
    "zomm": "zoom",
    "daltonien": "daltonien",
    "daltonnien": "daltonien",
    "sous titre": "sous-titres",
    "soutitres": "sous-titres",
    "clavier virtuel": "clavier virtuel",
    "clavie virtuel": "clavier virtuel",
    # Vague 13 — Reseau / DNS / Ports / SSL
    "cloudeflare": "cloudflare",
    "cloudflaire": "cloudflare",
    "cloudflere": "cloudflare",
    "dieunesse": "dns",
    "deeness": "dns",
    "d n s": "dns",
    "arp": "arp",
    "arpe": "arp",
    "essaielle": "ssl",
    "certificat": "certificat",
    "certificas": "certificat",
    "nslookupe": "nslookup",
    "n s lookup": "nslookup",
    "routage": "routage",
    "routaje": "routage",
    "portt": "port",
    "ip publique": "ip publique",
    "ip publiq": "ip publique",
    # Vague 14 — Fichiers / Compression / Hash
    "zippe": "zip",
    "zipe": "zip",
    "dezippe": "decompresse",
    "dezipe": "decompresse",
    "hache": "hash",
    "hachage": "hash",
    "sha 256": "sha256",
    "sha256": "sha256",
    "checksom": "checksum",
    "doublon": "doublons",
    "doubllon": "doublons",
    "comprresse": "compresse",
    "kompresse": "compresse",
    "renomme": "renomme",
    "renome": "renomme",
    "propriete": "proprietes",
    "propriaite": "proprietes",
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

    # Apply phrase-level corrections (multi-word only to avoid substring issues)
    for wrong, right in VOICE_CORRECTIONS.items():
        if " " in wrong and wrong in text:
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
                    score = 0.85  # Parameterized match: lower than exact non-param match (0.90)
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
        "media": "Controle Media",
        "fenetre": "Fenetres Windows",
        "clipboard": "Presse-papier & Saisie",
        "systeme": "Systeme Windows",
        "trading": "Trading & IA",
        "jarvis": "Controle JARVIS",
    }
    for cat, cmds in categories.items():
        lines.append(f"\n  {cat_names.get(cat, cat)}:")
        for cmd in cmds:
            trigger_example = cmd.triggers[0]
            lines.append(f"    - {trigger_example} → {cmd.description}")
    return "\n".join(lines)
