"""
Voice Driver - WhisperFlow Integration
Ecoute continue avec faster-whisper, VAD, et injection dans les Logic Hooks.

Usage:
  python voice_driver.py              # Mode vocal (micro)
  python voice_driver.py --keyboard   # Mode clavier (debug/test)
  python voice_driver.py --test       # Test rapide du systeme
"""

import sys
import os

# Forcer UTF-8 sur la console Windows (evite les ??? sur les accents)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
import wave
import tempfile
import argparse
import threading
import numpy as np
from pathlib import Path

# CUDA safety: si --cpu dans argv, desactiver CUDA AVANT tout import torch
# Ceci evite le hang infini quand le driver NVIDIA est corrompu
if "--cpu" in sys.argv:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""

# Ajouter le dossier parent au path
sys.path.insert(0, str(Path(__file__).parent))

from logic_hooks import LogicHookManager
from router_proxy import RouterBrain


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

WHISPER_MODEL = "large-v3-turbo"  # turbo: 809M params, 6x plus rapide, meme precision que large-v3
WHISPER_DEVICE = "cuda"        # cuda/cpu
WHISPER_COMPUTE = "float16"    # float16/int8

# Aliases pour --model (raccourcis pratiques)
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
SILENCE_THRESHOLD = 500        # Amplitude seuil pour detecter le silence
SILENCE_DURATION = 1.5         # Secondes de silence avant de transcrire
MAX_RECORD_DURATION = 30       # Max secondes d'enregistrement continu
WAKE_WORDS = ["hey", "ok", "assistant", "claude", "jarvis"]
USE_WAKE_WORD = False          # True = attend un mot declencheur
WHISPER_LANGUAGE = "fr"         # Forcer francais (reduit hallucinations EN de 90%)
MIN_LANGUAGE_PROB = 0.50        # Rejeter si probabilite langue < 50%

# Push-to-Talk config
PTT_ENABLED = True              # True = Push-to-Talk, False = ecoute continue
PTT_KEY = "right ctrl"          # Touche a maintenir pour parler
PTT_BIP_FREQ_ON = 800           # Hz du bip d'ouverture
PTT_BIP_FREQ_OFF = 400          # Hz du bip de fermeture
PTT_BIP_DURATION = 100          # ms

# Audio ducking config
TTS_COOLDOWN = 2.0              # Secondes d'attente APRES fin du TTS (anti-echo)
TTS_ECHO_THRESHOLD = 0.45       # Seuil de similarite pour detecter echo TTS

# Silero VAD config
USE_SILERO_VAD = True           # True = Silero VAD (ML, 4x plus precis), False = amplitude threshold
SILERO_VAD_THRESHOLD = 0.35     # Seuil speech probability (0.0-1.0, 0.35 = sensible)

# ═══════════════════════════════════════════════════════════════
# STT POST-PROCESSING - Filtre bruit + corrections
# ═══════════════════════════════════════════════════════════════

# Phrases de bruit - EXACT match (rejete si texte complet = une de ces phrases)
NOISE_EXACT = {
    "bye", "goodbye", "have a good one", "see you",
    "danke", "merci", "gracias", "ciao",
    "ok", "okay", "yep", "yeah", "yah",
    "hmm", "huh", "uh", "um", "ah", "oh",
    "the end", "world",
    "sous-titres", "sous-titrage", "subtitles",
}

# Fragments de bruit - PARTIEL match (rejete si texte CONTIENT un de ces fragments)
NOISE_FRAGMENTS = [
    "thanks for watching", "thank you for watching", "thank you very much",
    "thank you", "thanks for listening", "merci d'avoir",
    "merci a tous", "merci à tous",
    "like and subscribe", "subscribe", "hit the bell",
    "d'avoir regardé", "d'avoir regarde", "cette vidéo", "cette video",
    "that's all", "that is all",
    "sous-titres réalisés", "sous-titres realises",
    "je suis un agent", "je ne peux pas",
    "n'hésitez pas", "n'hesitez pas", "bonne journée", "bonne journee",
    "avec plaisir", "je reste à votre disposition",
    "je reste a votre disposition",
    "pouvez-vous préciser", "pouvez-vous preciser",
    "je m'améliore", "je m'ameliore",
    "chaque interaction", "opportunité pour",
]

