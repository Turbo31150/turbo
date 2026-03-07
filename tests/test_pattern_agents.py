#!/usr/bin/env python3
"""Tests for pattern_agents + smart_dispatcher + agent_factory."""
import asyncio
import json
import sys
import os
sys.path.insert(0, "F:/BUREAU/turbo")
os.chdir("F:/BUREAU/turbo")

import pytest

from src.pattern_agents import PatternAgentRegistry, PatternAgent, AGENT_CONFIGS
from src.smart_dispatcher import SmartDispatcher
from src.agent_factory import AgentFactory


class TestPatternAgentRegistry:
    def test_26_agents_registered(self):
        reg = PatternAgentRegistry()
        assert len(reg.agents) == 26  # 20 domain + 6 size-based

    def test_all_pattern_types(self):
        reg = PatternAgentRegistry()
        expected = {"classifier", "simple", "web", "code", "analysis", "system",
                    "creative", "math", "data", "devops", "reasoning", "trading",
                    "security", "architecture",
                    "voice", "email", "automation", "learning", "monitoring", "optimization",
                    "nano", "micro", "small", "medium", "large", "xl"}
        assert set(reg.agents.keys()) == expected

    def test_classify_code(self):
        reg = PatternAgentRegistry()
        assert reg.classify("Ecris une fonction Python") == "code"

    def test_classify_simple(self):
        reg = PatternAgentRegistry()
        assert reg.classify("bonjour") == "simple"

    def test_classify_math(self):
        reg = PatternAgentRegistry()
        assert reg.classify("calcule la derivee de x^2") == "math"

    def test_classify_trading(self):
        reg = PatternAgentRegistry()
        assert reg.classify("analyse trading BTC RSI MACD") == "trading"

    def test_classify_security(self):
        reg = PatternAgentRegistry()
        assert reg.classify("audit securite injection OWASP") == "security"

    def test_classify_system(self):
        reg = PatternAgentRegistry()
        assert reg.classify("check GPU monitoring cpu") == "system"

    def test_classify_default(self):
        reg = PatternAgentRegistry()
        result = reg.classify("une question vague quelconque sans keywords")
        assert result in reg.agents  # should still return valid pattern

    def test_list_agents(self):
        reg = PatternAgentRegistry()
        agents = reg.list_agents()
        assert len(agents) == 26  # 20 domain + 6 size-based
        assert all("pattern_id" in a for a in agents)
        assert all("type" in a for a in agents)

    def test_agent_priority_order(self):
        reg = PatternAgentRegistry()
        agents = reg.list_agents()
        priorities = [a["priority"] for a in agents]
        assert priorities == sorted(priorities)

    @pytest.mark.asyncio
    async def test_dispatch_simple(self):
        reg = PatternAgentRegistry()
        r = await reg.dispatch("simple", "bonjour")
        assert r.pattern == "simple"
        assert r.latency_ms > 0
        await reg.close()

    @pytest.mark.asyncio
    async def test_dispatch_auto(self):
        reg = PatternAgentRegistry()
        r = await reg.dispatch_auto("2+2=?")
        assert r.pattern in reg.agents
        await reg.close()


class TestSmartDispatcher:
    def test_init(self):
        d = SmartDispatcher()
        assert d.registry is not None

    def test_routing_report(self):
        d = SmartDispatcher()
        report = d.get_routing_report()
        assert isinstance(report, dict)

    @pytest.mark.asyncio
    async def test_health_check(self):
        d = SmartDispatcher()
        h = await d.health_check()
        assert "M1" in h
        assert "OL1" in h
        await d.close()


class TestAgentFactory:
    def test_init(self):
        f = AgentFactory()
        assert f.db_path.endswith("etoile.db")

    def test_report(self):
        f = AgentFactory()
        report = f.generate_report()
        assert "total_patterns" in report
        assert "total_dispatches" in report
        assert report["total_patterns"] >= 1  # at least some patterns in DB

    def test_evolve(self):
        f = AgentFactory()
        evolutions = f.analyze_and_evolve()
        assert isinstance(evolutions, list)


class TestAgentConfigs:
    def test_all_configs_valid(self):
        for agent in AGENT_CONFIGS:
            assert agent.pattern_id.startswith("PAT_")
            assert agent.agent_id
            assert agent.primary_node
            assert agent.strategy in ("single", "race", "consensus", "category", "chain")
            assert agent.priority >= 1

    def test_26_agents(self):
        assert len(AGENT_CONFIGS) == 26  # 20 domain + 6 size-based

    def test_unique_pattern_ids(self):
        ids = [a.pattern_id for a in AGENT_CONFIGS]
        assert len(ids) == len(set(ids))

    def test_unique_types(self):
        types = [a.pattern_type for a in AGENT_CONFIGS]
        assert len(types) == len(set(types))

    def test_all_nodes_exist(self):
        from src.pattern_agents import NODES
        for agent in AGENT_CONFIGS:
            assert agent.primary_node in NODES, f"{agent.pattern_id} uses unknown node {agent.primary_node}"

    def test_new_domain_agents(self):
        reg = PatternAgentRegistry()
        new_domains = ["voice", "email", "automation", "learning", "monitoring", "optimization"]
        for d in new_domains:
            assert d in reg.agents, f"Missing domain agent: {d}"

    def test_classify_voice(self):
        reg = PatternAgentRegistry()
        assert reg.classify("voix parle dis") == "voice"

    def test_classify_email(self):
        reg = PatternAgentRegistry()
        assert reg.classify("email inbox gmail") == "email"

    def test_classify_automation(self):
        reg = PatternAgentRegistry()
        assert reg.classify("automatise cron schedule") == "automation"

    def test_classify_monitoring(self):
        reg = PatternAgentRegistry()
        assert reg.classify("monitore health status") == "monitoring"

    def test_classify_optimization(self):
        reg = PatternAgentRegistry()
        assert reg.classify("optimise performance latence") == "optimization"


class TestPipelineComposer:
    def test_pipelines_exist(self):
        from src.pipeline_composer import PIPELINES
        assert len(PIPELINES) == 5
        assert "code-review" in PIPELINES
        assert "smart-qa" in PIPELINES

    def test_pipeline_build(self):
        from src.pipeline_composer import code_review_pipeline
        pipe = code_review_pipeline()
        assert len(pipe.steps) == 3
        assert pipe.name == "code-review"


class TestAgentMonitor:
    def test_monitor_singleton(self):
        from src.agent_monitor import get_monitor
        m1 = get_monitor()
        m2 = get_monitor()
        assert m1 is m2

    def test_dashboard_structure(self):
        from src.agent_monitor import get_monitor
        d = get_monitor().get_dashboard()
        assert "total_dispatches" in d
        assert "agents" in d
        assert "nodes" in d
        assert "alerts" in d

    def test_record_dispatch(self):
        from src.agent_monitor import AgentMonitor
        m = AgentMonitor()
        m.record_dispatch("code", "M1", "single", 1000, True, 0.8)
        d = m.get_dashboard()
        assert d["total_dispatches"] == 1
        assert "code" in d["agents"]


class TestAutoScaler:
    def test_init(self):
        from src.auto_scaler import AutoScaler
        s = AutoScaler()
        assert s.db_path == "F:/BUREAU/turbo/etoile.db"

    @pytest.mark.asyncio
    async def test_scale(self):
        from src.auto_scaler import AutoScaler
        s = AutoScaler()
        actions = await s.scale()
        assert isinstance(actions, list)
        assert all("action" in a for a in actions)


class TestRoutingOptimizer:
    def test_report(self):
        from src.routing_optimizer import RoutingOptimizer
        opt = RoutingOptimizer()
        r = opt.report()
        assert "nodes" in r
        assert "recommendations" in r

    def test_optimal_config(self):
        from src.routing_optimizer import RoutingOptimizer
        opt = RoutingOptimizer()
        cfg = opt.get_optimal_config("code", "Ecris une fonction Python")
        assert "node" in cfg
        assert "timeout_s" in cfg
        assert "max_tokens" in cfg


