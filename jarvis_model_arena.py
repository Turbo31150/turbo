#!/usr/bin/env python3
"""JARVIS Model Arena — tournament system for comparing models on M1."""
import json, time, sys, os, subprocess
import urllib.request
from datetime import datetime
from jarvis_bench_utils import NODES, load_history, save_history, append_run, compute_composite_score

CANDIDATE_MODELS = {
    "qwen3-coder-30b": {"id": "qwen/qwen3-coder-30b-a3b-2507", "config": {"context_length": 8192, "eval_batch_size": 512, "flash_attention": True, "offload_kv_cache_to_gpu": True, "num_experts": 8}},
    "devstral": {"id": "devstral-small-2505", "config": {"context_length": 8192, "eval_batch_size": 512, "flash_attention": True, "offload_kv_cache_to_gpu": True}},
    "gpt-oss-20b": {"id": "gpt-oss-20b", "config": {"context_length": 8192, "eval_batch_size": 512, "flash_attention": True, "offload_kv_cache_to_gpu": True}},
}

M1 = NODES["M1"]

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def unload_m1():
    try:
        req = urllib.request.Request(M1["health_url"], headers={"Authorization": f"Bearer {M1['key']}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        for m in data.get("data", data.get("models", [])):
            for inst in m.get("loaded_instances", []):
                iid = inst["id"]
                body = json.dumps({"instance_id": iid}).encode()
                req2 = urllib.request.Request(M1["unload_url"], data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {M1['key']}"})
                urllib.request.urlopen(req2, timeout=30)
                log(f"Unloaded: {iid}")
    except Exception as e:
        log(f"Unload error (may be ok): {e}")

def load_m1(model_id, config):
    load_body = {"model": model_id}
    load_body.update(config)
    body = json.dumps(load_body).encode()
    req = urllib.request.Request(M1["load_url"], data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {M1['key']}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read())
        if result.get("status") == "loaded":
            log(f"Loaded: {model_id} in {result.get('load_time_seconds', '?')}s")
            return True
        log(f"Load response: {result}")
        return False
    except Exception as e:
        log(f"Load FAILED: {e}")
        return False

def warmup_m1(model_id):
    for prompt in ["Reponds OK", "2+2?", "Bonjour"]:
        try:
            body = json.dumps({"model": model_id, "input": prompt, "temperature": 0.2, "max_output_tokens": 20, "stream": False, "store": False}).encode()
            req = urllib.request.Request(M1["chat_url"], data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {M1['key']}"})
            urllib.request.urlopen(req, timeout=60)
        except:
            pass

def run_benchmark(cycles=5, tasks_per_cycle=40):
    log(f"Running benchmark: {cycles} cycles x {tasks_per_cycle} tasks...")
    try:
        subprocess.run(
            [sys.executable, "C:/Users/franc/jarvis_autotest.py", str(cycles), str(tasks_per_cycle)],
            capture_output=True, text=True, timeout=1800, cwd="C:/Users/franc"
        )
    except Exception as e:
        log(f"Benchmark subprocess error: {e}")
    try:
        data = json.load(open("C:/Users/franc/jarvis_autotest_results.json", encoding="utf-8"))
        total = data["total"]
        pass_rate = data["pass"] * 100.0 / max(total, 1)
        lats = []
        for nd in data.get("by_node", {}).values():
            if nd.get("avg_latency"):
                lats.extend([nd["avg_latency"]] * nd["total"])
        avg_lat = int(sum(lats) / len(lats)) if lats else 0
        return pass_rate, avg_lat, total, data["errors"]
    except Exception as e:
        log(f"Failed to parse results: {e}")
        return 0, 0, 0, 0

def tournament(candidate_name, quick=False):
    if candidate_name not in CANDIDATE_MODELS:
        log(f"Unknown model: {candidate_name}. Available: {', '.join(CANDIDATE_MODELS.keys())}")
        return

    candidate = CANDIDATE_MODELS[candidate_name]
    history = load_history()
    champion = history["champion"]
    cycles = 2 if quick else 5

    log("=" * 50)
    log(f"ARENA: {champion['model']} (champion, score={champion['score']}) vs {candidate['id']}")
    log("=" * 50)

    log("\n--- CHAMPION benchmark ---")
    ch_pass, ch_lat, ch_total, ch_err = run_benchmark(cycles, 40)
    ch_err_rate = ch_err * 100.0 / max(ch_total, 1)
    ch_score = compute_composite_score(ch_pass, ch_lat, ch_err_rate)
    log(f"Champion: pass={ch_pass:.0f}% lat={ch_lat}ms score={ch_score}")

    log(f"\n--- Loading CANDIDATE: {candidate['id']} ---")
    unload_m1()
    time.sleep(3)
    if not load_m1(candidate["id"], candidate["config"]):
        log("CANDIDATE load failed — restoring champion")
        load_m1(champion["model"], champion.get("config", M1["config"]))
        return

    time.sleep(5)
    warmup_m1(candidate["id"])

    log("\n--- CANDIDATE benchmark ---")
    ca_pass, ca_lat, ca_total, ca_err = run_benchmark(cycles, 40)
    ca_err_rate = ca_err * 100.0 / max(ca_total, 1)
    ca_score = compute_composite_score(ca_pass, ca_lat, ca_err_rate)
    log(f"Candidate: pass={ca_pass:.0f}% lat={ca_lat}ms score={ca_score}")

    log(f"\n{'=' * 50}")
    log(f"RESULTS: Champion={ch_score} vs Candidate={ca_score}")

    if ca_score > ch_score:
        log(f"NEW CHAMPION: {candidate['id']} (score {ca_score} > {ch_score})")
        history["champion"] = {
            "model": candidate["id"],
            "score": ca_score,
            "since": datetime.now().strftime("%Y-%m-%d"),
            "config": candidate["config"],
        }
        save_history(history)
        append_run("arena", candidate["id"], candidate["config"], ca_pass, ca_lat, ca_total, ca_err)
    else:
        log(f"CHAMPION RETAINED: {champion['model']} (score {ch_score} >= {ca_score})")
        log("Restoring champion model...")
        unload_m1()
        time.sleep(3)
        load_m1(champion["model"], champion.get("config", M1["config"]))
        append_run("arena", candidate["id"], candidate["config"], ca_pass, ca_lat, ca_total, ca_err)

    log("=" * 50)

def show_history():
    history = load_history()
    ch = history.get("champion", {})
    print(f"\nChampion: {ch.get('model', '?')} (score={ch.get('score', 0)}, since={ch.get('since', '?')})")
    print(f"\nLast 10 runs:")
    for run in history.get("runs", [])[-10:]:
        print(f"  [{run['timestamp']}] {run['type']:8s} | {run['model_m1'][:30]:30s} | score={run['score_composite']:5.2f} | pass={run['pass_rate']:.0f}% | lat={run['avg_latency_ms']}ms")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 jarvis_model_arena.py <model-name>     # test a candidate")
        print("  python3 jarvis_model_arena.py --quick <model>   # quick test (2 cycles)")
        print("  python3 jarvis_model_arena.py --all             # test all candidates")
        print("  python3 jarvis_model_arena.py --history         # show history")
        print(f"\nAvailable candidates: {', '.join(CANDIDATE_MODELS.keys())}")
        sys.exit(0)

    args = sys.argv[1:]
    if "--history" in args:
        show_history()
    elif "--auto" in args:
        # Auto mode: run quick tournament on all candidates, silent output
        for name in CANDIDATE_MODELS:
            try:
                tournament(name, quick=True)
            except Exception as e:
                print(f"Arena {name} error: {e}")
    elif "--all" in args:
        quick = "--quick" in args
        for name in CANDIDATE_MODELS:
            tournament(name, quick=quick)
    elif "--quick" in args:
        others = [a for a in args if a != "--quick"]
        if others:
            tournament(others[0], quick=True)
        else:
            print("Usage: python3 jarvis_model_arena.py --quick <model-name>")
    else:
        tournament(args[0])
