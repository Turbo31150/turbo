#!/usr/bin/env python3
"""win_gesture_detector.py — Mouse gesture detector with pattern recognition.
COWORK #221 — Batch 101: Windows Advanced Control

Usage:
    python dev/win_gesture_detector.py --calibrate
    python dev/win_gesture_detector.py --watch
    python dev/win_gesture_detector.py --actions
    python dev/win_gesture_detector.py --stats
    python dev/win_gesture_detector.py --once
"""
import argparse, json, sqlite3, time, subprocess, os, ctypes, math
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "gesture_detector.db"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS gestures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        pattern TEXT NOT NULL,
        direction TEXT,
        speed REAL,
        distance REAL,
        duration_ms INTEGER,
        points_count INTEGER,
        action_triggered TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS gesture_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pattern TEXT UNIQUE NOT NULL,
        action TEXT NOT NULL,
        description TEXT,
        enabled INTEGER DEFAULT 1
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS calibration (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        screen_width INTEGER,
        screen_height INTEGER,
        sensitivity REAL DEFAULT 1.0,
        min_distance INTEGER DEFAULT 50,
        sample_rate_ms INTEGER DEFAULT 50
    )""")
    # Default actions
    count = db.execute("SELECT COUNT(*) FROM gesture_actions").fetchone()[0]
    if count == 0:
        defaults = [
            ("swipe_right", "next_tab", "Switch to next tab"),
            ("swipe_left", "prev_tab", "Switch to previous tab"),
            ("swipe_up", "scroll_top", "Scroll to top"),
            ("swipe_down", "scroll_bottom", "Scroll to bottom"),
            ("circle_cw", "refresh", "Refresh page"),
            ("circle_ccw", "undo", "Undo last action"),
            ("zigzag", "close_tab", "Close current tab"),
            ("shake", "cancel", "Cancel current operation"),
        ]
        for pat, act, desc in defaults:
            db.execute("INSERT INTO gesture_actions (pattern, action, description) VALUES (?,?,?)", (pat, act, desc))
    db.commit()
    return db

def get_cursor_pos():
    """Get cursor position via ctypes."""
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)

def calc_distance(p1, p2):
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

def calc_direction(p1, p2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    angle = math.degrees(math.atan2(-dy, dx))  # -dy because screen Y is inverted
    if angle < 0:
        angle += 360
    if 315 <= angle or angle < 45:
        return "right"
    elif 45 <= angle < 135:
        return "up"
    elif 135 <= angle < 225:
        return "left"
    else:
        return "down"

def detect_pattern(points):
    """Detect gesture pattern from a list of (x, y) points."""
    if len(points) < 3:
        return "unknown", "none", 0.0, 0.0

    total_dist = sum(calc_distance(points[i], points[i+1]) for i in range(len(points)-1))
    straight_dist = calc_distance(points[0], points[-1])
    primary_dir = calc_direction(points[0], points[-1])

    # Direction changes
    directions = []
    for i in range(len(points)-1):
        d = calc_direction(points[i], points[i+1])
        if not directions or directions[-1] != d:
            directions.append(d)

    direction_changes = len(directions) - 1

    # Classify pattern
    if direction_changes <= 1 and total_dist > 30:
        if straight_dist / max(total_dist, 1) > 0.7:
            pattern = f"swipe_{primary_dir}"
        else:
            pattern = f"curve_{primary_dir}"
    elif direction_changes >= 6:
        pattern = "shake"
    elif direction_changes >= 3:
        # Check for circle
        if straight_dist < total_dist * 0.3:
            # Determine CW vs CCW using cross product sum
            cross_sum = 0
            for i in range(len(points) - 2):
                dx1 = points[i+1][0] - points[i][0]
                dy1 = points[i+1][1] - points[i][1]
                dx2 = points[i+2][0] - points[i+1][0]
                dy2 = points[i+2][1] - points[i+1][1]
                cross_sum += dx1 * dy2 - dy1 * dx2
            pattern = "circle_cw" if cross_sum > 0 else "circle_ccw"
        else:
            pattern = "zigzag"
    else:
        pattern = f"move_{primary_dir}"

    return pattern, primary_dir, total_dist, straight_dist

def do_calibrate():
    """Calibrate by sampling cursor for a few seconds."""
    db = init_db()
    user32 = ctypes.windll.user32
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)

    # Sample cursor positions
    samples = []
    print("Calibrating... move mouse in a circle for 3 seconds", flush=True)
    start = time.time()
    while time.time() - start < 3.0:
        pos = get_cursor_pos()
        samples.append(pos)
        time.sleep(0.05)

    # Calculate speed statistics
    speeds = []
    for i in range(1, len(samples)):
        d = calc_distance(samples[i-1], samples[i])
        speeds.append(d / 0.05)  # pixels per second

    avg_speed = sum(speeds) / len(speeds) if speeds else 0
    max_speed = max(speeds) if speeds else 0
    sensitivity = 1.0 if avg_speed < 500 else 0.5 if avg_speed < 1000 else 0.3

    db.execute("INSERT INTO calibration (ts, screen_width, screen_height, sensitivity, min_distance, sample_rate_ms) VALUES (?,?,?,?,?,?)",
               (datetime.now().isoformat(), sw, sh, sensitivity, 50, 50))
    db.commit()

    result = {
        "action": "calibrate",
        "screen": {"width": sw, "height": sh},
        "samples": len(samples),
        "avg_speed_pps": round(avg_speed, 1),
        "max_speed_pps": round(max_speed, 1),
        "recommended_sensitivity": sensitivity,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_watch(duration=5):
    """Watch mouse for gestures over a short period."""
    db = init_db()
    points = []
    gesture_start = time.time()

    while time.time() - gesture_start < duration:
        pos = get_cursor_pos()
        points.append(pos)
        time.sleep(0.05)

    if len(points) >= 3:
        pattern, direction, total_dist, straight_dist = detect_pattern(points)
        duration_ms = int((time.time() - gesture_start) * 1000)
        speed = total_dist / (duration_ms / 1000) if duration_ms > 0 else 0

        # Check action
        row = db.execute("SELECT action, description FROM gesture_actions WHERE pattern=? AND enabled=1", (pattern,)).fetchone()
        action_triggered = row[0] if row else None

        db.execute("INSERT INTO gestures (ts, pattern, direction, speed, distance, duration_ms, points_count, action_triggered) VALUES (?,?,?,?,?,?,?,?)",
                   (datetime.now().isoformat(), pattern, direction, speed, total_dist, duration_ms, len(points), action_triggered))
        db.commit()

        result = {
            "action": "watch",
            "pattern": pattern,
            "direction": direction,
            "speed_pps": round(speed, 1),
            "distance_px": round(total_dist, 1),
            "straight_distance_px": round(straight_dist, 1),
            "duration_ms": duration_ms,
            "points": len(points),
            "action_triggered": action_triggered,
            "ts": datetime.now().isoformat()
        }
    else:
        result = {"action": "watch", "pattern": "none", "points": len(points), "note": "Not enough movement"}

    db.close()
    return result

def do_actions():
    db = init_db()
    rows = db.execute("SELECT pattern, action, description, enabled FROM gesture_actions ORDER BY pattern").fetchall()
    actions = [{"pattern": r[0], "action": r[1], "description": r[2], "enabled": bool(r[3])} for r in rows]
    result = {"action": "list_actions", "gesture_actions": actions, "total": len(actions), "ts": datetime.now().isoformat()}
    db.close()
    return result

def do_stats():
    db = init_db()
    total = db.execute("SELECT COUNT(*) FROM gestures").fetchone()[0]
    patterns = db.execute("SELECT pattern, COUNT(*) as cnt FROM gestures GROUP BY pattern ORDER BY cnt DESC").fetchall()
    recent = db.execute("SELECT ts, pattern, direction, speed, distance FROM gestures ORDER BY id DESC LIMIT 10").fetchall()
    avg_speed = db.execute("SELECT AVG(speed) FROM gestures").fetchone()[0] or 0
    result = {
        "action": "stats",
        "total_gestures": total,
        "patterns": {r[0]: r[1] for r in patterns},
        "avg_speed": round(avg_speed, 1),
        "recent": [{"ts": r[0], "pattern": r[1], "direction": r[2], "speed": round(r[3] or 0, 1), "distance": round(r[4] or 0, 1)} for r in recent],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    pos = get_cursor_pos()
    total = db.execute("SELECT COUNT(*) FROM gestures").fetchone()[0]
    actions = db.execute("SELECT COUNT(*) FROM gesture_actions WHERE enabled=1").fetchone()[0]
    cal = db.execute("SELECT ts, sensitivity FROM calibration ORDER BY id DESC LIMIT 1").fetchone()
    result = {
        "status": "ok",
        "cursor_position": {"x": pos[0], "y": pos[1]},
        "total_gestures_recorded": total,
        "active_actions": actions,
        "last_calibration": {"ts": cal[0], "sensitivity": cal[1]} if cal else None,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="Mouse Gesture Detector — COWORK #221")
    parser.add_argument("--calibrate", action="store_true", help="Calibrate gesture detection")
    parser.add_argument("--watch", action="store_true", help="Watch for gestures (5s)")
    parser.add_argument("--actions", action="store_true", help="List configured actions")
    parser.add_argument("--stats", action="store_true", help="Show gesture statistics")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.calibrate:
        print(json.dumps(do_calibrate(), ensure_ascii=False, indent=2))
    elif args.watch:
        print(json.dumps(do_watch(), ensure_ascii=False, indent=2))
    elif args.actions:
        print(json.dumps(do_actions(), ensure_ascii=False, indent=2))
    elif args.stats:
        print(json.dumps(do_stats(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
