"""JARVIS Continuous Improvement Orchestrator.

Full automation pipeline:
1. Audit codebase
2. Auto-fix what can be fixed
3. Re-audit and compare
4. Generate report (JSON + Telegram)
5. Track history

Usage:
    python scripts/continuous_improve.py                  # Full cycle
    python scripts/continuous_improve.py --dry-run        # Preview fixes
    python scripts/continuous_improve.py --history         # Show improvement history
    python scripts/continuous_improve.py --report-telegram # Send last report to Telegram
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.auto_auditor import AutoAuditor
from src.auto_fixer import AutoFixer


def print_header(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def load_history() -> list[dict]:
    """Load improvement history."""
    history_path = ROOT / "data" / "improvement_history.json"
    if history_path.exists():
        return json.loads(history_path.read_text(encoding="utf-8"))
    return []


def save_history(entry: dict) -> None:
    """Append to improvement history."""
    history_path = ROOT / "data" / "improvement_history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history = load_history()
    history.append(entry)
    # Keep last 100 entries
    history = history[-100:]
    history_path.write_text(json.dumps(history, indent=2, default=str), encoding="utf-8")


def send_telegram(message: str) -> bool:
    """Send report to Telegram."""
    try:
        sys.path.insert(0, str(ROOT / "cowork" / "dev"))
        from _paths import TELEGRAM_TOKEN, TELEGRAM_CHAT
    except Exception:
        print("  [WARN] Could not load Telegram credentials")
        return False

    if not TELEGRAM_TOKEN:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = [message[i:i + 4000] for i in range(0, len(message), 4000)]
    for chunk in chunks:
        data = json.dumps({
            "chat_id": TELEGRAM_CHAT,
            "text": chunk,
            "parse_mode": "Markdown",
        }).encode()
        try:
            req = urllib.request.Request(url, data, {"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            print(f"  [ERR] Telegram: {e}")
            return False
    return True


def format_telegram_report(result: dict) -> str:
    """Format improvement result for Telegram."""
    lines = [
        "*JARVIS Auto-Improve Report*",
        f"Score: {result['before_score']} -> {result['after_score']} ({result['score_delta']:+d})",
        f"Fixes: {result['fixes_applied']}/{result['fixes_attempted']} applied",
    ]

    comp = result.get("comparison", {})
    if comp:
        lines.append(f"Findings: {comp.get('findings_before', '?')} -> {comp.get('findings_after', '?')}")
        lines.append(f"Critical: {comp.get('critical_before', 0)} -> {comp.get('critical_after', 0)}")

    lines.append(f"Duration: {result['duration_ms']}ms")

    if result.get("dry_run"):
        lines.append("_Mode: DRY RUN (no changes applied)_")

    return "\n".join(lines)


def run_full_cycle(dry_run: bool = False, telegram: bool = False) -> dict:
    """Run full improvement cycle."""
    print_header("JARVIS CONTINUOUS IMPROVEMENT")
    if dry_run:
        print("  Mode: DRY RUN (no changes)")

    t0 = time.monotonic()

    # 1. Run auto-fixer cycle (includes audit + fix + re-audit)
    print("\n  Phase 1: Audit + Fix cycle...", flush=True)
    fixer = AutoFixer()
    result = fixer.run_fix_cycle(dry_run=dry_run)

    print(f"\n  Score: {result['before_score']} -> {result['after_score']} ({result['score_delta']:+d})")
    print(f"  Fixes: {result['fixes_applied']}/{result['fixes_attempted']} applied")

    # Show applied fixes
    applied = [f for f in result["fixes"] if f["applied"]]
    if applied:
        print(f"\n  Applied fixes ({len(applied)}):")
        for f in applied[:20]:
            name = Path(f["file"]).name
            print(f"    - {name}: {f['type']} — {f['message']}")

    # Show flagged long functions
    flagged = [f for f in result["fixes"] if f["type"] == "flag_long_functions" and f["applied"]]
    if flagged:
        print(f"\n  Long functions flagged ({len(flagged)}):")
        for f in flagged[:10]:
            name = Path(f["file"]).name
            print(f"    - {name}: {f['message'][:80]}")

    # 2. Save history
    entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "before_score": result["before_score"],
        "after_score": result["after_score"],
        "score_delta": result["score_delta"],
        "fixes_applied": result["fixes_applied"],
        "fixes_attempted": result["fixes_attempted"],
        "dry_run": dry_run,
    }
    save_history(entry)

    # 3. Save detailed report
    report_dir = ROOT / "data" / "improvement_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"improve_{ts}.json"
    report_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\n  Report saved: {report_path}")

    # 4. Telegram
    if telegram:
        print("  Sending to Telegram...", end=" ", flush=True)
        msg = format_telegram_report(result)
        ok = send_telegram(msg)
        print("OK" if ok else "FAILED")

    total_ms = int((time.monotonic() - t0) * 1000)
    print_header("DONE")
    print(f"  Total: {total_ms}ms")

    return result


def show_history() -> None:
    """Show improvement history."""
    history = load_history()
    if not history:
        print("  No improvement history found.")
        return

    print_header("IMPROVEMENT HISTORY")
    print(f"  {'Date':<20} {'Before':>8} {'After':>8} {'Delta':>8} {'Fixes':>8}")
    print(f"  {'-'*56}")

    for entry in history[-20:]:
        ts = entry.get("timestamp", "?")[:19]
        before = entry.get("before_score", 0)
        after = entry.get("after_score", 0)
        delta = entry.get("score_delta", 0)
        fixes = entry.get("fixes_applied", 0)
        dry = " (dry)" if entry.get("dry_run") else ""
        print(f"  {ts:<20} {before:>8} {after:>8} {delta:>+8} {fixes:>8}{dry}")

    # Trend
    if len(history) >= 2:
        first = history[0].get("after_score", 0)
        last = history[-1].get("after_score", 0)
        total_delta = last - first
        print(f"\n  Overall trend: {first} -> {last} ({total_delta:+d} over {len(history)} cycles)")


def main():
    parser = argparse.ArgumentParser(description="JARVIS Continuous Improvement")
    parser.add_argument("--dry-run", action="store_true", help="Preview without applying")
    parser.add_argument("--history", action="store_true", help="Show improvement history")
    parser.add_argument("--telegram", action="store_true", help="Send report to Telegram")
    parser.add_argument("--report-telegram", action="store_true", help="Send last report to Telegram")
    args = parser.parse_args()

    if args.history:
        show_history()
        return

    if args.report_telegram:
        report_dir = ROOT / "data" / "improvement_reports"
        reports = sorted(report_dir.glob("improve_*.json")) if report_dir.exists() else []
        if not reports:
            print("  No improvement reports found.")
            return
        result = json.loads(reports[-1].read_text())
        msg = format_telegram_report(result)
        send_telegram(msg)
        print("  Sent to Telegram.")
        return

    run_full_cycle(dry_run=args.dry_run, telegram=args.telegram)


if __name__ == "__main__":
    main()
