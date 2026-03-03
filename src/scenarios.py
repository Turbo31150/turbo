"""JARVIS Scenario Engine — Generate, simulate, and validate voice command scenarios.

Generates realistic usage scenarios, runs them through the command matching pipeline,
and records pass/fail results in the SQL database.
"""

from __future__ import annotations

import json
import logging
import time

logger = logging.getLogger("jarvis.scenarios")

from src.database import (
    init_db, add_scenario, get_all_scenarios, record_validation,
    get_stats, get_validation_report, import_commands_from_code,
    import_skills_from_code, import_corrections_from_code,
)
from src.commands import match_command, correct_voice_text
from src.skills import find_skill


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO DEFINITIONS — Real usage scenarios
# ═══════════════════════════════════════════════════════════════════════════

SCENARIO_TEMPLATES: list[dict] = [
    # ── ROUTINE MATIN ─────────────────────────────────────────────────
    {"name": "reveil_matin_check", "category": "routine", "difficulty": "easy",
     "description": "L'utilisateur se reveille et demande l'etat du systeme",
     "voice_input": "info systeme", "expected": ["info_systeme"],
     "expected_result": "Affiche les infos CPU/RAM/Disque"},
    {"name": "matin_ouvre_chrome", "category": "routine", "difficulty": "easy",
     "description": "Ouvrir le navigateur le matin",
     "voice_input": "ouvre chrome", "expected": ["ouvrir_chrome"],
     "expected_result": "Chrome s'ouvre"},
    {"name": "matin_check_mails", "category": "routine", "difficulty": "easy",
     "description": "Verifier ses emails",
     "voice_input": "ouvre mes mails", "expected": ["ouvrir_gmail"],
     "expected_result": "Gmail s'ouvre dans Chrome"},
    {"name": "matin_youtube", "category": "routine", "difficulty": "easy",
     "description": "Ouvrir YouTube le matin",
     "voice_input": "ouvre youtube", "expected": ["ouvrir_youtube"],
     "expected_result": "YouTube s'ouvre"},
    {"name": "matin_rapport_cluster", "category": "routine", "difficulty": "normal",
     "description": "Verifier l'etat du cluster IA",
     "voice_input": "comment va le cluster", "expected": ["statut_cluster"],
     "expected_result": "Status des 3 machines du cluster"},

    # ── NAVIGATION ────────────────────────────────────────────────────
    {"name": "nav_google_search", "category": "navigation", "difficulty": "easy",
     "description": "Recherche Google vocale",
     "voice_input": "cherche recette de cookies", "expected": ["chercher_google"],
     "expected_result": "Recherche Google lancee"},
    {"name": "nav_youtube_search", "category": "navigation", "difficulty": "normal",
     "description": "Recherche YouTube vocale",
     "voice_input": "youtube tutoriel python", "expected": ["chercher_youtube"],
     "expected_result": "Recherche YouTube lancee"},
    {"name": "nav_site_specifique", "category": "navigation", "difficulty": "normal",
     "description": "Naviguer vers un site specifique",
     "voice_input": "va sur github", "expected": ["ouvrir_github"],
     "expected_result": "GitHub s'ouvre"},
    {"name": "nav_tradingview", "category": "navigation", "difficulty": "easy",
     "description": "Ouvrir TradingView pour les charts",
     "voice_input": "ouvre les charts", "expected": ["ouvrir_tradingview"],
     "expected_result": "TradingView s'ouvre"},
    {"name": "nav_nouvel_onglet", "category": "navigation", "difficulty": "easy",
     "description": "Ouvrir un nouvel onglet",
     "voice_input": "nouvel onglet", "expected": ["nouvel_onglet"],
     "expected_result": "Ctrl+T execute"},
    {"name": "nav_fermer_onglet", "category": "navigation", "difficulty": "easy",
     "description": "Fermer l'onglet actif",
     "voice_input": "ferme l'onglet", "expected": ["fermer_onglet"],
     "expected_result": "Ctrl+W execute"},
    {"name": "nav_incognito", "category": "navigation", "difficulty": "normal",
     "description": "Ouvrir Chrome en mode prive",
     "voice_input": "navigation privee", "expected": ["mode_incognito"],
     "expected_result": "Chrome incognito s'ouvre"},

    # ── APPLICATIONS ──────────────────────────────────────────────────
    {"name": "app_vscode", "category": "app", "difficulty": "easy",
     "description": "Ouvrir VSCode",
     "voice_input": "ouvre vscode", "expected": ["ouvrir_vscode"],
     "expected_result": "VSCode s'ouvre"},
    {"name": "app_terminal", "category": "app", "difficulty": "easy",
     "description": "Ouvrir un terminal",
     "voice_input": "ouvre le terminal", "expected": ["ouvrir_terminal"],
     "expected_result": "Windows Terminal s'ouvre"},
    {"name": "app_discord", "category": "app", "difficulty": "easy",
     "description": "Ouvrir Discord",
     "voice_input": "ouvre discord", "expected": ["ouvrir_discord"],
     "expected_result": "Discord s'ouvre"},
    {"name": "app_spotify", "category": "app", "difficulty": "easy",
     "description": "Lancer Spotify",
     "voice_input": "lance la musique", "expected": ["ouvrir_spotify"],
     "expected_result": "Spotify s'ouvre"},
    {"name": "app_lmstudio", "category": "app", "difficulty": "easy",
     "description": "Ouvrir LM Studio",
     "voice_input": "ouvre lm studio", "expected": ["ouvrir_lmstudio"],
     "expected_result": "LM Studio s'ouvre"},
    {"name": "app_calculatrice", "category": "app", "difficulty": "easy",
     "description": "Ouvrir la calculatrice",
     "voice_input": "calculatrice", "expected": ["ouvrir_calculatrice"],
     "expected_result": "Calculatrice s'ouvre"},
    {"name": "app_task_manager", "category": "app", "difficulty": "easy",
     "description": "Ouvrir le gestionnaire de taches",
     "voice_input": "task manager", "expected": ["ouvrir_task_manager"],
     "expected_result": "Task Manager s'ouvre"},

    # ── MEDIA ─────────────────────────────────────────────────────────
    {"name": "media_pause", "category": "media", "difficulty": "easy",
     "description": "Mettre en pause la musique",
     "voice_input": "pause", "expected": ["media_play_pause"],
     "expected_result": "Media Play/Pause envoye"},
    {"name": "media_next_track", "category": "media", "difficulty": "easy",
     "description": "Passer au morceau suivant",
     "voice_input": "prochain morceau", "expected": ["media_next"],
     "expected_result": "Media Next envoye"},
    {"name": "media_volume_up", "category": "media", "difficulty": "easy",
     "description": "Monter le volume",
     "voice_input": "monte le son", "expected": ["volume_haut"],
     "expected_result": "Volume augmente"},
    {"name": "media_volume_down", "category": "media", "difficulty": "easy",
     "description": "Baisser le volume",
     "voice_input": "baisse le son", "expected": ["volume_bas"],
     "expected_result": "Volume baisse"},
    {"name": "media_mute", "category": "media", "difficulty": "easy",
     "description": "Couper le son",
     "voice_input": "coupe le son", "expected": ["muet"],
     "expected_result": "Son coupe/reactive"},

    # ── FENETRES ──────────────────────────────────────────────────────
    {"name": "win_show_desktop", "category": "fenetre", "difficulty": "easy",
     "description": "Afficher le bureau",
     "voice_input": "montre le bureau", "expected": ["minimiser_tout"],
     "expected_result": "Toutes les fenetres minimisees"},
    {"name": "win_alt_tab", "category": "fenetre", "difficulty": "easy",
     "description": "Changer de fenetre",
     "voice_input": "change de fenetre", "expected": ["alt_tab"],
     "expected_result": "Alt+Tab execute"},
    {"name": "win_close", "category": "fenetre", "difficulty": "easy",
     "description": "Fermer la fenetre active",
     "voice_input": "ferme ca", "expected": ["fermer_fenetre"],
     "expected_result": "Alt+F4 envoye"},
    {"name": "win_maximize", "category": "fenetre", "difficulty": "easy",
     "description": "Maximiser la fenetre",
     "voice_input": "plein ecran", "expected": ["maximiser_fenetre"],
     "expected_result": "Fenetre maximisee"},
    {"name": "win_snap_left", "category": "fenetre", "difficulty": "normal",
     "description": "Snapper la fenetre a gauche",
     "voice_input": "mets a gauche", "expected": ["fenetre_gauche"],
     "expected_result": "Fenetre snappee a gauche"},
    {"name": "win_snap_right", "category": "fenetre", "difficulty": "normal",
     "description": "Snapper la fenetre a droite",
     "voice_input": "mets a droite", "expected": ["fenetre_droite"],
     "expected_result": "Fenetre snappee a droite"},

    # ── CLIPBOARD / SAISIE ────────────────────────────────────────────
    {"name": "clip_copier", "category": "clipboard", "difficulty": "easy",
     "description": "Copier la selection",
     "voice_input": "copie", "expected": ["copier"],
     "expected_result": "Ctrl+C envoye"},
    {"name": "clip_coller", "category": "clipboard", "difficulty": "easy",
     "description": "Coller",
     "voice_input": "colle", "expected": ["coller"],
     "expected_result": "Ctrl+V envoye"},
    {"name": "clip_save", "category": "clipboard", "difficulty": "easy",
     "description": "Sauvegarder le fichier",
     "voice_input": "sauvegarde", "expected": ["sauvegarder"],
     "expected_result": "Ctrl+S envoye"},
    {"name": "clip_undo", "category": "clipboard", "difficulty": "easy",
     "description": "Annuler la derniere action",
     "voice_input": "annule", "expected": ["annuler"],
     "expected_result": "Ctrl+Z envoye"},
    {"name": "clip_select_all", "category": "clipboard", "difficulty": "easy",
     "description": "Selectionner tout",
     "voice_input": "selectionne tout", "expected": ["tout_selectionner"],
     "expected_result": "Ctrl+A envoye"},

    # ── SYSTEME ───────────────────────────────────────────────────────
    {"name": "sys_lock", "category": "systeme", "difficulty": "easy",
     "description": "Verrouiller le PC",
     "voice_input": "verrouille le pc", "expected": ["verrouiller"],
     "expected_result": "PC verrouille"},
    {"name": "sys_screenshot", "category": "systeme", "difficulty": "easy",
     "description": "Faire une capture d'ecran",
     "voice_input": "capture ecran", "expected": ["capture_ecran"],
     "expected_result": "Outil de capture lance"},
    {"name": "sys_gpu_info", "category": "systeme", "difficulty": "normal",
     "description": "Verifier les GPU",
     "voice_input": "info gpu", "expected": ["info_gpu"],
     "expected_result": "Infos GPU affichees"},
    {"name": "sys_network", "category": "systeme", "difficulty": "normal",
     "description": "Verifier le reseau",
     "voice_input": "info reseau", "expected": ["info_reseau"],
     "expected_result": "Infos reseau affichees"},
    {"name": "sys_processes", "category": "systeme", "difficulty": "normal",
     "description": "Lister les processus",
     "voice_input": "liste les processus", "expected": ["processus"],
     "expected_result": "Liste des processus affichee"},
    {"name": "sys_wifi_scan", "category": "systeme", "difficulty": "normal",
     "description": "Scanner les reseaux Wi-Fi",
     "voice_input": "scan wifi", "expected": ["wifi_scan"],
     "expected_result": "Reseaux Wi-Fi listes"},
    {"name": "sys_settings", "category": "systeme", "difficulty": "easy",
     "description": "Ouvrir les parametres Windows",
     "voice_input": "ouvre les parametres", "expected": ["ouvrir_parametres"],
     "expected_result": "Parametres ouverts"},
    {"name": "sys_bluetooth_on", "category": "systeme", "difficulty": "normal",
     "description": "Activer le Bluetooth",
     "voice_input": "active le bluetooth", "expected": ["bluetooth_on"],
     "expected_result": "Bluetooth active"},
    {"name": "sys_night_mode", "category": "systeme", "difficulty": "easy",
     "description": "Activer le mode nuit",
     "voice_input": "mode nuit", "expected": ["mode_nuit"],
     "expected_result": "Mode nuit active"},
    {"name": "sys_virtual_desktop", "category": "systeme", "difficulty": "normal",
     "description": "Ouvrir la vue des taches",
     "voice_input": "vue des taches", "expected": ["vue_taches"],
     "expected_result": "Vue des taches ouverte"},
    {"name": "sys_disk_info", "category": "systeme", "difficulty": "normal",
     "description": "Voir l'espace disque",
     "voice_input": "espace disque", "expected": ["info_disques", "param_stockage"],
     "expected_result": "Espace disque affiche"},
    {"name": "sys_performance_mode", "category": "systeme", "difficulty": "normal",
     "description": "Activer le mode haute performance",
     "voice_input": "mode performance", "expected": ["plan_performance"],
     "expected_result": "Plan haute performance active"},
    {"name": "sys_device_manager", "category": "systeme", "difficulty": "normal",
     "description": "Ouvrir le gestionnaire de peripheriques",
     "voice_input": "gestionnaire de peripheriques", "expected": ["gestionnaire_peripheriques"],
     "expected_result": "Device Manager ouvert"},

    # ── FICHIERS ──────────────────────────────────────────────────────
    {"name": "file_documents", "category": "fichiers", "difficulty": "easy",
     "description": "Ouvrir le dossier Documents",
     "voice_input": "ouvre mes documents", "expected": ["ouvrir_documents"],
     "expected_result": "Dossier Documents ouvert"},
    {"name": "file_downloads", "category": "fichiers", "difficulty": "easy",
     "description": "Ouvrir les telechargements",
     "voice_input": "ouvre les telechargements", "expected": ["ouvrir_telechargements"],
     "expected_result": "Dossier Telechargements ouvert"},
    {"name": "file_explorer", "category": "fichiers", "difficulty": "easy",
     "description": "Ouvrir l'explorateur",
     "voice_input": "ouvre l'explorateur", "expected": ["ouvrir_explorateur"],
     "expected_result": "Explorateur Windows ouvert"},
    {"name": "file_projects", "category": "fichiers", "difficulty": "easy",
     "description": "Ouvrir le dossier projets",
     "voice_input": "ouvre mes projets", "expected": ["ouvrir_projets"],
     "expected_result": "Dossier turbo ouvert"},

    # ── TRADING ───────────────────────────────────────────────────────
    {"name": "trading_scan", "category": "trading", "difficulty": "normal",
     "description": "Scanner le marche",
     "voice_input": "scanne le marche", "expected": ["scanner_marche"],
     "expected_result": "Scanner MEXC lance"},
    {"name": "trading_status", "category": "trading", "difficulty": "normal",
     "description": "Verifier le trading",
     "voice_input": "comment va le trading", "expected": ["statut_trading"],
     "expected_result": "Status trading affiche"},
    {"name": "trading_positions", "category": "trading", "difficulty": "normal",
     "description": "Voir les positions ouvertes",
     "voice_input": "mes positions", "expected": ["positions_trading"],
     "expected_result": "Positions affichees"},
    {"name": "trading_signals", "category": "trading", "difficulty": "normal",
     "description": "Voir les signaux en attente",
     "voice_input": "quels signaux", "expected": ["signaux_trading"],
     "expected_result": "Signaux affiches"},
    {"name": "trading_mexc", "category": "trading", "difficulty": "easy",
     "description": "Ouvrir MEXC",
     "voice_input": "ouvre l'exchange", "expected": ["ouvrir_mexc"],
     "expected_result": "MEXC ouvert dans Chrome"},

    # ── DEV ───────────────────────────────────────────────────────────
    {"name": "dev_git_status", "category": "dev", "difficulty": "normal",
     "description": "Verifier le statut Git",
     "voice_input": "statut git", "expected": ["git_status"],
     "expected_result": "Git status affiche"},
    {"name": "dev_git_log", "category": "dev", "difficulty": "normal",
     "description": "Voir les derniers commits",
     "voice_input": "derniers commits", "expected": ["git_log"],
     "expected_result": "Git log affiche"},
    {"name": "dev_docker_ps", "category": "dev", "difficulty": "normal",
     "description": "Lister les conteneurs Docker",
     "voice_input": "docker ps", "expected": ["docker_ps"],
     "expected_result": "Conteneurs Docker listes"},

    # ── JARVIS CONTROLE ───────────────────────────────────────────────
    {"name": "jarvis_aide", "category": "jarvis", "difficulty": "easy",
     "description": "Demander l'aide JARVIS",
     "voice_input": "que sais tu faire", "expected": ["jarvis_aide"],
     "expected_result": "Liste des commandes affichee"},
    {"name": "jarvis_stop", "category": "jarvis", "difficulty": "easy",
     "description": "Arreter JARVIS",
     "voice_input": "au revoir", "expected": ["jarvis_stop"],
     "expected_result": "JARVIS s'arrete"},
    {"name": "jarvis_suggestions", "category": "jarvis", "difficulty": "normal",
     "description": "Demander des suggestions",
     "voice_input": "que me suggeres tu", "expected": ["jarvis_suggestions"],
     "expected_result": "Suggestions affichees"},

    # ── CORRECTIONS VOCALES (phrases avec fautes STT) ─────────────────
    {"name": "correction_crome", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'crome' au lieu de 'chrome'",
     "voice_input": "ouvre crome", "expected": ["ouvrir_chrome"],
     "expected_result": "Correction phonetique → ouvre chrome"},
    {"name": "correction_gougueule", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'gougueule' au lieu de 'google'",
     "voice_input": "cherche sur gougueule python", "expected": ["chercher_google"],
     "expected_result": "Correction phonetique → cherche sur google"},
    {"name": "correction_bleutous", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'bleutous' au lieu de 'bluetooth'",
     "voice_input": "active le bleutous", "expected": ["bluetooth_on"],
     "expected_result": "Correction phonetique → bluetooth"},
    {"name": "correction_vscode_typo", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'vis code' au lieu de 'vscode'",
     "voice_input": "ouvre vis code", "expected": ["ouvrir_vscode"],
     "expected_result": "Correction → vscode"},
    {"name": "correction_diskord", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'diskord' au lieu de 'discord'",
     "voice_input": "ouvre diskord", "expected": ["ouvrir_discord"],
     "expected_result": "Correction → discord"},

    # ── PIPELINES/SKILLS ──────────────────────────────────────────────
    {"name": "skill_rapport_matin", "category": "pipeline", "difficulty": "normal",
     "description": "Lancer le rapport du matin",
     "voice_input": "rapport du matin", "expected": ["rapport_matin"],
     "expected_result": "Pipeline rapport_matin execute"},
    {"name": "skill_mode_dev", "category": "pipeline", "difficulty": "normal",
     "description": "Passer en mode developpement",
     "voice_input": "mode dev", "expected": ["mode_dev", "mode_developpeur"],
     "expected_result": "Pipeline mode_dev execute"},
    {"name": "skill_mode_gaming", "category": "pipeline", "difficulty": "normal",
     "description": "Passer en mode gaming",
     "voice_input": "mode gaming", "expected": ["mode_gaming"],
     "expected_result": "Pipeline mode_gaming execute"},
    {"name": "skill_mode_focus", "category": "pipeline", "difficulty": "normal",
     "description": "Activer le mode concentration",
     "voice_input": "mode focus", "expected": ["mode_focus"],
     "expected_result": "Pipeline mode_focus execute"},
    {"name": "skill_diagnostic", "category": "pipeline", "difficulty": "normal",
     "description": "Lancer un diagnostic complet",
     "voice_input": "diagnostic complet", "expected": ["diagnostic_complet"],
     "expected_result": "Pipeline diagnostic execute"},
    {"name": "skill_mode_trading", "category": "pipeline", "difficulty": "normal",
     "description": "Passer en mode trading",
     "voice_input": "mode trading", "expected": ["mode_trading"],
     "expected_result": "Pipeline mode_trading execute"},
    {"name": "skill_routine_soir", "category": "pipeline", "difficulty": "normal",
     "description": "Lancer la routine du soir",
     "voice_input": "routine du soir", "expected": ["routine_soir"],
     "expected_result": "Pipeline routine_soir execute"},
    {"name": "skill_mode_musique", "category": "pipeline", "difficulty": "easy",
     "description": "Passer en mode musique",
     "voice_input": "mode musique", "expected": ["mode_musique"],
     "expected_result": "Pipeline mode_musique execute"},

    # ── ACCESSIBILITE ─────────────────────────────────────────────────
    {"name": "access_loupe", "category": "accessibilite", "difficulty": "easy",
     "description": "Activer la loupe",
     "voice_input": "active la loupe", "expected": ["loupe"],
     "expected_result": "Loupe activee"},
    {"name": "access_clavier_visuel", "category": "accessibilite", "difficulty": "easy",
     "description": "Ouvrir le clavier visuel",
     "voice_input": "clavier visuel", "expected": ["clavier_visuel"],
     "expected_result": "Clavier visuel ouvert"},
    {"name": "access_dictee", "category": "accessibilite", "difficulty": "easy",
     "description": "Lancer la dictee vocale",
     "voice_input": "dictee vocale", "expected": ["dictee"],
     "expected_result": "Dictee Windows activee"},

    # ═══════════════════════════════════════════════════════════════════
    # VAGUE 2 — 80+ nouveaux scenarios Windows (couverture gaps)
    # ═══════════════════════════════════════════════════════════════════

    # ── SYSTEME AVANCE (40 scenarios) ────────────────────────────────
    {"name": "sys_cpu_usage", "category": "systeme", "difficulty": "easy",
     "description": "Voir utilisation CPU",
     "voice_input": "utilisation cpu", "expected": ["cpu_usage"],
     "expected_result": "Usage CPU affiche"},
    {"name": "sys_ram_usage", "category": "systeme", "difficulty": "easy",
     "description": "Voir utilisation RAM",
     "voice_input": "utilisation ram", "expected": ["ram_usage"],
     "expected_result": "Usage RAM affiche"},
    {"name": "sys_uptime", "category": "systeme", "difficulty": "easy",
     "description": "Voir depuis combien de temps le PC tourne",
     "voice_input": "uptime", "expected": ["uptime"],
     "expected_result": "Uptime affiche"},
    {"name": "sys_top_cpu", "category": "systeme", "difficulty": "normal",
     "description": "Voir les processus les plus gourmands en CPU",
     "voice_input": "top cpu", "expected": ["top_cpu"],
     "expected_result": "Top processus CPU affiches"},
    {"name": "sys_top_ram", "category": "systeme", "difficulty": "normal",
     "description": "Voir les processus les plus gourmands en RAM",
     "voice_input": "top ram", "expected": ["top_ram"],
     "expected_result": "Top processus RAM affiches"},
    {"name": "sys_eteindre", "category": "systeme", "difficulty": "easy",
     "description": "Eteindre le PC",
     "voice_input": "eteins le pc", "expected": ["eteindre"],
     "expected_result": "Arret programme"},
    {"name": "sys_redemarrer", "category": "systeme", "difficulty": "easy",
     "description": "Redemarrer le PC",
     "voice_input": "redemarre le pc", "expected": ["redemarrer"],
     "expected_result": "Redemarrage lance"},
    {"name": "sys_veille", "category": "systeme", "difficulty": "easy",
     "description": "Mettre en veille",
     "voice_input": "mise en veille", "expected": ["veille"],
     "expected_result": "PC en veille"},
    {"name": "sys_luminosite_haut", "category": "systeme", "difficulty": "easy",
     "description": "Augmenter la luminosite",
     "voice_input": "monte la luminosite", "expected": ["luminosite_haut"],
     "expected_result": "Luminosite augmentee"},
    {"name": "sys_luminosite_bas", "category": "systeme", "difficulty": "easy",
     "description": "Baisser la luminosite",
     "voice_input": "baisse la luminosite", "expected": ["luminosite_bas"],
     "expected_result": "Luminosite baissee"},
    {"name": "sys_mode_sombre", "category": "systeme", "difficulty": "easy",
     "description": "Activer le mode sombre",
     "voice_input": "active le mode sombre", "expected": ["mode_sombre"],
     "expected_result": "Mode sombre active"},
    {"name": "sys_mode_clair", "category": "systeme", "difficulty": "easy",
     "description": "Activer le mode clair",
     "voice_input": "active le mode clair", "expected": ["mode_clair"],
     "expected_result": "Mode clair active"},
    {"name": "sys_wifi_connecter", "category": "systeme", "difficulty": "normal",
     "description": "Connecter au WiFi",
     "voice_input": "connecte moi au wifi maison", "expected": ["wifi_connecter"],
     "expected_result": "WiFi connecte"},
    {"name": "sys_wifi_deconnecter", "category": "systeme", "difficulty": "normal",
     "description": "Deconnecter le WiFi",
     "voice_input": "deconnecte le wifi", "expected": ["wifi_deconnecter"],
     "expected_result": "WiFi deconnecte"},
    {"name": "sys_bluetooth_off", "category": "systeme", "difficulty": "normal",
     "description": "Desactiver le Bluetooth",
     "voice_input": "desactive le bluetooth", "expected": ["bluetooth_off"],
     "expected_result": "Bluetooth desactive"},
    {"name": "sys_mode_avion", "category": "systeme", "difficulty": "easy",
     "description": "Activer le mode avion",
     "voice_input": "mode avion", "expected": ["mode_avion_on"],
     "expected_result": "Mode avion active"},
    {"name": "sys_ipconfig", "category": "systeme", "difficulty": "normal",
     "description": "Voir la configuration IP",
     "voice_input": "ipconfig", "expected": ["ipconfig"],
     "expected_result": "Config IP affichee"},
    {"name": "sys_ping", "category": "systeme", "difficulty": "normal",
     "description": "Ping un hote",
     "voice_input": "ping google", "expected": ["ping_host"],
     "expected_result": "Ping execute"},
    {"name": "sys_ip_publique", "category": "systeme", "difficulty": "normal",
     "description": "Voir l'IP publique",
     "voice_input": "ip externe", "expected": ["ip_publique"],
     "expected_result": "IP publique affichee"},
    {"name": "sys_adresse_mac", "category": "systeme", "difficulty": "normal",
     "description": "Voir l'adresse MAC",
     "voice_input": "adresse mac", "expected": ["adresse_mac"],
     "expected_result": "Adresse MAC affichee"},
    {"name": "sys_dns_google", "category": "systeme", "difficulty": "hard",
     "description": "Changer les DNS vers Google",
     "voice_input": "mets le dns google", "expected": ["dns_changer_google"],
     "expected_result": "DNS Google configures"},
    {"name": "sys_vider_dns", "category": "systeme", "difficulty": "normal",
     "description": "Vider le cache DNS",
     "voice_input": "vide le cache dns", "expected": ["vider_dns"],
     "expected_result": "Cache DNS vide"},
    {"name": "sys_ports_ouverts", "category": "systeme", "difficulty": "normal",
     "description": "Voir les ports ouverts",
     "voice_input": "quels ports sont ouverts", "expected": ["ports_ouverts", "netstat"],
     "expected_result": "Ports ouverts listes"},
    {"name": "sys_connexions_actives", "category": "systeme", "difficulty": "normal",
     "description": "Voir les connexions actives",
     "voice_input": "connexions etablies", "expected": ["connexions_actives", "netstat"],
     "expected_result": "Connexions affichees"},
    {"name": "sys_nettoyage_disque", "category": "systeme", "difficulty": "normal",
     "description": "Nettoyer le disque",
     "voice_input": "nettoyage de disque", "expected": ["nettoyage_disque"],
     "expected_result": "Nettoyage lance"},
    {"name": "sys_vider_corbeille", "category": "systeme", "difficulty": "easy",
     "description": "Vider la corbeille",
     "voice_input": "vide la corbeille", "expected": ["vider_corbeille"],
     "expected_result": "Corbeille videe"},
    {"name": "sys_vider_temp", "category": "systeme", "difficulty": "normal",
     "description": "Vider les fichiers temporaires",
     "voice_input": "vide les fichiers temporaires", "expected": ["vider_temp"],
     "expected_result": "Temp vide"},
    {"name": "sys_nouveau_bureau", "category": "systeme", "difficulty": "normal",
     "description": "Creer un nouveau bureau virtuel",
     "voice_input": "nouveau bureau", "expected": ["nouveau_bureau"],
     "expected_result": "Bureau virtuel cree"},
    {"name": "sys_snap_layout", "category": "systeme", "difficulty": "normal",
     "description": "Ouvrir les snap layouts",
     "voice_input": "snap layout", "expected": ["snap_layout"],
     "expected_result": "Snap layouts ouverts"},
    {"name": "sys_pare_feu", "category": "systeme", "difficulty": "normal",
     "description": "Ouvrir le pare-feu",
     "voice_input": "ouvre le pare-feu", "expected": ["pare_feu"],
     "expected_result": "Pare-feu ouvert"},
    {"name": "sys_windows_security", "category": "systeme", "difficulty": "easy",
     "description": "Ouvrir Windows Security",
     "voice_input": "securite windows", "expected": ["windows_security"],
     "expected_result": "Windows Security ouvert"},
    {"name": "sys_focus_on", "category": "systeme", "difficulty": "normal",
     "description": "Activer le mode focus",
     "voice_input": "ne pas deranger", "expected": ["focus_assist_on"],
     "expected_result": "Focus assist active"},
    {"name": "sys_focus_off", "category": "systeme", "difficulty": "normal",
     "description": "Desactiver le mode focus",
     "voice_input": "reactive les notifications", "expected": ["focus_assist_off"],
     "expected_result": "Focus assist desactive"},
    {"name": "sys_zoom_avant", "category": "systeme", "difficulty": "easy",
     "description": "Zoomer",
     "voice_input": "zoom avant", "expected": ["zoom_avant"],
     "expected_result": "Zoom avant"},
    {"name": "sys_zoom_arriere", "category": "systeme", "difficulty": "easy",
     "description": "Dezoomer",
     "voice_input": "zoom arriere", "expected": ["zoom_arriere"],
     "expected_result": "Zoom arriere"},
    {"name": "sys_planifier_arret", "category": "systeme", "difficulty": "hard",
     "description": "Planifier un arret du PC",
     "voice_input": "eteins dans 30 minutes", "expected": ["planifier_arret"],
     "expected_result": "Arret programme"},
    {"name": "sys_annuler_arret", "category": "systeme", "difficulty": "normal",
     "description": "Annuler l'arret programme",
     "voice_input": "annule l'arret", "expected": ["annuler_arret"],
     "expected_result": "Arret annule"},
    {"name": "sys_date", "category": "systeme", "difficulty": "easy",
     "description": "Voir la date actuelle",
     "voice_input": "quelle date", "expected": ["date_actuelle"],
     "expected_result": "Date affichee"},
    {"name": "sys_heure", "category": "systeme", "difficulty": "easy",
     "description": "Voir l'heure actuelle",
     "voice_input": "quelle heure", "expected": ["heure_actuelle"],
     "expected_result": "Heure affichee"},
    {"name": "sys_programmes_installes", "category": "systeme", "difficulty": "normal",
     "description": "Lister les programmes installes",
     "voice_input": "programmes installes", "expected": ["programmes_installees"],
     "expected_result": "Liste programmes"},

    # ── FICHIERS AVANCE (15 scenarios) ───────────────────────────────
    {"name": "file_images", "category": "fichiers", "difficulty": "easy",
     "description": "Ouvrir le dossier Images",
     "voice_input": "ouvre mes images", "expected": ["ouvrir_images"],
     "expected_result": "Dossier Images ouvert"},
    {"name": "file_musique", "category": "fichiers", "difficulty": "easy",
     "description": "Ouvrir le dossier Musique",
     "voice_input": "ouvre ma musique", "expected": ["ouvrir_musique"],
     "expected_result": "Dossier Musique ouvert"},
    {"name": "file_creer_dossier", "category": "fichiers", "difficulty": "normal",
     "description": "Creer un nouveau dossier",
     "voice_input": "cree un dossier test", "expected": ["creer_dossier"],
     "expected_result": "Dossier cree"},
    {"name": "file_chercher", "category": "fichiers", "difficulty": "normal",
     "description": "Chercher un fichier",
     "voice_input": "recherche fichier config", "expected": ["chercher_fichier", "chercher_google"],
     "expected_result": "Fichier trouve"},
    {"name": "file_lister", "category": "fichiers", "difficulty": "normal",
     "description": "Lister le contenu d'un dossier",
     "voice_input": "liste le dossier documents", "expected": ["lister_dossier"],
     "expected_result": "Contenu liste"},
    {"name": "file_gros_fichiers", "category": "fichiers", "difficulty": "normal",
     "description": "Trouver les gros fichiers",
     "voice_input": "gros fichiers", "expected": ["gros_fichiers"],
     "expected_result": "Gros fichiers listes"},
    {"name": "file_appdata", "category": "fichiers", "difficulty": "normal",
     "description": "Ouvrir AppData",
     "voice_input": "ouvre appdata", "expected": ["ouvrir_appdata"],
     "expected_result": "AppData ouvert"},
    {"name": "file_recents", "category": "fichiers", "difficulty": "easy",
     "description": "Voir les fichiers recents",
     "voice_input": "fichiers recents", "expected": ["ouvrir_recents", "derniers_fichiers"],
     "expected_result": "Fichiers recents affiches"},
    {"name": "file_temp", "category": "fichiers", "difficulty": "normal",
     "description": "Ouvrir le dossier temp",
     "voice_input": "ouvre temp", "expected": ["ouvrir_temp"],
     "expected_result": "Dossier temp ouvert"},
    {"name": "file_espace_dossier", "category": "fichiers", "difficulty": "normal",
     "description": "Voir l'espace d'un dossier",
     "voice_input": "taille du dossier documents", "expected": ["espace_dossier"],
     "expected_result": "Espace calcule"},
    {"name": "file_compresser", "category": "fichiers", "difficulty": "normal",
     "description": "Compresser un dossier",
     "voice_input": "compresse le dossier", "expected": ["compresser_dossier"],
     "expected_result": "Dossier compresse"},
    {"name": "file_hash", "category": "fichiers", "difficulty": "hard",
     "description": "Calculer le hash d'un fichier",
     "voice_input": "hash du fichier", "expected": ["hash_fichier"],
     "expected_result": "Hash calcule"},
    {"name": "file_doublons", "category": "fichiers", "difficulty": "normal",
     "description": "Trouver les fichiers en double",
     "voice_input": "fichiers en double", "expected": ["doublons_fichiers"],
     "expected_result": "Doublons listes"},
    {"name": "file_dossiers_vides", "category": "fichiers", "difficulty": "normal",
     "description": "Trouver les dossiers vides",
     "voice_input": "dossiers vides", "expected": ["dossiers_vides", "trouver_dossiers_vides"],
     "expected_result": "Dossiers vides listes"},
    {"name": "file_nombre", "category": "fichiers", "difficulty": "normal",
     "description": "Compter les fichiers dans un dossier",
     "voice_input": "compte les fichiers dans documents", "expected": ["nombre_fichiers"],
     "expected_result": "Nombre affiche"},

    # ── NAVIGATION AVANCE (10 scenarios) ─────────────────────────────
    {"name": "nav_gmail", "category": "navigation", "difficulty": "easy",
     "description": "Ouvrir Gmail",
     "voice_input": "ouvre gmail", "expected": ["ouvrir_gmail"],
     "expected_result": "Gmail ouvert"},
    {"name": "nav_github", "category": "navigation", "difficulty": "easy",
     "description": "Ouvrir GitHub",
     "voice_input": "ouvre github", "expected": ["ouvrir_github"],
     "expected_result": "GitHub ouvert"},
    {"name": "nav_favoris", "category": "navigation", "difficulty": "easy",
     "description": "Ouvrir les favoris Chrome",
     "voice_input": "ouvre les favoris", "expected": ["chrome_favoris", "favoris_chrome"],
     "expected_result": "Favoris ouverts"},
    {"name": "nav_historique", "category": "navigation", "difficulty": "easy",
     "description": "Voir l'historique Chrome",
     "voice_input": "historique chrome", "expected": ["historique_chrome"],
     "expected_result": "Historique ouvert"},
    {"name": "nav_onglet_suivant", "category": "navigation", "difficulty": "easy",
     "description": "Passer a l'onglet suivant",
     "voice_input": "onglet suivant", "expected": ["onglet_suivant"],
     "expected_result": "Onglet suivant"},
    {"name": "nav_onglet_precedent", "category": "navigation", "difficulty": "easy",
     "description": "Revenir a l'onglet precedent",
     "voice_input": "onglet precedent", "expected": ["onglet_precedent"],
     "expected_result": "Onglet precedent"},
    {"name": "nav_rouvrir_onglet", "category": "navigation", "difficulty": "normal",
     "description": "Rouvrir le dernier onglet ferme",
     "voice_input": "rouvre l'onglet", "expected": ["rouvrir_onglet"],
     "expected_result": "Onglet rouvert"},
    {"name": "nav_plein_ecran", "category": "navigation", "difficulty": "easy",
     "description": "Chrome en plein ecran",
     "voice_input": "chrome plein ecran", "expected": ["chrome_plein_ecran"],
     "expected_result": "Chrome fullscreen"},
    {"name": "nav_zoom_plus", "category": "navigation", "difficulty": "easy",
     "description": "Zoomer dans Chrome",
     "voice_input": "zoom avant chrome", "expected": ["chrome_zoom_plus"],
     "expected_result": "Zoom Chrome augmente"},
    {"name": "nav_zoom_moins", "category": "navigation", "difficulty": "easy",
     "description": "Dezoomer dans Chrome",
     "voice_input": "zoom arriere chrome", "expected": ["chrome_zoom_moins"],
     "expected_result": "Zoom Chrome reduit"},

    # ── APPLICATIONS AVANCE (8 scenarios) ────────────────────────────
    {"name": "app_notepad", "category": "app", "difficulty": "easy",
     "description": "Ouvrir le bloc-notes",
     "voice_input": "ouvre le bloc notes", "expected": ["ouvrir_notepad"],
     "expected_result": "Notepad ouvert"},
    {"name": "app_paint", "category": "app", "difficulty": "easy",
     "description": "Ouvrir Paint",
     "voice_input": "ouvre paint", "expected": ["ouvrir_paint"],
     "expected_result": "Paint ouvert"},
    {"name": "app_vlc", "category": "app", "difficulty": "easy",
     "description": "Ouvrir VLC",
     "voice_input": "ouvre vlc", "expected": ["ouvrir_vlc"],
     "expected_result": "VLC ouvert"},
    {"name": "app_obs", "category": "app", "difficulty": "easy",
     "description": "Ouvrir OBS",
     "voice_input": "ouvre obs", "expected": ["ouvrir_obs"],
     "expected_result": "OBS ouvert"},
    {"name": "app_fermer", "category": "app", "difficulty": "normal",
     "description": "Fermer une application",
     "voice_input": "ferme chrome", "expected": ["fermer_app", "fermer_fenetre"],
     "expected_result": "App fermee"},
    {"name": "app_snipping", "category": "app", "difficulty": "easy",
     "description": "Ouvrir l'outil de capture",
     "voice_input": "outil de capture", "expected": ["ouvrir_snipping"],
     "expected_result": "Snipping tool ouvert"},
    {"name": "app_7zip", "category": "app", "difficulty": "easy",
     "description": "Ouvrir 7-Zip",
     "voice_input": "ouvre 7zip", "expected": ["ouvrir_7zip"],
     "expected_result": "7-Zip ouvert"},
    {"name": "app_wordpad", "category": "app", "difficulty": "easy",
     "description": "Ouvrir WordPad",
     "voice_input": "ouvre wordpad", "expected": ["ouvrir_wordpad"],
     "expected_result": "WordPad ouvert"},

    # ── DEV AVANCE (8 scenarios) ─────────────────────────────────────
    {"name": "dev_git_pull", "category": "dev", "difficulty": "normal",
     "description": "Faire un git pull",
     "voice_input": "git pull", "expected": ["git_pull"],
     "expected_result": "Git pull execute"},
    {"name": "dev_git_push", "category": "dev", "difficulty": "normal",
     "description": "Faire un git push",
     "voice_input": "git push", "expected": ["git_push"],
     "expected_result": "Git push execute"},
    {"name": "dev_docker_images", "category": "dev", "difficulty": "normal",
     "description": "Lister les images Docker",
     "voice_input": "images docker", "expected": ["docker_images"],
     "expected_result": "Images Docker listees"},
    {"name": "dev_docker_stop", "category": "dev", "difficulty": "normal",
     "description": "Arreter tous les conteneurs",
     "voice_input": "arrete tous les conteneurs", "expected": ["docker_stop_all"],
     "expected_result": "Conteneurs arretes"},
    {"name": "dev_python_version", "category": "dev", "difficulty": "easy",
     "description": "Voir la version Python",
     "voice_input": "version python", "expected": ["python_version"],
     "expected_result": "Version Python affichee"},
    {"name": "dev_pip_list", "category": "dev", "difficulty": "normal",
     "description": "Lister les packages pip",
     "voice_input": "pip list", "expected": ["pip_list"],
     "expected_result": "Packages listes"},
    {"name": "dev_jupyter", "category": "dev", "difficulty": "easy",
     "description": "Ouvrir Jupyter",
     "voice_input": "ouvre jupyter", "expected": ["ouvrir_jupyter"],
     "expected_result": "Jupyter ouvert"},
    {"name": "dev_n8n", "category": "dev", "difficulty": "easy",
     "description": "Ouvrir n8n",
     "voice_input": "ouvre n8n", "expected": ["ouvrir_n8n"],
     "expected_result": "n8n ouvert"},

    # ── FENETRE AVANCE (5 scenarios) ─────────────────────────────────
    {"name": "win_minimize", "category": "fenetre", "difficulty": "easy",
     "description": "Minimiser la fenetre",
     "voice_input": "minimise", "expected": ["minimiser_fenetre"],
     "expected_result": "Fenetre minimisee"},
    {"name": "win_focus", "category": "fenetre", "difficulty": "normal",
     "description": "Focus sur une fenetre",
     "voice_input": "focus sur chrome", "expected": ["focus_fenetre"],
     "expected_result": "Chrome au premier plan"},
    {"name": "win_liste", "category": "fenetre", "difficulty": "normal",
     "description": "Lister les fenetres ouvertes",
     "voice_input": "liste les fenetres", "expected": ["liste_fenetres"],
     "expected_result": "Fenetres listees"},
    {"name": "win_snap_haut_gauche", "category": "fenetre", "difficulty": "normal",
     "description": "Snapper en haut a gauche",
     "voice_input": "fenetre en haut a gauche", "expected": ["fenetre_haut_gauche"],
     "expected_result": "Fenetre en quart haut-gauche"},
    {"name": "win_snap_bas_droite", "category": "fenetre", "difficulty": "normal",
     "description": "Snapper en bas a droite",
     "voice_input": "fenetre en bas a droite", "expected": ["fenetre_bas_droite"],
     "expected_result": "Fenetre en quart bas-droite"},

    # ── CLIPBOARD AVANCE (5 scenarios) ───────────────────────────────
    {"name": "clip_couper", "category": "clipboard", "difficulty": "easy",
     "description": "Couper la selection",
     "voice_input": "coupe", "expected": ["couper"],
     "expected_result": "Ctrl+X envoye"},
    {"name": "clip_refaire", "category": "clipboard", "difficulty": "easy",
     "description": "Refaire l'action annulee",
     "voice_input": "refais", "expected": ["refaire"],
     "expected_result": "Ctrl+Y envoye"},
    {"name": "clip_recherche", "category": "clipboard", "difficulty": "easy",
     "description": "Rechercher dans la page",
     "voice_input": "recherche dans la page", "expected": ["recherche_page"],
     "expected_result": "Ctrl+F ouvert"},
    {"name": "clip_lire_clipboard", "category": "clipboard", "difficulty": "normal",
     "description": "Lire le contenu du presse-papier",
     "voice_input": "lis le presse papier", "expected": ["lire_presse_papier"],
     "expected_result": "Contenu clipboard affiche"},
    {"name": "clip_ecrire_texte", "category": "clipboard", "difficulty": "normal",
     "description": "Ecrire du texte",
     "voice_input": "ecris bonjour", "expected": ["ecrire_texte"],
     "expected_result": "Texte saisi"},

    # ── MEDIA AVANCE (2 scenarios) ───────────────────────────────────
    {"name": "media_previous_track", "category": "media", "difficulty": "easy",
     "description": "Revenir au morceau precedent",
     "voice_input": "morceau precedent", "expected": ["media_previous"],
     "expected_result": "Media Previous envoye"},
    {"name": "media_volume_precis", "category": "media", "difficulty": "normal",
     "description": "Mettre le volume a un niveau precis",
     "voice_input": "volume a 50", "expected": ["volume_precis"],
     "expected_result": "Volume regle a 50%"},

    # ── CORRECTIONS VOCALES AVANCE (5 scenarios) ─────────────────────
    {"name": "correction_youtoube", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'youtoube' au lieu de 'youtube'",
     "voice_input": "ouvre youtoube", "expected": ["ouvrir_youtube", "aller_sur_site"],
     "expected_result": "Correction phonetique youtube"},
    {"name": "correction_spottifaille", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'spottifaille' au lieu de 'spotify'",
     "voice_input": "ouvre spottifaille", "expected": ["ouvrir_spotify", "ouvrir_app"],
     "expected_result": "Correction phonetique spotify"},
    {"name": "correction_termenal", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'termenal' au lieu de 'terminal'",
     "voice_input": "ouvre le termenal", "expected": ["ouvrir_terminal", "aller_sur_site"],
     "expected_result": "Correction phonetique terminal"},
    {"name": "correction_dockeur", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'dockeur' au lieu de 'docker'",
     "voice_input": "liste les conteneurs dockeur", "expected": ["docker_ps"],
     "expected_result": "Correction phonetique docker"},
    {"name": "correction_git_statut", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'gite statut' au lieu de 'git status'",
     "voice_input": "statut gite", "expected": ["git_status"],
     "expected_result": "Correction phonetique git"},

    # ── PIPELINES AVANCE (8 scenarios) ───────────────────────────────
    {"name": "skill_mode_presentation", "category": "pipeline", "difficulty": "normal",
     "description": "Passer en mode presentation",
     "voice_input": "mode presentation", "expected": ["mode_presentation"],
     "expected_result": "Pipeline mode_presentation execute"},
    {"name": "skill_mode_stream", "category": "pipeline", "difficulty": "normal",
     "description": "Passer en mode stream",
     "voice_input": "mode stream", "expected": ["mode_stream"],
     "expected_result": "Pipeline mode_stream execute"},
    {"name": "skill_mode_cinema", "category": "pipeline", "difficulty": "normal",
     "description": "Passer en mode cinema",
     "voice_input": "mode cinema", "expected": ["mode_cinema"],
     "expected_result": "Pipeline mode_cinema execute"},
    {"name": "skill_cleanup_ram", "category": "pipeline", "difficulty": "normal",
     "description": "Nettoyer la RAM",
     "voice_input": "nettoie la ram", "expected": ["cleanup_ram"],
     "expected_result": "Pipeline cleanup_ram execute"},
    {"name": "skill_mode_reunion", "category": "pipeline", "difficulty": "normal",
     "description": "Passer en mode reunion",
     "voice_input": "mode reunion", "expected": ["mode_reunion"],
     "expected_result": "Pipeline mode_reunion execute"},
    {"name": "skill_backup_rapide", "category": "pipeline", "difficulty": "normal",
     "description": "Faire un backup rapide",
     "voice_input": "backup rapide", "expected": ["backup_rapide"],
     "expected_result": "Pipeline backup_rapide execute"},
    {"name": "skill_mode_lecture", "category": "pipeline", "difficulty": "normal",
     "description": "Passer en mode lecture",
     "voice_input": "mode lecture", "expected": ["mode_lecture"],
     "expected_result": "Pipeline mode_lecture execute"},
    {"name": "skill_routine_soir_bis", "category": "pipeline", "difficulty": "normal",
     "description": "Routine du soir avec formulation alternative",
     "voice_input": "je vais dormir", "expected": ["routine_soir"],
     "expected_result": "Pipeline routine_soir execute"},

    # ── TRADING AVANCE (3 scenarios) ─────────────────────────────────
    {"name": "trading_breakout", "category": "trading", "difficulty": "hard",
     "description": "Detecter les breakouts",
     "voice_input": "detecte les breakouts", "expected": ["detecter_breakout"],
     "expected_result": "Breakouts detectes"},
    {"name": "trading_sniper", "category": "trading", "difficulty": "hard",
     "description": "Lancer le sniper breakout",
     "voice_input": "sniper breakout", "expected": ["sniper_breakout"],
     "expected_result": "Sniper lance"},
    {"name": "trading_consensus", "category": "trading", "difficulty": "normal",
     "description": "Lancer le consensus IA",
     "voice_input": "consensus ia", "expected": ["consensus_ia", "consensus_trading"],
     "expected_result": "Consensus IA lance"},

    # ── JARVIS AVANCE (3 scenarios) ──────────────────────────────────
    {"name": "jarvis_skills_list", "category": "jarvis", "difficulty": "easy",
     "description": "Lister les skills JARVIS",
     "voice_input": "liste les skills", "expected": ["jarvis_skills"],
     "expected_result": "Skills listes"},
    {"name": "jarvis_projets", "category": "jarvis", "difficulty": "easy",
     "description": "Voir les projets JARVIS",
     "voice_input": "liste les projets", "expected": ["jarvis_projets"],
     "expected_result": "Projets affiches"},
    {"name": "jarvis_repete", "category": "jarvis", "difficulty": "easy",
     "description": "Repeter la derniere commande",
     "voice_input": "repete", "expected": ["jarvis_repete"],
     "expected_result": "Derniere commande repetee"},

    # ═══════════════════════════════════════════════════════════════════
    # VAGUE 15 — Widgets, Store, Explorer, Phone Link, Clipboard cloud
    # ═══════════════════════════════════════════════════════════════════

    # ── SYSTEME VAGUE 15 ─────────────────────────────────────────────
    {"name": "sys_widgets", "category": "systeme", "difficulty": "easy",
     "description": "Ouvrir les widgets Windows",
     "voice_input": "ouvre les widgets", "expected": ["ouvrir_widgets"],
     "expected_result": "Panneau widgets ouvert"},
    {"name": "sys_game_bar", "category": "systeme", "difficulty": "easy",
     "description": "Ouvrir la Game Bar",
     "voice_input": "ouvre la game bar", "expected": ["game_bar"],
     "expected_result": "Game Bar ouverte"},
    {"name": "sys_screen_record", "category": "systeme", "difficulty": "normal",
     "description": "Enregistrer l'ecran",
     "voice_input": "enregistre l'ecran", "expected": ["screen_recording", "enregistrer_ecran"],
     "expected_result": "Enregistrement lance"},
    {"name": "sys_partage_proximite", "category": "systeme", "difficulty": "normal",
     "description": "Activer le partage de proximite",
     "voice_input": "active le partage de proximite", "expected": ["partage_proximite_on"],
     "expected_result": "Partage proximite ouvert"},
    {"name": "sys_params_notifs", "category": "systeme", "difficulty": "easy",
     "description": "Gerer les notifications",
     "voice_input": "parametres notifications", "expected": ["parametres_notifications"],
     "expected_result": "Settings notifications ouvert"},
    {"name": "sys_apps_defaut", "category": "systeme", "difficulty": "easy",
     "description": "Apps par defaut",
     "voice_input": "apps par defaut", "expected": ["parametres_apps_defaut", "apps_par_defaut"],
     "expected_result": "Settings apps defaut"},
    {"name": "sys_about_pc", "category": "systeme", "difficulty": "easy",
     "description": "A propos du PC",
     "voice_input": "a propos du pc", "expected": ["parametres_about", "a_propos_pc"],
     "expected_result": "Infos PC affichees"},
    {"name": "sys_sante_disque", "category": "systeme", "difficulty": "normal",
     "description": "Verifier la sante du SSD",
     "voice_input": "sante des disques", "expected": ["verifier_sante_disque", "disque_sante", "disk_sante"],
     "expected_result": "Etat SMART affiche"},
    {"name": "sys_speed_test", "category": "systeme", "difficulty": "normal",
     "description": "Tester la vitesse internet",
     "voice_input": "test de vitesse", "expected": ["vitesse_internet"],
     "expected_result": "Latence affichee"},
    {"name": "sys_historique_updates", "category": "systeme", "difficulty": "normal",
     "description": "Voir les dernieres mises a jour",
     "voice_input": "dernieres mises a jour", "expected": ["historique_mises_a_jour"],
     "expected_result": "Historique updates affiche"},
    {"name": "sys_taches_planifiees", "category": "systeme", "difficulty": "normal",
     "description": "Lister les taches planifiees",
     "voice_input": "taches planifiees", "expected": ["taches_planifiees"],
     "expected_result": "Taches listees"},
    {"name": "sys_startup_apps", "category": "systeme", "difficulty": "normal",
     "description": "Voir les apps au demarrage",
     "voice_input": "apps au demarrage", "expected": ["demarrage_apps"],
     "expected_result": "Apps demarrage listees"},

    # ── APPLICATIONS VAGUE 15 ────────────────────────────────────────
    {"name": "app_store", "category": "app", "difficulty": "easy",
     "description": "Ouvrir le Microsoft Store",
     "voice_input": "ouvre le store", "expected": ["store_ouvrir"],
     "expected_result": "Microsoft Store ouvert"},
    {"name": "app_store_updates", "category": "app", "difficulty": "normal",
     "description": "Verifier les updates du Store",
     "voice_input": "mises a jour store", "expected": ["store_updates"],
     "expected_result": "Updates verifiees"},
    {"name": "app_phone_link", "category": "app", "difficulty": "easy",
     "description": "Ouvrir Phone Link",
     "voice_input": "ouvre phone link", "expected": ["ouvrir_phone_link"],
     "expected_result": "Phone Link ouvert"},

    # ── CLIPBOARD VAGUE 15 ───────────────────────────────────────────
    {"name": "clip_historique", "category": "clipboard", "difficulty": "easy",
     "description": "Ouvrir l'historique du clipboard",
     "voice_input": "historique presse papier", "expected": ["clipboard_historique", "historique_clipboard"],
     "expected_result": "Win+V ouvert"},

    # ── SAISIE VAGUE 15 ──────────────────────────────────────────────
    {"name": "saisie_emojis", "category": "saisie", "difficulty": "easy",
     "description": "Ouvrir le panneau emojis",
     "voice_input": "ouvre les emojis", "expected": ["ouvrir_emojis"],
     "expected_result": "Panneau emojis ouvert"},
    {"name": "saisie_dictee", "category": "saisie", "difficulty": "easy",
     "description": "Activer la dictee Windows",
     "voice_input": "dictee windows", "expected": ["ouvrir_dictee"],
     "expected_result": "Dictee activee"},

    # ── FICHIERS VAGUE 15 ────────────────────────────────────────────
    {"name": "file_nouvel_onglet_explorer", "category": "fichiers", "difficulty": "normal",
     "description": "Nouvel onglet dans l'Explorateur",
     "voice_input": "nouvel onglet explorateur", "expected": ["explorer_nouvel_onglet"],
     "expected_result": "Onglet explorateur ouvert"},

    # ── CORRECTIONS VAGUE 15 ─────────────────────────────────────────
    {"name": "correction_widjets", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'widjets' au lieu de 'widgets'",
     "voice_input": "ouvre les widjets", "expected": ["ouvrir_widgets"],
     "expected_result": "Correction phonetique widgets"},
    {"name": "correction_guame_bar", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'guame bar' au lieu de 'game bar'",
     "voice_input": "ouvre la guame bar", "expected": ["game_bar"],
     "expected_result": "Correction phonetique game bar"},
    {"name": "correction_fone_link", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'fone link' au lieu de 'phone link'",
     "voice_input": "ouvre fone link", "expected": ["ouvrir_phone_link", "ouvrir_app"],
     "expected_result": "Correction phonetique phone link"},

    # ═══════════════════════════════════════════════════════════════════
    # VAGUE 16 — Audio / Imprimantes / Sandbox / Accessibilite / Power
    # ═══════════════════════════════════════════════════════════════════

    # ── AUDIO ─────────────────────────────────────────────────────────
    {"name": "sys_audio_sortie", "category": "systeme", "difficulty": "easy",
     "description": "Changer la sortie audio",
     "voice_input": "sortie audio", "expected": ["audio_sortie"],
     "expected_result": "Settings son ouvert"},
    {"name": "sys_volume_mixer", "category": "systeme", "difficulty": "normal",
     "description": "Mixer de volume par app",
     "voice_input": "mixer volume", "expected": ["volume_app"],
     "expected_result": "Mixer volume ouvert"},
    {"name": "sys_micro_mute", "category": "systeme", "difficulty": "easy",
     "description": "Couper le micro",
     "voice_input": "coupe le micro", "expected": ["micro_mute_toggle", "micro_mute"],
     "expected_result": "Micro coupe"},

    # ── IMPRIMANTES ──────────────────────────────────────────────────
    {"name": "sys_imprimantes", "category": "systeme", "difficulty": "easy",
     "description": "Lister les imprimantes",
     "voice_input": "liste les imprimantes", "expected": ["liste_imprimantes"],
     "expected_result": "Imprimantes listees"},
    {"name": "sys_imprimante_defaut", "category": "systeme", "difficulty": "normal",
     "description": "Voir l'imprimante par defaut",
     "voice_input": "imprimante par defaut", "expected": ["imprimante_defaut"],
     "expected_result": "Imprimante par defaut affichee"},
    {"name": "sys_param_imprimantes", "category": "systeme", "difficulty": "easy",
     "description": "Parametres imprimantes",
     "voice_input": "parametres imprimantes", "expected": ["param_imprimantes"],
     "expected_result": "Settings imprimantes ouvert"},

    # ── SANDBOX ──────────────────────────────────────────────────────
    {"name": "sys_sandbox", "category": "systeme", "difficulty": "normal",
     "description": "Ouvrir Windows Sandbox",
     "voice_input": "ouvre la sandbox", "expected": ["sandbox_ouvrir", "ouvrir_sandbox"],
     "expected_result": "Sandbox ouverte"},

    # ── ACCESSIBILITE AVANCEE ────────────────────────────────────────
    {"name": "access_contraste", "category": "accessibilite", "difficulty": "normal",
     "description": "Activer le contraste eleve",
     "voice_input": "contraste eleve", "expected": ["contraste_eleve_toggle", "contraste_eleve"],
     "expected_result": "Contraste eleve active"},
    {"name": "access_sous_titres_live", "category": "accessibilite", "difficulty": "normal",
     "description": "Activer les sous-titres en direct",
     "voice_input": "sous titres en direct", "expected": ["sous_titres_live", "sous_titres"],
     "expected_result": "Live captions actives"},
    {"name": "access_filtre_couleur", "category": "accessibilite", "difficulty": "normal",
     "description": "Activer le filtre de couleur",
     "voice_input": "filtre de couleur", "expected": ["filtre_couleur_toggle", "filtre_couleur"],
     "expected_result": "Filtre couleur active"},
    {"name": "access_gros_curseur", "category": "accessibilite", "difficulty": "easy",
     "description": "Agrandir le curseur",
     "voice_input": "agrandis le curseur", "expected": ["taille_curseur"],
     "expected_result": "Curseur agrandi"},
    {"name": "access_narrateur", "category": "accessibilite", "difficulty": "normal",
     "description": "Activer le narrateur",
     "voice_input": "active le narrateur", "expected": ["narrateur_toggle", "narrateur"],
     "expected_result": "Narrateur active"},

    # ── POWER MANAGEMENT ─────────────────────────────────────────────
    {"name": "sys_power_plan", "category": "systeme", "difficulty": "normal",
     "description": "Voir le plan d'alimentation",
     "voice_input": "quel plan alimentation", "expected": ["plan_alimentation_actif"],
     "expected_result": "Plan actif affiche"},
    {"name": "sys_battery_report", "category": "systeme", "difficulty": "normal",
     "description": "Rapport de batterie",
     "voice_input": "rapport batterie", "expected": ["batterie_rapport"],
     "expected_result": "Rapport genere"},
    {"name": "sys_screen_timeout", "category": "systeme", "difficulty": "easy",
     "description": "Configurer la veille ecran",
     "voice_input": "timeout ecran", "expected": ["ecran_timeout"],
     "expected_result": "Settings veille ouvert"},

    # ── MULTI-ECRANS ─────────────────────────────────────────────────
    {"name": "sys_detecter_ecrans", "category": "systeme", "difficulty": "normal",
     "description": "Detecter les ecrans",
     "voice_input": "detecte les ecrans", "expected": ["detecter_ecrans"],
     "expected_result": "Ecrans detectes"},
    {"name": "sys_param_affichage", "category": "systeme", "difficulty": "easy",
     "description": "Parametres d'affichage",
     "voice_input": "parametres affichage", "expected": ["param_affichage"],
     "expected_result": "Settings display ouvert"},

    # ── PROCESSUS AVANCE ─────────────────────────────────────────────
    {"name": "sys_kill_process", "category": "systeme", "difficulty": "hard",
     "description": "Tuer un processus par nom",
     "voice_input": "tue le processus notepad", "expected": ["kill_process_nom", "kill_process"],
     "expected_result": "Processus arrete"},
    {"name": "sys_process_details", "category": "systeme", "difficulty": "normal",
     "description": "Details d'un processus",
     "voice_input": "details du processus chrome", "expected": ["processus_details"],
     "expected_result": "Details affiches"},

    # ── DIAGNOSTICS RESEAU ───────────────────────────────────────────
    {"name": "sys_diag_reseau", "category": "systeme", "difficulty": "normal",
     "description": "Diagnostic reseau complet",
     "voice_input": "diagnostic reseau", "expected": ["diagnostic_reseau"],
     "expected_result": "Diagnostic execute"},
    {"name": "sys_wifi_password", "category": "systeme", "difficulty": "hard",
     "description": "Voir le mot de passe WiFi",
     "voice_input": "mot de passe wifi", "expected": ["wifi_mot_de_passe"],
     "expected_result": "Password affiche"},

    # ── OUTILS SYSTEME ───────────────────────────────────────────────
    {"name": "sys_event_viewer", "category": "systeme", "difficulty": "normal",
     "description": "Ouvrir l'observateur d'evenements",
     "voice_input": "observateur evenements", "expected": ["ouvrir_evenements"],
     "expected_result": "Event Viewer ouvert"},
    {"name": "sys_services", "category": "systeme", "difficulty": "normal",
     "description": "Ouvrir les services",
     "voice_input": "ouvre les services", "expected": ["ouvrir_services"],
     "expected_result": "Services ouvert"},
    {"name": "sys_perfmon", "category": "systeme", "difficulty": "normal",
     "description": "Moniteur de performances",
     "voice_input": "moniteur de performance", "expected": ["ouvrir_moniteur_perf"],
     "expected_result": "PerfMon ouvert"},
    {"name": "sys_fiabilite", "category": "systeme", "difficulty": "normal",
     "description": "Moniteur de fiabilite",
     "voice_input": "moniteur de fiabilite", "expected": ["ouvrir_fiabilite"],
     "expected_result": "Reliability Monitor ouvert"},

    # ── RACCOURCIS WINDOWS ───────────────────────────────────────────
    {"name": "sys_notification_center", "category": "systeme", "difficulty": "easy",
     "description": "Ouvrir le centre de notifications",
     "voice_input": "centre de notifications", "expected": ["action_center", "centre_notifications"],
     "expected_result": "Win+N ouvert"},
    {"name": "sys_quick_settings", "category": "systeme", "difficulty": "easy",
     "description": "Ouvrir les parametres rapides",
     "voice_input": "parametres rapides", "expected": ["quick_settings"],
     "expected_result": "Win+A ouvert"},
    {"name": "sys_search_windows", "category": "systeme", "difficulty": "easy",
     "description": "Ouvrir la recherche Windows",
     "voice_input": "recherche windows", "expected": ["search_windows", "recherche_windows"],
     "expected_result": "Win+S ouvert"},

    # ── CORRECTIONS VAGUE 16 ─────────────────────────────────────────
    {"name": "correction_sandboxe", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'sandboxe' au lieu de 'sandbox'",
     "voice_input": "ouvre la sandboxe", "expected": ["sandbox_ouvrir", "ouvrir_sandbox"],
     "expected_result": "Correction phonetique sandbox"},
    {"name": "correction_imprimente", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'imprimente' au lieu de 'imprimante'",
     "voice_input": "liste les imprimentes", "expected": ["liste_imprimantes"],
     "expected_result": "Correction phonetique imprimantes"},

    # ── VAGUE 17 — WSL / HYPER-V / DIAGNOSTICS / SECURITE ─────────────
    {"name": "dev_wsl_lancer", "category": "dev", "difficulty": "easy",
     "description": "Lancer WSL (Linux)",
     "voice_input": "lance wsl", "expected": ["wsl_lancer"],
     "expected_result": "WSL demarre"},
    {"name": "dev_wsl_liste", "category": "dev", "difficulty": "normal",
     "description": "Lister distributions WSL",
     "voice_input": "liste les distributions wsl", "expected": ["wsl_liste"],
     "expected_result": "Liste des distros WSL"},
    {"name": "dev_wsl_shutdown", "category": "dev", "difficulty": "normal",
     "description": "Arreter WSL",
     "voice_input": "arrete wsl", "expected": ["wsl_shutdown"],
     "expected_result": "WSL arrete"},
    {"name": "sys_hyperv", "category": "systeme", "difficulty": "normal",
     "description": "Ouvrir Hyper-V Manager",
     "voice_input": "ouvre hyper-v", "expected": ["hyper_v_manager"],
     "expected_result": "Hyper-V Manager ouvert"},
    {"name": "app_terminal_settings", "category": "app", "difficulty": "normal",
     "description": "Ouvrir parametres Windows Terminal",
     "voice_input": "parametres du terminal", "expected": ["terminal_settings"],
     "expected_result": "Settings Terminal ouvert"},
    {"name": "access_sticky_keys", "category": "accessibilite", "difficulty": "normal",
     "description": "Touches remanentes (sticky keys)",
     "voice_input": "sticky keys", "expected": ["sticky_keys_toggle"],
     "expected_result": "Parametres touches remanentes"},
    {"name": "sys_storage_sense", "category": "systeme", "difficulty": "normal",
     "description": "Activer Storage Sense",
     "voice_input": "active l'assistant de stockage", "expected": ["storage_sense"],
     "expected_result": "Storage Sense ouvert"},
    {"name": "sys_point_restauration", "category": "systeme", "difficulty": "hard",
     "description": "Creer un point de restauration",
     "voice_input": "cree un point de restauration", "expected": ["creer_point_restauration"],
     "expected_result": "Point de restauration cree"},
    {"name": "sys_hosts", "category": "systeme", "difficulty": "normal",
     "description": "Afficher le fichier hosts",
     "voice_input": "affiche hosts", "expected": ["voir_hosts"],
     "expected_result": "Contenu du fichier hosts"},
    {"name": "sys_dxdiag", "category": "systeme", "difficulty": "easy",
     "description": "Lancer DxDiag",
     "voice_input": "lance dxdiag", "expected": ["dxdiag"],
     "expected_result": "DxDiag lance"},
    {"name": "sys_memoire_diag", "category": "systeme", "difficulty": "hard",
     "description": "Diagnostic memoire Windows",
     "voice_input": "diagnostic memoire", "expected": ["memoire_diagnostic"],
     "expected_result": "MdSched lance"},
    {"name": "sys_reset_reseau", "category": "systeme", "difficulty": "hard",
     "description": "Reinitialiser la pile reseau",
     "voice_input": "reinitialise le reseau", "expected": ["reset_reseau"],
     "expected_result": "Winsock et IP reinitialises"},
    {"name": "sys_bitlocker", "category": "systeme", "difficulty": "normal",
     "description": "Verifier le statut BitLocker",
     "voice_input": "statut bitlocker", "expected": ["bitlocker_status"],
     "expected_result": "Statut BitLocker affiche"},
    {"name": "sys_update_pause", "category": "systeme", "difficulty": "normal",
     "description": "Mettre en pause Windows Update",
     "voice_input": "pause les mises a jour", "expected": ["windows_update_pause"],
     "expected_result": "Page Windows Update ouverte"},
    {"name": "sys_mode_dev", "category": "systeme", "difficulty": "normal",
     "description": "Activer le mode developpeur",
     "voice_input": "mode developpeur", "expected": ["mode_developpeur"],
     "expected_result": "Parametres dev ouverts"},
    {"name": "sys_remote_desktop", "category": "systeme", "difficulty": "normal",
     "description": "Ouvrir les parametres Bureau a distance",
     "voice_input": "bureau a distance", "expected": ["remote_desktop"],
     "expected_result": "Remote Desktop settings"},
    {"name": "sys_credential_manager", "category": "systeme", "difficulty": "normal",
     "description": "Ouvrir le gestionnaire d'identifiants",
     "voice_input": "gestionnaire d'identifiants", "expected": ["credential_manager"],
     "expected_result": "Credential Manager ouvert"},
    {"name": "sys_certmgr", "category": "systeme", "difficulty": "normal",
     "description": "Ouvrir le gestionnaire de certificats",
     "voice_input": "gestionnaire de certificats", "expected": ["certmgr"],
     "expected_result": "CertMgr ouvert"},
    {"name": "sys_chkdsk", "category": "systeme", "difficulty": "hard",
     "description": "Verifier les erreurs disque",
     "voice_input": "verifie le disque", "expected": ["chkdsk_check"],
     "expected_result": "ChkDsk lance"},
    {"name": "clipboard_coller_brut", "category": "clipboard", "difficulty": "normal",
     "description": "Coller sans mise en forme",
     "voice_input": "colle sans format", "expected": ["coller_sans_format"],
     "expected_result": "Ctrl+Shift+V envoye"},
    {"name": "sys_file_history", "category": "systeme", "difficulty": "normal",
     "description": "Ouvrir l'historique des fichiers",
     "voice_input": "historique des fichiers", "expected": ["file_history"],
     "expected_result": "Parametres backup ouverts"},
    {"name": "sys_troubleshoot_reseau", "category": "systeme", "difficulty": "hard",
     "description": "Depanner le reseau",
     "voice_input": "depanne le reseau", "expected": ["troubleshoot_reseau"],
     "expected_result": "Depannage reseau lance"},
    {"name": "sys_troubleshoot_audio", "category": "systeme", "difficulty": "hard",
     "description": "Depanner le son",
     "voice_input": "depanne le son", "expected": ["troubleshoot_audio"],
     "expected_result": "Depannage audio lance"},
    {"name": "sys_troubleshoot_update", "category": "systeme", "difficulty": "hard",
     "description": "Depanner Windows Update",
     "voice_input": "depanne windows update", "expected": ["troubleshoot_update"],
     "expected_result": "Depannage WU lance"},
    {"name": "sys_power_options", "category": "systeme", "difficulty": "normal",
     "description": "Options d'alimentation avancees",
     "voice_input": "options d'alimentation", "expected": ["power_options"],
     "expected_result": "PowerCfg CPL ouvert"},

    # ── CORRECTIONS VAGUE 17 ─────────────────────────────────────────
    {"name": "correction_wessel", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'wessel' au lieu de 'wsl'",
     "voice_input": "lance wessel", "expected": ["wsl_lancer"],
     "expected_result": "Correction WSL phonetique"},
    {"name": "correction_bitlockeur", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'bitlockeur' au lieu de 'bitlocker'",
     "voice_input": "statut bitlockeur", "expected": ["bitlocker_status"],
     "expected_result": "Correction BitLocker phonetique"},
    {"name": "correction_depannaje", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'depannaje' au lieu de 'depannage'",
     "voice_input": "depannaje reseau", "expected": ["troubleshoot_reseau"],
     "expected_result": "Correction depannage phonetique"},
    {"name": "correction_hipeurv", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'hipeur v' au lieu de 'hyper-v'",
     "voice_input": "ouvre hipeur v", "expected": ["hyper_v_manager"],
     "expected_result": "Correction Hyper-V phonetique"},
    {"name": "correction_developeur", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'developeur' au lieu de 'developpeur'",
     "voice_input": "mode developeur", "expected": ["mode_developpeur"],
     "expected_result": "Correction developpeur phonetique"},

    # ═══════════════════════════════════════════════════════════════════
    # VAGUE 18 — Copilot, Screenshots, Planificateur, Disque, USB,
    #            Adaptateurs, Firewall, Langue, NTP, Securite
    # ═══════════════════════════════════════════════════════════════════

    # ── Copilot / AI ──────────────────────────────────────────────────
    {"name": "app_copilot_lancer", "category": "app", "difficulty": "easy",
     "description": "Lancer Windows Copilot",
     "voice_input": "lance copilot", "expected": ["copilot_lancer"],
     "expected_result": "Copilot lance"},
    {"name": "sys_copilot_params", "category": "systeme", "difficulty": "normal",
     "description": "Parametres de Copilot",
     "voice_input": "parametres copilot", "expected": ["copilot_parametres"],
     "expected_result": "Page Copilot settings"},
    {"name": "sys_cortana_off", "category": "systeme", "difficulty": "normal",
     "description": "Desactiver Cortana",
     "voice_input": "desactive cortana", "expected": ["cortana_desactiver"],
     "expected_result": "Cortana desactivee"},

    # ── Screenshots avances ───────────────────────────────────────────
    {"name": "sys_capture_fenetre", "category": "systeme", "difficulty": "normal",
     "description": "Capturer la fenetre active",
     "voice_input": "capture la fenetre", "expected": ["capture_fenetre"],
     "expected_result": "Alt+PrintScreen envoye"},
    {"name": "sys_capture_retardee", "category": "systeme", "difficulty": "hard",
     "description": "Capture d'ecran retardee",
     "voice_input": "capture retardee", "expected": ["capture_retardee"],
     "expected_result": "Capture retardee lancee"},
    {"name": "fichiers_dossier_captures", "category": "fichiers", "difficulty": "easy",
     "description": "Ouvrir le dossier screenshots",
     "voice_input": "dossier captures", "expected": ["dossier_captures"],
     "expected_result": "Dossier Screenshots ouvert"},

    # ── Planificateur ─────────────────────────────────────────────────
    {"name": "sys_planificateur", "category": "systeme", "difficulty": "normal",
     "description": "Ouvrir le planificateur de taches",
     "voice_input": "ouvre le planificateur", "expected": ["planificateur_ouvrir"],
     "expected_result": "Task Scheduler ouvert"},
    {"name": "sys_creer_tache", "category": "systeme", "difficulty": "hard",
     "description": "Creer une tache planifiee",
     "voice_input": "cree une tache planifiee", "expected": ["creer_tache_planifiee"],
     "expected_result": "Assistant tache lancee"},

    # ── Disque avance ─────────────────────────────────────────────────

    # ── USB / Peripheriques ───────────────────────────────────────────
    {"name": "sys_lister_usb", "category": "systeme", "difficulty": "easy",
     "description": "Lister les peripheriques USB",
     "voice_input": "liste les usb", "expected": ["lister_usb"],
     "expected_result": "Liste USB affichee"},
    {"name": "sys_ejecter_usb", "category": "systeme", "difficulty": "normal",
     "description": "Ejecter un USB en securite",
     "voice_input": "ejecte l'usb", "expected": ["ejecter_usb"],
     "expected_result": "USB ejecte"},
    {"name": "sys_peripheriques_connectes", "category": "systeme", "difficulty": "easy",
     "description": "Lister les peripheriques connectes",
     "voice_input": "peripheriques connectes", "expected": ["peripheriques_connectes"],
     "expected_result": "Liste peripheriques affichee"},

    # ── Adaptateurs reseau ────────────────────────────────────────────
    {"name": "sys_lister_adaptateurs", "category": "systeme", "difficulty": "normal",
     "description": "Lister les adaptateurs reseau",
     "voice_input": "liste les adaptateurs reseau", "expected": ["lister_adaptateurs"],
     "expected_result": "Adaptateurs listes"},
    {"name": "sys_desactiver_wifi", "category": "systeme", "difficulty": "hard",
     "description": "Desactiver l'adaptateur Wi-Fi",
     "voice_input": "desactive la carte wifi", "expected": ["desactiver_wifi_adaptateur"],
     "expected_result": "Wi-Fi desactive"},
    {"name": "sys_activer_wifi", "category": "systeme", "difficulty": "hard",
     "description": "Activer l'adaptateur Wi-Fi",
     "voice_input": "active l'adaptateur wifi", "expected": ["activer_wifi_adaptateur"],
     "expected_result": "Wi-Fi active"},

    # ── Firewall avance ───────────────────────────────────────────────
    {"name": "sys_firewall_status", "category": "systeme", "difficulty": "normal",
     "description": "Statut du pare-feu",
     "voice_input": "statut firewall", "expected": ["firewall_status"],
     "expected_result": "Statut firewall affiche"},
    {"name": "sys_firewall_regles", "category": "systeme", "difficulty": "hard",
     "description": "Lister les regles du pare-feu",
     "voice_input": "regles firewall", "expected": ["firewall_regles"],
     "expected_result": "Regles listees"},
    {"name": "sys_firewall_reset", "category": "systeme", "difficulty": "hard",
     "description": "Reinitialiser le pare-feu",
     "voice_input": "reset firewall", "expected": ["firewall_reset"],
     "expected_result": "Firewall reinitialise"},

    # ── Langue / Clavier ──────────────────────────────────────────────
    {"name": "sys_ajouter_langue", "category": "systeme", "difficulty": "normal",
     "description": "Ajouter une langue",
     "voice_input": "ajoute une langue", "expected": ["ajouter_langue"],
     "expected_result": "Page ajout langue"},
    {"name": "sys_ajouter_clavier", "category": "systeme", "difficulty": "normal",
     "description": "Ajouter un clavier",
     "voice_input": "ajoute un clavier", "expected": ["ajouter_clavier"],
     "expected_result": "Page clavier settings"},
    {"name": "sys_langues_installees", "category": "systeme", "difficulty": "easy",
     "description": "Lister les langues installees",
     "voice_input": "langues installees", "expected": ["langues_installees"],
     "expected_result": "Liste langues affichee"},

    # ── NTP / Heure ───────────────────────────────────────────────────
    {"name": "sys_sync_heure", "category": "systeme", "difficulty": "normal",
     "description": "Synchroniser l'heure NTP",
     "voice_input": "synchronise l'heure", "expected": ["synchroniser_heure"],
     "expected_result": "Heure synchronisee"},
    {"name": "sys_serveur_ntp", "category": "systeme", "difficulty": "normal",
     "description": "Afficher le serveur NTP",
     "voice_input": "serveur ntp", "expected": ["serveur_ntp"],
     "expected_result": "Info NTP affichee"},

    # ── Securite avancee ──────────────────────────────────────────────
    {"name": "sys_windows_hello", "category": "systeme", "difficulty": "normal",
     "description": "Parametres Windows Hello",
     "voice_input": "windows hello", "expected": ["windows_hello"],
     "expected_result": "Page Hello ouverte"},
    {"name": "sys_securite_comptes", "category": "systeme", "difficulty": "normal",
     "description": "Securite des comptes",
     "voice_input": "securite des comptes", "expected": ["securite_comptes"],
     "expected_result": "Page securite comptes"},
    {"name": "sys_activation_windows", "category": "systeme", "difficulty": "easy",
     "description": "Verifier l'activation Windows",
     "voice_input": "activation windows", "expected": ["activation_windows"],
     "expected_result": "Statut activation affiche"},
    {"name": "sys_recuperation", "category": "systeme", "difficulty": "normal",
     "description": "Options de recuperation",
     "voice_input": "recuperation systeme", "expected": ["recuperation_systeme"],
     "expected_result": "Page recovery ouverte"},

    # ── CORRECTIONS VAGUE 18 ─────────────────────────────────────────
    {"name": "correction_kopilot", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'kopilot' au lieu de 'copilot'",
     "voice_input": "lance kopilot", "expected": ["copilot_lancer"],
     "expected_result": "Correction copilot phonetique"},
    {"name": "correction_cortanna", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'cortanna' au lieu de 'cortana'",
     "voice_input": "desactive cortanna", "expected": ["cortana_desactiver"],
     "expected_result": "Correction cortana phonetique"},
    {"name": "correction_plannificateur", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'plannificateur' au lieu de 'planificateur'",
     "voice_input": "ouvre le plannificateur", "expected": ["planificateur_ouvrir"],
     "expected_result": "Correction planificateur phonetique"},
    {"name": "correction_fairewall", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'fairewall' au lieu de 'firewall'",
     "voice_input": "statut fairewall", "expected": ["firewall_status"],
     "expected_result": "Correction firewall phonetique"},
    {"name": "correction_sinkronise", "category": "correction", "difficulty": "hard",
     "description": "STT retourne 'sinkronise' au lieu de 'synchronise'",
     "voice_input": "sinkronise l'heure", "expected": ["synchroniser_heure"],
     "expected_result": "Correction synchronise phonetique"},
]


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO VALIDATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════

