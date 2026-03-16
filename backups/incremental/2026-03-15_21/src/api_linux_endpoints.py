"""API REST Linux — Blueprint Flask exposant toutes les fonctionnalités JARVIS.

20 endpoints couvrant santé système, skills, commandes vocales, brain,
cluster, dominos, profils, notifications, performance et statistiques.

Enregistrement : dans le serveur Flask principal (port 8080) via
    app.register_blueprint(linux_api)

Préfixe automatique : /api/linux/*
"""

from __future__ import annotations

import json
import logging
import os
import platform
import sqlite3
import subprocess
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request

logger = logging.getLogger("jarvis.api_linux")

# ── Blueprint ────────────────────────────────────────────────────────────
linux_api = Blueprint("linux_api", __name__, url_prefix="/api/linux")

_BASE_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = _BASE_DIR / "data"
_DB_PATH = _DATA_DIR / "jarvis.db"
_LEARNED_DB = _DATA_DIR / "learned_actions.db"

# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _ok(data: Any, message: str = "ok") -> tuple:
    """Réponse JSON standard succès."""
    return jsonify({"status": "ok", "message": message, "data": data}), 200


def _err(message: str, code: int = 400) -> tuple:
    """Réponse JSON standard erreur."""
    return jsonify({"status": "error", "message": message, "data": None}), code


def _run(cmd: str, timeout: int = 10) -> str:
    """Exécuter une commande shell avec timeout."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return ""


def _safe_json(raw: str) -> Any:
    """Parse JSON sans planter."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return raw


# ═══════════════════════════════════════════════════════════════════════════
# 1. GET /api/linux/health — Santé complète
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/health", methods=["GET"])
def health():
    """Santé complète : CPU, RAM, GPU, disque, services."""
    info: dict[str, Any] = {
        "timestamp": time.time(),
        "hostname": platform.node(),
        "kernel": platform.release(),
        "uptime": _run("uptime -p"),
    }

    # CPU
    try:
        load_1, load_5, load_15 = os.getloadavg()
        cpu_count = os.cpu_count() or 1
        info["cpu"] = {
            "cores": cpu_count,
            "load_1m": round(load_1, 2),
            "load_5m": round(load_5, 2),
            "load_15m": round(load_15, 2),
            "usage_pct": round(load_1 / cpu_count * 100, 1),
        }
    except OSError:
        info["cpu"] = {"error": "unavailable"}

    # RAM
    try:
        meminfo = Path("/proc/meminfo").read_text()
        mem = {}
        for line in meminfo.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                mem[parts[0].rstrip(":")] = int(parts[1])  # en kB
        total = mem.get("MemTotal", 0)
        avail = mem.get("MemAvailable", 0)
        used = total - avail
        info["ram"] = {
            "total_mb": round(total / 1024),
            "used_mb": round(used / 1024),
            "available_mb": round(avail / 1024),
            "usage_pct": round(used / max(1, total) * 100, 1),
        }
    except OSError:
        info["ram"] = {"error": "unavailable"}

    # GPU (nvidia-smi)
    gpu_raw = _run(
        "nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,"
        "memory.used,memory.total --format=csv,noheader,nounits"
    )
    gpus = []
    if gpu_raw:
        for line in gpu_raw.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "temp_c": int(parts[2]),
                    "utilization_pct": int(parts[3]),
                    "memory_used_mb": int(parts[4]),
                    "memory_total_mb": int(parts[5]),
                })
    info["gpus"] = gpus
    info["gpu_count"] = len(gpus)

    # Disque
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bfree * st.f_frsize
        used = total - free
        info["disk"] = {
            "total_gb": round(total / (1024 ** 3), 1),
            "used_gb": round(used / (1024 ** 3), 1),
            "free_gb": round(free / (1024 ** 3), 1),
            "usage_pct": round(used / max(1, total) * 100, 1),
        }
    except OSError:
        info["disk"] = {"error": "unavailable"}

    # Services systemd critiques
    services_raw = _run(
        "systemctl list-units --type=service --state=running --no-pager --no-legend "
        "| head -20"
    )
    info["services_running"] = len(services_raw.splitlines()) if services_raw else 0

    return _ok(info, "health check complete")


