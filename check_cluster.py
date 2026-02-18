"""Check cluster status on M1, M2, and OL1 — Optimized for JARVIS Turbo v10.1."""
import asyncio
import httpx
import time


async def check_lmstudio(c: httpx.AsyncClient, name: str, url: str) -> dict:
    """Check an LM Studio node."""
    result = {"name": name, "url": url, "status": "offline", "models": [], "loaded": []}
    try:
        r = await c.get(f"{url}/api/v1/models")
        models_data = r.json().get("models", [])
        loaded = [m for m in models_data if m.get("loaded_instances")]
        result["status"] = "online"
        result["models"] = [m["key"] for m in loaded]

        # Test inference on first loaded model
        if loaded:
            model_id = loaded[0]["key"]
            # Skip embedding models
            if "embed" in model_id.lower():
                model_id = loaded[1]["key"] if len(loaded) > 1 else model_id

            t0 = time.perf_counter()
            try:
                r2 = await c.post(f"{url}/api/v1/chat", json={
                    "model": model_id,
                    "input": "ping",
                    "temperature": 0.1,
                    "max_output_tokens": 8,
                    "stream": False,
                    "store": False,
                })
                r2.raise_for_status()
                latency = (time.perf_counter() - t0) * 1000
                result["loaded"].append({"model": model_id, "latency_ms": round(latency)})
            except Exception:
                pass
    except Exception as e:
        result["error"] = str(e)
    return result


async def check_ollama(c: httpx.AsyncClient, name: str, url: str) -> dict:
    """Check an Ollama node."""
    result = {"name": name, "url": url, "status": "offline", "models": []}
    try:
        r = await c.get(f"{url}/api/tags")
        data = r.json()
        result["status"] = "online"
        result["models"] = [m["name"] for m in data.get("models", [])]
    except Exception as e:
        result["error"] = str(e)
    return result


async def main():
    nodes = [
        ("M1", "http://10.5.0.2:1234", "lmstudio"),
        ("M2", "http://192.168.1.26:1234", "lmstudio"),
        ("OL1", "http://127.0.0.1:11434", "ollama"),
    ]

    async with httpx.AsyncClient(timeout=15) as c:
        tasks = []
        for name, url, backend in nodes:
            if backend == "lmstudio":
                tasks.append(check_lmstudio(c, name, url))
            else:
                tasks.append(check_ollama(c, name, url))

        results = await asyncio.gather(*tasks)

    print("=" * 60)
    print("  JARVIS Turbo v10.1 — Cluster Health Check")
    print("=" * 60)

    total_models = 0
    online = 0
    for r in results:
        icon = "OK" if r["status"] == "online" else "OFFLINE"
        print(f"\n[{icon}] {r['name']} ({r['url']})")
        if r["status"] == "online":
            online += 1
            print(f"  Models disponibles: {len(r['models'])}")
            for m in r["models"]:
                print(f"    - {m}")
            total_models += len(r["models"])
            if "loaded" in r:
                for loaded in r["loaded"]:
                    print(f"  Inference test: {loaded['model']} -> {loaded['latency_ms']}ms")
        else:
            print(f"  Erreur: {r.get('error', 'inconnu')}")

    print(f"\n{'=' * 60}")
    print(f"  {online}/{len(nodes)} nodes en ligne, {total_models} modeles total")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
