#!/usr/bin/env python3
"""ia_autonomous_coder.py — Codeur autonome JARVIS.

Genere, ameliore et review des scripts sans intervention humaine.
Utilise gpt-oss:120b via OL1.

Usage:
    python dev/ia_autonomous_coder.py --once
    python dev/ia_autonomous_coder.py --generate "Script qui monitore la RAM"
    python dev/ia_autonomous_coder.py --improve SCRIPT
    python dev/ia_autonomous_coder.py --review
"""
import argparse
import ast
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "autonomous_coder.db"
OL1_URL = "http://127.0.0.1:11434/api/chat"
M1_URL = "http://127.0.0.1:1234/api/v1/chat"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS generations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, description TEXT, filename TEXT,
        model TEXT, success INTEGER, attempt INTEGER,
        error TEXT)""")
    db.commit()
    return db


def query_gpt_oss(prompt, timeout=120):
    """Query gpt-oss:120b via Ollama."""
    try:
        data = json.dumps({
            "model": "gpt-oss:120b-cloud",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False, "think": False,
        }).encode()
        req = urllib.request.Request(OL1_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read().decode())
            return result.get("message", {}).get("content", "")
    except Exception:
        pass
    # Fallback M1
    try:
        data = json.dumps({
            "model": "qwen3-8b", "input": f"/nothink\n{prompt}",
            "temperature": 0.3, "max_output_tokens": 4096, "stream": False, "store": False,
        }).encode()
        req = urllib.request.Request(M1_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read().decode())
            for item in reversed(result.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return c.get("text", "")
    except Exception:
        pass
    return ""


def extract_python(response):
    """Extract Python code from response."""
    # Try to find ```python ... ``` block
    if "```python" in response:
        start = response.index("```python") + 9
        end = response.index("```", start) if "```" in response[start:] else len(response)
        return response[start:end].strip()
    if "```" in response:
        start = response.index("```") + 3
        end = response.index("```", start) if "```" in response[start:] else len(response)
        return response[start:end].strip()
    # If no code blocks, return as-is if it looks like Python
    if "def " in response or "import " in response:
        return response.strip()
    return ""


def validate_code(code):
    """Validate Python code syntax."""
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, str(e)


def test_script(filepath):
    """Test a script with --help."""
    try:
        result = subprocess.run(
            [sys.executable, str(filepath), "--help"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def generate_script(description, max_attempts=3):
    """Generate a script from description."""
    db = init_db()
    filename = description.lower().replace(" ", "_")[:30] + ".py"
    filename = "".join(c for c in filename if c.isalnum() or c in "._")

    prompt = f"""Genere un script Python JARVIS standalone pour: {description}

REGLES:
- Uniquement stdlib Python (pas de pip install)
- argparse CLI avec --help et --once
- Sortie JSON via json.dumps
- SQLite pour stockage dans dev/data/
- Compatible Windows 11

Reponds UNIQUEMENT avec le code Python complet, pas d'explication."""

    for attempt in range(1, max_attempts + 1):
        response = query_gpt_oss(prompt)
        code = extract_python(response)

        if not code:
            db.execute(
                "INSERT INTO generations (ts, description, filename, model, success, attempt, error) VALUES (?,?,?,?,?,?,?)",
                (time.time(), description, filename, "gpt-oss", 0, attempt, "no_code_extracted")
            )
            continue

        valid, error = validate_code(code)
        if not valid:
            # Retry with error context
            prompt += f"\n\nERREUR PRECEDENTE: {error}\nCorrige le code."
            db.execute(
                "INSERT INTO generations (ts, description, filename, model, success, attempt, error) VALUES (?,?,?,?,?,?,?)",
                (time.time(), description, filename, "gpt-oss", 0, attempt, error)
            )
            continue

        # Write file
        filepath = DEV / filename
        filepath.write_text(code, encoding="utf-8")

        # Test
        if test_script(filepath):
            db.execute(
                "INSERT INTO generations (ts, description, filename, model, success, attempt, error) VALUES (?,?,?,?,?,?,?)",
                (time.time(), description, filename, "gpt-oss", 1, attempt, "")
            )
            db.commit()
            db.close()
            return {"success": True, "filename": filename, "attempts": attempt, "lines": len(code.split("\n"))}
        else:
            filepath.unlink()
            db.execute(
                "INSERT INTO generations (ts, description, filename, model, success, attempt, error) VALUES (?,?,?,?,?,?,?)",
                (time.time(), description, filename, "gpt-oss", 0, attempt, "test_failed")
            )

    db.commit()
    db.close()
    return {"success": False, "filename": filename, "attempts": max_attempts, "error": "max_attempts_reached"}


def do_once():
    """Check COWORK_QUEUE for pending scripts and generate one."""
    queue_file = DEV.parent / "COWORK_QUEUE.md"
    if not queue_file.exists():
        return {"message": "No COWORK_QUEUE.md found"}

    content = queue_file.read_text(encoding="utf-8", errors="ignore")
    # Find first PENDING script
    for line in content.split("\n"):
        if "PENDING" in line and "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                script_name = parts[2] if len(parts) > 2 else ""
                if script_name.endswith(".py"):
                    return {"next_pending": script_name, "status": "would_generate"}

    return {"message": "No pending scripts found"}


def main():
    parser = argparse.ArgumentParser(description="IA Autonomous Coder")
    parser.add_argument("--once", action="store_true", help="Check queue + generate")
    parser.add_argument("--generate", metavar="DESC", help="Generate script from description")
    parser.add_argument("--improve", metavar="SCRIPT", help="Improve existing script")
    parser.add_argument("--review", action="store_true", help="Review recent generations")
    args = parser.parse_args()

    if args.generate:
        result = generate_script(args.generate)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.review:
        db = init_db()
        rows = db.execute("SELECT ts, description, filename, success, attempt FROM generations ORDER BY ts DESC LIMIT 10").fetchall()
        db.close()
        print(json.dumps([{
            "ts": datetime.fromtimestamp(r[0]).isoformat(), "desc": r[1],
            "file": r[2], "success": bool(r[3]), "attempt": r[4],
        } for r in rows], indent=2))
    else:
        result = do_once()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
