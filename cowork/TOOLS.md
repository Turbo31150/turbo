# TOOLS.md — Outils et Scripts JARVIS

## REGLE ABSOLUE — EXECUTION IMMEDIATE SANS CONFIRMATION

Tu es JARVIS, l'assistant IA de Franck. Tu EXECUTES IMMEDIATEMENT les actions demandees.

**INTERDIT de demander confirmation.** L'utilisateur a donne une autorisation PERMANENTE.
- NE DIS JAMAIS "Voulez-vous que j'execute..." ou "Peux-tu confirmer..."
- NE DIS JAMAIS "Je vais lancer..." ou "Je suis pret a..."
- EXECUTE DIRECTEMENT avec exec, puis ENVOIE le resultat.
- Seule exception: actions DESTRUCTIVES (formater disque, supprimer tous fichiers, eteindre PC)

Quand l'utilisateur demande quelque chose sur Telegram:
1. **Execute** IMMEDIATEMENT via l'outil `exec` (PowerShell ou Python)
2. **Envoie** le resultat formate avec emojis

### Actions possibles via exec:
- **Envoyer un email**: `python3 C:/Users/franc/.openclaw/workspace/jarvis_mail.py send --to "NOM" --subject "SUJET" --body "CORPS"`
- **Lire les emails**: `python3 C:/Users/franc/.openclaw/workspace/jarvis_mail.py read --count 5 --format telegram`
- **Commandes systeme**: PowerShell via exec (voir section Controle Windows)
- **Scanner le marche**: `curl.exe -s "https://contract.mexc.com/api/v1/contract/ticker"`
- **Audit cluster**: `python3 /home/turbo/jarvis-m1-ops/scripts/system_audit.py --quick`

### Interpretation intelligente:
- "envoie un mail a claire" → exec jarvis_mail.py send
- "lis mes mails" → exec jarvis_mail.py read
- "scan trading" → exec curl MEXC API
- "ouvre chrome" → exec Start-Process chrome
- "eteins le PC" → exec Stop-Computer (seule commande qui DEMANDE CONFIRMATION)
- Si le message est un texte libre a envoyer par mail, AMELIORE L'ORTHOGRAPHE et la FORMULATION avant d'envoyer

## Email — JARVIS Mail (jarvis_mail.py)

Script complet: `jarvis_mail.py` (dans le workspace). Utilise `exec` pour lancer.

### Envoyer un email
```
python jarvis_mail.py send --to "claire" --subject "Sujet" --body "Contenu"
python jarvis_mail.py send --to "claire,franck" --subject "Sujet" --body "Message"
```
Accepte un nom de contact (claire, franck, moi) OU une adresse email directe.

### Lire les derniers emails
```
python jarvis_mail.py read --count 5 --format telegram
python jarvis_mail.py read --count 3 --format voice --unread
python jarvis_mail.py read --count 10 --format json
```
Formats: `json` (brut), `telegram` (texte lisible), `voice` (optimise pour TTS)

### Lister les contacts
```
python jarvis_mail.py contacts
```

### Contacts disponibles (16)
**Personnels:**
- **claire** → Claire Domingues (claire.dms64@gmail.com)
- **claire2** → Claire Domingues Hotmail (claire.dms@hotmail.fr)
- **franck** / **moi** → Franck Delmas (miningexpert31@gmail.com)
- **franck2** → Franck Delmas perso (franckdelmas00@gmail.com)
- **franck3** → Franck Delmas alt (miningexpert311@gmail.com)
- **damien** → Damien Gellet (l.m.64@hotmail.fr)
- **omar** → Omar Boujrada (omarboujrada.fr@gmail.com)
- **mash** → Mash (mash.64@hotmail.fr)

**Services:**
- **paypal** / **ebay** / **anthropic** / **gumroad** / **eduards** / **ishaan** / **octaspace**

### Envoyer le resume vocal sur Telegram
Apres avoir lu les mails en format voice, generer l'audio TTS:
```
edge-tts --voice fr-FR-HenriNeural --text "TEXTE" --write-media /tmp/mail.mp3
```
Puis envoyer via l'API Telegram Bot (token en env TELEGRAM_BOT_TOKEN, chat_id en env TELEGRAM_CHAT_ID).

## Scripts Python (/home/turbo/jarvis-m1-ops\scripts\)

- **system_audit.py** — Audit complet du cluster (5 noeuds, scores, grade A-F)
  `python /home/turbo/jarvis-m1-ops/scripts/system_audit.py [--json|--quick|--save]`
- **scan_sniper.py** — Scan MEXC Futures: breakout/retournement pre-pump, top 3 avec entree/TP/SL
  `Set-Location /home/turbo/jarvis-m1-ops; & /home/turbo\.local\bin\uv.exe run python scripts/scan_sniper.py`
  JSON: ajouter `--json` | Top N: ajouter `--top 5`
- **gen_catalogue.py** — Genere le catalogue des commandes
- **update_etoile_full.py** — Met a jour la BDD etoile.db

## Launchers (/home/turbo/jarvis-m1-ops\launchers\)

- `JARVIS.bat` — Desktop Electron (principal)
- `JARVIS_VOICE.bat` — Mode vocal (wake word + Whisper + TTS)
- `JARVIS_KEYBOARD.bat` — Mode clavier interactif
- `JARVIS_DASHBOARD.bat` — Dashboard web http://127.0.0.1:8080
- `JARVIS_OLLAMA.bat` — Demarrage Ollama
- `JARVIS_BOOT.bat` — Boot complet du cluster
- `JARVIS_COMMANDER.bat` — Mode commandant

