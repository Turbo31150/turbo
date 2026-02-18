# Check M2 models
Write-Host "=== M2 MODELS ==="
$models = Invoke-RestMethod -Uri "http://192.168.1.26:1234/v1/models" -TimeoutSec 5
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
            messages = @(
                @{role = "system"; content = "Tu es un assistant IA. Reponds en francais, sois concis."},
                @{role = "user"; content = "Dis bonjour"}
            )
            temperature = 0.5
            max_tokens = 64
        } | ConvertTo-Json -Depth 4

        $r = Invoke-RestMethod -Uri "http://192.168.1.26:1234/v1/chat/completions" -Method POST -ContentType "application/json" -Body $body -TimeoutSec 60
        $sw.Stop()
        Write-Host ("  OK! Temps: " + $sw.ElapsedMilliseconds + "ms")
        $content = $r.choices[0].message.content
        if ($content.Length -gt 150) { $content = $content.Substring(0, 150) + "..." }
        Write-Host ("  Reponse: " + $content)
        Write-Host ("  Tokens: " + $r.usage.completion_tokens + " completion, " + $r.usage.prompt_tokens + " prompt")
    } catch {
        Write-Host ("  ERREUR: " + $_.Exception.Message)
    }
    Write-Host ""
}
