#!/usr/bin/env python3
"""Save ALL JARVIS system configuration to databases for instant restore.

Saves everything needed to rebuild the system from scratch:
- OpenClaw agents (IDENTITY.md, models.json, .mcp.json)
- Cluster nodes, services, routing
- Source files, proxy scripts, autostart
- Database schemas, git config, env keys
- Trading, consensus, version metadata

Usage:
    uv run python scripts/save_full_config.py
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

TURBO = Path("F:/BUREAU/turbo")
ETOILE = TURBO / "data" / "etoile.db"
JARVIS = TURBO / "data" / "jarvis.db"
SNIPER = TURBO / "data" / "sniper.db"
AGENTS_DIR = Path(os.path.expanduser("~/.openclaw/agents"))
ts = time.time()
now = datetime.now().isoformat()


def _migrate_agent_patterns(db):
    """Ensure agent_patterns table has all columns expected by src/ modules."""
    try:
        existing = {c[1] for c in db.execute("PRAGMA table_info(agent_patterns)").fetchall()}
        if not existing:
            return  # table doesn't exist yet
        required = {
            "pattern_type": "TEXT", "pattern_id": "TEXT", "model_primary": "TEXT",
            "strategy": 'TEXT DEFAULT "single"', "agent_id": "TEXT",
            "priority": "INTEGER DEFAULT 50", "keywords": "TEXT",
            "model_fallbacks": "TEXT", "system_prompt": "TEXT",
            "max_tokens": "INTEGER DEFAULT 512", "temperature": "REAL DEFAULT 0.3",
            "timeout_s": "REAL DEFAULT 30", "created_at": "TEXT", "updated_at": "TEXT",
            "success_rate": "REAL DEFAULT 0", "total_dispatches": "INTEGER DEFAULT 0",
            "total_calls": "INTEGER DEFAULT 0", "status": 'TEXT DEFAULT "active"',
            "avg_latency_ms": "REAL DEFAULT 0",
        }
        added = 0
        for col, dtype in required.items():
            if col not in existing:
                db.execute(f"ALTER TABLE agent_patterns ADD COLUMN {col} {dtype}")
                added += 1
        if added:
            db.execute("""UPDATE agent_patterns SET
                pattern_type = pattern_name, pattern_id = 'pat-' || id,
                model_primary = agent_primary,
                agent_id = 'pat-' || LOWER(REPLACE(pattern_name, '-', '_'))
                WHERE pattern_type IS NULL""")
            print(f"  agent_patterns: migrated ({added} columns added)")
    except Exception:
        pass  # table may not exist in fresh install


def save_etoile():
    """Save full system state to etoile.db system_restore table."""
    db = sqlite3.connect(str(ETOILE))
    db.execute("DROP TABLE IF EXISTS system_restore")
    db.execute("""
        CREATE TABLE system_restore (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            category TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            file_path TEXT,
            checksum TEXT,
            UNIQUE(category, key)
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_sr_cat ON system_restore(category)")

    def save(cat, key, value, file_path=None, checksum=None):
        v = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        db.execute(
            "INSERT OR REPLACE INTO system_restore (ts, category, key, value, file_path, checksum) VALUES (?,?,?,?,?,?)",
            (ts, cat, key, v, file_path, checksum),
        )

    # A. OpenClaw Agents
    print("=== OpenClaw Agents ===")
    agent_count = 0
    for d in sorted(AGENTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        name = d.name

        identity_path = d / "agent" / "IDENTITY.md"
        if identity_path.exists():
            content = identity_path.read_text(encoding="utf-8", errors="replace")
            md5 = hashlib.md5(content.encode()).hexdigest()
            save("openclaw_identity", name, content, str(identity_path), md5)

        models_path = d / "agent" / "models.json"
        if models_path.exists():
            content = models_path.read_text(encoding="utf-8", errors="replace")
            save("openclaw_models", name, content, str(models_path))

        for mp in [d / ".mcp.json", d / "agent" / ".mcp.json"]:
            if mp.exists():
                content = mp.read_text(encoding="utf-8", errors="replace")
                save("openclaw_mcp", name, content, str(mp))
                break

        agent_count += 1
    print(f"  {agent_count} agents saved")

    # B. Routing Table
    print("=== Routing Table ===")
    try:
        sys.path.insert(0, str(TURBO))
        from src.openclaw_bridge import INTENT_TO_AGENT, _FAST_PATTERNS
        save("routing", "intent_to_agent", INTENT_TO_AGENT)
        patterns = [(p.pattern, intent) for p, intent in _FAST_PATTERNS]
        save("routing", "fast_patterns", patterns)
        print(f"  {len(INTENT_TO_AGENT)} routes, {len(patterns)} patterns")
    except Exception as e:
        print(f"  Routing import error: {e}")

    # C. Cluster Nodes
    print("=== Cluster Nodes ===")
    nodes = {
        "M1": {"host": "127.0.0.1", "port": 1234, "model": "qwen3-8b", "type": "lmstudio", "gpu": "6x (46GB)", "weight": 1.8, "tok_s": 46, "ctx": 32768, "nothink": True},
        "M2": {"host": "192.168.1.26", "port": 1234, "model": "deepseek-r1-0528-qwen3-8b", "type": "lmstudio", "gpu": "3x (24GB)", "weight": 1.5, "tok_s": 44, "nothink": False},
        "M3": {"host": "192.168.1.113", "port": 1234, "model": "deepseek-r1-0528-qwen3-8b", "type": "lmstudio", "gpu": "1x (8GB)", "weight": 1.2, "tok_s": 33, "ctx": 131072, "nothink": False},
        "OL1": {"host": "127.0.0.1", "port": 11434, "model": "qwen3:1.7b", "type": "ollama", "weight": 1.3, "tok_s": 84, "parallel": 3},
    }
    for name, cfg in nodes.items():
        save("cluster_node", name, cfg)
    print(f"  {len(nodes)} nodes")

    # D. Services
    print("=== Services ===")
    services = {
        "LMStudio_M1": {"host": "127.0.0.1", "port": 1234, "type": "inference"},
        "Ollama_OL1": {"host": "127.0.0.1", "port": 11434, "type": "inference"},
        "JARVIS_WS": {"host": "127.0.0.1", "port": 9742, "type": "websocket", "stack": "FastAPI"},
        "OpenClaw_GW": {"host": "127.0.0.1", "port": 18789, "type": "gateway", "bind": "loopback"},
        "LMStudio_M2": {"host": "192.168.1.26", "port": 1234, "type": "inference"},
        "LMStudio_M3": {"host": "192.168.1.113", "port": 1234, "type": "inference"},
        "Direct_Proxy": {"host": "127.0.0.1", "port": 18800, "type": "proxy", "script": "direct-proxy.js"},
    }
    for name, cfg in services.items():
        save("service", name, cfg)
    print(f"  {len(services)} services")

    # E. Key Source Files
    print("=== Source Files ===")
    config_files = [
        "pyproject.toml", ".env.example", "package.json", ".gitignore",
        "scripts/lmstudio_mcp_bridge.py", "scripts/jarvis_full_automation.py",
        "scripts/cowork_github_report.py", "scripts/openclaw_auto_dispatch.py",
        "src/openclaw_bridge.py", "src/_paths.py", "src/adaptive_router.py",
        "src/dispatch_engine.py", "src/smart_dispatcher.py", "src/intent_classifier.py",
        "src/ia_tool_executor.py", "src/auto_auditor.py", "src/auto_fixer.py",
        "python_ws/server.py", "python_ws/routes/chat.py",
    ]
    saved_files = 0
    for rel in config_files:
        fp = TURBO / rel
        if fp.exists():
            content = fp.read_text(encoding="utf-8", errors="replace")
            md5 = hashlib.md5(content.encode()).hexdigest()
            save("source_file", rel, content, str(fp), md5)
            saved_files += 1
    print(f"  {saved_files} files saved")

    # F. Proxy Scripts
    print("=== Proxy Scripts ===")
    for proxy in ["gemini-proxy.js", "claude-proxy.js", "direct-proxy.js"]:
        fp = TURBO / proxy
        if fp.exists():
            content = fp.read_text(encoding="utf-8", errors="replace")
            md5 = hashlib.md5(content.encode()).hexdigest()
            save("proxy_script", proxy, content, str(fp), md5)
            print(f"  {proxy}")

    # G. Windows Autostart
    print("=== Autostart ===")
    startup_dir = Path(os.path.expanduser("~/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"))
    for f in startup_dir.glob("JARVIS*"):
        content = f.read_text(encoding="utf-8", errors="replace")
        save("autostart", f.name, content, str(f))
        print(f"  {f.name}")
    # Also save unified_boot and watchdog if they exist
    for script in ["scripts/unified_boot.py", "scripts/watchdog_services.py", "launchers/JARVIS_AUTOSTART.bat"]:
        fp = TURBO / script
        if fp.exists():
            content = fp.read_text(encoding="utf-8", errors="replace")
            save("autostart", script, content, str(fp))
            print(f"  {script}")

    # H. .env keys (no secrets)
    print("=== Environment ===")
    env_file = TURBO / ".env"
    if env_file.exists():
        keys = [line.split("=")[0].strip() for line in env_file.read_text(errors="replace").splitlines()
                if "=" in line and not line.strip().startswith("#")]
        save("env", "env_keys", keys)
        print(f"  {len(keys)} env keys")
    env_ex = TURBO / ".env.example"
    if env_ex.exists():
        save("env", "env_example", env_ex.read_text(errors="replace"), str(env_ex))

    # I. Git Config
    print("=== Git ===")
    r = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True, cwd=str(TURBO))
    remotes = {}
    for line in r.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) >= 2 and "(fetch)" in line:
            remotes[parts[0]] = parts[1]
    save("git", "remotes", remotes)
    save("git", "branch", "main")
    r2 = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(TURBO))
    save("git", "head_commit", r2.stdout.strip())
    save("git", "head_date", now)
    print(f"  {len(remotes)} remotes, HEAD: {r2.stdout.strip()[:8]}")

    # J. Database Schemas
    print("=== DB Schemas ===")
    data_dir = TURBO / "data"
    for dbf in sorted(data_dir.glob("*.db")):
        if "backup" in dbf.name or "20260" in dbf.name:
            continue
        try:
            dbc = sqlite3.connect(str(dbf))
            schemas = dbc.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL ORDER BY name"
            ).fetchall()
            schema_text = "\n".join(s[0] for s in schemas if s[0])
            save("db_schema", dbf.name, schema_text, str(dbf))
            print(f"  {dbf.name}: {len(schemas)} tables")
            dbc.close()
        except Exception as e:
            print(f"  {dbf.name}: ERROR {e}")

    # K. Ollama Models
    print("=== Ollama Models ===")
    try:
        import httpx
        resp = httpx.get("http://127.0.0.1:11434/api/tags", timeout=3)
        models = [{"name": m["name"], "size": m.get("size", 0)} for m in resp.json().get("models", [])]
        save("ollama", "models", models)
        print(f"  {len(models)} models")
    except Exception as e:
        print(f"  Error: {e}")

    # L. LM Studio Models (M1)
    print("=== LM Studio Models ===")
    try:
        import httpx
        resp = httpx.get("http://127.0.0.1:1234/api/v1/models", timeout=3)
        data = resp.json()
        all_models = data.get("data", data.get("models", []))
        loaded = [{"id": m.get("id", m.get("name", "?")), "loaded": bool(m.get("loaded_instances"))} for m in all_models]
        save("lmstudio", "m1_models", loaded)
        print(f"  M1: {len(loaded)} models ({sum(1 for m in loaded if m['loaded'])} loaded)")
    except Exception as e:
        print(f"  M1 Error: {e}")

    # M. Consensus Weights
    print("=== Consensus ===")
    weights = {"M1": 1.8, "M2": 1.5, "OL1": 1.3, "GEMINI": 1.2, "CLAUDE": 1.2, "M3": 1.2}
    save("consensus", "weights", weights)
    save("consensus", "quorum_threshold", "0.65")

    # N. Trading Config
    print("=== Trading ===")
    trading = {
        "exchange": "MEXC Futures", "leverage": 10, "tp_pct": 0.4, "sl_pct": 0.25,
        "position_size_usdt": 10, "min_score": 70,
        "pairs": ["BTC", "ETH", "SOL", "SUI", "PEPE", "DOGE", "XRP", "ADA", "AVAX", "LINK"],
        "scan_interval_min": 5, "active_hours": "8-23",
    }
    save("trading", "full_config", trading)

    # O. Dispatch Matrix
    print("=== Dispatch Matrix ===")
    matrix = {
        "code_nouveau": {"principal": "M1", "secondaire": "OL1", "verificateur": "M2"},
        "bug_fix": {"principal": "M1", "secondaire": "OL1", "verificateur": "M2"},
        "architecture": {"principal": "M1", "secondaire": "OL1", "verificateur": "M2"},
        "raisonnement": {"principal": "M1", "secondaire": "M2", "verificateur": "M3"},
        "trading": {"principal": "OL1", "secondaire": "M1"},
        "securite": {"principal": "M1", "secondaire": "OL1", "verificateur": "M2"},
        "question_simple": {"principal": "OL1", "secondaire": "M1"},
        "recherche_web": {"principal": "OL1", "secondaire": "GEMINI"},
        "consensus": {"principal": "M1+M2+OL1+M3+GEMINI+CLAUDE", "method": "vote_pondere"},
    }
    save("routing", "dispatch_matrix", matrix)
    print(f"  {len(matrix)} routes")

    # P. Voice Config
    print("=== Voice ===")
    voice = {
        "pipeline": "OpenWakeWord > Whisper large-v3-turbo CUDA > TTS Edge",
        "voice": "fr-FR-DeniseNeural",
        "fallback_tts": ["Edge TTS", "Windows SAPI Hortense", "Web Speech API"],
        "whisper_model": "large-v3-turbo",
        "whisper_device": "cuda",
        "timeout_correction": 15.0,
        "timeout_command": 8.0,
    }
    save("voice", "config", voice)

    # Q. Electron Desktop Config
    print("=== Electron ===")
    electron = {
        "version": "1.0",
        "stack": "Electron 33 + React 19 + Vite 6",
        "ws_port": 9742,
        "pages": 29,
        "pages_list": [
            "Dashboard", "Chat", "Trading", "Voice", "LMStudio", "Settings",
            "Dictionary", "Pipelines", "Toolbox", "Logs", "Terminal",
            "Orchestrator", "Memory", "Metrics", "Alerts", "Workflows",
            "Health", "Resources", "Scheduler", "Services", "Notifications",
            "Queue", "Gateway", "Infra", "Mesh", "Automation", "Processes",
            "Snapshots", "System",
        ],
    }
    save("electron", "config", electron)

    # R. OpenClaw Gateway Config
    print("=== OpenClaw Gateway ===")
    openclaw_cfg_path = Path(os.path.expanduser("~/.openclaw/config.json"))
    if openclaw_cfg_path.exists():
        save("openclaw", "gateway_config", openclaw_cfg_path.read_text(errors="replace"), str(openclaw_cfg_path))
        print(f"  config.json saved")
    # Crons
    openclaw_crons = Path(os.path.expanduser("~/.openclaw/crons.json"))
    if openclaw_crons.exists():
        save("openclaw", "crons", openclaw_crons.read_text(errors="replace"), str(openclaw_crons))
        print(f"  crons.json saved")
    # Plugins
    openclaw_plugins = Path(os.path.expanduser("~/.openclaw/plugins.json"))
    if openclaw_plugins.exists():
        save("openclaw", "plugins", openclaw_plugins.read_text(errors="replace"), str(openclaw_plugins))
        print(f"  plugins.json saved")

    # S. Project File Manifest (all src/ and scripts/ with checksums)
    print("=== File Manifest ===")
    manifest = {}
    for pattern, label in [("src/*.py", "src"), ("scripts/*.py", "scripts"), ("python_ws/**/*.py", "python_ws")]:
        for fp in sorted(TURBO.glob(pattern)):
            content = fp.read_text(encoding="utf-8", errors="replace")
            manifest[str(fp.relative_to(TURBO))] = {
                "size": len(content),
                "lines": content.count("\n") + 1,
                "md5": hashlib.md5(content.encode()).hexdigest(),
            }
    save("manifest", "source_files", manifest)
    print(f"  {len(manifest)} files in manifest")

    # T. Version + Metadata
    save("meta", "version", "JARVIS v12.4")
    save("meta", "snapshot_date", now)
    save("meta", "snapshot_ts", str(ts))
    save("meta", "platform", "Windows 11 Pro 10.0.26300")
    save("meta", "python", "3.13")
    save("meta", "sdk", "Claude Agent SDK v0.1.35")
    save("meta", "uv", "0.10.2")
    save("meta", "turbo_dir", str(TURBO))
    save("meta", "user", "Turbo")
    save("meta", "assistant", "JARVIS")

    # Ensure agent_patterns has all required columns (schema migration)
    _migrate_agent_patterns(db)

    db.commit()
    total = db.execute("SELECT COUNT(*) FROM system_restore").fetchone()[0]
    cats = db.execute("SELECT category, COUNT(*) FROM system_restore GROUP BY category ORDER BY COUNT(*) DESC").fetchall()
    print(f"\n{'='*60}")
    print(f"system_restore: {total} entries total")
    for c, n in cats:
        print(f"  {c:<25} {n:>4} entries")
    db.close()
    return total


