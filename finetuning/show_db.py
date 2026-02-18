"""Affiche le contenu de la DB memoire_finetuning."""
import sqlite3

conn = sqlite3.connect("F:/BUREAU/turbo/finetuning/memoire_finetuning.db")

tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("=== memoire_finetuning.db ===")
print(f"Tables: {len(tables)}")
for (t,) in tables:
    count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t}: {count} rows")

print("\n=== Runs ===")
for r in conn.execute("SELECT id, run_name, status, notes FROM runs").fetchall():
    print(f"  #{r[0]}: {r[1]} [{r[2]}]")
    if r[3]:
        print(f"    Notes: {r[3]}")

print("\n=== Erreurs documentees ===")
for e in conn.execute("SELECT error_type, fix_applied FROM errors").fetchall():
    fix = str(e[1])[:70]
    print(f"  {e[0]}: {fix}")

print("\n=== Patches ===")
for p in conn.execute("SELECT patch_name, target_library, still_needed FROM patches").fetchall():
    print(f"  {p[0]} ({p[1]}) [needed: {bool(p[2])}]")

print("\n=== Datasets ===")
for d in conn.execute("SELECT dataset_type, num_examples, file_size_mb FROM datasets").fetchall():
    print(f"  {d[0]}: {d[1]} exemples ({d[2]} MB)")

print("\n=== Modeles disponibles ===")
for m in conn.execute("SELECT model_name, category FROM model_benchmarks ORDER BY category").fetchall():
    print(f"  [{m[1]}] {m[0]}")

conn.close()
