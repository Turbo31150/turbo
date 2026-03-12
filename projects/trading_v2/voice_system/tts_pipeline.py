"""
TTS PIPELINE v2.0 - Triple Fallback (Local CUDA -> Cloud HF -> pyttsx3)
1. LOCAL: Chatterbox sur GPU (meilleure qualite, ~3-5s, pas de reseau)
2. CLOUD: Chatterbox HuggingFace (si GPU indisponible, ~10-20s)
3. LOCAL SAPI5: pyttsx3 Microsoft Hortense FR (instantane, qualite basique)

Usage:
    from tts_pipeline import TTSPipeline
    tts = TTSPipeline()
    tts.say("Bonjour")              # Auto: Local -> Cloud -> pyttsx3
    tts.say("Vite", cloning=False)  # Force pyttsx3 direct (instantane)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from voice_cloner import VoiceCloner
from local_tts import LocalTTS

REF_AUDIO = r"/home/turbo\TRADING_V2_PRODUCTION\config\my_voice_ref.wav"


class TTSPipeline:
    def __init__(self, ref_audio=None, preload_local=True):
        self.ref_audio = ref_audio or REF_AUDIO
        self.cloner = VoiceCloner(preload_local=preload_local)
        self.local = LocalTTS()
        self.is_speaking = False

    def say(self, text, cloning=True):
        """Parle. Local CUDA -> Cloud HF -> pyttsx3."""
        if not text:
            return

        self.is_speaking = True

        try:
            # 1+2. Chatterbox (local CUDA ou cloud HF)
            if cloning and self.cloner.is_ready:
                ref = self.ref_audio if os.path.exists(self.ref_audio) else None
                audio_file = self.cloner.synthesize(text, "fr", ref)
                if audio_file and os.path.exists(audio_file):
                    try:
                        import winsound
                        winsound.PlaySound(audio_file, winsound.SND_FILENAME)
                        return
                    except Exception as e:
                        print(f"  [TTS-PIPE] Erreur lecture: {e}")

            # 3. Fallback pyttsx3 (instantane)
            self.local.speak(text)
        finally:
            self.is_speaking = False


if __name__ == "__main__":
    tts = TTSPipeline()
    tts.say("Test du pipeline vocal hybride version 2.")
