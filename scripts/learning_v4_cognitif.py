#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JARVIS Learning v4 COGNITIF — Scenarios conversationnels naturels + pipelines multi-etapes
L'utilisateur parle comme dans la vraie vie, JARVIS comprend l'intention et agit.
100 scenarios x 5 modeles = 500 requetes FULL PARALLEL
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
        "model": "qwen3-8b", "sem": 3,
    },
    "M1-dsr1": {
        "type": "openai",
        "url": "http://10.5.0.2:1234/v1/chat/completions",
        "key": "sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7",
        "model": "deepseek-r1-0528-qwen3-8b", "sem": 2,
    },
    "M2-coder": {
        "type": "openai",
        "url": "http://192.168.1.26:1234/v1/chat/completions",
        "key": "sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4",
        "model": "deepseek-coder-v2-lite-instruct", "sem": 3,
    },
    "M3-mistral": {
        "type": "openai",
        "url": "http://192.168.1.113:1234/v1/chat/completions",
        "key": "sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux",
        "model": "mistral-7b-instruct-v0.3", "sem": 3,
    },
    "OL1-qwen": {
        "type": "ollama",
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "qwen3:1.7b", "sem": 3,
    },
}

TIMEOUT = 35

# ── SYSTEM PROMPT JARVIS ────────────────────────────────────
SYSTEM_PROMPT = """Tu es JARVIS, assistant IA personnel sur Windows 11.
Tu controles un cluster de 3 machines IA (M1/M2/M3) + Ollama + Gemini.
Tu as acces a PowerShell, au systeme, au reseau, au trading, a la domotique.

REGLES:
1. Comprends l'INTENTION derriere le langage naturel conversationnel
2. Decompose en ETAPES si necessaire (pipeline multi-actions)
3. Genere le code PowerShell executable pour CHAQUE etape
4. Reponds en francais, concis, avec le format:

INTENTION: <ce que l'utilisateur veut vraiment>
PIPELINE:
```powershell
# Etape 1: <description>
<commande1>
# Etape 2: <description>
<commande2>
```
EXPLICATION: <resume en 1-2 phrases>
COGNITIF: <analyse/recommandation si pertinent>"""

