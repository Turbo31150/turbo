#!/usr/bin/env python3
"""ia_code_generator_v2.py — Autonomous code generation from specs (#249).

Sends spec to M1 (curl 127.0.0.1:1234/api/v1/chat), extracts code from
response, validates with ast.parse, writes to file if valid.

Usage:
    python dev/ia_code_generator_v2.py --once
    python dev/ia_code_generator_v2.py --generate "SPEC"
    python dev/ia_code_generator_v2.py --validate
    python dev/ia_code_generator_v2.py --deploy
    python dev/ia_code_generator_v2.py --history
"""
import argparse
import ast
import json
import os
import re
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "code_generator_v2.db"
OUTPUT_DIR = DEV / "generated"

M1_URL = "http://127.0.0.1:1234/api/v1/chat"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS generations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        spec TEXT NOT NULL,
        code TEXT,
        valid INTEGER DEFAULT 0,
        filename TEXT,
        deployed INTEGER DEFAULT 0,
        model TEXT DEFAULT 'qwen3-8b',
        latency_ms REAL,
        error TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS validations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        generation_id INTEGER,
        valid INTEGER,
        errors TEXT,
        warnings TEXT
    )""")
    db.commit()
    return db


def call_m1(spec):
    """Call M1 (LM Studio) to generate code."""
    prompt = f"/nothink\nGenerate a complete, valid Python script for the following specification. Return ONLY Python code, no explanations:\n\n{spec}"
    body = json.dumps({
        "model": "qwen3-8b",
        "input": prompt,
        "temperature": 0.2,
        "max_output_tokens": 4096,
        "stream": False,
        "store": False,
    })
    start = time.time()
    try:
        out = subprocess.check_output(
            ["curl", "-s", "--max-time", "60",
             M1_URL, "-H", "Content-Type: application/json", "-d", body],
            stderr=subprocess.DEVNULL, text=True, timeout=65,
        )
        latency = (time.time() - start) * 1000
        data = json.loads(out)
        # Extract from output array - take last message type
        output = data.get("output", [])
        content = ""
        for item in reversed(output):
            if item.get("type") == "message":
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        content = c.get("text", "")
                        break
                if content:
                    break
        if not content and output:
            content = str(output[0].get("content", ""))
        return content, latency, None
    except subprocess.TimeoutExpired:
        return None, (time.time() - start) * 1000, "timeout"
    except Exception as e:
        return None, (time.time() - start) * 1000, str(e)


def extract_code(raw_response):
    """Extract Python code from model response."""
    if not raw_response:
        return None

    match = re.search(r'```python\s*\n(.*?)```', raw_response, re.DOTALL)
    if match:
        return match.group(1).strip()

    match = re.search(r'```\s*\n(.*?)```', raw_response, re.DOTALL)
    if match:
        return match.group(1).strip()

    stripped = raw_response.strip()
    if stripped.startswith(("import ", "from ", "#!/", "def ", "class ", "#")):
        return stripped

    return stripped


def validate_python(code):
    """Validate Python code with ast.parse."""
    errors = []
    warnings = []
    try:
        tree = ast.parse(code)
        functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]

        if not functions and not classes:
            warnings.append("No functions or classes defined")

        code_lines = code.split("\n")
        for i, line in enumerate(code_lines):
            if "exec(" in line or "eval(" in line:
                warnings.append(f"Line {i+1}: Uses exec/eval (security risk)")
            if "os.system(" in line:
                warnings.append(f"Line {i+1}: Uses os.system (prefer subprocess)")

        return True, errors, warnings, {
            "functions": len(functions),
            "classes": len(classes),
            "imports": len(imports),
            "lines": len(code_lines),
        }
    except SyntaxError as e:
        errors.append(f"SyntaxError at line {e.lineno}: {e.msg}")
        return False, errors, warnings, {}


def do_generate(spec):
    """Generate code from specification."""
    db = init_db()
    now = datetime.now()

    raw, latency, error = call_m1(spec)

    if error:
        db.execute(
            "INSERT INTO generations (ts, spec, error, latency_ms) VALUES (?,?,?,?)",
            (now.isoformat(), spec, error, round(latency, 1)),
        )
        db.commit()
        db.close()
        return {
            "ts": now.isoformat(), "action": "generate", "spec": spec,
            "success": False, "error": error, "latency_ms": round(latency, 1),
        }

    code = extract_code(raw)
    if not code:
        db.execute(
            "INSERT INTO generations (ts, spec, error, latency_ms) VALUES (?,?,?,?)",
            (now.isoformat(), spec, "no_code_extracted", round(latency, 1)),
        )
        db.commit()
        db.close()
        return {
            "ts": now.isoformat(), "action": "generate", "spec": spec,
            "success": False, "error": "no_code_extracted",
            "raw_preview": (raw[:300] + "...") if raw and len(raw) > 300 else raw,
        }

    valid, errors, warnings, stats = validate_python(code)

    safe_name = re.sub(r'[^a-z0-9_]', '_', spec[:40].lower().strip())
    filename = f"gen_{safe_name}.py"

    gen_id = db.execute(
        "INSERT INTO generations (ts, spec, code, valid, filename, model, latency_ms, error) VALUES (?,?,?,?,?,?,?,?)",
        (now.isoformat(), spec, code, int(valid), filename, "qwen3-8b",
         round(latency, 1), "; ".join(errors) if errors else None),
    ).lastrowid

    db.execute(
        "INSERT INTO validations (ts, generation_id, valid, errors, warnings) VALUES (?,?,?,?,?)",
        (now.isoformat(), gen_id, int(valid), json.dumps(errors), json.dumps(warnings)),
    )
    db.commit()

    result = {
        "ts": now.isoformat(), "action": "generate", "spec": spec,
        "success": valid, "generation_id": gen_id, "filename": filename,
        "code_lines": stats.get("lines", 0), "functions": stats.get("functions", 0),
        "classes": stats.get("classes", 0), "valid": valid,
        "errors": errors, "warnings": warnings, "latency_ms": round(latency, 1),
        "code_preview": code[:500] + "..." if len(code) > 500 else code,
    }
    db.close()
    return result


def do_validate():
    """Validate latest unvalidated generation."""
    db = init_db()
    row = db.execute(
        "SELECT id, code, filename FROM generations WHERE valid=0 AND code IS NOT NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if not row:
        db.close()
        return {"ts": datetime.now().isoformat(), "action": "validate", "message": "No unvalidated generations"}

    gen_id, code, filename = row
    valid, errors, warnings, stats = validate_python(code)

    db.execute("UPDATE generations SET valid=? WHERE id=?", (int(valid), gen_id))
    db.execute(
        "INSERT INTO validations (ts, generation_id, valid, errors, warnings) VALUES (?,?,?,?,?)",
        (datetime.now().isoformat(), gen_id, int(valid), json.dumps(errors), json.dumps(warnings)),
    )
    db.commit()

    result = {
        "ts": datetime.now().isoformat(), "action": "validate",
        "generation_id": gen_id, "filename": filename,
        "valid": valid, "errors": errors, "warnings": warnings, "stats": stats,
    }
    db.close()
    return result


def do_deploy():
    """Deploy latest valid generation to file."""
    db = init_db()
    row = db.execute(
        "SELECT id, code, filename FROM generations WHERE valid=1 AND deployed=0 ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if not row:
        db.close()
        return {"ts": datetime.now().isoformat(), "action": "deploy", "message": "No valid undeployed generations"}

    gen_id, code, filename = row
    filepath = OUTPUT_DIR / filename

    try:
        filepath.write_text(code, encoding="utf-8")
        db.execute("UPDATE generations SET deployed=1 WHERE id=?", (gen_id,))
        db.commit()
        result = {
            "ts": datetime.now().isoformat(), "action": "deploy",
            "generation_id": gen_id, "filename": filename,
            "path": str(filepath), "success": True,
        }
    except Exception as e:
        result = {
            "ts": datetime.now().isoformat(), "action": "deploy",
            "generation_id": gen_id, "success": False, "error": str(e),
        }

    db.close()
    return result


def do_history():
    """Show generation history."""
    db = init_db()
    rows = db.execute(
        "SELECT id, ts, spec, valid, deployed, filename, latency_ms, error FROM generations ORDER BY id DESC LIMIT 20"
    ).fetchall()

    total = db.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
    valid_count = db.execute("SELECT COUNT(*) FROM generations WHERE valid=1").fetchone()[0]
    deployed_count = db.execute("SELECT COUNT(*) FROM generations WHERE deployed=1").fetchone()[0]

    result = {
        "ts": datetime.now().isoformat(), "action": "history",
        "total_generations": total, "valid": valid_count, "deployed": deployed_count,
        "success_rate": round(valid_count / max(total, 1), 3),
        "recent": [
            {"id": r[0], "ts": r[1], "spec": r[2][:80], "valid": bool(r[3]),
             "deployed": bool(r[4]), "filename": r[5], "latency_ms": r[6], "error": r[7]}
            for r in rows
        ],
    }
    db.close()
    return result


def do_status():
    db = init_db()
    result = {
        "ts": datetime.now().isoformat(),
        "script": "ia_code_generator_v2.py",
        "script_id": 249,
        "db": str(DB_PATH),
        "output_dir": str(OUTPUT_DIR),
        "total_generations": db.execute("SELECT COUNT(*) FROM generations").fetchone()[0],
        "valid_generations": db.execute("SELECT COUNT(*) FROM generations WHERE valid=1").fetchone()[0],
        "deployed": db.execute("SELECT COUNT(*) FROM generations WHERE deployed=1").fetchone()[0],
        "status": "ok",
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="ia_code_generator_v2.py — Autonomous code generation (#249)")
    parser.add_argument("--generate", type=str, metavar="SPEC", help="Generate code from specification")
    parser.add_argument("--validate", action="store_true", help="Validate latest generation")
    parser.add_argument("--deploy", action="store_true", help="Deploy latest valid generation")
    parser.add_argument("--history", action="store_true", help="Show generation history")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.generate:
        result = do_generate(args.generate)
    elif args.validate:
        result = do_validate()
    elif args.deploy:
        result = do_deploy()
    elif args.history:
        result = do_history()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
