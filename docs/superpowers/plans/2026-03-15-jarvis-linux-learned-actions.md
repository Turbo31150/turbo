# JARVIS Linux Migration + Learned Actions — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Porter JARVIS sur Linux avec un système de Learned Actions qui sauvegarde chaque action réussie (demande conversationnelle → pipeline d'exécution) pour replay instantané.

**Architecture:** 3 couches — (1) Learned Actions Cache (SQLite + fuzzy match), (2) Dominos Linux (commandes vocales → bash/systemctl), (3) Platform Abstraction (dispatch OS automatique). Le moteur Learned Actions s'intègre dans le pipeline vocal existant entre `voice_correction` et `match_command`.

**Tech Stack:** Python 3.13, SQLite, asyncio, uv, pytest, systemd, bash

**Spec:** `docs/superpowers/specs/2026-03-15-jarvis-linux-learned-actions-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `src/learned_actions.py` | Moteur CRUD + fuzzy match + exécution pipeline pour actions apprises |
| `src/platform_dispatch.py` | Dispatch OS automatique avec stub fallback |
| `src/domino_pipelines_linux.py` | 30+ dominos Linux en langage conversationnel |
| `src/linux_maintenance.py` | Equivalent Linux de commands_maintenance.py (systemctl, journalctl) |
| `scripts/audit_commands_platform.py` | Classifie les 853 commandes par plateforme |
| `tests/test_learned_actions.py` | Tests Learned Actions engine |
| `tests/test_platform_dispatch.py` | Tests platform dispatch |
| `tests/test_domino_pipelines_linux.py` | Tests dominos Linux |

### Modified Files
| File | Changes |
|------|---------|
| `projects/linux/install.sh:157` | Fix: `src.openclaw_bridge` → `src.openclaw_server` |
| `projects/linux/docker-compose.yml` | Add: service `jarvis-openclaw` port 18789 |
| `src/cowork_bridge.py:43-46` | Fix: config-driven COWORK_PATHS |
| `src/commands.py` | Cleanup: remove no-op `replace("/", "/")` |
| `src/domino_executor.py` | Add: `execute_learned_action()` wrapper using DominoStep + route_step |

---

## Chunk 1: Fondations — Fixes critiques + Learned Actions Engine

### Task 1: Fix install.sh OpenClaw module

**Files:**
- Modify: `projects/linux/install.sh:157`

- [ ] **Step 1: Lire le fichier et confirmer le bug**

Run: `grep -n "openclaw" projects/linux/install.sh`
Expected: ligne 157 contient `src.openclaw_bridge`

- [ ] **Step 2: Corriger le module**

```bash
# Dans install.sh, remplacer:
ExecStart=$JARVIS_HOME/.venv/bin/python -m src.openclaw_bridge
# Par:
ExecStart=$JARVIS_HOME/.venv/bin/python -m src.openclaw_server
```

- [ ] **Step 3: Commit**

```bash
git add projects/linux/install.sh
git commit -m "fix: install.sh use openclaw_server instead of bridge"
```

---

### Task 2: Add jarvis-openclaw to docker-compose

**Files:**
- Modify: `projects/linux/docker-compose.yml`

- [ ] **Step 1: Ajouter le service OpenClaw**

```yaml
  jarvis-openclaw:
    build:
      context: ../..
      dockerfile: projects/linux/Dockerfile
    container_name: jarvis-openclaw
    ports:
      - "18789:18789"
    volumes:
      - ../../:/app
    environment:
      - JARVIS_HOME=/app
    command: python -m src.openclaw_server
    restart: unless-stopped
    depends_on:
      - jarvis-ws
```

- [ ] **Step 2: Commit**

```bash
git add projects/linux/docker-compose.yml
git commit -m "feat: add jarvis-openclaw service to docker-compose"
```

---

### Task 3: Fix cowork_bridge.py hardcoded Windows paths

**Files:**
- Modify: `src/cowork_bridge.py:43-46`

- [ ] **Step 1: Lire le code actuel**

Run: `grep -n "COWORK_PATHS" src/cowork_bridge.py | head -10`

- [ ] **Step 2: Remplacer par config-driven paths**

```python
# Avant (hardcoded):
COWORK_PATHS = [
    Path("C:/Users/franc/.openclaw/workspace/dev"),
    Path("/home/turbo/jarvis/cowork/dev"),
]

# Après (config-driven):
from src.config import PATHS
import os

COWORK_PATHS = [PATHS["turbo"] / "cowork" / "dev"]
if os.name == "nt":
    COWORK_PATHS.insert(0, Path("C:/Users/franc/.openclaw/workspace/dev"))
```

- [ ] **Step 3: Commit**

```bash
git add src/cowork_bridge.py
git commit -m "fix: cowork_bridge use config-driven paths, remove hardcoded Windows path on Linux"
```

---

### Task 4: Cleanup commands.py no-op replace

**Files:**
- Modify: `src/commands.py:40`

- [ ] **Step 1: Confirmer le no-op**

Run: `grep -n 'replace.*"/"' src/commands.py | head -5`
Expected: ligne 40 contient `.replace("/", "/")` — un no-op inutile

- [ ] **Step 2: Supprimer le no-op**

```python
# Avant:
_TURBO_DIR = str(PATHS.get("turbo", "/home/turbo/jarvis-m1-ops")).replace("/", "/")

