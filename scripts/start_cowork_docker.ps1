# ═══════════════════════════════════════════════════════════════
# JARVIS Cowork Docker — Auto-Start Script
# Scheduled Task: runs at Windows startup
# ═══════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$TURBO = 'F:\BUREAU\turbo'
$COMPOSE_FILE = Join-Path $TURBO 'projects\linux\docker-compose.cowork.yml'
$LOG = Join-Path $TURBO 'logs\cowork-docker.log'

# Ensure log directory
New-Item -ItemType Directory -Force -Path "$TURBO\logs" | Out-Null

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts | $msg" | Tee-Object -Append -FilePath $LOG
}

# Wait for Docker Desktop
Log "Waiting for Docker Desktop..."
$maxWait = 120
$waited = 0
while ($waited -lt $maxWait) {
    $dockerOk = docker info 2>$null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 5
    $waited += 5
}

if ($waited -ge $maxWait) {
    Log "ERROR: Docker Desktop not ready after ${maxWait}s"
    exit 1
}
Log "Docker Desktop ready"

# Deploy patterns if needed
Log "Checking COWORK patterns in etoile.db..."
$patternCount = python -c "import sqlite3; db=sqlite3.connect('$TURBO/etoile.db'); print(db.execute(`"SELECT COUNT(*) FROM agent_patterns WHERE pattern_id LIKE 'PAT_CW_%'`").fetchone()[0]); db.close()" 2>$null
if ($patternCount -eq "0") {
    Log "Deploying 30 COWORK patterns..."
    python "$TURBO\cowork\deploy_cowork_agents.py" --deploy 2>&1 | Tee-Object -Append -FilePath $LOG
    Log "Patterns deployed"
} else {
    Log "Patterns already deployed: $patternCount"
}

# Start cowork containers
Log "Starting cowork containers..."
docker compose -f $COMPOSE_FILE up -d 2>&1 | Tee-Object -Append -FilePath $LOG

# Verify
Start-Sleep -Seconds 10
$running = docker ps --filter "name=jarvis-cowork" --format "{{.Names}}: {{.Status}}" 2>$null
Log "Running containers:`n$running"

# Health check loop
Log "Starting health monitor (every 5min)..."
while ($true) {
    Start-Sleep -Seconds 300
    $containers = docker ps --filter "name=jarvis-cowork" --format "{{.Names}}:{{.Status}}" 2>$null
    $dead = docker ps --filter "name=jarvis-cowork" --filter "status=exited" --format "{{.Names}}" 2>$null
    if ($dead) {
        Log "RESTARTING dead containers: $dead"
        docker compose -f $COMPOSE_FILE up -d 2>&1 | Tee-Object -Append -FilePath $LOG
    }
}

