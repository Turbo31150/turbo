# ============================================================================
# SCANNER PRO UNIFIE v3.0 + CQ PIPELINE v5.0 - MODULE PRINCIPAL
# Indicateurs: RSI, StochRSI, ADX/DMI, MACD, OBV, Chaikin, EMA, Pivots, Fib
# CQ: Contextual Quotient - 8 modeles, 3 stages, poids adaptatifs, self-correction
# Scoring composite 0-125 | Multi-TF | IA + CQ | Telegram | Database
# Autonomous mode | Market Regime | Predictions tracking | Adaptive weights
# ============================================================================

# --- CONFIGURATION ---
$script:MEXC_API = "https://contract.mexc.com/api/v1/contract"
$script:TELEGRAM_TOKEN = $global:TELEGRAM_TOKEN
$script:TELEGRAM_CHAT = $global:TELEGRAM_CHAT
$script:SQL_DB = if ($global:SQL_DATABASE) { $global:SQL_DATABASE } else { "F:\BUREAU\laaaaaaaaaaaa\database\trading.db" }
$script:LM_STUDIO_URL = if ($global:LM_STUDIO_URL) { $global:LM_STUDIO_URL } else { "http://127.0.0.1:1234" }

# --- CQ CLUSTER CONFIG ---
$script:CQ_CLUSTER = @{
    M1 = @{ URL = 'http://192.168.1.85:1234';  Models = @('qwen/qwen3-30b-a3b-2507', 'openai/gpt-oss-20b', 'nvidia/nemotron-3-nano', 'zai-org/glm-4.7-flash', 'qwen/qwen3-coder-30b', 'mistralai/devstral-small-2-2512'); Weight = 1.3; Role = 'deep' }
    M2 = @{ URL = 'http://192.168.1.26:1234';  Models = @('nvidia/nemotron-3-nano', 'openai/gpt-oss-20b', 'zai-org/glm-4.7-flash', 'deepseek-coder-v2-lite-instruct');  Weight = 1.0; Role = 'fast' }
    M3 = @{ URL = 'http://192.168.1.113:1234'; Models = @('nvidia/nemotron-3-nano', 'openai/gpt-oss-20b', 'mistral-7b-instruct-v0.3', 'phi-3.1-mini-128k-instruct');  Weight = 0.8; Role = 'validate' }
}
$script:CQ_SYSTEM_PROMPT = "Tu es un trader crypto expert. Reponds au format: DIRECTION confiance/10 raison. Exemple: LONG 8/10 breakout confirme"
$script:CQ_MODELS_NO_SYSTEM = @('mistral-7b-instruct-v0.3', 'phi-3.1-mini-128k-instruct')

# ============================================================================
# SECTION A: FONCTIONS UTILITAIRES
# ============================================================================

function Get-MexcTickers {
    <#
    .SYNOPSIS Recupere tous les tickers futures MEXC, filtre par volume minimum.
    #>
    param([double]$MinVolume = 100000)

    $response = Invoke-RestMethod -Uri "$script:MEXC_API/ticker" -TimeoutSec 15
    $parsed = @()
    foreach ($t in $response.data) {
        $vol = [double]$t.volume24
        $last = [double]$t.lastPrice
        if ($vol -gt $MinVolume -and $last -gt 0) {
            $change = [double]$t.riseFallRate * 100
            $parsed += [PSCustomObject]@{
                Symbol      = $t.symbol
                Prix        = $last
                Change      = [math]::Round($change, 2)
                Volume      = [math]::Round($vol, 0)
                Bid         = $t.bid1
                Ask         = $t.ask1
                FundingRate = $t.fundingRate
            }
        }
    }
    return $parsed
}

function Get-MexcKlines {
    <#
    .SYNOPSIS Recupere les klines MEXC et retourne des arrays paralleles convertis en doubles.
    .PARAMETER Symbol  Ex: 'HYPE_USDT'
    .PARAMETER Interval  Min15, Min60, Hour4
    .PARAMETER Limit  Nombre de bougies
    #>
    param(
        [string]$Symbol,
        [string]$Interval = 'Min60',
        [int]$Limit = 48
    )

    $url = "$script:MEXC_API/kline/${Symbol}?interval=${Interval}&limit=${Limit}"
    $kl = (Invoke-RestMethod -Uri $url -TimeoutSec 10).data

    if (-not $kl.close -or $kl.close.Count -lt 3) { return $null }

    $closes = [double[]]::new($kl.close.Count)
    $highs  = [double[]]::new($kl.high.Count)
    $lows   = [double[]]::new($kl.low.Count)
    $opens  = [double[]]::new($kl.open.Count)
    $vols   = [double[]]::new($kl.vol.Count)

    for ($i = 0; $i -lt $kl.close.Count; $i++) {
        $closes[$i] = [double]$kl.close[$i]
        $highs[$i]  = [double]$kl.high[$i]
        $lows[$i]   = [double]$kl.low[$i]
        $opens[$i]  = [double]$kl.open[$i]
        $vols[$i]   = [double]$kl.vol[$i]
    }

    return @{
        closes = $closes
        highs  = $highs
        lows   = $lows
        opens  = $opens
        vols   = $vols
        count  = $closes.Count
    }
}

# ============================================================================
# SECTION B: INDICATEURS TECHNIQUES
# ============================================================================

function Get-SMA {
    param([double[]]$Data, [int]$Period)
    if ($Data.Count -lt $Period) { return $null }
    $sum = 0.0
    for ($i = $Data.Count - $Period; $i -lt $Data.Count; $i++) { $sum += $Data[$i] }
    return $sum / $Period
}

function Get-EMA {
    <#
    .SYNOPSIS Calcule l'EMA sur un tableau de données.
    #>
    param([double[]]$Data, [int]$Period)
    if ($Data.Count -lt $Period) { return $null }

    $mult = 2.0 / ($Period + 1)
    # Seed: SMA des $Period premières valeurs
    $sum = 0.0
    for ($i = 0; $i -lt $Period; $i++) { $sum += $Data[$i] }
    $ema = $sum / $Period

    for ($i = $Period; $i -lt $Data.Count; $i++) {
        $ema = ($Data[$i] - $ema) * $mult + $ema
    }
    return [math]::Round($ema, 10)
}

function Get-EMAAlignment {
    <#
    .SYNOPSIS Retourne EMA 5/10/20 et status d'alignement.
    #>
    param([double[]]$Closes)

    $ema5  = Get-EMA -Data $Closes -Period 5
    $ema10 = Get-EMA -Data $Closes -Period 10
    $ema20 = Get-EMA -Data $Closes -Period 20

    $status = "MIXED"
    if ($ema5 -and $ema10 -and $ema20) {
        if ($ema5 -gt $ema10 -and $ema10 -gt $ema20) { $status = "BULL_ALIGN" }
        elseif ($ema5 -lt $ema10 -and $ema10 -lt $ema20) { $status = "BEAR_ALIGN" }
        elseif ($ema5 -gt $ema10) { $status = "BULL_CROSS" }
        elseif ($ema5 -lt $ema10) { $status = "BEAR_CROSS" }
    }

    return @{
        EMA5   = $ema5
        EMA10  = $ema10
        EMA20  = $ema20
        Status = $status
    }
}

function Get-RSI {
    <#
    .SYNOPSIS RSI classique (Wilder) sur N périodes.
    #>
    param([double[]]$Closes, [int]$Period = 14)
    if ($Closes.Count -lt ($Period + 1)) { return 50 }

    $avgGain = 0.0
    $avgLoss = 0.0
    # Première moyenne (SMA)
    for ($i = 1; $i -le $Period; $i++) {
        $diff = $Closes[$i] - $Closes[$i - 1]
        if ($diff -ge 0) { $avgGain += $diff } else { $avgLoss += [math]::Abs($diff) }
    }
    $avgGain /= $Period
    $avgLoss /= $Period

    # Smoothing Wilder
    for ($i = $Period + 1; $i -lt $Closes.Count; $i++) {
        $diff = $Closes[$i] - $Closes[$i - 1]
        $gain = if ($diff -ge 0) { $diff } else { 0 }
        $loss = if ($diff -lt 0) { [math]::Abs($diff) } else { 0 }
        $avgGain = ($avgGain * ($Period - 1) + $gain) / $Period
        $avgLoss = ($avgLoss * ($Period - 1) + $loss) / $Period
    }

    if ($avgLoss -eq 0) { return if ($avgGain -gt 0) { 100 } else { 50 } }
    $rs = $avgGain / $avgLoss
    return [math]::Round(100 - (100 / (1 + $rs)), 1)
}

function Get-RSISeries {
    <#
    .SYNOPSIS Retourne un tableau de valeurs RSI pour chaque point (utile pour StochRSI).
    #>
    param([double[]]$Closes, [int]$Period = 14)
    if ($Closes.Count -lt ($Period + 1)) { return @() }

    $rsiValues = @()
    $avgGain = 0.0
    $avgLoss = 0.0

    for ($i = 1; $i -le $Period; $i++) {
        $diff = $Closes[$i] - $Closes[$i - 1]
        if ($diff -ge 0) { $avgGain += $diff } else { $avgLoss += [math]::Abs($diff) }
    }
    $avgGain /= $Period
    $avgLoss /= $Period

    if ($avgLoss -eq 0) {
        $rsiValues += if ($avgGain -gt 0) { 100.0 } else { 50.0 }
    } else {
        $rsiValues += [math]::Round(100 - (100 / (1 + ($avgGain / $avgLoss))), 4)
    }

    for ($i = $Period + 1; $i -lt $Closes.Count; $i++) {
        $diff = $Closes[$i] - $Closes[$i - 1]
        $gain = if ($diff -ge 0) { $diff } else { 0 }
        $loss = if ($diff -lt 0) { [math]::Abs($diff) } else { 0 }
        $avgGain = ($avgGain * ($Period - 1) + $gain) / $Period
        $avgLoss = ($avgLoss * ($Period - 1) + $loss) / $Period
        if ($avgLoss -eq 0) {
            $rsiValues += if ($avgGain -gt 0) { 100.0 } else { 50.0 }
        } else {
            $rsiValues += [math]::Round(100 - (100 / (1 + ($avgGain / $avgLoss))), 4)
        }
    }
    return $rsiValues
}

function Get-StochRSI {
    <#
    .SYNOPSIS RSI Stochastique (14,14,3,3).
    Retourne %K, %D, et signal (OVERSOLD_BUY, OVERBOUGHT_SELL, CROSS_UP, CROSS_DOWN, NEUTRAL).
    #>
    param([double[]]$Closes, [int]$RSIPeriod = 14, [int]$StochPeriod = 14, [int]$KSmooth = 3, [int]$DSmooth = 3)

    $rsiSeries = Get-RSISeries -Closes $Closes -Period $RSIPeriod
    if ($rsiSeries.Count -lt $StochPeriod) {
        return @{ K = 50; D = 50; Signal = "NEUTRAL"; Raw = 0.5 }
    }

    # Calcul StochRSI brut
    $stochRaw = @()
    for ($i = $StochPeriod - 1; $i -lt $rsiSeries.Count; $i++) {
        $window = $rsiSeries[($i - $StochPeriod + 1)..$i]
        $rsiMin = ($window | Measure-Object -Minimum).Minimum
        $rsiMax = ($window | Measure-Object -Maximum).Maximum
        if (($rsiMax - $rsiMin) -eq 0) { $stochRaw += 0.5 }
        else { $stochRaw += ($rsiSeries[$i] - $rsiMin) / ($rsiMax - $rsiMin) }
    }

    if ($stochRaw.Count -lt $KSmooth) {
        return @{ K = 50; D = 50; Signal = "NEUTRAL"; Raw = 0.5 }
    }

    # %K = SMA du StochRSI brut
    $kValues = @()
    for ($i = $KSmooth - 1; $i -lt $stochRaw.Count; $i++) {
        $window = $stochRaw[($i - $KSmooth + 1)..$i]
        $kValues += ($window | Measure-Object -Average).Average
    }

    # %D = SMA de %K
    $dValues = @()
    if ($kValues.Count -ge $DSmooth) {
        for ($i = $DSmooth - 1; $i -lt $kValues.Count; $i++) {
            $window = $kValues[($i - $DSmooth + 1)..$i]
            $dValues += ($window | Measure-Object -Average).Average
        }
    }

    $k = [math]::Round($kValues[-1] * 100, 1)
    $d = if ($dValues.Count -gt 0) { [math]::Round($dValues[-1] * 100, 1) } else { $k }

    # Signal
    $signal = "NEUTRAL"
    $prevK = if ($kValues.Count -ge 2) { [math]::Round($kValues[-2] * 100, 1) } else { $k }
    $prevD = if ($dValues.Count -ge 2) { [math]::Round($dValues[-2] * 100, 1) } else { $d }

    if ($k -lt 20) { $signal = "OVERSOLD_BUY" }
    elseif ($k -gt 80) { $signal = "OVERBOUGHT_SELL" }

    if ($prevK -le $prevD -and $k -gt $d -and $k -lt 50) { $signal = "CROSS_UP" }
    elseif ($prevK -ge $prevD -and $k -lt $d -and $k -gt 50) { $signal = "CROSS_DOWN" }

    return @{ K = $k; D = $d; Signal = $signal; Raw = $kValues[-1] }
}

function Get-ATR {
    <#
    .SYNOPSIS Average True Range.
    #>
    param([double[]]$Highs, [double[]]$Lows, [double[]]$Closes, [int]$Period = 14)
    if ($Closes.Count -lt ($Period + 1)) { return 0 }

    $trValues = @()
    for ($i = 1; $i -lt $Closes.Count; $i++) {
        $tr1 = $Highs[$i] - $Lows[$i]
        $tr2 = [math]::Abs($Highs[$i] - $Closes[$i - 1])
        $tr3 = [math]::Abs($Lows[$i] - $Closes[$i - 1])
        $trValues += [math]::Max($tr1, [math]::Max($tr2, $tr3))
    }

    # ATR Wilder smoothing
    $sum = 0.0
    for ($i = 0; $i -lt $Period; $i++) { $sum += $trValues[$i] }
    $atr = $sum / $Period
    for ($i = $Period; $i -lt $trValues.Count; $i++) {
        $atr = ($atr * ($Period - 1) + $trValues[$i]) / $Period
    }
    return $atr
}

function Get-ADX-DMI {
    <#
    .SYNOPSIS ADX + Directional Movement Index (14 periodes).
    Retourne ADX, +DI, -DI, signal de tendance.
    #>
    param([double[]]$Highs, [double[]]$Lows, [double[]]$Closes, [int]$Period = 14)

    if ($Closes.Count -lt ($Period + 2)) {
        return @{ ADX = 0; PlusDI = 0; MinusDI = 0; Signal = "NO_DATA"; Trend = "NONE" }
    }

    $plusDM = @()
    $minusDM = @()
    $trValues = @()

    for ($i = 1; $i -lt $Highs.Count; $i++) {
        $upMove = $Highs[$i] - $Highs[$i - 1]
        $downMove = $Lows[$i - 1] - $Lows[$i]

        if ($upMove -gt $downMove -and $upMove -gt 0) { $plusDM += $upMove } else { $plusDM += 0 }
        if ($downMove -gt $upMove -and $downMove -gt 0) { $minusDM += $downMove } else { $minusDM += 0 }

        $tr1 = $Highs[$i] - $Lows[$i]
        $tr2 = [math]::Abs($Highs[$i] - $Closes[$i - 1])
        $tr3 = [math]::Abs($Lows[$i] - $Closes[$i - 1])
        $trValues += [math]::Max($tr1, [math]::Max($tr2, $tr3))
    }

    if ($trValues.Count -lt $Period) {
        return @{ ADX = 0; PlusDI = 0; MinusDI = 0; Signal = "NO_DATA"; Trend = "NONE" }
    }

    # Wilder smoothing pour +DM, -DM, TR
    $smoothPlusDM = 0.0; $smoothMinusDM = 0.0; $smoothTR = 0.0
    for ($i = 0; $i -lt $Period; $i++) {
        $smoothPlusDM += $plusDM[$i]
        $smoothMinusDM += $minusDM[$i]
        $smoothTR += $trValues[$i]
    }

    $dxValues = @()
    for ($i = $Period; $i -lt $trValues.Count; $i++) {
        $smoothPlusDM = $smoothPlusDM - ($smoothPlusDM / $Period) + $plusDM[$i]
        $smoothMinusDM = $smoothMinusDM - ($smoothMinusDM / $Period) + $minusDM[$i]
        $smoothTR = $smoothTR - ($smoothTR / $Period) + $trValues[$i]

        $pdi = if ($smoothTR -gt 0) { 100 * $smoothPlusDM / $smoothTR } else { 0 }
        $mdi = if ($smoothTR -gt 0) { 100 * $smoothMinusDM / $smoothTR } else { 0 }

        $diSum = $pdi + $mdi
        $dx = if ($diSum -gt 0) { 100 * [math]::Abs($pdi - $mdi) / $diSum } else { 0 }
        $dxValues += @{ DX = $dx; PDI = $pdi; MDI = $mdi }
    }

    if ($dxValues.Count -lt $Period) {
        $lastDX = $dxValues[-1]
        return @{
            ADX     = [math]::Round($lastDX.DX, 1)
            PlusDI  = [math]::Round($lastDX.PDI, 1)
            MinusDI = [math]::Round($lastDX.MDI, 1)
            Signal  = "INSUFFICIENT"
            Trend   = "NONE"
        }
    }

    # ADX = Wilder smoothing des DX
    $adxSum = 0.0
    for ($i = 0; $i -lt $Period; $i++) { $adxSum += $dxValues[$i].DX }
    $adx = $adxSum / $Period
    for ($i = $Period; $i -lt $dxValues.Count; $i++) {
        $adx = ($adx * ($Period - 1) + $dxValues[$i].DX) / $Period
    }

    $lastEntry = $dxValues[-1]
    $pdi = [math]::Round($lastEntry.PDI, 1)
    $mdi = [math]::Round($lastEntry.MDI, 1)
    $adx = [math]::Round($adx, 1)

    # Signal
    $trend = "NONE"
    $signal = "NEUTRAL"
    if ($adx -gt 25) {
        if ($pdi -gt $mdi) { $trend = "STRONG_BULL"; $signal = "TREND_BULL" }
        else { $trend = "STRONG_BEAR"; $signal = "TREND_BEAR" }
    } elseif ($adx -gt 20) {
        if ($pdi -gt $mdi) { $trend = "BULL"; $signal = "WEAK_BULL" }
        else { $trend = "BEAR"; $signal = "WEAK_BEAR" }
    } else {
        $trend = "NO_TREND"; $signal = "RANGING"
    }

    # Croisement DI
    if ($dxValues.Count -ge 2) {
        $prev = $dxValues[-2]
        if ($prev.PDI -le $prev.MDI -and $pdi -gt $mdi) { $signal = "DI_CROSS_BULL" }
        elseif ($prev.PDI -ge $prev.MDI -and $pdi -lt $mdi) { $signal = "DI_CROSS_BEAR" }
    }

    return @{ ADX = $adx; PlusDI = $pdi; MinusDI = $mdi; Signal = $signal; Trend = $trend }
}

