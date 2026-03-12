"""JARVIS Browser Memory — Persistent web page memory with bookmarks, landmarks & search.

Stores visited pages, bookmarks, HTML landmarks, notes, and enables
semantic search over browsing history. Integrates with browser_navigator
for automatic page tracking and voice-driven recall.

Usage:
    from src.browser_memory import browser_memory
    browser_memory.track_visit("https://example.com", "Example", content="...")
    browser_memory.bookmark("https://example.com", tags=["dev", "docs"])
    results = browser_memory.search_pages("python tutorial")
    landmarks = browser_memory.get_landmarks("https://example.com")
"""

from __future__ import annotations

import logging
import math
import re
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.browser_memory")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "browser_memory.db"


def _tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r'[a-zàâéèêëïîôùûüç0-9]+', text.lower()) if len(w) > 1]


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = Counter(tokens)
    total = len(tokens) or 1
    return {t: (count / total) * idf.get(t, 1.0) for t, count in tf.items()}


def _cosine_sim(v1: dict[str, float], v2: dict[str, float]) -> float:
    common = set(v1.keys()) & set(v2.keys())
    if not common:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in common)
    mag1 = math.sqrt(sum(v ** 2 for v in v1.values()))
    mag2 = math.sqrt(sum(v ** 2 for v in v2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


class BrowserMemory:
    """Persistent browser page memory with bookmarks, landmarks, and semantic search."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DB_PATH
        self._idf: dict[str, float] = {}
        self._init_db()
        self._rebuild_idf()

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT DEFAULT '',
                    domain TEXT DEFAULT '',
                    content_summary TEXT DEFAULT '',
                    tokens TEXT DEFAULT '',
                    screenshot_path TEXT DEFAULT '',
                    visit_count INTEGER DEFAULT 1,
                    bookmarked BOOLEAN DEFAULT 0,
                    tags TEXT DEFAULT '[]',
                    notes TEXT DEFAULT '',
                    first_visit REAL,
                    last_visit REAL,
                    UNIQUE(url)
                );

                CREATE TABLE IF NOT EXISTS landmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id INTEGER NOT NULL,
                    element_type TEXT NOT NULL,
                    selector TEXT DEFAULT '',
                    text_content TEXT DEFAULT '',
                    label TEXT DEFAULT '',
                    position_y INTEGER DEFAULT 0,
                    created_at REAL,
                    FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS page_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    urls TEXT NOT NULL,
                    created_at REAL,
                    last_used REAL
                );

                CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url);
                CREATE INDEX IF NOT EXISTS idx_pages_domain ON pages(domain);
                CREATE INDEX IF NOT EXISTS idx_pages_bookmarked ON pages(bookmarked);
                CREATE INDEX IF NOT EXISTS idx_landmarks_page ON landmarks(page_id);
            """)

    def _rebuild_idf(self) -> None:
        with sqlite3.connect(str(self._db_path)) as conn:
            rows = conn.execute("SELECT tokens FROM pages WHERE tokens != ''").fetchall()
        if not rows:
            return
        n_docs = len(rows)
        df: Counter = Counter()
        for (tokens_str,) in rows:
            for t in set(tokens_str.split()):
                df[t] += 1
        self._idf = {t: math.log(n_docs / (1 + count)) for t, count in df.items()}

    def _extract_domain(self, url: str) -> str:
        m = re.match(r'https?://([^/]+)', url)
        return m.group(1) if m else url

    # ── Page Tracking ──────────────────────────────────────────────────────

    def track_visit(self, url: str, title: str = "", content: str = "",
                    screenshot_path: str = "") -> int:
        """Track a page visit. Updates existing or creates new entry. Returns page ID."""
        if not url or url in ("about:blank", ""):
            return 0

        domain = self._extract_domain(url)
        summary = content[:2000] if content else ""
        tokens = _tokenize(f"{title} {domain} {summary}")
        now = time.time()

        with sqlite3.connect(str(self._db_path)) as conn:
            existing = conn.execute("SELECT id, visit_count FROM pages WHERE url = ?", (url,)).fetchone()

            if existing:
                page_id, count = existing
                conn.execute("""
                    UPDATE pages SET title = ?, content_summary = ?, tokens = ?,
                    screenshot_path = CASE WHEN ? != '' THEN ? ELSE screenshot_path END,
                    visit_count = ?, last_visit = ?, domain = ?
                    WHERE id = ?
                """, (title, summary, " ".join(tokens),
                      screenshot_path, screenshot_path,
                      count + 1, now, domain, page_id))
            else:
                c = conn.execute("""
                    INSERT INTO pages (url, title, domain, content_summary, tokens,
                    screenshot_path, visit_count, first_visit, last_visit)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """, (url, title, domain, summary, " ".join(tokens),
                      screenshot_path, now, now))
                page_id = c.lastrowid

        self._rebuild_idf()
        logger.info("Tracked visit: %s (%s)", title[:40] or url[:40], domain)
        return page_id

    # ── Bookmarks ──────────────────────────────────────────────────────────

    def bookmark(self, url: str, tags: list[str] | None = None,
                 notes: str = "") -> dict[str, Any]:
        """Bookmark current page. Creates entry if not visited yet."""
        import json

        with sqlite3.connect(str(self._db_path)) as conn:
            existing = conn.execute("SELECT id FROM pages WHERE url = ?", (url,)).fetchone()
            if existing:
                page_id = existing[0]
                updates = ["bookmarked = 1"]
                params: list[Any] = []
                if tags:
                    updates.append("tags = ?")
                    params.append(json.dumps(tags))
                if notes:
                    updates.append("notes = ?")
                    params.append(notes)
                params.append(page_id)
                conn.execute(f"UPDATE pages SET {', '.join(updates)} WHERE id = ?", params)
            else:
                now = time.time()
                domain = self._extract_domain(url)
                tokens = _tokenize(f"{domain} {notes} {' '.join(tags or [])}")
                c = conn.execute("""
                    INSERT INTO pages (url, title, domain, tokens, bookmarked, tags, notes,
                    first_visit, last_visit)
                    VALUES (?, '', ?, ?, 1, ?, ?, ?, ?)
                """, (url, domain, " ".join(tokens),
                      json.dumps(tags or []), notes, now, now))
                page_id = c.lastrowid

        logger.info("Bookmarked: %s (tags=%s)", url[:60], tags)
        return {"page_id": page_id, "bookmarked": True, "url": url, "tags": tags or []}

    def unbookmark(self, url: str) -> bool:
        with sqlite3.connect(str(self._db_path)) as conn:
            c = conn.execute("UPDATE pages SET bookmarked = 0 WHERE url = ?", (url,))
            return c.rowcount > 0

    def get_bookmarks(self, limit: int = 20) -> list[dict[str, Any]]:
        import json
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT id, url, title, domain, tags, notes, visit_count, last_visit
                FROM pages WHERE bookmarked = 1
                ORDER BY last_visit DESC LIMIT ?
            """, (limit,)).fetchall()
        return [{
            **dict(r),
            "tags": json.loads(r["tags"]) if r["tags"] else [],
        } for r in rows]

    # ── Landmarks (HTML elements of interest) ──────────────────────────────

    def store_landmarks(self, url: str, landmarks: list[dict[str, Any]]) -> int:
        """Store HTML landmarks (headings, links, buttons, forms) for a page."""
        with sqlite3.connect(str(self._db_path)) as conn:
            page = conn.execute("SELECT id FROM pages WHERE url = ?", (url,)).fetchone()
            if not page:
                return 0
            page_id = page[0]

            # Clear old landmarks for this page
            conn.execute("DELETE FROM landmarks WHERE page_id = ?", (page_id,))

            now = time.time()
            count = 0
            for lm in landmarks[:200]:  # Cap at 200 per page
                conn.execute("""
                    INSERT INTO landmarks (page_id, element_type, selector, text_content,
                    label, position_y, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (page_id, lm.get("type", ""), lm.get("selector", ""),
                      lm.get("text", "")[:200], lm.get("label", "")[:100],
                      lm.get("y", 0), now))
                count += 1

        logger.info("Stored %d landmarks for %s", count, url[:60])
        return count

    def get_landmarks(self, url: str, element_type: str | None = None) -> list[dict[str, Any]]:
        """Get stored landmarks for a page."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            page = conn.execute("SELECT id FROM pages WHERE url = ?", (url,)).fetchone()
            if not page:
                return []

            sql = "SELECT * FROM landmarks WHERE page_id = ?"
            params: list[Any] = [page[0]]
            if element_type:
                sql += " AND element_type = ?"
                params.append(element_type)
            sql += " ORDER BY position_y"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    # ── Search ─────────────────────────────────────────────────────────────

    def search_pages(self, query: str, limit: int = 10,
                     bookmarks_only: bool = False) -> list[dict[str, Any]]:
        """Semantic search over visited pages using TF-IDF similarity."""
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        query_vec = _tfidf_vector(query_tokens, self._idf)

        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            sql = "SELECT * FROM pages"
            if bookmarks_only:
                sql += " WHERE bookmarked = 1"
            rows = conn.execute(sql).fetchall()

        scored = []
        for row in rows:
            page_tokens = row["tokens"].split() if row["tokens"] else []
            if not page_tokens:
                continue
            page_vec = _tfidf_vector(page_tokens, self._idf)
            sim = _cosine_sim(query_vec, page_vec)
            if sim > 0.05:
                scored.append((sim, dict(row)))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [{
            "url": r["url"],
            "title": r["title"],
            "domain": r["domain"],
            "similarity": round(sim, 4),
            "visit_count": r["visit_count"],
            "bookmarked": bool(r["bookmarked"]),
            "last_visit": r["last_visit"],
        } for sim, r in scored[:limit]]

    def find_page_by_name(self, name: str) -> dict[str, Any] | None:
        """Fuzzy find a page by title or domain fragment."""
        name_lower = name.lower().strip()
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            # Exact domain match first
            row = conn.execute(
                "SELECT * FROM pages WHERE domain LIKE ? ORDER BY last_visit DESC LIMIT 1",
                (f"%{name_lower}%",)
            ).fetchone()
            if row:
                return dict(row)
            # Title match
            row = conn.execute(
                "SELECT * FROM pages WHERE LOWER(title) LIKE ? ORDER BY last_visit DESC LIMIT 1",
                (f"%{name_lower}%",)
            ).fetchone()
            return dict(row) if row else None

    # ── History ─────────────────────────────────────────────────────────────

    def recent_pages(self, limit: int = 10) -> list[dict[str, Any]]:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT url, title, domain, visit_count, bookmarked, last_visit
                FROM pages ORDER BY last_visit DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def most_visited(self, limit: int = 10) -> list[dict[str, Any]]:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT url, title, domain, visit_count, bookmarked, last_visit
                FROM pages ORDER BY visit_count DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ── Sessions (save/restore tab groups) ─────────────────────────────────

    def save_session(self, name: str, urls: list[str]) -> dict[str, Any]:
        """Save a group of tabs as a named session."""
        import json
        now = time.time()
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO page_sessions (name, urls, created_at, last_used)
                VALUES (?, ?, ?, ?)
            """, (name, json.dumps(urls), now, now))
        return {"session": name, "tabs": len(urls), "urls": urls}

    def load_session(self, name: str) -> list[str]:
        """Load a saved session. Returns list of URLs."""
        import json
        with sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute(
                "SELECT urls FROM page_sessions WHERE name = ?", (name,)
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE page_sessions SET last_used = ? WHERE name = ?",
                    (time.time(), name)
                )
                return json.loads(row[0])
        return []

    def list_sessions(self) -> list[dict[str, Any]]:
        import json
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT name, urls, last_used FROM page_sessions ORDER BY last_used DESC"
            ).fetchall()
        return [{"name": r["name"], "tabs": len(json.loads(r["urls"])),
                 "last_used": r["last_used"]} for r in rows]

    # ── Notes ──────────────────────────────────────────────────────────────

    def add_note(self, url: str, note: str) -> bool:
        """Add/append a note to a page."""
        with sqlite3.connect(str(self._db_path)) as conn:
            existing = conn.execute("SELECT notes FROM pages WHERE url = ?", (url,)).fetchone()
            if not existing:
                return False
            old_notes = existing[0] or ""
            new_notes = f"{old_notes}\n{note}".strip() if old_notes else note
            conn.execute("UPDATE pages SET notes = ? WHERE url = ?", (new_notes, url))
        return True

    # ── Stats ──────────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        with sqlite3.connect(str(self._db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
            bookmarks = conn.execute("SELECT COUNT(*) FROM pages WHERE bookmarked = 1").fetchone()[0]
            landmarks = conn.execute("SELECT COUNT(*) FROM landmarks").fetchone()[0]
            sessions = conn.execute("SELECT COUNT(*) FROM page_sessions").fetchone()[0]
            domains = conn.execute("SELECT COUNT(DISTINCT domain) FROM pages").fetchone()[0]
        return {
            "total_pages": total,
            "bookmarks": bookmarks,
            "landmarks": landmarks,
            "sessions": sessions,
            "unique_domains": domains,
            "idf_vocab": len(self._idf),
        }

    def cleanup(self, max_pages: int = 5000) -> int:
        """Remove oldest non-bookmarked pages if over limit."""
        with sqlite3.connect(str(self._db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
            if total <= max_pages:
                return 0
            excess = total - max_pages
            c = conn.execute("""
                DELETE FROM pages WHERE id IN (
                    SELECT id FROM pages WHERE bookmarked = 0
                    ORDER BY last_visit ASC LIMIT ?
                )
            """, (excess,))
            removed = c.rowcount
        if removed:
            self._rebuild_idf()
        return removed


# Global singleton
browser_memory = BrowserMemory()
