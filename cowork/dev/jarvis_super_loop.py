"""
JARVIS Super Loop — Continuous Autonomous Improvement Engine.

Full cluster (M1+M2+M3+OL1) running 1000 cycles covering:
1. TRADING: Analyse performance signaux, optimise parametres, detecte patterns gagnants
2. PERFORMANCE: Benchmark cluster nodes, identifie goulots, optimise routing
3. CODE: Genere corrections, nouvelles features, refactoring suggestions
4. REPARATION: Detecte erreurs, corrige bugs, repare services offline
5. AMELIORATION: Vision globale, anticipe besoins, suggere architecture

Usage:
  python cowork/dev/jarvis_super_loop.py --cycles 1000
  python cowork/dev/jarvis_super_loop.py --cycles 100 --focus trading
"""

import json
import os
import re
import sys
import time
import sqlite3
import subprocess
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TURBO_ROOT = Path(__file__).resolve().parent.parent.parent
SNIPER_DB = TURBO_ROOT / "data" / "sniper_scan.db"
LOOP_DB = TURBO_ROOT / "data" / "super_loop.db"
COWORK_PATH = TURBO_ROOT / "cowork" / "dev"

# Full cluster — ALL available nodes
CLUSTER = [
    {"id": "M1", "url": "http://127.0.0.1:1234/v1/chat/completions", "model": "qwen3-8b", "type": "lmstudio", "weight": 1.8},
    {"id": "M2", "url": "http://192.168.1.26:1234/v1/chat/completions", "model": "deepseek-r1-0528-qwen3-8b", "type": "lmstudio", "weight": 1.5},
    {"id": "OL1", "url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b", "type": "ollama", "weight": 1.3},
    {"id": "M3", "url": "http://192.168.1.113:1234/v1/chat/completions", "model": "deepseek-r1-0528-qwen3-8b", "type": "lmstudio", "weight": 1.2},
]

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT = "2010747443"

import urllib.request
import urllib.error


def http_post(url, data, timeout=90, headers=None):
    body = json.dumps(data).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def http_get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def send_telegram(text, chat_id=None):
    token = TELEGRAM_TOKEN
    if not token:
        env_path = TURBO_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("TELEGRAM_TOKEN="):
                    token = line.split("=", 1)[1].strip()
    if not token:
        return
    cid = chat_id or TELEGRAM_CHAT
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        try:
            http_post(f"https://api.telegram.org/bot{token}/sendMessage",
                      {"chat_id": cid, "text": chunk}, timeout=10)
        except Exception:
            try:
                http_post(f"https://api.telegram.org/bot{token}/sendMessage",
                          {"chat_id": cid, "text": chunk}, timeout=10)
            except Exception:
                pass


# ─── Database ────────────────────────────────────────────────────────────────

def init_loop_db():
    LOOP_DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(LOOP_DB))
    c.executescript("""
        CREATE TABLE IF NOT EXISTS loop_cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            cycle INTEGER,
            domain TEXT,
            task TEXT,
            cluster_responses INTEGER,
            improvements TEXT,
            actions_taken TEXT,
            duration_s REAL,
            success INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS discovered_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            domain TEXT,
            severity TEXT,
            description TEXT,
            fix_applied INTEGER DEFAULT 0,
            fix_description TEXT
        );
        CREATE TABLE IF NOT EXISTS param_evolution (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            param TEXT,
            old_val TEXT,
            new_val TEXT,
            reason TEXT,
            suggested_by TEXT
        );
        CREATE TABLE IF NOT EXISTS code_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            file_path TEXT,
            suggestion_type TEXT,
            description TEXT,
            code_snippet TEXT,
            applied INTEGER DEFAULT 0,
            consensus_score REAL
        );
    """)
    c.close()


# ─── Cluster Query ───────────────────────────────────────────────────────────

