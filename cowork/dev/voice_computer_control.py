#!/usr/bin/env python3
"""voice_computer_control.py — Pilote Windows et le navigateur entierement a la voix.

Controle complet du PC sans clavier ni souris:
- Navigateur (via browser_pilot.py CDP Chrome DevTools Protocol, port 9222)
- Windows Desktop (via PowerShell subprocess)
- Systeme (CPU, RAM, GPU, disques, processus)
- Multimedia (lecture, volume, pistes)

Usage:
    python dev/voice_computer_control.py --cmd "ouvre google"
    python dev/voice_computer_control.py --cmd "cherche sur google meteo paris"
    python dev/voice_computer_control.py --cmd "monte le volume"
    python dev/voice_computer_control.py --cmd "ouvre le bloc-notes"
    python dev/voice_computer_control.py --cmd "usage processeur"
    python dev/voice_computer_control.py --method browser_open --params '{"url":"https://google.com"}'
    python dev/voice_computer_control.py --list
    python dev/voice_computer_control.py --list-methods
"""
import argparse
import difflib
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BROWSER_PILOT = Path(__file__).parent / "browser_pilot.py"
PYTHON = sys.executable
CDP_PORT = 9222
POWERSHELL = "bash"
SCREENSHOT_DIR = Path(os.path.expanduser("~")) / "Pictures" / "Screenshots"


