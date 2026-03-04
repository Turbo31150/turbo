#!/usr/bin/env python3
"""
JARVIS Watchdog Agent - Monitoring autonome 24/7
Supervision cluster GPU + services + alertes Telegram
"""

import asyncio
import sqlite3
import json
import subprocess
import sys
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import deque
import aiohttp
import requests
from dataclasses import dataclass, asdict
from enum import Enum

# ========== CONFIG ==========
BASE_PATH = r"F:\BUREAU\turbo"
DB_PATH = f"{BASE_PATH}\\jarvis.db"
LOG_FILE = f"{BASE_PATH}\\logs\\watchdog.log"

CYCLE_SECONDS = 30  # Probe toutes les 30s
HEARTBEAT_INTERVAL = 300  # Log heartbeat toutes les 5min
MAX_METRICS_POINTS = 1000  # Rolling window

# Seuils alertes
TEMP_WARNING = 75
TEMP_CRITICAL = 85
VRAM_CRITICAL = 90
LATENCY_WARNING_MS = 500

# Restart policy
COOLDOWN_MINUTES = 5
MAX_RESTARTS_PER_HOUR = 3

# Nodes config
NODES = {
    "M1": {
        "name": "M1-qwen3",
        "url": "http://127.0.0.1:1234",
        "endpoint": "/v1/models",
        "service": "LMStudio",
        "type": "lm_studio",
    },
    "M2": {
        "name": "M2-deepseek",
        "url": "http://192.168.1.26:1234",
        "endpoint": "/v1/models",
        "service": "LMStudio",
        "type": "lm_studio",
    },
    "M3": {
        "name": "M3-mistral",
        "url": "http://192.168.1.113:1234",
        "endpoint": "/v1/models",
        "service": "LMStudio",
        "type": "lm_studio",
    },
    "OL1": {
        "name": "OL1-ollama",
        "url": "http://127.0.0.1:11434",
        "endpoint": "/api/tags",
        "service": "Ollama",
        "type": "ollama",
    },
}