function Get-MACD {
    <#
    .SYNOPSIS MACD(12,26,9) avec Signal et Histogramme.
    #>
    param([double[]]$Closes, [int]$Fast = 12, [int]$Slow = 26, [int]$SignalPeriod = 9)

    if ($Closes.Count -lt $Slow) {
        return @{ MACD = 0; Signal = 0; Histogram = 0; Direction = "NEUTRAL"; CrossSignal = "NONE" }
    }

    # Calculer series EMA pour le MACD line et signal line
    $fastMult = 2.0 / ($Fast + 1)
    $slowMult = 2.0 / ($Slow + 1)
    $sigMult  = 2.0 / ($SignalPeriod + 1)

    # Seed fast EMA
    $sum = 0.0; for ($i = 0; $i -lt $Fast; $i++) { $sum += $Closes[$i] }
    $fastEMA = $sum / $Fast

    # Seed slow EMA
    $sum = 0.0; for ($i = 0; $i -lt $Slow; $i++) { $sum += $Closes[$i] }
    $slowEMA = $sum / $Slow

    $macdLine = @()
    for ($i = $Slow; $i -lt $Closes.Count; $i++) {
        $fastEMA = ($Closes[$i] - $fastEMA) * $fastMult + $fastEMA
        $slowEMA = ($Closes[$i] - $slowEMA) * $slowMult + $slowEMA
        $macdLine += ($fastEMA - $slowEMA)
    }
    # Re-run fast from scratch for accuracy
    $sum = 0.0; for ($i = 0; $i -lt $Fast; $i++) { $sum += $Closes[$i] }
    $fastEMA = $sum / $Fast
    $sum = 0.0; for ($i = 0; $i -lt $Slow; $i++) { $sum += $Closes[$i] }
    $slowEMA = $sum / $Slow
    $macdLine = @()
    for ($i = 1; $i -lt $Closes.Count; $i++) {
        $fastEMA = ($Closes[$i] - $fastEMA) * $fastMult + $fastEMA
        $slowEMA = ($Closes[$i] - $slowEMA) * $slowMult + $slowEMA
        if ($i -ge ($Slow - 1)) {
            $macdLine += ($fastEMA - $slowEMA)
        }
    }

    if ($macdLine.Count -lt $SignalPeriod) {
        $macdVal = $macdLine[-1]
        return @{ MACD = [math]::Round($macdVal, 10); Signal = 0; Histogram = [math]::Round($macdVal, 10); Direction = if ($macdVal -gt 0) {"BULLISH"} else {"BEARISH"}; CrossSignal = "NONE" }
    }

    # Signal line = EMA du MACD
    $sum = 0.0; for ($i = 0; $i -lt $SignalPeriod; $i++) { $sum += $macdLine[$i] }
    $signalEMA = $sum / $SignalPeriod
    for ($i = $SignalPeriod; $i -lt $macdLine.Count; $i++) {
        $signalEMA = ($macdLine[$i] - $signalEMA) * $sigMult + $signalEMA
    }

    $macdVal = $macdLine[-1]
    $histogram = $macdVal - $signalEMA

    # Direction et croisement
    $direction = if ($macdVal -gt 0) { "BULLISH" } else { "BEARISH" }
    $crossSignal = "NONE"
    if ($macdLine.Count -ge 2) {
        $prevMACD = $macdLine[-2]
        # Approximation signal precedent
        $sum = 0.0; for ($i = 0; $i -lt $SignalPeriod; $i++) { $sum += $macdLine[$i] }
        $prevSigEMA = $sum / $SignalPeriod
        for ($i = $SignalPeriod; $i -lt ($macdLine.Count - 1); $i++) {
            $prevSigEMA = ($macdLine[$i] - $prevSigEMA) * $sigMult + $prevSigEMA
        }
        $prevHisto = $prevMACD - $prevSigEMA
        if ($prevHisto -le 0 -and $histogram -gt 0) { $crossSignal = "BULL_CROSS" }
        elseif ($prevHisto -ge 0 -and $histogram -lt 0) { $crossSignal = "BEAR_CROSS" }
    }

    # Histogramme croissant/decroissant
    $histoTrend = "FLAT"
    if ($macdLine.Count -ge 3) {
        $h1 = $macdLine[-3] - $signalEMA  # approximation
        $h2 = $macdLine[-2] - $signalEMA
        $h3 = $histogram
        if ($h3 -gt $h2 -and $h2 -gt $h1) { $histoTrend = "RISING" }
        elseif ($h3 -lt $h2 -and $h2 -lt $h1) { $histoTrend = "FALLING" }
    }

    return @{
        MACD        = [math]::Round($macdVal, 10)
        Signal      = [math]::Round($signalEMA, 10)
        Histogram   = [math]::Round($histogram, 10)
        Direction   = $direction
        CrossSignal = $crossSignal
        HistoTrend  = $histoTrend
    }
}

function Get-OBV {
    <#
    .SYNOPSIS On Balance Volume avec trend SMA(20).
    #>
    param([double[]]$Closes, [double[]]$Volumes)
    if ($Closes.Count -lt 2) {
        return @{ OBV = 0; Trend = "NEUTRAL"; Divergence = "NONE"; SMA20 = 0 }
    }

    $obvSeries = @(0.0)
    for ($i = 1; $i -lt $Closes.Count; $i++) {
        if ($Closes[$i] -gt $Closes[$i - 1]) { $obvSeries += ($obvSeries[-1] + $Volumes[$i]) }
        elseif ($Closes[$i] -lt $Closes[$i - 1]) { $obvSeries += ($obvSeries[-1] - $Volumes[$i]) }
        else { $obvSeries += $obvSeries[-1] }
    }

    $obv = $obvSeries[-1]

    # SMA 20 de l'OBV
    $obvSMA20 = $obv
    if ($obvSeries.Count -ge 20) {
        $sum = 0.0
        for ($i = $obvSeries.Count - 20; $i -lt $obvSeries.Count; $i++) { $sum += $obvSeries[$i] }
        $obvSMA20 = $sum / 20
    }

    # Trend OBV (5 dernieres valeurs)
    $obvTrend = "NEUTRAL"
    if ($obvSeries.Count -ge 6) {
        $recent = $obvSeries[-1]
        $past = $obvSeries[-6]
        if ($recent -gt $past) { $obvTrend = "RISING" }
        elseif ($recent -lt $past) { $obvTrend = "FALLING" }
    }

    # Divergence: prix monte + OBV baisse ou inverse
    $divergence = "NONE"
    if ($Closes.Count -ge 6) {
        $priceUp = $Closes[-1] -gt $Closes[-6]
        $obvUp = $obvSeries[-1] -gt $obvSeries[-6]
        if ($priceUp -and -not $obvUp) { $divergence = "BEARISH_DIV" }
        elseif (-not $priceUp -and $obvUp) { $divergence = "BULLISH_DIV" }
    }

    return @{
        OBV        = [math]::Round($obv, 0)
        SMA20      = [math]::Round($obvSMA20, 0)
        Trend      = $obvTrend
        Divergence = $divergence
    }
}

