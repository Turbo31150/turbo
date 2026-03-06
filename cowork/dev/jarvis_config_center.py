#!/usr/bin/env python3
"""jarvis_config_center.py (#194) — Unified configuration center.

Store key-value configs dans SQLite avec types, descriptions, valeurs par defaut.
Override par variables d'environnement. Export/import JSON.

Usage:
    python dev/jarvis_config_center.py --once
    python dev/jarvis_config_center.py --get cluster.m1.url
    python dev/jarvis_config_center.py --set cluster.m1.url "http://127.0.0.1:1234"
    python dev/jarvis_config_center.py --list
    python dev/jarvis_config_center.py --export
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "config_center.db"

# Default configs to seed on first run
DEFAULT_CONFIGS = [
    # Cluster
    ("cluster.m1.url", "http://127.0.0.1:1234", "str", "M1 LM Studio URL", "JARVIS_M1_URL"),
    ("cluster.m1.model", "qwen3-8b", "str", "M1 default model", "JARVIS_M1_MODEL"),
    ("cluster.m2.url", "http://192.168.1.26:1234", "str", "M2 LM Studio URL", "JARVIS_M2_URL"),
    ("cluster.m2.model", "deepseek-r1-0528-qwen3-8b", "str", "M2 default model", "JARVIS_M2_MODEL"),
    ("cluster.m3.url", "http://192.168.1.113:1234", "str", "M3 LM Studio URL", "JARVIS_M3_URL"),
    ("cluster.ol1.url", "http://127.0.0.1:11434", "str", "OL1 Ollama URL", "JARVIS_OL1_URL"),
    ("cluster.ol1.model", "qwen3:1.7b", "str", "OL1 default local model", "JARVIS_OL1_MODEL"),
    # Server
    ("server.webhook.port", "9801", "int", "Webhook server port", "JARVIS_WEBHOOK_PORT"),
    ("server.api.port", "9742", "int", "API server port", "JARVIS_API_PORT"),
    ("server.dashboard.port", "8080", "int", "Dashboard port", "JARVIS_DASHBOARD_PORT"),
    # Timeouts
    ("timeout.m1", "60", "int", "M1 request timeout seconds", "JARVIS_TIMEOUT_M1"),
    ("timeout.m2", "120", "int", "M2 request timeout seconds", "JARVIS_TIMEOUT_M2"),
    ("timeout.ol1", "30", "int", "OL1 request timeout seconds", "JARVIS_TIMEOUT_OL1"),
    ("timeout.gemini", "45", "int", "Gemini request timeout seconds", "JARVIS_TIMEOUT_GEMINI"),
    # Trading
    ("trading.dry_run", "false", "bool", "Trading dry run mode", "JARVIS_DRY_RUN"),
    ("trading.tp_percent", "0.4", "float", "Take profit percentage", "JARVIS_TP_PERCENT"),
    ("trading.sl_percent", "0.25", "float", "Stop loss percentage", "JARVIS_SL_PERCENT"),
    ("trading.size_usdt", "10", "float", "Trade size in USDT", "JARVIS_TRADE_SIZE"),
    ("trading.min_score", "70", "int", "Minimum signal score", "JARVIS_MIN_SCORE"),
    # System
    ("system.gpu.thermal_warn", "75", "int", "GPU thermal warning threshold C", "JARVIS_GPU_WARN"),
    ("system.gpu.thermal_critical", "85", "int", "GPU thermal critical threshold C", "JARVIS_GPU_CRITICAL"),
    ("system.ollama.parallel", "3", "int", "Ollama parallel requests", "OLLAMA_NUM_PARALLEL"),
    # Self-critic
    ("ia.self_critic.min_score", "70", "int", "Min score before regeneration", "JARVIS_MIN_CRITIC_SCORE"),
    ("ia.self_critic.max_iterations", "3", "int", "Max improvement iterations", "JARVIS_MAX_CRITIC_ITER"),
    # Event bus
    ("events.ttl_seconds", "3600", "int", "Event TTL in seconds", "JARVIS_EVENT_TTL"),
    ("events.max_batch", "50", "int", "Max events per subscribe", "JARVIS_EVENT_BATCH"),
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS configs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        value TEXT NOT NULL,
        value_type TEXT DEFAULT 'str',
        description TEXT,
        env_override TEXT,
        default_value TEXT,
        updated_ts REAL,
        created_ts REAL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS config_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        key TEXT,
        old_value TEXT,
        new_value TEXT,
        source TEXT
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_configs_key ON configs(key)")

    # Seed defaults if empty
    count = db.execute("SELECT COUNT(*) FROM configs").fetchone()[0]
    if count == 0:
        now = time.time()
        for key, value, vtype, desc, env_var in DEFAULT_CONFIGS:
            db.execute(
                """INSERT OR IGNORE INTO configs
                   (key, value, value_type, description, env_override, default_value, updated_ts, created_ts)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (key, value, vtype, desc, env_var, value, now, now)
            )
    db.commit()
    return db


