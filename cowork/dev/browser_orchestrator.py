#!/usr/bin/env python3
"""Browser Orchestrator — Unified control of Chrome, BrowserOS, and Comet DevMCP.

3 navigateurs, 1 interface:
  - Chrome/Chromium via CDP (port 9222) + chrome-devtools-mcp
  - BrowserOS MCP (port 9000) — automation, snapshots, 40+ integrations
  - Comet DevMCP (Python, C:\Jarvis\mcp\servers\cometdevmcp) — headless Chrome modifie

Usage:
    python cowork/dev/browser_orchestrator.py --once          # Health check all browsers
    python cowork/dev/browser_orchestrator.py --navigate URL  # Open URL in all browsers
    python cowork/dev/browser_orchestrator.py --screenshot    # Screenshot from Chrome CDP
    python cowork/dev/browser_orchestrator.py --browser chrome --navigate URL
    python cowork/dev/browser_orchestrator.py --browser browseros --navigate URL
    python cowork/dev/browser_orchestrator.py --list-pages    # List open pages
    python cowork/dev/browser_orchestrator.py --start-all     # Start all browser services
"""

import argparse
import json
import sqlite3
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

TURBO = Path(__file__).resolve().parent.parent.parent
DB_PATH = TURBO / "etoile.db"

BROWSERS = {
    "chrome": {
        "name": "Chrome DevTools CDP",
        "health_url": "http://127.0.0.1:9222/json/version",
        "pages_url": "http://127.0.0.1:9222/json",
        "port": 9222,
        "type": "cdp",
    },
    "browseros": {
        "name": "BrowserOS MCP",
        "health_url": "http://127.0.0.1:9000/health",
        "port": 9000,
        "type": "mcp",
    },
    "comet": {
        "name": "Comet DevMCP",
        "task_name": "Jarvis-MCP-cometdevmcp",
        "bootstrap": r"C:\Jarvis\mcp\bootstrap\cometdevmcp.ps1",
        "type": "python",
    },
}


def http_get(url, timeout=5):
    """GET request, return parsed JSON or None."""
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        return json.loads(resp.read())
    except Exception:
        return None


def http_post(url, data, timeout=10):
    """POST JSON request."""
    payload = json.dumps(data).encode()
    try:
        req = urllib.request.Request(url, data=payload,
            headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def check_health():
    """Check all browser services health."""
    results = {}
    # Chrome CDP
    data = http_get(BROWSERS["chrome"]["health_url"])
    results["chrome"] = {
        "status": "UP" if data else "DOWN",
        "version": data.get("Browser", "unknown") if data else None,
        "port": 9222
    }

    # BrowserOS
    data = http_get(BROWSERS["browseros"]["health_url"])
    results["browseros"] = {
        "status": "UP" if data and data.get("status") == "ok" else "DOWN",
        "cdp_connected": data.get("cdpConnected") if data else False,
        "port": 9000
    }

    # Comet — check scheduled task state
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "Get-ScheduledTask -TaskName 'Jarvis-MCP-cometdevmcp' | Select-Object -ExpandProperty State"],
            capture_output=True, text=True, timeout=5)
        state = r.stdout.strip()
        results["comet"] = {"status": state if state else "UNKNOWN", "type": "scheduled_task"}
    except Exception:
        results["comet"] = {"status": "UNKNOWN"}

    return results


def list_chrome_pages():
    """List open pages in Chrome via CDP."""
    data = http_get(BROWSERS["chrome"]["pages_url"])
    if not data:
        return []
    return [{"title": p.get("title", ""), "url": p.get("url", ""),
             "type": p.get("type", "")} for p in data if p.get("type") == "page"]


def navigate_chrome(url):
    """Open a new tab in Chrome via CDP."""
    encoded = urllib.parse.quote(url, safe="")
    result = http_get(f"http://127.0.0.1:9222/json/new?{encoded}")
    return result


def navigate_browseros(url):
    """Open a new page via BrowserOS MCP."""
    return http_post("http://127.0.0.1:9000/mcp", {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "new_page", "arguments": {"url": url}}
    })


def start_all():
    """Start all browser services."""
    results = {}
    # Start BrowserOS
    try:
        subprocess.run(["powershell.exe", "-NoProfile", "-Command",
            "schtasks /Run /tn 'Jarvis-MCP-broweros'"], capture_output=True, timeout=5)
        results["browseros"] = "started"
    except Exception as e:
        results["browseros"] = f"error: {e}"

    # Start Comet
    try:
        subprocess.run(["powershell.exe", "-NoProfile", "-Command",
            "schtasks /Run /tn 'Jarvis-MCP-cometdevmcp'"], capture_output=True, timeout=5)
        results["comet"] = "started"
    except Exception as e:
        results["comet"] = f"error: {e}"

    # Chrome CDP — already running if DevTools port is open
    data = http_get(BROWSERS["chrome"]["health_url"])
    results["chrome"] = "already_running" if data else "not_available"

    return results


def log_action(action, details=""):
    """Log to etoile.db."""
    try:
        db = sqlite3.connect(str(DB_PATH))
        db.execute("INSERT INTO cluster_health (timestamp,node,status,model,latency_ms) VALUES (?,?,?,?,?)",
            (datetime.now().isoformat(), "browser_orchestrator", "OK", action, 0))
        db.commit()
        db.close()
    except Exception:
        pass


def main():
    import urllib.parse
    parser = argparse.ArgumentParser(description="Browser Orchestrator — Chrome + BrowserOS + Comet")
    parser.add_argument("--once", action="store_true", help="Health check all browsers")
    parser.add_argument("--navigate", type=str, help="Open URL")
    parser.add_argument("--browser", choices=["chrome", "browseros", "comet", "all"], default="all")
    parser.add_argument("--list-pages", action="store_true", help="List Chrome pages")
    parser.add_argument("--screenshot", action="store_true", help="Take screenshot (via BrowserOS)")
    parser.add_argument("--start-all", action="store_true", help="Start all browser services")
    args = parser.parse_args()

    if args.start_all:
        result = start_all()
        log_action("start_all")
        print(json.dumps(result, indent=2))

    elif args.list_pages:
        pages = list_chrome_pages()
        print(json.dumps({"pages": pages, "count": len(pages)}, indent=2))

    elif args.navigate:
        results = {}
        if args.browser in ("chrome", "all"):
            results["chrome"] = navigate_chrome(args.navigate)
        if args.browser in ("browseros", "all"):
            results["browseros"] = navigate_browseros(args.navigate)
        log_action(f"navigate:{args.navigate[:50]}")
        print(json.dumps(results, indent=2, default=str))

    elif args.once:
        health = check_health()
        pages = list_chrome_pages()
        result = {
            "timestamp": datetime.now().isoformat(),
            "browsers": health,
            "chrome_pages": len(pages),
            "total_up": sum(1 for b in health.values() if b.get("status") in ("UP", "Running", "Ready")),
        }
        log_action("health_check")
        print(json.dumps(result, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