def _simulate_match(voice_input: str) -> tuple[str | None, float, str]:
    """Simulate voice command matching without executing.

    Returns: (matched_command_name, score, match_type)
    match_type: 'command', 'skill', 'none'

    Priority: skills/pipelines first (they are multi-step), then single commands.
    """
    # 1. Apply voice corrections
    corrected = correct_voice_text(voice_input)

    # 2. Try skill match FIRST (pipelines are higher priority)
    skill, skill_score = find_skill(corrected)

    # 3. Try command match
    cmd, params, cmd_score = match_command(corrected)

    # 4. Return best match with skill priority
    # Skills (pipelines) are multi-step and should take priority when they match well
    if skill and skill_score >= 0.65:
        # Only prefer command if it's a PERFECT exact match (1.0)
        if cmd and cmd_score == 1.0:
            return cmd.name, cmd_score, "command"
        return skill.name, skill_score, "skill"

    # If command matches
    if cmd and cmd_score >= 0.60:
        return cmd.name, cmd_score, "command"

    # Fallback to skill with lower threshold
    if skill and skill_score >= 0.55:
        return skill.name, skill_score, "skill"

    # No match
    best = max(cmd_score if cmd else 0, skill_score if skill else 0)
    return None, best, "none"


def validate_scenario(scenario: dict, cycle_number: int) -> dict:
    """Validate a single scenario and record the result."""
    start = time.perf_counter()

    voice_input = scenario["voice_input"]
    expected_names = scenario["expected"]  # List of acceptable command names

    matched_name, score, match_type = _simulate_match(voice_input)
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Determine result
    if matched_name and matched_name in expected_names:
        result = "pass"
        details = f"Match exact: {matched_name} (score={score:.2f}, type={match_type})"
    elif matched_name and score >= 0.75:
        result = "partial"
        details = f"Match partiel: {matched_name} au lieu de {expected_names} (score={score:.2f})"
    elif matched_name:
        result = "fail"
        details = f"Mauvais match: {matched_name} au lieu de {expected_names} (score={score:.2f})"
    else:
        result = "fail"
        details = f"Aucun match pour '{voice_input}' (expected={expected_names}, best_score={score:.2f})"

    # Record in database
    record_validation(
        cycle_number=cycle_number,
        scenario_name=scenario["name"],
        voice_input=voice_input,
        matched_command=matched_name,
        match_score=score,
        expected_command=expected_names[0] if expected_names else "",
        result=result,
        details=details,
        execution_time_ms=elapsed_ms,
        scenario_id=scenario.get("id"),
    )

    return {
        "scenario": scenario["name"],
        "voice_input": voice_input,
        "matched": matched_name,
        "expected": expected_names,
        "score": score,
        "result": result,
        "details": details,
        "time_ms": round(elapsed_ms, 2),
    }


