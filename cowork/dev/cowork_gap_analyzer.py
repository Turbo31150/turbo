#!/usr/bin/env python3
"""cowork_gap_analyzer.py — Analyzes gaps in cowork script coverage.

Scans all cowork scripts, classifies them by category prefix (ia_, jarvis_,
win_, trading_, voice_, etc.) and reports which categories are underrepresented
compared to the overall distribution.

Usage:
    python dev/cowork_gap_analyzer.py --once
    python dev/cowork_gap_analyzer.py --once --min-scripts 3
    python dev/cowork_gap_analyzer.py --dry-run
"""
import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TURBO_DIR = SCRIPT_DIR.parent.parent
DATA_DIR = TURBO_DIR / "data"

# Known categories and their expected prefixes
CATEGORY_PREFIXES = {
    "ia": "IA / AI agents",
    "jarvis": "JARVIS core",
    "win": "Windows integration",
    "trading": "Trading pipeline",
    "voice": "Voice system",
    "cluster": "Cluster management",
    "cowork": "Cowork meta / orchestration",
    "dispatch": "Dispatch engine",
    "benchmark": "Benchmarking",
    "telegram": "Telegram bot",
    "workspace": "Workspace tools",
    "memory": "Memory management",
    "model": "Model management",
    "service": "Service monitoring",
    "performance": "Performance tools",
    "data": "Data pipeline",
    "process": "Process management",
}

# Expected minimum scripts per category for a well-covered system
EXPECTED_MIN = {
    "ia": 10,
    "jarvis": 8,
    "win": 8,
    "trading": 3,
    "voice": 2,
    "cluster": 2,
    "dispatch": 2,
    "benchmark": 2,
    "cowork": 2,
}


def classify_script(name: str) -> str:
    """Classify a script name into a category by prefix."""
    stem = Path(name).stem
    for prefix in sorted(CATEGORY_PREFIXES.keys(), key=len, reverse=True):
        if stem.startswith(prefix + "_"):
            return prefix
    return "other"


def scan_cowork_dirs() -> dict:
    """Scan all cowork subdirectories for .py scripts."""
    cowork_root = SCRIPT_DIR.parent  # cowork/
    results = {}
    for subdir in sorted(cowork_root.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith((".", "__")):
            scripts = sorted(p.name for p in subdir.glob("*.py") if p.is_file())
            if scripts:
                results[subdir.name] = scripts
    return results


def analyze_gaps(all_scripts: list, min_scripts: int = 2) -> dict:
    """Analyze category distribution and identify gaps."""
    category_counts = Counter()
    category_scripts = {}

    for script in all_scripts:
        cat = classify_script(script)
        category_counts[cat] += 1
        category_scripts.setdefault(cat, []).append(script)

    total = len(all_scripts)
    gaps = []
    well_covered = []

    for cat, expected in EXPECTED_MIN.items():
        actual = category_counts.get(cat, 0)
        if actual < min_scripts or actual < expected * 0.5:
            gaps.append({
                "category": cat,
                "description": CATEGORY_PREFIXES.get(cat, "Unknown"),
                "actual": actual,
                "expected_min": expected,
                "deficit": max(0, expected - actual),
                "severity": "critical" if actual == 0 else "warning",
            })
        else:
            well_covered.append({
                "category": cat,
                "description": CATEGORY_PREFIXES.get(cat, "Unknown"),
                "actual": actual,
                "expected_min": expected,
            })

    # Check for categories with zero representation
    for cat, desc in CATEGORY_PREFIXES.items():
        if cat not in category_counts and cat not in EXPECTED_MIN:
            gaps.append({
                "category": cat,
                "description": desc,
                "actual": 0,
                "expected_min": 1,
                "deficit": 1,
                "severity": "info",
            })

    gaps.sort(key=lambda g: (-g["deficit"], g["category"]))

    return {
        "total_scripts": total,
        "categories": dict(category_counts.most_common()),
        "category_scripts": category_scripts,
        "gaps": gaps,
        "well_covered": well_covered,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Analyze gaps in cowork script coverage"
    )
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Analyze without saving")
    parser.add_argument(
        "--min-scripts", type=int, default=2,
        help="Minimum scripts per category (default: 2)"
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    # Scan all cowork subdirectories
    dirs_scripts = scan_cowork_dirs()
    all_scripts = []
    for scripts in dirs_scripts.values():
        all_scripts.extend(scripts)

    # Analyze
    analysis = analyze_gaps(all_scripts, min_scripts=args.min_scripts)

    if args.json:
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
        sys.exit(0)

    # Human-readable output
    print(f"=== Cowork Gap Analysis ===")
    print(f"Scanned {len(dirs_scripts)} directories, {analysis['total_scripts']} scripts total")
    print()

    print("Category distribution:")
    for cat, count in sorted(analysis["categories"].items(), key=lambda x: -x[1]):
        desc = CATEGORY_PREFIXES.get(cat, "Other")
        print(f"  {cat:15s} : {count:3d} scripts  ({desc})")
    print()

    if analysis["gaps"]:
        print(f"GAPS FOUND ({len(analysis['gaps'])}):")
        for gap in analysis["gaps"]:
            icon = "!!" if gap["severity"] == "critical" else ".." if gap["severity"] == "info" else "**"
            print(
                f"  [{icon}] {gap['category']:15s} : {gap['actual']}/{gap['expected_min']} "
                f"(deficit {gap['deficit']}) — {gap['description']}"
            )
    else:
        print("No significant gaps found.")

    print()

    result = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "total_scripts": analysis["total_scripts"],
        "total_categories": len(analysis["categories"]),
        "gaps_found": len(analysis["gaps"]),
        "critical_gaps": sum(1 for g in analysis["gaps"] if g["severity"] == "critical"),
    }
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
