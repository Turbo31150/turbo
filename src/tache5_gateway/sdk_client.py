"""
sdk_client.py - SDK Client Python JARVIS Gateway
Client async httpx, auto-retry exponentiel, auth JWT, WebSocket,
type hints complets, context manager
Pour /home/turbo/jarvis-m1-ops/src/
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import httpx

logger = logging.getLogger("jarvis.sdk")

# ──────────────────── Config ────────────────────

@dataclass
class SDKConfig:
    base_url: str = "http://127.0.0.1:8900"
    ws_url: str = "ws://127.0.0.1:8900/ws"
    username: str = "jarvis"
    password: str = "turbo2024"
    timeout: float = 30.0
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 30.0
    auto_login: bool = True

# ──────────────────── Response Wrapper ────────────────────

@dataclass
class APIResponse:
    status_code: int
    data: Any
    headers: dict = field(default_factory=dict)
    elapsed_ms: float = 0.0
    request_id: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    @property
    def error(self) -> Optional[str]:
        if not self.ok and isinstance(self.data, dict):
            return self.data.get("message") or self.data.get("detail") or str(self.data)
        return None


# ──────────────────── Retry Logic ────────────────────

class RetryHandler:
    """Gestion auto-retry avec backoff exponentiel."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def execute(self, fn, *args, **kwargs) -> Any:
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                return await fn(*args, **kwargs)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError) as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    logger.warning(
                        f"Retry {attempt + 1}/{self.max_retries}: {type(e).__name__}, "
                        f"waiting {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 502, 503, 504):
                    last_error = e
                    if attempt < self.max_retries:
                        retry_after = float(
                            e.response.headers.get("Retry-After", self.base_delay * (2 ** attempt))
                        )
                        delay = min(retry_after, self.max_delay)
                        logger.warning(f"Retry {attempt + 1}: HTTP {e.response.status_code}, waiting {delay:.1f}s")
                        await asyncio.sleep(delay)
                else:
                    raise
        raise last_error

# ──────────────────── Main SDK Client ────────────────────

class JarvisClient:
    """Client SDK async pour JARVIS Gateway."""

    def __init__(self, config: Optional[SDKConfig] = None):
        self.config = config or SDKConfig()
        self._client: Optional[httpx.AsyncClient] = None
        self._token: Optional[str] = None
        self._token_expires: float = 0
        self._retry = RetryHandler(
            self.config.max_retries,
            self.config.retry_base_delay,
            self.config.retry_max_delay,
        )

    # ──── Lifecycle ────

    async def __aenter__(self) -> "JarvisClient":
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def connect(self):
        """Ouvrir la connexion HTTP."""
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=httpx.Timeout(self.config.timeout),
            follow_redirects=True,
        )
        if self.config.auto_login:
            await self.login()

    async def close(self):
        """Fermer proprement."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # ──── Auth ────

    async def login(self, username: str = "", password: str = "") -> APIResponse:
        """Authentification JWT."""
        user = username or self.config.username
        pwd = password or self.config.password
        resp = await self._raw_request("POST", "/api/auth/login", json={
            "username": user, "password": pwd,
        })
        if resp.ok and isinstance(resp.data, dict):
            self._token = resp.data.get("token")
            expires_in = resp.data.get("expires_in", 86400)
            self._token_expires = time.time() + expires_in - 60
            logger.info(f"Logged in as {user}")
        return resp

    async def _ensure_auth(self):
        """Auto-refresh token si expiré."""
        if not self._token or time.time() > self._token_expires:
            await self.login()

    def _auth_headers(self) -> dict:
        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    # ──── Core Request ────

    async def _raw_request(self, method: str, path: str, **kwargs) -> APIResponse:
        """Requête HTTP brute."""
        if not self._client:
            await self.connect()
        start = time.time()
        try:
            response = await self._client.request(method, path, **kwargs)
            elapsed = (time.time() - start) * 1000
            try:
                data = response.json()
            except Exception:
                data = response.text
            return APIResponse(
                status_code=response.status_code,
                data=data,
                headers=dict(response.headers),
                elapsed_ms=round(elapsed, 1),
                request_id=response.headers.get("X-Request-ID", ""),
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return APIResponse(
                status_code=0,
                data={"error": type(e).__name__, "message": str(e)},
                elapsed_ms=round(elapsed, 1),
            )

    async def request(self, method: str, path: str, **kwargs) -> APIResponse:
        """Requête avec auth et retry."""
        await self._ensure_auth()
        kwargs.setdefault("headers", {}).update(self._auth_headers())
        return await self._retry.execute(self._raw_request, method, path, **kwargs)

    async def get(self, path: str, **kwargs) -> APIResponse:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs) -> APIResponse:
        return await self.request("POST", path, **kwargs)    # ──── Health ────

    async def health(self) -> APIResponse:
        return await self._raw_request("GET", "/api/health")

    async def status(self) -> APIResponse:
        return await self.get("/api/status")

    # ──── Cluster ────

    async def cluster_health(self) -> APIResponse:
        return await self.get("/api/cluster/health")

    async def cluster_query(
        self, prompt: str, node: str = "auto", model: str = "",
        temperature: float = 0.3, max_tokens: int = 2000,
    ) -> APIResponse:
        return await self.post("/api/cluster/query", json={
            "prompt": prompt, "node": node, "model": model,
            "temperature": temperature, "max_tokens": max_tokens,
        })

    async def cluster_consensus(
        self, prompt: str,
        nodes: Optional[list[str]] = None,
        strategy: str = "quality_weighted",
    ) -> APIResponse:
        payload = {"prompt": prompt, "strategy": strategy}
        if nodes:
            payload["nodes"] = nodes
        return await self.post("/api/cluster/consensus", json=payload)

    async def cluster_gpu(self) -> APIResponse:
        return await self.get("/api/cluster/gpu")

    async def cluster_models(self) -> APIResponse:
        return await self.get("/api/cluster/models")

    # ──── Trading ────

    async def trading_action(self, action: str, params: Optional[dict] = None) -> APIResponse:
        return await self.post("/api/trading/action", json={
            "action": action, "params": params or {},
        })

    async def trading_scan(self, **params) -> APIResponse:
        return await self.trading_action("scan", params)

    async def trading_positions(self) -> APIResponse:
        return await self.get("/api/trading/positions")

    async def trading_signals(self) -> APIResponse:
        return await self.get("/api/trading/signals")

    async def trading_status(self) -> APIResponse:
        return await self.get("/api/trading/status")

    async def trading_execute(self, signal_id: int, dry_run: bool = True) -> APIResponse:
        return await self.trading_action("execute", {
            "signal_id": signal_id, "dry_run": dry_run,
        })

    async def trading_close(self, symbol: str) -> APIResponse:
        return await self.trading_action("close", {"symbol": symbol})

    # ──── Voice ────

    async def voice_recognize(self, text: str) -> APIResponse:
        return await self.post("/api/voice/recognize", json={
            "text": text, "action": "recognize",
        })

    async def voice_tts(self, text: str) -> APIResponse:
        return await self.post("/api/voice/tts", json={
            "text": text, "action": "tts",
        })

    async def voice_analytics(self) -> APIResponse:
        return await self.get("/api/voice/analytics")

    # ──── Agents ────

    async def agent_action(self, action: str, agent_id: str = "", **params) -> APIResponse:
        return await self.post("/api/agents/action", json={
            "agent_id": agent_id, "action": action, "params": params,
        })

    async def agent_list(self) -> APIResponse:
        return await self.get("/api/agents/list")

    async def agent_status(self) -> APIResponse:
        return await self.get("/api/agents/status")

    async def agent_start(self, agent_id: str, **params) -> APIResponse:
        return await self.agent_action("start", agent_id, **params)

    async def agent_stop(self, agent_id: str) -> APIResponse:
        return await self.agent_action("stop", agent_id)

    # ──── Automation ────

    async def list_dominos(self) -> APIResponse:
        return await self.get("/api/automation/dominos")

    async def list_skills(self) -> APIResponse:
        return await self.get("/api/automation/skills")

    async def list_workflows(self) -> APIResponse:
        return await self.get("/api/automation/workflows")

    # ──── Metrics ────

    async def metrics(self) -> APIResponse:
        return await self.get("/api/metrics")

    async def metrics_summary(self) -> APIResponse:
        return await self.get("/api/metrics/summary")

    async def config(self) -> APIResponse:
        return await self.get("/api/config")

    # ──── WebSocket ────

    async def ws_stream(
        self, channel: str = "default", on_message: Optional[callable] = None,
    ) -> AsyncIterator[dict]:
        """Stream WebSocket avec auto-reconnect."""
        import websockets

        url = f"{self.config.ws_url}/{channel}"
        retry_count = 0

        while retry_count < self.config.max_retries:
            try:
                async with websockets.connect(url) as ws:
                    logger.info(f"WS connected to {channel}")
                    retry_count = 0
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            msg = {"type": "raw", "data": raw}

                        if on_message:
                            await on_message(msg)
                        yield msg

            except Exception as e:
                retry_count += 1
                delay = min(self.config.retry_base_delay * (2 ** retry_count), 30)
                logger.warning(f"WS disconnected ({e}), reconnecting in {delay:.0f}s...")
                await asyncio.sleep(delay)

        logger.error(f"WS max retries reached for channel {channel}")


# ──────────────────── Convenience Functions ────────────────────

async def quick_query(prompt: str, node: str = "auto") -> dict:
    """Query rapide sans gestion de session."""
    async with JarvisClient() as client:
        resp = await client.cluster_query(prompt, node=node)
        return resp.data if resp.ok else {"error": resp.error}


async def quick_consensus(prompt: str) -> dict:
    """Consensus rapide sans gestion de session."""
    async with JarvisClient() as client:
        resp = await client.cluster_consensus(prompt)
        return resp.data if resp.ok else {"error": resp.error}


async def quick_health() -> dict:
    """Health check rapide."""
    async with JarvisClient() as client:
        resp = await client.health()
        return resp.data if resp.ok else {"error": resp.error}
