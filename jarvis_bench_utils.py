#!/usr/bin/env python3
"""Shared utilities for benchmark history, scoring, and node config."""
import json, os
from datetime import datetime

HISTORY_FILE = "C:/Users/franc/jarvis_benchmark_history.json"
MAX_RUNS = 500

NODES = {
    "M1": {
        "health_url": "http://10.5.0.2:1234/api/v1/models",
        "chat_url": "http://10.5.0.2:1234/api/v1/chat",
        "type": "lmstudio-responses",
        "model": "qwen/qwen3-8b",
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
    quality = pass_rate_pct / 10.0
    speed = max(0, 10 - avg_latency_ms / 1000.0)
    reliability = (100 - error_rate_pct) / 10.0
    return round(quality * 0.6 + speed * 0.3 + reliability * 0.1, 2)

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {"runs": [], "champion": {"model": "unknown", "score": 0, "since": "", "config": {}}}
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_history(data):
    if len(data["runs"]) > MAX_RUNS:
        data["runs"] = data["runs"][-MAX_RUNS:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def append_run(run_type, model_m1, config_m1, pass_rate, avg_latency_ms, total_tests, error_count, by_node=None, by_domain=None):
    """Append a benchmark run to history. Returns (score, regression_detected)."""
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

    regression = False
    same_type = [r for r in history["runs"][:-1] if r["type"] == run_type]
    if same_type:
        prev_score = same_type[-1]["score_composite"]
        if prev_score > 0 and (prev_score - score) / prev_score > 0.10:
            regression = True

    if score > history["champion"].get("score", 0):
        history["champion"] = {
            "model": model_m1,
            "score": score,
            "since": datetime.now().strftime("%Y-%m-%d"),
            "config": config_m1,
        }

    save_history(history)
    return score, regression
