$p = Start-Process -FilePath "/Program Files\nodejs\node.exe" -ArgumentList "node_modules\vite\bin\vite.js" -WorkingDirectory "/home/turbo/jarvis-m1-ops\electron" -PassThru -WindowStyle Normal
Write-Output "PID: $($p.Id)"
Start-Sleep -Seconds 20
netstat -ano | Select-String "5173"
try {
    $r = Invoke-WebRequest -Uri "http://localhost:5173/" -UseBasicParsing -TimeoutSec 10
    Write-Output "HTTP: $($r.StatusCode)"
} catch {
    Write-Output "ERR: $($_.Exception.Message)"
}
