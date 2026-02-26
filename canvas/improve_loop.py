#!/usr/bin/env python3
"""
JARVIS Agent Improvement Loop v1.0
100 cycles: test → evaluate → tune → repeat
Each cycle tests multiple categories, scores responses, and tunes params.
"""

import json, time, sys, os, random, re
from datetime import datetime
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

try:
    import httpx
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'httpx', '-q'])
    import httpx

PROXY = "http://127.0.0.1:18800/chat"
TIMEOUT = 90
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
LOG_FILE = DATA_DIR / "improve_log.jsonl"
SCORES_FILE = DATA_DIR / "improve_scores.json"

# ── Test Suite: 40 questions across 8 categories ──────────────────────────────
TEST_SUITE = [
    # CODE (5 tests)
    {"cat": "code", "agent": "coder", "q": "Ecris une fonction Python qui verifie si une chaine est un palindrome", "check": ["def ", "palindrome", "return"], "fmt": ["```"]},
    {"cat": "code", "agent": "coder", "q": "Ecris un decorateur Python qui mesure le temps d'execution d'une fonction", "check": ["def ", "time", "wrapper", "return"], "fmt": ["```"]},
    {"cat": "code", "agent": "coder", "q": "Implemente un tri par fusion (merge sort) en Python", "check": ["def ", "merge", "sort", "return"], "fmt": ["```"]},
    {"cat": "code", "agent": "coder", "q": "Ecris une classe Python pour une file d'attente (queue) avec enqueue et dequeue", "check": ["class", "enqueue", "dequeue"], "fmt": ["```"]},
    {"cat": "code", "agent": "coder", "q": "Ecris une fonction qui trouve les doublons dans une liste", "check": ["def ", "return"], "fmt": ["```"]},

    # MATH (5 tests)
    {"cat": "math", "agent": "math-solver", "q": "Calcule 23 * 17 + 89 - 45. Montre chaque etape.", "check": ["391", "480", "435"], "expect": "435", "fmt": ["etape", "resultat"]},
    {"cat": "math", "agent": "math-solver", "q": "Quelle est la somme des 10 premiers nombres: 1+2+3+...+10?", "check": ["55"], "expect": "55", "fmt": ["etape"]},
    {"cat": "math", "agent": "math-solver", "q": "Si un train roule a 120 km/h pendant 2h30, quelle distance parcourt-il?", "check": ["300"], "expect": "300", "fmt": ["etape", "resultat"]},
    {"cat": "math", "agent": "math-solver", "q": "Calcule la factorielle de 7 (7!)", "check": ["5040"], "expect": "5040", "fmt": ["etape"]},
    {"cat": "math", "agent": "math-solver", "q": "Resous: 2x + 5 = 17. Quelle est la valeur de x?", "check": ["6"], "expect": "6", "fmt": ["etape"]},

    # RAISON (5 tests)
    {"cat": "raison", "agent": "raisonnement", "q": "Si tous les chats sont des animaux et certains animaux sont noirs, peut-on conclure que certains chats sont noirs?", "check": ["non", "ne peut pas"], "expect_neg": True, "fmt": ["premisse", "conclusion"]},
    {"cat": "raison", "agent": "raisonnement", "q": "Pierre est plus grand que Paul. Paul est plus grand que Jacques. Qui est le plus grand?", "check": ["pierre"], "expect": "pierre", "fmt": ["etape"]},
    {"cat": "raison", "agent": "raisonnement", "q": "Si il pleut, la route est mouillee. La route est mouillee. Pleut-il?", "check": ["pas", "ne peut", "affirm"], "expect_neg": True, "fmt": ["conclusion"]},
    {"cat": "raison", "agent": "raisonnement", "q": "Tous les rectangles sont des parallelogrammes. Tous les carres sont des rectangles. Les carres sont-ils des parallelogrammes?", "check": ["oui"], "expect": "oui", "fmt": ["etape", "conclusion"]},
    {"cat": "raison", "agent": "raisonnement", "q": "Un fermier a 17 moutons. Tous sauf 9 meurent. Combien en reste-t-il?", "check": ["9"], "expect": "9", "fmt": ["etape"]},

    # ARCHI (3 tests)
    {"cat": "archi", "agent": "main", "q": "Compare REST vs GraphQL pour une API de chat en temps reel. Quelle approche recommandes-tu?", "check": ["rest", "graphql"], "fmt": ["avantage", "recommand"]},
    {"cat": "archi", "agent": "main", "q": "Propose une architecture pour un systeme de cache distribue", "check": ["cache", "redis|memcach"], "fmt": ["composant"]},
    {"cat": "archi", "agent": "main", "q": "Microservices vs monolithe pour une startup de 5 devs?", "check": ["monolith", "micro"], "fmt": ["recommand"]},

    # SYSTEM (3 tests)
    {"cat": "system", "agent": "main", "q": "Comment lister tous les processus qui utilisent plus de 1GB de RAM en PowerShell?", "check": ["process", "memory", "get-process|powershell"], "fmt": ["```", "powershell|ps1"]},
    {"cat": "system", "agent": "main", "q": "Comment creer une tache planifiee Windows qui execute un script Python toutes les heures?", "check": ["schtasks|task scheduler|planif"], "fmt": ["commande|command"]},
    {"cat": "system", "agent": "main", "q": "Comment voir l'utilisation GPU sous Windows avec nvidia-smi?", "check": ["nvidia-smi"], "fmt": ["```"]},

    # TRADING (3 tests)
    {"cat": "trading", "agent": "trading-analyst", "q": "Quels indicateurs techniques sont les plus fiables pour le scalping crypto 5min?", "check": ["rsi|macd|volume|ema|bollinger"], "fmt": ["indicateur"]},
    {"cat": "trading", "agent": "trading-analyst", "q": "Explique la strategie de breakout avec confirmation de volume", "check": ["breakout", "volume"], "fmt": ["etape|strateg"]},
    {"cat": "trading", "agent": "trading-analyst", "q": "Comment calculer un risk/reward ratio et pourquoi c'est important?", "check": ["risk", "reward", "ratio"], "fmt": ["calcul|formul"]},

    # SEC (3 tests)
    {"cat": "sec", "agent": "main", "q": "Liste les 5 vulnerabilites web les plus critiques (OWASP Top 5)", "check": ["injection|xss|csrf|auth|access"], "fmt": ["severite|critique|haut"]},
    {"cat": "sec", "agent": "main", "q": "Comment securiser une API REST? Liste les bonnes pratiques.", "check": ["auth|token|https|rate.limit|valid"], "fmt": ["pratique|regle"]},
    {"cat": "sec", "agent": "main", "q": "Explique l'attaque SQL injection et comment s'en proteger", "check": ["sql", "inject", "param|prepar|sanitiz"], "fmt": ["correctif|protect"]},

    # CREAT (3 tests) — scoring needs check/fmt patterns to differentiate quality
    {"cat": "creat", "agent": "main", "q": "Redige un pitch de 3 phrases pour une app de meditation IA personnalisee", "check": ["meditation|meditat", "ia|intelligen", "personnal|adapt"], "fmt": ["**", "1\\.|2\\.|3\\."], "min_len": 80, "max_len": 500},
    {"cat": "creat", "agent": "main", "q": "Ecris un slogan accrocheur pour un cafe tech a Paris", "check": ["cafe|coffee", "tech|code|dev|numer"], "fmt": ["**|slogan"], "min_len": 20, "max_len": 300},
    {"cat": "creat", "agent": "main", "q": "Propose 5 noms creatifs pour un chatbot IA francais", "check": ["1\\.|2\\.|3\\.|4\\.|5\\.", "chatbot|bot|ia|assistant"], "fmt": ["1\\.", "5\\."], "min_len": 60},

    # META (2 tests)
    {"cat": "meta", "agent": "main", "q": "Explique le concept de recursion a quelqu'un qui n'a jamais code", "check": ["recursion|recursif|appel"], "fmt": ["exemple|analogie"]},
    {"cat": "meta", "agent": "main", "q": "Quelle est la difference entre IA, machine learning et deep learning?", "check": ["ia|intelligence", "machine.learn|ml", "deep.learn|dl"], "fmt": []},
]

