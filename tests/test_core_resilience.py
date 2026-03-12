import pytest
import os
import subprocess
from pathlib import Path
from src.config import config, PATHS

def test_linux_paths():
    """Vérifier que tous les chemins dans la config sont POSIX."""
    for key, path in PATHS.items():
        assert isinstance(path, Path)
        assert str(path).startswith("/") or str(path).startswith(".")
        assert "\\" not in str(path)

def test_gpu_scheduler_presence():
    """Vérifier que le scheduler GPU est présent et exécutable."""
    scheduler = Path("/home/turbo/jarvis-m1-ops/src/gpu_scheduler.py")
    assert scheduler.exists()
    assert os.access(scheduler, os.X_OK)

def test_tts_fallback():
    """Vérifier que le script TTS existe et peut être appelé."""
    tts_script = Path("/home/turbo/jarvis-m1-ops/scripts/jarvis-tts.sh")
    assert tts_script.exists()
    assert os.access(tts_script, os.X_OK)

def test_env_structure():
    """Vérifier que les variables d'environnement critiques sont définies."""
    from dotenv import load_dotenv
    load_dotenv()
    assert os.getenv("PROJECT_DIR") == "/home/turbo/jarvis-m1-ops"
    assert int(os.getenv("GPU_COUNT", 0)) == 6

def test_mcp_config_posix():
    """Vérifier que .mcp.json est bien en format POSIX."""
    import json
    with open("/home/turbo/jarvis-m1-ops/.mcp.json", "r") as f:
        data = json.load(f)
    for server in data["mcpServers"].values():
        for arg in server.get("args", []):
            if "/" in arg:
                assert "\\" not in arg
        if "cwd" in server:
            assert "\\" not in server["cwd"]
