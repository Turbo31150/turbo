"""
VOICE JARVIS v1.0 - Pilotage Vocal Conversationnel Rapide
STT (faster-whisper) + Silero VAD + Corrections STT -> Commander JARVIS -> OS Pilot
Mode PTT (Push-to-Talk RIGHT_CTRL) ou ecoute continue

Usage:
  python voice_jarvis.py              # PTT mode (defaut)
  python voice_jarvis.py --continuous # Ecoute continue
  python voice_jarvis.py --keyboard   # Mode clavier (debug)
  python voice_jarvis.py --cpu        # Forcer CPU (pas de CUDA)
  python voice_jarvis.py --model small # Modele leger
"""
import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
import argparse
import threading
import numpy as np
import re

# Forcer CPU si demande AVANT import torch
if "--cpu" in sys.argv:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""

# Import commander JARVIS
sys.path.insert(0, os.path.dirname(__file__))
from commander_v2 import process_input, speak, TTS_OK

# ================================================================
# CONFIGURATION
# ================================================================
WHISPER_MODEL = "large-v3-turbo"
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE = "float16"
WHISPER_LANGUAGE = "fr"
MIN_LANGUAGE_PROB = 0.50

MODEL_ALIASES = {
    "turbo": "large-v3-turbo",
    "large": "large-v3",
    "distil-fr": "bofenghuang/whisper-large-v3-french-distil-dec16",
    "medium": "medium",
    "small": "small",
    "base": "base",
    "tiny": "tiny",
}

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024
SILENCE_DURATION = 1.5
MAX_RECORD_DURATION = 30

# Push-to-Talk
PTT_ENABLED = True
PTT_KEY = "right ctrl"
PTT_BIP_FREQ_ON = 800
PTT_BIP_FREQ_OFF = 400
PTT_BIP_DURATION = 100

# Anti-echo TTS
TTS_COOLDOWN = 2.0
TTS_ECHO_THRESHOLD = 0.45

# Silero VAD
USE_SILERO_VAD = True
SILERO_VAD_THRESHOLD = 0.35


# ================================================================
# STT CORRECTIONS - Filtrage bruit + corrections crypto/commandes
# ================================================================
NOISE_EXACT = {
    "bye", "goodbye", "see you", "danke", "merci", "gracias", "ciao",
    "ok", "okay", "yep", "yeah", "yah", "hmm", "huh", "uh", "um", "ah", "oh",
    "the end", "world", "sous-titres", "sous-titrage", "subtitles",
}

NOISE_FRAGMENTS = [
    "thanks for watching", "thank you for watching", "thank you very much",
    "thank you", "thanks for listening", "merci d'avoir",
    "merci a tous", "like and subscribe", "subscribe",
    "d'avoir regarde", "cette video", "that's all",
    "sous-titres realises", "je suis un agent", "je ne peux pas",
    "n'hesitez pas", "bonne journee", "avec plaisir",
    "je reste a votre disposition", "pouvez-vous preciser",
    "je m'ameliore", "chaque interaction",
]

SINGLE_WORD_NOISE = {
    "what", "yes", "no", "hey", "hi", "hello", "so", "well", "right",
    "sure", "fine", "good", "nice", "great", "wow",
    "oui", "non", "bon", "bien", "voila", "allez", "tiens", "super",
    "d'accord", "stop",
}

CRYPTO_FIXES = {
    "bcc": "btc", "btg": "btc", "bitco": "btc", "bitcoin": "btc",
    "bit coin": "btc", "b t c": "btc",
    "etg": "eth", "ether": "eth", "ethereum": "eth",
    "sold": "sol", "soul": "sol", "solana": "sol",
    "dodge": "doge", "doj": "doge", "dogecoin": "doge",
    "sweet": "sui", "suey": "sui", "apt os": "apt", "aptos": "apt",
    "ship": "shib", "shiba": "shib", "wifi": "wif", "whiff": "wif",
    "bonque": "bonk", "bunk": "bonk", "link": "link",
    "avalanche": "avax", "avacs": "avax",
}

COMMAND_FIXES = {
    "hyper": "sniper", "snipper": "sniper",
    "scanner": "scan", "scanne": "scan", "scannez": "scan",
    "scad": "scan", "scat": "scan", "skad": "scan",
    "skane": "scan", "skanne": "scan",
    "fermer": "ferme", "copier": "copie", "copiez": "copie",
    "coller": "colle", "collez": "colle", "couper": "coupe",
    "annuler": "annule", "capture": "screenshot",
    "breaker": "breakout", "break out": "breakout",
    "lancer": "lance", "lancez": "lance",
    "ouvrir": "ouvre", "ouvrez": "ouvre",
}

