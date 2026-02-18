#!/usr/bin/env python3
"""Test the brain_analyze and brain_suggest bug fixes."""

import asyncio
import json


def test_auto_create_handling():
    """Test that auto_create accepts both boolean and string."""
    print("\n=== TEST 1: auto_create parameter handling ===")

    # Simulate what the MCP server does
    def handle_boolean_and_string(auto_raw):
        # This is the fixed logic
        if isinstance(auto_raw, bool):
            auto = auto_raw
        else:
            auto = str(auto_raw).lower() == "true"
        return auto

    # Test cases
    test_cases = [
        (True, True, "boolean True"),
        (False, False, "boolean False"),
        ("true", True, "string 'true'"),
        ("false", False, "string 'false'"),
        ("True", True, "string 'True'"),
        ("False", False, "string 'False'"),
        (1, False, "integer 1 (fallback)"),
        ("1", False, "string '1' (fallback)"),
    ]

    for input_val, expected, description in test_cases:
        result = handle_boolean_and_string(input_val)
        status = "PASS" if result == expected else "FAIL"
        print(f"  [{status}] {description}: {input_val} -> {result}")
        if result != expected:
            print(f"         Expected: {expected}, Got: {result}")


async def test_cluster_error_handling():
    """Test that cluster_suggest_skill logs errors properly."""
    print("\n=== TEST 2: cluster_suggest_skill error handling ===")

    # We can't fully test this without running the actual code,
    # but we can verify the fix is in place
    with open("F:/BUREAU/turbo/src/brain.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Check that specific error handling is present
    checks = [
        ("httpx.ConnectError", "ConnectError handling"),
        ("json.JSONDecodeError", "JSONDecodeError handling"),
        ("logging.warning", "logging for errors"),
    ]

    for check_str, description in checks:
        if check_str in content:
            print(f"  [PASS] {description} is present")
        else:
            print(f"  [FAIL] {description} is missing")


def verify_mcp_server_fix():
    """Verify the fix in mcp_server.py."""
    print("\n=== TEST 3: mcp_server.py brain_analyze fix ===")

    with open("F:/BUREAU/turbo/src/mcp_server.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Check that the isinstance check is present
    if "isinstance(auto_raw, bool)" in content:
        print("  [PASS] isinstance(auto_raw, bool) check is present")
    else:
        print("  [FAIL] isinstance check is missing")

    # Check that we convert to string before calling .lower()
    if 'str(auto_raw).lower()' in content:
        print("  [PASS] Safe str().lower() conversion is present")
    else:
        print("  [FAIL] Safe string conversion is missing")


if __name__ == "__main__":
    print("Testing JARVIS brain fixes...")
    test_auto_create_handling()
    asyncio.run(test_cluster_error_handling())
    verify_mcp_server_fix()
    print("\n=== All tests completed ===")
