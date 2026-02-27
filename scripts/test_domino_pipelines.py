"""Validation et test du module domino_pipelines."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.domino_pipelines import DOMINO_PIPELINES, DOMINO_LEARNING_DATASET, get_domino_stats, find_domino

stats = get_domino_stats()
print("=" * 60)
print("DOMINO PIPELINES — VALIDATION")
print("=" * 60)

print(f"\n  Total dominos:      {stats['total_dominos']}")
print(f"  Total triggers:     {stats['total_triggers']}")
print(f"  Total steps:        {stats['total_steps']}")
print(f"  Learning examples:  {stats['learning_examples']}")
print(f"  Critical:           {stats['critical_count']}")
print(f"  High priority:      {stats['high_count']}")

print(f"\n  Categories:")
for cat, count in sorted(stats['categories'].items()):
    print(f"    {cat}: {count}")

print(f"\n{'=' * 60}")
print("FIND_DOMINO TESTS")
print("=" * 60)

tests = [
    "bonjour jarvis",
    "scan trading complet",
    "debug gpu chaud",
    "bonne nuit jarvis",
    "lance le stream",
    "backup complet",
    "hotfix urgent",
    "scan securite complet",
    "consensus cluster",
    "optimise les gpu",
    "verifie les alertes",
    "mode cafe code",
    "ferme tout trading",
    "pause dejeuner",
]

PASS = FAIL = 0
for t in tests:
    d = find_domino(t)
    if d:
        print(f"  [PASS] \"{t}\" -> {d.id} ({len(d.steps)} steps, {d.category})")
        PASS += 1
    else:
        print(f"  [FAIL] \"{t}\" -> NOT FOUND")
        FAIL += 1

print(f"\n{'=' * 60}")
print(f"RESULTATS: {PASS} PASS / {FAIL} FAIL")
print(f"Learning dataset: {len(DOMINO_LEARNING_DATASET)} examples prets pour fine-tuning")
print(f"{'=' * 60}")
