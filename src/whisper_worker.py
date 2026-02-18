"""Persistent Whisper Worker — loads model once, transcribes fast via stdin/stdout.

Protocol (line-based):
  IN:  /path/to/audio.wav
  OUT: transcribed text (or empty line on error)
  IN:  QUIT
  (process exits)

Uses faster-whisper with CUDA for ~4x speedup over openai-whisper.
"""

import sys
import os
import warnings

# Suppress noisy warnings
warnings.filterwarnings("ignore")
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")


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
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()

            # Filter hallucinations
            if text.lower() in HALLUCINATIONS or len(text) < 2:
                print("", flush=True)
            else:
                print(text, flush=True)
        except Exception as e:
            print("", flush=True)
            print(f"WHISPER_ERROR: {e}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
