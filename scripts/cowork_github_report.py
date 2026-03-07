"""JARVIS Cowork GitHub Report — Generates audit reports for jarvis-cowork repo.

Produces a structured report of:
- All cowork scripts inventory (438 scripts)
- Pattern classification and coverage
- Agent routing mapping
- OpenClaw integration status
- Test coverage and health

Usage:
    uv run python scripts/cowork_github_report.py
    uv run python scripts/cowork_github_report.py --push  # Generate + git push to jarvis-cowork
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

TURBO_DIR = Path(_root)
COWORK_DIR = TURBO_DIR / "cowork" / "dev"
ETOILE_DB = TURBO_DIR / "data" / "etoile.db"
REPORT_DIR = TURBO_DIR / "cowork" / "dev" / "reports"


def count_scripts() -> dict:
    """Count and categorize all cowork scripts."""
    scripts = []
    categories = Counter()

    for f in sorted(COWORK_DIR.glob("*.py")):
        if f.name.startswith("_"):
            continue
        name = f.stem
        size = f.stat().st_size
        lines = len(f.read_text(encoding="utf-8", errors="replace").splitlines())

        # Auto-categorize by prefix/keywords
        cat = "other"
        if name.startswith("auto_"):
            cat = "automation"
        elif name.startswith("trading") or "trade" in name:
            cat = "trading"
        elif name.startswith("daily_") or "report" in name:
            cat = "reporting"
        elif name.startswith("cluster_") or "cluster" in name or "node" in name:
            cat = "cluster"
        elif "monitor" in name or "health" in name or "alert" in name:
            cat = "monitoring"
        elif "pipeline" in name or "domino" in name:
            cat = "pipeline"
        elif "browser" in name or "web" in name or "linkedin" in name:
            cat = "web"
        elif "voice" in name or "whisper" in name or "tts" in name:
            cat = "voice"
        elif "security" in name or "audit" in name or "credential" in name:
            cat = "security"
        elif "test" in name or "benchmark" in name:
            cat = "testing"
        elif "skill" in name or "memory" in name or "brain" in name:
            cat = "intelligence"
        elif "deploy" in name or "git" in name or "ci" in name:
            cat = "devops"
        elif "telegram" in name or "message" in name:
            cat = "communication"

        categories[cat] += 1
        scripts.append({"name": name, "category": cat, "lines": lines, "size": size})

    return {
        "total": len(scripts),
        "categories": dict(categories.most_common()),
        "scripts": scripts,
        "top_by_size": sorted(scripts, key=lambda x: -x["lines"])[:20],
    }


def get_db_stats() -> dict:
    """Get cowork-related DB stats from etoile.db."""
    try:
        db = sqlite3.connect(str(ETOILE_DB))
        db.row_factory = sqlite3.Row

        tables = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%cowork%'"
        ).fetchall()]

        stats = {"tables": tables}

        for table in tables:
            count = db.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
            stats[table] = {"count": count}

        # Tool metrics
        try:
            tool_count = db.execute("SELECT COUNT(*) FROM tool_metrics").fetchone()[0]
            tool_agents = db.execute(
                "SELECT tool_name, COUNT(*) as n FROM tool_metrics GROUP BY tool_name ORDER BY n DESC LIMIT 10"
            ).fetchall()
            stats["tool_metrics"] = {
                "total": tool_count,
                "top_tools": [{"tool": r["tool_name"], "calls": r["n"]} for r in tool_agents],
            }
        except Exception:
            pass

        # Dispatch log
        try:
            dispatch_count = db.execute("SELECT COUNT(*) FROM agent_dispatch_log").fetchone()[0]
            stats["dispatch_log"] = {"total": dispatch_count}
        except Exception:
            pass

        db.close()
        return stats
    except Exception as e:
        return {"error": str(e)}


def get_openclaw_status() -> dict:
    """Get OpenClaw agent status."""
    agents_dir = Path(os.path.expanduser("~/.openclaw/agents"))
    if not agents_dir.exists():
        return {"error": "OpenClaw agents dir not found"}

    agents = []
    for d in sorted(agents_dir.iterdir()):
        if d.is_dir():
            identity = d / "agent" / "IDENTITY.md"
            models = d / "agent" / "models.json"
            agents.append({
                "name": d.name,
                "identity": identity.exists(),
                "models": models.exists(),
            })

    return {
        "total": len(agents),
        "with_identity": sum(1 for a in agents if a["identity"]),
        "with_models": sum(1 for a in agents if a["models"]),
        "agents": agents,
    }


def get_test_stats() -> dict:
    """Get test suite stats."""
    test_dir = TURBO_DIR / "tests"
    test_files = list(test_dir.glob("test_*.py"))
    total_funcs = 0
    for f in test_files:
        content = f.read_text(encoding="utf-8", errors="replace")
        total_funcs += content.count("def test_")

    return {
        "test_files": len(test_files),
        "test_functions": total_funcs,
    }


def generate_report() -> str:
    """Generate the full markdown report."""
    now = datetime.now()
    scripts = count_scripts()
    db_stats = get_db_stats()
    openclaw = get_openclaw_status()
    tests = get_test_stats()

    # Build routing coverage
    try:
        from src.openclaw_bridge import INTENT_TO_AGENT
        routing_count = len(INTENT_TO_AGENT)
        agents_routed = len(set(INTENT_TO_AGENT.values()))
    except Exception:
        routing_count = 0
        agents_routed = 0

    report = f"""# JARVIS Cowork Report — {now.strftime('%Y-%m-%d %H:%M')}

