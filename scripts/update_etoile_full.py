"""Update etoile.db with FULL detail: categories, all commands, pipelines, MCP tools."""
import sqlite3
import json
import os
import sys
import shutil

sys.path.insert(0, ".")
for mod in list(sys.modules.keys()):
    if "commands" in mod:
        del sys.modules[mod]

from src.commands import COMMANDS

# ── Organize commands ──
cats: dict[str, list] = {}
seen: set[str] = set()
ordered_cmds = []
for cmd in COMMANDS:
    if cmd.name in seen:
        continue
    seen.add(cmd.name)
    cat = cmd.category
    if cat not in cats:
        cats[cat] = []
    cats[cat].append(cmd)
    ordered_cmds.append(cmd)

cat_labels = {
    "systeme": "Systeme & Maintenance",
    "navigation": "Navigation Web",
    "dev": "Developpement & Outils",
    "pipeline": "Pipelines Multi-Etapes",
    "fenetre": "Gestion des Fenetres",
    "media": "Media & Volume",
    "app": "Applications",
    "browser": "Navigateur",
    "raccourci": "Raccourcis Clavier",
    "saisie": "Saisie & Texte",
    "clipboard": "Presse-papier",
    "fichiers": "Fichiers & Dossiers",
    "accessibilite": "Accessibilite",
    "jarvis": "JARVIS Controle",
    "launcher": "Launchers",
    "trading": "Trading",
}

# ── 74 MCP Tools (parsed from src/tools.py) ──
MCP_TOOLS = [
    ("lm_query", "Interroger un noeud LM Studio", "cluster", "prompt,node,model,mode"),
    ("lm_mcp_query", "Interroger M1/M2 avec serveurs MCP", "cluster", "prompt,node,model,servers,allowed_tools,context_length"),
    ("lm_list_mcp_servers", "Lister les serveurs MCP disponibles", "cluster", ""),
    ("gemini_query", "Interroger Gemini via proxy", "cluster", "prompt,model,json_mode"),
    ("bridge_query", "Routage intelligent vers le meilleur noeud", "cluster", "prompt,task_type,preferred_node"),
    ("bridge_mesh", "Requete parallele sur N noeuds", "cluster", "prompt,nodes,timeout_per_node"),
    ("lm_models", "Lister les modeles charges sur un noeud", "cluster", "node"),
    ("lm_cluster_status", "Sante de tous les noeuds du cluster", "cluster", ""),
    ("consensus", "Consensus multi-noeuds IA", "cluster", "prompt,nodes,timeout_per_node"),
    ("lm_load_model", "Charger un modele sur M1", "cluster", "model,context,parallel"),
    ("lm_unload_model", "Decharger un modele de M1", "cluster", "model"),
    ("lm_switch_coder", "Basculer M1 en mode code", "cluster", ""),
    ("lm_switch_dev", "Basculer M1 en mode dev", "cluster", ""),
    ("lm_gpu_stats", "Statistiques GPU detaillees", "cluster", ""),
    ("lm_benchmark", "Benchmark latence M1/M2/OL1", "cluster", "nodes"),
    ("lm_perf_metrics", "Metriques de performance du cluster", "cluster", ""),
    ("ollama_query", "Interroger Ollama local ou cloud", "ollama", "prompt,model"),
    ("ollama_models", "Lister les modeles Ollama disponibles", "ollama", ""),
    ("ollama_pull", "Telecharger un modele Ollama", "ollama", "model_name"),
    ("ollama_status", "Sante du backend Ollama", "ollama", ""),
    ("ollama_web_search", "Recherche web via Ollama cloud", "ollama", "query,model"),
    ("ollama_subagents", "3 sous-agents Ollama cloud en parallele", "ollama", "task,aspects"),
    ("ollama_trading_analysis", "Analyse trading parallele 3 sous-agents", "ollama", "pair,timeframe"),
    ("run_script", "Executer un script Python indexe", "scripts", "script_name,args"),
    ("list_scripts", "Lister les scripts Python disponibles", "scripts", ""),
    ("list_project_paths", "Lister les dossiers projets indexes", "scripts", ""),
    ("open_app", "Ouvrir une application par nom", "apps", "name,args"),
    ("close_app", "Fermer une application par processus", "apps", "name"),
    ("open_url", "Ouvrir une URL dans le navigateur", "apps", "url,browser"),
    ("list_processes", "Lister les processus Windows", "system", "filter"),
    ("kill_process", "Arreter un processus par nom ou PID", "system", "target"),
    ("list_windows", "Lister toutes les fenetres visibles", "windows", ""),
    ("focus_window", "Mettre une fenetre au premier plan", "windows", "title"),
    ("minimize_window", "Minimiser une fenetre", "windows", "title"),
    ("maximize_window", "Maximiser une fenetre", "windows", "title"),
    ("send_keys", "Envoyer des touches clavier", "input", "keys"),
    ("type_text", "Taper du texte dans la fenetre active", "input", "text"),
    ("press_hotkey", "Appuyer sur un raccourci clavier", "input", "keys"),
    ("mouse_click", "Cliquer a des coordonnees ecran", "input", "x,y"),
    ("clipboard_get", "Lire le contenu du presse-papier", "clipboard", ""),
    ("clipboard_set", "Ecrire dans le presse-papier", "clipboard", "text"),
    ("open_folder", "Ouvrir un dossier dans Explorateur", "files", "path"),
    ("list_folder", "Lister le contenu d'un dossier", "files", "path,pattern"),
    ("create_folder", "Creer un nouveau dossier", "files", "path"),
    ("copy_item", "Copier un fichier ou dossier", "files", "source,dest"),
    ("move_item", "Deplacer un fichier ou dossier", "files", "source,dest"),
    ("delete_item", "Supprimer un fichier vers la corbeille", "files", "path"),
    ("read_text_file", "Lire un fichier texte", "files", "path,lines"),
    ("write_text_file", "Ecrire dans un fichier texte", "files", "path,content"),
    ("search_files", "Chercher des fichiers recursivement", "files", "path,pattern"),
    ("volume_up", "Augmenter le volume systeme", "media", ""),
    ("volume_down", "Baisser le volume systeme", "media", ""),
    ("volume_mute", "Basculer muet/son", "media", ""),
    ("screenshot", "Prendre une capture d'ecran", "screen", "filename"),
    ("screen_resolution", "Obtenir la resolution ecran", "screen", ""),
    ("system_info", "Infos systeme completes CPU/RAM/GPU", "system", ""),
    ("gpu_info", "Infos detaillees GPU VRAM/driver", "system", ""),
    ("network_info", "Adresses IP et interfaces reseau", "system", ""),
    ("powershell_run", "Executer une commande PowerShell", "system", "command"),
    ("lock_screen", "Verrouiller le PC", "system", ""),
    ("shutdown_pc", "Eteindre le PC", "system", ""),
    ("restart_pc", "Redemarrer le PC", "system", ""),
    ("sleep_pc", "Mettre le PC en veille", "system", ""),
    ("list_services", "Lister les services Windows", "system", "filter"),
    ("start_service", "Demarrer un service Windows", "system", "name"),
    ("stop_service", "Arreter un service Windows", "system", "name"),
    ("wifi_networks", "Lister les reseaux WiFi disponibles", "network", ""),
    ("ping", "Ping un hote", "network", "host"),
    ("get_ip", "Obtenir les adresses IP locales", "network", ""),
    ("registry_read", "Lire une valeur du registre Windows", "registry", "path,name"),
    ("registry_write", "Ecrire une valeur dans le registre", "registry", "path,name,value,type"),
    ("notify", "Notification toast Windows", "ui", "title,message"),
    ("speak", "Synthese vocale Windows SAPI", "ui", "text"),
    ("scheduled_tasks", "Lister les taches planifiees Windows", "system", "filter"),
]

