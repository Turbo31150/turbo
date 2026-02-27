import re, sqlite3, os
os.chdir(r"F:\BUREAU\turbo")

def count_cmds(fp):
    with open(fp, encoding="utf-8") as f:
        return len(re.findall(r'JarvisCommand\(', f.read()))

def extract(fp):
    with open(fp, encoding="utf-8") as f:
        c = f.read()
    return re.findall(r'JarvisCommand\("([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*\[(.*?)\],\s*"([^"]+)"', c, re.DOTALL)

files = {
    "commands.py": "src/commands.py",
    "commands_pipelines.py": "src/commands_pipelines.py",
    "commands_dev.py": "src/commands_dev.py",
    "commands_maintenance.py": "src/commands_maintenance.py",
    "commands_navigation.py": "src/commands_navigation.py"
}

counts = {k: count_cmds(v) for k, v in files.items()}
total = sum(counts.values())

cmds = {}
for k, v in files.items():
    cmds[k] = extract(v)

conn = sqlite3.connect("data/etoile.db")
cur = conn.cursor()

cur.execute('SELECT entity_name, parent, role FROM map WHERE entity_type="skill" ORDER BY parent')
skills = cur.fetchall()
cur.execute('SELECT entity_name, parent, role FROM map WHERE entity_type="tool" ORDER BY parent')
tools = cur.fetchall()
cur.execute('SELECT entity_name, role FROM map WHERE entity_type="workflow"')
workflows = cur.fetchall()
cur.execute('SELECT entity_name, parent, role FROM map WHERE entity_type="routing_rule"')
routes = cur.fetchall()
cur.execute('SELECT entity_name, role FROM map WHERE entity_type="launcher"')
launchers = cur.fetchall()
cur.execute('SELECT entity_name, parent, role FROM map WHERE entity_type="script"')
scripts = cur.fetchall()
cur.execute('SELECT * FROM agents')
agents = cur.fetchall()
cur.execute('SELECT category, key, value, confidence FROM memories ORDER BY category')
memories = cur.fetchall()
conn.close()

md = []

md.append(f"""# JARVIS Etoile v10.3 - Documentation Complete

> **{total} commandes vocales - {len(cmds["commands_pipelines.py"])} pipelines - {len(skills)} skills - {len(tools)} outils MCP**
>
> Genere automatiquement depuis le code source et la base etoile.db

---

## Chiffres Cles

| Metrique | Valeur | Source |
|----------|--------|--------|
| **Commandes vocales** | **{total}** | 5 fichiers Python |
| Commandes principales | {counts["commands.py"]} | commands.py |
| Pipelines multi-etapes | {counts["commands_pipelines.py"]} | commands_pipelines.py |
| Commandes dev | {counts["commands_dev.py"]} | commands_dev.py |
| Commandes maintenance | {counts["commands_maintenance.py"]} | commands_maintenance.py |
| Commandes navigation | {counts["commands_navigation.py"]} | commands_navigation.py |
| Skills autonomes (DB) | {len(skills)} | etoile.db |
| Outils MCP | {len(tools)} | etoile.db |
| Workflows n8n | {len(workflows)} | etoile.db |
| Launchers | {len(launchers)} | etoile.db |
| Scripts | {len(scripts)} | etoile.db |
| Regles de routage | {len(routes)} | etoile.db |

---
""")

def trigs(raw):
    return [t.strip().strip('"').strip("'") for t in raw.split(',') if t.strip() and 'JarvisCommand' not in t]

def group_by_cat(data):
    cats = {}
    for name, cat, desc, tr, atype in data:
        cats.setdefault(cat, []).append((name, desc, trigs(tr)[:3]))
    return cats

def write_cat_tables(md, grouped, section_title, count, source):
    md.append(f"## {section_title} ({count} commandes)\n")
    md.append(f"Fichier : `{source}`\n")
    for cat in sorted(grouped.keys()):
        items = grouped[cat]
        md.append(f"\n### {cat.upper()} ({len(items)})\n")
        md.append("| Commande | Description | Declencheurs |")
        md.append("|----------|-------------|-------------|")
        for name, desc, trs in items:
            t = ", ".join(trs[:2]) if trs else "-"
            md.append(f"| `{name}` | {desc} | {t} |")
    md.append("")

# 1. MAIN COMMANDS
main_g = group_by_cat(cmds["commands.py"])
write_cat_tables(md, main_g, "1. Commandes Vocales Principales", counts["commands.py"], "src/commands.py")

# 2. PIPELINES
md.append("---\n")
md.append(f"## 2. Pipelines Multi-Etapes ({counts['commands_pipelines.py']} pipelines)\n")
md.append("Fichier : `src/commands_pipelines.py`\n")
pipe_g = {}
for name, cat, desc, tr, atype in cmds["commands_pipelines.py"]:
    if name.startswith("sim_"): g = "SIMULATIONS"
    elif name.startswith("mode_"): g = "MODES"
    elif "routine" in name or name.startswith("fin_") or name.startswith("pause_"): g = "ROUTINES"
    elif name.startswith("dev_") or "pomodoro" in name: g = "DEV"
    elif name.startswith("ouvre_"): g = "NAVIGATION"
    elif any(x in name for x in ["trading","crypto","scalp"]): g = "TRADING"
    elif any(x in name for x in ["nettoyage","diagnostic","maintenance","audit","backup","rapport"]): g = "MAINTENANCE"
    else: g = "AUTRES"
    pipe_g.setdefault(g, []).append((name, desc))

