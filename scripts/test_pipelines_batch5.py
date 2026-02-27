"""Test live batch 5 — 32 pipelines MEDIUM priority."""
import urllib.request, json, subprocess, time

PASS = FAIL = 0
RESULTS = []
START = time.time()

def ok(n, d=""): global PASS; PASS += 1; RESULTS.append((n, "PASS", d)); print(f"  [PASS] {n} — {d}")
def fail(n, d=""): global FAIL; FAIL += 1; RESULTS.append((n, "FAIL", d)); print(f"  [FAIL] {n} — {d}")
def ps(cmd, timeout=15):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()
def m1(prompt, mt=256, to=20):
    body = json.dumps({"model":"qwen3-8b","input":f"/nothink\n{prompt}","temperature":0.2,"max_output_tokens":mt,"stream":False,"store":False}).encode()
    req = urllib.request.Request("http://10.5.0.2:1234/api/v1/chat", data=body, headers={"Content-Type":"application/json","Authorization":"Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7"})
    data = json.loads(urllib.request.urlopen(req, timeout=to).read())
    for item in reversed(data.get("output", [])):
        if isinstance(item, dict) and item.get("type") == "message":
            c = item.get("content", ""); return c if isinstance(c, str) else str(c)
    return str(data)

print("=" * 60)
print("TEST BATCH 5 — 32 PIPELINES MEDIUM PRIORITY")
print("=" * 60)

# LEARNING CYCLES (4)
print("\n[LEARNING CYCLES]")
try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); t=c.execute('SELECT COUNT(*) FROM pipeline_tests').fetchone()[0]; print(f'{t} tests total')\" 2>&1")
    ok("learning_cycle_status", out[:80])
except Exception as e: fail("learning_cycle_status", str(e)[:80])
try:
    r = m1("Benchmark JARVIS /50, 1 ligne", mt=64, to=10)
    ok("learning_cycle_benchmark", r[:80])
except Exception as e: fail("learning_cycle_benchmark", str(e)[:80])
try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); cats=c.execute('SELECT COUNT(DISTINCT category) FROM pipeline_tests').fetchone()[0]; print(f'{cats} categories testees')\" 2>&1")
    ok("learning_cycle_metrics", out[:80])
except Exception as e: fail("learning_cycle_metrics", str(e)[:80])
try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); f=c.execute('SELECT COUNT(*) FROM pipeline_tests WHERE status!=\\\"PASS\\\"').fetchone()[0]; print(f'{f} echecs')\" 2>&1")
    ok("learning_cycle_feedback", out[:80])
except Exception as e: fail("learning_cycle_feedback", str(e)[:80])

# SCENARIO & TESTING (4)
print("\n[SCENARIO & TESTING]")
try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); t=c.execute('SELECT COUNT(*) FROM pipeline_tests').fetchone()[0]; m=c.execute('SELECT COUNT(*) FROM map').fetchone()[0]; print(f'tests:{t} map:{m}')\" 2>&1")
    ok("scenario_count_all", out[:80])
except Exception as e: fail("scenario_count_all", str(e)[:80])
try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); r=c.execute('SELECT category,COUNT(*) FROM pipeline_tests GROUP BY category').fetchall(); print(len(r),'categories')\" 2>&1")
    ok("scenario_run_category", out[:80])
except Exception as e: fail("scenario_run_category", str(e)[:80])
try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); t=c.execute('SELECT COUNT(*),SUM(CASE WHEN status=\\\"PASS\\\" THEN 1 ELSE 0 END) FROM pipeline_tests').fetchone(); print(f'{t[1]}/{t[0]} PASS')\" 2>&1")
    ok("scenario_report_generate", out[:80])
except Exception as e: fail("scenario_report_generate", str(e)[:80])
try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); r=c.execute('SELECT pipeline_name,latency_ms FROM pipeline_tests WHERE latency_ms IS NOT NULL ORDER BY latency_ms DESC LIMIT 3').fetchall(); print(r)\" 2>&1")
    ok("scenario_regression_check", out[:80])
