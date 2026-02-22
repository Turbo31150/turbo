# Commandes Vocales JARVIS - Reference Complete

> Mise a jour automatique: 2026-02-22 | Voice Pipeline v2

**1597 commandes** au total, dont **259 pipelines** multi-etapes, reparties en **14 categories**.

| Categorie | Nombre |
|-----------|--------|
| Systeme Windows | 640 |
| Navigation Web | 297 |
| Pipelines Multi-Etapes | 259 |
| Developpement & Outils | 241 |
| Fichiers & Documents | 47 |
| Applications | 23 |
| Trading & IA | 19 |
| Fenetres Windows | 13 |
| Presse-papier & Saisie | 13 |
| Controle JARVIS | 12 |
| Launchers JARVIS | 12 |
| Accessibilite | 10 |
| Controle Media | 7 |
| Saisie & Texte | 4 |
| **TOTAL** | **1597** |

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
| sim_diag_reseau_complet | "diagnostic reseau complet" | ping 8.8.8.8 -n 3 | Select-String 'Moyenne|Average... > ipconfig /flushdns; nslookup google.com 2>&1 | Sel... > trace... |
| sim_diag_wifi | "probleme wifi complet" | netsh wlan show interfaces | Select-String 'SSID|S... > ping 192.168.1.1 -n 3 | Select-String 'Moyenne|Ave... > ping ... |
| sim_diag_cluster_deep | "diagnostic cluster profond" | $m2 = try{(Invoke-WebRequest -Uri 'http://192.168.... > nvidia-smi --query-gpu=name,temperature.gpu,utiliz... > (Invo... |
| sim_audit_securite | "audit securite complet" | Get-NetTCPConnection -State Listen | Group-Object ... > Get-NetTCPConnection -State Established | Where Re... > $rdp ... |
| sim_hardening_check | "check hardening" | Get-NetFirewallProfile | Select Name, Enabled | Out-String > $uac = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft... > ... |
| sim_audit_mots_de_passe | "audit mots de passe" | net accounts 2>&1 | Out-String > Get-LocalUser | Select Name, Enabled, PasswordRequ... > "Audit mots de passe termine" |
| sim_new_project_python | "nouveau projet python" | $name = 'new_project_' + (Get-Date -Format 'yyyyMM... > cd "F:\BUREAU\$((Get-ChildItem F:\BUREAU -Director... > Ouvri... |
| sim_new_project_node | "nouveau projet node" | $name = 'node_project_' + (Get-Date -Format 'yyyyM... > cd "F:\BUREAU\$((Get-ChildItem F:\BUREAU -Director... > Ouvri... |
| sim_clone_and_setup | "clone et setup {repo}" | cd F:\BUREAU; git clone '{repo}' 2>&1 | Out-String > pause 2s > Ouvrir code > pause 2s > "Repo clone et ouvert dans V... |
| sim_grand_nettoyage_disque | "grand nettoyage du disque" | $s1 = (Get-ChildItem $env:TEMP -Recurse -File -Err... > Remove-Item "$env:LOCALAPPDATA\Google\Chrome\User ... > Clear... (confirm) |
| sim_archive_vieux_projets | "archive les vieux projets" | $old = Get-ChildItem F:\BUREAU -Directory | Where ... |
| sim_scan_fichiers_orphelins | "scan fichiers orphelins" | "=== Fichiers > 100MB ==="; Get-ChildItem F:\BUREA... > "=== Doublons par nom ==="; Get-ChildItem F:\BUREA... > "=== ... |
| sim_design_review | "review design complet" | Raccourci: win+shift+m > pause 3s > Raccourci: win+shift+c > pause 3s > Raccourci: win+shift+t > pause 3s > Raccourci... |
| sim_layout_productif | "layout productif" | Ouvrir code > pause 2s > Raccourci: win+left > pause 1s > Web: http://127.0.0.1:8080 > pause 2s > Raccourci: win+righ... |
| sim_copier_texte_image | "copie le texte de l'image" | Raccourci: win+shift+t > pause 5s > $clip = Get-Clipboard -ErrorAction SilentlyContinu... |
| sim_db_health_check | "health check des bases" | $j = (Get-Item F:\BUREAU\turbo\data\jarvis.db -Err... > sqlite3 F:\BUREAU\turbo\data\jarvis.db 'PRAGMA int... > sqlit... |
| sim_db_backup | "backup les bases" | $d = Get-Date -Format 'yyyy-MM-dd_HHmm'; Copy-Item... |
| sim_db_stats | "stats des bases" | sqlite3 F:\BUREAU\turbo\data\jarvis.db '.tables' 2... > sqlite3 F:\BUREAU\turbo\data\jarvis.db 'SELECT "sk... > sqlit... |
| sim_docker_full_status | "status docker complet" | docker ps --format 'table {{.Names}}\t{{.Status}}\... > docker images --format 'table {{.Repository}}\t{{.... > docke... |
| sim_docker_cleanup | "nettoie docker a fond" | docker container prune -f 2>&1 | Out-String > docker image prune -a -f 2>&1 | Out-String > docker volume prune -f 2>&... (confirm) |
| sim_docker_restart_all | "redemarre docker" | docker restart $(docker ps -q) 2>&1 | Out-String > pause 3s > docker ps --format 'table {{.Names}}\t{{.Status}}'... >... |
| sim_code_review_prep | "prepare la code review" | cd F:\BUREAU\turbo; git log --oneline -5 2>&1 | Out-String > cd F:\BUREAU\turbo; git diff --stat HEAD~3 2>&1 | Out-St... |
| sim_code_review_split | "layout review" | Ouvrir code > pause 2s > Raccourci: win+left > pause 1s > Web: https://github.com/Turbo31150/turbo > pause 2s > Racco... |
| sim_learn_topic | "session apprentissage {topic}" | Web: https://www.youtube.com/results?search_query={topic}+tutorial > pause 2s > Web: https://www.google.com/search?q=... |
| sim_learn_python | "apprends moi python" | Web: https://docs.python.org/3/tutorial/ > pause 2s > Web: https://www.freecodecamp.org/learn/scientific-computing-wi... |
| sim_learn_rust | "apprends moi rust" | Web: https://doc.rust-lang.org/book/ > pause 2s > Web: https://play.rust-lang.org/ > pause 1s > "Session Rust ouverte... |
| sim_layout_4_quadrants | "4 quadrants" | Ouvrir code > pause 2s > Raccourci: win+left > Raccourci: win+up > pause 1s > Ouvrir wt > pause 1s > Raccourci: win+l... |
| sim_layout_trading_full | "layout trading complet" | Web: https://futures.mexc.com > pause 3s > Raccourci: win+left > pause 1s > Web: https://www.coingecko.com > pause 2s... |
| sim_layout_recherche | "layout recherche" | Web: https://www.perplexity.ai > pause 2s > Raccourci: win+left > pause 1s > Web: https://claude.ai > pause 2s > Racc... |
| sim_remote_work_start | "mode teletravail" | MinimizeAll > pause 1s > Ouvrir code > pause 2s > Raccourci: win+left > pause 1s > Web: https://mail.google.com > pau... |
| sim_standup_meeting | "prepare le standup" | cd F:\BUREAU\turbo; "=== HIER ==="; git log --sinc... > cd F:\BUREAU\turbo; "=== AUJOURD'HUI ==="; git log... > cd F:... |
| sim_crypto_research | "recherche crypto complete" | Web: https://www.coingecko.com > pause 2s > Web: https://www.coindesk.com > pause 2s > Web: https://etherscan.io > pa... |
| sim_trading_session | "session trading complete" | Web: https://futures.mexc.com > pause 3s > Web: https://www.tradingview.com > pause 2s > Ouvrir wt > pause 1s > cd F:... |
| sim_post_crash_recovery | "recovery apres crash" | Get-PhysicalDisk | Select FriendlyName, HealthStat... > Get-WinEvent -FilterHashtable @{LogName='System';L... > Get-S... |
| sim_repair_system | "repare le systeme" | DISM /Online /Cleanup-Image /CheckHealth 2>&1 | Out-String > sfc /verifyonly 2>&1 | Select -Last 3 | Out-String > "Ve... (confirm) |
| sim_fullstack_build | "build complet du projet" | cd F:\BUREAU\turbo; & 'C:\Users\franc\.local\bin\u... > cd F:\BUREAU\turbo; & 'C:\Users\franc\.local\bin\u... > "Buil... |
| sim_deploy_check | "check avant deploiement" | cd F:\BUREAU\turbo; git status -sb 2>&1 | Out-String > cd F:\BUREAU\turbo; & 'C:\Users\franc\.local\bin\u... > cd F:\... |
| sim_git_release | "fais une release" | cd F:\BUREAU\turbo; $v = git describe --tags --abb... > cd F:\BUREAU\turbo; git log --oneline -10 2>&1 | Out-String >... |
| sim_api_test_session | "session test api" | Web: https://web.postman.co > pause 2s > Web: https://httpbin.org > pause 1s > Ouvrir wt > "Session API testing ouver... |
| sim_api_endpoints_check | "check tous les endpoints" | try{$r=Invoke-WebRequest http://127.0.0.1:11434/ap... > try{$r=Invoke-WebRequest http://192.168.1.26:1234/... > try{$... |
| sim_social_all | "ouvre tous les reseaux sociaux" | Web: https://x.com > pause 1s > Web: https://www.linkedin.com > pause 1s > Web: https://www.instagram.com > pause 1s ... |
| sim_content_creation | "setup creation contenu" | Web: https://www.canva.com > pause 2s > Web: https://unsplash.com > pause 1s > Ouvrir notepad > "Setup creation de co... |
| sim_design_session | "session design" | Web: https://www.figma.com > pause 2s > Web: https://dribbble.com > pause 1s > Web: https://coolors.co > pause 1s > W... |
| sim_ui_inspiration | "inspiration ui" | Web: https://dribbble.com > pause 1s > Web: https://www.behance.net > pause 1s > Web: https://www.awwwards.com > "3 s... |
| sim_optimize_full | "optimise le systeme" | $tmp = (Get-ChildItem $env:TEMP -Recurse -ErrorAct... > Get-CimInstance Win32_StartupCommand | Select Name... > Get-S... |
| sim_cleanup_aggressive | "nettoyage agressif" | Remove-Item $env:TEMP\* -Recurse -Force -ErrorActi... > Remove-Item "$env:LOCALAPPDATA\Microsoft\Windows\E... > Clear... (confirm) |
| sim_learn_coding | "session apprentissage code" | Web: https://www.youtube.com > pause 1s > Web: https://developer.mozilla.org > pause 1s > Web: https://www.w3schools.... |
| sim_learn_ai | "session apprentissage ia" | Web: https://huggingface.co/learn > pause 1s > Web: https://arxiv.org/list/cs.AI/recent > pause 1s > Web: https://www... |
| sim_pomodoro_25 | "lance un pomodoro" | Add-Type -AssemblyName System.Speech; (New-Object ... > Settings > Start-Sleep -Seconds 1500; Add-Type -AssemblyName ... |
| sim_backup_turbo | "backup le projet" | cd F:\BUREAU\turbo; git bundle create F:\BUREAU\tu... > Compress-Archive -Path F:\BUREAU\turbo\data -Desti... > "Back... |
| sim_backup_verify | "verifie les backups" | Get-ChildItem F:\BUREAU\turbo_backup_*.bundle -Err... > Get-ChildItem F:\BUREAU\turbo_data_backup_*.zip -E... > "Veri... |
| sim_morning_routine | "routine du matin" | Web: https://www.meteofrance.com > pause 1s > Web: https://news.google.com > pause 1s > Web: https://mail.google.com ... |
| sim_evening_shutdown | "routine du soir" | cd F:\BUREAU\turbo; git status -sb 2>&1 | Out-String > cd F:\BUREAU\turbo; git stash 2>&1 | Out-String > Remove-Item ... |
| sim_freelance_setup | "mode freelance" | Web: https://www.malt.fr > pause 1s > Web: https://mail.google.com > pause 1s > Ouvrir wt > "Setup freelance pret — M... |
| sim_client_meeting | "prepare le meeting client" | Ouvrir ms-teams > pause 3s > Ouvrir notepad > pause 1s > cd F:\BUREAU\turbo; git log --oneline -5 2>&1 | Out-String >... |
| sim_db_backup_all | "backup toutes les bases" | $d=Get-Date -Format yyyyMMdd; Copy-Item F:\BUREAU\... > $d=Get-Date -Format yyyyMMdd; Copy-Item F:\BUREAU\... > "Back... |
| sim_security_full_audit | "audit securite complet" | Get-NetTCPConnection -State Listen | Select -First... > Get-NetFirewallProfile | Select Name, Enabled | Fo... > Get-L... |
| sim_security_network | "audit reseau" | Get-NetTCPConnection | Where { $_.State -eq 'Estab... > Get-DnsClientCache | Select -First 15 Entry, Data ... > arp -... |
| sim_benchmark_system | "benchmark systeme" | $cpu = Get-CimInstance Win32_Processor; "CPU: $($c... > $ram = Get-CimInstance Win32_OperatingSystem; "RAM... > Get-P... |
| sim_benchmark_cluster | "benchmark cluster" | $sw=[Diagnostics.Stopwatch]::StartNew(); try{Invok... > $sw=[Diagnostics.Stopwatch]::StartNew(); try{Invok... > $sw=[... |
| sim_doc_session | "session documentation" | code F:\BUREAU\turbo\docs 2>$null > pause 2s > Web: https://devdocs.io > pause 1s > Web: https://markdownlivepreview.... |
| sim_doc_generate | "genere toute la doc" | cd F:\BUREAU\turbo; & 'C:\Users\franc\.local\bin\u... > cd F:\BUREAU\turbo; & 'C:\Users\franc\.local\bin\u... > "Docu... |
| sim_ai_workspace | "workspace ia" | Web: https://huggingface.co > pause 1s > Web: https://arxiv.org/list/cs.AI/recent > pause 1s > Ouvrir wt > pause 1s >... |
| sim_model_eval | "evalue les modeles" | cd F:\BUREAU\turbo; & 'C:\Users\franc\.local\bin\u... > "Evaluation modeles terminee — voir data/benchmark... |
| sim_home_office | "mode bureau" | Ouvrir ms-teams > pause 2s > Web: https://mail.google.com > pause 1s > Ouvrir spotify > pause 1s > try{Invoke-WebRequ... |
| sim_focus_deep_work | "mode deep work" | MinimizeAll > Settings > pause 1s > Ouvrir spotify > "Deep work active — Focus Assist ON, 90 minutes de... |
| sim_weekend_chill | "mode weekend" | Web: https://www.netflix.com > pause 1s > Ouvrir spotify > pause 1s > Web: https://www.ubereats.com > powercfg /setac... |
| sim_movie_night | "soiree film" | MinimizeAll > pause 1s > Web: https://www.netflix.com > Settings > "Soiree film prete — Netflix + Night Light" |

---

## Listing Complet par Categorie

### Navigation Web (297 commandes)

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
| ouvrir_impots | Ouvrir impots.gouv.fr | "ouvre les impots", "impots gouv", "va sur les impots", +2 | browser |
| ouvrir_ameli | Ouvrir Ameli (Assurance Maladie) | "ouvre ameli", "assurance maladie", "va sur ameli", +2 | browser |
| ouvrir_caf | Ouvrir la CAF | "ouvre la caf", "allocations familiales", "va sur la caf", +1 | browser |
| ouvrir_sncf | Ouvrir SNCF Connect (trains) | "ouvre sncf", "billets de train", "va sur sncf", +2 | browser |
| ouvrir_doctolib | Ouvrir Doctolib (rendez-vous medical) | "ouvre doctolib", "prends un rdv medical", "va sur doctolib", +2 | browser |
| ouvrir_la_poste | Ouvrir La Poste (suivi colis) | "ouvre la poste", "suivi colis", "va sur la poste", +2 | browser |
| ouvrir_pole_emploi | Ouvrir France Travail (ex Pole Emploi) | "ouvre pole emploi", "france travail", "va sur pole emploi", +1 | browser |
| ouvrir_service_public | Ouvrir Service-Public.fr | "service public", "demarches administratives", "va sur service public", +1 | browser |
| ouvrir_fnac | Ouvrir Fnac.com | "ouvre la fnac", "va sur la fnac", "fnac en ligne", +1 | browser |
| ouvrir_cdiscount | Ouvrir Cdiscount | "ouvre cdiscount", "va sur cdiscount", "cdiscount", +1 | browser |
| ouvrir_amazon_fr | Ouvrir Amazon France | "ouvre amazon france", "amazon fr", "va sur amazon", +1 | browser |
| ouvrir_boursorama | Ouvrir Boursorama (banque/bourse) | "ouvre boursorama", "va sur boursorama", "banque en ligne", +1 | browser |
| ouvrir_free_mobile | Ouvrir Free Mobile (espace client) | "ouvre free", "espace client free", "va sur free", +1 | browser |
| ouvrir_edf | Ouvrir EDF (electricite) | "ouvre edf", "mon compte edf", "facture electricite", +1 | browser |
| ouvrir_aws_console | Ouvrir AWS Console | "ouvre aws", "console aws", "va sur aws", +2 | browser |
| ouvrir_azure_portal | Ouvrir Azure Portal | "ouvre azure", "portal azure", "va sur azure", +2 | browser |
| ouvrir_gcp_console | Ouvrir Google Cloud Console | "ouvre google cloud", "gcp console", "va sur google cloud", +2 | browser |
| ouvrir_netlify | Ouvrir Netlify (deploiement) | "ouvre netlify", "va sur netlify", "netlify dashboard", +1 | browser |
| ouvrir_digitalocean | Ouvrir DigitalOcean | "ouvre digitalocean", "va sur digital ocean", "digital ocean", +1 | browser |
| ouvrir_le_monde | Ouvrir Le Monde | "ouvre le monde", "actualites le monde", "va sur le monde", +2 | browser |
| ouvrir_le_figaro | Ouvrir Le Figaro | "ouvre le figaro", "actualites figaro", "va sur le figaro", +1 | browser |
| ouvrir_liberation | Ouvrir Liberation | "ouvre liberation", "actualites liberation", "va sur libe", +1 | browser |
| ouvrir_france_info | Ouvrir France Info | "ouvre france info", "actualites france", "va sur france info", +1 | browser |
| ouvrir_techcrunch | Ouvrir TechCrunch (tech news) | "ouvre techcrunch", "news tech", "va sur techcrunch", +1 | browser |
| ouvrir_hackernews | Ouvrir Hacker News | "ouvre hacker news", "va sur hacker news", "ycombinator news", +2 | browser |
| ouvrir_ars_technica | Ouvrir Ars Technica | "ouvre ars technica", "va sur ars technica", "ars technica", +1 | browser |
| ouvrir_the_verge | Ouvrir The Verge | "ouvre the verge", "va sur the verge", "the verge", +1 | browser |
| ouvrir_deezer | Ouvrir Deezer | "ouvre deezer", "va sur deezer", "musique deezer", +1 | browser |
| ouvrir_mycanal | Ouvrir MyCanal | "ouvre canal plus", "va sur mycanal", "canal+", +1 | browser |
| chercher_leboncoin | Rechercher sur Leboncoin | "cherche sur leboncoin {requete}", "leboncoin {requete}", "annonce {requete}", +1 | browser |
| ouvrir_khan_academy | Ouvrir Khan Academy | "ouvre khan academy", "va sur khan academy", "khan academy", +1 | browser |
| ouvrir_edx | Ouvrir edX | "ouvre edx", "va sur edx", "mooc edx", +1 | browser |
| ouvrir_freecodecamp | Ouvrir freeCodeCamp | "ouvre freecodecamp", "va sur freecodecamp", "apprendre a coder", +1 | browser |
| ouvrir_caniuse | Ouvrir Can I Use (compatibilite navigateur) | "ouvre can i use", "compatibilite navigateur", "caniuse", +2 | browser |
| ouvrir_frandroid | Ouvrir Frandroid (tech FR) | "ouvre frandroid", "va sur frandroid", "actu tech frandroid", +1 | browser |
| ouvrir_numerama | Ouvrir Numerama (tech FR) | "ouvre numerama", "va sur numerama", "actu numerama", +1 | browser |
| ouvrir_les_numeriques | Ouvrir Les Numeriques (tests produits) | "ouvre les numeriques", "les numeriques", "tests produits", +1 | browser |
| ouvrir_01net | Ouvrir 01net (tech FR) | "ouvre 01net", "va sur 01 net", "01net", +1 | browser |
| ouvrir_journal_du_net | Ouvrir Le Journal du Net | "ouvre journal du net", "jdn", "journal du net", +1 | browser |
| ouvrir_binance | Ouvrir Binance | "ouvre binance", "va sur binance", "binance exchange", +1 | browser |
| ouvrir_coinbase | Ouvrir Coinbase | "ouvre coinbase", "va sur coinbase", "coinbase exchange", +1 | browser |
| ouvrir_kraken | Ouvrir Kraken | "ouvre kraken", "va sur kraken", "kraken exchange", +1 | browser |
| ouvrir_etherscan | Ouvrir Etherscan (explorateur Ethereum) | "ouvre etherscan", "etherscan", "explorateur ethereum", +1 | browser |
| ouvrir_booking | Ouvrir Booking.com (hotels) | "ouvre booking", "reserve un hotel", "va sur booking", +1 | browser |
| ouvrir_airbnb | Ouvrir Airbnb | "ouvre airbnb", "va sur airbnb", "location airbnb", +1 | browser |
| ouvrir_google_flights | Ouvrir Google Flights (vols) | "ouvre google flights", "billets d'avion", "cherche un vol", +2 | browser |
| ouvrir_tripadvisor | Ouvrir TripAdvisor | "ouvre tripadvisor", "avis restaurants", "va sur tripadvisor", +1 | browser |
| ouvrir_blablacar | Ouvrir BlaBlaCar (covoiturage) | "ouvre blablacar", "covoiturage", "va sur blablacar", +1 | browser |
| ouvrir_legifrance | Ouvrir Legifrance (textes de loi) | "ouvre legifrance", "textes de loi", "va sur legifrance", +2 | browser |
| ouvrir_ants | Ouvrir ANTS (carte d'identite, permis) | "ouvre ants", "carte d'identite", "va sur ants", +2 | browser |
| ouvrir_prefecture | Ouvrir la prise de RDV en prefecture | "rendez vous prefecture", "ouvre la prefecture", "va sur la prefecture", +1 | browser |
| ouvrir_steam_store | Ouvrir le Steam Store | "ouvre le store steam", "magasin steam", "steam shop", +2 | browser |
| ouvrir_epic_games | Ouvrir Epic Games Store | "ouvre epic games", "va sur epic games", "epic store", +2 | browser |
| ouvrir_gog | Ouvrir GOG.com (jeux sans DRM) | "ouvre gog", "va sur gog", "jeux gog", +1 | browser |
| ouvrir_humble_bundle | Ouvrir Humble Bundle | "ouvre humble bundle", "humble bundle", "bundle de jeux", +1 | browser |
| ouvrir_vidal | Ouvrir Vidal (medicaments) | "ouvre vidal", "notice medicament", "va sur vidal", +1 | browser |
| ouvrir_doctissimo | Ouvrir Doctissimo (sante) | "ouvre doctissimo", "symptomes", "va sur doctissimo", +1 | browser |
| chercher_github_repos | Rechercher un repo sur GitHub | "cherche un repo {requete}", "github repo {requete}", "projet github {requete}" | browser |
| chercher_huggingface_models | Rechercher un modele sur Hugging Face | "cherche un modele {requete}", "huggingface model {requete}", "modele ia {requete}" | browser |
| ouvrir_grafana_cloud | Ouvrir Grafana Cloud | "ouvre grafana", "va sur grafana", "dashboard grafana", +1 | browser |
| ouvrir_datadog | Ouvrir Datadog | "ouvre datadog", "va sur datadog", "monitoring datadog", +1 | browser |
| ouvrir_sentry | Ouvrir Sentry (error tracking) | "ouvre sentry", "va sur sentry", "erreurs sentry", +1 | browser |
| ouvrir_pagerduty | Ouvrir PagerDuty (alerting) | "ouvre pagerduty", "alertes pagerduty", "on call pagerduty" | browser |
| ouvrir_newrelic | Ouvrir New Relic (APM) | "ouvre new relic", "va sur newrelic", "performance newrelic", +1 | browser |
| ouvrir_uptime_robot | Ouvrir UptimeRobot (monitoring) | "ouvre uptime robot", "status sites", "monitoring uptime" | browser |
| ouvrir_prometheus_docs | Ouvrir la doc Prometheus | "doc prometheus", "prometheus documentation", "ouvre prometheus" | browser |
| ouvrir_jenkins | Ouvrir Jenkins | "ouvre jenkins", "va sur jenkins", "builds jenkins" | browser |
| ouvrir_circleci | Ouvrir CircleCI | "ouvre circleci", "circle ci", "builds circleci" | browser |
| ouvrir_travis_ci | Ouvrir Travis CI | "ouvre travis", "travis ci", "builds travis" | browser |
| ouvrir_gitlab_ci | Ouvrir GitLab CI/CD | "ouvre gitlab ci", "gitlab pipelines", "builds gitlab" | browser |
| ouvrir_postman_web | Ouvrir Postman Web | "ouvre postman", "va sur postman", "test api postman", +1 | browser |
| ouvrir_swagger_editor | Ouvrir Swagger Editor | "ouvre swagger", "swagger editor", "editeur openapi" | browser |
| ouvrir_rapidapi | Ouvrir RapidAPI (marketplace API) | "ouvre rapidapi", "va sur rapidapi", "marketplace api", +1 | browser |
| ouvrir_httpbin | Ouvrir HTTPBin (test HTTP) | "ouvre httpbin", "test http", "httpbin test" | browser |
| ouvrir_reqbin | Ouvrir ReqBin (HTTP client en ligne) | "ouvre reqbin", "client http en ligne", "tester une requete" | browser |
| ouvrir_malt | Ouvrir Malt (freelance FR) | "ouvre malt", "va sur malt", "freelance malt", +1 | browser |
| ouvrir_fiverr | Ouvrir Fiverr | "ouvre fiverr", "va sur fiverr", "services fiverr" | browser |
| ouvrir_upwork | Ouvrir Upwork | "ouvre upwork", "va sur upwork", "jobs upwork", +1 | browser |
| ouvrir_welcome_jungle | Ouvrir Welcome to the Jungle (emploi tech) | "ouvre welcome to the jungle", "offres d'emploi tech", "welcome jungle", +1 | browser |
| ouvrir_indeed | Ouvrir Indeed | "ouvre indeed", "va sur indeed", "offres d'emploi", +1 | browser |
| ouvrir_uber_eats | Ouvrir Uber Eats | "ouvre uber eats", "commande uber eats", "uber eats", +1 | browser |
| ouvrir_deliveroo | Ouvrir Deliveroo | "ouvre deliveroo", "commande deliveroo", "livraison deliveroo" | browser |
| ouvrir_just_eat | Ouvrir Just Eat | "ouvre just eat", "commande just eat", "livraison just eat" | browser |
| ouvrir_tf1_plus | Ouvrir TF1+ (replay TF1) | "ouvre tf1", "replay tf1", "tf1 plus", +1 | browser |
| ouvrir_france_tv | Ouvrir France.tv (replay France TV) | "ouvre france tv", "replay france tv", "france television", +1 | browser |
| ouvrir_arte_replay | Ouvrir Arte.tv (replay) | "ouvre arte", "replay arte", "arte tv", +1 | browser |
| ouvrir_bfm_tv | Ouvrir BFM TV en direct | "ouvre bfm", "bfm tv", "info en direct", +1 | browser |
| ouvrir_cnews | Ouvrir CNews | "ouvre cnews", "c news", "cnews en direct" | browser |
| ouvrir_mediapart | Ouvrir Mediapart | "ouvre mediapart", "va sur mediapart", "articles mediapart" | browser |
| ouvrir_trello | Ouvrir Trello | "ouvre trello", "va sur trello", "mes boards trello", +1 | browser |
| ouvrir_asana | Ouvrir Asana | "ouvre asana", "va sur asana", "projets asana" | browser |
| ouvrir_monday | Ouvrir Monday.com | "ouvre monday", "va sur monday", "monday com" | browser |
| ouvrir_clickup | Ouvrir ClickUp | "ouvre clickup", "va sur clickup", "projets clickup" | browser |
| ouvrir_darty | Ouvrir Darty | "ouvre darty", "va sur darty", "electromenager darty" | browser |
| ouvrir_boulanger | Ouvrir Boulanger | "ouvre boulanger", "va sur boulanger", "electromenager boulanger" | browser |
| ouvrir_leroy_merlin | Ouvrir Leroy Merlin (bricolage) | "ouvre leroy merlin", "bricolage", "va sur leroy merlin" | browser |
| ouvrir_castorama | Ouvrir Castorama (bricolage) | "ouvre castorama", "va sur castorama", "bricolage castorama" | browser |
| ouvrir_vinted | Ouvrir Vinted | "ouvre vinted", "va sur vinted", "vetements vinted" | browser |
| ouvrir_revolut | Ouvrir Revolut | "ouvre revolut", "va sur revolut", "compte revolut" | browser |
| ouvrir_n26 | Ouvrir N26 (banque en ligne) | "ouvre n26", "va sur n26", "banque n26" | browser |
| ouvrir_bankin | Ouvrir Bankin (agrégateur comptes) | "ouvre bankin", "va sur bankin", "mes comptes bankin", +1 | browser |
| ouvrir_dribbble | Ouvrir Dribbble (inspiration design) | "ouvre dribbble", "inspiration design", "va sur dribbble" | browser |
| ouvrir_unsplash | Ouvrir Unsplash (photos libres) | "ouvre unsplash", "photos gratuites", "images libres", +1 | browser |
| ouvrir_coolors | Ouvrir Coolors (palettes couleurs) | "ouvre coolors", "palette de couleurs", "generateur couleurs" | browser |
| ouvrir_fontawesome | Ouvrir Font Awesome (icones) | "ouvre font awesome", "icones font awesome", "cherche une icone" | browser |
| ouvrir_claude_ai | Ouvrir Claude AI | "ouvre claude", "va sur claude", "lance claude ai" | browser |
| ouvrir_gemini_web | Ouvrir Google Gemini | "ouvre gemini web", "va sur gemini", "google gemini" | browser |
| ouvrir_midjourney | Ouvrir Midjourney | "ouvre midjourney", "va sur midjourney", "genere une image ia" | browser |
| ouvrir_replicate | Ouvrir Replicate (ML APIs) | "ouvre replicate", "va sur replicate", "api ml replicate" | browser |
| ouvrir_together_ai | Ouvrir Together AI (inference) | "ouvre together ai", "va sur together", "together inference" | browser |
| ouvrir_ollama_web | Ouvrir Ollama (modeles locaux) | "ouvre ollama site", "va sur ollama", "site ollama" | browser |
| ouvrir_openrouter | Ouvrir OpenRouter (multi-model API) | "ouvre openrouter", "va sur openrouter", "api openrouter" | browser |
| ouvrir_geeksforgeeks | Ouvrir GeeksForGeeks | "ouvre geeksforgeeks", "geeks for geeks", "gfg" | browser |
| ouvrir_digitalocean_docs | Ouvrir DigitalOcean Tutorials | "ouvre digitalocean", "tutos digitalocean", "digital ocean docs" | browser |
| ouvrir_realpython | Ouvrir Real Python (tutos Python) | "ouvre real python", "tutos python", "real python" | browser |
| ouvrir_css_tricks | Ouvrir CSS-Tricks | "ouvre css tricks", "astuces css", "css tricks" | browser |
| ouvrir_web_dev | Ouvrir web.dev (Google) | "ouvre web dev", "web dev google", "bonnes pratiques web" | browser |
| ouvrir_bandcamp | Ouvrir Bandcamp | "ouvre bandcamp", "va sur bandcamp", "musique bandcamp" | browser |
| ouvrir_data_gouv | Ouvrir data.gouv.fr (open data) | "ouvre data gouv", "open data france", "donnees publiques" | browser |
| ouvrir_seloger | Ouvrir SeLoger | "ouvre seloger", "va sur seloger", "cherche un appart", +1 | browser |
| ouvrir_pap | Ouvrir PAP (particulier a particulier) | "ouvre pap", "pap immobilier", "de particulier a particulier" | browser |
| ouvrir_bienici | Ouvrir Bien'ici (immobilier) | "ouvre bienici", "bien ici", "immobilier bienici" | browser |
| ouvrir_logic_immo | Ouvrir Logic-Immo | "ouvre logic immo", "logic immo", "logement logic immo" | browser |
| ouvrir_ratp | Ouvrir RATP (metro Paris) | "ouvre ratp", "metro paris", "plan ratp", +1 | browser |
| ouvrir_citymapper | Ouvrir Citymapper (itineraires) | "ouvre citymapper", "itineraire transport", "citymapper" | browser |
| ouvrir_onedrive_web | Ouvrir OneDrive Web | "ouvre onedrive", "va sur onedrive", "one drive web" | browser |
| ouvrir_dropbox | Ouvrir Dropbox | "ouvre dropbox", "va sur dropbox", "fichiers dropbox" | browser |
| ouvrir_mega | Ouvrir Mega (stockage chiffre) | "ouvre mega", "va sur mega", "mega cloud" | browser |
| ouvrir_discord_web | Ouvrir Discord Web | "ouvre discord web", "discord en ligne", "va sur discord" | browser |
| ouvrir_zoom | Ouvrir Zoom | "ouvre zoom", "va sur zoom", "lance zoom", +1 | browser |

### Fichiers & Documents (47 commandes)

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
| compresser_fichier | Compresser un dossier en ZIP | "compresse en zip", "zip le dossier", "cree un zip", +2 | powershell |
| decompresser_fichier | Decompresser un fichier ZIP | "decompresse le zip", "unzip", "extrais l'archive", +2 | powershell |
| compresser_turbo | Compresser le projet turbo en ZIP (sans .git ni venv) | "zip turbo", "archive turbo", "compresse le projet", +1 | powershell |
| vider_dossier_temp | Supprimer les fichiers temporaires | "vide le temp", "nettoie les temporaires", "clean temp", +1 | powershell |
| lister_fichiers_recents | Lister les 20 fichiers les plus recents sur le bureau | "fichiers recents", "derniers fichiers", "quoi de recent", +1 | powershell |
| chercher_gros_fichiers | Trouver les fichiers > 100 MB sur F: | "gros fichiers partout", "fichiers enormes", "quoi prend toute la place", +1 | powershell |
| doublons_bureau | Detecter les doublons potentiels par nom dans F:\BUREAU | "doublons bureau", "fichiers en double", "trouve les doublons", +2 | powershell |
| taille_telechargements | Taille du dossier Telechargements | "taille telechargements", "poids downloads", "combien dans les telechargements", +1 | powershell |
| vider_telechargements | Vider le dossier Telechargements (fichiers > 30 jours) | "vide les telechargements", "nettoie les downloads", "clean downloads", +1 | powershell |
| lister_telechargements | Derniers fichiers telecharges | "derniers telechargements", "quoi de telecharge", "recent downloads", +1 | powershell |
| ouvrir_telechargements | Ouvrir le dossier Telechargements | "ouvre les telechargements", "dossier downloads", "va dans les telechargements", +1 | powershell |
| ouvrir_documents | Ouvrir le dossier Documents | "ouvre les documents", "dossier documents", "mes documents", +1 | powershell |
| ouvrir_bureau_dossier | Ouvrir F:\BUREAU dans l'explorateur | "ouvre le bureau", "dossier bureau", "va dans bureau", +1 | powershell |
| fichier_recent_modifie | Trouver le dernier fichier modifie partout | "dernier fichier modifie", "quoi vient de changer", "last modified", +1 | powershell |
| compter_fichiers_type | Compter les fichiers par extension dans un dossier | "compte les fichiers par type", "extensions dans {path}", "quels types de fichiers dans {path}" | powershell |

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

### Systeme Windows (640 commandes)

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
| powertoys_color_picker | Lancer le Color Picker PowerToys | "color picker", "pipette couleur", "capture une couleur", +2 | hotkey |
| powertoys_text_extractor | Extraire du texte de l'ecran (OCR PowerToys) | "text extractor", "ocr ecran", "lis le texte a l'ecran", +2 | hotkey |
| powertoys_screen_ruler | Mesurer des distances a l'ecran (Screen Ruler) | "screen ruler", "regle ecran", "mesure l'ecran", +2 | hotkey |
| powertoys_always_on_top | Epingler la fenetre au premier plan (PowerToys) | "pin powertoys", "epingle powertoys", "always on top powertoys", +1 | hotkey |
| powertoys_paste_plain | Coller en texte brut (PowerToys) | "colle en texte brut", "paste plain", "coller sans mise en forme", +2 | hotkey |
| powertoys_fancyzones | Activer FancyZones layout editor | "fancy zones", "editeur de zones", "layout fancyzones", +2 | hotkey |
| powertoys_peek | Apercu rapide de fichier (PowerToys Peek) | "peek fichier", "apercu rapide", "preview powertoys", +1 | hotkey |
| powertoys_launcher | Ouvrir PowerToys Run (lanceur rapide) | "powertoys run", "lanceur rapide", "quick launcher", +2 | hotkey |
| traceroute_google | Traceroute vers Google DNS | "traceroute", "trace la route", "tracert google", +2 | powershell |
| ping_google | Ping Google pour tester la connexion | "ping google", "teste internet", "j'ai internet", +2 | powershell |
| ping_cluster_complet | Ping tous les noeuds du cluster IA | "ping tout le cluster", "tous les noeuds repondent", "test cluster complet", +1 | powershell |
| netstat_ecoute | Ports en ecoute avec processus associes | "netstat listen", "ports en ecoute", "quels ports ecoutent", +1 | powershell |
| flush_dns | Purger le cache DNS | "flush dns", "purge dns", "vide le cache dns", +2 | powershell |
| flush_arp | Purger la table ARP | "flush arp", "vide la table arp", "purge arp", +1 | powershell |
| ip_config_complet | Configuration IP complete de toutes les interfaces | "ipconfig all", "config ip complete", "toutes les ips", +2 | powershell |
| speed_test_rapide | Test de debit internet rapide (download) | "speed test", "test de vitesse", "vitesse internet", +2 | powershell |
| vpn_status | Verifier l'etat des connexions VPN actives | "etat vpn", "vpn status", "suis je en vpn", +2 | powershell |
| shutdown_timer_30 | Programmer l'extinction dans 30 minutes | "eteins dans 30 minutes", "shutdown dans 30 min", "timer extinction 30", +1 | powershell |
| shutdown_timer_60 | Programmer l'extinction dans 1 heure | "eteins dans une heure", "shutdown dans 1h", "timer extinction 1h", +1 | powershell |
| shutdown_timer_120 | Programmer l'extinction dans 2 heures | "eteins dans deux heures", "shutdown dans 2h", "timer extinction 2h", +1 | powershell |
| annuler_shutdown | Annuler l'extinction programmee | "annule l'extinction", "cancel shutdown", "arrete le timer", +2 | powershell |
| restart_timer_30 | Programmer un redemarrage dans 30 minutes | "redemarre dans 30 minutes", "restart dans 30 min", "redemarrage programme 30" | powershell |
| rappel_vocal | Creer un rappel vocal avec notification | "rappelle moi dans {minutes} minutes", "timer {minutes} min", "alarme dans {minutes} minutes", +1 | powershell |
| generer_mot_de_passe | Generer un mot de passe securise aleatoire | "genere un mot de passe", "password random", "mot de passe aleatoire", +2 | powershell |
| audit_rdp | Verifier si le Bureau a distance est active | "rdp actif", "bureau a distance", "remote desktop status", +2 | powershell |
| audit_admin_users | Lister les utilisateurs administrateurs | "qui est admin", "utilisateurs administrateurs", "admin users", +2 | powershell |
| sessions_actives | Lister les sessions utilisateur actives | "sessions actives", "qui est connecte", "user sessions", +1 | powershell |
| check_hash_fichier | Calculer le hash SHA256 d'un fichier | "hash du fichier {path}", "sha256 {path}", "checksum {path}", +1 | powershell |
| audit_software_recent | Logiciels installes recemment (30 derniers jours) | "logiciels recemment installes", "quoi de neuf installe", "installations recentes", +1 | powershell |
| firewall_toggle_profil | Activer/desactiver le pare-feu pour le profil actif | "toggle firewall", "active le pare feu", "desactive le firewall", +2 | powershell |
| luminosite_haute | Monter la luminosite au maximum | "luminosite max", "brightness max", "ecran au maximum", +2 | powershell |
| luminosite_basse | Baisser la luminosite au minimum | "luminosite min", "brightness low", "ecran au minimum", +2 | powershell |
| luminosite_moyenne | Luminosite a 50% | "luminosite moyenne", "brightness medium", "luminosite normale", +2 | powershell |
| info_moniteurs | Informations sur les moniteurs connectes | "info moniteurs", "quels ecrans", "resolution ecran", +2 | powershell |
| batterie_info | Etat de la batterie (si laptop) | "etat batterie", "battery status", "niveau batterie", +2 | powershell |
| power_events_recent | Historique veille/reveil des dernieres 24h | "historique veille", "quand le pc s'est endormi", "power events", +1 | powershell |
| night_light_toggle | Basculer l'eclairage nocturne | "lumiere de nuit", "night light", "eclairage nocturne", +2 | powershell |
| imprimer_page | Imprimer la page/document actif | "imprime", "print", "lance l'impression", +2 | hotkey |
| file_impression | Voir la file d'attente d'impression | "file d'impression", "print queue", "quoi dans l'imprimante", +2 | powershell |
| annuler_impressions | Annuler toutes les impressions en attente | "annule les impressions", "cancel print", "arrete l'imprimante", +1 | powershell |
| imprimante_par_defaut | Voir l'imprimante par defaut | "quelle imprimante par defaut", "default printer", "imprimante principale", +1 | powershell |
| kill_chrome | Forcer la fermeture de Chrome | "tue chrome", "kill chrome", "force ferme chrome", +1 | powershell |
| kill_edge | Forcer la fermeture d'Edge | "tue edge", "kill edge", "force ferme edge", +1 | powershell |
| kill_discord | Forcer la fermeture de Discord | "tue discord", "kill discord", "ferme discord de force", +1 | powershell |
| kill_spotify | Forcer la fermeture de Spotify | "tue spotify", "kill spotify", "ferme spotify de force", +1 | powershell |
| kill_steam | Forcer la fermeture de Steam | "tue steam", "kill steam", "ferme steam de force", +1 | powershell |
| priorite_haute | Passer la fenetre active en priorite haute CPU | "priorite haute", "high priority", "boost le processus", +1 | powershell |
| processus_reseau | Processus utilisant le reseau actuellement | "qui utilise le reseau", "processus reseau", "network processes", +1 | powershell |
| wsl_status | Voir les distributions WSL installees | "distributions wsl", "wsl list", "quelles distros linux", +2 | powershell |
| wsl_start | Demarrer WSL (distribution par defaut) | "lance wsl", "demarre linux", "ouvre wsl", +2 | powershell |
| wsl_disk_usage | Espace disque utilise par WSL | "taille wsl", "espace wsl", "combien pese linux", +1 | powershell |
| loupe_activer | Activer la loupe Windows | "active la loupe", "zoom ecran", "magnifier on", +2 | hotkey |
| loupe_desactiver | Desactiver la loupe Windows | "desactive la loupe", "arrete le zoom", "magnifier off", +1 | hotkey |
| haut_contraste_toggle | Basculer en mode haut contraste | "haut contraste", "high contrast", "mode contraste", +1 | hotkey |
| touches_remanentes | Activer/desactiver les touches remanentes | "touches remanentes", "sticky keys", "touches collantes", +1 | powershell |
| taille_texte_plus | Augmenter la taille du texte systeme | "texte plus grand", "agrandis le texte", "bigger text", +1 | powershell |
| ouvrir_melangeur_audio | Ouvrir le melangeur de volume | "melangeur audio", "volume mixer", "mix audio", +2 | powershell |
| ouvrir_param_son | Ouvrir les parametres de son | "parametres son", "reglages audio", "sound settings", +2 | powershell |
| lister_audio_devices | Lister les peripheriques audio | "peripheriques audio", "quelles sorties son", "audio devices", +2 | powershell |
| volume_50 | Mettre le volume a 50% | "volume a 50", "moitie volume", "volume moyen", +1 | powershell |
| volume_25 | Mettre le volume a 25% | "volume a 25", "volume bas", "volume faible", +1 | powershell |
| volume_max | Mettre le volume au maximum | "volume a fond", "volume maximum", "volume 100", +1 | powershell |
| storage_sense_on | Activer Storage Sense (nettoyage auto) | "active storage sense", "nettoyage automatique", "auto clean", +1 | powershell |
| disk_cleanup | Lancer le nettoyage de disque Windows (cleanmgr) | "nettoyage de disque", "disk cleanup", "cleanmgr", +1 | powershell |
| defrag_status | Voir l'etat de fragmentation des disques | "etat defragmentation", "defrag status", "disques fragmentes", +1 | powershell |
| optimiser_disques | Optimiser/defragmenter les disques | "optimise les disques", "defragmente", "defrag", +1 | powershell |
| focus_assist_alarms | Focus Assist mode alarmes seulement | "alarmes seulement", "focus alarms only", "juste les alarmes", +1 | powershell |
| startup_apps_list | Lister les apps qui demarrent au boot | "apps au demarrage", "startup apps", "quoi se lance au boot", +1 | powershell |
| startup_settings | Ouvrir les parametres des apps au demarrage | "parametres demarrage", "startup settings", "gerer le demarrage", +1 | powershell |
| credential_list | Lister les identifiants Windows enregistres | "liste les identifiants", "quels mots de passe", "credentials saved", +1 | powershell |
| dns_serveurs | Voir les serveurs DNS configures | "quels serveurs dns", "dns configures", "dns servers", +2 | powershell |
| sync_horloge | Synchroniser l'horloge avec le serveur NTP | "synchronise l'horloge", "sync ntp", "mets l'heure a jour", +2 | powershell |
| timezone_info | Voir le fuseau horaire actuel | "quel fuseau horaire", "timezone", "heure locale", +2 | powershell |
| calendrier_mois | Afficher le calendrier du mois en cours | "calendrier", "montre le calendrier", "quel jour on est", +1 | powershell |
| ouvrir_rdp | Ouvrir le client Remote Desktop | "ouvre remote desktop", "lance rdp", "bureau a distance client", +2 | powershell |
| rdp_connect | Connexion Remote Desktop a une machine | "connecte en rdp a {host}", "remote desktop {host}", "bureau a distance sur {host}", +1 | powershell |
| ssh_connect | Connexion SSH a un serveur | "connecte en ssh a {host}", "ssh {host}", "terminal distant {host}", +1 | powershell |
| changer_clavier | Changer la disposition clavier (FR/EN) | "change le clavier", "switch keyboard", "clavier francais", +2 | hotkey |
| clavier_suivant | Passer a la disposition clavier suivante | "clavier suivant", "next keyboard", "alt shift", +1 | hotkey |
| taskbar_cacher | Cacher la barre des taches automatiquement | "cache la taskbar", "hide taskbar", "barre des taches invisible", +1 | powershell |
| wallpaper_info | Voir le fond d'ecran actuel | "quel fond d'ecran", "wallpaper actuel", "image de fond", +1 | powershell |
| icones_bureau_toggle | Afficher/masquer les icones du bureau | "cache les icones", "montre les icones", "icones bureau", +2 | powershell |
| sandbox_launch | Lancer Windows Sandbox | "lance la sandbox", "windows sandbox", "ouvre la sandbox", +1 | powershell |
| hyperv_list_vms | Lister les machines virtuelles Hyper-V | "liste les vms", "virtual machines", "hyper v vms", +2 | powershell |
| hyperv_start_vm | Demarrer une VM Hyper-V | "demarre la vm {vm}", "start vm {vm}", "lance la machine {vm}", +1 | powershell |
| hyperv_stop_vm | Arreter une VM Hyper-V | "arrete la vm {vm}", "stop vm {vm}", "eteins la machine {vm}", +1 | powershell |
| service_start | Demarrer un service Windows | "demarre le service {svc}", "start service {svc}", "lance le service {svc}" | powershell |
| service_stop | Arreter un service Windows | "arrete le service {svc}", "stop service {svc}", "coupe le service {svc}" | powershell |
| service_restart | Redemarrer un service Windows | "redemarre le service {svc}", "restart service {svc}", "relance le service {svc}" | powershell |
| service_status | Voir l'etat d'un service Windows | "etat du service {svc}", "status service {svc}", "le service {svc} tourne" | powershell |
| partitions_list | Lister toutes les partitions | "liste les partitions", "partitions disque", "volumes montes", +1 | powershell |
| disques_physiques | Voir les disques physiques installes | "disques physiques", "quels disques", "ssd hdd", +2 | powershell |
| clipboard_contenu | Voir le contenu actuel du presse-papier | "quoi dans le presse papier", "clipboard content", "montre le clipboard", +1 | powershell |
| clipboard_en_majuscules | Convertir le texte du clipboard en majuscules | "clipboard en majuscules", "texte en majuscules", "uppercase clipboard", +1 | powershell |
| clipboard_en_minuscules | Convertir le texte du clipboard en minuscules | "clipboard en minuscules", "texte en minuscules", "lowercase clipboard", +1 | powershell |
| clipboard_compter_mots | Compter les mots dans le presse-papier | "combien de mots copies", "word count clipboard", "compte les mots", +1 | powershell |
| clipboard_trim | Nettoyer les espaces du texte clipboard | "nettoie le clipboard", "trim clipboard", "enleve les espaces", +1 | powershell |
| param_camera | Parametres de confidentialite camera | "parametres camera", "privacy camera", "autoriser la camera", +1 | powershell |
| param_microphone | Parametres de confidentialite microphone | "parametres microphone", "privacy micro", "autoriser le micro", +1 | powershell |
| param_localisation | Parametres de localisation/GPS | "parametres localisation", "privacy location", "active le gps", +2 | powershell |
| param_gaming | Parametres de jeu Windows | "parametres gaming", "game settings", "mode jeu settings", +2 | powershell |
| param_comptes | Parametres des comptes utilisateur | "parametres comptes", "account settings", "gerer les comptes", +1 | powershell |
| param_connexion | Parametres de connexion (PIN, mot de passe) | "options de connexion", "sign in options", "changer le pin", +2 | powershell |
| param_apps_defaut | Parametres des apps par defaut | "apps par defaut", "default apps", "navigateur par defaut", +1 | powershell |
| param_fonctionnalites_optionnelles | Fonctionnalites optionnelles Windows | "fonctionnalites optionnelles", "optional features", "ajouter une fonctionnalite", +1 | powershell |
| param_souris | Parametres de la souris | "parametres souris", "mouse settings", "vitesse souris", +1 | powershell |
| param_clavier | Parametres du clavier | "parametres clavier", "keyboard settings", "vitesse clavier", +1 | powershell |
| param_phone_link | Ouvrir Phone Link (connexion telephone) | "phone link", "lien telephone", "connecter mon telephone", +1 | powershell |
| param_notifications_apps | Parametres notifications par application | "notifications par app", "gerer les notifications", "notifs par app", +1 | powershell |
| param_multitache | Parametres multitache (snap, bureaux virtuels) | "parametres multitache", "multitasking settings", "snap settings", +1 | powershell |
| param_stockage | Parametres de stockage (espace disque) | "parametres stockage", "storage settings", "gestion stockage", +1 | powershell |
| param_proxy | Parametres de proxy reseau | "parametres proxy", "proxy settings", "configurer le proxy", +1 | powershell |
| param_vpn_settings | Parametres VPN Windows | "parametres vpn", "vpn settings", "configurer le vpn", +1 | powershell |
| param_wifi_settings | Parametres WiFi avances | "parametres wifi", "wifi settings", "reseaux connus", +1 | powershell |
| param_update_avance | Parametres Windows Update avances | "update avance", "windows update settings", "options de mise a jour", +1 | powershell |
| param_recovery | Options de recuperation systeme | "recovery options", "reinitialiser le pc", "restauration systeme", +1 | powershell |
| param_developeurs | Parametres developpeur Windows | "mode developpeur", "developer settings", "active le mode dev", +1 | powershell |
| calculatrice_standard | Ouvrir la calculatrice Windows | "ouvre la calculatrice", "calculatrice", "calc", +1 | powershell |
| calculer_expression | Calculer une expression mathematique | "calcule {expr}", "combien fait {expr}", "resultat de {expr}", +1 | powershell |
| convertir_temperature | Convertir Celsius en Fahrenheit et inversement | "convertis {temp} degres", "celsius en fahrenheit {temp}", "fahrenheit en celsius {temp}", +1 | powershell |
| convertir_octets | Convertir des octets en unites lisibles | "convertis {bytes} octets", "combien de go fait {bytes}", "bytes en gb {bytes}", +1 | powershell |
| clipboard_base64_encode | Encoder le clipboard en Base64 | "encode en base64", "base64 encode", "clipboard en base64", +1 | powershell |
| clipboard_base64_decode | Decoder le clipboard depuis Base64 | "decode le base64", "base64 decode", "clipboard depuis base64", +1 | powershell |
| clipboard_url_encode | Encoder le clipboard en URL (percent-encode) | "url encode", "encode l'url", "percent encode", +1 | powershell |
| clipboard_json_format | Formatter le JSON du clipboard avec indentation | "formate le json", "json pretty", "indente le json", +1 | powershell |
| clipboard_md5 | Calculer le MD5 du texte dans le clipboard | "md5 du clipboard", "hash md5 texte", "md5 du texte copie", +1 | powershell |
| clipboard_sort_lines | Trier les lignes du clipboard par ordre alphabetique | "trie les lignes", "sort lines clipboard", "ordonne le clipboard", +1 | powershell |
| clipboard_unique_lines | Supprimer les lignes dupliquees du clipboard | "deduplique les lignes", "unique lines", "enleve les doublons texte", +1 | powershell |
| clipboard_reverse | Inverser le texte du clipboard | "inverse le texte", "reverse clipboard", "texte a l'envers", +1 | powershell |
| power_performance | Activer le plan d'alimentation Haute Performance | "mode performance", "high performance", "pleine puissance", +2 | powershell |
| power_equilibre | Activer le plan d'alimentation Equilibre | "mode equilibre", "balanced power", "plan normal", +1 | powershell |
| power_economie | Activer le plan d'alimentation Economie d'energie | "mode economie", "power saver", "economie energie", +2 | powershell |
| power_plans_list | Lister les plans d'alimentation disponibles | "quels plans alimentation", "power plans", "modes d'alimentation disponibles", +1 | powershell |
| sleep_timer_30 | Mettre le PC en veille dans 30 minutes | "veille dans 30 minutes", "sleep dans 30 min", "dors dans une demi heure", +1 | powershell |
| network_reset | Reset complet de la pile reseau Windows | "reset reseau", "reinitialise le reseau", "network reset", +1 | powershell |
| network_troubleshoot | Lancer le depanneur reseau Windows | "depanne le reseau", "network troubleshoot", "diagnostic reseau windows", +1 | powershell |
| arp_table | Afficher la table ARP (machines sur le reseau local) | "table arp", "machines sur le reseau", "arp -a", +1 | powershell |
| nslookup_domain | Resoudre un nom de domaine (nslookup) | "nslookup {domain}", "resous {domain}", "ip de {domain}", +1 | powershell |
| registry_backup | Sauvegarder le registre complet | "backup registre", "sauvegarde le registre", "exporte le registre", +1 | powershell |
| registry_search | Chercher une cle dans le registre | "cherche dans le registre {cle}", "registry search {cle}", "trouve la cle {cle}" | powershell |
| registry_recent_changes | Cles de registre recemment modifiees | "registre recent", "changements registre", "modifications registre" | powershell |
| registry_startup_entries | Lister les entrees de demarrage dans le registre | "startup registre", "autorun registre", "demarrage registre" | powershell |
| fonts_list | Lister les polices installees | "liste les polices", "quelles fonts", "polices installees", +1 | powershell |
| fonts_count | Compter les polices installees | "combien de polices", "nombre de fonts", "total polices" | powershell |
| fonts_folder | Ouvrir le dossier des polices | "dossier polices", "ouvre les fonts", "ouvrir dossier fonts" | powershell |
| env_list_user | Lister les variables d'environnement utilisateur | "variables utilisateur", "env vars user", "mes variables", +1 | powershell |
| env_list_system | Lister les variables d'environnement systeme | "variables systeme", "env vars systeme", "environnement systeme" | powershell |
| env_set_user | Definir une variable d'environnement utilisateur | "set variable {nom} {valeur}", "definis {nom} a {valeur}", "env set {nom} {valeur}" | powershell |
| env_path_entries | Lister les dossiers dans le PATH | "montre le path", "dossiers du path", "contenu du path", +1 | powershell |
| env_add_to_path | Ajouter un dossier au PATH utilisateur | "ajoute au path {dossier}", "path add {dossier}", "rajoute {dossier} au path" | powershell |
| schtask_running | Lister les taches planifiees en cours d'execution | "taches en cours", "scheduled tasks running", "taches actives" | powershell |
| schtask_next_run | Prochaines taches planifiees | "prochaines taches", "next scheduled tasks", "quand les taches" | powershell |
| schtask_history | Historique des taches planifiees recentes | "historique taches", "task history", "dernieres taches executees" | powershell |
| firewall_status | Statut du pare-feu Windows | "statut pare feu", "firewall status", "etat du firewall", +1 | powershell |
| firewall_rules_list | Lister les regles du pare-feu actives | "regles pare feu", "firewall rules", "liste les regles firewall" | powershell |
| firewall_block_ip | Bloquer une adresse IP dans le pare-feu | "bloque l'ip {ip}", "firewall block {ip}", "interdit {ip}", +1 | powershell |
| firewall_recent_blocks | Voir les connexions recemment bloquees | "connexions bloquees", "firewall blocks", "qui est bloque" | powershell |
| disk_smart_status | Statut SMART des disques (sante) | "sante des disques", "smart status", "etat des disques", +1 | powershell |
| disk_space_by_folder | Espace utilise par dossier (top 15) | "espace par dossier", "quels dossiers prennent de la place", "gros dossiers", +1 | powershell |
| disk_temp_files_age | Fichiers temporaires les plus anciens | "vieux fichiers temp", "anciens temp", "temp files age" | powershell |
| usb_list_devices | Lister les peripheriques USB connectes | "peripheriques usb", "usb connectes", "quels usb", +1 | powershell |
| usb_storage_list | Lister les cles USB et disques amovibles | "cles usb", "disques amovibles", "usb storage", +1 | powershell |
| usb_safely_eject | Ejecter un peripherique USB en securite | "ejecte la cle usb", "ejecter usb", "safely eject", +1 | powershell |
| usb_history | Historique des peripheriques USB connectes | "historique usb", "anciens usb", "usb history", +1 | powershell |
| screen_resolution | Afficher la resolution de chaque ecran | "resolution ecran", "quelle resolution", "taille ecran", +1 | powershell |
| screen_brightness_up | Augmenter la luminosite | "augmente la luminosite", "plus de lumiere", "brightness up", +1 | powershell |
| screen_brightness_down | Baisser la luminosite | "baisse la luminosite", "moins de lumiere", "brightness down", +1 | powershell |
| screen_night_light | Activer/desactiver l'eclairage nocturne | "eclairage nocturne", "night light", "mode nuit ecran", +1 | powershell |
| screen_refresh_rate | Voir la frequence de rafraichissement | "frequence ecran", "refresh rate", "hertz ecran", +1 | powershell |
| audio_list_devices | Lister tous les peripheriques audio | "peripheriques audio", "devices audio", "quels hauts parleurs", +1 | powershell |
| audio_default_speaker | Voir le haut-parleur par defaut | "haut parleur par defaut", "quel speaker", "sortie audio", +1 | powershell |
| audio_volume_level | Voir le niveau de volume actuel | "quel volume", "niveau du son", "volume level", +1 | powershell |
| audio_settings | Ouvrir les parametres de son | "parametres son", "reglages audio", "settings audio", +1 | powershell |
| process_by_memory | Top 15 processus par memoire | "processus par memoire", "qui consomme la ram", "top ram", +1 | powershell |
| process_by_cpu | Top 15 processus par CPU | "processus par cpu", "qui consomme le cpu", "top cpu", +1 | powershell |
| process_tree | Arborescence des processus (parent-enfant) | "arbre des processus", "process tree", "qui lance quoi", +1 | powershell |
| process_handles | Processus avec le plus de handles ouverts | "handles ouverts", "processus handles", "qui a trop de handles" | powershell |

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

### Developpement & Outils (241 commandes)

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
| wt_split_horizontal | Diviser le terminal Windows horizontalement | "split terminal horizontal", "divise le terminal", "terminal cote a cote", +1 | powershell |
| wt_split_vertical | Diviser le terminal Windows verticalement | "split terminal vertical", "divise le terminal vertical", "nouveau panneau vertical" | powershell |
| wt_new_tab | Nouvel onglet dans Windows Terminal | "nouvel onglet terminal", "new tab terminal", "nouveau tab wt", +1 | powershell |
| wt_new_tab_powershell | Nouvel onglet PowerShell dans Windows Terminal | "terminal powershell", "onglet powershell", "ouvre un powershell", +1 | powershell |
| wt_new_tab_cmd | Nouvel onglet CMD dans Windows Terminal | "terminal cmd", "onglet cmd", "ouvre un cmd", +1 | powershell |
| wt_quake_mode | Ouvrir le terminal en mode quake (dropdown) | "terminal quake", "quake mode", "terminal dropdown", +1 | hotkey |
| vscode_zen_mode | Activer le mode zen dans VSCode | "mode zen vscode", "zen mode", "vscode zen", +2 | hotkey |
| vscode_format_document | Formater le document dans VSCode | "formate le document", "format code", "prettier", +2 | hotkey |
| vscode_word_wrap | Basculer le retour a la ligne dans VSCode | "word wrap vscode", "retour a la ligne", "toggle wrap", +2 | hotkey |
| vscode_minimap | Afficher/masquer la minimap VSCode | "minimap vscode", "toggle minimap", "carte du code", +1 | powershell |
| vscode_multi_cursor_down | Ajouter un curseur en dessous dans VSCode | "multi curseur bas", "curseur en dessous", "ctrl alt down", +1 | hotkey |
| vscode_multi_cursor_up | Ajouter un curseur au dessus dans VSCode | "multi curseur haut", "curseur au dessus", "ctrl alt up", +1 | hotkey |
| vscode_rename_symbol | Renommer un symbole dans VSCode (refactoring) | "renomme le symbole", "rename symbol", "refactor rename", +2 | hotkey |
| vscode_go_to_definition | Aller a la definition dans VSCode | "va a la definition", "go to definition", "f12 vscode", +1 | hotkey |
| vscode_peek_definition | Apercu de la definition (peek) dans VSCode | "peek definition", "apercu definition", "alt f12", +1 | hotkey |
| vscode_find_all_references | Trouver toutes les references dans VSCode | "toutes les references", "find references", "shift f12", +2 | hotkey |
| vscode_fold_all | Plier tout le code dans VSCode | "plie tout le code", "fold all", "ferme les blocs", +2 | hotkey |
| vscode_unfold_all | Deplier tout le code dans VSCode | "deplie tout le code", "unfold all", "ouvre les blocs", +2 | hotkey |
| vscode_toggle_comment | Commenter/decommenter la ligne ou selection | "commente", "decommente", "toggle comment", +2 | hotkey |
| vscode_problems_panel | Ouvrir le panneau des problemes VSCode | "panneau problemes", "errors vscode", "problems panel", +2 | hotkey |
| docker_ps_all | Lister tous les conteneurs Docker | "tous les conteneurs", "docker ps all", "conteneurs docker", +1 | powershell |
| docker_logs_last | Logs du dernier conteneur lance | "logs docker", "docker logs", "logs du conteneur", +1 | powershell |
| pytest_turbo | Lancer les tests pytest du projet turbo | "lance les tests", "pytest", "run tests", +2 | powershell |
| pytest_last_failed | Relancer les tests qui ont echoue | "relance les tests echoues", "pytest lf", "rerun failed", +1 | powershell |
| ruff_check | Lancer ruff (linter Python) sur turbo | "ruff check", "lint python", "verifie le code python", +1 | powershell |
| ruff_format | Formater le code Python avec ruff format | "ruff format", "formate le python", "format python", +1 | powershell |
| mypy_check | Verifier les types Python avec mypy | "mypy check", "verifie les types", "type check python", +1 | powershell |
| pip_list_turbo | Lister les packages Python du projet turbo | "packages python", "pip list", "quels packages python", +2 | powershell |
| count_lines_python | Compter les lignes de code Python du projet | "combien de lignes de code", "lignes python", "count lines", +2 | powershell |
| sqlite_jarvis | Ouvrir la base JARVIS en SQLite | "ouvre la base jarvis", "sqlite jarvis", "base de donnees jarvis", +1 | powershell |
| sqlite_etoile | Explorer la base etoile.db | "ouvre etoile db", "base etoile", "sqlite etoile", +1 | powershell |
| sqlite_tables | Lister les tables d'une base SQLite | "tables sqlite {db}", "quelles tables dans {db}", "schema {db}", +1 | powershell |
| redis_ping | Ping Redis local | "ping redis", "redis ok", "test redis", +1 | powershell |
| redis_info | Informations Redis (memoire, clients) | "info redis", "redis info", "etat redis", +1 | powershell |
| turbo_file_count | Nombre de fichiers par type dans turbo | "combien de fichiers turbo", "types de fichiers", "file count", +1 | powershell |
| turbo_todo_scan | Scanner les TODO/FIXME/HACK dans le code | "trouve les todo", "scan todo", "fixme dans le code", +2 | powershell |
| turbo_import_graph | Voir les imports entre modules turbo | "graph des imports", "imports turbo", "dependances modules", +1 | powershell |
| git_cherry_pick | Cherry-pick un commit specifique | "cherry pick {hash}", "git cherry pick {hash}", "prends le commit {hash}" | powershell |
| git_tags | Lister les tags git | "tags git", "quels tags", "git tags", +2 | powershell |
| git_branch_create | Creer une nouvelle branche git | "cree une branche {branch}", "nouvelle branche {branch}", "git branch {branch}" | powershell |
| git_branch_delete | Supprimer une branche git locale | "supprime la branche {branch}", "delete branch {branch}", "git branch delete {branch}" | powershell |
| git_branch_switch | Changer de branche git | "va sur la branche {branch}", "switch {branch}", "checkout {branch}", +1 | powershell |
| git_merge_branch | Merger une branche dans la branche actuelle | "merge {branch}", "fusionne {branch}", "git merge {branch}", +1 | powershell |
| ssh_keygen | Generer une nouvelle cle SSH | "genere une cle ssh", "ssh keygen", "nouvelle cle ssh", +1 | powershell |
| ssh_pubkey | Afficher la cle publique SSH | "montre ma cle ssh", "cle publique ssh", "ssh public key", +1 | powershell |
| ssh_known_hosts | Voir les hosts SSH connus | "hosts ssh connus", "known hosts", "serveurs ssh", +1 | powershell |
| cargo_build | Compiler un projet Rust (cargo build) | "cargo build", "compile en rust", "build rust", +1 | powershell |
| cargo_test | Lancer les tests Rust (cargo test) | "cargo test", "tests rust", "test en rust", +1 | powershell |
| cargo_clippy | Lancer le linter Rust (clippy) | "cargo clippy", "lint rust", "clippy rust", +1 | powershell |
| npm_run_dev | Lancer npm run dev | "npm run dev", "lance le dev node", "start node dev", +1 | powershell |
| npm_run_build | Lancer npm run build | "npm run build", "build node", "compile le frontend", +1 | powershell |
| python_profile_turbo | Profiler le startup de JARVIS | "profile jarvis", "temps de demarrage", "performance startup", +1 | powershell |
| python_memory_usage | Mesurer la memoire Python du projet | "memoire python", "python memory", "consommation python", +1 | powershell |
| uv_add_package | Ajouter un package Python avec uv | "uv add {package}", "installe {package}", "ajoute le package {package}", +1 | powershell |
| uv_remove_package | Supprimer un package Python avec uv | "uv remove {package}", "desinstalle {package}", "enleve {package}", +1 | powershell |
| uv_lock | Regenerer le lockfile uv | "uv lock", "lock les deps", "regenere le lockfile", +1 | powershell |
| port_in_use | Trouver quel processus utilise un port | "qui utilise le port {port}", "port {port} occupe", "process sur port {port}", +1 | powershell |
| env_var_get | Lire une variable d'environnement | "variable {var}", "env {var}", "valeur de {var}", +1 | powershell |
| tree_turbo | Arborescence du projet turbo (2 niveaux) | "arborescence turbo", "tree turbo", "structure du projet", +1 | powershell |
| gh_create_issue | Creer une issue GitHub | "cree une issue {titre}", "nouvelle issue {titre}", "github issue {titre}", +1 | powershell |
| gh_list_issues | Lister les issues GitHub ouvertes | "liste les issues", "issues ouvertes", "github issues", +1 | powershell |
| gh_list_prs | Lister les pull requests GitHub | "liste les pr", "pull requests", "github prs", +1 | powershell |
| gh_view_pr | Voir les details d'une PR | "montre la pr {num}", "detail pr {num}", "github pr {num}", +1 | powershell |
| gh_pr_checks | Voir les checks d'une PR | "checks de la pr {num}", "status pr {num}", "ci pr {num}", +1 | powershell |
| gh_repo_view | Voir les infos du repo GitHub courant | "info du repo", "github repo info", "details du repo", +1 | powershell |
| gh_workflow_list | Lister les workflows GitHub Actions | "workflows github", "github actions", "liste les workflows", +1 | powershell |
| gh_release_list | Lister les releases GitHub | "releases github", "liste les releases", "versions publiees", +1 | powershell |
| go_build | Compiler un projet Go | "go build", "compile en go", "build le projet go" | powershell |
| go_test | Lancer les tests Go | "go test", "tests go", "lance les tests go", +1 | powershell |
| go_fmt | Formater le code Go | "go fmt", "formate le go", "gofmt" | powershell |
| go_mod_tidy | Nettoyer les dependances Go | "go mod tidy", "nettoie les deps go", "clean go modules" | powershell |
| venv_create | Creer un environnement virtuel Python | "cree un venv", "nouveau virtualenv", "python venv", +1 | powershell |
| venv_activate | Activer le virtualenv courant | "active le venv", "activate venv", "source venv" | powershell |
| conda_list_envs | Lister les environnements Conda | "conda envs", "liste les envs conda", "quels environnements conda" | powershell |
| conda_install_pkg | Installer un package Conda | "conda install {package}", "installe avec conda {package}" | powershell |
| curl_get | Faire un GET sur une URL | "curl get {url}", "requete get {url}", "test api {url}", +1 | powershell |
| curl_post_json | Faire un POST JSON sur une URL | "curl post {url}", "post json {url}", "envoie a {url}" | powershell |
| api_health_check | Verifier si une API repond (ping HTTP) | "ping api {url}", "api en ligne {url}", "health check {url}", +1 | powershell |
| api_response_time | Mesurer le temps de reponse d'une URL | "temps de reponse {url}", "latence de {url}", "speed test {url}" | powershell |
| lint_ruff_check | Linter Python avec Ruff | "ruff check", "lint python", "verifie le code python", +1 | powershell |
| lint_ruff_fix | Auto-fixer les erreurs Ruff | "ruff fix", "fixe le lint", "corrige ruff", +1 | powershell |
| format_black | Formater Python avec Black | "black format", "formate avec black", "black le code" | powershell |
| lint_mypy | Verifier les types Python avec mypy | "mypy check", "verifie les types", "type check python", +1 | powershell |
| lint_eslint | Linter JavaScript avec ESLint | "eslint", "lint javascript", "verifie le js", +1 | powershell |
| format_prettier | Formater JS/TS avec Prettier | "prettier format", "formate avec prettier", "prettier le code" | powershell |
| logs_turbo | Voir les derniers logs JARVIS | "logs jarvis", "dernieres logs", "montre les logs", +1 | powershell |
| logs_windows_errors | Voir les erreurs recentes Windows | "erreurs windows", "logs erreurs systeme", "event log errors", +1 | powershell |
| logs_clear_turbo | Vider les logs JARVIS | "vide les logs", "efface les logs", "clear les logs", +1 | powershell |
| logs_search | Chercher dans les logs JARVIS | "cherche dans les logs {pattern}", "grep les logs {pattern}", "logs contenant {pattern}" | powershell |
| netstat_listen | Voir les ports en ecoute | "ports en ecoute", "quels ports ouverts", "netstat listen", +1 | powershell |
| whois_domain | Whois d'un domaine | "whois {domaine}", "info domaine {domaine}", "proprietaire de {domaine}" | powershell |
| ssl_check | Verifier le certificat SSL d'un site | "check ssl {domaine}", "certificat ssl {domaine}", "expire quand {domaine}", +1 | powershell |
| dns_lookup | Resoudre un domaine (DNS lookup complet) | "dns {domaine}", "resoudre {domaine}", "ip de {domaine}", +1 | powershell |
| pytest_verbose | Lancer pytest en mode verbose | "tests verbose", "pytest verbose", "lance les tests en detail", +1 | powershell |
| pytest_file | Lancer pytest sur un fichier specifique | "teste le fichier {fichier}", "pytest {fichier}", "lance les tests de {fichier}" | powershell |
| pytest_coverage | Lancer pytest avec couverture de code | "tests avec couverture", "pytest coverage", "code coverage", +1 | powershell |
| pytest_markers | Lister les markers pytest disponibles | "markers pytest", "pytest markers", "quels markers" | powershell |
| pytest_quick | Tests rapides (fail at first error) | "tests rapides", "pytest quick", "teste vite fait", +1 | powershell |
| sqlite_query | Executer une requete SQLite | "sqlite {requete}", "requete sqlite {requete}", "query sqlite {requete}" | powershell |
| sqlite_schema | Voir le schema d'une table | "schema de {table}", "structure table {table}", "describe {table}" | powershell |
| etoile_count | Compter les entrees dans etoile.db | "combien dans etoile", "entries etoile", "taille etoile db" | powershell |
| etoile_query | Requete sur etoile.db | "query etoile {requete}", "etoile db {requete}", "cherche dans etoile {requete}" | powershell |
| db_size_all | Taille de toutes les bases de donnees | "taille des bases", "poids des db", "db sizes", +1 | powershell |
| json_validate | Valider un fichier JSON | "valide le json {fichier}", "json valide {fichier}", "check json {fichier}" | powershell |
| json_pretty_file | Formatter un fichier JSON (pretty print) | "formate le json {fichier}", "pretty json {fichier}", "indente le json {fichier}" | powershell |
| csv_to_json | Convertir un CSV en JSON | "csv en json {fichier}", "convertis le csv {fichier}", "csv to json {fichier}" | powershell |
| count_lines_file | Compter les lignes d'un fichier | "combien de lignes {fichier}", "lines count {fichier}", "compte les lignes {fichier}" | powershell |
| count_lines_src | Compter les lignes de code du projet turbo | "lignes de code turbo", "combien de lignes de code", "loc turbo", +1 | powershell |
| pip_audit | Auditer les deps Python (vulnerabilites) | "pip audit", "vulnerabilites python", "securite deps python", +1 | powershell |
| bandit_scan | Scanner Python avec Bandit (securite) | "bandit scan", "securite code python", "scan bandit", +1 | powershell |
| electron_dev | Lancer Electron en mode dev | "electron dev", "lance electron", "electron en dev", +1 | powershell |
| electron_build | Builder l'app Electron | "electron build", "build electron", "compile electron", +1 | powershell |
| vite_dev | Lancer Vite en mode dev | "vite dev", "lance vite", "serveur vite", +1 | powershell |
| vite_build | Builder avec Vite | "vite build", "build vite", "compile vite" | powershell |
| vite_preview | Previsualiser le build Vite | "vite preview", "preview build", "previsualise le build" | powershell |
| python_profile | Profiler un script Python | "profile python {script}", "profiling {script}", "benchmark python {script}" | powershell |
| benchmark_import_time | Mesurer le temps d'import de turbo | "temps d'import turbo", "import time", "benchmark import", +1 | powershell |
| memory_usage_python | Utilisation memoire de Python | "memoire python", "ram python", "python memory" | powershell |

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
