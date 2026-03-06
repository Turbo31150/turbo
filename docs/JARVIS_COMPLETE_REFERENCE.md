# JARVIS Turbo v12.4 — Reference Complete

## Architecture

```
JARVIS Turbo v12.4
├── Claude Agent SDK (orchestrateur principal)
├── 13 SDK Agents (ia-deep, ia-fast, ia-check, ia-trading, ia-system, ia-bridge, ia-consensus, +6)
├── 609 MCP Handlers (602 MCP + 7 cowork = 609)
├── 2182 Commandes vocales (+ 2736 corrections + 1078 triggers + 301 dominos)
├── 80 Skills + 89 Patterns (persistants JSON)
├── 409 Scripts COWORK autonomes
├── 40 OpenClaw Agents + 56 dynamic agents
├── Brain autonome (pattern learning)
├── Dashboard Electron (React 19 + Vite 6, 29 pages)
├── Systray Windows (pystray)
└── 63 Workflows n8n
```

## Cluster IA — 3 Machines / 10 GPU / ~78 GB VRAM

| Noeud | IP | Role | GPU | VRAM | Modele |
|-------|-----|------|-----|------|--------|
| M1 | 127.0.0.1:1234 | Champion Local | 6 | 46 GB | qwen3-8b (+ gpt-oss-20b deep) |
| M2 | 192.168.1.26:1234 | Reasoning | 3 | 24 GB | deepseek-r1-0528-qwen3-8b |
| M3 | 192.168.1.113:1234 | Reasoning Fallback | 1 | 8 GB | deepseek-r1-0528-qwen3-8b |

## 13 SDK Agents

| Agent | Modele | Role | Tools |
|-------|--------|------|-------|
| ia-deep | Opus | Architecte, analyse profonde | Read, Glob, Grep, WebSearch, WebFetch + bridges |
| ia-fast | Haiku | Ingenieur, execution rapide | Read, Write, Edit, Bash, Glob, Grep |
| ia-check | Sonnet | Validateur, review, tests | Read, Bash, Glob, Grep + bridges |
| ia-trading | Sonnet | Trading MEXC Futures 10x | Read, Bash, Glob, Grep, run_script, lm_query, consensus |
| ia-system | Haiku | Operations Windows | Read, Write, Edit, Bash, Glob, Grep |
| ia-bridge | Sonnet | Orchestrateur multi-noeuds | gemini_query, bridge_query, bridge_mesh |
| ia-consensus | Sonnet | Vote pondere multi-IA | M1=1.5, GEMINI=1.2, M2=1.0, OL1=0.8, M3=0.5 |

## 609 MCP Handlers (602 MCP + 7 cowork)

### LM Studio (4)
1. `lm_query` — Interroger un noeud LM Studio
2. `lm_models` — Lister les modeles charges
3. `lm_cluster_status` — Sante du cluster
4. `consensus` — Consensus multi-IA

### Scripts (3)
5. `run_script` — Executer un script indexe
6. `list_scripts` — Lister les scripts
7. `list_project_paths` — Chemins des projets

### Applications (3)
8. `open_app` — Ouvrir une application
9. `close_app` — Fermer une application
10. `open_url` — Ouvrir une URL

### Processus (2)
11. `list_processes` — Lister les processus
12. `kill_process` — Tuer un processus

### Fenetres (4)
13. `list_windows` — Lister les fenetres
14. `focus_window` — Focus sur une fenetre
15. `minimize_window` — Minimiser
16. `maximize_window` — Maximiser

### Clavier/Souris (4)
17. `send_keys` — Envoyer des touches
18. `type_text` — Taper du texte
19. `press_hotkey` — Raccourci clavier
20. `mouse_click` — Clic souris

### Presse-papier (2)
21. `clipboard_get` — Lire le presse-papier
22. `clipboard_set` — Ecrire dans le presse-papier

### Fichiers (9)
23. `open_folder` — Ouvrir un dossier
24. `list_folder` — Lister le contenu
25. `create_folder` — Creer un dossier
26. `copy_item` — Copier
27. `move_item` — Deplacer
28. `delete_item` — Supprimer
29. `read_text_file` — Lire un fichier
30. `write_text_file` — Ecrire un fichier
31. `search_files` — Chercher des fichiers

### Audio (3)
32. `volume_up` — Augmenter le volume
33. `volume_down` — Baisser le volume
34. `volume_mute` — Couper/activer le son

### Ecran (2)
35. `screenshot` — Capture d'ecran
36. `screen_resolution` — Resolution ecran

