# Cluster Resilience & Model Arena — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a self-healing watchdog, a model tournament system, and continuous benchmark history for the JARVIS cluster.

**Architecture:** Three standalone Python scripts sharing a JSON history file. The healer runs as a daemon (60s loop), the arena runs on-demand via CLI, and the autotest feeds the history after each run. Plugin commands expose status.

**Tech Stack:** Python 3.13 (stdlib only — urllib, json, time, datetime), LM Studio REST API, Ollama API. No external dependencies.

---

### Task 1: Create benchmark history JSON + helper module

**Files:**
- Create: `C:/Users/franc/jarvis_benchmark_history.json`
- Create: `C:/Users/franc/jarvis_bench_utils.py`

**Step 1: Create the empty history file**

```json
{
  "runs": [],
  "champion": {
    "model": "qwen/qwen3-30b-a3b-2507",
    "score": 0,
    "since": "2026-02-25",
    "config": {"context_length": 8192, "temperature": 0.2}
  }
}
```

Write this to `C:/Users/franc/jarvis_benchmark_history.json`.

**Step 2: Create the shared utils module**

Write `C:/Users/franc/jarvis_bench_utils.py`:

```python
#!/usr/bin/env python3
"""Shared utilities for benchmark history, scoring, and node config."""
import json, os, time
from datetime import datetime

HISTORY_FILE = "C:/Users/franc/jarvis_benchmark_history.json"
MAX_RUNS = 500

# Node configs — single source of truth
NODES = {
    "M1": {
        "health_url": "http://10.5.0.2:1234/api/v1/models",
        "chat_url": "http://10.5.0.2:1234/api/v1/chat",
        "type": "lmstudio-responses",
        "model": "qwen/qwen3-30b-a3b-2507",
        "key": "sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7",
        "load_url": "http://10.5.0.2:1234/api/v1/models/load",
        "unload_url": "http://10.5.0.2:1234/api/v1/models/unload",
        "config": {"context_length": 8192, "eval_batch_size": 512, "flash_attention": True, "offload_kv_cache_to_gpu": True, "num_experts": 8},
        "health_timeout": 5,
    },
    "M2": {
        "health_url": "http://192.168.1.26:1234/api/v1/models",
        "chat_url": "http://192.168.1.26:1234/v1/chat/completions",
        "type": "lmstudio",
        "model": "deepseek-coder-v2-lite-instruct",
        "key": "sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4",
        "load_url": "http://192.168.1.26:1234/api/v1/models/load",
        "unload_url": "http://192.168.1.26:1234/api/v1/models/unload",
        "config": {"context_length": 4096, "eval_batch_size": 512, "flash_attention": True, "offload_kv_cache_to_gpu": True, "num_experts": 6},
        "health_timeout": 5,
    },
    "M3": {
        "health_url": "http://192.168.1.113:1234/api/v1/models",
        "chat_url": "http://192.168.1.113:1234/v1/chat/completions",
        "type": "lmstudio",
        "model": "mistral-7b-instruct-v0.3",
        "key": "sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux",
        "load_url": "http://192.168.1.113:1234/api/v1/models/load",
        "unload_url": "http://192.168.1.113:1234/api/v1/models/unload",
        "config": {"context_length": 4096, "eval_batch_size": 512, "flash_attention": True, "offload_kv_cache_to_gpu": True},
        "health_timeout": 5,
    },
    "OL1": {
        "health_url": "http://127.0.0.1:11434/api/tags",
        "chat_url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "qwen3:1.7b",
        "key": None,
        "load_url": None,
        "unload_url": None,
        "config": {},
        "health_timeout": 3,
    },
}

def compute_composite_score(pass_rate_pct, avg_latency_ms, error_rate_pct):
    """score = qualite*0.6 + vitesse*0.3 + fiabilite*0.1, all normalized 0-10."""
    quality = pass_rate_pct / 10.0       # 100% -> 10.0
    speed = max(0, 10 - avg_latency_ms / 1000.0)  # 0ms->10, 10000ms->0
    reliability = (100 - error_rate_pct) / 10.0  # 0% errors -> 10.0
    return round(quality * 0.6 + speed * 0.3 + reliability * 0.1, 2)

def load_history():
    """Load benchmark history from JSON file."""
    if not os.path.exists(HISTORY_FILE):
        return {"runs": [], "champion": {"model": "unknown", "score": 0, "since": "", "config": {}}}
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_history(data):
    """Save benchmark history, enforcing MAX_RUNS rotation."""
    if len(data["runs"]) > MAX_RUNS:
        data["runs"] = data["runs"][-MAX_RUNS:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def append_run(run_type, model_m1, config_m1, pass_rate, avg_latency_ms, total_tests, error_count, by_node=None, by_domain=None):
    """Append a benchmark run to history and return (score, regression_detected)."""
    history = load_history()
    error_rate = error_count * 100.0 / max(total_tests, 1)
    score = compute_composite_score(pass_rate, avg_latency_ms, error_rate)
    run = {
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "type": run_type,
        "model_m1": model_m1,
        "config_m1": config_m1,
        "score_composite": score,
        "pass_rate": pass_rate,
        "avg_latency_ms": avg_latency_ms,
        "total_tests": total_tests,
        "by_node": by_node or {},
        "by_domain": by_domain or {},
    }
    history["runs"].append(run)

    # Check regression: >10% drop vs previous run of same type
    regression = False
    same_type = [r for r in history["runs"][:-1] if r["type"] == run_type]
    if same_type:
        prev_score = same_type[-1]["score_composite"]
        if prev_score > 0 and (prev_score - score) / prev_score > 0.10:
            regression = True

    # Update champion if new high score
    if score > history["champion"].get("score", 0):
        history["champion"] = {
            "model": model_m1,
            "score": score,
            "since": datetime.now().strftime("%Y-%m-%d"),
            "config": config_m1,
        }

    save_history(history)
    return score, regression
```

