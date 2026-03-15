#!/usr/bin/env python3
"""voice_aliases.py — Raccourcis vocaux ultra-courts pour JARVIS.

Permet de transformer des mots/phrases tres courts en commandes completes,
skills, ou actions bash. Persistance JSON + integration dans le voice_router.

Usage:
    python src/voice_aliases.py --list
    python src/voice_aliases.py --resolve "chaud"
    python src/voice_aliases.py --search "gpu"
    python src/voice_aliases.py --add "mon alias" "ma commande complete"
    python src/voice_aliases.py --remove "mon alias"
    python src/voice_aliases.py --init-db
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Garantir que le dossier racine jarvis est dans le PYTHONPATH
_jarvis_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _jarvis_root not in sys.path:
    sys.path.insert(0, _jarvis_root)

logger = logging.getLogger(__name__)

# Chemin du fichier de persistance
ALIASES_FILE = Path(_jarvis_root) / "data" / "voice_aliases.json"
DB_PATH = Path(_jarvis_root) / "data" / "jarvis.db"


# ---------------------------------------------------------------------------
# Categories d'aliases pour organisation
# ---------------------------------------------------------------------------
CATEGORY_SYSTEM = "system"
CATEGORY_NETWORK = "network"
CATEGORY_GPU = "gpu"
CATEGORY_DISK = "disk"
CATEGORY_SECURITY = "security"
CATEGORY_PROCESS = "process"
CATEGORY_DEV = "dev"
CATEGORY_GIT = "git"
CATEGORY_DOCKER = "docker"
CATEGORY_AUDIO = "audio"
CATEGORY_JARVIS = "jarvis"
CATEGORY_TRADING = "trading"
CATEGORY_MONITOR = "monitor"
CATEGORY_SERVICE = "service"
CATEGORY_CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Structure d'un alias
# ---------------------------------------------------------------------------
@dataclass
class VoiceAlias:
    """Un raccourci vocal."""

    short: str                              # Mot/phrase court(e)
    full: str                               # Commande/skill complete
    category: str = CATEGORY_CUSTOM         # Categorie
    action_type: str = "skill"              # skill | bash | compound
    description: str = ""                   # Description courte
    usage_count: int = 0                    # Nombre d'utilisations
    last_used: float = 0.0                  # Timestamp derniere utilisation
    enabled: bool = True                    # Actif ou desactive

    def to_dict(self) -> dict[str, Any]:
        """Serialise en dict pour JSON."""
        return {
            "short": self.short,
            "full": self.full,
            "category": self.category,
            "action_type": self.action_type,
            "description": self.description,
            "usage_count": self.usage_count,
            "last_used": self.last_used,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoiceAlias:
        """Deserialise depuis un dict."""
        return cls(
            short=data["short"],
            full=data["full"],
            category=data.get("category", CATEGORY_CUSTOM),
            action_type=data.get("action_type", "skill"),
            description=data.get("description", ""),
            usage_count=data.get("usage_count", 0),
            last_used=data.get("last_used", 0.0),
            enabled=data.get("enabled", True),
        )


# ---------------------------------------------------------------------------
# 100 aliases predefinis
# ---------------------------------------------------------------------------
DEFAULT_ALIASES: list[dict[str, Any]] = [
    # === JARVIS / Diagnostics (10) ===
    {"short": "ça va", "full": "jarvis_self_diagnostic", "category": CATEGORY_JARVIS, "action_type": "skill", "description": "Auto-diagnostic JARVIS complet"},
    {"short": "quoi de neuf", "full": "rapport_systeme_linux", "category": CATEGORY_JARVIS, "action_type": "skill", "description": "Rapport systeme global"},
    {"short": "santé", "full": "health_summary", "category": CATEGORY_JARVIS, "action_type": "skill", "description": "Resume sante du systeme"},
    {"short": "état", "full": "diagnostics_quick", "category": CATEGORY_JARVIS, "action_type": "skill", "description": "Diagnostic rapide"},
    {"short": "version", "full": "cat /home/turbo/jarvis/VERSION 2>/dev/null || echo 'JARVIS v12.4'", "category": CATEGORY_JARVIS, "action_type": "bash", "description": "Version JARVIS"},
    {"short": "boot", "full": "jarvis_boot_status", "category": CATEGORY_JARVIS, "action_type": "skill", "description": "Statut de demarrage JARVIS"},
    {"short": "aide", "full": "list_skills", "category": CATEGORY_JARVIS, "action_type": "skill", "description": "Liste des skills disponibles"},
    {"short": "rappel", "full": "memory_list", "category": CATEGORY_JARVIS, "action_type": "skill", "description": "Liste des souvenirs JARVIS"},
    {"short": "cerveau", "full": "brain_status", "category": CATEGORY_JARVIS, "action_type": "skill", "description": "Statut du brain JARVIS"},
    {"short": "apprends", "full": "brain_learn", "category": CATEGORY_JARVIS, "action_type": "skill", "description": "Apprentissage brain"},

    # === Systeme (10) ===
    {"short": "up", "full": "uptime -p", "category": CATEGORY_SYSTEM, "action_type": "bash", "description": "Uptime systeme"},
    {"short": "ram", "full": "free -h", "category": CATEGORY_SYSTEM, "action_type": "bash", "description": "Usage memoire RAM"},
    {"short": "cpu", "full": "mpstat 1 1 2>/dev/null || top -bn1 | head -5", "category": CATEGORY_SYSTEM, "action_type": "bash", "description": "Usage CPU"},
    {"short": "charge", "full": "cat /proc/loadavg", "category": CATEGORY_SYSTEM, "action_type": "bash", "description": "Load average systeme"},
    {"short": "swap", "full": "swapon --show && free -h | grep Swap", "category": CATEGORY_SYSTEM, "action_type": "bash", "description": "Usage swap"},
    {"short": "kernel", "full": "uname -r", "category": CATEGORY_SYSTEM, "action_type": "bash", "description": "Version du kernel"},
    {"short": "who", "full": "who && w", "category": CATEGORY_SYSTEM, "action_type": "bash", "description": "Utilisateurs connectes"},
    {"short": "log", "full": "journalctl --user -n 30 --no-pager", "category": CATEGORY_SYSTEM, "action_type": "bash", "description": "30 derniers logs utilisateur"},
    {"short": "err", "full": "journalctl -p err --since '1 hour ago' --no-pager -n 20", "category": CATEGORY_SYSTEM, "action_type": "bash", "description": "Erreurs de la derniere heure"},
    {"short": "date", "full": "date '+%A %d %B %Y, %H:%M:%S'", "category": CATEGORY_SYSTEM, "action_type": "bash", "description": "Date et heure actuelles"},

    # === GPU / Temperatures (10) ===
    {"short": "chaud", "full": "optimise_gpu_linux", "category": CATEGORY_GPU, "action_type": "skill", "description": "Temperatures et optimisation GPU"},
    {"short": "gpu", "full": "gpu_info", "category": CATEGORY_GPU, "action_type": "skill", "description": "Infos GPU completes"},
    {"short": "vram", "full": "nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader", "category": CATEGORY_GPU, "action_type": "bash", "description": "Usage VRAM"},
    {"short": "nvidia", "full": "nvidia-smi", "category": CATEGORY_GPU, "action_type": "bash", "description": "Dashboard nvidia-smi complet"},
    {"short": "thermal", "full": "sensors 2>/dev/null || nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader", "category": CATEGORY_GPU, "action_type": "bash", "description": "Temperatures capteurs"},
    {"short": "fan", "full": "sensors 2>/dev/null | grep -i fan || echo 'Pas de capteur fan'", "category": CATEGORY_GPU, "action_type": "bash", "description": "Vitesse ventilateurs"},
    {"short": "watts", "full": "nvidia-smi --query-gpu=power.draw --format=csv,noheader", "category": CATEGORY_GPU, "action_type": "bash", "description": "Consommation GPU en watts"},
    {"short": "clock", "full": "nvidia-smi --query-gpu=clocks.gr,clocks.mem --format=csv,noheader", "category": CATEGORY_GPU, "action_type": "bash", "description": "Frequences GPU"},
    {"short": "cuda", "full": "nvcc --version 2>/dev/null || echo 'CUDA non installe'", "category": CATEGORY_GPU, "action_type": "bash", "description": "Version CUDA"},
    {"short": "driver", "full": "nvidia-smi --query-gpu=driver_version --format=csv,noheader", "category": CATEGORY_GPU, "action_type": "bash", "description": "Version driver GPU"},

    # === Disque / Stockage (8) ===
    {"short": "place", "full": "disk_analysis_linux", "category": CATEGORY_DISK, "action_type": "skill", "description": "Analyse espace disque"},
    {"short": "df", "full": "df -h --type=ext4 --type=btrfs --type=xfs --type=tmpfs 2>/dev/null || df -h", "category": CATEGORY_DISK, "action_type": "bash", "description": "Espace disque par partition"},
    {"short": "io", "full": "iostat -x 1 1 2>/dev/null || cat /proc/diskstats | head -10", "category": CATEGORY_DISK, "action_type": "bash", "description": "I/O disque en cours"},
    {"short": "gros", "full": "du -sh /home/turbo/* 2>/dev/null | sort -rh | head -10", "category": CATEGORY_DISK, "action_type": "bash", "description": "Plus gros dossiers home"},
    {"short": "tmp", "full": "du -sh /tmp/* 2>/dev/null | sort -rh | head -10", "category": CATEGORY_DISK, "action_type": "bash", "description": "Contenu de /tmp"},
    {"short": "mount", "full": "findmnt --real --noheadings", "category": CATEGORY_DISK, "action_type": "bash", "description": "Points de montage actifs"},
    {"short": "trash", "full": "du -sh ~/.local/share/Trash/files/ 2>/dev/null || echo 'Corbeille vide'", "category": CATEGORY_DISK, "action_type": "bash", "description": "Taille de la corbeille"},
    {"short": "zap", "full": "nettoyage_profond_linux", "category": CATEGORY_DISK, "action_type": "skill", "description": "Nettoyage profond systeme"},

    # === Reseau (10) ===
    {"short": "net", "full": "diagnostic_reseau_linux", "category": CATEGORY_NETWORK, "action_type": "skill", "description": "Diagnostic reseau complet"},
    {"short": "ip", "full": "ip -br addr show", "category": CATEGORY_NETWORK, "action_type": "bash", "description": "Adresses IP locales"},
    {"short": "port", "full": "ss -tlnp", "category": CATEGORY_NETWORK, "action_type": "bash", "description": "Ports en ecoute"},
    {"short": "ping", "full": "ping -c 3 8.8.8.8", "category": CATEGORY_NETWORK, "action_type": "bash", "description": "Ping Google DNS"},
    {"short": "wifi", "full": "nmcli dev wifi list 2>/dev/null || iwconfig 2>/dev/null", "category": CATEGORY_NETWORK, "action_type": "bash", "description": "Reseaux WiFi visibles"},
    {"short": "dns", "full": "cat /etc/resolv.conf | grep nameserver", "category": CATEGORY_NETWORK, "action_type": "bash", "description": "Serveurs DNS configures"},
    {"short": "routes", "full": "ip route show", "category": CATEGORY_NETWORK, "action_type": "bash", "description": "Table de routage"},
    {"short": "speed", "full": "speedtest-cli --simple 2>/dev/null || curl -s https://raw.githubusercontent.com/sivel/speedtest-cli/master/speedtest.py | python3", "category": CATEGORY_NETWORK, "action_type": "bash", "description": "Test de vitesse internet"},
    {"short": "connexions", "full": "ss -tunp | head -20", "category": CATEGORY_NETWORK, "action_type": "bash", "description": "Connexions reseau actives"},
    {"short": "pub", "full": "curl -s ifconfig.me", "category": CATEGORY_NETWORK, "action_type": "bash", "description": "Adresse IP publique"},

    # === Securite (7) ===
    {"short": "safe", "full": "securite_audit_linux", "category": CATEGORY_SECURITY, "action_type": "skill", "description": "Audit de securite complet"},
    {"short": "fw", "full": "sudo ufw status verbose 2>/dev/null || sudo iptables -L -n 2>/dev/null | head -20", "category": CATEGORY_SECURITY, "action_type": "bash", "description": "Statut firewall"},
    {"short": "fail", "full": "sudo fail2ban-client status 2>/dev/null || echo 'fail2ban non installe'", "category": CATEGORY_SECURITY, "action_type": "bash", "description": "Statut fail2ban"},
    {"short": "auth", "full": "journalctl -u ssh --since '1 hour ago' --no-pager -n 15 2>/dev/null || tail -15 /var/log/auth.log 2>/dev/null", "category": CATEGORY_SECURITY, "action_type": "bash", "description": "Tentatives d'authentification"},
    {"short": "scan", "full": "security_scan", "category": CATEGORY_SECURITY, "action_type": "skill", "description": "Scan securite rapide"},
    {"short": "score", "full": "security_score", "category": CATEGORY_SECURITY, "action_type": "skill", "description": "Score de securite"},
    {"short": "lock", "full": "loginctl lock-session", "category": CATEGORY_SECURITY, "action_type": "bash", "description": "Verrouiller l'ecran"},

    # === Processus (5) ===
    {"short": "top", "full": "ps aux --sort=-%cpu | head -12", "category": CATEGORY_PROCESS, "action_type": "bash", "description": "Top processus CPU"},
    {"short": "mem", "full": "ps aux --sort=-%mem | head -12", "category": CATEGORY_PROCESS, "action_type": "bash", "description": "Top processus memoire"},
    {"short": "kill", "full": "list_processes", "category": CATEGORY_PROCESS, "action_type": "skill", "description": "Liste processus pour kill"},
    {"short": "zombie", "full": "ps aux | grep -w Z | grep -v grep || echo 'Pas de zombie'", "category": CATEGORY_PROCESS, "action_type": "bash", "description": "Processus zombies"},
    {"short": "jobs", "full": "systemctl --user list-units --type=service --state=running --no-pager", "category": CATEGORY_PROCESS, "action_type": "bash", "description": "Services utilisateur actifs"},

    # === Dev / Build (10) ===
    {"short": "test", "full": "cd /home/turbo/jarvis && uv run pytest --tb=short -q 2>&1 | tail -20", "category": CATEGORY_DEV, "action_type": "bash", "description": "Lancer les tests pytest"},
    {"short": "lint", "full": "cd /home/turbo/jarvis && ruff check src/ --statistics 2>&1 | tail -15", "category": CATEGORY_DEV, "action_type": "bash", "description": "Verifier le code avec ruff"},
    {"short": "build", "full": "cd /home/turbo/jarvis && npm run build 2>&1 | tail -10", "category": CATEGORY_DEV, "action_type": "bash", "description": "Build Electron"},
    {"short": "format", "full": "cd /home/turbo/jarvis && ruff format src/ --check 2>&1 | tail -10", "category": CATEGORY_DEV, "action_type": "bash", "description": "Verifier formatage ruff"},
    {"short": "type", "full": "cd /home/turbo/jarvis && mypy src/ --ignore-missing-imports 2>&1 | tail -15", "category": CATEGORY_DEV, "action_type": "bash", "description": "Verification types mypy"},
    {"short": "pip", "full": "pip list --outdated 2>/dev/null | head -15", "category": CATEGORY_DEV, "action_type": "bash", "description": "Packages pip obsoletes"},
    {"short": "node", "full": "node --version && npm --version", "category": CATEGORY_DEV, "action_type": "bash", "description": "Versions Node.js et npm"},
    {"short": "py", "full": "python3 --version && uv --version", "category": CATEGORY_DEV, "action_type": "bash", "description": "Versions Python et uv"},
    {"short": "todo", "full": "grep -rn 'TODO\\|FIXME\\|HACK\\|XXX' /home/turbo/jarvis/src/ 2>/dev/null | wc -l", "category": CATEGORY_DEV, "action_type": "bash", "description": "Nombre de TODO dans le code"},
    {"short": "lines", "full": "find /home/turbo/jarvis/src -name '*.py' | xargs wc -l 2>/dev/null | tail -1", "category": CATEGORY_DEV, "action_type": "bash", "description": "Total lignes de code Python"},

    # === Git (7) ===
    {"short": "push", "full": "cd /home/turbo/jarvis && git add -A && git commit -m 'auto-commit via JARVIS' && git push", "category": CATEGORY_GIT, "action_type": "bash", "description": "Git add + commit + push"},
    {"short": "status", "full": "cd /home/turbo/jarvis && git status -sb", "category": CATEGORY_GIT, "action_type": "bash", "description": "Git status court"},
    {"short": "diff", "full": "cd /home/turbo/jarvis && git diff --stat", "category": CATEGORY_GIT, "action_type": "bash", "description": "Git diff resume"},
    {"short": "last", "full": "cd /home/turbo/jarvis && git log --oneline -10", "category": CATEGORY_GIT, "action_type": "bash", "description": "10 derniers commits"},
    {"short": "branch", "full": "cd /home/turbo/jarvis && git branch -a", "category": CATEGORY_GIT, "action_type": "bash", "description": "Branches git"},
    {"short": "stash", "full": "cd /home/turbo/jarvis && git stash list", "category": CATEGORY_GIT, "action_type": "bash", "description": "Liste des stash git"},
    {"short": "pull", "full": "cd /home/turbo/jarvis && git pull --rebase", "category": CATEGORY_GIT, "action_type": "bash", "description": "Git pull rebase"},

    # === Docker (3) ===
    {"short": "dock", "full": "docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}' 2>/dev/null || echo 'Docker non actif'", "category": CATEGORY_DOCKER, "action_type": "bash", "description": "Conteneurs Docker actifs"},
    {"short": "images", "full": "docker images --format 'table {{.Repository}}\\t{{.Tag}}\\t{{.Size}}' 2>/dev/null | head -15", "category": CATEGORY_DOCKER, "action_type": "bash", "description": "Images Docker"},
    {"short": "compose", "full": "cd /home/turbo/jarvis/projects/linux && docker compose ps 2>/dev/null", "category": CATEGORY_DOCKER, "action_type": "bash", "description": "Statut Docker Compose JARVIS"},

    # === Audio (3) ===
    {"short": "fix", "full": "fix_audio_linux", "category": CATEGORY_AUDIO, "action_type": "skill", "description": "Reparer l'audio Linux"},
    {"short": "vol", "full": "pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null || amixer get Master 2>/dev/null", "category": CATEGORY_AUDIO, "action_type": "bash", "description": "Volume audio actuel"},
    {"short": "mute", "full": "pactl set-sink-mute @DEFAULT_SINK@ toggle", "category": CATEGORY_AUDIO, "action_type": "bash", "description": "Basculer sourdine"},

    # === Backup / Sauvegarde (3) ===
    {"short": "save", "full": "backup_jarvis_linux", "category": CATEGORY_JARVIS, "action_type": "skill", "description": "Backup complet JARVIS"},
    {"short": "snap", "full": "cd /home/turbo/jarvis && tar czf /tmp/jarvis-snap-$(date +%Y%m%d-%H%M).tar.gz data/*.db src/ 2>&1 | tail -3", "category": CATEGORY_JARVIS, "action_type": "bash", "description": "Snapshot rapide JARVIS"},
    {"short": "restore", "full": "ls -lth /tmp/jarvis-snap-*.tar.gz 2>/dev/null | head -5 || echo 'Aucun snapshot'", "category": CATEGORY_JARVIS, "action_type": "bash", "description": "Lister les snapshots"},

    # === Cluster / IA (7) ===
    {"short": "cluster", "full": "jarvis_cluster_health", "category": CATEGORY_MONITOR, "action_type": "skill", "description": "Sante du cluster IA"},
    {"short": "models", "full": "lm_models", "category": CATEGORY_MONITOR, "action_type": "skill", "description": "Modeles IA charges"},
    {"short": "ollama", "full": "ollama_status", "category": CATEGORY_MONITOR, "action_type": "skill", "description": "Statut serveur Ollama"},
    {"short": "ask", "full": "ollama_query", "category": CATEGORY_MONITOR, "action_type": "skill", "description": "Interroger un modele IA"},
    {"short": "bench", "full": "lm_benchmark", "category": CATEGORY_MONITOR, "action_type": "skill", "description": "Benchmark modele IA"},
    {"short": "route", "full": "orch_routing_matrix", "category": CATEGORY_MONITOR, "action_type": "skill", "description": "Matrice de routage IA"},
    {"short": "budget", "full": "orch_budget", "category": CATEGORY_MONITOR, "action_type": "skill", "description": "Budget orchestrateur IA"},

    # === Trading (5) ===
    {"short": "trade", "full": "trading_status", "category": CATEGORY_TRADING, "action_type": "skill", "description": "Statut trading global"},
    {"short": "positions", "full": "trading_positions", "category": CATEGORY_TRADING, "action_type": "skill", "description": "Positions trading ouvertes"},
    {"short": "signaux", "full": "trading_pending_signals", "category": CATEGORY_TRADING, "action_type": "skill", "description": "Signaux trading en attente"},
    {"short": "backtest", "full": "trading_backtest_list", "category": CATEGORY_TRADING, "action_type": "skill", "description": "Backtests disponibles"},
    {"short": "ranks", "full": "trading_strategy_rankings", "category": CATEGORY_TRADING, "action_type": "skill", "description": "Classement des strategies"},

    # === Services systemd (2) ===
    {"short": "services", "full": "service_list", "category": CATEGORY_SERVICE, "action_type": "skill", "description": "Liste des services JARVIS"},
    {"short": "restart", "full": "systemctl --user restart jarvis-mcp.service 2>/dev/null || echo 'Service non trouve'", "category": CATEGORY_SERVICE, "action_type": "bash", "description": "Redemarrer le service MCP"},
]

assert len(DEFAULT_ALIASES) == 100, f"Il faut exactement 100 aliases, on en a {len(DEFAULT_ALIASES)}"


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------
class VoiceAliasManager:
    """Gestionnaire de raccourcis vocaux ultra-courts.

    Charge les aliases depuis un fichier JSON, avec fallback sur les
    aliases predefinis. Supporte ajout/suppression/recherche.
    """

    def __init__(self, aliases_file: str | Path | None = None) -> None:
        self._file = Path(aliases_file) if aliases_file else ALIASES_FILE
        self._aliases: dict[str, VoiceAlias] = {}
        self._load()

    # --- Persistance -------------------------------------------------------

    def _load(self) -> None:
        """Charge les aliases depuis le fichier JSON ou initialise les defauts."""
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text(encoding="utf-8"))
                for entry in data:
                    alias = VoiceAlias.from_dict(entry)
                    self._aliases[alias.short.lower()] = alias
                logger.info("Charge %d aliases depuis %s", len(self._aliases), self._file)
                return
            except Exception as exc:
                logger.warning("Erreur lecture aliases: %s — reinitialisation", exc)

        # Initialiser avec les aliases par defaut
        self._init_defaults()
        self._save()

    def _init_defaults(self) -> None:
        """Initialise les aliases par defaut."""
        for entry in DEFAULT_ALIASES:
            alias = VoiceAlias.from_dict(entry)
            self._aliases[alias.short.lower()] = alias

    def _save(self) -> None:
        """Sauvegarde les aliases dans le fichier JSON."""
        self._file.parent.mkdir(parents=True, exist_ok=True)
        data = [a.to_dict() for a in self._aliases.values()]
        self._file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # --- API publique ------------------------------------------------------

    def resolve_alias(self, text: str) -> dict[str, Any] | None:
        """Resout un alias vocal en commande complete.

        Args:
            text: Texte vocal (mot ou phrase courte).

        Returns:
            Dict avec 'full', 'action_type', 'category', 'description'
            ou None si aucun alias ne correspond.
        """
        key = text.lower().strip()
        alias = self._aliases.get(key)
        if alias and alias.enabled:
            # Mettre a jour les stats d'utilisation
            alias.usage_count += 1
            alias.last_used = time.time()
            self._save()
            return {
                "short": alias.short,
                "full": alias.full,
                "action_type": alias.action_type,
                "category": alias.category,
                "description": alias.description,
            }
        return None

    def add_alias(
        self,
        short: str,
        full: str,
        category: str = CATEGORY_CUSTOM,
        action_type: str = "bash",
        description: str = "",
    ) -> bool:
        """Ajoute un nouvel alias vocal.

        Args:
            short: Raccourci vocal.
            full: Commande complete.
            category: Categorie de l'alias.
            action_type: Type d'action (skill | bash | compound).
            description: Description courte.

        Returns:
            True si ajoute, False si deja existant.
        """
        key = short.lower().strip()
        if key in self._aliases:
            logger.warning("Alias '%s' existe deja — utiliser update ou remove d'abord", key)
            return False
        self._aliases[key] = VoiceAlias(
            short=short.strip(),
            full=full,
            category=category,
            action_type=action_type,
            description=description,
        )
        self._save()
        logger.info("Alias ajoute: '%s' -> '%s'", short, full)
        return True

    def update_alias(
        self,
        short: str,
        full: str | None = None,
        category: str | None = None,
        action_type: str | None = None,
        description: str | None = None,
        enabled: bool | None = None,
    ) -> bool:
        """Met a jour un alias existant.

        Returns:
            True si mis a jour, False si non trouve.
        """
        key = short.lower().strip()
        alias = self._aliases.get(key)
        if not alias:
            return False
        if full is not None:
            alias.full = full
        if category is not None:
            alias.category = category
        if action_type is not None:
            alias.action_type = action_type
        if description is not None:
            alias.description = description
        if enabled is not None:
            alias.enabled = enabled
        self._save()
        return True

    def remove_alias(self, short: str) -> bool:
        """Supprime un alias.

        Returns:
            True si supprime, False si non trouve.
        """
        key = short.lower().strip()
        if key in self._aliases:
            del self._aliases[key]
            self._save()
            logger.info("Alias supprime: '%s'", short)
            return True
        return False

    def list_aliases(self, category: str | None = None) -> list[dict[str, Any]]:
        """Liste les aliases, optionnellement filtres par categorie.

        Args:
            category: Categorie a filtrer, ou None pour tout.

        Returns:
            Liste de dicts representant chaque alias.
        """
        result = []
        for alias in sorted(self._aliases.values(), key=lambda a: (a.category, a.short)):
            if category and alias.category != category:
                continue
            result.append(alias.to_dict())
        return result

    def search_alias(self, query: str) -> list[dict[str, Any]]:
        """Recherche dans les aliases par mot-cle.

        Cherche dans short, full, description et category.

        Args:
            query: Terme de recherche.

        Returns:
            Liste de dicts correspondants.
        """
        query_lower = query.lower().strip()
        results = []
        for alias in self._aliases.values():
            # Recherche dans tous les champs texte
            searchable = f"{alias.short} {alias.full} {alias.description} {alias.category}".lower()
            if query_lower in searchable:
                results.append(alias.to_dict())
        return sorted(results, key=lambda a: a["short"])

    def get_categories(self) -> dict[str, int]:
        """Retourne les categories avec leur nombre d'aliases.

        Returns:
            Dict {category: count}.
        """
        cats: dict[str, int] = {}
        for alias in self._aliases.values():
            cats[alias.category] = cats.get(alias.category, 0) + 1
        return dict(sorted(cats.items()))

    def get_stats(self) -> dict[str, Any]:
        """Retourne des statistiques sur les aliases.

        Returns:
            Dict avec total, categories, top utilises, etc.
        """
        aliases = list(self._aliases.values())
        top_used = sorted(aliases, key=lambda a: a.usage_count, reverse=True)[:10]
        return {
            "total": len(aliases),
            "enabled": sum(1 for a in aliases if a.enabled),
            "disabled": sum(1 for a in aliases if not a.enabled),
            "categories": self.get_categories(),
            "total_usage": sum(a.usage_count for a in aliases),
            "top_used": [{"short": a.short, "count": a.usage_count} for a in top_used if a.usage_count > 0],
        }

    def reset_defaults(self) -> int:
        """Reinitialise les aliases par defaut (sans toucher aux customs).

        Returns:
            Nombre d'aliases reinitialises.
        """
        count = 0
        default_shorts = {e["short"].lower() for e in DEFAULT_ALIASES}
        for entry in DEFAULT_ALIASES:
            key = entry["short"].lower()
            if key not in self._aliases:
                self._aliases[key] = VoiceAlias.from_dict(entry)
                count += 1
        self._save()
        return count


# ---------------------------------------------------------------------------
# Singleton global
# ---------------------------------------------------------------------------
voice_alias_manager = VoiceAliasManager()


# ---------------------------------------------------------------------------
# Fonction d'integration pour voice_router.py
# ---------------------------------------------------------------------------
def resolve_voice_alias(text: str) -> dict[str, Any] | None:
    """Point d'entree pour le voice_router — resout un alias vocal.

    Args:
        text: Texte vocal brut.

    Returns:
        Dict avec les infos de l'alias, ou None.
    """
    return voice_alias_manager.resolve_alias(text)


def execute_alias(text: str) -> dict[str, Any] | None:
    """Resout ET execute un alias vocal.

    Utilise par le voice_router pour executer directement la commande
    associee a un alias (bash ou skill).

    Args:
        text: Texte vocal brut.

    Returns:
        Dict resultat compatible voice_router, ou None si pas d'alias.
    """
    alias_info = resolve_voice_alias(text)
    if not alias_info:
        return None

    action_type = alias_info["action_type"]
    full_cmd = alias_info["full"]

    if action_type == "bash":
        return _execute_bash_alias(full_cmd, alias_info)
    elif action_type == "skill":
        return _execute_skill_alias(full_cmd, alias_info)
    elif action_type == "compound":
        return _execute_compound_alias(full_cmd, alias_info)

    return None


def _execute_bash_alias(cmd: str, alias_info: dict[str, Any]) -> dict[str, Any]:
    """Execute une commande bash et retourne le resultat."""
    import subprocess

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=_jarvis_root,
        )
        output = result.stdout.strip() or result.stderr.strip() or "(aucune sortie)"
        return {
            "success": result.returncode == 0,
            "method": f"voice_alias:{alias_info['short']}",
            "result": output[:500],
            "confidence": 1.0,
            "module": "voice_aliases",
            "alias": alias_info["short"],
            "action_type": "bash",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "method": f"voice_alias:{alias_info['short']}",
            "result": "Timeout (30s) depasse",
            "confidence": 1.0,
            "module": "voice_aliases",
            "alias": alias_info["short"],
            "action_type": "bash",
        }
    except Exception as exc:
        return {
            "success": False,
            "method": f"voice_alias:{alias_info['short']}",
            "result": f"Erreur: {exc}",
            "confidence": 1.0,
            "module": "voice_aliases",
            "alias": alias_info["short"],
            "action_type": "bash",
        }


def _execute_skill_alias(skill_name: str, alias_info: dict[str, Any]) -> dict[str, Any]:
    """Execute un skill MCP via le systeme JARVIS."""
    try:
        # Tenter d'appeler le skill via le MCP server
        from src.tools import call_tool
        result = call_tool(skill_name, {})
        output = str(result)[:500] if result else "(aucun resultat)"
        return {
            "success": True,
            "method": f"voice_alias:{alias_info['short']}",
            "result": output,
            "confidence": 1.0,
            "module": "voice_aliases",
            "alias": alias_info["short"],
            "action_type": "skill",
            "skill": skill_name,
        }
    except ImportError:
        # Fallback: essayer via les modules de commande directement
        return _execute_bash_alias(
            f"cd /home/turbo/jarvis && uv run python -c \"from src.tools import call_tool; print(call_tool('{skill_name}', {{}}))\"",
            alias_info,
        )
    except Exception as exc:
        return {
            "success": False,
            "method": f"voice_alias:{alias_info['short']}",
            "result": f"Erreur skill '{skill_name}': {exc}",
            "confidence": 1.0,
            "module": "voice_aliases",
            "alias": alias_info["short"],
            "action_type": "skill",
        }


def _execute_compound_alias(cmd: str, alias_info: dict[str, Any]) -> dict[str, Any]:
    """Execute une commande composee (plusieurs etapes separees par &&)."""
    return _execute_bash_alias(cmd, alias_info)


# ---------------------------------------------------------------------------
# Insertion dans jarvis.db (voice_commands)
# ---------------------------------------------------------------------------
def insert_aliases_into_db(db_path: str | Path | None = None) -> int:
    """Insere les 100 aliases dans la table voice_commands de jarvis.db.

    Ne cree pas de doublons : verifie si l'alias existe deja par son nom.

    Args:
        db_path: Chemin vers la base de donnees.

    Returns:
        Nombre d'aliases inseres.
    """
    db = Path(db_path) if db_path else DB_PATH
    if not db.exists():
        logger.error("Base de donnees introuvable: %s", db)
        return 0

    conn = sqlite3.connect(str(db))
    inserted = 0
    now = time.time()

    try:
        for entry in DEFAULT_ALIASES:
            name = f"alias:{entry['short']}"
            # Verifier si l'alias existe deja
            existing = conn.execute(
                "SELECT id FROM voice_commands WHERE name = ?", (name,)
            ).fetchone()
            if existing:
                continue

            triggers = json.dumps([entry["short"]])
            conn.execute(
                """INSERT INTO voice_commands
                   (name, category, description, triggers, action_type, action,
                    params, confirm, enabled, created_at, usage_count)
                   VALUES (?, ?, ?, ?, ?, ?, '[]', 0, 1, ?, 0)""",
                (
                    name,
                    f"alias:{entry['category']}",
                    entry.get("description", f"Alias vocal: {entry['short']}"),
                    triggers,
                    entry["action_type"],
                    entry["full"],
                    now,
                ),
            )
            inserted += 1

        conn.commit()
        logger.info("Insere %d aliases dans voice_commands (jarvis.db)", inserted)
    except Exception as exc:
        logger.error("Erreur insertion DB: %s", exc)
        conn.rollback()
    finally:
        conn.close()

    return inserted


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    """Point d'entree CLI."""
    parser = argparse.ArgumentParser(description="JARVIS Voice Aliases Manager")
    parser.add_argument("--list", nargs="?", const="all", metavar="CATEGORY",
                        help="Lister les aliases (optionnel: par categorie)")
    parser.add_argument("--resolve", metavar="TEXT", help="Resoudre un alias")
    parser.add_argument("--execute", metavar="TEXT", help="Resoudre et executer un alias")
    parser.add_argument("--search", metavar="QUERY", help="Rechercher dans les aliases")
    parser.add_argument("--add", nargs=2, metavar=("SHORT", "FULL"),
                        help="Ajouter un alias")
    parser.add_argument("--remove", metavar="SHORT", help="Supprimer un alias")
    parser.add_argument("--stats", action="store_true", help="Statistiques des aliases")
    parser.add_argument("--categories", action="store_true", help="Lister les categories")
    parser.add_argument("--init-db", action="store_true",
                        help="Inserer les aliases dans jarvis.db")
    parser.add_argument("--reset", action="store_true",
                        help="Reinitialiser les aliases par defaut")
    args = parser.parse_args()

    manager = voice_alias_manager

    if args.resolve:
        result = manager.resolve_alias(args.resolve)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Aucun alias pour: '{args.resolve}'")

    elif args.execute:
        result = execute_alias(args.execute)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Aucun alias pour: '{args.execute}'")

    elif args.search:
        results = manager.search_alias(args.search)
        if results:
            for r in results:
                enabled = "ON " if r["enabled"] else "OFF"
                print(f"  [{enabled}] {r['short']:15s} -> {r['full'][:50]:50s}  ({r['category']})")
            print(f"\n{len(results)} resultat(s)")
        else:
            print(f"Aucun resultat pour: '{args.search}'")

    elif args.list is not None:
        category = None if args.list == "all" else args.list
        aliases = manager.list_aliases(category)
        current_cat = ""
        for a in aliases:
            if a["category"] != current_cat:
                current_cat = a["category"]
                print(f"\n{'=' * 50}")
                print(f"  {current_cat.upper()}")
                print(f"{'=' * 50}")
            enabled = "ON " if a["enabled"] else "OFF"
            print(f"  [{enabled}] {a['short']:15s} -> {a['full'][:55]}")
        print(f"\nTotal: {len(aliases)} aliases")

    elif args.add:
        short, full = args.add
        if manager.add_alias(short, full):
            print(f"Alias ajoute: '{short}' -> '{full}'")
        else:
            print(f"Alias '{short}' existe deja")

    elif args.remove:
        if manager.remove_alias(args.remove):
            print(f"Alias supprime: '{args.remove}'")
        else:
            print(f"Alias non trouve: '{args.remove}'")

    elif args.stats:
        stats = manager.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    elif args.categories:
        cats = manager.get_categories()
        for cat, count in cats.items():
            print(f"  {cat:15s} : {count:3d} aliases")
        print(f"\n  {'TOTAL':15s} : {sum(cats.values()):3d} aliases")

    elif args.init_db:
        count = insert_aliases_into_db()
        print(f"Insere {count} aliases dans jarvis.db")

    elif args.reset:
        count = manager.reset_defaults()
        print(f"Reinitialise {count} aliases par defaut")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
