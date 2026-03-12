#!/usr/bin/env python3
"""Cluster Scaler — adjust parallel slots and VRAM allocation."""
import argparse, json, urllib.request

def get_m1_config() -> dict:
    try:
        req = urllib.request.Request("http://127.0.0.1:1234/api/v1/models")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        models = data.get("data", data.get("models", []))
        return {"loaded_models": len(models), "models": [m.get("id", "?") for m in models]}
    except Exception as e:
        return {"error": str(e)}

def get_ollama_config() -> dict:
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return {"models": len(data.get("models", []))}
    except Exception as e:
        return {"error": str(e)}

def main():
    parser = argparse.ArgumentParser(description="Cluster scaling info")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    m1 = get_m1_config()
    ol1 = get_ollama_config()

    report = {
        "m1_lmstudio": m1,
        "ol1_ollama": ol1,
        "recommendations": []
    }

    if m1.get("loaded_models", 0) > 3:
        report["recommendations"].append("M1: Consider unloading unused models to free VRAM")
    if m1.get("loaded_models", 0) == 1:
        report["recommendations"].append("M1: Only 1 model loaded — room for parallel models")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=== Cluster Scale Report ===")
        print(f"M1: {m1}")
        print(f"OL1: {ol1}")
        for r in report.get("recommendations", []):
            print(f"  >> {r}")

if __name__ == "__main__":
    main()
