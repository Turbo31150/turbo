#!/usr/bin/env python3
"""Mega Distribution Test v2.0 — Tests massifs progressifs TOUS CHEMINS.

60+ taches en crescendo, testant TOUTES les combinaisons:
  - 8 noeuds: M1, M2, M3, OL1-local, OL1-cloud(gpt-oss), OL1-cloud(devstral), Gemini, OL1-mini
  - 9 circuits: solo, dual, triple, race, chain, broadcast, fallback, consensus, adaptive
  - 7 formats: text, code, json, markdown, structured, yaml, csv
  - 8 tailles: micro, small, medium, long, xl, xxl, chain, routing
  - 6 categories: code, math, analyse, system, debug, archi

Sauvegarde temps-reel SQLite. Resume par noeud/circuit/taille/format/categorie.
"""
from __future__ import annotations
import concurrent.futures, json, os, sqlite3, subprocess, sys, time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

TURBO = Path("F:/BUREAU/turbo")
DB = sqlite3.connect(str(TURBO / "data" / "etoile.db"))
DB.execute("""CREATE TABLE IF NOT EXISTS mega_bench_v2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT, ts TEXT, batch TEXT, task_id INTEGER,
    circuit TEXT, format TEXT, size_class TEXT, category TEXT,
    node TEXT, ok INTEGER, lat REAL, toks INTEGER, toks_s REAL,
    prompt_preview TEXT, content_preview TEXT, error TEXT)""")
RUN_ID = f"megav2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
TS = datetime.now().isoformat()
TOTAL_OK = 0
TOTAL_FAIL = 0

def save(batch, tid, circuit, fmt, size, cat, node, ok, lat, toks, toks_s, prompt, content, error=""):
    global TOTAL_OK, TOTAL_FAIL
    if ok: TOTAL_OK += 1
    else: TOTAL_FAIL += 1
    DB.execute("INSERT INTO mega_bench_v2 VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (RUN_ID, TS, batch, tid, circuit, fmt, size, cat, node,
         1 if ok else 0, lat, toks, toks_s,
         prompt[:80], (content or "")[:200], (error or "")[:100]))
    DB.commit()

# === NODES ===
def lms(url, model, prompt, mt, nothink=True, timeout=60):
    pfx = "/nothink\n" if nothink else ""
    body = json.dumps({"model":model,"input":f"{pfx}{prompt}","temperature":0.2,
        "max_output_tokens":mt,"stream":False,"store":False}).encode()
    req = Request(url, data=body, headers={"Content-Type":"application/json"})
    t0 = time.time()
    with urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode())
    lat = time.time() - t0
    c = ""
    reasoning = ""
    for o in reversed(d.get("output",[])):
        if o.get("type") == "message" and not c: c = o.get("content","")
        if o.get("type") == "reasoning" and not reasoning: reasoning = o.get("content","")
    if not c.strip() and reasoning.strip():
        c = reasoning
    return lat, c

def oll(model, prompt, mt, timeout=90):
    body = json.dumps({"model":model,"messages":[{"role":"user","content":prompt}],
        "stream":False,"think":False,"options":{"num_predict":mt}}).encode()
    req = Request("http://127.0.0.1:11434/api/chat", data=body, headers={"Content-Type":"application/json"})
    t0 = time.time()
    with urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode())
    return time.time()-t0, d.get("message",{}).get("content","")

def gemini_call(prompt, timeout=60):
    t0 = time.time()
    r = subprocess.run(
        ["node", "F:/BUREAU/turbo/gemini-proxy.js", prompt],
        capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace"
    )
    lat = time.time() - t0
    out = r.stdout.strip()
    if r.returncode != 0 and not out:
        raise Exception(r.stderr.strip()[:80] or "gemini error")
    return lat, out

