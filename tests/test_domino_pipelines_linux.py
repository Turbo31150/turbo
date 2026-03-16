from __future__ import annotations
import pytest


def test_linux_pipelines_exist():
    from src.domino_pipelines_linux import LINUX_PIPELINES
    assert len(LINUX_PIPELINES) >= 45


def test_pipeline_structure():
    from src.domino_pipelines_linux import LINUX_PIPELINES
    required = {"name", "triggers", "category", "steps"}
    for name, pipeline in LINUX_PIPELINES.items():
        missing = required - set(pipeline.keys())
        assert not missing, f"Pipeline {name} manque: {missing}"


def test_pipeline_steps_valid_types():
    from src.domino_pipelines_linux import LINUX_PIPELINES
    valid_types = {"bash", "python", "curl", "tool", "pipeline", "condition"}
    for name, pipeline in LINUX_PIPELINES.items():
        for i, step in enumerate(pipeline["steps"]):
            assert step["type"] in valid_types, f"Pipeline {name}, step {i}: type '{step['type']}' invalide"


def test_health_check_pipeline():
    from src.domino_pipelines_linux import LINUX_PIPELINES
    hc = LINUX_PIPELINES["health-check"]
    commands = [s["command"] for s in hc["steps"]]
    assert any("nvidia-smi" in c for c in commands)
    assert any("systemctl" in c for c in commands)
    assert any("df" in c or "free" in c for c in commands)


def test_no_powershell_in_steps():
    from src.domino_pipelines_linux import LINUX_PIPELINES
    for name, pipeline in LINUX_PIPELINES.items():
        for step in pipeline["steps"]:
            assert "Get-" not in step["command"], f"{name}: PowerShell detecté"
            assert "Set-" not in step["command"], f"{name}: PowerShell detecté"


def test_search_pipeline():
    from src.domino_pipelines_linux import search_pipeline
    result = search_pipeline("espace disque")
    assert result is not None
    assert result["key"] == "disk-usage"


def test_list_pipelines_by_category():
    from src.domino_pipelines_linux import list_pipelines
    system = list_pipelines("system")
    assert len(system) >= 5
    cluster = list_pipelines("cluster")
    assert len(cluster) >= 2
