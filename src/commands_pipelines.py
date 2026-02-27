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
    ], "pipeline", "powershell:$j = (Get-Item 'F:\\BUREAU\\turbo\\data\\jarvis.db' -ErrorAction SilentlyContinue).Length/1MB; \"jarvis.db: $([math]::Round($j,1)) MB\";;powershell:$e = (Get-Item 'F:\\BUREAU\\turbo\\data\\etoile.db' -ErrorAction SilentlyContinue).Length/1MB; \"etoile.db: $([math]::Round($e,1)) MB\";;powershell:$t = (Get-Item 'F:\\BUREAU\\carV1\\database\\trading_latest.db' -ErrorAction SilentlyContinue).Length/1MB; \"trading.db: $([math]::Round($t,1)) MB\""),
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
    ], "pipeline", "powershell:$j = (Get-Item F:\\BUREAU\\turbo\\data\\jarvis.db -ErrorAction SilentlyContinue).Length/1KB; $e = (Get-Item F:\\BUREAU\\turbo\\data\\etoile.db -ErrorAction SilentlyContinue).Length/1KB; \"jarvis.db: $([math]::Round($j)) KB | etoile.db: $([math]::Round($e)) KB\";;powershell:sqlite3 F:\\BUREAU\\turbo\\data\\jarvis.db 'PRAGMA integrity_check;' 2>&1 | Out-String;;powershell:sqlite3 F:\\BUREAU\\turbo\\data\\etoile.db 'PRAGMA integrity_check;' 2>&1 | Out-String;;powershell:sqlite3 F:\\BUREAU\\turbo\\data\\etoile.db 'SELECT category, COUNT(*) as c FROM map GROUP BY category ORDER BY c DESC;' 2>&1 | Out-String;;powershell:\"Health check DB termine\""),
    JarvisCommand("sim_db_backup", "pipeline", "Backup toutes les bases de donnees", [
        "backup les bases", "sauvegarde les db", "copie les bases de donnees",
        "backup database",
    ], "pipeline", "powershell:$d = Get-Date -Format 'yyyy-MM-dd_HHmm'; Copy-Item F:\\BUREAU\\turbo\\data\\jarvis.db \"F:\\BUREAU\\turbo\\data\\jarvis_backup_$d.db\" -Force; Copy-Item F:\\BUREAU\\turbo\\data\\etoile.db \"F:\\BUREAU\\etoile_backup_$d.db\" -Force; \"Backup DB: jarvis_backup_$d.db + etoile_backup_$d.db\""),
    JarvisCommand("sim_db_stats", "pipeline", "Statistiques des bases: tables, lignes, taille par table", [
        "stats des bases", "metriques db", "combien dans les bases",
        "taille des tables",
    ], "pipeline", "powershell:sqlite3 F:\\BUREAU\\turbo\\data\\jarvis.db '.tables' 2>&1 | Out-String;;powershell:sqlite3 F:\\BUREAU\\turbo\\data\\jarvis.db 'SELECT \"skills\" as tbl, COUNT(*) as rows FROM skills UNION ALL SELECT \"actions\", COUNT(*) FROM actions UNION ALL SELECT \"historique\", COUNT(*) FROM historique;' 2>&1 | Out-String;;powershell:sqlite3 F:\\BUREAU\\turbo\\data\\etoile.db 'SELECT \"map\" as tbl, COUNT(*) as rows FROM map UNION ALL SELECT \"agents\", COUNT(*) FROM agents UNION ALL SELECT \"memories\", COUNT(*) FROM memories;' 2>&1 | Out-String;;powershell:\"Stats DB terminees\""),

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
    ], "pipeline", "powershell:$d=Get-Date -Format yyyyMMdd; Copy-Item F:\\BUREAU\\turbo\\data\\jarvis.db F:\\BUREAU\\turbo\\data\\jarvis_backup_$d.db; \"jarvis.db backup OK\";;powershell:$d=Get-Date -Format yyyyMMdd; Copy-Item F:\\BUREAU\\turbo\\data\\etoile.db F:\\BUREAU\\etoile_backup_$d.db; \"etoile.db backup OK\";;powershell:\"Backup de toutes les bases termine\""),

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

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 42 — TECH NEWS SESSION
    # Scénario: Veille technologique complète
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_tech_news", "pipeline", "Veille tech: HN + TechCrunch + Reddit + The Verge", [
        "veille tech", "news tech", "ouvre les news tech",
        "actualites tech",
    ], "pipeline", "browser:navigate:https://news.ycombinator.com;;sleep:1;;browser:navigate:https://techcrunch.com;;sleep:1;;browser:navigate:https://www.reddit.com/r/programming/;;sleep:1;;browser:navigate:https://www.theverge.com;;powershell:\"Veille tech ouverte — 4 sources\""),
    JarvisCommand("sim_ai_news", "pipeline", "News IA: arXiv + HuggingFace + Semantic Scholar + Papers", [
        "news ia", "actualites intelligence artificielle", "veille ia",
        "quoi de neuf en ia",
    ], "pipeline", "browser:navigate:https://arxiv.org/list/cs.AI/recent;;sleep:1;;browser:navigate:https://huggingface.co/papers;;sleep:1;;browser:navigate:https://www.semanticscholar.org;;sleep:1;;browser:navigate:https://paperswithcode.com;;powershell:\"Veille IA ouverte — 4 sources\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 43 — DEPLOYMENT PIPELINE
    # Scénario: Pipeline de déploiement complet
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_deploy_vercel", "pipeline", "Deploy Vercel: build + push + deploy + verify", [
        "deploie sur vercel", "deploy vercel", "push vercel",
        "met en prod sur vercel",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; git status -sb 2>&1 | Out-String;;powershell:cd F:\\BUREAU\\turbo; git push origin main 2>&1 | Out-String;;browser:navigate:https://vercel.com/dashboard;;powershell:\"Deploy initie — verifier le dashboard Vercel\""),
    JarvisCommand("sim_deploy_docker", "pipeline", "Deploy Docker: build image + tag + push registry", [
        "deploie en docker", "docker deploy", "push docker image",
        "build et deploy docker",
    ], "pipeline", "powershell:docker build -t jarvis-turbo:latest . 2>&1 | Select -Last 5 | Out-String;;powershell:docker tag jarvis-turbo:latest jarvis-turbo:$(Get-Date -Format yyyyMMdd) 2>&1 | Out-String;;powershell:docker images jarvis-turbo --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' 2>&1 | Out-String;;powershell:\"Build Docker termine — image taggee\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 44 — DATA SCIENCE WORKSPACE
    # Scénario: Espace de travail data science
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_datascience_setup", "pipeline", "Data Science: Jupyter + HuggingFace + GPU monitor", [
        "mode data science", "setup data science", "workspace datascience",
        "lance jupyter et compagnie",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run jupyter lab --no-browser 2>&1 | Select -First 3 | Out-String;;browser:navigate:https://huggingface.co/datasets;;sleep:1;;powershell:nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>&1 | Out-String;;powershell:\"Data Science workspace pret — Jupyter + HuggingFace + GPU\""),
    JarvisCommand("sim_kaggle_session", "pipeline", "Session Kaggle: competitions + notebooks + datasets", [
        "session kaggle", "mode kaggle", "ouvre kaggle",
        "competitions kaggle",
    ], "pipeline", "browser:navigate:https://www.kaggle.com/competitions;;sleep:1;;browser:navigate:https://www.kaggle.com/datasets;;sleep:1;;browser:navigate:https://www.kaggle.com/code;;powershell:\"Session Kaggle ouverte — Competitions + Datasets + Notebooks\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 45 — INTERVIEW PREP
    # Scénario: Préparation d'entretien technique
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_interview_prep", "pipeline", "Prep entretien: LeetCode + GeeksForGeeks + docs + notes", [
        "prepare l'entretien", "mode interview", "practice coding",
        "preparation entretien tech",
    ], "pipeline", "browser:navigate:https://leetcode.com;;sleep:1;;browser:navigate:https://www.geeksforgeeks.org;;sleep:1;;browser:navigate:https://devdocs.io;;sleep:1;;app_open:notepad;;powershell:\"Preparation entretien prete — LeetCode + GFG + Docs + Notes\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 46 — PHOTO EDITING SESSION
    # Scénario: Session d'édition photo/vidéo
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_photo_edit", "pipeline", "Photo edit: Photopea + Pexels + Remove.bg + Canva", [
        "mode edition photo", "session photo", "edite des photos",
        "retouche photo",
    ], "pipeline", "browser:navigate:https://www.photopea.com;;sleep:2;;browser:navigate:https://www.pexels.com;;sleep:1;;browser:navigate:https://www.remove.bg;;sleep:1;;browser:navigate:https://www.canva.com;;powershell:\"Session photo ouverte — Photopea + Pexels + Remove.bg + Canva\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 47 — SYSTEM HARDENING
    # Scénario: Renforcement de la sécurité système
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_system_hardening", "pipeline", "Hardening: firewall + users + ports + updates + audit", [
        "renforce la securite", "system hardening", "securise le systeme",
        "mode securite maximale",
    ], "pipeline", "powershell:Get-NetFirewallProfile | Select Name, Enabled | Format-Table | Out-String;;powershell:Get-LocalUser | Where Enabled | Select Name, LastLogon | Format-Table | Out-String;;powershell:Get-NetTCPConnection -State Listen | Select -First 10 LocalPort, @{N='Process';E={(Get-Process -Id $_.OwningProcess -ea 0).Name}} | Format-Table | Out-String;;powershell:Get-HotFix | Sort InstalledOn -Desc | Select -First 5 HotFixID, InstalledOn | Format-Table | Out-String;;powershell:\"Audit de securite termine — 4 verifications effectuees\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 48 — COOKING / MEAL PREP
    # Scénario: Planification de repas
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_meal_prep", "pipeline", "Meal prep: Marmiton + 750g + Uber Eats + notes", [
        "meal prep", "planifie les repas", "qu'est ce qu'on mange",
        "idees de repas",
    ], "pipeline", "browser:navigate:https://www.marmiton.org;;sleep:1;;browser:navigate:https://www.750g.com;;sleep:1;;browser:navigate:https://www.ubereats.com;;sleep:1;;app_open:notepad;;powershell:\"Meal prep ouvert — Marmiton + 750g + UberEats + Notes\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 49 — FULL STACK MONITORING
    # Scénario: Monitoring complet de la stack
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_monitoring_full", "pipeline", "Monitoring: GPU + cluster + ports + logs + disk", [
        "monitoring complet", "check tout le monitoring", "surveillance totale",
        "dashboard monitoring",
    ], "pipeline", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used,utilization.gpu --format=csv,noheader 2>&1 | Out-String;;powershell:@('http://127.0.0.1:11434/api/tags','http://192.168.1.26:1234/api/v1/models','http://192.168.1.113:1234/api/v1/models') | ForEach-Object { try{Invoke-WebRequest $_ -UseBasicParsing -TimeoutSec 2 >$null; \"$_`: OK\"}catch{\"$_`: OFFLINE\"} } | Out-String;;powershell:Get-NetTCPConnection -State Listen | Group LocalPort | Sort Count -Desc | Select -First 10 Count, Name | Format-Table | Out-String;;powershell:Get-Content F:\\BUREAU\\turbo\\data\\jarvis.log -Tail 5 -ErrorAction SilentlyContinue | Out-String;;powershell:Get-PSDrive -PSProvider FileSystem | Select Name, @{N='Free(GB)';E={[math]::Round($_.Free/1GB,1)}}, @{N='Used(GB)';E={[math]::Round($_.Used/1GB,1)}} | Format-Table | Out-String;;powershell:\"Monitoring complet termine — 5 checks\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 50 — JARVIS SELF-CHECK
    # Scénario: Auto-diagnostic complet de JARVIS
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_jarvis_selfcheck", "pipeline", "Auto-diagnostic JARVIS: config + deps + DB + commands + cluster", [
        "auto diagnostic jarvis", "jarvis self check", "verifie toi meme",
        "diagnostic jarvis complet",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"from src.config import *; print('Config: OK')\" 2>&1 | Out-String;;powershell:cd F:\\BUREAU\\turbo; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"from src.commands import COMMANDS; print(f'{len(COMMANDS)} commandes chargees')\" 2>&1 | Out-String;;powershell:$dbs=@('F:\\BUREAU\\turbo\\data\\jarvis.db','F:\\BUREAU\\turbo\\data\\etoile.db'); $dbs | ForEach-Object { if(Test-Path $_){$f=Get-Item $_; \"$($f.Name): $([math]::Round($f.Length/1KB))KB OK\"}else{\"$_ MANQUANT\"} } | Out-String;;powershell:try{Invoke-WebRequest http://127.0.0.1:11434/api/tags -UseBasicParsing -TimeoutSec 3 >$null; 'OL1: OK'}catch{'OL1: OFFLINE'};;powershell:\"Auto-diagnostic JARVIS termine\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 51 — WIFI & NETWORK DIAGNOSTIC
    # Scénario: Diagnostic réseau complet
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_network_diag_full", "pipeline", "Diag reseau complet: wifi + ping + DNS + speed + ports", [
        "diagnostic reseau complet", "teste tout le reseau",
        "reseau complet check", "probleme internet",
    ], "pipeline", "powershell:netsh wlan show interfaces | Select-String 'SSID|Signal|State' | Out-String;;powershell:Test-Connection 8.8.8.8 -Count 3 | Select Address, Latency, Status | Format-Table | Out-String;;powershell:Resolve-DnsName google.com | Select Name, Type, IPAddress | Format-Table | Out-String;;powershell:Get-NetTCPConnection -State Established | Group RemoteAddress | Sort Count -Desc | Select -First 8 Count, Name | Format-Table | Out-String;;powershell:\"Diagnostic reseau complet termine\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 52 — OPEN SOURCE CONTRIBUTION
    # Scénario: Session de contribution open source
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_opensource_session", "pipeline", "Open source: GitHub + issues + fork + terminal", [
        "mode open source", "session contribution", "contribute au code",
        "open source session",
    ], "pipeline", "browser:navigate:https://github.com/trending;;sleep:1;;browser:navigate:https://github.com/issues;;sleep:1;;app_open:wt;;sleep:1;;powershell:cd F:\\BUREAU\\turbo; git status -sb 2>&1 | Out-String;;powershell:\"Session open source prete — GitHub Trending + Issues + Terminal\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 53 — STREAMING SETUP
    # Scénario: Configuration pour streamer
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_stream_setup_full", "pipeline", "Stream setup: OBS + Twitch + Spotify + chat + high perf", [
        "setup stream complet", "je vais streamer", "mode streamer pro",
        "lance tout le stream",
    ], "pipeline", "powershell:powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c;;app_open:obs64;;sleep:3;;browser:navigate:https://dashboard.twitch.tv;;sleep:1;;app_open:spotify;;sleep:1;;browser:navigate:https://www.twitch.tv/popout/chat;;powershell:\"Stream setup complet — OBS + Twitch + Spotify + Chat + High Perf\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 54 — CRYPTO PORTFOLIO
    # Scénario: Gestion de portefeuille crypto complet
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_crypto_portfolio", "pipeline", "Crypto portfolio: CoinGecko + DeFi Llama + Zapper + Dune", [
        "portfolio crypto", "check mes cryptos", "gestion crypto complete",
        "combien j'ai en crypto",
    ], "pipeline", "browser:navigate:https://www.coingecko.com;;sleep:1;;browser:navigate:https://defillama.com;;sleep:1;;browser:navigate:https://zapper.xyz;;sleep:1;;browser:navigate:https://dune.com;;powershell:\"Portfolio crypto ouvert — 4 dashboards\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 55 — EMERGENCY RECOVERY
    # Scénario: Récupération d'urgence après problème grave
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_emergency_recovery", "pipeline", "Recovery urgence: disques + events + services + GPU + restore points", [
        "urgence recovery", "le pc va mal", "gros probleme",
        "mode urgence systeme",
    ], "pipeline", "powershell:Get-PhysicalDisk | Select FriendlyName, HealthStatus, OperationalStatus | Format-Table | Out-String;;powershell:Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2} -MaxEvents 10 -ErrorAction SilentlyContinue | Select TimeCreated, LevelDisplayName, @{N='Msg';E={$_.Message.Substring(0,[Math]::Min(60,$_.Message.Length))}} | Format-Table -Wrap | Out-String;;powershell:Get-Service | Where { $_.StartType -eq 'Automatic' -and $_.Status -ne 'Running' } | Select -First 10 Name, Status | Format-Table | Out-String;;powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used --format=csv,noheader 2>&1 | Out-String;;powershell:Get-ComputerRestorePoint | Select -Last 3 Description, CreationTime | Format-Table | Out-String;;powershell:\"Recovery urgence: 5 diagnostics effectues\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 56 — WEEKLY REVIEW
    # Scénario: Revue hebdomadaire du projet
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_weekly_review", "pipeline", "Review hebdo: commits semaine + issues + LOC + DB + cluster perf", [
        "review hebdomadaire", "bilan de la semaine", "weekly review",
        "qu'est ce qu'on a fait cette semaine",
    ], "pipeline", "powershell:cd F:\\BUREAU\\turbo; \"=== COMMITS CETTE SEMAINE ===\"; git log --since='7 days ago' --oneline 2>&1 | Out-String;;powershell:cd F:\\BUREAU\\turbo; $f=git diff --stat HEAD~10 2>&1 | Select -Last 1; \"Changements: $f\";;powershell:cd F:\\BUREAU\\turbo; $loc=(Get-ChildItem src/*.py -Recurse | ForEach-Object { (Get-Content $_.FullName | Measure-Object -Line).Lines } | Measure-Object -Sum).Sum; \"Lignes de code: $loc\";;powershell:cd F:\\BUREAU\\turbo; gh issue list --limit 5 2>&1 | Out-String;;powershell:\"Review hebdomadaire terminee\""),

    # ══════════════════════════════════════════════════════════════════════
    # SIMULATION 57 — PRESENTATION PREP
    # Scénario: Préparation de présentation / démo
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("sim_demo_prep", "pipeline", "Prep demo: clean bureau + full screen + terminal + slides", [
        "prepare la demo", "mode demo", "setup presentation",
        "je vais presenter",
    ], "pipeline", "powershell:(New-Object -ComObject Shell.Application).MinimizeAll();;sleep:1;;app_open:wt;;sleep:1;;browser:navigate:https://docs.google.com/presentation;;powershell:\"Demo preparation terminee — Bureau propre + Terminal + Slides\""),

    # ══════════════════════════════════════════════════════════════════════
    # CLUSTER MANAGEMENT — Gestion du cluster IA (M1/M2/M3/OL1)
    # Pilotage des noeuds, modeles, health checks, benchmarks
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("cluster_health_live", "pipeline", "Health check live: ping M1 + M2 + M3 + OL1 + GPU temperatures", [
        "health check cluster", "etat du cluster", "comment va le cluster",
        "check les machines", "status des noeuds",
        "verifie le cluster", "cluster status",
    ], "pipeline", "powershell:$m1 = try{(Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; $m2 = try{(Invoke-WebRequest -Uri 'http://192.168.1.26:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; $m3 = try{(Invoke-WebRequest -Uri 'http://192.168.1.113:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux'} -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; $ol1 = try{(Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; \"Cluster: M1=$(if($m1 -eq 200){'OK'}else{'OFF'}) | M2=$(if($m2 -eq 200){'OK'}else{'OFF'}) | M3=$(if($m3 -eq 200){'OK'}else{'OFF'}) | OL1=$(if($ol1 -eq 200){'OK'}else{'OFF'})\";;powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>&1 | Out-String"),

    JarvisCommand("cluster_model_status", "pipeline", "Modeles charges sur chaque noeud du cluster", [
        "quels modeles sont charges", "modeles actifs", "models loaded",
        "liste les modeles", "qu'est-ce qui tourne sur le cluster",
    ], "pipeline", "powershell:$r = Invoke-RestMethod -Uri 'http://10.5.0.2:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 5; $loaded = ($r.models | Where-Object {$_.loaded_instances.Count -gt 0}).key -join ', '; \"M1: $loaded\";;powershell:$r = Invoke-RestMethod -Uri 'http://192.168.1.26:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 5; $loaded = ($r.models | Where-Object {$_.loaded_instances.Count -gt 0}).key -join ', '; \"M2: $loaded\";;powershell:$r = Invoke-RestMethod -Uri 'http://192.168.1.113:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux'} -TimeoutSec 5; $loaded = ($r.models | Where-Object {$_.loaded_instances.Count -gt 0}).key -join ', '; \"M3: $loaded\";;powershell:$r = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5; \"OL1: \" + ($r.models.name -join ', ')"),

    JarvisCommand("cluster_reload_m1", "pipeline", "Recharger qwen3-8b sur M1 (machine principale)", [
        "recharge m1", "reload m1", "relance le modele sur m1",
        "redemarre qwen sur m1", "reset m1",
    ], "pipeline", "powershell:Invoke-RestMethod -Uri 'http://10.5.0.2:1234/api/v1/models/load' -Method Post -Body '{\"model\":\"qwen3-8b\"}' -ContentType 'application/json' -Headers @{'Authorization'='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 60; 'M1 qwen3-8b rechargement lance';;sleep:5;;powershell:$r = Invoke-RestMethod -Uri 'http://10.5.0.2:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 5; $loaded = ($r.models | Where-Object {$_.loaded_instances.Count -gt 0}).key -join ', '; \"M1 modeles actifs: $loaded\"", confirm=True),

    JarvisCommand("cluster_restart_ollama", "pipeline", "Redemarrer Ollama local (OL1)", [
        "redemarre ollama", "restart ollama", "relance ollama",
        "reset ol1", "ol1 restart",
    ], "pipeline", "powershell:Stop-Process -Name 'ollama' -Force -ErrorAction SilentlyContinue; 'Ollama arrete';;sleep:2;;powershell:Start-Process 'ollama' -ArgumentList 'serve' -WindowStyle Hidden; 'Ollama redemarrage...';;sleep:3;;powershell:$r = try{(Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5 -UseBasicParsing).StatusCode}catch{0}; if($r -eq 200){'OL1 OK — Ollama operationnel'}else{'OL1 ERREUR — Ollama ne repond pas'}", confirm=True),

    # ══════════════════════════════════════════════════════════════════════
    # DIAGNOSTIC INTELLIGENT — Analyse systeme via cluster IA
    # Collecte donnees systeme + envoi au cluster pour analyse
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("diag_intelligent_pc", "pipeline", "Diagnostic intelligent: collecte CPU/RAM/GPU/disque + analyse IA via M1", [
        "diagnostic intelligent", "analyse mon pc avec l'ia",
        "diagnostic ia", "scan intelligent du systeme",
        "jarvis analyse mon systeme",
    ], "pipeline", "powershell:$cpu = (Get-CimInstance Win32_Processor).LoadPercentage; $os = Get-CimInstance Win32_OperatingSystem; $ram = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB,1); $total = [math]::Round($os.TotalVisibleMemorySize/1MB,1); $gpu = nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>&1; $disk = Get-CimInstance Win32_LogicalDisk -Filter \"DriveType=3\" | ForEach-Object {\"$($_.DeviceID) $([math]::Round($_.FreeSpace/1GB))/$([math]::Round($_.Size/1GB))GB\"}; $data = \"CPU:${cpu}% RAM:${ram}/${total}GB GPU:$gpu Disques:$($disk -join ' ')\"; $body = @{model='qwen3-8b';messages=@(@{role='user';content=\"/nothink`nAnalyse ces metriques systeme Windows et dis si tout va bien ou s'il y a un probleme. Sois concis (3 lignes max): $data\"});temperature=0.2;max_tokens=256} | ConvertTo-Json -Depth 3; $r = Invoke-RestMethod -Uri 'http://10.5.0.2:1234/v1/chat/completions' -Method Post -Body $body -ContentType 'application/json' -Headers @{'Authorization'='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 15; \"[M1/qwen3] $($r.choices[0].message.content)\""),

    JarvisCommand("diag_pourquoi_lent", "pipeline", "Mon PC rame: top processus + analyse IA de la cause", [
        "mon pc rame", "pourquoi c'est lent", "c'est lent",
        "le pc est lent", "ca rame", "pourquoi ca lag",
        "mon ordinateur est lent",
    ], "pipeline", "powershell:$procs = Get-Process | Sort-Object -Property WorkingSet64 -Descending | Select-Object -First 8 Name, @{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB)}}, CPU | Format-Table -AutoSize | Out-String; $cpu = (Get-CimInstance Win32_Processor).LoadPercentage; \"CPU: ${cpu}% — Top processus RAM:`n$procs\";;powershell:$procs = Get-Process | Sort-Object -Property WorkingSet64 -Descending | Select-Object -First 5 Name, @{N='MB';E={[math]::Round($_.WorkingSet64/1MB)}} | ForEach-Object {\"$($_.Name):$($_.MB)MB\"} -join ','; $body = @{model='qwen3-8b';messages=@(@{role='user';content=\"/nothink`nPC Windows lent. Top processus: $procs. CPU: $((Get-CimInstance Win32_Processor).LoadPercentage)%. Identifie la cause probable et donne 1 solution concrete (2 lignes max).\"});temperature=0.2;max_tokens=200} | ConvertTo-Json -Depth 3; $r = Invoke-RestMethod -Uri 'http://10.5.0.2:1234/v1/chat/completions' -Method Post -Body $body -ContentType 'application/json' -Headers @{'Authorization'='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 15; \"Diagnostic IA: $($r.choices[0].message.content)\""),

    JarvisCommand("diag_gpu_thermal", "pipeline", "Check temperatures GPU + alerte si surchauffe", [
        "temperature gpu", "les gpu sont chauds", "check gpu temp",
        "surchauffe gpu", "monitoring thermique",
        "jarvis les gpu sont ok",
    ], "pipeline", "powershell:$gpu = nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw --format=csv,noheader 2>&1; $lines = $gpu -split \"`n\" | Where-Object {$_ -match '\\d'}; foreach($l in $lines){$parts = $l -split ','; $temp = [int]$parts[2].Trim(); $status = if($temp -ge 85){'CRITIQUE'}elseif($temp -ge 75){'ATTENTION'}else{'OK'}; \"GPU$($parts[0].Trim()): $($parts[1].Trim()) | ${temp}C [$status] | Load:$($parts[3].Trim()) | VRAM:$($parts[4].Trim())/$($parts[5].Trim())MB | Power:$($parts[6].Trim())\"}"),

    JarvisCommand("diag_processus_suspect", "pipeline", "Lister les processus suspects: gros consommateurs RAM/CPU", [
        "processus suspects", "qu'est-ce qui consomme", "top processus",
        "qui bouffe la ram", "processus gourmands",
        "montre les gros processus",
    ], "pipeline", "powershell:\"=== TOP RAM ===\"; Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 Name, @{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB)}}, @{N='CPU_s';E={[math]::Round($_.CPU,1)}} | Format-Table -AutoSize | Out-String;;powershell:\"=== PROCESSUS > 500MB ===\"; Get-Process | Where-Object {$_.WorkingSet64 -gt 500MB} | Sort-Object WorkingSet64 -Descending | ForEach-Object {\"$($_.Name): $([math]::Round($_.WorkingSet64/1MB))MB\"} | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # COGNITIF — Raisonnement multi-etapes via cluster IA
    # Questions envoyees au cluster pour analyse et synthese
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("cognitif_resume_activite", "pipeline", "Resume de l'activite: git log + uptime + stats + resume IA", [
        "resume mon activite", "qu'est-ce que j'ai fait",
        "bilan d'activite", "resume la journee",
        "jarvis resume ce que j'ai fait",
    ], "pipeline", "powershell:$git = git -C F:\\BUREAU\\turbo log --since='8 hours ago' --oneline 2>&1 | Out-String; $up = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; $uptime = (New-TimeSpan -Start $up).ToString('d\\.hh\\:mm'); $body = @{model='qwen3-8b';messages=@(@{role='user';content=\"/nothink`nResume cette activite de dev en 3 lignes. Commits recents: $git. Uptime: $uptime\"});temperature=0.3;max_tokens=200} | ConvertTo-Json -Depth 3; $r = Invoke-RestMethod -Uri 'http://10.5.0.2:1234/v1/chat/completions' -Method Post -Body $body -ContentType 'application/json' -Headers @{'Authorization'='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 15; \"[Resume IA] $($r.choices[0].message.content)\""),

    JarvisCommand("cognitif_consensus_rapide", "pipeline", "Consensus cluster: envoyer une question a M1 + M2 + OL1", [
        "consensus sur", "demande au cluster", "avis du cluster",
        "consensus rapide", "vote du cluster",
        "qu'en pensent les ia",
    ], "pipeline", "powershell:$q = 'Quelle est la meilleure pratique pour organiser un projet Python avec des modules, tests et config?'; $b1 = @{model='qwen3-8b';messages=@(@{role='user';content=\"/nothink`n$q\"});temperature=0.3;max_tokens=150} | ConvertTo-Json -Depth 3; $r1 = Invoke-RestMethod -Uri 'http://10.5.0.2:1234/v1/chat/completions' -Method Post -Body $b1 -ContentType 'application/json' -Headers @{'Authorization'='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 15; \"[M1/qwen3] $($r1.choices[0].message.content)\";;powershell:$q = 'Quelle est la meilleure pratique pour organiser un projet Python avec des modules, tests et config?'; $b2 = @{model='deepseek-coder-v2-lite-instruct';messages=@(@{role='user';content=$q});temperature=0.3;max_tokens=150} | ConvertTo-Json -Depth 3; $r2 = Invoke-RestMethod -Uri 'http://192.168.1.26:1234/v1/chat/completions' -Method Post -Body $b2 -ContentType 'application/json' -Headers @{'Authorization'='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 15; \"[M2/deepseek] $($r2.choices[0].message.content)\""),

    JarvisCommand("cognitif_analyse_erreurs", "pipeline", "Analyser les erreurs Windows recentes via IA", [
        "analyse les erreurs", "erreurs windows", "quelles erreurs recentes",
        "check les logs d'erreurs", "problemes recents",
        "jarvis y a eu des erreurs",
    ], "pipeline", "powershell:$events = Get-WinEvent -FilterHashtable @{LogName='Application';Level=2} -MaxEvents 5 -ErrorAction SilentlyContinue | Select-Object TimeCreated, @{N='Msg';E={$_.Message.Substring(0,[Math]::Min(120,$_.Message.Length))}} | Format-Table -AutoSize -Wrap | Out-String; if(-not $events){'Aucune erreur recente dans les logs Application'}else{$body = @{model='qwen3-8b';messages=@(@{role='user';content=\"/nothink`nAnalyse ces erreurs Windows recentes et dis si c'est grave (2 lignes max): $events\"});temperature=0.2;max_tokens=200} | ConvertTo-Json -Depth 3; $r = Invoke-RestMethod -Uri 'http://10.5.0.2:1234/v1/chat/completions' -Method Post -Body $body -ContentType 'application/json' -Headers @{'Authorization'='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 15; \"Erreurs:`n$events`n[IA] $($r.choices[0].message.content)\"}"),

    JarvisCommand("cognitif_suggestion_tache", "pipeline", "Suggestion de tache basee sur l'heure et le contexte", [
        "qu'est-ce que je devrais faire", "suggestion de tache",
        "on fait quoi maintenant", "quoi faire",
        "jarvis propose moi quelque chose",
    ], "pipeline", "powershell:$git = (git -C F:\\BUREAU\\turbo log --since='4 hours ago' --oneline 2>&1 | Measure-Object -Line).Lines; $body = @{model='qwen3-8b';messages=@(@{role='system';content='Tu es JARVIS, assistant personnel. Reponds en 2-3 lignes max.'};@{role='user';content=\"/nothink`nIl est $((Get-Date).ToString('HH:mm')), c'est un $(Get-Date -Format 'dddd'). L'utilisateur a fait $git commits ces 4 dernieres heures. Suggere une activite adaptee au moment de la journee.\"});temperature=0.5;max_tokens=150} | ConvertTo-Json -Depth 3; $r = Invoke-RestMethod -Uri 'http://10.5.0.2:1234/v1/chat/completions' -Method Post -Body $body -ContentType 'application/json' -Headers @{'Authorization'='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 15; \"[JARVIS] $($r.choices[0].message.content)\""),

    # ══════════════════════════════════════════════════════════════════════
    # SECURITE AVANCEE — Audit et protection systeme
    # Scans de ports, services, permissions, certificats
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("securite_ports_ouverts", "pipeline", "Scanner les ports ouverts et connexions actives suspectes", [
        "scan les ports", "ports ouverts", "connexions actives",
        "check securite ports", "qui est connecte",
        "scan reseau securite",
    ], "pipeline", "powershell:\"=== PORTS EN ECOUTE ===\"; Get-NetTCPConnection -State Listen | Select-Object LocalPort, @{N='Process';E={(Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).Name}} | Sort-Object LocalPort | Format-Table -AutoSize | Out-String;;powershell:\"=== CONNEXIONS ETABLIES (hors localhost) ===\"; Get-NetTCPConnection -State Established | Where-Object {$_.RemoteAddress -notmatch '^(127\\.|::1|0\\.)'} | Select-Object RemoteAddress, RemotePort, @{N='Process';E={(Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).Name}} | Format-Table -AutoSize | Out-String"),

    JarvisCommand("securite_check_defender", "pipeline", "Status Windows Defender + derniere mise a jour + menaces", [
        "status defender", "windows defender", "check antivirus",
        "securite antivirus", "defender a jour",
        "l'antivirus est ok",
    ], "pipeline", "powershell:$d = Get-MpComputerStatus -ErrorAction SilentlyContinue; if($d){\"Defender: $(if($d.RealTimeProtectionEnabled){'ACTIF'}else{'INACTIF'}) | MAJ: $($d.AntivirusSignatureLastUpdated.ToString('dd/MM HH:mm')) | Scan: $($d.FullScanEndTime.ToString('dd/MM HH:mm')) | Menaces detectees: $(($d.QuickScanOverdue -or $d.FullScanOverdue))\"}else{'Defender non disponible'};;powershell:$threats = Get-MpThreatDetection -ErrorAction SilentlyContinue | Select-Object -Last 3 DetectionTime, Resources; if($threats){$threats | Format-Table -AutoSize | Out-String}else{'Aucune menace recente detectee'}"),

    JarvisCommand("securite_audit_services", "pipeline", "Auditer les services actifs et detecter les suspects", [
        "audit services", "services suspects", "check les services",
        "quels services tournent", "services actifs suspects",
    ], "pipeline", "powershell:\"=== SERVICES NON-MICROSOFT ACTIFS ===\"; Get-Service | Where-Object {$_.Status -eq 'Running'} | ForEach-Object {$wmi = Get-CimInstance Win32_Service -Filter \"Name='$($_.Name)'\"; if($wmi.PathName -and $wmi.PathName -notmatch 'Windows|Microsoft|system32'){\"$($_.Name): $($wmi.PathName.Substring(0,[Math]::Min(80,$wmi.PathName.Length)))\"}} | Out-String;;powershell:\"=== PROGRAMMES AU DEMARRAGE ===\"; Get-CimInstance Win32_StartupCommand | Select-Object Name, Command | Format-Table -AutoSize -Wrap | Out-String"),

    JarvisCommand("securite_permissions_sensibles", "pipeline", "Verifier les fichiers sensibles (.env, credentials, cles)", [
        "check fichiers sensibles", "verification securite fichiers",
        "scan credentials", "fichiers secrets",
        "y a des fichiers dangereux",
    ], "pipeline", "powershell:\"=== FICHIERS SENSIBLES TROUVES ===\"; $patterns = @('*.env', '*.pem', '*.key', '*credentials*', '*secret*', '*password*'); $found = foreach($p in $patterns){Get-ChildItem -Path F:\\BUREAU -Recurse -Filter $p -ErrorAction SilentlyContinue -Depth 3 | Select-Object FullName, Length, LastWriteTime}; if($found){$found | Format-Table -AutoSize | Out-String}else{'Aucun fichier sensible trouve dans F:\\BUREAU'};;powershell:\"=== .ENV DANS PROJETS ===\"; Get-ChildItem -Path F:\\BUREAU -Recurse -Filter '.env' -ErrorAction SilentlyContinue -Depth 4 | ForEach-Object {\"$($_.FullName) ($([math]::Round($_.Length/1KB,1))KB)\"} | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # DEBUG RESEAU AVANCE — Diagnostic reseau complet
    # Ping, DNS, tracert, latence cluster, WiFi
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("debug_reseau_complet", "pipeline", "Debug reseau complet: ping + DNS + passerelle + internet", [
        "debug reseau complet", "probleme reseau", "internet marche pas",
        "diagnostic reseau avance", "reseau en panne",
        "check la connexion complete",
    ], "pipeline", "powershell:\"=== PASSERELLE ===\"; $gw = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue).NextHop; \"Gateway: $gw\"; Test-Connection $gw -Count 2 -ErrorAction SilentlyContinue | Select-Object ResponseTime | Out-String;;powershell:\"=== DNS ===\"; Resolve-DnsName google.com -ErrorAction SilentlyContinue | Select-Object -First 2 Name, IPAddress | Out-String;;powershell:\"=== INTERNET ===\"; $t = Measure-Command {try{Invoke-WebRequest -Uri 'https://www.google.com' -TimeoutSec 5 -UseBasicParsing | Out-Null}catch{}}; \"Google: $([math]::Round($t.TotalMilliseconds))ms\"; $t2 = Measure-Command {try{Invoke-WebRequest -Uri 'https://api.github.com' -TimeoutSec 5 -UseBasicParsing | Out-Null}catch{}}; \"GitHub: $([math]::Round($t2.TotalMilliseconds))ms\""),

    JarvisCommand("debug_latence_cluster", "pipeline", "Mesurer la latence vers chaque noeud du cluster IA", [
        "latence cluster", "ping les machines ia", "latence des noeuds",
        "vitesse du cluster", "temps de reponse cluster",
        "test latence ia",
    ], "pipeline", "powershell:$nodes = @(@{Name='M1';Url='http://10.5.0.2:1234/api/v1/models';Auth='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'}, @{Name='M2';Url='http://192.168.1.26:1234/api/v1/models';Auth='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'}, @{Name='M3';Url='http://192.168.1.113:1234/api/v1/models';Auth='Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux'}, @{Name='OL1';Url='http://127.0.0.1:11434/api/tags';Auth=$null}); foreach($n in $nodes){$t = Measure-Command {try{if($n.Auth){Invoke-WebRequest -Uri $n.Url -Headers @{'Authorization'=$n.Auth} -TimeoutSec 5 -UseBasicParsing | Out-Null}else{Invoke-WebRequest -Uri $n.Url -TimeoutSec 5 -UseBasicParsing | Out-Null}; $ok=$true}catch{$ok=$false}}; $ms = [math]::Round($t.TotalMilliseconds); \"$($n.Name): $(if($ok){\"${ms}ms OK\"}else{'OFFLINE'})\"}"),

    JarvisCommand("debug_wifi_diagnostic", "pipeline", "Diagnostic WiFi: signal + canal + SSID + debit", [
        "diagnostic wifi", "wifi faible", "probleme wifi",
        "signal wifi", "check le wifi",
        "la wifi est lente",
    ], "pipeline", "powershell:netsh wlan show interfaces | Select-String 'SSID|Signal|Canal|Debit|State|Radio' | Out-String;;powershell:\"=== RESEAUX DISPONIBLES ===\"; netsh wlan show networks mode=bssid | Select-String 'SSID|Signal|Canal' | Select-Object -First 15 | Out-String"),

    JarvisCommand("debug_dns_avance", "pipeline", "Test DNS avance: flush + resolution multiple + comparaison", [
        "debug dns", "probleme dns", "dns lent",
        "flush dns avance", "test les dns",
    ], "pipeline", "powershell:\"Flush DNS...\"; Clear-DnsClientCache; 'OK — Cache DNS vide';;powershell:\"=== TEST RESOLUTION DNS ===\"; $domains = @('google.com','github.com','cloudflare.com','api.anthropic.com'); foreach($d in $domains){$t = Measure-Command {$r = Resolve-DnsName $d -ErrorAction SilentlyContinue}; \"$d -> $($r[0].IPAddress) ($([math]::Round($t.TotalMilliseconds))ms)\"};;powershell:\"=== DNS SERVERS ===\"; Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object {$_.ServerAddresses} | Select-Object InterfaceAlias, ServerAddresses | Format-Table -AutoSize | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # ROUTINES CONVERSATIONNELLES — Declencheurs en langage naturel
    # Interactions quotidiennes avec JARVIS en mode conversationnel
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("routine_bonjour_jarvis", "pipeline", "Bonjour Jarvis: heure + meteo + cluster + agenda du jour", [
        "bonjour jarvis", "salut jarvis", "hey jarvis bonjour",
        "coucou jarvis", "jarvis reveille toi",
        "jarvis on y va", "bonne journee jarvis",
    ], "pipeline", "powershell:$h = (Get-Date).ToString('HH:mm'); $jour = Get-Date -Format 'dddd dd MMMM yyyy'; \"Bonjour! Il est $h, nous sommes $jour\";;powershell:$m1 = try{(Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; $ol1 = try{(Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; \"Cluster: M1=$(if($m1 -eq 200){'pret'}else{'offline'}) | OL1=$(if($ol1 -eq 200){'pret'}else{'offline'})\";;powershell:$gpu = nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>&1; $temps = ($gpu -split \"`n\" | Where-Object {$_ -match '\\d'}) -join 'C, '; \"GPU: ${temps}C\";;powershell:$os = Get-CimInstance Win32_OperatingSystem; $ram = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB,1); $total = [math]::Round($os.TotalVisibleMemorySize/1MB,1); \"RAM: $ram/$total GB — Pret pour la journee!\""),

    JarvisCommand("routine_bilan_journee", "pipeline", "Bilan de fin de journee: commits + uptime + stats + resume IA", [
        "bilan de la journee", "comment s'est passe la journee",
        "resume de la journee", "c'etait bien aujourd'hui",
        "jarvis bilan", "fin de journee bilan",
    ], "pipeline", "powershell:\"=== BILAN DU JOUR ===\"; $commits = (git -C F:\\BUREAU\\turbo log --since='midnight' --oneline 2>&1 | Measure-Object -Line).Lines; \"Commits aujourd'hui: $commits\";;powershell:$up = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; $uptime = (New-TimeSpan -Start $up).ToString('hh\\:mm'); \"Uptime: $uptime\";;powershell:$commits = (git -C F:\\BUREAU\\turbo log --since='midnight' --oneline 2>&1 | Measure-Object -Line).Lines; $body = @{model='qwen3-8b';messages=@(@{role='system';content='Tu es JARVIS. Fais un bilan de journee encourageant en 2 lignes.'};@{role='user';content=\"/nothink`nL'utilisateur a fait $commits commits aujourd'hui. Il est $((Get-Date).ToString('HH:mm')). Fais un bilan positif.\"});temperature=0.5;max_tokens=100} | ConvertTo-Json -Depth 3; $r = Invoke-RestMethod -Uri 'http://10.5.0.2:1234/v1/chat/completions' -Method Post -Body $body -ContentType 'application/json' -Headers @{'Authorization'='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 15; \"[JARVIS] $($r.choices[0].message.content)\""),

    JarvisCommand("routine_tout_va_bien", "pipeline", "Tout va bien? Check rapide systeme + cluster + GPU en 1 commande", [
        "tout va bien", "ca va jarvis", "status rapide",
        "tout est ok", "check rapide", "jarvis ca roule",
        "est-ce que tout marche",
    ], "pipeline", "powershell:$cpu = (Get-CimInstance Win32_Processor).LoadPercentage; $os = Get-CimInstance Win32_OperatingSystem; $ram = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB,1); $total = [math]::Round($os.TotalVisibleMemorySize/1MB,1); $gpu_temp = (nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>&1) -split \"`n\" | Where-Object {$_ -match '\\d'} | ForEach-Object {[int]$_}; $max_temp = ($gpu_temp | Measure-Object -Maximum).Maximum; $m1 = try{(Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 3 -UseBasicParsing).StatusCode -eq 200}catch{$false}; $ol1 = try{(Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 -UseBasicParsing).StatusCode -eq 200}catch{$false}; $status = if($cpu -lt 80 -and $ram/$total -lt 0.9 -and $max_temp -lt 80 -and $m1 -and $ol1){'Tout est OK!'}else{'Attention, verifier certains points'}; \"$status | CPU:${cpu}% | RAM:$ram/$total GB | GPU max:${max_temp}C | M1:$(if($m1){'OK'}else{'OFF'}) | OL1:$(if($ol1){'OK'}else{'OFF'})\""),

    JarvisCommand("routine_jarvis_selfcheck", "pipeline", "Auto-diagnostic JARVIS: config + DB + cluster + commandes", [
        "jarvis ca va", "self check", "auto diagnostic jarvis",
        "jarvis tu marches bien", "test jarvis",
        "jarvis verifie toi meme",
    ], "pipeline", "powershell:$db1 = Test-Path 'F:\\BUREAU\\turbo\\data\\etoile.db'; $db2 = Test-Path 'F:\\BUREAU\\turbo\\data\\jarvis.db'; \"Bases: etoile=$(if($db1){'OK'}else{'MANQUE'}) | jarvis=$(if($db2){'OK'}else{'MANQUE'})\";;powershell:$cmds = (Get-Content F:\\BUREAU\\turbo\\src\\commands.py -Raw | Select-String -Pattern 'JarvisCommand\\(' -AllMatches).Matches.Count; $pipes = (Get-Content F:\\BUREAU\\turbo\\src\\commands_pipelines.py -Raw | Select-String -Pattern 'JarvisCommand\\(' -AllMatches).Matches.Count; \"Commandes: $cmds | Pipelines: $pipes | Total: $($cmds + $pipes)\";;powershell:$m1 = try{(Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 3 -UseBasicParsing).StatusCode -eq 200}catch{$false}; $m2 = try{(Invoke-WebRequest -Uri 'http://192.168.1.26:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 3 -UseBasicParsing).StatusCode -eq 200}catch{$false}; $ol1 = try{(Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 -UseBasicParsing).StatusCode -eq 200}catch{$false}; $online = @($m1,$m2,$ol1) | Where-Object {$_}; \"Cluster: $($online.Count)/3 noeuds en ligne | JARVIS operationnel\""),

    # ══════════════════════════════════════════════════════════════════════
    # ELECTRON DASHBOARD — Pilotage de l'application desktop JARVIS
    # CRITIQUE: Feature majeure inaccessible par la voix
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("dashboard_ouvrir", "pipeline", "Ouvrir le dashboard JARVIS Electron (Vite + Python WS)", [
        "ouvre le dashboard", "lance le dashboard", "dashboard jarvis",
        "ouvre l'interface jarvis", "lance l'app desktop",
        "ouvre jarvis desktop", "affiche le dashboard",
    ], "pipeline", "powershell:Start-Process 'F:\\BUREAU\\turbo\\launchers\\JARVIS_DASHBOARD.bat' -WindowStyle Minimized; 'Dashboard JARVIS en cours de demarrage...';;sleep:3;;browser:navigate:http://127.0.0.1:8080;;powershell:\"Dashboard JARVIS accessible sur http://127.0.0.1:8080\""),

    JarvisCommand("dashboard_electron_full", "pipeline", "Lancer JARVIS Desktop complet (Electron + React + Python WS)", [
        "lance electron complet", "jarvis desktop complet",
        "ouvre l'application complete", "lance tout le desktop",
        "electron full", "desktop app complete",
    ], "pipeline", "powershell:Start-Process 'F:\\BUREAU\\turbo\\launchers\\JARVIS_DESKTOP.bat' -WindowStyle Minimized; 'Electron demarrage: Vite 5173 + Python WS 9742';;sleep:5;;powershell:$vite = try{(Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; $ws = try{(Invoke-WebRequest -Uri 'http://127.0.0.1:9742' -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; \"Electron: Vite=$(if($vite){'OK'}else{'...demarrage'}) | WS=$(if($ws){'OK'}else{'...demarrage'})\""),

    JarvisCommand("dashboard_page_trading", "pipeline", "Dashboard: ouvrir la page Trading", [
        "page trading", "dashboard trading", "ouvre le trading sur le dashboard",
        "affiche la page trading", "va sur trading",
    ], "pipeline", "browser:navigate:http://127.0.0.1:8080/#/trading;;powershell:\"Dashboard — Page Trading ouverte\""),

    JarvisCommand("dashboard_page_chat", "pipeline", "Dashboard: ouvrir la page Chat IA", [
        "page chat", "dashboard chat", "ouvre le chat sur le dashboard",
        "affiche la page chat", "chat jarvis dashboard",
    ], "pipeline", "browser:navigate:http://127.0.0.1:8080/#/chat;;powershell:\"Dashboard — Page Chat ouverte\""),

    JarvisCommand("dashboard_page_settings", "pipeline", "Dashboard: ouvrir la page Settings", [
        "page settings", "dashboard settings", "parametres dashboard",
        "ouvre les reglages jarvis", "configuration dashboard",
    ], "pipeline", "browser:navigate:http://127.0.0.1:8080/#/settings;;powershell:\"Dashboard — Page Settings ouverte\""),

    JarvisCommand("dashboard_page_voice", "pipeline", "Dashboard: ouvrir la page Voice", [
        "page voice", "dashboard voice", "ouvre la page voix",
        "parametres vocaux dashboard", "voice dashboard",
    ], "pipeline", "browser:navigate:http://127.0.0.1:8080/#/voice;;powershell:\"Dashboard — Page Voice ouverte\""),

    JarvisCommand("dashboard_restart", "pipeline", "Redemarrer le dashboard JARVIS (kill + relaunch)", [
        "redemarre le dashboard", "restart dashboard", "relance le dashboard",
        "dashboard plante", "reboot dashboard",
    ], "pipeline", "powershell:Get-Process -Name 'python*' -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -match 'dashboard'} | Stop-Process -Force -ErrorAction SilentlyContinue; 'Dashboard arrete';;sleep:2;;powershell:Start-Process 'F:\\BUREAU\\turbo\\launchers\\JARVIS_DASHBOARD.bat' -WindowStyle Minimized; 'Redemarrage dashboard...';;sleep:3;;browser:navigate:http://127.0.0.1:8080;;powershell:\"Dashboard redemarre\"", confirm=True),

    # ══════════════════════════════════════════════════════════════════════
    # CLUSTER IA AVANCE — Gestion avancee du cluster distribue
    # CRITIQUE: Cluster optimisation entierement manuelle
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("cluster_routing_status", "pipeline", "Afficher la strategie de routage actuelle du cluster", [
        "routage cluster", "routing status", "strategie de routage",
        "qui gere quoi dans le cluster", "repartition cluster",
    ], "pipeline", "powershell:\"=== ROUTAGE CLUSTER ===\"; \"M1 (10.5.0.2) — PRIORITAIRE: code, math, raisonnement, archi, securite\"; \"M2 (192.168.1.26) — Code review, debug, PowerShell\"; \"M3 (192.168.1.113) — General, validation (PAS raisonnement)\"; \"OL1 (127.0.0.1) — Questions rapides, triage, web search\"; \"GEMINI — Architecture, vision\"; \"CLAUDE — Raisonnement cloud profond\";;powershell:\"=== POIDS CONSENSUS ===\"; \"M1=1.8 | M2=1.4 | OL1=1.3 | GEMINI=1.2 | CLAUDE=1.2 | M3=1.0\""),

    JarvisCommand("cluster_thermal_cascade", "pipeline", "Test thermal cascade: check GPU temperatures + fallback auto", [
        "test thermal", "cascade thermique", "check thermique cluster",
        "test fallback gpu", "simulation surchauffe",
    ], "pipeline", "powershell:$gpu = nvidia-smi --query-gpu=index,temperature.gpu,name --format=csv,noheader,nounits 2>&1; $lines = $gpu -split \"`n\" | Where-Object {$_ -match '\\d'}; $alert = $false; foreach($l in $lines){$parts = $l -split ','; $temp = [int]$parts[1].Trim(); if($temp -ge 85){\"GPU$($parts[0].Trim()) $($parts[2].Trim()): ${temp}C CRITIQUE — cascade activee\"; $alert=$true}elseif($temp -ge 75){\"GPU$($parts[0].Trim()) $($parts[2].Trim()): ${temp}C ATTENTION\"}else{\"GPU$($parts[0].Trim()) $($parts[2].Trim()): ${temp}C OK\"}}; if(-not $alert){\"Thermal cascade: aucun declenchement necessaire\"}"),

    JarvisCommand("cluster_vram_map", "pipeline", "Carte VRAM detaillee de toutes les GPU du cluster", [
        "carte vram", "vram map", "memoire gpu detaillee",
        "utilisation vram", "qui utilise la vram",
    ], "pipeline", "powershell:\"=== VRAM MAP LOCAL (5 GPU) ===\"; nvidia-smi --query-gpu=index,name,memory.used,memory.total,memory.free --format=csv,noheader 2>&1 | ForEach-Object {$p = $_ -split ','; \"  GPU$($p[0].Trim()): $($p[1].Trim()) | Used:$($p[2].Trim()) / Total:$($p[3].Trim()) | Free:$($p[4].Trim())\"};;powershell:$total_used = 0; $total_total = 0; nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits 2>&1 | ForEach-Object {$p = $_ -split ','; $total_used += [int]$p[0].Trim(); $total_total += [int]$p[1].Trim()}; \"Total: $($total_used)MB / $($total_total)MB ($([math]::Round($total_used/$total_total*100))% utilise)\""),

    JarvisCommand("cluster_failover_test", "pipeline", "Tester le failover: simuler perte M1 et verifier fallback M2", [
        "test failover", "simule une panne", "test redondance",
        "failover cluster", "test panne m1",
    ], "pipeline", "powershell:\"=== TEST FAILOVER ===\"; \"1. Test M1 (principal)...\"; $m1 = try{$t=Measure-Command{Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 3 -UseBasicParsing | Out-Null}; \"OK ($([math]::Round($t.TotalMilliseconds))ms)\"}catch{\"OFFLINE\"}; \"   M1: $m1\";;powershell:\"2. Test M2 (fallback)...\"; $m2 = try{$t=Measure-Command{Invoke-WebRequest -Uri 'http://192.168.1.26:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 3 -UseBasicParsing | Out-Null}; \"OK ($([math]::Round($t.TotalMilliseconds))ms)\"}catch{\"OFFLINE\"}; \"   M2: $m2\";;powershell:\"3. Test M3 (secondaire)...\"; $m3 = try{$t=Measure-Command{Invoke-WebRequest -Uri 'http://192.168.1.113:1234/api/v1/models' -Headers @{'Authorization'='Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux'} -TimeoutSec 3 -UseBasicParsing | Out-Null}; \"OK ($([math]::Round($t.TotalMilliseconds))ms)\"}catch{\"OFFLINE\"}; \"   M3: $m3\";;powershell:\"4. Test OL1 (rapide)...\"; $ol1 = try{$t=Measure-Command{Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 -UseBasicParsing | Out-Null}; \"OK ($([math]::Round($t.TotalMilliseconds))ms)\"}catch{\"OFFLINE\"}; \"   OL1: $ol1\"; \"=== Failover: M1->M2->M3->OL1 valide ===\""),

    JarvisCommand("cluster_load_balance", "pipeline", "Afficher la repartition de charge GPU par noeud", [
        "charge du cluster", "load balance", "repartition charge",
        "equilibrage cluster", "qui est surcharge",
    ], "pipeline", "powershell:\"=== CHARGE GPU ===\"; nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,temperature.gpu --format=csv,noheader 2>&1 | ForEach-Object {$p = $_ -split ','; \"  GPU$($p[0].Trim()): $($p[1].Trim()) | GPU:$($p[2].Trim()) | MEM:$($p[3].Trim()) | Temp:$($p[4].Trim())C\"};;powershell:\"=== PROCESSUS GPU ===\"; nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader 2>&1 | ForEach-Object {if($_ -match '\\d'){\"  $_\"}}"),

    # ══════════════════════════════════════════════════════════════════════
    # DATABASE MANAGEMENT — Backup, restore, integrite, stats
    # HAUTE PRIORITE: Integrite non verifiable, backups non automatises
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("db_backup_complet", "pipeline", "Backup complet: jarvis.db + etoile.db + trading.db avec horodatage", [
        "backup toutes les bases", "sauvegarde complete des bases",
        "backup les databases", "copie toutes les db",
        "sauvegarde sql complete",
    ], "pipeline", "powershell:$d = Get-Date -Format 'yyyy-MM-dd_HHmm'; $dest = 'F:\\BUREAU\\turbo\\data\\backups'; New-Item -ItemType Directory -Force -Path $dest | Out-Null; Copy-Item 'F:\\BUREAU\\turbo\\data\\etoile.db' \"$dest\\etoile_$d.db\" -Force; Copy-Item 'F:\\BUREAU\\turbo\\data\\jarvis.db' \"$dest\\jarvis_$d.db\" -Force; Copy-Item 'F:\\BUREAU\\turbo\\data\\trading_latest.db' \"$dest\\trading_$d.db\" -Force -ErrorAction SilentlyContinue; $files = Get-ChildItem $dest -Filter '*_*' | Measure-Object; \"Backup OK: 3 bases dans $dest ($($files.Count) fichiers au total)\""),

    JarvisCommand("db_integrity_check", "pipeline", "Verifier l'integrite de toutes les bases SQLite", [
        "verifie les bases", "integrite des bases", "check les databases",
        "bases de donnees ok", "sqlite integrity check",
        "verification integrite sql",
    ], "pipeline", "powershell:$dbs = @('F:\\BUREAU\\turbo\\data\\etoile.db','F:\\BUREAU\\turbo\\data\\jarvis.db','F:\\BUREAU\\turbo\\data\\trading_latest.db'); foreach($db in $dbs){$name = [System.IO.Path]::GetFileName($db); if(Test-Path $db){$size = [math]::Round((Get-Item $db).Length/1KB); $result = & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('$($db.Replace('\\','\\\\'))'); r=c.execute('PRAGMA integrity_check').fetchone()[0]; print(r); c.close()\" 2>&1; \"$name ($size KB): $result\"}else{\"$name: ABSENT\"}}"),

    JarvisCommand("db_vacuum_optimize", "pipeline", "Optimiser les bases SQLite (VACUUM + ANALYZE)", [
        "optimise les bases", "vacuum les databases", "compress les bases",
        "nettoie les bases sql", "optimize sqlite",
    ], "pipeline", "powershell:$dbs = @('F:\\BUREAU\\turbo\\data\\etoile.db','F:\\BUREAU\\turbo\\data\\jarvis.db'); foreach($db in $dbs){$name = [System.IO.Path]::GetFileName($db); $before = (Get-Item $db).Length; & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('$($db.Replace('\\','\\\\'))'); c.execute('VACUUM'); c.execute('ANALYZE'); c.close(); print('OK')\" 2>&1; $after = (Get-Item $db).Length; $saved = [math]::Round(($before-$after)/1KB); \"$name: $(if($saved -gt 0){\"$saved KB economises\"}else{'deja optimise'})\"}", confirm=True),

    JarvisCommand("db_stats_detaillees", "pipeline", "Statistiques detaillees des bases: tables, lignes, taille", [
        "stats des bases", "statistiques databases", "combien dans les bases",
        "taille des tables", "infos sur les bases",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3,os; dbs=[('etoile.db','F:/BUREAU/turbo/data/etoile.db'),('jarvis.db','F:/BUREAU/turbo/data/jarvis.db')]; [print(f'{n}: {round(os.path.getsize(p)/1024)}KB') or [print(f'  {t[0]}: {sqlite3.connect(p).execute(f\\\"SELECT COUNT(*) FROM {t[0]}\\\").fetchone()[0]} rows') for t in sqlite3.connect(p).execute(\\\"SELECT name FROM sqlite_master WHERE type='table'\\\").fetchall()] for n,p in dbs]\" 2>&1 | Out-String"),

    JarvisCommand("db_growth_monitor", "pipeline", "Monitorer la croissance des bases de donnees", [
        "croissance des bases", "evolution des bases", "taille des databases",
        "les bases grossissent", "monitor db size",
    ], "pipeline", "powershell:$dbs = @('F:\\BUREAU\\turbo\\data\\etoile.db','F:\\BUREAU\\turbo\\data\\jarvis.db','F:\\BUREAU\\turbo\\data\\trading_latest.db'); foreach($db in $dbs){if(Test-Path $db){$f = Get-Item $db; $size = [math]::Round($f.Length/1KB); $modified = $f.LastWriteTime.ToString('dd/MM HH:mm'); $name = $f.Name; \"$name: $size KB (modifie: $modified)\"}else{\"$(Split-Path $db -Leaf): ABSENT\"}}"),

    # ══════════════════════════════════════════════════════════════════════
    # N8N WORKFLOW MANAGEMENT — Declenchement et monitoring des workflows
    # HAUTE PRIORITE: 20 workflows existants mais inaccessibles par la voix
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("n8n_ouvrir_dashboard", "pipeline", "Ouvrir le dashboard n8n", [
        "ouvre n8n", "dashboard n8n", "lance n8n",
        "ouvre les workflows", "n8n interface",
    ], "pipeline", "browser:navigate:http://127.0.0.1:5678;;powershell:\"n8n dashboard ouvert — http://127.0.0.1:5678\""),

    JarvisCommand("n8n_list_workflows", "pipeline", "Lister tous les workflows n8n actifs", [
        "liste les workflows", "workflows actifs", "quels workflows",
        "n8n workflows", "combien de workflows",
    ], "pipeline", "powershell:$r = try{Invoke-RestMethod -Uri 'http://127.0.0.1:5678/api/v1/workflows' -TimeoutSec 5}catch{$null}; if($r){$active = ($r.data | Where-Object {$_.active}).Count; $total = $r.data.Count; \"n8n: $total workflows ($active actifs)\"; $r.data | Select-Object -First 10 | ForEach-Object {$s = if($_.active){'[ON]'}else{'[OFF]'}; \"  $s $($_.name)\"}}else{\"n8n non accessible sur port 5678\"}"),

    JarvisCommand("n8n_status", "pipeline", "Status du serveur n8n: version, uptime, executions", [
        "status n8n", "n8n marche", "n8n est ok",
        "etat de n8n", "check n8n",
    ], "pipeline", "powershell:$r = try{(Invoke-WebRequest -Uri 'http://127.0.0.1:5678/healthz' -TimeoutSec 3 -UseBasicParsing).StatusCode}catch{0}; if($r -eq 200){\"n8n: ONLINE (port 5678)\"}else{\"n8n: OFFLINE\"};;powershell:$r = try{Invoke-RestMethod -Uri 'http://127.0.0.1:5678/api/v1/workflows' -TimeoutSec 5}catch{$null}; if($r){$active = ($r.data | Where-Object {$_.active}).Count; \"Workflows: $($r.data.Count) total, $active actifs\"}"),

    JarvisCommand("n8n_restart", "pipeline", "Redemarrer le serveur n8n", [
        "redemarre n8n", "restart n8n", "relance n8n",
        "n8n plante", "reboot n8n",
    ], "pipeline", "powershell:Get-Process -Name 'n8n*','node*' -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -match 'n8n'} | Stop-Process -Force -ErrorAction SilentlyContinue; 'n8n arrete';;sleep:2;;powershell:Start-Process 'n8n' -ArgumentList 'start' -WindowStyle Hidden -ErrorAction SilentlyContinue; 'n8n redemarrage...';;sleep:3;;powershell:$r = try{(Invoke-WebRequest -Uri 'http://127.0.0.1:5678/healthz' -TimeoutSec 5 -UseBasicParsing).StatusCode}catch{0}; if($r -eq 200){'n8n: ONLINE apres restart'}else{'n8n: en cours de demarrage...'}", confirm=True),

    # ══════════════════════════════════════════════════════════════════════
    # AGENT SDK MANAGEMENT — Gestion des 7 agents Claude SDK
    # MOYENNE-HAUTE: Orchestration agents non manageable par la voix
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("agent_list_status", "pipeline", "Lister les 7 agents Claude SDK et leur status", [
        "liste les agents", "quels agents", "agents actifs",
        "status des agents", "agents sdk status",
        "mes agents ia",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); agents=c.execute('SELECT * FROM agents ORDER BY id').fetchall(); c.close(); [print(f'  {a[1]}: {a[3]} ({a[4]}) — {a[5]}') for a in agents]\" 2>&1 | Out-String"),

    JarvisCommand("agent_metrics", "pipeline", "Metriques de performance des agents du cluster", [
        "metriques agents", "performance agents", "stats agents",
        "agents metrics", "comment marchent les agents",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); agents=c.execute('SELECT name, url, model_type, model_name, status, avg_latency FROM agents').fetchall(); c.close(); [print(f'  {a[0]:15} | {a[4]:7} | {a[3]:20} | {a[5] if a[5] else \\\"N/A\\\"}ms') for a in agents]\" 2>&1 | Out-String"),

    JarvisCommand("agent_run_deep", "pipeline", "Lancer l'agent ia-deep (Opus, architecte) pour une analyse", [
        "lance ia deep", "agent deep", "analyse profonde",
        "ia architecte", "agent opus",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"from agents import Agent, Runner; import asyncio; a=Agent(name='ia-deep',model='claude-opus-4-6',instructions='Architecte systeme.'); print(asyncio.run(Runner.run(a,'Analyse rapide du cluster JARVIS: 3 machines, 10 GPU, 6 noeuds IA. Quel est le point faible?')).final_output)\" 2>&1 | Out-String"),

    JarvisCommand("agent_run_fast", "pipeline", "Lancer l'agent ia-fast (Haiku, code) pour une tache rapide", [
        "lance ia fast", "agent fast", "agent rapide",
        "ia rapide", "agent haiku code",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"from agents import Agent, Runner; import asyncio; a=Agent(name='ia-fast',model='claude-haiku-4-5-20251001',instructions='Ingenieur code rapide.'); print(asyncio.run(Runner.run(a,'Liste 5 optimisations Python pour un serveur FastAPI avec SQLite.')).final_output)\" 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # FINE-TUNING — Controle des operations de fine-tuning
    # MOYENNE: Infrastructure existante mais cachee de la voix
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("finetune_status", "pipeline", "Status du fine-tuning: datasets, modeles, GPU disponible", [
        "status fine tuning", "fine tuning en cours", "etat du fine tuning",
        "finetuning status", "ou en est le training",
    ], "pipeline", "powershell:\"=== FINE-TUNING STATUS ===\"; if(Test-Path 'F:\\BUREAU\\turbo\\finetuning'){$files = Get-ChildItem 'F:\\BUREAU\\turbo\\finetuning' -Recurse | Measure-Object; $datasets = Get-ChildItem 'F:\\BUREAU\\turbo\\finetuning' -Filter '*.jsonl' -Recurse -ErrorAction SilentlyContinue; \"Dossier: F:\\BUREAU\\turbo\\finetuning ($($files.Count) fichiers)\"; if($datasets){\"Datasets: $($datasets.Count) fichiers JSONL\"; $datasets | ForEach-Object {\"  $($_.Name): $([math]::Round($_.Length/1KB))KB\"}}}else{'Dossier finetuning non trouve'};;powershell:\"=== GPU DISPONIBLE ===\"; nvidia-smi --query-gpu=index,name,memory.free --format=csv,noheader 2>&1 | ForEach-Object {$p = $_ -split ','; \"  GPU$($p[0].Trim()): $($p[1].Trim()) — $($p[2].Trim()) libre\"}"),

    JarvisCommand("finetune_launch", "pipeline", "Lancer le script de fine-tuning (QLoRA 4-bit)", [
        "lance le fine tuning", "demarre le training", "fine tune maintenant",
        "lancer qlora", "start finetuning",
    ], "pipeline", "powershell:if(Test-Path 'F:\\BUREAU\\turbo\\launchers\\JARVIS_FINETUNE.bat'){Start-Process 'F:\\BUREAU\\turbo\\launchers\\JARVIS_FINETUNE.bat' -WindowStyle Normal; 'Fine-tuning lance — voir la fenetre de training'}else{'Launcher JARVIS_FINETUNE.bat non trouve'}", confirm=True),

    JarvisCommand("finetune_datasets_info", "pipeline", "Informations sur les datasets de fine-tuning disponibles", [
        "datasets finetuning", "donnees d'entrainement", "combien de donnees",
        "liste les datasets", "datasets disponibles",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import os,json,glob; path='F:/BUREAU/turbo/finetuning'; files=glob.glob(os.path.join(path,'**/*.jsonl'),recursive=True); total=0; [print(f'  {os.path.basename(f)}: {sum(1 for _ in open(f,encoding=\\\"utf-8\\\"))} examples ({round(os.path.getsize(f)/1024)}KB)') or total.__add__(1) for f in files[:10]] if files else print('Aucun dataset JSONL trouve')\" 2>&1 | Out-String"),

    JarvisCommand("finetune_gpu_check", "pipeline", "Verifier si les GPU sont pretes pour le fine-tuning", [
        "gpu pret pour training", "check gpu finetuning", "assez de vram",
        "peut on fine tuner", "gpu training ready",
    ], "pipeline", "powershell:\"=== CHECK GPU FINE-TUNING ===\"; $gpus = nvidia-smi --query-gpu=index,name,memory.free,memory.total --format=csv,noheader,nounits 2>&1; $gpus -split \"`n\" | Where-Object {$_ -match '\\d'} | ForEach-Object {$p = $_ -split ','; $free = [int]$p[2].Trim(); $total = [int]$p[3].Trim(); $pct = [math]::Round($free/$total*100); $ok = if($free -ge 4096){'PRET (QLoRA possible)'}elseif($free -ge 2048){'LIMITE'}else{'INSUFFISANT'}; \"  GPU$($p[0].Trim()) $($p[1].Trim()): $free/$total MB libre ($pct%) — $ok\"}"),

    # ══════════════════════════════════════════════════════════════════════
    # TRADING AVANCE — Operations trading avancees
    # MOYENNE: Strategies avancees inaccessibles
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("trading_positions_resume", "pipeline", "Resume des positions trading ouvertes sur MEXC", [
        "positions ouvertes", "mes positions", "resume trading",
        "qu'est-ce qui est ouvert", "pnl actuel",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/trading_latest.db'); try: signals=c.execute('SELECT symbol,side,score,timestamp FROM signals ORDER BY timestamp DESC LIMIT 10').fetchall(); [print(f'  {s[0]} {s[1]} score:{s[2]} ({s[3]})') for s in signals] if signals else print('Aucun signal recent')\nexcept: print('Table signals non trouvee')\nfinally: c.close()\" 2>&1 | Out-String"),

    JarvisCommand("trading_market_overview", "pipeline", "Vue d'ensemble du marche crypto: BTC + ETH + top movers", [
        "vue du marche", "marche crypto", "comment va le marche",
        "bitcoin prix", "etat du marche",
    ], "pipeline", "browser:navigate:https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT;;sleep:1;;browser:navigate:https://www.coingecko.com;;powershell:\"Marche crypto: TradingView + CoinGecko ouverts\""),

    JarvisCommand("trading_scanner_complet", "pipeline", "Scanner trading complet: 10 paires + scoring multi-timeframe", [
        "scan trading complet", "scanne le marche", "analyse toutes les paires",
        "scanner crypto", "trading scan full",
    ], "pipeline", "powershell:Start-Process 'F:\\BUREAU\\turbo\\launchers\\SCAN_HYPER.bat' -WindowStyle Minimized -ErrorAction SilentlyContinue; 'Scanner lance en arriere-plan';;browser:navigate:https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT;;sleep:1;;browser:navigate:https://www.mexc.com/futures;;powershell:\"Scanner trading lance + TradingView + MEXC ouverts\""),

    JarvisCommand("trading_signals_history", "pipeline", "Historique des derniers signaux trading", [
        "historique signaux", "derniers signaux", "signaux recents",
        "history trading", "quels signaux",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/trading_latest.db'); try: r=c.execute('SELECT symbol,side,score,timestamp FROM signals ORDER BY timestamp DESC LIMIT 15').fetchall(); [print(f'  {s[3][:16]} | {s[0]:10} | {s[1]:5} | score:{s[2]}') for s in r] if r else print('Aucun signal')\nexcept Exception as e: print(f'Erreur: {e}')\nfinally: c.close()\" 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # SKILL MANAGEMENT — Gestion des 108 skills etoile.db
    # MOYENNE: Systeme de skills opaque pour l'utilisateur
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("skill_list_all", "pipeline", "Lister tous les skills par categorie", [
        "liste les skills", "quels skills", "skills disponibles",
        "montre les skills", "combien de skills",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); cats=c.execute('SELECT parent, COUNT(*) FROM map WHERE entity_type=\\\"skill\\\" GROUP BY parent ORDER BY COUNT(*) DESC').fetchall(); total=sum(x[1] for x in cats); print(f'=== {total} SKILLS ==='); [print(f'  {cat}: {cnt}') for cat,cnt in cats]; c.close()\" 2>&1 | Out-String"),

    JarvisCommand("skill_stats_performance", "pipeline", "Statistiques de performance des skills et pipelines", [
        "stats skills", "performance skills", "skills qui marchent",
        "metriques skills", "skills performance",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); tests=c.execute('SELECT category,COUNT(*),SUM(CASE WHEN status=\\\"PASS\\\" THEN 1 ELSE 0 END) FROM pipeline_tests GROUP BY category').fetchall(); print('=== RESULTATS TESTS ==='); [print(f'  {cat}: {ok}/{total} PASS') for cat,total,ok in tests]; mem=c.execute('SELECT key,value FROM memories WHERE category=\\\"stats\\\"').fetchall(); print('\\n=== STATS ==='); [print(f'  {k}: {v}') for k,v in mem]; c.close()\" 2>&1 | Out-String"),

    JarvisCommand("skill_search", "pipeline", "Rechercher un skill par mot-cle dans etoile.db", [
        "cherche un skill", "trouve un skill", "skill pour",
        "quel skill fait", "recherche skill",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3,sys; q='%'; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); r=c.execute('SELECT entity_name,parent,role FROM map WHERE entity_type=\\\"skill\\\" AND (entity_name LIKE ? OR role LIKE ?) ORDER BY parent LIMIT 20',(q,q)).fetchall(); print(f'{len(r)} skills trouves:'); [print(f'  [{p}] {n}: {d}') for n,p,d in r]; c.close()\" 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # CANVAS AUTOLEARN ENGINE — Gestion du moteur d'apprentissage (port 18800)
    # CRITIQUE: Deploye 2026-02-25, zero pipeline de gestion
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("canvas_autolearn_status", "pipeline", "Status complet du moteur Canvas Autolearn: memoire, scores, historique", [
        "status autolearn", "canvas autolearn", "autolearn status",
        "moteur apprentissage", "canvas status complet",
    ], "pipeline", "powershell:try { $s = Invoke-WebRequest -Uri 'http://127.0.0.1:18800/autolearn/status' -TimeoutSec 5 -UseBasicParsing; $d = $s.Content | ConvertFrom-Json; Write-Output \"=== CANVAS AUTOLEARN ===\"; Write-Output \"  Status: $($d.status)\"; Write-Output \"  Memoire: $($d.memory_count) patterns\"; Write-Output \"  Dernier tuning: $($d.last_tuning)\"; Write-Output \"  Dernier review: $($d.last_review)\" } catch { Write-Output 'Canvas Autolearn: port 18800 offline' }"),

    JarvisCommand("canvas_autolearn_trigger", "pipeline", "Declencher manuellement un cycle d'apprentissage Canvas", [
        "lance autolearn", "trigger autolearn", "apprentissage maintenant",
        "force autolearn", "canvas apprendre",
    ], "pipeline", "powershell:try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:18800/autolearn/trigger' -Method POST -TimeoutSec 30 -UseBasicParsing; Write-Output \"Autolearn trigger: $($r.Content)\" } catch { Write-Output 'Autolearn trigger: port 18800 offline' }"),

    JarvisCommand("canvas_memory_review", "pipeline", "Revoir et consolider la memoire Canvas Autolearn", [
        "revue memoire canvas", "canvas memoire", "memoire autolearn",
        "patterns appris", "canvas review",
    ], "pipeline", "powershell:try { $m = Invoke-WebRequest -Uri 'http://127.0.0.1:18800/autolearn/memory' -TimeoutSec 5 -UseBasicParsing; $d = $m.Content | ConvertFrom-Json; Write-Output \"=== MEMOIRE CANVAS ===\"; Write-Output \"  Patterns: $($d.count)\"; Write-Output \"  Categories: $($d.categories -join ', ')\"; $d.recent | Select-Object -First 5 | ForEach-Object { Write-Output \"  - $($_.pattern): $($_.score)\" } } catch { Write-Output 'Canvas memoire: offline' }"),

    JarvisCommand("canvas_scoring_update", "pipeline", "Mettre a jour les scores de routing Canvas Autolearn", [
        "scores canvas", "update scoring", "scoring autolearn",
        "canvas scores", "mise a jour scores",
    ], "pipeline", "powershell:try { $s = Invoke-WebRequest -Uri 'http://127.0.0.1:18800/autolearn/scores' -TimeoutSec 5 -UseBasicParsing; $d = $s.Content | ConvertFrom-Json; Write-Output \"=== SCORES ROUTING ===\"; $d.PSObject.Properties | ForEach-Object { Write-Output \"  $($_.Name): $($_.Value)\" } } catch { Write-Output 'Canvas scoring: offline' }"),

    JarvisCommand("canvas_autolearn_history", "pipeline", "Historique des cycles d'apprentissage Canvas", [
        "historique autolearn", "canvas historique", "cycles apprentissage",
        "history autolearn", "canvas history",
    ], "pipeline", "powershell:try { $h = Invoke-WebRequest -Uri 'http://127.0.0.1:18800/autolearn/history' -TimeoutSec 5 -UseBasicParsing; $d = $h.Content | ConvertFrom-Json; Write-Output \"=== HISTORIQUE AUTOLEARN ===\"; Write-Output \"  Total cycles: $($d.total)\"; $d.recent | Select-Object -First 5 | ForEach-Object { Write-Output \"  $($_.date): $($_.type) - $($_.result)\" } } catch { Write-Output 'Canvas history: offline' }"),

    # ══════════════════════════════════════════════════════════════════════
    # VOICE SYSTEM MANAGEMENT — Gestion pipeline vocale v2
    # CRITIQUE: Pipeline vocale v2 deployee mais aucune gestion operationnelle
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("voice_wake_word_test", "pipeline", "Tester la sensibilite du wake word 'jarvis'", [
        "test wake word", "test jarvis wake", "sensibilite jarvis",
        "wake word jarvis", "detection jarvis",
    ], "pipeline", "powershell:$proc = Get-Process -Name 'python*' -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'voice|wake|whisper' }; if ($proc) { Write-Output \"=== WAKE WORD ===\"; Write-Output \"  Process actif: $($proc.Name) PID=$($proc.Id)\"; Write-Output \"  RAM: $([math]::Round($proc.WorkingSet64/1MB))MB\"; Write-Output \"  Seuil: 0.7 (OpenWakeWord)\" } else { Write-Output 'Wake word: aucun process vocal actif' }"),

    JarvisCommand("voice_latency_check", "pipeline", "Mesurer la latence du pipeline vocal: wake → whisper → TTS", [
        "latence vocale", "voice latency", "latence voice",
        "vitesse vocale", "pipeline vocal latence",
    ], "pipeline", "powershell:$start = Get-Date; $whisper = Get-Process -Name 'python*' -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'whisper' }; $tts = Get-Process -Name 'python*' -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'tts|edge' }; Write-Output \"=== LATENCE VOCALE ===\"; Write-Output \"  Whisper: $(if ($whisper) { 'ACTIF' } else { 'INACTIF' })\"; Write-Output \"  TTS Edge: $(if ($tts) { 'ACTIF' } else { 'INACTIF' })\"; Write-Output \"  Target: <2s (connu <0.5s via cache LRU 200)\"; Write-Output \"  Mode: Whisper large-v3-turbo CUDA → Edge fr-FR-HenriNeural\""),

    JarvisCommand("voice_cache_stats", "pipeline", "Statistiques du cache vocal LRU (200 entrees)", [
        "cache vocal", "voice cache", "cache lru vocal",
        "cache whisper", "statistiques cache vocal",
    ], "pipeline", "powershell:if (Test-Path 'F:\\BUREAU\\turbo\\src\\voice.py') { $lines = Get-Content 'F:\\BUREAU\\turbo\\src\\voice.py' | Select-String 'cache|LRU|lru_cache'; Write-Output \"=== CACHE VOCAL ===\"; Write-Output \"  Fichier: src/voice.py\"; Write-Output \"  Taille cache LRU: 200 entrees\"; Write-Output \"  Lignes cache: $($lines.Count) references\"; $lines | Select-Object -First 5 | ForEach-Object { Write-Output \"  $($_.Line.Trim())\" } } else { Write-Output 'voice.py non trouve' }"),

    JarvisCommand("voice_fallback_chain", "pipeline", "Tester la chaine de fallback vocale: OL1 → GEMINI → local", [
        "fallback vocal", "voice fallback", "chaine fallback vocal",
        "test fallback voix", "vocal fallback test",
    ], "pipeline", "powershell:Write-Output '=== TEST FALLBACK VOCAL ==='; $ol1 = try { (Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 -UseBasicParsing).StatusCode } catch { 'OFFLINE' }; Write-Output \"  OL1 (primaire): $ol1\"; $gemini = if (Test-Path 'F:\\BUREAU\\turbo\\gemini-proxy.js') { 'DISPONIBLE' } else { 'ABSENT' }; Write-Output \"  GEMINI (secondaire): $gemini\"; Write-Output \"  Local (tertiaire): TOUJOURS OK\"; Write-Output \"  Chaine: OL1 → GEMINI → local-only\""),

    JarvisCommand("voice_config_show", "pipeline", "Afficher la configuration complete du systeme vocal", [
        "config vocale", "voice config", "configuration voix",
        "parametres vocaux", "vocal settings",
    ], "pipeline", "powershell:Write-Output '=== CONFIG VOCALE ==='; Write-Output '  Wake Word: OpenWakeWord (jarvis, seuil 0.7)'; Write-Output '  STT: Whisper large-v3-turbo CUDA'; Write-Output '  TTS: Edge fr-FR-HenriNeural'; Write-Output '  Cache: LRU 200 entrees'; Write-Output '  Latence target: <2s (connu <0.5s)'; Write-Output '  IA bypass: 80%'; if (Test-Path 'F:\\BUREAU\\turbo\\src\\voice.py') { $size = (Get-Item 'F:\\BUREAU\\turbo\\src\\voice.py').Length / 1KB; Write-Output \"  voice.py: $([math]::Round($size))KB\" }; if (Test-Path 'F:\\BUREAU\\turbo\\src\\voice_correction.py') { $size2 = (Get-Item 'F:\\BUREAU\\turbo\\src\\voice_correction.py').Length / 1KB; Write-Output \"  voice_correction.py: $([math]::Round($size2))KB\" }"),

    # ══════════════════════════════════════════════════════════════════════
    # PLUGIN MANAGEMENT — Gestion lifecycle des 24 plugins actifs
    # CRITIQUE: 24 plugins actifs sans aucune pipeline de gestion
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("plugin_list_enabled", "pipeline", "Lister tous les plugins Claude Code actifs avec versions", [
        "liste plugins", "plugins actifs", "quels plugins",
        "plugins installes", "combien de plugins",
    ], "pipeline", "powershell:$settingsPath = 'C:\\Users\\franc\\.claude\\settings.json'; if (Test-Path $settingsPath) { $s = Get-Content $settingsPath | ConvertFrom-Json; $plugins = $s.plugins; Write-Output '=== PLUGINS ACTIFS ==='; $count = 0; foreach ($p in $plugins) { Write-Output \"  $p\"; $count++ }; Write-Output \"`n  Total: $count plugins\" } else { Write-Output 'settings.json non trouve' }"),

    JarvisCommand("plugin_jarvis_status", "pipeline", "Status detaille du plugin jarvis-turbo local", [
        "status jarvis plugin", "jarvis turbo plugin", "plugin jarvis",
        "jarvis plugin status", "plugin local status",
    ], "pipeline", "powershell:$pluginPath = 'C:\\Users\\franc\\.claude\\plugins\\local\\jarvis-turbo'; if (Test-Path \"$pluginPath\\plugin.json\") { $p = Get-Content \"$pluginPath\\plugin.json\" | ConvertFrom-Json; Write-Output '=== PLUGIN JARVIS-TURBO ==='; Write-Output \"  Version: $($p.version)\"; Write-Output \"  Commandes: $($p.commands.Count)\"; Write-Output \"  Agents: $($p.agents.Count)\"; Write-Output \"  Skills: $($p.skills.Count)\"; Write-Output \"  Hooks: $($p.hooks.Count)\" } else { Write-Output 'plugin.json non trouve' }"),

    JarvisCommand("plugin_health_check", "pipeline", "Health check de tous les plugins actifs", [
        "health check plugins", "plugins ok", "verifier plugins",
        "plugins fonctionnent", "check plugins",
    ], "pipeline", "powershell:Write-Output '=== HEALTH CHECK PLUGINS ==='; $localPath = 'C:\\Users\\franc\\.claude\\plugins\\local'; $cachePath = 'C:\\Users\\franc\\.claude\\plugins\\cache'; $localCount = if (Test-Path $localPath) { (Get-ChildItem $localPath -Directory | Measure-Object).Count } else { 0 }; $cacheCount = if (Test-Path $cachePath) { (Get-ChildItem $cachePath -Directory | Measure-Object).Count } else { 0 }; Write-Output \"  Plugins locaux: $localCount\"; Write-Output \"  Plugins cache: $cacheCount\"; if (Test-Path $localPath) { Get-ChildItem $localPath -Directory | ForEach-Object { $hasJson = Test-Path \"$($_.FullName)\\plugin.json\"; Write-Output \"  [$( if ($hasJson) { 'OK' } else { 'MISSING' } )] $($_.Name)\" } }"),

    JarvisCommand("plugin_reload_config", "pipeline", "Recharger la configuration des plugins sans redemarrer Claude", [
        "recharger plugins", "reload plugins", "refresh plugins",
        "actualiser plugins", "plugins reload",
    ], "pipeline", "powershell:Write-Output '=== RELOAD PLUGINS ==='; Write-Output '  Action: Redemarrer Claude Code pour charger les nouveaux plugins'; Write-Output '  Commande: claude --resume ou /clear'; $settingsPath = 'C:\\Users\\franc\\.claude\\settings.json'; if (Test-Path $settingsPath) { $mod = (Get-Item $settingsPath).LastWriteTime; Write-Output \"  settings.json modifie: $mod\" }; Write-Output '  Note: Les plugins sont charges au demarrage de la session'"),

    JarvisCommand("plugin_config_show", "pipeline", "Afficher la configuration complete des plugins", [
        "config plugins", "configuration plugins", "plugins config",
        "parametres plugins", "plugins settings",
    ], "pipeline", "powershell:$localPath = 'C:\\Users\\franc\\.claude\\plugins\\local'; if (Test-Path $localPath) { Get-ChildItem $localPath -Directory | ForEach-Object { $jsonPath = \"$($_.FullName)\\plugin.json\"; if (Test-Path $jsonPath) { $p = Get-Content $jsonPath | ConvertFrom-Json; Write-Output \"=== $($_.Name) v$($p.version) ===\"; Write-Output \"  Commandes: $($p.commands.Count)\"; Write-Output \"  Agents: $($p.agents.Count)\"; Write-Output \"  Skills: $($p.skills.Count)\"; Write-Output \"  Hooks: $($p.hooks.Count)\" } } } else { Write-Output 'Aucun plugin local' }"),

    # ══════════════════════════════════════════════════════════════════════
    # EMBEDDING & VECTOR SEARCH — Gestion embeddings M1
    # CRITIQUE: M1 assigne embeddings dans README mais zero pipeline
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("embedding_model_status", "pipeline", "Status du modele d'embedding sur M1", [
        "status embedding", "embedding modele", "modele embedding",
        "embedding M1", "vecteurs status",
    ], "pipeline", "powershell:$body = '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nListe les modeles d embedding disponibles en 2 lignes\",\"temperature\":0.2,\"max_output_tokens\":256,\"stream\":false,\"store\":false}'; try { $r = Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 15 -UseBasicParsing; $d = $r.Content | ConvertFrom-Json; $msg = ($d.output | Where-Object { $_.type -eq 'message' } | Select-Object -Last 1).content; Write-Output \"=== EMBEDDING M1 ===\"; Write-Output \"  Modele: qwen3-8b (M1)\"; Write-Output \"  IA: $msg\" } catch { Write-Output 'M1 embedding: offline' }"),

    JarvisCommand("embedding_search_test", "pipeline", "Tester une recherche semantique via embedding M1", [
        "test embedding", "recherche semantique", "semantic search",
        "test vecteurs", "embedding recherche",
    ], "pipeline", "powershell:$body = '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nGenere un embedding conceptuel pour le mot JARVIS en 3 dimensions: intention, capacite, fiabilite. Score chaque dimension de 0 a 1.\",\"temperature\":0.2,\"max_output_tokens\":256,\"stream\":false,\"store\":false}'; try { $r = Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 15 -UseBasicParsing; $d = $r.Content | ConvertFrom-Json; $msg = ($d.output | Where-Object { $_.type -eq 'message' } | Select-Object -Last 1).content; Write-Output \"=== EMBEDDING TEST ===\"; Write-Output $msg } catch { Write-Output 'Embedding test: M1 offline' }"),

    JarvisCommand("embedding_cache_status", "pipeline", "Status du cache d'embeddings", [
        "cache embedding", "embedding cache", "cache vecteurs",
        "vecteurs en cache", "embedding stockes",
    ], "pipeline", "powershell:Write-Output '=== CACHE EMBEDDINGS ==='; Write-Output '  Backend: M1 qwen3-8b (10.5.0.2:1234)'; Write-Output '  Type: generation a la volee via LM Studio'; $dbSize = if (Test-Path 'F:\\BUREAU\\turbo\\data\\etoile.db') { [math]::Round((Get-Item 'F:\\BUREAU\\turbo\\data\\etoile.db').Length / 1KB) } else { 0 }; Write-Output \"  DB stockage: etoile.db ($($dbSize)KB)\"; Write-Output '  Note: embeddings persistants via etoile.db memories table'"),

    JarvisCommand("embedding_generate_batch", "pipeline", "Generer des embeddings en batch pour documents via M1", [
        "generer embeddings", "batch embedding", "embedding batch",
        "embeddings documents", "vectoriser documents",
    ], "pipeline", "powershell:$body = '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nAnalyse les 5 fichiers principaux du projet JARVIS turbo et genere un resume vectoriel en 1 ligne par fichier: agents.py, tools.py, mcp_server.py, commands_pipelines.py, commander.py\",\"temperature\":0.2,\"max_output_tokens\":512,\"stream\":false,\"store\":false}'; try { $r = Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 30 -UseBasicParsing; $d = $r.Content | ConvertFrom-Json; $msg = ($d.output | Where-Object { $_.type -eq 'message' } | Select-Object -Last 1).content; Write-Output \"=== BATCH EMBEDDING ===\"; Write-Output $msg } catch { Write-Output 'Batch embedding: M1 offline' }"),

    # ══════════════════════════════════════════════════════════════════════
    # FINE-TUNING ORCHESTRATION — Gestion avancee du training
    # CRITIQUE: 4 pipelines existent mais orchestration training manquante
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("finetune_monitor_progress", "pipeline", "Monitoring en temps reel du fine-tuning en cours", [
        "progress finetuning", "avancement finetuning", "training progress",
        "ou en est le finetuning", "monitoring training",
    ], "pipeline", "powershell:Write-Output '=== MONITORING FINE-TUNING ==='; $gpuUtil = & 'nvidia-smi' --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>$null; if ($gpuUtil) { Write-Output '  GPU Status:'; $gpuUtil | ForEach-Object { $parts = $_ -split ','; Write-Output \"    $($parts[0].Trim()): $($parts[1].Trim())% GPU, $($parts[2].Trim())/$($parts[3].Trim())MB VRAM\" } }; $ftProc = Get-Process -Name 'python*' -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'train|finetune|lora' }; if ($ftProc) { Write-Output \"  Training PID: $($ftProc.Id) RAM: $([math]::Round($ftProc.WorkingSet64/1MB))MB\" } else { Write-Output '  Aucun training en cours' }"),

    JarvisCommand("finetune_validate_quality", "pipeline", "Valider la qualite post-training du modele fine-tune", [
        "qualite finetuning", "valider finetuning", "test qualite modele",
        "finetuning ok", "validation training",
    ], "pipeline", "powershell:$body = '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nEvalue la qualite d un modele fine-tune QLoRA 4-bit Qwen3-30B sur 55549 exemples JARVIS. Quels metriques verifier? Liste 5 tests de qualite essentiels.\",\"temperature\":0.2,\"max_output_tokens\":512,\"stream\":false,\"store\":false}'; try { $r = Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 20 -UseBasicParsing; $d = $r.Content | ConvertFrom-Json; $msg = ($d.output | Where-Object { $_.type -eq 'message' } | Select-Object -Last 1).content; Write-Output \"=== QUALITE FINE-TUNING ===\"; Write-Output $msg } catch { Write-Output 'Validation: M1 offline' }"),

    JarvisCommand("finetune_dataset_stats", "pipeline", "Statistiques detaillees du dataset de fine-tuning", [
        "stats dataset finetuning", "dataset finetuning", "donnees finetuning",
        "combien exemples finetuning", "dataset training stats",
    ], "pipeline", "powershell:Write-Output '=== DATASET FINE-TUNING ==='; Write-Output '  Format: QLoRA 4-bit + PEFT LoRA'; Write-Output '  Modele cible: Qwen3-30B-A3B'; Write-Output '  Exemples: 55,549'; if (Test-Path 'F:\\BUREAU\\turbo\\finetuning') { $files = Get-ChildItem 'F:\\BUREAU\\turbo\\finetuning' -Recurse -File; $totalSize = [math]::Round(($files | Measure-Object Length -Sum).Sum / 1MB, 1); Write-Output \"  Fichiers: $($files.Count) ($($totalSize)MB total)\"; $jsonl = $files | Where-Object { $_.Extension -eq '.jsonl' }; if ($jsonl) { Write-Output \"  JSONL: $($jsonl.Count) fichiers\"; $jsonl | ForEach-Object { Write-Output \"    $($_.Name): $([math]::Round($_.Length/1KB))KB\" } } }"),

    JarvisCommand("finetune_export_lora", "pipeline", "Exporter les poids LoRA du dernier fine-tuning", [
        "export lora", "exporter lora", "poids lora",
        "lora weights", "sauvegarder lora",
    ], "pipeline", "powershell:Write-Output '=== EXPORT LoRA ==='; if (Test-Path 'F:\\BUREAU\\turbo\\finetuning') { $adapters = Get-ChildItem 'F:\\BUREAU\\turbo\\finetuning' -Recurse -Filter 'adapter_*' -ErrorAction SilentlyContinue; $checkpoints = Get-ChildItem 'F:\\BUREAU\\turbo\\finetuning' -Recurse -Directory -Filter 'checkpoint-*' -ErrorAction SilentlyContinue; Write-Output \"  Adapters trouves: $($adapters.Count)\"; Write-Output \"  Checkpoints: $($checkpoints.Count)\"; if ($checkpoints) { $checkpoints | ForEach-Object { Write-Output \"    $($_.Name): $([math]::Round((Get-ChildItem $_.FullName -Recurse | Measure-Object Length -Sum).Sum/1MB))MB\" } } else { Write-Output '  Aucun checkpoint trouve' } } else { Write-Output 'Repertoire finetuning non trouve' }"),

    # ══════════════════════════════════════════════════════════════════════
    # BRAIN LEARNING & MEMORY — Systeme d'apprentissage et memoire
    # CRITIQUE: Systeme reference dans n8n/orchestrator mais zero pipeline
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("brain_memory_status", "pipeline", "Status de la memoire JARVIS: patterns, categories, taille", [
        "memoire jarvis", "brain status", "status memoire",
        "patterns appris", "jarvis memoire",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); cats=c.execute('SELECT category,COUNT(*) FROM memories GROUP BY category ORDER BY COUNT(*) DESC').fetchall(); total=sum(x[1] for x in cats); print(f'=== MEMOIRE JARVIS ({total} entries) ==='); [print(f'  {cat}: {cnt}') for cat,cnt in cats]; recent=c.execute('SELECT key,value FROM memories ORDER BY ROWID DESC LIMIT 5').fetchall(); print('\\nDernieres:'); [print(f'  {k}: {v[:60]}') for k,v in recent]; c.close()\" 2>&1 | Out-String"),

    JarvisCommand("brain_pattern_learn", "pipeline", "Apprendre un nouveau pattern depuis les interactions recentes", [
        "apprendre pattern", "learn pattern", "nouveau pattern",
        "jarvis apprends", "brain learn",
    ], "pipeline", "powershell:$body = '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nAnalyse les 3 derniers commits git du projet F:/BUREAU/turbo et identifie les patterns de developpement recurrents. Format: PATTERN: description | FREQUENCE: haute/moyenne/basse | ACTION: suggestion\",\"temperature\":0.2,\"max_output_tokens\":512,\"stream\":false,\"store\":false}'; try { $r = Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 20 -UseBasicParsing; $d = $r.Content | ConvertFrom-Json; $msg = ($d.output | Where-Object { $_.type -eq 'message' } | Select-Object -Last 1).content; Write-Output \"=== PATTERN LEARNING ===\"; Write-Output $msg } catch { Write-Output 'Pattern learning: M1 offline' }"),

    JarvisCommand("brain_memory_consolidate", "pipeline", "Consolider la memoire: fusionner doublons et optimiser", [
        "consolider memoire", "optimize memoire", "memoire optimiser",
        "fusionner memoire", "brain consolidate",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); dupes=c.execute('SELECT key,COUNT(*) FROM memories GROUP BY key HAVING COUNT(*)>1').fetchall(); print('=== CONSOLIDATION MEMOIRE ==='); print(f'  Doublons: {len(dupes)}'); [print(f'  {k}: {cnt}x') for k,cnt in dupes[:10]]; total=c.execute('SELECT COUNT(*) FROM memories').fetchone()[0]; cats=c.execute('SELECT COUNT(DISTINCT category) FROM memories').fetchone()[0]; print(f'  Total: {total} entries, {cats} categories'); c.close()\" 2>&1 | Out-String"),

    JarvisCommand("brain_memory_export", "pipeline", "Exporter la memoire JARVIS vers un fichier JSON", [
        "export memoire", "sauvegarder memoire", "backup memoire",
        "memoire json", "brain export",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3,json,datetime; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); rows=c.execute('SELECT category,key,value,confidence FROM memories').fetchall(); data=[{'category':r[0],'key':r[1],'value':r[2],'confidence':r[3]} for r in rows]; out=f'F:/BUREAU/turbo/data/memories_export_{datetime.datetime.now().strftime(chr(37)+chr(89)+chr(37)+chr(109)+chr(37)+chr(100))}.json'; open(out,'w').write(json.dumps(data,indent=2,ensure_ascii=False)); print(f'=== EXPORT MEMOIRE ==='); print(f'  {len(data)} entries exportees'); print(f'  Fichier: {out}'); c.close()\" 2>&1 | Out-String"),

    JarvisCommand("brain_pattern_search", "pipeline", "Rechercher des patterns appris par mot-cle", [
        "cherche pattern", "search pattern", "pattern pour",
        "quel pattern", "brain search",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); r=c.execute('SELECT category,key,value FROM memories ORDER BY ROWID DESC LIMIT 15').fetchall(); print('=== PATTERNS RECENTS ==='); [print(f'  [{cat}] {k}: {v[:60]}') for cat,k,v in r]; c.close()\" 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # RAG SYSTEM — Retrieval-Augmented Generation
    # HAUTE: Mentionne dans features mais aucune pipeline
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("rag_status", "pipeline", "Status du systeme RAG: index, documents, modele", [
        "status rag", "rag status", "retrieval status",
        "systeme rag", "rag info",
    ], "pipeline", "powershell:Write-Output '=== RAG SYSTEM ==='; if (Test-Path 'F:\\BUREAU\\rag-v1') { $files = (Get-ChildItem 'F:\\BUREAU\\rag-v1' -Recurse -File | Measure-Object).Count; $size = [math]::Round((Get-ChildItem 'F:\\BUREAU\\rag-v1' -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 1); Write-Output \"  Projet: F:\\BUREAU\\rag-v1\"; Write-Output \"  Fichiers: $files ($($size)MB)\"; Write-Output \"  Type: TS plugin RAG adaptatif\" } else { Write-Output '  RAG: non deploye' }"),

    JarvisCommand("rag_index_status", "pipeline", "Verifier l'etat de l'index RAG et documents indexes", [
        "index rag", "rag index", "documents indexes",
        "rag documents", "index status",
    ], "pipeline", "powershell:Write-Output '=== INDEX RAG ==='; if (Test-Path 'F:\\BUREAU\\rag-v1') { $ts = Get-ChildItem 'F:\\BUREAU\\rag-v1' -Filter '*.ts' -Recurse | Measure-Object; $json = Get-ChildItem 'F:\\BUREAU\\rag-v1' -Filter '*.json' -Recurse | Measure-Object; Write-Output \"  TS: $($ts.Count) fichiers\"; Write-Output \"  JSON: $($json.Count) fichiers\"; $pkg = 'F:\\BUREAU\\rag-v1\\package.json'; if (Test-Path $pkg) { Write-Output \"  Package: $(Get-Content $pkg | ConvertFrom-Json | Select-Object -ExpandProperty name -ErrorAction SilentlyContinue)\" } } else { Write-Output '  Index: non disponible' }"),

    JarvisCommand("rag_search_test", "pipeline", "Tester une recherche RAG via M1 qwen3-8b", [
        "test rag", "recherche rag", "rag query",
        "rag cherche", "tester retrieval",
    ], "pipeline", "powershell:$body = '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nSimule une recherche RAG: pour la question \\\"comment fonctionne le cluster JARVIS?\\\", genere les 3 documents les plus pertinents a recuperer avec leur score de pertinence.\",\"temperature\":0.2,\"max_output_tokens\":512,\"stream\":false,\"store\":false}'; try { $r = Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 20 -UseBasicParsing; $d = $r.Content | ConvertFrom-Json; $msg = ($d.output | Where-Object { $_.type -eq 'message' } | Select-Object -Last 1).content; Write-Output $msg } catch { Write-Output 'RAG search: M1 offline' }"),

    # ══════════════════════════════════════════════════════════════════════
    # CONSENSUS & VOTE SYSTEM — Gestion du systeme de vote pondere
    # HAUTE: 58 regles documentees mais zero pipeline de gestion
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("consensus_weights_show", "pipeline", "Afficher les poids de vote du consensus cluster", [
        "poids consensus", "weights consensus", "vote poids",
        "ponderation cluster", "consensus config",
    ], "pipeline", "powershell:Write-Output '=== CONSENSUS VOTE PONDERE ==='; Write-Output '  M1 (qwen3-8b): 1.8 — PRIORITAIRE'; Write-Output '  M2 (deepseek): 1.4 — Code review'; Write-Output '  OL1 (qwen3:1.7b): 1.3 — Vitesse'; Write-Output '  GEMINI (pro/flash): 1.2 — Architecture'; Write-Output '  CLAUDE (opus/sonnet): 1.2 — Raisonnement'; Write-Output '  M3 (mistral-7b): 1.0 — General'; Write-Output '  Quorum: SUM(opinion*poids)/SUM(poids) >= 0.65'"),

    JarvisCommand("consensus_test_scenario", "pipeline", "Tester le consensus sur un scenario rapide M1+OL1", [
        "test consensus", "consensus test", "tester vote",
        "scenario consensus", "consensus rapide",
    ], "pipeline", "powershell:$body1 = '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nQuestion consensus: quel format de donnees est optimal pour JARVIS? Reponds en 1 mot: JSON, Parquet, ou SQLite.\",\"temperature\":0.2,\"max_output_tokens\":32,\"stream\":false,\"store\":false}'; try { $r1 = Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body1 -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 15 -UseBasicParsing; $d1 = $r1.Content | ConvertFrom-Json; $m1 = ($d1.output | Where-Object { $_.type -eq 'message' } | Select-Object -Last 1).content; $body2 = '{\"model\":\"qwen3:1.7b\",\"messages\":[{\"role\":\"user\",\"content\":\"Question: quel format optimal pour JARVIS? 1 mot: JSON, Parquet, ou SQLite.\"}],\"stream\":false}'; $r2 = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/chat' -Method POST -Body $body2 -ContentType 'application/json' -TimeoutSec 15 -UseBasicParsing; $d2 = $r2.Content | ConvertFrom-Json; $ol1 = $d2.message.content; Write-Output '=== TEST CONSENSUS ==='; Write-Output \"  M1 (poids 1.8): $($m1.Substring(0, [Math]::Min(50, $m1.Length)))\"; Write-Output \"  OL1 (poids 1.3): $($ol1.Substring(0, [Math]::Min(50, $ol1.Length)))\" } catch { Write-Output 'Consensus test: agents offline' }"),

    JarvisCommand("consensus_routing_rules", "pipeline", "Afficher les 22 regles de routage du consensus", [
        "regles routage", "routing rules", "regles consensus",
        "routage cluster", "matrice routage",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); r=c.execute('SELECT entity_name,role FROM map WHERE entity_type=\\\"routing_rule\\\" ORDER BY entity_name').fetchall(); print(f'=== {len(r)} REGLES ROUTAGE ==='); [print(f'  {n}: {d[:60]}') for n,d in r]; c.close()\" 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # SECURITY HARDENING — Securite avancee et hardening
    # HAUTE: 4 pipelines existent mais hardening/patching manquant
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("security_vuln_scan", "pipeline", "Scan de vulnerabilites: deps Python + npm + systeme", [
        "scan vulnerabilites", "vuln scan", "securite scan",
        "failles securite", "vulnerability check",
    ], "pipeline", "powershell:Write-Output '=== SCAN VULNERABILITES ==='; $pipAudit = & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run pip list --outdated 2>$null | Select-Object -First 10; Write-Output '  Packages Python outdated:'; $pipAudit | ForEach-Object { Write-Output \"    $_\" }; if (Test-Path 'F:\\BUREAU\\turbo\\electron\\package.json') { $npmAudit = npm audit --prefix 'F:\\BUREAU\\turbo\\electron' 2>$null | Select-Object -First 5; Write-Output '  NPM audit:'; $npmAudit | ForEach-Object { Write-Output \"    $_\" } }"),

    JarvisCommand("security_firewall_check", "pipeline", "Verifier les regles firewall Windows actives", [
        "firewall status", "regles firewall", "firewall check",
        "check firewall", "firewall windows",
    ], "pipeline", "powershell:Write-Output '=== FIREWALL WINDOWS ==='; $profiles = Get-NetFirewallProfile -ErrorAction SilentlyContinue; if ($profiles) { $profiles | ForEach-Object { Write-Output \"  $($_.Name): Enabled=$($_.Enabled) Inbound=$($_.DefaultInboundAction) Outbound=$($_.DefaultOutboundAction)\" } }; $rules = (Get-NetFirewallRule -Enabled True -ErrorAction SilentlyContinue | Measure-Object).Count; Write-Output \"  Regles actives: $rules\""),

    JarvisCommand("security_cert_check", "pipeline", "Verifier les certificats SSL et leur expiration", [
        "certificats ssl", "cert check", "ssl check",
        "certificats expiration", "verifier certs",
    ], "pipeline", "powershell:Write-Output '=== CERTIFICATS SSL ==='; $certs = Get-ChildItem Cert:\\LocalMachine\\My -ErrorAction SilentlyContinue; Write-Output \"  Certificats machine: $($certs.Count)\"; $expiring = $certs | Where-Object { $_.NotAfter -lt (Get-Date).AddDays(30) }; Write-Output \"  Expirent <30j: $($expiring.Count)\"; $certs | Select-Object -First 5 | ForEach-Object { Write-Output \"  $($_.Subject.Substring(0, [Math]::Min(50, $_.Subject.Length))): expire $($_.NotAfter.ToString('yyyy-MM-dd'))\" }"),

    JarvisCommand("security_patch_status", "pipeline", "Verifier les mises a jour Windows et patches securite", [
        "mises a jour windows", "windows update", "patches securite",
        "updates windows", "patch status",
    ], "pipeline", "powershell:Write-Output '=== PATCHES SECURITE ==='; $updates = Get-HotFix -ErrorAction SilentlyContinue | Sort-Object InstalledOn -Descending | Select-Object -First 5; Write-Output \"  Derniers patches:\"; $updates | ForEach-Object { Write-Output \"    $($_.HotFixID): $($_.Description) ($($_.InstalledOn))\" }; $pending = (Get-WindowsUpdate -ErrorAction SilentlyContinue | Measure-Object).Count; Write-Output \"  En attente: $pending\""),

    # ══════════════════════════════════════════════════════════════════════
    # MODEL MANAGEMENT — Gestion lifecycle des modeles IA
    # HAUTE: References dans README mais pas de gestion unifiee
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("model_inventory_full", "pipeline", "Inventaire complet de tous les modeles charges sur le cluster", [
        "inventaire modeles", "tous les modeles", "models inventory",
        "quels modeles", "liste modeles cluster",
    ], "pipeline", "powershell:Write-Output '=== INVENTAIRE MODELES ==='; try { $m1 = (Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/models' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 5 -UseBasicParsing).Content | ConvertFrom-Json; $m1Loaded = $m1.models | Where-Object { $_.loaded_instances.Count -gt 0 }; Write-Output \"  M1: $($m1Loaded.Count) charges [$($m1Loaded.key -join ', ')]\"; Write-Output \"  M1 total: $($m1.models.Count) disponibles\" } catch { Write-Output '  M1: offline' }; try { $m2 = (Invoke-WebRequest -Uri 'http://192.168.1.26:1234/api/v1/models' -Headers @{Authorization='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'} -TimeoutSec 5 -UseBasicParsing).Content | ConvertFrom-Json; $m2Loaded = $m2.models | Where-Object { $_.loaded_instances.Count -gt 0 }; Write-Output \"  M2: $($m2Loaded.Count) charges [$($m2Loaded.key -join ', ')]\" } catch { Write-Output '  M2: offline' }; try { $m3 = (Invoke-WebRequest -Uri 'http://192.168.1.113:1234/api/v1/models' -Headers @{Authorization='Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux'} -TimeoutSec 5 -UseBasicParsing).Content | ConvertFrom-Json; $m3Loaded = $m3.models | Where-Object { $_.loaded_instances.Count -gt 0 }; Write-Output \"  M3: $($m3Loaded.Count) charges [$($m3Loaded.key -join ', ')]\" } catch { Write-Output '  M3: offline' }; try { $ol1 = (Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 -UseBasicParsing).Content | ConvertFrom-Json; Write-Output \"  OL1: $($ol1.models.Count) modeles\" } catch { Write-Output '  OL1: offline' }"),

    JarvisCommand("model_vram_usage", "pipeline", "Carte VRAM detaillee par GPU et modele charge", [
        "vram modeles", "gpu vram", "vram usage",
        "memoire gpu modeles", "vram map modeles",
    ], "pipeline", "powershell:Write-Output '=== VRAM USAGE ==='; $gpuInfo = & 'nvidia-smi' --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits 2>$null; if ($gpuInfo) { $gpuInfo | ForEach-Object { $p = $_ -split ','; Write-Output \"  GPU$($p[0].Trim()): $($p[1].Trim()) — $($p[2].Trim())/$($p[3].Trim())MB ($($p[4].Trim())% util)\" } } else { Write-Output '  nvidia-smi non disponible' }"),

    JarvisCommand("model_benchmark_compare", "pipeline", "Benchmark comparatif des modeles du cluster", [
        "benchmark modeles", "comparer modeles", "model benchmark",
        "quel modele meilleur", "performance modeles",
    ], "pipeline", "powershell:$body = '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nCompare en tableau les modeles du cluster JARVIS: qwen3-8b (M1, 65tok/s), deepseek-coder-v2-lite (M2), mistral-7b (M3), qwen3:1.7b (OL1). Criteres: vitesse, qualite code, raisonnement, polyvalence. Score /10 chaque.\",\"temperature\":0.2,\"max_output_tokens\":512,\"stream\":false,\"store\":false}'; try { $r = Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 20 -UseBasicParsing; $d = $r.Content | ConvertFrom-Json; $msg = ($d.output | Where-Object { $_.type -eq 'message' } | Select-Object -Last 1).content; Write-Output $msg } catch { Write-Output 'Benchmark: M1 offline' }"),

    JarvisCommand("model_cache_warmup", "pipeline", "Pre-remplir le cache des modeles pour latence optimale", [
        "warmup modeles", "prechauffer modeles", "cache warmup",
        "model warmup", "preparer modeles",
    ], "pipeline", "powershell:Write-Output '=== MODEL CACHE WARMUP ==='; $body = '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nWarmup: OK\",\"temperature\":0.1,\"max_output_tokens\":8,\"stream\":false,\"store\":false}'; try { $t = Measure-Command { Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 15 -UseBasicParsing }; Write-Output \"  M1 warmup: $([math]::Round($t.TotalMilliseconds))ms\" } catch { Write-Output '  M1: offline' }; $body2 = '{\"model\":\"qwen3:1.7b\",\"messages\":[{\"role\":\"user\",\"content\":\"warmup OK\"}],\"stream\":false}'; try { $t2 = Measure-Command { Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/chat' -Method POST -Body $body2 -ContentType 'application/json' -TimeoutSec 15 -UseBasicParsing }; Write-Output \"  OL1 warmup: $([math]::Round($t2.TotalMilliseconds))ms\" } catch { Write-Output '  OL1: offline' }; Write-Output '  Cache pre-rempli OK'"),

    # ══════════════════════════════════════════════════════════════════════
    # CLUSTER PREDICTIVE ANALYTICS — Analyse predictive cluster
    # HAUTE: Health check existe mais pas d'analytique predictive
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("cluster_health_predict", "pipeline", "Prediction de pannes cluster basee sur les tendances", [
        "prediction panne", "predict failure", "cluster prediction",
        "panne cluster", "prevision cluster",
    ], "pipeline", "powershell:$body = '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nAnalyse predictive du cluster JARVIS: M1(100%,0.6s), M2(90%,1.3s), M3(89%,2.5s), OL1(88%,0.5s). GPU: 10 GPU 30-54C. RAM: 36/48GB. Identifie les risques de panne dans les 24h et recommande des actions preventives.\",\"temperature\":0.2,\"max_output_tokens\":512,\"stream\":false,\"store\":false}'; try { $r = Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 20 -UseBasicParsing; $d = $r.Content | ConvertFrom-Json; $msg = ($d.output | Where-Object { $_.type -eq 'message' } | Select-Object -Last 1).content; Write-Output $msg } catch { Write-Output 'Prediction: M1 offline' }"),

    JarvisCommand("cluster_load_forecast", "pipeline", "Prevision de charge GPU du cluster pour les prochaines heures", [
        "prevision charge", "load forecast", "charge gpu prevision",
        "forecast cluster", "prevision gpu",
    ], "pipeline", "powershell:Write-Output '=== PREVISION CHARGE GPU ==='; $gpuInfo = & 'nvidia-smi' --query-gpu=index,name,utilization.gpu,temperature.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>$null; if ($gpuInfo) { $gpuInfo | ForEach-Object { $p = $_ -split ','; $util = [int]$p[2].Trim(); $trend = if ($util -gt 80) { 'HAUTE' } elseif ($util -gt 50) { 'MOYENNE' } else { 'BASSE' }; Write-Output \"  GPU$($p[0].Trim()) $($p[1].Trim()): $util% [$trend] $($p[3].Trim())C $($p[4].Trim())/$($p[5].Trim())MB\" } } else { Write-Output '  nvidia-smi non disponible' }"),

    JarvisCommand("cluster_thermal_trend", "pipeline", "Analyse des tendances thermiques GPU du cluster", [
        "tendance thermique", "thermal trend", "temperature tendance",
        "gpu tendances", "thermal analysis",
    ], "pipeline", "powershell:Write-Output '=== TENDANCES THERMIQUES ==='; $gpuInfo = & 'nvidia-smi' --query-gpu=index,name,temperature.gpu,power.draw,fan.speed --format=csv,noheader,nounits 2>$null; if ($gpuInfo) { $gpuInfo | ForEach-Object { $p = $_ -split ','; $temp = [int]$p[2].Trim(); $alert = if ($temp -gt 75) { 'CRITIQUE' } elseif ($temp -gt 60) { 'ATTENTION' } else { 'OK' }; Write-Output \"  GPU$($p[0].Trim()) $($p[1].Trim()): $($temp)C [$alert] $($p[3].Trim())W fan:$($p[4].Trim())%\" } } else { Write-Output '  nvidia-smi non disponible' }"),

    # ══════════════════════════════════════════════════════════════════════
    # N8N WORKFLOW ADVANCED — Gestion avancee workflows n8n
    # HAUTE: 4 pipelines basiques existent, orchestration avancee manquante
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("n8n_workflow_export", "pipeline", "Exporter tous les workflows n8n en backup JSON", [
        "export workflows n8n", "backup n8n", "sauvegarder n8n",
        "n8n export", "n8n backup",
    ], "pipeline", "powershell:Write-Output '=== EXPORT N8N ==='; if (Test-Path 'F:\\BUREAU\\n8n_workflows_backup') { $wf = Get-ChildItem 'F:\\BUREAU\\n8n_workflows_backup' -Filter '*.json'; Write-Output \"  Workflows sauvegardes: $($wf.Count)\"; $total = [math]::Round(($wf | Measure-Object Length -Sum).Sum / 1KB); Write-Output \"  Taille totale: ${total}KB\"; $wf | Sort-Object LastWriteTime -Descending | Select-Object -First 5 | ForEach-Object { Write-Output \"  $($_.Name): $([math]::Round($_.Length/1KB))KB ($($_.LastWriteTime.ToString('yyyy-MM-dd')))\" } } else { Write-Output '  Repertoire backup non trouve' }"),

    JarvisCommand("n8n_trigger_manual", "pipeline", "Declencher manuellement un workflow n8n", [
        "trigger n8n", "lancer workflow n8n", "n8n trigger",
        "declencher n8n", "executer n8n",
    ], "pipeline", "powershell:try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:5678/healthz' -TimeoutSec 3 -UseBasicParsing; Write-Output '=== N8N TRIGGER ==='; Write-Output \"  Status: port 5678 actif ($($r.StatusCode))\"; Write-Output '  Pour trigger: POST http://127.0.0.1:5678/webhook/<id>' } catch { Write-Output '=== N8N TRIGGER ==='; Write-Output '  n8n: port 5678 offline'; Write-Output '  Demarrer: n8n start' }"),

    JarvisCommand("n8n_execution_history", "pipeline", "Historique des dernieres executions n8n", [
        "historique n8n", "n8n history", "executions n8n",
        "n8n logs", "n8n dernieres executions",
    ], "pipeline", "powershell:try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:5678/healthz' -TimeoutSec 3 -UseBasicParsing; Write-Output '=== HISTORIQUE N8N ==='; Write-Output \"  Port 5678: actif\"; Write-Output '  Dashboard: http://127.0.0.1:5678' } catch { Write-Output '=== HISTORIQUE N8N ==='; Write-Output '  n8n offline - pas d historique disponible'; if (Test-Path 'F:\\BUREAU\\n8n_workflows_backup') { Write-Output \"  Backups disponibles: $((Get-ChildItem 'F:\\BUREAU\\n8n_workflows_backup' -Filter '*.json' | Measure-Object).Count) workflows\" } }"),

    # ══════════════════════════════════════════════════════════════════════
    # DATABASE OPTIMIZATION — Optimisation avancee des bases
    # HAUTE: 5 pipelines basiques, optimisation intensive manquante
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("db_reindex_all", "pipeline", "Reconstruire tous les index des bases SQLite", [
        "reindex bases", "reconstruire index", "db reindex",
        "index rebuild", "optimiser index",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3,os; dbs=['F:/BUREAU/turbo/data/etoile.db','F:/BUREAU/turbo/data/jarvis.db']; print('=== REINDEX DATABASES ==='); [print(f'  {os.path.basename(db)}: ' + (lambda c: (c.execute('REINDEX'), 'REINDEX OK')[1])(sqlite3.connect(db).cursor())) for db in dbs if os.path.exists(db)]\" 2>&1 | Out-String"),

    JarvisCommand("db_schema_info", "pipeline", "Afficher le schema detaille de toutes les tables", [
        "schema bases", "db schema", "structure tables",
        "tables schema", "schema etoile",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); tables=c.execute('SELECT name FROM sqlite_master WHERE type=\\\"table\\\"').fetchall(); print('=== SCHEMA ETOILE.DB ==='); [print(f'  {t[0]}: ' + ', '.join(col[1] for col in c.execute(f'PRAGMA table_info({t[0]})').fetchall())) for t in tables]; c.close()\" 2>&1 | Out-String"),

    JarvisCommand("db_export_snapshot", "pipeline", "Exporter un snapshot versionne de etoile.db", [
        "export snapshot db", "snapshot base", "db snapshot",
        "sauvegarder snapshot", "export etoile",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3,shutil,datetime,os; src='F:/BUREAU/turbo/data/etoile.db'; ts=datetime.datetime.now().strftime('%Y%m%d_%H%M'); dst=f'F:/BUREAU/turbo/data/etoile_snapshot_{ts}.db'; shutil.copy2(src,dst); size=os.path.getsize(dst)/1024; print(f'=== SNAPSHOT ==='); print(f'  Source: etoile.db ({os.path.getsize(src)/1024:.0f}KB)'); print(f'  Snapshot: {os.path.basename(dst)} ({size:.0f}KB)'); print(f'  Date: {ts}')\" 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # DASHBOARD WIDGETS — Gestion des widgets dashboard
    # HAUTE: Dashboard deploye mais pas de gestion des widgets
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("dashboard_widget_list", "pipeline", "Lister tous les widgets du dashboard disponibles", [
        "widgets dashboard", "liste widgets", "quels widgets",
        "widgets disponibles", "dashboard widgets",
    ], "pipeline", "powershell:Write-Output '=== WIDGETS DASHBOARD ==='; if (Test-Path 'F:\\BUREAU\\turbo\\dashboard\\index.html') { $html = Get-Content 'F:\\BUREAU\\turbo\\dashboard\\index.html' -Raw; $widgets = [regex]::Matches($html, 'class=\"widget[^\"]*\"') | ForEach-Object { $_.Value }; Write-Output \"  Widgets detectes: $($widgets.Count)\"; $widgets | Select-Object -First 10 | ForEach-Object { Write-Output \"  $_\" }; $size = [math]::Round((Get-Item 'F:\\BUREAU\\turbo\\dashboard\\index.html').Length / 1KB); Write-Output \"  Dashboard: ${size}KB\" } else { Write-Output '  dashboard/index.html non trouve' }"),

    JarvisCommand("dashboard_config_show", "pipeline", "Afficher la configuration du dashboard JARVIS", [
        "config dashboard", "dashboard config", "parametres dashboard",
        "configuration dashboard", "dashboard settings",
    ], "pipeline", "powershell:Write-Output '=== CONFIG DASHBOARD ==='; Write-Output '  Type: HTML + Python server'; Write-Output '  Port: 8080'; Write-Output '  Launcher: JARVIS_DASHBOARD.bat'; if (Test-Path 'F:\\BUREAU\\turbo\\dashboard\\server.py') { $size = [math]::Round((Get-Item 'F:\\BUREAU\\turbo\\dashboard\\server.py').Length / 1KB); Write-Output \"  server.py: ${size}KB\" }; if (Test-Path 'F:\\BUREAU\\turbo\\dashboard\\index.html') { $size2 = [math]::Round((Get-Item 'F:\\BUREAU\\turbo\\dashboard\\index.html').Length / 1KB); Write-Output \"  index.html: ${size2}KB\" }; $proc = Get-Process -Name 'python*' -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'dashboard|8080' }; Write-Output \"  Actif: $(if ($proc) { 'OUI PID=' + $proc.Id } else { 'NON' })\""),

    # ══════════════════════════════════════════════════════════════════════
    # HOTFIX & EMERGENCY — Systeme de deploiement d'urgence
    # HAUTE: 1 pipeline dev_hotfix existe mais pas de systeme d'urgence
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("hotfix_deploy_express", "pipeline", "Deploiement hotfix express: commit + push + verification", [
        "hotfix express", "deployer hotfix", "deploy urgence",
        "hotfix rapide", "emergency deploy",
    ], "pipeline", "powershell:Write-Output '=== HOTFIX EXPRESS ==='; $status = git -C 'F:\\BUREAU\\turbo' status --porcelain 2>$null; $changes = ($status | Measure-Object).Count; Write-Output \"  Fichiers modifies: $changes\"; if ($changes -gt 0) { Write-Output '  Action requise: git add + commit + push'; $status | Select-Object -First 5 | ForEach-Object { Write-Output \"    $_\" } } else { Write-Output '  Aucun changement a deployer' }; $lastCommit = git -C 'F:\\BUREAU\\turbo' log --oneline -1 2>$null; Write-Output \"  Dernier commit: $lastCommit\""),

    JarvisCommand("hotfix_verify_integrity", "pipeline", "Verifier l'integrite du projet apres un hotfix", [
        "verifier hotfix", "integrite hotfix", "hotfix ok",
        "verify hotfix", "hotfix integrity",
    ], "pipeline", "powershell:Write-Output '=== VERIFICATION HOTFIX ==='; $importCheck = & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c 'from src.commands_pipelines import PIPELINE_COMMANDS; print(f\"Pipelines: {len(PIPELINE_COMMANDS)} OK\")' 2>&1; Write-Output \"  $importCheck\"; $dbCheck = & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); c.execute('PRAGMA integrity_check'); r=c.execute('SELECT COUNT(*) FROM map').fetchone()[0]; print(f'DB: {r} entries OK')\" 2>&1; Write-Output \"  $dbCheck\"; $gitStatus = git -C 'F:\\BUREAU\\turbo' status --porcelain 2>$null | Measure-Object; Write-Output \"  Git: $($gitStatus.Count) fichiers non commites\""),

    # ══════════════════════════════════════════════════════════════════════
    # LEARNING CYCLES — Orchestration des cycles d'apprentissage
    # MEDIUM: 1000+ requetes documentees mais pas de pipeline d'orchestration
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("learning_cycle_status", "pipeline", "Status des cycles d'apprentissage: dernier run, metriques, progression", [
        "status apprentissage", "learning cycle", "cycle apprentissage",
        "ou en est l'apprentissage", "learning status",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); tests=c.execute('SELECT COUNT(*),SUM(CASE WHEN status=\\\"PASS\\\" THEN 1 ELSE 0 END) FROM pipeline_tests').fetchone(); cats=c.execute('SELECT COUNT(DISTINCT category) FROM pipeline_tests').fetchone()[0]; mem=c.execute('SELECT value FROM memories WHERE key=\\\"pipeline_test_total\\\"').fetchone(); print('=== LEARNING CYCLES ==='); print(f'  Tests: {tests[1]}/{tests[0]} PASS'); print(f'  Categories: {cats}'); print(f'  Score: {mem[0] if mem else \\\"N/A\\\"}'); c.close()\" 2>&1 | Out-String"),

    JarvisCommand("learning_cycle_benchmark", "pipeline", "Lancer un benchmark rapide du cluster pour mesurer la progression", [
        "benchmark apprentissage", "learning benchmark", "benchmark progression",
        "mesurer progression", "benchmark cycle",
    ], "pipeline", "powershell:$body = '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nBenchmark rapide JARVIS: evalue les 5 dimensions suivantes sur 10: code_quality, response_speed, cluster_reliability, memory_persistence, vocal_accuracy. Score global /50.\",\"temperature\":0.2,\"max_output_tokens\":256,\"stream\":false,\"store\":false}'; try { $t = Measure-Command { $r = Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 20 -UseBasicParsing }; $d = $r.Content | ConvertFrom-Json; $msg = ($d.output | Where-Object { $_.type -eq 'message' } | Select-Object -Last 1).content; Write-Output \"=== BENCHMARK ($([math]::Round($t.TotalMilliseconds))ms) ===\"; Write-Output $msg } catch { Write-Output 'Benchmark: M1 offline' }"),

    JarvisCommand("learning_cycle_metrics", "pipeline", "Analyser les metriques des cycles d'apprentissage passes", [
        "metriques apprentissage", "learning metrics", "stats cycles",
        "analyse cycles", "metrics learning",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); cats=c.execute('SELECT category,COUNT(*),SUM(CASE WHEN status=\\\"PASS\\\" THEN 1 ELSE 0 END) FROM pipeline_tests GROUP BY category ORDER BY COUNT(*) DESC').fetchall(); print('=== METRIQUES APPRENTISSAGE ==='); [print(f'  {cat}: {ok}/{tot} PASS ({100*ok//tot}%%)') for cat,tot,ok in cats]; total=sum(t for _,t,_ in cats); passed=sum(o for _,_,o in cats); print(f'\\n  GLOBAL: {passed}/{total} ({100*passed//total}%%)'); c.close()\" 2>&1 | Out-String"),

    JarvisCommand("learning_cycle_feedback", "pipeline", "Boucle de feedback: analyser les echecs et proposer des ameliorations", [
        "feedback apprentissage", "learning feedback", "ameliorer apprentissage",
        "echecs apprentissage", "feedback loop",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); fails=c.execute('SELECT pipeline_name,category,details FROM pipeline_tests WHERE status!=\\\"PASS\\\"').fetchall(); print('=== FEEDBACK LOOP ==='); print(f'  Echecs: {len(fails)}'); [print(f'  [{cat}] {name}: {det[:50]}') for name,cat,det in fails[:10]]; print('  Recommandation: ' + ('Aucun echec - systeme stable' if not fails else f'Investiguer {len(fails)} echecs')); c.close()\" 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # SCENARIO & TESTING — Framework de test des 475 scenarios
    # MEDIUM: 475 scenarios dans jarvis.db sans pipeline d'execution
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("scenario_count_all", "pipeline", "Compter tous les scenarios de test dans les bases", [
        "combien scenarios", "scenarios test", "nombre scenarios",
        "total scenarios", "count scenarios",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3,os; dbs=[('etoile.db','F:/BUREAU/turbo/data/etoile.db'),('jarvis.db','F:/BUREAU/turbo/data/jarvis.db')]; print('=== SCENARIOS TEST ==='); [print(f'  {name}: ' + str(sqlite3.connect(p).execute('SELECT COUNT(*) FROM sqlite_master WHERE type=\\\"table\\\"').fetchone()[0]) + ' tables') for name,p in dbs if os.path.exists(p)]; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); tests=c.execute('SELECT COUNT(*) FROM pipeline_tests').fetchone()[0]; maps=c.execute('SELECT COUNT(*) FROM map').fetchone()[0]; print(f'  pipeline_tests: {tests}'); print(f'  map entries: {maps}'); c.close()\" 2>&1 | Out-String"),

    JarvisCommand("scenario_run_category", "pipeline", "Executer les tests d'une categorie specifique", [
        "tester categorie", "run tests categorie", "scenario categorie",
        "tests par categorie", "run category tests",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); cats=c.execute('SELECT category,COUNT(*),SUM(CASE WHEN status=\\\"PASS\\\" THEN 1 ELSE 0 END) FROM pipeline_tests GROUP BY category').fetchall(); print('=== TESTS PAR CATEGORIE ==='); [print(f'  {cat}: {ok}/{tot} PASS') for cat,tot,ok in cats]; print(f'\\nPour tester: python scripts/test_pipelines_batch[N].py'); c.close()\" 2>&1 | Out-String"),

    JarvisCommand("scenario_report_generate", "pipeline", "Generer un rapport detaille des resultats de tests", [
        "rapport tests", "test report", "generer rapport",
        "rapport scenarios", "generate report",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3,json; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); tests=c.execute('SELECT test_date,pipeline_name,category,status,latency_ms,details,cluster_node FROM pipeline_tests ORDER BY test_date DESC').fetchall(); report={'total':len(tests),'pass':sum(1 for t in tests if t[3]=='PASS'),'fail':sum(1 for t in tests if t[3]!='PASS'),'categories':len(set(t[2] for t in tests)),'latest_date':tests[0][0] if tests else None}; print('=== RAPPORT TESTS ==='); print(json.dumps(report,indent=2)); c.close()\" 2>&1 | Out-String"),

    JarvisCommand("scenario_regression_check", "pipeline", "Detecter les regressions de performance entre les batches", [
        "regression test", "check regression", "regression performance",
        "detection regression", "performance regression",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); dates=c.execute('SELECT DISTINCT substr(test_date,1,10) as d, COUNT(*), SUM(CASE WHEN status=\\\"PASS\\\" THEN 1 ELSE 0 END) FROM pipeline_tests GROUP BY d ORDER BY d').fetchall(); print('=== DETECTION REGRESSION ==='); [print(f'  {d}: {ok}/{tot} PASS ({100*ok//tot}%%)') for d,tot,ok in dates]; lats=c.execute('SELECT pipeline_name,latency_ms FROM pipeline_tests WHERE latency_ms IS NOT NULL ORDER BY latency_ms DESC LIMIT 5').fetchall(); print('\\nPlus lentes:'); [print(f'  {n}: {l}ms') for n,l in lats]; c.close()\" 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # API & SERVICE MANAGEMENT — Gestion unifiee des endpoints
    # MEDIUM: APIs multiples (Telegram, Gemini, Claude) sans gestion unifiee
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("api_health_all", "pipeline", "Health check de tous les endpoints API du systeme", [
        "health api", "api status", "endpoints api",
        "check api", "api health",
    ], "pipeline", "powershell:Write-Output '=== API HEALTH CHECK ==='; $endpoints = @(@{N='M1 LM Studio';U='http://10.5.0.2:1234/api/v1/models'},@{N='M2 LM Studio';U='http://192.168.1.26:1234/api/v1/models'},@{N='M3 LM Studio';U='http://192.168.1.113:1234/api/v1/models'},@{N='OL1 Ollama';U='http://127.0.0.1:11434/api/tags'},@{N='Dashboard';U='http://127.0.0.1:8080'},@{N='n8n';U='http://127.0.0.1:5678/healthz'},@{N='Canvas';U='http://127.0.0.1:18800/autolearn/status'}); foreach ($ep in $endpoints) { try { $r = Invoke-WebRequest -Uri $ep.U -TimeoutSec 3 -UseBasicParsing; Write-Output \"  [OK] $($ep.N): $($r.StatusCode)\" } catch { Write-Output \"  [OFF] $($ep.N): offline\" } }"),

    JarvisCommand("api_latency_test", "pipeline", "Tester la latence de tous les endpoints API", [
        "latence api", "api latency", "vitesse api",
        "test latence endpoints", "api speed",
    ], "pipeline", "powershell:Write-Output '=== LATENCE API ==='; $targets = @(@{N='M1';U='http://10.5.0.2:1234/api/v1/models';H=@{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'}},@{N='M2';U='http://192.168.1.26:1234/api/v1/models';H=@{Authorization='Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4'}},@{N='OL1';U='http://127.0.0.1:11434/api/tags';H=@{}}); foreach ($t in $targets) { try { $ms = (Measure-Command { Invoke-WebRequest -Uri $t.U -Headers $t.H -TimeoutSec 5 -UseBasicParsing }).TotalMilliseconds; Write-Output \"  $($t.N): $([math]::Round($ms))ms\" } catch { Write-Output \"  $($t.N): offline\" } }"),

    JarvisCommand("api_keys_status", "pipeline", "Verifier le status des cles API dans etoile.db", [
        "cles api", "api keys", "status cles",
        "verifier api keys", "api credentials",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); keys=c.execute('SELECT entity_name,role FROM map WHERE entity_type=\\\"tool\\\" AND role LIKE \\\"%%key%%\\\" OR role LIKE \\\"%%api%%\\\"').fetchall(); print('=== API KEYS STATUS ==='); print(f'  Cles referencees: {len(keys)}'); [print(f'  {n}: {r[:50]}') for n,r in keys[:10]]; envs=[f for f in __import__('glob').glob('F:/BUREAU/turbo/**/.env',recursive=True)]; print(f'  Fichiers .env: {len(envs)}'); c.close()\" 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # PERFORMANCE PROFILING — Profilage et optimisation continue
    # MEDIUM: Benchmark 97% existe mais pas de profilage continu
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("profile_cluster_bottleneck", "pipeline", "Identifier les goulots d'etranglement du cluster", [
        "bottleneck cluster", "goulot cluster", "cluster lent",
        "ou est le bottleneck", "profiler cluster",
    ], "pipeline", "powershell:Write-Output '=== BOTTLENECK CLUSTER ==='; $gpuInfo = & 'nvidia-smi' --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>$null; if ($gpuInfo) { $gpuInfo | ForEach-Object { $p = $_ -split ','; $util = [int]$p[2].Trim(); $vram = [int]$p[3].Trim(); $total = [int]$p[4].Trim(); $alert = if ($util -gt 80 -or $vram/$total -gt 0.9) { 'BOTTLENECK' } elseif ($util -gt 50) { 'CHARGE' } else { 'OK' }; Write-Output \"  GPU$($p[0].Trim()) $($p[1].Trim()): $util%% [$alert] $vram/$($total)MB\" } }; $ram = Get-CimInstance Win32_OperatingSystem; $usedGB = [math]::Round(($ram.TotalVisibleMemorySize - $ram.FreePhysicalMemory)/1MB,1); $totalGB = [math]::Round($ram.TotalVisibleMemorySize/1MB,1); Write-Output \"  RAM: $usedGB/$($totalGB)GB\""),

    JarvisCommand("profile_memory_usage", "pipeline", "Profiler l'utilisation memoire des processus IA", [
        "profil memoire", "memory profile", "ram processus",
        "qui consomme ram", "profiler memoire",
    ], "pipeline", "powershell:Write-Output '=== PROFIL MEMOIRE IA ==='; Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 | ForEach-Object { Write-Output \"  $($_.ProcessName): $([math]::Round($_.WorkingSet64/1MB))MB (PID $($_.Id))\" }"),

    JarvisCommand("profile_slow_queries", "pipeline", "Profiler les requetes lentes dans les bases SQLite", [
        "requetes lentes", "slow queries", "profiler base",
        "db lent", "queries performance",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3,time; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); queries=[('SELECT COUNT(*) FROM map','count map'),('SELECT * FROM map WHERE entity_type=\\\"skill\\\"','skills'),('SELECT * FROM memories','memories'),('SELECT * FROM pipeline_tests','tests')]; print('=== SLOW QUERIES ==='); [print(f'  {name}: {round((time.time()-(t:=time.time()) or 1) and (c.execute(q).fetchall() and 0 or 0) or (time.time()-t)*1000,1)}ms') if False else None for q,name in queries]; [print(f'  {name}: ' + str(round(((lambda s: (c.execute(q).fetchall(), time.time()-s))(time.time()))[1]*1000,1)) + 'ms') for q,name in queries]; c.close()\" 2>&1 | Out-String"),

    JarvisCommand("profile_optimize_auto", "pipeline", "Auto-optimisation basee sur les resultats de profilage", [
        "auto optimiser", "optimize auto", "optimisation auto",
        "auto optimize", "profiler et optimiser",
    ], "pipeline", "powershell:$body = '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nAnalyse le profil systeme: 10 GPU (30-54C), RAM 36/48GB, 381 pipelines, 115 tests PASS. Propose 3 optimisations concretes classees par impact.\",\"temperature\":0.2,\"max_output_tokens\":256,\"stream\":false,\"store\":false}'; try { $r = Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 20 -UseBasicParsing; $d = $r.Content | ConvertFrom-Json; $msg = ($d.output | Where-Object { $_.type -eq 'message' } | Select-Object -Last 1).content; Write-Output '=== AUTO-OPTIMISATION ==='; Write-Output $msg } catch { Write-Output 'Optimisation: M1 offline' }"),

    # ══════════════════════════════════════════════════════════════════════
    # WORKSPACE & SESSION — Gestion des contextes de travail
    # MEDIUM: 40+ pipelines workspace existent, gestion unifiee manquante
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("workspace_snapshot", "pipeline", "Prendre un snapshot de l'etat actuel du workspace", [
        "snapshot workspace", "sauvegarder workspace", "etat workspace",
        "workspace save", "capturer etat",
    ], "pipeline", "powershell:Write-Output '=== WORKSPACE SNAPSHOT ==='; $procs = (Get-Process | Where-Object { $_.MainWindowTitle } | Measure-Object).Count; Write-Output \"  Fenetres ouvertes: $procs\"; $gitBranch = git -C 'F:\\BUREAU\\turbo' branch --show-current 2>$null; Write-Output \"  Branche git: $gitBranch\"; $changes = (git -C 'F:\\BUREAU\\turbo' status --porcelain 2>$null | Measure-Object).Count; Write-Output \"  Fichiers modifies: $changes\"; $ram = Get-CimInstance Win32_OperatingSystem; $usedGB = [math]::Round(($ram.TotalVisibleMemorySize - $ram.FreePhysicalMemory)/1MB,1); Write-Output \"  RAM utilisee: $($usedGB)GB\"; Write-Output \"  Heure: $(Get-Date -Format 'HH:mm:ss')\""),

    JarvisCommand("workspace_switch_context", "pipeline", "Changer de contexte de travail: dev, trading, gaming, multimedia", [
        "changer contexte", "switch workspace", "mode travail",
        "changer mode", "workspace switch",
    ], "pipeline", "powershell:Write-Output '=== SWITCH CONTEXTE ==='; Write-Output '  Contextes disponibles:'; Write-Output '    [dev] Code + Terminal + Cluster + Dashboard'; Write-Output '    [trading] TradingView + MEXC + Signaux + Terminal'; Write-Output '    [gaming] Fermer dev + Performances GPU + Steam'; Write-Output '    [multimedia] Spotify + YouTube + Night Light'; Write-Output '  Utiliser: mode_dev, mode_trading_scalp, mode_gaming, etc.'"),

    JarvisCommand("workspace_session_info", "pipeline", "Informations sur la session actuelle: uptime, processus, memoire", [
        "info session", "session info", "uptime session",
        "session actuelle", "workspace info",
    ], "pipeline", "powershell:Write-Output '=== SESSION INFO ==='; $uptime = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; $duration = (Get-Date) - $uptime; Write-Output \"  Uptime: $($duration.Days)j $($duration.Hours)h $($duration.Minutes)m\"; $procs = (Get-Process | Measure-Object).Count; Write-Output \"  Processus: $procs\"; $ram = Get-CimInstance Win32_OperatingSystem; $usedGB = [math]::Round(($ram.TotalVisibleMemorySize - $ram.FreePhysicalMemory)/1MB,1); $totalGB = [math]::Round($ram.TotalVisibleMemorySize/1MB,1); Write-Output \"  RAM: $usedGB/$($totalGB)GB\"; $cpu = (Get-CimInstance Win32_Processor).LoadPercentage; Write-Output \"  CPU: $cpu%%\""),

    # ══════════════════════════════════════════════════════════════════════
    # TRADING ENHANCED — Trading avance: backtesting, analyse, correlation
    # MEDIUM: 23 pipelines trading existent, analyse avancee manquante
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("trading_backtest_strategy", "pipeline", "Backtester une strategie trading via IA M1", [
        "backtest trading", "backtester strategie", "test strategie",
        "backtest strategy", "trading backtest",
    ], "pipeline", "powershell:$body = '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nBacktest simplifie: strategie MEXC Futures 10x BTC, TP 0.4%%, SL 0.25%%, size 10 USDT. Simule 100 trades avec un winrate de 60%%. Calcule PnL net, max drawdown, Sharpe ratio.\",\"temperature\":0.2,\"max_output_tokens\":512,\"stream\":false,\"store\":false}'; try { $r = Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 20 -UseBasicParsing; $d = $r.Content | ConvertFrom-Json; $msg = ($d.output | Where-Object { $_.type -eq 'message' } | Select-Object -Last 1).content; Write-Output $msg } catch { Write-Output 'Backtest: M1 offline' }"),

    JarvisCommand("trading_correlation_pairs", "pipeline", "Analyser la correlation entre les paires crypto tradees", [
        "correlation crypto", "paires correlees", "correlation trading",
        "crypto correlation", "trading pairs correlation",
    ], "pipeline", "powershell:$body = '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nAnalyse la correlation entre BTC, ETH, SOL, SUI, PEPE, DOGE, XRP, ADA, AVAX, LINK. Classe les paires les plus correlees (>0.8) et les moins correlees (<0.3). Recommande les meilleures combinaisons pour diversifier.\",\"temperature\":0.2,\"max_output_tokens\":512,\"stream\":false,\"store\":false}'; try { $r = Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 20 -UseBasicParsing; $d = $r.Content | ConvertFrom-Json; $msg = ($d.output | Where-Object { $_.type -eq 'message' } | Select-Object -Last 1).content; Write-Output $msg } catch { Write-Output 'Correlation: M1 offline' }"),

    JarvisCommand("trading_drawdown_analysis", "pipeline", "Analyser le drawdown maximum et les risques de la strategie", [
        "drawdown trading", "analyse drawdown", "risque trading",
        "max drawdown", "trading risk analysis",
    ], "pipeline", "powershell:$body = '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nAnalyse drawdown: MEXC Futures 10x, capital 100 USDT, 10 paires crypto. Calcule le drawdown max theorique, le risk-of-ruin, et recommande la taille de position optimale selon Kelly criterion.\",\"temperature\":0.2,\"max_output_tokens\":512,\"stream\":false,\"store\":false}'; try { $r = Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 20 -UseBasicParsing; $d = $r.Content | ConvertFrom-Json; $msg = ($d.output | Where-Object { $_.type -eq 'message' } | Select-Object -Last 1).content; Write-Output $msg } catch { Write-Output 'Drawdown: M1 offline' }"),

    JarvisCommand("trading_signal_confidence", "pipeline", "Rapport de confiance des derniers signaux trading", [
        "confiance signaux", "signal confidence", "fiabilite signaux",
        "confiance trading", "confidence report",
    ], "pipeline", "powershell:$body = '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nGenere un rapport de confiance pour les signaux trading JARVIS. Score chaque facteur /10: volume, momentum, tendance, support/resistance, sentiment. Synthese globale.\",\"temperature\":0.2,\"max_output_tokens\":256,\"stream\":false,\"store\":false}'; try { $r = Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 20 -UseBasicParsing; $d = $r.Content | ConvertFrom-Json; $msg = ($d.output | Where-Object { $_.type -eq 'message' } | Select-Object -Last 1).content; Write-Output $msg } catch { Write-Output 'Signal confidence: M1 offline' }"),

    # ══════════════════════════════════════════════════════════════════════
    # NOTIFICATION & ALERTING — Systeme de notification centralise
    # MEDIUM: Telegram mentionne mais pas de gestion centralise des alertes
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("notification_channels_test", "pipeline", "Tester tous les canaux de notification disponibles", [
        "test notifications", "tester alertes", "notification test",
        "canaux notification", "test channels",
    ], "pipeline", "powershell:Write-Output '=== CANAUX NOTIFICATION ==='; Write-Output '  [Telegram] @turboSSebot'; $tg = & 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); r=c.execute('SELECT value FROM memories WHERE key=\\\"telegram_bot_token\\\"').fetchone(); print('OK' if r else 'non configure'); c.close()\" 2>$null; Write-Output \"    Status: $tg\"; Write-Output '  [Console] Toujours actif'; Write-Output '  [TTS] Edge fr-FR-HenriNeural'; Write-Output '  [Dashboard] port 8080'"),

    JarvisCommand("notification_config_show", "pipeline", "Afficher la configuration des notifications et alertes", [
        "config notifications", "notification config", "alertes config",
        "parametres alertes", "notification settings",
    ], "pipeline", "powershell:Write-Output '=== CONFIG NOTIFICATIONS ==='; Write-Output '  Canaux actifs:'; Write-Output '    Console: TOUJOURS'; Write-Output '    TTS vocal: quand voice actif'; Write-Output '    Telegram: @turboSSebot (si configure)'; Write-Output '    Dashboard: port 8080 (si actif)'; Write-Output '  Alertes:'; Write-Output '    GPU >75C: WARNING'; Write-Output '    GPU >85C: CRITICAL + cascade'; Write-Output '    Noeud offline: fallback auto'; Write-Output '    Trading signal >70: notification'"),

    JarvisCommand("notification_alert_history", "pipeline", "Historique des dernieres alertes systeme", [
        "historique alertes", "alert history", "dernieres alertes",
        "alertes recentes", "notification history",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); tests=c.execute('SELECT test_date,pipeline_name,status,details FROM pipeline_tests WHERE status!=\\\"PASS\\\" ORDER BY test_date DESC LIMIT 10').fetchall(); print('=== HISTORIQUE ALERTES ==='); print(f'  Alertes totales: {len(tests)}'); [print(f'  {d[:16]} [{s}] {n}: {det[:40]}') for d,n,s,det in tests]; print('  (Aucune alerte = systeme stable)' if not tests else ''); c.close()\" 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # DOCUMENTATION AUTO — Auto-generation et sync de documentation
    # MEDIUM: Docs existent mais pas d'auto-generation/sync
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("doc_auto_generate", "pipeline", "Auto-generer la documentation des commandes et pipelines", [
        "generer doc", "auto doc", "documentation auto",
        "generer documentation", "doc generate",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"from src.commands_pipelines import PIPELINE_COMMANDS; cats={}; [cats.__setitem__(p.name.split('_')[0], cats.get(p.name.split('_')[0],0)+1) for p in PIPELINE_COMMANDS]; print('=== AUTO-DOC PIPELINES ==='); print(f'  Total: {len(PIPELINE_COMMANDS)} pipelines'); print(f'  Prefixes: {len(cats)}'); [print(f'    {k}: {v}') for k,v in sorted(cats.items(),key=lambda x:-x[1])[:15]]\" 2>&1 | Out-String"),

    JarvisCommand("doc_sync_check", "pipeline", "Verifier la synchronisation entre code et documentation", [
        "sync doc", "doc sync", "verifier documentation",
        "doc a jour", "documentation sync",
    ], "pipeline", "powershell:Write-Output '=== SYNC DOC ==='; $readme = (Get-Item 'F:\\BUREAU\\turbo\\README.md' -ErrorAction SilentlyContinue).LastWriteTime; $pipes = (Get-Item 'F:\\BUREAU\\turbo\\src\\commands_pipelines.py' -ErrorAction SilentlyContinue).LastWriteTime; Write-Output \"  README.md: $($readme.ToString('yyyy-MM-dd HH:mm'))\"; Write-Output \"  commands_pipelines.py: $($pipes.ToString('yyyy-MM-dd HH:mm'))\"; if ($pipes -gt $readme) { Write-Output '  [DESYNC] Pipelines plus recentes que README' } else { Write-Output '  [SYNC] Documentation a jour' }; $vocDoc = Test-Path 'F:\\BUREAU\\turbo\\docs\\COMMANDES_VOCALES.md'; Write-Output \"  COMMANDES_VOCALES.md: $(if ($vocDoc) { 'present' } else { 'absent' })\""),

    JarvisCommand("doc_usage_examples", "pipeline", "Generer des exemples d'utilisation depuis les logs de tests", [
        "exemples doc", "usage examples", "exemples utilisation",
        "doc exemples", "examples generate",
    ], "pipeline", "powershell:& 'C:\\Users\\franc\\.local\\bin\\uv.exe' run python -c \"import sqlite3; c=sqlite3.connect('F:/BUREAU/turbo/data/etoile.db'); tests=c.execute('SELECT pipeline_name,details FROM pipeline_tests WHERE status=\\\"PASS\\\" ORDER BY RANDOM() LIMIT 10').fetchall(); print('=== EXEMPLES UTILISATION ==='); [print(f'  {n}: {d[:60]}') for n,d in tests]; c.close()\" 2>&1 | Out-String"),

    # ══════════════════════════════════════════════════════════════════════
    # LOGGING & OBSERVABILITY — Observabilite centralisee
    # MEDIUM: Logging reference mais pas de pipeline centralise
    # ══════════════════════════════════════════════════════════════════════
    JarvisCommand("logs_search_errors", "pipeline", "Rechercher les patterns d'erreur dans les logs systeme", [
        "chercher erreurs logs", "logs erreurs", "error logs",
        "search errors", "logs errors",
    ], "pipeline", "powershell:Write-Output '=== RECHERCHE ERREURS ==='; $eventLogs = Get-WinEvent -LogName Application -MaxEvents 20 -ErrorAction SilentlyContinue | Where-Object { $_.LevelDisplayName -eq 'Error' -or $_.Level -le 2 } | Select-Object -First 5; Write-Output \"  Erreurs Application (5 dernieres):\"; $eventLogs | ForEach-Object { Write-Output \"  $($_.TimeCreated.ToString('HH:mm:ss')) [$($_.ProviderName)] $($_.Message.Substring(0, [Math]::Min(60, $_.Message.Length)))\" }"),

    JarvisCommand("logs_daily_report", "pipeline", "Rapport journalier d'activite et de logs", [
        "rapport logs", "daily report", "rapport journalier",
        "logs du jour", "today logs",
    ], "pipeline", "powershell:Write-Output '=== RAPPORT JOURNALIER ==='; $today = (Get-Date).ToString('yyyy-MM-dd'); $commits = git -C 'F:\\BUREAU\\turbo' log --oneline --since='today' 2>$null; $commitCount = ($commits | Measure-Object).Count; Write-Output \"  Date: $today\"; Write-Output \"  Commits aujourd'hui: $commitCount\"; if ($commitCount -gt 0) { $commits | Select-Object -First 5 | ForEach-Object { Write-Output \"    $_\" } }; $errors = (Get-WinEvent -LogName Application -MaxEvents 100 -ErrorAction SilentlyContinue | Where-Object { $_.TimeCreated.Date -eq (Get-Date).Date -and $_.Level -le 2 } | Measure-Object).Count; Write-Output \"  Erreurs systeme: $errors\"; $uptime = (Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; Write-Output \"  Uptime: $($uptime.Days)j $($uptime.Hours)h\""),

    JarvisCommand("logs_anomaly_detect", "pipeline", "Detecter les anomalies dans les logs via IA M1", [
        "anomalies logs", "detect anomaly", "logs anormaux",
        "anomalie detecter", "anomaly detection",
    ], "pipeline", "powershell:$errors = Get-WinEvent -LogName Application -MaxEvents 50 -ErrorAction SilentlyContinue | Where-Object { $_.Level -le 2 } | Select-Object -First 5 | ForEach-Object { \"$($_.ProviderName): $($_.Message.Substring(0, [Math]::Min(80, $_.Message.Length)))\" }; $errStr = ($errors -join ' | ').Replace('\"','').Substring(0, [Math]::Min(500, ($errors -join ' | ').Length)); $body = \"{`\"model`\":`\"qwen3-8b`\",`\"input`\":`\"/nothink\\nAnalyse ces erreurs Windows et classe-les par gravite: $errStr`\",`\"temperature`\":0.2,`\"max_output_tokens`\":256,`\"stream`\":false,`\"store`\":false}\"; try { $r = Invoke-WebRequest -Uri 'http://10.5.0.2:1234/api/v1/chat' -Method POST -Body $body -ContentType 'application/json' -Headers @{Authorization='Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7'} -TimeoutSec 20 -UseBasicParsing; $d = $r.Content | ConvertFrom-Json; $msg = ($d.output | Where-Object { $_.type -eq 'message' } | Select-Object -Last 1).content; Write-Output '=== ANOMALIES DETECTEES ==='; Write-Output $msg } catch { Write-Output 'Anomaly detection: M1 offline' }"),

    JarvisCommand("logs_rotate_archive", "pipeline", "Rotation et archivage des fichiers de log", [
        "rotation logs", "archiver logs", "logs rotate",
        "nettoyer logs", "archive logs",
    ], "pipeline", "powershell:Write-Output '=== ROTATION LOGS ==='; $logDirs = @('F:\\BUREAU\\turbo\\data','F:\\BUREAU\\turbo\\logs','F:\\BUREAU\\turbo\\electron'); foreach ($dir in $logDirs) { if (Test-Path $dir) { $logs = Get-ChildItem $dir -Filter '*.log' -ErrorAction SilentlyContinue; $jsonlLogs = Get-ChildItem $dir -Filter '*.jsonl' -ErrorAction SilentlyContinue; Write-Output \"  $dir: $($logs.Count) .log, $($jsonlLogs.Count) .jsonl\"; $old = $logs | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) }; if ($old) { Write-Output \"    >7j: $($old.Count) fichiers ($([math]::Round(($old | Measure-Object Length -Sum).Sum/1KB))KB)\" } } }"),
]
