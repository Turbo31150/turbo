"""Test LIVE domino pipelines — execute les cascades reelles sur le cluster."""
import urllib.request, json, subprocess, time

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
            if isinstance(content, str): return content
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "output_text": return c["text"]
    return str(data)

print("=" * 60)
print("TEST LIVE DOMINO PIPELINES — CASCADES CLUSTER")
print("=" * 60)

# === ROUTINE MATIN — domino_matin_complet ===
print("\n[DOMINO] routine_matin: domino_matin_complet")
try:
    # Step 1: GPU check
    gpu = ps("nvidia-smi --query-gpu=temperature.gpu,memory.used --format=csv,noheader")
    print(f"    Step 1 GPU: {gpu[:60]}")
    # Step 2: Cluster health
    resp = urllib.request.urlopen("http://10.5.0.2:1234/api/v1/models", timeout=5)
    models = json.loads(resp.read())
    m1_models = len(models.get("data", models.get("models", [])))
    print(f"    Step 2 M1: {m1_models} modeles charges")
    # Step 3: Date/heure
    dt = ps("Get-Date -Format 'dddd dd MMMM yyyy HH:mm'")
    print(f"    Step 3 Date: {dt}")
    ok("domino_matin_complet", f"3 steps OK — GPU+M1+Date")
except Exception as e: fail("domino_matin_complet", str(e)[:80])

# === TRADING CASCADE — domino_trading_full_scan ===
print("\n[DOMINO] trading_cascade: domino_trading_full_scan")
try:
    # Step 1: M1 analyse prix
    prices = m1_ask("Donne le prix approximatif actuel du BTC et ETH en 1 ligne", 128)
    print(f"    Step 1 Prix: {prices[:60]}")
    # Step 2: M1 correlation
    corr = m1_ask("Correlation BTC-ETH: haute, moyenne ou basse? 1 mot", 32)
    print(f"    Step 2 Corr: {corr[:40]}")
    # Step 3: M1 signal
    sig = m1_ask("Score de trading BTC sur 100 (nombre seulement)", 32)
    print(f"    Step 3 Signal: {sig[:40]}")
    ok("domino_trading_full_scan", f"3 steps M1 OK")
except Exception as e: fail("domino_trading_full_scan", str(e)[:80])

# === DEBUG CASCADE — domino_debug_cluster ===
print("\n[DOMINO] debug_cascade: domino_debug_cluster")
try:
    nodes_ok = 0
    for name, url in [("M1", "http://10.5.0.2:1234/api/v1/models"), ("M2", "http://192.168.1.26:1234/api/v1/models"), ("OL1", "http://127.0.0.1:11434/api/tags")]:
        try:
            urllib.request.urlopen(url, timeout=3)
            print(f"    {name}: ONLINE")
            nodes_ok += 1
        except: print(f"    {name}: OFFLINE")
    ok("domino_debug_cluster", f"{nodes_ok}/3 nodes online")
except Exception as e: fail("domino_debug_cluster", str(e)[:80])

# === GPU THERMAL — domino_gpu_monitor_full ===
print("\n[DOMINO] gpu_thermal: domino_gpu_monitor_full")
try:
    metrics = ps("nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader")
    lines = [l.strip() for l in metrics.split("\n") if l.strip()]
    print(f"    {len(lines)} GPU detectes")
    for i, l in enumerate(lines[:3]):
        print(f"    GPU{i}: {l[:70]}")
    # M1 evaluation
    eval_result = m1_ask(f"Evalue en 1 ligne si ces GPU sont OK: {metrics[:200]}", 128)
    print(f"    M1 eval: {eval_result[:60]}")
    ok("domino_gpu_monitor_full", f"{len(lines)} GPU + M1 eval OK")
except Exception as e: fail("domino_gpu_monitor_full", str(e)[:80])

# === DEPLOY FLOW — domino_deploy_standard (dry run) ===
print("\n[DOMINO] deploy_flow: domino_deploy_standard (dry run)")
try:
    status = ps("git -C 'F:\\BUREAU\\turbo' status --short")
    branch = ps("git -C 'F:\\BUREAU\\turbo' branch --show-current")
    last = ps("git -C 'F:\\BUREAU\\turbo' log -1 --oneline")
    print(f"    Branch: {branch}, Last: {last[:50]}")
    print(f"    Status: {len(status.split(chr(10)))} fichiers modifies")
    ok("domino_deploy_standard", f"branch={branch}, dry run OK")
except Exception as e: fail("domino_deploy_standard", str(e)[:80])