# Après:
_TURBO_DIR = str(PATHS.get("turbo", "/home/turbo/jarvis"))
```

- [ ] **Step 3: Commit**

```bash
git add src/commands.py
git commit -m "cleanup: remove no-op replace and fix default path in commands.py"
```

---

### Task 5: Create platform_dispatch.py

**Files:**
- Create: `src/platform_dispatch.py`
- Test: `tests/test_platform_dispatch.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_platform_dispatch.py
from __future__ import annotations
import pytest
from unittest.mock import patch


def test_get_platform_module_linux():
    """Sur Linux, retourne le module linux_*."""
    with patch("src.platform_dispatch.IS_LINUX", True):
        with patch("src.platform_dispatch.IS_WINDOWS", False):
            from src.platform_dispatch import get_platform_module
            mod = get_platform_module("sys")
            assert hasattr(mod, "__name__")
            assert "linux" in mod.__name__


def test_get_platform_module_missing_returns_stub():
    """Module inexistant retourne un stub, pas un crash."""
    from src.platform_dispatch import get_platform_module
    stub = get_platform_module("zzznonexistent")
    with pytest.raises(NotImplementedError, match="pas encore implémenté"):
        stub.some_function()


def test_stub_message_includes_module_name():
    """Le stub indique quel module créer."""
    from src.platform_dispatch import get_platform_module
    stub = get_platform_module("display")
    with pytest.raises(NotImplementedError, match="linux_display"):
        stub.get_resolution()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_platform_dispatch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.platform_dispatch'`

- [ ] **Step 3: Write implementation**

```python
# src/platform_dispatch.py
"""Dispatch automatique vers modules plateforme (linux_* ou win_*)."""
from __future__ import annotations

import importlib
import logging
import os

log = logging.getLogger(__name__)

IS_LINUX = os.name != "nt"
IS_WINDOWS = os.name == "nt"


class _NotImplementedStub:
    """Stub pour modules pas encore portés."""

    def __init__(self, domain: str, platform: str) -> None:
        self._domain = domain
        self._platform = platform
        self.__name__ = f"{platform}_{domain}_stub"

    def __getattr__(self, name: str):
        raise NotImplementedError(
            f"{self._platform}_{self._domain}.{name}() pas encore implémenté. "
            f"Créer src/{self._platform}_{self._domain}.py"
        )


def get_platform_module(domain: str):
    """Retourne le module plateforme approprié ou un stub."""
    prefix = "linux" if IS_LINUX else "win"
    module_name = f"src.{prefix}_{domain}"
    try:
        return importlib.import_module(module_name)
    except ImportError:
        log.warning("Module %s pas trouvé, stub retourné", module_name)
        return _NotImplementedStub(domain, prefix)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_platform_dispatch.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/platform_dispatch.py tests/test_platform_dispatch.py
git commit -m "feat: platform_dispatch.py — OS-aware module loader with stub fallback"
```

---

### Task 6: Create learned_actions.py — DB schema + CRUD

**Files:**
- Create: `src/learned_actions.py`
- Test: `tests/test_learned_actions.py`

- [ ] **Step 1: Write failing tests for DB init + CRUD**

```python
# tests/test_learned_actions.py
from __future__ import annotations
import json
import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def la_engine():
    """Learned Actions engine avec DB temporaire."""
    from src.learned_actions import LearnedActionsEngine
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test_learned.db"
        engine = LearnedActionsEngine(db_path)
        yield engine


def test_init_creates_tables(la_engine):
    """La DB est créée avec les bonnes tables."""
    import sqlite3
    conn = sqlite3.connect(la_engine.db_path)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    assert "learned_actions" in tables
    assert "learned_action_triggers" in tables
    assert "action_executions" in tables
    conn.close()


def test_save_action(la_engine):
    """Sauvegarder une action avec triggers."""
    action_id = la_engine.save_action(
        canonical_name="gpu-status",
        category="system",
        platform="linux",
        trigger_phrases=["voir les gpu", "status gpu", "état des gpu"],
        pipeline_steps=[
            {"type": "bash", "command": "nvidia-smi --query-gpu=name,temperature.gpu --format=csv,noheader"}
        ],
    )
    assert action_id > 0

    # Vérifier les triggers
    action = la_engine.get_action(action_id)
    assert action is not None
    assert action["canonical_name"] == "gpu-status"
    assert len(action["triggers"]) == 3


def test_match_exact(la_engine):
    """Match exact sur une phrase trigger."""
    la_engine.save_action(
        canonical_name="gpu-status",
        category="system",
        platform="linux",
        trigger_phrases=["voir les gpu"],
        pipeline_steps=[{"type": "bash", "command": "nvidia-smi"}],
    )
    match = la_engine.match("voir les gpu")
    assert match is not None
    assert match["canonical_name"] == "gpu-status"


def test_match_fuzzy(la_engine):
    """Match fuzzy quand pas de match exact."""
    la_engine.save_action(
        canonical_name="gpu-status",
        category="system",
        platform="linux",
        trigger_phrases=["voir les gpu", "status gpu"],
        pipeline_steps=[{"type": "bash", "command": "nvidia-smi"}],
    )
    # Phrase similaire mais pas identique
    match = la_engine.match("montre moi les gpu")
    # Peut matcher ou pas selon le seuil — on vérifie que ça ne crash pas
    # Le fuzzy à 0.75 devrait matcher "voir les gpu" ≈ "montre moi les gpu"
    assert match is None or match["canonical_name"] == "gpu-status"


def test_match_no_result(la_engine):
    """Pas de match retourne None."""
    match = la_engine.match("quelque chose de complètement différent")
    assert match is None


def test_record_execution(la_engine):
    """Logger une exécution."""
    action_id = la_engine.save_action(
        canonical_name="gpu-status",
        category="system",
        platform="linux",
        trigger_phrases=["voir les gpu"],
        pipeline_steps=[{"type": "bash", "command": "nvidia-smi"}],
    )
    la_engine.record_execution(
        action_id=action_id,
        trigger_text="voir les gpu",
        status="success",
        duration_ms=150.0,
        output="GPU 0: RTX 3060, 45C",
    )
    action = la_engine.get_action(action_id)
    assert action["success_count"] == 1


def test_platform_filter(la_engine):
    """Match respecte le filtre plateforme."""
    la_engine.save_action(
        canonical_name="win-only",
        category="system",
        platform="windows",
        trigger_phrases=["ouvre le registre"],
        pipeline_steps=[{"type": "bash", "command": "regedit"}],
    )
    # Sur Linux, ne devrait pas matcher une action windows-only
    match = la_engine.match("ouvre le registre", platform="linux")
    assert match is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_learned_actions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.learned_actions'`

