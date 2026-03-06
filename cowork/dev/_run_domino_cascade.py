#!/usr/bin/env python3
"""Run a cascade of dominos sequentially, report results via Telegram."""
import sys, json, os, time, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from _paths import TELEGRAM_TOKEN, TELEGRAM_CHAT

def send_telegram(text):
    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT, "text": text[:4000]}).encode()
    try:
        req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data)
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

def run_domino(name):
    from src.domino_pipelines import find_domino, DOMINO_PIPELINES
    from src.domino_executor import DominoExecutor
    # Try exact ID match first, then search
    dp = next((d for d in DOMINO_PIPELINES if d.id == name), None)
    if not dp:
        dp = find_domino(name)
    if not dp:
        return {"name": name, "success": False, "error": "not found"}
    start = time.time()
    try:
        executor = DominoExecutor()
        result = executor.run(dp)
        return {
            "name": name,
            "success": result.get("success", False),
            "passed": result.get("passed", 0),
            "failed": result.get("failed", 0),
            "duration_s": round(time.time() - start, 1),
        }
    except Exception as e:
        return {"name": name, "success": False, "error": str(e)[:100], "duration_s": round(time.time() - start, 1)}

def main():
    domino_names = sys.argv[1:]
    if not domino_names:
        print("Usage: _run_domino_cascade.py <domino1> [domino2] ...")
        sys.exit(1)

    results = []
    for name in domino_names:
        r = run_domino(name)
        results.append(r)

    ok = sum(1 for r in results if r.get("success"))
    total = len(results)
    total_dur = sum(r.get("duration_s", 0) for r in results)

    lines = [f"[CASCADE] {ok}/{total} dominos OK ({total_dur:.0f}s)"]
    for r in results:
        icon = "+" if r.get("success") else "-"
        detail = f'{r.get("passed",0)}OK/{r.get("failed",0)}KO' if r.get("success") else r.get("error", "?")
        lines.append(f"  {icon} {r['name']} ({r.get('duration_s',0):.0f}s) {detail}")

    report = "\n".join(lines)
    print(report)
    send_telegram(report)

    out = {"cascade": domino_names, "ok": ok, "total": total, "duration_s": total_dur, "results": results}
    print(json.dumps(out))

    if ok < total:
        sys.exit(1)

if __name__ == "__main__":
    main()
