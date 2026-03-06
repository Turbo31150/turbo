"""
middleware.py - Middleware FastAPI JARVIS
JSON structured logging, error handling, metrics collector, health probes,
request tracing, GZIP compression
Pour F:/BUREAU/turbo/src/
"""

import asyncio
import gzip
import json
import logging
import time
import traceback
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from io import BytesIO
from typing import Optional, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("jarvis.middleware")

# ──────────────────── Structured JSON Logger ────────────────────

class JSONFormatter(logging.Formatter):
    """Formatter JSON structuré pour logs."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": time.time(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }
        # Extra fields
        for key in ("request_id", "method", "path", "status_code", "duration_ms", "client_ip"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        return json.dumps(log_entry, default=str)


def setup_json_logging(level: int = logging.INFO) -> logging.Logger:
    """Configurer le logging JSON structuré."""
    root = logging.getLogger("jarvis")
    root.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    return root


# ──────────────────── Request Metrics ────────────────────

@dataclass
class EndpointMetrics:
    total_requests: int = 0
    total_errors: int = 0
    latencies: deque = field(default_factory=lambda: deque(maxlen=500))
    status_codes: dict = field(default_factory=lambda: defaultdict(int))
    last_request: float = 0.0

    @property
    def avg_latency(self) -> float:
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)

    @property
    def p95_latency(self) -> float:
        if not self.latencies:
            return 0.0
        sorted_lats = sorted(self.latencies)
        idx = int(len(sorted_lats) * 0.95)
        return sorted_lats[min(idx, len(sorted_lats) - 1)]

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_errors / self.total_requests

class MetricsCollector:
    """Collecteur de métriques par endpoint."""

    def __init__(self):
        self._endpoints: dict[str, EndpointMetrics] = defaultdict(EndpointMetrics)
        self._global = EndpointMetrics()
        self._start_time = time.time()
        self._active_requests = 0

    def record(self, method: str, path: str, status_code: int, duration_ms: float):
        key = f"{method} {path}"

        # Per-endpoint
        ep = self._endpoints[key]
        ep.total_requests += 1
        ep.latencies.append(duration_ms)
        ep.status_codes[status_code] += 1
        ep.last_request = time.time()
        if status_code >= 400:
            ep.total_errors += 1

        # Global
        self._global.total_requests += 1
        self._global.latencies.append(duration_ms)
        self._global.status_codes[status_code] += 1
        if status_code >= 400:
            self._global.total_errors += 1

    def get_summary(self) -> dict:
        uptime = time.time() - self._start_time
        return {
            "uptime_seconds": round(uptime, 1),
            "total_requests": self._global.total_requests,
            "total_errors": self._global.total_errors,
            "error_rate": round(self._global.error_rate, 4),
            "avg_latency_ms": round(self._global.avg_latency, 1),
            "p95_latency_ms": round(self._global.p95_latency, 1),
            "requests_per_min": round(
                self._global.total_requests / max(uptime / 60, 1), 1
            ),
            "active_requests": self._active_requests,
            "status_codes": dict(self._global.status_codes),
            "endpoints": len(self._endpoints),
        }

    def get_endpoints(self, top_n: int = 20) -> list[dict]:
        sorted_eps = sorted(
            self._endpoints.items(),
            key=lambda x: -x[1].total_requests,
        )[:top_n]
        return [
            {
                "endpoint": key,
                "requests": ep.total_requests,
                "errors": ep.total_errors,
                "error_rate": round(ep.error_rate, 4),
                "avg_latency_ms": round(ep.avg_latency, 1),
                "p95_latency_ms": round(ep.p95_latency, 1),
            }
            for key, ep in sorted_eps
        ]

    def get_prometheus(self) -> str:
        """Export Prometheus text format."""
        lines = []
        lines.append(f"# HELP jarvis_requests_total Total requests")
        lines.append(f"# TYPE jarvis_requests_total counter")
        lines.append(f"jarvis_requests_total {self._global.total_requests}")

        lines.append(f"# HELP jarvis_errors_total Total errors")
        lines.append(f"# TYPE jarvis_errors_total counter")
        lines.append(f"jarvis_errors_total {self._global.total_errors}")

        lines.append(f"# HELP jarvis_latency_avg Average latency ms")
        lines.append(f"# TYPE jarvis_latency_avg gauge")
        lines.append(f"jarvis_latency_avg {self._global.avg_latency:.1f}")

        lines.append(f"# HELP jarvis_latency_p95 P95 latency ms")
        lines.append(f"# TYPE jarvis_latency_p95 gauge")
        lines.append(f"jarvis_latency_p95 {self._global.p95_latency:.1f}")

        for code, count in self._global.status_codes.items():
            lines.append(f'jarvis_status_code{{code="{code}"}} {count}')

        return "\n".join(lines) + "\n"

# ──────────────────── Request Tracing Middleware ────────────────────

class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Middleware de traçabilité: request_id, timing, logging."""

    def __init__(self, app: FastAPI, metrics: MetricsCollector):
        super().__init__(app)
        self.metrics = metrics

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        start = time.time()
        self.metrics._active_requests += 1

        # Inject request_id
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start) * 1000

            # Record metrics
            path = self._normalize_path(request.url.path)
            self.metrics.record(request.method, path, response.status_code, duration_ms)

            # Add headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"

            # Log
            logger.info(
                f"{request.method} {request.url.path} {response.status_code} {duration_ms:.0f}ms",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 1),
                    "client_ip": request.client.host if request.client else "unknown",
                },
            )
            return response

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            path = self._normalize_path(request.url.path)
            self.metrics.record(request.method, path, 500, duration_ms)

            logger.error(
                f"Unhandled error: {type(e).__name__}: {e}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": round(duration_ms, 1),
                },
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "message": str(e),
                    "request_id": request_id,
                },
            )
        finally:
            self.metrics._active_requests -= 1

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normaliser les paths pour grouper les métriques."""
        parts = path.strip("/").split("/")
        normalized = []
        for part in parts:
            if len(part) > 20 or part.isdigit():
                normalized.append(":id")
            else:
                normalized.append(part)
        return "/" + "/".join(normalized)


# ──────────────────── Error Handler Middleware ────────────────────

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Gestion centralisée des erreurs avec format JSON standard."""

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            request_id = getattr(request.state, "request_id", "unknown")
            error_type = type(e).__name__

            if error_type == "HTTPException":
                status = getattr(e, "status_code", 500)
                detail = getattr(e, "detail", str(e))
            elif error_type in ("ValidationError", "RequestValidationError"):
                status = 422
                detail = str(e)
            else:
                status = 500
                detail = "Internal server error"

            return JSONResponse(
                status_code=status,
                content={
                    "error": error_type.lower(),
                    "message": detail,
                    "request_id": request_id,
                    "timestamp": time.time(),
                },
            )

