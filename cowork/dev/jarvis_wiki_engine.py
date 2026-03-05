#!/usr/bin/env python3
"""jarvis_wiki_engine.py — Wiki engine. Internal wiki with articles (topic, content, tags). Full-text search.
Usage: python dev/jarvis_wiki_engine.py --create "TOPIC" --once
"""
import argparse, json, os, sqlite3, subprocess, time, hashlib, re
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "wiki_engine.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        topic TEXT NOT NULL,
        content TEXT,
        tags TEXT,
        author TEXT DEFAULT 'jarvis',
        version INTEGER DEFAULT 1,
        views INTEGER DEFAULT 0,
        updated REAL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS revisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        article_id INTEGER,
        content TEXT,
        version INTEGER,
        change_summary TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tag TEXT UNIQUE,
        article_count INTEGER DEFAULT 0
    )""")

    # Create FTS virtual table if not exists
    try:
        db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts
            USING fts5(topic, content, tags)""")
    except Exception:
        pass  # FTS5 might not be available

    db.commit()
    return db


def do_create(topic, content=None, tags=None):
    """Create a new wiki article."""
    db = init_db()
    now = time.time()

    if not content:
        content = f"# {topic}\n\nArticle about {topic}. Edit with --update to add content."

    tag_list = tags.split(",") if tags else [topic.lower().split()[0]]
    tags_str = json.dumps(tag_list)

    # Check if topic already exists
    existing = db.execute(
        "SELECT id FROM articles WHERE topic=?", (topic,)
    ).fetchone()
    if existing:
        db.close()
        return {
            "ts": datetime.now().isoformat(),
            "action": "create",
            "status": "exists",
            "article_id": existing[0],
            "topic": topic,
            "message": "Topic already exists. Use --update to modify."
        }

    article_id = db.execute(
        "INSERT INTO articles (ts, topic, content, tags, updated) VALUES (?,?,?,?,?)",
        (now, topic, content, tags_str, now)
    ).lastrowid

    # Insert into FTS
    try:
        db.execute(
            "INSERT INTO articles_fts (rowid, topic, content, tags) VALUES (?,?,?,?)",
            (article_id, topic, content, tags_str)
        )
    except Exception:
        pass

    # Update tag counts
    for tag in tag_list:
        tag = tag.strip().lower()
        db.execute(
            "INSERT INTO tags (tag, article_count) VALUES (?,1) ON CONFLICT(tag) DO UPDATE SET article_count=article_count+1",
            (tag,)
        )

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "action": "create",
        "status": "created",
        "article_id": article_id,
        "topic": topic,
        "tags": tag_list,
        "content_length": len(content)
    }


def do_search(query=None):
    """Search wiki articles (full-text or tag search)."""
    db = init_db()

    if not query:
        # Return all articles
        rows = db.execute(
            "SELECT id, topic, tags, views, ts FROM articles ORDER BY updated DESC LIMIT 30"
        ).fetchall()
    else:
        # Try FTS first
        try:
            rows = db.execute(
                "SELECT a.id, a.topic, a.tags, a.views, a.ts FROM articles a "
                "JOIN articles_fts f ON a.id = f.rowid "
                "WHERE articles_fts MATCH ? ORDER BY rank LIMIT 20",
                (query,)
            ).fetchall()
        except Exception:
            # Fallback to LIKE search
            like_q = f"%{query}%"
            rows = db.execute(
                "SELECT id, topic, tags, views, ts FROM articles "
                "WHERE topic LIKE ? OR content LIKE ? OR tags LIKE ? "
                "ORDER BY updated DESC LIMIT 20",
                (like_q, like_q, like_q)
            ).fetchall()

    db.close()
    return {
        "ts": datetime.now().isoformat(),
        "action": "search",
        "query": query,
        "results_count": len(rows),
        "results": [
            {
                "id": r[0],
                "topic": r[1],
                "tags": json.loads(r[2]) if r[2] else [],
                "views": r[3],
                "created": datetime.fromtimestamp(r[4]).isoformat()
            }
            for r in rows
        ]
    }


