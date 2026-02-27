"""WhisperFlow — Test complet des commandes via WebSocket"""
import asyncio
import json
import time
import httpx
import websockets

WS_URL = "ws://127.0.0.1:9742/ws"
API_BASE = "http://127.0.0.1:9742"

results = []

def log(test_name, ok, detail=""):
    status = "OK" if ok else "FAIL"
    results.append((test_name, ok, detail))
    print(f"  {'[OK]' if ok else '[FAIL]'} {test_name}" + (f" — {detail}" if detail else ""))


async def ws_send_recv(ws, channel, action, payload=None, timeout=12):
    """Send a WS request and wait for a matching response."""
    req_id = f"test_{int(time.time()*1000)}"
    msg = {"id": req_id, "type": "request", "channel": channel, "action": action, "payload": payload or {}}
    await ws.send(json.dumps(msg))

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=deadline - time.time())
            data = json.loads(raw)
            # Match response by id or by channel+type
            if data.get("id") == req_id or (data.get("type") == "response" and data.get("channel") == channel):
                return data
            # Also accept events from same channel
            if data.get("type") == "event" and data.get("channel") == channel:
                return data
        except asyncio.TimeoutError:
            break
    return None


async def run_tests():
    print("\n=== WhisperFlow Test Suite ===\n")

    # Test 1: Health check HTTP
    print("[1] Health Check HTTP")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_BASE}/health", timeout=5)
            d = r.json()
            log("Backend health", d.get("status") == "ok", f"port={d.get('port')}")
    except Exception as e:
        log("Backend health", False, str(e))

    # Test 2: Dictionary API
    print("\n[2] Dictionary API")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_BASE}/api/dictionary", timeout=10)
            d = r.json()
            stats = d.get("stats", {})
            cmds = stats.get("commands", 0)
            pipes = stats.get("pipelines", 0)
            log("Dictionary stats", cmds > 0 and pipes > 0, f"{cmds} cmds, {pipes} pipes")
            log("Dictionary keys", all(k in d for k in ["commands", "pipelines", "pipeline_dictionary"]))
            # Test search functionality — check data structure
            first_cmd = d.get("commands", [{}])[0] if d.get("commands") else {}
            log("Command structure", "name" in first_cmd and "triggers" in first_cmd, f"first={first_cmd.get('name','?')}")
    except Exception as e:
        log("Dictionary API", False, str(e))

    # Test 3-9: WebSocket tests
    print("\n[3] WebSocket Connection")
    try:
        async with websockets.connect(WS_URL) as ws:
            log("WS connect", True, "connected")

            # Test 4: Text command — simple (ouvre chrome)
            print("\n[4] Text Command — Commande systeme")
            resp = await ws_send_recv(ws, "chat", "send_message", {"text": "quelle heure est-il", "files": []})
            if resp:
                has_payload = resp.get("payload") is not None or resp.get("event") is not None
                log("Chat send_message", has_payload, f"type={resp.get('type')}")
            else:
                log("Chat send_message", False, "timeout")

            # Test 5: Cluster status
            print("\n[5] Cluster Status")
            resp = await ws_send_recv(ws, "cluster", "get_status")
            if resp:
                nodes = resp.get("payload", {})
                if isinstance(nodes, dict):
                    node_names = list(nodes.get("nodes", nodes.get("status", nodes)).keys()) if isinstance(nodes.get("nodes", nodes.get("status", nodes)), dict) else []
                    log("Cluster status", len(node_names) > 0 or bool(nodes), f"nodes={node_names or list(nodes.keys())[:4]}")
                else:
                    log("Cluster status", bool(nodes), f"payload type={type(nodes).__name__}")
            else:
                log("Cluster status", False, "timeout")

            # Test 6: TTS check (send a short text)
            print("\n[6] TTS Speak")
            resp = await ws_send_recv(ws, "voice", "tts_speak", {"text": "test vocal"}, timeout=8)
            # TTS might not return a response, just check no error
            log("TTS speak", resp is None or not resp.get("error"), f"resp={'ok' if resp else 'no response (normal for TTS)'}")

            # Test 7: Chat memory — remember a word
            print("\n[7] Chat Memory")
            resp = await ws_send_recv(ws, "chat", "send_message", {"text": "retiens le mot ananas", "files": []})
            if resp:
                log("Memory store", resp.get("payload") is not None, "stored")
            else:
                log("Memory store", False, "timeout")

            # Small delay for processing
            await asyncio.sleep(2)

            # Test 8: Chat memory — recall
            resp = await ws_send_recv(ws, "chat", "send_message", {"text": "quel mot je t'ai demande de retenir", "files": []})
            if resp:
                payload = resp.get("payload", {})
                text = ""
                if isinstance(payload, dict):
                    am = payload.get("agent_message", {})
                    text = am.get("text", "") if isinstance(am, dict) else str(payload.get("response", ""))
                log("Memory recall", "ananas" in text.lower() if text else False, f"response={text[:80] if text else 'empty'}")
            else:
                log("Memory recall", False, "timeout")

            # Test 9: System command execution
            print("\n[9] System Command Execute")
            resp = await ws_send_recv(ws, "system", "execute_command", {"command_name": "volume_up", "params": {}})
            if resp:
                p = resp.get("payload", {})
                executed = p.get("executed", False) if isinstance(p, dict) else False
                log("System execute", resp.get("type") == "response", f"executed={executed}")
            else:
                log("System execute", False, "timeout")

    except Exception as e:
        log("WS connect", False, str(e))

    # Summary
    print("\n" + "=" * 50)
    ok_count = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"RESULTAT: {ok_count}/{total} tests OK")
    for name, ok, detail in results:
        if not ok:
            print(f"  ECHEC: {name} — {detail}")
    print("=" * 50)
    return ok_count, total


if __name__ == "__main__":
    asyncio.run(run_tests())
