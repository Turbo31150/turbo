#!/usr/bin/env python3
"""ia_code_generator.py — Generateur de code IA.

Cree du code a partir de specifications NL via cluster.

Usage:
    python dev/ia_code_generator.py --once
    python dev/ia_code_generator.py --generate "SPEC"
    python dev/ia_code_generator.py --language py
    python dev/ia_code_generator.py --test
"""
import argparse
import ast
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "code_generator.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS generations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, spec TEXT, language TEXT,
        code TEXT, valid INTEGER, quality_score REAL)""")
    db.commit()
    return db


def query_m1(prompt, max_tokens=2048):
    try:
        body = json.dumps({
            "model": "qwen3-8b",
            "input": f"/nothink\n{prompt}",
            "temperature": 0.2,
            "max_output_tokens": max_tokens,
            "stream": False, "store": False,
        })
        out = subprocess.run(
            ["curl", "-s", "--max-time", "60", "http://127.0.0.1:1234/api/v1/chat",
             "-H", "Content-Type: application/json", "-d", body],
            capture_output=True, text=True, timeout=65
        )
        if out.stdout.strip():
            data = json.loads(out.stdout)
            for item in reversed(data.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return c.get("text", "")
    except Exception:
        pass
    return ""


def extract_code(text, lang="python"):
    # Extract from markdown code blocks
    import re
    pattern = rf"```(?:{lang}|py|python)?\s*\n(.*?)```"
    m = re.search(pattern, text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Fallback: return text that looks like code
    lines = [l for l in text.split("\n") if l.strip() and not l.startswith("#")]
    return "\n".join(lines)


def validate_python(code):
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"


def generate_code(spec, lang="py"):
    prompt = f"""Generate a clean, working {lang} function for this specification:

{spec}

Requirements:
- Only output the code, no explanations
- Include type hints if Python
- Handle edge cases
- Keep it simple and readable"""

    response = query_m1(prompt)
    code = extract_code(response, "python" if lang == "py" else lang)

    valid = False
    error = None
    if lang == "py":
        valid, error = validate_python(code)
    elif code.strip():
        valid = True

    quality = 0.0
    if valid:
        quality = 0.5
        if len(code.split("\n")) > 3:
            quality += 0.2
        if "def " in code or "function " in code:
            quality += 0.2
        if '"""' in code or "'''" in code or "//" in code:
            quality += 0.1

    return {
        "spec": spec,
        "language": lang,
        "code": code[:2000],
        "valid": valid,
        "error": error,
        "quality_score": round(quality, 2),
        "lines": len(code.split("\n")),
    }


def do_generate(spec=None, lang="py"):
    db = init_db()

    if not spec:
        spec = "Create a function that calculates Fibonacci numbers efficiently"

    result = generate_code(spec, lang)

    db.execute("INSERT INTO generations (ts, spec, language, code, valid, quality_score) VALUES (?,?,?,?,?,?)",
               (time.time(), result["spec"], result["language"], result["code"],
                int(result["valid"]), result["quality_score"]))
    db.commit()
    db.close()

    return {"ts": datetime.now().isoformat(), **result}


def do_stats():
    db = init_db()
    total = db.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
    valid = db.execute("SELECT COUNT(*) FROM generations WHERE valid=1").fetchone()[0]
    avg_q = db.execute("SELECT AVG(quality_score) FROM generations").fetchone()[0] or 0
    db.close()
    return {
        "ts": datetime.now().isoformat(),
        "total_generations": total,
        "valid_pct": round(valid / max(total, 1) * 100, 1),
        "avg_quality": round(avg_q, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="IA Code Generator")
    parser.add_argument("--once", action="store_true", help="Generate sample")
    parser.add_argument("--generate", metavar="SPEC", help="Generate from spec")
    parser.add_argument("--language", metavar="LANG", default="py", choices=["py", "js", "bash"])
    parser.add_argument("--test", action="store_true", help="Test generation")
    parser.add_argument("--save", action="store_true", help="Save output")
    args = parser.parse_args()

    if args.generate:
        print(json.dumps(do_generate(args.generate, args.language), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_stats(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
