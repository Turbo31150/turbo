# Create-DesktopShortcuts.ps1
# Genere les raccourcis JARVIS sur le bureau avec icones Windows
# Usage: powershell -ExecutionPolicy Bypass -File Create-DesktopShortcuts.ps1

$Desktop = [System.Environment]::GetFolderPath("Desktop")
$LaunchersDir = "/home/turbo\TRADING_V2_PRODUCTION\launchers"
$Shell = New-Object -ComObject WScript.Shell

# Mapping: nom fichier -> (nom raccourci, description, icone Windows)
# Icones: shell32.dll contient 300+ icones, imageres.dll aussi
$Shortcuts = @(
    @{
        Bat = "JARVIS_GUI.bat"
        Name = "JARVIS - Command Center"
        Desc = "GUI Cockpit Pilotage + Memoire + Stats"
        Icon = "/Windows\System32\shell32.dll,21"  # PC monitor
    },
    @{
        Bat = "JARVIS_VOICE.bat"
        Name = "JARVIS - Voice PTT"
        Desc = "Mode vocal Push-to-Talk (RIGHT_CTRL)"
        Icon = "/Windows\System32\shell32.dll,168"  # Microphone
    },
    @{
        Bat = "JARVIS_KEYBOARD.bat"
        Name = "JARVIS - Mode Clavier"
        Desc = "Commander v3.5 en mode texte"
        Icon = "/Windows\System32\shell32.dll,44"  # Terminal/keyboard
    },
    @{
        Bat = "SCAN_HYPER.bat"
        Name = "JARVIS - Hyper Scan"
        Desc = "Grid Computing M2+M3+Gemini"
        Icon = "/Windows\System32\shell32.dll,22"  # Search/magnifier
    },
    @{
        Bat = "SNIPER.bat"
        Name = "JARVIS - Sniper Breakout"
        Desc = "Detection pre-pump orderbook"
        Icon = "/Windows\System32\shell32.dll,48"  # Target/crosshair
    },
    @{
        Bat = "PIPELINE_10.bat"
        Name = "JARVIS - Pipeline 10 Cycles"
        Desc = "Auto scan + DB 10 iterations"
        Icon = "/Windows\System32\shell32.dll,46"  # Gears/refresh
    },
    @{
        Bat = "MONITOR_RIVER.bat"
        Name = "JARVIS - Monitor RIVER"
        Desc = "Scalp 1min avec alertes Telegram"
        Icon = "/Windows\System32\shell32.dll,24"  # Chart/signal
    },
    @{
        Bat = "TRIDENT.bat"
        Name = "JARVIS - Trident Execute"
        Desc = "Multi-ordres MEXC (DRY RUN)"
        Icon = "/Windows\System32\shell32.dll,25"  # Lightning
    },
    @{
        Bat = "SNIPER_10.bat"
        Name = "JARVIS - Sniper 10 Cycles"
        Desc = "Focus tracking continu"
        Icon = "/Windows\System32\shell32.dll,176"  # Radar
    }
)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  JARVIS - Creation des raccourcis bureau" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$Created = 0
foreach ($s in $Shortcuts) {
    $BatPath = Join-Path $LaunchersDir $s.Bat
    if (-not (Test-Path $BatPath)) {
        Write-Host "  SKIP: $($s.Bat) non trouve" -ForegroundColor Yellow
        continue
    }

    $LnkPath = Join-Path $Desktop "$($s.Name).lnk"
    $Shortcut = $Shell.CreateShortcut($LnkPath)
    $Shortcut.TargetPath = $BatPath
    $Shortcut.WorkingDirectory = $LaunchersDir
    $Shortcut.Description = $s.Desc
    $Shortcut.IconLocation = $s.Icon
    $Shortcut.WindowStyle = 1  # Normal window
    $Shortcut.Save()

    Write-Host "  OK: $($s.Name)" -ForegroundColor Green
    $Created++
}

# Raccourci special: dossier JARVIS complet
$LnkAll = Join-Path $Desktop "JARVIS - Dossier Complet.lnk"
$ShortcutAll = $Shell.CreateShortcut($LnkAll)
$ShortcutAll.TargetPath = "/home/turbo\TRADING_V2_PRODUCTION"
$ShortcutAll.Description = "Dossier TRADING_V2_PRODUCTION complet"
$ShortcutAll.IconLocation = "/Windows\System32\shell32.dll,4"  # Folder
$ShortcutAll.Save()
$Created++
Write-Host "  OK: JARVIS - Dossier Complet" -ForegroundColor Green

Write-Host ""
Write-Host "  $Created raccourcis crees sur le bureau" -ForegroundColor Cyan
Write-Host "  Dossier: $Desktop" -ForegroundColor DarkGray
Write-Host ""
