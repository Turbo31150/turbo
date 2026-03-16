"""Linux Hotkey Daemon — Raccourcis clavier globaux synchronises avec les commandes vocales.

Daemon qui gere les raccourcis clavier JARVIS via gsettings (methode GNOME native).
Les raccourcis executent les memes skills que les commandes vocales, assurant
une synchronisation complete entre les deux modes d'interaction.

Architecture :
  - Les raccourcis sont enregistres via gsettings/dconf (custom-keybindings)
  - Chaque raccourci appelle execute_skill.sh qui execute le skill JARVIS
  - Le daemon surveille les changements de skills et met a jour les raccourcis
  - Compatible GNOME Shell / Cinnamon / Budgie (tout DE base sur gsettings)

Usage :
  python3 src/linux_hotkey_daemon.py [--install] [--status] [--list] [--sync]
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.hotkey_daemon")

# Repertoire racine de JARVIS
JARVIS_HOME = Path(__file__).resolve().parent.parent
SKILL_SCRIPT = JARVIS_HOME / "scripts" / "execute_skill.sh"
LOG_FILE = JARVIS_HOME / "logs" / "hotkey_daemon.log"

# Chemin dconf pour les custom keybindings GNOME
KEYBINDING_BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
KEYBINDING_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
MEDIA_KEYS_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"

# Offset pour les keybindings JARVIS (custom100+) — evite les conflits
CUSTOM_OFFSET = 100


@dataclass
class HotkeyBinding:
    """Definition d'un raccourci clavier JARVIS."""
    name: str                # Nom affiche dans les parametres GNOME
    binding: str             # Combinaison de touches (format GSettings: <Super>1)
    skill_name: str          # Nom du skill JARVIS a executer
    command: str = ""        # Commande a executer (generee automatiquement)
    category: str = "skill"  # Type : skill, url, app
    enabled: bool = True
    usage_count: int = 0
    last_used: float = 0.0


# Raccourcis predefinis — synchronises avec les commandes vocales
PREDEFINED_HOTKEYS: list[HotkeyBinding] = [
    HotkeyBinding(
        name="JARVIS Rapport Systeme",
        binding="<Super>1",
        skill_name="rapport_systeme_linux",
        category="skill",
    ),
    HotkeyBinding(
        name="JARVIS Maintenance Complete",
        binding="<Super>2",
        skill_name="maintenance_complete_linux",
        category="skill",
    ),
    HotkeyBinding(
        name="JARVIS Diagnostic Reseau",
        binding="<Super>3",
        skill_name="diagnostic_reseau_linux",
        category="skill",
    ),
    HotkeyBinding(
        name="JARVIS Cluster Check",
        binding="<Super>4",
        skill_name="cluster_check_linux",
        category="skill",
    ),
    HotkeyBinding(
        name="JARVIS Mode Dev",
        binding="<Super>5",
        skill_name="mode_dev_linux",
        category="skill",
    ),
    HotkeyBinding(
        name="JARVIS Doc Vocale",
        binding="<Super>F1",
        skill_name="",
        command=f"xdg-open {JARVIS_HOME}/docs/voice_commands_reference.html",
        category="app",
    ),
    HotkeyBinding(
        name="JARVIS Dashboard",
        binding="<Super>F2",
        skill_name="",
        command="xdg-open http://127.0.0.1:8088",
        category="url",
    ),
    HotkeyBinding(
        name="JARVIS Nettoyage Profond",
        binding="<Super>F5",
        skill_name="nettoyage_profond_linux",
        category="skill",
    ),
    HotkeyBinding(
        name="JARVIS Self Diagnostic",
        binding="<Super>F12",
        skill_name="jarvis_self_diagnostic",
        category="skill",
    ),
    HotkeyBinding(
        name="JARVIS Focus Mode",
        binding="<Super>Escape",
        skill_name="focus_mode_linux",
        category="skill",
    ),
]

