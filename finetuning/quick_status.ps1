$proc = Get-Process -Id 4296 -ErrorAction SilentlyContinue
if ($proc) {
    $memGB = [math]::Round($proc.WorkingSet64 / 1GB, 2)
    $cpuSec = [math]::Round($proc.CPU, 0)
    Write-Host "PID 4296: $memGB GB RAM, CPU: ${cpuSec}s, Running: $([math]::Round(((Get-Date) - $proc.StartTime).TotalMinutes, 1)) min"
} else {
    Write-Host "PID 4296: DEAD"
}

nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader 2>$null
