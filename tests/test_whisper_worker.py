"""Tests for src/whisper_worker.py — Persistent Whisper subprocess manager.

Covers: WhisperWorker (init, _start, transcribe, close).
Subprocess calls are fully mocked (no real Whisper model loaded).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Patch stdin.reconfigure before importing (pytest replaces stdin with DontReadFromInput)
if not hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure = lambda **kw: None  # type: ignore[attr-defined]


# ===========================================================================
# WhisperWorker — mocked subprocess
# ===========================================================================

class TestWhisperWorkerInit:
    def test_start_success(self):
        from src.whisper_worker import WhisperWorker
        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = ["WHISPER_LOADED device=cuda\n"]
        mock_proc.poll.return_value = None
        with patch("subprocess.Popen", return_value=mock_proc):
            ww = WhisperWorker.__new__(WhisperWorker)
            ww.model = "large-v3-turbo"
            ww._proc = None
            ww._lock = __import__("threading").Lock()
            ww._ready = False
            ww._start()
        assert ww._ready is True

    def test_start_failure_process_dies(self):
        from src.whisper_worker import WhisperWorker
        mock_proc = MagicMock()
        mock_proc.stdout.readline.return_value = ""
        mock_proc.poll.return_value = 1
        mock_proc.stderr.read.return_value = "CUDA not found"
        with patch("subprocess.Popen", return_value=mock_proc):
            ww = WhisperWorker.__new__(WhisperWorker)
            ww.model = "large-v3-turbo"
            ww._proc = None
            ww._lock = __import__("threading").Lock()
            ww._ready = False
            with pytest.raises(RuntimeError, match="Whisper subprocess died"):
                ww._start()


class TestWhisperWorkerTranscribe:
    def _make_worker(self, mock_proc):
        from src.whisper_worker import WhisperWorker
        ww = WhisperWorker.__new__(WhisperWorker)
        ww.model = "large-v3-turbo"
        ww._proc = mock_proc
        ww._lock = __import__("threading").Lock()
        ww._ready = True
        return ww

    def test_transcribe_file_path(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdout.readline.side_effect = [
            "SEGMENT: Bonjour\n",
            "DONE: Bonjour tout le monde\n",
        ]
        ww = self._make_worker(mock_proc)
        result = ww.transcribe("C:/audio/test.wav")
        assert result == "Bonjour tout le monde"
        mock_proc.stdin.write.assert_called_once_with("C:/audio/test.wav\n")

    def test_transcribe_bytes(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdout.readline.side_effect = [
            "DONE: Test transcription\n",
        ]
        ww = self._make_worker(mock_proc)
        with patch("tempfile.NamedTemporaryFile") as mock_tmp:
            mock_file = MagicMock()
            mock_file.name = "/tmp/audio.wav"
            mock_tmp.return_value = mock_file
            with patch("os.unlink"):
                result = ww.transcribe(b"\x00\x01\x02\x03")
        assert result == "Test transcription"

    def test_transcribe_restarts_dead_process(self):
        from src.whisper_worker import WhisperWorker
        mock_dead = MagicMock()
        mock_dead.poll.return_value = 1  # dead

        mock_new = MagicMock()
        mock_new.poll.return_value = None
        mock_new.stdout.readline.side_effect = [
            "WHISPER_LOADED device=cpu\n",  # from _start
            "DONE: Hello\n",  # from transcribe
        ]

        ww = WhisperWorker.__new__(WhisperWorker)
        ww.model = "large-v3-turbo"
        ww._proc = mock_dead
        ww._lock = __import__("threading").Lock()
        ww._ready = True

        with patch("subprocess.Popen", return_value=mock_new):
            result = ww.transcribe("test.wav")
        assert result == "Hello"


class TestWhisperWorkerClose:
    def test_close_running(self):
        from src.whisper_worker import WhisperWorker
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        ww = WhisperWorker.__new__(WhisperWorker)
        ww._proc = mock_proc
        ww.close()
        mock_proc.stdin.write.assert_called_with("QUIT\n")

    def test_close_already_dead(self):
        from src.whisper_worker import WhisperWorker
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        ww = WhisperWorker.__new__(WhisperWorker)
        ww._proc = mock_proc
        ww.close()  # should not crash
        mock_proc.stdin.write.assert_not_called()

    def test_close_none(self):
        from src.whisper_worker import WhisperWorker
        ww = WhisperWorker.__new__(WhisperWorker)
        ww._proc = None
        ww.close()  # should not crash