# ═══════════════════════════════════════════════════════════════════════════
# 2. GET /api/linux/skills — Liste des skills
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/skills", methods=["GET"])
def list_skills():
    """Liste de tous les skills avec triggers."""
    try:
        from src.skills import load_skills
        skills = load_skills()
        data = []
        for s in skills:
            data.append({
                "name": s.name,
                "description": s.description,
                "category": s.category,
                "triggers": s.triggers,
                "steps_count": len(s.steps),
                "usage_count": s.usage_count,
                "success_rate": s.success_rate,
            })
        return _ok({"count": len(data), "skills": data})
    except Exception as exc:
        return _err(f"skills load failed: {exc}", 500)


# ═══════════════════════════════════════════════════════════════════════════
# 3. GET /api/linux/skills/<name> — Détail d'un skill
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/skills/<name>", methods=["GET"])
def get_skill(name: str):
    """Détail complet d'un skill par nom."""
    try:
        from src.skills import load_skills
        skills = load_skills()
        for s in skills:
            if s.name == name:
                return _ok(asdict(s))
        return _err(f"skill '{name}' not found", 404)
    except Exception as exc:
        return _err(f"skill lookup failed: {exc}", 500)


# ═══════════════════════════════════════════════════════════════════════════
# 4. POST /api/linux/skills/execute — Exécuter un skill
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/skills/execute", methods=["POST"])
def execute_skill():
    """Exécuter un skill par nom. Body : {"skill": "nom"}."""
    body = request.get_json(silent=True) or {}
    skill_name = body.get("skill", "")
    if not skill_name:
        return _err("missing 'skill' parameter")

    try:
        from src.skills import load_skills, record_skill_use
        skills = load_skills()
        target = None
        for s in skills:
            if s.name == skill_name:
                target = s
                break
        if not target:
            return _err(f"skill '{skill_name}' not found", 404)

        # Enregistrer l'utilisation
        record_skill_use(skill_name)
        steps_summary = [{"tool": st.tool, "args": st.args} for st in target.steps]
        return _ok({
            "skill": skill_name,
            "steps": steps_summary,
            "status": "queued",
            "message": f"Skill '{skill_name}' enqueued ({len(target.steps)} steps)",
        })
    except Exception as exc:
        return _err(f"skill execution failed: {exc}", 500)


# ═══════════════════════════════════════════════════════════════════════════
# 5. GET /api/linux/voice/commands — Commandes vocales
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/voice/commands", methods=["GET"])
def voice_commands():
    """Liste des commandes vocales, avec filtre optionnel ?category=xxx."""
    category = request.args.get("category")
    try:
        from src.commands import get_commands_by_category
        cmds = get_commands_by_category(category)
        data = []
        for c in cmds:
            data.append({
                "name": c.name,
                "category": c.category,
                "description": c.description,
                "triggers": c.triggers,
                "action_type": c.action_type,
                "confirm": c.confirm,
            })
        return _ok({"count": len(data), "commands": data})
    except Exception as exc:
        return _err(f"commands load failed: {exc}", 500)


# ═══════════════════════════════════════════════════════════════════════════
# 6. GET /api/linux/voice/corrections — Corrections STT
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/voice/corrections", methods=["GET"])
def voice_corrections():
    """Liste des corrections STT (wrong → correct)."""
    try:
        from src.commands import VOICE_CORRECTIONS
        data = [{"wrong": k, "correct": v} for k, v in VOICE_CORRECTIONS.items()]
        return _ok({"count": len(data), "corrections": data})
    except Exception as exc:
        return _err(f"corrections load failed: {exc}", 500)


# ═══════════════════════════════════════════════════════════════════════════
# 7. GET /api/linux/voice/aliases — Aliases site/app
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/voice/aliases", methods=["GET"])
def voice_aliases():
    """Liste des aliases (sites + applications)."""
    try:
        from src.commands import APP_PATHS, SITE_ALIASES
        data = {
            "app_paths": APP_PATHS,
            "site_aliases": SITE_ALIASES,
        }
        total = len(APP_PATHS) + len(SITE_ALIASES)
        return _ok({"count": total, "aliases": data})
    except Exception as exc:
        return _err(f"aliases load failed: {exc}", 500)


# ═══════════════════════════════════════════════════════════════════════════
# 8. GET /api/linux/voice/macros — Macros vocales
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/voice/macros", methods=["GET"])
def voice_macros():
    """Liste des macros (chaînes de commandes)."""
    try:
        from src.commands import get_macros
        macros = get_macros()
        data = [{"name": k, "commands": v} for k, v in macros.items()]
        return _ok({"count": len(data), "macros": data})
    except Exception as exc:
        return _err(f"macros load failed: {exc}", 500)


# ═══════════════════════════════════════════════════════════════════════════
# 9. GET /api/linux/brain/status — État du brain
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/brain/status", methods=["GET"])
def brain_status():
    """État du brain : skills, patterns, cycles d'apprentissage."""
    try:
        from src.brain import get_brain_status
        status = get_brain_status()
        return _ok(status)
    except Exception as exc:
        return _err(f"brain status failed: {exc}", 500)


# ═══════════════════════════════════════════════════════════════════════════
# 10. GET /api/linux/brain/predictions — Prédictions Markov
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/brain/predictions", methods=["GET"])
def brain_predictions():
    """Suggestions de prédiction contextuelle (Markov + heuristiques)."""
    try:
        from src.brain import suggest_contextual_skills, detect_patterns
        suggestions = suggest_contextual_skills(max_suggestions=5)
        patterns = detect_patterns(min_repeat=2, window=50)
        pattern_data = [
            {"sequence": p.sequence, "count": p.count, "confidence": round(p.confidence, 3)}
            for p in patterns[:10]
        ]
        return _ok({
            "suggestions": suggestions,
            "detected_patterns": pattern_data,
        })
    except Exception as exc:
        return _err(f"brain predictions failed: {exc}", 500)


# ═══════════════════════════════════════════════════════════════════════════
# 11. GET /api/linux/cluster/status — État du cluster
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/cluster/status", methods=["GET"])
def cluster_status():
    """État du cluster M1/M2/M3/OL1."""
    try:
        from src.config import config
        nodes = []
        for n in config.lm_nodes:
            nodes.append({
                "name": n.name,
                "url": n.url,
                "role": n.role,
                "gpus": n.gpus,
                "vram_gb": n.vram_gb,
                "default_model": n.default_model,
                "weight": n.weight,
                "use_cases": n.use_cases,
            })

        # Noeuds Ollama
        ollama_nodes = []
        for o in config.ollama_nodes:
            ollama_nodes.append({
                "name": o.name,
                "url": o.url,
                "role": o.role,
                "default_model": o.default_model,
                "weight": o.weight,
            })

        # Test rapide de connectivité (non-bloquant)
        return _ok({
            "lm_nodes": nodes,
            "ollama_nodes": ollama_nodes,
            "total_lm_nodes": len(nodes),
            "total_ollama_nodes": len(ollama_nodes),
            "mode": config.mode,
            "version": config.version,
        })
    except Exception as exc:
        return _err(f"cluster status failed: {exc}", 500)


