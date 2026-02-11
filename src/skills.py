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
                SkillStep("open_url", {"url": "http://localhost:3000"}, "Ouvrir localhost:3000"),
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
                "moitie moitie", "cote a cote",
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
                SkillStep("open_url", {"url": "http://localhost:8888"}, "Ouvrir Jupyter"),
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
    ]
