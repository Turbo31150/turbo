Set-Location "F:\BUREAU\turbo\electron"
$env:NODE_ENV = "development"
Start-Process -FilePath "npx" -ArgumentList "vite --port 5173 --host 127.0.0.1" -NoNewWindow -PassThru
Start-Sleep -Seconds 5
$env:VITE_DEV_SERVER_URL = "http://127.0.0.1:5173"
Start-Process -FilePath "npx" -ArgumentList "electron ." -NoNewWindow