PHRASE_PATTERNS = [
    (re.compile(r".*(?:scan|scad|scat|skad|skane)\w*\s+(\w+).*", re.I),
     lambda m: f"scan {m.group(1).upper()}"),
    (re.compile(r".*(?:lance|lancer)\s+(?:le\s+)?(?:scan|scad)\w*\s+(\w+).*", re.I),
     lambda m: f"scan {m.group(1).upper()}"),
    (re.compile(r".*check\s*(?:les?\s+)?marge.*", re.I),
     lambda _: "check marges"),
    (re.compile(r".*(?:breakout|breaker)\s+(\w+).*", re.I),
     lambda m: f"breakout {m.group(1).upper()}"),
    (re.compile(r".*(?:sniper|hyper|snipper)\s+(\w+).*", re.I),
     lambda m: f"sniper {m.group(1).upper()}"),
    (re.compile(r".*(?:analyse|analyze)\s+(\w+).*", re.I),
     lambda m: f"analyze {m.group(1).upper()}"),
]


def stt_postprocess(text):
    """Post-traitement STT: filtre bruit, corrige crypto/commandes"""
    if not text:
        return None

    clean = text.strip().rstrip(".")
    if len(clean) <= 2:
        return None

    lower = clean.lower()

    if lower in NOISE_EXACT:
        return None
    if lower in SINGLE_WORD_NOISE:
        return None

    for fragment in NOISE_FRAGMENTS:
        if fragment in lower:
            return None

    # Reponse IA (pas une commande utilisateur)
    if len(clean) > 60:
        ia_markers = ["je suis", "je ne suis pas", "je reste", "n'hesitez",
                      "votre question", "votre demande", "pour vous aider"]
        if any(m in lower for m in ia_markers):
            return None

    # Corriger phrases entieres
    for pattern, replacer in PHRASE_PATTERNS:
        m = pattern.match(lower)
        if m:
            result = replacer(m)
            print(f"  [PHRASE-FIX] '{clean}' -> '{result}'")
            return result

    # Corriger commandes mot-a-mot
    words = clean.split()
    corrected = []
    for w in words:
        low = w.lower().strip(".,!?")
        if low in COMMAND_FIXES:
            corrected.append(COMMAND_FIXES[low])
        elif low in CRYPTO_FIXES:
            corrected.append(CRYPTO_FIXES[low].upper())
        else:
            corrected.append(w)

    result = " ".join(corrected)
    if result != clean:
        print(f"  [AUTOCORRECT] '{clean}' -> '{result}'")
    return result