# ── 100 SCENARIOS CONVERSATIONNELS ──────────────────────────
SCENARIOS = [
    # ── ROUTINE QUOTIDIENNE (1-15) ──
    {"id":1, "cat":"routine", "cmd":"Jarvis, bonjour! C'est quoi le programme aujourd'hui?",
     "keywords":["Get-Date","Get-ScheduledTask","agenda","calendar","programme"],
     "intent":"salutation + briefing matinal"},
    {"id":2, "cat":"routine", "cmd":"Prepare mon espace de travail",
     "keywords":["Start-Process","code","terminal","explorer","workspace"],
     "intent":"ouvrir IDE + terminal + dossier projet"},
    {"id":3, "cat":"routine", "cmd":"J'arrive au bureau, lance tout ce qu'il faut",
     "keywords":["Start-Process","code","chrome","terminal","outlook"],
     "intent":"pipeline demarrage journee"},
    {"id":4, "cat":"routine", "cmd":"Fais le menage sur mon PC",
     "keywords":["Remove-Item","TEMP","Clear-RecycleBin","cleanmgr","nettoy"],
     "intent":"nettoyage fichiers temp + corbeille + cache"},
    {"id":5, "cat":"routine", "cmd":"Je pars, ferme tout proprement",
     "keywords":["Stop-Process","shutdown","save","ferme","kill"],
     "intent":"sauvegarder + fermer apps + verrouiller"},
    {"id":6, "cat":"routine", "cmd":"C'est l'heure de la pause, mets de la musique",
     "keywords":["Start-Process","spotify","music","wmplayer","media"],
     "intent":"lancer lecteur musique"},
    {"id":7, "cat":"routine", "cmd":"Reveil! Lance mon setup de dev",
     "keywords":["Start-Process","code","terminal","npm","dev","server"],
     "intent":"IDE + terminal + serveur dev"},
    {"id":8, "cat":"routine", "cmd":"Bonne nuit Jarvis, eteins tout dans 10 minutes",
     "keywords":["shutdown","timer","sleep","10","minutes"],
     "intent":"extinction programmee"},
    {"id":9, "cat":"routine", "cmd":"Fais une sauvegarde de mes trucs importants",
     "keywords":["Copy-Item","Compress-Archive","backup","sauvegard"],
     "intent":"backup fichiers critiques"},
    {"id":10, "cat":"routine", "cmd":"Rappelle moi dans une heure de faire la mise a jour",
     "keywords":["ScheduledTask","Register","reminder","rappel","heure"],
     "intent":"creer rappel planifie"},
    {"id":11, "cat":"routine", "cmd":"Verifie que tout tourne bien ce matin",
     "keywords":["Get-Service","Get-Process","health","check","status"],
     "intent":"health check systeme + services"},
    {"id":12, "cat":"routine", "cmd":"Active le mode focus, pas de distractions",
     "keywords":["Stop-Process","notification","focus","Discord","Teams","desactiv"],
     "intent":"fermer apps sociales + activer mode concentration"},
    {"id":13, "cat":"routine", "cmd":"Je reviens dans 5 min, verrouille",
     "keywords":["LockWorkStation","verrouill","lock","rundll32"],
     "intent":"verrouiller session"},
    {"id":14, "cat":"routine", "cmd":"Ouvre mes mails et mon agenda",
     "keywords":["Start-Process","outlook","mail","calendar","agenda"],
     "intent":"ouvrir client mail + calendrier"},
    {"id":15, "cat":"routine", "cmd":"C'est la fin de journee, fais le bilan",
     "keywords":["Get-EventLog","Get-Process","uptime","bilan","resume"],
     "intent":"resume activite du jour"},

    # ── TROUBLESHOOTING & DEBUG (16-30) ──
    {"id":16, "cat":"debug", "cmd":"Mon PC rame, c'est quoi le probleme?",
     "keywords":["Get-Process","CPU","Memory","WorkingSet","Sort","diagnostic"],
     "intent":"diagnostic performance + identifier processus gourmand"},
    {"id":17, "cat":"debug", "cmd":"Internet marche plus, aide moi",
     "keywords":["Test-Connection","ping","DNS","ipconfig","netsh","reseau"],
     "intent":"diagnostic connectivite reseau"},
    {"id":18, "cat":"debug", "cmd":"Y'a un truc qui bouffe toute la RAM",
     "keywords":["Get-Process","Sort","WorkingSet","Memory","MB","RAM"],
     "intent":"identifier processus memoire + option kill"},
    {"id":19, "cat":"debug", "cmd":"Chrome a plante encore, debloque la situation",
     "keywords":["Stop-Process","chrome","Start-Process","kill","restart"],
     "intent":"kill chrome + relancer proprement"},
    {"id":20, "cat":"debug", "cmd":"Le disque est presque plein, fais de la place",
     "keywords":["Get-PSDrive","Remove-Item","TEMP","WinSxS","cleanmgr","espace"],
     "intent":"diagnostic espace + nettoyage agressif"},
    {"id":21, "cat":"debug", "cmd":"Le WiFi se deconnecte tout le temps",
     "keywords":["netsh","wlan","adapter","Disable","Enable","WiFi","diagnostic"],
     "intent":"diagnostic WiFi + reset adaptateur"},
    {"id":22, "cat":"debug", "cmd":"Un programme refuse de se fermer",
     "keywords":["Stop-Process","Force","taskkill","PID","programme"],
     "intent":"force kill processus bloque"},
    {"id":23, "cat":"debug", "cmd":"Mon ecran scintille c'est bizarre",
     "keywords":["driver","display","GPU","nvidia","resolution","ecran"],
     "intent":"diagnostic affichage + driver GPU"},
    {"id":24, "cat":"debug", "cmd":"Windows Update est bloque depuis ce matin",
     "keywords":["Restart-Service","wuauserv","WindowsUpdate","bits","update"],
     "intent":"reset service Windows Update"},
    {"id":25, "cat":"debug", "cmd":"J'ai plus de son, aide",
     "keywords":["Get-Service","Audiosrv","audio","Restart","son","speaker"],
     "intent":"diagnostic audio + redemarrer service"},
    {"id":26, "cat":"debug", "cmd":"Le cluster M2 repond plus, verifie",
     "keywords":["Test-NetConnection","192.168.1.26","1234","ping","cluster"],
     "intent":"health check machine distante M2"},
    {"id":27, "cat":"debug", "cmd":"Pourquoi le ventilateur tourne a fond?",
     "keywords":["nvidia-smi","temperature","GPU","CPU","Get-Counter","thermal"],
     "intent":"check temperatures + processus CPU/GPU"},
    {"id":28, "cat":"debug", "cmd":"Y'a un processus suspect qui tourne",
     "keywords":["Get-Process","Path","CommandLine","suspect","inconnu"],
     "intent":"lister processus + identifier inconnus"},
    {"id":29, "cat":"debug", "cmd":"Mon VPN se connecte pas",
     "keywords":["Get-VpnConnection","rasdial","VPN","netsh","connect"],
     "intent":"diagnostic VPN + tentative reconnexion"},
    {"id":30, "cat":"debug", "cmd":"LM Studio sur M1 repond pas, relance",
     "keywords":["Test-NetConnection","10.5.0.2","1234","curl","LM Studio"],
     "intent":"check + restart LM Studio distant"},

    # ── PILOTAGE SYSTEME AVANCE (31-45) ──
    {"id":31, "cat":"systeme", "cmd":"Montre moi l'etat de sante de tout le systeme",
     "keywords":["Get-ComputerInfo","Get-PhysicalDisk","RAM","CPU","health"],
     "intent":"dashboard systeme complet"},
    {"id":32, "cat":"systeme", "cmd":"Optimise les performances du PC",
     "keywords":["Stop-Service","Disable","startup","defrag","optimize"],
     "intent":"desactiver services inutiles + optimiser"},
    {"id":33, "cat":"systeme", "cmd":"Mets a jour tout ce qui peut l'etre",
     "keywords":["WindowsUpdate","winget","upgrade","update","choco"],
     "intent":"MAJ Windows + applications"},
    {"id":34, "cat":"systeme", "cmd":"Scanne le systeme pour des virus",
     "keywords":["Start-MpScan","Defender","antivirus","scan","securite"],
     "intent":"scan antivirus complet"},
    {"id":35, "cat":"systeme", "cmd":"Cree un point de restauration au cas ou",
     "keywords":["Checkpoint-Computer","restore","restauration","point"],
     "intent":"point de restauration systeme"},
    {"id":36, "cat":"systeme", "cmd":"Active le mode sombre, j'en ai marre du blanc",
     "keywords":["AppsUseLightTheme","Personalize","dark","sombre","theme"],
     "intent":"basculer en mode sombre"},
    {"id":37, "cat":"systeme", "cmd":"Quelles apps se lancent au demarrage? Desactive les inutiles",
     "keywords":["Get-ItemProperty","Run","startup","demarrage","Disable"],
     "intent":"audit + nettoyage demarrage"},
    {"id":38, "cat":"systeme", "cmd":"Combien de RAM et de CPU j'utilise la?",
     "keywords":["Get-Counter","Processor","Memory","RAM","CPU","utilisation"],
     "intent":"metriques temps reel CPU/RAM"},
    {"id":39, "cat":"systeme", "cmd":"Configure le pare-feu pour bloquer les connexions entrantes",
     "keywords":["NetFirewallProfile","Set-NetFirewallRule","block","pare-feu"],
     "intent":"renforcer securite pare-feu"},
    {"id":40, "cat":"systeme", "cmd":"Planifie un redemarrage cette nuit a 3h",
     "keywords":["shutdown","ScheduledTask","03:00","reboot","nuit"],
     "intent":"redemarrage planifie nocturne"},
    {"id":41, "cat":"systeme", "cmd":"Montre les derniers crashs ou erreurs systeme",
     "keywords":["Get-EventLog","Error","Critical","crash","erreur","System"],
     "intent":"analyse logs erreurs"},
    {"id":42, "cat":"systeme", "cmd":"Verifie que les disques sont en bonne sante",
     "keywords":["Get-PhysicalDisk","Health","SMART","chkdsk","disque"],
     "intent":"diagnostic sante disques"},
    {"id":43, "cat":"systeme", "cmd":"Installe Python 3.13 et Node.js",
     "keywords":["winget","install","python","node","choco","setup"],
     "intent":"installation logiciels via package manager"},
    {"id":44, "cat":"systeme", "cmd":"Bloque l'acces a YouTube pendant 2 heures",
     "keywords":["hosts","youtube","block","netsh","firewall","bloquer"],
     "intent":"bloquer site via hosts/firewall"},
    {"id":45, "cat":"systeme", "cmd":"Partage mon dossier Projets sur le reseau",
     "keywords":["New-SmbShare","share","partage","reseau","Projets"],
     "intent":"creer partage reseau"},

    # ── CLUSTER IA & JARVIS (46-60) ──
    {"id":46, "cat":"cluster", "cmd":"Verifie que toutes les machines du cluster sont en ligne",
     "keywords":["Test-NetConnection","10.5.0.2","192.168.1.26","192.168.1.113","ping","cluster"],
     "intent":"health check 3 machines"},
    {"id":47, "cat":"cluster", "cmd":"C'est quoi la temperature GPU sur chaque machine?",
     "keywords":["nvidia-smi","temperature","GPU","M1","M2","M3"],
     "intent":"monitoring thermique cluster"},
    {"id":48, "cat":"cluster", "cmd":"Charge le modele qwen3-30b sur M1",
     "keywords":["curl","load","model","qwen3-30b","LM Studio","10.5.0.2"],
     "intent":"charger modele IA specifique"},
    {"id":49, "cat":"cluster", "cmd":"Compare les performances de M1 et M2 sur une question",
     "keywords":["curl","benchmark","M1","M2","compare","performance","latence"],
     "intent":"benchmark comparatif 2 noeuds"},
    {"id":50, "cat":"cluster", "cmd":"Combien de VRAM il reste sur M1?",
     "keywords":["nvidia-smi","memory","VRAM","free","GPU","M1"],
     "intent":"check VRAM disponible"},
    {"id":51, "cat":"cluster", "cmd":"Decharge les modeles inutilises pour liberer de la VRAM",
     "keywords":["curl","unload","model","VRAM","free","memory"],
     "intent":"liberer VRAM en dechargeant modeles"},
    {"id":52, "cat":"cluster", "cmd":"Lance un consensus sur la meilleure strategie de trading",
     "keywords":["curl","consensus","M1","M2","M3","trading","vote"],
     "intent":"consensus multi-agent trading"},
    {"id":53, "cat":"cluster", "cmd":"Quel modele est le plus rapide en ce moment?",
     "keywords":["benchmark","latence","tok/s","vitesse","rapide","modele"],
     "intent":"benchmark latence temps reel"},
    {"id":54, "cat":"cluster", "cmd":"Redemarre Ollama, il a l'air bloque",
     "keywords":["Restart-Service","ollama","Stop","Start","service"],
     "intent":"restart service Ollama"},
    {"id":55, "cat":"cluster", "cmd":"Fait tourner les 3 machines sur un probleme de code",
     "keywords":["curl","M1","M2","M3","code","parallele","gather"],
     "intent":"dispatch code review 3 noeuds"},
    {"id":56, "cat":"cluster", "cmd":"Sauvegarde la config de tous les modeles charges",
     "keywords":["curl","models","config","save","json","backup"],
     "intent":"export config cluster"},
    {"id":57, "cat":"cluster", "cmd":"Montre moi le dashboard du cluster en temps reel",
     "keywords":["Start-Process","dashboard","8080","http","monitoring"],
     "intent":"ouvrir dashboard web"},
    {"id":58, "cat":"cluster", "cmd":"Active le failover, si M1 tombe M2 prend le relais",
     "keywords":["failover","fallback","M1","M2","health","check","auto"],
     "intent":"configurer basculement automatique"},
    {"id":59, "cat":"cluster", "cmd":"Quelle est la charge totale du cluster?",
     "keywords":["GPU","CPU","utilisation","charge","cluster","total"],
     "intent":"metriques agregees cluster"},
    {"id":60, "cat":"cluster", "cmd":"Envoie cette question aux 5 IA et compare les reponses",
     "keywords":["curl","M1","M2","M3","Ollama","Gemini","compare","parallel"],
     "intent":"query broadcast + comparaison"},

    # ── COGNITIF & ANALYSE (61-75) ──
    {"id":61, "cat":"cognitif", "cmd":"Analyse les logs d'erreur et dis moi ce qui cloche",
     "keywords":["Get-EventLog","Error","analyse","diagnostic","pattern","probleme"],
     "intent":"analyse intelligente des logs"},
    {"id":62, "cat":"cognitif", "cmd":"Resume ce qui s'est passe sur le PC depuis ce matin",
     "keywords":["Get-EventLog","today","resume","activite","journal","matin"],
     "intent":"synthese activite journaliere"},
    {"id":63, "cat":"cognitif", "cmd":"Quels fichiers j'ai modifie cette semaine?",
     "keywords":["Get-ChildItem","LastWriteTime","recent","modifie","semaine"],
     "intent":"historique modifications recentes"},
    {"id":64, "cat":"cognitif", "cmd":"Dis moi si mon PC est en securite",
     "keywords":["Defender","Firewall","Update","securite","audit","check"],
     "intent":"audit securite rapide"},
    {"id":65, "cat":"cognitif", "cmd":"Recommande moi des optimisations pour ce PC",
     "keywords":["optimize","startup","service","RAM","SSD","recommand"],
     "intent":"recommendations intelligentes"},
    {"id":66, "cat":"cognitif", "cmd":"C'est quoi ce processus bizarre que je vois?",
     "keywords":["Get-Process","information","CommandLine","Path","suspect"],
     "intent":"analyse processus inconnu"},
    {"id":67, "cat":"cognitif", "cmd":"Explique moi pourquoi le PC est lent aujourd'hui",
     "keywords":["Get-Process","CPU","Memory","IO","analyse","lent","cause"],
     "intent":"diagnostic intelligent performance"},
    {"id":68, "cat":"cognitif", "cmd":"Prevois combien d'espace disque il me reste pour 30 jours",
     "keywords":["Get-PSDrive","croissance","prediction","espace","30 jours"],
     "intent":"prediction stockage"},
    {"id":69, "cat":"cognitif", "cmd":"Y'a t'il des mises a jour critiques a faire?",
     "keywords":["WindowsUpdate","critical","securite","update","important"],
     "intent":"audit MAJ critiques"},
    {"id":70, "cat":"cognitif", "cmd":"Fais un rapport de sante complet du cluster",
     "keywords":["health","rapport","cluster","M1","M2","M3","GPU","status"],
     "intent":"rapport sante cluster complet"},
    {"id":71, "cat":"cognitif", "cmd":"Compare mon utilisation CPU d'aujourd'hui vs hier",
     "keywords":["Get-Counter","CPU","compare","historique","tendance"],
     "intent":"analyse tendance performance"},
    {"id":72, "cat":"cognitif", "cmd":"Quels services consomment le plus de ressources?",
     "keywords":["Get-Service","Get-Process","service","ressource","consomm"],
     "intent":"audit services par consommation"},
    {"id":73, "cat":"cognitif", "cmd":"Donne moi un score de sante global de 0 a 100",
     "keywords":["score","health","sante","CPU","RAM","disk","global","note"],
     "intent":"score sante synthetique"},
    {"id":74, "cat":"cognitif", "cmd":"Detecte si quelqu'un a essaye de se connecter a mon PC",
     "keywords":["Get-EventLog","Security","logon","failed","intrusion","4625"],
     "intent":"analyse tentatives connexion"},
    {"id":75, "cat":"cognitif", "cmd":"Suggere les meilleurs moments pour faire les mises a jour",
     "keywords":["usage","pattern","CPU","bas","nuit","maintenance","schedule"],
     "intent":"planification intelligente maintenance"},

    # ── PRODUCTIVITE & WORKFLOW (76-90) ──
    {"id":76, "cat":"workflow", "cmd":"Ouvre mon projet turbo et lance les tests",
     "keywords":["Start-Process","code","turbo","test","pytest","npm"],
     "intent":"ouvrir projet + executer tests"},
    {"id":77, "cat":"workflow", "cmd":"Deploie la derniere version sur GitHub",
     "keywords":["git","commit","push","deploy","github"],
     "intent":"pipeline git commit + push"},
    {"id":78, "cat":"workflow", "cmd":"Cherche dans mon code ou j'utilise asyncio",
     "keywords":["Get-ChildItem","Select-String","grep","asyncio","recherche"],
     "intent":"recherche code dans projet"},
    {"id":79, "cat":"workflow", "cmd":"Lance le serveur de dev et ouvre le navigateur",
     "keywords":["Start-Process","npm","python","server","localhost","chrome"],
     "intent":"demarrer serveur + ouvrir browser"},
    {"id":80, "cat":"workflow", "cmd":"Fais un git status et montre moi les changements",
     "keywords":["git","status","diff","log","changement","modif"],
     "intent":"etat git du projet"},
    {"id":81, "cat":"workflow", "cmd":"Cree une branche pour la nouvelle feature",
     "keywords":["git","checkout","branch","feature","nouvelle"],
     "intent":"creer branche git"},
    {"id":82, "cat":"workflow", "cmd":"Compile le projet et montre les erreurs",
     "keywords":["npm","build","compile","error","tsc","erreur"],
     "intent":"build + diagnostic erreurs"},
    {"id":83, "cat":"workflow", "cmd":"Sauvegarde mon travail, commit et push",
     "keywords":["git","add","commit","push","save","sauvegard"],
     "intent":"pipeline git save complet"},
    {"id":84, "cat":"workflow", "cmd":"Montre moi les TODO dans le code",
     "keywords":["Select-String","TODO","FIXME","HACK","grep","tache"],
     "intent":"chercher annotations TODO"},
    {"id":85, "cat":"workflow", "cmd":"Installe les dependances du projet",
     "keywords":["npm","install","pip","uv","requirements","dependance"],
     "intent":"installer deps projet"},
    {"id":86, "cat":"workflow", "cmd":"Lance Docker et demarre mes containers",
     "keywords":["docker","compose","up","container","start"],
     "intent":"demarrer environnement Docker"},
    {"id":87, "cat":"workflow", "cmd":"Formate tout le code du projet proprement",
     "keywords":["prettier","black","format","lint","eslint","ruff"],
     "intent":"formatage code automatique"},
    {"id":88, "cat":"workflow", "cmd":"Montre les derniers commits du projet",
     "keywords":["git","log","oneline","commit","dernier","recent"],
     "intent":"historique git recent"},
    {"id":89, "cat":"workflow", "cmd":"Compare la branche actuelle avec main",
     "keywords":["git","diff","main","compare","branche","merge"],
     "intent":"diff branche vs main"},
    {"id":90, "cat":"workflow", "cmd":"Ouvre la doc du projet dans le navigateur",
     "keywords":["Start-Process","readme","doc","localhost","browser"],
     "intent":"ouvrir documentation"},

    # ── DIVERTISSEMENT & PERSO (91-100) ──
    {"id":91, "cat":"perso", "cmd":"Jarvis, quelle heure il est a Tokyo?",
     "keywords":["Get-Date","TimeZone","Tokyo","UTC","heure","timezone"],
     "intent":"convertir fuseau horaire"},
    {"id":92, "cat":"perso", "cmd":"Dis moi un truc interessant sur l'IA",
     "keywords":["IA","intelligence","artificielle","fun fact","info","apprend"],
     "intent":"conversation knowledge (cognitif pur)"},
    {"id":93, "cat":"perso", "cmd":"Mets un fond d'ecran cool",
     "keywords":["wallpaper","fond","ecran","SystemParametersInfo","image"],
     "intent":"changer fond ecran"},
    {"id":94, "cat":"perso", "cmd":"C'est quoi la meteo dehors?",
     "keywords":["Invoke-RestMethod","wttr","meteo","weather","temperature"],
     "intent":"recuperer meteo en ligne"},
    {"id":95, "cat":"perso", "cmd":"Calcule combien ca fait 15% de 2450 euros",
     "keywords":["calcul","15","2450","math","resultat","pourcentage"],
     "intent":"calcul mathematique rapide"},
    {"id":96, "cat":"perso", "cmd":"Chronometre 5 minutes et previens moi",
     "keywords":["Start-Sleep","timer","chrono","5","minutes","notification"],
     "intent":"timer avec notification"},
    {"id":97, "cat":"perso", "cmd":"Traduis 'hello world' en japonais",
     "keywords":["traduction","japonais","hello","world","translate"],
     "intent":"traduction texte (cognitif)"},
    {"id":98, "cat":"perso", "cmd":"Lis moi les dernieres news tech",
     "keywords":["Invoke-RestMethod","news","RSS","tech","actualite"],
     "intent":"recuperer actualites tech"},
    {"id":99, "cat":"perso", "cmd":"Ecris un script Python qui trie une liste",
     "keywords":["python","script","sort","tri","liste","code"],
     "intent":"generation de code a la demande"},
    {"id":100, "cat":"perso", "cmd":"Merci Jarvis, t'es le meilleur!",
     "keywords":["merci","plaisir","disponible","remerciement"],
     "intent":"reponse empathique + statut"},
]