def validate_type(value_str, value_type):
    """Validate and cast value to expected type."""
    try:
        if value_type == "int":
            return int(value_str), True
        elif value_type == "float":
            return float(value_str), True
        elif value_type == "bool":
            if value_str.lower() in ("true", "1", "yes", "on"):
                return True, True
            elif value_str.lower() in ("false", "0", "no", "off"):
                return False, True
            else:
                return None, False
        else:  # str
            return value_str, True
    except (ValueError, TypeError):
        return None, False


def resolve_value(db, key):
    """Resolve config value with env override."""
    row = db.execute(
        "SELECT value, value_type, env_override, description, default_value FROM configs WHERE key = ?",
        (key,)
    ).fetchone()

    if not row:
        return None

    value, vtype, env_var, description, default_value = row

    # Check env override
    source = "database"
    if env_var:
        env_val = os.environ.get(env_var)
        if env_val is not None:
            value = env_val
            source = f"env:{env_var}"

    # Cast type
    typed_value, valid = validate_type(value, vtype)
    if not valid:
        typed_value = value  # Return raw if cast fails

    return {
        "key": key,
        "value": typed_value,
        "raw_value": value,
        "type": vtype,
        "source": source,
        "description": description,
        "default": default_value,
        "env_var": env_var
    }


def get_config(db, key):
    """Get a config value."""
    result = resolve_value(db, key)
    if result:
        return {"status": "ok", **result}

    # Try prefix match
    rows = db.execute(
        "SELECT key FROM configs WHERE key LIKE ? ORDER BY key LIMIT 10",
        (f"{key}%",)
    ).fetchall()

    return {
        "status": "error",
        "error": f"Config key '{key}' not found",
        "suggestions": [r[0] for r in rows]
    }


def set_config(db, key, value):
    """Set a config value."""
    existing = db.execute(
        "SELECT value, value_type FROM configs WHERE key = ?", (key,)
    ).fetchone()

    now = time.time()

    if existing:
        old_value, vtype = existing
        typed_value, valid = validate_type(value, vtype)
        if not valid:
            return {
                "status": "error",
                "error": f"Invalid value '{value}' for type '{vtype}'",
                "expected_type": vtype
            }

        db.execute("UPDATE configs SET value = ?, updated_ts = ? WHERE key = ?",
                    (str(value), now, key))
        db.execute(
            "INSERT INTO config_history (ts, key, old_value, new_value, source) VALUES (?,?,?,?,?)",
            (now, key, old_value, str(value), "cli")
        )
    else:
        # New key - detect type
        vtype = "str"
        try:
            int(value)
            vtype = "int"
        except ValueError:
            try:
                float(value)
                vtype = "float"
            except ValueError:
                if value.lower() in ("true", "false"):
                    vtype = "bool"

        db.execute(
            """INSERT INTO configs (key, value, value_type, description, default_value, updated_ts, created_ts)
               VALUES (?,?,?,?,?,?,?)""",
            (key, value, vtype, "", value, now, now)
        )
        db.execute(
            "INSERT INTO config_history (ts, key, old_value, new_value, source) VALUES (?,?,?,?,?)",
            (now, key, None, value, "cli:new")
        )
        old_value = None

    db.commit()

    return {
        "status": "ok",
        "key": key,
        "old_value": old_value,
        "new_value": value,
        "action": "updated" if existing else "created"
    }


def list_configs(db):
    """List all configs."""
    rows = db.execute(
        "SELECT key, value, value_type, description, env_override FROM configs ORDER BY key"
    ).fetchall()

    configs = []
    for key, value, vtype, desc, env_var in rows:
        resolved = resolve_value(db, key)
        configs.append({
            "key": key,
            "value": resolved["value"] if resolved else value,
            "type": vtype,
            "description": desc,
            "source": resolved["source"] if resolved else "database",
            "env_var": env_var or ""
        })

    # Group by prefix
    groups = {}
    for c in configs:
        prefix = c["key"].split(".")[0]
        groups.setdefault(prefix, []).append(c)

    return {
        "status": "ok",
        "total": len(configs),
        "groups": {k: len(v) for k, v in groups.items()},
        "configs": configs
    }


def export_configs(db):
    """Export all configs as JSON."""
    rows = db.execute(
        "SELECT key, value, value_type, description, env_override, default_value FROM configs ORDER BY key"
    ).fetchall()

    export = {}
    for key, value, vtype, desc, env_var, default in rows:
        typed_value, _ = validate_type(value, vtype)
        export[key] = {
            "value": typed_value if typed_value is not None else value,
            "type": vtype,
            "description": desc,
            "env_var": env_var,
            "default": default
        }

    return {
        "status": "ok",
        "total": len(export),
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "configs": export
    }


def import_configs(db, filepath):
    """Import configs from JSON file."""
    path = Path(filepath)
    if not path.exists():
        return {"status": "error", "error": f"File not found: {filepath}"}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"status": "error", "error": f"Invalid JSON: {e}"}

    configs = data.get("configs", data)
    imported = 0
    errors = []

    for key, info in configs.items():
        if isinstance(info, dict):
            value = str(info.get("value", ""))
        else:
            value = str(info)

        result = set_config(db, key, value)
        if result["status"] == "ok":
            imported += 1
        else:
            errors.append({"key": key, "error": result.get("error", "")})

    return {
        "status": "ok",
        "imported": imported,
        "errors": errors,
        "total_in_file": len(configs)
    }


def once(db):
    """Run once: show config summary."""
    total = db.execute("SELECT COUNT(*) FROM configs").fetchone()[0]
    groups = db.execute(
        "SELECT SUBSTR(key, 1, INSTR(key, '.') - 1) AS grp, COUNT(*) FROM configs GROUP BY grp ORDER BY grp"
    ).fetchall()

    history_count = db.execute("SELECT COUNT(*) FROM config_history").fetchone()[0]

    # Count env overrides active
    env_overrides = 0
    rows = db.execute("SELECT env_override FROM configs WHERE env_override IS NOT NULL AND env_override != ''").fetchall()
    for row in rows:
        if os.environ.get(row[0]):
            env_overrides += 1

    return {
        "status": "ok",
        "mode": "once",
        "script": "jarvis_config_center.py (#194)",
        "total_configs": total,
        "groups": {g[0]: g[1] for g in groups if g[0]},
        "active_env_overrides": env_overrides,
        "total_changes": history_count,
        "db_path": str(DB_PATH)
    }


def main():
    parser = argparse.ArgumentParser(
        description="jarvis_config_center.py (#194) — Unified configuration center"
    )
    parser.add_argument("--get", type=str, metavar="KEY",
                        help="Get config value by key")
    parser.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"),
                        help="Set config key to value")
    parser.add_argument("--list", action="store_true",
                        help="List all configs")
    parser.add_argument("--export", action="store_true",
                        help="Export all configs as JSON")
    parser.add_argument("--import-file", type=str, metavar="FILE",
                        help="Import configs from JSON file")
    parser.add_argument("--once", action="store_true",
                        help="Run once: show config summary")
    args = parser.parse_args()

    db = init_db()

    if args.get:
        result = get_config(db, args.get)
    elif args.set:
        result = set_config(db, args.set[0], args.set[1])
    elif args.list:
        result = list_configs(db)
    elif args.export:
        result = export_configs(db)
    elif args.import_file:
        result = import_configs(db, args.import_file)
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        db.close()
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
