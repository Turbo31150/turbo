#!/usr/bin/env python3
"""JARVIS Voice TTS — text-to-speech via edge-tts."""
import argparse, asyncio, subprocess, sys, tempfile, os

VOICE = "fr-FR-DeniseNeural"

async def speak_edge_tts(text: str, voice: str = VOICE):
    try:
        import edge_tts
        comm = edge_tts.Communicate(text, voice)
        tmp = os.path.join(tempfile.gettempdir(), "jarvis_tts.mp3")
        await comm.save(tmp)
        if sys.platform == "win32":
            subprocess.run(
                ["bash", "-c", f'(New-Object Media.SoundPlayer "{tmp}").PlaySync()'],
                capture_output=True, timeout=30,
            )
        return True
    except ImportError:
        return False

def speak_pyttsx3(text: str):
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 160)
        engine.say(text)
        engine.runAndWait()
        return True
    except ImportError:
        return False

def main():
    parser = argparse.ArgumentParser(description="JARVIS TTS")
    parser.add_argument("text", nargs="?", default="Systeme JARVIS operationnel")
    parser.add_argument("--voice", default=VOICE)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if not asyncio.run(speak_edge_tts(args.text, args.voice)):
        if not speak_pyttsx3(args.text):
            print(f"TTS unavailable. Text: {args.text}")
            sys.exit(1)
    print(f"Spoke: {args.text[:60]}...")

if __name__ == "__main__":
    main()