function Get-ChaikinOscillator {
    <#
    .SYNOPSIS Chaikin Oscillator (EMA3 - EMA10 de l'ADL).
    REGLE SPECIALE:
      - Chaikin < 0 = BOTTOM / signal achat
      - Chaikin > 0 = DANGER / signal sortie
    #>
    param([double[]]$Highs, [double[]]$Lows, [double[]]$Closes, [double[]]$Volumes)

    if ($Closes.Count -lt 10) {
        return @{ Value = 0; Signal = "NEUTRAL"; Zone = "NEUTRAL"; CrossDirection = "NONE" }
    }

    # ADL (Accumulation/Distribution Line)
    $adl = @(0.0)
    for ($i = 0; $i -lt $Closes.Count; $i++) {
        $hl = $Highs[$i] - $Lows[$i]
        if ($hl -eq 0) { $mfm = 0 }
        else { $mfm = (($Closes[$i] - $Lows[$i]) - ($Highs[$i] - $Closes[$i])) / $hl }
        $mfv = $mfm * $Volumes[$i]
        $adl += ($adl[-1] + $mfv)
    }
    # Remove initial 0
    $adl = $adl[1..($adl.Count - 1)]

    if ($adl.Count -lt 10) {
        return @{ Value = 0; Signal = "NEUTRAL"; Zone = "NEUTRAL"; CrossDirection = "NONE" }
    }

    # EMA 3 et EMA 10 de l'ADL
    $adlArr = [double[]]$adl
    $ema3 = Get-EMA -Data $adlArr -Period 3
    $ema10 = Get-EMA -Data $adlArr -Period 10

    $chaikin = $ema3 - $ema10

    # Zone (regle speciale user)
    $zone = "NEUTRAL"
    if ($chaikin -lt 0) { $zone = "BOTTOM" }      # Signal achat
    elseif ($chaikin -gt 0) { $zone = "DANGER" }   # Signal sortie

    # Signal avec nuances
    $signal = "NEUTRAL"
    # Calculer le chaikin precedent pour detecter croisements et direction
    $prevChaikin = 0
    if ($adl.Count -ge 11) {
        $adlPrev = [double[]]$adl[0..($adl.Count - 2)]
        $prevEma3 = Get-EMA -Data $adlPrev -Period 3
        $prevEma10 = Get-EMA -Data $adlPrev -Period 10
        $prevChaikin = $prevEma3 - $prevEma10
    }

    $crossDir = "NONE"
    if ($prevChaikin -le 0 -and $chaikin -gt 0) { $crossDir = "CROSS_UP" }     # Croise 0 vers le haut
    elseif ($prevChaikin -ge 0 -and $chaikin -lt 0) { $crossDir = "CROSS_DOWN" } # Croise 0 vers le bas

    # Signal combine
    if ($chaikin -lt 0 -and $chaikin -gt $prevChaikin) { $signal = "BOTTOM_RISING" }      # Bottom + remontant = STRONG BUY
    elseif ($chaikin -lt 0 -and $chaikin -le $prevChaikin) { $signal = "BOTTOM_FALLING" }  # Bottom mais descendant
    elseif ($chaikin -gt 0 -and $chaikin -lt $prevChaikin) { $signal = "DANGER_FALLING" }  # Danger + descendant = EXIT
    elseif ($chaikin -gt 0 -and $chaikin -ge $prevChaikin) { $signal = "DANGER_RISING" }   # Danger + montant

    if ($crossDir -eq "CROSS_UP") { $signal = "ENTRY_SIGNAL" }
    if ($crossDir -eq "CROSS_DOWN") { $signal = "EXIT_SIGNAL" }

    return @{
        Value          = [math]::Round($chaikin, 4)
        Signal         = $signal
        Zone           = $zone
        CrossDirection = $crossDir
        PrevValue      = [math]::Round($prevChaikin, 4)
    }
}

function Get-RangePosition {
    param([double]$Price, [double]$High, [double]$Low)
    if (($High - $Low) -eq 0) { return 50 }
    return [math]::Round(($Price - $Low) / ($High - $Low) * 100, 1)
}

function Get-PivotPoints {
    param([double]$High, [double]$Low, [double]$Close)
    $pivot = ($High + $Low + $Close) / 3
    return @{
        P  = [math]::Round($pivot, 8)
        R1 = [math]::Round(2 * $pivot - $Low, 8)
        R2 = [math]::Round($pivot + ($High - $Low), 8)
        S1 = [math]::Round(2 * $pivot - $High, 8)
        S2 = [math]::Round($pivot - ($High - $Low), 8)
    }
}

function Get-Fibonacci {
    param([double]$High, [double]$Low)
    $range = $High - $Low
    return @{
        'Fib236' = [math]::Round($Low + $range * 0.236, 8)
        'Fib382' = [math]::Round($Low + $range * 0.382, 8)
        'Fib500' = [math]::Round($Low + $range * 0.5, 8)
        'Fib618' = [math]::Round($Low + $range * 0.618, 8)
        'Fib786' = [math]::Round($Low + $range * 0.786, 8)
    }
}

# ============================================================================
# SECTION C: SCORE COMPOSITE BREAKOUT v2.0 (0-100)
# ============================================================================

function Get-BreakoutScore {
    <#
    .SYNOPSIS Scoring composite v2.0+CQ integrant tous les indicateurs + consensus IA.
    Retourne score 0-115, verdict, raisons detaillees.
    #>
    param(
        [hashtable]$Indicators1H,
        [hashtable]$Indicators15M = $null,
        [hashtable]$Indicators4H = $null,
        [double]$FundingRate = 0,
        [hashtable]$CQResult = $null
    )

    $score = 0
    $reasons = @()
    $ind = $Indicators1H

    # 1. Range Position (15 pts)
    $rp = $ind.RangePos
    if ($rp -gt 85) { $score += 15; $reasons += "Range>${rp}%(breakout zone)" }
    elseif ($rp -gt 70) { $score += 10; $reasons += "Range=${rp}%(high)" }
    elseif ($rp -gt 50) { $score += 5 }

    # 2. RSI Momentum (10 pts)
    $rsi = $ind.RSI
    if ($rsi -ge 55 -and $rsi -le 75) { $score += 10; $reasons += "RSI=${rsi}(momentum)" }
    elseif ($rsi -ge 50 -and $rsi -lt 55) { $score += 5 }
    if ($rsi -gt 75) { $score -= 5; $reasons += "RSI=${rsi}(surachat penalty)" }

    # 3. StochRSI Signal (10 pts)
    $stoch = $ind.StochRSI
    if ($stoch) {
        if ($stoch.Signal -eq "CROSS_UP" -and $stoch.K -lt 30) { $score += 10; $reasons += "StochRSI cross up(${$stoch.K})" }
        elseif ($stoch.Signal -eq "OVERSOLD_BUY") { $score += 8; $reasons += "StochRSI oversold(K=$($stoch.K))" }
        elseif ($stoch.K -lt 30 -and $stoch.K -gt $stoch.D) { $score += 7; $reasons += "StochRSI remontant" }
        if ($stoch.K -gt 80) { $score -= 3; $reasons += "StochRSI surachat" }
    }

    # 4. ADX/DMI Force (10 pts)
    $adx = $ind.ADX_DMI
    if ($adx) {
        if ($adx.ADX -gt 25 -and $adx.PlusDI -gt $adx.MinusDI) { $score += 10; $reasons += "ADX=$($adx.ADX)(trend bull fort)" }
        elseif ($adx.ADX -gt 20 -and $adx.PlusDI -gt $adx.MinusDI) { $score += 7; $reasons += "ADX=$($adx.ADX)(trend bull)" }
        elseif ($adx.ADX -lt 15) { $reasons += "ADX=$($adx.ADX)(pas de tendance)" }
        if ($adx.Signal -eq "DI_CROSS_BULL") { $score += 3; $reasons += "DI+ croise DI-(bull)" }
    }

    # 5. EMA Alignment (10 pts)
    $ema = $ind.EMA
    if ($ema) {
        if ($ema.Status -eq "BULL_ALIGN") { $score += 10; $reasons += "EMA bull align(5>10>20)" }
        elseif ($ema.Status -eq "BULL_CROSS") { $score += 5; $reasons += "EMA5>EMA10" }
    }

    # 6. MACD Direction (10 pts)
    $macd = $ind.MACD
    if ($macd) {
        if ($macd.Direction -eq "BULLISH" -and $macd.HistoTrend -eq "RISING") { $score += 10; $reasons += "MACD+(histo rising)" }
        elseif ($macd.Direction -eq "BULLISH") { $score += 7; $reasons += "MACD+" }
        if ($macd.CrossSignal -eq "BULL_CROSS") { $score += 3; $reasons += "MACD bull cross" }
    }

    # 7. Volume/OBV (10 pts)
    $obv = $ind.OBV
    $volR = $ind.VolRatio
    if ($volR -gt 1.5 -and $obv -and $obv.Trend -eq "RISING") { $score += 10; $reasons += "Vol=${volR}x+OBV hausse" }
    elseif ($volR -gt 1.0 -and $obv -and $obv.Trend -eq "RISING") { $score += 7; $reasons += "Vol=${volR}x+OBV ok" }
    elseif ($volR -gt 1.5) { $score += 5; $reasons += "Vol=${volR}x" }
    if ($obv -and $obv.Divergence -eq "BEARISH_DIV") { $score -= 5; $reasons += "OBV divergence bear" }

    # 8. Chaikin Oscillator (10 pts) - REGLE SPECIALE
    $ch = $ind.Chaikin
    if ($ch) {
        if ($ch.Signal -eq "BOTTOM_RISING") { $score += 10; $reasons += "Chaikin<0 remontant(BOTTOM BUY)" }
        elseif ($ch.Signal -eq "ENTRY_SIGNAL") { $score += 8; $reasons += "Chaikin croise 0 vers haut(ENTRY)" }
        elseif ($ch.Zone -eq "BOTTOM") { $score += 5; $reasons += "Chaikin<0(bottom zone)" }
        if ($ch.Signal -eq "DANGER_FALLING") { $score -= 3; $reasons += "Chaikin>0 descendant(DANGER)" }
        if ($ch.Signal -eq "EXIT_SIGNAL") { $score -= 5; $reasons += "Chaikin croise 0 vers bas(EXIT)" }
        if ($ch.Zone -eq "DANGER" -and $ch.Value -gt $ch.PrevValue) { $score -= 3; $reasons += "Chaikin>0 montant(surachat)" }
    }

    # 9. Multi-Timeframe (10 pts)
    $tfBull = 0
    if ($ind.RangePos -gt 55 -and $ind.RSI -gt 45) { $tfBull++ }
    if ($Indicators15M -and $Indicators15M.RangePos -gt 55 -and $Indicators15M.RSI -gt 45) { $tfBull++ }
    if ($Indicators4H -and $Indicators4H.RangePos -gt 50 -and $Indicators4H.RSI -gt 45) { $tfBull++ }
    if ($tfBull -ge 3) { $score += 10; $reasons += "3/3 TF bullish" }
    elseif ($tfBull -ge 2) { $score += 5; $reasons += "${tfBull}/3 TF bullish" }

    # 10. Funding Rate (5 pts)
    if ($FundingRate -ne 0) {
        $fr = [double]$FundingRate
        if ($fr -lt 0) { $score += 5; $reasons += "Funding negatif(squeeze potential)" }
        elseif ($fr -gt 0.0005) { $score -= 3; $reasons += "Funding>0.05%(surleverage)" }
    }

    # 11. CQ Consensus (25 pts) - Pipeline 8 modeles v5.0
    if ($CQResult -and $CQResult.Success) {
        $cqDir = $CQResult.Consensus
        $cqConf = $CQResult.Confidence
        $cqModels = $CQResult.Models
        if ($cqDir -eq 'LONG' -and $cqConf -ge 75 -and $cqModels -ge 6) {
            $score += 25; $reasons += "CQ LONG conf=${cqConf}%(${cqModels} IAs,high)"
        } elseif ($cqDir -eq 'LONG' -and $cqConf -ge 65) {
            $score += 18; $reasons += "CQ LONG conf=${cqConf}%(${cqModels} IAs)"
        } elseif ($cqDir -eq 'LONG' -and $cqConf -ge 55) {
            $score += 12; $reasons += "CQ LONG conf=${cqConf}%"
        } elseif ($cqDir -eq 'LONG') {
            $score += 5; $reasons += "CQ LONG faible(${cqConf}%)"
        } elseif ($cqDir -eq 'SHORT' -and $cqConf -ge 65) {
            $score -= 12; $reasons += "CQ SHORT conf=${cqConf}%(DANGER)"
        } elseif ($cqDir -eq 'SHORT') {
            $score -= 5; $reasons += "CQ SHORT faible(${cqConf}%)"
        }
        if ($CQResult.EarlyExit) { $score -= 8; $reasons += "CQ early exit SHORT" }
    }

    # Clamp score
    $score = [math]::Max(0, [math]::Min(125, $score))

    # Verdict (score max 125)
    $verdict = "PAS DE BREAKOUT"
    $action = "ATTENDRE"
    if ($score -ge 85) { $verdict = "BREAKOUT CONFIRME"; $action = "LONG AGRESSIF" }
    elseif ($score -ge 65) { $verdict = "BREAKOUT PROBABLE"; $action = "LONG MODERE" }
    elseif ($score -ge 45) { $verdict = "MOMENTUM HAUSSIER"; $action = "LONG PRUDENT" }
    elseif ($score -ge 30) { $verdict = "EN CONSTRUCTION"; $action = "SURVEILLER" }

    return @{
        Score   = $score
        Verdict = $verdict
        Action  = $action
        Reasons = $reasons
    }
}

# ============================================================================
# SECTION D: CALCUL COMPLET D'INDICATEURS POUR UN KLINE SET
# ============================================================================

function Get-AllIndicators {
    <#
    .SYNOPSIS Calcule tous les indicateurs sur un set de klines.
    #>
    param([hashtable]$Klines, [double]$LastPrice)

    $c = $Klines.closes
    $h = $Klines.highs
    $l = $Klines.lows
    $v = $Klines.vols

    $high = ($h | Measure-Object -Maximum).Maximum
    $low  = ($l | Measure-Object -Minimum).Minimum
    $totalVol = ($v | Measure-Object -Sum).Sum
    $avgVol = ($v | Measure-Object -Average).Average
    $lastVol = $v[-1]
    $volRatio = if ($avgVol -gt 0) { [math]::Round($lastVol / $avgVol, 2) } else { 1 }

    return @{
        High      = $high
        Low       = $low
        Amplitude = if ($low -gt 0) { [math]::Round(($high - $low) / $low * 100, 2) } else { 0 }
        RangePos  = Get-RangePosition -Price $LastPrice -High $high -Low $low
        RSI       = Get-RSI -Closes $c -Period 14
        StochRSI  = Get-StochRSI -Closes $c
        ADX_DMI   = Get-ADX-DMI -Highs $h -Lows $l -Closes $c
        EMA       = Get-EMAAlignment -Closes $c
        MACD      = Get-MACD -Closes $c
        OBV       = Get-OBV -Closes $c -Volumes $v
        Chaikin   = Get-ChaikinOscillator -Highs $h -Lows $l -Closes $c -Volumes $v
        Pivots    = Get-PivotPoints -High $high -Low $low -Close $LastPrice
        Fibonacci = Get-Fibonacci -High $high -Low $low
        VolRatio  = $volRatio
        TotalVol  = [math]::Round($totalVol, 0)
        AvgVol    = [math]::Round($avgVol, 0)
    }
}

# ============================================================================
# SECTION E: FONCTIONS DE SCANNING
# ============================================================================

function Scan-TopMovers {
    <#
    .SYNOPSIS Scan complet du marche MEXC Futures.
    Top 15 Gainers, Top 10 Losers, Top 10 Volume + Analyse breakout + CQ consensus.
    #>
    param(
        [switch]$NoTelegram,
        [switch]$NoIA,
        [switch]$NoCQ,
        [int]$TopGainers = 15,
        [int]$TopLosers = 10,
        [int]$TopVolume = 10,
        [int]$BreakoutDepth = 8
    )

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "    SCANNER PRO v2.0 - TOP MOVERS MEXC FUTURES" -ForegroundColor Yellow
    Write-Host "    $timestamp" -ForegroundColor Gray
    Write-Host "================================================================" -ForegroundColor Cyan

    # 1. Tickers
    Write-Host "`n  [1/4] Recuperation tickers..." -ForegroundColor DarkGray
    $allTickers = Get-MexcTickers -MinVolume 100000
    Write-Host "  -> $($allTickers.Count) paires (vol > 100K)" -ForegroundColor Green

    $gainers = $allTickers | Sort-Object Change -Descending | Select-Object -First $TopGainers
    $losers  = $allTickers | Sort-Object Change | Select-Object -First $TopLosers
    $topVol  = $allTickers | Sort-Object Volume -Descending | Select-Object -First $TopVolume

    # 2. Affichage Gainers
    Write-Host "`n  ============ TOP $TopGainers GAINERS ============" -ForegroundColor Green
    foreach ($g in $gainers) {
        $c = if ($g.Change -gt 10) { 'Green' } elseif ($g.Change -gt 5) { 'Yellow' } else { 'White' }
        Write-Host ("  {0,-16} {1,12} {2,8}%  Vol:{3,12}" -f $g.Symbol, $g.Prix, $g.Change, $g.Volume) -ForegroundColor $c
    }

    Write-Host "`n  ============ TOP $TopLosers LOSERS =============" -ForegroundColor Red
    foreach ($l in $losers) {
        $c = if ($l.Change -lt -10) { 'Red' } elseif ($l.Change -lt -5) { 'DarkRed' } else { 'Yellow' }
        Write-Host ("  {0,-16} {1,12} {2,8}%  Vol:{3,12}" -f $l.Symbol, $l.Prix, $l.Change, $l.Volume) -ForegroundColor $c
    }

    Write-Host "`n  ============ TOP $TopVolume VOLUME ==============" -ForegroundColor Cyan
    foreach ($v in $topVol) {
        Write-Host ("  {0,-16} {1,12} {2,8}%  Vol:{3,12}" -f $v.Symbol, $v.Prix, $v.Change, $v.Volume) -ForegroundColor White
    }

    # 3. Breakout analysis sur top gainers
    Write-Host "`n  [2/4] Analyse breakout top $BreakoutDepth gainers..." -ForegroundColor DarkGray
    $breakoutResults = @()

    foreach ($g in $gainers | Select-Object -First $BreakoutDepth) {
        try {
            $klines = Get-MexcKlines -Symbol $g.Symbol -Interval 'Min60' -Limit 48
            if (-not $klines) { continue }

            $indicators = Get-AllIndicators -Klines $klines -LastPrice $g.Prix

            # CQ Consensus sur les top candidats (score >= 30 seulement pour eviter trop d'appels)
            $cqResult = $null
            if (-not $NoCQ) {
                $volM = [math]::Round($indicators.TotalVol / 1e6, 1)
                $indStr = "RSI=$($indicators.RSI) ADX=$($indicators.ADX_DMI.ADX) MACD=$($indicators.MACD.Direction) Chaikin=$($indicators.Chaikin.Zone)"
                $cqResult = Get-CQConsensus -Symbol $g.Symbol -Price $g.Prix -ChangePct $g.Change -VolumeM $volM -Indicators $indStr
            }

            $scoreResult = Get-BreakoutScore -Indicators1H $indicators -FundingRate $g.FundingRate -CQResult $cqResult

            $cqLabel = if ($cqResult -and $cqResult.Success) { "$($cqResult.Consensus)($($cqResult.Confidence)%)" } else { "N/A" }
            $tp1v = [math]::Round($g.Prix * 1.015, 6); $tp2v = [math]::Round($g.Prix * 1.03, 6); $tp3v = [math]::Round($g.Prix * 1.055, 6); $slv = [math]::Round($g.Prix * 0.988, 6)
            # V3.2: Override TP/SL si CQ haute confiance (LONG ou SHORT)
            if ($cqResult -and $cqResult.Success -and $cqResult.Consensus -ne 'HOLD' -and $cqResult.Confidence -ge 80) {
                $tp1v = $cqResult.TP1; $tp2v = $cqResult.TP2; $tp3v = $cqResult.TP3; $slv = $cqResult.SL
            }

            $result = [PSCustomObject]@{
                Symbol   = $g.Symbol
                Prix     = $g.Prix
                Change   = $g.Change
                Score    = $scoreResult.Score
                Verdict  = $scoreResult.Verdict
                Action   = $scoreResult.Action
                CQ       = $cqLabel
                RSI      = $indicators.RSI
                StochK   = $indicators.StochRSI.K
                ADX      = $indicators.ADX_DMI.ADX
                Chaikin  = $indicators.Chaikin.Zone
                MACD     = $indicators.MACD.Direction
                OBV      = $indicators.OBV.Trend
                Range    = $indicators.RangePos
                VolRatio = $indicators.VolRatio
                EMA      = $indicators.EMA.Status
                TP1      = $tp1v; TP2 = $tp2v; TP3 = $tp3v; SL = $slv
                Reasons  = $scoreResult.Reasons
            }
            $breakoutResults += $result

            $sc = if ($scoreResult.Score -ge 55) { 'Green' } elseif ($scoreResult.Score -ge 35) { 'Yellow' } else { 'White' }
            $cqTag = if ($cqResult -and $cqResult.Success) { " CQ=$cqLabel" } else { "" }
            Write-Host "  $($g.Symbol): Score=$($scoreResult.Score)/125 [$($scoreResult.Verdict)]${cqTag} RSI=$($indicators.RSI) StochK=$($indicators.StochRSI.K) ADX=$($indicators.ADX_DMI.ADX) Chaikin=$($indicators.Chaikin.Zone)" -ForegroundColor $sc
        } catch {
            Write-Host "  $($g.Symbol): Erreur klines" -ForegroundColor DarkGray
        }
    }

    # 4. Affichage breakout detaille
    Write-Host "`n  ============ BREAKOUT SCORING + CQ ============" -ForegroundColor Magenta
    foreach ($r in $breakoutResults | Sort-Object Score -Descending) {
        $sc = if ($r.Score -ge 55) { 'Green' } elseif ($r.Score -ge 35) { 'Yellow' } else { 'White' }
        Write-Host ""
        Write-Host "  $($r.Symbol) - Score: $($r.Score)/125 [$($r.Verdict)] CQ:$($r.CQ)" -ForegroundColor $sc
        Write-Host "  Prix: $($r.Prix) | Chg: +$($r.Change)% | Range: $($r.Range)% | Vol: $($r.VolRatio)x" -ForegroundColor White
        Write-Host "  RSI:$($r.RSI) StochK:$($r.StochK) ADX:$($r.ADX) MACD:$($r.MACD) OBV:$($r.OBV) EMA:$($r.EMA) Chaikin:$($r.Chaikin)" -ForegroundColor DarkGray
        if ($r.Action -like '*LONG*') {
            Write-Host "  -> $($r.Action) | TP1:$($r.TP1) TP2:$($r.TP2) TP3:$($r.TP3) SL:$($r.SL)" -ForegroundColor Green
        }
        Write-Host "  Raisons: $($r.Reasons -join ' | ')" -ForegroundColor DarkGray
    }

    # 5. Telegram
    if (-not $NoTelegram) {
        Write-Host "`n  [3/4] Envoi Telegram..." -ForegroundColor DarkGray
        Send-ScanTelegram -Type 'topmovers' -Gainers $gainers -Losers $losers -TopVol $topVol -Breakouts $breakoutResults
    }

    # 6. Database
    Write-Host "`n  [4/4] Sauvegarde signaux..." -ForegroundColor DarkGray
    foreach ($r in $breakoutResults | Where-Object { $_.Score -ge 40 }) {
        Save-Signal -Data $r
    }

    Write-Host "`n================================================================" -ForegroundColor Cyan
    Write-Host "    SCAN TERMINE - $($breakoutResults.Count) tokens analyses" -ForegroundColor Yellow
    Write-Host "================================================================`n" -ForegroundColor Cyan

    return $breakoutResults
}

function Scan-Breakout {
    <#
    .SYNOPSIS Analyse breakout multi-tokens avec tous les indicateurs + Multi-TF + CQ Pipeline.
    .EXAMPLE Scan-Breakout -Symbols @('JELLYJELLY_USDT','MONAD_USDT','HYPE_USDT')
    .EXAMPLE Scan-Breakout -Symbols @('HYPE_USDT') -NoCQ  # Sans consensus CQ
    #>
    param(
        [string[]]$Symbols,
        [switch]$NoIA,
        [switch]$NoTelegram,
        [switch]$NoCQ
    )

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "    SCANNER PRO v2.0 - ANALYSE BREAKOUT" -ForegroundColor Yellow
    Write-Host "    $($Symbols -join ' | ')" -ForegroundColor White
    Write-Host "    $timestamp" -ForegroundColor Gray
    Write-Host "================================================================" -ForegroundColor Cyan

    $allResults = @()
    $aiData = ""

    foreach ($sym in $Symbols) {
        $symbol = if ($sym -match '_USDT$') { $sym } else { "${sym}_USDT" }
        Write-Host "`n  Chargement $symbol..." -ForegroundColor DarkGray

        try {
            # Ticker
            $ticker = (Invoke-RestMethod -Uri "$script:MEXC_API/ticker?symbol=$symbol" -TimeoutSec 10).data
            $last = [double]$ticker.lastPrice
            $fundingRate = $ticker.fundingRate

            # Multi-TF klines
            $kl15  = Get-MexcKlines -Symbol $symbol -Interval 'Min15' -Limit 48
            $kl60  = Get-MexcKlines -Symbol $symbol -Interval 'Min60' -Limit 48
            $kl240 = Get-MexcKlines -Symbol $symbol -Interval 'Hour4' -Limit 30

            # Indicateurs par TF
            $ind15 = if ($kl15) { Get-AllIndicators -Klines $kl15 -LastPrice $last } else { $null }
            $ind60 = if ($kl60) { Get-AllIndicators -Klines $kl60 -LastPrice $last } else { $null }
            $ind4h = if ($kl240) { Get-AllIndicators -Klines $kl240 -LastPrice $last } else { $null }

            # Score composite
            $baseInd = if ($ind60) { $ind60 } else { $ind15 }
            if (-not $baseInd) { Write-Host "  Pas de donnees pour $symbol" -ForegroundColor Red; continue }

            # CQ Consensus (si active)
            $cqResult = $null
            if (-not $NoCQ) {
                $volM = [math]::Round($baseInd.TotalVol / 1e6, 1)
                $indStr = "RSI=$($baseInd.RSI) StochK=$($baseInd.StochRSI.K) ADX=$($baseInd.ADX_DMI.ADX) MACD=$($baseInd.MACD.Direction) Chaikin=$($baseInd.Chaikin.Zone) EMA=$($baseInd.EMA.Status) Range=$($baseInd.RangePos)%"
                $change = 0
                try { $change = [math]::Round(([double]$ticker.riseFallRate) * 100, 1) } catch {}
                $cqResult = Get-CQConsensus -Symbol $symbol -Price $last -ChangePct $change -VolumeM $volM -Indicators $indStr
                if ($cqResult.Success) {
                    $cqColor = switch ($cqResult.Consensus) { 'LONG' { 'Green' }; 'SHORT' { 'Red' }; default { 'Yellow' } }
                    Write-Host "  CQ: $($cqResult.Consensus) | Conf: $($cqResult.Confidence)% | Models: $($cqResult.Models)/8" -ForegroundColor $cqColor
                }
            }

            $scoreResult = Get-BreakoutScore -Indicators1H $baseInd -Indicators15M $ind15 -Indicators4H $ind4h -FundingRate $fundingRate -CQResult $cqResult

            # Affichage detaille
            Write-Host ""
            Write-Host "  ================================================================" -ForegroundColor Yellow
            Write-Host "  $symbol - Prix: $last | Funding: $fundingRate" -ForegroundColor Yellow
            Write-Host "  ================================================================" -ForegroundColor Yellow

            $tfMap = @{ '15min' = $ind15; '1H' = $ind60; '4H' = $ind4h }
            foreach ($tf in @('15min','1H','4H')) {
                $ind = $tfMap[$tf]
                if (-not $ind) { continue }

                Write-Host "`n  --- $tf ---" -ForegroundColor Cyan
                Write-Host "  High: $($ind.High) | Low: $($ind.Low) | Amplitude: $($ind.Amplitude)%"
                Write-Host "  Range Position: $($ind.RangePos)%" -ForegroundColor $(if ($ind.RangePos -gt 80) {'Green'} elseif ($ind.RangePos -lt 20) {'Red'} else {'Yellow'})
                Write-Host "  RSI: $($ind.RSI) | StochRSI K:$($ind.StochRSI.K) D:$($ind.StochRSI.D) [$($ind.StochRSI.Signal)]" -ForegroundColor $(if ($ind.RSI -gt 70) {'Red'} elseif ($ind.RSI -lt 30) {'Green'} else {'Yellow'})
                Write-Host "  ADX: $($ind.ADX_DMI.ADX) | +DI:$($ind.ADX_DMI.PlusDI) -DI:$($ind.ADX_DMI.MinusDI) [$($ind.ADX_DMI.Trend)]" -ForegroundColor $(if ($ind.ADX_DMI.Trend -like '*BULL*') {'Green'} elseif ($ind.ADX_DMI.Trend -like '*BEAR*') {'Red'} else {'Yellow'})
                Write-Host "  EMA: 5=$($ind.EMA.EMA5) 10=$($ind.EMA.EMA10) 20=$($ind.EMA.EMA20) [$($ind.EMA.Status)]" -ForegroundColor $(if ($ind.EMA.Status -like 'BULL*') {'Green'} elseif ($ind.EMA.Status -like 'BEAR*') {'Red'} else {'Yellow'})
                Write-Host "  MACD: $($ind.MACD.MACD) | Signal:$($ind.MACD.Signal) | Histo:$($ind.MACD.Histogram) [$($ind.MACD.Direction)] [$($ind.MACD.HistoTrend)]" -ForegroundColor $(if ($ind.MACD.Direction -eq 'BULLISH') {'Green'} else {'Red'})
                Write-Host "  OBV: $($ind.OBV.OBV) | Trend:$($ind.OBV.Trend) | Div:$($ind.OBV.Divergence)" -ForegroundColor $(if ($ind.OBV.Trend -eq 'RISING') {'Green'} elseif ($ind.OBV.Divergence -like '*BEAR*') {'Red'} else {'White'})
                Write-Host "  Chaikin: $($ind.Chaikin.Value) | Zone:$($ind.Chaikin.Zone) | Signal:$($ind.Chaikin.Signal)" -ForegroundColor $(if ($ind.Chaikin.Zone -eq 'BOTTOM') {'Green'} elseif ($ind.Chaikin.Zone -eq 'DANGER') {'Red'} else {'Yellow'})
                Write-Host "  Volume: $($ind.VolRatio)x | Total: $($ind.TotalVol)"
                Write-Host "  Pivot: $($ind.Pivots.P) | R1:$($ind.Pivots.R1) R2:$($ind.Pivots.R2) | S1:$($ind.Pivots.S1) S2:$($ind.Pivots.S2)"
                Write-Host "  Fib: 23.6%=$($ind.Fibonacci.Fib236) 38.2%=$($ind.Fibonacci.Fib382) 50%=$($ind.Fibonacci.Fib500) 61.8%=$($ind.Fibonacci.Fib618) 78.6%=$($ind.Fibonacci.Fib786)"
            }

            # Verdict
            $tp1 = [math]::Round($last * 1.015, 6)
            $tp2 = [math]::Round($last * 1.03, 6)
            $tp3 = [math]::Round($last * 1.055, 6)
            $sl  = [math]::Round($last * 0.988, 6)

            Write-Host "`n  ======= VERDICT BREAKOUT + CQ =======" -ForegroundColor Magenta
            $sc = if ($scoreResult.Score -ge 55) { 'Green' } elseif ($scoreResult.Score -ge 35) { 'Yellow' } else { 'Red' }
            Write-Host "  Score:     $($scoreResult.Score) / 115" -ForegroundColor $sc
            Write-Host "  Verdict:   $($scoreResult.Verdict)" -ForegroundColor $sc
            Write-Host "  Action:    $($scoreResult.Action)" -ForegroundColor $(if ($scoreResult.Action -like '*LONG*') {'Green'} else {'Yellow'})
            if ($cqResult -and $cqResult.Success) {
                $cqColor = switch ($cqResult.Consensus) { 'LONG' { 'Green' }; 'SHORT' { 'Red' }; default { 'Yellow' } }
                Write-Host "  CQ:        $($cqResult.Consensus) | Conf:$($cqResult.Confidence)% | $($cqResult.Models)/8 models" -ForegroundColor $cqColor
                Write-Host "  CQ Detail: $($cqResult.Details -join ' | ')" -ForegroundColor DarkGray
            }
            Write-Host "  Raisons:   $($scoreResult.Reasons -join ' | ')" -ForegroundColor Gray

            # V3.2: Use CQ TP/SL si haute confiance (LONG ou SHORT), sinon fallback statique
            if ($cqResult -and $cqResult.Success -and $cqResult.Consensus -ne 'HOLD' -and $cqResult.Confidence -ge 80) {
                $tp1 = $cqResult.TP1; $tp2 = $cqResult.TP2; $tp3 = $cqResult.TP3; $sl = $cqResult.SL
                Write-Host "  (TP/SL dynamiques CQ V3.2 - ATR-based)" -ForegroundColor DarkGray
            }

            if ($scoreResult.Action -like '*LONG*') {
                Write-Host "  Entree:    $last" -ForegroundColor White
                Write-Host "  TP1: $tp1 | TP2: $tp2 | TP3: $tp3" -ForegroundColor Green
                Write-Host "  SL: $sl" -ForegroundColor Red
            }

            $cqConsensus = if ($cqResult -and $cqResult.Success) { "$($cqResult.Consensus)($($cqResult.Confidence)%)" } else { "N/A" }

            $result = [PSCustomObject]@{
                Symbol   = $symbol
                Prix     = $last
                Score    = $scoreResult.Score
                Verdict  = $scoreResult.Verdict
                Action   = $scoreResult.Action
                CQ       = $cqConsensus
                RSI      = $baseInd.RSI
                StochK   = $baseInd.StochRSI.K
                ADX      = $baseInd.ADX_DMI.ADX
                MACD     = $baseInd.MACD.Direction
                OBV      = $baseInd.OBV.Trend
                Chaikin  = "$($baseInd.Chaikin.Zone)/$($baseInd.Chaikin.Signal)"
                EMA      = $baseInd.EMA.Status
                Range    = $baseInd.RangePos
                VolRatio = $baseInd.VolRatio
                TP1      = $tp1; TP2 = $tp2; TP3 = $tp3; SL = $sl
                Reasons  = $scoreResult.Reasons
                FundingRate = $fundingRate
            }
            $allResults += $result

            # Donnees pour IA
            $sym2 = $symbol -replace '_USDT',''
            $aiData += "${sym2}: Prix=$last, Score=$($scoreResult.Score)/125, Verdict=$($scoreResult.Verdict), RSI=$($baseInd.RSI), StochRSI_K=$($baseInd.StochRSI.K), ADX=$($baseInd.ADX_DMI.ADX), MACD=$($baseInd.MACD.Direction), OBV=$($baseInd.OBV.Trend), Chaikin=$($baseInd.Chaikin.Zone)/$($baseInd.Chaikin.Signal), EMA=$($baseInd.EMA.Status), Range=$($baseInd.RangePos)%, VolRatio=$($baseInd.VolRatio)x, Funding=$fundingRate, Raisons=[$($scoreResult.Reasons -join ', ')]. "

            # Save signal si score assez haut
            if ($scoreResult.Score -ge 40) { Save-Signal -Data $result }

        } catch {
            Write-Host "  ERREUR $symbol : $($_.Exception.Message)" -ForegroundColor Red
        }
    }

    # IA Analysis
    if (-not $NoIA -and $aiData.Length -gt 0) {
        Write-Host "`n  ============ ANALYSE IA ============" -ForegroundColor Magenta
        $aiResult = Get-AIAnalysis -Data $aiData -Context "breakout"
        if ($aiResult) { Write-Host "`n$aiResult" }
    }

    # Telegram
    if (-not $NoTelegram -and $allResults.Count -gt 0) {
        Send-ScanTelegram -Type 'breakout' -Breakouts $allResults
    }

    # Tableau resume
    Write-Host "`n  ============ RESUME ============" -ForegroundColor Cyan
    $allResults | Sort-Object Score -Descending | Format-Table Symbol, Prix, Score, Verdict, CQ, RSI, StochK, ADX, Chaikin, MACD, Range, VolRatio -AutoSize

    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "    ANALYSE BREAKOUT TERMINEE" -ForegroundColor Yellow
    Write-Host "================================================================`n" -ForegroundColor Cyan

    return $allResults
}

function Scan-Token {
    <#
    .SYNOPSIS Analyse profonde d'un seul token avec tous les TF et indicateurs.
    .EXAMPLE Scan-Token -Symbol 'HYPE'
    #>
    param(
        [string]$Symbol,
        [switch]$NoIA,
        [switch]$NoTelegram
    )

    $fullSym = if ($Symbol -match '_USDT$') { $Symbol } else { "${Symbol}_USDT" }
    $results = Scan-Breakout -Symbols @($fullSym) -NoIA:$NoIA -NoTelegram:$NoTelegram
    return $results
}

# ============================================================================
# SECTION F: INTEGRATION IA
# ============================================================================

function Get-AIAnalysis {
    <#
    .SYNOPSIS Envoie les donnees de scan a LM Studio pour analyse IA.
    Timeout 45s, modele nemotron-3-nano (rapide), fallback qwen3-30b.
    #>
    param(
        [string]$Data,
        [string]$Context = "general"
    )

    $systemPrompt = "Tu es un expert en analyse technique crypto. Analyse concise et actionnabe en francais. Max 300 mots."
    $userPrompt = switch ($Context) {
        "breakout" {
            "Analyse breakout de ces tokens MEXC Futures ($(Get-Date -Format 'dd/MM HH:mm')):`n${Data}`nPour chaque: 1) Probabilite breakout 0-100% 2) Direction+force 3) Entry/TP/SL optimises 4) Risk/Reward 5) Timing. CLASSEMENT final du meilleur au pire setup."
        }
        "topmovers" {
            "Analyse rapide top movers MEXC Futures:`n${Data}`nQuels tokens presentent les meilleures opportunites? Signal, direction, force."
        }
        default {
            "Analyse ces donnees trading:`n${Data}"
        }
    }

    # Essayer nemotron d'abord (plus rapide), fallback sur qwen3-30b
    $models = @('nvidia/nemotron-3-nano', 'qwen/qwen3-30b-a3b-2507')

    # Essayer chaque serveur avec son modele prioritaire
    $servers = @(
        @{ URL = $script:CQ_CLUSTER.M2.URL; Model = 'nvidia/nemotron-3-nano' }
        @{ URL = $script:CQ_CLUSTER.M1.URL; Model = 'qwen/qwen3-30b-a3b-2507' }
        @{ URL = $script:CQ_CLUSTER.M3.URL; Model = 'nvidia/nemotron-3-nano' }
    )

    foreach ($srv in $servers) {
        try {
            Write-Host "  Analyse IA ($($srv.Model) @ $($srv.URL))..." -ForegroundColor DarkGray
            $body = @{
                model      = $srv.Model
                messages   = @(
                    @{ role = 'system'; content = $systemPrompt }
                    @{ role = 'user'; content = $userPrompt }
                )
                temperature = 0.3
                max_tokens  = 800
            } | ConvertTo-Json -Depth 5
            $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($body)

            $resp = Invoke-RestMethod -Uri "$($srv.URL)/v1/chat/completions" -Method Post -Body $bodyBytes -ContentType 'application/json; charset=utf-8' -TimeoutSec 45
            $text = $resp.choices[0].message.content
            Write-Host "  IA OK ($($srv.Model))" -ForegroundColor Green
            return $text
        } catch {
            Write-Host "  IA $($srv.Model) erreur: $($_.Exception.Message)" -ForegroundColor DarkGray
        }
    }

    Write-Host "  Analyse IA indisponible (3 serveurs tentes)" -ForegroundColor Red
    return $null
}

# ============================================================================
# SECTION F2: CQ PIPELINE v5.0 - CONTEXTUAL QUOTIENT
# 8 modeles, 3 stages (FAST + DEEP + CONTRARIAN), adaptive weights, self-correction
# ============================================================================

function Invoke-CQCall {
    <#
    .SYNOPSIS Appel LM Studio optimise pour CQ. Skip system prompt pour Mistral/Phi.
    #>
    param(
        [string]$ServerURL,
        [string]$Model,
        [string]$Prompt,
        [int]$MaxTokens = 60,
        [int]$Timeout = 45
    )

    try {
        $messages = @()
        if ($Model -notin $script:CQ_MODELS_NO_SYSTEM) {
            $messages += @{ role = 'system'; content = $script:CQ_SYSTEM_PROMPT }
            $messages += @{ role = 'user'; content = $Prompt }
        } else {
            $messages += @{ role = 'user'; content = "$($script:CQ_SYSTEM_PROMPT)`n`n$Prompt" }
        }

        $body = @{
            model       = $Model
            messages    = $messages
            max_tokens  = $MaxTokens
            temperature = 0.1
            top_p       = 0.9
        } | ConvertTo-Json -Depth 5

        $t0 = Get-Date
        $resp = Invoke-RestMethod -Uri "$ServerURL/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec $Timeout
        $elapsed = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
        $answer = $resp.choices[0].message.content.Trim()

        return @{ Success = $true; Answer = $answer; Time = $elapsed; Model = $Model }
    } catch {
        return @{ Success = $false; Answer = ''; Time = 0; Error = $_.Exception.Message.Substring(0, [math]::Min(50, $_.Exception.Message.Length)) }
    }
}

function Parse-CQVote {
    <#
    .SYNOPSIS Parse un vote LONG/SHORT/HOLD + confiance depuis une reponse IA.
    #>
    param([string]$Text)

    if (-not $Text) { return @{ Vote = 'HOLD'; Confidence = 5 } }

    $upper = $Text.ToUpper()

    # Confidence
    $conf = 5
    if ($upper -match '(\d+)\s*/\s*10') { $conf = [int]$Matches[1] }
    elseif ($upper -match 'confiance\s*:?\s*(\d+)') { $conf = [int]$Matches[1] }
    $conf = [math]::Max(1, [math]::Min(10, $conf))

    # Direction
    $vote = 'HOLD'
    if ($upper -match 'LONG|BUY|ACHAT|HAUSSIER') { $vote = 'LONG' }
    elseif ($upper -match 'SHORT|SELL|VENTE|BAISSIER') { $vote = 'SHORT' }

    return @{ Vote = $vote; Confidence = $conf }
}

function Build-TradingContext {
    <#
    .SYNOPSIS Assemble le contexte trading depuis MEXC API (positions, marche BTC).
    Format concis ~200 tokens pour injection CQ.
    #>
    param([string]$Symbol)

    $parts = @()

    # BTC regime
    try {
        $btcTicker = (Invoke-RestMethod -Uri "$script:MEXC_API/ticker?symbol=BTC_USDT" -TimeoutSec 5).data
        $btcChange = [math]::Round([double]$btcTicker.riseFallRate * 100, 1)
        $btcPrice = [double]$btcTicker.lastPrice
        $regime = if ($btcChange -gt 2) { 'BULL' } elseif ($btcChange -lt -2) { 'BEAR' } else { 'RANGE' }
        $warning = if ($btcChange -lt -1) { ', prudence longs' } elseif ($btcChange -gt 1) { ', favorable longs' } else { '' }
        $parts += "[MARCHE] BTC $btcPrice (${btcChange}%) = ${regime}${warning}"
    } catch {
        $parts += "[MARCHE] BTC indisponible"
    }

    # Positions MEXC (via ticker funding rates comme proxy)
    try {
        $allTickers = Invoke-RestMethod -Uri "$script:MEXC_API/ticker" -TimeoutSec 5
        $avgFunding = ($allTickers.data | Where-Object { $_.fundingRate } | ForEach-Object { [double]$_.fundingRate } | Measure-Object -Average).Average
        $parts += "[FUNDING GLOBAL] Moy: $([math]::Round($avgFunding * 100, 4))%"
    } catch {}

    if ($Symbol) {
        $parts += "[ANALYSE] $Symbol"
    }

    return ($parts -join "`n")
}

# --- RunspacePool helper for CQ stages ---
function Invoke-CQStageParallel {
    <#
    .SYNOPSIS Execute un stage CQ en parallele via RunspacePool.
    Retourne les votes parses et details.
    #>
    param(
        [array]$Calls,
        [string]$Prompt,
        [int]$PoolSize = 3
    )

    $results = @()
    $pool = [runspacefactory]::CreateRunspacePool(1, $PoolSize)
    $pool.Open()

    $jobs = foreach ($call in $Calls) {
        $ps = [powershell]::Create().AddScript({
            param($URL, $Model, $Prompt, $MaxTokens, $Timeout, $SystemPrompt, $NoSystemModels)
            $messages = @()
            if ($Model -notin $NoSystemModels) {
                $messages += @{ role = 'system'; content = $SystemPrompt }
                $messages += @{ role = 'user'; content = $Prompt }
            } else {
                $messages += @{ role = 'user'; content = "$SystemPrompt`n`n$Prompt" }
            }
            $body = @{ model = $Model; messages = $messages; max_tokens = $MaxTokens; temperature = 0.1; top_p = 0.9 } | ConvertTo-Json -Depth 5
            try {
                $t0 = Get-Date
                $resp = Invoke-RestMethod -Uri "$URL/v1/chat/completions" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec $Timeout
                $elapsed = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
                return @{ Success = $true; Answer = $resp.choices[0].message.content.Trim(); Time = $elapsed }
            } catch { return @{ Success = $false; Answer = ''; Time = 0 } }
        }).AddArgument($call.URL).AddArgument($call.Model).AddArgument($Prompt).AddArgument($call.MaxTokens).AddArgument($call.Timeout).AddArgument($script:CQ_SYSTEM_PROMPT).AddArgument($script:CQ_MODELS_NO_SYSTEM)
        $ps.RunspacePool = $pool
        @{ PS = $ps; Handle = $ps.BeginInvoke(); Name = $call.Name; Weight = $call.Weight; Model = $call.Model }
    }

    foreach ($job in $jobs) {
        try {
            $res = $job.PS.EndInvoke($job.Handle)
            $job.PS.Dispose()
            if ($res -and $res.Success) {
                $parsed = Parse-CQVote -Text $res.Answer
                $results += @{
                    Name       = $job.Name
                    Model      = $job.Model
                    Vote       = $parsed.Vote
                    Confidence = $parsed.Confidence
                    Weight     = $job.Weight
                    Time       = $res.Time
                    Answer     = $res.Answer
                }
            }
        } catch {}
    }

    $pool.Close()
    $pool.Dispose()
    return ,$results  # Force array (evite PowerShell unwrap single hashtable)
}

function Get-CQConsensus {
    <#
    .SYNOPSIS CQ v5.0 - Pipeline 3 stages pour consensus multi-modele.
    Stage 1 FAST (~3s):  M2-Nemotron + M2-GLM-4.7 + M3-Nemotron (screening)
    Stage 2 DEEP (~5s):  M1-Qwen30B + M1-GPToss + M3-GPToss (analyse profonde)
    Stage 3 CONTRARIAN (~3s): M3-Mistral + M3-Phi3.1 (sceptiques)
    Early exit si Stage 1 unanime SHORT.
    Adaptive weights depuis DB si disponible.
    Retourne: consensus, confiance%, votes details, TP/SL dynamiques, model_votes JSON.
    #>
    param(
        [string]$Symbol,
        [double]$Price,
        [double]$ChangePct = 0,
        [double]$VolumeM = 0,
        [double]$RangePos = 0.5,
        [string]$Indicators = '',
        [switch]$SendTelegram
    )

    $context = Build-TradingContext -Symbol $Symbol
    $sigStr = if ($Indicators) { $Indicators } else { "$($ChangePct.ToString('+0.0;-0.0'))% Vol ${VolumeM}M RP $RangePos" }

    $prompt = @"
${context}

SIGNAL: $Symbol `$$Price | Change: $($ChangePct.ToString('+0.0;-0.0'))% | Volume: ${VolumeM}M USDT | Range: $RangePos
Indicateurs: $sigStr
Verdict?
"@

    # Load adaptive weights (override static if DB available)
    $adaptiveW = Get-AdaptiveWeights
    $weights = @{
        M1 = if ($adaptiveW) { $adaptiveW.M1 } else { $script:CQ_CLUSTER.M1.Weight }
        M2 = if ($adaptiveW) { $adaptiveW.M2 } else { $script:CQ_CLUSTER.M2.Weight }
        M3 = if ($adaptiveW) { $adaptiveW.M3 } else { $script:CQ_CLUSTER.M3.Weight }
    }

    $allVotes = @{ LONG = 0.0; SHORT = 0.0; HOLD = 0.0 }
    $details = @()
    $modelVotes = @{}
    $totalConf = 0
    $voteCount = 0

    # === STAGE 1: FAST SCREENING (3 models) ===
    Write-Host "    CQ Stage 1 (FAST 3 models)..." -ForegroundColor DarkGray -NoNewline

    $stage1Calls = @(
        @{ Name = 'M2-Nemo';    URL = $script:CQ_CLUSTER.M2.URL; Model = 'nvidia/nemotron-3-nano';  Weight = $weights.M2;       MaxTokens = 50; Timeout = 25 }
        @{ Name = 'M2-GLM47';   URL = $script:CQ_CLUSTER.M2.URL; Model = 'zai-org/glm-4.7-flash';   Weight = $weights.M2 * 0.9; MaxTokens = 50; Timeout = 25 }
        @{ Name = 'M3-Nemo';    URL = $script:CQ_CLUSTER.M3.URL; Model = 'nvidia/nemotron-3-nano';   Weight = $weights.M3;       MaxTokens = 50; Timeout = 25 }
    )

    $stage1Results = Invoke-CQStageParallel -Calls $stage1Calls -Prompt $prompt -PoolSize 3

    $stage1ShortCount = 0
    foreach ($r in $stage1Results) {
        $allVotes[$r.Vote] += $r.Weight * ($r.Confidence / 10)
        $totalConf += $r.Confidence
        $voteCount++
        $details += "$($r.Name)=$($r.Vote)($($r.Confidence)/10,$($r.Time)s)"
        $modelVotes[$r.Name] = @{ model = $r.Model; vote = $r.Vote; confidence = $r.Confidence; time = $r.Time }
        if ($r.Vote -eq 'SHORT') { $stage1ShortCount++ }
    }
    Write-Host " $($stage1Results.Count) votes" -ForegroundColor DarkGray

    # Early exit: si 3/3 SHORT en Stage 1, skip stages 2+3
    $earlyExit = ($stage1Results.Count -ge 3 -and $stage1ShortCount -ge 3)
    if ($earlyExit) {
        Write-Host "    -> Early exit: 3/3 SHORT en Stage 1" -ForegroundColor Red
    }

    if (-not $earlyExit) {
        # === STAGE 2: DEEP ANALYSIS (3 models) ===
        Write-Host "    CQ Stage 2 (DEEP 3 models)..." -ForegroundColor DarkGray -NoNewline

        $stage2Calls = @(
            @{ Name = 'M1-Qwen30B'; URL = $script:CQ_CLUSTER.M1.URL; Model = 'qwen/qwen3-30b-a3b-2507'; Weight = $weights.M1;       MaxTokens = 60; Timeout = 55 }
            @{ Name = 'M1-GPToss';  URL = $script:CQ_CLUSTER.M1.URL; Model = 'openai/gpt-oss-20b';       Weight = $weights.M1 * 0.85; MaxTokens = 60; Timeout = 40 }
            @{ Name = 'M3-GPToss';  URL = $script:CQ_CLUSTER.M3.URL; Model = 'openai/gpt-oss-20b';       Weight = $weights.M3 * 0.9;  MaxTokens = 60; Timeout = 35 }
        )

        $stage2Results = Invoke-CQStageParallel -Calls $stage2Calls -Prompt $prompt -PoolSize 3

        foreach ($r in $stage2Results) {
            $allVotes[$r.Vote] += $r.Weight * ($r.Confidence / 10)
            $totalConf += $r.Confidence
            $voteCount++
            $details += "$($r.Name)=$($r.Vote)($($r.Confidence)/10,$($r.Time)s)"
            $modelVotes[$r.Name] = @{ model = $r.Model; vote = $r.Vote; confidence = $r.Confidence; time = $r.Time }
        }
        Write-Host " $($stage2Results.Count) votes" -ForegroundColor DarkGray

        # === STAGE 3: CONTRARIAN (2 models - sceptiques) ===
        Write-Host "    CQ Stage 3 (CONTRARIAN 2 models)..." -ForegroundColor DarkGray -NoNewline

        $contrarianPrompt = @"
${context}

SIGNAL: $Symbol `$$Price | Change: $($ChangePct.ToString('+0.0;-0.0'))% | Volume: ${VolumeM}M USDT
Indicateurs: $sigStr

IMPORTANT: Sois SCEPTIQUE. Cherche les raisons pour NE PAS entrer. Quels sont les risques? Si le signal est faible, dis HOLD ou SHORT.
Verdict?
"@

        $stage3Calls = @(
            @{ Name = 'M3-Mistral'; URL = $script:CQ_CLUSTER.M3.URL; Model = 'mistral-7b-instruct-v0.3';     Weight = $weights.M3 * 0.7; MaxTokens = 60; Timeout = 30 }
            @{ Name = 'M3-Phi31';   URL = $script:CQ_CLUSTER.M3.URL; Model = 'phi-3.1-mini-128k-instruct';    Weight = $weights.M3 * 0.6; MaxTokens = 60; Timeout = 30 }
        )

        $stage3Results = Invoke-CQStageParallel -Calls $stage3Calls -Prompt $contrarianPrompt -PoolSize 2

        foreach ($r in $stage3Results) {
            $allVotes[$r.Vote] += $r.Weight * ($r.Confidence / 10)
            $totalConf += $r.Confidence
            $voteCount++
            $details += "$($r.Name)=$($r.Vote)($($r.Confidence)/10,$($r.Time)s)"
            $modelVotes[$r.Name] = @{ model = $r.Model; vote = $r.Vote; confidence = $r.Confidence; time = $r.Time }
        }
        Write-Host " $($stage3Results.Count) votes" -ForegroundColor DarkGray
    }

    Write-Host "    -> $voteCount votes total" -ForegroundColor DarkGray

    # === CONSENSUS FINAL ===
    $totalW = $allVotes.LONG + $allVotes.SHORT + $allVotes.HOLD
    if ($totalW -eq 0) {
        return @{ Success = $false; Consensus = 'HOLD'; Confidence = 0; Models = 0; Details = @(); ModelVotes = @{} }
    }

    $consensus = ($allVotes.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 1).Key
    $confidence = [math]::Round($allVotes[$consensus] / $totalW * 100, 1)
    $avgConf = if ($voteCount -gt 0) { [math]::Round($totalConf / $voteCount, 1) } else { 5 }

    # === V3.2 PATCH: Direction weighting (SHORT WR 57.6% vs LONG WR 6.8%) ===
    if ($consensus -eq 'SHORT') {
        $confidence = [math]::Min(99, [math]::Round($confidence * 1.5, 1))
        $details += "SHORT_BOOST(x1.5)"
    } elseif ($consensus -eq 'LONG') {
        $confidence = [math]::Round($confidence * 0.4, 1)
        $details += "LONG_PENALTY(x0.4)"
    }

    # Bonus confiance si contrarians confirment
    if (-not $earlyExit -and $stage3Results.Count -ge 2) {
        $contrarianLong = ($stage3Results | Where-Object { $_.Vote -eq 'LONG' }).Count
        if ($consensus -eq 'LONG' -and $contrarianLong -ge 2) {
            $confidence = [math]::Min(99, $confidence + 5)
            $details += "CONTRARIAN_CONFIRM(+5%)"
        }
    }

    # TP/SL dynamique base sur ATR (cap 15%)
    $atrFactor = [math]::Min([math]::Max([math]::Abs($ChangePct) / 100, 0.015), 0.15)
    if ($consensus -eq 'LONG') {
        $tp1 = [math]::Round($Price * (1 + $atrFactor * 0.5), 8)
        $tp2 = [math]::Round($Price * (1 + $atrFactor * 1.0), 8)
        $tp3 = [math]::Round($Price * (1 + $atrFactor * 1.8), 8)
        $sl  = [math]::Round($Price * (1 - $atrFactor * 0.8), 8)
    } elseif ($consensus -eq 'SHORT') {
        $tp1 = [math]::Round($Price * (1 - $atrFactor * 0.5), 8)
        $tp2 = [math]::Round($Price * (1 - $atrFactor * 1.0), 8)
        $tp3 = [math]::Round($Price * (1 - $atrFactor * 1.8), 8)
        $sl  = [math]::Round($Price * (1 + $atrFactor * 0.8), 8)
    } else {
        $tp1 = $tp2 = $tp3 = $sl = $Price
    }

    $rrRatio = if ($sl -ne $Price) { [math]::Round([math]::Abs($tp2 - $Price) / [math]::Abs($Price - $sl), 2) } else { 0 }

    # Telegram alert
    # V3.2: Confidence threshold raised from 60% to 80% (WR 28% -> 75%)
    if ($SendTelegram -and $consensus -ne 'HOLD' -and $confidence -ge 80) {
        $arrow = if ($consensus -eq 'LONG') { '&#x1F7E2;' } else { '&#x1F534;' }
        $nl = "`n"
        $tMsg = "${arrow} <b>CQ v5.0 TURBO SIGNAL</b>${nl}"
        $tMsg += "<b>$Symbol</b> | $consensus | Conf: ${confidence}%${nl}"
        $tMsg += "Entry: `$$Price${nl}"
        $tMsg += "TP1: `$$tp1 | TP2: `$$tp2 | TP3: `$$tp3${nl}"
        $tMsg += "SL: `$$sl | R:R ${rrRatio}:1${nl}"
        $tMsg += "Models: ${voteCount}/8 | AvgConf: ${avgConf}/10${nl}"
        $tMsg += ($details -join ' | ')

        if ($tMsg.Length -gt 4000) { $tMsg = $tMsg.Substring(0, 3990) + "${nl}..." }
        try {
            $teleBody = @{ chat_id = $script:TELEGRAM_CHAT; text = $tMsg; parse_mode = 'HTML' } | ConvertTo-Json -Depth 3
            Invoke-RestMethod -Uri "https://api.telegram.org/bot$($script:TELEGRAM_TOKEN)/sendMessage" -Method Post -Body $teleBody -ContentType 'application/json; charset=utf-8' -TimeoutSec 10 | Out-Null
        } catch {}
    }

    return @{
        Success    = $true
        Consensus  = $consensus
        Confidence = $confidence
        AvgConf    = $avgConf
        Votes      = @{ LONG = [math]::Round($allVotes.LONG, 2); SHORT = [math]::Round($allVotes.SHORT, 2); HOLD = [math]::Round($allVotes.HOLD, 2) }
        Models     = $voteCount
        Details    = $details
        ModelVotes = $modelVotes
        TP1        = $tp1; TP2 = $tp2; TP3 = $tp3; SL = $sl
        RR         = $rrRatio
        EarlyExit  = $earlyExit
    }
}