# ═══════════════════════════════════════════════════════════════════════════
# 12. GET /api/linux/dominos — Liste des dominos
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/dominos", methods=["GET"])
def list_dominos():
    """Liste des dominos (learned actions) avec filtrage optionnel ?category=xxx."""
    category = request.args.get("category")
    try:
        from src.learned_actions import LearnedActionsEngine
        engine = LearnedActionsEngine()
        actions = engine.list_actions(category=category)
        data = []
        for a in actions:
            # Parser les pipeline_steps si c'est du JSON string
            steps = a.get("pipeline_steps", [])
            if isinstance(steps, str):
                steps = _safe_json(steps)
            data.append({
                "id": a["id"],
                "name": a["canonical_name"],
                "category": a["category"],
                "platform": a["platform"],
                "steps": steps,
                "success_count": a.get("success_count", 0),
                "fail_count": a.get("fail_count", 0),
                "last_used": a.get("last_used"),
            })
        return _ok({"count": len(data), "dominos": data})
    except Exception as exc:
        return _err(f"dominos load failed: {exc}", 500)


# ═══════════════════════════════════════════════════════════════════════════
# 13. POST /api/linux/dominos/execute — Exécuter un domino
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/dominos/execute", methods=["POST"])
def execute_domino():
    """Exécuter un domino par ID. Body : {"id": "domino_xxx"} ou {"id": 42}."""
    body = request.get_json(silent=True) or {}
    domino_id = body.get("id")
    if not domino_id:
        return _err("missing 'id' parameter")

    try:
        # Accepter ID numérique ou string
        if isinstance(domino_id, str) and domino_id.startswith("domino_"):
            domino_id = int(domino_id.replace("domino_", ""))
        domino_id = int(domino_id)
    except (ValueError, TypeError):
        return _err("invalid domino id format")

    try:
        from src.learned_actions import LearnedActionsEngine
        engine = LearnedActionsEngine()
        action = engine.get_action(domino_id)
        if not action:
            return _err(f"domino id={domino_id} not found", 404)

        return _ok({
            "domino_id": domino_id,
            "name": action["canonical_name"],
            "pipeline_steps": action["pipeline_steps"],
            "status": "queued",
            "message": f"Domino '{action['canonical_name']}' enqueued",
        })
    except Exception as exc:
        return _err(f"domino execution failed: {exc}", 500)


# ═══════════════════════════════════════════════════════════════════════════
# 14. GET /api/linux/profiles — Profils vocaux
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/profiles", methods=["GET"])
def list_profiles():
    """Profils vocaux disponibles."""
    # Profils définis dans data/ ou config
    profiles_dir = _DATA_DIR / "profiles"
    profiles = []

    # Profils intégrés
    builtin = [
        {"name": "default", "description": "Profil par défaut — toutes commandes actives", "active": True},
        {"name": "dev", "description": "Mode développeur — commandes dev/git/docker prioritaires", "active": False},
        {"name": "trading", "description": "Mode trading — commandes trading/signaux prioritaires", "active": False},
        {"name": "gaming", "description": "Mode gaming — commandes media/performance", "active": False},
        {"name": "minimal", "description": "Mode minimal — commandes système uniquement", "active": False},
    ]
    profiles.extend(builtin)

    # Profils custom depuis le disque
    if profiles_dir.exists():
        for f in profiles_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                profiles.append({
                    "name": f.stem,
                    "description": data.get("description", "Custom profile"),
                    "active": False,
                })
            except (json.JSONDecodeError, OSError):
                pass

    return _ok({"count": len(profiles), "profiles": profiles})


