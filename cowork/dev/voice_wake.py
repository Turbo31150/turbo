#!/usr/bin/env python3
"""JARVIS Wake Word Detector — listens for 'Jarvis' wake word."""
import argparse, subprocess, sys, time

def listen_loop(wake_word: str = "jarvis", callback_url: str = None):
    print(f"Listening for wake word: '{wake_word}'...")
    print("(Using Windows Speech Recognition)")

    ps_script = f'''
    Add-Type -AssemblyName System.Speech
    $recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine
    $recognizer.SetInputToDefaultAudioDevice()
    $grammar = New-Object System.Speech.Recognition.DictationGrammar
    $recognizer.LoadGrammar($grammar)
    while ($true) {{
        $result = $recognizer.Recognize((New-Object TimeSpan(0,0,3)))
        if ($result -and $result.Text -match "{wake_word}") {{
            Write-Output "WAKE: $($result.Text)"
            break
        }}
    }}
    '''
    try:
        r = subprocess.run(["bash", "-c", ps_script], capture_output=True, text=True, timeout=300)
        if r.stdout.strip():
            print(f"Wake word detected! Full: {r.stdout.strip()}")
            if callback_url:
                import urllib.request
                urllib.request.urlopen(callback_url, timeout=5)
            return True
    except subprocess.TimeoutExpired:
        print("Listen timeout")
    return False

def main():
    parser = argparse.ArgumentParser(description="JARVIS wake word detector")
    parser.add_argument("--word", default="jarvis", help="Wake word to listen for")
    parser.add_argument("--callback", help="URL to call when wake word detected")
    parser.add_argument("--once", action="store_true", help="Listen once and exit")
    args = parser.parse_args()

    if args.once:
        listen_loop(args.word, args.callback)
    else:
        while True:
            if listen_loop(args.word, args.callback):
                time.sleep(1)

if __name__ == "__main__":
    main()