def query_node(node, prompt, timeout=90):
    """Query a single cluster node with timeout."""
    try:
        if node["type"] == "ollama":
            resp = http_post(node["url"], {
                "model": node["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "think": False
            }, timeout=timeout)
            text = resp.get("message", {}).get("content", "")
        else:
            resp = http_post(node["url"], {
                "model": node["model"],
                "messages": [{"role": "user", "content": f"/nothink\n{prompt}"}],
                "temperature": 0.3, "max_tokens": 2048, "stream": False
            }, timeout=timeout)
            choices = resp.get("choices", [])
            text = choices[0]["message"]["content"] if choices else ""
        text = re.sub(r'<think>[\s\S]*?</think>', '', text).strip()
        return {"node": node["id"], "text": text, "weight": node["weight"], "ok": True}
    except Exception as e:
        return {"node": node["id"], "text": "", "error": str(e), "weight": node["weight"], "ok": False}


def query_full_cluster(prompt, timeout=90):
    """Query all cluster nodes in parallel."""
    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(query_node, node, prompt, timeout): node for node in CLUSTER}
        for f in as_completed(futs, timeout=timeout + 10):
            try:
                results.append(f.result())
            except Exception:
                pass
    return results


def extract_json(text):
    """Extract JSON from response text."""
    try:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return None


def weighted_vote(responses, key="recommendation"):
    """Weighted vote across cluster responses."""
    votes = {}
    for r in responses:
        if not r.get("ok") or not r.get("text"):
            continue
        parsed = extract_json(r["text"])
        if parsed and key in parsed:
            val = str(parsed[key])
            votes[val] = votes.get(val, 0) + r["weight"]
    if not votes:
        return None
    return max(votes, key=votes.get)


# ─── DOMAIN 1: TRADING ──────────────────────────────────────────────────────

def cycle_trading(cycle_num):
    """Analyse et optimise le trading — signaux, parametres, performance."""
    actions = []

    # 1. Get performance data
    try:
        db = sqlite3.connect(str(SNIPER_DB))
        total = db.execute("SELECT COUNT(*) FROM signal_tracker").fetchone()[0]
        if total == 0:
            db.close()
            return {"actions": ["no_data"], "improvements": []}

        tp1 = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE tp1_hit=1").fetchone()[0]
        sl = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE sl_hit=1").fetchone()[0]
        avg_pnl = db.execute("SELECT AVG(pnl_pct) FROM signal_tracker WHERE status != 'OPEN'").fetchone()[0] or 0
        open_count = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE status='OPEN'").fetchone()[0]
        expired = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE status='EXPIRED'").fetchone()[0]

        # Recent 20 signals detail
        recent = db.execute(
            "SELECT symbol, direction, score, pnl_pct, tp1_hit, sl_hit, validations "
            "FROM signal_tracker ORDER BY id DESC LIMIT 20"
        ).fetchall()

        # Winning patterns
        winning = db.execute(
            "SELECT ss.pattern FROM scan_signals ss "
            "JOIN signal_tracker st ON ss.symbol = st.symbol "
            "WHERE st.tp1_hit=1 ORDER BY st.id DESC LIMIT 20"
        ).fetchall()
        losing = db.execute(
            "SELECT ss.pattern FROM scan_signals ss "
            "JOIN signal_tracker st ON ss.symbol = st.symbol "
            "WHERE st.sl_hit=1 ORDER BY st.id DESC LIMIT 20"
        ).fetchall()
        db.close()
    except Exception as e:
        return {"actions": [f"db_error: {e}"], "improvements": []}

    # 2. Ask cluster for trading optimization
    recent_str = "\n".join([
        f"  {r[0].replace('_USDT','')}: {r[1]} score={r[2]:.0f} pnl={r[3]:+.2f}% tp1={'Y' if r[4] else 'N'} sl={'Y' if r[5] else 'N'} valid={r[6]}"
        for r in recent[:10]
    ])
    win_patterns = ", ".join(set(p[0] for p in winning if p[0]))[:300]
    lose_patterns = ", ".join(set(p[0] for p in losing if p[0]))[:300]

    prompt = f"""Expert trading algo. Analyse les resultats du scanner JARVIS et suggere des optimisations.

STATS GLOBALES:
- {total} signaux total | {open_count} ouverts | {expired} expires
- TP1: {tp1} touches ({tp1*100//total if total else 0}%) | SL: {sl} touches ({sl*100//total if total else 0}%)
- PnL moyen: {avg_pnl:+.2f}%

DERNIERS SIGNAUX:
{recent_str}

PATTERNS GAGNANTS: {win_patterns}
PATTERNS PERDANTS: {lose_patterns}

Reponds en JSON:
{{"analysis": "resume 2 lignes",
  "trading_improvements": [
    {{"type": "param|filter|indicator|strategy", "name": "...", "current": "...", "suggested": "...", "impact": "HIGH/MED/LOW", "reason": "..."}}
  ],
  "dangerous_patterns": ["patterns a eviter"],
  "winning_formula": "combinaison gagnante detectee"
}}"""

    responses = query_full_cluster(prompt)
    valid = [r for r in responses if r.get("ok")]
    actions.append(f"cluster_queried: {len(valid)}/{len(CLUSTER)} responded")

    improvements = []
    for r in valid:
        parsed = extract_json(r["text"])
        if parsed and "trading_improvements" in parsed:
            for imp in parsed["trading_improvements"]:
                imp["node"] = r["node"]
                imp["weight"] = r["weight"]
                improvements.append(imp)

    return {"actions": actions, "improvements": improvements, "responses": len(valid)}