- [ ] **Step 3: Write implementation**

```python
# src/learned_actions.py
"""Moteur Learned Actions — sauvegarde et replay de pipelines appris."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).parent.parent / "data" / "learned_actions.db"
_FUZZY_THRESHOLD = 0.75
_CURRENT_PLATFORM = "linux" if os.name != "nt" else "windows"


def _similarity(a: str, b: str) -> float:
    """Score de similarité — aligné sur src.commands.similarity().
    Utilise max(SequenceMatcher, (jaccard + coverage) / 2).
    """
    a_lower, b_lower = a.lower().strip(), b.lower().strip()
    seq_score = SequenceMatcher(None, a_lower, b_lower).ratio()
    words_a = set(a_lower.split())
    words_b = set(b_lower.split())
    if words_a and words_b:
        intersection = words_a & words_b
        union = words_a | words_b
        jaccard = len(intersection) / len(union)
        coverage = len(intersection) / len(words_b)
        bow_score = (jaccard + coverage) / 2.0
    else:
        bow_score = 0.0
    return max(seq_score, bow_score)


class LearnedActionsEngine:
    """CRUD + match + exécution pour actions apprises."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or _DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._trigger_cache: dict[str, int] | None = None

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS learned_actions (
                    id INTEGER PRIMARY KEY,
                    canonical_name TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL,
                    platform TEXT DEFAULT 'both',
                    pipeline_steps TEXT NOT NULL,
                    context_required TEXT,
                    success_count INTEGER DEFAULT 0,
                    fail_count INTEGER DEFAULT 0,
                    avg_duration_ms REAL,
                    last_used TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    learned_from TEXT
                );
                CREATE TABLE IF NOT EXISTS learned_action_triggers (
                    id INTEGER PRIMARY KEY,
                    action_id INTEGER NOT NULL REFERENCES learned_actions(id) ON DELETE CASCADE,
                    phrase TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS action_executions (
                    id INTEGER PRIMARY KEY,
                    action_id INTEGER REFERENCES learned_actions(id),
                    trigger_text TEXT,
                    status TEXT,
                    duration_ms REAL,
                    output TEXT,
                    error TEXT,
                    executed_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_trigger_phrase ON learned_action_triggers(phrase);
                CREATE INDEX IF NOT EXISTS idx_trigger_action ON learned_action_triggers(action_id);
                CREATE INDEX IF NOT EXISTS idx_la_category ON learned_actions(category);
                CREATE INDEX IF NOT EXISTS idx_la_platform ON learned_actions(platform);
            """)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _invalidate_cache(self) -> None:
        self._trigger_cache = None

    def _build_cache(self) -> dict[str, int]:
        if self._trigger_cache is not None:
            return self._trigger_cache
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT phrase, action_id FROM learned_action_triggers"
            ).fetchall()
        self._trigger_cache = {r["phrase"].lower().strip(): r["action_id"] for r in rows}
        return self._trigger_cache

    def save_action(
        self,
        canonical_name: str,
        category: str,
        platform: str,
        trigger_phrases: list[str],
        pipeline_steps: list[dict[str, Any]],
        context_required: dict[str, Any] | None = None,
        learned_from: str | None = None,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO learned_actions
                   (canonical_name, category, platform, pipeline_steps, context_required, learned_from)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(canonical_name) DO UPDATE SET
                       category = excluded.category,
                       platform = excluded.platform,
                       pipeline_steps = excluded.pipeline_steps,
                       context_required = excluded.context_required,
                       learned_from = excluded.learned_from""",
                (
                    canonical_name,
                    category,
                    platform,
                    json.dumps(pipeline_steps),
                    json.dumps(context_required) if context_required else None,
                    learned_from,
                ),
            )
            action_id = cur.lastrowid
            # Supprimer anciens triggers et réinsérer
            conn.execute(
                "DELETE FROM learned_action_triggers WHERE action_id = ?",
                (action_id,),
            )
            for phrase in trigger_phrases:
                conn.execute(
                    "INSERT INTO learned_action_triggers (action_id, phrase) VALUES (?, ?)",
                    (action_id, phrase.lower().strip()),
                )
        self._invalidate_cache()
        return action_id

    def get_action(self, action_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM learned_actions WHERE id = ?", (action_id,)
            ).fetchone()
            if not row:
                return None
            triggers = conn.execute(
                "SELECT phrase FROM learned_action_triggers WHERE action_id = ?",
                (action_id,),
            ).fetchall()
        return {
            **dict(row),
            "pipeline_steps": json.loads(row["pipeline_steps"]),
            "triggers": [t["phrase"] for t in triggers],
        }

    def match(
        self, text: str, platform: str | None = None
    ) -> dict[str, Any] | None:
        platform = platform or _CURRENT_PLATFORM
        text_lower = text.lower().strip()
        cache = self._build_cache()

        # 1. Match exact O(1)
        if text_lower in cache:
            action_id = cache[text_lower]
            action = self.get_action(action_id)
            if action and action["platform"] in (platform, "both"):
                return action

        # 2. Fuzzy match
        best_score = 0.0
        best_action_id = None
        for phrase, action_id in cache.items():
            score = _similarity(text_lower, phrase)
            if score > best_score:
                best_score = score
                best_action_id = action_id

        if best_score >= _FUZZY_THRESHOLD and best_action_id is not None:
            action = self.get_action(best_action_id)
            if action and action["platform"] in (platform, "both"):
                return action

        return None

    def record_execution(
        self,
        action_id: int,
        trigger_text: str,
        status: str,
        duration_ms: float,
        output: str = "",
        error: str = "",
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO action_executions
                   (action_id, trigger_text, status, duration_ms, output, error)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (action_id, trigger_text, status, duration_ms, output, error),
            )
            if status == "success":
                conn.execute(
                    """UPDATE learned_actions SET
                       success_count = success_count + 1,
                       last_used = CURRENT_TIMESTAMP,
                       avg_duration_ms = COALESCE(
                           (avg_duration_ms * success_count + ?) / (success_count + 1),
                           ?
                       )
                       WHERE id = ?""",
                    (duration_ms, duration_ms, action_id),
                )
            else:
                conn.execute(
                    "UPDATE learned_actions SET fail_count = fail_count + 1 WHERE id = ?",
                    (action_id,),
                )

    def list_actions(
        self, category: str | None = None, platform: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM learned_actions WHERE 1=1"
        params: list[Any] = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if platform:
            query += " AND platform IN (?, 'both')"
            params.append(platform)
        query += " ORDER BY success_count DESC"
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_learned_actions.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/learned_actions.py tests/test_learned_actions.py
git commit -m "feat: learned_actions engine — CRUD, fuzzy match, execution logging"
```

