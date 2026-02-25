#!/usr/bin/env python3
"""JARVIS Cluster Healer — auto-repair watchdog + auto-arena daemon."""
import json, time, sys, os, re, subprocess
import urllib.request, urllib.error
from datetime import datetime
from jarvis_bench_utils import NODES, load_history

LOG_FILE = "C:/Users/franc/jarvis_healer.log"
CHECK_INTERVAL = 60
MINI_BENCH_THRESHOLD = 0.66
ARENA_COOLDOWN_HOURS = 1
ARENA_WEEKLY_DAYS = 7

node_state = {}
for nid in NODES:
    node_state[nid] = {
        "status": "unknown",
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
    cfg = NODES[node_id]
    try:
        headers = {}
        if cfg["key"]:
            headers["Authorization"] = f"Bearer {cfg['key']}"
        req = urllib.request.Request(cfg["health_url"], headers=headers)
        with urllib.request.urlopen(req, timeout=cfg["health_timeout"]) as resp:
            data = json.loads(resp.read())
        if cfg["type"] in ("lmstudio", "lmstudio-responses"):
            for m in data.get("data", data.get("models", [])):
                if m.get("loaded_instances"):
                    return True
            return False
        if cfg["type"] == "ollama":
            return len(data.get("models", [])) > 0
        return True
    except Exception:
        return False

def mini_benchmark(node_id):
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
    cfg = NODES[node_id]
    if not cfg.get("load_url"):
        return False
    state = node_state[node_id]
    model = state["last_known_good"]["model"]
    config = state["last_known_good"]["config"]
    try:
        body = json.dumps({"instance_id": model}).encode()
        req = urllib.request.Request(cfg["unload_url"], data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"})
        try:
            urllib.request.urlopen(req, timeout=30)
        except:
            pass
        time.sleep(2)
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
    state = node_state[node_id]
    state["status"] = "healing"
    state["heal_attempts"] += 1
    log(f"HEALING {node_id} (attempt #{state['heal_attempts']})")

    if not reload_model(node_id):
        log(f"  {node_id} reload FAILED — marking offline")
        state["status"] = "offline"
        return False

    log(f"  {node_id} reloaded — running mini-benchmark...")
    time.sleep(5)

    score = mini_benchmark(node_id)
    log(f"  {node_id} mini-bench: {score:.0%}")

    if score >= MINI_BENCH_THRESHOLD:
        state["status"] = "healthy"
        state["fail_count"] = 0
        state["heal_attempts"] = 0
        log(f"  {node_id} HEALED successfully")
        return True

    if state["heal_attempts"] <= 2:
        log(f"  {node_id} mini-bench failed — retrying reload...")
        return heal_node(node_id)

    state["status"] = "offline"
    log(f"  {node_id} OFFLINE after {state['heal_attempts']} heal attempts")
    return False

def check_regression():
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

# === AUTO-ARENA ===

arena_state = {
    "last_arena": None,
    "last_models_m1": None,
    "cooldown_until": None,
}

def get_m1_models():
    """Get currently loaded models on M1."""
    cfg = NODES.get("M1")
    if not cfg:
        return []
    try:
        headers = {"Authorization": f"Bearer {cfg['key']}"}
        req = urllib.request.Request(cfg["health_url"], headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        models = []
        for m in data.get("data", data.get("models", [])):
            if m.get("loaded_instances"):
                models.append(m.get("id", m.get("model", "")))
        return sorted(models)
    except Exception:
        return []

def should_run_arena():
    """Check if arena should trigger (event-driven or weekly)."""
    now = datetime.now()

    # Cooldown check
    if arena_state["cooldown_until"] and now < arena_state["cooldown_until"]:
        return False, None

    # Event-driven: new model detected on M1
    current_models = get_m1_models()
    if current_models and current_models != arena_state["last_models_m1"]:
        if arena_state["last_models_m1"] is not None:
            new = set(current_models) - set(arena_state["last_models_m1"] or [])
            if new:
                arena_state["last_models_m1"] = current_models
                return True, f"new_model:{list(new)[0]}"
        arena_state["last_models_m1"] = current_models

    # Weekly check
    history = load_history()
    runs = history.get("runs", [])
    if runs:
        last_ts = runs[-1].get("timestamp", "")
        try:
            last_dt = datetime.fromisoformat(last_ts)
            days_since = (now - last_dt).days
            if days_since >= ARENA_WEEKLY_DAYS:
                return True, "weekly"
        except ValueError:
            pass
    elif not runs:
        return True, "first_run"

    return False, None

def run_arena(reason):
    """Run arena tournament via subprocess."""
    log(f"[ARENA] Triggering arena: {reason}")
    arena_state["cooldown_until"] = datetime.now() + __import__('datetime').timedelta(hours=ARENA_COOLDOWN_HOURS)
    arena_state["last_arena"] = datetime.now()

    try:
        result = subprocess.run(
            ["python3", "C:/Users/franc/jarvis_model_arena.py", "--quick", "--auto"],
            capture_output=True, text=True, timeout=1800
        )
        if result.returncode == 0:
            log(f"[ARENA] Complete: {result.stdout.strip()[-200:]}")
        else:
            log(f"[ARENA] Failed (exit {result.returncode}): {result.stderr.strip()[-200:]}")
    except subprocess.TimeoutExpired:
        log("[ARENA] Timeout after 30min")
    except Exception as e:
        log(f"[ARENA] Error: {e}")

def run_daemon():
    log("=" * 50)
    log("JARVIS Cluster Healer + Auto-Arena started")
    log(f"Monitoring: {', '.join(NODES.keys())}")
    log(f"Interval: {CHECK_INTERVAL}s | Arena cooldown: {ARENA_COOLDOWN_HOURS}h | Weekly: {ARENA_WEEKLY_DAYS}d")
    log("=" * 50)

    # Init M1 models baseline
    arena_state["last_models_m1"] = get_m1_models()

    cycle = 0
    while True:
        cycle += 1
        for node_id in NODES:
            state = node_state[node_id]
            healthy = health_check(node_id)
            if not healthy:
                time.sleep(5)
                healthy = health_check(node_id)

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
                    time.sleep(10)
                    heal_node(node_id)

        check_regression()

        # Auto-arena check every 5 cycles (~5 min)
        if cycle % 5 == 0:
            trigger, reason = should_run_arena()
            if trigger:
                run_arena(reason)

        summary = " | ".join(f"{nid}:{node_state[nid]['status']}" for nid in NODES)
        log(f"Status: {summary}")
        time.sleep(CHECK_INTERVAL)

def print_status():
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
