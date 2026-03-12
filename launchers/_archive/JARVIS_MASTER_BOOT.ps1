# =============================================================================
# JARVIS MASTER BOOT v2.0 — Script unifie de demarrage complet
# Un seul terminal pour tout: cluster + services + verification + logs
#
# Usage:
#   .\JARVIS_MASTER_BOOT.ps1              # Boot complet
#   .\JARVIS_MASTER_BOOT.ps1 -StatusOnly  # Status sans demarrer
#   .\JARVIS_MASTER_BOOT.ps1 -SkipOpenClaw # Skip OpenClaw gateway
#   .\JARVIS_MASTER_BOOT.ps1 -Verify      # Verification multi-agent seulement
# =============================================================================

param(
    [switch]$StatusOnly,
    [switch]$SkipOpenClaw,
    [switch]$Verify,
    [switch]$FixCrons,
    [int]$Port = 1234
)

$ErrorActionPreference = "Continue"
$Host.UI.RawUI.WindowTitle = "JARVIS Master Boot v2.0"

# =============================================================================
# CONFIG
# =============================================================================
$TURBO = "/home/turbo/jarvis-m1-ops"
$HOME_DIR = $env:USERPROFILE
$OPENCLAW_DIR = "$HOME_DIR\.openclaw"
$LOG_DIR = "$TURBO\logs"
$LOG_FILE = "$LOG_DIR\master_boot_$(Get-Date -Format 'yyyy-MM-dd').log"
$LMS = "$HOME_DIR\.lmstudio\bin\lms.exe"
$UV = "$HOME_DIR\.local\bin\uv.exe"

# Cluster nodes
$NODES = @{
    "M1" = @{ url = "http://127.0.0.1:$Port"; ip = "127.0.0.1"; port = $Port }
    "M2" = @{ url = "http://192.168.1.26:1234"; ip = "192.168.1.26"; port = 1234 }
    "M3" = @{ url = "http://192.168.1.113:1234"; ip = "192.168.1.113"; port = 1234 }
}

# Services
$SERVICES = @{
    "Ollama"       = @{ port = 11434; host = "127.0.0.1" }
    "n8n"          = @{ port = 5678;  host = "127.0.0.1" }
    "OpenClaw"     = @{ port = 18789; host = "127.0.0.1" }
    "GeminiProxy"  = @{ port = 18791; host = "127.0.0.1" }
    "Dashboard"    = @{ port = 8080;  host = "127.0.0.1" }
    "CanvasProxy"  = @{ port = 18800; host = "127.0.0.1" }
    "JARVIS WS"    = @{ port = 9742;  host = "127.0.0.1" }
}

# =============================================================================
# HELPERS
# =============================================================================
function Write-Status {
    param([string]$Msg, [string]$Level = "INFO")
    $ts = Get-Date -Format "HH:mm:ss"
    $icons = @{ "OK" = "[OK]"; "INFO" = "[..]"; "WARN" = "[!!]"; "FAIL" = "[XX]"; "PHASE" = "[>>]"; "DIM" = "[--]" }
    $colors = @{ "OK" = "Green"; "INFO" = "Cyan"; "WARN" = "Yellow"; "FAIL" = "Red"; "PHASE" = "Magenta"; "DIM" = "DarkGray" }
    $icon = if ($icons[$Level]) { $icons[$Level] } else { "[..]" }
    $color = if ($colors[$Level]) { $colors[$Level] } else { "White" }
    Write-Host "$icon $Msg" -ForegroundColor $color
    if (-not (Test-Path $LOG_DIR)) { New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null }
    Add-Content -Path $LOG_FILE -Value "[$ts] [$Level] $Msg" -ErrorAction SilentlyContinue
}

function Test-Port {
    param([string]$Host_, [int]$Port_, [int]$Timeout = 3000)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $result = $tcp.BeginConnect($Host_, $Port_, $null, $null)
        $success = $result.AsyncWaitHandle.WaitOne($Timeout)
        $tcp.Close()
        return $success
    } catch { return $false }
}

