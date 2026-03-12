#!/usr/bin/env python3
"""dynamic_timeout.py — Adaptive timeout system for cluster dispatches.

Implements the "door metaphor": timeout adapts to the size and complexity
of the request, like holding a door open longer when carrying boxes.

Factors that increase timeout:
- Long prompts (more tokens to process)
- Complex task types (reasoning, consensus, architecture)
- Slow nodes (M2/M3 with deepseek-r1 reasoning)
- High expected output (code generation, analysis)
- Context window pressure (near max_ctx)

Factors that decrease timeout:
- Short prompts (simple questions)
- Fast nodes (M1, OL1)
- Cached responses available
- Historical fast responses for this type

The system learns from dispatch history to auto-tune.

CLI:
    --compute TYPE PROMPT [NODE] : Compute optimal timeout
    --learn                      : Learn from dispatch history
    --matrix                     : Show timeout matrix
    --test                       : Test with sample prompts

Stdlib-only (json, argparse, sqlite3, math).
"""

import argparse
import json
import math
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
GAPS_DB = DATA_DIR / "cowork_gaps.db"
from _paths import ETOILE_DB

# Base timeouts per task type (seconds) - the "normal walking speed"
BASE_TIMEOUTS = {
    "classifier": 5,
    "simple":     10,
    "quick":      8,
    "web":        15,
    "system":     15,
    "data":       20,
    "devops":     20,
    "creative":   30,
    "code":       30,
    "math":       30,
    "analysis":   45,
    "trading":    45,
    "architecture": 60,
    "security":   45,
    "reasoning":  60,
    "consensus":  90,
    "deep":       90,
}

# Node speed factors - how much slower than baseline
NODE_FACTORS = {
    "M1":  1.0,    # Fastest (qwen3-8b, 65 tok/s)
    "OL1": 1.2,    # Fast (qwen3:1.7b, 84 tok/s but smaller)
    "M2":  2.5,    # Slow (deepseek-r1 reasoning, 44 tok/s but thinks)
    "M3":  3.0,    # Slowest (deepseek-r1, 33 tok/s sequential)
}

# Max context windows (tokens)
NODE_CTX = {
    "M1":  32768,
    "OL1": 8192,
    "M2":  27000,
    "M3":  25000,
}

# Limits
MIN_TIMEOUT = 3
MAX_TIMEOUT = 180
MARGIN_FACTOR = 1.5  # Add 50% margin to computed timeout


def get_db(path):
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def estimate_tokens(text):
    """Rough token count (1 token ~ 4 chars or 0.75 words)."""
    return max(len(text) // 4, len(text.split()))


def estimate_prompt_complexity(prompt):
    """Score prompt complexity 1.0 (simple) to 3.0 (very complex)."""
    tokens = estimate_tokens(prompt)

    # Length factor
    if tokens < 20:
        length_factor = 1.0
    elif tokens < 100:
        length_factor = 1.3
    elif tokens < 500:
        length_factor = 1.7
    elif tokens < 2000:
        length_factor = 2.2
    else:
        length_factor = 3.0

    # Content complexity indicators
    complexity_keywords = [
        "analyse", "analyze", "compare", "explain", "debug", "refactor",
        "architecture", "design", "consensus", "review", "audit",
        "complex", "detailed", "comprehensive", "all", "every",
        "step by step", "reasoning", "think", "prove", "demonstrate",
    ]
    simple_keywords = [
        "ok", "yes", "no", "hello", "bonjour", "hi",
        "nombre", "number", "un mot", "one word", "uniquement",
    ]

    prompt_lower = prompt.lower()
    complexity_hits = sum(1 for k in complexity_keywords if k in prompt_lower)
    simple_hits = sum(1 for k in simple_keywords if k in prompt_lower)

    if simple_hits > 0 and complexity_hits == 0:
        content_factor = 0.7
    elif complexity_hits >= 3:
        content_factor = 2.5
    elif complexity_hits >= 1:
        content_factor = 1.5
    else:
        content_factor = 1.0

    return round(length_factor * content_factor, 2)


def estimate_output_size(task_type, prompt):
    """Estimate expected output size factor."""
    output_factors = {
        "simple":       0.5,   # Short answer
        "quick":        0.5,
        "classifier":   0.3,
        "math":         0.7,
        "system":       1.0,
        "web":          1.2,
        "data":         1.3,
        "code":         2.0,   # Code can be long
        "creative":     1.5,
        "analysis":     2.0,
        "trading":      1.5,
        "architecture": 2.5,
        "reasoning":    2.0,
        "security":     1.8,
        "consensus":    2.5,
        "deep":         3.0,
    }
    base = output_factors.get(task_type, 1.0)

    # Adjust by prompt signals
    prompt_lower = prompt.lower()
    if any(k in prompt_lower for k in ["uniquement", "un mot", "nombre", "only", "one word"]):
        base *= 0.3
    if any(k in prompt_lower for k in ["detailed", "complete", "all", "comprehensive", "detaille"]):
        base *= 1.5

    return round(base, 2)


def context_pressure(prompt, node):
    """Compute context pressure (how close to max_ctx)."""
    tokens = estimate_tokens(prompt)
    max_ctx = NODE_CTX.get(node, 32768)
    ratio = tokens / max_ctx

    if ratio > 0.8:
        return 3.0   # Critical - very slow, risk of context exceeded
    elif ratio > 0.5:
        return 2.0   # High pressure
    elif ratio > 0.3:
        return 1.5   # Moderate
    else:
        return 1.0   # Normal


def get_historical_timeout(task_type, node):
    """Get learned timeout from dispatch history."""
    try:
        edb = get_db(ETOILE_DB)
        has = edb.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='agent_dispatch_log'"
        ).fetchone()[0]
        if not has:
            edb.close()
            return None

        rows = edb.execute("""
            SELECT latency_ms, success FROM agent_dispatch_log
            WHERE classified_type=? AND node=? AND latency_ms > 0
            ORDER BY id DESC LIMIT 20
        """, (task_type, node)).fetchall()
        edb.close()

        if len(rows) < 3:
            return None

        latencies = [r["latency_ms"] for r in rows if r["success"]]
        if not latencies:
            return None

        # P95 of successful latencies
        latencies.sort()
        p95_idx = max(0, int(len(latencies) * 0.95) - 1)
        p95 = latencies[p95_idx]

        # Add margin
        return round(p95 / 1000 * MARGIN_FACTOR + 2, 1)

    except Exception:
        return None


