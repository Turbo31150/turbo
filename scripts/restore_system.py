#!/usr/bin/env python3
"""JARVIS System Restore — Restauration complete depuis les databases.

Prend UNE database (jarvis.db) et restaure tout le systeme:
- Structure de fichiers
- .env template
- .mcp.json
- Plugin Claude Code
- pyproject.toml
- Schemas DB
- Git info
- Windows tasks
- Pip packages

Usage:
    python scripts/restore_system.py                          # Affiche l'etat stocke
    python scripts/restore_system.py --check                  # Verifie integrite vs DB
    python scripts/restore_system.py --restore <jarvis.db>    # Restaure depuis backup
    python scripts/restore_system.py --export <dir>           # Export config en fichiers
    python scripts/restore_system.py --diff                   # Compare etat actuel vs DB
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_config(db_path: str) -> dict[str, any]:
    """Load all config from database."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT key, value, ts FROM system_config ORDER BY key").fetchall()
    conn.close()
    config = {}
    for key, value, ts in rows:
        try:
            config[key] = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            config[key] = value
    return config


def show_status(db_path: str) -> None:
    """Show stored system state."""
    config = load_config(db_path)

    print(f"\n{'='*60}")
    print(f"  JARVIS SYSTEM STATE (from {Path(db_path).name})")
    print(f"{'='*60}")

    # Cluster
    nodes = config.get("cluster_nodes", {})
    print(f"\n  CLUSTER: {len(nodes)} nodes")
    for name, info in nodes.items():
        if isinstance(info, dict):
            print(f"    {name}: {info.get('host', '?')} ({info.get('model', '?')}) w={info.get('weight', '?')}")

    # Audit
    for key in sorted(config.keys()):
        if key.startswith("audit_status"):
            audit = config[key]
            print(f"\n  AUDIT ({key}):")
            print(f"    Score: {audit.get('score', '?')}/100")
            print(f"    Modules: {audit.get('modules', '?')} | Tests: {audit.get('test_files', audit.get('tests', '?'))}")
            print(f"    Coverage: {audit.get('coverage_pct', audit.get('coverage', '?'))}%")
            print(f"    Critical: {audit.get('critical', '?')} | Major: {audit.get('major', '?')}")

    # MCP
    mcp = config.get("mcp_servers", config.get("mcp_json", {}))
    if isinstance(mcp, dict):
        servers = mcp.get("mcpServers", mcp)
        print(f"\n  MCP SERVERS: {len(servers)}")
        for name in servers:
            print(f"    - {name}")

    # Modules
    modules = config.get("src_module_registry", {})
    if modules:
        print(f"\n  SRC MODULES: {len(modules)}")
        total_lines = sum(m.get("lines", 0) for m in modules.values() if isinstance(m, dict))
        with_all = sum(1 for m in modules.values() if isinstance(m, dict) and m.get("has_all"))
        print(f"    Total lines: {total_lines:,}")
        print(f"    With __all__: {with_all}/{len(modules)}")

    # Tests
    tests = config.get("test_registry", {})
    if tests:
        total_tests = sum(t.get("test_count", 0) for t in tests.values() if isinstance(t, dict))
        print(f"\n  TESTS: {len(tests)} files, {total_tests} test functions")

    # Plugin
    plugin = config.get("plugin_content", {})
    if plugin:
        print(f"\n  PLUGIN: {len(plugin)} files")
        for name in sorted(plugin.keys()):
            print(f"    - {name}")

    # Agents
    agents = config.get("plugin_agents", {})
    if agents:
        print(f"\n  AGENTS: {len(agents)}")
        for name, info in agents.items():
            if isinstance(info, dict):
                print(f"    - {name} ({info.get('color', '?')})")

    # Git
    git = config.get("git_info", {})
    if isinstance(git, dict):
        print(f"\n  GIT: branch={git.get('branch', '?')}")

    # Packages
    pkgs = config.get("pip_packages", [])
    if pkgs:
        print(f"\n  PIP: {len(pkgs)} packages")

    # File tree
    tree = config.get("file_tree", {})
    if tree:
        print(f"\n  FILE TREE: {len(tree)} tracked files")

    # Env keys
    env_keys = config.get("env_keys", [])
    if env_keys:
        print(f"\n  ENV KEYS: {len(env_keys)}")
        for k in env_keys:
            print(f"    - {k}")

    # DB schemas
    for db_name in ["etoile", "jarvis", "sniper"]:
        schema = config.get(f"db_schema_{db_name}", [])
        if schema:
            print(f"\n  DB SCHEMA {db_name}: {len(schema)} tables")

    # Windows tasks
    tasks = config.get("windows_tasks", [])
    if tasks:
        print(f"\n  WINDOWS TASKS: {len(tasks)}")
        for t in tasks:
            print(f"    {t[:80]}")

    print(f"\n  TOTAL CONFIG ENTRIES: {len(config)}")
    print(f"{'='*60}")