# ── API CALL ────────────────────────────────────────────────
async def call_api(client, model_name, cfg, user_msg, sem):
    async with sem:
        t0 = time.time()
        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg}
            ]
            if cfg["type"] == "openai":
                r = await client.post(cfg["url"],
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"},
                    json={"model": cfg["model"], "messages": messages,
                          "temperature": 0.3, "max_tokens": 600, "stream": False},
                    timeout=TIMEOUT)
                content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                r = await client.post(cfg["url"],
                    json={"model": cfg["model"], "messages": messages,
                          "stream": False, "think": False},
                    timeout=TIMEOUT)
                content = r.json().get("message", {}).get("content", "")
            lat = round(time.time() - t0, 2)
            return {"model": model_name, "content": content, "latency": lat, "ok": bool(content.strip())}
        except Exception as e:
            return {"model": model_name, "content": str(e)[:100], "latency": round(time.time()-t0,2), "ok": False}

# ── SCORING COGNITIF ────────────────────────────────────────
def score_response(resp, sc):
    """Score multi-criteres: intention, pipeline, keywords, format, cognitif"""
    if not resp["ok"] or not resp["content"]:
        return 0
    c = resp["content"].lower()
    s = 0

    # 1. Keywords match (max 30)
    kw_matches = sum(1 for kw in sc["keywords"] if kw.lower() in c)
    s += min(kw_matches * 6, 30)

    # 2. Format structure (max 25)
    if "intention" in c or "intent" in c: s += 5
    if "pipeline" in c or "etape" in c or "step" in c: s += 5
    if "```" in c: s += 10  # code block present
    if "explication" in c or "explanation" in c or "explica" in c: s += 5

    # 3. PowerShell content (max 20)
    ps_indicators = ["get-", "set-", "start-process", "stop-", "new-", "remove-",
                     "invoke-", "test-", "restart-", "powershell", "$env:", "$_"]
    ps_count = sum(1 for ind in ps_indicators if ind in c)
    s += min(ps_count * 4, 20)

    # 4. Cognitive quality (max 15)
    cognitive_words = ["recommand", "attention", "important", "conseil", "suggest",
                       "analyse", "diagnostic", "optimis", "securit", "risque",
                       "amelior", "cognitif", "note:", "remarque"]
    cog_count = sum(1 for w in cognitive_words if w in c)
    s += min(cog_count * 5, 15)

    # 5. Length & quality (max 10)
    if 100 < len(c) < 3000: s += 5
    if len(c) > 200: s += 3  # detailed response
    if c.count("```") >= 2: s += 2  # has code blocks

    return min(s, 100)

