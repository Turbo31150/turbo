#!/usr/bin/env python3
"""
AUTONOMOUS AGENT ORCHESTRATOR v1.0
Système d'agents autonomes pour LM Studio avec:
- Raisonnement auto
- Gestion pannes
- Récupération automatique
- Division de tâches
- Agents spécialisés
"""
import json
import time
import sqlite3
import requests
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

# Paths
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "database" / "lmstudio.db"
AGENTS_DIR = BASE_DIR / "agents"

# MCP Server URL
MCP_SERVER = "http://127.0.0.1:8000"

# ============================================
# BASE AGENT CLASS
# ============================================

class Agent:
    """Base autonomous agent with reasoning and recovery"""

    def __init__(self, name: str, role: str, server_preference: str = "auto"):
        self.name = name
        self.role = role
        self.server_preference = server_preference
        self.memory = []
        self.task_history = []
        self.status = "idle"

    def think(self, context: str) -> str:
        """Reasoning step - analyze situation and plan"""
        prompt = f"""You are {self.name}, role: {self.role}.

Context: {context}

Think step-by-step:
1. What is the current situation?
2. What is the goal?
3. What are the available actions?
4. What is the best course of action?
5. What could go wrong?

Provide a brief reasoning (max 100 words)."""

        response = self._query_server(prompt, max_tokens=200)

        if response.get("success"):
            reasoning = response["answer"]
            self.memory.append({
                "type": "reasoning",
                "content": reasoning,
                "timestamp": time.time()
            })
            return reasoning
        else:
            return "ERROR: Cannot reason - server unavailable"

    def execute(self, task: str, **kwargs) -> Dict:
        """Execute task with auto-recovery"""
        self.status = "working"

        # Save task to DB
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        task_id = c.execute(
            "INSERT INTO tasks VALUES (NULL, ?, ?, ?, ?, ?, ?, NULL) RETURNING id",
            (time.time(), self.name, "execute", task, "running", None)
        ).fetchone()[0]
        conn.commit()
        conn.close()

        start = time.time()

        try:
            # Think first
            reasoning = self.think(f"Task: {task}\nContext: {json.dumps(kwargs)}")

            # Execute
            result = self._execute_impl(task, **kwargs)

            duration = int((time.time() - start) * 1000)

            # Update DB
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                "UPDATE tasks SET status = ?, result = ?, duration_ms = ? WHERE id = ?",
                ("completed", json.dumps(result), duration, task_id)
            )
            conn.commit()
            conn.close()

            self.status = "idle"
            self.task_history.append({
                "task": task,
                "result": result,
                "duration_ms": duration
            })

            return {
                "success": True,
                "agent": self.name,
                "task": task,
                "reasoning": reasoning,
                "result": result,
                "duration_ms": duration
            }

        except Exception as e:
            error_msg = str(e)

            # Log error
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                "UPDATE tasks SET status = ?, result = ? WHERE id = ?",
                ("failed", error_msg, task_id)
            )
            c.execute(
                "INSERT INTO alerts VALUES (NULL, ?, ?, ?, ?, 0)",
                (time.time(), "task_failed", "ERROR", f"{self.name}: {error_msg}")
            )
            conn.commit()
            conn.close()

            self.status = "error"

            # Auto-recovery: try alternative approach
            recovery_result = self._auto_recover(task, error_msg, kwargs)

            return {
                "success": False,
                "agent": self.name,
                "task": task,
                "error": error_msg,
                "recovery_attempted": True,
                "recovery_result": recovery_result
            }

    def _execute_impl(self, task: str, **kwargs) -> Any:
        """Implementation to override in subclasses"""
        raise NotImplementedError

    def _auto_recover(self, task: str, error: str, kwargs: Dict) -> Dict:
        """Auto-recovery from failure"""
        recovery_prompt = f"""Task failed: {task}
Error: {error}

What alternative approach can be tried?
Provide a concrete solution (max 50 words)."""

        response = self._query_server(recovery_prompt, max_tokens=100)

        if response.get("success"):
            return {
                "success": True,
                "suggestion": response["answer"]
            }
        else:
            return {
                "success": False,
                "error": "Recovery failed - all servers offline"
            }

    def _query_server(self, prompt: str, max_tokens: int = 500) -> Dict:
        """Query MCP server"""
        try:
            if self.server_preference == "auto":
                endpoint = f"{MCP_SERVER}/query/auto"
            else:
                endpoint = f"{MCP_SERVER}/query"

            response = requests.post(endpoint, json={
                "prompt": prompt,
                "max_tokens": max_tokens,
                "server": self.server_preference if self.server_preference != "auto" else "M1"
            }, timeout=120)

            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

# ============================================
# SPECIALIZED AGENTS
# ============================================

class TradingAgent(Agent):
    """Agent spécialisé trading analysis"""

    def __init__(self):
        super().__init__("TradeAnalyzer", "Trading Signal Analysis", "M1")

    def _execute_impl(self, symbol: str, **kwargs) -> Dict:
        """Analyze trading symbol"""

        # Get MEXC data
        try:
            response = requests.get(f"{MCP_SERVER}/mexc/scan", params={"min_score": 70})
            scan_data = response.json()

            if not scan_data.get("success"):
                return {"error": "MEXC scan failed"}

            # Find symbol
            signals = scan_data.get("signals", [])
            symbol_data = next((s for s in signals if s["symbol"] == symbol), None)

            if not symbol_data:
                return {"error": f"Symbol {symbol} not found in scan"}

            # Analyze with LM Studio
            analysis_prompt = f"""Analyze {symbol}:
Price: {symbol_data['price']}
Change: {symbol_data['change']}%
Volume: {symbol_data['volume']}
Position: {symbol_data['position']}%
Score: {symbol_data['score']}

Recommendation: LONG, SHORT, or HOLD?
Entry, TP1, TP2, SL levels?
Max 100 words."""

            response = self._query_server(analysis_prompt, max_tokens=200)

            if response.get("success"):
                return {
                    "symbol": symbol,
                    "data": symbol_data,
                    "analysis": response["answer"],
                    "server_used": response.get("server")
                }
            else:
                return {"error": "Analysis query failed"}

        except Exception as e:
            return {"error": str(e)}


class CodeAgent(Agent):
    """Agent spécialisé génération code"""

    def __init__(self):
        super().__init__("CodeMaster", "Code Generation", "M2")

    def _execute_impl(self, task: str, language: str = "python", **kwargs) -> Dict:
        """Generate code"""

        prompt = f"""Generate {language} code for: {task}

Requirements:
- Clean, efficient code
- Comments in French
- Error handling

Provide only the code, no explanation."""

        response = self._query_server(prompt, max_tokens=1000)

        if response.get("success"):
            code = response["answer"]

            # Save to file if requested
            if kwargs.get("save_file"):
                filename = kwargs.get("filename", "generated_code.py")
                filepath = AGENTS_DIR / filename
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(code)

                return {
                    "code": code,
                    "saved_to": str(filepath),
                    "server_used": response.get("server")
                }
            else:
                return {
                    "code": code,
                    "server_used": response.get("server")
                }
        else:
            return {"error": "Code generation failed"}


class ResearchAgent(Agent):
    """Agent spécialisé recherche et analyse"""

    def __init__(self):
        super().__init__("Researcher", "Research & Analysis", "auto")

    def _execute_impl(self, query: str, **kwargs) -> Dict:
        """Research query"""

        max_tokens = kwargs.get("max_tokens", 500)

        response = self._query_server(query, max_tokens=max_tokens)

        if response.get("success"):
            return {
                "query": query,
                "answer": response["answer"],
                "server_used": response.get("server"),
                "tokens": response.get("tokens")
            }
        else:
            return {"error": "Research query failed"}


class ConsensusAgent(Agent):
    """Agent consensus multi-serveur"""

    def __init__(self):
        super().__init__("ConsensusBuilder", "Multi-Server Consensus", "ALL")

    def _execute_impl(self, question: str, **kwargs) -> Dict:
        """Get consensus from multiple servers"""

        try:
            response = requests.post(f"{MCP_SERVER}/consensus", json={
                "question": question,
                "servers": kwargs.get("servers", ["M1", "M2", "M3"])
            }, timeout=180)

            return response.json()

        except Exception as e:
            return {"error": str(e)}

# ============================================
# ORCHESTRATOR
# ============================================

