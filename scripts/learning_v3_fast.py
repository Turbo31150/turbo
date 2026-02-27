#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS Learning v3 FAST — 100 scenarios x 5 modeles = 500 requetes
FULL PARALLEL HTTP only (pas de subprocess) — resultats en streaming
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import httpx
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# ── ENDPOINTS ───────────────────────────────────────────────
MODELS = {
    "M1-qwen3": {
        "type": "openai",
        "url": "http://10.5.0.2:1234/v1/chat/completions",
        "key": "sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7",
        "model": "qwen3-8b",
        "sem": 3,
    },
    "M1-dsr1": {
        "type": "openai",
        "url": "http://10.5.0.2:1234/v1/chat/completions",
        "key": "sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7",
        "model": "deepseek-r1-0528-qwen3-8b",
        "sem": 2,
    },
    "M2-coder": {
        "type": "openai",
        "url": "http://192.168.1.26:1234/v1/chat/completions",
        "key": "sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4",
        "model": "deepseek-coder-v2-lite-instruct",
        "sem": 3,
    },
    "M3-mistral": {
        "type": "openai",
        "url": "http://192.168.1.113:1234/v1/chat/completions",
        "key": "sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux",
        "model": "mistral-7b-instruct-v0.3",
        "sem": 3,
    },
    "OL1-qwen": {
        "type": "ollama",
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "qwen3:1.7b",
        "sem": 3,
    },
}

TIMEOUT = 30

