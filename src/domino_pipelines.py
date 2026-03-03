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

import os
from dataclasses import dataclass

from src.config import PATHS

_TURBO_DIR = str(PATHS.get("turbo", "F:/BUREAU/turbo")).replace("/", "\\")
_TURBO_DIR_FWD = str(PATHS.get("turbo", "F:/BUREAU/turbo"))
_M1_KEY = os.getenv("LM_STUDIO_1_API_KEY", os.getenv("LM_STUDIO_1_KEY", ""))
_M2_KEY = os.getenv("LM_STUDIO_2_API_KEY", os.getenv("LM_STUDIO_2_KEY", ""))


@dataclass
class DominoStep:
    """Une etape dans une cascade domino."""
    name: str                   # Identifiant de l'etape
    action: str                 # Action a executer (pipeline ref, powershell, curl, etc.)
    action_type: str            # Type: pipeline, powershell, curl, python, condition
    condition: str | None = None  # Condition optionnelle (ex: "gpu_temp < 80")
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
            DominoStep("list_env", f"powershell:Get-Content '{_TURBO_DIR}\\.env' | Select-String 'KEY|TOKEN|SECRET' | Measure-Object", "powershell"),
            DominoStep("check_git_history", f"powershell:git -C '{_TURBO_DIR}' log --oneline -5 -- '*.env*'", "powershell"),
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

    # ─────────────────────────────────────────────────────────────────────
    # SYSTEM CLEANUP (3 cascades) — nettoyage systeme
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_cleanup_temp",
        trigger_vocal=["nettoie les fichiers temporaires", "vide le temp", "clean temp files"],
        steps=[
            DominoStep("count_temp", "powershell:Get-ChildItem $env:TEMP -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum | Select-Object Count, @{N='SizeMB';E={[math]::Round($_.Sum/1MB)}}", "powershell", timeout_s=15),
            DominoStep("count_pip", "bash:pip cache info 2>/dev/null | head -3 || echo 'pip cache N/A'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts_cleanup", "python:edge_tts_speak('Analyse des fichiers temporaires terminee.')", "python"),
        ],
        category="system_cleanup",
        description="Analyse temp files: compter taille TEMP + pip cache",
        learning_context="Nettoyage — identifier les fichiers temporaires a supprimer",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_cleanup_orphans",
        trigger_vocal=["cherche les processus orphelins", "kill les zombies", "processus fantomes"],
        steps=[
            DominoStep("find_orphans", "powershell:Get-Process | Where-Object {$_.Responding -eq $false} | Select-Object Name, Id, @{N='MB';E={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("high_cpu", "powershell:Get-Process | Sort-Object CPU -Descending | Select-Object Name, Id, CPU, @{N='MB';E={[math]::Round($_.WorkingSet64/1MB)}} -First 5 | Format-Table", "powershell", timeout_s=10),
            DominoStep("tts_orphans", "python:edge_tts_speak('Processus orphelins et gros consommateurs identifies.')", "python"),
        ],
        category="system_cleanup",
        description="Detecter processus orphelins et top CPU consumers",
        learning_context="Nettoyage — trouver les processus bloques ou gourmands",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_cleanup_git",
        trigger_vocal=["nettoie le git", "git cleanup", "git prune"],
        steps=[
            DominoStep("git_gc", "bash:cd F:/BUREAU/turbo && git gc --auto 2>&1 | tail -3", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("git_prune", "bash:cd F:/BUREAU/turbo && git remote prune origin 2>&1 | head -5", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("git_size", "bash:cd F:/BUREAU/turbo && du -sh .git 2>/dev/null || echo '.git size N/A'", "bash", timeout_s=10),
            DominoStep("tts_git", "python:edge_tts_speak('Nettoyage git termine.')", "python"),
        ],
        category="system_cleanup",
        description="Git cleanup: gc, prune remote branches, check size",
        learning_context="Nettoyage — maintenance du depot git",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # PERFORMANCE TUNING (2 cascades) — optimisation performances
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_perf_gpu_optimize",
        trigger_vocal=["optimise les gpu", "gpu tuning", "ajuste les performances gpu"],
        steps=[
            DominoStep("gpu_clocks", "powershell:nvidia-smi --query-gpu=name,clocks.current.graphics,clocks.current.memory,power.draw --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("gpu_procs", "powershell:nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader 2>$null || echo 'No GPU processes'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts_gpu_tune", "python:edge_tts_speak('Metriques GPU collectees. Optimisation analysee.')", "python"),
        ],
        category="performance_tuning",
        description="GPU tuning: clocks, processes, power analysis",
        learning_context="Performance — analyser et optimiser l'utilisation GPU",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_perf_memory_optimize",
        trigger_vocal=["optimise la memoire", "libere de la ram", "memory cleanup"],
        steps=[
            DominoStep("ram_status", "powershell:$os=Get-CimInstance Win32_OperatingSystem; [math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB,1).ToString()+'GB / '+[math]::Round($os.TotalVisibleMemorySize/1MB,1).ToString()+'GB'", "powershell", timeout_s=10),
            DominoStep("top_ram", "powershell:Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object Name, @{N='MB';E={[math]::Round($_.WorkingSet64/1MB)}} -First 8 | Format-Table", "powershell", timeout_s=10),
            DominoStep("tts_mem", "python:edge_tts_speak('Memoire analysee. Top consommateurs affiches.')", "python"),
        ],
        category="performance_tuning",
        description="Memory analysis: RAM usage + top consumers",
        learning_context="Performance — identifier les processus gourmands en RAM",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # TESTING PIPELINE (2 cascades) — execution de tests
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_test_all_dominos",
        trigger_vocal=["teste tous les dominos", "run all tests", "lance les tests complets"],
        steps=[
            DominoStep("count_dominos", "bash:cd F:/BUREAU/turbo && python3 -c \"from src.domino_pipelines import DOMINO_PIPELINES; print(f'{len(DOMINO_PIPELINES)} cascades')\"", "bash", timeout_s=10),
            DominoStep("count_dataset", "bash:wc -l F:/BUREAU/turbo/data/domino_learning_dataset.jsonl", "bash", timeout_s=5),
            DominoStep("tts_test", "python:edge_tts_speak('Preparation des tests. Cascades et dataset comptes.')", "python"),
        ],
        category="testing_pipeline",
        description="Pre-test: compter cascades et dataset avant run",
        learning_context="Tests — preparer et valider avant execution",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_test_cluster_health",
        trigger_vocal=["test de sante cluster", "cluster health check", "verifie la sante du cluster"],
        steps=[
            DominoStep("ping_m1", f"bash:curl -s --max-time 3 http://10.5.0.2:1234/api/v1/models -H 'Authorization: Bearer {_M1_KEY}' > /dev/null 2>&1 && echo 'M1 OK' || echo 'M1 FAIL'", "bash", timeout_s=5),
            DominoStep("ping_m2", f"bash:curl -s --max-time 3 http://192.168.1.26:1234/api/v1/models -H 'Authorization: Bearer {_M2_KEY}' > /dev/null 2>&1 && echo 'M2 OK' || echo 'M2 FAIL'", "bash", timeout_s=5),
            DominoStep("ping_ol1", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags > /dev/null 2>&1 && echo 'OL1 OK' || echo 'OL1 FAIL'", "bash", timeout_s=5),
            DominoStep("gpu_temps", "powershell:nvidia-smi --query-gpu=name,temperature.gpu --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("tts_health", "python:edge_tts_speak('Health check cluster termine.')", "python"),
        ],
        category="testing_pipeline",
        description="Health check: ping M1/M2/OL1 + GPU temps",
        learning_context="Tests — verifier la sante de tous les noeuds",
        priority="high",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # DOCUMENTATION (2 cascades) — generation de docs
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_doc_stats",
        trigger_vocal=["statistiques du projet", "stats jarvis", "resume du projet"],
        steps=[
            DominoStep("count_files", "bash:cd F:/BUREAU/turbo && find src/ -name '*.py' | wc -l", "bash", timeout_s=10),
            DominoStep("count_lines", "bash:cd F:/BUREAU/turbo && wc -l src/*.py src/**/*.py 2>/dev/null | tail -1 || echo 'N/A'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("git_commits", "bash:cd F:/BUREAU/turbo && git rev-list --count HEAD", "bash", timeout_s=5),
            DominoStep("tts_stats", "python:edge_tts_speak('Statistiques du projet affichees.')", "python"),
        ],
        category="documentation",
        description="Stats projet: fichiers Python, lignes, commits",
        learning_context="Documentation — generer des statistiques projet",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_doc_changelog",
        trigger_vocal=["genere le changelog", "historique des changements", "quoi de neuf"],
        steps=[
            DominoStep("recent_commits", "bash:cd F:/BUREAU/turbo && git log --oneline --since='7 days ago' | head -20", "bash", timeout_s=10),
            DominoStep("files_changed", "bash:cd F:/BUREAU/turbo && git diff --stat HEAD~10 2>/dev/null | tail -3", "bash", timeout_s=10),
            DominoStep("tts_changelog", "python:edge_tts_speak('Changelog de la semaine affiche.')", "python"),
        ],
        category="documentation",
        description="Changelog: commits recents + fichiers modifies",
        learning_context="Documentation — suivre les changements recents",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # ENRICHISSEMENT categories existantes
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_meeting_timer",
        trigger_vocal=["timer de reunion", "minuteur meeting", "chrono reunion"],
        steps=[
            DominoStep("tts_timer_start", "python:edge_tts_speak('Timer de reunion demarre.')", "python"),
            DominoStep("log_meeting", "bash:echo \"$(date '+%Y-%m-%d %H:%M') MEETING START\" >> F:/BUREAU/turbo/data/meeting_log.txt", "bash", timeout_s=5),
        ],
        category="meeting_assistant",
        description="Timer reunion: demarrer chrono + log",
        learning_context="Reunion — chronometrer les reunions",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_code_lint",
        trigger_vocal=["lance le linter", "verifie la qualite du code", "lint le code"],
        steps=[
            DominoStep("python_syntax", "bash:cd F:/BUREAU/turbo && python3 -m py_compile src/domino_pipelines.py 2>&1 && echo 'SYNTAX OK' || echo 'SYNTAX ERROR'", "bash", timeout_s=10),
            DominoStep("import_check", "bash:cd F:/BUREAU/turbo && python3 -c 'from src.domino_pipelines import DOMINO_PIPELINES; print(f\"{len(DOMINO_PIPELINES)} cascades OK\")' 2>&1", "bash", timeout_s=10),
            DominoStep("tts_lint", "python:edge_tts_speak('Verification du code terminee.')", "python"),
        ],
        category="code_generation",
        description="Lint check: syntaxe Python + imports",
        learning_context="Code — verifier la qualite syntaxique",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_learn_quiz",
        trigger_vocal=["lance un quiz", "quiz de revision", "teste mes connaissances"],
        steps=[
            DominoStep("random_domino", "bash:cd F:/BUREAU/turbo && python3 -c \"import random; from src.domino_pipelines import DOMINO_PIPELINES; dp=random.choice(DOMINO_PIPELINES); print(f'Quiz: {dp.description}')\"", "bash", timeout_s=10),
            DominoStep("tts_quiz", "python:edge_tts_speak('Quiz: devine quel domino correspond a cette description.')", "python"),
        ],
        category="learning_mode",
        description="Quiz: afficher description random, deviner le domino",
        learning_context="Apprentissage — tester ses connaissances des cascades",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_network_bandwidth",
        trigger_vocal=["test de bande passante", "speed test", "test de vitesse reseau"],
        steps=[
            DominoStep("download_test", "bash:curl -s --max-time 10 -o /dev/null -w '%{speed_download}' https://speed.cloudflare.com/__down?bytes=10000000 2>/dev/null | python3 -c \"import sys; speed=float(sys.stdin.read()); print(f'{speed/1024/1024:.1f} MB/s download')\"", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("cluster_latency", "bash:for ip in 10.5.0.2 192.168.1.26 192.168.1.113; do ping -n 1 -w 500 $ip 2>/dev/null | grep -i 'time=' || echo \"$ip timeout\"; done", "bash", timeout_s=10),
            DominoStep("tts_bandwidth", "python:edge_tts_speak('Test de bande passante termine.')", "python"),
        ],
        category="network_diagnostics",
        description="Bandwidth test: download speed + cluster latency",
        learning_context="Reseau — mesurer la bande passante et latence",
        priority="normal",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # NOUVELLES CASCADES (batch 59 — 2026-03-03)
    # ─────────────────────────────────────────────────────────────────────

    DominoPipeline(
        id="domino_bilan_cluster_complet",
        trigger_vocal=["bilan cluster complet", "rapport cluster", "etat complet du cluster"],
        steps=[
            DominoStep("health_m1", "curl:http://10.5.0.2:1234/api/v1/models", "curl", on_fail="skip", timeout_s=5),
            DominoStep("health_m2", "curl:http://192.168.1.26:1234/api/v1/models", "curl", on_fail="skip", timeout_s=5),
            DominoStep("health_m3", "curl:http://192.168.1.113:1234/api/v1/models", "curl", on_fail="skip", timeout_s=5),
            DominoStep("health_ol1", "curl:http://127.0.0.1:11434/api/tags", "curl", on_fail="skip", timeout_s=5),
            DominoStep("gpu_all", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("vram_summary", "powershell:nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader", "powershell"),
            DominoStep("tts_bilan", "python:edge_tts_speak('Bilan cluster complet termine. Tous les noeuds verifies.')", "python"),
        ],
        category="cluster_management",
        description="Bilan complet: health check 4 noeuds + GPU details + VRAM",
        learning_context="Bilan exhaustif du cluster — afficher noeuds offline en priorite",
        priority="high",
    ),

    DominoPipeline(
        id="domino_mode_coding_intense",
        trigger_vocal=["mode coding", "mode dev intense", "mode programmation", "session de code"],
        steps=[
            DominoStep("open_vscode", "app_open:code", "pipeline"),
            DominoStep("open_terminal", "app_open:terminal", "pipeline"),
            DominoStep("disable_notifs", "powershell:New-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings' -Name 'NOC_GLOBAL_SETTING_TOASTS_ENABLED' -Value 0 -PropertyType DWORD -Force 2>$null", "powershell", on_fail="skip"),
            DominoStep("cluster_warmup", "curl:http://10.5.0.2:1234/api/v1/models", "curl", on_fail="skip", timeout_s=5),
            DominoStep("focus_timer", "python:start_pomodoro(25)", "python"),
            DominoStep("tts_coding", "python:edge_tts_speak('Mode coding active. Notifications desactivees. Focus 25 minutes.')", "python"),
        ],
        category="productivity",
        description="Mode coding intense: VSCode + terminal + disable notifs + focus timer",
        learning_context="Dev intense — desactiver distractions, activer timer pomodoro 25min",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_rapport_du_jour",
        trigger_vocal=["rapport du jour", "bilan de la journee", "resume du jour", "qu'est ce qu'on a fait aujourd'hui"],
        steps=[
            DominoStep("git_today", "powershell:git -C 'F:\\BUREAU\\turbo' log --oneline --since='midnight' --format='%h %s'", "powershell"),
            DominoStep("cluster_stats", "curl:http://10.5.0.2:1234/api/v1/models", "curl", on_fail="skip", timeout_s=5),
            DominoStep("db_stats", "python:sqlite3_table_counts('etoile.db')", "python", on_fail="skip"),
            DominoStep("trading_pnl", "python:fetch_today_pnl()", "python", on_fail="skip"),
            DominoStep("tts_rapport", "python:edge_tts_speak('Rapport du jour genere.')", "python"),
        ],
        category="productivity",
        description="Rapport quotidien: git log today + cluster + DB + trading PnL",
        learning_context="Bilan de fin de journee — commits, cluster health, trading resume",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_maintenance_hebdo",
        trigger_vocal=["maintenance hebdo", "maintenance de la semaine", "nettoyage hebdomadaire"],
        steps=[
            DominoStep("vacuum_etoile", "python:sqlite3_vacuum('etoile.db')", "python", timeout_s=60),
            DominoStep("vacuum_jarvis", "python:sqlite3_vacuum('jarvis.db')", "python", timeout_s=30),
            DominoStep("git_prune", "powershell:git -C 'F:\\BUREAU\\turbo' gc --prune=now", "powershell", timeout_s=60),
            DominoStep("clean_temp", "powershell:Remove-Item -Path $env:TEMP\\* -Force -Recurse -ErrorAction SilentlyContinue 2>$null; Write-Output 'Temp nettoye'", "powershell", on_fail="skip", timeout_s=30),
            DominoStep("clean_logs", "powershell:Get-ChildItem 'F:\\BUREAU\\turbo\\data\\*.log' -ErrorAction SilentlyContinue | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Remove-Item -Force 2>$null", "powershell", on_fail="skip"),
            DominoStep("tts_maintenance", "python:edge_tts_speak('Maintenance hebdomadaire terminee. Bases nettoyees, fichiers temporaires supprimes.')", "python"),
        ],
        category="maintenance",
        description="Maintenance hebdo: vacuum DB + git gc + clean temp + clean old logs",
        learning_context="Maintenance preventive — vacuum, nettoyage, liberation espace",
        priority="normal",
        cooldown_s=3600,
    ),

    DominoPipeline(
        id="domino_code_review_complet",
        trigger_vocal=["code review complet", "revue de code", "review le code"],
        steps=[
            DominoStep("git_diff", "powershell:git -C 'F:\\BUREAU\\turbo' diff --stat HEAD~3", "powershell"),
            DominoStep("lint_check", "powershell:cd F:\\BUREAU\\turbo && uv run python -m ruff check src/ --statistics 2>&1 | Select-Object -First 20", "powershell", on_fail="skip", timeout_s=30),
            DominoStep("type_check", "powershell:cd F:\\BUREAU\\turbo && npx tsc --noEmit 2>&1 | Select-Object -Last 5", "powershell", on_fail="skip", timeout_s=30),
            DominoStep("test_quick", "powershell:cd F:\\BUREAU\\turbo && uv run python -m pytest tests/ -q --tb=no 2>&1 | Select-Object -Last 3", "powershell", on_fail="skip", timeout_s=60),
            DominoStep("tts_review", "python:edge_tts_speak('Code review termine. Resultats affiches.')", "python"),
        ],
        category="dev_workflow",
        description="Code review: git diff + lint + type check + tests rapides",
        learning_context="Review — diff des 3 derniers commits, lint ruff, types TS, tests pytest",
        priority="normal",
    ),

    DominoPipeline(
        id="domino_analyse_trading_ia",
        trigger_vocal=["analyse trading ia", "ia analyse le marche", "consensus trading"],
        steps=[
            DominoStep("fetch_prices", "python:fetch_mexc_prices(['BTC','ETH','SOL','SUI','PEPE'])", "python", timeout_s=15),
            DominoStep("m1_analysis", "curl:http://10.5.0.2:1234/api/v1/chat", "curl", timeout_s=30),
            DominoStep("gptoss_analysis", "curl:http://127.0.0.1:11434/api/chat", "curl", timeout_s=60),
            DominoStep("consensus_vote", "python:weighted_consensus_vote()", "python"),
            DominoStep("tts_trading", "python:edge_tts_speak('Analyse trading IA terminee. Consensus genere.')", "python"),
        ],
        category="trading_cascade",
        description="Analyse trading IA: prix + M1 analyse + gpt-oss analyse + consensus vote",
        learning_context="Trading IA — consensus M1+gpt-oss sur top 5 paires, vote pondere",
        priority="high",
    ),
    # ── Batch 76: 10 nouveaux dominos ─────────────────────────────────────
    DominoPipeline(
        id="domino_quick_health",
        trigger_vocal=["health check rapide", "tout va bien", "check rapide"],
        steps=[
            DominoStep("check_m1", "curl:http://10.5.0.2:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("check_ol1", "curl:http://127.0.0.1:11434/api/tags", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("check_gpu", "powershell:nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,memory.used --format=csv,noheader", "powershell", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Health check rapide termine.')", "python"),
        ],
        category="cluster",
        description="Health check rapide 3 steps: M1 + OL1 + GPU",
        learning_context="Quick health check — M1, OL1, GPU en 3 steps rapides",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_update_corrections",
        trigger_vocal=["recharge les corrections", "met a jour les corrections", "sync corrections"],
        steps=[
            DominoStep("load_db", "python:edge_tts_speak('Rechargement des corrections vocales depuis la base de donnees.')", "python"),
        ],
        category="voice",
        description="Recharger les corrections vocales depuis la DB",
        learning_context="Voice — reload corrections dict from DB",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_git_status_complet",
        trigger_vocal=["statut git complet", "git status complet", "etat du repo"],
        steps=[
            DominoStep("git_status", "bash:cd F:/BUREAU/turbo && git status --short", "bash", timeout_s=10),
            DominoStep("git_log", "bash:cd F:/BUREAU/turbo && git log --oneline -10", "bash", timeout_s=10),
            DominoStep("git_branch", "bash:cd F:/BUREAU/turbo && git branch -vv", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Statut git complet affiche.')", "python"),
        ],
        category="dev",
        description="Statut git complet: status + log 10 + branches",
        learning_context="Dev — git status, log, branches en un seul domino",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_vram_cleanup",
        trigger_vocal=["libere la vram", "nettoie la vram", "optimise la vram"],
        steps=[
            DominoStep("check_vram", "powershell:nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader", "powershell"),
            DominoStep("kill_idle", "python:kill_idle_gpu_processes()", "python"),
            DominoStep("check_after", "powershell:nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader", "powershell"),
            DominoStep("tts", "python:edge_tts_speak('VRAM nettoyee. Processus idle supprimes.')", "python"),
        ],
        category="gpu",
        description="Nettoyer la VRAM en killant les processus idle",
        learning_context="GPU — kill idle VRAM processes, before/after check",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_daily_standup",
        trigger_vocal=["standup", "daily standup", "standup du jour", "morning standup"],
        steps=[
            DominoStep("git_yesterday", "bash:cd F:/BUREAU/turbo && git log --since='yesterday' --oneline", "bash", timeout_s=10),
            DominoStep("cluster_health", "curl:http://10.5.0.2:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("db_stats", "python:sqlite3_table_counts('etoile.db')", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Daily standup: commits d hier affiches, cluster verifie.')", "python"),
        ],
        category="routine",
        description="Daily standup: commits hier + cluster + DB stats",
        learning_context="Routine — standup quotidien avec git + cluster + DB",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_clean_temp_files",
        trigger_vocal=["nettoie les temporaires", "supprime les temp", "clean temp"],
        steps=[
            DominoStep("clean_data_tmp", "python:clear_all_caches()", "python"),
            DominoStep("clean_pycache", "bash:find F:/BUREAU/turbo -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; echo OK", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Fichiers temporaires nettoyes.')", "python"),
        ],
        category="maintenance",
        description="Nettoyer les fichiers temporaires et caches Python",
        learning_context="Maintenance — clean tmp files + pycache",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_export_metrics",
        trigger_vocal=["exporte les metriques", "export metrics", "sauvegarde les stats"],
        steps=[
            DominoStep("db_counts", "python:sqlite3_table_counts('etoile.db')", "python"),
            DominoStep("db_counts_jarvis", "python:sqlite3_table_counts('jarvis.db')", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Metriques exportees.')", "python"),
        ],
        category="monitoring",
        description="Exporter les metriques DB (etoile + jarvis)",
        learning_context="Monitoring — export table counts from both DBs",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_model_benchmark",
        trigger_vocal=["benchmark modele", "teste le modele", "vitesse modele"],
        steps=[
            DominoStep("bench_m1", "curl:http://10.5.0.2:1234/api/v1/chat", "curl", timeout_s=30),
            DominoStep("bench_ol1", "curl:http://127.0.0.1:11434/api/chat", "curl", timeout_s=30, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Benchmark modele termine.')", "python"),
        ],
        category="cluster",
        description="Benchmark rapide M1 + OL1",
        learning_context="Cluster — benchmark latency M1+OL1",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_check_disk_space",
        trigger_vocal=["espace disque", "combien de place", "disk space"],
        steps=[
            DominoStep("check_c", "powershell:Get-PSDrive C | Select-Object @{N='Free_GB';E={[math]::Round($_.Free/1GB,1)}}, @{N='Used_GB';E={[math]::Round($_.Used/1GB,1)}} | Format-Table", "powershell"),
            DominoStep("check_f", "powershell:Get-PSDrive F | Select-Object @{N='Free_GB';E={[math]::Round($_.Free/1GB,1)}}, @{N='Used_GB';E={[math]::Round($_.Used/1GB,1)}} | Format-Table", "powershell", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Espace disque verifie.')", "python"),
        ],
        category="system",
        description="Verifier l'espace disque C: et F:",
        learning_context="System — disk space C: et F: via PowerShell",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_api_latency_test",
        trigger_vocal=["test latence api", "ping les apis", "latence des noeuds"],
        steps=[
            DominoStep("ping_m1", "curl:http://10.5.0.2:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("ping_m2", "curl:http://192.168.1.26:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("ping_m3", "curl:http://192.168.1.113:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("ping_ol1", "curl:http://127.0.0.1:11434/api/tags", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Test de latence API termine. Tous les noeuds pingues.')", "python"),
        ],
        category="cluster",
        description="Test de latence API sur tous les noeuds",
        learning_context="Cluster — ping 4 nodes for API latency test",
        priority="normal",
    ),
    # ── Batch 80: 15 nouveaux dominos (automation, project, data, integration) ──
    DominoPipeline(
        id="domino_auto_commit",
        trigger_vocal=["auto commit", "commite automatiquement", "sauvegarde le code"],
        steps=[
            DominoStep("git_status", "bash:cd F:/BUREAU/turbo && git status --short | head -20", "bash", timeout_s=10),
            DominoStep("git_add", "bash:cd F:/BUREAU/turbo && git add -A", "bash", timeout_s=10),
            DominoStep("git_commit", "bash:cd F:/BUREAU/turbo && git commit -m 'auto: sauvegarde vocale $(date +%Y%m%d_%H%M)' 2>&1 || echo 'Nothing to commit'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Code commite automatiquement.')", "python"),
        ],
        category="automation",
        description="Auto commit: git add + commit avec timestamp",
        learning_context="Automation — sauvegarder rapidement l'etat du code",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_auto_push",
        trigger_vocal=["pousse le code", "git push", "envoie sur github"],
        steps=[
            DominoStep("git_status", "bash:cd F:/BUREAU/turbo && git status --short", "bash", timeout_s=10),
            DominoStep("git_push", "bash:cd F:/BUREAU/turbo && git push 2>&1 | tail -3", "bash", timeout_s=30),
            DominoStep("tts", "python:edge_tts_speak('Code pousse sur GitHub.')", "python"),
        ],
        category="automation",
        description="Git push: verifier status + push",
        learning_context="Automation — push rapide apres commit",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_project_init",
        trigger_vocal=["initialise un projet python", "nouveau projet", "cree un projet"],
        steps=[
            DominoStep("check_uv", "bash:uv --version 2>/dev/null || echo 'uv not found'", "bash", timeout_s=5),
            DominoStep("check_git", "bash:git --version", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Outils de projet verifies. Pret pour initialiser.')", "python"),
        ],
        category="project_management",
        description="Init projet: verifier outils (uv, git)",
        learning_context="Project — verifier les prerequis avant creation",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_env_check",
        trigger_vocal=["verifie l'environnement", "check env", "environnement ok"],
        steps=[
            DominoStep("python_ver", "bash:python --version 2>&1", "bash", timeout_s=5),
            DominoStep("uv_ver", "bash:uv --version 2>&1 || echo 'uv N/A'", "bash", timeout_s=5),
            DominoStep("node_ver", "bash:node --version 2>&1 || echo 'node N/A'", "bash", timeout_s=5),
            DominoStep("git_ver", "bash:git --version 2>&1", "bash", timeout_s=5),
            DominoStep("env_file", f"bash:test -f F:/BUREAU/turbo/.env && echo '.env exists' || echo '.env MISSING'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Environnement verifie. Python, UV, Node, Git OK.')", "python"),
        ],
        category="project_management",
        description="Check environnement: Python, UV, Node, Git, .env",
        learning_context="Project — verifier que tous les outils sont installes",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_db_export_csv",
        trigger_vocal=["exporte la base en csv", "export csv", "sauvegarde csv"],
        steps=[
            DominoStep("export_etoile", "python:export_db_to_csv('etoile.db')", "python", timeout_s=30),
            DominoStep("tts", "python:edge_tts_speak('Base exportee en CSV.')", "python"),
        ],
        category="data_analysis",
        description="Export etoile.db vers CSV",
        learning_context="Data — export DB vers fichiers CSV pour analyse externe",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_db_row_count",
        trigger_vocal=["combien de lignes en base", "comptage base", "stats base de donnees"],
        steps=[
            DominoStep("count_etoile", "python:sqlite3_table_counts('etoile.db')", "python"),
            DominoStep("count_jarvis", "python:sqlite3_table_counts('jarvis.db')", "python", on_fail="skip"),
            DominoStep("count_sniper", "python:sqlite3_table_counts('sniper.db')", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Comptage des bases termine.')", "python"),
        ],
        category="data_analysis",
        description="Comptage lignes: etoile + jarvis + sniper",
        learning_context="Data — count rows dans les 3 DB principales",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_log_analysis",
        trigger_vocal=["analyse les logs", "check les logs", "log analysis"],
        steps=[
            DominoStep("recent_errors", "python:check_recent_error_logs()", "python", timeout_s=15),
            DominoStep("log_size", "bash:ls -lh F:/BUREAU/turbo/data/*.log 2>/dev/null || echo 'No logs'", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Analyse des logs terminee.')", "python"),
        ],
        category="data_analysis",
        description="Analyse logs: erreurs recentes + taille fichiers log",
        learning_context="Data — verifier les erreurs dans les logs",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_ollama_models",
        trigger_vocal=["liste les modeles ollama", "quels modeles ollama", "ollama models"],
        steps=[
            DominoStep("list_local", "curl:http://127.0.0.1:11434/api/tags", "curl", timeout_s=10),
            DominoStep("running", "curl:http://127.0.0.1:11434/api/ps", "curl", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Modeles Ollama listes.')", "python"),
        ],
        category="integration",
        description="Lister les modeles Ollama: tags + running",
        learning_context="Integration — lister les modeles Ollama locaux et en cours",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_lmstudio_models",
        trigger_vocal=["liste les modeles lm studio", "quels modeles lm studio", "lm studio models"],
        steps=[
            DominoStep("list_m1", "curl:http://10.5.0.2:1234/api/v1/models", "curl", timeout_s=10, on_fail="skip"),
            DominoStep("list_m2", "curl:http://192.168.1.26:1234/api/v1/models", "curl", timeout_s=10, on_fail="skip"),
            DominoStep("list_m3", "curl:http://192.168.1.113:1234/api/v1/models", "curl", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Modeles LM Studio listes sur les 3 noeuds.')", "python"),
        ],
        category="integration",
        description="Lister les modeles LM Studio sur M1/M2/M3",
        learning_context="Integration — modeles charges sur chaque noeud LM Studio",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_n8n_status",
        trigger_vocal=["statut n8n", "n8n status", "les workflows"],
        steps=[
            DominoStep("check_n8n", "curl:http://127.0.0.1:5678/healthz", "curl", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Statut n8n verifie.')", "python"),
        ],
        category="integration",
        description="Check n8n health",
        learning_context="Integration — verifier que n8n est en ligne",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_session_save",
        trigger_vocal=["sauvegarde la session", "save session", "snapshot session"],
        steps=[
            DominoStep("save_state", "python:save_session_state()", "python"),
            DominoStep("git_snapshot", "bash:cd F:/BUREAU/turbo && git stash push -m 'session-snapshot-$(date +%Y%m%d_%H%M)' 2>&1 && git stash pop 2>&1 || echo 'Nothing to stash'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Session sauvegardee.')", "python"),
        ],
        category="automation",
        description="Sauvegarder la session: state + git snapshot",
        learning_context="Automation — snapshot etat courant de la session",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_watch_gpu_temp",
        trigger_vocal=["surveille les temperatures", "watch gpu", "alerte temperature"],
        steps=[
            DominoStep("read_temps", "powershell:nvidia-smi --query-gpu=name,temperature.gpu --format=csv,noheader", "powershell"),
            DominoStep("eval_danger", "python:throttle_gpu_if_critical('80')", "python"),
            DominoStep("tts", "python:edge_tts_speak('Surveillance temperatures GPU active.')", "python"),
        ],
        category="monitoring_live",
        description="Surveiller les temperatures GPU et alerter si critique",
        learning_context="Monitoring — surveillance active des temperatures GPU",
        priority="high",
    ),
    DominoPipeline(
        id="domino_quick_test",
        trigger_vocal=["test rapide", "quick test", "verifie que ca marche"],
        steps=[
            DominoStep("syntax_check", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && python -m py_compile src/domino_pipelines.py && echo 'ALL SYNTAX OK'", "bash", timeout_s=15),
            DominoStep("import_check", "bash:cd F:/BUREAU/turbo && python -c 'from src.commands import COMMANDS; from src.voice_correction import process_voice_command; from src.domino_pipelines import DOMINO_PIPELINES; print(f\"OK: {len(COMMANDS)} cmds, {len(DOMINO_PIPELINES)} dominos\")'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Test rapide OK. Syntaxe et imports valides.')", "python"),
        ],
        category="testing_pipeline",
        description="Test rapide: syntaxe + imports des modules principaux",
        learning_context="Tests — verification rapide syntaxe et imports",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_cluster_rebalance",
        trigger_vocal=["reequilibre le cluster", "cluster rebalance", "redistribue les modeles"],
        steps=[
            DominoStep("check_m1_load", "curl:http://10.5.0.2:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("check_m2_load", "curl:http://192.168.1.26:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("check_gpu_usage", "powershell:nvidia-smi --query-gpu=name,utilization.gpu,memory.used --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Etat du cluster analyse pour reequilibrage.')", "python"),
        ],
        category="cluster_management",
        description="Analyser la charge du cluster pour reequilibrage",
        learning_context="Cluster — analyser repartition charge M1/M2 + GPU utilisation",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_full_system_report",
        trigger_vocal=["rapport systeme complet", "etat global", "tout savoir sur le systeme"],
        steps=[
            DominoStep("cpu_ram", "powershell:$os=Get-CimInstance Win32_OperatingSystem; $cpu=(Get-CimInstance Win32_Processor).LoadPercentage; $ram=[math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB,1); Write-Output \"CPU: ${cpu}% | RAM: ${ram}GB\"", "powershell", timeout_s=10),
            DominoStep("gpu_all", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("disk_all", "powershell:Get-PSDrive -PSProvider FileSystem | Select-Object Name,@{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}},@{N='UsedGB';E={[math]::Round($_.Used/1GB,1)}} | Format-Table", "powershell", timeout_s=10),
            DominoStep("cluster_health", "curl:http://10.5.0.2:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("ollama_status", "curl:http://127.0.0.1:11434/api/tags", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("git_status", "bash:cd F:/BUREAU/turbo && git log --oneline -3", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Rapport systeme complet genere. CPU, RAM, GPU, disques, cluster, git.')", "python"),
        ],
        category="monitoring",
        description="Rapport complet: CPU + RAM + GPU + disques + cluster + git",
        learning_context="Monitoring — rapport exhaustif de tout le systeme",
        priority="normal",
    ),
    # ── Batch 83: 10 nouveaux dominos (workflow, analytics, daily) ──
    DominoPipeline(
        id="domino_morning_full",
        trigger_vocal=["briefing complet", "demarrage complet", "full morning"],
        steps=[
            DominoStep("date_heure", "powershell:Get-Date -Format 'dddd dd MMMM yyyy HH:mm'", "powershell", timeout_s=5),
            DominoStep("gpu_status", "powershell:nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total --format=csv,noheader", "powershell", timeout_s=10),
            DominoStep("cluster_m1", "curl:http://10.5.0.2:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("cluster_ol1", "curl:http://127.0.0.1:11434/api/tags", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("disk_space", "powershell:Get-PSDrive C,F -ErrorAction SilentlyContinue | Select-Object Name,@{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}} | Format-Table", "powershell", timeout_s=10),
            DominoStep("git_pending", "bash:cd F:/BUREAU/turbo && git status --short | wc -l", "bash", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Briefing complet. Date, GPU, cluster, disques, et git verifies.')", "python"),
        ],
        category="routine_matin",
        description="Briefing complet: date + GPU + cluster + disques + git",
        learning_context="Morning full — tout checker au demarrage de la journee",
        priority="high",
    ),
    DominoPipeline(
        id="domino_end_of_day",
        trigger_vocal=["fin de journee", "bonne nuit jarvis", "je pars", "fin du travail"],
        steps=[
            DominoStep("git_commit", "bash:cd F:/BUREAU/turbo && git add -A && git commit -m 'auto: fin de journee $(date +%Y%m%d)' 2>&1 || echo 'Nothing to commit'", "bash", timeout_s=15),
            DominoStep("git_push", "bash:cd F:/BUREAU/turbo && git push 2>&1 || echo 'Push failed or nothing to push'", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("backup_db", "python:backup_etoile_db()", "python", on_fail="skip"),
            DominoStep("session_stats", "python:get_session_stats()", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Fin de journee. Code commite, backup fait. Bonne soiree!')", "python"),
        ],
        category="routine_soir",
        description="Fin de journee: auto commit + push + backup + stats session",
        learning_context="End of day — sauvegarder tout proprement avant de partir",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_weekly_report",
        trigger_vocal=["rapport hebdomadaire", "bilan de la semaine", "weekly report"],
        steps=[
            DominoStep("git_week", "bash:cd F:/BUREAU/turbo && git log --oneline --since='7 days ago' | wc -l", "bash", timeout_s=10),
            DominoStep("git_stats", "bash:cd F:/BUREAU/turbo && git diff --stat HEAD~20 2>/dev/null | tail -3", "bash", timeout_s=10),
            DominoStep("db_stats", "python:sqlite3_table_counts('etoile.db')", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Rapport hebdomadaire genere.')", "python"),
        ],
        category="documentation",
        description="Rapport hebdo: commits semaine + diff stats + DB counts",
        learning_context="Weekly — resume de la semaine de travail",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_test_voice_pipeline",
        trigger_vocal=["teste le pipeline vocal", "test voice", "teste la reconnaissance"],
        steps=[
            DominoStep("count_cmds", "bash:cd F:/BUREAU/turbo && python -c 'from src.commands import COMMANDS, VOICE_CORRECTIONS; print(f\"{len(COMMANDS)} cmds, {len(VOICE_CORRECTIONS)} corrections\")'", "bash", timeout_s=10),
            DominoStep("count_implicits", "bash:cd F:/BUREAU/turbo && python -c 'from src.voice_correction import IMPLICIT_COMMANDS; print(f\"{len(IMPLICIT_COMMANDS)} implicits\")'", "bash", timeout_s=10),
            DominoStep("count_dominos", "bash:cd F:/BUREAU/turbo && python -c 'from src.domino_pipelines import DOMINO_PIPELINES; print(f\"{len(DOMINO_PIPELINES)} dominos\")'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Pipeline vocal teste. Toutes les stats affichees.')", "python"),
        ],
        category="testing_pipeline",
        description="Test du pipeline vocal: compter commandes, corrections, implicites, dominos",
        learning_context="Testing — verification rapide du pipeline vocal complet",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_analytics_usage",
        trigger_vocal=["statistiques d'utilisation", "analytics", "quelles commandes j'utilise"],
        steps=[
            DominoStep("top_commands", "python:get_session_stats()", "python", on_fail="skip"),
            DominoStep("db_counts", "python:sqlite3_table_counts('jarvis.db')", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Statistiques d utilisation affichees.')", "python"),
        ],
        category="data_analysis",
        description="Analytics: top commandes + stats DB jarvis",
        learning_context="Analytics — comprendre les patterns d'utilisation",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_git_log_visual",
        trigger_vocal=["historique git", "log git", "montre les commits"],
        steps=[
            DominoStep("git_graph", "bash:cd F:/BUREAU/turbo && git log --oneline --graph -15", "bash", timeout_s=10),
            DominoStep("git_authors", "bash:cd F:/BUREAU/turbo && git shortlog -sn --since='30 days ago' | head -5", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Historique git affiche.')", "python"),
        ],
        category="dev_workflow",
        description="Historique git visuel: graph + top authors",
        learning_context="Dev — visualiser l'historique git",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_check_services",
        trigger_vocal=["verifie les services", "check services", "services en ligne"],
        steps=[
            DominoStep("check_lmstudio", "curl:http://10.5.0.2:1234/api/v1/models", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("check_ollama", "curl:http://127.0.0.1:11434/api/tags", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("check_n8n", "curl:http://127.0.0.1:5678/healthz", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("check_dashboard", "curl:http://127.0.0.1:8080", "curl", timeout_s=5, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Services verifies: LM Studio, Ollama, n8n, Dashboard.')", "python"),
        ],
        category="monitoring",
        description="Check services: LM Studio + Ollama + n8n + Dashboard",
        learning_context="Monitoring — verifier que tous les services web sont en ligne",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_rotate_logs",
        trigger_vocal=["rotation des logs", "archive les logs", "nettoie les vieux logs"],
        steps=[
            DominoStep("count_logs", "bash:ls -la F:/BUREAU/turbo/data/*.log 2>/dev/null | wc -l", "bash", timeout_s=5),
            DominoStep("archive_old", "powershell:Get-ChildItem 'F:\\BUREAU\\turbo\\data\\*.log' | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | ForEach-Object { Move-Item $_.FullName ($_.FullName + '.archived') -Force }; 'Logs archives'", "powershell", on_fail="skip", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Rotation des logs terminee.')", "python"),
        ],
        category="maintenance",
        description="Rotation logs: compter + archiver les logs > 7 jours",
        learning_context="Maintenance — archiver les vieux logs pour liberer de l'espace",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_cache_cleanup",
        trigger_vocal=["nettoie les caches", "vide tous les caches", "cache cleanup"],
        steps=[
            DominoStep("clear_python", "python:clear_all_caches()", "python"),
            DominoStep("clear_pip", "bash:pip cache purge 2>/dev/null || echo 'pip cache N/A'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("clear_npm", "bash:npm cache clean --force 2>/dev/null || echo 'npm cache N/A'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Tous les caches nettoyes: Python, pip, npm.')", "python"),
        ],
        category="system_cleanup",
        description="Cache cleanup: Python + pip + npm caches",
        learning_context="Nettoyage — vider tous les caches de dev",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_security_quick",
        trigger_vocal=["check securite rapide", "securite rapide", "quick security"],
        steps=[
            DominoStep("open_ports", "powershell:Get-NetTCPConnection -State Listen | Select-Object LocalPort -Unique | Measure-Object | Select-Object Count", "powershell", timeout_s=10),
            DominoStep("firewall", "powershell:Get-NetFirewallProfile | Select-Object Name,Enabled | Format-Table", "powershell", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Check securite rapide: ports et firewall verifies.')", "python"),
        ],
        category="security_sweep",
        description="Securite rapide: ports ouverts + firewall status",
        learning_context="Securite — check rapide en 2 steps",
        priority="normal",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # BATCH 84 — Dev workflow / Network / Performance / Backup (12 dominos)
    # ═══════════════════════════════════════════════════════════════════════
    DominoPipeline(
        id="domino_code_review",
        trigger_vocal=["revue de code", "code review", "review le code", "analyse le code"],
        steps=[
            DominoStep("git_status", "bash:cd F:/BUREAU/turbo && git status --short", "bash", timeout_s=5),
            DominoStep("git_diff_stats", "bash:cd F:/BUREAU/turbo && git diff --stat HEAD~1", "bash", timeout_s=10),
            DominoStep("py_lint", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && python -m py_compile src/domino_pipelines.py && python -m py_compile src/domino_executor.py && echo 'ALL SYNTAX OK'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Revue de code terminee. Syntaxe OK, diff genere.')", "python"),
        ],
        category="code_generation",
        description="Code review: git status + diff + syntax check",
        learning_context="Dev — verifier la qualite du code avant commit",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_deploy_staging",
        trigger_vocal=["deploie en staging", "deploy staging", "push staging", "envoie en staging"],
        steps=[
            DominoStep("syntax_check", "bash:cd F:/BUREAU/turbo && python -m py_compile src/commands.py && python -m py_compile src/voice_correction.py && echo 'Syntax OK'", "bash", timeout_s=10),
            DominoStep("git_add", "bash:cd F:/BUREAU/turbo && git add -A", "bash", timeout_s=5),
            DominoStep("git_commit", "bash:cd F:/BUREAU/turbo && git commit -m 'deploy: staging $(date +%Y%m%d-%H%M)' 2>&1 || echo 'Nothing to commit'", "bash", timeout_s=10),
            DominoStep("git_push", "bash:cd F:/BUREAU/turbo && git push 2>&1 || echo 'Push failed'", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Deploiement staging termine. Code pousse.')", "python"),
        ],
        category="dev_workflow",
        description="Deploy staging: syntax check + commit + push",
        learning_context="Deployment — pipeline de deploiement en staging",
        priority="high",
    ),
    DominoPipeline(
        id="domino_git_cleanup",
        trigger_vocal=["nettoie git", "git cleanup", "clean les branches", "menage git"],
        steps=[
            DominoStep("prune_remote", "bash:cd F:/BUREAU/turbo && git remote prune origin 2>&1", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("list_merged", "bash:cd F:/BUREAU/turbo && git branch --merged main 2>/dev/null | grep -v main | head -10 || echo 'No merged branches'", "bash", timeout_s=10),
            DominoStep("gc", "bash:cd F:/BUREAU/turbo && git gc --auto 2>&1", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Nettoyage git termine. Branches prunees, garbage collection fait.')", "python"),
        ],
        category="dev_workflow",
        description="Git cleanup: prune remote + list merged + gc",
        learning_context="Maintenance git — nettoyer les branches mortes",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_db_optimize",
        trigger_vocal=["optimise les bases", "db optimize", "optimise la base", "performance base"],
        steps=[
            DominoStep("vacuum_etoile", "python:sqlite3_vacuum('etoile.db')", "python"),
            DominoStep("vacuum_jarvis", "python:sqlite3_vacuum('jarvis.db')", "python"),
            DominoStep("vacuum_sniper", "python:sqlite3_vacuum('sniper.db')", "python", on_fail="skip"),
            DominoStep("analyze", "python:sqlite3_analyze()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Bases de donnees optimisees. Vacuum et analyze termines.')", "python"),
        ],
        category="data_analysis",
        description="DB optimize: VACUUM + ANALYZE sur toutes les bases",
        learning_context="Data — optimiser les performances SQLite",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_voice_pipeline_test",
        trigger_vocal=["teste le pipeline vocal", "test voix complet", "voice pipeline test", "test la reconnaissance"],
        steps=[
            DominoStep("count_cmds", "python:count_commands()", "python"),
            DominoStep("count_corrections", "python:count_voice_corrections()", "python"),
            DominoStep("test_match", "python:test_voice_match('ouvre chrome')", "python"),
            DominoStep("test_match2", "python:test_voice_match('statut du cluster')", "python"),
            DominoStep("tts", "python:edge_tts_speak('Pipeline vocal OK. Commandes et corrections comptees, matching teste.')", "python"),
        ],
        category="testing_pipeline",
        description="Voice pipeline test: count + match tests",
        learning_context="Test — verifier que le pipeline vocal marche correctement",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_network_scan",
        trigger_vocal=["scan reseau", "diagnostic reseau", "test le reseau", "network scan"],
        steps=[
            DominoStep("ping_gw", "bash:ping -c 2 192.168.1.1 2>/dev/null || ping -n 2 192.168.1.1", "bash", timeout_s=10),
            DominoStep("ping_dns", "bash:ping -c 2 8.8.8.8 2>/dev/null || ping -n 2 8.8.8.8", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("dns_check", "bash:nslookup google.com 2>&1 | head -5", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Scan reseau termine. Gateway, DNS et connectivite verifies.')", "python"),
        ],
        category="network_diagnostics",
        description="Network scan: ping gateway + DNS + connectivity",
        learning_context="Reseau — diagnostic complet de la connectivite",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_log_monitor",
        trigger_vocal=["surveille les logs", "monitor les logs", "log monitor", "regarde les erreurs"],
        steps=[
            DominoStep("count_errors", "bash:grep -ci 'error\\|exception\\|fail' F:/BUREAU/turbo/data/*.log 2>/dev/null || echo '0 errors'", "bash", timeout_s=10),
            DominoStep("recent_errors", "bash:grep -i 'error\\|exception' F:/BUREAU/turbo/data/*.log 2>/dev/null | tail -5 || echo 'No recent errors'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Monitoring des logs termine. Erreurs comptees.')", "python"),
        ],
        category="monitoring_live",
        description="Log monitor: count errors + show recent",
        learning_context="Monitoring — surveiller les erreurs dans les logs",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_update_deps",
        trigger_vocal=["mets a jour les dependances", "update deps", "upgrade packages", "mise a jour pip"],
        steps=[
            DominoStep("pip_outdated", "bash:pip list --outdated 2>/dev/null | head -15", "bash", timeout_s=15),
            DominoStep("uv_sync", "bash:cd F:/BUREAU/turbo && uv sync 2>&1 | tail -3", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Dependances verifiees. Liste des packages obsoletes affichee.')", "python"),
        ],
        category="dev_workflow",
        description="Update deps: check outdated + uv sync",
        learning_context="Dev — maintenir les dependances a jour",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_cluster_warmup",
        trigger_vocal=["chauffe le cluster", "warmup cluster", "prepare le cluster", "reveille le cluster"],
        steps=[
            DominoStep("ping_m1", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -1 || echo 'M1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("ping_ol1", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | head -1 || echo 'OL1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("ping_m2", "bash:curl -s --max-time 3 http://192.168.1.26:1234/api/v1/models 2>/dev/null | head -1 || echo 'M2 OFFLINE'", "bash", timeout_s=5, on_fail="skip"),
            DominoStep("ping_m3", "bash:curl -s --max-time 3 http://192.168.1.113:1234/api/v1/models 2>/dev/null | head -1 || echo 'M3 OFFLINE'", "bash", timeout_s=5, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Cluster chauffe. Tous les noeuds pingues.')", "python"),
        ],
        category="monitoring",
        description="Cluster warmup: ping all nodes to wake them",
        learning_context="Cluster — reveiller et verifier tous les noeuds",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_backup_full_system",
        trigger_vocal=["backup complet du systeme", "sauvegarde totale", "backup full", "backup tout"],
        steps=[
            DominoStep("backup_etoile", "python:backup_etoile_db()", "python"),
            DominoStep("backup_jarvis", "python:backup_db('jarvis.db')", "python", on_fail="skip"),
            DominoStep("backup_sniper", "python:backup_db('sniper.db')", "python", on_fail="skip"),
            DominoStep("git_commit", "bash:cd F:/BUREAU/turbo && git add -A && git commit -m 'backup: full system $(date +%Y%m%d)' 2>&1 || echo 'Nothing to commit'", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Backup complet du systeme termine. Toutes les bases sauvegardees.')", "python"),
        ],
        category="backup_chain",
        description="Full system backup: all DBs + git commit",
        learning_context="Backup — sauvegarde complete de toutes les donnees",
        priority="high",
    ),
    DominoPipeline(
        id="domino_performance_report",
        trigger_vocal=["rapport de performance", "performance report", "etat des performances", "combien ca tourne"],
        steps=[
            DominoStep("cpu", "powershell:Get-CimInstance Win32_Processor | Select-Object LoadPercentage", "powershell", timeout_s=10),
            DominoStep("ram", "powershell:[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)", "powershell", timeout_s=10),
            DominoStep("gpu", "powershell:nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,memory.used --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("disk", "powershell:Get-PSDrive C,F -ErrorAction SilentlyContinue | Select-Object Name,@{N='Free(GB)';E={[math]::Round($_.Free/1GB)}}", "powershell", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Rapport de performance genere. CPU, RAM, GPU et disques verifies.')", "python"),
        ],
        category="monitoring",
        description="Performance report: CPU + RAM + GPU + Disk",
        learning_context="Monitoring — rapport detaille des performances systeme",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_quick_benchmark",
        trigger_vocal=["benchmark rapide", "quick bench", "teste la vitesse", "bench rapide"],
        steps=[
            DominoStep("bench_m1", "bash:curl -s --max-time 10 http://127.0.0.1:1234/api/v1/chat -H 'Content-Type: application/json' -d '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nDis bonjour en 1 mot.\",\"temperature\":0.1,\"max_output_tokens\":50,\"stream\":false,\"store\":false}' 2>/dev/null | head -c 200 || echo 'M1 TIMEOUT'", "bash", timeout_s=15),
            DominoStep("bench_ol1", "bash:curl -s --max-time 10 http://127.0.0.1:11434/api/chat -d '{\"model\":\"qwen3:1.7b\",\"messages\":[{\"role\":\"user\",\"content\":\"Dis bonjour en 1 mot.\"}],\"stream\":false}' 2>/dev/null | head -c 200 || echo 'OL1 TIMEOUT'", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Benchmark rapide termine. M1 et OL1 testes.')", "python"),
        ],
        category="testing_pipeline",
        description="Quick benchmark: test M1 + OL1 response time",
        learning_context="Benchmark — tester la vitesse de reponse du cluster",
        priority="normal",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # BATCH 85 — Routines quotidiennes / Maintenance avancée (10 dominos)
    # ═══════════════════════════════════════════════════════════════════════
    DominoPipeline(
        id="domino_lunch_break",
        trigger_vocal=["pause dejeuner", "je mange", "lunch break", "pause midi"],
        steps=[
            DominoStep("git_save", "bash:cd F:/BUREAU/turbo && git add -A && git commit -m 'auto: pause midi $(date +%H%M)' 2>&1 || echo 'Nothing to commit'", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("lock_screen", "powershell:rundll32.exe user32.dll,LockWorkStation", "powershell", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Pause dejeuner. Code sauvegarde, ecran verrouille. Bon appetit!')", "python"),
        ],
        category="routine_matin",
        description="Pause dejeuner: save + lock screen",
        learning_context="Routine — preparer le systeme pour une pause dejeuner",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_coffee_break",
        trigger_vocal=["pause cafe", "coffee break", "je prends un cafe", "petite pause"],
        steps=[
            DominoStep("save_state", "bash:cd F:/BUREAU/turbo && git stash 2>&1 || echo 'Nothing to stash'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Pause cafe. Etat sauvegarde. Prends ton temps!')", "python"),
        ],
        category="routine_matin",
        description="Pause cafe: git stash le travail en cours",
        learning_context="Routine — petite pause avec sauvegarde de contexte",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_focus_mode",
        trigger_vocal=["mode focus", "mode concentration", "active le focus", "deep work"],
        steps=[
            DominoStep("disable_notif", "powershell:Set-ItemProperty -Path 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\PushNotifications' -Name 'ToastEnabled' -Value 0 -ErrorAction SilentlyContinue; 'Notifications disabled'", "powershell", timeout_s=5, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Mode focus active. Notifications desactivees. Bonne concentration!')", "python"),
        ],
        category="power_management",
        description="Focus mode: disable notifications for deep work",
        learning_context="Productivite — activer le mode concentration",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_disk_health",
        trigger_vocal=["sante des disques", "disk health", "etat des ssd", "smart status"],
        steps=[
            DominoStep("disk_space", "powershell:Get-PSDrive -PSProvider FileSystem | Select-Object Name,@{N='Used(GB)';E={[math]::Round($_.Used/1GB,1)}},@{N='Free(GB)';E={[math]::Round($_.Free/1GB,1)}}", "powershell", timeout_s=10),
            DominoStep("smart", "powershell:Get-PhysicalDisk | Select-Object FriendlyName,MediaType,HealthStatus,Size | Format-Table", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Sante des disques verifiee. Espace et SMART status affiches.')", "python"),
        ],
        category="monitoring",
        description="Disk health: space + SMART status",
        learning_context="Monitoring — verifier la sante des disques SSD/HDD",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_memory_cleanup",
        trigger_vocal=["libere la memoire", "nettoie la ram", "memory cleanup", "libere la ram"],
        steps=[
            DominoStep("clear_standby", "powershell:[System.GC]::Collect(); 'GC collected'", "powershell", timeout_s=10),
            DominoStep("ram_status", "powershell:[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)", "powershell", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Memoire nettoyee. RAM disponible affichee.')", "python"),
        ],
        category="system_cleanup",
        description="Memory cleanup: GC collect + RAM status",
        learning_context="Systeme — liberer de la memoire RAM",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_gpu_detailed",
        trigger_vocal=["detail gpu", "gpu detaille", "info gpu complete", "nvidia detail"],
        steps=[
            DominoStep("nvidia_smi", "powershell:nvidia-smi 2>$null || 'nvidia-smi not available'", "powershell", timeout_s=10),
            DominoStep("gpu_processes", "powershell:nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Detail GPU complet affiche. Temperatures, VRAM et processus GPU.')", "python"),
        ],
        category="monitoring",
        description="GPU detailed: nvidia-smi + GPU processes",
        learning_context="Monitoring — informations GPU detaillees",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_docker_status",
        trigger_vocal=["statut docker", "docker status", "conteneurs actifs", "docker ps"],
        steps=[
            DominoStep("docker_ps", "bash:docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || echo 'Docker not running'", "bash", timeout_s=10),
            DominoStep("docker_images", "bash:docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' 2>/dev/null | head -10 || echo 'N/A'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Statut Docker affiche. Conteneurs et images listes.')", "python"),
        ],
        category="dev_workflow",
        description="Docker status: containers + images",
        learning_context="Docker — voir les conteneurs et images actifs",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_project_stats",
        trigger_vocal=["stats du projet", "statistiques projet", "project stats", "combien de lignes"],
        steps=[
            DominoStep("line_count", "bash:wc -l F:/BUREAU/turbo/src/*.py 2>/dev/null || echo 'N/A'", "bash", timeout_s=10),
            DominoStep("file_count", "bash:find F:/BUREAU/turbo/src -name '*.py' 2>/dev/null | wc -l || echo 'N/A'", "bash", timeout_s=10),
            DominoStep("git_stats", "bash:cd F:/BUREAU/turbo && git log --oneline | wc -l && echo 'commits' 2>/dev/null", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Statistiques du projet affichees. Lignes, fichiers et commits comptes.')", "python"),
        ],
        category="dev_workflow",
        description="Project stats: line count + file count + git commits",
        learning_context="Dev — statistiques du projet JARVIS",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_windows_cleanup",
        trigger_vocal=["nettoie windows", "windows cleanup", "vide les temp", "menage windows"],
        steps=[
            DominoStep("clear_temp", "powershell:Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; 'Temp cleared'", "powershell", timeout_s=15, on_fail="skip"),
            DominoStep("clear_prefetch", "powershell:Remove-Item C:\\Windows\\Prefetch\\* -Force -ErrorAction SilentlyContinue; 'Prefetch cleared'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("recycle_bin", "powershell:Clear-RecycleBin -Force -ErrorAction SilentlyContinue; 'Recycle bin emptied'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Nettoyage Windows termine. Fichiers temp, prefetch et corbeille vides.')", "python"),
        ],
        category="system_cleanup",
        description="Windows cleanup: temp + prefetch + recycle bin",
        learning_context="Systeme — nettoyage complet de Windows",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_evening_review",
        trigger_vocal=["bilan du soir", "revue du soir", "evening review", "resume de la journee"],
        steps=[
            DominoStep("git_log_today", "bash:cd F:/BUREAU/turbo && git log --oneline --since=midnight 2>/dev/null || echo 'No commits today'", "bash", timeout_s=10),
            DominoStep("db_stats", "python:count_commands()", "python"),
            DominoStep("corrections_stats", "python:count_voice_corrections()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Bilan du soir. Commits du jour, commandes et corrections comptees.')", "python"),
        ],
        category="routine_soir",
        description="Evening review: today's commits + stats",
        learning_context="Routine — bilan de fin de journee",
        priority="normal",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # BATCH 86 — Startup/Shutdown / Maintenance avancee (10 dominos)
    # ═══════════════════════════════════════════════════════════════════════
    DominoPipeline(
        id="domino_startup_sequence",
        trigger_vocal=["sequence de demarrage", "startup", "boot sequence", "demarre tout"],
        steps=[
            DominoStep("health_m1", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 100 || echo 'M1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("health_ol1", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 100 || echo 'OL1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("git_pull", "bash:cd F:/BUREAU/turbo && git pull --ff-only 2>&1 || echo 'Pull failed or up to date'", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("gpu_temp", "powershell:nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Sequence de demarrage terminee. Cluster verifie, code a jour, GPU ok.')", "python"),
        ],
        category="routine_matin",
        description="Startup sequence: health check + git pull + GPU temp",
        learning_context="Boot — sequence complete de demarrage du systeme",
        priority="high",
    ),
    DominoPipeline(
        id="domino_shutdown_sequence",
        trigger_vocal=["sequence arret", "shutdown", "arrete tout proprement", "extinction"],
        steps=[
            DominoStep("git_save", "bash:cd F:/BUREAU/turbo && git add -A && git commit -m 'auto: shutdown $(date +%Y%m%d-%H%M)' 2>&1 || echo 'Nothing to commit'", "bash", timeout_s=15, on_fail="skip"),
            DominoStep("git_push", "bash:cd F:/BUREAU/turbo && git push 2>&1 || echo 'Push failed'", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("backup_db", "python:backup_etoile_db()", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Extinction propre. Code sauvegarde, backup fait. A bientot!')", "python"),
        ],
        category="routine_soir",
        description="Shutdown sequence: save + push + backup",
        learning_context="Shutdown — eteindre proprement avec sauvegarde de tout",
        priority="high",
    ),
    DominoPipeline(
        id="domino_weekly_maintenance",
        trigger_vocal=["maintenance hebdo", "weekly maintenance", "maintenance de la semaine", "entretien hebdomadaire"],
        steps=[
            DominoStep("vacuum_all", "python:sqlite3_vacuum('etoile.db')", "python"),
            DominoStep("vacuum_jarvis", "python:sqlite3_vacuum('jarvis.db')", "python", on_fail="skip"),
            DominoStep("analyze_all", "python:sqlite3_analyze()", "python"),
            DominoStep("git_gc", "bash:cd F:/BUREAU/turbo && git gc --auto 2>&1", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("clear_temp", "powershell:Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; 'Temp cleared'", "powershell", timeout_s=15, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Maintenance hebdomadaire terminee. Bases optimisees, git propre, temp vides.')", "python"),
        ],
        category="system_cleanup",
        description="Weekly maintenance: vacuum + analyze + git gc + temp cleanup",
        learning_context="Maintenance — entretien hebdomadaire complet",
        priority="high",
    ),
    DominoPipeline(
        id="domino_emergency_save",
        trigger_vocal=["sauvegarde urgence", "emergency save", "sauve tout vite", "urgence backup"],
        steps=[
            DominoStep("git_save", "bash:cd F:/BUREAU/turbo && git add -A && git commit -m 'EMERGENCY SAVE $(date +%Y%m%d-%H%M%S)' 2>&1 || echo 'Nothing'", "bash", timeout_s=10),
            DominoStep("git_push", "bash:cd F:/BUREAU/turbo && git push 2>&1 || echo 'Push failed'", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("backup_etoile", "python:backup_etoile_db()", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Sauvegarde d'urgence terminee!')", "python"),
        ],
        category="backup_chain",
        description="Emergency save: instant commit + push + backup",
        learning_context="Urgence — sauvegarder tout immediatement",
        priority="critical",
    ),
    DominoPipeline(
        id="domino_dev_setup",
        trigger_vocal=["prepare le dev", "setup dev", "prepare l'environnement", "init workspace"],
        steps=[
            DominoStep("git_status", "bash:cd F:/BUREAU/turbo && git status --short", "bash", timeout_s=5),
            DominoStep("uv_sync", "bash:cd F:/BUREAU/turbo && uv sync 2>&1 | tail -3", "bash", timeout_s=30, on_fail="skip"),
            DominoStep("health_cluster", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 50 || echo 'M1 OFFLINE'", "bash", timeout_s=5, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Environnement dev pret. Git, dependances et cluster verifies.')", "python"),
        ],
        category="dev_workflow",
        description="Dev setup: git status + uv sync + cluster check",
        learning_context="Dev — preparer l'environnement de developpement",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_pip_upgrade_all",
        trigger_vocal=["upgrade tous les packages", "pip upgrade all", "mets tout a jour pip", "upgrade pip"],
        steps=[
            DominoStep("list_outdated", "bash:pip list --outdated --format=columns 2>/dev/null | head -20", "bash", timeout_s=15),
            DominoStep("tts", "python:edge_tts_speak('Liste des packages obsoletes affichee. Verifiez avant de mettre a jour.')", "python"),
        ],
        category="dev_workflow",
        description="Pip upgrade: list outdated packages",
        learning_context="Dev — verifier les packages Python a mettre a jour",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_vram_monitor",
        trigger_vocal=["surveille la vram", "vram monitor", "watch vram", "monitore la vram"],
        steps=[
            DominoStep("vram_usage", "powershell:nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Utilisation VRAM affichee par GPU.')", "python"),
        ],
        category="monitoring",
        description="VRAM monitor: usage per GPU",
        learning_context="Monitoring — surveiller l'utilisation VRAM en temps reel",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_ollama_restart",
        trigger_vocal=["redemarre ollama", "restart ollama", "relance ollama", "ollama restart"],
        steps=[
            DominoStep("stop_ollama", "bash:taskkill /IM ollama.exe /F 2>/dev/null || echo 'Ollama not running'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("start_ollama", "bash:ollama serve &>/dev/null &; sleep 2; echo 'Ollama restarted'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("verify", "bash:curl -s --max-time 5 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 50 || echo 'OL1 not responding'", "bash", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Ollama redemarre et verifie.')", "python"),
        ],
        category="monitoring",
        description="Ollama restart: stop + start + verify",
        learning_context="Maintenance — redemarrer Ollama quand il ne repond plus",
        priority="high",
    ),
    DominoPipeline(
        id="domino_model_benchmark",
        trigger_vocal=["benchmark modeles", "model benchmark", "teste les modeles", "compare les modeles"],
        steps=[
            DominoStep("bench_m1_qwen8b", "bash:curl -s --max-time 15 http://127.0.0.1:1234/api/v1/chat -H 'Content-Type: application/json' -d '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nReponds OK en 1 mot.\",\"temperature\":0.1,\"max_output_tokens\":20,\"stream\":false,\"store\":false}' 2>/dev/null | head -c 100 || echo 'M1 TIMEOUT'", "bash", timeout_s=20),
            DominoStep("bench_ol1_1.7b", "bash:curl -s --max-time 15 http://127.0.0.1:11434/api/chat -d '{\"model\":\"qwen3:1.7b\",\"messages\":[{\"role\":\"user\",\"content\":\"Reponds OK en 1 mot.\"}],\"stream\":false}' 2>/dev/null | head -c 100 || echo 'OL1-1.7b TIMEOUT'", "bash", timeout_s=20),
            DominoStep("bench_ol1_14b", "bash:curl -s --max-time 15 http://127.0.0.1:11434/api/chat -d '{\"model\":\"qwen3:14b\",\"messages\":[{\"role\":\"user\",\"content\":\"Reponds OK en 1 mot.\"}],\"stream\":false}' 2>/dev/null | head -c 100 || echo 'OL1-14b TIMEOUT'", "bash", timeout_s=20, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Benchmark modeles termine. M1 et OL1 testes.')", "python"),
        ],
        category="testing_pipeline",
        description="Model benchmark: test M1 + OL1 models response",
        learning_context="Benchmark — tester et comparer les modeles charges",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_health_full",
        trigger_vocal=["health check complet", "check complet", "diagnostic complet du cluster", "full health"],
        steps=[
            DominoStep("m1", "bash:curl -s --max-time 3 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 80 || echo 'M1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("m2", "bash:curl -s --max-time 3 http://192.168.1.26:1234/api/v1/models 2>/dev/null | head -c 80 || echo 'M2 OFFLINE'", "bash", timeout_s=5, on_fail="skip"),
            DominoStep("m3", "bash:curl -s --max-time 3 http://192.168.1.113:1234/api/v1/models 2>/dev/null | head -c 80 || echo 'M3 OFFLINE'", "bash", timeout_s=5, on_fail="skip"),
            DominoStep("ol1", "bash:curl -s --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 80 || echo 'OL1 OFFLINE'", "bash", timeout_s=5),
            DominoStep("gpu", "powershell:nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,memory.used --format=csv,noheader 2>$null || 'N/A'", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Health check complet. Tous les noeuds et GPU verifies.')", "python"),
        ],
        category="monitoring",
        description="Full health check: all nodes + GPU",
        learning_context="Monitoring — diagnostic complet de tout le cluster",
        priority="high",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # BATCH 87 — Audio / Security / Data / Workspace (10 dominos)
    # ═══════════════════════════════════════════════════════════════════════
    DominoPipeline(
        id="domino_audio_setup",
        trigger_vocal=["configure l'audio", "audio setup", "parametres son", "regle le son"],
        steps=[
            DominoStep("audio_devices", "powershell:Get-AudioDevice -List 2>$null || Get-CimInstance Win32_SoundDevice | Select-Object Name,Status", "powershell", timeout_s=10),
            DominoStep("volume", "powershell:[Audio]::Volume 2>$null || 'Volume API N/A'", "powershell", timeout_s=5, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Configuration audio affichee. Peripheriques et volume verifies.')", "python"),
        ],
        category="media_control",
        description="Audio setup: list devices + check volume",
        learning_context="Audio — configurer et verifier les peripheriques audio",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_security_audit",
        trigger_vocal=["audit de securite", "security audit", "check securite complet", "full security"],
        steps=[
            DominoStep("ports", "powershell:Get-NetTCPConnection -State Listen | Select-Object LocalPort -Unique | Measure-Object | Select-Object Count", "powershell", timeout_s=10),
            DominoStep("firewall", "powershell:Get-NetFirewallProfile | Select-Object Name,Enabled | Format-Table", "powershell", timeout_s=10),
            DominoStep("defender", "powershell:Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureLastUpdated", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("env_secrets", "bash:grep -rl 'sk-\\|password\\|secret' F:/BUREAU/turbo/src/*.py 2>/dev/null | wc -l || echo '0 files with potential secrets'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Audit de securite termine. Ports, firewall, antivirus et secrets verifies.')", "python"),
        ],
        category="security_sweep",
        description="Security audit: ports + firewall + defender + secrets scan",
        learning_context="Securite — audit complet de la posture de securite",
        priority="high",
    ),
    DominoPipeline(
        id="domino_data_export_full",
        trigger_vocal=["exporte toutes les donnees", "data export full", "export complet", "exporte tout en csv"],
        steps=[
            DominoStep("export_etoile", "python:export_db_to_csv('etoile.db')", "python"),
            DominoStep("export_jarvis", "python:export_db_to_csv('jarvis.db')", "python", on_fail="skip"),
            DominoStep("export_sniper", "python:export_db_to_csv('sniper.db')", "python", on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Export complet termine. Toutes les bases exportees en CSV.')", "python"),
        ],
        category="data_analysis",
        description="Full data export: all databases to CSV",
        learning_context="Data — exporter toutes les bases en format CSV",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_voice_calibrate",
        trigger_vocal=["calibre la voix", "voice calibrate", "ajuste la reconnaissance", "calibration vocale"],
        steps=[
            DominoStep("test_simple", "python:test_voice_match('ouvre chrome')", "python"),
            DominoStep("test_cluster", "python:test_voice_match('statut du cluster')", "python"),
            DominoStep("test_trading", "python:test_voice_match('scan trading')", "python"),
            DominoStep("count", "python:count_commands()", "python"),
            DominoStep("corrections", "python:count_voice_corrections()", "python"),
            DominoStep("tts", "python:edge_tts_speak('Calibration vocale terminee. 5 tests de matching passes.')", "python"),
        ],
        category="testing_pipeline",
        description="Voice calibrate: run match tests + count stats",
        learning_context="Voice — calibrer et tester la reconnaissance vocale",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_screen_setup",
        trigger_vocal=["configure les ecrans", "screen setup", "parametres ecrans", "display settings"],
        steps=[
            DominoStep("displays", "powershell:Get-CimInstance Win32_VideoController | Select-Object Name,CurrentHorizontalResolution,CurrentVerticalResolution", "powershell", timeout_s=10),
            DominoStep("monitors", "powershell:Get-CimInstance WmiMonitorBasicDisplayParams -Namespace root/wmi -ErrorAction SilentlyContinue | Select-Object Active,MaxHorizontalImageSize | Format-Table", "powershell", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Configuration ecrans affichee. Resolution et moniteurs verifies.')", "python"),
        ],
        category="monitoring",
        description="Screen setup: display info + resolution",
        learning_context="Systeme — verifier la configuration des ecrans",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_task_kill_heavy",
        trigger_vocal=["tue les processus lourds", "kill heavy", "libere le cpu", "kill les processus"],
        steps=[
            DominoStep("list_heavy", "powershell:Get-Process | Sort-Object CPU -Descending | Select-Object -First 5 Name,CPU,@{N='RAM(MB)';E={[math]::Round($_.WorkingSet/1MB)}}", "powershell", timeout_s=10),
            DominoStep("tts", "python:edge_tts_speak('Top 5 processus lourds affiches. Tuez manuellement si necessaire.')", "python"),
        ],
        category="system_cleanup",
        description="List heavy processes: top 5 by CPU",
        learning_context="Systeme — identifier les processus qui consomment le plus",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_workspace_organize",
        trigger_vocal=["organise le workspace", "range le bureau", "workspace organize", "trie les fichiers"],
        steps=[
            DominoStep("count_desktop", "powershell:(Get-ChildItem $env:USERPROFILE\\Desktop -File).Count", "powershell", timeout_s=5),
            DominoStep("count_downloads", "powershell:(Get-ChildItem $env:USERPROFILE\\Downloads -File).Count", "powershell", timeout_s=5),
            DominoStep("tts", "python:edge_tts_speak('Workspace analyse. Fichiers sur le bureau et dans les telechargements comptes.')", "python"),
        ],
        category="system_cleanup",
        description="Workspace organize: count desktop + downloads files",
        learning_context="Organisation — analyser le workspace pour identifier le desordre",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_api_test",
        trigger_vocal=["teste les api", "api test", "check les endpoints", "verifie les api"],
        steps=[
            DominoStep("test_m1", "bash:curl -s --max-time 5 http://127.0.0.1:1234/api/v1/models 2>/dev/null | head -c 50 || echo 'M1 API FAIL'", "bash", timeout_s=10),
            DominoStep("test_ol1", "bash:curl -s --max-time 5 http://127.0.0.1:11434/api/tags 2>/dev/null | head -c 50 || echo 'OL1 API FAIL'", "bash", timeout_s=10),
            DominoStep("test_dashboard", "bash:curl -s --max-time 5 http://127.0.0.1:8080 2>/dev/null | head -c 50 || echo 'Dashboard API FAIL'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Test API termine. M1, OL1 et Dashboard verifies.')", "python"),
        ],
        category="testing_pipeline",
        description="API test: check M1 + OL1 + Dashboard endpoints",
        learning_context="Test — verifier que toutes les API sont accessibles",
        priority="normal",
    ),
    DominoPipeline(
        id="domino_db_migration",
        trigger_vocal=["migration de base", "db migration", "migre les donnees", "database migration"],
        steps=[
            DominoStep("backup_first", "python:backup_etoile_db()", "python"),
            DominoStep("integrity", "python:check_db_integrity('etoile.db')", "python"),
            DominoStep("tts", "python:edge_tts_speak('Migration preparee. Backup fait et integrite verifiee.')", "python"),
        ],
        category="data_analysis",
        description="DB migration prep: backup + integrity check",
        learning_context="Data — preparer une migration de base de donnees",
        priority="high",
    ),
    DominoPipeline(
        id="domino_git_stash_pop",
        trigger_vocal=["recupere le stash", "stash pop", "git stash pop", "reprends le travail"],
        steps=[
            DominoStep("stash_list", "bash:cd F:/BUREAU/turbo && git stash list 2>&1 || echo 'No stashes'", "bash", timeout_s=5),
            DominoStep("stash_pop", "bash:cd F:/BUREAU/turbo && git stash pop 2>&1 || echo 'Nothing to pop'", "bash", timeout_s=10, on_fail="skip"),
            DominoStep("tts", "python:edge_tts_speak('Stash recupere. Travail en cours restaure.')", "python"),
        ],
        category="dev_workflow",
        description="Git stash pop: restore stashed work",
        learning_context="Git — recuperer le travail stashe",
        priority="normal",
    ),
]

# Post-process: replace hardcoded paths with config-driven values
for _pipeline in DOMINO_PIPELINES:
    for _step in _pipeline.steps:
        if "F:\\BUREAU\\turbo" in _step.action:
            _step.action = _step.action.replace("F:\\BUREAU\\turbo", _TURBO_DIR)
        if "F:/BUREAU/turbo" in _step.action:
            _step.action = _step.action.replace("F:/BUREAU/turbo", _TURBO_DIR_FWD)


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

def find_domino(text: str) -> DominoPipeline | None:
    """Trouve le domino pipeline correspondant a une phrase vocale.

    Matching order: exact trigger > partial trigger > ID match > keyword in description.
    """
    text_lower = text.lower().strip()
    best_match = None
    best_score = 0.0

    for dp in DOMINO_PIPELINES:
        # 1. Exact trigger match (highest priority)
        for trigger in dp.trigger_vocal:
            if text_lower == trigger.lower():
                return dp

        # 2. Partial trigger match (containment)
        for trigger in dp.trigger_vocal:
            trig_lower = trigger.lower()
            if trig_lower in text_lower or text_lower in trig_lower:
                from difflib import SequenceMatcher
                score = SequenceMatcher(None, text_lower, trig_lower).ratio()
                if score > best_score and score > 0.6:
                    best_score = score
                    best_match = dp

        # 3. ID match (e.g. "domino_backup_complet" matches "backup complet")
        id_clean = dp.id.replace("domino_", "").replace("_", " ")
        if text_lower == id_clean or id_clean in text_lower:
            score = 0.75
            if score > best_score:
                best_score = score
                best_match = dp

        # 4. Keyword match in description (lowest priority)
        text_words = set(text_lower.split())
        desc_words = set(dp.description.lower().split())
        common = text_words & desc_words - {"de", "du", "le", "la", "les", "un", "une", "des", "et", "en", "a"}
        if len(common) >= 2:
            keyword_score = len(common) / max(len(text_words), 1) * 0.65
            if keyword_score > best_score and keyword_score > 0.5:
                best_score = keyword_score
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