# Corrections crypto courantes (STT mal entendu -> correct)
CRYPTO_FIXES = {
    "bcc": "btc", "btg": "btc", "bitco": "btc", "bitcoin": "btc",
    "bit coin": "btc", "b t c": "btc",
    "etg": "eth", "ether": "eth", "ethereum": "eth", "etherium": "eth",
    "sold": "sol", "soul": "sol", "solana": "sol",
    "dodge": "doge", "doj": "doge", "dogecoin": "doge",
    "sweet": "sui", "suey": "sui",
    "apt os": "apt", "aptos": "apt",
    "pepe": "pepe", "pepay": "pepe",
    "ship": "shib", "shiba": "shib",
    "wifi": "wif", "whiff": "wif",
    "bonque": "bonk", "bunk": "bonk",
    "link": "link", "chain link": "link",
    "matic": "matic", "polygon": "matic",
    "avalanche": "avax", "avacs": "avax",
}

# Corrections commandes courantes (STT -> commande)
COMMAND_FIXES = {
    "hyper": "sniper", "sniper": "sniper", "snipper": "sniper",
    "scanner": "scan", "scanne": "scan", "scannez": "scan",
    "scad": "scan", "scat": "scan", "skad": "scan",
    "scade": "scan", "scades": "scan", "scader": "scan",
    "skane": "scan", "skanne": "scan", "scanne": "scan",
    "fermer": "ferme", "fermé": "ferme",
    "copier": "copie", "copiez": "copie",
    "coller": "colle", "collez": "colle",
    "couper": "coupe",
    "annuler": "annule",
    "capture": "screenshot",
    "check marge": "check marges", "vérifie marge": "check marges",
    "breaker": "breakout", "break out": "breakout",
    "lance": "lance", "lancer": "lance", "lancez": "lance",
}

# Patterns de phrases entieres (regex -> commande normalisee)
# Capture les deformations courantes de Whisper pour les commandes trading
import re as _re
PHRASE_PATTERNS = [
    (_re.compile(r".*(?:scan|scad|scat|skad|skane)\w*\s+(\w+).*", _re.I), lambda m: f"scan {m.group(1).upper()}"),
    (_re.compile(r".*(?:lance|lancer|lancez?)\s+(?:le\s+)?(?:scan|scad|scat)\w*\s+(\w+).*", _re.I), lambda m: f"scan {m.group(1).upper()}"),
    (_re.compile(r".*check\s*(?:les?\s+)?marge.*", _re.I), lambda _: "check marges"),
    (_re.compile(r".*(?:breakout|breaker|break\s*out)\s+(\w+).*", _re.I), lambda m: f"breakout {m.group(1).upper()}"),
    (_re.compile(r".*(?:sniper|hyper|snipper)\s+(\w+).*", _re.I), lambda m: f"sniper {m.group(1).upper()}"),
    (_re.compile(r".*(?:analyse|analyze)\s+(\w+).*", _re.I), lambda m: f"analyze {m.group(1).upper()}"),
]


def stt_postprocess(text):
    """Post-traitement STT: filtre bruit, corrige crypto/commandes"""
    if not text:
        return None

    clean = text.strip().rstrip(".")

    # Filtre 1: trop court (1-2 chars)
    if len(clean) <= 2:
        return None

    lower = clean.lower()

    # Filtre 2: match exact de phrases courtes de bruit
    if lower in NOISE_EXACT:
        return None

    # Filtre 3: 1 mot courant (anglais/francais)
    single_word_noise = {"what", "yes", "no", "hey", "hi", "hello", "so",
                         "well", "right", "sure", "fine", "good", "nice",
                         "great", "wow", "oui", "non", "bon", "bien",
                         "voilà", "voila", "allez", "tiens", "super",
                         "d'accord", "stop"}
    if lower in single_word_noise:
        return None

    # Filtre 4: PARTIEL - rejeter si le texte contient un fragment de bruit
    for fragment in NOISE_FRAGMENTS:
        if fragment in lower:
            return None

    # Filtre 5: texte qui semble etre une reponse IA (pas une commande utilisateur)
    # Heuristique: phrases longues (>60 chars) avec style formel
    if len(clean) > 60:
        ia_markers = ["je suis", "je ne suis pas", "je reste", "n'hésitez",
                      "n'hesitez", "votre question", "votre demande",
                      "pour vous aider", "bonne journée", "avec plaisir"]
        if any(m in lower for m in ia_markers):
            return None

    # Corriger phrases entieres (prioritaire sur mot-a-mot)
    for pattern, replacer in PHRASE_PATTERNS:
        m = pattern.match(lower)
        if m:
            result = replacer(m)
            try:
                print(f"  [PHRASE-FIX] '{clean}' -> '{result}'")
            except UnicodeEncodeError:
                print(f"  [PHRASE-FIX] correction appliquee")
            return result

    # Corriger commandes mot-a-mot
    words = clean.split()
    corrected_words = []
    for w in words:
        low = w.lower().strip(".,!?")
        if low in COMMAND_FIXES:
            corrected_words.append(COMMAND_FIXES[low])
        elif low in CRYPTO_FIXES:
            corrected_words.append(CRYPTO_FIXES[low].upper())
        else:
            corrected_words.append(w)

    result = " ".join(corrected_words)

    # Log si correction appliquee
    if result != clean:
        try:
            print(f"  [AUTOCORRECT] '{clean}' -> '{result}'")
        except UnicodeEncodeError:
            print(f"  [AUTOCORRECT] correction appliquee")

    return result