def do_update(article_id=None, topic=None, content=None, tags=None):
    """Update an existing wiki article."""
    db = init_db()

    if article_id:
        row = db.execute(
            "SELECT id, topic, content, version FROM articles WHERE id=?", (article_id,)
        ).fetchone()
    elif topic:
        row = db.execute(
            "SELECT id, topic, content, version FROM articles WHERE topic=?", (topic,)
        ).fetchone()
    else:
        db.close()
        return {"ts": datetime.now().isoformat(), "action": "update", "error": "Provide --article-id or topic"}

    if not row:
        db.close()
        return {"ts": datetime.now().isoformat(), "action": "update", "error": "Article not found"}

    art_id, art_topic, old_content, version = row
    new_version = version + 1
    new_content = content or old_content

    # Save revision
    db.execute(
        "INSERT INTO revisions (ts, article_id, content, version, change_summary) VALUES (?,?,?,?,?)",
        (time.time(), art_id, old_content, version, "Updated via CLI")
    )

    # Update article
    updates = {"version": new_version, "updated": time.time()}
    if content:
        updates["content"] = content
    if tags:
        updates["tags"] = json.dumps(tags.split(","))

    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [art_id]
    db.execute(f"UPDATE articles SET {set_clause} WHERE id=?", values)

    # Update FTS
    try:
        db.execute("DELETE FROM articles_fts WHERE rowid=?", (art_id,))
        db.execute(
            "INSERT INTO articles_fts (rowid, topic, content, tags) VALUES (?,?,?,?)",
            (art_id, art_topic, new_content, updates.get("tags", ""))
        )
    except Exception:
        pass

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "action": "update",
        "article_id": art_id,
        "topic": art_topic,
        "version": new_version,
        "status": "updated"
    }


def do_export():
    """Export all wiki articles."""
    db = init_db()
    rows = db.execute(
        "SELECT id, topic, content, tags, views, ts, version FROM articles ORDER BY topic"
    ).fetchall()

    articles = []
    for r in rows:
        articles.append({
            "id": r[0],
            "topic": r[1],
            "content": r[2][:500] if r[2] else "",
            "tags": json.loads(r[3]) if r[3] else [],
            "views": r[4],
            "created": datetime.fromtimestamp(r[5]).isoformat(),
            "version": r[6]
        })

    # Export to file
    export_path = DEV / "data" / "wiki_export.json"
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    all_tags = db.execute("SELECT tag, article_count FROM tags ORDER BY article_count DESC").fetchall()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "action": "export",
        "total_articles": len(articles),
        "export_path": str(export_path),
        "tags": [{"tag": t[0], "count": t[1]} for t in all_tags],
        "articles": [{"id": a["id"], "topic": a["topic"], "version": a["version"]} for a in articles[:20]]
    }


def main():
    parser = argparse.ArgumentParser(description="Wiki engine — Internal wiki with full-text search")
    parser.add_argument("--create", metavar="TOPIC", help="Create a new article")
    parser.add_argument("--content", metavar="TEXT", help="Article content (for --create or --update)")
    parser.add_argument("--tags", metavar="TAGS", help="Comma-separated tags")
    parser.add_argument("--search", nargs="?", const="", metavar="QUERY", help="Search articles")
    parser.add_argument("--update", action="store_true", help="Update an article")
    parser.add_argument("--article-id", type=int, metavar="ID", help="Article ID for update")
    parser.add_argument("--export", action="store_true", help="Export all articles")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.create:
        result = do_create(args.create, args.content, args.tags)
    elif args.search is not None:
        result = do_search(args.search if args.search else None)
    elif args.update:
        result = do_update(article_id=args.article_id, content=args.content, tags=args.tags)
    elif args.export:
        result = do_export()
    else:
        db = init_db()
        result = {
            "ts": datetime.now().isoformat(),
            "status": "ok",
            "db": str(DB_PATH),
            "total_articles": db.execute("SELECT COUNT(*) FROM articles").fetchone()[0],
            "total_tags": db.execute("SELECT COUNT(*) FROM tags").fetchone()[0],
            "help": "Use --create TOPIC / --search [QUERY] / --update / --export"
        }
        db.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
