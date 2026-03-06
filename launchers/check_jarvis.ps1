# Check for running JARVIS/Python processes
Write-Host "=== Processus Python ==="
Get-Process python*, uv -ErrorAction SilentlyContinue |
    Select-Object Id, ProcessName, MainWindowTitle, StartTime |
    Format-Table -AutoSize

Write-Host "`n=== Fenetres avec 'jarvis' ou 'turbo' ou 'train' ==="
Get-Process | Where-Object { $_.MainWindowTitle -match 'jarvis|turbo|train|hybrid' } |
    Select-Object Id, ProcessName, MainWindowTitle |
    Format-Table -AutoSize
