"""JARVIS Improve Loop 100 Cycles -- Amelioration continue via Telegram.

Lance 100 cycles d'amelioration autonome:
1. Diagnostic systeme (cluster, GPU, DB, commandes)
2. Identification des points faibles (gap analysis)
3. Generation de corrections/ameliorations via cluster IA
4. Application + test
5. Rapport Telegram a chaque cycle

Usage:
    python scripts/improve_loop_100.py                  # 100 cycles
    python scripts/improve_loop_100.py --cycles 10      # 10 cycles
    python scripts/improve_loop_100.py --dry-run        # preview sans modifier
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Setup paths
TURBO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TURBO_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("improve_loop")

# Telegram config
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT", "")

# Load .env if needed
if not TELEGRAM_TOKEN:
    env_path = TURBO_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            eq = line.find("=")
            if eq < 0:
                continue
            k, v = line[:eq].strip(), line[eq + 1:].strip()
            if k == "TELEGRAM_TOKEN":
                TELEGRAM_TOKEN = v
            elif k == "TELEGRAM_CHAT":
                TELEGRAM_CHAT = v

JARVIS_DB = TURBO_DIR / "data" / "jarvis.db"


# ── Telegram sender ─────────────────────────────────────────────────────────

def send_telegram(text: str, parse_mode: str = "Markdown") -> bool:
    """Send message to Telegram chat."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        logger.warning("Telegram not configured, skipping send")
        return False
    import urllib.request
    import urllib.parse

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # Split long messages
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT,
            "text": chunk,
            "parse_mode": parse_mode,
        }).encode()
        try:
            req = urllib.request.Request(url, data)
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            # Retry without parse_mode (Markdown can fail on special chars)
            try:
                data = urllib.parse.urlencode({
                    "chat_id": TELEGRAM_CHAT,
                    "text": chunk,
                }).encode()
                req = urllib.request.Request(url, data)
                urllib.request.urlopen(req, timeout=10)
            except Exception as e2:
                logger.error(f"Telegram send failed: {e2}")
                return False
    return True


# ── Cluster FULL — All nodes parallel (race + consensus) ─────────────────────

import re as _re_global
from concurrent.futures import ThreadPoolExecutor, as_completed

# Node definitions with weights for consensus
CLUSTER_NODES = [
    {"id": "M1", "weight": 1.8, "type": "lmstudio",
     "url": "http://127.0.0.1:1234/api/v1/chat", "model": "qwen3-8b", "timeout": 25},
    {"id": "M2", "weight": 1.4, "type": "lmstudio",
     "url": "http://192.168.1.26:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b", "timeout": 30},
    {"id": "M3", "weight": 1.0, "type": "lmstudio",
     "url": "http://192.168.1.113:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b", "timeout": 30},
    {"id": "OL1-local", "weight": 1.3, "type": "ollama",
     "url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b", "timeout": 15},
    # DELETED: model removed from Ollama
    # {"id": "gpt-oss", "weight": 1.9, "type": "ollama-cloud",
    #  "url": "http://127.0.0.1:11434/api/chat", "model": "gpt-oss:120b-cloud", "timeout": 60},
    # DELETED: model removed from Ollama
    # {"id": "devstral", "weight": 1.5, "type": "ollama-cloud",
    #  "url": "http://127.0.0.1:11434/api/chat", "model": "devstral-2:123b-cloud", "timeout": 60},
    {"id": "GEMINI", "weight": 1.2, "type": "gemini",
     "url": None, "model": "gemini-3-pro", "timeout": 45},
    {"id": "CLAUDE", "weight": 1.2, "type": "claude",
     "url": None, "model": "claude-proxy", "timeout": 45},
]


