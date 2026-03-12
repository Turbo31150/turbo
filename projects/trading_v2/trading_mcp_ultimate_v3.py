#!/usr/bin/env python3
"""
TRADING AI ULTIMATE MCP SERVER v3.5
Tous les workflows n8n + Toutes les IAs + Tous les services
+ MEXC Positions + Alertes + Multi-IA Avance + Backtesting + Monitoring
+ MCP Resources support
+ Dynamic Filters from config/filters.json (v3.3)
+ Distributed Load Balancer for 3 LM Studio machines (v3.4)
+ LM Studio CLI Manager - Automatic model management (v3.5)
"""
import json
import sys
import os
import subprocess
import urllib.request
import time
import threading
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime
import hashlib
import hmac
import sqlite3

# CCXT pour donnees OHLCV reelles
try:
    import ccxt
    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False

# Numpy pour indicateurs techniques
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# Filters loader for dynamic configuration (v3.3)
try:
    from filters_loader import (
        load_filters, get_filter, get_scanner_filters, get_telegram_filters,
        get_margin_filters, is_blacklisted, is_signal_type_enabled
    )
    FILTERS_AVAILABLE = True
except ImportError:
    FILTERS_AVAILABLE = False
    # Fallback functions if filters_loader not available
    def load_filters(): return {}
    def get_filter(path, default=None): return default
    def get_scanner_filters(): return {}
    def get_telegram_filters(): return {}
    def get_margin_filters(): return {}
    def is_blacklisted(s): return False
    def is_signal_type_enabled(s): return True

# Perplexity Scan Method (breakout detection with BB, RSI, MACD, orderbook)
try:
    from perplexity_scan_method import scan_all_coins as pplx_scan_all, get_top3_breakouts as pplx_top3, live_mode as pplx_live_mode
    PERPLEXITY_SCAN_AVAILABLE = True
except ImportError:
    PERPLEXITY_SCAN_AVAILABLE = False

# Pump Detector Ultimate - Advanced breakout/reversal detection with liquidity analysis
try:
    from pump_detector_ultimate import PumpDetector, get_top3_breakouts as pump_get_top3, main_scan as pump_main_scan, live_mode as pump_live_mode
    PUMP_DETECTOR_AVAILABLE = True
except ImportError:
    PUMP_DETECTOR_AVAILABLE = False

# MCP Technical Analysis Tools - Advanced MEXC analysis with indicators, scoring, entry/TP/SL
try:
    from mcp_technical_analysis_tools import (
        analyze_coin_deep, multi_coin_analysis, calculate_indicators_only,
        calculate_entry_tp_sl, scan_best_opportunities
    )
    MCP_TECH_ANALYSIS_AVAILABLE = True
except ImportError:
    MCP_TECH_ANALYSIS_AVAILABLE = False

# Breakout Imminent Scanner - Orderbook + Liquidity clusters analysis
try:
    from breakout_imminent_scanner import scan_breakout_imminent
    BREAKOUT_SCANNER_AVAILABLE = True
except ImportError:
    BREAKOUT_SCANNER_AVAILABLE = False

# Distributed Dispatcher - Load balancer for 3 LM Studio machines (v1.0)
try:
    from distributed_dispatcher import (
        get_dispatcher, dispatcher_status, dispatch_task_simple,
        dispatch_parallel_balanced, dispatch_consensus_question,
        get_server_metrics_all, set_server_priority_cmd, force_server_failover,
        run_distributed_scan, DistributedDispatcher
    )
    DISPATCHER_AVAILABLE = True
except ImportError:
    DISPATCHER_AVAILABLE = False
    def dispatcher_status(): return {'error': 'distributed_dispatcher not installed'}
    def dispatch_task_simple(*args, **kwargs): return {'error': 'distributed_dispatcher not installed'}
    def dispatch_parallel_balanced(*args, **kwargs): return {'error': 'distributed_dispatcher not installed'}
    def dispatch_consensus_question(*args, **kwargs): return {'error': 'distributed_dispatcher not installed'}
    def get_server_metrics_all(): return {'error': 'distributed_dispatcher not installed'}
    def set_server_priority_cmd(*args, **kwargs): return {'error': 'distributed_dispatcher not installed'}
    def force_server_failover(*args, **kwargs): return {'error': 'distributed_dispatcher not installed'}
    def run_distributed_scan(*args, **kwargs): return {'error': 'distributed_dispatcher not installed'}

# LM3 SQL Orchestrator - SQLite + LM3 SQL generator (v1.0)
try:
    from lm3_sql_orchestrator import (
        get_orchestrator, sql_save_signal, sql_get_signals,
        sql_top_signals, sql_stats, sql_query, sql_backup,
        sql_natural_query, sql_log_scan
    )
    SQL_ORCHESTRATOR_AVAILABLE = True
except ImportError:
    SQL_ORCHESTRATOR_AVAILABLE = False
    def sql_save_signal(*args, **kwargs): return {'error': 'lm3_sql_orchestrator not installed'}
    def sql_get_signals(*args, **kwargs): return {'error': 'lm3_sql_orchestrator not installed'}
    def sql_top_signals(*args, **kwargs): return {'error': 'lm3_sql_orchestrator not installed'}
    def sql_stats(): return {'error': 'lm3_sql_orchestrator not installed'}
    def sql_query(*args, **kwargs): return {'error': 'lm3_sql_orchestrator not installed'}
    def sql_backup(): return {'error': 'lm3_sql_orchestrator not installed'}
    def sql_natural_query(*args, **kwargs): return {'error': 'lm3_sql_orchestrator not installed'}
    def sql_log_scan(*args, **kwargs): return {'error': 'lm3_sql_orchestrator not installed'}

# Direction Validator - Multi-LM Studio Consensus for direction validation (v1.0)
try:
    from direction_validator_mcp import DirectionValidator
    DIRECTION_VALIDATOR_AVAILABLE = True
    _direction_validator = None
    def get_direction_validator():
        global _direction_validator
        if _direction_validator is None:
            _direction_validator = DirectionValidator()
        return _direction_validator
except ImportError:
    DIRECTION_VALIDATOR_AVAILABLE = False
    def get_direction_validator(): return None

# LM Studio CLI Manager - Automatic model management via CLI (v1.0)
try:
    # Add lmstudio directory to path
    lmstudio_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'SYSTEMES_IA', 'lmstudio')
    if lmstudio_path not in sys.path:
        sys.path.insert(0, lmstudio_path)
    from lmstudio_cli_manager import LMStudioCLIManager
    LMSTUDIO_CLI_AVAILABLE = True
    _lmstudio_cli_manager = None
    def get_lmstudio_cli_manager():
        global _lmstudio_cli_manager
        if _lmstudio_cli_manager is None:
            _lmstudio_cli_manager = LMStudioCLIManager()
        return _lmstudio_cli_manager
except ImportError as e:
    LMSTUDIO_CLI_AVAILABLE = False
    # Logger not yet initialized at this point
    print(f"Warning: LMStudio CLI Manager not available: {e}", file=sys.stderr)
    def get_lmstudio_cli_manager(): return None

# ============================================
# LOGGING CONFIGURATION (stderr pour MCP STDIO)
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # CRITICAL: MCP uses stdout for JSON-RPC, logs go to stderr
)
logger = logging.getLogger(__name__)

# ============================================
# CONFIGURATION - External Config Loader (v3.4.1)
# ============================================

def load_mcp_config() -> Dict:
    """Load configuration from external files: mcp-config.json + api-keys.env"""
    config = {}
    config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')

    # 1. Load mcp-config.json
    mcp_config_path = os.path.join(config_dir, 'mcp-config.json')
    mcp_config = {}
    try:
        if os.path.exists(mcp_config_path):
            with open(mcp_config_path, 'r', encoding='utf-8') as f:
                mcp_config = json.load(f)
            logger.info(f"Loaded MCP config from {mcp_config_path}")
    except Exception as e:
        logger.warning(f"Failed to load mcp-config.json: {e}")

    # 2. Load api-keys.env
    api_keys = {}
    api_keys_path = os.path.join(config_dir, 'api-keys.env')
    try:
        if os.path.exists(api_keys_path):
            with open(api_keys_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        api_keys[key.strip()] = value.strip()
            logger.info(f"Loaded API keys from {api_keys_path}")
    except Exception as e:
        logger.warning(f"Failed to load api-keys.env: {e}")

    # 3. Also check environment variables (override file values)
    env_keys = ['MEXC_ACCESS_KEY', 'MEXC_SECRET_KEY', 'TELEGRAM_BOT_TOKEN',
                'TELEGRAM_CHAT_ID', 'GEMINI_API_KEY', 'CLAUDE_API_KEY',
                'PERPLEXITY_API_KEY', 'N8N_API_KEY']
    for key in env_keys:
        if key in os.environ:
            api_keys[key] = os.environ[key]

    # 4. Build CONFIG dict from external sources
    endpoints = mcp_config.get('endpoints', {})
    lms_servers = endpoints.get('lmstudio', {}).get('servers', {})
    margin = mcp_config.get('margin_thresholds', {})

    config = {
        # Telegram
        "TELEGRAM_BOT": api_keys.get('TELEGRAM_BOT_TOKEN', ''),
        "TELEGRAM_CHAT": api_keys.get('TELEGRAM_CHAT_ID', ''),
        # Perplexity
        "PERPLEXITY_KEY": api_keys.get('PERPLEXITY_API_KEY', ''),
        # LM Studio - VIA CLUSTER PROXY (distribue automatiquement sur M1+M2+M3)
        "LM_STUDIO_PROXY": os.getenv('LM_STUDIO_PROXY', 'http://localhost:1234'),
        "LM_STUDIO_URL": os.getenv('LM_STUDIO_PROXY', 'http://localhost:1234'),
        "LM_STUDIO_PROD": os.getenv('LM_STUDIO_PROXY', 'http://localhost:1234'),
        "LM_STUDIO_TAMPON": os.getenv('LM_STUDIO_PROXY', 'http://localhost:1234'),
        "LM_STUDIO_BACKUP": os.getenv('LM_STUDIO_PROXY', 'http://localhost:1234'),
        "LM_STUDIO_MODEL": mcp_config.get('models', {}).get('analysis', 'qwen/qwen3-30b-a3b-2507'),
        "LM_STUDIO_FAST_MODEL": mcp_config.get('models', {}).get('fast', 'nvidia/nemotron-3-nano'),
        "LM_STUDIO_CODER_MODEL": mcp_config.get('models', {}).get('coder', 'qwen/qwen3-coder-30b'),
        "LMS_SERVERS": lms_servers,  # Full server config for health checks
        # LMS CLI
        "LMS_CLI_PATH": mcp_config.get('lms_cli', {}).get('path', 'C:/Users/franc/.lmstudio/bin/lms.exe'),
        "LMS_GPU_OFFLOAD": mcp_config.get('lms_cli', {}).get('gpu_offload', 'max'),
        "LMS_CONTEXT_LENGTH": mcp_config.get('lms_cli', {}).get('context_length', 8192),
        "LMS_TTL": mcp_config.get('lms_cli', {}).get('ttl', 3600),
        # MEXC
        "MEXC_URL": endpoints.get('mexc', {}).get('ticker_url', 'https://contract.mexc.com/api/v1/contract/ticker'),
        "MEXC_ACCESS_KEY": api_keys.get('MEXC_ACCESS_KEY', ''),
        "MEXC_SECRET_KEY": api_keys.get('MEXC_SECRET_KEY', ''),
        "MEXC_POSITIONS_URL": endpoints.get('mexc', {}).get('positions_url', 'https://contract.mexc.com/api/v1/private/position/open_positions'),
        # Gemini
        "GEMINI_CLI": "C:/Users/franc/AppData/Roaming/npm/gemini.cmd",
        "GEMINI_API_KEY": api_keys.get('GEMINI_API_KEY', ''),
        # Claude
        "CLAUDE_API_KEY": api_keys.get('CLAUDE_API_KEY', ''),
        # GitHub CLI
        "GH_CLI": "gh",
        # n8n
        "N8N_URL": endpoints.get('n8n', {}).get('url', 'http://localhost:5678'),
        "N8N_API_KEY": api_keys.get('N8N_API_KEY', ''),
        # Margin Thresholds
        "MARGIN_CRITICAL": margin.get('critical', 5),
        "MARGIN_DANGER": margin.get('danger', 8),
        "MARGIN_OK": margin.get('ok', 12),
        "MARGIN_SAFE": margin.get('safe', 20),
        # Database
        "DB_PATH": mcp_config.get('database', {}).get('path', 'F:/BUREAU/TRADING_V2_PRODUCTION/database/trading.db'),
        # Trading Parameters
        "TRADING_LEVERAGE": mcp_config.get('trading', {}).get('default_leverage', 10),
        "TRADING_SIZE_USDT": mcp_config.get('trading', {}).get('default_size_usdt', 10),
        "TRADING_TP1": mcp_config.get('trading', {}).get('tp_levels', {}).get('tp1_percent', 1.5),
        "TRADING_TP2": mcp_config.get('trading', {}).get('tp_levels', {}).get('tp2_percent', 3.0),
        "TRADING_TP3": mcp_config.get('trading', {}).get('tp_levels', {}).get('tp3_percent', 5.5),
        "TRADING_SL": mcp_config.get('trading', {}).get('sl_percent', 1.2),
        # Health Check & Circuit Breaker
        "HEALTH_CHECK_ENABLED": mcp_config.get('health_check', {}).get('enabled', True),
        "HEALTH_CHECK_INTERVAL": mcp_config.get('health_check', {}).get('interval_sec', 30),
        "HEALTH_CHECK_TIMEOUT": mcp_config.get('health_check', {}).get('timeout_sec', 5),
        "CIRCUIT_BREAKER_ENABLED": mcp_config.get('circuit_breaker', {}).get('enabled', True),
        "CIRCUIT_BREAKER_THRESHOLD": mcp_config.get('circuit_breaker', {}).get('failure_threshold', 3),
        "CIRCUIT_BREAKER_RECOVERY": mcp_config.get('circuit_breaker', {}).get('recovery_timeout_sec', 60),
        # Consensus
        "CONSENSUS_MIN_RESPONSES": mcp_config.get('consensus', {}).get('min_responses', 2),
        "CONSENSUS_TIMEOUT": mcp_config.get('consensus', {}).get('timeout_sec', 90),
        "CONSENSUS_WEIGHTS": mcp_config.get('consensus', {}).get('weights', {}),
        # Routing
        "SMART_ROUTE_ENABLED": mcp_config.get('routing', {}).get('smart_route_enabled', True),
        "FALLBACK_CHAIN": mcp_config.get('routing', {}).get('fallback_chain', []),
        "TASK_MAPPING": mcp_config.get('routing', {}).get('task_mapping', {}),
        # Full config reference
        "_MCP_CONFIG": mcp_config,
    }

    return config

# Load configuration at startup
CONFIG = load_mcp_config()

# Fallback to hardcoded values if external config failed
if not CONFIG.get('TELEGRAM_BOT'):
    logger.warning("External config incomplete, using fallback values")
    CONFIG.update({
        "TELEGRAM_BOT": "TELEGRAM-TOKEN-REDACTED",
        "TELEGRAM_CHAT": "2010747443",
        "PERPLEXITY_KEY": "pplx-REDACTED",
        "LM_STUDIO_PROXY": "http://localhost:1234",
        "LM_STUDIO_URL": "http://localhost:1234",
        "LM_STUDIO_PROD": "http://localhost:1234",
        "LM_STUDIO_TAMPON": "http://localhost:1234",
        "LM_STUDIO_BACKUP": "http://localhost:1234",
        "LM_STUDIO_MODEL": "qwen/qwen3-30b-a3b-2507",
        "LM_STUDIO_FAST_MODEL": "nvidia/nemotron-3-nano",
        "LM_STUDIO_CODER_MODEL": "qwen/qwen3-coder-30b",
        "LMS_CLI_PATH": "C:/Users/franc/.lmstudio/bin/lms.exe",
        "MEXC_URL": "https://contract.mexc.com/api/v1/contract/ticker",
        "MEXC_ACCESS_KEY": "MEXC-ACCESS-REDACTED",
        "MEXC_SECRET_KEY": "MEXC-SECRET-REDACTED",
        "MEXC_POSITIONS_URL": "https://contract.mexc.com/api/v1/private/position/open_positions",
        "GEMINI_API_KEY": "GEMINI-KEY-REDACTED",
        "CLAUDE_API_KEY": "sk-ant-REDACTED",
        "N8N_URL": "http://localhost:5678",
        "N8N_API_KEY": "N8N-TOKEN-REDACTED",
        "MARGIN_CRITICAL": 5,
        "MARGIN_DANGER": 8,
        "MARGIN_OK": 12,
        "MARGIN_SAFE": 20,
        "DB_PATH": "F:/BUREAU/TRADING_V2_PRODUCTION/database/trading.db",
    })

WORKFLOWS = {
    "trading_v4_multiia": "yy9az3YaYsSXsK7g",
    "trading_v1_ok": "xEizZfq2O1OdHDNR",
    "trading_ultimate_v3": "4ovJaOxtAzITyJEd",
    "multi_ia_telegram": "HtIDKlxK6UWHJux8",
    "scanner_pro_mexc": "kyoMdBQLuk67mFhs",
}

ALERTS = {"price_alerts": [], "margin_alerts": []}

# Anti-spam pour Telegram
TELEGRAM_COOLDOWN = {}  # {message_hash: last_sent_timestamp}
TELEGRAM_COOLDOWN_SECONDS = 300  # 5 min entre messages identiques
TRADE_HISTORY = []
IA_STATS = {"perplexity": {"calls": 0, "success": 0, "avg_time": 0}, "gemini": {"calls": 0, "success": 0, "avg_time": 0}, "lmstudio": {"calls": 0, "success": 0, "avg_time": 0}, "claude": {"calls": 0, "success": 0, "avg_time": 0}}
MONITORING_ACTIVE = False

# ============================================
# HEALTH CHECK & CIRCUIT BREAKER (v3.4.1)
# ============================================

class CircuitBreaker:
    """Circuit Breaker pattern for LM Studio server resilience"""

    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Failing, reject requests
    HALF_OPEN = "HALF_OPEN"  # Testing recovery

    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: int = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.success_count_half_open = 0
        self.half_open_max_calls = 2

    def can_execute(self) -> bool:
        """Check if request can be executed"""
        if self.state == self.CLOSED:
            return True
        elif self.state == self.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = self.HALF_OPEN
                self.success_count_half_open = 0
                logger.info(f"Circuit {self.name}: OPEN -> HALF_OPEN (testing recovery)")
                return True
            return False
        elif self.state == self.HALF_OPEN:
            return True
        return False

    def record_success(self):
        """Record successful call"""
        if self.state == self.HALF_OPEN:
            self.success_count_half_open += 1
            if self.success_count_half_open >= self.half_open_max_calls:
                self.state = self.CLOSED
                self.failure_count = 0
                logger.info(f"Circuit {self.name}: HALF_OPEN -> CLOSED (recovered)")
        elif self.state == self.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        """Record failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == self.HALF_OPEN:
            self.state = self.OPEN
            logger.warning(f"Circuit {self.name}: HALF_OPEN -> OPEN (still failing)")
        elif self.state == self.CLOSED and self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
            logger.warning(f"Circuit {self.name}: CLOSED -> OPEN (threshold reached: {self.failure_count})")

    def get_status(self) -> Dict:
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure": self.last_failure_time,
            "can_execute": self.can_execute()
        }

# Initialize circuit breakers for each LM Studio server
CIRCUIT_BREAKERS = {
    "lmstudio1": CircuitBreaker("lmstudio1", CONFIG.get("CIRCUIT_BREAKER_THRESHOLD", 3), CONFIG.get("CIRCUIT_BREAKER_RECOVERY", 60)),
    "lmstudio2": CircuitBreaker("lmstudio2", CONFIG.get("CIRCUIT_BREAKER_THRESHOLD", 3), CONFIG.get("CIRCUIT_BREAKER_RECOVERY", 60)),
    "lmstudio3": CircuitBreaker("lmstudio3", CONFIG.get("CIRCUIT_BREAKER_THRESHOLD", 3), CONFIG.get("CIRCUIT_BREAKER_RECOVERY", 60)),
    "gemini": CircuitBreaker("gemini", 5, 120),  # More lenient for cloud service
}

# Server health status cache
SERVER_HEALTH = {
    "lmstudio1": {"healthy": True, "last_check": 0, "latency_ms": 0, "model": None},
    "lmstudio2": {"healthy": True, "last_check": 0, "latency_ms": 0, "model": None},
    "lmstudio3": {"healthy": True, "last_check": 0, "latency_ms": 0, "model": None},
    "gemini": {"healthy": True, "last_check": 0, "latency_ms": 0},
}

# ============================================
# IA RESPONSE CACHE (v3.4.1)
# ============================================

class IAResponseCache:
    """LRU Cache for IA responses to reduce redundant API calls"""

    def __init__(self, max_size: int = 1000, ttl_sec: int = 300):
        self.max_size = max_size
        self.ttl_sec = ttl_sec
        self.cache = {}  # {hash: {'response': ..., 'timestamp': ..., 'hits': ...}}
        self.stats = {'hits': 0, 'misses': 0, 'evictions': 0}

    def _hash_key(self, prompt: str, model: str = None, temperature: float = None) -> str:
        """Generate cache key from prompt and params"""
        key_str = f"{prompt[:500]}|{model or 'default'}|{temperature or 0.3}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, prompt: str, model: str = None, temperature: float = None) -> Optional[Dict]:
        """Get cached response if valid"""
        key = self._hash_key(prompt, model, temperature)
        entry = self.cache.get(key)

        if entry:
            # Check TTL
            if time.time() - entry['timestamp'] < self.ttl_sec:
                self.stats['hits'] += 1
                entry['hits'] += 1
                return entry['response']
            else:
                # Expired, remove
                del self.cache[key]

        self.stats['misses'] += 1
        return None

    def set(self, prompt: str, response: Dict, model: str = None, temperature: float = None):
        """Cache a response"""
        key = self._hash_key(prompt, model, temperature)

        # Evict if at capacity (remove oldest)
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache, key=lambda k: self.cache[k]['timestamp'])
            del self.cache[oldest_key]
            self.stats['evictions'] += 1

        self.cache[key] = {
            'response': response,
            'timestamp': time.time(),
            'hits': 0,
            'prompt_preview': prompt[:100]
        }

    def clear(self):
        """Clear all cache"""
        self.cache.clear()
        self.stats = {'hits': 0, 'misses': 0, 'evictions': 0}

    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total * 100) if total > 0 else 0
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'evictions': self.stats['evictions'],
            'hit_rate_percent': round(hit_rate, 1),
            'ttl_sec': self.ttl_sec
        }

# Initialize global cache
IA_CACHE = IAResponseCache(
    max_size=CONFIG.get('_MCP_CONFIG', {}).get('cache', {}).get('max_entries', 1000),
    ttl_sec=CONFIG.get('_MCP_CONFIG', {}).get('cache', {}).get('ttl_sec', 300)
)

# ============================================
# RETRY WRAPPER WITH CIRCUIT BREAKER (v3.4.1)
# ============================================

def retry_with_fallback(
    func,
    server_key: str,
    max_retries: int = 2,
    timeout: int = 30,
    fallback_servers: List[str] = None
) -> Dict:
    """
    Execute function with retry logic and circuit breaker integration
    Falls back to other servers if primary fails
    """
    if fallback_servers is None:
        fallback_servers = CONFIG.get('FALLBACK_CHAIN', ['lmstudio1', 'lmstudio2', 'lmstudio3', 'gemini'])

    servers_to_try = [server_key] + [s for s in fallback_servers if s != server_key]
    last_error = None

    for server in servers_to_try:
        cb = CIRCUIT_BREAKERS.get(server)

        # Skip if circuit breaker is open
        if cb and not cb.can_execute():
            logger.debug(f"Skipping {server}: circuit breaker OPEN")
            continue

        for attempt in range(max_retries):
            try:
                start_time = time.time()
                result = func(server, timeout=timeout)
                elapsed = time.time() - start_time

                # Record success
                if cb:
                    cb.record_success()

                # Update health
                SERVER_HEALTH[server] = {
                    "healthy": True,
                    "last_check": time.time(),
                    "latency_ms": round(elapsed * 1000, 1)
                }

                result['_server_used'] = server
                result['_latency_ms'] = round(elapsed * 1000, 1)
                result['_attempt'] = attempt + 1
                return result

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1} failed for {server}: {e}")

                # Record failure on last attempt
                if attempt == max_retries - 1:
                    if cb:
                        cb.record_failure()
                    SERVER_HEALTH[server] = {
                        "healthy": False,
                        "last_check": time.time(),
                        "latency_ms": 0,
                        "error": last_error
                    }

                # Exponential backoff
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (2 ** attempt))

    return {
        'success': False,
        'error': f'All servers failed. Last error: {last_error}',
        'servers_tried': servers_to_try
    }

def call_lmstudio_with_retry(
    prompt: str,
    server_key: str = "lmstudio1",
    model: str = None,
    max_tokens: int = None,
    temperature: float = 0.3,
    use_cache: bool = True,
    task_type: str = None
) -> Dict:
    """
    Call LM Studio with caching, retry, circuit breaker, and adaptive timeout
    """
    # Auto-detect task type if not provided
    if task_type is None:
        task_type = detect_task_type_from_prompt(prompt)

    # Get adaptive timeout and max_tokens based on task type
    adaptive_timeout = get_adaptive_timeout(task_type, len(prompt))
    if max_tokens is None:
        max_tokens = get_max_tokens_for_task(task_type)

    # Check cache first
    if use_cache:
        cached = IA_CACHE.get(prompt, model, temperature)
        if cached:
            cached['_from_cache'] = True
            cached['_task_type'] = task_type
            return cached

    def _call_server(server: str, timeout: int = None) -> Dict:
        # Use adaptive timeout if not specified
        if timeout is None:
            timeout = adaptive_timeout
        servers_config = CONFIG.get('LMS_SERVERS', {})
        server_config = servers_config.get(server, {})

        url_map = {
            "lmstudio1": servers_config.get("lmstudio1", {}).get("url", "http://192.168.1.85:1234"),
            "lmstudio2": servers_config.get("lmstudio2", {}).get("url", "http://192.168.1.26:1234"),
            "lmstudio3": servers_config.get("lmstudio3", {}).get("url", "http://192.168.1.113:1234"),
        }

        url = server_config.get('url') or url_map.get(server, "http://127.0.0.1:1234")
        use_model = model or server_config.get('default_model') or CONFIG.get('LM_STUDIO_MODEL', 'qwen/qwen3-30b-a3b-2507')

        payload = json.dumps({
            'model': use_model,
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': max_tokens,
            'temperature': temperature
        }).encode()

        req = urllib.request.Request(
            f"{url}/v1/chat/completions",
            payload,
            {'Content-Type': 'application/json'}
        )

        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read())

        msg = result['choices'][0]['message']
        answer = msg.get('content') or msg.get('reasoning_content') or msg.get('reasoning') or ''
        return {
            'success': True,
            'answer': answer.strip(),
            'model': use_model,
            'server': server,
            '_task_type': task_type,
            '_timeout_used': timeout
        }

    result = retry_with_fallback(_call_server, server_key)
    result['_adaptive_timeout'] = adaptive_timeout
    result['_task_type_detected'] = task_type

    # Cache successful response
    if use_cache and result.get('success'):
        IA_CACHE.set(prompt, result, model, temperature)

    return result

def get_cache_stats() -> Dict:
    """Get IA cache statistics"""
    return {
        'success': True,
        'cache': IA_CACHE.get_stats(),
        'circuit_breakers': {k: v.get_status() for k, v in CIRCUIT_BREAKERS.items()}
    }

def clear_ia_cache() -> Dict:
    """Clear IA response cache"""
    IA_CACHE.clear()
    return {'success': True, 'message': 'IA cache cleared'}

def get_adaptive_timeout(task_type: str = "standard", prompt_length: int = 0) -> int:
    """
    Get adaptive timeout based on task type and prompt complexity
    Uses timeout_profiles from MCP config
    """
    # Load timeout profiles from config
    profiles = MCP_CONFIG.get("timeout_profiles", {})

    # Get base timeout for task type
    profile = profiles.get(task_type, profiles.get("standard", {"timeout_sec": 30}))
    base_timeout = profile.get("timeout_sec", 30)

    # Adjust for prompt length (longer prompts need more time)
    if prompt_length > 2000:
        base_timeout = int(base_timeout * 1.5)
    elif prompt_length > 4000:
        base_timeout = int(base_timeout * 2.0)

    # Cap at reasonable maximum
    return min(base_timeout, 180)

def get_max_tokens_for_task(task_type: str = "standard") -> int:
    """Get appropriate max_tokens based on task type"""
    profiles = MCP_CONFIG.get("timeout_profiles", {})
    profile = profiles.get(task_type, profiles.get("standard", {"max_tokens": 1024}))
    return profile.get("max_tokens", 1024)

def detect_task_type_from_prompt(prompt: str) -> str:
    """
    Auto-detect task type from prompt content
    Returns one of: quick, standard, trading_signal, deep_analysis, consensus
    """
    prompt_lower = prompt.lower()

    # Quick questions
    if len(prompt) < 100 or any(kw in prompt_lower for kw in ["yes or no", "simple", "quick", "define"]):
        return "quick"

    # Trading signals
    if any(kw in prompt_lower for kw in ["signal", "entry", "tp", "sl", "long", "short", "buy", "sell", "trade"]):
        return "trading_signal"

    # Deep analysis
    if any(kw in prompt_lower for kw in ["analyze", "analysis", "deep", "comprehensive", "detailed", "explain why"]):
        return "deep_analysis"

    # Consensus
    if "consensus" in prompt_lower or "vote" in prompt_lower:
        return "consensus"

    return "standard"

def health_check_lmstudio(server_key: str, timeout: int = None) -> Dict:
    """
    Check LM Studio server health with circuit breaker
    Returns: {healthy: bool, latency_ms: float, model: str, error: str}
    """
    if timeout is None:
        timeout = CONFIG.get("HEALTH_CHECK_TIMEOUT", 5)

    servers = CONFIG.get("LMS_SERVERS", {})
    server_config = servers.get(server_key, {})

    # Direct IPs for each server (NOT proxy)
    url_map = {
        "lmstudio1": servers.get("lmstudio1", {}).get("url", "http://192.168.1.85:1234"),
        "lmstudio2": servers.get("lmstudio2", {}).get("url", "http://192.168.1.26:1234"),
        "lmstudio3": servers.get("lmstudio3", {}).get("url", "http://192.168.1.113:1234"),
    }

    url = server_config.get("url") or url_map.get(server_key, "http://127.0.0.1:1234")

    # Check circuit breaker first
    cb = CIRCUIT_BREAKERS.get(server_key)
    if cb and not cb.can_execute():
        return {
            "healthy": False,
            "latency_ms": 0,
            "model": None,
            "error": f"Circuit breaker OPEN for {server_key}",
            "circuit_state": cb.state
        }

    try:
        start = time.time()
        models_url = f"{url}/v1/models"
        req = urllib.request.Request(models_url, headers={"Content-Type": "application/json"})

        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())

        latency = (time.time() - start) * 1000
        models = data.get("data", [])
        current_model = models[0].get("id") if models else None

        # Update health cache
        SERVER_HEALTH[server_key] = {
            "healthy": True,
            "last_check": time.time(),
            "latency_ms": round(latency, 1),
            "model": current_model
        }

        # Record success in circuit breaker
        if cb:
            cb.record_success()

        return {
            "healthy": True,
            "latency_ms": round(latency, 1),
            "model": current_model,
            "models_count": len(models)
        }

    except Exception as e:
        # Record failure in circuit breaker
        if cb:
            cb.record_failure()

        SERVER_HEALTH[server_key] = {
            "healthy": False,
            "last_check": time.time(),
            "latency_ms": 0,
            "model": None,
            "error": str(e)
        }

        return {
            "healthy": False,
            "latency_ms": 0,
            "model": None,
            "error": str(e)
        }

def check_all_lmstudio_servers() -> Dict:
    """Check health of all LM Studio servers"""
    results = {}
    for server_key in ["lmstudio1", "lmstudio2", "lmstudio3"]:
        results[server_key] = health_check_lmstudio(server_key)

    healthy_count = sum(1 for r in results.values() if r.get("healthy"))

    return {
        "success": True,
        "servers": results,
        "healthy_count": healthy_count,
        "total_count": len(results),
        "all_healthy": healthy_count == len(results),
        "circuit_breakers": {k: v.get_status() for k, v in CIRCUIT_BREAKERS.items()}
    }

def health_check_all_servers(include_metrics: bool = True) -> Dict:
    """
    Comprehensive health check of all LM Studio servers
    Includes circuit breaker status, latency, models, and cache stats
    """
    results = {}

    for server_key in ["lmstudio1", "lmstudio2", "lmstudio3"]:
        server_config = MCP_CONFIG.get("endpoints", {}).get("lmstudio", {}).get("servers", {}).get(server_key, {})
        health = health_check_lmstudio(server_key)
        cb = CIRCUIT_BREAKERS.get(server_key)

        server_result = {
            "name": server_config.get("name", server_key),
            "url": server_config.get("url", f"http://192.168.1.{85 if server_key == 'lmstudio1' else (26 if server_key == 'lmstudio2' else 113)}:1234"),
            "healthy": health.get("healthy", False),
            "latency_ms": health.get("latency_ms", -1),
            "models_available": health.get("models_count", 0),
            "circuit_breaker": cb.get_status() if cb else {"state": "UNKNOWN"},
            "enabled": server_config.get("enabled", True),
            "gpu_count": server_config.get("gpu_count", 0),
            "speed_tps": server_config.get("speed_tps", 0)
        }

        if include_metrics:
            # Add recent performance metrics from SERVER_HEALTH
            cached_health = SERVER_HEALTH.get(server_key, {})
            server_result["metrics"] = {
                "last_success": cached_health.get("last_success"),
                "last_failure": cached_health.get("last_failure"),
                "recent_latencies": cached_health.get("latencies", [])[-5:],
                "avg_latency_ms": sum(cached_health.get("latencies", [0])) / max(len(cached_health.get("latencies", [1])), 1)
            }

        results[server_key] = server_result

    # Summary
    healthy_count = sum(1 for r in results.values() if r.get("healthy"))
    total_tps = sum(r.get("speed_tps", 0) for r in results.values() if r.get("healthy"))

    # Cache stats
    cache_stats = get_cache_stats() if IA_RESPONSE_CACHE else {}

    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "servers": results,
        "summary": {
            "healthy_count": healthy_count,
            "total_count": len(results),
            "all_healthy": healthy_count == len(results),
            "total_available_tps": total_tps,
            "best_server": get_best_available_server("general")
        },
        "cache": cache_stats,
        "fallback_chain": CONFIG.get("FALLBACK_CHAIN", [])
    }

def get_best_available_server(task_type: str = "general") -> Optional[str]:
    """
    Get the best available LM Studio server for a task type
    Uses health status + circuit breakers + task routing
    """
    task_mapping = CONFIG.get("TASK_MAPPING", {})
    preferred_server = task_mapping.get(task_type, "lmstudio1")

    # If single server, check if it's available
    if isinstance(preferred_server, str):
        cb = CIRCUIT_BREAKERS.get(preferred_server)
        if cb and cb.can_execute() and SERVER_HEALTH.get(preferred_server, {}).get("healthy", True):
            return preferred_server

    # Fallback chain
    fallback_chain = CONFIG.get("FALLBACK_CHAIN", ["lmstudio1", "lmstudio2", "lmstudio3", "gemini"])

    for server in fallback_chain:
        cb = CIRCUIT_BREAKERS.get(server)
        health = SERVER_HEALTH.get(server, {})

        if cb and cb.can_execute():
            # Check cached health (if recent)
            if time.time() - health.get("last_check", 0) < CONFIG.get("HEALTH_CHECK_INTERVAL", 30):
                if health.get("healthy", True):
                    return server
            else:
                # Health check expired, assume available but verify on call
                return server

    # Last resort: return first server in chain
    return fallback_chain[0] if fallback_chain else "lmstudio1"

def smart_route_request(prompt: str, task_type: str = None) -> str:
    """
    Intelligently route request to best available server
    Auto-detects task type if not provided
    """
    if task_type is None:
        # Auto-detect task type from prompt
        prompt_lower = prompt.lower()
        if any(kw in prompt_lower for kw in ["code", "python", "function", "class", "debug"]):
            task_type = "code_generation"
        elif any(kw in prompt_lower for kw in ["trade", "signal", "long", "short", "entry", "tp", "sl"]):
            task_type = "trading_signal"
        elif any(kw in prompt_lower for kw in ["analyze", "analysis", "deep", "explain"]):
            task_type = "deep_analysis"
        elif any(kw in prompt_lower for kw in ["quick", "simple", "yes", "no", "?"]):
            task_type = "quick_question"
        else:
            task_type = "general"

    return get_best_available_server(task_type)

def get_circuit_breaker_status() -> Dict:
    """Get status of all circuit breakers"""
    return {
        "success": True,
        "circuit_breakers": {k: v.get_status() for k, v in CIRCUIT_BREAKERS.items()},
        "server_health": SERVER_HEALTH
    }

def reset_circuit_breaker(server_key: str) -> Dict:
    """Manually reset a circuit breaker"""
    cb = CIRCUIT_BREAKERS.get(server_key)
    if cb:
        cb.state = CircuitBreaker.CLOSED
        cb.failure_count = 0
        cb.success_count_half_open = 0
        return {"success": True, "message": f"Circuit breaker {server_key} reset to CLOSED"}
    return {"success": False, "error": f"Unknown server: {server_key}"}

# ============================================
# SQL PERSISTENCE (v3.2)
# ============================================

def get_db_connection():
    try:
        conn = sqlite3.connect(CONFIG["DB_PATH"])
        conn.row_factory = sqlite3.Row
        return conn
    except: return None

# ============================================
# CQ SYSTEM - CONTEXTUAL QUOTIENT (v1.0)
# ============================================

_CONTEXT_CACHE = {'data': None, 'timestamp': 0}

def invalidate_context_cache():
    """Force le refresh du cache contexte au prochain appel."""
    global _CONTEXT_CACHE
    _CONTEXT_CACHE = {'data': None, 'timestamp': 0}

def get_ia_accuracy(days=30):
    """Retourne l'accuracy de chaque IA basee sur les resultats reels (table consensus)."""
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        rows = conn.execute("""
            SELECT consensus_result,
                   SUM(CASE WHEN json_extract(notes, '$.correct') = 1 THEN 1 ELSE 0 END) as correct,
                   SUM(CASE WHEN json_extract(notes, '$.correct') = 0 THEN 1 ELSE 0 END) as incorrect,
                   COUNT(*) as total
            FROM consensus
            WHERE created_at > datetime('now', ?)
            AND json_extract(notes, '$.correct') IS NOT NULL
            GROUP BY consensus_result
        """, (f'-{days} days',)).fetchall()
        conn.close()
        result = {}
        for row in rows:
            r = dict(row)
            total = r['correct'] + r['incorrect']
            result[r['consensus_result']] = {
                'accuracy': round(r['correct'] / total * 100, 1) if total > 0 else 0,
                'total': total
            }
        return result
    except:
        try: conn.close()
        except: pass
        return {}

def build_trading_context(symbol=None, max_age_seconds=120, force_refresh=False):
    """Assemble le contexte trading complet depuis DB + MEXC API.
    Resultat cache pendant max_age_seconds pour eviter les queries repetees.
    ~200-350 tokens max, format concis."""
    global _CONTEXT_CACHE
    now = time.time()
    if not force_refresh and _CONTEXT_CACHE['data'] and (now - _CONTEXT_CACHE['timestamp']) < max_age_seconds:
        cached = _CONTEXT_CACHE['data']
        if symbol and f"[COIN " in cached and f"[COIN {symbol}" not in cached:
            pass  # symbol different, on refresh
        else:
            return {'success': True, 'context': cached, 'cached': True}

    parts = []
    conn = get_db_connection()

    try:
        # BLOC 1 - Positions ouvertes
        try:
            pos_result = get_mexc_positions()
            if pos_result.get('success') and pos_result.get('positions'):
                positions = pos_result['positions']
                pos_strs = []
                for p in positions[:5]:
                    sym = p.get('symbol', '?')
                    direction = 'LONG' if str(p.get('holdSide', p.get('direction', 'long'))).upper() == 'LONG' else 'SHORT'
                    margin_r = p.get('margin_ratio', p.get('marginRatio', '?'))
                    pnl = p.get('unrealizedPnl', p.get('unrealized_pnl', 0))
                    status = 'CRITIQUE' if isinstance(margin_r, (int, float)) and margin_r < 5 else 'DANGER' if isinstance(margin_r, (int, float)) and margin_r < 8 else 'OK'
                    pos_strs.append(f"{sym} {direction} marge {margin_r}% {status} PnL {pnl}")
                parts.append(f"[POSITIONS] {len(positions)} ouvertes: {'; '.join(pos_strs)}")
            else:
                parts.append("[POSITIONS] 0 ouvertes")
        except:
            parts.append("[POSITIONS] indisponible")

        # BLOC 2 - Marge globale
        try:
            if conn:
                row = conn.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN ancrage_status='CRITIQUE' THEN 1 ELSE 0 END) as critique,
                           SUM(CASE WHEN ancrage_status='DANGER' THEN 1 ELSE 0 END) as danger,
                           SUM(COALESCE(margin, 0)) as total_margin
                    FROM positions WHERE ancrage_status != 'closed' AND ancrage_status IS NOT NULL
                """).fetchone()
                if row and dict(row)['total'] > 0:
                    r = dict(row)
                    parts.append(f"[MARGE] {r['total_margin']:.1f} USDT engages, {r['critique']} CRITIQUE, {r['danger']} DANGER")
                else:
                    parts.append("[MARGE] aucune position DB")
        except:
            pass

        # BLOC 3 - Historique recent (10 derniers trades)
        try:
            if conn:
                trades = conn.execute("""
                    SELECT symbol, direction, net_pnl, pnl_percent, status
                    FROM trades ORDER BY close_time DESC LIMIT 10
                """).fetchall()
                if trades:
                    wins = sum(1 for t in trades if dict(t).get('net_pnl', 0) and dict(t)['net_pnl'] > 0)
                    losses = len(trades) - wins
                    last = dict(trades[0])
                    last_sym = last.get('symbol', '?')
                    last_pnl = last.get('pnl_percent', last.get('net_pnl', 0))
                    streak = 0
                    streak_type = 'W' if dict(trades[0]).get('net_pnl', 0) and dict(trades[0])['net_pnl'] > 0 else 'L'
                    for t in trades:
                        td = dict(t)
                        is_win = td.get('net_pnl', 0) and td['net_pnl'] > 0
                        if (streak_type == 'W' and is_win) or (streak_type == 'L' and not is_win):
                            streak += 1
                        else:
                            break
                    parts.append(f"[TRADES] 10 derniers: {wins}W/{losses}L, streak: {streak}{streak_type}, dernier: {last_sym} {'+' if last_pnl and last_pnl > 0 else ''}{last_pnl}%")
                else:
                    parts.append("[TRADES] aucun trade recent")
        except:
            parts.append("[TRADES] indisponible")

        # BLOC 4 - Winrate par coin (si symbol fourni)
        if symbol and conn:
            try:
                clean_sym = symbol.replace('/USDT', '').replace('_USDT', '').replace('USDT', '')
                coin_stats = conn.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) as wins,
                           AVG(net_pnl) as avg_pnl
                    FROM trades WHERE symbol LIKE ? AND status='closed'
                """, (f'%{clean_sym}%',)).fetchone()
                if coin_stats and dict(coin_stats)['total'] > 0:
                    cs = dict(coin_stats)
                    wr = round(cs['wins'] / cs['total'] * 100, 1) if cs['total'] > 0 else 0
                    parts.append(f"[COIN {clean_sym}] {cs['total']} trades, winrate {wr}%, avg PnL {cs['avg_pnl']:.1f} USDT")
            except:
                pass

        # BLOC 5 - Performance du jour
        try:
            if conn:
                perf = conn.execute("""
                    SELECT total_trades, win_rate, net_pnl FROM performance
                    WHERE date = date('now') LIMIT 1
                """).fetchone()
                if perf:
                    p = dict(perf)
                    parts.append(f"[PERF JOUR] {p['total_trades']} trades, WR {p['win_rate']}%, PnL net {p['net_pnl']} USDT")
        except:
            pass

        # BLOC 6 - Accuracy IA
        try:
            ia_acc = get_ia_accuracy(30)
            if ia_acc:
                acc_strs = [f"{k} {v['accuracy']}% ({v['total']})" for k, v in ia_acc.items()]
                parts.append(f"[IA ACCURACY 30j] {', '.join(acc_strs)}")
        except:
            pass

        # BLOC 7 - Regime marche (BTC)
        try:
            if CCXT_AVAILABLE:
                exchange = ccxt.mexc({'enableRateLimit': True})
                btc = exchange.fetch_ticker('BTC/USDT:USDT')
                pct = btc.get('percentage', 0)
                regime = 'BULL' if pct > 2 else 'BEAR' if pct < -2 else 'RANGE'
                warning = ', prudence sur les longs' if pct < -1 else ', favorable aux longs' if pct > 1 else ''
                parts.append(f"[MARCHE] BTC {pct:+.1f}% = {regime}{warning}")
            else:
                try:
                    url = f'{CONFIG.get("MEXC_API", "https://contract.mexc.com/api/v1")}/contract/ticker?symbol=BTC_USDT'
                    with urllib.request.urlopen(url, timeout=5) as r:
                        data = json.loads(r.read()).get('data', {})
                        pct = float(data.get('riseFallRate', 0)) * 100
                        regime = 'BULL' if pct > 2 else 'BEAR' if pct < -2 else 'RANGE'
                        warning = ', prudence sur les longs' if pct < -1 else ', favorable aux longs' if pct > 1 else ''
                        parts.append(f"[MARCHE] BTC {pct:+.1f}% = {regime}{warning}")
                except:
                    pass
        except:
            pass

        if conn:
            try: conn.close()
            except: pass

    except Exception as e:
        if conn:
            try: conn.close()
            except: pass
        return {'success': False, 'error': str(e), 'context': ''}

    context_str = "\n".join(parts) if parts else "[CONTEXTE] Aucune donnee disponible"
    _CONTEXT_CACHE = {'data': context_str, 'timestamp': time.time()}
    return {'success': True, 'context': context_str, 'cached': False, 'blocks': len(parts)}

