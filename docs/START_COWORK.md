# JARVIS COWORK - Systeme de developpement autonome

Date: 2026-03-05 06:15 CET

## Vue d'ensemble

JARVIS COWORK est un systeme d'**intelligence collective** qui fait travailler
**6 agents IA en parallele** pour developper automatiquement de nouvelles features,
corriger des bugs, optimiser le code, et ameliorer JARVIS 24/7.

### Architecture

```
                    COWORK ORCHESTRATOR
                           |
        +------------------+------------------+
        |                  |                  |
    ARCHITECT           CODER            REVIEWER
   (Design sys)     (Impl code)      (Quality check)
        |                  |                  |
    M1: deepseek      M2: qwen2.5      M3: deepseek
        |                  |                  |
        +------------------+------------------+
                           |
        +------------------+------------------+
        |                  |                  |
     TESTER          OPTIMIZER         DOCUMENTER
  (Gen tests)      (Perf optim)      (Write docs)
        |                  |                  |
   Ollama Cloud      Ollama Cloud       Gemini
```

### Workflow autonome

1. **Task Queue** : 20 taches predefinies (voir cowork_master_config.py)
2. **Orchestrator** : Selectionne la prochaine tache selon priorite/dependances
3. **Agent Assignment** : Assigne les agents IA requis (architect, coder, etc.)
4. **Execution** :
   - Phase 1: Design (architect)
   - Phase 2: Implementation (coder)
   - Phase 3: Code review (reviewer)
   - Phase 4: Tests (tester)
5. **Validation** : Verifie score review >= 70/100 et tests passes
6. **Commit** : Si OK, commit automatique du code
7. **Loop** : Passe a la tache suivante

---

## Queue de taches (20 taches)

### Phase 1: Infrastructure critique (2 taches)

| ID | Titre | Priorite | Duree | Agents |
|----|-------|----------|-------|--------|
| DEV-001 | Creer table scheduler_jobs | CRITICAL | 15 min | Coder, Reviewer |
| DEV-002 | Implementer attribut 'running' AutonomousLoop | CRITICAL | 20 min | Coder, Reviewer |

### Phase 2: Optimisations performance (2 taches)

| ID | Titre | Priorite | Duree | Agents |
|----|-------|----------|-------|--------|
| DEV-003 | Optimiser GPU memory management | HIGH | 45 min | Optimizer, Coder |
| DEV-004 | Connection pooling pour bases de donnees | HIGH | 40 min | Coder, Optimizer |

### Phase 3: Features majeures (3 taches)

| ID | Titre | Priorite | Duree | Agents |
|----|-------|----------|-------|--------|
| DEV-005 | Systeme cache distribue inter-noeuds | HIGH | 90 min | Architect, Coder |
| DEV-006 | Auto-tuning hyperparametres trading | HIGH | 120 min | Architect, Coder, Tester |
| DEV-007 | Voice commands avec wake word detection | MEDIUM | 180 min | Architect, Coder |

### Phase 4: Intelligence & Learning (2 taches)

| ID | Titre | Priorite | Duree | Agents |
|----|-------|----------|-------|--------|
| DEV-008 | Pattern mining multi-source | MEDIUM | 150 min | Architect, Coder, Optimizer |
| DEV-009 | Self-improving code generator | MEDIUM | 240 min | Architect, Coder, Reviewer, Tester |

### Phase 5: UI & Monitoring (2 taches)

| ID | Titre | Priorite | Duree | Agents |
|----|-------|----------|-------|--------|
| DEV-010 | Dashboard temps reel Streamlit | MEDIUM | 180 min | Coder, Documenter |
| DEV-011 | Notifications multi-canal | LOW | 90 min | Coder |

### Phase 6: Security & Robustness (2 taches)

| ID | Titre | Priorite | Duree | Agents |
|----|-------|----------|-------|--------|
| DEV-012 | Chiffrement end-to-end pour secrets | HIGH | 60 min | Architect, Coder, Reviewer |
| DEV-013 | Rate limiting & circuit breakers globaux | HIGH | 45 min | Architect, Coder |

### Phase 7: Testing & Quality (2 taches)