def _query_node(node: dict, prompt: str) -> dict[str, Any]:
    """Query a single cluster node. Returns {id, content, latency_ms, weight}."""
    import time as _t
    start = _t.time()
    node_id = node["id"]
    timeout = node["timeout"]

    try:
        if node["type"] == "lmstudio":
            r = subprocess.run(
                ["curl", "-s", "--max-time", str(timeout),
                 node["url"], "-H", "Content-Type: application/json",
                 "-d", json.dumps({
                     "model": node["model"],
                     "input": f"/nothink\n{prompt}",
                     "temperature": 0.3,
                     "max_output_tokens": 1024,
                     "stream": False, "store": False,
                 })],
                capture_output=True, text=True, timeout=timeout + 5,
            )
            if r.returncode == 0 and r.stdout.strip():
                data = json.loads(r.stdout)
                # LM Studio Responses API: find last message block
                for item in reversed(data.get("output", [])):
                    if item.get("type") == "message":
                        content = item.get("content", "")
                        if isinstance(content, list):
                            content = content[0].get("text", "")
                        if content:
                            return {"id": node_id, "content": content,
                                    "latency_ms": int((_t.time() - start) * 1000),
                                    "weight": node["weight"]}
                # Fallback: OpenAI-compat format
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    if content:
                        return {"id": node_id, "content": content,
                                "latency_ms": int((_t.time() - start) * 1000),
                                "weight": node["weight"]}

        elif node["type"] in ("ollama", "ollama-cloud"):
            payload = {
                "model": node["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }
            if node["type"] == "ollama-cloud":
                payload["think"] = False
            r = subprocess.run(
                ["curl", "-s", "--max-time", str(timeout),
                 node["url"], "-d", json.dumps(payload)],
                capture_output=True, text=True, timeout=timeout + 5,
            )
            if r.returncode == 0 and r.stdout.strip():
                data = json.loads(r.stdout)
                content = data.get("message", {}).get("content", "")
                if content:
                    content = _re_global.sub(r"<think>.*?</think>", "", content, flags=_re_global.DOTALL).strip()
                    if content:
                        return {"id": node_id, "content": content,
                                "latency_ms": int((_t.time() - start) * 1000),
                                "weight": node["weight"]}

        elif node["type"] == "gemini":
            r = subprocess.run(
                ["node", "/home/turbo/jarvis-m1-ops/gemini-proxy.js", prompt[:2000]],
                capture_output=True, text=True, timeout=timeout,
            )
            if r.returncode == 0 and r.stdout.strip():
                content = r.stdout.strip()
                if len(content) > 10:
                    return {"id": node_id, "content": content,
                            "latency_ms": int((_t.time() - start) * 1000),
                            "weight": node["weight"]}

        elif node["type"] == "claude":
            r = subprocess.run(
                ["node", "/home/turbo/jarvis-m1-ops/claude-proxy.js", prompt[:2000]],
                capture_output=True, text=True, timeout=timeout,
            )
            if r.returncode == 0 and r.stdout.strip():
                content = r.stdout.strip()
                if len(content) > 10:
                    return {"id": node_id, "content": content,
                            "latency_ms": int((_t.time() - start) * 1000),
                            "weight": node["weight"]}

    except Exception as e:
        logger.debug(f"[{node_id}] failed: {e}")

    return {"id": node_id, "content": "", "latency_ms": int((_t.time() - start) * 1000), "weight": node["weight"]}


def cluster_race(prompt: str) -> tuple[str, str]:
    """Race all nodes in parallel, return (content, winner_id) from first good response."""
    with ThreadPoolExecutor(max_workers=len(CLUSTER_NODES)) as pool:
        futures = {pool.submit(_query_node, node, prompt): node["id"] for node in CLUSTER_NODES}
        for future in as_completed(futures, timeout=65):
            try:
                result = future.result()
                if result["content"]:
                    logger.info(f"  RACE WINNER: [{result['id']}] {result['latency_ms']}ms")
                    # Cancel remaining futures (best effort)
                    for f in futures:
                        f.cancel()
                    return result["content"], result["id"]
            except Exception:
                pass
    return "", "none"


def cluster_consensus(prompt: str, min_responses: int = 2) -> tuple[str, str, list[dict]]:
    """Query all nodes, collect responses, return weighted best.

    Returns: (best_content, attribution, all_results)
    """
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(CLUSTER_NODES)) as pool:
        futures = {pool.submit(_query_node, node, prompt): node for node in CLUSTER_NODES}
        for future in as_completed(futures, timeout=70):
            try:
                result = future.result()
                if result["content"]:
                    results.append(result)
            except Exception:
                pass

    if not results:
        return "", "none", []

    # Sort by weight (higher = more trusted)
    results.sort(key=lambda r: r["weight"], reverse=True)

    # Log all responses
    for r in results:
        logger.info(f"  [{r['id']}] w={r['weight']} {r['latency_ms']}ms — {r['content'][:60]}...")

    # Return highest-weighted response
    best = results[0]
    attribution = f"{best['id']} (w={best['weight']}, {len(results)} nodes responded)"
    return best["content"], attribution, results


def cluster_query(prompt: str, timeout_s: int = 30) -> str:
    """Query cluster — race mode (fastest wins). Wrapper for backward compat."""
    content, winner = cluster_race(prompt)
    return content


# ── Diagnostic functions ─────────────────────────────────────────────────────

def check_cluster_health() -> dict[str, Any]:
    """Quick health check of all cluster nodes."""
    nodes = {
        "M1": "http://127.0.0.1:1234/api/v1/models",
        "OL1": "http://127.0.0.1:11434/api/tags",
        "M2": "http://192.168.1.26:1234/api/v1/models",
        "M3": "http://192.168.1.113:1234/api/v1/models",
    }
    results: dict[str, str] = {}
    for name, url in nodes.items():
        try:
            r = subprocess.run(
                ["curl", "-s", "--max-time", "3", url],
                capture_output=True, text=True, timeout=5,
            )
            results[name] = "online" if r.returncode == 0 and r.stdout.strip() else "degraded"
        except Exception:
            results[name] = "offline"

    online = sum(1 for v in results.values() if v == "online")
    return {"nodes": results, "online": online, "total": len(nodes)}


def check_gpu_status() -> dict[str, Any]:
    """Get GPU temperatures and VRAM usage."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,temperature.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            return {"error": "nvidia-smi failed"}
        gpus = []
        max_temp = 0
        total_vram_used = 0
        total_vram = 0
        for line in r.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                temp = int(parts[1])
                used = int(parts[2])
                total = int(parts[3])
                max_temp = max(max_temp, temp)
                total_vram_used += used
                total_vram += total
                gpus.append({"idx": int(parts[0]), "temp": temp, "vram_used_mb": used, "vram_total_mb": total})
        return {"gpus": len(gpus), "max_temp": max_temp, "vram_used_gb": round(total_vram_used / 1024, 1),
                "vram_total_gb": round(total_vram / 1024, 1)}
    except Exception as e:
        return {"error": str(e)}


def check_db_stats() -> dict[str, Any]:
    """Check database health and stats."""
    stats: dict[str, Any] = {}
    for db_name, db_path in [("jarvis", JARVIS_DB), ("etoile", TURBO_DIR / "data" / "etoile.db")]:
        if not db_path.exists():
            stats[db_name] = {"error": "not found"}
            continue
        try:
            conn = sqlite3.connect(str(db_path))
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            total_rows = 0
            for (tbl,) in tables:
                try:
                    cnt = conn.execute(f"SELECT COUNT(*) FROM [{tbl}]").fetchone()[0]
                    total_rows += cnt
                except Exception:
                    pass
            size_kb = db_path.stat().st_size // 1024
            stats[db_name] = {"tables": len(tables), "rows": total_rows, "size_kb": size_kb}
            conn.close()
        except Exception as e:
            stats[db_name] = {"error": str(e)}
    return stats


def check_commands_health() -> dict[str, Any]:
    """Check voice commands system health."""
    try:
        from src.commands import COMMANDS, VOICE_CORRECTIONS, match_command
        cmd, params, score = match_command("ouvre chrome")
        return {
            "total_commands": len(COMMANDS),
            "voice_corrections": len(VOICE_CORRECTIONS),
            "test_match": cmd.name if cmd else None,
            "test_score": score,
        }
    except Exception as e:
        return {"error": str(e)}


def check_source_issues() -> list[dict[str, str]]:
    """Find potential issues in source files."""
    issues: list[dict[str, str]] = []
    src_dir = TURBO_DIR / "src"
    for py_file in sorted(src_dir.glob("*.py")):
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
            lines = content.split("\n")

            # Check for common issues
            if len(lines) > 500:
                issues.append({"file": py_file.name, "issue": f"large_file ({len(lines)} lines)", "severity": "low"})
            if "TODO" in content or "FIXME" in content:
                todo_count = content.count("TODO") + content.count("FIXME")
                issues.append({"file": py_file.name, "issue": f"{todo_count} TODO/FIXME", "severity": "medium"})
            if "except:" in content or "except Exception:" in content:
                bare_except = content.count("except:") + content.count("except Exception:\n        pass")
                if bare_except > 3:
                    issues.append({"file": py_file.name, "issue": f"{bare_except} bare excepts", "severity": "low"})
            if "import *" in content:
                issues.append({"file": py_file.name, "issue": "wildcard import", "severity": "medium"})
        except Exception:
            pass
    return issues[:20]


# ── Improvement categories ───────────────────────────────────────────────────

IMPROVEMENT_CATEGORIES = [
    "voice_commands",       # New commands, better triggers, corrections
    "cluster_performance",  # Routing, timeouts, fallbacks
    "error_handling",       # Bare excepts, missing retries
    "code_quality",         # TODO/FIXME, large files, dead code
    "security",             # Hardcoded paths, missing validation
    "testing",              # Missing tests, test coverage
    "documentation",        # Missing docstrings, outdated docs
    "database",             # Schema optimizations, indexes
    "monitoring",           # Better logging, metrics
    "automation",           # New autonomous tasks, pipelines
]


_ISSUE_SEEN: set[str] = set()  # Track seen issues to avoid repeats


def _find_real_issue(category: str) -> dict[str, Any] | None:
    """Find a real, actionable issue in source code for a given category."""
    import re as _re
    src_dir = TURBO_DIR / "src"
    scripts_dir = TURBO_DIR / "scripts"

    def _unseen(key: str, result: dict) -> dict | None:
        if key in _ISSUE_SEEN:
            return None
        _ISSUE_SEEN.add(key)
        return result

    if category == "error_handling":
        for py_file in sorted(src_dir.glob("*.py")):
            try:
                lines = py_file.read_text(encoding="utf-8", errors="replace").split("\n")
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    # bare except
                    if stripped == "except:":
                        key = f"eh:{py_file.name}:{i}"
                        ctx = "\n".join(lines[max(0, i - 3):i + 4])
                        r = _unseen(key, {"file": f"src/{py_file.name}", "line": i + 1, "context": ctx,
                                          "issue": "bare except: swallows all errors"})
                        if r:
                            return r
                    # except Exception: pass
                    if stripped.startswith("except") and i + 1 < len(lines) and lines[i + 1].strip() == "pass":
                        key = f"ehp:{py_file.name}:{i}"
                        ctx = "\n".join(lines[max(0, i - 3):i + 4])
                        r = _unseen(key, {"file": f"src/{py_file.name}", "line": i + 1, "context": ctx,
                                          "issue": "except + pass hides errors"})
                        if r:
                            return r
                    # broad except Exception without logging
                    if stripped == "except Exception as e:" and i + 1 < len(lines):
                        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                        if next_line == "pass" or next_line.startswith("return"):
                            key = f"ehn:{py_file.name}:{i}"
                            ctx = "\n".join(lines[max(0, i - 2):i + 4])
                            r = _unseen(key, {"file": f"src/{py_file.name}", "line": i + 1, "context": ctx,
                                              "issue": "exception caught but not logged"})
                            if r:
                                return r
            except Exception:
                pass

    elif category == "code_quality":
        for py_file in sorted(src_dir.glob("*.py")):
            try:
                lines = py_file.read_text(encoding="utf-8", errors="replace").split("\n")
                for i, line in enumerate(lines):
                    # TODO/FIXME
                    if "TODO" in line or "FIXME" in line or "HACK" in line or "XXX" in line:
                        key = f"cq:{py_file.name}:{i}"
                        ctx = "\n".join(lines[max(0, i - 1):i + 3])
                        r = _unseen(key, {"file": f"src/{py_file.name}", "line": i + 1, "context": ctx,
                                          "issue": f"TODO/FIXME: {line.strip()[:80]}"})
                        if r:
                            return r
                    # duplicate imports
                    if line.strip().startswith("import ") or line.strip().startswith("from "):
                        for j in range(i + 1, min(i + 50, len(lines))):
                            if lines[j].strip() == line.strip() and line.strip():
                                key = f"cqd:{py_file.name}:{i}:{j}"
                                ctx = f"Line {i+1}: {line.strip()}\nLine {j+1}: {lines[j].strip()}"
                                r = _unseen(key, {"file": f"src/{py_file.name}", "line": j + 1, "context": ctx,
                                                  "issue": f"duplicate import: {line.strip()[:60]}"})
                                if r:
                                    return r
                    # unused variable assignment (simple heuristic: var = ... never used again)
                    if "import *" in line:
                        key = f"cqw:{py_file.name}:{i}"
                        ctx = "\n".join(lines[max(0, i - 1):i + 2])
                        r = _unseen(key, {"file": f"src/{py_file.name}", "line": i + 1, "context": ctx,
                                          "issue": f"wildcard import: {line.strip()}"})
                        if r:
                            return r
            except Exception:
                pass

    elif category == "security":
        for py_file in sorted(src_dir.glob("*.py")):
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    # Hardcoded credentials
                    if _re.search(r'(password|secret|token|api_key)\s*=\s*["\'][^"\']{5,}', line, _re.I):
                        key = f"sec:{py_file.name}:{i}"
                        ctx = "\n".join(lines[max(0, i - 1):i + 3])
                        r = _unseen(key, {"file": f"src/{py_file.name}", "line": i + 1, "context": ctx,
                                          "issue": "hardcoded credential"})
                        if r:
                            return r
                    # subprocess with shell=True
                    if "shell=True" in line and "subprocess" in content:
                        key = f"secs:{py_file.name}:{i}"
                        ctx = "\n".join(lines[max(0, i - 2):i + 3])
                        r = _unseen(key, {"file": f"src/{py_file.name}", "line": i + 1, "context": ctx,
                                          "issue": "subprocess with shell=True (injection risk)"})
                        if r:
                            return r
                    # eval/exec usage
                    if _re.search(r'\beval\s*\(', line) or _re.search(r'\bexec\s*\(', line):
                        if "# safe" not in line.lower() and "compile" not in line:
                            key = f"sece:{py_file.name}:{i}"
                            ctx = "\n".join(lines[max(0, i - 1):i + 3])
                            r = _unseen(key, {"file": f"src/{py_file.name}", "line": i + 1, "context": ctx,
                                              "issue": "eval/exec usage (code injection risk)"})
                            if r:
                                return r
            except Exception:
                pass

    elif category == "testing":
        # Find functions without any test
        tested_funcs: set[str] = set()
        test_dir = TURBO_DIR / "tests"
        if test_dir.exists():
            for tf in test_dir.glob("*.py"):
                try:
                    content = tf.read_text(encoding="utf-8", errors="replace")
                    tested_funcs.update(_re.findall(r'def test_(\w+)', content))
                except Exception:
                    pass
        # Find public functions in src/ that have no test
        for py_file in sorted(src_dir.glob("*.py")):
            try:
                lines = py_file.read_text(encoding="utf-8", errors="replace").split("\n")
                for i, line in enumerate(lines):
                    m = _re.match(r'^def (\w+)\(', line)
                    if m and not m.group(1).startswith("_"):
                        fname = m.group(1)
                        if fname not in tested_funcs and fname not in ("main", "setup", "run"):
                            key = f"test:{py_file.name}:{fname}"
                            ctx = "\n".join(lines[i:i + 5])
                            r = _unseen(key, {"file": f"src/{py_file.name}", "line": i + 1, "context": ctx,
                                              "issue": f"function {fname}() has no test"})
                            if r:
                                return r
            except Exception:
                pass

    elif category == "documentation":
        # Find functions/classes without docstrings
        for py_file in sorted(src_dir.glob("*.py")):
            try:
                lines = py_file.read_text(encoding="utf-8", errors="replace").split("\n")
                for i, line in enumerate(lines):
                    if _re.match(r'^\s*(def|class) \w+', line):
                        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                        if not next_line.startswith('"""') and not next_line.startswith("'''"):
                            func_name = _re.match(r'^\s*(def|class) (\w+)', line)
                            if func_name and not func_name.group(2).startswith("_"):
                                key = f"doc:{py_file.name}:{i}"
                                ctx = "\n".join(lines[i:i + 4])
                                r = _unseen(key, {"file": f"src/{py_file.name}", "line": i + 1, "context": ctx,
                                                  "issue": f"{func_name.group(1)} {func_name.group(2)} missing docstring"})
                                if r:
                                    return r
            except Exception:
                pass

    elif category == "voice_commands":
        # Find voice commands with very similar triggers (potential conflicts)
        try:
            conn = sqlite3.connect(str(JARVIS_DB))
            rows = conn.execute("SELECT name, triggers FROM voice_commands WHERE enabled=1").fetchall()
            conn.close()
            triggers_map: dict[str, list[str]] = {}
            for name, triggers_json in rows:
                for t in json.loads(triggers_json):
                    t_lower = t.lower().strip()
                    if len(t_lower) > 3:
                        triggers_map.setdefault(t_lower, []).append(name)
            # Find duplicate triggers
            for trigger, cmds in triggers_map.items():
                if len(cmds) > 1:
                    key = f"vc:dup:{trigger}"
                    r = _unseen(key, {"file": "data/jarvis.db", "line": 0,
                                      "context": json.dumps({"trigger": trigger, "commands": cmds}),
                                      "issue": f"duplicate trigger '{trigger}' -> {cmds}"})
                    if r:
                        return r
        except Exception:
            pass
        # Also check for short triggers (< 3 words, high false positive risk)
        try:
            conn = sqlite3.connect(str(JARVIS_DB))
            rows = conn.execute("SELECT name, triggers FROM voice_commands WHERE enabled=1").fetchall()
            conn.close()
            for name, triggers_json in rows:
                for t in json.loads(triggers_json):
                    words = t.strip().split()
                    if len(words) == 1 and len(words[0]) < 5:
                        key = f"vc:short:{name}:{t}"
                        r = _unseen(key, {"file": "data/jarvis.db", "line": 0,
                                          "context": json.dumps({"name": name, "trigger": t}),
                                          "issue": f"very short trigger '{t}' on cmd {name} (false positive risk)"})
                        if r:
                            return r
        except Exception:
            pass

    elif category == "monitoring":
        # Find modules without logging
        for py_file in sorted(src_dir.glob("*.py")):
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
                if "logger" not in content and "logging" not in content and len(content) > 500:
                    key = f"mon:{py_file.name}"
                    r = _unseen(key, {"file": f"src/{py_file.name}", "line": 1,
                                      "context": content[:200],
                                      "issue": f"No logging in {py_file.name} ({len(content)} bytes)"})
                    if r:
                        return r
            except Exception:
                pass
        # Find functions with no timing/metrics
        for py_file in sorted(src_dir.glob("*.py")):
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
                lines = content.split("\n")
                if "time.time()" not in content and "perf_counter" not in content and len(content) > 2000:
                    for i, line in enumerate(lines):
                        if _re.match(r'^async def \w+\(', line) or _re.match(r'^def \w+\(', line):
                            key = f"mont:{py_file.name}:{i}"
                            ctx = "\n".join(lines[i:i + 5])
                            r = _unseen(key, {"file": f"src/{py_file.name}", "line": i + 1, "context": ctx,
                                              "issue": f"no timing/metrics in {py_file.name}"})
                            if r:
                                return r
            except Exception:
                pass

    elif category == "database":
        # Check for missing indexes on large tables
        try:
            conn = sqlite3.connect(str(JARVIS_DB))
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            for (tbl,) in tables:
                indexes = conn.execute(f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{tbl}'").fetchall()
                cnt = conn.execute(f"SELECT COUNT(*) FROM [{tbl}]").fetchone()[0]
                if cnt > 50 and len(indexes) == 0:
                    cols = conn.execute(f"PRAGMA table_info([{tbl}])").fetchall()
                    col_names = [c[1] for c in cols]
                    key = f"db:idx:{tbl}"
                    r = _unseen(key, {"file": "data/jarvis.db", "line": 0,
                                      "context": f"Table {tbl}: {cnt} rows, 0 indexes, cols: {col_names}",
                                      "issue": f"Table {tbl} has {cnt} rows but no indexes"})
                    if r:
                        conn.close()
                        return r
            conn.close()
        except Exception:
            pass
        # Check etoile.db too
        try:
            etoile_db = TURBO_DIR / "data" / "etoile.db"
            if etoile_db.exists():
                conn = sqlite3.connect(str(etoile_db))
                tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                for (tbl,) in tables:
                    indexes = conn.execute(f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{tbl}'").fetchall()
                    cnt = conn.execute(f"SELECT COUNT(*) FROM [{tbl}]").fetchone()[0]
                    if cnt > 100 and len(indexes) == 0:
                        key = f"db:eidx:{tbl}"
                        cols = conn.execute(f"PRAGMA table_info([{tbl}])").fetchall()
                        r = _unseen(key, {"file": "data/etoile.db", "line": 0,
                                          "context": f"Table {tbl}: {cnt} rows, 0 indexes, cols: {[c[1] for c in cols]}",
                                          "issue": f"etoile.db: Table {tbl} has {cnt} rows but no indexes"})
                        if r:
                            conn.close()
                            return r
                conn.close()
        except Exception:
            pass

    elif category == "cluster_performance":
        # Find hardcoded timeouts that could be optimized
        for py_file in sorted(src_dir.glob("*.py")):
            try:
                lines = py_file.read_text(encoding="utf-8", errors="replace").split("\n")
                for i, line in enumerate(lines):
                    # Very long timeouts (>60s)
                    m = _re.search(r'timeout\s*[=:]\s*(\d+)', line)
                    if m and int(m.group(1)) > 60:
                        key = f"cp:timeout:{py_file.name}:{i}"
                        ctx = "\n".join(lines[max(0, i - 1):i + 3])
                        r = _unseen(key, {"file": f"src/{py_file.name}", "line": i + 1, "context": ctx,
                                          "issue": f"high timeout {m.group(1)}s could cause blocking"})
                        if r:
                            return r
                    # Missing timeout on requests/curl
                    if "httpx.AsyncClient()" in line and "timeout" not in line:
                        key = f"cp:notimeout:{py_file.name}:{i}"
                        ctx = "\n".join(lines[max(0, i - 1):i + 3])
                        r = _unseen(key, {"file": f"src/{py_file.name}", "line": i + 1, "context": ctx,
                                          "issue": "httpx client without explicit timeout"})
                        if r:
                            return r
            except Exception:
                pass

    elif category == "automation":
        # Find repetitive patterns that could be automated
        for py_file in sorted(src_dir.glob("*.py")):
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
                lines = content.split("\n")
                # Find repeated try/except blocks with same structure
                for i, line in enumerate(lines):
                    if line.strip() == "try:" and i + 5 < len(lines):
                        block = "\n".join(lines[i:i + 6])
                        # Check if same block appears elsewhere
                        rest = "\n".join(lines[i + 6:])
                        if block in rest:
                            key = f"auto:dup:{py_file.name}:{i}"
                            r = _unseen(key, {"file": f"src/{py_file.name}", "line": i + 1, "context": block,
                                              "issue": "duplicated try/except block could be refactored"})
                            if r:
                                return r
            except Exception:
                pass

    return None


async def run_improvement_cycle(cycle_num: int, total: int, dry_run: bool = False) -> dict[str, Any]:
    """Run a single improvement cycle with real code context."""
    cycle_start = time.time()
    category = IMPROVEMENT_CATEGORIES[cycle_num % len(IMPROVEMENT_CATEGORIES)]
    report: dict[str, Any] = {
        "cycle": cycle_num,
        "total": total,
        "category": category,
        "actions": [],
        "improvements": 0,
        "errors": [],
    }

    logger.info(f"=== Cycle {cycle_num}/{total} [{category}] ===")

    # Phase 1: Diagnostic
    diag = {
        "cluster": check_cluster_health(),
        "gpu": check_gpu_status(),
        "commands": check_commands_health(),
    }
    report["diagnostic"] = diag

    # Phase 2: Find a REAL issue in the codebase
    real_issue = await asyncio.to_thread(_find_real_issue, category)
    if not real_issue:
        report["actions"].append(f"No actionable issues found for {category}")
        report["duration_s"] = round(time.time() - cycle_start, 1)
        return report

    report["issue"] = real_issue

    # Phase 3: Ask FULL CLUSTER (consensus) for fix with REAL code context
    prompt = (
        f"Tu es un dev Python senior. Corrige ce probleme EXACTEMENT.\n"
        f"Fichier: {real_issue['file']}, ligne {real_issue['line']}\n"
        f"Probleme: {real_issue['issue']}\n"
        f"Code actuel:\n```\n{real_issue['context']}\n```\n\n"
        f"Reponds en JSON strict:\n"
        '{{"old": "ligne(s) exacte(s) a remplacer (copie exacte)", '
        '"new": "nouvelle version corrigee", '
        '"action": "description courte du fix"}}\n\n'
        "IMPORTANT: 'old' doit etre une copie EXACTE du code actuel. Reponds UNIQUEMENT JSON."
    )

    # Use consensus (all nodes parallel) for code fixes
    suggestion_text, attribution, all_results = await asyncio.to_thread(
        cluster_consensus, prompt, 2
    )
    report["cluster_responses"] = len(all_results)
    report["cluster_winner"] = attribution
    nodes_used = [r["id"] for r in all_results]
    report["nodes_used"] = nodes_used
    report["actions"].append(f"Cluster: {len(all_results)} nodes ({', '.join(nodes_used)})")

    if not suggestion_text:
        report["errors"].append("Cluster: no valid response from any node")
        report["duration_s"] = round(time.time() - cycle_start, 1)
        return report

    # Phase 4: Parse best response, try others if JSON parse fails
    suggestion = None
    for result in all_results:
        try:
            text = result["content"].strip()
            # Extract JSON from markdown code blocks if present
            if "```" in text:
                parts = text.split("```")
                for part in parts[1:]:
                    cleaned = part.strip()
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:].strip()
                    if cleaned.startswith("{"):
                        text = cleaned.split("```")[0].strip() if "```" in cleaned else cleaned
                        break
            parsed = json.loads(text)
            if parsed.get("old") and parsed.get("new"):
                suggestion = parsed
                report["suggestion_source"] = result["id"]
                break
        except (json.JSONDecodeError, IndexError):
            continue

    if not suggestion:
        report["errors"].append(f"JSON parse failed on all {len(all_results)} responses")
        report["suggestion_raw"] = suggestion_text[:200]
        report["duration_s"] = round(time.time() - cycle_start, 1)
        return report

    report["suggestion"] = suggestion
    report["actions"].append(f"Fix by [{report.get('suggestion_source', '?')}]: {suggestion.get('action', '?')}")

    # Phase 5: Apply fix if old text matches
    target_path = real_issue["file"]
    if not dry_run and target_path.startswith("src/"):
        target_file = TURBO_DIR / target_path
        if target_file.exists():
            try:
                content = target_file.read_text(encoding="utf-8")
                old_code = suggestion.get("old", "")
                new_code = suggestion.get("new", "")

                if old_code and old_code in content and new_code and old_code != new_code:
                    new_content = content.replace(old_code, new_code, 1)
                    target_file.write_text(new_content, encoding="utf-8")

                    # Syntax check
                    r = subprocess.run(
                        [sys.executable, "-c",
                         f"import py_compile; py_compile.compile(r'{target_file}', doraise=True)"],
                        capture_output=True, text=True, timeout=10,
                    )
                    if r.returncode == 0:
                        report["applied"] = True
                        report["improvements"] += 1
                        report["syntax_valid"] = True
                        report["actions"].append(f"Applied + syntax OK: {target_path}")
                        logger.info(f"Improvement applied to {target_path}")
                    else:
                        # Revert
                        target_file.write_text(content, encoding="utf-8")
                        report["applied"] = False
                        report["syntax_valid"] = False
                        report["errors"].append(f"Syntax error after apply, reverted")
                        report["actions"].append("REVERTED")
                else:
                    report["applied"] = False
                    if not old_code or old_code not in content:
                        report["actions"].append("old code not found in file")
                    else:
                        report["actions"].append("no change needed")
            except Exception as e:
                report["errors"].append(f"Apply: {e}")
    elif target_path.startswith("data/") and not dry_run:
        # Database improvements (add indexes, etc.)
        if "index" in real_issue["issue"].lower():
            try:
                conn = sqlite3.connect(str(JARVIS_DB))
                # Parse table name from issue
                import re as _re
                m = _re.search(r"Table (\w+)", real_issue["issue"])
                if m:
                    tbl = m.group(1)
                    # Add index on first non-id column
                    cols = conn.execute(f"PRAGMA table_info([{tbl}])").fetchall()
                    for col in cols:
                        if col[1] not in ("id", "rowid"):
                            idx_name = f"idx_{tbl}_{col[1]}"
                            conn.execute(f"CREATE INDEX IF NOT EXISTS [{idx_name}] ON [{tbl}]([{col[1]}])")
                            report["applied"] = True
                            report["improvements"] += 1
                            report["actions"].append(f"Created index {idx_name}")
                            logger.info(f"Created index {idx_name}")
                            break
                conn.commit()
                conn.close()
            except Exception as e:
                report["errors"].append(f"DB fix: {e}")
    else:
        if dry_run:
            report["actions"].append("DRY RUN")

    report["duration_s"] = round(time.time() - cycle_start, 1)
    return report


def format_telegram_report(report: dict[str, Any]) -> str:
    """Format a cycle report for Telegram."""
    cycle = report.get("cycle", "?")
    total = report.get("total", "?")
    cat = report.get("category", "?")
    dur = report.get("duration_s", "?")
    improvements = report.get("improvements", 0)
    errors = report.get("errors", [])
    diag = report.get("diagnostic", {})
    suggestion = report.get("suggestion", {})

    status = "OK" if not errors else "WARN"
    applied = "OUI" if report.get("applied") else "NON"

    cluster_info = diag.get("cluster", {})
    gpu_info = diag.get("gpu", {})

    lines = [
        f"JARVIS Improve #{cycle}/{total}",
        f"Categorie: {cat}",
        f"Cluster: {cluster_info.get('online', '?')}/{cluster_info.get('total', '?')} | GPU: {gpu_info.get('max_temp', '?')}C",
        f"Suggestion: {suggestion.get('action', 'aucune')[:80]}",
        f"Applique: {applied} | Status: {status}",
        f"Duree: {dur}s",
    ]
    if errors:
        lines.append(f"Erreurs: {'; '.join(str(e)[:60] for e in errors[:3])}")

    return "\n".join(lines)


def format_summary_report(all_reports: list[dict[str, Any]], total_time: float) -> str:
    """Format final summary for Telegram."""
    total = len(all_reports)
    applied = sum(1 for r in all_reports if r.get("applied"))
    errors = sum(len(r.get("errors", [])) for r in all_reports)
    improvements = sum(r.get("improvements", 0) for r in all_reports)

    cats: dict[str, int] = {}
    for r in all_reports:
        cat = r.get("category", "?")
        cats[cat] = cats.get(cat, 0) + r.get("improvements", 0)

    lines = [
        "=== JARVIS IMPROVE LOOP TERMINE ===",
        f"Cycles: {total}",
        f"Ameliorations appliquees: {improvements}",
        f"Suggestions: {applied} appliquees",
        f"Erreurs: {errors}",
        f"Duree totale: {round(total_time, 1)}s",
        "",
        "Par categorie:",
    ]
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        if count > 0:
            lines.append(f"  {cat}: {count}")

    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="JARVIS Improve Loop 100 Cycles")
    parser.add_argument("--cycles", type=int, default=100, help="Number of cycles (default: 100)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without applying changes")
    parser.add_argument("--pause", type=float, default=2.0, help="Pause between cycles in seconds")
    parser.add_argument("--report-every", type=int, default=5, help="Send Telegram report every N cycles")
    args = parser.parse_args()

    total_start = time.time()
    all_reports: list[dict[str, Any]] = []

    mode = "DRY RUN" if args.dry_run else "LIVE"
    start_msg = (
        f"JARVIS Improve Loop DEMARRE\n"
        f"Mode: {mode}\n"
        f"Cycles: {args.cycles}\n"
        f"Rapport Telegram: toutes les {args.report_every} cycles"
    )
    logger.info(start_msg)
    send_telegram(start_msg)

    for i in range(1, args.cycles + 1):
        try:
            report = await run_improvement_cycle(i, args.cycles, dry_run=args.dry_run)
            all_reports.append(report)

            # Log to console
            status = "OK" if not report.get("errors") else "WARN"
            logger.info(
                f"Cycle {i}/{args.cycles} [{report['category']}] "
                f"improvements={report.get('improvements', 0)} "
                f"status={status} ({report.get('duration_s', '?')}s)"
            )

            # Send Telegram report every N cycles
            if i % args.report_every == 0 or i == args.cycles:
                batch = all_reports[-args.report_every:]
                batch_improvements = sum(r.get("improvements", 0) for r in batch)
                batch_errors = sum(len(r.get("errors", [])) for r in batch)
                telegram_msg = (
                    f"JARVIS Improve #{i}/{args.cycles}\n"
                    f"Batch: {batch_improvements} ameliorations, {batch_errors} erreurs\n"
                    f"Total: {sum(r.get('improvements', 0) for r in all_reports)} ameliorations"
                )
                send_telegram(telegram_msg)

            # Pause between cycles
            if i < args.cycles:
                await asyncio.sleep(args.pause)

        except KeyboardInterrupt:
            logger.info(f"Interrupted at cycle {i}")
            break
        except Exception as e:
            logger.error(f"Cycle {i} crashed: {e}")
            all_reports.append({"cycle": i, "errors": [str(e)], "improvements": 0})

    # Final summary
    total_time = time.time() - total_start
    summary = format_summary_report(all_reports, total_time)
    logger.info(summary)
    send_telegram(summary)

    # Save full report
    report_file = TURBO_DIR / "data" / "improve_loop_report.json"
    report_file.write_text(json.dumps(all_reports, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Full report saved: {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