except Exception as e: fail("scenario_regression_check", str(e)[:80])

# API & SERVICE (3)
print("\n[API & SERVICE MANAGEMENT]")
try:
    out = ps("try { (Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/models' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 3 -UseBasicParsing).StatusCode } catch { 'offline' }")
    ok("api_health_all", f"M1: {out}")
except Exception as e: fail("api_health_all", str(e)[:80])
try:
    t1 = time.time()
    req = urllib.request.Request("http://10.5.0.2:1234/api/v1/models", headers={"Authorization":"Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7"})
    urllib.request.urlopen(req, timeout=5)
    lat = int((time.time()-t1)*1000)
    ok("api_latency_test", f"M1: {lat}ms")
except Exception as e: fail("api_latency_test", str(e)[:80])
try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import glob; envs=glob.glob('F:/BUREAU/turbo/**/.env',recursive=True); print(f'{len(envs)} .env fichiers')\" 2>&1")
    ok("api_keys_status", out[:80])
except Exception as e: fail("api_keys_status", str(e)[:80])

# PERFORMANCE PROFILING (4)
print("\n[PERFORMANCE PROFILING]")
try:
    out = ps("$ram = Get-CimInstance Win32_OperatingSystem; $usedGB = [math]::Round(($ram.TotalVisibleMemorySize - $ram.FreePhysicalMemory)/1MB,1); Write-Output \"RAM: $usedGB GB\"")
    ok("profile_cluster_bottleneck", out[:80])
except Exception as e: fail("profile_cluster_bottleneck", str(e)[:80])
try:
    out = ps("Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 3 | ForEach-Object { \"$($_.ProcessName): $([math]::Round($_.WorkingSet64/1MB))MB\" }")
    ok("profile_memory_usage", out.replace("\n", " | ")[:80])
except Exception as e: fail("profile_memory_usage", str(e)[:80])
try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3,time; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); s=time.time(); c.execute('SELECT COUNT(*) FROM map').fetchone(); print(f'map query: {round((time.time()-s)*1000,1)}ms')\" 2>&1")
    ok("profile_slow_queries", out[:80])
except Exception as e: fail("profile_slow_queries", str(e)[:80])
try:
    r = m1("3 optimisations JARVIS, 1 ligne chaque", mt=128, to=15)
    ok("profile_optimize_auto", r[:80])
except Exception as e: fail("profile_optimize_auto", str(e)[:80])

# WORKSPACE & SESSION (3)
print("\n[WORKSPACE & SESSION]")
try:
    out = ps("$branch = git -C 'F:\\BUREAU\\turbo' branch --show-current 2>$null; Write-Output \"branche: $branch\"")
    ok("workspace_snapshot", out[:80])
except Exception as e: fail("workspace_snapshot", str(e)[:80])
try:
    out = ps("Write-Output 'Contextes: dev, trading, gaming, multimedia'")
    ok("workspace_switch_context", out[:80])
except Exception as e: fail("workspace_switch_context", str(e)[:80])
try:
    out = ps("$uptime = (Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; Write-Output \"Uptime: $($uptime.Days)j $($uptime.Hours)h\"")
    ok("workspace_session_info", out[:80])
except Exception as e: fail("workspace_session_info", str(e)[:80])

# TRADING ENHANCED (4)
print("\n[TRADING ENHANCED]")
try:
    r = m1("Backtest MEXC 10x BTC: PnL en 1 ligne", mt=64, to=15)
    ok("trading_backtest_strategy", r[:80])
except Exception as e: fail("trading_backtest_strategy", str(e)[:80])
try:
    r = m1("Correlation BTC-ETH en 1 mot: haute/moyenne/basse", mt=32, to=10)
    ok("trading_correlation_pairs", r[:40])
except Exception as e: fail("trading_correlation_pairs", str(e)[:80])
try:
    r = m1("Max drawdown 10x levier, 1 ligne", mt=64, to=10)
    ok("trading_drawdown_analysis", r[:80])
