#!/usr/bin/env python3
"""INTENSIVE Social Automation Engine — MONITOR > DETECT > GENERATE > PUBLISH > LOG.

Monitors notifications, news, messages across LinkedIn, GitHub, Telegram, Email.
Auto-responds and publishes via M1 cluster for content generation.
Stdlib-only. All output JSON. Logs to etoile.db memories table.
"""

import argparse
import json
import sqlite3
import subprocess
import time
import urllib.request
import urllib.error
import os
import sys
from datetime import datetime, timezone

# --- Config ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "etoile.db")
BROWSEROS_URL = "http://127.0.0.1:9000/mcp"
M1_URL = "http://127.0.0.1:1234/api/v1/chat"
OL1_URL = "http://127.0.0.1:11434/api/chat"
TELEGRAM_CHAT_ID = 2010747443
MONITOR_INTERVAL = 60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_to_db(action: str, platform: str, content: str, status: str = "ok"):
    """Log event to etoile.db memories table (category=social_automation)."""
    try:
        db = os.path.normpath(DB_PATH)
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS memories "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, category TEXT, "
            "action TEXT, platform TEXT, content TEXT, status TEXT)"
        )
        conn.execute(
            "INSERT INTO memories (timestamp, category, action, platform, content, status) "
            "VALUES (?, 'social_automation', ?, ?, ?, ?)",
            (_now(), action, platform, content[:2000], status),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(json.dumps({"log_error": str(e)}), file=sys.stderr)


def _get_telegram_token() -> str:
    """Read Telegram bot token from etoile.db api_keys table."""
    try:
        db = os.path.normpath(DB_PATH)
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT value FROM api_keys WHERE key='telegram_bot_token' OR name='telegram_bot_token' LIMIT 1"
        ).fetchone()
        conn.close()
        return row[0] if row else os.environ.get("TELEGRAM_BOT_TOKEN", "")
    except Exception:
        return os.environ.get("TELEGRAM_BOT_TOKEN", "")


