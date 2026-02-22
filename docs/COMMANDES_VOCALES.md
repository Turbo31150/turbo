# Commandes Vocales JARVIS - Reference Complete

> Mise a jour automatique: 2026-02-22 | Voice Pipeline v2

**652 commandes** au total, dont **81 pipelines** multi-etapes, reparties en **14 categories**.

| Categorie | Nombre |
|-----------|--------|
| Systeme Windows | 292 |
| Pipelines Multi-Etapes | 81 |
| Navigation Web | 77 |
| Developpement & Outils | 57 |
| Fichiers & Documents | 32 |
| Applications | 23 |
| Trading & IA | 19 |
| Fenetres Windows | 13 |
| Presse-papier & Saisie | 13 |
| Controle JARVIS | 12 |
| Launchers JARVIS | 12 |
| Accessibilite | 10 |
| Controle Media | 7 |
| Saisie & Texte | 4 |
| **TOTAL** | **652** |

---

## Pipelines Multi-Etapes

Les pipelines executent plusieurs actions en sequence (separees par `;;`).

| Pipeline | Trigger principal | Actions |
|----------|------------------|---------|
| range_bureau | "range mon bureau" | MinimizeAll |
| va_sur_mails_comet | "va sur mes mails" | Comet: https://mail.google.com |
| mode_travail | "mode travail" | Ouvrir vscode > pause 1s > Ouvrir terminal |
| mode_trading | "mode trading" | Web: https://www.tradingview.com > Web: https://www.mexc.com > Web: http://127.0.0.1:8080 |
| rapport_matin | "rapport du matin" | Comet: https://mail.google.com > pause 1s > Web: https://www.tradingview.com > Web: http://127.0.0.1:8080 |
| bonne_nuit | "bonne nuit" | MinimizeAll > pause 1s > Lock PC (confirm) |
| mode_focus | "mode focus" | MinimizeAll > Settings |
| mode_cinema | "mode cinema" | MinimizeAll > pause 1s > Web: https://www.netflix.com |
| ouvre_youtube_comet | "ouvre youtube sur comet" | Comet: https://youtube.com |
| ouvre_github_comet | "ouvre github sur comet" | Comet: https://github.com |
| ouvre_cluster | "ouvre le cluster" | Web: http://127.0.0.1:8080 > Web: http://10.5.0.2:1234 |
| ferme_tout | "ferme tout" | MinimizeAll (confirm) |
| mode_musique | "mode musique" | MinimizeAll > pause 1s > Ouvrir spotify |
| mode_gaming | "mode gaming" | powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c > pause 1s > Ouvrir steam > pause 2s > Raccourci: win+g |
| mode_stream | "mode stream" | MinimizeAll > pause 1s > Ouvrir obs64 > pause 2s > Ouvrir spotify |
| mode_presentation | "mode presentation" | DisplaySwitch.exe /clone > pause 2s > Ouvrir powerpnt |
| mode_lecture | "mode lecture" | MinimizeAll > pause 1s > Comet: C:\Users\franc\AppData\Local\Perplexity\Comet\Application\comet.exe |
| mode_reunion | "mode reunion" | Ouvrir discord > pause 1s > Settings |
| mode_code_turbo | "mode code turbo" | Ouvrir code > pause 1s > Ouvrir wt > pause 1s > Ouvrir lmstudio > pause 1s > Web: http://127.0.0.1:8080 |
| mode_detente | "mode detente" | MinimizeAll > pause 1s > Ouvrir spotify > pause 1s > Start-Process ms-settings:nightlight |
| routine_soir | "routine du soir" | Web: https://www.tradingview.com > pause 2s > Start-Process ms-settings:nightlight > pause 1s > MinimizeAll |
| check_trading_rapide | "check trading rapide" | Web: https://www.tradingview.com > Web: https://www.mexc.com |
| setup_ia | "setup ia" | Ouvrir lmstudio > pause 1s > Web: http://127.0.0.1:8080 > pause 1s > Ouvrir wt |
| nettoyage_express | "nettoyage express" | Clear-RecycleBin -Force -ErrorAction SilentlyConti... > Remove-Item $env:TEMP\* -Recurse -Force -ErrorActi... > ipcon... (confirm) |
| diagnostic_complet | "diagnostic complet" | Tool: system_info > Tool: gpu_info > $os = Get-CimInstance Win32_OperatingSystem; $tota... > Get-PhysicalDisk | Selec... |
| debug_reseau | "debug reseau" | ipconfig /flushdns; 'DNS purge' > $p = Test-Connection 8.8.8.8 -Count 2 -ErrorAction... > $d = Resolve-DnsName google... |
| veille_securisee | "veille securisee" | MinimizeAll > pause 1s > Lock PC > pause 2s > Veille (confirm) |
| ouvre_reddit_comet | "ouvre reddit sur comet" | Comet: https://www.reddit.com |
| ouvre_twitter_comet | "ouvre twitter sur comet" | Comet: https://x.com |
| ouvre_chatgpt_comet | "ouvre chatgpt sur comet" | Comet: https://chat.openai.com |
| ouvre_claude_comet | "ouvre claude sur comet" | Comet: https://claude.ai |
| ouvre_linkedin_comet | "ouvre linkedin sur comet" | Comet: https://www.linkedin.com |
| ouvre_amazon_comet | "ouvre amazon sur comet" | Comet: https://www.amazon.fr |
| ouvre_twitch_comet | "ouvre twitch sur comet" | Comet: https://www.twitch.tv |
| ouvre_social_comet | "ouvre les reseaux sociaux comet" | Comet: https://x.com > pause 1s > Comet: https://www.reddit.com > pause 1s > Ouvrir discord |
| ouvre_perplexity_comet | "ouvre perplexity sur comet" | Comet: https://www.perplexity.ai |
| ouvre_huggingface_comet | "ouvre hugging face sur comet" | Comet: https://huggingface.co |
| mode_crypto | "mode crypto" | Web: https://www.tradingview.com > pause 1s > Web: https://www.mexc.com/exchange/BTC_USDT > pause 1s > Web: https://w... |
| mode_ia_complet | "mode ia complet" | Ouvrir lmstudio > pause 1s > Web: http://127.0.0.1:8080 > pause 1s > Web: https://claude.ai > pause 1s > Web: https:/... |
| mode_debug | "mode debug" | Ouvrir wt > pause 1s > nvidia-smi > Get-WinEvent -FilterHashtable @{LogName='System';L... |
| mode_monitoring | "mode monitoring" | Web: http://127.0.0.1:8080 > pause 1s > nvidia-smi --query-gpu=name,temperature.gpu,utiliz... > $m2 = try{(Invoke-Web... |
| mode_communication | "mode communication" | Ouvrir discord > pause 1s > Ouvrir telegram > pause 1s > Ouvrir whatsapp |
| mode_documentation | "mode documentation" | Web: https://www.notion.so > pause 1s > Web: https://docs.google.com > pause 1s > Web: https://drive.google.com |
| mode_focus_total | "mode focus total" | MinimizeAll > pause 1s > Settings > pause 1s > Start-Process ms-settings:nightlight > pause 1s > Ouvrir code |
| mode_review | "mode review" | Ouvrir code > pause 1s > Web: https://github.com > pause 1s > Ouvrir wt |
| routine_matin | "routine du matin" | Ouvrir lmstudio > pause 2s > Web: http://127.0.0.1:8080 > pause 1s > Web: https://www.tradingview.com > pause 1s > We... |
| backup_express | "backup express" | cd F:\BUREAU\turbo; git add -A; git commit -m 'Bac... (confirm) |
| reboot_cluster | "reboot le cluster" | Stop-Process -Name 'ollama' -Force -ErrorAction Si... > pause 3s > $m2 = try{(Invoke-WebRequest -Uri 'http://192.168.... |
| pause_travail | "pause travail" | MinimizeAll > pause 1s > Ouvrir spotify > pause 2s > Lock PC |
| fin_journee | "fin de journee" | cd F:\BUREAU\turbo; git add -A; git commit -m 'Fin... > pause 1s > Start-Process ms-settings:nightlight > pause 1s > ... |
| ouvre_github_via_comet | "ouvre github sur comet" | Comet: https://github.com |
| ouvre_youtube_via_comet | "ouvre youtube sur comet" | Comet: https://www.youtube.com |
| ouvre_tradingview_comet | "ouvre tradingview sur comet" | Comet: https://www.tradingview.com |
| ouvre_coingecko_comet | "ouvre coingecko sur comet" | Comet: https://www.coingecko.com |
| ouvre_ia_comet | "ouvre toutes les ia comet" | Comet: https://chat.openai.com > pause 1s > Comet: https://claude.ai > pause 1s > Comet: https://www.perplexity.ai |
| mode_cinema_complet | "mode cinema complet" | MinimizeAll > pause 1s > Start-Process ms-settings:nightlight > pause 1s > Web: https://www.netflix.com > pause 2s > ... |
| mode_workout | "mode workout" | Ouvrir spotify > pause 2s > Web: https://www.youtube.com/results?search_query=workout+timer+30+min > pause 1s > $t=Ne... |
| mode_etude | "mode etude" | MinimizeAll > pause 1s > Settings > pause 1s > Web: https://fr.wikipedia.org > pause 1s > Web: https://docs.google.com |
| mode_diner | "mode diner" | MinimizeAll > pause 1s > Start-Process ms-settings:nightlight > pause 1s > Ouvrir spotify |
| routine_depart | "routine depart" | cd F:\BUREAU\turbo; git add -A; git commit -m 'Aut... > pause 1s > MinimizeAll > pause 1s > powercfg /setactive a1841... (confirm) |
| routine_retour | "routine retour" | powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c > pause 1s > Ouvrir lmstudio > pause 2s > Web: https://mail.... |
| mode_nuit_totale | "mode nuit totale" | MinimizeAll > pause 1s > Start-Process ms-settings:nightlight > pause 1s > (New-Object -ComObject WScript.Shell).Send... (confirm) |
| dev_morning_setup | "dev morning" | cd F:\BUREAU\turbo; git pull --rebase 2>&1 | Out-String > pause 1s > Ouvrir code > pause 2s > Ouvrir wt > pause 1s > ... |
| dev_deep_work | "deep work" | Stop-Process -Name 'discord','telegram','slack' -F... > pause 1s > MinimizeAll > pause 1s > Settings > pause 1s > Ouv... |
| dev_standup_prep | "standup prep" | cd F:\BUREAU\turbo; git log --since='yesterday' --... > pause 1s > Web: https://github.com > pause 1s > Web: http://1... |
| dev_deploy_check | "check avant deploy" | cd F:\BUREAU\turbo; & 'C:\Users\franc\.local\bin\u... > cd F:\BUREAU\turbo; git status -sb > docker ps --format 'tabl... |
| dev_friday_report | "rapport vendredi" | cd F:\BUREAU\turbo; 'Commits cette semaine:'; git ... > cd F:\BUREAU\turbo; $py = (Get-ChildItem src/*.py ... > Web: ... |
| dev_code_review_setup | "setup code review" | Web: https://github.com/pulls > pause 1s > Ouvrir code > pause 1s > cd F:\BUREAU\turbo; git diff --stat 2>&1 | Out-St... |
| audit_securite_complet | "audit securite complet" | Get-MpComputerStatus | Select AntivirusEnabled, Re... > Get-NetTCPConnection -State Listen | Group-Object ... > Get-N... |
| rapport_systeme_complet | "rapport systeme complet" | $cpu = (Get-CimInstance Win32_Processor).Name; $us... > $os = Get-CimInstance Win32_OperatingSystem; $used... > nvidi... |
| maintenance_totale | "maintenance totale" | Clear-RecycleBin -Force -ErrorAction SilentlyConti... > Remove-Item $env:TEMP\* -Recurse -Force -ErrorActi... > Remov... (confirm) |
| sauvegarde_tous_projets | "sauvegarde tous les projets" | cd F:\BUREAU\turbo; git add -A; git commit -m 'Bac... > cd F:\BUREAU\carV1; if(Test-Path .git){git add -A;... > cd F:... (confirm) |
| pomodoro_start | "pomodoro" | Stop-Process -Name 'discord','telegram','slack' -F... > MinimizeAll > pause 1s > Ouvrir code > $end = (Get-Date).AddM... |
| pomodoro_break | "pause pomodoro" | MinimizeAll > pause 1s > Ouvrir spotify > $end = (Get-Date).AddMinutes(5).ToString('HH:mm');... |
| mode_entretien | "mode entretien" | Stop-Process -Name 'spotify' -Force -ErrorAction S... > MinimizeAll > pause 1s > Settings > pause 1s > Ouvrir discord |
| mode_recherche | "mode recherche" | Web: https://www.perplexity.ai > pause 1s > Web: https://scholar.google.com > pause 1s > Web: https://fr.wikipedia.or... |
| mode_youtube | "mode youtube" | MinimizeAll > pause 1s > Web: https://www.youtube.com > pause 2s > Raccourci: f11 |
| mode_spotify_focus | "spotify focus" | MinimizeAll > pause 1s > Ouvrir spotify > pause 1s > Settings |
| ouvre_tout_dev_web | "dev web complet" | Ouvrir code > pause 1s > Ouvrir wt > pause 1s > Web: http://localhost:3000 > pause 1s > Web: https://www.npmjs.com |
| mode_twitch_stream | "mode twitch" | Ouvrir obs64 > pause 2s > Web: https://dashboard.twitch.tv > pause 1s > Ouvrir spotify > pause 1s > Web: https://www.... |
| mode_email_productif | "mode email" | Stop-Process -Name 'discord','telegram','slack' -F... > MinimizeAll > pause 1s > Web: https://mail.google.com > pause... |

---

## Listing Complet par Categorie

### Navigation Web (77 commandes)

| Commande | Description | Triggers | Type |
|----------|------------|----------|------|
| ouvrir_chrome | Ouvrir Google Chrome | "ouvre chrome", "ouvrir chrome", "lance chrome", +7 | app_open |
| ouvrir_comet | Ouvrir Comet Browser | "ouvre comet", "ouvrir comet", "lance comet", +1 | app_open |
| aller_sur_site | Naviguer vers un site web | "va sur {site}", "ouvre {site}", "navigue vers {site}", +5 | browser |
| chercher_google | Rechercher sur Google | "cherche {requete}", "recherche {requete}", "google {requete}", +4 | browser |
| chercher_youtube | Rechercher sur YouTube | "cherche sur youtube {requete}", "youtube {requete}", "recherche sur youtube {requete}", +1 | browser |
| ouvrir_gmail | Ouvrir Gmail | "ouvre gmail", "ouvrir gmail", "ouvre mes mails", +6 | browser |
| ouvrir_youtube | Ouvrir YouTube | "ouvre youtube", "va sur youtube", "lance youtube", +2 | browser |
| ouvrir_github | Ouvrir GitHub | "ouvre github", "va sur github", "ouvrir github" | browser |
| ouvrir_tradingview | Ouvrir TradingView | "ouvre tradingview", "va sur tradingview", "lance tradingview", +2 | browser |
| ouvrir_mexc | Ouvrir MEXC | "ouvre mexc", "va sur mexc", "lance mexc", +5 | browser |
| nouvel_onglet | Ouvrir un nouvel onglet | "nouvel onglet", "nouveau tab", "ouvre un nouvel onglet", +1 | hotkey |
| fermer_onglet | Fermer l'onglet actif | "ferme l'onglet", "ferme cet onglet", "ferme le tab", +2 | hotkey |
| mode_incognito | Ouvrir Chrome en mode incognito | "mode incognito", "navigation privee", "ouvre en prive", +2 | powershell |
| historique_chrome | Ouvrir l'historique Chrome | "historique chrome", "ouvre l'historique", "historique navigateur", +1 | hotkey |
| favoris_chrome | Ouvrir les favoris Chrome | "ouvre les favoris", "favoris", "bookmarks", +2 | hotkey |
| telecharger_chrome | Ouvrir les telechargements Chrome | "telechargements chrome", "ouvre les downloads", "mes telechargements navigateur" | hotkey |
| nouvel_onglet | Ouvrir un nouvel onglet Chrome | "nouvel onglet", "ouvre un onglet", "nouveau tab", +2 | hotkey |
| onglet_precedent | Onglet precedent Chrome | "onglet precedent", "tab precedent", "onglet d'avant", +1 | hotkey |
| onglet_suivant | Onglet suivant Chrome | "onglet suivant", "tab suivant", "prochain onglet", +1 | hotkey |
| rouvrir_onglet | Rouvrir le dernier onglet ferme | "rouvre l'onglet", "rouvrir onglet", "restaure l'onglet", +2 | hotkey |
| chrome_favoris | Ouvrir les favoris Chrome | "ouvre les favoris", "mes favoris", "bookmarks", +2 | hotkey |
| chrome_telechargements | Ouvrir les telechargements Chrome | "telechargements chrome", "mes telechargements chrome", "fichiers telecharges", +1 | hotkey |
| chrome_plein_ecran | Chrome en plein ecran (F11) | "plein ecran", "chrome plein ecran", "fullscreen", +2 | hotkey |
| chrome_zoom_plus | Zoom avant Chrome | "zoom avant chrome", "agrandir la page", "plus grand", +2 | hotkey |
| chrome_zoom_moins | Zoom arriere Chrome | "zoom arriere chrome", "reduire la page", "plus petit", +2 | hotkey |
| chrome_zoom_reset | Reinitialiser le zoom Chrome | "zoom normal", "zoom 100", "reinitialise le zoom", +2 | hotkey |
| meteo | Afficher la meteo | "meteo", "la meteo", "quelle meteo", +9 | browser |
| ouvrir_twitter | Ouvrir Twitter/X | "ouvre twitter", "va sur twitter", "ouvre x", +2 | browser |
| ouvrir_reddit | Ouvrir Reddit | "ouvre reddit", "va sur reddit", "lance reddit", +1 | browser |
| ouvrir_linkedin | Ouvrir LinkedIn | "ouvre linkedin", "va sur linkedin", "lance linkedin", +1 | browser |
| ouvrir_instagram | Ouvrir Instagram | "ouvre instagram", "va sur instagram", "lance instagram", +2 | browser |
| ouvrir_tiktok | Ouvrir TikTok | "ouvre tiktok", "va sur tiktok", "lance tiktok" | browser |
| ouvrir_twitch | Ouvrir Twitch | "ouvre twitch", "va sur twitch", "lance twitch", +1 | browser |
| ouvrir_chatgpt | Ouvrir ChatGPT | "ouvre chatgpt", "va sur chatgpt", "lance chatgpt", +2 | browser |
| ouvrir_claude | Ouvrir Claude AI | "ouvre claude", "va sur claude", "lance claude", +2 | browser |
| ouvrir_perplexity | Ouvrir Perplexity | "ouvre perplexity", "va sur perplexity", "lance perplexity", +1 | browser |
| ouvrir_huggingface | Ouvrir Hugging Face | "ouvre hugging face", "va sur hugging face", "lance hugging face", +1 | browser |
| ouvrir_wikipedia | Ouvrir Wikipedia | "ouvre wikipedia", "va sur wikipedia", "lance wikipedia", +1 | browser |
| ouvrir_amazon | Ouvrir Amazon | "ouvre amazon", "va sur amazon", "lance amazon", +1 | browser |
| ouvrir_leboncoin | Ouvrir Leboncoin | "ouvre leboncoin", "va sur leboncoin", "lance leboncoin", +2 | browser |
| ouvrir_netflix | Ouvrir Netflix | "ouvre netflix", "va sur netflix", "lance netflix" | browser |
| ouvrir_spotify_web | Ouvrir Spotify Web Player | "ouvre spotify web", "spotify web", "lance spotify en ligne", +1 | browser |
| ouvrir_disney_plus | Ouvrir Disney+ | "ouvre disney plus", "va sur disney plus", "lance disney", +1 | browser |
| ouvrir_stackoverflow | Ouvrir Stack Overflow | "ouvre stackoverflow", "va sur stackoverflow", "ouvre stack overflow", +1 | browser |
| ouvrir_npmjs | Ouvrir NPM | "ouvre npm", "va sur npm", "ouvre npmjs", +1 | browser |
| ouvrir_pypi | Ouvrir PyPI | "ouvre pypi", "va sur pypi", "lance pypi", +1 | browser |
| ouvrir_docker_hub | Ouvrir Docker Hub | "ouvre docker hub", "va sur docker hub", "lance docker hub" | browser |
| ouvrir_google_drive | Ouvrir Google Drive | "ouvre google drive", "va sur google drive", "ouvre drive", +2 | browser |
| ouvrir_google_docs | Ouvrir Google Docs | "ouvre google docs", "va sur google docs", "ouvre docs", +1 | browser |
| ouvrir_google_sheets | Ouvrir Google Sheets | "ouvre google sheets", "va sur google sheets", "ouvre sheets", +1 | browser |
| ouvrir_google_maps | Ouvrir Google Maps | "ouvre google maps", "va sur google maps", "ouvre maps", +2 | browser |
| ouvrir_google_calendar | Ouvrir Google Calendar | "ouvre google calendar", "ouvre l'agenda", "ouvre le calendrier", +2 | browser |
| ouvrir_notion | Ouvrir Notion | "ouvre notion", "va sur notion", "lance notion", +1 | browser |
| chercher_images | Rechercher des images sur Google | "cherche des images de {requete}", "images de {requete}", "google images {requete}", +1 | browser |
| chercher_reddit | Rechercher sur Reddit | "cherche sur reddit {requete}", "reddit {requete}", "recherche reddit {requete}" | browser |
| chercher_wikipedia | Rechercher sur Wikipedia | "cherche sur wikipedia {requete}", "wikipedia {requete}", "wiki {requete}" | browser |
| chercher_amazon | Rechercher sur Amazon | "cherche sur amazon {requete}", "amazon {requete}", "recherche amazon {requete}", +1 | browser |
| ouvrir_tradingview_web | Ouvrir TradingView | "ouvre tradingview", "va sur tradingview", "lance tradingview", +1 | browser |
| ouvrir_coingecko | Ouvrir CoinGecko | "ouvre coingecko", "va sur coingecko", "lance coingecko", +1 | browser |
| ouvrir_coinmarketcap | Ouvrir CoinMarketCap | "ouvre coinmarketcap", "va sur coinmarketcap", "lance coinmarketcap", +1 | browser |
| ouvrir_mexc_exchange | Ouvrir MEXC Exchange | "ouvre mexc", "va sur mexc", "lance mexc", +1 | browser |
| ouvrir_dexscreener | Ouvrir DexScreener | "ouvre dexscreener", "va sur dexscreener", "lance dexscreener", +1 | browser |
| ouvrir_telegram_web | Ouvrir Telegram Web | "ouvre telegram web", "telegram web", "telegram en ligne", +1 | browser |
| ouvrir_whatsapp_web | Ouvrir WhatsApp Web | "ouvre whatsapp web", "whatsapp web", "whatsapp en ligne", +1 | browser |
| ouvrir_slack_web | Ouvrir Slack Web | "ouvre slack web", "slack web", "slack en ligne", +1 | browser |
| ouvrir_teams_web | Ouvrir Microsoft Teams Web | "ouvre teams web", "teams web", "teams en ligne", +1 | browser |
| ouvrir_youtube_music | Ouvrir YouTube Music | "ouvre youtube music", "youtube music", "lance youtube music", +1 | browser |
| ouvrir_prime_video | Ouvrir Amazon Prime Video | "ouvre prime video", "va sur prime video", "lance prime video", +1 | browser |
| ouvrir_crunchyroll | Ouvrir Crunchyroll | "ouvre crunchyroll", "va sur crunchyroll", "lance crunchyroll", +1 | browser |
| ouvrir_github_web | Ouvrir GitHub | "ouvre github", "va sur github", "lance github", +1 | browser |
| ouvrir_vercel | Ouvrir Vercel | "ouvre vercel", "va sur vercel", "lance vercel" | browser |
| ouvrir_crates_io | Ouvrir crates.io (Rust packages) | "ouvre crates io", "va sur crates", "crates rust", +1 | browser |
| chercher_video_youtube | Rechercher sur YouTube | "cherche sur youtube {requete}", "youtube {requete}", "recherche youtube {requete}", +1 | browser |
| chercher_github | Rechercher sur GitHub | "cherche sur github {requete}", "github {requete}", "recherche github {requete}", +1 | browser |
| chercher_stackoverflow | Rechercher sur Stack Overflow | "cherche sur stackoverflow {requete}", "stackoverflow {requete}", "stack overflow {requete}" | browser |
| chercher_npm | Rechercher un package NPM | "cherche sur npm {requete}", "npm {requete}", "recherche npm {requete}", +1 | browser |
| chercher_pypi | Rechercher un package PyPI | "cherche sur pypi {requete}", "pypi {requete}", "recherche pypi {requete}", +1 | browser |

### Fichiers & Documents (32 commandes)

| Commande | Description | Triggers | Type |
|----------|------------|----------|------|
| ouvrir_documents | Ouvrir le dossier Documents | "ouvre mes documents", "ouvrir mes documents", "ouvre documents", +3 | powershell |
| ouvrir_bureau | Ouvrir le dossier Bureau | "ouvre le bureau", "ouvrir le bureau", "affiche le bureau", +4 | powershell |
| ouvrir_dossier | Ouvrir un dossier specifique | "ouvre le dossier {dossier}", "ouvrir le dossier {dossier}", "va dans {dossier}", +1 | powershell |
| ouvrir_telechargements | Ouvrir Telechargements | "ouvre les telechargements", "ouvre mes telechargements", "ouvrir telechargements", +1 | powershell |
| ouvrir_images | Ouvrir le dossier Images | "ouvre mes images", "ouvre mes photos", "ouvre le dossier images", +2 | powershell |
| ouvrir_musique | Ouvrir le dossier Musique | "ouvre ma musique", "ouvre le dossier musique", "va dans ma musique" | powershell |
| ouvrir_projets | Ouvrir le dossier projets | "ouvre mes projets", "va dans les projets", "ouvre le dossier turbo", +2 | powershell |
| ouvrir_explorateur | Ouvrir l'explorateur de fichiers | "ouvre l'explorateur", "ouvre l'explorateur de fichiers", "explorateur de fichiers", +1 | hotkey |
| lister_dossier | Lister le contenu d'un dossier | "que contient {dossier}", "liste le dossier {dossier}", "contenu du dossier {dossier}", +1 | jarvis_tool |
| creer_dossier | Creer un nouveau dossier | "cree un dossier {nom}", "nouveau dossier {nom}", "cree le dossier {nom}", +4 | jarvis_tool |
| chercher_fichier | Chercher un fichier | "cherche le fichier {nom}", "trouve le fichier {nom}", "ou est le fichier {nom}", +1 | jarvis_tool |
| ouvrir_recents | Ouvrir les fichiers recents | "fichiers recents", "ouvre les recents", "derniers fichiers", +1 | powershell |
| ouvrir_temp | Ouvrir le dossier temporaire | "ouvre le dossier temp", "fichiers temporaires", "dossier temp", +1 | powershell |
| ouvrir_appdata | Ouvrir le dossier AppData | "ouvre appdata", "dossier appdata", "ouvre app data", +1 | powershell |
| espace_dossier | Taille d'un dossier | "taille du dossier {dossier}", "combien pese {dossier}", "espace utilise par {dossier}", +1 | powershell |
| nombre_fichiers | Compter les fichiers dans un dossier | "combien de fichiers dans {dossier}", "nombre de fichiers {dossier}", "compte les fichiers dans {dossier}" | powershell |
| compresser_dossier | Compresser un dossier en ZIP | "compresse {dossier}", "zip {dossier}", "archive {dossier}", +2 | powershell |
| decompresser_zip | Decompresser un fichier ZIP | "decompresse {fichier}", "unzip {fichier}", "extrais {fichier}", +2 | powershell |
| hash_fichier | Calculer le hash SHA256 d'un fichier | "hash de {fichier}", "sha256 de {fichier}", "checksum de {fichier}", +2 | powershell |
| chercher_contenu | Chercher du texte dans les fichiers | "cherche {texte} dans les fichiers", "grep {texte}", "trouve {texte} dans les fichiers", +1 | powershell |
| derniers_fichiers | Derniers fichiers modifies | "derniers fichiers modifies", "fichiers recents", "quoi de nouveau", +2 | powershell |
| doublons_fichiers | Trouver les fichiers en double | "fichiers en double", "doublons", "trouve les doublons", +2 | powershell |
| gros_fichiers | Trouver les plus gros fichiers | "plus gros fichiers", "fichiers les plus lourds", "gros fichiers", +2 | powershell |
| fichiers_type | Lister les fichiers d'un type | "fichiers {ext}", "tous les {ext}", "liste les {ext}", +2 | powershell |
| renommer_masse | Renommer des fichiers en masse | "renomme les fichiers {ancien} en {nouveau}", "remplace {ancien} par {nouveau} dans les noms" | powershell |
| dossiers_vides | Trouver les dossiers vides | "dossiers vides", "repertoires vides", "trouve les dossiers vides", +1 | powershell |
| proprietes_fichier | Proprietes detaillees d'un fichier | "proprietes de {fichier}", "details de {fichier}", "info sur {fichier}", +2 | powershell |
| copier_fichier | Copier un fichier vers un dossier | "copie {source} dans {destination}", "copie {source} vers {destination}", "duplique {source} dans {destination}" | powershell |
| deplacer_fichier | Deplacer un fichier | "deplace {source} dans {destination}", "deplace {source} vers {destination}", "bouge {source} dans {destination}" | powershell |
| explorer_nouvel_onglet | Nouvel onglet dans l'Explorateur | "nouvel onglet explorateur", "onglet explorateur", "new tab explorer", +1 | powershell |
| dossier_captures | Ouvrir le dossier captures d'ecran | "dossier captures", "ouvre les captures", "dossier screenshots", +2 | powershell |
| taille_dossiers_bureau | Taille de chaque dossier dans F:\BUREAU | "taille des projets", "poids des dossiers bureau", "combien pese chaque projet", +1 | powershell |

### Applications (23 commandes)

| Commande | Description | Triggers | Type |
|----------|------------|----------|------|
| ouvrir_vscode | Ouvrir Visual Studio Code | "ouvre vscode", "ouvrir vscode", "lance vscode", +8 | app_open |
| ouvrir_terminal | Ouvrir un terminal | "ouvre le terminal", "ouvrir le terminal", "lance powershell", +5 | app_open |
| ouvrir_lmstudio | Ouvrir LM Studio | "ouvre lm studio", "lance lm studio", "demarre lm studio", +2 | app_open |
| ouvrir_discord | Ouvrir Discord | "ouvre discord", "lance discord", "va sur discord", +2 | app_open |
| ouvrir_spotify | Ouvrir Spotify | "ouvre spotify", "lance spotify", "mets spotify", +2 | app_open |
| ouvrir_task_manager | Ouvrir le gestionnaire de taches | "ouvre le gestionnaire de taches", "task manager", "gestionnaire de taches", +3 | app_open |
| ouvrir_notepad | Ouvrir Notepad | "ouvre notepad", "ouvre bloc notes", "ouvre le bloc notes", +2 | app_open |
| ouvrir_calculatrice | Ouvrir la calculatrice | "ouvre la calculatrice", "lance la calculatrice", "calculatrice", +1 | app_open |
| fermer_app | Fermer une application | "ferme {app}", "fermer {app}", "quitte {app}", +2 | jarvis_tool |
| ouvrir_app | Ouvrir une application par nom | "ouvre {app}", "ouvrir {app}", "lance {app}", +1 | app_open |
| ouvrir_paint | Ouvrir Paint | "ouvre paint", "lance paint", "ouvrir paint", +1 | app_open |
| ouvrir_wordpad | Ouvrir WordPad | "ouvre wordpad", "lance wordpad", "ouvrir wordpad" | app_open |
| ouvrir_snipping | Ouvrir l'Outil Capture | "ouvre l'outil capture", "lance l'outil capture", "outil de capture", +2 | app_open |
| ouvrir_magnifier | Ouvrir la loupe Windows | "ouvre la loupe windows", "loupe windows", "loupe ecran" | hotkey |
| fermer_loupe | Fermer la loupe Windows | "ferme la loupe", "desactive la loupe", "arrete la loupe" | hotkey |
| ouvrir_obs | Ouvrir OBS Studio | "ouvre obs", "lance obs", "obs studio", +2 | app_open |
| ouvrir_vlc | Ouvrir VLC Media Player | "ouvre vlc", "lance vlc", "ouvrir vlc", +1 | app_open |
| ouvrir_7zip | Ouvrir 7-Zip | "ouvre 7zip", "lance 7zip", "ouvrir 7zip", +2 | app_open |
| store_ouvrir | Ouvrir le Microsoft Store | "ouvre le store", "microsoft store", "ouvre le magasin", +2 | powershell |
| store_updates | Verifier les mises a jour du Store | "mises a jour store", "store updates", "update les apps", +2 | powershell |
| ouvrir_phone_link | Ouvrir Phone Link (liaison telephone) | "ouvre phone link", "liaison telephone", "phone link", +2 | powershell |
| terminal_settings | Ouvrir les parametres Windows Terminal | "parametres du terminal", "reglages terminal", "settings terminal", +1 | powershell |
| copilot_lancer | Lancer Windows Copilot | "lance copilot", "ouvre copilot", "copilot", +2 | hotkey |

### Controle Media (7 commandes)

| Commande | Description | Triggers | Type |
|----------|------------|----------|------|
| media_play_pause | Play/Pause media | "play", "pause", "mets pause", +11 | hotkey |
| media_next | Piste suivante | "suivant", "piste suivante", "chanson suivante", +6 | hotkey |
| media_previous | Piste precedente | "precedent", "piste precedente", "chanson precedente", +9 | hotkey |
| volume_haut | Augmenter le volume | "monte le volume", "augmente le volume", "volume plus fort", +4 | hotkey |
| volume_bas | Baisser le volume | "baisse le volume", "diminue le volume", "volume moins fort", +4 | hotkey |
| muet | Couper/activer le son | "coupe le son", "mute", "silence", +4 | hotkey |
| volume_precis | Mettre le volume a un niveau precis | "mets le volume a {niveau}", "volume a {niveau}", "regle le volume a {niveau}", +1 | powershell |

### Fenetres Windows (13 commandes)

| Commande | Description | Triggers | Type |
|----------|------------|----------|------|
| minimiser_tout | Minimiser toutes les fenetres | "minimise tout", "montre le bureau", "affiche le bureau", +3 | hotkey |
| alt_tab | Basculer entre les fenetres | "change de fenetre", "fenetre suivante", "bascule", +3 | hotkey |
| fermer_fenetre | Fermer la fenetre active | "ferme la fenetre", "ferme ca", "ferme cette fenetre", +2 | hotkey |
| maximiser_fenetre | Maximiser la fenetre active | "maximise", "plein ecran", "maximiser la fenetre", +2 | hotkey |
| minimiser_fenetre | Minimiser la fenetre active | "minimise", "reduis la fenetre", "minimiser", +2 | hotkey |
| fenetre_gauche | Fenetre a gauche | "fenetre a gauche", "mets a gauche", "snap gauche", +2 | hotkey |
| fenetre_droite | Fenetre a droite | "fenetre a droite", "mets a droite", "snap droite", +2 | hotkey |
| focus_fenetre | Mettre le focus sur une fenetre | "focus sur {titre}", "va sur la fenetre {titre}", "montre {titre}", +1 | jarvis_tool |
| liste_fenetres | Lister les fenetres ouvertes | "quelles fenetres sont ouvertes", "liste les fenetres", "montre les fenetres", +1 | jarvis_tool |
| fenetre_haut_gauche | Fenetre en haut a gauche | "fenetre en haut a gauche", "snap haut gauche", "coin haut gauche", +1 | powershell |
| fenetre_haut_droite | Fenetre en haut a droite | "fenetre en haut a droite", "snap haut droite", "coin haut droite", +1 | powershell |
| fenetre_bas_gauche | Fenetre en bas a gauche | "fenetre en bas a gauche", "snap bas gauche", "coin bas gauche", +1 | powershell |
| fenetre_bas_droite | Fenetre en bas a droite | "fenetre en bas a droite", "snap bas droite", "coin bas droite", +1 | powershell |

### Presse-papier & Saisie (13 commandes)

| Commande | Description | Triggers | Type |
|----------|------------|----------|------|
| copier | Copier la selection | "copie", "copier", "copy", +2 | hotkey |
| coller | Coller le contenu | "colle", "coller", "paste", +2 | hotkey |
| couper | Couper la selection | "coupe", "couper", "cut", +1 | hotkey |
| tout_selectionner | Selectionner tout | "selectionne tout", "tout selectionner", "select all", +2 | hotkey |
| annuler | Annuler la derniere action | "annule", "annuler", "undo", +2 | hotkey |
| ecrire_texte | Ecrire du texte au clavier | "ecris {texte}", "tape {texte}", "saisis {texte}", +2 | jarvis_tool |
| sauvegarder | Sauvegarder le fichier actif | "sauvegarde", "enregistre", "save", +3 | hotkey |
| refaire | Refaire la derniere action annulee | "refais", "redo", "refaire", +3 | hotkey |
| recherche_page | Rechercher dans la page | "recherche dans la page", "cherche dans la page", "find", +2 | hotkey |
| lire_presse_papier | Lire le contenu du presse-papier | "lis le presse-papier", "qu'est-ce qui est copie", "contenu du presse-papier", +1 | jarvis_tool |
| historique_clipboard | Historique du presse-papier | "historique du presse-papier", "clipboard history", "historique presse-papier", +1 | hotkey |
| clipboard_historique | Ouvrir l'historique du presse-papier | "historique presse papier", "clipboard history", "ouvre l'historique clipboard", +2 | hotkey |
| coller_sans_format | Coller sans mise en forme | "colle sans format", "coller sans mise en forme", "colle en texte brut", +1 | hotkey |

### Systeme Windows (292 commandes)

| Commande | Description | Triggers | Type |
|----------|------------|----------|------|
| verrouiller | Verrouiller le PC | "verrouille le pc", "verrouille l'ecran", "lock", +2 | powershell |
| eteindre | Eteindre le PC | "eteins le pc", "eteindre le pc", "arrete le pc", +6 | powershell |
| redemarrer | Redemarrer le PC | "redemarre le pc", "redemarrer le pc", "reboot", +6 | powershell |
| veille | Mettre en veille | "mets en veille", "veille", "sleep", +3 | powershell |
| capture_ecran | Capture d'ecran | "capture ecran", "screenshot", "prends une capture", +3 | hotkey |
| info_systeme | Infos systeme | "info systeme", "infos systeme", "statut systeme", +5 | jarvis_tool |
| info_gpu | Infos GPU | "info gpu", "infos gpu", "statut gpu", +4 | jarvis_tool |
| info_reseau | Infos reseau | "info reseau", "infos reseau", "statut reseau", +3 | jarvis_tool |
| processus | Lister les processus | "liste les processus", "montre les processus", "quels processus tournent", +1 | jarvis_tool |
| kill_process | Tuer un processus | "tue le processus {nom}", "kill {nom}", "ferme le processus {nom}", +1 | jarvis_tool |
| wifi_scan | Scanner les reseaux Wi-Fi | "scan wifi", "wifi scan", "reseaux wifi", +6 | jarvis_tool |
| ping_host | Ping un hote | "ping {host}", "teste la connexion a {host}", "verifie {host}", +1 | jarvis_tool |
| vider_corbeille | Vider la corbeille | "vide la corbeille", "nettoie la corbeille", "vider la corbeille", +1 | powershell |
| mode_nuit | Activer/desactiver le mode nuit | "mode nuit", "lumiere bleue", "filtre bleu", +3 | hotkey |
| ouvrir_run | Ouvrir la boite Executer | "ouvre executer", "boite de dialogue executer", "run", +2 | hotkey |
| recherche_windows | Recherche Windows | "recherche windows", "cherche sur le pc", "recherche sur le pc", +2 | hotkey |
| centre_notifications | Ouvrir le centre de notifications | "ouvre les notifications", "notifications", "centre de notifications", +1 | hotkey |
| ouvrir_widgets | Ouvrir les widgets | "ouvre les widgets", "widgets", "affiche les widgets", +1 | hotkey |
| ouvrir_emojis | Ouvrir le panneau emojis | "ouvre les emojis", "emojis", "panneau emojis", +1 | hotkey |
| projeter_ecran | Projeter l'ecran | "projette l'ecran", "duplique l'ecran", "mode ecran", +2 | hotkey |
| vue_taches | Vue des taches / bureaux virtuels | "vue des taches", "bureaux virtuels", "task view", +2 | hotkey |
| bureau_suivant | Passer au bureau virtuel suivant | "bureau suivant", "prochain bureau", "next desktop", +1 | hotkey |
| bureau_precedent | Passer au bureau virtuel precedent | "bureau precedent", "bureau virtuel precedent", "previous desktop", +1 | hotkey |
| ouvrir_parametres | Ouvrir les parametres Windows | "ouvre les parametres", "parametres", "reglages", +3 | ms_settings |
| param_wifi | Parametres Wi-Fi | "parametres wifi", "reglages wifi", "ouvre les parametres wifi", +1 | ms_settings |
| param_bluetooth | Parametres Bluetooth | "parametres bluetooth", "reglages bluetooth", "ouvre les parametres bluetooth", +1 | ms_settings |
| param_affichage | Parametres d'affichage | "parametres affichage", "reglages ecran", "parametres ecran", +1 | ms_settings |
| param_son | Parametres son | "parametres son", "reglages audio", "parametres audio", +1 | ms_settings |
| param_stockage | Espace disque et stockage | "espace disque", "stockage", "parametres stockage", +2 | ms_settings |
| param_mises_a_jour | Mises a jour Windows | "mises a jour", "windows update", "mise a jour", +2 | ms_settings |
| param_alimentation | Parametres d'alimentation | "parametres alimentation", "economie energie", "reglages alimentation", +1 | ms_settings |
| bluetooth_on | Activer le Bluetooth | "active le bluetooth", "allume bluetooth", "bluetooth on", +2 | powershell |
| bluetooth_off | Desactiver le Bluetooth | "desactive le bluetooth", "coupe bluetooth", "bluetooth off", +2 | powershell |
| luminosite_haut | Augmenter la luminosite | "augmente la luminosite", "plus lumineux", "luminosite plus", +1 | powershell |
| luminosite_bas | Baisser la luminosite | "baisse la luminosite", "moins lumineux", "luminosite moins", +1 | powershell |
| lister_services | Lister les services Windows | "liste les services", "services windows", "quels services", +1 | jarvis_tool |
| demarrer_service | Demarrer un service Windows | "demarre le service {nom}", "start service {nom}", "lance le service {nom}" | jarvis_tool |
| arreter_service | Arreter un service Windows | "arrete le service {nom}", "stop service {nom}", "stoppe le service {nom}" | jarvis_tool |
| resolution_ecran | Resolution de l'ecran | "resolution ecran", "quelle resolution", "resolution de l'ecran", +1 | jarvis_tool |
| taches_planifiees | Taches planifiees Windows | "taches planifiees", "taches automatiques", "scheduled tasks", +1 | jarvis_tool |
| mode_avion_on | Activer le mode avion | "active le mode avion", "mode avion", "mode avion on", +2 | ms_settings |
| micro_mute | Couper le microphone | "coupe le micro", "mute le micro", "micro off", +2 | powershell |
| micro_unmute | Reactiver le microphone | "reactive le micro", "unmute micro", "micro on", +2 | powershell |
| param_camera | Parametres camera | "parametres camera", "reglages camera", "config camera", +1 | ms_settings |
| nouveau_bureau | Creer un nouveau bureau virtuel | "nouveau bureau", "cree un bureau", "ajoute un bureau", +2 | hotkey |
| fermer_bureau | Fermer le bureau virtuel actif | "ferme le bureau", "ferme ce bureau", "supprime le bureau", +2 | hotkey |
| zoom_avant | Zoomer | "zoom avant", "zoom plus", "agrandis", +2 | hotkey |
| zoom_arriere | Dezoomer | "zoom arriere", "zoom moins", "retrecis", +2 | hotkey |
| zoom_reset | Reinitialiser le zoom | "zoom normal", "zoom reset", "taille normale", +1 | hotkey |
| imprimer | Imprimer | "imprime", "imprimer", "print", +2 | hotkey |
| renommer | Renommer le fichier selectionne | "renomme", "renommer", "rename", +2 | hotkey |
| supprimer | Supprimer le fichier/element selectionne | "supprime", "supprimer", "delete", +7 | hotkey |
| proprietes | Proprietes du fichier selectionne | "proprietes", "proprietes du fichier", "infos fichier", +1 | hotkey |
| actualiser | Actualiser la page ou le dossier | "actualise", "rafraichis", "refresh", +3 | hotkey |
| verrouiller_rapide | Verrouiller le PC rapidement | "verrouille", "lock", "verrouille vite", +1 | hotkey |
| loupe | Activer la loupe / zoom accessibilite | "active la loupe", "loupe", "magnifier", +2 | hotkey |
| loupe_off | Desactiver la loupe | "desactive la loupe", "ferme la loupe", "loupe off", +1 | hotkey |
| narrateur | Activer/desactiver le narrateur | "active le narrateur", "narrateur", "narrator", +2 | hotkey |
| clavier_visuel | Ouvrir le clavier visuel | "clavier visuel", "ouvre le clavier", "clavier ecran", +2 | powershell |
| dictee | Activer la dictee vocale Windows | "dictee", "dictee vocale", "lance la dictee", +3 | hotkey |
| contraste_eleve | Activer le mode contraste eleve | "contraste eleve", "high contrast", "mode contraste", +1 | hotkey |
| param_accessibilite | Parametres d'accessibilite | "parametres accessibilite", "reglages accessibilite", "accessibilite", +1 | ms_settings |
| enregistrer_ecran | Enregistrer l'ecran (Xbox Game Bar) | "enregistre l'ecran", "lance l'enregistrement", "record", +3 | hotkey |
| game_bar | Ouvrir la Xbox Game Bar | "ouvre la game bar", "game bar", "xbox game bar", +1 | hotkey |
| snap_layout | Ouvrir les dispositions Snap | "snap layout", "disposition fenetre", "snap", +2 | hotkey |
| plan_performance | Activer le mode performances | "mode performance", "performances maximales", "haute performance", +2 | powershell |
| plan_equilibre | Activer le mode equilibre | "mode equilibre", "plan equilibre", "balanced", +2 | powershell |
| plan_economie | Activer le mode economie d'energie | "mode economie", "economie d'energie", "power saver", +2 | powershell |
| ipconfig | Afficher la configuration IP | "montre l'ip", "quelle est mon adresse ip", "ipconfig", +2 | jarvis_tool |
| vider_dns | Vider le cache DNS | "vide le cache dns", "flush dns", "nettoie le dns", +2 | powershell |
| param_vpn | Parametres VPN | "parametres vpn", "reglages vpn", "config vpn", +2 | ms_settings |
| param_proxy | Parametres proxy | "parametres proxy", "reglages proxy", "config proxy", +1 | ms_settings |
| etendre_ecran | Etendre l'affichage sur un second ecran | "etends l'ecran", "double ecran", "ecran etendu", +2 | powershell |
| dupliquer_ecran | Dupliquer l'affichage | "duplique l'ecran", "meme image", "ecran duplique", +2 | powershell |
| ecran_principal_seul | Afficher uniquement sur l'ecran principal | "ecran principal seulement", "un seul ecran", "desactive le second ecran", +1 | powershell |
| ecran_secondaire_seul | Afficher uniquement sur le second ecran | "ecran secondaire seulement", "second ecran uniquement", "affiche sur l'autre ecran", +1 | powershell |
| focus_assist_on | Activer l'aide a la concentration (ne pas deranger) | "ne pas deranger", "focus assist", "mode silencieux", +2 | powershell |
| focus_assist_off | Desactiver l'aide a la concentration | "desactive ne pas deranger", "reactive les notifications", "focus assist off", +1 | powershell |
| taskbar_hide | Masquer la barre des taches | "cache la barre des taches", "masque la taskbar", "barre des taches invisible", +1 | powershell |
| taskbar_show | Afficher la barre des taches | "montre la barre des taches", "affiche la taskbar", "barre des taches visible", +1 | powershell |
| night_light_on | Activer l'eclairage nocturne | "active la lumiere nocturne", "night light on", "eclairage nocturne", +2 | powershell |
| night_light_off | Desactiver l'eclairage nocturne | "desactive la lumiere nocturne", "night light off", "lumiere normale", +1 | powershell |
| info_disques | Afficher l'espace disque | "espace disque", "info disques", "combien de place", +2 | powershell |
| vider_temp | Vider les fichiers temporaires | "vide les fichiers temporaires", "nettoie les temp", "supprime les temp", +1 | powershell |
| ouvrir_alarmes | Ouvrir l'application Horloge/Alarmes | "ouvre les alarmes", "alarme", "minuteur", +3 | app_open |
| historique_activite | Ouvrir l'historique d'activite Windows | "historique activite", "timeline", "activites recentes", +2 | ms_settings |
| param_clavier | Parametres clavier | "parametres clavier", "reglages clavier", "config clavier", +2 | ms_settings |
| param_souris | Parametres souris | "parametres souris", "reglages souris", "config souris", +2 | ms_settings |
| param_batterie | Parametres batterie | "parametres batterie", "etat batterie", "batterie", +2 | ms_settings |
| param_comptes | Parametres des comptes utilisateur | "parametres comptes", "comptes utilisateur", "mon compte", +1 | ms_settings |
| param_heure | Parametres date et heure | "parametres heure", "reglages heure", "date et heure", +2 | ms_settings |
| param_langue | Parametres de langue | "parametres langue", "changer la langue", "langue windows", +1 | ms_settings |
| windows_security | Ouvrir Windows Security | "ouvre la securite", "securite windows", "windows security", +3 | app_open |
| pare_feu | Parametres du pare-feu | "parametres pare-feu", "firewall", "ouvre le pare-feu", +2 | ms_settings |
| partage_proximite | Parametres de partage a proximite | "partage a proximite", "nearby sharing", "partage rapide", +2 | ms_settings |
| hotspot | Activer le point d'acces mobile | "point d'acces", "hotspot", "partage de connexion", +2 | ms_settings |
| defrag_disque | Optimiser les disques (defragmentation) | "defragmente", "optimise les disques", "defragmentation", +2 | powershell |
| gestion_disques | Ouvrir le gestionnaire de disques | "gestionnaire de disques", "gestion des disques", "disk manager", +2 | powershell |
| variables_env | Ouvrir les variables d'environnement | "variables d'environnement", "variables env", "env variables", +2 | powershell |
| evenements_windows | Ouvrir l'observateur d'evenements | "observateur d'evenements", "event viewer", "journaux windows", +2 | powershell |
| moniteur_ressources | Ouvrir le moniteur de ressources | "moniteur de ressources", "resource monitor", "ressources systeme", +2 | powershell |
| info_systeme_detaille | Ouvrir les informations systeme detaillees | "informations systeme detaillees", "msinfo", "infos systeme avancees", +2 | powershell |
| nettoyage_disque | Ouvrir le nettoyage de disque Windows | "nettoyage de disque", "disk cleanup", "nettoie le disque", +2 | powershell |
| gestionnaire_peripheriques | Ouvrir le gestionnaire de peripheriques | "gestionnaire de peripheriques", "device manager", "mes peripheriques", +2 | powershell |
| connexions_reseau | Ouvrir les connexions reseau | "connexions reseau", "adaptateurs reseau", "network connections", +2 | powershell |
| programmes_installees | Ouvrir programmes et fonctionnalites | "programmes installes", "applications installees", "liste des programmes", +1 | ms_settings |
| demarrage_apps | Gerer les applications au demarrage | "applications demarrage", "programmes au demarrage", "gere le demarrage", +2 | ms_settings |
| param_confidentialite | Parametres de confidentialite | "parametres confidentialite", "privacy", "confidentialite", +2 | ms_settings |
| param_reseau_avance | Parametres reseau avances | "parametres reseau avances", "reseau avance", "advanced network", +1 | ms_settings |
| partager_ecran | Partager l'ecran via Miracast | "partage l'ecran", "miracast", "cast", +3 | hotkey |
| param_imprimantes | Parametres imprimantes et scanners | "parametres imprimantes", "imprimante", "ouvre les imprimantes", +2 | ms_settings |
| param_fond_ecran | Personnaliser le fond d'ecran | "fond d'ecran", "change le fond", "wallpaper", +2 | ms_settings |
| param_couleurs | Personnaliser les couleurs Windows | "couleurs windows", "couleur d'accent", "theme couleur", +4 | ms_settings |
| param_ecran_veille | Parametres ecran de verrouillage | "ecran de veille", "ecran de verrouillage", "lock screen", +1 | ms_settings |
| param_polices | Gerer les polices installees | "polices", "fonts", "gere les polices", +2 | ms_settings |
| param_themes | Gerer les themes Windows | "themes windows", "change le theme", "personnalise le theme", +2 | ms_settings |
| mode_sombre | Activer le mode sombre Windows | "active le mode sombre", "dark mode on", "theme sombre", +2 | powershell |
| mode_clair | Activer le mode clair Windows | "active le mode clair", "light mode on", "theme clair", +2 | powershell |
| param_son_avance | Parametres audio avances | "parametres audio avances", "son avance", "mixer audio", +2 | ms_settings |
| param_hdr | Parametres HDR | "parametres hdr", "active le hdr", "hdr", +2 | ms_settings |
| ouvrir_regedit | Ouvrir l'editeur de registre | "ouvre le registre", "regedit", "editeur de registre", +1 | powershell |
| ouvrir_mmc | Ouvrir la console de gestion (MMC) | "console de gestion", "mmc", "ouvre mmc", +1 | powershell |
| ouvrir_politique_groupe | Ouvrir l'editeur de strategie de groupe | "politique de groupe", "group policy", "gpedit", +2 | powershell |
| taux_rafraichissement | Parametres taux de rafraichissement ecran | "taux de rafraichissement", "hertz ecran", "frequence ecran", +2 | ms_settings |
| param_notifications_avance | Parametres notifications avances | "parametres notifications avances", "gere les notifications", "quelles apps notifient", +1 | ms_settings |
| param_multitache | Parametres multitache Windows | "parametres multitache", "multitasking", "reglages multitache", +2 | ms_settings |
| apps_par_defaut | Gerer les applications par defaut | "applications par defaut", "apps par defaut", "ouvre avec", +2 | ms_settings |
| param_stockage_avance | Gestion du stockage et assistant | "assistant stockage", "nettoyage automatique", "stockage intelligent", +2 | ms_settings |
| sauvegarder_windows | Parametres de sauvegarde Windows | "sauvegarde windows", "backup windows", "parametres backup", +2 | ms_settings |
| restauration_systeme | Ouvrir la restauration du systeme | "restauration systeme", "point de restauration", "system restore", +2 | powershell |
| a_propos_pc | Informations sur le PC (A propos) | "a propos du pc", "about pc", "nom du pc", +3 | ms_settings |
| param_ethernet | Parametres Ethernet | "parametres ethernet", "cable reseau", "connexion filaire", +2 | ms_settings |
| param_data_usage | Utilisation des donnees reseau | "utilisation donnees", "data usage", "consommation reseau", +2 | ms_settings |
| tracert | Tracer la route vers un hote | "trace la route vers {host}", "traceroute {host}", "tracert {host}", +1 | powershell |
| netstat | Afficher les connexions reseau actives | "connexions actives", "netstat", "ports ouverts", +2 | powershell |
| uptime | Temps de fonctionnement du PC | "uptime", "depuis quand le pc tourne", "temps de fonctionnement", +2 | powershell |
| temperature_cpu | Temperature du processeur | "temperature cpu", "temperature processeur", "cpu temperature", +2 | powershell |
| liste_utilisateurs | Lister les utilisateurs du PC | "liste les utilisateurs", "quels utilisateurs", "comptes locaux", +2 | powershell |
| adresse_mac | Afficher les adresses MAC | "adresse mac", "mac address", "adresses mac", +1 | powershell |
| vitesse_reseau | Tester la vitesse de la carte reseau | "vitesse reseau", "speed test", "debit reseau", +2 | powershell |
| param_optionnel | Gerer les fonctionnalites optionnelles Windows | "fonctionnalites optionnelles", "optional features", "features windows", +2 | ms_settings |
| ouvrir_sandbox | Ouvrir Windows Sandbox | "ouvre la sandbox", "sandbox", "windows sandbox", +2 | powershell |
| verifier_fichiers | Verifier l'integrite des fichiers systeme | "verifie les fichiers systeme", "sfc scan", "scan integrite", +2 | powershell |
| wifi_connecter | Se connecter a un reseau Wi-Fi | "connecte moi au wifi {ssid}", "connecte au wifi {ssid}", "rejoins le wifi {ssid}", +1 | powershell |
| wifi_deconnecter | Se deconnecter du Wi-Fi | "deconnecte le wifi", "deconnecte du wifi", "wifi off", +2 | powershell |
| wifi_profils | Lister les profils Wi-Fi sauvegardes | "profils wifi", "wifi sauvegardes", "reseaux memorises", +2 | powershell |
| clipboard_vider | Vider le presse-papier | "vide le presse-papier", "efface le clipboard", "nettoie le presse-papier", +1 | powershell |
| clipboard_compter | Compter les caracteres du presse-papier | "combien de caracteres dans le presse-papier", "taille du presse-papier", "longueur du clipboard" | powershell |
| recherche_everywhere | Rechercher partout sur le PC | "recherche partout {terme}", "cherche partout {terme}", "trouve {terme} sur le pc", +1 | powershell |
| tache_planifier | Creer une tache planifiee | "planifie une tache {nom}", "cree une tache planifiee {nom}", "programme {nom}", +1 | powershell |
| variables_utilisateur | Afficher les variables d'environnement utilisateur | "variables utilisateur", "mes variables", "env utilisateur", +1 | powershell |
| chemin_path | Afficher le PATH systeme | "montre le path", "affiche le path", "variable path", +2 | powershell |
| deconnexion_windows | Deconnexion de la session Windows | "deconnecte moi", "deconnexion", "log out", +2 | powershell |
| hibernation | Mettre en hibernation | "hiberne", "hibernation", "mise en hibernation", +2 | powershell |
| planifier_arret | Planifier un arret dans X minutes | "eteins dans {minutes} minutes", "arret dans {minutes} minutes", "programme l'arret dans {minutes}", +6 | powershell |
| annuler_arret | Annuler un arret programme | "annule l'arret", "annuler shutdown", "cancel shutdown", +2 | powershell |
| heure_actuelle | Donner l'heure actuelle | "quelle heure est-il", "quelle heure", "l'heure", +6 | powershell |
| date_actuelle | Donner la date actuelle | "quelle date", "quel jour on est", "on est quel jour", +3 | powershell |
| ecran_externe_etendre | Etendre sur ecran externe | "etends l'ecran", "ecran etendu", "mode etendu", +2 | powershell |
| ecran_duplique | Dupliquer l'ecran | "duplique l'ecran", "ecran duplique", "mode duplique", +2 | powershell |
| ecran_interne_seul | Ecran interne uniquement | "ecran principal seulement", "ecran interne seul", "desactive l'ecran externe", +1 | powershell |
| ecran_externe_seul | Ecran externe uniquement | "ecran externe seulement", "ecran externe seul", "desactive l'ecran principal", +1 | powershell |
| ram_usage | Utilisation de la RAM | "utilisation ram", "combien de ram", "memoire utilisee", +2 | powershell |
| cpu_usage | Utilisation du processeur | "utilisation cpu", "charge du processeur", "combien de cpu", +2 | powershell |
| cpu_info | Informations sur le processeur | "quel processeur", "info cpu", "nom du processeur", +2 | powershell |
| ram_info | Informations detaillees sur la RAM | "info ram", "details ram", "combien de barrettes", +2 | powershell |
| batterie_niveau | Niveau de batterie | "niveau de batterie", "combien de batterie", "batterie restante", +2 | powershell |
| disque_sante | Sante des disques (SMART) | "sante des disques", "etat des disques", "smart disque", +2 | powershell |
| carte_mere | Informations carte mere | "info carte mere", "quelle carte mere", "modele carte mere", +2 | powershell |
| bios_info | Informations BIOS | "info bios", "version bios", "quel bios", +2 | powershell |
| top_ram | Top 10 processus par RAM | "quoi consomme la ram", "top ram", "processus gourmands ram", +2 | powershell |
| top_cpu | Top 10 processus par CPU | "quoi consomme le cpu", "top cpu", "processus gourmands cpu", +2 | powershell |
| carte_graphique | Informations carte graphique | "quelle carte graphique", "info gpu detaille", "specs gpu", +2 | powershell |
| windows_version | Version exacte de Windows | "version de windows", "quelle version windows", "build windows", +2 | powershell |
| dns_changer_google | Changer DNS vers Google (8.8.8.8) | "mets le dns google", "change le dns en google", "dns google", +2 | powershell |
| dns_changer_cloudflare | Changer DNS vers Cloudflare (1.1.1.1) | "mets le dns cloudflare", "change le dns en cloudflare", "dns cloudflare", +2 | powershell |
| dns_reset | Remettre le DNS en automatique | "dns automatique", "reset le dns", "dns par defaut", +2 | powershell |
| ports_ouverts | Lister les ports ouverts | "ports ouverts", "quels ports sont ouverts", "liste les ports", +2 | powershell |
| ip_publique | Obtenir l'IP publique | "mon ip publique", "quelle est mon ip publique", "ip externe", +2 | powershell |
| partage_reseau | Lister les partages reseau | "partages reseau", "dossiers partages", "quels dossiers sont partages", +2 | powershell |
| connexions_actives | Connexions reseau actives | "connexions actives", "qui est connecte", "connexions etablies", +2 | powershell |
| vitesse_reseau | Vitesse de la carte reseau | "vitesse reseau", "debit carte reseau", "link speed", +2 | powershell |
| arp_table | Afficher la table ARP | "table arp", "arp", "appareils sur le reseau", +2 | powershell |
| test_port | Tester si un port est ouvert sur une machine | "teste le port {port} sur {host}", "port {port} ouvert sur {host}", "check port {port} {host}", +1 | powershell |
| route_table | Afficher la table de routage | "table de routage", "routes reseau", "route table", +2 | powershell |
| nslookup | Resolution DNS d'un domaine | "nslookup {domaine}", "resous {domaine}", "dns de {domaine}", +2 | powershell |
| certificat_ssl | Verifier le certificat SSL d'un site | "certificat ssl de {site}", "check ssl {site}", "verifie le ssl de {site}", +1 | powershell |
| voir_logs | Voir les logs systeme ou JARVIS | "les logs", "voir les logs", "montre les logs", +7 | powershell |
| ouvrir_widgets | Ouvrir le panneau Widgets Windows | "ouvre les widgets", "widgets windows", "panneau widgets", +2 | hotkey |
| partage_proximite_on | Activer le partage de proximite | "active le partage de proximite", "nearby sharing on", "partage proximite actif", +1 | powershell |
| screen_recording | Lancer l'enregistrement d'ecran (Game Bar) | "enregistre l'ecran", "screen recording", "capture video", +2 | hotkey |
| game_bar | Ouvrir la Game Bar Xbox | "ouvre la game bar", "game bar", "xbox game bar", +2 | hotkey |
| parametres_notifications | Ouvrir les parametres de notifications | "parametres notifications", "gere les notifications", "reglages notifications", +1 | powershell |
| parametres_apps_defaut | Ouvrir les apps par defaut | "apps par defaut", "applications par defaut", "change les apps par defaut", +1 | powershell |
| parametres_about | A propos de ce PC | "a propos du pc", "about this pc", "infos pc", +2 | powershell |
| verifier_sante_disque | Verifier la sante des disques | "sante des disques", "health check disque", "smart disque", +2 | powershell |
| vitesse_internet | Tester la vitesse internet | "test de vitesse", "speed test", "vitesse internet", +2 | powershell |
| historique_mises_a_jour | Voir l'historique des mises a jour Windows | "historique updates", "dernieres mises a jour", "updates windows recentes", +1 | powershell |
| taches_planifiees | Lister les taches planifiees | "taches planifiees", "scheduled tasks", "task scheduler", +2 | powershell |
| demarrage_apps | Voir les apps au demarrage | "apps au demarrage", "startup apps", "programmes au demarrage", +2 | powershell |
| certificats_ssl | Verifier un certificat SSL | "verifie le ssl de {site}", "certificat ssl {site}", "check ssl {site}", +1 | powershell |
| audio_sortie | Changer la sortie audio | "change la sortie audio", "sortie audio", "output audio", +2 | powershell |
| audio_entree | Configurer le microphone | "configure le micro", "entree audio", "input audio", +2 | powershell |
| volume_app | Mixer de volume par application | "mixer volume", "volume par application", "volume des apps", +2 | powershell |
| micro_mute_toggle | Couper/reactiver le micro | "coupe le micro", "mute le micro", "micro off", +3 | powershell |
| liste_imprimantes | Lister les imprimantes | "liste les imprimantes", "quelles imprimantes", "imprimantes disponibles", +2 | powershell |
| imprimante_defaut | Voir l'imprimante par defaut | "imprimante par defaut", "quelle imprimante", "default printer", +1 | powershell |
| param_imprimantes | Ouvrir les parametres imprimantes | "parametres imprimantes", "settings imprimantes", "gere les imprimantes", +1 | powershell |
| sandbox_ouvrir | Ouvrir Windows Sandbox | "ouvre la sandbox", "windows sandbox", "lance la sandbox", +2 | powershell |
| plan_alimentation_actif | Voir le plan d'alimentation actif | "quel plan alimentation", "power plan actif", "plan energie actif", +1 | powershell |
| batterie_rapport | Generer un rapport de batterie | "rapport batterie", "battery report", "sante de la batterie", +2 | powershell |
| ecran_timeout | Configurer la mise en veille ecran | "timeout ecran", "ecran en veille apres", "delai mise en veille ecran", +1 | powershell |
| detecter_ecrans | Detecter les ecrans connectes | "detecte les ecrans", "detect displays", "cherche les ecrans", +2 | powershell |
| param_affichage | Ouvrir les parametres d'affichage | "parametres affichage", "settings display", "reglages ecran", +1 | powershell |
| kill_process_nom | Tuer un processus par nom | "tue le processus {nom}", "kill {nom}", "ferme le processus {nom}", +2 | powershell |
| processus_details | Details d'un processus | "details du processus {nom}", "info processus {nom}", "combien consomme {nom}", +1 | powershell |
| diagnostic_reseau | Lancer un diagnostic reseau complet | "diagnostic reseau", "diagnostique le reseau", "probleme reseau", +2 | powershell |
| wifi_mot_de_passe | Afficher le mot de passe WiFi actuel | "mot de passe wifi", "password wifi", "cle wifi", +2 | powershell |
| ouvrir_evenements | Ouvrir l'observateur d'evenements | "observateur evenements", "event viewer", "journaux windows", +2 | powershell |
| ouvrir_services | Ouvrir les services Windows | "ouvre les services", "services windows", "gere les services", +1 | powershell |
| ouvrir_moniteur_perf | Ouvrir le moniteur de performances | "moniteur de performance", "performance monitor", "moniteur perf", +1 | powershell |
| ouvrir_fiabilite | Ouvrir le moniteur de fiabilite | "moniteur de fiabilite", "reliability monitor", "fiabilite windows", +1 | powershell |
| action_center | Ouvrir le centre de notifications | "centre de notifications", "notification center", "action center", +1 | hotkey |
| quick_settings | Ouvrir les parametres rapides | "parametres rapides", "quick settings", "raccourcis rapides", +1 | hotkey |
| search_windows | Ouvrir la recherche Windows | "recherche windows", "windows search", "ouvre la recherche", +1 | hotkey |
| hyper_v_manager | Ouvrir le gestionnaire Hyper-V | "ouvre hyper-v", "lance hyper-v", "gestionnaire hyper-v", +2 | powershell |
| storage_sense | Activer l'assistant de stockage | "active l'assistant de stockage", "storage sense", "nettoyage automatique", +1 | powershell |
| creer_point_restauration | Creer un point de restauration systeme | "cree un point de restauration", "point de restauration", "creer point de restauration", +1 | powershell |
| voir_hosts | Afficher le fichier hosts | "montre le fichier hosts", "affiche hosts", "ouvre hosts", +1 | powershell |
| dxdiag | Lancer le diagnostic DirectX | "lance dxdiag", "diagnostic directx", "dxdiag", +2 | powershell |
| memoire_diagnostic | Lancer le diagnostic memoire Windows | "diagnostic memoire", "teste la memoire", "test ram", +2 | powershell |
| reset_reseau | Reinitialiser la pile reseau | "reinitialise le reseau", "reset reseau", "reset network", +2 | powershell |
| bitlocker_status | Verifier le statut BitLocker | "statut bitlocker", "etat bitlocker", "bitlocker status", +1 | powershell |
| windows_update_pause | Mettre en pause les mises a jour Windows | "pause les mises a jour", "suspends les mises a jour", "mets en pause windows update", +1 | powershell |
| mode_developpeur | Activer/desactiver le mode developpeur | "active le mode developpeur", "mode developpeur", "developer mode", +1 | powershell |
| remote_desktop | Parametres Bureau a distance | "bureau a distance", "remote desktop", "ouvre remote desktop", +2 | powershell |
| credential_manager | Ouvrir le gestionnaire d'identifiants | "gestionnaire d'identifiants", "credential manager", "identifiants windows", +1 | powershell |
| certmgr | Ouvrir le gestionnaire de certificats | "gestionnaire de certificats", "certificats windows", "certmgr", +1 | powershell |
| chkdsk_check | Verifier les erreurs du disque | "verifie le disque", "check disk", "chkdsk", +2 | powershell |
| file_history | Parametres historique des fichiers | "historique des fichiers", "file history", "sauvegarde fichiers", +1 | powershell |
| troubleshoot_reseau | Lancer le depannage reseau | "depanne le reseau", "depannage reseau", "troubleshoot reseau", +1 | powershell |
| troubleshoot_audio | Lancer le depannage audio | "depanne le son", "depannage audio", "troubleshoot audio", +1 | powershell |
| troubleshoot_update | Lancer le depannage Windows Update | "depanne windows update", "depannage mises a jour", "troubleshoot update", +1 | powershell |
| power_options | Options d'alimentation avancees | "options d'alimentation", "power options", "alimentation avancee", +1 | powershell |
| copilot_parametres | Parametres de Copilot | "parametres copilot", "reglages copilot", "config copilot", +1 | ms_settings |
| cortana_desactiver | Desactiver Cortana | "desactive cortana", "coupe cortana", "cortana off", +2 | powershell |
| capture_fenetre | Capturer la fenetre active | "capture la fenetre", "screenshot fenetre", "capture fenetre active", +2 | hotkey |
| capture_retardee | Capture d'ecran avec delai | "capture retardee", "screenshot retarde", "capture dans 5 secondes", +2 | powershell |
| planificateur_ouvrir | Ouvrir le planificateur de taches | "planificateur de taches", "ouvre le planificateur", "task scheduler", +2 | powershell |
| creer_tache_planifiee | Creer une tache planifiee | "cree une tache planifiee", "nouvelle tache planifiee", "ajoute une tache planifiee", +1 | powershell |
| lister_usb | Lister les peripheriques USB connectes | "liste les usb", "peripheriques usb", "usb connectes", +2 | powershell |
| ejecter_usb | Ejecter un peripherique USB en securite | "ejecte l'usb", "ejecter usb", "retire l'usb", +2 | powershell |
| peripheriques_connectes | Lister tous les peripheriques connectes | "peripheriques connectes", "liste les peripheriques", "appareils connectes", +1 | powershell |
| lister_adaptateurs | Lister les adaptateurs reseau | "liste les adaptateurs reseau", "adaptateurs reseau", "interfaces reseau", +1 | powershell |
| desactiver_wifi_adaptateur | Desactiver l'adaptateur Wi-Fi | "desactive le wifi", "coupe l'adaptateur wifi", "wifi off adaptateur", +1 | powershell |
| activer_wifi_adaptateur | Activer l'adaptateur Wi-Fi | "active l'adaptateur wifi", "reactive le wifi", "wifi on adaptateur", +1 | powershell |
| firewall_status | Afficher le statut du pare-feu | "statut pare-feu", "statut firewall", "firewall status", +2 | powershell |
| firewall_regles | Lister les regles du pare-feu | "regles pare-feu", "regles firewall", "firewall rules", +1 | powershell |
| firewall_reset | Reinitialiser le pare-feu | "reinitialise le pare-feu", "reset firewall", "firewall reset", +1 | powershell |
| ajouter_langue | Ajouter une langue au systeme | "ajoute une langue", "installer une langue", "nouvelle langue", +1 | ms_settings |
| ajouter_clavier | Ajouter une disposition de clavier | "ajoute un clavier", "nouveau clavier", "ajouter disposition clavier", +1 | ms_settings |
| langues_installees | Lister les langues installees | "langues installees", "quelles langues", "liste des langues", +2 | powershell |
| synchroniser_heure | Synchroniser l'heure avec le serveur NTP | "synchronise l'heure", "sync heure", "mettre a l'heure", +2 | powershell |
| serveur_ntp | Afficher le serveur NTP configure | "serveur ntp", "quel serveur ntp", "serveur de temps", +2 | powershell |
| windows_hello | Parametres Windows Hello | "windows hello", "hello biometrique", "parametres hello", +2 | ms_settings |
| securite_comptes | Securite des comptes Windows | "securite des comptes", "securite compte", "protection compte", +2 | ms_settings |
| activation_windows | Verifier l'activation Windows | "activation windows", "windows active", "statut activation", +2 | powershell |
| recuperation_systeme | Options de recuperation systeme | "recuperation systeme", "options de recuperation", "recovery", +2 | ms_settings |
| gpu_temperatures | Temperatures GPU via nvidia-smi | "temperatures gpu", "gpu temperature", "chauffe les gpu", +2 | powershell |
| vram_usage | Utilisation VRAM de toutes les GPU | "utilisation vram", "vram utilisee", "combien de vram", +2 | powershell |
| disk_io | Activite I/O des disques | "activite des disques", "io disques", "disk io", +2 | powershell |
| network_io | Debit reseau en temps reel | "debit reseau", "trafic reseau", "network io", +2 | powershell |
| services_failed | Services Windows en echec | "services en echec", "services plantes", "services failed", +2 | powershell |
| event_errors | Dernières erreurs systeme (Event Log) | "erreurs systeme recentes", "derniers errors", "event log errors", +2 | powershell |
| boot_time | Temps de demarrage du dernier boot | "temps de demarrage", "boot time", "combien de temps au boot", +2 | powershell |
| nettoyer_prefetch | Nettoyer le dossier Prefetch | "nettoie prefetch", "vide prefetch", "clean prefetch", +1 | powershell |
| nettoyer_thumbnails | Nettoyer le cache des miniatures | "nettoie les miniatures", "vide le cache miniatures", "clean thumbnails", +1 | powershell |
| nettoyer_logs | Nettoyer les vieux logs | "nettoie les logs", "supprime les vieux logs", "clean logs", +2 | powershell |
| scan_ports_local | Scanner les ports ouverts localement | "scan mes ports", "scan ports local", "quels ports j'expose", +2 | powershell |
| connexions_suspectes | Verifier les connexions sortantes suspectes | "connexions suspectes", "qui se connecte dehors", "connexions sortantes", +1 | powershell |
| autorun_check | Verifier les programmes au demarrage | "quoi se lance au demarrage", "autorun check", "programmes auto start", +2 | powershell |
| defender_scan_rapide | Lancer un scan rapide Windows Defender | "scan antivirus", "lance un scan defender", "scan rapide", +2 | powershell |
| defender_status | Statut de Windows Defender | "statut defender", "etat antivirus", "defender ok", +2 | powershell |
| top_cpu_processes | Top 10 processus par CPU | "top cpu", "processus gourmands cpu", "qui mange le cpu", +2 | powershell |
| top_ram_processes | Top 10 processus par RAM | "top ram", "processus gourmands ram", "qui mange la ram", +2 | powershell |
| uptime_system | Uptime du systeme Windows | "uptime", "depuis combien de temps le pc tourne", "duree allumage", +1 | powershell |
| windows_update_check | Verifier les mises a jour Windows disponibles | "mises a jour windows", "windows update", "check updates", +2 | powershell |
| ip_publique_externe | Obtenir l'adresse IP publique | "ip publique", "quelle est mon ip", "mon ip publique", +2 | powershell |
| latence_cluster | Ping de latence vers les noeuds du cluster | "latence cluster", "ping le cluster ia", "latence des noeuds", +2 | powershell |
| wifi_info | Informations sur la connexion WiFi active | "info wifi", "quel wifi", "connexion wifi", +2 | powershell |
| espace_disques | Espace libre sur tous les disques | "espace disque", "combien d'espace libre", "espace libre", +2 | powershell |
| gros_fichiers_bureau | Top 10 plus gros fichiers du bureau | "plus gros fichiers", "gros fichiers bureau", "fichiers les plus lourds", +1 | powershell |

### Trading & IA (19 commandes)

| Commande | Description | Triggers | Type |
|----------|------------|----------|------|
| scanner_marche | Scanner le marche MEXC | "scanne le marche", "scanner le marche", "lance le scanner", +3 | script |
| detecter_breakout | Detecter les breakouts | "detecte les breakouts", "cherche les breakouts", "breakout detector", +2 | script |
| pipeline_trading | Lancer le pipeline intensif | "lance le pipeline", "pipeline intensif", "demarre le pipeline", +6 | script |
| sniper_breakout | Lancer le sniper breakout | "lance le sniper", "sniper breakout", "demarre le sniper", +1 | script |
| river_scalp | Lancer le River Scalp 1min | "lance river scalp", "river scalp", "scalp 1 minute", +2 | script |
| hyper_scan | Lancer l'hyper scan V2 | "lance hyper scan", "hyper scan", "scan intensif", +1 | script |
| statut_cluster | Statut du cluster IA | "statut du cluster", "etat du cluster", "statut cluster", +3 | jarvis_tool |
| modeles_charges | Modeles charges sur le cluster | "quels modeles sont charges", "liste les modeles", "modeles charges", +2 | jarvis_tool |
| ollama_status | Statut du backend Ollama | "statut ollama", "etat ollama", "status ollama", +3 | jarvis_tool |
| ollama_modeles | Modeles Ollama disponibles | "modeles ollama", "liste modeles ollama", "quels modeles ollama" | jarvis_tool |
| recherche_web_ia | Recherche web via Ollama cloud | "recherche web {requete}", "cherche sur le web {requete}", "recherche internet {requete}", +1 | jarvis_tool |
| consensus_ia | Consensus multi-IA | "consensus sur {question}", "demande un consensus sur {question}", "lance un consensus {question}", +1 | jarvis_tool |
| query_ia | Interroger une IA locale | "demande a {node} {prompt}", "interroge {node} sur {prompt}", "pose a {node} la question {prompt}" | jarvis_tool |
| signaux_trading | Signaux de trading en attente | "signaux en attente", "quels signaux", "signaux trading", +2 | jarvis_tool |
| positions_trading | Positions de trading ouvertes | "mes positions", "positions ouvertes", "quelles positions", +2 | jarvis_tool |
| statut_trading | Statut global du trading | "statut trading", "etat du trading", "status trading", +2 | jarvis_tool |
| executer_signal | Executer un signal de trading | "execute le signal {id}", "lance le signal {id}", "trade le signal {id}", +1 | jarvis_tool |
| cluster_health | Health check rapide du cluster IA | "health check cluster", "verifie le cluster ia", "est ce que le cluster va bien", +3 | powershell |
| ollama_running | Modeles Ollama actuellement en memoire | "quels modeles ollama tournent", "ollama running", "modeles en memoire ollama", +1 | powershell |

### Developpement & Outils (57 commandes)

| Commande | Description | Triggers | Type |
|----------|------------|----------|------|
| docker_ps | Lister les conteneurs Docker | "liste les conteneurs", "docker ps", "conteneurs docker", +2 | powershell |
| docker_images | Lister les images Docker | "images docker", "docker images", "quelles images", +1 | powershell |
| docker_stop_all | Arreter tous les conteneurs Docker | "arrete tous les conteneurs", "docker stop all", "stoppe docker", +1 | powershell |
| git_status | Git status du projet courant | "git status", "statut git", "etat du repo", +2 | powershell |
| git_log | Git log recent | "git log", "historique git", "derniers commits", +2 | powershell |
| git_pull | Git pull origin main | "git pull", "tire les changements", "pull git", +2 | powershell |
| git_push | Git push origin main | "git push", "pousse les commits", "push git", +2 | powershell |
| pip_list | Lister les packages Python installes | "pip list", "packages python", "quels packages", +2 | powershell |
| python_version | Version Python et uv | "version python", "quelle version python", "python version", +1 | powershell |
| ouvrir_n8n | Ouvrir n8n dans le navigateur | "ouvre n8n", "lance n8n", "n8n", +2 | browser |
| lm_studio_restart | Relancer LM Studio | "relance lm studio", "redemarre lm studio", "restart lm studio", +1 | powershell |
| ouvrir_jupyter | Ouvrir Jupyter dans le navigateur | "ouvre jupyter", "lance jupyter", "jupyter notebook", +2 | browser |
| wsl_lancer | Lancer WSL (Windows Subsystem for Linux) | "lance wsl", "ouvre wsl", "lance linux", +3 | powershell |
| wsl_liste | Lister les distributions WSL installees | "liste les distributions wsl", "wsl liste", "distributions linux" | powershell |
| wsl_shutdown | Arreter toutes les distributions WSL | "arrete wsl", "stoppe wsl", "ferme wsl", +1 | powershell |
| git_branches | Lister les branches git | "branches git", "quelles branches", "liste les branches", +2 | powershell |
| git_diff | Voir les modifications non commitees | "git diff", "modifications en cours", "quelles modifications", +2 | powershell |
| git_stash | Sauvegarder les modifications en stash | "git stash", "stash les changements", "sauvegarde les modifs", +1 | powershell |
| git_stash_pop | Restaurer les modifications du stash | "git stash pop", "restaure le stash", "recupere le stash", +1 | powershell |
| git_last_commit | Voir le dernier commit en detail | "dernier commit", "last commit", "montre le dernier commit", +1 | powershell |
| git_count | Compter les commits du projet | "combien de commits", "nombre de commits", "git count", +1 | powershell |
| node_version | Version de Node.js | "version node", "quelle version node", "node version", +1 | powershell |
| npm_list_global | Packages NPM globaux | "packages npm globaux", "npm global", "npm list global", +1 | powershell |
| ollama_restart | Redemarrer Ollama | "redemarre ollama", "restart ollama", "relance ollama", +1 | powershell |
| ollama_pull | Telecharger un modele Ollama | "telecharge le modele {model}", "ollama pull {model}", "installe le modele {model}", +1 | powershell |
| ollama_list | Lister les modeles Ollama installes | "liste les modeles ollama", "modeles ollama installes", "ollama list", +1 | powershell |
| ollama_remove | Supprimer un modele Ollama | "supprime le modele {model}", "ollama rm {model}", "desinstalle le modele {model}", +1 | powershell |
| lm_studio_models | Modeles charges dans LM Studio (M1, M2, M3) | "modeles lm studio", "quels modeles lm studio", "modeles charges lm studio" | powershell |
| uv_sync | Synchroniser les dependances uv | "uv sync", "synchronise les dependances", "sync les packages", +1 | powershell |
| python_test | Lancer les tests Python du projet | "lance les tests", "run tests", "pytest", +2 | powershell |
| python_lint | Verifier le code avec ruff | "lint le code", "ruff check", "verifie le code", +2 | powershell |
| docker_logs | Voir les logs d'un conteneur Docker | "logs docker de {container}", "docker logs {container}", "montre les logs de {container}" | powershell |
| docker_restart | Redemarrer un conteneur Docker | "redemarre le conteneur {container}", "docker restart {container}", "relance {container}" | powershell |
| docker_prune | Nettoyer les ressources Docker inutilisees | "nettoie docker", "docker prune", "clean docker", +1 | powershell |
| docker_stats | Statistiques des conteneurs Docker | "stats docker", "docker stats", "ressources docker", +1 | powershell |
| turbo_lines | Compter les lignes de code du projet turbo | "combien de lignes de code", "lignes de code turbo", "lines of code", +2 | powershell |
| turbo_size | Taille totale du projet turbo | "taille du projet turbo", "poids du projet", "combien pese turbo", +1 | powershell |
| turbo_files | Compter les fichiers du projet turbo | "combien de fichiers turbo", "nombre de fichiers", "fichiers du projet", +1 | powershell |
| lms_status | Statut du serveur LM Studio local | "statut lm studio", "lm studio status", "etat lm studio", +2 | powershell |
| lms_list_loaded | Modeles actuellement charges dans LM Studio local | "modeles charges locaux", "lms loaded", "quels modeles tourment", +2 | powershell |
| lms_load_model | Charger un modele dans LM Studio local | "charge le modele {model}", "lms load {model}", "load {model} dans lm studio", +1 | powershell |
| lms_unload_model | Decharger un modele de LM Studio local | "decharge le modele {model}", "lms unload {model}", "unload {model}", +1 | powershell |
| lms_list_available | Lister les modeles disponibles sur le disque | "modeles disponibles lm studio", "lms list", "quels modeles j'ai", +1 | powershell |
| git_status_turbo | Statut git du projet turbo | "git status", "statut git", "etat du repo", +1 | powershell |
| git_log_short | Derniers 10 commits (resume) | "historique git", "git log", "derniers commits", +2 | powershell |
| git_remote_info | Informations sur le remote git | "remote git", "git remote", "quel remote", +2 | powershell |
| ouvrir_telegram | Ouvrir Telegram Desktop | "ouvre telegram", "lance telegram", "va sur telegram", +1 | app_open |
| ouvrir_whatsapp | Ouvrir WhatsApp Desktop | "ouvre whatsapp", "lance whatsapp", "va sur whatsapp", +1 | app_open |
| ouvrir_slack | Ouvrir Slack Desktop | "ouvre slack", "lance slack", "va sur slack", +1 | app_open |
| ouvrir_teams | Ouvrir Microsoft Teams | "ouvre teams", "lance teams", "va sur teams", +2 | app_open |
| ouvrir_zoom | Ouvrir Zoom | "ouvre zoom", "lance zoom", "va sur zoom", +1 | app_open |
| bun_version | Version de Bun | "version bun", "quelle version bun", "bun version" | powershell |
| deno_version | Version de Deno | "version deno", "quelle version deno", "deno version" | powershell |
| rust_version | Version de Rust/Cargo | "version rust", "quelle version rust", "rustc version", +2 | powershell |
| python_uv_version | Version de Python et uv | "version python", "quelle version python", "python version", +1 | powershell |
| turbo_recent_changes | Fichiers modifies recemment dans turbo | "fichiers recents turbo", "modifications recentes", "quoi de modifie recemment", +1 | powershell |
| turbo_todo | Lister les TODO dans le code turbo | "liste les todo", "todo dans le code", "quels todo reste", +2 | powershell |

### Controle JARVIS (12 commandes)

| Commande | Description | Triggers | Type |
|----------|------------|----------|------|
| historique_commandes | Voir l'historique des commandes JARVIS | "historique des commandes", "quelles commandes j'ai utilise", "dernieres commandes", +1 | powershell |
| jarvis_aide | Afficher l'aide JARVIS | "aide", "help", "quelles commandes", +5 | list_commands |
| jarvis_stop | Arreter JARVIS | "jarvis stop", "jarvis arrete", "arrete jarvis", +11 | exit |
| jarvis_repete | Repeter la derniere reponse | "repete", "redis", "repete ca", +3 | jarvis_repeat |
| jarvis_scripts | Lister les scripts disponibles | "quels scripts sont disponibles", "liste les scripts", "montre les scripts", +1 | jarvis_tool |
| jarvis_projets | Lister les projets indexes | "quels projets existent", "liste les projets", "montre les projets", +1 | jarvis_tool |
| jarvis_notification | Envoyer une notification | "notifie {message}", "notification {message}", "envoie une notification {message}", +1 | jarvis_tool |
| jarvis_skills | Lister les skills/pipelines appris | "quels skills existent", "liste les skills", "montre les skills", +3 | list_commands |
| jarvis_suggestions | Suggestions d'actions | "que me suggeres tu", "suggestions", "quoi faire", +2 | list_commands |
| jarvis_brain_status | Etat du cerveau JARVIS | "etat du cerveau", "brain status", "cerveau jarvis", +2 | jarvis_tool |
| jarvis_brain_learn | Apprendre de nouveaux patterns | "apprends", "brain learn", "auto apprends", +2 | jarvis_tool |
| jarvis_brain_suggest | Demander une suggestion de skill a l'IA | "suggere un skill", "brain suggest", "invente un skill", +2 | jarvis_tool |

### Launchers JARVIS (12 commandes)

| Commande | Description | Triggers | Type |
|----------|------------|----------|------|
| launch_pipeline_10 | Lancer le Pipeline 10 Cycles | "lance le pipeline 10 cycles", "pipeline 10 cycles", "pipeline 10", +4 | script |
| launch_sniper_10 | Lancer le Sniper 10 Cycles | "lance le sniper 10 cycles", "sniper 10 cycles", "sniper 10", +2 | script |
| launch_sniper_breakout | Lancer le Sniper Breakout | "lance sniper breakout", "sniper breakout", "detection breakout", +2 | script |
| launch_trident | Lancer Trident Execute (dry run) | "lance trident", "trident execute", "execute trident", +2 | script |
| launch_hyper_scan | Lancer l'Hyper Scan V2 | "lance hyper scan", "hyper scan v2", "grid computing scan", +2 | script |
| launch_monitor_river | Lancer le Monitor RIVER Scalp | "lance river", "monitor river", "lance le monitor river", +3 | script |
| launch_command_center | Ouvrir le JARVIS Command Center (GUI) | "ouvre le command center", "command center", "lance le cockpit", +4 | script |
| launch_electron_app | Ouvrir JARVIS Electron App | "lance electron", "jarvis electron", "ouvre l'application jarvis", +2 | script |
| launch_widget | Ouvrir le Widget JARVIS | "lance le widget jarvis", "jarvis widget", "widget trading", +2 | script |
| launch_disk_cleaner | Lancer le nettoyeur de disque | "nettoie le disque", "disk cleaner", "lance le nettoyeur", +3 | script |
| launch_master_node | Lancer le Master Interaction Node | "lance le master node", "master interaction", "noeud principal", +2 | script |
| launch_fs_agent | Lancer l'agent fichiers JARVIS | "lance l'agent fichiers", "fs agent", "agent systeme fichiers", +2 | script |

### Accessibilite (10 commandes)

| Commande | Description | Triggers | Type |
|----------|------------|----------|------|
| taille_texte_grand | Agrandir la taille du texte systeme | "texte plus grand", "agrandis le texte", "taille texte grande", +2 | ms_settings |
| clavier_virtuel | Ouvrir le clavier virtuel | "clavier virtuel", "ouvre le clavier virtuel", "clavier a l'ecran", +2 | powershell |
| filtre_couleur | Activer/desactiver le filtre de couleur | "filtre de couleur", "active le filtre couleur", "mode daltonien", +2 | ms_settings |
| sous_titres | Parametres des sous-titres | "sous-titres", "parametres sous-titres", "active les sous-titres", +2 | ms_settings |
| contraste_eleve_toggle | Activer/desactiver le contraste eleve | "contraste eleve", "high contrast", "active le contraste", +2 | powershell |
| sous_titres_live | Activer les sous-titres en direct | "sous titres en direct", "live captions", "active les sous titres", +2 | powershell |
| filtre_couleur_toggle | Activer les filtres de couleur | "filtre de couleur", "color filter", "daltonien", +2 | powershell |
| taille_curseur | Changer la taille du curseur | "agrandis le curseur", "curseur plus grand", "taille curseur", +2 | powershell |
| narrateur_toggle | Activer/desactiver le narrateur | "active le narrateur", "narrateur windows", "desactive le narrateur", +2 | powershell |
| sticky_keys_toggle | Activer/desactiver les touches remanentes | "active les touches remanentes", "desactive les touches remanentes", "sticky keys", +1 | powershell |

### Saisie & Texte (4 commandes)

| Commande | Description | Triggers | Type |
|----------|------------|----------|------|
| texte_majuscule | Convertir le presse-papier en majuscules | "en majuscules", "tout en majuscules", "texte en majuscules", +2 | powershell |
| texte_minuscule | Convertir le presse-papier en minuscules | "en minuscules", "tout en minuscules", "texte en minuscules", +1 | powershell |
| ouvrir_emojis | Ouvrir le panneau emojis | "ouvre les emojis", "panneau emojis", "emoji picker", +2 | hotkey |
| ouvrir_dictee | Activer la dictee vocale Windows | "dicte", "dictee windows", "active la dictee", +2 | hotkey |
