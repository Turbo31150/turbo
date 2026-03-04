#!/usr/bin/env python3
"""
JARVIS Predictive Analyzer - Analyse prédictive et détection d'anomalies
Basée sur historique cluster + machine learning classique
"""

import sqlite3
import json
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
import numpy as np
import requests

# ========== CONFIG ==========
BASE_PATH = r"F:\BUREAU\turbo"
DB_PATH = f"{BASE_PATH}\\jarvis.db"
LOG_FILE = f"{BASE_PATH}\\logs\\predictor.log"

# Nodes
NODES = ["M1", "M2", "M3", "OL1", "GEMINI", "CLAUDE"]

# Z-score threshold pour anomalies
ZSCORE_THRESHOLD = 2.5

# Prediction window (hours)
PREDICTION_WINDOW_HOURS = 1

# Event bus config
EVENT_BUS_URL = "http://127.0.0.1:8000"

# ========== LOGGING ==========
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ========== DATACLASSES ==========
@dataclass
class Anomaly:
    timestamp: str
    node_id: str
    metric_type: str  # "latency", "temperature", "vram"
    zscore: float
    value: float
    expected_value: float
    severity: str  # "warning", "critical"

@dataclass
class Prediction:
    node_id: str
    timestamp: str
    metric: str
    predicted_value: float
    confidence: float
    time_to_critical: Optional[int]  # minutes
    recommendation: str
    accuracy: Optional[float] = None

@dataclass
class HealthScore:
    timestamp: str
    node_id: str
    overall_score: float  # 0-100
    latency_score: float
    temperature_score: float
    vram_score: float
    stability_score: float
    breakdown: Dict

# ========== DATABASE ==========
class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialise les tables"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT,
                timestamp TEXT,
                metric TEXT,
                predicted_value REAL,
                confidence REAL,
                time_to_critical INTEGER,
                recommendation TEXT,
                accuracy REAL,
                actual_value REAL
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                node_id TEXT,
                metric_type TEXT,
                zscore REAL,
                value REAL,
                expected_value REAL,
                severity TEXT
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS health_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                node_id TEXT,
                overall_score REAL,
                latency_score REAL,
                temperature_score REAL,
                vram_score REAL,
                stability_score REAL,
                breakdown TEXT
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS recurring_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT,
                hour_of_day INTEGER,
                metric TEXT,
                avg_value REAL,
                std_dev REAL,
                occurrences INTEGER
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Predictor DB initialized")

    def insert_prediction(self, pred: Prediction):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO predictions 
            (node_id, timestamp, metric, predicted_value, confidence, time_to_critical, recommendation, accuracy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pred.node_id, pred.timestamp, pred.metric, pred.predicted_value,
            pred.confidence, pred.time_to_critical, pred.recommendation, pred.accuracy
        ))
        conn.commit()
        conn.close()

    def insert_anomaly(self, anomaly: Anomaly):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO anomalies 
            (timestamp, node_id, metric_type, zscore, value, expected_value, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            anomaly.timestamp, anomaly.node_id, anomaly.metric_type,
            anomaly.zscore, anomaly.value, anomaly.expected_value, anomaly.severity
        ))
        conn.commit()
        conn.close()

    def insert_health_score(self, score: HealthScore):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO health_scores 
            (timestamp, node_id, overall_score, latency_score, temperature_score, vram_score, stability_score, breakdown)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            score.timestamp, score.node_id, score.overall_score,
            score.latency_score, score.temperature_score, score.vram_score,
            score.stability_score, json.dumps(score.breakdown)
        ))
        conn.commit()
        conn.close()

    def get_metrics_window(self, node_id: str, hours: int = 2) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        c.execute("""
            SELECT * FROM node_metrics 
            WHERE node_id = ? AND timestamp > ? AND status = 'ONLINE'
            ORDER BY timestamp ASC
        """, (node_id, cutoff))
        rows = [dict(row) for row in c.fetchall()]
        conn.close()
        return rows

    def insert_recurring_pattern(self, node_id: str, hour: int, metric: str, avg: float, std: float, count: int):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO recurring_patterns 
            (node_id, hour_of_day, metric, avg_value, std_dev, occurrences)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (node_id, hour, metric, avg, std, count))
        conn.commit()
        conn.close()

