###############################################################################
# JARVIS Docker — Demarrage rapide
# Lance Open WebUI + GPU Monitor
###############################################################################

$ErrorActionPreference = "Continue"

Write-Host "=== JARVIS Docker Stack ===" -ForegroundColor Cyan

# Verifier Docker
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Host "[ERREUR] Docker non installe. Lancez install_docker.ps1 d'abord." -ForegroundColor Red
    exit 1
}

# Verifier Docker Desktop est lance
$dockerDesktop = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $dockerDesktop) {
    Write-Host "[...] Lancement Docker Desktop..." -ForegroundColor Yellow
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    Write-Host "  Attente du demarrage Docker (30s)..."
    Start-Sleep 30
}

# Verifier que le daemon Docker repond
$maxRetries = 10
for ($i = 1; $i -le $maxRetries; $i++) {
    $info = docker info 2>&1
    if ($LASTEXITCODE -eq 0) { break }
    Write-Host "  Docker pas encore pret... ($i/$maxRetries)"
    Start-Sleep 5
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERREUR] Docker daemon ne repond pas apres ${maxRetries} tentatives" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Docker pret" -ForegroundColor Green

# S'assurer que LM Studio et Ollama sont accessibles
$lmStudio = Test-NetConnection -ComputerName 10.5.0.2 -Port 1234 -InformationLevel Quiet -WarningAction SilentlyContinue
$ollama = Test-NetConnection -ComputerName 127.0.0.1 -Port 11434 -InformationLevel Quiet -WarningAction SilentlyContinue

if ($lmStudio) { Write-Host "[OK] LM Studio accessible (10.5.0.2:1234)" -ForegroundColor Green }
else { Write-Host "[!] LM Studio non accessible (10.5.0.2:1234)" -ForegroundColor Yellow }

if ($ollama) { Write-Host "[OK] Ollama accessible (127.0.0.1:11434)" -ForegroundColor Green }
else { Write-Host "[!] Ollama non accessible (127.0.0.1:11434)" -ForegroundColor Yellow }

# Lancer la stack
Write-Host "`n[...] Lancement de la stack Docker..." -ForegroundColor Cyan
Set-Location "F:\BUREAU\turbo\docker"
docker compose up -d

# Afficher les URLs
Write-Host ""
$localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch "Loopback" -and $_.PrefixOrigin -eq "Dhcp" } | Select-Object -First 1).IPAddress

Write-Host "=== JARVIS WebUI ===" -ForegroundColor Green
Write-Host "  PC:       http://localhost:3000"
if ($localIP) {
    Write-Host "  Mobile:   http://${localIP}:3000"
}
Write-Host ""
Write-Host "  Logs:     docker compose logs -f open-webui"
Write-Host "  GPU Mon:  docker logs -f jarvis-gpu-monitor"
Write-Host "  Arreter:  docker compose down"
