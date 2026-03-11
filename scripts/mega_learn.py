#!/usr/bin/env python3
"""MEGA LEARNING PIPELINE v7 — CONTINUOUS POOL (no batch blocking).

8 workers continuously fed. Fast tasks (OL1=0.5s, M1=2s) cycle rapidly
while slow tasks (M2=30s, M3=30s) run in background without blocking.
Expected: 40-80 dispatches/min.
"""
import urllib.request, json, time, random, string, sqlite3, subprocess, os, sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

WS = 'http://127.0.0.1:9742'
IMPROVE = f'{WS}/api/self-improve/run'
DISPATCH = f'{WS}/api/dispatch_engine/dispatch'
DB_PATH = 'F:/BUREAU/turbo/data/etoile.db'

TG_TOKEN = '8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw'
TG_CHAT = '2010747443'

WORDS = 'alpha beta gamma delta omega flux node cache proxy route hash queue stack tree graph sort merge split parse build redis kafka docker vue react flask django numpy tensor cuda vram gpu cluster agent pipeline socket thread async await coroutine iterator decorator generator cryptography blockchain validator staking liquidity arbitrage momentum fibonacci macd rsi bollinger scalping portfolio optimization backtest neural network transformer attention embedding tokenizer gradient epoch inference latency throughput microservice kubernetes helm terraform ansible prometheus grafana'.split()

TOPICS = [
    "Ecris une fonction Python pour {w1}", "Calcule {n1} * {n2}",
    "Explique {w1} en contexte {w2}", "Debug: {w1} erreur dans {w2}",
    "Architecture: {w1} avec {w2}", "Optimise {w1} pour {w2}",
    "Analyse impact de {w1}", "Trading signal {w1}",
    "CI/CD pour {w1}", "Securite {w1} contre {w2}",
    "Refactoring {w1}", "Test unitaire {w1}",
    "Compare {w1} vs {w2}", "Resume avantages de {w1}",
    "Decorator Python {w1}", "Deploy {w1} K8s",
]

_db_lock = threading.Lock()
_stats_lock = threading.Lock()
_ol1_sem = threading.Semaphore(3)  # OLLAMA_NUM_PARALLEL=3
_m1_sem = threading.Semaphore(5)   # M1 parallel=11, boost throughput

def uid():
    return ''.join(random.choices(string.ascii_lowercase, k=4))

def flush(*a):
    print(*a, flush=True)

def prompt():
    w1, w2 = random.choice(WORDS), random.choice(WORDS)
    n1, n2 = random.randint(10, 999), random.randint(10, 999)
    return random.choice(TOPICS).format(w1=w1, w2=w2, n1=n1, n2=n2)

def send_tg(text):
    try:
        p = json.dumps({"chat_id": TG_CHAT, "text": text, "parse_mode": "Markdown"}).encode()
        urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data=p, headers={"Content-Type": "application/json"}), timeout=10)
    except Exception:
        pass

