"""JARVIS Linux System Integration — Complete Linux automation toolkit.
Adapted from windows.py for Ubuntu 22.04 LTS.
"""
from __future__ import annotations
import json
import subprocess
import os
from typing import Any

__all__ = [
    "check_accessibility",
    "check_service",
    "clipboard_get",
    "clipboard_set",
    "close_application",
    "get_gpu_info",
    "get_ip_address",
    "get_network_info",
    "get_system_info",
    "kill_process",
    "list_processes",
    "list_services",
    "notify_linux",
    "open_application",
    "open_url",
    "run_bash",
]

def run_bash(command: str) -> str:
    """Exécute une commande Bash et retourne stdout+stderr."""
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return (r.stdout + "\n" + r.stderr).strip()
    except Exception as e:
        return f"Erreur Bash: {e}"

def notify_linux(title: str, message: str):
    """Envoie une notification desktop Linux."""
    try:
        subprocess.run(["notify-send", title, message], check=False)
    except: pass

def get_ip_address() -> str:
    """Récupère l'adresse IP locale."""
    try:
        r = subprocess.run(["hostname", "-I"], capture_output=True, text=True)
        return r.stdout.split()[0] if r.stdout.strip() else "127.0.0.1"
    except: return "127.0.0.1"

def list_processes() -> list[dict[str, Any]]:
    """Liste les processus actifs."""
    try:
        r = subprocess.run(["ps", "-aux", "--sort=-%mem"], capture_output=True, text=True)
        lines = r.stdout.strip().split('\n')[1:21] # Top 20
        processes = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 11:
                processes.append({"pid": parts[1], "cpu": parts[2], "mem": parts[3], "name": parts[10]})
        return processes
    except: return []

def check_service(name: str) -> str:
    """Vérifie le statut d'un service systemd."""
    try:
        r = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True)
        return r.stdout.strip()
    except: return "unknown"

def kill_process(name_or_pid: str):
    """Tue un processus."""
    try:
        cmd = ["kill", "-9", name_or_pid] if name_or_pid.isdigit() else ["pkill", "-f", name_or_pid]
        subprocess.run(cmd, check=False)
    except: pass

def open_url(url: str):
    """Ouvre une URL dans le navigateur par défaut."""
    try:
        subprocess.run(["xdg-open", url], check=False)
    except: pass

def get_gpu_info() -> str:
    """Récupère les infos NVIDIA GPU."""
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu", "--format=csv,noheader"], capture_output=True, text=True)
        return r.stdout.strip()
    except: return "NVIDIA N/A"

def get_system_info() -> dict[str, Any]:
    """Infos système globales."""
    import psutil
    return {
        "os": "Linux (Ubuntu)",
        "cpu_count": psutil.cpu_count(),
        "cpu_usage": psutil.cpu_percent(),
        "ram": f"{psutil.virtual_memory().percent}%",
        "ip": get_ip_address()
    }

# Stub functions for compatibility
def check_accessibility(): return True
def clipboard_get(): return ""
def clipboard_set(text): pass
def close_application(name): kill_process(name)
def list_services(): return []
def open_application(name): subprocess.Popen([name], shell=True)
def get_network_info(): return {}