# ── Connect to etoile.db ──
try:
    from src.config import PATHS
    DB_PATH = str(PATHS["etoile_db"])
except ImportError:
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "etoile.db")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# ── Clean old entries ──
old_types = [
    "vocal_command", "vocal_pipeline", "vocal_category",
    "mcp_tool", "vocal_stats",
]
for t in old_types:
    cur.execute("DELETE FROM map WHERE entity_type = ?", (t,))
    print(f"  Cleared: {t} ({cur.rowcount} rows)")

# ── Insert vocal categories ──
for cat in sorted(cats.keys()):
    label = cat_labels.get(cat, cat.title())
    cmds_in_cat = cats[cat]
    pipe_count = len([c for c in cmds_in_cat if c.action_type == "pipeline"])
    cmd_count = len(cmds_in_cat) - pipe_count
    cmd_names = [c.name for c in cmds_in_cat]
    metadata = json.dumps({
        "label": label,
        "total": len(cmds_in_cat),
        "commands": cmd_count,
        "pipelines": pipe_count,
        "command_list": cmd_names,
    }, ensure_ascii=False)
    cur.execute(
        "INSERT OR REPLACE INTO map (entity_type, entity_name, role, parent, metadata) VALUES (?, ?, ?, ?, ?)",
        ("vocal_category", cat, label, "jarvis_vocal", metadata),
    )
print(f"  Inserted: {len(cats)} vocal_category entries")