# ================================================================
# VOICE LISTENER - Whisper + VAD + PTT -> Commander JARVIS
# ================================================================
class VoiceJarvis:
    def __init__(self):
        self.model = None
        self.vad_model = None
        self.is_listening = True
        self.ptt_active = False
        self._tts_last_spoke = 0.0
        self._tts_last_text = ""
        self._load_model()
        self._load_vad()

    def _check_cuda(self, timeout=10):
        if os.environ.get("CUDA_VISIBLE_DEVICES") == "":
            return False
        import concurrent.futures
        def _check():
            import torch
            return torch.cuda.is_available()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(_check).result(timeout=timeout)
        except Exception:
            print("  [CUDA] Timeout - fallback CPU")
            os.environ["CUDA_VISIBLE_DEVICES"] = ""
            return False

    def _load_model(self):
        global WHISPER_DEVICE
        if WHISPER_DEVICE == "cuda" and not self._check_cuda():
            print("  [WHISPER] CUDA indisponible, bascule CPU")
            WHISPER_DEVICE = "cpu"

        device = WHISPER_DEVICE
        compute = WHISPER_COMPUTE if device == "cuda" else "int8"
        print(f"  [WHISPER] Chargement '{WHISPER_MODEL}' sur {device}...")
        try:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(WHISPER_MODEL, device=device, compute_type=compute)
            print(f"  [WHISPER] Pret sur {device}")
        except Exception as e:
            print(f"  [WHISPER] Erreur {device}: {e}")
            try:
                os.environ["CUDA_VISIBLE_DEVICES"] = ""
                from faster_whisper import WhisperModel
                self.model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
                print("  [WHISPER] Fallback CPU OK")
            except Exception as e2:
                print(f"  [WHISPER] FATAL: {e2}")
                self.model = None

    def _load_vad(self):
        if not USE_SILERO_VAD:
            return
        try:
            import torch
            model, _ = torch.hub.load('snakers4/silero-vad', 'silero_vad',
                                      force_reload=False, trust_repo=True, onnx=False)
            self.vad_model = model
            print("  [VAD] Silero VAD charge")
        except Exception as e:
            print(f"  [VAD] Silero indisponible ({e})")
            self.vad_model = None

    def _is_speech(self, audio_np):
        if self.vad_model is None:
            return np.abs(audio_np).mean() > 500
        try:
            import torch
            tensor = torch.from_numpy(audio_np.copy()).float()
            if tensor.abs().max() > 1.0:
                tensor = tensor / 32768.0
            conf = self.vad_model(tensor, SAMPLE_RATE).item()
            return conf >= SILERO_VAD_THRESHOLD
        except Exception:
            return np.abs(audio_np).mean() > 500

    def _start_ptt(self):
        import keyboard
        key_name = PTT_KEY.split()[-1]

        def on_press(event):
            if event.name == key_name and not self.ptt_active:
                self.ptt_active = True
                try:
                    import winsound
                    winsound.Beep(PTT_BIP_FREQ_ON, PTT_BIP_DURATION)
                except Exception:
                    pass

        def on_release(event):
            if event.name == key_name and self.ptt_active:
                self.ptt_active = False
                try:
                    import winsound
                    winsound.Beep(PTT_BIP_FREQ_OFF, PTT_BIP_DURATION)
                except Exception:
                    pass

        keyboard.on_press(on_press)
        keyboard.on_release(on_release)

    def _is_echo(self, text):
        if not self._tts_last_text or not text:
            return False
        if time.time() - self._tts_last_spoke > 5.0:
            return False
        from difflib import SequenceMatcher
        ratio = SequenceMatcher(None, text.lower()[:100], self._tts_last_text.lower()[:100]).ratio()
        return ratio >= TTS_ECHO_THRESHOLD

    def _find_mic(self, pa):
        import pyaudio
        print("\n  [MIC] Recherche microphone...")
        preferred = []
        fallbacks = []

        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                name = info["name"]
                try:
                    print(f"  [MIC] {name} (idx {i})", end="")
                except UnicodeEncodeError:
                    print(f"  [MIC] device idx {i}", end="")
                if "wh-1000" in name.lower() or "hands-free" in name.lower():
                    preferred.append(i)
                    print(" **")
                elif "microphone" in name.lower() or "realtek" in name.lower():
                    fallbacks.append(i)
                    print(" *")
                else:
                    print("")

        for idx in preferred + fallbacks:
            try:
                test = pa.open(format=pyaudio.paInt16, channels=CHANNELS, rate=SAMPLE_RATE,
                               input=True, input_device_index=idx, frames_per_buffer=CHUNK_SIZE)
                test.read(CHUNK_SIZE, exception_on_overflow=False)
                test.stop_stream()
                test.close()
                print(f"  [MIC] Selectionne: idx {idx}")
                return idx
            except Exception:
                pass

        try:
            return pa.get_default_input_device_info()["index"]
        except Exception:
            return 0

    def _record_until_silence(self, stream):
        frames = []
        silent_chunks = 0
        max_chunks = int(MAX_RECORD_DURATION * SAMPLE_RATE / CHUNK_SIZE)
        silence_needed = int(SILENCE_DURATION * SAMPLE_RATE / CHUNK_SIZE)
        is_speaking = False

        for _ in range(max_chunks):
            if not self.is_listening:
                break
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            except Exception:
                continue

            audio = np.frombuffer(data, dtype=np.int16)

            if self._is_speech(audio):
                is_speaking = True
                silent_chunks = 0
                frames.append(data)
            elif is_speaking:
                silent_chunks += 1
                frames.append(data)
                if silent_chunks >= silence_needed:
                    break

        return b"".join(frames) if is_speaking else None

    def _transcribe(self, audio_bytes):
        if not self.model:
            return None

        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        try:
            segments, info = self.model.transcribe(
                audio_np, beam_size=5, language=WHISPER_LANGUAGE,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=200),
            )

            full_text = " ".join(seg.text.strip() for seg in segments).strip()
            if not full_text:
                return None

            prob = info.language_probability if hasattr(info, "language_probability") else 0
            if isinstance(prob, float) and prob < MIN_LANGUAGE_PROB:
                print(f"  [STT] REJETE (confiance {prob:.0%})")
                return None

            lang = info.language if hasattr(info, "language") else "?"
            print(f"  [STT] ({lang} {prob:.0%}) \"{full_text}\"")
            return full_text

        except Exception as e:
            print(f"  [STT] Erreur: {e}")
            return None

    def _track_tts(self, original_speak):
        """Wrapper pour tracker les sorties TTS (anti-echo)"""
        def wrapped(text):
            original_speak(text)
            self._tts_last_spoke = time.time()
            self._tts_last_text = text[:200] if text else ""
        return wrapped

    def start(self):
        """Boucle d'ecoute principale"""
        import pyaudio

        # Patcher speak() pour anti-echo
        import commander_v2
        commander_v2.speak = self._track_tts(commander_v2.speak)

        pa = pyaudio.PyAudio()
        mic_idx = self._find_mic(pa)

        mode = "PTT (RIGHT_CTRL)" if PTT_ENABLED else "Ecoute continue"
        print(f"\n{'='*60}")
        print(f"  VOICE JARVIS v1.0 - Pilotage Vocal")
        print(f"  Whisper: {WHISPER_MODEL} ({WHISPER_DEVICE})")
        print(f"  VAD: {'Silero' if self.vad_model else 'Amplitude'}")
        print(f"  Mode: {mode}")
        print(f"  Micro: idx {mic_idx}")
        print(f"  Silence: {SILENCE_DURATION}s | Max: {MAX_RECORD_DURATION}s")
        print(f"  Ctrl+C pour arreter")
        print(f"{'='*60}\n")

        if PTT_ENABLED:
            threading.Thread(target=self._start_ptt, daemon=True).start()
            print(f"  [PTT] Maintenir {PTT_KEY} pour parler\n")

        stream = pa.open(
            format=pyaudio.paInt16, channels=CHANNELS, rate=SAMPLE_RATE,
            input=True, input_device_index=mic_idx, frames_per_buffer=CHUNK_SIZE,
        )

        speak("Jarvis vocal en ligne. Pret.")
        print("  [MIC] Ecoute active...\n")

        try:
            while self.is_listening:
                # Anti-echo: cooldown apres TTS
                if self._tts_last_spoke > 0:
                    if time.time() - self._tts_last_spoke < TTS_COOLDOWN:
                        time.sleep(0.1)
                        continue

                # PTT: skip si touche non maintenue
                if PTT_ENABLED and not self.ptt_active:
                    time.sleep(0.05)
                    continue

                frames = self._record_until_silence(stream)

                if frames and len(frames) > SAMPLE_RATE:
                    text = self._transcribe(frames)
                    if text and len(text.strip()) > 1:
                        # Echo TTS?
                        if self._is_echo(text):
                            print("  [ECHO] Rejete")
                            continue

                        # Corrections STT
                        text = stt_postprocess(text)
                        if not text:
                            print("  [NOISE] Rejete")
                            continue

                        # Envoyer au Commander JARVIS
                        print(f"  [VOICE] >> {text}")
                        process_input(text)
                        print()

        except KeyboardInterrupt:
            print("\n  [STOP] Arret vocal.")
            speak("Systeme vocal desactive.")
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()


