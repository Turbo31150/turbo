#!/usr/bin/env python3
"""ia_debate_engine.py — AI debate engine with pro/contra and judge.
COWORK #225 — Batch 103: IA Collaborative

Usage:
    python dev/ia_debate_engine.py --debate "Python vs Rust for web backends"
    python dev/ia_debate_engine.py --debate "Microservices vs Monolith" --rounds 3
    python dev/ia_debate_engine.py --judge
    python dev/ia_debate_engine.py --transcript
    python dev/ia_debate_engine.py --once
"""
import argparse, json, sqlite3, time, subprocess, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "debate_engine.db"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS debates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        topic TEXT NOT NULL,
        rounds INTEGER DEFAULT 3,
        pro_model TEXT DEFAULT 'M1',
        contra_model TEXT DEFAULT 'OL1',
        judge_model TEXT DEFAULT 'gpt-oss',
        status TEXT DEFAULT 'pending',
        winner TEXT,
        pro_score REAL,
        contra_score REAL,
        synthesis TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS debate_turns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        debate_id INTEGER NOT NULL,
        round_num INTEGER NOT NULL,
        side TEXT NOT NULL,
        model TEXT NOT NULL,
        argument TEXT NOT NULL,
        score REAL,
        ts TEXT NOT NULL,
        duration_ms INTEGER,
        FOREIGN KEY (debate_id) REFERENCES debates(id)
    )""")
    db.commit()
    return db

def query_m1(prompt):
    """Query M1 via curl."""
    payload = json.dumps({
        "model": "qwen3-8b",
        "input": f"/nothink\\n{prompt}",
        "temperature": 0.4,
        "max_output_tokens": 1024,
        "stream": False,
        "store": False
    })
    try:
        cmd = f'curl -s --max-time 60 http://127.0.0.1:1234/api/v1/chat -H "Content-Type: application/json" -d {json.dumps(payload)}'
        start = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=65, shell=True)
        elapsed = int((time.time() - start) * 1000)
        if r.stdout.strip():
            data = json.loads(r.stdout)
            output = data.get("output", [])
            for item in reversed(output):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return c.get("text", "").strip(), elapsed
        return None, elapsed
    except Exception as e:
        return None, 0

def query_ol1(prompt):
    """Query OL1 via curl."""
    payload = json.dumps({
        "model": "qwen3:1.7b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    })
    try:
        cmd = f'curl -s --max-time 60 http://127.0.0.1:11434/api/chat -d {json.dumps(payload)}'
        start = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=65, shell=True)
        elapsed = int((time.time() - start) * 1000)
        if r.stdout.strip():
            data = json.loads(r.stdout)
            content = data.get("message", {}).get("content", "")
            # Remove thinking tags if present
            if "<think>" in content:
                import re
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            return content.strip(), elapsed
        return None, elapsed
    except Exception as e:
        return None, 0

def query_gptoss(prompt):
    """Query gpt-oss:120b cloud via OL1."""
    payload = json.dumps({
        "model": "gpt-oss:120b-cloud",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False
    })
    try:
        cmd = f'curl -s --max-time 120 http://127.0.0.1:11434/api/chat -d {json.dumps(payload)}'
        start = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=125, shell=True)
        elapsed = int((time.time() - start) * 1000)
        if r.stdout.strip():
            data = json.loads(r.stdout)
            return data.get("message", {}).get("content", "").strip(), elapsed
        return None, elapsed
    except Exception as e:
        return None, 0

def do_debate(topic, rounds=3):
    db = init_db()
    now = datetime.now().isoformat()
    cursor = db.execute("INSERT INTO debates (ts, topic, rounds, status) VALUES (?,?,?,?)",
                        (now, topic, rounds, "running"))
    debate_id = cursor.lastrowid
    db.commit()

    results = {"debate_id": debate_id, "topic": topic, "rounds": [], "status": "running"}

    for round_num in range(1, rounds + 1):
        round_data = {"round": round_num, "pro": None, "contra": None}

        # PRO argument (M1)
        if round_num == 1:
            pro_prompt = f"Tu es POUR dans un debat sur: '{topic}'. Donne 3 arguments solides EN FAVEUR. Sois concis (150 mots max)."
        else:
            pro_prompt = f"Debat sur: '{topic}'. Tu es POUR. Round {round_num}/{rounds}. Renforce tes arguments precedents et reponds aux critiques. 150 mots max."

        pro_text, pro_ms = query_m1(pro_prompt)
        if pro_text:
            db.execute("INSERT INTO debate_turns (debate_id, round_num, side, model, argument, ts, duration_ms) VALUES (?,?,?,?,?,?,?)",
                       (debate_id, round_num, "pro", "M1", pro_text, datetime.now().isoformat(), pro_ms))
            round_data["pro"] = {"model": "M1", "argument": pro_text[:500], "duration_ms": pro_ms}

        # CONTRA argument (OL1)
        if round_num == 1:
            contra_prompt = f"Tu es CONTRE dans un debat sur: '{topic}'. Donne 3 arguments solides CONTRE. Sois concis (150 mots max)."
        else:
            contra_prompt = f"Debat sur: '{topic}'. Tu es CONTRE. Round {round_num}/{rounds}. Renforce tes arguments et reponds au PRO. 150 mots max."

        contra_text, contra_ms = query_ol1(contra_prompt)
        if contra_text:
            db.execute("INSERT INTO debate_turns (debate_id, round_num, side, model, argument, ts, duration_ms) VALUES (?,?,?,?,?,?,?)",
                       (debate_id, round_num, "contra", "OL1", contra_text, datetime.now().isoformat(), contra_ms))
            round_data["contra"] = {"model": "OL1", "argument": contra_text[:500], "duration_ms": contra_ms}

        results["rounds"].append(round_data)
        db.commit()

    # Judge (gpt-oss or M1 fallback)
    all_args = ""
    for rd in results["rounds"]:
        pro_arg = rd.get("pro", {}).get("argument", "N/A")
        contra_arg = rd.get("contra", {}).get("argument", "N/A")
        all_args += f"\nRound {rd['round']}:\nPRO: {pro_arg}\nCONTRA: {contra_arg}\n"

    judge_prompt = f"Tu es juge d'un debat sur: '{topic}'.\n{all_args}\nEvalue chaque cote (score /10). Declare un gagnant et explique. Format: PRO: X/10, CONTRA: Y/10, GAGNANT: [PRO/CONTRA], RAISON: [explication]"

    judge_text, judge_ms = query_m1(judge_prompt)
    results["judge"] = {"model": "M1_judge", "verdict": judge_text[:500] if judge_text else "Unable to judge", "duration_ms": judge_ms}

    db.execute("UPDATE debates SET status='completed', synthesis=? WHERE id=?",
               (judge_text[:1000] if judge_text else "N/A", debate_id))
    db.commit()
    results["status"] = "completed"
    results["ts"] = datetime.now().isoformat()
    db.close()
    return results

def do_judge():
    db = init_db()
    row = db.execute("SELECT id, topic, synthesis, winner, pro_score, contra_score FROM debates ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        db.close()
        return {"error": "No debates found"}
    result = {
        "action": "judge",
        "debate_id": row[0],
        "topic": row[1],
        "synthesis": row[2],
        "winner": row[3],
        "pro_score": row[4],
        "contra_score": row[5],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_transcript():
    db = init_db()
    debate = db.execute("SELECT id, topic, rounds, status, ts FROM debates ORDER BY id DESC LIMIT 1").fetchone()
    if not debate:
        db.close()
        return {"error": "No debates found"}

    turns = db.execute("SELECT round_num, side, model, argument, duration_ms FROM debate_turns WHERE debate_id=? ORDER BY round_num, side",
                       (debate[0],)).fetchall()
    transcript = []
    for t in turns:
        transcript.append({
            "round": t[0], "side": t[1], "model": t[2],
            "argument": t[3][:300], "duration_ms": t[4]
        })
    result = {
        "action": "transcript",
        "debate_id": debate[0],
        "topic": debate[1],
        "total_rounds": debate[2],
        "status": debate[3],
        "started_at": debate[4],
        "transcript": transcript,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    total = db.execute("SELECT COUNT(*) FROM debates").fetchone()[0]
    completed = db.execute("SELECT COUNT(*) FROM debates WHERE status='completed'").fetchone()[0]
    total_turns = db.execute("SELECT COUNT(*) FROM debate_turns").fetchone()[0]
    recent = db.execute("SELECT ts, topic, status FROM debates ORDER BY id DESC LIMIT 5").fetchall()
    result = {
        "status": "ok",
        "total_debates": total,
        "completed": completed,
        "total_turns": total_turns,
        "models": {"pro": "M1 (qwen3-8b)", "contra": "OL1 (qwen3:1.7b)", "judge": "M1"},
        "recent_debates": [{"ts": r[0], "topic": r[1], "status": r[2]} for r in recent],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="IA Debate Engine — COWORK #225")
    parser.add_argument("--debate", type=str, metavar="TOPIC", help="Start a debate on topic")
    parser.add_argument("--rounds", type=int, default=3, help="Number of debate rounds (default: 3)")
    parser.add_argument("--judge", action="store_true", help="Show last debate judgment")
    parser.add_argument("--transcript", action="store_true", help="Show last debate transcript")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.debate:
        print(json.dumps(do_debate(args.debate, args.rounds), ensure_ascii=False, indent=2))
    elif args.judge:
        print(json.dumps(do_judge(), ensure_ascii=False, indent=2))
    elif args.transcript:
        print(json.dumps(do_transcript(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