function Start-CQScan {
    <#
    .SYNOPSIS CQ v4.0 - Scan MEXC complet + consensus 4 modeles sur chaque candidat.
    Pipeline: 850+ tickers -> Filter -> Score -> Top N -> 4-model consensus -> Telegram
    .EXAMPLE Start-CQScan -TopN 8 -MinChange 3
    #>
    param(
        [double]$MinChange = 2.0,
        [double]$MinVolume = 3000000,
        [int]$TopN = 10,
        [switch]$NoTelegram
    )

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Magenta
    Write-Host "    CQ PIPELINE v5.0 - TURBO SCAN" -ForegroundColor Yellow
    Write-Host "    8 Modeles | 3 Serveurs GPU | Pipeline 3 Stages" -ForegroundColor White
    Write-Host "    $timestamp" -ForegroundColor Gray
    Write-Host "================================================================" -ForegroundColor Magenta

    # 1. Scan MEXC
    Write-Host "`n  [1/3] Scan MEXC tickers..." -ForegroundColor DarkGray
    $allTickers = Get-MexcTickers -MinVolume $MinVolume
    Write-Host "  -> $($allTickers.Count) paires (vol > $([math]::Round($MinVolume/1e6,1))M)" -ForegroundColor Green

    # 2. Score et filtre candidats
    Write-Host "  [2/3] Filtrage candidats..." -ForegroundColor DarkGray
    $candidates = @()
    foreach ($t in $allTickers) {
        try {
            $hi = [double]$t.Prix  # Approximation, on utilise le change pour le filtre
            $rp = 0.5
            $score = 0

            if ([math]::Abs($t.Change) -gt $MinChange) {
                $score = [math]::Abs($t.Change) * [math]::Min($t.Volume / 1e6, 3) * 5
            }
            if ($t.Change -gt 5) { $score *= 1.5 }  # Bonus gros movers

            if ($score -gt 15) {
                $candidates += [PSCustomObject]@{
                    Symbol   = $t.Symbol
                    Prix     = $t.Prix
                    Change   = $t.Change
                    VolumeM  = [math]::Round($t.Volume / 1e6, 1)
                    Score    = [math]::Round($score, 1)
                    Funding  = $t.FundingRate
                }
            }
        } catch {}
    }

    $candidates = $candidates | Sort-Object Score -Descending | Select-Object -First $TopN
    Write-Host "  -> $($candidates.Count) candidats selectionnes" -ForegroundColor Green

    if ($candidates.Count -eq 0) {
        Write-Host "  Aucun candidat avec change > ${MinChange}% et vol > $([math]::Round($MinVolume/1e6,1))M" -ForegroundColor Yellow
        return @()
    }

    # 3. CQ Consensus sur chaque
    Write-Host "  [3/3] Consensus CQ 4 modeles sur $($candidates.Count) candidats..." -ForegroundColor DarkGray
    $signals = @()

    foreach ($c in $candidates) {
        Write-Host "`n  --- $($c.Symbol) ($($c.Change)% | $($c.VolumeM)M) ---" -ForegroundColor Cyan
        $cqResult = Get-CQConsensus -Symbol $c.Symbol -Price $c.Prix -ChangePct $c.Change -VolumeM $c.VolumeM -SendTelegram:(-not $NoTelegram)

        if ($cqResult.Success) {
            $color = switch ($cqResult.Consensus) { 'LONG' { 'Green' }; 'SHORT' { 'Red' }; default { 'Yellow' } }
            Write-Host "    -> $($cqResult.Consensus) | Conf: $($cqResult.Confidence)% | Models: $($cqResult.Models)/8 | R:R $($cqResult.RR):1" -ForegroundColor $color
            Write-Host "    -> $($cqResult.Details -join ' | ')" -ForegroundColor DarkGray

            $signals += [PSCustomObject]@{
                Symbol     = $c.Symbol
                Prix       = $c.Prix
                Change     = $c.Change
                VolumeM    = $c.VolumeM
                Consensus  = $cqResult.Consensus
                Confidence = $cqResult.Confidence
                AvgConf    = $cqResult.AvgConf
                Models     = $cqResult.Models
                TP1        = $cqResult.TP1
                TP2        = $cqResult.TP2
                TP3        = $cqResult.TP3
                SL         = $cqResult.SL
                RR         = $cqResult.RR
                Details    = ($cqResult.Details -join ' | ')
            }
        } else {
            Write-Host "    -> Pas de reponse CQ" -ForegroundColor DarkGray
        }
    }

    # Resultats
    # V3.2: Confidence threshold raised from 60% to 80%
    $goSignals = $signals | Where-Object { $_.Confidence -ge 80 -and $_.Consensus -ne 'HOLD' }

    Write-Host "`n  ============ CQ RESULTATS ============" -ForegroundColor Magenta
    $signals | Sort-Object Confidence -Descending | Format-Table Symbol, Prix, Change, Consensus, Confidence, AvgConf, Models, RR, TP1, SL -AutoSize

    if ($goSignals.Count -gt 0) {
        Write-Host "  GO SIGNALS: $($goSignals.Count)" -ForegroundColor Green
        foreach ($s in $goSignals) {
            Write-Host "  -> $($s.Consensus) $($s.Symbol) @ $($s.Prix) | Conf:$($s.Confidence)% | TP1:$($s.TP1) SL:$($s.SL)" -ForegroundColor Green
        }
    } else {
        Write-Host "  Aucun GO signal (conf >= 80%)" -ForegroundColor Yellow
    }

    Write-Host "`n================================================================" -ForegroundColor Magenta
    Write-Host "    CQ SCAN TERMINE - $($signals.Count) analyses, $($goSignals.Count) GO signals" -ForegroundColor Yellow
    Write-Host "================================================================`n" -ForegroundColor Magenta

    return $signals
}