# ── SCENARIOS ───────────────────────────────────────────────
SCENARIOS = [
    {"id":1,"cat":"fichiers","cmd":"ouvre le dossier Documents","exp":"explorer"},
    {"id":2,"cat":"fichiers","cmd":"cree un dossier Projets sur le bureau","exp":"New-Item"},
    {"id":3,"cat":"fichiers","cmd":"supprime les fichiers temporaires","exp":"Remove-Item"},
    {"id":4,"cat":"fichiers","cmd":"liste les fichiers PDF sur le bureau","exp":"Get-ChildItem"},
    {"id":5,"cat":"fichiers","cmd":"copie rapport.txt dans Documents","exp":"Copy-Item"},
    {"id":6,"cat":"fichiers","cmd":"renomme ancien.txt en nouveau.txt","exp":"Rename-Item"},
    {"id":7,"cat":"fichiers","cmd":"montre l'espace disque disponible","exp":"Get-PSDrive"},
    {"id":8,"cat":"fichiers","cmd":"compresse le dossier Logs en zip","exp":"Compress-Archive"},
    {"id":9,"cat":"fichiers","cmd":"cherche les fichiers modifies aujourd'hui","exp":"Get-ChildItem"},
    {"id":10,"cat":"fichiers","cmd":"affiche la taille du dossier turbo","exp":"Measure-Object"},
    {"id":11,"cat":"fichiers","cmd":"cree un fichier texte avec du contenu","exp":"Set-Content"},
    {"id":12,"cat":"fichiers","cmd":"deplace tous les PNG dans images","exp":"Move-Item"},
    {"id":13,"cat":"fichiers","cmd":"affiche les 10 plus gros fichiers","exp":"Sort-Object"},
    {"id":14,"cat":"fichiers","cmd":"vide la corbeille","exp":"Clear-RecycleBin"},
    {"id":15,"cat":"fichiers","cmd":"ouvre config.json dans notepad","exp":"notepad"},
    {"id":16,"cat":"processus","cmd":"liste les processus gourmands en memoire","exp":"Get-Process"},
    {"id":17,"cat":"processus","cmd":"ferme Chrome","exp":"Stop-Process"},
    {"id":18,"cat":"processus","cmd":"lance le calculateur Windows","exp":"calc"},
    {"id":19,"cat":"processus","cmd":"ouvre VS Code dans turbo","exp":"code"},
    {"id":20,"cat":"processus","cmd":"verifie si Discord tourne","exp":"Get-Process"},
    {"id":21,"cat":"processus","cmd":"ouvre le gestionnaire de taches","exp":"taskmgr"},
    {"id":22,"cat":"processus","cmd":"redemarre l'explorateur Windows","exp":"explorer"},
    {"id":23,"cat":"processus","cmd":"affiche l'utilisation CPU","exp":"Get-Counter"},
    {"id":24,"cat":"processus","cmd":"lance PowerShell admin","exp":"RunAs"},
    {"id":25,"cat":"processus","cmd":"ferme toutes les fenetres Notepad","exp":"Stop-Process"},
    {"id":26,"cat":"processus","cmd":"liste les applications installees","exp":"Get-Package"},
    {"id":27,"cat":"processus","cmd":"ouvre les parametres Windows","exp":"ms-settings"},
    {"id":28,"cat":"processus","cmd":"lance un terminal Windows","exp":"wt"},
    {"id":29,"cat":"processus","cmd":"affiche le uptime du PC","exp":"LastBootUpTime"},
    {"id":30,"cat":"processus","cmd":"kill le processus PID 1234","exp":"Stop-Process"},
    {"id":31,"cat":"reseau","cmd":"affiche mon adresse IP","exp":"Get-NetIPAddress"},
    {"id":32,"cat":"reseau","cmd":"ping google.com","exp":"Test-Connection"},
    {"id":33,"cat":"reseau","cmd":"affiche les connexions reseau actives","exp":"Get-NetTCPConnection"},
    {"id":34,"cat":"reseau","cmd":"teste la vitesse de connexion","exp":"Measure"},
    {"id":35,"cat":"reseau","cmd":"affiche le nom du WiFi connecte","exp":"netsh"},
    {"id":36,"cat":"reseau","cmd":"ouvre les parametres reseau","exp":"ms-settings"},
    {"id":37,"cat":"reseau","cmd":"affiche la table de routage","exp":"Get-NetRoute"},
    {"id":38,"cat":"reseau","cmd":"scanne les ports ouverts","exp":"Test-NetConnection"},
    {"id":39,"cat":"reseau","cmd":"affiche le DNS configure","exp":"DnsClientServerAddress"},
    {"id":40,"cat":"reseau","cmd":"flush le cache DNS","exp":"Clear-DnsClientCache"},
    {"id":41,"cat":"reseau","cmd":"affiche la bande passante","exp":"NetAdapterStatistics"},
    {"id":42,"cat":"reseau","cmd":"resous github.com","exp":"Resolve-DnsName"},
    {"id":43,"cat":"reseau","cmd":"verifie port 1234 sur M1","exp":"Test-NetConnection"},
    {"id":44,"cat":"reseau","cmd":"affiche les partages reseau","exp":"Get-SmbShare"},
    {"id":45,"cat":"reseau","cmd":"desactive puis reactive WiFi","exp":"NetAdapter"},
    {"id":46,"cat":"systeme","cmd":"affiche les infos systeme","exp":"Get-ComputerInfo"},
    {"id":47,"cat":"systeme","cmd":"affiche la version Windows","exp":"OSVersion"},
    {"id":48,"cat":"systeme","cmd":"verifie les mises a jour","exp":"WindowsUpdate"},
    {"id":49,"cat":"systeme","cmd":"affiche la RAM disponible","exp":"Win32_OperatingSystem"},
    {"id":50,"cat":"systeme","cmd":"affiche la temperature GPU","exp":"nvidia-smi"},
    {"id":51,"cat":"systeme","cmd":"affiche les variables d'env","exp":"Env:"},
    {"id":52,"cat":"systeme","cmd":"ajoute un chemin au PATH","exp":"Environment"},
    {"id":53,"cat":"systeme","cmd":"planifie un redemarrage","exp":"shutdown"},
    {"id":54,"cat":"systeme","cmd":"annule le redemarrage","exp":"shutdown"},
    {"id":55,"cat":"systeme","cmd":"affiche les events recents","exp":"Get-EventLog"},
    {"id":56,"cat":"systeme","cmd":"verifie integrite fichiers","exp":"sfc"},
    {"id":57,"cat":"systeme","cmd":"affiche les pilotes","exp":"driverquery"},
    {"id":58,"cat":"systeme","cmd":"verifie sante du disque","exp":"Get-PhysicalDisk"},
    {"id":59,"cat":"systeme","cmd":"cles registre demarrage","exp":"Get-ItemProperty"},
    {"id":60,"cat":"systeme","cmd":"cree un point de restauration","exp":"Checkpoint"},
    {"id":61,"cat":"services","cmd":"liste les services actifs","exp":"Get-Service"},
    {"id":62,"cat":"services","cmd":"redemarre Windows Update","exp":"Restart-Service"},
    {"id":63,"cat":"services","cmd":"arrete le spouleur","exp":"Stop-Service"},
    {"id":64,"cat":"services","cmd":"affiche services desactives","exp":"Get-Service"},
    {"id":65,"cat":"services","cmd":"statut du pare-feu","exp":"NetFirewallProfile"},
    {"id":66,"cat":"services","cmd":"active bureau a distance","exp":"Set-ItemProperty"},
    {"id":67,"cat":"services","cmd":"affiche taches planifiees","exp":"ScheduledTask"},
    {"id":68,"cat":"services","cmd":"cree tache quotidienne","exp":"Register-ScheduledTask"},
    {"id":69,"cat":"services","cmd":"verifie Windows Defender","exp":"MpComputerStatus"},
    {"id":70,"cat":"services","cmd":"scan antivirus rapide","exp":"Start-MpScan"},
    {"id":71,"cat":"audio","cmd":"monte le volume a 80%","exp":"volume"},
    {"id":72,"cat":"audio","cmd":"coupe le son","exp":"mute"},
    {"id":73,"cat":"audio","cmd":"capture d'ecran","exp":"Screen"},
    {"id":74,"cat":"audio","cmd":"ouvre mixeur volume","exp":"sndvol"},
    {"id":75,"cat":"audio","cmd":"peripheriques audio","exp":"Audio"},
    {"id":76,"cat":"audio","cmd":"joue un son notification","exp":"SystemSounds"},
    {"id":77,"cat":"audio","cmd":"ouvre lecteur media","exp":"wmplayer"},
    {"id":78,"cat":"audio","cmd":"enregistre l'ecran 10s","exp":"ffmpeg"},
    {"id":79,"cat":"audio","cmd":"dis bonjour vocal","exp":"Speech"},
    {"id":80,"cat":"audio","cmd":"resolution d'ecran","exp":"Screen"},
    {"id":81,"cat":"affichage","cmd":"active mode sombre","exp":"AppsUseLightTheme"},
    {"id":82,"cat":"affichage","cmd":"active mode clair","exp":"AppsUseLightTheme"},
    {"id":83,"cat":"affichage","cmd":"verrouille la session","exp":"LockWorkStation"},
    {"id":84,"cat":"affichage","cmd":"minimise toutes fenetres","exp":"MinimizeAll"},
    {"id":85,"cat":"affichage","cmd":"restaure toutes fenetres","exp":"UndoMinimizeAll"},
    {"id":86,"cat":"affichage","cmd":"change le fond d'ecran","exp":"SystemParametersInfo"},
    {"id":87,"cat":"affichage","cmd":"active veilleuse","exp":"NightLight"},
    {"id":88,"cat":"affichage","cmd":"moniteurs connectes","exp":"DesktopMonitor"},
    {"id":89,"cat":"affichage","cmd":"parametres affichage","exp":"ms-settings:display"},
    {"id":90,"cat":"affichage","cmd":"clavier virtuel","exp":"osk"},
    {"id":91,"cat":"productivite","cmd":"ouvre calendrier","exp":"calendar"},
    {"id":92,"cat":"productivite","cmd":"rappel dans 30 minutes","exp":"ScheduledTask"},
    {"id":93,"cat":"productivite","cmd":"affiche date et heure","exp":"Get-Date"},
    {"id":94,"cat":"productivite","cmd":"ouvre calculatrice","exp":"calc"},
    {"id":95,"cat":"productivite","cmd":"copie texte presse-papier","exp":"Set-Clipboard"},
    {"id":96,"cat":"productivite","cmd":"contenu presse-papier","exp":"Get-Clipboard"},
    {"id":97,"cat":"productivite","cmd":"ouvre un site web","exp":"Start-Process"},
    {"id":98,"cat":"productivite","cmd":"affiche la meteo","exp":"Invoke-RestMethod"},
    {"id":99,"cat":"productivite","cmd":"eteins PC dans 5 min","exp":"shutdown"},
    {"id":100,"cat":"productivite","cmd":"annule l'extinction","exp":"shutdown"},
]

