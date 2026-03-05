#!/usr/bin/env python3
"""jarvis_permission_auditor.py — Auditeur permissions JARVIS.

Verifie que les scripts n'ont pas trop de privileges.

Usage:
    python dev/jarvis_permission_auditor.py --once
    python dev/jarvis_permission_auditor.py --audit
    python dev/jarvis_permission_auditor.py --excessive
    python dev/jarvis_permission_auditor.py --report
"""
import argparse
import ast
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "permission_auditor.db"

DANGEROUS_CALLS = {
    "os.system": "Shell execution",
    "os.popen": "Shell execution",
    "subprocess.call": "Subprocess (check shell=True)",
    "eval": "Dynamic code execution",
    "exec": "Dynamic code execution",
    "compile": "Dynamic compilation",
    "__import__": "Dynamic import",
    "ctypes.windll": "Win32 API access",
    "winreg": "Registry access",
    "shutil.rmtree": "Recursive delete",
    "os.remove": "File deletion",
    "os.unlink": "File deletion",
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS audits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, scripts_scanned INTEGER,
        issues_found INTEGER, high_risk INTEGER, report TEXT)""")
    db.commit()
    return db


def audit_script(filepath):
    issues = []
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except Exception:
        return issues

    # Check imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("ctypes", "winreg"):
                    issues.append({
                        "line": node.lineno,
                        "type": "import",
                        "detail": f"Import {alias.name} — {DANGEROUS_CALLS.get(alias.name, 'system access')}",
                        "risk": "medium",
                    })
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module in ("ctypes", "winreg"):
                issues.append({
                    "line": node.lineno,
                    "type": "import",
                    "detail": f"From {node.module} import — system access",
                    "risk": "medium",
                })

    # Check function calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    func_name = f"{node.func.value.id}.{node.func.attr}"
            elif isinstance(node.func, ast.Name):
                func_name = node.func.id

            if func_name in DANGEROUS_CALLS:
                risk = "high" if func_name in ("eval", "exec", "os.system") else "medium"
                issues.append({
                    "line": node.lineno,
                    "type": "call",
                    "detail": f"{func_name} — {DANGEROUS_CALLS[func_name]}",
                    "risk": risk,
                })

            # Check shell=True in subprocess
            if func_name.startswith("subprocess."):
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value:
                        issues.append({
                            "line": node.lineno,
                            "type": "shell",
                            "detail": f"{func_name} with shell=True",
                            "risk": "high",
                        })

    return issues


def do_audit():
    db = init_db()
    results = []
    total_issues = 0
    high_risk = 0

    for py in sorted(DEV.glob("*.py")):
        issues = audit_script(py)
        if issues:
            results.append({
                "script": py.name,
                "issues": len(issues),
                "high_risk": sum(1 for i in issues if i["risk"] == "high"),
                "details": issues[:5],
            })
            total_issues += len(issues)
            high_risk += sum(1 for i in issues if i["risk"] == "high")

    db.execute("INSERT INTO audits (ts, scripts_scanned, issues_found, high_risk, report) VALUES (?,?,?,?,?)",
               (time.time(), len(list(DEV.glob("*.py"))), total_issues, high_risk,
                json.dumps(results[:20])))
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "scripts_scanned": len(list(DEV.glob("*.py"))),
        "total_issues": total_issues,
        "high_risk": high_risk,
        "medium_risk": total_issues - high_risk,
        "top_risky_scripts": sorted(results, key=lambda x: x["high_risk"], reverse=True)[:10],
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Permission Auditor")
    parser.add_argument("--once", "--audit", action="store_true", help="Audit permissions")
    parser.add_argument("--excessive", action="store_true", help="Show excessive")
    parser.add_argument("--fix", action="store_true", help="Suggest fixes")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()
    print(json.dumps(do_audit(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
