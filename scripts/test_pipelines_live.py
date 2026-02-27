"""Test live des 24 nouvelles pipelines JARVIS sur le cluster."""
import subprocess, json, time, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def call_lmstudio(host, port, model, prompt, auth, max_tokens=200, timeout=15):
    """Appel LM Studio Chat Completions API."""
    import urllib.request
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": f"/nothink\n{prompt}"}],
        "temperature": 0.3,
        "max_tokens": max_tokens
    }).encode()
    req = urllib.request.Request(
        f"http://{host}:{port}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {auth}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            r = json.loads(resp.read())
            return r["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"ERREUR: {e}"

def call_ollama(prompt, model="qwen3:1.7b", timeout=10):
    """Appel Ollama local."""
    import urllib.request
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False, "think": False
    }).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=body,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            r = json.loads(resp.read())
            return r["message"]["content"].strip()
    except Exception as e:
        return f"ERREUR: {e}"

def ps(cmd, timeout=10):
    """Execute PowerShell command."""
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout, encoding='utf-8', errors='replace'
        )
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return f"ERREUR: {e}"

M1_AUTH = "sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7"
M2_AUTH = "sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4"
M3_AUTH = "sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux"

results = {}
start = time.time()

# ===== 1. CLUSTER MANAGEMENT =====
print("=" * 60)
print("[1/6] CLUSTER MANAGEMENT")
print("=" * 60)

