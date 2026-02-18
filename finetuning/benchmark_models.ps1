###############################################################################
# JARVIS — Benchmark Multi-Modeles LM Studio
# Teste tous les modeles GGUF et compare latence / qualite
# Usage: powershell -File benchmark_models.ps1
###############################################################################

$LMS = "C:\Users\franc\.lmstudio\bin\lms.exe"
$API = "http://10.5.0.2:1234/v1"
$RESULTS_FILE = "F:\BUREAU\turbo\finetuning\benchmark_results.json"

# Modeles a tester (exclure les blacklistes et trop gros)
$Models = @(
    @{ Name = "qwen3-30b-a3b-instruct-2507";   Category = "general";   VRAM = "18GB" }
    @{ Name = "qwen3-coder-30b-a3b-instruct";   Category = "code";      VRAM = "18GB" }
    @{ Name = "gpt-oss-20b";                     Category = "general";   VRAM = "12GB" }
    @{ Name = "devstral-small-2-24b-instruct";   Category = "code";      VRAM = "14GB" }
    @{ Name = "deepseek-r1-0528-qwen3-8b";       Category = "reasoning"; VRAM = "5GB"  }
    @{ Name = "gemma-3-12b-it";                   Category = "general";   VRAM = "7GB"  }
    @{ Name = "ministral-3-14b-reasoning-2512";   Category = "reasoning"; VRAM = "8GB"  }
    @{ Name = "qwen3-vl-8b-instruct";             Category = "vision";    VRAM = "5GB"  }
)

# Prompts de test par categorie
$TestPrompts = @{
    "general" = @(
        "Explique en 3 phrases ce qu'est le machine learning.",
        "Quels sont les 5 langages de programmation les plus utilises en 2025 ?",
        "Traduis en anglais: 'Le systeme JARVIS utilise un cluster multi-GPU pour l''inference locale.'"
    )
    "code" = @(
        "Ecris une fonction Python qui trie une liste de dictionnaires par une cle donnee.",
        "Corrige ce code: def fib(n): return fib(n-1) + fib(n-2)",
        "Ecris un script PowerShell qui liste les processus utilisant plus de 1 GB de RAM."
    )
    "reasoning" = @(
        "Un train part de Paris a 8h a 200km/h. Un autre part de Lyon (450km) a 9h a 250km/h. A quelle heure se croisent-ils ?",
        "Si tous les chats sont des animaux et certains animaux sont noirs, peut-on conclure que certains chats sont noirs ?",
        "Decompose etape par etape: comment optimiser un modele de trading qui a un ratio de Sharpe de 0.8 ?"
    )
    "vision" = @(
        "Decris ce que tu vois dans cette image de bureau Windows avec 5 fenetres ouvertes."
    )
}

$AllResults = @()

foreach ($model in $Models) {
    $modelName = $model.Name
    $category = $model.Category

    Write-Host "`n$('='*60)" -ForegroundColor Cyan
    Write-Host "Test: $modelName ($category)" -ForegroundColor Cyan
    Write-Host "$('='*60)" -ForegroundColor Cyan

    # Charger le modele
    Write-Host "[...] Chargement $modelName..."
    $loadStart = Get-Date
    & $LMS load $modelName --yes 2>&1 | Out-Null
    Start-Sleep 5

    # Verifier que le modele est charge
    $loaded = & $LMS ps 2>&1
    if ($loaded -notmatch $modelName) {
        Write-Host "[SKIP] Echec chargement $modelName" -ForegroundColor Red
        continue
    }

    $loadTime = ((Get-Date) - $loadStart).TotalSeconds
    Write-Host "[OK] Charge en $([math]::Round($loadTime, 1))s"

    # Tester avec les prompts de sa categorie
    $prompts = $TestPrompts[$category]
    $modelResults = @()

    foreach ($prompt in $prompts) {
        Write-Host "`n  Prompt: $($prompt.Substring(0, [math]::Min(60, $prompt.Length)))..."

        $body = @{
            model = $modelName
            messages = @(
                @{ role = "user"; content = $prompt }
            )
            max_tokens = 500
            temperature = 0.7
        } | ConvertTo-Json -Depth 5

        $start = Get-Date
        try {
            $response = Invoke-RestMethod -Uri "$API/chat/completions" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 60
            $elapsed = ((Get-Date) - $start).TotalSeconds
            $tokens = $response.usage.completion_tokens
            $tps = if ($elapsed -gt 0) { [math]::Round($tokens / $elapsed, 1) } else { 0 }
            $answer = $response.choices[0].message.content

            Write-Host "  Temps: $([math]::Round($elapsed, 1))s | Tokens: $tokens | TPS: $tps" -ForegroundColor Green
            Write-Host "  Reponse: $($answer.Substring(0, [math]::Min(100, $answer.Length)))..."

            $modelResults += @{
                prompt = $prompt
                time_s = [math]::Round($elapsed, 2)
                tokens = $tokens
                tps = $tps
                answer_preview = $answer.Substring(0, [math]::Min(200, $answer.Length))
            }
        } catch {
            Write-Host "  [ERREUR] $($_.Exception.Message)" -ForegroundColor Red
            $modelResults += @{
                prompt = $prompt
                error = $_.Exception.Message
            }
        }
    }

    # Calculer les moyennes
    $validResults = $modelResults | Where-Object { $_.tps -gt 0 }
    $avgTPS = if ($validResults.Count -gt 0) {
        [math]::Round(($validResults | ForEach-Object { $_.tps } | Measure-Object -Average).Average, 1)
    } else { 0 }
    $avgTime = if ($validResults.Count -gt 0) {
        [math]::Round(($validResults | ForEach-Object { $_.time_s } | Measure-Object -Average).Average, 2)
    } else { 0 }

    Write-Host "`n  --- Resultats $modelName ---" -ForegroundColor Yellow
    Write-Host "  Moyenne TPS: $avgTPS | Moyenne temps: ${avgTime}s | Load: ${loadTime}s"

    $AllResults += @{
        model = $modelName
        category = $category
        vram = $model.VRAM
        load_time_s = [math]::Round($loadTime, 1)
        avg_tps = $avgTPS
        avg_time_s = $avgTime
        tests = $modelResults
    }

    # Decharger le modele
    Write-Host "[...] Dechargement $modelName..."
    & $LMS unload $modelName --yes 2>&1 | Out-Null
    Start-Sleep 3
}

# Sauvegarder les resultats
$AllResults | ConvertTo-Json -Depth 10 | Set-Content $RESULTS_FILE -Encoding UTF8
Write-Host "`n$('='*60)" -ForegroundColor Green
Write-Host "Benchmark termine ! Resultats: $RESULTS_FILE" -ForegroundColor Green

# Afficher le classement
Write-Host "`n=== CLASSEMENT ===" -ForegroundColor Cyan
$sorted = $AllResults | Sort-Object { $_.avg_tps } -Descending
foreach ($r in $sorted) {
    $stars = "*" * [math]::Min([int]($r.avg_tps / 5), 10)
    Write-Host "  $($r.model.PadRight(40)) | TPS: $($r.avg_tps.ToString().PadLeft(6)) | $stars"
}