# ============================================================================
# SECTION G: TELEGRAM
# ============================================================================

function Escape-TelegramHtml {
    <# Echappe les caracteres speciaux pour Telegram HTML parse_mode #>
    param([string]$Text)
    if (-not $Text) { return '' }
    $Text = $Text -replace '&', '&amp;'
    $Text = $Text -replace '<', '&lt;'
    $Text = $Text -replace '>', '&gt;'
    return $Text
}

function Send-ScanTelegram {
    <#
    .SYNOPSIS Envoie les resultats de scan via Telegram.
    #>
    param(
        [string]$Type,
        $Gainers = @(),
        $Losers = @(),
        $TopVol = @(),
        $Breakouts = @()
    )

    if (-not $script:TELEGRAM_TOKEN -or -not $script:TELEGRAM_CHAT) {
        Write-Host "  Telegram non configure" -ForegroundColor Red
        return
    }

    $nl = "`n"
    $msg = ""

    switch ($Type) {
        'topmovers' {
            $msg = "<b>SCANNER PRO v2.0 - TOP MOVERS</b>${nl}"
            $msg += "$(Get-Date -Format 'dd/MM HH:mm')${nl}${nl}"

            $msg += "<b>TOP GAINERS</b>${nl}"
            $rank = 1
            foreach ($g in $Gainers | Select-Object -First 10) {
                $sym = $g.Symbol -replace '_USDT',''
                $msg += "${rank}. <b>${sym}</b>: $($g.Prix) | <b>+$($g.Change)%</b>${nl}"
                $rank++
            }

            $msg += "${nl}<b>TOP LOSERS</b>${nl}"
            $rank = 1
            foreach ($l in $Losers | Select-Object -First 7) {
                $sym = $l.Symbol -replace '_USDT',''
                $msg += "${rank}. ${sym}: $($l.Prix) | $($l.Change)%${nl}"
                $rank++
            }

            if ($Breakouts | Where-Object { $_.Score -ge 40 }) {
                $msg += "${nl}<b>SIGNAUX BREAKOUT</b>${nl}"
                foreach ($b in $Breakouts | Where-Object { $_.Score -ge 40 } | Sort-Object Score -Descending) {
                    $sym = Escape-TelegramHtml ($b.Symbol -replace '_USDT','')
                    $chk = Escape-TelegramHtml "$($b.Chaikin)"
                    $msg += "${nl}<b>$(Escape-TelegramHtml $b.Verdict) ${sym}</b> (Score:$($b.Score)/125)${nl}"
                    $msg += "Prix:$($b.Prix) | +$($b.Change)%${nl}"
                    $msg += "RSI:$($b.RSI) StochK:$($b.StochK) ADX:$($b.ADX) Chaikin:${chk}${nl}"
                    if ($b.Action -like '*LONG*') {
                        $msg += "TP1:$($b.TP1) TP2:$($b.TP2) SL:$($b.SL)${nl}"
                    }
                }
            }
        }

        'breakout' {
            $msg = "<b>SCANNER PRO v2.0 - BREAKOUT</b>${nl}"
            $msg += "$(Get-Date -Format 'dd/MM HH:mm')${nl}${nl}"

            foreach ($b in $Breakouts | Sort-Object Score -Descending) {
                $sym = Escape-TelegramHtml ($b.Symbol -replace '_USDT','')
                $icon = if ($b.Score -ge 55) { [char]::ConvertFromUtf32(0x1F680) } elseif ($b.Score -ge 40) { [char]::ConvertFromUtf32(0x2B06) } else { [char]::ConvertFromUtf32(0x1F4CA) }
                $msg += "${icon} <b>${sym}</b> - Score: $($b.Score)/125${nl}"
                $msg += "<b>$(Escape-TelegramHtml $b.Verdict)</b> | $(Escape-TelegramHtml $b.Action)${nl}"
                $msg += "Prix:$($b.Prix) | Range:$($b.Range)%${nl}"
                $msg += "RSI:$($b.RSI) | StochK:$($b.StochK) | ADX:$($b.ADX)${nl}"
                $chk = Escape-TelegramHtml "$($b.Chaikin)"
                $ema = Escape-TelegramHtml "$($b.EMA)"
                $msg += "MACD:$($b.MACD) | OBV:$($b.OBV) | Chaikin:${chk}${nl}"
                $msg += "EMA:${ema} | Vol:$($b.VolRatio)x | CQ:$($b.CQ)${nl}"
                if ($b.Action -like '*LONG*') {
                    $msg += "TP1:$($b.TP1) | TP2:$($b.TP2) | TP3:$($b.TP3)${nl}"
                    $msg += "SL:$($b.SL)${nl}"
                }
                $reasons = Escape-TelegramHtml ($b.Reasons -join ', ')
                $msg += "Raisons: ${reasons}${nl}${nl}"
            }
        }

        'signal' {
            foreach ($b in $Breakouts | Where-Object { $_.Score -ge 55 }) {
                $sym = Escape-TelegramHtml ($b.Symbol -replace '_USDT','')
                $icon = [char]::ConvertFromUtf32(0x1F6A8)
                $msg += "${icon} <b>SIGNAL $(Escape-TelegramHtml $b.Action) ${sym}</b>${nl}"
                $msg += "Score:$($b.Score)/125 | Prix:$($b.Prix)${nl}"
                $msg += "TP1:$($b.TP1) | SL:$($b.SL)${nl}${nl}"
            }
        }
    }

    if ($msg.Length -eq 0) { return }

    # Truncate si message trop long (Telegram max 4096 chars)
    if ($msg.Length -gt 4000) { $msg = $msg.Substring(0, 3990) + "${nl}...(tronque)" }

    $teleBody = @{
        chat_id    = $script:TELEGRAM_CHAT
        text       = $msg
        parse_mode = "HTML"
    } | ConvertTo-Json -Depth 3
    $teleBytes = [System.Text.Encoding]::UTF8.GetBytes($teleBody)

    try {
        $url = "https://api.telegram.org/bot$($script:TELEGRAM_TOKEN)/sendMessage"
        $resp = Invoke-RestMethod -Uri $url -Method Post -Body $teleBytes -ContentType 'application/json; charset=utf-8' -TimeoutSec 10
        if ($resp.ok) {
            Write-Host "  Telegram OK (msg_id: $($resp.result.message_id))" -ForegroundColor Green
        }
    } catch {
        $errBody = ''
        if ($_.Exception.Response) {
            try { $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream()); $errBody = $sr.ReadToEnd(); $sr.Close() } catch {}
        }
        Write-Host "  Telegram erreur: $($_.Exception.Message) $errBody" -ForegroundColor Red
    }
}

