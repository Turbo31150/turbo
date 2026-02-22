"""JARVIS — Commandes de maintenance, monitoring et securite systeme."""

from __future__ import annotations

from src.commands import JarvisCommand

MAINTENANCE_COMMANDS: list[JarvisCommand] = [
    # ══════════════════════════════════════════════════════════════════════
    # MONITORING CLUSTER IA
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("cluster_health", "trading", "Health check rapide du cluster IA", [
        "health check cluster", "verifie le cluster ia",
        "est ce que le cluster va bien", "ping le cluster",
        "check cluster ia", "cluster ok",
    ], "powershell", "$m2 = try{(Invoke-WebRequest -Uri 'http://192.168.1.26:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; $ol1 = try{(Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; $m3 = try{(Invoke-WebRequest -Uri 'http://192.168.1.113:1234/api/v1/models' -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; \"M2: $(if($m2 -eq 200){'OK'}else{'OFFLINE'}) | OL1: $(if($ol1 -eq 200){'OK'}else{'OFFLINE'}) | M3: $(if($m3 -eq 200){'OK'}else{'OFFLINE'})\""),
    JarvisCommand("gpu_temperatures", "systeme", "Temperatures GPU via nvidia-smi", [
        "temperatures gpu", "gpu temperature", "chauffe les gpu",
        "les gpu chauffent", "temp gpu",
    ], "powershell", "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits | ForEach-Object { $f = $_ -split ','; \"$($f[0].Trim()): $($f[1].Trim())C | GPU $($f[2].Trim())% | VRAM $($f[3].Trim())/$($f[4].Trim()) MB\" }"),
    JarvisCommand("vram_usage", "systeme", "Utilisation VRAM de toutes les GPU", [
        "utilisation vram", "vram utilisee", "combien de vram",
        "etat de la vram", "vram libre",
    ], "powershell", "nvidia-smi --query-gpu=name,memory.used,memory.total,memory.free --format=csv,noheader,nounits | ForEach-Object { $f = $_ -split ','; \"$($f[0].Trim()): $($f[1].Trim())/$($f[2].Trim()) MB (libre: $($f[3].Trim()) MB)\" }"),
    JarvisCommand("ollama_running", "trading", "Modeles Ollama actuellement en memoire", [
        "quels modeles ollama tournent", "ollama running",
        "modeles en memoire ollama", "ollama actifs",
    ], "powershell", "(Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/ps' -TimeoutSec 5).models | ForEach-Object { \"$($_.name) | VRAM: $([math]::Round($_.size_vram/1GB,2)) GB | Until: $($_.expires_at)\" }"),

    # ══════════════════════════════════════════════════════════════════════
    # MONITORING SYSTEME AVANCE
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("disk_io", "systeme", "Activite I/O des disques", [
        "activite des disques", "io disques", "disk io",
        "lecture ecriture disque", "performance disque",
    ], "powershell", "Get-Counter '\\PhysicalDisk(*)\\Disk Reads/sec','\\PhysicalDisk(*)\\Disk Writes/sec' -SampleInterval 1 -MaxSamples 1 | Select-Object -ExpandProperty CounterSamples | Select InstanceName, CookedValue | Out-String"),
    JarvisCommand("network_io", "systeme", "Debit reseau en temps reel", [
        "debit reseau", "trafic reseau", "network io",
        "bande passante utilisee", "activite reseau",
    ], "powershell", "Get-Counter '\\Network Interface(*)\\Bytes Received/sec','\\Network Interface(*)\\Bytes Sent/sec' -SampleInterval 1 -MaxSamples 1 | Select-Object -ExpandProperty CounterSamples | Where CookedValue -gt 0 | Select InstanceName, @{N='KB/s';E={[math]::Round($_.CookedValue/1KB,1)}} | Out-String"),
    JarvisCommand("services_failed", "systeme", "Services Windows en echec", [
        "services en echec", "services plantes", "services failed",
        "quels services ne marchent pas", "services ko",
    ], "powershell", "Get-Service | Where Status -eq 'Stopped' | Where StartType -eq 'Automatic' | Select Name, DisplayName, Status | Out-String"),
    JarvisCommand("event_errors", "systeme", "Dernières erreurs systeme (Event Log)", [
        "erreurs systeme recentes", "derniers errors", "event log errors",
        "quelles erreurs systeme", "erreurs windows recentes",
    ], "powershell", "Get-WinEvent -FilterHashtable @{LogName='System';Level=2} -MaxEvents 10 -ErrorAction SilentlyContinue | Select TimeCreated, Id, Message | Out-String -Width 200"),
    JarvisCommand("boot_time", "systeme", "Temps de demarrage du dernier boot", [
        "temps de demarrage", "boot time", "combien de temps au boot",
        "duree du demarrage", "le pc a mis combien de temps a demarrer",
    ], "powershell", "$boot = Get-WinEvent -FilterHashtable @{LogName='System';ID=6005} -MaxEvents 1 -ErrorAction SilentlyContinue; $before = Get-WinEvent -FilterHashtable @{LogName='System';ID=12} -MaxEvents 1 -ErrorAction SilentlyContinue; if($boot -and $before){ $delta = $boot.TimeCreated - $before.TimeCreated; \"Boot: $([math]::Round($delta.TotalSeconds)) secondes\" } else { 'Donnees indisponibles' }"),

    # ══════════════════════════════════════════════════════════════════════
    # NETTOYAGE & OPTIMISATION
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("nettoyer_prefetch", "systeme", "Nettoyer le dossier Prefetch", [
        "nettoie prefetch", "vide prefetch", "clean prefetch",
        "supprime prefetch",
    ], "powershell", "Remove-Item C:\\Windows\\Prefetch\\* -Force -ErrorAction SilentlyContinue; 'Prefetch nettoye'", confirm=True),
    JarvisCommand("nettoyer_thumbnails", "systeme", "Nettoyer le cache des miniatures", [
        "nettoie les miniatures", "vide le cache miniatures",
        "clean thumbnails", "supprime les thumbnails",
    ], "powershell", "Remove-Item \"$env:LOCALAPPDATA\\Microsoft\\Windows\\Explorer\\thumbcache_*\" -Force -ErrorAction SilentlyContinue; 'Cache miniatures nettoye'"),
    JarvisCommand("nettoyer_logs", "systeme", "Nettoyer les vieux logs", [
        "nettoie les logs", "supprime les vieux logs", "clean logs",
        "vide les logs", "nettoie les journaux",
    ], "powershell", "wevtutil el | ForEach-Object { wevtutil cl $_ 2>$null }; 'Journaux systeme nettoyes'", confirm=True),
    JarvisCommand("taille_dossiers_bureau", "fichiers", "Taille de chaque dossier dans F:\\BUREAU", [
        "taille des projets", "poids des dossiers bureau",
        "combien pese chaque projet", "espace par projet",
    ], "powershell", "Get-ChildItem 'F:\\BUREAU' -Directory | ForEach-Object { $s = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum; [PSCustomObject]@{Dossier=$_.Name; 'Taille(GB)'=[math]::Round($s/1GB,2)} } | Sort 'Taille(GB)' -Descending | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # SECURITE & AUDIT
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("scan_ports_local", "systeme", "Scanner les ports ouverts localement", [
        "scan mes ports", "scan ports local", "quels ports j'expose",
        "ports ouverts en local", "scan securite ports",
    ], "powershell", "Get-NetTCPConnection -State Listen | Group-Object LocalPort | Select @{N='Port';E={$_.Name}}, @{N='Process';E={(Get-Process -Id ($_.Group[0].OwningProcess) -ErrorAction SilentlyContinue).Name}}, Count | Sort Port | Out-String"),
    JarvisCommand("connexions_suspectes", "systeme", "Verifier les connexions sortantes suspectes", [
        "connexions suspectes", "qui se connecte dehors",
        "connexions sortantes", "check connexions",
    ], "powershell", "Get-NetTCPConnection -State Established | Where RemoteAddress -notmatch '^(127|10|192\\.168|0\\.)' | Select RemoteAddress, RemotePort, @{N='Process';E={(Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).Name}} | Sort RemoteAddress -Unique | Out-String"),
    JarvisCommand("autorun_check", "systeme", "Verifier les programmes au demarrage", [
        "quoi se lance au demarrage", "autorun check",
        "programmes auto start", "verifie le demarrage",
        "audit demarrage",
    ], "powershell", "Get-CimInstance Win32_StartupCommand | Select Name, Command, Location | Out-String; Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -ErrorAction SilentlyContinue | Select * -ExcludeProperty PS* | Out-String"),
    JarvisCommand("defender_scan_rapide", "systeme", "Lancer un scan rapide Windows Defender", [
        "scan antivirus", "lance un scan defender", "scan rapide",
        "antivirus scan", "defender scan",
    ], "powershell", "Start-MpScan -ScanType QuickScan; 'Scan rapide Defender lance'"),
    JarvisCommand("defender_status", "systeme", "Statut de Windows Defender", [
        "statut defender", "etat antivirus", "defender ok",
        "windows defender status", "protection antivirus",
    ], "powershell", "Get-MpComputerStatus | Select AntivirusEnabled, RealTimeProtectionEnabled, AntivirusSignatureLastUpdated, QuickScanEndTime | Out-String"),
]
