#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS Learning Cycles v2 TURBO — 100 scenarios x 6 modeles = 600 requetes
FULLY CONCURRENT: tous les modeles bombardes en parallele non-stop
M1 (qwen3-8b + deepseek-r1) + M2 (deepseek-coder) + M3 (mistral) + OL1 (qwen3:1.7b) + Gemini CLI
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import httpx
import asyncio
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# ── CONFIG ──────────────────────────────────────────────────
LMSTUDIO_MODELS = {
    "M1-qwen3": {
        "url": "http://10.5.0.2:1234/v1/chat/completions",
        "key": "sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7",
        "model": "qwen3-8b"
    },
    "M1-deepseek-r1": {
        "url": "http://10.5.0.2:1234/v1/chat/completions",
        "key": "sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7",
        "model": "deepseek-r1-0528-qwen3-8b"
    },
    "M2-coder": {
        "url": "http://192.168.1.26:1234/v1/chat/completions",
        "key": "sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4",
        "model": "deepseek-coder-v2-lite-instruct"
    },
    "M3-mistral": {
        "url": "http://192.168.1.113:1234/v1/chat/completions",
        "key": "sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux",
        "model": "mistral-7b-instruct-v0.3"
    },
}

OL1_URL = "http://127.0.0.1:11434/api/chat"

# Semaphores par machine pour saturer sans crash
SEM_M1 = asyncio.Semaphore(4)   # M1: 2 modeles charges, 2 req/modele
SEM_M2 = asyncio.Semaphore(2)   # M2: 1 modele
SEM_M3 = asyncio.Semaphore(2)   # M3: 1 modele
SEM_OL1 = asyncio.Semaphore(2)  # OL1: local petit modele
SEM_GEMINI = asyncio.Semaphore(2)  # Gemini: rate limit

SEM_MAP = {
    "M1-qwen3": SEM_M1, "M1-deepseek-r1": SEM_M1,
    "M2-coder": SEM_M2, "M3-mistral": SEM_M3,
    "OL1-qwen3": SEM_OL1, "GEMINI": SEM_GEMINI
}

TIMEOUT = 30

