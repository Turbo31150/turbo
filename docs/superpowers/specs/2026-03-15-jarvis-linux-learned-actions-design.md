# JARVIS Linux Migration + Learned Actions System — Design Spec

**Date**: 2026-03-15
**Auteur**: Turbo + Claude Opus
**Status**: APPROVED

---

## 1. Vision

JARVIS est né sous Windows. Ce projet porte l'écosystème sur Linux tout en créant un système de **Learned Actions** : chaque action réussie est sauvegardée (demande conversationnelle + pipeline d'exécution) pour être rejouée instantanément.

**Principe fondamental** : La 1ère fois = dialogue + essais + réflexion. La 2ème fois = exécution immédiate.

---

## 2. Architecture Cible

### 2.1 Trois couches

```
┌─────────────────────────────────────────────────┐
│  COUCHE 1 — LEARNED ACTIONS CACHE               │
│  conversational_request → saved_pipeline         │
│  SQLite: learned_actions.db                      │
├─────────────────────────────────────────────────┤
│  COUCHE 2 — DOMINOS LINUX                        │
│  Commandes vocales FR → bash/systemctl/python    │
│  Fichier: src/domino_pipelines_linux.py          │
├─────────────────────────────────────────────────┤
│  COUCHE 3 — PLATFORM ABSTRACTION                 │
│  os.name dispatch → linux_*.py / win_*.py        │
│  Pattern existant: windows.py → linux_sys.py     │
└─────────────────────────────────────────────────┘
```

### 2.2 Learned Actions — Schema DB

```sql
CREATE TABLE learned_actions (
    id INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE, -- nom unique de l'action
    category TEXT NOT NULL,             -- system, trading, cluster, voice, dev, etc.
    platform TEXT DEFAULT 'both',       -- linux, windows, both
    pipeline_steps TEXT NOT NULL,       -- JSON array d'étapes d'exécution
    -- Chaque étape: {type, command, args, timeout, retry, fallback}
    -- Types: bash, python, curl, tool, pipeline (aligné sur DominoExecutor existant)
    context_required TEXT,              -- JSON: variables/conditions requises
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    avg_duration_ms REAL,
    last_used TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    learned_from TEXT                   -- session/conversation d'origine
);

-- Table de jonction pour lookup O(1) exact + fuzzy efficace
-- Miroir du pattern _trigger_exact dict dans src/commands.py
CREATE TABLE learned_action_triggers (
    id INTEGER PRIMARY KEY,
    action_id INTEGER NOT NULL REFERENCES learned_actions(id) ON DELETE CASCADE,
    phrase TEXT NOT NULL                -- une phrase conversationnelle par row
);

CREATE TABLE action_executions (
    id INTEGER PRIMARY KEY,
    action_id INTEGER REFERENCES learned_actions(id),
    trigger_text TEXT,                  -- la phrase exacte qui a déclenché
    status TEXT,                        -- success, failed, partial
    duration_ms REAL,
    output TEXT,                        -- résultat résumé
    error TEXT,
    executed_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trigger_phrase ON learned_action_triggers(phrase);
CREATE INDEX idx_trigger_action ON learned_action_triggers(action_id);
CREATE INDEX idx_category ON learned_actions(category);
CREATE INDEX idx_platform ON learned_actions(platform);
```

### 2.3 Pipeline d'exécution Learned Action

```
User: "lance un scan trading"
  │
  ├─ 1. Lookup dans learned_action_triggers:
  │     a) Hash exact sur phrase normalisée (O(1))
  │     b) Sinon fuzzy via src.commands.similarity() (max(SequenceMatcher, bag-of-words))
  │     c) Seuil > 0.75 → action trouvée (aligné sur commands.py)
  │
  ├─ 2. Vérifier context_required (GPU dispo? Noeud up?)
  │
  ├─ 3. Exécuter pipeline_steps séquentiellement
  │     Chaque step: {type: "bash", command: "uv run python scripts/trading_v2/gpu_pipeline.py --quick --json"}
  │     Si fail → retry → fallback → log erreur
  │
  ├─ 4. Logger dans action_executions
  │
  └─ 5. Mettre à jour success_count, avg_duration_ms
```

### 2.4 Apprentissage d'une nouvelle action