def compute_timeout(task_type, prompt, node="M1"):
    """Compute optimal timeout using all factors — the "door" algorithm.

    Like a door:
    - Quick person (simple prompt) = door opens briefly (low timeout)
    - Person carrying boxes (complex prompt) = door stays open longer
    - Slow person (M2/M3) = door stays open even longer
    - Crowded hallway (context pressure) = extra patience needed
    """
    # 1. Base timeout from task type
    base = BASE_TIMEOUTS.get(task_type, 30)

    # 2. Node speed factor (M2/M3 are slower "walkers")
    node_factor = NODE_FACTORS.get(node, 1.5)

    # 3. Prompt complexity (how many "boxes" they're carrying)
    complexity = estimate_prompt_complexity(prompt)

    # 4. Expected output size (bigger response = door open longer)
    output_factor = estimate_output_size(task_type, prompt)

    # 5. Context pressure (crowded hallway = slower)
    ctx_pressure = context_pressure(prompt, node)

    # 6. Historical data (learn from past trips through the door)
    historical = get_historical_timeout(task_type, node)

    # Compute adaptive timeout
    # Formula: base * node_speed * sqrt(complexity * output_factor) * ctx_pressure
    computed = base * node_factor * math.sqrt(complexity * output_factor) * ctx_pressure

    # If we have historical data, blend 50/50
    if historical:
        computed = (computed + historical) / 2

    # Apply limits
    timeout = max(MIN_TIMEOUT, min(round(computed, 1), MAX_TIMEOUT))

    return {
        "timeout_s": timeout,
        "task_type": task_type,
        "node": node,
        "factors": {
            "base": base,
            "node_factor": node_factor,
            "complexity": complexity,
            "output_factor": output_factor,
            "ctx_pressure": ctx_pressure,
            "historical": historical,
        },
        "prompt_tokens": estimate_tokens(prompt),
        "formula": f"{base} * {node_factor} * sqrt({complexity} * {output_factor}) * {ctx_pressure}",
    }