def log_fb(node, pattern, ok, ms, quality=0.0, preview=''):
    try:
        with _db_lock:
            db = sqlite3.connect(DB_PATH, timeout=5)
            db.execute("""INSERT INTO agent_feedback
                (node, pattern, success, latency_ms, auto_quality, prompt_preview, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
                (node, pattern, 1 if ok else 0, int(ms), quality, preview[:200]))
            db.commit()
            db.close()
    except Exception:
        pass

# ── HTTP CALLERS ─────────────────────────────────────────────

def _http(url, data, timeout=15):
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"_error": str(e)[:80]}

def _lms(d):
    tps = d.get('stats', {}).get('tokens_per_second', 0)
    for o in reversed(d.get('output', [])):
        if o.get('type') == 'message':
            c = o.get('content', '')
            if isinstance(c, str) and c.strip():
                return True, c.strip()[:200], tps
            if isinstance(c, list):
                for i in c:
                    if isinstance(i, dict) and i.get('type') == 'output_text':
                        return True, i['text'][:200], tps
    return False, d.get('_error', 'no output')[:80], 0

def call_ol1(p, to=10):
    with _ol1_sem:
        d = _http("http://127.0.0.1:11434/api/chat",
            {"model": "qwen3:1.7b", "messages": [{"role": "user", "content": p}],
             "stream": False, "think": False}, to)
        if '_error' in d: return False, d['_error'], 0
        return True, d.get('message', {}).get('content', '')[:200], 0

def call_m1(p, to=20):
    with _m1_sem:
        d = _http("http://127.0.0.1:1234/api/v1/chat",
            {"model": "qwen3-8b", "input": f"/nothink\n{p}",
             "temperature": 0.3, "max_output_tokens": 64, "stream": False, "store": False}, to)
        if '_error' in d: return False, d['_error'], 0
        return _lms(d)

def call_m2(p, to=45):
    d = _http("http://192.168.1.26:1234/api/v1/chat",
        {"model": "deepseek-r1-0528-qwen3-8b", "input": p,
         "temperature": 0.3, "max_output_tokens": 512, "stream": False, "store": False}, to)
    if '_error' in d: return False, d['_error'], 0
    return _lms(d)

def call_m3(p, to=45):
    d = _http("http://192.168.1.113:1234/api/v1/chat",
        {"model": "deepseek-r1-0528-qwen3-8b", "input": p,
         "temperature": 0.3, "max_output_tokens": 512, "stream": False, "store": False}, to)
    if '_error' in d: return False, d['_error'], 0
    return _lms(d)

def call_ws(pat, p, to=15):
    d = _http(DISPATCH, {"pattern": pat, "prompt": p}, to)
    if '_error' in d: return False, d['_error'], 0
    return d.get('success', False), f'{d.get("node","?")} q={d.get("quality",0):.2f}', d.get('latency_ms', 0)

def call_cowork(p, to=15):
    d = _http(f'{WS}/api/chat/send', {"content": p, "mode": "cowork"}, to)
    if '_error' in d: return False, d['_error'], 0
    msg = d.get('agent_message', {}).get('content', '') or str(d.get('response', ''))
    return bool(msg), msg[:200], 0

OC_ENV = {**os.environ, "OPENCLAW_GATEWAY_PORT": "18789",
    "OPENCLAW_GATEWAY_TOKEN": "ae1cd158a0975c30e7712b274859e202896e7f67203de9d2"}
OC_CWD = "C:\\Users\\franc\\.openclaw"
OC_AGENTS = ["coding","fast-chat","deep-work","trading","m1-deep","ol1-fast",
    "recherche-synthese","debug-detective","creative-brainstorm","data-analyst"]
_oc_sem = threading.Semaphore(2)
_gem_sem = threading.Semaphore(1)   # Gemini: 1 at a time (90s calls)
_claude_sem = threading.Semaphore(1) # Claude: 1 at a time (15-20s calls)

def _kill_tree(pid):
    """Kill process tree on Windows (taskkill /F /T)."""
    try:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)],
            capture_output=True, timeout=5)
    except Exception:
        pass

def _safe_subprocess(cmd, timeout=25, **kw):
    """Subprocess with hard kill on timeout — never hangs."""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace', **kw)
        timer = threading.Timer(timeout, lambda: _kill_tree(proc.pid))
        timer.start()
        try:
            out, err = proc.communicate(timeout=timeout + 3)
        except subprocess.TimeoutExpired:
            _kill_tree(proc.pid)
            try: out, err = proc.communicate(timeout=3)
            except Exception: out, err = '', 'timeout'
        finally:
            timer.cancel()
        return out or '', err or ''
    except Exception as e:
        try: _kill_tree(proc.pid)
        except Exception: pass
        return '', str(e)[:80]

def call_openclaw(p, to=30):
    agent = random.choice(OC_AGENTS)
    with _oc_sem:
        out, err = _safe_subprocess(
            ["openclaw", "agent", "--agent", agent, "--message", p,
             "--json", "--timeout", "20", "--session-id", f"l-{uid()}"],
            timeout=to, cwd=OC_CWD, env=OC_ENV)
        if out.strip():
            try:
                d = json.loads(out)
                payloads = d.get('result', {}).get('payloads', [])
                text = ' '.join(x.get('text', '') for x in payloads)[:200]
                if text and 'aborted' not in text.lower():
                    return True, f"[OC/{agent}] {text}", 0
            except Exception:
                pass
            if 'aborted' not in out.lower():
                return True, out[:200], 0
        return False, (err or 'empty')[:80], 0

def call_gemini(p, to=120):
    with _gem_sem:
        out, err = _safe_subprocess(
            ["node", "F:/BUREAU/turbo/gemini-proxy.js", "--json", p], timeout=to)
        if out.strip():
            try:
                d = json.loads(out)
                text = str(d.get('text', d.get('response', '')))[:200]
                if text: return True, f"[GEMINI] {text}", 0
            except Exception:
                return True, out[:200], 0
        return False, (err or 'empty')[:80], 0

def call_claude_proxy(p, to=40):
    with _claude_sem:
        out, err = _safe_subprocess(
            ["node", "F:/BUREAU/turbo/claude-proxy.js", "--json", p], timeout=to)
        if out.strip():
            try:
                d = json.loads(out)
                text = str(d.get('text', d.get('response', '')))[:200]
                if text: return True, f"[CLAUDE] {text}", 0
            except Exception:
                return True, out[:200], 0
        return False, (err or 'empty')[:80], 0

def self_improve():
    try:
        req = urllib.request.Request(IMPROVE, method='POST', data=b'{}',
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read())
            act = res.get('actions_taken', 0)
            if res.get('status') == 'skipped_no_new_data': return 0, 'skip'
            if act > 0:
                parts = [f'{a["type"]}:{a["target"]}' for a in res.get('actions', [])]
                return act, f'{act}a({"|".join(parts[:3])})'
            return 0, 'ok'
    except Exception:
        return 0, 'err'

# ── TASK GENERATOR ───────────────────────────────────────────
# Weighted random: fast tasks more frequent than slow ones

TASK_POOL = [
    # (weight, node, pattern, caller_fn, timeout)
    # Fast (OL1 0.5-5s, M1 1-8s) — HIGH weight for throughput
    (5, "OL1",    "fast",   call_ol1,          25),
    (4, "M1",     "code",   call_m1,           30),
    (4, "M1",     "math",   call_m1,           30),
    # Medium (WS 5-15s, Cowork 5-15s)
    # WS disabled — server unresponsive under load
    # (3, "WS",     "code",   lambda p,to=15: call_ws("code", p, to), 15),
    # (3, "WS",     "math",   lambda p,to=15: call_ws("math", p, to), 15),
    # (2, "WS",     "simple", lambda p,to=15: call_ws("simple", p, to), 15),
    # COWORK disabled — WS server (9742) is down
    # (2, "COWORK", "task",   call_cowork, 15),
    # OpenClaw agents (10-30s, sem=2)
    (1, "OC",     "agent",  call_openclaw,     30),
    # Cloud proxies — LOW weight to avoid semaphore queueing
    (1, "GEMINI", "archi",  call_gemini,       120),
    (1, "CLAUDE", "reason", call_claude_proxy,  60),
    # Slow reasoning (15-45s)
    (1, "M2",     "reason", call_m2,           45),
    (1, "M3",     "reason", call_m3,           45),
]

_weights = [t[0] for t in TASK_POOL]

def next_task():
    """Pick a random task weighted towards fast ones."""
    w, node, pat, fn, to = random.choices(TASK_POOL, weights=_weights, k=1)[0]
    p = prompt()
    return node, pat, fn, to, p

# ── EXECUTE ──────────────────────────────────────────────────

def execute(args):
    node, pat, fn, to, p = args
    t0 = time.time()
    try:
        ok, text, extra = fn(p, to)
    except Exception as e:
        ok, text, extra = False, str(e)[:30], 0
    ms = (time.time() - t0) * 1000
    q = 0.8 if ok else 0.0
    if ok and extra > 0:
        q = min(1.0, 0.7 + extra / 200)
    log_fb(node, pat, ok, ms, q, f"{node}/{pat}: {p[:40]}")
    return node, pat, ok, ms

# ── MAIN — CONTINUOUS POOL ───────────────────────────────────

start = time.time()
total_ok = 0
total_fail = 0
total_learn = 0
node_stats = {}
last_print = 0
last_tg = 0
last_improve = 0

flush("=" * 72)
flush("  MEGA LEARNING v7 — CONTINUOUS POOL | 8 workers | ALL CHANNELS")
flush("  OL1+M1+M2+M3+WS+Cowork+OpenClaw+Gemini+Claude")
flush("  Weighted: fast(OL1/M1) > medium(WS/OC/Gemini/Claude) > slow(M2/M3)")
flush("=" * 72)
flush()

send_tg("🚀 *MEGA LEARN v7 STARTED*\n8 workers | Continuous pool\nOL1+M1+M2+M3+WS+Cowork+OC+Gemini+Claude\nTarget: 10k dispatches")

# ── PARASITE CLEANER (lfm/llama keep auto-loading on M1) ─────
PARASITES = ["lfm2.5-1.2b-instruct", "llama-3.2-1b-instruct"]

def clean_parasites():
    """Unload parasite models from M1 every 30s."""
    while True:
        time.sleep(30)
        for p in PARASITES:
            try:
                _http("http://127.0.0.1:1234/api/v1/models/unload",
                    {"instance_id": p}, timeout=3)
            except Exception:
                pass

cleaner = threading.Thread(target=clean_parasites, daemon=True)
cleaner.start()

executor = ThreadPoolExecutor(max_workers=10)
futures = set()

# Pre-fill the pool
for _ in range(12):
    futures.add(executor.submit(execute, next_task()))

while total_ok + total_fail < 10000:
    # Wait for ANY task to complete
    done = set()
    for f in futures:
        if f.done():
            done.add(f)

    if not done:
        time.sleep(0.1)
        continue

    for f in done:
        futures.discard(f)
        try:
            node, pat, ok, ms = f.result()
        except Exception:
            node, pat, ok, ms = "ERR", "?", False, 0

        with _stats_lock:
            if node not in node_stats:
                node_stats[node] = {'ok': 0, 'fail': 0, 'ms': 0, 'count': 0}
            node_stats[node]['count'] += 1
            node_stats[node]['ms'] += ms
            if ok:
                total_ok += 1
                node_stats[node]['ok'] += 1
            else:
                total_fail += 1
                node_stats[node]['fail'] += 1

        # Immediately submit new task (keep pool full)
        futures.add(executor.submit(execute, next_task()))

    total = total_ok + total_fail
    elapsed = time.time() - start
    rate = total / max(elapsed, 1) * 60

    # Self-improve every 30s
    if time.time() - last_improve > 30:
        last_improve = time.time()
        act, lm = self_improve()
        total_learn += act
        if act > 0:
            flush(f'  LEARN: {lm}')

    # Print every 10s or every 50 tasks
    if time.time() - last_print > 10 or total % 50 == 0:
        last_print = time.time()
        ok_pct = total_ok * 100 // max(total, 1)
        flush(f'  {total:5d}/10k | {total_ok}OK ({ok_pct}%) | {rate:.0f}/min | {elapsed:.0f}s')

    # Telegram every 120s
    if time.time() - last_tg > 120:
        last_tg = time.time()
        lines = []
        for n, s in sorted(node_stats.items(), key=lambda x: x[1]['ok'], reverse=True):
            avg = s['ms'] / max(s['count'], 1)
            sr = s['ok'] * 100 // max(s['count'], 1)
            lines.append(f'{n:8s}: {s["ok"]:4d}OK/{s["count"]:4d} ({sr:3d}%) {avg:.0f}ms')
        tg = f"📊 *v7 — {total}/10k*\n{rate:.0f}/min | {total_ok}OK ({total_ok*100//max(total,1)}%)\n"
        tg += "```\n" + "\n".join(lines[:8]) + "\n```"
        send_tg(tg)

    # DB backup every 2000 tasks
    if total % 2000 == 0 and total > 0:
        try:
            import shutil
            shutil.copy2(DB_PATH, f'{DB_PATH}.bak_{total}')
            flush(f'  DB backup at {total}')
        except Exception:
            pass

# Cleanup
executor.shutdown(wait=True)
elapsed = time.time() - start

flush(f'\n{"=" * 72}')
flush(f'  DONE: {total_ok} OK / {total_fail} FAIL | {total_learn} learn | {elapsed:.0f}s')
flush(f'{"=" * 72}')

flush('\n  FINAL:')
lines = []
for n, s in sorted(node_stats.items(), key=lambda x: x[1]['ok'], reverse=True):
    avg = s['ms'] / max(s['count'], 1)
    sr = s['ok'] * 100 // max(s['count'], 1)
    line = f'{n:8s}: {s["ok"]:5d}OK/{s["count"]:5d} ({sr:3d}%) avg={avg:.0f}ms'
    flush(f'  {line}')
    lines.append(line)

tg = f"✅ *v7 DONE*\n{total_ok}OK / {total_fail}FAIL | {elapsed:.0f}s | {total_learn} learn\n"
tg += "```\n" + "\n".join(lines) + "\n```"
send_tg(tg)
