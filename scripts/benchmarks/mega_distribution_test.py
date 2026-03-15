#!/usr/bin/env python3
"""Mega Distribution Test v1.0 — Tests massifs progressifs.

50+ taches en crescendo, testant TOUTES les combinaisons:
  - Taille: micro(1tok) → petit(64tok) → moyen(256tok) → long(512tok) → XL(1024tok)
  - Circuit: solo / dual / triple / race / chain / broadcast / fallback
  - Format: texte / code / json / markdown / structured
  - Routing: direct / round-robin / best-fit / failover

Sauvegarde chaque resultat en SQLite en temps reel.
"""
from __future__ import annotations
import concurrent.futures, json, os, sqlite3, sys, time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

<<<<<<< Updated upstream
TURBO = Path("/home/turbo/jarvis-m1-ops")
=======
TURBO = Path("/home/turbo/jarvis")
>>>>>>> Stashed changes
DB = sqlite3.connect(str(TURBO / "data" / "etoile.db"))
DB.execute("""CREATE TABLE IF NOT EXISTS mega_bench (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT, ts TEXT, batch TEXT, task_id INTEGER,
    circuit TEXT, format TEXT, size_class TEXT,
    node TEXT, ok INTEGER, lat REAL, toks INTEGER, toks_s REAL,
    prompt_preview TEXT, content_preview TEXT, error TEXT)""")
RUN_ID = f"mega_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
TS = datetime.now().isoformat()
TOTAL_OK = 0
TOTAL_FAIL = 0

def save(batch, tid, circuit, fmt, size, node, ok, lat, toks, toks_s, prompt, content, error=""):
    global TOTAL_OK, TOTAL_FAIL
    if ok: TOTAL_OK += 1
    else: TOTAL_FAIL += 1
    DB.execute("INSERT INTO mega_bench VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (RUN_ID, TS, batch, tid, circuit, fmt, size, node,
         1 if ok else 0, lat, toks, toks_s,
         prompt[:80], content[:200], error[:100]))
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
        if o.get("type") == "message" and not c:
            c = o.get("content","")
        if o.get("type") == "reasoning" and not reasoning:
            reasoning = o.get("content","")
    # deepseek-r1: content is often in reasoning block, message is empty
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

N = {
    "M1": lambda p,mt: lms("http://127.0.0.1:1234/api/v1/chat","qwen3-8b",p,mt),
    "M2": lambda p,mt: lms("http://192.168.1.26:1234/api/v1/chat","deepseek/deepseek-r1-0528-qwen3-8b",p,max(mt,2048),False),
    "M3": lambda p,mt: lms("http://192.168.1.113:1234/api/v1/chat","deepseek/deepseek-r1-0528-qwen3-8b",p,max(mt,2048),False,90),
    "OL14": lambda p,mt: oll("qwen3:14b",p,mt),
}

def call(node, prompt, mt):
    try:
        lat, c = N[node](prompt, mt)
        toks = len(c.split())
        return {"node":node,"ok":True,"lat":round(lat,2),"toks":toks,"toks_s":round(toks/max(lat,.01),1),"content":c}
    except Exception as e:
        return {"node":node,"ok":False,"lat":0,"toks":0,"toks_s":0,"content":"","error":str(e)[:80]}

def show(r, tag=""):
    s = f"  {tag}{r['node']:6s} {r['lat']:5.1f}s {r['toks']:4d}tok {r['toks_s']:5.1f}t/s"
    if not r["ok"]: s = f"  {tag}{r['node']:6s} FAIL {r.get('error','')[:30]}"
    print(s)

# === CIRCUITS ===
def solo(node, prompt, mt):
    return [call(node, prompt, mt)]

def dual_parallel(n1, n2, prompt, mt):
    with concurrent.futures.ThreadPoolExecutor(2) as ex:
        f1 = ex.submit(call, n1, prompt, mt)
        f2 = ex.submit(call, n2, prompt, mt)
        return [f1.result(), f2.result()]