### Systeme (8)
37. `system_info` — Informations systeme
38. `gpu_info` — Informations GPU
39. `network_info` — Informations reseau
40. `powershell_run` — Executer PowerShell
41. `lock_screen` — Verrouiller
42. `shutdown_pc` — Eteindre
43. `restart_pc` — Redemarrer
44. `sleep_pc` — Veille

### Services (3)
45. `list_services` — Lister les services
46. `start_service` — Demarrer un service
47. `stop_service` — Arreter un service

### Reseau (3)
48. `wifi_networks` — Scanner Wi-Fi
49. `ping` — Ping un hote
50. `get_ip` — Adresse IP

### Registre (2)
51. `registry_read` — Lire le registre
52. `registry_write` — Ecrire dans le registre

### Notifications/Voix (3)
53. `notify` — Notification Windows
54. `speak` — Synthese vocale TTS
55. `scheduled_tasks` — Taches planifiees

### Trading (5)
56. `trading_pending_signals` — Signaux en attente
57. `trading_execute_signal` — Executer un signal
58. `trading_positions` — Positions ouvertes
59. `trading_status` — Status pipeline
60. `trading_close_position` — Fermer une position

### Skills (5)
61. `list_skills` — Lister les skills
62. `create_skill` — Creer un skill
63. `remove_skill` — Supprimer un skill
64. `suggest_actions` — Suggestions
65. `action_history` — Historique des actions

### Brain (4)
66. `brain_status` — Status du cerveau
67. `brain_analyze` — Analyser les patterns
68. `brain_suggest` — Suggestion IA du cluster
69. `brain_learn` — Auto-apprentissage

## 2182 Commandes Vocales (3895 total vocal entries)

### Navigation Web (13)
- ouvre chrome / ouvre comet / va sur {site} / cherche {requete}
- cherche sur youtube {requete} / ouvre gmail / ouvre youtube
- ouvre github / ouvre tradingview / ouvre mexc
- nouvel onglet / ferme l'onglet / ajoute aux favoris

### Fichiers & Documents (10)
- ouvre mes documents / ouvre le bureau / ouvre le dossier {dossier}
- ouvre les telechargements / ouvre mes images / ouvre ma musique
- ouvre mes projets / ouvre l'explorateur / liste le dossier {dossier}
- cree un dossier {nom} / cherche le fichier {nom}

### Applications (10)
- ouvre vscode / ouvre le terminal / ouvre lm studio
- ouvre discord / ouvre spotify / ouvre le gestionnaire de taches
- ouvre notepad / ouvre la calculatrice / ferme {app} / ouvre {app}

### Controle Media (7)
- play/pause / suivant / precedent / monte le volume
- baisse le volume / muet / volume a {niveau}

### Fenetres Windows (9)
- minimise tout / alt tab / ferme la fenetre / maximise
- minimise / fenetre a gauche / fenetre a droite
- focus sur {titre} / liste les fenetres

### Presse-papier & Saisie (11)
- copie / colle / coupe / selectionne tout / annule
- ecris {texte} / sauvegarde / refais / recherche dans la page
- lis le presse-papier / historique du presse-papier

### Systeme Windows (50+)
- verrouille / eteins / redemarre / veille / capture ecran
- info systeme / info gpu / info reseau / processus
- kill {nom} / scan wifi / ping {host} / vide la corbeille
- mode nuit / ouvre executer / recherche windows
- notifications / widgets / emojis / projeter l'ecran
- bureaux virtuels / parametres wifi/bluetooth/affichage/son
- stockage / mises a jour / alimentation
- bluetooth on/off / luminosite +/- / services
- mode avion / micro mute/unmute / camera

### Trading & IA (30+)
- lance le cluster / cluster status / modeles charges
- consensus {question} / query {question} / lance un scan
- scanner mexc / breakout detector / pipeline intensif
- positions ouvertes / signaux en attente / execute le signal
- ferme la position / status trading
- liste les scripts / lance le script {nom}

### Controle JARVIS (20+)
- status / aide / liste les commandes / skills
- brain status / brain learn / nouveau skill
- lance le skill {nom} / historique / suggestions
- rapport du matin / mode trading / mode dev
- mode gaming / diagnostic complet

### Accessibilite (10+)
- loupe / narrateur / clavier virtuel / contraste eleve
- dictee vocale / mode daltonien / sous-titres

### Chrome Avance (10+)
- historique chrome / telechargements / favoris
- zoom in/out / mode incognito / ouvrir devtools
- plein ecran / restaure la fenetre

### Docker/Git/Dev (15+)
- docker ps / docker images / docker restart
- git status / git pull / git push / git log
- pip list / jupyter notebook / lance n8n / lance lm studio
- wifi profils / wifi connect {nom}

