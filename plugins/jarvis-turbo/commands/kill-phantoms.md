---
name: kill-phantoms
description: Detecte et kill les processus fantomes MCP/Python/Node dupliques — watchdog integre cluster JARVIS, SQLite metrics, Telegram alerts
arguments:
  - name: mode
    description: "Mode: scan|kill|aggressive|watchdog|stats|health|status (default: kill)"
    required: false
---

Phantom Process Killer v2.0 — integre au cluster JARVIS avec config JSON, SQLite, Telegram.

## Etape 1 — Scan des processus fantomes

```bash
python3 F:/BUREAU/turbo/scripts/kill_phantoms.py --dry-run --json
```

Analyse le rapport JSON. Identifie les types de fantomes detectes (MCP Node, Python zombies, npx wrappers, memory hogs, stale processes).

## Etape 2 — Action selon le mode demande

Si l'utilisateur demande "scan" ou "status" → affiche le rapport et arrete.
Si "aggressive" :
```bash
python3 F:/BUREAU/turbo/scripts/kill_phantoms.py --aggressive --telegram
```

Si "watchdog" :
```bash
python3 F:/BUREAU/turbo/scripts/kill_phantoms.py --watchdog --interval 120
```

Si "stats" :
```bash
python3 F:/BUREAU/turbo/scripts/kill_phantoms.py --stats --hours 48
```

Si "health" :
```bash
python3 F:/BUREAU/turbo/scripts/kill_phantoms.py --health
```

Par defaut (kill) :
```bash
python3 F:/BUREAU/turbo/scripts/kill_phantoms.py --json
```

## Etape 3 — Verification post-nettoyage

Si des processus ont ete tues, verifie le cluster :

```bash
python3 F:/BUREAU/turbo/scripts/kill_phantoms.py --health --json
```

Puis verifie les MCP de la session active :

```bash
python3 -c "
import subprocess, json
r = subprocess.run(['tasklist','/FI','IMAGENAME eq node.exe','/FO','CSV','/NH'], capture_output=True, text=True)
node_count = len([l for l in r.stdout.strip().split('\n') if l.strip() and 'node.exe' in l])
r2 = subprocess.run(['tasklist','/FI','IMAGENAME eq pythonw.exe','/FO','CSV','/NH'], capture_output=True, text=True)
py_count = len([l for l in r2.stdout.strip().split('\n') if l.strip() and 'pythonw.exe' in l])
print(json.dumps({'node_processes': node_count, 'python_services': py_count}))
"
```

## Configuration

Config JSON: `F:/BUREAU/turbo/data/kill_phantoms.json`
Regenerer config par defaut: `python3 F:/BUREAU/turbo/scripts/kill_phantoms.py --init-config`
DB historique: `F:/BUREAU/turbo/data/kill_phantoms.db`
Logs: `F:/BUREAU/turbo/logs/kill_phantoms.log`

## Parametres CLI complets

| Parametre | Description |
|-----------|-------------|
| `--dry-run` | Scan sans kill |
| `--watchdog` | Mode daemon continu |
| `--aggressive` | Seuils bas (300MB, 1h) |
| `--interval N` | Intervalle watchdog (secondes) |
| `--keep N` | Garder N instances par type |
| `--max-mem N` | Kill orphelins > N MB |
| `--max-age N` | Kill processus > N heures |
| `--telegram` | Forcer alerte Telegram |
| `--stats` | Historique kills |
| `--health` | Health check cluster seul |
| `--json` | Sortie JSON |
| `--config path` | Config JSON custom |
| `--protect-pids 1,2` | PIDs proteges extra |