# ── 100 SCENARIOS (repris de v1) ────────────────────────────
SCENARIOS = [
    {"id":1,"cat":"fichiers","cmd":"ouvre le dossier Documents","expected":"explorer","ps":"Start-Process explorer $env:USERPROFILE\\Documents"},
    {"id":2,"cat":"fichiers","cmd":"cree un dossier Projets sur le bureau","expected":"New-Item","ps":"New-Item -Path $env:USERPROFILE\\Desktop\\Projets -ItemType Directory"},
    {"id":3,"cat":"fichiers","cmd":"supprime les fichiers temporaires","expected":"Remove-Item","ps":"Remove-Item $env:TEMP\\* -Recurse -Force"},
    {"id":4,"cat":"fichiers","cmd":"liste les fichiers PDF sur le bureau","expected":"Get-ChildItem","ps":"Get-ChildItem $env:USERPROFILE\\Desktop -Filter *.pdf"},
    {"id":5,"cat":"fichiers","cmd":"copie le fichier rapport.txt dans Documents","expected":"Copy-Item","ps":"Copy-Item rapport.txt $env:USERPROFILE\\Documents\\"},
    {"id":6,"cat":"fichiers","cmd":"renomme le fichier ancien.txt en nouveau.txt","expected":"Rename-Item","ps":"Rename-Item ancien.txt nouveau.txt"},
    {"id":7,"cat":"fichiers","cmd":"montre l'espace disque disponible","expected":"Get-PSDrive","ps":"Get-PSDrive -PSProvider FileSystem"},
    {"id":8,"cat":"fichiers","cmd":"compresse le dossier Logs en zip","expected":"Compress-Archive","ps":"Compress-Archive -Path .\\Logs -DestinationPath .\\Logs.zip"},
    {"id":9,"cat":"fichiers","cmd":"cherche les fichiers modifies aujourd'hui","expected":"Get-ChildItem","ps":"Get-ChildItem -Recurse | Where {$_.LastWriteTime -ge (Get-Date).Date}"},
    {"id":10,"cat":"fichiers","cmd":"affiche la taille du dossier turbo","expected":"Measure-Object","ps":"(Get-ChildItem F:\\BUREAU\\turbo -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB"},
    {"id":11,"cat":"fichiers","cmd":"cree un fichier texte avec du contenu","expected":"Set-Content","ps":"Set-Content -Path note.txt -Value 'Hello JARVIS'"},
    {"id":12,"cat":"fichiers","cmd":"deplace tous les PNG dans un dossier images","expected":"Move-Item","ps":"Move-Item *.png .\\images\\ -Force"},
    {"id":13,"cat":"fichiers","cmd":"affiche les 10 plus gros fichiers du disque","expected":"Sort-Object","ps":"Get-ChildItem C:\\ -Recurse -File | Sort-Object Length -Desc | Select -First 10"},
    {"id":14,"cat":"fichiers","cmd":"vide la corbeille","expected":"Clear-RecycleBin","ps":"Clear-RecycleBin -Force"},
    {"id":15,"cat":"fichiers","cmd":"ouvre le fichier config.json dans notepad","expected":"notepad","ps":"Start-Process notepad config.json"},
    {"id":16,"cat":"processus","cmd":"liste les processus qui consomment le plus de memoire","expected":"Get-Process","ps":"Get-Process | Sort WorkingSet64 -Desc | Select -First 10"},
    {"id":17,"cat":"processus","cmd":"ferme Chrome","expected":"Stop-Process","ps":"Stop-Process -Name chrome -Force"},
    {"id":18,"cat":"processus","cmd":"lance le calculateur Windows","expected":"calc","ps":"Start-Process calc"},
    {"id":19,"cat":"processus","cmd":"ouvre VS Code dans le dossier turbo","expected":"code","ps":"Start-Process code F:\\BUREAU\\turbo"},
    {"id":20,"cat":"processus","cmd":"verifie si Discord est en cours d'execution","expected":"Get-Process","ps":"Get-Process discord -ErrorAction SilentlyContinue"},
    {"id":21,"cat":"processus","cmd":"ouvre le gestionnaire de taches","expected":"taskmgr","ps":"Start-Process taskmgr"},
    {"id":22,"cat":"processus","cmd":"redemarre l'explorateur Windows","expected":"explorer","ps":"Stop-Process -Name explorer -Force; Start-Process explorer"},
    {"id":23,"cat":"processus","cmd":"affiche l'utilisation CPU actuelle","expected":"Get-Counter","ps":"(Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples.CookedValue"},
    {"id":24,"cat":"processus","cmd":"lance PowerShell en tant qu'administrateur","expected":"RunAs","ps":"Start-Process powershell -Verb RunAs"},
    {"id":25,"cat":"processus","cmd":"ferme toutes les fenetres de Notepad","expected":"Stop-Process","ps":"Stop-Process -Name notepad -Force"},
    {"id":26,"cat":"processus","cmd":"liste les applications installees","expected":"Get-Package","ps":"Get-Package | Select Name, Version"},
    {"id":27,"cat":"processus","cmd":"ouvre les parametres Windows","expected":"ms-settings","ps":"Start-Process ms-settings:"},
    {"id":28,"cat":"processus","cmd":"lance un terminal Windows","expected":"wt","ps":"Start-Process wt"},
    {"id":29,"cat":"processus","cmd":"affiche le temps de fonctionnement du PC","expected":"uptime","ps":"(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime"},
    {"id":30,"cat":"processus","cmd":"kill le processus avec PID 1234","expected":"Stop-Process","ps":"Stop-Process -Id 1234 -Force"},
    {"id":31,"cat":"reseau","cmd":"affiche mon adresse IP","expected":"Get-NetIPAddress","ps":"Get-NetIPAddress -AddressFamily IPv4"},
    {"id":32,"cat":"reseau","cmd":"ping google.com","expected":"Test-Connection","ps":"Test-Connection google.com -Count 4"},
    {"id":33,"cat":"reseau","cmd":"affiche les connexions reseau actives","expected":"Get-NetTCPConnection","ps":"Get-NetTCPConnection -State Established"},
    {"id":34,"cat":"reseau","cmd":"verifie la vitesse de connexion","expected":"Measure","ps":"Measure-Command { Invoke-WebRequest 'https://speed.cloudflare.com' }"},
    {"id":35,"cat":"reseau","cmd":"affiche le nom du reseau WiFi connecte","expected":"netsh","ps":"netsh wlan show interfaces | Select-String SSID"},
    {"id":36,"cat":"reseau","cmd":"ouvre les parametres reseau","expected":"ms-settings","ps":"Start-Process ms-settings:network"},
    {"id":37,"cat":"reseau","cmd":"affiche la table de routage","expected":"Get-NetRoute","ps":"Get-NetRoute"},
    {"id":38,"cat":"reseau","cmd":"scanne les ports ouverts sur localhost","expected":"Test-NetConnection","ps":"Test-NetConnection 127.0.0.1 -Port 1234"},
    {"id":39,"cat":"reseau","cmd":"affiche le DNS configure","expected":"Get-DnsClientServerAddress","ps":"Get-DnsClientServerAddress -AddressFamily IPv4"},
    {"id":40,"cat":"reseau","cmd":"flush le cache DNS","expected":"Clear-DnsClientCache","ps":"Clear-DnsClientCache"},
    {"id":41,"cat":"reseau","cmd":"affiche la bande passante utilisee","expected":"Get-NetAdapterStatistics","ps":"Get-NetAdapterStatistics"},
    {"id":42,"cat":"reseau","cmd":"resous le nom de domaine github.com","expected":"Resolve-DnsName","ps":"Resolve-DnsName github.com"},
    {"id":43,"cat":"reseau","cmd":"verifie si le port 1234 est ouvert sur M1","expected":"Test-NetConnection","ps":"Test-NetConnection 10.5.0.2 -Port 1234"},
    {"id":44,"cat":"reseau","cmd":"affiche les partages reseau","expected":"Get-SmbShare","ps":"Get-SmbShare"},
    {"id":45,"cat":"reseau","cmd":"desactive puis reactive le WiFi","expected":"Disable-NetAdapter","ps":"Disable-NetAdapter -Name Wi-Fi -Confirm:$false; Enable-NetAdapter -Name Wi-Fi"},
    {"id":46,"cat":"systeme","cmd":"affiche les infos systeme","expected":"Get-ComputerInfo","ps":"Get-ComputerInfo | Select OsName, OsVersion"},
    {"id":47,"cat":"systeme","cmd":"affiche la version de Windows","expected":"OSVersion","ps":"[System.Environment]::OSVersion.VersionString"},
    {"id":48,"cat":"systeme","cmd":"verifie les mises a jour Windows","expected":"WindowsUpdate","ps":"Get-WindowsUpdate"},
    {"id":49,"cat":"systeme","cmd":"affiche la RAM disponible","expected":"Get-CimInstance","ps":"Get-CimInstance Win32_OperatingSystem | Select FreePhysicalMemory, TotalVisibleMemorySize"},
    {"id":50,"cat":"systeme","cmd":"affiche la temperature GPU","expected":"nvidia-smi","ps":"nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader"},
    {"id":51,"cat":"systeme","cmd":"affiche les variables d'environnement","expected":"Env:","ps":"Get-ChildItem Env: | Sort Name"},
    {"id":52,"cat":"systeme","cmd":"ajoute un chemin au PATH","expected":"Environment","ps":"[Environment]::SetEnvironmentVariable('Path', $env:Path+';C:\\New', 'User')"},
    {"id":53,"cat":"systeme","cmd":"planifie un redemarrage dans 1 heure","expected":"shutdown","ps":"shutdown /r /t 3600"},
    {"id":54,"cat":"systeme","cmd":"annule le redemarrage planifie","expected":"shutdown /a","ps":"shutdown /a"},
    {"id":55,"cat":"systeme","cmd":"affiche les evenements systeme recents","expected":"Get-EventLog","ps":"Get-EventLog -LogName System -Newest 10"},
    {"id":56,"cat":"systeme","cmd":"verifie l'integrite des fichiers systeme","expected":"sfc","ps":"sfc /scannow"},
    {"id":57,"cat":"systeme","cmd":"affiche les pilotes installes","expected":"driverquery","ps":"driverquery /FO CSV"},
    {"id":58,"cat":"systeme","cmd":"verifie la sante du disque","expected":"Get-PhysicalDisk","ps":"Get-PhysicalDisk | Select FriendlyName, HealthStatus"},
    {"id":59,"cat":"systeme","cmd":"affiche les cles de registre de demarrage","expected":"Get-ItemProperty","ps":"Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run'"},
    {"id":60,"cat":"systeme","cmd":"cree un point de restauration systeme","expected":"Checkpoint-Computer","ps":"Checkpoint-Computer -Description 'JARVIS Backup'"},
    {"id":61,"cat":"services","cmd":"liste les services en cours d'execution","expected":"Get-Service","ps":"Get-Service | Where Status -eq Running"},
    {"id":62,"cat":"services","cmd":"redemarre le service Windows Update","expected":"Restart-Service","ps":"Restart-Service wuauserv -Force"},
    {"id":63,"cat":"services","cmd":"arrete le service spouleur d'impression","expected":"Stop-Service","ps":"Stop-Service Spooler -Force"},
    {"id":64,"cat":"services","cmd":"affiche les services desactives","expected":"Get-Service","ps":"Get-Service | Where StartType -eq Disabled"},
    {"id":65,"cat":"services","cmd":"verifie le statut du pare-feu","expected":"Get-NetFirewallProfile","ps":"Get-NetFirewallProfile | Select Name, Enabled"},
    {"id":66,"cat":"services","cmd":"active le bureau a distance","expected":"Set-ItemProperty","ps":"Set-ItemProperty 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server' -Name fDenyTSConnections -Value 0"},
    {"id":67,"cat":"services","cmd":"affiche les taches planifiees","expected":"Get-ScheduledTask","ps":"Get-ScheduledTask | Where State -eq Ready"},
    {"id":68,"cat":"services","cmd":"cree une tache planifiee quotidienne","expected":"Register-ScheduledTask","ps":"Register-ScheduledTask -TaskName 'JarvisDaily'"},
    {"id":69,"cat":"services","cmd":"verifie l'antivirus Windows Defender","expected":"Get-MpComputerStatus","ps":"Get-MpComputerStatus"},
    {"id":70,"cat":"services","cmd":"lance un scan antivirus rapide","expected":"Start-MpScan","ps":"Start-MpScan -ScanType QuickScan"},
    {"id":71,"cat":"audio","cmd":"monte le volume a 80%","expected":"volume","ps":"(New-Object -ComObject WScript.Shell).SendKeys([char]175)"},
    {"id":72,"cat":"audio","cmd":"coupe le son","expected":"mute","ps":"(New-Object -ComObject WScript.Shell).SendKeys([char]173)"},
    {"id":73,"cat":"audio","cmd":"prends une capture d'ecran","expected":"screenshot","ps":"[System.Windows.Forms.Screen]::PrimaryScreen"},
    {"id":74,"cat":"audio","cmd":"ouvre le mixeur de volume","expected":"sndvol","ps":"Start-Process sndvol"},
    {"id":75,"cat":"audio","cmd":"affiche les peripheriques audio","expected":"AudioEndpoint","ps":"Get-PnpDevice -Class AudioEndpoint"},
    {"id":76,"cat":"audio","cmd":"joue un son de notification","expected":"SystemSounds","ps":"[System.Media.SystemSounds]::Exclamation.Play()"},
    {"id":77,"cat":"audio","cmd":"ouvre le lecteur Windows Media","expected":"wmplayer","ps":"Start-Process wmplayer"},
    {"id":78,"cat":"audio","cmd":"enregistre l'ecran pendant 10 secondes","expected":"ffmpeg","ps":"ffmpeg -f gdigrab -framerate 30 -t 10 -i desktop"},
    {"id":79,"cat":"audio","cmd":"dis bonjour avec la synthese vocale","expected":"Speech","ps":"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('Bonjour')"},
    {"id":80,"cat":"audio","cmd":"affiche la resolution d'ecran","expected":"Screen","ps":"[System.Windows.Forms.Screen]::PrimaryScreen.Bounds"},
    {"id":81,"cat":"affichage","cmd":"active le mode sombre","expected":"AppsUseLightTheme","ps":"Set-ItemProperty 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name AppsUseLightTheme -Value 0"},
    {"id":82,"cat":"affichage","cmd":"active le mode clair","expected":"AppsUseLightTheme","ps":"Set-ItemProperty 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name AppsUseLightTheme -Value 1"},
    {"id":83,"cat":"affichage","cmd":"verrouille la session","expected":"LockWorkStation","ps":"rundll32.exe user32.dll,LockWorkStation"},
    {"id":84,"cat":"affichage","cmd":"minimise toutes les fenetres","expected":"MinimizeAll","ps":"(New-Object -ComObject Shell.Application).MinimizeAll()"},
    {"id":85,"cat":"affichage","cmd":"restaure toutes les fenetres","expected":"UndoMinimizeAll","ps":"(New-Object -ComObject Shell.Application).UndoMinimizeAll()"},
    {"id":86,"cat":"affichage","cmd":"change le fond d'ecran","expected":"SystemParametersInfo","ps":"[Wallpaper]::SystemParametersInfo(20, 0, 'wallpaper.jpg', 3)"},
    {"id":87,"cat":"affichage","cmd":"active la veilleuse night light","expected":"NightLight","ps":"Start-Process ms-settings:nightlight"},
    {"id":88,"cat":"affichage","cmd":"affiche les moniteurs connectes","expected":"DesktopMonitor","ps":"Get-CimInstance Win32_DesktopMonitor"},
    {"id":89,"cat":"affichage","cmd":"ouvre les parametres d'affichage","expected":"ms-settings:display","ps":"Start-Process ms-settings:display"},
    {"id":90,"cat":"affichage","cmd":"active le clavier virtuel","expected":"osk","ps":"Start-Process osk"},
    {"id":91,"cat":"productivite","cmd":"ouvre le calendrier","expected":"outlookcal","ps":"Start-Process outlookcal:"},
    {"id":92,"cat":"productivite","cmd":"cree un rappel dans 30 minutes","expected":"ScheduledTask","ps":"Register-ScheduledTask -TaskName 'JarvisReminder'"},
    {"id":93,"cat":"productivite","cmd":"affiche la date et l'heure","expected":"Get-Date","ps":"Get-Date -Format 'dddd dd MMMM yyyy HH:mm:ss'"},
    {"id":94,"cat":"productivite","cmd":"ouvre la calculatrice Windows","expected":"calc","ps":"Start-Process calc"},
    {"id":95,"cat":"productivite","cmd":"copie du texte dans le presse-papier","expected":"Set-Clipboard","ps":"Set-Clipboard 'Texte copie'"},
    {"id":96,"cat":"productivite","cmd":"affiche le contenu du presse-papier","expected":"Get-Clipboard","ps":"Get-Clipboard"},
    {"id":97,"cat":"productivite","cmd":"ouvre un site web","expected":"Start-Process","ps":"Start-Process 'https://github.com'"},
    {"id":98,"cat":"productivite","cmd":"affiche la meteo","expected":"Invoke-RestMethod","ps":"Invoke-RestMethod 'https://wttr.in/Paris?format=3'"},
    {"id":99,"cat":"productivite","cmd":"eteins le PC dans 5 minutes","expected":"shutdown","ps":"shutdown /s /t 300"},
    {"id":100,"cat":"productivite","cmd":"annule l'extinction","expected":"shutdown /a","ps":"shutdown /a"},
]