# ========== ANOMALY DETECTION ==========
class AnomalyDetector:
    def __init__(self, db: Database):
        self.db = db

    def detect_zscore_anomalies(self, node_id: str, window_hours: int = 2) -> List[Anomaly]:
        """Détecte anomalies via z-score"""
        metrics = self.db.get_metrics_window(node_id, window_hours)
        
        if len(metrics) < 5:
            return []
        
        anomalies = []
        now = datetime.utcnow().isoformat()
        
        # Latency detection
        latencies = [m["latency_ms"] for m in metrics if m["latency_ms"] > 0]
        if len(latencies) >= 3:
            anomalies.extend(self._compute_zscores(
                node_id, "latency", latencies, metrics
            ))
        
        # GPU temp detection
        temps = [m["gpu_temp"] for m in metrics if m["gpu_temp"] is not None]
        if len(temps) >= 3:
            anomalies.extend(self._compute_zscores(
                node_id, "temperature", temps, metrics
            ))
        
        # VRAM detection
        vrams = [m["gpu_vram_percent"] for m in metrics if m["gpu_vram_percent"] is not None]
        if len(vrams) >= 3:
            anomalies.extend(self._compute_zscores(
                node_id, "vram", vrams, metrics
            ))
        
        return anomalies

    def _compute_zscores(self, node_id: str, metric_type: str, values: List[float], metrics: List) -> List[Anomaly]:
        """Calcule z-scores pour une métrique"""
        anomalies = []
        
        mean = np.mean(values)
        std = np.std(values)
        
        if std == 0:
            return anomalies
        
        for metric in metrics[-5:]:  # Derniers 5 points
            if metric_type == "latency":
                val = metric["latency_ms"]
                field = "latency_ms"
            elif metric_type == "temperature":
                val = metric["gpu_temp"]
                field = "gpu_temp"
            else:
                val = metric["gpu_vram_percent"]
                field = "gpu_vram_percent"
            
            if val is not None:
                zscore = abs((val - mean) / std)
                if zscore >= ZSCORE_THRESHOLD:
                    severity = "critical" if zscore >= 3.5 else "warning"
                    anomalies.append(Anomaly(
                        timestamp=datetime.utcnow().isoformat(),
                        node_id=node_id,
                        metric_type=metric_type,
                        zscore=zscore,
                        value=val,
                        expected_value=mean,
                        severity=severity
                    ))
        
        return anomalies

# ========== PREDICTIVE ENGINE ==========
class PredictiveEngine:
    def __init__(self, db: Database):
        self.db = db

    def predict_crash(self, node_id: str) -> Optional[Prediction]:
        """Prédit crash via trend analysis"""
        metrics = self.db.get_metrics_window(node_id, hours=1)
        
        if len(metrics) < 5:
            return None
        
        # Trend analysis sur GPU temp
        temps = [m["gpu_temp"] for m in metrics if m["gpu_temp"] is not None]
        if len(temps) >= 3:
            trend = self._calculate_trend(temps)
            if trend > 0.5:  # Augmentation rapide
                latest_temp = temps[-1]
                time_to_critical = self._estimate_time_to_critical(temps, TEMP_CRITICAL=85)
                
                if time_to_critical and time_to_critical < 15:  # < 15 min
                    return Prediction(
                        node_id=node_id,
                        timestamp=datetime.utcnow().isoformat(),
                        metric="gpu_temperature",
                        predicted_value=self._predict_next_value(temps),
                        confidence=0.75,
                        time_to_critical=time_to_critical,
                        recommendation="Reduce batch size or increase cooling",
                        accuracy=None
                    )
        
        # Trend analysis sur VRAM
        vrams = [m["gpu_vram_percent"] for m in metrics if m["gpu_vram_percent"] is not None]
        if len(vrams) >= 3:
            trend = self._calculate_trend(vrams)
            if trend > 1.0:  # Augmentation rapide
                latest_vram = vrams[-1]
                if latest_vram > 80:
                    time_to_critical = self._estimate_time_to_critical(vrams, threshold=90)
                    
                    if time_to_critical and time_to_critical < 20:
                        return Prediction(
                            node_id=node_id,
                            timestamp=datetime.utcnow().isoformat(),
                            metric="gpu_vram",
                            predicted_value=self._predict_next_value(vrams),
                            confidence=0.70,
                            time_to_critical=time_to_critical,
                            recommendation="Clear cache or reduce model context length",
                            accuracy=None
                        )
        
        return None

    def _calculate_trend(self, values: List[float]) -> float:
        """Calcule la pente de la tendance"""
        if len(values) < 2:
            return 0
        x = np.arange(len(values))
        y = np.array(values)
        slope = np.polyfit(x, y, 1)[0]
        return slope

    def _predict_next_value(self, values: List[float]) -> float:
        """Prédit la prochaine valeur"""
        if len(values) < 2:
            return values[-1]
        x = np.arange(len(values))
        y = np.array(values)
        coeffs = np.polyfit(x, y, 1)
        next_x = len(values)
        return float(np.polyval(coeffs, next_x))

    def _estimate_time_to_critical(self, values: List[float], threshold: float = 85) -> Optional[int]:
        """Estime temps jusqu'au seuil critique"""
        if len(values) < 2:
            return None
        
        x = np.arange(len(values))
        y = np.array(values)
        
        if y[-1] >= threshold:
            return 0
        
        slope = np.polyfit(x, y, 1)[0]
        if slope <= 0:
            return None
        
        remaining = threshold - y[-1]
        minutes_per_point = 0.5  # 30s par point
        time_to_critical = int((remaining / slope) * minutes_per_point)
        
        return max(1, time_to_critical)

    def detect_recurring_patterns(self, node_id: str) -> Dict[int, Dict]:
        """Détecte patterns récurrents par heure"""
        conn = sqlite3.connect(self.db.db_path)
        c = conn.cursor()
        
        # Récupère 7 jours de données
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        c.execute("""
            SELECT timestamp, gpu_temp FROM node_metrics 
            WHERE node_id = ? AND timestamp > ? AND gpu_temp IS NOT NULL
        """, (node_id, cutoff))
        
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            return {}
        
        # Groupe par heure du jour
        hourly_data = defaultdict(list)
        for ts, temp in rows:
            hour = datetime.fromisoformat(ts).hour
            hourly_data[hour].append(temp)
        
        patterns = {}
        for hour, temps in hourly_data.items():
            if len(temps) >= 2:
                avg = np.mean(temps)
                std = np.std(temps)
                patterns[hour] = {
                    "avg": float(avg),
                    "std": float(std),
                    "count": len(temps)
                }
                
                # Save pattern
                self.db.insert_recurring_pattern(
                    node_id, hour, "gpu_temp", avg, std, len(temps)
                )
        
        return patterns

