$blobDir = "$env:USERPROFILE\.cache\huggingface\hub\models--Qwen--Qwen3-30B-A3B\blobs"
$blobs = Get-ChildItem $blobDir -ErrorAction SilentlyContinue | Sort-Object Length -Descending
foreach ($b in $blobs) {
    $sizeGB = [math]::Round($b.Length / 1GB, 3)
    $sizeMB = [math]::Round($b.Length / 1MB, 1)
    if ($sizeGB -gt 0.1) {
        Write-Host "$($b.Name.Substring(0,12))... - $sizeGB GB"
    } else {
        Write-Host "$($b.Name.Substring(0,12))... - $sizeMB MB"
    }
}
Write-Host "`nTotal blobs: $($blobs.Count)"
$totalGB = [math]::Round(($blobs | Measure-Object Length -Sum).Sum / 1GB, 2)
Write-Host "Total: $totalGB GB"
