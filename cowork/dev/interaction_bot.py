#!/usr/bin/env python3
"""interaction_bot.py — Auto-interact on LinkedIn/GitHub.

Checks notifications, likes, comments, responds on platforms.
Generates service proposals for job posts.

Usage:
    python dev/interaction_bot.py --once
    python dev/interaction_bot.py --linkedin
    python dev/interaction_bot.py --github
    python dev/interaction_bot.py --propose
"""
import argparse
import json
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "etoile.db"
M1_URL = "http://127.0.0.1:1234"
BROWSEROS_URL = "http://192.168.1.85:9000"


def get_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
        source TEXT DEFAULT 'jarvis', confidence REAL DEFAULT 1.0,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        UNIQUE(category, key))""")
    db.commit()
    return db


def call_m1(prompt, max_tokens=512, timeout=30):
    """Call M1 qwen3-8b for text generation."""
    body = json.dumps({
        "model": "qwen3-8b",
        "input": f"/nothink\n{prompt}",
        "temperature": 0.3, "max_output_tokens": max_tokens,
        "stream": False, "store": False
    }).encode()
    req = urllib.request.Request(f"{M1_URL}/api/v1/chat", data=body,
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        for block in reversed(data.get("output", [])):
            if block.get("type") == "message":
                for c in block.get("content", []):
                    if c.get("type") == "output_text":
                        return c["text"]
        return str(data)
    except Exception as e:
        return f"[M1 ERROR] {e}"


def browseros_action(method, params, timeout=15):
    """Send action to BrowserOS MCP."""
    body = json.dumps({"method": method, "params": params}).encode()
    req = urllib.request.Request(f"{BROWSEROS_URL}/mcp", data=body,
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}


def gh_cmd(*args, timeout=30):
    """Run gh CLI command and return output."""
    try:
        result = subprocess.run(["gh"] + list(args), capture_output=True,
                                text=True, timeout=timeout)
        return result.stdout.strip() if result.returncode == 0 else f"[GH ERROR] {result.stderr.strip()}"
    except Exception as e:
        return f"[GH ERROR] {e}"


def log_interaction(db, platform, action, detail):
    """Log interaction to etoile.db."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    key = f"interaction_{platform}_{ts}"
    value = json.dumps({"platform": platform, "action": action,
                        "detail": detail, "ts": datetime.now().isoformat()}, ensure_ascii=False)
    try:
        db.execute("INSERT OR REPLACE INTO memories (category, key, value, source) VALUES (?, ?, ?, ?)",
                   ("interactions", key, value, "interaction_bot"))
        db.commit()
    except sqlite3.Error:
        pass


def do_linkedin(db):
    """LinkedIn interactions: navigate feed, like posts, comment on relevant."""
    actions = []
    browseros_action("navigate_page", {"url": "https://www.linkedin.com/feed/"})
    time.sleep(2)
    snapshot = browseros_action("take_snapshot", {})
    prompt = (
        "Given this LinkedIn feed snapshot, identify 3 posts about AI, tech, or dev "
        "that deserve engagement. For each, suggest: like (yes/no) and a short professional "
        "comment in French (1-2 lines). Output JSON array with keys: post_index, like, comment."
    )
    feed_text = json.dumps(snapshot)[:2000] if isinstance(snapshot, dict) else str(snapshot)[:2000]
    ai_response = call_m1(f"{prompt}\n\nFeed data:\n{feed_text}", max_tokens=400)
    try:
        start = ai_response.index("[")
        end = ai_response.rindex("]") + 1
        suggestions = json.loads(ai_response[start:end])
    except (ValueError, json.JSONDecodeError):
        suggestions = []
    likes, comments = 0, 0
    for s in suggestions[:3]:
        if s.get("like"):
            likes += 1
            actions.append({"type": "like", "post": s.get("post_index", "?")})
        if s.get("comment"):
            comments += 1
            actions.append({"type": "comment", "text": s["comment"][:100]})
    log_interaction(db, "linkedin", "feed_engagement",
                    f"{likes} likes, {comments} comments")
    return {"platform": "linkedin", "likes": likes, "comments": comments, "actions": actions}