# ===========================================================================
# VoiceComputerControl — Classe principale
# ===========================================================================
class VoiceComputerControl:
    """Controle complet du PC a la voix: navigateur, Windows, systeme, multimedia."""

    def __init__(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # Helpers internes
    # -----------------------------------------------------------------------
    def _run_ps(self, script: str, timeout: int = 15) -> str:
        """Execute un script PowerShell et retourne stdout."""
        try:
            r = subprocess.run(
                [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, text=True, timeout=timeout
            )
            return r.stdout.strip() if r.returncode == 0 else r.stderr.strip()
        except subprocess.TimeoutExpired:
            return "ERREUR: Timeout PowerShell"
        except Exception as e:
            return f"ERREUR: {e}"

    def _run_cmd(self, cmd: list, timeout: int = 15) -> str:
        """Execute une commande systeme et retourne stdout."""
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return r.stdout.strip() if r.returncode == 0 else r.stderr.strip()
        except subprocess.TimeoutExpired:
            return "ERREUR: Timeout commande"
        except Exception as e:
            return f"ERREUR: {e}"

    def _browser_cmd(self, *args, timeout: int = 20) -> str:
        """Appelle browser_pilot.py avec les arguments donnes."""
        if not BROWSER_PILOT.exists():
            return "ERREUR: browser_pilot.py introuvable"
        cmd = [PYTHON, str(BROWSER_PILOT)] + list(args)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            output = r.stdout.strip()
            if r.returncode != 0 and r.stderr.strip():
                return r.stderr.strip()
            # Tenter de parser le JSON pour un retour propre
            try:
                data = json.loads(output)
                if isinstance(data, dict):
                    if "error" in data:
                        return f"ERREUR navigateur: {data['error']}"
                    if "result" in data:
                        return str(data["result"])
                    if "text" in data:
                        return str(data["text"])[:2000]
                    if "action" in data:
                        return f"{data['action']}: OK"
                return output
            except (json.JSONDecodeError, ValueError):
                return output if output else "OK"
        except subprocess.TimeoutExpired:
            return "ERREUR: Timeout navigateur"
        except Exception as e:
            return f"ERREUR: {e}"

    def _ensure_cdp(self) -> str | None:
        """Verifie que CDP est actif, sinon lance le navigateur."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", CDP_PORT))
            sock.close()
            if result != 0:
                self._browser_cmd("--start")
                time.sleep(1)
                return "Navigateur lance"
            return None
        except Exception:
            self._browser_cmd("--start")
            return "Navigateur lance"

    def _sendkeys(self, keys: str) -> str:
        """Envoie des touches via PowerShell SendKeys."""
        script = f"""
Add-Type -AssemblyName System.Windows.Forms
Start-Sleep -Milliseconds 200
[System.Windows.Forms.SendKeys]::SendWait('{keys}')
"""
        return self._run_ps(script)

    # ===================================================================
    # NAVIGATEUR — via browser_pilot.py CDP
    # ===================================================================
    def browser_open(self, url: str) -> str:
        """Ouvre une URL dans le navigateur."""
        self._ensure_cdp()
        if not url.startswith(("http://", "https://", "file://")):
            url = "https://" + url
        return self._browser_cmd("--navigate", url)

    def browser_search(self, query: str) -> str:
        """Recherche sur Google."""
        self._ensure_cdp()
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        return self._browser_cmd("--navigate", url)

    def browser_back(self) -> str:
        """Page precedente."""
        return self._browser_cmd("--back")

    def browser_forward(self) -> str:
        """Page suivante."""
        return self._browser_cmd("--forward")

    def browser_scroll(self, direction: str = "down", amount: int = 500) -> str:
        """Scroller la page (up/down/top/bottom)."""
        d = direction.lower()
        if d in ("up", "down", "top", "bottom"):
            return self._browser_cmd("--scroll", d)
        return f"Direction inconnue: {direction}. Utilise up/down/top/bottom."

    def browser_click(self, text_or_selector: str) -> str:
        """Cliquer sur un element (texte visible ou selecteur CSS)."""
        # Heuristique: si contient . # [ = -> selecteur CSS, sinon texte
        if any(c in text_or_selector for c in ".#[]>+~="):
            return self._browser_cmd("--click", text_or_selector)
        return self._browser_cmd("--click-text", text_or_selector)

    def browser_type(self, text: str) -> str:
        """Taper du texte dans le champ actif."""
        return self._browser_cmd("--type", text)

    def browser_press(self, key: str) -> str:
        """Appuyer sur une touche (Enter, Tab, Escape, etc.)."""
        return self._browser_cmd("--press", key)

    def browser_new_tab(self, url: str = "about:blank") -> str:
        """Ouvrir un nouvel onglet."""
        self._ensure_cdp()
        return self._browser_cmd("--new-tab", url)

    def browser_close_tab(self) -> str:
        """Fermer l'onglet actif."""
        return self._browser_cmd("--close-tab")

    def browser_tabs(self) -> str:
        """Lister les onglets ouverts."""
        output = self._browser_cmd("--tabs")
        try:
            tabs = json.loads(output)
            if isinstance(tabs, list):
                lines = [f"{i+1}. {t.get('title', 'Sans titre')} — {t.get('url', '')}"
                         for i, t in enumerate(tabs)]
                return f"{len(tabs)} onglet(s):\n" + "\n".join(lines)
        except (json.JSONDecodeError, ValueError):
            pass
        return output

    def browser_read(self) -> str:
        """Lire le contenu textuel de la page."""
        return self._browser_cmd("--text")

    def browser_screenshot(self, path: str = None) -> str:
        """Capture d'ecran du navigateur."""
        if not path:
            path = str(SCREENSHOT_DIR / f"browser_{int(time.time())}.png")
        return self._browser_cmd("--screenshot", path)

    def browser_zoom(self, in_out: str = "in") -> str:
        """Zoom avant/arriere dans le navigateur."""
        if in_out.lower() in ("in", "plus", "+"):
            js = "document.body.style.zoom = (parseFloat(document.body.style.zoom || 1) + 0.1).toString(); 'zoom: ' + document.body.style.zoom"
        else:
            js = "document.body.style.zoom = Math.max(0.1, parseFloat(document.body.style.zoom || 1) - 0.1).toString(); 'zoom: ' + document.body.style.zoom"
        return self._browser_cmd("--eval", js)

    def browser_find(self, text: str) -> str:
        """Chercher du texte dans la page (Ctrl+F)."""
        # Utiliser window.find() en JS
        js = f"window.find('{text.replace(chr(39), chr(92)+chr(39))}') ? 'Trouve: {text}' : 'Non trouve: {text}'"
        return self._browser_cmd("--eval", js)

    def browser_bookmark(self) -> str:
        """Ajouter la page aux favoris (Ctrl+D)."""
        self._sendkeys("^d")
        return "Boite de dialogue favoris ouverte"

    def browser_refresh(self) -> str:
        """Rafraichir la page."""
        return self._browser_cmd("--eval", "location.reload(); 'page rafraichie'")

    def browser_fullscreen(self) -> str:
        """Basculer en plein ecran (F11)."""
        self._sendkeys("{F11}")
        return "Plein ecran bascule"

    # ===================================================================
    # WINDOWS DESKTOP — via PowerShell
    # ===================================================================
    def win_open_app(self, name: str) -> str:
        """Ouvrir une application Windows."""
        app_map = {
            "notepad": "notepad",
            "bloc-notes": "notepad",
            "blocnotes": "notepad",
            "calc": "calc",
            "calculatrice": "calc",
            "calculator": "calc",
            "explorer": "explorer",
            "explorateur": "explorer",
            "terminal": "wt",
            "wt": "wt",
            "cmd": "cmd",
            "bash": "bash",
            "paint": "mspaint",
            "snip": "SnippingTool",
            "capture": "SnippingTool",
            "word": "winword",
            "excel": "excel",
            "chrome": "chrome",
            "edge": "msedge",
            "firefox": "firefox",
            "spotify": "spotify",
            "discord": "discord",
            "code": "code",
            "vscode": "code",
            "task manager": "taskmgr",
            "gestionnaire": "taskmgr",
            "regedit": "regedit",
            "services": "services.msc",
            "control": "control",
            "panneau": "control",
        }
        # Applications avec URI ms-*
        uri_map = {
            "ms-settings:": "ms-settings:",
            "parametres": "ms-settings:",
            "settings": "ms-settings:",
            "ms-settings:bluetooth": "ms-settings:bluetooth",
            "ms-settings:network-wifi": "ms-settings:network-wifi",
            "ms-settings:display": "ms-settings:display",
            "store": "ms-windows-store:",
            "courrier": "outlookmail:",
            "mail": "outlookmail:",
            "calendrier": "outlookcal:",
            "photos": "ms-photos:",
            "camera": "microsoft.windows.camera:",
            "horloge": "ms-clock:",
            "alarme": "ms-clock:",
            "meteo": "bingweather:",
            "cartes": "bingmaps:",
            "musique": "mswindowsmusic:",
        }
        key = name.lower().strip()
        if key in uri_map:
            return self._run_ps(f"Start-Process '{uri_map[key]}'")  or f"{name} ouvert"
        exe = app_map.get(key, key)
        return self._run_ps(f"Start-Process '{exe}'") or f"{name} ouvert"

    def win_close_app(self) -> str:
        """Fermer la fenetre active (Alt+F4)."""
        self._sendkeys("%{F4}")
        return "Fenetre fermee"

    def win_minimize(self) -> str:
        """Minimiser la fenetre active."""
        script = """
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait("% n")
"""
        self._run_ps(script)
        return "Fenetre minimisee"

    def win_maximize(self) -> str:
        """Maximiser la fenetre active."""
        script = """
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait("% x")
"""
        self._run_ps(script)
        return "Fenetre maximisee"

    def win_switch_app(self) -> str:
        """Basculer entre les fenetres (Alt+Tab)."""
        self._sendkeys("%{TAB}")
        return "Fenetre changee"

    def win_screenshot(self, path: str = None) -> str:
        """Capture d'ecran Windows via PowerShell."""
        if not path:
            path = str(SCREENSHOT_DIR / f"screen_{int(time.time())}.png")
        script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$screen = [System.Windows.Forms.Screen]::PrimaryScreen
$bitmap = New-Object System.Drawing.Bitmap($screen.Bounds.Width, $screen.Bounds.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Bounds.Location, [System.Drawing.Point]::Empty, $screen.Bounds.Size)
$bitmap.Save('{path}')
$graphics.Dispose()
$bitmap.Dispose()
Write-Output '{path}'
"""
        result = self._run_ps(script, timeout=10)
        if os.path.exists(path):
            return f"Capture sauvegardee: {path}"
        return result or "Erreur lors de la capture"

    def win_lock(self) -> str:
        """Verrouiller l'ecran."""
        self._run_cmd(["rundll32.exe", "user32.dll,LockWorkStation"])
        return "Ecran verrouille"

    def win_volume(self, action: str = "up") -> str:
        """Controle du volume (up/down/mute)."""
        script_map = {
            "up": """
$wsh = New-Object -ComObject WScript.Shell
$wsh.SendKeys([char]0xAF)
$wsh.SendKeys([char]0xAF)
""",
            "down": """
$wsh = New-Object -ComObject WScript.Shell
$wsh.SendKeys([char]0xAE)
$wsh.SendKeys([char]0xAE)
""",
            "mute": """
$wsh = New-Object -ComObject WScript.Shell
$wsh.SendKeys([char]0xAD)
""",
        }
        # Approche plus fiable via nircmd ou PowerShell Audio
        ps_map = {
            "up": """
Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
public class Audio {
    [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, int dwExtraInfo);
    public const byte VK_VOLUME_UP = 0xAF;
    public static void VolumeUp() { keybd_event(VK_VOLUME_UP, 0, 0, 0); keybd_event(VK_VOLUME_UP, 0, 2, 0); }
}
'@
[Audio]::VolumeUp()
[Audio]::VolumeUp()
[Audio]::VolumeUp()
""",
            "down": """
Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
public class Audio {
    [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, int dwExtraInfo);
    public const byte VK_VOLUME_DOWN = 0xAE;
    public static void VolumeDown() { keybd_event(VK_VOLUME_DOWN, 0, 0, 0); keybd_event(VK_VOLUME_DOWN, 0, 2, 0); }
}
'@
[Audio]::VolumeDown()
[Audio]::VolumeDown()
[Audio]::VolumeDown()
""",
            "mute": """
Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
public class Audio {
    [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, int dwExtraInfo);
    public const byte VK_VOLUME_MUTE = 0xAD;
    public static void Mute() { keybd_event(VK_VOLUME_MUTE, 0, 0, 0); keybd_event(VK_VOLUME_MUTE, 0, 2, 0); }
}
'@
[Audio]::Mute()
""",
        }
        key = action.lower()
        if key not in ps_map:
            return f"Action inconnue: {action}. Utilise up/down/mute."
        self._run_ps(ps_map[key])
        labels = {"up": "Volume augmente", "down": "Volume baisse", "mute": "Son coupe/reactive"}
        return labels.get(key, "Volume modifie")

    def win_brightness(self, action: str = "up") -> str:
        """Luminosite ecran (up/down)."""
        if action.lower() == "up":
            script = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, [Math]::Min(100, (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness + 10))"
        else:
            script = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, [Math]::Max(0, (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness - 10))"
        result = self._run_ps(script)
        return result or f"Luminosite {'augmentee' if action.lower() == 'up' else 'baissee'}"

    def win_wifi(self, on_off: str = "on") -> str:
        """Activer/desactiver le WiFi."""
        if on_off.lower() in ("on", "activer", "oui"):
            script = "netsh interface set interface name='Wi-Fi' admin=enabled"
        else:
            script = "netsh interface set interface name='Wi-Fi' admin=disabled"
        result = self._run_cmd(["netsh", "interface", "set", "interface",
                                 "name=Wi-Fi",
                                 f"admin={'enabled' if on_off.lower() in ('on', 'activer', 'oui') else 'disabled'}"])
        return result or f"WiFi {'active' if on_off.lower() in ('on', 'activer', 'oui') else 'desactive'}"

    def win_bluetooth(self, on_off: str = "on") -> str:
        """Activer/desactiver le Bluetooth."""
        # Ouvrir les parametres Bluetooth
        self._run_ps("Start-Process 'ms-settings:bluetooth'")
        return f"Parametres Bluetooth ouverts — {'activez' if on_off.lower() in ('on', 'activer', 'oui') else 'desactivez'} manuellement"

    def win_shutdown(self) -> str:
        """Eteindre l'ordinateur."""
        self._run_cmd(["shutdown", "/s", "/t", "5"])
        return "Extinction dans 5 secondes"

    def win_restart(self) -> str:
        """Redemarrer l'ordinateur."""
        self._run_cmd(["shutdown", "/r", "/t", "5"])
        return "Redemarrage dans 5 secondes"

    def win_sleep(self) -> str:
        """Mise en veille."""
        self._run_ps("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        return "Mise en veille"

    def win_file_explorer(self, path: str = None) -> str:
        """Ouvrir l'explorateur de fichiers."""
        if path:
            self._run_cmd(["explorer", path])
            return f"Explorateur ouvert: {path}"
        self._run_cmd(["explorer"])
        return "Explorateur ouvert"

    def win_search(self, query: str = "") -> str:
        """Recherche Windows."""
        if query:
            # Ouvre la recherche Windows et tape la requete
            self._sendkeys("^({ESC})")
            time.sleep(0.5)
            script = f"""
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait('{query}')
"""
            self._run_ps(script)
            return f"Recherche Windows: {query}"
        self._sendkeys("^({ESC})")
        return "Recherche Windows ouverte"

    def win_clipboard_copy(self) -> str:
        """Copier (Ctrl+C)."""
        self._sendkeys("^c")
        return "Copie dans le presse-papiers"

    def win_clipboard_paste(self) -> str:
        """Coller (Ctrl+V)."""
        self._sendkeys("^v")
        return "Colle depuis le presse-papiers"

    def win_taskbar_pin(self, app: str) -> str:
        """Epingler une application a la barre des taches."""
        return "Fonction disponible via le menu contextuel — clic droit sur l'application"

    def win_notification_clear(self) -> str:
        """Effacer les notifications."""
        # Ouvrir le centre de notifications et tout effacer
        self._sendkeys("#{a}")
        time.sleep(0.5)
        return "Centre de notifications ouvert"

    def win_snap_left(self) -> str:
        """Snap fenetre a gauche."""
        self._sendkeys("#{LEFT}")
        return "Fenetre ancree a gauche"

    def win_snap_right(self) -> str:
        """Snap fenetre a droite."""
        self._sendkeys("#{RIGHT}")
        return "Fenetre ancree a droite"

    def win_desktop_show(self) -> str:
        """Afficher le bureau (Win+D)."""
        self._sendkeys("#{d}")
        return "Bureau affiche"

    def win_task_manager(self) -> str:
        """Ouvrir le gestionnaire de taches."""
        self._run_cmd(["taskmgr"])
        return "Gestionnaire de taches ouvert"

    # ===================================================================
    # SYSTEME — Monitoring
    # ===================================================================
    def sys_cpu_usage(self) -> str:
        """Usage CPU."""
        script = "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"
        result = self._run_ps(script)
        try:
            return f"Usage CPU: {float(result):.0f}%"
        except (ValueError, TypeError):
            return f"Usage CPU: {result}"

    def sys_ram_usage(self) -> str:
        """Usage RAM."""
        script = """
$os = Get-CimInstance Win32_OperatingSystem
$total = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$free = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
$used = [math]::Round($total - $free, 1)
$pct = [math]::Round(($used / $total) * 100, 0)
Write-Output "$used Go / $total Go ($pct%)"
"""
        result = self._run_ps(script)
        return f"RAM: {result}"

    def sys_disk_space(self) -> str:
        """Espace disque."""
        script = """
Get-PSDrive -PSProvider FileSystem | Where-Object {$_.Used -gt 0} | ForEach-Object {
    $total = [math]::Round(($_.Used + $_.Free) / 1GB, 0)
    $free = [math]::Round($_.Free / 1GB, 0)
    $pct = [math]::Round($_.Used / ($_.Used + $_.Free) * 100, 0)
    Write-Output "$($_.Name): $free Go libres / $total Go ($pct% utilise)"
}
"""
        result = self._run_ps(script)
        return f"Disques:\n{result}"

    def sys_gpu_temp(self) -> str:
        """Temperature GPU (nvidia-smi)."""
        result = self._run_cmd(["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                                 "--format=csv,noheader,nounits"])
        if "ERREUR" in result or not result:
            return "nvidia-smi non disponible ou pas de GPU NVIDIA"
        lines = result.strip().split("\n")
        output = []
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                output.append(f"{parts[0]}: {parts[1]}C, GPU {parts[2]}%, VRAM {parts[3]}/{parts[4]} Mo")
            else:
                output.append(line.strip())
        return "GPU:\n" + "\n".join(output)

    def sys_processes(self, n: int = 10) -> str:
        """Top N processus par CPU."""
        script = f"""
Get-Process | Sort-Object CPU -Descending | Select-Object -First {n} | ForEach-Object {{
    $cpu = if ($_.CPU) {{ [math]::Round($_.CPU, 1) }} else {{ 0 }}
    $mem = [math]::Round($_.WorkingSet64 / 1MB, 0)
    Write-Output "$($_.ProcessName): CPU=$($cpu)s, RAM=$($mem)Mo"
}}
"""
        result = self._run_ps(script)
        return f"Top {n} processus:\n{result}"

    def sys_kill_process(self, name: str) -> str:
        """Tuer un processus par nom."""
        script = f"Stop-Process -Name '{name}' -Force -ErrorAction SilentlyContinue; Write-Output 'OK'"
        result = self._run_ps(script)
        return f"Processus {name} arrete" if "OK" in result else f"Impossible de tuer {name}: {result}"

    def sys_ip_address(self) -> str:
        """Adresse IP locale et publique."""
        # IP locale
        local_script = """
(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike '*Loopback*' -and $_.IPAddress -ne '127.0.0.1'} | Select-Object -First 3 | ForEach-Object {"$($_.InterfaceAlias): $($_.IPAddress)"}) -join '; '
"""
        local_ip = self._run_ps(local_script)
        return f"IP locale: {local_ip}"

    def sys_uptime(self) -> str:
        """Duree de fonctionnement du systeme."""
        script = """
$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$up = (Get-Date) - $boot
Write-Output "$($up.Days)j $($up.Hours)h $($up.Minutes)m"
"""
        result = self._run_ps(script)
        return f"Uptime: {result}"

    def sys_battery(self) -> str:
        """Niveau de batterie."""
        script = """
$bat = Get-CimInstance Win32_Battery
if ($bat) {
    Write-Output "$($bat.EstimatedChargeRemaining)% — $($bat.BatteryStatus)"
} else {
    Write-Output "Pas de batterie (PC fixe)"
}
"""
        result = self._run_ps(script)
        return f"Batterie: {result}"

    # ===================================================================
    # MULTIMEDIA — Controle media
    # ===================================================================
    def _media_key(self, vk_code: int) -> str:
        """Envoie une touche media via keybd_event."""
        script = f"""
Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
public class MediaKey {{
    [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, int dwExtraInfo);
    public static void Press(byte vk) {{ keybd_event(vk, 0, 0, 0); keybd_event(vk, 0, 2, 0); }}
}}
'@
[MediaKey]::Press({vk_code})
"""
        return self._run_ps(script)

    def media_play_pause(self) -> str:
        """Lecture/Pause."""
        self._media_key(0xB3)  # VK_MEDIA_PLAY_PAUSE
        return "Lecture/Pause"

    def media_next(self) -> str:
        """Piste suivante."""
        self._media_key(0xB0)  # VK_MEDIA_NEXT_TRACK
        return "Piste suivante"

    def media_previous(self) -> str:
        """Piste precedente."""
        self._media_key(0xB1)  # VK_MEDIA_PREV_TRACK
        return "Piste precedente"

    def media_volume(self, level: int = 50) -> str:
        """Regler le volume a un niveau precis (0-100)."""
        level = max(0, min(100, level))
        # Utiliser PowerShell pour set le volume via AudioDevice si disponible
        # Fallback: set via nircmd-like approach
        script = f"""
Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {{
    int _0(); int _1(); int _2(); int _3();
    int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);
    int _5();
    int GetMasterVolumeLevelScalar(out float pfLevel);
}}
[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice {{ int Activate(ref System.Guid iid, int dwClsCtx, System.IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface); }}
[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator {{ int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppDevice); }}
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class MMDeviceEnumerator {{}}
public class Vol {{
    public static void Set(float level) {{
        var enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumerator());
        IMMDevice dev; enumerator.GetDefaultAudioEndpoint(0, 1, out dev);
        var iid = typeof(IAudioEndpointVolume).GUID;
        object o; dev.Activate(ref iid, 1, System.IntPtr.Zero, out o);
        var vol = (IAudioEndpointVolume)o;
        vol.SetMasterVolumeLevelScalar(level, System.Guid.Empty);
    }}
}}
'@
[Vol]::Set({level / 100.0})
"""
        result = self._run_ps(script, timeout=10)
        if "ERREUR" in result:
            return f"Volume: methode directe non disponible ({result})"
        return f"Volume regle a {level}%"


# ===========================================================================
# VOICE_COMMANDS — Mapping phrases vocales → methodes
# ===========================================================================
VOICE_COMMANDS = {
    # ===================================================================
    # NAVIGATEUR — Sites courants
    # ===================================================================
    "ouvre google": ("browser_open", {"url": "https://google.com"}),
    "va sur google": ("browser_open", {"url": "https://google.com"}),
    "google": ("browser_open", {"url": "https://google.com"}),
    "ouvre youtube": ("browser_open", {"url": "https://youtube.com"}),
    "va sur youtube": ("browser_open", {"url": "https://youtube.com"}),
    "youtube": ("browser_open", {"url": "https://youtube.com"}),
    "ouvre gmail": ("browser_open", {"url": "https://gmail.com"}),
    "va sur gmail": ("browser_open", {"url": "https://gmail.com"}),
    "ouvre twitter": ("browser_open", {"url": "https://x.com"}),
    "ouvre x": ("browser_open", {"url": "https://x.com"}),
    "ouvre facebook": ("browser_open", {"url": "https://facebook.com"}),
    "ouvre reddit": ("browser_open", {"url": "https://reddit.com"}),
    "ouvre github": ("browser_open", {"url": "https://github.com"}),
    "ouvre linkedin": ("browser_open", {"url": "https://linkedin.com"}),
    "ouvre wikipedia": ("browser_open", {"url": "https://fr.wikipedia.org"}),
    "ouvre amazon": ("browser_open", {"url": "https://amazon.fr"}),
    "ouvre netflix": ("browser_open", {"url": "https://netflix.com"}),
    "ouvre twitch": ("browser_open", {"url": "https://twitch.tv"}),
    "ouvre chatgpt": ("browser_open", {"url": "https://chat.openai.com"}),
    "ouvre claude": ("browser_open", {"url": "https://claude.ai"}),
    "ouvre whatsapp": ("browser_open", {"url": "https://web.whatsapp.com"}),
    "ouvre telegram": ("browser_open", {"url": "https://web.telegram.org"}),
    "ouvre instagram": ("browser_open", {"url": "https://instagram.com"}),
    "ouvre tiktok": ("browser_open", {"url": "https://tiktok.com"}),
    "ouvre le site": ("browser_open", {}),  # needs url param
    "va sur le site": ("browser_open", {}),  # needs url param
    "ouvre la page": ("browser_open", {}),  # needs url param
    "navigue vers": ("browser_open", {}),  # needs url param

    # NAVIGATEUR — Recherche
    "cherche sur google": ("browser_search", {}),  # needs query param
    "recherche sur google": ("browser_search", {}),
    "recherche google": ("browser_search", {}),
    "recherche": ("browser_search", {}),
    "cherche": ("browser_search", {}),
    "google cherche": ("browser_search", {}),
    "fais une recherche": ("browser_search", {}),
    "trouve": ("browser_search", {}),
    "cherche sur internet": ("browser_search", {}),
    "recherche sur internet": ("browser_search", {}),
    "recherche web": ("browser_search", {}),

    # NAVIGATEUR — Navigation
    "page precedente": ("browser_back", {}),
    "retour": ("browser_back", {}),
    "reviens en arriere": ("browser_back", {}),
    "en arriere": ("browser_back", {}),
    "va en arriere": ("browser_back", {}),
    "recule": ("browser_back", {}),
    "page suivante": ("browser_forward", {}),
    "avance": ("browser_forward", {}),
    "va en avant": ("browser_forward", {}),
    "page d'apres": ("browser_forward", {}),
    "en avant": ("browser_forward", {}),

    # NAVIGATEUR — Scroll
    "descends": ("browser_scroll", {"direction": "down"}),
    "scroll en bas": ("browser_scroll", {"direction": "down"}),
    "scroll down": ("browser_scroll", {"direction": "down"}),
    "fais defiler en bas": ("browser_scroll", {"direction": "down"}),
    "defiler en bas": ("browser_scroll", {"direction": "down"}),
    "descends la page": ("browser_scroll", {"direction": "down"}),
    "plus bas": ("browser_scroll", {"direction": "down"}),
    "continue": ("browser_scroll", {"direction": "down"}),
    "monte": ("browser_scroll", {"direction": "up"}),
    "scroll en haut": ("browser_scroll", {"direction": "up"}),
    "scroll up": ("browser_scroll", {"direction": "up"}),
    "fais defiler en haut": ("browser_scroll", {"direction": "up"}),
    "defiler en haut": ("browser_scroll", {"direction": "up"}),
    "remonte": ("browser_scroll", {"direction": "up"}),
    "plus haut": ("browser_scroll", {"direction": "up"}),
    "monte la page": ("browser_scroll", {"direction": "up"}),
    "tout en haut": ("browser_scroll", {"direction": "top"}),
    "debut de page": ("browser_scroll", {"direction": "top"}),
    "haut de page": ("browser_scroll", {"direction": "top"}),
    "retour en haut": ("browser_scroll", {"direction": "top"}),
    "tout en bas": ("browser_scroll", {"direction": "bottom"}),
    "fin de page": ("browser_scroll", {"direction": "bottom"}),
    "bas de page": ("browser_scroll", {"direction": "bottom"}),
    "va tout en bas": ("browser_scroll", {"direction": "bottom"}),

    # NAVIGATEUR — Interaction
    "clique": ("browser_click", {}),  # needs text_or_selector
    "clique sur": ("browser_click", {}),
    "appuie sur": ("browser_click", {}),
    "selectionne": ("browser_click", {}),
    "tape": ("browser_type", {}),  # needs text
    "ecris": ("browser_type", {}),
    "saisis": ("browser_type", {}),
    "entre le texte": ("browser_type", {}),
    "remplis": ("browser_type", {}),
    "entree": ("browser_press", {"key": "Enter"}),
    "valide": ("browser_press", {"key": "Enter"}),
    "confirme": ("browser_press", {"key": "Enter"}),
    "ok": ("browser_press", {"key": "Enter"}),
    "tabulation": ("browser_press", {"key": "Tab"}),
    "tab": ("browser_press", {"key": "Tab"}),
    "champ suivant": ("browser_press", {"key": "Tab"}),
    "echap": ("browser_press", {"key": "Escape"}),
    "escape": ("browser_press", {"key": "Escape"}),
    "annule": ("browser_press", {"key": "Escape"}),
    "ferme": ("browser_press", {"key": "Escape"}),
    "efface": ("browser_press", {"key": "Backspace"}),
    "supprime": ("browser_press", {"key": "Delete"}),
    "espace": ("browser_press", {"key": "space"}),

    # NAVIGATEUR — Onglets
    "nouvel onglet": ("browser_new_tab", {}),
    "nouveau tab": ("browser_new_tab", {}),
    "ouvre un onglet": ("browser_new_tab", {}),
    "ouvre un nouvel onglet": ("browser_new_tab", {}),
    "cree un onglet": ("browser_new_tab", {}),
    "ferme l'onglet": ("browser_close_tab", {}),
    "ferme cet onglet": ("browser_close_tab", {}),
    "ferme le tab": ("browser_close_tab", {}),
    "supprime l'onglet": ("browser_close_tab", {}),
    "les onglets": ("browser_tabs", {}),
    "liste les onglets": ("browser_tabs", {}),
    "quels onglets": ("browser_tabs", {}),
    "combien d'onglets": ("browser_tabs", {}),
    "montre les onglets": ("browser_tabs", {}),
    "onglets ouverts": ("browser_tabs", {}),

    # NAVIGATEUR — Lecture & Info
    "lis la page": ("browser_read", {}),
    "lis le contenu": ("browser_read", {}),
    "lis moi la page": ("browser_read", {}),
    "qu'est-ce qu'il y a sur la page": ("browser_read", {}),
    "contenu de la page": ("browser_read", {}),
    "texte de la page": ("browser_read", {}),
    "resume la page": ("browser_read", {}),
    "capture ecran": ("browser_screenshot", {}),
    "screenshot": ("browser_screenshot", {}),
    "capture la page": ("browser_screenshot", {}),
    "fais une capture": ("browser_screenshot", {}),
    "prends une capture": ("browser_screenshot", {}),

    # NAVIGATEUR — Zoom
    "zoom plus": ("browser_zoom", {"in_out": "in"}),
    "zoom avant": ("browser_zoom", {"in_out": "in"}),
    "zoome": ("browser_zoom", {"in_out": "in"}),
    "agrandis": ("browser_zoom", {"in_out": "in"}),
    "plus gros": ("browser_zoom", {"in_out": "in"}),
    "zoom moins": ("browser_zoom", {"in_out": "out"}),
    "zoom arriere": ("browser_zoom", {"in_out": "out"}),
    "dezoome": ("browser_zoom", {"in_out": "out"}),
    "retrecis": ("browser_zoom", {"in_out": "out"}),
    "plus petit": ("browser_zoom", {"in_out": "out"}),

    # NAVIGATEUR — Divers
    "actualise": ("browser_refresh", {}),
    "rafraichis": ("browser_refresh", {}),
    "recharge la page": ("browser_refresh", {}),
    "refresh": ("browser_refresh", {}),
    "f5": ("browser_refresh", {}),
    "recharge": ("browser_refresh", {}),
    "plein ecran": ("browser_fullscreen", {}),
    "mode plein ecran": ("browser_fullscreen", {}),
    "fullscreen": ("browser_fullscreen", {}),
    "ecran complet": ("browser_fullscreen", {}),
    "cherche dans la page": ("browser_find", {}),  # needs text
    "trouve dans la page": ("browser_find", {}),
    "ctrl f": ("browser_find", {}),
    "recherche dans la page": ("browser_find", {}),
    "ajoute aux favoris": ("browser_bookmark", {}),
    "favori": ("browser_bookmark", {}),
    "bookmark": ("browser_bookmark", {}),
    "marque la page": ("browser_bookmark", {}),

    # ===================================================================
    # WINDOWS — Applications
    # ===================================================================
    "ouvre le bloc-notes": ("win_open_app", {"name": "notepad"}),
    "ouvre bloc-notes": ("win_open_app", {"name": "notepad"}),
    "ouvre notepad": ("win_open_app", {"name": "notepad"}),
    "bloc-notes": ("win_open_app", {"name": "notepad"}),
    "ouvre la calculatrice": ("win_open_app", {"name": "calc"}),
    "calculatrice": ("win_open_app", {"name": "calc"}),
    "ouvre la calculette": ("win_open_app", {"name": "calc"}),
    "ouvre l'explorateur": ("win_open_app", {"name": "explorer"}),
    "explorateur de fichiers": ("win_open_app", {"name": "explorer"}),
    "ouvre mes fichiers": ("win_open_app", {"name": "explorer"}),
    "ouvre le terminal": ("win_open_app", {"name": "wt"}),
    "terminal": ("win_open_app", {"name": "wt"}),
    "ouvre un terminal": ("win_open_app", {"name": "wt"}),
    "ouvre bash": ("win_open_app", {"name": "bash"}),
    "ouvre cmd": ("win_open_app", {"name": "cmd"}),
    "invite de commandes": ("win_open_app", {"name": "cmd"}),
    "ouvre les parametres": ("win_open_app", {"name": "ms-settings:"}),
    "parametres": ("win_open_app", {"name": "ms-settings:"}),
    "ouvre les reglages": ("win_open_app", {"name": "ms-settings:"}),
    "reglages": ("win_open_app", {"name": "ms-settings:"}),
    "ouvre paint": ("win_open_app", {"name": "paint"}),
    "ouvre l'outil de capture": ("win_open_app", {"name": "capture"}),
    "ouvre word": ("win_open_app", {"name": "word"}),
    "ouvre excel": ("win_open_app", {"name": "excel"}),
    "ouvre chrome": ("win_open_app", {"name": "chrome"}),
    "ouvre edge": ("win_open_app", {"name": "edge"}),
    "ouvre firefox": ("win_open_app", {"name": "firefox"}),
    "ouvre spotify": ("win_open_app", {"name": "spotify"}),
    "ouvre discord": ("win_open_app", {"name": "discord"}),
    "ouvre vs code": ("win_open_app", {"name": "code"}),
    "ouvre vscode": ("win_open_app", {"name": "code"}),
    "ouvre visual studio code": ("win_open_app", {"name": "code"}),
    "ouvre le panneau de configuration": ("win_open_app", {"name": "control"}),

    # WINDOWS — Fenetre
    "ferme la fenetre": ("win_close_app", {}),
    "ferme l'application": ("win_close_app", {}),
    "ferme le programme": ("win_close_app", {}),
    "alt f4": ("win_close_app", {}),
    "quitte": ("win_close_app", {}),
    "quitte l'application": ("win_close_app", {}),
    "minimise": ("win_minimize", {}),
    "minimise la fenetre": ("win_minimize", {}),
    "reduis la fenetre": ("win_minimize", {}),
    "cache la fenetre": ("win_minimize", {}),
    "mets en petit": ("win_minimize", {}),
    "maximise": ("win_maximize", {}),
    "maximise la fenetre": ("win_maximize", {}),
    "agrandis la fenetre": ("win_maximize", {}),
    "mets en grand": ("win_maximize", {}),
    "mets en plein ecran": ("win_maximize", {}),
    "change de fenetre": ("win_switch_app", {}),
    "alt tab": ("win_switch_app", {}),
    "fenetre suivante": ("win_switch_app", {}),
    "bascule": ("win_switch_app", {}),
    "passe a l'autre fenetre": ("win_switch_app", {}),
    "fenetre a gauche": ("win_snap_left", {}),
    "snap gauche": ("win_snap_left", {}),
    "mets a gauche": ("win_snap_left", {}),
    "ancre a gauche": ("win_snap_left", {}),
    "fenetre a droite": ("win_snap_right", {}),
    "snap droite": ("win_snap_right", {}),
    "mets a droite": ("win_snap_right", {}),
    "ancre a droite": ("win_snap_right", {}),
    "affiche le bureau": ("win_desktop_show", {}),
    "montre le bureau": ("win_desktop_show", {}),
    "bureau": ("win_desktop_show", {}),
    "cache tout": ("win_desktop_show", {}),
    "minimise tout": ("win_desktop_show", {}),

    # WINDOWS — Systeme
    "capture ecran windows": ("win_screenshot", {}),
    "screenshot windows": ("win_screenshot", {}),
    "capture d'ecran": ("win_screenshot", {}),
    "verrouille l'ecran": ("win_lock", {}),
    "verrouille": ("win_lock", {}),
    "verrouille le pc": ("win_lock", {}),
    "verrouillage": ("win_lock", {}),
    "lock": ("win_lock", {}),
    "monte le volume": ("win_volume", {"action": "up"}),
    "augmente le volume": ("win_volume", {"action": "up"}),
    "volume plus": ("win_volume", {"action": "up"}),
    "plus fort": ("win_volume", {"action": "up"}),
    "baisse le volume": ("win_volume", {"action": "down"}),
    "diminue le volume": ("win_volume", {"action": "down"}),
    "volume moins": ("win_volume", {"action": "down"}),
    "moins fort": ("win_volume", {"action": "down"}),
    "coupe le son": ("win_volume", {"action": "mute"}),
    "mute": ("win_volume", {"action": "mute"}),
    "silence": ("win_volume", {"action": "mute"}),
    "son coupe": ("win_volume", {"action": "mute"}),
    "reactive le son": ("win_volume", {"action": "mute"}),
    "augmente la luminosite": ("win_brightness", {"action": "up"}),
    "luminosite plus": ("win_brightness", {"action": "up"}),
    "plus lumineux": ("win_brightness", {"action": "up"}),
    "baisse la luminosite": ("win_brightness", {"action": "down"}),
    "luminosite moins": ("win_brightness", {"action": "down"}),
    "moins lumineux": ("win_brightness", {"action": "down"}),
    "active le wifi": ("win_wifi", {"on_off": "on"}),
    "desactive le wifi": ("win_wifi", {"on_off": "off"}),
    "coupe le wifi": ("win_wifi", {"on_off": "off"}),
    "allume le wifi": ("win_wifi", {"on_off": "on"}),
    "active le bluetooth": ("win_bluetooth", {"on_off": "on"}),
    "desactive le bluetooth": ("win_bluetooth", {"on_off": "off"}),
    "coupe le bluetooth": ("win_bluetooth", {"on_off": "off"}),
    "allume le bluetooth": ("win_bluetooth", {"on_off": "on"}),

    # WINDOWS — Alimentation
    "eteins l'ordinateur": ("win_shutdown", {}),
    "eteins le pc": ("win_shutdown", {}),
    "extinction": ("win_shutdown", {}),
    "arrete le pc": ("win_shutdown", {}),
    "shutdown": ("win_shutdown", {}),
    "eteins tout": ("win_shutdown", {}),
    "redemarre": ("win_restart", {}),
    "redemarre le pc": ("win_restart", {}),
    "redemarre l'ordinateur": ("win_restart", {}),
    "redemarrage": ("win_restart", {}),
    "restart": ("win_restart", {}),
    "mise en veille": ("win_sleep", {}),
    "veille": ("win_sleep", {}),
    "mets en veille": ("win_sleep", {}),
    "dors": ("win_sleep", {}),
    "sleep": ("win_sleep", {}),

    # WINDOWS — Divers
    "gestionnaire de taches": ("win_task_manager", {}),
    "task manager": ("win_task_manager", {}),
    "ouvre le gestionnaire de taches": ("win_task_manager", {}),
    "ctrl alt suppr": ("win_task_manager", {}),
    "recherche windows": ("win_search", {}),  # needs query
    "cherche sur windows": ("win_search", {}),
    "cherche dans le pc": ("win_search", {}),
    "copie": ("win_clipboard_copy", {}),
    "ctrl c": ("win_clipboard_copy", {}),
    "copier": ("win_clipboard_copy", {}),
    "colle": ("win_clipboard_paste", {}),
    "ctrl v": ("win_clipboard_paste", {}),
    "coller": ("win_clipboard_paste", {}),
    "efface les notifications": ("win_notification_clear", {}),
    "notifications": ("win_notification_clear", {}),
    "centre de notifications": ("win_notification_clear", {}),
    "ouvre l'explorateur a": ("win_file_explorer", {}),  # needs path

    # ===================================================================
    # SYSTEME — Monitoring
    # ===================================================================
    "usage processeur": ("sys_cpu_usage", {}),
    "usage cpu": ("sys_cpu_usage", {}),
    "charge processeur": ("sys_cpu_usage", {}),
    "combien de cpu": ("sys_cpu_usage", {}),
    "cpu": ("sys_cpu_usage", {}),
    "etat du processeur": ("sys_cpu_usage", {}),
    "usage memoire": ("sys_ram_usage", {}),
    "usage ram": ("sys_ram_usage", {}),
    "memoire": ("sys_ram_usage", {}),
    "combien de ram": ("sys_ram_usage", {}),
    "ram utilisee": ("sys_ram_usage", {}),
    "etat de la memoire": ("sys_ram_usage", {}),
    "espace disque": ("sys_disk_space", {}),
    "disque dur": ("sys_disk_space", {}),
    "combien d'espace": ("sys_disk_space", {}),
    "stockage": ("sys_disk_space", {}),
    "espace libre": ("sys_disk_space", {}),
    "etat du disque": ("sys_disk_space", {}),
    "etat des disques": ("sys_disk_space", {}),
    "temperature gpu": ("sys_gpu_temp", {}),
    "temperature carte graphique": ("sys_gpu_temp", {}),
    "gpu temperature": ("sys_gpu_temp", {}),
    "chauffe du gpu": ("sys_gpu_temp", {}),
    "etat du gpu": ("sys_gpu_temp", {}),
    "etat de la carte graphique": ("sys_gpu_temp", {}),
    "processus actifs": ("sys_processes", {"n": 10}),
    "liste les processus": ("sys_processes", {"n": 10}),
    "processus en cours": ("sys_processes", {"n": 10}),
    "qu'est-ce qui tourne": ("sys_processes", {"n": 10}),
    "quels processus": ("sys_processes", {"n": 10}),
    "top processus": ("sys_processes", {"n": 10}),
    "programmes en cours": ("sys_processes", {"n": 10}),
    "tue le processus": ("sys_kill_process", {}),  # needs name
    "arrete le processus": ("sys_kill_process", {}),
    "kill": ("sys_kill_process", {}),
    "force l'arret de": ("sys_kill_process", {}),
    "adresse ip": ("sys_ip_address", {}),
    "mon ip": ("sys_ip_address", {}),
    "quelle est mon ip": ("sys_ip_address", {}),
    "ip locale": ("sys_ip_address", {}),
    "ip address": ("sys_ip_address", {}),
    "uptime": ("sys_uptime", {}),
    "depuis combien de temps": ("sys_uptime", {}),
    "duree de fonctionnement": ("sys_uptime", {}),
    "temps de fonctionnement": ("sys_uptime", {}),
    "le pc tourne depuis": ("sys_uptime", {}),
    "batterie": ("sys_battery", {}),
    "niveau de batterie": ("sys_battery", {}),
    "combien de batterie": ("sys_battery", {}),
    "autonomie": ("sys_battery", {}),
    "etat de la batterie": ("sys_battery", {}),

    # ===================================================================
    # MULTIMEDIA — Controle media
    # ===================================================================
    "lecture": ("media_play_pause", {}),
    "play": ("media_play_pause", {}),
    "pause": ("media_play_pause", {}),
    "lecture pause": ("media_play_pause", {}),
    "play pause": ("media_play_pause", {}),
    "mets pause": ("media_play_pause", {}),
    "lance la musique": ("media_play_pause", {}),
    "arrete la musique": ("media_play_pause", {}),
    "reprends la lecture": ("media_play_pause", {}),
    "continue la musique": ("media_play_pause", {}),
    "piste suivante": ("media_next", {}),
    "chanson suivante": ("media_next", {}),
    "morceau suivant": ("media_next", {}),
    "musique suivante": ("media_next", {}),
    "next": ("media_next", {}),
    "suivant": ("media_next", {}),
    "saute": ("media_next", {}),
    "passe la chanson": ("media_next", {}),
    "piste precedente": ("media_previous", {}),
    "chanson precedente": ("media_previous", {}),
    "morceau precedent": ("media_previous", {}),
    "musique precedente": ("media_previous", {}),
    "previous": ("media_previous", {}),
    "precedent": ("media_previous", {}),
    "reviens a la chanson": ("media_previous", {}),
}


# ===========================================================================
# Extracteur de parametres dynamiques
# ===========================================================================
# Patterns: "cherche X" → query=X, "ouvre X" → url/name=X, etc.
PARAM_PATTERNS = [
    # browser_search: "cherche sur google X" / "recherche X"
    (r"(?:cherche sur google|recherche sur google|recherche google|google cherche|cherche sur internet|recherche sur internet|recherche web|fais une recherche)\s+(.+)",
     "browser_search", "query"),
    (r"(?:cherche|recherche|trouve)\s+(.+)",
     "browser_search", "query"),
    # browser_open: "ouvre le site X" / "va sur X" / "navigue vers X"
    (r"(?:ouvre le site|ouvre la page|va sur le site|va sur la page|navigue vers|ouvre l'adresse)\s+(.+)",
     "browser_open", "url"),
    # browser_click: "clique sur X"
    (r"(?:clique sur|appuie sur|selectionne)\s+(.+)",
     "browser_click", "text_or_selector"),
    # browser_type: "tape X" / "ecris X"
    (r"(?:tape|ecris|saisis|entre le texte|remplis)\s+(.+)",
     "browser_type", "text"),
    # browser_find: "cherche dans la page X"
    (r"(?:cherche dans la page|trouve dans la page|recherche dans la page|ctrl f)\s+(.+)",
     "browser_find", "text"),
    # browser_new_tab: "nouvel onglet X"
    (r"(?:nouvel onglet|nouveau tab|ouvre un (?:nouvel )?onglet)\s+(.+)",
     "browser_new_tab", "url"),
    # win_open_app: "ouvre X" (generique, apres les patterns specifiques)
    (r"ouvre\s+(?:le |la |l'|les |un |une )?(.+)",
     "win_open_app", "name"),
    # win_search: "recherche windows X"
    (r"(?:recherche windows|cherche sur windows|cherche dans le pc)\s+(.+)",
     "win_search", "query"),
    # win_file_explorer: "ouvre l'explorateur a X"
    (r"(?:ouvre l'explorateur a|ouvre l'explorateur dans|explorateur)\s+(.+)",
     "win_file_explorer", "path"),
    # sys_kill_process: "tue le processus X" / "kill X"
    (r"(?:tue le processus|arrete le processus|kill|force l'arret de)\s+(.+)",
     "sys_kill_process", "name"),
    # media_volume: "volume a X"
    (r"(?:volume a|mets le volume a|regle le volume a)\s+(\d+)",
     "media_volume", "level"),
]


# ===========================================================================
# Moteur de matching vocal
# ===========================================================================
def _normalize(text: str) -> str:
    """Normalise le texte vocal: minuscule, supprime accents redondants, trim."""
    text = text.lower().strip()
    # Supprime la ponctuation sauf les tirets et apostrophes utiles
    text = re.sub(r"[.,;:!?\"()]", "", text)
    # Normalise les espaces multiples
    text = re.sub(r"\s+", " ", text)
    return text


def _fuzzy_match(text: str, candidates: list, threshold: float = 0.55) -> tuple:
    """Retourne la meilleure correspondance fuzzy (commande, score)."""
    best_match = None
    best_score = 0.0

    for candidate in candidates:
        # Score 1: ratio direct
        score = difflib.SequenceMatcher(None, text, candidate).ratio()
        # Score 2: le candidat est contenu dans le texte
        if candidate in text:
            score = max(score, 0.85 + len(candidate) / (len(text) + 1) * 0.15)
        # Score 3: le texte commence par le candidat
        if text.startswith(candidate):
            score = max(score, 0.9 + len(candidate) / (len(text) + 1) * 0.1)
        # Score 4: correspondance exacte
        if text == candidate:
            score = 1.0

        if score > best_score:
            best_score = score
            best_match = candidate

    if best_score >= threshold:
        return best_match, best_score
    return None, 0.0


def execute_voice_command(text: str) -> str:
    """Parse un texte vocal, trouve la commande, extrait les parametres, execute.

    Args:
        text: Le texte vocal brut (ex: "cherche sur google meteo paris")

    Returns:
        Resultat textuel pour le TTS
    """
    ctrl = VoiceComputerControl()
    normalized = _normalize(text)

    if not normalized:
        return "Je n'ai pas compris la commande."

    # ----- Etape 1: Essayer les patterns regex pour extraire des parametres -----
    for pattern, method_name, param_name in PARAM_PATTERNS:
        m = re.match(pattern, normalized)
        if m:
            param_value = m.group(1).strip()
            if param_value:
                method = getattr(ctrl, method_name, None)
                if method:
                    try:
                        if param_name == "level":
                            return method(level=int(param_value))
                        return method(**{param_name: param_value})
                    except Exception as e:
                        return f"Erreur lors de l'execution: {e}"

    # ----- Etape 2: Match exact dans VOICE_COMMANDS -----
    if normalized in VOICE_COMMANDS:
        method_name, params = VOICE_COMMANDS[normalized]
        method = getattr(ctrl, method_name, None)
        if method:
            try:
                return method(**params)
            except Exception as e:
                return f"Erreur: {e}"

    # ----- Etape 3: Chercher la meilleure sous-chaine dans le texte -----
    # Trier les candidats par longueur decroissante (preference aux commandes longues)
    candidates = sorted(VOICE_COMMANDS.keys(), key=len, reverse=True)
    for candidate in candidates:
        if candidate in normalized:
            method_name, params = VOICE_COMMANDS[candidate]
            # Extraire un parametre residuel apres la commande
            remainder = normalized.replace(candidate, "").strip()
            method = getattr(ctrl, method_name, None)
            if method:
                try:
                    if remainder and not params:
                        # Tenter de passer le reste comme premier parametre
                        import inspect
                        sig = inspect.signature(method)
                        param_names = [p for p in sig.parameters if p != "self"]
                        if param_names:
                            return method(**{param_names[0]: remainder})
                    return method(**params)
                except Exception as e:
                    return f"Erreur: {e}"

    # ----- Etape 4: Fuzzy matching -----
    match, score = _fuzzy_match(normalized, list(VOICE_COMMANDS.keys()))
    if match:
        method_name, params = VOICE_COMMANDS[match]
        method = getattr(ctrl, method_name, None)
        if method:
            try:
                # Extraire un parametre residuel
                remainder = normalized
                for word in match.split():
                    remainder = remainder.replace(word, "", 1).strip()
                remainder = remainder.strip()

                if remainder and not params:
                    import inspect
                    sig = inspect.signature(method)
                    param_names = [p for p in sig.parameters if p != "self"]
                    if param_names:
                        return method(**{param_names[0]: remainder})
                return method(**params)
            except Exception as e:
                return f"Erreur: {e}"

    return f"Commande non reconnue: '{text}'. Dis 'aide' pour la liste des commandes."


# ===========================================================================
# CLI
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(
        description="JARVIS Voice Computer Control — Pilote Windows et navigateur a la voix",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python voice_computer_control.py --cmd "ouvre google"
  python voice_computer_control.py --cmd "cherche sur google meteo paris"
  python voice_computer_control.py --cmd "monte le volume"
  python voice_computer_control.py --cmd "usage processeur"
  python voice_computer_control.py --method browser_open --params '{"url":"https://google.com"}'
  python voice_computer_control.py --method sys_cpu_usage
  python voice_computer_control.py --list
  python voice_computer_control.py --list-methods
""")
    parser.add_argument("--cmd", type=str, help="Commande vocale a executer")
    parser.add_argument("--method", type=str, help="Methode a appeler directement")
    parser.add_argument("--params", type=str, default="{}", help="Parametres JSON pour --method")
    parser.add_argument("--list", action="store_true", help="Lister toutes les commandes vocales")
    parser.add_argument("--list-methods", action="store_true", help="Lister toutes les methodes disponibles")
    parser.add_argument("--count", action="store_true", help="Compter les commandes vocales")
    parser.add_argument("--json", action="store_true", help="Sortie JSON")
    args = parser.parse_args()

    # Liste des commandes vocales
    if args.list:
        by_method = {}
        for phrase, (method, params) in sorted(VOICE_COMMANDS.items()):
            by_method.setdefault(method, []).append(phrase)
        if args.json:
            print(json.dumps(by_method, indent=2, ensure_ascii=False))
        else:
            total = 0
            for method, phrases in sorted(by_method.items()):
                print(f"\n--- {method} ({len(phrases)} variantes) ---")
                for p in sorted(phrases):
                    print(f"  \"{p}\"")
                total += len(phrases)
            print(f"\nTotal: {total} commandes vocales")
        return

    # Compter
    if args.count:
        print(f"{len(VOICE_COMMANDS)} commandes vocales")
        return

    # Liste des methodes
    if args.list_methods:
        ctrl = VoiceComputerControl()
        methods = [m for m in dir(ctrl) if not m.startswith("_") and callable(getattr(ctrl, m))]
        if args.json:
            info = {}
            for m in methods:
                import inspect
                sig = inspect.signature(getattr(ctrl, m))
                params = {p: str(v.default) if v.default is not inspect.Parameter.empty else "required"
                          for p, v in sig.parameters.items() if p != "self"}
                doc = getattr(ctrl, m).__doc__ or ""
                info[m] = {"params": params, "doc": doc.strip().split("\n")[0]}
            print(json.dumps(info, indent=2, ensure_ascii=False))
        else:
            for m in methods:
                import inspect
                sig = inspect.signature(getattr(ctrl, m))
                doc = (getattr(ctrl, m).__doc__ or "").strip().split("\n")[0]
                print(f"  {m}{sig}  — {doc}")
            print(f"\nTotal: {len(methods)} methodes")
        return

    # Appel methode directe
    if args.method:
        ctrl = VoiceComputerControl()
        method = getattr(ctrl, args.method, None)
        if not method:
            print(f"ERREUR: Methode '{args.method}' inconnue", file=sys.stderr)
            sys.exit(1)
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError:
            print(f"ERREUR: Parametres JSON invalides: {args.params}", file=sys.stderr)
            sys.exit(1)
        try:
            result = method(**params)
            if args.json:
                print(json.dumps({"method": args.method, "params": params, "result": result},
                                 indent=2, ensure_ascii=False))
            else:
                print(result)
        except Exception as e:
            print(f"ERREUR: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # Commande vocale
    if args.cmd:
        result = execute_voice_command(args.cmd)
        if args.json:
            print(json.dumps({"command": args.cmd, "result": result}, indent=2, ensure_ascii=False))
        else:
            print(result)
        return

    # Mode interactif
    if sys.stdin.isatty():
        print("JARVIS Voice Computer Control — Mode interactif")
        print("Tapez une commande vocale (ou 'quit' pour quitter):\n")
        while True:
            try:
                cmd = input("> ").strip()
                if cmd.lower() in ("quit", "exit", "q"):
                    break
                if not cmd:
                    continue
                result = execute_voice_command(cmd)
                print(f"  {result}\n")
            except (KeyboardInterrupt, EOFError):
                break
        print("Au revoir.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
