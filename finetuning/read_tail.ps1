$file = "C:\Users\franc\AppData\Local\Temp\claude\C--Users-franc\tasks\b61f00b.output"
$stream = [System.IO.File]::Open($file, 'Open', 'Read', 'ReadWrite')
$size = $stream.Length
$readSize = [math]::Min(4000, $size)
$buffer = New-Object byte[] $readSize
$stream.Seek(-$readSize, 'End') | Out-Null
$stream.Read($buffer, 0, $readSize) | Out-Null
$stream.Close()

$text = [System.Text.Encoding]::UTF8.GetString($buffer)
# Split on \r and take last 30 segments
$parts = $text -split "`r"
$lastParts = $parts | Select-Object -Last 30
foreach ($p in $lastParts) {
    $trimmed = $p.Trim()
    if ($trimmed) { Write-Host $trimmed }
}