PROMPT = 'Tu es JARVIS, assistant Windows 11. Commande: "{cmd}". Genere le PowerShell:\n```powershell\n<cmd>\n```\nExplication: <1 phrase>'

# ── API ─────────────────────────────────────────────────────
async def call_api(client, model_name, cfg, prompt, sem):
    async with sem:
        t0 = time.time()
        try:
            if cfg["type"] == "openai":
                r = await client.post(cfg["url"],
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"},
                    json={"model": cfg["model"],
                          "messages": [{"role": "user", "content": "/no_think\n" + prompt}],
                          "temperature": 0.2, "max_tokens": 300, "stream": False},
                    timeout=TIMEOUT)
                content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            else:  # ollama
                r = await client.post(cfg["url"],
                    json={"model": cfg["model"],
                          "messages": [{"role": "user", "content": "/no_think\n" + prompt}],
                          "stream": False, "think": False},
                    timeout=TIMEOUT)
                content = r.json().get("message", {}).get("content", "")
            lat = round(time.time() - t0, 2)
            return {"model": model_name, "content": content, "latency": lat, "ok": bool(content.strip())}
        except Exception as e:
            return {"model": model_name, "content": str(e)[:100], "latency": round(time.time()-t0,2), "ok": False}

def score_it(resp, sc):
    if not resp["ok"]: return 0
    c = resp["content"].lower()
    s = 0
    if sc["exp"].lower() in c: s += 40
    if "```" in c: s += 20
    if any(w in c for w in ["explication","cette commande","permet de","cette"]): s += 10
    if 20 < len(c) < 1500: s += 15
    if any(w in c for w in ["powershell","start-process","get-","set-","stop-","new-","remove-"]): s += 15
    return min(s, 100)