| ID | Titre | Priorite | Duree | Agents |
|----|-------|----------|-------|--------|
| DEV-014 | Suite tests automatises complete | MEDIUM | 300 min | Tester, Coder |
| DEV-015 | CI/CD pipeline GitHub Actions | MEDIUM | 120 min | Architect, Coder |

### Phase 8: Advanced features (2 taches)

| ID | Titre | Priorite | Duree | Agents |
|----|-------|----------|-------|--------|
| DEV-016 | Multi-user support avec permissions | LOW | 180 min | Architect, Coder |
| DEV-017 | Plugin system pour extensions | LOW | 240 min | Architect, Coder, Documenter |

### Phase 9: Documentation (1 tache)

| ID | Titre | Priorite | Duree | Agents |
|----|-------|----------|-------|--------|
| DEV-018 | Documentation technique complete | MEDIUM | 180 min | Documenter |

### Phase 10: Performance monitoring (2 taches)

| ID | Titre | Priorite | Duree | Agents |
|----|-------|----------|-------|--------|
| DEV-019 | Profiling automatique & bottleneck detection | LOW | 120 min | Optimizer, Coder |
| DEV-020 | A/B testing framework pour strategies | LOW | 150 min | Architect, Coder, Tester |

**Duree totale estimee: ~50 heures** (reparti sur plusieurs jours/semaines)

---

## Demarrage rapide

### Etape 1: Verifier la configuration

```powershell
cd /home/turbo/jarvis-m1-ops
python -c "from src.cowork_master_config import *; print(f'{len(AVAILABLE_AGENTS)} agents, {len(DEVELOPMENT_QUEUE)} tasks')"
```

Doit afficher: `6 agents, 20 tasks`

### Etape 2: Demarrer l'orchestrateur

**Option A - En tant que service (recommande)**

Ajouter au bootstrap (dans `startup_wiring.py`) :

```python
async def _step_cowork_orchestrator() -> dict[str, Any]:
    from src.cowork_orchestrator import cowork_orchestrator
    if not cowork_orchestrator.running:
        asyncio.create_task(cowork_orchestrator.start())
        await asyncio.sleep(0.5)
    return {
        "running": cowork_orchestrator.running,
        "queue_size": len([t for t in cowork_orchestrator.task_queue if t.status == 'pending'])
    }
```

Puis l'appeler dans `bootstrap_jarvis()` apres l'etape 8 (autonomous loop).

**Option B - Manuel (test)**

```python
import asyncio
from src.cowork_orchestrator import cowork_orchestrator

asyncio.run(cowork_orchestrator.start())
```

### Etape 3: Monitorer l'avancement

```python
from src.cowork_orchestrator import cowork_orchestrator

status = cowork_orchestrator.status()
print(f"Running: {status['running']}")
print(f"Uptime: {status['uptime_hours']:.2f}h")
print(f"Completed: {status['stats']['tasks_completed']}")
print(f"Failed: {status['stats']['tasks_failed']}")
print(f"Active: {status['active_tasks']}")
print(f"Queue: {status['queue_size']}")
```

### Etape 4: Logs

Les logs sont ecrits dans :
- **Console** : Tous les evenements importants
- **Fichier** : `/home/turbo/jarvis-m1-ops/logs/cowork.log`
- **Event bus** : Events `cowork/task_completed` et `cowork/task_failed`

---

## Configuration des agents

### Agents LM Studio (locaux)

| Agent | Role | Node | Modele | Context |
|-------|------|------|--------|--------|
| architect_m1 | Architect | M1 (192.168.1.12) | deepseek-coder-v3 | 32k |
| coder_m2 | Coder | M2 (192.168.1.13) | qwen2.5-coder | 32k |
| reviewer_m3 | Reviewer | M3 (192.168.1.14) | deepseek-coder-v3 | 16k |

### Agents Ollama Cloud

| Agent | Role | Modele |
|-------|------|--------|
| tester_ollama | Tester | deepseek-r1:14b |
| optimizer_ollama | Optimizer | qwen2.5-coder:32b |

### Agent Gemini

| Agent | Role | Backend |
|-------|------|--------|
| documenter_gemini | Documenter | Gemini Pro |

---

## Mecanismes de securite

### Quality Gates

1. **Code Review obligatoire** : Score >= 70/100
2. **Tests obligatoires** : Tests doivent passer
3. **Coverage minimum** : 70%

