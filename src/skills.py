"""JARVIS Skills & Pipelines — Persistent memory for learned action chains.

A Skill is a named sequence of actions that JARVIS learns and can replay.
Skills are saved to disk and survive restarts.

Examples:
  "mode gaming"  → ferme chrome, lance steam, volume 80%
  "rapport matin" → cluster status, trading status, system info, speak resume
  "clean ram"    → list processes, kill les plus gros, notify result
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


SKILLS_FILE = Path(__file__).resolve().parent.parent / "data" / "skills.json"
HISTORY_FILE = Path(__file__).resolve().parent.parent / "data" / "action_history.json"


@dataclass
class SkillStep:
    """A single step in a skill pipeline."""
    tool: str          # MCP tool name or action_type (e.g. "lm_cluster_status", "app_open")
    args: dict = field(default_factory=dict)
    description: str = ""
    wait_for_result: bool = True


@dataclass
class Skill:
    """A learned action pipeline."""
    name: str
    description: str
    triggers: list[str]       # Voice phrases that activate this skill
    steps: list[SkillStep]
    category: str = "custom"
    created_at: float = 0.0
    usage_count: int = 0
    last_used: float = 0.0
    success_rate: float = 1.0
    confirm: bool = False     # Demander confirmation vocale avant execution


def _ensure_data_dir():
    SKILLS_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_skills() -> list[Skill]:
    """Load skills from persistent storage."""
    _ensure_data_dir()
    if not SKILLS_FILE.exists():
        # Create with default skills
        defaults = _default_skills()
        save_skills(defaults)
        return defaults
    try:
        data = json.loads(SKILLS_FILE.read_text(encoding="utf-8"))
        skills = []
        for s in data:
            steps = [SkillStep(**st) for st in s.pop("steps", [])]
            skills.append(Skill(**s, steps=steps))
        return skills
    except Exception:
        return _default_skills()


def save_skills(skills: list[Skill]):
    """Save skills to persistent storage."""
    _ensure_data_dir()
    data = []
    for s in skills:
        d = asdict(s)
        data.append(d)
    SKILLS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def add_skill(skill: Skill) -> None:
    """Add a new skill and save."""
    skills = load_skills()
    # Replace if same name exists
    skills = [s for s in skills if s.name != skill.name]
    skill.created_at = time.time()
    skills.append(skill)
    save_skills(skills)


def remove_skill(name: str) -> bool:
    """Remove a skill by name."""
    skills = load_skills()
    before = len(skills)
    skills = [s for s in skills if s.name != name]
    if len(skills) < before:
        save_skills(skills)
        return True
    return False


def find_skill(voice_text: str, threshold: float = 0.60) -> tuple[Skill | None, float]:
    """Match voice input to a learned skill."""
    from difflib import SequenceMatcher
    text = voice_text.lower().strip()
    skills = load_skills()

    best: Skill | None = None
    best_score = 0.0

    for skill in skills:
        for trigger in skill.triggers:
            if text == trigger.lower():
                return skill, 1.0
            if trigger.lower() in text:
                score = 0.90
            else:
                score = SequenceMatcher(None, text, trigger.lower()).ratio()
            if score > best_score:
                best_score = score
                best = skill

    if best_score < threshold:
        return None, best_score
    return best, best_score


def record_skill_use(name: str, success: bool):
    """Record skill usage for learning."""
    skills = load_skills()
    for s in skills:
        if s.name == name:
            s.usage_count += 1
            s.last_used = time.time()
            if success:
                s.success_rate = (s.success_rate * (s.usage_count - 1) + 1.0) / s.usage_count
            else:
                s.success_rate = (s.success_rate * (s.usage_count - 1)) / s.usage_count
            break
    save_skills(skills)


def log_action(action: str, result: str, success: bool):
    """Log an action to history for pattern learning."""
    _ensure_data_dir()
    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    history.append({
        "action": action,
        "result": result[:200],
        "success": success,
        "timestamp": time.time(),
    })
    # Keep last 500 actions
    history = history[-500:]
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def get_action_history(limit: int = 20) -> list[dict]:
    """Get recent action history."""
    if not HISTORY_FILE.exists():
        return []
    try:
        history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return history[-limit:]
    except Exception:
        return []


def format_skills_list() -> str:
    """Format skills for voice output."""
    skills = load_skills()
    if not skills:
        return "Aucun skill enregistre."
    lines = [f"Skills JARVIS ({len(skills)}):"]
    for s in skills:
        usage = f" ({s.usage_count}x)" if s.usage_count > 0 else ""
        lines.append(f"  {s.name}: {s.description}{usage}")
        lines.append(f"    Triggers: {', '.join(s.triggers[:3])}")
        lines.append(f"    Actions: {len(s.steps)} etapes")
    return "\n".join(lines)


def suggest_next_actions(context: str, last_actions: list[str] | None = None) -> list[str]:
    """Suggest next actions based on context and history."""
    suggestions = []

    # Context-based suggestions
    ctx = context.lower()
    if "trading" in ctx or "signal" in ctx:
        suggestions.extend([
            "trading_status — Voir le status du pipeline",
            "trading_pending_signals — Signaux en attente",
            "consensus BTC — Avis multi-IA sur le marche",
        ])
    elif "systeme" in ctx or "ram" in ctx or "cpu" in ctx:
        suggestions.extend([
            "system_info — Infos systeme completes",
            "list_processes — Processus en cours",
            "gpu_info — Etat des GPU",
        ])
    elif "cluster" in ctx or "ia" in ctx or "modele" in ctx:
        suggestions.extend([
            "lm_cluster_status — Statut du cluster",
            "lm_models — Modeles charges sur chaque noeud",
            "consensus — Lancer un consensus multi-IA",
        ])
    elif "fichier" in ctx or "dossier" in ctx or "disque" in ctx:
        suggestions.extend([
            "list_folder — Lister un dossier",
            "search_files — Chercher des fichiers",
            "read_text_file — Lire un fichier",
        ])
    else:
        # General suggestions
        suggestions.extend([
            "lm_cluster_status — Statut du cluster IA",
            "trading_status — Pipeline trading",
            "system_info — Infos systeme",
            "list_scripts — Scripts disponibles",
        ])

    return suggestions[:5]


# ═══════════════════════════════════════════════════════════════════════════
# DEFAULT SKILLS (pre-configured pipelines)
# ═══════════════════════════════════════════════════════════════════════════

def _default_skills() -> list[Skill]:
    """Create default skill pipelines."""
    return [
        Skill(
            name="rapport_matin",
            description="Rapport complet du matin: cluster, trading, systeme",
            triggers=[
                "rapport du matin", "rapport matin", "briefing matin",
                "resume du matin", "status complet", "etat general",
            ],
            steps=[
                SkillStep("lm_cluster_status", {}, "Statut du cluster IA"),
                SkillStep("system_info", {}, "Infos systeme"),
                SkillStep("trading_status", {}, "Status pipeline trading"),
                SkillStep("trading_pending_signals", {}, "Signaux en attente"),
            ],
            category="routine",
        ),
        Skill(
            name="mode_trading",
            description="Active le mode trading: ouvre Chrome sur les graphes, lance le scanner",
            triggers=[
                "mode trading", "lance le trading", "session trading",
                "active le trading", "demarre le trading",
            ],
            steps=[
                SkillStep("app_open", {"name": "chrome"}, "Ouvrir Chrome"),
                SkillStep("open_url", {"url": "https://www.tradingview.com"}, "TradingView"),
                SkillStep("trading_status", {}, "Verifier le pipeline"),
                SkillStep("lm_cluster_status", {}, "Verifier le cluster IA"),
            ],
            category="trading",
        ),
        Skill(
            name="mode_dev",
            description="Active le mode developpement: terminal, VSCode, status git",
            triggers=[
                "mode dev", "mode developpement", "session dev",
                "lance le dev", "mode code", "mode programmation",
            ],
            steps=[
                SkillStep("app_open", {"name": "cursor"}, "Ouvrir Cursor IDE"),
                SkillStep("app_open", {"name": "wt"}, "Ouvrir Terminal"),
                SkillStep("lm_cluster_status", {}, "Verifier le cluster IA"),
            ],
            category="dev",
        ),
        Skill(
            name="mode_gaming",
            description="Active le mode gaming: ferme Chrome, lance Steam, volume max",
            triggers=[
                "mode gaming", "mode jeu", "lance le gaming",
                "session gaming", "on joue",
            ],
            steps=[
                SkillStep("close_app", {"name": "chrome"}, "Fermer Chrome"),
                SkillStep("app_open", {"name": "steam"}, "Lancer Steam"),
                SkillStep("volume_up", {}, "Monter le volume"),
                SkillStep("volume_up", {}, "Monter le volume"),
            ],
            category="loisir",
        ),
        Skill(
            name="diagnostic_complet",
            description="Diagnostic complet: systeme, GPU, cluster, reseau, disques",
            triggers=[
                "diagnostic complet", "check complet", "verification complete",
                "tout verifier", "health check", "bilan complet",
            ],
            steps=[
                SkillStep("system_info", {}, "Infos systeme"),
                SkillStep("gpu_info", {}, "Infos GPU"),
                SkillStep("lm_cluster_status", {}, "Statut cluster"),
                SkillStep("network_info", {}, "Infos reseau"),
            ],
            category="systeme",
        ),
        Skill(
            name="consensus_trading",
            description="Consensus multi-IA sur le marche crypto",
            triggers=[
                "consensus trading", "avis du cluster", "consensus crypto",
                "que pensent les ia", "analyse multi ia",
            ],
            steps=[
                SkillStep("trading_status", {}, "Status pipeline"),
                SkillStep("consensus", {"prompt": "Analyse rapide du marche crypto. BTC, ETH, SOL. Tendance et signal en 3 lignes.", "nodes": "M1,M2,M3"}, "Consensus cluster"),
            ],
            category="trading",
        ),
        Skill(
            name="cleanup_ram",
            description="Nettoyer la RAM: lister les processus gourmands et suggerer",
            triggers=[
                "nettoie la ram", "libere la memoire", "cleanup ram",
                "ram pleine", "trop de ram utilisee",
            ],
            steps=[
                SkillStep("system_info", {}, "Verifier la RAM"),
                SkillStep("list_processes", {"filter": ""}, "Lister les processus"),
            ],
            category="systeme",
        ),
        Skill(
            name="ferme_tout",
            description="Fermer toutes les applications non essentielles",
            triggers=[
                "ferme tout", "tout fermer", "clean desktop",
                "bureau propre", "ferme les applications",
            ],
            steps=[
                SkillStep("close_app", {"name": "chrome"}, "Fermer Chrome"),
                SkillStep("close_app", {"name": "discord"}, "Fermer Discord"),
                SkillStep("close_app", {"name": "spotify"}, "Fermer Spotify"),
                SkillStep("press_hotkey", {"keys": "win+d"}, "Afficher le bureau"),
            ],
            category="systeme",
            confirm=True,
        ),

        # ── NOUVEAUX PIPELINES ──

        Skill(
            name="mode_presentation",
            description="Mode presentation: mode nuit off, luminosite max, volume moyen, projeter ecran",
            triggers=[
                "mode presentation", "lance la presentation",
                "mode pres", "je presente", "active la presentation",
            ],
            steps=[
                SkillStep("press_hotkey", {"keys": "win+p"}, "Ouvrir projection ecran"),
                SkillStep("powershell_run", {"command": "$b = 100; (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, $b)"}, "Luminosite max"),
                SkillStep("volume_down", {}, "Baisser le volume"),
                SkillStep("press_hotkey", {"keys": "win+d"}, "Afficher le bureau"),
            ],
            category="productivite",
        ),
        Skill(
            name="mode_focus",
            description="Mode focus: ferme les distractions, active ne pas deranger, plein ecran",
            triggers=[
                "mode focus", "mode concentration", "je bosse",
                "pas de distraction", "focus total", "mode travail",
            ],
            steps=[
                SkillStep("close_app", {"name": "discord"}, "Fermer Discord"),
                SkillStep("close_app", {"name": "spotify"}, "Fermer Spotify"),
                SkillStep("close_app", {"name": "telegram"}, "Fermer Telegram"),
                SkillStep("volume_mute", {}, "Couper le son"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode Focus actif. Aucune distraction."}, "Notification"),
            ],
            category="productivite",
        ),
        Skill(
            name="mode_musique",
            description="Mode musique: lance Spotify, volume agreable, mode nuit",
            triggers=[
                "mode musique", "mets de la musique", "ambiance musicale",
                "lance la musique de fond", "background music",
            ],
            steps=[
                SkillStep("app_open", {"name": "spotify"}, "Lancer Spotify"),
                SkillStep("volume_down", {}, "Baisser un peu le volume"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode musique actif. Spotify lance."}, "Notification"),
            ],
            category="loisir",
        ),
        Skill(
            name="routine_soir",
            description="Routine du soir: sauvegarde, ferme apps, mode nuit, veille",
            triggers=[
                "routine du soir", "bonne nuit", "fin de journee",
                "je vais dormir", "routine nuit", "au dodo",
            ],
            steps=[
                SkillStep("press_hotkey", {"keys": "ctrl+s"}, "Sauvegarder le travail en cours"),
                SkillStep("close_app", {"name": "chrome"}, "Fermer Chrome"),
                SkillStep("close_app", {"name": "code"}, "Fermer VSCode"),
                SkillStep("close_app", {"name": "discord"}, "Fermer Discord"),
                SkillStep("press_hotkey", {"keys": "win+a"}, "Activer mode nuit"),
                SkillStep("powershell_run", {"command": "$b = 20; (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, $b)"}, "Luminosite basse"),
                SkillStep("notify", {"title": "JARVIS", "message": "Bonne nuit. Routine terminee."}, "Notification"),
            ],
            category="routine",
            confirm=True,
        ),
        Skill(
            name="workspace_frontend",
            description="Workspace frontend: Chrome DevTools, VSCode, terminal, localhost",
            triggers=[
                "workspace frontend", "mode frontend", "session front",
                "lance le front", "workspace web",
            ],
            steps=[
                SkillStep("app_open", {"name": "code"}, "Ouvrir VSCode"),
                SkillStep("app_open", {"name": "wt"}, "Ouvrir Terminal"),
                SkillStep("open_url", {"url": "http://127.0.0.1:3000"}, "Ouvrir 127.0.0.1:3000"),
                SkillStep("notify", {"title": "JARVIS", "message": "Workspace frontend pret."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="workspace_backend",
            description="Workspace backend: terminal, VSCode, Postman, LM Studio",
            triggers=[
                "workspace backend", "mode backend", "session back",
                "lance le back", "workspace api",
            ],
            steps=[
                SkillStep("app_open", {"name": "code"}, "Ouvrir VSCode"),
                SkillStep("app_open", {"name": "wt"}, "Ouvrir Terminal"),
                SkillStep("app_open", {"name": "lmstudio"}, "Ouvrir LM Studio"),
                SkillStep("lm_cluster_status", {}, "Verifier le cluster"),
                SkillStep("notify", {"title": "JARVIS", "message": "Workspace backend pret."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="optimiser_pc",
            description="Optimisation PC: vider corbeille, nettoyer RAM, diagnostic disque",
            triggers=[
                "optimise le pc", "nettoie le pc", "optimisation",
                "accelere le pc", "pc lent", "boost pc",
            ],
            steps=[
                SkillStep("system_info", {}, "Diagnostic systeme"),
                SkillStep("list_processes", {"filter": ""}, "Lister processus gourmands"),
                SkillStep("powershell_run", {"command": "Clear-RecycleBin -Force -ErrorAction SilentlyContinue; 'Corbeille videe'"}, "Vider la corbeille"),
                SkillStep("gpu_info", {}, "Verifier les GPU"),
                SkillStep("notify", {"title": "JARVIS", "message": "Optimisation terminee. Verifie les resultats."}, "Notification"),
            ],
            category="systeme",
            confirm=True,
        ),
        Skill(
            name="monitoring_complet",
            description="Monitoring en temps reel: systeme, GPU, reseau, cluster, services",
            triggers=[
                "monitoring complet", "surveillance complete",
                "tout surveiller", "dashboard monitoring", "status global",
            ],
            steps=[
                SkillStep("system_info", {}, "Infos systeme"),
                SkillStep("gpu_info", {}, "Infos GPU"),
                SkillStep("network_info", {}, "Infos reseau"),
                SkillStep("lm_cluster_status", {}, "Cluster IA"),
                SkillStep("screen_resolution", {}, "Resolution ecran"),
                SkillStep("wifi_networks", {}, "Reseaux Wi-Fi"),
                SkillStep("list_services", {}, "Services Windows"),
            ],
            category="systeme",
        ),
        Skill(
            name="split_screen_travail",
            description="Ecran divise: navigateur a gauche, editeur a droite",
            triggers=[
                "ecran divise", "split screen", "deux fenetres",
                "moitie moitie", "cote a cote", "ecran de travail",
                "espace de travail", "travail en split",
            ],
            steps=[
                SkillStep("app_open", {"name": "chrome"}, "Ouvrir Chrome"),
                SkillStep("press_hotkey", {"keys": "win+left"}, "Chrome a gauche"),
                SkillStep("app_open", {"name": "code"}, "Ouvrir VSCode"),
                SkillStep("press_hotkey", {"keys": "win+right"}, "VSCode a droite"),
            ],
            category="productivite",
        ),
        Skill(
            name="backup_rapide",
            description="Sauvegarde rapide: save tout, screenshot, copier dans presse-papier",
            triggers=[
                "backup rapide", "sauvegarde rapide", "save all",
                "tout sauvegarder", "sauve tout",
            ],
            steps=[
                SkillStep("press_hotkey", {"keys": "ctrl+s"}, "Sauvegarder fichier actif"),
                SkillStep("screenshot", {}, "Capture d'ecran"),
                SkillStep("notify", {"title": "JARVIS", "message": "Sauvegarde rapide effectuee."}, "Notification"),
            ],
            category="productivite",
        ),
        Skill(
            name="mode_stream",
            description="Mode streaming: lance OBS, Chrome, volume optimal, mode nuit off",
            triggers=[
                "mode stream", "lance le stream", "session stream",
                "je stream", "streaming mode",
            ],
            steps=[
                SkillStep("app_open", {"name": "obs64"}, "Lancer OBS Studio"),
                SkillStep("app_open", {"name": "chrome"}, "Ouvrir Chrome"),
                SkillStep("volume_up", {}, "Monter le volume"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode stream actif. OBS pret."}, "Notification"),
            ],
            category="loisir",
        ),
        Skill(
            name="check_trading_complet",
            description="Check trading complet: status, positions, signaux, cluster, consensus",
            triggers=[
                "check trading complet", "bilan trading",
                "revue trading", "analyse complete trading",
                "tout le trading",
            ],
            steps=[
                SkillStep("trading_status", {}, "Status pipeline trading"),
                SkillStep("trading_positions", {}, "Positions ouvertes"),
                SkillStep("trading_pending_signals", {}, "Signaux en attente"),
                SkillStep("lm_cluster_status", {}, "Cluster IA"),
                SkillStep("consensus", {"prompt": "Analyse marche crypto: BTC ETH SOL. Tendance, risque, signal.", "nodes": "M1,M2,M3"}, "Consensus multi-IA"),
            ],
            category="trading",
        ),

        # ── VAGUE 2: Pipelines avances ──

        Skill(
            name="mode_reunion",
            description="Mode reunion: ouvre Teams/Zoom, coupe micro, check camera, volume bas",
            triggers=[
                "mode reunion", "lance la reunion", "session visio",
                "mode visio", "visioconference", "mode meeting",
            ],
            steps=[
                SkillStep("app_open", {"name": "teams"}, "Ouvrir Teams"),
                SkillStep("volume_down", {}, "Baisser le volume"),
                SkillStep("volume_down", {}, "Baisser encore"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode reunion actif. Micro coupe par defaut."}, "Notification"),
            ],
            category="communication",
        ),
        Skill(
            name="mode_communication",
            description="Mode communication: ouvre Discord, Telegram, Gmail",
            triggers=[
                "mode communication", "ouvre les messageries", "mode social",
                "lance les messageries", "session communication",
            ],
            steps=[
                SkillStep("app_open", {"name": "discord"}, "Ouvrir Discord"),
                SkillStep("app_open", {"name": "telegram"}, "Ouvrir Telegram"),
                SkillStep("open_url", {"url": "https://mail.google.com"}, "Ouvrir Gmail"),
                SkillStep("notify", {"title": "JARVIS", "message": "Messageries ouvertes."}, "Notification"),
            ],
            category="communication",
        ),
        Skill(
            name="pause_cafe",
            description="Pause cafe: sauvegarde, verrouille le PC, coupe le son",
            triggers=[
                "pause cafe", "je fais une pause", "pause",
                "je reviens", "brb", "afk",
            ],
            steps=[
                SkillStep("press_hotkey", {"keys": "ctrl+s"}, "Sauvegarder"),
                SkillStep("volume_mute", {}, "Couper le son"),
                SkillStep("lock_screen", {}, "Verrouiller le PC"),
            ],
            category="routine",
        ),
        Skill(
            name="retour_pause",
            description="Retour de pause: reactive le son, check notifications, status rapide",
            triggers=[
                "retour de pause", "je suis revenu", "c'est bon je suis la",
                "retour", "de retour", "je suis de retour",
            ],
            steps=[
                SkillStep("volume_up", {}, "Remettre le son"),
                SkillStep("volume_up", {}, "Volume normal"),
                SkillStep("system_info", {}, "Check systeme rapide"),
                SkillStep("notify", {"title": "JARVIS", "message": "Bon retour. Tout est operationnel."}, "Notification"),
            ],
            category="routine",
        ),
        Skill(
            name="mode_ia",
            description="Mode IA: lance LM Studio, check cluster, liste modeles",
            triggers=[
                "mode ia", "mode intelligence artificielle", "session ia",
                "lance l'ia", "active l'ia", "mode cluster",
            ],
            steps=[
                SkillStep("app_open", {"name": "lmstudio"}, "Lancer LM Studio"),
                SkillStep("lm_cluster_status", {}, "Verifier le cluster"),
                SkillStep("lm_models", {}, "Lister les modeles charges"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode IA actif. Cluster verifie."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="deploiement",
            description="Mode deploiement: terminal, status systeme, check services, monitoring",
            triggers=[
                "mode deploiement", "lance le deploiement", "session deploy",
                "deploy", "deploie", "mode deploy",
            ],
            steps=[
                SkillStep("app_open", {"name": "wt"}, "Ouvrir Terminal"),
                SkillStep("system_info", {}, "Check systeme"),
                SkillStep("list_services", {}, "Verifier les services"),
                SkillStep("network_info", {}, "Check reseau"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode deploiement pret."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="debug_reseau",
            description="Debug reseau: info reseau, scan wifi, ping, services, IP",
            triggers=[
                "debug reseau", "probleme reseau", "diagnostique reseau",
                "le reseau marche pas", "pas d'internet", "debug network",
            ],
            steps=[
                SkillStep("network_info", {}, "Infos reseau"),
                SkillStep("wifi_networks", {}, "Scanner Wi-Fi"),
                SkillStep("ping", {"host": "8.8.8.8"}, "Ping Google DNS"),
                SkillStep("ping", {"host": "192.168.1.1"}, "Ping gateway"),
                SkillStep("notify", {"title": "JARVIS", "message": "Diagnostic reseau termine."}, "Notification"),
            ],
            category="systeme",
        ),
        Skill(
            name="mode_lecture",
            description="Mode lecture: ferme distractions, mode nuit, volume bas, zoom texte",
            triggers=[
                "mode lecture", "mode etude", "session lecture",
                "je lis", "mode read", "mode lire",
            ],
            steps=[
                SkillStep("close_app", {"name": "discord"}, "Fermer Discord"),
                SkillStep("close_app", {"name": "spotify"}, "Fermer Spotify"),
                SkillStep("press_hotkey", {"keys": "win+a"}, "Mode nuit"),
                SkillStep("volume_down", {}, "Baisser le volume"),
                SkillStep("volume_down", {}, "Volume minimal"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode lecture actif."}, "Notification"),
            ],
            category="productivite",
        ),
        Skill(
            name="update_systeme",
            description="Preparation mise a jour: sauvegarde, check updates, check espace disque",
            triggers=[
                "update systeme", "mise a jour systeme", "prepare les updates",
                "mets a jour le pc", "lance les mises a jour",
            ],
            steps=[
                SkillStep("press_hotkey", {"keys": "ctrl+s"}, "Sauvegarder le travail"),
                SkillStep("system_info", {}, "Check systeme"),
                SkillStep("powershell_run", {"command": "Get-CimInstance Win32_LogicalDisk | Select DeviceID, @{N='Free(GB)';E={[math]::Round($_.FreeSpace/1GB,1)}} | Out-String"}, "Espace disque"),
                SkillStep("notify", {"title": "JARVIS", "message": "Systeme pret pour mise a jour."}, "Notification"),
            ],
            category="systeme",
        ),
        Skill(
            name="mode_recherche",
            description="Mode recherche: ouvre Chrome, Google, multiple onglets, presse-papier",
            triggers=[
                "mode recherche", "session recherche", "lance les recherches",
                "mode investigation", "je recherche",
            ],
            steps=[
                SkillStep("app_open", {"name": "chrome"}, "Ouvrir Chrome"),
                SkillStep("open_url", {"url": "https://www.google.com"}, "Google"),
                SkillStep("open_url", {"url": "https://www.perplexity.ai"}, "Perplexity"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode recherche actif. Chrome + Perplexity."}, "Notification"),
            ],
            category="productivite",
        ),
        Skill(
            name="workspace_turbo",
            description="Workspace JARVIS Turbo: ouvre le projet, terminal, cluster check",
            triggers=[
                "workspace turbo", "ouvre turbo", "session turbo",
                "lance turbo", "mode turbo", "workspace jarvis",
            ],
            steps=[
                SkillStep("app_open", {"name": "code"}, "Ouvrir VSCode"),
                SkillStep("app_open", {"name": "wt"}, "Ouvrir Terminal"),
                SkillStep("open_url", {"url": "https://github.com/Turbo31150/turbo"}, "GitHub Turbo"),
                SkillStep("lm_cluster_status", {}, "Verifier le cluster"),
                SkillStep("notify", {"title": "JARVIS", "message": "Workspace Turbo pret."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="rapport_soir",
            description="Rapport du soir: bilan trading, cluster status, historique actions",
            triggers=[
                "rapport du soir", "bilan du soir", "briefing soir",
                "resume de la journee", "bilan journee",
            ],
            steps=[
                SkillStep("trading_status", {}, "Bilan trading"),
                SkillStep("trading_positions", {}, "Positions restantes"),
                SkillStep("lm_cluster_status", {}, "Status cluster"),
                SkillStep("system_info", {}, "Status systeme"),
                SkillStep("action_history", {}, "Historique des actions"),
            ],
            category="routine",
        ),

        # ── VAGUE 3: Pipelines accessibilite / performance / reseau / creatif ──

        Skill(
            name="mode_cinema",
            description="Mode cinema: ferme tout, volume max, luminosite min, plein ecran",
            triggers=[
                "mode cinema", "mode film", "lance un film",
                "session cinema", "regarde un film",
            ],
            steps=[
                SkillStep("close_app", {"name": "discord"}, "Fermer Discord"),
                SkillStep("close_app", {"name": "telegram"}, "Fermer Telegram"),
                SkillStep("volume_up", {}, "Monter le volume"),
                SkillStep("volume_up", {}, "Volume max"),
                SkillStep("powershell_run", {"command": "$b = 30; (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, $b)"}, "Luminosite tamisee"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode cinema actif. Bon film."}, "Notification"),
            ],
            category="loisir",
        ),
        Skill(
            name="mode_securite",
            description="Mode securite: mode avion, verrouillage, bluetooth off",
            triggers=[
                "mode securite", "securise le pc", "mode panique",
                "coupe tout", "mode offline",
            ],
            steps=[
                SkillStep("press_hotkey", {"keys": "ctrl+s"}, "Sauvegarder"),
                SkillStep("powershell_run", {"command": "Add-Type -AssemblyName System.Runtime.WindowsRuntime; $radio = [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]::GetRadiosAsync().GetAwaiter().GetResult() | Where-Object { $_.Kind -eq 'Bluetooth' }; if($radio) { $radio[0].SetStateAsync('Off').GetAwaiter().GetResult() | Out-Null; 'Bluetooth off' }"}, "Couper Bluetooth"),
                SkillStep("volume_mute", {}, "Couper le son"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode securite actif."}, "Notification"),
            ],
            category="systeme",
            confirm=True,
        ),
        Skill(
            name="mode_accessibilite",
            description="Mode accessibilite: loupe, narrateur, contraste eleve, clavier visuel",
            triggers=[
                "mode accessibilite", "aide visuelle", "active l'accessibilite",
                "j'ai du mal a voir", "mode malvoyant",
            ],
            steps=[
                SkillStep("press_hotkey", {"keys": "win++"}, "Activer la loupe"),
                SkillStep("powershell_run", {"command": "Start-Process osk"}, "Ouvrir clavier visuel"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode accessibilite actif: loupe + clavier visuel."}, "Notification"),
            ],
            category="systeme",
        ),
        Skill(
            name="mode_economie_energie",
            description="Mode economie: plan eco, luminosite basse, bluetooth off, mode nuit",
            triggers=[
                "mode economie", "economise la batterie", "mode batterie",
                "economie d'energie", "mode eco",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "powercfg /setactive a1841308-3541-4fab-bc81-f71556f20b4a; 'Mode economie active'"}, "Plan economie"),
                SkillStep("powershell_run", {"command": "$b = 20; (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, $b)"}, "Luminosite basse"),
                SkillStep("powershell_run", {"command": "Add-Type -AssemblyName System.Runtime.WindowsRuntime; $radio = [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]::GetRadiosAsync().GetAwaiter().GetResult() | Where-Object { $_.Kind -eq 'Bluetooth' }; if($radio) { $radio[0].SetStateAsync('Off').GetAwaiter().GetResult() | Out-Null; 'Bluetooth off' }"}, "Couper Bluetooth"),
                SkillStep("press_hotkey", {"keys": "win+a"}, "Mode nuit"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode economie actif. Batterie preservee."}, "Notification"),
            ],
            category="systeme",
        ),
        Skill(
            name="mode_performance_max",
            description="Mode performance: plan haute perf, luminosite max, bluetooth off",
            triggers=[
                "mode performance", "performances max", "full power",
                "mode turbo pc", "puissance maximale",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c; 'Mode haute performance active'"}, "Plan haute performance"),
                SkillStep("powershell_run", {"command": "$b = 100; (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, $b)"}, "Luminosite max"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode performance max actif."}, "Notification"),
            ],
            category="systeme",
        ),
        Skill(
            name="clean_reseau",
            description="Nettoyage reseau complet: flush DNS, check IP, scan wifi, ping",
            triggers=[
                "clean reseau", "nettoie le reseau", "repare internet",
                "flush dns complet", "reset reseau",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "ipconfig /flushdns"}, "Vider le cache DNS"),
                SkillStep("network_info", {}, "Infos reseau"),
                SkillStep("wifi_networks", {}, "Scanner Wi-Fi"),
                SkillStep("ping", {"host": "8.8.8.8"}, "Ping Google DNS"),
                SkillStep("notify", {"title": "JARVIS", "message": "Nettoyage reseau termine."}, "Notification"),
            ],
            category="systeme",
        ),
        Skill(
            name="workspace_data",
            description="Workspace data science: Chrome, LM Studio, terminal, Jupyter",
            triggers=[
                "workspace data", "mode data science", "session data",
                "lance le data", "workspace analyse",
            ],
            steps=[
                SkillStep("app_open", {"name": "chrome"}, "Ouvrir Chrome"),
                SkillStep("app_open", {"name": "lmstudio"}, "Ouvrir LM Studio"),
                SkillStep("app_open", {"name": "wt"}, "Ouvrir Terminal"),
                SkillStep("open_url", {"url": "http://127.0.0.1:8888"}, "Ouvrir Jupyter"),
                SkillStep("lm_cluster_status", {}, "Verifier le cluster"),
                SkillStep("notify", {"title": "JARVIS", "message": "Workspace data pret."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="session_creative",
            description="Session creative: Spotify, mode focus, snap layout, luminosite agreable",
            triggers=[
                "session creative", "mode creatif", "inspiration",
                "mode creation", "lance la creation",
            ],
            steps=[
                SkillStep("app_open", {"name": "spotify"}, "Lancer Spotify"),
                SkillStep("close_app", {"name": "discord"}, "Fermer Discord"),
                SkillStep("powershell_run", {"command": "$b = 60; (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, $b)"}, "Luminosite agreable"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode creatif actif. Bonne inspiration."}, "Notification"),
            ],
            category="productivite",
        ),

        # ── VAGUE 4: Pipelines multi-ecran / nettoyage / confort ──

        Skill(
            name="mode_double_ecran",
            description="Mode double ecran: etend l'affichage, snap layout, navigateur + editeur",
            triggers=[
                "mode double ecran", "deux ecrans", "active le second ecran",
                "dual screen", "mode etendu",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "DisplaySwitch.exe /extend"}, "Etendre l'affichage"),
                SkillStep("app_open", {"name": "chrome"}, "Ouvrir Chrome"),
                SkillStep("press_hotkey", {"keys": "win+left"}, "Chrome a gauche"),
                SkillStep("app_open", {"name": "code"}, "Ouvrir VSCode"),
                SkillStep("press_hotkey", {"keys": "win+right"}, "VSCode a droite"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode double ecran actif."}, "Notification"),
            ],
            category="productivite",
        ),
        Skill(
            name="nettoyage_complet",
            description="Nettoyage complet: temp + corbeille + DNS + diagnostic",
            triggers=[
                "nettoyage complet", "grand nettoyage", "clean complet",
                "nettoie tout", "purge complete",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; 'Temp nettoye'"}, "Vider temp"),
                SkillStep("powershell_run", {"command": "Clear-RecycleBin -Force -ErrorAction SilentlyContinue; 'Corbeille videe'"}, "Vider corbeille"),
                SkillStep("powershell_run", {"command": "ipconfig /flushdns"}, "Vider DNS"),
                SkillStep("system_info", {}, "Diagnostic systeme"),
                SkillStep("notify", {"title": "JARVIS", "message": "Nettoyage complet termine."}, "Notification"),
            ],
            category="systeme",
            confirm=True,
        ),
        Skill(
            name="mode_confort",
            description="Mode confort: night light, luminosite agreable, volume moyen, focus assist",
            triggers=[
                "mode confort", "ambiance confortable", "mode relax",
                "mode zen", "ambiance douce",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "$b = 50; (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, $b)"}, "Luminosite 50%"),
                SkillStep("volume_down", {}, "Volume moyen"),
                SkillStep("press_hotkey", {"keys": "win+a"}, "Mode nuit"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode confort actif. Ambiance douce."}, "Notification"),
            ],
            category="loisir",
        ),
        Skill(
            name="check_espace_disque",
            description="Verification espace disque + temp + diagnostic stockage",
            triggers=[
                "check espace disque", "verifie l'espace", "combien de place reste",
                "disques pleins", "espace restant",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "Get-CimInstance Win32_LogicalDisk | Select DeviceID, @{N='Total(GB)';E={[math]::Round($_.Size/1GB,1)}}, @{N='Free(GB)';E={[math]::Round($_.FreeSpace/1GB,1)}} | Out-String"}, "Espace disque"),
                SkillStep("powershell_run", {"command": "$s = (Get-ChildItem $env:TEMP -Recurse -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB; \"Temp: $([math]::Round($s,1)) MB\""}, "Taille fichiers temp"),
                SkillStep("notify", {"title": "JARVIS", "message": "Verification espace terminee."}, "Notification"),
            ],
            category="systeme",
        ),

        # ── VAGUE 5: Pipelines securite / maintenance avancee ──

        Skill(
            name="audit_securite",
            description="Audit securite: Windows Security + pare-feu + services + confidentialite",
            triggers=[
                "audit securite", "check securite", "verification securite",
                "securite du pc", "scan securite",
            ],
            steps=[
                SkillStep("app_open", {"name": "windowsdefender:"}, "Ouvrir Windows Security"),
                SkillStep("list_services", {}, "Verifier les services"),
                SkillStep("network_info", {}, "Check reseau"),
                SkillStep("notify", {"title": "JARVIS", "message": "Audit securite termine."}, "Notification"),
            ],
            category="systeme",
        ),
        Skill(
            name="maintenance_complete",
            description="Maintenance complete: nettoyage disque + temp + defrag + check espace",
            triggers=[
                "maintenance complete", "entretien du pc", "maintenance pc",
                "entretien complet", "soin du pc",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; 'Temp nettoye'"}, "Vider temp"),
                SkillStep("powershell_run", {"command": "Clear-RecycleBin -Force -ErrorAction SilentlyContinue; 'Corbeille videe'"}, "Vider corbeille"),
                SkillStep("powershell_run", {"command": "Get-CimInstance Win32_LogicalDisk | Select DeviceID, @{N='Free(GB)';E={[math]::Round($_.FreeSpace/1GB,1)}} | Out-String"}, "Espace disque"),
                SkillStep("system_info", {}, "Diagnostic systeme"),
                SkillStep("gpu_info", {}, "Check GPU"),
                SkillStep("notify", {"title": "JARVIS", "message": "Maintenance complete terminee."}, "Notification"),
            ],
            category="systeme",
            confirm=True,
        ),
        Skill(
            name="mode_partage_ecran",
            description="Mode partage ecran: Miracast + luminosite max + mode presentation",
            triggers=[
                "mode partage ecran", "partage d'ecran", "diffuse l'ecran",
                "lance le cast", "envoie sur la tv",
            ],
            steps=[
                SkillStep("press_hotkey", {"keys": "win+k"}, "Ouvrir Miracast"),
                SkillStep("powershell_run", {"command": "$b = 100; (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, $b)"}, "Luminosite max"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode partage ecran actif."}, "Notification"),
            ],
            category="productivite",
        ),
        Skill(
            name="diagnostic_demarrage",
            description="Diagnostic demarrage: apps au demarrage + services + utilisation disque",
            triggers=[
                "diagnostic demarrage", "le pc demarre lentement",
                "demarrage lent", "optimise le demarrage", "pourquoi c'est lent",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "Get-CimInstance Win32_StartupCommand | Select Name, Command | Out-String"}, "Apps au demarrage"),
                SkillStep("list_services", {}, "Services actifs"),
                SkillStep("system_info", {}, "Diagnostic systeme"),
                SkillStep("powershell_run", {"command": "Get-CimInstance Win32_LogicalDisk | Select DeviceID, @{N='Free(GB)';E={[math]::Round($_.FreeSpace/1GB,1)}} | Out-String"}, "Espace disque"),
                SkillStep("notify", {"title": "JARVIS", "message": "Diagnostic demarrage termine."}, "Notification"),
            ],
            category="systeme",
        ),

        # ── VAGUE 6: Pipelines personnalisation / ambiance ──

        Skill(
            name="mode_nuit_complet",
            description="Mode nuit complet: mode sombre + night light + luminosite basse + volume bas",
            triggers=[
                "mode nuit complet", "ambiance nuit", "tout en sombre",
                "active tout le mode nuit", "nuit totale",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name 'AppsUseLightTheme' -Value 0; Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name 'SystemUsesLightTheme' -Value 0; 'Mode sombre active'"}, "Mode sombre"),
                SkillStep("powershell_run", {"command": "$b = 20; (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, $b)"}, "Luminosite basse"),
                SkillStep("volume_down", {}, "Volume bas"),
                SkillStep("volume_down", {}, "Volume minimal"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode nuit complet actif."}, "Notification"),
            ],
            category="productivite",
        ),
        Skill(
            name="mode_jour",
            description="Mode jour: mode clair + luminosite max + night light off",
            triggers=[
                "mode jour", "mode journee", "tout en clair",
                "ambiance jour", "reveil",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name 'AppsUseLightTheme' -Value 1; Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name 'SystemUsesLightTheme' -Value 1; 'Mode clair active'"}, "Mode clair"),
                SkillStep("powershell_run", {"command": "$b = 80; (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, $b)"}, "Luminosite haute"),
                SkillStep("volume_up", {}, "Volume normal"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode jour actif. Bonne journee."}, "Notification"),
            ],
            category="productivite",
        ),

        # ── VAGUE 7: Pipelines diagnostic / sauvegarde / reseau avance ──

        Skill(
            name="diagnostic_reseau_complet",
            description="Diagnostic reseau complet: IP, MAC, vitesse, tracert, netstat, DNS, ping",
            triggers=[
                "diagnostic reseau complet", "analyse reseau complete",
                "tout le reseau", "deep network check",
            ],
            steps=[
                SkillStep("network_info", {}, "Infos reseau"),
                SkillStep("powershell_run", {"command": "Get-NetAdapter | Select Name, MacAddress, Status, LinkSpeed | Out-String"}, "Adaptateurs reseau"),
                SkillStep("wifi_networks", {}, "Reseaux Wi-Fi"),
                SkillStep("ping", {"host": "8.8.8.8"}, "Ping Google"),
                SkillStep("powershell_run", {"command": "ipconfig /flushdns; 'DNS flush OK'"}, "Flush DNS"),
                SkillStep("notify", {"title": "JARVIS", "message": "Diagnostic reseau complet termine."}, "Notification"),
            ],
            category="systeme",
        ),
        Skill(
            name="diagnostic_sante_pc",
            description="Diagnostic sante: CPU temp, uptime, espace disque, RAM, GPU",
            triggers=[
                "diagnostic sante", "sante du pc", "health check complet",
                "comment va le pc", "etat de sante",
            ],
            steps=[
                SkillStep("system_info", {}, "Infos systeme"),
                SkillStep("gpu_info", {}, "Infos GPU"),
                SkillStep("powershell_run", {"command": "$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; $up = (Get-Date) - $boot; \"Uptime: $($up.Days)j $($up.Hours)h $($up.Minutes)m\""}, "Uptime"),
                SkillStep("powershell_run", {"command": "Get-CimInstance Win32_LogicalDisk | Select DeviceID, @{N='Free(GB)';E={[math]::Round($_.FreeSpace/1GB,1)}} | Out-String"}, "Espace disque"),
                SkillStep("notify", {"title": "JARVIS", "message": "Diagnostic sante termine."}, "Notification"),
            ],
            category="systeme",
        ),
        Skill(
            name="preparation_backup",
            description="Preparation sauvegarde: save tout, check espace, ouvre parametres backup",
            triggers=[
                "prepare le backup", "preparation sauvegarde",
                "avant la sauvegarde", "pre-backup",
            ],
            steps=[
                SkillStep("press_hotkey", {"keys": "ctrl+s"}, "Sauvegarder fichier actif"),
                SkillStep("powershell_run", {"command": "Get-CimInstance Win32_LogicalDisk | Select DeviceID, @{N='Free(GB)';E={[math]::Round($_.FreeSpace/1GB,1)}} | Out-String"}, "Espace disque"),
                SkillStep("system_info", {}, "Check systeme"),
                SkillStep("notify", {"title": "JARVIS", "message": "Pre-backup OK. Pret pour la sauvegarde."}, "Notification"),
            ],
            category="systeme",
        ),

        # ── VAGUE 8: Pipelines Docker / Git / Dev / ML ──

        Skill(
            name="mode_docker",
            description="Mode Docker: liste conteneurs, images, espace disque",
            triggers=[
                "mode docker", "check docker", "etat docker",
                "docker complet", "environnement docker",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | Out-String"}, "Conteneurs actifs"),
                SkillStep("powershell_run", {"command": "docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' | Out-String"}, "Images Docker"),
                SkillStep("powershell_run", {"command": "docker system df | Out-String"}, "Espace Docker"),
                SkillStep("notify", {"title": "JARVIS", "message": "Check Docker termine."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="git_workflow",
            description="Workflow Git: status, diff, log recent, pull",
            triggers=[
                "git workflow", "check git", "etat du repo",
                "synchronise git", "mise a jour git",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "cd F:\\BUREAU\\turbo; git status"}, "Git status"),
                SkillStep("powershell_run", {"command": "cd F:\\BUREAU\\turbo; git diff --stat | Out-String"}, "Git diff"),
                SkillStep("powershell_run", {"command": "cd F:\\BUREAU\\turbo; git log --oneline -5 | Out-String"}, "Log recent"),
                SkillStep("notify", {"title": "JARVIS", "message": "Git workflow check termine."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="workspace_ml",
            description="Workspace ML: Jupyter + LM Studio + GPU check",
            triggers=[
                "workspace ml", "mode machine learning", "lance le workspace ml",
                "mode ia", "workspace ia locale",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "Start-Process lmstudio"}, "Lancer LM Studio"),
                SkillStep("app_open", {"name": "chrome"}, "Ouvrir Chrome"),
                SkillStep("powershell_run", {"command": "Start-Process 'http://127.0.0.1:8888'"}, "Ouvrir Jupyter"),
                SkillStep("gpu_info", {}, "Check GPU"),
                SkillStep("lm_cluster_status", {}, "Statut cluster"),
                SkillStep("notify", {"title": "JARVIS", "message": "Workspace ML pret."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="debug_docker",
            description="Debug Docker: logs, restart conteneurs, nettoyage volumes",
            triggers=[
                "debug docker", "probleme docker", "docker ne marche pas",
                "repare docker", "clean docker",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "docker ps -a --format 'table {{.Names}}\t{{.Status}}' | Out-String"}, "Tous les conteneurs"),
                SkillStep("powershell_run", {"command": "docker volume ls | Out-String"}, "Volumes Docker"),
                SkillStep("powershell_run", {"command": "docker system prune -f 2>&1 | Out-String"}, "Nettoyage Docker"),
                SkillStep("notify", {"title": "JARVIS", "message": "Debug Docker termine."}, "Notification"),
            ],
            category="dev",
            confirm=True,
        ),

        # ── VAGUE 9: Pipelines multimedia / nettoyage / automatisation ──

        Skill(
            name="mode_stream",
            description="Mode stream: OBS + micro check + game bar + performance max",
            triggers=[
                "mode stream", "lance le stream", "prepare le stream",
                "streaming", "je vais streamer",
            ],
            steps=[
                SkillStep("app_open", {"name": "obs64"}, "Lancer OBS"),
                SkillStep("press_hotkey", {"keys": "win+g"}, "Game Bar"),
                SkillStep("powershell_run", {"command": "powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c 2>$null; 'Mode haute performance'"}, "Performance max"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode stream pret. OBS lance."}, "Notification"),
            ],
            category="loisir",
        ),
        Skill(
            name="nettoyage_clipboard",
            description="Nettoyage complet: clipboard + temp + historique recent",
            triggers=[
                "nettoyage rapide", "clean rapide", "nettoie vite",
                "nettoyage clipboard et temp",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "Set-Clipboard -Value $null; 'Clipboard vide'"}, "Vider clipboard"),
                SkillStep("powershell_run", {"command": "Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; 'Temp nettoye'"}, "Vider temp"),
                SkillStep("notify", {"title": "JARVIS", "message": "Nettoyage rapide termine."}, "Notification"),
            ],
            category="systeme",
        ),
        Skill(
            name="inventaire_apps",
            description="Inventaire des applications installees et environnement dev",
            triggers=[
                "inventaire applications", "quelles apps sont installees",
                "liste toutes les applications", "inventaire logiciels",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "Get-Package | Select Name, Version | Sort Name | Out-String"}, "Apps installees"),
                SkillStep("powershell_run", {"command": "python --version 2>&1; docker --version 2>&1; git --version 2>&1; node --version 2>&1"}, "Versions dev"),
                SkillStep("powershell_run", {"command": "$env:PATH -split ';' | Where-Object { $_ -ne '' } | Out-String"}, "PATH"),
                SkillStep("notify", {"title": "JARVIS", "message": "Inventaire applications termine."}, "Notification"),
            ],
            category="systeme",
        ),

        # ── VAGUE 10: Pipelines session / ecrans / productivite ──

        Skill(
            name="mode_presentation",
            description="Mode presentation: ecran etendu + volume off + focus assist + luminosite max",
            triggers=[
                "mode presentation", "je vais presenter", "lance la presentation",
                "prepare la presentation", "powerpoint mode",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "displayswitch.exe /extend"}, "Ecran etendu"),
                SkillStep("powershell_run", {"command": "$b = 100; (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, $b)"}, "Luminosite max"),
                SkillStep("press_hotkey", {"keys": "volume_mute"}, "Couper le son"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode presentation actif."}, "Notification"),
            ],
            category="productivite",
        ),
        Skill(
            name="fin_journee",
            description="Fin de journee: sauvegarde + ferme tout + planifie veille",
            triggers=[
                "fin de journee", "j'ai fini", "bonne nuit jarvis",
                "c'est fini pour aujourd'hui", "je m'en vais",
            ],
            steps=[
                SkillStep("press_hotkey", {"keys": "ctrl+s"}, "Sauvegarder"),
                SkillStep("powershell_run", {"command": "Get-Date -Format 'dddd dd MMMM yyyy HH:mm' | Out-String"}, "Heure de fin"),
                SkillStep("notify", {"title": "JARVIS", "message": "Bonne soiree ! Tout est sauvegarde."}, "Notification"),
            ],
            category="routine",
        ),
        Skill(
            name="mode_dual_screen",
            description="Mode double ecran: etendre + snap fenetre + luminosite uniforme",
            triggers=[
                "mode double ecran", "active les deux ecrans", "mode dual screen",
                "deux ecrans", "branche l'ecran",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "displayswitch.exe /extend"}, "Ecran etendu"),
                SkillStep("powershell_run", {"command": "$b = 70; (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, $b)"}, "Luminosite 70%"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode double ecran actif."}, "Notification"),
            ],
            category="productivite",
        ),

        # ── VAGUE 11: Pipelines hardware / diagnostic complet ──

        Skill(
            name="inventaire_hardware",
            description="Inventaire hardware complet: CPU, RAM, GPU, carte mere, BIOS, disques",
            triggers=[
                "inventaire hardware", "specs completes", "tout le hardware",
                "details materiel", "fiche technique pc",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "Get-CimInstance Win32_Processor | Select Name, NumberOfCores, MaxClockSpeed | Out-String"}, "CPU"),
                SkillStep("powershell_run", {"command": "Get-CimInstance Win32_PhysicalMemory | Select Manufacturer, Capacity, Speed | Out-String"}, "RAM"),
                SkillStep("gpu_info", {}, "GPU"),
                SkillStep("powershell_run", {"command": "Get-CimInstance Win32_BaseBoard | Select Manufacturer, Product | Out-String"}, "Carte mere"),
                SkillStep("powershell_run", {"command": "Get-PhysicalDisk | Select FriendlyName, MediaType, HealthStatus, Size | Out-String"}, "Disques"),
                SkillStep("powershell_run", {"command": "Get-CimInstance Win32_BIOS | Select SMBIOSBIOSVersion | Out-String"}, "BIOS"),
                SkillStep("notify", {"title": "JARVIS", "message": "Inventaire hardware complet termine."}, "Notification"),
            ],
            category="systeme",
        ),
        Skill(
            name="check_performances",
            description="Check performances: CPU load, RAM, top processus, GPU temp",
            triggers=[
                "check performances", "comment tourne le pc", "performances",
                "le pc rame", "c'est lent",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "$cpu = (Get-CimInstance Win32_Processor).LoadPercentage; \"CPU: $cpu%\""}, "CPU load"),
                SkillStep("powershell_run", {"command": "$os = Get-CimInstance Win32_OperatingSystem; $used = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB,1); \"RAM utilisee: $used GB\""}, "RAM"),
                SkillStep("powershell_run", {"command": "Get-Process | Sort WorkingSet64 -Desc | Select -First 5 Name, @{N='MB';E={[math]::Round($_.WorkingSet64/1MB)}} | Out-String"}, "Top 5 RAM"),
                SkillStep("gpu_info", {}, "GPU"),
                SkillStep("notify", {"title": "JARVIS", "message": "Check performances termine."}, "Notification"),
            ],
            category="systeme",
        ),
        Skill(
            name="rapport_batterie",
            description="Rapport batterie complet: niveau, sante, estimation autonomie",
            triggers=[
                "rapport batterie", "etat batterie complet", "batterie detaillee",
                "autonomie restante", "check batterie",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "$b = Get-CimInstance Win32_Battery; if ($b) { \"Niveau: $($b.EstimatedChargeRemaining)%`nStatut: $($b.BatteryStatus)`nEstimation: $($b.EstimatedRunTime) min\" } else { 'PC fixe - pas de batterie' }"}, "Niveau batterie"),
                SkillStep("powershell_run", {"command": "powercfg /batteryreport /output $env:TEMP\\battery.html 2>$null; 'Rapport genere dans Temp'"}, "Rapport batterie"),
                SkillStep("notify", {"title": "JARVIS", "message": "Rapport batterie genere."}, "Notification"),
            ],
            category="systeme",
        ),

        # ── VAGUE 12: Pipelines productivite / accessibilite / navigation ──

        Skill(
            name="mode_4_fenetres",
            description="Mode 4 fenetres: snap en 4 coins + luminosite equilibree",
            triggers=[
                "mode 4 fenetres", "quatre fenetres", "snap en 4",
                "4 coins", "quadrillage",
            ],
            steps=[
                SkillStep("press_hotkey", {"keys": "win+tab"}, "Vue des taches"),
                SkillStep("powershell_run", {"command": "$b = 70; (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, $b)"}, "Luminosite equilibree"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode 4 fenetres - utilisez Snap Layout pour positionner."}, "Notification"),
            ],
            category="productivite",
        ),
        Skill(
            name="mode_accessibilite_complet",
            description="Mode accessibilite complet: loupe + narrateur + contraste + clavier virtuel",
            triggers=[
                "mode accessibilite complet", "accessibilite totale",
                "active toute l'accessibilite", "j'ai besoin d'aide visuelle",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "Start-Process osk"}, "Clavier virtuel"),
                SkillStep("press_hotkey", {"keys": "win+plus"}, "Loupe"),
                SkillStep("notify", {"title": "JARVIS", "message": "Mode accessibilite complet actif."}, "Notification"),
            ],
            category="accessibilite",
        ),
        Skill(
            name="navigation_rapide",
            description="Navigation rapide: nouveau tab + favoris + zoom reset",
            triggers=[
                "navigation rapide", "chrome rapide", "surf rapide",
                "nouveau surf",
            ],
            steps=[
                SkillStep("app_open", {"name": "chrome"}, "Ouvrir Chrome"),
                SkillStep("press_hotkey", {"keys": "ctrl+t"}, "Nouvel onglet"),
                SkillStep("press_hotkey", {"keys": "ctrl+0"}, "Reset zoom"),
                SkillStep("notify", {"title": "JARVIS", "message": "Navigation rapide prete."}, "Notification"),
            ],
            category="navigation",
        ),

        # ── VAGUE 13: Pipelines reseau avance / securite reseau ──

        Skill(
            name="audit_reseau",
            description="Audit reseau: IP publique, DNS, ports ouverts, ARP, vitesse",
            triggers=[
                "audit reseau", "analyse le reseau", "securite reseau",
                "scan reseau complet", "qui est sur mon reseau",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "(Invoke-WebRequest -Uri 'https://api.ipify.org' -UseBasicParsing).Content"}, "IP publique"),
                SkillStep("network_info", {}, "IP locale"),
                SkillStep("powershell_run", {"command": "Get-NetTCPConnection -State Listen | Select LocalPort, @{N='Process';E={(Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).Name}} | Sort LocalPort | Select -First 15 | Out-String"}, "Ports ouverts"),
                SkillStep("powershell_run", {"command": "Get-NetNeighbor | Where State -ne Unreachable | Select IPAddress, LinkLayerAddress | Out-String"}, "Table ARP"),
                SkillStep("powershell_run", {"command": "Get-NetAdapter | Where Status -eq Up | Select Name, LinkSpeed | Out-String"}, "Vitesse"),
                SkillStep("notify", {"title": "JARVIS", "message": "Audit reseau termine."}, "Notification"),
            ],
            category="systeme",
        ),
        Skill(
            name="optimise_dns",
            description="Optimisation DNS: flush + passage sur Cloudflare + test",
            triggers=[
                "optimise le dns", "dns rapide", "accelere le dns",
                "internet lent", "dns lent",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "ipconfig /flushdns; 'DNS flush OK'"}, "Flush DNS"),
                SkillStep("powershell_run", {"command": "Set-DnsClientServerAddress -InterfaceAlias 'Wi-Fi' -ServerAddresses ('1.1.1.1','1.0.0.1'); 'DNS Cloudflare configure'"}, "DNS Cloudflare"),
                SkillStep("ping", {"host": "google.com"}, "Test connexion"),
                SkillStep("notify", {"title": "JARVIS", "message": "DNS optimise sur Cloudflare."}, "Notification"),
            ],
            category="systeme",
            confirm=True,
        ),
        Skill(
            name="diagnostic_connexion",
            description="Diagnostic connexion internet: ping, DNS, IP, vitesse, tracert",
            triggers=[
                "diagnostic connexion", "internet ne marche pas",
                "pas de connexion", "probleme internet", "debug internet",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "Get-NetAdapter | Where Status -eq Up | Select Name, LinkSpeed, Status | Out-String"}, "Carte reseau"),
                SkillStep("ping", {"host": "8.8.8.8"}, "Ping Google DNS"),
                SkillStep("powershell_run", {"command": "Resolve-DnsName google.com -ErrorAction SilentlyContinue | Select Name, IPAddress | Out-String"}, "Test DNS"),
                SkillStep("powershell_run", {"command": "(Invoke-WebRequest -Uri 'https://api.ipify.org' -UseBasicParsing -TimeoutSec 5).Content"}, "IP publique"),
                SkillStep("notify", {"title": "JARVIS", "message": "Diagnostic connexion termine."}, "Notification"),
            ],
            category="systeme",
        ),

        # ── VAGUE 14: Pipelines fichiers / nettoyage / organisation ──

        Skill(
            name="nettoyage_fichiers",
            description="Nettoyage fichiers: doublons + gros fichiers + dossiers vides + temp",
            triggers=[
                "nettoyage fichiers", "organise les fichiers", "fais le menage",
                "clean les fichiers", "libere de l'espace",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; 'Temp nettoye'"}, "Vider temp"),
                SkillStep("powershell_run", {"command": "$e = Get-ChildItem -Directory -Recurse -Path $env:USERPROFILE -ErrorAction SilentlyContinue | Where { (Get-ChildItem $_.FullName -Force -ErrorAction SilentlyContinue).Count -eq 0 }; \"$($e.Count) dossiers vides trouves\""}, "Dossiers vides"),
                SkillStep("powershell_run", {"command": "Get-ChildItem $env:USERPROFILE -Recurse -File -ErrorAction SilentlyContinue | Sort Length -Desc | Select -First 10 Name, @{N='MB';E={[math]::Round($_.Length/1MB,1)}} | Out-String"}, "Top 10 gros fichiers"),
                SkillStep("notify", {"title": "JARVIS", "message": "Analyse fichiers terminee."}, "Notification"),
            ],
            category="fichiers",
        ),
        Skill(
            name="backup_projet",
            description="Backup projet: compresse le dossier turbo + git status + timestamp",
            triggers=[
                "backup du projet", "sauvegarde le projet", "archive le projet",
                "compresse turbo", "backup turbo",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "cd F:\\BUREAU\\turbo; git status --short | Out-String"}, "Git status"),
                SkillStep("powershell_run", {"command": "$ts = Get-Date -Format 'yyyyMMdd_HHmm'; Compress-Archive -Path 'F:\\BUREAU\\turbo\\src' -DestinationPath \"F:\\BUREAU\\turbo_backup_$ts.zip\" -Force; \"Backup: turbo_backup_$ts.zip\""}, "Compression"),
                SkillStep("notify", {"title": "JARVIS", "message": "Backup projet termine."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="analyse_code",
            description="Analyse code: fichiers Python, lignes, taille, structure",
            triggers=[
                "analyse le code", "stats du code", "combien de lignes de code",
                "metriques du projet", "analyse le projet",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "$py = Get-ChildItem 'F:\\BUREAU\\turbo\\src' -Filter '*.py' -Recurse; \"$($py.Count) fichiers Python\""}, "Fichiers Python"),
                SkillStep("powershell_run", {"command": "$lines = (Get-ChildItem 'F:\\BUREAU\\turbo\\src' -Filter '*.py' -Recurse | Get-Content | Measure-Object -Line).Lines; \"$lines lignes de code\""}, "Lignes de code"),
                SkillStep("powershell_run", {"command": "$s = (Get-ChildItem 'F:\\BUREAU\\turbo\\src' -Recurse -File | Measure-Object Length -Sum).Sum / 1KB; \"Taille src: $([math]::Round($s,1)) KB\""}, "Taille"),
                SkillStep("notify", {"title": "JARVIS", "message": "Analyse code terminee."}, "Notification"),
            ],
            category="dev",
        ),

        # ── VAGUE 15: Pipelines Multi-Agent (MAO) ──

        Skill(
            name="forge_code",
            description="The Forge: M2 genere le code, M1 review logique, correction auto si erreur",
            triggers=[
                "forge du code", "genere du code", "code autonome",
                "auto code", "la forge", "lance la forge",
            ],
            steps=[
                SkillStep("lm_cluster_status", {}, "Verifier cluster disponible"),
                SkillStep("lm_query", {"prompt": "Genere le code Python demande. Code uniquement, pas d'explication.", "node": "M2"}, "M2 genere le code"),
                SkillStep("lm_query", {"prompt": "Review ce code. Identifie bugs, problemes logiques, optimisations. Sois precis.", "node": "M1"}, "M1 review logique"),
                SkillStep("notify", {"title": "JARVIS Forge", "message": "Code genere par M2 et review par M1."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="shield_audit",
            description="The Shield: Audit securite multi-IA parallele (M1 + M2 analysent en parallele)",
            triggers=[
                "audit de securite", "shield", "scan de securite",
                "verifie la securite du code", "audit code",
            ],
            steps=[
                SkillStep("lm_query", {"prompt": "Analyse ce code pour les failles de securite: injections SQL, XSS, fuites de cles API, OWASP top 10. Liste chaque probleme.", "node": "M1"}, "M1 analyse securite"),
                SkillStep("lm_query", {"prompt": "Verifie ce code pour les bugs logiques, race conditions, et erreurs de gestion memoire.", "node": "M2"}, "M2 analyse logique"),
                SkillStep("notify", {"title": "JARVIS Shield", "message": "Audit securite termine. M1 + M2 ont analyse."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="brain_index",
            description="The Brain: Indexe le projet dans la memoire JARVIS via M1",
            triggers=[
                "indexe le projet", "memorise le projet", "brain index",
                "mets a jour la memoire", "apprends le projet",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "$py = Get-ChildItem 'F:\\BUREAU\\turbo\\src' -Filter '*.py' -Recurse; $py | Select Name, @{N='KB';E={[math]::Round($_.Length/1KB,1)}} | Out-String"}, "Lister fichiers source"),
                SkillStep("powershell_run", {"command": "$lines = (Get-ChildItem 'F:\\BUREAU\\turbo\\src' -Filter '*.py' -Recurse | Get-Content | Measure-Object -Line).Lines; \"$lines lignes de code total\""}, "Compter les lignes"),
                SkillStep("lm_query", {"prompt": "Resume en 5 lignes l'architecture de ce projet Python: structure des fichiers, patterns utilises, technologies.", "node": "M1"}, "M1 resume le projet"),
                SkillStep("notify", {"title": "JARVIS Brain", "message": "Projet indexe dans la memoire."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="medic_repair",
            description="The Medic: Auto-reparation cluster — verifie et relance M1, M2, Ollama",
            triggers=[
                "medic", "repare le cluster", "auto reparation",
                "le cluster est casse", "relance les agents", "repare les ia",
            ],
            steps=[
                SkillStep("lm_cluster_status", {}, "Check cluster complet"),
                SkillStep("powershell_run", {"command": "$r = try { (Invoke-WebRequest -Uri 'http://10.5.0.2:1234/v1/models' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 3).StatusCode } catch { 0 }; if ($r -eq 200) { 'M1 OK' } else { 'M1 OFFLINE — relance LM Studio' }"}, "Check M1"),
                SkillStep("powershell_run", {"command": "$r = try { (Invoke-WebRequest -Uri 'http://192.168.1.26:1234/v1/models' -Headers @{Authorization='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 3).StatusCode } catch { 0 }; if ($r -eq 200) { 'M2 OK' } else { 'M2 OFFLINE' }"}, "Check M2"),
                SkillStep("powershell_run", {"command": "$r = try { (Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3).StatusCode } catch { 0 }; if ($r -eq 200) { 'Ollama OK' } else { Start-Process ollama -ArgumentList 'serve' -WindowStyle Hidden; 'Ollama relance' }"}, "Check/Relance Ollama"),
                SkillStep("notify", {"title": "JARVIS Medic", "message": "Diagnostic cluster termine. Agents verifies."}, "Notification"),
            ],
            category="systeme",
        ),
        Skill(
            name="consensus_mao",
            description="MAO Consensus: Question envoyee a M1 + M2 + OL1, synthese des reponses",
            triggers=[
                "consensus complet", "mao consensus", "avis de tous les agents",
                "demande a tout le monde", "consensus multi agent",
            ],
            steps=[
                SkillStep("lm_cluster_status", {}, "Verifier disponibilite agents"),
                SkillStep("consensus", {"prompt": "Reponds a cette question avec ta recommandation + niveau de confiance (1-10) + justification courte.", "nodes": "M1,M2"}, "Consensus M1+M2"),
                SkillStep("lm_query", {"prompt": "Donne ton avis sur cette question en 3 lignes. Niveau de confiance 1-10.", "node": "OL1"}, "Avis OL1"),
                SkillStep("notify", {"title": "JARVIS MAO", "message": "Consensus multi-agent termine."}, "Notification"),
            ],
            category="dev",
        ),

        # ── VAGUE 16: Skills avances Multi-Agent ──

        Skill(
            name="lab_tests",
            description="The Lab: M1 genere les tests, execute localement, M2 analyse les echecs",
            triggers=[
                "lance les tests", "genere des tests", "test automatique",
                "lab tests", "teste le code", "pytest",
            ],
            steps=[
                SkillStep("lm_query", {"prompt": "Genere un script pytest complet pour tester le code demande. Code uniquement.", "node": "M1"}, "M1 genere les tests"),
                SkillStep("powershell_run", {"command": "cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -m pytest src/ --tb=short -q 2>&1 | Out-String"}, "Executer pytest"),
                SkillStep("notify", {"title": "JARVIS Lab", "message": "Tests executes. Resultats disponibles."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="architect_diagram",
            description="The Architect: M1 analyse le code et genere un diagramme Mermaid de l'architecture",
            triggers=[
                "diagramme architecture", "documente l'architecture",
                "schema du projet", "architect", "mermaid",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "$py = Get-ChildItem 'F:\\BUREAU\\turbo\\src' -Filter '*.py' -Recurse; $py | ForEach-Object { $_.Name + ': ' + (Select-String -Path $_.FullName -Pattern '^(class |def |async def )' | Measure-Object).Count + ' definitions' } | Out-String"}, "Scanner structure code"),
                SkillStep("lm_query", {"prompt": "Analyse cette structure de fichiers Python et genere un diagramme Mermaid.js montrant les relations entre modules. Format: ```mermaid ... ```", "node": "M1"}, "M1 genere le diagramme"),
                SkillStep("notify", {"title": "JARVIS Architect", "message": "Diagramme architecture genere."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="oracle_veille",
            description="The Oracle: Recherche web via OL1 cloud (minimax) + synthese M1",
            triggers=[
                "veille technologique", "recherche sur le web", "oracle",
                "cherche des infos", "renseigne toi sur",
            ],
            steps=[
                SkillStep("ollama_web_search", {"query": "Recherche les dernieres informations sur le sujet demande"}, "OL1 cloud recherche web"),
                SkillStep("lm_query", {"prompt": "Synthese en 5 points des informations trouvees. Sois factuel et precis.", "node": "M1"}, "M1 synthetise"),
                SkillStep("notify", {"title": "JARVIS Oracle", "message": "Veille technologique terminee."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="sentinel_securite",
            description="The Sentinel: Scan ports ouverts, connexions actives, processus suspects",
            triggers=[
                "sentinel", "scan de menaces", "cyber defense",
                "connexions suspectes", "qui est connecte", "scan securite reseau",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "Get-NetTCPConnection -State Listen | Select LocalPort, @{N='Process';E={(Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).Name}} | Sort LocalPort | Out-String"}, "Ports en ecoute"),
                SkillStep("powershell_run", {"command": "Get-NetTCPConnection -State Established | Where { $_.RemoteAddress -notmatch '^(127|10|192\\.168|0\\.0)' } | Select RemoteAddress, RemotePort, @{N='Process';E={(Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).Name}} | Out-String"}, "Connexions externes"),
                SkillStep("powershell_run", {"command": "Get-NetFirewallRule -Enabled True -Direction Inbound | Where Action -eq Allow | Select DisplayName, Profile | Select -First 10 | Out-String"}, "Regles pare-feu entrantes"),
                SkillStep("notify", {"title": "JARVIS Sentinel", "message": "Scan securite termine."}, "Notification"),
            ],
            category="systeme",
        ),
        Skill(
            name="alchemist_transform",
            description="The Alchemist: M1 transforme des donnees d'un format a un autre (CSV, JSON, SQL...)",
            triggers=[
                "transforme les donnees", "convertis le fichier", "alchemist",
                "change le format", "csv vers json", "json vers csv",
            ],
            steps=[
                SkillStep("lm_query", {"prompt": "Transforme ces donnees dans le format demande. Retourne uniquement les donnees converties, pas d'explication.", "node": "M1"}, "M1 transforme les donnees"),
                SkillStep("notify", {"title": "JARVIS Alchemist", "message": "Transformation de donnees terminee."}, "Notification"),
            ],
            category="dev",
        ),
        Skill(
            name="director_standup",
            description="The Director: Rapport quotidien basé sur git log + status systeme + trading",
            triggers=[
                "rapport quotidien", "standup", "director",
                "resume de la journee", "qu'est ce qui s'est passe",
            ],
            steps=[
                SkillStep("powershell_run", {"command": "cd F:\\BUREAU\\turbo; git log --since='24 hours ago' --oneline 2>&1 | Out-String"}, "Git log 24h"),
                SkillStep("system_info", {}, "Status systeme"),
                SkillStep("trading_status", {}, "Status trading"),
                SkillStep("lm_query", {"prompt": "En tant que chef de projet, fais un rapport vocal court (5 lignes max) de l'avancement basé sur ces infos: commits recents, status systeme, status trading.", "node": "M1"}, "M1 genere le rapport"),
                SkillStep("notify", {"title": "JARVIS Director", "message": "Rapport quotidien genere."}, "Notification"),
            ],
            category="routine",
        ),
    ]
