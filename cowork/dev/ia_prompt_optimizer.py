#!/usr/bin/env python3
"""ia_prompt_optimizer.py — Optimise les prompts systeme.

Teste variantes, mesure qualite reponses, A/B test iteratif.

Usage:
    python dev/ia_prompt_optimizer.py --once
    python dev/ia_prompt_optimizer.py --analyze
    python dev/ia_prompt_optimizer.py --optimize "PROMPT"
    python dev/ia_prompt_optimizer.py --report
"""
import argparse
import json
import os
import sqlite3
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "prompt_optimizer.db"
M1_URL = "http://127.0.0.1:1234/api/v1/chat"
OL1_URL = "http://127.0.0.1:11434/api/chat"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, original_prompt TEXT, variant_type TEXT,
        variant_prompt TEXT, score REAL, latency_ms REAL,
        response_len INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS best_prompts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, task TEXT, best_prompt TEXT, score REAL)""")
    db.commit()
    return db


def query_m1(prompt, timeout=20):
    """Query M1."""
    try:
        data = json.dumps({
            "model": "qwen3-8b", "input": f"/nothink\n{prompt}",
            "temperature": 0.3, "max_output_tokens": 512, "stream": False, "store": False,
        }).encode()
        req = urllib.request.Request(M1_URL, data=data, headers={"Content-Type": "application/json"})
        start = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read().decode())
            latency = (time.time() - start) * 1000
            for item in reversed(result.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return c.get("text", ""), latency
        return "", (time.time() - start) * 1000
    except Exception:
        return "", 0


def generate_variants(prompt):
    """Generate 3 variants of a prompt."""
    variants = []

    # Variant 1: Shorter
    shorter = prompt
    for filler in ["s'il te plait ", "please ", "je voudrais que tu ", "peux-tu "]:
        shorter = shorter.replace(filler, "")
    if shorter != prompt:
        variants.append({"type": "shorter", "prompt": shorter.strip()})

    # Variant 2: More structured (add format)
    structured = prompt + "\n\nReponds en JSON structure avec les champs pertinents."
    variants.append({"type": "structured", "prompt": structured})

    # Variant 3: With role
    role_prompt = f"Tu es un expert technique JARVIS. {prompt}"
    variants.append({"type": "with_role", "prompt": role_prompt})

    return variants


def score_response(response, prompt):
    """Score a response quality (0-1)."""
    if not response:
        return 0.0

    score = 0.0
    # Length appropriateness
    if 50 < len(response) < 2000:
        score += 0.3
    elif len(response) >= 20:
        score += 0.15

    # Contains structured data
    if any(marker in response for marker in ["{", "```", "- ", "1."]):
        score += 0.2

    # Relevance (keywords from prompt in response)
    prompt_words = set(prompt.lower().split())
    response_words = set(response.lower().split())
    overlap = len(prompt_words & response_words) / max(len(prompt_words), 1)
    score += min(overlap * 0.3, 0.3)

    # No error indicators
    if not any(err in response.lower() for err in ["error", "erreur", "sorry", "cannot"]):
        score += 0.2

    return min(round(score, 3), 1.0)


def do_optimize(prompt=None):
    """Run optimization experiment."""
    db = init_db()

    test_prompts = []
    if prompt:
        test_prompts = [prompt]
    else:
        # Default test prompts
        test_prompts = [
            "Liste les 5 commandes les plus utiles pour surveiller un cluster GPU",
            "Explique comment optimiser la latence d'un pipeline voix vers action",
            "Genere un script Python qui monitore la temperature GPU",
        ]

    results = []
    for p in test_prompts:
        # Test original
        orig_resp, orig_lat = query_m1(p)
        orig_score = score_response(orig_resp, p)

        experiment = {
            "prompt": p[:80],
            "original_score": orig_score,
            "original_latency_ms": round(orig_lat, 1),
            "variants": [],
        }

        # Test variants
        variants = generate_variants(p)
        best_variant = None
        best_score = orig_score

        for v in variants:
            resp, lat = query_m1(v["prompt"])
            v_score = score_response(resp, p)

            db.execute(
                "INSERT INTO experiments (ts, original_prompt, variant_type, variant_prompt, score, latency_ms, response_len) VALUES (?,?,?,?,?,?,?)",
                (time.time(), p[:200], v["type"], v["prompt"][:200], v_score, lat, len(resp))
            )

            variant_result = {
                "type": v["type"], "score": v_score,
                "latency_ms": round(lat, 1), "delta": round(v_score - orig_score, 3),
            }
            experiment["variants"].append(variant_result)

            if v_score > best_score:
                best_score = v_score
                best_variant = v["type"]

        experiment["best_variant"] = best_variant or "original"
        experiment["improvement"] = round(best_score - orig_score, 3)
        results.append(experiment)

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "prompts_tested": len(results),
        "improved": sum(1 for r in results if r["improvement"] > 0),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="IA Prompt Optimizer")
    parser.add_argument("--once", "--analyze", action="store_true", help="Run optimization")
    parser.add_argument("--optimize", metavar="PROMPT", help="Optimize specific prompt")
    parser.add_argument("--report", action="store_true", help="Report")
    args = parser.parse_args()

    result = do_optimize(args.optimize)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
