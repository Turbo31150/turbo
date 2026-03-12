# claude_desktop_dispatch.ps1 — Automatise Claude Desktop pour envoyer des prompts multi-taches
# Usage: powershell -File claude_desktop_dispatch.ps1 -Prompts "prompt1","prompt2","prompt3"
#        powershell -File claude_desktop_dispatch.ps1 -File "tasks.txt" -DelaySeconds 10

param(
    [string[]]$Prompts = @(),
    [string]$File = "",
    [int]$DelaySeconds = 8,
    [switch]$DryRun,
    [switch]$Sequential
)

Add-Type -AssemblyName System.Windows.Forms

$ErrorActionPreference = "Stop"

# --- Win32 API pour focus fenetre ---
$win32Code = @'
using System;
using System.Runtime.InteropServices;
public class Win32Focus {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
}
'@
try { Add-Type -TypeDefinition $win32Code -ErrorAction SilentlyContinue } catch {}

function Write-Status($msg, $color) {
    if (-not $color) { $color = "Cyan" }
    Write-Host "[DISPATCH] " -ForegroundColor Yellow -NoNewline
    Write-Host $msg -ForegroundColor $color
}

function Get-ClaudeWindow {
    # Cherche specifiquement Claude Desktop (Electron/Store), PAS Claude Code (terminal)
    $procs = Get-Process claude* | Where-Object {
        $_.MainWindowTitle -eq "Claude" -and $_.MainWindowHandle -ne 0
    } | Where-Object {
        try {
            $path = $_.MainModule.FileName
            # Accepter: WindowsApps (Store), ClaudeDesktopPatched, Programs\Claude
            # Rejeter: claude-cli, node, claude.exe dans .local (Claude Code)
            $path -match "WindowsApps|ClaudeDesktop|Programs.Claude" -and $path -notmatch "cli|node|\.local"
        } catch { $true }
    }
    if (-not $procs) {
        Write-Status "Claude Desktop non detecte. Lancement..." "Yellow"
        $claudePath = "$env:LOCALAPPDATA\ClaudeDesktopPatched\claude.exe"
        if (-not (Test-Path $claudePath)) {
            $claudePath = "$env:LOCALAPPDATA\Programs\Claude\claude.exe"
        }
        if (Test-Path $claudePath) {
            Start-Process $claudePath
            Start-Sleep -Seconds 5
            $procs = Get-Process claude* | Where-Object {
                $_.MainWindowTitle -eq "Claude" -and $_.MainWindowHandle -ne 0
            }
        }
    }
    $selected = $procs | Select-Object -First 1
    if ($selected) {
        $pid_ = $selected.Id
        Write-Status "Claude Desktop detecte (PID $pid_)" "DarkCyan"
    }
    return $selected
}

function Send-PromptToClaudeDesktop($Prompt) {
    $claude = Get-ClaudeWindow
    if (-not $claude) {
        Write-Status "ERREUR: Claude Desktop introuvable" "Red"
        return $false
    }

    $hwnd = $claude.MainWindowHandle

    # Restore si minimise
    if ([Win32Focus]::IsIconic($hwnd)) {
        [Win32Focus]::ShowWindow($hwnd, 9) | Out-Null
        Start-Sleep -Milliseconds 500
    }

    [Win32Focus]::SetForegroundWindow($hwnd) | Out-Null
    Start-Sleep -Milliseconds 800

    # Copie le prompt dans le clipboard
    [System.Windows.Forms.Clipboard]::SetText($Prompt)
    Start-Sleep -Milliseconds 300

    # Ctrl+V pour coller puis Enter pour envoyer
    [System.Windows.Forms.SendKeys]::SendWait("^v")
    Start-Sleep -Milliseconds 500
    [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")

    $pLen = $Prompt.Length
    Write-Status "Prompt envoye ($pLen chars)" "Green"
    return $true
}

function New-Conversation {
    $claude = Get-ClaudeWindow
    if (-not $claude) { return $false }

    $hwnd = $claude.MainWindowHandle
    [Win32Focus]::SetForegroundWindow($hwnd) | Out-Null
    Start-Sleep -Milliseconds 500

    # Alt+Shift+N pour nouvelle conversation dans Claude Desktop Store
    # (Ctrl+N ouvre d'autres apps comme Ollama)
    [System.Windows.Forms.SendKeys]::SendWait("+^n")
    Start-Sleep -Seconds 1
    # Fallback: clic sur le bouton + en haut gauche (coordonnees sidebar)
    # Si le raccourci ne marche pas, on envoie la tache dans la meme conversation
    return $true
}

# --- MAIN ---

Write-Host ""
Write-Host "========================================" -ForegroundColor Magenta
Write-Host "  CLAUDE DESKTOP MULTI-TASK DISPATCHER" -ForegroundColor Magenta
Write-Host "  JARVIS Turbo v10.6" -ForegroundColor DarkMagenta
Write-Host "========================================" -ForegroundColor Magenta
Write-Host ""

# Charger les prompts depuis un fichier si specifie
if ($File -and (Test-Path $File)) {
    $Prompts = Get-Content $File | Where-Object { $_.Trim() -ne "" -and -not $_.StartsWith("#") }
    Write-Status "Charge $($Prompts.Count) taches depuis $File"
}

if ($Prompts.Count -eq 0) {
    Write-Status "Aucun prompt fourni. Usage:" "Yellow"
    Write-Host '  -Prompts "task1","task2"' -ForegroundColor Gray
    Write-Host '  -File "tasks.txt"' -ForegroundColor Gray
    exit 1
}

Write-Status "$($Prompts.Count) tache(s) a dispatcher" "White"
Write-Host ""

if ($DryRun) {
    Write-Status "MODE DRY RUN - rien ne sera envoye" "Yellow"
    for ($i = 0; $i -lt $Prompts.Count; $i++) {
        $p = $Prompts[$i]
        if ($p.Length -gt 80) { $preview = $p.Substring(0, 80) + "..." } else { $preview = $p }
        Write-Host "  [$($i+1)] $preview" -ForegroundColor Gray
    }
    exit 0
}

$success = 0
$fail = 0

for ($i = 0; $i -lt $Prompts.Count; $i++) {
    $prompt = $Prompts[$i]
    if ($prompt.Length -gt 60) { $preview = $prompt.Substring(0, 60) + "..." } else { $preview = $prompt }

    Write-Host ""
    Write-Status "Tache $($i+1)/$($Prompts.Count): $preview" "White"

    if ($i -gt 0 -and (-not $Sequential)) {
        Write-Status "Nouvelle conversation..." "DarkCyan"
        New-Conversation | Out-Null
    }

    $result = Send-PromptToClaudeDesktop $prompt
    if ($result) { $success++ } else { $fail++ }

    if ($i -lt ($Prompts.Count - 1)) {
        Write-Status "Attente ${DelaySeconds}s avant prochaine tache..." "DarkGray"
        Start-Sleep -Seconds $DelaySeconds
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Magenta
$totalCount = $Prompts.Count
if ($fail -eq 0) { $statusColor = "Green" } else { $statusColor = "Yellow" }
Write-Status "TERMINE: $success OK / $fail FAIL sur $totalCount taches" $statusColor
Write-Host "========================================" -ForegroundColor Magenta
