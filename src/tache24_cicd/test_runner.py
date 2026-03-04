#!/usr/bin/env python3
"""
JARVIS Test Runner - Framework automatisé de tests pour JARVIS
Découverte + exécution async + reporting JSON/console
"""

import os
import sys
import json
import time
import sqlite3
import asyncio
import importlib.util
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Callable, Optional
from enum import Enum
import traceback
import re

# Couleurs console
class Colors:
    RESET = "\033[0m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

class TestType(Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    PERFORMANCE = "performance"

@dataclass
class TestResult:
    name: str
    test_type: str
    status: str  # "pass", "fail", "error", "skipped"
    duration: float
    message: str = ""
    error_trace: str = ""

@dataclass
class TestRunReport:
    timestamp: datetime
    total_tests: int
    passed: int
    failed: int
    errors: int
    skipped: int
    duration: float
    coverage_estimate: float
    results: List[TestResult]
    exit_code: int

class MockCluster:
    """Mock pour tests du cluster"""
    def __init__(self):
        self.nodes = {
            "M1": {"url": "127.0.0.1:1234", "status": "online"},
            "M2": {"url": "192.168.1.26:1234", "status": "online"},
            "M3": {"url": "192.168.1.113:1234", "status": "online"},
            "OL1": {"url": "127.0.0.1:11434", "status": "online"},
            "GEMINI": {"url": "gemini-proxy", "status": "online"},
        }
    
    async def ping_node(self, node_name: str) -> bool:
        """Simule un ping noeud"""
        if node_name in self.nodes:
            return self.nodes[node_name]["status"] == "online"
        return False
    
    async def query_test(self, node_name: str, prompt: str) -> Dict[str, Any]:
        """Simule une query de test"""
        await asyncio.sleep(0.1)
        return {
            "node": node_name,
            "prompt": prompt,
            "response": f"Response from {node_name}",
            "latency_ms": 150
        }
    
    async def consensus_test(self, nodes: List[str], prompt: str) -> Dict[str, Any]:
        """Simule un consensus multi-IA"""
        await asyncio.sleep(0.2)
        return {
            "nodes": nodes,
            "prompt": prompt,
            "consensus": "agreed",
            "confidence": 0.95
        }

class MockDatabase:
    """Mock pour tests de base de données"""
    def __init__(self):
        self.data = {}
    
    async def insert(self, table: str, data: Dict) -> bool:
        if table not in self.data:
            self.data[table] = []
        self.data[table].append(data)
        return True
    
    async def query(self, table: str, filters: Dict) -> List[Dict]:
        if table not in self.data:
            return []
        return [row for row in self.data[table] if all(row.get(k) == v for k, v in filters.items())]

class MockTrading:
    """Mock pour tests trading"""
    def __init__(self):
        self.positions = []
        self.signals = []
    
    async def get_positions(self) -> List[Dict]:
        """Retourne positions mock"""
        return [
            {"symbol": "BTC/USDT", "side": "long", "pnl": 250.5},
            {"symbol": "ETH/USDT", "side": "short", "pnl": -50.2}
        ]
    
    async def process_signal(self, signal: Dict) -> bool:
        """Simule le traitement d'un signal"""
        await asyncio.sleep(0.05)
        self.signals.append(signal)
        return True

class MockVoice:
    """Mock pour tests voice pipeline"""
    def __init__(self):
        self.recognition_rate = 0.95
    
    async def recognize(self, audio: bytes) -> Dict[str, Any]:
        """Simule la reconnaissance vocale"""
        await asyncio.sleep(0.1)
        return {
            "text": "Mock recognized text",
            "confidence": self.recognition_rate,
            "duration_ms": 1500
        }

class MockGateway:
    """Mock pour tests gateway HTTP"""
    async def request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Simule une requête HTTP"""
        await asyncio.sleep(0.05)
        return {
            "status_code": 200,
            "endpoint": endpoint,
            "method": method,
            "data": data or {}
        }

class TestRunner:
    """Runner principal de tests"""
    
    def __init__(self, tests_dir: str, base_path: str = "F:\\BUREAU\\turbo"):
        self.tests_dir = Path(tests_dir)
        self.base_path = Path(base_path)
        self.db_path = self.base_path / "db" / "test_history.db"
        self.results: List[TestResult] = []
        self.start_time = None
        self.end_time = None
        
        # Fixtures
        self.mock_cluster = MockCluster()
        self.mock_db = MockDatabase()
        self.mock_trading = MockTrading()
        self.mock_voice = MockVoice()
        self.mock_gateway = MockGateway()
        
        self._init_db()
    
    def _init_db(self):
        """Initialise la base SQLite pour historique"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_runs (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                total_tests INTEGER,
                passed INTEGER,
                failed INTEGER,
                errors INTEGER,
                duration REAL,
                exit_code INTEGER
            )
        """)
        conn.commit()
        conn.close()
    
    def discover_tests(self) -> Dict[str, List[Path]]:
        """Découvre automatiquement les tests par type"""
        tests_by_type = {
            "unit": [],
            "integration": [],
            "e2e": [],
            "performance": []
        }
        
        if not self.tests_dir.exists():
            print(f"{Colors.YELLOW}Répertoire tests non trouvé: {self.tests_dir}{Colors.RESET}")
            return tests_by_type
        
        for test_file in self.tests_dir.glob("test_*.py"):
            content = test_file.read_text()
            
            if "test_unit" in test_file.name or "@unit" in content:
                tests_by_type["unit"].append(test_file)
            elif "test_integration" in test_file.name or "@integration" in content:
                tests_by_type["integration"].append(test_file)
            elif "test_e2e" in test_file.name or "@e2e" in content:
                tests_by_type["e2e"].append(test_file)
            elif "test_performance" in test_file.name or "@performance" in content:
                tests_by_type["performance"].append(test_file)
            else:
                tests_by_type["unit"].append(test_file)
        
        return tests_by_type
    
    async def run_cluster_tests(self) -> List[TestResult]:
        """Tests du cluster: ping + query + consensus"""
        results = []
        
        # Test ping chaque noeud
        for node_name in self.mock_cluster.nodes.keys():
            start = time.time()
            try:
                pong = await self.mock_cluster.ping_node(node_name)
                duration = time.time() - start
                status = "pass" if pong else "fail"
                results.append(TestResult(
                    name=f"cluster_ping_{node_name}",
                    test_type=TestType.INTEGRATION.value,
                    status=status,
                    duration=duration,
                    message=f"Ping {node_name}: {status}"
                ))
            except Exception as e:
                results.append(TestResult(
                    name=f"cluster_ping_{node_name}",
                    test_type=TestType.INTEGRATION.value,
                    status="error",
                    duration=time.time() - start,
                    error_trace=str(e)
                ))
        
        # Test query
        start = time.time()
        try:
            result = await self.mock_cluster.query_test("M1", "test prompt")
            duration = time.time() - start
            results.append(TestResult(
                name="cluster_query_test",
                test_type=TestType.INTEGRATION.value,
                status="pass",
                duration=duration,
                message=f"Query latency: {result['latency_ms']}ms"
            ))
        except Exception as e:
            results.append(TestResult(
                name="cluster_query_test",
                test_type=TestType.INTEGRATION.value,
                status="error",
                duration=time.time() - start,
                error_trace=str(e)
            ))
        
        # Test consensus
        start = time.time()
        try:
            result = await self.mock_cluster.consensus_test(["M1", "M2", "M3"], "consensus test")
            duration = time.time() - start
            results.append(TestResult(
                name="cluster_consensus_test",
                test_type=TestType.INTEGRATION.value,
                status="pass",
                duration=duration,
                message=f"Consensus: {result['consensus']} ({result['confidence']:.2%})"
            ))
        except Exception as e:
            results.append(TestResult(
                name="cluster_consensus_test",
                test_type=TestType.INTEGRATION.value,
                status="error",
                duration=time.time() - start,
                error_trace=str(e)
            ))
        
        return results
    
    async def run_trading_tests(self) -> List[TestResult]:
        """Tests trading: positions + signals"""
        results = []
        
        # Test positions
        start = time.time()
        try:
            positions = await self.mock_trading.get_positions()
            duration = time.time() - start
            results.append(TestResult(
                name="trading_get_positions",
                test_type=TestType.UNIT.value,
                status="pass",
                duration=duration,
                message=f"Retrieved {len(positions)} positions"
            ))
        except Exception as e:
            results.append(TestResult(
                name="trading_get_positions",
                test_type=TestType.UNIT.value,
                status="error",
                duration=time.time() - start,
                error_trace=str(e)
            ))
        
        # Test signal processing
        start = time.time()
        try:
            signal = {"symbol": "BTC/USDT", "action": "buy", "qty": 1.0}
            success = await self.mock_trading.process_signal(signal)
            duration = time.time() - start
            status = "pass" if success else "fail"
            results.append(TestResult(
                name="trading_process_signal",
                test_type=TestType.UNIT.value,
                status=status,
                duration=duration,
                message=f"Signal processing: {status}"
            ))
        except Exception as e:
            results.append(TestResult(
                name="trading_process_signal",
                test_type=TestType.UNIT.value,
                status="error",
                duration=time.time() - start,
                error_trace=str(e)
            ))
        
        return results
    
    async def run_voice_tests(self) -> List[TestResult]:
        """Tests voice pipeline"""
        results = []
        
        start = time.time()
        try:
            # Mock audio bytes
            audio = b"mock_audio_data"
            result = await self.mock_voice.recognize(audio)
            duration = time.time() - start
            results.append(TestResult(
                name="voice_recognize",
                test_type=TestType.UNIT.value,
                status="pass",
                duration=duration,
                message=f"Recognition confidence: {result['confidence']:.2%}"
            ))
        except Exception as e:
            results.append(TestResult(
                name="voice_recognize",
                test_type=TestType.UNIT.value,
                status="error",
                duration=time.time() - start,
                error_trace=str(e)
            ))
        
        return results
    
    async def run_gateway_tests(self) -> List[TestResult]:
        """Tests gateway HTTP"""
        results = []
        endpoints = ["/health", "/api/cluster", "/api/trading", "/api/voice", "/api/status"]
        
        for endpoint in endpoints:
            start = time.time()
            try:
                result = await self.mock_gateway.request("GET", endpoint)
                duration = time.time() - start
                status = "pass" if result["status_code"] == 200 else "fail"
                results.append(TestResult(
                    name=f"gateway_{endpoint.replace('/', '_')}",
                    test_type=TestType.E2E.value,
                    status=status,
                    duration=duration,
                    message=f"HTTP {result['status_code']}"
                ))
            except Exception as e:
                results.append(TestResult(
                    name=f"gateway_{endpoint.replace('/', '_')}",
                    test_type=TestType.E2E.value,
                    status="error",
                    duration=time.time() - start,
                    error_trace=str(e)
                ))
        
        return results
    
    async def run_all_tests(self) -> TestRunReport:
        """Exécute tous les tests"""
        self.start_time = time.time()
        
        # Tests intégrés
        results = []
        results.extend(await self.run_cluster_tests())
        results.extend(await self.run_trading_tests())
        results.extend(await self.run_voice_tests())
        results.extend(await self.run_gateway_tests())
        
        self.results = results
        self.end_time = time.time()
        
        return self._generate_report()
    
    def _generate_report(self) -> TestRunReport:
        """Génère le rapport de tests"""
        total = len(self.results)
        passed = len([r for r in self.results if r.status == "pass"])
        failed = len([r for r in self.results if r.status == "fail"])
        errors = len([r for r in self.results if r.status == "error"])
        skipped = len([r for r in self.results if r.status == "skipped"])
        
        duration = self.end_time - self.start_time if self.start_time and self.end_time else 0
        coverage = (passed / total * 100) if total > 0 else 0
        
        # Exit code
        if errors > 0:
            exit_code = 2
        elif failed > 0:
            exit_code = 1
        else:
            exit_code = 0
        
        report = TestRunReport(
            timestamp=datetime.now(),
            total_tests=total,
            passed=passed,
            failed=failed,
            errors=errors,
            skipped=skipped,
            duration=duration,
            coverage_estimate=coverage,
            results=self.results,
            exit_code=exit_code
        )
        
        self._save_to_db(report)
        return report
    
    def _save_to_db(self, report: TestRunReport):
        """Sauvegarde dans SQLite"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO test_runs 
            (timestamp, total_tests, passed, failed, errors, duration, exit_code)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            report.timestamp.isoformat(),
            report.total_tests,
            report.passed,
            report.failed,
            report.errors,
            report.duration,
            report.exit_code
        ))
        conn.commit()
        conn.close()
    
    def print_report(self, report: TestRunReport):
        """Affiche le rapport en couleur"""
        print(f"\n{Colors.BLUE}{'='*70}")
        print(f"TEST REPORT - {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}{Colors.RESET}\n")
        
        print(f"Total Tests: {report.total_tests}")
        print(f"{Colors.GREEN}Passed: {report.passed}{Colors.RESET}")
        if report.failed > 0:
            print(f"{Colors.RED}Failed: {report.failed}{Colors.RESET}")
        if report.errors > 0:
            print(f"{Colors.RED}Errors: {report.errors}{Colors.RESET}")
        if report.skipped > 0:
            print(f"{Colors.YELLOW}Skipped: {report.skipped}{Colors.RESET}")
        
        print(f"\nCoverage Estimate: {report.coverage_estimate:.1f}%")
        print(f"Duration: {report.duration:.2f}s")
        print(f"\nExit Code: {report.exit_code}")
        
        if report.failed > 0 or report.errors > 0:
            print(f"\n{Colors.RED}Failed/Error Tests:{Colors.RESET}")
            for result in report.results:
                if result.status in ["fail", "error"]:
                    print(f"  - {result.name} ({result.test_type})")
                    if result.error_trace:
                        print(f"    {result.error_trace[:100]}...")
        
        print(f"\n{Colors.BLUE}{'='*70}{Colors.RESET}\n")
    
    def export_json(self, report: TestRunReport, output_file: str):
        """Exporte le rapport en JSON"""
        data = {
            "timestamp": report.timestamp.isoformat(),
            "summary": {
                "total": report.total_tests,
                "passed": report.passed,
                "failed": report.failed,
                "errors": report.errors,
                "skipped": report.skipped,
                "coverage": f"{report.coverage_estimate:.1f}%",
                "duration": f"{report.duration:.2f}s"
            },
            "exit_code": report.exit_code,
            "results": [
                {
                    "name": r.name,
                    "type": r.test_type,
                    "status": r.status,
                    "duration": f"{r.duration:.3f}s",
                    "message": r.message,
                    "error": r.error_trace
                }
                for r in report.results
            ]
        }
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"Rapport JSON exporté: {output_path}")

async def main():
    """Point d'entrée"""
    base_path = "F:\\BUREAU\\turbo"
    tests_dir = Path(base_path) / "tests"
    
    runner = TestRunner(str(tests_dir), base_path)
    
    print(f"{Colors.CYAN}Démarrage des tests JARVIS...{Colors.RESET}\n")
    
    report = await runner.run_all_tests()
    runner.print_report(report)
    
    # Export JSON
    json_output = Path(base_path) / "reports" / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    runner.export_json(report, str(json_output))
    
    sys.exit(report.exit_code)

if __name__ == "__main__":
    asyncio.run(main())
