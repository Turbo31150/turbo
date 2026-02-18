Write-Host "=== Python Processes ==="
Get-Process python* -ErrorAction SilentlyContinue | ForEach-Object {
    $memGB = [math]::Round($_.WorkingSet64 / 1GB, 2)
    $cpuSec = [math]::Round($_.CPU, 0)
    Write-Host "PID $($_.Id) - $memGB GB RAM - CPU: ${cpuSec}s"
}

Write-Host "`n=== Output File ==="
$outFile = "C:\Users\franc\AppData\Local\Temp\claude\C--Users-franc\tasks\b7b9b99.output"
if (Test-Path $outFile) {
    $info = Get-Item $outFile
    Write-Host "Last modified: $($info.LastWriteTime)"
    Write-Host "Size: $([math]::Round($info.Length / 1KB, 1)) KB"
} else {
    Write-Host "Output file not found"
}

Write-Host "`n=== GPU VRAM ==="
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader
