"""JARVIS Perplexity Bridge -- Proactive intelligence from Perplexity to JARVIS.

This module enables Perplexity (via MCP connector) to:
1. Store learnings into JARVIS memory for future use
2. Create skills/dominos based on conversation analysis
3. Trigger self-improvement cycles
4. Push context from web research back into JARVIS brain

Designed to be called by Perplexity MCP tools to make JARVIS smarter
after each interaction.

Usage:
    from src.perplexity_bridge import perplexity_bridge
    await perplexity_bridge.learn_from_interaction(prompt, response, context)
    await perplexity_bridge.suggest_improvement(area, suggestion)
"""

from __future__ import annotations

import asyncio
import logging
import time
import json
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.perplexity_bridge")


@dataclass
class InteractionRecord:
    """Record of a Perplexity <-> JARVIS interaction."""
    prompt: str
    response_summary: str
    tools_used: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    improvements_suggested: list[str] = field(default_factory=list)


class PerplexityBridge:
    """Bridge between Perplexity AI and JARVIS internal systems."""
    
    def __init__(self):
        self.interactions: list[InteractionRecord] = []
        self.improvements_pending: list[dict[str, Any]] = []
        self.skills_created: int = 0
        self.memories_stored: int = 0
    
    async def learn_from_interaction(
        self, 
        prompt: str, 
        response_summary: str,
        tools_used: list[str] | None = None,
        context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Store learnings from a Perplexity interaction into JARVIS brain.
        
        Analyzes what tools were used, what the user asked, and stores
        relevant patterns for future skill creation.
        """
        record = InteractionRecord(
            prompt=prompt,
            response_summary=response_summary[:500],
            tools_used=tools_used or [],
            context=context or {}
        )
        self.interactions.append(record)
        
        # Store in JARVIS memory
        try:
            from src.agent_memory import agent_memory
            agent_memory.store(
                content=f"Perplexity interaction: {prompt[:200]}",
                category="perplexity_learning",
                importance=0.7,
                metadata={
                    "tools_used": tools_used or [],
                    "response_preview": response_summary[:200],
                    "ts": time.time()
                }
            )
            self.memories_stored += 1
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
        
        # Log to brain for pattern analysis
        try:
            from src.brain import brain
            brain.log_action("perplexity_interaction", {
                "prompt": prompt[:300],
                "tools": tools_used or [],
                "ts": time.time()
            })
        except Exception as e:
            logger.error(f"Failed to log to brain: {e}")
        
        # Emit event for bus subscribers
        try:
            from src.event_bus import event_bus
            await event_bus.emit("perplexity.interaction", {
                "prompt": prompt[:200],
                "tools_count": len(tools_used or []),
                "ts": time.time()
            })
        except Exception:
            pass
        
        # Analyze if a skill should be created
        suggestion = await self._analyze_for_skill(record)
        
        return {
            "stored": True,
            "memory_count": self.memories_stored,
            "skill_suggestion": suggestion,
            "interaction_count": len(self.interactions)
        }
    
    async def suggest_improvement(
        self,
        area: str,
        suggestion: str,
        priority: int = 5,
        code_snippet: str | None = None
    ) -> dict[str, Any]:
        """Perplexity suggests an improvement for JARVIS.
        
        Areas: 'voice', 'trading', 'cluster', 'skills', 'performance', 'security'
        """
        improvement = {
            "area": area,
            "suggestion": suggestion,
            "priority": priority,
            "code_snippet": code_snippet,
            "ts": time.time(),
            "status": "pending"
        }
        self.improvements_pending.append(improvement)
        
        # Store as high-importance memory
        try:
            from src.agent_memory import agent_memory
            agent_memory.store(
                content=f"Improvement suggestion ({area}): {suggestion}",
                category="improvement_suggestions",
                importance=0.9,
                metadata=improvement
            )
        except Exception as e:
            logger.error(f"Failed to store improvement: {e}")
        
        # Emit event
        try:
            from src.event_bus import event_bus
            await event_bus.emit("perplexity.improvement_suggested", improvement)
        except Exception:
            pass
        
        logger.info(f"Improvement suggested for {area}: {suggestion[:100]}")
        
        return {
            "stored": True,
            "pending_improvements": len(self.improvements_pending),
            "area": area
        }
    
    async def create_skill_from_analysis(
        self,
        name: str,
        description: str,
        triggers: list[str],
        steps: list[dict[str, Any]],
        category: str = "perplexity_auto"
    ) -> dict[str, Any]:
        """Create a new JARVIS skill based on Perplexity analysis."""
        try:
            from src.brain import brain
            skill_data = {
                "name": name,
                "description": description,
                "triggers": triggers,
                "steps": steps,
                "category": category,
                "source": "perplexity_bridge",
                "created_at": time.time()
            }
            
            # Create via brain
            brain.create_skill(
                name=name,
                description=description,
                triggers=triggers,
                steps=[json.dumps(s) for s in steps],
                category=category
            )
            self.skills_created += 1
            
            # Emit event
            from src.event_bus import event_bus
            await event_bus.emit("perplexity.skill_created", skill_data)
            
            logger.info(f"Skill '{name}' created from Perplexity analysis")
            
            return {"created": True, "name": name, "total_created": self.skills_created}
            
        except Exception as e:
            logger.error(f"Failed to create skill: {e}")
            return {"created": False, "error": str(e)}
    
    async def get_context_for_query(self, query: str) -> dict[str, Any]:
        """Get JARVIS context relevant to a Perplexity query.
        
        Returns relevant memories, recent interactions, active skills,
        and system state to enrich Perplexity responses.
        """
        context: dict[str, Any] = {"query": query[:200], "ts": time.time()}
        
        # Recent memories
        try:
            from src.agent_memory import agent_memory
            memories = agent_memory.search(query, limit=5)
            context["relevant_memories"] = memories
        except Exception:
            context["relevant_memories"] = []
        
        # Recent interactions
        recent = self.interactions[-5:] if self.interactions else []
        context["recent_interactions"] = [
            {"prompt": r.prompt[:100], "tools": r.tools_used} 
            for r in recent
        ]
        
        # Pending improvements
        context["pending_improvements"] = len(self.improvements_pending)
        context["skills_created_by_perplexity"] = self.skills_created
        
        return context
    
    async def _analyze_for_skill(self, record: InteractionRecord) -> str | None:
        """Analyze if this interaction pattern should become a skill."""
        if len(self.interactions) < 3:
            return None
        
        # Check if similar prompts have been asked before
        recent_prompts = [r.prompt.lower() for r in self.interactions[-10:]]
        keywords = set()
        for p in recent_prompts:
            for word in p.split():
                if len(word) > 4:
                    keywords.add(word)
        
        # If same tools used in 3+ recent interactions, suggest skill
        tool_counts: dict[str, int] = {}
        for r in self.interactions[-10:]:
            for tool in r.tools_used:
                tool_counts[tool] = tool_counts.get(tool, 0) + 1
        
        frequent_tools = [
            t for t, c in tool_counts.items() if c >= 3
        ]
        
        if frequent_tools:
            return (
                f"Pattern dtect: outils {', '.join(frequent_tools[:3])} "
                f"utiliss frquemment. Crer un skill automatis?"
            )
        
        return None
    
    def status(self) -> dict[str, Any]:
        """Current bridge status."""
        return {
            "total_interactions": len(self.interactions),
            "memories_stored": self.memories_stored,
            "skills_created": self.skills_created,
            "improvements_pending": len(self.improvements_pending),
            "recent_tools": list(set(
                t for r in self.interactions[-5:] for t in r.tools_used
            )) if self.interactions else []
        }


# Singleton
perplexity_bridge = PerplexityBridge()