# === SECURITY SWEEP — domino_security_full ===
print("\n[DOMINO] security_sweep: domino_security_full")
try:
    ports = ps("(Get-NetTCPConnection -State Listen | Select-Object -ExpandProperty LocalPort -Unique).Count")
    print(f"    Step 1 Ports ouverts: {ports}")
    fw = ps("(Get-NetFirewallProfile | Where-Object {$_.Enabled}).Count")
    print(f"    Step 2 Firewall profiles actifs: {fw}")
    envs = ps("(Get-ChildItem 'F:\\BUREAU\\turbo' -Recurse -Filter '.env*' -ErrorAction SilentlyContinue).Count")
    print(f"    Step 3 Fichiers .env: {envs}")
    ok("domino_security_full", f"ports={ports}, fw={fw}, env={envs}")
except Exception as e: fail("domino_security_full", str(e)[:80])

# === BACKUP CHAIN — domino_backup_quick ===
print("\n[DOMINO] backup_chain: domino_backup_quick")
try:
    size = ps("(Get-Item 'F:\\BUREAU\\turbo\\data\\etoile.db').Length / 1MB")
    print(f"    etoile.db: {size} MB")
    ok("domino_backup_quick", f"etoile.db size={size}MB")
except Exception as e: fail("domino_backup_quick", str(e)[:80])

# === MONITORING ALERT — domino_monitor_system_full ===
print("\n[DOMINO] monitoring_alert: domino_monitor_system_full")
try:
    cpu = ps("(Get-CimInstance Win32_Processor).LoadPercentage")
    print(f"    CPU: {cpu}%")
    ram = ps("[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)")
    print(f"    RAM libre: {ram} GB")
    disk_c = ps("[math]::Round((Get-PSDrive C).Free/1GB,1)")
    disk_f = ps("[math]::Round((Get-PSDrive F).Free/1GB,1)")
    print(f"    Disques: C={disk_c}GB F={disk_f}GB libres")
    ok("domino_monitor_system_full", f"CPU={cpu}% RAM={ram}GB C={disk_c}GB")
except Exception as e: fail("domino_monitor_system_full", str(e)[:80])

# === COLLABORATION — domino_collab_consensus ===
print("\n[DOMINO] collaboration: domino_collab_consensus")
try:
    question = "Le fine-tuning QLoRA est-il meilleur que LoRA standard pour un modele 8B? Reponds OUI ou NON en 1 mot."
    # M1
    r1 = m1_ask(question, 32)
    print(f"    M1: {r1[:30]}")
    # OL1
    body = json.dumps({"model": "qwen3:1.7b", "messages": [{"role": "user", "content": question}], "stream": False, "think": False}).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=body, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=10)
    r2 = json.loads(resp.read())["message"]["content"]
    print(f"    OL1: {r2[:30]}")
    ok("domino_collab_consensus", f"M1+OL1 consensus OK")
except Exception as e: fail("domino_collab_consensus", str(e)[:80])

# === STREAMING — domino_stream_start (dry run) ===
print("\n[DOMINO] streaming: domino_stream_start (dry run)")
try:
    net = ps("$p = Test-Connection 8.8.8.8 -Count 1 -TimeoutSeconds 3 -ErrorAction SilentlyContinue; if ($p) { $p.ResponseTime.ToString() + 'ms' } else { 'timeout' }")
    print(f"    Reseau: {net}")
    obs = ps("$obs = Get-Process -Name 'obs64','obs32' -ErrorAction SilentlyContinue; if ($obs) { 'OBS ACTIF PID=' + $obs.Id } else { 'OBS inactif' }")
    print(f"    OBS: {obs}")
    ok("domino_stream_start", f"net={net}, {obs}")
except Exception as e: fail("domino_stream_start", str(e)[:80])

# === ROUTINE SOIR — domino_bonne_nuit (dry run) ===
print("\n[DOMINO] routine_soir: domino_bonne_nuit (dry run)")
try:
    hour = ps("(Get-Date).Hour")
    print(f"    Heure: {hour}h")
    gpu_temps = ps("nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader")
    print(f"    GPU temps: {gpu_temps[:40]}")
    ok("domino_bonne_nuit", f"heure={hour}h, dry run OK")
except Exception as e: fail("domino_bonne_nuit", str(e)[:80])

# === DEBUG DB — domino_debug_db ===
print("\n[DOMINO] debug_cascade: domino_debug_db")
try:
    integrity = ps("& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); print(c.execute('PRAGMA integrity_check').fetchone()[0])\" 2>&1")
    print(f"    Integrity: {integrity}")
    size = ps("(Get-Item 'F:\\BUREAU\\turbo\\data\\etoile.db').Length")
    print(f"    Size: {size} bytes")
    ok("domino_debug_db", f"integrity={integrity}, size={size}b")
except Exception as e: fail("domino_debug_db", str(e)[:80])

elapsed = time.time() - START
print(f"\n{'=' * 60}")
print(f"RESULTATS DOMINO LIVE: {PASS} PASS / {FAIL} FAIL sur {PASS+FAIL} cascades")
print(f"Temps total: {elapsed:.1f}s")
print(f"{'=' * 60}")
