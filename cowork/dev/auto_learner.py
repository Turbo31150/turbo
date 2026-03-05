#!/usr/bin/env python3
"""JARVIS Auto Learner — Analyse les logs d'erreurs et propose des corrections."""
import json, sys, os, re
from datetime import datetime, timedelta
from collections import Counter

TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT = "2010747443"

LOG_SOURCES = [
    {"name": "OpenClaw", "path": os.path.expandvars(r"%USERPROFILE%\.openclaw\agents\main\logs"), "pattern": "*.log"},
    {"name": "Monitor", "path": "C:/Users/franc/.openclaw/workspace/dev/monitor_log.json", "type": "jsonl"},
    {"name": "Optimizer", "path": "C:/Users/franc/.openclaw/workspace/dev/optimizer_log.json", "type": "jsonl"},
]

ERROR_PATTERNS = [
    (r"timeout|timed out", "TIMEOUT", "Verifier connectivite reseau ou augmenter timeout"),
    (r"connection refused|ECONNREFUSED", "CONN_REFUSED", "Service non demarre — verifier le port"),
    (r"out of memory|OOM|MemoryError", "OOM", "Memoire insuffisante — liberer RAM ou reduire batch"),
    (r"CUDA|GPU|cuda", "GPU_ERROR", "Probleme GPU — verifier drivers NVIDIA ou VRAM"),
    (r"permission denied|access denied", "PERM_ERROR", "Permissions insuffisantes — verifier droits"),
    (r"404|not found", "NOT_FOUND", "Ressource introuvable — verifier URL/chemin"),
    (r"500|internal server error", "SERVER_ERROR", "Erreur serveur interne — verifier logs du service"),
    (r"rate limit|429|too many requests", "RATE_LIMIT", "Limite de requetes — implementer backoff"),
    (r"FailoverError", "FAILOVER", "Cascade de fallback — verifier agents primaires"),
    (r"ctx=\d+ < min", "CTX_TOO_SMALL", "Contexte modele insuffisant — utiliser un modele plus grand"),
]

def send_telegram(msg):
    import urllib.request
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=10)
    except: pass

def scan_log_file(path, max_lines=500):
    errors = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-max_lines:]
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(kw in line_lower for kw in ["error", "fail", "exception", "critical", "traceback"]):
                # Classify
                category = "UNKNOWN"
                suggestion = "Verifier manuellement"
                for pattern, cat, sug in ERROR_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        category = cat
                        suggestion = sug
                        break
                errors.append({
                    "line": len(lines) - len(lines) + i + 1,
                    "text": line.strip()[:200],
                    "category": category,
                    "suggestion": suggestion,
                })
    except Exception as e:
        errors.append({"text": f"Cannot read {path}: {e}", "category": "READ_ERROR", "suggestion": "Verifier le chemin"})
    return errors

def scan_jsonl(path):
    errors = []
    try:
        with open(path, "r") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    for key, val in data.items():
                        if isinstance(val, dict) and val.get("status") == "offline":
                            errors.append({
                                "text": f"{key} offline: {val.get('error', '?')[:100]}",
                                "category": "NODE_DOWN",
                                "suggestion": f"Redemarrer {key} ou verifier connectivite",
                            })
                except json.JSONDecodeError:
                    pass
    except: pass
    return errors

def scan_all_sources():
    all_errors = {}
    for src in LOG_SOURCES:
        path = src["path"]
        if src.get("type") == "jsonl":
            if os.path.isfile(path):
                all_errors[src["name"]] = scan_jsonl(path)
        elif os.path.isdir(path):
            for f in sorted(os.listdir(path))[-3:]:  # Last 3 log files
                fp = os.path.join(path, f)
                if os.path.isfile(fp):
                    errs = scan_log_file(fp)
                    if errs:
                        all_errors[f"{src['name']}/{f}"] = errs
        elif os.path.isfile(path):
            all_errors[src["name"]] = scan_log_file(path)
    return all_errors

def generate_report(all_errors):
    total = sum(len(v) for v in all_errors.values())
    if total == 0:
        return "Aucune erreur detectee dans les logs recents.", {}

    # Count categories
    cats = Counter()
    for errs in all_errors.values():
        for e in errs:
            cats[e["category"]] += 1

    lines = [f"[JARVIS LEARNER] {datetime.now().strftime('%H:%M')} — {total} erreurs"]
    for cat, count in cats.most_common(5):
        # Find first suggestion for this category
        sug = next((e["suggestion"] for errs in all_errors.values() for e in errs if e["category"] == cat), "?")
        lines.append(f"  {cat}: {count}x → {sug}")

    return "\n".join(lines), cats

if __name__ == "__main__":
    if "--once" in sys.argv:
        all_errors = scan_all_sources()
        report, cats = generate_report(all_errors)
        print(report)
        if "--notify" in sys.argv and cats:
            send_telegram(report)
    elif "--detail" in sys.argv:
        all_errors = scan_all_sources()
        for source, errs in all_errors.items():
            print(f"\n--- {source} ({len(errs)} errors) ---")
            for e in errs[-5:]:
                print(f"  [{e['category']}] {e['text'][:120]}")
                print(f"    → {e['suggestion']}")
    else:
        print("Usage: auto_learner.py --once [--notify] | --detail")