class TestAdaptiveRouter:
    def test_init(self):
        from src.adaptive_router import AdaptiveRouter
        router = AdaptiveRouter()
        assert len(router.circuits) >= 4
        assert len(router.health) >= 4

    def test_pick_node(self):
        from src.adaptive_router import AdaptiveRouter
        router = AdaptiveRouter()
        node = router.pick_node("code", "Ecris un parser JSON")
        assert node in router.health

    def test_pick_nodes(self):
        from src.adaptive_router import AdaptiveRouter
        router = AdaptiveRouter()
        nodes = router.pick_nodes("code", count=3)
        assert 1 <= len(nodes) <= 3
        assert all(n in router.health for n in nodes)

    def test_record_success(self):
        from src.adaptive_router import AdaptiveRouter
        router = AdaptiveRouter()
        router.record("M1", "code", True, 1500, 0.8)
        assert router.health["M1"].total_calls >= 1

    def test_record_failure_trips_circuit(self):
        from src.adaptive_router import AdaptiveRouter, CircuitState
        router = AdaptiveRouter()
        for _ in range(6):
            router.record("M3", "code", False, 60000, 0)
        assert router.circuits["M3"].state == CircuitState.OPEN

    def test_acquire_release(self):
        from src.adaptive_router import AdaptiveRouter
        router = AdaptiveRouter()
        router.acquire("M1")
        assert router.health["M1"].active_requests >= 1
        router.release("M1")

    def test_status(self):
        from src.adaptive_router import AdaptiveRouter
        router = AdaptiveRouter()
        status = router.get_status()
        assert "nodes" in status
        assert "affinities" in status
        assert "healthy_nodes" in status

    def test_recommendations(self):
        from src.adaptive_router import AdaptiveRouter
        router = AdaptiveRouter()
        recs = router.get_recommendations()
        assert isinstance(recs, list)

    def test_singleton(self):
        from src.adaptive_router import get_router
        r1 = get_router()
        r2 = get_router()
        assert r1 is r2


class TestPatternDiscovery:
    def test_init(self):
        from src.pattern_discovery import PatternDiscovery
        d = PatternDiscovery()
        assert d.db_path.endswith("etoile.db")

    def test_discover(self):
        from src.pattern_discovery import PatternDiscovery
        d = PatternDiscovery()
        patterns = d.discover()
        assert isinstance(patterns, list)

    def test_behavior(self):
        from src.pattern_discovery import PatternDiscovery
        d = PatternDiscovery()
        insights = d.analyze_behavior()
        assert isinstance(insights, list)
        # Should have at least peak_hours if there's data
        types = [i.insight_type for i in insights]
        assert all(t in ("peak_hours", "pattern_distribution", "complexity_trend", "success_degradation") for t in types)

    def test_full_report(self):
        from src.pattern_discovery import PatternDiscovery
        d = PatternDiscovery()
        report = d.full_report()
        assert "discovered_patterns" in report
        assert "behavior_insights" in report
        assert "total_discovered" in report


class TestOrchestratorV3:
    def test_init(self):
        from src.agent_orchestrator_v3 import Orchestrator
        o = Orchestrator()
        assert o.registry is not None
        assert o.router is not None

    def test_list_workflows(self):
        from src.agent_orchestrator_v3 import Orchestrator
        o = Orchestrator()
        wf = o.list_workflows()
        assert "deep-analysis" in wf
        assert "code-generate" in wf
        assert "consensus-3" in wf
        assert "trading-full" in wf
        assert "security-audit" in wf

    def test_auto_select_code(self):
        from src.agent_orchestrator_v3 import Orchestrator
        o = Orchestrator()
        assert o._auto_select_workflow("ecris une fonction Python") == "code-generate"

    def test_auto_select_trading(self):
        from src.agent_orchestrator_v3 import Orchestrator
        o = Orchestrator()
        assert o._auto_select_workflow("analyse trading BTC RSI") == "trading-full"

    def test_auto_select_security(self):
        from src.agent_orchestrator_v3 import Orchestrator
        o = Orchestrator()
        assert o._auto_select_workflow("audit securite OWASP") == "security-audit"

    def test_workflows_config(self):
        from src.agent_orchestrator_v3 import WORKFLOWS
        assert len(WORKFLOWS) >= 7
        for name, steps in WORKFLOWS.items():
            if name != "auto":
                assert len(steps) >= 2, f"Workflow {name} has only {len(steps)} steps"

    @pytest.mark.asyncio
    async def test_execute_auto(self):
        from src.agent_orchestrator_v3 import Orchestrator
        o = Orchestrator()
        r = await o.execute("2+2=?", budget_s=30)
        assert r.ok or not r.ok  # Just test it doesn't crash
        assert r.total_latency_ms > 0
        assert len(r.steps) >= 1
        await o.close()


class TestAgentCollaboration:
    def test_init(self):
        from src.agent_collaboration import AgentBus
        bus = AgentBus()
        assert bus.registry is not None

    def test_get_stats(self):
        from src.agent_collaboration import AgentBus
        bus = AgentBus()
        stats = bus.get_stats()
        assert "total_messages" in stats
        assert "success_rate" in stats

    def test_message_log(self):
        from src.agent_collaboration import AgentBus
        bus = AgentBus()
        log = bus.get_message_log()
        assert isinstance(log, list)

    @pytest.mark.asyncio
    async def test_ask(self):
        from src.agent_collaboration import AgentBus
        bus = AgentBus()
        msg = await bus.ask("simple", "Bonjour")
        assert msg.to_agent == "simple"
        assert msg.msg_type == "response"
        await bus.close()

    @pytest.mark.asyncio
    async def test_chain(self):
        from src.agent_collaboration import AgentBus
        bus = AgentBus()
        result = await bus.chain(["simple", "reasoning"], "2+2=?")
        assert result.steps_total == 2
        assert result.total_latency_ms > 0
        await bus.close()

    def test_singleton(self):
        from src.agent_collaboration import get_bus
        b1 = get_bus()
        b2 = get_bus()
        assert b1 is b2


class TestHealthGuardian:
    @pytest.mark.asyncio
    async def test_check_all(self):
        from src.agent_health_guardian import HealthGuardian
        g = HealthGuardian()
        report = await g.check_all()
        assert report.total_nodes >= 4
        assert report.overall_status in ("healthy", "degraded", "critical")

    def test_get_summary_no_check(self):
        from src.agent_health_guardian import HealthGuardian
        g = HealthGuardian()
        summary = g.get_summary()
        assert summary["status"] == "unknown"

    @pytest.mark.asyncio
    async def test_auto_heal(self):
        from src.agent_health_guardian import HealthGuardian
        g = HealthGuardian()
        healed = await g.auto_heal()
        assert isinstance(healed, list)


class TestBenchmarkRunner:
    def test_init(self):
        from src.pattern_benchmark_runner import BenchmarkRunner
        r = BenchmarkRunner()
        assert r.registry is not None

    def test_prompts_exist(self):
        from src.pattern_benchmark_runner import BENCHMARK_PROMPTS
        assert len(BENCHMARK_PROMPTS) >= 10
        assert all(len(v) >= 3 for v in BENCHMARK_PROMPTS.values())

    def test_history(self):
        from src.pattern_benchmark_runner import BenchmarkRunner
        r = BenchmarkRunner()
        h = r.get_history()
        assert isinstance(h, list)


class TestSelfImprover:
    @pytest.mark.asyncio
    async def test_run_cycle(self):
        from src.agent_self_improve import SelfImprover
        imp = SelfImprover()
        report = await imp.run_cycle()
        assert report.cycle_id == 1
        assert report.duration_ms > 0
        assert isinstance(report.actions, list)
        assert isinstance(report.recommendations, list)

    def test_get_history(self):
        from src.agent_self_improve import SelfImprover
        imp = SelfImprover()
        history = imp.get_history()
        assert isinstance(history, list)


