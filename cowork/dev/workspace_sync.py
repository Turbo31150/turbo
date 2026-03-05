#!/usr/bin/env python3
"""JARVIS Workspace Sync — Verification et synchronisation du workspace COWORK."""
import json, sys, os, subprocess, glob
from datetime import datetime

DEV_DIR = "C:/Users/franc/.openclaw/workspace/dev"
TASKS_FILE = "C:/Users/franc/.openclaw/workspace/COWORK_TASKS.md"

def list_scripts():
    scripts = sorted(glob.glob(os.path.join(DEV_DIR, "*.py")))
    return [os.path.basename(s) for s in scripts]

def test_script(script_path):
    """Test a script with --help or common flags."""
    for flag in ["--help", "--stats", "--list", "--once"]:
        try:
            r = subprocess.run(["python", script_path, flag],
                              capture_output=True, text=True, timeout=15)
            if r.returncode == 0 and len(r.stdout) > 5:
                return True, flag, r.stdout[:100]
        except: pass
    return False, None, "No working flag found"

def check_all():
    scripts = list_scripts()
    results = []
    for name in scripts:
        path = os.path.join(DEV_DIR, name)
        size = os.path.getsize(path)
        ok, flag, output = test_script(path)
        results.append({"name": name, "size": size, "ok": ok, "flag": flag, "output": output[:60]})
    return results

def generate_report(results):
    ok_count = sum(1 for r in results if r["ok"])
    total = len(results)
    lines = [f"[WORKSPACE SYNC] {datetime.now().strftime('%H:%M')}"]
    lines.append(f"  Scripts: {total} | Working: {ok_count} | Failed: {total - ok_count}")
    lines.append(f"  Coverage: {round(ok_count/total*100) if total else 0}%\n")
    for r in results:
        status = "OK" if r["ok"] else "FAIL"
        size_kb = round(r["size"] / 1024, 1)
        lines.append(f"  [{status}] {r['name']} ({size_kb}KB)" + (f" — {r['flag']}" if r["ok"] else ""))
    return "\n".join(lines)

if __name__ == "__main__":
    if "--check" in sys.argv:
        results = check_all()
        report = generate_report(results)
        print(report)
    elif "--report" in sys.argv:
        results = check_all()
        report = generate_report(results)
        print(report)
        # Save
        with open(os.path.join(DEV_DIR, "sync_report.json"), "w") as f:
            json.dump({"ts": datetime.now().isoformat(), "results": results}, f, indent=2)
        print(f"\nReport saved to sync_report.json")
    elif "--list" in sys.argv:
        scripts = list_scripts()
        print(f"[WORKSPACE] {len(scripts)} scripts:")
        for s in scripts:
            size = round(os.path.getsize(os.path.join(DEV_DIR, s)) / 1024, 1)
            print(f"  {s} ({size}KB)")
    else:
        print("Usage: workspace_sync.py --check | --report | --list")
