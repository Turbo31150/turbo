#!/usr/bin/env python3
"""Generateur automatique de documentation pour commandes vocales, skills et dominos JARVIS.

Lit les sources (jarvis.db, skills.json, domino_pipelines.py) et genere :
 - Un fichier HTML interactif avec recherche temps reel et accordeons
 - Un fichier Markdown avec la meme information

Code en anglais, commentaires en francais.
"""

import json
import os
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path

# === Chemins ===
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "jarvis.db"
SKILLS_PATH = BASE_DIR / "data" / "skills.json"
DOMINO_PATH = BASE_DIR / "src" / "domino_pipelines.py"
DOCS_DIR = BASE_DIR / "docs"
HTML_OUTPUT = DOCS_DIR / "voice_commands_reference.html"
MD_OUTPUT = DOCS_DIR / "VOICE_COMMANDS.md"


def load_voice_commands() -> list[dict]:
    """Charge les commandes vocales depuis la base de donnees."""
    if not DB_PATH.exists():
        print(f"[WARN] Base de donnees introuvable : {DB_PATH}")
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT name, category, description, triggers, action_type, action, "
        "confirm, enabled, usage_count, success_count, fail_count "
        "FROM voice_commands ORDER BY category, name"
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        triggers = r["triggers"]
        try:
            triggers = json.loads(triggers)
        except (json.JSONDecodeError, TypeError):
            triggers = [str(triggers)]
        results.append({
            "name": r["name"],
            "category": r["category"] or "other",
            "description": r["description"] or "",
            "triggers": triggers,
            "action_type": r["action_type"] or "",
            "action": r["action"] or "",
            "confirm": bool(r["confirm"]),
            "enabled": bool(r["enabled"]),
            "usage_count": r["usage_count"] or 0,
            "success_count": r["success_count"] or 0,
            "fail_count": r["fail_count"] or 0,
        })
    return results


def load_voice_corrections() -> list[dict]:
    """Charge les corrections vocales depuis la base de donnees."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT wrong, correct, category, hit_count FROM voice_corrections ORDER BY category, wrong"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_voice_macros() -> list[dict]:
    """Charge les macros vocales depuis la base de donnees."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT name, commands, description, usage_count FROM voice_macros ORDER BY name"
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        commands = r["commands"]
        try:
            commands = json.loads(commands)
        except (json.JSONDecodeError, TypeError):
            commands = [str(commands)]
        results.append({
            "name": r["name"],
            "commands": commands,
            "description": r["description"] or "",
            "usage_count": r["usage_count"] or 0,
        })
    return results


