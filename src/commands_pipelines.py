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
]
