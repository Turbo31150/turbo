"""Generate the full command list section for README.md."""
import sys
sys.path.insert(0, ".")
from src.commands import COMMANDS

# Group by category
cats: dict[str, list] = {}
for c in COMMANDS:
    cat = c.category
    if cat not in cats:
        cats[cat] = []
    cats[cat].append(c)

pipelines = [c for c in COMMANDS if c.action_type == "pipeline"]

lines = []
lines.append("")
lines.append("## 812 Commandes Vocales — Liste Complete")
lines.append("")
lines.append(f"**{len(COMMANDS)} commandes** au total dont **{len(pipelines)} pipelines** multi-etapes.")
lines.append(f"Reparties en **{len(cats)} categories**.")
lines.append("")
lines.append("| Categorie | Nb | Description |")
lines.append("|-----------|-----|------------|")
for cat in sorted(cats.keys()):
    cmds = cats[cat]
    lines.append(f"| **{cat}** | {len(cmds)} | {', '.join(c.name for c in cmds[:3])}... |")

lines.append("")
lines.append("<details>")
lines.append("<summary><strong>Liste complete des 812 commandes (cliquez pour derouler)</strong></summary>")
lines.append("")

for cat in sorted(cats.keys()):
    cmds = cats[cat]
    lines.append(f"### {cat.upper()} ({len(cmds)})")
    lines.append("")
    lines.append("| Commande | Type | Description | Triggers |")
    lines.append("|----------|------|-------------|----------|")
    for c in cmds:
        triggers = ", ".join(c.triggers[:2])
        lines.append(f"| `{c.name}` | {c.action_type} | {c.description} | {triggers} |")
    lines.append("")

lines.append("</details>")
lines.append("")

output = "\n".join(lines)
print(output)

# Also write to a temp file for easy inclusion
with open("data/readme_commands_section.md", "w", encoding="utf-8") as f:
    f.write(output)

print(f"\n--- Generated {len(lines)} lines for {len(COMMANDS)} commands ---", file=sys.stderr)
