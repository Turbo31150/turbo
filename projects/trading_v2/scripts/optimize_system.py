"""
OPTIMIZE SYSTEM v1.0 - Audit, Doublons, Autocompilation (V3.6 Phase 4)
1. Detecte les fonctions dupliquees entre scripts .py
2. Analyse command_history: commandes en echec > 50%
3. Autocompilation: identifie commandes similaires -> propose macros generiques

Usage:
  python optimize_system.py                # Audit complet
  python optimize_system.py --duplicates   # Doublons seulement
  python optimize_system.py --failures     # Commandes en echec
  python optimize_system.py --autocompile  # Propositions de macros
"""
import os
import sys
import re
import ast
import sqlite3
import json
import argparse
from collections import defaultdict, Counter
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"/home/turbo\TRADING_V2_PRODUCTION"
DB_PATH = os.path.join(ROOT, "database", "trading.db")
SCAN_DIRS = [
    os.path.join(ROOT, "scripts"),
    os.path.join(ROOT, "voice_system"),
]


# ============================================================
# PHASE 1: DETECTION DOUBLONS
# ============================================================

def scan_functions(directory):
    """Extrait toutes les fonctions def de tous les .py d'un dossier"""
    functions = {}  # name -> [(file, lineno, args, body_hash)]

    for dirpath, _, filenames in os.walk(directory):
        for fname in filenames:
            if not fname.endswith(".py") or fname.startswith("__"):
                continue
            filepath = os.path.join(dirpath, fname)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    source = f.read()
                tree = ast.parse(source, filename=filepath)
            except (SyntaxError, Exception):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    name = node.name
                    args = [a.arg for a in node.args.args]
                    # Hash du body pour detecter les corps identiques
                    body_src = ast.dump(node)
                    body_hash = hash(body_src)

                    if name not in functions:
                        functions[name] = []
                    functions[name].append({
                        "file": os.path.relpath(filepath, ROOT),
                        "line": node.lineno,
                        "args": args,
                        "hash": body_hash,
                    })

    return functions


def scan_imports(directory):
    """Detecte les imports inutilises (import fait mais jamais reference)"""
    issues = []

    for dirpath, _, filenames in os.walk(directory):
        for fname in filenames:
            if not fname.endswith(".py") or fname.startswith("__"):
                continue
            filepath = os.path.join(dirpath, fname)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    source = "".join(lines)
            except Exception:
                continue

            # Trouver les imports simples
            for i, line in enumerate(lines, 1):
                m = re.match(r"^import (\w+)", line.strip())
                if m:
                    mod = m.group(1)
                    # Verifier si le module est utilise apres l'import
                    rest = "".join(lines[i:])
                    if mod not in rest:
                        issues.append({
                            "file": os.path.relpath(filepath, ROOT),
                            "line": i,
                            "import": mod,
                            "type": "unused_import",
                        })

    return issues


