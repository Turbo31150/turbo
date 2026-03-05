#!/usr/bin/env python3
"""JARVIS Cowork: Dispatch Integration Test.

End-to-end test of the full dispatch pipeline:
  1. Dynamic timeout calculation
  2. Smart prompt truncation
  3. Context overflow protection
  4. Quality gate evaluation
  5. Proactive need detection

Usage:
    python cowork/dev/dispatch_integration_test.py [--once]
"""

import os
import sys

sys.path.insert(0, "F:/BUREAU/turbo")
os.chdir("F:/BUREAU/turbo")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.pattern_agents import PatternAgent, PatternAgentRegistry, NODES


def test_dynamic_timeouts():
    """Verify dynamic timeouts cover all patterns and nodes."""
    agent = PatternAgent(
        pattern_id="TEST", pattern_type="code", agent_id="test",
        system_prompt="", primary_node="M1", fallback_nodes=[],
        strategy="single", priority=1, max_tokens=1024,
    )

    issues = []
    for pattern in PatternAgent.PATTERN_TIMEOUT:
        agent.pattern_type = pattern
        for node in NODES:
            t = agent._calc_timeout(node, "test prompt")
            if t < 10 or t > 180:
                issues.append(f"{pattern}/{node}: timeout={t}s out of range")
            # Long prompt should increase timeout (unless already at 180s cap)
            long_t = agent._calc_timeout(node, "x " * 5000)
            if long_t < t:
                issues.append(f"{pattern}/{node}: long prompt decreased timeout: {long_t} < {t}")

    return len(issues) == 0, issues


def test_prompt_truncation():
    """Verify smart truncation works for all node types."""
    agent = PatternAgent(
        pattern_id="TEST", pattern_type="code", agent_id="test",
        system_prompt="", primary_node="M1", fallback_nodes=[],
        strategy="single", priority=1, max_tokens=1024,
    )

    issues = []
    # Short prompt should be unchanged
    short = "Ecris un parser JSON"
    if agent._truncate_prompt("M1", short) != short:
        issues.append("Short prompt was modified")

    # Long prompt should be truncated for M1 (32k ctx)
    long_prompt = "x " * 60000  # 120k chars >> 89k limit
    truncated = agent._truncate_prompt("M1", long_prompt)
    if len(truncated) >= len(long_prompt):
        issues.append(f"Long prompt not truncated: {len(truncated)} >= {len(long_prompt)}")
    if "[...tronque...]" not in truncated:
        issues.append("Truncation marker missing")

    # Cloud node (128k) should allow more
    cloud_result = agent._truncate_prompt("gpt-oss", long_prompt)
    if len(cloud_result) < len(truncated):
        issues.append(f"Cloud truncated MORE than local: cloud={len(cloud_result)} < local={len(truncated)}")

    # Tail preservation
    context = "blah " * 30000
    question = "\n\nQuelle est la meilleure approche?"
    result = agent._truncate_prompt("M1", context + question)
    if "approche" not in result:
        issues.append("Tail question not preserved")

    return len(issues) == 0, issues


def test_adapt_max_tokens():
    """Verify max_tokens adaptation prevents context overflow."""
    agent = PatternAgent(
        pattern_id="TEST", pattern_type="code", agent_id="test",
        system_prompt="", primary_node="M1", fallback_nodes=[],
        strategy="single", priority=1, max_tokens=2048,
    )

    issues = []
    # Normal prompt — should get full max_tokens
    normal = "Write a function" * 10
    tokens = agent._adapt_max_tokens("M1", normal)
    if tokens < 256:
        issues.append(f"Normal prompt got too few tokens: {tokens}")

    # Very long prompt (>80% of M1 ctx) — should cap aggressively
    huge = "x " * 100000  # ~50k tokens >> M1's 32k
    tokens = agent._adapt_max_tokens("M1", huge)
    if tokens > 512:
        issues.append(f"Huge prompt didn't cap tokens: {tokens}")

    # Cloud node should allow more tokens
    cloud_tokens = agent._adapt_max_tokens("gpt-oss", normal)
    local_tokens = agent._adapt_max_tokens("M1", normal)
    if cloud_tokens < local_tokens:
        issues.append(f"Cloud tokens < local: {cloud_tokens} < {local_tokens}")

    return len(issues) == 0, issues


def test_agent_registry():
    """Verify all agents are properly configured."""
    reg = PatternAgentRegistry()
    issues = []

    if len(reg.agents) < 26:
        issues.append(f"Only {len(reg.agents)} agents (expected >= 26)")

    for ptype, agent in reg.agents.items():
        if agent.primary_node not in NODES:
            issues.append(f"{ptype}: primary_node '{agent.primary_node}' not in NODES")
        for fb in agent.fallback_nodes:
            if fb not in NODES:
                issues.append(f"{ptype}: fallback '{fb}' not in NODES")
        if agent.max_tokens < 128:
            issues.append(f"{ptype}: max_tokens too low: {agent.max_tokens}")

    return len(issues) == 0, issues


def test_classify_confidence():
    """Verify classification with confidence works correctly."""
    reg = PatternAgentRegistry()
    issues = []

    test_cases = [
        ("bonjour", "simple"),
        ("ecris un script Python", "code"),
        ("calcule 2+2", "math"),
        ("analyse le code", "analysis"),
    ]
    for prompt, expected in test_cases:
        result = reg.classify_with_confidence(prompt)
        if "pattern" not in result:
            issues.append(f"'{prompt}': missing 'pattern' key")
        if "confidence" not in result:
            issues.append(f"'{prompt}': missing 'confidence' key")
        if result.get("confidence", 0) < 0 or result.get("confidence", 0) > 1:
            issues.append(f"'{prompt}': confidence out of range: {result.get('confidence')}")

    return len(issues) == 0, issues


def test_proactive_detection():
    """Verify proactive need detection works."""
    from src.cowork_proactive import get_proactive
    issues = []

    pro = get_proactive()
    needs = pro.detect_needs()
    if not isinstance(needs, list):
        issues.append(f"detect_needs returned {type(needs)}, expected list")

    anticipation = pro.anticipate()
    if "predictions" not in anticipation:
        issues.append("anticipate() missing 'predictions' key")

    return len(issues) == 0, issues


def main():
    tests = [
        ("Dynamic Timeouts", test_dynamic_timeouts),
        ("Prompt Truncation", test_prompt_truncation),
        ("Adapt Max Tokens", test_adapt_max_tokens),
        ("Agent Registry", test_agent_registry),
        ("Classify + Confidence", test_classify_confidence),
        ("Proactive Detection", test_proactive_detection),
    ]

    print("=== JARVIS Dispatch Integration Tests ===\n")
    ok_count = 0
    for name, fn in tests:
        try:
            passed, issues = fn()
            status = "PASS" if passed else "FAIL"
            ok_count += passed
            print(f"  [{status}] {name}")
            for issue in issues[:3]:
                print(f"        -> {issue}")
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")

    print(f"\n{ok_count}/{len(tests)} tests passed")
    return ok_count == len(tests)


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