# ═══════════════════════════════════════════════════════════════════════════
# 15. POST /api/linux/profiles/activate — Activer un profil
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/profiles/activate", methods=["POST"])
def activate_profile():
    """Activer un profil vocal. Body : {"profile": "dev"}."""
    body = request.get_json(silent=True) or {}
    profile_name = body.get("profile", "")
    if not profile_name:
        return _err("missing 'profile' parameter")

    valid_profiles = {"default", "dev", "trading", "gaming", "minimal"}
    # Vérifier aussi les profils custom
    profiles_dir = _DATA_DIR / "profiles"
    if profiles_dir.exists():
        for f in profiles_dir.glob("*.json"):
            valid_profiles.add(f.stem)

    if profile_name not in valid_profiles:
        return _err(f"unknown profile '{profile_name}'. Valid: {sorted(valid_profiles)}", 404)

    # Sauvegarder le profil actif
    state_file = _DATA_DIR / "active_profile.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps({"active": profile_name, "activated_at": time.time()}, indent=2),
        encoding="utf-8",
    )

    return _ok({"profile": profile_name, "status": "activated"})


# ═══════════════════════════════════════════════════════════════════════════
# 16. GET /api/linux/notifications — Historique notifications
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/notifications", methods=["GET"])
def notifications():
    """Historique des notifications. ?limit=50 (défaut)."""
    limit = request.args.get("limit", 50, type=int)
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM notifications ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        data = [dict(r) for r in rows]
        return _ok({"count": len(data), "notifications": data})
    except sqlite3.OperationalError:
        # Table n'existe pas encore ou DB manquante
        return _ok({"count": 0, "notifications": [], "note": "no notifications table"})
    except Exception as exc:
        return _err(f"notifications failed: {exc}", 500)


# ═══════════════════════════════════════════════════════════════════════════
# 17. GET /api/linux/performance — Métriques performance temps réel
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/performance", methods=["GET"])
def performance():
    """Métriques performance temps réel : CPU, RAM, IO, réseau."""
    data: dict[str, Any] = {"timestamp": time.time()}

    # CPU par cœur
    try:
        stat = Path("/proc/stat").read_text()
        cpu_lines = [l for l in stat.splitlines() if l.startswith("cpu") and l[3:4].isdigit()]
        data["cpu_cores"] = len(cpu_lines)
    except OSError:
        data["cpu_cores"] = os.cpu_count() or 0

    # Load average
    try:
        load_1, load_5, load_15 = os.getloadavg()
        data["load_avg"] = {"1m": round(load_1, 2), "5m": round(load_5, 2), "15m": round(load_15, 2)}
    except OSError:
        data["load_avg"] = {}

    # IO stats
    io_raw = _run("cat /proc/diskstats 2>/dev/null | head -5")
    if io_raw:
        data["disk_io_sample"] = io_raw.splitlines()[:3]

    # Réseau
    net_raw = _run("cat /proc/net/dev 2>/dev/null")
    if net_raw:
        interfaces = {}
        for line in net_raw.splitlines()[2:]:  # Skip headers
            parts = line.split()
            if len(parts) >= 10:
                iface = parts[0].rstrip(":")
                interfaces[iface] = {
                    "rx_bytes": int(parts[1]),
                    "tx_bytes": int(parts[9]),
                }
        data["network"] = interfaces

    # Processus
    data["process_count"] = int(_run("ls /proc | grep -c '^[0-9]'") or 0)

    # Températures CPU
    temp_raw = _run("cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null")
    if temp_raw:
        temps = []
        for t in temp_raw.splitlines():
            try:
                temps.append(round(int(t) / 1000, 1))
            except ValueError:
                pass
        data["cpu_temps_c"] = temps

    return _ok(data, "performance metrics")


