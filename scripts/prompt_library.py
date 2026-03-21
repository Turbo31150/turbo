#!/usr/bin/env python3
"""prompt_library.py — Bibliotheque de Prompts Multi-IA v2.0

Integration complete avec le cluster JARVIS:
- Indexation automatique de tous les prompts (397+)
- Scoring qualite par prompt (completude, structure, metadata)
- Auto-selection par contexte (intent classification)
- Boucle amelioration continue (feedback loop)
- Integration cluster IA distribue (M1/M2/OL1/GEMINI)

Usage:
    python scripts/prompt_library.py --index           # Re-indexer tous les prompts
    python scripts/prompt_library.py --search "debug"  # Chercher un prompt
    python scripts/prompt_library.py --score            # Scorer la qualite
    python scripts/prompt_library.py --suggest "task"   # Auto-suggerer prompt
    python scripts/prompt_library.py --improve          # Boucle amelioration
    python scripts/prompt_library.py --stats            # Stats bibliotheque
    python scripts/prompt_library.py --export           # Export JSON complet
    python scripts/prompt_library.py --json             # Output JSON

Stdlib-only (os, json, re, sqlite3, argparse, pathlib).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Paths ────────────────────────────────────────────────────────────────────
TURBO_DIR = Path("F:/BUREAU/turbo")
LIB_DIR = TURBO_DIR / "knowledge" / "bibliotheque-prompts-multi-ia"
PROMPTS_DIR = LIB_DIR / "prompts"
PROMPT_DIR = LIB_DIR / "prompt"  # legacy
DB_PATH = TURBO_DIR / "data" / "prompt_library.db"
EXPORT_PATH = LIB_DIR / "export" / "jarvis-prompts-index.json"

# ── Categories mapping ───────────────────────────────────────────────────────
CATEGORIES = {
    "claude-code": {"weight": 1.5, "ia": "Claude Code CLI", "tags": ["code", "debug", "refactor", "test"]},
    "gemini-cli": {"weight": 1.2, "ia": "Gemini CLI", "tags": ["code", "architecture", "audit"]},
    "chatgpt": {"weight": 1.0, "ia": "ChatGPT", "tags": ["general", "writing", "analysis"]},
    "codex-cli": {"weight": 1.1, "ia": "Codex CLI", "tags": ["code", "terminal", "automation"]},
    "browseros": {"weight": 1.0, "ia": "BrowserOS", "tags": ["web", "scraping", "automation"]},
    "openclaw": {"weight": 1.2, "ia": "OpenClaw", "tags": ["agents", "routing", "orchestration"]},
    "n8n": {"weight": 0.9, "ia": "n8n", "tags": ["workflow", "automation", "integration"]},
    "perplexity": {"weight": 1.0, "ia": "Perplexity", "tags": ["research", "search", "facts"]},
    "models-locaux": {"weight": 1.3, "ia": "LM Studio/Ollama", "tags": ["local", "gpu", "inference"]},
    "cluster": {"weight": 1.4, "ia": "Cluster JARVIS", "tags": ["distributed", "consensus", "routing"]},
    "claude-api": {"weight": 1.1, "ia": "Claude API", "tags": ["api", "sdk", "integration"]},
    "gemini-app": {"weight": 0.9, "ia": "Gemini App", "tags": ["mobile", "web", "general"]},
    "codex-openai": {"weight": 0.8, "ia": "Codex OpenAI", "tags": ["code", "completion"]},
    "multi-ia": {"weight": 1.5, "ia": "Multi-IA", "tags": ["orchestration", "comparison", "consensus"]},
}

# ── Intent patterns for auto-selection ───────────────────────────────────────
INTENT_PATTERNS = [
    (re.compile(r"debug|fix|bug|erreur|crash|broken", re.I), "debug"),
    (re.compile(r"refactor|clean|reorgani|restructur", re.I), "refactor"),
    (re.compile(r"test|unit|integration|pytest|jest", re.I), "test"),
    (re.compile(r"deploy|linux|server|infra|docker", re.I), "deploy"),
    (re.compile(r"archi|design|plan|concevoir|structur", re.I), "architecture"),
    (re.compile(r"optimi|perf|speed|latenc|rapide|lent", re.I), "performance"),
    (re.compile(r"audit|review|qualit|analyse|scanner", re.I), "audit"),
    (re.compile(r"migrat|port|transfer|upgrad", re.I), "migration"),
    (re.compile(r"monitor|watch|alert|log|observ", re.I), "monitoring"),
    (re.compile(r"creat|nouveau|generer|build|develop", re.I), "creation"),
    (re.compile(r"document|readme|guide|tuto", re.I), "documentation"),
    (re.compile(r"autom|script|batch|cron|schedul", re.I), "automation"),
    (re.compile(r"trad|signal|crypto|bourse|mexc", re.I), "trading"),
    (re.compile(r"web|browser|scrap|navigat", re.I), "web"),
    (re.compile(r"cluster|distribu|consensus|multi.?agent", re.I), "cluster"),
    (re.compile(r"config|setup|install|param", re.I), "configuration"),
]


# ── SQLite ───────────────────────────────────────────────────────────────────
def init_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            category TEXT,
            subcategory TEXT,
            title TEXT,
            format TEXT DEFAULT 'md',
            size_bytes INTEGER DEFAULT 0,
            lines INTEGER DEFAULT 0,
            has_code_blocks INTEGER DEFAULT 0,
            has_metadata INTEGER DEFAULT 0,
            quality_score REAL DEFAULT 0,
            tags TEXT DEFAULT '[]',
            intent TEXT,
            last_indexed TEXT,
            use_count INTEGER DEFAULT 0,
            last_used TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now','localtime')),
            prompt_id TEXT,
            context TEXT,
            feedback TEXT,
            score REAL DEFAULT 0
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_prompts_cat ON prompts(category)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_prompts_intent ON prompts(intent)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_prompts_score ON prompts(quality_score DESC)")
    db.commit()
    return db


# ── Indexation ───────────────────────────────────────────────────────────────
def index_all(db: sqlite3.Connection) -> dict:
    """Index all prompt files into SQLite."""
    t0 = time.time()
    stats = {"indexed": 0, "updated": 0, "categories": {}, "errors": 0}

    for base_dir in [PROMPTS_DIR, PROMPT_DIR]:
        if not base_dir.exists():
            continue
        for filepath in base_dir.rglob("*"):
            if filepath.is_dir() or filepath.name.startswith("."):
                continue
            try:
                rel = filepath.relative_to(base_dir)
                parts = rel.parts
                category = parts[0] if len(parts) > 1 else "uncategorized"
                subcategory = parts[1] if len(parts) > 2 else ""
                prompt_id = f"{category}/{rel.name}"

                content = filepath.read_text(encoding="utf-8", errors="replace")
                lines = content.count("\n") + 1
                has_code = 1 if "```" in content else 0
                has_meta = 1 if content.startswith("---") or content.startswith("#") else 0

                # Extract title
                title = ""
                for line in content.splitlines()[:5]:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                if not title:
                    title = filepath.stem.replace("-", " ").replace("_", " ").title()

                # Classify intent
                intent = classify_intent(content[:500] + " " + title)

                # Quality score
                score = compute_quality(content, has_code, has_meta, lines)

                # Tags from category config
                cat_info = CATEGORIES.get(category.lower(), {})
                tags = cat_info.get("tags", [])

                db.execute("""
                    INSERT OR REPLACE INTO prompts
                    (id, path, category, subcategory, title, format, size_bytes, lines,
                     has_code_blocks, has_metadata, quality_score, tags, intent, last_indexed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (prompt_id, str(filepath), category, subcategory, title,
                      filepath.suffix.lstrip(".") or "md", filepath.stat().st_size,
                      lines, has_code, has_meta, score, json.dumps(tags),
                      intent, datetime.now().isoformat()))

                stats["indexed"] += 1
                stats["categories"][category] = stats["categories"].get(category, 0) + 1

            except Exception as e:
                stats["errors"] += 1

    db.commit()
    stats["duration_ms"] = round((time.time() - t0) * 1000)
    return stats