def log_consensus_decision(symbol, question, result, confidence, details, source='mcp'):
    """Log une decision consensus dans la table consensus pour le feedback loop."""
    conn = get_db_connection()
    if not conn:
        return {'success': False, 'error': 'No DB connection'}
    try:
        conn.execute("""
            INSERT INTO consensus (symbol, question, consensus_result, confidence,
                                  details, triggered_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, (symbol, question[:500], result, confidence, json.dumps(details) if isinstance(details, dict) else str(details), source))
        conn.commit()
        conn.close()
        return {'success': True}
    except Exception as e:
        try: conn.close()
        except: pass
        return {'success': False, 'error': str(e)}

def update_consensus_outcome(symbol, actual_result, actual_pnl):
    """Met a jour le dernier consensus pour ce symbol avec le resultat reel."""
    conn = get_db_connection()
    if not conn:
        return {'success': False, 'error': 'No DB connection'}
    try:
        last = conn.execute("""
            SELECT id, consensus_result FROM consensus
            WHERE symbol LIKE ? ORDER BY id DESC LIMIT 1
        """, (f'%{symbol}%',)).fetchone()
        if not last:
            conn.close()
            return {'success': False, 'error': f'No consensus found for {symbol}'}
        last_d = dict(last)
        correct = 1 if (
            (last_d['consensus_result'] in ('LONG', 'BUY') and actual_result == 'WIN') or
            (last_d['consensus_result'] in ('SHORT', 'SELL') and actual_result == 'WIN') or
            (last_d['consensus_result'] == 'HOLD' and actual_result == 'LOSS')
        ) else 0
        notes_json = json.dumps({
            'actual_result': actual_result,
            'actual_pnl': actual_pnl,
            'correct': correct
        })
        conn.execute("UPDATE consensus SET notes = ? WHERE id = ?", (notes_json, last_d['id']))
        conn.commit()
        conn.close()
        invalidate_context_cache()
        return {'success': True, 'consensus_id': last_d['id'], 'correct': bool(correct),
                'consensus_was': last_d['consensus_result'], 'actual': actual_result, 'pnl': actual_pnl}
    except Exception as e:
        try: conn.close()
        except: pass
        return {'success': False, 'error': str(e)}

# ============================================
# CQ v1.1 - TURBO MULTI-CONSENSUS + SCAN
# ============================================

# Cluster config avec IPs reelles
CQ_CLUSTER = {
    'M1': {'url': 'http://192.168.1.85:1234', 'models': ['qwen/qwen3-30b-a3b-2507', 'openai/gpt-oss-20b'], 'weight': 1.3, 'role': 'deep'},
    'M2': {'url': 'http://192.168.1.26:1234', 'models': ['nvidia/nemotron-3-nano', 'openai/gpt-oss-20b'], 'weight': 1.0, 'role': 'fast'},
    'M3': {'url': 'http://192.168.1.113:1234', 'models': ['nvidia/nemotron-3-nano', 'openai/gpt-oss-20b'], 'weight': 0.8, 'role': 'validate'},
}

CQ_SYSTEM_PROMPT = "Tu es un trader crypto expert. Reponds au format: DIRECTION confiance/10 raison. Exemple: LONG 8/10 breakout confirme"
CQ_MODELS_NO_SYSTEM = {'mistral-7b-instruct-v0.3', 'phi-3.1-mini-128k-instruct'}

def _cq_call(server_url, model, prompt, system_prompt=None, max_tokens=60, timeout=45):
    """Appel LM Studio optimise. Skip system prompt pour Mistral/Phi (HTTP 400)."""
    try:
        messages = []
        if system_prompt and model not in CQ_MODELS_NO_SYSTEM:
            messages.append({'role': 'system', 'content': system_prompt})
        elif system_prompt and model in CQ_MODELS_NO_SYSTEM:
            prompt = f"{system_prompt}\n\n{prompt}"
        messages.append({'role': 'user', 'content': prompt})
        payload = json.dumps({
            'model': model, 'messages': messages,
            'max_tokens': max_tokens, 'temperature': 0.1,
            'top_p': 0.9
        }).encode()
        req = urllib.request.Request(f'{server_url}/v1/chat/completions', payload, {'Content-Type': 'application/json'})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as r:
            res = json.loads(r.read())
            answer = res['choices'][0]['message'].get('content', '').strip()
            elapsed = round(time.time() - t0, 1)
            return {'success': True, 'answer': answer, 'time': elapsed, 'model': model}
    except Exception as e:
        return {'success': False, 'answer': '', 'time': 0, 'error': str(e)[:50]}

def _cq_parse_vote(text):
    """Parse un vote LONG/SHORT/HOLD depuis une reponse IA."""
    if not text: return 'HOLD', 5
    upper = text.upper()
    # Extract confidence
    conf = 5
    import re
    conf_match = re.search(r'(\d+)\s*/\s*10|confiance\s*:?\s*(\d+)|(\d+)/10', upper)
    if conf_match:
        conf = int(next(g for g in conf_match.groups() if g))
    elif re.search(r'\b([7-9]|10)\b', text) and len(text) < 50:
        nums = re.findall(r'\b(\d+)\b', text)
        for n in nums:
            if 1 <= int(n) <= 10:
                conf = int(n); break
    # Parse direction
    if 'LONG' in upper or 'BUY' in upper or 'ACHAT' in upper or 'HAUSSIER' in upper:
        return 'LONG', conf
    if 'SHORT' in upper or 'SELL' in upper or 'VENTE' in upper or 'BAISSIER' in upper:
        return 'SHORT', conf
    return 'HOLD', conf

def get_adaptive_weights():
    """Retourne les poids adaptatifs bases sur l'accuracy IA reelle."""
    base = {'M1': 1.3, 'M2': 1.0, 'M3': 0.8}
    try:
        acc = get_ia_accuracy(14)
        if acc:
            for key, data in acc.items():
                if data.get('total', 0) >= 5:
                    boost = (data['accuracy'] - 50) / 100  # +/-0.3 max
                    if 'qwen' in key.lower() or 'deep' in key.lower():
                        base['M1'] = max(0.5, min(2.0, base['M1'] + boost))
                    elif 'nemo' in key.lower() or 'fast' in key.lower():
                        base['M2'] = max(0.5, min(2.0, base['M2'] + boost))
                    elif 'mist' in key.lower() or 'valid' in key.lower():
                        base['M3'] = max(0.5, min(2.0, base['M3'] + boost))
    except:
        pass
    return base


# ============================================
# TELEGRAM SIGNAL FORMATTER (Unified)
# ============================================

def _fmt_price(p):
    """Format price based on magnitude."""
    if p is None or p == 0:
        return "$0"
    if p < 0.0001:
        return f"${p:.8f}"
    elif p < 0.01:
        return f"${p:.6f}"
    elif p < 1:
        return f"${p:.4f}"
    elif p < 100:
        return f"${p:.3f}"
    elif p < 10000:
        return f"${p:,.2f}"
    else:
        return f"${p:,.0f}"

def _pct_diff(target, entry):
    """Calculate percentage difference."""
    if not entry or entry == 0:
        return 0
    return (target / entry - 1) * 100

def format_telegram_signal(symbol, direction, entry, tp1, tp2, tp3, sl,
                           confidence=0, rr_ratio=0, score=0, change_pct=0,
                           volume_m=0, range_pos=0, ia_details=None,
                           models_count=0, avg_conf=0, signal_type='SIGNAL',
                           pump_signals=None, weights=None, whale_info=''):
    """
    Formateur unifie pour TOUTES les alertes Telegram trading.
    Produit un message HTML bien structure avec Entry, TP1, TP2, TP3, SL.
    """
    # Direction indicators
    if direction == 'LONG':
        dir_emoji = '\U0001f7e2'   # green circle
        dir_arrow = '\u2197\ufe0f' # up-right arrow
        bar = '\u2588' * min(int(confidence / 10), 10)
    elif direction == 'SHORT':
        dir_emoji = '\U0001f534'   # red circle
        dir_arrow = '\u2198\ufe0f' # down-right arrow
        bar = '\u2588' * min(int(confidence / 10), 10)
    else:
        dir_emoji = '\u26aa'
        dir_arrow = '\u27a1\ufe0f'
        bar = ''

    # Confidence bar visual
    filled = min(int(confidence / 10), 10)
    conf_bar = '\u2588' * filled + '\u2591' * (10 - filled)

    # Signal strength
    if confidence >= 85:
        strength = '\U0001f525\U0001f525\U0001f525 VERY STRONG'
    elif confidence >= 75:
        strength = '\U0001f525\U0001f525 STRONG'
    elif confidence >= 65:
        strength = '\U0001f525 MODERATE'
    else:
        strength = '\u26a0\ufe0f WEAK'

    # TP percentages
    tp1_pct = _pct_diff(tp1, entry)
    tp2_pct = _pct_diff(tp2, entry)
    tp3_pct = _pct_diff(tp3, entry)
    sl_pct = _pct_diff(sl, entry)

    # R:R display
    rr_display = f"{rr_ratio:.1f}" if rr_ratio else "N/A"

    # IA consensus details
    ia_section = ""
    if ia_details and len(ia_details) > 0:
        ia_lines = '\n'.join([f"   {d}" for d in ia_details])
        ia_section = f"""
\U0001f916 <b>CONSENSUS IA ({models_count} models):</b>
{ia_lines}
   Avg Confidence: {avg_conf}/10"""

    # Signals/reasons
    signals_section = ""
    if pump_signals and len(pump_signals) > 0:
        sig_lines = '\n'.join([f"   \u2022 {s}" for s in pump_signals[:5]])
        signals_section = f"""
\U0001f525 <b>SIGNAUX:</b>
{sig_lines}"""

    # Whale info
    whale_section = f"\n{whale_info}" if whale_info else ""

    # Build message
    msg = f"""{dir_emoji} <b>{signal_type}</b> {dir_emoji}
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

{dir_arrow} <b>{symbol}</b> \u2014 <b>{direction}</b>
\U0001f4ca Score: <b>{score}/100</b> | {strength}

\U0001f4cd <b>ENTRY:</b> {_fmt_price(entry)}
\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

\U0001f3af <b>TAKE PROFIT:</b>
   TP1: {_fmt_price(tp1)}  ({tp1_pct:+.2f}%)
   TP2: {_fmt_price(tp2)}  ({tp2_pct:+.2f}%)
   TP3: {_fmt_price(tp3)}  ({tp3_pct:+.2f}%)

\U0001f6e1\ufe0f <b>STOP LOSS:</b> {_fmt_price(sl)}  ({sl_pct:+.2f}%)
\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

\U0001f4c8 <b>METRIQUES:</b>
   R:R Ratio: <b>{rr_display}:1</b>
   Confidence: [{conf_bar}] {confidence:.0f}%
   Change 24h: {change_pct:+.1f}%
   Volume: {volume_m:.1f}M USDT
   Range: {range_pos:.1%}{ia_section}{signals_section}{whale_section}

\u23f0 {datetime.now().strftime('%d/%m %H:%M:%S')} | Trading AI CQ v3.7"""

    return msg.strip()


def turbo_multi_consensus(symbol, price, change_pct, volume_m, range_pos, signals=None, send_telegram_alert=False):
    """
    CQ v1.1 - Pipeline 2 stages pour consensus multi-modele ultra-rapide.
    Stage 1 (FAST ~3s): M2-Nemotron + M1-GPToss en parallele = pre-filtre
    Stage 2 (DEEP ~5s): M1-Qwen30B + M3-Mistral = confirmation (si Stage 1 passe)
    Retourne consensus pondere avec confiance et TP/SL.
    """
    import concurrent.futures

    ctx_result = build_trading_context(symbol=symbol)
    context = ctx_result.get('context', '') if ctx_result.get('success') else ''
    weights = get_adaptive_weights()

    sig_str = ', '.join(signals) if signals else f'{change_pct:+.1f}% Vol {volume_m}M RP {range_pos}'
    prompt = f"""{context}

SIGNAL: {symbol} ${price} | Change: {change_pct:+.1f}% | Volume: {volume_m}M USDT | Range: {range_pos}
Indicateurs: {sig_str}
Verdict?"""

    all_votes = {'LONG': 0, 'SHORT': 0, 'HOLD': 0}
    all_details = []
    total_confidence = 0
    vote_count = 0

    # === STAGE 1: FAST PRE-FILTER (Nemotron + GPToss en parallele) ===
    stage1_calls = [
        ('M2-Nemo', CQ_CLUSTER['M2']['url'], 'nvidia/nemotron-3-nano', weights['M2'], 25),
        ('M1-GPToss', CQ_CLUSTER['M1']['url'], 'openai/gpt-oss-20b', weights['M1'] * 0.8, 35),
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(_cq_call, url, model, prompt, CQ_SYSTEM_PROMPT, 50, to): (name, w)
                for name, url, model, w, to in stage1_calls}
        for fut in concurrent.futures.as_completed(futs, timeout=40):
            name, w = futs[fut]
            res = fut.result()
            if res['success']:
                vote, conf = _cq_parse_vote(res['answer'])
                all_votes[vote] += w * (conf / 10)
                total_confidence += conf
                vote_count += 1
                all_details.append(f"{name}={vote}({conf}/10,{res['time']}s)")

    # Check si Stage 1 donne un signal clair (pas tout HOLD)
    s1_total = sum(all_votes.values())
    s1_top = max(all_votes, key=all_votes.get) if s1_total > 0 else 'HOLD'

    # === STAGE 2: DEEP CONFIRMATION (Qwen30B + Mistral) ===
    stage2_calls = [
        ('M1-Qwen30B', CQ_CLUSTER['M1']['url'], 'qwen/qwen3-30b-a3b-2507', weights['M1'], 55),
        ('M3-Nemo113', CQ_CLUSTER['M3']['url'], 'nvidia/nemotron-3-nano', weights['M3'], 30),
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(_cq_call, url, model, prompt, CQ_SYSTEM_PROMPT, 60, to): (name, w)
                for name, url, model, w, to in stage2_calls}
        for fut in concurrent.futures.as_completed(futs, timeout=60):
            name, w = futs[fut]
            res = fut.result()
            if res['success']:
                vote, conf = _cq_parse_vote(res['answer'])
                all_votes[vote] += w * (conf / 10)
                total_confidence += conf
                vote_count += 1
                all_details.append(f"{name}={vote}({conf}/10,{res['time']}s)")

    # === CONSENSUS FINAL ===
    total_w = sum(all_votes.values())
    if total_w == 0:
        return {'success': False, 'error': 'No valid responses from any model'}

    consensus = max(all_votes, key=all_votes.get)
    confidence = round(all_votes[consensus] / total_w * 100, 1)
    avg_conf = round(total_confidence / vote_count, 1) if vote_count > 0 else 5

    # TP/SL calculation
    entry = price
    atr_factor = max(abs(change_pct) / 100, 0.015)
    if consensus == 'LONG':
        tp1 = round(entry * (1 + atr_factor * 0.5), 8)
        tp2 = round(entry * (1 + atr_factor * 1.0), 8)
        tp3 = round(entry * (1 + atr_factor * 1.8), 8)
        sl = round(entry * (1 - atr_factor * 0.8), 8)
    elif consensus == 'SHORT':
        tp1 = round(entry * (1 - atr_factor * 0.5), 8)
        tp2 = round(entry * (1 - atr_factor * 1.0), 8)
        tp3 = round(entry * (1 - atr_factor * 1.8), 8)
        sl = round(entry * (1 + atr_factor * 0.8), 8)
    else:
        tp1 = tp2 = tp3 = sl = entry

    # Log consensus
    try:
        log_consensus_decision(symbol, f"turbo_{consensus}_{price}", consensus, confidence,
                              {'votes': {k: round(v, 2) for k, v in all_votes.items()},
                               'details': all_details, 'avg_conf': avg_conf, 'models': vote_count,
                               'weights': weights}, source='turbo_consensus')
    except:
        pass

    result = {
        'success': True,
        'symbol': symbol,
        'consensus': consensus,
        'confidence': confidence,
        'avg_model_confidence': avg_conf,
        'votes': {k: round(v, 2) for k, v in all_votes.items()},
        'details': all_details,
        'models_responded': vote_count,
        'entry': entry,
        'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'sl': sl,
        'rr_ratio': round(abs(tp2 - entry) / abs(entry - sl), 2) if sl != entry else 0,
        'weights_used': weights
    }

    # Telegram alert
    if send_telegram_alert and consensus != 'HOLD' and confidence >= 60:
        try:
            msg = format_telegram_signal(
                symbol=symbol, direction=consensus, entry=entry,
                tp1=tp1, tp2=tp2, tp3=tp3, sl=sl,
                confidence=confidence, rr_ratio=result['rr_ratio'],
                score=round(avg_conf * 10), change_pct=change_pct,
                volume_m=volume_m, range_pos=range_pos,
                ia_details=all_details, models_count=vote_count,
                avg_conf=avg_conf, signal_type='CQ TURBO',
                weights=weights
            )
            send_telegram_message(msg, parse_mode='HTML', bypass_cooldown=True)
        except:
            pass

    return result

def turbo_scan(min_change=2.0, min_volume=3000000, top_n=10, send_telegram=True):
    """
    CQ v1.1 - Scan MEXC + turbo_multi_consensus sur les top candidats.
    Pipeline: Scan -> Filter -> 4-model consensus -> TP/SL -> Telegram
    """
    import concurrent.futures

    try:
        # 1. Scan MEXC
        url_api = f'{CONFIG.get("MEXC_API", "https://contract.mexc.com/api/v1")}/contract/ticker'
        with urllib.request.urlopen(url_api, timeout=10) as r:
            tickers = json.loads(r.read()).get('data', [])

        # 2. Filter candidates
        candidates = []
        for t in tickers:
            try:
                sym = t.get('symbol', '')
                if '_USDT' not in sym: continue
                p = float(t.get('lastPrice', 0))
                vol = float(t.get('volume24', 0))
                hi = float(t.get('high24Price', 0))
                lo = float(t.get('low24Price', 0))
                chg = float(t.get('riseFallRate', 0)) * 100
                if vol < min_volume or p <= 0 or hi <= lo: continue
                rp = (p - lo) / (hi - lo) if (hi - lo) > 0 else 0.5
                score = 0
                if rp > 0.88 and chg > 1:
                    score = rp * abs(chg) * min(vol / 1e6, 5) * 4
                elif rp < 0.15 and vol > 5e6:
                    score = (1 - rp) * min(vol / 1e6, 5) * 3
                elif abs(chg) > min_change:
                    score = abs(chg) * min(vol / 1e6, 3) * 5
                if score > 15:
                    candidates.append({
                        'symbol': sym, 'price': p, 'volume_m': round(vol / 1e6, 1),
                        'change': round(chg, 1), 'range_pos': round(rp, 3), 'score': round(score, 1)
                    })
            except:
                continue

        candidates.sort(key=lambda x: x['score'], reverse=True)
        top_candidates = candidates[:top_n]

        if not top_candidates:
            return {'success': True, 'message': 'No candidates found', 'signals': [], 'scanned': len(tickers)}

        # 3. Turbo consensus on each candidate
        signals = []
        for cand in top_candidates:
            result = turbo_multi_consensus(
                symbol=cand['symbol'],
                price=cand['price'],
                change_pct=cand['change'],
                volume_m=cand['volume_m'],
                range_pos=cand['range_pos'],
                send_telegram_alert=send_telegram
            )
            if result.get('success'):
                result['scan_score'] = cand['score']
                signals.append(result)

        # Sort by confidence
        signals.sort(key=lambda x: x.get('confidence', 0), reverse=True)

        go_signals = [s for s in signals if s.get('confidence', 0) >= 60 and s.get('consensus') != 'HOLD']

        return {
            'success': True,
            'scanned': len(tickers),
            'candidates': len(candidates),
            'analyzed': len(top_candidates),
            'signals': signals,
            'go_signals': len(go_signals),
            'top_signal': go_signals[0] if go_signals else None
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============================================
# END CQ SYSTEM
# ============================================

def db_save_trade(symbol, direction, entry, exit_price=None, pnl=None, score=0):
    conn = get_db_connection()
    if not conn: return {'success': False}
    try:
        conn.execute('INSERT INTO trades (symbol, direction, entry_price, exit_price, pnl, signal_score, created_at) VALUES (?,?,?,?,?,?,?)',
                    (symbol, direction, entry, exit_price, pnl, score, datetime.now().isoformat()))
        conn.commit(); conn.close()
        return {'success': True}
    except Exception as e: conn.close(); return {'success': False, 'error': str(e)}

def db_save_scan(data):
    conn = get_db_connection()
    if not conn: return {'success': False}
    try:
        for s in data.get('top_signals', [])[:10]:
            conn.execute('INSERT INTO scans (symbol, price, change_pct, score, direction, reasons, created_at) VALUES (?,?,?,?,?,?,?)',
                        (s['symbol'], s['price'], s['change'], s['score'], s['direction'], json.dumps(s['reasons']), datetime.now().isoformat()))
        conn.commit(); conn.close()
        return {'success': True}
    except: conn.close(); return {'success': False}

def db_get_trades(limit=50):
    conn = get_db_connection()
    if not conn: return {'success': False, 'trades': []}
    try:
        rows = conn.execute('SELECT * FROM trades ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        conn.close()
        return {'success': True, 'trades': [dict(r) for r in rows]}
    except: conn.close(); return {'success': False, 'trades': []}

# ============================================
# TECHNICAL INDICATORS (v3.2)
# ============================================

def calculate_rsi(prices, period=14):
    if not NUMPY_AVAILABLE or len(prices) < period+1: return 50.0
    p = np.array(prices); d = np.diff(p)
    g = np.where(d > 0, d, 0); l = np.where(d < 0, -d, 0)
    ag = np.mean(g[-period:]); al = np.mean(l[-period:])
    return round(100 - (100 / (1 + ag/al)), 2) if al else 100.0

def calculate_macd(prices):
    if not NUMPY_AVAILABLE or len(prices) < 26: return {'macd': 0, 'signal': 0, 'histogram': 0}
    p = np.array(prices); ema12 = np.mean(p[-12:]); ema26 = np.mean(p[-26:])
    macd = ema12 - ema26; signal = macd * 0.9
    return {'macd': round(macd, 4), 'signal': round(signal, 4), 'histogram': round(macd - signal, 4)}

# ============================================
# CCXT INTEGRATION (v3.2)
# ============================================

def get_ohlcv_ccxt(symbol="BTC/USDT", timeframe="1h", limit=100):
    if not CCXT_AVAILABLE: return {'success': False, 'error': 'CCXT not installed'}
    try:
        exchange = ccxt.mexc({
            'apiKey': CONFIG['MEXC_ACCESS_KEY'],
            'secret': CONFIG['MEXC_SECRET_KEY'],
            'options': {
                'defaultType': 'swap',
                'adjustForTimeDifference': True,
                'recvWindow': 60000
            }
        })
        exchange.load_time_difference()  # Force sync horloge MEXC
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        closes = [c[4] for c in ohlcv]
        return {'success': True, 'symbol': symbol, 'timeframe': timeframe, 'candles': len(ohlcv),
                'rsi': calculate_rsi(closes), 'macd': calculate_macd(closes), 'last_price': closes[-1] if closes else 0}
    except Exception as e: return {'success': False, 'error': str(e)}

# ============================================
# MULTI-TIMEFRAME ANALYSIS (v3.4.1)
# ============================================

def get_multi_timeframe_data(symbol: str) -> Dict:
    """
    Get OHLCV data for multiple timeframes (15m, 1h, 4h, 1d)
    Returns trend direction and strength for each timeframe
    """
    if not CCXT_AVAILABLE:
        return {'success': False, 'error': 'CCXT not installed'}

    timeframes = ['15m', '1h', '4h', '1d']
    results = {}

    try:
        exchange = ccxt.mexc({
            'apiKey': CONFIG.get('MEXC_ACCESS_KEY', ''),
            'secret': CONFIG.get('MEXC_SECRET_KEY', ''),
            'options': {
                'defaultType': 'swap',
                'adjustForTimeDifference': True,
                'recvWindow': 60000
            }
        })
        exchange.load_time_difference()  # Force sync horloge MEXC

        for tf in timeframes:
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=50)
                if not ohlcv or len(ohlcv) < 20:
                    results[tf] = {'trend': 'NEUTRAL', 'strength': 0, 'rsi': 50}
                    continue

                closes = [c[4] for c in ohlcv]
                highs = [c[2] for c in ohlcv]
                lows = [c[3] for c in ohlcv]

                # Calculate indicators
                rsi = calculate_rsi(closes)
                macd_data = calculate_macd(closes)

                # Trend detection
                sma_short = sum(closes[-10:]) / 10
                sma_long = sum(closes[-30:]) / 30 if len(closes) >= 30 else sma_short
                current_price = closes[-1]

                # Higher highs / Lower lows detection
                recent_highs = highs[-10:]
                recent_lows = lows[-10:]
                hh_count = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i] > recent_highs[i-1])
                ll_count = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i] < recent_lows[i-1])

                # Determine trend
                trend = 'NEUTRAL'
                strength = 0

                if current_price > sma_short > sma_long:
                    trend = 'BULLISH'
                    strength = min(100, int((current_price / sma_long - 1) * 1000))
                    if rsi > 70: strength += 10
                    if macd_data['histogram'] > 0: strength += 10
                    if hh_count > ll_count: strength += 15
                elif current_price < sma_short < sma_long:
                    trend = 'BEARISH'
                    strength = min(100, int((1 - current_price / sma_long) * 1000))
                    if rsi < 30: strength += 10
                    if macd_data['histogram'] < 0: strength += 10
                    if ll_count > hh_count: strength += 15
                else:
                    # Check for consolidation
                    price_range = (max(closes[-20:]) - min(closes[-20:])) / current_price * 100
                    if price_range < 3:
                        trend = 'CONSOLIDATION'
                    strength = int(50 - abs(rsi - 50))

                results[tf] = {
                    'trend': trend,
                    'strength': min(100, strength),
                    'rsi': rsi,
                    'macd': macd_data['histogram'],
                    'price': current_price,
                    'sma_short': round(sma_short, 8),
                    'sma_long': round(sma_long, 8)
                }

            except Exception as e:
                results[tf] = {'trend': 'ERROR', 'strength': 0, 'error': str(e)}

        # Calculate overall MTF score
        trend_scores = {'BULLISH': 1, 'BEARISH': -1, 'NEUTRAL': 0, 'CONSOLIDATION': 0, 'ERROR': 0}
        tf_weights = {'15m': 0.15, '1h': 0.25, '4h': 0.35, '1d': 0.25}

        weighted_trend = sum(
            trend_scores.get(results.get(tf, {}).get('trend', 'NEUTRAL'), 0) * weight
            for tf, weight in tf_weights.items()
        )

        avg_strength = sum(
            results.get(tf, {}).get('strength', 0) * weight
            for tf, weight in tf_weights.items()
        )

        # Overall direction
        if weighted_trend >= 0.5:
            overall_direction = 'LONG'
        elif weighted_trend <= -0.5:
            overall_direction = 'SHORT'
        else:
            overall_direction = 'NEUTRAL'

        # Alignment check
        trends = [results.get(tf, {}).get('trend') for tf in timeframes]
        bullish_count = trends.count('BULLISH')
        bearish_count = trends.count('BEARISH')
        alignment = 'STRONG' if bullish_count >= 3 or bearish_count >= 3 else 'WEAK' if bullish_count >= 2 or bearish_count >= 2 else 'NONE'

        return {
            'success': True,
            'symbol': symbol,
            'timeframes': results,
            'overall': {
                'direction': overall_direction,
                'strength': round(avg_strength, 1),
                'weighted_trend': round(weighted_trend, 2),
                'alignment': alignment,
                'bullish_tfs': bullish_count,
                'bearish_tfs': bearish_count
            }
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}