function Wait-Port {
    param([string]$Host_, [int]$Port_, [int]$MaxWait = 30)
    for ($i = 0; $i -lt $MaxWait; $i += 2) {
        if (Test-Port $Host_ $Port_) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Invoke-M1Query {
    param([string]$Prompt, [int]$MaxTokens = 256)
    try {
        $body = @{
            model = "qwen3-8b"
            input = "/nothink`n$Prompt"
            temperature = 0.2
            max_output_tokens = $MaxTokens
            stream = $false
            store = $false
        } | ConvertTo-Json -Depth 3
        $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($body)
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/chat" -Method Post `
            -ContentType "application/json" -Body $bodyBytes -TimeoutSec 30
        # Extract last message block (skip reasoning)
        $result = ""
        foreach ($o in $r.output) {
            if ($o.type -eq "message") { $result = $o.content }
        }
        if ($result.Trim()) { return $result.Trim() }
        return "ERREUR: reponse vide"
    } catch { return "ERREUR: $($_.Exception.Message)" }
}

# =============================================================================
# PHASE 1: GPU + INFRASTRUCTURE
# =============================================================================
function Phase-1-Infrastructure {
    Write-Status "PHASE 1 - INFRASTRUCTURE (GPU + LM Studio + Ollama)" "PHASE"

    # GPU Status
    $gpuData = nvidia-smi --query-gpu=index,name,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits 2>$null
    if ($gpuData) {
        $maxTemp = 0
        foreach ($line in $gpuData) {
            $p = $line -split ","
            if ($p.Count -ge 5) {
                $idx = $p[0].Trim(); $name = $p[1].Trim()
                $used = [int]$p[2].Trim(); $total = [int]$p[3].Trim(); $temp = [int]$p[4].Trim()
                $pct = [math]::Round($used / [math]::Max($total, 1) * 100)
                $color = if ($temp -ge 80) { "Red" } elseif ($temp -ge 65) { "Yellow" } else { "Green" }
                Write-Host "  GPU$idx $($name.PadRight(25)) ${used}MB/${total}MB (${pct}%) ${temp}C" -ForegroundColor $color
                if ($temp -gt $maxTemp) { $maxTemp = $temp }
            }
        }
        if ($maxTemp -ge 85) { Write-Status "THERMAL CRITIQUE: ${maxTemp}C" "FAIL" }
        elseif ($maxTemp -ge 75) { Write-Status "Thermal warning: ${maxTemp}C" "WARN" }
        else { Write-Status "Thermal OK: ${maxTemp}C" "OK" }
    }

    # LM Studio M1
    if (Test-Port "127.0.0.1" $Port) {
        Write-Status "M1 LM Studio: actif sur :$Port" "OK"
    } else {
        Write-Status "M1 LM Studio: demarrage..." "INFO"
        & $LMS server start --port $Port 2>&1 | Out-Null
        if (Wait-Port "127.0.0.1" $Port 20) {
            Write-Status "M1 LM Studio: demarre" "OK"
        } else {
            Write-Status "M1 LM Studio: ECHEC demarrage" "FAIL"
        }
    }

    # Ollama
    if (Test-Port "127.0.0.1" 11434) {
        $tags = try { Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 } catch { $null }
        $count = if ($tags) { $tags.models.Count } else { "?" }
        Write-Status "Ollama: actif ($count modeles)" "OK"
    } else {
        Write-Status "Ollama: demarrage..." "INFO"
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
        if (Wait-Port "127.0.0.1" 11434 15) {
            Write-Status "Ollama: demarre" "OK"
        } else {
            Write-Status "Ollama: OFFLINE" "WARN"
        }
    }

    # M2/M3 (check only)
    foreach ($n in @("M2", "M3")) {
        $node = $NODES[$n]
        if (Test-Port $node.ip $node.port 3000) {
            Write-Status "$n ($($node.ip)): ONLINE" "OK"
        } else {
            Write-Status "$n ($($node.ip)): OFFLINE" "DIM"
        }
    }
}

# =============================================================================
# PHASE 2: MODELES
# =============================================================================
function Phase-2-Models {
    Write-Status "PHASE 2 - MODELES (load + warmup)" "PHASE"

    if (-not (Test-Port "127.0.0.1" $Port)) {
        Write-Status "M1 OFFLINE - skip" "WARN"
        return
    }

    # Check loaded models via API
    try {
        $models = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/models" -TimeoutSec 5
        $loaded = $models.data | Where-Object { $_.loaded_instances }
        if ($loaded) {
            foreach ($m in $loaded) {
                $id = $m.loaded_instances[0].id
                $ctx = $m.loaded_instances[0].config.context_length
                $ttl = $m.loaded_instances[0].remaining_ttl_seconds
                Write-Status "Modele charge: $id (ctx=$ctx, ttl=${ttl}s)" "OK"
            }
        } else {
            Write-Status "Aucun modele charge - chargement qwen3-8b..." "INFO"
            & $LMS load "qwen/qwen3-8b" -y --gpu max -c 32768 --parallel 4 2>&1 | Out-Null
            Start-Sleep -Seconds 5
            Write-Status "qwen3-8b charge" "OK"
        }
    } catch {
        Write-Status "Erreur API models: $_" "WARN"
    }

    # Warmup
    Write-Status "Warmup M1..." "INFO"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $warmup = Invoke-M1Query "Reponds OK." 5
    $sw.Stop()
    if ($warmup -and $warmup -notmatch "ERREUR") {
        Write-Status "Warmup OK - $($sw.ElapsedMilliseconds)ms" "OK"
    } else {
        Write-Status "Warmup ECHEC: $warmup" "WARN"
    }
}

# =============================================================================
# PHASE 3: SERVICES
# =============================================================================
function Phase-3-Services {
    Write-Status "PHASE 3 - SERVICES (n8n + proxies + dashboard)" "PHASE"

    # n8n
    if (Test-Port "127.0.0.1" 5678) {
        Write-Status "n8n: actif sur :5678" "OK"
    } else {
        Write-Status "n8n: OFFLINE (demarrer manuellement)" "DIM"
    }

    # Gemini Proxy
    $geminiProxy = "$TURBO\gemini-proxy.js"
    if (Test-Port "127.0.0.1" 18791) {
        Write-Status "Gemini Proxy: actif sur :18791" "OK"
    } elseif (Test-Path $geminiProxy) {
        Write-Status "Gemini Proxy: demarrage..." "INFO"
        Start-Process -FilePath "node" -ArgumentList $geminiProxy -WorkingDirectory $TURBO -WindowStyle Hidden
        if (Wait-Port "127.0.0.1" 18791 10) {
            Write-Status "Gemini Proxy: demarre" "OK"
        } else {
            Write-Status "Gemini Proxy: ECHEC" "WARN"
        }
    }

    # Dashboard
    if (Test-Port "127.0.0.1" 8080) {
        Write-Status "Dashboard: actif sur :8080" "OK"
    } else {
        Write-Status "Dashboard: OFFLINE" "DIM"
    }

    # OpenClaw
    if (-not $SkipOpenClaw) {
        if (Test-Port "127.0.0.1" 18789) {
            Write-Status "OpenClaw Gateway: actif sur :18789" "OK"
        } else {
            Write-Status "OpenClaw Gateway: OFFLINE" "DIM"
        }
    }
}

# =============================================================================
# PHASE 4: VERIFICATION MULTI-AGENT
# =============================================================================
function Phase-4-Verification {
    Write-Status "PHASE 4 - VERIFICATION MULTI-AGENT (cluster IA)" "PHASE"

    if (-not (Test-Port "127.0.0.1" $Port)) {
        Write-Status "M1 OFFLINE - verification impossible" "FAIL"
        return
    }

    # 4a. SQLite integrity
    Write-Status "Verification SQLite..." "INFO"
    $dbs = @{
        "etoile" = "$TURBO\data\etoile.db"
        "jarvis" = "$TURBO\data\jarvis.db"
        "sniper" = "$TURBO\data\sniper.db"
    }
    foreach ($dbName in $dbs.Keys) {
        $dbPath = $dbs[$dbName]
        if (Test-Path $dbPath) {
            try {
                $result = & sqlite3 $dbPath "PRAGMA integrity_check;" 2>$null
                $tables = & sqlite3 $dbPath "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>$null
                if ($result -eq "ok") {
                    Write-Status "  $dbName : OK ($tables tables)" "OK"
                } else {
                    Write-Status "  $dbName : CORRUPTION ($result)" "FAIL"
                }
            } catch {
                Write-Status "  $dbName : erreur check" "WARN"
            }
        } else {
            Write-Status "  $dbName : fichier absent" "DIM"
        }
    }

    # 4b. Verification IA via M1 cluster
    Write-Status "Audit IA via M1/qwen3-8b..." "INFO"

    $auditPrompt = @"
Tu es un auditeur systeme JARVIS. Analyse ce rapport et donne un score /100 + 3 actions prioritaires:
- M1: qwen3-8b ctx=28813, 25 tok/s, 100% uptime
- M2: deepseek-r1 ctx=27057, 16 tok/s, en ligne
- M3: OFFLINE
- Cloud Ollama: minimax/glm-5/kimi (3 modeles restants)
- OpenClaw: 2436 rate limits, 147 context overflow, 361 gateway timeout en 1 jour
- 563 crons total, 165 actifs, 6 haute frequence (<15min)
- GPU: 6 cartes, max 59C, pas de throttling
Reponds en format structure court.
"@

    $auditResult = Invoke-M1Query $auditPrompt 512
    if ($auditResult -and $auditResult -notmatch "^ERREUR") {
        Write-Host ""
        Write-Host "  --- AUDIT IA (M1/qwen3-8b) ---" -ForegroundColor Cyan
        $auditResult -split "`n" | ForEach-Object { Write-Host "  $_" -ForegroundColor White }
        Write-Host "  --- FIN AUDIT ---" -ForegroundColor Cyan
        Write-Host ""
    } else {
        Write-Status "Audit IA echec" "WARN"
    }

    # 4c. Check OpenClaw log health
    $ocLog = "$env:TEMP\openclaw\openclaw-$(Get-Date -Format 'yyyy-MM-dd').log"
    if (Test-Path $ocLog) {
        $content = Get-Content $ocLog -Raw -ErrorAction SilentlyContinue
        $rateLimits = ([regex]::Matches($content, "rate limit")).Count
        $ctxExceeded = ([regex]::Matches($content, "Context size")).Count
        $gwTimeout = ([regex]::Matches($content, "gateway timeout")).Count
        Write-Status "OpenClaw Logs: $rateLimits rate-limits, $ctxExceeded ctx-overflow, $gwTimeout gw-timeout" $(if ($rateLimits -gt 100) { "WARN" } else { "OK" })
    }

    # 4d. Git status check
    if (Test-Path "$TURBO\.git") {
        $gitStatus = git -C $TURBO status --porcelain 2>$null
        $changedFiles = ($gitStatus | Measure-Object).Count
        Write-Status "Git: $changedFiles fichiers modifies" $(if ($changedFiles -gt 20) { "WARN" } else { "OK" })
    }

    # 4e. Disk check
    foreach ($drive in @("/", "F:\")) {
        try {
            $disk = Get-PSDrive -Name $drive[0] 2>$null
            if ($disk) {
                $freeGB = [math]::Round($disk.Free / 1GB, 1)
                $level = if ($freeGB -lt 20) { "WARN" } else { "OK" }
                Write-Status "Disque $drive : ${freeGB}GB libre" $level
            }
        } catch {}
    }
}

# =============================================================================
# PHASE 5: TELEGRAM HISTORY
# =============================================================================
function Phase-5-TelegramHistory {
    Write-Status "PHASE 5 - TELEGRAM HISTORY (messages recents)" "PHASE"

    $sessionsDir = "$OPENCLAW_DIR\agents\main\sessions"
    if (-not (Test-Path $sessionsDir)) {
        Write-Status "Dossier sessions absent" "DIM"
        return
    }

    # Use Python to parse sessions (faster than PS for JSONL)
    $pyScript = @"
import json, os
from pathlib import Path
from datetime import datetime

sessions_dir = Path(r'$sessionsDir')
telegram_msgs = []

for f in sorted(sessions_dir.glob('*.jsonl'), key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
    try:
        for line in f.read_text(encoding='utf-8', errors='replace').splitlines():
            if not line.strip():
                continue
            entry = json.loads(line.strip())
            if entry.get('type') == 'message':
                msg = entry.get('message', {})
                if isinstance(msg, dict):
                    role = msg.get('role', '?')
                    content = msg.get('content', '')
                elif isinstance(msg, str):
                    role = '?'
                    content = msg
                else:
                    continue

                # Check if content has text blocks
                if isinstance(content, list):
                    texts = [c.get('text', '')[:100] for c in content if isinstance(c, dict) and c.get('type') == 'text']
                    content = ' '.join(texts)

                ts = entry.get('timestamp', '')
                raw = json.dumps(entry)
                is_telegram = 'telegram' in raw.lower()

                if content and len(str(content).strip()) > 5 and role in ('user', 'assistant'):
                    telegram_msgs.append({
                        'ts': ts[:19] if ts else '?',
                        'role': role,
                        'telegram': is_telegram,
                        'preview': str(content)[:100].replace('\n', ' ')
                    })
    except Exception:
        pass

# Show recent messages
print(f'Messages trouves: {len(telegram_msgs)}')
tg = [m for m in telegram_msgs if m['telegram']]
print(f'Messages Telegram: {len(tg)}')
print()
for m in tg[:15]:
    icon = 'USR' if m['role'] == 'user' else 'BOT'
    print(f"  [{m['ts']}] [{icon}] {m['preview']}")
"@

    $env:PYTHONIOENCODING = "utf-8"
    $result = $pyScript | python3 2>&1
    $result | ForEach-Object { Write-Host "  $_" -ForegroundColor White }
}

# =============================================================================
# FINAL REPORT
# =============================================================================
function Show-FinalReport {
    param([double]$Duration)

    Write-Host ""
    Write-Host "  ================================================================" -ForegroundColor Green
    Write-Host "    JARVIS MASTER BOOT COMPLETE" -ForegroundColor Green
    Write-Host "    $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | Duree: $([math]::Round($Duration, 1))s" -ForegroundColor Green
    Write-Host "  ================================================================" -ForegroundColor Green
    Write-Host ""

    # Quick status table
    Write-Host "  SERVICE                PORT    STATUS" -ForegroundColor Cyan
    Write-Host "  ----------------------------------------" -ForegroundColor DarkGray
    foreach ($svc in $SERVICES.Keys | Sort-Object) {
        $s = $SERVICES[$svc]
        $online = Test-Port $s.host $s.port 1000
        $status = if ($online) { "OK" } else { "OFFLINE" }
        $color = if ($online) { "Green" } else { "Red" }
        Write-Host "  $($svc.PadRight(22)) :$($s.port.ToString().PadRight(7)) " -NoNewline
        Write-Host $status -ForegroundColor $color
    }

    Write-Host ""
    Write-Host "  CLUSTER NODES" -ForegroundColor Cyan
    Write-Host "  ----------------------------------------" -ForegroundColor DarkGray
    foreach ($n in $NODES.Keys | Sort-Object) {
        $node = $NODES[$n]
        $online = Test-Port $node.ip $node.port 1000
        $status = if ($online) { "ONLINE" } else { "OFFLINE" }
        $color = if ($online) { "Green" } else { "Red" }
        Write-Host "  $($n.PadRight(8)) $($node.ip.PadRight(18)) " -NoNewline
        Write-Host $status -ForegroundColor $color
    }

    Write-Host ""
    Write-Host "  Log: $LOG_FILE" -ForegroundColor DarkGray
    Write-Host ""
}

# =============================================================================
# MAIN
# =============================================================================
$sw = [System.Diagnostics.Stopwatch]::StartNew()

# Enable ANSI
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ""
Write-Host "  ================================================================" -ForegroundColor Magenta
Write-Host "    JARVIS MASTER BOOT v2.0" -ForegroundColor Magenta
Write-Host "    $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Magenta
Write-Host "  ================================================================" -ForegroundColor Magenta
Write-Host ""

Add-Content -Path $LOG_FILE -Value "`n========== MASTER BOOT $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==========" -ErrorAction SilentlyContinue

if ($StatusOnly) {
    Phase-4-Verification
    Show-FinalReport $sw.Elapsed.TotalSeconds
    exit 0
}

if ($Verify) {
    Phase-4-Verification
    Phase-5-TelegramHistory
    exit 0
}

# Full boot sequence
Phase-1-Infrastructure
Phase-2-Models
Phase-3-Services

# Phase 3.5 - Python services (WS backend, Telegram, WhisperFlow)
Log "CYAN" "`n=== PHASE 3.5 - Python Services (unified boot) ==="
$unifiedBoot = "$TURBO\scripts\jarvis_unified_boot.py"
if (Test-Path $unifiedBoot) {
    Log "WHITE" "  Lancement services Python via jarvis_unified_boot.py..."
    try {
        $proc = Start-Process -FilePath "python" -ArgumentList "`"$unifiedBoot`" --phase 4" -WorkingDirectory $TURBO -PassThru -NoNewWindow
        Log "GREEN" "  Python services lances (PID: $($proc.Id))"
    } catch {
        Log "YELLOW" "  WARN: Impossible de lancer jarvis_unified_boot.py: $_"
    }
} else {
    Log "YELLOW" "  WARN: $unifiedBoot introuvable"
}

Phase-4-Verification
Phase-5-TelegramHistory

$sw.Stop()
Show-FinalReport $sw.Elapsed.TotalSeconds
