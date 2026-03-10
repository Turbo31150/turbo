"""Tests for JARVIS Rollback Manager."""

import os
import tempfile
from pathlib import Path

import pytest


class TestRollbackManager:
    def test_import(self):
        from src.rollback_manager import rollback_manager
        assert rollback_manager is not None

    def test_get_stats(self):
        from src.rollback_manager import rollback_manager
        stats = rollback_manager.get_stats()
        assert "total_fixes" in stats
        assert "max_snapshots" in stats

    def test_get_history(self):
        from src.rollback_manager import rollback_manager
        history = rollback_manager.get_history()
        assert isinstance(history, list)

    def test_snapshot_file(self):
        from src.rollback_manager import rollback_manager
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("test content")
            f.flush()
            snap = rollback_manager.snapshot_file(f.name)
        assert snap is not None
        assert Path(snap).exists()
        # Cleanup
        os.unlink(snap)
        os.unlink(f.name)

    def test_snapshot_nonexistent(self):
        from src.rollback_manager import rollback_manager
        snap = rollback_manager.snapshot_file("/nonexistent/file.txt")
        assert snap is None

    def test_restore_file(self):
        from src.rollback_manager import rollback_manager
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("original")
            original_path = f.name
        snap = rollback_manager.snapshot_file(original_path)
        # Modify original
        with open(original_path, "w") as f:
            f.write("modified")
        # Restore
        result = rollback_manager.restore_file(snap, original_path)
        assert result is True
        with open(original_path) as f:
            assert f.read() == "original"
        os.unlink(snap)
        os.unlink(original_path)

    def test_safe_fix_success(self):
        from src.rollback_manager import rollback_manager
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("data")
            path = f.name
        with rollback_manager.safe_fix("test_fix", target="test", files=[path]) as ctx:
            assert "fix_id" in ctx
            with open(path, "w") as f:
                f.write("fixed data")
        # Success — file should have new content
        with open(path) as f:
            assert f.read() == "fixed data"
        os.unlink(path)

    def test_safe_fix_rollback(self):
        from src.rollback_manager import rollback_manager
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("original data")
            path = f.name
        with pytest.raises(ValueError):
            with rollback_manager.safe_fix("test_fail", target="test", files=[path]):
                with open(path, "w") as f:
                    f.write("broken data")
                raise ValueError("Fix failed!")
        # Should be rolled back to original
        with open(path) as f:
            assert f.read() == "original data"
        os.unlink(path)

    def test_snapshot_class(self):
        from src.rollback_manager import Snapshot
        s = Snapshot(fix_id="test", target="db", timestamp=1.0, snapshot_path="/tmp/x")
        assert s.fix_id == "test"


class TestVRAMOptimizer:
    def test_import(self):
        from src.vram_optimizer import vram_optimizer
        assert vram_optimizer is not None

    def test_get_gpu_state(self):
        from src.vram_optimizer import vram_optimizer
        gpus = vram_optimizer.get_gpu_state()
        assert isinstance(gpus, list)

    def test_get_report(self):
        from src.vram_optimizer import vram_optimizer
        report = vram_optimizer.get_report()
        assert "gpus" in report
        assert "loaded_models" in report
        assert "trend" in report

    @pytest.mark.asyncio
    async def test_check_and_optimize(self):
        from src.vram_optimizer import vram_optimizer
        result = await vram_optimizer.check_and_optimize()
        assert "status" in result
        assert result["status"] in ("healthy", "warning", "critical", "no_gpu")

    def test_gpu_state_dataclass(self):
        from src.vram_optimizer import GPUState
        g = GPUState(name="RTX", temp_c=50, vram_used_mb=4000,
                     vram_total_mb=8000, utilization_pct=60, vram_pct=50.0)
        assert g.vram_pct == 50.0
