"""Benchmark TOP 4 cloud vs M1: 10 prompts complets, ~10 checks chacun."""
import sys, io, json, time, asyncio, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import httpx

PROMPTS = [
    {"prompt": "Ecris un decorateur Python retry avec backoff exponentiel, max 3 tentatives, qui log chaque echec. Code complet uniquement.",
     "checks": {"has_def":r"def\s+\w+","has_decorator":r"def\s+\w+\(.*\).*:","has_retry":r"(for|while).*\b(range|attempt|retry|try)\b",
                "has_sleep":r"(time\.sleep|sleep|await\s+asyncio\.sleep)","has_backoff":r"(\*\*|\*\s*2|expo|backoff|2\s*\*\*)","has_max":r"(max_retries|retries|3|attempts)",
                "has_log":r"(log|print|logger|warning|error)","has_except":r"(except|Exception|try)","has_functools":r"(functools|wraps|wrapper)"}},
    {"prompt": "Implemente une classe LRUCache en Python avec get/put en O(1). Utilise OrderedDict. Code complet uniquement.",
     "checks": {"has_class":r"class\s+LRU","has_ordereddict":r"OrderedDict","has_get":r"def\s+get\s*\(","has_put":r"def\s+(put|set)\s*\(",
                "has_capacity":r"(capacity|maxsize|max_size|size)","has_move":r"move_to_end","has_pop":r"popitem","has_init":r"def\s+__init__","has_return":r"return"}},
    {"prompt": "Ecris une fonction async Python qui fetch 10 URLs en parallele avec asyncio.gather, gere les timeouts de 5s, retourne les resultats. Code complet uniquement.",
     "checks": {"has_async":r"async\s+def","has_await":r"await","has_gather":r"asyncio\.gather","has_timeout":r"(timeout|TimeoutError|wait_for)",
                "has_http":r"(aiohttp|httpx|ClientSession|AsyncClient|fetch)","has_try":r"try.*except","has_return":r"return",
                "has_list":r"(results|responses|\[)","has_url":r"(urls|url)"}},
    {"prompt": "Ecris un context manager Python qui mesure le temps d'execution et la memoire peak, et affiche le resultat. Code complet uniquement.",
     "checks": {"has_ctx":r"(class\s+\w+|@contextmanager|contextlib)","has_enter":r"(__enter__|yield)","has_exit":r"(__exit__|finally)",
                "has_time":r"(time\.|perf_counter|monotonic)","has_mem":r"(tracemalloc|psutil|resource|memory|get_traced_memory)",
                "has_print":r"(print|log|format|f\")","has_elapsed":r"(elapsed|duration|diff|delta)"}},
    {"prompt": "Ecris une classe Python ThreadSafeRateLimiter avec acquire() et get_stats(), sliding window, threading.Lock. Code complet uniquement.",
     "checks": {"has_class":r"class\s+\w*RateLimiter","has_init":r"def\s+__init__","has_acquire":r"def\s+acquire","has_stats":r"def\s+get_stats",
                "has_lock":r"(threading\.Lock|Lock\(\))","has_window":r"(window|interval|seconds)","has_time":r"(time\.|monotonic)",
                "has_bool":r"return\s+(True|False)","has_sliding":r"(filter|remove|pop|deque|timestamps)","has_threading":r"import\s+threading|from\s+threading",
                "has_dict":r"(return\s*\{|dict\()"}},
    {"prompt": "Ecris un singleton thread-safe en Python avec double-checked locking et __new__. Ajoute une methode reset() pour les tests. Code complet uniquement.",
     "checks": {"has_class":r"class\s+\w*[Ss]ingleton","has_new":r"def\s+__new__","has_instance":r"(_instance|_instances)",
                "has_lock":r"(Lock\(\)|threading\.Lock)","has_check":r"if.*(_instance|cls\._)",
                "has_reset":r"def\s+reset","has_none":r"(None|is\s+None)","has_return":r"return",
                "has_threading":r"(import\s+threading|from\s+threading)"}},
    {"prompt": "Ecris un producer-consumer en Python avec queue.Queue, 3 producers et 2 consumers en threads, poison pill pour arret propre. Code complet uniquement.",
     "checks": {"has_queue":r"(queue\.Queue|Queue\(\))","has_thread":r"(Thread|threading)","has_producer":r"(producer|Producer|produce)",
                "has_consumer":r"(consumer|Consumer|consume)","has_poison":r"(None|sentinel|STOP|poison|DONE)",
                "has_put":r"\.put\(","has_get":r"\.get\(","has_join":r"(\.join\(\)|join)",
                "has_loop":r"(while|for)","has_start":r"\.start\(\)"}},
    {"prompt": "Ecris un validateur de schema JSON en Python. Classe SchemaValidator avec validate() qui verifie types (str/int/float/bool/list/dict), champs requis, et retourne les erreurs. Code complet uniquement.",
     "checks": {"has_class":r"class\s+\w*Validator","has_validate":r"def\s+validate","has_types":r"(isinstance|type\()",
                "has_required":r"(required|obligatoire)","has_errors":r"(errors|erreurs|Error)",
                "has_dict_check":r"(dict|mapping)","has_list_check":r"(list|array|sequence)",
                "has_return":r"return","has_str_int":r"(str|int|float|bool)"}},
    {"prompt": "Ecris un event emitter Python type-safe avec on(), emit(), off(). Support wildcards '*' et once(). Utilise des callbacks typees. Code complet uniquement.",
     "checks": {"has_class":r"class\s+\w*(Event|Emitter)","has_on":r"def\s+on\s*\(","has_emit":r"def\s+emit\s*\(",
                "has_off":r"def\s+(off|remove|unsubscribe)\s*\(","has_once":r"(def\s+once|once)",
                "has_wildcard":r"(\*|wildcard|pattern|fnmatch)","has_callback":r"(callback|handler|listener|Callable)",
                "has_dict":r"(dict|defaultdict|_listeners|_handlers)","has_init":r"def\s+__init__"}},
    {"prompt": "Ecris un pool de connexions generique en Python avec acquire/release, max_size, timeout, health check. Thread-safe. Code complet uniquement.",
     "checks": {"has_class":r"class\s+\w*(Pool|pool)","has_acquire":r"def\s+acquire","has_release":r"def\s+release",
                "has_max":r"(max_size|max_conn|capacity|pool_size)","has_timeout":r"(timeout|Timeout|wait)",
                "has_health":r"(health|check|alive|valid|ping)","has_lock":r"(Lock|Semaphore|Condition|threading)",
                "has_init":r"def\s+__init__","has_context":r"(__enter__|__exit__|contextmanager|with)"}},
]