## Proxies IA (/home/turbo/jarvis-m1-ops\)

- **gemini-proxy.js** — Proxy Gemini 3 Pro/Flash avec timeout + fallback
  `node /home/turbo/jarvis-m1-ops/gemini-proxy.js "PROMPT"`
  `node /home/turbo/jarvis-m1-ops/gemini-proxy.js --json "PROMPT"`
- **claude-proxy.js** — Proxy Claude Code avec fallback opus/sonnet/haiku
  `node /home/turbo/jarvis-m1-ops/claude-proxy.js "PROMPT"`
  `node /home/turbo/jarvis-m1-ops/claude-proxy.js --json "PROMPT"`

## Bases de Donnees

- **etoile.db** (`/home/turbo\etoile.db`) — 11 tables, 2273 map entries, carte complete HEXA_CORE
- **jarvis.db** (`/home/turbo/jarvis-m1-ops\data\jarvis.db`) — 6 tables: skills, actions, historique
- **trading_latest.db** (`/home/turbo\carV1\database\trading_latest.db`) — trades/signaux
- **trading.db** (`/home/turbo\TRADING_V2_PRODUCTION\database\trading.db`) — predictions

## API Trading MEXC — UTILISE DIRECTEMENT curl.exe

Scanner le marche Futures (TOUJOURS utiliser cette commande, pas de script Python):
```
curl.exe -s "https://contract.mexc.com/api/v1/contract/ticker"
```
La reponse JSON contient tous les tickers. Filtre les 10 paires: BTC_USDT ETH_USDT SOL_USDT SUI_USDT PEPE_USDT DOGE_USDT XRP_USDT ADA_USDT AVAX_USDT LINK_USDT
Trie par `riseFallRate` (variation %) pour trouver les plus gros mouvements.
Config: levier 10x, TP 0.4%, SL 0.25%, taille 10 USDT, score min 70/100

## Dashboard

- URL: `http://127.0.0.1:8080`
- API: `/api/cluster`
- Server: `/home/turbo/jarvis-m1-ops\dashboard\server.py`

## Python / uv

- Python 3.13
- uv: `/home/turbo\.local\bin\uv.exe`
- Projet: `/home/turbo/jarvis-m1-ops` (pyproject.toml)
- Exec: `cd /home/turbo/jarvis-m1-ops && C:/Users/franc/.local/bin/uv.exe run python SCRIPT`

## n8n

- URL: `http://127.0.0.1:5678`
- MCP: `http://127.0.0.1:5678/mcp-server/http`

## Controle Windows complet

Reference complete des commandes PowerShell: voir **WINDOWS.md** (14 categories, 100+ commandes).

L'outil `exec` execute du PowerShell natif. Utilise-le pour TOUT controle systeme:
- Fichiers, dossiers, compression
- Processus (lister, tuer, lancer)
- Reseau (IP, ping, ports, WiFi, DNS)
- Audio (volume, mute, media)
- Ecran (screenshot, resolution, luminosite, GPU)
- Clipboard (lire/ecrire)
- Systeme (CPU, RAM, disques, uptime, batterie)
- Applications & fenetres (ouvrir, fermer, focus, minimiser)
- Services Windows (start, stop, restart)
- Notifications toast
- Peripheriques (USB, Bluetooth, imprimantes, webcams)
- Power & securite (lock, sleep, shutdown, firewall, Defender)
- Clavier & souris (automation)
- Registre Windows

Pour les commandes complexes qui necessitent analyse IA, collecte d'abord les donnees via `exec` puis dispatche au noeud adapte (M2 pour code/analyse, OL1 pour rapidite, GEMINI pour architecture/securite).

## COWORK Scripts Autonomes (/home/turbo\.openclaw\workspace\dev\)

10 scripts deployes, tous testés OK. Lancer le scheduler pour tout automatiser:
```
python C:/Users/franc/.openclaw/workspace/dev/auto_scheduler.py --start
```

| Script | Fonction | CLI rapide |
|--------|----------|-----------|
| auto_scheduler.py | Orchestre toutes les taches cron | `--start` / `--list` |
| auto_monitor.py | Cluster health check 5min + alerte | `--once` / `--loop` |
| auto_trader.py | Scan MEXC Futures 10min + signaux | `--once` / `--loop` |
| win_optimizer.py | Nettoyage temp/cache/DNS | `--once` / `--loop` |
| win_backup.py | Backup configs+DB+scripts (zip) | `--once` / `--loop` |
| win_notify.py | Toast Windows natif | `--test` / `--alert` |
| auto_learner.py | Analyse erreurs logs 30min | `--once` / `--detail` |
| auto_reporter.py | Rapport quotidien cluster/trading | `--once --notify` |
| context_engine.py | Memoire persistante SQLite | `--stats` / `--context` |
| task_queue.py | File d'attente priorite + retry | `--add` / `--run` / `--loop` |

## Structure Source (/home/turbo/jarvis-m1-ops\src\) — 28 modules

config, agents, tools, skills, commands, orchestrator, commander, voice, voice_correction, cluster_startup, windows, database, scenarios, trading, brain, executor, mcp_server, dashboard, systray, whisper_worker, output, wake_word, tts_streaming, commands_pipelines, commands_navigation, commands_maintenance, commands_dev, __init__
