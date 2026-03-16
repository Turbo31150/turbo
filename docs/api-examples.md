# JARVIS API — Exemples d'utilisation (curl & Python)

> Documentation des endpoints API REST de JARVIS.
> > Base URL : `http://localhost:8080`
> >
> > ---
> >
> > ## 1. Health Check — État du système
> >
> > ### curl
> >
> > ```bash
> > curl -s http://localhost:8080/api/linux/health | python3 -m json.tool
> > ```
> >
> > ### Python
> >
> > ```python
> > import requests
> >
> > r = requests.get("http://localhost:8080/api/linux/health")
> > data = r.json()
> > print(f"Status: {data['status']}")
> > print(f"Uptime: {data['uptime']}")
> > print(f"CPU: {data['cpu_percent']}%")
> > print(f"RAM: {data['ram_percent']}%")
> > ```
> >
> > ### Réponse attendue
> >
> > ```json
> > {
> >   "status": "ok",
> >   "uptime": "4d 12h 33m",
> >   "cpu_percent": 23.5,
> >   "ram_percent": 61.2,
> >   "gpu_count": 6,
> >   "services_active": 17,
> >   "timestamp": "2026-03-16T12:00:00"
> > }
> > ```
> >
> > ---
> >
> > ## 2. Skills — Lister les 203 compétences
> >
> > ### curl
> >
> > ```bash
> > curl -s http://localhost:8080/api/linux/skills | python3 -m json.tool
> > ```
> >
> > ### Python
> >
> > ```python
> > import requests
> >
> > r = requests.get("http://localhost:8080/api/linux/skills")
> > skills = r.json()["skills"]
> > print(f"Nombre de skills: {len(skills)}")
> > for s in skills[:5]:
> >     print(f"  - {s['name']} ({s['category']})")
> > ```
> >
> > ### Réponse attendue
> >
> > ```json
> > {
> >   "count": 203,
> >   "skills": [
> >     {
> >       "name": "rapport_systeme",
> >       "category": "system",
> >       "triggers": ["rapport système", "status machine"],
> >       "steps": 4
> >     }
> >   ]
> > }
> > ```
> >
> > ---
> >
> > ## 3. Cluster Status — État du cluster GPU
> >
> > ### curl
> >
> > ```bash
> > curl -s http://localhost:8080/api/linux/cluster/status | python3 -m json.tool
> > ```
> >
> > ### Python
> >
> > ```python
> > import requests
> >
> > r = requests.get("http://localhost:8080/api/linux/cluster/status")
> > cluster = r.json()
> > for node in cluster["nodes"]:
> >     status = "ON" if node["online"] else "OFF"
> >     print(f"{node['name']}: {status} — {node['model']} ({node['tok_per_sec']} tok/s)")
> > ```
> >
> > ### Réponse attendue
> >
> > ```json
> > {
> >   "nodes": [
> >     {"name": "M1", "online": true, "model": "qwen3-8b", "tok_per_sec": 46, "role": "Champion local"},
> >     {"name": "M2", "online": true, "model": "deepseek-r1-qwen3-8b", "tok_per_sec": 44, "role": "Reasoning"},
> >     {"name": "M3", "online": true, "model": "deepseek-r1-qwen3-8b", "tok_per_sec": null, "role": "Reasoning fallback"},
> >     {"name": "OL1", "online": true, "model": "gpt-oss:120b", "tok_per_sec": 51, "role": "Champion cloud"}
> >   ],
> >   "total_gpu": 10,
> >   "total_vram_gb": 78
> > }
> > ```
> >
> > ---
> >
> > ## 4. Commandes vocales
> >
> > ### curl
> >
> > ```bash
> > # Toutes les commandes
> > curl -s http://localhost:8080/api/linux/voice/commands | python3 -m json.tool
> >
> > # Filtrer par catégorie
> > curl -s "http://localhost:8080/api/linux/voice/commands?category=system" | python3 -m json.tool
> > ```
> >
> > ### Python
> >
> > ```python
> > import requests
> >
> > r = requests.get("http://localhost:8080/api/linux/voice/commands", params={"category": "system"})
> > cmds = r.json()["commands"]
> > print(f"Commandes système: {len(cmds)}")
> > for c in cmds[:3]:
> >     print(f"  '{c['trigger']}' -> {c['action']}")
> > ```
> >
> > ### Réponse attendue
> >
> > ```json
> > {
> >   "total": 1218,
> >   "category": "system",
> >   "commands": [
> >     {"trigger": "rapport système", "action": "system_report", "confirm": false},
> >     {"trigger": "redémarre le service", "action": "restart_service", "confirm": true}
> >   ]
> > }
> > ```
> >
> > ---
> >
> > ## 5. Brain Status — État du cerveau IA
> >
> > ### curl
> >
> > ```bash
> > curl -s http://localhost:8080/api/linux/brain/status | python3 -m json.tool
> > ```
> >
> > ### Python
> >
> > ```python
> > import requests
> >
> > r = requests.get("http://localhost:8080/api/linux/brain/status")
> > brain = r.json()
> > print(f"Skills: {brain['skills_count']}")
> > print(f"Dominos: {brain['dominos_count']}")
> > print(f"Improve cycles: {brain['improve_cycles']}")
> > print(f"Last cycle: {brain['last_cycle']}")
> > ```
> >
> > ### Réponse attendue
> >
> > ```json
> > {
> >   "skills_count": 203,
> >   "dominos_count": 494,
> >   "improve_cycles": 847,
> >   "last_cycle": "2026-03-16T11:30:00",
> >   "voice_corrections": 398,
> >   "learned_actions": 156
> > }
> > ```
> >
> > ---
> >
> > ## 6. Dominos — Liste des pipelines
> >
> > ### curl
> >
> > ```bash
> > curl -s http://localhost:8080/api/linux/dominos | python3 -m json.tool
> > ```
> >
> > ### Python
> >
> > ```python
> > import requests
> >
> > r = requests.get("http://localhost:8080/api/linux/dominos")
> > dominos = r.json()["dominos"]
> > print(f"Total dominos: {len(dominos)}")
> > for d in dominos[:3]:
> >     print(f"  [{d['category']}] {d['name']} — {len(d['steps'])} steps")
> > ```
> >
> > ---
> >
> > ## 7. Exécuter un domino
> >
> > ### curl
> >
> > ```bash
> > curl -X POST http://localhost:8080/api/linux/dominos/execute \
> >   -H "Content-Type: application/json" \
> >   -d '{"domino": "morning-routine"}'
> > ```
> >
> > ### Python
> >
> > ```python
> > import requests
> >
> > r = requests.post(
> >     "http://localhost:8080/api/linux/dominos/execute",
> >     json={"domino": "morning-routine"}
> > )
> > result = r.json()
> > print(f"Status: {result['status']}")
> > print(f"Steps executed: {result['steps_executed']}")
> > ```
> >
> > ---
> >
> > ## 8. Profils utilisateur
> >
> > ### curl
> >
> > ```bash
> > # Lister les profils
> > curl -s http://localhost:8080/api/linux/profiles | python3 -m json.tool
> >
> > # Activer un profil
> > curl -X POST http://localhost:8080/api/linux/profiles/activate \
> >   -H "Content-Type: application/json" \
> >   -d '{"profile": "dev"}'
> > ```
> >
> > ### Python
> >
> > ```python
> > import requests
> >
> > # Lister
> > r = requests.get("http://localhost:8080/api/linux/profiles")
> > for p in r.json()["profiles"]:
> >     active = " (actif)" if p["active"] else ""
> >     print(f"  {p['name']}{active}")
> >
> > # Activer
> > r = requests.post(
> >     "http://localhost:8080/api/linux/profiles/activate",
> >     json={"profile": "trading"}
> > )
> > print(r.json()["message"])
> > ```
> >
> > ---
> >
> > ## 9. Notifications
> >
> > ### curl
> >
> > ```bash
> > curl -s http://localhost:8080/api/linux/notifications | python3 -m json.tool
> > ```
> >
> > ### Python
> >
> > ```python
> > import requests
> >
> > r = requests.get("http://localhost:8080/api/linux/notifications")
> > notifs = r.json()["notifications"]
> > for n in notifs[-5:]:
> >     print(f"[{n['level']}] {n['message']} ({n['timestamp']})")
> > ```
> >
> > ---
> >
> > ## 10. Rapport quotidien
> >
> > ### curl
> >
> > ```bash
> > curl -s http://localhost:8080/api/linux/report/today | python3 -m json.tool
> > ```
> >
> > ### Python
> >
> > ```python
> > import requests
> >
> > r = requests.get("http://localhost:8080/api/linux/report/today")
> > report = r.json()
> > print(f"Date: {report['date']}")
> > print(f"Services actifs: {report['services_active']}")
> > print(f"Commandes vocales (24h): {report['voice_commands_24h']}")
> > print(f"Recommandations: {len(report['recommendations'])}")
> > for rec in report["recommendations"]:
> >     print(f"  - {rec}")
> > ```
> >
> > ---
> >
> > ## Script complet de test
> >
> > ```python
> > #!/usr/bin/env python3
> > """Test rapide de tous les endpoints JARVIS."""
> > import requests
> > import sys
> >
> > BASE = "http://localhost:8080"
> >
> > endpoints = [
> >     ("GET", "/api/linux/health"),
> >     ("GET", "/api/linux/skills"),
> >     ("GET", "/api/linux/cluster/status"),
> >     ("GET", "/api/linux/voice/commands"),
> >     ("GET", "/api/linux/brain/status"),
> >     ("GET", "/api/linux/dominos"),
> >     ("GET", "/api/linux/profiles"),
> >     ("GET", "/api/linux/notifications"),
> >     ("GET", "/api/linux/report/today"),
> >     ("GET", "/api/linux/stats"),
> > ]
> >
> > ok, fail = 0, 0
> > for method, path in endpoints:
> >     try:
> >         r = requests.request(method, f"{BASE}{path}", timeout=5)
> >         status = "OK" if r.status_code == 200 else f"ERR {r.status_code}"
> >         if r.status_code == 200:
> >             ok += 1
> >         else:
> >             fail += 1
> >     except Exception as e:
> >         status = f"FAIL ({e})"
> >         fail += 1
> >     print(f"  [{status}] {method} {path}")
> >
> > print(f"\nResultat: {ok} OK, {fail} echecs sur {len(endpoints)} endpoints")
> > sys.exit(1 if fail > 0 else 0)
> > ```
> >
> > ---
> >
> > *Fixes #3*
