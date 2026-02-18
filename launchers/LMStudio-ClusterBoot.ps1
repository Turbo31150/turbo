# ═══════════════════════════════════════════════════════════════════════════
# JARVIS CLUSTER BOOT — LM Studio + Ollama Integration Windows
# Auto-start serveur, load modeles optimaux, warmup, benchmark
# ═══════════════════════════════════════════════════════════════════════════

param(
    [switch]$ServerOnly,
    [switch]$Status,
    [switch]$Stop,
    [switch]$Benchmark,
    [int]$Port = 1234
)

$ErrorActionPreference = "SilentlyContinue"

# ── GPU Priority — RTX 3080 (GPU5) en premier ────────────────────────────
$env:CUDA_VISIBLE_DEVICES = "5,0,1,2,3,4"

# ── Configuration ─────────────────────────────────────────────────────────
$LMS_PATH = "C:\Users\franc\.lmstudio\bin\lms.exe"
$LOG_FILE = "F:\BUREAU\turbo\logs\cluster_boot.log"

# M1 — Modele permanent au boot
$M1_MODEL = "qwen/qwen3-30b-a3b-2507"
$M1_GPU = "max"
$M1_CONTEXT = 32768    # 32K tokens (PAS 8192!)
$M1_PARALLEL = 4       # 4 requetes paralleles

# M2 — Remote
$M2_URL = "http://192.168.1.26:1234"

# Ollama
$OLLAMA_URL = "http://127.0.0.1:11434"

# Blacklist — NE JAMAIS charger ces modeles
$BLACKLIST = @("nvidia/nemotron-3-nano", "zai-org/glm-4.7-flash")

# ── Helpers ───────────────────────────────────────────────────────────────

function Write-Log {
    param([string]$Message, [string]$Level = "INFO", [string]$Color = "White")
    $timestamp = Get-Date -Format "HH:mm:ss"
    $line = "[$timestamp] [$Level] $Message"
    Write-Host $line -ForegroundColor $Color
    # Log to file
    $logDir = Split-Path $LOG_FILE -Parent
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    Add-Content -Path $LOG_FILE -Value $line -ErrorAction SilentlyContinue
}