# ========== HEALTH SCORING ==========
class HealthScorer:
    def __init__(self, db: Database):
        self.db = db

    def compute_health_score(self, node_id: str) -> HealthScore:
        """Calcule score de santé global"""
        metrics = self.db.get_metrics_window(node_id, hours=1)
        
        if not metrics:
            return HealthScore(
                timestamp=datetime.utcnow().isoformat(),
                node_id=node_id,
                overall_score=0,
                latency_score=0,
                temperature_score=0,
                vram_score=0,
                stability_score=0,
                breakdown={}
            )
        
        # Latency score
        latencies = [m["latency_ms"] for m in metrics if m["latency_ms"] > 0]
        latency_score = self._score_latency(latencies) if latencies else 100
        
        # Temperature score
        temps = [m["gpu_temp"] for m in metrics if m["gpu_temp"] is not None]
        temperature_score = self._score_temperature(temps) if temps else 100
        
        # VRAM score
        vrams = [m["gpu_vram_percent"] for m in metrics if m["gpu_vram_percent"] is not None]
        vram_score = self._score_vram(vrams) if vrams else 100
        
        # Stability score (0 fails per 10 probes = 100)
        online_count = sum(1 for m in metrics if m["status"] == "ONLINE")
        stability_score = (online_count / len(metrics)) * 100 if metrics else 0
        
        # Overall score (weighted average)
        overall = (
            latency_score * 0.25 +
            temperature_score * 0.30 +
            vram_score * 0.25 +
            stability_score * 0.20
        )
        
        breakdown = {
            "latency": {
                "score": latency_score,
                "avg_ms": np.mean(latencies) if latencies else 0,
                "max_ms": max(latencies) if latencies else 0
            },
            "temperature": {
                "score": temperature_score,
                "avg_c": np.mean(temps) if temps else 0,
                "max_c": max(temps) if temps else 0
            },
            "vram": {
                "score": vram_score,
                "avg_percent": np.mean(vrams) if vrams else 0,
                "max_percent": max(vrams) if vrams else 0
            },
            "stability": {
                "score": stability_score,
                "online_probes": online_count,
                "total_probes": len(metrics)
            }
        }
        
        return HealthScore(
            timestamp=datetime.utcnow().isoformat(),
            node_id=node_id,
            overall_score=overall,
            latency_score=latency_score,
            temperature_score=temperature_score,
            vram_score=vram_score,
            stability_score=stability_score,
            breakdown=breakdown
        )

    def _score_latency(self, latencies: List[float]) -> float:
        """Score 0-100 pour latence"""
        avg = np.mean(latencies)
        if avg < 100:
            return 100
        elif avg < 200:
            return 90
        elif avg < 500:
            return 70
        else:
            return max(0, 100 - (avg - 500) / 10)

    def _score_temperature(self, temps: List[float]) -> float:
        """Score 0-100 pour température"""
        max_temp = max(temps)
        if max_temp < 50:
            return 100
        elif max_temp < 65:
            return 90
        elif max_temp < 75:
            return 75
        elif max_temp < 85:
            return 50
        else:
            return max(0, 100 - (max_temp - 85) * 2)

    def _score_vram(self, vrams: List[float]) -> float:
        """Score 0-100 pour VRAM"""
        max_vram = max(vrams)
        if max_vram < 50:
            return 100
        elif max_vram < 70:
            return 85
        elif max_vram < 85:
            return 60
        elif max_vram < 95:
            return 30
        else:
            return 0