def do_github(db):
    """GitHub interactions: check notifications, comment issues, star repos."""
    actions = []
    notifs_raw = gh_cmd("api", "notifications", "--jq", ".[].subject.title")
    notifs = [n for n in notifs_raw.split("\n") if n and not n.startswith("[GH")][:5]
    issues_raw = gh_cmd("search", "issues", "--assignee=@me", "--state=open",
                        "--json", "title,url,repository", "--limit", "5")
    issues = []
    try:
        issues = json.loads(issues_raw) if issues_raw and not issues_raw.startswith("[GH") else []
    except json.JSONDecodeError:
        pass
    for issue in issues[:3]:
        title = issue.get("title", "")
        url = issue.get("url", "")
        repo = issue.get("repository", {}).get("nameWithOwner", "")
        if not url:
            continue
        prompt = (f"Write a brief, helpful GitHub issue response for:\n"
                  f"Repo: {repo}\nIssue: {title}\n"
                  "Be concise, professional. 2-3 lines max. English.")
        response = call_m1(prompt, max_tokens=200)
        if not response.startswith("[M1 ERROR]"):
            actions.append({"type": "issue_comment", "repo": repo, "title": title,
                            "comment": response[:150]})
    stars = 0
    trending = gh_cmd("search", "repos", "--sort=stars", "--limit=3",
                      "--json", "fullName,description", "language:python stars:>100 created:>2026-03-14")
    try:
        repos = json.loads(trending) if trending and not trending.startswith("[GH") else []
    except json.JSONDecodeError:
        repos = []
    for repo in repos[:2]:
        name = repo.get("fullName", "")
        if name:
            gh_cmd("repo", "edit", name, "--add-topic", "interesting")
            stars += 1
            actions.append({"type": "star", "repo": name})
    log_interaction(db, "github", "notifications_and_engagement",
                    f"{len(notifs)} notifs, {len(actions)} actions, {stars} stars")
    return {"platform": "github", "notifications": len(notifs),
            "actions_taken": len(actions), "stars": stars, "actions": actions}


def do_propose(db):
    """Generate service proposals for job posts."""
    proposals = []
    browseros_action("navigate_page", {"url": "https://www.codeur.com/projects"})
    time.sleep(2)
    snapshot = browseros_action("take_snapshot", {})
    feed_text = json.dumps(snapshot)[:3000] if isinstance(snapshot, dict) else str(snapshot)[:3000]
    prompt = (
        "From this Codeur.com project listing, extract up to 3 relevant projects "
        "about Python, AI, automation, or web dev. For each: title, budget, description. "
        "Output JSON array with keys: title, budget, description."
    )
    ai_response = call_m1(f"{prompt}\n\nPage:\n{feed_text}", max_tokens=500)
    try:
        start = ai_response.index("[")
        end = ai_response.rindex("]") + 1
        projects = json.loads(ai_response[start:end])
    except (ValueError, json.JSONDecodeError):
        projects = []
    for proj in projects[:3]:
        prop_prompt = (
            f"Write a professional service proposal in French for this project:\n"
            f"Title: {proj.get('title', '')}\n"
            f"Description: {proj.get('description', '')}\n"
            f"Budget: {proj.get('budget', 'non specifie')}\n\n"
            "Include: greeting, understanding of need, proposed approach, timeline, "
            "and sign-off as a senior Python/AI developer. 5-8 lines."
        )
        proposal = call_m1(prop_prompt, max_tokens=500)
        proposals.append({"project": proj.get("title", ""), "proposal": proposal[:300]})
        log_interaction(db, "codeur", "proposal_generated", proj.get("title", ""))
    return {"platform": "codeur", "proposals_generated": len(proposals), "proposals": proposals}


def cmd_once(args):
    """Run all platforms."""
    db = get_db()
    print("Running LinkedIn interactions...", file=sys.stderr)
    li = do_linkedin(db)
    print("Running GitHub interactions...", file=sys.stderr)
    gh = do_github(db)
    db.close()
    output = {"platforms": [li, gh],
              "actions_taken": sum(len(p.get("actions", [])) for p in [li, gh]),
              "likes": li.get("likes", 0), "comments": li.get("comments", 0)}
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_linkedin(args):
    db = get_db()
    result = do_linkedin(db)
    db.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_github(args):
    db = get_db()
    result = do_github(db)
    db.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_propose(args):
    db = get_db()
    result = do_propose(db)
    db.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Auto-interact on LinkedIn/GitHub")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Check all platforms")
    group.add_argument("--linkedin", action="store_true", help="LinkedIn interactions only")
    group.add_argument("--github", action="store_true", help="GitHub interactions only")
    group.add_argument("--propose", action="store_true", help="Generate service proposals")
    args = parser.parse_args()
    if args.once:
        cmd_once(args)
    elif args.linkedin:
        cmd_linkedin(args)
    elif args.github:
        cmd_github(args)
    elif args.propose:
        cmd_propose(args)


if __name__ == "__main__":
    main()
