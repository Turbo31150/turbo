# Temporarily disable LM Studio auto-start for training
# Re-enable with: enable_lmstudio_startup.ps1

$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$regName = "electron.app.LM Studio"

# Backup value
$current = (Get-ItemProperty $regPath -Name $regName -ErrorAction SilentlyContinue).$regName
if ($current) {
    # Save backup
    Set-ItemProperty $regPath -Name "${regName}_BACKUP" -Value $current
    # Remove auto-start
    Remove-ItemProperty $regPath -Name $regName
    Write-Host "[OK] LM Studio auto-start desactive"
    Write-Host "  Backup: ${regName}_BACKUP"
} else {
    Write-Host "[INFO] LM Studio auto-start deja desactive"
}

# Kill any running instance
taskkill /F /IM "LM Studio.exe" /T 2>$null
Start-Sleep 3

# Verify GPU is clean
nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader
