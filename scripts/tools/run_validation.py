"""Run 50 validation cycles and save report."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.scenarios import run_50_cycles

report = run_50_cycles()

out = Path(__file__).resolve().parent / "data" / "validation_report.json"
out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

s = report["summary"]
print(f"\nRESULTAT: {s['total_passed']}/{s['total_tests']} ({s['global_pass_rate']}%)")
print(f"Echecs: {s['total_failed']}, Partiels: {s['total_partial']}")

if report["failures"]:
    print(f"\nSCENARIOS EN ECHEC ({len(report['failures'])}):")
    for name, info in sorted(report["failures"].items(), key=lambda x: -x[1]["count"]):
        print(f"  {name}: {info['count']}x — {info['details'][:100]}")