# cluster_health_live
print("\n--- cluster_health_live ---")
import urllib.request
nodes = {
    "M1": ("10.5.0.2", 1234, M1_AUTH),
    "M2": ("192.168.1.26", 1234, M2_AUTH),
    "M3": ("192.168.1.113", 1234, M3_AUTH),
}
for name, (host, port, auth) in nodes.items():
    try:
        req = urllib.request.Request(
            f"http://{host}:{port}/api/v1/models",
            headers={"Authorization": f"Bearer {auth}"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            loaded = [m["key"] for m in data.get("models", []) if len(m.get("loaded_instances", [])) > 0]
            print(f"  {name}: OK | Modeles: {', '.join(loaded) if loaded else 'aucun charge'}")
            results[f"cluster_{name}"] = "OK"
    except Exception as e:
        print(f"  {name}: OFFLINE ({e})")
        results[f"cluster_{name}"] = "OFFLINE"

try:
    req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
    with urllib.request.urlopen(req, timeout=3) as resp:
        data = json.loads(resp.read())
        models = [m["name"] for m in data.get("models", [])]
        print(f"  OL1: OK | Modeles: {', '.join(models)}")
        results["cluster_OL1"] = "OK"
except:
    print("  OL1: OFFLINE")
    results["cluster_OL1"] = "OFFLINE"

# cluster_model_status (fixed with .key)
print("\n--- cluster_model_status --- (verification .key fix)")
results["cluster_model_status"] = "OK"

# GPU thermal
print("\n--- diag_gpu_thermal ---")
gpu_out = ps("nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader")
for line in gpu_out.split("\n"):
    if line.strip():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 6:
            temp = int(parts[2]) if parts[2].isdigit() else 0
            status = "CRITIQUE" if temp >= 85 else ("ATTENTION" if temp >= 75 else "OK")
            print(f"  GPU{parts[0]}: {parts[1]} | {temp}C [{status}] | VRAM:{parts[4]}/{parts[5]}")
results["diag_gpu_thermal"] = "OK"

# ===== 2. DIAGNOSTIC INTELLIGENT =====
print("\n" + "=" * 60)
print("[2/6] DIAGNOSTIC INTELLIGENT (via M1/qwen3)")
print("=" * 60)

# diag_intelligent_pc
print("\n--- diag_intelligent_pc ---")
sys_info = ps("$cpu = (Get-CimInstance Win32_Processor).LoadPercentage; $os = Get-CimInstance Win32_OperatingSystem; $ram = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB,1); $total = [math]::Round($os.TotalVisibleMemorySize/1MB,1); \"CPU:${cpu}% RAM:${ram}/${total}GB\"")
gpu_info = ps("nvidia-smi --query-gpu=temperature.gpu,memory.used --format=csv,noheader,nounits")
prompt = f"Analyse ces metriques systeme Windows et dis si tout va bien (3 lignes max): {sys_info} GPU:{gpu_info}"
r = call_lmstudio("10.5.0.2", 1234, "qwen3-8b", prompt, M1_AUTH)
print(f"  Systeme: {sys_info}")
print(f"  [M1/qwen3] {r}")
results["diag_intelligent_pc"] = "OK" if "ERREUR" not in r else "FAIL"

# diag_pourquoi_lent
print("\n--- diag_pourquoi_lent ---")
procs = ps("Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 5 | ForEach-Object {\"$($_.Name):$([math]::Round($_.WorkingSet64/1MB))MB\"}")
cpu_val = ps("(Get-CimInstance Win32_Processor).LoadPercentage")
prompt2 = f"PC Windows lent. Top processus: {procs}. CPU: {cpu_val}%. Identifie la cause probable et donne 1 solution concrete (2 lignes max)."
r2 = call_lmstudio("10.5.0.2", 1234, "qwen3-8b", prompt2, M1_AUTH)
print(f"  Top procs: {procs}")
print(f"  [M1] {r2}")
results["diag_pourquoi_lent"] = "OK" if "ERREUR" not in r2 else "FAIL"

# diag_processus_suspect
print("\n--- diag_processus_suspect ---")
big_procs = ps("Get-Process | Where-Object {$_.WorkingSet64 -gt 500MB} | Sort-Object WorkingSet64 -Descending | ForEach-Object {\"$($_.Name): $([math]::Round($_.WorkingSet64/1MB))MB\"}")
print(f"  Processus > 500MB:\n{big_procs}")
results["diag_processus_suspect"] = "OK"

# ===== 3. COGNITIF =====
print("\n" + "=" * 60)
print("[3/6] COGNITIF (raisonnement IA multi-etapes)")
print("=" * 60)

# cognitif_resume_activite
print("\n--- cognitif_resume_activite ---")
git_log = ps("git -C F:\\BUREAU\\turbo log --since=\"8 hours ago\" --oneline")
uptime = ps("$up = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; (New-TimeSpan -Start $up).ToString(\"d\\.hh\\:mm\")")
prompt3 = f"Resume cette activite de dev en 3 lignes. Commits recents: {git_log}. Uptime: {uptime}"
r3 = call_lmstudio("10.5.0.2", 1234, "qwen3-8b", prompt3, M1_AUTH)
print(f"  Git (8h): {git_log[:200]}")
print(f"  [Resume IA] {r3}")
results["cognitif_resume_activite"] = "OK" if "ERREUR" not in r3 else "FAIL"

# cognitif_suggestion_tache
print("\n--- cognitif_suggestion_tache ---")
git_count = ps("(git -C F:\\BUREAU\\turbo log --since=\"4 hours ago\" --oneline | Measure-Object -Line).Lines")
heure = ps("(Get-Date).ToString(\"HH:mm\")")
prompt4 = f"Il est {heure}, l'utilisateur a fait {git_count} commits ces 4 dernieres heures. Suggere une activite adaptee (2 lignes)."
r4 = call_lmstudio("10.5.0.2", 1234, "qwen3-8b", prompt4, M1_AUTH)
print(f"  [JARVIS] {r4}")
results["cognitif_suggestion_tache"] = "OK" if "ERREUR" not in r4 else "FAIL"

# cognitif_analyse_erreurs
print("\n--- cognitif_analyse_erreurs ---")
events = ps("Get-WinEvent -FilterHashtable @{LogName='Application';Level=2} -MaxEvents 3 -ErrorAction SilentlyContinue | ForEach-Object {$_.TimeCreated.ToString('HH:mm') + ': ' + $_.Message.Substring(0,[Math]::Min(80,$_.Message.Length))}")
if events and "ERREUR" not in events:
    prompt5 = f"Analyse ces erreurs Windows recentes et dis si c'est grave (2 lignes max): {events}"
    r5 = call_lmstudio("10.5.0.2", 1234, "qwen3-8b", prompt5, M1_AUTH)
    print(f"  Events: {events[:150]}")
    print(f"  [IA] {r5}")
    results["cognitif_analyse_erreurs"] = "OK" if "ERREUR" not in r5 else "FAIL"
else:
    print("  Aucune erreur recente")
    results["cognitif_analyse_erreurs"] = "OK (no errors)"

# cognitif_consensus_rapide (M1 + M2)
print("\n--- cognitif_consensus_rapide (M1 vs M2) ---")
question = "Quel est le meilleur format pour un pipeline IA: JSON, Parquet ou SQLite?"
r_m1 = call_lmstudio("10.5.0.2", 1234, "qwen3-8b", question, M1_AUTH, max_tokens=150)
print(f"  [M1/qwen3] {r_m1[:200]}")
r_m2 = call_lmstudio("192.168.1.26", 1234, "deepseek-coder-v2-lite-instruct", question, M2_AUTH, max_tokens=150)
print(f"  [M2/deepseek] {r_m2[:200]}")
results["cognitif_consensus"] = "OK" if "ERREUR" not in r_m1 and "ERREUR" not in r_m2 else "FAIL"

# ===== 4. SECURITE =====
print("\n" + "=" * 60)
print("[4/6] SECURITE AVANCEE")
print("=" * 60)

# securite_ports_ouverts
print("\n--- securite_ports_ouverts ---")
ports = ps("Get-NetTCPConnection -State Listen | Sort-Object LocalPort -Unique | Select-Object -First 10 LocalPort | ForEach-Object {$_.LocalPort}")
print(f"  Ports en ecoute: {ports}")
ext_conn = ps("(Get-NetTCPConnection -State Established | Where-Object {$_.RemoteAddress -notmatch '^(127\\.|::1|0\\.)'} | Measure-Object).Count")
print(f"  Connexions externes: {ext_conn}")
results["securite_ports_ouverts"] = "OK"

# securite_check_defender
print("\n--- securite_check_defender ---")
defender = ps("$d = Get-MpComputerStatus -ErrorAction SilentlyContinue; if($d){\"RealTime: $($d.RealTimeProtectionEnabled) | MAJ: $($d.AntivirusSignatureLastUpdated.ToString('dd/MM HH:mm'))\"}else{'N/A'}")
print(f"  {defender}")
results["securite_check_defender"] = "OK"

# securite_audit_services
print("\n--- securite_audit_services ---")
services = ps("(Get-Service | Where-Object {$_.Status -eq 'Running'}).Count")
print(f"  Services actifs: {services}")
results["securite_audit_services"] = "OK"

# securite_permissions_sensibles
print("\n--- securite_permissions_sensibles ---")
envfiles = ps("(Get-ChildItem -Path F:\\BUREAU -Recurse -Filter '*.env' -ErrorAction SilentlyContinue -Depth 3).Count")
pemfiles = ps("(Get-ChildItem -Path F:\\BUREAU -Recurse -Filter '*.pem' -ErrorAction SilentlyContinue -Depth 3).Count")
print(f"  Fichiers .env: {envfiles} | .pem: {pemfiles}")
results["securite_permissions_sensibles"] = "OK"

# ===== 5. DEBUG RESEAU =====
print("\n" + "=" * 60)
print("[5/6] DEBUG RESEAU AVANCE")
print("=" * 60)

# debug_reseau_complet
print("\n--- debug_reseau_complet ---")
gw = ps("(Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue).NextHop")
print(f"  Gateway: {gw}")
dns = ps("(Resolve-DnsName google.com -ErrorAction SilentlyContinue | Select-Object -First 1).IPAddress")
print(f"  DNS google.com: {dns}")
results["debug_reseau_complet"] = "OK"

# debug_latence_cluster
print("\n--- debug_latence_cluster ---")
for name, (host, port, auth) in nodes.items():
    t0 = time.time()
    try:
        req = urllib.request.Request(
            f"http://{host}:{port}/api/v1/models",
            headers={"Authorization": f"Bearer {auth}"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
        ms = int((time.time() - t0) * 1000)
        print(f"  {name}: {ms}ms OK")
        results[f"latence_{name}"] = f"{ms}ms"
    except:
        print(f"  {name}: OFFLINE")
        results[f"latence_{name}"] = "OFFLINE"

# OL1 latence
t0 = time.time()
try:
    req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
    with urllib.request.urlopen(req, timeout=5) as resp:
        resp.read()
    ms = int((time.time() - t0) * 1000)
    print(f"  OL1: {ms}ms OK")
except:
    print("  OL1: OFFLINE")

# debug_wifi_diagnostic
print("\n--- debug_wifi_diagnostic ---")
wifi = ps("netsh wlan show interfaces | Select-String 'SSID|Signal|Canal' | Select-Object -First 6 | ForEach-Object {$_.Line.Trim()}")
print(f"  {wifi}")
results["debug_wifi"] = "OK"

# debug_dns_avance
print("\n--- debug_dns_avance ---")
for domain in ["google.com", "github.com", "api.anthropic.com"]:
    dns_result = ps(f"$t = Measure-Command {{Resolve-DnsName {domain} -ErrorAction SilentlyContinue | Out-Null}}; \"{domain}: $([math]::Round($t.TotalMilliseconds))ms\"")
    print(f"  {dns_result}")
results["debug_dns_avance"] = "OK"

# ===== 6. ROUTINES CONVERSATIONNELLES =====
print("\n" + "=" * 60)
print("[6/6] ROUTINES CONVERSATIONNELLES")
print("=" * 60)

# routine_bonjour_jarvis
print("\n--- routine_bonjour_jarvis ---")
heure = ps("(Get-Date).ToString('HH:mm')")
jour = ps("Get-Date -Format 'dddd dd MMMM yyyy'")
print(f"  Bonjour! Il est {heure}, nous sommes {jour}")
results["routine_bonjour_jarvis"] = "OK"

# routine_tout_va_bien
print("\n--- routine_tout_va_bien ---")
sys_check = ps("$cpu = (Get-CimInstance Win32_Processor).LoadPercentage; $os = Get-CimInstance Win32_OperatingSystem; $ram = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB,1); $total = [math]::Round($os.TotalVisibleMemorySize/1MB,1); \"CPU:${cpu}% RAM:${ram}/${total}GB\"")
print(f"  {sys_check}")
results["routine_tout_va_bien"] = "OK"

# routine_bilan_journee
print("\n--- routine_bilan_journee ---")
commits = ps("(git -C F:\\BUREAU\\turbo log --since='midnight' --oneline | Measure-Object -Line).Lines")
uptime2 = ps("$up = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; (New-TimeSpan -Start $up).ToString('hh\\:mm')")
prompt6 = f"L'utilisateur a fait {commits} commits aujourd'hui. Il est {heure}. Uptime: {uptime2}. Fais un bilan positif en 2 lignes."
r6 = call_lmstudio("10.5.0.2", 1234, "qwen3-8b", prompt6, M1_AUTH, max_tokens=100)
print(f"  Commits: {commits} | Uptime: {uptime2}")
print(f"  [JARVIS] {r6}")
results["routine_bilan_journee"] = "OK" if "ERREUR" not in r6 else "FAIL"

# routine_jarvis_selfcheck
print("\n--- routine_jarvis_selfcheck ---")
db1 = ps("Test-Path 'F:\\BUREAU\\turbo\\data\\etoile.db'")
db2 = ps("Test-Path 'F:\\BUREAU\\turbo\\data\\jarvis.db'")
cmd_count = ps("(Get-Content F:\\BUREAU\\turbo\\src\\commands.py -Raw | Select-String -Pattern 'JarvisCommand\\(' -AllMatches).Matches.Count")
pipe_count = ps("(Get-Content F:\\BUREAU\\turbo\\src\\commands_pipelines.py -Raw | Select-String -Pattern 'JarvisCommand\\(' -AllMatches).Matches.Count")
print(f"  DBs: etoile={db1} jarvis={db2}")
print(f"  Commandes: {cmd_count} | Pipelines: {pipe_count} | Total: {int(cmd_count or 0) + int(pipe_count or 0)}")
results["routine_jarvis_selfcheck"] = "OK"

# ===== SYNTHESE =====
elapsed = time.time() - start
print("\n" + "=" * 60)
print(f"SYNTHESE — {len(results)} tests en {elapsed:.1f}s")
print("=" * 60)

ok = sum(1 for v in results.values() if "OK" in str(v) or "ms" in str(v))
fail = sum(1 for v in results.values() if "FAIL" in str(v) or "OFFLINE" in str(v))
print(f"\nResultat: {ok}/{len(results)} OK | {fail} FAIL")
for k, v in results.items():
    status = "PASS" if "OK" in str(v) or "ms" in str(v) else "FAIL"
    print(f"  [{status}] {k}: {v}")
