# Trading AI Cluster - Server Manager

## Architecture

| Machine | IP | Port | Role | GPUs |
|---------|-----|------|------|------|
| **DESKTOP-4OVCOL7** | 192.168.1.85 | 5000 | Master + Load Balancer | 5x (40GB) |
| WIN-TBOT | 192.168.1.26 | 5001 | Worker GPU | 3x |
| SERVER-3 | 192.168.1.113 | 5002 | Worker | 2x |

## Structure

```
/CLAUDE_WORKSPACE\SERVER_MANAGER\
├── config/
│   └── network_config.json     # Config cluster
├── scripts/
│   ├── master_daemon.py        # Master (daemon mode)
│   ├── master_server.py        # Master (interactif)
│   ├── worker_server.py        # Worker
│   └── cluster_monitor.py      # Monitoring
├── logs/                       # Logs quotidiens
├── tasks/                      # File de taches
├── shared/                     # Fichiers partages
├── START_DAEMON.bat            # Demarrer Master Daemon
├── START_MASTER.bat            # Demarrer Master Interactif
├── START_WORKER.bat            # Demarrer Worker
└── MONITOR.bat                 # Dashboard cluster
```

## Demarrage

### Sur le MASTER (192.168.1.85)

```cmd
# Mode Daemon (recommande)
START_DAEMON.bat

# ou Mode Interactif
START_MASTER.bat
```

### Sur les WORKERS (192.168.1.26, .113)

Copier le dossier SERVER_MANAGER sur chaque worker, puis:

```cmd
START_WORKER.bat
```

Le worker detecte automatiquement son ID basé sur l'IP.

## Commandes Monitor

```cmd
# Dashboard rapide
MONITOR.bat

# Tests specifiques
python scripts/cluster_monitor.py ping      # Test reseau
python scripts/cluster_monitor.py status    # Status services
python scripts/cluster_monitor.py gpu       # Status GPU
python scripts/cluster_monitor.py lm        # Status LM Studio
python scripts/cluster_monitor.py test      # Test execution
python scripts/cluster_monitor.py all       # Tout
```

## LM Studio Cluster

| Node | URL | Model | Role |
|------|-----|-------|------|
| master | http://192.168.1.85:1234 | qwen3-30b | Analysis |
| worker1 | http://192.168.1.26:1234 | nemotron-3-nano | Detection |
| worker2 | http://192.168.1.113:1234 | mistral-7b | Validation |

## API Master Daemon

Le Master Daemon accepte ces commandes TCP (JSON):

| Commande | Description |
|----------|-------------|
| PING | Test connexion |
| STATUS | Status complet |
| GET_WORKERS | Liste workers |
| SCAN_WORKERS | Re-scanner workers |
| ADD_TASK | Ajouter tache |
| STOP | Arreter daemon |

## Installation Workers

Sur chaque worker:

1. Copier le dossier `SERVER_MANAGER` vers `/CLAUDE_WORKSPACE\`
2. Ouvrir le port 5001 (worker1) ou 5002 (worker2) dans le firewall
3. Lancer `START_WORKER.bat`

### Firewall (PowerShell admin)

```powershell
# Worker1
New-NetFirewallRule -DisplayName "Trading Cluster Worker" -Direction Inbound -Port 5001 -Protocol TCP -Action Allow

# Worker2
New-NetFirewallRule -DisplayName "Trading Cluster Worker" -Direction Inbound -Port 5002 -Protocol TCP -Action Allow
```
