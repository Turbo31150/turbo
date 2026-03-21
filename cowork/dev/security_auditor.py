#!/usr/bin/env python3
"""Scan F:/BUREAU/turbo for exposed secrets in .py, .js, .json files.

Checks patterns: sk-, Bearer, password=, token=, PRIVATE_KEY.
Also verifies that api_keys table values in etoile.db are obfuscated.
Reports findings with file:line. Outputs JSON summary.
Logs execution to etoile.db cowork_execution_log.
"""

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

ETOILE_DB = Path(r"F:\BUREAU\turbo\etoile.db")
SCAN_ROOT = Path(r"F:\BUREAU\turbo")

# Directories to skip
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache"}

# Secret patterns: name -> regex
SECRET_PATTERNS = {
    "api_key_sk": re.compile(r'sk-[a-zA-Z0-9_\-:]{10,}'),
    "bearer_token": re.compile(r'Bearer\s+[a-zA-Z0-9_\-\.]{10,}'),
    "password_assign": re.compile(r'password\s*[=:]\s*["\'][^"\']{4,}["\']', re.IGNORECASE),
    "token_assign": re.compile(r'token\s*[=:]\s*["\'][a-zA-Z0-9_\-\.]{10,}["\']', re.IGNORECASE),
    "private_key": re.compile(r'PRIVATE[_\s]KEY', re.IGNORECASE),
    "secret_assign": re.compile(r'secret\s*[=:]\s*["\'][^"\']{6,}["\']', re.IGNORECASE),
}

# File extensions to scan
SCAN_EXTENSIONS = {".py", ".js", ".json", ".env", ".yml", ".yaml", ".toml"}


def log_run(db_path: Path, script: str, exit_code: int, duration_ms: float,
            success: bool, stdout_preview: str = "", stderr_preview: str = ""):
    try:
        con = sqlite3.connect(str(db_path))
        con.execute(
            "INSERT INTO cowork_execution_log (script,args,exit_code,duration_ms,success,stdout_preview,stderr_preview)"
            " VALUES (?,?,?,?,?,?,?)",
            (script, "--once", exit_code, duration_ms, int(success),
             stdout_preview[:500], stderr_preview[:500]))
        con.commit()
        con.close()
    except Exception:
        pass


def scan_files() -> list[dict]:
    """Scan all target files for secret patterns."""
    findings = []
    for ext in SCAN_EXTENSIONS:
        for fpath in SCAN_ROOT.rglob(f"*{ext}"):
            # Skip excluded dirs
            if any(skip in fpath.parts for skip in SKIP_DIRS):
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except (PermissionError, OSError):
                continue
            for line_no, line in enumerate(text.splitlines(), 1):
                for pname, pattern in SECRET_PATTERNS.items():
                    if pattern.search(line):
                        # Truncate line for safety
                        snippet = line.strip()[:120]
                        findings.append({
                            "file": str(fpath),
                            "line": line_no,
                            "pattern": pname,
                            "snippet": snippet,
                        })
    return findings


def check_api_keys_obfuscation() -> dict:
    """Check that api_keys values in etoile.db are obfuscated (not plaintext)."""
    if not ETOILE_DB.exists():
        return {"status": "db_not_found"}
    con = sqlite3.connect(str(ETOILE_DB))
    try:
        rows = con.execute("SELECT service, key_value FROM api_keys").fetchall()
    except Exception as exc:
        con.close()
        return {"status": f"error: {exc}"}
    con.close()

    exposed = []
    for service, key_value in rows:
        if not key_value:
            continue
        # Consider exposed if it looks like a raw key (long alphanumeric, starts with sk-, etc.)
        if (len(key_value) > 20 and re.match(r'^[a-zA-Z0-9_\-:\.]+$', key_value)
                and not key_value.startswith("***")):
            exposed.append({"service": service, "key_preview": key_value[:8] + "..."})

    return {
        "total_keys": len(rows),
        "exposed_count": len(exposed),
        "exposed": exposed,
        "status": "WARN_EXPOSED" if exposed else "OK_OBFUSCATED",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.parse_args()

    t0 = time.time()
    try:
        findings = scan_files()
        api_check = check_api_keys_obfuscation()

        result = {
            "scan_root": str(SCAN_ROOT),
            "files_findings": len(findings),
            "unique_files": len({f["file"] for f in findings}),
            "by_pattern": {},
            "api_keys_check": api_check,
            "findings": findings[:100],  # Cap output
        }
        for f in findings:
            p = f["pattern"]
            result["by_pattern"][p] = result["by_pattern"].get(p, 0) + 1

        output = json.dumps(result, indent=2, ensure_ascii=False)
        print(output)
        duration = (time.time() - t0) * 1000
        log_run(ETOILE_DB, "security_auditor.py", 0, duration, True, output[:500])
    except Exception as exc:
        duration = (time.time() - t0) * 1000
        err = str(exc)
        log_run(ETOILE_DB, "security_auditor.py", 1, duration, False, stderr_preview=err)
        print(json.dumps({"error": err}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