# ── MAIN ────────────────────────────────────────────────────
async def main():
    t0 = time.time()
    total = len(SCENARIOS) * len(MODELS)
    print(f"=== JARVIS Learning v4 COGNITIF ===", flush=True)
    print(f"100 scenarios conversationnels x {len(MODELS)} modeles = {total} requetes", flush=True)
    print(f"System prompt: {len(SYSTEM_PROMPT)} chars | Timeout: {TIMEOUT}s", flush=True)
    print(f"Debut: {datetime.now().strftime('%H:%M:%S')}", flush=True)
    print("="*80, flush=True)

    sems = {name: asyncio.Semaphore(cfg["sem"]) for name, cfg in MODELS.items()}
    stats = defaultdict(lambda: {"total":0,"score_sum":0,"lat_sum":0,"errors":0,"wins":0})
    results_map = defaultdict(list)
    completed = [0]

    async with httpx.AsyncClient() as client:
        # Create all tasks
        all_tasks = {}
        for i, sc in enumerate(SCENARIOS):
            for mname, cfg in MODELS.items():
                task = asyncio.create_task(call_api(client, mname, cfg, sc["cmd"], sems[mname]))
                all_tasks[id(task)] = (i, mname, task)

        # Gather with progress
        task_list = [t for _, _, t in all_tasks.values()]

        for fut in asyncio.as_completed(task_list):
            resp = await fut
            completed[0] += 1

            # Find which scenario/model this was
            tid = id(fut)
            # We need to match by checking all tasks
            for task_id, (sc_idx, mn, task) in all_tasks.items():
                if task.done() and not hasattr(task, '_scored'):
                    try:
                        r = task.result()
                        sc = SCENARIOS[sc_idx]
                        s = score_response(r, sc)
                        r["score"] = s
                        results_map[sc_idx].append(r)
                        stats[mn]["total"] += 1
                        stats[mn]["score_sum"] += s
                        stats[mn]["lat_sum"] += r["latency"]
                        if not r["ok"]: stats[mn]["errors"] += 1
                        task._scored = True
                    except:
                        task._scored = True

            if completed[0] % 50 == 0 or completed[0] == total:
                el = round(time.time() - t0, 1)
                rate = completed[0] / max(el, 0.1)
                print(f"  [{completed[0]:3d}/{total}] {el}s | {rate:.1f} req/s", flush=True)

    # ── DETERMINE WINNERS & DISPLAY ─────────────────────────
    full_results = []
    for i, sc in enumerate(SCENARIOS):
        resps = results_map.get(i, [])
        best = max(resps, key=lambda r: r.get("score", 0)) if resps else {"model":"?","score":0}
        if best.get("model","?") != "?":
            stats[best["model"]]["wins"] += 1

        scores = " ".join(f"{r['model']}:{r.get('score',0)}" for r in sorted(resps, key=lambda x:-x.get("score",0)))
        cat = f"[{sc['cat'][:5]:>5}]"
        print(f"[{i+1:3d}] {cat} {sc['cmd'][:45]:<45} -> {best.get('model','?')} ({best.get('score',0)}) | {scores}", flush=True)
        full_results.append({
            "id": sc["id"], "cmd": sc["cmd"], "cat": sc["cat"],
            "intent": sc["intent"], "winner": best.get("model",""),
            "best_score": best.get("score",0)
        })

    elapsed = round(time.time() - t0, 1)

    # ── FINAL REPORT ────────────────────────────────────────
    print("\n" + "="*80, flush=True)
    print(f"RESULTATS v4 COGNITIF — {elapsed}s total — {total/max(elapsed,0.1):.1f} req/s", flush=True)
    print("="*80, flush=True)

    print("\n-- CLASSEMENT --", flush=True)
    for name, st in sorted(stats.items(), key=lambda x: x[1]["score_sum"], reverse=True):
        avg = st["score_sum"] / max(st["total"], 1)
        lat = st["lat_sum"] / max(st["total"], 1)
        print(f"  {name:12s} | Score: {avg:5.1f}/100 | Wins: {st['wins']:3d}/100 | Lat: {lat:4.1f}s | Err: {st['errors']}", flush=True)

    cats = sorted(set(sc["cat"] for sc in SCENARIOS))
    print("\n-- CATEGORIES --", flush=True)
    for cat in cats:
        cr = [r for r in full_results if r["cat"] == cat]
        wins = defaultdict(int)
        for r in cr:
            if r["winner"]: wins[r["winner"]] += 1
        w = ", ".join(f"{k}:{v}" for k, v in sorted(wins.items(), key=lambda x: -x[1]))
        avg = sum(r["best_score"] for r in cr) / max(len(cr), 1)
        print(f"  {cat:12s} | {len(cr):2d} tests | Best: {avg:4.0f} | {w}", flush=True)

    # Top 5 best / worst scenarios
    print("\n-- TOP 5 MEILLEURS SCENARIOS --", flush=True)
    for r in sorted(full_results, key=lambda x: -x["best_score"])[:5]:
        print(f"  [{r['best_score']:3d}] {r['cmd'][:50]} ({r['winner']})", flush=True)
    print("\n-- TOP 5 PIRES SCENARIOS --", flush=True)
    for r in sorted(full_results, key=lambda x: x["best_score"])[:5]:
        print(f"  [{r['best_score']:3d}] {r['cmd'][:50]} ({r['winner']})", flush=True)

    # Save
    report = {
        "version": "v4_cognitif",
        "timestamp": datetime.now().isoformat(),
        "elapsed": elapsed,
        "total_requests": total,
        "system_prompt_len": len(SYSTEM_PROMPT),
        "stats": dict(stats),
        "results": full_results
    }
    p = Path("F:/BUREAU/turbo/data") / f"learning_v4_cognitif_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nRapport: {p}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
