"""Ajoute les 86 skills dans etoile.db map."""

import sqlite3
import json
from datetime import datetime

import os as _os
try:
    from src.config import PATHS
    _etoile_path = str(PATHS["etoile_db"])
except ImportError:
    _etoile_path = _os.path.join(_os.path.dirname(__file__), "data", "etoile.db")
conn = sqlite3.connect(_etoile_path)
cur = conn.cursor()
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

skills = {
    # Vague 1 (8)
    "rapport_matin": ("routine", "Rapport matinal complet"),
    "mode_trading": ("trading", "Mode trading MEXC"),
    "mode_dev": ("dev", "Mode developpement"),
    "mode_gaming": ("loisir", "Mode gaming"),
    "diagnostic_complet": ("systeme", "Diagnostic systeme complet"),
    "consensus_trading": ("trading", "Consensus multi-IA trading"),
    "cleanup_ram": ("systeme", "Nettoyage RAM"),
    "ferme_tout": ("systeme", "Fermer toutes les apps"),
    # Vague 2 (11)
    "mode_presentation": ("productivite", "Mode presentation"),
    "mode_focus": ("productivite", "Mode focus travail"),
    "mode_musique": ("loisir", "Mode musique"),
    "routine_soir": ("routine", "Routine du soir"),
    "workspace_frontend": ("dev", "Workspace frontend"),
    "workspace_backend": ("dev", "Workspace backend"),
    "optimiser_pc": ("systeme", "Optimiser performances PC"),
    "monitoring_complet": ("systeme", "Monitoring complet cluster"),
    "split_screen_travail": ("productivite", "Split screen travail"),
    "backup_rapide": ("fichiers", "Backup rapide"),
    "check_trading_complet": ("trading", "Check trading complet"),
    # Vague 3 (14)
    "mode_reunion": ("communication", "Mode reunion"),
    "mode_communication": ("communication", "Mode communication"),
    "pause_cafe": ("routine", "Pause cafe"),
    "retour_pause": ("routine", "Retour de pause"),
    "mode_ia": ("dev", "Mode IA/ML"),
    "deploiement": ("dev", "Pipeline deploiement"),
    "debug_reseau": ("systeme", "Debug reseau"),
    "mode_lecture": ("loisir", "Mode lecture"),
    "update_systeme": ("systeme", "Mise a jour systeme"),
    "mode_recherche": ("productivite", "Mode recherche web"),
    "workspace_turbo": ("dev", "Workspace turbo project"),
    "rapport_soir": ("routine", "Rapport du soir"),
    "mode_cinema": ("loisir", "Mode cinema"),
    "mode_securite": ("systeme", "Mode securite"),
    # Vague 4 (8)
    "mode_accessibilite": ("accessibilite", "Mode accessibilite"),
    "mode_economie_energie": ("systeme", "Mode economie energie"),
    "mode_performance_max": ("systeme", "Performance maximale"),
    "clean_reseau": ("systeme", "Nettoyage reseau"),
    "workspace_data": ("dev", "Workspace data science"),
    "session_creative": ("productivite", "Session creative"),
    "mode_double_ecran": ("productivite", "Mode double ecran"),
    "nettoyage_complet": ("systeme", "Nettoyage complet"),
    "mode_confort": ("accessibilite", "Mode confort"),
    # Vague 5 (5)
    "check_espace_disque": ("systeme", "Verification espace disque"),
    "audit_securite": ("systeme", "Audit securite"),
    "maintenance_complete": ("systeme", "Maintenance complete"),
    "mode_partage_ecran": ("communication", "Mode partage ecran"),
    "diagnostic_demarrage": ("systeme", "Diagnostic demarrage"),
    # Vague 6 (2)
    "mode_nuit_complet": ("routine", "Mode nuit complet"),
    "mode_jour": ("routine", "Mode jour"),
    # Vague 7 (3)
    "diagnostic_reseau_complet": ("systeme", "Diagnostic reseau complet"),
    "diagnostic_sante_pc": ("systeme", "Diagnostic sante PC"),
    "preparation_backup": ("fichiers", "Preparation backup"),
    # Vague 8 (4)
    "mode_docker": ("dev", "Mode Docker"),
    "git_workflow": ("dev", "Git workflow"),
    "workspace_ml": ("dev", "Workspace machine learning"),
    "debug_docker": ("dev", "Debug Docker"),
    # Vague 9 (3)
    "mode_stream": ("loisir", "Mode streaming"),
    "nettoyage_clipboard": ("systeme", "Nettoyage clipboard"),
    "inventaire_apps": ("systeme", "Inventaire applications"),
    # Vague 10 (2)
    "fin_journee": ("routine", "Fin de journee"),
    "mode_dual_screen": ("productivite", "Mode dual screen"),
    # Vague 11 (3)
    "inventaire_hardware": ("systeme", "Inventaire hardware"),
    "check_performances": ("systeme", "Check performances"),
    "rapport_batterie": ("systeme", "Rapport batterie"),
    # Vague 12 (3)
    "mode_4_fenetres": ("productivite", "Mode 4 fenetres"),
    "mode_accessibilite_complet": ("accessibilite", "Accessibilite complet"),
    "navigation_rapide": ("navigation", "Navigation rapide"),
    # Vague 13 (3)
    "audit_reseau": ("systeme", "Audit reseau"),
    "optimise_dns": ("systeme", "Optimiser DNS"),
    "diagnostic_connexion": ("systeme", "Diagnostic connexion"),
    # Vague 14 (3)
    "nettoyage_fichiers": ("fichiers", "Nettoyage fichiers"),
    "backup_projet": ("fichiers", "Backup projet"),
    "analyse_code": ("dev", "Analyse code"),
    # Vague 15 (6)
    "forge_code": ("dev", "Forge code pipeline"),
    "shield_audit": ("systeme", "Shield audit securite"),
    "brain_index": ("dev", "Brain indexation"),
    "medic_repair": ("systeme", "Medic reparation"),
    "consensus_mao": ("dev", "Consensus MAO multi-agent"),
    "lab_tests": ("dev", "Lab tests validation"),
    # Vague 16 (5)
    "architect_diagram": ("dev", "Architect diagramme"),
    "oracle_veille": ("productivite", "Oracle veille techno"),
    "sentinel_securite": ("systeme", "Sentinel securite"),
    "alchemist_transform": ("dev", "Alchemist transformation"),
    "director_standup": ("routine", "Director standup"),
}

inserted = 0
for name, (cat, desc) in skills.items():
    cur.execute("SELECT COUNT(*) FROM map WHERE entity_name=? AND entity_type='skill'", (name,))
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO map (entity_type,entity_name,parent,role,status,priority,metadata,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("skill", name, cat, desc, "active", 2, json.dumps({"category": cat, "source": "skills.py"}), now, now),
        )
        inserted += 1

conn.commit()

# Final count
cur.execute("SELECT COUNT(*) FROM map")
total = cur.fetchone()[0]
cur.execute("SELECT entity_type, COUNT(*) FROM map GROUP BY entity_type ORDER BY COUNT(*) DESC")
breakdown = cur.fetchall()

print(f"{inserted} skills inserees")
print(f"\nMAP TOTAL: {total} entrees")
for t, c in breakdown:
    print(f"  {t:15s}: {c:3d}")

conn.close()
