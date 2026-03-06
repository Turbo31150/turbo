#!/usr/bin/env python3
"""Quick Whisper transcription for Telegram bot.
Usage: python scripts/transcribe.py <wav_file> [--language fr]
Outputs transcribed text to stdout.
"""
import sys
from faster_whisper import WhisperModel

_model = None

def transcribe(wav_path, language="fr"):
    global _model
    if _model is None:
        import tempfile, wave, os, gc
        # Try large-v3-turbo on CUDA, then CPU, then tiny fallback
        for model_id, device, ctype in [
            ("large-v3-turbo", "cuda", "float16"),
            ("large-v3-turbo", "cpu", "int8"),
            ("tiny", "cpu", "int8"),
        ]:
            try:
                _model = WhisperModel(model_id, device=device, compute_type=ctype)
                # Smoke test with unique file per iteration (avoids CUDA handle leak)
                test_wav = os.path.join(tempfile.gettempdir(), f"_whisper_test_{device}.wav")
                with wave.open(test_wav, "w") as f:
                    f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
                    f.writeframes(b"\x00\x00" * 1600)  # 0.1s silence
                list(_model.transcribe(test_wav, language="fr")[0])
                try: os.unlink(test_wav)
                except OSError: pass
                print(f"Whisper: {model_id}/{device}/{ctype}", file=sys.stderr)
                break
            except Exception as e:
                print(f"Whisper {model_id}/{device} failed: {e}", file=sys.stderr)
                _model = None
                gc.collect()  # Release CUDA handles before next iteration
                continue
    if _model is None:
        return "[Erreur: aucun modele Whisper disponible]"
    segments, _ = _model.transcribe(wav_path, language=language, beam_size=1)
    return " ".join(seg.text.strip() for seg in segments)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: transcribe.py <wav_file>", file=sys.stderr)
        sys.exit(1)
    lang = "fr"
    if "--language" in sys.argv:
        idx = sys.argv.index("--language")
        lang = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "fr"
    result = transcribe(sys.argv[1], lang)
    print(result)