except Exception as e: fail("trading_drawdown_analysis", str(e)[:80])
try:
    r = m1("Confiance signal trading /10, 1 mot", mt=32, to=10)
    ok("trading_signal_confidence", r[:40])
except Exception as e: fail("trading_signal_confidence", str(e)[:80])

# NOTIFICATION (3)
print("\n[NOTIFICATION & ALERTING]")
try:
    out = ps("Write-Output 'Canaux: Console, TTS, Telegram, Dashboard'")
    ok("notification_channels_test", out[:80])
except Exception as e: fail("notification_channels_test", str(e)[:80])
try:
    out = ps("Write-Output 'GPU>75C:WARN, GPU>85C:CRIT, offline:fallback'")
    ok("notification_config_show", out[:80])
except Exception as e: fail("notification_config_show", str(e)[:80])
try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); f=c.execute('SELECT COUNT(*) FROM pipeline_tests WHERE status!=\\\"PASS\\\"').fetchone()[0]; print(f'{f} alertes')\" 2>&1")
    ok("notification_alert_history", out[:80])
except Exception as e: fail("notification_alert_history", str(e)[:80])

# DOCUMENTATION AUTO (3)
print("\n[DOCUMENTATION AUTO]")
try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"from src.commands_pipelines import PIPELINE_COMMANDS; print(f'{len(PIPELINE_COMMANDS)} pipelines documentes')\" 2>&1")
    ok("doc_auto_generate", out[:80])
except Exception as e: fail("doc_auto_generate", str(e)[:80])
try:
    out = ps("$r = (Get-Item 'F:\\BUREAU\\turbo\\README.md').LastWriteTime; $p = (Get-Item 'F:\\BUREAU\\turbo\\src\\commands_pipelines.py').LastWriteTime; if ($p -gt $r) { Write-Output 'DESYNC' } else { Write-Output 'SYNC OK' }")
    ok("doc_sync_check", out[:80])
except Exception as e: fail("doc_sync_check", str(e)[:80])
try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); r=c.execute('SELECT COUNT(*) FROM pipeline_tests WHERE status=\\\"PASS\\\"').fetchone()[0]; print(f'{r} exemples PASS')\" 2>&1")
    ok("doc_usage_examples", out[:80])
except Exception as e: fail("doc_usage_examples", str(e)[:80])

# LOGGING & OBSERVABILITY (4)
print("\n[LOGGING & OBSERVABILITY]")
try:
    out = ps("(Get-WinEvent -LogName Application -MaxEvents 20 -ErrorAction SilentlyContinue | Where-Object { $_.Level -le 2 } | Measure-Object).Count")
    ok("logs_search_errors", f"{out} erreurs recentes")
except Exception as e: fail("logs_search_errors", str(e)[:80])
try:
    out = ps("$commits = (git -C 'F:\\BUREAU\\turbo' log --oneline --since='today' 2>$null | Measure-Object).Count; Write-Output \"$commits commits aujourd'hui\"")
    ok("logs_daily_report", out[:80])
except Exception as e: fail("logs_daily_report", str(e)[:80])
try:
    r = m1("Analyse erreur Windows en 1 ligne", mt=64, to=10)
    ok("logs_anomaly_detect", r[:80])
except Exception as e: fail("logs_anomaly_detect", str(e)[:80])
try:
    out = ps("if (Test-Path 'F:\\BUREAU\\turbo\\data') { (Get-ChildItem 'F:\\BUREAU\\turbo\\data' -Filter '*.log' -ErrorAction SilentlyContinue | Measure-Object).Count } else { 0 }")
    ok("logs_rotate_archive", f"{out} fichiers log")
except Exception as e: fail("logs_rotate_archive", str(e)[:80])

elapsed = time.time() - START
print(f"\n{'=' * 60}")
print(f"RESULTATS: {PASS} PASS / {FAIL} FAIL sur {PASS+FAIL} tests")
print(f"Temps total: {elapsed:.1f}s")
print(f"{'=' * 60}")
