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
    ]
