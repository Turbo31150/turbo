#!/usr/bin/env python3
"""Email triage orchestrator — stdlib only, JSON output."""
import argparse, email, imaplib, json, os, sqlite3, sys
from datetime import datetime, timezone
from email.header import decode_header

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "etoile.db")
URGENT_KW = ["urgent", "asap", "critical", "emergency", "important", "action required", "deadline"]
SPAM_KW = ["unsubscribe", "casino", "lottery", "viagra", "winner", "free money", "click here"]
NEWSLETTER_KW = ["newsletter", "digest", "weekly update", "monthly report", "bulletin"]
DRAFT_TPL = "Bonjour,\n\nMerci pour votre message. Je reviens vers vous rapidement concernant: {subject}\n\nCordialement"

def _decode_hdr(msg, key):
    raw = msg.get(key, "")
    parts = decode_header(raw)
    return " ".join(f.decode(c or "utf-8", errors="replace") if isinstance(f, bytes) else f for f, c in parts)

def categorize(subject):
    low = subject.lower()
    for kws, cat in [(SPAM_KW, "spam"), (NEWSLETTER_KW, "newsletter"), (URGENT_KW, "urgent")]:
        if any(k in low for k in kws):
            return cat
    return "normal"

def connect_imap():
    server, user, pwd = (os.environ.get(v, "") for v in ("EMAIL_IMAP_SERVER", "EMAIL_USER", "EMAIL_PASSWORD"))
    if not all([server, user, pwd]):
        return None, "Missing env: EMAIL_IMAP_SERVER, EMAIL_USER, EMAIL_PASSWORD"
    try:
        conn = imaplib.IMAP4_SSL(server)
        conn.login(user, pwd)
        return conn, None
    except Exception as e:
        return None, str(e)

def fetch_inbox(conn, limit=50):
    conn.select("INBOX")
    _, data = conn.search(None, "UNSEEN")
    ids = data[0].split() if data[0] else []
    mails = []
    for uid in ids[:limit]:
        _, raw = conn.fetch(uid, "(RFC822)")
        if not raw or not raw[0]:
            continue
        msg = email.message_from_bytes(raw[0][1])
        subj = _decode_hdr(msg, "Subject")
        mails.append({"uid": uid.decode(), "from": _decode_hdr(msg, "From"),
                       "subject": subj, "date": msg.get("Date", ""), "category": categorize(subj)})
    return mails

def draft_responses(mails):
    return [{"uid": m["uid"], "to": m["from"], "subject": f"Re: {m['subject']}",
             "body": DRAFT_TPL.format(subject=m["subject"])} for m in mails if m["category"] == "urgent"]

def log_to_db(mails):
    try:
        db = sqlite3.connect(DB_PATH)
        db.execute("CREATE TABLE IF NOT EXISTS memories "
                   "(id INTEGER PRIMARY KEY, category TEXT, key TEXT, value TEXT, ts TEXT)")
        cats = {c: sum(1 for m in mails if m["category"] == c) for c in ("urgent", "normal", "newsletter", "spam")}
        db.execute("INSERT INTO memories (category, key, value, ts) VALUES (?, ?, ?, ?)",
                   ("email_triage", "triage_run", json.dumps({"count": len(mails), "categories": cats}),
                    datetime.now(timezone.utc).isoformat()))
        db.commit()
        db.close()
    except Exception:
        pass

def _count(mails):
    return {c: sum(1 for m in mails if m["category"] == c) for c in ("urgent", "normal", "newsletter", "spam")}

def run_once():
    conn, err = connect_imap()
    if err:
        return {"error": err}
    mails = fetch_inbox(conn)
    drafts = draft_responses(mails)
    log_to_db(mails)
    conn.logout()
    c = _count(mails)
    return {"fetched": len(mails), **c, "drafted": len(drafts), "drafts": drafts}

def run_fetch():
    conn, err = connect_imap()
    if err:
        return {"error": err}
    mails = fetch_inbox(conn)
    conn.logout()
    return {"fetched": len(mails), "emails": mails}

def run_send():
    return {"status": "not_implemented", "note": "SMTP send requires EMAIL_SMTP_SERVER env vars"}

def main():
    p = argparse.ArgumentParser(description="Email triage orchestrator")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--once", action="store_true", help="Fetch, triage, draft responses")
    g.add_argument("--fetch", action="store_true", help="Fetch inbox summary only")
    g.add_argument("--send", action="store_true", help="Send drafted responses")
    a = p.parse_args()
    result = run_once() if a.once else run_fetch() if a.fetch else run_send()
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