def run_validation_cycle(cycle_number: int, scenarios: list[dict] | None = None) -> dict:
    """Run a full validation cycle across all scenarios."""
    if scenarios is None:
        scenarios = get_all_scenarios()
        if not scenarios:
            scenarios = SCENARIO_TEMPLATES

    results = []
    for scenario in scenarios:
        r = validate_scenario(scenario, cycle_number)
        results.append(r)

    passed = sum(1 for r in results if r["result"] == "pass")
    failed = sum(1 for r in results if r["result"] == "fail")
    partial = sum(1 for r in results if r["result"] == "partial")
    total = len(results)

    return {
        "cycle": cycle_number,
        "total": total,
        "passed": passed,
        "failed": failed,
        "partial": partial,
        "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
        "avg_time_ms": round(sum(r["time_ms"] for r in results) / total, 2) if total > 0 else 0,
        "results": results,
    }


def run_50_cycles() -> dict:
    """Run 50 validation cycles and return comprehensive report."""
    # Initialize database
    init_db()
    logger.info("[1/4] Base SQL initialisee")

    # Import data
    n_cmd = import_commands_from_code()
    n_skill = import_skills_from_code()
    n_corr = import_corrections_from_code()
    logger.info("[2/4] Importe: %d commandes, %d skills, %d corrections", n_cmd, n_skill, n_corr)

    # Load scenarios into DB
    for tpl in SCENARIO_TEMPLATES:
        add_scenario(
            name=tpl["name"],
            description=tpl["description"],
            category=tpl["category"],
            voice_input=tpl["voice_input"],
            expected_commands=tpl["expected"],
            expected_result=tpl["expected_result"],
            difficulty=tpl.get("difficulty", "normal"),
        )
    logger.info("[3/4] %d scenarios charges", len(SCENARIO_TEMPLATES))

    # Run 50 cycles
    all_cycles = []
    for cycle in range(1, 51):
        cycle_result = run_validation_cycle(cycle, SCENARIO_TEMPLATES)
        all_cycles.append(cycle_result)
        if cycle % 10 == 0:
            logger.info("[Cycle %d/50] Pass rate: %s%% (%d/%d)", cycle, cycle_result['pass_rate'], cycle_result['passed'], cycle_result['total'])

    # Compile final report
    total_tests = sum(c["total"] for c in all_cycles)
    total_passed = sum(c["passed"] for c in all_cycles)
    total_failed = sum(c["failed"] for c in all_cycles)
    total_partial = sum(c["partial"] for c in all_cycles)

    init_db()  # Ensure tables exist before stats query
    stats = get_stats()
    logger.info("[4/4] 50 cycles termines — %d/%d passes (%.1f%%)", total_passed, total_tests, total_passed/total_tests*100 if total_tests else 0)

    # Find failed scenarios for analysis
    failures = {}
    for c in all_cycles:
        for r in c["results"]:
            if r["result"] in ("fail", "partial"):
                key = r["scenario"]
                if key not in failures:
                    failures[key] = {"count": 0, "details": r["details"], "voice_input": r["voice_input"]}
                failures[key]["count"] += 1

    return {
        "summary": {
            "total_cycles": 50,
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_partial": total_partial,
            "global_pass_rate": round(total_passed / total_tests * 100, 1) if total_tests > 0 else 0,
        },
        "db_stats": stats,
        "failures": failures,
        "cycles": [{k: v for k, v in c.items() if k != "results"} for c in all_cycles],
    }


