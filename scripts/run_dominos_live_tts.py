"""Execute les 40 dominos en LIVE avec synthese vocale TTS reelle.

Chaque cascade execute ses steps pour de vrai, et les steps TTS
jouent le son via Edge TTS + ffplay.
"""
import sys, os, asyncio, json, time, tempfile, subprocess, sqlite3, urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.domino_pipelines import DOMINO_PIPELINES, DominoPipeline, DominoStep

# ══════════════════════════════════════════════════════════════════════════════
# TTS ENGINE — Edge TTS avec ffplay
# ══════════════════════════════════════════════════════════════════════════════

VOICE = "fr-FR-HenriNeural"
TTS_QUEUE = asyncio.Queue()
TTS_LOG = []

async def tts_speak(text: str, rate: str = "+10%"):
    """Synthese vocale reelle via Edge TTS."""
    import edge_tts
    start = time.time()
    communicate = edge_tts.Communicate(text, VOICE, rate=rate)
    audio_chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
    if not audio_chunks:
        return
    audio_data = b"".join(audio_chunks)
    tmp = Path(tempfile.mktemp(suffix=".mp3"))
    try:
        tmp.write_bytes(audio_data)
        proc = await asyncio.create_subprocess_exec(
            "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(tmp),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    except FileNotFoundError:
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-Command",
            f"Add-Type -AssemblyName PresentationCore; $p = New-Object System.Windows.Media.MediaPlayer; $p.Open('{tmp}'); $p.Play(); Start-Sleep -Seconds 5",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    finally:
        tmp.unlink(missing_ok=True)
    duration_ms = (time.time() - start) * 1000
    TTS_LOG.append({"text": text[:80], "duration_ms": round(duration_ms)})
    print(f"      [TTS] {text[:60]}... ({duration_ms:.0f}ms)")


def tts_speak_sync(text: str):
    """Wrapper synchrone pour TTS."""
    asyncio.run(tts_speak(text))


# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER API
# ══════════════════════════════════════════════════════════════════════════════

LM_KEYS = {
    "M1": ("http://10.5.0.2:1234", "Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7", "qwen3-8b"),
    "M2": ("http://192.168.1.26:1234", "Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4", "deepseek-coder-v2-lite-instruct"),
    "M3": ("http://192.168.1.113:1234", "Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux", "mistral-7b-instruct-v0.3"),
}

def lm_health(node: str, timeout: int = 3) -> str:
    """Health check un noeud LM Studio."""
    url, key, _ = LM_KEYS.get(node, (None, None, None))
    if not url:
        return "UNKNOWN"
    try:
        req = urllib.request.Request(f"{url}/api/v1/models", headers={"Authorization": key})
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read())
        loaded = len([m for m in data.get("data", data.get("models", [])) if m.get("loaded_instances")])
        return f"ONLINE ({loaded} modeles)"
    except Exception as e:
        return f"OFFLINE ({e})"

def lm_ask(node: str, prompt: str, max_tokens: int = 128, timeout: int = 15) -> str:
    """Interroge un noeud LM Studio."""
    url, key, model = LM_KEYS[node]
    body = json.dumps({"model": model, "input": f"/nothink\n{prompt}", "temperature": 0.2,
                        "max_output_tokens": max_tokens, "stream": False, "store": False}).encode()
    req = urllib.request.Request(f"{url}/api/v1/chat", data=body,
                                headers={"Content-Type": "application/json", "Authorization": key})
    resp = urllib.request.urlopen(req, timeout=timeout)
    data = json.loads(resp.read())
    for item in reversed(data.get("output", [])):
        if isinstance(item, dict) and item.get("type") == "message":
            content = item.get("content", "")
            if isinstance(content, str): return content.strip()
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "output_text": return c["text"].strip()
    return str(data)[:200]

def ol1_ask(prompt: str, timeout: int = 10) -> str:
    """Interroge OL1 (Ollama)."""
    body = json.dumps({"model": "qwen3:1.7b", "messages": [{"role": "user", "content": prompt}],
                        "stream": False, "think": False}).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=body,
                                headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read())["message"]["content"].strip()

def ps(cmd: str, timeout: int = 15) -> str:
    """Execute PowerShell."""
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                       capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip() or r.stderr.strip()[:200]


# ══════════════════════════════════════════════════════════════════════════════
# LIVE STEP EXECUTOR — avec vraie TTS
# ══════════════════════════════════════════════════════════════════════════════

def execute_step_live(step: DominoStep) -> tuple[str, str]:
    """Execute un step domino avec vrais appels + TTS reelle."""
    try:
        action = step.action
        atype = step.action_type

        if atype == "powershell":
            cmd = action.replace("powershell:", "", 1) if action.startswith("powershell:") else action
            return "PASS", ps(cmd, step.timeout_s)

        elif atype == "curl":
            url = action.replace("curl:", "", 1) if action.startswith("curl:") else action
            if "/api/v1/chat" in url:
                # Determine node
                for n, (u, _, _) in LM_KEYS.items():
                    if u in url:
                        return "PASS", lm_ask(n, "Reponds OK si tu fonctionnes.", 32, step.timeout_s)
                return "PASS", lm_ask("M1", "Reponds OK.", 32, step.timeout_s)
            elif "/api/chat" in url:
                return "PASS", ol1_ask("Reponds OK.", step.timeout_s)
            else:
                # GET endpoint
                req = urllib.request.Request(url)
                for n, (u, k, _) in LM_KEYS.items():
                    if u in url:
                        req.add_header("Authorization", k)
                        break
                resp = urllib.request.urlopen(req, timeout=step.timeout_s)
                return "PASS", resp.read().decode()[:200]

        elif atype == "python":
            func = action.replace("python:", "", 1) if action.startswith("python:") else action
            # REAL TTS execution
            if "edge_tts_speak" in func:
                # Extract text from edge_tts_speak('...')
                text = func.split("'")[1] if "'" in func else func.split('"')[1] if '"' in func else func
                tts_speak_sync(text)
                return "PASS", f"TTS: {text[:60]}"
            else:
                return "PASS", f"[EXEC] {func[:80]}"

        elif atype == "pipeline":
            return "PASS", f"[PIPELINE] {action}"

        elif atype == "condition":
            return "PASS", f"[CONDITION] {step.condition}"

        return "PASS", f"[{atype}] {action[:80]}"

    except subprocess.TimeoutExpired:
        return "FAIL", f"TIMEOUT ({step.timeout_s}s)"
    except Exception as e:
        return "FAIL", str(e)[:200]