# ─── DOMAIN 2: PERFORMANCE ──────────────────────────────────────────────────

def cycle_performance(cycle_num):
    """Benchmark cluster performance, detect degradation."""
    actions = []
    issues = []

    # 1. Quick health check of all nodes
    t0 = time.time()
    health = {}
    for node in CLUSTER:
        t_node = time.time()
        try:
            r = query_node(node, "Reponds juste OK.", timeout=30)
            latency = time.time() - t_node
            health[node["id"]] = {
                "ok": r.get("ok", False),
                "latency": latency,
                "has_response": bool(r.get("text")),
            }
            if latency > 5:
                issues.append(f"{node['id']} slow: {latency:.1f}s")
            actions.append(f"{node['id']}: {'OK' if r.get('ok') else 'FAIL'} ({latency:.1f}s)")
        except Exception as e:
            health[node["id"]] = {"ok": False, "latency": 999, "error": str(e)}
            issues.append(f"{node['id']} offline: {e}")
            actions.append(f"{node['id']}: OFFLINE")

    total_time = time.time() - t0

    # 2. Detect degradation patterns
    offline = [nid for nid, h in health.items() if not h["ok"]]
    slow = [nid for nid, h in health.items() if h.get("latency", 0) > 5 and h["ok"]]

    if offline:
        issues.append(f"OFFLINE nodes: {', '.join(offline)}")
    if slow:
        issues.append(f"SLOW nodes: {', '.join(slow)}")

    # 3. Save issues for repair
    if issues:
        try:
            db = sqlite3.connect(str(LOOP_DB))
            for issue in issues:
                severity = "HIGH" if "OFFLINE" in issue else "MEDIUM"
                db.execute(
                    "INSERT INTO discovered_issues (domain, severity, description) VALUES (?,?,?)",
                    ("performance", severity, issue)
                )
            db.commit()
            db.close()
        except Exception:
            pass

    return {"actions": actions, "issues": issues, "health": health, "total_time": total_time}


# ─── DOMAIN 3: CODE GENERATION & IMPROVEMENT ────────────────────────────────

def cycle_code(cycle_num):
    """Ask cluster for code improvements, new features, refactoring."""
    actions = []

    # Read current sniper scanner stats for context
    try:
        line_count = sum(1 for _ in open(str(COWORK_PATH / "sniper_scanner.py"), encoding="utf-8"))
    except Exception:
        line_count = 0

    # List all cowork scripts
    scripts = sorted(COWORK_PATH.glob("*.py"))
    script_names = [s.name for s in scripts]

    prompt = f"""Expert Python. Le projet JARVIS a ces scripts dans cowork/dev/:
{', '.join(script_names)}

Le scanner principal (sniper_scanner.py) fait {line_count} lignes avec:
- 16 indicateurs techniques (BB, RSI, ADX, VWAP, EMA, Volume, Momentum, etc.)
- Mode REALTIME (30s cycle, detecte mouvements >0.4%)
- Mode SNIPER (deep analysis, 100 strategies GPU)
- Cluster consensus (6 nodes IA)
- Signal tracker (TP1/TP2/TP3/SL suivi)
- Telegram + voice alerts

Cycle d'amelioration #{cycle_num}. Suggere UNE amelioration concrete et implementable.

Reponds en JSON:
{{"improvement_type": "feature|refactor|indicator|bugfix|optimization",
  "file": "nom_fichier.py",
  "description": "description courte",
  "code_snippet": "code Python a ajouter/modifier (max 30 lignes)",
  "impact": "HIGH/MED/LOW",
  "reason": "pourquoi c'est utile"
}}"""

    responses = query_full_cluster(prompt, timeout=120)
    valid = [r for r in responses if r.get("ok")]
    actions.append(f"cluster_queried: {len(valid)} responses")

    suggestions = []
    for r in valid:
        parsed = extract_json(r["text"])
        if parsed and "code_snippet" in parsed:
            parsed["node"] = r["node"]
            parsed["weight"] = r["weight"]
            suggestions.append(parsed)

    # Save suggestions to DB
    if suggestions:
        try:
            db = sqlite3.connect(str(LOOP_DB))
            for s in suggestions:
                db.execute(
                    "INSERT INTO code_suggestions (file_path, suggestion_type, description, code_snippet, consensus_score) VALUES (?,?,?,?,?)",
                    (s.get("file", ""), s.get("improvement_type", ""), s.get("description", ""),
                     s.get("code_snippet", "")[:2000], s.get("weight", 0))
                )
            db.commit()
            db.close()
            actions.append(f"saved {len(suggestions)} code suggestions")
        except Exception as e:
            actions.append(f"db_save_error: {e}")

    return {"actions": actions, "suggestions": suggestions}


