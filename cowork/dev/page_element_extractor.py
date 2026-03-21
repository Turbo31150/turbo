#!/usr/bin/env python3
"""Page Element Extractor — Extract and memorize interactive elements from any page.

Connects via Chrome DevTools Protocol (CDP) WebSocket to extract buttons, links,
forms, inputs from LinkedIn, Codeur.com, etc. Stores in etoile.db for instant
reuse — never need to reload/rescan pages.

Usage:
    python cowork/dev/page_element_extractor.py --once --url https://linkedin.com/feed
    python cowork/dev/page_element_extractor.py --extract-all
    python cowork/dev/page_element_extractor.py --recall linkedin
    python cowork/dev/page_element_extractor.py --list-stored
"""

import argparse
import json
import sqlite3
import urllib.request
try:
    import websocket
except ImportError:
    websocket = None
import time
from datetime import datetime
from pathlib import Path

TURBO = Path(__file__).resolve().parent.parent.parent
DB_PATH = TURBO / "etoile.db"
CDP_URL = "http://127.0.0.1:9222"

# Pre-registered extraction configs per site
SITE_CONFIGS = {
    "linkedin": {
        "url": "https://www.linkedin.com/feed/",
        "selectors": {
            "share_button": "button.share-box-feed-entry__trigger",
            "share_textbox": "div.ql-editor[data-placeholder]",
            "post_button": "button.share-actions__primary-action",
            "like_buttons": "button[aria-label*='J\\'aime'], button[aria-label*='Like']",
            "comment_buttons": "button[aria-label*='Commenter'], button[aria-label*='Comment']",
            "notification_icon": "a[href='/notifications/']",
            "messaging_icon": "a[href='/messaging/']",
            "profile_menu": "button[class*='global-nav__primary-link--me']",
            "search_input": "input[class*='search-global-typeahead']",
            "feed_posts": "div.feed-shared-update-v2",
            "post_author": "span.feed-shared-actor__name",
            "post_text": "div.feed-shared-text",
            "connect_buttons": "button[aria-label*='Se connecter'], button[aria-label*='Connect']",
            "follow_buttons": "button[aria-label*='Suivre'], button[aria-label*='Follow']",
        },
        "js_extracts": {
            "feed_count": "document.querySelectorAll('.feed-shared-update-v2').length",
            "notification_count": "document.querySelector('.notification-badge__count')?.textContent || '0'",
            "messaging_count": "document.querySelector('.msg-overlay-bubble-header__badge')?.textContent || '0'",
        }
    },
    "codeur": {
        "url": "https://www.codeur.com/projects",
        "selectors": {
            "project_cards": "div.project-card, article.project",
            "project_titles": "h2.project-card__title a, a.project-title",
            "project_budgets": "span.project-card__budget, span.budget",
            "project_skills": "span.project-card__skill, span.skill-tag",
            "apply_buttons": "a.project-card__apply, a.btn-apply",
            "search_input": "input[name='q'], input.search-input",
            "category_links": "a.category-link, nav.categories a",
            "login_button": "a[href*='login'], a[href*='connexion']",
            "register_button": "a[href*='register'], a[href*='inscription']",
            "pagination": "nav.pagination a, a.page-link",
        },
        "js_extracts": {
            "project_count": "document.querySelectorAll('.project-card, article.project').length",
            "page_title": "document.title",
        }
    },
    "github": {
        "url": "https://github.com/Turbo31150",
        "selectors": {
            "repo_cards": "div[class*='pinned-item-list'] li",
            "repo_links": "a[data-hovercard-type='repository']",
            "star_buttons": "button[class*='starred'], form.unstarred button",
            "notification_indicator": "a[href='/notifications']",
            "new_repo_button": "a[href='/new']",
            "search_input": "input[name='q']",
            "profile_nav": "nav[aria-label='User profile'] a",
            "contribution_graph": "svg.js-calendar-graph-svg",
        },
        "js_extracts": {
            "repo_count": "document.querySelectorAll('a[data-hovercard-type=\"repository\"]').length",
            "followers": "document.querySelector('a[href*=\"followers\"] span')?.textContent || '0'",
        }
    },
    "ai_studio": {
        "url": "https://aistudio.google.com/",
        "selectors": {
            "new_prompt": "button[aria-label*='New'], button[class*='new-prompt']",
            "prompt_input": "textarea, div[contenteditable='true']",
            "run_button": "button[aria-label*='Run'], button[class*='run']",
            "model_selector": "button[class*='model-selector'], select[class*='model']",
        },
        "js_extracts": {
            "page_ready": "document.readyState",
        }
    }
}