# ═══════════════════════════════════════════════════════════════
# VOICE LISTENER
# ═══════════════════════════════════════════════════════════════

class VoiceListener:
    def __init__(self, hooks_manager):
        self.hooks = hooks_manager
        self.model = None
        self.vad_model = None           # Silero VAD model
        self.is_listening = True
        self.ptt_active = False         # Push-to-Talk: micro ouvert?
        self._tts_ref = None            # Reference TTSEngine pour audio ducking
        self._tts_last_spoke = 0.0      # Timestamp fin dernier TTS (pour cooldown)
        self._tts_last_text = ""        # Dernier texte TTS (pour echo detection)
        self._load_model()
        self._load_vad()

    def _check_cuda_available(self, timeout=10):
        """Verifie CUDA avec timeout pour eviter hang infini si driver corrompu"""
        if os.environ.get("CUDA_VISIBLE_DEVICES") == "":
            return False
        import concurrent.futures
        def _check():
            import torch
            return torch.cuda.is_available()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(_check)
                return future.result(timeout=timeout)
        except (concurrent.futures.TimeoutError, Exception) as e:
            print(f"  [CUDA] Detection timeout ({timeout}s) - driver probablement corrompu")
            print(f"  [CUDA] Fallback CPU automatique")
            os.environ["CUDA_VISIBLE_DEVICES"] = ""
            return False

    def _load_model(self):
        """Charge le modele Whisper (peut prendre quelques secondes)"""
        global WHISPER_DEVICE
        # Auto-detect: verifier CUDA avec timeout anti-hang
        if WHISPER_DEVICE == "cuda":
            if not self._check_cuda_available(timeout=10):
                print(f"  [WHISPER] CUDA indisponible, bascule sur CPU")
                WHISPER_DEVICE = "cpu"

        device = WHISPER_DEVICE
        compute = WHISPER_COMPUTE if device == "cuda" else "int8"
        print(f"\n  [WHISPER] Chargement modele '{WHISPER_MODEL}' sur {device}...")
        try:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(
                WHISPER_MODEL,
                device=device,
                compute_type=compute,
            )
            print(f"  [WHISPER] Modele charge sur {device}. Pret.")
        except Exception as e:
            print(f"  [WHISPER] Erreur {device}, fallback CPU: {e}")
            try:
                os.environ["CUDA_VISIBLE_DEVICES"] = ""
                from faster_whisper import WhisperModel
                self.model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
                print(f"  [WHISPER] Modele charge sur CPU.")
            except Exception as e2:
                print(f"  [WHISPER] ERREUR: {e2}")
                self.model = None

    def _load_vad(self):
        """Charge Silero VAD (rapide, ~50ms, CPU only)"""
        if not USE_SILERO_VAD:
            print("  [VAD] Silero desactive, utilisation amplitude threshold")
            return
        try:
            import torch
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                trust_repo=True,
                onnx=False,
            )
            self.vad_model = model
            self._vad_get_speech = utils[0]  # get_speech_timestamps
            print("  [VAD] Silero VAD charge (ML, CPU)")
        except Exception as e:
            print(f"  [VAD] Silero indisponible ({e}), fallback amplitude")
            self.vad_model = None

    def _is_speech_silero(self, audio_chunk_np):
        """Detecte parole dans un chunk audio via Silero VAD"""
        if self.vad_model is None:
            return None  # Fallback: laisser l'amplitude decider
        try:
            import torch
            tensor = torch.from_numpy(audio_chunk_np.copy()).float()
            if tensor.abs().max() > 1.0:
                tensor = tensor / 32768.0
            confidence = self.vad_model(tensor, SAMPLE_RATE).item()
            return confidence >= SILERO_VAD_THRESHOLD
        except Exception:
            return None  # Fallback silencieux

    def _start_ptt_listener(self):
        """Thread qui ecoute la touche PTT (RIGHT_CTRL)"""
        import keyboard

        key_name = PTT_KEY.split()[-1]  # "ctrl" from "right ctrl"

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

    def _is_tts_echo(self, text):
        """Detecte si le texte capture est un echo du dernier TTS output"""
        if not self._tts_last_text or not text:
            return False
        # Verifier seulement si capture dans les 5 sec apres TTS
        if time.time() - self._tts_last_spoke > 5.0:
            return False
        from difflib import SequenceMatcher
        ratio = SequenceMatcher(None, text.lower()[:100], self._tts_last_text.lower()[:100]).ratio()
        if ratio >= TTS_ECHO_THRESHOLD:
            return True
        # Verifier aussi si des mots cles du TTS sont dans le texte capture
        tts_words = set(self._tts_last_text.lower().split())
        stt_words = set(text.lower().split())
        if len(tts_words) > 3 and len(stt_words) > 3:
            overlap = len(tts_words & stt_words) / max(len(stt_words), 1)
            if overlap >= 0.4:
                return True
        return False

    def start_listening(self):
        """Boucle d'ecoute principale avec PyAudio"""
        import pyaudio

        pa = pyaudio.PyAudio()

        # Trouver le micro (WH-1000XM4 Hands-Free de preference)
        mic_index = self._find_microphone(pa)

        print(f"\n{'='*60}")
        print(f"  VOICE DRIVER ACTIF")
        print(f"  Micro: index {mic_index}")
        print(f"  Modele: {WHISPER_MODEL} ({WHISPER_DEVICE})")
        print(f"  Silence: {SILENCE_DURATION}s | Max: {MAX_RECORD_DURATION}s")
        print(f"  Wake word: {'OUI - ' + str(WAKE_WORDS) if USE_WAKE_WORD else 'NON (toujours actif)'}")
        ptt_status = "PTT (RIGHT_CTRL)" if PTT_ENABLED else "Ecoute continue"
        print(f"  Mode: {ptt_status}")
        print(f"  Ctrl+C pour arreter")
        print(f"{'='*60}\n")

        # Connecter le TTS au listener pour audio ducking + echo detection
        if hasattr(self.hooks, 'tts') and self.hooks.tts:
            self._tts_ref = self.hooks.tts
            # Patcher TTSEngine.speak pour tracker fin TTS + dernier texte
            original_speak = self.hooks.tts.speak
            def _tracked_speak(text, _orig=original_speak):
                _orig(text)
                self._tts_last_spoke = time.time()
                self._tts_last_text = text[:200] if text else ""
            self.hooks.tts.speak = _tracked_speak

        # Demarrer le thread PTT si actif
        if PTT_ENABLED:
            threading.Thread(target=self._start_ptt_listener, daemon=True).start()
            print(f"  [PTT] Push-to-Talk actif: maintenir {PTT_KEY}")

        stream = pa.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            input_device_index=mic_index,
            frames_per_buffer=CHUNK_SIZE,
        )

        print("  [MIC] Ecoute active...\n")

        try:
            while self.is_listening:
                # Audio ducking: skip si TTS parle (anti-larsen)
                if self._tts_ref and self._tts_ref.is_speaking:
                    time.sleep(0.1)
                    continue
                # Cooldown post-TTS: attendre X sec apres fin du TTS (echo casque)
                if self._tts_last_spoke > 0:
                    elapsed_since_tts = time.time() - self._tts_last_spoke
                    if elapsed_since_tts < TTS_COOLDOWN:
                        time.sleep(0.1)
                        continue
                # Push-to-Talk: skip si touche pas maintenue
                if PTT_ENABLED and not self.ptt_active:
                    time.sleep(0.05)
                    continue

                frames = self._record_until_silence(stream)

                if frames and len(frames) > SAMPLE_RATE:  # Au moins 1 seconde
                    text = self._transcribe(frames)
                    if text and len(text.strip()) > 1:
                        # === COUCHE 0: Detection echo TTS ===
                        if self._is_tts_echo(text):
                            print(f"  [ECHO] Rejete (echo TTS detecte)")
                            continue

                        # === COUCHE 1: Post-processing STT ===
                        text = stt_postprocess(text)
                        if not text:
                            print("  [NOISE] Rejete (bruit/hallucination)")
                            continue

                        # Verifier wake word si actif
                        if USE_WAKE_WORD:
                            if not any(w in text.lower() for w in WAKE_WORDS):
                                continue
                            for w in WAKE_WORDS:
                                text = text.lower().replace(w, "").strip()

                        if len(text) > 1:
                            self.hooks.process_input(text)
        except KeyboardInterrupt:
            print("\n  [STOP] Arret demande.")
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

    def _find_microphone(self, pa):
        """Trouve le meilleur micro disponible (teste avant de choisir)"""
        import pyaudio
        print("\n  [MIC] Recherche microphone...")
        preferred = []
        fallbacks = []

        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                name = info["name"]
                try:
                    print(f"  [MIC] Trouve: {name} (index {i})", end="")
                except UnicodeEncodeError:
                    print(f"  [MIC] Trouve: device index {i}", end="")
                if "wh-1000" in name.lower():
                    preferred.insert(0, i)
                    print(" ** WH-1000XM4 **")
                elif "hands-free" in name.lower():
                    preferred.append(i)
                    print(" ** HANDS-FREE **")
                elif "realtek" in name.lower() and "mic" in name.lower():
                    fallbacks.insert(0, i)
                    print(" (Realtek mic)")
                elif "microphone" in name.lower():
                    fallbacks.append(i)
                    print("")
                else:
                    print("")

        # Tester chaque micro candidat (preferred puis fallbacks)
        for idx in preferred + fallbacks:
            try:
                test = pa.open(format=pyaudio.paInt16, channels=CHANNELS, rate=SAMPLE_RATE,
                               input=True, input_device_index=idx, frames_per_buffer=CHUNK_SIZE)
                test.read(CHUNK_SIZE, exception_on_overflow=False)
                test.stop_stream()
                test.close()
                print(f"  [MIC] Selectionne: index {idx} (teste OK)")
                return idx
            except Exception as e:
                print(f"  [MIC] Index {idx} inaccessible ({e}), skip.")

        # Fallback: micro par defaut du systeme
        try:
            default = pa.get_default_input_device_info()
            print(f"  [MIC] Default: index {default['index']}")
            return default["index"]
        except Exception:
            # Dernier recours: scanner TOUS les devices et prendre le premier qui marche
            print("  [MIC] Scan exhaustif de tous les devices...")
            for i in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(i)
                if info["maxInputChannels"] > 0:
                    try:
                        test = pa.open(format=pyaudio.paInt16, channels=CHANNELS, rate=SAMPLE_RATE,
                                       input=True, input_device_index=i, frames_per_buffer=CHUNK_SIZE)
                        test.stop_stream()
                        test.close()
                        print(f"  [MIC] Fallback: index {i} fonctionne")
                        return i
                    except Exception:
                        pass
            print("  [MIC] ERREUR: aucun micro disponible!")
            return 0

    def _record_until_silence(self, stream):
        """Enregistre jusqu'a detection de silence"""
        frames = []
        silent_chunks = 0
        max_chunks = int(MAX_RECORD_DURATION * SAMPLE_RATE / CHUNK_SIZE)
        silence_chunks_needed = int(SILENCE_DURATION * SAMPLE_RATE / CHUNK_SIZE)
        is_speaking = False

        for _ in range(max_chunks):
            if not self.is_listening:
                break

            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            except Exception:
                continue

            audio_data = np.frombuffer(data, dtype=np.int16)

            # Detection parole: Silero VAD (ML) ou amplitude (fallback)
            speech_detected = False
            silero_result = self._is_speech_silero(audio_data) if self.vad_model else None
            if silero_result is not None:
                speech_detected = silero_result
            else:
                speech_detected = np.abs(audio_data).mean() > SILENCE_THRESHOLD

            if speech_detected:
                is_speaking = True
                silent_chunks = 0
                frames.append(data)
            elif is_speaking:
                silent_chunks += 1
                frames.append(data)
                if silent_chunks >= silence_chunks_needed:
                    break

        return b"".join(frames) if is_speaking else None

    def _transcribe(self, audio_bytes):
        """Transcription avec faster-whisper"""
        if not self.model:
            return None

        # Convertir bytes -> numpy float32
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        try:
            segments, info = self.model.transcribe(
                audio_np,
                beam_size=5,
                language=WHISPER_LANGUAGE,  # Forcer francais pour reduire hallucinations
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=200,
                ),
            )

            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())

            full_text = " ".join(text_parts).strip()

            if full_text:
                lang = info.language if hasattr(info, "language") else "?"
                prob = info.language_probability if hasattr(info, "language_probability") else 0
                prob_str = f"{prob:.0%}" if isinstance(prob, float) else "?"

                # Filtrer par confiance langue - rejeter si trop faible
                if isinstance(prob, float) and prob < MIN_LANGUAGE_PROB:
                    try:
                        print(f"  [STT] ({lang} {prob_str}) REJETE (confiance trop basse)")
                    except UnicodeEncodeError:
                        print(f"  [STT] REJETE (confiance trop basse)")
                    return None

                try:
                    print(f"  [STT] ({lang} {prob_str}) \"{full_text}\"")
                except UnicodeEncodeError:
                    safe = full_text.encode('ascii', errors='replace').decode('ascii')
                    print(f"  [STT] ({lang} {prob_str}) \"{safe}\"")

            return full_text

        except Exception as e:
            try:
                print(f"  [STT] Erreur: {e}")
            except UnicodeEncodeError:
                print(f"  [STT] Erreur: {str(e).encode('ascii', errors='replace').decode('ascii')}")
            return None