function Test-Api {
    param([string]$Url, [int]$Timeout = 3)
    try {
        $r = Invoke-RestMethod -Uri "$Url" -TimeoutSec $Timeout -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Invoke-Warmup {
    param([string]$Url, [string]$Model, [string]$ApiKey)
    try {
        $warmupHeaders = @{}
        if ($ApiKey) { $warmupHeaders["Authorization"] = "Bearer $ApiKey" }
        $body = @{
            model = $Model
            input = "Reponds OK."
            temperature = 0.1
            max_output_tokens = 5
            stream = $false
            store = $false
        } | ConvertTo-Json -Depth 3
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $r = Invoke-RestMethod -Uri "$Url/api/v1/chat" -Method Post -ContentType "application/json" -Headers $warmupHeaders -Body $body -TimeoutSec 30
        $sw.Stop()
        $content = if ($r.output.Count -gt 0) { $r.output[0].content } else { "(vide)" }
        return @{ OK = $true; LatencyMs = $sw.ElapsedMilliseconds; Content = $content }
    } catch {
        return @{ OK = $false; LatencyMs = -1; Error = $_.Exception.Message }
    }
}

# ── Status Mode ───────────────────────────────────────────────────────────
if ($Status) {
    Write-Log "=== CLUSTER STATUS ===" "INFO" "Cyan"
    & $LMS_PATH ps
    Write-Host ""
    # M1
    if (Test-Api "http://10.5.0.2:${Port}/api/v1/models") {
        Write-Log "M1 (10.5.0.2:$Port): ONLINE" "OK" "Green"
    } else {
        Write-Log "M1 (10.5.0.2:$Port): OFFLINE" "WARN" "Red"
    }
    # M2
    if (Test-Api "$M2_URL/api/v1/models") {
        Write-Log "M2 (192.168.1.26:1234): ONLINE" "OK" "Green"
    } else {
        Write-Log "M2 (192.168.1.26:1234): OFFLINE" "WARN" "Yellow"
    }
    # Ollama
    if (Test-Api "$OLLAMA_URL/api/tags") {
        Write-Log "Ollama (127.0.0.1:11434): ONLINE" "OK" "Green"
    } else {
        Write-Log "Ollama (127.0.0.1:11434): OFFLINE" "WARN" "Yellow"
    }
    # GPU
    Write-Host ""
    Write-Log "GPU VRAM:" "INFO" "Cyan"
    nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader 2>$null | ForEach-Object {
        Write-Host "  $_" -ForegroundColor White
    }
    exit 0
}

# ── Stop Mode ─────────────────────────────────────────────────────────────
if ($Stop) {
    Write-Log "Arret du serveur LM Studio..." "INFO" "Yellow"
    & $LMS_PATH server stop
    Write-Log "Serveur arrete" "OK" "Green"
    exit 0
}

# ═══════════════════════════════════════════════════════════════════════════
# BOOT SEQUENCE
# ═══════════════════════════════════════════════════════════════════════════

Write-Host ""
Write-Host "  ══════════════════════════════════════════════════" -ForegroundColor Magenta
Write-Host "    JARVIS CLUSTER BOOT — LM Studio + Ollama" -ForegroundColor Magenta
Write-Host "  ══════════════════════════════════════════════════" -ForegroundColor Magenta
Write-Host ""

Add-Content -Path $LOG_FILE -Value "`n========== BOOT $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==========" -ErrorAction SilentlyContinue

# ── Step 1: Check LMS CLI ─────────────────────────────────────────────────
if (-not (Test-Path $LMS_PATH)) {
    Write-Log "LMS CLI introuvable: $LMS_PATH" "ERREUR" "Red"
    exit 1
}

# ── Step 2: Start server ──────────────────────────────────────────────────
Write-Log "Verification serveur LM Studio..." "INFO" "Cyan"
$serverStatus = & $LMS_PATH server status 2>&1 | Out-String
if ($serverStatus -match "not running" -or $serverStatus -match "error") {
    Write-Log "Demarrage serveur sur port $Port..." "INFO" "Yellow"
    & $LMS_PATH server start --port $Port 2>&1 | Out-Null
    # Wait for server to be ready
    $ready = $false
    for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep -Seconds 2
        if (Test-Api "http://10.5.0.2:${Port}/api/v1/models") {
            $ready = $true
            break
        }
    }
    if ($ready) {
        Write-Log "Serveur demarre sur port $Port" "OK" "Green"
    } else {
        Write-Log "Serveur ne repond pas apres 20s!" "ERREUR" "Red"
        exit 1
    }
} else {
    Write-Log "Serveur deja actif" "OK" "Green"
}

if ($ServerOnly) {
    Write-Log "Mode ServerOnly - arret" "INFO" "Yellow"
    exit 0
}

# ── Step 3: Unload blacklisted models ─────────────────────────────────────
Write-Log "Verification modeles charges..." "INFO" "Cyan"
$psOutput = & $LMS_PATH ps 2>&1 | Out-String
foreach ($bl in $BLACKLIST) {
    if ($psOutput -match [regex]::Escape($bl)) {
        Write-Log "Unload blackliste: $bl" "INFO" "Yellow"
        & $LMS_PATH unload $bl 2>&1 | Out-Null
    }
}

# ── Step 4: Load qwen3-30b (PERMANENT — no TTL) ──────────────────────────
Write-Log "Chargement $M1_MODEL..." "INFO" "Yellow"
$psAfter = & $LMS_PATH ps 2>&1 | Out-String
if ($psAfter -match [regex]::Escape($M1_MODEL)) {
    Write-Log "$M1_MODEL deja charge" "OK" "Green"
} else {
    Write-Log "GPU=$M1_GPU, ctx=$M1_CONTEXT, parallel=$M1_PARALLEL (PERMANENT, pas de TTL)" "INFO" "Cyan"

    # Attempt 1
    & $LMS_PATH load $M1_MODEL -y --gpu $M1_GPU -c $M1_CONTEXT --parallel $M1_PARALLEL 2>&1 | Out-Null
    Start-Sleep -Seconds 3

    # Verify
    $psCheck = & $LMS_PATH ps 2>&1 | Out-String
    if ($psCheck -match [regex]::Escape($M1_MODEL)) {
        Write-Log "$M1_MODEL charge avec succes" "OK" "Green"
    } else {
        # Attempt 2
        Write-Log "Retry chargement..." "WARN" "Yellow"
        Start-Sleep -Seconds 5
        & $LMS_PATH load $M1_MODEL -y --gpu $M1_GPU -c $M1_CONTEXT --parallel $M1_PARALLEL 2>&1 | Out-Null
        Start-Sleep -Seconds 5
        $psCheck2 = & $LMS_PATH ps 2>&1 | Out-String
        if ($psCheck2 -match [regex]::Escape($M1_MODEL)) {
            Write-Log "$M1_MODEL charge (2e tentative)" "OK" "Green"
        } else {
            Write-Log "ECHEC chargement $M1_MODEL" "ERREUR" "Red"
        }
    }
}

# ── Step 5: Warmup inference (pre-fill KV cache) ─────────────────────────
Write-Log "Warmup inference M1..." "INFO" "Cyan"
$warmup = Invoke-Warmup -Url "http://10.5.0.2:$Port" -Model $M1_MODEL
if ($warmup.OK) {
    Write-Log "Warmup OK — $($warmup.LatencyMs)ms — '$($warmup.Content)'" "OK" "Green"
} else {
    Write-Log "Warmup ECHEC: $($warmup.Error)" "WARN" "Yellow"
}

# ── Step 6: Check M2 ─────────────────────────────────────────────────────
Write-Log "Verification M2 ($M2_URL)..." "INFO" "Cyan"
if (Test-Api "$M2_URL/api/v1/models") {
    Write-Log "M2: ONLINE" "OK" "Green"
    if ($Benchmark) {
        $m2w = Invoke-Warmup -Url $M2_URL -Model "deepseek-coder-v2-lite-instruct"
        if ($m2w.OK) {
            Write-Log "M2 warmup: $($m2w.LatencyMs)ms" "OK" "Green"
        }
    }
} else {
    Write-Log "M2: OFFLINE (192.168.1.26 injoignable)" "WARN" "Yellow"
}

# ── Step 7: Check Ollama ──────────────────────────────────────────────────
Write-Log "Verification Ollama ($OLLAMA_URL)..." "INFO" "Cyan"
if (Test-Api "$OLLAMA_URL/api/tags") {
    try {
        $tags = Invoke-RestMethod -Uri "$OLLAMA_URL/api/tags" -TimeoutSec 3
        $models = ($tags.models | ForEach-Object { $_.name }) -join ", "
        Write-Log "Ollama: ONLINE ($models)" "OK" "Green"
    } catch {
        Write-Log "Ollama: ONLINE (erreur parsing)" "WARN" "Yellow"
    }
} else {
    Write-Log "Ollama: OFFLINE" "WARN" "Yellow"
}

# ── Step 8: GPU Stats ─────────────────────────────────────────────────────
Write-Host ""
Write-Log "GPU VRAM:" "INFO" "Cyan"
$gpuData = nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits 2>$null
if ($gpuData) {
    $totalUsed = 0
    $totalAvail = 0
    foreach ($line in $gpuData) {
        $parts = $line -split ","
        if ($parts.Count -ge 5) {
            $idx = $parts[0].Trim()
            $name = $parts[1].Trim()
            $used = [int]$parts[2].Trim()
            $total = [int]$parts[3].Trim()
            $util = $parts[4].Trim()
            $pct = [math]::Round($used / [math]::Max($total, 1) * 100)
            $bar = ("#" * [math]::Floor($pct / 5)) + ("." * (20 - [math]::Floor($pct / 5)))
            $totalUsed += $used
            $totalAvail += $total
            $color = "Green"
            if ($pct -gt 80) { $color = "Red" }
            elseif ($pct -gt 50) { $color = "Yellow" }
            Write-Host "  GPU$idx $($name.PadRight(22)) [$bar] ${used}MB/${total}MB (${pct}%)" -ForegroundColor $color
        }
    }
    $totalPct = [math]::Round($totalUsed / [math]::Max($totalAvail, 1) * 100)
    Write-Log "VRAM Total: ${totalUsed}MB / ${totalAvail}MB ($totalPct%)" "INFO" "Cyan"
}

# ── Final Report ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ══════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "    CLUSTER BOOT COMPLETE" -ForegroundColor Green
Write-Host "  ══════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Log "M1 API:  http://10.5.0.2:$Port/api/v1/chat" "INFO" "White"
Write-Log "M2 API:  $M2_URL/api/v1/chat" "INFO" "White"
Write-Log "Ollama:  $OLLAMA_URL/api/chat" "INFO" "White"
Write-Host ""
