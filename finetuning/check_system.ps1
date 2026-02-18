Write-Host "=== RAM ==="
$os = Get-CimInstance Win32_OperatingSystem
$totalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
Write-Host "Total: $totalGB GB | Libre: $freeGB GB"

Write-Host "`n=== Top 10 RAM ==="
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 | ForEach-Object {
    $memGB = [math]::Round($_.WorkingSet64 / 1GB, 2)
    Write-Host "$($_.ProcessName) (PID $($_.Id)) - $memGB GB"
}

Write-Host "`n=== HF Cache ==="
$hfPath = "$env:USERPROFILE\.cache\huggingface\hub\models--Qwen--Qwen3-30B-A3B"
if (Test-Path $hfPath) {
    $snapshots = Get-ChildItem "$hfPath\snapshots" -Directory -ErrorAction SilentlyContinue
    if ($snapshots) {
        foreach ($snap in $snapshots) {
            $files = Get-ChildItem $snap.FullName -ErrorAction SilentlyContinue
            Write-Host "Snapshot: $($snap.Name)"
            Write-Host "  Fichiers: $($files.Count)"
            foreach ($f in $files) {
                $sizeMB = [math]::Round($f.Length / 1MB, 1)
                Write-Host "    $($f.Name) - $sizeMB MB"
            }
        }
    }
    $blobs = Get-ChildItem "$hfPath\blobs" -ErrorAction SilentlyContinue
    if ($blobs) {
        Write-Host "`nBlobs: $($blobs.Count) fichiers"
        $totalBlobGB = [math]::Round(($blobs | Measure-Object Length -Sum).Sum / 1GB, 2)
        Write-Host "Total blobs: $totalBlobGB GB"
    }
} else {
    Write-Host "Cache HF non trouve"
}
