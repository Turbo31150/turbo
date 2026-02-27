"""Test live du DominoExecutor — execute les cascades via le moteur complet."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.domino_executor import DominoExecutor
from src.domino_pipelines import DOMINO_PIPELINES

executor = DominoExecutor()

# Test 1: Execution par phrase vocale
print("\n" + "=" * 60)
print("TEST 1: Execution par phrase vocale")
print("=" * 60)
executor.run_by_voice("bonjour jarvis")
executor.run_by_voice("debug cluster")
executor.run_by_voice("scan securite complet")
executor.run_by_voice("backup rapide")
executor.run_by_voice("performance systeme")

# Test 2: Phrase inconnue
print("\n" + "=" * 60)
print("TEST 2: Phrase inconnue")
print("=" * 60)
executor.run_by_voice("fait moi un sandwich")

# Resume final
print("\n" + "=" * 60)
print("RESUME FINAL")
print("=" * 60)
results = executor.get_all_results()
print(f"  Runs: {results['runs']}")
print(f"  Total: {results['total_pass']} PASS / {results['total_fail']} FAIL / {results['total_skip']} SKIP")
print(f"  Temps: {results['total_ms']:.0f}ms")
for r in results["details"]:
    print(f"    {r['domino_id']}: {r['passed']}/{r['total_steps']} PASS ({r['total_ms']:.0f}ms)")
