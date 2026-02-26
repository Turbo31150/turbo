#!/usr/bin/env pwsh
<#
.SYNOPSIS
    JARVIS CLI — Interface PowerShell unifiee pour le cluster IA
.DESCRIPTION
    Sous-commandes chainables via pipe (|) avec filtrage par mots-cles.
.EXAMPLE
    .\jarvis.ps1 ask "ecris fibonacci" -Node M1
    .\jarvis.ps1 status | .\jarvis.ps1 filter -Keyword "FAIL"
    .\jarvis.ps1 bench -Cycles 5 | .\jarvis.ps1 filter -Domain code
    .\jarvis.ps1 heal --status
    .\jarvis.ps1 arena --history
#>
param(
    [Parameter(Position=0)]
    [ValidateSet("ask","status","heal","arena","history","bench","filter","route","score","scores","consensus","profile","export","db","help")]
    [string]$Command = "help",

    [Parameter(Position=1, ValueFromRemainingArguments=$true)]
    [string[]]$Args_,

    [string]$Node,
    [string]$Domain,
    [string]$Keyword,
    [string]$Model,
    [int]$Cycles = 2,
    [int]$Tasks = 12,
    [switch]$Json,
    [switch]$Quick,
    [Parameter(ValueFromPipeline=$true)]
    [string]$PipeInput
)

# === CONFIG ===
$Nodes = @{
    "M1" = @{
        Url = "http://10.5.0.2:1234/api/v1/chat"
        HealthUrl = "http://10.5.0.2:1234/api/v1/models"
        Type = "lmstudio-responses"
        Model = "qwen/qwen3-8b"
        Key = "sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7"
        Tags = @("code","math","raisonnement","trading","securite","web","systeme","traduction")
        Priority = 3
    }
    "M2" = @{
        Url = "http://192.168.1.26:1234/v1/chat/completions"
        HealthUrl = "http://192.168.1.26:1234/api/v1/models"
        Type = "lmstudio"
        Model = "deepseek-coder-v2-lite-instruct"
        Key = "sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4"
        Tags = @("code","review","debug","securite")
        Priority = 2
    }
    "M3" = @{
        Url = "http://192.168.1.113:1234/v1/chat/completions"
        HealthUrl = "http://192.168.1.113:1234/api/v1/models"
        Type = "lmstudio"
        Model = "mistral-7b-instruct-v0.3"
        Key = "sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux"
        Tags = @("general","validation","systeme","traduction")
        Priority = 1
        NoSystemRole = $true
    }
    "OL1" = @{
        Url = "http://127.0.0.1:11434/api/chat"
        HealthUrl = "http://127.0.0.1:11434/api/tags"
        Type = "ollama"
        Model = "qwen3:1.7b"
        Key = $null
        Tags = @("rapide","simple","math","traduction","web")
        Priority = 2
    }
}

# Keywords -> Domain mapping
$DomainKeywords = @{
    "code"          = @("code","fonction","function","class","def","sql","bash","python","javascript","script","ecris","programme")
    "math"          = @("math","calcul","calcule","derive","equation","racine","pourcentage","nombre","combien")
    "raisonnement"  = @("logique","raisonnement","si","conclusion","deduction","premisse","syllogisme","reflechis")
    "trading"       = @("trading","rsi","btc","eth","signal","long","short","bull","bear","sma","volume","breakout")
    "securite"      = @("securite","injection","xss","ssl","ssh","https","vulnerabilite","port","header","cve")
    "web"           = @("web","http","api","fetch","curl","express","endpoint","rest","json","html")
    "systeme"       = @("systeme","powershell","bash","processus","disque","port","taskkill","netstat","gpu","ram")
    "traduction"    = @("traduis","translate","anglais","francais","espagnol","english","french","traduction")
}

# Routing: domain -> preferred nodes
$Routing = @{
    "code"          = @("M2","M1","M3","OL1")
    "math"          = @("M1","OL1","M2","M3")
    "raisonnement"  = @("M1","M2","OL1")
    "traduction"    = @("M1","OL1","M2","M3")
    "systeme"       = @("M1","OL1","M2","M3")
    "trading"       = @("M1","OL1","M2")
    "securite"      = @("M1","M2","M3")
    "web"           = @("M1","M2","OL1","M3")
}

# === ADAPTIVE ROUTING (etoile.db) ===
$DbHelper = "C:/Users/franc/jarvis_db.py"
$AutolearnUrl = "http://127.0.0.1:18800/autolearn/status"
$MinDataPoints = 3

# Reverse: jarvis domain -> autolearn category
$DomainToAutolearn = @{
    "code"          = "code"
    "securite"      = "sec"
    "web"           = "web"
    "systeme"       = "system"
    "trading"       = "trading"
    "raisonnement"  = "ia"
    "math"          = "default"
    "traduction"    = "default"
    "general"       = "default"
}

$RoutingLogFile = "C:/Users/franc/jarvis_routing_log.json"

