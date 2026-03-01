"""Test WebSocket: /consensus mode parallele."""
import asyncio, json, time, websockets

async def test():
    uri = "ws://127.0.0.1:9742/ws"
    async with websockets.connect(uri) as ws:
        print("=== TEST: /consensus via WebSocket (7 agents paralleles) ===")
        envelope = {
            "id": "test_consensus_002",
            "type": "request",
            "channel": "chat",
            "action": "send_message",
            "payload": {"content": "/consensus Quel est le langage le plus rapide pour le backend web en 2026 ?"},
        }
        t0 = time.time()
        await ws.send(json.dumps(envelope))

        responses = []
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=120)
                msg = json.loads(raw)
                responses.append(msg)
                if msg.get("type") == "event" and msg.get("event") == "agent_complete":
                    break
                if msg.get("type") == "response" and msg.get("id") == "test_consensus_002":
                    try:
                        while True:
                            raw2 = await asyncio.wait_for(ws.recv(), timeout=3)
                            msg2 = json.loads(raw2)
                            responses.append(msg2)
                            if msg2.get("event") == "agent_complete":
                                break
                    except asyncio.TimeoutError:
                        break
                    break
            except asyncio.TimeoutError:
                print("TIMEOUT 120s atteint")
                break

        elapsed = time.time() - t0
        print(f"Temps total: {elapsed:.1f}s")
        print(f"Messages recus: {len(responses)}")

        for r in responses:
            if r.get("type") == "response" and r.get("channel") == "chat":
                p = r.get("payload", {})
                am = p.get("agent_message", {})
                print()
                print(f"TYPE:    response")
                print(f"AGENT:   {am.get('agent', '?')}")
                print(f"TASK:    {p.get('task_type', '?')}")
                print(f"ELAPSED: {am.get('elapsed', '?')}s")
                content = am.get("content", "")
                print(f"CONTENT ({len(content)} chars):")
                print(content[:1500])
                if len(content) > 1500:
                    print(f"... (+{len(content)-1500} chars)")
                if r.get("error"):
                    print(f"ERROR:   {r['error']}")
            elif r.get("type") == "event":
                evt = r.get("event", "?")
                pl = json.dumps(r.get("payload", {}), ensure_ascii=False)[:100]
                print(f"EVENT:   {evt} -> {pl}")

asyncio.run(test())
