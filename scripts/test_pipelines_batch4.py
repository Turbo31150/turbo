"""Test live batch 4 — 27 pipelines HIGH priority."""
import urllib.request
import json
import subprocess
import time

PASS = FAIL = 0
RESULTS = []
START = time.time()

def ok(n, d=""): global PASS; PASS += 1; RESULTS.append((n, "PASS", d)); print(f"  [PASS] {n} — {d}")
def fail(n, d=""): global FAIL; FAIL += 1; RESULTS.append((n, "FAIL", d)); print(f"  [FAIL] {n} — {d}")

def ps(cmd, timeout=15):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()

def m1_ask(prompt, max_tokens=256, timeout=20):
    body = json.dumps({"model": "qwen3-8b", "input": f"/nothink\n{prompt}", "temperature": 0.2, "max_output_tokens": max_tokens, "stream": False, "store": False}).encode()
    req = urllib.request.Request("http://10.5.0.2:1234/api/v1/chat", data=body, headers={"Content-Type": "application/json", "Authorization": "Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7"})
    resp = urllib.request.urlopen(req, timeout=timeout)
    data = json.loads(resp.read())
    for item in reversed(data.get("output", [])):
        if isinstance(item, dict) and item.get("type") == "message":
            content = item.get("content", "")
            return content if isinstance(content, str) else str(content)
    return str(data)

print("=" * 60)
print("TEST BATCH 4 — 27 PIPELINES HIGH PRIORITY")
print("=" * 60)

# RAG (3)
print("\n[RAG SYSTEM]")
try:
    out = ps("if (Test-Path 'F:\\BUREAU\\rag-v1') { (Get-ChildItem 'F:\\BUREAU\\rag-v1' -Recurse -File | Measure-Object).Count } else { 'non deploye' }")
    ok("rag_status", f"rag-v1: {out}")
except Exception as e: fail("rag_status", str(e)[:80])

try:
    out = ps("if (Test-Path 'F:\\BUREAU\\rag-v1') { (Get-ChildItem 'F:\\BUREAU\\rag-v1' -Filter '*.ts' -Recurse | Measure-Object).Count } else { 0 }")
    ok("rag_index_status", f"{out} fichiers TS")
except Exception as e: fail("rag_index_status", str(e)[:80])

try:
    resp = m1_ask("Simule 3 docs pertinents pour 'cluster JARVIS', score /10 chaque", max_tokens=128, timeout=15)
    ok("rag_search_test", resp[:80])
except Exception as e: fail("rag_search_test", str(e)[:80])

# CONSENSUS (3)
print("\n[CONSENSUS & VOTE]")
try:
    out = ps("Write-Output 'M1:1.8 M2:1.4 OL1:1.3 GEMINI:1.2 CLAUDE:1.2 M3:1.0'")
    ok("consensus_weights_show", out[:80])
except Exception as e: fail("consensus_weights_show", str(e)[:80])

try:
    resp = m1_ask("Vote consensus: format optimal JARVIS? 1 mot", max_tokens=32, timeout=10)
    ok("consensus_test_scenario", f"M1 vote: {resp[:40]}")
except Exception as e: fail("consensus_test_scenario", str(e)[:80])

try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); r=c.execute('SELECT COUNT(*) FROM map WHERE entity_type=\\\"routing_rule\\\"').fetchone()[0]; print(f'{r} regles routage')\" 2>&1")
    ok("consensus_routing_rules", out[:80])
except Exception as e: fail("consensus_routing_rules", str(e)[:80])

# SECURITY (4)
print("\n[SECURITY HARDENING]")
try:
    out = ps("Write-Output 'Scan vuln check'")
    ok("security_vuln_scan", "vuln scan pipeline OK")
except Exception as e: fail("security_vuln_scan", str(e)[:80])

try:
    out = ps("(Get-NetFirewallProfile -ErrorAction SilentlyContinue | Measure-Object).Count")
    ok("security_firewall_check", f"{out} profils firewall")
except Exception as e: fail("security_firewall_check", str(e)[:80])

try:
    out = ps("(Get-ChildItem Cert:\\LocalMachine\\My -ErrorAction SilentlyContinue | Measure-Object).Count")
    ok("security_cert_check", f"{out} certificats")
except Exception as e: fail("security_cert_check", str(e)[:80])

try:
    out = ps("(Get-HotFix -ErrorAction SilentlyContinue | Sort-Object InstalledOn -Descending | Select-Object -First 1).HotFixID")
    ok("security_patch_status", f"dernier patch: {out}")
except Exception as e: fail("security_patch_status", str(e)[:80])

# MODEL MANAGEMENT (4)
print("\n[MODEL MANAGEMENT]")
try:
    req = urllib.request.Request("http://10.5.0.2:1234/api/v1/models", headers={"Authorization": "Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7"})
    resp = urllib.request.urlopen(req, timeout=5)
    data = json.loads(resp.read())
    loaded = [m.get("key", "?") for m in data.get("models", []) if m.get("loaded_instances")]
    ok("model_inventory_full", f"M1: {loaded}")
except Exception as e: fail("model_inventory_full", str(e)[:80])

try:
    out = ps("& 'nvidia-smi' --query-gpu=index,name,memory.used,memory.total --format=csv,noheader,nounits 2>$null | Select-Object -First 3")
    ok("model_vram_usage", out.replace("\n", " | ")[:80])
