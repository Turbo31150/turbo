Get-Process -Name 'electron*' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$conns = Get-NetTCPConnection -LocalPort 9742 -ErrorAction SilentlyContinue
foreach ($c in $conns) {
    Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
}
$conns5173 = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
foreach ($c in $conns5173) {
    Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
}
Write-Host "All JARVIS Desktop processes cleaned"
