#!/usr/bin/env python3
"""ia_story_generator.py — AI-powered story generator with coherence tracking.
COWORK #234 — Batch 106: IA Generative

Usage:
    python dev/ia_story_generator.py --generate "une IA qui prend conscience"
    python dev/ia_story_generator.py --continue
    python dev/ia_story_generator.py --style fantasy
    python dev/ia_story_generator.py --export story.md
    python dev/ia_story_generator.py --once
"""
import argparse, json, sqlite3, time, subprocess, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "story_generator.db"

STYLES = {
    "sf": {"prompt_prefix": "Ecris une histoire de science-fiction.", "tone": "technologique, futuriste"},
    "fantasy": {"prompt_prefix": "Ecris une histoire de fantasy.", "tone": "magique, epique"},
    "thriller": {"prompt_prefix": "Ecris un thriller haletant.", "tone": "suspense, tension"},
    "romance": {"prompt_prefix": "Ecris une histoire romantique.", "tone": "emotionnel, tendre"},
    "horreur": {"prompt_prefix": "Ecris une histoire d'horreur.", "tone": "sombre, effrayant"},
    "humour": {"prompt_prefix": "Ecris une histoire humoristique.", "tone": "drole, leger"},
    "policier": {"prompt_prefix": "Ecris un polar.", "tone": "enquete, mystere"},
}

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS stories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        theme TEXT NOT NULL,
        style TEXT DEFAULT 'sf',
        title TEXT,
        status TEXT DEFAULT 'in_progress',
        chapters INTEGER DEFAULT 0,
        total_words INTEGER DEFAULT 0,
        characters TEXT DEFAULT '[]',
        places TEXT DEFAULT '[]'
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS story_chapters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        story_id INTEGER NOT NULL,
        chapter_num INTEGER NOT NULL,
        ts TEXT NOT NULL,
        content TEXT NOT NULL,
        word_count INTEGER,
        model TEXT DEFAULT 'M1',
        duration_ms INTEGER,
        FOREIGN KEY (story_id) REFERENCES stories(id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS story_exports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        story_id INTEGER NOT NULL,
        ts TEXT NOT NULL,
        format TEXT,
        file_path TEXT,
        success INTEGER DEFAULT 1
    )""")
    db.commit()
    return db

def query_m1(prompt):
    payload = json.dumps({
        "model": "qwen3-8b",
        "input": f"/nothink\\n{prompt}",
        "temperature": 0.7,
        "max_output_tokens": 1024,
        "stream": False,
        "store": False
    })
    try:
        cmd = f'curl -s --max-time 60 http://127.0.0.1:1234/api/v1/chat -H "Content-Type: application/json" -d {json.dumps(payload)}'
        start = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=65, shell=True)
        elapsed = int((time.time() - start) * 1000)
        if r.stdout.strip():
            data = json.loads(r.stdout)
            for item in reversed(data.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return c.get("text", "").strip(), elapsed
        return None, elapsed
    except Exception:
        return None, 0

def extract_entities(text):
    """Extract character names and places from story text."""
    import re
    # Simple heuristic: capitalized words that appear multiple times
    words = re.findall(r'\b[A-Z][a-z]{2,}\b', text)
    word_freq = {}
    for w in words:
        word_freq[w] = word_freq.get(w, 0) + 1
    characters = [w for w, c in word_freq.items() if c >= 2][:10]
    return characters

def do_generate(theme, style="sf"):
    db = init_db()
    style_info = STYLES.get(style, STYLES["sf"])
    now = datetime.now().isoformat()

    prompt = f"""{style_info['prompt_prefix']}
Theme: {theme}
Ton: {style_info['tone']}
Ecris le premier chapitre (300-400 mots). Inclus:
- Un titre pour l'histoire
- Des personnages nommes
- Un lieu precis
- Une accroche de fin de chapitre
Format: TITRE: [titre]
CHAPITRE 1: [contenu]"""

    text, elapsed = query_m1(prompt)

    title = theme[:50]
    content = text or "Generation echouee — M1 indisponible"
    if text and "TITRE:" in text:
        parts = text.split("CHAPITRE", 1)
        title = parts[0].replace("TITRE:", "").strip()[:100]
        content = "CHAPITRE" + parts[1] if len(parts) > 1 else text

    word_count = len(content.split())
    characters = extract_entities(content)

    cursor = db.execute("INSERT INTO stories (created_at, updated_at, theme, style, title, chapters, total_words, characters) VALUES (?,?,?,?,?,?,?,?)",
                        (now, now, theme, style, title, 1, word_count, json.dumps(characters)))
    story_id = cursor.lastrowid

    db.execute("INSERT INTO story_chapters (story_id, chapter_num, ts, content, word_count, model, duration_ms) VALUES (?,?,?,?,?,?,?)",
               (story_id, 1, now, content, word_count, "M1", elapsed))
    db.commit()

    result = {
        "action": "generate",
        "story_id": story_id,
        "title": title,
        "theme": theme,
        "style": style,
        "chapter": 1,
        "word_count": word_count,
        "characters": characters,
        "content_preview": content[:500],
        "duration_ms": elapsed,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_continue():
    db = init_db()
    story = db.execute("SELECT id, theme, style, title, chapters, characters FROM stories WHERE status='in_progress' ORDER BY id DESC LIMIT 1").fetchone()
    if not story:
        db.close()
        return {"error": "No active story. Use --generate first."}

    story_id, theme, style, title, chapters, chars = story
    next_chapter = chapters + 1
    characters = json.loads(chars) if chars else []

    # Get last chapter for context
    last = db.execute("SELECT content FROM story_chapters WHERE story_id=? ORDER BY chapter_num DESC LIMIT 1", (story_id,)).fetchone()
    last_content = last[0][:500] if last else ""

    style_info = STYLES.get(style, STYLES["sf"])
    prompt = f"""Continue cette histoire ({style_info['tone']}).