# ──────────────────── GZIP Compression ────────────────────

class GZIPMiddleware(BaseHTTPMiddleware):
    """Compression GZIP pour réponses > min_size."""

    def __init__(self, app: FastAPI, min_size: int = 1024):
        super().__init__(app)
        self.min_size = min_size

    async def dispatch(self, request: Request, call_next) -> Response:
        accept_encoding = request.headers.get("Accept-Encoding", "")
        if "gzip" not in accept_encoding:
            return await call_next(request)

        response = await call_next(request)

        # Only compress JSON responses above min_size
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # Read body
        body = b""
        async for chunk in response.body_iterator:
            if isinstance(chunk, str):
                body += chunk.encode()
            else:
                body += chunk

        if len(body) < self.min_size:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        # Compress
        buf = BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6) as f:
            f.write(body)
        compressed = buf.getvalue()

        headers = dict(response.headers)
        headers["Content-Encoding"] = "gzip"
        headers["Content-Length"] = str(len(compressed))

        return Response(
            content=compressed,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )


# ──────────────────── Health Probes ────────────────────

class HealthProbes:
    """Liveness et Readiness probes pour Kubernetes/monitoring."""

    def __init__(self):
        self._ready = False
        self._checks: dict[str, Callable] = {}
        self._start_time = time.time()

    def set_ready(self, ready: bool = True):
        self._ready = ready

    def add_check(self, name: str, check_fn: Callable[[], bool]):
        self._checks[name] = check_fn

    def liveness(self) -> dict:
        """Probe liveness: le service tourne."""
        return {
            "status": "ok",
            "uptime": round(time.time() - self._start_time, 1),
            "timestamp": time.time(),
        }

    def readiness(self) -> dict:
        """Probe readiness: le service est prêt à recevoir du trafic."""
        checks_results = {}
        all_ok = self._ready

        for name, check_fn in self._checks.items():
            try:
                result = check_fn()
                checks_results[name] = "ok" if result else "fail"
                if not result:
                    all_ok = False
            except Exception as e:
                checks_results[name] = f"error: {e}"
                all_ok = False

        return {
            "status": "ready" if all_ok else "not_ready",
            "checks": checks_results,
            "timestamp": time.time(),
        }


# ──────────────────── Setup Helper ────────────────────

def setup_middleware(app: FastAPI) -> dict:
    """Installer tous les middlewares sur l'app FastAPI.

    Returns dict with references to metrics, health probes, etc.
    """
    metrics = MetricsCollector()
    health = HealthProbes()

    # Order matters: first added = outermost
    app.add_middleware(GZIPMiddleware, min_size=1024)
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(RequestTracingMiddleware, metrics=metrics)

    # Health endpoints
    @app.get("/healthz")
    async def liveness():
        return health.liveness()

    @app.get("/readyz")
    async def readiness():
        result = health.readiness()
        status_code = 200 if result["status"] == "ready" else 503
        return JSONResponse(content=result, status_code=status_code)

    # Metrics endpoints
    @app.get("/api/metrics/summary")
    async def metrics_summary():
        return metrics.get_summary()

    @app.get("/api/metrics/endpoints")
    async def metrics_endpoints():
        return metrics.get_endpoints(30)

    @app.get("/api/metrics/prometheus")
    async def metrics_prometheus():
        return Response(
            content=metrics.get_prometheus(),
            media_type="text/plain; charset=utf-8",
        )

    health.set_ready(True)

    return {
        "metrics": metrics,
        "health": health,
    }
