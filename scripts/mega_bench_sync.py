"""MEGA BENCHMARK SYNC — Tests sequentiels par noeud pour flush immediat."""
import json, time, sys, io, subprocess
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stdout.reconfigure(line_buffering=True)

NODES = {
    "M1": {"url": "http://10.5.0.2:1234/api/v1/chat", "model": "qwen3-8b",
            "auth": "sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7", "type": "lm",
            "prefix": "/nothink\n", "weight": 1.8, "tok": 1024},
    "M2": {"url": "http://192.168.1.26:1234/api/v1/chat", "model": "deepseek-coder-v2-lite-instruct",
            "auth": "sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4", "type": "lm",
            "prefix": "", "weight": 1.4, "tok": 512},
    "M3": {"url": "http://192.168.1.113:1234/api/v1/chat", "model": "mistral-7b-instruct-v0.3",
            "auth": "sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux", "type": "lm",
            "prefix": "", "weight": 1.0, "tok": 512},
    "OL1": {"url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b",
             "type": "ol", "prefix": "/nothink\n", "weight": 1.3, "tok": 512},
}

def query(node, prompt, timeout=25):
    """Synchronous query via httpx."""
    import httpx
    c = NODES[node]
    t0 = time.perf_counter()
    try:
        if c["type"] == "lm":
            r = httpx.post(c["url"], json={"model": c["model"], "input": c["prefix"]+prompt,
                "temperature": 0.2, "max_output_tokens": c["tok"], "stream": False, "store": False},
                headers={"Content-Type": "application/json", "Authorization": "Bearer " + c["auth"]},
                timeout=timeout)
            d = r.json()
            if "error" in d: return None, 0, d["error"].get("message","error")
            for o in reversed(d.get("output",[])):
                if o.get("type") == "message":
                    ct = o.get("content","")
                    if isinstance(ct, list): text = ct[0].get("text","")
                    else: text = str(ct)
                    return text, int((time.perf_counter()-t0)*1000), ""
            return "", int((time.perf_counter()-t0)*1000), "no_output"
        else:  # ollama
            r = httpx.post(c["url"], json={"model": c["model"],
                "messages": [{"role":"user","content": c["prefix"]+prompt}],
                "stream": False}, timeout=timeout)
            d = r.json()
            text = d.get("message",{}).get("content","")
            if "</think>" in text: text = text.split("</think>")[-1].strip()
            return text, int((time.perf_counter()-t0)*1000), ""
    except Exception as e:
        return None, int((time.perf_counter()-t0)*1000), str(e)[:100]

# ── TESTS ──
TESTS = [
    # Phase 1: Latence
    ("1.Latence", "ping", "Reponds juste: OK", ["ok"]),
    ("1.Latence", "echo", "Repete exactement: JARVIS ONLINE", ["jarvis","online"]),
    # Phase 2: Code Python
    ("2.Python", "fibonacci", "Ecris une fonction Python fibonacci(n) iterative. Code seulement.", ["def","fibonacci","return"]),
    ("2.Python", "quicksort", "Ecris une fonction Python quicksort(arr). Code seulement.", ["def","quicksort","pivot","return"]),
    ("2.Python", "async_fetch", "Ecris une fonction async Python fetch_urls(urls) avec httpx. Code seulement.", ["async","httpx","await"]),
    # Phase 3: Code JS
    ("3.JavaScript", "debounce", "Ecris une fonction JS debounce(fn, delay). Code seulement.", ["function","timeout","setTimeout"]),
    ("3.JavaScript", "retry", "Ecris une fonction JS async fetchWithRetry(url, max). Code seulement.", ["async","fetch","retry","await"]),
    # Phase 4: Logique
    ("4.Logique", "syllogisme", "Tous les chats sont animaux, certains animaux sont noirs. Certains chats sont-ils noirs? Oui ou Non.", ["non"]),
    ("4.Logique", "escargot", "Escargot monte 10m: +3m/jour, -2m/nuit. Combien de jours? Nombre seulement.", ["8"]),
    ("4.Logique", "course", "Tu depasses le 2eme dans une course. Ta position? Nombre seulement.", ["2"]),
    # Phase 5: Math
    ("5.Math", "calcul", "17*23+45-12*3 = ? Nombre seulement.", ["400"]),
    ("5.Math", "derivee", "Derivee de f(x)=3x^2+2x-5 ?", ["6x","2"]),
    ("5.Math", "moyenne", "Moyenne de 12,7,3,14,9,6,11 ? Nombre seulement.", ["8"]),
    # Phase 6: Trading
    ("6.Trading", "signal", "RSI=78, MACD bearish cross, prix > BB sup. Signal: LONG/SHORT/NEUTRE?", ["short"]),
    ("6.Trading", "risk", "100 USDT, levier 10x, entry 50000, SL 49500. Perte en % du capital?", ["10"]),
    # Phase 7: Systeme
    ("7.Systeme", "powershell", "PowerShell: lister processus >500MB RAM tries par memoire.", ["get-process","sort","memory"]),
    ("7.Systeme", "netstat", "Commande Windows pour connexions TCP actives avec PID?", ["netstat","-a"]),
    # Phase 8: Architecture
    ("8.Archi", "mcp", "Explique le Model Context Protocol (MCP) en 2 phrases.", ["tool","server","protocol"]),
    ("8.Archi", "consensus", "Comment implementer un consensus pondere multi-agents? 3 etapes.", ["poids","vote","score"]),
    # Phase 9: Generation
    ("9.Generation", "plan", "Plan projet en 5 etapes pour deployer un orchestrateur IA distribue.", ["1.","2.","3.","4.","5."]),
    # Phase 10: Multilingual
    ("10.Multi", "traduction", "Traduis en anglais: L'orchestrateur distribue les taches sur le cluster GPU.", ["orchestrator","distribut","task","cluster"]),
    ("10.Multi", "json", "JSON valide: name=M1, score=95, status=online. JSON seulement.", ['"name"','"score"','"status"']),
]

