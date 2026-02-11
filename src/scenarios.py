"""JARVIS Scenario Engine — Generate, simulate, and validate voice command scenarios.

Generates realistic usage scenarios, runs them through the command matching pipeline,
and records pass/fail results in the SQL database.
"""

from __future__ import annotations

import json
import random
import time
from typing import Any

from src.database import (
    init_db, add_scenario, get_all_scenarios, record_validation,
    get_stats, get_validation_report, import_commands_from_code,
    import_skills_from_code, import_corrections_from_code,
)
from src.commands import match_command, correct_voice_text, COMMANDS
from src.skills import find_skill, load_skills


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
     "voice_input": "mode dev", "expected": ["mode_dev"],
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
    print("  [1/4] Base SQL initialisee")

    # Import data
    n_cmd = import_commands_from_code()
    n_skill = import_skills_from_code()
    n_corr = import_corrections_from_code()
    print(f"  [2/4] Importe: {n_cmd} commandes, {n_skill} skills, {n_corr} corrections")

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
    print(f"  [3/4] {len(SCENARIO_TEMPLATES)} scenarios charges")

    # Run 50 cycles
    all_cycles = []
    for cycle in range(1, 51):
        cycle_result = run_validation_cycle(cycle, SCENARIO_TEMPLATES)
        all_cycles.append(cycle_result)
        if cycle % 10 == 0:
            print(f"  [Cycle {cycle}/50] Pass rate: {cycle_result['pass_rate']}% ({cycle_result['passed']}/{cycle_result['total']})")

    # Compile final report
    total_tests = sum(c["total"] for c in all_cycles)
    total_passed = sum(c["passed"] for c in all_cycles)
    total_failed = sum(c["failed"] for c in all_cycles)
    total_partial = sum(c["partial"] for c in all_cycles)

    stats = get_stats()
    print(f"  [4/4] 50 cycles termines — {total_passed}/{total_tests} passes ({round(total_passed/total_tests*100, 1)}%)")

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
