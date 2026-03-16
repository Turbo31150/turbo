"""Test d'intégration: save → match → execute cycle complet."""
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

        # 3. Record execution
        engine.record_execution(
            action_id=aid,
            trigger_text="fais un test",
            status="success",
            duration_ms=50.0,
            output="hello world\ndone",
        )

        # 4. Verify stats updated
        action = engine.get_action(aid)
        assert action["success_count"] == 1
        assert action["avg_duration_ms"] == 50.0

        # 5. List
        all_actions = engine.list_actions()
        assert len(all_actions) == 1

        # 6. Platform filter
        engine.save_action(
            canonical_name="win-only",
            category="test",
            platform="windows",
            trigger_phrases=["windows truc"],
            pipeline_steps=[{"type": "bash", "command": "echo win"}],
        )
        assert engine.match("windows truc", platform="linux") is None
        assert engine.match("windows truc", platform="windows") is not None


def test_similarity_alignment():
    """Vérifie que la similarité est alignée sur commands.py."""
    from src.learned_actions import _similarity
    # "scan trading" vs "trading scan" — bag-of-words should score high
    score = _similarity("scan trading", "trading scan")
    assert score >= 0.65, f"Score trop bas: {score}"
    # Complètement différent
    score2 = _similarity("bonjour monde", "gpu thermal check")
    assert score2 < 0.3, f"Score trop haut: {score2}"
