#!/usr/bin/env python3
"""
JARVIS CI/CD Pipeline - Pipeline local avec stages: lint → test → build → deploy → verify
Gestion rollback, git integration, Telegram webhooks, scheduling
"""

import os
import sys
import json
import time
import sqlite3
import asyncio
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
import fcntl

# Couleurs console
class Colors:
    RESET = "\033[0m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"

class StageStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"

@dataclass
class StageResult:
    name: str
    status: StageStatus
    duration: float
    output: str
    error: str = ""

@dataclass
class PipelineRun:
    run_id: str
    timestamp: datetime
    triggered_by: str  # "manual", "cron", "git_hook"
    hotfix: bool
    stages: List[StageResult]
    total_duration: float
    success: bool

class GitManager:
    """Gestion Git"""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
    
    def is_repo(self) -> bool:
        """Vérifie si c'est un repo git"""
        return (self.repo_path / ".git").exists()
    
    def commit_reports(self, message: str) -> bool:
        """Commit automatique des rapports"""
        try:
            os.chdir(str(self.repo_path))
            
            # Add rapports
            subprocess.run(
                ["git", "add", "reports/"],
                capture_output=True,
                timeout=10
            )
            
            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return result.returncode == 0
        except Exception as e:
            print(f"Erreur git commit: {e}")
            return False
    
    def get_branch(self) -> str:
        """Récupère la branche actuelle"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip()
        except:
            return "unknown"

class TelegramNotifier:
    """Notifications Telegram"""
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.bot_token and self.chat_id)
    
    async def send_message(self, message: str) -> bool:
        """Envoie un message Telegram"""
        if not self.enabled:
            return True
        
        try:
            import aiohttp
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {"chat_id": self.chat_id, "text": message}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, timeout=10) as resp:
                    return resp.status == 200
        except Exception as e:
            print(f"Erreur Telegram: {e}")
            return False
    
    async def notify_pipeline(self, run: PipelineRun):
        """Notifie les résultats du pipeline"""
        status_emoji = "✅" if run.success else "❌"
        message = f"""
{status_emoji} JARVIS CI/CD Pipeline
Branch: {run.triggered_by}
Durée: {run.total_duration:.2f}s
Stages: {len([s for s in run.stages if s.status == StageStatus.SUCCESS])}/{len(run.stages)}
"""
        await self.send_message(message)

class LockManager:
    """Gestion des locks pour éviter les runs parallèles"""
    
    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self.lock_file = None
    
    def acquire(self, timeout: int = 30) -> bool:
        """Acquiert le lock"""
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        
        start = time.time()
        while time.time() - start < timeout:
            try:
                self.lock_file = open(str(self.lock_path), "w")
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.lock_file.write(f"{os.getpid()}")
                return True
            except (IOError, OSError):
                time.sleep(1)
        
        return False
    
    def release(self):
        """Libère le lock"""
        if self.lock_file:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            self.lock_file.close()
            self.lock_path.unlink(missing_ok=True)

class CIPipeline:
    """Pipeline CI/CD principal"""
    
    def __init__(self, base_path: str = "F:\\BUREAU\\turbo"):
        self.base_path = Path(base_path)
        self.src_path = self.base_path / "src"
        self.prod_path = self.base_path / "prod"
        self.db_path = self.base_path / "db" / "pipeline_history.db"
        self.lock_path = self.base_path / "tmp" / "pipeline.lock"
        self.reports_path = self.base_path / "reports"
        
        self.git_manager = GitManager(self.base_path)
        self.telegram = TelegramNotifier()
        self.lock_manager = LockManager(self.lock_path)
        
        self.stages: List[StageResult] = []
        self.start_time = None
        self.hotfix = False
        
        self._init_db()
    
    def _init_db(self):
        """Initialise la base SQLite"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                triggered_by TEXT,
                hotfix INTEGER,
                stages_count INTEGER,
                success INTEGER,
                duration REAL
            )
        """)
        conn.commit()
        conn.close()
    
    async def run_pipeline(self, hotfix: bool = False, triggered_by: str = "manual") -> bool:
        """Exécute le pipeline complet"""
        
        # Acquiert le lock
        if not self.lock_manager.acquire():
            print(f"{Colors.RED}Pipeline déjà en cours d'exécution{Colors.RESET}")
            return False
        
        try:
            self.start_time = time.time()
            self.hotfix = hotfix
            
            print(f"{Colors.CYAN}Démarrage du pipeline CI/CD JARVIS{Colors.RESET}")
            print(f"Hotfix: {hotfix}, Déclenché par: {triggered_by}\n")
            
            stages = [
                ("lint", self._run_lint),
                ("test", self._run_test),
                ("build", self._run_build),
                ("deploy", self._run_deploy),
                ("verify", self._run_verify),
            ]
            
            for stage_name, stage_func in stages:
                # Skip lint+test si hotfix
                if self.hotfix and stage_name in ["lint", "test"]:
                    result = StageResult(
                        name=stage_name,
                        status=StageStatus.SKIPPED,
                        duration=0,
                        output="Skipped en mode hotfix"
                    )
                    self.stages.append(result)
                    print(f"{Colors.YELLOW}⊘ {stage_name}: SKIPPED{Colors.RESET}")
                    continue
                
                result = await stage_func()
                self.stages.append(result)
                
                # Affiche le résultat
                if result.status == StageStatus.SUCCESS:
                    print(f"{Colors.GREEN}✓ {stage_name}: SUCCESS ({result.duration:.2f}s){Colors.RESET}")
                elif result.status == StageStatus.FAILURE:
                    print(f"{Colors.RED}✗ {stage_name}: FAILURE{Colors.RESET}")
                    print(f"  {result.error[:100]}")
                    
                    # Rollback si deploy/verify échouent
                    if stage_name in ["deploy", "verify"]:
                        await self._rollback()
                    
                    total_duration = time.time() - self.start_time
                    await self._finalize(success=False, triggered_by=triggered_by)
                    return False
            
            total_duration = time.time() - self.start_time
            await self._finalize(success=True, triggered_by=triggered_by)
            return True
        
        finally:
            self.lock_manager.release()
    
    async def _run_lint(self) -> StageResult:
        """Stage: Lint avec ruff"""
        result = StageResult(
            name="lint",
            status=StageStatus.RUNNING,
            duration=0,
            output=""
        )
        
        start = time.time()
        try:
            # Lint tous les fichiers Python
            cmd = ["ruff", "check", str(self.src_path), "--fix"]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            result.duration = time.time() - start
            if proc.returncode == 0:
                result.status = StageStatus.SUCCESS
                result.output = "Lint successful"
            else:
                result.status = StageStatus.FAILURE
                result.error = proc.stderr or proc.stdout
        
        except subprocess.TimeoutExpired:
            result.status = StageStatus.FAILURE
            result.error = "Lint timeout"
            result.duration = time.time() - start
        except Exception as e:
            result.status = StageStatus.FAILURE
            result.error = str(e)
            result.duration = time.time() - start
        
        return result
    
    async def _run_test(self) -> StageResult:
        """Stage: Tests via test_runner.py"""
        result = StageResult(
            name="test",
            status=StageStatus.RUNNING,
            duration=0,
            output=""
        )
        
        start = time.time()
        try:
            test_runner = self.base_path / "src" / "tache24_cicd" / "test_runner.py"
            
            proc = subprocess.run(
                [sys.executable, str(test_runner)],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            result.duration = time.time() - start
            
            # Parse la sortie pour vérifier le seuil (>90%)
            if "Coverage Estimate: " in proc.stdout:
                import re
                match = re.search(r"Coverage Estimate: ([\d.]+)%", proc.stdout)
                if match:
                    coverage = float(match.group(1))
                    if coverage >= 90:
                        result.status = StageStatus.SUCCESS
                        result.output = f"Tests passed ({coverage:.1f}% coverage)"
                    else:
                        result.status = StageStatus.FAILURE
                        result.error = f"Coverage below threshold: {coverage:.1f}%"
                else:
                    result.status = StageStatus.FAILURE
                    result.error = "Could not parse coverage"
            else:
                if proc.returncode == 0:
                    result.status = StageStatus.SUCCESS
                    result.output = "Tests passed"
                else:
                    result.status = StageStatus.FAILURE
                    result.error = proc.stdout[-200:] if proc.stdout else "Unknown error"
        
        except subprocess.TimeoutExpired:
            result.status = StageStatus.FAILURE
            result.error = "Tests timeout"
            result.duration = time.time() - start
        except Exception as e:
            result.status = StageStatus.FAILURE
            result.error = str(e)
            result.duration = time.time() - start
        
        return result
    
    async def _run_build(self) -> StageResult:
        """Stage: Build - vérification imports + syntax"""
        result = StageResult(
            name="build",
            status=StageStatus.RUNNING,
            duration=0,
            output=""
        )
        
        start = time.time()
        try:
            errors = []
            
            # Vérification syntax de tous les .py
            for py_file in self.src_path.rglob("*.py"):
                try:
                    compile(py_file.read_text(), str(py_file), "exec")
                except SyntaxError as e:
                    errors.append(f"{py_file}: {e}")
            
            result.duration = time.time() - start
            
            if errors:
                result.status = StageStatus.FAILURE
                result.error = "\n".join(errors[:5])
            else:
                result.status = StageStatus.SUCCESS
                result.output = "Build successful - all syntax checks passed"
        
        except Exception as e:
            result.status = StageStatus.FAILURE
            result.error = str(e)
            result.duration = time.time() - start
        
        return result
    
    async def _run_deploy(self) -> StageResult:
        """Stage: Deploy - copie vers prod + restart"""
        result = StageResult(
            name="deploy",
            status=StageStatus.RUNNING,
            duration=0,
            output=""
        )
        
        start = time.time()
        try:
            # Crée backup de prod
            backup_path = self.prod_path.parent / f"prod_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if self.prod_path.exists():
                shutil.copytree(str(self.prod_path), str(backup_path))
            
            # Copie src vers prod
            self.prod_path.mkdir(parents=True, exist_ok=True)
            for item in self.src_path.iterdir():
                if item.is_dir():
                    dst = self.prod_path / item.name
                    if dst.exists():
                        shutil.rmtree(str(dst))
                    shutil.copytree(str(item), str(dst))
                else:
                    shutil.copy2(str(item), str(self.prod_path / item.name))
            
            result.duration = time.time() - start
            result.status = StageStatus.SUCCESS
            result.output = f"Deployed to {self.prod_path}"
        
        except Exception as e:
            result.status = StageStatus.FAILURE
            result.error = str(e)
            result.duration = time.time() - start
        
        return result
    
    async def _run_verify(self) -> StageResult:
        """Stage: Verify - health check post-deploy"""
        result = StageResult(
            name="verify",
            status=StageStatus.RUNNING,
            duration=0,
            output=""
        )
        
        start = time.time()
        try:
            checks = []
            
            # Vérification fichiers essentiels
            essential_files = [
                self.prod_path / "main.py",
                self.prod_path / "tache24_cicd" / "test_runner.py"
            ]
            
            for f in essential_files:
                checks.append(f.exists())
            
            result.duration = time.time() - start
            
            if all(checks):
                result.status = StageStatus.SUCCESS
                result.output = "Health check passed"
            else:
                result.status = StageStatus.FAILURE
                result.error = "Some essential files are missing"
        
        except Exception as e:
            result.status = StageStatus.FAILURE
            result.error = str(e)
            result.duration = time.time() - start
        
        return result
    
    async def _rollback(self):
        """Rollback automatique si verify échoue"""
        print(f"{Colors.YELLOW}Rollback en cours...{Colors.RESET}")
        
        # Trouve le backup le plus récent
        backup_pattern = self.prod_path.parent / "prod_backup_*"
        backups = sorted(self.prod_path.parent.glob("prod_backup_*"), reverse=True)
        
        if backups:
            latest_backup = backups[0]
            try:
                if self.prod_path.exists():
                    shutil.rmtree(str(self.prod_path))
                shutil.copytree(str(latest_backup), str(self.prod_path))
                print(f"{Colors.GREEN}Rollback successful{Colors.RESET}")
            except Exception as e:
                print(f"{Colors.RED}Rollback failed: {e}{Colors.RESET}")
    
    async def _finalize(self, success: bool, triggered_by: str):
        """Finalisation du pipeline"""
        total_duration = time.time() - self.start_time
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Sauvegarde en DB
        self._save_to_db(run_id, triggered_by, success, total_duration)
        
        # Commit git si repo
        if self.git_manager.is_repo():
            status = "success" if success else "failure"
            self.git_manager.commit_reports(
                f"CI/CD Pipeline {status} - {run_id}"
            )
        
        # Notification Telegram
        run = PipelineRun(
            run_id=run_id,
            timestamp=datetime.now(),
            triggered_by=triggered_by,
            hotfix=self.hotfix,
            stages=self.stages,
            total_duration=total_duration,
            success=success
        )
        await self.telegram.notify_pipeline(run)
        
        # Rapport final
        self._print_final_report(run)
        self._export_report(run)
    
    def _save_to_db(self, run_id: str, triggered_by: str, success: bool, duration: float):
        """Sauvegarde dans SQLite"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pipeline_runs
            (id, timestamp, triggered_by, hotfix, stages_count, success, duration)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            datetime.now().isoformat(),
            triggered_by,
            1 if self.hotfix else 0,
            len(self.stages),
            1 if success else 0,
            duration
        ))
        conn.commit()
        conn.close()
    
    def _print_final_report(self, run: PipelineRun):
        """Affiche le rapport final"""
        status_color = Colors.GREEN if run.success else Colors.RED
        status_text = "SUCCESS" if run.success else "FAILURE"
        
        print(f"\n{Colors.BLUE}{'='*70}")
        print(f"PIPELINE FINAL REPORT")
        print(f"{'='*70}{Colors.RESET}\n")
        
        print(f"Status: {status_color}{status_text}{Colors.RESET}")
        print(f"Duration: {run.total_duration:.2f}s")
        print(f"Hotfix: {'Yes' if run.hotfix else 'No'}")
        print(f"Triggered by: {run.triggered_by}")
        print(f"Run ID: {run.run_id}\n")
        
        print("Stages:")
        for stage in run.stages:
            if stage.status == StageStatus.SUCCESS:
                color = Colors.GREEN
                symbol = "✓"
            elif stage.status == StageStatus.FAILURE:
                color = Colors.RED
                symbol = "✗"
            else:
                color = Colors.YELLOW
                symbol = "⊘"
            
            print(f"  {color}{symbol} {stage.name}: {stage.status.value} ({stage.duration:.2f}s){Colors.RESET}")
        
        print(f"\n{Colors.BLUE}{'='*70}{Colors.RESET}\n")
    
    def _export_report(self, run: PipelineRun):
        """Exporte le rapport JSON"""
        self.reports_path.mkdir(parents=True, exist_ok=True)
        
        data = {
            "run_id": run.run_id,
            "timestamp": run.timestamp.isoformat(),
            "triggered_by": run.triggered_by,
            "hotfix": run.hotfix,
            "success": run.success,
            "duration": f"{run.total_duration:.2f}s",
            "stages": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "duration": f"{s.duration:.2f}s",
                    "output": s.output,
                    "error": s.error
                }
                for s in run.stages
            ]
        }
        
        report_file = self.reports_path / f"pipeline_{run.run_id}.json"
        report_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"Rapport exporté: {report_file}")

async def main():
    """Point d'entrée"""
    import argparse
    
    parser = argparse.ArgumentParser(description="JARVIS CI/CD Pipeline")
    parser.add_argument("--hotfix", action="store_true", help="Mode hotfix (skip lint+test)")
    parser.add_argument("--base-path", default="F:\\BUREAU\\turbo", help="Base path")
    parser.add_argument("--triggered-by", default="manual", help="Déclenché par")
    
    args = parser.parse_args()
    
    pipeline = CIPipeline(args.base_path)
    success = await pipeline.run_pipeline(
        hotfix=args.hotfix,
        triggered_by=args.triggered_by
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())
