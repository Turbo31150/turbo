# WINDOWS.md — Reference PowerShell pour Pilotage Windows Complet

Toutes les commandes ci-dessous s'executent via l'outil `exec` (PowerShell).
IMPORTANT: exec = PowerShell sur Windows. Utilise ces commandes telles quelles.

---

## 1. Fichiers & Dossiers

```powershell
# Lister un dossier
Get-ChildItem "C:\chemin" | Select-Object Mode, LastWriteTime, Length, Name | Format-Table -AutoSize

# Lister recursivement avec filtre
Get-ChildItem "C:\chemin" -Recurse -Filter "*.txt" -ErrorAction SilentlyContinue | Select-Object -First 20 FullName

# Creer un dossier
New-Item -ItemType Directory -Force -Path "C:\chemin\nouveau"

# Copier fichier/dossier
Copy-Item "C:\source" "C:\destination" -Recurse -Force

# Deplacer fichier/dossier
Move-Item "C:\source" "C:\destination" -Force

# Supprimer (vers corbeille — SECURISE)
Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("C:\fichier", "UIOption.OnlyErrorDialogs", "RecycleOption.SendToRecycleBin")

# Supprimer (permanent — ATTENTION)
Remove-Item "C:\chemin" -Recurse -Force

# Lire un fichier texte (50 premieres lignes)
Get-Content "C:\fichier.txt" -TotalCount 50

# Ecrire dans un fichier
Set-Content "C:\fichier.txt" -Value "contenu"

# Ajouter a un fichier
Add-Content "C:\fichier.txt" -Value "ligne ajoutee"

# Compresser en ZIP
Compress-Archive -Path "C:\dossier" -DestinationPath "C:\archive.zip" -Force

# Decompresser un ZIP
Expand-Archive -Path "C:\archive.zip" -DestinationPath "C:\destination" -Force

# Taille d'un dossier
(Get-ChildItem "C:\dossier" -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
```

---

## 2. Processus

```powershell
# Top 10 CPU
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, Id, CPU, @{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB,1)}} | Format-Table -AutoSize

# Top 10 RAM
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 Name, Id, @{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB,1)}}, CPU | Format-Table -AutoSize

# Chercher un processus
Get-Process -Name "*chrome*" -ErrorAction SilentlyContinue | Select-Object Name, Id, CPU, @{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB,1)}}

# Tuer un processus par nom
Stop-Process -Name "processus" -Force -ErrorAction SilentlyContinue

# Tuer un processus par PID
Stop-Process -Id 12345 -Force -ErrorAction SilentlyContinue

# Lancer un processus
Start-Process "app.exe"
Start-Process "app.exe" -ArgumentList "arg1 arg2"

# Nombre total de processus
(Get-Process).Count
```

---

## 3. Reseau

```powershell
# Adresses IP
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -ne '127.0.0.1' } | ForEach-Object { $_.InterfaceAlias + ': ' + $_.IPAddress }

# Tester connexion (ping)
Test-Connection "google.com" -Count 2 | Select-Object Address, ResponseTime | Format-Table

# Tester un port specifique
Test-NetConnection -ComputerName "192.168.1.26" -Port 1234

# Ports ouverts (en ecoute)
Get-NetTCPConnection -State Listen | Select-Object LocalPort, OwningProcess, @{N='Process';E={(Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).Name}} | Sort-Object LocalPort | Format-Table -AutoSize

# Connexions actives
Get-NetTCPConnection -State Established | Select-Object LocalPort, RemoteAddress, RemotePort, @{N='Process';E={(Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).Name}} | Format-Table -AutoSize

# WiFi — profils sauvegardes
netsh wlan show profiles

# WiFi — reseaux disponibles
netsh wlan show networks mode=bssid

# WiFi — connecter a un reseau
netsh wlan connect name="NomReseau"

# DNS — resoudre un nom
Resolve-DnsName "google.com"

# DNS — cache
Get-DnsClientCache | Select-Object -First 20 Entry, RecordType, Data

# IP publique
(Invoke-WebRequest -Uri "https://api.ipify.org" -UseBasicParsing).Content

# Adaptateurs reseau
Get-NetAdapter | Select-Object Name, Status, LinkSpeed, MacAddress | Format-Table -AutoSize

# Debit/stats
Get-NetAdapterStatistics | Select-Object Name, ReceivedBytes, SentBytes | Format-Table -AutoSize
```