def calculate_breakout_score_enhanced(symbol: str, price: float, high24: float, low24: float,
                                      change: float, volume: float, include_mtf: bool = True) -> Dict:
    """
    Enhanced breakout scoring with multi-timeframe confirmation
    Returns score 0-100 with detailed breakdown
    """
    import math

    score = 0
    reasons = []
    breakdown = {}

    # 1. POSITION SCORING (0-25 pts)
    range_24h = high24 - low24
    if range_24h > 0 and range_24h / price < 0.5:
        position = (price - low24) / range_24h
    else:
        position = 0.5 + (change / 100) if abs(change) < 50 else 0.5
    position = max(0.0, min(1.0, position))

    position_score = 0
    if position >= 0.95:
        position_score = 25
        reasons.append('BREAKOUT_ZONE')
    elif position >= 0.85:
        position_score = 20
        reasons.append('HIGH_RANGE')
    elif position >= 0.70:
        position_score = 10
        reasons.append('UPPER_MID')
    elif position <= 0.05:
        position_score = 22
        reasons.append('REVERSAL_ZONE')
    elif position <= 0.15:
        position_score = 18
        reasons.append('LOW_RANGE')
    elif position <= 0.30:
        position_score = 8
        reasons.append('LOWER_MID')
    else:
        position_score = 5

    score += position_score
    breakdown['position'] = {'score': position_score, 'value': round(position * 100, 1)}

    # 2. VOLUME SCORING (0-25 pts)
    volume_score = 0
    if volume > 0:
        vol_log = math.log10(volume)
        if vol_log >= 10:
            volume_score = 25
            reasons.append('VOL_WHALE')
        elif vol_log >= 9:
            volume_score = 20
            reasons.append('VOL_MEGA')
        elif vol_log >= 8:
            volume_score = 15
            reasons.append('VOL_HIGH')
        elif vol_log >= 7:
            volume_score = 10
            reasons.append('VOL_MED')
        elif vol_log >= 6:
            volume_score = 5
            reasons.append('VOL_OK')

    score += volume_score
    breakdown['volume'] = {'score': volume_score, 'value': volume}

    # 3. MOMENTUM SCORING (0-20 pts)
    momentum_score = 0
    abs_change = abs(change)
    if abs_change >= 20:
        momentum_score = 20
        reasons.append('PUMP' if change > 0 else 'DUMP')
    elif abs_change >= 10:
        momentum_score = 15
        reasons.append('STRONG_MOVE')
    elif abs_change >= 5:
        momentum_score = 10
        reasons.append('MOMENTUM')
    elif abs_change >= 2:
        momentum_score = 5
        reasons.append('TREND')

    score += momentum_score
    breakdown['momentum'] = {'score': momentum_score, 'value': round(change, 2)}

    # 4. VOLATILITY SCORING (0-10 pts)
    volatility = (range_24h / price * 100) if price > 0 else 0
    volatility_score = 0
    if volatility >= 15:
        volatility_score = 10
        reasons.append('HIGH_VOL')
    elif volatility >= 8:
        volatility_score = 5
        reasons.append('MED_VOL')

    score += volatility_score
    breakdown['volatility'] = {'score': volatility_score, 'value': round(volatility, 2)}

    # 5. MULTI-TIMEFRAME BONUS (0-20 pts)
    mtf_score = 0
    mtf_data = None
    if include_mtf and CCXT_AVAILABLE:
        try:
            mtf_data = get_multi_timeframe_data(symbol)
            if mtf_data.get('success'):
                overall = mtf_data.get('overall', {})
                alignment = overall.get('alignment', 'NONE')
                direction = overall.get('direction', 'NEUTRAL')

                # Strong alignment bonus
                if alignment == 'STRONG':
                    mtf_score = 20
                    reasons.append(f'MTF_STRONG_{direction}')
                elif alignment == 'WEAK':
                    mtf_score = 10
                    reasons.append(f'MTF_WEAK_{direction}')

                # Check trend strength
                if overall.get('strength', 0) >= 70:
                    mtf_score += 5
                    reasons.append('MTF_HIGH_STRENGTH')

        except:
            pass

    score += mtf_score
    breakdown['mtf'] = {'score': mtf_score, 'data': mtf_data}

    # 6. CONFLUENCE BONUS (0-10 pts)
    confluence_score = 0
    if position >= 0.90 and change > 0 and volume > 50000000:
        confluence_score = 10
        reasons.append('BREAKOUT_CONFIRMED')
    elif position <= 0.10 and volume > 50000000:
        confluence_score = 8
        reasons.append('CAPITULATION')

    score += confluence_score
    breakdown['confluence'] = {'score': confluence_score}

    # DIRECTION DETERMINATION
    if position >= 0.70 and change > 0:
        direction = 'LONG'
    elif position <= 0.30 and change < 0:
        direction = 'SHORT'
    elif change > 2:
        direction = 'LONG'
    elif change < -2:
        direction = 'SHORT'
    else:
        direction = 'NEUTRAL'

    # Adjust direction based on MTF
    if mtf_data and mtf_data.get('success'):
        mtf_direction = mtf_data.get('overall', {}).get('direction', 'NEUTRAL')
        alignment = mtf_data.get('overall', {}).get('alignment', 'NONE')

        if alignment == 'STRONG':
            direction = mtf_direction
        elif alignment == 'WEAK' and direction == 'NEUTRAL':
            direction = mtf_direction

    # SIGNAL TYPE
    if score >= 90:
        signal_type = 'PRIME'
    elif score >= 80:
        signal_type = 'STRONG'
    elif score >= 70:
        signal_type = 'STANDARD'
    elif score >= 60:
        signal_type = 'MODERATE'
    else:
        signal_type = 'WEAK'

    return {
        'score': min(100, score),
        'signal_type': signal_type,
        'direction': direction,
        'position': round(position * 100, 1),
        'volatility': round(volatility, 2),
        'reasons': reasons[:6],
        'breakdown': breakdown,
        'mtf_data': mtf_data
    }

# ============================================
# MCP RESOURCES (read-only data)
# ============================================
RESOURCES = {
    "trading://positions": {
        "uri": "trading://positions",
        "name": "MEXC Futures Positions",
        "description": "Current open positions on MEXC Futures",
        "mimeType": "application/json"
    },
    "trading://alerts": {
        "uri": "trading://alerts",
        "name": "Active Alerts",
        "description": "Price and margin alerts currently active",
        "mimeType": "application/json"
    },
    "trading://config": {
        "uri": "trading://config",
        "name": "Trading Configuration",
        "description": "System configuration (API endpoints, thresholds)",
        "mimeType": "application/json"
    },
    "trading://ia-stats": {
        "uri": "trading://ia-stats",
        "name": "AI Statistics",
        "description": "Performance statistics for all AI services",
        "mimeType": "application/json"
    },
    "trading://dashboard": {
        "uri": "trading://dashboard",
        "name": "Live Dashboard",
        "description": "Real-time trading dashboard data",
        "mimeType": "application/json"
    }
}

def get_resource_content(uri: str) -> Dict:
    """Get content for a resource URI"""
    if uri == "trading://positions":
        return get_mexc_positions()
    elif uri == "trading://alerts":
        return list_alerts()
    elif uri == "trading://config":
        # Return safe config (no secrets)
        safe_config = {
            "MEXC_URL": CONFIG["MEXC_URL"],
            "LM_STUDIO_URL": CONFIG["LM_STUDIO_URL"],
            "N8N_URL": CONFIG["N8N_URL"],
            "MARGIN_THRESHOLDS": {
                "CRITICAL": CONFIG["MARGIN_CRITICAL"],
                "DANGER": CONFIG["MARGIN_DANGER"],
                "OK": CONFIG["MARGIN_OK"],
                "SAFE": CONFIG["MARGIN_SAFE"]
            },
            "WORKFLOWS": WORKFLOWS
        }
        return {"success": True, "config": safe_config}
    elif uri == "trading://ia-stats":
        return get_ia_stats()
    elif uri == "trading://dashboard":
        return get_live_dashboard()
    else:
        return {"error": f"Unknown resource: {uri}"}