# ============================================================================
# SECTION H: DATABASE
# ============================================================================

function Save-Signal {
    <#
    .SYNOPSIS Sauvegarde un signal dans la base SQLite trading.db
    #>
    param([PSCustomObject]$Data)

    if (-not (Test-Path $script:SQL_DB)) { return }

    try {
        $sym = $Data.Symbol -replace '_USDT',''
        $direction = if ($Data.Action -like '*LONG*') { 'LONG' } else { 'NEUTRAL' }
        $reasons = if ($Data.Reasons) { ($Data.Reasons -join ' | ') } else { '' }
        $indicatorsJson = @{
            rsi      = $Data.RSI
            stochK   = $Data.StochK
            adx      = $Data.ADX
            macd     = $Data.MACD
            obv      = $Data.OBV
            chaikin  = $Data.Chaikin
            ema      = $Data.EMA
            range    = $Data.Range
            volRatio = $Data.VolRatio
        } | ConvertTo-Json -Compress

        $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        $query = "INSERT INTO signals (timestamp, symbol, direction, score, price, tp1, tp2, tp3, sl, reasons, source) VALUES ('$timestamp', '$sym', '$direction', $($Data.Score), $($Data.Prix), $($Data.TP1), $($Data.TP2), $($Data.TP3), $($Data.SL), '$reasons', 'scanner-pro-v2')"

        # Utiliser sqlite3 si disponible
        $sqlite = Get-Command sqlite3 -ErrorAction SilentlyContinue
        if ($sqlite) {
            & sqlite3 $script:SQL_DB $query 2>$null
        } else {
            # Fallback: System.Data.SQLite si disponible
            try {
                Add-Type -Path "C:\Program Files\System.Data.SQLite\System.Data.SQLite.dll" -ErrorAction SilentlyContinue
                $conn = New-Object System.Data.SQLite.SQLiteConnection("Data Source=$($script:SQL_DB)")
                $conn.Open()
                $cmd = $conn.CreateCommand()
                $cmd.CommandText = $query
                $cmd.ExecuteNonQuery() | Out-Null
                $conn.Close()
            } catch {
                # Silencieux - DB save optionnel
            }
        }
    } catch {
        # Silencieux
    }
}

# ============================================================================
# SECTION I: SELF-CORRECTION ENGINE - Predictions tracking + Adaptive weights
# ============================================================================

function Initialize-PredictionsDB {
    <#
    .SYNOPSIS Cree la table predictions dans SQLite si elle n'existe pas.
    #>
    if (-not (Test-Path $script:SQL_DB)) { return $false }

    $createSQL = @"
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    symbol TEXT NOT NULL,
    direction TEXT,
    confidence REAL,
    entry_price REAL,
    tp1 REAL, tp2 REAL, tp3 REAL, sl REAL,
    score INTEGER,
    models_used TEXT,
    model_votes TEXT,
    price_15m REAL,
    price_1h REAL,
    price_4h REAL,
    hit_tp1 BOOLEAN DEFAULT 0,
    hit_tp2 BOOLEAN DEFAULT 0,
    hit_sl BOOLEAN DEFAULT 0,
    result TEXT DEFAULT 'PENDING',
    pnl_pct REAL,
    checked_at DATETIME
);
"@

    try {
        $sqlite = Get-Command sqlite3 -ErrorAction SilentlyContinue
        if ($sqlite) {
            & sqlite3 $script:SQL_DB $createSQL 2>$null
            return $true
        } else {
            try {
                Add-Type -Path "C:\Program Files\System.Data.SQLite\System.Data.SQLite.dll" -ErrorAction SilentlyContinue
                $conn = New-Object System.Data.SQLite.SQLiteConnection("Data Source=$($script:SQL_DB)")
                $conn.Open()
                $cmd = $conn.CreateCommand()
                $cmd.CommandText = $createSQL
                $cmd.ExecuteNonQuery() | Out-Null
                $conn.Close()
                return $true
            } catch { return $false }
        }
    } catch { return $false }
}