---

## 4. Audio

```powershell
# Volume haut (1 cran)
(New-Object -ComObject WScript.Shell).SendKeys([char]175)

# Volume bas (1 cran)
(New-Object -ComObject WScript.Shell).SendKeys([char]174)

# Mute/Unmute (bascule)
(New-Object -ComObject WScript.Shell).SendKeys([char]173)

# Volume haut x5 (5 crans)
$ws = New-Object -ComObject WScript.Shell; 1..5 | ForEach-Object { $ws.SendKeys([char]175) }

# Volume bas x5
$ws = New-Object -ComObject WScript.Shell; 1..5 | ForEach-Object { $ws.SendKeys([char]174) }

# Devices audio
Get-CimInstance Win32_SoundDevice | Select-Object Name, Status | Format-Table -AutoSize

# Media play/pause
(New-Object -ComObject WScript.Shell).SendKeys([char]179)

# Media suivant
(New-Object -ComObject WScript.Shell).SendKeys([char]176)

# Media precedent
(New-Object -ComObject WScript.Shell).SendKeys([char]177)
```

---

## 5. Ecran & Affichage

```powershell
# Screenshot (sauvegarde sur le Bureau)
Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; $bmp = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height); $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size); $path = [Environment]::GetFolderPath('Desktop') + "\capture_$(Get-Date -Format 'yyyyMMdd_HHmmss').png"; $bmp.Save($path); $path

# Resolution ecran
Add-Type -AssemblyName System.Windows.Forms; $s = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "Resolution: $($s.Width)x$($s.Height)"

# Info GPU
Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name + ' | VRAM: ' + [math]::Round($_.AdapterRAM/1GB,1).ToString() + 'GB | Driver: ' + $_.DriverVersion }

# Luminosite (laptops uniquement) — valeur 0-100
(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, 50)

# Luminosite actuelle
(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness

# Multi-moniteurs
Get-CimInstance Win32_VideoController | Select-Object Name, CurrentHorizontalResolution, CurrentVerticalResolution | Format-Table -AutoSize

# Tous les ecrans
Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::AllScreens | ForEach-Object { $_.DeviceName + ': ' + $_.Bounds.Width + 'x' + $_.Bounds.Height + ' Primary=' + $_.Primary }
```

---

## 6. Clipboard

```powershell
# Lire le presse-papier
Get-Clipboard

# Ecrire dans le presse-papier
Set-Clipboard -Value "texte a copier"

# Copier un fichier dans le clipboard
Get-Content "C:\fichier.txt" | Set-Clipboard

# Vider le clipboard
Set-Clipboard -Value ""
```

---

## 7. Systeme

```powershell
# Info systeme complete
Get-ComputerInfo | Select-Object OsName, OsVersion, CsName, CsTotalPhysicalMemory, OsArchitecture | Format-List

# CPU usage instantane
Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 1 | ForEach-Object { $_.CounterSamples[0].CookedValue.ToString("0.0") + "%" }

# RAM usage
$os = Get-CimInstance Win32_OperatingSystem; $total = [math]::Round($os.TotalVisibleMemorySize/1MB, 1); $free = [math]::Round($os.FreePhysicalMemory/1MB, 1); $used = $total - $free; "RAM: $used/$total GB (libre: $free GB)"

# Disques — espace
Get-CimInstance Win32_LogicalDisk | ForEach-Object { $_.DeviceID + ' ' + [math]::Round($_.FreeSpace/1GB,1).ToString() + '/' + [math]::Round($_.Size/1GB,1).ToString() + ' GB libre' }

# Uptime
$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; $up = (Get-Date) - $boot; "Uptime: $($up.Days)j $($up.Hours)h $($up.Minutes)m"

# Batterie (laptops)
Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus

# Temperature CPU (si supporte)
Get-CimInstance -Namespace root/WMI -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue | ForEach-Object { [math]::Round(($_.CurrentTemperature - 2732) / 10, 1).ToString() + "C" }

# Variables d'environnement
Get-ChildItem Env: | Select-Object Name, Value | Format-Table -AutoSize

# Version Windows detaillee
[System.Environment]::OSVersion.VersionString + " Build " + (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").CurrentBuild

# Hostname
$env:COMPUTERNAME

# Utilisateur courant
$env:USERNAME + " (" + [System.Security.Principal.WindowsIdentity]::GetCurrent().Name + ")"
```