N = {
    "M1":       lambda p,mt: lms("http://127.0.0.1:1234/api/v1/chat","qwen3-8b",p,mt),
    "M2":       lambda p,mt: lms("http://192.168.1.26:1234/api/v1/chat","deepseek/deepseek-r1-0528-qwen3-8b",p,max(mt,2048),False),
    "M3":       lambda p,mt: lms("http://192.168.1.113:1234/api/v1/chat","deepseek/deepseek-r1-0528-qwen3-8b",p,max(mt,2048),False,120),
    "OL1":      lambda p,mt: oll("qwen3:1.7b",p,mt,30),
    "OL1-14b":  lambda p,mt: oll("qwen3:14b",p,mt,90),
    # DELETED: model removed from Ollama
    # "GPT-OSS":  lambda p,mt: oll("gpt-oss:120b-cloud",p,mt,120),
    # DELETED: model removed from Ollama
    # "DEVSTRAL": lambda p,mt: oll("devstral-2:123b-cloud",p,mt,120),
    "GEMINI":   lambda p,mt: gemini_call(p, 60),
}

def call(node, prompt, mt):
    try:
        lat, c = N[node](prompt, mt)
        toks = len((c or "").split())
        return {"node":node,"ok":True,"lat":round(lat,2),"toks":toks,"toks_s":round(toks/max(lat,.01),1),"content":c or ""}
    except Exception as e:
        return {"node":node,"ok":False,"lat":0,"toks":0,"toks_s":0,"content":"","error":str(e)[:80]}

def show(r, tag=""):
    if r["ok"]:
        s = f"  {tag}{r['node']:10s} {r['lat']:5.1f}s {r['toks']:4d}tok {r['toks_s']:5.1f}t/s"
    else:
        s = f"  {tag}{r['node']:10s} FAIL {r.get('error','')[:40]}"
    print(s, flush=True)

# === CIRCUITS ===
def solo(node, prompt, mt):
    return [call(node, prompt, mt)]

def dual_parallel(n1, n2, prompt, mt):
    with concurrent.futures.ThreadPoolExecutor(2) as ex:
        return [f.result() for f in [ex.submit(call, n1, prompt, mt), ex.submit(call, n2, prompt, mt)]]

def triple_parallel(nodes, prompt, mt):
    with concurrent.futures.ThreadPoolExecutor(len(nodes)) as ex:
        fs = [ex.submit(call, n, prompt, mt) for n in nodes]
        return [f.result() for f in fs]

def race_first(prompt, mt, nodes):
    with concurrent.futures.ThreadPoolExecutor(len(nodes)) as ex:
        fs = {ex.submit(call, n, prompt, mt): n for n in nodes}
        for f in concurrent.futures.as_completed(fs):
            r = f.result()
            if r["ok"]: return [r]
        return [{"node":"none","ok":False,"lat":0,"toks":0,"toks_s":0,"content":"","error":"all failed"}]

def chain_2(prompt1, mt1, prompt2_tpl, mt2, n1, n2):
    r1 = call(n1, prompt1, mt1)
    results = [r1]
    if r1["ok"]:
        p2 = prompt2_tpl.replace("{prev}", r1["content"][:500])
        r2 = call(n2, p2, mt2)
        results.append(r2)
    return results

def fallback_chain(prompt, mt, order):
    for n in order:
        r = call(n, prompt, mt)
        if r["ok"]: return [r]
    return [{"node":"none","ok":False,"lat":0,"toks":0,"toks_s":0,"content":"","error":"all failed"}]

def broadcast(prompt, mt, nodes):
    with concurrent.futures.ThreadPoolExecutor(len(nodes)) as ex:
        return [f.result() for f in [ex.submit(call, n, prompt, mt) for n in nodes]]

def consensus(prompt, mt, nodes, weights=None):
    """Vote pondere: lance tous, garde le meilleur score (toks * weight)."""
    results = broadcast(prompt, mt, nodes)
    if not weights:
        weights = {"M1":1.8,"M2":1.4,"M3":1.0,"OL1":1.3,"OL1-14b":1.3,"GEMINI":1.2}  # GPT-OSS/DEVSTRAL removed (models deleted from Ollama)
    best = None
    best_score = -1
    for r in results:
        if r["ok"]:
            score = r["toks"] * weights.get(r["node"], 1.0)
            if score > best_score:
                best_score = score
                best = r
    if best:
        best["_consensus"] = True
    return results

def adaptive(prompt, mt, category):
    """Routing adaptatif par categorie."""
    routes = {
        "code": ["M1","M2"],
        "math": ["M1","OL1"],
        "analyse": ["M1","M2","M3"],
        "system": ["M1","OL1"],
        "debug": ["M1","M2"],
        "archi": ["M1","GEMINI"],
    }
    nodes = routes.get(category, ["M1"])
    if len(nodes) == 1:
        return solo(nodes[0], prompt, mt)
    return race_first(prompt, mt, nodes)

