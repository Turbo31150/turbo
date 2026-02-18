###############################################################################
# JARVIS Docker Setup — Installation complete
# Config: Windows 11 + 5 GPU NVIDIA + WSL2
# Stockage Docker: F:\Docker
###############################################################################

param(
    [switch]$SkipDockerInstall,
    [switch]$SkipWSL,
    [string]$DockerDataRoot = "F:\Docker"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [!] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "  [X] $msg" -ForegroundColor Red }

# === Verification admin ===
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Err "Ce script doit etre lance en Administrateur !"
    Write-Host "  Clic droit > Executer en tant qu'administrateur"
    exit 1
}

# === 1. Verifier les pre-requis ===
Write-Step "1. Verification des pre-requis"

# NVIDIA Driver
$nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($nvidiaSmi) {
    $driverVer = (nvidia-smi --query-gpu=driver_version --format=csv,noheader | Select-Object -First 1).Trim()
    Write-OK "NVIDIA Driver: $driverVer"

    # Lister les GPUs
    nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader | ForEach-Object {
        $parts = $_ -split ','
        $idx = $parts[0].Trim()
        $name = $parts[1].Trim()
        $mem = $parts[2].Trim()
        Write-Host "    GPU $idx : $name ($mem)"
    }
} else {
    Write-Err "NVIDIA Driver non installe ! Installez-le d'abord."
    Write-Host "  https://www.nvidia.com/Download/index.aspx"
    exit 1
}

# Windows version
$build = [Environment]::OSVersion.Version.Build
if ($build -ge 19041) {
    Write-OK "Windows Build: $build (WSL2 compatible)"
} else {
    Write-Err "Windows Build $build trop ancien. Besoin >= 19041 pour WSL2."
    exit 1
}

# === 2. Installer WSL2 ===
if (-not $SkipWSL) {
    Write-Step "2. Configuration WSL2"

    $wslStatus = wsl --status 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-OK "WSL2 deja installe"
    } else {
        Write-Host "  Installation de WSL2..."
        wsl --install --no-distribution
        Write-Warn "Redemarrage peut etre necessaire apres l'installation WSL2"
    }

    # S'assurer que WSL2 est la version par defaut
    wsl --set-default-version 2 2>$null
    Write-OK "WSL2 defini comme version par defaut"
}

# === 3. Installer Docker Desktop ===
if (-not $SkipDockerInstall) {
    Write-Step "3. Installation Docker Desktop"

    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($docker) {
        $dockerVer = (docker --version 2>&1).ToString()
        Write-OK "Docker deja installe: $dockerVer"
    } else {
        Write-Host "  Telechargement Docker Desktop..."
        $installerUrl = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
        $installerPath = "$env:TEMP\DockerDesktopInstaller.exe"

        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
        Write-OK "Telechargement termine"

        Write-Host "  Installation Docker Desktop (peut prendre quelques minutes)..."
        Start-Process -FilePath $installerPath -ArgumentList "install", "--quiet", "--accept-license" -Wait

        # Rafraichir le PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

        Write-OK "Docker Desktop installe"
        Write-Warn "Vous devrez peut-etre vous deconnecter/reconnecter ou redemarrer"
    }
}

# === 4. Configurer Docker pour utiliser F:\ ===
Write-Step "4. Configuration stockage Docker sur F:\"

$dockerConfigDir = "$env:USERPROFILE\.docker"
$dockerConfigFile = "$dockerConfigDir\daemon.json"

if (-not (Test-Path $dockerConfigDir)) {
    New-Item -ItemType Directory -Path $dockerConfigDir -Force | Out-Null
}

# Creer le dossier data sur F:\
if (-not (Test-Path $DockerDataRoot)) {
    New-Item -ItemType Directory -Path $DockerDataRoot -Force | Out-Null
    Write-OK "Dossier Docker cree: $DockerDataRoot"
}

