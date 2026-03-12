"""Tests for JARVIS Resource Allocator."""

import pytest


class TestResourceAllocator:
    def test_import(self):
        from src.resource_allocator import resource_allocator
        assert resource_allocator is not None

    def test_get_cluster_resources(self):
        from src.resource_allocator import resource_allocator
        resources = resource_allocator.get_cluster_resources()
        assert "M1" in resources
        assert "OL1" in resources
        assert "M2" in resources
        assert "M3" in resources
        for node in resources.values():
            assert "online" in node
            assert "max_concurrent" in node

    def test_allocate_code(self):
        from src.resource_allocator import resource_allocator
        node = resource_allocator.allocate("code")
        assert node in ("M1", "OL1", "M3")  # M2 offline

    def test_allocate_reasoning(self):
        from src.resource_allocator import resource_allocator
        node = resource_allocator.allocate("reasoning")
        assert node in ("M1", "M3", "OL1")  # M2 offline, M3 or fallback

    def test_allocate_query(self):
        from src.resource_allocator import resource_allocator
        node = resource_allocator.allocate("query")
        assert node in ("OL1", "M1")

    def test_allocate_trading(self):
        from src.resource_allocator import resource_allocator
        node = resource_allocator.allocate("trading")
        assert node in ("OL1", "M1")

    def test_get_load_report(self):
        from src.resource_allocator import resource_allocator
        report = resource_allocator.get_load_report()
        assert "nodes" in report
        assert "total_active" in report

    def test_rebalance(self):
        from src.resource_allocator import resource_allocator
        suggestions = resource_allocator.rebalance()
        assert isinstance(suggestions, list)

    def test_record_allocation(self):
        from src.resource_allocator import resource_allocator
        resource_allocator.record_allocation("M1", "code", 150.0)
        report = resource_allocator.get_load_report()
        m1 = report["nodes"]["M1"]
        assert m1["total_allocations"] >= 1
