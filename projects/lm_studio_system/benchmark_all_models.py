#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Benchmark All LM Studio Models
Teste les 17 modèles disponibles sur les 3 serveurs
Métriques: tokens/sec, VRAM, qualité, répétitions
"""

import requests
import time
import json
from datetime import datetime
from typing import Dict, List

# Configuration
LM_STUDIO_SERVERS = [
    {
        "id": "server1",
        "url": "http://192.168.1.85:1234",
        "name": "LM Studio 1 - Deep Analysis",
        "gpus": 6
    },
    {
        "id": "server2",
        "url": "http://192.168.1.26:1234",
        "name": "LM Studio 2 - Fast Inference",
        "gpus": 3
    },
    {
        "id": "server3",
        "url": "http://192.168.1.113:1234",
        "name": "LM Studio 3 - Reasoning",
        "gpus": 2
    }
]

# Modèles à tester (17 modèles)
MODELS_TO_TEST = [
    "qwen/qwen3-30b-a3b-2507",
    "qwen/qwen3-coder-30b",
    "nvidia/nemotron-3-nano",
    "mistralai/devstral-small-2-2512",
    "mistralai/ministral-3-14b-reasoning",
    "zai-org/glm-4.6v-flash",
    "zai-org/glm-4.7-flash",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "google/gemma-3-12b",
    "deepseek/deepseek-r1-0528-qwen3-8b",
    "qwen/qwen3-vl-8b",
    "essentialai/rnj-1",
    "liquid/lfm2.5-1.2b",
    "llama-3.2-1b-instruct",
    "qwen2.5-0.5b-instruct",
    "text-embedding-nomic-embed-text-v1.5"
]

# Prompts de test
TEST_PROMPTS = [
    "Analyse technique BTC: tendance court terme?",
    "Code Python: fonction calcul Fibonacci",
    "Conseil trading ETHUSDT",
    "Résumé: avantages IA dans trading"
]


def get_available_models(server_url: str) -> List[str]:
    """Récupérer modèles disponibles sur serveur"""
    try:
        response = requests.get(f"{server_url}/v1/models", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return [m['id'] for m in data.get('data', [])]
        return []
    except Exception as e:
        print(f"  ❌ Erreur connexion: {e}")
        return []


def benchmark_model(server_url: str, model: str, prompt: str) -> Dict:
    """Benchmark un modèle"""
    try:
        url = f"{server_url}/v1/chat/completions"

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
            "temperature": 0.8,
            "repeat_penalty": 1.3,
            "top_p": 0.85,
            "top_k": 30,
            "presence_penalty": 0.7,
            "frequency_penalty": 0.9,
            "stream": False
        }

        start_time = time.time()
        response = requests.post(url, json=payload, timeout=60)
        elapsed_time = time.time() - start_time

        if response.status_code == 200:
            data = response.json()

            content = data['choices'][0]['message']['content']
            tokens = data.get('usage', {}).get('completion_tokens', 0)

            # Calculer tokens/sec
            tokens_per_sec = tokens / elapsed_time if elapsed_time > 0 else 0

            # Détecter répétitions
            words = content.split()
            unique_words = set(words)
            unique_ratio = len(unique_words) / len(words) if len(words) > 0 else 0

            # Qualité (simple heuristique)
            quality_score = min(100, int(unique_ratio * 100 + tokens_per_sec * 2))

            return {
                "success": True,
                "response": content[:200],
                "tokens": tokens,
                "elapsed_time": round(elapsed_time, 2),
                "tokens_per_sec": round(tokens_per_sec, 2),
                "unique_ratio": round(unique_ratio, 3),
                "quality_score": quality_score,
                "has_repetition": unique_ratio < 0.5
            }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Timeout (60s)"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def run_benchmark():
    """Exécuter benchmark complet"""
    print("\n" + "="*70)
    print(" BENCHMARK ALL LM STUDIO MODELS")
    print("="*70 + "\n")

    results = {
        "timestamp": datetime.now().isoformat(),
        "servers": [],
        "models_tested": 0,
        "models_success": 0,
        "summary": {}
    }

    for server in LM_STUDIO_SERVERS:
        print(f"\n{'='*70}")
        print(f" {server['name']}")
        print(f" {server['url']}")
        print(f"{'='*70}\n")

        # Récupérer modèles disponibles
        available_models = get_available_models(server['url'])

        if not available_models:
            print(f"  ❌ Serveur OFFLINE ou aucun modèle\n")
            continue

        print(f"  ✅ {len(available_models)} modèles disponibles\n")

        server_results = {
            "server_id": server['id'],
            "server_name": server['name'],
            "url": server['url'],
            "gpus": server['gpus'],
            "models_available": len(available_models),
            "models": []
        }

        # Tester chaque modèle
        for model in MODELS_TO_TEST:
            if model not in available_models:
                continue

            print(f"  [TEST] {model}")

            model_results = {
                "model": model,
                "tests": []
            }

            # Tester avec 2 prompts
            for i, prompt in enumerate(TEST_PROMPTS[:2], 1):
                print(f"    Prompt {i}/2... ", end='', flush=True)

                result = benchmark_model(server['url'], model, prompt)

                if result['success']:
                    print(f"✅ {result['tokens_per_sec']} t/s")
                    model_results['tests'].append(result)
                    results['models_success'] += 1
                else:
                    print(f"❌ {result.get('error', 'Erreur')}")

                results['models_tested'] += 1

            # Calculer moyennes
            if model_results['tests']:
                avg_tps = sum(t['tokens_per_sec'] for t in model_results['tests']) / len(model_results['tests'])
                avg_quality = sum(t['quality_score'] for t in model_results['tests']) / len(model_results['tests'])

                model_results['avg_tokens_per_sec'] = round(avg_tps, 2)
                model_results['avg_quality_score'] = round(avg_quality, 1)
                model_results['has_repetition'] = any(t['has_repetition'] for t in model_results['tests'])

                print(f"    → Moyenne: {model_results['avg_tokens_per_sec']} t/s, qualité: {model_results['avg_quality_score']}/100\n")

                # Ajouter au summary
                if model not in results['summary']:
                    results['summary'][model] = []
                results['summary'][model].append({
                    "server": server['id'],
                    "tokens_per_sec": model_results['avg_tokens_per_sec'],
                    "quality": model_results['avg_quality_score']
                })

            server_results['models'].append(model_results)

        results['servers'].append(server_results)

    # Sauvegarder résultats
    output_file = f"F:/BUREAU/lm_studio_system/benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Afficher résumé
    print("\n" + "="*70)
    print(" RÉSUMÉ BENCHMARK")
    print("="*70 + "\n")

    print(f"  Modèles testés: {results['models_tested']}")
    print(f"  Succès: {results['models_success']}")
    print(f"  Taux succès: {results['models_success']/results['models_tested']*100:.1f}%\n")

    print("  TOP 5 MODÈLES (tokens/sec):\n")

    # Calculer top modèles
    model_avg = {}
    for model, servers in results['summary'].items():
        avg_tps = sum(s['tokens_per_sec'] for s in servers) / len(servers)
        model_avg[model] = avg_tps

    top5 = sorted(model_avg.items(), key=lambda x: x[1], reverse=True)[:5]

    for i, (model, tps) in enumerate(top5, 1):
        print(f"    {i}. {model.split('/')[-1]:30s} {tps:6.1f} t/s")

    print(f"\n  📁 Résultats sauvegardés: {output_file}\n")

    print("="*70 + "\n")


if __name__ == "__main__":
    run_benchmark()