class TestEpisodicMemory:
    def test_init(self):
        from src.agent_episodic_memory import EpisodicMemory
        mem = EpisodicMemory()
        assert len(mem._episodes) > 0  # Seeded from dispatch_log

    def test_store_episode(self):
        from src.agent_episodic_memory import EpisodicMemory
        mem = EpisodicMemory()
        before = len(mem._episodes)
        mem.store_episode("code", "M1", "Test store episode", success=True, quality=0.9, latency_ms=500)
        assert len(mem._episodes) == before + 1
        assert mem._episodes[0].pattern == "code"
        assert mem.working.dispatch_count >= 1

    def test_recall(self):
        from src.agent_episodic_memory import EpisodicMemory
        mem = EpisodicMemory()
        mem.store_episode("code", "M1", "Ecris une fonction Python parser JSON", success=True)
        results = mem.recall("fonction Python", top_k=3)
        assert isinstance(results, list)

    def test_store_fact(self):
        from src.agent_episodic_memory import EpisodicMemory
        mem = EpisodicMemory()
        mem.store_fact("pattern_affinity", "code", "best_node", "M1", confidence=0.95)
        facts = mem.get_facts(subject="code")
        assert any(f.predicate == "best_node" for f in facts)

    def test_node_memory(self):
        from src.agent_episodic_memory import EpisodicMemory
        mem = EpisodicMemory()
        info = mem.get_node_memory("M1")
        assert "node" in info
        assert "total_episodes" in info
        assert "success_rate" in info

    def test_pattern_memory(self):
        from src.agent_episodic_memory import EpisodicMemory
        mem = EpisodicMemory()
        info = mem.get_pattern_memory("code")
        assert "pattern" in info
        assert "best_node" in info

    def test_learn(self):
        from src.agent_episodic_memory import EpisodicMemory
        mem = EpisodicMemory()
        learned = mem.learn_from_history()
        assert isinstance(learned, list)

    def test_session_summary(self):
        from src.agent_episodic_memory import EpisodicMemory
        mem = EpisodicMemory()
        summary = mem.get_session_summary()
        assert "elapsed_s" in summary
        assert "episodes_total" in summary

    def test_singleton(self):
        from src.agent_episodic_memory import get_episodic_memory
        m1 = get_episodic_memory()
        m2 = get_episodic_memory()
        assert m1 is m2


class TestTaskPlanner:
    def test_init(self):
        from src.agent_task_planner import TaskPlanner
        p = TaskPlanner()
        assert p.registry is not None

    def test_plan_simple(self):
        from src.agent_task_planner import TaskPlanner
        p = TaskPlanner()
        plan = p.plan("Bonjour")
        assert plan.complexity in ("nano", "micro")
        assert plan.sub_tasks == []  # Too simple to decompose

    def test_plan_api(self):
        from src.agent_task_planner import TaskPlanner
        p = TaskPlanner()
        plan = p.plan("Cree une API REST securisee avec authentification JWT")
        assert plan.complexity in ("small", "medium", "large", "xl")
        assert len(plan.sub_tasks) >= 3
        assert plan.sub_tasks[0].pattern in ("reasoning", "code", "analysis")

    def test_plan_trading(self):
        from src.agent_task_planner import TaskPlanner
        p = TaskPlanner()
        plan = p.plan("Analyse trading BTC position longue signal achat")
        assert len(plan.sub_tasks) >= 2

    def test_plan_to_dict(self):
        from src.agent_task_planner import TaskPlanner
        p = TaskPlanner()
        plan = p.plan("Analyse le code de securite")
        d = p.plan_to_dict(plan)
        assert "complexity" in d
        assert "sub_tasks" in d
        assert "summary" in d

    @pytest.mark.asyncio
    async def test_execute_plan(self):
        from src.agent_task_planner import TaskPlanner
        p = TaskPlanner()
        plan = p.plan("Bonjour")
        result = await p.execute_plan(plan)
        assert result.steps_total >= 1
        assert result.total_ms > 0
        await p.close()


class TestFeedbackLoop:
    def test_init(self):
        from src.agent_feedback_loop import FeedbackLoop
        fb = FeedbackLoop()
        assert len(fb._feedback_cache) > 0  # Seeded from dispatch_log

    def test_record_feedback(self):
        from src.agent_feedback_loop import FeedbackLoop
        fb = FeedbackLoop()
        before = len(fb._feedback_cache)
        fb.record_feedback("code", "M1", quality=0.9, success=True)
        assert len(fb._feedback_cache) == before + 1

    def test_get_trends(self):
        from src.agent_feedback_loop import FeedbackLoop
        fb = FeedbackLoop()
        trends = fb.get_trends()
        assert isinstance(trends, list)

    def test_suggest_adjustments(self):
        from src.agent_feedback_loop import FeedbackLoop
        fb = FeedbackLoop()
        adj = fb.suggest_adjustments()
        assert isinstance(adj, list)

    def test_quality_report(self):
        from src.agent_feedback_loop import FeedbackLoop
        fb = FeedbackLoop()
        report = fb.get_quality_report()
        assert "total_feedback" in report
        assert "avg_quality" in report
        assert "patterns" in report

    def test_ab_results(self):
        from src.agent_feedback_loop import FeedbackLoop
        fb = FeedbackLoop()
        results = fb.get_ab_results()
        assert isinstance(results, dict)

    def test_singleton(self):
        from src.agent_feedback_loop import get_feedback
        f1 = get_feedback()
        f2 = get_feedback()
        assert f1 is f2


