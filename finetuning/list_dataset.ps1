$dir = "F:\BUREAU\turbo\finetuning\dataset"
if (Test-Path $dir) {
    Get-ChildItem $dir | ForEach-Object {
        $sizeMB = [math]::Round($_.Length / 1MB, 2)
        Write-Host "$($_.Name) -- $sizeMB MB"
    }
} else {
    Write-Host "Dossier dataset non existant"
}
