"""Test suite for JARVIS System Audit — 8 async tests.

Tests cover all 4 tasks:
- Task 1: Node health checks (check_lm_node, check_ollama, check_gemini)
- Task 2: System info (check_gpu_local, check_system_info, check_ports)
- Task 3: Analysis layer (SPOF, security, scores)
- Task 4: Report formatter + CLI (format_report, save_report)

Usage:
    uv run python test_system_audit.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, ".")


async def test():
    print("=== JARVIS System Audit — Test Suite ===\n")
    passed = 0
    failed = 0

    # Import the module under test
    from scripts.system_audit import (
        check_lm_node,
        check_ollama,
        check_gemini,
        check_gpu_local,
        check_system_info,
        check_ports,
        analyze_spof,
        analyze_security,
        analyze_persistence,
        compute_scores,
        run_audit,
        format_report,
        save_report,
        KNOWN_PORTS,
        AUDIT_TIMEOUT,
    )
    from src.config import config

    # ══════════════════════════════════════════════════════════════════════════
    # Test 1: check_lm_node returns correct dict structure
    # ══════════════════════════════════════════════════════════════════════════
    try:
        print("[1] check_lm_node — dict structure + real check...")
        node = config.lm_nodes[1]  # M2 (champion, most likely online)
        result = await check_lm_node(node)

        # Validate structure regardless of online/offline
        required_keys = {"name", "url", "role", "status", "latency_ms", "error", "models"}
        assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"
        assert result["name"] == node.name, f"Expected {node.name}, got {result['name']}"
        assert result["url"] == node.url, f"Expected {node.url}, got {result['url']}"
        assert result["status"] in ("ONLINE", "OFFLINE", "TIMEOUT"), f"Bad status: {result['status']}"
        assert isinstance(result["latency_ms"], (int, float)), "latency_ms must be numeric"
        assert isinstance(result["models"], list), "models must be a list"

        if result["status"] == "ONLINE":
            assert result["latency_ms"] > 0, "Online node should have latency > 0"
            print(f"     M2 ONLINE, latency={result['latency_ms']:.0f}ms, models={len(result['models'])}")
        else:
            print(f"     M2 {result['status']} (error: {result['error']})")

        passed += 1
        print("     PASS")
    except Exception as e:
        failed += 1
        print(f"     FAIL: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # Test 2: check_ollama returns correct dict structure
    # ══════════════════════════════════════════════════════════════════════════
    try:
        print("[2] check_ollama — dict structure + real check...")
        ol_node = config.ollama_nodes[0]  # OL1
        result = await check_ollama(ol_node)

        required_keys = {"name", "url", "role", "status", "latency_ms", "error", "models"}
        assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"
        assert result["name"] == "OL1", f"Expected OL1, got {result['name']}"
        assert result["status"] in ("ONLINE", "OFFLINE", "TIMEOUT"), f"Bad status: {result['status']}"
        assert isinstance(result["models"], list), "models must be a list"

        if result["status"] == "ONLINE":
            assert result["latency_ms"] > 0, "Online node should have latency > 0"
            model_names = [m.get("name", "?") for m in result["models"]]
            print(f"     OL1 ONLINE, latency={result['latency_ms']:.0f}ms, models={model_names}")
        else:
            print(f"     OL1 {result['status']} (error: {result['error']})")

        passed += 1
        print("     PASS")
    except Exception as e:
        failed += 1
        print(f"     FAIL: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # Test 3: check_gemini returns correct dict structure
    # ══════════════════════════════════════════════════════════════════════════
    try:
        print("[3] check_gemini — dict structure + real check...")
        gemini = config.gemini_node
        result = await check_gemini(gemini)

        required_keys = {"name", "proxy_path", "role", "status", "latency_ms", "error", "models"}
        assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"
        assert result["name"] == "GEMINI", f"Expected GEMINI, got {result['name']}"
        assert result["status"] in ("ONLINE", "OFFLINE", "TIMEOUT"), f"Bad status: {result['status']}"
        assert isinstance(result["models"], list), "models must be a list"

        if result["status"] == "ONLINE":
            print(f"     GEMINI ONLINE, latency={result['latency_ms']:.0f}ms")
        else:
            print(f"     GEMINI {result['status']} (error: {result.get('error', 'none')})")

        passed += 1
        print("     PASS")
    except Exception as e:
        failed += 1
        print(f"     FAIL: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # Test 4: System info collection (GPU + OS + ports)
    # ══════════════════════════════════════════════════════════════════════════
    try:
        print("[4] check_gpu_local + check_system_info + check_ports...")

        # Run all three in parallel
        gpus, sys_info, ports = await asyncio.gather(
            check_gpu_local(),
            check_system_info(),
            check_ports(),
        )

        # GPU validation
        assert isinstance(gpus, list), "gpus must be a list"
        if gpus:
            g = gpus[0]
            assert "index" in g and "name" in g and "temperature" in g, f"GPU missing keys: {g}"
            assert "memory_used_mb" in g and "memory_total_mb" in g, f"GPU missing memory keys: {g}"
            print(f"     GPUs: {len(gpus)} found ({gpus[0]['name']}, ...)")
        else:
            print("     GPUs: none detected (nvidia-smi unavailable)")

        # System info validation
        assert isinstance(sys_info, dict), "sys_info must be dict"
        assert "os_version" in sys_info, "Missing os_version"
        assert "ram_total_gb" in sys_info, "Missing ram_total_gb"
        assert "disks" in sys_info, "Missing disks"
        print(f"     OS: {sys_info['os_version']}")
        print(f"     RAM: {sys_info['ram_total_gb']:.1f} GB total, {sys_info['ram_free_gb']:.1f} GB free")
        print(f"     Disks: {len(sys_info['disks'])} drives")

        # Ports validation
        assert isinstance(ports, dict), "ports must be dict"
        assert "127.0.0.1" in ports, "Must scan 127.0.0.1"
        for host, port_list in ports.items():
            assert isinstance(port_list, list), f"Port list for {host} must be a list"
            for p in port_list:
                assert "port" in p and "open" in p, f"Port entry missing keys: {p}"
        open_local = [p["port"] for p in ports.get("127.0.0.1", []) if p["open"]]
        print(f"     Local open ports: {open_local}")

        passed += 1
        print("     PASS")
    except Exception as e:
        failed += 1
        print(f"     FAIL: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # Test 5: SPOF analysis
    # ══════════════════════════════════════════════════════════════════════════
    try:
        print("[5] analyze_spof — detection logic...")

        # Scenario A: only 1 node with url online (M2 only) — should trigger LM SPOF
        # Note: analyze_spof counts all nodes with "url" key, including OL1
        fake_nodes_degraded = [
            {"name": "M1", "url": "http://10.5.0.2:1234", "status": "OFFLINE", "role": "deep_analysis", "latency_ms": 0, "error": "timeout", "models": []},
            {"name": "M2", "url": "http://192.168.1.26:1234", "status": "ONLINE", "role": "fast_inference", "latency_ms": 50, "error": None, "models": [{"id": "deepseek"}]},
            {"name": "M3", "url": "http://192.168.1.113:1234", "status": "OFFLINE", "role": "general_inference", "latency_ms": 0, "error": "refused", "models": []},
            {"name": "OL1", "url": "http://127.0.0.1:11434", "status": "OFFLINE", "role": "cloud_inference", "latency_ms": 0, "error": "refused", "models": []},
            {"name": "GEMINI", "proxy_path": "F:/BUREAU/turbo/gemini-proxy.js", "status": "ONLINE", "role": "architecture", "latency_ms": 800, "error": None, "models": []},
        ]

        spofs = analyze_spof(fake_nodes_degraded)
        assert isinstance(spofs, list), "spofs must be a list"
        assert len(spofs) > 0, "Should detect at least 1 SPOF"

        # Should detect single LM node SPOF (only M2 online with url)
        lm_spof = [s for s in spofs if "LM Studio" in s["component"]]
        assert len(lm_spof) == 1, f"Expected 1 LM SPOF, got {len(lm_spof)}"
        assert lm_spof[0]["severity"] == "high", f"LM SPOF should be high severity"

        # Should detect GEMINI single proxy
        gemini_spof = [s for s in spofs if "GEMINI" in s["component"]]
        assert len(gemini_spof) == 1, "Should detect GEMINI single proxy SPOF"

        # Should detect Master orchestrator
        master_spof = [s for s in spofs if "Master" in s["component"]]
        assert len(master_spof) == 1, "Should detect Master orchestrator SPOF"

        # Should detect embedding + web search SPOFs
        embed_spof = [s for s in spofs if "Embedding" in s["component"]]
        assert len(embed_spof) == 1, "Should detect embedding SPOF"

        # Scenario B: multiple nodes online — LM SPOF should NOT trigger
        fake_nodes_healthy = [
            {"name": "M2", "url": "http://192.168.1.26:1234", "status": "ONLINE", "role": "fast_inference", "latency_ms": 50, "error": None, "models": []},
            {"name": "M3", "url": "http://192.168.1.113:1234", "status": "ONLINE", "role": "general_inference", "latency_ms": 80, "error": None, "models": []},
            {"name": "OL1", "url": "http://127.0.0.1:11434", "status": "ONLINE", "role": "cloud_inference", "latency_ms": 20, "error": None, "models": []},
            {"name": "GEMINI", "proxy_path": "gemini-proxy.js", "status": "ONLINE", "role": "architecture", "latency_ms": 500, "error": None, "models": []},
        ]
        spofs_healthy = analyze_spof(fake_nodes_healthy)
        lm_spof_healthy = [s for s in spofs_healthy if "LM Studio" in s["component"]]
        assert len(lm_spof_healthy) == 0, f"Healthy cluster should not trigger LM SPOF, got {len(lm_spof_healthy)}"

        print(f"     Degraded scenario: {len(spofs)} SPOFs: {[s['component'] for s in spofs]}")
        print(f"     Healthy scenario: {len(spofs_healthy)} SPOFs (no LM SPOF)")
        passed += 1
        print("     PASS")
    except Exception as e:
        failed += 1
        print(f"     FAIL: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # Test 6: Security analysis + compute_scores
    # ══════════════════════════════════════════════════════════════════════════
    try:
        print("[6] analyze_security + compute_scores...")

        fake_ports = {
            "127.0.0.1": [{"port": 1234, "open": True}, {"port": 11434, "open": True}],
            "192.168.1.26": [{"port": 1234, "open": True}],
            "192.168.1.113": [{"port": 1234, "open": False}],
        }
        fake_nodes_full = [
            {"name": "M2", "url": "http://192.168.1.26:1234", "status": "ONLINE", "role": "fast_inference", "latency_ms": 50, "error": None, "models": [{"id": "deepseek"}]},
            {"name": "OL1", "url": "http://127.0.0.1:11434", "status": "ONLINE", "role": "cloud_inference", "latency_ms": 20, "error": None, "models": [{"name": "qwen3:1.7b"}]},
            {"name": "GEMINI", "proxy_path": "gemini-proxy.js", "status": "ONLINE", "role": "architecture", "latency_ms": 800, "error": None, "models": []},
        ]

        # Security
        sec_issues = analyze_security(fake_nodes_full, fake_ports)
        assert isinstance(sec_issues, list), "security issues must be a list"
        # Should flag exposed port on 192.168.1.26
        exposed = [i for i in sec_issues if "192.168.1.26" in i.get("issue", "")]
        assert len(exposed) >= 1, "Should flag exposed ports on 192.168.1.26"
        print(f"     Security issues: {len(sec_issues)}")
        for i in sec_issues:
            print(f"       - [{i['severity']}] {i['issue']}")

        # Persistence
        persistence = analyze_persistence()
        assert isinstance(persistence, dict), "persistence must be a dict"
        assert "data/" in persistence, "Should check data/ path"
        print(f"     Persistence paths: {len(persistence)} checked")

        # Scores
        fake_gpus = [
            {"index": 0, "name": "RTX 3080", "temperature": 55, "memory_used_mb": 2000, "memory_total_mb": 10240, "utilization_percent": 30},
        ]
        scores = compute_scores(fake_nodes_full, fake_gpus, fake_ports, persistence)
        assert isinstance(scores, dict), "scores must be a dict"
        expected_metrics = {"stability", "resilience", "security", "scalability", "multimodal", "observability"}
        assert expected_metrics.issubset(scores.keys()), f"Missing score metrics: {expected_metrics - scores.keys()}"

        for metric, val in scores.items():
            assert 0 <= val <= 100, f"{metric} score {val} out of range"
            print(f"       {metric}: {val}/100")

        passed += 1
        print("     PASS")
    except Exception as e:
        failed += 1
        print(f"     FAIL: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # Test 7: run_audit full pipeline (quick mode)
    # ══════════════════════════════════════════════════════════════════════════
    try:
        print("[7] run_audit(quick=True) — full pipeline...")
        t0 = time.monotonic()
        report = await run_audit(quick=True)
        elapsed = (time.monotonic() - t0) * 1000

        assert isinstance(report, dict), "report must be dict"
        required_top_keys = {
            "timestamp", "version", "audit_duration_ms", "quick_mode",
            "nodes", "gpus", "system_info", "ports",
            "persistence", "spofs", "security", "scores",
        }
        assert required_top_keys.issubset(report.keys()), f"Missing report keys: {required_top_keys - report.keys()}"
        assert report["quick_mode"] is True, "Should be quick mode"

        # M1 should be SKIPPED in quick mode
        m1_nodes = [n for n in report["nodes"] if n["name"] == "M1"]
        assert len(m1_nodes) == 1, "M1 should be in nodes list even when skipped"
        assert m1_nodes[0]["status"] == "SKIPPED", f"M1 should be SKIPPED, got {m1_nodes[0]['status']}"

        online_count = sum(1 for n in report["nodes"] if n["status"] == "ONLINE")
        print(f"     Completed in {elapsed:.0f}ms")
        print(f"     Nodes: {len(report['nodes'])} total, {online_count} online")
        print(f"     GPUs: {len(report['gpus'])}")
        print(f"     SPOFs: {len(report['spofs'])}")
        print(f"     Security: {len(report['security'])} issues")

        passed += 1
        print("     PASS")
    except Exception as e:
        failed += 1
        print(f"     FAIL: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # Test 8: format_report + save_report
    # ══════════════════════════════════════════════════════════════════════════
    try:
        print("[8] format_report + save_report...")

        # Use the report from test 7 (or generate a minimal one)
        try:
            _ = report  # noqa: F841 — use report from test 7
        except NameError:
            report = await run_audit(quick=True)

        # format_report
        text = format_report(report)
        assert isinstance(text, str), "format_report must return string"
        assert len(text) > 500, f"Report too short: {len(text)} chars"
        assert "JARVIS SYSTEM AUDIT REPORT" in text, "Missing report header"
        assert "EXECUTIVE SUMMARY" in text, "Missing executive summary section"
        assert "NODE HEALTH" in text, "Missing node health section"
        assert "READINESS SCORES" in text, "Missing readiness scores section"
        assert "ARCHITECTURE MAP" in text, "Missing architecture map section"
        assert "TOPOLOGY" in text, "Missing topology section"
        assert "MULTIMODAL MATRIX" in text, "Missing multimodal matrix section"
        assert "RISKS" in text, "Missing risks section"
        assert "SECURITY" in text, "Missing security section"
        assert "PERFORMANCE" in text, "Missing performance section"
        assert "PERSISTENCE" in text, "Missing persistence section"

        # Count sections (should be 10)
        section_count = text.count("======")
        print(f"     Report: {len(text)} chars, ~{section_count // 2} sections")

        # save_report
        filepath = save_report(report)
        assert filepath.exists(), f"Saved file not found: {filepath}"
        assert filepath.suffix == ".json", "Must save as .json"
        assert "audit_" in filepath.name, "Filename must start with audit_"

        # Validate JSON content
        with open(filepath, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["version"] == report["version"], "Saved version mismatch"
        assert len(saved["nodes"]) == len(report["nodes"]), "Saved nodes count mismatch"

        print(f"     Saved to: {filepath}")
        print(f"     File size: {filepath.stat().st_size} bytes")

        # Cleanup test file
        filepath.unlink(missing_ok=True)
        print("     Cleaned up test file")

        passed += 1
        print("     PASS")
    except Exception as e:
        failed += 1
        print(f"     FAIL: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # Summary
    # ══════════════════════════════════════════════════════════════════════════
    total = passed + failed
    print(f"\n=== Results: {passed}/{total} passed ===")
    if failed > 0:
        print(f"    {failed} test(s) FAILED")
    else:
        print("    All tests passed!")

    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(test())
    sys.exit(0 if ok else 1)