# ── Scoring Engine ─────────────────────────────────────────────────────────────
def score_response(test, text, latency_ms):
    """Score a response 0-100 on: correctness, structure, format, speed, length."""
    if not text or len(text) < 10:
        return {"total": 0, "correct": 0, "structure": 0, "format": 0, "speed": 0, "length": 0}

    low = text.lower()
    scores = {}

    # 1. Correctness (40 pts) — do key terms appear?
    if test.get("check"):
        hits = 0
        for pattern in test["check"]:
            if re.search(pattern, low):
                hits += 1
        scores["correct"] = int((hits / len(test["check"])) * 40)
    else:
        scores["correct"] = 30  # Creative tasks: base score

    # Exact answer check (bonus)
    if test.get("expect"):
        if test["expect"].lower() in low:
            scores["correct"] = min(40, scores["correct"] + 10)

    # Negative expectation check
    if test.get("expect_neg"):
        neg_patterns = ["non", "ne peut pas", "ne peut", "pas conclure", "impossible", "incorrect", "faux", "erreur"]
        if any(p in low for p in neg_patterns):
            scores["correct"] = min(40, scores["correct"] + 10)

    # 2. Structure (20 pts) — headings, lists, numbered steps
    struct_score = 0
    if re.search(r'#{1,4}\s', text): struct_score += 5       # Markdown headings
    if re.search(r'\n\s*[-*•]\s', text): struct_score += 4   # Bullet lists
    if re.search(r'\n\s*\d+[\.\)]\s', text): struct_score += 4  # Numbered lists
    if re.search(r'\*\*[^*]+\*\*', text): struct_score += 4  # Bold emphasis
    if len(text.split('\n')) >= 5: struct_score += 3          # Multi-line
    scores["structure"] = min(20, struct_score)

    # 3. Format compliance (20 pts) — expected format markers
    if test.get("fmt"):
        fmt_hits = 0
        for pattern in test["fmt"]:
            if re.search(pattern, low):
                fmt_hits += 1
        scores["format"] = int((fmt_hits / len(test["fmt"])) * 20)
    else:
        scores["format"] = 15  # No specific format = base score

    # 4. Speed (10 pts) — faster is better
    if latency_ms < 5000: scores["speed"] = 10
    elif latency_ms < 15000: scores["speed"] = 8
    elif latency_ms < 30000: scores["speed"] = 6
    elif latency_ms < 60000: scores["speed"] = 4
    else: scores["speed"] = 2

    # 5. Length appropriateness (10 pts)
    text_len = len(text)
    min_len = test.get("min_len", 100)
    max_len = test.get("max_len", 3000)
    if min_len <= text_len <= max_len:
        scores["length"] = 10
    elif text_len < min_len:
        scores["length"] = max(0, int(10 * (text_len / min_len)))
    else:
        scores["length"] = max(3, 10 - int((text_len - max_len) / 500))

    scores["total"] = sum(scores.values())
    return scores


