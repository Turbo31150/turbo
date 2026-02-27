"""JARVIS — Domino Pipelines: cascades automatiques declenchees par commande vocale.

Chaque DominoPipeline definit une chaine d'actions ou chaque etape declenche
automatiquement la suivante. Le systeme apprend du contexte (heure, GPU, cluster)
pour adapter les cascades dynamiquement.

Architecture:
  trigger vocal -> etape1 -> etape2 -> ... -> etapeN
  Chaque etape peut etre: pipeline existant, commande powershell, curl API, ou condition.

Genere par consensus cluster M1+M2+OL1 (2026-02-27).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DominoStep:
    """Une etape dans une cascade domino."""
    name: str                   # Identifiant de l'etape
    action: str                 # Action a executer (pipeline ref, powershell, curl, etc.)
    action_type: str            # Type: pipeline, powershell, curl, python, condition
    condition: Optional[str] = None  # Condition optionnelle (ex: "gpu_temp < 80")
    on_fail: str = "stop"       # Comportement si echec: stop, skip, fallback
    timeout_s: int = 30         # Timeout par etape


@dataclass
class DominoPipeline:
    """Pipeline domino — cascade d'actions declenchees par une commande vocale."""
    id: str                     # Identifiant unique
    trigger_vocal: list[str]    # Phrases vocales pour declencher
    steps: list[DominoStep]     # Etapes en cascade
    category: str               # Categorie domino
    description: str            # Description de la cascade
    learning_context: str       # Contexte pour l'apprentissage IA
    priority: str = "normal"    # normal, high, critical
    cooldown_s: int = 60        # Temps min entre 2 executions


# ══════════════════════════════════════════════════════════════════════════════
# DOMINO PIPELINES — Generes par consensus cluster M1+M2+OL1
# ══════════════════════════════════════════════════════════════════════════════

