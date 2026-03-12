#!/usr/bin/env python3
"""ia_agent_spawner.py — #201 Spawns micro-agents with specs (goal, model, timeout).
Usage:
    python dev/ia_agent_spawner.py --spawn '{"goal":"test","model":"qwen3-8b","timeout":60,"script":"dev/health_checker.py --once"}'
    python dev/ia_agent_spawner.py --list
    python dev/ia_agent_spawner.py --kill 3
    python dev/ia_agent_spawner.py --monitor
    python dev/ia_agent_spawner.py --once
"""
import argparse, json, sqlite3, time, subprocess, os, signal, sys
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "agent_spawner.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal TEXT NOT NULL,
        model TEXT DEFAULT 'qwen3-8b',
        script TEXT,
        timeout_sec INTEGER DEFAULT 120,
        pid INTEGER,
        status TEXT DEFAULT 'pending',
        exit_code INTEGER,
        stdout TEXT,
        stderr TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        started_at TEXT,
        finished_at TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS agent_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id INTEGER,
        level TEXT DEFAULT 'info',
        message TEXT,
        ts TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(agent_id) REFERENCES agents(id)
    )""")
    db.commit()
    return db


def spawn_agent(db, spec):
    """Spawn a micro-agent from a JSON spec."""
    if isinstance(spec, str):
        spec = json.loads(spec)
    goal = spec.get("goal", "unnamed")
    model = spec.get("model", "qwen3-8b")
    script = spec.get("script", "")
    timeout = spec.get("timeout", 120)

    cur = db.execute(
        "INSERT INTO agents (goal, model, script, timeout_sec, status) VALUES (?,?,?,?,?)",
        (goal, model, script, timeout, "spawning")
    )
    agent_id = cur.lastrowid
    db.commit()

    if not script:
        db.execute("UPDATE agents SET status='error', stderr='No script specified' WHERE id=?", (agent_id,))
        db.commit()
        return {"id": agent_id, "status": "error", "reason": "no script specified"}

    try:
        cmd = [sys.executable] + script.split()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(DEV.parent),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        db.execute(
            "UPDATE agents SET pid=?, status='running', started_at=datetime('now','localtime') WHERE id=?",
            (proc.pid, agent_id)
        )
        db.execute(
            "INSERT INTO agent_logs (agent_id, level, message) VALUES (?,?,?)",
            (agent_id, "info", f"Spawned PID {proc.pid}: {script}")
        )
        db.commit()

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            exit_code = proc.returncode
            status = "completed" if exit_code == 0 else "failed"
            db.execute(
                "UPDATE agents SET status=?, exit_code=?, stdout=?, stderr=?, finished_at=datetime('now','localtime') WHERE id=?",
                (status, exit_code, stdout.decode(errors='replace')[:10000], stderr.decode(errors='replace')[:5000], agent_id)
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            db.execute(
                "UPDATE agents SET status='timeout', exit_code=-1, stdout=?, stderr=?, finished_at=datetime('now','localtime') WHERE id=?",
                (stdout.decode(errors='replace')[:10000], stderr.decode(errors='replace')[:5000], agent_id)
            )
            db.execute(
                "INSERT INTO agent_logs (agent_id, level, message) VALUES (?,?,?)",
                (agent_id, "warning", f"Timeout after {timeout}s, killed PID {proc.pid}")
            )
        db.commit()
        row = db.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        cols = [d[0] for d in db.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).description]
        return dict(zip(cols, row))

    except Exception as e:
        db.execute(
            "UPDATE agents SET status='error', stderr=? WHERE id=?",
            (str(e), agent_id)
        )
        db.commit()
        return {"id": agent_id, "status": "error", "reason": str(e)}


def list_agents(db, limit=20):
    """List recent agents."""
    rows = db.execute(
        "SELECT id, goal, model, script, status, pid, exit_code, created_at, finished_at FROM agents ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    cols = ["id", "goal", "model", "script", "status", "pid", "exit_code", "created_at", "finished_at"]
    agents = [dict(zip(cols, r)) for r in rows]
    stats = {}
    for st in ["completed", "failed", "timeout", "running", "error", "pending"]:
        cnt = db.execute("SELECT COUNT(*) FROM agents WHERE status=?", (st,)).fetchone()[0]
        if cnt > 0:
            stats[st] = cnt
    return {"agents": agents, "stats": stats, "total": sum(stats.values())}


def kill_agent(db, agent_id):
    """Kill a running agent by ID."""
    row = db.execute("SELECT pid, status FROM agents WHERE id=?", (agent_id,)).fetchone()
    if not row:
        return {"error": f"Agent {agent_id} not found"}
    pid, status = row
    if status != "running":
        return {"error": f"Agent {agent_id} is not running (status={status})"}
    try:
        if os.name == 'nt':
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, signal.SIGKILL)
        db.execute(
            "UPDATE agents SET status='killed', finished_at=datetime('now','localtime') WHERE id=?",
            (agent_id,)
        )
        db.execute(
            "INSERT INTO agent_logs (agent_id, level, message) VALUES (?,?,?)",
            (agent_id, "warning", f"Manually killed PID {pid}")
        )
        db.commit()
        return {"status": "killed", "agent_id": agent_id, "pid": pid}
    except Exception as e:
        return {"error": str(e)}


def monitor_agents(db):
    """Check running agents, update stale ones."""
    running = db.execute("SELECT id, pid, timeout_sec, started_at FROM agents WHERE status='running'").fetchall()
    results = []
    for aid, pid, timeout, started in running:
        alive = False
        try:
            if os.name == 'nt':
                r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
                alive = str(pid) in r.stdout
            else:
                os.kill(pid, 0)
                alive = True
        except (OSError, ProcessLookupError):
            alive = False

        if not alive:
            db.execute(
                "UPDATE agents SET status='disappeared', finished_at=datetime('now','localtime') WHERE id=?",
                (aid,)
            )
            results.append({"agent_id": aid, "pid": pid, "action": "marked_disappeared"})
        else:
            if started:
                try:
                    st = datetime.strptime(started, "%Y-%m-%d %H:%M:%S")
                    elapsed = (datetime.now() - st).total_seconds()
                    if elapsed > timeout:
                        kill_agent(db, aid)
                        results.append({"agent_id": aid, "pid": pid, "action": "killed_timeout", "elapsed": round(elapsed)})
                    else:
                        results.append({"agent_id": aid, "pid": pid, "action": "still_running", "elapsed": round(elapsed)})
                except ValueError:
                    results.append({"agent_id": aid, "pid": pid, "action": "still_running"})
            else:
                results.append({"agent_id": aid, "pid": pid, "action": "still_running"})

    db.commit()
    return {"monitored": len(running), "actions": results}


def do_status(db):
    """Overall spawner status."""
    stats = {}
    for st in ["completed", "failed", "timeout", "running", "error", "killed", "pending", "disappeared"]:
        cnt = db.execute("SELECT COUNT(*) FROM agents WHERE status=?", (st,)).fetchone()[0]
        if cnt > 0:
            stats[st] = cnt
    total = db.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
    recent = db.execute(
        "SELECT id, goal, status, created_at FROM agents ORDER BY id DESC LIMIT 5"
    ).fetchall()
    return {
        "script": "ia_agent_spawner.py",
        "id": 201,
        "db": str(DB_PATH),
        "total_agents": total,
        "stats": stats,
        "recent": [{"id": r[0], "goal": r[1], "status": r[2], "created": r[3]} for r in recent],
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="IA Agent Spawner — spawn/monitor micro-agents")
    parser.add_argument("--spawn", type=str, help="Spawn agent from JSON spec")
    parser.add_argument("--list", action="store_true", help="List recent agents")
    parser.add_argument("--kill", type=int, metavar="ID", help="Kill a running agent")
    parser.add_argument("--monitor", action="store_true", help="Monitor running agents")
    parser.add_argument("--once", action="store_true", help="Show status and exit")
    args = parser.parse_args()

    db = init_db()

    if args.spawn:
        result = spawn_agent(db, args.spawn)
    elif args.list:
        result = list_agents(db)
    elif args.kill:
        result = kill_agent(db, args.kill)
    elif args.monitor:
        result = monitor_agents(db)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
