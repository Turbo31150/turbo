"""Auto-generate COMMANDES_VOCALES.md from the COMMANDS list."""
import sys
sys.path.insert(0, "F:\\BUREAU\\turbo")

from src.commands import COMMANDS
from datetime import date

lines = []
lines.append("# Commandes Vocales JARVIS - Reference Complete")
lines.append("")
lines.append(f"> Mise a jour automatique: {date.today()} | Voice Pipeline v2")
lines.append("")

# Stats
total = len(COMMANDS)
cats = {}
for c in COMMANDS:
    cats[c.category] = cats.get(c.category, 0) + 1

pipeline_count = sum(1 for c in COMMANDS if c.action_type == "pipeline")

lines.append(f"**{total} commandes** au total, dont **{pipeline_count} pipelines** multi-etapes, reparties en **{len(cats)} categories**.")
lines.append("")
lines.append("| Categorie | Nombre |")
lines.append("|-----------|--------|")

cat_labels = {
    "systeme": "Systeme Windows",
    "navigation": "Navigation Web",
    "dev": "Developpement & Outils",
    "pipeline": "Pipelines Multi-Etapes",
    "fichiers": "Fichiers & Documents",
    "app": "Applications",
    "trading": "Trading & IA",
    "fenetre": "Fenetres Windows",
    "clipboard": "Presse-papier & Saisie",
    "jarvis": "Controle JARVIS",
    "launcher": "Launchers JARVIS",
    "accessibilite": "Accessibilite",
    "media": "Controle Media",
    "saisie": "Saisie & Texte",
}

for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
    label = cat_labels.get(cat, cat.title())
    lines.append(f"| {label} | {count} |")
lines.append(f"| **TOTAL** | **{total}** |")
lines.append("")
lines.append("---")
lines.append("")

# Pipelines section
lines.append("## Pipelines Multi-Etapes")
lines.append("")
lines.append("Les pipelines executent plusieurs actions en sequence (separees par `;;`).")
lines.append("")
lines.append("| Pipeline | Trigger principal | Actions |")
lines.append("|----------|------------------|---------|")

for c in COMMANDS:
    if c.action_type != "pipeline":
        continue
    steps = c.action.split(";;")
    action_parts = []
    for s in steps:
        s = s.strip()
        if s.startswith("app_open:"):
            action_parts.append(f"Ouvrir {s[9:]}")
        elif s.startswith("browser:navigate:"):
            action_parts.append(f"Web: {s[17:]}")
        elif s.startswith("sleep:"):
            action_parts.append(f"pause {s[6:]}s")
        elif s.startswith("hotkey:"):
            action_parts.append(f"Raccourci: {s[7:]}")
        elif s.startswith("ms_settings:"):
            action_parts.append("Settings")
        elif s.startswith("jarvis_tool:"):
            action_parts.append(f"Tool: {s[12:]}")
        elif "MinimizeAll" in s:
            action_parts.append("MinimizeAll")
        elif "LockWorkStation" in s:
            action_parts.append("Lock PC")
        elif "SetSuspendState" in s:
            action_parts.append("Veille")
        elif s.startswith("powershell:"):
            cmd = s[11:]
            if "Start-Process" in cmd and "comet" in cmd.lower():
                parts = cmd.split("'")
                url = parts[-2] if len(parts) >= 3 else "..."
                action_parts.append(f"Comet: {url}")
            elif len(cmd) > 60:
                action_parts.append(cmd[:50] + "...")
            else:
                action_parts.append(cmd)
        else:
            if len(s) > 60:
                action_parts.append(s[:50] + "...")
            else:
                action_parts.append(s)
    actions_str = " > ".join(action_parts)
    if len(actions_str) > 120:
        actions_str = actions_str[:117] + "..."
    confirm_str = " (confirm)" if c.confirm else ""
    lines.append(f'| {c.name} | "{c.triggers[0]}" | {actions_str}{confirm_str} |')

lines.append("")
lines.append("---")
lines.append("")

# Listing by category
lines.append("## Listing Complet par Categorie")
lines.append("")

cat_order = [
    "navigation", "fichiers", "app", "media", "fenetre", "clipboard",
    "systeme", "trading", "dev", "jarvis", "launcher", "accessibilite", "saisie",
]
for cat in cats:
    if cat not in cat_order:
        cat_order.append(cat)

for cat in cat_order:
    if cat not in cats:
        continue
    if cat == "pipeline":
        continue
    label = cat_labels.get(cat, cat.title())
    count = cats[cat]
    lines.append(f"### {label} ({count} commandes)")
    lines.append("")
    lines.append("| Commande | Description | Triggers | Type |")
    lines.append("|----------|------------|----------|------|")

    for c in COMMANDS:
        if c.category != cat:
            continue
        triggers_display = ", ".join(f'"{t}"' for t in c.triggers[:3])
        if len(c.triggers) > 3:
            triggers_display += f", +{len(c.triggers) - 3}"
        lines.append(f"| {c.name} | {c.description} | {triggers_display} | {c.action_type} |")

    lines.append("")

content = "\n".join(lines)

with open("F:\\BUREAU\\turbo\\docs\\COMMANDES_VOCALES.md", "w", encoding="utf-8") as f:
    f.write(content)

print(f"Generated {len(lines)} lines, {len(content)} chars")
print(f"{total} commandes documentees, {pipeline_count} pipelines")
