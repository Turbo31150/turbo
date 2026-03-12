"""embedding_service.py — Service d'embedding unifié JARVIS.

Fallback chain: Gemini API → M1/LM Studio → OL1/Ollama
Supporte: texte, batch, cache SQLite, circuit breaker par provider.

Usage:
    from src.embedding_service import get_embedding_service
    svc = get_embedding_service()
    vec = await svc.embed("Hello world")
    vecs = await svc.embed_batch(["Hello", "World"])
    sim = svc.cosine_similarity(vec1, vec2)
"""

import asyncio
import json
import math
import os
import sqlite3
import hashlib
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger("jarvis.embedding")

# ── Config ────────────────────────────────────────────────────────────────

GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"
GEMINI_BATCH_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
GEMINI_MODEL = "gemini-embedding-001"
GEMINI_DIMS = 768  # bon rapport qualité/taille (supporté: 128-3072)

M1_EMBED_URL = "http://127.0.0.1:1234/v1/embeddings"
M1_EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"

OL1_EMBED_URL = "http://127.0.0.1:11434/api/embed"
OL1_EMBED_MODEL = "nomic-embed-text"  # à pull si besoin

DB_PATH = Path(__file__).parent.parent / "data" / "embedding_cache.db"

# Clés Gemini (rotation si plusieurs)
GEMINI_KEYS = [
    k for k in [
        os.getenv("GEMINI_API_KEY", ""),
        os.getenv("GEMINI_API_KEY_ALT", ""),
        os.getenv("GEMINI_API_KEY_TURBO", ""),
    ] if k
]


@dataclass
class ProviderStatus:
    """Circuit breaker per provider."""
    name: str
    failures: int = 0
    last_failure: float = 0.0
    circuit_open: bool = False
    avg_latency_ms: float = 0.0
    total_calls: int = 0

    def record_success(self, latency_ms: float):
        self.failures = 0
        self.circuit_open = False
        self.total_calls += 1
        # Running average
        if self.avg_latency_ms == 0:
            self.avg_latency_ms = latency_ms
        else:
            self.avg_latency_ms = self.avg_latency_ms * 0.8 + latency_ms * 0.2

    def record_failure(self):
        self.failures += 1
        self.last_failure = time.time()
        self.total_calls += 1
        if self.failures >= 3:
            self.circuit_open = True
            logger.warning(f"[EMBED] Circuit OPEN pour {self.name} ({self.failures} failures)")

    def is_available(self) -> bool:
        if not self.circuit_open:
            return True
        # Auto-reset après 60s
        if time.time() - self.last_failure > 60:
            self.circuit_open = False
            self.failures = 0
            logger.info(f"[EMBED] Circuit RESET pour {self.name}")
            return True
        return False


