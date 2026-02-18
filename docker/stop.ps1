###############################################################################
# JARVIS Docker — Arret propre
###############################################################################

Write-Host "=== Arret JARVIS Docker Stack ===" -ForegroundColor Cyan
Set-Location "F:\BUREAU\turbo\docker"
docker compose down
Write-Host "[OK] Stack arretee" -ForegroundColor Green
