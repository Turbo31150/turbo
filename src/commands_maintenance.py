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

    # ══════════════════════════════════════════════════════════════════════
    # INVENTAIRE SYSTÈME (inspiré PDQ PowerShell one-liners)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("installed_apps_list", "systeme", "Lister les applications installees", [
        "liste les applications", "apps installees", "quelles apps j'ai",
        "programmes installes", "inventaire logiciels",
    ], "powershell", "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Where DisplayName | Select DisplayName, DisplayVersion, Publisher | Sort DisplayName | Out-String -Width 200"),
    JarvisCommand("hotfix_history", "systeme", "Historique des correctifs Windows installes", [
        "historique hotfix", "correctifs installes", "patches windows",
        "quels hotfix", "mises a jour installees",
    ], "powershell", "Get-HotFix | Sort InstalledOn -Descending | Select -First 15 HotFixID, Description, InstalledOn | Format-Table -AutoSize | Out-String"),
    JarvisCommand("scheduled_tasks_active", "systeme", "Taches planifiees actives", [
        "taches planifiees actives", "scheduled tasks", "quelles taches auto",
        "taches programmees", "cron windows",
    ], "powershell", "Get-ScheduledTask | Where State -eq 'Ready' | Where TaskPath -notmatch '^\\\\Microsoft' | Select TaskName, State, @{N='Next';E={($_ | Get-ScheduledTaskInfo).NextRunTime}} | Out-String"),
    JarvisCommand("tpm_info", "systeme", "Informations sur le module TPM", [
        "info tpm", "tpm status", "etat du tpm",
        "module tpm", "securite tpm",
    ], "powershell", "Get-Tpm | Select TpmPresent, TpmReady, TpmEnabled, ManufacturerVersion | Out-String"),
    JarvisCommand("printer_list", "systeme", "Imprimantes installees et leur statut", [
        "liste les imprimantes", "imprimantes installees", "quelles imprimantes",
        "printers", "etat des imprimantes",
    ], "powershell", "Get-Printer | Select Name, DriverName, PortName, PrinterStatus | Format-Table -AutoSize | Out-String"),
    JarvisCommand("startup_impact", "systeme", "Impact des programmes au demarrage sur le boot", [
        "impact demarrage", "startup impact", "quoi ralentit le boot",
        "programmes lents au demarrage", "performance boot",
    ], "powershell", "Get-CimInstance Win32_StartupCommand | Select Name, Command, Location | Out-String; '---'; Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -ErrorAction SilentlyContinue | Select * -ExcludeProperty PS* | Out-String"),
    JarvisCommand("system_info_detaille", "systeme", "Infos systeme detaillees (OS, BIOS, carte mere)", [
        "infos systeme detaillees", "system info", "details du pc",
        "specs du pc", "configuration materielle",
    ], "powershell", "$os = Get-CimInstance Win32_OperatingSystem; $bios = Get-CimInstance Win32_BIOS; $mb = Get-CimInstance Win32_BaseBoard; \"OS: $($os.Caption) Build $($os.BuildNumber)`nBIOS: $($bios.Manufacturer) $($bios.SMBIOSBIOSVersion)`nCarte mere: $($mb.Manufacturer) $($mb.Product)\""),
    JarvisCommand("ram_slots_detail", "systeme", "Details des barrettes RAM (type, vitesse, slots)", [
        "details ram", "barrettes ram", "ram slots",
        "type de ram", "vitesse ram",
    ], "powershell", "Get-CimInstance Win32_PhysicalMemory | Select BankLabel, @{N='Capacite(GB)';E={[math]::Round($_.Capacity/1GB)}}, Speed, Manufacturer | Format-Table -AutoSize | Out-String"),
    JarvisCommand("cpu_details", "systeme", "Details du processeur (coeurs, threads, frequence)", [
        "details cpu", "info processeur", "specs cpu",
        "coeurs cpu", "frequence processeur",
    ], "powershell", "$cpu = Get-CimInstance Win32_Processor; \"$($cpu.Name)`nCoeurs: $($cpu.NumberOfCores) | Threads: $($cpu.NumberOfLogicalProcessors)`nFrequence: $($cpu.MaxClockSpeed) MHz | Cache L3: $([math]::Round($cpu.L3CacheSize/1024)) MB\""),
    JarvisCommand("network_adapters_list", "systeme", "Adaptateurs reseau actifs et leur configuration", [
        "adaptateurs reseau", "interfaces reseau", "network adapters",
        "cartes reseau", "config reseau",
    ], "powershell", "Get-NetAdapter | Where Status -eq 'Up' | Select Name, InterfaceDescription, LinkSpeed, MacAddress | Format-Table -AutoSize | Out-String"),
    JarvisCommand("dns_cache_view", "systeme", "Voir le cache DNS local", [
        "cache dns", "dns cache", "voir le cache dns",
        "entrees dns", "dns local",
    ], "powershell", "Get-DnsClientCache | Select Entry, Type, Data | Select -First 20 | Format-Table -AutoSize | Out-String"),
    JarvisCommand("recycle_bin_size", "systeme", "Taille de la corbeille", [
        "taille corbeille", "poids corbeille", "combien dans la corbeille",
        "corbeille pleine", "espace corbeille",
    ], "powershell", "$shell = New-Object -ComObject Shell.Application; $rb = $shell.NameSpace(0x0a); $count = $rb.Items().Count; $size = ($rb.Items() | ForEach-Object { $rb.GetDetailsOf($_, 3) }); \"Corbeille: $count elements\""),
    JarvisCommand("temp_folder_size", "systeme", "Taille du dossier temporaire", [
        "taille du temp", "dossier temp", "poids du temp",
        "combien dans temp", "espace temporaire",
    ], "powershell", "$s = (Get-ChildItem $env:TEMP -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum; \"Dossier TEMP: $([math]::Round($s/1MB)) MB ($((Get-ChildItem $env:TEMP -Recurse -File -ErrorAction SilentlyContinue).Count) fichiers)\""),
    JarvisCommand("last_shutdown_time", "systeme", "Heure du dernier arret du PC", [
        "dernier arret", "quand le pc s'est eteint", "last shutdown",
        "dernier shutdown", "heure extinction",
    ], "powershell", "$e = Get-WinEvent -FilterHashtable @{LogName='System';ID=1074} -MaxEvents 1 -ErrorAction SilentlyContinue; if($e){\"Dernier arret: $($e.TimeCreated.ToString('dd/MM/yyyy HH:mm')) — $($e.Message.Split([char]10)[0])\"}else{'Pas de donnees'}"),
    JarvisCommand("bluescreen_history", "systeme", "Historique des ecrans bleus (BSOD)", [
        "ecrans bleus", "bsod", "bluescreen", "historique bsod",
        "crashs windows", "blue screen of death",
    ], "powershell", "$dumps = Get-ChildItem 'C:\\Windows\\Minidump' -ErrorAction SilentlyContinue; if($dumps){$dumps | Select Name, @{N='Date';E={$_.LastWriteTime.ToString('dd/MM/yyyy HH:mm')}}, @{N='Taille(KB)';E={[math]::Round($_.Length/1KB)}} | Out-String}else{'Aucun BSOD enregistre'}"),
    JarvisCommand("disk_smart_health", "systeme", "Etat de sante SMART des disques", [
        "sante disques", "smart disques", "disk health",
        "etat ssd", "disques en bonne sante",
    ], "powershell", "Get-PhysicalDisk | Select FriendlyName, MediaType, HealthStatus, OperationalStatus, @{N='Taille(GB)';E={[math]::Round($_.Size/1GB)}} | Format-Table -AutoSize | Out-String"),
    JarvisCommand("firewall_rules_count", "systeme", "Nombre de regles firewall par profil", [
        "regles firewall", "combien de regles pare-feu", "firewall count",
        "etat du pare-feu", "firewall stats",
    ], "powershell", "$profiles = Get-NetFirewallProfile | Select Name, Enabled; $inbound = (Get-NetFirewallRule -Direction Inbound -Enabled True -ErrorAction SilentlyContinue).Count; $outbound = (Get-NetFirewallRule -Direction Outbound -Enabled True -ErrorAction SilentlyContinue).Count; $profiles | Out-String; \"Regles actives — Entrant: $inbound | Sortant: $outbound\""),
    JarvisCommand("env_variables_key", "systeme", "Variables d'environnement cles (PATH, TEMP, etc.)", [
        "variables environnement", "env vars", "montre le path",
        "path systeme", "environnement windows",
    ], "powershell", "\"COMPUTERNAME: $env:COMPUTERNAME`nUSERNAME: $env:USERNAME`nTEMP: $env:TEMP`nHOME: $env:USERPROFILE\"; '---PATH---'; $env:PATH -split ';' | Where { $_ } | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # INTÉGRITÉ SYSTÈME (inspiré PowerShell sysadmin, wholesalebackup.com)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sfc_scan", "systeme", "Lancer un scan d'integrite systeme (sfc /scannow)", [
        "scan integrite", "sfc scannow", "verifie les fichiers systeme",
        "repare le systeme", "scan sfc",
    ], "powershell", "sfc /scannow 2>&1 | Select -Last 5 | Out-String", confirm=True),
    JarvisCommand("dism_health_check", "systeme", "Verifier la sante de l'image Windows (DISM)", [
        "dism health", "sante windows", "dism check",
        "verifie l'image windows", "dism scan",
    ], "powershell", "DISM /Online /Cleanup-Image /CheckHealth 2>&1 | Out-String"),
    JarvisCommand("system_restore_points", "systeme", "Lister les points de restauration systeme", [
        "points de restauration", "restore points", "sauvegardes systeme",
        "quels points de restauration",
    ], "powershell", "Get-ComputerRestorePoint -ErrorAction SilentlyContinue | Select -First 10 SequenceNumber, Description, CreationTime | Format-Table -AutoSize | Out-String"),
    JarvisCommand("usb_devices_list", "systeme", "Lister les peripheriques USB connectes", [
        "peripheriques usb", "usb connectes", "quels usb",
        "liste les usb", "usb devices",
    ], "powershell", "Get-PnpDevice -PresentOnly | Where InstanceId -like 'USB*' | Where Status -eq 'OK' | Select FriendlyName, Status | Format-Table -AutoSize | Out-String"),
    JarvisCommand("bluetooth_devices", "systeme", "Lister les peripheriques Bluetooth", [
        "peripheriques bluetooth", "bluetooth connectes", "quels bluetooth",
        "appareils bluetooth", "liste bluetooth",
    ], "powershell", "Get-PnpDevice | Where Class -eq 'Bluetooth' | Where Status -eq 'OK' | Select FriendlyName, Status | Format-Table -AutoSize | Out-String"),
    JarvisCommand("certificates_list", "systeme", "Certificats systeme installes (racine)", [
        "certificats installes", "certificates", "liste les certificats",
        "certificats racine", "certs systeme",
    ], "powershell", "Get-ChildItem Cert:\\LocalMachine\\Root | Select -First 15 Subject, NotAfter | Format-Table -AutoSize | Out-String"),
    JarvisCommand("page_file_info", "systeme", "Configuration du fichier de pagination (swap)", [
        "page file", "fichier de pagination", "swap windows",
        "memoire virtuelle", "taille du swap",
    ], "powershell", "Get-CimInstance Win32_PageFileUsage | Select Name, @{N='Alloue(MB)';E={$_.AllocatedBaseSize}}, @{N='Utilise(MB)';E={$_.CurrentUsage}} | Out-String"),
    JarvisCommand("windows_features", "systeme", "Fonctionnalites Windows activees", [
        "fonctionnalites windows", "features windows", "quelles features activees",
        "options windows", "composants windows",
    ], "powershell", "Get-WindowsOptionalFeature -Online | Where State -eq 'Enabled' | Select FeatureName | Select -First 20 | Out-String"),
    JarvisCommand("power_plan_active", "systeme", "Plan d'alimentation actif et ses details", [
        "plan alimentation", "power plan", "mode d'alimentation",
        "quel mode performance", "economie energie",
    ], "powershell", "$plan = powercfg /getactivescheme; $plan"),
    JarvisCommand("bios_version", "systeme", "Version du BIOS et date", [
        "version bios", "bios info", "quel bios",
        "info bios", "firmware bios",
    ], "powershell", "$b = Get-CimInstance Win32_BIOS; \"BIOS: $($b.Manufacturer) | Version: $($b.SMBIOSBIOSVersion) | Date: $($b.ReleaseDate.ToString('dd/MM/yyyy'))\""),
    JarvisCommand("windows_version_detail", "systeme", "Version detaillee de Windows (build, edition)", [
        "version windows", "quelle version windows", "build windows",
        "edition windows", "windows version",
    ], "powershell", "$os = Get-CimInstance Win32_OperatingSystem; \"$($os.Caption) | Build $($os.BuildNumber) | Version $($os.Version) | Arch $($os.OSArchitecture)\""),
    JarvisCommand("network_connections_count", "systeme", "Nombre de connexions reseau actives par etat", [
        "connexions reseau actives", "combien de connexions", "network connections",
        "etat des connexions", "connexions par etat",
    ], "powershell", "Get-NetTCPConnection | Group-Object State | Select Name, Count | Sort Count -Descending | Out-String"),
    JarvisCommand("drivers_probleme", "systeme", "Pilotes en erreur ou problematiques", [
        "pilotes en erreur", "drivers probleme", "drivers defaillants",
        "quels drivers bugent", "peripheriques en erreur",
    ], "powershell", "Get-PnpDevice | Where Status -ne 'OK' | Select FriendlyName, Status, Class | Format-Table -AutoSize | Out-String"),
    JarvisCommand("shared_folders", "systeme", "Dossiers partages sur ce PC", [
        "dossiers partages", "partages reseau", "shared folders",
        "quels dossiers sont partages", "partages windows",
    ], "powershell", "Get-SmbShare | Where Name -notmatch '\\$' | Select Name, Path, Description | Format-Table -AutoSize | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # PILOTAGE WINDOWS SANS SOURIS — Fenêtres, apps, audio, affichage
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("focus_app_name", "systeme", "Mettre le focus sur une application par son nom", [
        "va sur {app}", "bascule sur {app}", "focus {app}",
        "montre {app}", "met {app} au premier plan",
    ], "powershell", "$w = Get-Process -Name '*{app}*' -ErrorAction SilentlyContinue | Where MainWindowTitle | Select -First 1; if($w){(New-Object -ComObject WScript.Shell).AppActivate($w.Id); \"Focus: $($w.MainWindowTitle)\"}else{\"App '{app}' non trouvee\"}", ["app"]),
    JarvisCommand("fermer_app_name", "systeme", "Fermer une application par son nom", [
        "ferme {app}", "tue {app}", "arrete {app}",
        "quitte {app}", "kill {app}",
    ], "powershell", "Stop-Process -Name '*{app}*' -Force -ErrorAction SilentlyContinue; 'Processus {app} ferme'", ["app"], confirm=True),
    JarvisCommand("liste_fenetres_ouvertes", "systeme", "Lister toutes les fenetres ouvertes avec leur titre", [
        "quelles fenetres sont ouvertes", "liste les fenetres", "fenetres actives",
        "quoi est ouvert", "apps ouvertes",
    ], "powershell", "Get-Process | Where MainWindowTitle | Select Name, MainWindowTitle, @{N='RAM(MB)';E={[math]::Round($_.WS/1MB)}} | Format-Table -AutoSize | Out-String"),
    JarvisCommand("fenetre_toujours_visible", "systeme", "Rendre la fenetre active always-on-top", [
        "toujours visible", "always on top", "epingle la fenetre",
        "garde au premier plan", "fenetre au dessus",
    ], "powershell", "Add-Type @\"`nusing System;using System.Runtime.InteropServices;public class W{[DllImport(\"user32.dll\")]public static extern IntPtr GetForegroundWindow();[DllImport(\"user32.dll\")]public static extern bool SetWindowPos(IntPtr h,IntPtr a,int x,int y,int w,int h2,uint f);}`n\"@; [W]::SetWindowPos([W]::GetForegroundWindow(), [IntPtr](-1), 0, 0, 0, 0, 0x0003); 'Fenetre epinglee au premier plan'"),
    JarvisCommand("deplacer_fenetre_moniteur", "systeme", "Deplacer la fenetre active vers l'autre moniteur", [
        "fenetre autre ecran", "deplace sur l'autre ecran", "bouge la fenetre",
        "move to other monitor", "fenetre ecran suivant",
    ], "hotkey", "win+shift+right"),
    JarvisCommand("centrer_fenetre", "systeme", "Centrer la fenetre active sur l'ecran", [
        "centre la fenetre", "fenetre au centre", "center window",
        "recentre la fenetre",
    ], "powershell", "Add-Type @\"`nusing System;using System.Runtime.InteropServices;public class CW{[DllImport(\"user32.dll\")]public static extern IntPtr GetForegroundWindow();[DllImport(\"user32.dll\")]public static extern bool GetWindowRect(IntPtr h,out int[] r);[DllImport(\"user32.dll\")]public static extern bool MoveWindow(IntPtr h,int x,int y,int w,int h2,bool r);}`n\"@; $s = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea; $h = [CW]::GetForegroundWindow(); $w = 1200; $ht = 800; [CW]::MoveWindow($h, ($s.Width-$w)/2, ($s.Height-$ht)/2, $w, $ht, $true); 'Fenetre centree'"),
    JarvisCommand("switch_audio_output", "systeme", "Lister et changer la sortie audio", [
        "change la sortie audio", "switch audio", "quel sortie son",
        "casque ou haut parleur", "audio output",
    ], "powershell", "Get-AudioDevice -List -ErrorAction SilentlyContinue | Select Index, Name, Default | Out-String; if(-not $?){ 'Installez AudioDeviceCmdlets: Install-Module AudioDeviceCmdlets' }"),
    JarvisCommand("toggle_wifi", "systeme", "Activer/desactiver le WiFi", [
        "toggle wifi", "active le wifi", "desactive le wifi",
        "coupe le wifi", "allume le wifi",
    ], "powershell", "$a = Get-NetAdapter -Name '*Wi*' -ErrorAction SilentlyContinue | Select -First 1; if($a.Status -eq 'Up'){Disable-NetAdapter $a.Name -Confirm:$false; 'WiFi desactive'}else{Enable-NetAdapter $a.Name -Confirm:$false; 'WiFi active'}"),
    JarvisCommand("toggle_bluetooth", "systeme", "Activer/desactiver le Bluetooth", [
        "toggle bluetooth", "active le bluetooth", "desactive le bluetooth",
        "coupe le bluetooth", "allume le bluetooth",
    ], "powershell", "ms-settings:bluetooth"),
    JarvisCommand("toggle_dark_mode", "systeme", "Basculer entre mode sombre et mode clair", [
        "mode sombre", "dark mode", "toggle dark mode",
        "mode clair", "change le theme", "light mode",
    ], "powershell", "$k = 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize'; $v = (Get-ItemProperty $k).AppsUseLightTheme; if($v -eq 0){Set-ItemProperty $k AppsUseLightTheme 1; Set-ItemProperty $k SystemUsesLightTheme 1; 'Mode clair active'}else{Set-ItemProperty $k AppsUseLightTheme 0; Set-ItemProperty $k SystemUsesLightTheme 0; 'Mode sombre active'}"),
    JarvisCommand("taper_date", "systeme", "Taper la date du jour automatiquement", [
        "tape la date", "ecris la date", "insere la date",
        "date du jour", "quelle date",
    ], "powershell", "$d = Get-Date -Format 'dd/MM/yyyy'; Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait($d); \"Date inseree: $d\""),
    JarvisCommand("taper_heure", "systeme", "Taper l'heure actuelle automatiquement", [
        "tape l'heure", "ecris l'heure", "insere l'heure",
        "quelle heure est il", "heure actuelle",
    ], "powershell", "$h = Get-Date -Format 'HH:mm'; Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait($h); \"Heure inseree: $h\""),
    JarvisCommand("vider_clipboard", "systeme", "Vider le presse-papier", [
        "vide le presse papier", "clear clipboard", "efface le clipboard",
        "nettoie le presse papier",
    ], "powershell", "Set-Clipboard -Value ''; 'Presse-papier vide'"),
    JarvisCommand("dismiss_notifications", "systeme", "Fermer toutes les notifications Windows", [
        "ferme les notifications", "dismiss notifications", "efface les notifs",
        "vide les notifications", "supprime les notifications",
    ], "hotkey", "win+shift+a"),
    JarvisCommand("ouvrir_gestionnaire_peripheriques", "systeme", "Ouvrir le Gestionnaire de peripheriques", [
        "gestionnaire de peripheriques", "device manager", "ouvre le gestionnaire peripheriques",
        "peripheriques systeme",
    ], "powershell", "Start-Process devmgmt.msc"),
    JarvisCommand("ouvrir_gestionnaire_disques", "systeme", "Ouvrir la Gestion des disques", [
        "gestion des disques", "disk management", "ouvre la gestion des disques",
        "partitions disque",
    ], "powershell", "Start-Process diskmgmt.msc"),
    JarvisCommand("ouvrir_services_windows", "systeme", "Ouvrir la console Services Windows", [
        "services windows", "console services", "ouvre les services",
        "gerer les services",
    ], "powershell", "Start-Process services.msc"),
    JarvisCommand("ouvrir_registre", "systeme", "Ouvrir l'editeur de registre", [
        "editeur de registre", "regedit", "ouvre le registre",
        "registre windows",
    ], "powershell", "Start-Process regedit"),
    JarvisCommand("ouvrir_event_viewer", "systeme", "Ouvrir l'observateur d'evenements", [
        "observateur d'evenements", "event viewer", "ouvre les logs windows",
        "journaux systeme",
    ], "powershell", "Start-Process eventvwr.msc"),
    JarvisCommand("hibernation_profonde", "systeme", "Mettre le PC en hibernation profonde", [
        "hiberne le pc maintenant", "hibernation profonde", "mode hibernation profonde",
        "mets en hibernation le pc",
    ], "powershell", "shutdown /h", confirm=True),
    JarvisCommand("restart_bios", "systeme", "Redemarrer vers le BIOS/UEFI", [
        "redemarre dans le bios", "restart bios", "acces uefi",
        "bios au redemarrage",
    ], "powershell", "shutdown /r /fw /t 0", confirm=True),
    JarvisCommand("taskbar_app_1", "systeme", "Lancer la 1ere app epinglee dans la taskbar", [
        "premiere app taskbar", "app 1 taskbar", "lance l'app 1",
        "taskbar un",
    ], "hotkey", "win+1"),
    JarvisCommand("taskbar_app_2", "systeme", "Lancer la 2eme app epinglee dans la taskbar", [
        "deuxieme app taskbar", "app 2 taskbar", "lance l'app 2",
        "taskbar deux",
    ], "hotkey", "win+2"),
    JarvisCommand("taskbar_app_3", "systeme", "Lancer la 3eme app epinglee dans la taskbar", [
        "troisieme app taskbar", "app 3 taskbar", "lance l'app 3",
        "taskbar trois",
    ], "hotkey", "win+3"),
    JarvisCommand("taskbar_app_4", "systeme", "Lancer la 4eme app epinglee dans la taskbar", [
        "quatrieme app taskbar", "app 4 taskbar", "lance l'app 4",
        "taskbar quatre",
    ], "hotkey", "win+4"),
    JarvisCommand("taskbar_app_5", "systeme", "Lancer la 5eme app epinglee dans la taskbar", [
        "cinquieme app taskbar", "app 5 taskbar", "lance l'app 5",
        "taskbar cinq",
    ], "hotkey", "win+5"),
    JarvisCommand("fenetre_autre_bureau", "systeme", "Deplacer la fenetre vers le bureau virtuel suivant", [
        "fenetre bureau suivant", "deplace la fenetre sur l'autre bureau",
        "move to next desktop", "fenetre au bureau deux",
    ], "hotkey", "win+shift+right"),
    JarvisCommand("browser_retour", "systeme", "Page precedente dans le navigateur", [
        "page precedente", "retour arriere", "go back",
        "reviens en arriere", "page d'avant",
    ], "hotkey", "alt+left"),
    JarvisCommand("browser_avancer", "systeme", "Page suivante dans le navigateur", [
        "page suivante", "avance", "go forward",
        "page d'apres",
    ], "hotkey", "alt+right"),
    JarvisCommand("browser_rafraichir", "systeme", "Rafraichir la page web", [
        "rafraichis la page", "reload", "refresh",
        "recharge la page", "f5",
    ], "hotkey", "f5"),
    JarvisCommand("browser_hard_refresh", "systeme", "Rafraichir sans cache", [
        "hard refresh", "rafraichis sans cache", "ctrl f5",
        "force le rechargement",
    ], "hotkey", "ctrl+shift+r"),
    JarvisCommand("browser_private", "systeme", "Ouvrir une fenetre de navigation privee", [
        "navigation privee", "fenetre privee", "incognito",
        "mode prive", "private browsing",
    ], "hotkey", "ctrl+shift+n"),
    JarvisCommand("browser_bookmark", "systeme", "Ajouter la page aux favoris", [
        "ajoute aux favoris", "bookmark", "favori cette page",
        "met en favori",
    ], "hotkey", "ctrl+d"),
    JarvisCommand("browser_address_bar", "systeme", "Aller dans la barre d'adresse", [
        "barre d'adresse", "address bar", "tape une url",
        "va dans la barre d'adresse",
    ], "hotkey", "ctrl+l"),
    JarvisCommand("browser_fermer_tous_onglets", "systeme", "Fermer tous les onglets sauf l'actif", [
        "ferme tous les onglets", "close all tabs", "garde juste cet onglet",
        "nettoie les onglets",
    ], "powershell", "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('^w'); 'Onglet ferme'"),
    JarvisCommand("browser_epingler_onglet", "systeme", "Epingler/detacher l'onglet actif", [
        "epingle l'onglet", "pin tab", "detache l'onglet",
        "onglet epingle",
    ], "powershell", "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('+{F10}'); 'Menu contextuel ouvert — epinglez manuellement'"),
    JarvisCommand("texte_debut_ligne", "systeme", "Aller au debut de la ligne", [
        "debut de ligne", "home", "va au debut",
        "curseur au debut",
    ], "hotkey", "home"),
    JarvisCommand("texte_fin_ligne", "systeme", "Aller a la fin de la ligne", [
        "fin de ligne", "end", "va a la fin",
        "curseur a la fin",
    ], "hotkey", "end"),
    JarvisCommand("texte_debut_document", "systeme", "Aller au debut du document", [
        "debut du document", "tout en haut", "ctrl home",
        "va au debut du fichier",
    ], "hotkey", "ctrl+home"),
    JarvisCommand("texte_fin_document", "systeme", "Aller a la fin du document", [
        "fin du document", "tout en bas", "ctrl end",
        "va a la fin du fichier",
    ], "hotkey", "ctrl+end"),
    JarvisCommand("texte_selectionner_ligne", "systeme", "Selectionner la ligne entiere", [
        "selectionne la ligne", "select line", "prends toute la ligne",
    ], "hotkey", "home;;shift+end"),
    JarvisCommand("texte_supprimer_ligne", "systeme", "Supprimer la ligne entiere (VSCode)", [
        "supprime la ligne", "delete line", "efface la ligne",
        "enleve la ligne",
    ], "hotkey", "ctrl+shift+k"),
    JarvisCommand("texte_dupliquer_ligne", "systeme", "Dupliquer la ligne (VSCode)", [
        "duplique la ligne", "duplicate line", "copie la ligne en dessous",
    ], "hotkey", "shift+alt+down"),
    JarvisCommand("texte_deplacer_ligne_haut", "systeme", "Deplacer la ligne vers le haut (VSCode)", [
        "monte la ligne", "move line up", "ligne vers le haut",
    ], "hotkey", "alt+up"),
    JarvisCommand("texte_deplacer_ligne_bas", "systeme", "Deplacer la ligne vers le bas (VSCode)", [
        "descends la ligne", "move line down", "ligne vers le bas",
    ], "hotkey", "alt+down"),
    JarvisCommand("vscode_palette", "systeme", "Ouvrir la palette de commandes VSCode", [
        "palette de commandes", "command palette", "ctrl shift p",
        "commande vscode",
    ], "hotkey", "ctrl+shift+p"),
    JarvisCommand("vscode_terminal", "systeme", "Ouvrir/fermer le terminal VSCode", [
        "terminal vscode", "ouvre le terminal intergre", "toggle terminal",
        "affiche le terminal",
    ], "hotkey", "ctrl+`"),
    JarvisCommand("vscode_sidebar", "systeme", "Afficher/masquer la sidebar VSCode", [
        "sidebar vscode", "panneau lateral", "toggle sidebar",
        "cache la sidebar", "montre la sidebar",
    ], "hotkey", "ctrl+b"),
    JarvisCommand("vscode_go_to_file", "systeme", "Rechercher et ouvrir un fichier dans VSCode", [
        "ouvre un fichier vscode", "go to file", "ctrl p",
        "cherche un fichier dans vscode",
    ], "hotkey", "ctrl+p"),
    JarvisCommand("vscode_go_to_line", "systeme", "Aller a une ligne dans VSCode", [
        "va a la ligne", "go to line", "ctrl g",
        "saute a la ligne",
    ], "hotkey", "ctrl+g"),
    JarvisCommand("vscode_split_editor", "systeme", "Diviser l'editeur VSCode en deux", [
        "divise l'editeur", "split editor", "editeur cote a cote",
        "deux colonnes vscode",
    ], "hotkey", "ctrl+\\"),
    JarvisCommand("vscode_close_all", "systeme", "Fermer tous les fichiers ouverts dans VSCode", [
        "ferme tous les fichiers vscode", "close all tabs vscode",
        "nettoie vscode", "ferme tout dans vscode",
    ], "hotkey", "ctrl+k ctrl+w"),
    JarvisCommand("explorer_dossier_parent", "systeme", "Remonter au dossier parent dans l'Explorateur", [
        "dossier parent", "remonte d'un dossier", "go up folder",
        "dossier du dessus",
    ], "hotkey", "alt+up"),
    JarvisCommand("explorer_nouveau_dossier", "systeme", "Creer un nouveau dossier dans l'Explorateur", [
        "nouveau dossier", "cree un dossier", "new folder",
        "creer un repertoire",
    ], "hotkey", "ctrl+shift+n"),
    JarvisCommand("explorer_afficher_caches", "systeme", "Afficher les fichiers caches dans l'Explorateur", [
        "montre les fichiers caches", "fichiers caches", "show hidden files",
        "affiche les fichiers invisibles",
    ], "powershell", "Set-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced' Hidden 1; Stop-Process -Name explorer -Force; Start-Process explorer; 'Fichiers caches visibles'"),
    JarvisCommand("explorer_masquer_caches", "systeme", "Masquer les fichiers caches", [
        "cache les fichiers caches", "masque les fichiers invisibles", "hide hidden files",
        "desactive les fichiers caches",
    ], "powershell", "Set-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced' Hidden 2; Stop-Process -Name explorer -Force; Start-Process explorer; 'Fichiers caches masques'"),

    # ══════════════════════════════════════════════════════════════════════
    # SCROLL & NAVIGATION PAGE — Contrôle sans souris
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("scroll_haut", "systeme", "Scroller vers le haut", [
        "scroll up", "monte la page", "scrolle vers le haut",
        "remonte", "scroll haut",
    ], "hotkey", "up;;up;;up;;up;;up"),
    JarvisCommand("scroll_bas", "systeme", "Scroller vers le bas", [
        "scroll down", "descends la page", "scrolle vers le bas",
        "descends", "scroll bas",
    ], "hotkey", "down;;down;;down;;down;;down"),
    JarvisCommand("page_haut", "systeme", "Page precedente (Page Up)", [
        "page up", "page precedente", "monte d'une page",
        "remonte d'une page", "page vers le haut",
    ], "hotkey", "pageup"),
    JarvisCommand("page_bas", "systeme", "Page suivante (Page Down)", [
        "page down", "page suivante", "descends d'une page",
        "avance d'une page", "page vers le bas",
    ], "hotkey", "pagedown"),
    JarvisCommand("scroll_rapide_haut", "systeme", "Scroller rapidement vers le haut (5 pages)", [
        "scroll rapide haut", "monte vite", "remonte rapidement",
        "scroll fast up",
    ], "hotkey", "pageup;;pageup;;pageup;;pageup;;pageup"),
    JarvisCommand("scroll_rapide_bas", "systeme", "Scroller rapidement vers le bas (5 pages)", [
        "scroll rapide bas", "descends vite", "descends rapidement",
        "scroll fast down",
    ], "hotkey", "pagedown;;pagedown;;pagedown;;pagedown;;pagedown"),

    # ══════════════════════════════════════════════════════════════════════
    # WINDOW SNAPPING — Ancrage précis des fenêtres
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("snap_gauche", "systeme", "Ancrer la fenetre a gauche (moitie ecran)", [
        "fenetre a gauche", "snap left", "colle a gauche",
        "moitie gauche", "ancre a gauche",
    ], "hotkey", "win+left"),
    JarvisCommand("snap_droite", "systeme", "Ancrer la fenetre a droite (moitie ecran)", [
        "fenetre a droite", "snap right", "colle a droite",
        "moitie droite", "ancre a droite",
    ], "hotkey", "win+right"),
    JarvisCommand("snap_haut_gauche", "systeme", "Ancrer la fenetre en haut a gauche (quart ecran)", [
        "fenetre haut gauche", "snap top left", "quart haut gauche",
        "coin haut gauche",
    ], "hotkey", "win+left;;win+up"),
    JarvisCommand("snap_bas_gauche", "systeme", "Ancrer la fenetre en bas a gauche (quart ecran)", [
        "fenetre bas gauche", "snap bottom left", "quart bas gauche",
        "coin bas gauche",
    ], "hotkey", "win+left;;win+down"),
    JarvisCommand("snap_haut_droite", "systeme", "Ancrer la fenetre en haut a droite (quart ecran)", [
        "fenetre haut droite", "snap top right", "quart haut droite",
        "coin haut droite",
    ], "hotkey", "win+right;;win+up"),
    JarvisCommand("snap_bas_droite", "systeme", "Ancrer la fenetre en bas a droite (quart ecran)", [
        "fenetre bas droite", "snap bottom right", "quart bas droite",
        "coin bas droite",
    ], "hotkey", "win+right;;win+down"),
    JarvisCommand("restaurer_fenetre", "systeme", "Restaurer la fenetre a sa taille precedente", [
        "restaure la fenetre", "taille normale", "restore window",
        "fenetre normale", "desmaximise",
    ], "hotkey", "win+down"),

    # ══════════════════════════════════════════════════════════════════════
    # ONGLETS NAVIGATEUR — Gestion complète sans souris
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("onglet_1", "systeme", "Aller au 1er onglet", [
        "onglet 1", "premier onglet", "tab 1",
        "va au premier onglet",
    ], "hotkey", "ctrl+1"),
    JarvisCommand("onglet_2", "systeme", "Aller au 2eme onglet", [
        "onglet 2", "deuxieme onglet", "tab 2",
        "va au deuxieme onglet",
    ], "hotkey", "ctrl+2"),
    JarvisCommand("onglet_3", "systeme", "Aller au 3eme onglet", [
        "onglet 3", "troisieme onglet", "tab 3",
        "va au troisieme onglet",
    ], "hotkey", "ctrl+3"),
    JarvisCommand("onglet_4", "systeme", "Aller au 4eme onglet", [
        "onglet 4", "quatrieme onglet", "tab 4",
        "va au quatrieme onglet",
    ], "hotkey", "ctrl+4"),
    JarvisCommand("onglet_5", "systeme", "Aller au 5eme onglet", [
        "onglet 5", "cinquieme onglet", "tab 5",
        "va au cinquieme onglet",
    ], "hotkey", "ctrl+5"),
    JarvisCommand("onglet_dernier", "systeme", "Aller au dernier onglet", [
        "dernier onglet", "last tab", "va au dernier onglet",
        "onglet le plus a droite",
    ], "hotkey", "ctrl+9"),
    JarvisCommand("nouvel_onglet_vierge", "systeme", "Ouvrir un nouvel onglet vierge", [
        "nouvel onglet vierge", "new tab blank", "ouvre un onglet vide",
        "onglet vierge",
    ], "hotkey", "ctrl+t"),
    JarvisCommand("mute_onglet", "systeme", "Couper le son de l'onglet (clic droit requis)", [
        "mute l'onglet", "coupe le son de l'onglet", "silence onglet",
        "mute tab",
    ], "powershell", "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('m'); 'Tentative de mute — fonctionne si menu contextuel ouvert'"),
    JarvisCommand("browser_devtools", "systeme", "Ouvrir les DevTools du navigateur", [
        "ouvre les devtools", "developer tools", "ouvre la console",
        "f12", "outils developpeur",
    ], "hotkey", "f12"),
    JarvisCommand("browser_devtools_console", "systeme", "Ouvrir la console DevTools directement", [
        "ouvre la console navigateur", "console chrome", "console edge",
        "ctrl shift j", "javascript console",
    ], "hotkey", "ctrl+shift+j"),
    JarvisCommand("browser_source_view", "systeme", "Voir le code source de la page", [
        "voir le code source", "view source", "source de la page",
        "ctrl u", "code html de la page",
    ], "hotkey", "ctrl+u"),

    # ══════════════════════════════════════════════════════════════════════
    # TEXTE — Sélection, copier/coller, navigation par mot
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("curseur_mot_gauche", "systeme", "Deplacer le curseur d'un mot a gauche", [
        "mot precedent", "word left", "recule d'un mot",
        "curseur mot gauche",
    ], "hotkey", "ctrl+left"),
    JarvisCommand("curseur_mot_droite", "systeme", "Deplacer le curseur d'un mot a droite", [
        "mot suivant", "word right", "avance d'un mot",
        "curseur mot droite",
    ], "hotkey", "ctrl+right"),
    JarvisCommand("selectionner_mot", "systeme", "Selectionner le mot sous le curseur", [
        "selectionne le mot", "select word", "prends le mot",
        "mot selectionne",
    ], "hotkey", "ctrl+shift+left;;ctrl+shift+right"),
    JarvisCommand("selectionner_mot_gauche", "systeme", "Etendre la selection d'un mot a gauche", [
        "selection mot gauche", "select word left", "etends la selection a gauche",
        "ajoute le mot precedent",
    ], "hotkey", "ctrl+shift+left"),
    JarvisCommand("selectionner_mot_droite", "systeme", "Etendre la selection d'un mot a droite", [
        "selection mot droite", "select word right", "etends la selection a droite",
        "ajoute le mot suivant",
    ], "hotkey", "ctrl+shift+right"),
    JarvisCommand("selectionner_tout", "systeme", "Selectionner tout le contenu", [
        "selectionne tout", "select all", "tout selectionner",
        "ctrl a", "prends tout",
    ], "hotkey", "ctrl+a"),
    JarvisCommand("copier_texte", "systeme", "Copier la selection", [
        "copie", "copy", "copier", "ctrl c",
        "copie ca",
    ], "hotkey", "ctrl+c"),
    JarvisCommand("couper_texte", "systeme", "Couper la selection", [
        "coupe", "cut", "couper", "ctrl x",
        "coupe ca",
    ], "hotkey", "ctrl+x"),
    JarvisCommand("coller_texte", "systeme", "Coller le contenu du presse-papier", [
        "colle", "paste", "coller", "ctrl v",
        "colle ca",
    ], "hotkey", "ctrl+v"),
    JarvisCommand("annuler_action", "systeme", "Annuler la derniere action (undo)", [
        "annule", "undo", "ctrl z", "defais",
        "annule ca",
    ], "hotkey", "ctrl+z"),
    JarvisCommand("retablir_action", "systeme", "Retablir l'action annulee (redo)", [
        "retablis", "redo", "ctrl y", "refais",
        "retablis ca",
    ], "hotkey", "ctrl+y"),
    JarvisCommand("rechercher_dans_page", "systeme", "Ouvrir la recherche dans la page", [
        "cherche dans la page", "find", "ctrl f",
        "recherche dans la page", "trouve dans la page",
    ], "hotkey", "ctrl+f"),
    JarvisCommand("rechercher_et_remplacer", "systeme", "Ouvrir rechercher et remplacer", [
        "cherche et remplace", "find replace", "ctrl h",
        "remplacer dans la page",
    ], "hotkey", "ctrl+h"),
    JarvisCommand("supprimer_mot_gauche", "systeme", "Supprimer le mot precedent", [
        "supprime le mot precedent", "delete word left", "efface le mot avant",
        "ctrl backspace",
    ], "hotkey", "ctrl+backspace"),
    JarvisCommand("supprimer_mot_droite", "systeme", "Supprimer le mot suivant", [
        "supprime le mot suivant", "delete word right", "efface le mot apres",
        "ctrl delete",
    ], "hotkey", "ctrl+delete"),

    # ══════════════════════════════════════════════════════════════════════
    # MENU CONTEXTUEL & INTERACTIONS SOURIS ALTERNATIVES
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("menu_contextuel", "systeme", "Ouvrir le menu contextuel (clic droit)", [
        "clic droit", "menu contextuel", "right click",
        "ouvre le menu", "shift f10",
    ], "hotkey", "shift+f10"),
    JarvisCommand("valider_entree", "systeme", "Appuyer sur Entree (valider)", [
        "entree", "valide", "enter", "ok",
        "appuie sur entree", "confirme",
    ], "hotkey", "enter"),
    JarvisCommand("echapper", "systeme", "Appuyer sur Echap (annuler/fermer)", [
        "echap", "escape", "annule", "ferme le menu",
        "quitte le dialogue",
    ], "hotkey", "escape"),
    JarvisCommand("tabulation", "systeme", "Naviguer au champ suivant (Tab)", [
        "tab", "champ suivant", "element suivant",
        "tabulation", "passe au suivant",
    ], "hotkey", "tab"),
    JarvisCommand("tabulation_inverse", "systeme", "Naviguer au champ precedent (Shift+Tab)", [
        "shift tab", "champ precedent", "element precedent",
        "retour tab", "reviens au precedent",
    ], "hotkey", "shift+tab"),
    JarvisCommand("ouvrir_selection", "systeme", "Ouvrir/activer l'element selectionne (Espace)", [
        "espace", "active", "coche", "decoche",
        "appuie sur espace",
    ], "hotkey", "space"),

    # ══════════════════════════════════════════════════════════════════════
    # VOLUME & MÉDIA — Contrôle audio complet
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("media_suivant", "systeme", "Piste suivante", [
        "piste suivante", "next track", "chanson suivante",
        "musique suivante", "skip",
    ], "powershell", "(New-Object -ComObject WScript.Shell).SendKeys([char]176); 'Piste suivante'"),
    JarvisCommand("media_precedent", "systeme", "Piste precedente", [
        "piste precedente", "previous track", "chanson precedente",
        "musique precedente", "reviens en arriere musique",
    ], "powershell", "(New-Object -ComObject WScript.Shell).SendKeys([char]177); 'Piste precedente'"),

    # ══════════════════════════════════════════════════════════════════════
    # CAPTURE D'ÉCRAN & ENREGISTREMENT
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("screenshot_complet", "systeme", "Capture d'ecran complete (dans presse-papier)", [
        "screenshot", "capture d'ecran", "print screen",
        "fais un screenshot", "copie l'ecran",
    ], "hotkey", "win+shift+s"),
    JarvisCommand("screenshot_fenetre", "systeme", "Capture d'ecran de la fenetre active", [
        "screenshot fenetre", "capture la fenetre", "alt print screen",
        "screenshot de la fenetre",
    ], "hotkey", "alt+printscreen"),
    JarvisCommand("snip_screen", "systeme", "Outil de capture d'ecran (selection libre)", [
        "snip", "outil capture", "snipping tool",
        "decoupe l'ecran", "capture selective",
    ], "hotkey", "win+shift+s"),

    # ══════════════════════════════════════════════════════════════════════
    # BUREAUX VIRTUELS & TASK VIEW
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("task_view", "systeme", "Ouvrir la vue des taches (Task View)", [
        "task view", "vue des taches", "montre les fenetres",
        "toutes les fenetres", "win tab",
    ], "hotkey", "win+tab"),
    JarvisCommand("creer_bureau_virtuel", "systeme", "Creer un nouveau bureau virtuel", [
        "nouveau bureau virtuel", "cree un bureau", "new desktop",
        "ajoute un bureau virtuel",
    ], "hotkey", "win+ctrl+d"),
    JarvisCommand("fermer_bureau_virtuel", "systeme", "Fermer le bureau virtuel actuel", [
        "ferme le bureau virtuel", "supprime ce bureau", "close desktop",
        "enleve le bureau virtuel",
    ], "hotkey", "win+ctrl+f4"),

    # ══════════════════════════════════════════════════════════════════════
    # ZOOM — Contrôle du zoom dans les apps
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("zoom_in", "systeme", "Zoomer (agrandir)", [
        "zoom in", "zoome", "agrandis", "plus gros",
        "ctrl plus", "augmente le zoom",
    ], "hotkey", "ctrl+="),
    JarvisCommand("zoom_out", "systeme", "Dezoomer (reduire)", [
        "zoom out", "dezoome", "reduis", "plus petit",
        "ctrl moins", "diminue le zoom",
    ], "hotkey", "ctrl+-"),

    # ══════════════════════════════════════════════════════════════════════
    # SYSTÈME WINDOWS — Raccourcis fondamentaux
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("switch_app", "systeme", "Basculer entre les applications (Alt+Tab)", [
        "switch app", "alt tab", "change d'application",
        "bascule entre les apps", "app suivante",
    ], "hotkey", "alt+tab"),
    JarvisCommand("switch_app_inverse", "systeme", "Basculer en arriere entre les apps", [
        "app precedente alt tab", "reverse alt tab", "reviens a l'app precedente",
        "shift alt tab",
    ], "hotkey", "shift+alt+tab"),
    JarvisCommand("ouvrir_start_menu", "systeme", "Ouvrir le menu Demarrer", [
        "ouvre le menu demarrer", "start menu", "menu demarrer",
        "ouvre start", "touche windows",
    ], "hotkey", "win"),
    JarvisCommand("ouvrir_centre_notifications", "systeme", "Ouvrir le centre de notifications", [
        "ouvre les notifications", "centre de notifications", "notification center",
        "montre les notifs", "win n",
    ], "hotkey", "win+n"),
    JarvisCommand("ouvrir_clipboard_history", "systeme", "Ouvrir l'historique du presse-papier", [
        "historique presse papier", "clipboard history", "win v",
        "anciens copier coller", "historique clipboard",
    ], "hotkey", "win+v"),
    JarvisCommand("ouvrir_emojis_clavier", "systeme", "Ouvrir le panneau emojis", [
        "panneau emojis", "emoji keyboard", "win point",
        "insere un emoji", "ouvre les emojis clavier",
    ], "hotkey", "win+."),
    JarvisCommand("plein_ecran_toggle", "systeme", "Basculer en plein ecran (F11)", [
        "plein ecran", "fullscreen", "f11",
        "mode plein ecran", "toggle fullscreen",
    ], "hotkey", "f11"),
    JarvisCommand("renommer_fichier", "systeme", "Renommer le fichier/dossier selectionne (F2)", [
        "renomme", "rename", "f2",
        "renomme le fichier", "change le nom",
    ], "hotkey", "f2"),
    JarvisCommand("supprimer_selection", "systeme", "Supprimer la selection", [
        "supprime", "delete", "supprimer",
        "efface ca", "enleve ca",
    ], "hotkey", "delete"),
    JarvisCommand("ouvrir_proprietes", "systeme", "Voir les proprietes du fichier selectionne", [
        "proprietes", "properties", "alt enter",
        "voir les proprietes", "details du fichier",
    ], "hotkey", "alt+enter"),
    JarvisCommand("fermer_fenetre_active", "systeme", "Fermer la fenetre/app active (Alt+F4)", [
        "ferme la fenetre", "close window", "alt f4",
        "ferme l'application", "quitte l'app",
    ], "hotkey", "alt+f4"),
    JarvisCommand("ouvrir_parametres_systeme", "systeme", "Ouvrir les Parametres Windows", [
        "ouvre les parametres", "parametres windows", "settings",
        "ouvre les reglages", "win i",
    ], "hotkey", "win+i"),
    JarvisCommand("ouvrir_centre_accessibilite", "systeme", "Ouvrir les options d'accessibilite", [
        "accessibilite", "options accessibilite", "ease of access",
        "loupe windows", "narrateur",
    ], "hotkey", "win+u"),
    JarvisCommand("dictee_vocale_windows", "systeme", "Activer la dictee vocale Windows", [
        "dictee vocale", "voice typing", "win h",
        "dicte du texte", "tape a la voix",
    ], "hotkey", "win+h"),
    JarvisCommand("projection_ecran", "systeme", "Options de projection ecran (etendre, dupliquer)", [
        "projection ecran", "project screen", "win p",
        "dupliquer ecran", "etendre ecran",
    ], "hotkey", "win+p"),
    JarvisCommand("connecter_appareil", "systeme", "Ouvrir le panneau de connexion d'appareils (Cast)", [
        "connecter un appareil", "cast screen", "win k",
        "diffuser ecran", "partage ecran",
    ], "hotkey", "win+k"),
    JarvisCommand("ouvrir_game_bar_direct", "systeme", "Ouvrir la Xbox Game Bar", [
        "game bar directe", "xbox game bar", "win g direct",
        "ouvre la barre de jeu",
    ], "hotkey", "win+g"),

    # ══════════════════════════════════════════════════════════════════════
    # POWERTOYS — Intégration outils Microsoft PowerToys
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("powertoys_color_picker", "systeme", "Lancer le Color Picker PowerToys", [
        "color picker", "pipette couleur", "capture une couleur",
        "quel est ce code couleur", "selectionne une couleur",
    ], "hotkey", "win+shift+c"),
    JarvisCommand("powertoys_text_extractor", "systeme", "Extraire du texte de l'ecran (OCR PowerToys)", [
        "text extractor", "ocr ecran", "lis le texte a l'ecran",
        "extrais le texte", "copie le texte de l'image",
    ], "hotkey", "win+shift+t"),
    JarvisCommand("powertoys_screen_ruler", "systeme", "Mesurer des distances a l'ecran (Screen Ruler)", [
        "screen ruler", "regle ecran", "mesure l'ecran",
        "regle powertoys", "mesurer a l'ecran",
    ], "hotkey", "win+shift+m"),
    JarvisCommand("powertoys_always_on_top", "systeme", "Epingler la fenetre au premier plan (PowerToys)", [
        "pin powertoys", "epingle powertoys", "always on top powertoys",
        "garde la fenetre devant",
    ], "hotkey", "win+ctrl+t"),
    JarvisCommand("powertoys_paste_plain", "systeme", "Coller en texte brut (PowerToys)", [
        "colle en texte brut", "paste plain", "coller sans mise en forme",
        "ctrl win alt v", "paste as plain text",
    ], "hotkey", "ctrl+win+alt+v"),
    JarvisCommand("powertoys_fancyzones", "systeme", "Activer FancyZones layout editor", [
        "fancy zones", "editeur de zones", "layout fancyzones",
        "zones powertoys", "arrange les zones ecran",
    ], "hotkey", "win+shift+`"),
    JarvisCommand("powertoys_peek", "systeme", "Apercu rapide de fichier (PowerToys Peek)", [
        "peek fichier", "apercu rapide", "preview powertoys",
        "regarde le fichier rapidement",
    ], "hotkey", "ctrl+space"),
    JarvisCommand("powertoys_launcher", "systeme", "Ouvrir PowerToys Run (lanceur rapide)", [
        "powertoys run", "lanceur rapide", "quick launcher",
        "alt space", "lance powertoys run",
    ], "hotkey", "alt+space"),

    # ══════════════════════════════════════════════════════════════════════
    # OPÉRATIONS FICHIERS — Compression, manipulation, organisation
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("compresser_fichier", "fichiers", "Compresser un dossier en ZIP", [
        "compresse en zip", "zip le dossier", "cree un zip",
        "archive le dossier", "compress files",
    ], "powershell", "$d = (Get-ChildItem F:\\BUREAU -Directory | Sort LastWriteTime -Descending | Select -First 1).FullName; $zip = \"$d.zip\"; Compress-Archive -Path $d -DestinationPath $zip -Force; \"Compresse: $zip\""),
    JarvisCommand("decompresser_fichier", "fichiers", "Decompresser un fichier ZIP", [
        "decompresse le zip", "unzip", "extrais l'archive",
        "dezippe", "decompresser",
    ], "powershell", "$z = Get-ChildItem F:\\BUREAU\\*.zip -ErrorAction SilentlyContinue | Sort LastWriteTime -Descending | Select -First 1; if($z){Expand-Archive $z.FullName -DestinationPath ($z.FullName -replace '\\.zip$','') -Force; \"Extrait: $($z.Name)\"}else{'Aucun ZIP trouve'}"),
    JarvisCommand("compresser_turbo", "fichiers", "Compresser le projet turbo en ZIP (sans .git ni venv)", [
        "zip turbo", "archive turbo", "compresse le projet",
        "backup zip turbo",
    ], "powershell", "$dest = \"F:\\BUREAU\\turbo_$(Get-Date -Format 'yyyy-MM-dd_HHmm').zip\"; Get-ChildItem F:\\BUREAU\\turbo -Recurse -File | Where { $_.FullName -notmatch '\\.git\\\\|__pycache__|node_modules|\\.venv|dist' } | Compress-Archive -DestinationPath $dest -Force; \"Archive: $dest\""),
    JarvisCommand("vider_dossier_temp", "fichiers", "Supprimer les fichiers temporaires", [
        "vide le temp", "nettoie les temporaires", "clean temp",
        "supprime les fichiers temporaires",
    ], "powershell", "$count = (Get-ChildItem $env:TEMP -Recurse -File -ErrorAction SilentlyContinue).Count; Remove-Item \"$env:TEMP\\*\" -Recurse -Force -ErrorAction SilentlyContinue; \"$count fichiers temporaires supprimes\"", confirm=True),
    JarvisCommand("lister_fichiers_recents", "fichiers", "Lister les 20 fichiers les plus recents sur le bureau", [
        "fichiers recents", "derniers fichiers", "quoi de recent",
        "fichiers modifies recemment",
    ], "powershell", "Get-ChildItem F:\\BUREAU -Recurse -File -ErrorAction SilentlyContinue | Sort LastWriteTime -Descending | Select -First 20 @{N='Modifie';E={$_.LastWriteTime.ToString('dd/MM HH:mm')}}, @{N='Taille(KB)';E={[math]::Round($_.Length/1KB)}}, Name | Format-Table -AutoSize | Out-String"),
    JarvisCommand("chercher_gros_fichiers", "fichiers", "Trouver les fichiers > 100 MB sur F:", [
        "gros fichiers partout", "fichiers enormes", "quoi prend toute la place",
        "plus gros fichiers systeme",
    ], "powershell", "Get-ChildItem F:\\ -Recurse -File -ErrorAction SilentlyContinue | Where Length -gt 100MB | Sort Length -Descending | Select -First 15 @{N='Taille(MB)';E={[math]::Round($_.Length/1MB)}}, FullName | Format-Table -AutoSize | Out-String -Width 200"),
    JarvisCommand("doublons_bureau", "fichiers", "Detecter les doublons potentiels par nom dans F:\\BUREAU", [
        "doublons bureau", "fichiers en double", "trouve les doublons",
        "duplicate files", "doublons dans mes projets",
    ], "powershell", "Get-ChildItem F:\\BUREAU -Recurse -File -ErrorAction SilentlyContinue | Group-Object Name | Where Count -gt 1 | Select Name, Count | Sort Count -Descending | Select -First 20 | Format-Table -AutoSize | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # RÉSEAU AVANCÉ — Diagnostic, VPN, DNS
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("traceroute_google", "systeme", "Traceroute vers Google DNS", [
        "traceroute", "trace la route", "tracert google",
        "chemin reseau", "trace route",
    ], "powershell", "tracert -d -h 15 8.8.8.8 2>&1 | Out-String"),
    JarvisCommand("ping_google", "systeme", "Ping Google pour tester la connexion", [
        "ping google", "teste internet", "j'ai internet",
        "est ce que internet marche", "test connexion",
    ], "powershell", "ping 8.8.8.8 -n 4 | Out-String"),
    JarvisCommand("ping_cluster_complet", "systeme", "Ping tous les noeuds du cluster IA", [
        "ping tout le cluster", "tous les noeuds repondent",
        "test cluster complet", "ping m1 m2 m3",
    ], "powershell", "$results = @(); @('192.168.1.26','192.168.1.113','10.5.0.2','127.0.0.1') | ForEach-Object { $t = Test-Connection $_ -Count 1 -TimeoutSeconds 2 -ErrorAction SilentlyContinue; $results += \"$_`: $(if($t){\"$([math]::Round($t.Latency))ms\"}else{'TIMEOUT'})\" }; $results -join ' | '"),
    JarvisCommand("netstat_ecoute", "systeme", "Ports en ecoute avec processus associes", [
        "netstat listen", "ports en ecoute", "quels ports ecoutent",
        "qui ecoute sur quel port",
    ], "powershell", "Get-NetTCPConnection -State Listen | Select LocalPort, @{N='Process';E={(Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).Name}} | Sort LocalPort | Format-Table -AutoSize | Out-String"),
    JarvisCommand("flush_dns", "systeme", "Purger le cache DNS", [
        "flush dns", "purge dns", "vide le cache dns",
        "recharge le dns", "dns flush",
    ], "powershell", "ipconfig /flushdns 2>&1 | Out-String"),
    JarvisCommand("flush_arp", "systeme", "Purger la table ARP", [
        "flush arp", "vide la table arp", "purge arp",
        "nettoie arp",
    ], "powershell", "arp -d * 2>&1; 'Table ARP purgee'"),
    JarvisCommand("ip_config_complet", "systeme", "Configuration IP complete de toutes les interfaces", [
        "ipconfig all", "config ip complete", "toutes les ips",
        "detail reseau complet", "ip de tout",
    ], "powershell", "ipconfig /all | Out-String"),
    JarvisCommand("speed_test_rapide", "systeme", "Test de debit internet rapide (download)", [
        "speed test", "test de vitesse", "vitesse internet",
        "debit download", "teste ma connexion",
    ], "powershell", "$t = Measure-Command { Invoke-WebRequest 'https://speed.cloudflare.com/__down?bytes=10000000' -UseBasicParsing -OutFile $null -TimeoutSec 15 }; $mbps = [math]::Round(80/$t.TotalSeconds,1); \"Download: ~$mbps Mbps\""),
    JarvisCommand("vpn_status", "systeme", "Verifier l'etat des connexions VPN actives", [
        "etat vpn", "vpn status", "suis je en vpn",
        "vpn connecte", "quel vpn",
    ], "powershell", "$vpn = Get-VpnConnection -ErrorAction SilentlyContinue | Where ConnectionStatus -eq 'Connected'; if($vpn){\"VPN actif: $($vpn.Name) — $($vpn.ServerAddress)\"}else{'Aucun VPN connecte'}"),

    # ══════════════════════════════════════════════════════════════════════
    # TIMERS & PLANIFICATION — Minuteries, alarmes, shutdown programme
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("shutdown_timer_30", "systeme", "Programmer l'extinction dans 30 minutes", [
        "eteins dans 30 minutes", "shutdown dans 30 min", "timer extinction 30",
        "arrete le pc dans une demi heure",
    ], "powershell", "shutdown /s /t 1800; 'Extinction programmee dans 30 minutes'", confirm=True),
    JarvisCommand("shutdown_timer_60", "systeme", "Programmer l'extinction dans 1 heure", [
        "eteins dans une heure", "shutdown dans 1h", "timer extinction 1h",
        "arrete le pc dans une heure",
    ], "powershell", "shutdown /s /t 3600; 'Extinction programmee dans 1 heure'", confirm=True),
    JarvisCommand("shutdown_timer_120", "systeme", "Programmer l'extinction dans 2 heures", [
        "eteins dans deux heures", "shutdown dans 2h", "timer extinction 2h",
        "arrete le pc dans 2 heures",
    ], "powershell", "shutdown /s /t 7200; 'Extinction programmee dans 2 heures'", confirm=True),
    JarvisCommand("annuler_shutdown", "systeme", "Annuler l'extinction programmee", [
        "annule l'extinction", "cancel shutdown", "arrete le timer",
        "n'eteins plus", "abort shutdown",
    ], "powershell", "shutdown /a 2>&1; 'Extinction programmee annulee'"),
    JarvisCommand("restart_timer_30", "systeme", "Programmer un redemarrage dans 30 minutes", [
        "redemarre dans 30 minutes", "restart dans 30 min",
        "redemarrage programme 30",
    ], "powershell", "shutdown /r /t 1800; 'Redemarrage programme dans 30 minutes'", confirm=True),
    JarvisCommand("rappel_vocal", "systeme", "Creer un rappel vocal avec notification", [
        "rappelle moi dans {minutes} minutes", "timer {minutes} min",
        "alarme dans {minutes} minutes", "minuterie {minutes}",
    ], "powershell", "$t = {minutes}; Start-Job -ScriptBlock { param($m) Start-Sleep ($m*60); [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); [System.Windows.Forms.MessageBox]::Show(\"Rappel JARVIS: $m minutes ecoulees!\", 'JARVIS Timer') } -ArgumentList $t | Out-Null; \"Timer $t minutes lance en arriere-plan\"", ["minutes"]),

    # ══════════════════════════════════════════════════════════════════════
    # SÉCURITÉ ÉTENDUE — Audit, mots de passe, chiffrement
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("generer_mot_de_passe", "systeme", "Generer un mot de passe securise aleatoire", [
        "genere un mot de passe", "password random", "mot de passe aleatoire",
        "cree un password", "genere un password",
    ], "powershell", "$chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*'; $pwd = -join (1..20 | ForEach-Object { $chars[(Get-Random -Max $chars.Length)] }); Set-Clipboard $pwd; \"Mot de passe (20 chars) copie dans le presse-papier\""),
    JarvisCommand("audit_rdp", "systeme", "Verifier si le Bureau a distance est active", [
        "rdp actif", "bureau a distance", "remote desktop status",
        "check rdp", "est ce que rdp est active",
    ], "powershell", "$rdp = (Get-ItemProperty 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server').fDenyTSConnections; if($rdp -eq 0){'RDP ACTIVE — attention securite!'}else{'RDP desactive (ok)'}"),
    JarvisCommand("audit_admin_users", "systeme", "Lister les utilisateurs administrateurs", [
        "qui est admin", "utilisateurs administrateurs", "admin users",
        "comptes admin", "quels comptes ont les droits admin",
    ], "powershell", "Get-LocalGroupMember -Group Administrators -ErrorAction SilentlyContinue | Select Name, ObjectClass | Out-String"),
    JarvisCommand("sessions_actives", "systeme", "Lister les sessions utilisateur actives", [
        "sessions actives", "qui est connecte", "user sessions",
        "quelles sessions sont ouvertes",
    ], "powershell", "quser 2>$null | Out-String; if(-not $?){ query user 2>$null | Out-String }"),
    JarvisCommand("check_hash_fichier", "systeme", "Calculer le hash SHA256 d'un fichier", [
        "hash du fichier {path}", "sha256 {path}", "checksum {path}",
        "verifie l'integrite de {path}",
    ], "powershell", "(Get-FileHash '{path}' -Algorithm SHA256).Hash", ["path"]),
    JarvisCommand("audit_software_recent", "systeme", "Logiciels installes recemment (30 derniers jours)", [
        "logiciels recemment installes", "quoi de neuf installe",
        "installations recentes", "derniers logiciels",
    ], "powershell", "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Where InstallDate | Where { try { [datetime]::ParseExact($_.InstallDate,'yyyyMMdd',$null) -gt (Get-Date).AddDays(-30) } catch { $false } } | Select DisplayName, InstallDate | Sort InstallDate -Descending | Format-Table -AutoSize | Out-String"),
    JarvisCommand("firewall_toggle_profil", "systeme", "Activer/desactiver le pare-feu pour le profil actif", [
        "toggle firewall", "active le pare feu", "desactive le firewall",
        "firewall on off", "bascule le pare feu",
    ], "powershell", "$p = (Get-NetConnectionProfile).NetworkCategory; $f = (Get-NetFirewallProfile -Name $p).Enabled; if($f){Set-NetFirewallProfile -Name $p -Enabled False; \"Firewall $p DESACTIVE\"}else{Set-NetFirewallProfile -Name $p -Enabled True; \"Firewall $p ACTIVE\"}", confirm=True),

    # ══════════════════════════════════════════════════════════════════════
    # HARDWARE & AFFICHAGE — Luminosité, moniteurs, batterie
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("luminosite_haute", "systeme", "Monter la luminosite au maximum", [
        "luminosite max", "brightness max", "ecran au maximum",
        "monte la luminosite", "pleine luminosite",
    ], "powershell", "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods -ErrorAction SilentlyContinue).WmiSetBrightness(1,100); 'Luminosite: 100%'"),
    JarvisCommand("luminosite_basse", "systeme", "Baisser la luminosite au minimum", [
        "luminosite min", "brightness low", "ecran au minimum",
        "baisse la luminosite", "luminosite basse",
    ], "powershell", "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods -ErrorAction SilentlyContinue).WmiSetBrightness(1,20); 'Luminosite: 20%'"),
    JarvisCommand("luminosite_moyenne", "systeme", "Luminosite a 50%", [
        "luminosite moyenne", "brightness medium", "luminosite normale",
        "ecran a moitie", "luminosite 50",
    ], "powershell", "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods -ErrorAction SilentlyContinue).WmiSetBrightness(1,50); 'Luminosite: 50%'"),
    JarvisCommand("info_moniteurs", "systeme", "Informations sur les moniteurs connectes", [
        "info moniteurs", "quels ecrans", "resolution ecran",
        "moniteurs connectes", "screens info",
    ], "powershell", "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::AllScreens | ForEach-Object { \"$($_.DeviceName): $($_.Bounds.Width)x$($_.Bounds.Height) $(if($_.Primary){'(Principal)'}else{''})\" }"),
    JarvisCommand("batterie_info", "systeme", "Etat de la batterie (si laptop)", [
        "etat batterie", "battery status", "niveau batterie",
        "combien de batterie", "autonomie restante",
    ], "powershell", "$b = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue; if($b){\"Batterie: $($b.EstimatedChargeRemaining)% | Etat: $($b.Status) | Branchee: $(if($b.BatteryStatus -eq 2){'Oui'}else{'Non'})\"}else{'Pas de batterie detectee (PC fixe)'}"),
    JarvisCommand("power_events_recent", "systeme", "Historique veille/reveil des dernieres 24h", [
        "historique veille", "quand le pc s'est endormi", "power events",
        "veille et reveil recent",
    ], "powershell", "Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='Microsoft-Windows-Power-Troubleshooter','Microsoft-Windows-Kernel-Power'} -MaxEvents 10 -ErrorAction SilentlyContinue | Select TimeCreated, @{N='Event';E={$_.Message.Split([char]10)[0]}} | Out-String"),
    JarvisCommand("night_light_toggle", "systeme", "Basculer l'eclairage nocturne", [
        "lumiere de nuit", "night light", "eclairage nocturne",
        "mode nuit ecran", "filtre bleu",
    ], "powershell", "Start-Process ms-settings:nightlight; 'Parametres eclairage nocturne ouverts'"),

    # ══════════════════════════════════════════════════════════════════════
    # IMPRESSION — Gestion imprimante et PDF
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("imprimer_page", "systeme", "Imprimer la page/document actif", [
        "imprime", "print", "lance l'impression",
        "imprime la page", "ctrl p",
    ], "hotkey", "ctrl+p"),
    JarvisCommand("file_impression", "systeme", "Voir la file d'attente d'impression", [
        "file d'impression", "print queue", "quoi dans l'imprimante",
        "impressions en attente", "queue d'impression",
    ], "powershell", "Get-PrintJob -PrinterName (Get-Printer | Select -First 1 -ExpandProperty Name) -ErrorAction SilentlyContinue | Select DocumentName, JobStatus, Size | Out-String; if(-not $?){ 'Aucune imprimante ou file vide' }"),
    JarvisCommand("annuler_impressions", "systeme", "Annuler toutes les impressions en attente", [
        "annule les impressions", "cancel print", "arrete l'imprimante",
        "vide la file d'impression",
    ], "powershell", "Get-Printer | ForEach-Object { Get-PrintJob -PrinterName $_.Name -ErrorAction SilentlyContinue | Remove-PrintJob -ErrorAction SilentlyContinue }; 'File d'impression videe'"),
    JarvisCommand("imprimante_par_defaut", "systeme", "Voir l'imprimante par defaut", [
        "quelle imprimante par defaut", "default printer", "imprimante principale",
        "imprimante active",
    ], "powershell", "$p = Get-CimInstance Win32_Printer | Where Default -eq $true; if($p){\"Par defaut: $($p.Name) | Etat: $($p.PrinterStatus)\"}else{'Aucune imprimante par defaut'}"),

    # ══════════════════════════════════════════════════════════════════════
    # PROCESSUS AVANCÉ — Kill ciblé, priorité, affinité
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("kill_chrome", "systeme", "Forcer la fermeture de Chrome", [
        "tue chrome", "kill chrome", "force ferme chrome",
        "arrete chrome de force",
    ], "powershell", "Stop-Process -Name chrome -Force -ErrorAction SilentlyContinue; 'Chrome ferme'", confirm=True),
    JarvisCommand("kill_edge", "systeme", "Forcer la fermeture d'Edge", [
        "tue edge", "kill edge", "force ferme edge",
        "arrete edge de force",
    ], "powershell", "Stop-Process -Name msedge -Force -ErrorAction SilentlyContinue; 'Edge ferme'", confirm=True),
    JarvisCommand("kill_discord", "systeme", "Forcer la fermeture de Discord", [
        "tue discord", "kill discord", "ferme discord de force",
        "arrete discord",
    ], "powershell", "Stop-Process -Name discord -Force -ErrorAction SilentlyContinue; 'Discord ferme'", confirm=True),
    JarvisCommand("kill_spotify", "systeme", "Forcer la fermeture de Spotify", [
        "tue spotify", "kill spotify", "ferme spotify de force",
        "arrete spotify",
    ], "powershell", "Stop-Process -Name spotify -Force -ErrorAction SilentlyContinue; 'Spotify ferme'", confirm=True),
    JarvisCommand("kill_steam", "systeme", "Forcer la fermeture de Steam", [
        "tue steam", "kill steam", "ferme steam de force",
        "arrete steam",
    ], "powershell", "Stop-Process -Name steam -Force -ErrorAction SilentlyContinue; 'Steam ferme'", confirm=True),
    JarvisCommand("priorite_haute", "systeme", "Passer la fenetre active en priorite haute CPU", [
        "priorite haute", "high priority", "boost le processus",
        "accelere cette app",
    ], "powershell", "$fg = [System.Diagnostics.Process]::GetCurrentProcess(); Add-Type @\"`nusing System;using System.Runtime.InteropServices;public class FG{[DllImport(\"user32.dll\")]public static extern IntPtr GetForegroundWindow();[DllImport(\"user32.dll\")]public static extern uint GetWindowThreadProcessId(IntPtr h,out uint pid);}`n\"@; $pid = 0; [FG]::GetWindowThreadProcessId([FG]::GetForegroundWindow(),[ref]$pid); if($pid){(Get-Process -Id $pid).PriorityClass = 'High'; \"PID $pid passe en priorite haute\"}else{'Impossible'}"),
    JarvisCommand("processus_reseau", "systeme", "Processus utilisant le reseau actuellement", [
        "qui utilise le reseau", "processus reseau", "network processes",
        "quelles apps utilisent internet",
    ], "powershell", "Get-NetTCPConnection -State Established | Group-Object OwningProcess | ForEach-Object { $p = Get-Process -Id $_.Name -ErrorAction SilentlyContinue; [PSCustomObject]@{Process=$p.Name; PID=$_.Name; Connexions=$_.Count} } | Sort Connexions -Descending | Select -First 15 | Format-Table -AutoSize | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # WSL — Windows Subsystem for Linux
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("wsl_status", "systeme", "Voir les distributions WSL installees", [
        "distributions wsl", "wsl list", "quelles distros linux",
        "etat wsl", "linux installe",
    ], "powershell", "wsl --list --verbose 2>&1 | Out-String"),
    JarvisCommand("wsl_start", "systeme", "Demarrer WSL (distribution par defaut)", [
        "lance wsl", "demarre linux", "ouvre wsl",
        "start wsl", "lance ubuntu",
    ], "powershell", "Start-Process wsl"),
    JarvisCommand("wsl_disk_usage", "systeme", "Espace disque utilise par WSL", [
        "taille wsl", "espace wsl", "combien pese linux",
        "disque wsl",
    ], "powershell", "Get-ChildItem \"$env:LOCALAPPDATA\\Packages\\*Linux*\\LocalState\\ext4.vhdx\" -ErrorAction SilentlyContinue | Select @{N='Distro';E={($_.Directory.Parent.Name -split '_')[0]}}, @{N='Taille(GB)';E={[math]::Round($_.Length/1GB,2)}} | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # ACCESSIBILITÉ — Outils d'aide Windows
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("loupe_activer", "systeme", "Activer la loupe Windows", [
        "active la loupe", "zoom ecran", "magnifier on",
        "agrandis l'ecran", "loupe windows",
    ], "hotkey", "win+="),
    JarvisCommand("loupe_desactiver", "systeme", "Desactiver la loupe Windows", [
        "desactive la loupe", "arrete le zoom", "magnifier off",
        "ferme la loupe",
    ], "hotkey", "win+escape"),
    JarvisCommand("haut_contraste_toggle", "systeme", "Basculer en mode haut contraste", [
        "haut contraste", "high contrast", "mode contraste",
        "contraste eleve",
    ], "hotkey", "left_alt+left_shift+printscreen"),
    JarvisCommand("touches_remanentes", "systeme", "Activer/desactiver les touches remanentes", [
        "touches remanentes", "sticky keys", "touches collantes",
        "toggle sticky keys",
    ], "powershell", "Start-Process ms-settings:easeofaccess-keyboard; 'Parametres clavier accessibilite ouverts'"),
    JarvisCommand("taille_texte_plus", "systeme", "Augmenter la taille du texte systeme", [
        "texte plus grand", "agrandis le texte", "bigger text",
        "taille texte plus",
    ], "powershell", "Start-Process ms-settings:easeofaccess-display; 'Parametres taille texte ouverts'"),

    # ══════════════════════════════════════════════════════════════════════
    # SON & AUDIO AVANCÉ — Gestion sortie/entrée audio
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_melangeur_audio", "systeme", "Ouvrir le melangeur de volume", [
        "melangeur audio", "volume mixer", "mix audio",
        "son par application", "ouvre le melangeur",
    ], "powershell", "Start-Process sndvol.exe"),
    JarvisCommand("ouvrir_param_son", "systeme", "Ouvrir les parametres de son", [
        "parametres son", "reglages audio", "sound settings",
        "config audio", "sortie audio",
    ], "powershell", "Start-Process ms-settings:sound"),
    JarvisCommand("lister_audio_devices", "systeme", "Lister les peripheriques audio", [
        "peripheriques audio", "quelles sorties son", "audio devices",
        "liste les hauts parleurs", "microphones disponibles",
    ], "powershell", "Get-CimInstance Win32_SoundDevice | Select Name, Status | Format-Table -AutoSize | Out-String"),
    JarvisCommand("volume_50", "systeme", "Mettre le volume a 50%", [
        "volume a 50", "moitie volume", "volume moyen",
        "baisse le volume a 50",
    ], "powershell", "$w = New-Object -ComObject WScript.Shell; 1..50 | ForEach-Object { $w.SendKeys([char]174) }; 1..25 | ForEach-Object { $w.SendKeys([char]175) }; 'Volume ~50%'"),
    JarvisCommand("volume_25", "systeme", "Mettre le volume a 25%", [
        "volume a 25", "volume bas", "volume faible",
        "baisse le volume",
    ], "powershell", "$w = New-Object -ComObject WScript.Shell; 1..50 | ForEach-Object { $w.SendKeys([char]174) }; 1..12 | ForEach-Object { $w.SendKeys([char]175) }; 'Volume ~25%'"),
    JarvisCommand("volume_max", "systeme", "Mettre le volume au maximum", [
        "volume a fond", "volume maximum", "volume 100",
        "monte le son a fond",
    ], "powershell", "$w = New-Object -ComObject WScript.Shell; 1..50 | ForEach-Object { $w.SendKeys([char]175) }; 'Volume maximum'"),

    # ══════════════════════════════════════════════════════════════════════
    # STORAGE SENSE & NETTOYAGE INTELLIGENT
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("storage_sense_on", "systeme", "Activer Storage Sense (nettoyage auto)", [
        "active storage sense", "nettoyage automatique", "auto clean",
        "storage sense on",
    ], "powershell", "Start-Process ms-settings:storagepolicies; 'Parametres Storage Sense ouverts'"),
    JarvisCommand("disk_cleanup", "systeme", "Lancer le nettoyage de disque Windows (cleanmgr)", [
        "nettoyage de disque", "disk cleanup", "cleanmgr",
        "nettoie le disque windows",
    ], "powershell", "Start-Process cleanmgr -ArgumentList '/d C' -Wait; 'Nettoyage de disque lance'"),
    JarvisCommand("defrag_status", "systeme", "Voir l'etat de fragmentation des disques", [
        "etat defragmentation", "defrag status", "disques fragmentes",
        "optimisation disques",
    ], "powershell", "Get-PhysicalDisk | ForEach-Object { $vol = Get-Volume | Where DriveLetter; $vol | Select DriveLetter, FileSystemType, @{N='Taille(GB)';E={[math]::Round($_.Size/1GB)}}, HealthStatus } | Out-String"),
    JarvisCommand("optimiser_disques", "systeme", "Optimiser/defragmenter les disques", [
        "optimise les disques", "defragmente", "defrag",
        "optimize drives",
    ], "powershell", "Start-Process dfrgui; 'Outil d optimisation des disques ouvert'"),

    # ══════════════════════════════════════════════════════════════════════
    # FOCUS ASSIST & NOTIFICATIONS — Modes concentration
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("focus_assist_alarms", "systeme", "Focus Assist mode alarmes seulement", [
        "alarmes seulement", "focus alarms only", "juste les alarmes",
        "notifications prioritaires",
    ], "powershell", "Start-Process ms-settings:quietmomentshome; 'Regles automatiques Focus Assist ouvertes'"),

    # ══════════════════════════════════════════════════════════════════════
    # GESTION STARTUP — Apps au démarrage
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("startup_apps_list", "systeme", "Lister les apps qui demarrent au boot", [
        "apps au demarrage", "startup apps", "quoi se lance au boot",
        "programmes au demarrage",
    ], "powershell", "Get-CimInstance Win32_StartupCommand | Select Name, Command | Format-Table -AutoSize | Out-String; '---Registre---'; Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -ErrorAction SilentlyContinue | Select * -ExcludeProperty PS* | Format-List | Out-String"),
    JarvisCommand("startup_settings", "systeme", "Ouvrir les parametres des apps au demarrage", [
        "parametres demarrage", "startup settings", "gerer le demarrage",
        "config startup",
    ], "powershell", "Start-Process ms-settings:startupapps"),

    # ══════════════════════════════════════════════════════════════════════
    # CREDENTIAL MANAGER — Mots de passe enregistrés
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("credential_list", "systeme", "Lister les identifiants Windows enregistres", [
        "liste les identifiants", "quels mots de passe", "credentials saved",
        "identifiants sauvegardes",
    ], "powershell", "cmdkey /list 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # HOSTS FILE & DNS AVANCÉ
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("dns_serveurs", "systeme", "Voir les serveurs DNS configures", [
        "quels serveurs dns", "dns configures", "dns servers",
        "resolver dns", "dns actifs",
    ], "powershell", "Get-DnsClientServerAddress | Where ServerAddresses | Select InterfaceAlias, @{N='DNS';E={$_.ServerAddresses -join ', '}} | Format-Table -AutoSize | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # DATE, HEURE & TIMEZONE
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sync_horloge", "systeme", "Synchroniser l'horloge avec le serveur NTP", [
        "synchronise l'horloge", "sync ntp", "mets l'heure a jour",
        "time sync", "horloge precise",
    ], "powershell", "w32tm /resync /force 2>&1 | Out-String"),
    JarvisCommand("timezone_info", "systeme", "Voir le fuseau horaire actuel", [
        "quel fuseau horaire", "timezone", "heure locale",
        "zone horaire", "utc offset",
    ], "powershell", "$tz = Get-TimeZone; \"$($tz.DisplayName) | UTC$($tz.BaseUtcOffset.Hours):$($tz.BaseUtcOffset.Minutes.ToString('00')) | Heure: $(Get-Date -Format 'HH:mm:ss')\""),
    JarvisCommand("calendrier_mois", "systeme", "Afficher le calendrier du mois en cours", [
        "calendrier", "montre le calendrier", "quel jour on est",
        "calendrier du mois",
    ], "powershell", "$d = Get-Date; $first = Get-Date -Day 1; $last = $first.AddMonths(1).AddDays(-1); \"$($d.ToString('MMMM yyyy'))`n`nLun Mar Mer Jeu Ven Sam Dim\"; 1..$last.Day | ForEach-Object { $day = Get-Date -Day $_; if($_ -eq $d.Day){\"[$_]\"}else{\"$_\"} } | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # REMOTE DESKTOP & SSH
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvrir_rdp", "systeme", "Ouvrir le client Remote Desktop", [
        "ouvre remote desktop", "lance rdp", "bureau a distance client",
        "connexion distante", "remote desktop",
    ], "powershell", "Start-Process mstsc"),
    JarvisCommand("rdp_connect", "systeme", "Connexion Remote Desktop a une machine", [
        "connecte en rdp a {host}", "remote desktop {host}",
        "bureau a distance sur {host}", "rdp {host}",
    ], "powershell", "Start-Process mstsc -ArgumentList '/v:{host}'", ["host"]),
    JarvisCommand("ssh_connect", "systeme", "Connexion SSH a un serveur", [
        "connecte en ssh a {host}", "ssh {host}", "terminal distant {host}",
        "connexion ssh {host}",
    ], "powershell", "Start-Process ssh -ArgumentList '{host}' -NoNewWindow", ["host"]),

    # ══════════════════════════════════════════════════════════════════════
    # LANGUE & CLAVIER — Changement de disposition
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("changer_clavier", "systeme", "Changer la disposition clavier (FR/EN)", [
        "change le clavier", "switch keyboard", "clavier francais",
        "clavier anglais", "change la langue",
    ], "hotkey", "win+space"),
    JarvisCommand("clavier_suivant", "systeme", "Passer a la disposition clavier suivante", [
        "clavier suivant", "next keyboard", "alt shift",
        "bascule clavier",
    ], "hotkey", "alt+shift"),

    # ══════════════════════════════════════════════════════════════════════
    # TASKBAR & BUREAU — Personnalisation
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("taskbar_cacher", "systeme", "Cacher la barre des taches automatiquement", [
        "cache la taskbar", "hide taskbar", "barre des taches invisible",
        "masque la barre des taches",
    ], "powershell", "Start-Process ms-settings:taskbar; 'Parametres barre des taches ouverts'"),
    JarvisCommand("wallpaper_info", "systeme", "Voir le fond d'ecran actuel", [
        "quel fond d'ecran", "wallpaper actuel", "image de fond",
        "fond d ecran",
    ], "powershell", "(Get-ItemProperty 'HKCU:\\Control Panel\\Desktop' TranscodedImageCache -ErrorAction SilentlyContinue | Out-Null); $p = (Get-ItemProperty 'HKCU:\\Control Panel\\Desktop').WallPaper; \"Fond d'ecran: $p\""),
    JarvisCommand("icones_bureau_toggle", "systeme", "Afficher/masquer les icones du bureau", [
        "cache les icones", "montre les icones", "icones bureau",
        "toggle desktop icons", "bureau vide",
    ], "powershell", "$r = 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced'; $v = (Get-ItemProperty $r).HideIcons; Set-ItemProperty $r HideIcons $(1-$v); Stop-Process -Name explorer -Force; Start-Process explorer; if($v){'Icones affichees'}else{'Icones masquees'}"),

    # ══════════════════════════════════════════════════════════════════════
    # HYPER-V & SANDBOX — Virtualisation
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sandbox_launch", "systeme", "Lancer Windows Sandbox", [
        "lance la sandbox", "windows sandbox", "ouvre la sandbox",
        "environnement isole",
    ], "powershell", "Start-Process WindowsSandbox; 'Windows Sandbox lance'"),
    JarvisCommand("hyperv_list_vms", "systeme", "Lister les machines virtuelles Hyper-V", [
        "liste les vms", "virtual machines", "hyper v vms",
        "quelles vms", "machines virtuelles",
    ], "powershell", "Get-VM -ErrorAction SilentlyContinue | Select Name, State, @{N='RAM(GB)';E={[math]::Round($_.MemoryAssigned/1GB,1)}}, Uptime | Format-Table -AutoSize | Out-String; if(-not $?){ 'Hyper-V non disponible' }"),
    JarvisCommand("hyperv_start_vm", "systeme", "Demarrer une VM Hyper-V", [
        "demarre la vm {vm}", "start vm {vm}", "lance la machine {vm}",
        "allume la vm {vm}",
    ], "powershell", "Start-VM -Name '{vm}' -ErrorAction SilentlyContinue; 'VM {vm} demarree'", ["vm"]),
    JarvisCommand("hyperv_stop_vm", "systeme", "Arreter une VM Hyper-V", [
        "arrete la vm {vm}", "stop vm {vm}", "eteins la machine {vm}",
        "shutdown vm {vm}",
    ], "powershell", "Stop-VM -Name '{vm}' -ErrorAction SilentlyContinue; 'VM {vm} arretee'", ["vm"]),

    # ══════════════════════════════════════════════════════════════════════
    # GESTION DES SERVICES — Start/Stop/Restart
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("service_start", "systeme", "Demarrer un service Windows", [
        "demarre le service {svc}", "start service {svc}",
        "lance le service {svc}",
    ], "powershell", "Start-Service '{svc}' -ErrorAction SilentlyContinue; Get-Service '{svc}' | Select Name, Status | Out-String", ["svc"]),
    JarvisCommand("service_stop", "systeme", "Arreter un service Windows", [
        "arrete le service {svc}", "stop service {svc}",
        "coupe le service {svc}",
    ], "powershell", "Stop-Service '{svc}' -Force -ErrorAction SilentlyContinue; Get-Service '{svc}' | Select Name, Status | Out-String", ["svc"], confirm=True),
    JarvisCommand("service_restart", "systeme", "Redemarrer un service Windows", [
        "redemarre le service {svc}", "restart service {svc}",
        "relance le service {svc}",
    ], "powershell", "Restart-Service '{svc}' -Force -ErrorAction SilentlyContinue; Get-Service '{svc}' | Select Name, Status | Out-String", ["svc"]),
    JarvisCommand("service_status", "systeme", "Voir l'etat d'un service Windows", [
        "etat du service {svc}", "status service {svc}",
        "le service {svc} tourne",
    ], "powershell", "Get-Service '{svc}' -ErrorAction SilentlyContinue | Select Name, Status, StartType | Out-String", ["svc"]),

    # ══════════════════════════════════════════════════════════════════════
    # GESTION DISQUES AVANCÉE — Partitions, lettre, format
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("partitions_list", "systeme", "Lister toutes les partitions", [
        "liste les partitions", "partitions disque", "volumes montes",
        "quelles partitions",
    ], "powershell", "Get-Volume | Where DriveLetter | Select DriveLetter, FileSystemLabel, FileSystem, @{N='Taille(GB)';E={[math]::Round($_.Size/1GB,1)}}, @{N='Libre(GB)';E={[math]::Round($_.SizeRemaining/1GB,1)}}, HealthStatus | Format-Table -AutoSize | Out-String"),
    JarvisCommand("disques_physiques", "systeme", "Voir les disques physiques installes", [
        "disques physiques", "quels disques", "ssd hdd",
        "physical disks", "stockage installe",
    ], "powershell", "Get-PhysicalDisk | Select FriendlyName, MediaType, BusType, @{N='Taille(GB)';E={[math]::Round($_.Size/1GB)}}, HealthStatus | Format-Table -AutoSize | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # CLIPBOARD AVANCÉ — Opérations presse-papier
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("clipboard_contenu", "systeme", "Voir le contenu actuel du presse-papier", [
        "quoi dans le presse papier", "clipboard content", "montre le clipboard",
        "qu'est ce que j'ai copie",
    ], "powershell", "$c = Get-Clipboard -ErrorAction SilentlyContinue; if($c){\"Clipboard ($($c.Length) chars): $($c.Substring(0, [math]::Min($c.Length, 200)))$(if($c.Length -gt 200){'...'})\" }else{'Presse-papier vide'}"),
    JarvisCommand("clipboard_en_majuscules", "systeme", "Convertir le texte du clipboard en majuscules", [
        "clipboard en majuscules", "texte en majuscules", "uppercase clipboard",
        "convertis en majuscules",
    ], "powershell", "$c = Get-Clipboard; if($c){$u = $c.ToUpper(); Set-Clipboard $u; \"Converti en majuscules ($($u.Length) chars)\"}else{'Rien dans le clipboard'}"),
    JarvisCommand("clipboard_en_minuscules", "systeme", "Convertir le texte du clipboard en minuscules", [
        "clipboard en minuscules", "texte en minuscules", "lowercase clipboard",
        "convertis en minuscules",
    ], "powershell", "$c = Get-Clipboard; if($c){$l = $c.ToLower(); Set-Clipboard $l; \"Converti en minuscules ($($l.Length) chars)\"}else{'Rien dans le clipboard'}"),
    JarvisCommand("clipboard_compter_mots", "systeme", "Compter les mots dans le presse-papier", [
        "combien de mots copies", "word count clipboard", "compte les mots",
        "mots dans le clipboard",
    ], "powershell", "$c = Get-Clipboard; if($c){$w = ($c -split '\\s+').Count; $ch = $c.Length; $l = ($c -split '`n').Count; \"$w mots | $ch caracteres | $l lignes\"}else{'Presse-papier vide'}"),
    JarvisCommand("clipboard_trim", "systeme", "Nettoyer les espaces du texte clipboard", [
        "nettoie le clipboard", "trim clipboard", "enleve les espaces",
        "clean le presse papier",
    ], "powershell", "$c = Get-Clipboard; if($c){$t = ($c -split '`n' | ForEach-Object { $_.Trim() }) -join \"`n\"; Set-Clipboard $t; \"Clipboard nettoye ($($t.Length) chars)\"}else{'Vide'}"),

    # ══════════════════════════════════════════════════════════════════════
    # PARAMÈTRES WINDOWS — Accès direct aux pages Settings
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("param_camera", "systeme", "Parametres de confidentialite camera", [
        "parametres camera", "privacy camera", "autoriser la camera",
        "acces camera",
    ], "powershell", "Start-Process ms-settings:privacy-webcam"),
    JarvisCommand("param_microphone", "systeme", "Parametres de confidentialite microphone", [
        "parametres microphone", "privacy micro", "autoriser le micro",
        "acces microphone",
    ], "powershell", "Start-Process ms-settings:privacy-microphone"),
    JarvisCommand("param_localisation", "systeme", "Parametres de localisation/GPS", [
        "parametres localisation", "privacy location", "active le gps",
        "desactive la localisation", "position gps",
    ], "powershell", "Start-Process ms-settings:privacy-location"),
    JarvisCommand("param_gaming", "systeme", "Parametres de jeu Windows", [
        "parametres gaming", "game settings", "mode jeu settings",
        "xbox settings", "reglages jeu",
    ], "powershell", "Start-Process ms-settings:gaming-gamebar"),
    JarvisCommand("param_comptes", "systeme", "Parametres des comptes utilisateur", [
        "parametres comptes", "account settings", "gerer les comptes",
        "mon compte windows",
    ], "powershell", "Start-Process ms-settings:accounts"),
    JarvisCommand("param_connexion", "systeme", "Parametres de connexion (PIN, mot de passe)", [
        "options de connexion", "sign in options", "changer le pin",
        "windows hello", "mot de passe windows",
    ], "powershell", "Start-Process ms-settings:signinoptions"),
    JarvisCommand("param_apps_defaut", "systeme", "Parametres des apps par defaut", [
        "apps par defaut", "default apps", "navigateur par defaut",
        "lecteur pdf par defaut",
    ], "powershell", "Start-Process ms-settings:defaultapps"),
    JarvisCommand("param_fonctionnalites_optionnelles", "systeme", "Fonctionnalites optionnelles Windows", [
        "fonctionnalites optionnelles", "optional features", "ajouter une fonctionnalite",
        "features windows optionnelles",
    ], "powershell", "Start-Process ms-settings:optionalfeatures"),
    JarvisCommand("param_souris", "systeme", "Parametres de la souris", [
        "parametres souris", "mouse settings", "vitesse souris",
        "sensibilite souris",
    ], "powershell", "Start-Process ms-settings:mousetouchpad"),
    JarvisCommand("param_clavier", "systeme", "Parametres du clavier", [
        "parametres clavier", "keyboard settings", "vitesse clavier",
        "repetition clavier",
    ], "powershell", "Start-Process ms-settings:keyboard"),
    JarvisCommand("param_phone_link", "systeme", "Ouvrir Phone Link (connexion telephone)", [
        "phone link", "lien telephone", "connecter mon telephone",
        "votre telephone",
    ], "powershell", "Start-Process ms-settings:mobile-devices"),
    JarvisCommand("param_notifications_apps", "systeme", "Parametres notifications par application", [
        "notifications par app", "gerer les notifications", "notifs par app",
        "quelles apps notifient",
    ], "powershell", "Start-Process ms-settings:notifications"),
    JarvisCommand("param_multitache", "systeme", "Parametres multitache (snap, bureaux virtuels)", [
        "parametres multitache", "multitasking settings", "snap settings",
        "reglages snap",
    ], "powershell", "Start-Process ms-settings:multitasking"),
    JarvisCommand("param_stockage", "systeme", "Parametres de stockage (espace disque)", [
        "parametres stockage", "storage settings", "gestion stockage",
        "espace utilise",
    ], "powershell", "Start-Process ms-settings:storagesense"),
    JarvisCommand("param_proxy", "systeme", "Parametres de proxy reseau", [
        "parametres proxy", "proxy settings", "configurer le proxy",
        "proxy windows",
    ], "powershell", "Start-Process ms-settings:network-proxy"),
    JarvisCommand("param_vpn_settings", "systeme", "Parametres VPN Windows", [
        "parametres vpn", "vpn settings", "configurer le vpn",
        "ajouter un vpn",
    ], "powershell", "Start-Process ms-settings:network-vpn"),
    JarvisCommand("param_wifi_settings", "systeme", "Parametres WiFi avances", [
        "parametres wifi", "wifi settings", "reseaux connus",
        "gerer le wifi",
    ], "powershell", "Start-Process ms-settings:network-wifi"),
    JarvisCommand("param_update_avance", "systeme", "Parametres Windows Update avances", [
        "update avance", "windows update settings", "options de mise a jour",
        "maj avancees",
    ], "powershell", "Start-Process ms-settings:windowsupdate-options"),
    JarvisCommand("param_recovery", "systeme", "Options de recuperation systeme", [
        "recovery options", "reinitialiser le pc", "restauration systeme",
        "reset windows",
    ], "powershell", "Start-Process ms-settings:recovery"),
    JarvisCommand("param_developeurs", "systeme", "Parametres developpeur Windows", [
        "mode developpeur", "developer settings", "active le mode dev",
        "parametres dev windows",
    ], "powershell", "Start-Process ms-settings:developers"),

    # ══════════════════════════════════════════════════════════════════════
    # CALCULATRICE — Modes et conversions
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("calculatrice_standard", "systeme", "Ouvrir la calculatrice Windows", [
        "ouvre la calculatrice", "calculatrice", "calc",
        "lance la calculette",
    ], "powershell", "Start-Process calc"),
    JarvisCommand("calculer_expression", "systeme", "Calculer une expression mathematique", [
        "calcule {expr}", "combien fait {expr}", "resultat de {expr}",
        "{expr} egal combien",
    ], "powershell", "$r = Invoke-Expression '{expr}' 2>&1; \"Resultat: $r\"", ["expr"]),
    JarvisCommand("convertir_temperature", "systeme", "Convertir Celsius en Fahrenheit et inversement", [
        "convertis {temp} degres", "celsius en fahrenheit {temp}",
        "fahrenheit en celsius {temp}", "temperature {temp}",
    ], "powershell", "$t = {temp}; if($t -gt 60){$c = [math]::Round(($t-32)*5/9,1); \"$t F = $c C\"}else{$f = [math]::Round($t*9/5+32,1); \"$t C = $f F\"}", ["temp"]),
    JarvisCommand("convertir_octets", "systeme", "Convertir des octets en unites lisibles", [
        "convertis {bytes} octets", "combien de go fait {bytes}",
        "bytes en gb {bytes}", "taille {bytes}",
    ], "powershell", "$b = [double]'{bytes}'; if($b -ge 1TB){\"$([math]::Round($b/1TB,2)) TB\"}elseif($b -ge 1GB){\"$([math]::Round($b/1GB,2)) GB\"}elseif($b -ge 1MB){\"$([math]::Round($b/1MB,2)) MB\"}else{\"$([math]::Round($b/1KB,2)) KB\"}", ["bytes"]),

    # ══════════════════════════════════════════════════════════════════════
    # TEXTE & ENCODAGE — Transformations clipboard avancées
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("clipboard_base64_encode", "systeme", "Encoder le clipboard en Base64", [
        "encode en base64", "base64 encode", "clipboard en base64",
        "convertis en base64",
    ], "powershell", "$c = Get-Clipboard; if($c){$b = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($c)); Set-Clipboard $b; \"Base64 ($($b.Length) chars) copie\"}else{'Vide'}"),
    JarvisCommand("clipboard_base64_decode", "systeme", "Decoder le clipboard depuis Base64", [
        "decode le base64", "base64 decode", "clipboard depuis base64",
        "decodifie base64",
    ], "powershell", "$c = Get-Clipboard; if($c){try{$d = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($c)); Set-Clipboard $d; \"Decode ($($d.Length) chars) copie\"}catch{'Pas du Base64 valide'}}else{'Vide'}"),
    JarvisCommand("clipboard_url_encode", "systeme", "Encoder le clipboard en URL (percent-encode)", [
        "url encode", "encode l'url", "percent encode",
        "echappe l'url",
    ], "powershell", "$c = Get-Clipboard; if($c){$e = [uri]::EscapeDataString($c); Set-Clipboard $e; \"URL encode ($($e.Length) chars) copie\"}else{'Vide'}"),
    JarvisCommand("clipboard_json_format", "systeme", "Formatter le JSON du clipboard avec indentation", [
        "formate le json", "json pretty", "indente le json",
        "beautify json clipboard",
    ], "powershell", "$c = Get-Clipboard; if($c){try{$j = $c | ConvertFrom-Json | ConvertTo-Json -Depth 10; Set-Clipboard $j; \"JSON formate copie\"}catch{'Pas du JSON valide'}}else{'Vide'}"),
    JarvisCommand("clipboard_md5", "systeme", "Calculer le MD5 du texte dans le clipboard", [
        "md5 du clipboard", "hash md5 texte", "md5 du texte copie",
        "checksum clipboard",
    ], "powershell", "$c = Get-Clipboard; if($c){$md5 = [System.Security.Cryptography.MD5]::Create(); $hash = [BitConverter]::ToString($md5.ComputeHash([Text.Encoding]::UTF8.GetBytes($c))) -replace '-',''; Set-Clipboard $hash; \"MD5: $hash (copie)\"}else{'Vide'}"),
    JarvisCommand("clipboard_sort_lines", "systeme", "Trier les lignes du clipboard par ordre alphabetique", [
        "trie les lignes", "sort lines clipboard", "ordonne le clipboard",
        "classe les lignes",
    ], "powershell", "$c = Get-Clipboard; if($c){$s = ($c -split '`n' | Sort-Object) -join \"`n\"; Set-Clipboard $s; \"$($s.Split(\"`n\").Count) lignes triees\"}else{'Vide'}"),
    JarvisCommand("clipboard_unique_lines", "systeme", "Supprimer les lignes dupliquees du clipboard", [
        "deduplique les lignes", "unique lines", "enleve les doublons texte",
        "clipboard sans doublons",
    ], "powershell", "$c = Get-Clipboard; if($c){$u = ($c -split '`n' | Select-Object -Unique) -join \"`n\"; $orig = ($c -split '`n').Count; $new = ($u -split '`n').Count; Set-Clipboard $u; \"$orig -> $new lignes (suppr $($orig-$new) doublons)\"}else{'Vide'}"),
    JarvisCommand("clipboard_reverse", "systeme", "Inverser le texte du clipboard", [
        "inverse le texte", "reverse clipboard", "texte a l'envers",
        "retourne le texte",
    ], "powershell", "$c = Get-Clipboard; if($c){$r = -join ($c.ToCharArray() | Sort-Object {$null} -Descending); Set-Clipboard $r; \"Texte inverse ($($r.Length) chars)\"}else{'Vide'}"),

    # ══════════════════════════════════════════════════════════════════════
    # FICHIERS — Gestion dossier Téléchargements & organisation
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("taille_telechargements", "fichiers", "Taille du dossier Telechargements", [
        "taille telechargements", "poids downloads", "combien dans les telechargements",
        "downloads size",
    ], "powershell", "$d = \"$env:USERPROFILE\\Downloads\"; $s = (Get-ChildItem $d -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum; $c = (Get-ChildItem $d -File -ErrorAction SilentlyContinue).Count; \"Telechargements: $([math]::Round($s/1GB,2)) GB ($c fichiers)\""),
    JarvisCommand("vider_telechargements", "fichiers", "Vider le dossier Telechargements (fichiers > 30 jours)", [
        "vide les telechargements", "nettoie les downloads", "clean downloads",
        "supprime les vieux telechargements",
    ], "powershell", "$d = \"$env:USERPROFILE\\Downloads\"; $old = Get-ChildItem $d -File | Where { $_.LastWriteTime -lt (Get-Date).AddDays(-30) }; $old | Remove-Item -Force -ErrorAction SilentlyContinue; \"$($old.Count) fichiers > 30 jours supprimes\"", confirm=True),
    JarvisCommand("lister_telechargements", "fichiers", "Derniers fichiers telecharges", [
        "derniers telechargements", "quoi de telecharge", "recent downloads",
        "fichiers telecharges",
    ], "powershell", "Get-ChildItem \"$env:USERPROFILE\\Downloads\" -File | Sort LastWriteTime -Descending | Select -First 15 @{N='Date';E={$_.LastWriteTime.ToString('dd/MM HH:mm')}}, @{N='Taille(MB)';E={[math]::Round($_.Length/1MB,1)}}, Name | Format-Table -AutoSize | Out-String"),
    JarvisCommand("ouvrir_telechargements", "fichiers", "Ouvrir le dossier Telechargements", [
        "ouvre les telechargements", "dossier downloads", "va dans les telechargements",
        "ouvre downloads",
    ], "powershell", "Start-Process explorer \"$env:USERPROFILE\\Downloads\""),
    JarvisCommand("ouvrir_documents", "fichiers", "Ouvrir le dossier Documents", [
        "ouvre les documents", "dossier documents", "mes documents",
        "ouvre mes fichiers",
    ], "powershell", "Start-Process explorer \"$env:USERPROFILE\\Documents\""),
    JarvisCommand("ouvrir_bureau_dossier", "fichiers", "Ouvrir F:\\BUREAU dans l'explorateur", [
        "ouvre le bureau", "dossier bureau", "va dans bureau",
        "explore le bureau",
    ], "powershell", "Start-Process explorer 'F:\\BUREAU'"),
    JarvisCommand("fichier_recent_modifie", "fichiers", "Trouver le dernier fichier modifie partout", [
        "dernier fichier modifie", "quoi vient de changer", "last modified",
        "fichier le plus recent",
    ], "powershell", "Get-ChildItem F:\\BUREAU -Recurse -File -ErrorAction SilentlyContinue | Where { $_.FullName -notmatch '\\.git|__pycache__|node_modules' } | Sort LastWriteTime -Descending | Select -First 1 @{N='Modifie';E={$_.LastWriteTime.ToString('dd/MM/yyyy HH:mm')}}, FullName | Out-String"),
    JarvisCommand("compter_fichiers_type", "fichiers", "Compter les fichiers par extension dans un dossier", [
        "compte les fichiers par type", "extensions dans {path}",
        "quels types de fichiers dans {path}",
    ], "powershell", "Get-ChildItem '{path}' -Recurse -File -ErrorAction SilentlyContinue | Group Extension | Sort Count -Descending | Select @{N='Type';E={if($_.Name){$_.Name}else{'(sans)'}}} , Count | Select -First 15 | Format-Table -AutoSize | Out-String", ["path"]),

    # ══════════════════════════════════════════════════════════════════════
    # POWER MANAGEMENT — Modes performance et économie
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("power_performance", "systeme", "Activer le plan d'alimentation Haute Performance", [
        "mode performance", "high performance", "pleine puissance",
        "plan performance", "boost le pc",
    ], "powershell", "powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c; 'Plan Haute Performance active'"),
    JarvisCommand("power_equilibre", "systeme", "Activer le plan d'alimentation Equilibre", [
        "mode equilibre", "balanced power", "plan normal",
        "performance normale",
    ], "powershell", "powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e; 'Plan Equilibre active'"),
    JarvisCommand("power_economie", "systeme", "Activer le plan d'alimentation Economie d'energie", [
        "mode economie", "power saver", "economie energie",
        "plan economique", "economise la batterie",
    ], "powershell", "powercfg /setactive a1841308-3541-4fab-bc81-f71556f20b4a; 'Plan Economie d energie active'"),
    JarvisCommand("power_plans_list", "systeme", "Lister les plans d'alimentation disponibles", [
        "quels plans alimentation", "power plans", "modes d'alimentation disponibles",
        "liste les plans",
    ], "powershell", "powercfg /list | Out-String"),
    JarvisCommand("sleep_timer_30", "systeme", "Mettre le PC en veille dans 30 minutes", [
        "veille dans 30 minutes", "sleep dans 30 min", "dors dans une demi heure",
        "timer veille 30",
    ], "powershell", "Start-Job -ScriptBlock { Start-Sleep 1800; Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend',$false,$false) } | Out-Null; 'Veille programmee dans 30 minutes'", confirm=True),

    # ══════════════════════════════════════════════════════════════════════
    # RÉSEAU — Reset et dépannage complet
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("network_reset", "systeme", "Reset complet de la pile reseau Windows", [
        "reset reseau", "reinitialise le reseau", "network reset",
        "repare le reseau",
    ], "powershell", "netsh winsock reset; netsh int ip reset; ipconfig /flushdns; 'Pile reseau reinitialisee — redemarrage recommande'", confirm=True),
    JarvisCommand("network_troubleshoot", "systeme", "Lancer le depanneur reseau Windows", [
        "depanne le reseau", "network troubleshoot", "diagnostic reseau windows",
        "aide reseau",
    ], "powershell", "Start-Process msdt -ArgumentList '/id NetworkDiagnosticsWeb'"),
    JarvisCommand("arp_table", "systeme", "Afficher la table ARP (machines sur le reseau local)", [
        "table arp", "machines sur le reseau", "arp -a",
        "qui est sur mon reseau",
    ], "powershell", "arp -a | Out-String"),
    JarvisCommand("nslookup_domain", "systeme", "Resoudre un nom de domaine (nslookup)", [
        "nslookup {domain}", "resous {domain}", "ip de {domain}",
        "dns lookup {domain}",
    ], "powershell", "nslookup '{domain}' 2>&1 | Out-String", ["domain"]),

    # ══════════════════════════════════════════════════════════════════════
    # REGISTRE WINDOWS — Manipulation du registre
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("registry_backup", "systeme", "Sauvegarder le registre complet", [
        "backup registre", "sauvegarde le registre", "exporte le registre",
        "backup registry",
    ], "powershell", "reg export HKLM F:\\BUREAU\\registry_backup_$(Get-Date -Format yyyyMMdd).reg /y 2>&1; 'Registre HKLM exporte'", confirm=True),
    JarvisCommand("registry_search", "systeme", "Chercher une cle dans le registre", [
        "cherche dans le registre {cle}", "registry search {cle}",
        "trouve la cle {cle}",
    ], "powershell", "Get-ChildItem -Path HKCU:\\Software -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '*{cle}*' } | Select -First 10 | Out-String", ["cle"]),
    JarvisCommand("registry_recent_changes", "systeme", "Cles de registre recemment modifiees", [
        "registre recent", "changements registre", "modifications registre",
    ], "powershell", "Get-ChildItem HKCU:\\Software -ErrorAction SilentlyContinue | Sort LastWriteTime -Descending | Select -First 15 Name, @{N='Modified';E={$_.LastWriteTime}} | Format-Table | Out-String"),
    JarvisCommand("registry_startup_entries", "systeme", "Lister les entrees de demarrage dans le registre", [
        "startup registre", "autorun registre", "demarrage registre",
    ], "powershell", "Get-ItemProperty HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run -ErrorAction SilentlyContinue | Format-List | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # POLICES — Gestion des fonts Windows
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("fonts_list", "systeme", "Lister les polices installees", [
        "liste les polices", "quelles fonts", "polices installees",
        "mes polices",
    ], "powershell", "(New-Object System.Drawing.Text.InstalledFontCollection).Families | Select -First 40 | ForEach-Object { $_.Name } | Out-String"),
    JarvisCommand("fonts_count", "systeme", "Compter les polices installees", [
        "combien de polices", "nombre de fonts", "total polices",
    ], "powershell", "$c = (New-Object System.Drawing.Text.InstalledFontCollection).Families.Count; \"$c polices installees\""),
    JarvisCommand("fonts_folder", "systeme", "Ouvrir le dossier des polices", [
        "dossier polices", "ouvre les fonts", "ouvrir dossier fonts",
    ], "powershell", "Start-Process 'C:\\Windows\\Fonts'"),

    # ══════════════════════════════════════════════════════════════════════
    # VARIABLES D'ENVIRONNEMENT — Gestion des env vars
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("env_list_user", "systeme", "Lister les variables d'environnement utilisateur", [
        "variables utilisateur", "env vars user", "mes variables",
        "environnement utilisateur",
    ], "powershell", "[Environment]::GetEnvironmentVariables('User') | Format-Table -AutoSize | Out-String"),
    JarvisCommand("env_list_system", "systeme", "Lister les variables d'environnement systeme", [
        "variables systeme", "env vars systeme", "environnement systeme",
    ], "powershell", "[Environment]::GetEnvironmentVariables('Machine') | Format-Table -AutoSize | Out-String"),
    JarvisCommand("env_set_user", "systeme", "Definir une variable d'environnement utilisateur", [
        "set variable {nom} {valeur}", "definis {nom} a {valeur}",
        "env set {nom} {valeur}",
    ], "powershell", "[Environment]::SetEnvironmentVariable('{nom}', '{valeur}', 'User'); \"Variable {nom} = {valeur} definie\"", ["nom", "valeur"]),
    JarvisCommand("env_path_entries", "systeme", "Lister les dossiers dans le PATH", [
        "montre le path", "dossiers du path", "contenu du path",
        "qu'est ce qu'il y a dans le path",
    ], "powershell", "$env:PATH -split ';' | Where-Object { $_ } | ForEach-Object { $i=0 } { $i++; \"$i. $_\" } | Out-String"),
    JarvisCommand("env_add_to_path", "systeme", "Ajouter un dossier au PATH utilisateur", [
        "ajoute au path {dossier}", "path add {dossier}",
        "rajoute {dossier} au path",
    ], "powershell", "$p = [Environment]::GetEnvironmentVariable('PATH','User'); if($p -notlike '*{dossier}*'){[Environment]::SetEnvironmentVariable('PATH',\"$p;{dossier}\",'User'); '{dossier} ajoute au PATH'}else{'Deja dans le PATH'}", ["dossier"]),

    # ══════════════════════════════════════════════════════════════════════
    # TÂCHES PLANIFIÉES — Gestion avancée
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("schtask_running", "systeme", "Lister les taches planifiees en cours d'execution", [
        "taches en cours", "scheduled tasks running", "taches actives",
    ], "powershell", "Get-ScheduledTask | Where-Object { $_.State -eq 'Running' } | Select TaskName, State, TaskPath | Format-Table | Out-String"),
    JarvisCommand("schtask_next_run", "systeme", "Prochaines taches planifiees", [
        "prochaines taches", "next scheduled tasks", "quand les taches",
    ], "powershell", "Get-ScheduledTask | Get-ScheduledTaskInfo -ErrorAction SilentlyContinue | Where-Object { $_.NextRunTime -gt (Get-Date) } | Sort NextRunTime | Select -First 15 TaskName, NextRunTime | Format-Table | Out-String"),
    JarvisCommand("schtask_history", "systeme", "Historique des taches planifiees recentes", [
        "historique taches", "task history", "dernieres taches executees",
    ], "powershell", "Get-ScheduledTask | Get-ScheduledTaskInfo -ErrorAction SilentlyContinue | Where-Object { $_.LastRunTime -gt (Get-Date).AddDays(-1) } | Sort LastRunTime -Descending | Select -First 15 TaskName, LastRunTime, LastTaskResult | Format-Table | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # PARE-FEU WINDOWS — Gestion du firewall
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("firewall_status", "systeme", "Statut du pare-feu Windows", [
        "statut pare feu", "firewall status", "etat du firewall",
        "le pare feu est actif",
    ], "powershell", "Get-NetFirewallProfile | Select Name, Enabled, DefaultInboundAction, DefaultOutboundAction | Format-Table | Out-String"),
    JarvisCommand("firewall_rules_list", "systeme", "Lister les regles du pare-feu actives", [
        "regles pare feu", "firewall rules", "liste les regles firewall",
    ], "powershell", "Get-NetFirewallRule -Enabled True -Direction Inbound | Select -First 20 DisplayName, Action, Profile | Format-Table | Out-String"),
    JarvisCommand("firewall_block_ip", "systeme", "Bloquer une adresse IP dans le pare-feu", [
        "bloque l'ip {ip}", "firewall block {ip}", "interdit {ip}",
        "ban {ip}",
    ], "powershell", "New-NetFirewallRule -DisplayName 'JARVIS Block {ip}' -Direction Inbound -RemoteAddress {ip} -Action Block; 'IP {ip} bloquee dans le pare-feu'", ["ip"], confirm=True),
    JarvisCommand("firewall_recent_blocks", "systeme", "Voir les connexions recemment bloquees", [
        "connexions bloquees", "firewall blocks", "qui est bloque",
    ], "powershell", "Get-WinEvent -FilterHashtable @{LogName='Security';Id=5157} -MaxEvents 15 -ErrorAction SilentlyContinue | Select TimeCreated, @{N='Details';E={$_.Message.Substring(0,[Math]::Min(100,$_.Message.Length))}} | Format-Table -Wrap | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # DISQUE — Santé et performance
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("disk_smart_status", "systeme", "Statut SMART des disques (sante)", [
        "sante des disques", "smart status", "etat des disques",
        "disques en bonne sante",
    ], "powershell", "Get-PhysicalDisk | Select FriendlyName, MediaType, HealthStatus, OperationalStatus, @{N='Size(GB)';E={[math]::Round($_.Size/1GB)}} | Format-Table | Out-String"),
    JarvisCommand("disk_space_by_folder", "systeme", "Espace utilise par dossier (top 15)", [
        "espace par dossier", "quels dossiers prennent de la place",
        "gros dossiers", "qui prend de la place",
    ], "powershell", "Get-ChildItem F:\\ -Directory -ErrorAction SilentlyContinue | ForEach-Object { $s = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; [PSCustomObject]@{Dossier=$_.Name; 'Taille(GB)'=[math]::Round($s/1GB,2)} } | Sort 'Taille(GB)' -Descending | Select -First 15 | Format-Table | Out-String"),
    JarvisCommand("disk_temp_files_age", "systeme", "Fichiers temporaires les plus anciens", [
        "vieux fichiers temp", "anciens temp", "temp files age",
    ], "powershell", "Get-ChildItem $env:TEMP -File -ErrorAction SilentlyContinue | Where { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } | Sort LastWriteTime | Select -First 15 Name, @{N='Age(j)';E={((Get-Date)-$_.LastWriteTime).Days}}, @{N='MB';E={[math]::Round($_.Length/1MB,1)}} | Format-Table | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # USB — Gestion des périphériques USB
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("usb_list_devices", "systeme", "Lister les peripheriques USB connectes", [
        "peripheriques usb", "usb connectes", "quels usb",
        "liste les usb",
    ], "powershell", "Get-PnpDevice -Class USB -Status OK -ErrorAction SilentlyContinue | Select FriendlyName, Status, InstanceId | Format-Table | Out-String"),
    JarvisCommand("usb_storage_list", "systeme", "Lister les cles USB et disques amovibles", [
        "cles usb", "disques amovibles", "usb storage",
        "quelles cles usb",
    ], "powershell", "Get-WmiObject Win32_DiskDrive | Where { $_.InterfaceType -eq 'USB' } | Select Model, @{N='Size(GB)';E={[math]::Round($_.Size/1GB)}} | Format-Table | Out-String"),
    JarvisCommand("usb_safely_eject", "systeme", "Ejecter un peripherique USB en securite", [
        "ejecte la cle usb", "ejecter usb", "safely eject",
        "retire la cle",
    ], "powershell", "$d = (Get-WmiObject Win32_DiskDrive | Where { $_.InterfaceType -eq 'USB' } | Select -First 1); if($d){$eject = New-Object -ComObject Shell.Application; $eject.Namespace(17).ParseName(($d.DeviceID)).InvokeVerb('Eject'); 'Ejection demandee'}else{'Aucun USB trouve'}", confirm=True),
    JarvisCommand("usb_history", "systeme", "Historique des peripheriques USB connectes", [
        "historique usb", "anciens usb", "usb history",
        "quels usb ont ete branches",
    ], "powershell", "Get-ItemProperty HKLM:\\SYSTEM\\CurrentControlSet\\Enum\\USBSTOR\\*\\* -ErrorAction SilentlyContinue | Select FriendlyName, @{N='LastSeen';E={$_.ContainerID}} | Select -First 20 | Format-Table | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # ÉCRAN / AFFICHAGE — Paramètres d'écran
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("screen_resolution", "systeme", "Afficher la resolution de chaque ecran", [
        "resolution ecran", "quelle resolution", "taille ecran",
        "resolution affichage",
    ], "powershell", "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::AllScreens | ForEach-Object { \"$($_.DeviceName): $($_.Bounds.Width)x$($_.Bounds.Height) $(if($_.Primary){'(Principal)'}else{''})\" } | Out-String"),
    JarvisCommand("screen_brightness_up", "systeme", "Augmenter la luminosite", [
        "augmente la luminosite", "plus de lumiere", "brightness up",
        "ecran plus lumineux",
    ], "powershell", "$b = (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness -ErrorAction SilentlyContinue).CurrentBrightness; if($b -ne $null){$n=[math]::Min(100,$b+10); (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(0,$n); \"Luminosite: $n%\"}else{'Non supporte (desktop)'}"),
    JarvisCommand("screen_brightness_down", "systeme", "Baisser la luminosite", [
        "baisse la luminosite", "moins de lumiere", "brightness down",
        "ecran moins lumineux",
    ], "powershell", "$b = (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness -ErrorAction SilentlyContinue).CurrentBrightness; if($b -ne $null){$n=[math]::Max(0,$b-10); (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(0,$n); \"Luminosite: $n%\"}else{'Non supporte (desktop)'}"),
    JarvisCommand("screen_night_light", "systeme", "Activer/desactiver l'eclairage nocturne", [
        "eclairage nocturne", "night light", "mode nuit ecran",
        "lumiere bleue",
    ], "powershell", "Start-Process ms-settings:nightlight"),
    JarvisCommand("screen_refresh_rate", "systeme", "Voir la frequence de rafraichissement", [
        "frequence ecran", "refresh rate", "hertz ecran",
        "combien de hertz",
    ], "powershell", "Get-CimInstance Win32_VideoController | Select Name, @{N='RefreshRate(Hz)';E={$_.CurrentRefreshRate}}, @{N='Resolution';E={\"$($_.CurrentHorizontalResolution)x$($_.CurrentVerticalResolution)\"}} | Format-Table | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # AUDIO — Gestion des périphériques audio
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("audio_list_devices", "systeme", "Lister tous les peripheriques audio", [
        "peripheriques audio", "devices audio", "quels hauts parleurs",
        "liste les devices son",
    ], "powershell", "Get-PnpDevice -Class AudioEndpoint -Status OK -ErrorAction SilentlyContinue | Select FriendlyName, Status | Format-Table | Out-String"),
    JarvisCommand("audio_default_speaker", "systeme", "Voir le haut-parleur par defaut", [
        "haut parleur par defaut", "quel speaker", "sortie audio",
        "default speaker",
    ], "powershell", "Get-AudioDevice -Playback -ErrorAction SilentlyContinue | Select Name, Default | Format-Table | Out-String; if($?-eq $false){Get-CimInstance Win32_SoundDevice | Select Name, Status | Format-Table | Out-String}"),
    JarvisCommand("audio_volume_level", "systeme", "Voir le niveau de volume actuel", [
        "quel volume", "niveau du son", "volume level",
        "le son est a combien",
    ], "powershell", "Add-Type -TypeDefinition 'using System.Runtime.InteropServices; [Guid(\"5CDF2C82-841E-4546-9722-0CF74078229A\"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)] interface IAudioEndpointVolume { int a(); int b(); int c(); int d(); int e(); int f(); int g(); int h(); int GetMasterVolumeLevelScalar(out float pfLevel); }'; 'Volume: voir Parametres > Son'"),
    JarvisCommand("audio_settings", "systeme", "Ouvrir les parametres de son", [
        "parametres son", "reglages audio", "settings audio",
        "ouvre les parametres de son",
    ], "powershell", "Start-Process ms-settings:sound"),

    # ══════════════════════════════════════════════════════════════════════
    # PROCESSUS AVANCÉ — Gestion des processus détaillée
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("process_by_memory", "systeme", "Top 15 processus par memoire", [
        "processus par memoire", "qui consomme la ram", "top ram",
        "memory hogs",
    ], "powershell", "Get-Process | Sort WorkingSet64 -Descending | Select -First 15 Name, @{N='RAM(MB)';E={[math]::Round($_.WorkingSet64/1MB)}}, CPU, Id | Format-Table | Out-String"),
    JarvisCommand("process_by_cpu", "systeme", "Top 15 processus par CPU", [
        "processus par cpu", "qui consomme le cpu", "top cpu",
        "cpu hogs",
    ], "powershell", "Get-Process | Where { $_.CPU -gt 0 } | Sort CPU -Descending | Select -First 15 Name, @{N='CPU(s)';E={[math]::Round($_.CPU,1)}}, @{N='RAM(MB)';E={[math]::Round($_.WorkingSet64/1MB)}}, Id | Format-Table | Out-String"),
    JarvisCommand("process_tree", "systeme", "Arborescence des processus (parent-enfant)", [
        "arbre des processus", "process tree", "qui lance quoi",
        "hierarchie processus",
    ], "powershell", "Get-CimInstance Win32_Process | Select Name, ProcessId, ParentProcessId | Sort ParentProcessId | Select -First 30 | Format-Table | Out-String"),
    JarvisCommand("process_handles", "systeme", "Processus avec le plus de handles ouverts", [
        "handles ouverts", "processus handles", "qui a trop de handles",
    ], "powershell", "Get-Process | Sort HandleCount -Descending | Select -First 15 Name, HandleCount, @{N='RAM(MB)';E={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table | Out-String"),
]
