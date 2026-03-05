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
    def test_20_agents_registered(self):
        reg = PatternAgentRegistry()
        assert len(reg.agents) == 20

    def test_all_pattern_types(self):
        reg = PatternAgentRegistry()
        expected = {"classifier", "simple", "web", "code", "analysis", "system",
                    "creative", "math", "data", "devops", "reasoning", "trading",
                    "security", "architecture",
                    "voice", "email", "automation", "learning", "monitoring", "optimization"}
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
        assert len(agents) == 20
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
        assert f.db_path == "F:/BUREAU/turbo/etoile.db"

    def test_report(self):
        f = AgentFactory()
        report = f.generate_report()
        assert "total_patterns" in report
        assert "total_dispatches" in report
        assert report["total_patterns"] >= 14

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

    def test_20_agents(self):
        assert len(AGENT_CONFIGS) == 20

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
        assert len(router.circuits) >= 6
        assert len(router.health) >= 6

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
        assert d.db_path == "F:/BUREAU/turbo/etoile.db"

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

    def test_score_quality_empty(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        assert engine._score_quality("code", "", 0, False) == 0.0

    def test_score_quality_good(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        score = engine._score_quality("code", "def parse_json(data):\n    return json.loads(data)\n```", 1500, True)
        assert score > 0.5

    def test_score_quality_simple(self):
        from src.dispatch_engine import DispatchEngine
        engine = DispatchEngine()
        score = engine._score_quality("simple", "Paris est la capitale de la France.", 500, True)
        assert score > 0.3

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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-x"])