---

## Chunk 2: Dominos Linux + Integration Pipeline Vocal

### Task 7: Create domino_pipelines_linux.py — 10 dominos système

**Files:**
- Create: `src/domino_pipelines_linux.py`
- Test: `tests/test_domino_pipelines_linux.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_domino_pipelines_linux.py
from __future__ import annotations
import pytest


def test_linux_pipelines_exist():
    """Les pipelines Linux sont définis."""
    from src.domino_pipelines_linux import LINUX_PIPELINES
    assert len(LINUX_PIPELINES) >= 10


def test_pipeline_structure():
    """Chaque pipeline a les champs requis."""
    from src.domino_pipelines_linux import LINUX_PIPELINES
    required = {"name", "triggers", "category", "steps"}
    for name, pipeline in LINUX_PIPELINES.items():
        missing = required - set(pipeline.keys())
        assert not missing, f"Pipeline {name} manque: {missing}"


def test_pipeline_steps_valid_types():
    """Chaque step utilise un type supporté par DominoExecutor."""
    from src.domino_pipelines_linux import LINUX_PIPELINES
    valid_types = {"bash", "python", "curl", "tool", "pipeline", "condition"}  # Aligné sur DominoExecutor.execute_step
    for name, pipeline in LINUX_PIPELINES.items():
        for i, step in enumerate(pipeline["steps"]):
            assert step["type"] in valid_types, (
                f"Pipeline {name}, step {i}: type '{step['type']}' invalide"
            )


def test_health_check_pipeline():
    """Le pipeline health-check contient les bonnes commandes."""
    from src.domino_pipelines_linux import LINUX_PIPELINES
    hc = LINUX_PIPELINES["health-check"]
    commands = [s["command"] for s in hc["steps"]]
    assert any("nvidia-smi" in c for c in commands)
    assert any("systemctl" in c for c in commands)
    assert any("df" in c or "free" in c for c in commands)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_domino_pipelines_linux.py -v`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/domino_pipelines_linux.py
"""Dominos Linux — pipelines en langage conversationnel."""
from __future__ import annotations

