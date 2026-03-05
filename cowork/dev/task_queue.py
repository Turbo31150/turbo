#!/usr/bin/env python3
"""JARVIS Task Queue — File d'attente de taches avec priorite et retry."""
import json, sys, os, sqlite3, subprocess, time
from datetime import datetime

DB_PATH = "C:/Users/franc/.openclaw/workspace/dev/tasks.db"
TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT = "2010747443"
MAX_RETRIES = 3

def send_telegram(msg):
    import urllib.request
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=10)
    except: pass

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        command TEXT NOT NULL,
        priority INTEGER DEFAULT 5,
        status TEXT DEFAULT 'pending',
        retries INTEGER DEFAULT 0,
        max_retries INTEGER DEFAULT 3,
        created TEXT NOT NULL,
        started TEXT,
        completed TEXT,
        result TEXT,
        error TEXT
    )""")
    conn.commit()
    return conn

def add_task(conn, name, command, priority=5, max_retries=MAX_RETRIES):
    c = conn.cursor()
    c.execute("INSERT INTO tasks (name, command, priority, max_retries, created) VALUES (?, ?, ?, ?, ?)",
              (name, command, priority, max_retries, datetime.now().isoformat()))
    conn.commit()
    tid = c.lastrowid
    print(f"Task #{tid} added: {name} (priority={priority})")
    return tid

def get_next_task(conn):
    c = conn.cursor()
    c.execute("""SELECT id, name, command, retries, max_retries FROM tasks
                 WHERE status IN ('pending', 'retry')
                 ORDER BY priority DESC, created ASC LIMIT 1""")
    return c.fetchone()

def execute_task(conn, task_row):
    tid, name, command, retries, max_retries = task_row
    c = conn.cursor()
    c.execute("UPDATE tasks SET status='running', started=? WHERE id=?",
              (datetime.now().isoformat(), tid))
    conn.commit()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Executing #{tid}: {name}")
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            c.execute("UPDATE tasks SET status='done', completed=?, result=? WHERE id=?",
                      (datetime.now().isoformat(), result.stdout[:2000], tid))
            conn.commit()
            print(f"  OK: {result.stdout[:100]}")
            return True
        else:
            raise Exception(result.stderr[:500] or f"Exit code {result.returncode}")
    except Exception as e:
        error = str(e)[:500]
        retries += 1
        if retries < max_retries:
            c.execute("UPDATE tasks SET status='retry', retries=?, error=? WHERE id=?",
                      (retries, error, tid))
            print(f"  FAIL (retry {retries}/{max_retries}): {error[:80]}")
        else:
            c.execute("UPDATE tasks SET status='failed', retries=?, error=?, completed=? WHERE id=?",
                      (retries, error, datetime.now().isoformat(), tid))
            send_telegram(f"[JARVIS TASK FAIL] #{tid} {name}: {error[:100]}")
            print(f"  FAILED: {error[:80]}")
        conn.commit()
        return False

def list_tasks(conn, status=None):
    c = conn.cursor()
    if status:
        c.execute("SELECT id, name, status, priority, retries, created FROM tasks WHERE status=? ORDER BY priority DESC", (status,))
    else:
        c.execute("SELECT id, name, status, priority, retries, created FROM tasks ORDER BY priority DESC, id DESC LIMIT 20")
    rows = c.fetchall()
    print(f"[TASK QUEUE] {len(rows)} tasks" + (f" ({status})" if status else ""))
    for r in rows:
        print(f"  #{r[0]} [{r[2]}] P{r[3]} retry={r[4]} — {r[1]}")

def process_queue(conn, max_tasks=10):
    processed = 0
    while processed < max_tasks:
        task = get_next_task(conn)
        if not task:
            break
        execute_task(conn, task)
        processed += 1
        time.sleep(1)
    return processed

if __name__ == "__main__":
    conn = init_db()

    if "--add" in sys.argv:
        idx = sys.argv.index("--add")
        name = sys.argv[idx+1] if len(sys.argv) > idx+1 else "task"
        cmd = sys.argv[idx+2] if len(sys.argv) > idx+2 else "echo OK"
        priority = int(sys.argv[sys.argv.index("--priority")+1]) if "--priority" in sys.argv else 5
        add_task(conn, name, cmd, priority)

    elif "--list" in sys.argv:
        status = sys.argv[sys.argv.index("--list")+1] if len(sys.argv) > sys.argv.index("--list")+1 else None
        list_tasks(conn, status)

    elif "--run" in sys.argv:
        n = process_queue(conn)
        print(f"Processed {n} tasks")

    elif "--loop" in sys.argv:
        interval = 30
        print(f"Queue worker running every {interval}s... Ctrl+C to stop")
        while True:
            n = process_queue(conn)
            if n: print(f"[{datetime.now().strftime('%H:%M:%S')}] Processed {n} tasks")
            time.sleep(interval)

    elif "--clear" in sys.argv:
        status = sys.argv[sys.argv.index("--clear")+1] if len(sys.argv) > sys.argv.index("--clear")+1 else "done"
        c = conn.cursor()
        c.execute("DELETE FROM tasks WHERE status=?", (status,))
        conn.commit()
        print(f"Cleared {c.rowcount} '{status}' tasks")

    else:
        print("Usage: task_queue.py --add <name> <command> [--priority N]")
        print("       --list [status] | --run | --loop | --clear [status]")

    conn.close()
