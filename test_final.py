"""Test final end-to-end — Config + Cloud + M1 + Ollama local + Cluster."""
import sys, os, io, asyncio, time

# UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

os.chdir("F:/BUREAU/turbo")
sys.path.insert(0, ".")

print("=" * 60)
print("  TEST FINAL JARVIS TURBO — Validation complete")
print("=" * 60)

errors = []

# --- 1. Config ---
print("\n[1/5] Config...")
try:
    from src.config import config, SCRIPTS, PATHS
    m1 = config.get_node("M1")
    m2 = config.get_node("M2")
    print(f"  M1: {m1.url} — default: {m1.default_model}")
    print(f"  M2: {m2.url} — default: {m2.default_model}")
    print(f"  M1 models: {list(m1.models.keys())}")
    print(f"  Scripts: {len(SCRIPTS)}, Paths: {len(PATHS)}")

    # Verify no localhost
    assert "localhost" not in m1.url, "M1 utilise encore localhost!"
    assert "localhost" not in m2.url, "M2 utilise encore localhost!"

    # Verify no nemotron/gpt-oss in default
    assert "nemotron" not in m1.default_model, "M1 default est encore nemotron!"
    assert "gpt-oss" not in m2.default_model, "M2 default est encore gpt-oss!"

    # Verify Ollama config
    ol1 = config.get_ollama_node("OL1")
    print(f"  OL1: {ol1.url} — models: {list(ol1.models.keys())}")
    assert "correction" in ol1.models, "Ollama manque le modele correction!"
    print("  [OK] Config validee")
except Exception as e:
    errors.append(f"Config: {e}")
    print(f"  [!!] {e}")

# --- 2. Cloud models test ---
print("\n[2/5] Ollama Cloud (3 modeles en parallele)...")
try:
    from src.tools import _ollama_cloud_query, CLOUD_MODELS
    print(f"  Modeles: {CLOUD_MODELS}")

    async def test_cloud():
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
        return results

    results = asyncio.run(test_cloud())
    ok_count = sum(1 for r in results if not isinstance(r, Exception))
    if ok_count < 2:
        errors.append(f"Cloud: seulement {ok_count}/3 modeles OK")
    else:
        print(f"  [OK] {ok_count}/3 modeles cloud fonctionnels")
except Exception as e:
    errors.append(f"Cloud: {e}")
    print(f"  [!!] {e}")

# --- 3. M1 LM Studio (qwen3-30b) ---
print("\n[3/5] M1 LM Studio (qwen3-30b)...")
try:
    import httpx

    async def test_m1():
        async with httpx.AsyncClient(timeout=20) as client:
            start = time.time()
            resp = await client.post(
                "http://10.5.0.2:1234/v1/chat/completions",
                json={
                    "model": "qwen/qwen3-30b-a3b-2507",
                    "messages": [{"role": "user", "content": "Reponds juste OK"}],
                    "max_tokens": 10,
                    "temperature": 0.1,
                }
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            elapsed = time.time() - start
            return content.strip(), elapsed

    content, elapsed = asyncio.run(test_m1())
    print(f"  Reponse: '{content[:50]}' ({elapsed:.2f}s)")
    print("  [OK] M1 qwen3-30b operationnel")
except httpx.ConnectError:
    errors.append("M1: LM Studio non accessible (10.5.0.2:1234)")
    print("  [!!] LM Studio non accessible sur 10.5.0.2:1234")
except httpx.ReadTimeout:
    errors.append("M1: Timeout (modele peut-etre pas charge)")
    print("  [!!] Timeout — qwen3-30b pas charge?")
except Exception as e:
    errors.append(f"M1: {type(e).__name__}: {e}")
    print(f"  [!!] {type(e).__name__}: {e}")

# --- 4. Ollama local (qwen3:1.7b) ---
print("\n[4/5] Ollama local (qwen3:1.7b correction)...")
try:
    import httpx

    async def test_ollama_local():
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
            return content.strip()[:50], elapsed

    content, elapsed = asyncio.run(test_ollama_local())
    print(f"  Reponse: '{content}' ({elapsed:.2f}s)")
    print("  [OK] Ollama qwen3:1.7b operationnel")
except httpx.ConnectError:
    errors.append("Ollama: non accessible (127.0.0.1:11434)")
    print("  [!!] Ollama non accessible sur 127.0.0.1:11434")
except httpx.ReadTimeout:
    errors.append("Ollama: Timeout")
    print("  [!!] Timeout")
except Exception as e:
    errors.append(f"Ollama local: {type(e).__name__}: {e}")
    print(f"  [!!] {type(e).__name__}: {e}")

# --- 5. Cluster startup ---
print("\n[5/5] Cluster startup + verify_all...")
try:
    from src.cluster_startup import ensure_cluster_ready
    print("  cluster_startup importe OK")

    # Verify all files compile
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
            py_compile.compile(f"F:/BUREAU/turbo/{f}", doraise=True)
            compile_ok += 1
        except py_compile.PyCompileError as e:
            print(f"  [!!] Compile error: {f}: {e}")
    print(f"  Compilation: {compile_ok}/{len(files)} fichiers OK")
    if compile_ok < len(files):
        errors.append(f"Compilation: {compile_ok}/{len(files)}")
    else:
        print("  [OK] Tout compile")
except Exception as e:
    errors.append(f"Cluster startup: {e}")
    print(f"  [!!] {e}")

# --- Resume ---
print("\n" + "=" * 60)
if errors:
    print(f"  RESULTAT: {5 - len(errors)}/5 tests OK — {len(errors)} erreur(s):")
    for e in errors:
        print(f"    - {e}")
    sys.exit(1)
else:
    print("  RESULTAT: 5/5 tests OK — JARVIS Turbo 100% operationnel!")
    print("  Cloud: 3 modeles | M1: qwen3-30b | Ollama: qwen3:1.7b")
    print("  11 fichiers compiles | 0 localhost | 0 nemotron/gpt-oss")
    sys.exit(0)