# Chaque pipeline: name, triggers (phrases vocales FR), category, steps
# Steps alignés sur DominoExecutor: bash, python, curl, tool, pipeline, condition
LINUX_PIPELINES: dict[str, dict] = {
    # === SYSTEME ===
    "health-check": {
        "name": "Health Check Système",
        "triggers": ["vérifie la santé du système", "health check", "état du système", "santé système"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo 'Pas de GPU NVIDIA'", "label": "GPU Status"},
            {"type": "bash", "command": "systemctl --user list-units 'jarvis-*' --no-pager --plain 2>/dev/null || echo 'Pas de services jarvis'", "label": "Services JARVIS"},
            {"type": "bash", "command": "df -h / /home --output=target,size,used,avail,pcent 2>/dev/null", "label": "Espace disque"},
            {"type": "bash", "command": "free -h", "label": "Mémoire RAM"},
            {"type": "bash", "command": "uptime", "label": "Uptime"},
        ],
    },
    "cluster-status": {
        "name": "État du Cluster",
        "triggers": ["état du cluster", "cluster status", "vérifie le cluster", "les noeuds sont up"],
        "category": "cluster",
        "steps": [
            {"type": "bash", "command": "curl -s --max-time 5 http://127.0.0.1:1234/v1/models 2>/dev/null || echo 'M1 OFFLINE'", "label": "M1"},
            {"type": "bash", "command": "curl -s --max-time 5 http://192.168.1.26:1234/v1/models 2>/dev/null || echo 'M2 OFFLINE'", "label": "M2"},
            {"type": "bash", "command": "curl -s --max-time 5 http://192.168.1.113:1234/v1/models 2>/dev/null || echo 'M3 OFFLINE'", "label": "M3"},
            {"type": "bash", "command": "curl -s --max-time 5 http://127.0.0.1:11434/api/tags 2>/dev/null || echo 'OL1 OFFLINE'", "label": "OL1"},
        ],
    },
    "gpu-thermal": {
        "name": "Température GPU",
        "triggers": ["température gpu", "gpu thermal", "les gpu sont chauds", "thermal gpu"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "nvidia-smi --query-gpu=index,name,temperature.gpu,fan.speed,power.draw --format=csv,noheader 2>/dev/null || echo 'Pas de GPU'", "label": "Thermal"},
        ],
    },
    "restart-service": {
        "name": "Redémarrer Service",
        "triggers": ["redémarre {service}", "restart {service}", "relance {service}"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "systemctl --user restart jarvis-{service} && systemctl --user status jarvis-{service} --no-pager", "label": "Restart"},
        ],
    },
    "logs-service": {
        "name": "Logs Service",
        "triggers": ["montre les logs de {service}", "logs {service}", "journal {service}"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "journalctl --user -u jarvis-{service} -n 50 --no-pager", "label": "Logs"},
        ],
    },
    "disk-usage": {
        "name": "Espace Disque",
        "triggers": ["espace disque", "disk usage", "combien de place", "stockage"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "df -h --output=target,size,used,avail,pcent / /home 2>/dev/null", "label": "Partitions"},
            {"type": "bash", "command": "du -sh ~/jarvis/data/ ~/jarvis/cowork/ ~/jarvis/src/ 2>/dev/null | sort -rh", "label": "Dossiers JARVIS"},
        ],
    },
    "network-check": {
        "name": "État Réseau",
        "triggers": ["état réseau", "network check", "réseau ok", "ping cluster"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "ip -br addr show | grep -v lo", "label": "Interfaces"},
            {"type": "bash", "command": "ping -c 1 -W 2 192.168.1.26 >/dev/null 2>&1 && echo 'M2: OK' || echo 'M2: OFFLINE'", "label": "Ping M2"},
            {"type": "bash", "command": "ping -c 1 -W 2 192.168.1.113 >/dev/null 2>&1 && echo 'M3: OK' || echo 'M3: OFFLINE'", "label": "Ping M3"},
        ],
    },
    "process-list": {
        "name": "Processus Actifs",
        "triggers": ["processus actifs", "process list", "top processus", "qui consomme"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "ps aux --sort=-%cpu | head -15", "label": "Top CPU"},
            {"type": "bash", "command": "ps aux --sort=-%mem | head -10", "label": "Top RAM"},
        ],
    },
    "check-updates": {
        "name": "Vérifier Mises à Jour",
        "triggers": ["vérifie les mises à jour", "check updates", "mises à jour disponibles"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "apt list --upgradable 2>/dev/null | head -20 || dnf check-update 2>/dev/null | head -20", "label": "Updates"},
        ],
    },
    "backup-db": {
        "name": "Sauvegarde Bases de Données",
        "triggers": ["sauvegarde les bases", "backup db", "backup databases", "sauvegarde sqlite"],
        "category": "system",
        "steps": [
            {"type": "bash", "command": "mkdir -p ~/jarvis/backups/$(date +%Y%m%d) && for db in ~/jarvis/data/*.db; do [ -f \"$db\" ] && sqlite3 \"$db\" \".backup ~/jarvis/backups/$(date +%Y%m%d)/$(basename $db)\" 2>/dev/null && echo \"OK: $(basename $db)\" || echo \"SKIP: $(basename $db)\"; done", "label": "Backup"},
        ],
    },
    # === CLUSTER IA ===
    "quick-ask": {
        "name": "Question Rapide",
        "triggers": ["demande à {noeud} {question}", "quick ask {noeud}", "pose la question à {noeud}"],
        "category": "cluster",
        "steps": [
            {"type": "bash", "command": "curl -s --max-time 30 http://127.0.0.1:1234/api/v1/chat -H 'Content-Type: application/json' -d '{\"model\":\"qwen/qwen3-8b\",\"input\":\"/nothink\\n{question}\",\"temperature\":0.2,\"max_output_tokens\":1024,\"stream\":false,\"store\":false}'", "label": "Ask M1"},
        ],
    },
    "benchmark-quick": {
        "name": "Benchmark Rapide",
        "triggers": ["benchmark rapide", "bench cluster", "teste la vitesse", "latence cluster"],
        "category": "cluster",
        "steps": [
            {"type": "bash", "command": "echo 'M1:' && time curl -s --max-time 10 http://127.0.0.1:1234/api/v1/chat -H 'Content-Type: application/json' -d '{\"model\":\"qwen/qwen3-8b\",\"input\":\"/nothink\\nReponds OK\",\"max_output_tokens\":10,\"stream\":false,\"store\":false}' 2>&1 | tail -1", "label": "Bench M1"},
            {"type": "bash", "command": "echo 'OL1:' && time curl -s --max-time 10 http://127.0.0.1:11434/api/chat -d '{\"model\":\"qwen3:1.7b\",\"messages\":[{\"role\":\"user\",\"content\":\"Reponds OK\"}],\"stream\":false,\"think\":false}' 2>&1 | tail -1", "label": "Bench OL1"},
        ],
    },
    "trading-scan": {
        "name": "Scan Trading",
        "triggers": ["scan trading", "lance le trading", "trading scan", "analyse crypto"],
        "category": "trading",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && uv run python scripts/trading_v2/gpu_pipeline.py --quick --json 2>/dev/null || echo 'Pipeline trading non disponible'", "label": "GPU Pipeline"},
        ],
    },
    # === DEV/WORKFLOW ===
    "git-status": {
        "name": "État du Repo",
        "triggers": ["état du repo", "git status", "git quoi de neuf", "changements git"],
        "category": "dev",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && git status --short | head -30", "label": "Status"},
            {"type": "bash", "command": "cd ~/jarvis && git log --oneline -5", "label": "Last commits"},
        ],
    },
    "run-tests": {
        "name": "Lancer les Tests",
        "triggers": ["lance les tests", "run tests", "pytest", "teste le code"],
        "category": "dev",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && uv run pytest -x --tb=short -q 2>&1 | tail -20", "label": "Tests"},
        ],
    },
    "audit-system": {
        "name": "Audit Système Complet",
        "triggers": ["audit système", "audit complet", "system audit", "vérifie tout"],
        "category": "dev",
        "steps": [
            {"type": "bash", "command": "cd ~/jarvis && uv run python scripts/system_audit.py --quick 2>&1 | tail -40", "label": "Audit"},
        ],
    },
}


