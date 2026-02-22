"""Generate full command catalog as detailed markdown tables."""
import sys
sys.path.insert(0, ".")

for mod in list(sys.modules.keys()):
    if "commands" in mod:
        del sys.modules[mod]

from src.commands import COMMANDS

# Organize by category
cats: dict[str, list] = {}
seen: set[str] = set()
for cmd in COMMANDS:
    if cmd.name in seen:
        continue
    seen.add(cmd.name)
    cat = cmd.category
    if cat not in cats:
        cats[cat] = []
    cats[cat].append(cmd)

# Category labels
cat_labels = {
    "systeme": "Systeme & Maintenance",
    "navigation": "Navigation Web",
    "dev": "Developpement & Outils",
    "pipeline": "Pipelines Multi-Etapes",
    "fenetre": "Gestion des Fenetres",
    "media": "Media & Volume",
    "application": "Applications",
    "browser": "Navigateur",
    "raccourci": "Raccourcis Clavier",
}

lines: list[str] = []
lines.append("# JARVIS Turbo — Catalogue Complet des Commandes Vocales")
lines.append("")
lines.append(f"> **{len(seen)} commandes** au total | Genere automatiquement le 2026-02-22")
lines.append("")

# Table of contents
lines.append("## Table des matieres")
lines.append("")
for cat in sorted(cats.keys()):
    label = cat_labels.get(cat, cat.title())
    count = len(cats[cat])
    pipes = len([c for c in cats[cat] if c.action_type == "pipeline"])
    anchor = label.lower().replace(" ", "-").replace("&", "").replace("/", "-")
    extra = f" ({pipes} pipelines)" if pipes else ""
    lines.append(f"- [{label}](#{anchor}) — {count} commandes{extra}")
lines.append("")
lines.append("---")
lines.append("")

# Each category
for cat in sorted(cats.keys()):
    label = cat_labels.get(cat, cat.title())
    cmds = cats[cat]
    lines.append(f"## {label}")
    lines.append("")
    lines.append(f"**{len(cmds)} commandes**")
    lines.append("")

    # Table header
    lines.append("| # | Nom | Description | Declencheurs | Type | Params | Confirm |")
    lines.append("|---|-----|-------------|--------------|------|--------|---------|")

    for i, cmd in enumerate(cmds, 1):
        triggers_list = ["`" + t + "`" for t in cmd.triggers[:3]]
        triggers = ", ".join(triggers_list)
        if len(cmd.triggers) > 3:
            triggers += f" +{len(cmd.triggers) - 3}"
        params = ", ".join(cmd.params) if cmd.params and isinstance(cmd.params, list) else "—"
        confirm = "Oui" if cmd.confirm else "—"
        desc = cmd.description.replace("|", "/")
        name = "`" + cmd.name + "`"
        atype = cmd.action_type
        lines.append(f"| {i} | {name} | {desc} | {triggers} | {atype} | {params} | {confirm} |")

    lines.append("")

# Summary stats
lines.append("---")
lines.append("")
lines.append("## Statistiques")
lines.append("")
lines.append("| Categorie | Commandes | Pipelines |")
lines.append("|-----------|-----------|-----------|")
total_cmds = 0
total_pipes = 0
for cat in sorted(cats.keys()):
    label = cat_labels.get(cat, cat.title())
    count = len(cats[cat])
    pipes = len([c for c in cats[cat] if c.action_type == "pipeline"])
    non_pipes = count - pipes
    total_cmds += non_pipes
    total_pipes += pipes
    lines.append(f"| {label} | {non_pipes} | {pipes} |")
lines.append(f"| **TOTAL** | **{total_cmds}** | **{total_pipes}** |")
lines.append("")
lines.append(f"> **Grand total: {total_cmds + total_pipes} commandes vocales**")
lines.append("")

content = "\n".join(lines)
with open("docs/CATALOGUE_COMMANDES.md", "w", encoding="utf-8") as f:
    f.write(content)
print(f"Generated {len(lines)} lines, {len(content)} chars")
print(f"{len(seen)} commands, {total_pipes} pipelines across {len(cats)} categories")