def learn_timeouts():
    """Learn optimal timeouts from dispatch history."""
    try:
        edb = get_db(ETOILE_DB)
        gaps = get_db(GAPS_DB)

        rows = edb.execute("""
            SELECT classified_type, node, latency_ms, success
            FROM agent_dispatch_log
            WHERE latency_ms > 0
            ORDER BY id DESC LIMIT 500
        """).fetchall()

        # Group by (type, node)
        groups = {}
        for r in rows:
            key = (r["classified_type"] or "unknown", r["node"] or "unknown")
            groups.setdefault(key, []).append({
                "latency_ms": r["latency_ms"],
                "success": r["success"],
            })

        learned = 0
        now = datetime.now().isoformat()
        for (task_type, node), entries in groups.items():
            if len(entries) < 3:
                continue

            ok_latencies = [e["latency_ms"] for e in entries if e["success"]]
            if not ok_latencies:
                continue

            ok_latencies.sort()
            p50 = ok_latencies[len(ok_latencies) // 2]
            p95 = ok_latencies[max(0, int(len(ok_latencies) * 0.95) - 1)]
            max_lat = max(ok_latencies)
            recommended = round(p95 / 1000 * MARGIN_FACTOR + 2, 1)
            recommended = max(MIN_TIMEOUT, min(recommended, MAX_TIMEOUT))

            gaps.execute("""
                INSERT INTO timeout_configs
                (timestamp, pattern, node, recommended_timeout_s, p50_latency_ms,
                 p95_latency_ms, max_latency_ms, sample_count, applied)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (now, task_type, node, recommended, p50, p95, max_lat, len(ok_latencies)))
            learned += 1

        gaps.commit()
        gaps.close()
        edb.close()

        print(f"Learned {learned} timeout configs from {len(rows)} dispatches")
        return learned

    except Exception as e:
        print(f"Error: {e}")
        return 0


def show_matrix():
    """Show timeout matrix for all type/node combos."""
    print("=== Dynamic Timeout Matrix (seconds) ===")
    print(f"  {'Type':15} {'M1':>6} {'OL1':>6} {'M2':>6} {'M3':>6}")
    print(f"  {'-'*15} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")

    sample_prompt = "/nothink\nDo the task."
    for task_type in sorted(BASE_TIMEOUTS.keys()):
        vals = []
        for node in ["M1", "OL1", "M2", "M3"]:
            result = compute_timeout(task_type, sample_prompt, node)
            vals.append(f"{result['timeout_s']:>5.0f}s")
        print(f"  {task_type:15} {'  '.join(vals)}")

    print(f"\n  Context pressure example (long prompt):")
    long_prompt = "x " * 5000  # ~5000 tokens
    for node in ["M1", "OL1"]:
        result = compute_timeout("code", long_prompt, node)
        print(f"    {node}: {result['timeout_s']}s (ctx_pressure={result['factors']['ctx_pressure']})")


def run_test():
    """Test timeout computation with various scenarios."""
    print("=== Dynamic Timeout Tests ===\n")

    tests = [
        ("simple", "OK", "M1", "Ultra-simple"),
        ("simple", "Quelle est la capitale de la France?", "OL1", "Simple question"),
        ("code", "/nothink\nEcris une fonction fibonacci recursive en Python", "M1", "Code M1"),
        ("code", "/nothink\nEcris une fonction fibonacci recursive en Python", "M2", "Code M2 (slower)"),
        ("reasoning", "Explique en detail pourquoi P!=NP est un probleme ouvert. Analyse complete.", "M2", "Complex reasoning"),
        ("analysis", "Compare en detail les architectures microservices vs monolithique. Avantages, inconvenients, cas d'usage, exemples, metriques.", "M1", "Deep analysis"),
        ("simple", "OK", "M3", "Simple on slow node"),
        ("consensus", "Analyse complete du marche crypto avec prediction et strategie detaillee pour les 3 prochains mois", "M1", "Heavy consensus"),
    ]

    for task_type, prompt, node, desc in tests:
        result = compute_timeout(task_type, prompt, node)
        t = result["timeout_s"]
        c = result["factors"]["complexity"]
        print(f"  {desc:30} -> {t:5.0f}s  (type={task_type}, node={node}, complexity={c})")

    print(f"\n  Context pressure tests:")
    for size in [100, 1000, 5000, 20000]:
        prompt = "x " * size
        result = compute_timeout("code", prompt, "OL1")
        print(f"    {size} tokens -> {result['timeout_s']}s (pressure={result['factors']['ctx_pressure']})")


def main():
    parser = argparse.ArgumentParser(description="Dynamic Timeout Manager")
    parser.add_argument("--compute", nargs="+", metavar=("TYPE", "PROMPT"), help="Compute timeout")
    parser.add_argument("--learn", action="store_true", help="Learn from history")
    parser.add_argument("--matrix", action="store_true", help="Show timeout matrix")
    parser.add_argument("--test", action="store_true", help="Test scenarios")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if not any([args.compute, args.learn, args.matrix, args.test]):
        parser.print_help()
        sys.exit(1)

    if args.learn:
        learn_timeouts()
        return

    if args.matrix:
        show_matrix()
        return

    if args.test:
        run_test()
        return

    if args.compute:
        if len(args.compute) >= 2:
            task_type = args.compute[0]
            prompt = args.compute[1]
            node = args.compute[2] if len(args.compute) > 2 else "M1"
        else:
            task_type = args.compute[0]
            prompt = "default prompt"
            node = "M1"

        result = compute_timeout(task_type, prompt, node)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Timeout: {result['timeout_s']}s for {task_type}/{node}")
            print(f"  Factors: {json.dumps(result['factors'])}")


if __name__ == "__main__":
    main()