def triple_parallel(prompt, mt):
    with concurrent.futures.ThreadPoolExecutor(3) as ex:
        fs = [ex.submit(call, n, prompt, mt) for n in ["M1","M2","M3"]]
        return [f.result() for f in concurrent.futures.as_completed(fs)]

def race_first(prompt, mt, nodes=None):
    nodes = nodes or ["M1","M2","M3","OL14"]
    with concurrent.futures.ThreadPoolExecutor(len(nodes)) as ex:
        fs = {ex.submit(call, n, prompt, mt): n for n in nodes}
        for f in concurrent.futures.as_completed(fs):
            r = f.result()
            if r["ok"]: return [r]  # first OK wins
        return [{"node":"none","ok":False,"lat":0,"toks":0,"toks_s":0,"content":"","error":"all failed"}]

def chain_2(prompt1, mt1, prompt2_tpl, mt2, n1="M1", n2="M2"):
    r1 = call(n1, prompt1, mt1)
    results = [r1]
    if r1["ok"]:
        p2 = prompt2_tpl.replace("{prev}", r1["content"][:400])
        r2 = call(n2, p2, mt2)
        results.append(r2)
    return results

def fallback_chain(prompt, mt, order=None):
    order = order or ["M1","M2","M3","OL14"]
    for n in order:
        r = call(n, prompt, mt)
        if r["ok"]: return [r]
    return [{"node":"none","ok":False,"lat":0,"toks":0,"toks_s":0,"content":"","error":"all failed"}]

def broadcast(prompt, mt):
    with concurrent.futures.ThreadPoolExecutor(4) as ex:
        fs = [ex.submit(call, n, prompt, mt) for n in ["M1","M2","M3","OL14"]]
        return [f.result() for f in fs]

# === BATCHES ===
def run_batch(name, tasks):
    print(f"\n{'='*65}")
    print(f"  BATCH: {name} ({len(tasks)} taches)")
    print(f"{'='*65}")
    t0 = time.time()
    batch_ok = 0
    for i, t in enumerate(tasks):
        prompt = t["prompt"]
        mt = t["mt"]
        circuit = t["circuit"]
        fmt = t.get("format", "text")
        size = t.get("size", "micro")
        tag = f"[{i+1:2d}/{len(tasks)}] "

        if circuit == "solo":
            results = solo(t.get("node","M1"), prompt, mt)
        elif circuit == "dual":
            results = dual_parallel(t.get("n1","M1"), t.get("n2","M2"), prompt, mt)
        elif circuit == "triple":
            results = triple_parallel(prompt, mt)
        elif circuit == "race":
            results = race_first(prompt, mt, t.get("nodes"))
        elif circuit == "chain":
            results = chain_2(prompt, mt, t["prompt2"], t["mt2"], t.get("n1","M1"), t.get("n2","M2"))
        elif circuit == "fallback":
            results = fallback_chain(prompt, mt, t.get("order"))
        elif circuit == "broadcast":
            results = broadcast(prompt, mt)
        else:
            results = solo("M1", prompt, mt)

        for r in results:
            show(r, tag)
            save(name, i+1, circuit, fmt, size, r["node"], r["ok"],
                 r["lat"], r["toks"], r["toks_s"], prompt, r.get("content",""), r.get("error",""))
            if r["ok"]: batch_ok += 1
        tag = "        "  # indent subsequent results

    dur = time.time() - t0
    print(f"\n  Batch {name}: {batch_ok} OK / {len(tasks)} taches / {dur:.1f}s")
    return dur