---

## 8. Applications & Fenetres

```powershell
# Ouvrir une application
Start-Process "chrome"
Start-Process "notepad"
Start-Process "code"           # VS Code
Start-Process "explorer.exe"   # Explorateur
Start-Process "calc"           # Calculatrice
Start-Process "mspaint"        # Paint
Start-Process "cmd"            # Terminal CMD
Start-Process "powershell"     # Terminal PS
Start-Process "wt"             # Windows Terminal

# Ouvrir une URL
Start-Process "chrome" "https://google.com"
Start-Process "https://google.com"   # navigateur par defaut

# Ouvrir un fichier avec l'app par defaut
Start-Process "C:\chemin\fichier.pdf"
Invoke-Item "C:\chemin\fichier.pdf"

# Ouvrir un dossier dans Explorer
Start-Process explorer.exe -ArgumentList "C:\chemin"

# Fermer une application
Stop-Process -Name "chrome" -Force -ErrorAction SilentlyContinue

# Lister les fenetres ouvertes
Get-Process | Where-Object { $_.MainWindowTitle -ne '' } | Select-Object Id, ProcessName, MainWindowTitle | Format-Table -AutoSize

# Focus sur une fenetre (par titre partiel)
Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class Win { [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd); }'; $p = Get-Process | Where-Object { $_.MainWindowTitle -match "TITRE" } | Select-Object -First 1; if ($p) { [Win]::SetForegroundWindow($p.MainWindowHandle) }

# Minimiser une fenetre
Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class Win { [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow); }'; $p = Get-Process | Where-Object { $_.MainWindowTitle -match "TITRE" } | Select-Object -First 1; if ($p) { [Win]::ShowWindow($p.MainWindowHandle, 6) }

# Maximiser une fenetre
# Meme code que minimiser mais avec nCmdShow = 3

# Lister apps installees
Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\* | Where-Object { $_.DisplayName -ne $null } | Select-Object DisplayName, DisplayVersion | Sort-Object DisplayName | Format-Table -AutoSize
```

---

## 9. Services Windows

```powershell
# Services en cours
Get-Service | Where-Object Status -eq Running | Select-Object Name, DisplayName | Format-Table -AutoSize

# Chercher un service
Get-Service -Name "*ssh*" -ErrorAction SilentlyContinue | Select-Object Status, Name, DisplayName

# Demarrer un service
Start-Service "NomService" -ErrorAction SilentlyContinue

# Arreter un service
Stop-Service "NomService" -Force -ErrorAction SilentlyContinue

# Redemarrer un service
Restart-Service "NomService" -Force -ErrorAction SilentlyContinue

# Services au demarrage automatique
Get-Service | Where-Object { $_.StartType -eq 'Automatic' -and $_.Status -ne 'Running' } | Select-Object Name, Status, DisplayName | Format-Table -AutoSize
```

---

## 10. Notifications

```powershell
# Toast notification Windows
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; $t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); $t.GetElementsByTagName('text')[0].AppendChild($t.CreateTextNode('TITRE')) > $null; $t.GetElementsByTagName('text')[1].AppendChild($t.CreateTextNode('MESSAGE')) > $null; $n = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('JARVIS'); $n.Show([Windows.UI.Notifications.ToastNotification]::new($t))
```

Remplacer `TITRE` et `MESSAGE` par le contenu voulu.

---

## 11. Peripheriques