# ========== EVENT BUS ==========
class EventPublisher:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def publish_prediction(self, prediction: Prediction):
        """Publie prédiction sur event bus"""
        try:
            event = {
                "type": "prediction.crash_warning",
                "node_id": prediction.node_id,
                "metric": prediction.metric,
                "time_to_critical_minutes": prediction.time_to_critical,
                "recommendation": prediction.recommendation,
                "confidence": prediction.confidence
            }
            requests.post(f"{self.base_url}/events", json=event, timeout=2)
        except Exception as e:
            logger.debug(f"Event publish failed: {e}")

    def publish_anomaly(self, anomaly: Anomaly):
        """Publie anomalie"""
        try:
            event = {
                "type": "prediction.anomaly_detected",
                "node_id": anomaly.node_id,
                "metric": anomaly.metric_type,
                "zscore": anomaly.zscore,
                "severity": anomaly.severity
            }
            requests.post(f"{self.base_url}/events", json=event, timeout=2)
        except Exception as e:
            logger.debug(f"Event publish failed: {e}")

# ========== MAIN ANALYZER ==========
class PredictiveAnalyzer:
    def __init__(self):
        self.db = Database(DB_PATH)
        self.detector = AnomalyDetector(self.db)
        self.predictor = PredictiveEngine(self.db)
        self.scorer = HealthScorer(self.db)
        self.events = EventPublisher(EVENT_BUS_URL)

    async def analyze_all_nodes(self):
        """Analyse tous les noeuds"""
        logger.info("Running full analysis...")
        
        for node_id in NODES:
            try:
                # Anomalies
                anomalies = self.detector.detect_zscore_anomalies(node_id)
                for anomaly in anomalies:
                    self.db.insert_anomaly(anomaly)
                    self.events.publish_anomaly(anomaly)
                    logger.warning(f"Anomaly detected: {anomaly.node_id} {anomaly.metric_type} zscore={anomaly.zscore:.2f}")
                
                # Predictions
                prediction = self.predictor.predict_crash(node_id)
                if prediction:
                    self.db.insert_prediction(prediction)
                    self.events.publish_prediction(prediction)
                    logger.warning(f"Crash predicted: {prediction.node_id} in {prediction.time_to_critical}min")
                
                # Patterns
                patterns = self.predictor.detect_recurring_patterns(node_id)
                if patterns:
                    logger.info(f"Patterns found for {node_id}: {len(patterns)} hours")
                
                # Health score
                health = self.scorer.compute_health_score(node_id)
                self.db.insert_health_score(health)
                logger.info(f"Health: {node_id} = {health.overall_score:.1f}/100")
                
            except Exception as e:
                logger.error(f"Analysis failed for {node_id}: {e}")

    def export_report(self) -> Dict:
        """Exporte rapport JSON pour dashboard"""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "nodes": {}
        }
        
        for node_id in NODES:
            health = self.scorer.compute_health_score(node_id)
            prediction = self.predictor.predict_crash(node_id)
            
            report["nodes"][node_id] = {
                "health_score": health.overall_score,
                "breakdown": health.breakdown,
                "prediction": asdict(prediction) if prediction else None
            }
        
        return report

async def main():
    analyzer = PredictiveAnalyzer()
    try:
        while True:
            await analyzer.analyze_all_nodes()
            report = analyzer.export_report()
            logger.info(f"Analysis cycle complete: {json.dumps(report, indent=2)}")
            
            import asyncio
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        logger.info("Analyzer stopped")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
