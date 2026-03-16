"""JARVIS Voice Pipeline v3.1 — Linux Native & Open Source (Vosk + Whisper-Flow + Piper).

Ameliorations v3.1:
- Detection de silence (VAD) pour duree d'enregistrement adaptative
- Bip sonore au wake-word
- Mode conversation continue (5s sans re-dire "Jarvis")
- Corrections vocales SQL appliquees avant dispatch
- Retry STT en cas d'echec
- Logging dans voice_analytics

Pipeline:
1. Vosk ('Jarvis') wake-word detector (Offline, no API key).
2. Whisper-Flow (Local WebSocket) STT for commands.
3. Voice Router dispatch (682+ commandes, 5 modules).
4. Piper TTS (Local) for natural response.
"""

import asyncio
import json
import logging
import os
import struct
import subprocess
import time

import numpy as np
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import websockets

logger = logging.getLogger("jarvis.voice_pipeline")

# Configuration
VOSK_MODEL_PATH = "/home/turbo/jarvis/data/vosk-model-small-fr-0.22"
WHISPER_WS_URL = os.getenv("WHISPER_WS_URL", "ws://127.0.0.1:8000/whisper")
PIPER_BIN = "/home/turbo/jarvis/.venv/bin/piper"
PIPER_MODEL = "/home/turbo/jarvis/data/piper/fr_FR-siwis-medium.onnx"
SAMPLE_RATE = 16000
CHUNK_SIZE = 800  # 50ms a 16kHz

# VAD (Voice Activity Detection) parametres
SILENCE_THRESHOLD = 500    # Amplitude RMS en dessous = silence
SILENCE_DURATION = 1.5     # Secondes de silence pour arreter l'enregistrement
MAX_RECORD_SECONDS = 10    # Duree max d'enregistrement
MIN_RECORD_SECONDS = 1.0   # Duree min avant d'accepter le silence

# Mode conversation continue
CONVO_TIMEOUT = 5.0  # Secondes sans commande avant de revenir en mode wake-word


