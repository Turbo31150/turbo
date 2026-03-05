#!/usr/bin/env python3
"""ia_goal_tracker.py — #202 Hierarchical goal tracking (goal->subgoals->tasks).
Usage:
    python dev/ia_goal_tracker.py --set '{"name":"Ship v11","deadline":"2026-04-01","subgoals":["Refactor core","Add tests"]}'
    python dev/ia_goal_tracker.py --progress
    python dev/ia_goal_tracker.py --complete 5
    python dev/ia_goal_tracker.py --report
    python dev/ia_goal_tracker.py --once
"""
import argparse, json, sqlite3, time, os
from datetime import datetime, timedelta
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "goal_tracker.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER,
        name TEXT NOT NULL,
        description TEXT,
        level TEXT DEFAULT 'goal',
        status TEXT DEFAULT 'active',
        priority INTEGER DEFAULT 5,
        deadline TEXT,
        progress_pct REAL DEFAULT 0.0,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        completed_at TEXT,
        FOREIGN KEY(parent_id) REFERENCES goals(id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS goal_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal_id INTEGER,
        old_status TEXT,
        new_status TEXT,
        old_progress REAL,
        new_progress REAL,
        ts TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(goal_id) REFERENCES goals(id)
    )""")
    db.commit()
    return db


def set_goal(db, spec):
    """Create a goal with optional subgoals and tasks."""
    if isinstance(spec, str):
        spec = json.loads(spec)
    name = spec.get("name", "Unnamed goal")
    desc = spec.get("description", "")
    deadline = spec.get("deadline", "")
    priority = spec.get("priority", 5)
    parent_id = spec.get("parent_id")

    cur = db.execute(
        "INSERT INTO goals (name, description, deadline, priority, parent_id, level) VALUES (?,?,?,?,?,?)",
        (name, desc, deadline, priority, parent_id, "goal" if not parent_id else "subgoal")
    )
    goal_id = cur.lastrowid

    subgoal_ids = []
    for sg in spec.get("subgoals", []):
        if isinstance(sg, str):
            sg = {"name": sg}
        sg_cur = db.execute(
            "INSERT INTO goals (name, description, parent_id, level, deadline, priority) VALUES (?,?,?,?,?,?)",
            (sg.get("name", ""), sg.get("description", ""), goal_id, "subgoal",
             sg.get("deadline", deadline), sg.get("priority", priority))
        )
        sg_id = sg_cur.lastrowid
        subgoal_ids.append(sg_id)

        for task in sg.get("tasks", []):
            if isinstance(task, str):
                task = {"name": task}
            db.execute(
                "INSERT INTO goals (name, description, parent_id, level, priority) VALUES (?,?,?,?,?)",
                (task.get("name", ""), task.get("description", ""), sg_id, "task", task.get("priority", 5))
            )

    for task in spec.get("tasks", []):
        if isinstance(task, str):
            task = {"name": task}
        db.execute(
            "INSERT INTO goals (name, description, parent_id, level, priority) VALUES (?,?,?,?,?)",
            (task.get("name", ""), task.get("description", ""), goal_id, "task", task.get("priority", 5))
        )

    db.commit()
    return {"created": goal_id, "name": name, "subgoals": subgoal_ids, "level": "goal"}


def _calc_progress(db, goal_id):
    """Recursively calculate progress from children."""
    children = db.execute("SELECT id, status, progress_pct FROM goals WHERE parent_id=?", (goal_id,)).fetchall()
    if not children:
        row = db.execute("SELECT status FROM goals WHERE id=?", (goal_id,)).fetchone()
        return 100.0 if row and row[0] == "completed" else 0.0

    total = 0.0
    for cid, cstatus, cprog in children:
        child_prog = _calc_progress(db, cid)
        db.execute("UPDATE goals SET progress_pct=? WHERE id=?", (child_prog, cid))
        total += child_prog

    return round(total / len(children), 1)


def update_progress(db):
    """Recalculate progress for all top-level goals."""
    top_goals = db.execute("SELECT id, name FROM goals WHERE parent_id IS NULL AND level='goal'").fetchall()
    results = []
    for gid, gname in top_goals:
        old = db.execute("SELECT progress_pct FROM goals WHERE id=?", (gid,)).fetchone()[0]
        new_prog = _calc_progress(db, gid)
        db.execute("UPDATE goals SET progress_pct=? WHERE id=?", (new_prog, gid))
        if abs(new_prog - old) > 0.01:
            db.execute(
                "INSERT INTO goal_history (goal_id, old_progress, new_progress) VALUES (?,?,?)",
                (gid, old, new_prog)
            )
        results.append({"id": gid, "name": gname, "progress": new_prog})
    db.commit()
    return {"goals": results, "updated": len(results)}


def complete_item(db, item_id):
    """Mark a goal/subgoal/task as completed."""
    row = db.execute("SELECT name, status, level FROM goals WHERE id=?", (item_id,)).fetchone()
    if not row:
        return {"error": f"Item {item_id} not found"}
    name, old_status, level = row
    db.execute(
        "UPDATE goals SET status='completed', progress_pct=100.0, completed_at=datetime('now','localtime') WHERE id=?",
        (item_id,)
    )
    db.execute(
        "INSERT INTO goal_history (goal_id, old_status, new_status, old_progress, new_progress) VALUES (?,?,?,?,?)",
        (item_id, old_status, "completed", 0, 100)
    )
    db.commit()
    update_progress(db)
    return {"completed": item_id, "name": name, "level": level}


def generate_report(db):
    """Full hierarchical report."""
    top = db.execute(
        "SELECT id, name, status, progress_pct, deadline, priority, created_at FROM goals WHERE parent_id IS NULL AND level='goal' ORDER BY priority DESC, created_at DESC"
    ).fetchall()
    report = []
    for gid, gname, gstatus, gprog, gdeadline, gpri, gcreated in top:
        children = db.execute(
            "SELECT id, name, status, progress_pct, level FROM goals WHERE parent_id=? ORDER BY id",
            (gid,)
        ).fetchall()
        subs = []
        for cid, cname, cstatus, cprog, clevel in children:
            tasks = db.execute(
                "SELECT id, name, status, progress_pct FROM goals WHERE parent_id=? ORDER BY id",
                (cid,)
            ).fetchall()
            subs.append({
                "id": cid, "name": cname, "status": cstatus,
                "progress": cprog, "level": clevel,
                "tasks": [{"id": t[0], "name": t[1], "status": t[2], "progress": t[3]} for t in tasks]
            })

        overdue = False
        if gdeadline and gstatus == "active":
            try:
                dl = datetime.strptime(gdeadline, "%Y-%m-%d")
                overdue = dl < datetime.now()
            except ValueError:
                pass

        report.append({
            "id": gid, "name": gname, "status": gstatus,
            "progress": gprog, "deadline": gdeadline,
            "priority": gpri, "overdue": overdue,
            "children": subs
        })

    total = db.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
    completed = db.execute("SELECT COUNT(*) FROM goals WHERE status='completed'").fetchone()[0]
    return {
        "report": report,
        "summary": {
            "total_items": total,
            "completed": completed,
            "active": total - completed,
            "completion_rate": round(completed / total * 100, 1) if total else 0
        }
    }


def do_status(db):
    """Quick status overview."""
    update_progress(db)
    total = db.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
    by_level = {}
    for lv in ["goal", "subgoal", "task"]:
        by_level[lv] = db.execute("SELECT COUNT(*) FROM goals WHERE level=?", (lv,)).fetchone()[0]
    by_status = {}
    for st in ["active", "completed"]:
        by_status[st] = db.execute("SELECT COUNT(*) FROM goals WHERE status=?", (st,)).fetchone()[0]
    top = db.execute(
        "SELECT id, name, progress_pct, deadline FROM goals WHERE parent_id IS NULL AND level='goal' AND status='active' ORDER BY priority DESC LIMIT 5"
    ).fetchall()
    return {
        "script": "ia_goal_tracker.py",
        "id": 202,
        "db": str(DB_PATH),
        "total": total,
        "by_level": by_level,
        "by_status": by_status,
        "active_goals": [{"id": t[0], "name": t[1], "progress": t[2], "deadline": t[3]} for t in top],
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="IA Goal Tracker — hierarchical goal management")
    parser.add_argument("--set", type=str, metavar="GOAL_JSON", help="Create goal from JSON spec")
    parser.add_argument("--progress", action="store_true", help="Update and show progress")
    parser.add_argument("--complete", type=int, metavar="ID", help="Mark item as completed")
    parser.add_argument("--report", action="store_true", help="Full hierarchical report")
    parser.add_argument("--once", action="store_true", help="Show status and exit")
    args = parser.parse_args()

    db = init_db()

    if args.set:
        result = set_goal(db, args.set)
    elif args.progress:
        result = update_progress(db)
    elif args.complete:
        result = complete_item(db, args.complete)
    elif args.report:
        result = generate_report(db)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