def find_duplicates():
    """Trouve les fonctions dupliquees entre fichiers"""
    print("\n  === DETECTION DOUBLONS ===")

    all_functions = {}
    for d in SCAN_DIRS:
        if os.path.exists(d):
            funcs = scan_functions(d)
            for name, entries in funcs.items():
                if name not in all_functions:
                    all_functions[name] = []
                all_functions[name].extend(entries)

    # Aussi scanner la racine
    for fname in os.listdir(ROOT):
        if fname.endswith(".py"):
            funcs = scan_functions(ROOT)
            for name, entries in funcs.items():
                if name not in all_functions:
                    all_functions[name] = []
                all_functions[name].extend(entries)
            break

    duplicates = []
    identical = []

    for name, entries in all_functions.items():
        if name.startswith("_") and len(name) <= 3:
            continue  # Skip __init__ etc

        files = set(e["file"] for e in entries)
        if len(files) > 1:
            # Meme nom dans plusieurs fichiers
            duplicates.append((name, entries))

            # Verifier si le corps est identique
            hashes = set(e["hash"] for e in entries)
            if len(hashes) == 1:
                identical.append((name, entries))

    # Rapport
    print(f"  Total fonctions scannees: {sum(len(v) for v in all_functions.values())}")
    print(f"  Noms uniques: {len(all_functions)}")
    print(f"  Doublons (meme nom, fichiers differents): {len(duplicates)}")
    print(f"  Identiques (meme nom + meme corps): {len(identical)}")

    if duplicates:
        print(f"\n  Doublons detectes:")
        for name, entries in duplicates[:15]:
            locs = ", ".join(f"{e['file']}:{e['line']}" for e in entries)
            is_identical = any(name == n for n, _ in identical)
            tag = " [IDENTIQUE]" if is_identical else ""
            print(f"    {name}(){tag} -> {locs}")

    # Imports inutilises
    print(f"\n  === IMPORTS INUTILISES ===")
    all_issues = []
    for d in SCAN_DIRS:
        if os.path.exists(d):
            all_issues.extend(scan_imports(d))

    if all_issues:
        for issue in all_issues[:10]:
            print(f"    {issue['file']}:{issue['line']} - import {issue['import']} (non utilise)")
    else:
        print(f"    Aucun import inutilise detecte")

    return duplicates, identical, all_issues


# ============================================================
# PHASE 2: ANALYSE COMMAND HISTORY
# ============================================================

def analyze_failures():
    """Analyse les commandes en echec dans command_history"""
    print("\n  === ANALYSE COMMANDES EN ECHEC ===")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Stats globales
    cur.execute("SELECT COUNT(*) FROM command_history")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM command_history WHERE exec_success = 0")
    failures = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM command_history WHERE exec_success = 1")
    successes = cur.fetchone()[0]

    print(f"  Total commandes: {total}")
    print(f"  Succes: {successes} ({successes/total*100:.0f}%)" if total else "")
    print(f"  Echecs: {failures} ({failures/total*100:.0f}%)" if total else "")

    # Top actions en echec
    cur.execute("""
        SELECT action,
            COUNT(*) as total,
            SUM(CASE WHEN exec_success = 1 THEN 1 ELSE 0 END) as ok,
            SUM(CASE WHEN exec_success = 0 THEN 1 ELSE 0 END) as fail
        FROM command_history
        WHERE action IS NOT NULL
        GROUP BY action
        HAVING total >= 2
        ORDER BY fail DESC
    """)
    rows = cur.fetchall()

    if rows:
        print(f"\n  Actions (>= 2 utilisations):")
        obsolete = []
        for action, t, ok, fail in rows:
            rate = ok / t * 100 if t else 0
            fail_rate = fail / t * 100 if t else 0
            status = "OK" if rate >= 50 else "WARN" if rate >= 25 else "OBSOLETE"
            print(f"    {action:25} : {ok}ok/{fail}fail ({rate:.0f}% succes) [{status}]")
            if fail_rate > 50:
                obsolete.append(action)

        if obsolete:
            print(f"\n  Actions OBSOLETES (>50% echec): {obsolete}")
    else:
        print(f"  Pas assez de donnees (< 2 utilisations par action)")

    # Top erreurs
    cur.execute("""
        SELECT exec_error, COUNT(*) as cnt
        FROM command_history
        WHERE exec_error IS NOT NULL AND exec_error != ''
        GROUP BY exec_error
        ORDER BY cnt DESC
        LIMIT 5
    """)
    errors = cur.fetchall()
    if errors:
        print(f"\n  Top erreurs:")
        for err, cnt in errors:
            print(f"    [{cnt}x] {err[:80]}")

    # Sources d'intent
    cur.execute("""
        SELECT intent_source, COUNT(*) as cnt
        FROM command_history
        GROUP BY intent_source
        ORDER BY cnt DESC
    """)
    print(f"\n  Sources d'intent:")
    for src, cnt in cur.fetchall():
        print(f"    {src or 'NULL':15} : {cnt}")

    conn.close()
    return obsolete if rows else []


# ============================================================
# PHASE 3: AUTOCOMPILATION
# ============================================================