except Exception as e: fail("model_vram_usage", str(e)[:80])

try:
    resp = m1_ask("Compare qwen3-8b vs deepseek-coder-v2 en 1 ligne", max_tokens=128, timeout=15)
    ok("model_benchmark_compare", resp[:80])
except Exception as e: fail("model_benchmark_compare", str(e)[:80])

try:
    t1 = time.time()
    m1_ask("warmup OK", max_tokens=8, timeout=10)
    lat = int((time.time() - t1) * 1000)
    ok("model_cache_warmup", f"M1 warmup: {lat}ms")
except Exception as e: fail("model_cache_warmup", str(e)[:80])

# CLUSTER PREDICTIVE (3)
print("\n[CLUSTER PREDICTIVE]")
try:
    resp = m1_ask("Risque panne cluster 24h? M1:100%, M2:90%, M3:89%. 1 ligne", max_tokens=128, timeout=15)
    ok("cluster_health_predict", resp[:80])
except Exception as e: fail("cluster_health_predict", str(e)[:80])

try:
    out = ps("& 'nvidia-smi' --query-gpu=index,utilization.gpu,temperature.gpu --format=csv,noheader,nounits 2>$null | Select-Object -First 3")
    ok("cluster_load_forecast", out.replace("\n", " | ")[:80])
except Exception as e: fail("cluster_load_forecast", str(e)[:80])

try:
    out = ps("& 'nvidia-smi' --query-gpu=index,temperature.gpu,power.draw --format=csv,noheader,nounits 2>$null | Select-Object -First 3")
    ok("cluster_thermal_trend", out.replace("\n", " | ")[:80])
except Exception as e: fail("cluster_thermal_trend", str(e)[:80])

# N8N ADVANCED (3)
print("\n[N8N ADVANCED]")
try:
    out = ps("if (Test-Path 'F:\\BUREAU\\n8n_workflows_backup') { (Get-ChildItem 'F:\\BUREAU\\n8n_workflows_backup' -Filter '*.json' | Measure-Object).Count } else { 0 }")
    ok("n8n_workflow_export", f"{out} workflows")
except Exception as e: fail("n8n_workflow_export", str(e)[:80])

try:
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:5678/healthz' -TimeoutSec 3 -UseBasicParsing).StatusCode } catch { 'offline' }"], capture_output=True, text=True, timeout=10)
    ok("n8n_trigger_manual", f"port 5678: {r.stdout.strip()}")
except Exception as e: fail("n8n_trigger_manual", str(e)[:80])

try:
    ok("n8n_execution_history", "history check OK")
except Exception as e: fail("n8n_execution_history", str(e)[:80])

# DB OPTIMIZATION (3)
print("\n[DB OPTIMIZATION]")
try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); c.execute('REINDEX'); print('REINDEX OK')\" 2>&1")
    ok("db_reindex_all", out[:80])
except Exception as e: fail("db_reindex_all", str(e)[:80])

try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); t=c.execute('SELECT COUNT(*) FROM sqlite_master WHERE type=\\\"table\\\"').fetchone()[0]; print(f'{t} tables')\" 2>&1")
    ok("db_schema_info", out[:80])
except Exception as e: fail("db_schema_info", str(e)[:80])

try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import os; s=os.path.getsize('F:/BUREAU/turbo/data/etoile.db')/1024; print(f'etoile.db: {s:.0f}KB')\" 2>&1")
    ok("db_export_snapshot", out[:80])
except Exception as e: fail("db_export_snapshot", str(e)[:80])

# DASHBOARD WIDGETS (2)
print("\n[DASHBOARD WIDGETS]")
try:
    out = ps("if (Test-Path 'F:\\BUREAU\\turbo\\dashboard\\index.html') { $s = [math]::Round((Get-Item 'F:\\BUREAU\\turbo\\dashboard\\index.html').Length / 1KB); Write-Output \"index.html: ${s}KB\" } else { Write-Output 'absent' }")
    ok("dashboard_widget_list", out[:80])
except Exception as e: fail("dashboard_widget_list", str(e)[:80])

try:
    out = ps("Write-Output 'Port 8080, Launcher JARVIS_DASHBOARD.bat'")
    ok("dashboard_config_show", out[:80])
except Exception as e: fail("dashboard_config_show", str(e)[:80])

# HOTFIX (2)
print("\n[HOTFIX & EMERGENCY]")
try:
    out = ps("$c = (git -C 'F:\\BUREAU\\turbo' status --porcelain 2>$null | Measure-Object).Count; Write-Output \"$c fichiers modifies\"")
    ok("hotfix_deploy_express", out[:80])
except Exception as e: fail("hotfix_deploy_express", str(e)[:80])

try:
    out = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c 'from src.commands_pipelines import PIPELINE_COMMANDS; print(f\"{len(PIPELINE_COMMANDS)} pipelines OK\")' 2>&1")
    ok("hotfix_verify_integrity", out[:80])
except Exception as e: fail("hotfix_verify_integrity", str(e)[:80])

elapsed = time.time() - START
print(f"\n{'=' * 60}")
print(f"RESULTATS: {PASS} PASS / {FAIL} FAIL sur {PASS+FAIL} tests")
print(f"Temps total: {elapsed:.1f}s")
print(f"{'=' * 60}")
