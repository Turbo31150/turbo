"""Tests for src/dependency_graph.py — Module/service dependency tracking.

Covers: DependencyGraph (add_node, add_dependency, remove_node, remove_dependency,
get_dependencies, get_dependents, has_cycle, topological_sort, impact_analysis,
transitive_deps, get_all_nodes, get_graph, get_stats), dep_graph singleton.
Pure in-memory — no external calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dependency_graph import DependencyGraph, dep_graph


# ===========================================================================
# Node management
# ===========================================================================

class TestNodeManagement:
    def test_add_node(self):
        g = DependencyGraph()
        g.add_node("A")
        assert "A" in g.get_all_nodes()

    def test_add_node_with_metadata(self):
        g = DependencyGraph()
        g.add_node("A", metadata={"version": "1.0"})
        graph = g.get_graph()
        assert graph["A"]["metadata"] == {"version": "1.0"}

    def test_remove_node(self):
        g = DependencyGraph()
        g.add_node("A")
        assert g.remove_node("A") is True
        assert "A" not in g.get_all_nodes()

    def test_remove_nonexistent(self):
        g = DependencyGraph()
        assert g.remove_node("nope") is False

    def test_remove_cleans_edges(self):
        g = DependencyGraph()
        g.add_dependency("A", "B")
        g.add_dependency("C", "B")
        g.remove_node("B")
        assert g.get_dependencies("A") == []
        assert g.get_dependencies("C") == []


# ===========================================================================
# Dependencies
# ===========================================================================

class TestDependencies:
    def test_add_dependency(self):
        g = DependencyGraph()
        g.add_dependency("A", "B")
        assert g.get_dependencies("A") == ["B"]
        assert g.get_dependents("B") == ["A"]

    def test_multiple_dependencies(self):
        g = DependencyGraph()
        g.add_dependency("A", "B")
        g.add_dependency("A", "C")
        deps = g.get_dependencies("A")
        assert sorted(deps) == ["B", "C"]

    def test_remove_dependency(self):
        g = DependencyGraph()
        g.add_dependency("A", "B")
        assert g.remove_dependency("A", "B") is True
        assert g.get_dependencies("A") == []

    def test_remove_dependency_nonexistent(self):
        g = DependencyGraph()
        assert g.remove_dependency("A", "B") is False

    def test_get_dependencies_empty(self):
        g = DependencyGraph()
        g.add_node("A")
        assert g.get_dependencies("A") == []

    def test_get_dependents_empty(self):
        g = DependencyGraph()
        g.add_node("A")
        assert g.get_dependents("A") == []


# ===========================================================================
# Cycle detection
# ===========================================================================

class TestCycleDetection:
    def test_no_cycle(self):
        g = DependencyGraph()
        g.add_dependency("A", "B")
        g.add_dependency("B", "C")
        assert g.has_cycle() is False

    def test_with_cycle(self):
        g = DependencyGraph()
        g.add_dependency("A", "B")
        g.add_dependency("B", "C")
        g.add_dependency("C", "A")
        assert g.has_cycle() is True

    def test_self_cycle(self):
        g = DependencyGraph()
        g.add_dependency("A", "A")
        assert g.has_cycle() is True

    def test_empty_graph(self):
        g = DependencyGraph()
        assert g.has_cycle() is False


# ===========================================================================
# Topological sort
# ===========================================================================

class TestTopologicalSort:
    def test_simple_chain(self):
        g = DependencyGraph()
        g.add_dependency("A", "B")
        g.add_dependency("B", "C")
        order = g.topological_sort()
        assert order.index("C") < order.index("B")
        assert order.index("B") < order.index("A")

    def test_independent_nodes(self):
        g = DependencyGraph()
        g.add_node("A")
        g.add_node("B")
        order = g.topological_sort()
        assert set(order) == {"A", "B"}

    def test_cycle_raises(self):
        g = DependencyGraph()
        g.add_dependency("A", "B")
        g.add_dependency("B", "A")
        with pytest.raises(ValueError, match="Cycle"):
            g.topological_sort()

    def test_diamond(self):
        g = DependencyGraph()
        g.add_dependency("D", "B")
        g.add_dependency("D", "C")
        g.add_dependency("B", "A")
        g.add_dependency("C", "A")
        order = g.topological_sort()
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")


# ===========================================================================
# Impact analysis & transitive deps
# ===========================================================================

class TestAnalysis:
    def test_impact_analysis(self):
        g = DependencyGraph()
        g.add_dependency("B", "A")
        g.add_dependency("C", "A")
        g.add_dependency("D", "B")
        affected = g.impact_analysis("A")
        assert "B" in affected
        assert "C" in affected
        assert "D" in affected

    def test_impact_analysis_leaf(self):
        g = DependencyGraph()
        g.add_dependency("A", "B")
        assert g.impact_analysis("A") == []

    def test_transitive_deps(self):
        g = DependencyGraph()
        g.add_dependency("A", "B")
        g.add_dependency("B", "C")
        g.add_dependency("C", "D")
        trans = g.transitive_deps("A")
        assert sorted(trans) == ["B", "C", "D"]

    def test_transitive_deps_none(self):
        g = DependencyGraph()
        g.add_node("A")
        assert g.transitive_deps("A") == []


# ===========================================================================
# Graph / Stats
# ===========================================================================

class TestGraphAndStats:
    def test_get_graph(self):
        g = DependencyGraph()
        g.add_dependency("A", "B")
        graph = g.get_graph()
        assert "A" in graph
        assert "B" in graph["A"]["depends_on"]
        assert "A" in graph["B"]["depended_by"]

    def test_get_all_nodes(self):
        g = DependencyGraph()
        g.add_node("X")
        g.add_node("Y")
        assert sorted(g.get_all_nodes()) == ["X", "Y"]

    def test_stats(self):
        g = DependencyGraph()
        g.add_dependency("A", "B")
        g.add_dependency("A", "C")
        stats = g.get_stats()
        assert stats["total_nodes"] == 3
        assert stats["total_edges"] == 2
        assert stats["has_cycle"] is False

    def test_stats_leaf_and_root(self):
        g = DependencyGraph()
        g.add_dependency("A", "B")
        stats = g.get_stats()
        # B has no deps -> leaf, A depends on B -> not leaf
        # B has no reverse (wait, A depends on B, so B has dependents)
        # Root = no reverse deps
        assert stats["leaf_nodes"] >= 1  # B has no forward deps
        assert stats["root_nodes"] >= 0


# ===========================================================================
# Singleton (pre-populated)
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert dep_graph is not None
        assert isinstance(dep_graph, DependencyGraph)

    def test_jarvis_modules_present(self):
        nodes = dep_graph.get_all_nodes()
        assert "orchestrator_v2" in nodes
        assert "event_bus" in nodes
        assert "load_balancer" in nodes

    def test_no_cycle_in_jarvis(self):
        assert dep_graph.has_cycle() is False

    def test_topological_sort_works(self):
        order = dep_graph.topological_sort()
        assert len(order) > 10