**Step 3: Verify the module loads**

Run: `python3 -c "from jarvis_bench_utils import compute_composite_score; print(compute_composite_score(100, 11265, 0))"`
Expected: a number around 8.87 (quality=6.0 + speed=max(0,10-11.265)*0.3=-0.38 capped → recalc needed)

Actually: `quality=10.0*0.6=6.0`, `speed=max(0, 10-11.265)=0*0.3=0`, `reliability=10.0*0.1=1.0` → **7.0**

Run the command and verify output is `7.0`.

**Step 4: Commit**

```bash
cd C:/Users/franc && git add jarvis_bench_utils.py jarvis_benchmark_history.json
git commit -m "feat: add benchmark history utils + initial JSON"
```

---

### Task 2: Integrate history into autotest.py

**Files:**
- Modify: `C:/Users/franc/jarvis_autotest.py:342-358` (save_results function)
- Modify: `C:/Users/franc/jarvis_autotest.py:419-422` (main, after final save)

**Step 1: Add history import at top of autotest.py**

After the existing imports (line 3), add:

```python
from jarvis_bench_utils import append_run, NODES as BENCH_NODES
```

**Step 2: Add append_to_history() call in save_results()**

At the end of `save_results()` (after line 358), add:

```python
    # Append to benchmark history
    try:
        total = results["total"]
        if total > 0:
            pass_rate = results["pass"] * 100.0 / total
            # Compute global avg latency from all node averages
            all_lats = []
            for nd in results["by_node"].values():
                if nd.get("avg_latency"):
                    all_lats.extend([nd["avg_latency"]] * nd["total"])
            avg_lat = int(sum(all_lats) / len(all_lats)) if all_lats else 0
            # Simplified by_node for history
            bn = {n: {"pass": s["pass"], "total": s["total"], "avg_latency": s.get("avg_latency", 0)} for n, s in results["by_node"].items()}
            bd = {d: {"pass": s["pass"], "total": s["total"]} for d, s in results["by_domain"].items()}
            score, regression = append_run(
                "autotest", NODES["M1"]["model"],
                {"context_length": 8192, "temperature": 0.2},
                pass_rate, avg_lat, total, results["errors"],
                by_node=bn, by_domain=bd
            )
            if regression:
                print(f"  [REGRESSION] Score dropped >10%! Current: {score}", flush=True)
    except Exception as e:
        print(f"  [WARN] History append failed: {e}", flush=True)
```

**Step 3: Test by running 1 cycle**

