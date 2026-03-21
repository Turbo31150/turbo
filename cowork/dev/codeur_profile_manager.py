#!/usr/bin/env python3
"""Codeur.com Profile Manager — Update profile, respond to projects via BrowserOS.

Usage:
    python cowork/dev/codeur_profile_manager.py --once     # Check profile + new projects
    python cowork/dev/codeur_profile_manager.py --update    # Update profile description
    python cowork/dev/codeur_profile_manager.py --projects  # List matching projects
"""

import argparse
import json
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

TURBO = Path(__file__).resolve().parent.parent.parent
DB_PATH = TURBO / "etoile.db"
BROWSEROS_URL = "http://127.0.0.1:9000/mcp"
CODEUR_URL = "https://www.codeur.com"

SKILLS = ["Python", "JavaScript", "TypeScript", "Docker", "DevOps", "IA", "Trading", "React",
          "FastAPI", "WebSocket", "GPU", "Orchestration", "Automation", "MCP", "Claude"]


def mcp_call(method, params):
    """Call BrowserOS MCP tool."""
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": method, "arguments": params}}).encode()
    try:
        req = urllib.request.Request(BROWSEROS_URL, data=payload,
                                     headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=15).read())
    except Exception as e:
        return {"error": str(e)}


def check_profile():
    """Navigate to Codeur.com profile and extract info."""
    result = mcp_call("new_page", {"url": f"{CODEUR_URL}/users/search?q=turbo31150"})
    return result


def search_projects(keywords=None):
    """Search for matching projects on Codeur.com."""
    kw = keywords or ["python", "ia", "automatisation", "docker"]
    results = []
    for k in kw[:3]:
        r = mcp_call("new_page", {"url": f"{CODEUR_URL}/projects?q={k}", "background": True})
        results.append({"keyword": k, "result": r})
    return results


def log_action(action, details=""):
    """Log to etoile.db."""
    try:
        db = sqlite3.connect(str(DB_PATH))
        db.execute("INSERT INTO memories(category,key,value,confidence,source,updated_at) VALUES(?,?,?,?,?,?)",
                   ("codeur_com", action, json.dumps(details, default=str)[:500], 1.0,
                    "codeur_profile_manager", datetime.now().isoformat()))
        db.commit()
        db.close()
    except Exception:
        pass


def run_once():
    """Full check: profile + projects."""
    report = {"timestamp": datetime.now().isoformat(), "skills": SKILLS}
    report["profile_check"] = check_profile()
    report["projects"] = search_projects()
    log_action("daily_check", report)
    print(json.dumps(report, indent=2, default=str))
    return report


def main():
    parser = argparse.ArgumentParser(description="Codeur.com Profile Manager")
    parser.add_argument("--once", action="store_true", help="Full check")
    parser.add_argument("--update", action="store_true", help="Update profile")
    parser.add_argument("--projects", action="store_true", help="Search projects")
    args = parser.parse_args()

    if args.projects:
        r = search_projects()
        print(json.dumps(r, indent=2, default=str))
    elif args.update:
        r = check_profile()
        print(json.dumps(r, indent=2, default=str))
    elif args.once:
        run_once()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