Titre: {title}
Personnages: {', '.join(characters[:5])}
Dernier chapitre: {last_content}

Ecris le chapitre {next_chapter} (300-400 mots). Maintiens la coherence des personnages et des lieux.
CHAPITRE {next_chapter}:"""

    text, elapsed = query_m1(prompt)
    content = text or f"Chapitre {next_chapter} — Generation echouee"
    word_count = len(content.split())
    new_chars = extract_entities(content)
    all_chars = list(set(characters + new_chars))

    now = datetime.now().isoformat()
    db.execute("INSERT INTO story_chapters (story_id, chapter_num, ts, content, word_count, model, duration_ms) VALUES (?,?,?,?,?,?,?)",
               (story_id, next_chapter, now, content, word_count, "M1", elapsed))
    db.execute("UPDATE stories SET chapters=?, total_words=total_words+?, characters=?, updated_at=? WHERE id=?",
               (next_chapter, word_count, json.dumps(all_chars), now, story_id))
    db.commit()

    result = {
        "action": "continue",
        "story_id": story_id,
        "title": title,
        "chapter": next_chapter,
        "word_count": word_count,
        "total_words": db.execute("SELECT total_words FROM stories WHERE id=?", (story_id,)).fetchone()[0],
        "characters": all_chars,
        "content_preview": content[:500],
        "duration_ms": elapsed,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_style(style_name=None):
    result = {
        "action": "styles",
        "available_styles": {k: v for k, v in STYLES.items()},
        "selected": style_name,
        "ts": datetime.now().isoformat()
    }
    return result

def do_export(file_path):
    db = init_db()
    story = db.execute("SELECT id, title, theme, style, chapters FROM stories ORDER BY id DESC LIMIT 1").fetchone()
    if not story:
        db.close()
        return {"error": "No stories to export"}

    story_id = story[0]
    chapters = db.execute("SELECT chapter_num, content FROM story_chapters WHERE story_id=? ORDER BY chapter_num", (story_id,)).fetchall()

    output = Path(file_path)
    try:
        lines = [f"# {story[1]}\n", f"*Theme: {story[2]} | Style: {story[3]}*\n\n---\n"]
        for ch in chapters:
            lines.append(f"\n## Chapitre {ch[0]}\n\n{ch[1]}\n")
        lines.append(f"\n---\n*Genere par JARVIS IA — {datetime.now().strftime('%Y-%m-%d')}*\n")

        output.write_text("\n".join(lines), encoding="utf-8")
        db.execute("INSERT INTO story_exports (story_id, ts, format, file_path, success) VALUES (?,?,?,?,?)",
                   (story_id, datetime.now().isoformat(), output.suffix, str(output.resolve()), 1))
        db.commit()

        result = {
            "action": "export",
            "story_id": story_id,
            "title": story[1],
            "chapters_exported": len(chapters),
            "file_path": str(output.resolve()),
            "success": True,
            "ts": datetime.now().isoformat()
        }
    except Exception as e:
        result = {"action": "export", "error": str(e)}

    db.close()
    return result

def do_once():
    db = init_db()
    total = db.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
    active = db.execute("SELECT COUNT(*) FROM stories WHERE status='in_progress'").fetchone()[0]
    total_chapters = db.execute("SELECT COUNT(*) FROM story_chapters").fetchone()[0]
    total_words = db.execute("SELECT SUM(total_words) FROM stories").fetchone()[0] or 0
    result = {
        "status": "ok",
        "total_stories": total,
        "active_stories": active,
        "total_chapters": total_chapters,
        "total_words": total_words,
        "available_styles": list(STYLES.keys()),
        "model": "M1 (qwen3-8b)",
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="IA Story Generator — COWORK #234")
    parser.add_argument("--generate", type=str, metavar="THEME", help="Generate new story")
    parser.add_argument("--continue", dest="continue_story", action="store_true", help="Continue current story")
    parser.add_argument("--style", type=str, help="Set/show story style")
    parser.add_argument("--export", type=str, metavar="FILE", help="Export story to MD file")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.generate:
        style = args.style or "sf"
        print(json.dumps(do_generate(args.generate, style), ensure_ascii=False, indent=2))
    elif args.continue_story:
        print(json.dumps(do_continue(), ensure_ascii=False, indent=2))
    elif args.style:
        print(json.dumps(do_style(args.style), ensure_ascii=False, indent=2))
    elif args.export:
        print(json.dumps(do_export(args.export), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