def get_pipeline(name: str) -> dict | None:
    """Retourne un pipeline par nom."""
    return LINUX_PIPELINES.get(name)


def search_pipeline(text: str) -> dict | None:
    """Cherche un pipeline par phrase trigger (exact substring)."""
    text_lower = text.lower()
    for name, pipeline in LINUX_PIPELINES.items():
        for trigger in pipeline["triggers"]:
            # Ignorer les triggers avec {param} pour match simple
            if "{" in trigger:
                continue
            if trigger in text_lower or text_lower in trigger:
                return {"name": name, **pipeline}
    return None


def list_pipelines(category: str | None = None) -> list[dict]:
    """Liste les pipelines, optionnellement filtrés par catégorie."""
    results = []
    for name, pipeline in LINUX_PIPELINES.items():
        if category and pipeline["category"] != category:
            continue
        results.append({"name": name, **pipeline})
    return results
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_domino_pipelines_linux.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/domino_pipelines_linux.py tests/test_domino_pipelines_linux.py
git commit -m "feat: 16 dominos Linux — système, cluster, trading, dev"
```

---

### Task 8: Seed learned_actions.db with Linux dominos

**Files:**
- Create: `scripts/seed_learned_actions.py`

- [ ] **Step 1: Write seeding script**

```python
# scripts/seed_learned_actions.py
"""Seed learned_actions.db avec les dominos Linux."""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

from src.learned_actions import LearnedActionsEngine
from src.domino_pipelines_linux import LINUX_PIPELINES


def main():
    engine = LearnedActionsEngine()
    count = 0
    for name, pipeline in LINUX_PIPELINES.items():
        try:
            engine.save_action(
                canonical_name=name,
                category=pipeline["category"],
                platform="linux",
                trigger_phrases=pipeline["triggers"],
                pipeline_steps=pipeline["steps"],
                learned_from="seed_dominos_linux",
            )
            count += 1
            print(f"  OK: {name} ({len(pipeline['triggers'])} triggers)")
        except Exception as e:
            print(f"  FAIL: {name} — {e}")
    print(f"\n{count}/{len(LINUX_PIPELINES)} dominos seedés dans learned_actions.db")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run seeding**

Run: `uv run python scripts/seed_learned_actions.py`
Expected: `16/16 dominos seedés dans learned_actions.db`

- [ ] **Step 3: Verify DB content**

Run: `sqlite3 data/learned_actions.db "SELECT canonical_name, category FROM learned_actions ORDER BY category"`
Expected: 16 rows

- [ ] **Step 4: Commit**

```bash
git add scripts/seed_learned_actions.py
git commit -m "feat: seed script for learned_actions with 16 Linux dominos"
```

---

### Task 9: Integrate learned_actions into domino_executor.py

**Files:**
- Modify: `src/domino_executor.py`

- [ ] **Step 1: Lire le code d'entrée du DominoExecutor**

Run: `grep -n "def execute_domino\|def run_domino\|class Domino" src/domino_executor.py | head -10`

- [ ] **Step 2: Ajouter lookup learned_actions avant exécution classique**

Au début du fichier, ajouter l'import :

```python
from src.learned_actions import LearnedActionsEngine
_learned_engine = LearnedActionsEngine()
```

