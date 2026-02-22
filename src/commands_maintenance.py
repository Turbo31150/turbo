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

    # ══════════════════════════════════════════════════════════════════════
    # MONITORING PROCESSUS
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("top_cpu_processes", "systeme", "Top 10 processus par CPU", [
        "top cpu", "processus gourmands cpu", "qui mange le cpu",
        "quoi consomme le cpu", "plus gros cpu",
    ], "powershell", "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, @{N='CPU(s)';E={[math]::Round($_.CPU,1)}}, @{N='RAM(MB)';E={[math]::Round($_.WS/1MB)}} | Format-Table -AutoSize | Out-String"),
    JarvisCommand("top_ram_processes", "systeme", "Top 10 processus par RAM", [
        "top ram", "processus gourmands ram", "qui mange la ram",
        "quoi consomme la memoire", "plus gros ram",
    ], "powershell", "Get-Process | Sort-Object WS -Descending | Select-Object -First 10 Name, @{N='RAM(MB)';E={[math]::Round($_.WS/1MB)}}, @{N='CPU(s)';E={[math]::Round($_.CPU,1)}} | Format-Table -AutoSize | Out-String"),
    JarvisCommand("uptime_system", "systeme", "Uptime du systeme Windows", [
        "uptime", "depuis combien de temps le pc tourne",
        "duree allumage", "combien de temps allume",
    ], "powershell", "$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; $up = (Get-Date) - $boot; \"Allume depuis $($up.Days)j $($up.Hours)h $($up.Minutes)min (boot: $($boot.ToString('dd/MM HH:mm')))\""),
    JarvisCommand("windows_update_check", "systeme", "Verifier les mises a jour Windows disponibles", [
        "mises a jour windows", "windows update", "check updates",
        "verifier les maj", "y a des mises a jour",
    ], "powershell", "try { $s = New-Object -ComObject Microsoft.Update.Session; $u = $s.CreateUpdateSearcher(); $r = $u.Search('IsInstalled=0'); if($r.Updates.Count -gt 0){ $r.Updates | ForEach-Object { $_.Title } | Out-String } else { 'Aucune mise a jour en attente' } } catch { 'Erreur lors de la verification' }"),

    # ══════════════════════════════════════════════════════════════════════
    # RESEAU AVANCE
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ip_publique_externe", "systeme", "Obtenir l'adresse IP publique", [
        "ip publique", "quelle est mon ip", "mon ip publique",
        "adresse ip externe", "mon adresse ip",
    ], "powershell", "(Invoke-RestMethod -Uri 'https://api.ipify.org?format=json' -TimeoutSec 5).ip"),
    JarvisCommand("latence_cluster", "systeme", "Ping de latence vers les noeuds du cluster", [
        "latence cluster", "ping le cluster ia", "latence des noeuds",
        "temps de reponse cluster", "ping noeuds ia",
    ], "powershell", "$m2 = try{(Measure-Command{Invoke-WebRequest -Uri 'http://192.168.1.26:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 5 -UseBasicParsing}).TotalMilliseconds}catch{-1}; $ol1 = try{(Measure-Command{Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5 -UseBasicParsing}).TotalMilliseconds}catch{-1}; $m3 = try{(Measure-Command{Invoke-WebRequest -Uri 'http://192.168.1.113:1234/api/v1/models' -TimeoutSec 5 -UseBasicParsing}).TotalMilliseconds}catch{-1}; \"M2: $([math]::Round($m2))ms | OL1: $([math]::Round($ol1))ms | M3: $([math]::Round($m3))ms\""),
    JarvisCommand("wifi_info", "systeme", "Informations sur la connexion WiFi active", [
        "info wifi", "quel wifi", "connexion wifi",
        "signal wifi", "etat du wifi",
    ], "powershell", "netsh wlan show interfaces | Select-String 'SSID|Signal|Debit|Etat' | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # ESPACE DISQUE
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("espace_disques", "systeme", "Espace libre sur tous les disques", [
        "espace disque", "combien d'espace libre", "espace libre",
        "disques pleins", "etat des disques",
    ], "powershell", "Get-PSDrive -PSProvider FileSystem | Where Used -gt 0 | Select Name, @{N='Utilise(GB)';E={[math]::Round($_.Used/1GB,1)}}, @{N='Libre(GB)';E={[math]::Round($_.Free/1GB,1)}}, @{N='Total(GB)';E={[math]::Round(($_.Used+$_.Free)/1GB,1)}} | Format-Table -AutoSize | Out-String"),
    JarvisCommand("gros_fichiers_bureau", "systeme", "Top 10 plus gros fichiers du bureau", [
        "plus gros fichiers", "gros fichiers bureau",
        "fichiers les plus lourds", "quoi prend de la place",
    ], "powershell", "Get-ChildItem 'F:\\BUREAU' -Recurse -File -ErrorAction SilentlyContinue | Sort Length -Descending | Select -First 10 @{N='Taille(MB)';E={[math]::Round($_.Length/1MB,1)}}, FullName | Format-Table -AutoSize | Out-String -Width 200"),

    # ══════════════════════════════════════════════════════════════════════
    # MONITORING AVANCÉ
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("processus_zombies", "systeme", "Detecter les processus qui ne repondent pas", [
        "processus zombies", "processus bloques", "applications gelees",
        "quoi est bloque", "processes not responding",
    ], "powershell", "Get-Process | Where { $_.Responding -eq $false } | Select Name, Id, @{N='RAM(MB)';E={[math]::Round($_.WS/1MB)}} | Out-String"),
    JarvisCommand("dernier_crash", "systeme", "Dernier crash ou erreur critique Windows", [
        "dernier crash", "derniere erreur critique", "dernier plantage",
        "quand le pc a plante",
    ], "powershell", "Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2} -MaxEvents 5 -ErrorAction SilentlyContinue | Select TimeCreated, LevelDisplayName, Message | Out-String -Width 200"),
    JarvisCommand("temps_allumage_apps", "systeme", "Depuis combien de temps chaque app tourne", [
        "duree des apps", "depuis quand les apps tournent",
        "temps d'execution des processus", "uptime des apps",
    ], "powershell", "Get-Process | Where { $_.CPU -gt 10 } | Sort CPU -Descending | Select -First 10 Name, @{N='Uptime';E={(Get-Date) - $_.StartTime}}, @{N='CPU(s)';E={[math]::Round($_.CPU,1)}} | Format-Table -AutoSize | Out-String"),
    JarvisCommand("taille_cache_navigateur", "systeme", "Taille des caches navigateur Chrome/Edge", [
        "taille cache navigateur", "cache chrome", "cache edge",
        "combien pese le cache web",
    ], "powershell", "$chrome = (Get-ChildItem \"$env:LOCALAPPDATA\\Google\\Chrome\\User Data\\Default\\Cache\" -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum/1MB; $edge = (Get-ChildItem \"$env:LOCALAPPDATA\\Microsoft\\Edge\\User Data\\Default\\Cache\" -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum/1MB; \"Chrome cache: $([math]::Round($chrome,1)) MB | Edge cache: $([math]::Round($edge,1)) MB\""),

    # ══════════════════════════════════════════════════════════════════════
    # NETTOYAGE AVANCÉ
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("nettoyer_cache_navigateur", "systeme", "Vider les caches Chrome et Edge", [
        "vide le cache navigateur", "nettoie le cache chrome",
        "clean cache web", "purge cache navigateur",
    ], "powershell", "Remove-Item \"$env:LOCALAPPDATA\\Google\\Chrome\\User Data\\Default\\Cache\\*\" -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item \"$env:LOCALAPPDATA\\Microsoft\\Edge\\User Data\\Default\\Cache\\*\" -Recurse -Force -ErrorAction SilentlyContinue; 'Caches navigateur nettoyes'", confirm=True),
    JarvisCommand("nettoyer_crash_dumps", "systeme", "Supprimer les crash dumps Windows", [
        "nettoie les crash dumps", "supprime les dumps",
        "clean crash dumps", "vide les crash dumps",
    ], "powershell", "$count = (Get-ChildItem \"$env:LOCALAPPDATA\\CrashDumps\" -File -ErrorAction SilentlyContinue).Count; Remove-Item \"$env:LOCALAPPDATA\\CrashDumps\\*\" -Force -ErrorAction SilentlyContinue; \"$count crash dumps supprimes\""),
    JarvisCommand("nettoyer_windows_old", "systeme", "Taille du dossier Windows.old (ancien systeme)", [
        "taille windows old", "windows old", "combien pese windows old",
        "ancien systeme",
    ], "powershell", "if(Test-Path 'C:\\Windows.old'){ $s = (Get-ChildItem 'C:\\Windows.old' -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum/1GB; \"Windows.old: $([math]::Round($s,1)) GB\" }else{ 'Pas de dossier Windows.old' }"),

    # ══════════════════════════════════════════════════════════════════════
    # CLUSTER IA — Monitoring avance
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("gpu_power_draw", "systeme", "Consommation electrique des GPU", [
        "consommation gpu", "watt gpu", "puissance gpu",
        "combien consomment les gpu", "power draw gpu",
    ], "powershell", "nvidia-smi --query-gpu=name,power.draw,power.limit --format=csv,noheader,nounits | ForEach-Object { $f = $_ -split ','; \"$($f[0].Trim()): $($f[1].Trim())W / $($f[2].Trim())W max\" }"),
    JarvisCommand("gpu_fan_speed", "systeme", "Vitesse des ventilateurs GPU", [
        "ventilateurs gpu", "fans gpu", "vitesse fan gpu",
        "les gpu ventilent combien",
    ], "powershell", "nvidia-smi --query-gpu=name,fan.speed --format=csv,noheader | Out-String"),
    JarvisCommand("gpu_driver_version", "systeme", "Version du driver NVIDIA", [
        "version driver nvidia", "driver gpu", "nvidia driver",
        "quel driver gpu",
    ], "powershell", "nvidia-smi --query-gpu=name,driver_version --format=csv,noheader | Out-String"),
    JarvisCommand("cluster_latence_detaillee", "systeme", "Latence detaillee de chaque noeud du cluster avec modeles", [
        "latence detaillee cluster", "ping detaille cluster",
        "benchmark rapide cluster", "vitesse des noeuds",
    ], "powershell", "$m2t = (Measure-Command{try{Invoke-WebRequest -Uri 'http://192.168.1.26:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 5 -UseBasicParsing}catch{}}).TotalMilliseconds; $m3t = (Measure-Command{try{Invoke-WebRequest -Uri 'http://192.168.1.113:1234/api/v1/models' -TimeoutSec 5 -UseBasicParsing}catch{}}).TotalMilliseconds; $ol1t = (Measure-Command{try{Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5 -UseBasicParsing}catch{}}).TotalMilliseconds; \"M2: $([math]::Round($m2t))ms | M3: $([math]::Round($m3t))ms | OL1: $([math]::Round($ol1t))ms\""),
]
