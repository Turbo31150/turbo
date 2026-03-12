"""Test final end-to-end — Config + Cloud + M1 + Ollama local + Cluster.

Integration test that makes REAL network calls. Run standalone:
    python tests/test_final.py

Excluded from pytest by default (pyproject.toml addopts --ignore).
"""
import sys
import os
import asyncio
import time

# Only run side-effects when executed directly
if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.chdir("/home/turbo/jarvis-m1-ops")
    sys.path.insert(0, ".")


def _test_config():
    """1. Config validation."""
    from src.config import config, SCRIPTS, PATHS
    m1 = config.get_node("M1")
    m2 = config.get_node("M2")
    print(f"  M1: {m1.url} — default: {m1.default_model}")
    print(f"  M2: {m2.url} — default: {m2.default_model}")
    print(f"  M1 models: {list(m1.models.keys())}")
    print(f"  Scripts: {len(SCRIPTS)}, Paths: {len(PATHS)}")

    assert "localhost" not in m1.url, "M1 utilise encore localhost!"
    assert "localhost" not in m2.url, "M2 utilise encore localhost!"
    assert "nemotron" not in m1.default_model, "M1 default est encore nemotron!"
    assert "gpt-oss" not in m2.default_model, "M2 default est encore gpt-oss!"

    ol1 = config.get_ollama_node("OL1")
    print(f"  OL1: {ol1.url} — models: {list(ol1.models.keys())}")
    assert "correction" in ol1.models, "Ollama manque le modele correction!"
    print("  [OK] Config validee")


async def _test_cloud():
    """2. Cloud models test."""
    from src.tools import _ollama_cloud_query, CLOUD_MODELS
    print(f"  Modeles: {CLOUD_MODELS}")

    start = time.time()
    tasks = [
        _ollama_cloud_query("Reponds juste 'OK-minimax'", "minimax-m2.5:cloud", timeout=30),
        _ollama_cloud_query("Reponds juste 'OK-glm'", "glm-5:cloud", timeout=30),
        _ollama_cloud_query("Reponds juste 'OK-kimi'", "kimi-k2.5:cloud", timeout=30),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start
    for model, result in zip(CLOUD_MODELS, results):
        if isinstance(result, Exception):
            print(f"  [!!] {model}: {result}")
        else:
            preview = result[:80].replace("\n", " ")
            print(f"  [OK] {model}: {preview}")
    print(f"  Temps total (parallel): {elapsed:.1f}s")

    ok_count = sum(1 for r in results if not isinstance(r, Exception))
    if ok_count < 2:
        raise RuntimeError(f"seulement {ok_count}/3 modeles OK")
    print(f"  [OK] {ok_count}/3 modeles cloud fonctionnels")


async def _test_m1():
    """3. M1 LM Studio (qwen3-30b)."""
    import httpx
    async with httpx.AsyncClient(timeout=20) as client:
        start = time.time()
        resp = await client.post(
            "http://127.0.0.1:1234/api/v1/chat",
            headers={"Authorization": "Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7"},
            json={
                "model": "qwen/qwen3-30b-a3b-2507",
                "input": "Reponds juste OK",
                "max_output_tokens": 10,
                "temperature": 0.1,
                "stream": False,
                "store": False,
            }
        )
        resp.raise_for_status()
        content = resp.json()["output"][0]["content"]
        elapsed = time.time() - start
        print(f"  Reponse: '{content.strip()[:50]}' ({elapsed:.2f}s)")
        print("  [OK] M1 qwen3-30b operationnel")


async def _test_ollama_local():
    """4. Ollama local (qwen3:1.7b)."""
    import httpx
    async with httpx.AsyncClient(timeout=20) as client:
        start = time.time()
        resp = await client.post(
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": "qwen3:1.7b",
                "messages": [{"role": "user", "content": "Reponds juste OK"}],
                "stream": False,
                "think": False,
            }
        )
        resp.raise_for_status()
        msg = resp.json()["message"]
        content = msg.get("content", "") or msg.get("thinking", "")
        elapsed = time.time() - start
        print(f"  Reponse: '{content.strip()[:50]}' ({elapsed:.2f}s)")
        print("  [OK] Ollama qwen3:1.7b operationnel")


def _test_cluster_compile():
    """5. Cluster startup + compile check."""
    from src.cluster_startup import ensure_cluster_ready
    print("  cluster_startup importe OK")

    import py_compile
    files = [
        "src/config.py", "src/tools.py", "src/orchestrator.py",
        "src/voice_correction.py", "src/cluster_startup.py",
        "src/voice.py", "src/executor.py", "src/brain.py",
        "src/mcp_server.py", "src/commands.py", "main.py",
    ]
    compile_ok = 0
    for f in files:
        try:
            py_compile.compile(f"/home/turbo/jarvis-m1-ops/{f}", doraise=True)
            compile_ok += 1
        except py_compile.PyCompileError as e:
            print(f"  [!!] Compile error: {f}: {e}")
    print(f"  Compilation: {compile_ok}/{len(files)} fichiers OK")
    assert compile_ok == len(files), f"Compilation: {compile_ok}/{len(files)}"
    print("  [OK] Tout compile")


def main():
    """Run all 5 integration tests."""
    print("=" * 60)
    print("  TEST FINAL JARVIS TURBO — Validation complete")
    print("=" * 60)

    errors = []
    tests = [
        ("Config", lambda: _test_config()),
        ("Cloud", lambda: asyncio.run(_test_cloud())),
        ("M1", lambda: asyncio.run(_test_m1())),
        ("Ollama local", lambda: asyncio.run(_test_ollama_local())),
        ("Cluster compile", lambda: _test_cluster_compile()),
    ]

    for i, (name, fn) in enumerate(tests, 1):
        print(f"\n[{i}/5] {name}...")
        try:
            fn()
        except Exception as e:
            errors.append(f"{name}: {e}")
            print(f"  [!!] {e}")

    print("\n" + "=" * 60)
    if errors:
        print(f"  RESULTAT: {5 - len(errors)}/5 tests OK — {len(errors)} erreur(s):")
        for e in errors:
            print(f"    - {e}")
        sys.exit(1)
    else:
        print("  RESULTAT: 5/5 tests OK — JARVIS Turbo 100% operationnel!")
        sys.exit(0)


if __name__ == "__main__":
    main()
