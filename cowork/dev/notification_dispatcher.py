#!/usr/bin/env python3
"""notification_dispatcher.py — Central notification hub.

Aggregates notifications from GitHub, Telegram, Email (IMAP), triages by
urgency, dispatches responses via M1, and logs to etoile.db.

Usage:
  python dev/notification_dispatcher.py --once
  python dev/notification_dispatcher.py --listen
"""

import argparse, imaplib, json, os, sqlite3, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "etoile.db"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = 2010747443
M1_URL = "http://127.0.0.1:1234/api/v1/chat"
IMAP_HOST = os.environ.get("IMAP_HOST", "")
IMAP_USER = os.environ.get("IMAP_USER", "")
IMAP_PASS = os.environ.get("IMAP_PASS", "")

def _post(url, payload, headers=None, timeout=15):
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, json.dumps(payload).encode(), hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None

def _get(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None

def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS memories "
                 "(id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL, "
                 "key TEXT NOT NULL, value TEXT NOT NULL, source TEXT DEFAULT 'jarvis', "
                 "confidence REAL DEFAULT 1.0, created_at TEXT DEFAULT (datetime('now')), "
                 "updated_at TEXT DEFAULT (datetime('now')), UNIQUE(category, key))")
    return conn

def _log(key, value):
    conn = _db()
    conn.execute("INSERT OR REPLACE INTO memories (category, key, value) VALUES (?, ?, ?)",
                 ("notifications", key, json.dumps(value)))
    conn.commit(); conn.close()

def _triage(notif):
    t = notif.get("type", ""); text = notif.get("text", "").lower()
    if t in ("direct_message", "mention", "issue_assigned", "personal_message"):
        return "urgent"
    if any(k in text for k in ["@", "assigned", "urgent", "review requested"]):
        return "urgent"
    if t in ("like", "follow", "star", "reaction", "fork"):
        return "normal"
    return "low"

def _ask_m1(prompt):
    resp = _post(M1_URL, {"model": "qwen3-8b", "input": f"/nothink\n{prompt}",
                          "temperature": 0.2, "max_output_tokens": 512,
                          "stream": False, "store": False}, timeout=30)
    if not resp:
        return ""
    for block in reversed(resp.get("output", [])):
        if block.get("type") == "message":
            for c in block.get("content", []):
                if c.get("type") == "output_text":
                    return c.get("text", "")
    return ""

def fetch_github():
    notifs = []
    data = _get("https://api.github.com/notifications?per_page=20")
    if not data:
        return notifs
    for n in data:
        reason = n.get("reason", "")
        ntype = "issue_assigned" if reason == "assign" else (
            "mention" if reason == "mention" else reason)
        notifs.append({"platform": "github", "type": ntype,
                       "text": n.get("subject", {}).get("title", ""),
                       "url": n.get("subject", {}).get("url", ""), "id": n.get("id")})
    return notifs

def fetch_telegram():
    notifs = []
    if not TELEGRAM_TOKEN:
        return notifs
    data = _get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?limit=20")
    if not data or not data.get("ok"):
        return notifs
    for u in data.get("result", []):
        msg = u.get("message") or u.get("channel_post") or {}
        text = msg.get("text", "")
        chat = msg.get("chat", {})
        ntype = "direct_message" if chat.get("type") == "private" else "group_message"
        notifs.append({"platform": "telegram", "type": ntype, "text": text,
                       "chat_id": chat.get("id"), "update_id": u.get("update_id")})
    return notifs

def fetch_email():
    notifs = []
    if not all([IMAP_HOST, IMAP_USER, IMAP_PASS]):
        return notifs
    try:
        m = imaplib.IMAP4_SSL(IMAP_HOST)
        m.login(IMAP_USER, IMAP_PASS)
        m.select("INBOX")
        _, ids = m.search(None, "UNSEEN")
        for eid in (ids[0].split() or [])[:10]:
            _, data = m.fetch(eid, "(BODY[HEADER.FIELDS (SUBJECT FROM)])")
            raw = data[0][1].decode(errors="replace") if data[0] else ""
            notifs.append({"platform": "email", "type": "personal_message",
                           "text": raw.strip(), "id": eid.decode()})
        m.logout()
    except Exception:
        pass
    return notifs

def dispatch_response(notif, text):
    if notif["platform"] == "telegram" and TELEGRAM_TOKEN:
        cid = notif.get("chat_id", TELEGRAM_CHAT)
        _get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?"
             f"chat_id={cid}&text={urllib.request.quote(text[:4000])}")
        return True
    return False

def run_once():
    results = {"total": 0, "urgent": 0, "normal": 0, "low": 0, "responses_sent": 0}
    all_notifs = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fn): name for fn, name in
                [(fetch_github, "github"), (fetch_telegram, "telegram"),
                 (fetch_email, "email")]}
        for f in as_completed(futs):
            all_notifs.extend(f.result())
    for n in all_notifs:
        level = _triage(n)
        results[level] += 1
        results["total"] += 1
        if level == "urgent":
            reply = _ask_m1(f"Reply briefly to this notification: {n['text'][:500]}")
            if reply and dispatch_response(n, reply):
                results["responses_sent"] += 1
    ts = datetime.now().isoformat(timespec="seconds")
    _log(f"run_{ts}", results)
    return results

def main():
    ap = argparse.ArgumentParser(description="Central notification hub")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--once", action="store_true", help="Single fetch-triage-dispatch cycle")
    g.add_argument("--listen", action="store_true", help="Continuous mode (30s interval)")
    args = ap.parse_args()
    if args.once:
        print(json.dumps(run_once(), indent=2))
    elif args.listen:
        while True:
            r = run_once()
            print(json.dumps({"ts": datetime.now().isoformat(), **r}))
            time.sleep(30)

if __name__ == "__main__":
    main()
