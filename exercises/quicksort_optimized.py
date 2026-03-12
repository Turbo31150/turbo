"""Quicksort optimise — median-of-three + insertion sort + 3-way partition."""
from __future__ import annotations


def quicksort(arr: list, *, key=None, reverse: bool = False) -> list:
    """Tri quicksort in-place optimise. Retourne la liste pour chainage."""
    if len(arr) <= 1:
        return arr
    _quicksort(arr, 0, len(arr) - 1, key=key, reverse=reverse)
    return arr


# --- seuil sous lequel insertion sort est plus rapide ---
_INSERTION_THRESHOLD = 16


def _insertion_sort(arr: list, lo: int, hi: int, *, key, reverse: bool) -> None:
    for i in range(lo + 1, hi + 1):
        tmp = arr[i]
        k = key(tmp) if key else tmp
        j = i - 1
        if reverse:
            while j >= lo and (key(arr[j]) if key else arr[j]) < k:
                arr[j + 1] = arr[j]
                j -= 1
        else:
            while j >= lo and (key(arr[j]) if key else arr[j]) > k:
                arr[j + 1] = arr[j]
                j -= 1
        arr[j + 1] = tmp


def _median_of_three(arr: list, lo: int, hi: int, *, key) -> int:
    """Retourne l'indice du pivot median(lo, mid, hi)."""
    mid = (lo + hi) >> 1
    a = key(arr[lo]) if key else arr[lo]
    b = key(arr[mid]) if key else arr[mid]
    c = key(arr[hi]) if key else arr[hi]
    if a <= b <= c or c <= b <= a:
        return mid
    if b <= a <= c or c <= a <= b:
        return lo
    return hi


def _quicksort(arr: list, lo: int, hi: int, *, key, reverse: bool) -> None:
    while lo < hi:
        # Petit sous-tableau → insertion sort
        if hi - lo < _INSERTION_THRESHOLD:
            _insertion_sort(arr, lo, hi, key=key, reverse=reverse)
            return

        # Pivot median-of-three
        pivot_idx = _median_of_three(arr, lo, hi, key=key)
        arr[lo], arr[pivot_idx] = arr[pivot_idx], arr[lo]
        pivot = key(arr[lo]) if key else arr[lo]

        # Partition 3-way (Dutch National Flag)
        lt, i, gt = lo, lo + 1, hi
        while i <= gt:
            val = key(arr[i]) if key else arr[i]
            if (val < pivot) ^ reverse:
                arr[lt], arr[i] = arr[i], arr[lt]
                lt += 1
                i += 1
            elif (val > pivot) ^ reverse:
                arr[i], arr[gt] = arr[gt], arr[i]
                gt -= 1
            else:
                i += 1

        # Recurse sur la plus petite partition, boucle sur la plus grande
        # (elimination de la tail recursion)
        if lt - lo < hi - gt:
            _quicksort(arr, lo, lt - 1, key=key, reverse=reverse)
            lo = gt + 1  # boucle while
        else:
            _quicksort(arr, gt + 1, hi, key=key, reverse=reverse)
            hi = lt - 1  # boucle while


# --------------- tests rapides ---------------
if __name__ == "__main__":
    import random
    import time

    sizes = [100, 1_000, 10_000, 100_000]
    for n in sizes:
        data = [random.randint(0, n // 2) for _ in range(n)]
        copy1, copy2 = data[:], data[:]

        t0 = time.perf_counter()
        quicksort(copy1)
        t_qs = time.perf_counter() - t0

        t0 = time.perf_counter()
        copy2.sort()
        t_builtin = time.perf_counter() - t0

        assert copy1 == copy2, f"ERREUR sur n={n}"
        print(f"n={n:>7,}  quicksort={t_qs:.4f}s  builtin={t_builtin:.4f}s  ratio={t_qs/t_builtin:.1f}x")

    # Test reverse + key
    words = ["banana", "apple", "cherry", "date", "elderberry"]
    quicksort(words, key=len, reverse=True)
    assert words == sorted(words, key=len, reverse=True)
    print("\nTests key+reverse OK")
    print("Tous les tests passes.")