DOMINO_PIPELINES: list[DominoPipeline] = [

    # ─────────────────────────────────────────────────────────────────────
    # ROUTINE MATIN (5 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_matin_complet",
        trigger_vocal=["bonjour jarvis", "routine du matin", "demarre la journee", "lance le matin"],
        steps=[
            DominoStep("check_gpu", "powershell:nvidia-smi --query-gpu=temperature.gpu,memory.used --format=csv,noheader", "powershell"),
            DominoStep("cluster_health", "curl:http://10.5.0.2:1234/api/v1/models", "curl"),
            DominoStep("meteo_brief", "curl:http://127.0.0.1:11434/api/chat", "curl"),
            DominoStep("agenda_resume", "powershell:Get-Date -Format 'dddd dd MMMM yyyy HH:mm'", "powershell"),
            DominoStep("tts_briefing", "python:edge_tts_speak('Bonjour! Briefing du matin pret.')", "python"),
        ],
        category="routine_matin",
        description="Briefing matinal complet: GPU, cluster, meteo, agenda, synthese vocale",
        learning_context="L'utilisateur demarre sa journee — adapter selon l'heure et le jour de la semaine",
        priority="high",
    ),
    DominoPipeline(
        id="domino_cafe_code",
        trigger_vocal=["mode cafe code", "session cafe dev", "code du matin"],
        steps=[
            DominoStep("open_vscode", "app_open:code", "pipeline"),
            DominoStep("git_status", "powershell:git -C 'F:\\BUREAU\\turbo' status --short", "powershell"),
            DominoStep("open_spotify", "app_open:spotify", "pipeline"),
            DominoStep("cluster_check", "curl:http://10.5.0.2:1234/api/v1/models", "curl"),
            DominoStep("tts_ready", "python:edge_tts_speak('Environnement dev pret. Bon code!')", "python"),
        ],
        category="routine_matin",
        description="Setup matinal dev: VSCode + git + musique + cluster",
        learning_context="Session de dev matinale — prefere musique lo-fi et branche principale",
    ),
    DominoPipeline(
        id="domino_reveil_rapide",
        trigger_vocal=["reveil rapide", "demarrage express", "vite jarvis"],
        steps=[
            DominoStep("gpu_temp", "powershell:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader", "powershell"),
            DominoStep("date_heure", "powershell:Get-Date -Format 'HH:mm dddd'", "powershell"),
            DominoStep("tts_status", "python:edge_tts_speak('Systeme operationnel.')", "python"),
        ],
        category="routine_matin",
        description="Demarrage ultra-rapide: GPU + heure + confirmation vocale",
        learning_context="Demarrage rapide sans details — utilisateur presse",
    ),
    DominoPipeline(
        id="domino_matin_trading",
        trigger_vocal=["matin trading", "routine trading matin", "bonjour trading"],
        steps=[
            DominoStep("market_check", "curl:http://10.5.0.2:1234/api/v1/chat", "curl"),
            DominoStep("portfolio_status", "python:check_portfolio_balance()", "python"),
            DominoStep("signals_scan", "curl:http://10.5.0.2:1234/api/v1/chat", "curl"),
            DominoStep("alert_config", "python:configure_trading_alerts()", "python"),
            DominoStep("tts_market", "python:edge_tts_speak('Marche analyse. Signaux prets.')", "python"),
        ],
        category="routine_matin",
        description="Routine matin trading: marche + portfolio + signaux + alertes",
        learning_context="Trader matinal — BTC/ETH prioritaires, check drawdown avant tout",
        priority="high",
    ),
    DominoPipeline(
        id="domino_matin_weekend",
        trigger_vocal=["bonjour weekend", "matin tranquille", "routine weekend"],
        steps=[
            DominoStep("gpu_light", "powershell:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader", "powershell"),
            DominoStep("backup_check", "python:check_last_backup_date()", "python"),
            DominoStep("tts_weekend", "python:edge_tts_speak('Bon weekend! Systeme stable.')", "python"),
        ],
        category="routine_matin",
        description="Routine weekend allegee: GPU + backup + message",
        learning_context="Weekend — pas de trading, juste maintenance legere",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # TRADING CASCADE (5 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_trading_full_scan",
        trigger_vocal=["scan trading complet", "analyse complete marche", "trading full scan"],
        steps=[
            DominoStep("fetch_prices", "curl:http://10.5.0.2:1234/api/v1/chat", "curl"),
            DominoStep("correlation_check", "curl:http://10.5.0.2:1234/api/v1/chat", "curl"),
            DominoStep("signal_generate", "curl:http://10.5.0.2:1234/api/v1/chat", "curl"),
            DominoStep("risk_assess", "python:assess_trading_risk()", "python"),
            DominoStep("tts_signal", "python:edge_tts_speak('Scan termine. Signaux generes.')", "python"),
        ],
        category="trading_cascade",
        description="Scan trading complet: prix + correlation + signaux + risque",
        learning_context="Scan de marche complet — 10 paires MEXC, score min 70/100",
        priority="high",
    ),
    DominoPipeline(
        id="domino_trading_execute",
        trigger_vocal=["execute signal trading", "trade maintenant", "passe l'ordre"],
        steps=[
            DominoStep("confirm_signal", "python:validate_signal_score()", "python"),
            DominoStep("check_balance", "python:check_usdt_balance()", "python"),
            DominoStep("place_order", "python:execute_mexc_order()", "python", on_fail="stop"),
            DominoStep("set_tp_sl", "python:set_tp_sl_levels()", "python"),
            DominoStep("tts_confirm", "python:edge_tts_speak('Ordre place. TP et SL configures.')", "python"),
        ],
        category="trading_cascade",
        description="Execution trading: validation + balance + ordre + TP/SL",
        learning_context="Execution d'ordre — TOUJOURS verifier score >= 70 et balance suffisante",
        priority="critical",
        cooldown_s=120,
    ),
    DominoPipeline(
        id="domino_trading_close_all",
        trigger_vocal=["ferme tout trading", "close all positions", "urgence trading stop"],
        steps=[
            DominoStep("list_positions", "python:list_open_positions()", "python"),
            DominoStep("close_positions", "python:close_all_positions()", "python", on_fail="stop"),
            DominoStep("calculate_pnl", "python:calculate_session_pnl()", "python"),
            DominoStep("save_report", "python:save_trading_report()", "python"),
            DominoStep("tts_closed", "python:edge_tts_speak('Toutes positions fermees. PnL calcule.')", "python"),
        ],
        category="trading_cascade",
        description="Fermeture urgente: lister + fermer + PnL + rapport",
        learning_context="Fermeture d'urgence — priorite absolue, pas de confirmation intermediaire",
        priority="critical",
        cooldown_s=30,
    ),
    DominoPipeline(
        id="domino_trading_backtest",
        trigger_vocal=["lance un backtest", "backtest strategie", "simule le trading"],
        steps=[
            DominoStep("load_history", "python:load_price_history('1h', 30)", "python"),
            DominoStep("run_backtest", "curl:http://10.5.0.2:1234/api/v1/chat", "curl"),
            DominoStep("analyze_results", "python:analyze_backtest_results()", "python"),
            DominoStep("tts_result", "python:edge_tts_speak('Backtest termine.')", "python"),
        ],
        category="trading_cascade",
        description="Backtest complet: historique + simulation + analyse",
        learning_context="Backtest — utiliser M1 pour analyse, 30 jours par defaut en 1h",
    ),
    DominoPipeline(
        id="domino_trading_drawdown_alert",
        trigger_vocal=["check drawdown", "alerte pertes", "risque portfolio"],
        steps=[
            DominoStep("fetch_pnl", "python:fetch_current_pnl()", "python"),
            DominoStep("calc_drawdown", "python:calculate_drawdown()", "python"),
            DominoStep("eval_risk", "curl:http://10.5.0.2:1234/api/v1/chat", "curl"),
            DominoStep("tts_alert", "python:edge_tts_speak('Drawdown analyse complete.')", "python"),
        ],
        category="trading_cascade",
        description="Analyse drawdown: PnL + calcul + evaluation risque",
        learning_context="Drawdown — alerte si > 5% du capital, suggestion close si > 8%",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # DEBUG CASCADE (5 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_debug_cluster",
        trigger_vocal=["debug cluster", "probleme cluster", "cluster en panne"],
        steps=[
            DominoStep("ping_m1", "curl:http://10.5.0.2:1234/api/v1/models", "curl", on_fail="skip"),
            DominoStep("ping_m2", "curl:http://192.168.1.26:1234/api/v1/models", "curl", on_fail="skip"),
            DominoStep("ping_m3", "curl:http://192.168.1.113:1234/api/v1/models", "curl", on_fail="skip"),
            DominoStep("ping_ol1", "curl:http://127.0.0.1:11434/api/tags", "curl", on_fail="skip"),
            DominoStep("tts_report", "python:edge_tts_speak('Diagnostic cluster termine.')", "python"),
        ],
        category="debug_cascade",
        description="Debug cluster: ping tous les noeuds + rapport",
        learning_context="Debug cluster — identifier noeud offline, suggerer fallback",
        priority="high",
    ),
    DominoPipeline(
        id="domino_debug_gpu_thermal",
        trigger_vocal=["debug gpu chaud", "gpu surchauffe", "thermal throttle"],
        steps=[
            DominoStep("read_temps", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,power.draw --format=csv,noheader", "powershell"),
            DominoStep("check_fans", "powershell:nvidia-smi --query-gpu=fan.speed --format=csv,noheader", "powershell"),
            DominoStep("eval_thermal", "curl:http://10.5.0.2:1234/api/v1/chat", "curl"),
            DominoStep("throttle_if_hot", "python:throttle_gpu_if_critical(85)", "python", condition="gpu_temp > 80"),
            DominoStep("tts_thermal", "python:edge_tts_speak('Diagnostic thermique GPU termine.')", "python"),
        ],
        category="debug_cascade",
        description="Debug thermal GPU: temperatures + ventilateurs + throttle auto",
        learning_context="GPU chaud — 75C warning, 85C critical, throttle automatique",
        priority="critical",
    ),
    DominoPipeline(
        id="domino_debug_network",
        trigger_vocal=["debug reseau", "probleme connexion", "reseau en panne"],
        steps=[
            DominoStep("ping_gateway", "powershell:Test-Connection 192.168.1.1 -Count 2 -TimeoutSeconds 3", "powershell"),
            DominoStep("ping_internet", "powershell:Test-Connection 8.8.8.8 -Count 2 -TimeoutSeconds 3", "powershell"),
            DominoStep("dns_check", "powershell:Resolve-DnsName google.com -ErrorAction SilentlyContinue", "powershell"),
            DominoStep("cluster_lan", "powershell:Test-Connection 10.5.0.2 -Count 1 -TimeoutSeconds 3", "powershell", on_fail="skip"),
            DominoStep("tts_network", "python:edge_tts_speak('Diagnostic reseau termine.')", "python"),
        ],
        category="debug_cascade",
        description="Debug reseau complet: gateway + internet + DNS + cluster LAN",
        learning_context="Debug reseau — verifier gateway d'abord, puis internet, puis cluster",
    ),
    DominoPipeline(
        id="domino_debug_db",
        trigger_vocal=["debug base de donnees", "probleme database", "check database"],
        steps=[
            DominoStep("integrity_check", "python:sqlite3_integrity_check('etoile.db')", "python"),
            DominoStep("size_check", "powershell:Get-Item 'F:\\BUREAU\\turbo\\data\\etoile.db' | Select-Object Length", "powershell"),
            DominoStep("table_counts", "python:sqlite3_table_counts('etoile.db')", "python"),
            DominoStep("vacuum_if_large", "python:sqlite3_vacuum_if_needed('etoile.db', 50)", "python", condition="db_size_mb > 50"),
            DominoStep("tts_db", "python:edge_tts_speak('Base de donnees verifiee.')", "python"),
        ],
        category="debug_cascade",
        description="Debug DB: integrite + taille + comptages + vacuum conditionnel",
        learning_context="Debug DB — verifier integrite avant tout, vacuum si > 50 MB",
    ),
    DominoPipeline(
        id="domino_debug_api_cascade",
        trigger_vocal=["debug api", "api en panne", "test tous les endpoints"],
        steps=[
            DominoStep("health_m1", "curl:http://10.5.0.2:1234/api/v1/models", "curl", on_fail="skip", timeout_s=5),
            DominoStep("health_m2", "curl:http://192.168.1.26:1234/api/v1/models", "curl", on_fail="skip", timeout_s=5),
            DominoStep("health_ollama", "curl:http://127.0.0.1:11434/api/tags", "curl", on_fail="skip", timeout_s=5),
            DominoStep("health_n8n", "curl:http://127.0.0.1:5678/healthz", "curl", on_fail="skip", timeout_s=5),
            DominoStep("tts_api", "python:edge_tts_speak('Diagnostic API termine.')", "python"),
        ],
        category="debug_cascade",
        description="Debug API: health check tous endpoints cluster + n8n",
        learning_context="Debug API — on_fail=skip pour ne pas bloquer la cascade",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # DEPLOY FLOW (4 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_deploy_standard",
        trigger_vocal=["deploie le code", "deploy standard", "push en production"],
        steps=[
            DominoStep("git_status", "powershell:git -C 'F:\\BUREAU\\turbo' status --short", "powershell"),
            DominoStep("run_tests", "powershell:cd F:\\BUREAU\\turbo && uv run python -m pytest tests/ -q 2>&1", "powershell", on_fail="stop"),
            DominoStep("git_add_commit", "powershell:git -C 'F:\\BUREAU\\turbo' add -A && git -C 'F:\\BUREAU\\turbo' commit -m 'auto-deploy'", "powershell"),
            DominoStep("git_push", "powershell:git -C 'F:\\BUREAU\\turbo' push", "powershell"),
            DominoStep("tts_deploy", "python:edge_tts_speak('Deploiement termine avec succes.')", "python"),
        ],
        category="deploy_flow",
        description="Deploy standard: status + tests + commit + push",
        learning_context="Deploy — TOUJOURS tester avant de push, arreter si tests echouent",
        priority="high",
    ),
    DominoPipeline(
        id="domino_deploy_hotfix",
        trigger_vocal=["hotfix urgent", "deploy hotfix", "correction urgente"],
        steps=[
            DominoStep("git_stash", "powershell:git -C 'F:\\BUREAU\\turbo' stash", "powershell"),
            DominoStep("apply_fix", "powershell:git -C 'F:\\BUREAU\\turbo' add -A", "powershell"),
            DominoStep("commit_hotfix", "powershell:git -C 'F:\\BUREAU\\turbo' commit -m 'hotfix: correction urgente'", "powershell"),
            DominoStep("push_hotfix", "powershell:git -C 'F:\\BUREAU\\turbo' push", "powershell"),
            DominoStep("tts_hotfix", "python:edge_tts_speak('Hotfix deploye.')", "python"),
        ],
        category="deploy_flow",
        description="Hotfix rapide: stash + fix + commit + push",
        learning_context="Hotfix — rapide, pas de tests complets, stash le WIP d'abord",
        priority="critical",
    ),
    DominoPipeline(
        id="domino_deploy_rollback",
        trigger_vocal=["rollback deploy", "annule le dernier deploy", "reviens en arriere"],
        steps=[
            DominoStep("get_last_commit", "powershell:git -C 'F:\\BUREAU\\turbo' log -1 --oneline", "powershell"),
            DominoStep("revert_commit", "powershell:git -C 'F:\\BUREAU\\turbo' revert HEAD --no-edit", "powershell"),
            DominoStep("push_revert", "powershell:git -C 'F:\\BUREAU\\turbo' push", "powershell"),
            DominoStep("tts_rollback", "python:edge_tts_speak('Rollback effectue.')", "python"),
        ],
        category="deploy_flow",
        description="Rollback: revert dernier commit + push",
        learning_context="Rollback — revert propre, pas de force push, garder l'historique",
    ),
    DominoPipeline(
        id="domino_deploy_with_backup",
        trigger_vocal=["deploy avec backup", "deploie en securite", "deploy safe"],
        steps=[
            DominoStep("backup_db", "python:backup_etoile_db()", "python"),
            DominoStep("backup_config", "powershell:Copy-Item 'F:\\BUREAU\\turbo\\.env' 'F:\\BUREAU\\turbo\\.env.bak'", "powershell"),
            DominoStep("run_tests", "powershell:cd F:\\BUREAU\\turbo && uv run python -m pytest tests/ -q 2>&1", "powershell", on_fail="stop"),
            DominoStep("git_commit_push", "powershell:git -C 'F:\\BUREAU\\turbo' add -A && git -C 'F:\\BUREAU\\turbo' commit -m 'safe-deploy' && git -C 'F:\\BUREAU\\turbo' push", "powershell"),
            DominoStep("tts_safe", "python:edge_tts_speak('Deploy securise termine. Backup cree.')", "python"),
        ],
        category="deploy_flow",
        description="Deploy securise: backup DB + config + tests + commit + push",
        learning_context="Deploy safe — backup AVANT tout, arreter si tests echouent",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # SECURITY SWEEP (4 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_security_full",
        trigger_vocal=["scan securite complet", "audit securite", "security sweep"],
        steps=[
            DominoStep("check_ports", "powershell:Get-NetTCPConnection -State Listen | Select-Object LocalPort -Unique | Sort-Object LocalPort", "powershell"),
            DominoStep("check_firewall", "powershell:Get-NetFirewallProfile | Select-Object Name,Enabled", "powershell"),
            DominoStep("check_env_files", "powershell:Get-ChildItem 'F:\\BUREAU\\turbo' -Recurse -Filter '.env*' | Select-Object FullName", "powershell"),
            DominoStep("check_processes", "powershell:Get-Process | Where-Object {$_.CPU -gt 60} | Select-Object Name,CPU,Id", "powershell"),
            DominoStep("tts_security", "python:edge_tts_speak('Scan securite termine.')", "python"),
        ],
        category="security_sweep",
        description="Audit securite complet: ports + firewall + .env + processus suspects",
        learning_context="Securite — verifier ports ouverts, .env non exposes, processus gourmands",
        priority="high",
    ),
    DominoPipeline(
        id="domino_security_keys",
        trigger_vocal=["verifie les cles api", "check api keys", "audit cles"],
        steps=[
            DominoStep("list_env", "powershell:Get-Content 'F:\\BUREAU\\turbo\\.env' | Select-String 'KEY|TOKEN|SECRET' | Measure-Object", "powershell"),
            DominoStep("check_git_history", "powershell:git -C 'F:\\BUREAU\\turbo' log --oneline -5 -- '*.env*'", "powershell"),
            DominoStep("check_db_keys", "python:check_api_keys_in_db()", "python"),
            DominoStep("tts_keys", "python:edge_tts_speak('Audit cles API termine.')", "python"),
        ],
        category="security_sweep",
        description="Audit cles API: .env + historique git + DB",
        learning_context="Cles API — verifier qu'elles ne sont pas dans l'historique git",
    ),
    DominoPipeline(
        id="domino_security_network",
        trigger_vocal=["scan reseau securite", "check connexions suspectes", "intrusion check"],
        steps=[
            DominoStep("active_connections", "powershell:Get-NetTCPConnection -State Established | Group-Object RemoteAddress | Sort-Object Count -Descending | Select-Object -First 10 Count,Name", "powershell"),
            DominoStep("unknown_ips", "powershell:Get-NetTCPConnection -State Established | Where-Object {$_.RemoteAddress -notmatch '^(10\\.|192\\.168\\.|127\\.)' -and $_.RemoteAddress -ne '::1'} | Select-Object RemoteAddress,RemotePort -Unique", "powershell"),
            DominoStep("tts_network_sec", "python:edge_tts_speak('Scan reseau securite termine.')", "python"),
        ],
        category="security_sweep",
        description="Scan reseau securite: connexions actives + IPs inconnues",
        learning_context="Securite reseau — IPs hors 10.x/192.168.x sont suspectes sauf CDN connus",
    ),
    DominoPipeline(
        id="domino_security_permissions",
        trigger_vocal=["check permissions", "audit droits fichiers", "permissions securite"],
        steps=[
            DominoStep("check_acl", "powershell:(Get-Acl 'F:\\BUREAU\\turbo').Access | Select-Object IdentityReference,FileSystemRights", "powershell"),
            DominoStep("check_sensitive", "powershell:Get-ChildItem 'F:\\BUREAU\\turbo\\data' -Filter '*.db' | Select-Object Name,Length,LastWriteTime", "powershell"),
            DominoStep("tts_perms", "python:edge_tts_speak('Audit permissions termine.')", "python"),
        ],
        category="security_sweep",
        description="Audit permissions: ACL + fichiers sensibles",
        learning_context="Permissions — verifier que les .db ne sont pas en lecture publique",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # GPU THERMAL (3 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_gpu_monitor_full",
        trigger_vocal=["monitore les gpu", "status gpu complet", "thermal gpu"],
        steps=[
            DominoStep("gpu_all_metrics", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw --format=csv,noheader", "powershell"),
            DominoStep("gpu_processes", "powershell:nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader", "powershell"),
            DominoStep("eval_health", "curl:http://10.5.0.2:1234/api/v1/chat", "curl"),
            DominoStep("tts_gpu", "python:edge_tts_speak('Monitoring GPU complet.')", "python"),
        ],
        category="gpu_thermal",
        description="Monitoring GPU complet: metriques + processus + evaluation IA",
        learning_context="GPU monitoring — 5 GPU locaux, focus temperature et VRAM",
    ),
    DominoPipeline(
        id="domino_gpu_optimize",
        trigger_vocal=["optimise les gpu", "libere la vram", "gpu optimization"],
        steps=[
            DominoStep("check_vram", "powershell:nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader", "powershell"),
            DominoStep("kill_idle", "python:kill_idle_gpu_processes()", "python"),
            DominoStep("verify_free", "powershell:nvidia-smi --query-gpu=memory.free --format=csv,noheader", "powershell"),
            DominoStep("tts_optimized", "python:edge_tts_speak('GPU optimises. VRAM liberee.')", "python"),
        ],
        category="gpu_thermal",
        description="Optimisation GPU: check VRAM + kill idle + verification",
        learning_context="GPU optim — liberer VRAM en tuant les processus idle, garder LM Studio",
    ),
    DominoPipeline(
        id="domino_gpu_emergency",
        trigger_vocal=["urgence gpu", "gpu critical", "surchauffe critique"],
        steps=[
            DominoStep("read_temps", "powershell:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader", "powershell"),
            DominoStep("kill_heavy", "python:kill_heaviest_gpu_process()", "python", condition="any_gpu > 85"),
            DominoStep("reduce_power", "powershell:nvidia-smi -pl 150", "powershell"),
            DominoStep("tts_emergency", "python:edge_tts_speak('Urgence GPU geree. Puissance reduite.')", "python"),
        ],
        category="gpu_thermal",
        description="Urgence GPU: lire temps + kill + reduire puissance",
        learning_context="Urgence GPU — 85C+ = critique, kill le process le plus lourd, reduire TDP",
        priority="critical",
        cooldown_s=30,
    ),

    # ─────────────────────────────────────────────────────────────────────
    # BACKUP CHAIN (3 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_backup_complet",
        trigger_vocal=["backup complet", "sauvegarde totale", "backup tout"],
        steps=[
            DominoStep("backup_db", "python:backup_all_databases()", "python"),
            DominoStep("backup_config", "powershell:Copy-Item 'F:\\BUREAU\\turbo\\.env','F:\\BUREAU\\turbo\\pyproject.toml' -Destination 'F:\\BUREAU\\turbo\\backups\\' -Force", "powershell"),
            DominoStep("backup_git", "powershell:git -C 'F:\\BUREAU\\turbo' bundle create 'F:\\BUREAU\\turbo\\backups\\turbo.bundle' --all", "powershell"),
            DominoStep("verify_backup", "powershell:Get-ChildItem 'F:\\BUREAU\\turbo\\backups\\' -File | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name,Length,LastWriteTime", "powershell"),
            DominoStep("tts_backup", "python:edge_tts_speak('Backup complet termine.')", "python"),
        ],
        category="backup_chain",
        description="Backup complet: DB + config + git bundle + verification",
        learning_context="Backup — DB en priorite, git bundle pour tout l'historique",
        priority="high",
    ),
    DominoPipeline(
        id="domino_backup_quick",
        trigger_vocal=["backup rapide", "sauvegarde rapide", "quick backup"],
        steps=[
            DominoStep("backup_etoile", "python:backup_etoile_db()", "python"),
            DominoStep("tts_quick", "python:edge_tts_speak('Backup rapide etoile.db termine.')", "python"),
        ],
        category="backup_chain",
        description="Backup rapide: etoile.db seulement",
        learning_context="Backup rapide — juste la DB principale quand on est presse",
    ),
    DominoPipeline(
        id="domino_backup_restore",
        trigger_vocal=["restaure le backup", "restore backup", "recupere la sauvegarde"],
        steps=[
            DominoStep("list_backups", "powershell:Get-ChildItem 'F:\\BUREAU\\turbo\\backups\\' -Filter '*.db*' | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name,LastWriteTime", "powershell"),
            DominoStep("confirm_restore", "python:confirm_action('Restaurer le dernier backup?')", "python"),
            DominoStep("restore_db", "python:restore_latest_backup()", "python"),
            DominoStep("verify_integrity", "python:sqlite3_integrity_check('etoile.db')", "python"),
            DominoStep("tts_restored", "python:edge_tts_speak('Backup restaure et verifie.')", "python"),
        ],
        category="backup_chain",
        description="Restauration: lister + confirmer + restaurer + verifier integrite",
        learning_context="Restore — TOUJOURS confirmer avant, verifier integrite apres",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # MONITORING ALERT (3 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_monitor_system_full",
        trigger_vocal=["monitoring systeme complet", "status systeme total", "check tout le systeme"],
        steps=[
            DominoStep("cpu_ram", "powershell:Get-CimInstance Win32_OperatingSystem | Select-Object FreePhysicalMemory,TotalVisibleMemorySize; (Get-CimInstance Win32_Processor).LoadPercentage", "powershell"),
            DominoStep("disk_space", "powershell:Get-PSDrive -PSProvider FileSystem | Select-Object Name,@{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}},@{N='UsedGB';E={[math]::Round($_.Used/1GB,1)}}", "powershell"),
            DominoStep("gpu_status", "powershell:nvidia-smi --query-gpu=temperature.gpu,memory.used --format=csv,noheader", "powershell"),
            DominoStep("cluster_status", "curl:http://10.5.0.2:1234/api/v1/models", "curl", on_fail="skip"),
            DominoStep("tts_monitor", "python:edge_tts_speak('Monitoring systeme complet.')", "python"),
        ],
        category="monitoring_alert",
        description="Monitoring complet: CPU/RAM + disque + GPU + cluster",
        learning_context="Monitoring — CPU/RAM/Disk/GPU/Cluster dans cet ordre de priorite",
    ),
    DominoPipeline(
        id="domino_monitor_alerts_check",
        trigger_vocal=["verifie les alertes", "check alertes", "y a des alertes"],
        steps=[
            DominoStep("check_logs", "python:check_recent_error_logs()", "python"),
            DominoStep("check_gpu_temp", "powershell:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader", "powershell"),
            DominoStep("check_disk", "powershell:Get-PSDrive C,F | Select-Object Name,@{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}}", "powershell"),
            DominoStep("tts_alerts", "python:edge_tts_speak('Verification alertes terminee.')", "python"),
        ],
        category="monitoring_alert",
        description="Check alertes: logs erreurs + GPU temp + espace disque",
        learning_context="Alertes — logs d'erreur, GPU > 75C, disque < 20 GB sont des alertes",
    ),
    DominoPipeline(
        id="domino_monitor_performance",
        trigger_vocal=["performance systeme", "benchmark rapide", "check performance"],
        steps=[
            DominoStep("cpu_bench", "powershell:(Get-CimInstance Win32_Processor).LoadPercentage", "powershell"),
            DominoStep("mem_bench", "powershell:[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)", "powershell"),
            DominoStep("gpu_bench", "powershell:nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader", "powershell"),
            DominoStep("io_bench", "powershell:(Get-Counter '\\PhysicalDisk(_Total)\\Disk Bytes/sec' -ErrorAction SilentlyContinue).CounterSamples.CookedValue", "powershell"),
            DominoStep("tts_perf", "python:edge_tts_speak('Benchmark performance termine.')", "python"),
        ],
        category="monitoring_alert",
        description="Benchmark rapide: CPU + RAM + GPU + IO",
        learning_context="Performance — benchmark rapide sans charge, juste snapshot instant",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # COLLABORATION (3 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_collab_sync_cluster",
        trigger_vocal=["synchronise le cluster", "sync toutes les machines", "cluster sync"],
        steps=[
            DominoStep("check_m1", "curl:http://10.5.0.2:1234/api/v1/models", "curl", on_fail="skip"),
            DominoStep("check_m2", "curl:http://192.168.1.26:1234/api/v1/models", "curl", on_fail="skip"),
            DominoStep("check_m3", "curl:http://192.168.1.113:1234/api/v1/models", "curl", on_fail="skip"),
            DominoStep("sync_report", "python:generate_cluster_sync_report()", "python"),
            DominoStep("tts_sync", "python:edge_tts_speak('Cluster synchronise.')", "python"),
        ],
        category="collaboration",
        description="Sync cluster: verifier tous les noeuds + rapport",
        learning_context="Sync cluster — verifier chaque noeud, generer rapport d'etat",
    ),
    DominoPipeline(
        id="domino_collab_share_model",
        trigger_vocal=["partage le modele", "distribue sur le cluster", "model sharing"],
        steps=[
            DominoStep("check_model_local", "python:check_model_loaded_local()", "python"),
            DominoStep("check_target_vram", "curl:http://10.5.0.2:1234/api/v1/models", "curl"),
            DominoStep("transfer_config", "python:prepare_model_transfer_config()", "python"),
            DominoStep("tts_share", "python:edge_tts_speak('Configuration modele partagee.')", "python"),
        ],
        category="collaboration",
        description="Partage modele: check local + cible VRAM + transfert config",
        learning_context="Model sharing — verifier VRAM dispo sur cible avant transfert",
    ),
    DominoPipeline(
        id="domino_collab_consensus",
        trigger_vocal=["lance un consensus", "vote multi agents", "consensus cluster"],
        steps=[
            DominoStep("query_m1", "curl:http://10.5.0.2:1234/api/v1/chat", "curl", on_fail="skip"),
            DominoStep("query_m2", "curl:http://192.168.1.26:1234/api/v1/chat", "curl", on_fail="skip"),
            DominoStep("query_ol1", "curl:http://127.0.0.1:11434/api/chat", "curl", on_fail="skip"),
            DominoStep("vote_weighted", "python:calculate_weighted_vote()", "python"),
            DominoStep("tts_consensus", "python:edge_tts_speak('Consensus multi-agents termine.')", "python"),
        ],
        category="collaboration",
        description="Consensus: interroger M1+M2+OL1 + vote pondere",
        learning_context="Consensus — M1 poids 1.8, M2 poids 1.4, OL1 poids 1.3",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # BONNE NUIT / FIN DE JOURNEE (3 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_bonne_nuit",
        trigger_vocal=["bonne nuit jarvis", "fin de journee", "arrete tout pour ce soir"],
        steps=[
            DominoStep("save_session", "python:save_session_state()", "python"),
            DominoStep("backup_quick", "python:backup_etoile_db()", "python"),
            DominoStep("close_trading", "python:close_trading_if_open()", "python"),
            DominoStep("reduce_gpu", "powershell:nvidia-smi -pl 100", "powershell"),
            DominoStep("tts_goodnight", "python:edge_tts_speak('Bonne nuit! Tout est sauvegarde.')", "python"),
        ],
        category="routine_soir",
        description="Routine soir: sauvegarder + backup + fermer trading + reduire GPU",
        learning_context="Fin de journee — sauvegarder session, backup DB, reduire conso GPU",
    ),
    DominoPipeline(
        id="domino_pause_dejeuner",
        trigger_vocal=["pause dejeuner", "je vais manger", "break midi"],
        steps=[
            DominoStep("save_state", "python:save_session_state()", "python"),
            DominoStep("reduce_load", "python:reduce_cluster_load()", "python"),
            DominoStep("tts_lunch", "python:edge_tts_speak('Pause dejeuner. Systeme en veille legere.')", "python"),
        ],
        category="routine_soir",
        description="Pause dejeuner: sauvegarder + reduire charge",
        learning_context="Pause — ne pas eteindre, juste reduire la charge",
    ),
    DominoPipeline(
        id="domino_weekend_shutdown",
        trigger_vocal=["mode weekend", "eteins le cluster weekend", "shutdown weekend"],
        steps=[
            DominoStep("backup_full", "python:backup_all_databases()", "python"),
            DominoStep("save_metrics", "python:save_weekly_metrics()", "python"),
            DominoStep("close_all_trading", "python:close_all_positions()", "python"),
            DominoStep("reduce_all_gpu", "powershell:nvidia-smi -pl 80", "powershell"),
            DominoStep("tts_weekend_off", "python:edge_tts_speak('Mode weekend active. Bon repos!')", "python"),
        ],
        category="routine_soir",
        description="Shutdown weekend: backup + metriques + close trading + GPU eco",
        learning_context="Weekend — backup complet, fermer trading, GPU en eco",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # STREAMING (2 dominos)
    # ─────────────────────────────────────────────────────────────────────
    DominoPipeline(
        id="domino_stream_start",
        trigger_vocal=["lance le stream", "demarre le streaming", "on stream maintenant"],
        steps=[
            DominoStep("check_network", "powershell:Test-Connection 8.8.8.8 -Count 1 -TimeoutSeconds 3", "powershell"),
            DominoStep("start_obs", "app_open:obs64", "pipeline"),
            DominoStep("open_chat", "python:open_stream_chat_monitor()", "python"),
            DominoStep("tts_stream", "python:edge_tts_speak('Stream pret. OBS lance. Chat monitore.')", "python"),
        ],
        category="streaming",
        description="Demarrage stream: reseau + OBS + chat monitor",
        learning_context="Stream — verifier reseau d'abord, OBS + chat obligatoires",
    ),
    DominoPipeline(
        id="domino_stream_stop",
        trigger_vocal=["arrete le stream", "stop streaming", "fin du stream"],
        steps=[
            DominoStep("stop_obs", "powershell:Stop-Process -Name obs64,obs32 -Force -ErrorAction SilentlyContinue", "powershell"),
            DominoStep("save_vod", "python:save_stream_vod_info()", "python"),
            DominoStep("tts_stream_end", "python:edge_tts_speak('Stream termine. VOD sauvegardee.')", "python"),
        ],
        category="streaming",
        description="Arret stream: stop OBS + sauvegarder VOD info",
        learning_context="Fin stream — arreter OBS proprement, log la VOD",
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# LEARNING DATASET — Scenarios d'apprentissage vocal pour fine-tuning
# ══════════════════════════════════════════════════════════════════════════════

DOMINO_LEARNING_DATASET: list[dict] = []

def _build_learning_dataset():
    """Genere le dataset d'apprentissage a partir des dominos definis."""
    for dp in DOMINO_PIPELINES:
        for trigger in dp.trigger_vocal:
            DOMINO_LEARNING_DATASET.append({
                "input": trigger,
                "output": f"domino:{dp.id}",
                "category": dp.category,
                "steps": [s.name for s in dp.steps],
                "context": dp.learning_context,
                "priority": dp.priority,
            })

_build_learning_dataset()


# ══════════════════════════════════════════════════════════════════════════════
# DOMINO ENGINE — Executeur de cascades
# ══════════════════════════════════════════════════════════════════════════════

def find_domino(text: str) -> Optional[DominoPipeline]:
    """Trouve le domino pipeline correspondant a une phrase vocale."""
    text_lower = text.lower().strip()
    best_match = None
    best_score = 0.0

    for dp in DOMINO_PIPELINES:
        for trigger in dp.trigger_vocal:
            # Match exact
            if text_lower == trigger.lower():
                return dp
            # Match partiel (contient le trigger)
            if trigger.lower() in text_lower or text_lower in trigger.lower():
                from difflib import SequenceMatcher
                score = SequenceMatcher(None, text_lower, trigger.lower()).ratio()
                if score > best_score and score > 0.6:
                    best_score = score
                    best_match = dp

    return best_match


def get_domino_stats() -> dict:
    """Retourne les statistiques des domino pipelines."""
    categories = {}
    for dp in DOMINO_PIPELINES:
        categories[dp.category] = categories.get(dp.category, 0) + 1

    return {
        "total_dominos": len(DOMINO_PIPELINES),
        "total_triggers": sum(len(dp.trigger_vocal) for dp in DOMINO_PIPELINES),
        "total_steps": sum(len(dp.steps) for dp in DOMINO_PIPELINES),
        "categories": categories,
        "learning_examples": len(DOMINO_LEARNING_DATASET),
        "critical_count": sum(1 for dp in DOMINO_PIPELINES if dp.priority == "critical"),
        "high_count": sum(1 for dp in DOMINO_PIPELINES if dp.priority == "high"),
    }
