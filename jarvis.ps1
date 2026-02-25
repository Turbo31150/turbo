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
    [ValidateSet("ask","status","heal","arena","history","bench","filter","route","score","help")]
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
        Model = "qwen/qwen3-30b-a3b-2507"
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

function Pick-Node([string]$Domain, [string]$ForceNode) {
    if ($ForceNode -and $Nodes.ContainsKey($ForceNode)) { return $ForceNode }
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
                input = "[Instruction: $sysMsg]`n`n$Prompt"
                temperature = 0.2
                max_output_tokens = 1024
                stream = $false
                store = $false
            } | ConvertTo-Json -Depth 5
            $resp = Invoke-RestMethod -Uri $cfg.Url -Method Post -Body $body -Headers $headers -TimeoutSec 90
            $text = $resp.output[0].content
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
        $detectedDomain = if ($Domain) { $Domain } else { Detect-Domain $prompt }
        $selectedNode = Pick-Node $detectedDomain $Node

        Write-Host ('[JARVIS] Domain: {0} | Node: {1} | Prompt: {2}...' -f $detectedDomain, $selectedNode, $prompt.Substring(0, [Math]::Min(60, $prompt.Length))) -ForegroundColor Cyan
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

        if ($Json) {
            @{
                node = $result.Node
                domain = $detectedDomain
                latency_ms = $result.Latency
                response = $result.Text
                error = $result.Error
            } | ConvertTo-Json -Depth 3
        }
        else {
            Write-Host ""
            Write-Output $result.Text
            Write-Host ""
            Write-Host ('[{0} | {1} | {2}ms]' -f $result.Node, $detectedDomain, $result.Latency) -ForegroundColor DarkGray
        }
    }

    "status" {
        $output = @()
        foreach ($nid in @("M1","M2","M3","OL1")) {
            $cfg = $Nodes[$nid]
            $healthy = Health-Check $nid
            $status = if ($healthy) { "OK" } else { "FAIL" }
            $color = if ($healthy) { "Green" } else { "Red" }
            $tags = ($cfg.Tags -join ",")
            $line = "${nid}: $status | $($cfg.Model) | tags=$tags"
            Write-Host $line -ForegroundColor $color
            $output += [PSCustomObject]@{
                Node = $nid
                Status = $status
                Model = $cfg.Model
                Tags = $tags
                Priority = $cfg.Priority
            }
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
        $detectedDomain = Detect-Domain $prompt
        $selectedNode = Pick-Node $detectedDomain $Node
        $route = $Routing[$detectedDomain]
        Write-Host ('[ROUTE] Domain detecte: {0}' -f $detectedDomain) -ForegroundColor Cyan
        Write-Host ('[ROUTE] Noeud choisi: {0}' -f $selectedNode) -ForegroundColor Green
        Write-Host ('[ROUTE] Ordre fallback: {0}' -f ($route -join ' -> ')) -ForegroundColor DarkGray
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
