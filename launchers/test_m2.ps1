# ═══════════════════════════════════════════════════════════════
# TEST M2 — LM Studio Native API /api/v1/chat
# ═══════════════════════════════════════════════════════════════

$_M2_KEY = if ($env:LM_STUDIO_2_API_KEY) { $env:LM_STUDIO_2_API_KEY } elseif ($env:LM_STUDIO_2_KEY) { $env:LM_STUDIO_2_KEY } else { "" }
$M2_Headers = @{ Authorization = "Bearer $_M2_KEY" }

# Check M2 models
Write-Host "=== M2 MODELS ==="
$models = Invoke-RestMethod -Uri "http://192.168.1.26:1234/api/v1/models" -Headers $M2_Headers -TimeoutSec 5
foreach ($m in $models.data) {
    Write-Host ("  - " + $m.id)
}
Write-Host ""

# Try each model
foreach ($modelId in @("deepseek-coder-v2-lite-instruct", "openai/gpt-oss-20b", "zai-org/glm-4.7-flash", "nvidia/nemotron-3-nano")) {
    Write-Host ("=== TEST M2: $modelId ===")
    try {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $body = @{
            model = $modelId
            input = "Dis bonjour en francais, sois concis."
            temperature = 0.5
            max_output_tokens = 64
            stream = $false
            store = $false
        } | ConvertTo-Json -Depth 4

        $r = Invoke-RestMethod -Uri "http://192.168.1.26:1234/api/v1/chat" -Method POST -ContentType "application/json" -Headers $M2_Headers -Body $body -TimeoutSec 60
        $sw.Stop()
        Write-Host ("  OK! Temps: " + $sw.ElapsedMilliseconds + "ms")
        $content = if ($r.output.Count -gt 0) { $r.output[0].content } else { "(output vide)" }
        if ($content.Length -gt 150) { $content = $content.Substring(0, 150) + "..." }
        Write-Host ("  Reponse: " + $content)
        Write-Host ("  Tokens: " + $r.stats.total_output_tokens + " output, " + $r.stats.input_tokens + " input")
    } catch {
        Write-Host ("  ERREUR: " + $_.Exception.Message)
    }
    Write-Host ""
}