Run: `python3 C:/Users/franc/jarvis_autotest.py 1 5`
Then verify: `python3 -c "import json; d=json.load(open('C:/Users/franc/jarvis_benchmark_history.json')); print(len(d['runs']), 'runs'); print('Score:', d['runs'][-1]['score_composite'])"`
Expected: `1 runs` and a score > 0.

**Step 4: Commit**

```bash
cd C:/Users/franc && git add jarvis_autotest.py
git commit -m "feat: autotest writes to benchmark history after each run"
```

---

### Task 3: Create cluster healer — health checks

**Files:**
- Create: `C:/Users/franc/jarvis_cluster_healer.py`

**Step 1: Write the healer with health check loop**

Write `C:/Users/franc/jarvis_cluster_healer.py`:

```python
#!/usr/bin/env python3
"""JARVIS Cluster Healer — auto-repair watchdog daemon."""
import json, time, sys, os, urllib.request, urllib.error, re
from datetime import datetime
from jarvis_bench_utils import NODES, load_history, append_run

LOG_FILE = "C:/Users/franc/jarvis_healer.log"
CHECK_INTERVAL = 60  # seconds between full checks
MINI_BENCH_THRESHOLD = 0.66  # 2/3 must pass

# Track state per node
node_state = {}
for nid in NODES:
    node_state[nid] = {
        "status": "unknown",  # healthy, degraded, offline, healing
        "last_check": None,
        "fail_count": 0,
        "heal_attempts": 0,
        "last_known_good": {"model": NODES[nid]["model"], "config": NODES[nid]["config"].copy()},
    }

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

def health_check(node_id):
    """Ping a node's health endpoint. Returns True if healthy."""
    cfg = NODES[node_id]
    url = cfg["health_url"]
    timeout = cfg["health_timeout"]
    try:
        headers = {}
        if cfg["key"]:
            headers["Authorization"] = f"Bearer {cfg['key']}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        # LM Studio: check at least one model loaded
        if cfg["type"] in ("lmstudio", "lmstudio-responses"):
            models = data.get("data", data.get("models", []))
            for m in models:
                if m.get("loaded_instances"):
                    return True
            return False  # no model loaded
        # Ollama: check models list
        if cfg["type"] == "ollama":
            return len(data.get("models", [])) > 0
        return True
    except Exception:
        return False

def mini_benchmark(node_id):
    """Run 3 quick questions, return pass rate (0.0-1.0)."""
    tests = [
        ("Reponds juste OK", "ok"),
        ("Combien font 2 + 2 ? Juste le nombre.", "4"),
        ("Traduis 'bonjour' en anglais. Un mot.", "hello"),
    ]
    cfg = NODES[node_id]
    passed = 0
    for prompt, check in tests:
        try:
            if cfg["type"] == "ollama":
                body = json.dumps({"model": cfg["model"], "messages": [{"role": "user", "content": prompt}], "stream": False, "think": False, "options": {"num_ctx": 2048}}).encode()
                req = urllib.request.Request(cfg["chat_url"], data=body, headers={"Content-Type": "application/json"})
            elif cfg["type"] == "lmstudio-responses":
                body = json.dumps({"model": cfg["model"], "input": prompt, "temperature": 0.2, "max_output_tokens": 50, "stream": False, "store": False}).encode()
                req = urllib.request.Request(cfg["chat_url"], data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"})
            else:
                body = json.dumps({"model": cfg["model"], "messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 50, "stream": False}).encode()
                req = urllib.request.Request(cfg["chat_url"], data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"})

            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())

            if cfg["type"] == "ollama":
                text = result.get("message", {}).get("content", "")
            elif cfg["type"] == "lmstudio-responses":
                output = result.get("output", [])
                text = output[0].get("content", "") if output else ""
            else:
                text = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip().lower()
            if check in text:
                passed += 1
        except Exception:
            pass
    return passed / len(tests)

def reload_model(node_id):
    """Unload then reload the model on a LM Studio node. Returns True on success."""
    cfg = NODES[node_id]
    if not cfg.get("load_url"):
        return False  # OL1 — can't reload via API
    state = node_state[node_id]
    model = state["last_known_good"]["model"]
    config = state["last_known_good"]["config"]
    try:
        # Unload
        body = json.dumps({"instance_id": model}).encode()
        req = urllib.request.Request(cfg["unload_url"], data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"})
        try:
            urllib.request.urlopen(req, timeout=30)
        except:
            pass  # may fail if already unloaded
        time.sleep(2)
        # Load with config
        load_body = {"model": model}
        load_body.update(config)
        body = json.dumps(load_body).encode()
        req = urllib.request.Request(cfg["load_url"], data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read())
        return result.get("status") == "loaded"
    except Exception as e:
        log(f"  Reload {node_id} failed: {e}")
        return False

def heal_node(node_id):
    """Attempt to heal a failed node: reload + mini-benchmark + rollback."""
    state = node_state[node_id]
    state["status"] = "healing"
    state["heal_attempts"] += 1
    log(f"HEALING {node_id} (attempt #{state['heal_attempts']})")

    # Step 1: Reload
    if not reload_model(node_id):
        log(f"  {node_id} reload FAILED — marking offline")
        state["status"] = "offline"
        return False

    log(f"  {node_id} reloaded — running mini-benchmark...")
    time.sleep(5)  # let model warm up

    # Step 2: Mini benchmark
    score = mini_benchmark(node_id)
    log(f"  {node_id} mini-bench: {score:.0%}")

    if score >= MINI_BENCH_THRESHOLD:
        state["status"] = "healthy"
        state["fail_count"] = 0
        state["heal_attempts"] = 0
        log(f"  {node_id} HEALED successfully")
        return True

    # Step 3: Rollback — try once more with original config
    if state["heal_attempts"] <= 2:
        log(f"  {node_id} mini-bench failed — retrying reload...")
        return heal_node(node_id)  # recursive retry (max 2)

    # Give up
    state["status"] = "offline"
    log(f"  {node_id} OFFLINE after {state['heal_attempts']} heal attempts")
    return False

def check_regression():
    """Check benchmark history for recent regression."""
    history = load_history()
    runs = history.get("runs", [])
    if len(runs) < 2:
        return
    last = runs[-1]
    prev = runs[-2]
    if prev["score_composite"] > 0:
        drop = (prev["score_composite"] - last["score_composite"]) / prev["score_composite"]
        if drop > 0.10:
            log(f"[REGRESSION] Score dropped {drop:.0%}: {prev['score_composite']} -> {last['score_composite']}")

def run_daemon():
    """Main daemon loop."""
    log("=" * 50)
    log("JARVIS Cluster Healer started")
    log(f"Monitoring: {', '.join(NODES.keys())}")
    log(f"Interval: {CHECK_INTERVAL}s")
    log("=" * 50)

    while True:
        for node_id in NODES:
            state = node_state[node_id]

            # Health check with retry
            healthy = health_check(node_id)
            if not healthy:
                time.sleep(5)
                healthy = health_check(node_id)  # retry once

            if healthy:
                if state["status"] != "healthy":
                    log(f"{node_id}: recovered (was {state['status']})")
                state["status"] = "healthy"
                state["fail_count"] = 0
                state["last_check"] = datetime.now().strftime("%H:%M:%S")
            else:
                state["fail_count"] += 1
                state["last_check"] = datetime.now().strftime("%H:%M:%S")
                log(f"{node_id}: FAILED (count={state['fail_count']})")

                if state["fail_count"] >= 2:
                    # Wait 10s before taking action (avoid reload during active request)
                    time.sleep(10)
                    heal_node(node_id)

        # Check for regression after all nodes checked
        check_regression()

        # Print status summary
        summary = " | ".join(f"{nid}:{node_state[nid]['status']}" for nid in NODES)
        log(f"Status: {summary}")

        time.sleep(CHECK_INTERVAL)

def print_status():
    """One-shot: check all nodes and print status."""
    for node_id in NODES:
        healthy = health_check(node_id)
        status = "OK" if healthy else "FAIL"
        print(f"{node_id}: {status}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print_status()
    else:
        try:
            run_daemon()
        except KeyboardInterrupt:
            log("Healer stopped by user")
```

