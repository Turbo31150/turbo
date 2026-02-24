$conns = Get-NetTCPConnection -LocalPort 9742 -ErrorAction SilentlyContinue
foreach ($c in $conns) {
    Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
}
Write-Host "Port 9742 freed"
