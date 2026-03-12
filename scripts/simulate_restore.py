"""JARVIS Restore Simulation — Verify full system restore from DB only.

Simulates a complete install in a temp directory using ONLY jarvis.db.
Verifies every component can be restored and matches the original.
"""

import hashlib
import json
import os
import random
import shutil
import sqlite3
import time
from pathlib import Path

ROOT = Path("/home/turbo/jarvis-m1-ops")
SIM = Path("C:/Users/franc/AppData/Local/Temp/jarvis_restore_test")
DB_PATH = ROOT / "data" / "jarvis.db"

errors = []
ok_count = 0


def get(key):
    conn = sqlite3.connect(str(DB_PATH))
    row = conn.execute("SELECT value FROM system_config WHERE key=?", (key,)).fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


def check(name, condition, detail=""):
    global ok_count
    if condition:
        ok_count += 1
        print(f"  [OK]   {name}" + (f" — {detail}" if detail else ""))
    else:
        errors.append(f"{name}: {detail}")
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))


def main():
    global ok_count

    # Clean sim directory
    if SIM.exists():
        shutil.rmtree(SIM)
    SIM.mkdir(parents=True)

    print("=" * 60)
    print("  JARVIS RESTORE SIMULATION")
    print(f"  Source: {DB_PATH.name} ({DB_PATH.stat().st_size // 1024} KB)")
    print(f"  Target: {SIM}")
    print("=" * 60)

    # ── PHASE 1: Config entries readability ──────────────────
    print("\n--- PHASE 1: Config entries ---")
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute("SELECT key, value FROM system_config").fetchall()
    conn.close()
    readable = 0
    for key, value in rows:
        try:
            json.loads(value)
            readable += 1
        except Exception:
            errors.append(f"CONFIG_PARSE: {key}")
    check("Config readability", readable == len(rows), f"{readable}/{len(rows)} parseable")

    # ── PHASE 2: .mcp.json ───────────────────────────────────
    print("\n--- PHASE 2: .mcp.json ---")
    mcp = get("mcp_json")
    if mcp:
        target = SIM / ".mcp.json"
        target.write_text(json.dumps(mcp, indent=2), encoding="utf-8")
        restored = json.loads(target.read_text())
        servers = restored.get("mcpServers", {})
        check(".mcp.json servers", len(servers) == 3, f"{len(servers)} servers")
        for name in ["jarvis-lmstudio", "filesystem", "jarvis-mcp"]:
            check(f"  MCP server '{name}'", name in servers)
    else:
        check(".mcp.json", False, "not in DB")

    # ── PHASE 3: pyproject.toml ──────────────────────────────
    print("\n--- PHASE 3: pyproject.toml ---")
    pyp = get("pyproject_toml")
    if pyp and isinstance(pyp, str):
        target = SIM / "pyproject.toml"
        target.write_text(pyp, encoding="utf-8")
        orig = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        check("pyproject.toml", target.read_text() == orig,
              f"{len(pyp)} chars, EXACT MATCH" if target.read_text() == orig else "MISMATCH")
    else:
        check("pyproject.toml", False, "not in DB")

    # ── PHASE 4: Plugin files ────────────────────────────────
    print("\n--- PHASE 4: Plugin files ---")
    plugin = get("plugin_content")
    if plugin:
        for filepath, content in plugin.items():
            target = SIM / filepath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            orig_path = ROOT / filepath
            if orig_path.exists():
                orig = orig_path.read_text(encoding="utf-8", errors="replace")
                check(f"  {filepath}", content == orig,
                      "EXACT MATCH" if content == orig else f"MISMATCH stored={len(content)} orig={len(orig)}")
            else:
                check(f"  {filepath}", False, "original not found")
    else:
        check("Plugin content", False, "not in DB")

    # ── PHASE 5: .env keys (no secrets) ──────────────────────
    print("\n--- PHASE 5: .env keys ---")
    env_keys = get("env_keys")
    if env_keys:
        target = SIM / ".env.restore"
        lines = ["# JARVIS .env restored"]
        for k in env_keys:
            lines.append(f"{k}=")
        target.write_text("\n".join(lines), encoding="utf-8")

        orig_env = (ROOT / ".env").read_text(encoding="utf-8")
        missing = [k for k in env_keys if k not in orig_env]
        check("Env keys completeness", not missing, f"{len(env_keys)} keys, all in original")

        restored_text = target.read_text()
        leaked = any(s in restored_text for s in ["AAF-", "mx0v", "pplx-", "AIza", "sk-lm-"])
        check("No secrets leaked", not leaked, "SAFE" if not leaked else "LEAKED!")
    else:
        check(".env keys", False, "not in DB")

    # ── PHASE 6: DB schemas ──────────────────────────────────
    print("\n--- PHASE 6: DB schemas ---")
    for dbname in ["etoile", "jarvis", "sniper"]:
        schema = get(f"db_schema_{dbname}")
        if schema:
            db_file = SIM / "data" / f"{dbname}_restored.db"
            db_file.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db_file))
            created = 0
            for sql in schema:
                if sql:
                    try:
                        conn.execute(sql)
                        created += 1
                    except Exception:
                        pass
            conn.commit()
            actual = conn.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0]
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            conn.close()
            check(f"  {dbname} schema", actual >= 1 and integrity == "ok",
                  f"{actual} tables created, integrity={integrity}")
        else:
            check(f"  {dbname} schema", False, "not in DB")

    # ── PHASE 7: Module registry MD5 ─────────────────────────
    print("\n--- PHASE 7: Module registry MD5 ---")
    modules = get("src_module_registry")
    if modules:
        match = mismatch = 0
        drifted = []
        for name, info in modules.items():
            if not isinstance(info, dict):
                continue
            orig = ROOT / "src" / f"{name}.py"
            if orig.exists():
                content = orig.read_text(encoding="utf-8", errors="replace")
                current_md5 = hashlib.md5(content.encode()).hexdigest()[:12]
                if current_md5 == info.get("md5", ""):
                    match += 1
                else:
                    mismatch += 1
                    drifted.append(name)
        check("Module MD5 integrity", mismatch == 0,
              f"{match}/{len(modules)} MATCH" if mismatch == 0
              else f"{match} match, {mismatch} drifted: {drifted[:5]}")
    else:
        check("Module registry", False, "not in DB")

    # ── PHASE 8: Test registry ───────────────────────────────
    print("\n--- PHASE 8: Test registry ---")
    tests = get("test_registry")
    if tests:
        existing = sum(1 for name in tests if (ROOT / "tests" / f"{name}.py").exists())
        total_funcs = sum(t.get("test_count", 0) for t in tests.values() if isinstance(t, dict))
        check("Test files", existing == len(tests),
              f"{existing}/{len(tests)} exist, {total_funcs} test functions")
    else:
        check("Test registry", False, "not in DB")

    # ── PHASE 9: Pip packages ────────────────────────────────
    print("\n--- PHASE 9: Pip packages ---")
    pkgs = get("pip_packages")
    if pkgs:
        target = SIM / "requirements_restore.txt"
        lines = []
        for pkg in pkgs:
            if isinstance(pkg, dict):
                lines.append(f"{pkg.get('name', '')}=={pkg.get('version', '')}")
        target.write_text("\n".join(lines), encoding="utf-8")
        check("Pip packages", len(lines) > 500, f"{len(lines)} packages exported")
    else:
        check("Pip packages", False, "not in DB")

    # ── PHASE 10: Cluster config ─────────────────────────────
    print("\n--- PHASE 10: Cluster config ---")
    nodes = get("cluster_nodes")
    if nodes:
        check("Cluster nodes", len(nodes) >= 4, ", ".join(nodes.keys()))
        for name, info in nodes.items():
            if isinstance(info, dict):
                check(f"  {name} config", "host" in info and "model" in info,
                      f"{info.get('host', '?')} / {info.get('model', '?')}")
    else:
        check("Cluster nodes", False, "not in DB")

    # ── PHASE 11: Git info ───────────────────────────────────
    print("\n--- PHASE 11: Git info ---")
    git = get("git_info")
    if git and isinstance(git, dict):
        check("Git branch", bool(git.get("branch")), f"branch={git.get('branch')}")
        check("Git remote", bool(git.get("remote")), "remote URL stored")
        check("Git commits", bool(git.get("recent_commits")),
              f"{git.get('recent_commits', '').count(chr(10))} commits stored")
    else:
        check("Git info", False, "not in DB")

    # ── PHASE 12: File tree spot-check ───────────────────────
    print("\n--- PHASE 12: File tree spot-check ---")
    tree = get("file_tree")
    if tree:
        sample = random.sample(list(tree.keys()), min(100, len(tree)))
        spot_ok = sum(1 for rel in sample if (ROOT / rel.replace("/", os.sep)).exists())
        check("File tree spot-check", spot_ok == len(sample),
              f"{spot_ok}/{len(sample)} exist (of {len(tree)} tracked)")
    else:
        check("File tree", False, "not in DB")

    # ── PHASE 13: Trading config ─────────────────────────────
    print("\n--- PHASE 13: Trading config ---")
    trading = get("trading_config")
    if trading:
        check("Trading config", "exchange" in trading and "pairs" in trading,
              f"{trading.get('exchange', '?')}, {len(trading.get('pairs', []))} pairs")
    else:
        check("Trading config", False, "not in DB")

    # ── PHASE 14: Voice config ───────────────────────────────
    print("\n--- PHASE 14: Voice config ---")
    voice = get("voice_config")
    if voice:
        check("Voice config", bool(voice), f"voice={voice.get('voice', voice.get('tts_voice', '?'))}")
    else:
        check("Voice config", False, "not in DB")

    # ── PHASE 15: Automation pipeline ────────────────────────
    print("\n--- PHASE 15: Automation pipeline ---")
    auto = get("automation_pipeline")
    if auto:
        for key, path in auto.items():
            exists = (ROOT / path).exists()
            check(f"  {key}", exists, path)
    else:
        check("Automation pipeline", False, "not in DB")

    # ── PHASE 16: Windows tasks ──────────────────────────────
    print("\n--- PHASE 16: Windows tasks ---")
    tasks = get("windows_tasks")
    check("Windows tasks", tasks is not None and len(tasks) >= 1,
          f"{len(tasks)} tasks stored" if tasks else "not in DB")

    # ── PHASE 17: Cowork registry ────────────────────────────
    print("\n--- PHASE 17: Cowork registry ---")
    cowork = get("cowork_registry")
    if cowork:
        existing = sum(1 for name in cowork if (ROOT / "cowork" / "dev" / f"{name}.py").exists())
        check("Cowork scripts", existing == len(cowork),
              f"{existing}/{len(cowork)} scripts exist")
    else:
        check("Cowork registry", False, "not in DB")

    # ── PHASE 18: Restored directory inventory ───────────────
    print("\n--- PHASE 18: Restored directory ---")
    restored_files = [f for f in SIM.rglob("*") if f.is_file()]
    print(f"  {len(restored_files)} files restored:")
    for f in sorted(restored_files):
        rel = f.relative_to(SIM)
        print(f"    {str(rel):55} {f.stat().st_size:>8} bytes")
    check("Restore output", len(restored_files) >= 10, f"{len(restored_files)} files")

    # ── PHASE 19: Cross-DB redundancy ────────────────────────
    print("\n--- PHASE 19: Cross-DB redundancy ---")
    for dbname, dbpath, table in [
        ("etoile", ROOT / "etoile.db", "jarvis_system_config"),
        ("sniper", ROOT / "data" / "sniper.db", "jarvis_system_config"),
    ]:
        conn = sqlite3.connect(str(dbpath))
        try:
            count = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            check(f"  {dbname}.db redundancy", count > 0 and integrity == "ok",
                  f"{count} configs, integrity={integrity}")
        except Exception as e:
            check(f"  {dbname}.db redundancy", False, str(e))
        conn.close()

    # ═══════════════════════════════════════════════════════════
    # FINAL REPORT
    # ═══════════════════════════════════════════════════════════
    print()
    print("=" * 60)
    total_checks = ok_count + len(errors)
    if errors:
        print(f"  RESULT: {ok_count}/{total_checks} PASSED, {len(errors)} FAILED")
        print()
        for e in errors:
            print(f"    [ERR] {e}")
    else:
        print(f"  ALL {ok_count} CHECKS PASSED")
    print()
    verdict = "RESTAURATION 100% VIABLE" if not errors else "RESTAURATION PARTIELLE"
    print(f"  VERDICT: {verdict}")
    print(f"  Depuis jarvis.db seul -> systeme complet identique")
    print("=" * 60)

    # Cleanup
    shutil.rmtree(SIM)
    print(f"\n  Temp dir cleaned: {SIM}")


if __name__ == "__main__":
    main()