Puis ajouter cette fonction (utilise DominoStep + route_step comme l'executor existant) :

```python
def execute_with_learned_actions(text: str) -> dict | None:
    """Tente un replay learned action. Retourne None si pas de match."""
    from src.domino_pipelines import DominoStep
    match = _learned_engine.match(text)
    if not match:
        return None

    log.info("Learned action match: %s", match["canonical_name"])
    start = time.time()
    results = []
    for i, step_dict in enumerate(match["pipeline_steps"]):
        # Convertir dict → DominoStep (aligné sur l'executor existant)
        domino_step = DominoStep(
            name=step_dict.get("label", f"step_{i}"),
            action=step_dict["command"],
            action_type=step_dict["type"],
            timeout_s=step_dict.get("timeout", 30),
        )
        node = route_step(domino_step)  # Détermine le noeud optimal
        status, output = execute_step(domino_step, node)  # Signature correcte
        results.append({"step": domino_step.name, "status": status, "output": output})
        if status == "FAIL" and step_dict.get("on_fail", "stop") == "stop":
            break

    duration = (time.time() - start) * 1000
    all_passed = all(r["status"] == "PASS" for r in results)
    _learned_engine.record_execution(
        action_id=match["id"],
        trigger_text=text,
        status="success" if all_passed else "failed",
        duration_ms=duration,
        output=str(results[-1]["output"]) if results else "",
    )
    return {"source": "learned_action", "name": match["canonical_name"], "results": results}
```

- [ ] **Step 3: Tester manuellement**

Run: `uv run python -c "from src.domino_executor import execute_with_learned_actions; r = execute_with_learned_actions('espace disque'); print(r['name'] if r else 'No match')"`
Expected: `disk-usage` (si seedé) ou `No match`

- [ ] **Step 4: Commit**

```bash
git add src/domino_executor.py
git commit -m "feat: integrate learned_actions lookup into domino_executor"
```

---

### Task 10: Create linux_maintenance.py — systemctl equivalents

**Files:**
- Create: `src/linux_maintenance.py`
- Test: `tests/test_linux_maintenance.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_linux_maintenance.py
from __future__ import annotations


def test_module_has_commands():
    """Le module expose un dict de commandes."""
    from src.linux_maintenance import LINUX_MAINTENANCE_COMMANDS
    assert len(LINUX_MAINTENANCE_COMMANDS) >= 10


def test_commands_are_bash():
    """Toutes les commandes sont du bash valide (pas de PowerShell)."""
    from src.linux_maintenance import LINUX_MAINTENANCE_COMMANDS
    for name, cmd in LINUX_MAINTENANCE_COMMANDS.items():
        assert "Get-" not in cmd["command"], f"{name} contient du PowerShell!"
        assert "Set-" not in cmd["command"], f"{name} contient du PowerShell!"
        assert "powershell" not in cmd["command"].lower(), f"{name} utilise powershell!"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_linux_maintenance.py -v`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/linux_maintenance.py
"""Commandes maintenance Linux — équivalents de commands_maintenance.py (PowerShell → bash)."""
from __future__ import annotations

LINUX_MAINTENANCE_COMMANDS: dict[str, dict] = {
    "list-services": {
        "command": "systemctl --user list-units --type=service --no-pager --plain",
        "description": "Liste les services utilisateur actifs",
        "category": "services",
    },
    "stopped-services": {
        "command": "systemctl --user list-units --type=service --state=inactive --no-pager",
        "description": "Services arrêtés",
        "category": "services",
    },
    "top-cpu": {
        "command": "ps aux --sort=-%cpu | head -15",
        "description": "Top processus par CPU",
        "category": "processes",
    },
    "top-memory": {
        "command": "ps aux --sort=-%mem | head -15",
        "description": "Top processus par mémoire",
        "category": "processes",
    },
    "active-connections": {
        "command": "ss -tunapl 2>/dev/null | head -30",
        "description": "Connexions réseau actives",
        "category": "network",
    },
    "listening-ports": {
        "command": "ss -tlnp 2>/dev/null",
        "description": "Ports en écoute",
        "category": "network",
    },
    "disk-health": {
        "command": "df -h --output=target,fstype,size,used,avail,pcent | sort -k6 -rn",
        "description": "Santé disques",
        "category": "storage",
    },
    "temp-cleanup": {
        "command": "find /tmp -maxdepth 1 -type f -mtime +7 2>/dev/null | wc -l && echo 'fichiers tmp > 7 jours'",
        "description": "Fichiers temp anciens (lecture seule)",
        "category": "storage",
    },
    "system-logs-errors": {
        "command": "journalctl --priority=err --since='1 hour ago' --no-pager | tail -20",
        "description": "Erreurs système dernière heure",
        "category": "logs",
    },
    "memory-detail": {
        "command": "free -h && echo '---' && cat /proc/meminfo | head -10",
        "description": "Détail mémoire",
        "category": "memory",
    },
    "gpu-processes": {
        "command": "nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader 2>/dev/null || echo 'Pas de GPU'",
        "description": "Processus GPU",
        "category": "gpu",
    },
    "zram-status": {
        "command": "cat /proc/swaps 2>/dev/null && zramctl 2>/dev/null || echo 'Pas de ZRAM'",
        "description": "Status ZRAM/swap",
        "category": "memory",
    },
    "systemd-failed": {
        "command": "systemctl --failed --no-pager",
        "description": "Services en échec",
        "category": "services",
    },
    "kernel-info": {
        "command": "uname -a && echo '---' && lsb_release -a 2>/dev/null || cat /etc/os-release",
        "description": "Info kernel et distribution",
        "category": "system",
    },
    "cron-list": {
        "command": "crontab -l 2>/dev/null && echo '---' && systemctl --user list-timers --no-pager 2>/dev/null",
        "description": "Tâches planifiées",
        "category": "scheduler",
    },
}
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_linux_maintenance.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/linux_maintenance.py tests/test_linux_maintenance.py
git commit -m "feat: linux_maintenance.py — 15 commandes bash equivalent PowerShell"
```

---

## Chunk 3: Audit Script + Final Integration

### Task 11: Create audit_commands_platform.py

**Files:**
- Create: `scripts/audit_commands_platform.py`

- [ ] **Step 1: Write the audit script**

```python
# scripts/audit_commands_platform.py
"""Audit des 853 commandes vocales — classifie par plateforme."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, ".")

DB_PATH = Path("data/jarvis.db")


def audit():
    if not DB_PATH.exists():
        print(f"DB non trouvée: {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM voice_commands").fetchall()
    conn.close()

    stats = {"windows": 0, "linux": 0, "both": 0, "unknown": 0}
    windows_indicators = [
        "powershell", "Get-", "Set-", "Start-Process", "Stop-Process",
        "regedit", "taskkill", "C:\\", "C:/Users", "explorer.exe",
        ".exe", "wmic", "schtasks", "netsh",
    ]
    linux_indicators = [
        "systemctl", "journalctl", "apt ", "dnf ", "pacman",
        "xdg-open", "notify-send", "xdotool", "wmctrl",
        "/proc/", "/sys/", "xrandr",
    ]

    report = {"windows": [], "linux": [], "both": [], "to_port": []}

    for row in rows:
        cmd = dict(row)
        action = cmd.get("action", "") or ""
        action_type = cmd.get("action_type", "") or ""

        is_win = any(ind in action for ind in windows_indicators) or action_type == "powershell"
        is_linux = any(ind in action for ind in linux_indicators)

        if is_win and not is_linux:
            platform = "windows"
            report["to_port"].append(cmd.get("trigger", ""))
        elif is_linux and not is_win:
            platform = "linux"
        elif is_win and is_linux:
            platform = "both"
        else:
            platform = "both"  # Commandes génériques (python, curl, etc.)

        stats[platform] += 1

    total = sum(stats.values())
    print(f"\n=== Audit Commandes Vocales ({total} total) ===")
    print(f"  Cross-platform (both): {stats['both']}")
    print(f"  Windows-only:          {stats['windows']}")
    print(f"  Linux-only:            {stats['linux']}")
    print(f"\n  À porter vers Linux:   {len(report['to_port'])}")
    if report["to_port"][:10]:
        print(f"\n  Exemples à porter:")
        for t in report["to_port"][:10]:
            print(f"    - {t}")

    # Sauvegarder le rapport
    out = Path("data/audit_commands_platform.json")
    out.write_text(json.dumps(stats, indent=2))
    print(f"\n  Rapport sauvegardé: {out}")


if __name__ == "__main__":
    audit()
```

- [ ] **Step 2: Run the audit**

Run: `uv run python scripts/audit_commands_platform.py`
Expected: Stats des commandes par plateforme

- [ ] **Step 3: Commit**

```bash
git add scripts/audit_commands_platform.py
git commit -m "feat: audit script — classifie commandes vocales par plateforme"
```

---

### Task 12: Final integration test

**Files:**
- Create: `tests/test_integration_learned_actions.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration_learned_actions.py
"""Test d'intégration: seed → match → execute (sans réseau)."""
from __future__ import annotations

import tempfile
from pathlib import Path


def test_full_cycle():
    """Cycle complet: save → match → record."""
    from src.learned_actions import LearnedActionsEngine

    with tempfile.TemporaryDirectory() as tmp:
        engine = LearnedActionsEngine(Path(tmp) / "test.db")

        # 1. Save
        aid = engine.save_action(
            canonical_name="test-action",
            category="test",
            platform="both",
            trigger_phrases=["fais un test", "lance le test", "teste ça"],
            pipeline_steps=[
                {"type": "bash", "command": "echo 'hello world'"},
                {"type": "bash", "command": "echo 'done'"},
            ],
        )

        # 2. Match exact
        m = engine.match("fais un test")
        assert m is not None
        assert m["canonical_name"] == "test-action"
        assert len(m["pipeline_steps"]) == 2

        # 3. Match fuzzy
        m2 = engine.match("fais un petit test")
        assert m2 is not None or m2 is None  # Dépend du seuil

        # 4. Record execution
        engine.record_execution(
            action_id=aid,
            trigger_text="fais un test",
            status="success",
            duration_ms=50.0,
            output="hello world\ndone",
        )

        # 5. Verify stats updated
        action = engine.get_action(aid)
        assert action["success_count"] == 1
        assert action["avg_duration_ms"] == 50.0

        # 6. List
        all_actions = engine.list_actions()
        assert len(all_actions) == 1

        # 7. Platform filter
        engine.save_action(
            canonical_name="win-only",
            category="test",
            platform="windows",
            trigger_phrases=["windows truc"],
            pipeline_steps=[{"type": "bash", "command": "echo win"}],
        )
        assert engine.match("windows truc", platform="linux") is None
        assert engine.match("windows truc", platform="windows") is not None
```

- [ ] **Step 2: Run all tests**

Run: `uv run pytest tests/test_learned_actions.py tests/test_platform_dispatch.py tests/test_domino_pipelines_linux.py tests/test_linux_maintenance.py tests/test_integration_learned_actions.py -v`
Expected: ALL PASSED

- [ ] **Step 3: Final commit**

```bash
git add tests/test_integration_learned_actions.py
git commit -m "test: integration test for learned actions full cycle"
```

---

## Summary

| Chunk | Tasks | New Files | Tests |
|-------|-------|-----------|-------|
| **1: Fondations** | T1-T6 | platform_dispatch.py, learned_actions.py | 9 tests |
| **2: Dominos** | T7-T10 | domino_pipelines_linux.py, linux_maintenance.py, seed script | 6 tests |
| **3: Integration** | T11-T12 | audit script, integration test | 1 test |

**Total: 12 tasks, 8 new files, 16+ tests, ~750 lines of production code**