# === BATCH RUNNER ===
def run_batch(name, tasks):
    print(f"\n{'='*70}", flush=True)
    print(f"  BATCH: {name} ({len(tasks)} taches)", flush=True)
    print(f"{'='*70}", flush=True)
    t0 = time.time()
    batch_ok = 0
    for i, t in enumerate(tasks):
        prompt = t["prompt"]
        mt = t["mt"]
        circuit = t["circuit"]
        fmt = t.get("format", "text")
        size = t.get("size", "micro")
        cat = t.get("cat", "general")
        tag = f"[{i+1:2d}/{len(tasks)}] "

        if circuit == "solo":
            results = solo(t.get("node","M1"), prompt, mt)
        elif circuit == "dual":
            results = dual_parallel(t.get("n1","M1"), t.get("n2","M2"), prompt, mt)
        elif circuit == "triple":
            results = triple_parallel(t.get("nodes",["M1","M2","M3"]), prompt, mt)
        elif circuit == "race":
            results = race_first(prompt, mt, t.get("nodes",["M1","M2","OL1"]))
        elif circuit == "chain":
            results = chain_2(prompt, mt, t["prompt2"], t["mt2"], t.get("n1","M1"), t.get("n2","M2"))
        elif circuit == "fallback":
            results = fallback_chain(prompt, mt, t.get("order",["M1","M2","M3","OL1"]))
        elif circuit == "broadcast":
            results = broadcast(prompt, mt, t.get("nodes",["M1","M2","M3"]))
        elif circuit == "consensus":
            results = consensus(prompt, mt, t.get("nodes",["M1","M2","OL1"]))
        elif circuit == "adaptive":
            results = adaptive(prompt, mt, cat)
        else:
            results = solo("M1", prompt, mt)

        for r in results:
            show(r, tag)
            save(name, i+1, circuit, fmt, size, cat, r["node"], r["ok"],
                 r["lat"], r["toks"], r["toks_s"], prompt, r.get("content",""), r.get("error",""))
            if r["ok"]: batch_ok += 1
            tag = "          "

    dur = time.time() - t0
    total = sum(1 for t in tasks for _ in range(1))  # task count
    print(f"\n  -> Batch {name}: {batch_ok} reponses OK / {dur:.1f}s", flush=True)
    return dur

# ============================================================================
# TASK DEFINITIONS — PROGRESSIF MICRO -> XXL, TOUS CHEMINS
# ============================================================================

# --- BATCH 1: MICRO (12 taches) — solo/race/fallback, tous noeuds individuels ---
B1_MICRO = [
    {"prompt":"1+1?","mt":8,"circuit":"solo","node":"M1","format":"text","size":"micro","cat":"math"},
    {"prompt":"1+1?","mt":8,"circuit":"solo","node":"OL1","format":"text","size":"micro","cat":"math"},
    {"prompt":"Capital France?","mt":8,"circuit":"solo","node":"M1","format":"text","size":"micro","cat":"general"},
    {"prompt":"Capital France?","mt":8,"circuit":"solo","node":"OL1","format":"text","size":"micro","cat":"general"},
    {"prompt":"HTTP 404?","mt":16,"circuit":"solo","node":"M1","format":"text","size":"micro","cat":"system"},
    {"prompt":"HTTP 404?","mt":16,"circuit":"solo","node":"M2","format":"text","size":"micro","cat":"system"},
    {"prompt":"True or False: Python is typed?","mt":8,"circuit":"race","nodes":["M1","OL1","M2"],"format":"text","size":"micro","cat":"code"},
    {"prompt":"2*3+4?","mt":8,"circuit":"race","nodes":["M1","OL1"],"format":"text","size":"micro","cat":"math"},
    {"prompt":"TCP ou UDP pour streaming?","mt":16,"circuit":"fallback","order":["OL1","M1","M2"],"format":"text","size":"micro","cat":"system"},
    {"prompt":"GET vs POST?","mt":32,"circuit":"dual","n1":"M1","n2":"OL1","format":"text","size":"micro","cat":"system"},
    {"prompt":"C'est quoi JSON?","mt":32,"circuit":"solo","node":"GEMINI","format":"text","size":"micro","cat":"general"},
    {"prompt":"sqrt(144)?","mt":8,"circuit":"solo","node":"OL1","format":"text","size":"micro","cat":"math"},
]

