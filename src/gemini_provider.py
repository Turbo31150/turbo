"""gemini_provider.py — Provider Gemini API complet pour JARVIS.

45 modèles: texte, vision, image (Imagen 4), vidéo (Veo 3.1), TTS, audio natif,
embeddings, deep research, computer use, robotique.

Usage:
    from src.gemini_provider import get_gemini
    gp = get_gemini()
    result = await gp.chat("Explique les embeddings")
    result = await gp.vision("Décris cette image", image_path="photo.jpg")
    result = await gp.search("Dernières news Bitcoin")
    result = await gp.generate_image("Un chat astronaute")
    result = await gp.tts("Bonjour le monde")
    result = await gp.generate_video("Coucher de soleil sur la mer")
"""

import asyncio
import base64
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger("jarvis.gemini")

# ── Config ────────────────────────────────────────────────────────────────

API_BASE = "https://generativelanguage.googleapis.com/v1beta"

# ── Catalogue complet des 45 modèles Gemini (2026-03-11) ─────────────────

# Texte / Chat (generateContent)
MODELS_TEXT = {
    "fast":       "gemini-2.5-flash",              # Stable, rapide, 1M ctx
    "pro":        "gemini-2.5-pro",                # Stable, puissant, 1M ctx
    "lite":       "gemini-2.5-flash-lite",         # Ultra-économique, 1M ctx
    "flash3":     "gemini-3-flash-preview",        # Aperçu v3
    "pro3":       "gemini-3.1-pro-preview",        # Aperçu v3.1 raisonnement
    "pro3tools":  "gemini-3.1-pro-preview-customtools",  # Custom tools
    "lite3":      "gemini-3.1-flash-lite-preview", # Lite v3.1
    "flash2":     "gemini-2.0-flash",              # v2.0
    "flash2lite": "gemini-2.0-flash-lite",         # v2.0 lite
}

# Image generation (predict)
MODELS_IMAGE = {
    "imagen4":      "imagen-4.0-generate-001",       # Standard
    "imagen4ultra": "imagen-4.0-ultra-generate-001",  # Ultra qualité
    "imagen4fast":  "imagen-4.0-fast-generate-001",   # Rapide
    "nanopro":      "nano-banana-pro-preview",        # Nano Banana Pro (texte+image)
    "nano2":        "gemini-3.1-flash-image-preview", # Nano Banana 2
    "nano":         "gemini-2.5-flash-image",         # Nano Banana original
}

# Video generation (predictLongRunning)
MODELS_VIDEO = {
    "veo31":     "veo-3.1-generate-preview",      # Dernier, meilleur
    "veo31fast": "veo-3.1-fast-generate-preview",  # Rapide
    "veo3":      "veo-3.0-generate-001",           # Stable
    "veo3fast":  "veo-3.0-fast-generate-001",      # Rapide stable
    "veo2":      "veo-2.0-generate-001",           # Ancien
}

# TTS (generateContent avec audio output)
MODELS_TTS = {
    "tts":        "gemini-2.5-flash-preview-tts",    # Flash TTS
    "tts_pro":    "gemini-2.5-pro-preview-tts",      # Pro TTS (meilleur qualité)
}

# Audio natif (bidiGenerateContent — streaming bidirectionnel)
MODELS_AUDIO = {
    "audio":      "gemini-2.5-flash-native-audio-latest",  # Dernier
}

# Embeddings
MODELS_EMBED = {
    "embed":      "gemini-embedding-001",            # Stable, texte seul
    "embed2":     "gemini-embedding-2-preview",      # Multimodal (texte+image+audio+vidéo)
}

# Spéciaux
MODELS_SPECIAL = {
    "deep_research": "deep-research-pro-preview-12-2025",  # Recherche autonome
    "computer_use":  "gemini-2.5-computer-use-preview-10-2025",  # Contrôle UI
    "robotics":      "gemini-robotics-er-1.5-preview",     # Robotique
    "aqa":           "aqa",                                # Attributed QA
}

