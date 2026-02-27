#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
"""
JARVIS Learning Cycles — 100 scenarios Windows pilotage complet
Teste en parallele sur M1 (qwen3-8b + deepseek-r1), M2 (deepseek-coder), M3 (mistral-7b)
"""
import httpx
import asyncio
import json
import time
import random
from datetime import datetime
from pathlib import Path

# ── CONFIG ──────────────────────────────────────────────────
M1_URL = "http://10.5.0.2:1234/v1/chat/completions"
M1_KEY = "sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7"
M2_URL = "http://192.168.1.26:1234/v1/chat/completions"
M2_KEY = "sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4"
M3_URL = "http://192.168.1.113:1234/v1/chat/completions"
M3_KEY = "sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux"

MODELS = {
    "M1-qwen3":     {"url": M1_URL, "key": M1_KEY, "model": "qwen3-8b"},
    "M1-deepseek":  {"url": M1_URL, "key": M1_KEY, "model": "deepseek-r1-0528-qwen3-8b"},
    "M2-coder":     {"url": M2_URL, "key": M2_KEY, "model": "deepseek-coder-v2-lite-instruct"},
    "M3-mistral":   {"url": M3_URL, "key": M3_KEY, "model": "mistral-7b-instruct-v0.3"},
}

CONCURRENCY = 12  # requetes simultanées max (M1 dual model + M2 + M3)
TIMEOUT = 45      # secondes par requête