MODELS = {
    "gpt-oss:120b-cloud": ("http://127.0.0.1:11434/api/chat", "ollama"),
    "glm-4.7:cloud": ("http://127.0.0.1:11434/api/chat", "ollama"),
    "devstral-2:123b-cloud": ("http://127.0.0.1:11434/api/chat", "ollama"),
    "qwen3-coder-next:cloud": ("http://127.0.0.1:11434/api/chat", "ollama"),
    "M1/qwen3-8b": ("http://127.0.0.1:1234/api/v1/chat", "lmstudio"),
}

def build_body(model, prompt, api_type):
    if api_type == "ollama":
        return {"model": model, "messages": [{"role":"user","content":prompt}], "stream": False, "think": False, "options": {"num_predict": 1024, "temperature": 0.1}}
    else:
        return {"model": "qwen3-8b", "input": f"/nothink\n{prompt}", "temperature": 0.2, "max_output_tokens": 1024, "stream": False, "store": False}

def extract(data, api_type):
    if api_type == "ollama":
        return data.get("message",{}).get("content","")
    else:
        return next((o["content"] for o in reversed(data.get("output",[])) if o.get("type")=="message"), "")

async def test_one(client, model, url, api_type, prompt_data):
    t0 = time.perf_counter()
    try:
        resp = await client.post(url, json=build_body(model, prompt_data["prompt"], api_type), timeout=180.0)
        elapsed = time.perf_counter() - t0
        content = extract(resp.json(), api_type)
        if not content or len(content.strip()) < 20:
            return {"model": model, "ok": False, "time": round(elapsed,1), "quality": 0, "reason": "VIDE"}
        passed = sum(1 for p in prompt_data["checks"].values() if re.search(p, content, re.I|re.DOTALL))
        total = len(prompt_data["checks"])
        tokens = len(content.split()) * 1.3
        tps = round(tokens/elapsed, 1) if elapsed > 0 else 0
        missed = [k.replace("has_","") for k,p in prompt_data["checks"].items() if not re.search(p, content, re.I|re.DOTALL)]
        return {"model": model, "ok": True, "time": round(elapsed,1), "quality": round(passed/total*100),
                "passed": passed, "total": total, "tokens": int(tokens), "tps": tps, "content_len": len(content), "missed": missed}
    except Exception as e:
        return {"model": model, "ok": False, "time": round(time.perf_counter()-t0,1), "quality": 0, "reason": str(e)[:60]}

