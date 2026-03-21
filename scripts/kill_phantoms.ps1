$procs = Get-WmiObject Win32_Process -Filter "Name='node.exe'" | Select ProcessId, CommandLine, CreationDate
$types = @{
    'playwright-mcp' = 'playwright.*mcp.*cli\.js'
    'chrome-devtools' = 'chrome-devtools-mcp.*bin'
    'context7' = 'context7-mcp.*index\.js'
    'filesystem' = 'server-filesystem.*index\.js'
    'gemini-cli' = 'gemini-cli.*index\.js'
}
$killed = 0
foreach ($type in $types.Keys) {
    $pattern = $types[$type]
    $m = @($procs | Where-Object { $_.CommandLine -match $pattern -and $_.CommandLine -notmatch 'npx-cli' })
    if ($m.Count -le 1) {
        Write-Host "$type : $($m.Count) - OK"
        continue
    }
    $sorted = $m | Sort-Object CreationDate
    $toKill = @($sorted | Select-Object -First ($m.Count - 1))
    Write-Host "$type : $($m.Count) total, killing $($toKill.Count)"
    foreach ($p in $toKill) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "  Killed PID $($p.ProcessId)"
        $killed++
    }
}
$npxProcs = @($procs | Where-Object { $_.CommandLine -match 'npx-cli\.js.*(playwright|chrome-devtools|context7|filesystem)' })
$npxTypes = $npxProcs | Group-Object { if ($_.CommandLine -match 'playwright') {'pw'} elseif ($_.CommandLine -match 'chrome-devtools') {'cd'} elseif ($_.CommandLine -match 'context7') {'c7'} else {'fs'} }
foreach ($g in $npxTypes) {
    if ($g.Count -le 1) { continue }
    $sorted = $g.Group | Sort-Object CreationDate
    $toKill = @($sorted | Select-Object -First ($g.Count - 1))
    Write-Host "npx-$($g.Name) : killing $($toKill.Count) old wrappers"
    foreach ($p in $toKill) {
        taskkill /F /T /PID $p.ProcessId 2>$null | Out-Null
        Write-Host "  Killed NPX+children PID $($p.ProcessId)"
        $killed++
    }
}
Write-Host ""
Write-Host "Total killed: $killed"
