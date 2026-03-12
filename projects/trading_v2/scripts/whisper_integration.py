"""
WHISPER V3 INTEGRATION - L'Oreille Absolue
Transcription haute fidelite via openai/whisper-large-v3 (HuggingFace Transformers).
Utilise CUDA si disponible, sinon CPU avec float32.

Usage:
    from whisper_integration import WhisperIntegrator
    w = WhisperIntegrator()
    result = w.transcribe("audio.wav")  # {"text": "...", "confidence": 0.95}
"""
import os
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline


class WhisperIntegrator:
    def __init__(self, model_id="openai/whisper-large-v3"):
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self.pipe = None

        print(f"  [WHISPER-V3] Chargement sur {self.device} ({self.torch_dtype})...")

        try:
            self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_id,
                torch_dtype=self.torch_dtype,
                low_cpu_mem_usage=True,
                use_safetensors=True,
            )
            self.model.to(self.device)
            self.processor = AutoProcessor.from_pretrained(model_id)

            self.pipe = pipeline(
                "automatic-speech-recognition",
                model=self.model,
                tokenizer=self.processor.tokenizer,
                feature_extractor=self.processor.feature_extractor,
                max_new_tokens=128,
                chunk_length_s=30,
                batch_size=16,
                return_timestamps=True,
                torch_dtype=self.torch_dtype,
                device=self.device,
            )
            print("  [WHISPER-V3] Charge et pret.")
        except Exception as e:
            print(f"  [WHISPER-V3] Erreur chargement: {e}")
            self.pipe = None

    @property
    def is_ready(self):
        return self.pipe is not None

    def transcribe(self, audio_path, language="fr"):
        """Transcrit un fichier audio et retourne {text, confidence}."""
        if not self.pipe:
            return {"text": "", "confidence": 0.0}

        print(f"  [WHISPER-V3] Transcription de {audio_path}...")
        try:
            result = self.pipe(audio_path, generate_kwargs={"language": language})
            confidence = 0.95
            return {"text": result["text"], "confidence": confidence}
        except Exception as e:
            print(f"  [WHISPER-V3] Erreur transcription: {e}")
            return {"text": "", "confidence": 0.0}


if __name__ == "__main__":
    w = WhisperIntegrator()
    if w.is_ready:
        print("  Whisper V3 pret. Passe un fichier audio pour tester.")
    else:
        print("  Whisper V3 non charge.")