function Save-Prediction {
    <#
    .SYNOPSIS Sauvegarde une prediction CQ dans la table predictions.
    #>
    param(
        [string]$Symbol,
        [string]$Direction,
        [double]$Confidence,
        [double]$EntryPrice,
        [double]$TP1, [double]$TP2, [double]$TP3, [double]$SL,
        [int]$Score,
        [int]$ModelsUsed,
        [hashtable]$ModelVotes = @{}
    )

    if (-not (Test-Path $script:SQL_DB)) { return }
    Initialize-PredictionsDB | Out-Null

    $modelVotesJson = ($ModelVotes | ConvertTo-Json -Compress) -replace "'", "''"
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

    $query = "INSERT INTO predictions (created_at, symbol, direction, confidence, entry_price, tp1, tp2, tp3, sl, score, models_used, model_votes) VALUES ('$timestamp', '$Symbol', '$Direction', $Confidence, $EntryPrice, $TP1, $TP2, $TP3, $SL, $Score, $ModelsUsed, '$modelVotesJson')"

    try {
        $sqlite = Get-Command sqlite3 -ErrorAction SilentlyContinue
        if ($sqlite) {
            & sqlite3 $script:SQL_DB $query 2>$null
        } else {
            try {
                Add-Type -Path "C:\Program Files\System.Data.SQLite\System.Data.SQLite.dll" -ErrorAction SilentlyContinue
                $conn = New-Object System.Data.SQLite.SQLiteConnection("Data Source=$($script:SQL_DB)")
                $conn.Open()
                $cmd = $conn.CreateCommand()
                $cmd.CommandText = $query
                $cmd.ExecuteNonQuery() | Out-Null
                $conn.Close()
            } catch {}
        }
    } catch {}
}

function Check-Predictions {
    <#
    .SYNOPSIS Verifie les predictions PENDING: compare prix actuel vs entry/TP/SL.
    Met a jour result = WIN/LOSS/PARTIAL et pnl_pct.
    #>
    param([switch]$Verbose)

    if (-not (Test-Path $script:SQL_DB)) { return @() }
    Initialize-PredictionsDB | Out-Null

    $results = @()
    $sqlite = Get-Command sqlite3 -ErrorAction SilentlyContinue
    if (-not $sqlite) { return @() }

    # Lire predictions PENDING plus vieilles que 15 min
    $pendingRaw = & sqlite3 -separator '|' $script:SQL_DB "SELECT id, symbol, direction, confidence, entry_price, tp1, tp2, tp3, sl, score, models_used, model_votes, created_at FROM predictions WHERE result = 'PENDING' AND created_at <= datetime('now', 'localtime', '-15 minutes') ORDER BY created_at ASC LIMIT 50" 2>$null

    if (-not $pendingRaw) { return @() }

    foreach ($line in $pendingRaw) {
        $parts = $line -split '\|'
        if ($parts.Count -lt 13) { continue }

        $id = $parts[0]
        $symbol = $parts[1]
        $direction = $parts[2]
        $entryPrice = [double]$parts[4]
        $tp1 = [double]$parts[5]
        $tp2 = [double]$parts[6]
        $tp3 = [double]$parts[7]
        $sl = [double]$parts[8]
        $createdAt = $parts[12]

        # Recuperer prix actuel
        $fullSym = if ($symbol -match '_USDT$') { $symbol } else { "${symbol}_USDT" }
        try {
            $ticker = (Invoke-RestMethod -Uri "$script:MEXC_API/ticker?symbol=$fullSym" -TimeoutSec 5).data
            $currentPrice = [double]$ticker.lastPrice
        } catch { continue }

        # Calculer age de la prediction
        $ageMinutes = ((Get-Date) - [datetime]$createdAt).TotalMinutes

        # Determiner le prix a utiliser pour chaque timeframe
        $priceCol = ''
        if ($ageMinutes -ge 240) { $priceCol = 'price_4h' }
        elseif ($ageMinutes -ge 60) { $priceCol = 'price_1h' }
        else { $priceCol = 'price_15m' }

        # Calculer PnL et result
        $pnl = 0
        $result = 'PENDING'
        $hitTP1 = 0; $hitTP2 = 0; $hitSL = 0

        if ($direction -eq 'LONG') {
            $pnl = [math]::Round(($currentPrice - $entryPrice) / $entryPrice * 100, 2)
            if ($currentPrice -ge $tp2) { $result = 'WIN'; $hitTP1 = 1; $hitTP2 = 1 }
            elseif ($currentPrice -ge $tp1) { $result = 'PARTIAL'; $hitTP1 = 1 }
            elseif ($currentPrice -le $sl) { $result = 'LOSS'; $hitSL = 1 }
            elseif ($ageMinutes -ge 240) {
                $result = if ($pnl -gt 0) { 'WIN' } else { 'LOSS' }
            }
        } elseif ($direction -eq 'SHORT') {
            $pnl = [math]::Round(($entryPrice - $currentPrice) / $entryPrice * 100, 2)
            if ($currentPrice -le $tp2) { $result = 'WIN'; $hitTP1 = 1; $hitTP2 = 1 }
            elseif ($currentPrice -le $tp1) { $result = 'PARTIAL'; $hitTP1 = 1 }
            elseif ($currentPrice -ge $sl) { $result = 'LOSS'; $hitSL = 1 }
            elseif ($ageMinutes -ge 240) {
                $result = if ($pnl -gt 0) { 'WIN' } else { 'LOSS' }
            }
        } else {
            # HOLD - marquer comme checked apres 4h
            if ($ageMinutes -ge 240) { $result = 'HOLD_OK' }
        }

        if ($result -ne 'PENDING') {
            $now = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
            $updateSQL = "UPDATE predictions SET $priceCol = $currentPrice, hit_tp1 = $hitTP1, hit_tp2 = $hitTP2, hit_sl = $hitSL, result = '$result', pnl_pct = $pnl, checked_at = '$now' WHERE id = $id"
            & sqlite3 $script:SQL_DB $updateSQL 2>$null

            $results += [PSCustomObject]@{
                Id        = $id
                Symbol    = $symbol
                Direction = $direction
                Entry     = $entryPrice
                Current   = $currentPrice
                PnL       = $pnl
                Result    = $result
                Age       = [math]::Round($ageMinutes, 0)
            }

            if ($Verbose) {
                $color = switch ($result) { 'WIN' { 'Green' }; 'PARTIAL' { 'Yellow' }; 'LOSS' { 'Red' }; default { 'Gray' } }
                Write-Host "  [$result] $symbol $direction Entry:$entryPrice Now:$currentPrice PnL:${pnl}% (${ageMinutes}min)" -ForegroundColor $color
            }
        }
    }

    return $results
}

function Get-ModelAccuracy {
    <#
    .SYNOPSIS Calcule l'accuracy par modele depuis les predictions resolues.
    Retourne un tableau avec nom, total, wins, losses, accuracy%, avg_pnl.
    #>
    param([int]$Days = 14)

    if (-not (Test-Path $script:SQL_DB)) { return @() }

    $sqlite = Get-Command sqlite3 -ErrorAction SilentlyContinue
    if (-not $sqlite) { return @() }

    $rows = & sqlite3 -separator '|' $script:SQL_DB "SELECT model_votes, direction, result, pnl_pct FROM predictions WHERE result IN ('WIN','LOSS','PARTIAL') AND created_at >= datetime('now', 'localtime', '-$Days days')" 2>$null

    if (-not $rows) {
        Write-Host "  Pas de predictions resolues (${Days}j)" -ForegroundColor Yellow
        return @()
    }

    $modelStats = @{}

    foreach ($row in $rows) {
        $parts = $row -split '\|'
        if ($parts.Count -lt 4) { continue }

        $votesJson = $parts[0]
        $direction = $parts[1]
        $result = $parts[2]
        $pnl = [double]$parts[3]

        try {
            $votes = $votesJson | ConvertFrom-Json
        } catch { continue }

        foreach ($prop in $votes.PSObject.Properties) {
            $modelName = $prop.Name
            $vote = $prop.Value.vote

            if (-not $modelStats.ContainsKey($modelName)) {
                $modelStats[$modelName] = @{ Total = 0; Correct = 0; Wrong = 0; PnLSum = 0 }
            }

            $modelStats[$modelName].Total++
            $modelStats[$modelName].PnLSum += $pnl

            # Correct = model voted same direction as consensus AND result is WIN/PARTIAL
            $isCorrect = ($vote -eq $direction -and $result -in @('WIN', 'PARTIAL'))
            # Also correct if voted opposite and result is LOSS (was right to disagree)
            $isCorrectContrarian = ($vote -ne $direction -and $vote -ne 'HOLD' -and $result -eq 'LOSS')

            if ($isCorrect -or $isCorrectContrarian) {
                $modelStats[$modelName].Correct++
            } else {
                $modelStats[$modelName].Wrong++
            }
        }
    }

    $output = @()
    foreach ($kv in $modelStats.GetEnumerator() | Sort-Object { $_.Value.Total } -Descending) {
        $acc = if ($kv.Value.Total -gt 0) { [math]::Round($kv.Value.Correct / $kv.Value.Total * 100, 1) } else { 0 }
        $avgPnl = if ($kv.Value.Total -gt 0) { [math]::Round($kv.Value.PnLSum / $kv.Value.Total, 2) } else { 0 }
        $output += [PSCustomObject]@{
            Model    = $kv.Key
            Total    = $kv.Value.Total
            Correct  = $kv.Value.Correct
            Wrong    = $kv.Value.Wrong
            Accuracy = $acc
            AvgPnL   = $avgPnl
        }
    }

    return $output
}

function Get-AdaptiveWeights {
    <#
    .SYNOPSIS Calcule les poids adaptatifs M1/M2/M3 basés sur l'accuracy par serveur.
    Retourne $null si pas assez de donnees (< 5 predictions), sinon hashtable M1/M2/M3.
    Poids = base_weight * (0.7 + 0.6 * server_accuracy_ratio)
    Range: base * 0.7 a base * 1.3
    #>

    $accuracy = Get-ModelAccuracy -Days 14
    if (-not $accuracy -or $accuracy.Count -lt 3) { return $null }

    $totalPredictions = ($accuracy | Measure-Object -Property Total -Sum).Sum
    if ($totalPredictions -lt 5) { return $null }

    # Agreger par serveur (M1, M2, M3)
    $serverStats = @{ M1 = @{ Correct = 0; Total = 0 }; M2 = @{ Correct = 0; Total = 0 }; M3 = @{ Correct = 0; Total = 0 } }

    foreach ($m in $accuracy) {
        $server = if ($m.Model -match '^M1') { 'M1' } elseif ($m.Model -match '^M2') { 'M2' } elseif ($m.Model -match '^M3') { 'M3' } else { continue }
        $serverStats[$server].Correct += $m.Correct
        $serverStats[$server].Total += $m.Total
    }

    $baseWeights = @{ M1 = $script:CQ_CLUSTER.M1.Weight; M2 = $script:CQ_CLUSTER.M2.Weight; M3 = $script:CQ_CLUSTER.M3.Weight }
    $adaptiveWeights = @{}

    foreach ($srv in @('M1', 'M2', 'M3')) {
        $stats = $serverStats[$srv]
        $accRatio = if ($stats.Total -gt 0) { $stats.Correct / $stats.Total } else { 0.5 }
        # Scale: 0.7 to 1.3x base weight based on accuracy (0% → 0.7x, 100% → 1.3x)
        $multiplier = 0.7 + 0.6 * $accRatio
        $adaptiveWeights[$srv] = [math]::Round($baseWeights[$srv] * $multiplier, 3)
    }

    return $adaptiveWeights
}

function Show-PredictionsDashboard {
    <#
    .SYNOPSIS Affiche le dashboard predictions: recentes, stats, accuracy par modele.
    #>
    param([int]$Limit = 20)

    Write-Host "`n================================================================" -ForegroundColor Magenta
    Write-Host "    PREDICTIONS DASHBOARD - Self-Correction Engine" -ForegroundColor Yellow
    Write-Host "================================================================" -ForegroundColor Magenta

    $sqlite = Get-Command sqlite3 -ErrorAction SilentlyContinue
    if (-not $sqlite -or -not (Test-Path $script:SQL_DB)) {
        Write-Host "  SQLite non disponible" -ForegroundColor Red
        return
    }

    # Stats globales
    $statsRaw = & sqlite3 -separator '|' $script:SQL_DB "SELECT result, COUNT(*), ROUND(AVG(pnl_pct),2) FROM predictions WHERE result != 'PENDING' GROUP BY result" 2>$null
    Write-Host "`n  --- STATS GLOBALES ---" -ForegroundColor Cyan
    if ($statsRaw) {
        foreach ($line in $statsRaw) {
            $p = $line -split '\|'
            $color = switch ($p[0]) { 'WIN' { 'Green' }; 'PARTIAL' { 'Yellow' }; 'LOSS' { 'Red' }; default { 'Gray' } }
            Write-Host "  $($p[0]): $($p[1]) predictions (avg PnL: $($p[2])%)" -ForegroundColor $color
        }
    }

    # Predictions recentes
    Write-Host "`n  --- PREDICTIONS RECENTES ---" -ForegroundColor Cyan
    $recentRaw = & sqlite3 -separator '|' $script:SQL_DB "SELECT symbol, direction, confidence, entry_price, result, pnl_pct, created_at FROM predictions ORDER BY created_at DESC LIMIT $Limit" 2>$null
    if ($recentRaw) {
        foreach ($line in $recentRaw) {
            $p = $line -split '\|'
            $sym = $p[0]; $dir = $p[1]; $conf = $p[2]; $entry = $p[3]; $res = $p[4]; $pnl = $p[5]; $ts = $p[6]
            $color = switch ($res) { 'WIN' { 'Green' }; 'PARTIAL' { 'Yellow' }; 'LOSS' { 'Red' }; 'PENDING' { 'DarkGray' }; default { 'Gray' } }
            Write-Host "  $ts | $sym $dir ${conf}% Entry:$entry | $res PnL:${pnl}%" -ForegroundColor $color
        }
    }

    # Pending count
    $pendingCount = & sqlite3 $script:SQL_DB "SELECT COUNT(*) FROM predictions WHERE result = 'PENDING'" 2>$null
    Write-Host "`n  PENDING: $pendingCount predictions en attente" -ForegroundColor DarkGray

    # Accuracy par modele
    Write-Host "`n  --- ACCURACY PAR MODELE (14j) ---" -ForegroundColor Cyan
    $accuracy = Get-ModelAccuracy -Days 14
    if ($accuracy) {
        $accuracy | Sort-Object Accuracy -Descending | Format-Table Model, Total, Correct, Wrong, Accuracy, AvgPnL -AutoSize
    }

    # Poids adaptatifs
    $aw = Get-AdaptiveWeights
    if ($aw) {
        Write-Host "  POIDS ADAPTATIFS: M1=$($aw.M1) M2=$($aw.M2) M3=$($aw.M3)" -ForegroundColor Yellow
        Write-Host "  (Base: M1=$($script:CQ_CLUSTER.M1.Weight) M2=$($script:CQ_CLUSTER.M2.Weight) M3=$($script:CQ_CLUSTER.M3.Weight))" -ForegroundColor DarkGray
    } else {
        Write-Host "  POIDS: Statiques (< 5 predictions resolues)" -ForegroundColor DarkGray
    }

    Write-Host "================================================================`n" -ForegroundColor Magenta
}

# ============================================================================
# SECTION J: MARKET REGIME DETECTION
# ============================================================================

