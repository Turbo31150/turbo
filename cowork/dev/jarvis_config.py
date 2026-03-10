#!/usr/bin/env python3
"""JARVIS Config Manager — view and update configuration."""
import argparse, json, os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "jarvis_config.json")

DEFAULT_CONFIG = {
    "cluster": {
        "m1": {"host": "127.0.0.1", "port": 1234, "model": "qwen3-8b", "weight": 1.9},
        "ol1": {"host": "127.0.0.1", "port": 11434, "model": "qwen3:1.7b", "weight": 1.4},
        "m2": {"host": "192.168.1.26", "port": 1234, "model": "deepseek-r1-0528-qwen3-8b", "weight": 1.4},
        "m3": {"host": "192.168.1.113", "port": 1234, "model": "deepseek-r1-0528-qwen3-8b", "weight": 1.1},
    },
    "services": {
        "ws_port": 9742,
        "openclaw_port": 18789,
        "dashboard_port": 8080,
        "gemini_proxy_port": 18791,
        "canvas_proxy_port": 18800,
    },
    "trading": {
        "exchange": "mexc",
        "leverage": 10,
        "tp_pct": 0.4,
        "sl_pct": 0.25,
        "size_usdt": 10,
        "min_score": 70,
    }
}

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()

def save_config(config: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description="JARVIS config manager")
    parser.add_argument("--show", action="store_true", help="Show current config")
    parser.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), help="Set config key (dot notation)")
    parser.add_argument("--reset", action="store_true", help="Reset to defaults")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    config = load_config()

    if args.reset:
        save_config(DEFAULT_CONFIG)
        print("Config reset to defaults")
    elif args.set:
        key, value = args.set
        parts = key.split(".")
        target = config
        for p in parts[:-1]:
            target = target.setdefault(p, {})
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
        target[parts[-1]] = value
        save_config(config)
        print(f"Set {key} = {value}")
    else:
        print(json.dumps(config, indent=2))

if __name__ == "__main__":
    main()
