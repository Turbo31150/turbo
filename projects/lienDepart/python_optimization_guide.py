"""
Python Optimization Guide
=========================
Benchmark comparatif de techniques d'optimisation Python.
Chaque section presente une version naive (avant) et une version optimisee (apres).

Usage:
    python python_optimization_guide.py
"""

import time
import cProfile
import io
import pstats
import sys
import math
import random
import string
import asyncio
import concurrent.futures
from functools import lru_cache
from typing import Callable, Any

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

RESULTS: list[dict] = []
SEPARATOR = "+" + "-" * 31 + "+" + "-" * 12 + "+" + "-" * 12 + "+" + "-" * 9 + "+"
HEADER    = "| {:<29} | {:>10} | {:>10} | {:>7} |".format(
    "Technique", "Avant (ms)", "Apres (ms)", "Speedup"
)

# ---------------------------------------------------------------------------
# Decorator @benchmark
# ---------------------------------------------------------------------------

def benchmark(label: str, runs: int = 3) -> Callable:
    """Mesure le temps d'execution median sur `runs` repetitions (perf_counter_ns)."""
    def decorator(fn: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            times = []
            result = None
            for _ in range(runs):
                t0 = time.perf_counter_ns()
                result = fn(*args, **kwargs)
                t1 = time.perf_counter_ns()
                times.append(t1 - t0)
            times.sort()
            median_ns = times[runs // 2]
            wrapper._benchmark_ns = median_ns
            wrapper._benchmark_label = label
            return result
        wrapper._benchmark_ns = 0
        wrapper._benchmark_label = label
        return wrapper
    return decorator


def record(technique: str, before_ns: int, after_ns: int) -> None:
    """Enregistre une paire avant/apres dans RESULTS."""
    before_ms = before_ns / 1_000_000
    after_ms  = after_ns  / 1_000_000
    speedup   = before_ms / after_ms if after_ms > 0 else float("inf")
    RESULTS.append({
        "technique": technique,
        "before_ms": before_ms,
        "after_ms":  after_ms,
        "speedup":   speedup,
    })
    print(f"  [OK] {technique}: {before_ms:.2f} ms -> {after_ms:.2f} ms  ({speedup:.1f}x)")


# ---------------------------------------------------------------------------
# Section 1: Profiling avec cProfile
# ---------------------------------------------------------------------------

def _target_for_profiling() -> float:
    """Fonction cible utilisee pour la demo de profiling."""
    total = 0.0
    for i in range(1, 50_001):
        total += math.sqrt(i) * math.log(i)
    return total


def demo_profiling() -> None:
    """Montre l'usage programmatique de cProfile."""
    print("\n--- Section Profiling (cProfile) ---")
    buf = io.StringIO()
    pr  = cProfile.Profile()
    pr.enable()
    _target_for_profiling()
    pr.disable()
    ps = pstats.Stats(pr, stream=buf).sort_stats("cumulative")
    ps.print_stats(5)
    lines = buf.getvalue().splitlines()
    for line in lines[:20]:
        print("  ", line)
    print("  [INFO] Profiling illustratif uniquement — pas de paire avant/apres.")


# ---------------------------------------------------------------------------
# Section 2: Vectorisation (NumPy optionnel)
# ---------------------------------------------------------------------------

def demo_vectorisation() -> None:
    """Somme des carres de 1 000 000 nombres: boucle for vs NumPy."""
    print("\n--- Section Vectorisation ---")
    N = 1_000_000

    try:
        import numpy as np
    except ImportError:
        print("  [SKIP] NumPy non installe — section ignoree.")
        return

    data_list = list(range(N))
    data_np   = np.arange(N, dtype=np.float64)

    @benchmark("Vectorisation - boucle for")
    def before() -> float:
        return sum(x * x for x in data_list)

    @benchmark("Vectorisation - NumPy")
    def after() -> float:
        return float(np.sum(data_np ** 2))

    before()
    after()
    record("Vectorisation NumPy", before._benchmark_ns, after._benchmark_ns)


# ---------------------------------------------------------------------------
# Section 3: Structures de donnees — list 'in' O(n) vs set intersection O(1)
# ---------------------------------------------------------------------------

def demo_structures() -> None:
    """Recherche d'elements communs: iterations avec 'in list' vs set intersection."""
    print("\n--- Section Structures de donnees ---")
    N = 50_000
    universe = list(range(N * 2))
    random.shuffle(universe)
    list_a = universe[:N]
    list_b = universe[N:]
    set_a  = set(list_a)
    set_b  = set(list_b)

    @benchmark("Structures - list in (O(n^2))")
    def before() -> list:
        return [x for x in list_a if x in list_b]

    @benchmark("Structures - set intersection (O(n))")
    def after() -> set:
        return set_a & set_b

    before()
    after()
    record("Set vs List lookup", before._benchmark_ns, after._benchmark_ns)


# ---------------------------------------------------------------------------
# Section 4: Caching — Fibonacci naif vs lru_cache
# ---------------------------------------------------------------------------

def demo_caching() -> None:
    """Fibonacci recursif naif vs memoisation avec lru_cache."""
    print("\n--- Section Caching (lru_cache) ---")
    N = 35

    def fib_naive(n: int) -> int:
        if n <= 1:
            return n
        return fib_naive(n - 1) + fib_naive(n - 2)

    @lru_cache(maxsize=None)
    def fib_cached(n: int) -> int:
        if n <= 1:
            return n
        return fib_cached(n - 1) + fib_cached(n - 2)

    @benchmark("Caching - Fibonacci naif")
    def before() -> int:
        return fib_naive(N)

    @benchmark("Caching - Fibonacci lru_cache")
    def after() -> int:
        fib_cached.cache_clear()
        return fib_cached(N)

    before()
    after()
    record("Fibonacci lru_cache", before._benchmark_ns, after._benchmark_ns)


# ---------------------------------------------------------------------------
# Section 5: Generateurs vs listes en memoire
# ---------------------------------------------------------------------------

def demo_generators() -> None:
    """Pipeline de traitement: liste complete en memoire vs generateurs."""
    print("\n--- Section Generateurs ---")
    N = 2_000_000

    @benchmark("Generateurs - liste en memoire")
    def before() -> float:
        data    = list(range(N))
        evens   = [x for x in data if x % 2 == 0]
        squares = [x * x for x in evens]
        return sum(squares)

    @benchmark("Generateurs - pipeline generateurs")
    def after() -> float:
        data    = range(N)
        evens   = (x for x in data if x % 2 == 0)
        squares = (x * x for x in evens)
        return sum(squares)

    before()
    after()
    record("Pipeline generateurs", before._benchmark_ns, after._benchmark_ns)


# ---------------------------------------------------------------------------
# Section 6: I/O Async — simulation sans reseau
# ---------------------------------------------------------------------------

def demo_async() -> None:
    """Taches I/O simulees: sequentiel vs asyncio.gather()."""
    print("\n--- Section I/O Async (simulation) ---")
    TASKS   = 20
    DELAY_S = 0.02  # 20 ms par tache

    async def _fake_io(duration: float) -> float:
        await asyncio.sleep(duration)
        return duration

    @benchmark("Async - sequentiel")
    def before() -> float:
        async def run_seq() -> float:
            total = 0.0
            for _ in range(TASKS):
                total += await _fake_io(DELAY_S)
            return total
        return asyncio.run(run_seq())

    @benchmark("Async - asyncio.gather")
    def after() -> float:
        async def run_gather() -> float:
            results = await asyncio.gather(*[_fake_io(DELAY_S) for _ in range(TASKS)])
            return sum(results)
        return asyncio.run(run_gather())

    before()
    after()
    record("asyncio.gather vs sequentiel", before._benchmark_ns, after._benchmark_ns)


# ---------------------------------------------------------------------------
# Section 7: Multiprocessing — CPU-bound sequentiel vs ProcessPoolExecutor
# ---------------------------------------------------------------------------

def _heavy_cpu(n: int) -> float:
    """Calcul CPU intensif: somme des racines carrees."""
    return sum(math.sqrt(i) for i in range(n))


def demo_multiprocessing() -> None:
    """Calcul CPU-bound: boucle sequentielle vs ProcessPoolExecutor."""
    print("\n--- Section Multiprocessing ---")
    CHUNKS    = 8
    CHUNK_SZ  = 50_000

    @benchmark("Multiprocessing - sequentiel")
    def before() -> float:
        return sum(_heavy_cpu(CHUNK_SZ) for _ in range(CHUNKS))

    @benchmark("Multiprocessing - ProcessPoolExecutor")
    def after() -> float:
        with concurrent.futures.ProcessPoolExecutor() as executor:
            futures = [executor.submit(_heavy_cpu, CHUNK_SZ) for _ in range(CHUNKS)]
            return sum(f.result() for f in futures)

    before()
    after()
    if after._benchmark_ns > 0:
        record("ProcessPoolExecutor CPU-bound", before._benchmark_ns, after._benchmark_ns)
    else:
        print("  [INFO] Multiprocessing: mesure invalide, resultat ignore.")


# ---------------------------------------------------------------------------
# Section 8: Strings — concatenation += vs ''.join()
# ---------------------------------------------------------------------------

def demo_strings() -> None:
    """Construction de chaine: += iteratif vs ''.join()."""
    print("\n--- Section Strings ---")
    N    = 10_000
    WORD = "hello"

    @benchmark("Strings - concatenation +=")
    def before() -> str:
        result = ""
        for _ in range(N):
            result += WORD
        return result

    @benchmark("Strings - join()")
    def after() -> str:
        return "".join(WORD for _ in range(N))

    before()
    after()
    record("String join vs +=", before._benchmark_ns, after._benchmark_ns)


# ---------------------------------------------------------------------------
# Affichage du tableau recapitulatif
# ---------------------------------------------------------------------------

def print_summary() -> None:
    """Affiche le tableau ASCII comparatif de toutes les mesures."""
    print("\n")
    print(SEPARATOR)
    print(HEADER)
    print(SEPARATOR)
    for r in RESULTS:
        name_col    = r["technique"][:29]
        before_col  = f"{r['before_ms']:>10.2f}"
        after_col   = f"{r['after_ms']:>10.2f}"
        speedup_val = r["speedup"]
        if speedup_val == float("inf"):
            speedup_col = "    inf "
        else:
            speedup_col = f"{speedup_val:>6.1f}x"
        print(f"| {name_col:<29} | {before_col} | {after_col} | {speedup_col} |")
    print(SEPARATOR)
    if RESULTS:
        avg_speedup = sum(
            r["speedup"] for r in RESULTS if r["speedup"] != float("inf")
        ) / max(1, sum(1 for r in RESULTS if r["speedup"] != float("inf")))
        print(f"  Speedup moyen (hors inf): {avg_speedup:.1f}x\n")


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------

def main() -> None:
    """Execute toutes les demonstrations et affiche le bilan."""
    print("=" * 60)
    print("  Python Optimization Guide — Benchmark comparatif")
    print(f"  Python {sys.version.split()[0]}  |  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    demo_profiling()
    demo_vectorisation()
    demo_structures()
    demo_caching()
    demo_generators()
    demo_async()
    demo_multiprocessing()
    demo_strings()

    print_summary()


if __name__ == "__main__":
    main()