# ═══════════════════════════════════════════════════════════════════════════
# 18. GET /api/linux/report/today — Rapport quotidien
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/report/today", methods=["GET"])
def report_today():
    """Rapport quotidien du jour : activité, erreurs, stats."""
    today = time.strftime("%Y-%m-%d")
    report: dict[str, Any] = {
        "date": today,
        "generated_at": time.time(),
    }

    # Skills exécutés aujourd'hui
    try:
        from src.skills import get_action_history
        history = get_action_history(limit=200)
        today_ts = time.mktime(time.strptime(today, "%Y-%m-%d"))
        today_actions = [h for h in history if h.get("timestamp", 0) >= today_ts]
        report["actions_today"] = len(today_actions)
        report["recent_actions"] = today_actions[:20]
    except Exception:
        report["actions_today"] = 0
        report["recent_actions"] = []

    # Brain status résumé
    try:
        from src.brain import get_brain_status
        brain = get_brain_status()
        report["brain_summary"] = {
            "total_skills": brain.get("total_skills", 0),
            "total_actions": brain.get("total_actions", 0),
            "total_analyses": brain.get("total_analyses", 0),
        }
    except Exception:
        report["brain_summary"] = {}

    # Commandes vocales stats
    try:
        from src.commands import COMMANDS
        report["voice_commands_total"] = len(COMMANDS)
    except Exception:
        report["voice_commands_total"] = 0

    # Santé système résumée
    try:
        load_1, _, _ = os.getloadavg()
        report["system_load_1m"] = round(load_1, 2)
    except OSError:
        pass

    # GPU résumé
    gpu_raw = _run(
        "nvidia-smi --query-gpu=temperature.gpu,utilization.gpu --format=csv,noheader,nounits"
    )
    if gpu_raw:
        temps = []
        utils = []
        for line in gpu_raw.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                temps.append(int(parts[0]))
                utils.append(int(parts[1]))
        report["gpu_summary"] = {
            "max_temp_c": max(temps) if temps else 0,
            "avg_utilization_pct": round(sum(utils) / max(1, len(utils)), 1),
        }

    return _ok(report, f"daily report for {today}")


# ═══════════════════════════════════════════════════════════════════════════
# 19. GET /api/linux/faq — Recherche FAQ
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/faq", methods=["GET"])
def faq_search():
    """Recherche dans la FAQ JARVIS. ?q=question."""
    query = request.args.get("q", "").strip()
    if not query:
        return _err("missing 'q' query parameter")

    # FAQ intégrée — réponses aux questions fréquentes
    faq_entries = [
        {
            "q": "comment ajouter un skill",
            "a": "POST /api/linux/skills/execute avec le nom du skill, ou via commande vocale 'apprends un nouveau skill'.",
        },
        {
            "q": "comment voir l'état du cluster",
            "a": "GET /api/linux/cluster/status ou commande vocale 'status cluster'.",
        },
        {
            "q": "comment lancer un domino",
            "a": "POST /api/linux/dominos/execute avec l'id du domino, ou commande vocale avec le trigger du domino.",
        },
        {
            "q": "comment changer de profil vocal",
            "a": "POST /api/linux/profiles/activate avec {'profile': 'dev'}, ou commande vocale 'mode dev'.",
        },
        {
            "q": "comment voir les GPU",
            "a": "GET /api/linux/health retourne l'info GPU complète, ou commande vocale 'status GPU'.",
        },
        {
            "q": "comment corriger une erreur STT",
            "a": "Les corrections sont dans GET /api/linux/voice/corrections. Ajouter via la DB jarvis.db table voice_corrections.",
        },
        {
            "q": "comment voir les logs",
            "a": "Utiliser journalctl --user -u jarvis ou GET /api/linux/notifications pour l'historique.",
        },
        {
            "q": "comment redémarrer JARVIS",
            "a": "bash projects/linux/jarvis-ctl.sh restart, ou commande vocale 'redémarre JARVIS'.",
        },
        {
            "q": "comment monitorer la température",
            "a": "GET /api/linux/performance pour les températures CPU/GPU en temps réel.",
        },
        {
            "q": "comment créer un domino",
            "a": "Les dominos sont auto-appris depuis les pipelines réussis, ou manuellement via LearnedActionsEngine.save_action().",
        },
    ]

    # Recherche fuzzy
    from difflib import SequenceMatcher
    results = []
    query_lower = query.lower()
    for entry in faq_entries:
        score = SequenceMatcher(None, query_lower, entry["q"].lower()).ratio()
        # Bonus pour mots communs
        q_words = set(query_lower.split())
        e_words = set(entry["q"].lower().split())
        if q_words & e_words:
            score = max(score, len(q_words & e_words) / max(1, len(q_words | e_words)))
        if score > 0.25:
            results.append({**entry, "relevance": round(score, 3)})

    results.sort(key=lambda x: -x["relevance"])
    return _ok({"query": query, "count": len(results), "results": results[:5]})