def check_integrity(db_path: str) -> None:
    """Compare current state vs stored state."""
    config = load_config(db_path)
    modules = config.get("src_module_registry", {})

    print(f"\n{'='*60}")
    print(f"  INTEGRITY CHECK vs {Path(db_path).name}")
    print(f"{'='*60}")

    ok = 0
    changed = 0
    missing = 0
    added = 0

    # Check src modules
    current_modules = set()
    src_dir = ROOT / "src"
    if src_dir.exists():
        for f in src_dir.glob("*.py"):
            if f.name.startswith("__"):
                continue
            current_modules.add(f.stem)
            stored = modules.get(f.stem)
            if not stored:
                print(f"  [NEW]     src/{f.name}")
                added += 1
                continue

            content = f.read_text(encoding="utf-8", errors="replace")
            current_md5 = hashlib.md5(content.encode()).hexdigest()[:12]
            stored_md5 = stored.get("md5", "")

            if current_md5 == stored_md5:
                ok += 1
            else:
                current_lines = content.count("\n") + 1
                delta = current_lines - stored.get("lines", 0)
                print(f"  [CHANGED] src/{f.name} ({delta:+d} lines)")
                changed += 1

    # Check for deleted modules
    for name in modules:
        if name not in current_modules:
            print(f"  [DELETED] src/{name}.py")
            missing += 1

    print(f"\n  OK: {ok} | Changed: {changed} | New: {added} | Deleted: {missing}")
    print(f"  Integrity: {'MATCH' if changed == 0 and missing == 0 else 'DRIFT DETECTED'}")


def export_config(db_path: str, output_dir: str) -> None:
    """Export stored config to files for manual restoration."""
    config = load_config(db_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Export each config as JSON
    for key, value in config.items():
        filepath = out / f"{key}.json"
        filepath.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    # Generate restore script
    restore_sh = out / "restore.sh"
    lines = ["#!/bin/bash", "# JARVIS System Restore Script", f"# Generated from {Path(db_path).name}", ""]

    # Pip packages
    pkgs = config.get("pip_packages", [])
    if pkgs:
        lines.append("echo '=== Installing pip packages ==='")
        for pkg in pkgs:
            if isinstance(pkg, dict):
                lines.append(f"pip install {pkg.get('name', '')}=={pkg.get('version', '')} 2>/dev/null")

    # .mcp.json
    mcp = config.get("mcp_json")
    if mcp:
        lines.append("")
        lines.append("echo '=== Restoring .mcp.json ==='")
        lines.append(f"cat > .mcp.json << 'MCPEOF'")
        lines.append(json.dumps(mcp, indent=2))
        lines.append("MCPEOF")

    # pyproject.toml
    pyp = config.get("pyproject_toml")
    if pyp:
        lines.append("")
        lines.append("echo '=== Restoring pyproject.toml ==='")
        lines.append(f"cat > pyproject.toml << 'PYPEOF'")
        lines.append(pyp if isinstance(pyp, str) else json.dumps(pyp))
        lines.append("PYPEOF")

    # Plugin content
    plugin = config.get("plugin_content", {})
    if plugin:
        lines.append("")
        lines.append("echo '=== Restoring plugin files ==='")
        for filepath, content in plugin.items():
            dirpath = str(Path(filepath).parent)
            lines.append(f"mkdir -p '{dirpath}'")
            # Escape content for heredoc
            safe = content.replace("'", "'/''")
            lines.append(f"cat > '{filepath}' << 'PLUGEOF'")
            lines.append(content)
            lines.append("PLUGEOF")

    # .env template
    env_keys = config.get("env_keys", [])
    if env_keys:
        lines.append("")
        lines.append("echo '=== Generating .env template ==='")
        lines.append("cat > .env.restore << 'ENVEOF'")
        lines.append("# JARVIS .env — Fill in your values")
        for k in env_keys:
            lines.append(f"{k}=")
        lines.append("ENVEOF")

    # DB schemas
    for db_name in ["etoile", "jarvis", "sniper"]:
        schema = config.get(f"db_schema_{db_name}", [])
        if schema:
            lines.append("")
            lines.append(f"echo '=== Restoring {db_name} DB schema ==='")
            db_file = {"etoile": "etoile.db", "jarvis": "data/jarvis.db", "sniper": "data/sniper.db"}[db_name]
            for sql in schema:
                if sql:
                    safe_sql = sql.replace("'", "'/''")
                    lines.append(f"sqlite3 '{db_file}' '{safe_sql};' 2>/dev/null")

    lines.append("")
    lines.append("echo '=== Restore complete ==='")

    restore_sh.write_text("\n".join(lines), encoding="utf-8")

    # Generate summary
    summary = out / "RESTORE_README.md"
    summary.write_text(f"""# JARVIS System Restore

Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
Source: {Path(db_path).name}

## Contents

| File | Description |
|------|-------------|
| restore.sh | Full restore script (pip + configs + schemas) |
| *.json | Individual config entries |

## Quick Restore

```bash
cd /home/turbo/jarvis-m1-ops
bash restore/restore.sh
# Then fill in .env.restore with your secrets and rename to .env
```

## Manual Restore

1. Copy database files to their paths
2. Run `pip install -r requirements.txt`
3. Fill in `.env` with your API keys
4. Run `python scripts/restore_system.py --check data/jarvis.db`

## Stored Config: {len(config)} entries
""", encoding="utf-8")

    print(f"  Exported {len(config)} configs to {output_dir}/")
    print(f"  Restore script: {restore_sh}")
    print(f"  README: {summary}")


def restore_from_backup(backup_db: str) -> None:
    """Restore system from a backup database."""
    config = load_config(backup_db)

    print(f"\n{'='*60}")
    print(f"  RESTORE FROM {Path(backup_db).name}")
    print(f"{'='*60}")

    restored = 0

    # 1. .mcp.json
    mcp = config.get("mcp_json")
    if mcp:
        target = ROOT / ".mcp.json"
        target.write_text(json.dumps(mcp, indent=2), encoding="utf-8")
        print(f"  [OK] .mcp.json restored")
        restored += 1

    # 2. pyproject.toml
    pyp = config.get("pyproject_toml")
    if pyp and isinstance(pyp, str):
        target = ROOT / "pyproject.toml"
        target.write_text(pyp, encoding="utf-8")
        print(f"  [OK] pyproject.toml restored")
        restored += 1

    # 3. Plugin content
    plugin = config.get("plugin_content", {})
    for filepath, content in plugin.items():
        target = ROOT / filepath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"  [OK] {filepath} restored")
        restored += 1

    # 4. .env template (no secrets)
    env_keys = config.get("env_keys", [])
    if env_keys:
        env_file = ROOT / ".env.restore"
        lines = ["# JARVIS .env — Restored template, fill in values"]
        for k in env_keys:
            lines.append(f"{k}=YOUR_VALUE_HERE")
        env_file.write_text("\n".join(lines), encoding="utf-8")
        print(f"  [OK] .env.restore created ({len(env_keys)} keys)")
        restored += 1

    # 5. DB schemas
    for db_name in ["etoile", "jarvis", "sniper"]:
        schema = config.get(f"db_schema_{db_name}", [])
        if not schema:
            continue
        db_file = {"etoile": "etoile.db", "jarvis": "data/jarvis.db", "sniper": "data/sniper.db"}[db_name]
        target = ROOT / db_file
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            conn = sqlite3.connect(str(target))
            for sql in schema:
                if sql:
                    try:
                        conn.execute(sql)
                    except Exception:
                        pass
            conn.commit()
            conn.close()
            print(f"  [OK] {db_file} schema restored ({len(schema)} tables)")
            restored += 1
        else:
            print(f"  [SKIP] {db_file} already exists")

    # 6. Pip packages
    pkgs = config.get("pip_packages", [])
    if pkgs:
        req_file = ROOT / "requirements_restore.txt"
        lines = []
        for pkg in pkgs:
            if isinstance(pkg, dict):
                lines.append(f"{pkg.get('name', '')}=={pkg.get('version', '')}")
        req_file.write_text("\n".join(lines), encoding="utf-8")
        print(f"  [OK] requirements_restore.txt ({len(lines)} packages)")
        restored += 1

    print(f"\n  Restored: {restored} components")
    print(f"  Next: fill .env.restore with secrets, rename to .env")
    print(f"  Then: pip install -r requirements_restore.txt")


