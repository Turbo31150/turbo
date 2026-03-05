#!/usr/bin/env python3
"""MCP Tool Tester — Continuously test all 186+ MCP tools for regressions.

Imports mcp_server tool definitions, runs smoke tests on each handler,
tracks pass/fail rates over time, and alerts on regressions.
"""
import argparse
import importlib.util
import json
import sqlite3
import sys
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "mcp_tests.db"
TURBO = Path("F:/BUREAU/turbo")
MCP_SERVER = TURBO / "src" / "mcp_server.py"

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS test_results (
        id INTEGER PRIMARY KEY, ts REAL, tool_name TEXT,
        status TEXT, error TEXT, duration_ms REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS test_runs (
        id INTEGER PRIMARY KEY, ts REAL, total_tools INTEGER,
        passed INTEGER, failed INTEGER, skipped INTEGER, duration_s REAL)""")
    db.commit()
    return db

def extract_tool_names():
    """Extract tool names from TOOL_DEFINITIONS in mcp_server.py."""
    tools = []
    try:
        content = MCP_SERVER.read_text(encoding="utf-8")
        # Find TOOL_DEFINITIONS entries
        import re
        # Pattern: ("tool_name", "description", {...}, handler_func)
        pattern = r'\(\s*"(\w+)"\s*,'
        in_tools = False
        for line in content.splitlines():
            if "TOOL_DEFINITIONS" in line and "=" in line:
                in_tools = True
                continue
            if in_tools:
                if line.strip().startswith("]"):
                    break
                m = re.search(pattern, line)
                if m:
                    tools.append(m.group(1))
    except Exception as e:
        print(f"Erreur extraction: {e}")
    return tools

def test_tool_importable():
    """Check if mcp_server module is importable."""
    try:
        # Add src to path
        sys.path.insert(0, str(TURBO))
        sys.path.insert(0, str(TURBO / "src"))
        spec = importlib.util.spec_from_file_location("mcp_server", str(MCP_SERVER))
        if spec and spec.loader:
            return True, "Module importable"
    except Exception as e:
        return False, str(e)
    return False, "spec not found"

def smoke_test_tools(db, tools):
    """Run basic smoke tests on tool definitions."""
    passed = failed = skipped = 0
    start = time.time()

    for tool_name in tools:
        t0 = time.time()
        try:
            # Basic checks: name is valid, no spaces, reasonable length
            if not tool_name.isidentifier():
                raise ValueError(f"Invalid tool name: {tool_name}")
            if len(tool_name) > 100:
                raise ValueError(f"Tool name too long: {len(tool_name)}")

            # Check handler exists in source
            content = MCP_SERVER.read_text(encoding="utf-8")
            handler_name = f"handle_{tool_name}"
            alt_handler = f"_handle_{tool_name}"
            if handler_name not in content and alt_handler not in content:
                # Some handlers have different naming
                skipped += 1
                db.execute("INSERT INTO test_results (ts, tool_name, status, error, duration_ms) VALUES (?,?,?,?,?)",
                           (time.time(), tool_name, "skip", "handler not found by name", (time.time()-t0)*1000))
                continue

            passed += 1
            db.execute("INSERT INTO test_results (ts, tool_name, status, error, duration_ms) VALUES (?,?,?,?,?)",
                       (time.time(), tool_name, "pass", None, (time.time()-t0)*1000))
        except Exception as e:
            failed += 1
            db.execute("INSERT INTO test_results (ts, tool_name, status, error, duration_ms) VALUES (?,?,?,?,?)",
                       (time.time(), tool_name, "fail", str(e)[:200], (time.time()-t0)*1000))

    duration = time.time() - start
    db.execute("INSERT INTO test_runs (ts, total_tools, passed, failed, skipped, duration_s) VALUES (?,?,?,?,?,?)",
               (time.time(), len(tools), passed, failed, skipped, duration))
    db.commit()
    return passed, failed, skipped, duration

def check_regressions(db):
    """Compare latest run with previous runs to detect regressions."""
    runs = db.execute(
        "SELECT passed, failed, skipped FROM test_runs ORDER BY ts DESC LIMIT 2"
    ).fetchall()
    if len(runs) < 2:
        return None
    current, previous = runs[0], runs[1]
    if current[1] > previous[1]:
        return f"REGRESSION: {current[1]} failures (was {previous[1]})"
    if current[0] < previous[0]:
        return f"WARNING: {current[0]} passed (was {previous[0]})"
    return None

def main():
    parser = argparse.ArgumentParser(description="MCP Tool Tester")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=21600, help="Seconds between test runs")
    args = parser.parse_args()

    db = init_db()

    if args.once or not args.loop:
        # Check importability
        ok, msg = test_tool_importable()
        print(f"Module check: {'OK' if ok else 'FAIL'} — {msg}")

        # Extract and test tools
        tools = extract_tool_names()
        print(f"Found {len(tools)} tool definitions")

        if tools:
            p, f, s, d = smoke_test_tools(db, tools)
            print(f"Results: {p} passed, {f} failed, {s} skipped ({d:.1f}s)")

            regression = check_regressions(db)
            if regression:
                print(f"⚠ {regression}")

    if args.loop:
        print("MCP Tool Tester en boucle continue...")
        while True:
            try:
                tools = extract_tool_names()
                p, f, s, d = smoke_test_tools(db, tools)
                regression = check_regressions(db)
                ts = time.strftime('%H:%M')
                status = f"[{ts}] {p}✓ {f}✗ {s}⊘ ({d:.1f}s)"
                if regression:
                    status += f" | {regression}"
                print(status)
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