# --- BATCH 2: SMALL CODE (10 taches) — code multi-noeud, dual, formats divers ---
B2_SMALL = [
    {"prompt":"Hello world Python. Code only.","mt":32,"circuit":"solo","node":"M1","format":"code","size":"small","cat":"code"},
    {"prompt":"Hello world JavaScript. Code only.","mt":32,"circuit":"solo","node":"M2","format":"code","size":"small","cat":"code"},
    {"prompt":"Hello world Rust. Code only.","mt":64,"circuit":"solo","node":"OL1","format":"code","size":"small","cat":"code"},
    {"prompt":"Fibonacci(10) en Python. Code only.","mt":64,"circuit":"dual","n1":"M1","n2":"M2","format":"code","size":"small","cat":"code"},
    {"prompt":"Retourne JSON: {name,age,city} pour Alice 30 Paris","mt":64,"circuit":"solo","node":"M1","format":"json","size":"small","cat":"code"},
    {"prompt":"Tableau markdown 3 colonnes: Langage, Paradigme, Usage. 3 lignes.","mt":128,"circuit":"solo","node":"M1","format":"markdown","size":"small","cat":"general"},
    {"prompt":"Regex email validation. Code only.","mt":64,"circuit":"race","nodes":["M1","M2","OL1"],"format":"code","size":"small","cat":"code"},
    {"prompt":"SQL CREATE TABLE users (id, name, email, created_at).","mt":64,"circuit":"fallback","order":["M1","M2","OL1"],"format":"code","size":"small","cat":"code"},
    {"prompt":"YAML config pour un serveur web: host, port, ssl, workers.","mt":64,"circuit":"solo","node":"M1","format":"yaml","size":"small","cat":"system"},
    {"prompt":"CSV header: name,score,grade. 3 rows de donnees.","mt":64,"circuit":"dual","n1":"M1","n2":"OL1","format":"csv","size":"small","cat":"general"},
]

# --- BATCH 3: MEDIUM MIXED (8 taches) — dual/triple/race, categories variees ---
B3_MEDIUM = [
    {"prompt":"Classe Python Stack: push,pop,peek,is_empty,size. Code complet.","mt":256,"circuit":"solo","node":"M1","format":"code","size":"medium","cat":"code"},
    {"prompt":"Middleware Express.js: log method,url,status,duration. Code complet.","mt":256,"circuit":"solo","node":"M2","format":"code","size":"medium","cat":"code"},
    {"prompt":"Fonction retry avec backoff exponentiel en Python. Code complet.","mt":256,"circuit":"dual","n1":"M1","n2":"M2","format":"code","size":"medium","cat":"code"},
    {"prompt":"Compare Redis vs Memcached: {redis:{pros:[],cons:[]},memcached:{pros:[],cons:[]}}","mt":256,"circuit":"triple","nodes":["M1","M2","OL1"],"format":"json","size":"medium","cat":"analyse"},
    {"prompt":"Explique le pattern Observer avec exemple Python concret.","mt":256,"circuit":"consensus","nodes":["M1","M2","OL1"],"format":"text","size":"medium","cat":"archi"},
    {"prompt":"Dockerfile multi-stage pour app Node.js. Code complet.","mt":256,"circuit":"adaptive","format":"code","size":"medium","cat":"code"},
    {"prompt":"Debug ce code Python: def fib(n): return fib(n-1)+fib(n-2). Explique le bug et corrige.","mt":256,"circuit":"dual","n1":"M1","n2":"M2","format":"code","size":"medium","cat":"debug"},
    {"prompt":"Liste 5 commandes systemctl essentielles avec description. Format markdown.","mt":256,"circuit":"race","nodes":["M1","OL1","M2"],"format":"markdown","size":"medium","cat":"system"},
]

