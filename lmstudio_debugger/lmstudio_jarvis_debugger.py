#!/usr/bin/env python3
"""
JARVIS M1 - LM STUDIO AUTO-DEBUGGER
Agent autonome qui scanne, analyse, corrige et améliore TOUS les fichiers JARVIS M1
Mode : Loop ∞ d'amélioration continue

Auteur: LM Studio Agent (M2 LMT2)
Date: 2025
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configuration
PROJECT_ROOT = Path("/home/turbo/jarvis-m1-ops")
DEBUGGER_DIR = PROJECT_ROOT / "lmstudio_debugger"
LOGS_DIR = PROJECT_ROOT / "logs"
PATCHES_DIR = DEBUGGER_DIR / "patches"
METRICS_FILE = DEBUGGER_DIR / "metrics.json"

# LM Studio M2 Configuration (à ajuster selon votre setup)
LM_STUDIO_CONFIG = {
    "base_url": "http://127.0.0.1:1234",  # Adjust based on your setup
    "model": "qwen2.5-32b-instruct",
    "max_tokens": 8192,
    "temperature": 0.3,
}

# MCP Flask Server Configuration
MCP_CONFIG = {
    "host": "localhost",
    "port": 18789,
    "endpoint": "/mcp",
    "api_key": "1202"
}


class LMStudioDebugger:
    """Agent autonome d'auto-debugging pour JARVIS M1"""

    def __init__(self):
        self.loop_count = 0
        self.files_scanned = 0
        self.issues_found = 0
        self.fixes_applied = 0
        self.metrics_before: Dict[str, Any] = {}
        self.metrics_after: Dict[str, Any] = {}

    async def initialize(self) -> bool:
        """Initialisation du debugger"""
        print("🚀 INITIALISATION DU LM STUDIO JARVIS AUTO-DEBUGGER")
        print("=" * 60)

        # Create directories
        for dir_path in [LOGS_DIR, PATCHES_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Initialize metrics file
        if not METRICS_FILE.exists():
            with open(METRICS_FILE, 'w') as f:
                json.dump({
                    "start_time": datetime.now().isoformat(),
                    "loops": [],
                    "summary": {"total_scanned": 0, "total_fixes": 0}
                }, f, indent=2)

        # Log startup
        self._log_message("DEBUGGER", "Initialized successfully")
        print(f"✅ Project root: {PROJECT_ROOT}")
        print(f"✅ Logs dir: {LOGS_DIR}")
        print(f"✅ Patches dir: {PATCHES_DIR}")
        return True

    def _log_message(self, level: str, message: str):
        """Logger centralisé"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)

        # Write to log file
        log_file = LOGS_DIR / "debugger.log"
        with open(log_file, 'a') as f:
            f.write(log_entry + "\n")

    async def scan_files(self) -> List[Path]:
        """PHASE 1 - Scan tous les fichiers JARVIS M1"""
        print("\n📂 PHASE 1 : SCAN DES FICHIERS JARVIS M1")
        print("-" * 60)

        excluded_dirs = {'.venv', 'node_modules', '__pycache__', '.git', '.pytest_cache'}
        scanned_files: List[Path] = []

        # Walk directory tree, excluding virtual envs
        for root, dirs, files in os.walk(PROJECT_ROOT):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if d not in excluded_dirs]

            for file in files:
                filepath = Path(root) / file

                # Focus on relevant file types
                if file.endswith(('.py', '.sh', '.md', '.json', '.yaml', '.yml')):
                    scanned_files.append(filepath)
                    self.files_scanned += 1

        print(f"✅ Scanné {len(scanned_files)} fichiers (excluant .venv, node_modules)")
        return scanned_files

    def scan_for_issues(self, file_path: Path) -> List[Dict[str, Any]]:
        """Scan un fichier pour les problèmes connus"""
        issues = []

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')

            # Check for various issue patterns
            issue_patterns = [
                (r'FIXME', 'TODO marker found'),
                (r'TODO', 'TODO marker found'),
                (r'HACK', 'HACK comment found'),
                (r'Bug|BUG', 'Bug mentioned in code/comments'),
                (r'ERROR|error', 'Error string detected'),
                (r'raise\s+Exception', 'Generic exception raised'),
                (r'except\s+Exception\b', 'Generic exception caught'),
                (r'def\s+\w+\s*\([^)]*self[^)]*\):', 'Potential self parameter issue'),
                (r'import\s+(os|sys)\s*$', 'Direct import of os/sys (check usage)'),
            ]

            for line_num, line in enumerate(lines, 1):
                for pattern, description in issue_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        issues.append({
                            "file": str(file_path.relative_to(PROJECT_ROOT)),
                            "line": line_num,
                            "type": "code_issue",
                            "description": description,
                            "severity": "warning"
                        })

            # Check for common Python issues
            if file_path.suffix == '.py':
                # Missing type hints (Python 3.5+)
                if not re.search(r'->\s*\w+', content):
                    issues.append({
                        "file": str(file_path.relative_to(PROJECT_ROOT)),
                        "line": 0,
                        "type": "missing_type_hints",
                        "description": "No type hints found in file",
                        "severity": "info"
                    })

                # Check for bare except clauses
                if re.search(r'except\s*:', content):
                    issues.append({
                        "file": str(file_path.relative_to(PROJECT_ROOT)),
                        "line": 0,
                        "type": "bare_except",
                        "description": "Bare 'except:' clause found (should catch specific exception)",
                        "severity": "error"
                    })

        except Exception as e:
            issues.append({
                "file": str(file_path.relative_to(PROJECT_ROOT)),
                "line": 0,
                "type": "read_error",
                "description": f"Failed to read file: {e}",
                "severity": "error"
            })

        return issues

    async def analyze_issues(self, all_files: List[Path]) -> Dict[str, Any]:
        """PHASE 2 - Analyse des problèmes"""
        print("\n🔍 PHASE 2 : ANALYSE DES PROBLÈMES")
        print("-" * 60)

        all_issues = []

        for file_path in all_files:
            issues = self.scan_for_issues(file_path)
            all_issues.extend(issues)

        # Group by severity
        critical = [i for i in all_issues if i['severity'] == 'error']
        warnings = [i for i in all_issues if i['severity'] == 'warning']
        info = [i for i in all_issues if i['severity'] == 'info']

        print(f"📊 Résultats de l'analyse:")
        print(f"   - Problèmes critiques: {len(critical)}")
        print(f"   - Avertissements: {len(warnings)}")
        print(f"   - Informations: {len(info)}")
        print(f"   - Total: {len(all_issues)}")

        self.issues_found = len(all_issues)

        return {
            "total": len(all_issues),
            "critical": critical,
            "warnings": warnings,
            "info": info,
            "by_file": self._group_by_file(all_issues)
        }

    def _group_by_file(self, issues: List[Dict]) -> Dict[str, int]:
        """Grouper les problèmes par fichier"""
        grouped = {}
        for issue in issues:
            file_path = issue['file']
            if file_path not in grouped:
                grouped[file_path] = 0
            grouped[file_path] += 1
        return grouped

    async def generate_fixes(self, analysis_results: Dict[str, Any]) -> List[Dict]:
        """PHASE 3 - Génération des correctifs"""
        print("\n🔧 PHASE 3 : GÉNÉRATION DES CORRECTIFS")
        print("-" * 60)

        fixes = []

        # Auto-fix specific issues we can detect
        for issue in analysis_results.get('critical', []) + analysis_results.get('warnings', []):
            if issue['type'] == 'bare_except':
                fixes.append({
                    "issue_id": len(fixes),
                    "file": issue['file'],
                    "action": "replace_bare_except",
                    "description": "Replace bare 'except:' with 'except Exception as e:'",
                    "status": "pending"
                })

        # Count fixes to generate
        print(f"✅ {len(fixes)} correctifs générés automatiquement")
        return fixes

    async def apply_fixes(self, fixes: List[Dict]) -> int:
        """PHASE 4 - Application des correctifs"""
        print("\n📝 PHASE 4 : APPLICATION DES CORRECTIFS")
        print("-" * 60)

        applied = 0

        for fix in fixes:
            if fix['status'] != 'pending':
                continue

            file_path = PROJECT_ROOT / fix['file']
            try:
                # Create backup first
                backup_path = Path(f"{file_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                file_path.copy(backup_path)

                content = file_path.read_text()

                # Apply specific fixes
                if fix['action'] == 'replace_bare_except':
                    # Replace bare except with proper exception handling
                    new_content = re.sub(
                        r'except\s*:',
                        'except Exception as e:\n        # TODO: Handle specific exception',
                        content,
                        flags=re.MULTILINE
                    )

                    if new_content != content:
                        file_path.write_text(new_content)
                        print(f"✅ Fixé: {fix['file']} (bare except → exception handling)")
                        applied += 1

                # Save fix details to patches directory
                patch_file = PATCHES_DIR / f"{fix['action']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(patch_file, 'w') as f:
                    json.dump({
                        "file": fix['file'],
                        "action": fix['action'],
                        "backup": str(backup_path),
                        "timestamp": datetime.now().isoformat()
                    }, f, indent=2)

            except Exception as e:
                print(f"❌ Échec du fix sur {fix['file']}: {e}")

        self.fixes_applied = applied
        return applied

    async def test_changes(self) -> Dict[str, Any]:
        """PHASE 5 - Tests automatiques"""
        print("\n🧪 PHASE 5 : TESTS AUTOMATIQUES")
        print("-" * 60)

        results = {
            "pytest": {"passed": 0, "failed": 0},
            "linting": {"passed": 0, "failed": 0}
        }

        # Run pytest if available
        try:
            result = subprocess.run(
                ['python', '-m', 'pytest', str(PROJECT_ROOT / 'tests'), '-v'],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=60
            )

            # Parse pytest output
            if result.returncode == 0:
                results['pytest']['passed'] = 1
            else:
                results['pytest']['failed'] = 1

        except subprocess.TimeoutExpired:
            print("⏱️  Pytest timeout (60s)")
            results['pytest']['failed'] = 1
        except FileNotFoundError:
            print("📦 pytest non installé, skipping")

        # Basic syntax check on Python files
        for py_file in PROJECT_ROOT.glob('**/*.py'):
            if '.venv' in str(py_file):
                continue

            try:
                compile(py_file.read_text(), str(py_file), 'exec')
                results['linting']['passed'] += 1
            except SyntaxError as e:
                print(f"❌ Syntax error in {py_file}: {e}")
                results['linting']['failed'] += 1

        total_tests = results['pytest']['passed'] + results['pytest']['failed'] + \
                      results['linting']['passed'] + results['linting']['failed']

        if total_tests > 0:
            success_rate = ((results['pytest']['passed'] + results['linting']['passed']) / total_tests) * 100
            print(f"✅ Taux de réussite: {success_rate:.1f}%")

        return results

    async def update_metrics(self, analysis: Dict, fixes_applied: int, tests: Dict):
        """Mettre à jour les métriques"""
        self.loop_count += 1

        metrics = {
            "loop": self.loop_count,
            "timestamp": datetime.now().isoformat(),
            "files_scanned": self.files_scanned,
            "issues_found": self.issues_found,
            "fixes_applied": fixes_applied,
            "test_results": tests
        }

        # Load existing metrics and append new loop
        if METRICS_FILE.exists():
            with open(METRICS_FILE, 'r') as f:
                data = json.load(f)
        else:
            data = {"start_time": datetime.now().isoformat(), "loops": [], "summary": {}}

        data['loops'].append(metrics)
        data['summary']['total_scanned'] += self.files_scanned
        data['summary']['total_fixes'] += fixes_applied

        with open(METRICS_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    def display_report(self):
        """Afficher le rapport final"""
        print("\n" + "=" * 60)
        print("📊 RAPPORT FINAL DU LM STUDIO JARVIS AUTO-DEBUGGER")
        print("=" * 60)

        print(f"\n🔄 Boucles exécutées: {self.loop_count}")
        print(f"📂 Fichiers scannés: {self.files_scanned}")
        print(f"🔍 Problèmes trouvés: {self.issues_found}")
        print(f"✅ Correctifs appliqués: {self.fixes_applied}")

        # Show critical issues fixed
        if self.fixes_applied > 0:
            print(f"\n⚠️  {self.fixes_applied} problèmes critiques corrigés")

        print("\n📁 Fichiers générés:")
        print(f"   - Rapports: {LOGS_DIR}")
        print(f"   - Patches: {PATCHES_DIR}")
        print(f"   - Métriques: {METRICS_FILE}")

    async def run_loop(self, iterations: int = 1):
        """Exécuter la boucle principale"""
        await self.initialize()

        for i in range(iterations):
            print(f"\n{'='*60}")
            print(f"🔄 BOUCLE #{i+1}/{iterations}")
            print('=' * 60)

            # Phase 1: Scan files
            all_files = await self.scan_files()

            # Phase 2: Analyze issues
            analysis = await self.analyze_issues(all_files)

            # Phase 3: Generate fixes
            fixes = await self.generate_fixes(analysis)

            # Phase 4: Apply fixes
            applied = await self.apply_fixes(fixes)

            # Phase 5: Test changes
            tests = await self.test_changes()

            # Update metrics
            await self.update_metrics(analysis, applied, tests)

            # Sleep between loops (if multiple iterations)
            if i < iterations - 1:
                print(f"\n⏳ Pause avant la prochaine boucle...")
                time.sleep(2)

        # Final report
        self.display_report()


async def main():
    """Point d'entrée principal"""
    debugger = LMStudioDebugger()

    try:
        # Run 1 iteration by default, can be extended to ∞ loop
        await debugger.run_loop(iterations=1)

        print("\n✅ AUTO-DEBUGGER TERMINÉ AVEC SUCCÈS")
        return 0

    except KeyboardInterrupt:
        print("\n⚠️  Arrêt par l'utilisateur")
        return 0
    except Exception as e:
        print(f"\n❌ ERREUR CRITIQUE: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
