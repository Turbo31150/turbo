#!/usr/bin/env python3
"""Insere les commandes vocales des 11 nouveaux modules Linux dans jarvis.db."""

import json
import sqlite3
import time

DB_PATH = "/home/turbo/jarvis/data/jarvis.db"

# Toutes les commandes vocales organisees par module
LINUX_COMMANDS = [
    # ── 1. linux_journal_reader.py ──
    {
        "name": "linux_journal_logs_systeme",
        "category": "linux_journal",
        "description": "Affiche les 50 derniers logs systeme",
        "triggers": ["montre les logs système", "logs système", "montre les logs systeme"],
        "action_type": "bash",
        "action": "journalctl -n 50",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_journal_erreurs_recentes",
        "category": "linux_journal",
        "description": "Affiche les erreurs de la derniere heure",
        "triggers": ["erreurs récentes", "erreurs recentes", "erreurs système récentes"],
        "action_type": "bash",
        "action": 'journalctl -p err --since "1 hour ago"',
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_journal_logs_jarvis",
        "category": "linux_journal",
        "description": "Affiche les logs du service JARVIS",
        "triggers": ["logs du service jarvis", "logs jarvis", "journal jarvis"],
        "action_type": "bash",
        "action": "journalctl --user -u jarvis-* -n 30",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_journal_logs_boot",
        "category": "linux_journal",
        "description": "Affiche les logs du demarrage actuel",
        "triggers": ["logs du boot", "logs de démarrage", "journal du boot"],
        "action_type": "bash",
        "action": "journalctl -b",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_journal_cherche_logs",
        "category": "linux_journal",
        "description": "Cherche un terme dans les logs systeme",
        "triggers": ["cherche dans les logs {terme}", "recherche dans les logs {terme}"],
        "action_type": "bash",
        "action": "journalctl --grep={terme}",
        "params": '["terme"]',
        "confirm": 0,
    },

    # ── 2. linux_package_manager.py ──
    {
        "name": "linux_pkg_liste_paquets",
        "category": "linux_packages",
        "description": "Compte les paquets installes",
        "triggers": ["liste les paquets installés", "nombre de paquets", "paquets installés"],
        "action_type": "bash",
        "action": "dpkg --get-selections | wc -l",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_pkg_cherche_paquet",
        "category": "linux_packages",
        "description": "Recherche un paquet dans les depots",
        "triggers": ["cherche le paquet {nom}", "recherche le paquet {nom}"],
        "action_type": "bash",
        "action": "apt search {nom}",
        "params": '["nom"]',
        "confirm": 0,
    },
    {
        "name": "linux_pkg_installe",
        "category": "linux_packages",
        "description": "Installe un paquet via apt",
        "triggers": ["installe {paquet}", "installe le paquet {paquet}"],
        "action_type": "bash",
        "action": "sudo apt install -y {paquet}",
        "params": '["paquet"]',
        "confirm": 1,
    },
    {
        "name": "linux_pkg_supprime",
        "category": "linux_packages",
        "description": "Supprime un paquet via apt",
        "triggers": ["supprime {paquet}", "supprime le paquet {paquet}", "désinstalle {paquet}"],
        "action_type": "bash",
        "action": "sudo apt remove {paquet}",
        "params": '["paquet"]',
        "confirm": 1,
    },
    {
        "name": "linux_pkg_snap_liste",
        "category": "linux_packages",
        "description": "Liste les paquets snap installes",
        "triggers": ["paquets snap installés", "liste des snaps", "snap list"],
        "action_type": "bash",
        "action": "snap list",
        "params": "[]",
        "confirm": 0,
    },

    # ── 3. linux_update_manager.py ──
    {
        "name": "linux_update_disponibles",
        "category": "linux_updates",
        "description": "Liste les mises a jour disponibles",
        "triggers": ["mises à jour disponibles", "mises a jour disponibles", "updates disponibles"],
        "action_type": "bash",
        "action": "apt list --upgradable",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_update_systeme",
        "category": "linux_updates",
        "description": "Met a jour le systeme complet",
        "triggers": ["mets à jour le système", "mets a jour le systeme", "update système"],
        "action_type": "bash",
        "action": "sudo apt update && sudo apt upgrade -y",
        "params": "[]",
        "confirm": 1,
    },
    {
        "name": "linux_update_snaps",
        "category": "linux_updates",
        "description": "Met a jour les paquets snap",
        "triggers": ["mets à jour les snaps", "mets a jour les snaps", "snap refresh"],
        "action_type": "bash",
        "action": "sudo snap refresh",
        "params": "[]",
        "confirm": 1,
    },
    {
        "name": "linux_update_historique",
        "category": "linux_updates",
        "description": "Affiche l'historique des mises a jour",
        "triggers": ["historique des mises à jour", "historique des mises a jour", "historique updates"],
        "action_type": "bash",
        "action": "tail -50 /var/log/dpkg.log",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_update_reboot_requis",
        "category": "linux_updates",
        "description": "Verifie si un redemarrage est necessaire",
        "triggers": ["redémarre si nécessaire", "reboot nécessaire", "redémarrage requis"],
        "action_type": "bash",
        "action": "cat /var/run/reboot-required 2>/dev/null || echo 'Aucun redemarrage requis'",
        "params": "[]",
        "confirm": 0,
    },

    # ── 4. linux_security_status.py ──
    {
        "name": "linux_sec_parefeu",
        "category": "linux_security",
        "description": "Affiche l'etat du pare-feu UFW",
        "triggers": ["état du pare-feu", "etat du pare-feu", "statut ufw", "firewall status"],
        "action_type": "bash",
        "action": "sudo ufw status verbose",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_sec_tentatives_connexion",
        "category": "linux_security",
        "description": "Affiche les tentatives de connexion bloquees",
        "triggers": ["tentatives de connexion", "fail2ban status", "connexions bloquées"],
        "action_type": "bash",
        "action": "sudo fail2ban-client status",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_sec_scan_antivirus",
        "category": "linux_security",
        "description": "Lance un scan antivirus ClamAV",
        "triggers": ["scan antivirus", "lance un scan", "clamscan"],
        "action_type": "bash",
        "action": "clamscan --recursive /home/turbo",
        "params": "[]",
        "confirm": 1,
    },
    {
        "name": "linux_sec_apparmor",
        "category": "linux_security",
        "description": "Affiche l'etat des profils AppArmor",
        "triggers": ["état apparmor", "etat apparmor", "statut apparmor"],
        "action_type": "bash",
        "action": "sudo aa-status",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_sec_ports_ouverts",
        "category": "linux_security",
        "description": "Liste les ports ouverts en ecoute",
        "triggers": ["ports ouverts", "ports en écoute", "ports en ecoute"],
        "action_type": "bash",
        "action": "ss -tlnp",
        "params": "[]",
        "confirm": 0,
    },

    # ── 5. linux_power_manager.py ──
    {
        "name": "linux_power_profil",
        "category": "linux_power",
        "description": "Affiche le profil d'energie actuel",
        "triggers": ["profil d'énergie", "profil d'energie", "profil énergétique"],
        "action_type": "bash",
        "action": "powerprofilesctl get",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_power_performance",
        "category": "linux_power",
        "description": "Active le mode performance",
        "triggers": ["mode performance", "active le mode performance", "performance maximale"],
        "action_type": "bash",
        "action": "powerprofilesctl set performance",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_power_economie",
        "category": "linux_power",
        "description": "Active le mode economie d'energie",
        "triggers": ["mode économie", "mode economie", "économie d'énergie", "power saver"],
        "action_type": "bash",
        "action": "powerprofilesctl set power-saver",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_power_ventilateurs",
        "category": "linux_power",
        "description": "Affiche l'etat des ventilateurs",
        "triggers": ["état des ventilateurs", "etat des ventilateurs", "vitesse ventilateurs"],
        "action_type": "bash",
        "action": "sensors | grep -i fan",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_power_temperature",
        "category": "linux_power",
        "description": "Affiche la temperature du processeur",
        "triggers": ["température processeur", "temperature processeur", "température cpu", "temp cpu"],
        "action_type": "bash",
        "action": "sensors | grep Core",
        "params": "[]",
        "confirm": 0,
    },

    # ── 6. linux_config_manager.py ──
    {
        "name": "linux_config_theme_sombre",
        "category": "linux_config",
        "description": "Active le theme sombre GNOME",
        "triggers": ["thème sombre", "theme sombre", "mode sombre", "dark mode"],
        "action_type": "bash",
        "action": "gsettings set org.gnome.desktop.interface color-scheme prefer-dark",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_config_theme_clair",
        "category": "linux_config",
        "description": "Active le theme clair GNOME",
        "triggers": ["thème clair", "theme clair", "mode clair", "light mode"],
        "action_type": "bash",
        "action": "gsettings set org.gnome.desktop.interface color-scheme prefer-light",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_config_taille_texte",
        "category": "linux_config",
        "description": "Affiche le facteur de mise a l'echelle du texte",
        "triggers": ["taille du texte", "échelle du texte", "scaling texte"],
        "action_type": "bash",
        "action": "gsettings get org.gnome.desktop.interface text-scaling-factor",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_config_veilleuse_on",
        "category": "linux_config",
        "description": "Active la veilleuse (filtre bleu)",
        "triggers": ["active la veilleuse", "veilleuse on", "filtre bleu"],
        "action_type": "bash",
        "action": "gsettings set org.gnome.settings-daemon.plugins.color night-light-enabled true",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_config_veilleuse_off",
        "category": "linux_config",
        "description": "Desactive la veilleuse",
        "triggers": ["désactive la veilleuse", "desactive la veilleuse", "veilleuse off"],
        "action_type": "bash",
        "action": "gsettings set org.gnome.settings-daemon.plugins.color night-light-enabled false",
        "params": "[]",
        "confirm": 0,
    },

    # ── 7. linux_swap_manager.py ──
    {
        "name": "linux_swap_etat",
        "category": "linux_swap",
        "description": "Affiche l'etat du swap",
        "triggers": ["état du swap", "etat du swap", "swap status"],
        "action_type": "bash",
        "action": "swapon --show",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_swap_memoire_dispo",
        "category": "linux_swap",
        "description": "Affiche la memoire disponible",
        "triggers": ["mémoire disponible", "memoire disponible", "free memory", "ram disponible"],
        "action_type": "bash",
        "action": "free -h",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_swap_zram",
        "category": "linux_swap",
        "description": "Affiche l'etat du zram",
        "triggers": ["état zram", "etat zram", "zram status"],
        "action_type": "bash",
        "action": "zramctl",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_swap_vide",
        "category": "linux_swap",
        "description": "Vide et reactive le swap",
        "triggers": ["vide le swap", "flush swap", "reset swap"],
        "action_type": "bash",
        "action": "sudo swapoff -a && sudo swapon -a",
        "params": "[]",
        "confirm": 1,
    },
    {
        "name": "linux_swap_memoire_detail",
        "category": "linux_swap",
        "description": "Affiche les details de la memoire",
        "triggers": ["utilisation mémoire détaillée", "utilisation memoire detaillee", "meminfo"],
        "action_type": "bash",
        "action": "head -20 /proc/meminfo",
        "params": "[]",
        "confirm": 0,
    },

    # ── 8. linux_trash_manager.py ──
    {
        "name": "linux_trash_vide",
        "category": "linux_trash",
        "description": "Vide la corbeille",
        "triggers": ["vide la corbeille", "corbeille vide", "empty trash"],
        "action_type": "bash",
        "action": "gio trash --empty",
        "params": "[]",
        "confirm": 1,
    },
    {
        "name": "linux_trash_taille",
        "category": "linux_trash",
        "description": "Affiche la taille de la corbeille",
        "triggers": ["taille de la corbeille", "poids corbeille", "trash size"],
        "action_type": "bash",
        "action": "du -sh ~/.local/share/Trash/ 2>/dev/null || echo 'Corbeille vide'",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_trash_contenu",
        "category": "linux_trash",
        "description": "Liste le contenu de la corbeille",
        "triggers": ["contenu corbeille", "liste corbeille", "trash list"],
        "action_type": "bash",
        "action": "gio trash --list",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_trash_restaure_info",
        "category": "linux_trash",
        "description": "Infos sur la restauration depuis la corbeille",
        "triggers": ["restaure depuis la corbeille", "restaurer corbeille"],
        "action_type": "bash",
        "action": "echo 'Utilisez: gio trash --restore FICHIER pour restaurer un element. Listez avec: gio trash --list'",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_trash_fichiers_temp",
        "category": "linux_trash",
        "description": "Supprime les fichiers temporaires JARVIS",
        "triggers": ["supprime les fichiers temporaires", "clean temp", "nettoie les temporaires"],
        "action_type": "bash",
        "action": "rm -rf /tmp/jarvis-* && echo 'Fichiers temporaires supprimes'",
        "params": "[]",
        "confirm": 1,
    },

    # ── 9. linux_snapshot_manager.py ──
    {
        "name": "linux_snap_cree",
        "category": "linux_snapshots",
        "description": "Cree un snapshot systeme via timeshift",
        "triggers": ["crée un snapshot", "cree un snapshot", "nouveau snapshot"],
        "action_type": "bash",
        "action": "sudo timeshift --create --comments 'Snapshot JARVIS' --yes",
        "params": "[]",
        "confirm": 1,
    },
    {
        "name": "linux_snap_liste",
        "category": "linux_snapshots",
        "description": "Liste les snapshots disponibles",
        "triggers": ["liste les snapshots", "snapshots disponibles", "timeshift list"],
        "action_type": "bash",
        "action": "sudo timeshift --list",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_snap_restaure_info",
        "category": "linux_snapshots",
        "description": "Info sur la restauration de snapshot",
        "triggers": ["restaure un snapshot", "restore snapshot"],
        "action_type": "bash",
        "action": "echo 'ATTENTION: La restauration necessite une confirmation manuelle. Utilisez: sudo timeshift --restore'",
        "params": "[]",
        "confirm": 1,
    },
    {
        "name": "linux_snap_supprime_vieux",
        "category": "linux_snapshots",
        "description": "Supprime les anciens snapshots",
        "triggers": ["supprime les vieux snapshots", "nettoie les snapshots", "delete old snapshots"],
        "action_type": "bash",
        "action": "sudo timeshift --delete",
        "params": "[]",
        "confirm": 1,
    },
    {
        "name": "linux_snap_espace",
        "category": "linux_snapshots",
        "description": "Affiche l'espace utilise par les volumes logiques",
        "triggers": ["espace snapshots", "espace lvm", "taille snapshots"],
        "action_type": "bash",
        "action": "sudo lvs 2>/dev/null || echo 'LVM non configure - Utilisation de timeshift' && sudo timeshift --list 2>/dev/null | head -5",
        "params": "[]",
        "confirm": 0,
    },

    # ── 10. linux_workspace_manager.py ──
    {
        "name": "linux_ws_suivant",
        "category": "linux_workspace",
        "description": "Passe au bureau virtuel suivant",
        "triggers": ["bureau suivant", "workspace suivant", "next desktop"],
        "action_type": "bash",
        "action": "wmctrl -s $(expr $(wmctrl -d | grep '*' | cut -d' ' -f1) + 1)",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_ws_precedent",
        "category": "linux_workspace",
        "description": "Passe au bureau virtuel precedent",
        "triggers": ["bureau précédent", "bureau precedent", "workspace précédent", "previous desktop"],
        "action_type": "bash",
        "action": "wmctrl -s $(expr $(wmctrl -d | grep '*' | cut -d' ' -f1) - 1)",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_ws_liste",
        "category": "linux_workspace",
        "description": "Liste les bureaux virtuels",
        "triggers": ["liste les bureaux", "bureaux virtuels", "workspaces"],
        "action_type": "bash",
        "action": "wmctrl -d",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_ws_deplace_fenetre",
        "category": "linux_workspace",
        "description": "Deplace la fenetre active au bureau 2",
        "triggers": ["déplace fenêtre au bureau 2", "deplace fenetre au bureau 2", "move window to desktop 2"],
        "action_type": "bash",
        "action": "wmctrl -r :ACTIVE: -t 1",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_ws_nombre",
        "category": "linux_workspace",
        "description": "Affiche le nombre de bureaux virtuels",
        "triggers": ["nombre de bureaux", "combien de bureaux", "workspaces count"],
        "action_type": "bash",
        "action": "gsettings get org.gnome.desktop.wm.preferences num-workspaces",
        "params": "[]",
        "confirm": 0,
    },

    # ── 11. linux_share_manager.py ──
    {
        "name": "linux_share_liste",
        "category": "linux_share",
        "description": "Liste les partages reseau Samba",
        "triggers": ["partages réseau", "partages reseau", "samba shares", "network shares"],
        "action_type": "bash",
        "action": "net usershare list",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_share_monte_info",
        "category": "linux_share",
        "description": "Info sur le montage de partage SMB",
        "triggers": ["monte un partage", "monter un partage", "mount share"],
        "action_type": "bash",
        "action": "echo 'Utilisez: smbclient //SERVEUR/PARTAGE -U utilisateur pour se connecter a un partage SMB'",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_share_nfs",
        "category": "linux_share",
        "description": "Liste les exports NFS locaux",
        "triggers": ["partages NFS", "partages nfs", "exports nfs", "nfs shares"],
        "action_type": "bash",
        "action": "showmount -e 127.0.0.1",
        "params": "[]",
        "confirm": 0,
    },
    {
        "name": "linux_share_deconnecte",
        "category": "linux_share",
        "description": "Demonte les partages CIFS et NFS",
        "triggers": ["déconnecte les partages", "deconnecte les partages", "unmount shares"],
        "action_type": "bash",
        "action": "umount -t cifs,nfs -a 2>/dev/null && echo 'Partages deconnectes' || echo 'Aucun partage a deconnecter'",
        "params": "[]",
        "confirm": 1,
    },
    {
        "name": "linux_share_ssh_actives",
        "category": "linux_share",
        "description": "Affiche les connexions SSH actives",
        "triggers": ["connexions SSH actives", "connexions ssh actives", "ssh connections"],
        "action_type": "bash",
        "action": "ss -tn state established | grep :22",
        "params": "[]",
        "confirm": 0,
    },
]


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    inserted = 0
    skipped = 0
    errors = 0

    for cmd in LINUX_COMMANDS:
        triggers_json = json.dumps(cmd["triggers"], ensure_ascii=False)
        try:
            cursor.execute(
                """INSERT OR IGNORE INTO voice_commands
                   (name, category, description, triggers, action_type, action, params, confirm, enabled, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                (
                    cmd["name"],
                    cmd["category"],
                    cmd["description"],
                    triggers_json,
                    cmd["action_type"],
                    cmd["action"],
                    cmd["params"],
                    cmd["confirm"],
                    time.time(),
                ),
            )
            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except sqlite3.Error as e:
            print(f"  ERREUR pour {cmd['name']}: {e}")
            errors += 1

    conn.commit()

    # Verification du total
    total = cursor.execute("SELECT COUNT(*) FROM voice_commands").fetchone()[0]
    linux_count = cursor.execute(
        "SELECT COUNT(*) FROM voice_commands WHERE category LIKE 'linux_%'"
    ).fetchone()[0]

    conn.close()

    print(f"=== Insertion des commandes vocales Linux ===")
    print(f"  Inserees  : {inserted}")
    print(f"  Ignorees  : {skipped} (deja presentes)")
    print(f"  Erreurs   : {errors}")
    print(f"  Total commandes Linux dans la DB : {linux_count}")
    print(f"  Total commandes dans la DB       : {total}")


if __name__ == "__main__":
    main()