async def main():
    print("=" * 75)
    print("  BENCHMARK FINAL: TOP 4 CLOUD + M1 — 10 prompts x ~10 checks")
    print("=" * 75)

    all_results = {m: [] for m in MODELS}
    async with httpx.AsyncClient() as client:
        for i, pdata in enumerate(PROMPTS):
            short = pdata["prompt"][:50] + "..."
            print(f"\n  P{i+1}: {short} ({len(pdata['checks'])} checks)")
            tasks = [test_one(client, m, url, api, pdata) for m, (url, api) in MODELS.items()]
            results = await asyncio.gather(*tasks)
            for r in results:
                all_results[r["model"]].append(r)
                name = r["model"].split(":")[0] if ":" in r["model"] else r["model"]
                if r["ok"]:
                    miss = ",".join(r["missed"][:3]) if r["missed"] else "ALL OK"
                    print(f"    {name:22s} | {r['time']:5.1f}s | {r['tps']:5.1f}t/s | Q:{r['quality']:3d}% ({r['passed']}/{r['total']}) | {r['content_len']:4d}ch | {miss}")
                else:
                    print(f"    {name:22s} | {r['time']:5.1f}s | FAIL: {r.get('reason','?')}")

    print(f"\n{'='*75}")
    print(f"  CLASSEMENT FINAL — Score = Q*0.6 + V*0.2 + R*0.2")
    print(f"{'='*75}")

    ranking = []
    for model, results in all_results.items():
        ok = [r for r in results if r["ok"]]
        if not ok:
            ranking.append((model, 0, 0, 0, 0, 0, 0, len(results)-len(ok)))
            continue
        avg_q = sum(r["quality"] for r in ok) / len(ok)
        avg_t = sum(r["time"] for r in ok) / len(ok)
        avg_tps = sum(r["tps"] for r in ok) / len(ok)
        avg_rich = sum(r["content_len"] for r in ok) / len(ok)
        speed = min(100, avg_tps / 50 * 100)
        rich = min(100, avg_rich / 2000 * 100)
        comp = avg_q * 0.6 + speed * 0.2 + rich * 0.2
        ranking.append((model, comp, avg_q, speed, rich, avg_t, avg_tps, len(results)-len(ok)))

    ranking.sort(key=lambda x: x[1], reverse=True)
    print(f"  {'#':>2s} {'Modele':28s} | {'SCORE':>6s} | {'Q%':>5s} | {'V%':>5s} | {'R%':>5s} | {'Avg':>5s} | {'t/s':>5s} | {'Fail':>4s}")
    print(f"  -- {'─'*28}─┼{'─'*7}─┼{'─'*6}─┼{'─'*6}─┼{'─'*6}─┼{'─'*6}─┼{'─'*6}─┼{'─'*5}")
    for i, (m, comp, q, v, r, t, tps, fail) in enumerate(ranking):
        name = m.split(":")[0] if ":" in m else m
        tag = m.split(":")[-1] if ":" in m else ""
        display = f"{name}:{tag}" if tag and tag != name else name
        medal = [">>>","  >","   "][min(i,2)]
        if comp > 0:
            print(f"  {medal} {display:28s} | {comp:5.1f} | {q:4.1f}% | {v:4.1f}% | {r:4.1f}% | {t:4.1f}s | {tps:4.1f} | {fail}")
        else:
            print(f"      {display:28s} | FAIL  |       |       |       |       |       | {fail}")

    print(f"\n{'='*75}")

asyncio.run(main())