**Step 2: Test health check mode**

Run: `python3 C:/Users/franc/jarvis_cluster_healer.py --status`
Expected: Each node shows OK or FAIL.

**Step 3: Test daemon for 2 cycles (reduce interval temporarily)**

Run: `timeout 130 python3 C:/Users/franc/jarvis_cluster_healer.py` (let it run ~2 cycles then Ctrl+C)
Expected: Status lines printed, all nodes healthy, no heal attempts.

**Step 4: Commit**

```bash
cd C:/Users/franc && git add jarvis_cluster_healer.py
git commit -m "feat: cluster healer daemon with auto-repair and rollback"
```

---

### Task 4: Create model arena

**Files:**
- Create: `C:/Users/franc/jarvis_model_arena.py`

**Step 1: Write the arena script**

Write `C:/Users/franc/jarvis_model_arena.py`:

```python
#!/usr/bin/env python3
"""JARVIS Model Arena — tournament system for comparing models on M1."""
import json, time, sys, os, subprocess, urllib.request
from datetime import datetime
from jarvis_bench_utils import NODES, load_history, save_history, append_run, compute_composite_score

# Models available on M1 (on-demand)
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
    """Unload whatever model is loaded on M1."""
    try:
        # Get loaded model
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
    """Load a model on M1 with given config. Returns True on success."""
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
    """Send 3 throwaway queries to warm up the model."""
    for prompt in ["Reponds OK", "2+2?", "Bonjour"]:
        try:
            body = json.dumps({"model": model_id, "input": prompt, "temperature": 0.2, "max_output_tokens": 20, "stream": False, "store": False}).encode()
            req = urllib.request.Request(M1["chat_url"], data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {M1['key']}"})
            urllib.request.urlopen(req, timeout=60)
        except:
            pass

def run_benchmark(cycles=5, tasks_per_cycle=40):
    """Run autotest benchmark, return (pass_rate, avg_latency_ms, total, errors)."""
    log(f"Running benchmark: {cycles} cycles x {tasks_per_cycle} tasks...")
    result = subprocess.run(
        [sys.executable, "C:/Users/franc/jarvis_autotest.py", str(cycles), str(tasks_per_cycle)],
        capture_output=True, text=True, timeout=1800, cwd="C:/Users/franc"
    )
    # Parse results from JSON
    try:
        data = json.load(open("C:/Users/franc/jarvis_autotest_results.json", encoding="utf-8"))
        total = data["total"]
        pass_rate = data["pass"] * 100.0 / max(total, 1)
        # Compute avg latency
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
    """Run a full tournament: champion vs candidate."""
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

    # Step 1: Benchmark champion (current state)
    log("\n--- CHAMPION benchmark ---")
    ch_pass, ch_lat, ch_total, ch_err = run_benchmark(cycles, 40)
    ch_err_rate = ch_err * 100.0 / max(ch_total, 1)
    ch_score = compute_composite_score(ch_pass, ch_lat, ch_err_rate)
    log(f"Champion: pass={ch_pass:.0f}% lat={ch_lat}ms score={ch_score}")

    # Step 2: Swap to candidate
    log(f"\n--- Loading CANDIDATE: {candidate['id']} ---")
    unload_m1()
    time.sleep(3)
    if not load_m1(candidate["id"], candidate["config"]):
        log("CANDIDATE load failed — restoring champion")
        load_m1(champion["model"], champion.get("config", M1["config"]))
        return

    time.sleep(5)
    warmup_m1(candidate["id"])

    # Step 3: Benchmark candidate
    log("\n--- CANDIDATE benchmark ---")
    ca_pass, ca_lat, ca_total, ca_err = run_benchmark(cycles, 40)
    ca_err_rate = ca_err * 100.0 / max(ca_total, 1)
    ca_score = compute_composite_score(ca_pass, ca_lat, ca_err_rate)
    log(f"Candidate: pass={ca_pass:.0f}% lat={ca_lat}ms score={ca_score}")

    # Step 4: Compare
    log(f"\n{'=' * 50}")
    log(f"RESULTS: Champion={ch_score} vs Candidate={ca_score}")

    if ca_score > ch_score:
        log(f"NEW CHAMPION: {candidate['id']} (score {ca_score} > {ch_score})")
        # Update history
        history["champion"] = {
            "model": candidate["id"],
            "score": ca_score,
            "since": datetime.now().strftime("%Y-%m-%d"),
            "config": candidate["config"],
        }
        save_history(history)
        # Record arena run
        append_run("arena", candidate["id"], candidate["config"], ca_pass, ca_lat, ca_total, ca_err)
    else:
        log(f"CHAMPION RETAINED: {champion['model']} (score {ch_score} >= {ca_score})")
        # Rollback to champion
        log("Restoring champion model...")
        unload_m1()
        time.sleep(3)
        load_m1(champion["model"], champion.get("config", M1["config"]))
        # Record arena run
        append_run("arena", candidate["id"], candidate["config"], ca_pass, ca_lat, ca_total, ca_err)

    log("=" * 50)

def show_history():
    """Print recent benchmark history."""
    history = load_history()
    ch = history.get("champion", {})
    print(f"\nChampion: {ch.get('model', '?')} (score={ch.get('score', 0)}, since={ch.get('since', '?')})")
    print(f"\nLast 10 runs:")
    for run in history.get("runs", [])[-10:]:
        print(f"  [{run['timestamp']}] {run['type']:8s} | {run['model_m1'][:30]:30s} | score={run['score_composite']:5.2f} | pass={run['pass_rate']:.0f}% | lat={run['avg_latency_ms']}ms")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 jarvis_model_arena.py <model-name>    # test a candidate")
        print("  python3 jarvis_model_arena.py --quick <model>  # quick test (2 cycles)")
        print("  python3 jarvis_model_arena.py --all            # test all candidates")
        print("  python3 jarvis_model_arena.py --history        # show history")
        print(f"\nAvailable candidates: {', '.join(CANDIDATE_MODELS.keys())}")
        sys.exit(0)

    if sys.argv[1] == "--history":
        show_history()
    elif sys.argv[1] == "--all":
        quick = "--quick" in sys.argv
        for name in CANDIDATE_MODELS:
            tournament(name, quick=quick)
    elif sys.argv[1] == "--quick":
        if len(sys.argv) > 2:
            tournament(sys.argv[2], quick=True)
        else:
            print("Usage: python3 jarvis_model_arena.py --quick <model-name>")
    else:
        tournament(sys.argv[1])
```