PROMPT_TEMPLATE = """Tu es JARVIS, assistant IA pour Windows 11. L'utilisateur dit: "{cmd}"
Genere la commande PowerShell correspondante. Reponds UNIQUEMENT avec:
```powershell
<commande>
```
Explication: <explication courte>"""

# ── API CALLS ───────────────────────────────────────────────
async def call_lmstudio(client, name, cfg, prompt, sem):
    async with sem:
        t0 = time.time()
        try:
            r = await client.post(cfg["url"],
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"},
                json={"model": cfg["model"], "messages": [{"role": "user", "content": "/no_think\n" + prompt}],
                      "temperature": 0.2, "max_tokens": 384, "stream": False},
                timeout=TIMEOUT)
            d = r.json()
            content = d.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"model": name, "content": content, "latency": round(time.time()-t0, 2), "ok": bool(content)}
        except Exception as e:
            return {"model": name, "content": str(e)[:150], "latency": round(time.time()-t0, 2), "ok": False}

async def call_ollama(client, prompt, sem):
    async with sem:
        t0 = time.time()
        try:
            r = await client.post(OL1_URL,
                json={"model": "qwen3:1.7b", "messages": [{"role": "user", "content": "/no_think\n" + prompt}],
                      "stream": False, "think": False},
                timeout=TIMEOUT)
            d = r.json()
            content = d.get("message", {}).get("content", "")
            return {"model": "OL1-qwen3", "content": content, "latency": round(time.time()-t0, 2), "ok": bool(content)}
        except Exception as e:
            return {"model": "OL1-qwen3", "content": str(e)[:150], "latency": round(time.time()-t0, 2), "ok": False}

