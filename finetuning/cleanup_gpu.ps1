# Kill all Python processes to free leaked CUDA memory
$procs = Get-Process python* -ErrorAction SilentlyContinue
if ($procs) {
    foreach ($p in $procs) {
        $memMB = [math]::Round($p.WorkingSet64 / 1MB, 1)
        Write-Host "Killing PID $($p.Id) ($memMB MB)"
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep 2
} else {
    Write-Host "No Python processes"
}

Write-Host "`n=== GPU after cleanup ==="
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader

Write-Host "`n=== System RAM ==="
$os = Get-CimInstance Win32_OperatingSystem
$totalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
Write-Host "Total: $totalGB GB | Free: $freeGB GB"
