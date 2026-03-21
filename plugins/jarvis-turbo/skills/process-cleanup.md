---
name: process-cleanup
description: "Nettoyage automatique des processus fantomes/zombies — scan, kill doublons MCP/Python/Node, watchdog, stats SQLite, health cluster, Telegram alerts. Utiliser quand le systeme ralentit, RAM elevee, processus dupliques, ou maintenance systeme."
---

Tu dois nettoyer les processus fantomes du systeme JARVIS.

## Etape 1 — Diagnostic rapide

Lance un scan en dry-run pour identifier les fantomes :

```bash
python3 F:/BUREAU/turbo/scripts/kill_phantoms.py --dry-run --json
```

Analyse le JSON :
- `phantoms` : liste des processus detectes (type, PID, mem_mb, reason)
- `kept` : nombre de processus gardes (1 par type)

## Etape 2 — Decision

Si des fantomes sont detectes :
- **< 3 fantomes** → kill silencieux
- **>= 3 fantomes** → kill + alerte Telegram
- **RAM > 500MB totale** → mode agressif

### Kill standard
```bash
python3 F:/BUREAU/turbo/scripts/kill_phantoms.py --json
```

### Kill agressif (RAM elevee)
```bash
python3 F:/BUREAU/turbo/scripts/kill_phantoms.py --aggressive --telegram --json
```

## Etape 3 — Verification cluster

```bash
python3 F:/BUREAU/turbo/scripts/kill_phantoms.py --health --json
```

Verifie que M1, M2, OL1 sont toujours UP apres le nettoyage.

## Etape 4 — Rapport

Presente un resume :
- Nombre de fantomes elimines
- RAM liberee
- Etat cluster post-nettoyage
- Recommandation (watchdog si recurrence)

## Mode watchdog (si recurrence)

```bash
python3 F:/BUREAU/turbo/scripts/kill_phantoms.py --watchdog --interval 120
```

## Orchestrateur

```bash
python3 F:/BUREAU/turbo/scripts/devops_orchestrator.py --kill-phantoms
python3 F:/BUREAU/turbo/scripts/devops_orchestrator.py --cowork cleanup
```

## Stats historiques

```bash
python3 F:/BUREAU/turbo/scripts/kill_phantoms.py --stats --hours 48
```
