#!/usr/bin/env python3
"""windows_integration_agent.py

Batch 28: Agent d'integration Windows pour JARVIS.
Ameliore l'integration native Windows :
  - Notifications toast via PowerShell
  - Startup task dans Task Scheduler
  - Monitoring services Windows
  - Integration clipboard

Usage :
    windows_integration_agent.py --check     # verifie l'integration actuelle
    windows_integration_agent.py --setup     # configure les integrations
    windows_integration_agent.py --loop      # monitoring continu
"""

import argparse
import json
import os
import subprocess
import sys
import time


def send_toast(title, message, app_id="JARVIS"):
    """Envoie une notification toast Windows via PowerShell."""
    ps_script = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
$template = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>{title}</text>
      <text>{message}</text>
    </binding>
  </visual>
</toast>
"@
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("{app_id}").Show($toast)
'''
    try:
        result = subprocess.run(
            ["bash", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  Toast erreur: {e}")
        return False


def check_task_scheduler():
    """Verifie si JARVIS est dans le Task Scheduler Windows."""
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", "JARVIS_Startup", "/FO", "CSV"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and "JARVIS" in result.stdout:
            print("  Task Scheduler: JARVIS_Startup PRESENT")
            return True
        print("  Task Scheduler: JARVIS_Startup non configure")
        return False
    except Exception as e:
        print(f"  Task Scheduler: erreur - {e}")
        return False


def check_startup_folder():
    """Verifie les raccourcis dans le dossier Startup."""
    startup = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    jarvis_files = [f for f in os.listdir(startup) if "jarvis" in f.lower()] if os.path.isdir(startup) else []
    if jarvis_files:
        print(f"  Startup folder: {len(jarvis_files)} fichiers JARVIS")
        for f in jarvis_files:
            print(f"    - {f}")
        return True
    print("  Startup folder: aucun fichier JARVIS")
    return False


def check_services():
    """Verifie les services et processus JARVIS."""
    services = {}

    # Node.js processes
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq node.exe", "/FO", "CSV"],
            capture_output=True, text=True, timeout=10,
        )
        node_count = result.stdout.count("node.exe")
        services["node.exe"] = node_count
        print(f"  Node.js: {node_count} processus")
    except Exception:
        pass

    # Python processes
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
            capture_output=True, text=True, timeout=10,
        )
        py_count = result.stdout.count("python.exe")
        services["python.exe"] = py_count
        print(f"  Python: {py_count} processus")
    except Exception:
        pass

    # Ports check
    for name, port in [("Canvas Proxy", 18800), ("WS Backend", 9742), ("Ollama", 11434), ("LM Studio M1", 1234)]:
        try:
            import urllib.request
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
            services[name] = "UP"
            print(f"  {name} (:{port}): UP")
        except Exception:
            try:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                s.connect(("127.0.0.1", port))
                s.close()
                services[name] = "UP"
                print(f"  {name} (:{port}): UP")
            except Exception:
                services[name] = "DOWN"
                print(f"  {name} (:{port}): DOWN")

    return services


def check_gpu():
    """Verifie les GPU disponibles."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            gpus = result.stdout.strip().split("\n")
            print(f"  GPUs: {len(gpus)} detectes")
            for i, gpu in enumerate(gpus):
                parts = [p.strip() for p in gpu.split(",")]
                if len(parts) >= 5:
                    print(f"    GPU{i}: {parts[0]} | {parts[1]}C | {parts[2]}/{parts[3]}MB | {parts[4]}%")
            return len(gpus)
    except Exception:
        print("  GPUs: nvidia-smi non disponible")
    return 0


def run_check():
    """Execute un check complet de l'integration Windows."""
    print(f"\n[{time.strftime('%H:%M:%S')}] Windows Integration Agent")
    print("=" * 50)

    print("\n[Services]")
    services = check_services()

    print("\n[GPU]")
    check_gpu()

    print("\n[Startup]")
    check_task_scheduler()
    check_startup_folder()

    up_count = sum(1 for v in services.values() if v == "UP" or (isinstance(v, int) and v > 0))
    total = len(services)
    print(f"\nResume: {up_count}/{total} services operationnels")
    return services


def main():
    parser = argparse.ArgumentParser(description="Windows Integration Agent")
    parser.add_argument("--check", action="store_true", help="Check integration actuelle")
    parser.add_argument("--setup", action="store_true", help="Configure les integrations")
    parser.add_argument("--loop", action="store_true", help="Monitoring continu (5 min)")
    parser.add_argument("--toast", type=str, help="Envoie une notification toast test")
    args = parser.parse_args()

    if args.toast:
        ok = send_toast("JARVIS", args.toast)
        print("Toast envoye" if ok else "Toast echoue")
    elif args.loop:
        print("Mode monitoring (Ctrl+C pour arreter)")
        while True:
            run_check()
            time.sleep(300)
    else:
        run_check()


if __name__ == "__main__":
    main()