def load_skills() -> list[dict]:
    """Charge les skills depuis skills.json."""
    if not SKILLS_PATH.exists():
        print(f"[WARN] Fichier skills introuvable : {SKILLS_PATH}")
        return []
    with open(SKILLS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    results = []
    for s in data:
        results.append({
            "name": s.get("name", ""),
            "description": s.get("description", ""),
            "triggers": s.get("triggers", []),
            "steps": s.get("steps", []),
            "category": s.get("category", "other"),
            "confirm": s.get("confirm", False),
            "usage_count": s.get("usage_count", 0),
            "success_rate": s.get("success_rate", 0),
        })
    return results


def count_dominos() -> tuple[int, dict[str, int]]:
    """Compte les dominos et leurs categories depuis domino_pipelines.py."""
    if not DOMINO_PATH.exists():
        print(f"[WARN] Fichier dominos introuvable : {DOMINO_PATH}")
        return 0, {}
    content = DOMINO_PATH.read_text(encoding="utf-8")
    total = content.count("DominoPipeline(")
    categories = re.findall(r'category="([^"]+)"', content)
    return total, dict(Counter(categories))


def load_domino_details() -> list[dict]:
    """Extrait les details de chaque domino pipeline depuis le fichier source."""
    if not DOMINO_PATH.exists():
        return []
    content = DOMINO_PATH.read_text(encoding="utf-8")
    # Extraction par regex des blocs DominoPipeline
    dominos = []
    # Extraction id, trigger_vocal, category, description
    pattern = re.compile(
        r'DominoPipeline\(\s*'
        r'id="([^"]+)".*?'
        r'trigger_vocal=\[([^\]]+)\].*?'
        r'category="([^"]+)".*?'
        r'description="([^"]+)"',
        re.DOTALL,
    )
    for m in pattern.finditer(content):
        triggers_raw = m.group(2)
        triggers = [t.strip().strip('"').strip("'") for t in triggers_raw.split(",")]
        dominos.append({
            "id": m.group(1),
            "triggers": triggers,
            "category": m.group(3),
            "description": m.group(4),
        })
    return dominos


# ═══════════════════════════════════════════════════════════════════════
# GENERATION HTML
# ═══════════════════════════════════════════════════════════════════════

def generate_html(
    commands: list[dict],
    skills: list[dict],
    macros: list[dict],
    corrections: list[dict],
    domino_count: int,
    domino_cats: dict[str, int],
    dominos: list[dict],
) -> str:
    """Genere le fichier HTML interactif complet."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Regrouper commandes par categorie
    cmd_by_cat: dict[str, list[dict]] = {}
    for c in commands:
        cmd_by_cat.setdefault(c["category"], []).append(c)

    # Regrouper skills par categorie
    skill_by_cat: dict[str, list[dict]] = {}
    for s in skills:
        skill_by_cat.setdefault(s["category"], []).append(s)

    # Regrouper dominos par categorie
    domino_by_cat: dict[str, list[dict]] = {}
    for d in dominos:
        domino_by_cat.setdefault(d["category"], []).append(d)

    # Construction des sections commandes
    commands_html = _build_commands_section(cmd_by_cat)
    skills_html = _build_skills_section(skill_by_cat)
    macros_html = _build_macros_section(macros)
    corrections_html = _build_corrections_section(corrections)
    dominos_html = _build_dominos_section(domino_by_cat)

    total_triggers = sum(len(c["triggers"]) for c in commands)
    total_skill_triggers = sum(len(s["triggers"]) for s in skills)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JARVIS — Reference Commandes Vocales</title>
<style>
  :root {{
    --bg: #0a0a0a;
    --bg-card: #111118;
    --bg-hover: #1a1a2e;
    --cyan: #00d4ff;
    --cyan-dim: #00a0c0;
    --green: #00ff88;
    --orange: #ffaa00;
    --red: #ff4444;
    --text: #c8d6e5;
    --text-dim: #7f8c8d;
    --border: #222233;
    --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-mono);
    font-size: 14px;
    line-height: 1.6;
    padding: 20px;
    max-width: 1400px;
    margin: 0 auto;
  }}
  h1 {{
    color: var(--cyan);
    font-size: 2em;
    text-align: center;
    margin-bottom: 5px;
    text-shadow: 0 0 20px rgba(0,212,255,0.3);
  }}
  .subtitle {{
    text-align: center;
    color: var(--text-dim);
    margin-bottom: 30px;
    font-size: 0.9em;
  }}

  /* Statistiques animees */
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 15px;
    margin-bottom: 30px;
  }}
  .stat-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    text-align: center;
    transition: transform 0.2s, border-color 0.2s;
  }}
  .stat-card:hover {{
    transform: translateY(-2px);
    border-color: var(--cyan);
  }}
  .stat-number {{
    font-size: 2.2em;
    font-weight: bold;
    color: var(--cyan);
    display: block;
  }}
  .stat-label {{
    color: var(--text-dim);
    font-size: 0.85em;
    margin-top: 5px;
  }}

  /* Barre de recherche */
  .search-container {{
    position: sticky;
    top: 0;
    background: var(--bg);
    padding: 15px 0;
    z-index: 100;
    border-bottom: 1px solid var(--border);
    margin-bottom: 20px;
  }}
  #search-input {{
    width: 100%;
    padding: 12px 20px;
    background: var(--bg-card);
    border: 2px solid var(--border);
    border-radius: 8px;
    color: var(--cyan);
    font-family: var(--font-mono);
    font-size: 1em;
    outline: none;
    transition: border-color 0.2s;
  }}
  #search-input:focus {{
    border-color: var(--cyan);
    box-shadow: 0 0 10px rgba(0,212,255,0.2);
  }}
  #search-input::placeholder {{
    color: var(--text-dim);
  }}
  #search-count {{
    text-align: right;
    color: var(--text-dim);
    font-size: 0.85em;
    margin-top: 5px;
  }}

  /* Tabs de navigation */
  .tabs {{
    display: flex;
    gap: 5px;
    margin-bottom: 20px;
    flex-wrap: wrap;
  }}
  .tab {{
    padding: 8px 18px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text-dim);
    cursor: pointer;
    transition: all 0.2s;
    font-family: var(--font-mono);
    font-size: 0.9em;
  }}
  .tab:hover {{ border-color: var(--cyan); color: var(--text); }}
  .tab.active {{
    background: var(--cyan);
    color: var(--bg);
    border-color: var(--cyan);
    font-weight: bold;
  }}
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}

  /* Accordeons */
  .accordion {{
    margin-bottom: 10px;
  }}
  .accordion-header {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 18px;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: all 0.2s;
    user-select: none;
  }}
  .accordion-header:hover {{
    border-color: var(--cyan);
    background: var(--bg-hover);
  }}
  .accordion-header .cat-name {{
    color: var(--cyan);
    font-weight: bold;
  }}
  .accordion-header .cat-count {{
    background: var(--cyan);
    color: var(--bg);
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.85em;
    font-weight: bold;
  }}
  .accordion-header .arrow {{
    color: var(--cyan);
    transition: transform 0.2s;
    margin-left: 10px;
  }}
  .accordion-header.open .arrow {{
    transform: rotate(90deg);
  }}
  .accordion-body {{
    display: none;
    padding: 10px 0;
  }}
  .accordion-body.open {{
    display: block;
  }}

  /* Cartes de commande */
  .cmd-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 14px 18px;
    margin-bottom: 8px;
    transition: border-color 0.2s;
  }}
  .cmd-card:hover {{
    border-color: var(--cyan-dim);
  }}
  .cmd-name {{
    color: var(--green);
    font-weight: bold;
    font-size: 1em;
  }}
  .cmd-desc {{
    color: var(--text);
    margin: 4px 0;
    font-size: 0.9em;
  }}
  .cmd-triggers {{
    margin: 6px 0;
  }}
  .trigger-tag {{
    display: inline-block;
    background: rgba(0,212,255,0.1);
    border: 1px solid rgba(0,212,255,0.3);
    color: var(--cyan);
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.8em;
    margin: 2px 4px 2px 0;
  }}
  .cmd-meta {{
    color: var(--text-dim);
    font-size: 0.8em;
    margin-top: 6px;
  }}
  .cmd-meta span {{
    margin-right: 15px;
  }}
  .badge {{
    display: inline-block;
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 0.75em;
    font-weight: bold;
  }}
  .badge-bash {{ background: rgba(0,255,136,0.15); color: var(--green); }}
  .badge-python {{ background: rgba(255,170,0,0.15); color: var(--orange); }}
  .badge-curl {{ background: rgba(0,212,255,0.15); color: var(--cyan); }}
  .badge-pipeline {{ background: rgba(255,68,68,0.15); color: var(--red); }}
  .badge-other {{ background: rgba(200,214,229,0.1); color: var(--text-dim); }}

  .step-list {{
    margin: 8px 0 0 15px;
    list-style: none;
  }}
  .step-list li {{
    padding: 3px 0;
    color: var(--text-dim);
    font-size: 0.85em;
  }}
  .step-list li::before {{
    content: "▸ ";
    color: var(--cyan);
  }}

  /* Corrections table */
  .corr-table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
  }}
  .corr-table th {{
    background: var(--bg-card);
    color: var(--cyan);
    padding: 10px;
    text-align: left;
    border-bottom: 2px solid var(--border);
  }}
  .corr-table td {{
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
  }}
  .corr-table tr:hover td {{
    background: var(--bg-hover);
  }}

  /* Responsive */
  @media (max-width: 768px) {{
    body {{ padding: 10px; font-size: 13px; }}
    h1 {{ font-size: 1.5em; }}
    .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .tabs {{ gap: 3px; }}
    .tab {{ padding: 6px 12px; font-size: 0.8em; }}
  }}

  /* Impression */
  @media print {{
    body {{ background: #fff; color: #000; }}
    .search-container {{ display: none; }}
    .tabs {{ display: none; }}
    .tab-content {{ display: block !important; }}
    .accordion-body {{ display: block !important; }}
    .stat-card {{ border: 1px solid #ccc; }}
    .stat-number {{ color: #006; }}
    .cmd-name {{ color: #060; }}
    .trigger-tag {{ border: 1px solid #999; color: #006; background: #eef; }}
    h1, .accordion-header .cat-name {{ color: #006; }}
  }}
</style>
</head>
<body>

<h1>JARVIS — Reference Commandes Vocales</h1>
<p class="subtitle">Genere automatiquement le {now} | Cluster M1</p>

<!-- Statistiques -->
<div class="stats-grid">
  <div class="stat-card">
    <span class="stat-number" data-target="{len(commands)}">0</span>
    <div class="stat-label">Commandes vocales</div>
  </div>
  <div class="stat-card">
    <span class="stat-number" data-target="{len(skills)}">0</span>
    <div class="stat-label">Skills</div>
  </div>
  <div class="stat-card">
    <span class="stat-number" data-target="{domino_count}">0</span>
    <div class="stat-label">Domino Pipelines</div>
  </div>
  <div class="stat-card">
    <span class="stat-number" data-target="{len(macros)}">0</span>
    <div class="stat-label">Macros</div>
  </div>
  <div class="stat-card">
    <span class="stat-number" data-target="{len(corrections)}">0</span>
    <div class="stat-label">Corrections phonetiques</div>
  </div>
  <div class="stat-card">
    <span class="stat-number" data-target="{total_triggers + total_skill_triggers}">0</span>
    <div class="stat-label">Triggers totaux</div>
  </div>
</div>

<!-- Recherche -->
<div class="search-container">
  <input type="text" id="search-input" placeholder="Rechercher une commande, un trigger, un skill..." autocomplete="off">
  <div id="search-count"></div>
</div>

<!-- Tabs -->
<div class="tabs">
  <div class="tab active" data-tab="tab-commands">Commandes ({len(commands)})</div>
  <div class="tab" data-tab="tab-skills">Skills ({len(skills)})</div>
  <div class="tab" data-tab="tab-dominos">Dominos ({domino_count})</div>
  <div class="tab" data-tab="tab-macros">Macros ({len(macros)})</div>
  <div class="tab" data-tab="tab-corrections">Corrections ({len(corrections)})</div>
</div>

<!-- Contenu des tabs -->
<div id="tab-commands" class="tab-content active">
  <h2 style="color:var(--cyan);margin-bottom:15px;">Commandes Vocales</h2>
  {commands_html}
</div>

<div id="tab-skills" class="tab-content">
  <h2 style="color:var(--cyan);margin-bottom:15px;">Skills</h2>
  {skills_html}
</div>

<div id="tab-dominos" class="tab-content">
  <h2 style="color:var(--cyan);margin-bottom:15px;">Domino Pipelines</h2>
  {dominos_html}
</div>

<div id="tab-macros" class="tab-content">
  <h2 style="color:var(--cyan);margin-bottom:15px;">Macros Vocales</h2>
  {macros_html}
</div>

<div id="tab-corrections" class="tab-content">
  <h2 style="color:var(--cyan);margin-bottom:15px;">Corrections Phonetiques</h2>
  {corrections_html}
</div>

<script>
// Animation des compteurs
document.querySelectorAll('.stat-number[data-target]').forEach(el => {{
  const target = parseInt(el.dataset.target);
  const duration = 1200;
  const step = Math.max(1, Math.floor(target / 60));
  let current = 0;
  const timer = setInterval(() => {{
    current += step;
    if (current >= target) {{
      current = target;
      clearInterval(timer);
    }}
    el.textContent = current;
  }}, duration / 60);
}});

// Tabs
document.querySelectorAll('.tab').forEach(tab => {{
  tab.addEventListener('click', () => {{
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(tab.dataset.tab).classList.add('active');
  }});
}});

// Accordeons
document.querySelectorAll('.accordion-header').forEach(header => {{
  header.addEventListener('click', () => {{
    header.classList.toggle('open');
    header.nextElementSibling.classList.toggle('open');
  }});
}});

// Recherche temps reel
const searchInput = document.getElementById('search-input');
const searchCount = document.getElementById('search-count');

searchInput.addEventListener('input', () => {{
  const q = searchInput.value.toLowerCase().trim();
  let visible = 0;
  let total = 0;

  document.querySelectorAll('.cmd-card').forEach(card => {{
    total++;
    const text = card.textContent.toLowerCase();
    const match = !q || text.includes(q);
    card.style.display = match ? '' : 'none';
    if (match) visible++;
  }});

  // Ouvrir tous les accordeons si recherche active
  if (q) {{
    document.querySelectorAll('.tab-content').forEach(c => c.classList.add('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.add('active'));
    document.querySelectorAll('.accordion-header').forEach(h => h.classList.add('open'));
    document.querySelectorAll('.accordion-body').forEach(b => b.classList.add('open'));
  }}

  searchCount.textContent = q ? visible + ' / ' + total + ' resultats' : '';
}});
</script>

</body>
</html>"""


def _action_badge(action_type: str) -> str:
    """Retourne le badge HTML colore selon le type d'action."""
    t = action_type.lower()
    if "bash" in t:
        return '<span class="badge badge-bash">bash</span>'
    if "python" in t:
        return '<span class="badge badge-python">python</span>'
    if "curl" in t:
        return '<span class="badge badge-curl">curl</span>'
    if "pipeline" in t:
        return '<span class="badge badge-pipeline">pipeline</span>'
    return f'<span class="badge badge-other">{escape(action_type)}</span>'


def _build_commands_section(cmd_by_cat: dict[str, list[dict]]) -> str:
    """Construit les accordeons HTML pour les commandes vocales."""
    html_parts = []
    for cat in sorted(cmd_by_cat):
        cmds = cmd_by_cat[cat]
        cards = []
        for c in cmds:
            triggers_html = "".join(
                f'<span class="trigger-tag">{escape(t)}</span>' for t in c["triggers"]
            )
            cards.append(f"""
      <div class="cmd-card" data-searchable>
        <div class="cmd-name">{escape(c["name"])} {_action_badge(c["action_type"])}</div>
        <div class="cmd-desc">{escape(c["description"])}</div>
        <div class="cmd-triggers">{triggers_html}</div>
        <div class="cmd-meta">
          <span>Action: <code>{escape(c["action"][:80])}</code></span>
          <span>Utilisations: {c["usage_count"]}</span>
          {"<span style='color:var(--orange)'>Confirmation requise</span>" if c["confirm"] else ""}
          {"" if c["enabled"] else "<span style='color:var(--red)'>Desactivee</span>"}
        </div>
      </div>""")

        html_parts.append(f"""
    <div class="accordion">
      <div class="accordion-header">
        <span><span class="cat-name">{escape(cat)}</span></span>
        <span><span class="cat-count">{len(cmds)}</span><span class="arrow">&#9654;</span></span>
      </div>
      <div class="accordion-body">
        {"".join(cards)}
      </div>
    </div>""")
    return "\n".join(html_parts)


def _build_skills_section(skill_by_cat: dict[str, list[dict]]) -> str:
    """Construit les accordeons HTML pour les skills."""
    html_parts = []
    for cat in sorted(skill_by_cat):
        skills = skill_by_cat[cat]
        cards = []
        for s in skills:
            triggers_html = "".join(
                f'<span class="trigger-tag">{escape(t)}</span>' for t in s["triggers"]
            )
            steps_html = ""
            if s["steps"]:
                items = "".join(
                    f'<li>{escape(st.get("tool", ""))} — {escape(st.get("description", ""))}</li>'
                    for st in s["steps"]
                )
                steps_html = f'<ul class="step-list">{items}</ul>'

            cards.append(f"""
      <div class="cmd-card" data-searchable>
        <div class="cmd-name">{escape(s["name"])}</div>
        <div class="cmd-desc">{escape(s["description"])}</div>
        <div class="cmd-triggers">{triggers_html}</div>
        {steps_html}
        <div class="cmd-meta">
          <span>Etapes: {len(s["steps"])}</span>
          <span>Taux succes: {s["success_rate"]:.0%}</span>
          <span>Utilisations: {s["usage_count"]}</span>
        </div>
      </div>""")

        html_parts.append(f"""
    <div class="accordion">
      <div class="accordion-header">
        <span><span class="cat-name">{escape(cat)}</span></span>
        <span><span class="cat-count">{len(skills)}</span><span class="arrow">&#9654;</span></span>
      </div>
      <div class="accordion-body">
        {"".join(cards)}
      </div>
    </div>""")
    return "\n".join(html_parts)


def _build_dominos_section(domino_by_cat: dict[str, list[dict]]) -> str:
    """Construit les accordeons HTML pour les domino pipelines."""
    html_parts = []
    for cat in sorted(domino_by_cat):
        dominos = domino_by_cat[cat]
        cards = []
        for d in dominos:
            triggers_html = "".join(
                f'<span class="trigger-tag">{escape(t)}</span>' for t in d["triggers"]
            )
            cards.append(f"""
      <div class="cmd-card" data-searchable>
        <div class="cmd-name">{escape(d["id"])}</div>
        <div class="cmd-desc">{escape(d["description"])}</div>
        <div class="cmd-triggers">{triggers_html}</div>
      </div>""")

        html_parts.append(f"""
    <div class="accordion">
      <div class="accordion-header">
        <span><span class="cat-name">{escape(cat)}</span></span>
        <span><span class="cat-count">{len(dominos)}</span><span class="arrow">&#9654;</span></span>
      </div>
      <div class="accordion-body">
        {"".join(cards)}
      </div>
    </div>""")
    return "\n".join(html_parts)


def _build_macros_section(macros: list[dict]) -> str:
    """Construit les cartes HTML pour les macros."""
    cards = []
    for m in macros:
        cmds_html = "<ul class='step-list'>" + "".join(
            f"<li>{escape(c)}</li>" for c in m["commands"]
        ) + "</ul>"
        cards.append(f"""
    <div class="cmd-card" data-searchable>
      <div class="cmd-name">{escape(m["name"])}</div>
      <div class="cmd-desc">{escape(m["description"])}</div>
      {cmds_html}
      <div class="cmd-meta"><span>Utilisations: {m["usage_count"]}</span></div>
    </div>""")
    return "\n".join(cards)


def _build_corrections_section(corrections: list[dict]) -> str:
    """Construit la table HTML pour les corrections phonetiques."""
    # Regrouper par categorie
    by_cat: dict[str, list[dict]] = {}
    for c in corrections:
        by_cat.setdefault(c["category"] or "other", []).append(c)

    parts = []
    for cat in sorted(by_cat):
        rows = "".join(
            f'<tr class="cmd-card"><td>{escape(c["wrong"])}</td>'
            f'<td style="color:var(--green)">{escape(c["correct"])}</td>'
            f'<td>{c["hit_count"]}</td></tr>'
            for c in by_cat[cat]
        )
        parts.append(f"""
    <div class="accordion">
      <div class="accordion-header">
        <span><span class="cat-name">{escape(cat)}</span></span>
        <span><span class="cat-count">{len(by_cat[cat])}</span><span class="arrow">&#9654;</span></span>
      </div>
      <div class="accordion-body">
        <table class="corr-table">
          <thead><tr><th>Erreur</th><th>Correction</th><th>Occurrences</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>""")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# GENERATION MARKDOWN
# ═══════════════════════════════════════════════════════════════════════

def generate_markdown(
    commands: list[dict],
    skills: list[dict],
    macros: list[dict],
    corrections: list[dict],
    domino_count: int,
    domino_cats: dict[str, int],
    dominos: list[dict],
) -> str:
    """Genere le fichier Markdown complet."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_triggers = sum(len(c["triggers"]) for c in commands)
    total_skill_triggers = sum(len(s["triggers"]) for s in skills)

    lines = [
        f"# JARVIS - Reference Commandes Vocales",
        f"",
        f"> Genere automatiquement le {now} | Cluster M1",
        f"",
        f"## Statistiques",
        f"",
        f"| Metrique | Valeur |",
        f"|----------|--------|",
        f"| Commandes vocales | {len(commands)} |",
        f"| Skills | {len(skills)} |",
        f"| Domino Pipelines | {domino_count} |",
        f"| Macros | {len(macros)} |",
        f"| Corrections phonetiques | {len(corrections)} |",
        f"| Triggers totaux | {total_triggers + total_skill_triggers} |",
        f"",
        f"---",
        f"",
    ]

    # Commandes vocales
    lines.append("## Commandes Vocales\n")
    cmd_by_cat: dict[str, list[dict]] = {}
    for c in commands:
        cmd_by_cat.setdefault(c["category"], []).append(c)
    for cat in sorted(cmd_by_cat):
        lines.append(f"### {cat} ({len(cmd_by_cat[cat])} commandes)\n")
        for c in cmd_by_cat[cat]:
            triggers = ", ".join(f"`{t}`" for t in c["triggers"])
            lines.append(f"- **{c['name']}** [{c['action_type']}]")
            lines.append(f"  - Description: {c['description']}")
            lines.append(f"  - Triggers: {triggers}")
            lines.append(f"  - Action: `{c['action'][:100]}`")
            lines.append(f"  - Utilisations: {c['usage_count']}")
            lines.append("")
        lines.append("")

    # Skills
    lines.append("---\n")
    lines.append("## Skills\n")
    skill_by_cat: dict[str, list[dict]] = {}
    for s in skills:
        skill_by_cat.setdefault(s["category"], []).append(s)
    for cat in sorted(skill_by_cat):
        lines.append(f"### {cat} ({len(skill_by_cat[cat])} skills)\n")
        for s in skill_by_cat[cat]:
            triggers = ", ".join(f"`{t}`" for t in s["triggers"])
            lines.append(f"- **{s['name']}**")
            lines.append(f"  - Description: {s['description']}")
            lines.append(f"  - Triggers: {triggers}")
            if s["steps"]:
                lines.append(f"  - Etapes:")
                for st in s["steps"]:
                    lines.append(f"    1. `{st.get('tool', '')}` — {st.get('description', '')}")
            lines.append(f"  - Taux succes: {s['success_rate']:.0%}")
            lines.append("")
        lines.append("")

    # Dominos
    lines.append("---\n")
    lines.append(f"## Domino Pipelines ({domino_count} total)\n")
    domino_by_cat: dict[str, list[dict]] = {}
    for d in dominos:
        domino_by_cat.setdefault(d["category"], []).append(d)
    for cat in sorted(domino_by_cat):
        lines.append(f"### {cat} ({len(domino_by_cat[cat])} dominos)\n")
        for d in domino_by_cat[cat]:
            triggers = ", ".join(f"`{t}`" for t in d["triggers"])
            lines.append(f"- **{d['id']}**")
            lines.append(f"  - Description: {d['description']}")
            lines.append(f"  - Triggers: {triggers}")
            lines.append("")
        lines.append("")

    # Macros
    lines.append("---\n")
    lines.append("## Macros Vocales\n")
    for m in macros:
        lines.append(f"- **{m['name']}** — {m['description']}")
        lines.append(f"  - Commandes:")
        for cmd in m["commands"]:
            lines.append(f"    1. `{cmd}`")
        lines.append(f"  - Utilisations: {m['usage_count']}")
        lines.append("")

    # Corrections
    lines.append("---\n")
    lines.append("## Corrections Phonetiques\n")
    lines.append("| Erreur | Correction | Categorie | Occurrences |")
    lines.append("|--------|-----------|-----------|-------------|")
    for c in corrections:
        lines.append(f"| {c['wrong']} | {c['correct']} | {c['category']} | {c['hit_count']} |")
    lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    """Point d'entree principal — charge les donnees et genere les fichiers."""
    print("=" * 60)
    print("JARVIS — Generateur de documentation vocale")
    print("=" * 60)

    # Chargement des donnees
    print("\n[1/5] Chargement des commandes vocales...")
    commands = load_voice_commands()
    print(f"       -> {len(commands)} commandes chargees")

    print("[2/5] Chargement des skills...")
    skills = load_skills()
    print(f"       -> {len(skills)} skills chargees")

    print("[3/5] Chargement des corrections...")
    corrections = load_voice_corrections()
    print(f"       -> {len(corrections)} corrections chargees")

    print("[4/5] Chargement des macros...")
    macros = load_voice_macros()
    print(f"       -> {len(macros)} macros chargees")

    print("[5/5] Comptage des dominos...")
    domino_count, domino_cats = count_dominos()
    dominos = load_domino_details()
    print(f"       -> {domino_count} dominos ({len(domino_cats)} categories)")

    # Creation du dossier docs si necessaire
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # Generation HTML
    print(f"\nGeneration HTML -> {HTML_OUTPUT}")
    html_content = generate_html(commands, skills, macros, corrections, domino_count, domino_cats, dominos)
    HTML_OUTPUT.write_text(html_content, encoding="utf-8")
    html_size = HTML_OUTPUT.stat().st_size
    print(f"       -> {html_size:,} octets ecrits")

    # Generation Markdown
    print(f"Generation Markdown -> {MD_OUTPUT}")
    md_content = generate_markdown(commands, skills, macros, corrections, domino_count, domino_cats, dominos)
    MD_OUTPUT.write_text(md_content, encoding="utf-8")
    md_size = MD_OUTPUT.stat().st_size
    print(f"       -> {md_size:,} octets ecrits")

    # Resume final
    print("\n" + "=" * 60)
    print("RESUME:")
    print(f"  Commandes vocales : {len(commands)}")
    print(f"  Skills            : {len(skills)}")
    print(f"  Domino Pipelines  : {domino_count}")
    print(f"  Macros            : {len(macros)}")
    print(f"  Corrections       : {len(corrections)}")
    print(f"  HTML              : {HTML_OUTPUT}")
    print(f"  Markdown          : {MD_OUTPUT}")
    print("=" * 60)
    print("Documentation generee avec succes.")


if __name__ == "__main__":
    main()
