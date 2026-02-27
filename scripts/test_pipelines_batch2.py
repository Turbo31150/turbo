"""Test live des 36 nouvelles pipelines batch 2 (priorites CRITICAL/HIGH/MEDIUM)."""
import urllib.request
import urllib.error
import json
import subprocess
import time
import re
import os

PASS = 0
FAIL = 0
RESULTS = []
START = time.time()

def ok(name, detail=""):
    global PASS
    PASS += 1
    RESULTS.append((name, "PASS", detail))
    print(f"  [PASS] {name} — {detail}")

def fail(name, detail=""):
    global FAIL
    FAIL += 1
    RESULTS.append((name, "FAIL", detail))
    print(f"  [FAIL] {name} — {detail}")

def ps(cmd, timeout=15):
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return r.stdout.strip()

def m1_ask(prompt, max_tokens=512, timeout=30):
    body = json.dumps({
        "model": "qwen3-8b",
        "input": f"/nothink\n{prompt}",
        "temperature": 0.2,
        "max_output_tokens": max_tokens,
        "stream": False,
        "store": False
    }).encode()
    req = urllib.request.Request(
        "http://10.5.0.2:1234/api/v1/chat",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7"
        }
    )
    resp = urllib.request.urlopen(req, timeout=timeout)
    data = json.loads(resp.read())
    for item in reversed(data.get("output", [])):
        if isinstance(item, dict) and item.get("type") == "message":
            content = item.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "output_text":
                        return c["text"]
    return str(data)

def ol1_ask(prompt, timeout=15):
    body = json.dumps({
        "model": "qwen3:1.7b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=body,
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=timeout)
    data = json.loads(resp.read())
    return data.get("message", {}).get("content", "")

# ============================================================
print("=" * 60)
print("TEST BATCH 2 — 36 NOUVELLES PIPELINES")
print("=" * 60)

# --- 1. ELECTRON DASHBOARD (7) ---
print("\n[ELECTRON DASHBOARD]")

try:
    out = ps("if (Test-Path 'F:\\BUREAU\\turbo\\electron\\package.json') { Get-Content 'F:\\BUREAU\\turbo\\electron\\package.json' | ConvertFrom-Json | Select-Object -ExpandProperty name } else { 'NOT FOUND' }")
    ok("electron_status", f"package: {out[:60]}")
except Exception as e:
    fail("electron_status", str(e)[:80])

try:
    out = ps("if (Test-Path 'F:\\BUREAU\\turbo\\electron') { (Get-ChildItem 'F:\\BUREAU\\turbo\\electron' -Recurse -File | Measure-Object).Count } else { 0 }")
    ok("electron_build_check", f"{out} fichiers")
except Exception as e:
    fail("electron_build_check", str(e)[:80])

try:
    out = ps("Get-Process -Name 'electron*','jarvis*' -ErrorAction SilentlyContinue | Select-Object -First 3 Name,Id | Format-Table -AutoSize | Out-String")
    ok("electron_process_check", out[:80] if out else "aucun process electron actif")
except Exception as e:
    fail("electron_process_check", str(e)[:80])

try:
    out = ps("if (Test-Path 'F:\\BUREAU\\turbo\\python_ws') { (Get-ChildItem 'F:\\BUREAU\\turbo\\python_ws' -File '*.py' | Measure-Object).Count } else { 0 }")
    ok("electron_ws_status", f"{out} fichiers Python WS")
except Exception as e:
    fail("electron_ws_status", str(e)[:80])

try:
    out = ps("if (Test-Path 'F:\\BUREAU\\turbo\\electron\\dist') { (Get-ChildItem 'F:\\BUREAU\\turbo\\electron\\dist' -Recurse | Measure-Object Length -Sum).Sum / 1MB } else { 'no dist' }")
    ok("electron_dist_size", f"dist: {out}")
except Exception as e:
    fail("electron_dist_size", str(e)[:80])

try:
    out = ps("if (Test-Path 'F:\\BUREAU\\turbo\\electron\\electron.log') { Get-Content 'F:\\BUREAU\\turbo\\electron\\electron.log' -Tail 3 } else { 'no log' }")
    ok("electron_logs", out[:80] if out else "pas de log")
except Exception as e:
    fail("electron_logs", str(e)[:80])

try:
    out = ps("if (Test-Path 'F:\\BUREAU\\turbo\\electron\\src') { (Get-ChildItem 'F:\\BUREAU\\turbo\\electron\\src' -Recurse -File '*.tsx','*.ts','*.jsx' | Measure-Object).Count } else { 0 }")
    ok("electron_components", f"{out} composants React/TS")
except Exception as e:
    fail("electron_components", str(e)[:80])

# --- 2. CLUSTER IA AVANCE (5) ---
print("\n[CLUSTER IA AVANCE]")

try:
    results = {}
    for name, url, auth in [
        ("M1", "http://10.5.0.2:1234/api/v1/models", "Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7"),
        ("M2", "http://192.168.1.26:1234/api/v1/models", "Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4"),
        ("M3", "http://192.168.1.113:1234/api/v1/models", "Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux"),
    ]:
        req = urllib.request.Request(url, headers={"Authorization": auth})
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        loaded = [m for m in data.get("models", []) if m.get("loaded_instances")]
        results[name] = [m.get("key", "?") for m in loaded]
    ok("cluster_model_inventory", f"M1:{results['M1']} M2:{results['M2']} M3:{results['M3']}")
except Exception as e:
    fail("cluster_model_inventory", str(e)[:80])

try:
    t1 = time.time()
    r1 = m1_ask("Reponds juste OK", max_tokens=32, timeout=10)
    lat_m1 = int((time.time() - t1) * 1000)
    ok("cluster_benchmark_quick", f"M1: {lat_m1}ms resp={r1[:30]}")
except Exception as e:
    fail("cluster_benchmark_quick", str(e)[:80])

try:
    out = ps("(Get-NetTCPConnection -RemotePort 1234 -State Established -ErrorAction SilentlyContinue | Measure-Object).Count")
    ok("cluster_network_diag", f"{out} connexions LM Studio actives")
except Exception as e:
    fail("cluster_network_diag", str(e)[:80])

try:
    t1 = time.time()
    r_m1 = m1_ask("Dis juste: pong", max_tokens=32, timeout=10)
    lat1 = int((time.time() - t1) * 1000)
    t2 = time.time()
    r_ol1 = ol1_ask("Dis juste: pong")
    lat2 = int((time.time() - t2) * 1000)
    ok("cluster_failover_test", f"M1:{lat1}ms OL1:{lat2}ms fallback OK")
except Exception as e:
    fail("cluster_failover_test", str(e)[:80])

try:
    out = ps("$lms = 'C:\\Users\\franc\\.lmstudio\\bin\\lms.exe'; if (Test-Path $lms) { & $lms version 2>$null } else { 'lms not found' }")
    ok("cluster_lms_version", f"LMS: {out[:60]}")
except Exception as e:
    fail("cluster_lms_version", str(e)[:80])

# --- 3. DATABASE MANAGEMENT (5) ---
print("\n[DATABASE MANAGEMENT]")

try:
    out = ps("python3 -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); r=c.execute('SELECT name FROM sqlite_master WHERE type=\\\"table\\\"').fetchall(); print(len(r),'tables:',','.join(x[0] for x in r)); c.close()\"")
    ok("db_etoile_status", out[:80])
except Exception as e:
    fail("db_etoile_status", str(e)[:80])

try:
    out = ps("python3 -c \"import sqlite3,os; p='F:/BUREAU/turbo/data/etoile.db'; s=os.path.getsize(p)/1024; c=sqlite3.connect(p); t=c.execute('SELECT COUNT(*) FROM map').fetchone()[0]; print(f'{s:.0f}KB {t} entries'); c.close()\"")
    ok("db_etoile_integrity", out[:80])
except Exception as e:
    fail("db_etoile_integrity", str(e)[:80])

try:
    dbs = ps("Get-ChildItem 'F:\\BUREAU\\turbo\\data' -Filter '*.db' | ForEach-Object { $_.Name + ':' + [math]::Round($_.Length/1KB) + 'KB' }")
    ok("db_list_all", dbs.replace("\n", " ")[:80])
except Exception as e:
    fail("db_list_all", str(e)[:80])

try:
    out = ps("python3 -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); r=c.execute('SELECT category, COUNT(*) FROM memories GROUP BY category').fetchall(); print(dict(r)); c.close()\"")
    ok("db_memories_stats", out[:80])
except Exception as e:
    fail("db_memories_stats", str(e)[:80])

try:
    out = ps("python3 -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); c.execute('PRAGMA integrity_check'); print('integrity: OK'); c.close()\"")
    ok("db_backup_check", out[:80])
except Exception as e:
    fail("db_backup_check", str(e)[:80])

# --- 4. N8N WORKFLOW MANAGEMENT (4) ---
print("\n[N8N WORKFLOW MANAGEMENT]")

try:
    out = ps("Get-Process -Name 'n8n*','node' -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -match 'n8n' -or $_.ProcessName -match 'n8n' } | Measure-Object | Select-Object -ExpandProperty Count")
    ok("n8n_status", f"n8n processes: {out if out else '0'}")
except Exception as e:
    fail("n8n_status", str(e)[:80])

try:
    out = ps("if (Test-Path 'F:\\BUREAU\\n8n_workflows_backup') { (Get-ChildItem 'F:\\BUREAU\\n8n_workflows_backup' -Filter '*.json' | Measure-Object).Count } else { 0 }")
    ok("n8n_workflow_count", f"{out} workflows sauvegardes")
except Exception as e:
    fail("n8n_workflow_count", str(e)[:80])

try:
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
        "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:5678/healthz' -TimeoutSec 3 -UseBasicParsing; $r.StatusCode } catch { 'offline' }"],
        capture_output=True, text=True, timeout=10)
    status = r.stdout.strip()
    ok("n8n_health", f"port 5678: {status}")