for g in ["MODES","ROUTINES","DEV","TRADING","MAINTENANCE","NAVIGATION","SIMULATIONS","AUTRES"]:
    if g not in pipe_g: continue
    items = pipe_g[g]
    md.append(f"\n### {g} ({len(items)})\n")
    md.append("| Pipeline | Description |")
    md.append("|----------|-------------|")
    for name, desc in items:
        md.append(f"| `{name}` | {desc} |")
md.append("")

# 3. DEV COMMANDS
md.append("---\n")
dev_g = group_by_cat(cmds["commands_dev.py"])
write_cat_tables(md, dev_g, "3. Commandes Dev", counts["commands_dev.py"], "src/commands_dev.py")

# 4. MAINTENANCE
md.append("---\n")
maint_g = group_by_cat(cmds["commands_maintenance.py"])
write_cat_tables(md, maint_g, "4. Commandes Maintenance", counts["commands_maintenance.py"], "src/commands_maintenance.py")

# 5. NAVIGATION
md.append("---\n")
nav_g = group_by_cat(cmds["commands_navigation.py"])
write_cat_tables(md, nav_g, "5. Commandes Navigation", counts["commands_navigation.py"], "src/commands_navigation.py")

# 6. SKILLS
md.append("---\n")
md.append(f"## 6. Skills Autonomes ({len(skills)} skills - etoile.db)\n")
skill_cats = {}
for name, parent, role in skills:
    skill_cats.setdefault(parent, []).append((name, role))
for cat in sorted(skill_cats.keys()):
    items = skill_cats[cat]
    md.append(f"\n### {cat.upper()} ({len(items)})\n")
    md.append("| Skill | Description |")
    md.append("|-------|-------------|")
    for name, role in items:
        md.append(f"| `{name}` | {role} |")
md.append("")

# 7. MCP TOOLS
md.append("---\n")
md.append(f"## 7. Outils MCP ({len(tools)} outils)\n")
tool_cats = {}
for name, parent, role in tools:
    tool_cats.setdefault(parent, []).append((name, role))
for cat in sorted(tool_cats.keys()):
    items = tool_cats[cat]
    md.append(f"\n### {cat.upper()} ({len(items)})\n")
    md.append("| Outil | Description |")
    md.append("|-------|-------------|")
    for name, role in items:
        md.append(f"| `{name}` | {role} |")
md.append("")

# 8. WORKFLOWS + ROUTING
md.append("---\n")
md.append("## 8. Workflows, Routage et Infrastructure\n")

md.append(f"\n### Workflows n8n ({len(workflows)})\n")
md.append("| Workflow | Description |")
md.append("|----------|-------------|")
for name, role in workflows:
    md.append(f"| `{name}` | {role} |")

md.append(f"\n### Regles de Routage ({len(routes)})\n")
md.append("| Regle | Description |")
md.append("|-------|-------------|")
for name, parent, role in routes:
    md.append(f"| `{name}` | {role} |")

md.append(f"\n### Launchers ({len(launchers)})\n")
md.append("| Launcher | Description |")
md.append("|----------|-------------|")
for name, role in launchers:
    md.append(f"| `{name}` | {role} |")

md.append(f"\n### Scripts ({len(scripts)})\n")
md.append("| Script | Description |")
md.append("|--------|-------------|")
for name, parent, role in scripts:
    md.append(f"| `{name}` | {role} |")

# 9. AGENTS
md.append("\n---\n")
md.append("## 9. Agents IA et Memoires\n")
md.append(f"\n### Agents Enregistres\n")
md.append("| # | Nom | URL | Type | Modele | Status | Latence |")
md.append("|---|-----|-----|------|--------|--------|---------|")
for a in agents:
    st = "ONLINE" if a[5] == "online" else "OFFLINE"
    lat = f"{a[6]}ms" if a[6] and a[6] > 0 else "-"
    md.append(f"| {a[0]} | **{a[1]}** | `{a[2]}` | {a[3]} | {a[4]} | {st} | {lat} |")

md.append(f"\n### Memoires Systeme ({len(memories)})\n")
md.append("| Categorie | Cle | Valeur | Confiance |")
md.append("|-----------|-----|--------|-----------|")
for cat, key, val, conf in memories:
    v = val[:80].replace("|", " ")
    md.append(f"| {cat} | `{key}` | {v} | {conf:.0%} |")

md.append("\n---\n")
md.append("> **JARVIS Etoile v10.3** - Built by [Turbo31150](https://github.com/Turbo31150)")

os.makedirs("docs", exist_ok=True)
content = "\n".join(md)
with open("docs/COMMANDS_REFERENCE.md", "w", encoding="utf-8") as f:
    f.write(content)

print(f"OK: {len(content)} chars written")

