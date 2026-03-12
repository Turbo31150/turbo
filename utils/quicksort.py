from __future__ import annotations


def quicksort(arr: list, *, key=None, reverse: bool = False) -> list:
    """Tri quicksort in-place optimise (median-of-three + insertion cutoff).

    - Median-of-three pivot → evite O(n²) sur donnees triees/inversees
    - Insertion sort sous 16 elements → moins d'overhead recursif
    - Tail-call manuelle → profondeur pile O(log n) garantie
    """
    if len(arr) <= 1:
        return arr
    if key is None:
        _quicksort_raw(arr, 0, len(arr) - 1, reverse)
    else:
        _quicksort(arr, 0, len(arr) - 1, key, reverse)
    return arr


_INSERTION_THRESHOLD = 16


def _insertion_sort(arr: list, lo: int, hi: int, key, reverse: bool) -> None:
    for i in range(lo + 1, hi + 1):
        val = arr[i]
        k = key(val)
        j = i - 1
        if reverse:
            while j >= lo and key(arr[j]) < k:
                arr[j + 1] = arr[j]
                j -= 1
        else:
            while j >= lo and key(arr[j]) > k:
                arr[j + 1] = arr[j]
                j -= 1
        arr[j + 1] = val


def _median_of_three(arr: list, lo: int, hi: int, key) -> int:
    mid = (lo + hi) >> 1
    a, b, c = key(arr[lo]), key(arr[mid]), key(arr[hi])
    if a <= b <= c or c <= b <= a:
        return mid
    if b <= a <= c or c <= a <= b:
        return lo
    return hi


def _partition(arr: list, lo: int, hi: int, key, reverse: bool) -> int:
    """Lomuto-like partition avec pivot en arr[lo]. Retourne index final du pivot."""
    pivot = key(arr[lo])
    i, j = lo + 1, hi
    if reverse:
        while True:
            while i <= j and key(arr[i]) >= pivot:
                i += 1
            while j > lo and key(arr[j]) < pivot:
                j -= 1
            if i > j:
                break
            arr[i], arr[j] = arr[j], arr[i]
            i += 1
            j -= 1
    else:
        while True:
            while i <= j and key(arr[i]) <= pivot:
                i += 1
            while j > lo and key(arr[j]) > pivot:
                j -= 1
            if i > j:
                break
            arr[i], arr[j] = arr[j], arr[i]
            i += 1
            j -= 1
    arr[lo], arr[j] = arr[j], arr[lo]
    return j


def _partition_raw(arr: list, lo: int, hi: int, reverse: bool) -> int:
    """Partition sans key — evite le cout d'appel de fonction par comparaison."""
    pivot = arr[lo]
    i, j = lo + 1, hi
    if reverse:
        while True:
            while i <= j and arr[i] >= pivot:
                i += 1
            while j > lo and arr[j] < pivot:
                j -= 1
            if i > j:
                break
            arr[i], arr[j] = arr[j], arr[i]
            i += 1
            j -= 1
    else:
        while True:
            while i <= j and arr[i] <= pivot:
                i += 1
            while j > lo and arr[j] > pivot:
                j -= 1
            if i > j:
                break
            arr[i], arr[j] = arr[j], arr[i]
            i += 1
            j -= 1
    arr[lo], arr[j] = arr[j], arr[lo]
    return j


def _quicksort(arr: list, lo: int, hi: int, key, reverse: bool) -> None:
    while hi - lo >= _INSERTION_THRESHOLD:
        pivot_idx = _median_of_three(arr, lo, hi, key)
        arr[lo], arr[pivot_idx] = arr[pivot_idx], arr[lo]
        j = _partition(arr, lo, hi, key, reverse)
        if j - lo < hi - j:
            _quicksort(arr, lo, j - 1, key, reverse)
            lo = j + 1
        else:
            _quicksort(arr, j + 1, hi, key, reverse)
            hi = j - 1
    if hi > lo:
        _insertion_sort(arr, lo, hi, key, reverse)


def _quicksort_raw(arr: list, lo: int, hi: int, reverse: bool) -> None:
    """Fast-path sans key — ~30% plus rapide sur types natifs."""
    while hi - lo >= _INSERTION_THRESHOLD:
        mid = (lo + hi) >> 1
        a, b, c = arr[lo], arr[mid], arr[hi]
        if a <= b <= c or c <= b <= a:
            pivot_idx = mid
        elif b <= a <= c or c <= a <= b:
            pivot_idx = lo
        else:
            pivot_idx = hi
        arr[lo], arr[pivot_idx] = arr[pivot_idx], arr[lo]
        j = _partition_raw(arr, lo, hi, reverse)
        if j - lo < hi - j:
            _quicksort_raw(arr, lo, j - 1, reverse)
            lo = j + 1
        else:
            _quicksort_raw(arr, j + 1, hi, reverse)
            hi = j - 1
    if hi > lo:
        # Insertion sort inline sans key
        for i in range(lo + 1, hi + 1):
            val = arr[i]
            j2 = i - 1
            if reverse:
                while j2 >= lo and arr[j2] < val:
                    arr[j2 + 1] = arr[j2]
                    j2 -= 1
            else:
                while j2 >= lo and arr[j2] > val:
                    arr[j2 + 1] = arr[j2]
                    j2 -= 1
            arr[j2 + 1] = val


if __name__ == "__main__":
    import random
    import time

    sizes = [1_000, 10_000, 100_000]
    for n in sizes:
        data = [random.randint(0, n) for _ in range(n)]
        copy1, copy2 = data[:], data[:]

        t0 = time.perf_counter()
        quicksort(copy1)
        t_qs = time.perf_counter() - t0

        t0 = time.perf_counter()
        copy2.sort()
        t_builtin = time.perf_counter() - t0

        assert copy1 == copy2, "Tri incorrect!"
        print(f"n={n:>7,} | quicksort: {t_qs:.4f}s | builtin: {t_builtin:.4f}s | ratio: {t_qs/t_builtin:.1f}x")