class AgentOrchestrator:
    """Orchestrateur autonome d'agents avec gestion pannes"""

    def __init__(self):
        self.agents = {
            "trading": TradingAgent(),
            "code": CodeAgent(),
            "research": ResearchAgent(),
            "consensus": ConsensusAgent()
        }
        self.execution_log = []

    def dispatch(self, agent_type: str, **kwargs) -> Dict:
        """Dispatch task to agent avec auto-recovery"""

        if agent_type not in self.agents:
            return {"success": False, "error": f"Unknown agent: {agent_type}"}

        agent = self.agents[agent_type]

        print(f"\n[ORCHESTRATOR] Dispatching to {agent.name}")
        print(f"  Role: {agent.role}")
        print(f"  Status: {agent.status}")

        start = time.time()
        result = agent.execute(**kwargs)
        duration = int((time.time() - start) * 1000)

        # Log execution
        self.execution_log.append({
            "agent": agent.name,
            "agent_type": agent_type,
            "duration_ms": duration,
            "success": result.get("success", False),
            "timestamp": time.time()
        })

        return result

    def parallel_dispatch(self, tasks: List[Dict]) -> List[Dict]:
        """Dispatch multiple tasks (simulated parallel)"""

        results = []
        for task in tasks:
            agent_type = task.get("agent")
            params = {k: v for k, v in task.items() if k != "agent"}
            result = self.dispatch(agent_type, **params)
            results.append({
                "agent": agent_type,
                "result": result
            })

        return results

    def auto_divide_task(self, complex_task: str) -> List[Dict]:
        """Automatically divide complex task into sub-tasks"""

        # Use research agent to analyze task
        research = self.agents["research"]

        division_prompt = f"""Analyze this complex task and divide it into 3-5 sub-tasks:

Task: {complex_task}

Provide sub-tasks as JSON list:
[
  {{"agent": "research", "task": "..."}},
  {{"agent": "code", "task": "..."}},
  ...
]"""

        response = research._query_server(division_prompt, max_tokens=300)

        if response.get("success"):
            answer = response["answer"]

            # Try to extract JSON
            try:
                import re
                json_match = re.search(r'\[.*\]', answer, re.DOTALL)
                if json_match:
                    subtasks = json.loads(json_match.group())
                    return subtasks
            except:
                pass

        # Fallback: manual division
        return [
            {"agent": "research", "task": f"Research: {complex_task}"},
            {"agent": "code", "task": f"Implement: {complex_task}"}
        ]

    def get_stats(self) -> Dict:
        """Get orchestration statistics"""

        total_tasks = len(self.execution_log)
        if total_tasks == 0:
            return {"total_tasks": 0}

        success_count = sum(1 for log in self.execution_log if log["success"])
        avg_duration = sum(log["duration_ms"] for log in self.execution_log) / total_tasks

        agent_usage = {}
        for log in self.execution_log:
            agent = log["agent"]
            agent_usage[agent] = agent_usage.get(agent, 0) + 1

        return {
            "total_tasks": total_tasks,
            "success_count": success_count,
            "success_rate": f"{success_count/total_tasks*100:.1f}%",
            "avg_duration_ms": int(avg_duration),
            "agent_usage": agent_usage
        }

# ============================================
# CLI INTERFACE
# ============================================

def main():
    """CLI pour orchestrateur d'agents"""
    import sys

    if len(sys.argv) < 2:
        print("""Usage:
  python agent_orchestrator.py trading <symbol>
  python agent_orchestrator.py code <task>
  python agent_orchestrator.py research <query>
  python agent_orchestrator.py consensus <question>
  python agent_orchestrator.py auto-divide "<complex_task>"
  python agent_orchestrator.py stats
        """)
        return

    orchestrator = AgentOrchestrator()
    command = sys.argv[1]

    if command == "trading" and len(sys.argv) > 2:
        symbol = sys.argv[2]
        result = orchestrator.dispatch("trading", symbol=symbol)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif command == "code" and len(sys.argv) > 2:
        task = " ".join(sys.argv[2:])
        result = orchestrator.dispatch("code", task=task, language="python")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif command == "research" and len(sys.argv) > 2:
        query = " ".join(sys.argv[2:])
        result = orchestrator.dispatch("research", query=query)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif command == "consensus" and len(sys.argv) > 2:
        question = " ".join(sys.argv[2:])
        result = orchestrator.dispatch("consensus", question=question)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif command == "auto-divide" and len(sys.argv) > 2:
        complex_task = " ".join(sys.argv[2:])
        subtasks = orchestrator.auto_divide_task(complex_task)
        print("\nSub-tasks:")
        print(json.dumps(subtasks, indent=2, ensure_ascii=False))

        # Execute subtasks
        print("\nExecuting subtasks...")
        results = orchestrator.parallel_dispatch(subtasks)
        print(json.dumps(results, indent=2, ensure_ascii=False))

    elif command == "stats":
        stats = orchestrator.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    else:
        print("Unknown command")

if __name__ == "__main__":
    main()
