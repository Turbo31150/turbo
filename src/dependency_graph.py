"""Dependency Graph — Module/service dependency tracking.

Tracks which modules depend on which, detects cycles,
computes startup order, and provides impact analysis.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Any

logger = logging.getLogger("jarvis.dependency_graph")


class DependencyGraph:
    """Directed acyclic graph for module dependencies."""

    def __init__(self):
        self._edges: dict[str, set[str]] = defaultdict(set)  # node → depends_on
        self._reverse: dict[str, set[str]] = defaultdict(set)  # node → depended_by
        self._metadata: dict[str, dict] = {}

    def add_node(self, name: str, metadata: dict | None = None) -> None:
        """Add a node (module/service)."""
        if name not in self._edges:
            self._edges[name] = set()
        if name not in self._reverse:
            self._reverse[name] = set()
        if metadata:
            self._metadata[name] = metadata

    def add_dependency(self, node: str, depends_on: str) -> None:
        """Declare that *node* depends on *depends_on*."""
        self.add_node(node)
        self.add_node(depends_on)
        self._edges[node].add(depends_on)
        self._reverse[depends_on].add(node)

    def remove_node(self, name: str) -> bool:
        if name not in self._edges:
            return False
        # Remove from all edges
        for dep in self._edges[name]:
            self._reverse[dep].discard(name)
        for dependent in self._reverse[name]:
            self._edges[dependent].discard(name)
        del self._edges[name]
        del self._reverse[name]
        self._metadata.pop(name, None)
        return True

    def remove_dependency(self, node: str, depends_on: str) -> bool:
        if depends_on in self._edges.get(node, set()):
            self._edges[node].discard(depends_on)
            self._reverse[depends_on].discard(node)
            return True
        return False

    def get_dependencies(self, node: str) -> list[str]:
        """What does *node* depend on?"""
        return sorted(self._edges.get(node, set()))

    def get_dependents(self, node: str) -> list[str]:
        """What depends on *node*?"""
        return sorted(self._reverse.get(node, set()))

    def has_cycle(self) -> bool:
        """Check if the graph contains any cycles."""
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def _dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for dep in self._edges.get(node, set()):
                if dep not in visited:
                    if _dfs(dep):
                        return True
                elif dep in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for n in list(self._edges.keys()):
            if n not in visited:
                if _dfs(n):
                    return True
        return False

    def topological_sort(self) -> list[str]:
        """Return nodes in startup order (dependencies first).
        Raises ValueError if cycle detected."""
        in_degree: dict[str, int] = defaultdict(int)
        for node in self._edges:
            if node not in in_degree:
                in_degree[node] = 0
            for dep in self._edges[node]:
                in_degree.setdefault(dep, 0)
                # node depends on dep → dep must come first → doesn't affect dep's in_degree
                pass

        # Recompute: in_degree[x] = number of nodes that x depends on (forward deps)
        # Actually for startup order: we want reverse — start with nodes that have no dependencies
        in_deg: dict[str, int] = {n: 0 for n in self._edges}
        for node, deps in self._edges.items():
            in_deg[node] = len(deps)
            for d in deps:
                if d not in in_deg:
                    in_deg[d] = 0

        queue = deque([n for n, d in in_deg.items() if d == 0])
        result: list[str] = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for dependent in self._reverse.get(node, set()):
                in_deg[dependent] -= 1
                if in_deg[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(in_deg):
            raise ValueError("Cycle detected — cannot compute startup order")
        return result

    def impact_analysis(self, node: str) -> list[str]:
        """Find all nodes transitively affected if *node* goes down."""
        affected: set[str] = set()
        queue = deque([node])
        while queue:
            current = queue.popleft()
            for dep in self._reverse.get(current, set()):
                if dep not in affected:
                    affected.add(dep)
                    queue.append(dep)
        return sorted(affected)

    def transitive_deps(self, node: str) -> list[str]:
        """All transitive dependencies of *node*."""
        deps: set[str] = set()
        queue = deque(self._edges.get(node, set()))
        while queue:
            current = queue.popleft()
            if current not in deps:
                deps.add(current)
                queue.extend(self._edges.get(current, set()) - deps)
        return sorted(deps)

    def get_all_nodes(self) -> list[str]:
        return sorted(self._edges.keys())

    def get_graph(self) -> dict:
        """Full graph as adjacency dict."""
        return {
            node: {
                "depends_on": sorted(deps),
                "depended_by": sorted(self._reverse.get(node, set())),
                "metadata": self._metadata.get(node, {}),
            }
            for node, deps in self._edges.items()
        }

    def get_stats(self) -> dict:
        total_edges = sum(len(d) for d in self._edges.values())
        leaf_nodes = [n for n, d in self._edges.items() if not d]
        root_nodes = [n for n in self._edges if not self._reverse.get(n)]
        return {
            "total_nodes": len(self._edges),
            "total_edges": total_edges,
            "leaf_nodes": len(leaf_nodes),
            "root_nodes": len(root_nodes),
            "has_cycle": self.has_cycle(),
        }


# ── Singleton (pre-populated with JARVIS modules) ───────────────────────────
dep_graph = DependencyGraph()

# Register known JARVIS module dependencies
_JARVIS_DEPS = {
    "orchestrator_v2": ["load_balancer", "event_bus"],
    "autonomous_loop": ["orchestrator_v2", "task_queue", "event_bus"],
    "proactive_agent": ["agent_memory", "metrics_aggregator"],
    "load_balancer": ["rate_limiter"],
    "health_dashboard": ["cluster_diagnostics", "metrics_aggregator", "alert_manager", "task_scheduler", "rate_limiter", "config_manager", "audit_trail", "event_bus"],
    "metrics_aggregator": ["orchestrator_v2", "load_balancer", "autonomous_loop", "agent_memory", "event_bus"],
    "alert_manager": ["event_bus", "notifier"],
    "cluster_diagnostics": ["orchestrator_v2", "load_balancer", "autonomous_loop", "alert_manager", "event_bus"],
    "auto_optimizer": ["orchestrator_v2", "load_balancer", "autonomous_loop"],
    "resource_monitor": ["alert_manager"],
    "workflow_engine": [],
    "session_manager": [],
    "config_manager": [],
    "audit_trail": [],
    "event_bus": [],
    "task_queue": [],
    "notifier": [],
    "agent_memory": [],
    "rate_limiter": [],
    "task_scheduler": [],
    "plugin_manager": [],
    "command_router": [],
    "data_pipeline": [],
    "service_registry": [],
    "cache_manager": [],
    "secret_vault": [],
    "retry_manager": [],
}

for _mod, _deps in _JARVIS_DEPS.items():
    dep_graph.add_node(_mod)
    for _d in _deps:
        dep_graph.add_dependency(_mod, _d)