**Step 2: Test --history mode (safe, no model changes)**

Run: `python3 C:/Users/franc/jarvis_model_arena.py --history`
Expected: Shows champion and recent runs (may be empty or 1 run from Task 2).

**Step 3: Test usage message**

Run: `python3 C:/Users/franc/jarvis_model_arena.py`
Expected: Usage help with available candidates.

**Step 4: Commit**

```bash
cd C:/Users/franc && git add jarvis_model_arena.py
git commit -m "feat: model arena — tournament system with composite scoring"
```

---

### Task 5: Add plugin commands

**Files:**
- Create: `C:/Users/franc/.claude/plugins/local/jarvis-turbo/commands/heal-status.md`
- Create: `C:/Users/franc/.claude/plugins/local/jarvis-turbo/commands/arena.md`
- Create: `C:/Users/franc/.claude/plugins/local/jarvis-turbo/commands/benchmark-history.md`

**Step 1: Create /heal-status command**

Write `C:/Users/franc/.claude/plugins/local/jarvis-turbo/commands/heal-status.md`:

```markdown
---
name: heal-status
description: Affiche l'etat du cluster healer — statut de chaque noeud, dernier check, actions recentes
---

Verifie l'etat du cluster healer JARVIS.

**Quick check (pas de daemon requis):**
```bash
python3 C:/Users/franc/jarvis_cluster_healer.py --status
```

**Log recents:**
```bash
tail -20 C:/Users/franc/jarvis_healer.log
```

Presenter un tableau avec : Noeud | Statut | Dernier Check | Actions recentes.
```

