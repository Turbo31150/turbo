#!/usr/bin/env python3
"""JARVIS Voice STT — speech-to-text via whisper or Windows API."""
import argparse, json, subprocess, sys, os

def stt_whisper(audio_path: str) -> str:
    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_path, language="fr")
        return result.get("text", "")
    except ImportError:
        return ""

def stt_windows(duration: int = 5) -> str:
    ps_script = f'''
    Add-Type -AssemblyName System.Speech
    $recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine
    $recognizer.SetInputToDefaultAudioDevice()
    $grammar = New-Object System.Speech.Recognition.DictationGrammar
    $recognizer.LoadGrammar($grammar)
    $result = $recognizer.Recognize((New-Object TimeSpan(0,0,{duration})))
    if ($result) {{ $result.Text }}
    '''
    try:
        r = subprocess.run(["powershell", "-c", ps_script], capture_output=True, text=True, timeout=duration+5)
        return r.stdout.strip()
    except Exception:
        return ""

def main():
    parser = argparse.ArgumentParser(description="JARVIS Speech-to-Text")
    parser.add_argument("--file", help="Audio file path (uses whisper)")
    parser.add_argument("--mic", action="store_true", help="Use microphone (Windows Speech API)")
    parser.add_argument("--duration", type=int, default=5, help="Mic recording duration (seconds)")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.file:
        text = stt_whisper(args.file)
    elif args.mic:
        text = stt_windows(args.duration)
    else:
        parser.print_help()
        return

    if text:
        print(f"Transcription: {text}")
    else:
        print("No speech detected or STT unavailable")

if __name__ == "__main__":
    main()