function Log-Result([string]$NodeId, [string]$Domain, [int]$LatencyMs, [bool]$Success, [string]$Source="static", [string]$Prompt="", [string]$Preview="") {
    # Dual write: etoile.db + JSON (both via Python for consistency)
    $s = if ($Success) { "1" } else { "0" }
    python3 $DbHelper log_query $NodeId $Domain $LatencyMs $s $Source $Prompt $Preview 2>$null
    python3 $DbHelper log_json $RoutingLogFile $NodeId $Domain $LatencyMs $s 2>$null
}

function Log-Health([string]$NodeId, [string]$Status, [string]$Model, [int]$LatencyMs=0) {
    python3 $DbHelper log_health $NodeId $Status $Model $LatencyMs 2>$null
}

function Log-Consensus([string]$Query, [string]$NodesQueried, [string]$NodesResponded, [string]$Verdict, [double]$Confidence, [string]$Details="") {
    python3 $DbHelper log_consensus $Query $NodesQueried $NodesResponded $Verdict $Confidence $Details 2>$null
}

function Get-AutolearnRoute([string]$Domain) {
    $alCat = $DomainToAutolearn[$Domain]
    if (-not $alCat) { $alCat = "default" }
    try {
        $resp = Invoke-RestMethod -Uri $AutolearnUrl -TimeoutSec 2 -ErrorAction Stop
        $routing = $resp.pillars.tuning.current_routing
        $route = $routing.$alCat
        if ($route -and $route.Count -gt 0) {
            return @($route)
        }
    }
    catch { }
    return $null
}

function Get-AdaptiveRoute([string]$Domain) {
    # Priority: etoile.db (richer data)
    try {
        $raw = python3 $DbHelper adaptive_route $Domain $MinDataPoints 2>$null
        if ($raw -and $raw -ne "null") {
            return @($raw | ConvertFrom-Json)
        }
    } catch { }
    # Fallback: JSON file
    if (Test-Path $RoutingLogFile) {
        try {
            $log = @(Get-Content $RoutingLogFile -Raw | ConvertFrom-Json)
            $domEntries = @($log | Where-Object { $_.domain -eq $Domain })
            if ($domEntries.Count -lt $MinDataPoints) { return $null }
            $nodeScores = @{}
            foreach ($nid in $Nodes.Keys) {
                $ne = @($domEntries | Where-Object { $_.node -eq $nid })
                if ($ne.Count -lt 1) { continue }
                $sr = ($ne | Where-Object { $_.success -eq $true }).Count / $ne.Count
                $al = ($ne | Measure-Object -Property latency_ms -Average).Average
                $nodeScores[$nid] = [Math]::Round(([Math]::Max(0,(10-$al/5000)))*0.4 + $sr*10*0.6, 2)
            }
            if ($nodeScores.Count -eq 0) { return $null }
            return @($nodeScores.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object { $_.Key })
        } catch { }
    }
    return $null
}

# === FUNCTIONS ===

function Detect-Domain([string]$Text) {
    $textLower = $Text.ToLower()
    $scores = @{}
    foreach ($dom in $DomainKeywords.Keys) {
        $count = 0
        foreach ($kw in $DomainKeywords[$dom]) {
            if ($textLower -match [regex]::Escape($kw)) { $count++ }
        }
        if ($count -gt 0) { $scores[$dom] = $count }
    }
    if ($scores.Count -eq 0) { return "general" }
    return ($scores.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 1).Key
}

function Get-ScenarioRoute([string]$Domain) {
    try {
        $raw = python3 $DbHelper scenario_route $Domain 2>$null
        if ($raw -and $raw -ne "null") {
            $parsed = $raw | ConvertFrom-Json
            if ($parsed -and $parsed.Count -gt 0) {
                return @($parsed | ForEach-Object { $_.agent })
            }
        }
    } catch { }
    return $null
}

function Get-KeywordRoute([string]$Prompt) {
    try {
        $raw = python3 $DbHelper keyword_match $Prompt 2>$null
        if ($raw -and $raw -ne "null") {
            $parsed = $raw | ConvertFrom-Json
            if ($parsed -and $parsed.Count -gt 0) {
                return $parsed[0].agent
            }
        }
    } catch { }
    return $null
}

function Run-Dominos([string]$TriggerCmd, [string]$Condition="always") {
    try {
        $raw = python3 $DbHelper dominos $TriggerCmd $Condition 2>$null
        if (-not $raw -or $raw -eq "[]") { return }
        $chains = $raw | ConvertFrom-Json
        foreach ($chain in $chains) {
            if (-not $chain.auto) { continue }
            if ($chain.delay_ms -gt 0) { Start-Sleep -Milliseconds $chain.delay_ms }
            Write-Host ('[DOMINO] {0} -> {1}' -f $TriggerCmd, $chain.next_cmd) -ForegroundColor Magenta
            # Execute the chained command via jarvis.ps1 recursively
            $cmdParts = $chain.next_cmd -split ' ', 2
            $subCmd = $cmdParts[0]
            $subArgs = if ($cmdParts.Count -gt 1) { $cmdParts[1] } else { "" }
            powershell.exe -Command "& 'C:/Users/franc/jarvis.ps1' $subCmd $subArgs" 2>$null
        }
    } catch { }
}