class EmbeddingService:
    """Service d'embedding multi-provider avec fallback et cache."""

    def __init__(self):
        self._providers = {
            "gemini": ProviderStatus("gemini"),
            "m1": ProviderStatus("m1"),
            "ol1": ProviderStatus("ol1"),
        }
        self._gemini_key_idx = 0
        self._db: Optional[sqlite3.Connection] = None
        self._init_cache()

    # ── Cache SQLite ──────────────────────────────────────────────────────

    def _init_cache(self):
        try:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
            self._db.execute("""CREATE TABLE IF NOT EXISTS embeddings (
                hash TEXT PRIMARY KEY,
                provider TEXT,
                model TEXT,
                dims INTEGER,
                vector TEXT,
                created_at REAL
            )""")
            self._db.execute("""CREATE TABLE IF NOT EXISTS stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL,
                provider TEXT,
                latency_ms REAL,
                tokens INTEGER,
                success INTEGER
            )""")
            self._db.commit()
        except Exception as e:
            logger.warning(f"[EMBED] Cache init failed: {e}")
            self._db = None

    def _cache_key(self, text: str, dims: int) -> str:
        return hashlib.sha256(f"{text}:{dims}".encode()).hexdigest()[:32]

    def _get_cached(self, text: str, dims: int) -> Optional[list[float]]:
        if not self._db:
            return None
        try:
            h = self._cache_key(text, dims)
            row = self._db.execute(
                "SELECT vector FROM embeddings WHERE hash = ?", (h,)
            ).fetchone()
            if row:
                return json.loads(row[0])
        except Exception:
            pass
        return None

    def _set_cached(self, text: str, dims: int, vector: list[float], provider: str, model: str):
        if not self._db:
            return
        try:
            h = self._cache_key(text, dims)
            self._db.execute(
                "INSERT OR REPLACE INTO embeddings (hash, provider, model, dims, vector, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (h, provider, model, dims, json.dumps(vector), time.time())
            )
            self._db.commit()
        except Exception:
            pass

    def _log_stat(self, provider: str, latency_ms: float, tokens: int, success: bool):
        if not self._db:
            return
        try:
            self._db.execute(
                "INSERT INTO stats (ts, provider, latency_ms, tokens, success) VALUES (?,?,?,?,?)",
                (time.time(), provider, latency_ms, tokens, 1 if success else 0)
            )
            self._db.commit()
        except Exception:
            pass

    # ── Gemini API ────────────────────────────────────────────────────────

    def _next_gemini_key(self) -> str:
        keys = [k for k in GEMINI_KEYS if k]
        if not keys:
            return ""
        key = keys[self._gemini_key_idx % len(keys)]
        self._gemini_key_idx = (self._gemini_key_idx + 1) % len(keys)
        return key

    async def _embed_gemini(self, text: str, dims: int = GEMINI_DIMS) -> Optional[list[float]]:
        key = self._next_gemini_key()
        if not key:
            logger.warning("[EMBED] Aucune clé Gemini disponible")
            return None

        url = GEMINI_EMBED_URL.format(model=GEMINI_MODEL)
        payload = {
            "content": {"parts": [{"text": text}]},
            "taskType": "SEMANTIC_SIMILARITY",
            "outputDimensionality": dims,
        }

        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": key,
                    },
                    json=payload,
                )
                latency = (time.time() - t0) * 1000

                if resp.status_code == 200:
                    data = resp.json()
                    values = data.get("embedding", {}).get("values", [])
                    if values:
                        self._providers["gemini"].record_success(latency)
                        self._log_stat("gemini", latency, len(text.split()), True)
                        return values

                # 429 ou autre erreur → rotate key et fail
                logger.warning(f"[EMBED] Gemini {resp.status_code}: {resp.text[:200]}")
                self._providers["gemini"].record_failure()
                self._log_stat("gemini", latency, len(text.split()), False)
                return None

        except Exception as e:
            latency = (time.time() - t0) * 1000
            logger.warning(f"[EMBED] Gemini error: {e}")
            self._providers["gemini"].record_failure()
            self._log_stat("gemini", latency, 0, False)
            return None

    async def _embed_gemini_batch(self, texts: list[str], dims: int = GEMINI_DIMS) -> Optional[list[list[float]]]:
        key = self._next_gemini_key()
        if not key:
            return None

        url = GEMINI_BATCH_URL.format(model=GEMINI_MODEL)
        requests = []
        for text in texts:
            requests.append({
                "model": f"models/{GEMINI_MODEL}",
                "content": {"parts": [{"text": text}]},
                "taskType": "SEMANTIC_SIMILARITY",
                "outputDimensionality": dims,
            })

        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": key,
                    },
                    json={"requests": requests},
                )
                latency = (time.time() - t0) * 1000

                if resp.status_code == 200:
                    data = resp.json()
                    embeddings = data.get("embeddings", [])
                    results = [e.get("values", []) for e in embeddings]
                    if results and all(results):
                        self._providers["gemini"].record_success(latency)
                        self._log_stat("gemini", latency, sum(len(t.split()) for t in texts), True)
                        return results

                logger.warning(f"[EMBED] Gemini batch {resp.status_code}")
                self._providers["gemini"].record_failure()
                return None

        except Exception as e:
            logger.warning(f"[EMBED] Gemini batch error: {e}")
            self._providers["gemini"].record_failure()
            return None

    # ── M1 / LM Studio (OpenAI-compat) ────────────────────────────────────

    async def _embed_m1(self, text: str) -> Optional[list[float]]:
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    M1_EMBED_URL,
                    headers={"Content-Type": "application/json"},
                    json={"model": M1_EMBED_MODEL, "input": text},
                )
                latency = (time.time() - t0) * 1000

                if resp.status_code == 200:
                    data = resp.json()
                    emb = data.get("data", [{}])[0].get("embedding", [])
                    if emb:
                        self._providers["m1"].record_success(latency)
                        self._log_stat("m1", latency, len(text.split()), True)
                        return emb

                logger.warning(f"[EMBED] M1 {resp.status_code}: {resp.text[:200]}")
                self._providers["m1"].record_failure()
                self._log_stat("m1", latency, len(text.split()), False)
                return None

        except Exception as e:
            latency = (time.time() - t0) * 1000
            logger.warning(f"[EMBED] M1 error: {e}")
            self._providers["m1"].record_failure()
            self._log_stat("m1", latency, 0, False)
            return None

    # ── OL1 / Ollama ──────────────────────────────────────────────────────

    async def _embed_ol1(self, text: str) -> Optional[list[float]]:
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    OL1_EMBED_URL,
                    json={"model": OL1_EMBED_MODEL, "input": text},
                )
                latency = (time.time() - t0) * 1000

                if resp.status_code == 200:
                    data = resp.json()
                    emb = data.get("embeddings", [[]])[0]
                    if emb:
                        self._providers["ol1"].record_success(latency)
                        self._log_stat("ol1", latency, len(text.split()), True)
                        return emb

                logger.warning(f"[EMBED] OL1 {resp.status_code}: {resp.text[:200]}")
                self._providers["ol1"].record_failure()
                self._log_stat("ol1", latency, len(text.split()), False)
                return None

        except Exception as e:
            latency = (time.time() - t0) * 1000
            logger.warning(f"[EMBED] OL1 error: {e}")
            self._providers["ol1"].record_failure()
            self._log_stat("ol1", latency, 0, False)
            return None

    # ── API publique ──────────────────────────────────────────────────────

    async def embed(self, text: str, dims: int = GEMINI_DIMS, task_type: str = "SEMANTIC_SIMILARITY") -> Optional[list[float]]:
        """Embed un texte. Fallback chain: Gemini → M1 → OL1."""
        if not text or not text.strip():
            return None

        # Cache check
        cached = self._get_cached(text, dims)
        if cached:
            return cached

        # Fallback chain
        chain = [
            ("gemini", lambda: self._embed_gemini(text, dims)),
            ("m1", lambda: self._embed_m1(text)),
            ("ol1", lambda: self._embed_ol1(text)),
        ]

        for name, fn in chain:
            if not self._providers[name].is_available():
                logger.debug(f"[EMBED] Skip {name} (circuit open)")
                continue

            result = await fn()
            if result:
                model = {
                    "gemini": GEMINI_MODEL,
                    "m1": M1_EMBED_MODEL,
                    "ol1": OL1_EMBED_MODEL,
                }[name]
                self._set_cached(text, len(result), result, name, model)
                logger.info(f"[EMBED] OK via {name} ({len(result)} dims, {self._providers[name].avg_latency_ms:.0f}ms)")
                return result

        logger.error("[EMBED] Tous les providers ont échoué")
        return None

    async def embed_batch(self, texts: list[str], dims: int = GEMINI_DIMS) -> list[Optional[list[float]]]:
        """Embed plusieurs textes. Gemini batch si dispo, sinon séquentiel."""
        if not texts:
            return []

        # Séparer cached vs non-cached
        results: list[Optional[list[float]]] = [None] * len(texts)
        uncached_indices = []

        for i, text in enumerate(texts):
            cached = self._get_cached(text, dims)
            if cached:
                results[i] = cached
            else:
                uncached_indices.append(i)

        if not uncached_indices:
            return results

        uncached_texts = [texts[i] for i in uncached_indices]

        # Gemini batch (max 100 par appel)
        if self._providers["gemini"].is_available() and len(uncached_texts) <= 100:
            batch_result = await self._embed_gemini_batch(uncached_texts, dims)
            if batch_result and len(batch_result) == len(uncached_texts):
                for idx, vec in zip(uncached_indices, batch_result):
                    results[idx] = vec
                    self._set_cached(texts[idx], len(vec), vec, "gemini", GEMINI_MODEL)
                return results

        # Fallback: séquentiel
        for idx in uncached_indices:
            results[idx] = await self.embed(texts[idx], dims)

        return results

    # ── Similarité ────────────────────────────────────────────────────────

    @staticmethod
    def cosine_similarity(v1: list[float], v2: list[float]) -> float:
        """Cosine similarity entre deux vecteurs."""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        mag1 = math.sqrt(sum(a * a for a in v1))
        mag2 = math.sqrt(sum(b * b for b in v2))
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot / (mag1 * mag2)

    @staticmethod
    def l2_normalize(vector: list[float]) -> list[float]:
        """Normalisation L2 (requise pour dims < 3072 avec gemini-embedding-001)."""
        mag = math.sqrt(sum(v * v for v in vector))
        if mag == 0:
            return vector
        return [v / mag for v in vector]

    # ── Utilitaires ───────────────────────────────────────────────────────

    def status(self) -> dict:
        """Retourne le statut de tous les providers."""
        result = {}
        for name, p in self._providers.items():
            result[name] = {
                "available": p.is_available(),
                "circuit_open": p.circuit_open,
                "failures": p.failures,
                "total_calls": p.total_calls,
                "avg_latency_ms": round(p.avg_latency_ms, 1),
            }

        # Stats cache
        cache_size = 0
        if self._db:
            try:
                row = self._db.execute("SELECT COUNT(*) FROM embeddings").fetchone()
                cache_size = row[0] if row else 0
            except Exception:
                pass

        result["cache"] = {"entries": cache_size, "db": str(DB_PATH)}
        return result

    async def health_check(self) -> dict:
        """Test rapide de chaque provider."""
        test_text = "test embedding health check"
        results = {}

        for name, fn in [
            ("gemini", lambda: self._embed_gemini(test_text, 128)),
            ("m1", lambda: self._embed_m1(test_text)),
            ("ol1", lambda: self._embed_ol1(test_text)),
        ]:
            t0 = time.time()
            try:
                vec = await fn()
                latency = (time.time() - t0) * 1000
                results[name] = {
                    "ok": vec is not None,
                    "dims": len(vec) if vec else 0,
                    "latency_ms": round(latency, 1),
                }
            except Exception as e:
                results[name] = {"ok": False, "error": str(e)}

        return results


# ── Singleton ─────────────────────────────────────────────────────────────

_instance: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _instance
    if _instance is None:
        _instance = EmbeddingService()
    return _instance
