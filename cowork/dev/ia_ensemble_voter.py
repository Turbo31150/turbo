#!/usr/bin/env python3
"""ia_ensemble_voter.py — Vote ensemble multi-modeles.

Interroge N modeles, vote pondere, meilleure reponse.

Usage:
    python dev/ia_ensemble_voter.py --once
    python dev/ia_ensemble_voter.py --vote "QUESTION"
    python dev/ia_ensemble_voter.py --weights
    python dev/ia_ensemble_voter.py --history
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "ensemble_voter.db"

# MAO weights
AGENTS = [
    {"name": "M1", "weight": 1.8, "cmd": 'curl -s http://127.0.0.1:1234/api/v1/chat -H "Content-Type: application/json" -d \'{"model":"qwen3-8b","input":"/nothink/nPROMPT","temperature":0.2,"max_output_tokens":512,"stream":false,"store":false}\''},
    {"name": "OL1", "weight": 1.3, "cmd": "curl -s http://127.0.0.1:11434/api/chat -d '{\"model\":\"qwen3:1.7b\",\"messages\":[{\"role\":\"user\",\"content\":\"PROMPT\"}],\"stream\":false}'"},
    {"name": "M2", "weight": 1.5, "cmd": "curl -s http://192.168.1.26:1234/api/v1/chat -H \"Content-Type: application/json\" -d '{\"model\":\"deepseek-r1-0528-qwen3-8b\",\"input\":\"PROMPT\",\"max_output_tokens\":2048,\"stream\":false,\"store\":false}' --max-time 60"},
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, question TEXT, agent TEXT,
        response_preview TEXT, score REAL, weight REAL,
        latency_s REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, question TEXT, winner TEXT,
        confidence REAL, agents_responded INTEGER)""")
    db.commit()
    return db


def query_agent(agent, question, timeout=60):
    """Query a single agent."""
    cmd = agent["cmd"].replace("PROMPT", question.replace("'", "/'").replace('"', '/"'))
    try:
        start = time.time()
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        latency = time.time() - start
        data = json.loads(result.stdout)

        # Extract response based on API type
        text = ""
        if "message" in data:
            text = data["message"].get("content", "")
        elif "output" in data:
            for item in reversed(data.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            text = c.get("text", "")
                            break
                    if text:
                        break

        return {"text": text, "latency": latency, "ok": bool(text)}
    except Exception:
        return {"text": "", "latency": 0, "ok": False}


def score_response(text, question):
    """Score a response quality (0-1)."""
    if not text:
        return 0.0
    score = 0.0
    if len(text) > 20:
        score += 0.3
    if len(text) > 100:
        score += 0.2
    # Keyword overlap
    q_words = set(question.lower().split())
    r_words = set(text.lower().split())
    overlap = len(q_words & r_words) / max(len(q_words), 1)
    score += min(overlap * 0.3, 0.3)
    if not any(err in text.lower() for err in ["error", "sorry", "cannot"]):
        score += 0.2
    return min(round(score, 3), 1.0)


def do_vote(question):
    """Run ensemble vote."""
    db = init_db()
    responses = []

    for agent in AGENTS:
        result = query_agent(agent, question)
        quality = score_response(result["text"], question)
        weighted = quality * agent["weight"]

        responses.append({
            "agent": agent["name"],
            "weight": agent["weight"],
            "quality": quality,
            "weighted_score": round(weighted, 3),
            "latency_s": round(result["latency"], 2),
            "preview": result["text"][:150] if result["text"] else "(empty)",
            "ok": result["ok"],
        })

        db.execute(
            "INSERT INTO votes (ts, question, agent, response_preview, score, weight, latency_s) VALUES (?,?,?,?,?,?,?)",
            (time.time(), question[:200], agent["name"],
             result["text"][:200], quality, agent["weight"], result["latency"])
        )

    # Determine winner
    valid = [r for r in responses if r["ok"]]
    if valid:
        winner = max(valid, key=lambda r: r["weighted_score"])
    else:
        winner = {"agent": "none", "weighted_score": 0}

    total_weight = sum(r["weighted_score"] for r in valid)
    max_possible = sum(a["weight"] for a in AGENTS)
    confidence = round(total_weight / max(max_possible, 1), 3)

    db.execute(
        "INSERT INTO results (ts, question, winner, confidence, agents_responded) VALUES (?,?,?,?,?)",
        (time.time(), question[:200], winner["agent"], confidence, len(valid))
    )
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "question": question[:100],
        "winner": winner["agent"],
        "confidence": confidence,
        "agents_responded": len(valid),
        "responses": responses,
    }


def main():
    parser = argparse.ArgumentParser(description="IA Ensemble Voter")
    parser.add_argument("--once", action="store_true", help="Quick test vote")
    parser.add_argument("--vote", metavar="QUESTION", help="Vote on question")
    parser.add_argument("--weights", action="store_true", help="Show weights")
    parser.add_argument("--history", action="store_true", help="Vote history")
    args = parser.parse_args()

    if args.weights:
        print(json.dumps([{"agent": a["name"], "weight": a["weight"]} for a in AGENTS], indent=2))
    elif args.history:
        db = init_db()
        rows = db.execute("SELECT ts, question, winner, confidence FROM results ORDER BY ts DESC LIMIT 10").fetchall()
        db.close()
        print(json.dumps([{
            "ts": datetime.fromtimestamp(r[0]).isoformat(),
            "q": r[1][:60], "winner": r[2], "confidence": r[3],
        } for r in rows], indent=2))
    elif args.vote:
        result = do_vote(args.vote)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = do_vote("Quelle est la meilleure strategie pour optimiser un cluster GPU local?")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