function Pick-Node([string]$Domain, [string]$ForceNode, [string]$Prompt="") {
    if ($ForceNode -and $Nodes.ContainsKey($ForceNode)) { return $ForceNode }
    # Priority 1: Autolearn engine (50+ tuning cycles)
    $alRoute = @(Get-AutolearnRoute $Domain)
    if ($alRoute -and $alRoute[0]) {
        $script:RoutingSource = "autolearn"
        return $alRoute[0]
    }
    # Priority 2: Keyword match from etoile.db (188 keywords)
    if ($Prompt) {
        $kwMatch = Get-KeywordRoute $Prompt
        if ($kwMatch -and $Nodes.ContainsKey($kwMatch)) {
            $script:RoutingSource = "keyword"
            return $kwMatch
        }
    }
    # Priority 3: Scenario weights from etoile.db (51 entries)
    $scenarioRoute = @(Get-ScenarioRoute $Domain)
    if ($scenarioRoute -and $scenarioRoute[0]) {
        $script:RoutingSource = "scenario"
        return $scenarioRoute[0]
    }
    # Priority 4: Local adaptive (jarvis.ps1 CLI data)
    $adaptive = @(Get-AdaptiveRoute $Domain)
    if ($adaptive -and $adaptive[0]) {
        $script:RoutingSource = "adaptive"
        return $adaptive[0]
    }
    # Priority 5: Static defaults
    $script:RoutingSource = "static"
    $route = $Routing[$Domain]
    if (-not $route) { $route = @("M1","OL1","M2","M3") }
    return $route[0]
}

function Query-Node([string]$NodeId, [string]$Prompt) {
    $cfg = $Nodes[$NodeId]
    $headers = @{ "Content-Type" = "application/json" }
    if ($cfg.Key) { $headers["Authorization"] = "Bearer $($cfg.Key)" }
    $sysMsg = "Tu es JARVIS, assistant IA. Reponds toujours en francais, de maniere concise et precise."

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        if ($cfg.Type -eq "ollama") {
            $body = @{
                model = $cfg.Model
                messages = @(
                    @{ role = "system"; content = $sysMsg }
                    @{ role = "user"; content = $Prompt }
                )
                stream = $false
                think = $false
                options = @{ num_ctx = 4096; temperature = 0.2 }
            } | ConvertTo-Json -Depth 5
            $resp = Invoke-RestMethod -Uri $cfg.Url -Method Post -Body $body -Headers $headers -TimeoutSec 30
            $text = $resp.message.content
        }
        elseif ($cfg.Type -eq "lmstudio-responses") {
            $body = @{
                model = $cfg.Model
                input = "/nothink`n[Instruction: $sysMsg]`n`n$Prompt"
                temperature = 0.2
                max_output_tokens = 1024
                stream = $false
                store = $false
            } | ConvertTo-Json -Depth 5
            $resp = Invoke-RestMethod -Uri $cfg.Url -Method Post -Body $body -Headers $headers -TimeoutSec 30
            # Extract message content (skip reasoning block if present)
            $text = ""
            foreach ($out in $resp.output) {
                if ($out.type -eq "message" -and $out.content) { $text = $out.content }
            }
            if (-not $text -and $resp.output.Count -gt 0) { $text = $resp.output[-1].content }
        }
        else {
            if ($cfg.NoSystemRole) {
                $msgs = @(@{ role = "user"; content = "[Instruction: $sysMsg]`n`n$Prompt" })
            } else {
                $msgs = @(
                    @{ role = "system"; content = $sysMsg }
                    @{ role = "user"; content = $Prompt }
                )
            }
            $body = @{
                model = $cfg.Model
                messages = $msgs
                temperature = 0.2
                max_tokens = 1024
                stream = $false
            } | ConvertTo-Json -Depth 5
            $resp = Invoke-RestMethod -Uri $cfg.Url -Method Post -Body $body -Headers $headers -TimeoutSec 60
            $text = $resp.choices[0].message.content
        }
        $sw.Stop()
        # Strip think tags
        $text = $text -replace '(?s)<think>.*?</think>', ''
        return @{ Node=$NodeId; Text=$text.Trim(); Latency=$sw.ElapsedMilliseconds; Error=$null }
    }
    catch {
        $sw.Stop()
        return @{ Node=$NodeId; Text=""; Latency=$sw.ElapsedMilliseconds; Error=$_.Exception.Message }
    }
}

function Health-Check([string]$NodeId) {
    $cfg = $Nodes[$NodeId]
    $headers = @{}
    if ($cfg.Key) { $headers["Authorization"] = "Bearer $($cfg.Key)" }
    try {
        $resp = Invoke-RestMethod -Uri $cfg.HealthUrl -Headers $headers -TimeoutSec 5
        if ($cfg.Type -eq "ollama") {
            return ($resp.models.Count -gt 0)
        }
        else {
            $models = if ($resp.data) { $resp.data } else { $resp.models }
            foreach ($m in $models) {
                if ($m.loaded_instances -and $m.loaded_instances.Count -gt 0) { return $true }
            }
            return $false
        }
    }
    catch { return $false }
}