function Get-MarketRegime {
    <#
    .SYNOPSIS Detecte le regime de marche via BTC: BULL, BEAR, ou RANGE.
    Utilise BTC change24h + RSI 1H + ADX pour classification.
    Retourne regime, parametres adaptes (thresholds, focus).
    #>

    $regime = @{
        Type       = 'RANGE'
        BtcPrice   = 0
        BtcChange  = 0
        BtcRSI     = 50
        BtcADX     = 0
        Focus      = 'accumulation'
        MinChange  = 2.0
        ScoreBonus = 0
        SLMultiplier = 1.0
        TPMultiplier = 1.0
    }

    try {
        # BTC ticker
        $btcTicker = (Invoke-RestMethod -Uri "$script:MEXC_API/ticker?symbol=BTC_USDT" -TimeoutSec 5).data
        $regime.BtcPrice = [double]$btcTicker.lastPrice
        $regime.BtcChange = [math]::Round([double]$btcTicker.riseFallRate * 100, 1)

        # BTC klines 1H pour RSI + ADX
        $btcKlines = Get-MexcKlines -Symbol 'BTC_USDT' -Interval 'Min60' -Limit 48
        if ($btcKlines) {
            $regime.BtcRSI = Get-RSI -Closes $btcKlines.closes -Period 14
            $adxResult = Get-ADX-DMI -Highs $btcKlines.highs -Lows $btcKlines.lows -Closes $btcKlines.closes
            $regime.BtcADX = $adxResult.ADX
        }
    } catch {
        Write-Host "  Regime: BTC data indisponible, default RANGE" -ForegroundColor Yellow
        return $regime
    }

    # Classification
    if ($regime.BtcChange -gt 3 -and $regime.BtcRSI -gt 55) {
        $regime.Type = 'BULL'
        $regime.Focus = 'breakout'
        $regime.MinChange = 1.0      # Plus permissif
        $regime.ScoreBonus = 5       # Bonus breakout
        $regime.TPMultiplier = 1.3   # TP plus large
        $regime.SLMultiplier = 1.1   # SL un peu plus large
    }
    elseif ($regime.BtcChange -lt -3 -and $regime.BtcRSI -lt 45) {
        $regime.Type = 'BEAR'
        $regime.Focus = 'reversal+squeeze'
        $regime.MinChange = 3.0      # Plus strict
        $regime.ScoreBonus = -5      # Penalty breakout
        $regime.TPMultiplier = 0.7   # TP serrés
        $regime.SLMultiplier = 0.8   # SL serré
    }
    else {
        $regime.Type = 'RANGE'
        $regime.Focus = 'accumulation'
        $regime.MinChange = 2.0
        $regime.ScoreBonus = 0
        $regime.TPMultiplier = 1.0
        $regime.SLMultiplier = 1.0
    }

    # Refinement par ADX
    if ($regime.BtcADX -gt 30) {
        # Forte tendance - renforcer le regime
        if ($regime.Type -eq 'BULL') { $regime.ScoreBonus += 3 }
        elseif ($regime.Type -eq 'BEAR') { $regime.ScoreBonus -= 3 }
    }
    elseif ($regime.BtcADX -lt 15) {
        # Pas de tendance - forcer RANGE
        $regime.Type = 'RANGE'
        $regime.Focus = 'accumulation+volume_spikes'
    }

    return $regime
}

# ============================================================================
# SECTION K: SCANNER AUTONOME ADAPTATIF
# ============================================================================

function Start-AutonomousScan {
    <#
    .SYNOPSIS Scanner autonome en boucle continue avec self-correction.
    Detecte le regime → scan 850+ paires → top 20 → indicateurs multi-TF →
    CQ v5.0 sur top 5 → check predictions → adaptive weights → save → telegram.
    .PARAMETER IntervalMinutes  Intervalle entre scans (default 5)
    .PARAMETER MaxCycles  Nombre max de cycles (0 = infini)
    .PARAMETER NoTelegram  Desactive les alertes Telegram
    .EXAMPLE Start-AutonomousScan -IntervalMinutes 5
    .EXAMPLE Start-AutonomousScan -IntervalMinutes 3 -MaxCycles 10
    #>
    param(
        [int]$IntervalMinutes = 5,
        [int]$MaxCycles = 0,
        [int]$TopCandidates = 20,
        [int]$TopCQ = 5,
        [switch]$NoTelegram
    )

    # Init DB
    Initialize-PredictionsDB | Out-Null

    $cycle = 0
    $lowAccuracyStreak = 0
    $allCycleResults = @()

    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Magenta
    Write-Host "    SCANNER AUTONOME ADAPTATIF v3.0" -ForegroundColor Yellow
    Write-Host "    CQ v5.0 (8 models) | Self-Correction | Market Regime" -ForegroundColor White
    Write-Host "    Interval: ${IntervalMinutes}min | Top: $TopCandidates -> CQ: $TopCQ" -ForegroundColor Gray
    Write-Host "    $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
    Write-Host "================================================================" -ForegroundColor Magenta

    while ($true) {
        $cycle++
        $cycleStart = Get-Date

        if ($MaxCycles -gt 0 -and $cycle -gt $MaxCycles) {
            Write-Host "`n  MAX CYCLES ATTEINT ($MaxCycles). Arret." -ForegroundColor Yellow
            break
        }

        Write-Host "`n  ======== CYCLE #$cycle - $(Get-Date -Format 'HH:mm:ss') ========" -ForegroundColor Cyan

        # 1. Market Regime
        Write-Host "  [1/7] Detection regime..." -ForegroundColor DarkGray
        $regime = Get-MarketRegime
        $regimeColor = switch ($regime.Type) { 'BULL' { 'Green' }; 'BEAR' { 'Red' }; default { 'Yellow' } }
        Write-Host "  -> REGIME: $($regime.Type) | BTC: `$$($regime.BtcPrice) ($($regime.BtcChange)%) | RSI:$($regime.BtcRSI) ADX:$($regime.BtcADX)" -ForegroundColor $regimeColor
        Write-Host "  -> Focus: $($regime.Focus) | MinChange: $($regime.MinChange)% | TP:$($regime.TPMultiplier)x SL:$($regime.SLMultiplier)x" -ForegroundColor DarkGray

        # 2. Check predictions passees
        Write-Host "  [2/7] Check predictions passees..." -ForegroundColor DarkGray
        $checkResults = Check-Predictions -Verbose
        if ($checkResults.Count -gt 0) {
            $wins = ($checkResults | Where-Object { $_.Result -in @('WIN', 'PARTIAL') }).Count
            $losses = ($checkResults | Where-Object { $_.Result -eq 'LOSS' }).Count
            Write-Host "  -> Checked: $($checkResults.Count) | WIN:$wins LOSS:$losses" -ForegroundColor $(if ($wins -gt $losses) { 'Green' } else { 'Red' })
        }

        # 3. Adaptive weights
        Write-Host "  [3/7] Poids adaptatifs..." -ForegroundColor DarkGray
        $adaptiveW = Get-AdaptiveWeights
        if ($adaptiveW) {
            Write-Host "  -> M1=$($adaptiveW.M1) M2=$($adaptiveW.M2) M3=$($adaptiveW.M3)" -ForegroundColor Yellow
        } else {
            Write-Host "  -> Poids statiques (pas assez de donnees)" -ForegroundColor DarkGray
        }

        # 4. Scan marche
        Write-Host "  [4/7] Scan MEXC tickers..." -ForegroundColor DarkGray
        try {
            $allTickers = Get-MexcTickers -MinVolume 500000
        } catch {
            Write-Host "  ERREUR scan tickers: $($_.Exception.Message)" -ForegroundColor Red
            Start-Sleep -Seconds ($IntervalMinutes * 60)
            continue
        }
        Write-Host "  -> $($allTickers.Count) paires (vol > 500K)" -ForegroundColor Green

        # 5. Filtrer et scorer candidats (top N)
        Write-Host "  [5/7] Filtrage top $TopCandidates candidats..." -ForegroundColor DarkGray
        $candidates = @()

        foreach ($t in $allTickers) {
            $absChange = [math]::Abs($t.Change)
            if ($absChange -lt $regime.MinChange) { continue }

            $preScore = $absChange * [math]::Min($t.Volume / 1e6, 5) * 3
            if ($t.Change -gt 5) { $preScore *= 1.3 }
            if ($t.Change -gt 10) { $preScore *= 1.5 }
            $preScore += $regime.ScoreBonus

            if ($preScore -gt 10) {
                $candidates += [PSCustomObject]@{
                    Symbol   = $t.Symbol
                    Prix     = $t.Prix
                    Change   = $t.Change
                    VolumeM  = [math]::Round($t.Volume / 1e6, 1)
                    PreScore = [math]::Round($preScore, 1)
                    Funding  = $t.FundingRate
                }
            }
        }

        $candidates = $candidates | Sort-Object PreScore -Descending | Select-Object -First $TopCandidates
        Write-Host "  -> $($candidates.Count) candidats" -ForegroundColor Green

        if ($candidates.Count -eq 0) {
            Write-Host "  Aucun candidat. Attente ${IntervalMinutes}min..." -ForegroundColor Yellow
            Start-Sleep -Seconds ($IntervalMinutes * 60)
            continue
        }

        # 6. Indicateurs multi-TF sur top candidats → re-scorer → top CQ
        Write-Host "  [6/7] Indicateurs multi-TF + scoring..." -ForegroundColor DarkGray
        $scoredCandidates = @()

        foreach ($c in $candidates) {
            try {
                $kl60 = Get-MexcKlines -Symbol $c.Symbol -Interval 'Min60' -Limit 48
                if (-not $kl60) { continue }

                $ind60 = Get-AllIndicators -Klines $kl60 -LastPrice $c.Prix

                # Quick score (sans CQ) pour pre-filtrer
                $quickScore = Get-BreakoutScore -Indicators1H $ind60 -FundingRate $c.Funding
                $scoredCandidates += [PSCustomObject]@{
                    Symbol     = $c.Symbol
                    Prix       = $c.Prix
                    Change     = $c.Change
                    VolumeM    = $c.VolumeM
                    Funding    = $c.Funding
                    QuickScore = $quickScore.Score
                    Indicators = $ind60
                    Verdict    = $quickScore.Verdict
                    Reasons    = $quickScore.Reasons
                }
            } catch {}
        }

        $scoredCandidates = $scoredCandidates | Sort-Object QuickScore -Descending
        Write-Host "  -> $($scoredCandidates.Count) scores, top: $(($scoredCandidates | Select-Object -First 3 | ForEach-Object { "$($_.Symbol)=$($_.QuickScore)" }) -join ', ')" -ForegroundColor Green

        # 7. CQ v5.0 sur top N
        $cqCandidates = $scoredCandidates | Select-Object -First $TopCQ
        Write-Host "  [7/7] CQ v5.0 (8 models) sur $($cqCandidates.Count) candidats..." -ForegroundColor DarkGray

        $signals = @()
        foreach ($c in $cqCandidates) {
            Write-Host "`n  --- $($c.Symbol) (S:$($c.QuickScore) | $($c.Change)% | $($c.VolumeM)M) ---" -ForegroundColor Cyan

            $ind = $c.Indicators
            $volM = $c.VolumeM
            $indStr = "RSI=$($ind.RSI) StochK=$($ind.StochRSI.K) ADX=$($ind.ADX_DMI.ADX) MACD=$($ind.MACD.Direction) Chaikin=$($ind.Chaikin.Zone) EMA=$($ind.EMA.Status) Range=$($ind.RangePos)%"

            $cqResult = Get-CQConsensus -Symbol $c.Symbol -Price $c.Prix -ChangePct $c.Change -VolumeM $volM -Indicators $indStr -SendTelegram:(-not $NoTelegram)

            if ($cqResult.Success) {
                $color = switch ($cqResult.Consensus) { 'LONG' { 'Green' }; 'SHORT' { 'Red' }; default { 'Yellow' } }
                Write-Host "    -> $($cqResult.Consensus) | Conf: $($cqResult.Confidence)% | Models: $($cqResult.Models)/8 | R:R $($cqResult.RR):1" -ForegroundColor $color

                # Apply regime multipliers to TP/SL
                $tp1 = $cqResult.TP1; $tp2 = $cqResult.TP2; $tp3 = $cqResult.TP3; $sl = $cqResult.SL
                if ($regime.TPMultiplier -ne 1.0 -and $cqResult.Consensus -eq 'LONG') {
                    $diff1 = ($tp1 - $c.Prix) * $regime.TPMultiplier; $tp1 = [math]::Round($c.Prix + $diff1, 8)
                    $diff2 = ($tp2 - $c.Prix) * $regime.TPMultiplier; $tp2 = [math]::Round($c.Prix + $diff2, 8)
                    $diff3 = ($tp3 - $c.Prix) * $regime.TPMultiplier; $tp3 = [math]::Round($c.Prix + $diff3, 8)
                    $diffSL = ($c.Prix - $sl) * $regime.SLMultiplier; $sl = [math]::Round($c.Prix - $diffSL, 8)
                }

                # Save prediction
                if ($cqResult.Consensus -ne 'HOLD' -and $cqResult.Confidence -ge 55) {
                    Save-Prediction -Symbol $c.Symbol -Direction $cqResult.Consensus -Confidence $cqResult.Confidence `
                        -EntryPrice $c.Prix -TP1 $tp1 -TP2 $tp2 -TP3 $tp3 -SL $sl `
                        -Score $c.QuickScore -ModelsUsed $cqResult.Models -ModelVotes $cqResult.ModelVotes
                }

                $signals += [PSCustomObject]@{
                    Symbol     = $c.Symbol
                    Prix       = $c.Prix
                    Change     = $c.Change
                    QuickScore = $c.QuickScore
                    Consensus  = $cqResult.Consensus
                    Confidence = $cqResult.Confidence
                    Models     = $cqResult.Models
                    TP1 = $tp1; TP2 = $tp2; TP3 = $tp3; SL = $sl
                    RR         = $cqResult.RR
                    Regime     = $regime.Type
                }
            }
        }

        # Dashboard cycle
        # V3.2: Confidence threshold raised from 60% to 80%
    $goSignals = $signals | Where-Object { $_.Confidence -ge 80 -and $_.Consensus -ne 'HOLD' }
        Write-Host "`n  --- RESULTATS CYCLE #$cycle ---" -ForegroundColor Magenta
        if ($signals.Count -gt 0) {
            $signals | Sort-Object Confidence -Descending | Format-Table Symbol, Prix, Change, QuickScore, Consensus, Confidence, Models, RR, Regime -AutoSize
        }
        if ($goSignals.Count -gt 0) {
            Write-Host "  GO SIGNALS: $($goSignals.Count)" -ForegroundColor Green
            foreach ($s in $goSignals) {
                Write-Host "  -> $($s.Consensus) $($s.Symbol) @ $($s.Prix) | Conf:$($s.Confidence)% | TP1:$($s.TP1) SL:$($s.SL)" -ForegroundColor Green
            }
        }

        # Accuracy check for auto-stop
        $recentAccuracy = Get-ModelAccuracy -Days 3
        if ($recentAccuracy -and $recentAccuracy.Count -gt 0) {
            $avgAcc = ($recentAccuracy | Measure-Object -Property Accuracy -Average).Average
            if ($avgAcc -lt 35) {
                $lowAccuracyStreak++
                Write-Host "  ATTENTION: Accuracy basse (${avgAcc}%) - streak: $lowAccuracyStreak/5" -ForegroundColor Red
            } else {
                $lowAccuracyStreak = 0
            }

            if ($lowAccuracyStreak -ge 5) {
                Write-Host "`n  AUTO-STOP: Accuracy < 35% pendant 5 cycles consecutifs" -ForegroundColor Red
                Write-Host "  Dernier accuracy: ${avgAcc}%" -ForegroundColor Red
                if (-not $NoTelegram) {
                    try {
                        $stopMsg = "SCANNER AUTO-STOP: Accuracy ${avgAcc}% < 35% pendant 5 cycles. Revision necessaire."
                        $teleBody = @{ chat_id = $script:TELEGRAM_CHAT; text = $stopMsg } | ConvertTo-Json -Depth 3
                        Invoke-RestMethod -Uri "https://api.telegram.org/bot$($script:TELEGRAM_TOKEN)/sendMessage" -Method Post -Body $teleBody -ContentType 'application/json; charset=utf-8' -TimeoutSec 10 | Out-Null
                    } catch {}
                }
                break
            }
        }

        # Timing
        $elapsed = [math]::Round(((Get-Date) - $cycleStart).TotalSeconds, 0)
        $sleepSec = [math]::Max(10, ($IntervalMinutes * 60) - $elapsed)
        Write-Host "`n  Cycle #$cycle termine en ${elapsed}s. GO:$($goSignals.Count). Sleep ${sleepSec}s..." -ForegroundColor DarkGray
        Write-Host "  (Ctrl+C pour arreter)" -ForegroundColor DarkGray

        $allCycleResults += @{ Cycle = $cycle; Signals = $signals.Count; GO = $goSignals.Count; Regime = $regime.Type; Elapsed = $elapsed }

        Start-Sleep -Seconds $sleepSec
    }

    # Summary
    Write-Host "`n================================================================" -ForegroundColor Magenta
    Write-Host "    SCANNER AUTONOME - RESUME FINAL" -ForegroundColor Yellow
    Write-Host "    Cycles: $cycle | Duree totale: $([math]::Round(((Get-Date) - $cycleStart).TotalMinutes, 1))min" -ForegroundColor White
    Write-Host "================================================================`n" -ForegroundColor Magenta

    Show-PredictionsDashboard
}

# ============================================================================
# EXPORT
# ============================================================================
Write-Host "  [Scanner Pro v3.0 + CQ Pipeline v5.0] Module charge" -ForegroundColor DarkCyan
Write-Host "  Commandes: Scan-TopMovers, Scan-Breakout, Scan-Token, Start-CQScan, Get-CQConsensus" -ForegroundColor DarkCyan
Write-Host "  Nouvelles: Start-AutonomousScan, Get-MarketRegime, Get-ModelAccuracy, Show-PredictionsDashboard" -ForegroundColor DarkCyan
