```
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
        Assistant IA Linux Auto-Améliorant
```

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-Privée-red)
![Tests](https://img.shields.io/badge/Tests-2281_fonctions-green)
![Skills](https://img.shields.io/badge/Skills-203+-purple)
![Modules](https://img.shields.io/badge/Modules-246-orange)

---

## Apercu

**JARVIS** est un assistant IA vocal pour Linux, auto-ameliorant, construit sur le Claude Agent SDK. Il integre **203+ skills**, **853 commandes vocales**, **494 dominos automatises** et un cluster multi-GPU distribue (6 GPU, 4 noeuds). L'architecture couvre 246 modules Python (93K lignes), 21 modules Linux natifs, 613 handlers MCP et 517 endpoints REST.

JARVIS pilote integralement un poste Linux par la voix, les raccourcis clavier, l'API REST ou un dashboard web — tout en apprenant de chaque interaction pour s'ameliorer en continu.

---

## Fonctionnalites

### Controle vocal
- **853 commandes vocales** enregistrees en base (16 categories)
- **2 628 corrections STT** pour une reconnaissance robuste
- **Macros** : enchainer plusieurs commandes en une phrase
- Classification multi-intent (decomposition automatique des demandes complexes)
- Match fuzzy (SequenceMatcher + Jaccard, seuil 0.75)

### Cerveau auto-ameliorant (Brain)
- Apprentissage par renforcement : chaque pipeline reussi est sauvegarde automatiquement
- **41 dominos conversationnels** (5 categories : system, cluster, dev, trading, voice)
- Detection de patterns et generation automatique de skills
- Prediction d'intentions basee sur le contexte et l'historique

### Pipelines automatises (Dominos)
- **494 dominos** executables en cascade
- Triggers parametres avec match fuzzy
- Replay automatique des sequences apprises
- 4 handlers MCP : `learned_action_list`, `learned_action_match`, `learned_action_save`, `learned_action_stats`

### Cluster IA distribue
| Noeud | Modele | Role | Perf |
|-------|--------|------|------|
| M1 | qwen3-8b | Champion local | 46 tok/s |
| M1B | gpt-oss-20b | Deep local | ctx 25K |
| M2 | deepseek-r1-qwen3-8b | Reasoning | 44 tok/s |
| M3 | deepseek-r1-qwen3-8b | Reasoning fallback | — |
| OL1 cloud | gpt-oss:120b | Champion cloud | 51 tok/s |
| OL1 cloud | devstral-2:123b | Code cloud #2 | 94/100 |
| OL1 local | qwen3:1.7b | Ultra-rapide | 84 tok/s |

- Re-routage automatique en cascade (GPU warning 75C, critical 85C)
- Load balancing intelligent avec scoring par noeud

### Services systemd
17 services + 5 timers user :

| Timer | Frequence | Action |
|-------|-----------|--------|
| `jarvis-health` | 15 min | Health check cluster |
| `jarvis-backup` | Quotidien | Backup bases SQLite |
| `jarvis-thermal` | 5 min | Monitoring temperature GPU |
| `jarvis-log-rotate` | Hebdomadaire | Rotation logs + rapports |
| `jarvis-pipeline-check` | 10 min | Watchdog pipeline |

### Dashboard web + Conky
- Dashboard web sur port `8088`
- Widgets Conky temps reel (CPU, RAM, GPU, cluster)
- Canvas UI standalone sur port `18800` avec moteur d'autolearn

### Bot Telegram
- 15 commandes Linux pilotables a distance
- Notifications proactives (alertes GPU, services down, etc.)

### CI/CD
- GitHub Actions integre
- 2 281 fonctions de test (77+ fichiers, couverture 85.5%)
- `uv run pytest` pour lancer les tests

---

## Demarrage rapide

```bash
# Installation complete (deps, venv, services systemd)
./install_jarvis_linux.sh

# Alternative : Docker Compose
cd projects/linux && docker compose up -d

# Controle des services
./jarvis-ctl.sh status    # Voir l'etat
./jarvis-ctl.sh start     # Demarrer JARVIS
./jarvis-ctl.sh stop      # Arreter JARVIS
```

### Pre-requis
- Ubuntu 22.04+ / Debian 12+
- Python 3.13 + uv
- GNOME Shell (pour les raccourcis clavier gsettings)
- nvidia-driver + nvidia-smi (pour le monitoring GPU)
- `apt install xdotool xrandr` (controle desktop)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    UTILISATEUR                          │
│         Voix  |  Clavier  |  API  |  Telegram          │
└──────┬────────┴─────┬─────┴───┬───┴──────┬─────────────┘
       │              │         │          │
       v              v         v          v
┌──────────────┐ ┌─────────┐ ┌──────┐ ┌────────┐
│  STT Engine  │ │ Hotkey  │ │ REST │ │Telegram│
│ (corrections │ │ Daemon  │ │ API  │ │  Bot   │
│  2628 regles)│ │(gsettings)│ │(20ep)│ │(15 cmd)│
└──────┬───────┘ └────┬────┘ └──┬───┘ └───┬────┘
       │              │         │          │
       v              v         v          v
┌─────────────────────────────────────────────────────────┐
│              ROUTER / COMMANDER                         │
│   Classification intent + decomposition multi-tache     │
│   Match fuzzy (SequenceMatcher + Jaccard)                │
└──────────────────────┬──────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       v               v               v
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  21 Modules │ │  203 Skills │ │  494 Dominos│
│  linux_*.py │ │  skills.json│ │  learned_   │
│             │ │             │ │  actions.db │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │
       v               v               v
┌─────────────────────────────────────────────────────────┐
│                     BRAIN                               │
│   Apprentissage par renforcement + auto-generation      │
│   Patterns detectes → nouveaux skills + dominos         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       v
┌─────────────────────────────────────────────────────────┐
│              CLUSTER IA (M1/M1B/M2/M3/OL1)             │
│   Orchestration + load balancing + cascade thermique    │
│   10 GPU, 78 GB VRAM, scoring par noeud                 │
└─────────────────────────────────────────────────────────┘
```

---

## Commandes vocales — Exemples

| Categorie | Exemple | Description |
|-----------|---------|-------------|
| Systeme | *"rapport systeme"* | Diagnostic complet (CPU, RAM, GPU, disque) |
| Maintenance | *"nettoyage profond"* | apt autoremove + cache + logs |
| Reseau | *"diagnostic reseau"* | Interfaces, IP, routes, latence |
| Cluster | *"status cluster"* | Etat des 4 noeuds + GPU |
| Dev | *"mode dev"* | Active IDE + terminals + monitoring |
| Securite | *"audit securite"* | UFW, fail2ban, ports ouverts |
| Desktop | *"focus mode"* | Desactive notifications, plein ecran |
| Trading | *"scan trading"* | Pipeline GPU d'analyse marche |
| Fichiers | *"ouvre le dossier projets"* | Navigateur de fichiers |
| Apps | *"lance firefox"* | Ouverture d'application |

Les commandes supportent les **parametres** (*"ouvre {site}"*) et la **confirmation** pour les actions destructives.

---

## Raccourcis clavier

| Raccourci | Action |
|-----------|--------|
| `Super+1` | Rapport systeme |
| `Super+2` | Maintenance complete |
| `Super+3` | Diagnostic reseau |
| `Super+4` | Cluster check |
| `Super+5` | Mode dev |
| `Super+J` | Pipeline vocal |
| `Super+G` | GPU monitor |
| `Super+F1` | Documentation vocale (HTML) |
| `Super+F2` | Dashboard web |
| `Super+F5` | Nettoyage profond |
| `Super+F12` | Self-diagnostic JARVIS |
| `Super+Escape` | Focus mode |

Les raccourcis sont synchronises avec les commandes vocales via le module `linux_hotkey_daemon.py` et gsettings (GNOME natif).

---

## API REST

L'API est servie sur le port `8080` sous le prefixe `/api/linux/`. 20 endpoints disponibles :

| # | Methode | Endpoint | Description |
|---|---------|----------|-------------|
| 1 | GET | `/api/linux/health` | Sante complete (CPU, RAM, GPU, disque) |
| 2 | GET | `/api/linux/skills` | Liste des 203 skills |
| 3 | GET | `/api/linux/skills/<name>` | Detail d'un skill |
| 4 | POST | `/api/linux/skills/execute` | Executer un skill |
| 5 | GET | `/api/linux/voice/commands` | Commandes vocales (?category=) |
| 6 | GET | `/api/linux/voice/corrections` | Corrections STT |
| 7 | GET | `/api/linux/voice/aliases` | Aliases sites/apps |
| 8 | GET | `/api/linux/voice/macros` | Macros vocales |
| 9 | GET | `/api/linux/brain/status` | Etat du cerveau IA |
| 10 | GET | `/api/linux/brain/predictions` | Predictions d'intent |
| 11 | GET | `/api/linux/cluster/status` | Etat du cluster |
| 12 | GET | `/api/linux/dominos` | Liste des dominos |
| 13 | POST | `/api/linux/dominos/execute` | Executer un domino |
| 14 | GET | `/api/linux/profiles` | Profils utilisateur |
| 15 | POST | `/api/linux/profiles/activate` | Activer un profil |
| 16 | GET | `/api/linux/notifications` | Historique notifications |
| 17 | GET | `/api/linux/performance` | Metriques de performance |
| 18 | GET | `/api/linux/report/today` | Rapport du jour |
| 19 | GET | `/api/linux/faq` | FAQ dynamique |
| 20 | GET | `/api/linux/stats` | Statistiques globales |

### Exemples

```bash
# Sante du systeme
curl http://127.0.0.1:8080/api/linux/health | jq

# Lister les skills
curl http://127.0.0.1:8080/api/linux/skills | jq '.data.count'

# Executer un skill
curl -X POST http://127.0.0.1:8080/api/linux/skills/execute \
  -H "Content-Type: application/json" \
  -d '{"skill": "rapport_systeme_linux"}'

# Commandes vocales par categorie
curl "http://127.0.0.1:8080/api/linux/voice/commands?category=systeme" | jq

# Etat du cluster
curl http://127.0.0.1:8080/api/linux/cluster/status | jq
```

---

## Modules Linux

21 modules natifs dans `src/linux_*.py`, charges dynamiquement via `platform_dispatch.py` :

| Module | Domaine |
|--------|---------|
| `linux_sys.py` | Infos systeme (uname, uptime, memoire) |
| `linux_services.py` | Gestion systemd (start/stop/status) |
| `linux_network.py` | Interfaces reseau, IP, routes |
| `linux_packages.py` | APT/DNF, packages installes |
| `linux_package_manager.py` | Gestionnaire de paquets avance |
| `linux_display.py` | Xrandr, resolution |
| `linux_screen.py` | Screenshots, enregistrement ecran |
| `linux_desktop_control.py` | xdotool, controle fenetres |
| `linux_hotkey_daemon.py` | Raccourcis clavier globaux (gsettings) |
| `linux_power_manager.py` | Suspend, hibernate, shutdown |
| `linux_security_status.py` | UFW, fail2ban, audit |
| `linux_journal_reader.py` | Journalctl, logs systeme |
| `linux_maintenance.py` | Nettoyage, apt autoremove |
| `linux_startup.py` | Autostart XDG, systemd user |
| `linux_update_manager.py` | Mises a jour systeme |
| `linux_swap_manager.py` | Swap, zram config |
| `linux_workspace_manager.py` | Bureaux virtuels |
| `linux_snapshot_manager.py` | Snapshots btrfs/timeshift |
| `linux_config_manager.py` | Fichiers config (/etc) |
| `linux_share_manager.py` | Samba, NFS shares |
| `linux_trash_manager.py` | Corbeille freedesktop |

---

## Configuration

### Variables d'environnement

Copier `.env.example` vers `.env` et renseigner les valeurs. Les variables sensibles ne doivent **jamais** etre commitees.

### Profils vocaux

Les profils adaptent le comportement de JARVIS selon le contexte (dev, trading, multimedia, etc.). Activation via API ou commande vocale.

### Routines

Les routines sont des sequences de skills executees automatiquement (demarrage, cron, evenement). Configurables dans `data/skills.json`.

---

## Developpement

### Lancer les tests

```bash
uv run pytest                              # Tous les tests
uv run pytest tests/test_linux_*.py        # Tests Linux uniquement
uv run python scripts/system_audit.py --quick  # Audit rapide
```

### Structure du projet

```
jarvis/
├── src/                  # 246 modules Python (93K lignes)
│   ├── linux_*.py        # 21 modules Linux natifs
│   ├── commands.py       # Base de commandes vocales (SQL-backed)
│   ├── config.py         # Configuration cluster + routage
│   ├── tools.py          # Outils MCP (613 handlers)
│   ├── mcp_server.py     # Serveur MCP (6400+ lignes)
│   ├── commander.py      # Classification/decomposition taches
│   ├── learned_actions.py # Moteur dominos conversationnels
│   └── platform_dispatch.py # Dispatch linux_*/win_* automatique
├── data/                 # 64 bases SQLite (160 MB)
│   ├── jarvis.db         # Base principale (42 tables)
│   ├── skills.json       # 203 skills
│   └── learned_actions.db # 41 dominos conversationnels
├── canvas/               # UI standalone (port 18800)
├── cowork/dev/           # 409 scripts pipeline autonome
├── projects/linux/       # Deploy Docker + systemd
├── scripts/              # Utilitaires et generation
├── tests/                # 2 281 fonctions de test
└── main.py               # Point d'entree
```

### Conventions

- Python : type hints, async/await, f-strings, dataclasses
- Imports : `from __future__ import annotations` en premier
- Nommage : `snake_case` (Python), `camelCase` (JS)
- Toujours `127.0.0.1` au lieu de `localhost` (eviter le lag IPv6)

### Scripts utiles

```bash
uv run python scripts/system_audit.py --quick              # Audit rapide
uv run python scripts/trading_v2/gpu_pipeline.py --quick   # Trading scan
node canvas/direct-proxy.js                                 # Canvas proxy
python cowork/dev/autonomous_cluster_pipeline.py            # Pipeline autonome
uv run python scripts/generate_systemd_timers.py            # Generer timers
```

---

## Statistiques

| Metrique | Valeur |
|----------|--------|
| Modules Python | 246 (93K lignes) |
| Modules Linux | 21 |
| Skills | 203 |
| Categories de skills | 35 |
| Commandes vocales | 853 |
| Corrections STT | 2 628 |
| Dominos conversationnels | 41 |
| Handlers MCP | 613 |
| Endpoints REST | 517 |
| Endpoints API Linux | 20 |
| Bases SQLite | 64 (160 MB) |
| Tests | 2 281 fonctions (77+ fichiers) |
| Couverture | 85.5% |
| Noeuds cluster | 4 (+cloud) |
| GPU | 10 (78 GB VRAM) |
| Services systemd | 17 + 5 timers |
| Workflows n8n | 63 |
| Scripts cowork | 409 |
| Raccourcis clavier | 12 |
| Slash commands | 43 |

---

## Troubleshooting

| Symptome | Solution |
|----------|----------|
| M2/M3 TIMEOUT | `max_output_tokens` trop bas pour deepseek-r1, minimum 2048 |
| OL1 OFFLINE | `ollama serve` restart |
| Canvas crash | `node canvas/direct-proxy.js` restart (port 18800) |
| GPU >75C | `/thermal`, decharger modeles |
| systemd timer inactif | `systemctl --user enable --now jarvis-health.timer` |
| `linux_*.py` ImportError | `apt install xdotool xrandr` |
| platform_dispatch stub | Module pas porte — creer `src/linux_<domain>.py` |
| Docker compose fail | `docker compose logs jarvis-mcp` |
| xdotool echoue | Verifier `$DISPLAY` ou `$WAYLAND_DISPLAY` |

---

## Licence

Projet prive. Tous droits reserves.

---

*JARVIS Turbo v12.4 — Construit avec le Claude Agent SDK*
