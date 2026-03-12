import os
import subprocess
import time

def run_cmd(cmd):
    """Exécute une commande système et retourne le résultat."""
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except Exception as e:
        return f"Erreur exécution: {e}"

def open_app(app_name):
    """Lance une application via xdg-open ou gtk-launch."""
    if "terminal" in app_name.lower():
        subprocess.Popen(["gnome-terminal"])
    elif "firefox" in app_name.lower() or "navigateur" in app_name.lower():
        subprocess.Popen(["firefox"])
    else:
        subprocess.Popen(["xdg-open", f"$(which {app_name})"], shell=True)
    return f"Lancement de {app_name}."

def volume_control(action):
    """Gère le volume via amixer."""
    if action == "up":
        run_cmd("amixer set Master 10%+")
    elif action == "down":
        run_cmd("amixer set Master 10%-")
    elif action == "mute":
        run_cmd("amixer set Master toggle")
    return f"Volume {action}."

def mouse_click(x=None, y=None):
    """Effectue un clic de souris."""
    if x and y:
        run_cmd(f"xdotool mousemove {x} {y} click 1")
    else:
        run_cmd("xdotool click 1")
    return "Clic effectué."

def type_text(text):
    """Simule la saisie de texte."""
    run_cmd(f"xdotool type --delay 50 '{text}'")
    return f"Saisie de '{text}' terminée."

def press_key(key):
    """Simule l'appui d'une touche (ex: Return, space, Alt+Tab)."""
    run_cmd(f"xdotool key {key}")
    return f"Touche {key} pressée."

def get_window_list():
    """Liste les fenêtres ouvertes."""
    return run_cmd("wmctrl -l")

def focus_window(name):
    """Donne le focus à une fenêtre par son nom."""
    run_cmd(f"wmctrl -a '{name}'")
    return f"Focus sur {name}."

def execute_voice_action(command_text):
    """Interprète une commande naturelle en action Linux."""
    cmd = command_text.lower()
    
    if "ouvre" in cmd or "lancer" in cmd:
        app = cmd.split(" ")[-1]
        return open_app(app)
    elif "volume" in cmd:
        if "monte" in cmd or "plus" in cmd: return volume_control("up")
        if "baisse" in cmd or "moins" in cmd: return volume_control("down")
        if "coupe" in cmd: return volume_control("mute")
    elif "clique" in cmd:
        return mouse_click()
    elif "tape" in cmd:
        text = command_text.split("tape")[-1].strip()
        return type_text(text)
    elif "entre" in cmd or "entrée" in cmd:
        return press_key("Return")
    elif "fenêtre" in cmd:
        return get_window_list()
    
    return "Action non reconnue."