print("=" * 80)
print(f"  MEGA BENCHMARK JARVIS — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"  Noeuds: {list(NODES.keys())} | Tests: {len(TESTS)} | Total: {len(TESTS)*len(NODES)} queries")
print("=" * 80)

results = {n: {"scores": [], "latencies": [], "fails": 0} for n in NODES}
phase_data = {}
all_rows = []

current_phase = ""
for phase, task, prompt, keywords in TESTS:
    if phase != current_phase:
        current_phase = phase
        phase_data[phase] = {n: [] for n in NODES}
        print(f"\n{'─'*80}")
        print(f"  PHASE {phase}")
        print(f"{'─'*80}")

    print(f"\n  [{task}] {prompt[:65]}...")
    sys.stdout.flush()

    for node in NODES:
        text, lat, err = query(node, prompt)
        if text is not None and not err:
            tl = text.lower()
            found = [k for k in keywords if k.lower() in tl]
            score = len(found)/len(keywords) if keywords else (1.0 if len(text)>10 else 0.0)
            results[node]["scores"].append(score)
            results[node]["latencies"].append(lat)
            phase_data[phase][node].append(score)
            preview = text[:70].replace("\n"," ")
            print(f"    {node:4s} | OK  {score:4.0%} | {lat:5d}ms | [{len(found)}/{len(keywords)}] {preview}")
        else:
            results[node]["fails"] += 1
            phase_data[phase][node].append(0.0)
            print(f"    {node:4s} | FAIL     | {lat:5d}ms | {err[:60]}")
        sys.stdout.flush()
        all_rows.append({"phase":phase,"task":task,"node":node,"score":score if text and not err else 0,
                         "latency":lat,"success": text is not None and not err})

# ══════════════════════════════════════════════════════════════════════════════
# RAPPORT FINAL
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("  RAPPORT FINAL — MEGA BENCHMARK HEXA_CORE")
print("=" * 80)

print(f"\n{'Noeud':>6s} | {'Score':>6s} | {'Latence':>8s} | {'Succes':>7s} | {'Poids':>5s} | {'Pondere':>8s} | Grade")
print("-" * 70)

ranking = []
for n in NODES:
    r = results[n]
    sc = r["scores"]
    lt = r["latencies"]
    total = len(TESTS)
    if sc:
        avg_s = sum(sc)/len(sc)
        avg_l = sum(lt)/len(lt)
        succ = len(sc)/total
        grade = "A+" if avg_s>=0.85 else "A" if avg_s>=0.7 else "B" if avg_s>=0.55 else "C" if avg_s>=0.4 else "D"
    else:
        avg_s = avg_l = succ = 0; grade = "F"
    wp = avg_s * NODES[n]["weight"]
    ranking.append((n, avg_s, avg_l, succ, wp, grade))
    print(f"{n:>6s} | {avg_s:5.1%} | {avg_l:6.0f}ms | {succ:6.1%} | {NODES[n]['weight']:5.1f} | {wp:8.2f} | {grade}")

print("\n  SCORES PAR PHASE:")
print(f"  {'Phase':<20s}", end="")
for n in NODES: print(f" | {n:>5s}", end="")
print()
print("  " + "-" * 50)
for phase in phase_data:
    print(f"  {phase:<20s}", end="")
    for n in NODES:
        sc = phase_data[phase][n]
        avg = sum(sc)/len(sc) if sc else 0
        print(f" | {avg:4.0%} ", end="")
    print()

ranking.sort(key=lambda x: -x[4])
print(f"\n  CLASSEMENT FINAL (score * poids):")
for i, (n, s, l, su, wp, g) in enumerate(ranking, 1):
    medal = ["1er","2eme","3eme","4eme"][i-1]
    print(f"    {medal:>4s}  {n} — Grade {g}, Score {s:.1%}, Latence {l:.0f}ms, Pondere {wp:.2f}")

# Save
report = {
    "timestamp": datetime.now().isoformat(),
    "ranking": [{"rank":i+1,"node":n,"score":s,"latency_ms":int(l),"success":su,"weighted":wp,"grade":g}
                for i,(n,s,l,su,wp,g) in enumerate(ranking)],
    "phases": {p: {n: sum(v)/len(v) if v else 0 for n,v in nv.items()} for p,nv in phase_data.items()},
    "raw": all_rows,
}
rp = f"data/mega_benchmark_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
with open(rp, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
print(f"\n  Rapport: {rp}")
print("=" * 80)