**Step 2: Create /arena command**

Write `C:/Users/franc/.claude/plugins/local/jarvis-turbo/commands/arena.md`:

```markdown
---
name: arena
description: Lance un tournoi de modeles sur M1 — compare un candidat au champion actuel
args: model_name
---

Lance un tournoi Model Arena sur M1. Compare le modele $MODEL_NAME au champion actuel.

**ATTENTION:** Cette commande decharge le modele actuel de M1 pendant le tournoi (~30min). M1 sera indisponible pour les autres taches.

**Si model_name est fourni:**
```bash
python3 C:/Users/franc/jarvis_model_arena.py --quick $MODEL_NAME
```

**Si model_name est "all":**
```bash
python3 C:/Users/franc/jarvis_model_arena.py --all --quick
```

**Si pas de model_name, afficher l'historique:**
```bash
python3 C:/Users/franc/jarvis_model_arena.py --history
```

Modeles disponibles: qwen3-coder-30b, devstral, gpt-oss-20b
```

**Step 3: Create /benchmark-history command**

Write `C:/Users/franc/.claude/plugins/local/jarvis-turbo/commands/benchmark-history.md`:

```markdown
---
name: benchmark-history
description: Affiche l'historique des benchmarks — scores, tendance, champion actuel
---

Affiche l'historique des benchmarks du cluster JARVIS.

```bash
python3 C:/Users/franc/jarvis_model_arena.py --history
```

Aussi, lire le fichier brut pour analyse detaillee:
```bash
python3 -c "
import json
d = json.load(open('C:/Users/franc/jarvis_benchmark_history.json', encoding='utf-8'))
ch = d.get('champion', {})
print(f'Champion: {ch.get(\"model\",\"?\")} (score={ch.get(\"score\",0)}, depuis {ch.get(\"since\",\"?\")})')
runs = d.get('runs', [])
print(f'Total runs: {len(runs)}')
if len(runs) >= 2:
    trend = runs[-1]['score_composite'] - runs[-2]['score_composite']
    print(f'Tendance: {\"amelioration\" if trend > 0 else \"regression\"} ({trend:+.2f})')
