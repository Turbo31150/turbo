# ═══════════════════════════════════════════════════════════════
# TEST PERFORMANCE — LM Studio Native API /api/v1/chat
# ═══════════════════════════════════════════════════════════════

$M1_Headers = @{ Authorization = "Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7" }
$M2_Headers = @{ Authorization = "Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4" }

# Test 1 — M1 qwen3-30b simple
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$body = @{
    model = "qwen/qwen3-30b-a3b-2507"
    input = "Dis bonjour et donne l'heure"
    system_prompt = "Tu es JARVIS, assistant IA. Reponds en francais, sois concis."
    temperature = 0.5
    max_output_tokens = 128
    stream = $false
    store = $false
} | ConvertTo-Json -Depth 4

$r = Invoke-RestMethod -Uri "http://10.5.0.2:1234/api/v1/chat" -Method POST -ContentType "application/json" -Headers $M1_Headers -Body $body -TimeoutSec 30
$sw.Stop()

Write-Host "=== TEST PERFORMANCE M1 - qwen3-30b ==="
Write-Host ("Temps: " + $sw.ElapsedMilliseconds + "ms")
$content = if ($r.output.Count -gt 0) { $r.output[0].content } else { "(output vide)" }
Write-Host ("Reponse: " + $content.Substring(0, [Math]::Min(200, $content.Length)))
Write-Host ("Tokens: " + $r.stats.total_output_tokens + " output, " + $r.stats.input_tokens + " input")
Write-Host ""

# Test 2 — M1 identification commande
$sw2 = [System.Diagnostics.Stopwatch]::StartNew()
$body2 = @{
    model = "qwen/qwen3-30b-a3b-2507"
    input = "ouvre chrome et va sur youtube"
    system_prompt = "Tu es le cerveau local de JARVIS v10.1. Tu connais 450 commandes vocales, 77 skills et 73 outils MCP. Identifie la commande ou le skill qui correspond. Reponds: COMMANDE: nom ou SKILL: nom."
    temperature = 0.5
    max_output_tokens = 256
    stream = $false
    store = $false
} | ConvertTo-Json -Depth 4

$r2 = Invoke-RestMethod -Uri "http://10.5.0.2:1234/api/v1/chat" -Method POST -ContentType "application/json" -Headers $M1_Headers -Body $body2 -TimeoutSec 30
$sw2.Stop()

Write-Host "=== TEST 2 - Identification commande ==="
Write-Host ("Temps: " + $sw2.ElapsedMilliseconds + "ms")
$content2 = if ($r2.output.Count -gt 0) { $r2.output[0].content } else { "(output vide)" }
Write-Host ("Reponse: " + $content2.Substring(0, [Math]::Min(300, $content2.Length)))
Write-Host ("Tokens: " + $r2.stats.total_output_tokens + " output, " + $r2.stats.input_tokens + " input")
Write-Host ""

# Test 3 — M2 deepseek-coder
Write-Host "=== TEST M2 (192.168.1.26:1234) ==="
try {
    $sw3 = [System.Diagnostics.Stopwatch]::StartNew()
    $body3 = @{
        model = "deepseek-coder-v2-lite-instruct"
        input = "Dis bonjour en francais."
        temperature = 0.5
        max_output_tokens = 64
        stream = $false
        store = $false
    } | ConvertTo-Json -Depth 4

    $r3 = Invoke-RestMethod -Uri "http://192.168.1.26:1234/api/v1/chat" -Method POST -ContentType "application/json" -Headers $M2_Headers -Body $body3 -TimeoutSec 30
    $sw3.Stop()
    Write-Host ("Temps: " + $sw3.ElapsedMilliseconds + "ms")
    $content3 = if ($r3.output.Count -gt 0) { $r3.output[0].content } else { "(output vide)" }
    if ($content3.Length -gt 200) { $content3 = $content3.Substring(0, 200) + "..." }
    Write-Host ("Reponse: " + $content3)
    Write-Host ("Tokens: " + $r3.stats.total_output_tokens + " output, " + $r3.stats.input_tokens + " input")
} catch {
    Write-Host ("ERREUR M2: " + $_.Exception.Message)
}