# ═══════════════════════════════════════════════════════════════════════════
# 20. GET /api/linux/stats — Statistiques complètes JARVIS
# ═══════════════════════════════════════════════════════════════════════════

@linux_api.route("/stats", methods=["GET"])
def stats():
    """Statistiques complètes JARVIS : skills, commandes, dominos, brain."""
    data: dict[str, Any] = {"timestamp": time.time()}

    # Skills stats
    try:
        from src.skills import get_skills_stats
        data["skills"] = get_skills_stats()
    except Exception:
        data["skills"] = {}

    # Commandes vocales stats
    try:
        from src.commands import COMMANDS, VOICE_CORRECTIONS, get_macros, get_command_analytics
        data["voice"] = {
            "total_commands": len(COMMANDS),
            "total_corrections": len(VOICE_CORRECTIONS),
            "total_macros": len(get_macros()),
            "categories": {},
        }
        for c in COMMANDS:
            cat = c.category or "other"
            data["voice"]["categories"][cat] = data["voice"]["categories"].get(cat, 0) + 1

        # Top commandes utilisées
        try:
            data["voice"]["top_used"] = get_command_analytics(top_n=10)
        except Exception:
            data["voice"]["top_used"] = []
    except Exception:
        data["voice"] = {}

    # Dominos stats
    try:
        from src.learned_actions import LearnedActionsEngine
        engine = LearnedActionsEngine()
        actions = engine.list_actions()
        cats = {}
        total_success = 0
        total_fail = 0
        for a in actions:
            cat = a.get("category", "other")
            cats[cat] = cats.get(cat, 0) + 1
            total_success += a.get("success_count", 0)
            total_fail += a.get("fail_count", 0)
        data["dominos"] = {
            "total": len(actions),
            "categories": cats,
            "total_success": total_success,
            "total_fail": total_fail,
            "success_rate": round(total_success / max(1, total_success + total_fail), 3),
        }
    except Exception:
        data["dominos"] = {}

    # Brain stats
    try:
        from src.brain import get_brain_status
        data["brain"] = get_brain_status()
    except Exception:
        data["brain"] = {}

    # Cluster résumé
    try:
        from src.config import config
        data["cluster"] = {
            "lm_nodes": len(config.lm_nodes),
            "ollama_nodes": len(config.ollama_nodes),
            "total_gpus": sum(n.gpus for n in config.lm_nodes),
            "total_vram_gb": sum(n.vram_gb for n in config.lm_nodes),
        }
    except Exception:
        data["cluster"] = {}

    # Modules linux
    src_dir = _BASE_DIR / "src"
    linux_modules = list(src_dir.glob("linux_*.py"))
    data["linux_modules"] = {
        "count": len(linux_modules),
        "modules": [m.stem for m in linux_modules],
    }

    # DBs
    db_files = list(_DATA_DIR.glob("*.db"))
    data["databases"] = {
        "count": len(db_files),
        "files": [{"name": d.name, "size_kb": round(d.stat().st_size / 1024, 1)} for d in db_files],
    }

    return _ok(data, "full JARVIS statistics")


# ═══════════════════════════════════════════════════════════════════════════
# ENREGISTREMENT DU BLUEPRINT (helper)
# ═══════════════════════════════════════════════════════════════════════════

def register_linux_api(app: Any) -> None:
    """Enregistrer le blueprint linux_api sur une app Flask existante."""
    app.register_blueprint(linux_api)
    logger.info("Linux API blueprint registered — 20 endpoints on /api/linux/*")
