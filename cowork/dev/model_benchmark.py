#!/usr/bin/env python3
"""
JARVIS Cluster Benchmark Script
Benchmarks all AI cluster nodes (M1, M2, M3, OL1) with latency and token measurements.
Stores results in SQLite and outputs JSON summary.

Usage:
    python model_benchmark.py --run              # Run full benchmark
    python model_benchmark.py --quick            # Fast benchmark (1 prompt per node)
    python model_benchmark.py --history          # Show past benchmarks
    python model_benchmark.py --compare          # Compare latest scores
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.request
import urllib.error
import os
from datetime import datetime
from pathlib import Path


class ClusterBenchmark:
    """Benchmark suite for JARVIS cluster nodes."""

    # Node configurations
    NODES = {
        "M1": {
            "host": "127.0.0.1",
            "port": 1234,
            "type": "lm_studio",
            "model": "qwen3-8b",
            "description": "CHAMPION LOCAL — qwen3-8b (98.4/100)"
        },
        "M2": {
            "host": "192.168.1.26",
            "port": 1234,
            "type": "lm_studio",
            "model": "deepseek-r1-0528-qwen3-8b",
            "description": "Code specialist — deepseek-coder-v2 (85.1/100)"
        },
        "M3": {
            "host": "192.168.1.113",
            "port": 1234,
            "type": "lm_studio",
            "model": "deepseek-r1-0528-qwen3-8b",
            "description": "Reasoning fallback — deepseek-r1 (M3)"
        },
        "OL1": {
            "host": "127.0.0.1",
            "port": 11434,
            "type": "ollama",
            "model": "qwen3:1.7b",
            "description": "Fast polyvalent — qwen3:1.7b (88%)"
        }
    }

    # Test prompts
    PROMPTS = [
        {"name": "math_simple", "text": "What is 2+2?"},
        {"name": "code", "text": "Write a Python function to check if a number is prime"},
        {"name": "knowledge", "text": "Explain the difference between TCP and UDP in 3 sentences"}
    ]

    def __init__(self, db_path: str = None):
        """Initialize benchmark suite."""
        if db_path is None:
            db_path = "dev/data/benchmark.db"

        self.db_path = db_path
        self._ensure_db_dir()
        self._init_db()

    def _ensure_db_dir(self):
        """Create database directory if it doesn't exist."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def _init_db(self):
        """Initialize SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS benchmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    node_name TEXT NOT NULL,
                    node_host TEXT NOT NULL,
                    node_port INTEGER NOT NULL,
                    model TEXT NOT NULL,
                    prompt_name TEXT NOT NULL,
                    prompt_text TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    tokens_approx INTEGER NOT NULL,
                    success INTEGER NOT NULL,
                    error_message TEXT,
                    response_length INTEGER NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    node_name TEXT NOT NULL,
                    avg_latency_ms REAL NOT NULL,
                    total_requests INTEGER NOT NULL,
                    success_count INTEGER NOT NULL,
                    success_rate REAL NOT NULL,
                    avg_tokens_per_sec REAL NOT NULL
                )
            """)
            conn.commit()

    def _lm_studio_request(self, node_name: str, node_config: dict, prompt: str) -> tuple:
        """Send request to LM Studio endpoint."""
        url = f"http://{node_config['host']}:{node_config['port']}/api/v1/chat"

        payload = {
            "model": node_config["model"],
            "input": f"/nothink\n{prompt}",
            "temperature": 0.2,
            "max_output_tokens": 512,
            "stream": False,
            "store": False
        }

        try:
            start_time = time.time()
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
                latency_ms = (time.time() - start_time) * 1000

                # Extract response content
                response_text = ""
                if "output" in data and isinstance(data["output"], list):
                    for item in data["output"]:
                        if item.get("type") == "message":
                            response_text = item.get("content", "")

                tokens_approx = len(response_text) // 4
                return (True, latency_ms, tokens_approx, response_text, None)

        except urllib.error.URLError as e:
            return (False, 0, 0, "", f"Connection failed: {str(e)}")
        except json.JSONDecodeError as e:
            return (False, 0, 0, "", f"Invalid JSON response: {str(e)}")
        except Exception as e:
            return (False, 0, 0, "", f"Error: {str(e)}")

    def _ollama_request(self, node_name: str, node_config: dict, prompt: str) -> tuple:
        """Send request to Ollama endpoint."""
        url = f"http://{node_config['host']}:{node_config['port']}/api/chat"

        payload = {
            "model": node_config["model"],
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }

        try:
            start_time = time.time()
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
                latency_ms = (time.time() - start_time) * 1000

                response_text = data.get("message", {}).get("content", "")
                tokens_approx = len(response_text) // 4
                return (True, latency_ms, tokens_approx, response_text, None)

        except urllib.error.URLError as e:
            return (False, 0, 0, "", f"Connection failed: {str(e)}")
        except json.JSONDecodeError as e:
            return (False, 0, 0, "", f"Invalid JSON response: {str(e)}")
        except Exception as e:
            return (False, 0, 0, "", f"Error: {str(e)}")

    def benchmark_node(self, node_name: str, prompts: list = None) -> dict:
        """Benchmark a single node."""
        if prompts is None:
            prompts = self.PROMPTS

        if node_name not in self.NODES:
            return {"error": f"Unknown node: {node_name}"}

        node_config = self.NODES[node_name]
        results = {
            "node": node_name,
            "model": node_config["model"],
            "description": node_config["description"],
            "timestamp": datetime.now().isoformat(),
            "tests": []
        }

        print(f"  Benchmarking {node_name} ({node_config['host']}:{node_config['port']})...", end=" ", flush=True)

        for prompt_config in prompts:
            prompt_name = prompt_config["name"]
            prompt_text = prompt_config["text"]

            # Send request based on node type
            if node_config["type"] == "lm_studio":
                success, latency_ms, tokens, response_text, error = self._lm_studio_request(
                    node_name, node_config, prompt_text
                )
            else:  # ollama
                success, latency_ms, tokens, response_text, error = self._ollama_request(
                    node_name, node_config, prompt_text
                )

            test_result = {
                "prompt": prompt_name,
                "success": success,
                "latency_ms": round(latency_ms, 2),
                "tokens_approx": tokens,
                "response_length": len(response_text),
                "error": error
            }
            results["tests"].append(test_result)

            # Store in database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO benchmarks
                    (timestamp, node_name, node_host, node_port, model, prompt_name, prompt_text,
                     latency_ms, tokens_approx, success, error_message, response_length)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    results["timestamp"],
                    node_name,
                    node_config["host"],
                    node_config["port"],
                    node_config["model"],
                    prompt_name,
                    prompt_text,
                    latency_ms,
                    tokens,
                    1 if success else 0,
                    error,
                    len(response_text)
                ))
                conn.commit()

        # Calculate summary stats
        successful = [t for t in results["tests"] if t["success"]]
        if successful:
            avg_latency = sum(t["latency_ms"] for t in successful) / len(successful)
            avg_tokens_per_sec = sum(
                (t["tokens_approx"] / (t["latency_ms"] / 1000)) if t["latency_ms"] > 0 else 0
                for t in successful
            ) / len(successful)
            success_rate = len(successful) / len(results["tests"])

            results["summary"] = {
                "avg_latency_ms": round(avg_latency, 2),
                "success_rate": round(success_rate, 2),
                "avg_tokens_per_sec": round(avg_tokens_per_sec, 2)
            }

            # Store summary in database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO summary
                    (timestamp, node_name, avg_latency_ms, total_requests, success_count, success_rate, avg_tokens_per_sec)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    results["timestamp"],
                    node_name,
                    results["summary"]["avg_latency_ms"],
                    len(results["tests"]),
                    len(successful),
                    results["summary"]["success_rate"],
                    results["summary"]["avg_tokens_per_sec"]
                ))
                conn.commit()
        else:
            results["summary"] = {
                "avg_latency_ms": 0,
                "success_rate": 0,
                "avg_tokens_per_sec": 0
            }

        print("OK")
        return results

    def run_full_benchmark(self) -> dict:
        """Run benchmark on all nodes with all prompts."""
        print("\n=== FULL CLUSTER BENCHMARK ===")
        print(f"Nodes: {', '.join(self.NODES.keys())}")
        print(f"Prompts per node: {len(self.PROMPTS)}")
        print(f"Total tests: {len(self.NODES) * len(self.PROMPTS)}\n")

        all_results = {
            "timestamp": datetime.now().isoformat(),
            "benchmark_type": "full",
            "nodes_tested": list(self.NODES.keys()),
            "results": []
        }

        for node_name in self.NODES.keys():
            result = self.benchmark_node(node_name, self.PROMPTS)
            all_results["results"].append(result)

        return all_results

    def run_quick_benchmark(self) -> dict:
        """Run quick benchmark (1 prompt per node)."""
        print("\n=== QUICK CLUSTER BENCHMARK ===")
        print(f"Nodes: {', '.join(self.NODES.keys())}")
        print(f"Prompts per node: 1\n")

        all_results = {
            "timestamp": datetime.now().isoformat(),
            "benchmark_type": "quick",
            "nodes_tested": list(self.NODES.keys()),
            "results": []
        }

        for node_name in self.NODES.keys():
            result = self.benchmark_node(node_name, [self.PROMPTS[0]])
            all_results["results"].append(result)

        return all_results

    def show_history(self, limit: int = 10) -> dict:
        """Show past benchmarks from database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get summary history
            summaries = conn.execute("""
                SELECT DISTINCT timestamp, node_name, avg_latency_ms, success_rate,
                       avg_tokens_per_sec, success_count, total_requests
                FROM summary
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,)).fetchall()

            history = {
                "timestamp": datetime.now().isoformat(),
                "total_records": len(summaries),
                "recent_benchmarks": [dict(row) for row in summaries]
            }

        return history

    def compare_latest(self) -> dict:
        """Compare latest benchmark scores across all nodes."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get latest timestamp
            latest = conn.execute("""
                SELECT DISTINCT timestamp FROM summary ORDER BY timestamp DESC LIMIT 1
            """).fetchone()

            if not latest:
                return {"error": "No benchmark history found"}

            latest_timestamp = latest[0]

            # Get latest results for all nodes
            results = conn.execute("""
                SELECT node_name, avg_latency_ms, success_rate, avg_tokens_per_sec,
                       success_count, total_requests
                FROM summary
                WHERE timestamp = ?
                ORDER BY avg_latency_ms ASC
            """, (latest_timestamp,)).fetchall()

            comparison = {
                "timestamp": datetime.now().isoformat(),
                "benchmark_timestamp": latest_timestamp,
                "nodes_compared": [dict(row) for row in results],
                "rankings": {
                    "latency": sorted([dict(r) for r in results], key=lambda x: x["avg_latency_ms"]),
                    "throughput": sorted([dict(r) for r in results], key=lambda x: x["avg_tokens_per_sec"], reverse=True),
                    "reliability": sorted([dict(r) for r in results], key=lambda x: x["success_rate"], reverse=True)
                }
            }

        return comparison


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="JARVIS Cluster Benchmark — Test all AI nodes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python model_benchmark.py --run              Run full benchmark
  python model_benchmark.py --quick            Fast benchmark (1 prompt per node)
  python model_benchmark.py --history          Show past benchmarks
  python model_benchmark.py --compare          Compare latest scores
        """
    )

    parser.add_argument("--run", action="store_true", help="Run full benchmark on all nodes")
    parser.add_argument("--quick", action="store_true", help="Quick benchmark (1 prompt per node)")
    parser.add_argument("--history", action="store_true", help="Show past benchmark history")
    parser.add_argument("--compare", action="store_true", help="Compare latest benchmark scores")
    parser.add_argument("--db", default="dev/data/benchmark.db", help="Database path (default: dev/data/benchmark.db)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Create benchmark instance
    benchmark = ClusterBenchmark(db_path=args.db)

    # Execute requested action
    result = None

    if args.run:
        result = benchmark.run_full_benchmark()
    elif args.quick:
        result = benchmark.run_quick_benchmark()
    elif args.history:
        result = benchmark.show_history()
    elif args.compare:
        result = benchmark.compare_latest()
    else:
        parser.print_help()
        return 0

    # Output result
    if result:
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