### Hardware/Systeme Avance (20+)
- info cpu / info ram / info carte mere / info bios
- info gpu detaille / info disques / sante ssd
- temperature cpu / rapport batterie / uptime
- processeur / resolution ecran / fullscreen

## 80 Skills / 66 Pipelines

### Routines (6)
1. `rapport_matin` — Cluster + trading + systeme
2. `routine_soir` — Sauvegarde + ferme apps + mode nuit
3. `pause_cafe` — Save + mute + lock
4. `retour_pause` — Volume + check + notification
5. `rapport_soir` — Bilan trading + cluster + historique
6. `fin_journee` — Save + heure + notification

### Trading (3)
7. `mode_trading` — Chrome + TradingView + pipeline + cluster
8. `consensus_trading` — Status + consensus multi-IA
9. `check_trading_complet` — Status + positions + signaux + cluster + consensus

### Dev (8)
10. `mode_dev` — Cursor + Terminal + cluster
11. `workspace_frontend` — VSCode + Terminal + localhost:3000
12. `workspace_backend` — VSCode + Terminal + LM Studio
13. `workspace_turbo` — VSCode + Terminal + GitHub + cluster
14. `workspace_data` — Chrome + LM Studio + Terminal + Jupyter
15. `workspace_ml` — LM Studio + Chrome + Jupyter + GPU
16. `mode_ia` — LM Studio + cluster + modeles
17. `mode_docker` — Conteneurs + images + espace
18. `deploiement` — Terminal + systeme + services + reseau

### Productivite (10)
19. `mode_focus` — Ferme distractions + mute
20. `mode_presentation` — Projection + luminosite + volume
21. `split_screen_travail` — Chrome gauche + VSCode droite
22. `backup_rapide` — Save + screenshot + notification
23. `mode_recherche` — Chrome + Google + Perplexity
24. `session_creative` — Spotify + focus + luminosite
25. `mode_double_ecran` — Etendre + snap layout
26. `mode_partage_ecran` — Miracast + luminosite
27. `mode_4_fenetres` — Snap 4 coins + luminosite
28. `mode_dual_screen` — Etendre + luminosite uniforme

### Loisir (5)
29. `mode_gaming` — Ferme Chrome + Steam + volume max
30. `mode_musique` — Spotify + volume agreable
31. `mode_stream` — OBS + Chrome + volume
32. `mode_cinema` — Ferme distractions + volume max + luminosite
33. `mode_confort` — Night light + luminosite + volume

### Systeme (17)
34. `diagnostic_complet` — Systeme + GPU + cluster + reseau
35. `cleanup_ram` — Verifier RAM + lister processus
36. `ferme_tout` — Ferme Chrome + Discord + Spotify
37. `optimiser_pc` — Diagnostic + processus + corbeille + GPU
38. `monitoring_complet` — Systeme + GPU + reseau + cluster + services
39. `update_systeme` — Save + disque + check
40. `mode_securite` — Save + Bluetooth off + mute
41. `mode_accessibilite` — Loupe + clavier visuel
42. `mode_economie_energie` — Plan eco + luminosite + Bluetooth off
43. `mode_performance_max` — Plan haute perf + luminosite max
44. `clean_reseau` — Flush DNS + scan wifi + ping
45. `nettoyage_complet` — Temp + corbeille + DNS + diagnostic
46. `check_espace_disque` — Espace + temp
47. `audit_securite` — Windows Security + services + reseau
48. `maintenance_complete` — Temp + corbeille + disque + diagnostic + GPU
49. `diagnostic_demarrage` — Apps startup + services + systeme + disque
50. `mode_nuit_complet` — Mode sombre + luminosite basse + volume bas

### Reseau (2)
51. `debug_reseau` — Info + wifi + ping gateway + ping Google
52. `diagnostic_reseau_complet` — IP + MAC + Wi-Fi + ping + DNS

### Communication (2)
53. `mode_reunion` — Teams + volume bas
54. `mode_communication` — Discord + Telegram + Gmail

### Sante (3)
55. `diagnostic_sante_pc` — Systeme + GPU + uptime + disque
56. `preparation_backup` — Save + disque + check
57. `rapport_batterie` — Niveau + sante + estimation

### Ambiance (2)
58. `mode_jour` — Mode clair + luminosite haute + volume
59. `nettoyage_clipboard` — Clipboard + temp

### Docker (2)
60. `git_workflow` — Status + diff + log
61. `debug_docker` — Conteneurs + volumes + nettoyage

### Accessibilite (2)
62. `mode_accessibilite_complet` — Clavier virtuel + loupe
63. `navigation_rapide` — Chrome + onglet + zoom reset

