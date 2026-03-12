import os, subprocess, sys, json, requests, time

OPENCLAW_URL = "http://127.0.0.1:1234/v1/chat/completions"
PIPER_EXE = os.path.expanduser("~/.local/bin/piper")
VOICE_MODEL = os.path.expanduser("~/jarvis-m1-ops/voice_assets/fr_FR-denise-medium.onnx")

def speak(text):
    if not text: return
    print(f"🔊 JARVIS: {text}")
    try:
        cmd = f"echo '{text}' | {PIPER_EXE} --model {VOICE_MODEL} --output-raw | aplay -r 22050 -f S16_LE -t raw"
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e: print(f"❌ TTS Error: {e}")

def type_text(text):
    if not text: return
    print(f"⌨️ Dictée: {text}")
    try: subprocess.run(f"xdotool type --delay 20 '{text}'", shell=True)
    except Exception as e: print(f"❌ xdotool Error: {e}")

def ask_ai(prompt):
    try:
        model_resp = requests.get("http://127.0.0.1:1234/v1/models", timeout=2)
        model_id = model_resp.json()["data"][0]["id"]
    except: model_id = "default"
    payload = {"model": model_id, "messages": [{"role": "user", "content": prompt}], "max_tokens": 512, "temperature": 0.3}
    try:
        resp = requests.post(OPENCLAW_URL, json=payload, timeout=60)
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e: return f"Erreur IA: {e}"

def call_mcp_tool(name, arguments={}):
    payload = {"jsonrpc": "2.0", "id": int(time.time()), "method": "tools/call", "params": {"name": name, "arguments": arguments}}
    try:
        resp = requests.post("http://127.0.0.1:8080/mcp", json=payload, headers={"Authorization": "Bearer 1202"}, timeout=30)
        return resp.json().get("result", "Erreur outil")
    except Exception as e: return f"Erreur MCP: {e}"

def run_pipeline(pid):
    if pid == "range_bureau_auto": return call_mcp_tool("range_bureau")
    elif pid == "ferme_fenetre": subprocess.run("xdotool getwindowfocus windowclose", shell=True); return "Fenêtre fermée."
    elif pid == "capture_ecran": subprocess.run(f"gnome-screenshot -f ~/Bureau/Cap_$(date +%Y%m%d_%H%M%S).png", shell=True); return "Capture d'écran faite."
    elif pid == "mode_nuit": subprocess.run("gsettings set org.gnome.settings-daemon.plugins.color night-light-enabled true", shell=True); return "Mode nuit activé."
    elif pid == "mode_jour": subprocess.run("gsettings set org.gnome.settings-daemon.plugins.color night-light-enabled false", shell=True); return "Mode nuit désactivé."
    elif pid == "monte_volume": subprocess.run("amixer set Master 10%+", shell=True); return "Volume augmenté."
    elif pid == "baisse_volume": subprocess.run("amixer set Master 10%-", shell=True); return "Volume diminué."
    elif pid == "coupe_son": subprocess.run("amixer set Master toggle", shell=True); return "Son basculé."
    return "Pipeline inconnu."

def process_interaction(text):
    cmd = text.lower()
    mappings = {
        "range mon bureau": "range_bureau_auto", "ferme la fenêtre": "ferme_fenetre",
        "capture l'écran": "capture_ecran", "mode nuit": "mode_nuit", "mode jour": "mode_jour",
        "monte le volume": "monte_volume", "baisse le volume": "baisse_volume", "coupe le son": "coupe_son"
    }
    if cmd.startswith("écris"):
        type_text(text.replace("écris", "", 1).strip()); return
    for key, pipe_id in mappings.items():
        if key in cmd:
            speak("Exécution."); res = run_pipeline(pipe_id); speak(res); return
    res = ask_ai(text); print(f"🤖 IA: {res}"); speak(res)

if __name__ == "__main__":
    if len(sys.argv) > 1: process_interaction(" ".join(sys.argv[1:]))
    elif not sys.stdin.isatty(): process_interaction(sys.stdin.read().strip())