def _call_m1(prompt: str, max_tokens: int = 1024) -> str:
    """Call M1 (qwen3-8b) with /nothink for content generation."""
    payload = json.dumps({
        "model": "qwen3-8b",
        "input": f"/nothink\n{prompt}",
        "temperature": 0.3,
        "max_output_tokens": max_tokens,
        "stream": False,
        "store": False,
    }).encode()
    req = urllib.request.Request(M1_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        for block in reversed(data.get("output", [])):
            if block.get("type") == "message":
                for c in block.get("content", []):
                    if c.get("type") == "output_text":
                        return c["text"]
        return str(data)
    except Exception as e:
        return f"[M1 error: {e}]"


def _call_ol1_minimax(prompt: str) -> str:
    """Call OL1 minimax cloud (web search) with think:false."""
    payload = json.dumps({
        "model": "minimax-m2.5:cloud",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
    }).encode()
    req = urllib.request.Request(OL1_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data.get("message", {}).get("content", str(data))
    except Exception as e:
        return f"[OL1 error: {e}]"


def _browseros_call(method: str, params: dict) -> dict:
    """Call BrowserOS MCP tool via HTTP."""
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(BROWSEROS_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


# ---- Platform Checkers ----

def check_linkedin_notifications() -> list:
    """Navigate LinkedIn notifications via BrowserOS, parse content."""
    _browseros_call("navigate_page", {"url": "https://www.linkedin.com/notifications/"})
    time.sleep(3)
    result = _browseros_call("get_page_content", {})
    content = result.get("result", {}).get("content", "") if isinstance(result.get("result"), dict) else str(result)
    if not content or "error" in str(result).lower():
        return [{"platform": "linkedin", "type": "error", "detail": str(result)}]
    notifications = [{"platform": "linkedin", "type": "notification", "raw": content[:3000]}]
    _log_to_db("check", "linkedin", f"Found notifications chunk ({len(content)} chars)")
    return notifications


def check_github_activity() -> list:
    """Check GitHub notifications via gh CLI."""
    try:
        proc = subprocess.run(
            ["gh", "api", "notifications", "--paginate", "-q",
             '.[] | {id: .id, repo: .repository.full_name, type: .subject.type, title: .subject.title, reason: .reason}'],
            capture_output=True, text=True, timeout=15,
        )
        items = []
        for line in proc.stdout.strip().splitlines():
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        _log_to_db("check", "github", f"Found {len(items)} notifications")
        return [{"platform": "github", "type": n.get("type", "unknown"), **n} for n in items[:20]]
    except Exception as e:
        return [{"platform": "github", "type": "error", "detail": str(e)}]


def check_telegram_updates() -> list:
    """Check Telegram updates via Bot API getUpdates."""
    token = _get_telegram_token()
    if not token:
        return [{"platform": "telegram", "type": "error", "detail": "no token"}]
    url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=5&limit=20"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
        updates = data.get("result", [])
        _log_to_db("check", "telegram", f"Found {len(updates)} updates")
        return [
            {"platform": "telegram", "type": "message",
             "chat_id": u.get("message", {}).get("chat", {}).get("id"),
             "text": u.get("message", {}).get("text", ""),
             "from": u.get("message", {}).get("from", {}).get("first_name", ""),
             "update_id": u.get("update_id")}
            for u in updates if u.get("message")
        ]
    except Exception as e:
        return [{"platform": "telegram", "type": "error", "detail": str(e)}]


# ---- Generation ----

def generate_response(context: str, platform: str) -> str:
    """Generate contextual response via M1 cluster."""
    prompt = (
        f"Tu es un assistant professionnel. Genere une reponse appropriee pour {platform}.\n"
        f"Contexte: {context[:1500]}\n"
        f"Reponse (courte, professionnelle, en francais):"
    )
    return _call_m1(prompt)


def check_tech_news() -> list:
    """Fetch latest tech news via OL1 minimax web search."""
    raw = _call_ol1_minimax(
        "Latest tech news today 2026: AI, cloud, startups, crypto. "
        "Give 5 bullet points with source URLs if possible."
    )
    commentary = _call_m1(
        f"Voici les dernieres news tech:\n{raw[:2000]}\n\n"
        "Genere un commentaire LinkedIn professionnel (3-5 lignes, hashtags inclus)."
    )
    _log_to_db("tech_news", "all", raw[:1000])
    return [{"type": "tech_news", "raw": raw[:2000], "commentary": commentary}]


def propose_services() -> list:
    """Generate service proposals based on project posts."""
    raw = _call_ol1_minimax(
        "Derniers projets publies sur Codeur.com et LinkedIn Jobs France: "
        "developpement web, IA, automatisation. Liste 5 projets recents."
    )
    proposal = _call_m1(
        f"Projets detectes:\n{raw[:2000]}\n\n"
        "Genere une proposition de services professionnelle pour un freelance full-stack IA/automation. "
        "Format: objet, pitch 3 lignes, tarif indicatif."
    )
    _log_to_db("propose_services", "linkedin", proposal[:1000])
    return [{"type": "service_proposal", "projects": raw[:2000], "proposal": proposal}]


# ---- Publishing ----

def publish_response(platform: str, content: str, target: str = "", dry_run: bool = False) -> dict:
    """Publish response to platform. Returns status dict."""
    result = {"platform": platform, "content": content[:500], "dry_run": dry_run, "ts": _now()}
    if dry_run:
        result["status"] = "dry_run"
        _log_to_db("publish_dry", platform, content[:500])
        return result

    if platform == "linkedin":
        _browseros_call("navigate_page", {"url": "https://www.linkedin.com/feed/"})
        time.sleep(2)
        _browseros_call("click", {"selector": "[data-test-id='share-box-feed']"})
        time.sleep(1)
        _browseros_call("fill", {"selector": "[role='textbox']", "value": content})
        result["status"] = "posted"

    elif platform == "github" and target:
        proc = subprocess.run(
            ["gh", "issue", "comment", target, "--body", content],
            capture_output=True, text=True, timeout=15,
        )
        result["status"] = "commented" if proc.returncode == 0 else f"error: {proc.stderr}"

    elif platform == "telegram":
        token = _get_telegram_token()
        payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": content, "parse_mode": "Markdown"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload, headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result["status"] = "sent" if json.loads(resp.read()).get("ok") else "failed"
        except Exception as e:
            result["status"] = f"error: {e}"
    else:
        result["status"] = "unsupported"

    _log_to_db("publish", platform, content[:500], result["status"])
    return result


# ---- Main Cycle ----

def run_cycle(platforms: list, dry_run: bool = False) -> dict:
    """Run one full MONITOR > DETECT > GENERATE > PUBLISH > LOG cycle."""
    cycle = {"ts": _now(), "platforms": platforms, "dry_run": dry_run, "results": []}

    if "linkedin" in platforms:
        notifs = check_linkedin_notifications()
        for n in notifs:
            if n.get("type") != "error":
                resp = generate_response(json.dumps(n), "linkedin")
                pub = publish_response("linkedin", resp, dry_run=dry_run)
                cycle["results"].append({"check": n, "response": resp, "publish": pub})

    if "github" in platforms:
        activity = check_github_activity()
        for a in activity:
            if a.get("type") != "error" and a.get("reason") in ("mention", "review_requested", "assign"):
                resp = generate_response(json.dumps(a), "github")
                target = f"{a.get('repo', '')}#{a.get('id', '')}"
                pub = publish_response("github", resp, target=target, dry_run=dry_run)
                cycle["results"].append({"check": a, "response": resp, "publish": pub})

    if "telegram" in platforms:
        updates = check_telegram_updates()
        for u in updates:
            if u.get("type") != "error" and u.get("text"):
                resp = generate_response(u["text"], "telegram")
                pub = publish_response("telegram", resp, dry_run=dry_run)
                cycle["results"].append({"check": u, "response": resp, "publish": pub})

    news = check_tech_news()
    cycle["results"].append({"tech_news": news})

    proposals = propose_services()
    cycle["results"].append({"proposals": proposals})

    _log_to_db("cycle_complete", ",".join(platforms), json.dumps(cycle["results"])[:2000])
    return cycle


def main():
    parser = argparse.ArgumentParser(description="INTENSIVE Social Automation Engine")
    parser.add_argument("--once", action="store_true", help="Single cycle then exit")
    parser.add_argument("--monitor", action="store_true", help="Continuous loop (60s interval)")
    parser.add_argument("--linkedin", action="store_true", help="LinkedIn only")
    parser.add_argument("--github", action="store_true", help="GitHub only")
    parser.add_argument("--telegram", action="store_true", help="Telegram only")
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't publish")
    args = parser.parse_args()

    platforms = []
    if args.linkedin:
        platforms.append("linkedin")
    if args.github:
        platforms.append("github")
    if args.telegram:
        platforms.append("telegram")
    if not platforms:
        platforms = ["linkedin", "github", "telegram"]

    if args.once or (not args.monitor):
        result = run_cycle(platforms, dry_run=args.dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.monitor:
        print(json.dumps({"status": "monitor_started", "interval": MONITOR_INTERVAL, "platforms": platforms}))
        while True:
            try:
                result = run_cycle(platforms, dry_run=args.dry_run)
                print(json.dumps(result, ensure_ascii=False))
                sys.stdout.flush()
                time.sleep(MONITOR_INTERVAL)
            except KeyboardInterrupt:
                print(json.dumps({"status": "monitor_stopped", "ts": _now()}))
                break


if __name__ == "__main__":
    main()