# ========== ENUMS ==========
class HealthStatus(Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    OFFLINE = "OFFLINE"

class AlertSeverity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

# ========== DATACLASSES ==========
@dataclass
class NodeMetrics:
    node_id: str
    timestamp: str
    latency_ms: float
    gpu_temp: Optional[float]
    gpu_vram_percent: Optional[float]
    status: str
    models_count: int
    error: Optional[str] = None

@dataclass
class Alert:
    timestamp: str
    node_id: str
    severity: str
    message: str
    category: str  # "temperature", "vram", "latency", "offline", "restart"

# ========== LOGGING ==========
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ========== DATABASE ==========
class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialise les tables"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Métriques
        c.execute("""
            CREATE TABLE IF NOT EXISTS node_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT,
                timestamp TEXT,
                latency_ms REAL,
                gpu_temp REAL,
                gpu_vram_percent REAL,
                status TEXT,
                models_count INTEGER,
                error TEXT
            )
        """)
        
        # Alertes
        c.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                node_id TEXT,
                severity TEXT,
                message TEXT,
                category TEXT,
                telegram_sent INTEGER DEFAULT 0
            )
        """)
        
        # Restarts
        c.execute("""
            CREATE TABLE IF NOT EXISTS restart_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                node_id TEXT,
                service TEXT,
                reason TEXT,
                success INTEGER
            )
        """)
        
        # Heartbeat
        c.execute("""
            CREATE TABLE IF NOT EXISTS heartbeat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                status TEXT,
                nodes_healthy INTEGER,
                nodes_total INTEGER
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Database initialized")

    def insert_metrics(self, metrics: NodeMetrics):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO node_metrics 
            (node_id, timestamp, latency_ms, gpu_temp, gpu_vram_percent, status, models_count, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metrics.node_id, metrics.timestamp, metrics.latency_ms,
            metrics.gpu_temp, metrics.gpu_vram_percent, metrics.status,
            metrics.models_count, metrics.error
        ))
        conn.commit()
        conn.close()

    def insert_alert(self, alert: Alert):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO alerts (timestamp, node_id, severity, message, category)
            VALUES (?, ?, ?, ?, ?)
        """, (alert.timestamp, alert.node_id, alert.severity, alert.message, alert.category))
        conn.commit()
        conn.close()

    def insert_heartbeat(self, nodes_healthy: int, nodes_total: int):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO heartbeat (timestamp, status, nodes_healthy, nodes_total)
            VALUES (?, ?, ?, ?)
        """, (datetime.utcnow().isoformat(), "OK", nodes_healthy, nodes_total))
        conn.commit()
        conn.close()

    def insert_restart(self, node_id: str, service: str, reason: str, success: bool):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO restart_log (timestamp, node_id, service, reason, success)
            VALUES (?, ?, ?, ?, ?)
        """, (datetime.utcnow().isoformat(), node_id, service, reason, int(success)))
        conn.commit()
        conn.close()

    def get_metrics_for_node(self, node_id: str, minutes: int = 60) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
        c.execute("""
            SELECT * FROM node_metrics 
            WHERE node_id = ? AND timestamp > ?
            ORDER BY timestamp DESC LIMIT ?
        """, (node_id, cutoff, MAX_METRICS_POINTS))
        rows = [dict(row) for row in c.fetchall()]
        conn.close()
        return rows

    def get_recent_alerts(self, hours: int = 1) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        c.execute("""
            SELECT * FROM alerts WHERE timestamp > ?
            ORDER BY timestamp DESC
        """, (cutoff,))
        rows = [dict(row) for row in c.fetchall()]
        conn.close()
        return rows

    def get_restart_count_last_hour(self, node_id: str) -> int:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        cutoff = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        c.execute("""
            SELECT COUNT(*) FROM restart_log 
            WHERE node_id = ? AND timestamp > ? AND success = 1
        """, (node_id, cutoff))
        count = c.fetchone()[0]
        conn.close()
        return count

# ========== PROBES ==========
class ProbeEngine:
    def __init__(self, db: Database):
        self.db = db
        self.metrics_history = {node_id: deque(maxlen=MAX_METRICS_POINTS) for node_id in NODES}
        self.failure_counts = {node_id: 0 for node_id in NODES}
        self.last_restart = {node_id: None for node_id in NODES}

    async def probe_node(self, node_id: str) -> Optional[NodeMetrics]:
        """Probe un noeud et retourne les métriques"""
        node = NODES[node_id]
        start = datetime.utcnow()
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{node['url']}{node['endpoint']}") as resp:
                    latency_ms = (datetime.utcnow() - start).total_seconds() * 1000
                    data = await resp.json()
                    models_count = len(data.get("models", []))
                    
                    # Récupère temp GPU
                    gpu_temp = await self._get_gpu_temp(node_id)
                    gpu_vram = await self._get_gpu_vram(node_id)
                    
                    metrics = NodeMetrics(
                        node_id=node_id,
                        timestamp=datetime.utcnow().isoformat(),
                        latency_ms=latency_ms,
                        gpu_temp=gpu_temp,
                        gpu_vram_percent=gpu_vram,
                        status="ONLINE",
                        models_count=models_count,
                        error=None
                    )
                    
                    self.metrics_history[node_id].append(asdict(metrics))
                    self.failure_counts[node_id] = 0
                    return metrics
                    
        except Exception as e:
            logger.warning(f"Probe failed for {node_id}: {str(e)}")
            self.failure_counts[node_id] += 1
            
            metrics = NodeMetrics(
                node_id=node_id,
                timestamp=datetime.utcnow().isoformat(),
                latency_ms=-1,
                gpu_temp=None,
                gpu_vram_percent=None,
                status="OFFLINE",
                models_count=0,
                error=str(e)
            )
            self.metrics_history[node_id].append(asdict(metrics))
            return metrics

    async def _get_gpu_temp(self, node_id: str) -> Optional[float]:
        """Récupère temp GPU via nvidia-smi"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                temp = float(result.stdout.strip().split()[0])
                return temp
        except Exception as e:
            logger.debug(f"GPU temp read failed: {e}")
        return None

    async def _get_gpu_vram(self, node_id: str) -> Optional[float]:
        """Récupère utilisation VRAM GPU"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                line = result.stdout.strip().split()[0]
                used, total = map(int, line.replace("MiB", "").split(","))
                return (used / total) * 100
        except Exception as e:
            logger.debug(f"GPU VRAM read failed: {e}")
        return None

    async def probe_all(self) -> Dict[str, NodeMetrics]:
        """Probe tous les noeuds en parallèle"""
        tasks = [self.probe_node(node_id) for node_id in NODES]
        results = await asyncio.gather(*tasks)
        return {node_id: metrics for node_id, metrics in zip(NODES.keys(), results)}

# ========== ALERTING ==========
class AlertManager:
    def __init__(self, db: Database):
        self.db = db
        self.consecutive_failures = {node_id: 0 for node_id in NODES}
        self.alert_cooldown = {}  # (node_id, category) -> timestamp

    def check_thresholds(self, metrics: NodeMetrics) -> List[Alert]:
        """Génère des alertes basées sur les seuils"""
        alerts = []
        now = datetime.utcnow().isoformat()
        
        if metrics.status == "OFFLINE":
            self.consecutive_failures[metrics.node_id] += 1
            if self.consecutive_failures[metrics.node_id] >= 3:
                alert = Alert(
                    timestamp=now,
                    node_id=metrics.node_id,
                    severity=AlertSeverity.CRITICAL.value,
                    message=f"{metrics.node_id} offline for 3+ probes",
                    category="offline"
                )
                alerts.append(alert)
                self.db.insert_alert(alert)
        else:
            self.consecutive_failures[metrics.node_id] = 0
        
        if metrics.gpu_temp and metrics.gpu_temp >= TEMP_CRITICAL:
            alert = Alert(
                timestamp=now,
                node_id=metrics.node_id,
                severity=AlertSeverity.CRITICAL.value,
                message=f"GPU CRITICAL: {metrics.gpu_temp}°C",
                category="temperature"
            )
            alerts.append(alert)
            self.db.insert_alert(alert)
        elif metrics.gpu_temp and metrics.gpu_temp >= TEMP_WARNING:
            alert = Alert(
                timestamp=now,
                node_id=metrics.node_id,
                severity=AlertSeverity.WARNING.value,
                message=f"GPU WARNING: {metrics.gpu_temp}°C",
                category="temperature"
            )
            alerts.append(alert)
            self.db.insert_alert(alert)
        
        if metrics.gpu_vram_percent and metrics.gpu_vram_percent >= VRAM_CRITICAL:
            alert = Alert(
                timestamp=now,
                node_id=metrics.node_id,
                severity=AlertSeverity.CRITICAL.value,
                message=f"VRAM CRITICAL: {metrics.gpu_vram_percent:.1f}%",
                category="vram"
            )
            alerts.append(alert)
            self.db.insert_alert(alert)
        
        if metrics.latency_ms > LATENCY_WARNING_MS:
            alert = Alert(
                timestamp=now,
                node_id=metrics.node_id,
                severity=AlertSeverity.WARNING.value,
                message=f"Latency high: {metrics.latency_ms:.0f}ms",
                category="latency"
            )
            alerts.append(alert)
            self.db.insert_alert(alert)
        
        return alerts

    def send_telegram_alert(self, alert: Alert):
        """Envoie alerte via Telegram (stub)"""
        try:
            telegram_token = "YOUR_TELEGRAM_TOKEN"
            chat_id = "YOUR_CHAT_ID"
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            
            severity_emoji = {"INFO": "ℹ️", "WARNING": "⚠️", "CRITICAL": "🔴"}
            emoji = severity_emoji.get(alert.severity, "")
            
            message = (
                f"{emoji} [{alert.severity}] {alert.node_id}\n"
                f"{alert.message}\n"
                f"Time: {alert.timestamp}"
            )
            
            requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=5)
            logger.info(f"Telegram alert sent: {alert.node_id}")
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")

# ========== SERVICE RESTART ==========
class RestartManager:
    def __init__(self, db: Database):
        self.db = db
        self.last_restart_time = {}
        self.restart_count_window = {}

    async def try_restart(self, node_id: str, reason: str) -> bool:
        """Essaie de redémarrer un service"""
        node = NODES[node_id]
        now = datetime.utcnow()
        
        # Cooldown check
        if node_id in self.last_restart_time:
            elapsed = (now - self.last_restart_time[node_id]).total_seconds()
            if elapsed < COOLDOWN_MINUTES * 60:
                logger.info(f"Restart for {node_id} on cooldown ({elapsed:.0f}s)")
                return False
        
        # Rate limit check
        restart_count = self.db.get_restart_count_last_hour(node_id)
        if restart_count >= MAX_RESTARTS_PER_HOUR:
            logger.warning(f"Max restarts reached for {node_id} in last hour")
            return False
        
        try:
            service = node["service"]
            if service == "LMStudio":
                # Restart LM Studio (Windows)
                subprocess.run(["taskkill", "/IM", "LMStudio.exe", "/F"], timeout=5)
                await asyncio.sleep(2)
                subprocess.Popen("LMStudio.exe", start_new_session=True)
            elif service == "Ollama":
                subprocess.run(["taskkill", "/IM", "ollama.exe", "/F"], timeout=5)
                await asyncio.sleep(2)
                subprocess.Popen("ollama.exe", start_new_session=True)
            
            self.last_restart_time[node_id] = now
            self.db.insert_restart(node_id, service, reason, True)
            logger.info(f"Restarted {service} for {node_id}")
            return True
        except Exception as e:
            logger.error(f"Restart failed for {node_id}: {e}")
            self.db.insert_restart(node_id, node["service"], reason, False)
            return False

# ========== MAIN WATCHDOG ==========
class WatchdogAgent:
    def __init__(self):
        self.db = Database(DB_PATH)
        self.probe = ProbeEngine(self.db)
        self.alerts = AlertManager(self.db)
        self.restarts = RestartManager(self.db)
        self.running = True
        self.last_heartbeat = None

    async def run(self):
        """Boucle principale"""
        logger.info("Watchdog Agent started")
        
        while self.running:
            try:
                # Probe tous les noeuds
                all_metrics = await self.probe.probe_all()
                
                healthy_count = sum(1 for m in all_metrics.values() if m.status == "ONLINE")
                total_count = len(NODES)
                
                # Log heartbeat toutes les 5min
                now = datetime.utcnow()
                if not self.last_heartbeat or (now - self.last_heartbeat).total_seconds() > HEARTBEAT_INTERVAL:
                    self.db.insert_heartbeat(healthy_count, total_count)
                    self.last_heartbeat = now
                    logger.info(f"Heartbeat: {healthy_count}/{total_count} nodes healthy")
                
                # Check seuils et génère alertes
                for node_id, metrics in all_metrics.items():
                    self.db.insert_metrics(metrics)
                    
                    if metrics.status == "ONLINE":
                        alerts = self.alerts.check_thresholds(metrics)
                        for alert in alerts:
                            self.alerts.send_telegram_alert(alert)
                            
                            # Restart si CRITICAL
                            if alert.severity == AlertSeverity.CRITICAL.value:
                                await self.restarts.try_restart(node_id, alert.category)
                
                await asyncio.sleep(CYCLE_SECONDS)
                
            except KeyboardInterrupt:
                logger.info("Shutdown requested")
                self.running = False
            except Exception as e:
                logger.error(f"Main loop error: {e}", exc_info=True)
                await asyncio.sleep(5)

async def main():
    agent = WatchdogAgent()
    try:
        await agent.run()
    except KeyboardInterrupt:
        logger.info("Watchdog stopped")

if __name__ == "__main__":
    asyncio.run(main())