def classify_intent(text: str) -> str:
    for pattern, intent in INTENT_PATTERNS:
        if pattern.search(text):
            return intent
    return "general"


def compute_quality(content: str, has_code: int, has_meta: int, lines: int) -> float:
    """Score 0-100 based on completeness and structure."""
    score = 0
    # Length (max 25 pts)
    if lines > 5:
        score += min(25, lines * 0.5)
    # Has code examples (20 pts)
    score += has_code * 20
    # Has metadata/headers (15 pts)
    score += has_meta * 15
    # Has sections (## headers) (15 pts)
    sections = content.count("\n## ")
    score += min(15, sections * 5)
    # Has usage/examples (10 pts)
    if re.search(r"(exemple|usage|utilisation|example)", content, re.I):
        score += 10
    # Has variables/placeholders (10 pts)
    if re.search(r"(\{[A-Z_]+\}|\[.*\]|<.*>)", content):
        score += 10
    # Non-trivial content (5 pts)
    if len(content) > 200:
        score += 5
    return min(100, round(score, 1))


# ── Search ───────────────────────────────────────────────────────────────────
def search_prompts(db: sqlite3.Connection, query: str, limit: int = 10) -> list[dict]:
    """Search prompts by keyword."""
    rows = db.execute("""
        SELECT id, category, title, quality_score, intent, path
        FROM prompts
        WHERE title LIKE ? OR category LIKE ? OR intent LIKE ? OR id LIKE ?
        ORDER BY quality_score DESC
        LIMIT ?
    """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", limit)).fetchall()
    return [{"id": r[0], "category": r[1], "title": r[2],
             "score": r[3], "intent": r[4], "path": r[5]} for r in rows]


# ── Auto-suggest ─────────────────────────────────────────────────────────────
def suggest_prompt(db: sqlite3.Connection, task_description: str, ia: str = None) -> list[dict]:
    """Auto-suggest best prompts for a task."""
    intent = classify_intent(task_description)

    query = "SELECT id, category, title, quality_score, intent, path FROM prompts WHERE intent = ?"
    params = [intent]

    if ia:
        query += " AND category LIKE ?"
        params.append(f"%{ia}%")

    query += " ORDER BY quality_score DESC LIMIT 5"
    rows = db.execute(query, params).fetchall()

    if not rows:
        # Fallback: search by keywords
        words = task_description.split()[:3]
        for word in words:
            rows = db.execute(
                "SELECT id, category, title, quality_score, intent, path FROM prompts "
                "WHERE title LIKE ? ORDER BY quality_score DESC LIMIT 5",
                (f"%{word}%",)
            ).fetchall()
            if rows:
                break

    return [{"id": r[0], "category": r[1], "title": r[2],
             "score": r[3], "intent": r[4], "path": r[5]} for r in rows]


# ── Quality scoring ─────────────────────────────────────────────────────────
def score_library(db: sqlite3.Connection) -> dict:
    """Generate quality report for the entire library."""
    total = db.execute("SELECT COUNT(*) FROM prompts").fetchone()[0]
    avg_score = db.execute("SELECT AVG(quality_score) FROM prompts").fetchone()[0] or 0
    low_quality = db.execute("SELECT COUNT(*) FROM prompts WHERE quality_score < 30").fetchone()[0]
    high_quality = db.execute("SELECT COUNT(*) FROM prompts WHERE quality_score >= 70").fetchone()[0]

    by_category = db.execute("""
        SELECT category, COUNT(*), ROUND(AVG(quality_score),1)
        FROM prompts GROUP BY category ORDER BY COUNT(*) DESC
    """).fetchall()

    by_intent = db.execute("""
        SELECT intent, COUNT(*) FROM prompts GROUP BY intent ORDER BY COUNT(*) DESC LIMIT 10
    """).fetchall()

    return {
        "total": total,
        "avg_score": round(avg_score, 1),
        "high_quality": high_quality,
        "low_quality": low_quality,
        "by_category": [{"name": r[0], "count": r[1], "avg_score": r[2]} for r in by_category],
        "by_intent": [{"intent": r[0], "count": r[1]} for r in by_intent],
    }


# ── Improvement loop ────────────────────────────────────────────────────────
def improvement_suggestions(db: sqlite3.Connection) -> list[dict]:
    """Generate improvement suggestions for low-quality prompts."""
    rows = db.execute("""
        SELECT id, category, title, quality_score, has_code_blocks, has_metadata, lines, path
        FROM prompts WHERE quality_score < 40
        ORDER BY quality_score ASC LIMIT 20
    """).fetchall()

    suggestions = []
    for r in rows:
        issues = []
        if r[4] == 0:
            issues.append("Ajouter des exemples de code")
        if r[5] == 0:
            issues.append("Ajouter un titre/header markdown")
        if r[6] < 5:
            issues.append("Contenu trop court (<5 lignes)")
        if not issues:
            issues.append("Score bas — restructurer le contenu")
        suggestions.append({
            "id": r[0], "category": r[1], "title": r[2],
            "score": r[3], "issues": issues, "path": r[7]
        })
    return suggestions


# ── Export ───────────────────────────────────────────────────────────────────
def export_index(db: sqlite3.Connection) -> dict:
    """Export full index as JSON."""
    rows = db.execute("""
        SELECT id, category, subcategory, title, quality_score, intent, tags,
               has_code_blocks, lines, path
        FROM prompts ORDER BY category, quality_score DESC
    """).fetchall()

    index = {
        "library": "JARVIS Prompt Library",
        "version": "2.0",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total": len(rows),
        "prompts": []
    }
    for r in rows:
        index["prompts"].append({
            "id": r[0], "category": r[1], "subcategory": r[2],
            "title": r[3], "score": r[4], "intent": r[5],
            "tags": json.loads(r[6] or "[]"), "has_code": bool(r[7]),
            "lines": r[8], "path": r[9]
        })
    return index


# ── Stats ────────────────────────────────────────────────────────────────────
def show_stats(db: sqlite3.Connection) -> str:
    report = score_library(db)
    lines = [
        f"Bibliotheque Prompts Multi-IA",
        f"  Total: {report['total']} prompts",
        f"  Score moyen: {report['avg_score']}/100",
        f"  Haute qualite (>=70): {report['high_quality']}",
        f"  Basse qualite (<30): {report['low_quality']}",
        f"",
        f"  Par categorie:"
    ]
    for c in report["by_category"]:
        bar = "#" * int(c["avg_score"] / 5)
        lines.append(f"    {c['name']:20s} {c['count']:3d} prompts  [{bar:20s}] {c['avg_score']}/100")
    lines.append(f"\n  Par intent:")
    for i in report["by_intent"]:
        lines.append(f"    {i['intent']:15s} {i['count']:3d}")
    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="JARVIS Prompt Library v2.0")
    parser.add_argument("--index", action="store_true", help="Re-index all prompts")
    parser.add_argument("--search", type=str, help="Search prompts by keyword")
    parser.add_argument("--score", action="store_true", help="Quality scoring report")
    parser.add_argument("--suggest", type=str, help="Auto-suggest prompt for task")
    parser.add_argument("--ia", type=str, help="Filter by IA tool (with --suggest)")
    parser.add_argument("--improve", action="store_true", help="Improvement suggestions")
    parser.add_argument("--stats", action="store_true", help="Library statistics")
    parser.add_argument("--export", action="store_true", help="Export full index JSON")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    db = init_db()

    if args.index:
        stats = index_all(db)
        if args.json:
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        else:
            print(f"Indexed {stats['indexed']} prompts in {stats['duration_ms']}ms")
            for cat, count in sorted(stats["categories"].items(), key=lambda x: -x[1]):
                print(f"  {cat}: {count}")
        return

    if args.search:
        results = search_prompts(db, args.search)
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            for r in results:
                print(f"  [{r['score']:.0f}] {r['category']}/{r['title']} ({r['intent']})")
        return

    if args.suggest:
        results = suggest_prompt(db, args.suggest, args.ia)
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            print(f"Suggestions pour: {args.suggest}")
            for r in results:
                print(f"  [{r['score']:.0f}] {r['category']}/{r['title']}")
                print(f"       {r['path']}")
        return

    if args.score or args.stats:
        if args.json:
            print(json.dumps(score_library(db), indent=2, ensure_ascii=False))
        else:
            print(show_stats(db))
        return

    if args.improve:
        suggestions = improvement_suggestions(db)
        if args.json:
            print(json.dumps(suggestions, indent=2, ensure_ascii=False))
        else:
            print(f"Ameliorations suggerees ({len(suggestions)} prompts):")
            for s in suggestions:
                print(f"  [{s['score']:.0f}] {s['id']}")
                for issue in s["issues"]:
                    print(f"       - {issue}")
        return

    if args.export:
        index = export_index(db)
        EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(EXPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
        print(f"Exported {index['total']} prompts to {EXPORT_PATH}")
        return

    # Default: show stats
    # First index if DB is empty
    count = db.execute("SELECT COUNT(*) FROM prompts").fetchone()[0]
    if count == 0:
        print("Base vide — indexation...")
        stats = index_all(db)
        print(f"Indexed {stats['indexed']} prompts")
    print(show_stats(db))


if __name__ == "__main__":
    main()