def init_db():
    """Ensure page_elements table exists."""
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS page_elements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site TEXT NOT NULL,
        element_name TEXT NOT NULL,
        selector TEXT NOT NULL,
        element_type TEXT DEFAULT 'css',
        last_verified TEXT,
        verified_count INTEGER DEFAULT 0,
        extra_data TEXT,
        UNIQUE(site, element_name)
    )""")
    db.commit()
    db.close()


def store_elements(site, elements):
    """Store extracted elements in etoile.db."""
    db = sqlite3.connect(str(DB_PATH))
    stored = 0
    for name, selector in elements.items():
        try:
            db.execute("""INSERT OR REPLACE INTO page_elements
                (site, element_name, selector, element_type, last_verified, verified_count)
                VALUES (?, ?, ?, 'css', ?, COALESCE((SELECT verified_count FROM page_elements WHERE site=? AND element_name=?), 0) + 1)""",
                (site, name, selector, datetime.now().isoformat(), site, name))
            stored += 1
        except Exception:
            pass
    db.commit()
    db.close()
    return stored


def store_js_results(site, js_data):
    """Store JS extraction results in memories."""
    db = sqlite3.connect(str(DB_PATH))
    for key, value in js_data.items():
        try:
            db.execute("""INSERT OR REPLACE INTO memories
                (category, key, value, confidence, source, updated_at)
                VALUES (?, ?, ?, 1.0, 'page_extractor', ?)""",
                (f"page_data_{site}", key, str(value), datetime.now().isoformat()))
        except Exception:
            pass
    db.commit()
    db.close()


def get_cdp_pages():
    """List Chrome CDP pages."""
    try:
        resp = urllib.request.urlopen(f"{CDP_URL}/json", timeout=3)
        return json.loads(resp.read())
    except Exception:
        return []


def find_page_by_url(url_fragment):
    """Find a CDP page matching URL fragment."""
    pages = get_cdp_pages()
    for p in pages:
        if url_fragment.lower() in p.get("url", "").lower():
            return p
    return None


def extract_via_cdp(page_id, site_config):
    """Extract elements from a page via CDP WebSocket."""
    pages = get_cdp_pages()
    page = next((p for p in pages if p["id"] == page_id), None)
    if not page:
        return {"error": "Page not found"}

    ws_url = page.get("webSocketDebuggerUrl")
    if not ws_url:
        return {"error": "No WebSocket URL"}

    results = {"selectors_found": {}, "js_results": {}}

    try:
        import websocket as ws_lib
        conn = ws_lib.create_connection(ws_url, timeout=10)

        # Test each selector
        msg_id = 1
        for name, selector in site_config.get("selectors", {}).items():
            cmd = json.dumps({
                "id": msg_id, "method": "Runtime.evaluate",
                "params": {"expression": f"document.querySelectorAll('{selector}').length"}
            })
            conn.send(cmd)
            resp = json.loads(conn.recv())
            count = resp.get("result", {}).get("result", {}).get("value", 0)
            results["selectors_found"][name] = {"selector": selector, "count": count, "found": count > 0}
            msg_id += 1

        # Run JS extracts
        for name, expr in site_config.get("js_extracts", {}).items():
            cmd = json.dumps({
                "id": msg_id, "method": "Runtime.evaluate",
                "params": {"expression": expr}
            })
            conn.send(cmd)
            resp = json.loads(conn.recv())
            value = resp.get("result", {}).get("result", {}).get("value", "N/A")
            results["js_results"][name] = value
            msg_id += 1

        conn.close()
    except ImportError:
        # Fallback: use urllib to call CDP HTTP endpoint
        results["error"] = "websocket module not installed, using stored selectors only"
        results["selectors_found"] = {k: {"selector": v, "count": -1, "found": "unknown"}
                                       for k, v in site_config.get("selectors", {}).items()}

    return results


def extract_all_sites():
    """Extract elements from all configured sites."""
    init_db()
    report = {"timestamp": datetime.now().isoformat(), "sites": {}}

    for site, config in SITE_CONFIGS.items():
        # Store selectors regardless (pre-registered)
        stored = store_elements(site, config["selectors"])

        # Try to find open page
        page = find_page_by_url(config["url"].split("//")[1].split("/")[0])
        if page:
            results = extract_via_cdp(page["id"], config)
            store_js_results(site, results.get("js_results", {}))
            report["sites"][site] = {
                "status": "LIVE", "page_id": page["id"],
                "selectors_stored": stored,
                "selectors_found": sum(1 for v in results.get("selectors_found", {}).values()
                                       if v.get("found")),
                "js_results": results.get("js_results", {})
            }
        else:
            report["sites"][site] = {
                "status": "STORED_ONLY", "selectors_stored": stored,
                "note": "Page not open, selectors pre-registered for instant use"
            }

    report["total_selectors"] = sum(len(c["selectors"]) for c in SITE_CONFIGS.values())
    print(json.dumps(report, indent=2, default=str))
    return report


def recall_site(site_name):
    """Recall stored elements for a site."""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT * FROM page_elements WHERE site LIKE ?",
                      (f"%{site_name}%",)).fetchall()
    result = {"site": site_name, "elements": [dict(r) for r in rows]}
    # Also get page_data from memories
    mems = db.execute("SELECT key, value FROM memories WHERE category LIKE ?",
                      (f"page_data_%{site_name}%",)).fetchall()
    result["cached_data"] = {r["key"]: r["value"] for r in mems}
    db.close()
    print(json.dumps(result, indent=2, default=str))
    return result


def list_stored():
    """List all stored page elements."""
    db = sqlite3.connect(str(DB_PATH))
    rows = db.execute("""SELECT site, COUNT(*) as elements, MAX(last_verified) as last_check
                         FROM page_elements GROUP BY site""").fetchall()
    result = {"stored_sites": [{"site": r[0], "elements": r[1], "last_check": r[2]} for r in rows]}
    db.close()
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description="Page Element Extractor — CDP + etoile.db")
    parser.add_argument("--once", action="store_true", help="Extract from open pages")
    parser.add_argument("--extract-all", action="store_true", help="Extract all configured sites")
    parser.add_argument("--recall", type=str, help="Recall stored elements for site")
    parser.add_argument("--list-stored", action="store_true", help="List all stored sites")
    parser.add_argument("--url", type=str, help="Specific URL to extract from")
    args = parser.parse_args()

    init_db()

    if args.extract_all or args.once:
        extract_all_sites()
    elif args.recall:
        recall_site(args.recall)
    elif args.list_stored:
        list_stored()
    else:
        extract_all_sites()


if __name__ == "__main__":
    main()
