$offloadDir = "F:\BUREAU\turbo\finetuning\offload"
if (Test-Path $offloadDir) {
    $files = Get-ChildItem $offloadDir
    $totalMB = [math]::Round(($files | Measure-Object Length -Sum).Sum / 1MB, 1)
    Write-Host "Offload: $($files.Count) files, $totalMB MB total"
    $newest = $files | Sort-Object LastWriteTime -Descending | Select-Object -First 3
    foreach ($f in $newest) {
        $sizeMB = [math]::Round($f.Length / 1MB, 1)
        Write-Host "  $($f.Name) - $sizeMB MB - $($f.LastWriteTime)"
    }
} else {
    Write-Host "No offload dir"
}