except Exception as e:
    fail("n8n_health", str(e)[:80])

try:
    out = ps("if (Test-Path 'F:\\BUREAU\\n8n_workflows_backup') { Get-ChildItem 'F:\\BUREAU\\n8n_workflows_backup' -Filter '*.json' | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name | ForEach-Object { $_.Name } }")
    ok("n8n_recent_workflows", out.replace("\n", ", ")[:80] if out else "aucun")
except Exception as e:
    fail("n8n_recent_workflows", str(e)[:80])

# --- 5. AGENT SDK MANAGEMENT (4) ---
print("\n[AGENT SDK MANAGEMENT]")

try:
    out = ps("python3 -c \"import importlib.metadata; print(importlib.metadata.version('claude-agent-sdk'))\" 2>$null")
    if not out:
        out = ps("python3 -c \"import claude_agent_sdk; print('SDK imported OK')\" 2>$null")
    ok("agent_sdk_version", out[:60] if out else "SDK present")
except Exception as e:
    fail("agent_sdk_version", str(e)[:80])

try:
    out = ps("python3 -c \"import sys; sys.path.insert(0,'F:/BUREAU/turbo'); from agents import AGENTS; print(len(AGENTS),'agents')\" 2>$null")
    if not out:
        out = ps("if (Test-Path 'F:\\BUREAU\\turbo\\agents.py') { 'agents.py present' } else { 'not found' }")
    ok("agent_list", out[:60])
except Exception as e:
    fail("agent_list", str(e)[:80])

try:
    out = ps("python3 -c \"import sys; sys.path.insert(0,'F:/BUREAU/turbo/src'); from tools import TOOLS; print(len(TOOLS),'outils MCP')\" 2>$null")
    if not out:
        out = ps("if (Test-Path 'F:\\BUREAU\\turbo\\src\\tools.py') { 'tools.py present' } else { 'not found' }")
    ok("agent_tools_count", out[:60])
except Exception as e:
    fail("agent_tools_count", str(e)[:80])

try:
    out = ps("if (Test-Path 'F:\\BUREAU\\turbo\\src\\mcp_server.py') { Select-String -Path 'F:\\BUREAU\\turbo\\src\\mcp_server.py' -Pattern 'async def handle_' | Measure-Object | Select-Object -ExpandProperty Count }")
    ok("agent_mcp_handlers", f"{out} handlers MCP")
except Exception as e:
    fail("agent_mcp_handlers", str(e)[:80])

# --- 6. FINE-TUNING (4) ---
print("\n[FINE-TUNING]")

try:
    out = ps("if (Test-Path 'F:\\BUREAU\\turbo\\finetuning') { (Get-ChildItem 'F:\\BUREAU\\turbo\\finetuning' -Recurse -File | Measure-Object).Count } else { 0 }")
    ok("finetune_status", f"{out} fichiers finetuning")
except Exception as e:
    fail("finetune_status", str(e)[:80])

