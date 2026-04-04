"""OpenClaw Provider Health Check — DevOps Monitoring.

Vérifie tous les providers LLM configurés dans openclaw.json.
Retourne un rapport JSON avec latence, status, modèles disponibles.

Usage:
    python scripts/openclaw_provider_health.py [--json] [--fix]
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

OPENCLAW_JSON = Path.home() / ".openclaw" / "openclaw.json"
TIMEOUT = 5


def check_provider(name: str, config: dict) -> dict:
    """Check a single provider's health."""
    base_url = config.get("baseUrl", "")
    api_type = config.get("api", "openai-completions")
    result = {
        "provider": name,
        "baseUrl": base_url,
        "status": "unknown",
        "latency_ms": -1,
        "models_loaded": 0,
        "error": None,
    }

    if not base_url:
        result["status"] = "no_url"
        return result

    # Determine health endpoint
    # Detect Ollama by api type OR by well-known port 11434
    is_ollama = api_type == "ollama" or ":11434" in base_url
    if is_ollama:
        host = base_url.rstrip("/").removesuffix("/v1")
        health_url = f"{host}/api/tags"
    elif "/v1" in base_url:
        health_url = f"{base_url.rstrip('/v1')}/v1/models" if not base_url.endswith("/v1") else f"{base_url}/models"
    else:
        health_url = f"{base_url}/models"

    # Special handling for HuggingFace (needs auth)
    if "huggingface" in base_url or "router.huggingface" in base_url:
        api_key = config.get("apiKey", "")
        if not api_key or api_key.startswith("hf_VOTRE"):
            result["status"] = "no_token"
            result["error"] = "HuggingFace token not configured"
            return result

    try:
        start = time.time()
        req = urllib.request.Request(health_url, method="GET")
        api_key = config.get("apiKey", "")
        if api_key and not api_key.startswith("hf_VOTRE"):
            req.add_header("Authorization", f"Bearer {api_key}")
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        latency = (time.time() - start) * 1000
        data = json.loads(resp.read())

        result["latency_ms"] = round(latency)
        result["status"] = "healthy"

        # Count models
        if is_ollama:
            result["models_loaded"] = len(data.get("models", []))
        else:
            models = data.get("data", data.get("models", []))
            if isinstance(models, list):
                loaded = [m for m in models if m.get("loaded_instances") or m.get("id")]
                result["models_loaded"] = len(loaded)

    except urllib.error.URLError as e:
        result["status"] = "offline"
        result["error"] = str(e.reason)[:100]
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:100]

    return result


def run_health_check(as_json: bool = False, fix: bool = False) -> list[dict]:
    """Run health check on all providers."""
    if not OPENCLAW_JSON.exists():
        print("ERROR: openclaw.json not found")
        sys.exit(1)

    config = json.loads(OPENCLAW_JSON.read_text(encoding="utf-8"))
    providers = config.get("models", {}).get("providers", {})

    results = []
    for name, pconfig in providers.items():
        result = check_provider(name, pconfig)
        results.append(result)

    if as_json:
        print(json.dumps(results, indent=2))
    else:
        print(f"{'Provider':<15} {'Status':<12} {'Latency':<10} {'Models':<8} {'Error'}")
        print("-" * 70)
        for r in results:
            latency = f"{r['latency_ms']}ms" if r["latency_ms"] >= 0 else "-"
            error = r.get("error", "") or ""
            status_icon = {"healthy": "+", "offline": "X", "error": "!", "no_token": "?"}.get(r["status"], "?")
            print(f"{r['provider']:<15} {status_icon} {r['status']:<10} {latency:<10} {r['models_loaded']:<8} {error[:30]}")

    # Summary
    healthy = sum(1 for r in results if r["status"] == "healthy")
    total = len(results)
    if not as_json:
        print(f"\n{healthy}/{total} providers healthy")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenClaw Provider Health Check")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix offline providers")
    args = parser.parse_args()
    results = run_health_check(args.json, args.fix)
    healthy = sum(1 for r in results if r["status"] == "healthy")
    sys.exit(0 if healthy > 0 else 1)
