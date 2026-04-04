"""OpenClaw Smoke Test — DevOps End-to-End Provider Validation.

Teste chaque provider avec un vrai appel inference.
Verifie: connectivity, auth, inference, latence, format reponse.

Usage:
    python scripts/openclaw_smoke_test.py [--json] [--timeout 15]
"""
import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

OPENCLAW_JSON = Path.home() / ".openclaw" / "openclaw.json"
DEFAULT_TIMEOUT = 15

# One test model per provider — names MUST match openclaw.json providers
# Models use full IDs as shown by /v1/models (vendor/model format)
PROVIDER_TESTS = {
    "lmstudio": {
        "model": "qwen/qwen3-8b",
        "format": "lmstudio",
    },
    "m2-deepseek": {
        "model": "deepseek/deepseek-r1-0528-qwen3-8b",
        "format": "lmstudio",
    },
    "m3-deepseek": {
        "model": "deepseek/deepseek-r1-0528-qwen3-8b",
        "format": "lmstudio",
    },
    "ollama": {
        "model": "gemma3:4b",
        "format": "ollama",
    },
}

PROMPT = "Reply with exactly one word: PONG"


def build_payload(fmt: str, model: str) -> tuple[str, bytes]:
    """Build request URL path and body for each API format."""
    if fmt == "lmstudio":
        # deepseek-r1 models need reasoning (no /nothink), qwen3 uses /nothink
        needs_think = "deepseek" in model.lower() or "r1" in model.lower()
        prefix = "" if needs_think else "/nothink\n"
        body = {
            "model": model,
            "input": f"{prefix}{PROMPT}",
            "temperature": 0.1,
            "max_output_tokens": 512 if needs_think else 20,
            "stream": False,
            "store": False,
        }
        return "/api/v1/chat", json.dumps(body).encode()
    elif fmt == "ollama":
        body = {
            "model": model,
            "messages": [{"role": "user", "content": PROMPT}],
            "stream": False,
        }
        return "/api/chat", json.dumps(body).encode()
    else:  # openai
        body = {
            "model": model,
            "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": 20,
            "temperature": 0.1,
        }
        return "/v1/chat/completions", json.dumps(body).encode()


def extract_response(fmt: str, data: dict) -> str:
    """Extract text content from API response."""
    if fmt == "lmstudio":
        for item in data.get("output", []):
            if item.get("type") == "message":
                content = item.get("content", "")
                if isinstance(content, list):
                    for c in content:
                        if c.get("type") == "output_text":
                            return c.get("text", "").strip()
                elif isinstance(content, str):
                    return content.strip()
        # Fallback: reasoning block
        for item in data.get("output", []):
            if item.get("type") == "reasoning":
                return "[reasoning]"
        return ""
    elif fmt == "ollama":
        return data.get("message", {}).get("content", "").strip()
    else:  # openai
        choices = data.get("choices", [{}])
        return choices[0].get("message", {}).get("content", "").strip() if choices else ""


def smoke_test_provider(name: str, config: dict, test_cfg: dict, timeout: int) -> dict:
    """Run smoke test on a single provider."""
    base_url = config.get("baseUrl", "").rstrip("/")
    api_key = config.get("apiKey", "")
    fmt = test_cfg["format"]
    model = test_cfg["model"]

    result = {
        "provider": name,
        "model": model,
        "status": "unknown",
        "latency_ms": -1,
        "response": "",
        "pong": False,
        "error": None,
    }

    if not base_url:
        result["status"] = "no_url"
        return result

    path, body = build_payload(fmt, model)

    # LM Studio: baseUrl ends with /v1 (OpenAI compat) but native API is /api/v1/chat
    # Strip /v1 suffix to get the host root, then append the correct path
    if fmt == "lmstudio":
        host_root = base_url.removesuffix("/v1").removesuffix("/")
        url = host_root + path
    elif fmt == "openai" and base_url.endswith("/v1"):
        url = base_url + path.replace("/v1", "")
    else:
        url = base_url + path

    try:
        start = time.time()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        if api_key and not api_key.startswith("hf_VOTRE"):
            req.add_header("Authorization", f"Bearer {api_key}")

        resp = urllib.request.urlopen(req, timeout=timeout)
        latency = (time.time() - start) * 1000
        data = json.loads(resp.read())

        result["latency_ms"] = round(latency)
        text = extract_response(fmt, data)
        result["response"] = text[:100]
        result["pong"] = "pong" in text.lower()
        result["status"] = "pass" if result["pong"] else "partial"

    except urllib.error.HTTPError as e:
        result["status"] = "http_error"
        result["error"] = f"{e.code} {e.reason}"
    except urllib.error.URLError as e:
        result["status"] = "offline"
        result["error"] = str(e.reason)[:100]
    except TimeoutError:
        result["status"] = "timeout"
        result["error"] = f">{timeout}s"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:100]

    return result


def run_smoke_tests(as_json: bool = False, timeout: int = DEFAULT_TIMEOUT) -> list[dict]:
    """Run smoke tests on all providers."""
    if not OPENCLAW_JSON.exists():
        print("ERROR: openclaw.json not found")
        sys.exit(1)

    config = json.loads(OPENCLAW_JSON.read_text(encoding="utf-8"))
    providers = config.get("models", {}).get("providers", {})

    results = []
    for name, test_cfg in PROVIDER_TESTS.items():
        pconfig = providers.get(name, {})
        if not pconfig:
            results.append({"provider": name, "status": "not_configured", "pong": False})
            continue
        result = smoke_test_provider(name, pconfig, test_cfg, timeout)
        results.append(result)
        if not as_json:
            icon = "+" if result["pong"] else ("~" if result["status"] == "partial" else "X")
            latency = f"{result['latency_ms']}ms" if result["latency_ms"] >= 0 else "-"
            err = result.get("error", "") or ""
            resp = result.get("response", "")[:30]
            print(f"  {icon} {name:<15} {result['model']:<35} {latency:<10} {resp or err}")

    if as_json:
        print(json.dumps(results, indent=2))
    else:
        passed = sum(1 for r in results if r["pong"])
        partial = sum(1 for r in results if r["status"] == "partial")
        total = len(results)
        print(f"\n  {passed}/{total} PASS | {partial} PARTIAL | {total - passed - partial} FAIL")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenClaw Smoke Test")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Timeout per provider")
    args = parser.parse_args()

    if not args.json:
        print("OpenClaw Smoke Test — inference E2E")
        print("-" * 70)
    results = run_smoke_tests(args.json, args.timeout)
    passed = sum(1 for r in results if r.get("pong"))
    sys.exit(0 if passed > 0 else 1)