# --- BATCH 4: LONG ANALYSE (6 taches) — broadcast/triple/chain, grosse generation ---
B4_LONG = [
    {"prompt":"API REST complete pour gestion de taches: endpoints, schemas, exemples curl, auth JWT.","mt":512,"circuit":"solo","node":"M1","format":"structured","size":"long","cat":"archi"},
    {"prompt":"Serveur HTTP Python sans framework: GET/POST, routing, JSON responses. Code complet.","mt":512,"circuit":"dual","n1":"M1","n2":"M2","format":"code","size":"long","cat":"code"},
    {"prompt":"WebSocket vs SSE vs Long-polling: tableau comparatif complet + recommandations use-case.","mt":512,"circuit":"triple","nodes":["M1","M2","OL1"],"format":"markdown","size":"long","cat":"analyse"},
    {"prompt":"Cache LRU thread-safe Python avec TTL et namespaces. Code complet.","mt":512,"circuit":"broadcast","nodes":["M1","M2","OL1"],"format":"code","size":"long","cat":"code"},
    {"prompt":"Analyse de complexite: merge sort vs quick sort vs heap sort. Big-O, cas moyen/pire, stabilite.","mt":512,"circuit":"consensus","nodes":["M1","M2","OL1"],"format":"structured","size":"long","cat":"math"},
    {"prompt":"Guide complet debug Python: breakpoints, pdb, logging, profiling, memory leaks.","mt":512,"circuit":"adaptive","format":"text","size":"long","cat":"debug"},
]

# --- BATCH 5: XL GENERATION (4 taches) — grosses sorties, dual/broadcast ---
B5_XL = [
    {"prompt":"File d'attente distribuee: architecture, protocole, code Python producer+consumer complet.","mt":1024,"circuit":"solo","node":"M1","format":"structured","size":"xl","cat":"archi"},
    {"prompt":"Framework test unitaire Python: decorateurs @test, assertions, runner, rapport. Code complet.","mt":1024,"circuit":"dual","n1":"M1","n2":"M2","format":"code","size":"xl","cat":"code"},
    {"prompt":"Pipeline ETL complet Python: extraction CSV, transformation, chargement SQLite. Code fonctionnel.","mt":1024,"circuit":"consensus","nodes":["M1","M2","OL1"],"format":"code","size":"xl","cat":"code"},
    {"prompt":"Systeme de plugins dynamique Python: discovery, loading, lifecycle, events. Code complet.","mt":1024,"circuit":"race","nodes":["M1","M2"],"format":"code","size":"xl","cat":"archi"},
]

# --- BATCH 6: XXL DEEP (2 taches) — generation maximale ---
B6_XXL = [
    {"prompt":"Microservice complet Python: FastAPI, SQLAlchemy, JWT auth, CRUD, tests, Docker, CI/CD. Architecture + code.","mt":2048,"circuit":"solo","node":"M1","format":"structured","size":"xxl","cat":"archi"},
    {"prompt":"Interpreter de langage de programmation minimal: lexer, parser, AST, evaluateur. Python complet.","mt":2048,"circuit":"dual","n1":"M1","n2":"M2","format":"code","size":"xxl","cat":"code"},
]

# --- BATCH 7: CHAIN PIPELINES (4 taches) — step1->step2 multi-noeud ---
B7_CHAIN = [
    {"prompt":"Liste 5 vulnerabilites OWASP avec description courte.","mt":256,"circuit":"chain",
     "prompt2":"Pour chaque vulnerabilite, ecris un test Python:\n{prev}","mt2":512,
     "n1":"M1","n2":"M2","format":"code","size":"chain","cat":"debug"},
    {"prompt":"Schema base de donnees e-commerce: tables et relations.","mt":256,"circuit":"chain",
     "prompt2":"Ecris les CREATE TABLE SQL:\n{prev}","mt2":512,
     "n1":"M1","n2":"OL1","format":"code","size":"chain","cat":"code"},
    {"prompt":"Etapes CI/CD pour app Python.","mt":256,"circuit":"chain",
     "prompt2":"Ecris le GitHub Actions YAML:\n{prev}","mt2":512,
     "n1":"OL1","n2":"M1","format":"code","size":"chain","cat":"system"},
    {"prompt":"Liste les metriques de monitoring essentielles pour une API.","mt":256,"circuit":"chain",
     "prompt2":"Ecris un dashboard Python (Flask) affichant ces metriques:\n{prev}","mt2":1024,
     "n1":"M1","n2":"M2","format":"code","size":"chain","cat":"archi"},
]