def save_jarvis():
    """Update jarvis.db system_config with full inventory."""
    db = sqlite3.connect(str(JARVIS))
    # Check existing schema
    cols = [r[1] for r in db.execute("PRAGMA table_info(system_config)").fetchall()]
    if not cols:
        db.execute("""
            CREATE TABLE system_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL
            )
        """)
    elif "ts" not in cols:
        db.execute("ALTER TABLE system_config ADD COLUMN ts REAL")

    def save(key, value):
        v = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        db.execute("INSERT OR REPLACE INTO system_config (ts, key, value) VALUES (?,?,?)", (ts, key, v))

    # Count everything fresh
    src_count = len(list(TURBO.glob("src/*.py")))
    test_files = list(TURBO.glob("tests/test_*.py"))
    test_funcs = sum(f.read_text(errors="replace").count("def test_") for f in test_files)
    cowork_count = len(list((TURBO / "cowork" / "dev").glob("*.py"))) if (TURBO / "cowork" / "dev").exists() else 0
    script_count = len(list(TURBO.glob("scripts/*.py")))
    launcher_count = len(list((TURBO / "launchers").glob("*"))) if (TURBO / "launchers").exists() else 0

    save("version", json.dumps("JARVIS v12.4"))
    save("snapshot_date", json.dumps(now))
    save("src_modules", json.dumps(src_count))
    save("test_files", json.dumps(len(test_files)))
    save("test_functions", json.dumps(test_funcs))
    save("cowork_scripts", json.dumps(cowork_count))
    save("scripts_count", json.dumps(script_count))
    save("launchers_count", json.dumps(launcher_count))

    # Cluster
    save("cluster_nodes", json.dumps({
        "M1": {"host": "127.0.0.1:1234", "model": "qwen3-8b", "weight": 1.8, "gpu": "6x", "tok_s": 46},
        "M2": {"host": "192.168.1.26:1234", "model": "deepseek-r1-0528-qwen3-8b", "weight": 1.5, "gpu": "3x"},
        "M3": {"host": "192.168.1.113:1234", "model": "deepseek-r1-0528-qwen3-8b", "weight": 1.2, "gpu": "1x"},
        "OL1": {"host": "127.0.0.1:11434", "model": "qwen3:1.7b", "weight": 1.3, "tok_s": 84},
    }))

    save("services", json.dumps({"WS": 9742, "OpenClaw": 18789, "LMStudio": 1234, "Ollama": 11434, "Proxy": 18800}))
    save("openclaw_agents_count", json.dumps(40))
    save("openclaw_agents_with_identity", json.dumps(40))
    save("mcp_workspaces", json.dumps(41))
    save("routing_intents", json.dumps(37))
    save("ia_tools_count", json.dumps(23))
    save("last_config_save", json.dumps(ts))

    save("trading_config", json.dumps({
        "exchange": "MEXC Futures", "leverage": 10, "tp": 0.4, "sl": 0.25,
        "size": 10, "pairs": ["BTC", "ETH", "SOL", "SUI", "PEPE", "DOGE", "XRP", "ADA", "AVAX", "LINK"],
    }))

    save("voice_config", json.dumps({
        "pipeline": "OpenWakeWord>Whisper-large-v3-turbo>TTS-Edge",
        "voice": "fr-FR-DeniseNeural",
        "fallback": ["Edge", "SAPI", "WebSpeech"],
    }))

    save("electron_config", json.dumps({"version": "1.0", "stack": "Electron33+React19+Vite6", "ws_port": 9742, "pages": 29}))
    save("security_config", json.dumps({"env_file": ".env", "hardcoded_secrets": 0, "paths_module": "src/_paths.py"}))
    save("autostart_config", json.dumps({"startup": "JARVIS_BOOT_V2.bat", "watchdog_services": 7, "layers": 3}))

    save("database_paths", json.dumps({"etoile": "data/etoile.db", "jarvis": "data/jarvis.db", "sniper": "data/sniper.db"}))

    # Git info
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(TURBO))
    save("git_head", json.dumps(r.stdout.strip()))
    save("git_branch", json.dumps("main"))

    db.commit()
    count = db.execute("SELECT COUNT(*) FROM system_config").fetchone()[0]
    print(f"\njarvis.db system_config: {count} entries")
    db.close()
    return count