```powershell
# Peripheriques USB connectes
Get-CimInstance Win32_USBControllerDevice | ForEach-Object { [wmi]$_.Dependent } | Select-Object Name, Status | Format-Table -AutoSize

# Peripheriques USB simplifies
Get-PnpDevice -Class USB | Where-Object Status -eq OK | Select-Object FriendlyName, Status | Format-Table -AutoSize

# Bluetooth
Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | Select-Object FriendlyName, Status | Format-Table -AutoSize

# Imprimantes
Get-Printer | Select-Object Name, PrinterStatus, PortName | Format-Table -AutoSize

# Imprimante par defaut
Get-CimInstance Win32_Printer | Where-Object Default -eq $true | Select-Object Name

# Webcams / cameras
Get-PnpDevice -Class Camera -ErrorAction SilentlyContinue | Select-Object FriendlyName, Status

# Disques physiques
Get-PhysicalDisk | Select-Object FriendlyName, MediaType, Size, HealthStatus | Format-Table -AutoSize
```

---

## 12. Power & Securite

```powershell
# Verrouiller l'ecran
rundll32.exe user32.dll,LockWorkStation

# Mise en veille
Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)

# Eteindre le PC
Stop-Computer -Force

# Redemarrer le PC
Restart-Computer -Force

# Plan d'alimentation — lister
powercfg /list

# Plan d'alimentation — activer haute performance
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c

# Plan d'alimentation — activer equilibre
powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e

# Firewall — statut
Get-NetFirewallProfile | Select-Object Name, Enabled | Format-Table -AutoSize

# Firewall — regles actives
Get-NetFirewallRule -Enabled True | Select-Object -First 20 DisplayName, Direction, Action | Format-Table -AutoSize

# Firewall — bloquer un port
New-NetFirewallRule -DisplayName "Block Port 8080" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Block

# Windows Defender — statut
Get-MpComputerStatus | Select-Object AntivirusEnabled, RealTimeProtectionEnabled, AntivirusSignatureLastUpdated

# Windows Defender — scan rapide
Start-MpScan -ScanType QuickScan

# Taches planifiees
Get-ScheduledTask | Where-Object { $_.State -eq 'Ready' } | Select-Object -First 20 TaskName, State | Format-Table -AutoSize

# MAJ Windows (si module installe)
# Install-Module PSWindowsUpdate -Force
# Get-WindowsUpdate
```

---

## 13. Clavier & Souris (automation)

```powershell
# Envoyer des touches a la fenetre active
Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("texte")

# Raccourci clavier (ex: Ctrl+C)
Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("^c")
# ^ = Ctrl, % = Alt, + = Shift
# {ENTER}, {TAB}, {ESC}, {BACKSPACE}, {DELETE}, {F1}-{F12}
# {UP}, {DOWN}, {LEFT}, {RIGHT}, {HOME}, {END}

# Clic souris a coordonnees (x, y)
Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class Mouse { [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y); [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, int dwExtraInfo); }'; [Mouse]::SetCursorPos(500, 300); Start-Sleep -Milliseconds 100; [Mouse]::mouse_event(0x0002, 0, 0, 0, 0); [Mouse]::mouse_event(0x0004, 0, 0, 0, 0)
```

---

## 14. Registre Windows

```powershell
# Lire une valeur
Get-ItemPropertyValue "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion" -Name "CurrentBuild"

# Lire toutes les valeurs d'une cle
Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion"

# Ecrire une valeur
Set-ItemProperty "HKCU:\Software\MaCle" -Name "MaValeur" -Value "donnee" -Type String

# Creer une cle
New-Item -Path "HKCU:\Software\MaCle" -Force
```

---

## 15. Commandes avancees

### Speed test reseau natif (sans outil tiers)
```powershell
$start=(Get-Date); Invoke-WebRequest "http://speedtest.tele2.net/10MB.zip" -OutFile "$env:TEMP\st.tmp" -UseBasicParsing; $s=(Get-Date)-$start; Remove-Item "$env:TEMP\st.tmp"; "Download: {0:N2} MB/s" -f (10/$s.TotalSeconds)
```

### Mot de passe WiFi sauvegarde
```powershell
netsh wlan show profile name="NomReseau" key=clear
```

