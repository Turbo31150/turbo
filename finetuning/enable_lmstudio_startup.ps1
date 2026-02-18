# Re-enable LM Studio auto-start after training
$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$regName = "electron.app.LM Studio"

$backup = (Get-ItemProperty $regPath -Name "${regName}_BACKUP" -ErrorAction SilentlyContinue)."${regName}_BACKUP"
if ($backup) {
    Set-ItemProperty $regPath -Name $regName -Value $backup
    Remove-ItemProperty $regPath -Name "${regName}_BACKUP"
    Write-Host "[OK] LM Studio auto-start reactive: $backup"
} else {
    # Default value
    Set-ItemProperty $regPath -Name $regName -Value 'C:\Program Files\LM Studio\LM Studio.exe --run-as-service'
    Write-Host "[OK] LM Studio auto-start reactive (valeur par defaut)"
}
