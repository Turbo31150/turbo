#!/usr/bin/env python3
"""JARVIS Models — Show loaded models across cluster for Telegram.
Usage: python /home/turbo/jarvis-m1-ops/scripts/jarvis_models_telegram.py
"""
import json, subprocess, sys, time

TIMEOUT = 4

def run(cmd, timeout=TIMEOUT):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout,
                           encoding='utf-8', errors='replace')
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None

def check_lmstudio(name, url):
    r = run(f'curl -s --max-time 3 {url}')
    if not r:
        return name, "OFFLINE", []
    try:
        d = json.loads(r)
        models = d.get("data", d.get("models", []))
        loaded = []
        available = []
        for m in models:
            mid = m.get("key", m.get("id", "?"))
            display = m.get("display_name", mid)
            params = m.get("params_string", "")
            instances = m.get("loaded_instances", [])
            if instances:
                inst = instances[0] if isinstance(instances, list) else instances
                cfg = inst.get("config", inst)
                info = {
                    "id": mid, "display": display, "params": params,
                    "ctx": cfg.get("context_length", "?"),
                    "parallel": cfg.get("parallel", cfg.get("num_parallel", "?")),
                }
                loaded.append(info)
            else:
                available.append({"id": mid, "display": display, "params": params})
        return name, "OK", loaded, available
    except Exception:
        return name, "PARSE_ERROR", []

def check_ollama():
    r = run('curl -s --max-time 3 http://127.0.0.1:11434/api/tags')
    if not r:
        return "OL1", "OFFLINE", []
    try:
        d = json.loads(r)
        models = []
        for m in d.get("models", []):
            size_gb = round(m.get("size", 0) / (1024**3), 1)
            models.append({"name": m.get("name", "?"), "size_gb": size_gb, "family": m.get("details", {}).get("family", "")})
        return "OL1", "OK", models
    except Exception:
        return "OL1", "PARSE_ERROR", []

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    t0 = time.time()
    lines = ["JARVIS MODELS"]

    # M1
    result = check_lmstudio("M1", "http://127.0.0.1:1234/api/v1/models")
    if result[1] == "OK":
        loaded, avail = result[2], result[3] if len(result) > 3 else []
        lines.append(f"\nM1 (127.0.0.1:1234) — {len(loaded)} loaded, {len(avail)} available")
        for m in loaded:
            lines.append(f"  * {m['display']} [{m['params']}] (ctx={m.get('ctx','?')}, parallel={m.get('parallel','?')})")
        for m in avail[:5]:
            lines.append(f"    {m['display']} [{m['params']}]")
    else:
        lines.append(f"\nM1: {result[1]}")

    # OL1
    result = check_ollama()
    if result[1] == "OK":
        lines.append(f"\nOL1 (127.0.0.1:11434) — {len(result[2])} models")
        for m in result[2]:
            lines.append(f"  * {m['name']} ({m['size_gb']}GB, {m['family']})")
    else:
        lines.append(f"\nOL1: {result[1]}")

    # M2
    result = check_lmstudio("M2", "http://192.168.1.26:1234/api/v1/models")
    if result[1] == "OK":
        loaded = result[2]
        lines.append(f"\nM2 (192.168.1.26:1234) — {len(loaded)} loaded")
        for m in loaded:
            lines.append(f"  * {m['id']}")
    else:
        lines.append(f"\nM2: {result[1]}")

    # M3
    result = check_lmstudio("M3", "http://192.168.1.113:1234/api/v1/models")
    if result[1] == "OK":
        loaded = result[2]
        lines.append(f"\nM3 (192.168.1.113:1234) — {len(loaded)} loaded")
        for m in loaded:
            lines.append(f"  * {m['id']}")
    else:
        lines.append(f"\nM3: {result[1]}")

    elapsed = round(time.time() - t0, 1)
    lines.append(f"\n{elapsed}s")
    print("\n".join(lines))
