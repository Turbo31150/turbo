# Deep cleanup - kill all Python and GPU-using processes
Write-Host "=== Deep GPU Cleanup ==="

# Kill all python processes
$procs = Get-Process python*, uv -ErrorAction SilentlyContinue
foreach ($p in $procs) {
    Write-Host "Killing $($p.ProcessName) PID $($p.Id)"
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
}

Start-Sleep 3

# Check what's using GPU
Write-Host "`n=== GPU compute processes ==="
$gpuProcs = nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader 2>&1
Write-Host $gpuProcs

Write-Host "`n=== GPU memory after cleanup ==="
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader

Write-Host "`n=== RAM ==="
$os = Get-CimInstance Win32_OperatingSystem
$freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
Write-Host "Free: $freeGB GB"