async def call_gemini(prompt, sem):
    async with sem:
        t0 = time.time()
        try:
            proc = await asyncio.create_subprocess_exec(
                "node", "F:/BUREAU/turbo/gemini-proxy.js", prompt,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
            content = stdout.decode("utf-8", errors="replace").strip()
            return {"model": "GEMINI", "content": content, "latency": round(time.time()-t0, 2), "ok": bool(content)}
        except Exception as e:
            return {"model": "GEMINI", "content": str(e)[:150], "latency": round(time.time()-t0, 2), "ok": False}

# ── SCORING ─────────────────────────────────────────────────
def score(resp, scenario):
    if not resp["ok"] or not resp["content"]:
        return 0
    c = resp["content"].lower()
    s = 0
    if scenario["expected"].lower() in c: s += 40
    if "```powershell" in c or "```ps" in c or "```\n" in c: s += 20
    if "explication" in c or "explanation" in c or "cette commande" in c: s += 10
    if 30 < len(c) < 2000: s += 15
    parts = scenario["ps"].lower().split()[:3]
    s += min(sum(1 for p in parts if p in c) * 5, 15)
    return min(s, 100)

# ── MAIN ────────────────────────────────────────────────────
async def run():
    print(f"=== JARVIS Learning v2 TURBO ===", flush=True)
    print(f"100 scenarios x 6 modeles = 600 requetes FULL PARALLEL", flush=True)
    print(f"Debut: {datetime.now().strftime('%H:%M:%S')}", flush=True)
    print("="*80, flush=True)

    t_start = time.time()
    all_tasks = []
    task_meta = []  # (scenario_idx, model_name)

    async with httpx.AsyncClient() as client:
        # Create ALL tasks at once — full parallel bombardment
        for i, sc in enumerate(SCENARIOS):
            prompt = PROMPT_TEMPLATE.format(cmd=sc["cmd"])

            # LM Studio models (M1, M2, M3)
            for name, cfg in LMSTUDIO_MODELS.items():
                sem = SEM_MAP[name]
                all_tasks.append(call_lmstudio(client, name, cfg, prompt, sem))
                task_meta.append((i, name))

            # OL1 Ollama
            all_tasks.append(call_ollama(client, prompt, SEM_OL1))
            task_meta.append((i, "OL1-qwen3"))

            # Gemini CLI
            all_tasks.append(call_gemini(prompt, SEM_GEMINI))
            task_meta.append((i, "GEMINI"))

        print(f"Lancement de {len(all_tasks)} requetes en parallele...", flush=True)

        # Fire all at once!
        results_raw = await asyncio.gather(*all_tasks, return_exceptions=True)

    # ── ASSEMBLE RESULTS ────────────────────────────────────
    results_by_scenario = defaultdict(list)
    for (sc_idx, model_name), result in zip(task_meta, results_raw):
        if isinstance(result, Exception):
            result = {"model": model_name, "content": str(result)[:150], "latency": 0, "ok": False}
        results_by_scenario[sc_idx].append(result)

    # ── SCORE & DISPLAY ─────────────────────────────────────
    stats = defaultdict(lambda: {"total": 0, "score_sum": 0, "latency_sum": 0, "errors": 0, "wins": 0})
    full_results = []

    for i, sc in enumerate(SCENARIOS):
        responses = results_by_scenario[i]
        best_score = 0
        best_model = ""

        for resp in responses:
            s = score(resp, sc)
            resp["score"] = s
            mn = resp["model"]
            stats[mn]["total"] += 1
            stats[mn]["score_sum"] += s
            stats[mn]["latency_sum"] += resp["latency"]
            if not resp["ok"]: stats[mn]["errors"] += 1
            if s > best_score:
                best_score = s
                best_model = mn

        if best_model:
            stats[best_model]["wins"] += 1

        scores_str = " ".join(f"{r['model']}:{r['score']}" for r in sorted(responses, key=lambda x: -x["score"]))
        cat = f"[{sc['cat'][:5]:>5}]"
        print(f"[{i+1:3d}/100] {cat} {sc['cmd'][:42]:<42} -> {best_model} ({best_score}) | {scores_str}", flush=True)

        full_results.append({
            "id": sc["id"], "cmd": sc["cmd"], "cat": sc["cat"],
            "winner": best_model, "best_score": best_score,
            "responses": [{"model": r["model"], "score": r["score"], "latency": r["latency"], "ok": r["ok"]} for r in responses]
        })

    elapsed = round(time.time() - t_start, 1)

    # ── FINAL REPORT ────────────────────────────────────────
    print("\n" + "="*80, flush=True)
    print(f"RESULTATS FINAUX — 100 CYCLES x 6 MODELES — {elapsed}s total", flush=True)
    print("="*80, flush=True)

    print("\n-- CLASSEMENT GENERAL --", flush=True)
    for name, st in sorted(stats.items(), key=lambda x: x[1]["score_sum"], reverse=True):
        avg = st["score_sum"] / max(st["total"], 1)
        lat = st["latency_sum"] / max(st["total"], 1)
        print(f"  {name:18s} | Score: {avg:5.1f}/100 | Wins: {st['wins']:3d} | Latence: {lat:5.2f}s | Erreurs: {st['errors']}/{st['total']}", flush=True)

    print("\n-- PAR CATEGORIE --", flush=True)
    categories = sorted(set(sc["cat"] for sc in SCENARIOS))
    for cat in categories:
        cat_res = [r for r in full_results if r["cat"] == cat]
        winners = defaultdict(int)
        for r in cat_res:
            if r["winner"]: winners[r["winner"]] += 1
        w_str = ", ".join(f"{k}:{v}" for k, v in sorted(winners.items(), key=lambda x: -x[1]))
        avg_best = sum(r["best_score"] for r in cat_res) / max(len(cat_res), 1)
        print(f"  {cat:15s} | {len(cat_res):2d} tests | Best moy: {avg_best:5.1f} | {w_str}", flush=True)

    # ── SAVE ────────────────────────────────────────────────
    report = {
        "timestamp": datetime.now().isoformat(),
        "elapsed_seconds": elapsed,
        "total_requests": len(all_tasks),
        "stats": dict(stats),
        "results": full_results
    }
    outpath = Path("F:/BUREAU/turbo/data") / f"learning_v2_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    outpath.parent.mkdir(exist_ok=True)
    outpath.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nRapport: {outpath}", flush=True)
    print(f"Termine: {datetime.now().strftime('%H:%M:%S')} ({elapsed}s)", flush=True)

if __name__ == "__main__":
    asyncio.run(run())