## Summary

| Metric | Value |
|--------|-------|
| Cowork scripts | {scripts['total']} |
| Source modules (src/) | {len(list((TURBO_DIR / 'src').glob('*.py')))} |
| Test files | {tests['test_files']} |
| Test functions | {tests['test_functions']} |
| OpenClaw agents | {openclaw.get('total', 0)} |
| Agents with IDENTITY | {openclaw.get('with_identity', 0)}/{openclaw.get('total', 0)} |
| Intent routes | {routing_count} |
| Agents routed | {agents_routed} |

## Cowork Scripts by Category

| Category | Count |
|----------|-------|
"""
    for cat, count in sorted(scripts["categories"].items(), key=lambda x: -x[1]):
        report += f"| {cat} | {count} |\n"

    report += f"""
## Top 20 Scripts by Size

| Script | Lines | Category |
|--------|-------|----------|
"""
    for s in scripts["top_by_size"]:
        report += f"| {s['name']} | {s['lines']} | {s['category']} |\n"

    report += f"""
## OpenClaw Agents ({openclaw.get('total', 0)})

| Agent | IDENTITY | Models |
|-------|----------|--------|
"""
    for a in openclaw.get("agents", []):
        id_s = "OK" if a["identity"] else "---"
        mod_s = "OK" if a["models"] else "---"
        report += f"| {a['name']} | {id_s} | {mod_s} |\n"

    report += f"""
## Database Stats

"""
    if "tool_metrics" in db_stats:
        report += f"- Tool calls tracked: {db_stats['tool_metrics']['total']}\n"
        report += "- Top tools:\n"
        for t in db_stats["tool_metrics"].get("top_tools", [])[:5]:
            report += f"  - {t['tool']}: {t['calls']} calls\n"

    if "dispatch_log" in db_stats:
        report += f"- Dispatch log entries: {db_stats['dispatch_log']['total']}\n"

    report += f"""
## Architecture

```
Message → Intent Classifier → OpenClaw Bridge → Agent Selection
                                    ↓
                            Dispatch Engine → Node Selection (M1/M2/M3/OL1)
                                    ↓
                            Quality Gate → Feedback Loop → Episodic Memory
```

## Generated

- Date: {now.isoformat()}
- Generator: scripts/cowork_github_report.py
- JARVIS v12.4 — Turbo Cluster
"""
    return report


def main():
    parser = argparse.ArgumentParser(description="JARVIS Cowork GitHub Report")
    parser.add_argument("--push", action="store_true", help="Generate and push to GitHub")
    parser.add_argument("--output", type=str, help="Output file path")
    args = parser.parse_args()

    report = generate_report()

    # Save report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = args.output or str(REPORT_DIR / f"report_{date_str}.md")
    Path(output_path).write_text(report, encoding="utf-8")
    print(f"Report saved: {output_path}")

    # Also save as latest
    latest_path = REPORT_DIR / "LATEST_REPORT.md"
    latest_path.write_text(report, encoding="utf-8")
    print(f"Latest: {latest_path}")

    if args.push:
        print("\nPushing to GitHub jarvis-cowork remote...")
        try:
            subprocess.run(["git", "add", str(output_path), str(latest_path)],
                           cwd=str(TURBO_DIR), check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"report: cowork audit {date_str}"],
                cwd=str(TURBO_DIR), check=True, capture_output=True,
            )
            print("Committed. Use 'git push jarvis-cowork main' to push.")
        except subprocess.CalledProcessError as e:
            print(f"Git error: {e.stderr.decode()[:200] if e.stderr else e}")

    # Print summary
    print("\n" + "=" * 50)
    print(report[:500])
    print("...")


if __name__ == "__main__":
    main()
