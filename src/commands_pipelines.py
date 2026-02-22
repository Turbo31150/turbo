"""JARVIS — Commandes pipeline multi-etapes (workflows pre-enregistres)."""

from __future__ import annotations

from src.commands import JarvisCommand

COMET = r"C:\Users\franc\AppData\Local\Perplexity\Comet\Application\comet.exe"
MINIMIZE_ALL = "powershell:(New-Object -ComObject Shell.Application).MinimizeAll()"

PIPELINE_COMMANDS: list[JarvisCommand] = [
    # ══════════════════════════════════════════════════════════════════════
    # MODE — Ambiances et configurations d'usage
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("mode_musique", "pipeline", "Mode musique: minimiser tout + ouvrir Spotify", [
        "mode musique", "lance la musique en fond",
        "ambiance musicale", "mets de la musique",
        "lance le mode musique",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;app_open:spotify"),
    JarvisCommand("mode_gaming", "pipeline", "Mode gaming: haute performance + Steam + Game Bar", [
        "mode gaming", "mode jeu", "lance le mode gaming",
        "mode gamer", "session gaming",
        "lance le mode jeu",
    ], "pipeline", "powershell:powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c;;sleep:1;;app_open:steam;;sleep:2;;hotkey:win+g"),
    JarvisCommand("mode_stream", "pipeline", "Mode stream: minimiser tout + OBS + Spotify", [
        "mode stream", "lance le stream", "mode streaming",
        "setup stream", "lance le mode stream",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;app_open:obs64;;sleep:2;;app_open:spotify"),
    JarvisCommand("mode_presentation", "pipeline", "Mode presentation: dupliquer ecran + PowerPoint", [
        "mode presentation", "lance la presentation",
        "mode pres", "setup presentation",
        "lance le mode presentation",
    ], "pipeline", "powershell:DisplaySwitch.exe /clone;;sleep:2;;app_open:powerpnt"),
    JarvisCommand("mode_lecture", "pipeline", "Mode lecture: nuit + minimiser + Comet", [
        "mode lecture", "mode lire", "lance le mode lecture",
        "ambiance lecture", "mode bouquin",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;powershell:Start-Process '{COMET}'"),
    JarvisCommand("mode_reunion", "pipeline", "Mode reunion: Discord + focus assist", [
        "mode reunion", "lance la reunion", "mode meeting",
        "setup reunion", "lance le mode reunion",
    ], "pipeline", "app_open:discord;;sleep:1;;ms_settings:ms-settings:quiethours"),
    JarvisCommand("mode_code_turbo", "pipeline", "Mode dev turbo: VSCode + Terminal + LM Studio + Dashboard", [
        "mode code turbo", "setup dev complet", "mode turbo dev",
        "lance tout le dev", "mode dev complet",
        "ouvre mon environnement complet",
    ], "pipeline", "app_open:code;;sleep:1;;app_open:wt;;sleep:1;;app_open:lmstudio;;sleep:1;;browser:navigate:http://127.0.0.1:8080"),
    JarvisCommand("mode_detente", "pipeline", "Mode detente: minimiser + Spotify + lumiere nocturne", [
        "mode detente", "mode relax", "mode chill",
        "lance le mode detente", "ambiance zen",
        "mode zen",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;app_open:spotify;;sleep:1;;powershell:Start-Process ms-settings:nightlight"),

    # ══════════════════════════════════════════════════════════════════════
    # ROUTINE — Workflows recurrents
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("routine_soir", "pipeline", "Routine du soir: TradingView + night light + minimiser", [
        "routine du soir", "routine soir", "fin de journee",
        "lance la routine du soir", "evening routine",
    ], "pipeline", f"browser:navigate:https://www.tradingview.com;;sleep:2;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;{MINIMIZE_ALL}"),
    JarvisCommand("check_trading_rapide", "pipeline", "Check trading: TradingView + MEXC en parallele", [
        "check trading rapide", "check rapide trading",
        "jette un oeil au trading", "trading rapide",
        "coup d'oeil trading",
    ], "pipeline", "browser:navigate:https://www.tradingview.com;;browser:navigate:https://www.mexc.com"),
    JarvisCommand("setup_ia", "pipeline", "Setup IA: LM Studio + Dashboard + Terminal", [
        "setup ia", "lance le setup ia", "ouvre tout le cluster",
        "prepare le cluster", "mode ia",
        "lance le mode ia",
    ], "pipeline", "app_open:lmstudio;;sleep:1;;browser:navigate:http://127.0.0.1:8080;;sleep:1;;app_open:wt"),

    # ══════════════════════════════════════════════════════════════════════
    # MAINTENANCE — Nettoyage, diagnostic, securite
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("nettoyage_express", "pipeline", "Nettoyage express: corbeille + temp + DNS", [
        "nettoyage express", "nettoyage rapide", "clean express",
        "lance un nettoyage", "nettoie tout rapidement",
        "nettoyage du pc",
    ], "pipeline", "powershell:Clear-RecycleBin -Force -ErrorAction SilentlyContinue; 'Corbeille videe';;powershell:Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; 'Temp nettoye';;powershell:ipconfig /flushdns; 'DNS purge'", confirm=True),
    JarvisCommand("diagnostic_complet", "pipeline", "Diagnostic complet: systeme + GPU + RAM + disques", [
        "diagnostic complet", "diagnostic du pc", "check complet",
        "fais un diagnostic", "lance un diagnostic complet",
        "etat complet du systeme",
    ], "pipeline", "jarvis_tool:system_info;;jarvis_tool:gpu_info;;powershell:$os = Get-CimInstance Win32_OperatingSystem; $total = [math]::Round($os.TotalVisibleMemorySize/1MB,1); $free = [math]::Round($os.FreePhysicalMemory/1MB,1); \"RAM: $($total-$free)/$total GB\";;powershell:Get-PhysicalDisk | Select FriendlyName, HealthStatus, @{N='Size(GB)';E={[math]::Round($_.Size/1GB)}} | Out-String"),
    JarvisCommand("debug_reseau", "pipeline", "Debug reseau: flush DNS + ping + diagnostic", [
        "debug reseau", "debug le reseau", "diagnostic reseau rapide",
        "depanne le reseau rapidement", "check reseau complet",
    ], "pipeline", "powershell:ipconfig /flushdns; 'DNS purge';;powershell:$p = Test-Connection 8.8.8.8 -Count 2 -ErrorAction SilentlyContinue; if($p){'Ping Google: OK'}else{'Ping Google: ECHEC'};;powershell:$d = Resolve-DnsName google.com -ErrorAction SilentlyContinue; if($d){'DNS: OK'}else{'DNS: ECHEC'}"),
    JarvisCommand("veille_securisee", "pipeline", "Veille securisee: minimiser + verrouiller + veille", [
        "veille securisee", "mets en veille en securite",
        "veille et verrouille", "dors en securite",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;powershell:rundll32.exe user32.dll,LockWorkStation;;sleep:2;;powershell:rundll32.exe powrprof.dll,SetSuspendState 0,1,0", confirm=True),

    # ══════════════════════════════════════════════════════════════════════
    # COMET — Ouverture de sites specifiques via Comet
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvre_reddit_comet", "pipeline", "Ouvrir Reddit dans Comet", [
        "ouvre reddit sur comet", "reddit comet",
        "va sur reddit comet", "lance reddit comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://www.reddit.com'"),
    JarvisCommand("ouvre_twitter_comet", "pipeline", "Ouvrir Twitter/X dans Comet", [
        "ouvre twitter sur comet", "twitter comet", "x comet",
        "va sur twitter comet", "lance twitter comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://x.com'"),
    JarvisCommand("ouvre_chatgpt_comet", "pipeline", "Ouvrir ChatGPT dans Comet", [
        "ouvre chatgpt sur comet", "chatgpt comet",
        "va sur chatgpt comet", "lance chatgpt comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://chat.openai.com'"),
    JarvisCommand("ouvre_claude_comet", "pipeline", "Ouvrir Claude AI dans Comet", [
        "ouvre claude sur comet", "claude comet",
        "va sur claude comet", "lance claude comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://claude.ai'"),
    JarvisCommand("ouvre_linkedin_comet", "pipeline", "Ouvrir LinkedIn dans Comet", [
        "ouvre linkedin sur comet", "linkedin comet",
        "va sur linkedin comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://www.linkedin.com'"),
    JarvisCommand("ouvre_amazon_comet", "pipeline", "Ouvrir Amazon dans Comet", [
        "ouvre amazon sur comet", "amazon comet",
        "va sur amazon comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://www.amazon.fr'"),
    JarvisCommand("ouvre_twitch_comet", "pipeline", "Ouvrir Twitch dans Comet", [
        "ouvre twitch sur comet", "twitch comet",
        "va sur twitch comet", "lance twitch comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://www.twitch.tv'"),
    JarvisCommand("ouvre_social_comet", "pipeline", "Ouvrir les reseaux sociaux dans Comet (Twitter + Reddit + Discord)", [
        "ouvre les reseaux sociaux comet", "social comet",
        "lance les reseaux sociaux", "ouvre tout les reseaux",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://x.com';;sleep:1;;powershell:Start-Process '{COMET}' -ArgumentList 'https://www.reddit.com';;sleep:1;;app_open:discord"),
    JarvisCommand("ouvre_perplexity_comet", "pipeline", "Ouvrir Perplexity dans Comet", [
        "ouvre perplexity sur comet", "perplexity comet",
        "va sur perplexity comet", "lance perplexity comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://www.perplexity.ai'"),
    JarvisCommand("ouvre_huggingface_comet", "pipeline", "Ouvrir Hugging Face dans Comet", [
        "ouvre hugging face sur comet", "huggingface comet",
        "va sur hugging face comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://huggingface.co'"),

    # ══════════════════════════════════════════════════════════════════════
    # MODE — Nouveaux modes specialises
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("mode_crypto", "pipeline", "Mode crypto: TradingView + MEXC + CoinGecko", [
        "mode crypto", "mode trading crypto", "lance le mode crypto",
        "setup crypto", "ouvre tout le trading",
    ], "pipeline", "browser:navigate:https://www.tradingview.com;;sleep:1;;browser:navigate:https://www.mexc.com/exchange/BTC_USDT;;sleep:1;;browser:navigate:https://www.coingecko.com"),
    JarvisCommand("mode_ia_complet", "pipeline", "Mode IA complet: LM Studio + Dashboard + Claude + HuggingFace", [
        "mode ia complet", "ouvre tout le cluster ia",
        "lance toute l'ia", "setup ia complet",
        "mode intelligence artificielle",
    ], "pipeline", "app_open:lmstudio;;sleep:1;;browser:navigate:http://127.0.0.1:8080;;sleep:1;;browser:navigate:https://claude.ai;;sleep:1;;browser:navigate:https://huggingface.co"),
    JarvisCommand("mode_debug", "pipeline", "Mode debug: Terminal + GPU monitoring + logs systeme", [
        "mode debug", "mode debogage", "lance le mode debug",
        "setup debug", "ouvre les outils de debug",
    ], "pipeline", "app_open:wt;;sleep:1;;powershell:nvidia-smi;;powershell:Get-WinEvent -FilterHashtable @{LogName='System';Level=2} -MaxEvents 5 -ErrorAction SilentlyContinue | Select TimeCreated, Message | Out-String -Width 150"),
    JarvisCommand("mode_monitoring", "pipeline", "Mode monitoring: Dashboard + GPU + cluster health", [
        "mode monitoring", "mode surveillance", "lance le monitoring",
        "surveille tout", "mode supervision",
    ], "pipeline", "browser:navigate:http://127.0.0.1:8080;;sleep:1;;powershell:nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader;;powershell:$m2 = try{(Invoke-WebRequest -Uri 'http://192.168.1.26:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; $ol1 = try{(Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; \"M2: $(if($m2 -eq 200){'OK'}else{'OFFLINE'}) | OL1: $(if($ol1 -eq 200){'OK'}else{'OFFLINE'})\""),
    JarvisCommand("mode_communication", "pipeline", "Mode communication: Discord + Telegram + WhatsApp", [
        "mode communication", "mode com", "lance le mode com",
        "ouvre toutes les messageries", "mode messagerie",
    ], "pipeline", "app_open:discord;;sleep:1;;app_open:telegram;;sleep:1;;app_open:whatsapp"),
    JarvisCommand("mode_documentation", "pipeline", "Mode documentation: Notion + Google Docs + Drive", [
        "mode documentation", "mode docs", "lance le mode docs",
        "mode ecriture", "setup documentation",
    ], "pipeline", "browser:navigate:https://www.notion.so;;sleep:1;;browser:navigate:https://docs.google.com;;sleep:1;;browser:navigate:https://drive.google.com"),
    JarvisCommand("mode_focus_total", "pipeline", "Mode focus total: minimiser + focus assist + nuit + VSCode", [
        "mode focus total", "concentration maximale", "mode deep work",
        "focus absolu", "mode ultra focus",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;ms_settings:ms-settings:quiethours;;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;app_open:code"),
    JarvisCommand("mode_review", "pipeline", "Mode review: VSCode + navigateur Git + Terminal", [
        "mode review", "mode revue de code", "lance le mode review",
        "setup code review", "mode cr",
    ], "pipeline", "app_open:code;;sleep:1;;browser:navigate:https://github.com;;sleep:1;;app_open:wt"),

    # ══════════════════════════════════════════════════════════════════════
    # ROUTINE — Nouvelles routines
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("routine_matin", "pipeline", "Routine du matin: cluster + dashboard + trading + mails", [
        "routine du matin", "routine matin", "bonjour jarvis",
        "lance la routine du matin", "morning routine",
        "demarre la journee",
    ], "pipeline", "app_open:lmstudio;;sleep:2;;browser:navigate:http://127.0.0.1:8080;;sleep:1;;browser:navigate:https://www.tradingview.com;;sleep:1;;browser:navigate:https://mail.google.com"),
    JarvisCommand("backup_express", "pipeline", "Backup express: git add + commit du projet turbo", [
        "backup express", "sauvegarde rapide", "backup rapide",
        "sauvegarde le projet", "backup turbo",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; git add -A; git commit -m 'Backup express auto-JARVIS' 2>&1 | Out-String", confirm=True),
    JarvisCommand("reboot_cluster", "pipeline", "Reboot cluster: redemarre Ollama + ping LM Studio", [
        "reboot le cluster", "redemarre le cluster", "restart cluster ia",
        "relance le cluster", "reset cluster",
    ], "pipeline", "powershell:Stop-Process -Name 'ollama' -Force -ErrorAction SilentlyContinue; Start-Sleep 2; Start-Process 'ollama' -ArgumentList 'serve'; 'Ollama relance';;sleep:3;;powershell:$m2 = try{(Invoke-WebRequest -Uri 'http://192.168.1.26:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 5 -UseBasicParsing).StatusCode}catch{0}; $ol1 = try{(Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5 -UseBasicParsing).StatusCode}catch{0}; \"Apres reboot — M2: $(if($m2 -eq 200){'OK'}else{'OFFLINE'}) | OL1: $(if($ol1 -eq 200){'OK'}else{'OFFLINE'})\""),
    JarvisCommand("pause_travail", "pipeline", "Pause: minimiser + verrouiller ecran + Spotify", [
        "pause travail", "je fais une pause", "mode pause",
        "lance une pause", "break time",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;app_open:spotify;;sleep:2;;powershell:rundll32.exe user32.dll,LockWorkStation"),
    JarvisCommand("fin_journee", "pipeline", "Fin de journee: backup + nuit + fermer apps dev", [
        "fin de journee", "termine la journee", "je finis pour aujourd'hui",
        "bonne nuit jarvis", "on arrete pour aujourd'hui",
    ], "pipeline", f"powershell:cd F:\\BUREAU\\turbo; git add -A; git commit -m 'Fin de journee auto-JARVIS' --allow-empty 2>&1 | Out-String;;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;{MINIMIZE_ALL}"),

    # ══════════════════════════════════════════════════════════════════════
    # COMET — Nouveaux sites via Comet
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvre_github_via_comet", "pipeline", "Ouvrir GitHub dans Comet", [
        "ouvre github sur comet", "github comet",
        "va sur github comet", "lance github comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://github.com'"),
    JarvisCommand("ouvre_youtube_via_comet", "pipeline", "Ouvrir YouTube dans Comet", [
        "ouvre youtube sur comet", "youtube comet",
        "va sur youtube comet", "lance youtube comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://www.youtube.com'"),
    JarvisCommand("ouvre_tradingview_comet", "pipeline", "Ouvrir TradingView dans Comet", [
        "ouvre tradingview sur comet", "tradingview comet",
        "va sur tradingview comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://www.tradingview.com'"),
    JarvisCommand("ouvre_coingecko_comet", "pipeline", "Ouvrir CoinGecko dans Comet", [
        "ouvre coingecko sur comet", "coingecko comet",
        "va sur coingecko comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://www.coingecko.com'"),
    JarvisCommand("ouvre_ia_comet", "pipeline", "Ouvrir toutes les IA dans Comet (ChatGPT + Claude + Perplexity)", [
        "ouvre toutes les ia comet", "ia comet",
        "lance les ia sur comet", "ouvre les chatbots comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://chat.openai.com';;sleep:1;;powershell:Start-Process '{COMET}' -ArgumentList 'https://claude.ai';;sleep:1;;powershell:Start-Process '{COMET}' -ArgumentList 'https://www.perplexity.ai'"),

    # ══════════════════════════════════════════════════════════════════════
    # INSPIRÉ ALEXA ROUTINES — Modes ambiance et vie quotidienne
    # (source: reolink.com/blog/alexa-routines, the-ambient.com)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("mode_cinema_complet", "pipeline", "Mode cinema complet: minimiser + nuit + plein ecran + Netflix", [
        "mode cinema complet", "soiree film", "movie time",
        "lance un film", "mode film complet",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;browser:navigate:https://www.netflix.com;;sleep:2;;hotkey:f11"),
    JarvisCommand("mode_workout", "pipeline", "Mode workout: Spotify energique + YouTube fitness + timer", [
        "mode workout", "mode sport", "lance le sport",
        "mode entrainement", "session sport",
        "mode fitness",
    ], "pipeline", "app_open:spotify;;sleep:2;;browser:navigate:https://www.youtube.com/results?search_query=workout+timer+30+min;;sleep:1;;powershell:$t=New-TimeSpan -Minutes 30; \"Timer: $($t.Minutes) minutes — GO!\""),
    JarvisCommand("mode_etude", "pipeline", "Mode etude: focus + Wikipedia + Pomodoro mindset", [
        "mode etude", "mode revision", "mode etudiant",
        "lance le mode etude", "session revision",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;ms_settings:ms-settings:quiethours;;sleep:1;;browser:navigate:https://fr.wikipedia.org;;sleep:1;;browser:navigate:https://docs.google.com"),
    JarvisCommand("mode_diner", "pipeline", "Mode diner: minimiser + ambiance calme + Spotify", [
        "mode diner", "ambiance diner", "dinner time",
        "mode repas", "ambiance repas",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;app_open:spotify"),
    JarvisCommand("routine_depart", "pipeline", "Routine depart: sauvegarder + minimiser + verrouiller + economie", [
        "routine depart", "je pars", "je m'en vais",
        "a plus tard", "je quitte la maison",
        "mode absence",
    ], "pipeline", f"powershell:cd F:\\BUREAU\\turbo; git add -A; git commit -m 'Auto-save depart JARVIS' --allow-empty 2>&1 | Out-String;;sleep:1;;{MINIMIZE_ALL};;sleep:1;;powershell:powercfg /setactive a1841308-3541-4fab-bc81-f71556f20b4a;;sleep:1;;powershell:rundll32.exe user32.dll,LockWorkStation", confirm=True),
    JarvisCommand("routine_retour", "pipeline", "Routine retour: performance + cluster + mails + dashboard", [
        "routine retour", "je suis rentre", "je suis la",
        "je reviens", "mode retour",
    ], "pipeline", "powershell:powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c;;sleep:1;;app_open:lmstudio;;sleep:2;;browser:navigate:https://mail.google.com;;sleep:1;;browser:navigate:http://127.0.0.1:8080"),
    JarvisCommand("mode_nuit_totale", "pipeline", "Mode nuit: fermer tout + nuit + volume bas + verrouiller", [
        "mode nuit totale", "dodo", "je vais dormir",
        "extinction totale", "mode sommeil",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;powershell:(New-Object -ComObject WScript.Shell).SendKeys([char]174);(New-Object -ComObject WScript.Shell).SendKeys([char]174);(New-Object -ComObject WScript.Shell).SendKeys([char]174);;sleep:1;;powershell:rundll32.exe user32.dll,LockWorkStation", confirm=True),

    # ══════════════════════════════════════════════════════════════════════
    # INSPIRÉ XDA/MEDIUM — Workflows developpeur (gated launch)
    # (source: xda-developers.com, bhavyansh001.medium.com)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("dev_morning_setup", "pipeline", "Dev morning: git pull + Docker + VSCode + browser tabs travail", [
        "dev morning", "setup dev du matin", "prepare le dev",
        "ouvre mon environnement dev", "lance le setup dev",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; git pull --rebase 2>&1 | Out-String;;sleep:1;;app_open:code;;sleep:2;;app_open:wt;;sleep:1;;browser:navigate:https://github.com;;sleep:1;;browser:navigate:http://127.0.0.1:8080"),
    JarvisCommand("dev_deep_work", "pipeline", "Deep work: fermer distractions + VSCode + focus + terminal", [
        "deep work", "travail profond", "mode deep focus",
        "concentration dev", "code sans distraction",
    ], "pipeline", f"powershell:Stop-Process -Name 'discord','telegram','slack' -Force -ErrorAction SilentlyContinue; 'Distractions fermees';;sleep:1;;{MINIMIZE_ALL};;sleep:1;;ms_settings:ms-settings:quiethours;;sleep:1;;app_open:code;;sleep:1;;app_open:wt"),
    JarvisCommand("dev_standup_prep", "pipeline", "Standup prep: git log hier + board + dashboard", [
        "standup prep", "prepare le standup", "qu'est ce que j'ai fait hier",
        "recap hier", "preparation standup",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; git log --since='yesterday' --oneline 2>&1 | Out-String;;sleep:1;;browser:navigate:https://github.com;;sleep:1;;browser:navigate:http://127.0.0.1:8080"),
    JarvisCommand("dev_deploy_check", "pipeline", "Pre-deploy check: tests + git status + Docker status", [
        "check avant deploy", "pre deploy", "verification deploy",
        "pret a deployer", "deploy check",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run pytest -x --tb=short 2>&1 | Select -Last 10 | Out-String;;powershell:cd F:\\BUREAU\\turbo; git status -sb;;powershell:docker ps --format 'table {{.Names}}\\t{{.Status}}' 2>&1 | Out-String"),
    JarvisCommand("dev_friday_report", "pipeline", "Rapport vendredi: stats git semaine + dashboard + todos", [
        "rapport vendredi", "friday report", "recap de la semaine",
        "bilan semaine", "rapport hebdo",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; 'Commits cette semaine:'; git log --since='last monday' --oneline 2>&1 | Out-String;;powershell:cd F:\\BUREAU\\turbo; $py = (Get-ChildItem src/*.py -Recurse | Get-Content | Measure-Object -Line).Lines; \"Lignes de code: $py\";;browser:navigate:http://127.0.0.1:8080"),
    JarvisCommand("dev_code_review_setup", "pipeline", "Code review setup: GitHub PRs + VSCode + diff terminal", [
        "setup code review", "prepare la review", "code review setup",
        "lance la revue de code",
    ], "pipeline", "browser:navigate:https://github.com/pulls;;sleep:1;;app_open:code;;sleep:1;;powershell:cd F:\\BUREAU\\turbo; git diff --stat 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # INSPIRÉ POWERSHELL AUTOMATION — Audit, rapport, maintenance
    # (source: attuneops.io, ninjaone.com, learn.microsoft.com)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("audit_securite_complet", "pipeline", "Audit securite: Defender + ports + connexions + firewall + autorun", [
        "audit securite complet", "scan securite total", "audit de securite",
        "check securite complet", "securite totale",
    ], "pipeline", "powershell:Get-MpComputerStatus | Select AntivirusEnabled, RealTimeProtectionEnabled | Out-String;;powershell:Get-NetTCPConnection -State Listen | Group-Object LocalPort | Select @{N='Port';E={$_.Name}}, Count | Sort Port | Select -First 10 | Out-String;;powershell:Get-NetTCPConnection -State Established | Where RemoteAddress -notmatch '^(127|10|192\\.168|0\\.)' | Select RemoteAddress, RemotePort -Unique | Select -First 10 | Out-String;;powershell:Get-NetFirewallProfile | Select Name, Enabled | Out-String;;powershell:Get-CimInstance Win32_StartupCommand | Select Name, Command | Select -First 10 | Out-String"),
    JarvisCommand("rapport_systeme_complet", "pipeline", "Rapport systeme: CPU + RAM + GPU + disques + uptime + reseau", [
        "rapport systeme complet", "rapport systeme", "etat complet du pc",
        "bilan systeme", "diagnostic total",
    ], "pipeline", "powershell:$cpu = (Get-CimInstance Win32_Processor).Name; $usage = (Get-Counter '\\Processor(_Total)\\% Processor Time' -SampleInterval 1 -MaxSamples 1).CounterSamples.CookedValue; \"CPU: $cpu ($([math]::Round($usage))%)\";;powershell:$os = Get-CimInstance Win32_OperatingSystem; $used = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB,1); $total = [math]::Round($os.TotalVisibleMemorySize/1MB,1); \"RAM: $used/$total GB\";;powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>&1 | Out-String;;powershell:Get-PSDrive -PSProvider FileSystem | Where Used -gt 0 | Select Name, @{N='Libre(GB)';E={[math]::Round($_.Free/1GB,1)}} | Out-String;;powershell:$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; $up = (Get-Date) - $boot; \"Uptime: $($up.Days)j $($up.Hours)h $($up.Minutes)min\""),
    JarvisCommand("maintenance_totale", "pipeline", "Maintenance totale: corbeille + temp + prefetch + DNS + thumbnails + check updates", [
        "maintenance totale", "grand nettoyage", "maintenance complete",
        "nettoie tout le pc", "gros menage",
    ], "pipeline", "powershell:Clear-RecycleBin -Force -ErrorAction SilentlyContinue; 'Corbeille videe';;powershell:Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; 'Temp nettoye';;powershell:Remove-Item C:\\Windows\\Prefetch\\* -Force -ErrorAction SilentlyContinue; 'Prefetch nettoye';;powershell:ipconfig /flushdns; 'DNS purge';;powershell:Remove-Item \"$env:LOCALAPPDATA\\Microsoft\\Windows\\Explorer\\thumbcache_*\" -Force -ErrorAction SilentlyContinue; 'Thumbnails nettoyes';;powershell:wevtutil el | ForEach-Object { wevtutil cl $_ 2>$null }; 'Logs nettoyes'", confirm=True),
    JarvisCommand("sauvegarde_tous_projets", "pipeline", "Backup tous projets: git commit turbo + carV1 + serveur", [
        "sauvegarde tous les projets", "backup tous les projets",
        "backup global", "sauvegarde globale",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; git add -A; git commit -m 'Backup global auto-JARVIS' --allow-empty 2>&1 | Out-String;;powershell:cd F:\\BUREAU\\carV1; if(Test-Path .git){git add -A; git commit -m 'Backup auto-JARVIS' --allow-empty 2>&1 | Out-String}else{'carV1: pas de repo git'};;powershell:cd F:\\BUREAU\\serveur; if(Test-Path .git){git add -A; git commit -m 'Backup auto-JARVIS' --allow-empty 2>&1 | Out-String}else{'serveur: pas de repo git'}", confirm=True),

    # ══════════════════════════════════════════════════════════════════════
    # INSPIRÉ PRODUCTIVITÉ — Pomodoro, focus, pauses
    # (source: smarthomeinsider.co.uk, workbrighter.co)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("pomodoro_start", "pipeline", "Pomodoro: fermer distractions + focus + VSCode + timer 25min", [
        "pomodoro", "lance un pomodoro", "pomodoro start",
        "25 minutes de focus", "session pomodoro",
    ], "pipeline", f"powershell:Stop-Process -Name 'discord','telegram','slack' -Force -ErrorAction SilentlyContinue; 'Distractions fermees';;{MINIMIZE_ALL};;sleep:1;;app_open:code;;powershell:$end = (Get-Date).AddMinutes(25).ToString('HH:mm'); \"Pomodoro demarre — fin a $end\""),
    JarvisCommand("pomodoro_break", "pipeline", "Pause Pomodoro: minimiser + Spotify + 5 min", [
        "pause pomodoro", "break pomodoro", "pomodoro break",
        "5 minutes de pause", "petite pause pomodoro",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;app_open:spotify;;powershell:$end = (Get-Date).AddMinutes(5).ToString('HH:mm'); \"Pause jusqu'a $end — profite!\""),
    JarvisCommand("mode_entretien", "pipeline", "Mode entretien/call: fermer musique + focus + navigateur", [
        "mode entretien", "j'ai un call", "mode appel",
        "mode interview", "lance le mode call",
    ], "pipeline", f"powershell:Stop-Process -Name 'spotify' -Force -ErrorAction SilentlyContinue;;{MINIMIZE_ALL};;sleep:1;;ms_settings:ms-settings:quiethours;;sleep:1;;app_open:discord"),

    # ══════════════════════════════════════════════════════════════════════
    # MULTI-PLATEFORME — Routines contextuelles avancees
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("mode_recherche", "pipeline", "Mode recherche: Perplexity + Google Scholar + Wikipedia + Claude", [
        "mode recherche", "lance le mode recherche", "mode exploration",
        "session recherche", "mode investigation",
    ], "pipeline", "browser:navigate:https://www.perplexity.ai;;sleep:1;;browser:navigate:https://scholar.google.com;;sleep:1;;browser:navigate:https://fr.wikipedia.org;;sleep:1;;browser:navigate:https://claude.ai"),
    JarvisCommand("mode_youtube", "pipeline", "Mode YouTube: minimiser + plein ecran + YouTube", [
        "mode youtube", "lance youtube en grand", "session youtube",
        "regarde youtube", "youtube plein ecran",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;browser:navigate:https://www.youtube.com;;sleep:2;;hotkey:f11"),
    JarvisCommand("mode_spotify_focus", "pipeline", "Spotify focus: minimiser + Spotify + focus assist", [
        "spotify focus", "musique et concentration", "musique de travail",
        "lance la musique de focus",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;app_open:spotify;;sleep:1;;ms_settings:ms-settings:quiethours"),
    JarvisCommand("ouvre_tout_dev_web", "pipeline", "Dev web complet: VSCode + terminal + localhost + npm docs", [
        "dev web complet", "setup dev web", "lance le dev web",
        "ouvre mon stack web", "mode web dev",
    ], "pipeline", "app_open:code;;sleep:1;;app_open:wt;;sleep:1;;browser:navigate:http://localhost:3000;;sleep:1;;browser:navigate:https://www.npmjs.com"),
    JarvisCommand("mode_twitch_stream", "pipeline", "Mode stream Twitch: OBS + Twitch dashboard + Spotify + chat", [
        "mode twitch", "setup stream twitch", "lance le stream twitch",
        "ouvre mon stream",
    ], "pipeline", "app_open:obs64;;sleep:2;;browser:navigate:https://dashboard.twitch.tv;;sleep:1;;app_open:spotify;;sleep:1;;browser:navigate:https://www.twitch.tv/popout/chat"),
    JarvisCommand("mode_email_productif", "pipeline", "Email productif: Gmail + Calendar + fermer distractions", [
        "mode email", "traite les mails", "session email",
        "mode inbox zero", "gere les mails",
    ], "pipeline", f"powershell:Stop-Process -Name 'discord','telegram','slack' -Force -ErrorAction SilentlyContinue;;{MINIMIZE_ALL};;sleep:1;;browser:navigate:https://mail.google.com;;sleep:1;;browser:navigate:https://calendar.google.com"),

    # ══════════════════════════════════════════════════════════════════════
    # INSPIRÉ GOOGLE HOME / SIRI SHORTCUTS — Contextuels et lifestyle
    # (source: android.gadgethacks.com, glpwireless.com, beebom.com)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("mode_podcast", "pipeline", "Mode podcast: minimiser + Spotify + volume confortable", [
        "mode podcast", "lance un podcast", "ecoute un podcast",
        "session podcast", "podcasts",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;app_open:spotify;;powershell:$w = New-Object -ComObject WScript.Shell; 1..5 | ForEach {{ $w.SendKeys([char]175) }}; 'Volume ajuste'"),
    JarvisCommand("mode_apprentissage", "pipeline", "Mode apprentissage: focus + Udemy/Coursera + notes", [
        "mode apprentissage", "mode formation", "lance une formation",
        "session apprentissage", "mode cours en ligne",
    ], "pipeline", f"ms_settings:ms-settings:quiethours;;sleep:1;;browser:navigate:https://www.udemy.com;;sleep:1;;browser:navigate:https://docs.google.com;;sleep:1;;{MINIMIZE_ALL}"),
    JarvisCommand("mode_news", "pipeline", "Mode news: Google Actualites + Reddit + Twitter", [
        "mode news", "mode actualites", "quoi de neuf dans le monde",
        "lance les news", "session actualites",
    ], "pipeline", "browser:navigate:https://news.google.com;;sleep:1;;browser:navigate:https://www.reddit.com;;sleep:1;;browser:navigate:https://x.com"),
    JarvisCommand("mode_shopping", "pipeline", "Mode shopping: Amazon + Leboncoin + comparateur", [
        "mode shopping", "mode achats", "session shopping",
        "lance le shopping", "ouvre les boutiques",
    ], "pipeline", "browser:navigate:https://www.amazon.fr;;sleep:1;;browser:navigate:https://www.leboncoin.fr;;sleep:1;;browser:navigate:https://www.google.com/shopping"),
    JarvisCommand("mode_design", "pipeline", "Mode design: Figma + Pinterest + Canva", [
        "mode design", "mode graphisme", "lance le mode design",
        "session design", "ouvre les outils design",
    ], "pipeline", "browser:navigate:https://www.figma.com;;sleep:1;;browser:navigate:https://www.pinterest.com;;sleep:1;;browser:navigate:https://www.canva.com"),
    JarvisCommand("mode_musique_decouverte", "pipeline", "Decouverte musicale: Spotify + YouTube Music + SoundCloud", [
        "decouverte musicale", "explore la musique", "nouvelle musique",
        "mode decouverte musique",
    ], "pipeline", "app_open:spotify;;sleep:1;;browser:navigate:https://music.youtube.com;;sleep:1;;browser:navigate:https://soundcloud.com"),
    JarvisCommand("routine_weekend", "pipeline", "Routine weekend: relax + news + musique + Netflix", [
        "routine weekend", "mode weekend", "c'est le weekend",
        "lance le mode weekend", "samedi matin",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;browser:navigate:https://news.google.com;;sleep:1;;app_open:spotify"),
    JarvisCommand("mode_social_complet", "pipeline", "Social complet: Twitter + Reddit + Instagram + LinkedIn + Discord", [
        "mode social complet", "tous les reseaux", "ouvre tout les reseaux sociaux",
        "social media complet", "session reseaux sociaux",
    ], "pipeline", "browser:navigate:https://x.com;;sleep:1;;browser:navigate:https://www.reddit.com;;sleep:1;;browser:navigate:https://www.instagram.com;;sleep:1;;browser:navigate:https://www.linkedin.com;;sleep:1;;app_open:discord"),
    JarvisCommand("mode_planning", "pipeline", "Mode planning: Calendar + Notion + Google Tasks", [
        "mode planning", "mode planification", "organise ma semaine",
        "session planning", "mode agenda",
    ], "pipeline", "browser:navigate:https://calendar.google.com;;sleep:1;;browser:navigate:https://www.notion.so;;sleep:1;;browser:navigate:https://mail.google.com/tasks/canvas"),
    JarvisCommand("mode_brainstorm", "pipeline", "Mode brainstorm: Claude + Notion + timer", [
        "mode brainstorm", "session brainstorm", "lance un brainstorm",
        "mode idees", "reflexion creative",
    ], "pipeline", "browser:navigate:https://claude.ai;;sleep:1;;browser:navigate:https://www.notion.so;;powershell:$end = (Get-Date).AddMinutes(30).ToString('HH:mm'); \"Brainstorm demarre — fin a $end\""),

    # ══════════════════════════════════════════════════════════════════════
    # INSPIRÉ HONGKIAT / WINDOWS AUTOMATION — Nettoyage et gestion
    # (source: hongkiat.com, xda-developers.com, windowsforum.com)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("nettoyage_downloads", "pipeline", "Nettoyer les vieux telechargements (>30 jours)", [
        "nettoie les telechargements", "clean downloads",
        "vide les vieux downloads", "nettoie le dossier telechargements",
    ], "pipeline", "powershell:$count = (Get-ChildItem $env:USERPROFILE\\Downloads -File | Where { $_.LastWriteTime -lt (Get-Date).AddDays(-30) }).Count; Get-ChildItem $env:USERPROFILE\\Downloads -File | Where { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Force -ErrorAction SilentlyContinue; \"$count fichiers de plus de 30 jours supprimes\"", confirm=True),
    JarvisCommand("rapport_reseau_complet", "pipeline", "Rapport reseau: IP + DNS + latence + ports + WiFi", [
        "rapport reseau complet", "rapport reseau", "bilan reseau",
        "diagnostic reseau complet", "etat complet du reseau",
    ], "pipeline", "powershell:(Invoke-RestMethod -Uri 'https://api.ipify.org?format=json' -TimeoutSec 5).ip;;powershell:$dns = Resolve-DnsName google.com -ErrorAction SilentlyContinue; if($dns){'DNS: OK — ' + $dns[0].IPAddress}else{'DNS: ECHEC'};;powershell:$p = Test-Connection 8.8.8.8 -Count 2 -ErrorAction SilentlyContinue; if($p){\"Ping Google: $([math]::Round(($p | Measure-Object -Property Latency -Average).Average))ms\"}else{'Ping: ECHEC'};;powershell:netsh wlan show interfaces | Select-String 'SSID|Signal' | Out-String"),
    JarvisCommand("verif_toutes_mises_a_jour", "pipeline", "Verifier MAJ: Windows Update + pip + npm + ollama", [
        "verifie toutes les mises a jour", "check toutes les updates",
        "mises a jour globales", "tout est a jour",
    ], "pipeline", "powershell:try{$s=New-Object -ComObject Microsoft.Update.Session;$r=$s.CreateUpdateSearcher().Search('IsInstalled=0');\"Windows: $($r.Updates.Count) MAJ en attente\"}catch{'Windows: erreur verification'};;powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' pip list --outdated 2>&1 | Select -First 5 | Out-String;;powershell:npm outdated -g 2>&1 | Select -First 5 | Out-String"),
    JarvisCommand("snapshot_systeme", "pipeline", "Snapshot systeme: sauvegarder toutes les stats dans un fichier", [
        "snapshot systeme", "capture l'etat du systeme",
        "sauvegarde les stats", "photo du systeme",
    ], "pipeline", "powershell:$d = Get-Date -Format 'yyyy-MM-dd_HHmm'; $f = \"F:\\BUREAU\\turbo\\data\\snapshot_$d.txt\"; $os = Get-CimInstance Win32_OperatingSystem; $cpu = (Get-Counter '\\Processor(_Total)\\% Processor Time' -SampleInterval 1 -MaxSamples 1).CounterSamples.CookedValue; $ram = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB,1); $gpu = nvidia-smi --query-gpu=name,temperature.gpu,memory.used --format=csv,noheader 2>&1; \"Date: $d`nCPU: $([math]::Round($cpu))%`nRAM: $ram GB`nGPU: $gpu\" | Out-File $f -Encoding utf8; \"Snapshot sauvegarde: $f\""),

    # ══════════════════════════════════════════════════════════════════════
    # DEVELOPER WORKFLOWS AVANCÉS — Git, tests, features
    # (source: medium.com/@utkarshraj, process.st)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("dev_hotfix", "pipeline", "Hotfix: nouvelle branche + VSCode + tests", [
        "hotfix", "lance un hotfix", "dev hotfix",
        "correction urgente", "bug fix rapide",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; $branch = 'hotfix/' + (Get-Date -Format 'yyyyMMdd-HHmm'); git checkout -b $branch 2>&1 | Out-String;;sleep:1;;app_open:code;;sleep:1;;app_open:wt"),
    JarvisCommand("dev_new_feature", "pipeline", "Nouvelle feature: branche + VSCode + terminal + tests", [
        "nouvelle feature", "dev new feature", "lance une feature",
        "commence une nouvelle fonctionnalite",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; $branch = 'feature/' + (Get-Date -Format 'yyyyMMdd-HHmm'); git checkout -b $branch 2>&1 | Out-String;;sleep:1;;app_open:code;;sleep:1;;app_open:wt;;powershell:cd F:\\BUREAU\\turbo; git status -sb"),
    JarvisCommand("dev_merge_prep", "pipeline", "Preparation merge: lint + tests + git status + diff", [
        "prepare le merge", "pre merge", "merge prep",
        "pret a merger", "verification avant merge",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run ruff check src/ 2>&1 | Select -Last 5 | Out-String;;powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run pytest -x --tb=short 2>&1 | Select -Last 10 | Out-String;;powershell:cd F:\\BUREAU\\turbo; git diff --stat 2>&1 | Out-String"),
    JarvisCommand("dev_database_check", "pipeline", "Check databases: taille + tables de jarvis.db et etoile.db", [
        "check les databases", "verifie les bases de donnees",
        "etat des databases", "database check",
    ], "pipeline", "powershell:$j = (Get-Item 'F:\\BUREAU\\turbo\\data\\jarvis.db' -ErrorAction SilentlyContinue).Length/1MB; \"jarvis.db: $([math]::Round($j,1)) MB\";;powershell:$e = (Get-Item 'F:\\BUREAU\\etoile.db' -ErrorAction SilentlyContinue).Length/1MB; \"etoile.db: $([math]::Round($e,1)) MB\";;powershell:$t = (Get-Item 'F:\\BUREAU\\carV1\\database\\trading_latest.db' -ErrorAction SilentlyContinue).Length/1MB; \"trading.db: $([math]::Round($t,1)) MB\""),
    JarvisCommand("dev_live_coding", "pipeline", "Live coding: OBS + VSCode + terminal + navigateur localhost", [
        "live coding", "mode live code", "lance le live coding",
        "session live code", "code en direct",
    ], "pipeline", "app_open:obs64;;sleep:2;;app_open:code;;sleep:1;;app_open:wt;;sleep:1;;browser:navigate:http://localhost:3000"),
    JarvisCommand("dev_cleanup", "pipeline", "Dev cleanup: git clean + cache Python + node_modules check", [
        "dev cleanup", "nettoie le projet", "clean le code",
        "nettoyage dev", "purge dev",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; $pycache = (Get-ChildItem -Recurse -Directory -Filter '__pycache__').Count; Get-ChildItem -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force; \"$pycache dossiers __pycache__ supprimes\";;powershell:cd F:\\BUREAU\\turbo; $ruff = & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run ruff check src/ --statistics 2>&1 | Select -Last 3 | Out-String; $ruff"),

    # ══════════════════════════════════════════════════════════════════════
    # MULTI-ÉCRANS & PRODUCTIVITÉ AVANCÉE
    # (source: Siri focus modes, Google Home media triggers)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("mode_double_ecran_dev", "pipeline", "Double ecran dev: etendre + VSCode gauche + navigateur droite", [
        "mode double ecran dev", "setup double ecran", "dev deux ecrans",
        "double screen dev",
    ], "pipeline", "powershell:DisplaySwitch.exe /extend;;sleep:2;;app_open:code;;sleep:1;;hotkey:win+left;;sleep:1;;browser:navigate:http://127.0.0.1:8080;;sleep:1;;hotkey:win+right"),
    JarvisCommand("mode_presentation_zoom", "pipeline", "Presentation Zoom/Teams: fermer distractions + dupliquer ecran + app", [
        "mode presentation zoom", "setup presentation teams",
        "je fais une presentation", "lance la visio",
    ], "pipeline", f"powershell:Stop-Process -Name 'spotify','discord' -Force -ErrorAction SilentlyContinue;;{MINIMIZE_ALL};;sleep:1;;powershell:DisplaySwitch.exe /clone;;sleep:2;;app_open:teams"),
    JarvisCommand("mode_dashboard_complet", "pipeline", "Dashboard complet: JARVIS + TradingView + cluster + n8n", [
        "dashboard complet", "ouvre tous les dashboards",
        "mode tableau de bord", "tous les dashboards",
    ], "pipeline", "browser:navigate:http://127.0.0.1:8080;;sleep:1;;browser:navigate:https://www.tradingview.com;;sleep:1;;browser:navigate:http://127.0.0.1:5678;;sleep:1;;browser:navigate:http://192.168.1.26:1234"),
    JarvisCommand("ferme_tout_sauf_code", "pipeline", "Fermer tout sauf VSCode et terminal", [
        "ferme tout sauf le code", "garde juste vscode",
        "nettoie sauf l'editeur", "focus sur le code",
    ], "pipeline", f"powershell:Stop-Process -Name 'chrome','msedge','discord','telegram','slack','spotify','obs64' -Force -ErrorAction SilentlyContinue; 'Apps fermees';;sleep:1;;powershell:Get-Process code -ErrorAction SilentlyContinue | Select -First 1 | ForEach {{ 'VSCode actif' }}"),
    JarvisCommand("mode_detox_digital", "pipeline", "Detox digitale: fermer TOUT + verrouiller + night light", [
        "detox digitale", "mode detox", "deconnexion totale",
        "digital detox", "arrete tout les ecrans",
    ], "pipeline", f"powershell:Stop-Process -Name 'chrome','msedge','discord','telegram','slack','spotify','code','obs64' -Force -ErrorAction SilentlyContinue;;sleep:1;;{MINIMIZE_ALL};;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;powershell:rundll32.exe user32.dll,LockWorkStation", confirm=True),
    JarvisCommand("mode_musique_travail", "pipeline", "Musique de travail: Spotify + focus assist (pas de distractions)", [
        "musique de travail", "met de la musique pour bosser",
        "musique focus", "ambiance travail",
    ], "pipeline", "app_open:spotify;;sleep:1;;ms_settings:ms-settings:quiethours"),
    JarvisCommand("check_tout_rapide", "pipeline", "Check rapide tout: cluster + GPU + RAM + disques en 1 commande", [
        "check tout rapide", "etat rapide de tout", "resume systeme",
        "quick check", "tout va bien",
    ], "pipeline", "powershell:$m2 = try{(Invoke-WebRequest -Uri 'http://192.168.1.26:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; $ol1 = try{(Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; \"Cluster — M2: $(if($m2 -eq 200){'OK'}else{'OFF'}) | OL1: $(if($ol1 -eq 200){'OK'}else{'OFF'})\";;powershell:$os = Get-CimInstance Win32_OperatingSystem; $ram = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB,1); $total = [math]::Round($os.TotalVisibleMemorySize/1MB,1); \"RAM: $ram/$total GB\";;powershell:nvidia-smi --query-gpu=temperature.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # MODE — Hackathon, Data Science, DevOps
    # (source: turbogeek.co.uk, PDQ, Windows 11 automation)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("mode_hackathon", "pipeline", "Mode hackathon: timer + VSCode + terminal + GitHub + Claude", [
        "mode hackathon", "lance le hackathon", "setup hackathon",
        "session hackathon", "mode competition",
    ], "pipeline", "app_open:code;;sleep:1;;app_open:wt;;sleep:1;;browser:navigate:https://github.com;;sleep:1;;browser:navigate:https://claude.ai;;powershell:$end = (Get-Date).AddHours(4).ToString('HH:mm'); \"Hackathon demarre — deadline $end\""),
    JarvisCommand("mode_data_science", "pipeline", "Mode data science: Jupyter + Kaggle + docs Python + terminal", [
        "mode data science", "mode datascience", "lance jupyter",
        "session data science", "mode machine learning",
    ], "pipeline", "app_open:wt;;sleep:1;;browser:navigate:https://www.kaggle.com;;sleep:1;;browser:navigate:https://docs.python.org/3/;;sleep:1;;browser:navigate:https://scikit-learn.org"),
    JarvisCommand("mode_devops", "pipeline", "Mode DevOps: Docker + dashboard + terminal + GitHub Actions", [
        "mode devops", "mode ops", "lance le mode devops",
        "setup devops", "mode infrastructure",
    ], "pipeline", "app_open:wt;;sleep:1;;browser:navigate:http://127.0.0.1:8080;;sleep:1;;browser:navigate:https://github.com;;powershell:docker ps --format 'table {{.Names}}\\t{{.Status}}' 2>&1 | Out-String"),
    JarvisCommand("mode_securite_audit", "pipeline", "Mode audit securite: Defender + ports + connexions + terminal", [
        "mode securite", "mode audit securite", "lance un audit de securite",
        "session securite", "mode pentest",
    ], "pipeline", "app_open:wt;;sleep:1;;powershell:Get-MpComputerStatus | Select AntivirusEnabled, RealTimeProtectionEnabled | Out-String;;powershell:Get-NetTCPConnection -State Listen | Group-Object LocalPort | Select @{N='Port';E={$_.Name}}, Count | Sort Port | Select -First 15 | Out-String;;powershell:Get-NetTCPConnection -State Established | Where RemoteAddress -notmatch '^(127|10|192\\.168|0\\.)' | Select RemoteAddress, RemotePort -Unique | Select -First 10 | Out-String"),
    JarvisCommand("mode_trading_scalp", "pipeline", "Mode scalping: TradingView multi-timeframe + MEXC + terminal", [
        "mode scalping", "mode scalp", "trading scalp",
        "session scalping", "mode day trading",
    ], "pipeline", "browser:navigate:https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT;;sleep:1;;browser:navigate:https://www.mexc.com/exchange/BTC_USDT;;sleep:1;;browser:navigate:https://www.coingecko.com/en/coins/bitcoin;;sleep:1;;app_open:wt"),

    # ══════════════════════════════════════════════════════════════════════
    # ROUTINE — Midi, urgence, meeting
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("routine_midi", "pipeline", "Routine midi: pause + news + trading check rapide", [
        "routine midi", "pause midi", "lunch break",
        "pause dejeuner", "c'est midi",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;browser:navigate:https://news.google.com;;sleep:1;;browser:navigate:https://www.tradingview.com;;sleep:1;;app_open:spotify"),
    JarvisCommand("routine_nuit_urgence", "pipeline", "Mode urgence nuit: tout fermer + sauvegarder + veille immediate", [
        "urgence nuit", "extinction d'urgence", "dors maintenant",
        "veille immediatement", "shutdown rapide",
    ], "pipeline", f"powershell:cd F:\\BUREAU\\turbo; git add -A; git commit -m 'Emergency save JARVIS' --allow-empty 2>&1 | Out-String;;sleep:1;;{MINIMIZE_ALL};;powershell:rundll32.exe user32.dll,LockWorkStation;;sleep:2;;powershell:rundll32.exe powrprof.dll,SetSuspendState 0,1,0", confirm=True),
    JarvisCommand("setup_meeting_rapide", "pipeline", "Meeting rapide: micro check + fermer musique + Teams/Discord", [
        "meeting rapide", "setup meeting", "prepare un call rapide",
        "je dois appeler", "visio rapide",
    ], "pipeline", f"powershell:Stop-Process -Name 'spotify' -Force -ErrorAction SilentlyContinue;;{MINIMIZE_ALL};;sleep:1;;ms_settings:ms-settings:quiethours;;sleep:1;;app_open:discord"),

    # ══════════════════════════════════════════════════════════════════════
    # VEILLE TECH & FREELANCE
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("mode_veille_tech", "pipeline", "Veille tech: Hacker News + dev.to + Product Hunt + Reddit/programming", [
        "veille tech", "mode veille technologique", "quoi de neuf en tech",
        "session veille", "news dev",
    ], "pipeline", "browser:navigate:https://news.ycombinator.com;;sleep:1;;browser:navigate:https://dev.to;;sleep:1;;browser:navigate:https://www.producthunt.com;;sleep:1;;browser:navigate:https://www.reddit.com/r/programming"),
    JarvisCommand("mode_freelance", "pipeline", "Mode freelance: factures + mails + calendar + Notion", [
        "mode freelance", "mode client", "session freelance",
        "mode travail client", "setup freelance",
    ], "pipeline", "browser:navigate:https://mail.google.com;;sleep:1;;browser:navigate:https://calendar.google.com;;sleep:1;;browser:navigate:https://www.notion.so;;sleep:1;;browser:navigate:https://docs.google.com"),
    JarvisCommand("mode_debug_production", "pipeline", "Debug prod: logs + monitoring + terminal + dashboard", [
        "debug production", "mode debug prod", "urgence production",
        "incident prod", "probleme en prod",
    ], "pipeline", "app_open:wt;;sleep:1;;browser:navigate:http://127.0.0.1:8080;;sleep:1;;powershell:Get-WinEvent -FilterHashtable @{LogName='Application';Level=2} -MaxEvents 10 -ErrorAction SilentlyContinue | Select TimeCreated, Message | Out-String -Width 150;;powershell:nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used --format=csv,noheader"),

    # ══════════════════════════════════════════════════════════════════════
    # APPRENTISSAGE & CODING CHALLENGES
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("mode_apprentissage_code", "pipeline", "Mode apprentissage code: LeetCode + VSCode + docs + timer", [
        "mode apprentissage code", "session leetcode", "mode kata",
        "exercices de code", "mode coding challenge",
    ], "pipeline", "browser:navigate:https://leetcode.com;;sleep:1;;app_open:code;;sleep:1;;browser:navigate:https://docs.python.org/3/;;powershell:$end = (Get-Date).AddMinutes(45).ToString('HH:mm'); \"Session code demarre — fin a $end\""),
    JarvisCommand("mode_tutorial", "pipeline", "Mode tutorial: YouTube + VSCode + terminal + docs", [
        "mode tutorial", "mode tuto", "suis un tuto",
        "session tutorial", "mode formation video",
    ], "pipeline", "browser:navigate:https://www.youtube.com;;sleep:1;;app_open:code;;sleep:1;;app_open:wt;;sleep:1;;browser:navigate:https://developer.mozilla.org"),

    # ══════════════════════════════════════════════════════════════════════
    # BACKUP & MAINTENANCE AVANCÉE
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("mode_backup_total", "pipeline", "Backup total: tous les projets + snapshot systeme + rapport", [
        "backup total", "sauvegarde totale", "backup complet",
        "sauvegarde tout absolument", "full backup",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; git add -A; git commit -m 'Full backup auto-JARVIS' --allow-empty 2>&1 | Out-String;;powershell:cd F:\\BUREAU\\carV1; if(Test-Path .git){git add -A; git commit -m 'Backup auto-JARVIS' --allow-empty 2>&1 | Out-String};;powershell:cd F:\\BUREAU\\serveur; if(Test-Path .git){git add -A; git commit -m 'Backup auto-JARVIS' --allow-empty 2>&1 | Out-String};;powershell:$d = Get-Date -Format 'yyyy-MM-dd_HHmm'; $os = Get-CimInstance Win32_OperatingSystem; $ram = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB,1); \"Backup complet OK — RAM: $ram GB — $d\"", confirm=True),
    JarvisCommand("ouvre_dashboards_trading", "pipeline", "Tous les dashboards trading: TV + MEXC + CoinGecko + CoinMarketCap + DexScreener", [
        "tous les dashboards trading", "ouvre tout le trading",
        "full trading view", "tous les sites trading",
        "dashboard trading complet",
    ], "pipeline", "browser:navigate:https://www.tradingview.com;;sleep:1;;browser:navigate:https://www.mexc.com/exchange/BTC_USDT;;sleep:1;;browser:navigate:https://www.coingecko.com;;sleep:1;;browser:navigate:https://coinmarketcap.com;;sleep:1;;browser:navigate:https://dexscreener.com"),

    # ══════════════════════════════════════════════════════════════════════
    # CREATIVE & MEDIA
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("mode_photo_edit", "pipeline", "Mode retouche photo: Paint + navigateur refs + Pinterest", [
        "mode photo", "mode retouche", "retouche photo",
        "mode edition photo", "session photo",
    ], "pipeline", "app_open:mspaint;;sleep:1;;browser:navigate:https://www.pinterest.com;;sleep:1;;browser:navigate:https://www.canva.com"),
    JarvisCommand("mode_writing", "pipeline", "Mode ecriture: Google Docs + focus + nuit + Claude aide", [
        "mode ecriture", "mode redaction", "session ecriture",
        "lance le mode ecriture", "ecris quelque chose",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;ms_settings:ms-settings:quiethours;;sleep:1;;browser:navigate:https://docs.google.com;;sleep:1;;browser:navigate:https://claude.ai"),
    JarvisCommand("mode_video_marathon", "pipeline", "Mode marathon video: Netflix + nuit + plein ecran + snacks time", [
        "mode marathon", "marathon video", "binge watching",
        "session netflix", "mode series",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;browser:navigate:https://www.netflix.com;;sleep:2;;hotkey:f11;;powershell:\"Mode marathon active — bon visionnage!\""),

    # ══════════════════════════════════════════════════════════════════════
    # COMET — Nouveaux sites via Comet
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("ouvre_kaggle_comet", "pipeline", "Ouvrir Kaggle dans Comet", [
        "ouvre kaggle sur comet", "kaggle comet",
        "va sur kaggle comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://www.kaggle.com'"),
    JarvisCommand("ouvre_arxiv_comet", "pipeline", "Ouvrir arXiv dans Comet", [
        "ouvre arxiv sur comet", "arxiv comet",
        "va sur arxiv comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://arxiv.org'"),
    JarvisCommand("ouvre_notion_comet", "pipeline", "Ouvrir Notion dans Comet", [
        "ouvre notion sur comet", "notion comet",
        "va sur notion comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://www.notion.so'"),
    JarvisCommand("ouvre_stackoverflow_comet", "pipeline", "Ouvrir Stack Overflow dans Comet", [
        "ouvre stackoverflow sur comet", "stackoverflow comet",
        "va sur stackoverflow comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://stackoverflow.com'"),
    JarvisCommand("ouvre_medium_comet", "pipeline", "Ouvrir Medium dans Comet", [
        "ouvre medium sur comet", "medium comet",
        "va sur medium comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://medium.com'"),
    JarvisCommand("ouvre_gmail_comet", "pipeline", "Ouvrir Gmail dans Comet", [
        "ouvre gmail sur comet", "gmail comet",
        "va sur gmail comet", "mails comet",
    ], "pipeline", f"powershell:Start-Process '{COMET}' -ArgumentList 'https://mail.google.com'"),

    # ══════════════════════════════════════════════════════════════════════
    # INSPIRÉ STREAM DECK — Action Flows multi-actions (one-click)
    # (source: vsdinside.com, asianefficiency.com, xda-developers.com)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("mode_go_live", "pipeline", "Go Live: OBS + Twitch dashboard + Spotify + chat overlay", [
        "go live", "lance le stream maintenant", "on est en direct",
        "mode live", "demarre le live",
    ], "pipeline", "app_open:obs64;;sleep:2;;browser:navigate:https://dashboard.twitch.tv;;sleep:1;;app_open:spotify;;sleep:1;;browser:navigate:https://www.twitch.tv/popout/chat;;powershell:\"LIVE — Stream demarre!\""),
    JarvisCommand("mode_end_stream", "pipeline", "End stream: fermer OBS + Twitch + recap", [
        "arrete le stream", "fin du live", "end stream",
        "coupe le stream", "stop live",
    ], "pipeline", "powershell:Stop-Process -Name 'obs64' -Force -ErrorAction SilentlyContinue; 'OBS ferme';;sleep:1;;powershell:\"Stream termine — GG!\""),
    JarvisCommand("mode_daily_report", "pipeline", "Daily report: git log + stats code + dashboard + Google Sheets", [
        "rapport quotidien", "daily report", "genere le rapport",
        "rapport du jour", "stats du jour",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; 'Commits du jour:'; git log --since='today' --oneline 2>&1 | Out-String;;powershell:cd F:\\BUREAU\\turbo; $py = (Get-ChildItem src/*.py -Recurse | Get-Content | Measure-Object -Line).Lines; \"Code: $py lignes Python\";;browser:navigate:http://127.0.0.1:8080;;sleep:1;;browser:navigate:https://sheets.google.com"),
    JarvisCommand("mode_api_test", "pipeline", "Mode API testing: terminal + navigateur API docs + outils test", [
        "mode api test", "teste les api", "mode postman",
        "session api testing", "debug api",
    ], "pipeline", "app_open:wt;;sleep:1;;browser:navigate:http://127.0.0.1:8080;;sleep:1;;browser:navigate:https://httpie.io/app;;sleep:1;;browser:navigate:https://reqbin.com"),
    JarvisCommand("mode_conference_full", "pipeline", "Conference: fermer distractions + Teams + micro + focus assist", [
        "mode conference", "mode visio complete", "setup conference",
        "lance la visio complete", "reunion complete",
    ], "pipeline", f"powershell:Stop-Process -Name 'spotify','obs64' -Force -ErrorAction SilentlyContinue;;{MINIMIZE_ALL};;sleep:1;;ms_settings:ms-settings:quiethours;;sleep:1;;app_open:teams;;sleep:1;;powershell:\"Conference prete — micro et cam actifs\""),
    JarvisCommand("mode_end_meeting", "pipeline", "Fin meeting: fermer Teams/Discord/Zoom + restaurer musique", [
        "fin du meeting", "fin de la reunion", "end meeting",
        "ferme la visio", "reunion terminee",
    ], "pipeline", "powershell:Stop-Process -Name 'teams','zoom' -Force -ErrorAction SilentlyContinue; 'Apps reunion fermees';;sleep:1;;app_open:spotify;;powershell:\"Reunion terminee — retour au travail\""),
    JarvisCommand("mode_home_theater", "pipeline", "Home theater: minimiser + nuit + volume max + Disney+/Netflix plein ecran", [
        "mode home theater", "mode cinema maison", "soiree film maison",
        "home cinema", "mode salle de cinema",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;powershell:$w = New-Object -ComObject WScript.Shell; 1..10 | ForEach {{ $w.SendKeys([char]175) }}; 'Volume monte';;browser:navigate:https://www.netflix.com;;sleep:2;;hotkey:f11"),

    # ══════════════════════════════════════════════════════════════════════
    # DEV WORKFLOWS AVANCÉS — Refactoring, testing, deploy
    # (source: Raycast workflows, Alfred dev patterns)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("mode_refactoring", "pipeline", "Mode refactoring: VSCode + ruff + tests + git diff", [
        "mode refactoring", "session refactoring", "lance le refactoring",
        "mode refacto", "nettoie le code",
    ], "pipeline", "app_open:code;;sleep:1;;powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run ruff check src/ --statistics 2>&1 | Select -Last 5 | Out-String;;powershell:cd F:\\BUREAU\\turbo; git diff --stat 2>&1 | Out-String"),
    JarvisCommand("mode_testing_complet", "pipeline", "Mode tests complet: pytest + coverage + lint + terminal", [
        "mode testing complet", "lance tous les tests", "session testing",
        "mode tests", "teste tout le projet",
    ], "pipeline", "app_open:wt;;sleep:1;;powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run pytest -v --tb=short 2>&1 | Select -Last 20 | Out-String;;powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run ruff check src/ 2>&1 | Select -Last 5 | Out-String"),
    JarvisCommand("mode_deploy_checklist", "pipeline", "Checklist deploy: tests + lint + status git + build check", [
        "checklist deploy", "mode deploy", "pret pour le deploiement",
        "verification deploiement", "deploy checklist",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run pytest -x --tb=short 2>&1 | Select -Last 5 | Out-String;;powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run ruff check src/ 2>&1 | Select -Last 5 | Out-String;;powershell:cd F:\\BUREAU\\turbo; git status -sb;;powershell:cd F:\\BUREAU\\turbo; git log --oneline -3"),
    JarvisCommand("mode_documentation_code", "pipeline", "Mode doc code: VSCode + readthedocs + terminal + Notion", [
        "mode documentation code", "documente le code", "session docs code",
        "mode javadoc", "ecris la doc",
    ], "pipeline", "app_open:code;;sleep:1;;browser:navigate:https://www.notion.so;;sleep:1;;app_open:wt;;sleep:1;;browser:navigate:https://docs.python.org/3/"),
    JarvisCommand("mode_open_source", "pipeline", "Mode open source: GitHub issues + PRs + VSCode + terminal", [
        "mode open source", "mode contribution", "session open source",
        "contribue a un projet", "mode oss",
    ], "pipeline", "browser:navigate:https://github.com/pulls;;sleep:1;;browser:navigate:https://github.com/issues;;sleep:1;;app_open:code;;sleep:1;;app_open:wt"),
    JarvisCommand("mode_side_project", "pipeline", "Mode side project: VSCode + navigateur + terminal + timer 2h", [
        "mode side project", "mode projet perso", "lance le side project",
        "session projet perso", "mode hobby code",
    ], "pipeline", "app_open:code;;sleep:1;;app_open:wt;;sleep:1;;browser:navigate:https://github.com;;powershell:$end = (Get-Date).AddHours(2).ToString('HH:mm'); \"Side project demarre — fin a $end\""),

    # ══════════════════════════════════════════════════════════════════════
    # SYSADMIN — Workflows systeme avances
    # (source: turbogeek.co.uk, PDQ, wholesalebackup.com)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("mode_admin_sys", "pipeline", "Mode sysadmin: terminal + Event Viewer + services + ports", [
        "mode sysadmin", "mode administrateur", "mode admin systeme",
        "session admin", "mode it",
    ], "pipeline", "app_open:wt;;sleep:1;;powershell:Get-Service | Where Status -eq 'Stopped' | Where StartType -eq 'Automatic' | Select -First 5 Name, Status | Out-String;;powershell:Get-NetTCPConnection -State Listen | Group-Object LocalPort | Select @{N='Port';E={$_.Name}}, Count | Sort Port | Select -First 10 | Out-String;;powershell:Get-WinEvent -FilterHashtable @{LogName='System';Level=2} -MaxEvents 5 -ErrorAction SilentlyContinue | Select TimeCreated, Message | Out-String -Width 150"),
    JarvisCommand("mode_reseau_complet", "pipeline", "Mode reseau complet: ping + DNS + WiFi + ports + IP", [
        "mode reseau complet", "diagnostic reseau total", "analyse reseau complete",
        "tout le reseau", "reseau en detail",
    ], "pipeline", "powershell:$p = Test-Connection 8.8.8.8 -Count 2 -ErrorAction SilentlyContinue; if($p){\"Ping Google: $([math]::Round(($p | Measure-Object -Property Latency -Average).Average))ms\"}else{'Ping: ECHEC'};;powershell:Resolve-DnsName google.com -ErrorAction SilentlyContinue | Select -First 2 | Out-String;;powershell:netsh wlan show interfaces | Select-String 'SSID|Signal|Debit' | Out-String;;powershell:(Invoke-RestMethod -Uri 'https://api.ipify.org?format=json' -TimeoutSec 5).ip;;powershell:Get-NetTCPConnection -State Listen | Group-Object LocalPort | Select @{N='Port';E={$_.Name}}, Count | Sort Port | Select -First 10 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # LIFESTYLE — Finance, voyage, apéritif
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("mode_finance", "pipeline", "Mode finance: banque + budget + trading + calculatrice", [
        "mode finance", "mode budget", "gere mes finances",
        "session finance", "mode comptabilite",
    ], "pipeline", "browser:navigate:https://www.google.com/finance;;sleep:1;;browser:navigate:https://sheets.google.com;;sleep:1;;browser:navigate:https://www.tradingview.com;;sleep:1;;app_open:calc"),
    JarvisCommand("mode_voyage", "pipeline", "Mode voyage: Google Flights + Maps + Booking + meteo", [
        "mode voyage", "planifie un voyage", "mode vacances",
        "session voyage", "organise le voyage",
    ], "pipeline", "browser:navigate:https://www.google.com/flights;;sleep:1;;browser:navigate:https://maps.google.com;;sleep:1;;browser:navigate:https://www.booking.com;;sleep:1;;browser:navigate:https://www.google.com/search?q=meteo"),
    JarvisCommand("routine_aperitif", "pipeline", "Routine apero: fermer le travail + musique + ambiance", [
        "routine apero", "aperitif", "c'est l'heure de l'apero",
        "mode apero", "apero time",
    ], "pipeline", f"powershell:Stop-Process -Name 'code','wt' -Force -ErrorAction SilentlyContinue;;{MINIMIZE_ALL};;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;app_open:spotify;;powershell:\"Apero time! Bon moment!\""),
    JarvisCommand("mode_cuisine", "pipeline", "Mode cuisine: YouTube recettes + timer + Spotify musique", [
        "mode cuisine", "je fais a manger", "mode recette",
        "session cuisine", "lance une recette",
    ], "pipeline", "browser:navigate:https://www.youtube.com/results?search_query=recette+facile+rapide;;sleep:1;;app_open:spotify;;powershell:$end = (Get-Date).AddMinutes(45).ToString('HH:mm'); \"Cuisine demarre — pret vers $end\""),
    JarvisCommand("mode_meditation", "pipeline", "Mode meditation: minimiser + nuit + sons relaxants", [
        "mode meditation", "medite", "mode calme",
        "session meditation", "mode zen total",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;browser:navigate:https://www.youtube.com/results?search_query=meditation+guidee+10+minutes;;sleep:2;;hotkey:f11"),

    # ══════════════════════════════════════════════════════════════════════
    # REMOTE WORK & COLLABORATION
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("mode_pair_programming", "pipeline", "Pair programming: VSCode Live Share + terminal + Discord", [
        "mode pair programming", "pair prog", "session pair programming",
        "code a deux", "mode collaboration code",
    ], "pipeline", "app_open:code;;sleep:1;;app_open:discord;;sleep:1;;app_open:wt;;sleep:1;;browser:navigate:https://github.com"),
    JarvisCommand("mode_retrospective", "pipeline", "Retrospective: bilan semaine + git stats + Notion + Calendar", [
        "mode retro", "retrospective", "bilan de la semaine",
        "session retro", "mode retrospective",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; 'Commits semaine:'; git log --since='last monday' --oneline 2>&1 | Out-String;;browser:navigate:https://www.notion.so;;sleep:1;;browser:navigate:https://calendar.google.com;;sleep:1;;browser:navigate:http://127.0.0.1:8080"),
    JarvisCommand("mode_demo", "pipeline", "Mode demo: dupliquer ecran + navigateur + dashboard + presentation", [
        "mode demo", "prepare la demo", "session demo",
        "lance la demo", "mode demonstration",
    ], "pipeline", "powershell:DisplaySwitch.exe /clone;;sleep:2;;browser:navigate:http://127.0.0.1:8080;;sleep:1;;browser:navigate:https://github.com;;sleep:1;;powershell:\"Demo prete — go!\""),
    JarvisCommand("mode_scrum_master", "pipeline", "Mode Scrum: board + standup + Calendar + timer", [
        "mode scrum", "mode scrum master", "session scrum",
        "lance le daily", "mode agile",
    ], "pipeline", "browser:navigate:https://github.com/projects;;sleep:1;;browser:navigate:https://calendar.google.com;;sleep:1;;powershell:cd F:\\BUREAU\\turbo; git log --since='yesterday' --oneline 2>&1 | Out-String;;powershell:$end = (Get-Date).AddMinutes(15).ToString('HH:mm'); \"Standup demarre — max $end\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 1 — RÉVEIL & DÉMARRAGE JOURNÉE
    # Scénario: "Jarvis, demarre la journee" → boot complet sans toucher la souris
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_reveil_complet", "pipeline", "Simulation reveil: cluster + mails + trading + news + dashboard + café", [
        "demarre la journee complete", "simulation reveil", "boot complet",
        "lance tout pour la journee", "reveil total",
        "initialise ma journee",
    ], "pipeline", "powershell:powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c; 'Mode performance active';;app_open:lmstudio;;sleep:2;;browser:navigate:http://127.0.0.1:8080;;sleep:1;;browser:navigate:https://mail.google.com;;sleep:1;;browser:navigate:https://www.tradingview.com;;sleep:1;;browser:navigate:https://news.google.com;;powershell:$h = (Get-Date).ToString('HH:mm'); \"Bonjour! Il est $h — tout est pret\""),
    JarvisCommand("sim_check_matinal", "pipeline", "Check matinal rapide: cluster health + GPU + RAM + trading", [
        "check matinal", "tout va bien ce matin", "etat du matin",
        "check rapide matinal", "comment va le systeme",
    ], "pipeline", "powershell:$m2 = try{(Invoke-WebRequest -Uri 'http://192.168.1.26:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; $ol1 = try{(Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; \"Cluster — M2: $(if($m2 -eq 200){'OK'}else{'OFF'}) | OL1: $(if($ol1 -eq 200){'OK'}else{'OFF'})\";;powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used --format=csv,noheader,nounits 2>&1 | Out-String;;powershell:$os = Get-CimInstance Win32_OperatingSystem; $ram = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB,1); $total = [math]::Round($os.TotalVisibleMemorySize/1MB,1); \"RAM: $ram/$total GB\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 2 — SESSION DE TRAVAIL DEV COMPLÈTE
    # Scénario: Workflow dev du début à la fin sans souris
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_start_coding", "pipeline", "Demarrer une session de code: git pull + VSCode + terminal + snap", [
        "je commence a coder", "start coding session", "session de code",
        "lance le dev", "je vais coder",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; git pull --rebase 2>&1 | Out-String;;app_open:code;;sleep:2;;hotkey:win+left;;sleep:1;;app_open:wt;;sleep:1;;hotkey:win+right;;powershell:cd F:\\BUREAU\\turbo; git status -sb"),
    JarvisCommand("sim_code_and_test", "pipeline", "Code + test: lancer les tests + lint + afficher résultats", [
        "teste mon code", "code and test", "verifie tout mon code",
        "lint et test", "validation du code",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run ruff check src/ 2>&1 | Select -Last 5 | Out-String;;powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run pytest -x --tb=short 2>&1 | Select -Last 10 | Out-String;;powershell:cd F:\\BUREAU\\turbo; git diff --stat 2>&1 | Out-String"),
    JarvisCommand("sim_commit_and_push", "pipeline", "Commiter et pusher le code", [
        "commit et push", "sauvegarde et pousse", "envoie le code",
        "git push tout", "publie le code",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; git add -A; git status -sb;;powershell:cd F:\\BUREAU\\turbo; git commit -m 'Update auto-JARVIS' 2>&1 | Out-String;;powershell:cd F:\\BUREAU\\turbo; git push 2>&1 | Out-String", confirm=True),
    JarvisCommand("sim_debug_session", "pipeline", "Session debug: devtools + terminal + logs + monitoring", [
        "session debug complete", "je debug", "mode debug complet",
        "lance le debugging", "debug total",
    ], "pipeline", "app_open:code;;sleep:1;;hotkey:ctrl+`;;sleep:1;;hotkey:f12;;powershell:Get-WinEvent -FilterHashtable @{LogName='Application';Level=2} -MaxEvents 5 -ErrorAction SilentlyContinue | Select TimeCreated, Message | Out-String -Width 150"),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 3 — RÉUNION VIRTUELLE (avant, pendant, après)
    # Scénario: Préparer → Rejoindre → Présenter → Terminer
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_avant_reunion", "pipeline", "Avant reunion: fermer distractions + notes + agenda + micro check", [
        "prepare la reunion", "avant le meeting", "pre reunion",
        "setup avant la visio", "bientot en reunion",
    ], "pipeline", f"powershell:Stop-Process -Name 'spotify','obs64' -Force -ErrorAction SilentlyContinue;;{MINIMIZE_ALL};;sleep:1;;ms_settings:ms-settings:quiethours;;sleep:1;;browser:navigate:https://calendar.google.com;;sleep:1;;browser:navigate:https://docs.google.com"),
    JarvisCommand("sim_rejoindre_reunion", "pipeline", "Rejoindre: ouvrir Discord/Teams + partage ecran pret", [
        "rejoins la reunion", "join meeting", "entre en reunion",
        "lance la visio maintenant", "rejoins le call",
    ], "pipeline", "app_open:discord;;sleep:2;;hotkey:win+p;;powershell:\"En reunion — partage ecran disponible via Win+P\""),
    JarvisCommand("sim_presenter_ecran", "pipeline", "Presenter: dupliquer ecran + ouvrir dashboard + plein ecran", [
        "presente mon ecran", "partage ecran presentation",
        "lance la presentation maintenant", "montre mon ecran",
    ], "pipeline", "powershell:DisplaySwitch.exe /clone;;sleep:2;;browser:navigate:http://127.0.0.1:8080;;sleep:2;;hotkey:f11;;powershell:\"Presentation en cours\""),
    JarvisCommand("sim_apres_reunion", "pipeline", "Après reunion: fermer visio + restaurer musique + reprendre le dev", [
        "reunion terminee reprends", "apres le meeting", "fin de la visio reprends",
        "reviens au travail apres reunion", "post meeting",
    ], "pipeline", "powershell:Stop-Process -Name 'teams','zoom','discord' -Force -ErrorAction SilentlyContinue; 'Visio fermee';;sleep:1;;app_open:spotify;;sleep:1;;app_open:code;;sleep:1;;app_open:wt;;powershell:\"Reunion terminee — retour au dev\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 4 — PAUSE & DÉTENTE SANS SOURIS
    # Scénario: Transition travail → pause → retour au travail
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_pause_cafe", "pipeline", "Pause cafe: minimiser + verrouiller + 10 min", [
        "pause cafe", "je prends un cafe", "coffee break",
        "5 minutes de pause cafe", "petite pause",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;powershell:rundll32.exe user32.dll,LockWorkStation;;powershell:\"Pause cafe — reviens frais!\""),
    JarvisCommand("sim_pause_longue", "pipeline", "Pause longue: save + musique + nuit + verrouiller", [
        "longue pause", "grande pause", "je fais une grande pause",
        "pause dejeuner complete", "pause d'une heure",
    ], "pipeline", f"powershell:cd F:\\BUREAU\\turbo; git add -A; git commit -m 'Auto-save pause JARVIS' --allow-empty 2>&1 | Out-String;;{MINIMIZE_ALL};;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;app_open:spotify;;sleep:1;;powershell:rundll32.exe user32.dll,LockWorkStation"),
    JarvisCommand("sim_retour_pause", "pipeline", "Retour de pause: performance + rouvrir le dev + check cluster", [
        "je suis de retour", "retour de pause", "fin de la pause",
        "reprends le travail", "je reviens de pause",
    ], "pipeline", "powershell:powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c;;app_open:code;;sleep:1;;app_open:wt;;sleep:1;;powershell:$m2 = try{(Invoke-WebRequest -Uri 'http://192.168.1.26:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; \"Cluster M2: $(if($m2 -eq 200){'OK'}else{'OFF'}) — pret a bosser\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 5 — RECHERCHE & APPRENTISSAGE INTENSIF
    # Scénario: Session de recherche complète multi-sources
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_recherche_intensive", "pipeline", "Recherche intensive: Claude + Perplexity + Scholar + Wikipedia + notes", [
        "recherche intensive", "session recherche complete",
        "lance une grosse recherche", "mode investigation profonde",
    ], "pipeline", "browser:navigate:https://claude.ai;;sleep:1;;browser:navigate:https://www.perplexity.ai;;sleep:1;;browser:navigate:https://scholar.google.com;;sleep:1;;browser:navigate:https://fr.wikipedia.org;;sleep:1;;browser:navigate:https://docs.google.com;;powershell:\"5 sources ouvertes — bonne recherche!\""),
    JarvisCommand("sim_formation_video", "pipeline", "Formation video: YouTube + notes + VSCode + timer 2h", [
        "formation video complete", "session formation", "apprends en video",
        "cours video complet", "tuto complet",
    ], "pipeline", f"ms_settings:ms-settings:quiethours;;sleep:1;;{MINIMIZE_ALL};;sleep:1;;browser:navigate:https://www.youtube.com;;sleep:1;;app_open:code;;sleep:1;;browser:navigate:https://docs.google.com;;powershell:$end = (Get-Date).AddHours(2).ToString('HH:mm'); \"Formation jusqu'a $end\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 6 — TRADING COMPLET (analyse → execution → monitoring)
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_analyse_trading", "pipeline", "Analyse trading: multi-timeframe + indicateurs + news crypto", [
        "analyse trading complete", "session analyse trading",
        "analyse les marches", "etude des charts",
    ], "pipeline", "browser:navigate:https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT;;sleep:1;;browser:navigate:https://www.coingecko.com;;sleep:1;;browser:navigate:https://coinmarketcap.com;;sleep:1;;browser:navigate:https://www.coindesk.com;;powershell:\"Analyse en cours — 4 sources ouvertes\""),
    JarvisCommand("sim_execution_trading", "pipeline", "Execution trading: MEXC + TradingView + terminal signaux", [
        "execute le trading", "passe les ordres", "session execution trades",
        "trading actif", "lance le trading actif",
    ], "pipeline", "browser:navigate:https://www.mexc.com/exchange/BTC_USDT;;sleep:1;;browser:navigate:https://www.tradingview.com;;sleep:1;;app_open:wt;;powershell:\"Mode trading actif — attention aux positions\""),
    JarvisCommand("sim_monitoring_positions", "pipeline", "Monitoring positions: MEXC + alertes + DexScreener", [
        "surveille mes positions", "monitoring trading", "check mes trades",
        "comment vont mes positions", "etat de mes trades",
    ], "pipeline", "browser:navigate:https://www.mexc.com/exchange/BTC_USDT;;sleep:1;;browser:navigate:https://dexscreener.com;;sleep:1;;browser:navigate:https://www.tradingview.com;;powershell:\"Monitoring actif — surveille tes positions\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 7 — GESTION MULTI-FENÊTRES VOCALE
    # Scénario: Organiser son espace de travail 100% à la voix
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_layout_dev_split", "pipeline", "Layout dev split: VSCode gauche + navigateur droite", [
        "layout dev split", "code a gauche navigateur a droite",
        "split dev layout", "organise mon ecran pour coder",
    ], "pipeline", "app_open:code;;sleep:2;;hotkey:win+left;;sleep:1;;browser:navigate:http://127.0.0.1:8080;;sleep:1;;hotkey:win+right;;powershell:\"Layout: VSCode gauche | Dashboard droite\""),
    JarvisCommand("sim_layout_triple", "pipeline", "Layout triple: code + terminal + navigateur en quadrants", [
        "layout triple", "trois fenetres organisees", "quadrant layout",
        "organise trois apps", "layout travail",
    ], "pipeline", "app_open:code;;sleep:2;;hotkey:win+left;;hotkey:win+up;;sleep:1;;app_open:wt;;sleep:1;;hotkey:win+left;;hotkey:win+down;;sleep:1;;browser:navigate:http://127.0.0.1:8080;;sleep:1;;hotkey:win+right;;powershell:\"Triple layout organise\""),
    JarvisCommand("sim_tout_fermer_propre", "pipeline", "Fermeture propre: sauvegarder + fermer apps + minimiser + night light", [
        "ferme tout proprement", "clean shutdown apps", "termine proprement",
        "arrete tout et range", "finis proprement",
    ], "pipeline", f"powershell:cd F:\\BUREAU\\turbo; git add -A; git commit -m 'Clean close JARVIS' --allow-empty 2>&1 | Out-String;;powershell:Stop-Process -Name 'code','wt','obs64','discord','telegram' -Force -ErrorAction SilentlyContinue; 'Apps dev fermees';;sleep:1;;{MINIMIZE_ALL};;powershell:Start-Process ms-settings:nightlight;;\"Tout ferme proprement\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 8 — FIN DE JOURNÉE COMPLÈTE
    # Scénario: Sauvegarder → Rapport → Fermer → Night mode → Verrouiller
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_fin_journee_complete", "pipeline", "Fin de journee complete: backup + stats + nuit + economie + verrouiller", [
        "fin de journee complete", "termine la journee proprement",
        "bonne nuit complete", "arrete tout pour la nuit",
        "shutdown de fin de journee",
    ], "pipeline", f"powershell:cd F:\\BUREAU\\turbo; git add -A; git commit -m 'Fin de journee auto-JARVIS' --allow-empty 2>&1 | Out-String;;powershell:cd F:\\BUREAU\\turbo; $c = (git log --since='today' --oneline | Measure-Object).Count; \"$c commits aujourd'hui\";;powershell:Stop-Process -Name 'code','wt','obs64','discord','telegram','slack','chrome','msedge' -Force -ErrorAction SilentlyContinue; 'Toutes les apps fermees';;sleep:1;;{MINIMIZE_ALL};;powershell:Start-Process ms-settings:nightlight;;sleep:1;;powershell:powercfg /setactive a1841308-3541-4fab-bc81-f71556f20b4a; 'Mode economie active';;powershell:rundll32.exe user32.dll,LockWorkStation", confirm=True),
    JarvisCommand("sim_weekend_mode", "pipeline", "Mode weekend: fermer tout le dev + musique + news + Netflix", [
        "mode weekend complet", "c'est le weekend enfin",
        "plus de travail weekend", "transition weekend",
    ], "pipeline", f"powershell:cd F:\\BUREAU\\turbo; git add -A; git commit -m 'Weekend save JARVIS' --allow-empty 2>&1 | Out-String;;powershell:Stop-Process -Name 'code','wt','lmstudio' -Force -ErrorAction SilentlyContinue; 'Dev ferme';;sleep:1;;{MINIMIZE_ALL};;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;app_open:spotify;;sleep:1;;browser:navigate:https://www.netflix.com;;powershell:\"Bon weekend!\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 9 — URGENCES & DÉPANNAGE
    # Scénario: Réagir rapidement à un problème sans souris
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_urgence_gpu", "pipeline", "Urgence GPU: check temperatures + vram + killprocess gourmand", [
        "urgence gpu", "les gpu chauffent trop", "gpu en surchauffe",
        "sauve les gpu", "urgence temperature",
    ], "pipeline", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits | ForEach-Object { $f = $_ -split ','; \"$($f[0].Trim()): $($f[1].Trim())C GPU $($f[2].Trim())% VRAM $($f[3].Trim())/$($f[4].Trim()) MB\" };;powershell:Get-Process | Sort WS -Descending | Select -First 5 Name, @{N='RAM(MB)';E={[math]::Round($_.WS/1MB)}} | Format-Table -AutoSize | Out-String;;powershell:\"Check GPU termine — tue les processus gourmands si necessaire\""),
    JarvisCommand("sim_urgence_reseau", "pipeline", "Urgence reseau: flush DNS + reset adapter + ping + diagnostic", [
        "urgence reseau", "internet ne marche plus", "plus de connexion",
        "repare le reseau", "debug internet",
    ], "pipeline", "powershell:ipconfig /flushdns; 'DNS purge';;powershell:$p = Test-Connection 8.8.8.8 -Count 2 -ErrorAction SilentlyContinue; if($p){\"Ping Google: OK ($([math]::Round(($p | Measure-Object -Property Latency -Average).Average))ms)\"}else{'Ping Google: ECHEC'};;powershell:$d = Resolve-DnsName google.com -ErrorAction SilentlyContinue; if($d){'DNS: OK'}else{'DNS: ECHEC'};;powershell:netsh wlan show interfaces | Select-String 'SSID|Signal|Etat' | Out-String"),
    JarvisCommand("sim_urgence_espace", "pipeline", "Urgence espace disque: taille disques + temp + downloads + cache", [
        "urgence espace disque", "plus de place", "disque plein",
        "libere de l'espace", "urgence stockage",
    ], "pipeline", "powershell:Get-PSDrive -PSProvider FileSystem | Where Used -gt 0 | Select Name, @{N='Libre(GB)';E={[math]::Round($_.Free/1GB,1)}} | Out-String;;powershell:$t = (Get-ChildItem $env:TEMP -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum/1MB; \"TEMP: $([math]::Round($t)) MB\";;powershell:$d = (Get-ChildItem $env:USERPROFILE\\Downloads -File -ErrorAction SilentlyContinue | Where { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Measure-Object Length -Sum).Sum/1MB; \"Vieux downloads: $([math]::Round($d)) MB\";;powershell:$c = (Get-ChildItem \"$env:LOCALAPPDATA\\Google\\Chrome\\User Data\\Default\\Cache\" -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum/1MB; \"Cache Chrome: $([math]::Round($c)) MB\""),
    JarvisCommand("sim_urgence_performance", "pipeline", "Urgence performance: CPU + RAM + processus zombies + services en echec", [
        "urgence performance", "le pc rame", "tout est lent",
        "pourquoi c'est lent", "debug performance",
    ], "pipeline", "powershell:$cpu = (Get-Counter '\\Processor(_Total)\\% Processor Time' -SampleInterval 1 -MaxSamples 1).CounterSamples.CookedValue; \"CPU: $([math]::Round($cpu))%\";;powershell:$os = Get-CimInstance Win32_OperatingSystem; $used = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB,1); $total = [math]::Round($os.TotalVisibleMemorySize/1MB,1); \"RAM: $used/$total GB ($([math]::Round($used/$total*100))%)\";;powershell:Get-Process | Where { $_.Responding -eq $false } | Select Name, Id | Out-String;;powershell:Get-Process | Sort CPU -Descending | Select -First 5 Name, @{N='CPU(s)';E={[math]::Round($_.CPU,1)}}, @{N='RAM(MB)';E={[math]::Round($_.WS/1MB)}} | Format-Table -AutoSize | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 10 — MULTITÂCHE & PRODUCTIVITÉ AVANCÉE
    # Scénario: Jongler entre plusieurs activités sans souris
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_multitask_dev_trading", "pipeline", "Multitask dev+trading: split code/charts + cluster monitoring", [
        "multitask dev et trading", "code et trade en meme temps",
        "dev plus trading", "double activite",
    ], "pipeline", "app_open:code;;sleep:2;;hotkey:win+left;;sleep:1;;browser:navigate:https://www.tradingview.com;;sleep:1;;hotkey:win+right;;sleep:1;;powershell:$m2 = try{(Invoke-WebRequest -Uri 'http://192.168.1.26:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; \"Cluster M2: $(if($m2 -eq 200){'OK'}else{'OFF'})\""),
    JarvisCommand("sim_multitask_email_code", "pipeline", "Multitask email+code: mails a gauche + VSCode a droite", [
        "mails et code", "email et dev", "reponds aux mails en codant",
        "mail plus code", "inbox et vscode",
    ], "pipeline", "browser:navigate:https://mail.google.com;;sleep:2;;hotkey:win+left;;sleep:1;;app_open:code;;sleep:1;;hotkey:win+right;;powershell:\"Split: Gmail gauche | VSCode droite\""),
    JarvisCommand("sim_focus_extreme", "pipeline", "Focus extreme: fermer TOUT sauf VSCode + mute + night + timer 3h", [
        "focus extreme", "concentration absolue", "zero distraction",
        "mode monk", "plus rien ne me derange",
    ], "pipeline", f"powershell:Stop-Process -Name 'chrome','msedge','discord','telegram','slack','spotify','obs64' -Force -ErrorAction SilentlyContinue;;{MINIMIZE_ALL};;sleep:1;;ms_settings:ms-settings:quiethours;;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;app_open:code;;powershell:$end = (Get-Date).AddHours(3).ToString('HH:mm'); \"Focus extreme jusqu'a $end — ZERO distraction\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 11 — ENTERTAINMENT & LOISIRS COMPLETS
    # Scénario: Transition travail → loisirs sans toucher la souris
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_soiree_gaming", "pipeline", "Soiree gaming: fermer dev + performance + Steam + Game Bar", [
        "soiree gaming", "session jeu video", "mode gamer complet",
        "lance une soiree jeu", "gaming time",
    ], "pipeline", f"powershell:Stop-Process -Name 'code','wt','lmstudio' -Force -ErrorAction SilentlyContinue;;{MINIMIZE_ALL};;sleep:1;;powershell:powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c;;sleep:1;;app_open:steam;;sleep:3;;hotkey:win+g;;powershell:\"Mode gaming active — GG!\""),
    JarvisCommand("sim_soiree_film", "pipeline", "Soiree film: fermer tout + nuit + volume + Netflix plein ecran", [
        "soiree film complete", "on regarde un film", "movie night",
        "mode cinema total", "prépare le film",
    ], "pipeline", f"powershell:Stop-Process -Name 'code','wt','discord','lmstudio' -Force -ErrorAction SilentlyContinue;;{MINIMIZE_ALL};;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;powershell:$w = New-Object -ComObject WScript.Shell; 1..10 | ForEach {{ $w.SendKeys([char]175) }}; 'Volume monte';;browser:navigate:https://www.netflix.com;;sleep:3;;hotkey:f11;;powershell:\"Bon film!\""),
    JarvisCommand("sim_soiree_musique", "pipeline", "Soiree musique: minimiser + Spotify + ambiance + volume", [
        "soiree musique", "ambiance musicale complete", "music night",
        "met de la bonne musique", "soiree son",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;powershell:Start-Process ms-settings:nightlight;;sleep:1;;app_open:spotify;;sleep:1;;powershell:$w = New-Object -ComObject WScript.Shell; 1..7 | ForEach {{ $w.SendKeys([char]175) }}; 'Volume ajuste';;powershell:\"Soiree musique — profite!\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 12 — MAINTENANCE PLANIFIÉE HEBDO
    # Scénario: Nettoyage/maintenance systeme complet une fois par semaine
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_maintenance_hebdo", "pipeline", "Maintenance hebdo: temp + cache + corbeille + DNS + logs + updates", [
        "maintenance hebdomadaire", "grand nettoyage de la semaine",
        "nettoyage hebdo", "maintenance weekly",
    ], "pipeline", "powershell:Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; 'Temp nettoye';;powershell:Clear-RecycleBin -Force -ErrorAction SilentlyContinue; 'Corbeille videe';;powershell:Remove-Item \"$env:LOCALAPPDATA\\Microsoft\\Windows\\Explorer\\thumbcache_*\" -Force -ErrorAction SilentlyContinue; 'Thumbnails nettoyes';;powershell:ipconfig /flushdns; 'DNS purge';;powershell:Remove-Item \"$env:LOCALAPPDATA\\Google\\Chrome\\User Data\\Default\\Cache\\*\" -Recurse -Force -ErrorAction SilentlyContinue; 'Cache Chrome nettoye';;powershell:cd F:\\BUREAU\\turbo; $pycache = (Get-ChildItem -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue).Count; Get-ChildItem -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force; \"$pycache __pycache__ supprimes\";;powershell:\"Maintenance hebdo terminee!\"", confirm=True),
    JarvisCommand("sim_backup_hebdo", "pipeline", "Backup hebdo: tous les projets + snapshot + stats", [
        "backup hebdomadaire", "sauvegarde de la semaine",
        "backup weekly", "sauvegarde hebdo",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; git add -A; git commit -m 'Weekly backup JARVIS' --allow-empty 2>&1 | Out-String;;powershell:cd F:\\BUREAU\\turbo; $c = (git log --since='1 week ago' --oneline | Measure-Object).Count; $py = (Get-ChildItem src/*.py -Recurse | Get-Content | Measure-Object -Line).Lines; \"Semaine: $c commits | Code: $py lignes\";;powershell:$d = Get-Date -Format 'yyyy-MM-dd_HHmm'; $os = Get-CimInstance Win32_OperatingSystem; $ram = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB,1); \"Snapshot $d — RAM: $ram GB\"", confirm=True),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 13 — DIAGNOSTIC RÉSEAU COMPLET
    # Scénario: Investiguer un problème réseau de A à Z
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_diag_reseau_complet", "pipeline", "Diagnostic reseau: ping + DNS + traceroute + ports + IP publique", [
        "diagnostic reseau complet", "probleme internet complet",
        "analyse le reseau a fond", "debug reseau total",
    ], "pipeline", "powershell:ping 8.8.8.8 -n 3 | Select-String 'Moyenne|Average|100%' | Out-String;;powershell:ipconfig /flushdns; nslookup google.com 2>&1 | Select-String 'Address' | Out-String;;powershell:tracert -d -h 10 8.8.8.8 2>&1 | Select -Last 5 | Out-String;;powershell:Get-NetTCPConnection -State Listen | Group-Object LocalPort | Select @{N='Port';E={$_.Name}}, @{N='Process';E={(Get-Process -Id ($_.Group[0].OwningProcess) -ErrorAction SilentlyContinue).Name}} | Sort Port | Select -First 10 | Out-String;;powershell:(Invoke-RestMethod -Uri 'https://api.ipify.org?format=json' -TimeoutSec 5).ip;;powershell:\"Diagnostic reseau termine\""),
    JarvisCommand("sim_diag_wifi", "pipeline", "Diagnostic WiFi: signal + SSID + vitesse + DNS + latence", [
        "probleme wifi complet", "diagnostic wifi", "le wifi deconne",
        "analyse le wifi",
    ], "pipeline", "powershell:netsh wlan show interfaces | Select-String 'SSID|Signal|Debit|Etat' | Out-String;;powershell:ping 192.168.1.1 -n 3 | Select-String 'Moyenne|Average' | Out-String;;powershell:ping 8.8.8.8 -n 3 | Select-String 'Moyenne|Average' | Out-String;;powershell:\"Diagnostic WiFi termine\""),
    JarvisCommand("sim_diag_cluster_deep", "pipeline", "Diagnostic cluster profond: ping + models + GPU + latence", [
        "diagnostic cluster profond", "debug cluster complet",
        "le cluster repond plus", "analyse cluster deep",
    ], "pipeline", "powershell:$m2 = try{(Invoke-WebRequest -Uri 'http://192.168.1.26:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; $ol1 = try{(Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; $m3 = try{(Invoke-WebRequest -Uri 'http://192.168.1.113:1234/api/v1/models' -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; \"M2: $(if($m2-eq 200){'OK'}else{'OFFLINE'}) | OL1: $(if($ol1-eq 200){'OK'}else{'OFFLINE'}) | M3: $(if($m3-eq 200){'OK'}else{'OFFLINE'})\";;powershell:nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits | ForEach-Object { $f=$_-split','; \"$($f[0].Trim()): $($f[1].Trim())C | GPU$($f[2].Trim())% | VRAM $($f[3].Trim())/$($f[4].Trim())MB\" };;powershell:(Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/ps' -TimeoutSec 5).models | ForEach-Object { \"$($_.name) | VRAM: $([math]::Round($_.size_vram/1GB,2))GB\" };;powershell:\"Diagnostic cluster termine\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 14 — AUDIT SÉCURITÉ EXPRESS
    # Scénario: Vérification sécurité rapide du système
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_audit_securite", "pipeline", "Audit securite: ports + connexions + autorun + defender + RDP + admin", [
        "audit securite complet", "check securite", "scan securite total",
        "est ce que je suis securise", "verification securite",
    ], "pipeline", "powershell:Get-NetTCPConnection -State Listen | Group-Object LocalPort | Select @{N='Port';E={$_.Name}}, @{N='Process';E={(Get-Process -Id ($_.Group[0].OwningProcess) -ErrorAction SilentlyContinue).Name}}, Count | Sort Port | Select -First 10 | Out-String;;powershell:Get-NetTCPConnection -State Established | Where RemoteAddress -notmatch '^(127|10|192\\.168|0\\.)' | Select RemoteAddress, RemotePort, @{N='Process';E={(Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).Name}} | Sort RemoteAddress -Unique | Select -First 10 | Out-String;;powershell:$rdp = (Get-ItemProperty 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server').fDenyTSConnections; \"RDP: $(if($rdp -eq 0){'ACTIVE - ATTENTION'}else{'Desactive (OK)'})\";;powershell:$mp = Get-MpComputerStatus; \"Defender: $(if($mp.RealTimeProtectionEnabled){'OK'}else{'DESACTIVE!'}) | Signatures: $($mp.AntivirusSignatureLastUpdated.ToString('dd/MM'))\";;powershell:Get-LocalGroupMember -Group Administrators -ErrorAction SilentlyContinue | Select Name | Out-String;;powershell:\"Audit securite termine\""),
    JarvisCommand("sim_hardening_check", "pipeline", "Check durcissement: firewall + UAC + BitLocker + updates", [
        "check hardening", "durcissement systeme", "securite avancee",
        "est ce que le systeme est blinde",
    ], "pipeline", "powershell:Get-NetFirewallProfile | Select Name, Enabled | Out-String;;powershell:$uac = (Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System').EnableLUA; \"UAC: $(if($uac){'Active'}else{'DESACTIVE!'})\";;powershell:try{$bl = Get-BitLockerVolume -ErrorAction Stop; $bl | Select MountPoint, ProtectionStatus | Out-String}catch{'BitLocker: Non disponible ou non configure'};;powershell:try{$s = New-Object -ComObject Microsoft.Update.Session; $u = $s.CreateUpdateSearcher(); $r = $u.Search('IsInstalled=0'); \"Updates en attente: $($r.Updates.Count)\"}catch{'Verification updates impossible'};;powershell:\"Check hardening termine\""),
    JarvisCommand("sim_audit_mots_de_passe", "pipeline", "Audit mots de passe: politique + comptes + expiration", [
        "audit mots de passe", "politique password", "securite comptes",
        "check passwords",
    ], "pipeline", "powershell:net accounts 2>&1 | Out-String;;powershell:Get-LocalUser | Select Name, Enabled, PasswordRequired, PasswordLastSet | Format-Table -AutoSize | Out-String;;powershell:\"Audit mots de passe termine\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 15 — SETUP NOUVEAU PROJET
    # Scénario: Initialiser un nouveau projet de dev de A à Z
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_new_project_python", "pipeline", "Nouveau projet Python: dossier + venv + git + VSCode", [
        "nouveau projet python", "init projet python", "cree un projet python",
        "setup python project",
    ], "pipeline", "powershell:$name = 'new_project_' + (Get-Date -Format 'yyyyMMdd'); $path = \"F:\\BUREAU\\$name\"; New-Item $path -ItemType Directory -Force | Out-Null; cd $path; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' init 2>&1 | Out-String; \"Projet cree: $path\";;powershell:cd \"F:\\BUREAU\\$((Get-ChildItem F:\\BUREAU -Directory | Sort LastWriteTime -Descending | Select -First 1).Name)\"; git init 2>&1 | Out-String;;app_open:code;;sleep:2;;powershell:\"Projet Python initialise et ouvert dans VSCode\""),
    JarvisCommand("sim_new_project_node", "pipeline", "Nouveau projet Node.js: dossier + npm init + git + VSCode", [
        "nouveau projet node", "init projet javascript", "cree un projet node",
        "setup node project",
    ], "pipeline", "powershell:$name = 'node_project_' + (Get-Date -Format 'yyyyMMdd'); $path = \"F:\\BUREAU\\$name\"; New-Item $path -ItemType Directory -Force | Out-Null; cd $path; npm init -y 2>&1 | Out-String; \"Projet cree: $path\";;powershell:cd \"F:\\BUREAU\\$((Get-ChildItem F:\\BUREAU -Directory | Sort LastWriteTime -Descending | Select -First 1).Name)\"; git init 2>&1 | Out-String;;app_open:code;;sleep:2;;powershell:\"Projet Node.js initialise et ouvert dans VSCode\""),
    JarvisCommand("sim_clone_and_setup", "pipeline", "Cloner un repo et l'ouvrir: git clone + VSCode + install deps", [
        "clone et setup {repo}", "git clone et ouvre {repo}",
        "clone le projet {repo}", "setup repo {repo}",
    ], "pipeline", "powershell:cd F:\\BUREAU; git clone '{repo}' 2>&1 | Out-String;;sleep:2;;app_open:code;;sleep:2;;powershell:\"Repo clone et ouvert dans VSCode\"", ["repo"]),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 16 — GESTION FICHIERS MASSIVE
    # Scénario: Organiser, nettoyer, archiver des fichiers en masse
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_grand_nettoyage_disque", "pipeline", "Grand nettoyage: temp + cache + corbeille + thumbnails + crash dumps + pycache", [
        "grand nettoyage du disque", "mega clean", "libere de l'espace",
        "nettoyage massif", "purge totale",
    ], "pipeline", "powershell:$s1 = (Get-ChildItem $env:TEMP -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum/1MB; Remove-Item \"$env:TEMP\\*\" -Recurse -Force -ErrorAction SilentlyContinue; \"TEMP: $([math]::Round($s1)) MB liberes\";;powershell:Remove-Item \"$env:LOCALAPPDATA\\Google\\Chrome\\User Data\\Default\\Cache\\*\" -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item \"$env:LOCALAPPDATA\\Microsoft\\Edge\\User Data\\Default\\Cache\\*\" -Recurse -Force -ErrorAction SilentlyContinue; 'Caches navigateur nettoyes';;powershell:Clear-RecycleBin -Force -ErrorAction SilentlyContinue; 'Corbeille videe';;powershell:Remove-Item \"$env:LOCALAPPDATA\\Microsoft\\Windows\\Explorer\\thumbcache_*\" -Force -ErrorAction SilentlyContinue; 'Thumbnails nettoyes';;powershell:Remove-Item \"$env:LOCALAPPDATA\\CrashDumps\\*\" -Force -ErrorAction SilentlyContinue; 'Crash dumps supprimes';;powershell:Get-ChildItem F:\\BUREAU -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force; 'Pycache nettoyes';;powershell:$f = (Get-PSDrive F).Free/1GB; $c = (Get-PSDrive C).Free/1GB; \"Espace libre — C: $([math]::Round($c,1)) GB | F: $([math]::Round($f,1)) GB\"", confirm=True),
    JarvisCommand("sim_archive_vieux_projets", "pipeline", "Archiver les projets non modifies depuis 30 jours", [
        "archive les vieux projets", "zip les anciens projets",
        "range les projets inactifs", "archivage projets",
    ], "pipeline", "powershell:$old = Get-ChildItem F:\\BUREAU -Directory | Where { $_.Name -ne 'turbo' -and $_.LastWriteTime -lt (Get-Date).AddDays(-30) }; if($old){ $old | ForEach-Object { \"Inactif: $($_.Name) (modifie: $($_.LastWriteTime.ToString('dd/MM')))\"}; \"$($old.Count) projets inactifs detectes\" }else{ 'Tous les projets sont recents' }"),
    JarvisCommand("sim_scan_fichiers_orphelins", "pipeline", "Scanner fichiers orphelins: gros fichiers + doublons + anciens", [
        "scan fichiers orphelins", "nettoyage intelligent", "analyse les fichiers",
        "quoi supprimer",
    ], "pipeline", "powershell:\"=== Fichiers > 100MB ===\"; Get-ChildItem F:\\BUREAU -Recurse -File -ErrorAction SilentlyContinue | Where Length -gt 100MB | Sort Length -Desc | Select -First 5 @{N='MB';E={[math]::Round($_.Length/1MB)}}, FullName | Out-String;;powershell:\"=== Doublons par nom ===\"; Get-ChildItem F:\\BUREAU -Recurse -File -ErrorAction SilentlyContinue | Group Name | Where Count -gt 2 | Sort Count -Desc | Select -First 10 Name, Count | Out-String;;powershell:\"=== Fichiers > 1 an ===\"; Get-ChildItem F:\\BUREAU -Recurse -File -ErrorAction SilentlyContinue | Where { $_.LastWriteTime -lt (Get-Date).AddYears(-1) } | Measure-Object | Select @{N='Fichiers anciens (>1 an)';E={$_.Count}} | Out-String;;powershell:\"Scan fichiers termine\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 17 — POWERTOYS WORKFLOWS
    # Scénario: Enchainer les outils PowerToys pour être productif
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_design_review", "pipeline", "Design review: screen ruler + color picker + text extractor + screenshot", [
        "review design complet", "analyse visuelle", "design review",
        "mesure et capture", "inspection ui",
    ], "pipeline", "hotkey:win+shift+m;;sleep:3;;hotkey:win+shift+c;;sleep:3;;hotkey:win+shift+t;;sleep:3;;hotkey:win+shift+s;;powershell:\"Design review complete — outils fermes\""),
    JarvisCommand("sim_layout_productif", "pipeline", "Layout productif: FancyZones + always on top + snap windows", [
        "layout productif", "arrange mon ecran", "organise mes fenetres",
        "setup fenetres productif",
    ], "pipeline", "app_open:code;;sleep:2;;hotkey:win+left;;sleep:1;;browser:navigate:http://127.0.0.1:8080;;sleep:2;;hotkey:win+right;;sleep:1;;hotkey:win+ctrl+t;;powershell:\"Layout productif: VSCode gauche | Dashboard droite (epingle)\""),
    JarvisCommand("sim_copier_texte_image", "pipeline", "Copier du texte depuis une image: OCR + clipboard + notification", [
        "copie le texte de l'image", "ocr et copie", "lis l'image",
        "texte depuis screenshot",
    ], "pipeline", "hotkey:win+shift+t;;sleep:5;;powershell:$clip = Get-Clipboard -ErrorAction SilentlyContinue; if($clip){\"Texte copie: $($clip.Substring(0, [math]::Min($clip.Length, 100)))...\"}else{'Aucun texte capture'}"),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 18 — DATABASE MANAGEMENT
    # Scénario: Gestion des bases de données du projet
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_db_health_check", "pipeline", "Health check bases: jarvis.db + etoile.db + taille + integrite", [
        "health check des bases", "check les db", "bases de donnees ok",
        "diagnostic bases de donnees",
    ], "pipeline", "powershell:$j = (Get-Item F:\\BUREAU\\turbo\\data\\jarvis.db -ErrorAction SilentlyContinue).Length/1KB; $e = (Get-Item F:\\BUREAU\\etoile.db -ErrorAction SilentlyContinue).Length/1KB; \"jarvis.db: $([math]::Round($j)) KB | etoile.db: $([math]::Round($e)) KB\";;powershell:sqlite3 F:\\BUREAU\\turbo\\data\\jarvis.db 'PRAGMA integrity_check;' 2>&1 | Out-String;;powershell:sqlite3 F:\\BUREAU\\etoile.db 'PRAGMA integrity_check;' 2>&1 | Out-String;;powershell:sqlite3 F:\\BUREAU\\etoile.db 'SELECT category, COUNT(*) as c FROM map GROUP BY category ORDER BY c DESC;' 2>&1 | Out-String;;powershell:\"Health check DB termine\""),
    JarvisCommand("sim_db_backup", "pipeline", "Backup toutes les bases de donnees", [
        "backup les bases", "sauvegarde les db", "copie les bases de donnees",
        "backup database",
    ], "pipeline", "powershell:$d = Get-Date -Format 'yyyy-MM-dd_HHmm'; Copy-Item F:\\BUREAU\\turbo\\data\\jarvis.db \"F:\\BUREAU\\turbo\\data\\jarvis_backup_$d.db\" -Force; Copy-Item F:\\BUREAU\\etoile.db \"F:\\BUREAU\\etoile_backup_$d.db\" -Force; \"Backup DB: jarvis_backup_$d.db + etoile_backup_$d.db\""),
    JarvisCommand("sim_db_stats", "pipeline", "Statistiques des bases: tables, lignes, taille par table", [
        "stats des bases", "metriques db", "combien dans les bases",
        "taille des tables",
    ], "pipeline", "powershell:sqlite3 F:\\BUREAU\\turbo\\data\\jarvis.db '.tables' 2>&1 | Out-String;;powershell:sqlite3 F:\\BUREAU\\turbo\\data\\jarvis.db 'SELECT \"skills\" as tbl, COUNT(*) as rows FROM skills UNION ALL SELECT \"actions\", COUNT(*) FROM actions UNION ALL SELECT \"historique\", COUNT(*) FROM historique;' 2>&1 | Out-String;;powershell:sqlite3 F:\\BUREAU\\etoile.db 'SELECT \"map\" as tbl, COUNT(*) as rows FROM map UNION ALL SELECT \"agents\", COUNT(*) FROM agents UNION ALL SELECT \"memories\", COUNT(*) FROM memories;' 2>&1 | Out-String;;powershell:\"Stats DB terminees\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 19 — DOCKER WORKFLOWS
    # Scénario: Gestion de conteneurs Docker en vocal
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_docker_full_status", "pipeline", "Status Docker complet: containers + images + volumes + espace", [
        "status docker complet", "etat complet docker", "docker overview",
        "resume docker",
    ], "pipeline", "powershell:docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}' 2>&1 | Out-String;;powershell:docker images --format 'table {{.Repository}}\\t{{.Tag}}\\t{{.Size}}' 2>&1 | Out-String;;powershell:docker system df 2>&1 | Out-String;;powershell:\"Status Docker complet\""),
    JarvisCommand("sim_docker_cleanup", "pipeline", "Nettoyage Docker: prune containers + images + volumes + build cache", [
        "nettoie docker a fond", "docker cleanup total", "purge docker complete",
        "libere espace docker",
    ], "pipeline", "powershell:docker container prune -f 2>&1 | Out-String;;powershell:docker image prune -a -f 2>&1 | Out-String;;powershell:docker volume prune -f 2>&1 | Out-String;;powershell:docker builder prune -f 2>&1 | Out-String;;powershell:docker system df 2>&1 | Out-String;;powershell:\"Docker nettoye a fond\"", confirm=True),
    JarvisCommand("sim_docker_restart_all", "pipeline", "Redemarrer tous les conteneurs Docker", [
        "redemarre docker", "restart all containers", "relance les conteneurs",
        "docker restart tout",
    ], "pipeline", "powershell:docker restart $(docker ps -q) 2>&1 | Out-String;;sleep:3;;powershell:docker ps --format 'table {{.Names}}\\t{{.Status}}' 2>&1 | Out-String;;powershell:\"Tous les conteneurs redemarres\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 20 — SESSION CODE REVIEW
    # Scénario: Préparer et conduire une code review
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_code_review_prep", "pipeline", "Preparer une code review: git diff + VSCode + browser GitHub", [
        "prepare la code review", "session review", "revue de code",
        "je vais review du code",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; git log --oneline -5 2>&1 | Out-String;;powershell:cd F:\\BUREAU\\turbo; git diff --stat HEAD~3 2>&1 | Out-String;;app_open:code;;sleep:2;;browser:navigate:https://github.com/Turbo31150/turbo/pulls;;powershell:\"Code review prete — diff affiche\""),
    JarvisCommand("sim_code_review_split", "pipeline", "Layout code review: VSCode gauche + GitHub droite", [
        "layout review", "split code review", "cote a cote review",
        "ecran review",
    ], "pipeline", "app_open:code;;sleep:2;;hotkey:win+left;;sleep:1;;browser:navigate:https://github.com/Turbo31150/turbo;;sleep:2;;hotkey:win+right;;powershell:\"Layout review: VSCode | GitHub\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 21 — SESSION APPRENTISSAGE
    # Scénario: Apprendre un nouveau sujet de dev
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_learn_topic", "pipeline", "Session apprentissage: YouTube + docs + notes", [
        "session apprentissage {topic}", "je veux apprendre {topic}",
        "cours sur {topic}", "tuto {topic}",
    ], "pipeline", "browser:navigate:https://www.youtube.com/results?search_query={topic}+tutorial;;sleep:2;;browser:navigate:https://www.google.com/search?q={topic}+documentation;;sleep:1;;app_open:code;;sleep:1;;powershell:\"Session apprentissage {topic} prete\"", ["topic"]),
    JarvisCommand("sim_learn_python", "pipeline", "Apprentissage Python: docs + exercices + REPL", [
        "apprends moi python", "session python", "tuto python",
        "cours python",
    ], "pipeline", "browser:navigate:https://docs.python.org/3/tutorial/;;sleep:2;;browser:navigate:https://www.freecodecamp.org/learn/scientific-computing-with-python/;;sleep:1;;app_open:wt;;sleep:1;;powershell:\"Session Python ouverte — docs + exercices + terminal\""),
    JarvisCommand("sim_learn_rust", "pipeline", "Apprentissage Rust: The Book + playground", [
        "apprends moi rust", "session rust", "tuto rust",
        "cours rust",
    ], "pipeline", "browser:navigate:https://doc.rust-lang.org/book/;;sleep:2;;browser:navigate:https://play.rust-lang.org/;;sleep:1;;powershell:\"Session Rust ouverte — The Book + Playground\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 22 — MULTI-ÉCRAN WORKFLOWS
    # Scénario: Configurations multi-fenêtres avancées
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_layout_4_quadrants", "pipeline", "Layout 4 quadrants: Code + Terminal + Browser + Dashboard", [
        "4 quadrants", "layout quatre fenetres", "quatre ecrans",
        "quad split", "quatre zones",
    ], "pipeline", "app_open:code;;sleep:2;;hotkey:win+left;;hotkey:win+up;;sleep:1;;app_open:wt;;sleep:1;;hotkey:win+left;;hotkey:win+down;;sleep:1;;browser:navigate:http://127.0.0.1:8080;;sleep:2;;hotkey:win+right;;hotkey:win+up;;sleep:1;;app_open:spotify;;sleep:1;;hotkey:win+right;;hotkey:win+down;;powershell:\"Layout 4 quadrants configure\""),
    JarvisCommand("sim_layout_trading_full", "pipeline", "Layout trading: MEXC + CoinGecko + Terminal + Dashboard", [
        "layout trading complet", "ecran trading", "multi fenetre trading",
        "vue trading",
    ], "pipeline", "browser:navigate:https://futures.mexc.com;;sleep:3;;hotkey:win+left;;sleep:1;;browser:navigate:https://www.coingecko.com;;sleep:2;;hotkey:win+right;;hotkey:win+up;;sleep:1;;app_open:wt;;sleep:1;;hotkey:win+right;;hotkey:win+down;;powershell:\"Layout trading: MEXC | CoinGecko | Terminal\""),
    JarvisCommand("sim_layout_recherche", "pipeline", "Layout recherche: Perplexity + Claude + Notes", [
        "layout recherche", "ecran recherche", "mode recherche multi",
        "split recherche",
    ], "pipeline", "browser:navigate:https://www.perplexity.ai;;sleep:2;;hotkey:win+left;;sleep:1;;browser:navigate:https://claude.ai;;sleep:2;;hotkey:win+right;;powershell:\"Layout recherche: Perplexity | Claude\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 23 — REMOTE WORK SETUP
    # Scénario: Configuration télétravail
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_remote_work_start", "pipeline", "Setup teletravail: VPN + Slack + Gmail + VSCode + focus", [
        "mode teletravail", "start remote work", "je teletravaille",
        "setup travail a distance",
    ], "pipeline", f"{MINIMIZE_ALL};;sleep:1;;app_open:code;;sleep:2;;hotkey:win+left;;sleep:1;;browser:navigate:https://mail.google.com;;sleep:2;;hotkey:win+right;;sleep:1;;ms_settings:ms-settings:quiethours;;powershell:\"Teletravail configure — focus active\""),
    JarvisCommand("sim_standup_meeting", "pipeline", "Preparer le standup: git log hier + today + blocker check", [
        "prepare le standup", "daily standup", "scrum preparation",
        "qu'est ce que j'ai fait hier",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; \"=== HIER ===\"; git log --since='yesterday' --until='today' --oneline 2>&1 | Out-String;;powershell:cd F:\\BUREAU\\turbo; \"=== AUJOURD'HUI ===\"; git log --since='today' --oneline 2>&1 | Out-String;;powershell:cd F:\\BUREAU\\turbo; \"=== EN COURS ===\"; git status -sb 2>&1 | Out-String;;powershell:\"Standup preparation terminee\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 24 — CRYPTO & TRADING AVANCÉ
    # Scénario: Session de trading crypto complète
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_crypto_research", "pipeline", "Recherche crypto: CoinGecko + CoinDesk + Etherscan + Reddit", [
        "recherche crypto complete", "analyse crypto", "research trading",
        "etudie les cryptos",
    ], "pipeline", "browser:navigate:https://www.coingecko.com;;sleep:2;;browser:navigate:https://www.coindesk.com;;sleep:2;;browser:navigate:https://etherscan.io;;sleep:2;;browser:navigate:https://www.reddit.com/r/CryptoCurrency/;;powershell:\"Recherche crypto: 4 sources ouvertes\""),
    JarvisCommand("sim_trading_session", "pipeline", "Session trading: MEXC + TradingView + Terminal signaux", [
        "session trading complete", "lance le trading", "je vais trader",
        "ouvre tout le trading",
    ], "pipeline", "browser:navigate:https://futures.mexc.com;;sleep:3;;browser:navigate:https://www.tradingview.com;;sleep:2;;app_open:wt;;sleep:1;;powershell:cd F:\\BUREAU\\turbo; \"Session trading active — MEXC + TradingView + Terminal\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 25 — SYSTEM RECOVERY
    # Scénario: Récupération après crash ou problème
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_post_crash_recovery", "pipeline", "Post-crash: check disques + logs + services + GPU + cluster", [
        "recovery apres crash", "le pc a plante", "post crash check",
        "diagnostic apres plantage",
    ], "pipeline", "powershell:Get-PhysicalDisk | Select FriendlyName, HealthStatus | Out-String;;powershell:Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2} -MaxEvents 5 -ErrorAction SilentlyContinue | Select TimeCreated, LevelDisplayName, Message | Out-String -Width 150;;powershell:Get-Service | Where { $_.Status -eq 'Stopped' -and $_.StartType -eq 'Automatic' } | Select Name, Status | Select -First 10 | Out-String;;powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used --format=csv,noheader 2>&1 | Out-String;;powershell:\"Diagnostic post-crash termine\""),
    JarvisCommand("sim_repair_system", "pipeline", "Reparation systeme: DISM + SFC + services restart", [
        "repare le systeme", "system repair", "fix windows",
        "restaure les fichiers systeme",
    ], "pipeline", "powershell:DISM /Online /Cleanup-Image /CheckHealth 2>&1 | Out-String;;powershell:sfc /verifyonly 2>&1 | Select -Last 3 | Out-String;;powershell:\"Verification systeme terminee — lancez 'sfc /scannow' si necessaire\"", confirm=True),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 26 — FULL STACK DEPLOY
    # Scénario: Build, test et déploiement complet d'un projet
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_fullstack_build", "pipeline", "Build complet: lint + tests + build + rapport", [
        "build complet du projet", "full build", "lance tout le build",
        "compile et teste tout",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run ruff check src/ --output-format=concise 2>&1 | Select -Last 10 | Out-String;;powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -m pytest tests/ -x --tb=short 2>&1 | Select -Last 15 | Out-String;;powershell:\"Build complet termine\""),
    JarvisCommand("sim_deploy_check", "pipeline", "Pre-deploy: git status + tests + deps check + commit", [
        "check avant deploiement", "pre deploy check", "pret pour deployer",
        "verifie avant push",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; git status -sb 2>&1 | Out-String;;powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -m pytest tests/ -x --tb=line 2>&1 | Select -Last 10 | Out-String;;powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' pip check 2>&1 | Out-String;;powershell:\"Pre-deploy check termine — pret pour push\""),
    JarvisCommand("sim_git_release", "pipeline", "Release: tag + changelog + push tags", [
        "fais une release", "prepare la release", "git release",
        "nouvelle version",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; $v = git describe --tags --abbrev=0 2>$null; if($v){\"Derniere version: $v\"}else{\"Aucun tag existant\"};;powershell:cd F:\\BUREAU\\turbo; git log --oneline -10 2>&1 | Out-String;;powershell:\"Pret pour tagging — utilisez 'git tag vX.Y.Z' puis 'git push --tags'\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 27 — API TESTING SESSION
    # Scénario: Session complète de test d'API
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_api_test_session", "pipeline", "Session API: Postman + docs + terminal HTTP", [
        "session test api", "teste les apis", "ouvre le setup api",
        "api testing session",
    ], "pipeline", "browser:navigate:https://web.postman.co;;sleep:2;;browser:navigate:https://httpbin.org;;sleep:1;;app_open:wt;;powershell:\"Session API testing ouverte — Postman + HTTPBin + Terminal\""),
    JarvisCommand("sim_api_endpoints_check", "pipeline", "Verifier tous les endpoints locaux (cluster)", [
        "check tous les endpoints", "verifie les apis du cluster",
        "test endpoints locaux", "status des apis",
    ], "pipeline", "powershell:try{$r=Invoke-WebRequest http://127.0.0.1:11434/api/tags -UseBasicParsing -TimeoutSec 3; \"OL1: OK ($($r.StatusCode))\"}catch{\"OL1: OFFLINE\"};;powershell:try{$r=Invoke-WebRequest http://192.168.1.26:1234/api/v1/models -Headers @{Authorization='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -UseBasicParsing -TimeoutSec 3; \"M2: OK ($($r.StatusCode))\"}catch{\"M2: OFFLINE\"};;powershell:try{$r=Invoke-WebRequest http://192.168.1.113:1234/api/v1/models -UseBasicParsing -TimeoutSec 3; \"M3: OK ($($r.StatusCode))\"}catch{\"M3: OFFLINE\"};;powershell:try{$r=Invoke-WebRequest http://10.5.0.2:1234/api/v1/models -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -UseBasicParsing -TimeoutSec 3; \"M1: OK ($($r.StatusCode))\"}catch{\"M1: OFFLINE\"};;powershell:\"Endpoints check termine\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 28 — SOCIAL MEDIA MANAGER
    # Scénario: Ouvrir tous les réseaux sociaux + analytics
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_social_all", "pipeline", "Ouvrir tous les reseaux sociaux", [
        "ouvre tous les reseaux sociaux", "social media complet",
        "lance tous les socials", "ouvre tout social",
    ], "pipeline", "browser:navigate:https://x.com;;sleep:1;;browser:navigate:https://www.linkedin.com;;sleep:1;;browser:navigate:https://www.instagram.com;;sleep:1;;browser:navigate:https://www.reddit.com;;sleep:1;;browser:navigate:https://www.tiktok.com;;powershell:\"5 reseaux sociaux ouverts\""),
    JarvisCommand("sim_content_creation", "pipeline", "Setup creation contenu: Canva + Unsplash + notes", [
        "setup creation contenu", "je vais creer du contenu",
        "mode creation", "prepare la creation",
    ], "pipeline", "browser:navigate:https://www.canva.com;;sleep:2;;browser:navigate:https://unsplash.com;;sleep:1;;app_open:notepad;;powershell:\"Setup creation de contenu pret — Canva + Unsplash + Notes\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 29 — DESIGN WORKFLOW
    # Scénario: Session de design UI/UX complète
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_design_session", "pipeline", "Session design: Figma + Dribbble + Coolors + Font Awesome", [
        "session design", "mode design", "lance le design",
        "ouvre les outils design",
    ], "pipeline", "browser:navigate:https://www.figma.com;;sleep:2;;browser:navigate:https://dribbble.com;;sleep:1;;browser:navigate:https://coolors.co;;sleep:1;;browser:navigate:https://fontawesome.com/icons;;powershell:\"Session design ouverte — Figma + Dribbble + Coolors + FontAwesome\""),
    JarvisCommand("sim_ui_inspiration", "pipeline", "Inspiration UI: Dribbble + Behance + Awwwards", [
        "inspiration ui", "inspiration design", "montre moi du beau",
        "idees design",
    ], "pipeline", "browser:navigate:https://dribbble.com;;sleep:1;;browser:navigate:https://www.behance.net;;sleep:1;;browser:navigate:https://www.awwwards.com;;powershell:\"3 sources d'inspiration ouvertes\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 30 — SYSTEM OPTIMIZATION
    # Scénario: Optimisation complète du système Windows
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_optimize_full", "pipeline", "Optimisation: temp + startup + services + defrag check", [
        "optimise le systeme", "full optimization", "accelere le pc",
        "optimisation complete",
    ], "pipeline", "powershell:$tmp = (Get-ChildItem $env:TEMP -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB; \"Temp: $([math]::Round($tmp))MB\";;powershell:Get-CimInstance Win32_StartupCommand | Select Name, Command | Format-Table | Out-String;;powershell:Get-Service | Where { $_.StartType -eq 'Automatic' -and $_.Status -ne 'Running' } | Select Name, Status | Format-Table | Out-String;;powershell:defrag C: /A 2>&1 | Out-String;;powershell:\"Analyse d'optimisation terminee\""),
    JarvisCommand("sim_cleanup_aggressive", "pipeline", "Nettoyage agressif: temp + cache + logs + recycle bin", [
        "nettoyage agressif", "nettoie tout a fond", "libere maximum",
        "clean agressif",
    ], "pipeline", "powershell:Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; \"Temp nettoye\";;powershell:Remove-Item \"$env:LOCALAPPDATA\\Microsoft\\Windows\\Explorer\\thumbcache_*\" -Force -ErrorAction SilentlyContinue; \"Thumbnail cache nettoye\";;powershell:Clear-RecycleBin -Force -ErrorAction SilentlyContinue; \"Corbeille videe\";;powershell:\"Nettoyage agressif termine\"", confirm=True),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 31 — LEARNING SESSION
    # Scénario: Session d'apprentissage et formation
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_learn_coding", "pipeline", "Learning code: YouTube + MDN + W3Schools + exercism", [
        "session apprentissage code", "je veux apprendre", "mode apprentissage",
        "lance la formation",
    ], "pipeline", "browser:navigate:https://www.youtube.com;;sleep:1;;browser:navigate:https://developer.mozilla.org;;sleep:1;;browser:navigate:https://www.w3schools.com;;sleep:1;;browser:navigate:https://exercism.org;;powershell:\"Session apprentissage code ouverte — 4 ressources\""),
    JarvisCommand("sim_learn_ai", "pipeline", "Learning IA: HuggingFace + Papers + Cours + Playground", [
        "session apprentissage ia", "apprendre le machine learning",
        "mode apprentissage ia", "formation ia",
    ], "pipeline", "browser:navigate:https://huggingface.co/learn;;sleep:1;;browser:navigate:https://arxiv.org/list/cs.AI/recent;;sleep:1;;browser:navigate:https://www.coursera.org/browse/data-science/machine-learning;;sleep:1;;browser:navigate:https://playground.tensorflow.org;;powershell:\"Session apprentissage IA ouverte — 4 ressources\""),
    JarvisCommand("sim_pomodoro_25", "pipeline", "Pomodoro 25min: timer + focus assist + notification", [
        "lance un pomodoro", "pomodoro 25 minutes", "timer pomodoro",
        "focus 25 minutes",
    ], "pipeline", "powershell:Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('Pomodoro demarre, 25 minutes');;ms_settings:quiethours;;powershell:Start-Sleep -Seconds 1500; Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Pomodoro termine! Prends une pause de 5 minutes.', 'JARVIS Pomodoro');;powershell:\"Pomodoro 25min lance\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 32 — BACKUP STRATEGY
    # Scénario: Sauvegarde complète du projet et données
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_backup_turbo", "pipeline", "Backup turbo: git bundle + zip data + rapport", [
        "backup le projet", "sauvegarde turbo", "backup complet",
        "fais un backup",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; git bundle create F:\\BUREAU\\turbo_backup_$(Get-Date -Format yyyyMMdd).bundle --all 2>&1 | Out-String;;powershell:Compress-Archive -Path F:\\BUREAU\\turbo\\data -DestinationPath F:\\BUREAU\\turbo_data_backup_$(Get-Date -Format yyyyMMdd).zip -Force; \"Data backup cree\";;powershell:\"Backup turbo termine — bundle git + zip data\""),
    JarvisCommand("sim_backup_verify", "pipeline", "Verifier les backups: taille + date + integrite", [
        "verifie les backups", "check les sauvegardes", "status backup",
        "les backups sont ok",
    ], "pipeline", "powershell:Get-ChildItem F:\\BUREAU\\turbo_backup_*.bundle -ErrorAction SilentlyContinue | Select Name, @{N='Size(MB)';E={[math]::Round($_.Length/1MB,1)}}, LastWriteTime | Format-Table | Out-String;;powershell:Get-ChildItem F:\\BUREAU\\turbo_data_backup_*.zip -ErrorAction SilentlyContinue | Select Name, @{N='Size(MB)';E={[math]::Round($_.Length/1MB,1)}}, LastWriteTime | Format-Table | Out-String;;powershell:\"Verification backups terminee\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 33 — MORNING PRODUCTIVITY
    # Scénario: Routine matinale complète de productivité
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_morning_routine", "pipeline", "Routine matin: meteo + news + mails + cluster + standup", [
        "routine du matin", "bonjour jarvis", "demarre la journee",
        "morning routine",
    ], "pipeline", "browser:navigate:https://www.meteofrance.com;;sleep:1;;browser:navigate:https://news.google.com;;sleep:1;;browser:navigate:https://mail.google.com;;sleep:2;;powershell:try{$r=Invoke-WebRequest http://127.0.0.1:11434/api/tags -UseBasicParsing -TimeoutSec 3; \"OL1: OK\"}catch{\"OL1: OFF\"};;powershell:cd F:\\BUREAU\\turbo; git log --since='yesterday' --oneline 2>&1 | Out-String;;powershell:\"Routine matinale complete — bonne journee!\""),
    JarvisCommand("sim_evening_shutdown", "pipeline", "Routine soir: git status + save + clear temp + veille", [
        "routine du soir", "bonsoir jarvis", "fin de journee",
        "evening routine",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; git status -sb 2>&1 | Out-String;;powershell:cd F:\\BUREAU\\turbo; git stash 2>&1 | Out-String;;powershell:Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; \"Temp nettoye\";;powershell:\"Fin de journee — travail sauvegarde, systeme propre\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 34 — FREELANCE WORKSPACE
    # Scénario: Setup complet pour du travail freelance
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_freelance_setup", "pipeline", "Setup freelance: Malt + factures + timer + mail", [
        "mode freelance", "setup freelance", "session freelance",
        "je travaille en freelance",
    ], "pipeline", "browser:navigate:https://www.malt.fr;;sleep:1;;browser:navigate:https://mail.google.com;;sleep:1;;app_open:wt;;powershell:\"Setup freelance pret — Malt + Mail + Terminal\""),
    JarvisCommand("sim_client_meeting", "pipeline", "Prep meeting client: Teams + notes + projet + timer", [
        "prepare le meeting client", "meeting client", "reunion client",
        "appel client",
    ], "pipeline", "app_open:ms-teams;;sleep:3;;app_open:notepad;;sleep:1;;powershell:cd F:\\BUREAU\\turbo; git log --oneline -5 2>&1 | Out-String;;powershell:\"Meeting client prepare — Teams + Notes + Status projet\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 35 — DATABASE MANAGEMENT
    # Scénario: Gestion complète des bases de données
    # ══════════════════════════════════════════════════════════════════════
JarvisCommand("sim_db_backup_all", "pipeline", "Backup toutes les DBs: jarvis + etoile + trading", [
        "backup toutes les bases", "sauvegarde les bases", "db backup all",
        "backup databases",
    ], "pipeline", "powershell:$d=Get-Date -Format yyyyMMdd; Copy-Item F:\\BUREAU\\turbo\\data\\jarvis.db F:\\BUREAU\\turbo\\data\\jarvis_backup_$d.db; \"jarvis.db backup OK\";;powershell:$d=Get-Date -Format yyyyMMdd; Copy-Item F:\\BUREAU\\etoile.db F:\\BUREAU\\etoile_backup_$d.db; \"etoile.db backup OK\";;powershell:\"Backup de toutes les bases termine\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 36 — SECURITY AUDIT
    # Scénario: Audit de sécurité complet du système
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_security_full_audit", "pipeline", "Audit secu: ports + firewall + users + certs + deps", [
        "audit securite complet", "full security audit",
        "scan securite total", "verifie la securite du systeme",
    ], "pipeline", "powershell:Get-NetTCPConnection -State Listen | Select -First 10 LocalPort, @{N='Process';E={(Get-Process -Id $_.OwningProcess -ea 0).Name}} | Format-Table | Out-String;;powershell:Get-NetFirewallProfile | Select Name, Enabled | Format-Table | Out-String;;powershell:Get-LocalUser | Where Enabled | Select Name, LastLogon | Format-Table | Out-String;;powershell:Get-ChildItem Cert:\\LocalMachine\\My -ErrorAction SilentlyContinue | Select Subject, NotAfter | Format-Table | Out-String;;powershell:\"Audit securite termine — 4 scans effectues\""),
    JarvisCommand("sim_security_network", "pipeline", "Audit reseau: connexions + DNS + ARP + routes", [
        "audit reseau", "scan reseau complet", "network security audit",
        "verifie le reseau",
    ], "pipeline", "powershell:Get-NetTCPConnection | Where { $_.State -eq 'Established' } | Group RemoteAddress | Sort Count -Descending | Select -First 10 Count, Name | Format-Table | Out-String;;powershell:Get-DnsClientCache | Select -First 15 Entry, Data | Format-Table | Out-String;;powershell:arp -a | Out-String;;powershell:route print -4 | Select -First 20 | Out-String;;powershell:\"Audit reseau termine\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 37 — PERFORMANCE BENCHMARK
    # Scénario: Benchmark complet du système
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_benchmark_system", "pipeline", "Benchmark: CPU + RAM + disque + GPU + reseau", [
        "benchmark systeme", "performance complete", "teste les performances",
        "benchmark du pc",
    ], "pipeline", "powershell:$cpu = Get-CimInstance Win32_Processor; \"CPU: $($cpu.Name) — $($cpu.NumberOfCores) cores, $($cpu.MaxClockSpeed)MHz\";;powershell:$ram = Get-CimInstance Win32_OperatingSystem; \"RAM: $([math]::Round(($ram.TotalVisibleMemorySize-$ram.FreePhysicalMemory)/1MB,1))GB / $([math]::Round($ram.TotalVisibleMemorySize/1MB,1))GB\";;powershell:Get-PhysicalDisk | Select FriendlyName, MediaType, @{N='Size(GB)';E={[math]::Round($_.Size/1GB)}} | Format-Table | Out-String;;powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>&1 | Out-String;;powershell:\"Benchmark systeme termine\""),
    JarvisCommand("sim_benchmark_cluster", "pipeline", "Benchmark cluster: ping tous les noeuds + latence", [
        "benchmark cluster", "teste le cluster", "latence cluster",
        "performance du cluster",
    ], "pipeline", "powershell:$sw=[Diagnostics.Stopwatch]::StartNew(); try{Invoke-WebRequest http://127.0.0.1:11434/api/tags -UseBasicParsing -TimeoutSec 3 >$null; $sw.Stop(); \"OL1: $($sw.ElapsedMilliseconds)ms\"}catch{\"OL1: OFFLINE\"};;powershell:$sw=[Diagnostics.Stopwatch]::StartNew(); try{Invoke-WebRequest http://192.168.1.26:1234/api/v1/models -Headers @{Authorization='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -UseBasicParsing -TimeoutSec 3 >$null; $sw.Stop(); \"M2: $($sw.ElapsedMilliseconds)ms\"}catch{\"M2: OFFLINE\"};;powershell:$sw=[Diagnostics.Stopwatch]::StartNew(); try{Invoke-WebRequest http://192.168.1.113:1234/api/v1/models -UseBasicParsing -TimeoutSec 3 >$null; $sw.Stop(); \"M3: $($sw.ElapsedMilliseconds)ms\"}catch{\"M3: OFFLINE\"};;powershell:\"Benchmark cluster termine\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 38 — DOCUMENTATION SESSION
    # Scénario: Session de rédaction de documentation
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_doc_session", "pipeline", "Session docs: VSCode + docs + preview markdown", [
        "session documentation", "ecris la doc", "mode documentation",
        "redige la doc",
    ], "pipeline", "powershell:code F:\\BUREAU\\turbo\\docs 2>$null;;sleep:2;;browser:navigate:https://devdocs.io;;sleep:1;;browser:navigate:https://markdownlivepreview.com;;powershell:\"Session documentation ouverte — VSCode + DevDocs + Markdown Preview\""),
    JarvisCommand("sim_doc_generate", "pipeline", "Generer toute la doc: vocale + README + changelog", [
        "genere toute la doc", "regenere la documentation",
        "update la doc", "rafraichis la doc",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python scripts/gen_vocal_docs.py 2>&1 | Out-String;;powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python scripts/gen_readme_commands.py 2>&1 | Out-String;;powershell:\"Documentation regeneree — vocale + README\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 39 — AI/ML WORKSPACE
    # Scénario: Espace de travail IA et Machine Learning
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_ai_workspace", "pipeline", "Workspace IA: HuggingFace + Papers + GPU monitor + terminal", [
        "workspace ia", "espace de travail ia", "mode machine learning",
        "setup ia",
    ], "pipeline", "browser:navigate:https://huggingface.co;;sleep:1;;browser:navigate:https://arxiv.org/list/cs.AI/recent;;sleep:1;;app_open:wt;;sleep:1;;powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used,utilization.gpu --format=csv,noheader 2>&1 | Out-String;;powershell:\"Workspace IA pret — HuggingFace + arXiv + Terminal + GPU\""),
    JarvisCommand("sim_model_eval", "pipeline", "Evaluation modele: benchmark cluster + comparaison", [
        "evalue les modeles", "benchmark modeles", "compare les modeles",
        "evaluation ia",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python benchmark_cluster.py 2>&1 | Select -Last 20 | Out-String;;powershell:\"Evaluation modeles terminee — voir data/benchmark_report.json\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 40 — HOME OFFICE SETUP
    # Scénario: Configuration bureau à domicile complète
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_home_office", "pipeline", "Home office: Teams + Mail + Spotify + cluster + news", [
        "mode bureau", "home office", "mode teletravail",
        "setup bureau maison",
    ], "pipeline", "app_open:ms-teams;;sleep:2;;browser:navigate:https://mail.google.com;;sleep:1;;app_open:spotify;;sleep:1;;powershell:try{Invoke-WebRequest http://127.0.0.1:11434/api/tags -UseBasicParsing -TimeoutSec 3 >$null; 'Cluster: OL1 OK'}catch{'Cluster: OL1 OFF'};;browser:navigate:https://news.google.com;;powershell:\"Home office setup complet — Teams + Mail + Spotify + Cluster + News\""),
    JarvisCommand("sim_focus_deep_work", "pipeline", "Deep work: ferme tout + focus assist + timer 90min + musique lo-fi", [
        "mode deep work", "concentration maximale", "focus profond",
        "deep focus",
    ], "pipeline", "powershell:(New-Object -ComObject Shell.Application).MinimizeAll();;ms_settings:quiethours;;sleep:1;;app_open:spotify;;powershell:\"Deep work active — Focus Assist ON, 90 minutes de concentration\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 41 — WEEKEND CHILL
    # Scénario: Mode détente weekend
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_weekend_chill", "pipeline", "Weekend: Netflix + Spotify + food delivery + mode eco", [
        "mode weekend", "weekend chill", "mode detente",
        "c'est le weekend",
    ], "pipeline", "browser:navigate:https://www.netflix.com;;sleep:1;;app_open:spotify;;sleep:1;;browser:navigate:https://www.ubereats.com;;powershell:powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e;;powershell:\"Mode weekend active — Netflix + Spotify + UberEats + Eco\""),
    JarvisCommand("sim_movie_night", "pipeline", "Soiree film: minimiser tout + Netflix + lumiere tamisee", [
        "soiree film", "movie night", "mode cinema maison",
        "on regarde un film",
    ], "pipeline", "powershell:(New-Object -ComObject Shell.Application).MinimizeAll();;sleep:1;;browser:navigate:https://www.netflix.com;;ms_settings:nightlight;;powershell:\"Soiree film prete — Netflix + Night Light\""),
]