# Raccourcis pre-existants (informatif, pas geres par ce daemon)
EXISTING_HOTKEYS = {
    "<Super>j": "Pipeline vocal",
    "<Super>g": "GPU monitor",
}


def _run_gsettings(args: list[str], timeout: int = 10) -> tuple[bool, str]:
    """Execute une commande gsettings et retourne (success, output)."""
    try:
        result = subprocess.run(
            ["gsettings"] + args,
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except FileNotFoundError:
        return False, "gsettings non trouve — GNOME non installe?"
    except subprocess.TimeoutExpired:
        return False, "gsettings timeout"
    except OSError as e:
        return False, f"Erreur OS: {e}"


def _get_custom_path(index: int) -> str:
    """Retourne le chemin dconf pour un custom keybinding."""
    return f"{KEYBINDING_BASE}/custom{CUSTOM_OFFSET + index}/"


def _build_command(hotkey: HotkeyBinding) -> str:
    """Construit la commande a executer pour un raccourci."""
    if hotkey.command:
        return hotkey.command
    if hotkey.skill_name:
        return f"{SKILL_SCRIPT} {hotkey.skill_name}"
    return ""


def get_existing_keybindings() -> list[str]:
    """Recupere la liste des keybindings custom existants."""
    ok, output = _run_gsettings([
        "get", MEDIA_KEYS_SCHEMA, "custom-keybindings"
    ])
    if not ok or output in ("@as []", "[]"):
        return []

    # Parser la sortie GVariant — format: ['path1', 'path2', ...]
    cleaned = output.replace("@as ", "").strip("[]")
    if not cleaned:
        return []

    paths = []
    for part in cleaned.split(","):
        part = part.strip().strip("'\"")
        if part:
            paths.append(part)
    return paths


def install_hotkeys(hotkeys: list[HotkeyBinding] | None = None) -> dict[str, Any]:
    """Installe les raccourcis clavier via gsettings.

    Methode idempotente : peut etre appelee plusieurs fois sans effet secondaire.
    Retourne un rapport d'installation.
    """
    if hotkeys is None:
        hotkeys = PREDEFINED_HOTKEYS

    # S'assurer que le script execute_skill.sh est executable
    if SKILL_SCRIPT.exists():
        SKILL_SCRIPT.chmod(0o755)

    report = {
        "installed": [],
        "errors": [],
        "total": len(hotkeys),
        "success": 0,
    }

    # Recuperer les keybindings existants
    existing = get_existing_keybindings()

    # Filtrer les anciens raccourcis JARVIS (custom100-custom199)
    filtered = [
        p for p in existing
        if not any(f"/custom{i}/" in p for i in range(CUSTOM_OFFSET, CUSTOM_OFFSET + 100))
    ]

    # Ajouter nos raccourcis
    for i, hotkey in enumerate(hotkeys):
        if not hotkey.enabled:
            continue
        path = _get_custom_path(i)
        if path not in filtered:
            filtered.append(path)

    # Enregistrer la liste complete
    paths_str = "[" + ", ".join(f"'{p}'" for p in filtered) + "]"
    ok, err = _run_gsettings([
        "set", MEDIA_KEYS_SCHEMA, "custom-keybindings", paths_str
    ])
    if not ok:
        report["errors"].append(f"Echec enregistrement liste: {err}")
        return report

    # Configurer chaque raccourci
    for i, hotkey in enumerate(hotkeys):
        if not hotkey.enabled:
            continue

        path = _get_custom_path(i)
        schema_path = f"{KEYBINDING_SCHEMA}:{path}"
        command = _build_command(hotkey)

        errors = []
        for key, value in [("name", hotkey.name), ("command", command), ("binding", hotkey.binding)]:
            ok, err = _run_gsettings(["set", schema_path, key, value])
            if not ok:
                errors.append(f"{key}: {err}")

        if errors:
            report["errors"].append(f"{hotkey.binding}: {'; '.join(errors)}")
        else:
            report["installed"].append({
                "binding": hotkey.binding,
                "name": hotkey.name,
                "skill": hotkey.skill_name or "(custom)",
            })
            report["success"] += 1

    return report


def uninstall_hotkeys() -> dict[str, Any]:
    """Supprime tous les raccourcis JARVIS de gsettings."""
    existing = get_existing_keybindings()

    # Filtrer les raccourcis JARVIS
    cleaned = [
        p for p in existing
        if not any(f"/custom{i}/" in p for i in range(CUSTOM_OFFSET, CUSTOM_OFFSET + 100))
    ]

    paths_str = "[" + ", ".join(f"'{p}'" for p in cleaned) + "]"
    ok, err = _run_gsettings([
        "set", MEDIA_KEYS_SCHEMA, "custom-keybindings", paths_str
    ])

    return {
        "removed": len(existing) - len(cleaned),
        "remaining": len(cleaned),
        "success": ok,
        "error": err if not ok else None,
    }


def get_status() -> dict[str, Any]:
    """Retourne le statut actuel des raccourcis installes."""
    existing = get_existing_keybindings()

    # Compter les raccourcis JARVIS
    jarvis_paths = [
        p for p in existing
        if any(f"/custom{i}/" in p for i in range(CUSTOM_OFFSET, CUSTOM_OFFSET + 100))
    ]

    # Lire les details de chaque raccourci JARVIS
    hotkeys_info = []
    for path in jarvis_paths:
        schema_path = f"{KEYBINDING_SCHEMA}:{path}"
        info = {}
        for key in ("name", "command", "binding"):
            ok, val = _run_gsettings(["get", schema_path, key])
            info[key] = val.strip("'") if ok else "?"
        hotkeys_info.append(info)

    return {
        "total_custom": len(existing),
        "jarvis_count": len(jarvis_paths),
        "hotkeys": hotkeys_info,
        "existing_shortcuts": EXISTING_HOTKEYS,
    }


def list_hotkeys() -> str:
    """Affiche la liste des raccourcis en format lisible."""
    lines = ["=== JARVIS Hotkeys ===", ""]

    # Raccourcis geres par le daemon
    lines.append("Raccourcis dynamiques (geres par le daemon) :")
    for hotkey in PREDEFINED_HOTKEYS:
        status = "ON" if hotkey.enabled else "OFF"
        target = hotkey.skill_name or hotkey.command
        lines.append(f"  [{status}] {hotkey.binding:20s} -> {hotkey.name} ({target})")

    lines.append("")
    lines.append("Raccourcis pre-existants (non geres) :")
    for binding, desc in EXISTING_HOTKEYS.items():
        lines.append(f"        {binding:20s} -> {desc}")

    return "\n".join(lines)


def sync_with_skills() -> dict[str, Any]:
    """Synchronise les raccourcis avec les skills disponibles.

    Verifie que tous les skills references par les raccourcis existent
    et desactive les raccourcis dont le skill n'existe plus.
    """
    sys.path.insert(0, str(JARVIS_HOME))
    from src.skills import load_skills

    skills = load_skills()
    skill_names = {s.name for s in skills}

    sync_report = {"valid": [], "missing": [], "updated": 0}

    for hotkey in PREDEFINED_HOTKEYS:
        if hotkey.category != "skill":
            continue
        if hotkey.skill_name in skill_names:
            sync_report["valid"].append(hotkey.skill_name)
        else:
            sync_report["missing"].append(hotkey.skill_name)
            logger.warning(
                "Skill '%s' reference par raccourci '%s' introuvable",
                hotkey.skill_name, hotkey.binding,
            )

    return sync_report


def add_dynamic_hotkey(
    binding: str,
    skill_name: str,
    name: str | None = None,
) -> dict[str, Any]:
    """Ajoute un raccourci dynamique pour un skill existant.

    Permet d'etendre les raccourcis au-dela des predefinis.
    """
    if name is None:
        name = f"JARVIS {skill_name}"

    new_hotkey = HotkeyBinding(
        name=name,
        binding=binding,
        skill_name=skill_name,
        category="skill",
    )

    # Ajouter aux predefinis et reinstaller
    PREDEFINED_HOTKEYS.append(new_hotkey)
    report = install_hotkeys()

    return {
        "added": {"binding": binding, "skill": skill_name, "name": name},
        "install_report": report,
    }


def _setup_logging():
    """Configure le logging pour le daemon."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main():
    """Point d'entree CLI du daemon."""
    import argparse

    parser = argparse.ArgumentParser(
        description="JARVIS Linux Hotkey Daemon — Raccourcis clavier globaux",
    )
    parser.add_argument(
        "--install", action="store_true",
        help="Installer les raccourcis clavier via gsettings",
    )
    parser.add_argument(
        "--uninstall", action="store_true",
        help="Supprimer tous les raccourcis JARVIS",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Afficher le statut des raccourcis installes",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="Lister tous les raccourcis disponibles",
    )
    parser.add_argument(
        "--sync", action="store_true",
        help="Synchroniser les raccourcis avec les skills disponibles",
    )
    parser.add_argument(
        "--daemon", action="store_true",
        help="Lancer le daemon de surveillance (surveille les changements de skills)",
    )

    args = parser.parse_args()
    _setup_logging()

    if args.install:
        logger.info("Installation des raccourcis clavier JARVIS...")
        report = install_hotkeys()
        print(f"\nInstallation terminee: {report['success']}/{report['total']} raccourcis")
        for item in report["installed"]:
            print(f"  [OK] {item['binding']} -> {item['name']}")
        for err in report["errors"]:
            print(f"  [ERREUR] {err}")
        return

    if args.uninstall:
        logger.info("Suppression des raccourcis JARVIS...")
        report = uninstall_hotkeys()
        print(f"Supprime: {report['removed']} raccourcis")
        return

    if args.status:
        status = get_status()
        print(f"Raccourcis custom totaux: {status['total_custom']}")
        print(f"Raccourcis JARVIS: {status['jarvis_count']}")
        for hk in status["hotkeys"]:
            print(f"  {hk.get('binding', '?'):20s} -> {hk.get('name', '?')}")
        return

    if args.list:
        print(list_hotkeys())
        return

    if args.sync:
        logger.info("Synchronisation avec les skills...")
        report = sync_with_skills()
        print(f"Skills valides: {len(report['valid'])}")
        print(f"Skills manquants: {len(report['missing'])}")
        for name in report["missing"]:
            print(f"  [MANQUANT] {name}")
        return

    if args.daemon:
        logger.info("Demarrage du daemon de surveillance des raccourcis...")
        _run_daemon()
        return

    # Par defaut : afficher l'aide
    parser.print_help()


def _run_daemon():
    """Boucle de surveillance : reinstalle les raccourcis si les skills changent."""
    from src.skills import SKILLS_FILE

    logger.info("Daemon hotkey demarre — surveillance de %s", SKILLS_FILE)

    last_mtime = 0.0
    # Installation initiale
    install_hotkeys()

    while True:
        try:
            if SKILLS_FILE.exists():
                current_mtime = SKILLS_FILE.stat().st_mtime
                if current_mtime != last_mtime:
                    last_mtime = current_mtime
                    logger.info("Changement detecte dans skills.json — synchronisation...")
                    sync_report = sync_with_skills()
                    if sync_report["missing"]:
                        logger.warning(
                            "Skills manquants: %s",
                            ", ".join(sync_report["missing"]),
                        )
            time.sleep(30)  # Verifier toutes les 30 secondes
        except KeyboardInterrupt:
            logger.info("Daemon arrete par l'utilisateur")
            break
        except Exception as e:
            logger.error("Erreur daemon: %s", e)
            time.sleep(60)


if __name__ == "__main__":
    main()