# Gemma (open-source, hébergé par Google)
MODELS_GEMMA = {
    "gemma1b":  "gemma-3-1b-it",
    "gemma4b":  "gemma-3-4b-it",
    "gemma12b": "gemma-3-12b-it",
    "gemma27b": "gemma-3-27b-it",
}

# Alias unifié (tous les modèles)
MODELS = {**MODELS_TEXT, **MODELS_IMAGE, **MODELS_VIDEO, **MODELS_TTS,
          **MODELS_AUDIO, **MODELS_EMBED, **MODELS_SPECIAL, **MODELS_GEMMA}

DEFAULT_MODEL = "gemini-2.5-flash"

# Clé API
def _get_api_key() -> str:
    return (
        os.getenv("GEMINI_API_KEY", "")
        or os.getenv("GEMINI_API_KEY_TURBO", "")
        or os.getenv("GEMINI_API_KEY_ALT", "")
    )


@dataclass
class GeminiStats:
    total_calls: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    failures: int = 0
    avg_latency_ms: float = 0.0
    last_model: str = ""
    circuit_open: bool = False
    last_failure: float = 0.0

    def record_success(self, latency_ms: float, tokens_in: int = 0, tokens_out: int = 0, model: str = ""):
        self.total_calls += 1
        self.total_tokens_in += tokens_in
        self.total_tokens_out += tokens_out
        self.last_model = model
        self.failures = 0
        self.circuit_open = False
        if self.avg_latency_ms == 0:
            self.avg_latency_ms = latency_ms
        else:
            self.avg_latency_ms = self.avg_latency_ms * 0.8 + latency_ms * 0.2

    def record_failure(self):
        self.failures += 1
        self.total_calls += 1
        self.last_failure = time.time()
        if self.failures >= 5:
            self.circuit_open = True
            logger.warning("[GEMINI] Circuit OPEN après %d failures", self.failures)

    def is_available(self) -> bool:
        if not self.circuit_open:
            return True
        if time.time() - self.last_failure > 120:
            self.circuit_open = False
            self.failures = 0
            return True
        return False


def _log_to_sql(method: str, model: str, latency_ms: float, tokens_in: int, tokens_out: int, success: bool, error: str = ""):
    """Log usage dans etoile.db (fire-and-forget)."""
    try:
        import sqlite3
        db_path = Path(__file__).parent.parent / "data" / "etoile.db"
        db = sqlite3.connect(str(db_path), timeout=2)
        db.execute(
            "INSERT INTO gemini_usage (ts, method, model, latency_ms, tokens_in, tokens_out, success, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (time.time(), method, model, latency_ms, tokens_in, tokens_out, 1 if success else 0, error or None)
        )
        if success:
            db.execute(
                "UPDATE gemini_models SET total_calls = total_calls + 1, "
                "avg_latency_ms = (avg_latency_ms * total_calls + ?) / (total_calls + 1), "
                "last_used = ? WHERE model_id = ?",
                (latency_ms, time.time(), model)
            )
        db.commit()
        db.close()
    except Exception:
        pass  # fire-and-forget, jamais bloquer


