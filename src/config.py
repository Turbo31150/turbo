"""JARVIS configuration — Real cluster, models, routing, project paths, auto-tune."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

JARVIS_VERSION = "10.2"

# ── Project paths (existing codebase) ──────────────────────────────────────
PATHS = {
    "carV1":          Path("F:/BUREAU/carV1"),
    "mcp_lmstudio":   Path("F:/BUREAU/MCP_MCPLMSTUDIO1"),
    "lmstudio_backup": Path("F:/BUREAU/LMSTUDIO_BACKUP"),
    "prod_intensive":  Path("F:/BUREAU/PROD_INTENSIVE_V1"),
    "trading_v2":      Path("F:/BUREAU/TRADING_V2_PRODUCTION"),
    "turbo":           Path("F:/BUREAU/turbo"),
    "jarvis_legacy":   Path("F:/BUREAU/JARVIS"),
    "disk_cleaner":    Path("F:/BUREAU/disk_cleaner"),
}

# ── Existing scripts index ─────────────────────────────────────────────────
SCRIPTS = {
    # Core orchestration
    "multi_ia_orchestrator": PATHS["carV1"] / "python_scripts/core/multi_ia_orchestrator.py",
    "unified_orchestrator":  PATHS["carV1"] / "python_scripts/core/unified_orchestrator.py",
    "gpu_pipeline":          PATHS["carV1"] / "python_scripts/core/gpu_pipeline.py",
    # Scanners
    "mexc_scanner":          PATHS["carV1"] / "python_scripts/scanners/mexc_scanner.py",
    "breakout_detector":     PATHS["carV1"] / "python_scripts/scanners/breakout_detector.py",
    "gap_detector":          PATHS["carV1"] / "python_scripts/scanners/gap_detector.py",
    # Utils
    "live_data_connector":   PATHS["carV1"] / "python_scripts/utils/live_data_connector.py",
    "coinglass_client":      PATHS["carV1"] / "python_scripts/utils/coinglass_client.py",
    "position_tracker":      PATHS["carV1"] / "python_scripts/utils/position_tracker.py",
    "perplexity_client":     PATHS["carV1"] / "python_scripts/utils/perplexity_client.py",
    # Strategies
    "all_strategies":        PATHS["carV1"] / "python_scripts/strategies/all_strategies.py",
    "advanced_strategies":   PATHS["carV1"] / "python_scripts/strategies/advanced_strategies.py",
    # Trading MCP (the big one — 70+ tools)
    "trading_mcp_v3":        PATHS["trading_v2"] / "trading_mcp_ultimate_v3.py",
    "lmstudio_mcp_bridge":   PATHS["lmstudio_backup"] / "mcp_configs/lmstudio_mcp_bridge.py",
    # Pipelines
    "pipeline_intensif_v2":  PATHS["prod_intensive"] / "scripts/pipeline_intensif_v2.py",
    "pipeline_intensif":     PATHS["mcp_lmstudio"] / "scripts/pipeline_intensif.py",
    # Trading scripts
    "river_scalp_1min":      PATHS["trading_v2"] / "scripts/river_scalp_1min.py",
    "execute_trident":       PATHS["trading_v2"] / "scripts/execute_trident.py",
    "sniper_breakout":       PATHS["trading_v2"] / "scripts/sniper_breakout.py",
    "sniper_10cycles":       PATHS["trading_v2"] / "scripts/sniper_10cycles.py",
    "auto_cycle_10":         PATHS["trading_v2"] / "scripts/auto_cycle_10.py",
    "hyper_scan_v2":         PATHS["trading_v2"] / "scripts/hyper_scan_v2.py",
    # Voice
    "voice_driver":          PATHS["trading_v2"] / "voice_system/voice_driver.py",
    "voice_jarvis":          PATHS["trading_v2"] / "voice_system/voice_jarvis.py",
    "commander_v2":          PATHS["trading_v2"] / "voice_system/commander_v2.py",
    # Dashboard & GUI
    "dashboard":             PATHS["mcp_lmstudio"] / "dashboard/app.py",
    "jarvis_gui":            PATHS["trading_v2"] / "scripts/jarvis_gui.py",
    "jarvis_api":            PATHS["trading_v2"] / "scripts/jarvis_api.py",
    "jarvis_widget":         PATHS["trading_v2"] / "scripts/jarvis_widget.py",
    # JARVIS Legacy (F:\BUREAU\JARVIS)
    "jarvis_main":           PATHS["jarvis_legacy"] / "jarvis.py",
    "jarvis_mcp_legacy":     PATHS["jarvis_legacy"] / "jarvis_mcp_server.py",
    "fs_agent":              PATHS["jarvis_legacy"] / "fs_agent.py",
    "master_interaction":    PATHS["jarvis_legacy"] / "master_interaction_node.py",
    # Disk Cleaner
    "disk_cleaner":          PATHS["disk_cleaner"] / "disk_cleaner.py",
}


@dataclass
class LMStudioNode:
    name: str
    url: str
    role: str
    gpus: int = 0
    vram_gb: int = 0
    default_model: str = ""
    weight: float = 1.0
    use_cases: list[str] = field(default_factory=list)


@dataclass
class OllamaNode:
    name: str
    url: str
    role: str
    backend: str = "ollama"
    default_model: str = "minimax-m2.5:cloud"
    weight: float = 1.0
    use_cases: list[str] = field(default_factory=list)


@dataclass
class JarvisConfig:
    version: str = JARVIS_VERSION
    mode: str = "DUAL_CORE"

    # ── Real cluster ─────────────────────────────────────────────────────
    # M1: RTX 2060 (12GB) + 4x GTX 1660 SUPER (6GB) + RTX 3080 (10GB) = 46GB
    # M2: 3 GPU, 24GB VRAM
    # Total: 9 GPU, ~70 GB VRAM
    # Backend: llama.cpp v2.3.0 CUDA12 + Flash Attention + custom GPU ratio
    lm_nodes: list[LMStudioNode] = field(default_factory=lambda: [
        LMStudioNode(
            "M1", os.getenv("LM_STUDIO_1_URL", "http://10.5.0.2:1234"),
            "deep_analysis", gpus=6, vram_gb=46,
            default_model="qwen/qwen3-30b-a3b-2507", weight=1.5,
            use_cases=["Analyse technique", "Raisonnement", "Patterns complexes",
                       "Freeform", "Voice commands", "Auto-apprentissage"],
        ),
        LMStudioNode(
            "M2", os.getenv("LM_STUDIO_2_URL", "http://192.168.1.26:1234"),
            "fast_inference", gpus=3, vram_gb=24,
            default_model="deepseek-coder-v2-lite-instruct", weight=1.0,
            use_cases=["Code generation", "Quick responses", "Trading signals"],
        ),
    ])

    default_model: str = field(
        default_factory=lambda: os.getenv("LM_STUDIO_DEFAULT_MODEL", "qwen/qwen3-30b-a3b-2507")
    )

    # ── Ollama nodes ──────────────────────────────────────────────────────
    ollama_nodes: list[OllamaNode] = field(default_factory=lambda: [
        OllamaNode(
            "OL1", os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
            "cloud_inference",
            default_model=os.getenv("OLLAMA_DEFAULT_MODEL", "qwen3:1.7b"), weight=1.0,
            use_cases=["Recherche web", "Raisonnement cloud", "Resume", "Correction vocale"],
        ),
    ])

    # ── Model catalog (all available models) ──────────────────────────────
    # M1 permanent: qwen3-30b (18.56 GB, ctx 32768, MoE 3B actifs)
    # M1 on-demand: qwen3-coder-30b (code), devstral (dev), gpt-oss-20b (general)
    # M2 permanent: deepseek-coder-v2-lite (code rapide)
    # Ollama: qwen3:1.7b (local) + cloud (minimax, glm-5, kimi)
    models: dict[str, str] = field(default_factory=lambda: {
        "default":    "qwen/qwen3-30b-a3b-2507",        # M1 — toujours charge
        "fast":       "qwen/qwen3-30b-a3b-2507",        # M1 — MoE rapide (3B actifs)
        "coding":     "deepseek-coder-v2-lite-instruct", # M2 — code rapide
        "coding_m1":  "qwen/qwen3-coder-30b",           # M1 — code specialise (on-demand)
        "dev":        "mistralai/devstral-small-2-2512", # M1 — dev tasks (on-demand)
        "general":    "openai/gpt-oss-20b",              # M1 — general purpose (on-demand)
        "embeddings": "text-embedding-nomic-embed-text-v1.5",
    })

    # ── Ollama model catalog (local + cloud) ──────────────────────────────
    ollama_models: dict[str, str] = field(default_factory=lambda: {
        "correction": "qwen3:1.7b",          # Local — correction vocale (1.36 GB)
        "research":   "minimax-m2.5:cloud",   # Cloud — recherche web + sous-agents
        "reasoning":  "glm-5:cloud",          # Cloud — raisonnement avance
        "general":    "kimi-k2.5:cloud",      # Cloud — polyvalent
    })

    # ── Routing rules (M1 + M2 + OL1) ────────────────────────────────────
    routing: dict[str, list[str]] = field(default_factory=lambda: {
        "short_answer":    ["M1"],
        "deep_analysis":   ["M1"],
        "trading_signal":  ["M1", "OL1"],
        "code_generation": ["M2", "M1"],
        "validation":      ["M1", "M2"],
        "critical":        ["M1", "OL1"],
        "consensus":       ["M1", "OL1"],
        "web_research":    ["OL1"],
        "reasoning":       ["M1", "OL1"],
        "voice_correction": ["OL1"],
        "auto_learn":      ["M1"],
        "embedding":       ["M1"],
    })

    # ── Commander Mode routing (agent + IA per task type) ──────────────
    commander_routing: dict[str, list[dict]] = field(default_factory=lambda: {
        "code": [
            {"agent": "ia-fast", "ia": "M2", "role": "coder"},
            {"agent": "ia-check", "ia": "M1", "role": "reviewer"},
        ],
        "analyse": [
            {"agent": "ia-deep", "ia": "M1", "role": "analyzer"},
        ],
        "trading": [
            {"agent": "ia-trading", "ia": "M1", "role": "scanner"},
            {"agent": None, "ia": "OL1", "role": "web_data"},
            {"agent": "ia-check", "ia": "M1", "role": "validator"},
        ],
        "systeme": [
            {"agent": "ia-system", "ia": None, "role": "executor"},
        ],
        "web": [
            {"agent": None, "ia": "OL1", "role": "searcher"},
            {"agent": "ia-deep", "ia": "M1", "role": "synthesizer"},
        ],
        "simple": [
            {"agent": None, "ia": "M1", "role": "responder"},
        ],
    })

    # ── Inference parameters (optimized) ──────────────────────────────────
    temperature: float = 0.4
    max_tokens: int = 8192
    # Fast path: lower tokens for quick responses (voice, commands)
    fast_max_tokens: int = 256
    # Deep analysis: more tokens for thorough analysis
    deep_max_tokens: int = 16384

    # ── Connection settings ───────────────────────────────────────────────
    # httpx timeout tuning — IMPORTANT: 127.0.0.1 NOT localhost (IPv6 10s penalty)
    connect_timeout: float = 5.0      # TCP connection timeout
    inference_timeout: float = 120.0   # Full inference timeout
    fast_timeout: float = 10.0        # Quick queries (voice, commands)
    warmup_timeout: float = 15.0      # Model warmup
    health_timeout: float = 3.0       # Health checks

    # ── Auto-tune (adapts routing based on latency) ───────────────────────
    # Latency thresholds: if M1 > threshold, prefer M2 or OL1
    latency_threshold_ms: int = 3000   # Switch to fallback above this
    # Track last known latencies (updated by warmup/benchmark)
    _latency_cache: dict[str, int] = field(default_factory=dict)

    # ── GPU Thermal thresholds (Celsius) ────────────────────────────────
    gpu_thermal_warning: int = 75    # Warning: preferer M2 pour code
    gpu_thermal_critical: int = 85   # Critique: deporter vers M2/OL1/GEMINI

    # ── Trading config ─────────────────────────────────────────────────────
    exchange: str = "mexc"
    trading_mode: str = "futures"
    pairs: list[str] = field(default_factory=lambda: [
        "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "SUI/USDT:USDT",
        "PEPE/USDT:USDT", "DOGE/USDT:USDT", "XRP/USDT:USDT", "ADA/USDT:USDT",
        "AVAX/USDT:USDT", "LINK/USDT:USDT",
    ])
    leverage: int = 10
    tp_percent: float = 0.4
    sl_percent: float = 0.25

    # ── Execution pipeline ────────────────────────────────────────────────
    mexc_api_key: str = field(default_factory=lambda: os.getenv("MEXC_API_KEY", ""))
    mexc_secret_key: str = field(default_factory=lambda: os.getenv("MEXC_SECRET_KEY", ""))
    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_TOKEN", ""))
    telegram_chat: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT", ""))
    dry_run: bool = field(default_factory=lambda: os.getenv("DRY_RUN", "true").lower() == "true")
    size_usdt: float = 10.0
    min_signal_score: float = 70.0
    max_signal_age_minutes: int = 60

    # ── DB paths ──────────────────────────────────────────────────────────
    db_trading: Path = field(default_factory=lambda: PATHS["carV1"] / "database/trading_latest.db")
    db_predictions: Path = field(default_factory=lambda: PATHS["trading_v2"] / "database/trading.db")

    def get_node_url(self, name: str) -> str | None:
        for node in self.lm_nodes:
            if node.name == name:
                return node.url
        return None

    def get_node(self, name: str) -> LMStudioNode | None:
        for node in self.lm_nodes:
            if node.name == name:
                return node
        return None

    def get_ollama_node(self, name: str = "OL1") -> OllamaNode | None:
        for node in self.ollama_nodes:
            if node.name == name:
                return node
        return None

    def get_ollama_url(self, name: str = "OL1") -> str | None:
        node = self.get_ollama_node(name)
        return node.url if node else None

    def route(self, task_type: str) -> list[str]:
        """Return node names for a given task type.

        Auto-tune: if a node's latency exceeds threshold, prefer the next one.
        """
        nodes = self.routing.get(task_type, ["M1"])
        if not self._latency_cache:
            return nodes
        # Sort by latency (fastest first), keeping order for equal latencies
        return sorted(nodes, key=lambda n: self._latency_cache.get(n, 0))

    def update_latency(self, node: str, latency_ms: int) -> None:
        """Update latency cache for auto-tune routing."""
        self._latency_cache[node] = latency_ms

    def get_timeout(self, mode: str = "default") -> float:
        """Get appropriate timeout for the mode."""
        return {
            "fast": self.fast_timeout,
            "inference": self.inference_timeout,
            "health": self.health_timeout,
            "warmup": self.warmup_timeout,
        }.get(mode, self.inference_timeout)

    def get_model_for_task(self, task_type: str) -> tuple[str, str]:
        """Return (node_name, model_id) for a task type.

        Uses routing + model catalog to find the best model.
        """
        nodes = self.route(task_type)
        if not nodes:
            return ("M1", self.default_model)
        primary = nodes[0]
        if primary == "OL1":
            ol = self.get_ollama_node("OL1")
            return ("OL1", ol.default_model if ol else "qwen3:1.7b")
        node = self.get_node(primary)
        return (primary, node.default_model if node else self.default_model)


config = JarvisConfig()