# --- BATCH 8: CONSENSUS VOTES (3 taches) — vote pondere multi-agents ---
B8_CONSENSUS = [
    {"prompt":"Quelle base de donnees choisir pour 1M events/jour temps reel?","mt":256,"circuit":"consensus","nodes":["M1","M2","OL1"],"format":"text","size":"routing","cat":"archi"},
    {"prompt":"Meilleure strategie de cache pour API REST a fort traffic?","mt":256,"circuit":"consensus","nodes":["M1","M2","OL1"],"format":"text","size":"routing","cat":"archi"},
    {"prompt":"Monorepo vs polyrepo: avantages, inconvenients, recommandation.","mt":256,"circuit":"consensus","nodes":["M1","M2","OL1"],"format":"markdown","size":"routing","cat":"archi"},
]

# --- BATCH 9: ADAPTIVE ROUTING (4 taches) — routing par categorie ---
B9_ADAPTIVE = [
    {"prompt":"Fizzbuzz Python. Code only.","mt":128,"circuit":"adaptive","format":"code","size":"routing","cat":"code"},
    {"prompt":"Factorielle de 20?","mt":32,"circuit":"adaptive","format":"text","size":"routing","cat":"math"},
    {"prompt":"Difference process vs thread. Tableau comparatif.","mt":256,"circuit":"adaptive","format":"markdown","size":"routing","cat":"analyse"},
    {"prompt":"Ports standard: HTTP, HTTPS, SSH, FTP, MySQL, PostgreSQL, Redis.","mt":128,"circuit":"adaptive","format":"text","size":"routing","cat":"system"},
]

# --- BATCH 10: CLOUD TEST — DELETED: gpt-oss and devstral models removed from Ollama ---
B10_CLOUD = [
    # {"prompt":"Dis OK.","mt":8,"circuit":"solo","node":"GPT-OSS","format":"text","size":"micro","cat":"general"},
    # {"prompt":"Dis OK.","mt":8,"circuit":"solo","node":"DEVSTRAL","format":"text","size":"micro","cat":"general"},
    # {"prompt":"Dis OK.","mt":8,"circuit":"race","nodes":["GPT-OSS","DEVSTRAL","M1"],"format":"text","size":"micro","cat":"general"},
]

# --- BATCH 11: GEMINI PATH (2 taches) — test proxy Gemini ---
B11_GEMINI = [
    {"prompt":"Reponds uniquement OK.","mt":8,"circuit":"solo","node":"GEMINI","format":"text","size":"micro","cat":"general"},
    {"prompt":"Compare Docker vs Podman en 3 phrases.","mt":128,"circuit":"dual","n1":"GEMINI","n2":"M1","format":"text","size":"small","cat":"archi"},
]

# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    if sys.platform == "win32": os.system("")
    os.environ["PYTHONIOENCODING"] = "utf-8"

    batches = [
        ("1-MICRO(12)", B1_MICRO), ("2-SMALL(10)", B2_SMALL), ("3-MEDIUM(8)", B3_MEDIUM),
        ("4-LONG(6)", B4_LONG), ("5-XL(4)", B5_XL), ("6-XXL(2)", B6_XXL),
        ("7-CHAIN(4)", B7_CHAIN), ("8-CONSENSUS(3)", B8_CONSENSUS),
        ("9-ADAPTIVE(4)", B9_ADAPTIVE), ("10-CLOUD(3)", B10_CLOUD), ("11-GEMINI(2)", B11_GEMINI),
    ]
    total_tasks = sum(len(b[1]) for b in batches)

    print(f"\n{'='*70}", flush=True)
    print(f"  MEGA DISTRIBUTION TEST v2.0", flush=True)
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"  Tasks: {total_tasks} | Batches: {len(batches)} | Circuits: 9 | Formats: 7 | Noeuds: 8", flush=True)
    print(f"  Run: {RUN_ID}", flush=True)
    print(f"{'='*70}", flush=True)

    t0 = time.time()
    durations = {}

    for bname, btasks in batches:
        durations[bname] = run_batch(bname, btasks)

    total_dur = time.time() - t0

    # === SUMMARY ===
    print(f"\n{'='*70}", flush=True)
    print(f"  RESUME MEGA DISTRIBUTION TEST v2.0", flush=True)
    print(f"{'='*70}", flush=True)

    for bname, dur in durations.items():
        print(f"  {bname:20s} {dur:7.1f}s", flush=True)

    print(f"\n  --- STATS PAR NOEUD ---", flush=True)
    for row in DB.execute("""
        SELECT node, COUNT(*) as total, SUM(ok) as ok_count,
               ROUND(AVG(CASE WHEN ok=1 THEN lat END), 2) as avg_lat,
               ROUND(AVG(CASE WHEN ok=1 THEN toks_s END), 1) as avg_toks
        FROM mega_bench_v2 WHERE run_id=? GROUP BY node ORDER BY ok_count DESC, avg_lat
    """, (RUN_ID,)):
        node, total, ok, avg_lat, avg_toks = row
        pct = round((ok or 0)/total*100) if total else 0
        print(f"  {node:10s} {ok or 0:3d}/{total:3d} ({pct:3d}%) avg={avg_lat or 0}s {avg_toks or 0}t/s", flush=True)

    print(f"\n  --- STATS PAR CIRCUIT ---", flush=True)
    for row in DB.execute("""
        SELECT circuit, COUNT(*) as total, SUM(ok) as ok_count,
               ROUND(AVG(CASE WHEN ok=1 THEN lat END), 2) as avg_lat
        FROM mega_bench_v2 WHERE run_id=? GROUP BY circuit ORDER BY avg_lat
    """, (RUN_ID,)):
        circuit, total, ok, avg_lat = row
        print(f"  {circuit:12s} {ok or 0:3d}/{total:3d} avg={avg_lat or 0}s", flush=True)

    print(f"\n  --- STATS PAR TAILLE ---", flush=True)
    for row in DB.execute("""
        SELECT size_class, COUNT(*) as total, SUM(ok) as ok_count,
               ROUND(AVG(CASE WHEN ok=1 THEN lat END), 2) as avg_lat,
               ROUND(AVG(CASE WHEN ok=1 THEN toks END), 0) as avg_toks
        FROM mega_bench_v2 WHERE run_id=? GROUP BY size_class ORDER BY avg_lat
    """, (RUN_ID,)):
        sz, total, ok, avg_lat, avg_toks = row
        print(f"  {sz:10s} {ok or 0:3d}/{total:3d} avg={avg_lat or 0}s ~{int(avg_toks or 0)}tok", flush=True)

    print(f"\n  --- STATS PAR FORMAT ---", flush=True)
    for row in DB.execute("""
        SELECT format, COUNT(*) as total, SUM(ok) as ok_count,
               ROUND(AVG(CASE WHEN ok=1 THEN toks END), 0) as avg_toks
        FROM mega_bench_v2 WHERE run_id=? GROUP BY format ORDER BY avg_toks DESC
    """, (RUN_ID,)):
        fmt, total, ok, avg_toks = row
        print(f"  {fmt:12s} {ok or 0:3d}/{total:3d} ~{int(avg_toks or 0)}tok avg", flush=True)

    print(f"\n  --- STATS PAR CATEGORIE ---", flush=True)
    for row in DB.execute("""
        SELECT category, COUNT(*) as total, SUM(ok) as ok_count,
               ROUND(AVG(CASE WHEN ok=1 THEN lat END), 2) as avg_lat
        FROM mega_bench_v2 WHERE run_id=? GROUP BY category ORDER BY ok_count DESC
    """, (RUN_ID,)):
        cat, total, ok, avg_lat = row
        print(f"  {cat:12s} {ok or 0:3d}/{total:3d} avg={avg_lat or 0}s", flush=True)

    print(f"\n  TOTAL: {TOTAL_OK} OK / {TOTAL_OK+TOTAL_FAIL} appels en {total_dur:.1f}s", flush=True)
    print(f"  Run: {RUN_ID}", flush=True)
    print(f"  SQLite: etoile.db/mega_bench_v2", flush=True)

    # Save JSON summary
    summary = {
        "run_id": RUN_ID, "ts": TS, "version": "2.0",
        "total_ok": TOTAL_OK, "total_fail": TOTAL_FAIL,
        "total_duration_s": round(total_dur, 1),
        "durations": {k: round(v, 1) for k, v in durations.items()},
    }
    json_path = TURBO / "data" / f"{RUN_ID}.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"  JSON: {json_path}", flush=True)

    DB.close()