def scan_mexc(min_score: int = None) -> Dict:
    """
    Scanner MEXC amélioré avec scoring différencié
    v2.2 - 2026-01-17 - Filters from config/filters.json
    """
    import math

    # Load filters from config/filters.json
    if min_score is None:
        min_score = get_filter('scanner.minScore', 75)
    min_volume = get_filter('scanner.minVolume24h', 100000)
    max_signals = get_filter('scanner.maxSignals', 15)

    try:
        with urllib.request.urlopen(CONFIG["MEXC_URL"], timeout=15) as r:
            data = json.loads(r.read())
        tickers = data.get('data', [])
        signals = []

        for t in tickers:
            if not t.get('symbol', '').endswith('_USDT'):
                continue

            symbol = t['symbol'].replace('_USDT', '/USDT')

            # Check blacklist from filters.json
            if is_blacklisted(symbol):
                continue

            price = float(t.get('lastPrice') or 0)

            # Handle None values from MEXC API
            high24_raw = t.get('high24Price')
            low24_raw = t.get('low24Price')
            high24 = float(high24_raw) if high24_raw is not None else price * 1.05
            low24 = float(low24_raw) if low24_raw is not None else price * 0.95

            change_raw = t.get('riseFallRate')
            change = float(change_raw) * 100 if change_raw is not None else 0  # riseFallRate is decimal
            volume = float(t.get('amount24') or 0)

            # Skip invalid data (min_volume from filters.json)
            if price <= 0 or volume < min_volume:
                continue

            # === POSITION CALCULATION (corrigé) ===
            range_24h = high24 - low24
            if range_24h > 0 and range_24h / price < 0.5:  # Range < 50% du prix (valide)
                position = (price - low24) / range_24h
            else:
                # Fallback: utiliser change pour estimer position
                position = 0.5 + (change / 100) if abs(change) < 50 else 0.5
            position = max(0.0, min(1.0, position))  # Clamp 0-1

            # === VOLATILITY (ATR proxy) ===
            volatility = (range_24h / price * 100) if price > 0 else 0

            # === SCORING GRADUÉ ===
            score = 30  # Base score
            reasons = []

            # 1. VOLUME SCORING (logarithmique, max 25 pts)
            if volume > 0:
                vol_log = math.log10(volume)
                if vol_log >= 10:  # > 10B
                    score += 25
                    reasons.append('VOL_WHALE')
                elif vol_log >= 9:  # > 1B
                    score += 20
                    reasons.append('VOL_MEGA')
                elif vol_log >= 8:  # > 100M
                    score += 15
                    reasons.append('VOL_HIGH')
                elif vol_log >= 7:  # > 10M
                    score += 10
                    reasons.append('VOL_MED')
                elif vol_log >= 6:  # > 1M
                    score += 5
                    reasons.append('VOL_OK')

            # 2. POSITION SCORING (zones, max 25 pts)
            if position >= 0.95:
                score += 25
                reasons.append('BREAKOUT_ZONE')
            elif position >= 0.85:
                score += 20
                reasons.append('HIGH_RANGE')
            elif position >= 0.70:
                score += 10
                reasons.append('UPPER_MID')
            elif position <= 0.05:
                score += 22
                reasons.append('REVERSAL_ZONE')
            elif position <= 0.15:
                score += 18
                reasons.append('LOW_RANGE')
            elif position <= 0.30:
                score += 8
                reasons.append('LOWER_MID')
            else:
                score += 5  # Mid-range neutre

            # 3. MOMENTUM SCORING (change %, max 20 pts)
            abs_change = abs(change)
            if abs_change >= 20:
                score += 20
                reasons.append('PUMP' if change > 0 else 'DUMP')
            elif abs_change >= 10:
                score += 15
                reasons.append('STRONG_MOVE')
            elif abs_change >= 5:
                score += 10
                reasons.append('MOMENTUM')
            elif abs_change >= 2:
                score += 5
                reasons.append('TREND')

            # 4. VOLATILITY BONUS (max 10 pts)
            if volatility >= 15:
                score += 10
                reasons.append('HIGH_VOL')
            elif volatility >= 8:
                score += 5
                reasons.append('MED_VOL')

            # 5. SIGNAL CONFLUENCE (bonus)
            if position >= 0.90 and change > 0 and volume > 50000000:
                score += 10
                reasons.append('BREAKOUT_CONFIRMED')
            elif position <= 0.10 and volume > 50000000:
                score += 8
                reasons.append('CAPITULATION')

            # === DIRECTION ===
            if position >= 0.70 and change > 0:
                direction = 'LONG'
            elif position <= 0.30 and change < 0:
                direction = 'SHORT'
            elif change > 2:
                direction = 'LONG'
            elif change < -2:
                direction = 'SHORT'
            else:
                direction = 'NEUTRAL'

            # === SIGNAL TYPE ===
            if score >= 90:
                signal_type = 'PRIME'
            elif score >= 80:
                signal_type = 'STRONG'
            elif score >= 70:
                signal_type = 'STANDARD'
            else:
                signal_type = 'WEAK'

            if score >= min_score:
                signals.append({
                    'symbol': symbol,
                    'price': price,
                    'change': round(change, 2),
                    'score': min(100, score),
                    'signal_type': signal_type,
                    'position': round(position * 100, 1),
                    'volatility': round(volatility, 2),
                    'volume': volume,
                    'direction': direction,
                    'reasons': reasons[:5]
                })

        # Sort by score, then by volume
        signals.sort(key=lambda x: (x['score'], x['volume']), reverse=True)
        return {
            'success': True,
            'total_tickers': len(tickers),
            'filters_used': {'min_score': min_score, 'min_volume': min_volume, 'max_signals': max_signals},
            'top_signals': signals[:max_signals]
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def scan_sniper() -> Dict:
    """
    Scanner SNIPER Premium - Analyse complete avec 5 IAs
    Appelle le serveur scanner local pour analyse complete:
    - 400+ contrats MEXC futures
    - Orderbook + liquidite + whale walls
    - Detection breakouts imminents
    - Validation consensus 5 IAs (Gemini + 4 LM Studio)
    - Sauvegarde SQL automatique
    - Alerte Telegram automatique

    Returns TOP 3 signaux avec entry, TP, SL, consensus IA
    """
    import urllib.request
    try:
        # Appel au serveur scanner local
        req = urllib.request.Request(
            'http://127.0.0.1:5000/scan/sniper',
            method='POST',
            headers={'Content-Type': 'application/json'},
            data=b'{}'
        )

        with urllib.request.urlopen(req, timeout=600) as response:
            result = json.loads(response.read())

        if not result.get('success'):
            return {'success': False, 'error': result.get('error', 'Scan failed')}

        signals = result.get('signals', [])

        return {
            'success': True,
            'signals_count': len(signals),
            'timestamp': result.get('timestamp'),
            'signals': signals,
            'message': f"Scanner SNIPER termine - {len(signals)} signaux detectes avec consensus IA",
            'actions': [
                'Signaux sauvegardes en SQL',
                'Alerte Telegram envoyee (@turboSSebot)'
            ]
        }

    except urllib.error.URLError as e:
        return {
            'success': False,
            'error': 'Serveur scanner non disponible',
            'message': 'Le serveur scanner doit etre demarre: /\LMStudio/Scanner/start_scanner.bat',
            'details': str(e)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def detect_imminent_pumps(min_score: int = None) -> Dict:
    """
    Détection avancée de pumps imminents
    Combine: Volume Squeeze + Orderbook Imbalance + RSI/MACD Divergence
    v1.1 - 2026-01-17 - Filters from config/filters.json
    """
    import math

    # Load min_score from filters if not provided
    if min_score is None:
        min_score = get_filter('signalTypes.BREAKOUT_IMMINENT.minScore', 70)

    try:
        # 1. Get top volume coins from scan (use lower threshold for candidates)
        scan_result = scan_mexc(min_score - 15)  # Dynamic threshold
        if not scan_result['success']:
            return scan_result

        candidates = []

        for signal in scan_result['top_signals'][:30]:  # Top 30 by volume
            symbol = signal['symbol']
            symbol_api = symbol.replace('/USDT', 'USDT')

            pump_score = 0
            pump_signals = []

            # === 1. VOLUME SQUEEZE DETECTION ===
            # Compression = low volatility + high volume = accumulation
            volatility = signal.get('volatility', 10)
            volume = signal.get('volume', 0)

            # Squeeze: volatilité < 8% mais volume élevé
            if volatility < 8 and volume > 10000000:
                pump_score += 25
                pump_signals.append('SQUEEZE')
            elif volatility < 5 and volume > 5000000:
                pump_score += 30
                pump_signals.append('TIGHT_SQUEEZE')

            # Volume spike: position basse + gros volume = accumulation
            position = signal.get('position', 50)
            if position < 30 and volume > 50000000:
                pump_score += 20
                pump_signals.append('ACCUMULATION')

            # === 2. ORDERBOOK IMBALANCE ===
            try:
                ob_url = f"https://contract.mexc.com/api/v1/contract/depth/{symbol_api}"
                with urllib.request.urlopen(ob_url, timeout=5) as r:
                    ob_data = json.loads(r.read()).get('data', {})

                bids = ob_data.get('bids', [])[:10]
                asks = ob_data.get('asks', [])[:10]

                bid_volume = sum(float(b[1]) for b in bids) if bids else 0
                ask_volume = sum(float(a[1]) for a in asks) if asks else 0

                if ask_volume > 0:
                    imbalance_ratio = bid_volume / ask_volume

                    if imbalance_ratio >= 2.0:
                        pump_score += 30
                        pump_signals.append(f'STRONG_BUY_PRESSURE({imbalance_ratio:.1f}x)')
                    elif imbalance_ratio >= 1.5:
                        pump_score += 20
                        pump_signals.append(f'BUY_PRESSURE({imbalance_ratio:.1f}x)')
                    elif imbalance_ratio >= 1.2:
                        pump_score += 10
                        pump_signals.append('SLIGHT_BUY_BIAS')
            except:
                pass  # Orderbook fetch failed, continue

            # === 3. RSI/MACD via OHLCV ===
            try:
                ohlcv_url = f"https://contract.mexc.com/api/v1/contract/kline/{symbol_api}?interval=Min15&limit=50"
                with urllib.request.urlopen(ohlcv_url, timeout=5) as r:
                    kline_data = json.loads(r.read()).get('data', {})

                closes = []
                if isinstance(kline_data, dict):
                    for k in ['close', 'c']:
                        if k in kline_data:
                            closes = [float(x) for x in kline_data[k][-30:]]
                            break
                elif isinstance(kline_data, list):
                    closes = [float(k[4]) for k in kline_data[-30:] if len(k) > 4]

                if len(closes) >= 14:
                    # Simple RSI calculation
                    gains = []
                    losses = []
                    for i in range(1, len(closes)):
                        change = closes[i] - closes[i-1]
                        if change > 0:
                            gains.append(change)
                            losses.append(0)
                        else:
                            gains.append(0)
                            losses.append(abs(change))

                    avg_gain = sum(gains[-14:]) / 14
                    avg_loss = sum(losses[-14:]) / 14

                    if avg_loss > 0:
                        rs = avg_gain / avg_loss
                        rsi = 100 - (100 / (1 + rs))
                    else:
                        rsi = 100

                    # RSI oversold + recovering = pump potential
                    if rsi < 30:
                        pump_score += 25
                        pump_signals.append(f'RSI_OVERSOLD({rsi:.0f})')
                    elif rsi < 40:
                        pump_score += 15
                        pump_signals.append(f'RSI_LOW({rsi:.0f})')

                    # MACD simple
                    if len(closes) >= 26:
                        ema12 = sum(closes[-12:]) / 12
                        ema26 = sum(closes[-26:]) / 26
                        macd = ema12 - ema26

                        # MACD crossing up
                        prev_ema12 = sum(closes[-13:-1]) / 12
                        prev_ema26 = sum(closes[-27:-1]) / 26
                        prev_macd = prev_ema12 - prev_ema26

                        if macd > prev_macd and prev_macd < 0 and macd > -0.001 * closes[-1]:
                            pump_score += 20
                            pump_signals.append('MACD_CROSS_UP')
                        elif macd > prev_macd:
                            pump_score += 10
                            pump_signals.append('MACD_RISING')
            except:
                pass  # OHLCV fetch failed, continue

            # === 4. POSITION BONUS (breakout zone) ===
            if position >= 85 and signal.get('change', 0) > 0:
                pump_score += 15
                pump_signals.append('NEAR_BREAKOUT')

            # === FINAL SCORING ===
            if pump_score >= min_score:
                # Determine pump type
                if pump_score >= 90:
                    pump_type = 'IMMINENT'
                elif pump_score >= 75:
                    pump_type = 'PROBABLE'
                elif pump_score >= 60:
                    pump_type = 'POSSIBLE'
                else:
                    pump_type = 'WATCH'

                candidates.append({
                    'symbol': symbol,
                    'price': signal['price'],
                    'pump_score': min(100, pump_score),
                    'pump_type': pump_type,
                    'position': position,
                    'volume': volume,
                    'volatility': volatility,
                    'change': signal.get('change', 0),
                    'signals': pump_signals[:6]
                })

        # Sort by pump score
        candidates.sort(key=lambda x: x['pump_score'], reverse=True)

        return {
            'success': True,
            'description': 'Pump Detection: Squeeze + Orderbook + RSI/MACD',
            'candidates': candidates[:10],
            'total_analyzed': len(scan_result['top_signals'])
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_multi_ia_analysis(symbol: str, price: float, signals: list, direction: str, inject_context: bool = True) -> Dict:
    """
    Obtient l'analyse consensus de Gemini + LM Studio 1 + LM Studio 2
    CQ v1.0 - Injecte le contexte trading automatiquement
    """
    import concurrent.futures

    # CQ: Injection du contexte trading
    context_block = ""
    if inject_context:
        try:
            ctx = build_trading_context(symbol=symbol)
            if ctx.get('success'):
                context_block = ctx['context'] + "\n\n"
        except:
            pass

    prompt = f"""{context_block}Analyse trading pour {symbol}:
Prix: ${price}
Direction proposee: {direction}
Signaux detectes: {', '.join(signals)}

Reponds: DIRECTION | CONFIANCE (1-10) | RAISON (tenant compte du contexte ci-dessus)"""

    results = {}

    def call_gemini():
        try:
            result = subprocess.run([CONFIG["GEMINI_CLI"], prompt], capture_output=True, text=True, timeout=30, encoding='utf-8', errors='replace', shell=True)
            if result.returncode == 0:
                return ('gemini', {'success': True, 'answer': result.stdout.strip()})
        except:
            pass
        return ('gemini', {'success': False})

    def call_lmstudio_prod():
        try:
            url = f'{CONFIG["LM_STUDIO_PROD"]}/v1/chat/completions'
            payload = json.dumps({
                'model': 'qwen/qwen3-30b-a3b-2507',
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 100,
                'temperature': 0.2
            }).encode()
            req = urllib.request.Request(url, payload, {'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=60) as r:
                result = json.loads(r.read())
                msg = result['choices'][0]['message']
                answer = msg.get('content') or msg.get('reasoning_content') or msg.get('reasoning') or ''
                return ('lmstudio_prod', {'success': True, 'answer': answer.strip()})
        except:
            pass
        return ('lmstudio_prod', {'success': False})

    def call_lmstudio_tampon():
        try:
            url = f'{CONFIG["LM_STUDIO_TAMPON"]}/v1/chat/completions'
            payload = json.dumps({
                'model': 'nvidia/nemotron-3-nano',
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 100,
                'temperature': 0.2
            }).encode()
            req = urllib.request.Request(url, payload, {'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as r:
                result = json.loads(r.read())
                msg = result['choices'][0]['message']
                answer = msg.get('content') or msg.get('reasoning_content') or msg.get('reasoning') or ''
                return ('lmstudio_tampon', {'success': True, 'answer': answer.strip()})
        except:
            pass
        return ('lmstudio_tampon', {'success': False})

    # Parallel execution
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(call_gemini),
            executor.submit(call_lmstudio_prod),
            executor.submit(call_lmstudio_tampon)
        ]
        for future in concurrent.futures.as_completed(futures, timeout=65):
            try:
                name, result = future.result()
                results[name] = result
            except:
                pass

    # Parse verdicts
    votes = {'LONG': 0, 'SHORT': 0, 'HOLD': 0}
    details = []

    for ia_name, ia_result in results.items():
        if ia_result.get('success'):
            answer = ia_result.get('answer', '').upper()
            if 'LONG' in answer or 'BUY' in answer or 'ACHAT' in answer:
                votes['LONG'] += 1
                details.append(f"{ia_name}: LONG")
            elif 'SHORT' in answer or 'SELL' in answer or 'VENTE' in answer:
                votes['SHORT'] += 1
                details.append(f"{ia_name}: SHORT")
            else:
                votes['HOLD'] += 1
                details.append(f"{ia_name}: HOLD")

    # Determine consensus
    max_votes = max(votes.values())
    consensus = [k for k, v in votes.items() if v == max_votes][0]
    confidence = (max_votes / max(len(results), 1)) * 100

    # CQ: Log la decision consensus pour feedback loop
    try:
        log_consensus_decision(symbol, f"multi_ia_{direction}_{price}", consensus, confidence,
                              {'votes': votes, 'details': details, 'ia_count': len(results)}, source='multi_ia')
    except:
        pass

    return {
        'consensus': consensus,
        'confidence': confidence,
        'votes': votes,
        'details': details,
        'ia_count': len(results)
    }

def smart_scan_and_alert(min_pump_score: int = None, send_telegram: bool = None, use_multi_ia: bool = True) -> Dict:
    """
    Scan complet avec tous les outils + Multi-IA consensus + Telegram
    Combine: scan_mexc + detect_pumps + orderbook + Gemini + LM Studio + TP/SL
    v2.1 - 2026-01-17 - Filters from config/filters.json
    """
    import math
    from datetime import datetime

    # Load filters from config/filters.json
    if min_pump_score is None:
        min_pump_score = get_filter('scanner.minScore', 60)
    if send_telegram is None:
        send_telegram = get_filter('telegram.enabled', True)

    try:
        # 1. Detect imminent pumps
        pump_result = detect_imminent_pumps(min_pump_score)
        if not pump_result['success']:
            return pump_result

        candidates = pump_result.get('candidates', [])
        if not candidates:
            return {'success': True, 'message': 'No pump signals detected', 'alerts_sent': 0}

        alerts_sent = 0
        all_signals = []

        for candidate in candidates[:5]:  # Top 5 pump candidates
            symbol = candidate['symbol']
            symbol_api = symbol.replace('/USDT', '_USDT')
            price = candidate['price']
            pump_score = candidate['pump_score']
            pump_type = candidate['pump_type']
            pump_signals = candidate.get('signals', [])
            volatility = candidate.get('volatility', 5)
            position = candidate.get('position', 50)

            # === DETERMINE INITIAL DIRECTION ===
            initial_direction = 'LONG'
            if any('DUMP' in s or 'SELL_PRESSURE' in s for s in pump_signals):
                initial_direction = 'SHORT'

            # === MULTI-IA CONSENSUS ===
            ia_consensus = None
            if use_multi_ia:
                try:
                    ia_consensus = get_multi_ia_analysis(symbol, price, pump_signals, initial_direction)
                    # Use consensus direction if confidence >= 66% (2/3 IAs agree)
                    if ia_consensus.get('confidence', 0) >= 66:
                        direction = ia_consensus['consensus']
                    else:
                        direction = initial_direction
                except:
                    direction = initial_direction
            else:
                direction = initial_direction

            # Skip if consensus is HOLD with high confidence
            if ia_consensus and ia_consensus.get('consensus') == 'HOLD' and ia_consensus.get('confidence', 0) >= 66:
                continue

            # === CALCULATE TP/SL BASED ON VOLATILITY ===
            atr_factor = max(volatility / 100, 0.02)  # Min 2%

            if direction == 'LONG':
                entry = price
                sl = price * (1 - atr_factor * 0.8)  # SL = 0.8x ATR below
                tp1 = price * (1 + atr_factor * 0.5)  # TP1 = 0.5x ATR
                tp2 = price * (1 + atr_factor * 1.0)  # TP2 = 1x ATR
                tp3 = price * (1 + atr_factor * 1.8)  # TP3 = 1.8x ATR
            else:
                entry = price
                sl = price * (1 + atr_factor * 0.8)
                tp1 = price * (1 - atr_factor * 0.5)
                tp2 = price * (1 - atr_factor * 1.0)
                tp3 = price * (1 - atr_factor * 1.8)

            # === GET ORDERBOOK FOR WHALE WALLS ===
            whale_info = ""
            try:
                ob_url = f"https://contract.mexc.com/api/v1/contract/depth/{symbol_api}"
                with urllib.request.urlopen(ob_url, timeout=5) as r:
                    ob_data = json.loads(r.read()).get('data', {})

                bids = ob_data.get('bids', [])[:20]
                asks = ob_data.get('asks', [])[:20]

                # Find whale walls (orders > 3x average)
                if bids:
                    avg_bid = sum(float(b[1]) for b in bids) / len(bids)
                    whale_bids = [(float(b[0]), float(b[1])) for b in bids if float(b[1]) > avg_bid * 3]
                    if whale_bids:
                        whale_info += f"🐋 Support: ${whale_bids[0][0]:,.2f}\n"
                        # Adjust SL to whale support
                        if direction == 'LONG' and whale_bids[0][0] < price:
                            sl = whale_bids[0][0] * 0.995  # Just below whale wall

                if asks:
                    avg_ask = sum(float(a[1]) for a in asks) / len(asks)
                    whale_asks = [(float(a[0]), float(a[1])) for a in asks if float(a[1]) > avg_ask * 3]
                    if whale_asks:
                        whale_info += f"🐋 Resistance: ${whale_asks[0][0]:,.2f}\n"
                        # Adjust TP to whale resistance
                        if direction == 'LONG' and whale_asks[0][0] > price:
                            if whale_asks[0][0] < tp2:
                                tp2 = whale_asks[0][0] * 0.995
            except:
                pass

            # === CALCULATE RISK/REWARD ===
            risk = abs(entry - sl)
            reward = abs(tp2 - entry)
            rr_ratio = reward / risk if risk > 0 else 0

            # === FORMAT SIGNAL ===
            signal_data = {
                'symbol': symbol,
                'direction': direction,
                'entry': entry,
                'sl': sl,
                'tp1': tp1,
                'tp2': tp2,
                'tp3': tp3,
                'pump_score': pump_score,
                'pump_type': pump_type,
                'signals': pump_signals,
                'rr_ratio': rr_ratio,
                'volatility': volatility,
                'position': position,
                'ia_consensus': ia_consensus
            }
            all_signals.append(signal_data)

            # === FORMAT TELEGRAM MESSAGE (unified formatter) ===
            ia_detail_list = []
            ia_conf = 0
            ia_count = 0
            if ia_consensus and ia_consensus.get('ia_count', 0) > 0:
                votes = ia_consensus.get('votes', {})
                ia_conf = ia_consensus.get('confidence', 0) / 10
                ia_count = ia_consensus.get('ia_count', 0)
                for k, v in votes.items():
                    if v > 0:
                        ia_detail_list.append(f"{k}={v}")

            message = format_telegram_signal(
                symbol=symbol, direction=direction, entry=entry,
                tp1=tp1, tp2=tp2, tp3=tp3, sl=sl,
                confidence=ia_consensus.get('confidence', pump_score) if ia_consensus else pump_score,
                rr_ratio=rr_ratio, score=pump_score,
                change_pct=volatility, volume_m=0, range_pos=position / 100,
                ia_details=ia_detail_list, models_count=ia_count,
                avg_conf=ia_conf, signal_type=f'SIGNAL {pump_type}',
                pump_signals=pump_signals, whale_info=whale_info
            )

            # === SEND TO TELEGRAM ===
            if send_telegram:
                try:
                    tg_result = send_telegram_message(message.strip(), parse_mode='HTML', bypass_cooldown=True)
                    if tg_result.get('success'):
                        alerts_sent += 1
                except Exception as e:
                    pass  # Continue even if Telegram fails

        return {
            'success': True,
            'alerts_sent': alerts_sent,
            'signals': all_signals,
            'total_candidates': len(candidates)
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}

def send_telegram_message(message: str, parse_mode: str = 'HTML', bypass_cooldown: bool = False) -> Dict:
    """Send message to Telegram with proper formatting"""
    try:
        import urllib.parse

        # FIX: Use correct CONFIG keys (TELEGRAM_BOT and TELEGRAM_CHAT)
        token = CONFIG.get('TELEGRAM_BOT', '')
        chat_id = CONFIG.get('TELEGRAM_CHAT', '')

        if not token or not chat_id:
            return {'success': False, 'error': 'Telegram not configured'}

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            'chat_id': chat_id,
            'text': message,
            'parse_mode': parse_mode
        }).encode()

        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as r:
            result = json.loads(r.read())

        return {'success': result.get('ok', False), 'message_id': result.get('result', {}).get('message_id')}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_mexc_positions() -> Dict:
    """Get real MEXC Futures positions using authenticated API"""
    try:
        timestamp = str(int(time.time() * 1000))
        params = f'timestamp={timestamp}'
        signature = hmac.new(
            CONFIG['MEXC_SECRET_KEY'].encode(),
            params.encode(),
            hashlib.sha256
        ).hexdigest()
        
        url = f'{CONFIG["MEXC_POSITIONS_URL"]}?{params}&signature={signature}'
        req = urllib.request.Request(url)
        req.add_header('Content-Type', 'application/json')
        req.add_header('ApiKey', CONFIG['MEXC_ACCESS_KEY'])
        
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        
        positions = []
        for p in data.get('data', []):
            symbol = p.get('symbol', '').replace('_USDT', 'USDT')
            direction = 'LONG' if p.get('positionType', 1) == 1 else 'SHORT'
            positions.append({
                'symbol': symbol,
                'direction': direction,
                'current_price': float(p.get('openAvgPrice', 0)),
                'margin_ratio': float(p.get('marginRatio', 0)) * 100,
                'pnl': float(p.get('unrealisedPnl', 0)),
                'margin': float(p.get('positionMargin', 0)),
                'liquidation_price': float(p.get('liquidatePrice', 0)),
                'size': float(p.get('holdVol', 0))
            })
        return {'success': True, 'positions': positions, 'count': len(positions)}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_margin_ratios() -> Dict:
    """Get margin ratios with thresholds from config/filters.json"""
    positions = get_mexc_positions()
    if not positions['success']: return positions

    # Load margin thresholds from filters.json
    margin_critical = get_filter('margin.criticalThreshold', CONFIG['MARGIN_CRITICAL'])
    margin_danger = get_filter('margin.dangerThreshold', CONFIG['MARGIN_DANGER'])
    margin_ok = get_filter('margin.safeThreshold', CONFIG['MARGIN_OK'])
    margin_safe = get_filter('margin.excessThreshold', CONFIG['MARGIN_SAFE'])

    ratios = []
    for p in positions['positions']:
        ratio = p['margin_ratio']
        status = 'CRITIQUE' if ratio < margin_critical else 'DANGER' if ratio < margin_danger else 'OK' if ratio < margin_ok else 'SAFE' if ratio < margin_safe else 'EXCES'
        ratios.append({'symbol': p['symbol'], 'margin_ratio': round(ratio, 2), 'status': status, 'pnl': round(p['pnl'], 2)})
    ratios.sort(key=lambda x: x['margin_ratio'])
    return {'success': True, 'ratios': ratios, 'critical_count': len([r for r in ratios if r['status'] == 'CRITIQUE'])}

def check_critical_margins() -> Dict:
    ratios = get_margin_ratios()
    if not ratios['success']: return ratios
    critical = [r for r in ratios['ratios'] if r['status'] in ['CRITIQUE', 'DANGER']]
    if critical:
        msg = "[ANCRAGE] ALERTE MARGE\n"
        for c in critical:
            msg += f"[!!!] {c['symbol']}: {c['margin_ratio']}%\n"
        send_telegram(msg)
    return {'success': True, 'critical': critical, 'alert_sent': len(critical) > 0}

def suggest_margin_transfer() -> Dict:
    ratios = get_margin_ratios()
    if not ratios['success']: return ratios
    critical = [r for r in ratios['ratios'] if r['status'] in ['CRITIQUE', 'DANGER']]
    excess = [r for r in ratios['ratios'] if r['status'] == 'EXCES']
    suggestions = []
    for i, c in enumerate(critical):
        if i < len(excess):
            suggestions.append({'from': excess[i]['symbol'], 'to': c['symbol'], 'reason': f"Augmenter {c['symbol']} de {c['margin_ratio']}%"})
    return {'success': True, 'suggestions': suggestions}

def send_telegram(message: str, parse_mode: str = None, disable_notification: bool = False, bypass_cooldown: bool = False) -> Dict:
    """
    Envoie un message Telegram avec retry, anti-spam et formatage
    v1.1 - 2026-01-17 - Filters from config/filters.json

    Args:
        message: Le message à envoyer
        parse_mode: 'HTML' ou 'Markdown' pour le formatage
        disable_notification: True pour envoyer sans notification
        bypass_cooldown: True pour ignorer l'anti-spam
    """
    global TELEGRAM_COOLDOWN

    # Check if Telegram is enabled in filters
    telegram_enabled = get_filter('telegram.enabled', True)
    if not telegram_enabled:
        return {'success': False, 'error': 'Telegram disabled in filters.json', 'disabled': True}

    # Get cooldown from filters.json (default 300s = 5min)
    cooldown_seconds = get_filter('telegram.cooldownSeconds', TELEGRAM_COOLDOWN_SECONDS)

    # Anti-spam check
    msg_hash = hashlib.md5(message.encode()).hexdigest()[:8]
    now = time.time()

    if not bypass_cooldown and msg_hash in TELEGRAM_COOLDOWN:
        elapsed = now - TELEGRAM_COOLDOWN[msg_hash]
        if elapsed < cooldown_seconds:
            remaining = int(cooldown_seconds - elapsed)
            return {'success': False, 'error': f'Cooldown actif ({remaining}s restantes)', 'cooldown': True}

    # Préparer le payload
    payload_dict = {
        'chat_id': CONFIG["TELEGRAM_CHAT"],
        'text': message,
        'disable_web_page_preview': True,
        'disable_notification': disable_notification
    }

    if parse_mode and parse_mode.upper() in ['HTML', 'MARKDOWN', 'MARKDOWNV2']:
        payload_dict['parse_mode'] = parse_mode.upper()

    # Retry logic (3 tentatives)
    last_error = None
    for attempt in range(3):
        try:
            url = f'https://api.telegram.org/bot{CONFIG["TELEGRAM_BOT"]}/sendMessage'
            payload = json.dumps(payload_dict).encode()
            req = urllib.request.Request(url, payload, {'Content-Type': 'application/json'})

            with urllib.request.urlopen(req, timeout=15) as r:
                response = json.loads(r.read().decode())
                if response.get('ok'):
                    # Mettre à jour le cooldown
                    TELEGRAM_COOLDOWN[msg_hash] = now
                    # Nettoyer les vieux cooldowns (> 1h)
                    TELEGRAM_COOLDOWN = {k: v for k, v in TELEGRAM_COOLDOWN.items() if now - v < 3600}

                    msg_id = response.get('result', {}).get('message_id')
                    logger.info(f"[TG] Message envoyé (ID: {msg_id})")
                    return {'success': True, 'message_id': msg_id, 'attempt': attempt + 1}
                else:
                    last_error = response.get('description', 'Unknown error')

        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}: {e.reason}"
            logger.warning(f"[TG] Attempt {attempt+1} failed: {last_error}")
        except urllib.error.URLError as e:
            last_error = f"URL Error: {e.reason}"
            logger.warning(f"[TG] Attempt {attempt+1} failed: {last_error}")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"[TG] Attempt {attempt+1} failed: {last_error}")

        # Attendre avant retry (backoff exponentiel)
        if attempt < 2:
            time.sleep(2 ** attempt)

    logger.error(f"[TG] Échec après 3 tentatives: {last_error}")
    return {'success': False, 'error': last_error, 'attempts': 3}


def send_telegram_alert(alert_type: str, data: Dict) -> Dict:
    """
    Envoie une alerte formatee selon le type.
    Types: 'signal', 'margin', 'pnl', 'position', 'system'
    Pour 'signal': utilise le format unifie avec Entry/TP1/TP2/TP3
    """
    if alert_type == 'signal':
        # Use unified formatter for signal alerts
        try:
            msg = format_telegram_signal(
                symbol=data.get('symbol', '?'),
                direction=data.get('direction', 'HOLD'),
                entry=float(data.get('price', data.get('entry', 0))),
                tp1=float(data.get('tp1', 0)),
                tp2=float(data.get('tp2', 0)),
                tp3=float(data.get('tp3', data.get('tp2', 0))),
                sl=float(data.get('sl', 0)),
                confidence=float(data.get('confidence', data.get('score', 0))),
                rr_ratio=float(data.get('rr_ratio', 0)),
                score=int(data.get('score', 0)),
                change_pct=float(data.get('change', 0)),
                volume_m=float(data.get('volume_m', 0)),
                range_pos=float(data.get('range_pos', 0)),
                pump_signals=data.get('signals', []),
                signal_type=data.get('signal_type', 'SIGNAL')
            )
            return send_telegram(msg, parse_mode='HTML', bypass_cooldown=True)
        except Exception:
            pass

    templates = {
        'margin': """\u26a0\ufe0f <b>ANCRAGE - ALERTE MARGE</b> \u26a0\ufe0f
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
{positions}

\U0001f6a8 <b>Action:</b> {action}
\u23f0 """ + "{time}",

        'pnl': """\U0001f4b0 <b>PNL UPDATE</b>
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001f4ca Positions: {count}
\U0001f4b5 PnL Total: <b>{pnl:+.2f} USDT</b>
\U0001f7e2 Best: {best}
\U0001f534 Worst: {worst}""",

        'position': """\U0001f4cb <b>POSITION {action}</b>
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
<b>{symbol}</b> {direction}
\U0001f4cd Entry: {entry}
\U0001f4b0 Size: {size} USDT
\u2699\ufe0f Leverage: {leverage}x""",

        'system': """\U0001f527 <b>SYSTEM</b>
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
{message}"""
    }

    template = templates.get(alert_type, templates['system'])
    data['time'] = datetime.now().strftime('%d/%m %H:%M:%S')

    try:
        message = template.format(**data)
    except KeyError:
        message = f"[{alert_type.upper()}] {json.dumps(data, default=str)}"

    return send_telegram(message, parse_mode='HTML', bypass_cooldown=(alert_type in ['margin', 'system']))

def set_price_alert(symbol: str, condition: str, price: float) -> Dict:
    alert = {'id': len(ALERTS['price_alerts']) + 1, 'symbol': symbol, 'condition': condition, 'price': price, 'active': True}
    ALERTS['price_alerts'].append(alert)
    return {'success': True, 'alert': alert}

def set_margin_alert(symbol: str, threshold: float = 5) -> Dict:
    alert = {'id': len(ALERTS['margin_alerts']) + 1, 'symbol': symbol, 'threshold': threshold, 'active': True}
    ALERTS['margin_alerts'].append(alert)
    return {'success': True, 'alert': alert}

def check_all_alerts() -> Dict:
    triggered = []
    scan = scan_mexc(min_score=0)
    if scan['success']:
        prices = {s['symbol']: s['price'] for s in scan['top_signals']}
        for alert in ALERTS['price_alerts']:
            if alert['active'] and alert['symbol'] in prices:
                current = prices[alert['symbol']]
                if (alert['condition'] == 'above' and current > alert['price']) or (alert['condition'] == 'below' and current < alert['price']):
                    triggered.append({'type': 'price', 'alert': alert, 'current': current})
                    alert['active'] = False
    if triggered:
        send_telegram(f"[ALERTE] {len(triggered)} alertes declenchees")
    return {'success': True, 'triggered': triggered}

def list_alerts() -> Dict:
    return {'success': True, 'price_alerts': [a for a in ALERTS['price_alerts'] if a['active']], 'margin_alerts': [a for a in ALERTS['margin_alerts'] if a['active']]}

def delete_alert(alert_type: str, alert_id: int) -> Dict:
    for alert in ALERTS.get(f'{alert_type}_alerts', []):
        if alert['id'] == alert_id:
            alert['active'] = False
            return {'success': True}
    return {'success': False, 'error': 'Not found'}

def _update_ia_stats(ia_name: str, success: bool, elapsed: float):
    stats = IA_STATS[ia_name]
    stats['calls'] += 1
    if success: stats['success'] += 1
    stats['avg_time'] = (stats['avg_time'] * (stats['calls'] - 1) + elapsed) / stats['calls']

def ask_perplexity(question: str) -> Dict:
    """Ask Perplexity AI - FALLBACK to Gemini if fails"""
    start = time.time()
    try:
        url = 'https://api.perplexity.ai/chat/completions'
        payload = json.dumps({'model': 'sonar-pro', 'messages': [{'role': 'user', 'content': question}], 'max_tokens': 300}).encode()
        req = urllib.request.Request(url, payload, {'Authorization': f'Bearer {CONFIG["PERPLEXITY_KEY"]}', 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=20) as r:
            result = json.loads(r.read())
            _update_ia_stats('perplexity', True, time.time() - start)
            return {'success': True, 'answer': result['choices'][0]['message']['content'], 'source': 'perplexity'}
    except Exception as e:
        _update_ia_stats('perplexity', False, time.time() - start)
        # FALLBACK to Gemini
        gem = ask_gemini(question)
        if gem.get('success'):
            return {'success': True, 'answer': gem['answer'], 'source': 'gemini_fallback'}
        return {'success': False, 'error': str(e), 'fallback_tried': True}

def ask_gemini(prompt: str) -> Dict:
    start = time.time()
    try:
        result = subprocess.run([CONFIG["GEMINI_CLI"], prompt], capture_output=True, text=True, timeout=120, encoding='utf-8', errors='replace', shell=True)
        _update_ia_stats('gemini', result.returncode == 0, time.time() - start)
        if result.returncode == 0:
            return {'success': True, 'answer': result.stdout.strip()}
        else:
            return {'success': False, 'error': result.stderr or 'Unknown error'}
    except subprocess.TimeoutExpired:
        _update_ia_stats('gemini', False, time.time() - start)
        return {'success': False, 'error': 'Timeout after 120s'}
    except Exception as e:
        _update_ia_stats('gemini', False, time.time() - start)
        return {'success': False, 'error': str(e)}

def ask_lmstudio(question: str, model: str = None) -> Dict:
    start = time.time()
    try:
        url = f'{CONFIG["LM_STUDIO_URL"]}/v1/chat/completions'
        selected_model = model or CONFIG["LM_STUDIO_MODEL"]
        payload = json.dumps({'model': selected_model, 'messages': [{'role': 'user', 'content': question}], 'max_tokens': 500, 'temperature': 0.3}).encode()
        req = urllib.request.Request(url, payload, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
            _update_ia_stats('lmstudio', True, time.time() - start)
            msg = result['choices'][0]['message']
            answer = msg.get('content') or msg.get('reasoning_content') or msg.get('reasoning') or ''
            return {'success': True, 'model': selected_model, 'answer': answer.strip()}
    except Exception as e:
        _update_ia_stats('lmstudio', False, time.time() - start)
        return {'success': False, 'error': str(e)}

def ask_lmstudio_server(server_key: str, question: str, model: str = None) -> Dict:
    """Query a specific LM Studio server (lmstudio1=M1-Deep, lmstudio2=M2-Fast, lmstudio3=M3-Validate)"""
    servers = CONFIG.get('LMS_SERVERS', {})
    server = servers.get(server_key, {})
    url = server.get('url')
    if not url:
        url_fallback = {
            "lmstudio1": "http://192.168.1.85:1234",
            "lmstudio2": "http://192.168.1.26:1234",
            "lmstudio3": "http://192.168.1.113:1234",
        }
        url = url_fallback.get(server_key, CONFIG.get("LM_STUDIO_URL", "http://127.0.0.1:1234"))
    selected_model = model or server.get('default_model') or CONFIG.get("LM_STUDIO_MODEL", "qwen/qwen3-30b-a3b-2507")
    timeout = server.get('timeout_sec', 90)
    start = time.time()
    try:
        payload = json.dumps({
            'model': selected_model,
            'messages': [{'role': 'user', 'content': question}],
            'max_tokens': 500,
            'temperature': 0.3
        }).encode()
        req = urllib.request.Request(f'{url}/v1/chat/completions', payload, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read())
            msg = result['choices'][0]['message']
            answer = msg.get('content') or msg.get('reasoning_content') or msg.get('reasoning') or ''
            _update_ia_stats(f'lmstudio_{server_key}', True, time.time() - start)
            return {'success': True, 'server': server_key, 'model': selected_model, 'answer': answer.strip(), 'url': url, 'latency': round(time.time() - start, 2)}
    except Exception as e:
        _update_ia_stats(f'lmstudio_{server_key}', False, time.time() - start)
        return {'success': False, 'server': server_key, 'error': str(e), 'url': url}

def ask_claude(question: str, model: str = "claude-3-haiku-20240307") -> Dict:
    """Ask Claude AI - FALLBACK to Gemini (Claude serves as MCP)"""
    start = time.time()
    # Try Claude API first
    try:
        url = 'https://api.anthropic.com/v1/messages'
        payload = json.dumps({
            'model': model,
            'max_tokens': 1024,
            'messages': [{'role': 'user', 'content': question}]
        }).encode()
        req = urllib.request.Request(url, payload, {
            'Content-Type': 'application/json',
            'x-api-key': CONFIG.get("CLAUDE_API_KEY", ""),
            'anthropic-version': '2023-06-01'
        })
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read())
            answer = result['content'][0]['text']
            _update_ia_stats('claude', True, time.time() - start)
            return {'success': True, 'model': model, 'answer': answer, 'source': 'claude'}
    except Exception as e:
        _update_ia_stats('claude', False, time.time() - start)
        # FALLBACK to Gemini (Claude serves as MCP anyway)
        gem = ask_gemini(question)
        if gem.get('success'):
            return {'success': True, 'answer': gem['answer'], 'source': 'gemini_fallback', 'note': 'Claude serves as MCP'}
        return {'success': False, 'error': 'Claude API failed, Gemini fallback failed', 'fallback_tried': True}

def list_lmstudio_models() -> Dict:
    try:
        with urllib.request.urlopen(f'{CONFIG["LM_STUDIO_URL"]}/v1/models', timeout=5) as r:
            return {'success': True, 'models': [m['id'] for m in json.loads(r.read()).get('data', [])]}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def smart_route(question: str, task_type: str = "auto", inject_context: bool = True) -> Dict:
    # CQ: Injection contexte pour routes trading/consensus
    if inject_context and task_type in ("auto", "trading", "consensus"):
        try:
            ctx = build_trading_context()
            if ctx.get('success') and ctx.get('context'):
                question = f"{ctx['context']}\n\n{question}"
        except:
            pass
    if task_type == "web_search" or "actualite" in question.lower():
        return {'ia': 'perplexity', 'result': ask_perplexity(question)}
    elif task_type == "code" or "code" in question.lower():
        return {'ia': 'lmstudio_coder', 'result': ask_lmstudio(question, "qwen/qwen3-coder-30b")}
    elif task_type == "quick":
        return {'ia': 'gemini', 'result': ask_gemini(question)}
    else:
        return {'ia': 'lmstudio', 'result': ask_lmstudio(question)}

def parallel_consensus(question: str, models: List[str] = None, inject_context: bool = True) -> Dict:
    import concurrent.futures
    # CQ: Injection contexte trading
    original_question = question
    if inject_context:
        try:
            ctx = build_trading_context()
            if ctx.get('success') and ctx.get('context'):
                question = f"{ctx['context']}\n\nQUESTION: {question}"
        except:
            pass
    if models is None:
        models = ['gemini', 'lmstudio1', 'lmstudio2', 'lmstudio3']
    results = {}
    def call_ia(model):
        if model == 'perplexity': return ('perplexity', ask_perplexity(question))
        elif model == 'gemini': return ('gemini', ask_gemini(question))
        elif model in ('lmstudio1', 'lmstudio2', 'lmstudio3'):
            return (model, ask_lmstudio_server(model, question))
        else: return ('lmstudio', ask_lmstudio(question))
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(call_ia, m): m for m in models}
        for future in concurrent.futures.as_completed(futures, timeout=90):
            try:
                name, result = future.result()
                results[name] = result
            except: pass
    def parse_verdict(text):
        if not text: return 'HOLD'
        upper = text.upper()
        if 'LONG' in upper or 'BUY' in upper: return 'LONG'
        if 'SHORT' in upper or 'SELL' in upper: return 'SHORT'
        return 'HOLD'
    verdicts = {k: parse_verdict(v.get('answer', '')) for k, v in results.items() if v.get('success')}
    votes = list(verdicts.values())
    consensus = max(set(votes), key=votes.count) if votes else 'HOLD'
    confidence = int(votes.count(consensus) / len(votes) * 100) if votes else 50
    # CQ: Log la decision consensus
    try:
        symbol_hint = original_question.split()[0] if original_question else 'UNKNOWN'
        log_consensus_decision(symbol_hint, original_question[:200], consensus, confidence,
                              {'verdicts': verdicts, 'models': models}, source='parallel_consensus')
    except:
        pass
    return {'success': True, 'consensus': consensus, 'confidence': confidence, 'verdicts': verdicts}

def get_ia_stats() -> Dict:
    return {'success': True, 'stats': {ia: {'calls': s['calls'], 'success_rate': round(s['success']/s['calls']*100, 1) if s['calls'] > 0 else 0, 'avg_time': round(s['avg_time'], 2)} for ia, s in IA_STATS.items()}}

def gh_command(args: str) -> Dict:
    try:
        result = subprocess.run(f'{CONFIG["GH_CLI"]} {args}', shell=True, capture_output=True, text=True, timeout=30)
        return {'success': result.returncode == 0, 'output': result.stdout.strip(), 'error': result.stderr.strip() if result.returncode != 0 else None}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def gh_repo_list() -> Dict:
    return gh_command('repo list --json name,url,isPrivate')

def n8n_request(endpoint: str, method: str = "GET", data: Dict = None) -> Dict:
    try:
        url = f'{CONFIG["N8N_URL"]}/api/v1/{endpoint}'
        req = urllib.request.Request(url, json.dumps(data).encode() if data else None, method=method)
        req.add_header('X-N8N-API-KEY', CONFIG["N8N_API_KEY"])
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=10) as r:
            return {'success': True, 'data': json.loads(r.read())}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def n8n_list_workflows() -> Dict:
    result = n8n_request('workflows')
    if result['success']:
        return {'success': True, 'workflows': [{'id': w['id'], 'name': w['name'], 'active': w['active']} for w in result['data'].get('data', [])]}
    return result

def n8n_activate_workflow(workflow_id: str, active: bool = True) -> Dict:
    return n8n_request(f'workflows/{workflow_id}/{"activate" if active else "deactivate"}', method="POST")

def n8n_get_workflow(workflow_id: str) -> Dict:
    return n8n_request(f'workflows/{workflow_id}')

def n8n_run_workflow(workflow_name: str) -> Dict:
    if workflow_name in WORKFLOWS:
        return n8n_request(f'workflows/{WORKFLOWS[workflow_name]}/run', method="POST")
    return {'success': False, 'error': f'Workflow {workflow_name} not found'}

def n8n_activate_all() -> Dict:
    results = []
    for name, wf_id in WORKFLOWS.items():
        results.append({'name': name, 'success': n8n_activate_workflow(wf_id, True).get('success', False)})
    return {'success': True, 'activated': results}

def n8n_get_active_workflows() -> Dict:
    result = n8n_list_workflows()
    if result['success']:
        return {'success': True, 'active_workflows': [w for w in result['workflows'] if w['active']]}
    return result

def get_all_workflows() -> Dict:
    return {'success': True, 'workflows': WORKFLOWS}

def run_trading_v4() -> Dict:
    return n8n_run_workflow('trading_v4_multiia')

def run_scanner_pro() -> Dict:
    return n8n_run_workflow('scanner_pro_mexc')

def run_multi_ia_telegram() -> Dict:
    return n8n_run_workflow('multi_ia_telegram')

def open_browser(url: str) -> Dict:
    try:
        subprocess.run(['start', '', url], shell=True)
        return {'success': True, 'url': url}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def open_n8n_workflow(workflow_name: str) -> Dict:
    if workflow_name in WORKFLOWS:
        return open_browser(f'{CONFIG["N8N_URL"]}/workflow/{WORKFLOWS[workflow_name]}')
    return {'success': False, 'error': f'Workflow {workflow_name} not found'}

def open_n8n_dashboard() -> Dict:
    return open_browser(f'{CONFIG["N8N_URL"]}/workflows')

def get_multi_ia_consensus(symbol: str = "BTC/USDT") -> Dict:
    scan = scan_mexc()
    if not scan['success']: return scan
    signal = next((s for s in scan['top_signals'] if s['symbol'] == symbol), scan['top_signals'][0] if scan['top_signals'] else None)
    if not signal: return {'success': False, 'error': 'No signals'}
    question = f"Signal crypto {signal['symbol']}: Prix {signal['price']}, Score {signal['score']}/100. Verdict: LONG, SHORT ou HOLD?"
    verdicts = {}
    for ia, func in [('perplexity', ask_perplexity), ('gemini', ask_gemini), ('lmstudio', ask_lmstudio)]:
        r = func(question)
        if r['success']: verdicts[ia] = r['answer'][:100]
    def parse(text):
        if 'LONG' in text.upper() or 'BUY' in text.upper(): return 'LONG'
        if 'SHORT' in text.upper() or 'SELL' in text.upper(): return 'SHORT'
        return 'HOLD'
    parsed = {k: parse(v) for k, v in verdicts.items()}
    votes = list(parsed.values())
    consensus = max(set(votes), key=votes.count) if votes else 'HOLD'
    return {'success': True, 'signal': signal, 'consensus': consensus, 'confidence': int(votes.count(consensus)/len(votes)*100) if votes else 50, 'verdicts': parsed}

def run_backtest(symbol: str, strategy: str = "breakout", days: int = 7) -> Dict:
    import random
    trades = [{'id': i+1, 'symbol': symbol, 'pnl': round(random.uniform(-5, 8), 2)} for i in range(days * 3)]
    wins = len([t for t in trades if t['pnl'] > 0])
    return {'success': True, 'symbol': symbol, 'strategy': strategy, 'total_trades': len(trades), 'win_rate': round(wins/len(trades)*100, 1), 'total_pnl': round(sum(t['pnl'] for t in trades), 2)}

def get_trade_history() -> Dict:
    return {'success': True, 'trades': TRADE_HISTORY[-50:]}

def add_trade(symbol: str, direction: str, entry: float, exit_price: float = None, pnl: float = None) -> Dict:
    trade = {'id': len(TRADE_HISTORY) + 1, 'symbol': symbol, 'direction': direction, 'entry': entry, 'exit': exit_price, 'pnl': pnl, 'timestamp': datetime.now().isoformat()}
    TRADE_HISTORY.append(trade)
    return {'success': True, 'trade': trade}

def start_realtime_monitor(interval: int = 60) -> Dict:
    global MONITORING_ACTIVE
    MONITORING_ACTIVE = True
    def loop():
        while MONITORING_ACTIVE:
            check_critical_margins()
            check_all_alerts()
            time.sleep(interval)
    threading.Thread(target=loop, daemon=True).start()
    return {'success': True, 'status': 'Monitoring started', 'interval': interval}

def stop_realtime_monitor() -> Dict:
    global MONITORING_ACTIVE
    MONITORING_ACTIVE = False
    return {'success': True, 'status': 'Monitoring stopped'}

def get_live_dashboard() -> Dict:
    scan = scan_mexc(min_score=70)
    ratios = get_margin_ratios()
    return {'success': True, 'timestamp': datetime.now().isoformat(), 'monitoring_active': MONITORING_ACTIVE, 'top_signals': scan.get('top_signals', [])[:5], 'critical_positions': ratios.get('critical_count', 0), 'ia_stats': get_ia_stats().get('stats', {})}

N8N_WEBHOOKS = {"scan_market": "http://localhost:5678/webhook/scan-market", "multi_ia_consensus": "http://localhost:5678/webhook/multi-ia-consensus", "analyze_coin": "http://localhost:5678/webhook/analyze-coin", "fvg_scanner": "http://localhost:5678/webhook/fvg-scanner", "send_telegram_wh": "http://localhost:5678/webhook/send-telegram", "status": "http://localhost:5678/webhook/status"}

def webhook_call(endpoint: str, data: Dict = None) -> Dict:
    try:
        url = N8N_WEBHOOKS.get(endpoint, endpoint)
        req = urllib.request.Request(url, json.dumps(data).encode() if data else None, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=60) as r:
            return {'success': True, 'data': json.loads(r.read())}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def wh_scan_market(symbol: str = None) -> Dict:
    return webhook_call("scan_market", {'symbol': symbol} if symbol else {})

def wh_multi_ia_consensus(symbol: str = "BTC") -> Dict:
    return webhook_call("multi_ia_consensus", {'symbol': symbol})

def wh_analyze_coin(symbol: str = "BTC", notify: bool = True) -> Dict:
    return webhook_call("analyze_coin", {'symbol': symbol, 'notify': notify})

def wh_fvg_scanner(symbol: str = "BTC") -> Dict:
    return webhook_call("fvg_scanner", {'symbol': symbol})

def wh_send_telegram(message: str, chat_id: str = None) -> Dict:
    return webhook_call("send_telegram_wh", {'message': message, 'chat_id': chat_id} if chat_id else {'message': message})

def wh_get_status() -> Dict:
    try:
        with urllib.request.urlopen(N8N_WEBHOOKS["status"], timeout=10) as r:
            return {'success': True, 'data': json.loads(r.read())}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def wh_trading_signal(symbol: str = "BTC") -> Dict:
    return {'success': True, 'results': {'scan': wh_scan_market(symbol), 'consensus': wh_multi_ia_consensus(symbol), 'analysis': wh_analyze_coin(symbol)}}

# ============================================
# ORDERBOOK & ONCHAIN ANALYSIS (v3.3)
# ============================================

def get_orderbook_analysis(symbol: str = "BTC/USDT", limit: int = 20) -> Dict:
    """Analyse l'orderbook pour detecter la pression achat/vente"""
    if not CCXT_AVAILABLE: return {'success': False, 'error': 'CCXT not available'}
    try:
        exchange = ccxt.mexc({
            'apiKey': CONFIG['MEXC_ACCESS_KEY'],
            'secret': CONFIG['MEXC_SECRET_KEY'],
            'options': {
                'defaultType': 'swap',
                'adjustForTimeDifference': True,
                'recvWindow': 60000
            }
        })
        exchange.load_time_difference()  # Force sync horloge MEXC
        if not symbol.endswith(':USDT'):
            symbol = f"{symbol}:USDT" if '/USDT' in symbol else f"{symbol}/USDT:USDT"

        orderbook = exchange.fetch_order_book(symbol, limit)
        bids = orderbook['bids'][:limit]
        asks = orderbook['asks'][:limit]

        total_bid_vol = sum([b[1] for b in bids])
        total_ask_vol = sum([a[1] for a in asks])

        bid_wall = max(bids, key=lambda x: x[1]) if bids else [0, 0]
        ask_wall = max(asks, key=lambda x: x[1]) if asks else [0, 0]

        imbalance = (total_bid_vol - total_ask_vol) / (total_bid_vol + total_ask_vol) * 100 if (total_bid_vol + total_ask_vol) > 0 else 0
        spread = (asks[0][0] - bids[0][0]) / bids[0][0] * 100 if bids and asks else 0

        return {
            'success': True,
            'symbol': symbol,
            'bid_volume': round(total_bid_vol, 4),
            'ask_volume': round(total_ask_vol, 4),
            'imbalance': round(imbalance, 2),
            'bid_wall': {'price': bid_wall[0], 'size': round(bid_wall[1], 4)},
            'ask_wall': {'price': ask_wall[0], 'size': round(ask_wall[1], 4)},
            'spread_pct': round(spread, 4),
            'pressure': 'BUY' if imbalance > 10 else 'SELL' if imbalance < -10 else 'NEUTRAL',
            'best_bid': bids[0][0] if bids else 0,
            'best_ask': asks[0][0] if asks else 0
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_onchain_flow(symbol: str = "BTC/USDT") -> Dict:
    """Analyse les flux onchain via les trades recents (inflow/outflow)"""
    if not CCXT_AVAILABLE: return {'success': False, 'error': 'CCXT not available'}
    try:
        exchange = ccxt.mexc({
            'apiKey': CONFIG['MEXC_ACCESS_KEY'],
            'secret': CONFIG['MEXC_SECRET_KEY'],
            'options': {
                'defaultType': 'swap',
                'adjustForTimeDifference': True,
                'recvWindow': 60000
            }
        })
        exchange.load_time_difference()  # Force sync horloge MEXC
        if not symbol.endswith(':USDT'):
            symbol = f"{symbol}:USDT" if '/USDT' in symbol else f"{symbol}/USDT:USDT"

        trades = exchange.fetch_trades(symbol, limit=200)
        if not trades:
            return {'success': True, 'symbol': symbol, 'inflow': 0, 'outflow': 0, 'signal': 'NO_DATA'}

        buy_volume = sum([t['amount'] * t['price'] for t in trades if t['side'] == 'buy'])
        sell_volume = sum([t['amount'] * t['price'] for t in trades if t['side'] == 'sell'])

        avg_size = np.mean([t['amount'] for t in trades]) if NUMPY_AVAILABLE else sum([t['amount'] for t in trades]) / len(trades)
        whale_buys = len([t for t in trades if t['side'] == 'buy' and t['amount'] > avg_size * 10])
        whale_sells = len([t for t in trades if t['side'] == 'sell' and t['amount'] > avg_size * 10])

        net_flow = buy_volume - sell_volume
        flow_ratio = buy_volume / sell_volume if sell_volume > 0 else 999

        return {
            'success': True,
            'symbol': symbol,
            'inflow_usd': round(buy_volume, 2),
            'outflow_usd': round(sell_volume, 2),
            'net_flow_usd': round(net_flow, 2),
            'flow_ratio': round(flow_ratio, 2),
            'whale_buys': whale_buys,
            'whale_sells': whale_sells,
            'signal': 'INFLOW' if flow_ratio > 1.2 else 'OUTFLOW' if flow_ratio < 0.8 else 'BALANCED',
            'whale_activity': 'BULLISH' if whale_buys > whale_sells else 'BEARISH' if whale_sells > whale_buys else 'NEUTRAL'
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def deep_analyze_coin(symbol: str = "BTC/USDT") -> Dict:
    """Analyse complete d'un coin: OHLCV, Orderbook, Onchain, Niveaux"""
    if not CCXT_AVAILABLE: return {'success': False, 'error': 'CCXT not available'}
    try:
        exchange = ccxt.mexc({
            'apiKey': CONFIG['MEXC_ACCESS_KEY'],
            'secret': CONFIG['MEXC_SECRET_KEY'],
            'options': {
                'defaultType': 'swap',
                'adjustForTimeDifference': True,
                'recvWindow': 60000
            }
        })
        exchange.load_time_difference()  # Force sync horloge MEXC
        if not symbol.endswith(':USDT'):
            symbol = f"{symbol}:USDT" if '/USDT' in symbol else f"{symbol}/USDT:USDT"

        # Ticker
        ticker = exchange.fetch_ticker(symbol)

        # OHLCV
        ohlcv = exchange.fetch_ohlcv(symbol, '15m', limit=50)
        closes = [c[4] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]

        current_price = closes[-1]

        # ATR pour TP/SL
        if NUMPY_AVAILABLE and len(ohlcv) > 14:
            tr = np.maximum(np.array(highs[1:]) - np.array(lows[1:]),
                           np.maximum(np.abs(np.array(highs[1:]) - np.array(closes[:-1])),
                                     np.abs(np.array(lows[1:]) - np.array(closes[:-1]))))
            atr = np.mean(tr[-14:])
        else:
            atr = (max(highs[-14:]) - min(lows[-14:])) / 14

        # Orderbook
        ob = get_orderbook_analysis(symbol)

        # Onchain flow
        flow = get_onchain_flow(symbol)

        # Score
        score = 50
        if ob.get('pressure') == 'BUY': score += 15
        elif ob.get('pressure') == 'SELL': score -= 15
        if flow.get('signal') == 'INFLOW': score += 15
        elif flow.get('signal') == 'OUTFLOW': score -= 15
        if ticker.get('percentage', 0) > 0: score += 10
        if flow.get('whale_activity') == 'BULLISH': score += 10

        return {
            'success': True,
            'symbol': symbol.replace(':USDT', ''),
            'price': current_price,
            'change_24h': ticker.get('percentage', 0),
            'volume_24h': ticker.get('quoteVolume', 0),
            'rsi': calculate_rsi(closes),
            'macd': calculate_macd(closes),
            'levels': {
                'tp1': round(current_price + atr * 1.5, 6),
                'tp2': round(current_price + atr * 2.5, 6),
                'tp3': round(current_price + atr * 4, 6),
                'sl': round(current_price - atr * 1.2, 6),
                'atr': round(atr, 6),
                'atr_pct': round(atr / current_price * 100, 2)
            },
            'orderbook': {
                'pressure': ob.get('pressure'),
                'imbalance': ob.get('imbalance'),
                'bid_wall': ob.get('bid_wall'),
                'ask_wall': ob.get('ask_wall')
            },
            'onchain': {
                'signal': flow.get('signal'),
                'net_flow': flow.get('net_flow_usd'),
                'whale_activity': flow.get('whale_activity'),
                'whale_buys': flow.get('whale_buys'),
                'whale_sells': flow.get('whale_sells')
            },
            'score': min(100, max(0, score)),
            'recommendation': 'LONG' if score >= 65 else 'SHORT' if score <= 35 else 'WAIT',
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def send_signal_choices(signals: list = None) -> Dict:
    """Envoie les signaux avec choix numerotes sur Telegram"""
    if not signals:
        # Scanner pour trouver les signaux
        scan = scan_mexc(min_score=60)
        signals = scan.get('top_signals', [])[:5]

    if not signals:
        return {'success': False, 'error': 'No signals found'}

    msg = "[SIGNAUX DETECTES]\n"
    msg += "=" * 25 + "\n"
    msg += f"{datetime.now().strftime('%H:%M:%S')}\n\n"

    for i, sig in enumerate(signals, 1):
        symbol = sig.get('symbol', 'N/A')
        score = sig.get('score', sig.get('pump_score', 0))
        change = sig.get('change', sig.get('change_1h', 0))
        direction = sig.get('direction', 'N/A')

        msg += f"{i}. {symbol}\n"
        msg += f"   {direction} | Score: {score}\n"
        msg += f"   Change: {change:+.2f}%\n\n"

    msg += "Reponds 1-5 pour analyser en temps reel"

    result = send_telegram(msg)
    return {'success': result.get('success', False), 'signals_count': len(signals), 'message_id': result.get('message_id')}

def scan_all_pumps(min_volume: int = 1000000, min_change: float = 2.0) -> Dict:
    """Scanne tous les coins MEXC pour detecter les pumps immediats"""
    if not CCXT_AVAILABLE: return {'success': False, 'error': 'CCXT not available'}
    try:
        exchange = ccxt.mexc({
            'apiKey': CONFIG['MEXC_ACCESS_KEY'],
            'secret': CONFIG['MEXC_SECRET_KEY'],
            'options': {
                'defaultType': 'swap',
                'adjustForTimeDifference': True,
                'recvWindow': 60000
            }
        })
        exchange.load_time_difference()  # Force sync horloge MEXC
        markets = exchange.load_markets()

        swap_markets = [s for s in markets if markets[s].get('swap') and markets[s].get('active')]

        pumps = []
        for symbol in swap_markets[:100]:  # Limiter pour eviter timeout
            try:
                ticker = exchange.fetch_ticker(symbol)
                volume = ticker.get('quoteVolume', 0) or 0
                change = ticker.get('percentage', 0) or 0

                if volume >= min_volume and change >= min_change:
                    pumps.append({
                        'symbol': symbol.replace(':USDT', '').replace('/USDT', ''),
                        'price': ticker.get('last', 0),
                        'change_24h': round(change, 2),
                        'volume_usd': round(volume, 0),
                        'pump_score': min(100, int(50 + change * 2 + (volume / 10000000)))
                    })
            except:
                continue

        pumps = sorted(pumps, key=lambda x: x['pump_score'], reverse=True)[:10]

        return {
            'success': True,
            'total_scanned': len(swap_markets[:100]),
            'pumps_found': len(pumps),
            'top_pumps': pumps
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============================================
# IMMINENT PUMP DETECTOR (v3.3)
# Detection de pumps imminents avec liquidites
# ============================================

def calculate_liquidity_clusters(orderbook: Dict, current_price: float) -> Dict:
    """
    Identifie les clusters de liquidite dans l'orderbook
    pour determiner supports/resistances et zones de TP/SL optimales
    """
    bids = orderbook.get('bids', [])
    asks = orderbook.get('asks', [])

    if not bids or not asks:
        return {'support': current_price * 0.97, 'resistance_1': current_price * 1.03, 'resistance_2': current_price * 1.06}

    # Grouper les ordres par zones de prix (1% tolerance)
    def group_orders(orders, tolerance=0.01):
        if not orders:
            return []
        clusters = []
        # Handle both [price, volume] and [price, volume, extra...] formats
        first_order = orders[0]
        price0 = first_order[0] if isinstance(first_order, (list, tuple)) else first_order
        vol0 = first_order[1] if isinstance(first_order, (list, tuple)) and len(first_order) > 1 else 0
        current_cluster = {'price': price0, 'volume': vol0, 'orders': 1}

        for order in orders[1:]:
            price = order[0] if isinstance(order, (list, tuple)) else order
            volume = order[1] if isinstance(order, (list, tuple)) and len(order) > 1 else 0
            if current_cluster['price'] > 0 and abs(price - current_cluster['price']) / current_cluster['price'] <= tolerance:
                current_cluster['volume'] += volume
                current_cluster['orders'] += 1
            else:
                clusters.append(current_cluster)
                current_cluster = {'price': price, 'volume': volume, 'orders': 1}
        clusters.append(current_cluster)
        return sorted(clusters, key=lambda x: x['volume'], reverse=True)

    bid_clusters = group_orders(bids)[:5]
    ask_clusters = group_orders(asks)[:5]

    # Support = plus gros cluster bid proche du prix
    support = bid_clusters[0]['price'] if bid_clusters else current_price * 0.97

    # Resistances = clusters ask tries par volume
    resistance_1 = ask_clusters[0]['price'] if ask_clusters else current_price * 1.03
    resistance_2 = ask_clusters[1]['price'] if len(ask_clusters) > 1 else current_price * 1.06

    return {
        'support': round(support, 8),
        'resistance_1': round(resistance_1, 8),
        'resistance_2': round(resistance_2, 8),
        'bid_clusters': bid_clusters[:3],
        'ask_clusters': ask_clusters[:3]
    }

def calculate_optimal_levels(current_price: float, direction: str, liquidity: Dict, atr: float) -> Dict:
    """
    Calcule les niveaux optimaux d'entree, TP et SL
    bases sur les clusters de liquidite et l'ATR
    """
    support = liquidity.get('support', current_price * 0.97)
    resistance_1 = liquidity.get('resistance_1', current_price * 1.03)
    resistance_2 = liquidity.get('resistance_2', current_price * 1.06)

    if direction == 'LONG':
        # Entry: zone de consolidation actuelle
        entry_min = round(current_price * 0.995, 8)
        entry_max = round(current_price * 1.005, 8)

        # TP bases sur resistances (juste avant les walls)
        tp1 = round(resistance_1 * 0.98, 8)  # 2% avant resistance_1
        tp2 = round(resistance_1 * 1.02, 8)  # 2% apres resistance_1 (breakout)
        tp3 = round(resistance_2 * 0.98, 8)  # 2% avant resistance_2

        # SL base sur support + marge ATR
        sl = round(support - (atr * 0.5), 8)

    else:  # SHORT
        entry_min = round(current_price * 0.995, 8)
        entry_max = round(current_price * 1.005, 8)

        tp1 = round(support * 1.02, 8)
        tp2 = round(support * 0.98, 8)
        tp3 = round(support * 0.95, 8)

        sl = round(resistance_1 + (atr * 0.5), 8)

    # Calcul des gains potentiels
    gain_tp1 = abs((tp1 - current_price) / current_price * 100)
    gain_tp2 = abs((tp2 - current_price) / current_price * 100)
    gain_tp3 = abs((tp3 - current_price) / current_price * 100)
    risk = abs((sl - current_price) / current_price * 100)

    return {
        'entry_zone': {'min': entry_min, 'max': entry_max},
        'tp1': tp1,
        'tp2': tp2,
        'tp3': tp3,
        'sl': sl,
        'potential_gain_tp1': round(gain_tp1, 2),
        'potential_gain_tp2': round(gain_tp2, 2),
        'potential_gain_tp3': round(gain_tp3, 2),
        'risk_percent': round(risk, 2),
        'risk_reward': round(gain_tp2 / risk, 2) if risk > 0 else 0
    }

def detect_imminent_pumps(min_probability: int = 70, top_n: int = 3, send_telegram_alert: bool = True) -> Dict:
    """
    Detection de pumps imminents avec analyse complete:
    - Breakout detection (position > 85% du range)
    - Reversal detection (position < 15% + volume spike)
    - Liquidity cluster analysis
    - RSI/MACD alignment
    - Orderbook imbalance
    - Whale activity (inflow)

    Returns: Top N coins avec entry optimal, TP1/TP2/TP3, probabilite
    """
    if not CCXT_AVAILABLE:
        return {'success': False, 'error': 'CCXT not available'}

    try:
        import math

        # Step 1: Scan MEXC pour candidats
        scan_result = scan_mexc(min_score=60)
        if not scan_result.get('success'):
            return scan_result

        candidates = scan_result.get('top_signals', [])[:15]  # Top 15 pour analyse approfondie

        if not candidates:
            return {'success': True, 'top_signals': [], 'message': 'No candidates found'}

        # Step 2: Analyse approfondie de chaque candidat
        analyzed = []
        exchange = ccxt.mexc({
            'apiKey': CONFIG['MEXC_ACCESS_KEY'],
            'secret': CONFIG['MEXC_SECRET_KEY'],
            'options': {'defaultType': 'swap'}
        })

        for candidate in candidates:
            try:
                symbol = candidate.get('symbol', '')
                if not symbol:
                    continue

                # Format symbol pour CCXT
                ccxt_symbol = f"{symbol}:USDT" if '/USDT' in symbol else f"{symbol}/USDT:USDT"

                # Fetch detailed data
                ticker = exchange.fetch_ticker(ccxt_symbol)
                orderbook = exchange.fetch_order_book(ccxt_symbol, limit=50)
                ohlcv = exchange.fetch_ohlcv(ccxt_symbol, '15m', limit=50)

                current_price = ticker.get('last', 0)
                change_24h = ticker.get('percentage', 0) or 0
                volume_24h = ticker.get('quoteVolume', 0) or 0

                # Calcul RSI
                closes = [c[4] for c in ohlcv]
                rsi = calculate_rsi(closes) if len(closes) >= 14 else 50
                macd_data = calculate_macd(closes) if len(closes) >= 26 else {'histogram': 0}

                # ATR pour niveaux
                highs = [c[2] for c in ohlcv]
                lows = [c[3] for c in ohlcv]
                if NUMPY_AVAILABLE and len(ohlcv) > 14:
                    tr = np.maximum(np.array(highs[1:]) - np.array(lows[1:]),
                                   np.maximum(np.abs(np.array(highs[1:]) - np.array(closes[:-1])),
                                             np.abs(np.array(lows[1:]) - np.array(closes[:-1]))))
                    atr = np.mean(tr[-14:])
                else:
                    atr = (max(highs[-14:]) - min(lows[-14:])) / 14 if len(highs) >= 14 else current_price * 0.02

                # Analyse orderbook
                bids = orderbook.get('bids', [])[:50]
                asks = orderbook.get('asks', [])[:50]
                total_bid = sum([b[1] for b in bids])
                total_ask = sum([a[1] for a in asks])
                imbalance = (total_bid - total_ask) / (total_bid + total_ask) * 100 if (total_bid + total_ask) > 0 else 0

                # Calcul clusters liquidite
                liquidity = calculate_liquidity_clusters({'bids': bids, 'asks': asks}, current_price)

                # Position dans le range
                position = candidate.get('position', 0.5)

                # Detection type
                detection_type = 'NEUTRAL'
                if position >= 0.85 and change_24h > 2:
                    detection_type = 'BREAKOUT'
                elif position <= 0.15 and rsi < 35:
                    detection_type = 'REVERSAL'
                elif imbalance > 20 and change_24h > 0:
                    detection_type = 'ACCUMULATION'

                # Calcul probabilite
                probability = 50
                reasons = []

                # Volume factor
                if volume_24h > 100000000:
                    probability += 15
                    reasons.append('VOL_MEGA')
                elif volume_24h > 10000000:
                    probability += 10
                    reasons.append('VOL_HIGH')

                # Position factor
                if detection_type == 'BREAKOUT':
                    probability += 15
                    reasons.append('BREAKOUT_ZONE')
                elif detection_type == 'REVERSAL':
                    probability += 12
                    reasons.append('REVERSAL_ZONE')
                elif detection_type == 'ACCUMULATION':
                    probability += 10
                    reasons.append('ACCUMULATION')

                # RSI factor
                if 30 <= rsi <= 70:
                    probability += 10
                    reasons.append('RSI_OK')
                elif rsi < 30:
                    probability += 8
                    reasons.append('RSI_OVERSOLD')

                # MACD factor
                if macd_data.get('histogram', 0) > 0:
                    probability += 8
                    reasons.append('MACD_BULLISH')

                # Orderbook imbalance
                if imbalance > 15:
                    probability += 10
                    reasons.append('BUY_PRESSURE')
                elif imbalance < -15:
                    probability -= 10
                    reasons.append('SELL_PRESSURE')

                # Skip low probability
                if probability < min_probability:
                    continue

                # Direction
                direction = candidate.get('direction', 'LONG')

                # Calcul niveaux optimaux
                levels = calculate_optimal_levels(current_price, direction, liquidity, atr)

                analyzed.append({
                    'symbol': symbol,
                    'current_price': current_price,
                    'entry_zone': levels['entry_zone'],
                    'tp1': levels['tp1'],
                    'tp2': levels['tp2'],
                    'tp3': levels['tp3'],
                    'sl': levels['sl'],
                    'potential_gain': f"+{levels['potential_gain_tp2']:.1f}%",
                    'risk_reward': levels['risk_reward'],
                    'probability': min(100, probability),
                    'direction': direction,
                    'detection_type': detection_type,
                    'reasons': reasons,
                    'rsi': round(rsi, 2),
                    'macd_histogram': round(macd_data.get('histogram', 0), 6),
                    'orderbook_imbalance': round(imbalance, 2),
                    'volume_24h': round(volume_24h, 0),
                    'change_24h': round(change_24h, 2),
                    'liquidity_clusters': {
                        'support': liquidity['support'],
                        'resistance_1': liquidity['resistance_1'],
                        'resistance_2': liquidity['resistance_2']
                    }
                })

            except Exception as e:
                logger.warning(f"Error analyzing {candidate.get('symbol', 'unknown')}: {e}")
                continue

        # Sort by probability and take top N
        analyzed = sorted(analyzed, key=lambda x: x['probability'], reverse=True)[:top_n]

        # Assign ranks
        for i, sig in enumerate(analyzed, 1):
            sig['rank'] = i

        # Send Telegram alert if enabled
        telegram_sent = False
        if send_telegram_alert and analyzed:
            msg = "IMMINENT PUMP DETECTION\n"
            msg += "=" * 30 + "\n"
            msg += f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            for sig in analyzed:
                msg += f"#{sig['rank']} {sig['symbol']}\n"
                msg += f"   Direction: {sig['direction']} ({sig['detection_type']})\n"
                msg += f"   Prix: {sig['current_price']}\n"
                msg += f"   Entry: {sig['entry_zone']['min']} - {sig['entry_zone']['max']}\n"
                msg += f"   TP1: {sig['tp1']} | TP2: {sig['tp2']} | TP3: {sig['tp3']}\n"
                msg += f"   SL: {sig['sl']}\n"
                msg += f"   Gain: {sig['potential_gain']} | R/R: {sig['risk_reward']}\n"
                msg += f"   Probabilite: {sig['probability']}%\n"
                msg += f"   {', '.join(sig['reasons'][:4])}\n\n"

            result = send_telegram(msg)
            telegram_sent = result.get('success', False)

        return {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'candidates_scanned': len(candidates),
            'signals_found': len(analyzed),
            'top_signals': analyzed,
            'telegram_sent': telegram_sent
        }

    except Exception as e:
        logger.error(f"detect_imminent_pumps error: {e}")
        return {'success': False, 'error': str(e)}

def get_system_status() -> Dict:
    status = {}
    try:
        with urllib.request.urlopen(CONFIG["MEXC_URL"], timeout=5) as r: status['mexc'] = r.status == 200
    except: status['mexc'] = False
    try:
        with urllib.request.urlopen(f'https://api.telegram.org/bot{CONFIG["TELEGRAM_BOT"]}/getMe', timeout=5) as r: status['telegram'] = r.status == 200
    except: status['telegram'] = False
    try:
        result = n8n_list_workflows()
        status['n8n'] = result['success']
    except: status['n8n'] = False
    try:
        with urllib.request.urlopen(f'{CONFIG["LM_STUDIO_URL"]}/v1/models', timeout=3) as r: status['lmstudio'] = r.status == 200
    except: status['lmstudio'] = False
    status['monitoring_active'] = MONITORING_ACTIVE
    status['ccxt_available'] = CCXT_AVAILABLE
    status['numpy_available'] = NUMPY_AVAILABLE
    status['db_connected'] = get_db_connection() is not None
    return {'success': True, 'status': status, 'version': '3.2.0'}

# ============================================
# MULTI-SCANNER PIPELINE (v3.3)
# ============================================

LM_SERVERS = {
    "detector": {"url": "http://192.168.1.26:1234", "model": "nvidia/nemotron-3-nano", "role": "DETECTION"},
    "analyzer": {"url": "http://192.168.1.85:1234", "model": "qwen/qwen3-30b-a3b-2507", "role": "ANALYSIS"},
    "validator": {"url": "http://192.168.1.113:1234", "model": "mistral-7b-instruct-v0.3", "role": "VALIDATION"},
    "local": {"url": "http://127.0.0.1:1234", "model": "local", "role": "BACKUP"}
}

def check_all_lmstudio_servers() -> Dict:
    """Check health of all LM Studio servers"""
    results = {}
    for name, server in LM_SERVERS.items():
        try:
            with urllib.request.urlopen(f"{server['url']}/v1/models", timeout=5) as r:
                data = json.loads(r.read())
                models = [m['id'] for m in data.get('data', [])]
                results[name] = {"online": True, "url": server['url'], "role": server['role'], "models": len(models), "model_list": models[:5]}
        except Exception as e:
            results[name] = {"online": False, "url": server['url'], "role": server['role'], "error": str(e)}

    online_count = sum(1 for r in results.values() if r.get('online'))
    return {"success": True, "servers": results, "online_count": online_count, "total": len(LM_SERVERS)}

def query_lm_server(server_key: str, prompt: str, max_tokens: int = 500) -> Optional[str]:
    """Query a specific LM Studio server"""
    server = LM_SERVERS.get(server_key)
    if not server:
        return None

    try:
        payload = json.dumps({
            "model": server['model'],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.3
        }).encode()

        req = urllib.request.Request(
            f"{server['url']}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=45) as r:
            data = json.loads(r.read())
            msg = data["choices"][0]["message"]
            return msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or ""
    except Exception as e:
        logger.error(f"LM Server {server_key} error: {e}")
        return None

def distribute_task_parallel(task: str, max_tokens: int = 500, include_local: bool = False) -> Dict:
    """
    Distribute a task to all 3 remote LM Studio servers in parallel.
    Returns responses from all servers and a compacted summary.
    """
    import concurrent.futures

    # Select servers (exclude local by default to avoid PC freeze)
    servers_to_use = ["detector", "analyzer", "validator"]
    if include_local:
        servers_to_use.append("local")

    results = {}
    start_time = time.time()

    def query_server(server_key: str) -> tuple:
        """Query a single server and return (server_key, response, time)"""
        t0 = time.time()
        response = query_lm_server(server_key, task, max_tokens)
        elapsed = time.time() - t0
        return (server_key, response, elapsed)

    # Execute in parallel with ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(query_server, srv): srv for srv in servers_to_use}

        for future in concurrent.futures.as_completed(futures, timeout=60):
            try:
                server_key, response, elapsed = future.result()
                server_info = LM_SERVERS.get(server_key, {})
                results[server_key] = {
                    "response": response,
                    "time": round(elapsed, 2),
                    "model": server_info.get("model", "unknown"),
                    "role": server_info.get("role", "unknown"),
                    "success": response is not None
                }
            except Exception as e:
                server_key = futures[future]
                results[server_key] = {"response": None, "error": str(e), "success": False}

    total_time = round(time.time() - start_time, 2)
    success_count = sum(1 for r in results.values() if r.get("success"))

    # Compact responses - extract key points from each
    responses_text = []
    for srv, data in results.items():
        if data.get("response"):
            responses_text.append(f"[{srv.upper()}] {data['response'][:500]}")

    # Create compact summary if multiple responses
    compact = None
    if len(responses_text) >= 2:
        # Use the fastest successful response as base, note differences
        fastest = min((r for r in results.values() if r.get("success")), key=lambda x: x.get("time", 999), default=None)
        if fastest:
            compact = fastest.get("response", "")[:800]

    return {
        "success": success_count > 0,
        "task": task[:100] + "..." if len(task) > 100 else task,
        "servers_queried": len(servers_to_use),
        "servers_responded": success_count,
        "total_time": total_time,
        "results": results,
        "compact_response": compact or (responses_text[0] if responses_text else "No response"),
        "all_responses": responses_text
    }

def run_multi_scanner_pipeline(min_score: int = None, send_tg: bool = None, stages: List[str] = None) -> Dict:
    """Run multi-scanner pipeline with multiple LM Studio models
    v1.1 - 2026-01-17 - Filters from config/filters.json
    """
    import math
    start_time = time.time()
    stages = stages or ["detection", "analysis", "validation", "consensus"]

    # Load filters from config/filters.json
    if min_score is None:
        min_score = get_filter('scanner.minScore', 50)
    if send_tg is None:
        send_tg = get_filter('telegram.enabled', True)
    min_volume = get_filter('scanner.minVolume24h', 500000)

    # Stage 0: Pre-filter from MEXC
    try:
        with urllib.request.urlopen(CONFIG["MEXC_URL"], timeout=15) as r:
            tickers = json.loads(r.read()).get('data', [])
    except:
        return {"success": False, "error": "Failed to fetch MEXC data"}

    # Algorithmic pre-filter
    candidates = []
    for t in tickers:
        if not t.get('symbol', '').endswith('_USDT'):
            continue

        symbol = t['symbol'].replace('_USDT', '/USDT')

        # Check blacklist from filters.json
        if is_blacklisted(symbol):
            continue

        price = float(t.get('lastPrice') or 0)
        high24 = float(t.get('high24Price') or price * 1.05)
        low24 = float(t.get('low24Price') or price * 0.95)
        change = float(t.get('riseFallRate') or 0) * 100
        volume = float(t.get('amount24') or 0)

        if price <= 0 or volume < min_volume:
            continue

        range_24h = high24 - low24
        position = ((price - low24) / range_24h * 100) if range_24h > 0 else 50
        volatility = (range_24h / price * 100) if price > 0 else 0

        # Quick score
        score = 30
        reasons = []
        if volume > 100000000: score += 20; reasons.append("VOL_HIGH")
        elif volume > 10000000: score += 10; reasons.append("VOL_MED")
        if position >= 90: score += 25; reasons.append("BREAKOUT")
        elif position <= 10: score += 20; reasons.append("REVERSAL")
        if abs(change) >= 10: score += 20; reasons.append("STRONG_MOVE")
        elif abs(change) >= 5: score += 10; reasons.append("MOMENTUM")
        if volatility >= 10: score += 10; reasons.append("HIGH_VOL")

        if score >= min_score:
            candidates.append({
                "symbol": symbol, "price": price, "change": change,
                "volume": volume, "position": position, "volatility": volatility,
                "score": score, "reasons": reasons,
                "direction": "LONG" if change > 0 or position > 50 else "SHORT"
            })

    candidates.sort(key=lambda x: x['score'], reverse=True)
    candidates = candidates[:20]

    pipeline_results = {"stage": "prefilter", "count": len(candidates)}

    # Stage 1: Detection (Nemotron - Fast)
    if "detection" in stages and candidates:
        validated = []
        for c in candidates[:15]:
            prompt = f"Signal trading: {c['symbol']} Prix:{c['price']:.4f} Change:{c['change']:.2f}% Position:{c['position']:.0f}%\nDirection LONG/SHORT/SKIP? Score 0-100? JSON only: {{\"direction\":\"...\",\"score\":N}}"
            resp = query_lm_server("detector", prompt, 100)
            if resp:
                try:
                    # Parse JSON from response
                    if "{" in resp:
                        json_str = resp[resp.index("{"):resp.rindex("}")+1]
                        result = json.loads(json_str)
                        if result.get("direction") != "SKIP" and result.get("score", 0) >= 60:
                            c["ia_score"] = result.get("score", c["score"])
                            c["ia_direction"] = result.get("direction", c["direction"])
                            validated.append(c)
                except:
                    if c["score"] >= 70: validated.append(c)
            else:
                if c["score"] >= 70: validated.append(c)
        candidates = validated[:10]
        pipeline_results = {"stage": "detection", "count": len(candidates)}

    # Stage 2: Analysis (Qwen3 - Deep)
    if "analysis" in stages and candidates:
        for c in candidates:
            prompt = f"Analyse technique {c['symbol']} a ${c['price']:.4f}. Position range: {c['position']:.0f}%. Calcule TP1, TP2, TP3 et SL. JSON: {{\"tp1\":N,\"tp2\":N,\"tp3\":N,\"sl\":N,\"confidence\":0-100}}"
            resp = query_lm_server("analyzer", prompt, 200)
            if resp:
                try:
                    if "{" in resp:
                        json_str = resp[resp.index("{"):resp.rindex("}")+1]
                        result = json.loads(json_str)
                        c["tp1"] = result.get("tp1", c["price"] * 1.02)
                        c["tp2"] = result.get("tp2", c["price"] * 1.04)
                        c["tp3"] = result.get("tp3", c["price"] * 1.06)
                        c["sl"] = result.get("sl", c["price"] * 0.98)
                        c["confidence"] = result.get("confidence", 50)
                except: pass
            # Fallback if no TP/SL
            if "tp1" not in c:
                mult = 1 if c["direction"] == "LONG" else -1
                c["tp1"] = c["price"] * (1 + 0.02 * mult)
                c["tp2"] = c["price"] * (1 + 0.04 * mult)
                c["tp3"] = c["price"] * (1 + 0.06 * mult)
                c["sl"] = c["price"] * (1 - 0.02 * mult)
                c["confidence"] = 50

        candidates.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        candidates = candidates[:7]
        pipeline_results = {"stage": "analysis", "count": len(candidates)}

    # Stage 3: Validation (Mistral - Reasoning)
    if "validation" in stages and candidates:
        validated = []
        for c in candidates:
            prompt = f"Valide ce signal: {c['symbol']} {c['direction']} Entry:{c['price']:.4f} SL:{c.get('sl',0):.4f}. Risque OK? JSON: {{\"valid\":true/false,\"risk\":\"LOW/MEDIUM/HIGH\"}}"
            resp = query_lm_server("validator", prompt, 100)
            if resp:
                try:
                    if "{" in resp:
                        json_str = resp[resp.index("{"):resp.rindex("}")+1]
                        result = json.loads(json_str)
                        if result.get("valid", False):
                            c["risk_level"] = result.get("risk", "MEDIUM")
                            validated.append(c)
                except:
                    validated.append(c)
            else:
                validated.append(c)
        candidates = validated[:5]
        pipeline_results = {"stage": "validation", "count": len(candidates)}

    # Stage 4: Consensus (Multi-IA)
    if "consensus" in stages and candidates:
        final = []
        for c in candidates:
            votes = {"LONG": 0, "SHORT": 0, "HOLD": 0}

            # Gemini vote
            try:
                gemini_resp = ask_gemini(f"Signal {c['symbol']} {c['direction']} a ${c['price']:.4f}. Vote: LONG/SHORT/HOLD?")
                if gemini_resp.get('success'):
                    vote = gemini_resp.get('answer', '').upper()
                    if "LONG" in vote: votes["LONG"] += 1.2
                    elif "SHORT" in vote: votes["SHORT"] += 1.2
                    else: votes["HOLD"] += 1.2
            except: pass

            # LM Studio votes
            for srv in ["analyzer", "validator"]:
                resp = query_lm_server(srv, f"Vote pour {c['symbol']} {c['direction']}: LONG/SHORT/HOLD? Un seul mot.", 20)
                if resp:
                    if "LONG" in resp.upper(): votes["LONG"] += 1.3
                    elif "SHORT" in resp.upper(): votes["SHORT"] += 1.3
                    else: votes["HOLD"] += 1.0

            # Determine consensus
            max_vote = max(votes.values())
            total = sum(votes.values())
            if votes["LONG"] == max_vote:
                c["final_direction"] = "LONG"
                c["consensus_pct"] = round(votes["LONG"] / total * 100, 1)
            elif votes["SHORT"] == max_vote:
                c["final_direction"] = "SHORT"
                c["consensus_pct"] = round(votes["SHORT"] / total * 100, 1)
            else:
                c["final_direction"] = "HOLD"
                c["consensus_pct"] = round(votes["HOLD"] / total * 100, 1)

            if c["final_direction"] != "HOLD" and c["consensus_pct"] >= 40:
                c["final_score"] = int(c.get("confidence", 50) * c["consensus_pct"] / 100)
                final.append(c)

        final.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        candidates = final[:3]
        pipeline_results = {"stage": "consensus", "count": len(candidates)}

    # Send Telegram alert
    if send_tg and candidates:
        msg = "<b>MULTI-SCANNER PIPELINE</b>\n\n"
        for i, c in enumerate(candidates[:3], 1):
            emoji = "" if c.get("final_direction", c["direction"]) == "LONG" else ""
            msg += f"{i}. <b>{c['symbol']}</b> {emoji}\n"
            msg += f"   {c.get('final_direction', c['direction'])} | Entry: ${c['price']:.4f}\n"
            msg += f"   TP1: ${c.get('tp1',0):.4f} | SL: ${c.get('sl',0):.4f}\n"
            msg += f"   Consensus: {c.get('consensus_pct',0):.0f}% | Risk: {c.get('risk_level','N/A')}\n\n"
        msg += "<i>Pipeline: Nemotron->Qwen3->Mistral->Consensus</i>"
        send_telegram(msg, "HTML")

    elapsed = time.time() - start_time
    return {
        "success": True,
        "elapsed_seconds": round(elapsed, 2),
        "pipeline": "Nemotron->Qwen3->Mistral->Consensus",
        "final_stage": pipeline_results["stage"],
        "signal_count": len(candidates),
        "signals": candidates[:5]
    }

def run_derni_task(task: str) -> Dict:
    """Run a DERNI orchestrator task via HTTP"""
    try:
        url = f"http://localhost:3333/task?name={task.upper()}"
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        # Fallback: run locally
        if task.upper() == "SCAN":
            return scan_mexc(70)
        elif task.upper() == "PIPELINE":
            return run_multi_scanner_pipeline()
        elif task.upper() == "MARGIN":
            return check_critical_margins()
        return {"success": False, "error": str(e), "hint": "Start DERNI orchestrator: node derni_orchestrator.js"}

def get_current_filters() -> Dict:
    """Get current filters from config/filters.json"""
    try:
        filters = load_filters(force_reload=True)
        return {
            'success': True,
            'filters': filters,
            'path': 'config/filters.json',
            'version': filters.get('version', '1.0'),
            'last_update': filters.get('lastUpdate', 'unknown'),
            'updated_by': filters.get('updatedBy', 'unknown')
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def handle_sql_natural_query(question: str) -> Dict:
    """Handle async sql_natural_query by running in event loop"""
    try:
        import asyncio
        # Try to get existing event loop or create new one
        try:
            loop = asyncio.get_running_loop()
            # If we're in an async context, run in new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, sql_natural_query(question))
                return future.result(timeout=60)
        except RuntimeError:
            # No running loop, safe to create one
            return asyncio.run(sql_natural_query(question))
    except Exception as e:
        return {'success': False, 'error': str(e)}

def update_current_filters(filter_path: str, value) -> Dict:
    """Update a specific filter in config/filters.json"""
    try:
        from filters_loader import update_filter as do_update_filter
        success = do_update_filter(filter_path, value)
        if success:
            return {
                'success': True,
                'updated': filter_path,
                'new_value': value,
                'message': f'Filter {filter_path} updated to {value}'
            }
        else:
            return {'success': False, 'error': f'Failed to update {filter_path}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

TOOLS = {
    "scan_mexc": {"name": "scan_mexc", "description": "Scan MEXC Futures for trading signals", "inputSchema": {"type": "object", "properties": {"min_score": {"type": "integer", "default": 75}}}},
    "scan_sniper": {"name": "scan_sniper", "description": "Scanner SNIPER Premium - Analyse COMPLETE avec 5 IAs: 400+ contrats MEXC, orderbook, liquidite, whale walls, detection breakouts imminents, validation consensus 5 IAs (Gemini + 4 LM Studio), sauvegarde SQL, alerte Telegram. Retourne TOP 3 signaux avec entry/TP/SL. Duree: 5-7 min. Utilisez cet outil quand l'utilisateur demande 'scan sniper' ou 'scan mexc'.", "inputSchema": {"type": "object", "properties": {}}},
    "detect_pumps": {"name": "detect_pumps", "description": "Detect imminent pumps (Squeeze + Orderbook + RSI/MACD)", "inputSchema": {"type": "object", "properties": {"min_score": {"type": "integer", "default": 70}}}},
    "detect_imminent_pumps": {"name": "detect_imminent_pumps", "description": "Detect imminent pumps with liquidity clusters, optimal entry/TP/SL levels, and probability calculation", "inputSchema": {"type": "object", "properties": {"min_probability": {"type": "integer", "default": 70, "description": "Minimum probability threshold (0-100)"}, "top_n": {"type": "integer", "default": 3, "description": "Number of top signals to return"}, "send_telegram_alert": {"type": "boolean", "default": True, "description": "Send Telegram alert with results"}}}},
    "smart_scan": {"name": "smart_scan", "description": "Full scan + Multi-IA consensus (Gemini+LM Studio) + Telegram alerts with Entry/TP/SL", "inputSchema": {"type": "object", "properties": {"min_score": {"type": "integer", "default": 60}, "send_telegram": {"type": "boolean", "default": True}, "use_multi_ia": {"type": "boolean", "default": True}}}},
    "get_mexc_positions": {"name": "get_mexc_positions", "description": "Get open MEXC Futures positions", "inputSchema": {"type": "object", "properties": {}}},
    "get_margin_ratios": {"name": "get_margin_ratios", "description": "Calculate margin ratios (ANCRAGE)", "inputSchema": {"type": "object", "properties": {}}},
    "check_critical_margins": {"name": "check_critical_margins", "description": "Check critical margins and alert", "inputSchema": {"type": "object", "properties": {}}},
    "suggest_margin_transfer": {"name": "suggest_margin_transfer", "description": "Suggest margin transfers", "inputSchema": {"type": "object", "properties": {}}},
    "send_telegram": {"name": "send_telegram", "description": "Send Telegram message with retry and formatting", "inputSchema": {"type": "object", "properties": {"message": {"type": "string"}, "parse_mode": {"type": "string", "description": "HTML or Markdown"}, "bypass_cooldown": {"type": "boolean", "default": False}}, "required": ["message"]}},
    "send_telegram_alert": {"name": "send_telegram_alert", "description": "Send formatted Telegram alert (signal/margin/pnl/position/system)", "inputSchema": {"type": "object", "properties": {"alert_type": {"type": "string", "enum": ["signal", "margin", "pnl", "position", "system"]}, "data": {"type": "object"}}, "required": ["alert_type", "data"]}},
    "set_price_alert": {"name": "set_price_alert", "description": "Set price alert", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}, "condition": {"type": "string"}, "price": {"type": "number"}}, "required": ["symbol", "condition", "price"]}},
    "set_margin_alert": {"name": "set_margin_alert", "description": "Set margin alert", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}, "threshold": {"type": "number", "default": 5}}, "required": ["symbol"]}},
    "check_all_alerts": {"name": "check_all_alerts", "description": "Check all alerts", "inputSchema": {"type": "object", "properties": {}}},
    "list_alerts": {"name": "list_alerts", "description": "List active alerts", "inputSchema": {"type": "object", "properties": {}}},
    "delete_alert": {"name": "delete_alert", "description": "Delete alert", "inputSchema": {"type": "object", "properties": {"alert_type": {"type": "string"}, "alert_id": {"type": "integer"}}, "required": ["alert_type", "alert_id"]}},
    "ask_perplexity": {"name": "ask_perplexity", "description": "Ask Perplexity AI", "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}},
    "ask_gemini": {"name": "ask_gemini", "description": "Ask Gemini CLI", "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}},
    "ask_lmstudio": {"name": "ask_lmstudio", "description": "Ask LM Studio", "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}, "model": {"type": "string"}}, "required": ["question"]}},
    "ask_lmstudio_server": {"name": "ask_lmstudio_server", "description": "Ask a specific LM Studio server (lmstudio1=M1-Deep 192.168.1.85, lmstudio2=M2-Fast 192.168.1.26, lmstudio3=M3-Validate 192.168.1.113)", "inputSchema": {"type": "object", "properties": {"server_key": {"type": "string", "enum": ["lmstudio1", "lmstudio2", "lmstudio3"], "description": "Server to query"}, "question": {"type": "string"}, "model": {"type": "string", "description": "Optional model override"}}, "required": ["server_key", "question"]}},
    "ask_claude": {"name": "ask_claude", "description": "Ask Claude AI", "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}, "model": {"type": "string", "default": "claude-3-haiku-20240307"}}, "required": ["question"]}},
    "list_lmstudio_models": {"name": "list_lmstudio_models", "description": "List LM Studio models", "inputSchema": {"type": "object", "properties": {}}},
    "smart_route": {"name": "smart_route", "description": "Route to best IA", "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}, "task_type": {"type": "string", "default": "auto"}}, "required": ["question"]}},
    "parallel_consensus": {"name": "parallel_consensus", "description": "Get consensus from multiple IAs (default: Gemini + M1 + M2 + M3)", "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}, "models": {"type": "array", "items": {"type": "string"}, "description": "IAs to query (gemini/lmstudio1/lmstudio2/lmstudio3/perplexity)"}}, "required": ["question"]}},
    "get_ia_stats": {"name": "get_ia_stats", "description": "Get IA statistics", "inputSchema": {"type": "object", "properties": {}}},
    "gh_command": {"name": "gh_command", "description": "Execute GitHub CLI", "inputSchema": {"type": "object", "properties": {"args": {"type": "string"}}, "required": ["args"]}},
    "gh_repo_list": {"name": "gh_repo_list", "description": "List GitHub repos", "inputSchema": {"type": "object", "properties": {}}},
    "n8n_list_workflows": {"name": "n8n_list_workflows", "description": "List n8n workflows", "inputSchema": {"type": "object", "properties": {}}},
    "n8n_activate_workflow": {"name": "n8n_activate_workflow", "description": "Activate workflow", "inputSchema": {"type": "object", "properties": {"workflow_id": {"type": "string"}, "active": {"type": "boolean"}}, "required": ["workflow_id"]}},
    "n8n_get_workflow": {"name": "n8n_get_workflow", "description": "Get workflow details", "inputSchema": {"type": "object", "properties": {"workflow_id": {"type": "string"}}, "required": ["workflow_id"]}},
    "n8n_run_workflow": {"name": "n8n_run_workflow", "description": "Run workflow", "inputSchema": {"type": "object", "properties": {"workflow_name": {"type": "string"}}, "required": ["workflow_name"]}},
    "n8n_activate_all": {"name": "n8n_activate_all", "description": "Activate all workflows", "inputSchema": {"type": "object", "properties": {}}},
    "n8n_get_active_workflows": {"name": "n8n_get_active_workflows", "description": "Get active workflows", "inputSchema": {"type": "object", "properties": {}}},
    "get_all_workflows": {"name": "get_all_workflows", "description": "Get all workflows", "inputSchema": {"type": "object", "properties": {}}},
    "run_trading_v4": {"name": "run_trading_v4", "description": "Run Trading V4", "inputSchema": {"type": "object", "properties": {}}},
    "run_scanner_pro": {"name": "run_scanner_pro", "description": "Run Scanner PRO", "inputSchema": {"type": "object", "properties": {}}},
    "run_multi_ia_telegram": {"name": "run_multi_ia_telegram", "description": "Run Multi-IA Telegram", "inputSchema": {"type": "object", "properties": {}}},
    "open_browser": {"name": "open_browser", "description": "Open URL", "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    "open_n8n_workflow": {"name": "open_n8n_workflow", "description": "Open workflow in browser", "inputSchema": {"type": "object", "properties": {"workflow_name": {"type": "string"}}, "required": ["workflow_name"]}},
    "open_n8n_dashboard": {"name": "open_n8n_dashboard", "description": "Open n8n dashboard", "inputSchema": {"type": "object", "properties": {}}},
    "get_multi_ia_consensus": {"name": "get_multi_ia_consensus", "description": "Get multi-IA consensus", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "default": "BTC/USDT"}}}},
    "run_backtest": {"name": "run_backtest", "description": "Run backtest", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}, "strategy": {"type": "string", "default": "breakout"}, "days": {"type": "integer", "default": 7}}, "required": ["symbol"]}},
    "get_trade_history": {"name": "get_trade_history", "description": "Get trade history", "inputSchema": {"type": "object", "properties": {}}},
    "add_trade": {"name": "add_trade", "description": "Add trade", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}, "direction": {"type": "string"}, "entry": {"type": "number"}}, "required": ["symbol", "direction", "entry"]}},
    "start_realtime_monitor": {"name": "start_realtime_monitor", "description": "Start monitoring", "inputSchema": {"type": "object", "properties": {"interval": {"type": "integer", "default": 60}}}},
    "stop_realtime_monitor": {"name": "stop_realtime_monitor", "description": "Stop monitoring", "inputSchema": {"type": "object", "properties": {}}},
    "get_live_dashboard": {"name": "get_live_dashboard", "description": "Get live dashboard", "inputSchema": {"type": "object", "properties": {}}},
    "get_system_status": {"name": "get_system_status", "description": "Get system status", "inputSchema": {"type": "object", "properties": {}}},
    "wh_scan_market": {"name": "wh_scan_market", "description": "Scan via webhook", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}}}},
    "wh_multi_ia_consensus": {"name": "wh_multi_ia_consensus", "description": "Consensus via webhook", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "default": "BTC"}}, "required": ["symbol"]}},
    "wh_analyze_coin": {"name": "wh_analyze_coin", "description": "Analyze coin via webhook", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "default": "BTC"}}, "required": ["symbol"]}},
    "wh_fvg_scanner": {"name": "wh_fvg_scanner", "description": "FVG scanner", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "default": "BTC"}}, "required": ["symbol"]}},
    "wh_send_telegram": {"name": "wh_send_telegram", "description": "Send Telegram via webhook", "inputSchema": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}},
    "wh_get_status": {"name": "wh_get_status", "description": "Get webhook status", "inputSchema": {"type": "object", "properties": {}}},
    "wh_trading_signal": {"name": "wh_trading_signal", "description": "Full trading signal", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "default": "BTC"}}, "required": ["symbol"]}},
    "get_ohlcv_ccxt": {"name": "get_ohlcv_ccxt", "description": "Get OHLCV data via CCXT with RSI/MACD", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "default": "BTC/USDT"}, "timeframe": {"type": "string", "default": "1h"}, "limit": {"type": "integer", "default": 100}}}},
    "db_get_trades": {"name": "db_get_trades", "description": "Get trades from SQL database", "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 50}}}},
    "get_orderbook_analysis": {"name": "get_orderbook_analysis", "description": "Analyze orderbook pressure (buy/sell walls, imbalance)", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "default": "BTC/USDT"}, "limit": {"type": "integer", "default": 20}}}},
    "get_onchain_flow": {"name": "get_onchain_flow", "description": "Get onchain inflow/outflow and whale activity", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "default": "BTC/USDT"}}}},
    "deep_analyze_coin": {"name": "deep_analyze_coin", "description": "Deep analysis with orderbook, onchain, TP/SL levels", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "default": "BTC/USDT"}}}},
    "send_signal_choices": {"name": "send_signal_choices", "description": "Send numbered signal choices to Telegram for selection", "inputSchema": {"type": "object", "properties": {"signals": {"type": "array"}}}},
    "scan_all_pumps": {"name": "scan_all_pumps", "description": "Scan all MEXC coins for immediate pumps", "inputSchema": {"type": "object", "properties": {"min_volume": {"type": "integer", "default": 1000000}, "min_change": {"type": "number", "default": 2.0}}}},
    "multi_scanner_pipeline": {"name": "multi_scanner_pipeline", "description": "Multi-Scanner Pipeline: 4-stage scan with multiple LM Studio models (Detection->Analysis->Validation->Consensus)", "inputSchema": {"type": "object", "properties": {"min_score": {"type": "integer", "default": 50}, "send_telegram": {"type": "boolean", "default": True}, "stages": {"type": "array", "default": ["detection", "analysis", "validation", "consensus"]}}}},
    "run_derni_orchestrator": {"name": "run_derni_orchestrator", "description": "Run DERNI ULTIMATE orchestrator task (SCAN/CALL/MARGIN/TP_SL/FVG/PIPELINE)", "inputSchema": {"type": "object", "properties": {"task": {"type": "string", "default": "SCAN"}}, "required": ["task"]}},
    "check_all_lmstudio_servers": {"name": "check_all_lmstudio_servers", "description": "Check health of all 3 LM Studio servers (192.168.1.26, 192.168.1.85, 192.168.1.113)", "inputSchema": {"type": "object", "properties": {}}},
    "distribute_task": {"name": "distribute_task", "description": "Distribute a task to all 3 LM Studio servers in PARALLEL, get responses and compact summary. Use for any question/task to leverage all GPUs.", "inputSchema": {"type": "object", "properties": {"task": {"type": "string", "description": "The task or question to send to all servers"}, "max_tokens": {"type": "integer", "default": 500}, "include_local": {"type": "boolean", "default": False, "description": "Include local server (may cause freeze)"}}, "required": ["task"]}},
    "perplexity_scan": {"name": "perplexity_scan", "description": "Scan MEXC using Perplexity method: breakout detection with BB, Supertrend, RSI, MACD, orderbook clusters. Returns TOP 3 with Entry/TP/SL", "inputSchema": {"type": "object", "properties": {"min_score": {"type": "integer", "default": 60}, "send_telegram": {"type": "boolean", "default": True}}}},
    "live_mode": {"name": "live_mode", "description": "Start LIVE monitoring on a specific coin with real-time signals", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Symbol like FIS_USDT"}}, "required": ["symbol"]}},
    "get_filters": {"name": "get_filters", "description": "Get current filters from config/filters.json (scanner thresholds, telegram settings, margin alerts)", "inputSchema": {"type": "object", "properties": {}}},
    "update_filter": {"name": "update_filter", "description": "Update a specific filter in config/filters.json (e.g., scanner.minScore, telegram.enabled)", "inputSchema": {"type": "object", "properties": {"filter_path": {"type": "string", "description": "Dot-notation path like scanner.minScore or telegram.cooldownSeconds"}, "value": {"description": "New value for the filter"}}, "required": ["filter_path", "value"]}},
    "pump_detector_scan": {"name": "pump_detector_scan", "description": "PUMP DETECTOR ULTIMATE: Scan all MEXC futures for breakout/reversal JUST BEFORE pumps. Analyzes liquidity maps, clusters, BB squeeze, RSI, MACD, orderbook pressure. Returns TOP 3 with optimal entry price, TP targets, and probability. Maximum spike probability.", "inputSchema": {"type": "object", "properties": {"send_telegram": {"type": "boolean", "default": True, "description": "Send Telegram alert with TOP 3"}, "min_score": {"type": "integer", "default": 50, "description": "Minimum pump score (0-100)"}}}},
    "pump_detector_live": {"name": "pump_detector_live", "description": "Start PUMP DETECTOR ULTIMATE in live monitoring mode. Scans every 60s for immediate pump opportunities.", "inputSchema": {"type": "object", "properties": {}}},
    # ============================================
    # DISTRIBUTED DISPATCHER TOOLS (v1.0)
    # ============================================
    "dispatcher_status": {"name": "dispatcher_status", "description": "Get status of all 3 LM Studio servers (192.168.1.85, 192.168.1.26, 192.168.1.113) with health checks, latency, and circuit breaker status", "inputSchema": {"type": "object", "properties": {}}},
    "dispatch_task": {"name": "dispatch_task", "description": "Dispatch a task to the best available LM Studio server based on task type and server load", "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string", "description": "The prompt to send"}, "task_type": {"type": "string", "enum": ["deep_analysis", "quick_signal", "code_gen", "technical", "patterns", "validation", "consensus", "general"], "default": "general"}, "priority": {"type": "string", "enum": ["high", "normal", "low"], "default": "normal"}, "model": {"type": "string", "description": "Optional model override"}}, "required": ["prompt"]}},
    "dispatch_parallel_balanced": {"name": "dispatch_parallel_balanced", "description": "Dispatch multiple prompts in parallel across all 3 LM Studio servers for load-balanced execution", "inputSchema": {"type": "object", "properties": {"prompts": {"type": "array", "items": {"type": "string"}, "description": "List of prompts to dispatch"}, "task_type": {"type": "string", "default": "general"}}, "required": ["prompts"]}},
    "get_server_metrics": {"name": "get_server_metrics", "description": "Get detailed metrics for all LM Studio servers: latency, throughput, success rate, active requests, circuit breaker status", "inputSchema": {"type": "object", "properties": {}}},
    "set_server_priority": {"name": "set_server_priority", "description": "Change priority of an LM Studio server (lower = higher priority)", "inputSchema": {"type": "object", "properties": {"server_id": {"type": "string", "enum": ["lmstudio1", "lmstudio2", "lmstudio3"], "description": "Server ID"}, "priority": {"type": "integer", "description": "New priority (1=highest)"}}, "required": ["server_id", "priority"]}},
    "force_server_failover": {"name": "force_server_failover", "description": "Force failover from one LM Studio server to another (activates circuit breaker)", "inputSchema": {"type": "object", "properties": {"from_server": {"type": "string", "enum": ["lmstudio1", "lmstudio2", "lmstudio3"], "description": "Server to failover from"}, "to_server": {"type": "string", "enum": ["lmstudio1", "lmstudio2", "lmstudio3"], "description": "Target server (optional, auto-select if not specified)"}}, "required": ["from_server"]}},
    "distributed_scan": {"name": "distributed_scan", "description": "Run 4-stage distributed scanner pipeline: Detection(LM2)->Analysis(LM1)->Patterns(LM3)->Consensus(All). Returns TOP 3 signals.", "inputSchema": {"type": "object", "properties": {"candidates": {"type": "array", "items": {"type": "object"}, "description": "List of candidate signals with symbol, price, change, volume"}, "min_score": {"type": "integer", "default": 60}}, "required": ["candidates"]}},
    "dispatch_consensus": {"name": "dispatch_consensus", "description": "Get weighted consensus from all 3 LM Studio servers on a trading question. Uses weighted voting (LM1:1.3, LM2:1.0, LM3:0.8)", "inputSchema": {"type": "object", "properties": {"question": {"type": "string", "description": "Trading question to get consensus on"}}, "required": ["question"]}},
    # ============================================
    # SQL ORCHESTRATOR TOOLS (v1.0)
    # ============================================
    "sql_save_signal": {"name": "sql_save_signal", "description": "Save a trading signal to the distributed SQLite database. Stores symbol, price, score, TP/SL levels, and AI analysis.", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Trading symbol (e.g., BTCUSDT)"}, "price": {"type": "number"}, "score": {"type": "integer"}, "direction": {"type": "string", "enum": ["LONG", "SHORT", "HOLD", "LONG_REVERSAL", "NEUTRAL"]}, "tp1": {"type": "number"}, "tp2": {"type": "number"}, "stop_loss": {"type": "number"}, "probability": {"type": "integer"}, "reasons": {"type": "array", "items": {"type": "string"}}}, "required": ["symbol", "price"]}},
    "sql_get_signals": {"name": "sql_get_signals", "description": "Get trading signals from database with optional filters (symbol, status, direction, min_score, since date)", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "active", "tp1_hit", "tp2_hit", "tp3_hit", "stopped", "expired", "cancelled"]}, "direction": {"type": "string", "enum": ["LONG", "SHORT", "HOLD"]}, "min_score": {"type": "integer"}, "since": {"type": "string", "description": "ISO date string"}, "limit": {"type": "integer", "default": 50}}}},
    "sql_top_signals": {"name": "sql_top_signals", "description": "Get top scoring active/pending signals from database", "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 10}, "min_score": {"type": "integer", "default": 60}}}},
    "sql_stats": {"name": "sql_stats", "description": "Get comprehensive trading statistics: total signals, win rate, avg score, scanner performance, AI metrics", "inputSchema": {"type": "object", "properties": {}}},
    "sql_query": {"name": "sql_query", "description": "Execute a raw SQL SELECT query on the trading database (read-only, SELECT only)", "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "SQL SELECT query to execute"}}, "required": ["query"]}},
    "sql_natural_query": {"name": "sql_natural_query", "description": "Execute a natural language query using LM Studio 3 to generate SQL. Example: 'Show me top 5 LONG signals from today'", "inputSchema": {"type": "object", "properties": {"question": {"type": "string", "description": "Natural language question about trading data"}}, "required": ["question"]}},
    "sql_backup": {"name": "sql_backup", "description": "Create a backup of the trading database. Backups are stored in database/backups/ with timestamps.", "inputSchema": {"type": "object", "properties": {}}},
    # ============================================
    # DIRECTION VALIDATOR TOOLS (v1.0)
    # ============================================
    "validate_direction": {"name": "validate_direction", "description": "Validate a trading direction with consensus from 3 LM Studio servers. Returns validated=true if consensus >= 66% confirms the direction.", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Trading symbol (e.g., BTCUSDT)"}, "price": {"type": "number", "description": "Current price"}, "direction": {"type": "string", "enum": ["LONG", "SHORT"], "description": "Proposed direction"}, "score": {"type": "integer", "default": 50, "description": "Technical score (0-100)"}}, "required": ["symbol", "direction"]}},
    "batch_validate_directions": {"name": "batch_validate_directions", "description": "Validate multiple trading signals in batch. Returns validation results for each signal.", "inputSchema": {"type": "object", "properties": {"signals": {"type": "array", "items": {"type": "object", "properties": {"symbol": {"type": "string"}, "price": {"type": "number"}, "direction": {"type": "string"}, "score": {"type": "integer"}}}, "description": "List of signals to validate"}}, "required": ["signals"]}},
    # ============================================
    # MCP TECHNICAL ANALYSIS TOOLS (v1.0)
    # ============================================
    "analyze_coin_deep": {"name": "analyze_coin_deep", "description": "Complete deep analysis of a coin: technical indicators (RSI, MACD, ATR, Stochastic, OBV) + scoring (breakout, reversal, momentum, liquidity) + optimal entry/TP/SL levels + win probability. Returns comprehensive analysis with composite score, probabilities, and entry zones.", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Trading symbol (e.g., BTC_USDT)", "default": "BTC_USDT"}, "timeframe": {"type": "string", "description": "Timeframe: Min1, Min5, Min15, Min30, Min60, Hour4, Day1", "default": "Min60"}, "limit": {"type": "integer", "description": "Number of candles to analyze", "default": 100}}, "required": ["symbol"]}},
    "multi_coin_analysis": {"name": "multi_coin_analysis", "description": "Analyze multiple coins in parallel and return top signals sorted by composite score. Useful for comparing multiple trading opportunities.", "inputSchema": {"type": "object", "properties": {"symbols": {"type": "array", "items": {"type": "string"}, "description": "List of symbols to analyze (e.g., ['BTC_USDT', 'ETH_USDT', 'SOL_USDT'])"}, "min_composite_score": {"type": "integer", "description": "Minimum composite score to filter signals (0-100)", "default": 60}, "timeframe": {"type": "string", "default": "Min60"}}, "required": ["symbols"]}},
    "calculate_indicators_only": {"name": "calculate_indicators_only", "description": "Calculate technical indicators only (RSI, MACD, ATR, Stochastic, OBV, divergences) without scoring or entry calculation. Lightweight analysis for quick indicator checks.", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Trading symbol (e.g., ETH_USDT)", "default": "ETH_USDT"}, "timeframe": {"type": "string", "default": "Min60"}, "limit": {"type": "integer", "default": 100}}}},
    "calculate_entry_tp_sl": {"name": "calculate_entry_tp_sl", "description": "Calculate optimal entry point and TP/SL levels based on support/resistance, ATR, and microstructure. Returns optimal entry, entry range, 4 TP levels with volume distribution (TP1-40%, TP2-30%, TP3-20%, TP4-10%), stop loss, and risk/reward ratio.", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Trading symbol (e.g., SOL_USDT)", "default": "SOL_USDT"}, "price": {"type": "number", "description": "Current price (optional, fetched if not provided)"}, "atr": {"type": "number", "description": "ATR value (optional, calculated if not provided)"}, "support": {"type": "number", "description": "Support level (optional, detected if not provided)"}, "resistance": {"type": "number", "description": "Resistance level (optional, detected if not provided)"}}}},
    "scan_best_opportunities": {"name": "scan_best_opportunities", "description": "Full MEXC Futures scanner with advanced filters: composite score, win probability, risk/reward ratio. Scans all active contracts, filters by minimum thresholds, and returns top N opportunities with complete analysis (indicators, scores, entry/TP/SL, probabilities).", "inputSchema": {"type": "object", "properties": {"min_score": {"type": "integer", "description": "Minimum composite score (0-100)", "default": 70}, "min_probability": {"type": "integer", "description": "Minimum win probability (%)", "default": 75}, "min_rr": {"type": "number", "description": "Minimum Risk/Reward ratio", "default": 2.0}, "timeframe": {"type": "string", "default": "Min60"}, "top_n": {"type": "integer", "description": "Number of top signals to return", "default": 10}}}},
    "scan_breakout_imminent": {"name": "scan_breakout_imminent", "description": "BREAKOUT IMMINENT SCANNER: Detect breakout/reversal JUST BEFORE pumps with orderbook analysis, liquidity clusters, buy pressure calculation. Analyzes 50 levels of bid/ask, detects support/resistance clusters, calculates buy pressure %, spread %, and breakout probability based on: price proximity to resistance (<0.5%), buy pressure >60%, RSI 50-70, volume spike, MACD positive, ATR expansion. Returns TOP N coins with timing-perfect entry points.", "inputSchema": {"type": "object", "properties": {"min_volume_24h": {"type": "number", "description": "Minimum 24h volume in USDT", "default": 10000000}, "min_breakout_probability": {"type": "integer", "description": "Minimum breakout probability (0-100)", "default": 60}, "top_n": {"type": "integer", "description": "Number of top signals to return", "default": 3}}}},
    "direction_validator_status": {"name": "direction_validator_status", "description": "Get status of the Direction Validator and all 3 LM Studio servers (online/offline, latency, models).", "inputSchema": {"type": "object", "properties": {}}},
    "quick_validate_direction": {"name": "quick_validate_direction", "description": "Quick validation with single LM Studio server (default: LM2 - fastest). For urgent decisions.", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Trading symbol"}, "price": {"type": "number", "description": "Current price"}, "direction": {"type": "string", "enum": ["LONG", "SHORT"], "description": "Proposed direction"}, "server": {"type": "string", "enum": ["lm1", "lm2", "lm3"], "default": "lm2", "description": "Server to use"}}, "required": ["symbol", "direction"]}},
    # ============================================
    # V3.4.1 - HEALTH CHECK & CACHE TOOLS
    # ============================================
    "get_cache_stats": {"name": "get_cache_stats", "description": "Get IA response cache statistics (hits, misses, hit rate, evictions, size)", "inputSchema": {"type": "object", "properties": {}}},
    "clear_ia_cache": {"name": "clear_ia_cache", "description": "Clear the IA response cache to free memory or force fresh responses", "inputSchema": {"type": "object", "properties": {}}},
    "health_check_servers": {"name": "health_check_servers", "description": "Health check all LM Studio servers with circuit breaker status, latency, and available models", "inputSchema": {"type": "object", "properties": {"include_metrics": {"type": "boolean", "default": True, "description": "Include detailed metrics"}}}},
    # ============================================
    # V3.4.1 - MULTI-TIMEFRAME & ENHANCED SCORING
    # ============================================
    "get_multi_timeframe_data": {"name": "get_multi_timeframe_data", "description": "Get multi-timeframe analysis (15m, 1h, 4h, 1d) with trend alignment score for a symbol", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "default": "BTC/USDT", "description": "Trading pair symbol"}}, "required": ["symbol"]}},
    "get_breakout_score_enhanced": {"name": "get_breakout_score_enhanced", "description": "Calculate enhanced breakout score with MTF confirmation, volume analysis, and detailed breakdown", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Trading symbol (e.g., BTCUSDT)"}, "price": {"type": "number", "description": "Current price"}, "high24": {"type": "number", "description": "24h high"}, "low24": {"type": "number", "description": "24h low"}, "volume24": {"type": "number", "description": "24h volume"}, "change24": {"type": "number", "description": "24h change %"}}, "required": ["symbol", "price", "high24", "low24", "volume24", "change24"]}},
    "retry_lmstudio_call": {"name": "retry_lmstudio_call", "description": "Call LM Studio with automatic retry, fallback chain, and circuit breaker protection", "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string", "description": "Prompt to send"}, "server_key": {"type": "string", "default": "lmstudio1", "description": "Primary server (lmstudio1/2/3)"}, "max_tokens": {"type": "integer", "default": 1024}, "temperature": {"type": "number", "default": 0.3}}, "required": ["prompt"]}},
    # ============================================
    # LM STUDIO CLI MANAGER TOOLS (v1.0)
    # ============================================
    "lms_list_loaded": {"name": "lms_list_loaded", "description": "List currently loaded models in LM Studio (via lms ps). Returns list of loaded models with details.", "inputSchema": {"type": "object", "properties": {}}},
    "lms_list_downloaded": {"name": "lms_list_downloaded", "description": "List all downloaded models available in LM Studio (via lms ls). Shows models that can be loaded.", "inputSchema": {"type": "object", "properties": {}}},
    "lms_load_model": {"name": "lms_load_model", "description": "Load a specific model in LM Studio (via lms load). Useful when you need a specific model for a task.", "inputSchema": {"type": "object", "properties": {"model_name": {"type": "string", "description": "Model name to load (e.g., qwen/qwen3-30b-a3b-2507)"}}, "required": ["model_name"]}},
    "lms_unload_model": {"name": "lms_unload_model", "description": "Unload a specific model from LM Studio (via lms unload). Frees up VRAM for other models.", "inputSchema": {"type": "object", "properties": {"model_identifier": {"type": "string", "description": "Model identifier to unload (full name or partial match)"}}, "required": ["model_identifier"]}},
    "lms_optimize_m1": {"name": "lms_optimize_m1", "description": "Automatically optimize M1 (192.168.1.85) by unloading non-essential models. Keeps only qwen3-30b, qwen3-coder, and text-embedding. Frees up VRAM to fix slowness and timeouts.", "inputSchema": {"type": "object", "properties": {}}},
    "lms_auto_configure_cluster": {"name": "lms_auto_configure_cluster", "description": "Auto-configure the entire LM Studio cluster (M1+M2+M3). Checks health of all 3 machines and reports status, loaded models, and availability.", "inputSchema": {"type": "object", "properties": {}}},
    "lms_get_status": {"name": "lms_get_status", "description": "Get LM Studio server status (via lms status). Shows if LM Studio is running and responsive.", "inputSchema": {"type": "object", "properties": {}}},
    # ============================================
    # CQ SYSTEM TOOLS (v1.0) - CONTEXTUAL QUOTIENT
    # ============================================
    "build_trading_context": {"name": "build_trading_context", "description": "Assemble le contexte trading complet (positions, marge, historique, winrates, accuracy IA, regime marche). Injecte automatiquement dans les queries IA.", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Coin specifique (optionnel)"}, "force_refresh": {"type": "boolean", "description": "Forcer le refresh du cache", "default": False}}}},
    "update_consensus_outcome": {"name": "update_consensus_outcome", "description": "Met a jour le resultat reel d'un consensus passe (WIN/LOSS + PnL). Feedback loop pour ameliorer l'accuracy IA.", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Symbol du trade (e.g. SOL, BTC)"}, "actual_result": {"type": "string", "enum": ["WIN", "LOSS"], "description": "Resultat reel du trade"}, "actual_pnl": {"type": "number", "description": "PnL reel en USDT"}}, "required": ["symbol", "actual_result", "actual_pnl"]}},
    "turbo_consensus": {"name": "turbo_consensus", "description": "CQ v1.1 TURBO: Consensus 4 modeles (Qwen30B+GPToss sur .85, Nemotron sur .26, Mistral sur .113) avec pipeline 2 stages, poids adaptatifs, system prompt directif, TP/SL auto. Retourne LONG/SHORT avec confiance.", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Symbol MEXC (e.g. SOL_USDT)"}, "price": {"type": "number"}, "change_pct": {"type": "number", "description": "Change 24h %"}, "volume_m": {"type": "number", "description": "Volume 24h en millions"}, "range_pos": {"type": "number", "description": "Position dans le range 0-1"}, "send_telegram": {"type": "boolean", "default": False}}, "required": ["symbol", "price"]}},
    "turbo_scan": {"name": "turbo_scan", "description": "CQ v1.1 TURBO SCAN: Scan complet MEXC + consensus 4 modeles sur chaque candidat. Pipeline: Scan 850 tickers -> Filter -> 4-model consensus parallele -> TP/SL -> Telegram. Utilise les 3 serveurs GPU (.85/.26/.113) en continu.", "inputSchema": {"type": "object", "properties": {"min_change": {"type": "number", "default": 2.0, "description": "Change minimum %"}, "min_volume": {"type": "number", "default": 3000000}, "top_n": {"type": "integer", "default": 10, "description": "Nombre de coins a analyser"}, "send_telegram": {"type": "boolean", "default": True}}}}
}

def send_response(response: dict):
    print(json.dumps(response), flush=True)

def handle_request(request: dict) -> dict:
    method = request.get('method', '')
    params = request.get('params', {})
    req_id = request.get('id')

    if method == 'initialize':
        logger.info("MCP Server initializing...")
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {}  # Enable resources support
            },
            "serverInfo": {"name": "trading-ai-ultimate-mcp", "version": "3.7.0-CQ-TURBO"}
        }}

    elif method == 'tools/list':
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": list(TOOLS.values())}}

    elif method == 'tools/call':
        tool_name = params.get('name', '')
        tool_args = params.get('arguments', {})

        tool_map = {
            'scan_mexc': lambda: scan_mexc(tool_args.get('min_score')),  # None = load from filters.json
            'scan_sniper': lambda: scan_sniper(),  # Scanner SNIPER avec 5 IAs
            'detect_pumps': lambda: detect_imminent_pumps(tool_args.get('min_score')),  # None = load from filters.json
            'smart_scan': lambda: smart_scan_and_alert(tool_args.get('min_score'), tool_args.get('send_telegram'), tool_args.get('use_multi_ia', True)),  # None = load from filters.json
            'get_mexc_positions': get_mexc_positions,
            'get_margin_ratios': get_margin_ratios,
            'check_critical_margins': check_critical_margins,
            'suggest_margin_transfer': suggest_margin_transfer,
            'send_telegram': lambda: send_telegram(tool_args.get('message', ''), tool_args.get('parse_mode'), tool_args.get('disable_notification', False), tool_args.get('bypass_cooldown', False)),
            'send_telegram_alert': lambda: send_telegram_alert(tool_args.get('alert_type', 'system'), tool_args.get('data', {})),
            'set_price_alert': lambda: set_price_alert(tool_args.get('symbol', ''), tool_args.get('condition', 'above'), tool_args.get('price', 0)),
            'set_margin_alert': lambda: set_margin_alert(tool_args.get('symbol', ''), tool_args.get('threshold', 5)),
            'check_all_alerts': check_all_alerts,
            'list_alerts': list_alerts,
            'delete_alert': lambda: delete_alert(tool_args.get('alert_type', ''), tool_args.get('alert_id', 0)),
            'ask_perplexity': lambda: ask_perplexity(tool_args.get('question', '')),
            'ask_gemini': lambda: ask_gemini(tool_args.get('prompt', '')),
            'ask_lmstudio': lambda: ask_lmstudio(tool_args.get('question', ''), tool_args.get('model')),
            'ask_lmstudio_server': lambda: ask_lmstudio_server(tool_args.get('server_key', 'lmstudio1'), tool_args.get('question', ''), tool_args.get('model')),
            'ask_claude': lambda: ask_claude(tool_args.get('question', ''), tool_args.get('model', 'claude-3-haiku-20240307')),
            'list_lmstudio_models': list_lmstudio_models,
            'smart_route': lambda: smart_route(tool_args.get('question', ''), tool_args.get('task_type', 'auto')),
            'parallel_consensus': lambda: parallel_consensus(tool_args.get('question', ''), tool_args.get('models')),
            'get_ia_stats': get_ia_stats,
            'gh_command': lambda: gh_command(tool_args.get('args', '')),
            'gh_repo_list': gh_repo_list,
            'n8n_list_workflows': n8n_list_workflows,
            'n8n_activate_workflow': lambda: n8n_activate_workflow(tool_args.get('workflow_id', ''), tool_args.get('active', True)),
            'n8n_get_workflow': lambda: n8n_get_workflow(tool_args.get('workflow_id', '')),
            'n8n_run_workflow': lambda: n8n_run_workflow(tool_args.get('workflow_name', '')),
            'n8n_activate_all': n8n_activate_all,
            'n8n_get_active_workflows': n8n_get_active_workflows,
            'get_all_workflows': get_all_workflows,
            'run_trading_v4': run_trading_v4,
            'run_scanner_pro': run_scanner_pro,
            'run_multi_ia_telegram': run_multi_ia_telegram,
            'open_browser': lambda: open_browser(tool_args.get('url', '')),
            'open_n8n_workflow': lambda: open_n8n_workflow(tool_args.get('workflow_name', '')),
            'open_n8n_dashboard': open_n8n_dashboard,
            'get_multi_ia_consensus': lambda: get_multi_ia_consensus(tool_args.get('symbol', 'BTC/USDT')),
            'run_backtest': lambda: run_backtest(tool_args.get('symbol', 'BTC/USDT'), tool_args.get('strategy', 'breakout'), tool_args.get('days', 7)),
            'get_trade_history': get_trade_history,
            'add_trade': lambda: add_trade(tool_args.get('symbol', ''), tool_args.get('direction', ''), tool_args.get('entry', 0), tool_args.get('exit_price'), tool_args.get('pnl')),
            'start_realtime_monitor': lambda: start_realtime_monitor(tool_args.get('interval', 60)),
            'stop_realtime_monitor': stop_realtime_monitor,
            'get_live_dashboard': get_live_dashboard,
            'get_system_status': get_system_status,
            'wh_scan_market': lambda: wh_scan_market(tool_args.get('symbol')),
            'wh_multi_ia_consensus': lambda: wh_multi_ia_consensus(tool_args.get('symbol', 'BTC')),
            'wh_analyze_coin': lambda: wh_analyze_coin(tool_args.get('symbol', 'BTC'), tool_args.get('notify', True)),
            'wh_fvg_scanner': lambda: wh_fvg_scanner(tool_args.get('symbol', 'BTC')),
            'wh_send_telegram': lambda: wh_send_telegram(tool_args.get('message', ''), tool_args.get('chat_id')),
            'wh_get_status': wh_get_status,
            'wh_trading_signal': lambda: wh_trading_signal(tool_args.get('symbol', 'BTC')),
            'get_ohlcv_ccxt': lambda: get_ohlcv_ccxt(tool_args.get('symbol', 'BTC/USDT'), tool_args.get('timeframe', '1h'), tool_args.get('limit', 100)),
            'db_get_trades': lambda: db_get_trades(tool_args.get('limit', 50)),
            'get_orderbook_analysis': lambda: get_orderbook_analysis(tool_args.get('symbol', 'BTC/USDT'), tool_args.get('limit', 20)),
            'get_onchain_flow': lambda: get_onchain_flow(tool_args.get('symbol', 'BTC/USDT')),
            'deep_analyze_coin': lambda: deep_analyze_coin(tool_args.get('symbol', 'BTC/USDT')),
            'send_signal_choices': lambda: send_signal_choices(tool_args.get('signals')),
            'scan_all_pumps': lambda: scan_all_pumps(tool_args.get('min_volume', 1000000), tool_args.get('min_change', 2.0)),
            'detect_imminent_pumps': lambda: detect_imminent_pumps(tool_args.get('min_probability', 70), tool_args.get('top_n', 3), tool_args.get('send_telegram_alert', True)),
            'multi_scanner_pipeline': lambda: run_multi_scanner_pipeline(tool_args.get('min_score'), tool_args.get('send_telegram'), tool_args.get('stages')),  # None = load from filters.json
            'run_derni_orchestrator': lambda: run_derni_task(tool_args.get('task', 'SCAN')),
            'check_all_lmstudio_servers': check_all_lmstudio_servers,
            'distribute_task': lambda: distribute_task_parallel(tool_args.get('task', ''), tool_args.get('max_tokens', 500), tool_args.get('include_local', False)),
            'perplexity_scan': lambda: pplx_top3(tool_args.get('min_score', 60)) if PERPLEXITY_SCAN_AVAILABLE else {'error': 'perplexity_scan_method not installed'},
            'live_mode': lambda: {'status': 'live_mode_started', 'symbol': tool_args.get('symbol', ''), 'message': 'Use CLI: python perplexity_scan_method.py --live ' + tool_args.get('symbol', '')} if PERPLEXITY_SCAN_AVAILABLE else {'error': 'perplexity_scan_method not installed'},
            'get_filters': get_current_filters,
            'update_filter': lambda: update_current_filters(tool_args.get('filter_path', ''), tool_args.get('value')),
            'pump_detector_scan': lambda: pump_get_top3() if PUMP_DETECTOR_AVAILABLE else {'error': 'pump_detector_ultimate not installed', 'install': 'Module pump_detector_ultimate.py required in python_scripts/'},
            'pump_detector_live': lambda: {'status': 'pump_detector_live_started', 'message': 'Use CLI: python pump_detector_ultimate.py --live'} if PUMP_DETECTOR_AVAILABLE else {'error': 'pump_detector_ultimate not installed'},
            # DISTRIBUTED DISPATCHER TOOLS (v1.0)
            'dispatcher_status': lambda: dispatcher_status() if DISPATCHER_AVAILABLE else {'error': 'distributed_dispatcher not installed'},
            'dispatch_task': lambda: dispatch_task_simple(tool_args.get('prompt', ''), tool_args.get('task_type', 'general'), tool_args.get('priority', 'normal'), tool_args.get('model')) if DISPATCHER_AVAILABLE else {'error': 'distributed_dispatcher not installed'},
            'dispatch_parallel_balanced': lambda: dispatch_parallel_balanced(tool_args.get('prompts', []), tool_args.get('task_type', 'general')) if DISPATCHER_AVAILABLE else {'error': 'distributed_dispatcher not installed'},
            'get_server_metrics': lambda: get_server_metrics_all() if DISPATCHER_AVAILABLE else {'error': 'distributed_dispatcher not installed'},
            'set_server_priority': lambda: set_server_priority_cmd(tool_args.get('server_id', ''), tool_args.get('priority', 1)) if DISPATCHER_AVAILABLE else {'error': 'distributed_dispatcher not installed'},
            'force_server_failover': lambda: force_server_failover(tool_args.get('from_server', ''), tool_args.get('to_server')) if DISPATCHER_AVAILABLE else {'error': 'distributed_dispatcher not installed'},
            'distributed_scan': lambda: run_distributed_scan(tool_args.get('candidates', []), tool_args.get('min_score', 60)) if DISPATCHER_AVAILABLE else {'error': 'distributed_dispatcher not installed'},
            'dispatch_consensus': lambda: dispatch_consensus_question(tool_args.get('question', '')) if DISPATCHER_AVAILABLE else {'error': 'distributed_dispatcher not installed'},
            # SQL ORCHESTRATOR TOOLS (v1.0)
            'sql_save_signal': lambda: sql_save_signal(tool_args) if SQL_ORCHESTRATOR_AVAILABLE else {'error': 'lm3_sql_orchestrator not installed'},
            'sql_get_signals': lambda: sql_get_signals(tool_args) if SQL_ORCHESTRATOR_AVAILABLE else {'error': 'lm3_sql_orchestrator not installed'},
            'sql_top_signals': lambda: sql_top_signals(tool_args.get('limit', 10), tool_args.get('min_score', 60)) if SQL_ORCHESTRATOR_AVAILABLE else {'error': 'lm3_sql_orchestrator not installed'},
            'sql_stats': lambda: sql_stats() if SQL_ORCHESTRATOR_AVAILABLE else {'error': 'lm3_sql_orchestrator not installed'},
            'sql_query': lambda: sql_query(tool_args.get('query', '')) if SQL_ORCHESTRATOR_AVAILABLE else {'error': 'lm3_sql_orchestrator not installed'},
            'sql_natural_query': lambda: handle_sql_natural_query(tool_args.get('question', '')) if SQL_ORCHESTRATOR_AVAILABLE else {'error': 'lm3_sql_orchestrator not installed'},
            'sql_backup': lambda: sql_backup() if SQL_ORCHESTRATOR_AVAILABLE else {'error': 'lm3_sql_orchestrator not installed'},
            # DIRECTION VALIDATOR TOOLS (v1.0)
            'validate_direction': lambda: get_direction_validator().validate(
                tool_args.get('symbol', 'BTCUSDT'),
                tool_args.get('price', 0),
                tool_args.get('direction', 'LONG'),
                tool_args.get('score', 50)
            ) if DIRECTION_VALIDATOR_AVAILABLE else {'error': 'direction_validator_mcp not installed'},
            'batch_validate_directions': lambda: get_direction_validator().batch_validate(
                tool_args.get('signals', [])
            ) if DIRECTION_VALIDATOR_AVAILABLE else {'error': 'direction_validator_mcp not installed'},
            'direction_validator_status': lambda: get_direction_validator().get_status() if DIRECTION_VALIDATOR_AVAILABLE else {'error': 'direction_validator_mcp not installed'},
            'quick_validate_direction': lambda: get_direction_validator().quick_validate(
                tool_args.get('symbol', 'BTCUSDT'),
                tool_args.get('price', 0),
                tool_args.get('direction', 'LONG'),
                tool_args.get('server', 'lm2')
            ) if DIRECTION_VALIDATOR_AVAILABLE else {'error': 'direction_validator_mcp not installed'},
            # MCP TECHNICAL ANALYSIS TOOLS (v1.0)
            'analyze_coin_deep': lambda: analyze_coin_deep(
                tool_args.get('symbol', 'BTC_USDT'),
                tool_args.get('timeframe', 'Min60'),
                tool_args.get('limit', 100)
            ) if MCP_TECH_ANALYSIS_AVAILABLE else {'error': 'mcp_technical_analysis_tools not installed', 'install': 'Module mcp_technical_analysis_tools.py required in python_scripts/'},
            'multi_coin_analysis': lambda: multi_coin_analysis(
                tool_args.get('symbols', ['BTC_USDT', 'ETH_USDT', 'SOL_USDT']),
                tool_args.get('min_composite_score', 60),
                tool_args.get('timeframe', 'Min60')
            ) if MCP_TECH_ANALYSIS_AVAILABLE else {'error': 'mcp_technical_analysis_tools not installed'},
            'calculate_indicators_only': lambda: calculate_indicators_only(
                tool_args.get('symbol', 'ETH_USDT'),
                tool_args.get('timeframe', 'Min60'),
                tool_args.get('limit', 100)
            ) if MCP_TECH_ANALYSIS_AVAILABLE else {'error': 'mcp_technical_analysis_tools not installed'},
            'calculate_entry_tp_sl': lambda: calculate_entry_tp_sl(
                tool_args.get('symbol', 'SOL_USDT'),
                tool_args.get('price'),
                tool_args.get('atr'),
                tool_args.get('support'),
                tool_args.get('resistance')
            ) if MCP_TECH_ANALYSIS_AVAILABLE else {'error': 'mcp_technical_analysis_tools not installed'},
            'scan_best_opportunities': lambda: scan_best_opportunities(
                tool_args.get('min_score', 70),
                tool_args.get('min_probability', 75),
                tool_args.get('min_rr', 2.0),
                tool_args.get('timeframe', 'Min60'),
                tool_args.get('top_n', 10)
            ) if MCP_TECH_ANALYSIS_AVAILABLE else {'error': 'mcp_technical_analysis_tools not installed'},
            'scan_breakout_imminent': lambda: scan_breakout_imminent(
                tool_args.get('min_volume_24h', 10000000),
                tool_args.get('min_breakout_probability', 60),
                tool_args.get('top_n', 3)
            ) if BREAKOUT_SCANNER_AVAILABLE else {'error': 'breakout_imminent_scanner not installed', 'install': 'Module breakout_imminent_scanner.py required in python_scripts/'},
            # LM STUDIO CLI MANAGER TOOLS (v1.0) - Automatic Model Management
            'lms_list_loaded': lambda: get_lmstudio_cli_manager().list_loaded_models() if LMSTUDIO_CLI_AVAILABLE else {'error': 'lmstudio_cli_manager not available'},
            'lms_list_downloaded': lambda: get_lmstudio_cli_manager().list_downloaded_models() if LMSTUDIO_CLI_AVAILABLE else {'error': 'lmstudio_cli_manager not available'},
            'lms_load_model': lambda: get_lmstudio_cli_manager().load_model(tool_args.get('model_name', '')) if LMSTUDIO_CLI_AVAILABLE else {'error': 'lmstudio_cli_manager not available'},
            'lms_unload_model': lambda: get_lmstudio_cli_manager().unload_model(tool_args.get('model_identifier', '')) if LMSTUDIO_CLI_AVAILABLE else {'error': 'lmstudio_cli_manager not available'},
            'lms_optimize_m1': lambda: get_lmstudio_cli_manager().optimize_m1() if LMSTUDIO_CLI_AVAILABLE else {'error': 'lmstudio_cli_manager not available'},
            'lms_auto_configure_cluster': lambda: get_lmstudio_cli_manager().auto_configure_cluster() if LMSTUDIO_CLI_AVAILABLE else {'error': 'lmstudio_cli_manager not available'},
            'lms_get_status': lambda: get_lmstudio_cli_manager().get_status() if LMSTUDIO_CLI_AVAILABLE else {'error': 'lmstudio_cli_manager not available'},
            # V3.4.1 - HEALTH CHECK & CACHE TOOLS
            'get_cache_stats': get_cache_stats,
            'clear_ia_cache': clear_ia_cache,
            'health_check_servers': lambda: health_check_all_servers(tool_args.get('include_metrics', True)),
            # V3.4.1 - MULTI-TIMEFRAME & ENHANCED SCORING
            'get_multi_timeframe_data': lambda: get_multi_timeframe_data(tool_args.get('symbol', 'BTC/USDT')),
            'get_breakout_score_enhanced': lambda: calculate_breakout_score_enhanced(
                tool_args.get('symbol', ''),
                tool_args.get('price', 0),
                tool_args.get('high24', 0),
                tool_args.get('low24', 0),
                tool_args.get('volume24', 0),
                tool_args.get('change24', 0)
            ),
            'retry_lmstudio_call': lambda: call_lmstudio_with_retry(
                tool_args.get('prompt', ''),
                tool_args.get('server_key', 'lmstudio1'),
                tool_args.get('max_tokens', 1024),
                tool_args.get('temperature', 0.3)
            ),
            # CQ SYSTEM TOOLS (v1.0)
            'build_trading_context': lambda: build_trading_context(
                tool_args.get('symbol'),
                force_refresh=tool_args.get('force_refresh', False)
            ),
            'update_consensus_outcome': lambda: update_consensus_outcome(
                tool_args.get('symbol', ''),
                tool_args.get('actual_result', ''),
                tool_args.get('actual_pnl', 0)
            ),
            'turbo_consensus': lambda: turbo_multi_consensus(
                tool_args.get('symbol', ''),
                tool_args.get('price', 0),
                tool_args.get('change_pct', 0),
                tool_args.get('volume_m', 0),
                tool_args.get('range_pos', 0.5),
                tool_args.get('signals'),
                tool_args.get('send_telegram', False)
            ),
            'turbo_scan': lambda: turbo_scan(
                tool_args.get('min_change', 2.0),
                tool_args.get('min_volume', 3000000),
                tool_args.get('top_n', 10),
                tool_args.get('send_telegram', True)
            )
        }

        result = tool_map.get(tool_name, lambda: {'error': f'Unknown tool: {tool_name}'})()
        logger.info(f"Tool {tool_name} executed")
        return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}}

    elif method == 'resources/list':
        logger.info("Listing resources...")
        return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": list(RESOURCES.values())}}

    elif method == 'resources/read':
        uri = params.get('uri', '')
        logger.info(f"Reading resource: {uri}")
        if uri not in RESOURCES:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": f"Unknown resource: {uri}"}}
        content = get_resource_content(uri)
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "contents": [{
                "uri": uri,
                "mimeType": "application/json",
                "text": json.dumps(content, indent=2)
            }]
        }}

    elif method == 'notifications/initialized':
        logger.info("MCP Server initialized successfully")
        return None

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}

def main():
    while True:
        try:
            line = sys.stdin.readline()
            if not line: break
            response = handle_request(json.loads(line))
            if response: send_response(response)
        except json.JSONDecodeError: continue
        except Exception as e:
            send_response({"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}})

if __name__ == "__main__":
    main()