# ═══════════════════════════════════════════════════════════════
# MODE CLAVIER (DEBUG)
# ═══════════════════════════════════════════════════════════════

def keyboard_mode(hooks):
    """Mode clavier pour tester sans micro"""
    print(f"\n{'='*60}")
    print(f"  VOICE DRIVER - MODE CLAVIER (debug)")
    print(f"  Tapez vos commandes. 'quit' pour sortir.")
    print(f"{'='*60}\n")

    while True:
        try:
            text = input("  Vous > ").strip()
            if text.lower() in ("quit", "exit", "q"):
                break
            if text:
                result = hooks.process_input(text)
                print(f"  -> {result}\n")
        except (KeyboardInterrupt, EOFError):
            break

    print("\n  [BYE]")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    global WHISPER_MODEL, WHISPER_DEVICE, USE_WAKE_WORD, PTT_ENABLED, WHISPER_LANGUAGE

    parser = argparse.ArgumentParser(description="Voice Driver - Systeme vocal IA")
    parser.add_argument("--keyboard", "-k", action="store_true", help="Mode clavier (debug)")
    parser.add_argument("--test", "-t", action="store_true", help="Test rapide du systeme")
    parser.add_argument("--model", "-m", default=WHISPER_MODEL, help="Modele Whisper (small/medium/large-v3)")
    parser.add_argument("--cpu", action="store_true", help="Forcer CPU")
    parser.add_argument("--wake", "-w", action="store_true", help="Activer wake word")
    parser.add_argument("--ptt", action="store_true", help="Mode Push-to-Talk (RIGHT_CTRL)")
    parser.add_argument("--continuous", "-c", action="store_true", help="Force ecoute continue (desactive PTT)")
    parser.add_argument("--lang", default=WHISPER_LANGUAGE, help="Langue Whisper (fr/en/auto)")
    args = parser.parse_args()

    WHISPER_MODEL = MODEL_ALIASES.get(args.model, args.model)
    if args.cpu:
        WHISPER_DEVICE = "cpu"
    if args.wake:
        USE_WAKE_WORD = True
    if args.continuous:
        PTT_ENABLED = False
    elif args.ptt:
        PTT_ENABLED = True
    # Default: PTT_ENABLED = True (defini en constante)
    if args.lang == "auto":
        WHISPER_LANGUAGE = None
    else:
        WHISPER_LANGUAGE = args.lang

    print("""
  === VOICE DRIVER ===
  WhisperFlow + Logic Hooks + Router Brain
    """)

    # Init Router
    print("  [INIT] Router Brain...")
    router = RouterBrain()

    # Init Hooks
    print("  [INIT] Logic Hooks...")
    hooks = LogicHookManager(router=router)

    if args.test:
        print("\n  --- TEST MODE ---")
        # Test quick action
        hooks.process_input("copie")
        # Test IA
        hooks.process_input("Explique le RSI en une phrase")
        print("  --- FIN TEST ---")
        return

    if args.keyboard:
        keyboard_mode(hooks)
    else:
        listener = VoiceListener(hooks)
        listener.start_listening()


if __name__ == "__main__":
    main()