# ── 100 SCENARIOS WINDOWS ───────────────────────────────────
SCENARIOS = [
    # ── FICHIERS & DOSSIERS (1-15) ──
    {"id": 1,  "cat": "fichiers", "cmd": "ouvre le dossier Documents", "expected": "explorer", "powershell": "Start-Process explorer $env:USERPROFILE\\Documents"},
    {"id": 2,  "cat": "fichiers", "cmd": "crée un dossier Projets sur le bureau", "expected": "New-Item", "powershell": "New-Item -Path $env:USERPROFILE\\Desktop\\Projets -ItemType Directory"},
    {"id": 3,  "cat": "fichiers", "cmd": "supprime les fichiers temporaires", "expected": "Remove-Item", "powershell": "Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue"},
    {"id": 4,  "cat": "fichiers", "cmd": "liste les fichiers PDF sur le bureau", "expected": "Get-ChildItem", "powershell": "Get-ChildItem $env:USERPROFILE\\Desktop -Filter *.pdf"},
    {"id": 5,  "cat": "fichiers", "cmd": "copie le fichier rapport.txt dans Documents", "expected": "Copy-Item", "powershell": "Copy-Item rapport.txt $env:USERPROFILE\\Documents\\"},
    {"id": 6,  "cat": "fichiers", "cmd": "renomme le fichier ancien.txt en nouveau.txt", "expected": "Rename-Item", "powershell": "Rename-Item ancien.txt nouveau.txt"},
    {"id": 7,  "cat": "fichiers", "cmd": "montre l'espace disque disponible", "expected": "Get-PSDrive", "powershell": "Get-PSDrive -PSProvider FileSystem | Select Name, @{N='Free(GB)';E={[math]::Round($_.Free/1GB,2)}}"},
    {"id": 8,  "cat": "fichiers", "cmd": "compresse le dossier Logs en zip", "expected": "Compress-Archive", "powershell": "Compress-Archive -Path .\\Logs -DestinationPath .\\Logs.zip"},
    {"id": 9,  "cat": "fichiers", "cmd": "cherche les fichiers modifiés aujourd'hui", "expected": "Get-ChildItem", "powershell": "Get-ChildItem -Recurse | Where-Object {$_.LastWriteTime -ge (Get-Date).Date}"},
    {"id": 10, "cat": "fichiers", "cmd": "affiche la taille du dossier turbo", "expected": "Measure-Object", "powershell": "(Get-ChildItem F:\\BUREAU\\turbo -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB"},
    {"id": 11, "cat": "fichiers", "cmd": "crée un fichier texte avec du contenu", "expected": "Set-Content", "powershell": "Set-Content -Path note.txt -Value 'Hello JARVIS'"},
    {"id": 12, "cat": "fichiers", "cmd": "déplace tous les PNG dans un dossier images", "expected": "Move-Item", "powershell": "Move-Item *.png .\\images\\ -Force"},
    {"id": 13, "cat": "fichiers", "cmd": "affiche les 10 plus gros fichiers du disque", "expected": "Sort-Object", "powershell": "Get-ChildItem C:\\ -Recurse -File -ErrorAction SilentlyContinue | Sort-Object Length -Descending | Select -First 10 Name, @{N='MB';E={[math]::Round($_.Length/1MB,2)}}"},
    {"id": 14, "cat": "fichiers", "cmd": "vide la corbeille", "expected": "Clear-RecycleBin", "powershell": "Clear-RecycleBin -Force"},
    {"id": 15, "cat": "fichiers", "cmd": "ouvre le fichier config.json dans notepad", "expected": "notepad", "powershell": "Start-Process notepad config.json"},

    # ── PROCESSUS & APPS (16-30) ──
    {"id": 16, "cat": "processus", "cmd": "liste les processus qui utilisent le plus de mémoire", "expected": "Get-Process", "powershell": "Get-Process | Sort-Object WorkingSet64 -Descending | Select -First 10 Name, @{N='MB';E={[math]::Round($_.WorkingSet64/1MB)}}"},
    {"id": 17, "cat": "processus", "cmd": "ferme Chrome", "expected": "Stop-Process", "powershell": "Stop-Process -Name chrome -Force -ErrorAction SilentlyContinue"},
    {"id": 18, "cat": "processus", "cmd": "lance le calculateur Windows", "expected": "calc", "powershell": "Start-Process calc"},
    {"id": 19, "cat": "processus", "cmd": "ouvre VS Code dans le dossier turbo", "expected": "code", "powershell": "Start-Process code F:\\BUREAU\\turbo"},
    {"id": 20, "cat": "processus", "cmd": "vérifie si Discord est en cours d'exécution", "expected": "Get-Process", "powershell": "Get-Process discord -ErrorAction SilentlyContinue | Select Name, Id, CPU"},
    {"id": 21, "cat": "processus", "cmd": "ouvre le gestionnaire de tâches", "expected": "taskmgr", "powershell": "Start-Process taskmgr"},
    {"id": 22, "cat": "processus", "cmd": "redémarre l'explorateur Windows", "expected": "explorer", "powershell": "Stop-Process -Name explorer -Force; Start-Process explorer"},
    {"id": 23, "cat": "processus", "cmd": "affiche l'utilisation CPU actuelle", "expected": "Get-Counter", "powershell": "(Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples.CookedValue"},
    {"id": 24, "cat": "processus", "cmd": "lance PowerShell en tant qu'administrateur", "expected": "RunAs", "powershell": "Start-Process powershell -Verb RunAs"},
    {"id": 25, "cat": "processus", "cmd": "ferme toutes les fenêtres de Notepad", "expected": "Stop-Process", "powershell": "Stop-Process -Name notepad -Force -ErrorAction SilentlyContinue"},
    {"id": 26, "cat": "processus", "cmd": "liste les applications installées", "expected": "Get-Package", "powershell": "Get-Package | Select Name, Version | Sort Name"},
    {"id": 27, "cat": "processus", "cmd": "ouvre les paramètres Windows", "expected": "ms-settings", "powershell": "Start-Process ms-settings:"},
    {"id": 28, "cat": "processus", "cmd": "lance un terminal Windows", "expected": "wt", "powershell": "Start-Process wt"},
    {"id": 29, "cat": "processus", "cmd": "affiche le temps de fonctionnement du PC", "expected": "uptime", "powershell": "(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime"},
    {"id": 30, "cat": "processus", "cmd": "kill le processus avec PID 1234", "expected": "Stop-Process", "powershell": "Stop-Process -Id 1234 -Force"},

    # ── RESEAU (31-45) ──
    {"id": 31, "cat": "reseau", "cmd": "affiche mon adresse IP", "expected": "Get-NetIPAddress", "powershell": "Get-NetIPAddress -AddressFamily IPv4 | Where InterfaceAlias -ne 'Loopback' | Select IPAddress, InterfaceAlias"},
    {"id": 32, "cat": "reseau", "cmd": "ping google.com", "expected": "Test-Connection", "powershell": "Test-Connection google.com -Count 4"},
    {"id": 33, "cat": "reseau", "cmd": "affiche les connexions réseau actives", "expected": "Get-NetTCPConnection", "powershell": "Get-NetTCPConnection -State Established | Select LocalPort, RemoteAddress, RemotePort, OwningProcess | Sort RemoteAddress"},
    {"id": 34, "cat": "reseau", "cmd": "vérifie la vitesse de connexion", "expected": "Measure-Object", "powershell": "(Measure-Command { Invoke-WebRequest 'https://speed.cloudflare.com/__down?bytes=10000000' -UseBasicParsing }).TotalSeconds"},
    {"id": 35, "cat": "reseau", "cmd": "affiche le nom du réseau WiFi connecté", "expected": "netsh", "powershell": "netsh wlan show interfaces | Select-String 'SSID'"},
    {"id": 36, "cat": "reseau", "cmd": "ouvre les paramètres réseau", "expected": "ms-settings", "powershell": "Start-Process ms-settings:network"},
    {"id": 37, "cat": "reseau", "cmd": "affiche la table de routage", "expected": "Get-NetRoute", "powershell": "Get-NetRoute | Select DestinationPrefix, NextHop, InterfaceAlias | Format-Table"},
    {"id": 38, "cat": "reseau", "cmd": "scanne les ports ouverts sur localhost", "expected": "Test-NetConnection", "powershell": "1234,8080,1434,3000,5678 | ForEach { Test-NetConnection 127.0.0.1 -Port $_ -WarningAction SilentlyContinue | Select ComputerName, RemotePort, TcpTestSucceeded }"},
    {"id": 39, "cat": "reseau", "cmd": "affiche le DNS configuré", "expected": "Get-DnsClientServerAddress", "powershell": "Get-DnsClientServerAddress -AddressFamily IPv4 | Select InterfaceAlias, ServerAddresses"},
    {"id": 40, "cat": "reseau", "cmd": "flush le cache DNS", "expected": "Clear-DnsClientCache", "powershell": "Clear-DnsClientCache"},
    {"id": 41, "cat": "reseau", "cmd": "affiche la bande passante utilisée", "expected": "Get-NetAdapterStatistics", "powershell": "Get-NetAdapterStatistics | Select Name, ReceivedBytes, SentBytes"},
    {"id": 42, "cat": "reseau", "cmd": "résous le nom de domaine github.com", "expected": "Resolve-DnsName", "powershell": "Resolve-DnsName github.com"},
    {"id": 43, "cat": "reseau", "cmd": "vérifie si le port 1234 est ouvert sur M1", "expected": "Test-NetConnection", "powershell": "Test-NetConnection 10.5.0.2 -Port 1234"},
    {"id": 44, "cat": "reseau", "cmd": "affiche les partages réseau", "expected": "Get-SmbShare", "powershell": "Get-SmbShare"},
    {"id": 45, "cat": "reseau", "cmd": "désactive puis réactive le WiFi", "expected": "Disable-NetAdapter", "powershell": "Disable-NetAdapter -Name Wi-Fi -Confirm:$false; Start-Sleep 2; Enable-NetAdapter -Name Wi-Fi"},

    # ── SYSTEME & REGISTRE (46-60) ──
    {"id": 46, "cat": "systeme", "cmd": "affiche les infos système", "expected": "Get-ComputerInfo", "powershell": "Get-ComputerInfo | Select OsName, OsVersion, CsTotalPhysicalMemory, CsProcessors"},
    {"id": 47, "cat": "systeme", "cmd": "affiche la version de Windows", "expected": "winver", "powershell": "[System.Environment]::OSVersion.VersionString"},
    {"id": 48, "cat": "systeme", "cmd": "vérifie les mises à jour Windows", "expected": "WindowsUpdate", "powershell": "Get-WindowsUpdate -MicrosoftUpdate 2>$null || Write-Host 'Module PSWindowsUpdate requis'"},
    {"id": 49, "cat": "systeme", "cmd": "affiche la RAM disponible", "expected": "Get-CimInstance", "powershell": "$os = Get-CimInstance Win32_OperatingSystem; '{0:N2} GB libre / {1:N2} GB total' -f ($os.FreePhysicalMemory/1MB), ($os.TotalVisibleMemorySize/1MB)"},
    {"id": 50, "cat": "systeme", "cmd": "affiche la température GPU", "expected": "nvidia-smi", "powershell": "nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total --format=csv,noheader"},
    {"id": 51, "cat": "systeme", "cmd": "affiche les variables d'environnement", "expected": "Get-ChildItem Env:", "powershell": "Get-ChildItem Env: | Sort Name | Select Name, Value"},
    {"id": 52, "cat": "systeme", "cmd": "ajoute un chemin au PATH", "expected": "Environment", "powershell": "[Environment]::SetEnvironmentVariable('Path', $env:Path + ';C:\\NewPath', 'User')"},
    {"id": 53, "cat": "systeme", "cmd": "planifie un redémarrage dans 1 heure", "expected": "shutdown", "powershell": "shutdown /r /t 3600 /c 'Redémarrage planifié par JARVIS'"},
    {"id": 54, "cat": "systeme", "cmd": "annule le redémarrage planifié", "expected": "shutdown /a", "powershell": "shutdown /a"},
    {"id": 55, "cat": "systeme", "cmd": "affiche les événements système récents", "expected": "Get-EventLog", "powershell": "Get-EventLog -LogName System -Newest 10 | Select TimeGenerated, EntryType, Message"},
    {"id": 56, "cat": "systeme", "cmd": "vérifie l'intégrité des fichiers système", "expected": "sfc", "powershell": "sfc /scannow"},
    {"id": 57, "cat": "systeme", "cmd": "affiche les pilotes installés", "expected": "Get-WindowsDriver", "powershell": "driverquery /FO CSV | ConvertFrom-Csv | Select 'Module Name', 'Display Name' | Sort 'Display Name'"},
    {"id": 58, "cat": "systeme", "cmd": "vérifie la santé du disque", "expected": "Get-PhysicalDisk", "powershell": "Get-PhysicalDisk | Select FriendlyName, MediaType, HealthStatus, @{N='Size(GB)';E={[math]::Round($_.Size/1GB)}}"},
    {"id": 59, "cat": "systeme", "cmd": "affiche les clés de registre de démarrage", "expected": "Get-ItemProperty", "powershell": "Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run'"},
    {"id": 60, "cat": "systeme", "cmd": "crée un point de restauration système", "expected": "Checkpoint-Computer", "powershell": "Checkpoint-Computer -Description 'JARVIS Backup' -RestorePointType MODIFY_SETTINGS"},

    # ── SERVICES WINDOWS (61-70) ──
    {"id": 61, "cat": "services", "cmd": "liste les services en cours d'exécution", "expected": "Get-Service", "powershell": "Get-Service | Where Status -eq Running | Select Name, DisplayName | Sort DisplayName"},
    {"id": 62, "cat": "services", "cmd": "redémarre le service Windows Update", "expected": "Restart-Service", "powershell": "Restart-Service wuauserv -Force"},
    {"id": 63, "cat": "services", "cmd": "arrête le service de spouleur d'impression", "expected": "Stop-Service", "powershell": "Stop-Service Spooler -Force"},
    {"id": 64, "cat": "services", "cmd": "affiche les services désactivés", "expected": "Get-Service", "powershell": "Get-Service | Where StartType -eq Disabled | Select Name, DisplayName"},
    {"id": 65, "cat": "services", "cmd": "vérifie le statut du pare-feu Windows", "expected": "Get-NetFirewallProfile", "powershell": "Get-NetFirewallProfile | Select Name, Enabled"},
    {"id": 66, "cat": "services", "cmd": "active le bureau à distance", "expected": "Set-ItemProperty", "powershell": "Set-ItemProperty 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server' -Name fDenyTSConnections -Value 0"},
    {"id": 67, "cat": "services", "cmd": "affiche les tâches planifiées", "expected": "Get-ScheduledTask", "powershell": "Get-ScheduledTask | Where State -eq Ready | Select TaskName, TaskPath | Sort TaskName"},
    {"id": 68, "cat": "services", "cmd": "crée une tâche planifiée quotidienne", "expected": "Register-ScheduledTask", "powershell": "$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-File C:\\script.ps1'; $trigger = New-ScheduledTaskTrigger -Daily -At '08:00'; Register-ScheduledTask -TaskName 'JarvisDaily' -Action $action -Trigger $trigger"},
    {"id": 69, "cat": "services", "cmd": "vérifie l'antivirus Windows Defender", "expected": "Get-MpComputerStatus", "powershell": "Get-MpComputerStatus | Select AntivirusEnabled, RealTimeProtectionEnabled, AntivirusSignatureLastUpdated"},
    {"id": 70, "cat": "services", "cmd": "lance un scan antivirus rapide", "expected": "Start-MpScan", "powershell": "Start-MpScan -ScanType QuickScan"},

    # ── AUDIO & MULTIMEDIA (71-80) ──
    {"id": 71, "cat": "audio", "cmd": "monte le volume à 80%", "expected": "audio", "powershell": "$wshell = New-Object -ComObject WScript.Shell; 1..80 | ForEach { $wshell.SendKeys([char]175) }"},
    {"id": 72, "cat": "audio", "cmd": "coupe le son", "expected": "mute", "powershell": "$wshell = New-Object -ComObject WScript.Shell; $wshell.SendKeys([char]173)"},
    {"id": 73, "cat": "audio", "cmd": "prends une capture d'écran", "expected": "screenshot", "powershell": "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::PrimaryScreen | ForEach { $bmp = New-Object Drawing.Bitmap($_.Bounds.Width, $_.Bounds.Height); $g = [Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($_.Bounds.Location, [Drawing.Point]::Empty, $_.Bounds.Size); $bmp.Save(\"$env:USERPROFILE\\Desktop\\screenshot.png\") }"},
    {"id": 74, "cat": "audio", "cmd": "ouvre le mixeur de volume", "expected": "sndvol", "powershell": "Start-Process sndvol"},
    {"id": 75, "cat": "audio", "cmd": "affiche les périphériques audio", "expected": "Get-AudioDevice", "powershell": "Get-PnpDevice -Class AudioEndpoint | Where Status -eq OK | Select FriendlyName, Status"},
    {"id": 76, "cat": "audio", "cmd": "joue un son de notification", "expected": "SystemSounds", "powershell": "[System.Media.SystemSounds]::Exclamation.Play()"},
    {"id": 77, "cat": "audio", "cmd": "ouvre le lecteur Windows Media", "expected": "wmplayer", "powershell": "Start-Process wmplayer"},
    {"id": 78, "cat": "audio", "cmd": "enregistre l'écran pendant 10 secondes", "expected": "ffmpeg", "powershell": "ffmpeg -f gdigrab -framerate 30 -t 10 -i desktop -c:v libx264 -preset ultrafast $env:USERPROFILE\\Desktop\\recording.mp4"},
    {"id": 79, "cat": "audio", "cmd": "dis bonjour avec la synthèse vocale", "expected": "SAPI", "powershell": "Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Speak('Bonjour, je suis JARVIS')"},
    {"id": 80, "cat": "audio", "cmd": "affiche la résolution d'écran", "expected": "Screen", "powershell": "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::PrimaryScreen.Bounds | Select Width, Height"},

    # ── AFFICHAGE & BUREAU (81-90) ──
    {"id": 81, "cat": "affichage", "cmd": "active le mode sombre", "expected": "AppsUseLightTheme", "powershell": "Set-ItemProperty 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name AppsUseLightTheme -Value 0"},
    {"id": 82, "cat": "affichage", "cmd": "active le mode clair", "expected": "AppsUseLightTheme", "powershell": "Set-ItemProperty 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize' -Name AppsUseLightTheme -Value 1"},
    {"id": 83, "cat": "affichage", "cmd": "verrouille la session", "expected": "LockWorkStation", "powershell": "rundll32.exe user32.dll,LockWorkStation"},
    {"id": 84, "cat": "affichage", "cmd": "minimise toutes les fenêtres", "expected": "Shell.Application", "powershell": "(New-Object -ComObject Shell.Application).MinimizeAll()"},
    {"id": 85, "cat": "affichage", "cmd": "restaure toutes les fenêtres", "expected": "Shell.Application", "powershell": "(New-Object -ComObject Shell.Application).UndoMinimizeAll()"},
    {"id": 86, "cat": "affichage", "cmd": "change le fond d'écran", "expected": "SystemParametersInfo", "powershell": "Add-Type @'`nusing System.Runtime.InteropServices;`npublic class Wallpaper { [DllImport(\"user32.dll\")] public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni); }`n'@; [Wallpaper]::SystemParametersInfo(20, 0, 'C:\\path\\wallpaper.jpg', 3)"},
    {"id": 87, "cat": "affichage", "cmd": "active la veilleuse (night light)", "expected": "NightLight", "powershell": "Start-Process ms-settings:nightlight"},
    {"id": 88, "cat": "affichage", "cmd": "affiche les moniteurs connectés", "expected": "Get-CimInstance", "powershell": "Get-CimInstance Win32_DesktopMonitor | Select Name, ScreenWidth, ScreenHeight"},
    {"id": 89, "cat": "affichage", "cmd": "ouvre les paramètres d'affichage", "expected": "ms-settings:display", "powershell": "Start-Process ms-settings:display"},
    {"id": 90, "cat": "affichage", "cmd": "active le clavier virtuel", "expected": "osk", "powershell": "Start-Process osk"},

    # ── PRODUCTIVITE & DIVERS (91-100) ──
    {"id": 91,  "cat": "productivite", "cmd": "ouvre le calendrier", "expected": "outlookcal", "powershell": "Start-Process outlookcal: 2>$null || Start-Process ms-clock:"},
    {"id": 92,  "cat": "productivite", "cmd": "crée un rappel dans 30 minutes", "expected": "ScheduledTask", "powershell": "$action = New-ScheduledTaskAction -Execute 'msg' -Argument '* Rappel JARVIS!'; $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(30); Register-ScheduledTask -TaskName 'JarvisReminder' -Action $action -Trigger $trigger -Force"},
    {"id": 93,  "cat": "productivite", "cmd": "affiche la date et l'heure", "expected": "Get-Date", "powershell": "Get-Date -Format 'dddd dd MMMM yyyy HH:mm:ss'"},
    {"id": 94,  "cat": "productivite", "cmd": "ouvre la calculatrice Windows", "expected": "calc", "powershell": "Start-Process calc"},
    {"id": 95,  "cat": "productivite", "cmd": "copie du texte dans le presse-papier", "expected": "Set-Clipboard", "powershell": "Set-Clipboard 'Texte copié par JARVIS'"},
    {"id": 96,  "cat": "productivite", "cmd": "affiche le contenu du presse-papier", "expected": "Get-Clipboard", "powershell": "Get-Clipboard"},
    {"id": 97,  "cat": "productivite", "cmd": "ouvre un site web", "expected": "Start-Process", "powershell": "Start-Process 'https://github.com'"},
    {"id": 98,  "cat": "productivite", "cmd": "affiche le météo", "expected": "Invoke-RestMethod", "powershell": "(Invoke-RestMethod 'https://wttr.in/Paris?format=3')"},
    {"id": 99,  "cat": "productivite", "cmd": "éteins le PC dans 5 minutes", "expected": "shutdown", "powershell": "shutdown /s /t 300 /c 'Extinction planifiée par JARVIS'"},
    {"id": 100, "cat": "productivite", "cmd": "annule l'extinction", "expected": "shutdown /a", "powershell": "shutdown /a"},
]

