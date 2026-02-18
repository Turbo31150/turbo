"""Sync database + generate teaching reference for qwen3-30b."""
import json
import time
from src.database import init_db, import_commands_from_code, import_skills_from_code, import_corrections_from_code, get_stats
from src.commands import COMMANDS
from src.config import SCRIPTS, PATHS, config

# Step 1: Init + sync DB
print("=== SYNC DATABASE ===")
init_db()
n_cmd = import_commands_from_code()
print(f"  Commandes importees: {n_cmd}")
n_skill = import_skills_from_code()
print(f"  Skills importes: {n_skill}")
n_corr = import_corrections_from_code()
print(f"  Corrections importees: {n_corr}")

stats = get_stats()
print(f"\n  DB Stats: {stats['commands']} cmds, {stats['skills']} skills, {stats['corrections']} corrections")

# Step 2: Generate teaching reference for qwen3-30b
print("\n=== GENERATION REFERENCE IA ===")

lines = []
lines.append(f"# JARVIS v{config.version} — Reference Commandes pour IA locale")
lines.append(f"# Genere le {time.strftime('%Y-%m-%d %H:%M')}")
lines.append(f"# {len(COMMANDS)} commandes, {len(SCRIPTS)} scripts, {len(PATHS)} projets")
lines.append("")

# Commands by category
categories = {}
for cmd in COMMANDS:
    categories.setdefault(cmd.category, []).append(cmd)

for cat, cmds in sorted(categories.items()):
    lines.append(f"\n## {cat.upper()} ({len(cmds)} commandes)")
    for cmd in cmds:
        triggers = ", ".join(cmd.triggers[:3])
        lines.append(f"- {cmd.name}: {cmd.description} | triggers: [{triggers}] | action: {cmd.action_type}:{cmd.action}")

# Scripts
lines.append(f"\n\n## SCRIPTS DISPONIBLES ({len(SCRIPTS)})")
for name, path in sorted(SCRIPTS.items()):
    status = "OK" if path.exists() else "ABSENT"
    lines.append(f"- {name}: {path} [{status}]")

# Routing
lines.append("\n\n## ROUTAGE IA")
for task_type, nodes in config.routing.items():
    lines.append(f"- {task_type}: {' -> '.join(nodes)}")

# Cluster
lines.append("\n\n## CLUSTER")
for n in config.lm_nodes:
    lines.append(f"- {n.name} ({n.url}): {n.role}, {n.gpus} GPU, {n.vram_gb}GB, model={n.default_model}")
for n in config.ollama_nodes:
    lines.append(f"- {n.name} ({n.url}): {n.role}, model={n.default_model}")

ref_text = "\n".join(lines)

# Save reference file
ref_path = "data/JARVIS_REFERENCE.md"
with open(ref_path, "w", encoding="utf-8") as f:
    f.write(ref_text)
print(f"  Reference sauvee: {ref_path} ({len(lines)} lignes)")

# Step 3: Generate compact JSON for M1 system prompt
compact = {
    "version": config.version,
    "commands_count": len(COMMANDS),
    "categories": {cat: [{"name": c.name, "triggers": c.triggers[:2], "action": c.action} for c in cmds] for cat, cmds in categories.items()},
    "scripts": list(SCRIPTS.keys()),
    "routing": config.routing,
}
compact_path = "data/jarvis_commands_compact.json"
with open(compact_path, "w", encoding="utf-8") as f:
    json.dump(compact, f, ensure_ascii=False, indent=1)
print(f"  Compact JSON: {compact_path}")

print("\n=== DONE ===")
print(f"  {n_cmd} commandes dans DB")
print(f"  Reference MD pour qwen3-30b prete")
print(f"  JSON compact pour system prompt pret")
