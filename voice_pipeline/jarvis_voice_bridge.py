import os
import subprocess
import sys
import json
import requests
import time

# Configuration
OPENCLAW_URL = "http://127.0.0.1:1234/v1/chat/completions"
PIPER_EXE = os.path.expanduser("~/.local/bin/piper")
VOICE_MODEL = os.path.expanduser("~/jarvis-m1-ops/voice_assets/fr_FR-denise-medium.onnx")
TEMP_WAV = "/tmp/jarvis_speech.wav"

def speak(text):
    """Génère et joue la réponse vocale via Piper."""
    if not text: return
    print(f"🔊 JARVIS: {text}")
    try:
        # Génération du fichier WAV
        cmd = f"echo '{text}' | {PIPER_EXE} --model {VOICE_MODEL} --output_file {TEMP_WAV}"
        subprocess.run(cmd, shell=True, check=True, capture_output=True)
        # Lecture du fichier WAV
        subprocess.run(f"aplay {TEMP_WAV}", shell=True, check=True, capture_output=True)
    except Exception as e:
        print(f"❌ Erreur TTS: {e}")

def type_text(text):
    """Simule la frappe au clavier via xdotool."""
    if not text: return
    print(f"⌨️ Dictée: {text}")
    try:
        # On attend un peu pour que l'utilisateur puisse focus une fenêtre
        subprocess.run(f"xdotool type --delay 50 '{text}'", shell=True)
    except Exception as e:
        print(f"❌ Erreur xdotool: {e}")

def ask_openclaw(prompt):
    """Envoie une requête à OpenClaw et retourne la réponse."""
    payload = {
        "model": "",
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        resp = requests.post(OPENCLAW_URL, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Erreur de communication avec OpenClaw: {e}"

def call_mcp_tool(name, arguments={}):
    """Appelle un outil MCP directement."""
    payload = {
        "jsonrpc": "2.0",
        "id": int(time.time()),
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments}
    }
    try:
        resp = requests.post("http://127.0.0.1:8080/mcp", json=payload, headers={"Authorization": "Bearer 1202"}, timeout=30)
        return resp.json().get("result", "Erreur outil")
    except Exception as e:
        return f"Erreur MCP: {e}"

def process_interaction(text, mode="command"):
    """Gère l'interaction complète."""
    cmd = text.lower()
    if mode == "dictation" or cmd.startswith("écris"):
        # Mode dictée : on écrit simplement ce qui est dit
        content_to_type = text.replace("écris", "", 1).strip()
        type_text(content_to_type)
        return
    
    if "range mon bureau" in cmd or "range le bureau" in cmd:
        speak("Très bien Monsieur, je m'en occupe.")
        result = call_mcp_tool("range_bureau")
        speak(result)
        return

    # Mode commande : on demande à OpenClaw
    response = ask_openclaw(text)
    print(f"🤖 Réponse: {response}")
    speak(response)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_text = " ".join(sys.argv[1:])
        process_interaction(input_text)
    elif not sys.stdin.isatty():
        input_text = sys.stdin.read().strip()
        if input_text:
            process_interaction(input_text)
    else:
        print("Usage: python jarvis_voice_bridge.py [votre texte ici] ou pipez du texte.")
