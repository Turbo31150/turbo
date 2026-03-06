#!/usr/bin/env python3
"""JARVIS Auto Updater — Verification et mise a jour des composants."""
import json, sys, os, subprocess
from datetime import datetime

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT = "2010747443"
TURBO_DIR = "F:/BUREAU/turbo"
UV_BIN = "C:/Users/franc/.local/bin/uv.exe"

def send_telegram(msg):
    import urllib.request
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=10)
    except: pass

def run_cmd(cmd, cwd=None, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, shell=isinstance(cmd, str))
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def check_git_updates():
    ok, out, err = run_cmd(["git", "fetch", "--dry-run"], cwd=TURBO_DIR)
    ok2, out2, _ = run_cmd(["git", "log", "HEAD..origin/main", "--oneline"], cwd=TURBO_DIR)
    behind = len(out2.strip().split("\n")) if out2.strip() else 0
    ok3, branch, _ = run_cmd(["git", "branch", "--show-current"], cwd=TURBO_DIR)
    return {"branch": branch, "behind": behind, "has_updates": behind > 0}

def check_python_packages():
    ok, out, _ = run_cmd([UV_BIN, "pip", "list", "--outdated", "--format=json"], cwd=TURBO_DIR)
    if ok and out:
        try:
            packages = json.loads(out)
            return [{"name": p["name"], "current": p["version"], "latest": p["latest_version"]} for p in packages[:10]]
        except: pass
    return []

def check_ollama_version():
    ok, out, _ = run_cmd(["ollama", "--version"])
    return out if ok else "unknown"

def check_openclaw_version():
    ok, out, _ = run_cmd(["openclaw", "--version"])
    return out.strip() if ok else "unknown"

def check_all():
    report = {"ts": datetime.now().isoformat()}

    # Git
    git = check_git_updates()
    report["git"] = git

    # Packages
    packages = check_python_packages()
    report["outdated_packages"] = len(packages)
    report["packages"] = packages

    # Versions
    report["ollama"] = check_ollama_version()
    report["openclaw"] = check_openclaw_version()

    return report

def do_update():
    results = []
    # Git pull
    ok, out, err = run_cmd(["git", "pull", "--ff-only"], cwd=TURBO_DIR)
    results.append(f"Git pull: {'OK' if ok else 'FAIL'} {out[:60]}")

    # uv sync
    ok, out, _ = run_cmd([UV_BIN, "sync"], cwd=TURBO_DIR)
    results.append(f"UV sync: {'OK' if ok else 'FAIL'}")

    return results

if __name__ == "__main__":
    if "--check" in sys.argv:
        report = check_all()
        print(f"[AUTO UPDATER] {datetime.now().strftime('%H:%M')}")
        print(f"  Git: branch={report['git']['branch']}, behind={report['git']['behind']}")
        print(f"  Outdated packages: {report['outdated_packages']}")
        for p in report.get("packages", [])[:5]:
            print(f"    {p['name']}: {p['current']} -> {p['latest']}")
        print(f"  Ollama: {report['ollama']}")
        print(f"  OpenClaw: {report['openclaw']}")
        if report["git"]["has_updates"] or report["outdated_packages"]:
            print("\n  Updates available! Run --update to apply.")
        if "--notify" in sys.argv:
            send_telegram(f"[UPDATER] Git: {report['git']['behind']} behind | Packages: {report['outdated_packages']} outdated | Ollama: {report['ollama']}")

    elif "--update" in sys.argv:
        print("[AUTO UPDATER] Applying updates...")
        results = do_update()
        for r in results: print(f"  {r}")
        send_telegram("[UPDATER] " + " | ".join(results))

    elif "--history" in sys.argv:
        ok, out, _ = run_cmd(["git", "log", "--oneline", "-10"], cwd=TURBO_DIR)
        print(f"[GIT HISTORY]\n{out}")

    else:
        print("Usage: auto_updater.py --check [--notify] | --update | --history")