# ── Insert all vocal commands and pipelines ──
cmd_count = 0
pipe_count = 0
for cmd in ordered_cmds:
    is_pipeline = cmd.action_type == "pipeline"
    entity_type = "vocal_pipeline" if is_pipeline else "vocal_command"
    triggers = cmd.triggers[:5] if cmd.triggers else []
    params = cmd.params if isinstance(cmd.params, list) else []

    # Build rich metadata
    meta = {
        "description": cmd.description,
        "triggers": triggers,
        "trigger_count": len(cmd.triggers) if cmd.triggers else 0,
        "action_type": cmd.action_type,
        "category": cmd.category,
        "category_label": cat_labels.get(cmd.category, cmd.category.title()),
        "params": params,
        "confirm": cmd.confirm,
    }

    # For pipelines, count steps
    if is_pipeline and isinstance(cmd.action, str):
        steps = [s.strip() for s in cmd.action.split(";;") if s.strip()]
        meta["step_count"] = len(steps)
        # Classify step types
        step_types = set()
        for s in steps:
            if ":" in s:
                step_types.add(s.split(":")[0])
        meta["step_types"] = sorted(step_types)

    # Add action preview (truncated for readability)
    if isinstance(cmd.action, str):
        action_preview = cmd.action[:200]
        if len(cmd.action) > 200:
            action_preview += "..."
        meta["action_preview"] = action_preview

    metadata_json = json.dumps(meta, ensure_ascii=False)
    role = cmd.description[:80]
    parent = cmd.category

    cur.execute(
        "INSERT OR REPLACE INTO map (entity_type, entity_name, role, parent, metadata) VALUES (?, ?, ?, ?, ?)",
        (entity_type, cmd.name, role, parent, metadata_json),
    )
    if is_pipeline:
        pipe_count += 1
    else:
        cmd_count += 1

print(f"  Inserted: {cmd_count} vocal_command + {pipe_count} vocal_pipeline entries")

# ── Insert MCP tools ──
for tool_name, description, group, params_str in MCP_TOOLS:
    params = [p for p in params_str.split(",") if p] if params_str else []
    metadata = json.dumps({
        "description": description,
        "group": group,
        "params": params,
        "param_count": len(params),
        "source": "src/tools.py",
        "sdk": "claude_agent_sdk",
    }, ensure_ascii=False)
    cur.execute(
        "INSERT OR REPLACE INTO map (entity_type, entity_name, role, parent, metadata) VALUES (?, ?, ?, ?, ?)",
        ("mcp_tool", tool_name, description, group, metadata),
    )
print(f"  Inserted: {len(MCP_TOOLS)} mcp_tool entries")

# ── Insert summary stats ──
total_commands = cmd_count
total_pipelines = pipe_count
total_mcp = len(MCP_TOOLS)
stats_meta = json.dumps({
    "total_commands": total_commands,
    "total_pipelines": total_pipelines,
    "total_mcp_tools": total_mcp,
    "grand_total": total_commands + total_pipelines + total_mcp,
    "categories": len(cats),
    "category_breakdown": {
        cat_labels.get(cat, cat.title()): len(cats[cat])
        for cat in sorted(cats.keys())
    },
    "version": "v10.3",
    "date": "2026-02-22",
}, ensure_ascii=False)
cur.execute(
    "INSERT OR REPLACE INTO map (entity_type, entity_name, role, parent, metadata) VALUES (?, ?, ?, ?, ?)",
    ("vocal_stats", "jarvis_vocal_stats", "Statistiques vocales JARVIS", "jarvis", stats_meta),
)
print(f"  Inserted: vocal_stats summary")

conn.commit()

# ── Count total entries ──
cur.execute("SELECT COUNT(*) FROM map")
total = cur.fetchone()[0]

# ── Show breakdown by entity_type ──
cur.execute("SELECT entity_type, COUNT(*) FROM map GROUP BY entity_type ORDER BY COUNT(*) DESC")
print(f"\n{'='*50}")
print(f"  etoile.db — {total} entries total")
print(f"{'='*50}")
for row in cur.fetchall():
    print(f"  {row[0]:25s} {row[1]:>5d}")
print(f"{'='*50}")

conn.close()

# ── Ensure data/ copy is up to date ──
DEST = str(PATHS["etoile_db"]) if 'PATHS' in dir() else os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "etoile.db")
if os.path.abspath(DB_PATH) != os.path.abspath(DEST):
    shutil.copy2(DB_PATH, DEST)
    print(f"\nCopied to {DEST}")
else:
    print(f"\nDB already at {DEST}")
print(f"DONE — {total} entries ({total_commands} commands + {total_pipelines} pipelines + {total_mcp} MCP tools + {len(cats)} categories + stats)")