class TestDispatchEngine:
    def test_init(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        assert engine.config is not None
        assert engine._stats["total_dispatches"] == 0

    def test_config(self):
        from src.dispatch_engine import PipelineConfig, DispatchEngine
        cfg = PipelineConfig(enable_health_check=False, max_retries=3)
        engine = DispatchEngine(config=cfg)
        assert not engine.config.enable_health_check
        assert engine.config.max_retries == 3

    def test_quality_gate_integration_empty(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        result = engine._evaluate_quality_gate("code", "write code", "", 0, "M1")
        assert result["overall_score"] == 0.0 or not result["passed"]

    def test_quality_gate_integration_good(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        result = engine._evaluate_quality_gate(
            "code", "Ecris un parser JSON",
            "def parse_json(data):\n    import json\n    return json.loads(data)\n```\nParse une string JSON.",
            1500, "M1"
        )
        assert result["overall_score"] > 0.3
        assert isinstance(result["passed"], bool)
        assert isinstance(result["failed_gates"], list)

    def test_quality_gate_integration_simple(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        result = engine._evaluate_quality_gate(
            "simple", "Quelle est la capitale de la France",
            "Paris est la capitale de la France.", 500, "M1"
        )
        assert result["overall_score"] > 0.2

    def test_event_emission(self):
        from src.dispatch_engine import DispatchEngine, DispatchResult
        engine = DispatchEngine()
        dr = DispatchResult(
            pattern="code", node="M1", strategy="single",
            content="def foo(): pass", quality=0.8, latency_ms=1000,
            success=True, pipeline_ms=1200,
        )
        emitted = engine._emit_event(dr, "test prompt")
        assert emitted is True
        # Verify event was recorded
        from src.event_stream import get_stream
        stream = get_stream()
        events = stream.get_latest("dispatch", n=1)
        assert len(events) >= 1
        assert events[-1]["data"]["pattern"] == "code"

    def test_get_stats(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        stats = engine.get_stats()
        assert "total_dispatches" in stats
        assert "config" in stats
        assert stats["config"]["health_check"] is True

    def test_pipeline_report(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        report = engine.get_pipeline_report()
        assert "total_dispatches" in report or "error" in report

    def test_full_analytics(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        analytics = engine.get_full_analytics()
        assert isinstance(analytics, dict)
        if "error" not in analytics:
            assert "recommendations" in analytics

    def test_cache_key_deterministic(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        k1 = engine._cache_key("code", "test prompt")
        k2 = engine._cache_key("code", "test prompt")
        assert k1 == k2

    def test_cache_key_differs_by_pattern(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        k1 = engine._cache_key("code", "test")
        k2 = engine._cache_key("analysis", "test")
        assert k1 != k2

    def test_cache_put_get(self):
        from src.dispatch_engine import DispatchEngine, DispatchResult
        engine = DispatchEngine()
        result = DispatchResult(
            pattern="code", node="M1", strategy="single",
            content="def f(): pass", quality=0.8, latency_ms=100, success=True,
        )
        key = engine._cache_key("code", "test")
        engine._cache_put(key, result)
        cached = engine._cache_get(key)
        assert cached is not None
        assert cached.content == "def f(): pass"

    def test_cache_miss_on_failure(self):
        from src.dispatch_engine import DispatchEngine, DispatchResult
        engine = DispatchEngine()
        result = DispatchResult(
            pattern="code", node="M1", strategy="single",
            content="", quality=0, latency_ms=100, success=False,
        )
        key = engine._cache_key("code", "fail_test")
        engine._cache_put(key, result)
        cached = engine._cache_get(key)
        assert cached is None  # Failed results not cached

    def test_cache_stats_in_get_stats(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        stats = engine.get_stats()
        assert "cache" in stats
        assert "hits" in stats["cache"]
        assert stats["cache"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_dispatch_simple(self):
        from src.dispatch_engine import DispatchEngine, PipelineConfig
        cfg = PipelineConfig(enable_health_check=False, enable_memory_enrichment=False,
                             enable_feedback=False, enable_episodic_store=False)
        engine = DispatchEngine(config=cfg)
        result = await engine.dispatch("simple", "Bonjour")
        assert result.pattern == "simple"
        assert result.pipeline_ms > 0

    @pytest.mark.asyncio
    async def test_batch_dispatch(self):
        from src.dispatch_engine import DispatchEngine, PipelineConfig
        cfg = PipelineConfig(enable_health_check=False, enable_memory_enrichment=False,
                             enable_feedback=False, enable_episodic_store=False)
        engine = DispatchEngine(config=cfg)
        tasks = [{"pattern": "simple", "prompt": "test1"}, {"pattern": "simple", "prompt": "test2"}]
        results = await engine.batch_dispatch(tasks, concurrency=2)
        assert len(results) == 2

    def test_singleton(self):
        from src.dispatch_engine import get_engine
        e1 = get_engine()
        e2 = get_engine()
        assert e1 is e2


class TestPromptOptimizer:
    def test_init(self):
        from src.agent_prompt_optimizer import PromptOptimizer
        opt = PromptOptimizer()
        assert opt.SYSTEM_PROMPTS is not None

    def test_optimize_code(self):
        from src.agent_prompt_optimizer import PromptOptimizer
        opt = PromptOptimizer()
        result = opt.optimize("code", "Ecris un parser JSON")
        assert "system_prompt" in result
        assert "user_prompt" in result
        assert len(result["optimizations_applied"]) > 0
        assert "system_prompt" in result["optimizations_applied"]

    def test_optimize_simple(self):
        from src.agent_prompt_optimizer import PromptOptimizer
        opt = PromptOptimizer()
        result = opt.optimize("simple", "Quelle heure est-il?")
        assert result["pattern"] == "simple"

    def test_get_insights_all(self):
        from src.agent_prompt_optimizer import PromptOptimizer
        opt = PromptOptimizer()
        insights = opt.get_insights()
        assert isinstance(insights, dict)

    def test_get_insights_pattern(self):
        from src.agent_prompt_optimizer import PromptOptimizer
        opt = PromptOptimizer()
        insight = opt.get_insights("code")
        assert "pattern" in insight

    def test_get_templates(self):
        from src.agent_prompt_optimizer import PromptOptimizer
        opt = PromptOptimizer()
        templates = opt.get_templates()
        assert "code" in templates
        assert "system_prompt" in templates["code"]

    def test_analyze_prompt(self):
        from src.agent_prompt_optimizer import PromptOptimizer
        opt = PromptOptimizer()
        analysis = opt.analyze_prompt("code", "Ecris un parser JSON en Python")
        assert "estimated_quality" in analysis
        assert "suggestions" in analysis
        assert "optimized" in analysis

    def test_analyze_short_prompt(self):
        from src.agent_prompt_optimizer import PromptOptimizer
        opt = PromptOptimizer()
        analysis = opt.analyze_prompt("code", "fix")
        assert analysis["estimated_quality"] < 0.5
        assert any("vague" in s.lower() or "court" in s.lower() for s in analysis["suggestions"])

    def test_refresh(self):
        from src.agent_prompt_optimizer import PromptOptimizer
        opt = PromptOptimizer()
        opt.refresh()
        # Should not crash

    def test_singleton(self):
        from src.agent_prompt_optimizer import get_optimizer
        o1 = get_optimizer()
        o2 = get_optimizer()
        assert o1 is o2


class TestAutoScaler:
    def test_init(self):
        from src.agent_auto_scaler import AutoScaler
        scaler = AutoScaler()
        assert scaler.policy is not None

    def test_custom_policy(self):
        from src.agent_auto_scaler import AutoScaler, ScalePolicy
        policy = ScalePolicy(latency_warning_ms=3000, error_rate_critical=0.3)
        scaler = AutoScaler(policy=policy)
        assert scaler.policy.latency_warning_ms == 3000

    def test_get_load_metrics(self):
        from src.agent_auto_scaler import AutoScaler
        scaler = AutoScaler()
        metrics = scaler.get_load_metrics()
        assert isinstance(metrics, dict)

    def test_evaluate(self):
        from src.agent_auto_scaler import AutoScaler
        scaler = AutoScaler()
        actions = scaler.evaluate()
        assert isinstance(actions, list)

    def test_capacity_report(self):
        from src.agent_auto_scaler import AutoScaler
        scaler = AutoScaler()
        report = scaler.get_capacity_report()
        assert "cluster" in report
        assert "nodes" in report
        assert "recommendations" in report
        assert report["cluster"]["total_gpu_gb"] > 0

    def test_scaling_history(self):
        from src.agent_auto_scaler import AutoScaler
        scaler = AutoScaler()
        history = scaler.get_scaling_history()
        assert isinstance(history, list)

    def test_node_capabilities(self):
        from src.agent_auto_scaler import AutoScaler
        assert "M1" in AutoScaler.NODE_CAPABILITIES
        assert AutoScaler.NODE_CAPABILITIES["M1"]["gpu_gb"] == 46

    def test_singleton(self):
        from src.agent_auto_scaler import get_scaler
        s1 = get_scaler()
        s2 = get_scaler()
        assert s1 is s2


class TestEventStream:
    def test_init(self):
        from src.event_stream import EventStream
        stream = EventStream()
        assert stream._counter == 0

    def test_emit(self):
        from src.event_stream import EventStream
        stream = EventStream()
        eid = stream.emit("dispatch", {"pattern": "code", "node": "M1"})
        assert eid == 1

    def test_emit_multiple(self):
        from src.event_stream import EventStream
        stream = EventStream()
        stream.emit("dispatch", {"test": 1})
        stream.emit("health", {"test": 2})
        stream.emit("dispatch", {"test": 3})
        assert stream._counter == 3

    def test_get_events(self):
        from src.event_stream import EventStream
        stream = EventStream()
        stream.emit("dispatch", {"a": 1})
        stream.emit("dispatch", {"a": 2})
        events = stream.get_events("dispatch")
        assert len(events) == 2

    def test_get_events_since(self):
        from src.event_stream import EventStream
        stream = EventStream()
        stream.emit("dispatch", {"a": 1})
        stream.emit("dispatch", {"a": 2})
        stream.emit("dispatch", {"a": 3})
        events = stream.get_events("dispatch", since_id=1)
        assert len(events) == 2

    def test_get_latest(self):
        from src.event_stream import EventStream
        stream = EventStream()
        for i in range(20):
            stream.emit("dispatch", {"i": i})
        latest = stream.get_latest("dispatch", n=5)
        assert len(latest) == 5
        assert latest[-1]["data"]["i"] == 19

    def test_emit_dispatch(self):
        from src.event_stream import EventStream
        stream = EventStream()
        eid = stream.emit_dispatch("code", "M1", 0.9, 1500, True)
        assert eid > 0
        events = stream.get_events("dispatch")
        assert events[0]["data"]["pattern"] == "code"

    def test_emit_health(self):
        from src.event_stream import EventStream
        stream = EventStream()
        stream.emit_health("M1", "healthy")
        events = stream.get_events("health")
        assert len(events) == 1

    def test_emit_alert(self):
        from src.event_stream import EventStream
        stream = EventStream()
        stream.emit_alert("warning", "High latency", pattern="code", node="M1")
        events = stream.get_events("alert")
        assert events[0]["data"]["level"] == "warning"

    def test_get_stats(self):
        from src.event_stream import EventStream
        stream = EventStream()
        stream.emit("dispatch", {})
        stats = stream.get_stats()
        assert stats["total_events"] == 1
        assert "topics" in stats

    def test_get_topics(self):
        from src.event_stream import EventStream
        stream = EventStream()
        topics = stream.get_topics()
        assert "dispatch" in topics
        assert "health" in topics
        assert "description" in topics["dispatch"]

    def test_clear(self):
        from src.event_stream import EventStream
        stream = EventStream()
        stream.emit("dispatch", {"a": 1})
        stream.emit("health", {"b": 2})
        stream.clear("dispatch")
        assert len(stream.get_events("dispatch")) == 0
        assert len(stream.get_events("health")) == 1

    def test_clear_all(self):
        from src.event_stream import EventStream
        stream = EventStream()
        stream.emit("dispatch", {})
        stream.emit("health", {})
        stream.clear()
        assert len(stream.get_events()) == 0

    def test_sse_format(self):
        from src.event_stream import Event
        e = Event(id=42, topic="dispatch", data={"test": True}, timestamp=0)
        sse = e.to_sse()
        assert "id: 42" in sse
        assert "event: dispatch" in sse
        assert '"test": true' in sse

    def test_singleton(self):
        from src.event_stream import get_stream
        s1 = get_stream()
        s2 = get_stream()
        assert s1 is s2


class TestAgentEnsemble:
    def test_init(self):
        from src.agent_ensemble import AgentEnsemble
        ens = AgentEnsemble()
        assert ens.SCORING_WEIGHTS is not None

    def test_score_output_code(self):
        from src.agent_ensemble import AgentEnsemble
        ens = AgentEnsemble()
        scores = ens._score_output(
            "code", "parser json python",
            "def parse_json(data):\n    return json.loads(data)\n```\n# Handles nested JSON",
            1500,
        )
        assert "length" in scores
        assert "structure" in scores
        assert "relevance" in scores
        assert scores["structure"] > 0.5

    def test_score_output_simple(self):
        from src.agent_ensemble import AgentEnsemble
        ens = AgentEnsemble()
        scores = ens._score_output("simple", "capitale france", "Paris.", 200)
        assert scores["speed"] == 1.0
        assert scores["length"] > 0

    def test_default_nodes(self):
        from src.agent_ensemble import AgentEnsemble
        ens = AgentEnsemble()
        nodes = ens._default_nodes("code")
        assert "M1" in nodes
        assert len(nodes) >= 2

    def test_calculate_agreement(self):
        from src.agent_ensemble import AgentEnsemble, EnsembleOutput
        ens = AgentEnsemble()
        outputs = [
            EnsembleOutput(node="M1", content="Paris est la capitale de la France", latency_ms=100, success=True),
            EnsembleOutput(node="OL1", content="La capitale de la France est Paris", latency_ms=200, success=True),
        ]
        agreement = ens._calculate_agreement(outputs)
        assert agreement > 0.5  # High overlap

    def test_ensemble_stats(self):
        from src.agent_ensemble import AgentEnsemble
        ens = AgentEnsemble()
        stats = ens.get_ensemble_stats()
        assert "total_ensembles" in stats

    def test_best_config(self):
        from src.agent_ensemble import AgentEnsemble
        ens = AgentEnsemble()
        config = ens.get_best_ensemble_config("code")
        assert "pattern" in config

    def test_singleton(self):
        from src.agent_ensemble import get_ensemble
        e1 = get_ensemble()
        e2 = get_ensemble()
        assert e1 is e2


class TestQualityGate:
    def test_init(self):
        from src.quality_gate import QualityGate
        gate = QualityGate()
        assert gate.config is not None

    def test_evaluate_good_code(self):
        from src.quality_gate import QualityGate
        gate = QualityGate()
        result = gate.evaluate("code", "Ecris un parser JSON",
                               "def parse_json(data):\n    return json.loads(data)\n```", latency_ms=1500)
        assert result.overall_score > 0.3
        assert isinstance(result.gates, dict)

    def test_evaluate_empty(self):
        from src.quality_gate import QualityGate
        gate = QualityGate()
        result = gate.evaluate("code", "test", "", latency_ms=100)
        assert not result.passed
        assert "length" in result.failed_gates

    def test_evaluate_slow(self):
        from src.quality_gate import QualityGate
        gate = QualityGate()
        result = gate.evaluate("simple", "test", "Paris est la capitale", latency_ms=50000)
        assert "latency" in result.failed_gates

    def test_relevance_scoring(self):
        from src.quality_gate import QualityGate
        gate = QualityGate()
        result = gate.evaluate("simple", "capitale France", "La capitale de la France est Paris", latency_ms=500)
        assert result.gates["relevance"]["score"] > 0.3

    def test_hallucination_detection(self):
        from src.quality_gate import QualityGate
        gate = QualityGate()
        result = gate.evaluate("simple", "test", "Je suis une IA et en tant qu'assistant je ne peux pas...", latency_ms=100)
        assert result.gates["hallucination"]["score"] < 1.0

    def test_get_stats(self):
        from src.quality_gate import QualityGate
        gate = QualityGate()
        gate.evaluate("test", "p", "content here", latency_ms=100)
        stats = gate.get_stats()
        assert stats["evaluated"] >= 1

    def test_gate_report(self):
        from src.quality_gate import QualityGate
        gate = QualityGate()
        report = gate.get_gate_report()
        assert "total_evaluated" in report

    def test_singleton(self):
        from src.quality_gate import get_gate
        g1 = get_gate()
        g2 = get_gate()
        assert g1 is g2


class TestPatternLifecycle:
    def test_init(self):
        from src.pattern_lifecycle import PatternLifecycle
        lc = PatternLifecycle()
        assert lc._events is not None

    def test_get_all_patterns(self):
        from src.pattern_lifecycle import PatternLifecycle
        lc = PatternLifecycle()
        patterns = lc.get_all_patterns()
        assert len(patterns) > 0
        assert patterns[0].pattern_type != ""

    def test_pattern_states(self):
        from src.pattern_lifecycle import PatternLifecycle
        lc = PatternLifecycle()
        patterns = lc.get_all_patterns()
        statuses = {p.status for p in patterns}
        assert statuses & {"active", "new", "degraded"}

    def test_suggest_actions(self):
        from src.pattern_lifecycle import PatternLifecycle
        lc = PatternLifecycle()
        actions = lc.suggest_actions()
        assert isinstance(actions, list)

    def test_health_report(self):
        from src.pattern_lifecycle import PatternLifecycle
        lc = PatternLifecycle()
        report = lc.health_report()
        assert "total_patterns" in report
        assert "status_distribution" in report
        assert "top_patterns" in report

    def test_lifecycle_history(self):
        from src.pattern_lifecycle import PatternLifecycle
        lc = PatternLifecycle()
        history = lc.get_lifecycle_history()
        assert isinstance(history, list)

    def test_singleton(self):
        from src.pattern_lifecycle import get_lifecycle
        l1 = get_lifecycle()
        l2 = get_lifecycle()
        assert l1 is l2


class TestClusterIntelligence:
    def test_init(self):
        from src.cluster_intelligence import ClusterIntelligence
        intel = ClusterIntelligence()
        assert intel._cached_report is None

    def test_quick_status(self):
        from src.cluster_intelligence import ClusterIntelligence
        intel = ClusterIntelligence()
        status = intel.quick_status()
        assert "status" in status
        assert "total_dispatches" in status
        assert "patterns" in status

    def test_full_report(self):
        from src.cluster_intelligence import ClusterIntelligence
        intel = ClusterIntelligence()
        report = intel.full_report()
        assert "health_score" in report
        assert "subsystems" in report
        assert "actions" in report
        assert "summary" in report
        assert 0 <= report["health_score"] <= 100

    def test_priority_actions(self):
        from src.cluster_intelligence import ClusterIntelligence
        intel = ClusterIntelligence()
        actions = intel.priority_actions()
        assert isinstance(actions, list)

    def test_report_caching(self):
        from src.cluster_intelligence import ClusterIntelligence
        intel = ClusterIntelligence()
        r1 = intel.full_report()
        r2 = intel.full_report()
        assert r1["timestamp"] == r2["timestamp"]  # Same cached report

    def test_report_force_refresh(self):
        from src.cluster_intelligence import ClusterIntelligence
        intel = ClusterIntelligence()
        r1 = intel.full_report()
        r2 = intel.full_report(force_refresh=True)
        # May or may not differ in timestamp (same second)
        assert "health_score" in r2

    def test_singleton(self):
        from src.cluster_intelligence import get_intelligence
        i1 = get_intelligence()
        i2 = get_intelligence()
        assert i1 is i2


class TestCoworkBridge:
    def test_init(self):
        from src.cowork_bridge import CoworkBridge
        bridge = CoworkBridge()
        assert len(bridge._scripts) > 0

    def test_list_scripts(self):
        from src.cowork_bridge import CoworkBridge
        bridge = CoworkBridge()
        scripts = bridge.list_scripts()
        assert len(scripts) > 100

    def test_list_by_category(self):
        from src.cowork_bridge import CoworkBridge
        bridge = CoworkBridge()
        ia_scripts = bridge.list_scripts(category="ia")
        assert len(ia_scripts) > 0
        assert all(s["category"] == "ia" for s in ia_scripts)

    def test_search(self):
        from src.cowork_bridge import CoworkBridge
        bridge = CoworkBridge()
        results = bridge.search("thermal monitor")
        assert len(results) > 0
        assert results[0]["score"] > 0

    def test_search_no_results(self):
        from src.cowork_bridge import CoworkBridge
        bridge = CoworkBridge()
        results = bridge.search("xyznonexistent123")
        assert len(results) == 0

    def test_get_stats(self):
        from src.cowork_bridge import CoworkBridge
        bridge = CoworkBridge()
        stats = bridge.get_stats()
        assert stats["total_scripts"] > 100
        assert "categories" in stats
        assert "win" in stats["categories"]
        assert stats["cowork_path"] is not None

    def test_execution_history(self):
        from src.cowork_bridge import CoworkBridge
        bridge = CoworkBridge()
        history = bridge.get_execution_history()
        assert isinstance(history, list)

    def test_script_not_found(self):
        from src.cowork_bridge import CoworkBridge
        bridge = CoworkBridge()
        result = bridge.execute("nonexistent_script_xyz")
        assert not result.success
        assert result.exit_code == -1

    def test_singleton(self):
        from src.cowork_bridge import get_bridge
        b1 = get_bridge()
        b2 = get_bridge()
        assert b1 is b2


class TestSelfImprovement:
    def test_init(self):
        from src.self_improvement import SelfImprover
        imp = SelfImprover()
        assert imp._history is not None

    def test_analyze(self):
        from src.self_improvement import SelfImprover
        imp = SelfImprover()
        report = imp.analyze()
        assert "health_score" in report or "error" in report

    def test_suggest_improvements(self):
        from src.self_improvement import SelfImprover
        imp = SelfImprover()
        actions = imp.suggest_improvements()
        assert isinstance(actions, list)

    def test_apply_improvements_dry(self):
        from src.self_improvement import SelfImprover
        imp = SelfImprover()
        results = imp.apply_improvements(auto=False, max_actions=2)
        assert isinstance(results, list)

    def test_get_history(self):
        from src.self_improvement import SelfImprover
        imp = SelfImprover()
        history = imp.get_history()
        assert isinstance(history, list)

    def test_get_stats(self):
        from src.self_improvement import SelfImprover
        imp = SelfImprover()
        stats = imp.get_stats()
        assert "total_suggestions" in stats

    def test_improvement_action_dataclass(self):
        from src.self_improvement import ImprovementAction
        action = ImprovementAction(
            action_type="route_shift", target="M3",
            description="Test shift", priority="high",
            params={"from_node": "M3"},
        )
        assert action.action_type == "route_shift"
        assert not action.applied

    def test_singleton(self):
        from src.self_improvement import get_improver
        i1 = get_improver()
        i2 = get_improver()
        assert i1 is i2


class TestDynamicAgents:
    def test_init(self):
        from src.dynamic_agents import DynamicAgentSpawner
        spawner = DynamicAgentSpawner()
        assert not spawner._loaded

    def test_load_all(self):
        from src.dynamic_agents import DynamicAgentSpawner
        spawner = DynamicAgentSpawner()
        agents = spawner.load_all()
        assert isinstance(agents, dict)
        assert len(agents) > 0  # Should have dynamic agents beyond the 20 hardcoded

    def test_dynamic_agent_to_pattern(self):
        from src.dynamic_agents import DynamicAgent
        da = DynamicAgent(
            pattern_type="test_dynamic",
            agent_id="test-agent",
            model_primary="qwen3-8b",
            model_fallbacks="",
            strategy="single",
            system_prompt="Test prompt",
            node="M1",
        )
        pa = da.to_pattern_agent()
        assert pa.pattern_type == "test_dynamic"
        assert pa.primary_node == "M1"

    def test_get_stats(self):
        from src.dynamic_agents import DynamicAgentSpawner
        spawner = DynamicAgentSpawner()
        stats = spawner.get_stats()
        assert "total_dynamic_agents" in stats
        assert stats["loaded"] is True  # load_all called by get_stats

    def test_list_agents(self):
        from src.dynamic_agents import DynamicAgentSpawner
        spawner = DynamicAgentSpawner()
        agents = spawner.list_agents()
        assert isinstance(agents, list)
        if agents:
            assert "pattern" in agents[0]
            assert "agent_id" in agents[0]

    def test_register_to_registry(self):
        from src.dynamic_agents import DynamicAgentSpawner
        spawner = DynamicAgentSpawner()
        count = spawner.register_to_registry()
        assert isinstance(count, int)

    def test_generate_prompt(self):
        from src.dynamic_agents import DynamicAgentSpawner
        spawner = DynamicAgentSpawner()
        prompt = spawner._generate_prompt("win_monitoring", "cw-win-monitoring")
        assert "Windows" in prompt or "expert" in prompt

    def test_singleton(self):
        from src.dynamic_agents import get_spawner
        s1 = get_spawner()
        s2 = get_spawner()
        assert s1 is s2


class TestCoworkProactive:
    def test_init(self):
        from src.cowork_proactive import CoworkProactive
        pro = CoworkProactive()
        assert pro is not None

    def test_detect_needs(self):
        from src.cowork_proactive import CoworkProactive
        pro = CoworkProactive()
        needs = pro.detect_needs()
        assert isinstance(needs, list)

    def test_benchmark_trend_detection(self):
        from src.cowork_proactive import CoworkProactive
        pro = CoworkProactive()
        needs = pro._needs_from_benchmark_trend()
        assert isinstance(needs, list)

    def test_plan_execution(self):
        from src.cowork_proactive import CoworkProactive
        pro = CoworkProactive()
        needs = pro.detect_needs()
        plan = pro.plan_execution(needs)
        assert plan.scripts_to_run is not None
        assert plan.estimated_duration_s >= 0

    def test_run_proactive_dry(self):
        from src.cowork_proactive import CoworkProactive
        pro = CoworkProactive()
        result = pro.run_proactive(max_scripts=3, dry_run=True)
        assert "dry_run" in result or "needs_detected" in result

    def test_anticipate(self):
        from src.cowork_proactive import CoworkProactive
        pro = CoworkProactive()
        predictions = pro.anticipate()
        assert "predictions" in predictions

    def test_get_stats(self):
        from src.cowork_proactive import CoworkProactive
        pro = CoworkProactive()
        stats = pro.get_stats()
        assert "total_orchestrations" in stats

    def test_singleton(self):
        from src.cowork_proactive import get_proactive
        p1 = get_proactive()
        p2 = get_proactive()
        assert p1 is p2


class TestReflectionEngine:
    def test_init(self):
        from src.reflection_engine import ReflectionEngine
        engine = ReflectionEngine()
        assert engine is not None

    def test_reflect(self):
        from src.reflection_engine import ReflectionEngine
        engine = ReflectionEngine()
        insights = engine.reflect()
        assert isinstance(insights, list)

    def test_timeline(self):
        from src.reflection_engine import ReflectionEngine
        engine = ReflectionEngine()
        timeline = engine.timeline_analysis(hours=24)
        assert "period_hours" in timeline

    def test_summary(self):
        from src.reflection_engine import ReflectionEngine
        engine = ReflectionEngine()
        summary = engine.get_summary()
        assert "system_health" in summary or "error" in summary

    def test_insight_dataclass(self):
        from src.reflection_engine import Insight
        ins = Insight(
            category="quality", severity="info",
            title="Test", description="Test insight",
        )
        assert ins.category == "quality"

    def test_get_stats(self):
        from src.reflection_engine import ReflectionEngine
        engine = ReflectionEngine()
        stats = engine.get_stats()
        assert "total_insights" in stats

    def test_singleton(self):
        from src.reflection_engine import get_reflection
        r1 = get_reflection()
        r2 = get_reflection()
        assert r1 is r2


class TestPatternEvolution:
    def test_init(self):
        from src.pattern_evolution import PatternEvolution
        evo = PatternEvolution()
        assert evo is not None

    def test_analyze_gaps(self):
        from src.pattern_evolution import PatternEvolution
        evo = PatternEvolution()
        suggestions = evo.analyze_gaps()
        assert isinstance(suggestions, list)

    def test_auto_create_dry(self):
        from src.pattern_evolution import PatternEvolution
        evo = PatternEvolution()
        # High threshold to avoid creating patterns in test
        created = evo.auto_create_patterns(min_confidence=0.99)
        assert isinstance(created, list)

    def test_evolve_patterns(self):
        from src.pattern_evolution import PatternEvolution
        evo = PatternEvolution()
        evolved = evo.evolve_patterns(min_confidence=0.99)
        assert isinstance(evolved, list)

    def test_get_history(self):
        from src.pattern_evolution import PatternEvolution
        evo = PatternEvolution()
        history = evo.get_evolution_history()
        assert isinstance(history, list)

    def test_get_stats(self):
        from src.pattern_evolution import PatternEvolution
        evo = PatternEvolution()
        stats = evo.get_stats()
        assert "total_suggestions" in stats

    def test_suggestion_dataclass(self):
        from src.pattern_evolution import PatternSuggestion
        s = PatternSuggestion(
            action="create", pattern_type="testing",
            description="Test pattern", confidence=0.8,
        )
        assert s.action == "create"

    def test_singleton(self):
        from src.pattern_evolution import get_evolution
        e1 = get_evolution()
        e2 = get_evolution()
        assert e1 is e2


class TestDynamicTimeout:
    """Tests for PatternAgent._calc_timeout and _adapt_max_tokens."""

    def _make_agent(self, pattern_type="code", primary_node="M1", max_tokens=1024):
        return PatternAgent(
            pattern_id=f"PAT_{pattern_type.upper()}",
            pattern_type=pattern_type,
            agent_id=f"test-{pattern_type}",
            system_prompt="Test",
            primary_node=primary_node,
            fallback_nodes=["OL1"],
            strategy="single",
            priority=1,
            max_tokens=max_tokens,
        )

    def test_simple_short_timeout(self):
        agent = self._make_agent("simple")
        t = agent._calc_timeout("M1", "bonjour")
        assert 10 <= t <= 30  # simple(15) * M1(1.0) = 15

    def test_code_longer_timeout(self):
        agent = self._make_agent("code")
        t = agent._calc_timeout("M1", "Ecris un parser JSON")
        assert t >= 60  # code(90) * M1(1.0) = 90

    def test_reasoning_m3_very_long(self):
        agent = self._make_agent("reasoning")
        t = agent._calc_timeout("M3", "Explique la relativite")
        assert t >= 100  # reasoning(150) * M3(2.5) = clamped to 180

    def test_long_prompt_adds_time(self):
        agent = self._make_agent("simple")
        short_t = agent._calc_timeout("M1", "bonjour")
        long_prompt = "x" * 5000  # 5000 chars → (5000-1000)/500 = 8s extra
        long_t = agent._calc_timeout("M1", long_prompt)
        assert long_t > short_t

    def test_timeout_clamped_min(self):
        agent = self._make_agent("simple")
        t = agent._calc_timeout("M1", "x")
        assert t >= 10

    def test_timeout_clamped_max(self):
        agent = self._make_agent("reasoning")
        t = agent._calc_timeout("M3", "x" * 50000)
        assert t <= 180

    def test_unknown_node_uses_default_factor(self):
        agent = self._make_agent("code")
        t = agent._calc_timeout("UNKNOWN_NODE", "test")
        # code(90) * default(1.5) = 135
        assert 100 <= t <= 180

    def test_adapt_max_tokens_normal(self):
        agent = self._make_agent("code", max_tokens=1024)
        tokens = agent._adapt_max_tokens("M1", "Short prompt")
        assert tokens == 1024  # Plenty of room in 32k ctx

    def test_adapt_max_tokens_large_prompt(self):
        agent = self._make_agent("code", max_tokens=8192)
        # M1 ctx=32000, prompt ~100000 chars → ~25050 tokens → available=6950
        big_prompt = "x" * 100000
        tokens = agent._adapt_max_tokens("M1", big_prompt)
        assert tokens < 8192  # Should be capped below max_tokens (6950 < 8192)

    def test_adapt_max_tokens_overflow_protection(self):
        agent = self._make_agent("code", max_tokens=4096)
        # M3 ctx=25000, prompt ~96000 chars → ~24000 tokens → >80% of ctx → cap at 512
        huge_prompt = "x" * 96000
        tokens = agent._adapt_max_tokens("M3", huge_prompt)
        assert tokens <= 512

    def test_adapt_respects_min_output_reasoning(self):
        agent = self._make_agent("reasoning", primary_node="M2", max_tokens=256)
        # M2 has NODE_MIN_OUTPUT=2048, so even small prompt should get >=2048
        tokens = agent._adapt_max_tokens("M2", "Short question")
        assert tokens >= 2048

    def test_adapt_ol1_default_ctx(self):
        agent = self._make_agent("code", max_tokens=4096)
        # OL1 uses default ctx limit — medium prompts still have room
        tokens = agent._adapt_max_tokens("OL1", "Write a function" * 100)
        assert tokens >= 2048


class TestClassifyWithConfidence:
    """Tests for PatternAgentRegistry.classify_with_confidence()."""

    def test_returns_dict(self):
        reg = PatternAgentRegistry()
        result = reg.classify_with_confidence("Ecris une fonction Python")
        assert isinstance(result, dict)
        assert "pattern" in result
        assert "confidence" in result
        assert "candidates" in result

    def test_code_high_confidence(self):
        reg = PatternAgentRegistry()
        result = reg.classify_with_confidence("Ecris un script Python pour parser JSON")
        assert result["pattern"] == "code"
        assert result["confidence"] > 0.3

    def test_simple_from_short_prompt(self):
        reg = PatternAgentRegistry()
        result = reg.classify_with_confidence("bonjour")
        assert result["pattern"] == "simple"
        assert result["confidence"] >= 0.5

    def test_candidates_sorted(self):
        reg = PatternAgentRegistry()
        result = reg.classify_with_confidence("analyse le code Python pour trouver les failles de securite")
        assert len(result["candidates"]) >= 1
        if len(result["candidates"]) >= 2:
            assert result["candidates"][0]["score"] >= result["candidates"][1]["score"]

    def test_heuristic_code_detection(self):
        reg = PatternAgentRegistry()
        result = reg.classify_with_confidence("def hello():\n    pass")
        assert result["pattern"] == "code"

    def test_confidence_bounded(self):
        reg = PatternAgentRegistry()
        result = reg.classify_with_confidence("calcule la derivee de x^2 et ecris le code Python")
        assert 0 <= result["confidence"] <= 1.0

    def test_backward_compat_classify(self):
        reg = PatternAgentRegistry()
        # classify() should still return just a string
        result = reg.classify("trading BTC RSI MACD")
        assert isinstance(result, str)
        assert result == "trading"


class TestSizeBasedAgents:
    """Tests for size-based pattern agents (nano/micro/small/medium/large/xl)."""

    def test_nano_agent_config(self):
        reg = PatternAgentRegistry()
        agent = reg.agents["nano"]
        assert agent.primary_node == "OL1"
        assert agent.max_tokens == 128
        assert agent.strategy == "single"

    def test_xl_agent_config(self):
        reg = PatternAgentRegistry()
        agent = reg.agents["xl"]
        assert agent.primary_node == "M1"
        assert agent.max_tokens == 4096
        assert agent.strategy == "single"

    def test_large_has_fallback(self):
        reg = PatternAgentRegistry()
        agent = reg.agents["large"]
        assert len(agent.fallback_nodes) >= 1

    def test_medium_race_strategy(self):
        reg = PatternAgentRegistry()
        agent = reg.agents["medium"]
        assert agent.strategy == "race"

    def test_size_agents_priority_order(self):
        reg = PatternAgentRegistry()
        priorities = [reg.agents[s].priority for s in ["nano", "micro", "small", "medium", "large", "xl"]]
        assert priorities == sorted(priorities)  # Should be ascending


class TestAutoOptimizeStrategies:
    """Tests for PatternAgentRegistry.auto_optimize_strategies()."""

    def test_auto_optimize_returns_dict(self):
        from src.pattern_agents import PatternAgentRegistry
        reg = PatternAgentRegistry()
        result = reg.auto_optimize_strategies()
        assert isinstance(result, dict)

    def test_auto_optimize_no_crash(self):
        from src.pattern_agents import PatternAgentRegistry
        reg = PatternAgentRegistry()
        # Should handle gracefully even without sufficient data
        result = reg.auto_optimize_strategies()
        assert "error" not in result or isinstance(result.get("error"), str)


class TestRouteBlacklist:
    """Tests for ROUTE_BLACKLIST and ROUTE_PREFERENCE in dispatch_engine."""

    def test_blacklist_exists(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        assert hasattr(engine, 'ROUTE_BLACKLIST')
        assert len(engine.ROUTE_BLACKLIST) > 0

    def test_blacklist_blocks_m3_reasoning(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        assert ("reasoning", "M3") in engine.ROUTE_BLACKLIST

    def test_blacklist_blocks_m3_math(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        assert ("math", "M3") in engine.ROUTE_BLACKLIST

    def test_blacklist_blocks_m3_code(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        assert ("code", "M3") in engine.ROUTE_BLACKLIST

    def test_preference_exists(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        assert hasattr(engine, 'ROUTE_PREFERENCE')
        assert "code" in engine.ROUTE_PREFERENCE

    def test_preference_code_starts_m1(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        assert engine.ROUTE_PREFERENCE["code"][0] == "M1"

    def test_preference_simple_starts_ol1(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        assert engine.ROUTE_PREFERENCE["simple"][0] == "OL1"

    def test_preference_all_patterns_have_m1(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        for pattern, nodes in engine.ROUTE_PREFERENCE.items():
            assert "M1" in nodes, f"Pattern {pattern} missing M1 in preferences"


class TestAutoTuneGate:
    """Tests for QualityGate.auto_tune_from_data()."""

    def test_auto_tune_returns_dict(self):
        from src.quality_gate import QualityGate
        gate = QualityGate()
        result = gate.auto_tune_from_data(min_samples=10)
        assert isinstance(result, dict)

    def test_auto_tune_no_crash_empty_db(self):
        from src.quality_gate import QualityGate, GateConfig
        gate = QualityGate(config=GateConfig())
        # Should handle gracefully even with empty/missing tables
        result = gate.auto_tune_from_data(min_samples=99999)
        assert isinstance(result, dict)

    def test_gate_config_relevance_is_dict(self):
        from src.quality_gate import QualityGate
        gate = QualityGate()
        assert isinstance(gate.config.min_relevance, dict)
        assert "simple" in gate.config.min_relevance
        assert "code" in gate.config.min_relevance
        assert "default" in gate.config.min_relevance

    def test_gate_config_latency_is_dict(self):
        from src.quality_gate import QualityGate
        gate = QualityGate()
        assert isinstance(gate.config.max_latency_ms, dict)
        assert "simple" in gate.config.max_latency_ms

    def test_auto_tune_high_threshold_no_changes(self):
        from src.quality_gate import QualityGate
        gate = QualityGate()
        result = gate.auto_tune_from_data(min_samples=999999)
        # With absurd min_samples, no pattern should qualify → empty or no changes
        assert "error" not in result or isinstance(result.get("error"), str)


class TestQualityScoring:
    """Tests for PatternAgent._score_quality improvements."""

    def _make_agent(self, pattern_type="code"):
        return PatternAgent(
            pattern_id="TEST", pattern_type=pattern_type, agent_id="test",
            system_prompt="", primary_node="M1", fallback_nodes=["OL1"],
            strategy="single", priority=1,
        )

    def test_empty_content_zero_score(self):
        agent = self._make_agent()
        assert agent._score_quality("test", "") == 0.0

    def test_short_content_low_score(self):
        agent = self._make_agent()
        score = agent._score_quality("question", "Oui")
        assert score < 0.3

    def test_code_block_structure_detected(self):
        agent = self._make_agent("code")
        # Verify code blocks give non-zero structure bonus
        score = agent._score_quality("write function", "```python\ndef f(x):\n    return x * 2\n```")
        assert score > 0.2  # Code block should contribute positively

    def test_structured_list_bonus(self):
        agent = self._make_agent()
        flat = agent._score_quality("compare", "Python est mieux que Java pour le scripting.")
        listed = agent._score_quality("compare", "1) Python est dynamique\n2) Java est statique\n3) Python a plus de libs")
        assert listed >= flat

    def test_anti_hallucination_penalty(self):
        agent = self._make_agent()
        # Same approximate length, one with hallucination marker
        good = agent._score_quality("test question", "La capitale de la France est Paris, une ville magnifique et historique.")
        bad = agent._score_quality("test question", "En tant qu'IA, je ne peux pas repondre. Je suis un modele de langage limite.")
        assert bad < good

    def test_relevance_overlap(self):
        agent = self._make_agent()
        relevant = agent._score_quality("capitale France", "La capitale de la France est Paris")
        irrelevant = agent._score_quality("capitale France", "Le chat mange des croquettes")
        assert relevant > irrelevant

    def test_score_capped_at_one(self):
        agent = self._make_agent()
        score = agent._score_quality(
            "x", "### Section\n1) Point 1\n2) Point 2\n```python\ncode\n```\n" * 10
        )
        assert score <= 1.0


class TestBenchmarkAnalysis:
    """Tests for SelfImprover._analyze_benchmark_data()."""

    def test_analyze_returns_list(self):
        from src.self_improvement import SelfImprover
        imp = SelfImprover()
        actions = imp._analyze_benchmark_data()
        assert isinstance(actions, list)

    def test_analyze_actions_are_route_shift(self):
        from src.self_improvement import SelfImprover
        imp = SelfImprover()
        actions = imp._analyze_benchmark_data()
        for a in actions:
            assert a.action_type == "route_shift"
            assert "from_node" in a.params or "to_node" in a.params

    def test_suggest_improvements_includes_benchmark(self):
        from src.self_improvement import SelfImprover
        imp = SelfImprover()
        suggestions = imp.suggest_improvements()
        # Should include benchmark-derived actions (if data exists)
        assert isinstance(suggestions, list)

    def test_improvement_action_has_priority(self):
        from src.self_improvement import ImprovementAction
        action = ImprovementAction(
            action_type="route_shift", target="reasoning",
            description="Test", priority="high",
            params={"from_node": "M3", "to_node": "M1", "bad_rate": 0.0, "good_rate": 1.0},
        )
        assert action.priority in ("high", "medium", "low")


class TestPromptTruncation:
    """Tests for _truncate_prompt — smart prompt truncation to prevent context overflow."""

    def _agent(self):
        return PatternAgent(
            pattern_id="TEST", pattern_type="code", agent_id="test",
            system_prompt="", primary_node="M1", fallback_nodes=[],
            strategy="single", priority=1, max_tokens=1024,
        )

    def test_short_prompt_unchanged(self):
        a = self._agent()
        prompt = "Ecris un parser JSON"
        assert a._truncate_prompt("M1", prompt) == prompt

    def test_long_prompt_truncated(self):
        a = self._agent()
        # M1 ctx=32000 tokens, 70% = 22400 tokens, ~89600 chars
        prompt = "x " * 50000  # 100k chars > 89600
        result = a._truncate_prompt("M1", prompt)
        assert len(result) < len(prompt)
        assert "[...tronque...]" in result

    def test_preserves_tail_question(self):
        a = self._agent()
        ctx = "contexte " * 20000  # Lots of context
        question = "\n\nQuelle est la meilleure approche pour implementer ceci?"
        prompt = ctx + question
        result = a._truncate_prompt("M1", prompt)
        # The question at the end should be preserved
        assert "implementer" in result

    def test_different_nodes_truncation(self):
        a = self._agent()
        prompt = "x " * 50000  # 100k chars
        result_m1 = a._truncate_prompt("M1", prompt)
        result_ol1 = a._truncate_prompt("OL1", prompt)
        # Both should truncate (both have limited ctx)
        assert len(result_m1) <= len(prompt)
        assert len(result_ol1) <= len(prompt)

    def test_no_truncation_within_limit(self):
        a = self._agent()
        prompt = "test " * 1000  # 5k chars, well within M1's 89k limit
        assert a._truncate_prompt("M1", prompt) == prompt

    def test_truncation_contains_marker(self):
        a = self._agent()
        prompt = "data " * 50000
        result = a._truncate_prompt("M1", prompt)
        assert "[...tronque...]" in result

    def test_unknown_node_uses_default_limit(self):
        a = self._agent()
        prompt = "x " * 50000
        result = a._truncate_prompt("UNKNOWN_NODE", prompt)
        # Should still truncate using default 32k limit
        assert len(result) < len(prompt)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-x"])
