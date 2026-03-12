$path = "$env:USERPROFILE\.cache\huggingface\hub\models--Qwen--Qwen3-30B-A3B\blobs"
if (Test-Path $path) {
    $files = Get-ChildItem -Path $path -ErrorAction SilentlyContinue
    $total = ($files | Measure-Object -Property Length -Sum).Sum
    $count = $files.Count
    $gb = [math]::Round($total / 1GB, 2)
    Write-Host "Fichiers telecharges: $count | Taille: $gb GB / ~61 GB"
} else {
    # Check xet path
    $xetPath = "$env:USERPROFILE\.cache\huggingface\hub\models--Qwen--Qwen3-30B-A3B"
    if (Test-Path $xetPath) {
        $size = (Get-ChildItem -Path $xetPath -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        $gb = [math]::Round($size / 1GB, 2)
        Write-Host "Cache HF existe: $gb GB telecharges"
    } else {
        Write-Host "Telechargement pas encore demarre ou chemin different"
    }
}