def autocompile_macros():
    """Identifie les commandes similaires et propose des macros generiques"""
    print("\n  === AUTOCOMPILATION - MACROS GENERIQUES ===")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Recuperer les commandes reussies
    cur.execute("""
        SELECT action, params, COUNT(*) as cnt
        FROM command_history
        WHERE exec_success = 1 AND action IS NOT NULL
        GROUP BY action, params
        ORDER BY cnt DESC
    """)
    commands = cur.fetchall()

    if not commands:
        print("  Pas assez de donnees de commandes reussies")
        conn.close()
        return []

    # Grouper par action pour trouver les patterns
    action_groups = defaultdict(list)
    for action, params, cnt in commands:
        action_groups[action].append({"params": params, "count": cnt})

    # Identifier les candidats a la macro
    macros = []
    for action, usages in action_groups.items():
        if len(usages) >= 2:
            # Meme action, params differents = candidat macro
            all_params = [u["params"] for u in usages if u["params"]]
            total_uses = sum(u["count"] for u in usages)

            if len(set(all_params)) >= 2:
                macros.append({
                    "action": action,
                    "variants": len(usages),
                    "total_uses": total_uses,
                    "params": all_params[:5],
                    "suggestion": f"{action} <PARAM>",
                })

    if macros:
        print(f"  {len(macros)} macros generiques proposees:\n")
        for m in macros:
            print(f"    {m['suggestion']} ({m['variants']} variantes, {m['total_uses']} utilisations)")
            for p in m["params"][:3]:
                print(f"      ex: {m['action']} {p}")
    else:
        print("  Pas assez de variantes pour proposer des macros")

    # Patterns appris vs commandes
    cur.execute("SELECT pattern_text, action, usage_count FROM learned_patterns ORDER BY usage_count DESC")
    patterns = cur.fetchall()
    if patterns:
        print(f"\n  Top patterns appris (deja compiles):")
        for pat, act, cnt in patterns[:10]:
            print(f"    '{pat}' -> {act} (x{cnt})")

    # Workflows potentiels (sequences de commandes)
    cur.execute("""
        SELECT session_id, GROUP_CONCAT(action, ' -> ') as sequence, COUNT(*) as steps
        FROM command_history
        WHERE session_id IS NOT NULL AND action IS NOT NULL
        GROUP BY session_id
        HAVING steps >= 3
        ORDER BY steps DESC
        LIMIT 5
    """)
    sequences = cur.fetchall()
    if sequences:
        print(f"\n  Sequences de commandes frequentes (candidats workflow):")
        for sid, seq, steps in sequences:
            print(f"    Session {sid}: {seq} ({steps} etapes)")

    conn.close()
    return macros


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="System Optimizer v1.0")
    parser.add_argument("--duplicates", action="store_true", help="Doublons seulement")
    parser.add_argument("--failures", action="store_true", help="Echecs seulement")
    parser.add_argument("--autocompile", action="store_true", help="Macros seulement")
    args = parser.parse_args()

    print("=" * 60)
    print("  OPTIMIZE SYSTEM v1.0 - Audit & Autocompilation")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    run_all = not (args.duplicates or args.failures or args.autocompile)

    if run_all or args.duplicates:
        duplicates, identical, unused = find_duplicates()

    if run_all or args.failures:
        obsolete = analyze_failures()

    if run_all or args.autocompile:
        macros = autocompile_macros()

    # Resume final
    if run_all:
        print(f"\n{'='*60}")
        print(f"  RESUME OPTIMISATION")
        print(f"{'='*60}")
        print(f"  Doublons fonction:     {len(duplicates)} ({len(identical)} identiques)")
        print(f"  Imports inutilises:    {len(unused)}")
        print(f"  Actions obsoletes:     {len(obsolete)}")
        print(f"  Macros proposees:      {len(macros)}")
        status = "SYSTEME V3.6 DEPLOYE" if len(identical) == 0 and len(obsolete) == 0 else "OPTIMISATION RECOMMANDEE"
        print(f"\n  STATUS: {status}")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