### Traceroute
```powershell
Test-NetConnection google.com -TraceRoute
```

### Rechercher dans le contenu de fichiers
```powershell
Select-String -Path "C:\logs\*.log" -Pattern "ERROR" | Select-Object Path, LineNumber, Line
```

### Programmes installes (64+32 bit)
```powershell
Get-ItemProperty @("HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*","HKLM:\SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*") | Where-Object { $_.DisplayName } | Select-Object DisplayName, DisplayVersion | Sort-Object DisplayName
```

### Bluetooth on/off
```powershell
# Activer
Get-PnpDevice | Where-Object { $_.Class -eq "Bluetooth" } | Enable-PnpDevice -Confirm:$false

# Desactiver
Get-PnpDevice | Where-Object { $_.Class -eq "Bluetooth" } | Disable-PnpDevice -Confirm:$false
```

### Imprimante — imprimer un fichier
```powershell
Start-Process "C:\document.pdf" -Verb Print
```

### Multi-moniteur — changer disposition
```powershell
DisplaySwitch.exe /clone      # dupliquer
DisplaySwitch.exe /extend     # etendre
DisplaySwitch.exe /external   # ecran externe seul
DisplaySwitch.exe /internal   # ecran interne seul
```

### Sortie JSON (pour parsing agent)
```powershell
Get-Process | Select-Object -First 5 Name, CPU, WorkingSet64 | ConvertTo-Json -Depth 2
Get-CimInstance Win32_OperatingSystem | Select-Object FreePhysicalMemory, TotalVisibleMemorySize | ConvertTo-Json
```

### Ouvrir les Settings Windows directement
```powershell
Start-Process "ms-settings:"                  # Settings principal
Start-Process "ms-settings:display"           # Affichage
Start-Process "ms-settings:network-wifi"      # WiFi
Start-Process "ms-settings:bluetooth"         # Bluetooth
Start-Process "ms-settings:sound"             # Son
Start-Process "ms-settings:privacy"           # Confidentialite
Start-Process "ms-settings:windowsupdate"     # Mises a jour
```

---

## Notes pour l'agent

- **exec = PowerShell** sur Windows. Toutes ces commandes sont directement utilisables.
- **TOUJOURS** utiliser `127.0.0.1` au lieu de `localhost` (IPv6 timeout +10s).
- Pour les operations audio/fenetre: doit tourner dans la session utilisateur active.
- Utiliser `-ErrorAction SilentlyContinue` pour eviter les erreurs bloquantes.
- Ajouter `| ConvertTo-Json` pour un output structurable par l'agent.
- **Shutdown / Restart**: TOUJOURS demander confirmation a l'utilisateur avant!

---

## Aliases rapides

| Action | Commande courte |
|---|---|
| Volume + | `(New-Object -ComObject WScript.Shell).SendKeys([char]175)` |
| Volume - | `(New-Object -ComObject WScript.Shell).SendKeys([char]174)` |
| Mute | `(New-Object -ComObject WScript.Shell).SendKeys([char]173)` |
| Play/Pause | `(New-Object -ComObject WScript.Shell).SendKeys([char]179)` |
| Next | `(New-Object -ComObject WScript.Shell).SendKeys([char]176)` |
| Previous | `(New-Object -ComObject WScript.Shell).SendKeys([char]177)` |
| Lock | `rundll32.exe user32.dll,LockWorkStation` |
| Sleep | `Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend',$false,$false)` |
| Clipboard | `Get-Clipboard` |
| IP publique | `(Invoke-WebRequest -Uri "https://api.ipify.org" -UseBasicParsing).Content` |
| Disques | `Get-CimInstance Win32_LogicalDisk \| ForEach-Object { $_.DeviceID + ' ' + [math]::Round($_.FreeSpace/1GB,1) + '/' + [math]::Round($_.Size/1GB,1) + 'GB' }` |
| CPU% | `(Get-Counter '\Processor(_Total)\% Processor Time').CounterSamples.CookedValue` |
| Uptime | `(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime \| Select-Object Days,Hours,Minutes` |
