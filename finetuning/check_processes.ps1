Get-Process python* -ErrorAction SilentlyContinue | ForEach-Object {
    $memMB = [math]::Round($_.WorkingSet64 / 1MB, 0)
    Write-Host "PID $($_.Id) | $($_.ProcessName) | $memMB MB"
}