# ── MAIN ────────────────────────────────────────────────────
async def main():
    t0 = time.time()
    print(f"=== JARVIS Learning v3 FAST — {len(SCENARIOS)}x{len(MODELS)}={len(SCENARIOS)*len(MODELS)} requetes ===", flush=True)

    sems = {name: asyncio.Semaphore(cfg["sem"]) for name, cfg in MODELS.items()}
    completed = 0
    total = len(SCENARIOS) * len(MODELS)
    stats = defaultdict(lambda: {"total":0,"score_sum":0,"lat_sum":0,"errors":0,"wins":0})
    results_map = defaultdict(list)

    async with httpx.AsyncClient() as client:
        # Create all tasks
        tasks = {}
        for i, sc in enumerate(SCENARIOS):
            prompt = PROMPT.format(cmd=sc["cmd"])
            for mname, cfg in MODELS.items():
                task = asyncio.create_task(call_api(client, mname, cfg, prompt, sems[mname]))
                tasks[task] = (i, mname)

        # Process as completed — streaming results!
        for coro in asyncio.as_completed(tasks.keys()):
            resp = await coro
            sc_idx, mname = tasks[coro._coro.__self__] if hasattr(coro, '_coro') else (0, "?")
            completed += 1

            # Find the task in our map
            for t, (idx, mn) in tasks.items():
                if t.done() and not hasattr(t, '_counted'):
                    try:
                        r = t.result()
                        sc = SCENARIOS[idx]
                        s = score_it(r, sc)
                        r["score"] = s
                        results_map[idx].append(r)
                        stats[mn]["total"] += 1
                        stats[mn]["score_sum"] += s
                        stats[mn]["lat_sum"] += r["latency"]
                        if not r["ok"]: stats[mn]["errors"] += 1
                        t._counted = True
                    except:
                        pass

            # Print progress every 5 completions
            if completed % 25 == 0 or completed == total:
                elapsed = round(time.time() - t0, 1)
                rate = completed / max(elapsed, 0.1)
                print(f"  [{completed:3d}/{total}] {elapsed}s elapsed | {rate:.1f} req/s", flush=True)

    # ── DETERMINE WINNERS ───────────────────────────────────
    full_results = []
    for i, sc in enumerate(SCENARIOS):
        resps = results_map.get(i, [])
        best = max(resps, key=lambda r: r.get("score", 0)) if resps else {"model": "?", "score": 0}
        if best.get("model"):
            stats[best["model"]]["wins"] += 1
        scores = " ".join(f"{r['model']}:{r.get('score',0)}" for r in sorted(resps, key=lambda x: -x.get("score",0)))
        cat = f"[{sc['cat'][:5]:>5}]"
        print(f"[{i+1:3d}] {cat} {sc['cmd'][:40]:<40} -> {best.get('model','?')} ({best.get('score',0)}) | {scores}", flush=True)
        full_results.append({"id": sc["id"], "cmd": sc["cmd"], "cat": sc["cat"],
                            "winner": best.get("model",""), "best_score": best.get("score",0)})

    elapsed = round(time.time() - t0, 1)

    # ── FINAL ───────────────────────────────────────────────
    print("\n" + "="*80, flush=True)
    print(f"RESULTATS — {elapsed}s total — {total/max(elapsed,0.1):.1f} req/s", flush=True)
    print("="*80, flush=True)

    for name, st in sorted(stats.items(), key=lambda x: x[1]["score_sum"], reverse=True):
        avg = st["score_sum"] / max(st["total"], 1)
        lat = st["lat_sum"] / max(st["total"], 1)
        print(f"  {name:12s} | Score: {avg:5.1f}/100 | Wins: {st['wins']:3d}/100 | Lat: {lat:4.1f}s | Err: {st['errors']}", flush=True)

    cats = sorted(set(sc["cat"] for sc in SCENARIOS))
    print("\n-- Categories --", flush=True)
    for cat in cats:
        cr = [r for r in full_results if r["cat"] == cat]
        wins = defaultdict(int)
        for r in cr:
            if r["winner"]: wins[r["winner"]] += 1
        w = ", ".join(f"{k}:{v}" for k, v in sorted(wins.items(), key=lambda x: -x[1]))
        avg = sum(r["best_score"] for r in cr) / max(len(cr), 1)
        print(f"  {cat:12s} | {len(cr):2d} tests | Best: {avg:4.0f} | {w}", flush=True)

    # Save
    report = {"ts": datetime.now().isoformat(), "elapsed": elapsed, "stats": dict(stats), "results": full_results}
    p = Path("F:/BUREAU/turbo/data") / f"learning_v3_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved: {p}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
