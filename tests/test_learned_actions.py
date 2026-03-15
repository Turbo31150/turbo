from __future__ import annotations
import json
import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def la_engine():
    from src.learned_actions import LearnedActionsEngine
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test_learned.db"
        engine = LearnedActionsEngine(db_path)
        yield engine


def test_init_creates_tables(la_engine):
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
    action = la_engine.get_action(action_id)
    assert action is not None
    assert action["canonical_name"] == "gpu-status"
    assert len(action["triggers"]) == 3


def test_match_exact(la_engine):
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


def test_match_no_result(la_engine):
    match = la_engine.match("quelque chose de complètement différent")
    assert match is None


def test_record_execution(la_engine):
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
    la_engine.save_action(
        canonical_name="win-only",
        category="system",
        platform="windows",
        trigger_phrases=["ouvre le registre"],
        pipeline_steps=[{"type": "bash", "command": "regedit"}],
    )
    match = la_engine.match("ouvre le registre", platform="linux")
    assert match is None


def test_parameterized_match(la_engine):
    """Match avec paramètres {service}."""
    la_engine.save_action(
        canonical_name="restart-svc",
        category="system",
        platform="both",
        trigger_phrases=["redémarre {service}", "restart {service}"],
        pipeline_steps=[{"type": "bash", "command": "systemctl restart {service}"}],
    )
    match = la_engine.match("redémarre proxy")
    assert match is not None
    assert match["canonical_name"] == "restart-svc"
    assert match["params"]["service"] == "proxy"


def test_parameterized_match_multiple_params(la_engine):
    """Match avec plusieurs paramètres."""
    la_engine.save_action(
        canonical_name="ask-node",
        category="system",
        platform="both",
        trigger_phrases=["demande à {noeud} {question}"],
        pipeline_steps=[{"type": "bash", "command": "echo {noeud} {question}"}],
    )
    match = la_engine.match("demande à m2 quel est le status")
    assert match is not None
    assert match["canonical_name"] == "ask-node"
    assert match["params"]["noeud"] == "m2"
    assert "status" in match["params"]["question"]


def test_parameterized_no_match(la_engine):
    """Parameterized match ne matche pas si le texte ne correspond pas."""
    la_engine.save_action(
        canonical_name="restart-svc",
        category="system",
        platform="both",
        trigger_phrases=["redémarre {service}"],
        pipeline_steps=[{"type": "bash", "command": "systemctl restart {service}"}],
    )
    match = la_engine.match("arrête le service proxy")
    assert match is None


def test_save_preserves_stats_on_reseed(la_engine):
    """INSERT ON CONFLICT ne reset pas les stats."""
    aid = la_engine.save_action(
        canonical_name="test-action",
        category="test",
        platform="both",
        trigger_phrases=["test"],
        pipeline_steps=[{"type": "bash", "command": "echo ok"}],
    )
    la_engine.record_execution(aid, "test", "success", 100.0)
    # Re-seed same action
    la_engine.save_action(
        canonical_name="test-action",
        category="test",
        platform="both",
        trigger_phrases=["test", "test2"],
        pipeline_steps=[{"type": "bash", "command": "echo ok v2"}],
    )
    action = la_engine.get_action(aid)
    assert action["success_count"] == 1  # Preserved, not reset


def test_auto_learn(la_engine):
    """Auto-apprentissage crée une nouvelle action."""
    aid = la_engine.auto_learn_from_execution(
        trigger_text="montre les logs nginx",
        steps_executed=[{"type": "bash", "command": "journalctl -u nginx -n 50"}],
        category="system",
    )
    assert aid is not None
    action = la_engine.get_action(aid)
    assert action is not None
    assert "nginx" in action["canonical_name"] or "logs" in action["canonical_name"]


def test_auto_learn_no_duplicate(la_engine):
    """Auto-learn ne crée pas de doublon si action similaire existe."""
    la_engine.save_action(
        canonical_name="show-logs",
        category="system",
        platform="both",
        trigger_phrases=["montre les logs"],
        pipeline_steps=[{"type": "bash", "command": "journalctl -n 50"}],
    )
    aid = la_engine.auto_learn_from_execution(
        trigger_text="montre les logs",
        steps_executed=[{"type": "bash", "command": "journalctl -n 50"}],
    )
    assert aid is None  # Already exists


def test_recent_actions(la_engine):
    """recent_actions retourne les plus récentes."""
    for i in range(5):
        la_engine.save_action(
            canonical_name=f"action-{i}",
            category="test",
            platform="both",
            trigger_phrases=[f"test {i}"],
            pipeline_steps=[{"type": "bash", "command": f"echo {i}"}],
        )
    recent = la_engine.recent_actions(3)
    assert len(recent) == 3
