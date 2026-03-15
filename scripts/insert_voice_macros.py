#!/usr/bin/env python3
"""insert_voice_macros.py — Insere 30 macros vocales pre-enregistrees dans jarvis.db.

Lance une seule fois pour peupler la table voice_macros avec les macros courantes.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "jarvis.db"

# ── 30 macros pre-enregistrees ──────────────────────────────────────────────
PREBUILT_MACROS: list[dict[str, str | list[str]]] = [
    {
        "name": "ouvre_mon_espace_de_travail",
        "description": "Ouvre terminal + vscode + firefox",
        "commands": ["ouvre terminal", "ouvre vscode", "ouvre firefox"],
    },
    {
        "name": "ferme_tout",
        "description": "Ferme toutes les fenetres ouvertes",
        "commands": ["ferme toutes les fenêtres"],
    },
    {
        "name": "prépare_une_présentation",
        "description": "Ouvre LibreOffice Impress, plein ecran et mode ne pas deranger",
        "commands": ["ouvre libreoffice impress", "plein écran", "active ne pas déranger"],
    },
    {
        "name": "mode_musique",
        "description": "Ouvre Spotify et regle le volume a 60%",
        "commands": ["ouvre spotify", "volume 60"],
    },
    {
        "name": "mode_silence",
        "description": "Mute, mode ne pas deranger, baisse luminosite ecran",
        "commands": ["mute", "active ne pas déranger", "luminosité 20"],
    },
    {
        "name": "session_code_python",
        "description": "Ouvre terminal, VSCode et IPython",
        "commands": ["ouvre terminal", "ouvre vscode", "lance ipython"],
    },
    {
        "name": "vérifie_tout",
        "description": "Git status, tests, services et GPU",
        "commands": ["git status", "lance les tests", "vérifie les services", "vérifie gpu"],
    },
    {
        "name": "sauvegarde_et_push",
        "description": "Git add, commit et push",
        "commands": ["git add tout", "git commit", "git push"],
    },
    {
        "name": "diagnostic_complet",
        "description": "Diagnostic CPU, RAM, GPU, disque, reseau et services",
        "commands": [
            "vérifie cpu",
            "vérifie ram",
            "vérifie gpu",
            "vérifie disque",
            "vérifie réseau",
            "vérifie les services",
        ],
    },
    {
        "name": "nettoie_l_écran",
        "description": "Ferme notifications, minimise tout, reset wallpaper",
        "commands": ["ferme les notifications", "minimise tout", "reset wallpaper"],
    },
    {
        "name": "mode_lecture",
        "description": "Ouvre Firefox plein ecran avec luminosite basse",
        "commands": ["ouvre firefox", "plein écran", "luminosité 30"],
    },
    {
        "name": "mode_gaming",
        "description": "Ferme apps inutiles, mode performance, lance Steam",
        "commands": ["ferme les apps inutiles", "mode performance", "ouvre steam"],
    },
    {
        "name": "capture_et_partage",
        "description": "Capture ecran et copie dans le presse-papier",
        "commands": ["capture écran", "copie dans le presse-papier"],
    },
    {
        "name": "moniteur_temps_réel",
        "description": "Lance htop, nvidia-smi en boucle et iotop",
        "commands": ["lance htop", "lance nvidia-smi", "lance iotop"],
    },
    {
        "name": "mise_à_jour_complète",
        "description": "apt update, upgrade, snap refresh et verification reboot",
        "commands": ["apt update", "apt upgrade", "snap refresh", "vérifie reboot"],
    },
    {
        "name": "rapport_du_matin",
        "description": "Meteo, emails, git status et etat des services",
        "commands": ["donne la météo", "vérifie les emails", "git status", "vérifie les services"],
    },
    {
        "name": "session_trading",
        "description": "Ouvre TradingView, terminal pipeline et check GPU",
        "commands": ["ouvre tradingview", "lance le pipeline trading", "vérifie gpu"],
    },
    {
        "name": "debug_réseau",
        "description": "Ping, traceroute, DNS, ports et connexions",
        "commands": [
            "ping google",
            "traceroute google",
            "vérifie dns",
            "vérifie les ports",
            "liste les connexions",
        ],
    },
    {
        "name": "compile_et_teste",
        "description": "Build, pytest et coverage",
        "commands": ["lance le build", "lance pytest", "lance coverage"],
    },
    {
        "name": "archive_le_projet",
        "description": "Git bundle, archive tar et checksum",
        "commands": ["git bundle", "archive tar", "vérifie checksum"],
    },
    {
        "name": "mode_voyage",
        "description": "Economie energie, sync cloud et verrouillage",
        "commands": ["mode économie énergie", "synchronise le cloud", "verrouille l'écran"],
    },
    {
        "name": "restaure_l_audio",
        "description": "Redemarre PipeWire, volume 70% et unmute",
        "commands": ["redémarre pipewire", "volume 70", "unmute"],
    },
    {
        "name": "ouvre_la_doc",
        "description": "Ouvre docs JARVIS dans Firefox et man pages dans terminal",
        "commands": ["ouvre firefox docs jarvis", "ouvre terminal man pages"],
    },
    {
        "name": "check_sécurité",
        "description": "Verifie UFW, fail2ban, ports et permissions",
        "commands": [
            "vérifie ufw",
            "vérifie fail2ban",
            "vérifie les ports",
            "vérifie les permissions",
        ],
    },
    {
        "name": "mode_streaming",
        "description": "Lance OBS, Discord, verifie micro et camera",
        "commands": ["ouvre obs", "ouvre discord", "vérifie le micro", "vérifie la caméra"],
    },
    {
        "name": "range_les_fichiers",
        "description": "Organise les telechargements par type de fichier",
        "commands": ["organise les téléchargements"],
    },
    {
        "name": "sauvegarde_bases",
        "description": "Vacuum, backup SQLite et verification",
        "commands": ["vacuum base de données", "backup sqlite", "vérifie backup"],
    },
    {
        "name": "mode_zen",
        "description": "Fond nature, musique lo-fi, DND et timer pomodoro 25min",
        "commands": [
            "fond d'écran nature",
            "lance musique lo-fi",
            "active ne pas déranger",
            "timer 25 minutes",
        ],
    },
    {
        "name": "emergency_stop",
        "description": "Kill GPU processes, arrete le trading et envoie une alerte",
        "commands": ["kill gpu processes", "arrête le trading", "envoie une alerte"],
    },
    {
        "name": "fin_de_journée",
        "description": "Sauvegarde, backup, rapport, mode economie et verrouillage",
        "commands": [
            "sauvegarde tout",
            "lance le backup",
            "génère le rapport",
            "mode économie énergie",
            "verrouille l'écran",
        ],
    },
]


def main() -> None:
    """Insere les 30 macros pre-enregistrees dans la base."""
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    now = time.time()
    inserted = 0
    skipped = 0

    for macro in PREBUILT_MACROS:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO voice_macros
                   (name, commands, description, usage_count, created_at, last_used)
                   VALUES (?, ?, ?, 0, ?, 0)""",
                (
                    macro["name"],
                    json.dumps(macro["commands"], ensure_ascii=False),
                    macro["description"],
                    now,
                ),
            )
            if conn.total_changes > inserted + skipped:
                inserted += 1
            else:
                skipped += 1
        except sqlite3.Error as e:
            print(f"  [ERREUR] {macro['name']}: {e}")
            skipped += 1

    conn.commit()
    conn.close()
    print(f"Terminé: {inserted} macros insérées, {skipped} ignorées (déjà présentes).")


if __name__ == "__main__":
    main()
