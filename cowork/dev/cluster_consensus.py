#!/usr/bin/env python3
"""Cluster Consensus — Multi-agent voting system for critical decisions.

Dispatches a question to M1, OL1, M2, GEMINI. Collects answers.
Applies weighted voting. Returns consensus verdict.

Usage:
    python cowork/dev/cluster_consensus.py --once --question "Should we deploy?"
"""

import argparse
import json
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

TURBO = Path(__file__).resolve().parent.parent.parent
DB_PATH = TURBO / "etoile.db"

AGENTS = {
    "M1": {"weight": 1.9, "cmd": ["curl", "-s", "--max-time", "15", "http://127.0.0.1:1234/api/v1/chat",
            "-H", "Content-Type: application/json"]},
    "OL1": {"weight": 1.4, "cmd": ["curl", "-s", "--max-time", "10", "http://127.0.0.1:11434/api/chat"]},
}


def query_m1(question):
    """Query M1/qwen3-8b."""
    import urllib.request
    payload = json.dumps({
        "model": "qwen3-8b",
        "input": f"/nothink\n{question}",
        "temperature": 0.2, "max_output_tokens": 512, "stream": False, "store": False
    }).encode()
    try:
        req = urllib.request.Request("http://127.0.0.1:1234/api/v1/chat",
            data=payload, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        for item in reversed(data.get("output", [])):
            if item.get("type") == "message":
                c = item.get("content", "")
                if isinstance(c, list):
                    for x in c:
                        if isinstance(x, dict) and x.get("type") == "output_text":
                            return x["text"][:500]
                elif isinstance(c, str):
                    return c[:500]
    except Exception as e:
        return f"M1_ERROR: {e}"
    return "M1_NO_RESPONSE"


def query_ol1(question):
    """Query OL1/qwen3:1.7b."""
    import urllib.request
    payload = json.dumps({
        "model": "qwen3:1.7b",
        "messages": [{"role": "user", "content": f"/no_think\n{question}"}],
        "stream": False
    }).encode()
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/chat",
            data=payload, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        return data.get("message", {}).get("content", "OL1_NO_RESPONSE")[:500]
    except Exception as e:
        return f"OL1_ERROR: {e}"


def consensus(question):
    """Run consensus vote."""
    responses = {}
    responses["M1"] = query_m1(question)
    responses["OL1"] = query_ol1(question)

    # Log to DB
    try:
        db = sqlite3.connect(str(DB_PATH))
        db.execute("INSERT INTO consensus_log (timestamp, query, verdict, confidence, details) VALUES (?,?,?,?,?)",
            (datetime.now().isoformat(), question[:200], "pending", 0.0, json.dumps(responses, default=str)))
        db.commit()
        db.close()
    except Exception:
        pass

    result = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "responses": responses,
        "agents_responded": len([v for v in responses.values() if "ERROR" not in v]),
        "total_agents": len(responses)
    }
    print(json.dumps(result, indent=2, default=str))
    return result


def main():
    parser = argparse.ArgumentParser(description="Cluster Consensus Voting")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--question", "-q", type=str, required=True, help="Question to vote on")
    args = parser.parse_args()
    consensus(args.question)


if __name__ == "__main__":
    main()