$daemonConfig = @{
    "data-root" = $DockerDataRoot.Replace("\", "/")
    "default-runtime" = "nvidia"
    "runtimes" = @{
        "nvidia" = @{
            "path" = "nvidia-container-runtime"
            "runtimeArgs" = @()
        }
    }
    "storage-driver" = "overlay2"
    "log-driver" = "json-file"
    "log-opts" = @{
        "max-size" = "10m"
        "max-file" = "3"
    }
} | ConvertTo-Json -Depth 5

Set-Content -Path $dockerConfigFile -Value $daemonConfig -Encoding UTF8
Write-OK "daemon.json configure (data-root: $DockerDataRoot)"

# === 5. Configurer le pare-feu pour acces reseau local ===
Write-Step "5. Regles pare-feu pour acces reseau"

# Open WebUI (port 3000)
$rule3000 = Get-NetFirewallRule -DisplayName "JARVIS WebUI" -ErrorAction SilentlyContinue
if (-not $rule3000) {
    New-NetFirewallRule -DisplayName "JARVIS WebUI" -Direction Inbound -Protocol TCP -LocalPort 3000 -Action Allow -Profile Private | Out-Null
    Write-OK "Regle pare-feu ajoutee: port 3000 (Open WebUI)"
} else {
    Write-OK "Regle pare-feu port 3000 deja presente"
}

# LM Studio (port 1234) — pour acces depuis d'autres machines
$rule1234 = Get-NetFirewallRule -DisplayName "JARVIS LM Studio" -ErrorAction SilentlyContinue
if (-not $rule1234) {
    New-NetFirewallRule -DisplayName "JARVIS LM Studio" -Direction Inbound -Protocol TCP -LocalPort 1234 -Action Allow -Profile Private | Out-Null
    Write-OK "Regle pare-feu ajoutee: port 1234 (LM Studio)"
} else {
    Write-OK "Regle pare-feu port 1234 deja presente"
}

# Ollama (port 11434)
$rule11434 = Get-NetFirewallRule -DisplayName "JARVIS Ollama" -ErrorAction SilentlyContinue
if (-not $rule11434) {
    New-NetFirewallRule -DisplayName "JARVIS Ollama" -Direction Inbound -Protocol TCP -LocalPort 11434 -Action Allow -Profile Private | Out-Null
    Write-OK "Regle pare-feu ajoutee: port 11434 (Ollama)"
} else {
    Write-OK "Regle pare-feu port 11434 deja presente"
}

# === 6. Creer les alias et raccourcis ===
Write-Step "6. Alias et commandes utiles"

# Creer le dossier data pour Open WebUI
$dataDir = "F:\BUREAU\turbo\docker\data\open-webui"
if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
    Write-OK "Dossier data cree: $dataDir"
}

# === 7. Afficher le resume ===
Write-Step "7. Resume de l'installation"

# Obtenir l'IP locale
$localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch "Loopback" -and $_.PrefixOrigin -eq "Dhcp" } | Select-Object -First 1).IPAddress
if (-not $localIP) {
    $localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch "Loopback" } | Select-Object -First 1).IPAddress
}

Write-Host ""
Write-Host "Installation terminee !" -ForegroundColor Green
Write-Host ""
Write-Host "Prochaines etapes:" -ForegroundColor Cyan
Write-Host "  1. Redemarrez Docker Desktop s'il n'est pas deja lance"
Write-Host "  2. Verifiez que le backend WSL2 est actif dans Docker Desktop > Settings > General"
Write-Host "  3. Lancez la stack JARVIS:"
Write-Host "     cd F:\BUREAU\turbo\docker" -ForegroundColor Yellow
Write-Host "     docker compose up -d" -ForegroundColor Yellow
Write-Host ""
Write-Host "Acces:" -ForegroundColor Cyan
Write-Host "  Local:  http://localhost:3000"
Write-Host "  Reseau: http://${localIP}:3000  (depuis telephone/tablette)"
Write-Host ""
Write-Host "Commandes utiles:" -ForegroundColor Cyan
Write-Host "  docker compose logs -f open-webui   # Voir les logs"
Write-Host "  docker compose down                  # Arreter"
Write-Host "  docker compose up -d                 # Demarrer"
Write-Host "  docker compose restart               # Redemarrer"
Write-Host ""
Write-Host "Monitoring GPU:" -ForegroundColor Cyan
Write-Host "  docker logs -f jarvis-gpu-monitor    # Dashboard GPU temps reel"
Write-Host "  nvidia-smi -l 2                      # Rafraichissement 2s natif"
Write-Host ""

# === GPU Priority Note ===
Write-Host "Note GPU:" -ForegroundColor Yellow
Write-Host "  La RTX 3080 (GPU 5 physique) est le GPU moniteur."
Write-Host "  Pour la prioriser comme GPU principal dans Docker:"
Write-Host "  Utilisez NVIDIA_VISIBLE_DEVICES dans docker-compose.yml"
Write-Host "  L'ordre actuel : RTX 2060 (12GB) > RTX 3080 (10GB) > 3x GTX 1660S (6GB)"
Write-Host ""
Write-Host "  IMPORTANT: Les GTX 1660 Super n'ont PAS de Tensor Cores."
Write-Host "  Flash Attention 2 est desactive pour ces GPUs."
Write-Host "  Format GGUF recommande pour exploiter ce mix de generations."
