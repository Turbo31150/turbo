# === Stop LM Studio ===
Write-Host "=== Arret LM Studio ==="
$lms = Get-Process "LM Studio" -ErrorAction SilentlyContinue
if ($lms) {
    Write-Host "  Killing $($lms.Count) LM Studio processes..."
    $lms | Stop-Process -Force
    Start-Sleep 2
} else {
    Write-Host "  LM Studio not running"
}

# === Stop Ollama ===
Write-Host "`n=== Arret Ollama ==="
$ollama = Get-Process ollama*, "ollama app" -ErrorAction SilentlyContinue
if ($ollama) {
    Write-Host "  Killing $($ollama.Count) Ollama processes..."
    $ollama | Stop-Process -Force
    Start-Sleep 2
} else {
    Write-Host "  Ollama not running"
}

# === Verify GPU is free ===
Write-Host "`n=== GPU VRAM apres nettoyage ==="
Start-Sleep 3
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader

# === System RAM ===
Write-Host "`n=== System RAM ==="
$os = Get-CimInstance Win32_OperatingSystem
$totalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
Write-Host "Total: $totalGB GB | Free: $freeGB GB"