# ── Run a single test ──────────────────────────────────────────────────────────
def run_test(test, client):
    """Run one test and return result dict."""
    start = time.time()
    try:
        resp = client.post(PROXY, json={"text": test["q"], "agent": test["agent"]}, timeout=TIMEOUT)
        latency = int((time.time() - start) * 1000)
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}", "latency_ms": latency}

        data = resp.json().get("data", resp.json())
        text = data.get("text", "")
        mode = data.get("mode", "?")
        model = data.get("model", "?")
        turns = data.get("turns", 0)
        chain = data.get("chain", [])

        scores = score_response(test, text, latency)

        return {
            "ok": True, "text": text[:500], "full_len": len(text),
            "mode": mode, "model": model, "turns": turns,
            "chain": [{"node": s.get("node"), "role": s.get("role"), "ms": s.get("duration_ms", 0)} for s in chain],
            "latency_ms": latency, "scores": scores
        }
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        return {"ok": False, "error": str(e)[:200], "latency_ms": latency}


# ── Improvement Suggestions ────────────────────────────────────────────────────
def analyze_cycle(results):
    """Analyze cycle results and return improvement suggestions."""
    cat_scores = {}
    cat_issues = {}

    for r in results:
        cat = r["cat"]
        if cat not in cat_scores:
            cat_scores[cat] = []
            cat_issues[cat] = []

        if r["result"]["ok"]:
            cat_scores[cat].append(r["result"]["scores"]["total"])
            scores = r["result"]["scores"]
            if scores["correct"] < 25:
                cat_issues[cat].append("low_correctness")
            if scores["structure"] < 10:
                cat_issues[cat].append("poor_structure")
            if scores["format"] < 10:
                cat_issues[cat].append("bad_format")
            if scores["speed"] < 4:
                cat_issues[cat].append("too_slow")
        else:
            cat_scores[cat].append(0)
            cat_issues[cat].append("failure")

    suggestions = []
    for cat, scores_list in cat_scores.items():
        avg = sum(scores_list) / len(scores_list) if scores_list else 0
        issues = cat_issues.get(cat, [])

        if avg < 50:
            suggestions.append(f"[CRITICAL] {cat}: avg {avg:.0f}/100 — needs major prompt rewrite")
        elif avg < 70:
            suggestions.append(f"[WARNING] {cat}: avg {avg:.0f}/100 — needs tuning")

        if "low_correctness" in issues:
            suggestions.append(f"  → {cat}: improve correctness — add more specific instructions")
        if "poor_structure" in issues:
            suggestions.append(f"  → {cat}: improve structure — enforce markdown formatting")
        if "too_slow" in issues:
            suggestions.append(f"  → {cat}: too slow — reduce max_tokens or switch to faster node")

    return cat_scores, suggestions


