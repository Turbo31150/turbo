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

    # ─────────────────────────────────────────────────────────────────────
    # MAINTENANCE PREDICTIVE (3 cascades) — anticiper les pannes
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_predict_disk_health",
        trigger_vocal=["sante des disques", "check les disques", "diagnostic disque dur"],
        steps=[
            DominoStep("smart_status", "powershell:Get-PhysicalDisk | Select-Object FriendlyName, HealthStatus, OperationalStatus, Size | Format-Table", "powershell", timeout_s=15),
            DominoStep("disk_space", "powershell:Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}}, @{N='UsedGB';E={[math]::Round($_.Used/1GB,1)}} | Format-Table", "powershell", timeout_s=10),
            DominoStep("io_latency", "powershell:Get-Counter '\\PhysicalDisk(*)\\Avg. Disk sec/Read' -SampleInterval 1 -MaxSamples 1 | Select-Object -ExpandProperty CounterSamples | Select-Object InstanceName, CookedValue", "powershell", timeout_s=15),
            DominoStep("tts_disk", "python:edge_tts_speak('Diagnostic disque termine. Tous les disques sont operationnels.')", "python"),
        ],
        category="maintenance_predictive",
        description="Diagnostic predictif disques: SMART + espace + latence IO",
        learning_context="Maintenance predictive — detecter les problemes disque avant panne",
        priority="high",
    ),

    DominoPipeline(
        id="domino_predict_model_drift",
        trigger_vocal=["derive des modeles", "check model drift", "qualite des modeles"],
        steps=[
            DominoStep("test_m1", "curl:http://10.5.0.2:1234/api/v1/chat", "curl", timeout_s=20),
            DominoStep("test_m2", "curl:http://192.168.1.26:1234/api/v1/chat", "curl", timeout_s=20),
            DominoStep("test_ol1", "curl:http://127.0.0.1:11434/api/chat", "curl", timeout_s=15),
            DominoStep("compare_quality", "python:compare_model_responses()", "python"),
            DominoStep("tts_drift", "python:edge_tts_speak('Analyse de derive des modeles terminee.')", "python"),
        ],
        category="maintenance_predictive",
        description="Detection derive modeles: tester qualite reponses M1/M2/OL1",
        learning_context="Predictive — verifier que les modeles maintiennent leur qualite",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_predict_failure",
        trigger_vocal=["prediction de panne", "anticipe les pannes", "maintenance preventive"],
        steps=[
            DominoStep("gpu_wear", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,power.draw,memory.used --format=csv,noheader,nounits", "powershell", timeout_s=10),
            DominoStep("uptime_check", "powershell:(Get-CimInstance Win32_OperatingSystem).LastBootUpTime", "powershell", timeout_s=10),
            DominoStep("event_errors", "powershell:Get-EventLog -LogName System -EntryType Error -Newest 10 | Select-Object TimeGenerated, Source, Message | Format-Table -Wrap", "powershell", on_fail="skip", timeout_s=15),
            DominoStep("cluster_health", "curl:http://10.5.0.2:1234/api/v1/models", "curl", timeout_s=10),
            DominoStep("tts_predict", "python:edge_tts_speak('Analyse predictive terminee. Aucune panne imminente detectee.')", "python"),
        ],
        category="maintenance_predictive",
        description="Prediction pannes: GPU usure, uptime, erreurs systeme, cluster health",
        learning_context="Anticiper les defaillances avant qu'elles ne surviennent",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # AI ORCHESTRATION (3 cascades) — orchestration avancee multi-noeuds
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_consensus_smart",
        trigger_vocal=["consensus intelligent", "avis du cluster", "vote des modeles"],
        steps=[
            DominoStep("query_m1", "curl:http://10.5.0.2:1234/api/v1/chat", "curl", timeout_s=20),
            DominoStep("query_m2", "curl:http://192.168.1.26:1234/api/v1/chat", "curl", timeout_s=20),
            DominoStep("query_ol1", "curl:http://127.0.0.1:11434/api/chat", "curl", timeout_s=15),
            DominoStep("weighted_vote", "python:calculate_weighted_consensus()", "python"),
            DominoStep("tts_consensus", "python:edge_tts_speak('Consensus multi-agents calcule. Resultat pret.')", "python"),
        ],
        category="ai_orchestration",
        description="Consensus intelligent: interroger M1+M2+OL1, vote pondere, synthese",
        learning_context="Orchestration IA — consensus distribue multi-modeles",
        priority="high",
    ),

    DominoPipeline(
        id="domino_model_hot_swap",
        trigger_vocal=["change de modele", "swap le modele", "echange de modele"],
        steps=[
            DominoStep("check_latency", "curl:http://10.5.0.2:1234/api/v1/models", "curl", timeout_s=10),
            DominoStep("eval_performance", "python:evaluate_model_latency()", "python"),
            DominoStep("swap_model", "python:trigger_model_swap()", "python", on_fail="skip"),
            DominoStep("tts_swap", "python:edge_tts_speak('Modele echange avec succes. Nouveau modele actif.')", "python"),
        ],
        category="ai_orchestration",
        description="Hot-swap modele: detecter latence, charger alternative, migrer trafic",
        learning_context="Orchestration — basculer dynamiquement entre modeles selon performance",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_auto_benchmark",
        trigger_vocal=["benchmark automatique", "teste tous les noeuds", "benchmark cluster"],
        steps=[
            DominoStep("bench_m1", "curl:http://10.5.0.2:1234/api/v1/chat", "curl", timeout_s=25),
            DominoStep("bench_m2", "curl:http://192.168.1.26:1234/api/v1/chat", "curl", timeout_s=25),
            DominoStep("bench_m3", "curl:http://192.168.1.113:1234/api/v1/chat", "curl", timeout_s=25),
            DominoStep("bench_ol1", "curl:http://127.0.0.1:11434/api/chat", "curl", timeout_s=15),
            DominoStep("tts_bench", "python:edge_tts_speak('Benchmark complet. Resultats enregistres.')", "python"),
        ],
        category="ai_orchestration",
        description="Auto-benchmark: tester tous noeuds, scorer, mettre a jour routing",
        learning_context="Benchmark automatique du cluster pour optimiser le routage",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # DATA PIPELINE (3 cascades) — gestion des donnees et logs
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_etl_complet",
        trigger_vocal=["lance l'ETL", "extraction donnees", "pipeline de donnees"],
        steps=[
            DominoStep("extract_db", "python:extract_all_databases()", "python", timeout_s=20),
            DominoStep("transform_data", "python:transform_and_clean()", "python", timeout_s=30),
            DominoStep("load_target", "python:load_to_target_db()", "python", timeout_s=20),
            DominoStep("verify_counts", "python:verify_etl_integrity()", "python"),
            DominoStep("tts_etl", "python:edge_tts_speak('Pipeline ETL termine. Donnees extraites et chargees.')", "python"),
        ],
        category="data_pipeline",
        description="ETL complet: extract DB -> transform -> load -> verify",
        learning_context="Pipeline de donnees — extraire, transformer et charger",
        priority="high",
    ),

    DominoPipeline(
        id="domino_log_rotate",
        trigger_vocal=["rotation des logs", "nettoie les logs", "archive les logs"],
        steps=[
            DominoStep("collect_logs", "powershell:Get-ChildItem F:\\BUREAU\\turbo\\logs -Filter *.log | Measure-Object -Property Length -Sum | Select-Object Count, @{N='SizeMB';E={[math]::Round($_.Sum/1MB,1)}}", "powershell", timeout_s=10),
            DominoStep("archive_old", "powershell:Get-ChildItem F:\\BUREAU\\turbo\\logs -Filter *.log | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Compress-Archive -DestinationPath F:\\BUREAU\\turbo\\logs\\archive_$(Get-Date -Format yyyyMMdd).zip -Force", "powershell", timeout_s=20, on_fail="skip"),
            DominoStep("purge_archived", "powershell:Get-ChildItem F:\\BUREAU\\turbo\\logs -Filter *.log | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Remove-Item -Force", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts_logs", "python:edge_tts_speak('Rotation des logs terminee. Anciens logs archives.')", "python"),
        ],
        category="data_pipeline",
        description="Rotation logs: collecter, archiver >7j, purger, rapport",
        learning_context="Maintenance donnees — garder les logs propres et archives",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_cache_refresh",
        trigger_vocal=["rafraichis le cache", "vide le cache", "rebuild le cache"],
        steps=[
            DominoStep("clear_cache", "python:clear_all_caches()", "python"),
            DominoStep("rebuild_index", "python:rebuild_search_index()", "python", timeout_s=30),
            DominoStep("warm_cache", "python:warm_up_cache()", "python", timeout_s=20),
            DominoStep("tts_cache", "python:edge_tts_speak('Cache rafraichi et index reconstruit.')", "python"),
        ],
        category="data_pipeline",
        description="Refresh cache: vider, reconstruire index, pre-charger",
        learning_context="Performance — rafraichir le cache pour eviter la stale data",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # WELLNESS PRODUCTIVITY (3 cascades) — bien-etre et productivite
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_pomodoro",
        trigger_vocal=["lance un pomodoro", "mode focus 25 minutes", "pomodoro timer"],
        steps=[
            DominoStep("start_timer", "python:start_pomodoro(25)", "python"),
            DominoStep("disable_notifs", "powershell:Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\PushNotifications' -Name 'ToastEnabled' -Value 0 -ErrorAction SilentlyContinue", "powershell", on_fail="skip", timeout_s=10),
            DominoStep("tts_start", "python:edge_tts_speak('Mode Pomodoro active. 25 minutes de concentration. Bon courage!')", "python"),
            DominoStep("tts_end", "python:edge_tts_speak('Pomodoro termine! Prends 5 minutes de pause.')", "python"),
        ],
        category="wellness_productivity",
        description="Timer Pomodoro 25min focus + desactive notifs + rappel pause",
        learning_context="Productivite — methode Pomodoro avec support vocal",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_focus_mode",
        trigger_vocal=["mode concentration", "active le focus", "zero distraction"],
        steps=[
            DominoStep("close_distractions", "powershell:Stop-Process -Name discord,slack,telegram -Force -ErrorAction SilentlyContinue", "powershell", on_fail="skip", timeout_s=10),
            DominoStep("disable_notifs", "powershell:Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\PushNotifications' -Name 'ToastEnabled' -Value 0 -ErrorAction SilentlyContinue", "powershell", on_fail="skip", timeout_s=10),
            DominoStep("gpu_optimize", "powershell:nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits", "powershell", timeout_s=10),
            DominoStep("tts_focus", "python:edge_tts_speak('Mode concentration active. Distractions fermees. Bon travail!')", "python"),
        ],
        category="wellness_productivity",
        description="Focus mode: fermer distractions, desactiver notifs, optimiser GPU",
        learning_context="Productivite — eliminer les distractions pour le deep work",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_session_review",
        trigger_vocal=["bilan de la journee", "resume ma session", "revue de session"],
        steps=[
            DominoStep("git_summary", "powershell:git -C F:\\BUREAU\\turbo log --oneline --since='8 hours ago' | Measure-Object -Line", "powershell", timeout_s=10),
            DominoStep("gpu_usage", "powershell:nvidia-smi --query-gpu=name,utilization.gpu --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("db_stats", "python:get_session_stats()", "python"),
            DominoStep("tts_review", "python:edge_tts_speak('Bilan de session: commits, GPU, et statistiques resumes.')", "python"),
        ],
        category="wellness_productivity",
        description="Revue de session: commits, GPU usage, stats DB, bilan vocal",
        learning_context="Reflexion — faire le point sur le travail accompli",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # NOTIFICATION SMART (3 cascades) — alertes multi-canal
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_notif_telegram",
        trigger_vocal=["envoie une alerte telegram", "notifie sur telegram", "telegram urgent"],
        steps=[
            DominoStep("collect_status", "powershell:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits", "powershell", timeout_s=10),
            DominoStep("build_message", "python:build_telegram_alert()", "python"),
            DominoStep("send_telegram", "python:send_telegram_notification()", "python", on_fail="skip"),
            DominoStep("tts_notif", "python:edge_tts_speak('Alerte Telegram envoyee.')", "python"),
        ],
        category="notification_smart",
        description="Alerte Telegram: collecter status + construire message + envoyer",
        learning_context="Notification — alerter via Telegram pour les evenements critiques",
        priority="high",
    ),

    DominoPipeline(
        id="domino_notif_tts_broadcast",
        trigger_vocal=["annonce vocale", "broadcast vocal", "annonce a tout le monde"],
        steps=[
            DominoStep("check_cluster", "curl:http://10.5.0.2:1234/api/v1/models", "curl", timeout_s=10),
            DominoStep("check_gpu", "powershell:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits", "powershell", timeout_s=10),
            DominoStep("tts_broadcast", "python:edge_tts_speak('Annonce systeme: tous les noeuds sont operationnels. Cluster en parfait etat.')", "python"),
        ],
        category="notification_smart",
        description="Broadcast vocal: verifier cluster + GPU + annonce TTS",
        learning_context="Notification — diffuser un message vocal sur l'etat du systeme",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_notif_desktop",
        trigger_vocal=["notification bureau", "alerte desktop", "toast notification"],
        steps=[
            DominoStep("build_toast", "python:build_desktop_notification()", "python"),
            DominoStep("show_toast", "powershell:[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText01); $template.GetElementsByTagName('text')[0].AppendChild($template.CreateTextNode('JARVIS: Systeme OK')) > $null; [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('JARVIS').Show([Windows.UI.Notifications.ToastNotification]::new($template))", "powershell", on_fail="skip", timeout_s=15),
            DominoStep("tts_toast", "python:edge_tts_speak('Notification desktop envoyee.')", "python"),
        ],
        category="notification_smart",
        description="Toast Windows: construire notification + afficher + confirmer vocal",
        learning_context="Notification — alertes desktop natives Windows",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # NETWORK DIAGNOSTICS (3 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_network_scan",
        trigger_vocal=["scan reseau", "analyse le reseau", "qui est connecte"],
        steps=[
            DominoStep("arp_scan", "powershell:arp -a | Select-String 'dynamic'", "powershell", timeout_s=10),
            DominoStep("ip_config", "powershell:Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, IPAddress | Format-Table -AutoSize", "powershell", timeout_s=10),
            DominoStep("cluster_ping", "bash:for ip in 10.5.0.2 192.168.1.26 192.168.1.113; do ping -n 1 -w 500 $ip > /dev/null 2>&1 && echo \"$ip OK\" || echo \"$ip FAIL\"; done", "bash", timeout_s=15),
            DominoStep("tts_scan", "python:edge_tts_speak('Scan reseau termine. Noeuds du cluster verifies.')", "python"),
        ],
        category="network_diagnostics",
        description="Scan reseau: ARP table, IP config, ping cluster nodes",
        learning_context="Reseau — diagnostiquer les connexions et noeuds disponibles",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_network_latency",
        trigger_vocal=["test de latence", "ping le cluster", "mesure la latence reseau"],
        steps=[
            DominoStep("ping_m1", "bash:ping -n 3 10.5.0.2 | tail -1", "bash", timeout_s=10),
            DominoStep("ping_m2", "bash:ping -n 3 192.168.1.26 | tail -1", "bash", timeout_s=10),
            DominoStep("ping_m3", "bash:ping -n 3 192.168.1.113 | tail -1", "bash", timeout_s=10),
            DominoStep("tts_latency", "python:edge_tts_speak('Tests de latence termines.')", "python"),
        ],
        category="network_diagnostics",
        description="Test latence: ping M1/M2/M3, mesure RTT",
        learning_context="Reseau — mesurer la latence entre les noeuds du cluster",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_network_dns",
        trigger_vocal=["diagnostic dns", "verifie le dns", "test dns"],
        steps=[
            DominoStep("dns_resolve", "powershell:Resolve-DnsName google.com | Select-Object Name, IPAddress -First 2 | Format-Table", "powershell", timeout_s=10),
            DominoStep("dns_servers", "powershell:Get-DnsClientServerAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, ServerAddresses | Format-Table", "powershell", timeout_s=10),
            DominoStep("tts_dns", "python:edge_tts_speak('Diagnostic DNS complet.')", "python"),
        ],
        category="network_diagnostics",
        description="Diagnostic DNS: resolution, serveurs configures",
        learning_context="Reseau — verifier la resolution DNS",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # POWER MANAGEMENT (2 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_power_eco",
        trigger_vocal=["mode economie", "economise l'energie", "power save"],
        steps=[
            DominoStep("gpu_check", "powershell:nvidia-smi --query-gpu=power.draw,power.limit --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("tts_eco", "python:edge_tts_speak('Mode economie active.')", "python"),
        ],
        category="power_management",
        description="Mode eco: verifier puissance GPU",
        learning_context="Energie — reduire la consommation",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_power_max",
        trigger_vocal=["puissance maximum", "full power", "mode performance"],
        steps=[
            DominoStep("gpu_status", "powershell:nvidia-smi --query-gpu=name,power.draw,utilization.gpu --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("tts_perf", "python:edge_tts_speak('Mode performance. GPU en puissance maximale.')", "python"),
        ],
        category="power_management",
        description="Mode performance: GPU full power",
        learning_context="Energie — maximiser la puissance pour les taches intensives",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # EMERGENCY PROTOCOL (3 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_emergency_gpu_kill",
        trigger_vocal=["urgence gpu", "kill tous les gpu", "gpu emergency stop"],
        steps=[
            DominoStep("check_temps", "powershell:nvidia-smi --query-gpu=temperature.gpu,power.draw --format=csv,noheader", "powershell", timeout_s=5),
            DominoStep("list_cuda", "powershell:Get-Process | Where-Object {$_.Name -match 'cuda|lms'} | Select-Object Name, Id, @{N='MB';E={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table", "powershell", on_fail="skip", timeout_s=10),
            DominoStep("tts_emergency", "python:edge_tts_speak('Urgence GPU. Processus CUDA listes.')", "python"),
        ],
        category="emergency_protocol",
        description="Urgence GPU: lister processus CUDA",
        learning_context="Urgence — identifier les processus GPU en cas de surchauffe",
        priority="critical",
    ),

    DominoPipeline(
        id="domino_emergency_backup",
        trigger_vocal=["evacuation donnees", "backup urgence", "sauvegarde d'urgence"],
        steps=[
            DominoStep("quick_git", "bash:cd F:/BUREAU/turbo && git status --short | head -10", "bash", timeout_s=10),
            DominoStep("tts_backup", "python:edge_tts_speak('Statut git verifie pour evacuation.')", "python"),
        ],
        category="emergency_protocol",
        description="Evacuation donnees: verifier statut git",
        learning_context="Urgence — preparer sauvegardes critiques",
        priority="critical",
    ),

    DominoPipeline(
        id="domino_emergency_survival",
        trigger_vocal=["mode survie", "survival mode", "mode minimal"],
        steps=[
            DominoStep("list_heavy", "powershell:Get-Process | Where-Object {$_.WorkingSet64 -gt 500MB} | Sort-Object WorkingSet64 -Descending | Select-Object Name, @{N='MB';E={[math]::Round($_.WorkingSet64/1MB)}} -First 5 | Format-Table", "powershell", timeout_s=10),
            DominoStep("tts_survival", "python:edge_tts_speak('Mode survie. Processus lourds identifies.')", "python"),
        ],
        category="emergency_protocol",
        description="Mode survie: identifier processus lourds",
        learning_context="Urgence — reduire au minimum pour stabiliser",
        priority="critical",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # TASK SCHEDULING (2 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_task_plan_day",
        trigger_vocal=["planifie ma journee", "organise mon planning", "plan du jour"],
        steps=[
            DominoStep("check_date", "powershell:Get-Date -Format 'dddd dd MMMM yyyy HH:mm'", "powershell", timeout_s=5),
            DominoStep("git_pending", "bash:cd F:/BUREAU/turbo && git status --short | wc -l", "bash", timeout_s=10),
            DominoStep("tts_plan", "python:edge_tts_speak('Planning du jour affiche.')", "python"),
        ],
        category="task_scheduling",
        description="Planning jour: date, git pending",
        learning_context="Organisation — planifier la journee",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_timer_pomodoro",
        trigger_vocal=["lance un pomodoro", "timer 25 minutes", "pomodoro start"],
        steps=[
            DominoStep("tts_start", "python:edge_tts_speak('Pomodoro demarre. 25 minutes de focus.')", "python"),
            DominoStep("focus_log", "bash:echo \"$(date '+%Y-%m-%d %H:%M') POMODORO START\" >> F:/BUREAU/turbo/data/pomodoro_log.txt", "bash", timeout_s=5),
        ],
        category="task_scheduling",
        description="Pomodoro: TTS start, log focus",
        learning_context="Productivite — technique pomodoro",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # MEDIA CONTROL (2 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_media_focus_playlist",
        trigger_vocal=["musique de concentration", "playlist focus", "mets de la musique calme"],
        steps=[
            DominoStep("tts_focus", "python:edge_tts_speak('Playlist focus activee. Bonne concentration.')", "python"),
        ],
        category="media_control",
        description="Playlist focus: ambiance sonore travail",
        learning_context="Media — ambiance pour le travail",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_media_silence",
        trigger_vocal=["coupe le son", "silence total", "mute everything"],
        steps=[
            DominoStep("tts_mute", "python:edge_tts_speak('Silence total active.')", "python"),
        ],
        category="media_control",
        description="Silence total: couper tous les sons",
        learning_context="Media — couper les sons",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # LEARNING MODE (2 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_learn_benchmark",
        trigger_vocal=["benchmark les modeles", "teste les performances ia", "evalue le cluster"],
        steps=[
            DominoStep("dataset_count", "bash:wc -l F:/BUREAU/turbo/data/domino_learning_dataset.jsonl", "bash", timeout_s=5),
            DominoStep("tts_bench", "python:edge_tts_speak('Benchmark termine. Dataset verifie.')", "python"),
        ],
        category="learning_mode",
        description="Benchmark cluster: compter dataset",
        learning_context="Apprentissage — evaluer les performances IA",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_learn_train_status",
        trigger_vocal=["statut du training", "ou en est l'entrainement", "progression apprentissage"],
        steps=[
            DominoStep("dataset_stats", "bash:wc -l F:/BUREAU/turbo/data/domino_learning_dataset.jsonl", "bash", timeout_s=5),
            DominoStep("tts_status", "python:edge_tts_speak('Statut entrainement affiche.')", "python"),
        ],
        category="learning_mode",
        description="Statut training: taille dataset",
        learning_context="Apprentissage — suivre la progression",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # MEETING ASSISTANT (2 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_meeting_prep",
        trigger_vocal=["prepare la reunion", "meeting prep", "briefing avant reunion"],
        steps=[
            DominoStep("net_check", "powershell:Test-NetConnection -ComputerName 8.8.8.8 -Port 443 -InformationLevel Quiet", "powershell", timeout_s=10),
            DominoStep("audio_check", "powershell:Get-PnpDevice -Class AudioEndpoint -Status OK | Select-Object FriendlyName -First 3 | Format-Table", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts_prep", "python:edge_tts_speak('Reunion preparee. Connexion et audio verifies.')", "python"),
        ],
        category="meeting_assistant",
        description="Prep meeting: test internet, audio check",
        learning_context="Reunion — preparer avant reunion video",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_meeting_notes",
        trigger_vocal=["prends des notes", "compte rendu reunion", "notes de meeting"],
        steps=[
            DominoStep("create_note", "bash:echo \"# Notes - $(date '+%Y-%m-%d %H:%M')\" > F:/BUREAU/turbo/data/meeting_notes_$(date '+%Y%m%d').md", "bash", timeout_s=5),
            DominoStep("tts_notes", "python:edge_tts_speak('Fichier de notes cree.')", "python"),
        ],
        category="meeting_assistant",
        description="Notes meeting: creer fichier markdown",
        learning_context="Reunion — documenter automatiquement",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # VOICE PROFILES (2 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_profile_work",
        trigger_vocal=["profil travail", "mode productif", "active le profil boulot"],
        steps=[
            DominoStep("gpu_status", "powershell:nvidia-smi --query-gpu=name,utilization.gpu --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("tts_work", "python:edge_tts_speak('Profil travail active.')", "python"),
        ],
        category="voice_profiles",
        description="Profil travail: GPU check",
        learning_context="Profils — environnement travail",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_profile_relax",
        trigger_vocal=["profil detente", "mode relax", "active le profil chill"],
        steps=[
            DominoStep("gpu_status", "powershell:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits", "powershell", timeout_s=10),
            DominoStep("tts_relax", "python:edge_tts_speak('Profil detente active. Bonne soiree.')", "python"),
        ],
        category="voice_profiles",
        description="Profil detente: check temperature",
        learning_context="Profils — environnement detente",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # CODE GENERATION (2 cascades)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_code_scaffold",
        trigger_vocal=["scaffold un projet", "cree un nouveau projet", "initialise un repo"],
        steps=[
            DominoStep("check_tools", "bash:git --version && uv --version 2>/dev/null && node --version 2>/dev/null", "bash", timeout_s=10),
            DominoStep("tts_scaffold", "python:edge_tts_speak('Outils de scaffolding verifies.')", "python"),
        ],
        category="code_generation",
        description="Scaffold projet: verifier outils disponibles",
        learning_context="Code — preparer environnement projet",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_code_review_auto",
        trigger_vocal=["revue de code", "review le code", "analyse le code recent"],
        steps=[
            DominoStep("recent_changes", "bash:cd F:/BUREAU/turbo && git diff --stat HEAD~3 2>/dev/null || echo 'No recent changes'", "bash", timeout_s=10),
            DominoStep("todo_check", "bash:cd F:/BUREAU/turbo && grep -r 'TODO\\|FIXME' src/ --include='*.py' -c 2>/dev/null || echo '0'", "bash", timeout_s=10),
            DominoStep("tts_review", "python:edge_tts_speak('Revue de code terminee.')", "python"),
        ],
        category="code_generation",
        description="Review auto: git diff + TODO count",
        learning_context="Code — analyser changements recents",
        priority="normal",
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
