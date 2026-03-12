#!/usr/bin/env python3
"""JARVIS Smart Model Loader — Load/unload models on M1 based on task needs.

Manages the 20 available models on M1 (6 GPU, 46 GB VRAM), loading the right
model for heavy tasks (gpt-oss-20b, qwq-32b, deepseek-r1) and unloading
after use to free VRAM for qwen3-8b (the always-on workhorse).

Usage:
    python scripts/smart_model_loader.py load gpt-oss-20b
    python scripts/smart_model_loader.py load qwq-32b
    python scripts/smart_model_loader.py unload gpt-oss-20b
    python scripts/smart_model_loader.py status
    python scripts/smart_model_loader.py auto "complex architecture question"
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

M1_HOST = "127.0.0.1"
M1_PORT = 1234
ALWAYS_ON = "qwen3-8b"

# Model profiles: which tasks benefit from which model
MODEL_PROFILES = {
    "gpt-oss-20b": {
        "tasks": ["code", "architecture", "complex", "grosse demande"],
        "vram_gb": 14,
        "ctx": 131072,
        "speed": "~20 tok/s",
    },
    "qwq-32b": {
        "tasks": ["reasoning", "math", "logic", "deep-work", "analyse"],
        "vram_gb": 22,
        "ctx": 32768,
        "speed": "~9 tok/s",
    },
    "deepseek-r1-0528-qwen3-8b": {
        "tasks": ["reasoning", "consensus", "verification"],
        "vram_gb": 6,
        "ctx": 32768,
        "speed": "~30 tok/s",
    },
    "qwen3-30b-a3b-instruct-2507": {
        "tasks": ["code", "reasoning", "general"],
        "vram_gb": 20,
        "ctx": 131072,
        "speed": "~9 tok/s",
    },
    "devstral-small-2-24b-instruct-2512": {
        "tasks": ["code", "dev", "refactor"],
        "vram_gb": 16,
        "ctx": 262144,
        "speed": "~15 tok/s",
    },
}


def api_get(path: str, timeout: float = 5.0) -> dict | None:
    try:
        url = f"http://{M1_HOST}:{M1_PORT}{path}"
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def api_post(path: str, data: dict) -> dict | None:
    try:
        url = f"http://{M1_HOST}:{M1_PORT}{path}"
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"API error: {e}")
        return None


def get_models() -> list[dict]:
    """Get models from /v1/models (has IDs) — the standard endpoint."""
    resp = api_get("/v1/models")
    if resp:
        return resp.get("data", [])
    return []


def get_loaded() -> list[str]:
    """Get loaded model IDs from /api/v1/models (has loaded_instances)."""
    resp = api_get("/api/v1/models")
    if not resp:
        return []
    loaded = []
    for m in resp.get("data", resp.get("models", [])):
        instances = m.get("loaded_instances") or []
        for inst in instances:
            iid = inst.get("id", "")
            if iid:
                loaded.append(iid)
    return loaded


def load_model(model_id: str) -> bool:
    print(f"Loading {model_id}...")
    # LM Studio load via sending a chat request with the model
    resp = api_post("/v1/chat/completions", {
        "model": model_id,
        "messages": [{"role": "user", "content": "test"}],
        "max_tokens": 1,
    })
    if resp and resp.get("choices"):
        print(f"  {model_id} loaded successfully")
        return True
    print(f"  Failed to load {model_id}")
    return False


def unload_model(model_id: str) -> bool:
    print(f"Unloading {model_id}...")
    resp = api_post("/v1/models/unload", {"model": model_id})
    if resp:
        print(f"  {model_id} unloaded")
        return True
    # Try alternative endpoint
    resp = api_post(f"/api/v1/models/{model_id}/unload", {})
    if resp:
        print(f"  {model_id} unloaded (alt)")
        return True
    print(f"  Unload may have failed (check LM Studio)")
    return False


def status():
    models = get_models()
    loaded = get_loaded()
    print(f"M1 LM Studio — {len(models)} models, {len(loaded)} loaded")
    print()
    for m in models:
        mid = m.get("id", "?")
        is_loaded = mid in loaded
        profile = MODEL_PROFILES.get(mid, {})
        tasks = ", ".join(profile.get("tasks", []))
        marker = "*** LOADED ***" if is_loaded else ""
        vram = f"{profile.get('vram_gb', '?')} GB" if profile else ""
        print(f"  {'>' if is_loaded else ' '} {mid:<45} {vram:>8}  {marker}")
        if tasks:
            print(f"    tasks: {tasks}")
    print()
    print(f"Always-on: {ALWAYS_ON}")


def auto_select(query: str) -> str | None:
    query_lower = query.lower()
    best_match = None
    best_score = 0

    for model_id, profile in MODEL_PROFILES.items():
        score = 0
        for task in profile["tasks"]:
            if task in query_lower:
                score += 1
        if score > best_score:
            best_score = score
            best_match = model_id

    return best_match


def main():
    parser = argparse.ArgumentParser(description="JARVIS Smart Model Loader")
    parser.add_argument("action", choices=["load", "unload", "status", "auto"], help="Action")
    parser.add_argument("target", nargs="?", help="Model ID or query for auto")
    args = parser.parse_args()

    if args.action == "status":
        status()
    elif args.action == "load":
        if not args.target:
            print("Usage: smart_model_loader.py load <model-id>")
            sys.exit(1)
        load_model(args.target)
    elif args.action == "unload":
        if not args.target:
            print("Usage: smart_model_loader.py unload <model-id>")
            sys.exit(1)
        unload_model(args.target)
    elif args.action == "auto":
        query = args.target or ""
        model = auto_select(query)
        if model:
            loaded = get_loaded()
            if model in loaded:
                print(f"Auto-select: {model} (already loaded)")
            else:
                print(f"Auto-select: {model} for query '{query}'")
                load_model(model)
        else:
            print(f"No model match for '{query}', using {ALWAYS_ON}")


if __name__ == "__main__":
    main()