# ============================================================================
# TASK DEFINITIONS
# ============================================================================
BATCH_MICRO = [
    {"prompt":"Oui ou non: Python est type?","mt":8,"circuit":"solo","node":"M1","format":"text","size":"micro"},
    {"prompt":"1+1=?","mt":8,"circuit":"solo","node":"M1","format":"text","size":"micro"},
    {"prompt":"Capital de la France?","mt":8,"circuit":"solo","node":"M1","format":"text","size":"micro"},
    {"prompt":"HTTP status 404 signifie?","mt":16,"circuit":"solo","node":"M1","format":"text","size":"micro"},
    {"prompt":"Qu'est-ce que JSON?","mt":32,"circuit":"solo","node":"M1","format":"text","size":"micro"},
    {"prompt":"Difference entre GET et POST?","mt":32,"circuit":"solo","node":"M1","format":"text","size":"micro"},
    {"prompt":"Qu'est-ce qu'une API?","mt":32,"circuit":"solo","node":"M1","format":"text","size":"micro"},
    {"prompt":"C'est quoi Docker?","mt":32,"circuit":"solo","node":"M1","format":"text","size":"micro"},
    {"prompt":"TCP ou UDP pour streaming?","mt":16,"circuit":"race","nodes":["M1","OL14"],"format":"text","size":"micro"},
    {"prompt":"SQL: SELECT vs INSERT?","mt":32,"circuit":"dual","n1":"M1","n2":"M2","format":"text","size":"micro"},
]

BATCH_SMALL = [
    {"prompt":"Ecris un hello world en Python.","mt":32,"circuit":"solo","node":"M1","format":"code","size":"small"},
    {"prompt":"Ecris un hello world en JavaScript.","mt":32,"circuit":"solo","node":"M2","format":"code","size":"small"},
    {"prompt":"Ecris un hello world en Rust.","mt":64,"circuit":"solo","node":"M1","format":"code","size":"small"},
    {"prompt":"JSON: {\"name\":\"test\",\"value\":42} — ajoute un champ 'timestamp'. Retourne le JSON.","mt":64,"circuit":"solo","node":"M1","format":"json","size":"small"},
    {"prompt":"Retourne un tableau markdown 3x3 avec Header1,Header2,Header3 et des valeurs.","mt":128,"circuit":"solo","node":"M1","format":"markdown","size":"small"},
    {"prompt":"Ecris une regex pour valider un email.","mt":64,"circuit":"dual","n1":"M1","n2":"M2","format":"code","size":"small"},
    {"prompt":"Ecris un one-liner Python pour lire un fichier CSV.","mt":64,"circuit":"race","nodes":["M1","M2","OL14"],"format":"code","size":"small"},
    {"prompt":"Genere un schema SQL pour une table 'users' (id, name, email, created_at).","mt":128,"circuit":"fallback","format":"code","size":"small"},
]

BATCH_MEDIUM = [
    {"prompt":"Ecris une classe Python de stack avec push, pop, peek, is_empty. Code uniquement.","mt":256,"circuit":"solo","node":"M1","format":"code","size":"medium"},
    {"prompt":"Ecris un middleware Express.js qui log method, url, status, duration. Code uniquement.","mt":256,"circuit":"solo","node":"M2","format":"code","size":"medium"},
    {"prompt":"Ecris une fonction TypeScript generique de retry avec backoff exponentiel. Code uniquement.","mt":256,"circuit":"dual","n1":"M1","n2":"M2","format":"code","size":"medium"},
    {"prompt":"Compare en JSON structure: {\"redis\":{\"pros\":[],\"cons\":[]},\"memcached\":{\"pros\":[],\"cons\":[]}}","mt":256,"circuit":"triple","format":"json","size":"medium"},
    {"prompt":"Explique le pattern Observer avec un exemple Python concret.","mt":256,"circuit":"race","nodes":["M1","M2","M3"],"format":"text","size":"medium"},
    {"prompt":"Ecris un Dockerfile multi-stage pour une app Node.js. Code uniquement.","mt":256,"circuit":"fallback","format":"code","size":"medium"},
]

BATCH_LONG = [
    {"prompt":"Design complet d'une API REST pour un systeme de gestion de taches (CRUD + auth + pagination). Inclus les endpoints, schemas, et exemples curl.","mt":512,"circuit":"solo","node":"M1","format":"structured","size":"long"},
    {"prompt":"Ecris un serveur HTTP complet en Python (sans framework) qui gere GET/POST, routing, et retourne du JSON. Code uniquement.","mt":512,"circuit":"dual","n1":"M1","n2":"M2","format":"code","size":"long"},
    {"prompt":"Analyse complete: quand utiliser WebSocket vs SSE vs long-polling? Tableau comparatif + recommandations par use-case.","mt":512,"circuit":"triple","format":"markdown","size":"long"},
    {"prompt":"Ecris un systeme de cache LRU thread-safe en Python avec TTL, namespaces, et statistiques. Code complet.","mt":512,"circuit":"broadcast","format":"code","size":"long"},
]

BATCH_XL = [
    {"prompt":"Design un systeme de file d'attente distribue (comme RabbitMQ simplifie). Architecture, composants, protocole, code Python du producer et consumer.","mt":1024,"circuit":"solo","node":"M1","format":"structured","size":"xl"},
    {"prompt":"Ecris un framework de test unitaire minimaliste en Python (decorateurs @test, assertions, runner, rapport). Code complet fonctionnel.","mt":1024,"circuit":"dual","n1":"M1","n2":"M2","format":"code","size":"xl"},
]

BATCH_CHAIN = [
    {"prompt":"Liste 5 vulnerabilites OWASP Top 10 avec description courte.","mt":256,"circuit":"chain",
     "prompt2":"Pour chaque vulnerabilite ci-dessous, ecris un test Python de detection:\n{prev}","mt2":512,
     "n1":"M1","n2":"M2","format":"code","size":"chain"},
    {"prompt":"Genere un schema de base de donnees pour un e-commerce (tables, relations).","mt":256,"circuit":"chain",
     "prompt2":"Ecris les requetes SQL CREATE TABLE pour ce schema:\n{prev}","mt2":512,
     "n1":"M1","n2":"M3","format":"code","size":"chain"},
    {"prompt":"Liste les etapes d'un pipeline CI/CD pour une app Python.","mt":256,"circuit":"chain",
     "prompt2":"Ecris le fichier GitHub Actions YAML pour ces etapes:\n{prev}","mt2":512,
     "n1":"M1","n2":"M2","format":"code","size":"chain"},
]

BATCH_ROUTING = [
    {"prompt":"2+2?","mt":8,"circuit":"race","nodes":["M1","M2","M3","OL14"],"format":"text","size":"routing"},
    {"prompt":"Ecris fizzbuzz en Python.","mt":128,"circuit":"race","nodes":["M1","M2","M3","OL14"],"format":"code","size":"routing"},
    {"prompt":"Explique la difference entre process et thread avec avantages/inconvenients.","mt":512,"circuit":"race","nodes":["M1","M2","M3","OL14"],"format":"text","size":"routing"},
]

# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    if sys.platform == "win32": os.system("")
    os.environ["PYTHONIOENCODING"] = "utf-8"

    total_tasks = sum(len(b) for b in [BATCH_MICRO,BATCH_SMALL,BATCH_MEDIUM,BATCH_LONG,BATCH_XL,BATCH_CHAIN,BATCH_ROUTING])
    print(f"\n{'='*65}")
    print(f"  MEGA DISTRIBUTION TEST v1.0")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Tasks: {total_tasks} | Circuits: 7 | Formats: 5 | Sizes: 7")
    print(f"  Run: {RUN_ID}")
    print(f"{'='*65}")

    t0 = time.time()
    durations = {}

    durations["micro"] = run_batch("MICRO (10x solo/race/dual)", BATCH_MICRO)
    durations["small"] = run_batch("SMALL (8x code/json/markdown)", BATCH_SMALL)
    durations["medium"] = run_batch("MEDIUM (6x dual/triple/race)", BATCH_MEDIUM)
    durations["long"] = run_batch("LONG (4x broadcast/triple)", BATCH_LONG)
    durations["xl"] = run_batch("XL (2x solo/dual 1024tok)", BATCH_XL)
    durations["chain"] = run_batch("CHAIN (3x M1->M2/M3 pipeline)", BATCH_CHAIN)
    durations["routing"] = run_batch("ROUTING (3x race tous noeuds)", BATCH_ROUTING)

    total_dur = time.time() - t0

    # === SUMMARY ===
    print(f"\n{'='*65}")
    print(f"  RESUME MEGA DISTRIBUTION TEST")
    print(f"{'='*65}")

    # Per-batch stats
    for bname, dur in durations.items():
        print(f"  {bname:12s} {dur:6.1f}s")

    # Per-node stats from DB
    print(f"\n  --- STATS PAR NOEUD ---")
    for row in DB.execute("""
        SELECT node, COUNT(*) as total, SUM(ok) as ok_count,
               ROUND(AVG(CASE WHEN ok=1 THEN lat END), 2) as avg_lat,
               ROUND(AVG(CASE WHEN ok=1 THEN toks_s END), 1) as avg_toks
        FROM mega_bench WHERE run_id=? GROUP BY node ORDER BY avg_lat
    """, (RUN_ID,)):
        node, total, ok, avg_lat, avg_toks = row
        pct = round(ok/total*100) if total else 0
        print(f"  {node:8s} {ok:3d}/{total:3d} ({pct:3d}%) avg={avg_lat}s {avg_toks}t/s")

    # Per-circuit stats
    print(f"\n  --- STATS PAR CIRCUIT ---")
    for row in DB.execute("""
        SELECT circuit, COUNT(*) as total, SUM(ok) as ok_count,
               ROUND(AVG(CASE WHEN ok=1 THEN lat END), 2) as avg_lat
        FROM mega_bench WHERE run_id=? GROUP BY circuit ORDER BY avg_lat
    """, (RUN_ID,)):
        circuit, total, ok, avg_lat = row
        print(f"  {circuit:12s} {ok:3d}/{total:3d} avg={avg_lat}s")

    # Per-size stats
    print(f"\n  --- STATS PAR TAILLE ---")
    for row in DB.execute("""
        SELECT size_class, COUNT(*) as total, SUM(ok) as ok_count,
               ROUND(AVG(CASE WHEN ok=1 THEN lat END), 2) as avg_lat,
               ROUND(AVG(CASE WHEN ok=1 THEN toks END), 0) as avg_toks
        FROM mega_bench WHERE run_id=? GROUP BY size_class ORDER BY avg_lat
    """, (RUN_ID,)):
        sz, total, ok, avg_lat, avg_toks = row
        print(f"  {sz:10s} {ok:3d}/{total:3d} avg={avg_lat}s ~{int(avg_toks or 0)}tok")

    # Per-format stats
    print(f"\n  --- STATS PAR FORMAT ---")
    for row in DB.execute("""
        SELECT format, COUNT(*) as total, SUM(ok) as ok_count,
               ROUND(AVG(CASE WHEN ok=1 THEN toks END), 0) as avg_toks
        FROM mega_bench WHERE run_id=? GROUP BY format ORDER BY avg_toks DESC
    """, (RUN_ID,)):
        fmt, total, ok, avg_toks = row
        print(f"  {fmt:12s} {ok:3d}/{total:3d} ~{int(avg_toks or 0)}tok avg")

    print(f"\n  TOTAL: {TOTAL_OK} OK / {TOTAL_OK+TOTAL_FAIL} appels en {total_dur:.1f}s")
    print(f"  Run: {RUN_ID}")
    print(f"  SQLite: etoile.db/mega_bench")

    # Save JSON summary
    summary = {
        "run_id": RUN_ID, "ts": TS,
        "total_ok": TOTAL_OK, "total_fail": TOTAL_FAIL,
        "total_duration_s": round(total_dur, 1),
        "durations": {k: round(v, 1) for k, v in durations.items()},
    }
    json_path = TURBO / "data" / f"{RUN_ID}.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"  JSON: {json_path}")

    DB.close()
