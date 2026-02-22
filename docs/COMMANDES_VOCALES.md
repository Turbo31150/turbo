# Commandes Vocales JARVIS - Reference Complete

> Mise a jour automatique: 2026-02-22 | Voice Pipeline v2

**1092 commandes** au total, dont **191 pipelines** multi-etapes, reparties en **14 categories**.

| Categorie | Nombre |
|-----------|--------|
| Systeme Windows | 463 |
| Pipelines Multi-Etapes | 191 |
| Navigation Web | 167 |
| Developpement & Outils | 126 |
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
| **TOTAL** | **1092** |

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
| mode_podcast | "mode podcast" | MinimizeAll > pause 1s > Ouvrir spotify > $w = New-Object -ComObject WScript.Shell; 1..5 | F... |
| mode_apprentissage | "mode apprentissage" | Settings > pause 1s > Web: https://www.udemy.com > pause 1s > Web: https://docs.google.com > pause 1s > MinimizeAll |
| mode_news | "mode news" | Web: https://news.google.com > pause 1s > Web: https://www.reddit.com > pause 1s > Web: https://x.com |
| mode_shopping | "mode shopping" | Web: https://www.amazon.fr > pause 1s > Web: https://www.leboncoin.fr > pause 1s > Web: https://www.google.com/shopping |
| mode_design | "mode design" | Web: https://www.figma.com > pause 1s > Web: https://www.pinterest.com > pause 1s > Web: https://www.canva.com |
| mode_musique_decouverte | "decouverte musicale" | Ouvrir spotify > pause 1s > Web: https://music.youtube.com > pause 1s > Web: https://soundcloud.com |
| routine_weekend | "routine weekend" | MinimizeAll > pause 1s > Start-Process ms-settings:nightlight > pause 1s > Web: https://news.google.com > pause 1s > ... |
| mode_social_complet | "mode social complet" | Web: https://x.com > pause 1s > Web: https://www.reddit.com > pause 1s > Web: https://www.instagram.com > pause 1s > ... |
| mode_planning | "mode planning" | Web: https://calendar.google.com > pause 1s > Web: https://www.notion.so > pause 1s > Web: https://mail.google.com/ta... |
| mode_brainstorm | "mode brainstorm" | Web: https://claude.ai > pause 1s > Web: https://www.notion.so > $end = (Get-Date).AddMinutes(30).ToString('HH:mm')... |
| nettoyage_downloads | "nettoie les telechargements" | $count = (Get-ChildItem $env:USERPROFILE\Downloads... (confirm) |
| rapport_reseau_complet | "rapport reseau complet" | (Invoke-RestMethod -Uri 'https://api.ipify.org?for... > $dns = Resolve-DnsName google.com -ErrorAction Sil... > $p = ... |
| verif_toutes_mises_a_jour | "verifie toutes les mises a jour" | try{$s=New-Object -ComObject Microsoft.Update.Sess... > & 'C:\Users\franc\.local\bin\uv.exe' pip list --ou... > npm o... |
| snapshot_systeme | "snapshot systeme" | $d = Get-Date -Format 'yyyy-MM-dd_HHmm'; $f = "F:\... |
| dev_hotfix | "hotfix" | cd F:\BUREAU\turbo; $branch = 'hotfix/' + (Get-Dat... > pause 1s > Ouvrir code > pause 1s > Ouvrir wt |
| dev_new_feature | "nouvelle feature" | cd F:\BUREAU\turbo; $branch = 'feature/' + (Get-Da... > pause 1s > Ouvrir code > pause 1s > Ouvrir wt > cd F:\BUREAU\... |
| dev_merge_prep | "prepare le merge" | cd F:\BUREAU\turbo; & 'C:\Users\franc\.local\bin\u... > cd F:\BUREAU\turbo; & 'C:\Users\franc\.local\bin\u... > cd F:... |
| dev_database_check | "check les databases" | $j = (Get-Item 'F:\BUREAU\turbo\data\jarvis.db' -E... > $e = (Get-Item 'F:\BUREAU\etoile.db' -ErrorAction ... > $t = ... |
| dev_live_coding | "live coding" | Ouvrir obs64 > pause 2s > Ouvrir code > pause 1s > Ouvrir wt > pause 1s > Web: http://localhost:3000 |
| dev_cleanup | "dev cleanup" | cd F:\BUREAU\turbo; $pycache = (Get-ChildItem -Rec... > cd F:\BUREAU\turbo; $ruff = & 'C:\Users\franc\.loc... |
| mode_double_ecran_dev | "mode double ecran dev" | DisplaySwitch.exe /extend > pause 2s > Ouvrir code > pause 1s > Raccourci: win+left > pause 1s > Web: http://127.0.0.... |
| mode_presentation_zoom | "mode presentation zoom" | Stop-Process -Name 'spotify','discord' -Force -Err... > MinimizeAll > pause 1s > DisplaySwitch.exe /clone > pause 2s ... |
| mode_dashboard_complet | "dashboard complet" | Web: http://127.0.0.1:8080 > pause 1s > Web: https://www.tradingview.com > pause 1s > Web: http://127.0.0.1:5678 > pa... |
| ferme_tout_sauf_code | "ferme tout sauf le code" | Stop-Process -Name 'chrome','msedge','discord','te... > pause 1s > Get-Process code -ErrorAction SilentlyContinue | S... |
| mode_detox_digital | "detox digitale" | Stop-Process -Name 'chrome','msedge','discord','te... > pause 1s > MinimizeAll > pause 1s > Start-Process ms-settings... (confirm) |
| mode_musique_travail | "musique de travail" | Ouvrir spotify > pause 1s > Settings |
| check_tout_rapide | "check tout rapide" | $m2 = try{(Invoke-WebRequest -Uri 'http://192.168.... > $os = Get-CimInstance Win32_OperatingSystem; $ram ... > nvidi... |
| mode_hackathon | "mode hackathon" | Ouvrir code > pause 1s > Ouvrir wt > pause 1s > Web: https://github.com > pause 1s > Web: https://claude.ai > $end = ... |
| mode_data_science | "mode data science" | Ouvrir wt > pause 1s > Web: https://www.kaggle.com > pause 1s > Web: https://docs.python.org/3/ > pause 1s > Web: htt... |
| mode_devops | "mode devops" | Ouvrir wt > pause 1s > Web: http://127.0.0.1:8080 > pause 1s > Web: https://github.com > docker ps --format 'table {{... |
| mode_securite_audit | "mode securite" | Ouvrir wt > pause 1s > Get-MpComputerStatus | Select AntivirusEnabled, Re... > Get-NetTCPConnection -State Listen | G... |
| mode_trading_scalp | "mode scalping" | Web: https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT > pause 1s > Web: https://www.mexc.com/exchange/BTC_US... |
| routine_midi | "routine midi" | MinimizeAll > pause 1s > Web: https://news.google.com > pause 1s > Web: https://www.tradingview.com > pause 1s > Ouvr... |
| routine_nuit_urgence | "urgence nuit" | cd F:\BUREAU\turbo; git add -A; git commit -m 'Eme... > pause 1s > MinimizeAll > Lock PC > pause 2s > Veille (confirm) |
| setup_meeting_rapide | "meeting rapide" | Stop-Process -Name 'spotify' -Force -ErrorAction S... > MinimizeAll > pause 1s > Settings > pause 1s > Ouvrir discord |
| mode_veille_tech | "veille tech" | Web: https://news.ycombinator.com > pause 1s > Web: https://dev.to > pause 1s > Web: https://www.producthunt.com > pa... |
| mode_freelance | "mode freelance" | Web: https://mail.google.com > pause 1s > Web: https://calendar.google.com > pause 1s > Web: https://www.notion.so > ... |
| mode_debug_production | "debug production" | Ouvrir wt > pause 1s > Web: http://127.0.0.1:8080 > pause 1s > Get-WinEvent -FilterHashtable @{LogName='Applicati... ... |
| mode_apprentissage_code | "mode apprentissage code" | Web: https://leetcode.com > pause 1s > Ouvrir code > pause 1s > Web: https://docs.python.org/3/ > $end = (Get-Date).A... |
| mode_tutorial | "mode tutorial" | Web: https://www.youtube.com > pause 1s > Ouvrir code > pause 1s > Ouvrir wt > pause 1s > Web: https://developer.mozi... |
| mode_backup_total | "backup total" | cd F:\BUREAU\turbo; git add -A; git commit -m 'Ful... > cd F:\BUREAU\carV1; if(Test-Path .git){git add -A;... > cd F:... (confirm) |
| ouvre_dashboards_trading | "tous les dashboards trading" | Web: https://www.tradingview.com > pause 1s > Web: https://www.mexc.com/exchange/BTC_USDT > pause 1s > Web: https://w... |
| mode_photo_edit | "mode photo" | Ouvrir mspaint > pause 1s > Web: https://www.pinterest.com > pause 1s > Web: https://www.canva.com |
| mode_writing | "mode ecriture" | MinimizeAll > pause 1s > Start-Process ms-settings:nightlight > pause 1s > Settings > pause 1s > Web: https://docs.go... |
| mode_video_marathon | "mode marathon" | MinimizeAll > pause 1s > Start-Process ms-settings:nightlight > pause 1s > Web: https://www.netflix.com > pause 2s > ... |
| ouvre_kaggle_comet | "ouvre kaggle sur comet" | Comet: https://www.kaggle.com |
| ouvre_arxiv_comet | "ouvre arxiv sur comet" | Comet: https://arxiv.org |
| ouvre_notion_comet | "ouvre notion sur comet" | Comet: https://www.notion.so |
| ouvre_stackoverflow_comet | "ouvre stackoverflow sur comet" | Comet: https://stackoverflow.com |
| ouvre_medium_comet | "ouvre medium sur comet" | Comet: https://medium.com |
| ouvre_gmail_comet | "ouvre gmail sur comet" | Comet: https://mail.google.com |
| mode_go_live | "go live" | Ouvrir obs64 > pause 2s > Web: https://dashboard.twitch.tv > pause 1s > Ouvrir spotify > pause 1s > Web: https://www.... |
| mode_end_stream | "arrete le stream" | Stop-Process -Name 'obs64' -Force -ErrorAction Sil... > pause 1s > "Stream termine — GG!" |
| mode_daily_report | "rapport quotidien" | cd F:\BUREAU\turbo; 'Commits du jour:'; git log --... > cd F:\BUREAU\turbo; $py = (Get-ChildItem src/*.py ... > Web: ... |
| mode_api_test | "mode api test" | Ouvrir wt > pause 1s > Web: http://127.0.0.1:8080 > pause 1s > Web: https://httpie.io/app > pause 1s > Web: https://r... |
| mode_conference_full | "mode conference" | Stop-Process -Name 'spotify','obs64' -Force -Error... > MinimizeAll > pause 1s > Settings > pause 1s > Ouvrir teams >... |
| mode_end_meeting | "fin du meeting" | Stop-Process -Name 'teams','zoom' -Force -ErrorAct... > pause 1s > Ouvrir spotify > "Reunion terminee — retour au tra... |
| mode_home_theater | "mode home theater" | MinimizeAll > pause 1s > Start-Process ms-settings:nightlight > pause 1s > $w = New-Object -ComObject WScript.Shell; ... |
| mode_refactoring | "mode refactoring" | Ouvrir code > pause 1s > cd F:\BUREAU\turbo; & 'C:\Users\franc\.local\bin\u... > cd F:\BUREAU\turbo; git diff --stat ... |
| mode_testing_complet | "mode testing complet" | Ouvrir wt > pause 1s > cd F:\BUREAU\turbo; & 'C:\Users\franc\.local\bin\u... > cd F:\BUREAU\turbo; & 'C:\Users\franc\... |
| mode_deploy_checklist | "checklist deploy" | cd F:\BUREAU\turbo; & 'C:\Users\franc\.local\bin\u... > cd F:\BUREAU\turbo; & 'C:\Users\franc\.local\bin\u... > cd F:... |
| mode_documentation_code | "mode documentation code" | Ouvrir code > pause 1s > Web: https://www.notion.so > pause 1s > Ouvrir wt > pause 1s > Web: https://docs.python.org/3/ |
| mode_open_source | "mode open source" | Web: https://github.com/pulls > pause 1s > Web: https://github.com/issues > pause 1s > Ouvrir code > pause 1s > Ouvri... |
| mode_side_project | "mode side project" | Ouvrir code > pause 1s > Ouvrir wt > pause 1s > Web: https://github.com > $end = (Get-Date).AddHours(2).ToString('HH:... |
| mode_admin_sys | "mode sysadmin" | Ouvrir wt > pause 1s > Get-Service | Where Status -eq 'Stopped' | Where S... > Get-NetTCPConnection -State Listen | G... |
| mode_reseau_complet | "mode reseau complet" | $p = Test-Connection 8.8.8.8 -Count 2 -ErrorAction... > Resolve-DnsName google.com -ErrorAction SilentlyCo... > netsh... |
| mode_finance | "mode finance" | Web: https://www.google.com/finance > pause 1s > Web: https://sheets.google.com > pause 1s > Web: https://www.trading... |
| mode_voyage | "mode voyage" | Web: https://www.google.com/flights > pause 1s > Web: https://maps.google.com > pause 1s > Web: https://www.booking.c... |
| routine_aperitif | "routine apero" | Stop-Process -Name 'code','wt' -Force -ErrorAction... > MinimizeAll > pause 1s > Start-Process ms-settings:nightlight... |
| mode_cuisine | "mode cuisine" | Web: https://www.youtube.com/results?search_query=recette+facile+rapide > pause 1s > Ouvrir spotify > $end = (Get-Dat... |
| mode_meditation | "mode meditation" | MinimizeAll > pause 1s > Start-Process ms-settings:nightlight > pause 1s > Web: https://www.youtube.com/results?searc... |
| mode_pair_programming | "mode pair programming" | Ouvrir code > pause 1s > Ouvrir discord > pause 1s > Ouvrir wt > pause 1s > Web: https://github.com |
| mode_retrospective | "mode retro" | cd F:\BUREAU\turbo; 'Commits semaine:'; git log --... > Web: https://www.notion.so > pause 1s > Web: https://calendar... |
| mode_demo | "mode demo" | DisplaySwitch.exe /clone > pause 2s > Web: http://127.0.0.1:8080 > pause 1s > Web: https://github.com > pause 1s > "D... |
| mode_scrum_master | "mode scrum" | Web: https://github.com/projects > pause 1s > Web: https://calendar.google.com > pause 1s > cd F:\BUREAU\turbo; git l... |
| sim_reveil_complet | "demarre la journee complete" | powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a... > Ouvrir lmstudio > pause 2s > Web: http://127.0.0.1:8080 > pau... |
| sim_check_matinal | "check matinal" | $m2 = try{(Invoke-WebRequest -Uri 'http://192.168.... > nvidia-smi --query-gpu=name,temperature.gpu,memory... > $os =... |
| sim_start_coding | "je commence a coder" | cd F:\BUREAU\turbo; git pull --rebase 2>&1 | Out-String > Ouvrir code > pause 2s > Raccourci: win+left > pause 1s > O... |
| sim_code_and_test | "teste mon code" | cd F:\BUREAU\turbo; & 'C:\Users\franc\.local\bin\u... > cd F:\BUREAU\turbo; & 'C:\Users\franc\.local\bin\u... > cd F:... |
| sim_commit_and_push | "commit et push" | cd F:\BUREAU\turbo; git add -A; git status -sb > cd F:\BUREAU\turbo; git commit -m 'Update auto-JAR... > cd F:\BUREAU... (confirm) |
| sim_debug_session | "session debug complete" | Ouvrir code > pause 1s > Raccourci: ctrl+` > pause 1s > Raccourci: f12 > Get-WinEvent -FilterHashtable @{LogName='App... |
| sim_avant_reunion | "prepare la reunion" | Stop-Process -Name 'spotify','obs64' -Force -Error... > MinimizeAll > pause 1s > Settings > pause 1s > Web: https://c... |
| sim_rejoindre_reunion | "rejoins la reunion" | Ouvrir discord > pause 2s > Raccourci: win+p > "En reunion — partage ecran disponible via Win+P" |
| sim_presenter_ecran | "presente mon ecran" | DisplaySwitch.exe /clone > pause 2s > Web: http://127.0.0.1:8080 > pause 2s > Raccourci: f11 > "Presentation en cours" |
| sim_apres_reunion | "reunion terminee reprends" | Stop-Process -Name 'teams','zoom','discord' -Force... > pause 1s > Ouvrir spotify > pause 1s > Ouvrir code > pause 1s... |
| sim_pause_cafe | "pause cafe" | MinimizeAll > pause 1s > Lock PC > "Pause cafe — reviens frais!" |
| sim_pause_longue | "longue pause" | cd F:\BUREAU\turbo; git add -A; git commit -m 'Aut... > MinimizeAll > pause 1s > Start-Process ms-settings:nightlight... |
| sim_retour_pause | "je suis de retour" | powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c > Ouvrir code > pause 1s > Ouvrir wt > pause 1s > $m2 = try{... |
| sim_recherche_intensive | "recherche intensive" | Web: https://claude.ai > pause 1s > Web: https://www.perplexity.ai > pause 1s > Web: https://scholar.google.com > pau... |
| sim_formation_video | "formation video complete" | Settings > pause 1s > MinimizeAll > pause 1s > Web: https://www.youtube.com > pause 1s > Ouvrir code > pause 1s > Web... |
| sim_analyse_trading | "analyse trading complete" | Web: https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT > pause 1s > Web: https://www.coingecko.com > pause 1s... |
| sim_execution_trading | "execute le trading" | Web: https://www.mexc.com/exchange/BTC_USDT > pause 1s > Web: https://www.tradingview.com > pause 1s > Ouvrir wt > "M... |
| sim_monitoring_positions | "surveille mes positions" | Web: https://www.mexc.com/exchange/BTC_USDT > pause 1s > Web: https://dexscreener.com > pause 1s > Web: https://www.t... |
| sim_layout_dev_split | "layout dev split" | Ouvrir code > pause 2s > Raccourci: win+left > pause 1s > Web: http://127.0.0.1:8080 > pause 1s > Raccourci: win+righ... |
| sim_layout_triple | "layout triple" | Ouvrir code > pause 2s > Raccourci: win+left > Raccourci: win+up > pause 1s > Ouvrir wt > pause 1s > Raccourci: win+l... |
| sim_tout_fermer_propre | "ferme tout proprement" | cd F:\BUREAU\turbo; git add -A; git commit -m 'Cle... > Stop-Process -Name 'code','wt','obs64','discord','... > pause... |
| sim_fin_journee_complete | "fin de journee complete" | cd F:\BUREAU\turbo; git add -A; git commit -m 'Fin... > cd F:\BUREAU\turbo; $c = (git log --since='today' ... > Stop-... (confirm) |
| sim_weekend_mode | "mode weekend complet" | cd F:\BUREAU\turbo; git add -A; git commit -m 'Wee... > Stop-Process -Name 'code','wt','lmstudio' -Force -... > pause... |
| sim_urgence_gpu | "urgence gpu" | nvidia-smi --query-gpu=name,temperature.gpu,utiliz... > Get-Process | Sort WS -Descending | Select -First ... > "Chec... |
| sim_urgence_reseau | "urgence reseau" | ipconfig /flushdns; 'DNS purge' > $p = Test-Connection 8.8.8.8 -Count 2 -ErrorAction... > $d = Resolve-DnsName google... |
| sim_urgence_espace | "urgence espace disque" | Get-PSDrive -PSProvider FileSystem | Where Used -g... > $t = (Get-ChildItem $env:TEMP -Recurse -File -Erro... > $d = ... |
| sim_urgence_performance | "urgence performance" | $cpu = (Get-Counter '\Processor(_Total)\% Processo... > $os = Get-CimInstance Win32_OperatingSystem; $used... > Get-P... |
| sim_multitask_dev_trading | "multitask dev et trading" | Ouvrir code > pause 2s > Raccourci: win+left > pause 1s > Web: https://www.tradingview.com > pause 1s > Raccourci: wi... |
| sim_multitask_email_code | "mails et code" | Web: https://mail.google.com > pause 2s > Raccourci: win+left > pause 1s > Ouvrir code > pause 1s > Raccourci: win+ri... |
| sim_focus_extreme | "focus extreme" | Stop-Process -Name 'chrome','msedge','discord','te... > MinimizeAll > pause 1s > Settings > pause 1s > Start-Process ... |
| sim_soiree_gaming | "soiree gaming" | Stop-Process -Name 'code','wt','lmstudio' -Force -... > MinimizeAll > pause 1s > powercfg /setactive 8c5e7fda-e8bf-4a... |
| sim_soiree_film | "soiree film complete" | Stop-Process -Name 'code','wt','discord','lmstudio... > MinimizeAll > pause 1s > Start-Process ms-settings:nightlight... |
| sim_soiree_musique | "soiree musique" | MinimizeAll > pause 1s > Start-Process ms-settings:nightlight > pause 1s > Ouvrir spotify > pause 1s > $w = New-Objec... |
| sim_maintenance_hebdo | "maintenance hebdomadaire" | Remove-Item $env:TEMP\* -Recurse -Force -ErrorActi... > Clear-RecycleBin -Force -ErrorAction SilentlyConti... > Remov... (confirm) |
| sim_backup_hebdo | "backup hebdomadaire" | cd F:\BUREAU\turbo; git add -A; git commit -m 'Wee... > cd F:\BUREAU\turbo; $c = (git log --since='1 week ... > $d = ... (confirm) |

---

## Listing Complet par Categorie

### Navigation Web (167 commandes)

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
| ouvrir_google_translate | Ouvrir Google Translate | "ouvre google translate", "traducteur", "google traduction", +2 | browser |
| ouvrir_google_news | Ouvrir Google Actualites | "ouvre google news", "google actualites", "lance les news", +1 | browser |
| ouvrir_figma | Ouvrir Figma | "ouvre figma", "va sur figma", "lance figma" | browser |
| ouvrir_canva | Ouvrir Canva | "ouvre canva", "va sur canva", "lance canva" | browser |
| ouvrir_pinterest | Ouvrir Pinterest | "ouvre pinterest", "va sur pinterest", "lance pinterest" | browser |
| ouvrir_udemy | Ouvrir Udemy | "ouvre udemy", "va sur udemy", "lance udemy", +1 | browser |
| ouvrir_regex101 | Ouvrir Regex101 (testeur de regex) | "ouvre regex101", "testeur regex", "lance regex101", +1 | browser |
| ouvrir_jsonformatter | Ouvrir un formatteur JSON en ligne | "ouvre json formatter", "formatte du json", "json en ligne", +1 | browser |
| ouvrir_speedtest | Ouvrir Speedtest | "ouvre speedtest", "lance un speed test", "test de debit", +1 | browser |
| ouvrir_excalidraw | Ouvrir Excalidraw (tableau blanc) | "ouvre excalidraw", "tableau blanc", "lance excalidraw", +1 | browser |
| ouvrir_soundcloud | Ouvrir SoundCloud | "ouvre soundcloud", "va sur soundcloud", "lance soundcloud" | browser |
| ouvrir_google_scholar | Ouvrir Google Scholar | "ouvre google scholar", "google scholar", "recherche academique", +1 | browser |
| chercher_traduction | Traduire un texte via Google Translate | "traduis {requete}", "traduction de {requete}", "translate {requete}", +1 | browser |
| chercher_google_scholar | Rechercher sur Google Scholar | "cherche sur scholar {requete}", "article sur {requete}", "recherche academique {requete}", +1 | browser |
| chercher_huggingface | Rechercher un modele sur Hugging Face | "cherche sur hugging face {requete}", "modele {requete} huggingface", "hugging face {requete}" | browser |
| chercher_docker_hub | Rechercher une image Docker Hub | "cherche sur docker hub {requete}", "image docker {requete}", "docker hub {requete}" | browser |
| ouvrir_gmail_web | Ouvrir Gmail | "ouvre gmail", "va sur gmail", "lance gmail", +2 | browser |
| ouvrir_google_keep | Ouvrir Google Keep (notes) | "ouvre google keep", "ouvre keep", "lance keep", +2 | browser |
| ouvrir_google_photos | Ouvrir Google Photos | "ouvre google photos", "va sur google photos", "mes photos", +2 | browser |
| ouvrir_google_meet | Ouvrir Google Meet | "ouvre google meet", "lance meet", "google meet", +2 | browser |
| ouvrir_deepl | Ouvrir DeepL Traducteur | "ouvre deepl", "va sur deepl", "lance deepl", +2 | browser |
| ouvrir_wayback_machine | Ouvrir la Wayback Machine (archive web) | "ouvre wayback machine", "wayback machine", "archive internet", +2 | browser |
| ouvrir_codepen | Ouvrir CodePen | "ouvre codepen", "va sur codepen", "lance codepen", +2 | browser |
| ouvrir_jsfiddle | Ouvrir JSFiddle | "ouvre jsfiddle", "va sur jsfiddle", "lance jsfiddle", +1 | browser |
| ouvrir_dev_to | Ouvrir dev.to (communaute dev) | "ouvre dev to", "va sur dev to", "lance dev.to", +2 | browser |
| ouvrir_medium | Ouvrir Medium | "ouvre medium", "va sur medium", "lance medium", +1 | browser |
| ouvrir_hacker_news | Ouvrir Hacker News | "ouvre hacker news", "va sur hacker news", "lance hacker news", +2 | browser |
| ouvrir_producthunt | Ouvrir Product Hunt | "ouvre product hunt", "va sur product hunt", "lance product hunt", +2 | browser |
| ouvrir_coursera | Ouvrir Coursera | "ouvre coursera", "va sur coursera", "lance coursera", +2 | browser |
| ouvrir_kaggle | Ouvrir Kaggle | "ouvre kaggle", "va sur kaggle", "lance kaggle", +2 | browser |
| ouvrir_arxiv | Ouvrir arXiv (articles scientifiques) | "ouvre arxiv", "va sur arxiv", "lance arxiv", +2 | browser |
| ouvrir_gitlab | Ouvrir GitLab | "ouvre gitlab", "va sur gitlab", "lance gitlab" | browser |
| ouvrir_bitbucket | Ouvrir Bitbucket | "ouvre bitbucket", "va sur bitbucket", "lance bitbucket" | browser |
| ouvrir_leetcode | Ouvrir LeetCode | "ouvre leetcode", "va sur leetcode", "lance leetcode", +2 | browser |
| ouvrir_codewars | Ouvrir Codewars | "ouvre codewars", "va sur codewars", "lance codewars", +2 | browser |
| chercher_deepl | Traduire via DeepL | "traduis avec deepl {requete}", "deepl {requete}", "traduction deepl {requete}", +1 | browser |
| chercher_arxiv | Rechercher sur arXiv | "cherche sur arxiv {requete}", "arxiv {requete}", "paper sur {requete}", +1 | browser |
| chercher_kaggle | Rechercher sur Kaggle | "cherche sur kaggle {requete}", "kaggle {requete}", "dataset {requete}", +1 | browser |
| chercher_leetcode | Rechercher un probleme LeetCode | "cherche sur leetcode {requete}", "leetcode {requete}", "probleme {requete} leetcode" | browser |
| chercher_medium | Rechercher sur Medium | "cherche sur medium {requete}", "medium {requete}", "article medium {requete}" | browser |
| chercher_hacker_news | Rechercher sur Hacker News | "cherche sur hacker news {requete}", "hn {requete}", "hacker news {requete}" | browser |
| ouvrir_linear | Ouvrir Linear (gestion de projet dev) | "ouvre linear", "va sur linear", "lance linear", +2 | browser |
| ouvrir_miro | Ouvrir Miro (whiteboard collaboratif) | "ouvre miro", "va sur miro", "lance miro", +2 | browser |
| ouvrir_loom | Ouvrir Loom (enregistrement ecran) | "ouvre loom", "va sur loom", "lance loom", +1 | browser |
| ouvrir_supabase | Ouvrir Supabase | "ouvre supabase", "va sur supabase", "lance supabase", +1 | browser |
| ouvrir_firebase | Ouvrir Firebase Console | "ouvre firebase", "va sur firebase", "lance firebase", +1 | browser |
| ouvrir_railway | Ouvrir Railway (deploy) | "ouvre railway", "va sur railway", "lance railway", +1 | browser |
| ouvrir_cloudflare | Ouvrir Cloudflare Dashboard | "ouvre cloudflare", "va sur cloudflare", "lance cloudflare", +1 | browser |
| ouvrir_render | Ouvrir Render (hosting) | "ouvre render", "va sur render", "lance render", +1 | browser |
| ouvrir_fly_io | Ouvrir Fly.io | "ouvre fly io", "va sur fly", "lance fly io", +1 | browser |
| ouvrir_mdn | Ouvrir MDN Web Docs | "ouvre mdn", "va sur mdn", "docs mdn", +2 | browser |
| ouvrir_devdocs | Ouvrir DevDocs.io (toute la doc dev) | "ouvre devdocs", "va sur devdocs", "lance devdocs", +2 | browser |
| ouvrir_can_i_use | Ouvrir Can I Use (compatibilite navigateurs) | "ouvre can i use", "can i use", "compatibilite navigateur", +1 | browser |
| ouvrir_bundlephobia | Ouvrir Bundlephobia (taille des packages) | "ouvre bundlephobia", "bundlephobia", "taille package npm", +1 | browser |
| ouvrir_w3schools | Ouvrir W3Schools | "ouvre w3schools", "va sur w3schools", "tuto w3schools", +1 | browser |
| ouvrir_python_docs | Ouvrir la documentation Python officielle | "ouvre la doc python", "doc python", "python docs", +1 | browser |
| ouvrir_rust_docs | Ouvrir la documentation Rust (The Book) | "ouvre la doc rust", "doc rust", "rust book", +1 | browser |
| ouvrir_replit | Ouvrir Replit (IDE en ligne) | "ouvre replit", "va sur replit", "lance replit", +1 | browser |
| ouvrir_codesandbox | Ouvrir CodeSandbox | "ouvre codesandbox", "va sur codesandbox", "lance codesandbox", +1 | browser |
| ouvrir_stackblitz | Ouvrir StackBlitz | "ouvre stackblitz", "va sur stackblitz", "lance stackblitz", +1 | browser |
| ouvrir_typescript_playground | Ouvrir TypeScript Playground | "ouvre typescript playground", "typescript playground", "teste du typescript", +1 | browser |
| ouvrir_rust_playground | Ouvrir Rust Playground | "ouvre rust playground", "rust playground", "teste du rust", +1 | browser |
| ouvrir_google_trends | Ouvrir Google Trends | "ouvre google trends", "google trends", "tendances google", +1 | browser |
| ouvrir_alternativeto | Ouvrir AlternativeTo (alternatives logiciels) | "ouvre alternativeto", "alternativeto", "alternative a un logiciel", +1 | browser |
| ouvrir_downdetector | Ouvrir DownDetector (status services) | "ouvre downdetector", "downdetector", "c'est en panne", +2 | browser |
| ouvrir_virustotal | Ouvrir VirusTotal (scan fichiers/URLs) | "ouvre virustotal", "virustotal", "scan un fichier", +1 | browser |
| ouvrir_haveibeenpwned | Ouvrir Have I Been Pwned (verification email) | "ouvre have i been pwned", "haveibeenpwned", "mon email a ete pirate", +2 | browser |
| chercher_crates_io | Rechercher un crate Rust | "cherche sur crates {requete}", "crate rust {requete}", "package rust {requete}" | browser |
| chercher_alternativeto | Chercher une alternative a un logiciel | "alternative a {requete}", "cherche une alternative a {requete}", "remplace {requete}" | browser |
| chercher_mdn | Rechercher sur MDN Web Docs | "cherche sur mdn {requete}", "mdn {requete}", "doc web {requete}" | browser |
| chercher_can_i_use | Verifier la compatibilite d'une feature web | "can i use {requete}", "compatibilite de {requete}", "support de {requete}" | browser |
| ouvrir_chatgpt_plugins | Ouvrir ChatGPT (avec GPTs) | "ouvre les gpts", "chatgpt gpts", "custom gpt", +1 | browser |
| ouvrir_anthropic_console | Ouvrir la console Anthropic API | "ouvre anthropic console", "console anthropic", "api anthropic", +1 | browser |
| ouvrir_openai_platform | Ouvrir la plateforme OpenAI API | "ouvre openai platform", "console openai", "api openai", +1 | browser |
| ouvrir_google_colab | Ouvrir Google Colab | "ouvre google colab", "colab", "lance colab", +2 | browser |
| ouvrir_overleaf | Ouvrir Overleaf (LaTeX en ligne) | "ouvre overleaf", "va sur overleaf", "latex en ligne", +1 | browser |
| ouvrir_whimsical | Ouvrir Whimsical (diagrams & flowcharts) | "ouvre whimsical", "whimsical", "diagrammes whimsical", +1 | browser |
| ouvrir_grammarly | Ouvrir Grammarly | "ouvre grammarly", "grammarly", "correcteur anglais", +1 | browser |
| ouvrir_remove_bg | Ouvrir Remove.bg (supprimer arriere-plan) | "ouvre remove bg", "supprime l'arriere plan", "remove background", +1 | browser |
| ouvrir_tinypng | Ouvrir TinyPNG (compression images) | "ouvre tinypng", "compresse une image", "tiny png", +1 | browser |
| ouvrir_draw_io | Ouvrir draw.io (diagrammes) | "ouvre draw io", "drawio", "diagramme en ligne", +1 | browser |
| ouvrir_notion_calendar | Ouvrir Notion Calendar | "ouvre notion calendar", "calendrier notion", "notion agenda", +1 | browser |
| ouvrir_todoist | Ouvrir Todoist (gestion de taches) | "ouvre todoist", "va sur todoist", "mes taches todoist", +1 | browser |
| ouvrir_google_finance | Ouvrir Google Finance | "ouvre google finance", "google finance", "cours de bourse", +1 | browser |
| ouvrir_yahoo_finance | Ouvrir Yahoo Finance | "ouvre yahoo finance", "yahoo finance", "yahoo bourse", +1 | browser |
| ouvrir_coindesk | Ouvrir CoinDesk (news crypto) | "ouvre coindesk", "news crypto", "coindesk", +1 | browser |
| ouvrir_meteo | Ouvrir la meteo | "ouvre la meteo", "quel temps fait il", "meteo", +2 | browser |
| chercher_google_colab | Rechercher un notebook Colab | "cherche un notebook {requete}", "colab {requete}", "notebook sur {requete}" | browser |
| chercher_perplexity | Rechercher sur Perplexity AI | "cherche sur perplexity {requete}", "perplexity {requete}", "demande a perplexity {requete}" | browser |
| chercher_google_maps | Rechercher sur Google Maps | "cherche sur maps {requete}", "maps {requete}", "trouve {requete} sur la carte", +1 | browser |

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

### Systeme Windows (463 commandes)

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
| processus_zombies | Detecter les processus qui ne repondent pas | "processus zombies", "processus bloques", "applications gelees", +2 | powershell |
| dernier_crash | Dernier crash ou erreur critique Windows | "dernier crash", "derniere erreur critique", "dernier plantage", +1 | powershell |
| temps_allumage_apps | Depuis combien de temps chaque app tourne | "duree des apps", "depuis quand les apps tournent", "temps d'execution des processus", +1 | powershell |
| taille_cache_navigateur | Taille des caches navigateur Chrome/Edge | "taille cache navigateur", "cache chrome", "cache edge", +1 | powershell |
| nettoyer_cache_navigateur | Vider les caches Chrome et Edge | "vide le cache navigateur", "nettoie le cache chrome", "clean cache web", +1 | powershell |
| nettoyer_crash_dumps | Supprimer les crash dumps Windows | "nettoie les crash dumps", "supprime les dumps", "clean crash dumps", +1 | powershell |
| nettoyer_windows_old | Taille du dossier Windows.old (ancien systeme) | "taille windows old", "windows old", "combien pese windows old", +1 | powershell |
| gpu_power_draw | Consommation electrique des GPU | "consommation gpu", "watt gpu", "puissance gpu", +2 | powershell |
| gpu_fan_speed | Vitesse des ventilateurs GPU | "ventilateurs gpu", "fans gpu", "vitesse fan gpu", +1 | powershell |
| gpu_driver_version | Version du driver NVIDIA | "version driver nvidia", "driver gpu", "nvidia driver", +1 | powershell |
| cluster_latence_detaillee | Latence detaillee de chaque noeud du cluster avec modeles | "latence detaillee cluster", "ping detaille cluster", "benchmark rapide cluster", +1 | powershell |
| installed_apps_list | Lister les applications installees | "liste les applications", "apps installees", "quelles apps j'ai", +2 | powershell |
| hotfix_history | Historique des correctifs Windows installes | "historique hotfix", "correctifs installes", "patches windows", +2 | powershell |
| scheduled_tasks_active | Taches planifiees actives | "taches planifiees actives", "scheduled tasks", "quelles taches auto", +2 | powershell |
| tpm_info | Informations sur le module TPM | "info tpm", "tpm status", "etat du tpm", +2 | powershell |
| printer_list | Imprimantes installees et leur statut | "liste les imprimantes", "imprimantes installees", "quelles imprimantes", +2 | powershell |
| startup_impact | Impact des programmes au demarrage sur le boot | "impact demarrage", "startup impact", "quoi ralentit le boot", +2 | powershell |
| system_info_detaille | Infos systeme detaillees (OS, BIOS, carte mere) | "infos systeme detaillees", "system info", "details du pc", +2 | powershell |
| ram_slots_detail | Details des barrettes RAM (type, vitesse, slots) | "details ram", "barrettes ram", "ram slots", +2 | powershell |
| cpu_details | Details du processeur (coeurs, threads, frequence) | "details cpu", "info processeur", "specs cpu", +2 | powershell |
| network_adapters_list | Adaptateurs reseau actifs et leur configuration | "adaptateurs reseau", "interfaces reseau", "network adapters", +2 | powershell |
| dns_cache_view | Voir le cache DNS local | "cache dns", "dns cache", "voir le cache dns", +2 | powershell |
| recycle_bin_size | Taille de la corbeille | "taille corbeille", "poids corbeille", "combien dans la corbeille", +2 | powershell |
| temp_folder_size | Taille du dossier temporaire | "taille du temp", "dossier temp", "poids du temp", +2 | powershell |
| last_shutdown_time | Heure du dernier arret du PC | "dernier arret", "quand le pc s'est eteint", "last shutdown", +2 | powershell |
| bluescreen_history | Historique des ecrans bleus (BSOD) | "ecrans bleus", "bsod", "bluescreen", +3 | powershell |
| disk_smart_health | Etat de sante SMART des disques | "sante disques", "smart disques", "disk health", +2 | powershell |
| firewall_rules_count | Nombre de regles firewall par profil | "regles firewall", "combien de regles pare-feu", "firewall count", +2 | powershell |
| env_variables_key | Variables d'environnement cles (PATH, TEMP, etc.) | "variables environnement", "env vars", "montre le path", +2 | powershell |
| sfc_scan | Lancer un scan d'integrite systeme (sfc /scannow) | "scan integrite", "sfc scannow", "verifie les fichiers systeme", +2 | powershell |
| dism_health_check | Verifier la sante de l'image Windows (DISM) | "dism health", "sante windows", "dism check", +2 | powershell |
| system_restore_points | Lister les points de restauration systeme | "points de restauration", "restore points", "sauvegardes systeme", +1 | powershell |
| usb_devices_list | Lister les peripheriques USB connectes | "peripheriques usb", "usb connectes", "quels usb", +2 | powershell |
| bluetooth_devices | Lister les peripheriques Bluetooth | "peripheriques bluetooth", "bluetooth connectes", "quels bluetooth", +2 | powershell |
| certificates_list | Certificats systeme installes (racine) | "certificats installes", "certificates", "liste les certificats", +2 | powershell |
| page_file_info | Configuration du fichier de pagination (swap) | "page file", "fichier de pagination", "swap windows", +2 | powershell |
| windows_features | Fonctionnalites Windows activees | "fonctionnalites windows", "features windows", "quelles features activees", +2 | powershell |
| power_plan_active | Plan d'alimentation actif et ses details | "plan alimentation", "power plan", "mode d'alimentation", +2 | powershell |
| bios_version | Version du BIOS et date | "version bios", "bios info", "quel bios", +2 | powershell |
| windows_version_detail | Version detaillee de Windows (build, edition) | "version windows", "quelle version windows", "build windows", +2 | powershell |
| network_connections_count | Nombre de connexions reseau actives par etat | "connexions reseau actives", "combien de connexions", "network connections", +2 | powershell |
| drivers_probleme | Pilotes en erreur ou problematiques | "pilotes en erreur", "drivers probleme", "drivers defaillants", +2 | powershell |
| shared_folders | Dossiers partages sur ce PC | "dossiers partages", "partages reseau", "shared folders", +2 | powershell |
| focus_app_name | Mettre le focus sur une application par son nom | "va sur {app}", "bascule sur {app}", "focus {app}", +2 | powershell |
| fermer_app_name | Fermer une application par son nom | "ferme {app}", "tue {app}", "arrete {app}", +2 | powershell |
| liste_fenetres_ouvertes | Lister toutes les fenetres ouvertes avec leur titre | "quelles fenetres sont ouvertes", "liste les fenetres", "fenetres actives", +2 | powershell |
| fenetre_toujours_visible | Rendre la fenetre active always-on-top | "toujours visible", "always on top", "epingle la fenetre", +2 | powershell |
| deplacer_fenetre_moniteur | Deplacer la fenetre active vers l'autre moniteur | "fenetre autre ecran", "deplace sur l'autre ecran", "bouge la fenetre", +2 | hotkey |
| centrer_fenetre | Centrer la fenetre active sur l'ecran | "centre la fenetre", "fenetre au centre", "center window", +1 | powershell |
| switch_audio_output | Lister et changer la sortie audio | "change la sortie audio", "switch audio", "quel sortie son", +2 | powershell |
| toggle_wifi | Activer/desactiver le WiFi | "toggle wifi", "active le wifi", "desactive le wifi", +2 | powershell |
| toggle_bluetooth | Activer/desactiver le Bluetooth | "toggle bluetooth", "active le bluetooth", "desactive le bluetooth", +2 | powershell |
| toggle_dark_mode | Basculer entre mode sombre et mode clair | "mode sombre", "dark mode", "toggle dark mode", +3 | powershell |
| taper_date | Taper la date du jour automatiquement | "tape la date", "ecris la date", "insere la date", +2 | powershell |
| taper_heure | Taper l'heure actuelle automatiquement | "tape l'heure", "ecris l'heure", "insere l'heure", +2 | powershell |
| vider_clipboard | Vider le presse-papier | "vide le presse papier", "clear clipboard", "efface le clipboard", +1 | powershell |
| dismiss_notifications | Fermer toutes les notifications Windows | "ferme les notifications", "dismiss notifications", "efface les notifs", +2 | hotkey |
| ouvrir_gestionnaire_peripheriques | Ouvrir le Gestionnaire de peripheriques | "gestionnaire de peripheriques", "device manager", "ouvre le gestionnaire peripheriques", +1 | powershell |
| ouvrir_gestionnaire_disques | Ouvrir la Gestion des disques | "gestion des disques", "disk management", "ouvre la gestion des disques", +1 | powershell |
| ouvrir_services_windows | Ouvrir la console Services Windows | "services windows", "console services", "ouvre les services", +1 | powershell |
| ouvrir_registre | Ouvrir l'editeur de registre | "editeur de registre", "regedit", "ouvre le registre", +1 | powershell |
| ouvrir_event_viewer | Ouvrir l'observateur d'evenements | "observateur d'evenements", "event viewer", "ouvre les logs windows", +1 | powershell |
| hibernation_profonde | Mettre le PC en hibernation profonde | "hiberne le pc maintenant", "hibernation profonde", "mode hibernation profonde", +1 | powershell |
| restart_bios | Redemarrer vers le BIOS/UEFI | "redemarre dans le bios", "restart bios", "acces uefi", +1 | powershell |
| taskbar_app_1 | Lancer la 1ere app epinglee dans la taskbar | "premiere app taskbar", "app 1 taskbar", "lance l'app 1", +1 | hotkey |
| taskbar_app_2 | Lancer la 2eme app epinglee dans la taskbar | "deuxieme app taskbar", "app 2 taskbar", "lance l'app 2", +1 | hotkey |
| taskbar_app_3 | Lancer la 3eme app epinglee dans la taskbar | "troisieme app taskbar", "app 3 taskbar", "lance l'app 3", +1 | hotkey |
| taskbar_app_4 | Lancer la 4eme app epinglee dans la taskbar | "quatrieme app taskbar", "app 4 taskbar", "lance l'app 4", +1 | hotkey |
| taskbar_app_5 | Lancer la 5eme app epinglee dans la taskbar | "cinquieme app taskbar", "app 5 taskbar", "lance l'app 5", +1 | hotkey |
| fenetre_autre_bureau | Deplacer la fenetre vers le bureau virtuel suivant | "fenetre bureau suivant", "deplace la fenetre sur l'autre bureau", "move to next desktop", +1 | hotkey |
| browser_retour | Page precedente dans le navigateur | "page precedente", "retour arriere", "go back", +2 | hotkey |
| browser_avancer | Page suivante dans le navigateur | "page suivante", "avance", "go forward", +1 | hotkey |
| browser_rafraichir | Rafraichir la page web | "rafraichis la page", "reload", "refresh", +2 | hotkey |
| browser_hard_refresh | Rafraichir sans cache | "hard refresh", "rafraichis sans cache", "ctrl f5", +1 | hotkey |
| browser_private | Ouvrir une fenetre de navigation privee | "navigation privee", "fenetre privee", "incognito", +2 | hotkey |
| browser_bookmark | Ajouter la page aux favoris | "ajoute aux favoris", "bookmark", "favori cette page", +1 | hotkey |
| browser_address_bar | Aller dans la barre d'adresse | "barre d'adresse", "address bar", "tape une url", +1 | hotkey |
| browser_fermer_tous_onglets | Fermer tous les onglets sauf l'actif | "ferme tous les onglets", "close all tabs", "garde juste cet onglet", +1 | powershell |
| browser_epingler_onglet | Epingler/detacher l'onglet actif | "epingle l'onglet", "pin tab", "detache l'onglet", +1 | powershell |
| texte_debut_ligne | Aller au debut de la ligne | "debut de ligne", "home", "va au debut", +1 | hotkey |
| texte_fin_ligne | Aller a la fin de la ligne | "fin de ligne", "end", "va a la fin", +1 | hotkey |
| texte_debut_document | Aller au debut du document | "debut du document", "tout en haut", "ctrl home", +1 | hotkey |
| texte_fin_document | Aller a la fin du document | "fin du document", "tout en bas", "ctrl end", +1 | hotkey |
| texte_selectionner_ligne | Selectionner la ligne entiere | "selectionne la ligne", "select line", "prends toute la ligne" | hotkey |
| texte_supprimer_ligne | Supprimer la ligne entiere (VSCode) | "supprime la ligne", "delete line", "efface la ligne", +1 | hotkey |
| texte_dupliquer_ligne | Dupliquer la ligne (VSCode) | "duplique la ligne", "duplicate line", "copie la ligne en dessous" | hotkey |
| texte_deplacer_ligne_haut | Deplacer la ligne vers le haut (VSCode) | "monte la ligne", "move line up", "ligne vers le haut" | hotkey |
| texte_deplacer_ligne_bas | Deplacer la ligne vers le bas (VSCode) | "descends la ligne", "move line down", "ligne vers le bas" | hotkey |
| vscode_palette | Ouvrir la palette de commandes VSCode | "palette de commandes", "command palette", "ctrl shift p", +1 | hotkey |
| vscode_terminal | Ouvrir/fermer le terminal VSCode | "terminal vscode", "ouvre le terminal intergre", "toggle terminal", +1 | hotkey |
| vscode_sidebar | Afficher/masquer la sidebar VSCode | "sidebar vscode", "panneau lateral", "toggle sidebar", +2 | hotkey |
| vscode_go_to_file | Rechercher et ouvrir un fichier dans VSCode | "ouvre un fichier vscode", "go to file", "ctrl p", +1 | hotkey |
| vscode_go_to_line | Aller a une ligne dans VSCode | "va a la ligne", "go to line", "ctrl g", +1 | hotkey |
| vscode_split_editor | Diviser l'editeur VSCode en deux | "divise l'editeur", "split editor", "editeur cote a cote", +1 | hotkey |
| vscode_close_all | Fermer tous les fichiers ouverts dans VSCode | "ferme tous les fichiers vscode", "close all tabs vscode", "nettoie vscode", +1 | hotkey |
| explorer_dossier_parent | Remonter au dossier parent dans l'Explorateur | "dossier parent", "remonte d'un dossier", "go up folder", +1 | hotkey |
| explorer_nouveau_dossier | Creer un nouveau dossier dans l'Explorateur | "nouveau dossier", "cree un dossier", "new folder", +1 | hotkey |
| explorer_afficher_caches | Afficher les fichiers caches dans l'Explorateur | "montre les fichiers caches", "fichiers caches", "show hidden files", +1 | powershell |
| explorer_masquer_caches | Masquer les fichiers caches | "cache les fichiers caches", "masque les fichiers invisibles", "hide hidden files", +1 | powershell |
| scroll_haut | Scroller vers le haut | "scroll up", "monte la page", "scrolle vers le haut", +2 | hotkey |
| scroll_bas | Scroller vers le bas | "scroll down", "descends la page", "scrolle vers le bas", +2 | hotkey |
| page_haut | Page precedente (Page Up) | "page up", "page precedente", "monte d'une page", +2 | hotkey |
| page_bas | Page suivante (Page Down) | "page down", "page suivante", "descends d'une page", +2 | hotkey |
| scroll_rapide_haut | Scroller rapidement vers le haut (5 pages) | "scroll rapide haut", "monte vite", "remonte rapidement", +1 | hotkey |
| scroll_rapide_bas | Scroller rapidement vers le bas (5 pages) | "scroll rapide bas", "descends vite", "descends rapidement", +1 | hotkey |
| snap_gauche | Ancrer la fenetre a gauche (moitie ecran) | "fenetre a gauche", "snap left", "colle a gauche", +2 | hotkey |
| snap_droite | Ancrer la fenetre a droite (moitie ecran) | "fenetre a droite", "snap right", "colle a droite", +2 | hotkey |
| snap_haut_gauche | Ancrer la fenetre en haut a gauche (quart ecran) | "fenetre haut gauche", "snap top left", "quart haut gauche", +1 | hotkey |
| snap_bas_gauche | Ancrer la fenetre en bas a gauche (quart ecran) | "fenetre bas gauche", "snap bottom left", "quart bas gauche", +1 | hotkey |
| snap_haut_droite | Ancrer la fenetre en haut a droite (quart ecran) | "fenetre haut droite", "snap top right", "quart haut droite", +1 | hotkey |
| snap_bas_droite | Ancrer la fenetre en bas a droite (quart ecran) | "fenetre bas droite", "snap bottom right", "quart bas droite", +1 | hotkey |
| restaurer_fenetre | Restaurer la fenetre a sa taille precedente | "restaure la fenetre", "taille normale", "restore window", +2 | hotkey |
| onglet_1 | Aller au 1er onglet | "onglet 1", "premier onglet", "tab 1", +1 | hotkey |
| onglet_2 | Aller au 2eme onglet | "onglet 2", "deuxieme onglet", "tab 2", +1 | hotkey |
| onglet_3 | Aller au 3eme onglet | "onglet 3", "troisieme onglet", "tab 3", +1 | hotkey |
| onglet_4 | Aller au 4eme onglet | "onglet 4", "quatrieme onglet", "tab 4", +1 | hotkey |
| onglet_5 | Aller au 5eme onglet | "onglet 5", "cinquieme onglet", "tab 5", +1 | hotkey |
| onglet_dernier | Aller au dernier onglet | "dernier onglet", "last tab", "va au dernier onglet", +1 | hotkey |
| nouvel_onglet_vierge | Ouvrir un nouvel onglet vierge | "nouvel onglet vierge", "new tab blank", "ouvre un onglet vide", +1 | hotkey |
| mute_onglet | Couper le son de l'onglet (clic droit requis) | "mute l'onglet", "coupe le son de l'onglet", "silence onglet", +1 | powershell |
| browser_devtools | Ouvrir les DevTools du navigateur | "ouvre les devtools", "developer tools", "ouvre la console", +2 | hotkey |
| browser_devtools_console | Ouvrir la console DevTools directement | "ouvre la console navigateur", "console chrome", "console edge", +2 | hotkey |
| browser_source_view | Voir le code source de la page | "voir le code source", "view source", "source de la page", +2 | hotkey |
| curseur_mot_gauche | Deplacer le curseur d'un mot a gauche | "mot precedent", "word left", "recule d'un mot", +1 | hotkey |
| curseur_mot_droite | Deplacer le curseur d'un mot a droite | "mot suivant", "word right", "avance d'un mot", +1 | hotkey |
| selectionner_mot | Selectionner le mot sous le curseur | "selectionne le mot", "select word", "prends le mot", +1 | hotkey |
| selectionner_mot_gauche | Etendre la selection d'un mot a gauche | "selection mot gauche", "select word left", "etends la selection a gauche", +1 | hotkey |
| selectionner_mot_droite | Etendre la selection d'un mot a droite | "selection mot droite", "select word right", "etends la selection a droite", +1 | hotkey |
| selectionner_tout | Selectionner tout le contenu | "selectionne tout", "select all", "tout selectionner", +2 | hotkey |
| copier_texte | Copier la selection | "copie", "copy", "copier", +2 | hotkey |
| couper_texte | Couper la selection | "coupe", "cut", "couper", +2 | hotkey |
| coller_texte | Coller le contenu du presse-papier | "colle", "paste", "coller", +2 | hotkey |
| annuler_action | Annuler la derniere action (undo) | "annule", "undo", "ctrl z", +2 | hotkey |
| retablir_action | Retablir l'action annulee (redo) | "retablis", "redo", "ctrl y", +2 | hotkey |
| rechercher_dans_page | Ouvrir la recherche dans la page | "cherche dans la page", "find", "ctrl f", +2 | hotkey |
| rechercher_et_remplacer | Ouvrir rechercher et remplacer | "cherche et remplace", "find replace", "ctrl h", +1 | hotkey |
| supprimer_mot_gauche | Supprimer le mot precedent | "supprime le mot precedent", "delete word left", "efface le mot avant", +1 | hotkey |
| supprimer_mot_droite | Supprimer le mot suivant | "supprime le mot suivant", "delete word right", "efface le mot apres", +1 | hotkey |
| menu_contextuel | Ouvrir le menu contextuel (clic droit) | "clic droit", "menu contextuel", "right click", +2 | hotkey |
| valider_entree | Appuyer sur Entree (valider) | "entree", "valide", "enter", +3 | hotkey |
| echapper | Appuyer sur Echap (annuler/fermer) | "echap", "escape", "annule", +2 | hotkey |
| tabulation | Naviguer au champ suivant (Tab) | "tab", "champ suivant", "element suivant", +2 | hotkey |
| tabulation_inverse | Naviguer au champ precedent (Shift+Tab) | "shift tab", "champ precedent", "element precedent", +2 | hotkey |
| ouvrir_selection | Ouvrir/activer l'element selectionne (Espace) | "espace", "active", "coche", +2 | hotkey |
| media_suivant | Piste suivante | "piste suivante", "next track", "chanson suivante", +2 | powershell |
| media_precedent | Piste precedente | "piste precedente", "previous track", "chanson precedente", +2 | powershell |
| screenshot_complet | Capture d'ecran complete (dans presse-papier) | "screenshot", "capture d'ecran", "print screen", +2 | hotkey |
| screenshot_fenetre | Capture d'ecran de la fenetre active | "screenshot fenetre", "capture la fenetre", "alt print screen", +1 | hotkey |
| snip_screen | Outil de capture d'ecran (selection libre) | "snip", "outil capture", "snipping tool", +2 | hotkey |
| task_view | Ouvrir la vue des taches (Task View) | "task view", "vue des taches", "montre les fenetres", +2 | hotkey |
| creer_bureau_virtuel | Creer un nouveau bureau virtuel | "nouveau bureau virtuel", "cree un bureau", "new desktop", +1 | hotkey |
| fermer_bureau_virtuel | Fermer le bureau virtuel actuel | "ferme le bureau virtuel", "supprime ce bureau", "close desktop", +1 | hotkey |
| zoom_in | Zoomer (agrandir) | "zoom in", "zoome", "agrandis", +3 | hotkey |
| zoom_out | Dezoomer (reduire) | "zoom out", "dezoome", "reduis", +3 | hotkey |
| switch_app | Basculer entre les applications (Alt+Tab) | "switch app", "alt tab", "change d'application", +2 | hotkey |
| switch_app_inverse | Basculer en arriere entre les apps | "app precedente alt tab", "reverse alt tab", "reviens a l'app precedente", +1 | hotkey |
| ouvrir_start_menu | Ouvrir le menu Demarrer | "ouvre le menu demarrer", "start menu", "menu demarrer", +2 | hotkey |
| ouvrir_centre_notifications | Ouvrir le centre de notifications | "ouvre les notifications", "centre de notifications", "notification center", +2 | hotkey |
| ouvrir_clipboard_history | Ouvrir l'historique du presse-papier | "historique presse papier", "clipboard history", "win v", +2 | hotkey |
| ouvrir_emojis_clavier | Ouvrir le panneau emojis | "panneau emojis", "emoji keyboard", "win point", +2 | hotkey |
| plein_ecran_toggle | Basculer en plein ecran (F11) | "plein ecran", "fullscreen", "f11", +2 | hotkey |
| renommer_fichier | Renommer le fichier/dossier selectionne (F2) | "renomme", "rename", "f2", +2 | hotkey |
| supprimer_selection | Supprimer la selection | "supprime", "delete", "supprimer", +2 | hotkey |
| ouvrir_proprietes | Voir les proprietes du fichier selectionne | "proprietes", "properties", "alt enter", +2 | hotkey |
| fermer_fenetre_active | Fermer la fenetre/app active (Alt+F4) | "ferme la fenetre", "close window", "alt f4", +2 | hotkey |
| ouvrir_parametres_systeme | Ouvrir les Parametres Windows | "ouvre les parametres", "parametres windows", "settings", +2 | hotkey |
| ouvrir_centre_accessibilite | Ouvrir les options d'accessibilite | "accessibilite", "options accessibilite", "ease of access", +2 | hotkey |
| dictee_vocale_windows | Activer la dictee vocale Windows | "dictee vocale", "voice typing", "win h", +2 | hotkey |
| projection_ecran | Options de projection ecran (etendre, dupliquer) | "projection ecran", "project screen", "win p", +2 | hotkey |
| connecter_appareil | Ouvrir le panneau de connexion d'appareils (Cast) | "connecter un appareil", "cast screen", "win k", +2 | hotkey |
| ouvrir_game_bar_direct | Ouvrir la Xbox Game Bar | "game bar directe", "xbox game bar", "win g direct", +1 | hotkey |

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

### Developpement & Outils (126 commandes)

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
| git_blame_file | Git blame sur un fichier | "git blame de {fichier}", "blame {fichier}", "qui a modifie {fichier}", +1 | powershell |
| git_clean_branches | Nettoyer les branches git mergees | "nettoie les branches", "clean branches", "supprime les branches mergees", +1 | powershell |
| git_contributors | Lister les contributeurs du projet | "contributeurs git", "qui a contribue", "git contributors", +1 | powershell |
| git_file_history | Historique d'un fichier | "historique du fichier {fichier}", "git log de {fichier}", "modifications de {fichier}" | powershell |
| git_undo_last | Annuler le dernier commit (soft reset) | "annule le dernier commit", "undo last commit", "git undo", +1 | powershell |
| npm_audit | Audit de securite NPM | "npm audit", "audit securite npm", "vulnerabilites npm", +1 | powershell |
| npm_outdated | Packages NPM obsoletes | "npm outdated", "packages npm a jour", "quels packages npm a mettre a jour", +1 | powershell |
| pip_outdated | Packages Python obsoletes | "pip outdated", "packages python a mettre a jour", "quels packages python perime" | powershell |
| python_repl | Lancer un REPL Python | "lance python", "python repl", "ouvre python", +1 | powershell |
| kill_port | Tuer le processus sur un port specifique | "tue le port {port}", "kill port {port}", "libere le port {port}", +1 | powershell |
| qui_ecoute_port | Quel processus ecoute sur un port | "qui ecoute sur le port {port}", "quel process sur {port}", "port {port} utilise par", +1 | powershell |
| ports_dev_status | Statut des ports dev courants (3000, 5173, 8080, 8000, 9742) | "statut des ports dev", "ports dev", "quels ports dev tournent", +1 | powershell |
| ollama_vram_detail | Detail VRAM utilisee par chaque modele Ollama | "vram ollama detail", "ollama vram", "memoire ollama", +1 | powershell |
| ollama_stop_all | Decharger tous les modeles Ollama de la VRAM | "decharge tous les modeles ollama", "ollama stop all", "libere la vram ollama", +1 | powershell |
| git_reflog | Voir le reflog git (historique complet) | "git reflog", "reflog", "historique complet git", +1 | powershell |
| git_tag_list | Lister les tags git | "tags git", "git tags", "liste les tags", +2 | powershell |
| git_search_commits | Rechercher dans les messages de commit | "cherche dans les commits {requete}", "git search {requete}", "commit contenant {requete}", +1 | powershell |
| git_repo_size | Taille du depot git | "taille du repo git", "poids du git", "git size", +1 | powershell |
| git_stash_list | Lister les stash git | "liste les stash", "git stash list", "stash en attente", +1 | powershell |
| git_diff_staged | Voir les modifications stagees (pret a commit) | "diff staged", "git diff staged", "quoi va etre commite", +1 | powershell |
| docker_images_list | Lister les images Docker locales | "images docker", "docker images", "liste les images docker", +1 | powershell |
| docker_volumes | Lister les volumes Docker | "volumes docker", "docker volumes", "liste les volumes docker", +1 | powershell |
| docker_networks | Lister les reseaux Docker | "reseaux docker", "docker networks", "liste les networks docker", +1 | powershell |
| docker_disk_usage | Espace disque utilise par Docker | "espace docker", "docker disk usage", "combien pese docker", +1 | powershell |
| wsl_status | Statut de WSL et distributions installees | "statut wsl", "wsl status", "distributions wsl", +2 | powershell |
| winget_search | Rechercher un package via winget | "winget search {requete}", "cherche {requete} sur winget", "package winget {requete}", +1 | powershell |
| winget_list_installed | Lister les apps installees via winget | "winget list", "apps winget", "inventaire winget", +1 | powershell |
| winget_upgrade_all | Mettre a jour toutes les apps via winget | "winget upgrade all", "mets a jour tout winget", "update tout winget", +1 | powershell |
| code_extensions_list | Lister les extensions VSCode installees | "extensions vscode", "liste les extensions", "vscode extensions", +1 | powershell |
| code_install_ext | Installer une extension VSCode | "installe l'extension {ext}", "vscode install {ext}", "ajoute l'extension {ext}", +1 | powershell |
| ssh_keys_list | Lister les cles SSH | "cles ssh", "ssh keys", "liste les cles ssh", +1 | powershell |
| npm_cache_clean | Nettoyer le cache NPM | "nettoie le cache npm", "npm cache clean", "clean npm cache", +1 | powershell |
| uv_pip_tree | Arbre de dependances Python du projet | "arbre de dependances", "pip tree", "dependency tree", +2 | powershell |
| pip_show_package | Details d'un package Python installe | "details du package {package}", "pip show {package}", "info sur {package}", +1 | powershell |
| turbo_imports | Imports utilises dans le projet turbo | "imports du projet", "quels imports", "dependances importees", +1 | powershell |
| python_format_check | Verifier le formatage Python avec ruff format | "verifie le formatage", "ruff format check", "check formatting", +1 | powershell |
| python_type_check | Verifier les types Python (pyright/mypy) | "verifie les types", "type check", "pyright check", +2 | powershell |
| curl_test_endpoint | Tester un endpoint HTTP | "teste l'endpoint {url}", "curl {url}", "ping http {url}", +1 | powershell |
| n8n_workflows_list | Lister les workflows n8n actifs | "workflows n8n", "liste les workflows", "n8n actifs", +1 | powershell |
| git_worktree_list | Lister les worktrees git | "worktrees git", "git worktrees", "liste les worktrees", +1 | powershell |
| git_submodule_status | Statut des submodules git | "submodules git", "git submodules", "etat des submodules", +1 | powershell |
| git_cherry_unpicked | Commits non cherry-picked entre branches | "git cherry", "commits non picks", "cherry pick restant", +1 | powershell |
| git_branch_age | Age de chaque branche git | "age des branches", "branches vieilles", "quand les branches ont ete crees", +1 | powershell |
| git_commit_stats | Statistiques de commits (par jour/semaine) | "stats commits", "frequence commits", "git stats", +1 | powershell |
| docker_compose_up | Docker compose up (demarrer les services) | "docker compose up", "lance les conteneurs", "demarre docker compose", +1 | powershell |
| docker_compose_down | Docker compose down (arreter les services) | "docker compose down", "arrete les conteneurs", "stop docker compose", +1 | powershell |
| docker_compose_logs | Voir les logs Docker Compose | "logs docker compose", "compose logs", "docker compose logs", +1 | powershell |
| docker_compose_ps | Statut des services Docker Compose | "services docker compose", "compose ps", "docker compose status", +1 | powershell |
| uv_cache_clean | Nettoyer le cache uv | "nettoie le cache uv", "uv cache clean", "clean cache python", +1 | powershell |
| uv_pip_install | Installer un package Python via uv | "installe {package} python", "uv pip install {package}", "ajoute {package}", +1 | powershell |
| turbo_test_file | Lancer un fichier de test specifique | "teste le fichier {fichier}", "pytest {fichier}", "lance le test {fichier}", +1 | powershell |
| turbo_coverage | Couverture de tests du projet turbo | "coverage turbo", "couverture de tests", "test coverage", +2 | powershell |
| process_tree | Arbre des processus actifs | "arbre des processus", "process tree", "processus parent enfant", +1 | powershell |
| openssl_version | Version d'OpenSSL | "version openssl", "openssl version", "quelle version ssl" | powershell |
| git_version | Version de Git | "version git", "git version", "quelle version git" | powershell |
| cuda_version | Version de CUDA installee | "version cuda", "cuda version", "quelle version cuda", +1 | powershell |
| powershell_version | Version de PowerShell | "version powershell", "powershell version", "quelle version powershell" | powershell |
| dotnet_version | Versions de .NET installees | "version dotnet", "dotnet version", "quelle version net", +1 | powershell |
| turbo_skills_count | Compter les skills et commandes vocales du projet | "combien de skills", "nombre de commandes vocales", "inventaire skills", +1 | powershell |
| turbo_find_duplicates | Detecter les commandes vocales en doublon | "cherche les doublons", "duplicates commands", "commandes en double", +1 | powershell |
| turbo_generate_docs | Regenerer la documentation des commandes vocales | "regenere la doc", "update la doc vocale", "genere la doc commandes", +1 | powershell |
| turbo_generate_readme | Regenerer la section commandes du README | "regenere le readme", "update le readme", "genere le readme commandes", +1 | powershell |
| check_all_versions | Toutes les versions d'outils installes | "toutes les versions", "all versions", "inventaire outils", +1 | powershell |
| env_check_paths | Verifier que les outils essentiels sont dans le PATH | "check le path", "outils disponibles", "verifier le path", +1 | powershell |
| disk_space_summary | Resume espace disque pour le dev | "espace disque dev", "combien de place pour coder", "place restante", +1 | powershell |
| git_today | Commits d'aujourd'hui | "commits du jour", "git today", "quoi de neuf aujourd'hui", +1 | powershell |
| git_this_week | Commits de cette semaine | "commits de la semaine", "git this week", "cette semaine en git", +1 | powershell |
| git_push_turbo | Pusher les commits du projet turbo | "push turbo", "git push", "pousse le code", +1 | powershell |
| git_pull_turbo | Puller les commits du projet turbo | "pull turbo", "git pull", "recupere les commits", +1 | powershell |

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