# === COMMANDS ===

switch ($Command) {

    "ask" {
        $prompt = ($Args_ -join " ").Trim()
        if (-not $prompt) { Write-Host "Usage: jarvis ask `"votre question`" [-Node M1] [-Domain code]"; exit 1 }

        # Auto-detect domain from keywords
        $script:RoutingSource = "static"
        $detectedDomain = if ($Domain) { $Domain } else { Detect-Domain $prompt }
        $selectedNode = Pick-Node $detectedDomain $Node $prompt
        Write-Host ('[JARVIS] Domain: {0} | Node: {1} | Source: {2} | Prompt: {3}...' -f $detectedDomain, $selectedNode, $RoutingSource, $prompt.Substring(0, [Math]::Min(50, $prompt.Length))) -ForegroundColor Cyan
        $result = Query-Node $selectedNode $prompt

        if ($result.Error) {
            Write-Host ('[ERROR] {0}' -f $result.Error) -ForegroundColor Red
            # Fallback to next node
            $fallbacks = $Routing[$detectedDomain]
            if ($fallbacks) {
                foreach ($fb in $fallbacks) {
                    if ($fb -ne $selectedNode) {
                        Write-Host ('[FALLBACK] Trying {0}...' -f $fb) -ForegroundColor Yellow
                        $result = Query-Node $fb $prompt
                        if (-not $result.Error) { break }
                    }
                }
            }
        }

        # Log result for adaptive routing (JSON + etoile.db)
        $querySuccess = -not [bool]$result.Error
        $respPreview = if ($result.Text) { $result.Text.Substring(0, [Math]::Min(200, $result.Text.Length)) } else { "" }
        Log-Result $result.Node $detectedDomain $result.Latency $querySuccess $RoutingSource $prompt $respPreview

        # Domino chains
        if ($result.Error) { Run-Dominos "ask" "timeout" }
        else { Run-Dominos "ask" "success" }

        if ($Json) {
            @{
                node = $result.Node
                domain = $detectedDomain
                latency_ms = $result.Latency
                response = $result.Text
                error = $result.Error
                routing = $RoutingSource
            } | ConvertTo-Json -Depth 3
        }
        else {
            Write-Host ""
            Write-Output $result.Text
            Write-Host ""
            Write-Host ('[{0} | {1} | {2}ms | {3}]' -f $result.Node, $detectedDomain, $result.Latency, $RoutingSource) -ForegroundColor DarkGray
        }
    }

    "status" {
        $output = @()
        $failedNodes = @()
        foreach ($nid in @("M1","M2","M3","OL1")) {
            $cfg = $Nodes[$nid]
            $healthy = Health-Check $nid
            $status = if ($healthy) { "OK" } else { "FAIL" }
            $color = if ($healthy) { "Green" } else { "Red" }
            $tags = ($cfg.Tags -join ",")
            $line = "${nid}: $status | $($cfg.Model) | tags=$tags"
            Write-Host $line -ForegroundColor $color
            Log-Health $nid $status $cfg.Model
            if (-not $healthy) { $failedNodes += $nid }
            $output += [PSCustomObject]@{
                Node = $nid
                Status = $status
                Model = $cfg.Model
                Tags = $tags
                Priority = $cfg.Priority
            }
        }
        # Autolearn status
        try {
            $al = Invoke-RestMethod -Uri $AutolearnUrl -TimeoutSec 2 -ErrorAction Stop
            $alStatus = if ($al.running) { 'RUNNING' } else { 'STOPPED' }
            $alColor = if ($al.running) { 'Green' } else { 'Red' }
            Write-Host ('Autolearn: {0} | {1} msgs | {2} tuning cycles' -f $alStatus, $al.pillars.memory.total_messages, $al.pillars.tuning.history_count) -ForegroundColor $alColor
        } catch {
            Write-Host 'Autolearn: OFFLINE (port 18800)' -ForegroundColor Red
        }
        # Alerts + domino
        if ($failedNodes.Count -gt 0) {
            Write-Host ''
            Write-Host ('  ALERTE: {0} noeud(s) en panne: {1}' -f $failedNodes.Count, ($failedNodes -join ', ')) -ForegroundColor Red
            Write-Host '  Lancez "jarvis heal --status" pour diagnostiquer' -ForegroundColor Yellow
            Run-Dominos "status" "node_fail"
        } else {
            Run-Dominos "status" "all_ok"
        }
        if ($Json) { $output | ConvertTo-Json }
    }

    "heal" {
        $statusFlag = ($Args_ -contains "--status") -or ($Args_ -contains "-s")
        if ($statusFlag) {
            Write-Host '[HEALER] Quick status check...' -ForegroundColor Cyan
            python3 C:/Users/franc/jarvis_cluster_healer.py --status
            if (Test-Path "C:/Users/franc/jarvis_healer.log") {
                Write-Host "`n[HEALER] Last 10 log entries:" -ForegroundColor Cyan
                Get-Content "C:/Users/franc/jarvis_healer.log" -Tail 10
            }
        }
        else {
            Write-Host '[HEALER] Starting daemon (Ctrl+C to stop)...' -ForegroundColor Cyan
            python3 C:/Users/franc/jarvis_cluster_healer.py
        }
    }

    "arena" {
        $historyFlag = ($Args_ -contains "--history") -or ($Args_ -contains "-h")
        if ($historyFlag) {
            python3 C:/Users/franc/jarvis_model_arena.py --history
        }
        elseif ($Args_.Count -gt 0) {
            $modelName = $Args_[0]
            if ($Quick) {
                python3 C:/Users/franc/jarvis_model_arena.py --quick $modelName
            }
            else {
                python3 C:/Users/franc/jarvis_model_arena.py $modelName
            }
        }
        else {
            python3 C:/Users/franc/jarvis_model_arena.py
        }
    }

    "history" {
        $histData = Get-Content "C:/Users/franc/jarvis_benchmark_history.json" -Raw | ConvertFrom-Json
        $ch = $histData.champion
        Write-Host "`nChampion: $($ch.model) (score=$($ch.score), since=$($ch.since))" -ForegroundColor Green
        Write-Host ""
        if ($histData.runs.Count -gt 0) {
            $last10 = $histData.runs | Select-Object -Last 10
            Write-Host "Timestamp            Type      Score  Pass%  Latency   Model" -ForegroundColor Cyan
            Write-Host ("-" * 80) -ForegroundColor DarkGray
            foreach ($r in $last10) {
                $line = "{0,-20} {1,-9} {2,5:N2}  {3,4:N0}%  {4,7}ms  {5}" -f $r.timestamp, $r.type, $r.score_composite, $r.pass_rate, $r.avg_latency_ms, ($r.model_m1.Substring(0, [Math]::Min(30, $r.model_m1.Length)))
                $color = if ($r.score_composite -ge 7) { "Green" } elseif ($r.score_composite -ge 5) { "Yellow" } else { "Red" }
                Write-Host $line -ForegroundColor $color
            }
            # Trend
            if ($histData.runs.Count -ge 2) {
                $prev = $histData.runs[-2].score_composite
                $curr = $histData.runs[-1].score_composite
                $trend = $curr - $prev
                $arrow = if ($trend -gt 0) { "^" } elseif ($trend -lt 0) { "v" } else { "=" }
                $tColor = if ($trend -gt 0) { "Green" } elseif ($trend -lt 0) { "Red" } else { "Yellow" }
                Write-Host "`nTendance: $arrow $("{0:+0.00;-0.00}" -f $trend)" -ForegroundColor $tColor
            }
        }
        else {
            Write-Host "Aucun run enregistre." -ForegroundColor Yellow
        }
    }

    "bench" {
        Write-Host ('[BENCH] Running {0} cycles x {1} tasks...' -f $Cycles, $Tasks) -ForegroundColor Cyan
        python3 C:/Users/franc/jarvis_autotest.py $Cycles $Tasks
        Write-Host "`n[BENCH] Results:" -ForegroundColor Cyan
        $data = Get-Content "C:/Users/franc/jarvis_autotest_results.json" -Raw | ConvertFrom-Json
        $pct = [math]::Floor($data.pass * 100 / [Math]::Max($data.total, 1))
        Write-Host "  Pass: $($data.pass)/$($data.total) ($pct%)" -ForegroundColor $(if ($pct -ge 95) {"Green"} else {"Yellow"})
        foreach ($nid in $data.by_node.PSObject.Properties) {
            $n = $nid.Value
            $np = [math]::Floor($n.pass * 100 / [Math]::Max($n.total, 1))
            Write-Host "  $($nid.Name): $np% ($($n.total) tests, avg $($n.avg_latency)ms)"
        }
    }

    "filter" {
        # Filter piped input by keyword, domain, or node
        $input_lines = @()
        if ($PipeInput) { $input_lines += $PipeInput }
        $input | ForEach-Object { $input_lines += $_ }

        foreach ($line in $input_lines) {
            if (-not $line) { continue }
            $match = $true
            if ($Keyword -and $line -notmatch [regex]::Escape($Keyword)) { $match = $false }
            if ($Domain -and $line -notmatch [regex]::Escape($Domain)) { $match = $false }
            if ($Node -and $line -notmatch [regex]::Escape($Node)) { $match = $false }
            if ($match) { Write-Output $line }
        }
    }

    "route" {
        $prompt = ($Args_ -join " ").Trim()
        if (-not $prompt) {
            Write-Host 'Usage: jarvis route "prompt" -- affiche quel noeud serait choisi' ; exit 1
        }
        $script:RoutingSource = "static"
        $detectedDomain = Detect-Domain $prompt
        $selectedNode = Pick-Node $detectedDomain $Node
        $alRoute = @(Get-AutolearnRoute $detectedDomain)
        $adaptive = @(Get-AdaptiveRoute $detectedDomain)
        $staticRoute = $Routing[$detectedDomain]
        Write-Host ('[ROUTE] Domain detecte: {0}' -f $detectedDomain) -ForegroundColor Cyan
        Write-Host ('[ROUTE] Noeud choisi: {0} ({1})' -f $selectedNode, $RoutingSource) -ForegroundColor Green
        Write-Host ('[ROUTE] Statique:   {0}' -f ($staticRoute -join ' -> ')) -ForegroundColor DarkGray
        if ($alRoute -and $alRoute[0]) {
            Write-Host ('[ROUTE] Autolearn:  {0}' -f ($alRoute -join ' -> ')) -ForegroundColor Magenta
        } else {
            Write-Host '[ROUTE] Autolearn:  proxy offline ou pas de donnees' -ForegroundColor DarkGray
        }
        if ($adaptive -and $adaptive[0]) {
            Write-Host ('[ROUTE] Local CLI:  {0}' -f ($adaptive -join ' -> ')) -ForegroundColor Yellow
        } else {
            Write-Host '[ROUTE] Local CLI:  pas assez de donnees (min 3)' -ForegroundColor DarkGray
        }
        Write-Host '[ROUTE] Keywords matches:' -ForegroundColor DarkGray
        foreach ($dom in $DomainKeywords.Keys) {
            $count = 0
            foreach ($kw in $DomainKeywords[$dom]) {
                if ($prompt.ToLower() -match [regex]::Escape($kw)) { $count++ }
            }
            if ($count -gt 0) { Write-Host ('  {0} : {1} matches' -f $dom, $count) -ForegroundColor Yellow }
        }
    }

    "score" {
        @'
from jarvis_bench_utils import load_history, compute_composite_score
h = load_history()
ch = h['champion']
print(f'Champion: {ch["model"]}')
print(f'Score: {ch["score"]}')
print(f'Since: {ch["since"]}')
print(f'Runs: {len(h["runs"])}')
if h['runs']:
    last = h['runs'][-1]
    print(f'Last: {last["timestamp"]} score={last["score_composite"]} pass={last["pass_rate"]:.0f}%')
'@ | python3
    }

    "scores" {
        # Read from etoile.db via helper
        $raw = python3 $DbHelper scores 2>$null
        if (-not $raw -or $raw -eq "NO_DATA") {
            Write-Host 'Aucune donnee de routage. Utilisez "jarvis ask" pour alimenter le log.' -ForegroundColor Yellow
        }
        else {
            $data = $raw | ConvertFrom-Json
            # Also get DB stats
            $statsRaw = python3 $DbHelper stats 2>$null
            $stats = $statsRaw | ConvertFrom-Json
            Write-Host ("`nRoutage adaptatif -- {0} requetes (etoile.db) | {1} consensus | {2} health checks" -f $stats.total_queries, $stats.consensus_logs, $stats.health_checks) -ForegroundColor Cyan
            Write-Host ("{0,-14} {1,-6} {2,-6} {3,-10} {4,-10} {5,-8}" -f "Domain", "Node", "Reqs", "AvgLatency", "Success%", "Score") -ForegroundColor Cyan
            Write-Host ("-" * 60) -ForegroundColor DarkGray
            foreach ($row in $data) {
                $color = if ($row.score -ge 7) { "Green" } elseif ($row.score -ge 4) { "Yellow" } else { "Red" }
                Write-Host ("{0,-14} {1,-6} {2,-6} {3,-10} {4,-10} {5,-8}" -f $row.domain, $row.node, $row.count, "$($row.avg_latency)ms", "$($row.success_pct)%", $row.score) -ForegroundColor $color
            }
            Write-Host ("`nMin {0} requetes/domaine pour activer le routage adaptatif." -f $MinDataPoints) -ForegroundColor DarkGray
            if ($stats.last_query) {
                Write-Host ('Derniere requete: {0}' -f $stats.last_query) -ForegroundColor DarkGray
            }
        }
    }

    "consensus" {
        $prompt = ($Args_ -join " ").Trim()
        if (-not $prompt) { Write-Host 'Usage: jarvis consensus "votre question"' ; exit 1 }

        # Poids par noeud (benchmark-tuned)
        $weights = @{ "M1" = 1.8; "M2" = 1.4; "M3" = 1.0; "OL1" = 1.3 }
        $detectedDomain = Detect-Domain $prompt

        Write-Host ('[CONSENSUS] Domain: {0} | Noeuds: M1+M2+M3+OL1' -f $detectedDomain) -ForegroundColor Cyan
        Write-Host '[CONSENSUS] Interrogation en cours...' -ForegroundColor DarkGray

        # Query all nodes sequentially (PowerShell Jobs overhead > sequential for 4 nodes)
        $results = @{}
        foreach ($nid in @("OL1","M3","M2","M1")) {
            Write-Host ('  {0}...' -f $nid) -ForegroundColor DarkGray -NoNewline
            $r = Query-Node $nid $prompt
            $results[$nid] = $r
            $status = if ($r.Error) { 'FAIL' } else { 'OK' }
            $color = if ($r.Error) { 'Red' } else { 'Green' }
            Write-Host (' {0} ({1}ms)' -f $status, $r.Latency) -ForegroundColor $color
            Log-Result $nid $detectedDomain $r.Latency (-not [bool]$r.Error)
        }

        # Display responses
        Write-Host ''
        foreach ($nid in @("OL1","M3","M2","M1")) {
            $r = $results[$nid]
            if ($r.Error) {
                Write-Host ('{0} (w={1}): [ERREUR] {2}' -f $nid, $weights[$nid], $r.Error) -ForegroundColor Red
            } else {
                $preview = $r.Text.Substring(0, [Math]::Min(200, $r.Text.Length))
                if ($r.Text.Length -gt 200) { $preview += '...' }
                Write-Host ('{0} (w={1}, {2}ms):' -f $nid, $weights[$nid], $r.Latency) -ForegroundColor Yellow
                Write-Host "  $preview"
                Write-Host ''
            }
        }

        # Weighted vote - pick best by weight among successful
        $successNodes = @($results.Keys | Where-Object { -not $results[$_].Error })
        if ($successNodes.Count -eq 0) {
            Write-Host '[CONSENSUS] Aucun noeud disponible!' -ForegroundColor Red
        } else {
            $bestNode = ($successNodes | Sort-Object { $weights[$_] } -Descending)[0]
            $totalWeight = ($successNodes | ForEach-Object { $weights[$_] } | Measure-Object -Sum).Sum
            $bestWeight = $weights[$bestNode]
            $confidence = [Math]::Round($bestWeight / $totalWeight * 100, 0)
            Write-Host ('--- CONSENSUS ({0}/{1} noeuds) ---' -f $successNodes.Count, $results.Count) -ForegroundColor Green
            Write-Host ('Meilleure reponse: {0} (poids={1}, confiance={2}%)' -f $bestNode, $bestWeight, $confidence) -ForegroundColor Green
            Write-Host ''
            Write-Output $results[$bestNode].Text
            # Log to etoile.db
            Log-Consensus $prompt ("M1,M2,M3,OL1") ($successNodes -join ',') $bestNode ($confidence / 100)
        }

        if ($Json) {
            $jsonOut = @{
                domain = $detectedDomain
                nodes_queried = $results.Count
                nodes_ok = $successNodes.Count
                best_node = $bestNode
                confidence_pct = $confidence
                responses = @{}
            }
            foreach ($nid in $results.Keys) {
                $r = $results[$nid]
                $jsonOut.responses[$nid] = @{
                    text = $r.Text
                    latency_ms = $r.Latency
                    error = $r.Error
                    weight = $weights[$nid]
                }
            }
            $jsonOut | ConvertTo-Json -Depth 4
        }
    }

    "profile" {
        Write-Host '[PROFILE] Chargement du profil autolearn...' -ForegroundColor Cyan
        try {
            $resp = Invoke-RestMethod -Uri "http://127.0.0.1:18800/autolearn/memory" -TimeoutSec 5 -ErrorAction Stop
            Write-Host ''
            Write-Host '  Profil utilisateur' -ForegroundColor Green
            Write-Host ('  {0}' -f ('-' * 50)) -ForegroundColor DarkGray
            if ($resp.profile_summary) {
                Write-Host ('  {0}' -f $resp.profile_summary) -ForegroundColor White
            } else {
                Write-Host '  (profil en construction)' -ForegroundColor Yellow
            }
            Write-Host ''
            Write-Host ('  Messages totaux: {0}' -f $resp.total_messages) -ForegroundColor Cyan
            if ($resp.top_topics -and $resp.top_topics.Count -gt 0) {
                Write-Host '  Top topics:' -ForegroundColor Cyan
                foreach ($t in $resp.top_topics) {
                    $topic = $t[0]; $count = $t[1]
                    Write-Host ('    {0,-20} {1} msgs' -f $topic, $count) -ForegroundColor White
                }
            }
            Write-Host ''
            if ($resp.last_conversations -and $resp.last_conversations.Count -gt 0) {
                Write-Host '  Dernieres conversations:' -ForegroundColor Cyan
                $last5 = $resp.last_conversations | Select-Object -Last 5
                foreach ($c in $last5) {
                    $preview = if ($c.user_msg) { $c.user_msg.Substring(0, [Math]::Min(60, $c.user_msg.Length)) } else { '?' }
                    $ts = if ($c.timestamp) { $c.timestamp.Substring(11,5) } else { '' }
                    Write-Host ('    [{0}] {1}...' -f $ts, $preview) -ForegroundColor DarkGray
                }
            }
            if ($Json) { $resp | ConvertTo-Json -Depth 4 }
        }
        catch {
            Write-Host '[PROFILE] Autolearn proxy offline (port 18800)' -ForegroundColor Red
        }
    }

    "export" {
        $exportFile = "C:/Users/franc/jarvis_config_export.json"
        $config = @{
            timestamp = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
            nodes = @{}
            routing = $Routing
            domain_keywords = $DomainKeywords
        }
        foreach ($nid in $Nodes.Keys) {
            $cfg = $Nodes[$nid]
            $config.nodes[$nid] = @{
                model = $cfg.Model
                type = $cfg.Type
                url = $cfg.Url
                tags = $cfg.Tags
                priority = $cfg.Priority
            }
        }
        # Include etoile.db stats
        try {
            $statsRaw = python3 $DbHelper stats 2>$null
            $dbStats = $statsRaw | ConvertFrom-Json
            $config["etoile_db"] = $dbStats
        } catch { }
        $config | ConvertTo-Json -Depth 4 | Set-Content $exportFile -Encoding UTF8
        Write-Host ('[EXPORT] Configuration exportee: {0}' -f $exportFile) -ForegroundColor Green
        # Auto-push to GitHub if -Json flag (used as trigger for gh)
        if ($Json) {
            $config | ConvertTo-Json -Depth 4
        }
    }

    "db" {
        $raw = python3 $DbHelper summary 2>$null
        if (-not $raw) {
            Write-Host '[DB] Erreur lecture etoile.db' -ForegroundColor Red
        } else {
            $data = $raw | ConvertFrom-Json
            Write-Host ''
            Write-Host '  ETOILE.DB -- Resume complet' -ForegroundColor Cyan
            Write-Host ('  {0}' -f ('-' * 45)) -ForegroundColor DarkGray
            Write-Host ('  Queries:          {0}' -f $data.jarvis_queries) -ForegroundColor White
            Write-Host ('  Health checks:    {0}' -f $data.cluster_health) -ForegroundColor White
            Write-Host ('  Consensus logs:   {0}' -f $data.consensus_log) -ForegroundColor White
            Write-Host ('  Benchmarks:       {0}' -f $data.benchmark_results) -ForegroundColor White
            Write-Host ('  Metrics:          {0}' -f $data.metrics) -ForegroundColor White
            Write-Host ('  Map entries:      {0}' -f $data.map) -ForegroundColor White
            Write-Host ''
            Write-Host ('  Agent keywords:   {0}' -f $data.agent_keywords) -ForegroundColor Green
            Write-Host ('  Pipelines:        {0}' -f $data.pipeline_dictionary) -ForegroundColor Green
            Write-Host ('  Scenarios:        {0} ({1} weights)' -f $data.scenarios_count, $data.scenario_weights) -ForegroundColor Green
            Write-Host ('  Domino chains:    {0}' -f $data.domino_chains) -ForegroundColor Green
            Write-Host ''
            Write-Host '  Keywords par agent:' -ForegroundColor Cyan
            foreach ($prop in $data.agents_keywords.PSObject.Properties) {
                Write-Host ('    {0,-10} {1} keywords' -f $prop.Name, $prop.Value) -ForegroundColor White
            }
            Write-Host ''
        }
        if ($Json) { Write-Output $raw }
    }

    "help" {
        $helpText = @'

  JARVIS CLI -- Cluster IA distribue
  ==================================

  COMMANDES:
    jarvis ask "prompt"          Pose une question (auto-route par keywords)
    jarvis ask "prompt" -Node M1 Force un noeud specifique
    jarvis ask "prompt" -Json    Sortie JSON (pipeable)

    jarvis status                Statut de tous les noeuds
    jarvis status -Json          Sortie JSON

    jarvis route "prompt"        Affiche le routage sans executer

    jarvis bench -Cycles 5       Lance un benchmark
    jarvis history               Historique des scores
    jarvis score                 Score champion actuel
    jarvis scores                Scores adaptatifs par noeud x domaine

    jarvis consensus "question"  Vote pondere M1+M2+M3+OL1
    jarvis db                    Resume etoile.db (toutes tables)
    jarvis profile               Profil autolearn + topics + conversations
    jarvis export                Exporte la config en JSON

    jarvis heal --status         Etat du healer
    jarvis heal                  Lance le daemon healer

    jarvis arena model-name      Tournoi champion vs candidat
    jarvis arena --history       Historique des tournois

  FILTRAGE PAR PIPELINE:
    jarvis status | jarvis filter -Keyword "FAIL"
    jarvis bench | jarvis filter -Domain code
    jarvis bench | jarvis filter -Node M1

  EXEMPLES POWERSHELL:
    .\jarvis.ps1 ask "ecris fibonacci en python" -Node M1
    .\jarvis.ps1 status | Select-String "FAIL"
    .\jarvis.ps1 ask "calcule 847*23" -Json | ConvertFrom-Json
    .\jarvis.ps1 bench -Cycles 10 -Tasks 40

  MOTS-CLES DETECTES:
    code:         code, fonction, class, def, sql, python, javascript
    math:         calcul, derive, equation, racine, combien
    raisonnement: logique, si, conclusion, deduction, reflechis
    trading:      rsi, btc, signal, long, short, breakout
    securite:     injection, xss, ssl, ssh, vulnerabilite
    web:          http, api, fetch, curl, express, endpoint
    systeme:      powershell, processus, disque, port, gpu, ram
    traduction:   traduis, anglais, francais, espagnol

'@
        Write-Host $helpText -ForegroundColor Cyan
    }
}
