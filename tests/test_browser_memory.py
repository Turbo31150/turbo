"""Tests for src/browser_memory.py — Persistent browser page memory.

Covers: page tracking, bookmarks, landmarks, TF-IDF search, sessions,
notes, stats, cleanup, and edge cases.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.browser_memory import BrowserMemory, _tokenize, _tfidf_vector, _cosine_sim


@pytest.fixture
def mem(tmp_path):
    """BrowserMemory instance with an isolated temp database."""
    db = tmp_path / "test_browser.db"
    return BrowserMemory(db_path=db)


# ===========================================================================
# Tokenizer & TF-IDF helpers
# ===========================================================================

class TestTokenizer:
    def test_basic_tokenize(self):
        assert _tokenize("Hello World") == ["hello", "world"]

    def test_filters_single_char(self):
        assert _tokenize("a b cd ef") == ["cd", "ef"]

    def test_french_accents(self):
        tokens = _tokenize("éléphant café résumé")
        assert "éléphant" in tokens
        assert "café" in tokens

    def test_strips_punctuation(self):
        tokens = _tokenize("hello, world! foo-bar (test)")
        assert "hello" in tokens
        assert "world" in tokens
        assert "foo" in tokens
        assert "bar" in tokens

    def test_empty_string(self):
        assert _tokenize("") == []


class TestTFIDF:
    def test_tfidf_vector_basic(self):
        tokens = ["python", "web", "python"]
        idf = {"python": 1.0, "web": 2.0}
        vec = _tfidf_vector(tokens, idf)
        assert vec["python"] > 0
        assert vec["web"] > 0

    def test_cosine_sim_identical(self):
        v = {"a": 1.0, "b": 2.0}
        assert _cosine_sim(v, v) == pytest.approx(1.0)

    def test_cosine_sim_orthogonal(self):
        v1 = {"a": 1.0}
        v2 = {"b": 1.0}
        assert _cosine_sim(v1, v2) == 0.0

    def test_cosine_sim_empty(self):
        assert _cosine_sim({}, {"a": 1.0}) == 0.0

    def test_cosine_sim_zero_magnitude(self):
        assert _cosine_sim({"a": 0.0}, {"a": 1.0}) == 0.0


# ===========================================================================
# Page Tracking
# ===========================================================================

class TestPageTracking:
    def test_track_visit_creates_page(self, mem):
        pid = mem.track_visit("https://example.com", "Example", content="Hello world content")
        assert pid > 0

    def test_track_visit_increments_count(self, mem):
        mem.track_visit("https://example.com", "Example")
        mem.track_visit("https://example.com", "Example Updated")
        pages = mem.recent_pages()
        assert pages[0]["visit_count"] == 2
        assert pages[0]["title"] == "Example Updated"

    def test_track_visit_blank_url_ignored(self, mem):
        assert mem.track_visit("about:blank") == 0
        assert mem.track_visit("") == 0

    def test_track_multiple_urls(self, mem):
        mem.track_visit("https://a.com", "Site A")
        mem.track_visit("https://b.com", "Site B")
        mem.track_visit("https://c.com", "Site C")
        pages = mem.recent_pages()
        assert len(pages) == 3

    def test_domain_extraction(self, mem):
        mem.track_visit("https://docs.python.org/3/library/", "Python Docs")
        pages = mem.recent_pages()
        assert pages[0]["domain"] == "docs.python.org"

    def test_content_truncated_to_2000(self, mem):
        long_content = "x" * 5000
        mem.track_visit("https://long.com", "Long", content=long_content)
        # Should not crash — content is truncated internally


# ===========================================================================
# Bookmarks
# ===========================================================================

class TestBookmarks:
    def test_bookmark_existing_page(self, mem):
        mem.track_visit("https://example.com", "Example")
        result = mem.bookmark("https://example.com", tags=["dev", "docs"])
        assert result["bookmarked"] is True
        assert result["tags"] == ["dev", "docs"]

    def test_bookmark_new_page(self, mem):
        result = mem.bookmark("https://new.com", tags=["test"], notes="important")
        assert result["bookmarked"] is True
        assert result["page_id"] > 0

    def test_get_bookmarks(self, mem):
        mem.track_visit("https://a.com", "A")
        mem.track_visit("https://b.com", "B")
        mem.bookmark("https://a.com", tags=["tag1"])
        bookmarks = mem.get_bookmarks()
        assert len(bookmarks) == 1
        assert bookmarks[0]["url"] == "https://a.com"
        assert "tag1" in bookmarks[0]["tags"]

    def test_unbookmark(self, mem):
        mem.track_visit("https://a.com", "A")
        mem.bookmark("https://a.com")
        assert mem.unbookmark("https://a.com") is True
        assert len(mem.get_bookmarks()) == 0

    def test_unbookmark_nonexistent(self, mem):
        assert mem.unbookmark("https://nope.com") is False

    def test_bookmark_with_notes(self, mem):
        mem.track_visit("https://a.com", "A")
        mem.bookmark("https://a.com", notes="My important note")
        bookmarks = mem.get_bookmarks()
        assert bookmarks[0]["notes"] == "My important note"


# ===========================================================================
# Landmarks
# ===========================================================================

class TestLandmarks:
    def test_store_and_retrieve_landmarks(self, mem):
        mem.track_visit("https://example.com", "Example")
        landmarks = [
            {"type": "heading", "selector": "h1", "text": "Main Title", "y": 0},
            {"type": "link", "selector": "a.nav", "text": "About", "y": 100},
            {"type": "button", "selector": "button#submit", "text": "Submit", "y": 500},
        ]
        count = mem.store_landmarks("https://example.com", landmarks)
        assert count == 3

        result = mem.get_landmarks("https://example.com")
        assert len(result) == 3
        assert result[0]["text_content"] == "Main Title"

    def test_store_landmarks_replaces_old(self, mem):
        mem.track_visit("https://example.com", "Example")
        mem.store_landmarks("https://example.com", [{"type": "heading", "text": "Old"}])
        mem.store_landmarks("https://example.com", [{"type": "heading", "text": "New"}])
        result = mem.get_landmarks("https://example.com")
        assert len(result) == 1
        assert result[0]["text_content"] == "New"

    def test_store_landmarks_nonexistent_page(self, mem):
        assert mem.store_landmarks("https://nope.com", [{"type": "heading"}]) == 0

    def test_get_landmarks_by_type(self, mem):
        mem.track_visit("https://example.com", "Example")
        mem.store_landmarks("https://example.com", [
            {"type": "heading", "text": "Title"},
            {"type": "link", "text": "Click"},
            {"type": "heading", "text": "Section"},
        ])
        headings = mem.get_landmarks("https://example.com", element_type="heading")
        assert len(headings) == 2

    def test_landmarks_cap_at_200(self, mem):
        mem.track_visit("https://big.com", "Big Page")
        many = [{"type": "link", "text": f"Link {i}"} for i in range(300)]
        count = mem.store_landmarks("https://big.com", many)
        assert count == 200

    def test_get_landmarks_nonexistent_page(self, mem):
        assert mem.get_landmarks("https://nope.com") == []


# ===========================================================================
# Search
# ===========================================================================

class TestSearch:
    def test_search_finds_relevant_page(self, mem):
        mem.track_visit("https://python.org", "Python Programming Language",
                        content="Python is a versatile programming language for python developers")
        mem.track_visit("https://rust-lang.org", "Rust Programming Language",
                        content="Rust is a systems programming language for performance")
        mem.track_visit("https://example.com", "Example Site", content="Just an example site")
        mem.track_visit("https://docs.com", "Documentation", content="Some documentation here")
        results = mem.search_pages("python")
        assert len(results) >= 1
        assert results[0]["domain"] == "python.org"

    def test_search_empty_query(self, mem):
        mem.track_visit("https://example.com", "Example")
        assert mem.search_pages("") == []

    def test_search_no_results(self, mem):
        mem.track_visit("https://example.com", "Example", content="Hello world")
        results = mem.search_pages("xyzzyunknownterm")
        assert results == []

    def test_search_bookmarks_only(self, mem):
        mem.track_visit("https://a.com", "Python Docs", content="python programming")
        mem.track_visit("https://b.com", "Python Tutorial", content="python tutorial")
        mem.bookmark("https://b.com")
        results = mem.search_pages("python", bookmarks_only=True)
        urls = [r["url"] for r in results]
        assert "https://b.com" in urls
        assert "https://a.com" not in urls

    def test_search_result_fields(self, mem):
        mem.track_visit("https://example.com", "Test Page", content="test content")
        results = mem.search_pages("test")
        if results:
            r = results[0]
            assert "url" in r
            assert "title" in r
            assert "similarity" in r
            assert "visit_count" in r
            assert "bookmarked" in r


class TestFindByName:
    def test_find_by_domain(self, mem):
        mem.track_visit("https://github.com/user/repo", "My Repo")
        page = mem.find_page_by_name("github")
        assert page is not None
        assert "github.com" in page["domain"]

    def test_find_by_title(self, mem):
        mem.track_visit("https://example.com", "JARVIS Documentation")
        page = mem.find_page_by_name("jarvis")
        assert page is not None
        assert page["title"] == "JARVIS Documentation"

    def test_find_not_found(self, mem):
        mem.track_visit("https://example.com", "Test")
        assert mem.find_page_by_name("zzzznotfound") is None


# ===========================================================================
# Sessions
# ===========================================================================

class TestSessions:
    def test_save_and_load_session(self, mem):
        urls = ["https://a.com", "https://b.com", "https://c.com"]
        result = mem.save_session("work", urls)
        assert result["tabs"] == 3

        loaded = mem.load_session("work")
        assert loaded == urls

    def test_load_nonexistent_session(self, mem):
        assert mem.load_session("nope") == []

    def test_save_overwrites_existing(self, mem):
        mem.save_session("dev", ["https://a.com"])
        mem.save_session("dev", ["https://b.com", "https://c.com"])
        loaded = mem.load_session("dev")
        assert len(loaded) == 2
        assert "https://a.com" not in loaded

    def test_list_sessions(self, mem):
        mem.save_session("work", ["https://a.com"])
        mem.save_session("research", ["https://b.com", "https://c.com"])
        sessions = mem.list_sessions()
        assert len(sessions) == 2
        names = [s["name"] for s in sessions]
        assert "work" in names
        assert "research" in names

    def test_session_tabs_count(self, mem):
        mem.save_session("test", ["https://a.com", "https://b.com"])
        sessions = mem.list_sessions()
        s = next(s for s in sessions if s["name"] == "test")
        assert s["tabs"] == 2


# ===========================================================================
# Notes
# ===========================================================================

class TestNotes:
    def test_add_note(self, mem):
        mem.track_visit("https://example.com", "Test")
        assert mem.add_note("https://example.com", "First note") is True

    def test_add_note_appends(self, mem):
        mem.track_visit("https://example.com", "Test")
        mem.add_note("https://example.com", "Note 1")
        mem.add_note("https://example.com", "Note 2")
        bookmarks = mem.get_bookmarks()
        # Notes are on the page, check via bookmark
        mem.bookmark("https://example.com")
        bookmarks = mem.get_bookmarks()
        assert "Note 1" in bookmarks[0]["notes"]
        assert "Note 2" in bookmarks[0]["notes"]

    def test_add_note_nonexistent_page(self, mem):
        assert mem.add_note("https://nope.com", "Note") is False


# ===========================================================================
# Stats & Cleanup
# ===========================================================================

class TestStats:
    def test_stats_empty_db(self, mem):
        stats = mem.get_stats()
        assert stats["total_pages"] == 0
        assert stats["bookmarks"] == 0
        assert stats["landmarks"] == 0
        assert stats["sessions"] == 0

    def test_stats_with_data(self, mem):
        mem.track_visit("https://a.com", "A")
        mem.track_visit("https://b.com", "B")
        mem.bookmark("https://a.com")
        mem.store_landmarks("https://a.com", [{"type": "heading", "text": "T"}])
        mem.save_session("s1", ["https://a.com"])
        stats = mem.get_stats()
        assert stats["total_pages"] == 2
        assert stats["bookmarks"] == 1
        assert stats["landmarks"] == 1
        assert stats["sessions"] == 1
        assert stats["unique_domains"] == 2


class TestCleanup:
    def test_cleanup_under_limit(self, mem):
        mem.track_visit("https://a.com", "A")
        assert mem.cleanup(max_pages=100) == 0

    def test_cleanup_removes_oldest(self, mem):
        for i in range(10):
            mem.track_visit(f"https://site{i}.com", f"Site {i}")
        removed = mem.cleanup(max_pages=5)
        assert removed == 5
        pages = mem.recent_pages(limit=100)
        assert len(pages) == 5

    def test_cleanup_preserves_bookmarks(self, mem):
        mem.track_visit("https://old.com", "Old")
        mem.bookmark("https://old.com")
        for i in range(10):
            mem.track_visit(f"https://new{i}.com", f"New {i}")
        mem.cleanup(max_pages=5)
        page = mem.find_page_by_name("old")
        assert page is not None  # Bookmarked page preserved


# ===========================================================================
# History
# ===========================================================================

class TestHistory:
    def test_recent_pages_order(self, mem):
        mem.track_visit("https://first.com", "First")
        mem.track_visit("https://second.com", "Second")
        mem.track_visit("https://third.com", "Third")
        pages = mem.recent_pages()
        assert pages[0]["domain"] == "third.com"
        assert pages[2]["domain"] == "first.com"

    def test_most_visited_order(self, mem):
        mem.track_visit("https://rare.com", "Rare")
        for _ in range(5):
            mem.track_visit("https://popular.com", "Popular")
        pages = mem.most_visited()
        assert pages[0]["domain"] == "popular.com"
        assert pages[0]["visit_count"] == 5

    def test_recent_pages_limit(self, mem):
        for i in range(20):
            mem.track_visit(f"https://site{i}.com", f"Site {i}")
        pages = mem.recent_pages(limit=5)
        assert len(pages) == 5