class GeminiProvider:
    """Provider Gemini API complet — 45 modèles: texte, image, vidéo, TTS, audio, embedding."""

    def __init__(self):
        self.stats = GeminiStats()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120)
        return self._client

    def _url(self, model: str, method: str = "generateContent") -> str:
        key = _get_api_key()
        return f"{API_BASE}/models/{model}:{method}?key={key}"

    def _resolve_model(self, model: Optional[str] = None) -> str:
        if model and model in MODELS:
            return MODELS[model]
        if model:
            return model
        return DEFAULT_MODEL

    # ── Chat (texte) ──────────────────────────────────────────────────────

    async def chat(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        thinking: Optional[str] = None,
    ) -> dict[str, Any]:
        """Génération texte. model: 'fast'|'pro'|'flash3'|'pro3'|'lite' ou ID direct."""
        model_id = self._resolve_model(model)

        body: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        if thinking and thinking in ("minimal", "low", "medium", "high"):
            body["generationConfig"]["thinkingConfig"] = {"thinkingLevel": thinking.upper()}

        return await self._call(model_id, body)

    # ── Vision (image) ────────────────────────────────────────────────────

    async def vision(
        self,
        prompt: str,
        image_path: Optional[str] = None,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """Analyse d'image. Fournir image_path, image_url ou image_base64."""
        model_id = self._resolve_model(model or "fast")

        parts: list[dict] = [{"text": prompt}]

        if image_path:
            path = Path(image_path)
            if not path.exists():
                return {"error": f"Image non trouvée: {image_path}"}
            mime = {
                ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
            }.get(path.suffix.lower(), "image/jpeg")
            b64 = base64.b64encode(path.read_bytes()).decode()
            parts.append({"inlineData": {"mimeType": mime, "data": b64}})

        elif image_url:
            parts.append({"fileData": {"fileUri": image_url}})

        elif image_base64:
            parts.append({"inlineData": {"mimeType": "image/jpeg", "data": image_base64}})

        body = {
            "contents": [{"parts": parts}],
            "generationConfig": {"maxOutputTokens": 2048},
        }
        return await self._call(model_id, body)

    # ── Grounded Search (Google Search) ───────────────────────────────────

    async def search(
        self,
        query: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
    ) -> dict[str, Any]:
        """Recherche grounded via Google Search intégré."""
        model_id = self._resolve_model(model or "fast")

        body: dict[str, Any] = {
            "contents": [{"parts": [{"text": query}]}],
            "tools": [{"googleSearch": {}}],
            "generationConfig": {"maxOutputTokens": 2048},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        result = await self._call(model_id, body)

        # Extraire les sources de grounding
        if not result.get("error"):
            grounding = result.get("_raw", {}).get("candidates", [{}])[0].get(
                "groundingMetadata", {}
            )
            sources = grounding.get("groundingChunks", [])
            if sources:
                result["sources"] = [
                    {"title": s.get("web", {}).get("title", ""), "uri": s.get("web", {}).get("uri", "")}
                    for s in sources
                ]
        return result

    # ── Code Execution ────────────────────────────────────────────────────

    async def code(
        self,
        prompt: str,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """Exécution de code Python côté Google."""
        model_id = self._resolve_model(model or "fast")

        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"codeExecution": {}}],
            "generationConfig": {"maxOutputTokens": 4096},
        }
        return await self._call(model_id, body)

    # ── Multi-turn chat ───────────────────────────────────────────────────

    async def multi_turn(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Conversation multi-tour. messages: [{"role": "user"|"model", "text": "..."}]"""
        model_id = self._resolve_model(model)

        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "assistant":
                role = "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.get("text", msg.get("content", ""))}],
            })

        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 2048,
            },
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        return await self._call(model_id, body)

    # ── Image Generation (Imagen 4) ─────────────────────────────────────

    async def generate_image(
        self,
        prompt: str,
        model: str = "imagen4",
        aspect_ratio: str = "1:1",
        num_images: int = 1,
    ) -> dict[str, Any]:
        """Génère une image via Imagen 4. Retourne base64 image data."""
        model_id = MODELS_IMAGE.get(model, model)
        key = _get_api_key()
        if not key:
            return {"error": "Pas de clé Gemini"}

        url = f"{API_BASE}/models/{model_id}:predict?key={key}"
        body = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "aspectRatio": aspect_ratio,
                "sampleCount": min(num_images, 4),
            },
        }

        t0 = time.time()
        try:
            client = await self._get_client()
            r = await client.post(url, json=body, headers={"Content-Type": "application/json"}, timeout=60)
            latency = (time.time() - t0) * 1000

            if r.status_code == 200:
                data = r.json()
                predictions = data.get("predictions", [])
                images = []
                for p in predictions:
                    b64 = p.get("bytesBase64Encoded", "")
                    mime = p.get("mimeType", "image/png")
                    if b64:
                        images.append({"base64": b64, "mimeType": mime})
                self.stats.record_success(latency, model=model_id)
                return {"images": images, "count": len(images), "model": model_id, "latency_ms": round(latency, 1)}
            return {"error": f"Imagen HTTP {r.status_code}: {r.text[:200]}"}
        except Exception as e:
            self.stats.record_failure()
            return {"error": f"Imagen: {e}"}

    async def save_image(self, prompt: str, output_path: str, model: str = "imagen4", **kwargs) -> dict[str, Any]:
        """Génère et sauvegarde une image sur disque."""
        result = await self.generate_image(prompt, model=model, **kwargs)
        if result.get("error"):
            return result
        images = result.get("images", [])
        if not images:
            return {"error": "Aucune image générée"}

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        img_data = base64.b64decode(images[0]["base64"])
        path.write_bytes(img_data)
        return {**result, "saved_to": str(path), "size_bytes": len(img_data)}

    # ── Video Generation (Veo 3.1) ───────────────────────────────────────

    async def generate_video(
        self,
        prompt: str,
        model: str = "veo31fast",
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
    ) -> dict[str, Any]:
        """Lance la génération vidéo via Veo (async long-running). Retourne l'operation ID."""
        model_id = MODELS_VIDEO.get(model, model)
        key = _get_api_key()
        if not key:
            return {"error": "Pas de clé Gemini"}

        url = f"{API_BASE}/models/{model_id}:predictLongRunning?key={key}"
        body = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "aspectRatio": aspect_ratio,
                "durationSeconds": duration_seconds,
                "sampleCount": 1,
            },
        }

        t0 = time.time()
        try:
            client = await self._get_client()
            r = await client.post(url, json=body, headers={"Content-Type": "application/json"}, timeout=30)
            latency = (time.time() - t0) * 1000

            if r.status_code == 200:
                data = r.json()
                op_name = data.get("name", "")
                self.stats.record_success(latency, model=model_id)
                return {
                    "operation": op_name,
                    "model": model_id,
                    "latency_ms": round(latency, 1),
                    "status": "RUNNING",
                    "poll_url": f"{API_BASE}/{op_name}?key={key}",
                }
            return {"error": f"Veo HTTP {r.status_code}: {r.text[:200]}"}
        except Exception as e:
            self.stats.record_failure()
            return {"error": f"Veo: {e}"}

    async def check_video_status(self, operation_name: str) -> dict[str, Any]:
        """Vérifie le statut d'une génération vidéo."""
        key = _get_api_key()
        try:
            client = await self._get_client()
            r = await client.get(f"{API_BASE}/{operation_name}?key={key}", timeout=10)
            if r.status_code == 200:
                data = r.json()
                done = data.get("done", False)
                result = {"done": done, "operation": operation_name}
                if done:
                    resp = data.get("response", {})
                    videos = resp.get("predictions", [])
                    result["videos"] = [
                        {"base64": v.get("bytesBase64Encoded", ""), "mimeType": v.get("mimeType", "video/mp4")}
                        for v in videos if v.get("bytesBase64Encoded")
                    ]
                return result
            return {"error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    # ── TTS (Text-to-Speech) ──────────────────────────────────────────────

    async def tts(
        self,
        text: str,
        voice: str = "Kore",
        model: str = "tts",
    ) -> dict[str, Any]:
        """Synthèse vocale via Gemini TTS. Retourne audio base64 (WAV)."""
        model_id = MODELS_TTS.get(model, model)
        key = _get_api_key()
        if not key:
            return {"error": "Pas de clé Gemini"}

        url = f"{API_BASE}/models/{model_id}:generateContent?key={key}"
        body = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}},
                },
            },
        }

        t0 = time.time()
        try:
            client = await self._get_client()
            r = await client.post(url, json=body, headers={"Content-Type": "application/json"}, timeout=30)
            latency = (time.time() - t0) * 1000

            if r.status_code == 200:
                data = r.json()
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                for part in parts:
                    inline = part.get("inlineData", {})
                    if inline.get("data"):
                        self.stats.record_success(latency, model=model_id)
                        return {
                            "audio_base64": inline["data"],
                            "mimeType": inline.get("mimeType", "audio/wav"),
                            "model": model_id,
                            "latency_ms": round(latency, 1),
                        }
                return {"error": "Pas de données audio dans la réponse"}
            return {"error": f"TTS HTTP {r.status_code}: {r.text[:200]}"}
        except Exception as e:
            self.stats.record_failure()
            return {"error": f"TTS: {e}"}

    async def save_tts(self, text: str, output_path: str, **kwargs) -> dict[str, Any]:
        """Génère TTS et sauvegarde le fichier audio."""
        result = await self.tts(text, **kwargs)
        if result.get("error"):
            return result
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        audio_data = base64.b64decode(result["audio_base64"])
        path.write_bytes(audio_data)
        return {**result, "saved_to": str(path), "size_bytes": len(audio_data)}

    # ── Deep Research ─────────────────────────────────────────────────────

    async def deep_research(self, query: str) -> dict[str, Any]:
        """Recherche autonome multi-étapes via Deep Research Pro."""
        return await self.chat(
            query,
            model="deep-research-pro-preview-12-2025",
            max_tokens=65536,
            temperature=0.3,
        )

    # ── PDF Analysis ──────────────────────────────────────────────────────

    async def analyze_pdf(self, prompt: str, pdf_path: str, model: Optional[str] = None) -> dict[str, Any]:
        """Analyse un PDF via Gemini multimodal."""
        model_id = self._resolve_model(model or "fast")
        path = Path(pdf_path)
        if not path.exists():
            return {"error": f"PDF non trouvé: {pdf_path}"}

        b64 = base64.b64encode(path.read_bytes()).decode()
        body = {
            "contents": [{"parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": "application/pdf", "data": b64}},
            ]}],
            "generationConfig": {"maxOutputTokens": 4096},
        }
        return await self._call(model_id, body)

    # ── Audio Analysis ────────────────────────────────────────────────────

    async def analyze_audio(self, prompt: str, audio_path: str, model: Optional[str] = None) -> dict[str, Any]:
        """Analyse un fichier audio via Gemini."""
        model_id = self._resolve_model(model or "fast")
        path = Path(audio_path)
        if not path.exists():
            return {"error": f"Audio non trouvé: {audio_path}"}

        mime = {"mp3": "audio/mp3", "wav": "audio/wav", "ogg": "audio/ogg", "m4a": "audio/mp4"
                }.get(path.suffix.lstrip(".").lower(), "audio/mp3")
        b64 = base64.b64encode(path.read_bytes()).decode()
        body = {
            "contents": [{"parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": mime, "data": b64}},
            ]}],
            "generationConfig": {"maxOutputTokens": 4096},
        }
        return await self._call(model_id, body)

    # ── List models ───────────────────────────────────────────────────────

    async def list_models(self) -> dict[str, Any]:
        """Liste les modèles Gemini disponibles."""
        key = _get_api_key()
        if not key:
            return {"error": "Pas de clé Gemini configurée"}
        try:
            client = await self._get_client()
            r = await client.get(f"{API_BASE}/models?key={key}", timeout=10)
            if r.status_code == 200:
                data = r.json()
                models = []
                for m in data.get("models", []):
                    name = m.get("name", "").replace("models/", "")
                    models.append({
                        "id": name,
                        "displayName": m.get("displayName", ""),
                        "inputTokenLimit": m.get("inputTokenLimit", 0),
                        "outputTokenLimit": m.get("outputTokenLimit", 0),
                    })
                return {"models": models, "count": len(models)}
            return {"error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    # ── Health check ──────────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        """Test rapide de connectivité Gemini."""
        t0 = time.time()
        result = await self.chat("Reply with only: OK", model="fast", max_tokens=10, temperature=0)
        latency = (time.time() - t0) * 1000
        return {
            "ok": not result.get("error"),
            "latency_ms": round(latency, 1),
            "model": result.get("model", ""),
            "response": result.get("text", result.get("error", "")),
        }

    # ── Status ────────────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        return {
            "available": self.stats.is_available(),
            "circuit_open": self.stats.circuit_open,
            "total_calls": self.stats.total_calls,
            "failures": self.stats.failures,
            "avg_latency_ms": round(self.stats.avg_latency_ms, 1),
            "total_tokens_in": self.stats.total_tokens_in,
            "total_tokens_out": self.stats.total_tokens_out,
            "last_model": self.stats.last_model,
            "has_key": bool(_get_api_key()),
            "models": MODELS,
        }

    # ── Core API call ─────────────────────────────────────────────────────

    async def _call(self, model: str, body: dict) -> dict[str, Any]:
        """Appel API Gemini avec fallback modèle."""
        if not self.stats.is_available():
            return {"error": "Gemini circuit open (trop de failures)"}

        key = _get_api_key()
        if not key:
            return {"error": "Pas de clé Gemini (GEMINI_API_KEY)"}

        # Fallback chain de modèles
        models_to_try = [model]
        if model != DEFAULT_MODEL:
            models_to_try.append(DEFAULT_MODEL)

        for m in models_to_try:
            url = f"{API_BASE}/models/{m}:generateContent?key={key}"
            t0 = time.time()
            try:
                client = await self._get_client()
                r = await client.post(
                    url,
                    json=body,
                    headers={"Content-Type": "application/json"},
                )
                latency = (time.time() - t0) * 1000

                if r.status_code == 200:
                    data = r.json()
                    candidate = data.get("candidates", [{}])[0]
                    content = candidate.get("content", {})
                    parts = content.get("parts", [])

                    # Extraire texte + code
                    text_parts = []
                    code_parts = []
                    for part in parts:
                        if "text" in part:
                            text_parts.append(part["text"])
                        if "executableCode" in part:
                            code_parts.append(part["executableCode"].get("code", ""))
                        if "codeExecutionResult" in part:
                            text_parts.append(f"\n[Code Output]: {part['codeExecutionResult'].get('output', '')}")

                    text = "\n".join(text_parts)

                    # Usage
                    usage = data.get("usageMetadata", {})
                    tokens_in = usage.get("promptTokenCount", 0)
                    tokens_out = usage.get("candidatesTokenCount", 0)

                    self.stats.record_success(latency, tokens_in, tokens_out, m)
                    _log_to_sql("chat", m, latency, tokens_in, tokens_out, True)
                    logger.info("[GEMINI] OK %s — %d tokens, %.0fms", m, tokens_out, latency)

                    result = {
                        "text": text,
                        "model": m,
                        "latency_ms": round(latency, 1),
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "finish_reason": candidate.get("finishReason", ""),
                        "_raw": data,
                    }
                    if code_parts:
                        result["code"] = code_parts
                    return result

                # Erreur récupérable → try next model
                error_msg = r.json().get("error", {}).get("message", r.text[:200])
                logger.warning("[GEMINI] %s HTTP %d: %s", m, r.status_code, error_msg[:100])

                if r.status_code == 429:
                    # Rate limit → attendre un peu avant le prochain modèle
                    await asyncio.sleep(0.5)
                    continue
                if r.status_code >= 500:
                    continue  # Server error → try fallback

                # 400/401/403 → pas la peine de retry
                self.stats.record_failure()
                return {"error": f"Gemini {r.status_code}: {error_msg}"}

            except httpx.ReadTimeout:
                logger.warning("[GEMINI] Timeout %s (%.0fs)", m, (time.time() - t0))
                continue
            except Exception as e:
                logger.warning("[GEMINI] Error %s: %s", m, e)
                continue

        self.stats.record_failure()
        return {"error": "Gemini: tous les modèles ont échoué"}

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ── Singleton ─────────────────────────────────────────────────────────────

_instance: Optional[GeminiProvider] = None


def get_gemini() -> GeminiProvider:
    global _instance
    if _instance is None:
        _instance = GeminiProvider()
    return _instance
