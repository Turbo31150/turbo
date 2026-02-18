Get-Process | Where-Object { $_.ProcessName -like '*LM*Studio*' } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$remaining = (Get-Process | Where-Object { $_.ProcessName -like '*LM*Studio*' }).Count
Write-Host "LM Studio remaining: $remaining"
