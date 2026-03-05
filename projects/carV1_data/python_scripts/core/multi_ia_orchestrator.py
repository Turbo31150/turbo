#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MULTI-IA ORCHESTRATOR - Distribution des tâches aux modèles IA
Utilise: Qwen3-30B, GPT-OSS-20B, Gemini CLI
Serveur local: http://192.168.1.85:1234
"""
import os
import sys
import json
import subprocess
import requests
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
import threading

# Configuration serveur LM Studio
LM_STUDIO_URL = "http://192.168.1.85:1234/v1/chat/completions"

# Modèles disponibles
MODELS = {
    "qwen": "qwen/qwen3-30b-a3b-2507",
    "qwen_coder": "qwen/qwen3-coder-30b",
    "gpt_oss": "openai/gpt-oss-20b",
    "gemini": "gemini"  # CLI externe
}

@dataclass
class IATask:
    """Tâche pour un modèle IA"""
    task_id: str
    model: str
    prompt: str
    system_prompt: str = ""
    max_tokens: int = 1000
    priority: int = 1

@dataclass
class IAResponse:
    """Réponse d'un modèle IA"""
    task_id: str
    model: str
    content: str
    reasoning: str = ""
    success: bool = True
    error: str = ""
    latency_ms: float = 0.0

class MultiIAOrchestrator:
    """Orchestrateur multi-IA avec distribution parallèle"""

    def __init__(self, lm_studio_url: str = LM_STUDIO_URL):
        self.lm_studio_url = lm_studio_url
        self.results: Dict[str, IAResponse] = {}
        self.lock = threading.Lock()

    def check_server(self) -> bool:
        """Vérifie la disponibilité du serveur LM Studio"""
        try:
            response = requests.get(f"{self.lm_studio_url.rsplit('/', 2)[0]}/v1/models", timeout=5)
            return response.status_code == 200
        except:
            return False

    def query_lm_studio(self, model: str, prompt: str, system_prompt: str = "", max_tokens: int = 1000) -> Dict:
        """Requête vers LM Studio (Qwen ou GPT-OSS)"""
        start_time = datetime.now()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = requests.post(
                self.lm_studio_url,
                headers={"Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.7
                },
                timeout=120
            )

            latency = (datetime.now() - start_time).total_seconds() * 1000

            if response.status_code == 200:
                data = response.json()
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                return {
                    "success": True,
                    "content": message.get("content", ""),
                    "reasoning": message.get("reasoning", message.get("reasoning_content", "")),
                    "latency_ms": latency
                }
            else:
                return {"success": False, "error": f"HTTP {response.status_code}", "latency_ms": latency}

        except Exception as e:
            latency = (datetime.now() - start_time).total_seconds() * 1000
            return {"success": False, "error": str(e), "latency_ms": latency}

    def query_gemini(self, prompt: str) -> Dict:
        """Requête vers Gemini CLI"""
        start_time = datetime.now()

        try:
            # Escape quotes for PowerShell - simplified
            safe_prompt = prompt.replace('"', "'").replace('\n', ' ')

            # Use echo to pipe the prompt to gemini
            cmd = f'echo "{safe_prompt}" | gemini'

            result = subprocess.run(
                ["powershell", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=30,
                encoding='utf-8',
                errors='replace'
            )

            latency = (datetime.now() - start_time).total_seconds() * 1000

            # Filter out common noise from output
            content = result.stdout.strip()
            for noise in ["Loaded cached credentials", "[Multi-IA]", "Workspace:"]:
                if noise in content:
                    lines = [l for l in content.split('\n') if noise not in l]
                    content = '\n'.join(lines).strip()

            if content:
                return {"success": True, "content": content, "latency_ms": latency}
            elif result.stderr and "error" not in result.stderr.lower():
                return {"success": True, "content": result.stderr.strip(), "latency_ms": latency}
            else:
                return {"success": False, "error": result.stderr or "Empty response", "latency_ms": latency}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout 30s", "latency_ms": 30000}
        except Exception as e:
            return {"success": False, "error": str(e), "latency_ms": 0}

    def execute_task(self, task: IATask) -> IAResponse:
        """Exécute une tâche sur le modèle spécifié"""
        print(f"[{task.task_id}] Exécution sur {task.model}...")

        if task.model == "gemini":
            result = self.query_gemini(task.prompt)
        else:
            model_id = MODELS.get(task.model, task.model)
            result = self.query_lm_studio(model_id, task.prompt, task.system_prompt, task.max_tokens)

        response = IAResponse(
            task_id=task.task_id,
            model=task.model,
            content=result.get("content", ""),
            reasoning=result.get("reasoning", ""),
            success=result.get("success", False),
            error=result.get("error", ""),
            latency_ms=result.get("latency_ms", 0)
        )

        with self.lock:
            self.results[task.task_id] = response

        status = "[OK]" if response.success else "[ERR]"
        print(f"[{task.task_id}] {status} Termine en {response.latency_ms:.0f}ms")

        return response

    def distribute_tasks(self, tasks: List[IATask], max_parallel: int = 3) -> Dict[str, IAResponse]:
        """Distribue et exécute les tâches en parallèle"""
        print(f"\n{'='*60}")
        print(f"DISTRIBUTION MULTI-IA - {len(tasks)} tâches")
        print(f"{'='*60}\n")

        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = {executor.submit(self.execute_task, task): task for task in tasks}

            for future in as_completed(futures):
                task = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"[{task.task_id}] Erreur: {e}")

        return self.results

    def aggregate_signals(self, responses: Dict[str, IAResponse]) -> Dict:
        """Agrège les réponses des IAs pour décision finale"""
        signals = {"LONG": 0, "SHORT": 0, "NEUTRAL": 0}
        confidences = []
        analyses = []

        for task_id, response in responses.items():
            if response.success:
                content = response.content.upper()

                # Détection du signal
                if "LONG" in content or "ACHAT" in content or "BUY" in content:
                    signals["LONG"] += 1
                    confidences.append(0.8)
                elif "SHORT" in content or "VENTE" in content or "SELL" in content:
                    signals["SHORT"] += 1
                    confidences.append(0.8)
                else:
                    signals["NEUTRAL"] += 1
                    confidences.append(0.5)

                analyses.append({
                    "model": response.model,
                    "task_id": task_id,
                    "preview": response.content[:200] + "..." if len(response.content) > 200 else response.content
                })

        # Décision finale par majorité pondérée
        total = sum(signals.values())
        if total == 0:
            final_signal = "NEUTRAL"
            final_confidence = 0.0
        else:
            final_signal = max(signals, key=signals.get)
            final_confidence = signals[final_signal] / total * (sum(confidences) / len(confidences) if confidences else 0.5)

        return {
            "final_signal": final_signal,
            "confidence": round(final_confidence, 2),
            "votes": signals,
            "analyses": analyses,
            "timestamp": datetime.now().isoformat()
        }


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS DE DISTRIBUTION SPÉCIALISÉES
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_market_multi_ia(symbol: str, timeframe: str, market_data: Dict) -> Dict:
    """
    Analyse de marché distribuée sur les 3 IAs
    - Qwen: Analyse technique
    - GPT-OSS: Code et optimisation
    - Gemini: Recherche et tendances
    """
    orchestrator = MultiIAOrchestrator()

    # Préparer contexte
    price_summary = f"Prix actuel: {market_data.get('close', 0):.2f}, " \
                   f"High: {market_data.get('high', 0):.2f}, " \
                   f"Low: {market_data.get('low', 0):.2f}"

    tasks = [
        IATask(
            task_id="T1_QWEN_TECHNICAL",
            model="qwen",
            system_prompt="Tu es un expert en analyse technique. Réponds de façon concise avec LONG, SHORT ou NEUTRAL.",
            prompt=f"Analyse {symbol} sur {timeframe}. {price_summary}. Donne ton signal et justification courte.",
            max_tokens=500
        ),
        IATask(
            task_id="T2_GPT_STRATEGY",
            model="gpt_oss",
            system_prompt="Tu es un expert en trading algorithmique.",
            prompt=f"Pour {symbol} ({timeframe}), {price_summary}. Quelle stratégie recommandes-tu? Signal: LONG/SHORT/NEUTRAL?",
            max_tokens=500
        ),
        IATask(
            task_id="T3_GEMINI_SENTIMENT",
            model="gemini",
            prompt=f"Signal trading pour {symbol} timeframe {timeframe}? Réponds LONG, SHORT ou NEUTRAL avec raison courte."
        )
    ]

    results = orchestrator.distribute_tasks(tasks, max_parallel=3)
    aggregated = orchestrator.aggregate_signals(results)

    return aggregated


