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
]
