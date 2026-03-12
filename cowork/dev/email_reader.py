#!/usr/bin/env python3
"""JARVIS Email Reader — Lecture emails via IMAP (Gmail/Outlook)."""
import json, sys, os, imaplib, email, sqlite3
from email.header import decode_header
from datetime import datetime
from _paths import TELEGRAM_TOKEN, TELEGRAM_CHAT

DB_PATH = "C:/Users/franc/.openclaw/workspace/dev/emails.db"
CONFIG_PATH = "C:/Users/franc/.openclaw/workspace/dev/email_config.json"

DEFAULT_CONFIG = {
    "imap_host": "imap.gmail.com",
    "imap_port": 993,
    "email": "",
    "password": "",
    "folder": "INBOX",
    "max_emails": 10,
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT,
        uid TEXT UNIQUE, sender TEXT, subject TEXT, date TEXT,
        body_preview TEXT, is_read INTEGER DEFAULT 0
    )""")
    conn.commit()
    return conn

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    with open(CONFIG_PATH, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    return DEFAULT_CONFIG

def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

def decode_mime_header(header):
    if not header:
        return ""
    decoded = decode_header(header)
    parts = []
    for data, charset in decoded:
        if isinstance(data, bytes):
            parts.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(str(data))
    return " ".join(parts)

def get_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
                    break
                except:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
        except:
            body = str(msg.get_payload())
    return body[:500].strip()

def fetch_emails(config, limit=None):
    if not config.get("email") or not config.get("password"):
        print("Email non configure. Editez: " + CONFIG_PATH)
        print("  email: votre_adresse@gmail.com")
        print("  password: votre_mot_de_passe_app (pas le mot de passe normal)")
        print("  Pour Gmail: Creer un 'App Password' dans Google Account > Security")
        return []

    limit = limit or config.get("max_emails", 10)
    try:
        mail = imaplib.IMAP4_SSL(config["imap_host"], config.get("imap_port", 993))
        mail.login(config["email"], config["password"])
        mail.select(config.get("folder", "INBOX"))

        status, data = mail.search(None, "ALL")
        if status != "OK":
            print("Erreur recherche emails")
            return []

        email_ids = data[0].split()
        recent_ids = email_ids[-limit:][::-1]
        emails = []

        for eid in recent_ids:
            status, msg_data = mail.fetch(eid, "(RFC822)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            sender = decode_mime_header(msg.get("From", ""))
            subject = decode_mime_header(msg.get("Subject", ""))
            date = msg.get("Date", "")
            body = get_body(msg)
            uid = eid.decode()

            emails.append({
                "uid": uid,
                "sender": sender[:100],
                "subject": subject[:200],
                "date": date[:50],
                "body_preview": body[:300],
            })

        mail.logout()
        return emails
    except imaplib.IMAP4.error as e:
        print(f"Erreur IMAP: {e}")
        return []
    except Exception as e:
        print(f"Erreur connexion: {e}")
        return []

def format_email_telegram(emails):
    if not emails:
        return "Aucun email ou config manquante."
    lines = [f"📧 *{len(emails)} derniers emails*\n"]
    for i, e in enumerate(emails, 1):
        sender = e["sender"].split("<")[0].strip()[:30]
        subject = e["subject"][:60] or "(sans objet)"
        lines.append(f"*{i}.* {subject}")
        lines.append(f"   De: {sender}")
        if e.get("body_preview"):
            preview = e["body_preview"][:80].replace("\n", " ")
            lines.append(f"   > {preview}...")
        lines.append("")
    return "\n".join(lines)

def send_telegram(msg):
    import urllib.request
    token = "{TELEGRAM_TOKEN}"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": "2010747443", "text": msg[:4000], "parse_mode": "Markdown"}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}), timeout=10)
    except:
        # Fallback sans Markdown si erreur de parsing
        data = json.dumps({"chat_id": "2010747443", "text": msg[:4000]}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}), timeout=10)
        except: pass

def store_emails(conn, emails):
    c = conn.cursor()
    stored = 0
    for e in emails:
        try:
            c.execute("INSERT OR IGNORE INTO emails (ts, uid, sender, subject, date, body_preview) VALUES (?,?,?,?,?,?)",
                      (datetime.now().isoformat(), e["uid"], e["sender"], e["subject"], e["date"], e["body_preview"]))
            if c.rowcount > 0:
                stored += 1
        except: pass
    conn.commit()
    return stored

if __name__ == "__main__":
    conn = init_db()
    config = load_config()

    if "--setup" in sys.argv:
        print(f"[EMAIL CONFIG] {CONFIG_PATH}")
        print(f"  Host: {config['imap_host']}")
        print(f"  Email: {config.get('email', 'NON CONFIGURE')}")
        print(f"  Password: {'***' if config.get('password') else 'NON CONFIGURE'}")
        print(f"\nPour configurer, editez {CONFIG_PATH}")
        print("Gmail: utilisez un 'App Password' (Google Account > Security > 2FA > App Passwords)")

    elif "--read" in sys.argv or "--once" in sys.argv:
        limit = 5
        if "--count" in sys.argv:
            idx = sys.argv.index("--count")
            limit = int(sys.argv[idx + 1]) if len(sys.argv) > idx + 1 else 5
        emails = fetch_emails(config, limit=limit)
        if emails:
            store_emails(conn, emails)
            for i, e in enumerate(emails, 1):
                sender = e["sender"].split("<")[0].strip()[:40]
                print(f"\n--- Email {i} ---")
                print(f"  De: {sender}")
                print(f"  Objet: {e['subject'][:80]}")
                print(f"  Date: {e['date'][:30]}")
                if e["body_preview"]:
                    print(f"  Apercu: {e['body_preview'][:150]}...")
        if "--notify" in sys.argv and emails:
            msg = format_email_telegram(emails)
            send_telegram(msg)

    elif "--telegram" in sys.argv:
        emails = fetch_emails(config, limit=5)
        if emails:
            store_emails(conn, emails)
            msg = format_email_telegram(emails)
            send_telegram(msg)
            print(f"Envoye {len(emails)} emails sur Telegram")
        else:
            send_telegram("Aucun email ou configuration manquante.")

    elif "--history" in sys.argv:
        c = conn.cursor()
        c.execute("SELECT ts, sender, subject FROM emails ORDER BY id DESC LIMIT 20")
        rows = c.fetchall()
        print(f"[EMAIL HISTORY] {len(rows)} cached:")
        for r in rows:
            print(f"  [{r[0][:19]}] {r[1][:30]} — {r[2][:60]}")

    else:
        print("Usage: email_reader.py --setup | --read [--count N] [--notify] | --telegram | --history")
    conn.close()