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
