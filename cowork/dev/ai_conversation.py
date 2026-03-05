#!/usr/bin/env python3
"""JARVIS AI Conversation — Agent conversationnel multi-tours avec M1."""
import json, sys, os, sqlite3, urllib.request, subprocess
from datetime import datetime

DB_PATH = "C:/Users/franc/.openclaw/workspace/dev/conversation.db"
M1_URL = "http://127.0.0.1:1234/api/v1/chat"
M1_MODEL = "qwen3-8b"
SYSTEM_PROMPT = "Tu es JARVIS, assistant IA de Franck. Reponds en francais, de maniere concise et utile. Tu peux executer des commandes systeme si demande."

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT,
        role TEXT, content TEXT, session TEXT DEFAULT 'default'
    )""")
    conn.commit()
    return conn

def get_history(conn, session="default", limit=20):
    c = conn.cursor()
    c.execute("SELECT role, content FROM messages WHERE session=? ORDER BY id DESC LIMIT ?", (session, limit))
    return [{"role": r[0], "content": r[1]} for r in c.fetchall()][::-1]

def save_message(conn, role, content, session="default"):
    c = conn.cursor()
    c.execute("INSERT INTO messages (ts, role, content, session) VALUES (?,?,?,?)",
              (datetime.now().isoformat(), role, content[:5000], session))
    conn.commit()

def query_m1(messages):
    # Build conversation with system prompt
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    payload = json.dumps({
        "model": M1_MODEL,
        "input": "/nothink\n" + json.dumps(full_messages),
        "temperature": 0.3,
        "max_output_tokens": 1024,
        "stream": False,
        "store": False,
    }).encode()
    req = urllib.request.Request(M1_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        output = data.get("output", [])
        for block in reversed(output):
            if block.get("type") == "message":
                for c in block.get("content", []):
                    if c.get("type") == "output_text":
                        return c.get("text", "")
        return str(data)[:500]
    except Exception as e:
        return f"Erreur M1: {e}"

def check_exec_request(response):
    """Detecte si la reponse contient une commande a executer."""
    if "```" in response:
        lines = response.split("```")
        for i in range(1, len(lines), 2):
            code = lines[i].strip()
            if code.startswith(("bash\n", "powershell\n", "python\n")):
                return code.split("\n", 1)[1] if "\n" in code else None
    return None

def interactive_chat(conn):
    print("[JARVIS AI] Mode chat interactif. Tapez 'quit' pour sortir.\n")
    session = f"chat_{datetime.now().strftime('%Y%m%d_%H%M')}"
    while True:
        try:
            user_input = input("Vous > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            break
        save_message(conn, "user", user_input, session)
        history = get_history(conn, session, limit=10)
        response = query_m1(history)
        save_message(conn, "assistant", response, session)
        print(f"\nJARVIS > {response}\n")

def single_ask(conn, question):
    save_message(conn, "user", question)
    history = get_history(conn, limit=5)
    response = query_m1(history)
    save_message(conn, "assistant", response)
    print(f"JARVIS > {response}")

if __name__ == "__main__":
    conn = init_db()
    if "--chat" in sys.argv:
        interactive_chat(conn)
    elif "--ask" in sys.argv:
        idx = sys.argv.index("--ask")
        question = " ".join(sys.argv[idx+1:])
        if question:
            single_ask(conn, question)
        else:
            print("Usage: --ask 'votre question'")
    elif "--history" in sys.argv:
        history = get_history(conn, limit=20)
        print(f"[CONVERSATION] {len(history)} messages:")
        for m in history:
            role = "Vous" if m["role"] == "user" else "JARVIS"
            print(f"  {role}: {m['content'][:100]}")
    elif "--clear" in sys.argv:
        c = conn.cursor()
        c.execute("DELETE FROM messages")
        conn.commit()
        print("History cleared")
    else:
        print("Usage: ai_conversation.py --chat | --ask 'question' | --history | --clear")
    conn.close()