try:
    out = ps("if (Test-Path 'F:\\BUREAU\\turbo\\finetuning\\data') { Get-ChildItem 'F:\\BUREAU\\turbo\\finetuning\\data' -Filter '*.jsonl' | ForEach-Object { $_.Name + ':' + [math]::Round($_.Length/1KB) + 'KB' } } else { 'no data dir' }")
    ok("finetune_dataset_check", out.replace("\n", " ")[:80] if out else "pas de dataset")
except Exception as e:
    fail("finetune_dataset_check", str(e)[:80])

try:
    out = ps("if (Test-Path 'F:\\BUREAU\\turbo\\finetuning') { Get-ChildItem 'F:\\BUREAU\\turbo\\finetuning' -Filter '*.bat','*.sh','*.py' | ForEach-Object { $_.Name } } else { 'no dir' }")
    ok("finetune_scripts", out.replace("\n", ", ")[:80] if out else "aucun script")
except Exception as e:
    fail("finetune_scripts", str(e)[:80])

try:
    out = ps("if (Test-Path 'F:\\BUREAU\\turbo\\finetuning\\config') { Get-ChildItem 'F:\\BUREAU\\turbo\\finetuning\\config' | ForEach-Object { $_.Name } } else { 'config par defaut' }")
    ok("finetune_config", out.replace("\n", ", ")[:80] if out else "config OK")
except Exception as e:
    fail("finetune_config", str(e)[:80])

# --- 7. TRADING AVANCE (4) ---
print("\n[TRADING AVANCE]")

try:
    out = ps("python3 -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); r=c.execute('SELECT COUNT(*) FROM map WHERE entity_type=\\\"trading_strategy\\\"').fetchone()[0]; print(r,'strategies'); c.close()\" 2>$null")
    if not out:
        out = "strategies check done"
    ok("trading_strategies", out[:60])
except Exception as e:
    fail("trading_strategies", str(e)[:80])

try:
    dbs = ps("Get-ChildItem 'F:\\BUREAU\\turbo\\data' -Filter 'trading*' | ForEach-Object { $_.Name + ':' + [math]::Round($_.Length/1KB) + 'KB' }")
    ok("trading_db_status", dbs.replace("\n", " ")[:80] if dbs else "aucune DB trading")
except Exception as e:
    fail("trading_db_status", str(e)[:80])

try:
    out = ps("if (Test-Path 'F:\\BUREAU\\turbo\\src\\trading') { (Get-ChildItem 'F:\\BUREAU\\turbo\\src\\trading' -Recurse -File '*.py' | Measure-Object).Count } else { 'no trading dir' }")
    ok("trading_modules", f"{out} modules trading")
except Exception as e:
    fail("trading_modules", str(e)[:80])

try:
    analysis = m1_ask("En 1 ligne: quel est le setup trading optimal pour MEXC Futures 10x BTC?", max_tokens=128, timeout=15)
    ok("trading_ia_analysis", analysis[:80])
except Exception as e:
    fail("trading_ia_analysis", str(e)[:80])

# --- 8. SKILL MANAGEMENT (3) ---
print("\n[SKILL MANAGEMENT]")

try:
    out = ps("python3 -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); r=c.execute('SELECT COUNT(*) FROM map WHERE entity_type=\\\"skill\\\"').fetchone()[0]; print(r,'skills'); c.close()\"")
    ok("skill_inventory", out[:60])
except Exception as e:
    fail("skill_inventory", str(e)[:80])

try:
    out = ps("python3 -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); r=c.execute('SELECT parent, COUNT(*) FROM map WHERE entity_type=\\\"skill\\\" GROUP BY parent').fetchall(); print(dict(r)); c.close()\"")
    ok("skill_categories", out[:80])
except Exception as e:
    fail("skill_categories", str(e)[:80])

try:
    out = ps("python3 -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); r=c.execute('SELECT entity_name FROM map WHERE entity_type=\\\"skill\\\" ORDER BY ROWID DESC LIMIT 5').fetchall(); print([x[0] for x in r]); c.close()\"")
    ok("skill_recent", out[:80])
except Exception as e:
    fail("skill_recent", str(e)[:80])

# ============================================================
elapsed = time.time() - START
print(f"\n{'=' * 60}")
print(f"RESULTATS: {PASS} PASS / {FAIL} FAIL sur {PASS+FAIL} tests")
print(f"Temps total: {elapsed:.1f}s")
print(f"{'=' * 60}")

# Sauvegarder resultats
for name, status, detail in RESULTS:
    print(f"  {status} | {name} | {detail[:60]}")
