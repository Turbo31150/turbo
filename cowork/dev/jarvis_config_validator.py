#!/usr/bin/env python3
"""jarvis_config_validator.py — Valide toutes les configs JARVIS.

CLAUDE.md, plugin.json, .mcp.json, settings.

Usage:
    python dev/jarvis_config_validator.py --once
    python dev/jarvis_config_validator.py --validate
    python dev/jarvis_config_validator.py --fix
    python dev/jarvis_config_validator.py --report
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "config_validator.db"

CONFIG_FILES = [
    {
        "name": "CLAUDE.md",
        "path": "C:/Users/franc/.claude/CLAUDE.md",
        "type": "markdown",
        "required_keywords": ["PROTOCOLE", "AGENTS", "MATRICE", "ROUTING"],
    },
    {
        "name": "MEMORY.md",
        "path": "C:/Users/franc/.claude/projects/C--Users-franc/memory/MEMORY.md",
        "type": "markdown",
        "required_keywords": ["Setup", "Cluster", "Architecture"],
    },
    {
        "name": "plugin.json",
        "path": "C:/Users/franc/.claude/plugins/local/jarvis-turbo/plugin.json",
        "type": "json",
        "required_fields": ["name", "version", "description"],
    },
    {
        "name": "settings.json",
        "path": "C:/Users/franc/.claude/settings.json",
        "type": "json",
        "required_fields": [],
    },
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS validations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, config_name TEXT, status TEXT,
        issues_count INTEGER, details TEXT)""")
    db.commit()
    return db


def validate_json_file(config):
    """Validate a JSON config file."""
    issues = []
    path = Path(config["path"])

    if not path.exists():
        return {"status": "missing", "issues": ["File not found"]}

    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)

        # Check required fields
        for field in config.get("required_fields", []):
            if field not in data:
                issues.append(f"Missing required field: {field}")

        # Check for empty values
        for key, val in data.items() if isinstance(data, dict) else []:
            if val == "" or val is None:
                issues.append(f"Empty value for key: {key}")

        return {
            "status": "valid" if not issues else "issues",
            "size_bytes": len(content),
            "keys": len(data) if isinstance(data, dict) else 0,
            "issues": issues,
        }
    except json.JSONDecodeError as e:
        return {"status": "invalid_json", "issues": [str(e)[:100]]}
    except Exception as e:
        return {"status": "error", "issues": [str(e)[:100]]}


def validate_markdown_file(config):
    """Validate a Markdown config file."""
    issues = []
    path = Path(config["path"])

    if not path.exists():
        return {"status": "missing", "issues": ["File not found"]}

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")

        # Check size
        if len(content) < 100:
            issues.append("File too short (<100 chars)")
        if len(content) > 100000:
            issues.append("File very large (>100KB)")

        # Check required keywords
        for kw in config.get("required_keywords", []):
            if kw.lower() not in content.lower():
                issues.append(f"Missing keyword: {kw}")

        # Check for broken references
        lines = content.split("\n")
        for i, line in enumerate(lines):
            # Check file paths in backticks
            for match in __import__("re").findall(r'`([A-Z]:[/\\][^`]+)`', line):
                if not Path(match.replace("\\", "/")).exists():
                    if not any(skip in match for skip in ["PROMPT", "example", "YYYY"]):
                        issues.append(f"L{i+1}: Broken path reference: {match[:60]}")

        return {
            "status": "valid" if not issues else "issues",
            "size_bytes": len(content),
            "lines": len(lines),
            "issues": issues[:10],
        }
    except Exception as e:
        return {"status": "error", "issues": [str(e)[:100]]}


def do_validate():
    """Validate all configs."""
    db = init_db()
    results = []

    for config in CONFIG_FILES:
        if config["type"] == "json":
            result = validate_json_file(config)
        elif config["type"] == "markdown":
            result = validate_markdown_file(config)
        else:
            result = {"status": "unknown_type", "issues": []}

        result["name"] = config["name"]
        result["path"] = config["path"]
        results.append(result)

        db.execute(
            "INSERT INTO validations (ts, config_name, status, issues_count, details) VALUES (?,?,?,?,?)",
            (time.time(), config["name"], result["status"],
             len(result.get("issues", [])), json.dumps(result))
        )

    valid = sum(1 for r in results if r["status"] == "valid")
    total_issues = sum(len(r.get("issues", [])) for r in results)

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "configs_checked": len(results),
        "valid": valid,
        "total_issues": total_issues,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Config Validator")
    parser.add_argument("--once", "--validate", action="store_true", help="Validate all")
    parser.add_argument("--fix", action="store_true", help="Auto-fix")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()

    result = do_validate()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