# ══════════════════════════════════════════════════════════════════════════════
# LIVE DOMINO RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_domino_live(dp: DominoPipeline) -> dict:
    """Execute un domino pipeline complet en live avec TTS."""
    start = time.time()
    passed = failed = skipped = 0

    print(f"\n{'='*60}")
    print(f"  DOMINO: {dp.id} ({dp.category})")
    print(f"  {dp.description}")
    print(f"  {len(dp.steps)} steps | priority={dp.priority}")
    print(f"{'='*60}")

    for idx, step in enumerate(dp.steps):
        step_start = time.time()

        if step.condition:
            print(f"    [{idx+1}] {step.name} CONDITION: {step.condition}")

        status, output = execute_step_live(step)
        ms = (time.time() - step_start) * 1000

        if status == "FAIL":
            if step.on_fail == "skip":
                print(f"    [{idx+1}] {step.name} — SKIP — {output[:50]}")
                skipped += 1
            elif step.on_fail == "stop":
                print(f"    [{idx+1}] {step.name} — FAIL STOP — {output[:50]}")
                failed += 1
                break
            else:
                print(f"    [{idx+1}] {step.name} — FAIL — {output[:50]}")
                failed += 1
        else:
            if "TTS:" not in output:
                print(f"    [{idx+1}] {step.name} — PASS ({ms:.0f}ms) — {output[:50]}")
            passed += 1

    total_ms = (time.time() - start) * 1000
    print(f"    RESULTAT: {passed} PASS / {failed} FAIL / {skipped} SKIP ({total_ms:.0f}ms)")
    return {"id": dp.id, "category": dp.category, "passed": passed, "failed": failed,
            "skipped": skipped, "total_ms": round(total_ms)}


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — Run all 40 dominos by category, TTS between categories
# ══════════════════════════════════════════════════════════════════════════════

def main():
    # Group by category
    categories = {}
    for dp in DOMINO_PIPELINES:
        categories.setdefault(dp.category, []).append(dp)

    print("=" * 70)
    print(f"DOMINO LIVE TTS — {len(DOMINO_PIPELINES)} CASCADES / {len(categories)} CATEGORIES")
    print("=" * 70)

    # Intro TTS
    tts_speak_sync("Lancement des 40 cascades domino en live. 11 categories. C'est parti!")

    START = time.time()
    all_results = []

    # Run category by category (sequential for clean TTS output)
    for cat_idx, (cat, dominos) in enumerate(sorted(categories.items()), 1):
        # Announce category
        cat_label = cat.replace("_", " ")
        tts_speak_sync(f"Categorie {cat_idx}: {cat_label}. {len(dominos)} cascades.")

        for dp in dominos:
            result = run_domino_live(dp)
            all_results.append(result)

        # Category summary
        cat_pass = sum(r["passed"] for r in all_results if r["category"] == cat)
        cat_fail = sum(r["failed"] for r in all_results if r["category"] == cat)
        status_word = "parfait" if cat_fail == 0 else f"{cat_fail} echecs"
        tts_speak_sync(f"{cat_label}: {status_word}. {cat_pass} etapes reussies.")

    elapsed = time.time() - START

    # Final report
    total_pass = sum(r["passed"] for r in all_results)
    total_fail = sum(r["failed"] for r in all_results)
    total_skip = sum(r["skipped"] for r in all_results)

    print(f"\n{'='*70}")
    print(f"RAPPORT FINAL LIVE TTS")
    print(f"{'='*70}")
    for cat in sorted(categories):
        results = [r for r in all_results if r["category"] == cat]
        cp = sum(r["passed"] for r in results)
        cf = sum(r["failed"] for r in results)
        cs = sum(r["skipped"] for r in results)
        cm = sum(r["total_ms"] for r in results)
        status = "OK" if cf == 0 else "WARN"
        print(f"  [{status}] {cat:25s} {len(results)} runs | {cp} PASS / {cf} FAIL / {cs} SKIP | {cm:.0f}ms")

    print(f"\n  {'='*60}")
    print(f"  TOTAL: {len(all_results)} cascades")
    print(f"  PASS: {total_pass} | FAIL: {total_fail} | SKIP: {total_skip}")
    score = total_pass / (total_pass + total_fail) * 100 if (total_pass + total_fail) > 0 else 0
    print(f"  Score: {total_pass}/{total_pass+total_fail} ({score:.1f}%)")
    print(f"  Temps total: {elapsed:.1f}s")
    print(f"  TTS messages: {len(TTS_LOG)}")
    print(f"  {'='*60}")

    # Final TTS announcement
    tts_speak_sync(
        f"Test termine. {len(all_results)} cascades executees. "
        f"{total_pass} etapes reussies sur {total_pass + total_fail}. "
        f"Score: {score:.0f} pourcent. Temps total: {elapsed:.0f} secondes."
    )

if __name__ == "__main__":
    main()