### Inventaire (2)
64. `inventaire_hardware` — CPU + RAM + GPU + carte mere + disques + BIOS
65. `inventaire_apps` — Apps installees + versions dev + PATH
66. `check_performances` — CPU load + RAM + top 5 + GPU

## Trading Config

- Exchange: MEXC Futures
- Levier: 10x
- TP: 0.4% / SL: 0.25%
- Paires: BTC, ETH, SOL, SUI, PEPE, DOGE, XRP, ADA, AVAX, LINK
- Dry run par defaut

## Modes de Lancement

| Lanceur | Description |
|---------|-------------|
| `jarvis.bat` | Dashboard TUI + Systray complet |
| `jarvis_dashboard.bat` | Dashboard TUI seul |
| `jarvis_systray.bat` | Systray seul |
| `jarvis_interactive.bat` | Mode interactif CLI |
| `jarvis_hybrid.bat` | Mode hybride (voix + texte) |
| `jarvis_voice.bat` | Mode vocal pur |

## Workflows n8n (63)

| Workflow | Frequence | Description |
|----------|-----------|-------------|
| `jarvis_cluster_monitor` | 5 min | Surveille les 3 noeuds, alerte si offline |
| `jarvis_trading_pipeline` | 15 min | Consensus multi-IA sur crypto |
| `jarvis_daily_report` | 8h00 | Rapport matin vocal complet |
| `jarvis_system_health` | 10 min | CPU/RAM/disque, alerte vocale si critique |
| `jarvis_brain_learning` | 1h | Auto-apprentissage patterns |
| `jarvis_git_auto_backup` | 6h | Commit + push auto si changements |

## Fichiers Sources (246 modules src/, ~93,294 LOC)

| Fichier | LOC | Role |
|---------|-----|------|
| `src/config.py` | 178 | Configuration cluster, modeles, routing, trading |
| `src/agents.py` | 129 | 7 SDK agents Claude |
| `src/tools.py` | 528 | MCP tools pour SDK |
| `src/mcp_server.py` | 648 | Serveur MCP stdio 609 handlers |
| `src/orchestrator.py` | 643 | Client SDK, modes interactif/voice/hybrid |
| `src/commands.py` | 1840 | 955 commandes vocales + corrections |
| `src/skills.py` | 1338 | 66 pipelines + gestion skills |
| `src/executor.py` | 412 | Execution commandes et pipelines |
| `src/brain.py` | 323 | Apprentissage autonome |
| `src/windows.py` | 575 | Operations Windows/PowerShell |
| `src/trading.py` | 484 | Integration MEXC Futures |
| `src/voice.py` | 104 | Whisper STT + SAPI TTS |
| `src/voice_correction.py` | 559 | Pipeline correction vocale |
| `src/dashboard.py` | 527 | Dashboard TUI Textual |
| `src/systray.py` | 156 | Icone systray Windows |
| `src/output.py` | 149 | Schema JSON sortie |
| `src/__init__.py` | - | Package init |

## Installation Rapide

```bash
# Cloner le repo
git clone https://github.com/Turbo31150/turbo.git
cd turbo

# Installer les dependances
uv sync

# Configurer (.env)
cp .env.example .env
# Editer: MEXC_API_KEY, MEXC_SECRET_KEY, TELEGRAM_TOKEN, etc.

# Lancer
jarvis.bat          # Dashboard complet
jarvis_voice.bat    # Mode vocal
jarvis_interactive.bat  # Mode CLI
```

## System Prompt JARVIS

Le system prompt complet est dans `src/orchestrator.py`. Il definit JARVIS comme un orchestrateur IA multi-modal francophone avec acces a 609 MCP handlers, 13 SDK agents, 40 OpenClaw agents + 56 dynamic, et un cluster de 10 GPU.

## Statistiques globales (MaJ 2026-03-06)

| Metrique | Valeur |
|----------|--------|
| Modules src/ | 246 (93,294 lignes) |
| Scripts COWORK | 409 |
| MCP Handlers | 609 (602 + 7 cowork) |
| REST Endpoints | 517 |
| Tests (fonctions) | 2241 (77 fichiers) |
| Tables etoile.db | 42 (13,488 rows) |
| Workflows n8n | 63 |
| OpenClaw Agents | 40 + 56 dynamic |
| Skills | 80 |
| Patterns | 89 |
| SDK Agents | 13 |
| Launchers | 35 |
| Electron Pages | 29 |
| Commandes vocales | 2182 (3895 total vocal entries) |
| Cluster | M1 (qwen3-8b 46tok/s), M2 (qwen3-8b 42tok/s), M3 (mistral-7b 5.8tok/s), OL1 (qwen3:1.7b + cloud), Gemini, Claude |