# ═══════════════════════════════════════════════════════════════════════════
# CLI ENTRY
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    print("=" * 70)
    print("  JARVIS SCENARIO ENGINE — 50 Cycles de Validation")
    print("=" * 70)

    report = run_50_cycles()

    print("\n" + "=" * 70)
    print("  RAPPORT FINAL")
    print("=" * 70)
    s = report["summary"]
    print(f"  Cycles: {s['total_cycles']}")
    print(f"  Tests totaux: {s['total_tests']}")
    print(f"  Passes: {s['total_passed']} ({s['global_pass_rate']}%)")
    print(f"  Echoues: {s['total_failed']}")
    print(f"  Partiels: {s['total_partial']}")

    if report["failures"]:
        print(f"\n  SCENARIOS EN ECHEC ({len(report['failures'])} uniques):")
        for name, info in sorted(report["failures"].items(), key=lambda x: -x[1]["count"]):
            print(f"    {name}: {info['count']}x — {info['details'][:80]}")

    db = report["db_stats"]
    print(f"\n  BASE SQL: {db['commands']} cmds, {db['skills']} skills, {db['corrections']} corrections")
    print(f"  Scenarios: {db['scenarios']} ({db['scenarios_validated']} valides)")
    print(f"  Cycles enregistres: {db['validation_cycles']}")
