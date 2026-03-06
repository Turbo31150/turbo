#!/usr/bin/env python3
"""Validate all JARVIS voice scenarios — CI-ready, exit 0 on 100% pass."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import init_db, import_commands_from_code, import_skills_from_code, import_corrections_from_code
from src.scenarios import SCENARIO_TEMPLATES, _simulate_match


def main():
    init_db()
    import_commands_from_code()
    import_skills_from_code()
    import_corrections_from_code()

    mismatches = []
    passes = 0
    total = len(SCENARIO_TEMPLATES)

    for s in SCENARIO_TEMPLATES:
        matched, score, mtype = _simulate_match(s["voice_input"])
        if matched and matched in s["expected"]:
            passes += 1
        else:
            mismatches.append({
                "name": s["name"],
                "voice_input": s["voice_input"],
                "expected": s["expected"],
                "matched": matched,
                "score": round(score, 3),
            })

    rate = passes / total * 100 if total else 0
    print(f"Scenarios: {passes}/{total} pass ({rate:.1f}%)")

    if mismatches:
        print(f"\nMISMATCHES ({len(mismatches)}):")
        for m in mismatches:
            print(f"  {m['name']}: expected={m['expected']} got={m['matched']} score={m['score']}")
        sys.exit(1)
    else:
        print("All scenarios pass.")
        sys.exit(0)


if __name__ == "__main__":
    main()