# ─── DOMAIN 4: REPAIR ───────────────────────────────────────────────────────

def cycle_repair(cycle_num):
    """Detect and fix issues — offline services, DB corruption, stale data."""
    actions = []
    fixes = []

    # 1. Check databases integrity
    for db_path in [SNIPER_DB, LOOP_DB]:
        if db_path.exists():
            try:
                db = sqlite3.connect(str(db_path))
                result = db.execute("PRAGMA integrity_check").fetchone()
                if result[0] != "ok":
                    actions.append(f"DB corruption: {db_path.name}")
                    # Attempt VACUUM
                    db.execute("VACUUM")
                    fixes.append(f"VACUUM on {db_path.name}")
                db.close()
            except Exception as e:
                actions.append(f"DB error {db_path.name}: {e}")

    # 2. Check for stale open signals (>6h old)
    try:
        db = sqlite3.connect(str(SNIPER_DB))
        stale = db.execute(
            "SELECT COUNT(*) FROM signal_tracker WHERE status='OPEN' "
            "AND emitted_at < datetime('now', '-6 hours')"
        ).fetchone()[0]
        if stale > 0:
            db.execute(
                "UPDATE signal_tracker SET status='EXPIRED' "
                "WHERE status='OPEN' AND emitted_at < datetime('now', '-6 hours')"
            )
            db.commit()
            fixes.append(f"Expired {stale} stale signals (>6h)")
            actions.append(f"stale_cleanup: {stale}")
        db.close()
    except Exception:
        pass

    # 3. Check disk space
    try:
        import shutil
        for drive in ["/\", "F:/"]:
            usage = shutil.disk_usage(drive)
            free_gb = usage.free / (1024**3)
            if free_gb < 10:
                actions.append(f"LOW DISK: {drive} only {free_gb:.1f} GB free")
                # Save as discovered issue
                db = sqlite3.connect(str(LOOP_DB))
                db.execute(
                    "INSERT INTO discovered_issues (domain, severity, description) VALUES (?,?,?)",
                    ("repair", "HIGH", f"Low disk space on {drive}: {free_gb:.1f} GB free")
                )
                db.commit()
                db.close()
    except Exception:
        pass

    # 4. Check scanner process
    try:
        result = subprocess.run(
            ["tasklist"], capture_output=True, text=True, timeout=5
        )
        if "sniper_scanner" not in result.stdout.lower():
            # Scanner might not show with full name, check python processes
            python_count = result.stdout.lower().count("python")
            actions.append(f"python_processes: {python_count}")
    except Exception:
        pass

    # 5. Check unfixed issues from previous cycles
    try:
        db = sqlite3.connect(str(LOOP_DB))
        unfixed = db.execute(
            "SELECT COUNT(*) FROM discovered_issues WHERE fix_applied=0"
        ).fetchone()[0]
        if unfixed > 0:
            actions.append(f"unfixed_issues: {unfixed}")
        db.close()
    except Exception:
        pass

    return {"actions": actions, "fixes": fixes}


# ─── DOMAIN 5: STRATEGIC IMPROVEMENT ────────────────────────────────────────

def cycle_strategic(cycle_num):
    """Big picture — architecture, anticipation, vision."""
    actions = []

    # Only run every 10 cycles (expensive + strategic)
    if cycle_num % 10 != 0:
        return {"actions": ["skipped (every 10 cycles)"], "suggestions": []}

    # Gather system overview
    try:
        db = sqlite3.connect(str(SNIPER_DB))
        total_signals = db.execute("SELECT COUNT(*) FROM signal_tracker").fetchone()[0]
        total_scans = db.execute("SELECT COUNT(*) FROM scan_runs").fetchone()[0]
        total_coins = db.execute("SELECT COUNT(*) FROM coin_registry").fetchone()[0]
        db.close()
    except Exception:
        total_signals = total_scans = total_coins = 0

    try:
        db = sqlite3.connect(str(LOOP_DB))
        total_cycles = db.execute("SELECT COUNT(*) FROM loop_cycles").fetchone()[0]
        total_issues = db.execute("SELECT COUNT(*) FROM discovered_issues WHERE fix_applied=0").fetchone()[0]
        total_suggestions = db.execute("SELECT COUNT(*) FROM code_suggestions WHERE applied=0").fetchone()[0]
        db.close()
    except Exception:
        total_cycles = total_issues = total_suggestions = 0

    prompt = f"""Tu es l'architecte IA principal de JARVIS, un systeme de trading autonome.

ETAT ACTUEL:
- {total_signals} signaux emis | {total_scans} scans effectues | {total_coins} coins suivis
- {total_cycles} cycles d'amelioration | {total_issues} problemes non resolus | {total_suggestions} suggestions code en attente
- Cluster: 4 noeuds IA (M1 qwen3-8b CHAMPION, M2 deepseek-r1, OL1 qwen3:1.7b, M3 deepseek-r1)
- Mode REALTIME actif (30s cycles) + SNIPER mode (deep analysis)
- 16 indicateurs techniques + VWAP + Momentum streak + GPU 100 strategies

CYCLE STRATEGIQUE #{cycle_num}. Quelle est LA priorite #1 pour ameliorer le systeme?

Reponds en JSON:
{{"priority": "description courte",
  "domain": "trading|performance|code|architecture|data",
  "action_plan": ["etape 1", "etape 2", "etape 3"],
  "expected_impact": "description de l'impact attendu",
  "risk": "LOW/MED/HIGH"
}}"""

    # Only use top 3 nodes for strategic (expensive)
    top_nodes = [n for n in CLUSTER if n["weight"] >= 1.5]
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = {pool.submit(query_node, node, prompt, 120): node for node in top_nodes}
        for f in as_completed(futs, timeout=130):
            try:
                results.append(f.result())
            except Exception:
                pass

    valid = [r for r in results if r.get("ok")]
    actions.append(f"strategic_cluster: {len(valid)} responses")

    suggestions = []
    for r in valid:
        parsed = extract_json(r["text"])
        if parsed:
            parsed["node"] = r["node"]
            suggestions.append(parsed)

    return {"actions": actions, "suggestions": suggestions}


# ─── MAIN LOOP ───────────────────────────────────────────────────────────────

DOMAINS = [
    ("trading", cycle_trading),
    ("performance", cycle_performance),
    ("code", cycle_code),
    ("repair", cycle_repair),
    ("strategic", cycle_strategic),
]


def run_cycle(cycle_num, focus=None):
    """Run one complete cycle across all domains."""
    t0 = time.time()
    results = {}

    # Rotate through domains (or focus on one)
    if focus:
        domains = [(d, f) for d, f in DOMAINS if d == focus]
    else:
        # Round-robin: each cycle does trading + one other domain
        other_idx = (cycle_num - 1) % (len(DOMAINS) - 1) + 1
        domains = [DOMAINS[0], DOMAINS[other_idx]]  # Always trading + rotate others

    for domain_name, domain_fn in domains:
        try:
            log(f"  [{domain_name.upper()}]")
            result = domain_fn(cycle_num)
            results[domain_name] = result

            # Log actions
            for action in result.get("actions", [])[:3]:
                log(f"    {action}")
            for fix in result.get("fixes", [])[:3]:
                log(f"    FIX: {fix}")
            for imp in result.get("improvements", [])[:2]:
                if isinstance(imp, dict):
                    log(f"    IMPROVE: {imp.get('name', '')} — {imp.get('reason', '')[:60]}")
        except Exception as e:
            log(f"    ERROR: {e}")
            results[domain_name] = {"error": str(e)}

    duration = time.time() - t0

    # Save cycle to DB
    try:
        db = sqlite3.connect(str(LOOP_DB))
        for domain_name, result in results.items():
            db.execute(
                "INSERT INTO loop_cycles (cycle, domain, task, cluster_responses, improvements, actions_taken, duration_s, success) VALUES (?,?,?,?,?,?,?,?)",
                (cycle_num, domain_name, "auto",
                 result.get("responses", len(result.get("actions", []))),
                 json.dumps(result.get("improvements", result.get("suggestions", [])), default=str)[:2000],
                 json.dumps(result.get("actions", []))[:1000],
                 duration,
                 0 if "error" in result else 1)
            )
        db.commit()
        db.close()
    except Exception:
        pass

    return results, duration


def main():
    import argparse
    parser = argparse.ArgumentParser(description="JARVIS Super Improvement Loop")
    parser.add_argument("--cycles", type=int, default=1000, help="Number of cycles")
    parser.add_argument("--interval", type=int, default=120, help="Seconds between cycles")
    parser.add_argument("--focus", type=str, choices=["trading", "performance", "code", "repair", "strategic"],
                        help="Focus on one domain only")
    parser.add_argument("--notify", action="store_true", help="Send reports to Telegram")
    args = parser.parse_args()

    init_loop_db()
    log(f"JARVIS SUPER LOOP — {args.cycles} cycles, interval {args.interval}s")
    log(f"  Cluster: {', '.join(n['id'] for n in CLUSTER)} ({len(CLUSTER)} nodes)")
    log(f"  Domains: {', '.join(d for d, _ in DOMAINS)}")
    if args.focus:
        log(f"  Focus: {args.focus}")

    total_improvements = 0
    total_fixes = 0
    total_errors = 0

    for cycle in range(1, args.cycles + 1):
        t_cycle = time.time()
        log(f"=== SUPER LOOP CYCLE {cycle}/{args.cycles} ===")

        try:
            results, duration = run_cycle(cycle, focus=args.focus)

            # Count improvements and fixes
            for domain, result in results.items():
                if isinstance(result, dict):
                    total_improvements += len(result.get("improvements", result.get("suggestions", [])))
                    total_fixes += len(result.get("fixes", []))
                    if "error" in result:
                        total_errors += 1

            log(f"  Cycle {cycle} done in {duration:.1f}s")

        except Exception as e:
            log(f"  CYCLE ERROR: {e}")
            total_errors += 1

        # Progress report every 25 cycles
        if cycle % 25 == 0:
            report = (
                f"SUPER LOOP PROGRESS: {cycle}/{args.cycles}\n"
                f"Improvements: {total_improvements} | Fixes: {total_fixes} | Errors: {total_errors}\n"
                f"Uptime: {(time.time() - t_cycle):.0f}s per cycle"
            )
            log(report)
            if args.notify:
                send_telegram(report)

        # Telegram report every 100 cycles
        if cycle % 100 == 0 and args.notify:
            try:
                db = sqlite3.connect(str(LOOP_DB))
                suggestions_count = db.execute("SELECT COUNT(*) FROM code_suggestions").fetchone()[0]
                issues_count = db.execute("SELECT COUNT(*) FROM discovered_issues").fetchone()[0]
                db.close()
                report = (
                    f"JARVIS SUPER LOOP — RAPPORT #{cycle}\n"
                    f"Cycles: {cycle}/{args.cycles}\n"
                    f"Improvements: {total_improvements}\n"
                    f"Fixes: {total_fixes}\n"
                    f"Code suggestions: {suggestions_count}\n"
                    f"Issues detected: {issues_count}\n"
                    f"Errors: {total_errors}"
                )
                send_telegram(report)
            except Exception:
                pass

        # Wait between cycles
        if cycle < args.cycles:
            time.sleep(args.interval)

    log(f"SUPER LOOP COMPLETE — {args.cycles} cycles | {total_improvements} improvements | {total_fixes} fixes")


if __name__ == "__main__":
    main()
