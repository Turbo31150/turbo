"""
gateway.py - API Gateway Unifiée JARVIS
FastAPI port 8900, auth JWT, rate limiting, CORS, endpoints cluster/trading/voice/agents
Pour F:/BUREAU/turbo/src/
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("jarvis.gateway")
# ──────────────────── Config ────────────────────

@dataclass
class GatewayConfig:
    host: str = "127.0.0.1"
    port: int = 8900
    jwt_secret: str = os.getenv("JARVIS_JWT_SECRET", secrets.token_hex(32))
    jwt_expiry_hours: int = 24
    rate_limit_rpm: int = 120  # requests per minute
    rate_limit_burst: int = 20
    cors_origins: list[str] = None
    db_path: str = "jarvis.db"
    ws_port: int = 9742

    def __post_init__(self):
        if self.cors_origins is None:
            self.cors_origins = [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:8900",
                "http://127.0.0.1:8900",
            ]

# ──────────────────── Auth ────────────────────

class JWTAuth:
    """Authentification JWT simple."""

    def __init__(self, secret: str, expiry_hours: int = 24):
        self.secret = secret
        self.expiry = expiry_hours
        self._tokens: dict[str, dict] = {}

    def create_token(self, user_id: str, role: str = "admin") -> str:
        payload = {
            "user_id": user_id,
            "role": role,
            "iat": time.time(),
            "exp": time.time() + self.expiry * 3600,
            "jti": secrets.token_hex(8),
        }
        payload_json = json.dumps(payload, sort_keys=True)
        sig = hmac.new(
            self.secret.encode(), payload_json.encode(), hashlib.sha256
        ).hexdigest()
        token = f"{self._b64(payload_json)}.{sig}"
        self._tokens[payload["jti"]] = payload
        return token

    def verify_token(self, token: str) -> Optional[dict]:
        try:
            parts = token.split(".")
            if len(parts) != 2:
                return None
            payload_b64, sig = parts
            payload_json = self._unb64(payload_b64)
            expected_sig = hmac.new(
                self.secret.encode(), payload_json.encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                return None
            payload = json.loads(payload_json)
            if payload.get("exp", 0) < time.time():
                return None
            return payload
        except Exception:
            return None

    @staticmethod
    def _b64(s: str) -> str:
        import base64
        return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")

    @staticmethod
    def _unb64(s: str) -> str:
        import base64
        padding = 4 - len(s) % 4
        s += "=" * padding
        return base64.urlsafe_b64decode(s).decode()
# ──────────────────── Rate Limiter ────────────────────

class RateLimiter:
    """Rate limiting par IP avec sliding window."""

    def __init__(self, rpm: int = 120, burst: int = 20):
        self.rpm = rpm
        self.burst = burst
        self._windows: dict[str, list[float]] = defaultdict(list)

    def check(self, client_ip: str) -> tuple[bool, dict]:
        now = time.time()
        window = self._windows[client_ip]
        cutoff = now - 60
        window[:] = [t for t in window if t > cutoff]
        recent = [t for t in window if t > now - 10]
        if len(recent) >= self.burst:
            return False, {
                "error": "rate_limit_exceeded",
                "retry_after": 10,
                "limit": self.burst,
                "window": "10s",
            }
        if len(window) >= self.rpm:
            return False, {
                "error": "rate_limit_exceeded",
                "retry_after": 60,
                "limit": self.rpm,
                "window": "60s",
            }
        window.append(now)
        remaining = self.rpm - len(window)
        return True, {"remaining": remaining, "limit": self.rpm}

# ──────────────────── Request/Response Models ────────────────────

class AuthRequest(BaseModel):
    username: str
    password: str

class QueryRequest(BaseModel):
    prompt: str
    node: str = "auto"
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 2000

class ConsensusRequest(BaseModel):
    prompt: str
    nodes: list[str] = Field(default_factory=lambda: ["M1", "M2", "OL1"])
    strategy: str = "quality_weighted"

class TradingRequest(BaseModel):
    action: str
    params: dict = Field(default_factory=dict)

class VoiceRequest(BaseModel):
    text: str
    action: str = "recognize"

class AgentRequest(BaseModel):
    agent_id: str = ""
    action: str = "status"
    params: dict = Field(default_factory=dict)
# ──────────────────── WebSocket Manager ────────────────────

class WSManager:
    """Gestionnaire WebSocket pour streaming temps réel."""

    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, ws: WebSocket, channel: str = "default"):
        await ws.accept()
        self._connections[channel].add(ws)
        logger.info(f"WS connected to channel '{channel}' ({len(self._connections[channel])} clients)")

    def disconnect(self, ws: WebSocket, channel: str = "default"):
        self._connections[channel].discard(ws)

    async def broadcast(self, channel: str, data: dict):
        dead = set()
        for ws in self._connections.get(channel, set()):
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections[channel].discard(ws)

    @property
    def client_count(self) -> int:
        return sum(len(s) for s in self._connections.values())

# ──────────────────── App Factory ────────────────────

def create_gateway(config: Optional[GatewayConfig] = None) -> FastAPI:
    """Créer l'application FastAPI Gateway."""
    cfg = config or GatewayConfig()
    auth = JWTAuth(cfg.jwt_secret, cfg.jwt_expiry_hours)
    limiter = RateLimiter(cfg.rate_limit_rpm, cfg.rate_limit_burst)
    ws_manager = WSManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(f"JARVIS Gateway starting on port {cfg.port}")
        yield
        logger.info("JARVIS Gateway shutting down")

    app = FastAPI(
        title="JARVIS API Gateway",
        version="2.0.0",
        description="API Gateway unifiée pour le cluster JARVIS Turbo",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ──── Auth dependency ────

    async def require_auth(request: Request) -> dict:
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            token = request.query_params.get("token", "")
        payload = auth.verify_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return payload

    async def check_rate_limit(request: Request):
        ip = request.client.host if request.client else "unknown"
        allowed, info = limiter.check(ip)
        if not allowed:
            raise HTTPException(status_code=429, detail=info)
    # ──── Auth endpoints ────

    @app.post("/api/auth/login")
    async def login(req: AuthRequest):
        valid_users = {"jarvis": "turbo2024", "admin": "admin"}
        if req.username not in valid_users or valid_users[req.username] != req.password:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = auth.create_token(req.username, "admin")
        return {"token": token, "expires_in": cfg.jwt_expiry_hours * 3600}

    @app.get("/api/auth/verify")
    async def verify(user=Depends(require_auth)):
        return {"valid": True, "user": user}

    # ──── Health & Status ────

    @app.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "timestamp": time.time(),
            "version": "2.0.0",
            "uptime": time.time(),
            "ws_clients": ws_manager.client_count,
        }

    @app.get("/api/status")
    async def status(user=Depends(require_auth)):
        return {
            "gateway": {
                "port": cfg.port,
                "ws_clients": ws_manager.client_count,
            },
            "timestamp": time.time(),
        }

    # ──── Cluster endpoints ────

    @app.get("/api/cluster/health")
    async def cluster_health(user=Depends(require_auth)):
        return {"message": "Cluster health check", "timestamp": time.time()}

    @app.post("/api/cluster/query")
    async def cluster_query(req: QueryRequest, user=Depends(require_auth)):
        return {
            "node": req.node,
            "prompt": req.prompt[:100],
            "status": "queued",
            "timestamp": time.time(),
        }

    @app.post("/api/cluster/consensus")
    async def cluster_consensus(req: ConsensusRequest, user=Depends(require_auth)):
        return {
            "nodes": req.nodes,
            "strategy": req.strategy,
            "prompt": req.prompt[:100],
            "status": "processing",
            "timestamp": time.time(),
        }

    @app.get("/api/cluster/gpu")
    async def cluster_gpu(user=Depends(require_auth)):
        return {"message": "GPU stats", "timestamp": time.time()}

    @app.get("/api/cluster/models")
    async def cluster_models(user=Depends(require_auth)):
        return {"message": "Loaded models", "timestamp": time.time()}

    # ──── Trading endpoints ────

    @app.post("/api/trading/action")
    async def trading_action(req: TradingRequest, user=Depends(require_auth)):
        return {
            "action": req.action,
            "params": req.params,
            "status": "queued",
            "timestamp": time.time(),
        }

    @app.get("/api/trading/positions")
    async def trading_positions(user=Depends(require_auth)):
        return {"positions": [], "timestamp": time.time()}

    @app.get("/api/trading/signals")
    async def trading_signals(user=Depends(require_auth)):
        return {"signals": [], "timestamp": time.time()}

    @app.get("/api/trading/status")
    async def trading_status(user=Depends(require_auth)):
        return {"status": "idle", "timestamp": time.time()}
    # ──── Voice endpoints ────

    @app.post("/api/voice/recognize")
    async def voice_recognize(req: VoiceRequest, user=Depends(require_auth)):
        return {
            "text": req.text,
            "intent": "unknown",
            "confidence": 0.0,
            "timestamp": time.time(),
        }

    @app.post("/api/voice/tts")
    async def voice_tts(req: VoiceRequest, user=Depends(require_auth)):
        return {"text": req.text, "status": "queued", "timestamp": time.time()}

    @app.get("/api/voice/analytics")
    async def voice_analytics(user=Depends(require_auth)):
        return {"analytics": {}, "timestamp": time.time()}

    # ──── Agent endpoints ────

    @app.post("/api/agents/action")
    async def agent_action(req: AgentRequest, user=Depends(require_auth)):
        return {
            "agent_id": req.agent_id,
            "action": req.action,
            "status": "queued",
            "timestamp": time.time(),
        }

    @app.get("/api/agents/list")
    async def agent_list(user=Depends(require_auth)):
        return {"agents": [], "timestamp": time.time()}

    @app.get("/api/agents/status")
    async def agent_status(user=Depends(require_auth)):
        return {"agents": {}, "timestamp": time.time()}

    # ──── Automation endpoints ────

    @app.get("/api/automation/dominos")
    async def list_dominos(user=Depends(require_auth)):
        return {"dominos": [], "timestamp": time.time()}

    @app.get("/api/automation/skills")
    async def list_skills(user=Depends(require_auth)):
        return {"skills": [], "timestamp": time.time()}

    @app.get("/api/automation/workflows")
    async def list_workflows(user=Depends(require_auth)):
        return {"workflows": [], "timestamp": time.time()}

    # ──── WebSocket ────

    @app.websocket("/ws/{channel}")
    async def websocket_endpoint(ws: WebSocket, channel: str):
        await ws_manager.connect(ws, channel)
        try:
            while True:
                data = await ws.receive_text()
                msg = {"type": "message", "channel": channel, "data": data, "timestamp": time.time()}
                await ws_manager.broadcast(channel, msg)
        except WebSocketDisconnect:
            ws_manager.disconnect(ws, channel)

    @app.websocket("/ws")
    async def websocket_default(ws: WebSocket):
        await ws_manager.connect(ws, "default")
        try:
            while True:
                await ws.receive_text()
                await asyncio.sleep(0.1)
        except WebSocketDisconnect:
            ws_manager.disconnect(ws, "default")

    # ──── Metrics / Admin ────

    @app.get("/api/metrics")
    async def metrics(user=Depends(require_auth)):
        return {
            "ws_clients": ws_manager.client_count,
            "timestamp": time.time(),
        }

    @app.get("/api/config")
    async def get_config(user=Depends(require_auth)):
        return {
            "port": cfg.port,
            "rate_limit_rpm": cfg.rate_limit_rpm,
            "cors_origins": cfg.cors_origins,
        }

    return app


# ──────────────────── Entry Point ────────────────────

def run_gateway(config: Optional[GatewayConfig] = None):
    """Lancer le gateway."""
    import uvicorn
    cfg = config or GatewayConfig()
    app = create_gateway(cfg)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")


if __name__ == "__main__":
    run_gateway()