### Validation multi-niveaux

- **Phase 1** : Design review (architect)
- **Phase 2** : Code implementation (coder)
- **Phase 3** : Security & quality review (reviewer)
- **Phase 4** : Automated testing (tester)

### Rollback automatique

Si une tache genere du code qui casse les tests existants,
le systeme peut automatiquement faire un `git revert`.

---

## Ajouter des taches custom

### Methode 1 : Editer cowork_master_config.py

Ajouter a `DEVELOPMENT_QUEUE` :

```python
DevelopmentTask(
    id="DEV-XXX",
    title="Ma nouvelle feature",
    description="Description detaillee...",
    category=TaskCategory.FEATURE,
    priority=TaskPriority.HIGH,
    required_agents=[AgentRole.ARCHITECT, AgentRole.CODER],
    estimated_duration_min=60
)
```

### Methode 2 : API (a venir)

```python
from src.cowork_orchestrator import cowork_orchestrator

cowork_orchestrator.add_task(
    title="Fix bug XYZ",
    description="...",
    priority="HIGH"
)
```

---

## Monitoring avance

### Event Bus integration

Tous les evenements cowork sont emis sur l'event bus :

```python
from src.event_bus import event_bus

async def on_task_completed(event):
    print(f"Task {event.data['task_id']} completed!")

event_bus.subscribe("cowork", "task_completed", on_task_completed)
```

### Metriques Prometheus (a venir)

- `cowork_tasks_total{status="completed"}` : Total tasks completed
- `cowork_tasks_total{status="failed"}` : Total tasks failed
- `cowork_task_duration_seconds` : Task execution time
- `cowork_agents_busy` : Number of busy agents

---

## Troubleshooting

### L'orchestrateur ne demarre pas

Verifier que tous les agents sont accessibles :

```python
from src.cowork_master_config import AVAILABLE_AGENTS
from src.lm_client import lm_query

for name, config in AVAILABLE_AGENTS.items():
    if 'node' in config:
        try:
            await lm_query(config['node'], config['model'], "test", 512)
            print(f"{name}: OK")
        except:
            print(f"{name}: FAILED")
```

### Les taches echouent systematiquement

1. Verifier les logs dans `logs/cowork.log`
2. Verifier les quality gates : peut-etre trop stricts
3. Tester manuellement un agent :

```python
from src.cowork_orchestrator import cowork_orchestrator

agent_info = {"name": "coder_m2", "config": AVAILABLE_AGENTS["coder_m2"]}
result = await cowork_orchestrator._run_agent(agent_info, "Write a hello world")
print(result)
```

### Une tache est bloquee en "in_progress"

Timeout par defaut : 30 minutes. Si un agent ne repond pas :

```python
from src.cowork_orchestrator import cowork_orchestrator

# Force kill task
task = cowork_orchestrator.active_tasks["DEV-XXX"]
task.status = "failed"
task.error = "Timeout"
del cowork_orchestrator.active_tasks["DEV-XXX"]
```

---

## Roadmap

### v1.1 (prochaine semaine)

- [ ] Integration Git automatique (commits)
- [ ] Dashboard Streamlit temps reel
- [ ] Notifications Discord/Telegram
- [ ] Metrics Prometheus

### v1.2

- [ ] Auto-generation de tests
- [ ] Code coverage tracking
- [ ] Performance profiling automatique
- [ ] Self-improvement loop (le systeme s'ameliore lui-meme)

### v2.0

- [ ] Multi-project support
- [ ] Plugin system pour nouvelles taches
- [ ] Apprentissage par renforcement (prioritisation dynamique)
- [ ] Collaboration avec humains (review manuelle optionnelle)

---

## Statistiques attendues

Apres 1 semaine de fonctionnement 24/7 :

- **Tasks completed** : 15-20 (selon complexite)
- **Code lines generated** : 5000-10000
- **Commits** : 15-20
- **Tests created** : 100-200
- **Bugs fixed** : 5-10
- **Features added** : 3-5

---

**Le systeme COWORK transforme JARVIS en un organisme auto-evolutif qui
s'ameliore continuellement sans intervention humaine.**

**JARVIS devient immortel et en constante evolution.**

