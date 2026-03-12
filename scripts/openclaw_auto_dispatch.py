"""OpenClaw Auto-Dispatch — Automatically routes incoming messages to specialized agents.

This script runs as a daemon alongside OpenClaw gateway. It:
1. Monitors incoming messages via OpenClaw API
2. Classifies each message using the JARVIS bridge
3. Dispatches to the optimal agent
4. Logs all routing decisions to etoile.db

Usage:
    uv run python scripts/openclaw_auto_dispatch.py
    uv run python scripts/openclaw_auto_dispatch.py --test "ecris du code Python"
    uv run python scripts/openclaw_auto_dispatch.py --audit
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Add turbo root to path
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.openclaw_bridge import OpenClawBridge, INTENT_TO_AGENT


def test_routing(text: str):
    """Test routing for a single message."""
    bridge = OpenClawBridge()
    result = bridge.route(text, use_deep=True)
    print(f"  Text:       {text}")
    print(f"  Intent:     {result.intent}")
    print(f"  Agent:      {result.agent}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Source:     {result.source}")
    print(f"  Latency:    {result.latency_ms:.1f}ms")
    print(f"  Fallback:   {result.fallback_used}")
    return result


def audit_agents():
    """Full audit of OpenClaw agents configuration."""
    import os
    agents_dir = Path(os.path.expanduser("~/.openclaw/agents"))

    print("=" * 70)
    print("AUDIT OPENCLAW AGENTS — AVANT vs APRES")
    print("=" * 70)

    if not agents_dir.exists():
        print("ERREUR: Dossier agents non trouve")
        return

    agents = []
    for d in sorted(agents_dir.iterdir()):
        if d.is_dir():
            identity = d / "agent" / "IDENTITY.md"
            models = d / "agent" / "models.json"
            agents.append({
                "name": d.name,
                "has_identity": identity.exists(),
                "has_models": models.exists(),
                "identity_size": identity.stat().st_size if identity.exists() else 0,
            })

    total = len(agents)
    with_identity = sum(1 for a in agents if a["has_identity"])
    with_models = sum(1 for a in agents if a["has_models"])

    print(f"\nTotal agents:       {total}")
    print(f"Avec IDENTITY.md:   {with_identity}/{total} ({'OK' if with_identity == total else 'INCOMPLET'})")
    print(f"Avec models.json:   {with_models}/{total}")

    # Routing coverage
    bridge = OpenClawBridge()
    table = bridge.get_routing_table()
    agents_used = set(table.values())
    agent_names = {a["name"] for a in agents}
    routed = agents_used & agent_names
    unrouted = agent_names - agents_used - {"main"}

    print(f"\nAgents routes:      {len(routed)}/{total}")
    print(f"Agents non-routes:  {len(unrouted)} (pas de routing direct)")

    print("\n--- ROUTING TABLE ---")
    print(f"{'Intent':<25} {'Agent':<25} {'Existe':<10}")
    print("-" * 60)
    for intent, agent in sorted(table.items()):
        exists = "OK" if agent in agent_names else "MANQUANT"
        print(f"{intent:<25} {agent:<25} {exists:<10}")

    print("\n--- AGENTS DETAILS ---")
    print(f"{'Agent':<25} {'IDENTITY':<10} {'Models':<10} {'Size':<10}")
    print("-" * 55)
    for a in agents:
        id_status = "OK" if a["has_identity"] else "MANQUE"
        mod_status = "OK" if a["has_models"] else "---"
        size = f"{a['identity_size']}B" if a["identity_size"] else "---"
        print(f"{a['name']:<25} {id_status:<10} {mod_status:<10} {size:<10}")

    # Test routing accuracy
    print("\n--- TEST ROUTING (15 patterns) ---")
    test_cases = [
        ("ecris une fonction Python", "code-champion"),
        ("signal trading BTC long", "trading"),
        ("check cluster health", "system-ops"),
        ("audit securite OWASP", "securite-audit"),
        ("powershell get services", "windows"),
        ("architecture microservice", "gemini-pro"),
        ("raisonnement mathematique", "deep-reasoning"),
        ("recherche web actualites", "ol1-web"),
        ("traduis en anglais", "translator"),
        ("git commit push deploy", "devops-ci"),
        ("lance pipeline domino", "pipeline-monitor"),
        ("brainstorm idee creative", "creative-brainstorm"),
        ("analyse rapport statistiques", "analysis-engine"),
        ("oui", "quick-dispatch"),
        ("consensus vote critique", "consensus-master"),
    ]

    correct = 0
    for text, expected in test_cases:
        result = bridge.route(text)
        status = "OK" if result.agent == expected else f"FAIL (got {result.agent})"
        if result.agent == expected:
            correct += 1
        print(f"  '{text[:35]:<35}' -> {result.agent:<22} {status}")

    accuracy = correct / len(test_cases) * 100
    print(f"\nPrecision routing: {correct}/{len(test_cases)} ({accuracy:.0f}%)")

    return accuracy


def run_batch_test():
    """Run comprehensive batch test."""
    bridge = OpenClawBridge()

    messages = [
        "code Python async websocket server",
        "scan trading ETH SOL momentum",
        "sante cluster M1 M2 diagnostic",
        "audit vulnerabilites credentials hardcoded",
        "windows defender service restart powershell",
        "design architecture systeme distribue",
        "prouve que sqrt(2) est irrationnel",
        "cherche actualites crypto marche",
        "traduis cette documentation en anglais",
        "git push origin main deploy production",
        "execute pipeline maintenance nocturne",
        "propose des idees de features IA",
        "analyse performance latence par noeud SQL",
        "hello",
        "vote consensus multi-agent decision",
        "documente cette API changelog",
        "microphone vocal whisper transcription",
        "compare ces deux approches donnees",
    ]

    print(f"\nBatch routing: {len(messages)} messages\n")
    results = bridge.route_batch(messages)

    agent_counts: dict[str, int] = {}
    total_ms = 0.0

    for msg, result in zip(messages, results):
        print(f"  {msg[:50]:<50} -> {result.agent:<22} ({result.confidence:.0%})")
        agent_counts[result.agent] = agent_counts.get(result.agent, 0) + 1
        total_ms += result.latency_ms

    print(f"\n--- Distribution ---")
    for agent, count in sorted(agent_counts.items(), key=lambda x: -x[1]):
        print(f"  {agent:<25} {count} messages")

    print(f"\nTotal latency: {total_ms:.1f}ms ({total_ms/len(messages):.1f}ms/msg)")
    print(f"Agents uniques utilises: {len(agent_counts)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenClaw Auto-Dispatch")
    parser.add_argument("--test", type=str, help="Test routing for a single message")
    parser.add_argument("--audit", action="store_true", help="Full agent audit")
    parser.add_argument("--batch", action="store_true", help="Batch routing test")
    args = parser.parse_args()

    if args.test:
        test_routing(args.test)
    elif args.audit:
        audit_agents()
    elif args.batch:
        run_batch_test()
    else:
        # Default: run audit + batch
        audit_agents()
        print("\n" + "=" * 70)
        run_batch_test()
