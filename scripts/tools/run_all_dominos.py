"""Execute TOUTES les cascades domino en parallele par categorie via le DominoExecutor."""
import sys, os, time, json
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.domino_executor import DominoExecutor
from src.domino_pipelines import DOMINO_PIPELINES

# Group dominos by category
categories = {}
for dp in DOMINO_PIPELINES:
    categories.setdefault(dp.category, []).append(dp)

print("=" * 70)
print(f"DOMINO EXECUTOR — ALL {len(DOMINO_PIPELINES)} CASCADES / {len(categories)} CATEGORIES")
print("=" * 70)
for cat, dps in sorted(categories.items()):
    print(f"  {cat}: {len(dps)} dominos")
print()

START = time.time()

def run_category(cat, dominos):
    """Execute tous les dominos d'une categorie."""
    executor = DominoExecutor()
    results = []
    for dp in dominos:
        r = executor.run(dp)
        results.append(r)
    return cat, results

# Launch all categories in parallel (1 thread per category)
all_results = {}
with ThreadPoolExecutor(max_workers=len(categories)) as pool:
    futures = {pool.submit(run_category, cat, dps): cat for cat, dps in categories.items()}
    for future in as_completed(futures):
        cat, results = future.result()
        all_results[cat] = results

elapsed = time.time() - START

# Final report
print("\n" + "=" * 70)
print("RAPPORT FINAL — TOUTES CATEGORIES")
print("=" * 70)

total_pass = total_fail = total_skip = total_runs = 0
for cat in sorted(all_results):
    results = all_results[cat]
    cat_pass = sum(r["passed"] for r in results)
    cat_fail = sum(r["failed"] for r in results)
    cat_skip = sum(r["skipped"] for r in results)
    cat_ms = sum(r["total_ms"] for r in results)
    total_pass += cat_pass
    total_fail += cat_fail
    total_skip += cat_skip
    total_runs += len(results)
    status = "OK" if cat_fail == 0 else "WARN"
    print(f"  [{status}] {cat:25s} {len(results)} runs | {cat_pass} PASS / {cat_fail} FAIL / {cat_skip} SKIP | {cat_ms:.0f}ms")

print(f"\n  {'=' * 60}")
print(f"  TOTAL: {total_runs} cascades executees")
print(f"  PASS: {total_pass} | FAIL: {total_fail} | SKIP: {total_skip}")
print(f"  Temps total: {elapsed:.1f}s (parallelise)")
print(f"  Score: {total_pass}/{total_pass+total_fail} ({100*total_pass/(total_pass+total_fail):.1f}%)" if total_pass+total_fail > 0 else "")
print(f"  {'=' * 60}")
