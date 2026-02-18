"""Generate ultra-compact command reference for M1 system prompt (~3KB)."""
from src.commands import COMMANDS
from src.config import SCRIPTS, config

lines = []
lines.append(f"JARVIS v{config.version} | {len(COMMANDS)} cmds vocales | {len(SCRIPTS)} scripts | Cluster M1+M2+OL1")
lines.append("Tu es le cerveau local de JARVIS. Analyse les demandes vocales et identifie l'action.")
lines.append("")

# Group by category — top 5 per category
categories = {}
for cmd in COMMANDS:
    categories.setdefault(cmd.category, []).append(cmd)

for cat, cmds in sorted(categories.items()):
    # Format: command_name=trigger for M1 to learn the mapping
    top = [f"{c.name}={c.triggers[0]}" for c in cmds[:8]]
    extra = f" +{len(cmds)-8}" if len(cmds) > 8 else ""
    lines.append(f"{cat}({len(cmds)}): {' | '.join(top)}{extra}")

lines.append("")
lines.append(f"scripts({len(SCRIPTS)}): {', '.join(sorted(SCRIPTS.keys()))}")
lines.append(f"routage: " + " | ".join(f"{k}>{','.join(v)}" for k, v in config.routing.items()))
lines.append("")
lines.append("Si la demande correspond a une commande, reponds: ACTION=nom_commande")
lines.append("Si besoin d'un outil systeme: OUTIL=nom_outil(args)")
lines.append("Sinon reponds directement en francais, concis (2-3 phrases).")

text = "\n".join(lines)
with open("data/jarvis_m1_prompt.txt", "w", encoding="utf-8") as f:
    f.write(text)
print(f"Prompt M1: {len(text)} chars ({len(text)/1024:.1f} KB)")
print()
print(text)