class JarvisVoiceV3:
    def __init__(self):
        self.is_listening = True
        self.vosk_model = None
        self.recognizer = None
        self._in_conversation = False
        self._last_command_time = 0
        self._command_count = 0

    async def play_beep(self, freq: int = 800, duration_ms: int = 150):
        """Jouer un bip court pour indiquer l'ecoute."""
        try:
            t = np.linspace(0, duration_ms / 1000, int(SAMPLE_RATE * duration_ms / 1000), dtype=np.float32)
            env = np.ones_like(t)
            fade = int(len(t) * 0.1)
            env[:fade] = np.linspace(0, 1, fade)
            env[-fade:] = np.linspace(1, 0, fade)
            tone = (env * 0.3 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
            sd.play(tone, samplerate=SAMPLE_RATE, blocking=True)
        except Exception:
            pass

    async def play_success_beep(self):
        """Bip de succes: deux tons montants rapides."""
        await self.play_beep(freq=600, duration_ms=80)
        await self.play_beep(freq=900, duration_ms=80)

    async def play_error_beep(self):
        """Bip d'erreur: ton descendant."""
        await self.play_beep(freq=400, duration_ms=200)

    def _send_notification(self, title: str, message: str, icon: str = "dialog-information"):
        """Envoyer une notification desktop silencieuse."""
        try:
            subprocess.Popen(
                ["notify-send", "-i", icon, title, message[:200]],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    async def speak(self, text: str):
        """TTS via Piper (100% Local)."""
        if not text:
            return
        # Tronquer les reponses trop longues
        speak_text = text[:300]
        logger.info("[TTS] %s", speak_text[:80])
        try:
            process = subprocess.Popen(
                [PIPER_BIN, "-m", PIPER_MODEL, "--output_raw"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            stdout, _ = process.communicate(input=speak_text.encode("utf-8"), timeout=15)
            if stdout:
                play_proc = subprocess.Popen(
                    ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw"],
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                play_proc.communicate(input=stdout, timeout=15)
        except subprocess.TimeoutExpired:
            logger.warning("[TTS] Timeout")
        except Exception as e:
            logger.error("[TTS ERROR] %s", e)

    def _rms(self, audio_chunk: np.ndarray) -> float:
        """Calcule le RMS (Root Mean Square) d'un chunk audio."""
        if len(audio_chunk) == 0:
            return 0
        samples = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32)
        return float(np.sqrt(np.mean(samples ** 2)))

    async def transcribe_command(self, stream, retry: int = 1) -> str:
        """Enregistre avec VAD (detection silence) et transcrit via Whisper.

        Arrete l'enregistrement apres SILENCE_DURATION secondes de silence,
        ou MAX_RECORD_SECONDS au maximum.
        """
        logger.info("[REC] Ecoute de la commande (max %ds, silence=%.1fs)...",
                     MAX_RECORD_SECONDS, SILENCE_DURATION)
        frames = []
        silence_chunks = 0
        chunks_per_second = SAMPLE_RATE / CHUNK_SIZE
        silence_limit = int(SILENCE_DURATION * chunks_per_second)
        max_chunks = int(MAX_RECORD_SECONDS * chunks_per_second)
        min_chunks = int(MIN_RECORD_SECONDS * chunks_per_second)
        total_chunks = 0

        for _ in range(max_chunks):
            data, _ = stream.read(CHUNK_SIZE)
            frames.append(data)
            total_chunks += 1

            rms = self._rms(data)
            if rms < SILENCE_THRESHOLD:
                silence_chunks += 1
            else:
                silence_chunks = 0

            # Arreter si assez de silence APRES la duree minimale
            if total_chunks > min_chunks and silence_chunks >= silence_limit:
                logger.info("[REC] Silence detecte apres %.1fs", total_chunks / chunks_per_second)
                break

        duration = total_chunks / chunks_per_second
        logger.info("[REC] Enregistre %.1fs (%d chunks)", duration, total_chunks)

        if not frames:
            return ""

        audio_cmd = np.concatenate(frames)

        # Tentatives de transcription
        for attempt in range(retry + 1):
            try:
                async with websockets.connect(WHISPER_WS_URL) as ws:
                    await ws.send(audio_cmd.tobytes())
                    response = await asyncio.wait_for(ws.recv(), timeout=10)
                    text = json.loads(response).get("text", "").lower().strip()
                    if text:
                        return text
            except asyncio.TimeoutError:
                logger.warning("[STT] Timeout (tentative %d/%d)", attempt + 1, retry + 1)
            except Exception as e:
                logger.warning("[STT] Erreur: %s (tentative %d/%d)", e, attempt + 1, retry + 1)
                if attempt < retry:
                    await asyncio.sleep(0.5)

        return ""

    async def handle_command(self, cmd_text: str) -> bool:
        """Traite une commande vocale. Retourne True si on reste en mode conversation."""
        # Appliquer les corrections vocales SQL
        try:
            from src.db_boot_validator import apply_voice_correction
            corrected = apply_voice_correction(cmd_text)
            if corrected != cmd_text:
                logger.info("[CORR] '%s' → '%s'", cmd_text, corrected)
                cmd_text = corrected
        except Exception:
            pass

        logger.info("[CMD] '%s'", cmd_text)

        # Commandes de controle pipeline
        if cmd_text in ("stop", "arrete", "silence", "tais-toi", "au revoir"):
            await self.speak("A bientot!")
            return False
        if cmd_text in ("mode continu", "reste a l'ecoute", "continue d'ecouter"):
            self._in_conversation = True
            await self.speak("Mode continu active. Dites 'stop' pour arreter.")
            return True

        # Si en mode enregistrement macro, capturer la commande
        try:
            from src.voice_macros import macro_manager
            if macro_manager.is_recording and cmd_text not in ("stop macro", "arrete la macro", "fin macro"):
                macro_manager.add_command(cmd_text)
                logger.info("[MACRO] Commande ajoutee: %s", cmd_text)
        except Exception:
            pass

        # Dispatch via Voice Router
        try:
            from src.voice_router import route_voice_command
            result = route_voice_command(cmd_text)
            self._command_count += 1
            self._last_command_time = time.time()

            if result.get("success"):
                response = result.get("result", "OK")
                mod = result.get("module", "").split(".")[-1]
                method = result.get("method", "?")
                conf = result.get("confidence", 0)
                latency = result.get("latency_ms", 0)
                corrected_from = result.get("corrected_from", "")

                log_extra = f" (corrige depuis '{corrected_from}')" if corrected_from else ""
                logger.info("[OK] [%s] %s → %s (conf=%.1f, lat=%.0fms)%s",
                           mod, method, response[:80], conf, latency, log_extra)

                # Notification desktop pour les commandes systeme
                if mod in ("linux_desktop_control", "ia_conversationnel"):
                    self._send_notification("JARVIS", f"{method}: {response[:100]}")

                # Reponse vocale adaptee
                if len(response) > 200:
                    lines = response.split("\n")
                    speak_text = lines[0] if lines else response[:200]
                    await self.speak(speak_text)
                else:
                    await self.speak(response)
                return True
            else:
                logger.info("[?] Commande non reconnue: %s", cmd_text)
                await self.play_error_beep()
                await self.speak(f"Je n'ai pas compris: {cmd_text}")
                return True

        except Exception as e:
            logger.error("[ERR] %s", e)
            await self.speak("Erreur de traitement")
            return True

    async def run(self):
        logger.info("=" * 50)
        logger.info("JARVIS Voice Pipeline v3.1")
        logger.info("=" * 50)

        # Initialiser Vosk
        logger.info("Initialisation Vosk (modele: %s)...", VOSK_MODEL_PATH)
        if not os.path.exists(VOSK_MODEL_PATH):
            logger.info("Telechargement du modele Vosk FR...")
            os.makedirs(os.path.dirname(VOSK_MODEL_PATH), exist_ok=True)
            subprocess.run(["wget", "-qO", "/tmp/vosk-fr.zip",
                          "https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip"],
                         check=False)
            subprocess.run(["unzip", "-q", "/tmp/vosk-fr.zip", "-d",
                          "/home/turbo/jarvis/data/"], check=False)

        self.vosk_model = Model(VOSK_MODEL_PATH)
        self.recognizer = KaldiRecognizer(self.vosk_model, SAMPLE_RATE)

        # Precharger le cache vocal SQL
        try:
            from src.db_boot_validator import get_voice_cache
            cache = get_voice_cache()
            logger.info("Cache vocal: %d corrections chargees", len(cache.get("corrections", {})))
        except Exception:
            pass

        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=CHUNK_SIZE,
                               dtype="int16", channels=1) as stream:
            logger.info("Pret! Dites 'Jarvis' pour m'activer. (682+ commandes vocales)")
            print("[JARVIS] Pret ! Dites 'Jarvis' pour m'activer.")

            while self.is_listening:
                data, _ = stream.read(CHUNK_SIZE)

                if self.recognizer.AcceptWaveform(bytes(data)):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "")

                    if "jarvis" in text.lower():
                        logger.info("[WAKE] Detecte!")

                        # Bip + "Oui?"
                        await self.play_beep(freq=800, duration_ms=100)
                        await self.speak("Oui?")

                        # Mode conversation: boucle de commandes
                        self._in_conversation = True
                        while self._in_conversation:
                            cmd_text = await self.transcribe_command(stream, retry=1)
                            if not cmd_text:
                                # Pas de commande detectee
                                if time.time() - self._last_command_time > CONVO_TIMEOUT:
                                    self._in_conversation = False
                                    await self.play_beep(freq=400, duration_ms=80)
                                    logger.info("[CONV] Fin mode conversation (timeout)")
                                    break
                                continue

                            stay = await self.handle_command(cmd_text)
                            if not stay:
                                self._in_conversation = False
                                break

                            # En mode non-continu, sortir apres une commande
                            if not self._in_conversation:
                                break

                            # Bip court pour indiquer qu'on ecoute encore
                            await self.play_beep(freq=600, duration_ms=60)

                        # Reset le recognizer pour eviter les faux positifs
                        self.recognizer = KaldiRecognizer(self.vosk_model, SAMPLE_RATE)

                # Verifier aussi les resultats partiels pour le wake-word
                # (plus reactif que d'attendre le resultat final)
                else:
                    partial = json.loads(self.recognizer.PartialResult())
                    partial_text = partial.get("partial", "")
                    if "jarvis" in partial_text.lower() and len(partial_text.split()) <= 3:
                        # Forcer la reconnaissance du wake-word
                        self.recognizer.Reset()
                        logger.info("[WAKE] Detecte (partiel)!")
                        await self.play_beep(freq=800, duration_ms=100)
                        await self.speak("Oui?")

                        cmd_text = await self.transcribe_command(stream, retry=1)
                        if cmd_text:
                            await self.handle_command(cmd_text)

                        self.recognizer = KaldiRecognizer(self.vosk_model, SAMPLE_RATE)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    pipeline = JarvisVoiceV3()
    asyncio.run(pipeline.run())