# ── Main Loop ──────────────────────────────────────────────────────────────────
def main():
    total_cycles = 100
    tests_per_cycle = 5  # Random sample per cycle (40 total, 5 per cycle = ~100 total tests)
    all_scores = {}  # {cycle: {cat: avg_score}}

    print(f"{'='*70}")
    print(f"  JARVIS Agent Improvement Loop — {total_cycles} cycles")
    print(f"  {len(TEST_SUITE)} tests, {tests_per_cycle} per cycle")
    print(f"  Start: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*70}")
    print()

    client = httpx.Client(timeout=TIMEOUT)

    # Check proxy health
    try:
        r = client.get("http://127.0.0.1:18800/health", timeout=15)
    except:
        print("[ERROR] Proxy not responding on port 18800. Start it first.")
        sys.exit(1)

    global_start = time.time()
    cycle_scores_history = []
    best_cycle_score = 0
    total_tests_run = 0
    total_pass = 0

    for cycle in range(1, total_cycles + 1):
        cycle_start = time.time()

        # Select tests: rotate through all tests
        start_idx = ((cycle - 1) * tests_per_cycle) % len(TEST_SUITE)
        selected = []
        for i in range(tests_per_cycle):
            idx = (start_idx + i) % len(TEST_SUITE)
            selected.append(TEST_SUITE[idx])

        results = []
        cycle_total = 0

        cats_in_cycle = list(set(t["cat"] for t in selected))
        print(f"[Cycle {cycle:3d}/{total_cycles}] Testing: {', '.join(cats_in_cycle)}", end="", flush=True)

        for test in selected:
            result = run_test(test, client)
            total_tests_run += 1
            score = result.get("scores", {}).get("total", 0) if result["ok"] else 0
            cycle_total += score
            if score >= 50:
                total_pass += 1

            results.append({"cat": test["cat"], "agent": test["agent"], "q": test["q"][:60], "result": result})

            # Log to file
            log_entry = {
                "ts": datetime.now().isoformat(),
                "cycle": cycle,
                "cat": test["cat"],
                "agent": test["agent"],
                "q": test["q"][:80],
                "ok": result["ok"],
                "score": score,
                "latency_ms": result.get("latency_ms", 0),
                "mode": result.get("mode", "?"),
                "model": result.get("model", "?")
            }
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        cycle_avg = cycle_total / len(selected)
        cycle_time = time.time() - cycle_start
        best_cycle_score = max(best_cycle_score, cycle_avg)

        # Score bar (ASCII safe)
        bar_len = int(cycle_avg / 100 * 20)
        bar = '#' * bar_len + '.' * (20 - bar_len)

        status = "OK" if cycle_avg >= 60 else "!!"
        print(f"  {status} avg={cycle_avg:.0f}/100 [{bar}] {cycle_time:.1f}s")

        cycle_scores_history.append({"cycle": cycle, "avg": round(cycle_avg, 1), "cats": cats_in_cycle})

        # Every 10 cycles: detailed analysis
        if cycle % 10 == 0:
            elapsed = time.time() - global_start
            pass_rate = (total_pass / total_tests_run * 100) if total_tests_run else 0
            print(f"\n{'─'*70}")
            print(f"  Checkpoint @ cycle {cycle} | {elapsed:.0f}s elapsed | {total_tests_run} tests | {pass_rate:.0f}% pass (≥50)")
            print(f"  Best cycle avg: {best_cycle_score:.0f}/100")

            # Analyze last 10 cycles
            recent = cycle_scores_history[-10:]
            trend = recent[-1]["avg"] - recent[0]["avg"]
            trend_str = f"+{trend:.0f}" if trend >= 0 else f"{trend:.0f}"
            print(f"  Trend (10 cycles): {trend_str} pts")

            # Category breakdown from log
            cat_totals = {}
            cat_counts = {}
            for entry in cycle_scores_history[-10:]:
                pass  # we use the log file instead

            # Quick breakdown from results
            cat_avgs = {}
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    recent_entries = []
                    for line in f:
                        try:
                            e = json.loads(line)
                            if e["cycle"] > cycle - 10:
                                recent_entries.append(e)
                        except:
                            pass

                for e in recent_entries:
                    cat = e["cat"]
                    if cat not in cat_avgs:
                        cat_avgs[cat] = []
                    cat_avgs[cat].append(e["score"])

                print(f"\n  {'Category':<12} {'Avg':>5} {'Tests':>6} {'Status'}")
                print(f"  {'─'*40}")
                for cat in sorted(cat_avgs.keys()):
                    avg = sum(cat_avgs[cat]) / len(cat_avgs[cat])
                    count = len(cat_avgs[cat])
                    status = "GOOD" if avg >= 70 else ("TUNE" if avg >= 50 else "FIX!")
                    print(f"  {cat:<12} {avg:5.0f} {count:6d}  {status}")
            except:
                pass

            print(f"{'─'*70}\n")

        # Small delay between cycles to avoid overloading
        time.sleep(0.5)

    # ── Final Report ───────────────────────────────────────────────────────────
    total_time = time.time() - global_start
    pass_rate = (total_pass / total_tests_run * 100) if total_tests_run else 0

    print(f"\n{'='*70}")
    print(f"  FINAL REPORT — {total_cycles} cycles completed")
    print(f"{'='*70}")
    print(f"  Total time: {total_time:.0f}s ({total_time/60:.1f}min)")
    print(f"  Tests run: {total_tests_run}")
    print(f"  Pass rate (≥50): {pass_rate:.1f}%")
    print(f"  Best cycle avg: {best_cycle_score:.0f}/100")

    # Overall category averages from full log
    try:
        cat_all = {}
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    cat = e["cat"]
                    if cat not in cat_all:
                        cat_all[cat] = []
                    cat_all[cat].append(e["score"])
                except:
                    pass

        print(f"\n  {'Category':<12} {'Avg':>5} {'Min':>5} {'Max':>5} {'Tests':>6} {'Grade'}")
        print(f"  {'─'*50}")
        overall_avg = 0
        overall_count = 0
        for cat in sorted(cat_all.keys()):
            scores = cat_all[cat]
            avg = sum(scores) / len(scores)
            mn = min(scores)
            mx = max(scores)
            grade = "A" if avg >= 80 else ("B" if avg >= 65 else ("C" if avg >= 50 else "D"))
            print(f"  {cat:<12} {avg:5.0f} {mn:5.0f} {mx:5.0f} {len(scores):6d}  {grade}")
            overall_avg += sum(scores)
            overall_count += len(scores)

        if overall_count:
            print(f"  {'─'*50}")
            print(f"  {'OVERALL':<12} {overall_avg/overall_count:5.0f}")

        # Save final scores
        final = {
            "timestamp": datetime.now().isoformat(),
            "cycles": total_cycles,
            "total_tests": total_tests_run,
            "pass_rate": round(pass_rate, 1),
            "best_cycle": round(best_cycle_score, 1),
            "categories": {cat: {"avg": round(sum(s)/len(s), 1), "count": len(s)} for cat, s in cat_all.items()}
        }
        with open(SCORES_FILE, "w", encoding="utf-8") as f:
            json.dump(final, f, indent=2, ensure_ascii=False)
        print(f"\n  Scores saved to: {SCORES_FILE}")
    except Exception as e:
        print(f"  Error reading log: {e}")

    print(f"\n  Log file: {LOG_FILE}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
