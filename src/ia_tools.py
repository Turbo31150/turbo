"""JARVIS IA Tools — OpenAI function-calling schemas for M1/OL1/Gemini.

These tool definitions follow the OpenAI tools format so that any model
supporting function calling (qwen3, deepseek-r1, gemini, claude) can
invoke JARVIS system actions through a standardised interface.

Usage:
    from src.ia_tools import TOOLS, TOOLS_BY_NAME, get_tools_for_scope

    # Inject into LM Studio / Ollama request:
    payload["tools"] = get_tools_for_scope("system")  # or "all"
"""
from __future__ import annotations

from typing import Any

# ── Tool definitions ─────────────────────────────────────────────────────────
# Each tool maps 1:1 to a JARVIS HTTP endpoint on port 9742.
# scope: which category the tool belongs to (system, autonomous, cluster,
#         memory, chat, trading, cowork, diagnostics)
# method/path: the HTTP verb + route to call

TOOLS: list[dict[str, Any]] = [
    # ── AUTONOMOUS (pilotage boucle autonome) ────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "jarvis_autonomous_status",
            "description": (
                "Obtenir le statut complet de la boucle autonome JARVIS: "
                "liste des 18 taches, derniers runs, erreurs, etat global. "
                "Appeler en premier pour diagnostiquer le systeme."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "GET", "path": "/api/autonomous/status", "scope": "autonomous"},
    },
    {
        "type": "function",
        "function": {
            "name": "jarvis_autonomous_events",
            "description": (
                "Recuperer les evenements recents de la boucle autonome "
                "(alertes, erreurs, timeouts). Utile pour comprendre "
                "pourquoi une tache a echoue."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Nombre max d'evenements a retourner (defaut: 50).",
                        "default": 50,
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "GET", "path": "/api/autonomous/events", "scope": "autonomous"},
    },
    {
        "type": "function",
        "function": {
            "name": "jarvis_run_task",
            "description": (
                "Executer immediatement une tache autonome par son nom. "
                "Noms valides: health_check, gpu_monitor, drift_reroute, "
                "zombie_gc, vram_audit, system_audit_escalation, "
                "cluster_dispatch_check, self_heal, brain_auto_learn, "
                "conversation_checkpoint, db_backup, predict_next_actions. "
                "N'utiliser que quand une raison claire existe."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_name": {
                        "type": "string",
                        "description": "Nom exact de la tache autonome.",
                    },
                },
                "required": ["task_name"],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "POST", "path": "/api/autonomous/run/{task_name}", "scope": "autonomous"},
    },
    {
        "type": "function",
        "function": {
            "name": "jarvis_toggle_task",
            "description": (
                "Activer ou desactiver une tache autonome. "
                "Utile pour couper temporairement une tache problematique."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_name": {
                        "type": "string",
                        "description": "Nom de la tache.",
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "true pour activer, false pour desactiver.",
                    },
                },
                "required": ["task_name", "enabled"],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "POST", "path": "/api/autonomous/toggle/{task_name}", "scope": "autonomous"},
    },

    # ── CLUSTER (sante noeuds, GPU, modeles) ─────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "jarvis_cluster_health",
            "description": (
                "Verifier la sante complete du cluster: noeuds M1/M2/M3/OL1, "
                "latences, modeles charges, GPU. Retourne un dashboard JSON."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "GET", "path": "/api/cluster/dashboard", "scope": "cluster"},
    },
    {
        "type": "function",
        "function": {
            "name": "jarvis_orchestrator_health",
            "description": (
                "Sante de l'orchestrateur: temps de reponse, taches en cours, "
                "budget API restant, noeuds actifs."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "GET", "path": "/api/orchestrator/health", "scope": "cluster"},
    },
    {
        "type": "function",
        "function": {
            "name": "jarvis_best_node",
            "description": (
                "Obtenir le meilleur noeud pour un type de tache donne. "
                "Le load balancer choisit selon latence, charge et poids."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_type": {
                        "type": "string",
                        "description": (
                            "Type de tache: code, reasoning, simple, "
                            "architecture, trading, math, security."
                        ),
                    },
                },
                "required": ["task_type"],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "GET", "path": "/api/orchestrator/best/{task_type}", "scope": "cluster"},
    },

    # ── DIAGNOSTICS ──────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "jarvis_diagnostics_quick",
            "description": (
                "Diagnostic rapide du systeme: services, ports, DB, "
                "GPU, processus. Resultat en <5 secondes."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "GET", "path": "/api/diagnostics/quick", "scope": "diagnostics"},
    },
    {
        "type": "function",
        "function": {
            "name": "jarvis_diagnostics_full",
            "description": (
                "Diagnostic complet: audit profond de tous les services, "
                "DB integrity, GPU, reseau. Peut prendre 10-30s."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "POST", "path": "/api/diagnostics/run", "scope": "diagnostics"},
    },

    # ── MEMORY (memoire persistante agent) ───────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "jarvis_remember",
            "description": (
                "Stocker une information en memoire persistante JARVIS. "
                "Categories: general, user_pref, system, trading, code."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Texte a memoriser.",
                    },
                    "category": {
                        "type": "string",
                        "description": "Categorie (general, user_pref, system, trading, code).",
                        "default": "general",
                    },
                    "importance": {
                        "type": "number",
                        "description": "Score d'importance 0.0 a 1.0.",
                        "default": 0.5,
                    },
                },
                "required": ["content"],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "POST", "path": "/api/memory/remember", "scope": "memory"},
    },
    {
        "type": "function",
        "function": {
            "name": "jarvis_recall",
            "description": (
                "Rechercher dans la memoire persistante par similarite. "
                "Retourne les souvenirs les plus pertinents."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Requete de recherche.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Nombre max de resultats.",
                        "default": 5,
                    },
                    "category": {
                        "type": "string",
                        "description": "Filtrer par categorie (optionnel).",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "GET", "path": "/api/memory/recall", "scope": "memory"},
    },

    # ── DB (sante bases de donnees) ──────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "jarvis_db_health",
            "description": (
                "Verifier l'integrite de toutes les bases SQLite JARVIS "
                "(etoile.db, jarvis.db, sniper.db, finetuning.db)."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "GET", "path": "/api/db/health", "scope": "system"},
    },
    {
        "type": "function",
        "function": {
            "name": "jarvis_db_maintenance",
            "description": (
                "Lancer la maintenance DB: VACUUM, reindex, WAL checkpoint. "
                "A faire periodiquement pour garder les bases optimales."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "POST", "path": "/api/db/maintenance", "scope": "system"},
    },

    # ── ALERTS ───────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "jarvis_alerts_active",
            "description": (
                "Lister les alertes actives (VRAM critique, noeud offline, "
                "service down, etc.)."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "GET", "path": "/api/alerts/active", "scope": "system"},
    },
    {
        "type": "function",
        "function": {
            "name": "jarvis_alert_acknowledge",
            "description": "Acquitter une alerte par sa cle.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Cle unique de l'alerte a acquitter.",
                    },
                },
                "required": ["key"],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "POST", "path": "/api/alerts/acknowledge", "scope": "system"},
    },

    # ── COWORK (execution scripts) ───────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "jarvis_cowork_execute",
            "description": (
                "Executer un script cowork par son nom. Les scripts sont "
                "dans cowork/dev/ (438 scripts disponibles). "
                "ATTENTION: verifier le nom exact via jarvis_cowork_search."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "Nom du script (ex: 'gpu_benchmark.py').",
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Arguments a passer au script.",
                        "default": [],
                    },
                },
                "required": ["script"],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "POST", "path": "/api/cowork/execute", "scope": "cowork"},
    },
    {
        "type": "function",
        "function": {
            "name": "jarvis_cowork_search",
            "description": (
                "Rechercher un script cowork par mot-cle. Retourne les noms "
                "et descriptions des scripts correspondants."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Mot-cle de recherche.",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "GET", "path": "/api/cowork/search", "scope": "cowork"},
    },

    # ── PIPELINES (composition et execution) ─────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "jarvis_pipeline_execute",
            "description": (
                "Executer un pipeline compose par son nom. Les pipelines "
                "sont des sequences de prompts envoyes a differents noeuds."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nom du pipeline a executer.",
                    },
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "POST", "path": "/api/pipelines/execute", "scope": "system"},
    },

    # ── CHAT (envoyer un message dans le WS JARVIS) ─────────────────────
    {
        "type": "function",
        "function": {
            "name": "jarvis_send_message",
            "description": (
                "Envoyer un message dans le chat JARVIS et recevoir la reponse "
                "de l'assistant. Utile pour deleguer une question a un autre "
                "modele via l'orchestrateur JARVIS."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Contenu du message a envoyer.",
                    },
                },
                "required": ["content"],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "POST", "path": "/api/chat/send", "scope": "chat"},
    },

    # ── INTENT (classification) ──────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "jarvis_classify_intent",
            "description": (
                "Classifier l'intention d'un texte utilisateur. Retourne "
                "le type de tache detecte (code, trading, simple, etc.) "
                "et le score de confiance."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Texte a classifier.",
                    },
                },
                "required": ["text"],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "GET", "path": "/api/intent/classify", "scope": "system"},
    },

    # ── BOOT (verification/relance systeme) ──────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "jarvis_boot_status",
            "description": (
                "Obtenir le statut complet du boot JARVIS: noeuds, services, "
                "GPU, bases de donnees, disques. Equivalent de --status sans demarrer."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "GET", "path": "/api/boot/status", "scope": "system"},
    },
    {
        "type": "function",
        "function": {
            "name": "jarvis_boot_phase",
            "description": (
                "Lancer une phase specifique du boot JARVIS. "
                "Phase 1: Infrastructure, 2: Modeles, 3: Services Node, "
                "4: Services Python, 5: Watchdogs, 6: Validation. "
                "ATTENTION: operation lourde, utiliser avec precaution."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "phase": {
                        "type": "string",
                        "description": "Phase(s) a lancer (ex: '1', '1-3', '6').",
                        "default": "6",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "POST", "path": "/api/boot/phase", "scope": "system"},
    },

    # ── GPU (monitoring direct) ──────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "jarvis_gpu_status",
            "description": (
                "Obtenir le statut GPU detaille: VRAM usage, temperature, "
                "par GPU (RTX 2060, GTX 1660 SUPER, etc.)."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
        "_meta": {"method": "GET", "path": "/api/metrics/snapshot", "scope": "cluster"},
    },
]

# ── Index by name ────────────────────────────────────────────────────────────
TOOLS_BY_NAME: dict[str, dict] = {t["function"]["name"]: t for t in TOOLS}

# ── MCP Annotations (readOnlyHint / destructiveHint per MCP spec) ────────────
# Applied to get_mcp_tools_manifest() output for proper MCP client behavior.
_MCP_ANNOTATIONS: dict[str, dict] = {
    # Read-only tools (safe to call anytime, no side effects)
    "jarvis_autonomous_status": {"readOnlyHint": True},
    "jarvis_autonomous_events": {"readOnlyHint": True},
    "jarvis_cluster_health": {"readOnlyHint": True},
    "jarvis_orchestrator_health": {"readOnlyHint": True},
    "jarvis_best_node": {"readOnlyHint": True},
    "jarvis_diagnostics_quick": {"readOnlyHint": True},
    "jarvis_db_health": {"readOnlyHint": True},
    "jarvis_alerts_active": {"readOnlyHint": True},
    "jarvis_recall": {"readOnlyHint": True},
    "jarvis_cowork_search": {"readOnlyHint": True},
    "jarvis_classify_intent": {"readOnlyHint": True},
    "jarvis_boot_status": {"readOnlyHint": True},
    "jarvis_gpu_status": {"readOnlyHint": True},
    # Destructive tools (require explicit confirmation)
    "jarvis_cowork_execute": {"destructiveHint": True},
    "jarvis_db_maintenance": {"destructiveHint": True},
    "jarvis_pipeline_execute": {"destructiveHint": True},
    # Mutating but non-destructive (state-changing, idempotent)
    "jarvis_run_task": {"readOnlyHint": False},
    "jarvis_toggle_task": {"readOnlyHint": False},
    "jarvis_remember": {"readOnlyHint": False},
    "jarvis_alert_acknowledge": {"readOnlyHint": False},
    "jarvis_send_message": {"readOnlyHint": False},
    "jarvis_diagnostics_full": {"readOnlyHint": False},
    "jarvis_boot_phase": {"readOnlyHint": False, "destructiveHint": False},
}

# ── Scopes ───────────────────────────────────────────────────────────────────
_SCOPES: dict[str, list[str]] = {}
for _t in TOOLS:
    _scope = _t.get("_meta", {}).get("scope", "system")
    _SCOPES.setdefault(_scope, []).append(_t["function"]["name"])


def get_tools_for_scope(scope: str = "all") -> list[dict]:
    """Return tools filtered by scope.

    scope="all" returns everything.
    scope="system" returns system+autonomous+cluster+diagnostics.
    scope="minimal" returns only autonomous_status + diagnostics_quick + alerts.
    """
    if scope == "all":
        return [{k: v for k, v in t.items() if k != "_meta"} for t in TOOLS]

    if scope == "minimal":
        minimal_names = {
            "jarvis_autonomous_status", "jarvis_diagnostics_quick",
            "jarvis_alerts_active", "jarvis_cluster_health",
        }
        return [
            {k: v for k, v in t.items() if k != "_meta"}
            for t in TOOLS if t["function"]["name"] in minimal_names
        ]

    # Filter by scope name
    names = set()
    if scope == "system":
        for s in ("system", "autonomous", "cluster", "diagnostics"):
            names.update(_SCOPES.get(s, []))
    else:
        names.update(_SCOPES.get(scope, []))

    return [
        {k: v for k, v in t.items() if k != "_meta"}
        for t in TOOLS if t["function"]["name"] in names
    ]


def get_tool_meta(tool_name: str) -> dict:
    """Return the HTTP method + path for a tool."""
    tool = TOOLS_BY_NAME.get(tool_name)
    if not tool:
        return {}
    return tool.get("_meta", {})