def optimize_strategy_multi_ia(strategy_name: str, parameters: Dict) -> Dict:
    """
    Optimisation de stratégie par consensus multi-IA
    """
    orchestrator = MultiIAOrchestrator()

    param_str = json.dumps(parameters, indent=2)

    tasks = [
        IATask(
            task_id="OPT1_QWEN",
            model="qwen",
            system_prompt="Tu es un expert en optimisation de stratégies de trading.",
            prompt=f"Optimise les paramètres de la stratégie '{strategy_name}':\n{param_str}\nPropose des améliorations.",
            max_tokens=800
        ),
        IATask(
            task_id="OPT2_GPT",
            model="gpt_oss",
            system_prompt="Tu es un expert en backtesting et optimisation.",
            prompt=f"Stratégie: {strategy_name}\nParamètres: {param_str}\nSuggère des optimisations avec rationale.",
            max_tokens=800
        )
    ]

    results = orchestrator.distribute_tasks(tasks, max_parallel=2)

    optimizations = []
    for task_id, response in results.items():
        if response.success:
            optimizations.append({
                "model": response.model,
                "suggestions": response.content
            })

    return {
        "strategy": strategy_name,
        "original_params": parameters,
        "optimizations": optimizations,
        "timestamp": datetime.now().isoformat()
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN - DÉMONSTRATION
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("MULTI-IA ORCHESTRATOR - GPU Trading System")
    print("=" * 70)

    orchestrator = MultiIAOrchestrator()

    # Vérifier serveur
    print("\n[1] Vérification du serveur LM Studio...")
    if orchestrator.check_server():
        print("✅ Serveur LM Studio accessible")
    else:
        print("⚠️ Serveur LM Studio non accessible")

    # Test distribution
    print("\n[2] Test de distribution multi-IA...")

    test_tasks = [
        IATask(
            task_id="TEST_QWEN",
            model="qwen",
            system_prompt="Tu es un assistant trading.",
            prompt="Donne un signal pour BTC/USDT en 1 mot: LONG, SHORT ou NEUTRAL"
        ),
        IATask(
            task_id="TEST_GPT",
            model="gpt_oss",
            system_prompt="Tu es un assistant trading.",
            prompt="Signal pour ETH/USDT? Réponds: LONG, SHORT ou NEUTRAL"
        ),
        IATask(
            task_id="TEST_GEMINI",
            model="gemini",
            prompt="Signal trading crypto aujourd'hui? LONG SHORT ou NEUTRAL?"
        )
    ]

    results = orchestrator.distribute_tasks(test_tasks, max_parallel=3)

    print("\n[3] Résultats:")
    print("-" * 50)
    for task_id, response in results.items():
        status = "✅" if response.success else "❌"
        print(f"{status} {task_id} ({response.model}):")
        if response.success:
            print(f"   {response.content[:150]}...")
        else:
            print(f"   Erreur: {response.error}")
        print(f"   Latence: {response.latency_ms:.0f}ms")
        print()

    # Agrégation
    print("\n[4] Agrégation des signaux:")
    print("-" * 50)
    aggregated = orchestrator.aggregate_signals(results)
    print(f"Signal final: {aggregated['final_signal']}")
    print(f"Confiance: {aggregated['confidence']*100:.0f}%")
    print(f"Votes: {aggregated['votes']}")