for r in runs[-10:]:
    print(f'  [{r[\"timestamp\"]}] {r[\"type\"]:8s} score={r[\"score_composite\"]:5.2f} pass={r[\"pass_rate\"]:.0f}%')
"
```

Presenter sous forme de tableau avec tendance.
```

**Step 4: Commit**

```bash
cd C:/Users/franc && git add .claude/plugins/local/jarvis-turbo/commands/heal-status.md .claude/plugins/local/jarvis-turbo/commands/arena.md .claude/plugins/local/jarvis-turbo/commands/benchmark-history.md
git commit -m "feat: add /heal-status, /arena, /benchmark-history plugin commands"
```

---

### Task 6: End-to-end verification

**Step 1: Verify autotest + history integration**

Run:
```bash
python3 C:/Users/franc/jarvis_autotest.py 2 10
```
Then:
```bash
python3 C:/Users/franc/jarvis_model_arena.py --history
```
Expected: 2+ runs in history, scores displayed.

**Step 2: Verify healer health check**

Run:
```bash
python3 C:/Users/franc/jarvis_cluster_healer.py --status
```
Expected: All 4 nodes show OK.

**Step 3: Verify arena --history**

Run:
```bash
python3 C:/Users/franc/jarvis_model_arena.py --history
```
Expected: Champion displayed with score > 0, recent runs listed.

**Step 4: Verify plugin commands exist**

Run:
```bash
ls C:/Users/franc/.claude/plugins/local/jarvis-turbo/commands/heal-status.md C:/Users/franc/.claude/plugins/local/jarvis-turbo/commands/arena.md C:/Users/franc/.claude/plugins/local/jarvis-turbo/commands/benchmark-history.md
```
Expected: All 3 files exist.

**Step 5: Final commit**

```bash
cd F:/BUREAU/turbo && git add -A && git status
```
If clean, we're done. If changes pending:
```bash
git commit -m "test: verify end-to-end cluster resilience integration"
```

---

## Summary

| Task | What | Files | Depends on |
|------|------|-------|------------|
| 1 | Benchmark history utils | jarvis_bench_utils.py, benchmark_history.json | — |
| 2 | Autotest history integration | jarvis_autotest.py | Task 1 |
| 3 | Cluster healer daemon | jarvis_cluster_healer.py | Task 1 |
| 4 | Model arena tournament | jarvis_model_arena.py | Task 1 |
| 5 | Plugin commands | 3 .md files | Tasks 3, 4 |
| 6 | End-to-end verification | — | All |
