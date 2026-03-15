"""JARVIS Agent Collaboration — Inter-agent messaging and task delegation.

Enables agents to:
  - Send messages to other agents (request/response)
  - Delegate sub-tasks with context passing
  - Build collaborative chains (agent A asks agent B, uses result for agent C)
  - Share working context via a message bus

Usage:
    from src.agent_collaboration import AgentBus, get_bus
    bus = get_bus()
    response = await bus.ask("code", "Write a parser", context={"lang": "python"})
    chain = await bus.chain(["classifier", "code", "security"], "Build a secure API")
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from src.pattern_agents import PatternAgentRegistry, AgentResult


__all__ = [
    "AgentBus",
    "AgentMessage",
    "CollaborationResult",
    "get_bus",
]

logger = logging.getLogger("jarvis.agent_collaboration")


@dataclass
class AgentMessage:
    """A message between agents."""
    msg_id: str
    from_agent: str
    to_agent: str
    content: str
    msg_type: str = "request"   # request, response, delegate, broadcast
    context: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    response: Optional[str] = None
    latency_ms: float = 0
    ok: bool = False


@dataclass
class CollaborationResult:
    """Result of a multi-agent collaboration."""
    chain: list[str]            # Agent chain executed
    messages: list[AgentMessage]
    final_content: str
    total_latency_ms: float
    ok: bool
    steps_ok: int
    steps_total: int

    @property
    def summary(self) -> str:
        return (f"Chain: {' -> '.join(self.chain)} | "
                f"{self.steps_ok}/{self.steps_total} OK | "
                f"{self.total_latency_ms:.0f}ms")


class AgentBus:
    """Message bus for inter-agent communication."""

    def __init__(self):
        self.registry = PatternAgentRegistry()
        self._message_log: list[AgentMessage] = []
        self._subscribers: dict[str, list] = defaultdict(list)

    async def ask(self, target_pattern: str, prompt: str,
                  context: dict = None, from_agent: str = "orchestrator") -> AgentMessage:
        """Send a request to an agent and get a response."""
        msg_id = f"msg_{int(time.time()*1000)}"
        msg = AgentMessage(
            msg_id=msg_id,
            from_agent=from_agent,
            to_agent=target_pattern,
            content=prompt,
            msg_type="request",
            context=context or {},
        )

        # Enrich prompt with context
        enriched = prompt
        if context:
            ctx_str = "\n".join(f"- {k}: {v}" for k, v in context.items() if v)
            if ctx_str:
                enriched = f"Context:\n{ctx_str}\n\nTask: {prompt}"

        # Dispatch to the target agent
        result = await self.registry.dispatch(target_pattern, enriched)

        msg.response = result.content
        msg.latency_ms = result.latency_ms
        msg.ok = result.ok
        msg.msg_type = "response"

        self._message_log.append(msg)
        self._notify_subscribers(target_pattern, msg)

        return msg

    async def delegate(self, from_pattern: str, to_pattern: str,
                       task: str, parent_context: dict = None) -> AgentMessage:
        """Delegate a sub-task from one agent to another."""
        context = parent_context or {}
        context["delegated_from"] = from_pattern
        context["delegation_type"] = "sub-task"

        msg = await self.ask(to_pattern, task, context=context, from_agent=from_pattern)
        msg.msg_type = "delegate"
        return msg

    async def chain(self, agents: list[str], prompt: str,
                    context: dict = None) -> CollaborationResult:
        """Execute a chain of agents, passing results forward."""
        t0 = time.perf_counter()
        messages = []
        current_content = prompt
        current_context = dict(context or {})
        steps_ok = 0

        for i, agent in enumerate(agents):
            # Build prompt with previous agent's output
            if i > 0 and messages and messages[-1].ok:
                prev = messages[-1]
                chain_prompt = (
                    f"Previous agent ({prev.to_agent}) said:\n{prev.response[:1500]}\n\n"
                    f"Original task: {prompt[:500]}\n\n"
                    f"Your turn ({agent}): Continue or improve the response."
                )
                current_context["prev_agent"] = prev.to_agent
                current_context["prev_response_preview"] = prev.response[:200] if prev.response else ""
            else:
                chain_prompt = current_content

            msg = await self.ask(agent, chain_prompt, context=current_context, from_agent=agents[i-1] if i > 0 else "orchestrator")
            messages.append(msg)

            if msg.ok:
                steps_ok += 1
                current_content = msg.response or current_content
            else:
                # If chain breaks, continue with what we have
                logger.warning(f"Chain step {agent} failed, continuing with previous content")

        total_ms = (time.perf_counter() - t0) * 1000

        # Final content = last successful response
        ok_msgs = [m for m in messages if m.ok]
        final = ok_msgs[-1].response if ok_msgs else "Chain failed: no successful responses"

        return CollaborationResult(
            chain=agents,
            messages=messages,
            final_content=final,
            total_latency_ms=total_ms,
            ok=steps_ok > 0,
            steps_ok=steps_ok,
            steps_total=len(agents),
        )

    async def parallel_ask(self, targets: list[str], prompt: str,
                           context: dict = None) -> list[AgentMessage]:
        """Ask multiple agents in parallel."""
        tasks = [self.ask(t, prompt, context=context) for t in targets]
        return await asyncio.gather(*tasks)

    async def debate(self, agents: list[str], question: str, rounds: int = 2) -> CollaborationResult:
        """Multi-agent debate: agents discuss and refine a response over rounds."""
        t0 = time.perf_counter()
        messages = []
        current = question

        for round_num in range(rounds):
            round_messages = []
            for agent in agents:
                context = {
                    "debate_round": round_num + 1,
                    "total_rounds": rounds,
                    "other_agents": [a for a in agents if a != agent],
                }
                if round_num > 0 and messages:
                    # Show previous round's responses
                    prev_responses = "\n".join(
                        f"[{m.to_agent}]: {m.response[:300]}"
                        for m in messages[-len(agents):]
                        if m.ok
                    )
                    debate_prompt = (
                        f"Question: {question[:500]}\n\n"
                        f"Previous round responses:\n{prev_responses}\n\n"
                        f"Round {round_num + 1}: Refine your answer considering others' views."
                    )
                else:
                    debate_prompt = current

                msg = await self.ask(agent, debate_prompt, context=context)
                round_messages.append(msg)

            messages.extend(round_messages)

        total_ms = (time.perf_counter() - t0) * 1000
        ok_msgs = [m for m in messages if m.ok]
        steps_ok = len(ok_msgs)

        # Final: pick best quality from last round or combine
        last_round = messages[-len(agents):] if messages else []
        ok_last = [m for m in last_round if m.ok]
        final = ok_last[0].response if ok_last else "Debate failed"

        return CollaborationResult(
            chain=[f"debate:{a}" for a in agents] * rounds,
            messages=messages,
            final_content=final,
            total_latency_ms=total_ms,
            ok=steps_ok > 0,
            steps_ok=steps_ok,
            steps_total=len(agents) * rounds,
        )

    def subscribe(self, pattern: str, callback):
        """Subscribe to messages for a pattern (event-driven)."""
        self._subscribers[pattern].append(callback)

    def _notify_subscribers(self, pattern: str, msg: AgentMessage):
        """Notify subscribers of a new message."""
        for cb in self._subscribers.get(pattern, []):
            try:
                cb(msg)
            except Exception as e:
                logger.warning(f"Subscriber error: {e}")

    def get_message_log(self, limit: int = 50) -> list[dict]:
        """Get recent message history."""
        return [
            {
                "id": m.msg_id,
                "from": m.from_agent,
                "to": m.to_agent,
                "type": m.msg_type,
                "ok": m.ok,
                "latency_ms": round(m.latency_ms),
                "content_preview": m.content[:100],
                "response_preview": (m.response or "")[:100],
            }
            for m in self._message_log[-limit:]
        ]

    def get_stats(self) -> dict:
        """Collaboration statistics."""
        total = len(self._message_log)
        ok = sum(1 for m in self._message_log if m.ok)
        by_agent = defaultdict(lambda: {"sent": 0, "received": 0, "ok": 0})
        for m in self._message_log:
            by_agent[m.from_agent]["sent"] += 1
            by_agent[m.to_agent]["received"] += 1
            if m.ok:
                by_agent[m.to_agent]["ok"] += 1

        return {
            "total_messages": total,
            "success_rate": ok / max(1, total),
            "avg_latency_ms": sum(m.latency_ms for m in self._message_log) / max(1, total),
            "agents": dict(by_agent),
        }

    async def close(self):
        await self.registry.close()


# Singleton
_bus: Optional[AgentBus] = None

def get_bus() -> AgentBus:
    global _bus
    if _bus is None:
        _bus = AgentBus()
    return _bus
