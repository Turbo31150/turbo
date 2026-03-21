#!/usr/bin/env python3
"""calendar_sync.py — Sync with Google Calendar via MCP, fallback to local calendar.json."""
import argparse
import json
import os
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "etoile.db")
LOCAL_CAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "calendar.json")
MCP_URL = "http://192.168.1.85:9001/mcp"


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "CREATE TABLE IF NOT EXISTS memories ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, category TEXT, content TEXT)"
    )
    con.commit()
    return con


def log_memory(con, category, content):
    con.execute(
        "INSERT INTO memories (ts, category, content) VALUES (?, ?, ?)",
        (datetime.now().isoformat(), category, json.dumps(content, ensure_ascii=False)),
    )
    con.commit()


def fetch_mcp_events(today_str):
    """Try fetching today's events via Google Calendar MCP."""
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {
            "name": "gcal_list_events",
            "arguments": {"time_min": f"{today_str}T00:00:00Z", "time_max": f"{today_str}T23:59:59Z"},
        },
    }).encode()
    req = urllib.request.Request(MCP_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            result = data.get("result", {})
            content = result.get("content", [])
            if content and isinstance(content[0], dict):
                text = content[0].get("text", "[]")
                return json.loads(text) if text.startswith("[") else []
            return content if isinstance(content, list) else []
    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError):
        return None


def fetch_local_events(today_str):
    """Fallback: read events from a local calendar.json file."""
    if not os.path.isfile(LOCAL_CAL):
        return []
    try:
        with open(LOCAL_CAL, "r", encoding="utf-8") as f:
            all_events = json.load(f)
        return [e for e in all_events if e.get("date", "").startswith(today_str)]
    except (json.JSONDecodeError, OSError):
        return []


def find_next_meeting(events):
    now = datetime.now().strftime("%H:%M")
    upcoming = []
    for e in events:
        start = e.get("start", e.get("time", ""))
        if isinstance(start, dict):
            start = start.get("dateTime", start.get("date", ""))
        t = start[11:16] if len(start) > 11 else start
        if t >= now:
            upcoming.append({"title": e.get("summary", e.get("title", "?")), "time": t})
    upcoming.sort(key=lambda x: x["time"])
    return upcoming[0] if upcoming else None


def generate_briefing(events, next_mtg, today_str):
    n = len(events)
    lines = [f"Briefing du {today_str} — {n} evenement(s) aujourd'hui."]
    if next_mtg:
        lines.append(f"Prochain RDV: {next_mtg['title']} a {next_mtg['time']}.")
    else:
        lines.append("Aucun RDV a venir aujourd'hui.")
    for e in events[:5]:
        title = e.get("summary", e.get("title", "?"))
        start = e.get("start", e.get("time", ""))
        if isinstance(start, dict):
            start = start.get("dateTime", start.get("date", ""))
        lines.append(f"  - {title} ({start})")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Calendar sync & briefing")
    parser.add_argument("--once", action="store_true", help="Fetch today's events, generate briefing")
    parser.add_argument("--briefing", action="store_true", help="Morning briefing with upcoming meetings")
    args = parser.parse_args()
    if not args.once and not args.briefing:
        args.once = True

    today_str = date.today().isoformat()
    events = fetch_mcp_events(today_str)
    source = "mcp"
    if events is None:
        events = fetch_local_events(today_str)
        source = "local"

    next_mtg = find_next_meeting(events)
    briefing = generate_briefing(events, next_mtg, today_str)

    result = {
        "date": today_str,
        "events_count": len(events),
        "next_meeting": next_mtg,
        "briefing_text": briefing,
        "source": source,
    }

    con = init_db()
    log_memory(con, "calendar", result)
    con.close()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
