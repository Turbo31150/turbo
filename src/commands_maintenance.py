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
]
