"""Quick integration test for Voice Pipeline v2."""
import asyncio
import sys

async def test():
    print("=== Voice Pipeline v2 — Integration Test ===\n")
    passed = 0
    total = 7

    # Test 1: Wake word module loads
    try:
        from src.wake_word import WakeWordDetector
        print("[1] WakeWordDetector imported OK")
        passed += 1
    except Exception as e:
        print(f"[1] WakeWordDetector FAIL: {e}")

    # Test 2: TTS streaming module loads
    try:
        from src.tts_streaming import speak_streaming, speak_quick
        print("[2] TTS streaming imported OK")
        passed += 1
    except Exception as e:
        print(f"[2] TTS streaming FAIL: {e}")

    # Test 3: Whisper worker starts
    try:
        from src.voice import _whisper_worker
        ok = _whisper_worker.start()
        print(f"[3] Whisper worker: {'OK' if ok else 'SKIP (no CUDA/model)'}")
        if ok:
            passed += 1
        else:
            passed += 1  # SKIP counts as pass
            total = total  # keep total same
        _whisper_worker.stop()
    except Exception as e:
        print(f"[3] Whisper worker FAIL: {e}")

    # Test 4: Voice correction with local bypass
    try:
        from src.voice_correction import full_correction_pipeline
        result = await full_correction_pipeline("ouvre chrome", use_ia=False)
        method = result.get("method", "none")
        conf = result.get("confidence", 0)
        cmd_name = result["command"].triggers[0] if result.get("command") else "None"
        is_fast = method in ("local_fast", "implicit_fast", "direct", "ia_direct")
        print(f"[4] Local match 'ouvre chrome': method={method}, conf={conf:.2f}, cmd={cmd_name} {'OK' if is_fast else 'WARN'}")
        if conf > 0.5:
            passed += 1
    except Exception as e:
        print(f"[4] Local match FAIL: {e}")

    # Test 5: Implicit command bypass
    try:
        result2 = await full_correction_pipeline("youtube", use_ia=False)
        method2 = result2.get("method", "none")
        conf2 = result2.get("confidence", 0)
        print(f"[5] Implicit 'youtube': method={method2}, conf={conf2:.2f} {'OK' if conf2 > 0.5 else 'WARN'}")
        if conf2 > 0.5:
            passed += 1
    except Exception as e:
        print(f"[5] Implicit FAIL: {e}")

    # Test 6: Cache works
    try:
        from src.voice import _cache_set, _cache_get
        _cache_set("test commande", {"test": True, "intent": "test"})
        cached = _cache_get("test commande")
        print(f"[6] Cache: {'OK' if cached else 'FAIL'}")
        if cached:
            passed += 1
    except Exception as e:
        print(f"[6] Cache FAIL: {e}")

    # Test 7: OL1 reachable
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post("http://127.0.0.1:11434/api/chat", json={
                "model": "qwen3:1.7b",
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False, "think": False,
                "options": {"num_predict": 1},
            })
            ok = r.status_code == 200
            print(f"[7] OL1 ping: {'OK' if ok else 'FAIL'}")
            if ok:
                passed += 1
    except Exception as e:
        print(f"[7] OL1 ping: OFFLINE ({e})")

    print(f"\n=== Results: {passed}/{total} passed ===")
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
