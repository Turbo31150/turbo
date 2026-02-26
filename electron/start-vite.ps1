$p = Start-Process -FilePath "C:\Program Files\nodejs\node.exe" -ArgumentList "node_modules\vite\bin\vite.js" -WorkingDirectory "F:\BUREAU\turbo\electron" -PassThru -WindowStyle Normal
Write-Output "PID: $($p.Id)"
Start-Sleep -Seconds 20
netstat -ano | Select-String "5173"
try {
    $r = Invoke-WebRequest -Uri "http://localhost:5173/" -UseBasicParsing -TimeoutSec 10
    Write-Output "HTTP: $($r.StatusCode)"
} catch {
    Write-Output "ERR: $($_.Exception.Message)"
}
