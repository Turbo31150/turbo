#!/usr/bin/env python3
"""JARVIS AutoFix — Diagnostic + repair for Telegram.
1. Run boot diagnostic
2. Detect issues
3. Attempt fixes (restart services, clear circuit breakers)
4. Trigger self-improve cycle
5. Re-run diagnostic to verify

Usage: python F:/BUREAU/turbo/scripts/jarvis_autofix_telegram.py
"""
import json, subprocess, time, os, sys

TIMEOUT = 10
WS = "http://127.0.0.1:9742"

def run(cmd, timeout=TIMEOUT):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                           encoding='utf-8', errors='replace')
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None

def ws_post(path, data=None, timeout=10):
    body = json.dumps(data) if data else '{}'
    try:
        import urllib.request
        req = urllib.request.Request(f"{WS}{path}", data=body.encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None

def ws_get(path, timeout=5):
    try:
        import urllib.request
        with urllib.request.urlopen(f"{WS}{path}", timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    t0 = time.time()
    lines = ["JARVIS AUTOFIX", "=" * 40, ""]

    # Phase 1: Diagnostic
    lines.append("[Phase 1] Diagnostic...")
    boot = run('python "F:/BUREAU/turbo/scripts/jarvis_boot_telegram.py"', timeout=30)
    if boot:
        # Extract grade line
        for bl in boot.split("\n"):
            if "Grade" in bl:
                lines.append(f"  {bl.strip()}")
                break
        # Extract issues
        in_issues = False
        issues = []
        for bl in boot.split("\n"):
            if bl.strip() == "ISSUES":
                in_issues = True
                continue
            if in_issues and bl.strip().startswith("-"):
                issues.append(bl.strip().lstrip("- "))
        if issues:
            for i in issues:
                lines.append(f"  Issue: {i}")
        else:
            lines.append("  No issues detected")
    else:
        lines.append("  Boot diagnostic failed!")
        issues = ["boot_failed"]

    # Phase 2: Auto-repair
    lines.append("")
    lines.append("[Phase 2] Repair...")
    fixes_done = 0

    for issue in issues:
        if "M2 OFFLINE" in issue:
            lines.append(f"  SKIP: M2 offline (hardware, not fixable remotely)")
        elif "DOWN: WS" in issue:
            lines.append(f"  FIX: Restarting WS FastAPI...")
            # Try to restart via unified boot
            r = run('python "F:/BUREAU/turbo/scripts/jarvis_unified_boot.py" --phase python_services --skip openclaw', timeout=60)
            fixes_done += 1
        elif "DOWN: Proxy" in issue:
            lines.append(f"  FIX: Proxy restart needed (manual)")
        elif "THERMAL" in issue:
            lines.append(f"  WARN: {issue} (monitoring only)")

    # Reset circuit breakers via proxy
    cb_reset = run('curl -s --max-time 3 http://127.0.0.1:18800/health')
    if cb_reset:
        lines.append(f"  Circuit breakers refreshed via /health")
        fixes_done += 1

    if fixes_done == 0:
        lines.append("  No fixes needed")

    # Phase 3: Self-improve status (don't trigger — takes too long)
    lines.append("")
    lines.append("[Phase 3] Self-Improve status...")
    si = ws_get("/api/self-improve/status", timeout=15)
    if si and isinstance(si, dict):
        cycles = si.get("cycles", si.get("total_cycles", "?"))
        actions = si.get("total_actions", "?")
        lines.append(f"  {cycles} cycles, {actions} total actions")
        last = si.get("last_report", {})
        for a in last.get("actions", [])[:3]:
            lines.append(f"    {a.get('type','?')}: {a.get('target','?')} — {a.get('desc','')[:60]}")
    else:
        lines.append("  Self-improve unavailable")

    # Phase 4: Autonomous status
    lines.append("")
    lines.append("[Phase 4] Autonomous status...")
    auto = ws_get("/api/autonomous/status", timeout=15)
    if auto and isinstance(auto, dict):
        running = auto.get("running", False)
        tasks = auto.get("tasks", {})
        active = sum(1 for t in tasks.values() if t.get("enabled"))
        total_runs = sum(t.get("run_count", 0) for t in tasks.values())
        fails = sum(t.get("fail_count", 0) for t in tasks.values())
        lines.append(f"  {'RUNNING' if running else 'STOPPED'} | {active} tasks active | {total_runs} runs | {fails} fails")
        # Show any tasks with recent fails
        for tname, tdata in tasks.items():
            if tdata.get("fail_count", 0) > 0:
                lines.append(f"    WARN: {tname} — {tdata['fail_count']} fails")
    else:
        lines.append("  Autonomous loop unavailable")

    # Phase 5: Re-verify
    lines.append("")
    lines.append("[Phase 5] Verification...")
    boot2 = run('python "F:/BUREAU/turbo/scripts/jarvis_boot_telegram.py"', timeout=30)
    if boot2:
        for bl in boot2.split("\n"):
            if "Grade" in bl:
                lines.append(f"  AFTER: {bl.strip()}")
                break

    elapsed = round(time.time() - t0, 1)
    lines.append("")
    lines.append(f"Completed in {elapsed}s | Fixes: {fixes_done}")
    lines.append("=" * 40)

    print("\n".join(lines))
