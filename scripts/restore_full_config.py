#!/usr/bin/env python3
"""JARVIS Full Restore — Rebuild entire system from database snapshots.

Reads system_restore from etoile.db and recreates:
- All OpenClaw agent IDENTITY.md, models.json, .mcp.json
- Proxy scripts, autostart scripts
- Source files (with checksum verification)
- Config files, routing tables
- Prints full inventory for validation

Usage:
    uv run python scripts/restore_full_config.py --check     # Dry run: verify what would be restored
    uv run python scripts/restore_full_config.py --restore    # Actually restore all files
    uv run python scripts/restore_full_config.py --simulate   # Simulate full install from scratch
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

TURBO = Path("F:/BUREAU/turbo")
ETOILE = TURBO / "data" / "etoile.db"
JARVIS = TURBO / "data" / "jarvis.db"
SNIPER = TURBO / "data" / "sniper.db"
AGENTS_DIR = Path(os.path.expanduser("~/.openclaw/agents"))


def load_restore_data():
    """Load all system_restore entries from etoile.db."""
    db = sqlite3.connect(str(ETOILE))
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT * FROM system_restore ORDER BY category, key").fetchall()
    db.close()

    data = {}
    for r in rows:
        cat = r["category"]
        if cat not in data:
            data[cat] = {}
        data[cat][r["key"]] = {
            "value": r["value"],
            "file_path": r["file_path"],
            "checksum": r["checksum"],
            "ts": r["ts"],
        }
    return data


def check_integrity(data):
    """Verify all stored files match their checksums."""
    print("=" * 60)
    print("INTEGRITY CHECK")
    print("=" * 60)

    ok = 0
    mismatch = 0
    missing = 0
    no_check = 0

    for cat in sorted(data):
        for key, entry in sorted(data[cat].items()):
            fp = entry.get("file_path")
            stored_md5 = entry.get("checksum")

            if not fp or not stored_md5:
                no_check += 1
                continue

            path = Path(fp)
            if not path.exists():
                print(f"  MISSING  {fp}")
                missing += 1
                continue

            content = path.read_text(encoding="utf-8", errors="replace")
            actual_md5 = hashlib.md5(content.encode()).hexdigest()

            if actual_md5 == stored_md5:
                ok += 1
            else:
                print(f"  CHANGED  {fp} (stored={stored_md5[:8]} actual={actual_md5[:8]})")
                mismatch += 1

    print(f"\nResults: {ok} OK, {mismatch} changed, {missing} missing, {no_check} no checksum")
    return mismatch == 0 and missing == 0


def simulate_install(data):
    """Simulate a full installation from scratch — dry run."""
    print("=" * 60)
    print("SIMULATE FULL INSTALL FROM DATABASES")
    print("=" * 60)

    errors = []

    # 1. Metadata
    print("\n--- 1. System Metadata ---")
    meta = data.get("meta", {})
    for key, entry in sorted(meta.items()):
        print(f"  {key}: {entry['value'][:80]}")

    # 2. Cluster Nodes
    print("\n--- 2. Cluster Nodes ---")
    nodes = data.get("cluster_node", {})
    for name, entry in sorted(nodes.items()):
        cfg = json.loads(entry["value"])
        print(f"  {name}: {cfg['host']}:{cfg['port']} model={cfg['model']} weight={cfg['weight']}")

    # 3. Services
    print("\n--- 3. Services ---")
    services = data.get("service", {})
    for name, entry in sorted(services.items()):
        cfg = json.loads(entry["value"])
        print(f"  {name}: {cfg['host']}:{cfg['port']} type={cfg['type']}")

    # 4. OpenClaw Agents
    print("\n--- 4. OpenClaw Agents ---")
    identities = data.get("openclaw_identity", {})
    models = data.get("openclaw_models", {})
    mcps = data.get("openclaw_mcp", {})
    print(f"  IDENTITY.md: {len(identities)} agents")
    print(f"  models.json: {len(models)} agents")
    print(f"  .mcp.json:   {len(mcps)} agents")

    for name in sorted(identities):
        flags = ["ID"]
        if name in models:
            flags.append("MOD")
        if name in mcps:
            flags.append("MCP")
        # Verify target dir exists
        agent_dir = AGENTS_DIR / name / "agent"
        exists = agent_dir.exists()
        status = "EXISTS" if exists else "WOULD CREATE"
        print(f"    {name:<30} {' '.join(flags):<15} [{status}]")
        if not exists:
            errors.append(f"Agent dir missing: {agent_dir}")

    # 5. Routing
    print("\n--- 5. Routing ---")
    routing = data.get("routing", {})
    if "intent_to_agent" in routing:
        table = json.loads(routing["intent_to_agent"]["value"])
        agents_used = set(table.values())
        print(f"  Intent->Agent: {len(table)} routes -> {len(agents_used)} unique agents")
        # Verify all routed agents exist in identities
        for agent in sorted(agents_used):
            exists = agent in identities or agent == "main"
            status = "OK" if exists else "MISSING AGENT"
            if not exists:
                errors.append(f"Routed agent missing identity: {agent}")
            print(f"    {agent:<25} [{status}]")

    if "dispatch_matrix" in routing:
        matrix = json.loads(routing["dispatch_matrix"]["value"])
        print(f"  Dispatch matrix: {len(matrix)} task types")

    if "fast_patterns" in routing:
        patterns = json.loads(routing["fast_patterns"]["value"])
        print(f"  Fast patterns: {len(patterns)} regex rules")

    # 6. Source Files
    print("\n--- 6. Source Files ---")
    source_files = data.get("source_file", {})
    for rel, entry in sorted(source_files.items()):
        fp = Path(entry["file_path"]) if entry["file_path"] else TURBO / rel
        exists = fp.exists()
        stored_md5 = entry.get("checksum", "")
        if exists and stored_md5:
            actual_md5 = hashlib.md5(fp.read_text(errors="replace").encode()).hexdigest()
            match = "MATCH" if actual_md5 == stored_md5 else "CHANGED"
        elif exists:
            match = "EXISTS"
        else:
            match = "WOULD CREATE"
            errors.append(f"Source file missing: {rel}")
        stored_lines = entry["value"].count("\n") + 1
        print(f"  {rel:<45} {stored_lines:>5}L [{match}]")

    # 7. Proxy Scripts
    print("\n--- 7. Proxy Scripts ---")
    proxies = data.get("proxy_script", {})
    for name, entry in sorted(proxies.items()):
        fp = TURBO / name
        exists = fp.exists()
        status = "EXISTS" if exists else "WOULD CREATE"
        print(f"  {name:<30} [{status}]")

    # 8. Autostart
    print("\n--- 8. Autostart ---")
    autostart = data.get("autostart", {})
    for name, entry in sorted(autostart.items()):
        fp = Path(entry["file_path"]) if entry["file_path"] else None
        exists = fp.exists() if fp else False
        status = "EXISTS" if exists else "WOULD CREATE"
        print(f"  {name:<40} [{status}]")

    # 9. Database Schemas
    print("\n--- 9. Database Schemas ---")
    schemas = data.get("db_schema", {})
    for dbname, entry in sorted(schemas.items()):
        schema = entry["value"]
        table_count = schema.count("CREATE TABLE")
        print(f"  {dbname:<30} {table_count} tables stored")

    # 10. Git Config
    print("\n--- 10. Git Config ---")
    git = data.get("git", {})
    for key, entry in sorted(git.items()):
        print(f"  {key}: {entry['value'][:80]}")

    # 11. Environment
    print("\n--- 11. Environment ---")
    env = data.get("env", {})
    if "env_keys" in env:
        keys = json.loads(env["env_keys"]["value"])
        print(f"  .env keys needed: {len(keys)}")
        for k in keys:
            print(f"    {k}")

    # 12. Trading
    print("\n--- 12. Trading ---")
    trading = data.get("trading", {})
    if "full_config" in trading:
        cfg = json.loads(trading["full_config"]["value"])
        print(f"  Exchange: {cfg['exchange']}")
        print(f"  Leverage: {cfg['leverage']}x | TP: {cfg['tp_pct']}% | SL: {cfg['sl_pct']}%")
        print(f"  Pairs: {', '.join(cfg['pairs'])}")

    # 13. Voice
    print("\n--- 13. Voice ---")
    voice = data.get("voice", {})
    if "config" in voice:
        cfg = json.loads(voice["config"]["value"])
        print(f"  Pipeline: {cfg['pipeline']}")
        print(f"  Voice: {cfg['voice']}")
        print(f"  TTS fallback: {' > '.join(cfg['fallback_tts'])}")

    # 14. Consensus
    print("\n--- 14. Consensus ---")
    consensus = data.get("consensus", {})
    if "weights" in consensus:
        w = json.loads(consensus["weights"]["value"])
        for name, weight in sorted(w.items(), key=lambda x: -x[1]):
            print(f"  {name}: {weight}")

    # 15. Ollama + LM Studio Models
    print("\n--- 15. Models ---")
    ollama = data.get("ollama", {})
    if "models" in ollama:
        models = json.loads(ollama["models"]["value"])
        print(f"  Ollama: {len(models)} models")
        for m in models:
            print(f"    {m['name']}")

    lmstudio = data.get("lmstudio", {})
    if "m1_models" in lmstudio:
        models = json.loads(lmstudio["m1_models"]["value"])
        loaded = [m for m in models if m.get("loaded")]
        print(f"  LM Studio M1: {len(models)} total, {len(loaded)} loaded")

    # 16. File Manifest
    print("\n--- 16. File Manifest ---")
    manifest = data.get("manifest", {})
    if "source_files" in manifest:
        files = json.loads(manifest["source_files"]["value"])
        total_lines = sum(f["lines"] for f in files.values())
        print(f"  {len(files)} source files, {total_lines} total lines")

        # Verify current files match
        match_count = 0
        changed_count = 0
        missing_count = 0
        for rel, info in sorted(files.items()):
            fp = TURBO / rel
            if fp.exists():
                actual_md5 = hashlib.md5(fp.read_text(errors="replace").encode()).hexdigest()
                if actual_md5 == info["md5"]:
                    match_count += 1
                else:
                    changed_count += 1
            else:
                missing_count += 1
        print(f"  Verification: {match_count} match, {changed_count} changed, {missing_count} missing")

    # Summary
    print("\n" + "=" * 60)
    print("SIMULATION SUMMARY")
    print("=" * 60)

    total_entries = sum(len(v) for v in data.values())
    categories = len(data)
    print(f"Total entries in system_restore: {total_entries}")
    print(f"Categories: {categories}")

    if errors:
        print(f"\nISSUES FOUND: {len(errors)}")
        for e in errors[:20]:
            print(f"  ! {e}")
    else:
        print("\nNO ISSUES — System can be restored identically from databases")

    print(f"\nTo restore: copy etoile.db + jarvis.db + sniper.db")
    print(f"Then run: python scripts/restore_full_config.py --restore")
    return len(errors)


def restore_files(data, dry_run=False):
    """Actually restore all files from database."""
    print("=" * 60)
    print(f"RESTORE {'(DRY RUN)' if dry_run else '(LIVE)'}")
    print("=" * 60)

    restored = 0
    skipped = 0

    # Restore OpenClaw agents
    for cat, subdir in [
        ("openclaw_identity", "IDENTITY.md"),
        ("openclaw_models", "models.json"),
    ]:
        entries = data.get(cat, {})
        for name, entry in entries.items():
            target = AGENTS_DIR / name / "agent" / subdir
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(entry["value"], encoding="utf-8")
            print(f"  {'WOULD ' if dry_run else ''}WRITE {target}")
            restored += 1

    # Restore .mcp.json
    for name, entry in data.get("openclaw_mcp", {}).items():
        target = AGENTS_DIR / name / ".mcp.json"
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(entry["value"], encoding="utf-8")
        print(f"  {'WOULD ' if dry_run else ''}WRITE {target}")
        restored += 1

    # Restore source files
    for rel, entry in data.get("source_file", {}).items():
        target = TURBO / rel
        if target.exists():
            actual_md5 = hashlib.md5(target.read_text(errors="replace").encode()).hexdigest()
            if entry.get("checksum") and actual_md5 == entry["checksum"]:
                skipped += 1
                continue
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(entry["value"], encoding="utf-8")
        print(f"  {'WOULD ' if dry_run else ''}WRITE {target}")
        restored += 1

    # Restore proxy scripts
    for name, entry in data.get("proxy_script", {}).items():
        target = TURBO / name
        if not dry_run:
            target.write_text(entry["value"], encoding="utf-8")
        print(f"  {'WOULD ' if dry_run else ''}WRITE {target}")
        restored += 1

    # Restore autostart
    for name, entry in data.get("autostart", {}).items():
        fp = entry.get("file_path")
        if fp:
            target = Path(fp)
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(entry["value"], encoding="utf-8")
            print(f"  {'WOULD ' if dry_run else ''}WRITE {target}")
            restored += 1

    print(f"\nRestored: {restored}, Skipped (unchanged): {skipped}")
    return restored


def main():
    parser = argparse.ArgumentParser(description="JARVIS Full Restore from Databases")
    parser.add_argument("--check", action="store_true", help="Verify integrity of stored vs current files")
    parser.add_argument("--restore", action="store_true", help="Actually restore all files from DB")
    parser.add_argument("--simulate", action="store_true", help="Simulate full install (dry run)")
    parser.add_argument("--dry-run", action="store_true", help="With --restore, show what would be written")
    args = parser.parse_args()

    data = load_restore_data()
    print(f"Loaded {sum(len(v) for v in data.values())} entries from {len(data)} categories\n")

    if args.check:
        check_integrity(data)
    elif args.simulate:
        simulate_install(data)
    elif args.restore:
        restore_files(data, dry_run=args.dry_run)
    else:
        # Default: simulate
        simulate_install(data)


if __name__ == "__main__":
    main()