# ================================================================
# MAIN
# ================================================================
def main():
    global WHISPER_MODEL, WHISPER_DEVICE, PTT_ENABLED, WHISPER_LANGUAGE

    parser = argparse.ArgumentParser(description="Voice JARVIS - Pilotage vocal")
    parser.add_argument("--keyboard", "-k", action="store_true", help="Mode clavier (debug)")
    parser.add_argument("--continuous", "-c", action="store_true", help="Ecoute continue (pas PTT)")
    parser.add_argument("--model", "-m", default=WHISPER_MODEL, help="Modele Whisper")
    parser.add_argument("--cpu", action="store_true", help="Forcer CPU")
    parser.add_argument("--lang", default=WHISPER_LANGUAGE, help="Langue (fr/en/auto)")
    args = parser.parse_args()

    WHISPER_MODEL = MODEL_ALIASES.get(args.model, args.model)
    if args.cpu:
        WHISPER_DEVICE = "cpu"
    if args.continuous:
        PTT_ENABLED = False
    if args.lang == "auto":
        WHISPER_LANGUAGE = None
    else:
        WHISPER_LANGUAGE = args.lang

    print("=" * 60)
    print("  J.A.R.V.I.S. VOICE SYSTEM v1.0")
    print("  STT -> Corrections -> Commander -> Pilot -> TTS")
    print("=" * 60)

    if args.keyboard:
        # Mode debug clavier - utilise directement commander
        from commander_v2 import manual_input_loop
        speak("Mode clavier actif.")
        manual_input_loop()
    else:
        vj = VoiceJarvis()
        vj.start()


if __name__ == "__main__":
    main()
