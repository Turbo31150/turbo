"""JARVIS Voice Session Manager — centralise l'etat de la session vocale.

Remplace les variables globales dispersees par un objet session unique
avec stats temps reel, historique, et serialisation.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VoiceStats:
    """Real-time voice pipeline statistics."""
    total_commands: int = 0
    successful_commands: int = 0
    failed_commands: int = 0
    total_stt_ms: float = 0.0
    total_correction_ms: float = 0.0
    total_tts_ms: float = 0.0
    stt_count: int = 0
    correction_count: int = 0
    cache_hits: int = 0
    shortcut_hits: int = 0
    multi_intents: int = 0
    confirmations_asked: int = 0
    confirmations_accepted: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_commands == 0:
            return 0.0
        return self.successful_commands / self.total_commands

    @property
    def avg_stt_ms(self) -> float:
        if self.stt_count == 0:
            return 0.0
        return self.total_stt_ms / self.stt_count

    @property
    def avg_correction_ms(self) -> float:
        if self.correction_count == 0:
            return 0.0
        return self.total_correction_ms / self.correction_count

    def to_dict(self) -> dict:
        return {
            "total_commands": self.total_commands,
            "successful": self.successful_commands,
            "failed": self.failed_commands,
            "success_rate": round(self.success_rate * 100, 1),
            "avg_stt_ms": round(self.avg_stt_ms, 1),
            "avg_correction_ms": round(self.avg_correction_ms, 1),
            "cache_hits": self.cache_hits,
            "shortcut_hits": self.shortcut_hits,
            "multi_intents": self.multi_intents,
            "confirmations": {
                "asked": self.confirmations_asked,
                "accepted": self.confirmations_accepted,
            },
        }


class VoiceSession:
    """Manages the state of a single voice session.

    Centralizes: context, stats, mode, voice preference, timestamps.
    Thread-safe for concurrent access from voice_loop and WS handlers.
    """

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.started_at = time.monotonic()
        self.started_at_wall = time.time()

        # Mode
        self.mode: str = "wake"  # "wake" or "ptt"
        self.voice: str = "denise"
        self.active: bool = False

        # Stats
        self.stats = VoiceStats()
        self._lock = threading.Lock()

        # Command history (last 50 for session)
        self._history: list[dict] = []
        self._HISTORY_MAX = 50

        # Method distribution
        self._methods: dict[str, int] = {}

    def record_command(self, intent: str, method: str, confidence: float,
                       success: bool, latency_ms: float = 0.0):
        """Record a voice command execution."""
        with self._lock:
            self.stats.total_commands += 1
            if success:
                self.stats.successful_commands += 1
            else:
                self.stats.failed_commands += 1

            # Track method distribution
            self._methods[method] = self._methods.get(method, 0) + 1

            # Track special methods
            if method == "cache":
                self.stats.cache_hits += 1
            elif method == "shortcut":
                self.stats.shortcut_hits += 1
            elif method == "multi_intent":
                self.stats.multi_intents += 1

            # History
            entry = {
                "intent": intent,
                "method": method,
                "confidence": round(confidence, 3),
                "success": success,
                "latency_ms": round(latency_ms, 1),
                "timestamp": time.time(),
            }
            self._history.append(entry)
            if len(self._history) > self._HISTORY_MAX:
                self._history.pop(0)

    def record_stt(self, latency_ms: float):
        """Record STT latency."""
        with self._lock:
            self.stats.stt_count += 1
            self.stats.total_stt_ms += latency_ms

    def record_correction(self, latency_ms: float):
        """Record correction pipeline latency."""
        with self._lock:
            self.stats.correction_count += 1
            self.stats.total_correction_ms += latency_ms

    def record_confirmation(self, accepted: bool):
        """Record a confirmation prompt result."""
        with self._lock:
            self.stats.confirmations_asked += 1
            if accepted:
                self.stats.confirmations_accepted += 1

    @property
    def duration_s(self) -> float:
        return time.monotonic() - self.started_at

    def to_dict(self) -> dict:
        """Serialize session state for WS/REST exposure."""
        with self._lock:
            return {
                "session_id": self.session_id,
                "mode": self.mode,
                "voice": self.voice,
                "active": self.active,
                "duration_s": round(self.duration_s, 1),
                "started_at": self.started_at_wall,
                "stats": self.stats.to_dict(),
                "method_distribution": dict(self._methods),
                "recent_commands": self._history[-10:],
            }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @property
    def history(self) -> list[dict]:
        with self._lock:
            return list(self._history)


# ── Global session singleton ──────────────────────────────────────────────
_current_session: VoiceSession | None = None
_session_lock = threading.Lock()


def get_voice_session() -> VoiceSession:
    """Get or create the current voice session."""
    global _current_session
    with _session_lock:
        if _current_session is None:
            _current_session = VoiceSession()
        return _current_session


def start_voice_session(mode: str = "wake", voice: str = "denise") -> VoiceSession:
    """Start a new voice session, replacing any existing one."""
    global _current_session
    with _session_lock:
        session = VoiceSession()
        session.mode = mode
        session.voice = voice
        session.active = True
        _current_session = session
        return session


def end_voice_session() -> dict | None:
    """End the current session and return its final stats."""
    global _current_session
    with _session_lock:
        if _current_session is None:
            return None
        _current_session.active = False
        result = _current_session.to_dict()
        _current_session = None
        return result