```
User: "comment je fais pour voir les GPU?"
  │
  ├─ 1. Pas de match dans learned_actions → mode dialogue
  │
  ├─ 2. Essais: nvidia-smi, nvtop, sensors...
  │
  ├─ 3. Succès confirmé par l'utilisateur
  │
  ├─ 4. AUTO-SAVE:
  │     trigger_phrases: ["voir les gpu", "status gpu", "gpu info", "état des gpu"]
  │     pipeline_steps: [
  │       {type: "bash", command: "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader"},
  │       {type: "python", command: "src.gpu_guardian.get_thermal_status()"}
  │     ]
  │     platform: "linux"
  │
  └─ 5. Prochaine fois: exécution immédiate
```

---

## 3. Dominos Linux — Catalogue cible

### 3.1 Dominos système (priorité haute)

| Domino | Trigger vocal | Pipeline |
|--------|--------------|----------|
| health-check | "vérifie la santé du système" | nvidia-smi + systemctl status jarvis-* + df -h + free -h |
| cluster-status | "état du cluster" | curl M1 + M2 + M3 + OL1 health endpoints |
| gpu-thermal | "température GPU" | nvidia-smi --query-gpu=temperature.gpu |
| restart-service | "redémarre {service}" | systemctl --user restart jarvis-{service} |
| logs-service | "montre les logs de {service}" | journalctl --user -u jarvis-{service} -n 50 |
| disk-usage | "espace disque" | df -h + du -sh ~/jarvis/* |
| network-check | "état réseau" | ip addr + ping M2 + ping M3 |
| process-list | "processus actifs" | ps aux --sort=-%cpu | head -20 |
| check-updates | "vérifie les mises à jour" | apt update && apt list --upgradable (lecture seule, pas d'upgrade auto) |
| backup-db | "sauvegarde les bases" | sqlite3 .backup pour chaque .db |

### 3.2 Dominos cluster IA (priorité haute)

| Domino | Trigger vocal | Pipeline |
|--------|--------------|----------|
| model-load | "charge {modèle} sur {noeud}" | curl POST /v1/models/load |
| model-unload | "décharge le modèle de {noeud}" | curl DELETE /v1/models |
| consensus-query | "consensus sur {question}" | MAO protocol: dispatch parallèle M1+M2+OL1+M3 |
| quick-ask | "demande à {noeud}: {question}" | curl POST vers le noeud spécifié |
| benchmark-quick | "benchmark rapide" | curl chaque noeud avec prompt test + mesure latence |
| trading-scan | "scan trading" | uv run python scripts/trading_v2/gpu_pipeline.py --quick |
| heal-cluster | "répare le cluster" | health check → identify down → restart → verify |

### 3.3 Dominos dev/workflow (priorité moyenne)

| Domino | Trigger vocal | Pipeline |
|--------|--------------|----------|
| git-status | "état du repo" | git status + git log --oneline -5 |
| git-commit | "commit les changements" | git add -A + git commit |
| run-tests | "lance les tests" | uv run pytest -x --tb=short |
| canvas-restart | "redémarre canvas" | systemctl --user restart jarvis-proxy |
| pipeline-start | "lance le pipeline" | systemctl --user start jarvis-pipeline |
| audit-system | "audit système complet" | uv run python scripts/system_audit.py --quick |

### 3.4 Dominos voix/interaction (priorité moyenne)

| Domino | Trigger vocal | Pipeline |
|--------|--------------|----------|
| voice-learn | "apprends cette commande" | INSERT INTO voice_commands + INSERT INTO learned_actions |
| voice-list | "liste mes commandes" | SELECT FROM voice_commands WHERE platform='linux' |
| voice-test | "teste la commande {nom}" | Exécuter + mesurer + reporter |

---

## 4. Platform Abstraction Layer

### 4.1 Pattern à généraliser

```python
# src/platform_dispatch.py (NOUVEAU)
from __future__ import annotations
import os
import importlib
import logging

log = logging.getLogger(__name__)

IS_LINUX = os.name != "nt"
IS_WINDOWS = os.name == "nt"

class _NotImplementedStub:
    """Stub pour modules pas encore portés — lève NotImplementedError avec message clair."""
    def __init__(self, domain: str, platform: str):
        self._domain = domain
        self._platform = platform
    def __getattr__(self, name: str):
        raise NotImplementedError(
            f"{self._platform}_{self._domain}.{name}() pas encore implémenté. "
            f"Créer src/{self._platform}_{self._domain}.py"
        )

def get_platform_module(domain: str):
    """Retourne le module plateforme approprié.
    domain: 'desktop', 'power', 'services', 'registry', etc.
    Retourne un stub si le module n'existe pas encore (migration incrémentale).
    """
    prefix = "linux" if IS_LINUX else "win"
    module_name = f"src.{prefix}_{domain}"
    try:
        return importlib.import_module(module_name)
    except ImportError:
        log.warning(f"Module {module_name} pas trouvé, stub retourné")
        return _NotImplementedStub(domain, prefix)
```

### 4.2 Modules à créer/adapter

| Module Windows | Equivalent Linux | Status |
|----------------|-----------------|--------|
| registry_manager.py | linux_config_manager.py | EXISTE |
| startup_manager.py | linux_startup.py (systemd) | A CREER |
| power_manager.py | linux_power_manager.py | EXISTE |
| display_manager.py | linux_display.py (xrandr) | A CREER |
| window_manager.py | linux_desktop_control.py | EXISTE (partiel) |
| screen_capture.py | linux_screen.py (scrot/grim) | A CREER |
| commands_maintenance.py | linux_maintenance.py (systemctl) | A CREER |
| commands_pipelines.py | linux_pipelines.py | A CREER |

---

## 5. Fixes critiques immédiats

1. **install.sh ligne 157** : `src.openclaw_bridge` → `src.openclaw_server`
2. **docker-compose.yml** : ajouter service `jarvis-openclaw` port 18789
3. **src/cowork_bridge.py:43** : utiliser `PATHS["turbo"] / "cowork/dev"` config-driven, ajouter C:/Users seulement si `os.name == "nt"`
4. **src/commands.py** : supprimer `_TURBO_DIR.replace("/", "\\")`  sur Linux

---

## 6. Séquence d'implémentation

### Phase 1 — Fondations (session 1)
- [ ] Fixer les 4 bugs critiques
- [ ] Créer `learned_actions.db` + schema
- [ ] Créer `src/learned_actions.py` — moteur CRUD + fuzzy match + exécution
- [ ] Créer `src/platform_dispatch.py` — dispatch OS

### Phase 2 — Dominos Linux Core (session 2-3)
- [ ] Créer `src/domino_pipelines_linux.py` — 10 dominos système
- [ ] Créer `src/linux_maintenance.py` — remplacement commands_maintenance
- [ ] Adapter `src/domino_executor.py` — support platform dispatch + étendre execute_step() pour les types manquants
- [ ] Intégrer learned_actions dans le pipeline vocal

### Phase 3 — Dominos Cluster + Trading (session 3-4)
- [ ] 7 dominos cluster IA
- [ ] 6 dominos dev/workflow
- [ ] 4 dominos voix/interaction
- [ ] Chaque domino sauvegardé comme learned action

### Phase 4 — Commandes vocales Linux (session 4-5)
- [ ] Script d'audit : `scripts/audit_commands_platform.py` — classifie les 853 commandes :
  - `action_type=powershell` → `platform=windows`
  - `action_type=bash` sans chemin Windows → `platform=both`
  - `action_type=bash` avec chemin Windows → `platform=windows` (à porter)
- [ ] Porter les commandes `platform=windows` prioritaires vers Linux
- [ ] Créer les équivalents Linux pour les 294 commandes PowerShell (systemctl, journalctl, etc.)
- [ ] Intégrer avec linux_desktop_control.py existant (3,254 lignes déjà prêtes)

### Phase 5 — Polish + Tests (session 5-6)
- [ ] Tests pour chaque domino Linux
- [ ] Tests pour le système learned_actions
- [ ] Benchmark: latence 1ère exécution vs replay learned action
- [ ] Documentation dominos en langage conversationnel

---

## 7. Métriques de succès

- [ ] 30+ dominos Linux fonctionnels en langage conversationnel
- [ ] Learned Actions: replay < 500ms pour actions connues
- [ ] 0 chemins Windows hardcodés dans le code Linux
- [ ] install.sh + docker-compose fonctionnels sans erreur
- [ ] Couverture tests > 80% sur les nouveaux modules