def diff_state(db_path: str) -> None:
    """Show what changed since last snapshot."""
    check_integrity(db_path)

    config = load_config(db_path)

    # Check file count drift
    tree = config.get("file_tree", {})
    if tree:
        current_count = 0
        for pattern in ["src/*.py", "tests/*.py", "scripts/*.py"]:
            current_count += len(list(ROOT.glob(pattern)))
        stored_src = len([k for k in tree if k.startswith("src/")])
        stored_tests = len([k for k in tree if k.startswith("tests/")])
        stored_scripts = len([k for k in tree if k.startswith("scripts/")])
        print(f"\n  File counts (stored -> current):")
        print(f"    src/:     {stored_src} -> {len(list((ROOT/'src').glob('*.py')))}")
        print(f"    tests/:   {stored_tests} -> {len(list((ROOT/'tests').glob('*.py')))}")
        print(f"    scripts/: {stored_scripts} -> {len(list((ROOT/'scripts').glob('*.py')))}")


def main():
    parser = argparse.ArgumentParser(description="JARVIS System Restore")
    parser.add_argument("--check", action="store_true", help="Check integrity vs DB")
    parser.add_argument("--restore", metavar="DB", help="Restore from backup database")
    parser.add_argument("--export", metavar="DIR", help="Export config to directory")
    parser.add_argument("--diff", action="store_true", help="Show changes since snapshot")
    parser.add_argument("--db", default=str(ROOT / "data" / "jarvis.db"), help="Database path")
    args = parser.parse_args()

    db_path = args.restore or args.db

    if args.restore:
        restore_from_backup(args.restore)
    elif args.export:
        export_config(db_path, args.export)
    elif args.check:
        check_integrity(db_path)
    elif args.diff:
        diff_state(db_path)
    else:
        show_status(db_path)


if __name__ == "__main__":
    main()
