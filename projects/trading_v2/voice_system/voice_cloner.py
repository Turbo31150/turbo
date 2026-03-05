"""
VOICE CLONER v2.0 - Chatterbox TTS (Local CUDA + Cloud Fallback)
Pipeline: LOCAL (chatterbox sur GPU) -> CLOUD (Gradio HF API) -> None

Usage:
    from voice_cloner import VoiceCloner
    vc = VoiceCloner()
    audio_path = vc.synthesize("Bonjour")  # Local CUDA par defaut
"""
import os
import time
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

OUTPUT_DIR = r"F:\BUREAU\TRADING_V2_PRODUCTION\logs"

# --- LOCAL MODEL (Chatterbox sur CUDA) ---
LOCAL_MODEL = None
LOCAL_OK = False

def _load_local_model():
    """Charge Chatterbox en local sur CUDA (ou CPU). ~5s premier appel."""
    global LOCAL_MODEL, LOCAL_OK
    try:
        from chatterbox.tts import ChatterboxTTS
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"  [CLONER-LOCAL] Chargement Chatterbox sur {device}...")
        LOCAL_MODEL = ChatterboxTTS.from_pretrained(device=device)
        LOCAL_OK = True
        print(f"  [CLONER-LOCAL] Pret (SR={LOCAL_MODEL.sr})")
    except Exception as e:
        print(f"  [CLONER-LOCAL] Echec: {e}")
        LOCAL_OK = False

# --- CLOUD FALLBACK (Gradio HF API) ---
try:
    from gradio_client import Client, handle_file
    GRADIO_OK = True
except ImportError:
    GRADIO_OK = False


class VoiceCloner:
    def __init__(self, preload_local=True):
        self.local_ready = False
        self.cloud_client = None
        self.cloud_ready = False
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # 1. Charger le modele local
        if preload_local:
            _load_local_model()
            self.local_ready = LOCAL_OK

        # 2. Connecter le cloud en fallback (lazy - seulement si local KO)
        if not self.local_ready and GRADIO_OK:
            self._connect_cloud()

    def _connect_cloud(self):
        print("  [CLONER-CLOUD] Connexion HuggingFace...")
        try:
            self.cloud_client = Client("ResembleAI/Chatterbox-Multilingual-TTS")
            self.cloud_ready = True
            print("  [CLONER-CLOUD] Connecte.")
        except Exception as e:
            print(f"  [CLONER-CLOUD] Echec: {e}")

    @property
    def is_ready(self):
        return self.local_ready or self.cloud_ready

    def synthesize(self, text, language="fr", reference_audio=None):
        """Synthetise. Retourne chemin WAV ou None."""
        if not text:
            return None

        # 1. LOCAL (CUDA/CPU - rapide, pas de reseau)
        if self.local_ready:
            path = self._synth_local(text, reference_audio)
            if path:
                return path

        # 2. CLOUD fallback
        if not self.cloud_ready and GRADIO_OK:
            self._connect_cloud()
        if self.cloud_ready:
            path = self._synth_cloud(text, language, reference_audio)
            if path:
                return path

        print("  [CLONER] Aucun backend disponible.")
        return None

    def _synth_local(self, text, reference_audio=None):
        """Generation locale via Chatterbox CUDA."""
        global LOCAL_MODEL, LOCAL_OK
        print(f"  [CLONER-LOCAL] '{text[:40]}...'")
        try:
            import torchaudio as ta
            if reference_audio and os.path.exists(reference_audio):
                wav = LOCAL_MODEL.generate(text, audio_prompt_path=reference_audio)
            else:
                wav = LOCAL_MODEL.generate(text)
            timestamp = int(time.time())
            out_path = os.path.join(OUTPUT_DIR, f"tts_local_{timestamp}.wav")
            ta.save(out_path, wav, LOCAL_MODEL.sr)
            print(f"  [CLONER-LOCAL] OK -> {out_path}")
            return out_path
        except Exception as e:
            print(f"  [CLONER-LOCAL] Erreur: {e}")
            return None

    def _synth_cloud(self, text, language="fr", reference_audio=None):
        """Generation cloud via Gradio HF API."""
        print(f"  [CLONER-CLOUD] '{text[:40]}...'")
        try:
            if reference_audio and os.path.exists(reference_audio):
                audio_ref = handle_file(reference_audio)
            else:
                audio_ref = handle_file(
                    "https://github.com/gradio-app/gradio/raw/main/test/test_files/audio_sample.wav"
                )
            result = self.cloud_client.predict(
                text, language, audio_ref,
                0.5, 0.8, 0, 0.5,
                api_name="/generate_tts_audio",
            )
            print(f"  [CLONER-CLOUD] OK -> {result}")
            return result
        except Exception as e:
            print(f"  [CLONER-CLOUD] Erreur: {e}")
            return None


if __name__ == "__main__":
    vc = VoiceCloner()
    if vc.is_ready:
        path = vc.synthesize("Bonjour, je suis Jarvis, votre assistant vocal.")
        if path:
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME)
            print(f"  Audio joue: {path}")
    else:
        print("  Aucun backend TTS disponible.")
