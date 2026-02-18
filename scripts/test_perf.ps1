$sw = [System.Diagnostics.Stopwatch]::StartNew()
$body = @{
    model = "qwen/qwen3-30b-a3b-2507"
    messages = @(
        @{role = "system"; content = "Tu es JARVIS, assistant IA. Reponds en francais, sois concis."},
        @{role = "user"; content = "Dis bonjour et donne l'heure"}
    )
    temperature = 0.5
    max_tokens = 128
} | ConvertTo-Json -Depth 4

$r = Invoke-RestMethod -Uri "http://10.5.0.2:1234/v1/chat/completions" -Method POST -ContentType "application/json" -Body $body -TimeoutSec 30
$sw.Stop()

Write-Host "=== TEST PERFORMANCE M1 - qwen3-30b ==="
Write-Host ("Temps: " + $sw.ElapsedMilliseconds + "ms")
Write-Host ("Reponse: " + $r.choices[0].message.content.Substring(0, [Math]::Min(200, $r.choices[0].message.content.Length)))
Write-Host ("Tokens: " + $r.usage.completion_tokens + " completion, " + $r.usage.prompt_tokens + " prompt")
Write-Host ""

# Test 2 - requete plus complexe (knowledge base)
$sw2 = [System.Diagnostics.Stopwatch]::StartNew()
$body2 = @{
    model = "qwen/qwen3-30b-a3b-2507"
    messages = @(
        @{role = "system"; content = "Tu es le cerveau local de JARVIS v10.1. Tu connais 450 commandes vocales, 77 skills et 73 outils MCP. Identifie la commande ou le skill qui correspond. Reponds: COMMANDE: nom ou SKILL: nom."},
        @{role = "user"; content = "ouvre chrome et va sur youtube"}
    )
    temperature = 0.5
    max_tokens = 256
} | ConvertTo-Json -Depth 4

$r2 = Invoke-RestMethod -Uri "http://10.5.0.2:1234/v1/chat/completions" -Method POST -ContentType "application/json" -Body $body2 -TimeoutSec 30
$sw2.Stop()

Write-Host "=== TEST 2 - Identification commande ==="
Write-Host ("Temps: " + $sw2.ElapsedMilliseconds + "ms")
Write-Host ("Reponse: " + $r2.choices[0].message.content.Substring(0, [Math]::Min(300, $r2.choices[0].message.content.Length)))
Write-Host ("Tokens: " + $r2.usage.completion_tokens + " completion, " + $r2.usage.prompt_tokens + " prompt")
Write-Host ""

# Test 3 - M2 si accessible
Write-Host "=== TEST M2 (192.168.1.26:1234) ==="
try {
    $sw3 = [System.Diagnostics.Stopwatch]::StartNew()
    $body3 = @{
        model = "openai/gpt-oss-20b"
        messages = @(
            @{role = "system"; content = "Tu es un assistant IA. Reponds en francais."},
            @{role = "user"; content = "Dis bonjour"}
        )
        temperature = 0.5
        max_tokens = 64
    } | ConvertTo-Json -Depth 4

    $r3 = Invoke-RestMethod -Uri "http://192.168.1.26:1234/v1/chat/completions" -Method POST -ContentType "application/json" -Body $body3 -TimeoutSec 30
    $sw3.Stop()
    Write-Host ("Temps: " + $sw3.ElapsedMilliseconds + "ms")
    Write-Host ("Reponse: " + $r3.choices[0].message.content.Substring(0, [Math]::Min(200, $r3.choices[0].message.content.Length)))
    Write-Host ("Tokens: " + $r3.usage.completion_tokens + " completion, " + $r3.usage.prompt_tokens + " prompt")
} catch {
    Write-Host ("ERREUR M2: " + $_.Exception.Message)
}
