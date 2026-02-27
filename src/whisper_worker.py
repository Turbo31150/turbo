"""Persistent Whisper Worker — loads model once, transcribes fast via stdin/stdout.

Protocol (line-based):
  IN:  /path/to/audio.wav
  OUT: SEGMENT: partial text  (for each segment as it arrives)
  OUT: DONE: full text        (final result, or empty on error/hallucination)
  IN:  QUIT
  (process exits)

Uses faster-whisper with CUDA for ~4x speedup over openai-whisper.
"""

import sys
import os
import subprocess
import tempfile
import threading
import warnings
from pathlib import Path

# Suppress noisy warnings
warnings.filterwarnings("ignore")
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Force UTF-8 on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")


class WhisperWorker:
    """Manages a persistent whisper_worker subprocess for fast transcription.

    Usage:
        worker = WhisperWorker()
        text = worker.transcribe(wav_bytes_or_path)
    """

    def __init__(self, model: str = "large-v3-turbo"):
        self.model = model
        self._proc = None
        self._lock = threading.Lock()
        self._ready = False
        self._start()

    def _start(self):
        """Start the subprocess worker."""
        turbo_root = str(Path(__file__).resolve().parent.parent)
        env = os.environ.copy()
        env["WHISPER_MODEL"] = self.model
        env["PYTHONIOENCODING"] = "utf-8"

        self._proc = subprocess.Popen(
            [sys.executable, "-m", "src.whisper_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=turbo_root,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        # Wait for WHISPER_LOADED
        for _ in range(120):  # 120s max startup
            line = self._proc.stdout.readline().strip()
            if "WHISPER_LOADED" in line:
                self._ready = True
                break
            if "WHISPER_READY" in line:
                continue
            if self._proc.poll() is not None:
                stderr = self._proc.stderr.read()
                raise RuntimeError(f"Whisper subprocess died: {stderr[:500]}")

        if not self._ready:
            raise RuntimeError("Whisper subprocess did not become ready in 120s")

    def transcribe(self, audio) -> str:
        """Transcribe audio. Accepts bytes (WAV/WebM) or a file path string."""
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                self._start()

            # Write audio to temp file if bytes
            if isinstance(audio, (bytes, bytearray)):
                suffix = ".webm" if audio[:4] == b"\x1a\x45\xdf\xa3" else ".wav"
                tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
                tmp.write(audio)
                tmp.close()
                audio_path = tmp.name
            else:
                audio_path = str(audio)
                tmp = None

            try:
                self._proc.stdin.write(audio_path + "\n")
                self._proc.stdin.flush()

                # Collect segments until DONE
                full_text = ""
                while True:
                    line = self._proc.stdout.readline().strip()
                    if line.startswith("DONE:"):
                        full_text = line[5:].strip()
                        break
                    # SEGMENT lines are partial results
                return full_text
            finally:
                if tmp:
                    try:
                        os.unlink(tmp.name)
                    except OSError:
                        pass

    def close(self):
        """Shut down the subprocess."""
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.stdin.write("QUIT\n")
                self._proc.stdin.flush()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()

    def __del__(self):
        self.close()


def main():
    from faster_whisper import WhisperModel

    model_size = os.environ.get("WHISPER_MODEL", "large-v3-turbo")
    device = os.environ.get("WHISPER_DEVICE", "cuda")
    compute = os.environ.get("WHISPER_COMPUTE", "float16")
    language = os.environ.get("WHISPER_LANG", "fr")

    print(f"WHISPER_READY model={model_size} device={device}", flush=True)

    try:
        model = WhisperModel(model_size, device=device, compute_type=compute)
    except Exception:
        # Fallback to CPU if CUDA fails
        device = "cpu"
        compute = "int8"
        model = WhisperModel(model_size, device=device, compute_type=compute)

    print(f"WHISPER_LOADED device={device} compute={compute}", flush=True)

    # Hallucination filter
    HALLUCINATIONS = {
        ".", "..", "...", "merci.", "sous-titres", "sous-titrage",
        "merci d'avoir regarde", "merci de votre attention",
        "sous-titres realises par la communaute d'amara.org",
        "merci", "ok", "bye",
    }

    for line in sys.stdin:
        path = line.strip()
        if not path:
            continue
        if path.upper() == "QUIT":
            break

        try:
            segments, info = model.transcribe(
                path,
                language=language,
                beam_size=1,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=300),
            )
            parts = []
            for seg in segments:
                text_part = seg.text.strip()
                if text_part:
                    parts.append(text_part)
                    print(f"SEGMENT: {text_part}", flush=True)

            full_text = " ".join(parts).strip()

            if full_text.lower() in HALLUCINATIONS or len(full_text) < 2:
                print("DONE: ", flush=True)
            else:
                print(f"DONE: {full_text}", flush=True)
        except Exception as e:
            print("DONE: ", flush=True)
            print(f"WHISPER_ERROR: {e}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
