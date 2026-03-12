#!/usr/bin/env python3
"""JARVIS Voice Engine v2.0 - Wake Word -> Whisper -> MCP -> TTS."""

import os
import struct
import time
import json
import asyncio
import websockets
import pvporcupine
import pyaudio
import numpy as np
import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration
ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY", "")
WHISPER_URL = os.getenv("WHISPER_FLOW_WS_URL", "ws://localhost:9000")
MCP_URL = "http://localhost:18789/query"
TTS_SCRIPT = "/home/turbo/jarvis-m1-ops/scripts/jarvis-tts.sh"

class JarvisVoice:
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self.porcupine = pvporcupine.create(access_key=ACCESS_KEY, keywords=["jarvis"])
        self.stream = self.pa.open(
            rate=self.porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self.porcupine.frame_length
        )

    def speak(self, text):
        """Invoke the TTS script."""
        os.system(f"{TTS_SCRIPT} \"{text}\" &")

    async def send_to_mcp(self, text):
        """Route transcribed text to JARVIS MCP Server."""
        try:
            print(f"[VOICE] Envoi au MCP: {text}")
            res = requests.post(MCP_URL, json={"prompt": text, "source": "voice"}, timeout=15)
            response_data = res.json()
            answer = response_data.get("answer", "Commande exécutée, Monsieur.")
            self.speak(answer)
        except Exception as e:
            print(f"[ERROR] MCP Routing failed: {e}")
            self.speak("Erreur de liaison avec le serveur central.")

    async def record_and_transcribe(self):
        """Record 4 seconds of audio and send to Whisper-Flow."""
        print("[VOICE] Écoute de la commande...")
        frames = []
        # Record approx 4 seconds
        for _ in range(0, int(self.porcupine.sample_rate / self.porcupine.frame_length * 4)):
            data = self.stream.read(self.porcupine.frame_length)
            frames.append(data)
        
        audio_data = b''.join(frames)
        
        try:
            async with websockets.connect(WHISPER_URL) as ws:
                await ws.send(audio_data)
                result = await ws.recv()
                text = json.loads(result).get("text", "").strip()
                if text:
                    print(f"[VOICE] Transcrit: {text}")
                    await self.send_to_mcp(text)
        except Exception as e:
            print(f"[ERROR] Whisper connection failed: {e}")
            self.speak("Le moteur de transcription est hors ligne.")

    async def run(self):
        print("[JARVIS] Système vocal en ligne. En attente du mot-clé...")
        try:
            while True:
                pcm = self.stream.read(self.porcupine.frame_length)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
                
                if self.porcupine.process(pcm) >= 0:
                    print("[JARVIS] Oui, Monsieur ?")
                    os.system("play -q -n synth 0.1 sin 880 &") # Bip d'activation
                    await self.record_and_transcribe()
        finally:
            self.stream.close()
            self.porcupine.delete()

if __name__ == "__main__":
    jarvis = JarvisVoice()
    asyncio.run(jarvis.run())