def save_sniper():
    """Update sniper.db trading_config."""
    db = sqlite3.connect(str(SNIPER))
    cols = [r[1] for r in db.execute("PRAGMA table_info(trading_config)").fetchall()]
    if not cols:
        db.execute("""
            CREATE TABLE trading_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL
            )
        """)

    def save(key, value):
        v = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        db.execute("INSERT OR REPLACE INTO trading_config (ts, key, value) VALUES (?,?,?)", (ts, key, v))

    save("exchange", "MEXC Futures")
    save("leverage", "10")
    save("take_profit", "0.4")
    save("stop_loss", "0.25")
    save("position_size", "10")
    save("min_score", "70")
    save("pairs", json.dumps(["BTC", "ETH", "SOL", "SUI", "PEPE", "DOGE", "XRP", "ADA", "AVAX", "LINK"]))
    save("scan_interval_min", "5")
    save("active_hours", "8-23")
    save("last_config_save", str(ts))

    db.commit()
    count = db.execute("SELECT COUNT(*) FROM trading_config").fetchone()[0]
    print(f"\nsniper.db trading_config: {count} entries")
    db.close()
    return count


if __name__ == "__main__":
    print("=" * 60)
    print(f"JARVIS Full Config Save — {now}")
    print("=" * 60)

    e = save_etoile()
    j = save_jarvis()
    s = save_sniper()

    print("\n" + "=" * 60)
    print(f"TOTAL: etoile={e} + jarvis={j} + sniper={s} = {e+j+s} entries")
    print(f"Restore: just copy the 3 .db files + run restore script")
    print("=" * 60)