# ── PROMPT TEMPLATE ─────────────────────────────────────────
def make_prompt(scenario: dict) -> str:
    return f"""/no_think
Tu es JARVIS, assistant IA pour Windows 11. L'utilisateur dit: "{scenario['cmd']}"

Genere la commande PowerShell correspondante. Reponds UNIQUEMENT avec:
1. La commande PowerShell exacte (une seule ligne si possible)
2. Une explication courte (1 phrase)

Format:
```powershell
<commande>
```
Explication: <explication>"""

# ── API CALL ────────────────────────────────────────────────
async def call_model(client: httpx.AsyncClient, name: str, cfg: dict, prompt: str, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        t0 = time.time()
        try:
            # Chat Completions API (OpenAI compat)
            resp = await client.post(
                cfg["url"],
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"},
                json={
                    "model": cfg["model"],
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 512,
                    "stream": False
                },
                timeout=TIMEOUT
            )
            data = resp.json()
            # Chat Completions format
            content = ""
            choices = data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
            latency = round(time.time() - t0, 2)
            return {"model": name, "content": content, "latency": latency, "ok": bool(content)}
        except Exception as e:
            return {"model": name, "content": str(e)[:200], "latency": round(time.time() - t0, 2), "ok": False}

# ── SCORING ─────────────────────────────────────────────────
def score_response(response: dict, scenario: dict) -> int:
    """Score 0-100 based on keyword match and quality."""
    if not response["ok"]:
        return 0
    content = response["content"].lower()
    score = 0
    # Contains expected keyword
    if scenario["expected"].lower() in content:
        score += 40
    # Contains powershell code block
    if "```powershell" in content or "```ps" in content:
        score += 20
    # Contains explanation
    if "explication" in content or "explanation" in content:
        score += 10
    # Reasonable length
    if 50 < len(content) < 2000:
        score += 15
    # Contains relevant command parts
    ps_parts = scenario["powershell"].lower().split()
    matches = sum(1 for p in ps_parts[:3] if p in content)
    score += min(matches * 5, 15)
    return min(score, 100)

# ── MAIN LOOP ───────────────────────────────────────────────
async def run_cycles():
    results = []
    stats = {name: {"total": 0, "score_sum": 0, "latency_sum": 0, "errors": 0} for name in MODELS}

    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient() as client:
        for cycle_num, scenario in enumerate(SCENARIOS, 1):
            prompt = make_prompt(scenario)

            # Launch all models in parallel for this scenario
            tasks = [
                call_model(client, name, cfg, prompt, semaphore)
                for name, cfg in MODELS.items()
            ]
            responses = await asyncio.gather(*tasks)

            # Score each response
            cycle_result = {
                "cycle": cycle_num,
                "scenario": scenario["cmd"],
                "category": scenario["cat"],
                "responses": []
            }

            best_score = 0
            best_model = ""

            for resp in responses:
                s = score_response(resp, scenario)
                resp["score"] = s
                cycle_result["responses"].append(resp)
                stats[resp["model"]]["total"] += 1
                stats[resp["model"]]["score_sum"] += s
                stats[resp["model"]]["latency_sum"] += resp["latency"]
                if not resp["ok"]:
                    stats[resp["model"]]["errors"] += 1
                if s > best_score:
                    best_score = s
                    best_model = resp["model"]

            cycle_result["winner"] = best_model
            cycle_result["best_score"] = best_score
            results.append(cycle_result)

            # Progress
            cat_tag = f"[{scenario['cat'][:5]:>5}]"
            scores_str = " | ".join(f"{r['model']}:{r['score']}" for r in responses)
            print(f"[{cycle_num:3d}/100] {cat_tag} {scenario['cmd'][:45]:<45} -> Winner: {best_model} ({best_score}) | {scores_str}", flush=True)

    # ── FINAL STATS ─────────────────────────────────────────
    print("\n" + "="*80)
    print("RESULTATS FINAUX — 100 CYCLES D'APPRENTISSAGE")
    print("="*80)

    for name, st in sorted(stats.items(), key=lambda x: x[1]["score_sum"], reverse=True):
        avg_score = st["score_sum"] / max(st["total"], 1)
        avg_lat = st["latency_sum"] / max(st["total"], 1)
        print(f"  {name:15s} | Score moyen: {avg_score:5.1f}/100 | Latence moy: {avg_lat:5.2f}s | Erreurs: {st['errors']}/{st['total']}")

    # Category breakdown
    print("\n── Par catégorie ──")
    categories = set(s["cat"] for s in SCENARIOS)
    for cat in sorted(categories):
        cat_results = [r for r in results if r["category"] == cat]
        winners = {}
        for r in cat_results:
            w = r["winner"]
            winners[w] = winners.get(w, 0) + 1
        winner_str = ", ".join(f"{k}:{v}" for k, v in sorted(winners.items(), key=lambda x: -x[1]))
        avg = sum(r["best_score"] for r in cat_results) / len(cat_results)
        print(f"  {cat:15s} | {len(cat_results)} tests | Score best moy: {avg:.1f} | Winners: {winner_str}")

    # Save results
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_cycles": 100,
        "stats": stats,
        "results": results
    }
    outpath = Path("F:/BUREAU/turbo/data") / f"learning_100cycles_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    outpath.parent.mkdir(exist_ok=True)
    outpath.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRapport sauvé: {outpath}")

    return report

if __name__ == "__main__":
    asyncio.run(run_cycles())
