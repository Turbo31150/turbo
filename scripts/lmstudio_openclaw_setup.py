"""
LM Studio model config for OpenClaw compatibility.
Reloads qwen3-8b with optimal params: 65k context, parallel=2.
Run after LM Studio starts (before OpenClaw agents).
"""
import httpx
import sys
import json
import time

LM_URL = "http://127.0.0.1:1234"
MODEL = "qwen3-8b"
TARGET_CTX = 65536
TARGET_PARALLEL = 2

def get_instances():
    r = httpx.get(f"{LM_URL}/api/v1/models", timeout=5)
    data = r.json()
    instances = []
    for m in data.get("data", data.get("models", [])):
        for inst in m.get("loaded_instances", []):
            cfg = inst.get("config", {})
            instances.append({
                "id": inst["id"],
                "ctx": cfg.get("context_length", 0),
                "parallel": cfg.get("parallel", 1),
            })
    return instances

def main():
    try:
        instances = get_instances()
    except Exception as e:
        print(f"LM Studio offline: {e}")
        sys.exit(1)

    # Check if already optimal
    for inst in instances:
        if inst["ctx"] >= TARGET_CTX and inst["parallel"] == TARGET_PARALLEL:
            print(f"OK: {inst['id']} already optimal (ctx={inst['ctx']}, parallel={inst['parallel']})")
            return

    # Unload all qwen3-8b instances
    for inst in instances:
        if MODEL in inst["id"]:
            print(f"Unloading {inst['id']} (ctx={inst['ctx']}, parallel={inst['parallel']})")
            httpx.post(f"{LM_URL}/api/v1/models/unload",
                       json={"instance_id": inst["id"]}, timeout=30)
            time.sleep(1)

    # Load with optimal params
    print(f"Loading {MODEL} with ctx={TARGET_CTX}, parallel={TARGET_PARALLEL}")
    r = httpx.post(f"{LM_URL}/api/v1/models/load",
                   json={"model": MODEL, "context_length": TARGET_CTX,
                         "parallel": TARGET_PARALLEL, "flash_attention": True},
                   timeout=120)
    result = r.json()
    if result.get("status") == "loaded":
        print(f"OK: {result['instance_id']} loaded in {result.get('load_time_seconds', '?')}s")
    else:
        print(f"ERREUR: {result}")
        sys.exit(1)

if __name__ == "__main__":
    main()
